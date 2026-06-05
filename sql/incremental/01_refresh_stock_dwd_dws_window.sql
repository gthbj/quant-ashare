-- 文档维护：GPT-5（最近更新 2026-06-05）
-- BigQuery Standard SQL
-- OQ-005 Phase 2.2: 股票 DWD/DWS 窗口化刷新。
--
-- 口径：
-- - 目标表必须已由全量 CTAS 路径初始化。
-- - 本脚本只刷新股票日频 DWD 与策略 1 DWS，不写 ADS run/backtest 产物。
-- - DWD 写入窗口由 date_from/date_to 或 business_date 控制。
-- - daily_current 模式：默认刷新最近 20 个交易日（含当天），确保估值缺口自动修复。
-- - backfill 模式：显式 date_from/date_to，不做自动扩展。
-- - 价格特征读取窗口按 SSE 交易日历往前推 60 个交易日。
-- - 估值特征读取窗口按每只股票写入窗口首日前的实际 60 条估值观测推导，覆盖 daily_basic 缺口。
-- - 标签写入窗口按 SSE 交易日历往前推 20 个交易日，避免 t+H forward label 受 late data/生命周期变更影响后未回填。

DECLARE p_business_date DATE DEFAULT COALESCE(SAFE_CAST(NULLIF(@business_date, '') AS DATE), CURRENT_DATE('Asia/Shanghai'));
DECLARE p_date_from DATE DEFAULT SAFE_CAST(NULLIF(@date_from, '') AS DATE);
DECLARE p_requested_date_to DATE DEFAULT COALESCE(SAFE_CAST(NULLIF(@date_to, '') AS DATE), p_business_date);
DECLARE p_warehouse_mode STRING DEFAULT LOWER(NULLIF(@warehouse_mode, ''));
DECLARE p_date_to DATE DEFAULT CASE
  WHEN p_warehouse_mode = 'daily_current' THEN COALESCE(
    (
      SELECT MAX(cal_date)
      FROM `data-aquarium.ashare_dim.dim_trade_calendar`
      WHERE exchange = 'SSE'
        AND is_open = 1
        AND cal_date <= p_requested_date_to
    ),
    p_requested_date_to
  )
  ELSE p_requested_date_to
END;
DECLARE p_final_start_date DATE DEFAULT DATE '2019-01-01';
DECLARE p_feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_fin_feature_version STRING DEFAULT 'fin_default_v0_20260602';
DECLARE p_label_version STRING DEFAULT 'open_to_close_h1_5_10_20_v20260601';
DECLARE p_universe_version STRING DEFAULT 'universe_pv_v0_20260601';
DECLARE p_min_list_age_td INT64 DEFAULT 120;
DECLARE p_min_amount_ma20_cny FLOAT64 DEFAULT 50000000.0;
DECLARE p_min_close_price FLOAT64 DEFAULT 3.0;
DECLARE p_board_allowlist ARRAY<STRING> DEFAULT ['SSE_MAIN', 'SZSE_MAIN'];
DECLARE p_asof_lookback_days INT64 DEFAULT 900;
DECLARE p_valuation_observation_window INT64 DEFAULT 60;
DECLARE p_daily_current_lookback_td INT64 DEFAULT 20;

-- daily_current 模式：若 date_from 未显式指定，先将 date_to/business_date 归一为
-- 不晚于请求日期的最近 SSE 开市日，再自动往前推 20 个交易日。
-- backfill 模式：保持显式 date_from/date_to 不变。
DECLARE p_end_date_seq INT64 DEFAULT (
  SELECT trade_date_seq
  FROM `data-aquarium.ashare_dim.dim_trade_calendar`
  WHERE exchange = 'SSE'
    AND is_open = 1
    AND cal_date = p_date_to
  LIMIT 1
);
DECLARE p_daily_current_start_date DATE DEFAULT COALESCE(
  (
    SELECT MAX(cal_date)
    FROM `data-aquarium.ashare_dim.dim_trade_calendar`
    WHERE exchange = 'SSE'
      AND is_open = 1
      AND trade_date_seq <= p_end_date_seq - p_daily_current_lookback_td + 1
  ),
  p_date_to
);
DECLARE p_dwd_write_start_date DATE DEFAULT GREATEST(
  CASE
    WHEN p_warehouse_mode = 'daily_current' AND p_date_from IS NULL
      THEN p_daily_current_start_date
    ELSE COALESCE(p_date_from, p_date_to)
  END,
  p_final_start_date
);
DECLARE p_write_end_date DATE DEFAULT p_date_to;
DECLARE p_anchor_seq INT64 DEFAULT (
  SELECT MIN(trade_date_seq)
  FROM `data-aquarium.ashare_dim.dim_trade_calendar`
  WHERE exchange = 'SSE'
    AND is_open = 1
    AND cal_date >= p_dwd_write_start_date
);
DECLARE p_feature_read_start_date DATE DEFAULT GREATEST(
  COALESCE(
    (
      SELECT MAX(cal_date)
      FROM `data-aquarium.ashare_dim.dim_trade_calendar`
      WHERE exchange = 'SSE'
        AND is_open = 1
        AND trade_date_seq <= p_anchor_seq - 60
    ),
    DATE_SUB(p_dwd_write_start_date, INTERVAL 90 DAY)
  ),
  p_final_start_date
);
DECLARE p_valuation_feature_read_start_date DATE DEFAULT p_dwd_write_start_date;
DECLARE p_label_write_start_date DATE DEFAULT GREATEST(
  COALESCE(
    (
      SELECT MAX(cal_date)
      FROM `data-aquarium.ashare_dim.dim_trade_calendar`
      WHERE exchange = 'SSE'
        AND is_open = 1
        AND trade_date_seq <= p_anchor_seq - 20
    ),
    DATE_SUB(p_dwd_write_start_date, INTERVAL 35 DAY)
  ),
  p_final_start_date
);

IF p_write_end_date < p_dwd_write_start_date THEN
  RAISE USING MESSAGE = CONCAT(
    'windowed refresh requires write_end_date >= dwd_write_start_date; got ',
    CAST(p_write_end_date AS STRING),
    ' < ',
    CAST(p_dwd_write_start_date AS STRING)
  );
END IF;

ASSERT (
  SELECT COUNT(*) = 2
  FROM `data-aquarium.ashare_dwd.INFORMATION_SCHEMA.TABLES`
  WHERE table_name IN ('dwd_stock_eod_price', 'dwd_stock_eod_valuation')
) AS 'windowed refresh target DWD tables must exist; run full_rebuild/full_rebuild_compat before daily_current/backfill';

ASSERT (
  SELECT COUNT(*) = 7
  FROM `data-aquarium.ashare_dws.INFORMATION_SCHEMA.TABLES`
  WHERE table_name IN (
    'dws_stock_universe_daily',
    'dws_stock_feature_price_daily',
    'dws_stock_feature_valuation_daily',
    'dws_stock_feature_fin_daily',
    'dws_stock_label_daily',
    'dws_stock_feature_daily_v0',
    'dws_stock_sample_daily'
  )
) AS 'windowed refresh target DWS tables must exist; run full_rebuild/full_rebuild_compat before daily_current/backfill';

BEGIN TRANSACTION;

-- ────────────────────────────────────────────────────────────────────────────
-- DWD: dwd_stock_eod_price
-- ────────────────────────────────────────────────────────────────────────────

