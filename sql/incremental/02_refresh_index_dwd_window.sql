-- 文档维护：GPT-5 Codex（最近更新 2026-06-07）
-- BigQuery Standard SQL
-- Daily warehouse pipeline: 指数 DWD 窗口化刷新。
--
-- 口径：
-- - 目标表必须已由全量 CTAS 路径初始化。
-- - 本脚本只刷新 dwd_index_eod，不写 DWS market-state 或 ADS run/backtest 产物。
-- - daily_current 模式默认刷新最近 20 个交易日（含 date_to），覆盖指数 late data，并保持 2019+ 生产下限。
-- - backfill 模式使用显式 date_from/date_to；允许 owner 手工补 2019 年以前历史窗口。

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
DECLARE p_daily_current_lookback_td INT64 DEFAULT 20;
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

ASSERT p_warehouse_mode IN ('daily_current', 'backfill')
  AS 'index DWD window refresh requires warehouse_mode daily_current or backfill';

ASSERT p_write_end_date >= p_write_start_date
  AS 'index DWD window refresh requires write_end_date >= write_start_date';

ASSERT (
  SELECT COUNT(*) = 1
  FROM `data-aquarium.ashare_dwd.INFORMATION_SCHEMA.TABLES`
  WHERE table_name = 'dwd_index_eod'
) AS 'index DWD window refresh target dwd_index_eod must exist; run full_rebuild before daily_current/backfill';

BEGIN TRANSACTION;

DELETE FROM `data-aquarium.ashare_dwd.dwd_index_eod`
WHERE trade_date BETWEEN p_write_start_date AND p_write_end_date;

INSERT INTO `data-aquarium.ashare_dwd.dwd_index_eod` (
  trade_date,
  sec_code,
  source_sec_code,
  index_alias,
  open,
  high,
  low,
  close,
  pre_close,
  change,
  pct_chg,
  volume_lot,
  volume_share,
  amount_k_cny,
  amount_cny,
  total_mv_cny,
  float_mv_cny,
  total_share,
  float_share,
  free_share,
  turnover_rate,
  turnover_rate_free_float,
  pe,
  pe_ttm,
  pb,
  source_system,
  source_partition_date,
  ingested_at
)
WITH index_map AS (
  SELECT
    source_sec_code,
    sec_code,
    index_alias,
    daily_endpoint,
    dailybasic_endpoint,
    has_daily,
    has_dailybasic
  FROM `data-aquarium.ashare_dim.dim_index`
  WHERE has_daily
),
daily AS (
  SELECT
    m.sec_code,
    m.index_alias,
    d.ts_code AS source_sec_code,
    SAFE.PARSE_DATE('%Y%m%d', d.trade_date) AS trade_date,
    SAFE_CAST(d.open AS FLOAT64) AS open,
    SAFE_CAST(d.high AS FLOAT64) AS high,
    SAFE_CAST(d.low AS FLOAT64) AS low,
    SAFE_CAST(d.close AS FLOAT64) AS close,
    SAFE_CAST(d.pre_close AS FLOAT64) AS pre_close,
    SAFE_CAST(d.change AS FLOAT64) AS change,
    SAFE_CAST(d.pct_chg AS FLOAT64) AS pct_chg,
    SAFE_CAST(d.vol AS FLOAT64) AS volume_lot,
    SAFE_CAST(d.amount AS FLOAT64) AS amount_k_cny,
    COALESCE(d._source, 'tushare') AS source_system,
    d.partition_date AS source_partition_date,
    SAFE_CAST(d._ingested_at AS TIMESTAMP) AS ingested_at
  FROM `data-aquarium.ashare_ods.ods_tushare_index_daily` AS d
  JOIN index_map AS m
    ON d.endpoint = m.daily_endpoint
   AND d.ts_code = m.source_sec_code
  WHERE d.partition_date BETWEEN FORMAT_DATE('%Y%m%d', p_write_start_date) AND FORMAT_DATE('%Y%m%d', p_write_end_date)
    AND SAFE.PARSE_DATE('%Y%m%d', d.trade_date) BETWEEN p_write_start_date AND p_write_end_date
),
daily_basic AS (
  SELECT
    b.ts_code AS source_sec_code,
    SAFE.PARSE_DATE('%Y%m%d', b.trade_date) AS trade_date,
    SAFE_CAST(b.total_mv AS FLOAT64) AS total_mv_cny,
    SAFE_CAST(b.float_mv AS FLOAT64) AS float_mv_cny,
    SAFE_CAST(b.total_share AS FLOAT64) AS total_share,
    SAFE_CAST(b.float_share AS FLOAT64) AS float_share,
    SAFE_CAST(b.free_share AS FLOAT64) AS free_share,
    SAFE_CAST(b.turnover_rate AS FLOAT64) AS turnover_rate,
    SAFE_CAST(b.turnover_rate_f AS FLOAT64) AS turnover_rate_free_float,
    SAFE_CAST(b.pe AS FLOAT64) AS pe,
    SAFE_CAST(b.pe_ttm AS FLOAT64) AS pe_ttm,
    SAFE_CAST(b.pb AS FLOAT64) AS pb
  FROM `data-aquarium.ashare_ods.ods_tushare_index_dailybasic` AS b
  JOIN index_map AS m
    ON b.endpoint = m.dailybasic_endpoint
   AND b.ts_code = m.source_sec_code
  WHERE m.has_dailybasic
    AND b.partition_date BETWEEN FORMAT_DATE('%Y%m%d', p_write_start_date) AND FORMAT_DATE('%Y%m%d', p_write_end_date)
    AND SAFE.PARSE_DATE('%Y%m%d', b.trade_date) BETWEEN p_write_start_date AND p_write_end_date
)
SELECT
  d.trade_date,
  d.sec_code,
  d.source_sec_code,
  d.index_alias,
  d.open,
  d.high,
  d.low,
  d.close,
  d.pre_close,
  d.change,
  d.pct_chg,
  d.volume_lot,
  d.volume_lot * 100.0 AS volume_share,
  d.amount_k_cny,
  d.amount_k_cny * 1000.0 AS amount_cny,
  b.total_mv_cny,
  b.float_mv_cny,
  b.total_share,
  b.float_share,
  b.free_share,
  b.turnover_rate,
  b.turnover_rate_free_float,
  b.pe,
  b.pe_ttm,
  b.pb,
  d.source_system,
  d.source_partition_date,
  d.ingested_at
FROM daily AS d
LEFT JOIN daily_basic AS b
  ON d.source_sec_code = b.source_sec_code
 AND d.trade_date = b.trade_date;

COMMIT TRANSACTION;

SELECT
  'index DWD window refresh completed' AS status,
  p_write_start_date AS write_start_date,
  p_write_end_date AS write_end_date,
  COUNT(*) AS row_count,
  COUNTIF(sec_code = '000001.SH') AS sse_composite_row_count
FROM `data-aquarium.ashare_dwd.dwd_index_eod`
WHERE trade_date BETWEEN p_write_start_date AND p_write_end_date;
