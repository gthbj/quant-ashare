-- 文档维护：GPT-5（最近更新 2026-06-01）
-- BigQuery Standard SQL
-- 指数主维表：维护 canonical 指数代码、ODS 实际代码、端点可用性和 benchmark 候选状态。
-- 只 seed 当前 ODS index_daily source URI 中真实存在的端点；中证2000、国证2000等候选指数
-- 当前未见可用 ODS 端点，需上游补采后再加入 dim_index，不能提前写入默认 benchmark。
-- 字段描述由 sql/metadata/01_p0_table_column_descriptions.sql 统一维护。

DECLARE dwd_start_date DATE DEFAULT DATE '2019-01-01';
DECLARE dwd_end_date DATE DEFAULT CURRENT_DATE('Asia/Shanghai');

CREATE OR REPLACE TABLE `data-aquarium.ashare_dim.dim_index`
CLUSTER BY sec_code, source_sec_code
OPTIONS (
  description = 'Index dimension for canonical index code mapping, ODS endpoint availability, and benchmark candidate validation'
) AS
WITH index_seed AS (
  SELECT * FROM UNNEST([
    STRUCT(
      '000016.SH' AS source_sec_code,
      '000016.SH' AS sec_code,
      'SSE50' AS index_alias,
      '上证50' AS index_name,
      'SSE' AS index_family,
      'index_daily_000016_SH' AS daily_endpoint,
      'index_dailybasic_000016_SH' AS dailybasic_endpoint,
      TRUE AS allow_benchmark_candidate,
      '收益与 dailybasic 均可用' AS benchmark_note
    ),
    STRUCT(
      '000688.SH',
      '000688.SH',
      'STAR50',
      '科创50',
      'STAR',
      'index_daily_000688_SH',
      CAST(NULL AS STRING),
      TRUE,
      '收益基准可用；当前 ODS 无 dailybasic 端点，不能作为依赖估值字段的市场状态来源'
    ),
    STRUCT(
      '000852.SH',
      '000852.SH',
      'CSI1000',
      '中证1000',
      'CSI',
      'index_daily_000852_SH',
      CAST(NULL AS STRING),
      TRUE,
      '收益基准可用；当前 ODS 无 dailybasic 端点，不能作为依赖估值字段的市场状态来源'
    ),
    STRUCT(
      '000905.SH',
      '000905.SH',
      'CSI500',
      '中证500',
      'CSI',
      'index_daily_000905_SH',
      'index_dailybasic_000905_SH',
      TRUE,
      '收益与 dailybasic 均可用'
    ),
    STRUCT(
      '399001.SZ',
      '399001.SZ',
      'SZ_COMPONENT',
      '深证成指',
      'SZSE',
      'index_daily_399001_SZ',
      'index_dailybasic_399001_SZ',
      TRUE,
      '收益与 dailybasic 均可用'
    ),
    STRUCT(
      '399006.SZ',
      '399006.SZ',
      'CHINEXT',
      '创业板指',
      'SZSE',
      'index_daily_399006_SZ',
      'index_dailybasic_399006_SZ',
      TRUE,
      '收益与 dailybasic 均可用'
    ),
    STRUCT(
      '399300.SZ',
      '000300.SH',
      'CSI300',
      '沪深300',
      'CSI',
      'index_daily_399300_SZ',
      'index_dailybasic_399300_SZ',
      TRUE,
      'ODS 实际端点为 399300.SZ；DWD/ADS canonical 输出为 000300.SH'
    )
  ])
),
daily_stats AS (
  SELECT
    endpoint,
    ts_code AS source_sec_code,
    MIN(SAFE.PARSE_DATE('%Y%m%d', trade_date)) AS daily_first_trade_date,
    MAX(SAFE.PARSE_DATE('%Y%m%d', trade_date)) AS daily_last_trade_date,
    COUNT(*) AS daily_row_count,
    MAX(partition_date) AS daily_source_partition_date,
    MAX(SAFE_CAST(_ingested_at AS TIMESTAMP)) AS daily_ingested_at
  FROM `data-aquarium.ashare_ods.ods_tushare_index_daily`
  WHERE partition_date BETWEEN FORMAT_DATE('%Y%m%d', dwd_start_date) AND FORMAT_DATE('%Y%m%d', dwd_end_date)
    AND endpoint IN (SELECT daily_endpoint FROM index_seed WHERE daily_endpoint IS NOT NULL)
    AND SAFE.PARSE_DATE('%Y%m%d', trade_date) BETWEEN dwd_start_date AND dwd_end_date
  GROUP BY endpoint, ts_code
),
dailybasic_stats AS (
  SELECT
    endpoint,
    ts_code AS source_sec_code,
    MIN(SAFE.PARSE_DATE('%Y%m%d', trade_date)) AS dailybasic_first_trade_date,
    MAX(SAFE.PARSE_DATE('%Y%m%d', trade_date)) AS dailybasic_last_trade_date,
    COUNT(*) AS dailybasic_row_count,
    MAX(partition_date) AS dailybasic_source_partition_date,
    MAX(SAFE_CAST(_ingested_at AS TIMESTAMP)) AS dailybasic_ingested_at
  FROM `data-aquarium.ashare_ods.ods_tushare_index_dailybasic`
  WHERE partition_date BETWEEN FORMAT_DATE('%Y%m%d', dwd_start_date) AND FORMAT_DATE('%Y%m%d', dwd_end_date)
    AND endpoint IN (SELECT dailybasic_endpoint FROM index_seed WHERE dailybasic_endpoint IS NOT NULL)
    AND SAFE.PARSE_DATE('%Y%m%d', trade_date) BETWEEN dwd_start_date AND dwd_end_date
  GROUP BY endpoint, ts_code
)
SELECT
  s.sec_code,
  s.source_sec_code,
  s.index_alias,
  s.index_name,
  s.index_family,
  s.daily_endpoint,
  s.dailybasic_endpoint,
  d.daily_first_trade_date,
  d.daily_last_trade_date,
  b.dailybasic_first_trade_date,
  b.dailybasic_last_trade_date,
  IFNULL(d.daily_row_count > 0, FALSE) AS has_daily,
  IFNULL(b.dailybasic_row_count > 0, FALSE) AS has_dailybasic,
  IFNULL(d.daily_row_count > 0, FALSE) AND s.allow_benchmark_candidate AS is_benchmark_candidate,
  s.benchmark_note,
  'tushare' AS source_system,
  (
    SELECT MAX(partition_date)
    FROM UNNEST([d.daily_source_partition_date, b.dailybasic_source_partition_date]) AS partition_date
  ) AS source_partition_date,
  (
    SELECT MAX(ts)
    FROM UNNEST([d.daily_ingested_at, b.dailybasic_ingested_at]) AS ts
  ) AS ingested_at
FROM index_seed AS s
LEFT JOIN daily_stats AS d
  ON d.endpoint = s.daily_endpoint
 AND d.source_sec_code = s.source_sec_code
LEFT JOIN dailybasic_stats AS b
  ON b.endpoint = s.dailybasic_endpoint
 AND b.source_sec_code = s.source_sec_code;