DELETE FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price`
WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date;

INSERT INTO `data-aquarium.ashare_dwd.dwd_stock_eod_price` (
  trade_date,
  sec_code,
  open,
  high,
  low,
  close,
  pre_close,
  change,
  pct_chg,
  volume_lot,
  amount_k_cny,
  volume_share,
  amount_cny,
  adj_factor,
  open_hfq,
  high_hfq,
  low_hfq,
  close_hfq,
  ret_1d,
  up_limit,
  down_limit,
  is_limit_up,
  is_limit_down,
  is_one_word_limit_up,
  is_one_word_limit_down,
  is_suspended,
  suspend_timing,
  suspend_type,
  has_intraday_halt,
  has_open_halt,
  can_buy_open,
  can_sell_open,
  is_tradable,
  has_limit_data,
  has_suspend_event_data,
  source_system,
  source_partition_date,
  ingested_at
)
WITH cal AS (
  SELECT cal_date AS trade_date
  FROM `data-aquarium.ashare_dim.dim_trade_calendar`
  WHERE exchange = 'SSE'
    AND is_open = 1
    AND cal_date BETWEEN p_dwd_write_start_date AND p_write_end_date
),
universe AS (
  SELECT
    c.trade_date,
    s.sec_code
  FROM cal AS c
  JOIN `data-aquarium.ashare_dim.dim_stock` AS s
    ON c.trade_date >= COALESCE(s.list_date, DATE '1900-01-01')
   AND (s.delist_date IS NULL OR c.trade_date < s.delist_date)
),
daily AS (
  SELECT
    ts_code AS sec_code,
    SAFE.PARSE_DATE('%Y%m%d', trade_date) AS trade_date,
    SAFE_CAST(open AS FLOAT64) AS open,
    SAFE_CAST(high AS FLOAT64) AS high,
    SAFE_CAST(low AS FLOAT64) AS low,
    SAFE_CAST(close AS FLOAT64) AS close,
    SAFE_CAST(pre_close AS FLOAT64) AS pre_close,
    SAFE_CAST(change AS FLOAT64) AS change,
    SAFE_CAST(pct_chg AS FLOAT64) AS pct_chg,
    SAFE_CAST(vol AS FLOAT64) AS volume_lot,
    SAFE_CAST(amount AS FLOAT64) AS amount_k_cny,
    partition_date AS source_partition_date,
    SAFE_CAST(_ingested_at AS TIMESTAMP) AS ingested_at
  FROM `data-aquarium.ashare_ods.ods_tushare_daily`
  WHERE endpoint = 'daily'
    AND partition_date BETWEEN FORMAT_DATE('%Y%m%d', p_dwd_write_start_date) AND FORMAT_DATE('%Y%m%d', p_write_end_date)
    AND SAFE.PARSE_DATE('%Y%m%d', trade_date) BETWEEN p_dwd_write_start_date AND p_write_end_date
),
adj_factor AS (
  SELECT
    ts_code AS sec_code,
    SAFE.PARSE_DATE('%Y%m%d', trade_date) AS trade_date,
    SAFE_CAST(adj_factor AS FLOAT64) AS adj_factor
  FROM `data-aquarium.ashare_ods.ods_tushare_adj_factor`
  WHERE endpoint = 'adj_factor'
    AND partition_date BETWEEN FORMAT_DATE('%Y%m%d', p_dwd_write_start_date) AND FORMAT_DATE('%Y%m%d', p_write_end_date)
    AND SAFE.PARSE_DATE('%Y%m%d', trade_date) BETWEEN p_dwd_write_start_date AND p_write_end_date
),
limit_price AS (
  SELECT
    ts_code AS sec_code,
    SAFE.PARSE_DATE('%Y%m%d', trade_date) AS trade_date,
    SAFE_CAST(up_limit AS FLOAT64) AS up_limit,
    SAFE_CAST(down_limit AS FLOAT64) AS down_limit
  FROM `data-aquarium.ashare_ods.ods_tushare_stk_limit`
  WHERE endpoint = 'stk_limit'
    AND partition_date BETWEEN FORMAT_DATE('%Y%m%d', p_dwd_write_start_date) AND FORMAT_DATE('%Y%m%d', p_write_end_date)
    AND SAFE.PARSE_DATE('%Y%m%d', trade_date) BETWEEN p_dwd_write_start_date AND p_write_end_date
),
suspend_event AS (
  SELECT
    ts_code AS sec_code,
    SAFE.PARSE_DATE('%Y%m%d', trade_date) AS trade_date,
    STRING_AGG(DISTINCT suspend_timing, ',' ORDER BY suspend_timing) AS suspend_timing,
    'S' AS suspend_type,
    LOGICAL_OR(suspend_timing IS NULL) AS has_unknown_halt_timing,
    LOGICAL_OR(REGEXP_CONTAINS(COALESCE(suspend_timing, ''), r'(^|,)\s*(0?9:00|0?9:15|0?9:20|0?9:25|0?9:30)-')) AS has_open_halt_event
  FROM `data-aquarium.ashare_ods.ods_tushare_suspend_d`
  WHERE endpoint = 'suspend_d'
    AND partition_date BETWEEN FORMAT_DATE('%Y%m%d', p_dwd_write_start_date) AND FORMAT_DATE('%Y%m%d', p_write_end_date)
    AND suspend_type = 'S'
    AND SAFE.PARSE_DATE('%Y%m%d', trade_date) BETWEEN p_dwd_write_start_date AND p_write_end_date
  GROUP BY sec_code, trade_date
),
prev_close AS (
  SELECT
    sec_code,
    ARRAY_AGG(close_hfq IGNORE NULLS ORDER BY trade_date DESC LIMIT 1)[SAFE_OFFSET(0)] AS prev_close_hfq
  FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price`
  WHERE trade_date BETWEEN DATE_SUB(p_dwd_write_start_date, INTERVAL 730 DAY) AND DATE_SUB(p_dwd_write_start_date, INTERVAL 1 DAY)
  GROUP BY sec_code
),
joined AS (
  SELECT
    u.trade_date,
    u.sec_code,
    d.open,
    d.high,
    d.low,
    d.close,
    d.pre_close,
    d.change,
    d.pct_chg,
    d.volume_lot,
    d.amount_k_cny,
    d.volume_lot * 100.0 AS volume_share,
    d.amount_k_cny * 1000.0 AS amount_cny,
    a.adj_factor,
    d.open * a.adj_factor AS open_hfq,
    d.high * a.adj_factor AS high_hfq,
    d.low * a.adj_factor AS low_hfq,
    d.close * a.adj_factor AS close_hfq,
    l.up_limit,
    l.down_limit,
    e.suspend_timing,
    e.suspend_type,
    d.close IS NULL OR IFNULL(d.volume_lot, 0) = 0 AS is_suspended,
    e.sec_code IS NOT NULL AND d.close IS NOT NULL AND IFNULL(d.volume_lot, 0) > 0 AS has_intraday_halt,
    (COALESCE(e.has_open_halt_event, FALSE) OR COALESCE(e.has_unknown_halt_timing, FALSE))
      AND d.close IS NOT NULL
      AND IFNULL(d.volume_lot, 0) > 0 AS has_open_halt,
    l.sec_code IS NOT NULL AS has_limit_data,
    e.sec_code IS NOT NULL AS has_suspend_event_data,
    d.source_partition_date,
    d.ingested_at,
    p.prev_close_hfq
  FROM universe AS u
  LEFT JOIN daily AS d
    ON u.trade_date = d.trade_date
   AND u.sec_code = d.sec_code
  LEFT JOIN adj_factor AS a
    ON u.trade_date = a.trade_date
   AND u.sec_code = a.sec_code
  LEFT JOIN limit_price AS l
    ON u.trade_date = l.trade_date
   AND u.sec_code = l.sec_code
  LEFT JOIN suspend_event AS e
    ON u.trade_date = e.trade_date
   AND u.sec_code = e.sec_code
  LEFT JOIN prev_close AS p
    ON u.sec_code = p.sec_code
),
flagged AS (
  SELECT
    *,
    IF(close IS NULL OR up_limit IS NULL, NULL, close >= up_limit) AS is_limit_up,
    IF(close IS NULL OR down_limit IS NULL, NULL, close <= down_limit) AS is_limit_down,
    IF(open IS NULL OR high IS NULL OR low IS NULL OR up_limit IS NULL, NULL, open >= up_limit AND high >= up_limit AND low >= up_limit) AS is_one_word_limit_up,
    IF(open IS NULL OR high IS NULL OR low IS NULL OR down_limit IS NULL, NULL, open <= down_limit AND high <= down_limit AND low <= down_limit) AS is_one_word_limit_down,
    IF(is_suspended OR has_open_halt, FALSE, IF(open IS NULL OR up_limit IS NULL, NULL, open < up_limit)) AS can_buy_open,
    IF(is_suspended OR has_open_halt, FALSE, IF(open IS NULL OR down_limit IS NULL, NULL, open > down_limit)) AS can_sell_open
  FROM joined
),
calc AS (
  SELECT
    *,
    SAFE_DIVIDE(
      close_hfq,
      COALESCE(
        LAST_VALUE(close_hfq IGNORE NULLS) OVER (
          PARTITION BY sec_code
          ORDER BY trade_date
          ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ),
        prev_close_hfq
      )
    ) - 1.0 AS ret_1d
  FROM flagged
)
SELECT
  trade_date,
  sec_code,
  open,
  high,
  low,
  close,
  pre_close,
  change,
  pct_chg,
  volume_lot,
  amount_k_cny,
  volume_share,
  amount_cny,
  adj_factor,
  open_hfq,
  high_hfq,
  low_hfq,
  close_hfq,
  ret_1d,
  up_limit,
  down_limit,
  is_limit_up,
  is_limit_down,
  is_one_word_limit_up,
  is_one_word_limit_down,
  is_suspended,
  suspend_timing,
  suspend_type,
  has_intraday_halt,
  has_open_halt,
  can_buy_open,
  can_sell_open,
  IF(is_suspended OR has_open_halt, FALSE, IF(is_one_word_limit_up IS NULL OR is_one_word_limit_down IS NULL, NULL, NOT is_one_word_limit_up AND NOT is_one_word_limit_down)) AS is_tradable,
  has_limit_data,
  has_suspend_event_data,
  'tushare' AS source_system,
  source_partition_date,
  ingested_at
FROM calc;

-- ────────────────────────────────────────────────────────────────────────────
-- DWD: dwd_stock_eod_valuation
-- ────────────────────────────────────────────────────────────────────────────

DELETE FROM `data-aquarium.ashare_dwd.dwd_stock_eod_valuation`
WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date;

