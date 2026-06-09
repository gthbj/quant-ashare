-- 文档维护：GPT-5 Codex（最近更新 2026-06-08）
-- BigQuery Standard SQL
-- Daily warehouse pipeline: market-state DWS 窗口化刷新。
--
-- 口径：
-- - 目标表必须已由 sql/dws/08_dws_market_state_daily.sql 全量 CTAS 初始化。
-- - 本脚本只刷新 ashare_dws.dws_market_state_daily 的写入窗口，不写 ADS。
-- - daily_current 模式默认刷新最近 20 个交易日（含 date_to），并保持 2019+ 生产下限。
-- - backfill 模式使用显式 date_from/date_to；允许 owner 手工补 2019 年以前历史窗口。
-- - 为覆盖 20/60 日滚动指标，计算读取窗口从写入窗口首日向前扩 80 个 SSE 交易日。
-- - v0 兼容行保留旧 market-state 语义，sse_composite_* 字段置 NULL；v1 行填充 SSE Composite 字段。

DECLARE p_business_date DATE DEFAULT COALESCE(SAFE_CAST(NULLIF(@business_date, '') AS DATE), CURRENT_DATE('Asia/Shanghai'));
DECLARE p_date_from DATE DEFAULT SAFE_CAST(NULLIF(@date_from, '') AS DATE);
DECLARE p_requested_date_to DATE DEFAULT COALESCE(SAFE_CAST(NULLIF(@date_to, '') AS DATE), p_business_date);
DECLARE p_warehouse_mode STRING DEFAULT LOWER(COALESCE(NULLIF(@warehouse_mode, ''), 'daily_current'));
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
DECLARE p_daily_current_floor_date DATE DEFAULT DATE '2019-01-01';
DECLARE p_backfill_floor_date DATE DEFAULT DATE '1900-01-01';
DECLARE p_write_floor_date DATE DEFAULT CASE
  WHEN p_warehouse_mode = 'backfill' THEN p_backfill_floor_date
  ELSE p_daily_current_floor_date
END;
DECLARE p_feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_market_state_versions ARRAY<STRING> DEFAULT [
  'market_state_v0_20260606',
  'market_state_v1_20260607'
];
DECLARE p_daily_current_lookback_td INT64 DEFAULT 20;
DECLARE p_roll_window_lookback_td INT64 DEFAULT 80;
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
DECLARE p_write_start_date DATE DEFAULT GREATEST(
  CASE
    WHEN p_warehouse_mode = 'daily_current' AND p_date_from IS NULL
      THEN p_daily_current_start_date
    ELSE COALESCE(p_date_from, p_date_to)
  END,
  p_write_floor_date
);
DECLARE p_write_end_date DATE DEFAULT p_date_to;
DECLARE p_anchor_seq INT64 DEFAULT (
  SELECT MIN(trade_date_seq)
  FROM `data-aquarium.ashare_dim.dim_trade_calendar`
  WHERE exchange = 'SSE'
    AND is_open = 1
    AND cal_date >= p_write_start_date
    AND cal_date <= p_write_end_date
);
DECLARE p_read_start_date DATE DEFAULT GREATEST(
  COALESCE(
    (
      SELECT MAX(cal_date)
      FROM `data-aquarium.ashare_dim.dim_trade_calendar`
      WHERE exchange = 'SSE'
        AND is_open = 1
        AND trade_date_seq <= p_anchor_seq - p_roll_window_lookback_td
    ),
    DATE_SUB(p_write_start_date, INTERVAL 120 DAY)
  ),
  p_write_floor_date
);

ASSERT p_warehouse_mode IN ('daily_current', 'backfill')
  AS 'market-state window refresh requires warehouse_mode daily_current or backfill';

ASSERT p_write_end_date >= p_write_start_date
  AS 'market-state window refresh requires write_end_date >= write_start_date';

ASSERT p_anchor_seq IS NOT NULL
  AS 'market-state window refresh requires at least one SSE open date in the write window';

