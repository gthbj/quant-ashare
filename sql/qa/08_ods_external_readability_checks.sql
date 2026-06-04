-- 文档维护：GPT-5（最近更新 2026-06-04）
-- BigQuery Standard SQL
-- OQ-005: 当前生产采集范围 ODS 外部表可读性检查。
--
-- 范围：configs/ingestion/ods_current_scope_v0.yml 中当前 SQL 消费的 14 个 ODS endpoint。
-- 目的：在 ODS -> DIM/DWD/DWS/ADS 转换前，先确认外部表和 2019+ 分区可读。
-- 说明：这里不判断 API 空返回是否缺数；只检查已有 2019+ 分区是否能被 BigQuery 外部表读取。

DECLARE p_min_partition_date STRING DEFAULT '20190101';
DECLARE p_require_smoke_partition BOOL DEFAULT FALSE;
DECLARE p_smoke_endpoint STRING DEFAULT 'index_daily_000852_SH';
DECLARE p_smoke_partition_date STRING DEFAULT '20260603';
DECLARE p_smoke_run_id STRING DEFAULT 'oq005_gcs_smoke_index_daily_000852_20260603_01';

CREATE TEMP TABLE oq005_ods_readability AS
SELECT 'ods_tushare_daily' AS table_name, COUNT(*) AS sample_rows
FROM (
  SELECT 1
  FROM `data-aquarium.ashare_ods.ods_tushare_daily`
  WHERE endpoint = 'daily'
    AND partition_date BETWEEN p_min_partition_date AND '99999999'
  LIMIT 1
)
UNION ALL
SELECT 'ods_tushare_adj_factor', COUNT(*)
FROM (
  SELECT 1
  FROM `data-aquarium.ashare_ods.ods_tushare_adj_factor`
  WHERE endpoint = 'adj_factor'
    AND partition_date BETWEEN p_min_partition_date AND '99999999'
  LIMIT 1
)
UNION ALL
SELECT 'ods_tushare_stk_limit', COUNT(*)
FROM (
  SELECT 1
  FROM `data-aquarium.ashare_ods.ods_tushare_stk_limit`
  WHERE endpoint = 'stk_limit'
    AND partition_date BETWEEN p_min_partition_date AND '99999999'
  LIMIT 1
)
UNION ALL
SELECT 'ods_tushare_suspend_d', COUNT(*)
FROM (
  SELECT 1
  FROM `data-aquarium.ashare_ods.ods_tushare_suspend_d`
  WHERE endpoint = 'suspend_d'
    AND partition_date BETWEEN p_min_partition_date AND '99999999'
  LIMIT 1
)
UNION ALL
SELECT 'ods_tushare_daily_basic', COUNT(*)
FROM (
  SELECT 1
  FROM `data-aquarium.ashare_ods.ods_tushare_daily_basic`
  WHERE endpoint = 'daily_basic'
    AND partition_date BETWEEN p_min_partition_date AND '99999999'
  LIMIT 1
)
UNION ALL
SELECT 'ods_tushare_index_daily', COUNT(*)
FROM (
  SELECT 1
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
    AND partition_date BETWEEN p_min_partition_date AND '99999999'
  LIMIT 1
)
UNION ALL
SELECT 'ods_tushare_index_dailybasic', COUNT(*)
FROM (
  SELECT 1
  FROM `data-aquarium.ashare_ods.ods_tushare_index_dailybasic`
  WHERE endpoint IN (
      'index_dailybasic_000016_SH',
      'index_dailybasic_000905_SH',
      'index_dailybasic_399001_SZ',
      'index_dailybasic_399006_SZ',
      'index_dailybasic_399300_SZ'
    )
    AND partition_date BETWEEN p_min_partition_date AND '99999999'
  LIMIT 1
)
UNION ALL
SELECT 'ods_tushare_stock_basic', COUNT(*)
FROM (
  SELECT 1
  FROM `data-aquarium.ashare_ods.ods_tushare_stock_basic`
  WHERE endpoint IN ('stock_basic_listed', 'stock_basic_delisted')
    AND partition_date BETWEEN p_min_partition_date AND '99999999'
  LIMIT 1
)
UNION ALL
SELECT 'ods_tushare_trade_cal', COUNT(*)
FROM (
  SELECT 1
  FROM `data-aquarium.ashare_ods.ods_tushare_trade_cal`
  WHERE endpoint = 'trade_cal'
    AND partition_date BETWEEN p_min_partition_date AND '99999999'
  LIMIT 1
)
UNION ALL
SELECT 'ods_tushare_namechange', COUNT(*)
FROM (
  SELECT 1
  FROM `data-aquarium.ashare_ods.ods_tushare_namechange`
  WHERE endpoint = 'namechange'
    AND partition_date BETWEEN p_min_partition_date AND '99999999'
  LIMIT 1
)
UNION ALL
SELECT 'ods_tushare_fina_indicator', COUNT(*)
FROM (
  SELECT 1
  FROM `data-aquarium.ashare_ods.ods_tushare_fina_indicator`
  WHERE endpoint = 'fina_indicator'
    AND partition_date BETWEEN p_min_partition_date AND '99999999'
  LIMIT 1
)
UNION ALL
SELECT 'ods_tushare_income', COUNT(*)
FROM (
  SELECT 1
  FROM `data-aquarium.ashare_ods.ods_tushare_income`
  WHERE endpoint = 'income'
    AND partition_date BETWEEN p_min_partition_date AND '99999999'
  LIMIT 1
)
UNION ALL
SELECT 'ods_tushare_balancesheet', COUNT(*)
FROM (
  SELECT 1
  FROM `data-aquarium.ashare_ods.ods_tushare_balancesheet`
  WHERE endpoint = 'balancesheet'
    AND partition_date BETWEEN p_min_partition_date AND '99999999'
  LIMIT 1
)
UNION ALL
SELECT 'ods_tushare_cashflow', COUNT(*)
FROM (
  SELECT 1
  FROM `data-aquarium.ashare_ods.ods_tushare_cashflow`
  WHERE endpoint = 'cashflow'
    AND partition_date BETWEEN p_min_partition_date AND '99999999'
  LIMIT 1
);

ASSERT (
  SELECT COUNT(*) = 14
  FROM oq005_ods_readability
) AS 'QA-ODS-READ-1: OQ-005 readability scope must contain 14 ODS tables';

ASSERT (
  SELECT COUNTIF(sample_rows > 0) = COUNT(*)
  FROM oq005_ods_readability
) AS 'QA-ODS-READ-2: every current-scope ODS external table must have at least one readable 2019+ row';

IF p_require_smoke_partition THEN
  ASSERT (
    SELECT COUNT(*) = 1
    FROM `data-aquarium.ashare_ods.ods_tushare_index_daily`
    WHERE endpoint = p_smoke_endpoint
      AND partition_date = p_smoke_partition_date
      AND _run_id = p_smoke_run_id
  ) AS 'QA-ODS-READ-3: OQ-005 smoke partition must be readable with the expected run_id';
END IF;

SELECT *
FROM oq005_ods_readability
ORDER BY table_name;