INSERT INTO `data-aquarium.ashare_dwd.dwd_stock_eod_valuation` (
  trade_date,
  sec_code,
  close,
  turnover_rate,
  turnover_rate_free_float,
  volume_ratio,
  pe,
  pe_ttm,
  pb,
  ps,
  ps_ttm,
  dividend_yield,
  dividend_yield_ttm,
  total_share_10k,
  float_share_10k,
  free_share_10k,
  total_share,
  float_share,
  free_share,
  total_mv_10k_cny,
  circ_mv_10k_cny,
  total_mv_cny,
  circ_mv_cny,
  source_system,
  source_partition_date,
  ingested_at
)
SELECT
  SAFE.PARSE_DATE('%Y%m%d', trade_date) AS trade_date,
  ts_code AS sec_code,
  SAFE_CAST(close AS FLOAT64) AS close,
  SAFE_CAST(turnover_rate AS FLOAT64) AS turnover_rate,
  SAFE_CAST(turnover_rate_f AS FLOAT64) AS turnover_rate_free_float,
  SAFE_CAST(volume_ratio AS FLOAT64) AS volume_ratio,
  SAFE_CAST(pe AS FLOAT64) AS pe,
  SAFE_CAST(pe_ttm AS FLOAT64) AS pe_ttm,
  SAFE_CAST(pb AS FLOAT64) AS pb,
  SAFE_CAST(ps AS FLOAT64) AS ps,
  SAFE_CAST(ps_ttm AS FLOAT64) AS ps_ttm,
  SAFE_CAST(dv_ratio AS FLOAT64) AS dividend_yield,
  SAFE_CAST(dv_ttm AS FLOAT64) AS dividend_yield_ttm,
  SAFE_CAST(total_share AS FLOAT64) AS total_share_10k,
  SAFE_CAST(float_share AS FLOAT64) AS float_share_10k,
  SAFE_CAST(free_share AS FLOAT64) AS free_share_10k,
  SAFE_CAST(total_share AS FLOAT64) * 10000.0 AS total_share,
  SAFE_CAST(float_share AS FLOAT64) * 10000.0 AS float_share,
  SAFE_CAST(free_share AS FLOAT64) * 10000.0 AS free_share,
  SAFE_CAST(total_mv AS FLOAT64) AS total_mv_10k_cny,
  SAFE_CAST(circ_mv AS FLOAT64) AS circ_mv_10k_cny,
  SAFE_CAST(total_mv AS FLOAT64) * 10000.0 AS total_mv_cny,
  SAFE_CAST(circ_mv AS FLOAT64) * 10000.0 AS circ_mv_cny,
  COALESCE(_source, 'tushare') AS source_system,
  partition_date AS source_partition_date,
  SAFE_CAST(_ingested_at AS TIMESTAMP) AS ingested_at
FROM `data-aquarium.ashare_ods.ods_tushare_daily_basic`
WHERE endpoint = 'daily_basic'
  AND partition_date BETWEEN FORMAT_DATE('%Y%m%d', p_dwd_write_start_date) AND FORMAT_DATE('%Y%m%d', p_write_end_date)
  AND SAFE.PARSE_DATE('%Y%m%d', trade_date) BETWEEN p_dwd_write_start_date AND p_write_end_date;

SET p_valuation_feature_read_start_date = COALESCE((
  WITH first_write AS (
    SELECT
      sec_code,
      MIN(trade_date) AS first_write_trade_date
    FROM `data-aquarium.ashare_dwd.dwd_stock_eod_valuation`
    WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date
    GROUP BY sec_code
  ),
  ranked AS (
    SELECT
      v.sec_code,
      v.trade_date,
      ROW_NUMBER() OVER (
        PARTITION BY v.sec_code
        ORDER BY v.trade_date DESC
      ) AS obs_rank_desc
    FROM `data-aquarium.ashare_dwd.dwd_stock_eod_valuation` AS v
    JOIN first_write AS f
      ON v.sec_code = f.sec_code
     AND v.trade_date <= f.first_write_trade_date
    WHERE v.trade_date BETWEEN p_final_start_date AND p_write_end_date
  ),
  read_bounds AS (
    SELECT
      sec_code,
      MIN(trade_date) AS read_start_date
    FROM ranked
    WHERE obs_rank_desc <= p_valuation_observation_window
    GROUP BY sec_code
  )
  SELECT MIN(read_start_date)
  FROM read_bounds
), p_dwd_write_start_date);

-- ────────────────────────────────────────────────────────────────────────────
-- DWS: dws_stock_universe_daily
-- ────────────────────────────────────────────────────────────────────────────

DELETE FROM `data-aquarium.ashare_dws.dws_stock_universe_daily`
WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date;