ASSERT (
  SELECT COUNT(*) = 1
  FROM `data-aquarium.ashare_dws.INFORMATION_SCHEMA.TABLES`
  WHERE table_name = 'dws_market_state_daily'
) AS 'market-state window refresh target dws_market_state_daily must exist; run full_rebuild before daily_current/backfill';

MERGE `data-aquarium.ashare_dws.dws_market_state_daily` AS target
USING (
  WITH calendar AS (
    SELECT cal_date AS trade_date
    FROM `data-aquarium.ashare_dim.dim_trade_calendar`
    WHERE exchange = 'SSE'
      AND is_open = 1
      AND cal_date BETWEEN p_write_start_date AND p_write_end_date
  ),
  index_base AS (
    SELECT
      idx.trade_date,
      idx.sec_code,
      idx.close,
      idx.pct_chg / 100.0 AS ret_1d
    FROM `data-aquarium.ashare_dwd.dwd_index_eod` AS idx
    WHERE idx.trade_date BETWEEN p_read_start_date AND p_write_end_date
      AND idx.sec_code IN ('000001.SH', '000300.SH', '000852.SH')
      AND idx.close IS NOT NULL
  ),
  index_windowed AS (
    SELECT
      *,
      SAFE_DIVIDE(close, LAG(close, 5) OVER w) - 1.0 AS ret_5d,
      SAFE_DIVIDE(close, LAG(close, 20) OVER w) - 1.0 AS ret_20d,
      SAFE_DIVIDE(close, MAX(close) OVER w20) - 1.0 AS drawdown_20d,
      STDDEV_SAMP(ret_1d) OVER w20 AS vol_20d,
      SAFE_DIVIDE(close, AVG(close) OVER w20) - 1.0 AS close_to_ma20,
      SAFE_DIVIDE(close, AVG(close) OVER w60) - 1.0 AS close_to_ma60,
      SAFE_DIVIDE(AVG(close) OVER w20, AVG(close) OVER w60) - 1.0 AS ma20_to_ma60
    FROM index_base
    WINDOW
      w AS (PARTITION BY sec_code ORDER BY trade_date),
      w20 AS (PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),
      w60 AS (PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW)
  ),
  index_pivot AS (
    SELECT
      trade_date,
      MAX(IF(sec_code = '000001.SH', ret_5d, NULL)) AS sse_composite_ret_5d,
      MAX(IF(sec_code = '000001.SH', ret_20d, NULL)) AS sse_composite_ret_20d,
      MAX(IF(sec_code = '000001.SH', drawdown_20d, NULL)) AS sse_composite_drawdown_20d,
      MAX(IF(sec_code = '000001.SH', vol_20d, NULL)) AS sse_composite_vol_20d,
      MAX(IF(sec_code = '000001.SH', close_to_ma20, NULL)) AS sse_composite_close_to_ma20,
      MAX(IF(sec_code = '000001.SH', close_to_ma60, NULL)) AS sse_composite_close_to_ma60,
      MAX(IF(sec_code = '000001.SH', ma20_to_ma60, NULL)) AS sse_composite_ma20_to_ma60,
      MAX(IF(sec_code = '000300.SH', ret_5d, NULL)) AS csi300_ret_5d,
      MAX(IF(sec_code = '000300.SH', ret_20d, NULL)) AS csi300_ret_20d,
      MAX(IF(sec_code = '000300.SH', drawdown_20d, NULL)) AS csi300_drawdown_20d,
      MAX(IF(sec_code = '000300.SH', vol_20d, NULL)) AS csi300_vol_20d,
      MAX(IF(sec_code = '000852.SH', ret_5d, NULL)) AS csi1000_ret_5d,
      MAX(IF(sec_code = '000852.SH', ret_20d, NULL)) AS csi1000_ret_20d,
      MAX(IF(sec_code = '000852.SH', drawdown_20d, NULL)) AS csi1000_drawdown_20d,
      MAX(IF(sec_code = '000852.SH', vol_20d, NULL)) AS csi1000_vol_20d,
      MAX(IF(sec_code = '000852.SH', close_to_ma20, NULL)) AS csi1000_close_to_ma20,
      MAX(IF(sec_code = '000852.SH', close_to_ma60, NULL)) AS csi1000_close_to_ma60,
      MAX(IF(sec_code = '000852.SH', ma20_to_ma60, NULL)) AS csi1000_ma20_to_ma60
    FROM index_windowed
    WHERE trade_date BETWEEN p_write_start_date AND p_write_end_date
    GROUP BY trade_date
  ),
  stock_base AS (
    SELECT
      feat.trade_date,
      feat.sec_code,
      px.close_hfq,
      feat.ret_1d,
      feat.ret_20d,
      feat.drawdown_20d,
      feat.vol_20d,
      feat.total_mv_cny,
      feat.circ_mv_cny,
      COALESCE(px.is_limit_down, FALSE) AS is_limit_down,
      COALESCE(px.is_one_word_limit_down, FALSE) AS is_one_word_limit_down
    FROM `data-aquarium.ashare_dws.dws_stock_feature_daily_v0` AS feat
    JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
      ON px.sec_code = feat.sec_code
     AND px.trade_date = feat.trade_date
     AND px.trade_date BETWEEN p_read_start_date AND p_write_end_date
    WHERE feat.trade_date BETWEEN p_read_start_date AND p_write_end_date
      AND feat.feature_version = p_feature_version
      AND COALESCE(feat.in_universe_default, FALSE)
  ),
  stock_windowed AS (
    SELECT
      *,
      close_hfq > AVG(close_hfq) OVER w20 AS above_ma20,
      close_hfq <= MIN(close_hfq) OVER w20 AS is_new_low_20d
    FROM stock_base
    WINDOW
      w20 AS (PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)
  ),
  stock_agg AS (
    SELECT
      trade_date,
      COUNT(*) AS stock_count,
      COUNTIF(ret_1d > 0) AS adv_count,
      COUNTIF(ret_1d < 0) AS decline_count,
      SAFE_DIVIDE(COUNTIF(ret_1d > 0), COUNTIF(ret_1d IS NOT NULL)) AS adv_ratio_1d,
      COUNTIF(above_ma20) AS above_ma20_count,
      SAFE_DIVIDE(COUNTIF(above_ma20), COUNTIF(close_hfq IS NOT NULL)) AS above_ma20_ratio,
      COUNTIF(is_new_low_20d) AS new_low_20d_count,
      SAFE_DIVIDE(COUNTIF(is_new_low_20d), COUNTIF(close_hfq IS NOT NULL)) AS new_low_20d_ratio,
      COUNTIF(is_limit_down) AS limit_down_count,
      COUNTIF(is_one_word_limit_down) AS one_word_limit_down_count,
      SUM(IF(is_limit_down, COALESCE(circ_mv_cny, total_mv_cny, 0.0), 0.0)) AS limit_down_mv_cny,
      SUM(COALESCE(circ_mv_cny, total_mv_cny, 0.0)) AS universe_mv_cny,
      SAFE_DIVIDE(
        SUM(IF(is_limit_down, COALESCE(circ_mv_cny, total_mv_cny, 0.0), 0.0)),
        NULLIF(SUM(COALESCE(circ_mv_cny, total_mv_cny, 0.0)), 0.0)
      ) AS limit_down_mv_ratio,
      AVG(ret_20d) AS avg_ret_20d,
      APPROX_QUANTILES(ret_20d, 101)[OFFSET(25)] AS ret_20d_p25,
      APPROX_QUANTILES(ret_20d, 101)[OFFSET(50)] AS ret_20d_median,
      APPROX_QUANTILES(drawdown_20d, 101)[OFFSET(50)] AS drawdown_20d_median,
      AVG(vol_20d) AS avg_vol_20d
    FROM stock_windowed
    WHERE trade_date BETWEEN p_write_start_date AND p_write_end_date
    GROUP BY trade_date
  ),
  joined AS (
    SELECT
      cal.trade_date,
      ip.sse_composite_ret_5d,
      ip.sse_composite_ret_20d,
      ip.sse_composite_drawdown_20d,
      ip.sse_composite_vol_20d,
      ip.sse_composite_close_to_ma20,
      ip.sse_composite_close_to_ma60,
      ip.sse_composite_ma20_to_ma60,
      ip.csi300_ret_5d,
      ip.csi300_ret_20d,
      ip.csi300_drawdown_20d,
      ip.csi300_vol_20d,
      ip.csi1000_ret_5d,
      ip.csi1000_ret_20d,
      ip.csi1000_drawdown_20d,
      ip.csi1000_vol_20d,
      ip.csi1000_close_to_ma20,
      ip.csi1000_close_to_ma60,
      ip.csi1000_ma20_to_ma60,
      sa.stock_count,
      sa.adv_count,
      sa.decline_count,
      sa.adv_ratio_1d,
      sa.above_ma20_count,
      sa.above_ma20_ratio,
      sa.new_low_20d_count,
      sa.new_low_20d_ratio,
      sa.limit_down_count,
      sa.one_word_limit_down_count,
      sa.limit_down_mv_cny,
      sa.universe_mv_cny,
      sa.limit_down_mv_ratio,
      sa.avg_ret_20d,
      sa.ret_20d_p25,
      sa.ret_20d_median,
      sa.drawdown_20d_median,
      sa.avg_vol_20d,
      (
        ip.csi1000_ret_20d <= -0.08
        OR ip.csi1000_drawdown_20d <= -0.12
        OR ip.csi1000_close_to_ma60 <= -0.06
      ) AS is_smallcap_trend_down,
      (
        sa.adv_ratio_1d <= 0.35
        OR sa.above_ma20_ratio <= 0.35
        OR sa.new_low_20d_ratio >= 0.20
      ) AS is_breadth_weak,
      (
        sa.limit_down_count >= 80
        OR sa.one_word_limit_down_count >= 20
        OR sa.limit_down_mv_ratio >= 0.05
      ) AS is_limit_down_diffusion
    FROM calendar AS cal
    LEFT JOIN index_pivot AS ip USING (trade_date)
    LEFT JOIN stock_agg AS sa USING (trade_date)
  ),
  classified AS (
    SELECT
      *,
      (
        IF(COALESCE(is_smallcap_trend_down, FALSE), 1, 0)
        + IF(COALESCE(is_breadth_weak, FALSE), 1, 0)
        + IF(COALESCE(is_limit_down_diffusion, FALSE), 1, 0)
      ) AS risk_off_trigger_count,
      ARRAY_TO_STRING(
        ARRAY_CONCAT(
          IF(COALESCE(is_smallcap_trend_down, FALSE), ['smallcap_trend_down'], []),
          IF(COALESCE(is_breadth_weak, FALSE), ['breadth_weak'], []),
          IF(COALESCE(is_limit_down_diffusion, FALSE), ['limit_down_diffusion'], [])
        ),
        ';'
      ) AS risk_off_reasons
    FROM joined
  )
  SELECT
    trade_date,
    market_state_version,
    IF(market_state_version = 'market_state_v1_20260607', sse_composite_ret_5d, NULL) AS sse_composite_ret_5d,
    IF(market_state_version = 'market_state_v1_20260607', sse_composite_ret_20d, NULL) AS sse_composite_ret_20d,
    IF(market_state_version = 'market_state_v1_20260607', sse_composite_drawdown_20d, NULL) AS sse_composite_drawdown_20d,
    IF(market_state_version = 'market_state_v1_20260607', sse_composite_vol_20d, NULL) AS sse_composite_vol_20d,
    IF(market_state_version = 'market_state_v1_20260607', sse_composite_close_to_ma20, NULL) AS sse_composite_close_to_ma20,
    IF(market_state_version = 'market_state_v1_20260607', sse_composite_close_to_ma60, NULL) AS sse_composite_close_to_ma60,
    IF(market_state_version = 'market_state_v1_20260607', sse_composite_ma20_to_ma60, NULL) AS sse_composite_ma20_to_ma60,
    csi300_ret_5d,
    csi300_ret_20d,
    csi300_drawdown_20d,
    csi300_vol_20d,
    csi1000_ret_5d,
    csi1000_ret_20d,
    csi1000_drawdown_20d,
    csi1000_vol_20d,
    csi1000_close_to_ma20,
    csi1000_close_to_ma60,
    csi1000_ma20_to_ma60,
    stock_count,
    adv_count,
    decline_count,
    adv_ratio_1d,
    above_ma20_count,
    above_ma20_ratio,
    new_low_20d_count,
    new_low_20d_ratio,
    limit_down_count,
    one_word_limit_down_count,
    limit_down_mv_cny,
    universe_mv_cny,
    limit_down_mv_ratio,
    avg_ret_20d,
    ret_20d_p25,
    ret_20d_median,
    drawdown_20d_median,
    avg_vol_20d,
    is_smallcap_trend_down,
    is_breadth_weak,
    is_limit_down_diffusion,
    risk_off_trigger_count,
    (
      risk_off_trigger_count >= 2
      OR COALESCE(is_limit_down_diffusion, FALSE)
    ) AS is_risk_off,
    CASE
      WHEN risk_off_trigger_count >= 2 OR COALESCE(is_limit_down_diffusion, FALSE) THEN 'risk_off'
      WHEN csi1000_ret_20d > 0.04 AND adv_ratio_1d >= 0.55 AND above_ma20_ratio >= 0.55 THEN 'risk_on'
      ELSE 'risk_neutral'
    END AS market_regime,
    risk_off_reasons,
    'skip_new_buys' AS risk_off_action,
    CURRENT_TIMESTAMP() AS created_at
  FROM classified
  CROSS JOIN UNNEST(p_market_state_versions) AS market_state_version
) AS source
ON target.trade_date = source.trade_date
AND target.market_state_version = source.market_state_version
AND target.trade_date BETWEEN p_write_start_date AND p_write_end_date
WHEN MATCHED THEN UPDATE SET
  sse_composite_ret_5d = source.sse_composite_ret_5d,
  sse_composite_ret_20d = source.sse_composite_ret_20d,
  sse_composite_drawdown_20d = source.sse_composite_drawdown_20d,
  sse_composite_vol_20d = source.sse_composite_vol_20d,
  sse_composite_close_to_ma20 = source.sse_composite_close_to_ma20,
  sse_composite_close_to_ma60 = source.sse_composite_close_to_ma60,
  sse_composite_ma20_to_ma60 = source.sse_composite_ma20_to_ma60,
  csi300_ret_5d = source.csi300_ret_5d,
  csi300_ret_20d = source.csi300_ret_20d,
  csi300_drawdown_20d = source.csi300_drawdown_20d,
  csi300_vol_20d = source.csi300_vol_20d,
  csi1000_ret_5d = source.csi1000_ret_5d,
  csi1000_ret_20d = source.csi1000_ret_20d,
  csi1000_drawdown_20d = source.csi1000_drawdown_20d,
  csi1000_vol_20d = source.csi1000_vol_20d,
  csi1000_close_to_ma20 = source.csi1000_close_to_ma20,
  csi1000_close_to_ma60 = source.csi1000_close_to_ma60,
  csi1000_ma20_to_ma60 = source.csi1000_ma20_to_ma60,
  stock_count = source.stock_count,
  adv_count = source.adv_count,
  decline_count = source.decline_count,
  adv_ratio_1d = source.adv_ratio_1d,
  above_ma20_count = source.above_ma20_count,
  above_ma20_ratio = source.above_ma20_ratio,
  new_low_20d_count = source.new_low_20d_count,
  new_low_20d_ratio = source.new_low_20d_ratio,
  limit_down_count = source.limit_down_count,
  one_word_limit_down_count = source.one_word_limit_down_count,
  limit_down_mv_cny = source.limit_down_mv_cny,
  universe_mv_cny = source.universe_mv_cny,
  limit_down_mv_ratio = source.limit_down_mv_ratio,
  avg_ret_20d = source.avg_ret_20d,
  ret_20d_p25 = source.ret_20d_p25,
  ret_20d_median = source.ret_20d_median,
  drawdown_20d_median = source.drawdown_20d_median,
  avg_vol_20d = source.avg_vol_20d,
  is_smallcap_trend_down = source.is_smallcap_trend_down,
  is_breadth_weak = source.is_breadth_weak,
  is_limit_down_diffusion = source.is_limit_down_diffusion,
  risk_off_trigger_count = source.risk_off_trigger_count,
  is_risk_off = source.is_risk_off,
  market_regime = source.market_regime,
  risk_off_reasons = source.risk_off_reasons,
  risk_off_action = source.risk_off_action,
  created_at = source.created_at
