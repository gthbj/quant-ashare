-- 文档维护：GPT-5（最近更新 2026-05-31）
-- BigQuery Standard SQL
-- 指数日线 DWD：保留 ODS 实际存在的指数代码，并补充常用 canonical_index_code。

DECLARE dwd_start_date DATE DEFAULT DATE '2019-01-01';
DECLARE dwd_end_date DATE DEFAULT CURRENT_DATE('Asia/Shanghai');

CREATE OR REPLACE TABLE `data-aquarium.ashare_dwd.dwd_index_eod`
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY sec_code
OPTIONS (
  description = 'Daily index price and valuation DWD for available Tushare index_daily/index_dailybasic endpoints; rows written from 2019-01-01',
  require_partition_filter = TRUE
) AS
WITH index_map AS (
  SELECT '000016.SH' AS sec_code, '000016.SH' AS canonical_index_code, 'SSE50' AS index_alias UNION ALL
  SELECT '000688.SH', '000688.SH', 'STAR50' UNION ALL
  SELECT '000852.SH', '000852.SH', 'CSI1000' UNION ALL
  SELECT '000905.SH', '000905.SH', 'CSI500' UNION ALL
  SELECT '399001.SZ', '399001.SZ', 'SZ_COMPONENT' UNION ALL
  SELECT '399006.SZ', '399006.SZ', 'CHINEXT' UNION ALL
  SELECT '399300.SZ', '000300.SH', 'CSI300'
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
    SAFE_CAST(vol AS FLOAT64) AS volume,
    SAFE_CAST(amount AS FLOAT64) AS amount,
    COALESCE(_source, 'tushare') AS source_system,
    partition_date AS source_partition_date,
    SAFE_CAST(_ingested_at AS TIMESTAMP) AS ingested_at
  FROM `data-aquarium.ashare_ods.ods_tushare_index_daily`
  WHERE endpoint IN (
      'index_daily_000016_SH',
      'index_daily_000688_SH',
      'index_daily_000852_SH',
      'index_daily_000905_SH',
      'index_daily_399001_SZ',
      'index_daily_399006_SZ',
      'index_daily_399300_SZ'
    )
    AND partition_date BETWEEN FORMAT_DATE('%Y%m%d', dwd_start_date) AND FORMAT_DATE('%Y%m%d', dwd_end_date)
    AND SAFE.PARSE_DATE('%Y%m%d', trade_date) BETWEEN dwd_start_date AND dwd_end_date
),
daily_basic AS (
  SELECT
    ts_code AS sec_code,
    SAFE.PARSE_DATE('%Y%m%d', trade_date) AS trade_date,
    SAFE_CAST(total_mv AS FLOAT64) AS total_mv_10k_cny,
    SAFE_CAST(float_mv AS FLOAT64) AS float_mv_10k_cny,
    SAFE_CAST(total_mv AS FLOAT64) * 10000.0 AS total_mv_cny,
    SAFE_CAST(float_mv AS FLOAT64) * 10000.0 AS float_mv_cny,
    SAFE_CAST(total_share AS FLOAT64) AS total_share_10k,
    SAFE_CAST(float_share AS FLOAT64) AS float_share_10k,
    SAFE_CAST(free_share AS FLOAT64) AS free_share_10k,
    SAFE_CAST(total_share AS FLOAT64) * 10000.0 AS total_share,
    SAFE_CAST(float_share AS FLOAT64) * 10000.0 AS float_share,
    SAFE_CAST(free_share AS FLOAT64) * 10000.0 AS free_share,
    SAFE_CAST(turnover_rate AS FLOAT64) AS turnover_rate,
    SAFE_CAST(turnover_rate_f AS FLOAT64) AS turnover_rate_free_float,
    SAFE_CAST(pe AS FLOAT64) AS pe,
    SAFE_CAST(pe_ttm AS FLOAT64) AS pe_ttm,
    SAFE_CAST(pb AS FLOAT64) AS pb
  FROM `data-aquarium.ashare_ods.ods_tushare_index_dailybasic`
  WHERE endpoint IN (
      'index_dailybasic_000016_SH',
      'index_dailybasic_000905_SH',
      'index_dailybasic_399001_SZ',
      'index_dailybasic_399006_SZ',
      'index_dailybasic_399300_SZ'
    )
    AND partition_date BETWEEN FORMAT_DATE('%Y%m%d', dwd_start_date) AND FORMAT_DATE('%Y%m%d', dwd_end_date)
    AND SAFE.PARSE_DATE('%Y%m%d', trade_date) BETWEEN dwd_start_date AND dwd_end_date
)
SELECT
  d.trade_date,
  d.sec_code,
  m.canonical_index_code,
  m.index_alias,
  d.open,
  d.high,
  d.low,
  d.close,
  d.pre_close,
  d.change,
  d.pct_chg,
  d.volume,
  d.amount,
  b.total_mv_10k_cny,
  b.float_mv_10k_cny,
  b.total_mv_cny,
  b.float_mv_cny,
  b.total_share_10k,
  b.float_share_10k,
  b.free_share_10k,
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
  ON d.sec_code = b.sec_code
 AND d.trade_date = b.trade_date
LEFT JOIN index_map AS m
  ON d.sec_code = m.sec_code;

ALTER TABLE `data-aquarium.ashare_dwd.dwd_index_eod`
ALTER COLUMN trade_date SET OPTIONS (description = '交易日，月分区字段'),
ALTER COLUMN sec_code SET OPTIONS (description = 'ODS 实际指数代码'),
ALTER COLUMN canonical_index_code SET OPTIONS (description = '规范指数代码；399300.SZ 映射为 000300.SH'),
ALTER COLUMN index_alias SET OPTIONS (description = '常用指数别名');