INSERT INTO `data-aquarium.ashare_dws.dws_stock_universe_daily` (
  trade_date,
  sec_code,
  exchange,
  market,
  board,
  list_date,
  delist_date,
  first_trade_date,
  last_trade_date,
  is_delisted,
  is_listed,
  list_age_td,
  close,
  amount_cny,
  amount_ma20_cny,
  amount_obs_20d,
  is_suspended,
  is_one_word_limit_up,
  is_one_word_limit_down,
  is_one_word_limit,
  can_buy_open,
  can_sell_open,
  is_tradable_hard,
  is_st,
  is_star_st,
  pass_board,
  pass_list_age,
  pass_liquidity,
  pass_price,
  in_universe_default,
  universe_version,
  created_at
)
WITH price_base AS (
  SELECT
    trade_date,
    sec_code,
    close,
    amount_cny,
    is_suspended,
    is_one_word_limit_up,
    is_one_word_limit_down,
    can_buy_open,
    can_sell_open,
    is_tradable
  FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price`
  WHERE trade_date BETWEEN p_feature_read_start_date AND p_write_end_date
),
price_roll AS (
  SELECT
    *,
    AVG(amount_cny) OVER (
      PARTITION BY sec_code
      ORDER BY trade_date
      ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS amount_ma20_cny,
    COUNT(amount_cny) OVER (
      PARTITION BY sec_code
      ORDER BY trade_date
      ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS amount_obs_20d
  FROM price_base
),
first_list_trade AS (
  SELECT
    s.sec_code,
    MIN(c.cal_date) AS first_list_trade_date,
    MIN(c.trade_date_seq) AS first_list_trade_seq
  FROM `data-aquarium.ashare_dim.dim_stock` AS s
  JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS c
    ON c.exchange = 'SSE'
   AND c.is_open = 1
   AND c.cal_date >= COALESCE(s.list_date, DATE '1900-01-01')
   AND (s.delist_date IS NULL OR c.cal_date < s.delist_date)
  GROUP BY s.sec_code
),
st_daily AS (
  SELECT
    p.trade_date,
    p.sec_code,
    LOGICAL_OR(COALESCE(n.is_st, FALSE)) AS is_st,
    LOGICAL_OR(COALESCE(n.is_star_st, FALSE)) AS is_star_st
  FROM price_roll AS p
  LEFT JOIN `data-aquarium.ashare_dim.dim_stock_name_hist` AS n
    ON p.sec_code = n.sec_code
   AND p.trade_date >= n.valid_from
   AND p.trade_date < n.valid_to
  GROUP BY p.trade_date, p.sec_code
),
joined AS (
  SELECT
    p.trade_date,
    p.sec_code,
    s.exchange,
    s.market,
    s.board,
    s.list_date,
    s.delist_date,
    s.first_trade_date,
    s.last_trade_date,
    s.is_delisted,
    c.trade_date_seq,
    f.first_list_trade_seq,
    p.close,
    p.amount_cny,
    p.amount_ma20_cny,
    p.amount_obs_20d,
    p.is_suspended,
    p.is_one_word_limit_up,
    p.is_one_word_limit_down,
    COALESCE(p.is_one_word_limit_up, FALSE) OR COALESCE(p.is_one_word_limit_down, FALSE) AS is_one_word_limit,
    p.can_buy_open,
    p.can_sell_open,
    p.is_tradable,
    COALESCE(st.is_st, FALSE) AS is_st,
    COALESCE(st.is_star_st, FALSE) AS is_star_st
  FROM price_roll AS p
  JOIN `data-aquarium.ashare_dim.dim_stock` AS s
    ON p.sec_code = s.sec_code
  JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS c
    ON c.exchange = 'SSE'
   AND c.is_open = 1
   AND p.trade_date = c.cal_date
  LEFT JOIN first_list_trade AS f
    ON p.sec_code = f.sec_code
  LEFT JOIN st_daily AS st
    ON p.trade_date = st.trade_date
   AND p.sec_code = st.sec_code
)
SELECT
  trade_date,
  sec_code,
  exchange,
  market,
  board,
  list_date,
  delist_date,
  first_trade_date,
  last_trade_date,
  is_delisted,
  trade_date >= COALESCE(list_date, DATE '1900-01-01')
    AND (delist_date IS NULL OR trade_date < delist_date) AS is_listed,
  SAFE_CAST(trade_date_seq - first_list_trade_seq + 1 AS INT64) AS list_age_td,
  close,
  amount_cny,
  amount_ma20_cny,
  amount_obs_20d,
  is_suspended,
  is_one_word_limit_up,
  is_one_word_limit_down,
  is_one_word_limit,
  can_buy_open,
  can_sell_open,
  COALESCE(is_tradable, FALSE)
    AND trade_date >= COALESCE(list_date, DATE '1900-01-01')
    AND (delist_date IS NULL OR trade_date < delist_date) AS is_tradable_hard,
  is_st,
  is_star_st,
  board IN UNNEST(p_board_allowlist) AS pass_board,
  SAFE_CAST(trade_date_seq - first_list_trade_seq + 1 AS INT64) >= p_min_list_age_td AS pass_list_age,
  amount_obs_20d >= 20 AND amount_ma20_cny >= p_min_amount_ma20_cny AS pass_liquidity,
  close >= p_min_close_price AS pass_price,
  COALESCE(is_tradable, FALSE)
    AND trade_date >= COALESCE(list_date, DATE '1900-01-01')
    AND (delist_date IS NULL OR trade_date < delist_date)
    AND NOT is_st
    AND board IN UNNEST(p_board_allowlist)
    AND SAFE_CAST(trade_date_seq - first_list_trade_seq + 1 AS INT64) >= p_min_list_age_td
    AND amount_obs_20d >= 20
    AND amount_ma20_cny >= p_min_amount_ma20_cny
    AND close >= p_min_close_price AS in_universe_default,
  p_universe_version AS universe_version,
  CURRENT_TIMESTAMP() AS created_at
FROM joined
WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date;

-- ────────────────────────────────────────────────────────────────────────────
-- DWS: dws_stock_feature_price_daily
-- ────────────────────────────────────────────────────────────────────────────

DELETE FROM `data-aquarium.ashare_dws.dws_stock_feature_price_daily`
WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date
  AND feature_version = p_feature_version;

INSERT INTO `data-aquarium.ashare_dws.dws_stock_feature_price_daily` (
  trade_date,
  sec_code,
  feature_version,
  ret_1d,
  ret_3d,
  ret_5d,
  ret_10d,
  ret_20d,
  ret_60d,
  mom_20_5,
  mom_60_20,
  vol_5d,
  vol_20d,
  vol_60d,
  drawdown_20d,
  close_to_low_20d,
  amplitude_1d,
  gap_open_1d,
  intraday_ret_1d,
  hl_range_20d,
  amount_cny,
  amount_ma5_cny,
  amount_ma20_cny,
  amount_zscore_20d,
  volume_share,
  suspend_days_20d,
  limit_up_days_20d,
  limit_down_days_20d,
  one_word_limit_days_20d,
  tradable_days_20d,
  history_obs_60d,
  has_full_history_60d,
  created_at
)
WITH base AS (
  SELECT
    trade_date,
    sec_code,
    open_hfq,
    high_hfq,
    low_hfq,
    close_hfq,
    ret_1d,
    volume_share,
    amount_cny,
    is_suspended,
    is_limit_up,
    is_limit_down,
    is_one_word_limit_up,
    is_one_word_limit_down,
    is_tradable
  FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price`
  WHERE trade_date BETWEEN p_feature_read_start_date AND p_write_end_date
),
windowed AS (
  SELECT
    *,
    LAG(close_hfq, 1) OVER w AS close_hfq_lag_1d,
    LAG(close_hfq, 3) OVER w AS close_hfq_lag_3d,
    LAG(close_hfq, 5) OVER w AS close_hfq_lag_5d,
    LAG(close_hfq, 10) OVER w AS close_hfq_lag_10d,
    LAG(close_hfq, 20) OVER w AS close_hfq_lag_20d,
    LAG(close_hfq, 60) OVER w AS close_hfq_lag_60d,
    AVG(amount_cny) OVER w5 AS amount_ma5_cny,
    AVG(amount_cny) OVER w20 AS amount_ma20_cny,
    STDDEV_SAMP(amount_cny) OVER w20 AS amount_std20_cny,
    STDDEV_SAMP(ret_1d) OVER w5 AS vol_5d,
    STDDEV_SAMP(ret_1d) OVER w20 AS vol_20d,
    STDDEV_SAMP(ret_1d) OVER w60 AS vol_60d,
    MAX(close_hfq) OVER w20 AS close_hfq_max_20d,
    MIN(close_hfq) OVER w20 AS close_hfq_min_20d,
    AVG(SAFE_DIVIDE(high_hfq - low_hfq, close_hfq)) OVER w20 AS hl_range_20d,
    COUNT(close_hfq) OVER w60_plus AS history_obs_60d,
    SUM(CAST(COALESCE(is_suspended, FALSE) AS INT64)) OVER w20 AS suspend_days_20d,
    SUM(CAST(COALESCE(is_limit_up, FALSE) AS INT64)) OVER w20 AS limit_up_days_20d,
    SUM(CAST(COALESCE(is_limit_down, FALSE) AS INT64)) OVER w20 AS limit_down_days_20d,
    SUM(CAST(COALESCE(is_one_word_limit_up, FALSE) OR COALESCE(is_one_word_limit_down, FALSE) AS INT64)) OVER w20 AS one_word_limit_days_20d,
    SUM(CAST(COALESCE(is_tradable, FALSE) AS INT64)) OVER w20 AS tradable_days_20d
  FROM base
  WINDOW
    w AS (PARTITION BY sec_code ORDER BY trade_date),
    w5 AS (PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW),
    w20 AS (PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),
    w60 AS (PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW),
    w60_plus AS (PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN 60 PRECEDING AND CURRENT ROW)
)
SELECT
  trade_date,
  sec_code,
  p_feature_version AS feature_version,
  ret_1d,
  SAFE_DIVIDE(close_hfq, close_hfq_lag_3d) - 1.0 AS ret_3d,
  SAFE_DIVIDE(close_hfq, close_hfq_lag_5d) - 1.0 AS ret_5d,
  SAFE_DIVIDE(close_hfq, close_hfq_lag_10d) - 1.0 AS ret_10d,
  SAFE_DIVIDE(close_hfq, close_hfq_lag_20d) - 1.0 AS ret_20d,
  SAFE_DIVIDE(close_hfq, close_hfq_lag_60d) - 1.0 AS ret_60d,
  SAFE_DIVIDE(close_hfq_lag_5d, close_hfq_lag_20d) - 1.0 AS mom_20_5,
  SAFE_DIVIDE(close_hfq_lag_20d, close_hfq_lag_60d) - 1.0 AS mom_60_20,
  vol_5d,
  vol_20d,
  vol_60d,
  SAFE_DIVIDE(close_hfq, close_hfq_max_20d) - 1.0 AS drawdown_20d,
  SAFE_DIVIDE(close_hfq, close_hfq_min_20d) - 1.0 AS close_to_low_20d,
  SAFE_DIVIDE(high_hfq - low_hfq, close_hfq) AS amplitude_1d,
  SAFE_DIVIDE(open_hfq, close_hfq_lag_1d) - 1.0 AS gap_open_1d,
  SAFE_DIVIDE(close_hfq, open_hfq) - 1.0 AS intraday_ret_1d,
  hl_range_20d,
  amount_cny,
  amount_ma5_cny,
  amount_ma20_cny,
  SAFE_DIVIDE(amount_cny - amount_ma20_cny, NULLIF(amount_std20_cny, 0.0)) AS amount_zscore_20d,
  volume_share,
  suspend_days_20d,
  limit_up_days_20d,
  limit_down_days_20d,
  one_word_limit_days_20d,
  tradable_days_20d,
  history_obs_60d,
  history_obs_60d >= 61 AND close_hfq_lag_60d IS NOT NULL AS has_full_history_60d,
  CURRENT_TIMESTAMP() AS created_at
FROM windowed
WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date;

-- ────────────────────────────────────────────────────────────────────────────
-- DWS: dws_stock_feature_valuation_daily
-- ────────────────────────────────────────────────────────────────────────────

DELETE FROM `data-aquarium.ashare_dws.dws_stock_feature_valuation_daily`
WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date
  AND feature_version = p_feature_version;