WHEN NOT MATCHED THEN INSERT (
  trade_date,
  market_state_version,
  sse_composite_ret_5d,
  sse_composite_ret_20d,
  sse_composite_drawdown_20d,
  sse_composite_vol_20d,
  sse_composite_close_to_ma20,
  sse_composite_close_to_ma60,
  sse_composite_ma20_to_ma60,
  csi300_ret_5d,
  csi300_ret_20d,
  csi300_drawdown_20d,
  csi300_vol_20d,
  csi1000_ret_5d,
  csi1000_ret_20d,
  csi1000_drawdown_20d,
  csi1000_vol_20d,
  csi1000_close_to_ma20,
  csi1000_close_to_ma60,
  csi1000_ma20_to_ma60,
  stock_count,
  adv_count,
  decline_count,
  adv_ratio_1d,
  above_ma20_count,
  above_ma20_ratio,
  new_low_20d_count,
  new_low_20d_ratio,
  limit_down_count,
  one_word_limit_down_count,
  limit_down_mv_cny,
  universe_mv_cny,
  limit_down_mv_ratio,
  avg_ret_20d,
  ret_20d_p25,
  ret_20d_median,
  drawdown_20d_median,
  avg_vol_20d,
  is_smallcap_trend_down,
  is_breadth_weak,
  is_limit_down_diffusion,
  risk_off_trigger_count,
  is_risk_off,
  market_regime,
  risk_off_reasons,
  risk_off_action,
  created_at
) VALUES (
  source.trade_date,
  source.market_state_version,
  source.sse_composite_ret_5d,
  source.sse_composite_ret_20d,
  source.sse_composite_drawdown_20d,
  source.sse_composite_vol_20d,
  source.sse_composite_close_to_ma20,
  source.sse_composite_close_to_ma60,
  source.sse_composite_ma20_to_ma60,
  source.csi300_ret_5d,
  source.csi300_ret_20d,
  source.csi300_drawdown_20d,
  source.csi300_vol_20d,
  source.csi1000_ret_5d,
  source.csi1000_ret_20d,
  source.csi1000_drawdown_20d,
  source.csi1000_vol_20d,
  source.csi1000_close_to_ma20,
  source.csi1000_close_to_ma60,
  source.csi1000_ma20_to_ma60,
  source.stock_count,
  source.adv_count,
  source.decline_count,
  source.adv_ratio_1d,
  source.above_ma20_count,
  source.above_ma20_ratio,
  source.new_low_20d_count,
  source.new_low_20d_ratio,
  source.limit_down_count,
  source.one_word_limit_down_count,
  source.limit_down_mv_cny,
  source.universe_mv_cny,
  source.limit_down_mv_ratio,
  source.avg_ret_20d,
  source.ret_20d_p25,
  source.ret_20d_median,
  source.drawdown_20d_median,
  source.avg_vol_20d,
  source.is_smallcap_trend_down,
  source.is_breadth_weak,
  source.is_limit_down_diffusion,
  source.risk_off_trigger_count,
  source.is_risk_off,
  source.market_regime,
  source.risk_off_reasons,
  source.risk_off_action,
  source.created_at
);

SELECT
  'market-state window refresh completed' AS status,
  p_read_start_date AS read_start_date,
  p_write_start_date AS write_start_date,
  p_write_end_date AS write_end_date,
  COUNT(*) AS row_count,
  COUNTIF(market_state_version = 'market_state_v1_20260607') AS current_version_row_count
FROM `data-aquarium.ashare_dws.dws_market_state_daily`
WHERE trade_date BETWEEN p_write_start_date AND p_write_end_date;