INSERT INTO `data-aquarium.ashare_dws.dws_stock_feature_valuation_daily` (
  trade_date,
  sec_code,
  feature_version,
  turnover_rate,
  turnover_rate_free_float,
  turnover_rate_ma5,
  turnover_rate_ma20,
  turnover_rate_free_float_ma20,
  volume_ratio,
  volume_ratio_ma20,
  turnover_rate_zscore_60d,
  pe,
  pe_ttm,
  pb,
  ps,
  ps_ttm,
  dividend_yield,
  dividend_yield_ttm,
  is_pe_ttm_positive,
  is_pb_positive,
  is_ps_ttm_positive,
  ep_ttm,
  bp,
  sp_ttm,
  total_share,
  float_share,
  free_share,
  total_mv_cny,
  circ_mv_cny,
  log_total_mv,
  log_circ_mv,
  has_valuation_data,
  created_at
)
WITH base AS (
  WITH first_write AS (
    SELECT
      sec_code,
      MIN(trade_date) AS first_write_trade_date
    FROM `data-aquarium.ashare_dwd.dwd_stock_eod_valuation`
    WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date
    GROUP BY sec_code
  ),
  ranked AS (
    SELECT
      v.sec_code,
      v.trade_date,
      ROW_NUMBER() OVER (
        PARTITION BY v.sec_code
        ORDER BY v.trade_date DESC
      ) AS obs_rank_desc
    FROM `data-aquarium.ashare_dwd.dwd_stock_eod_valuation` AS v
    JOIN first_write AS f
      ON v.sec_code = f.sec_code
     AND v.trade_date <= f.first_write_trade_date
    WHERE v.trade_date BETWEEN p_valuation_feature_read_start_date AND p_write_end_date
  ),
  read_bounds AS (
    SELECT
      sec_code,
      MIN(trade_date) AS read_start_date
    FROM ranked
    WHERE obs_rank_desc <= p_valuation_observation_window
    GROUP BY sec_code
  )
  SELECT
    v.trade_date,
    v.sec_code,
    v.turnover_rate,
    v.turnover_rate_free_float,
    v.volume_ratio,
    v.pe,
    v.pe_ttm,
    v.pb,
    v.ps,
    v.ps_ttm,
    v.dividend_yield,
    v.dividend_yield_ttm,
    v.total_share,
    v.float_share,
    v.free_share,
    v.total_mv_cny,
    v.circ_mv_cny
  FROM `data-aquarium.ashare_dwd.dwd_stock_eod_valuation` AS v
  JOIN read_bounds AS b
    ON v.sec_code = b.sec_code
   AND v.trade_date >= b.read_start_date
  WHERE v.trade_date BETWEEN p_valuation_feature_read_start_date AND p_write_end_date
),
windowed AS (
  SELECT
    *,
    AVG(turnover_rate) OVER w5 AS turnover_rate_ma5,
    AVG(turnover_rate) OVER w20 AS turnover_rate_ma20,
    AVG(turnover_rate_free_float) OVER w20 AS turnover_rate_free_float_ma20,
    AVG(volume_ratio) OVER w20 AS volume_ratio_ma20,
    STDDEV_SAMP(turnover_rate) OVER w60 AS turnover_rate_std60,
    AVG(turnover_rate) OVER w60 AS turnover_rate_ma60
  FROM base
  WINDOW
    w5 AS (PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW),
    w20 AS (PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),
    w60 AS (PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW)
)
SELECT
  trade_date,
  sec_code,
  p_feature_version AS feature_version,
  turnover_rate,
  turnover_rate_free_float,
  turnover_rate_ma5,
  turnover_rate_ma20,
  turnover_rate_free_float_ma20,
  volume_ratio,
  volume_ratio_ma20,
  SAFE_DIVIDE(turnover_rate - turnover_rate_ma60, NULLIF(turnover_rate_std60, 0.0)) AS turnover_rate_zscore_60d,
  pe,
  pe_ttm,
  pb,
  ps,
  ps_ttm,
  dividend_yield,
  dividend_yield_ttm,
  pe_ttm > 0 AS is_pe_ttm_positive,
  pb > 0 AS is_pb_positive,
  ps_ttm > 0 AS is_ps_ttm_positive,
  IF(pe_ttm > 0, SAFE_DIVIDE(1.0, pe_ttm), NULL) AS ep_ttm,
  IF(pb > 0, SAFE_DIVIDE(1.0, pb), NULL) AS bp,
  IF(ps_ttm > 0, SAFE_DIVIDE(1.0, ps_ttm), NULL) AS sp_ttm,
  total_share,
  float_share,
  free_share,
  total_mv_cny,
  circ_mv_cny,
  IF(total_mv_cny > 0, LN(total_mv_cny), NULL) AS log_total_mv,
  IF(circ_mv_cny > 0, LN(circ_mv_cny), NULL) AS log_circ_mv,
  total_mv_cny IS NOT NULL AND circ_mv_cny IS NOT NULL AS has_valuation_data,
  CURRENT_TIMESTAMP() AS created_at
FROM windowed
WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date;

-- ────────────────────────────────────────────────────────────────────────────
-- DWS: dws_stock_feature_fin_daily
-- ────────────────────────────────────────────────────────────────────────────

DELETE FROM `data-aquarium.ashare_dws.dws_stock_feature_fin_daily`
WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date
  AND feature_version = p_fin_feature_version;

INSERT INTO `data-aquarium.ashare_dws.dws_stock_feature_fin_daily` (
  trade_date,
  sec_code,
  feature_version,
  report_period,
  ann_date_eff,
  visible_trade_date,
  report_caliber,
  is_default_report_caliber,
  report_age_days,
  fin_report_lag_days,
  has_fin_indicator,
  has_fin_income,
  has_fin_balancesheet,
  has_fin_cashflow,
  ind_report_caliber,
  ind_report_period,
  ind_visible_trade_date,
  bs_report_period,
  bs_visible_trade_date,
  cf_report_period,
  cf_visible_trade_date,
  roe,
  roe_deducted,
  roa,
  roic,
  grossprofit_margin,
  netprofit_margin,
  debt_to_assets,
  current_ratio,
  quick_ratio,
  assets_to_equity,
  ocf_to_or,
  ocf_to_profit,
  cash_ratio,
  netprofit_yoy,
  operating_revenue_yoy,
  total_revenue_yoy,
  basic_eps_yoy,
  q_roe,
  q_netprofit_margin,
  q_grossprofit_margin,
  total_revenue,
  revenue,
  operate_profit,
  total_profit,
  n_income,
  n_income_attr_p,
  ebit,
  ebitda,
  basic_eps,
  total_assets,
  total_cur_assets,
  total_cur_liab,
  total_liab,
  total_hldr_eqy_exc_min_int,
  total_hldr_eqy_inc_min_int,
  minority_int,
  money_cap,
  inventories,
  accounts_receiv,
  goodwill,
  n_cashflow_act,
  n_cashflow_inv_act,
  n_cash_flows_fnc_act,
  free_cashflow,
  cf_net_profit,
  created_at
)
WITH u AS (
  SELECT sec_code, trade_date
  FROM `data-aquarium.ashare_dws.dws_stock_universe_daily`
  WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date
),
ind_src AS (
  SELECT
    sec_code, report_period, ann_date_eff, visible_trade_date, update_flag, ingested_at, source_partition_date,
    roe, roe_deducted, roa, roic, grossprofit_margin, netprofit_margin,
    debt_to_assets, current_ratio, quick_ratio, assets_to_equity,
    ocf_to_or, ocf_to_profit, cash_ratio,
    netprofit_yoy, operating_revenue_yoy, total_revenue_yoy, basic_eps_yoy,
    q_roe, q_netprofit_margin, q_grossprofit_margin
  FROM `data-aquarium.ashare_dwd.dwd_fin_indicator`
),
inc_src AS (
  SELECT
    sec_code, report_period, ann_date_eff, visible_trade_date, update_flag, ingested_at, source_partition_date,
    total_revenue, revenue, operate_profit, total_profit, n_income, n_income_attr_p, ebit, ebitda, basic_eps
  FROM `data-aquarium.ashare_dwd.dwd_fin_income`
  WHERE is_default_report_caliber = TRUE
),
bs_src AS (
  SELECT
    sec_code, report_period, ann_date_eff, visible_trade_date, update_flag, ingested_at, source_partition_date,
    total_assets, total_cur_assets, total_cur_liab, total_liab,
    total_hldr_eqy_exc_min_int, total_hldr_eqy_inc_min_int, minority_int,
    money_cap, inventories, accounts_receiv, goodwill
  FROM `data-aquarium.ashare_dwd.dwd_fin_balancesheet`
  WHERE is_default_report_caliber = TRUE
),
cf_src AS (
  SELECT
    sec_code, report_period, ann_date_eff, visible_trade_date, update_flag, ingested_at, source_partition_date,
    n_cashflow_act, n_cashflow_inv_act, n_cash_flows_fnc_act, free_cashflow, net_profit AS cf_net_profit
  FROM `data-aquarium.ashare_dwd.dwd_fin_cashflow`
  WHERE is_default_report_caliber = TRUE
),
ind_asof AS (
  SELECT u.sec_code, u.trade_date,
    s.report_period AS ind_report_period,
    s.ann_date_eff AS ind_ann_date_eff,
    s.visible_trade_date AS ind_visible_trade_date,
    s.roe, s.roe_deducted, s.roa, s.roic, s.grossprofit_margin, s.netprofit_margin,
    s.debt_to_assets, s.current_ratio, s.quick_ratio, s.assets_to_equity,
    s.ocf_to_or, s.ocf_to_profit, s.cash_ratio,
    s.netprofit_yoy, s.operating_revenue_yoy, s.total_revenue_yoy, s.basic_eps_yoy,
    s.q_roe, s.q_netprofit_margin, s.q_grossprofit_margin
  FROM u
  JOIN ind_src AS s
    ON s.sec_code = u.sec_code
   AND s.visible_trade_date <= u.trade_date
   AND s.visible_trade_date >= DATE_SUB(u.trade_date, INTERVAL p_asof_lookback_days DAY)
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY u.sec_code, u.trade_date
    ORDER BY s.report_period DESC, s.ann_date_eff DESC, s.update_flag DESC, s.ingested_at DESC, s.source_partition_date DESC
  ) = 1
),
inc_asof AS (
  SELECT u.sec_code, u.trade_date,
    s.report_period AS inc_report_period,
    s.ann_date_eff AS inc_ann_date_eff,
    s.visible_trade_date AS inc_visible_trade_date,
    s.total_revenue, s.revenue, s.operate_profit, s.total_profit,
    s.n_income, s.n_income_attr_p, s.ebit, s.ebitda, s.basic_eps
  FROM u
  JOIN inc_src AS s
    ON s.sec_code = u.sec_code
   AND s.visible_trade_date <= u.trade_date
   AND s.visible_trade_date >= DATE_SUB(u.trade_date, INTERVAL p_asof_lookback_days DAY)
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY u.sec_code, u.trade_date
    ORDER BY s.report_period DESC, s.ann_date_eff DESC, s.update_flag DESC, s.ingested_at DESC, s.source_partition_date DESC
  ) = 1
),
bs_asof AS (
  SELECT u.sec_code, u.trade_date,
    s.report_period AS bs_report_period,
    s.ann_date_eff AS bs_ann_date_eff,
    s.visible_trade_date AS bs_visible_trade_date,
    s.total_assets, s.total_cur_assets, s.total_cur_liab, s.total_liab,
    s.total_hldr_eqy_exc_min_int, s.total_hldr_eqy_inc_min_int, s.minority_int,
    s.money_cap, s.inventories, s.accounts_receiv, s.goodwill
  FROM u
  JOIN bs_src AS s
    ON s.sec_code = u.sec_code
   AND s.visible_trade_date <= u.trade_date
   AND s.visible_trade_date >= DATE_SUB(u.trade_date, INTERVAL p_asof_lookback_days DAY)
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY u.sec_code, u.trade_date
    ORDER BY s.report_period DESC, s.ann_date_eff DESC, s.update_flag DESC, s.ingested_at DESC, s.source_partition_date DESC
  ) = 1
),
cf_asof AS (
  SELECT u.sec_code, u.trade_date,
    s.report_period AS cf_report_period,
    s.ann_date_eff AS cf_ann_date_eff,
    s.visible_trade_date AS cf_visible_trade_date,
    s.n_cashflow_act, s.n_cashflow_inv_act, s.n_cash_flows_fnc_act, s.free_cashflow, s.cf_net_profit
  FROM u
  JOIN cf_src AS s
    ON s.sec_code = u.sec_code
   AND s.visible_trade_date <= u.trade_date
   AND s.visible_trade_date >= DATE_SUB(u.trade_date, INTERVAL p_asof_lookback_days DAY)
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY u.sec_code, u.trade_date
    ORDER BY s.report_period DESC, s.ann_date_eff DESC, s.update_flag DESC, s.ingested_at DESC, s.source_partition_date DESC
  ) = 1
)
SELECT
  u.trade_date,
  u.sec_code,
  p_fin_feature_version AS feature_version,
  inc.inc_report_period AS report_period,
  inc.inc_ann_date_eff AS ann_date_eff,
  inc.inc_visible_trade_date AS visible_trade_date,
  'consolidated' AS report_caliber,
  TRUE AS is_default_report_caliber,
  DATE_DIFF(u.trade_date, inc.inc_report_period, DAY) AS report_age_days,
  DATE_DIFF(inc.inc_visible_trade_date, inc.inc_report_period, DAY) AS fin_report_lag_days,
  ind.ind_report_period IS NOT NULL AS has_fin_indicator,
  inc.inc_report_period IS NOT NULL AS has_fin_income,
  bs.bs_report_period IS NOT NULL AS has_fin_balancesheet,
  cf.cf_report_period IS NOT NULL AS has_fin_cashflow,
  'source_default' AS ind_report_caliber,
  ind.ind_report_period,
  ind.ind_visible_trade_date,
  bs.bs_report_period,
  bs.bs_visible_trade_date,
  cf.cf_report_period,
  cf.cf_visible_trade_date,
  ind.roe, ind.roe_deducted, ind.roa, ind.roic,
  ind.grossprofit_margin, ind.netprofit_margin,
  ind.debt_to_assets, ind.current_ratio, ind.quick_ratio, ind.assets_to_equity,
  ind.ocf_to_or, ind.ocf_to_profit, ind.cash_ratio,
  ind.netprofit_yoy, ind.operating_revenue_yoy, ind.total_revenue_yoy, ind.basic_eps_yoy,
  ind.q_roe, ind.q_netprofit_margin, ind.q_grossprofit_margin,
  inc.total_revenue, inc.revenue, inc.operate_profit, inc.total_profit,
  inc.n_income, inc.n_income_attr_p, inc.ebit, inc.ebitda, inc.basic_eps,
  bs.total_assets, bs.total_cur_assets, bs.total_cur_liab, bs.total_liab,
  bs.total_hldr_eqy_exc_min_int, bs.total_hldr_eqy_inc_min_int, bs.minority_int,
  bs.money_cap, bs.inventories, bs.accounts_receiv, bs.goodwill,
  cf.n_cashflow_act, cf.n_cashflow_inv_act, cf.n_cash_flows_fnc_act, cf.free_cashflow, cf.cf_net_profit,
  CURRENT_TIMESTAMP() AS created_at
FROM u
LEFT JOIN ind_asof AS ind ON ind.sec_code = u.sec_code AND ind.trade_date = u.trade_date
LEFT JOIN inc_asof AS inc ON inc.sec_code = u.sec_code AND inc.trade_date = u.trade_date
LEFT JOIN bs_asof AS bs ON bs.sec_code = u.sec_code AND bs.trade_date = u.trade_date
LEFT JOIN cf_asof AS cf ON cf.sec_code = u.sec_code AND cf.trade_date = u.trade_date;

-- ────────────────────────────────────────────────────────────────────────────
-- DWS: dws_stock_label_daily
-- ────────────────────────────────────────────────────────────────────────────

DELETE FROM `data-aquarium.ashare_dws.dws_stock_label_daily`
WHERE trade_date BETWEEN p_label_write_start_date AND p_write_end_date
  AND label_version = p_label_version;

INSERT INTO `data-aquarium.ashare_dws.dws_stock_label_daily` (
  trade_date,
  sec_code,
  label_version,
  entry_trade_date,
  exit_trade_date_1d,
  exit_trade_date_5d,
  exit_trade_date_10d,
  exit_trade_date_20d,
  label_entry_tradable,
  exit_reachable_1d,
  exit_reachable_5d,
  exit_reachable_10d,
  exit_reachable_20d,
  fwd_ret_1d,
  fwd_ret_5d,
  fwd_ret_10d,
  fwd_ret_20d,
  fwd_xs_ret_1d,
  fwd_xs_ret_5d,
  fwd_xs_ret_10d,
  fwd_xs_ret_20d,
  rank_pct_1d,
  rank_pct_5d,
  rank_pct_10d,
  rank_pct_20d,
  label_top30_1d,
  label_top30_5d,
  label_top30_10d,
  label_top30_20d,
  label_above_median_1d,
  label_above_median_5d,
  label_above_median_10d,
  label_above_median_20d,
  label_valid_1d,
  label_valid_5d,
  label_valid_10d,
  label_valid_20d,
  created_at
)
WITH cal AS (
  SELECT
    cal_date,
    trade_date_seq
  FROM `data-aquarium.ashare_dim.dim_trade_calendar`
  WHERE exchange = 'SSE'
    AND is_open = 1
    AND cal_date BETWEEN p_label_write_start_date AND DATE_ADD(p_write_end_date, INTERVAL 45 DAY)
),
price AS (
  SELECT
    p.trade_date,
    p.sec_code,
    c.trade_date_seq,
    p.open_hfq,
    p.close_hfq,
    p.can_buy_open,
    p.can_sell_open,
    p.is_suspended,
    p.is_one_word_limit_up,
    p.is_one_word_limit_down
  FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS p
  JOIN cal AS c
    ON p.trade_date = c.cal_date
  WHERE p.trade_date BETWEEN p_label_write_start_date AND DATE_ADD(p_write_end_date, INTERVAL 45 DAY)
),
raw AS (
  SELECT
    b.trade_date,
    b.sec_code,
    p_label_version AS label_version,
    ce.cal_date AS entry_trade_date,
    ce.cal_date AS exit_trade_date_1d,
    c5.cal_date AS exit_trade_date_5d,
    c10.cal_date AS exit_trade_date_10d,
    c20.cal_date AS exit_trade_date_20d,
    entry.open_hfq AS entry_open_hfq,
    entry.can_buy_open AS entry_can_buy_open,
    entry.is_suspended AS entry_is_suspended,
    entry.is_one_word_limit_up AS entry_is_one_word_limit_up,
    x1.close_hfq AS exit_close_hfq_1d,
    x5.close_hfq AS exit_close_hfq_5d,
    x10.close_hfq AS exit_close_hfq_10d,
    x20.close_hfq AS exit_close_hfq_20d,
    NOT COALESCE(x1.is_suspended, TRUE)
      AND NOT COALESCE(x1.is_one_word_limit_down, TRUE)
      AND x1.close_hfq IS NOT NULL AS exit_reachable_1d,
    NOT COALESCE(x5.is_suspended, TRUE)
      AND NOT COALESCE(x5.is_one_word_limit_down, TRUE)
      AND x5.close_hfq IS NOT NULL AS exit_reachable_5d,
    NOT COALESCE(x10.is_suspended, TRUE)
      AND NOT COALESCE(x10.is_one_word_limit_down, TRUE)
      AND x10.close_hfq IS NOT NULL AS exit_reachable_10d,
    NOT COALESCE(x20.is_suspended, TRUE)
      AND NOT COALESCE(x20.is_one_word_limit_down, TRUE)
      AND x20.close_hfq IS NOT NULL AS exit_reachable_20d
  FROM price AS b
  LEFT JOIN cal AS ce
    ON ce.trade_date_seq = b.trade_date_seq + 1
  LEFT JOIN cal AS c5
    ON c5.trade_date_seq = b.trade_date_seq + 5
  LEFT JOIN cal AS c10
    ON c10.trade_date_seq = b.trade_date_seq + 10
  LEFT JOIN cal AS c20
    ON c20.trade_date_seq = b.trade_date_seq + 20
  LEFT JOIN price AS entry
    ON entry.sec_code = b.sec_code
   AND entry.trade_date = ce.cal_date
  LEFT JOIN price AS x1
    ON x1.sec_code = b.sec_code
   AND x1.trade_date = ce.cal_date
  LEFT JOIN price AS x5
    ON x5.sec_code = b.sec_code
   AND x5.trade_date = c5.cal_date
  LEFT JOIN price AS x10
    ON x10.sec_code = b.sec_code
   AND x10.trade_date = c10.cal_date
  LEFT JOIN price AS x20
    ON x20.sec_code = b.sec_code
   AND x20.trade_date = c20.cal_date
  WHERE b.trade_date BETWEEN p_label_write_start_date AND p_write_end_date
),
returns AS (
  SELECT
    raw.*,
    COALESCE(u.in_universe_default, FALSE) AS in_universe_default_for_rank,
    COALESCE(entry_can_buy_open, FALSE)
      AND NOT COALESCE(entry_is_suspended, TRUE)
      AND NOT COALESCE(entry_is_one_word_limit_up, TRUE)
      AND entry_open_hfq IS NOT NULL AS label_entry_tradable,
    SAFE_DIVIDE(exit_close_hfq_1d, entry_open_hfq) - 1.0 AS fwd_ret_1d,
    SAFE_DIVIDE(exit_close_hfq_5d, entry_open_hfq) - 1.0 AS fwd_ret_5d,
    SAFE_DIVIDE(exit_close_hfq_10d, entry_open_hfq) - 1.0 AS fwd_ret_10d,
    SAFE_DIVIDE(exit_close_hfq_20d, entry_open_hfq) - 1.0 AS fwd_ret_20d
  FROM raw
  LEFT JOIN `data-aquarium.ashare_dws.dws_stock_universe_daily` AS u
    ON raw.trade_date = u.trade_date
   AND raw.sec_code = u.sec_code
   AND u.trade_date BETWEEN p_label_write_start_date AND p_write_end_date
),
rank_1d AS (
  SELECT
    trade_date,
    sec_code,
    PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY fwd_ret_1d) AS rank_pct_1d
  FROM returns
  WHERE fwd_ret_1d IS NOT NULL
    AND in_universe_default_for_rank
),
rank_5d AS (
  SELECT
    trade_date,
    sec_code,
    PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY fwd_ret_5d) AS rank_pct_5d
  FROM returns
  WHERE fwd_ret_5d IS NOT NULL
    AND in_universe_default_for_rank
),
rank_10d AS (
  SELECT
    trade_date,
    sec_code,
    PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY fwd_ret_10d) AS rank_pct_10d
  FROM returns
  WHERE fwd_ret_10d IS NOT NULL
    AND in_universe_default_for_rank
),
rank_20d AS (
  SELECT
    trade_date,
    sec_code,
    PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY fwd_ret_20d) AS rank_pct_20d
  FROM returns
  WHERE fwd_ret_20d IS NOT NULL
    AND in_universe_default_for_rank
)
SELECT
  r.trade_date,
  r.sec_code,
  r.label_version,
  r.entry_trade_date,
  r.exit_trade_date_1d,
  r.exit_trade_date_5d,
  r.exit_trade_date_10d,
  r.exit_trade_date_20d,
  r.label_entry_tradable,
  r.exit_reachable_1d,
  r.exit_reachable_5d,
  r.exit_reachable_10d,
  r.exit_reachable_20d,
  r.fwd_ret_1d,
  r.fwd_ret_5d,
  r.fwd_ret_10d,
  r.fwd_ret_20d,
  r.fwd_ret_1d - AVG(IF(r.in_universe_default_for_rank, r.fwd_ret_1d, NULL)) OVER (PARTITION BY r.trade_date) AS fwd_xs_ret_1d,
  r.fwd_ret_5d - AVG(IF(r.in_universe_default_for_rank, r.fwd_ret_5d, NULL)) OVER (PARTITION BY r.trade_date) AS fwd_xs_ret_5d,
  r.fwd_ret_10d - AVG(IF(r.in_universe_default_for_rank, r.fwd_ret_10d, NULL)) OVER (PARTITION BY r.trade_date) AS fwd_xs_ret_10d,
  r.fwd_ret_20d - AVG(IF(r.in_universe_default_for_rank, r.fwd_ret_20d, NULL)) OVER (PARTITION BY r.trade_date) AS fwd_xs_ret_20d,
  q1.rank_pct_1d,
  q5.rank_pct_5d,
  q10.rank_pct_10d,
  q20.rank_pct_20d,
  IF(q1.rank_pct_1d IS NULL, NULL, CAST(q1.rank_pct_1d >= 0.7 AS INT64)) AS label_top30_1d,
  IF(q5.rank_pct_5d IS NULL, NULL, CAST(q5.rank_pct_5d >= 0.7 AS INT64)) AS label_top30_5d,
  IF(q10.rank_pct_10d IS NULL, NULL, CAST(q10.rank_pct_10d >= 0.7 AS INT64)) AS label_top30_10d,
  IF(q20.rank_pct_20d IS NULL, NULL, CAST(q20.rank_pct_20d >= 0.7 AS INT64)) AS label_top30_20d,
  IF(q1.rank_pct_1d IS NULL, NULL, CAST(q1.rank_pct_1d > 0.5 AS INT64)) AS label_above_median_1d,
  IF(q5.rank_pct_5d IS NULL, NULL, CAST(q5.rank_pct_5d > 0.5 AS INT64)) AS label_above_median_5d,
  IF(q10.rank_pct_10d IS NULL, NULL, CAST(q10.rank_pct_10d > 0.5 AS INT64)) AS label_above_median_10d,
  IF(q20.rank_pct_20d IS NULL, NULL, CAST(q20.rank_pct_20d > 0.5 AS INT64)) AS label_above_median_20d,
  r.label_entry_tradable AND r.fwd_ret_1d IS NOT NULL AS label_valid_1d,
  r.label_entry_tradable AND r.fwd_ret_5d IS NOT NULL AS label_valid_5d,
  r.label_entry_tradable AND r.fwd_ret_10d IS NOT NULL AS label_valid_10d,
  r.label_entry_tradable AND r.fwd_ret_20d IS NOT NULL AS label_valid_20d,
  CURRENT_TIMESTAMP() AS created_at
FROM returns AS r
LEFT JOIN rank_1d AS q1
  ON r.trade_date = q1.trade_date
 AND r.sec_code = q1.sec_code
LEFT JOIN rank_5d AS q5
  ON r.trade_date = q5.trade_date
 AND r.sec_code = q5.sec_code
LEFT JOIN rank_10d AS q10
  ON r.trade_date = q10.trade_date
 AND r.sec_code = q10.sec_code
LEFT JOIN rank_20d AS q20
  ON r.trade_date = q20.trade_date
 AND r.sec_code = q20.sec_code;

-- ────────────────────────────────────────────────────────────────────────────
-- DWS: dws_stock_feature_daily_v0
-- ────────────────────────────────────────────────────────────────────────────

DELETE FROM `data-aquarium.ashare_dws.dws_stock_feature_daily_v0`
WHERE trade_date BETWEEN p_label_write_start_date AND p_write_end_date
  AND feature_version = p_feature_version;

INSERT INTO `data-aquarium.ashare_dws.dws_stock_feature_daily_v0` (
  trade_date,
  sec_code,
  feature_version,
  universe_version,
  market,
  board,
  list_age_td,
  is_st,
  is_tradable_hard,
  in_universe_default,
  ret_1d,
  ret_3d,
  ret_5d,
  ret_10d,
  ret_20d,
  ret_60d,
  mom_20_5,
  mom_60_20,
  vol_5d,
  vol_20d,
  vol_60d,
  drawdown_20d,
  close_to_low_20d,
  amplitude_1d,
  gap_open_1d,
  intraday_ret_1d,
  hl_range_20d,
  amount_cny,
  amount_ma5_cny,
  amount_ma20_cny,
  amount_zscore_20d,
  suspend_days_20d,
  limit_up_days_20d,
  limit_down_days_20d,
  one_word_limit_days_20d,
  tradable_days_20d,
  history_obs_60d,
  has_full_history_60d,
  turnover_rate,
  turnover_rate_free_float,
  turnover_rate_ma5,
  turnover_rate_ma20,
  turnover_rate_free_float_ma20,
  volume_ratio,
  volume_ratio_ma20,
  turnover_rate_zscore_60d,
  pe,
  pe_ttm,
  pb,
  ps,
  ps_ttm,
  dividend_yield_ttm,
  ep_ttm,
  bp,
  sp_ttm,
  total_mv_cny,
  circ_mv_cny,
  log_total_mv,
  log_circ_mv,
  has_valuation_data,
  created_at
)
SELECT
  p.trade_date,
  p.sec_code,
  p.feature_version,
  u.universe_version,
  u.market,
  u.board,
  u.list_age_td,
  u.is_st,
  u.is_tradable_hard,
  u.in_universe_default,
  p.ret_1d,
  p.ret_3d,
  p.ret_5d,
  p.ret_10d,
  p.ret_20d,
  p.ret_60d,
  p.mom_20_5,
  p.mom_60_20,
  p.vol_5d,
  p.vol_20d,
  p.vol_60d,
  p.drawdown_20d,
  p.close_to_low_20d,
  p.amplitude_1d,
  p.gap_open_1d,
  p.intraday_ret_1d,
  p.hl_range_20d,
  p.amount_cny,
  p.amount_ma5_cny,
  p.amount_ma20_cny,
  p.amount_zscore_20d,
  p.suspend_days_20d,
  p.limit_up_days_20d,
  p.limit_down_days_20d,
  p.one_word_limit_days_20d,
  p.tradable_days_20d,
  p.history_obs_60d,
  p.has_full_history_60d,
  v.turnover_rate,
  v.turnover_rate_free_float,
  v.turnover_rate_ma5,
  v.turnover_rate_ma20,
  v.turnover_rate_free_float_ma20,
  v.volume_ratio,
  v.volume_ratio_ma20,
  v.turnover_rate_zscore_60d,
  v.pe,
  v.pe_ttm,
  v.pb,
  v.ps,
  v.ps_ttm,
  v.dividend_yield_ttm,
  v.ep_ttm,
  v.bp,
  v.sp_ttm,
  v.total_mv_cny,
  v.circ_mv_cny,
  v.log_total_mv,
  v.log_circ_mv,
  v.has_valuation_data,
  CURRENT_TIMESTAMP() AS created_at
FROM `data-aquarium.ashare_dws.dws_stock_feature_price_daily` AS p
JOIN `data-aquarium.ashare_dws.dws_stock_universe_daily` AS u
  ON p.trade_date = u.trade_date
 AND p.sec_code = u.sec_code
 AND u.trade_date BETWEEN p_label_write_start_date AND p_write_end_date
LEFT JOIN `data-aquarium.ashare_dws.dws_stock_feature_valuation_daily` AS v
  ON p.trade_date = v.trade_date
 AND p.sec_code = v.sec_code
 AND p.feature_version = v.feature_version
 AND v.trade_date BETWEEN p_label_write_start_date AND p_write_end_date
WHERE p.trade_date BETWEEN p_label_write_start_date AND p_write_end_date
  AND p.feature_version = p_feature_version;

-- ────────────────────────────────────────────────────────────────────────────
-- DWS: dws_stock_sample_daily
-- ────────────────────────────────────────────────────────────────────────────

DELETE FROM `data-aquarium.ashare_dws.dws_stock_sample_daily`
WHERE trade_date BETWEEN p_label_write_start_date AND p_write_end_date
  AND feature_version = p_feature_version
  AND label_version = p_label_version;

INSERT INTO `data-aquarium.ashare_dws.dws_stock_sample_daily` (
  trade_date,
  sec_code,
  feature_version,
  label_version,
  universe_version,
  market,
  board,
  list_age_td,
  is_st,
  is_tradable_hard,
  in_universe_default,
  has_full_history_60d,
  has_valuation_data,
  label_entry_tradable,
  label_valid_1d,
  label_valid_5d,
  label_valid_10d,
  label_valid_20d,
  fwd_ret_1d,
  fwd_ret_5d,
  fwd_ret_10d,
  fwd_ret_20d,
  fwd_xs_ret_5d,
  fwd_xs_ret_10d,
  fwd_xs_ret_20d,
  rank_pct_5d,
  rank_pct_10d,
  rank_pct_20d,
  label_top30_5d,
  label_top30_10d,
  label_top30_20d,
  label_above_median_5d,
  label_above_median_10d,
  label_above_median_20d,
  ret_1d,
  ret_3d,
  ret_5d,
  ret_10d,
  ret_20d,
  ret_60d,
  mom_20_5,
  mom_60_20,
  vol_5d,
  vol_20d,
  vol_60d,
  drawdown_20d,
  hl_range_20d,
  amount_ma20_cny,
  amount_zscore_20d,
  turnover_rate,
  turnover_rate_free_float,
  turnover_rate_ma20,
  volume_ratio,
  pe_ttm,
  pb,
  ps_ttm,
  dividend_yield_ttm,
  ep_ttm,
  bp,
  sp_ttm,
  log_total_mv,
  log_circ_mv,
  sample_trainable_default,
  split_fold,
  split_tag,
  created_at
)
SELECT
  f.trade_date,
  f.sec_code,
  f.feature_version,
  l.label_version,
  f.universe_version,
  f.market,
  f.board,
  f.list_age_td,
  f.is_st,
  f.is_tradable_hard,
  f.in_universe_default,
  f.has_full_history_60d,
  f.has_valuation_data,
  l.label_entry_tradable,
  l.label_valid_1d,
  l.label_valid_5d,
  l.label_valid_10d,
  l.label_valid_20d,
  l.fwd_ret_1d,
  l.fwd_ret_5d,
  l.fwd_ret_10d,
  l.fwd_ret_20d,
  l.fwd_xs_ret_5d,
  l.fwd_xs_ret_10d,
  l.fwd_xs_ret_20d,
  l.rank_pct_5d,
  l.rank_pct_10d,
  l.rank_pct_20d,
  l.label_top30_5d,
  l.label_top30_10d,
  l.label_top30_20d,
  l.label_above_median_5d,
  l.label_above_median_10d,
  l.label_above_median_20d,
  f.ret_1d,
  f.ret_3d,
  f.ret_5d,
  f.ret_10d,
  f.ret_20d,
  f.ret_60d,
  f.mom_20_5,
  f.mom_60_20,
  f.vol_5d,
  f.vol_20d,
  f.vol_60d,
  f.drawdown_20d,
  f.hl_range_20d,
  f.amount_ma20_cny,
  f.amount_zscore_20d,
  f.turnover_rate,
  f.turnover_rate_free_float,
  f.turnover_rate_ma20,
  f.volume_ratio,
  f.pe_ttm,
  f.pb,
  f.ps_ttm,
  f.dividend_yield_ttm,
  f.ep_ttm,
  f.bp,
  f.sp_ttm,
  f.log_total_mv,
  f.log_circ_mv,
  f.in_universe_default
    AND f.has_full_history_60d
    AND COALESCE(f.has_valuation_data, FALSE)
    AND l.label_entry_tradable
    AND l.label_valid_5d AS sample_trainable_default,
  'fold_default_2019_2026' AS split_fold,
  CASE
    WHEN f.trade_date < DATE '2024-01-01' THEN 'train'
    WHEN f.trade_date < DATE '2025-01-01' THEN 'valid'
    WHEN f.trade_date < DATE '2026-01-01' THEN 'test'
    ELSE 'live'
  END AS split_tag,
  CURRENT_TIMESTAMP() AS created_at
FROM `data-aquarium.ashare_dws.dws_stock_feature_daily_v0` AS f
JOIN `data-aquarium.ashare_dws.dws_stock_label_daily` AS l
  ON f.trade_date = l.trade_date
 AND f.sec_code = l.sec_code
 AND l.trade_date BETWEEN p_label_write_start_date AND p_write_end_date
WHERE f.trade_date BETWEEN p_label_write_start_date AND p_write_end_date
  AND f.feature_version = p_feature_version
  AND l.label_version = p_label_version;

COMMIT TRANSACTION;

CREATE TEMP TABLE refresh_window AS
SELECT
  p_business_date AS business_date,
  p_requested_date_to AS requested_date_to,
  p_date_to AS effective_date_to,
  p_warehouse_mode AS warehouse_mode,
  p_dwd_write_start_date AS dwd_write_start_date,
  p_feature_read_start_date AS feature_read_start_date,
  p_valuation_feature_read_start_date AS valuation_feature_read_start_date,
  p_valuation_observation_window AS valuation_observation_window,
  p_label_write_start_date AS label_write_start_date,
  p_write_end_date AS write_end_date;

SELECT * FROM refresh_window;
