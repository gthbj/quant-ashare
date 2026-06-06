-- =============================================================================
-- QA: ODS Daily Partition Readiness Checks
-- 09_ods_daily_partition_readiness.sql
--
-- Daily scheduler guard for OQ-005. This checks only the business-date
-- partition or a recent small lookback window. Full-history schema checks and
-- repair validation remain in 06_ods_parquet_schema_checks.sql and must not
-- block the daily DAG by default.
--
-- Endpoint classification:
--   Strong (blocking): daily, daily_basic, adj_factor, stk_limit, index_daily
--     - Must have data on trading days by 20:00 CST
--     - Missing data blocks downstream transform
--
--   Weak (non-blocking): suspend_d, stock_basic, trade_cal, namechange,
--                         index_dailybasic, income_vip, balancesheet_vip,
--                         cashflow_vip, fina_indicator_vip
--     - No strict hourly guarantee
--     - Missing data logged but doesn't block pipeline
--     - API empty_return may be normal (e.g., no suspensions on a given day)
--
-- Parameters:
--   @pipeline_run_id: STRING, Composer DAG run id
--   @business_date: STRING, YYYY-MM-DD or YYYYMMDD
--   @pipeline_dry_run: STRING, 'true' or 'false'
--   @require_business_partition: STRING, optional 'true' or 'false'
--
-- Tushare official update times (for reference):
--   daily:          https://tushare.pro/document/2?doc_id=27   15:00-16:00 or 15:00-17:00
--   daily_basic:    https://tushare.pro/document/2?doc_id=32   15:00-17:00
--   adj_factor:     https://tushare.pro/document/2?doc_id=28   盘前 9:15-9:20
--   stk_limit:      https://tushare.pro/document/1?doc_id=108  交易日 9:00
--   index_daily:    https://tushare.pro/document/1?doc_id=108  15:00-17:00
--   suspend_d:      https://tushare.pro/document/2?doc_id=214  不定期
--   stock_basic:    https://tushare.pro/document/2?doc_id=25   无严格盘后保证
--   trade_cal:      https://tushare.pro/document/2?doc_id=26   交易日历
--   namechange:     https://tushare.pro/document/2?doc_id=100  无严格盘后保证
--   index_dailybasic: https://tushare.pro/document/1?doc_id=108 盘后更新
--   income/balancesheet/cashflow/fina_indicator: 财报实时更新
-- =============================================================================

DECLARE p_pipeline_run_id STRING DEFAULT @pipeline_run_id;
DECLARE p_business_date_arg STRING DEFAULT @business_date;
DECLARE p_pipeline_dry_run_arg STRING DEFAULT LOWER(TRIM(COALESCE(NULLIF(@pipeline_dry_run, ''), 'true')));
DECLARE p_require_business_partition_arg STRING DEFAULT LOWER(TRIM(COALESCE(@require_business_partition, '')));
DECLARE p_pipeline_dry_run BOOL DEFAULT p_pipeline_dry_run_arg IN ('1', 'true', 'yes', 'y', 'on');
DECLARE p_require_business_partition BOOL DEFAULT IF(
  p_require_business_partition_arg = '',
  NOT p_pipeline_dry_run,
  p_require_business_partition_arg IN ('1', 'true', 'yes', 'y', 'on')
);

DECLARE p_business_date DATE DEFAULT COALESCE(
  SAFE.PARSE_DATE('%Y-%m-%d', p_business_date_arg),
  SAFE.PARSE_DATE('%Y%m%d', p_business_date_arg)
);

DECLARE p_business_partition STRING DEFAULT FORMAT_DATE('%Y%m%d', p_business_date);
DECLARE p_recent_start STRING DEFAULT FORMAT_DATE('%Y%m%d', DATE_SUB(p_business_date, INTERVAL 30 DAY));
DECLARE p_finance_recent_start STRING DEFAULT FORMAT_DATE('%Y%m%d', DATE_SUB(p_business_date, INTERVAL 800 DAY));

-- Check if business_date is a trading day
DECLARE p_is_trading_day BOOL DEFAULT (
  SELECT COUNT(*) > 0
  FROM `data-aquarium.ashare_dim.dim_trade_calendar`
  WHERE exchange = 'SSE'
    AND is_open = 1
    AND cal_date = p_business_date
);

DECLARE p_trade_partition STRING DEFAULT COALESCE(
  (
    SELECT FORMAT_DATE('%Y%m%d', MAX(cal_date))
    FROM `data-aquarium.ashare_dim.dim_trade_calendar`
    WHERE exchange = 'SSE'
      AND is_open = 1
      AND cal_date <= p_business_date
  ),
  p_business_partition
);

-- API row limit for Tushare (default 5000 per request)
DECLARE p_api_row_limit INT64 DEFAULT 5000;

ASSERT p_pipeline_dry_run_arg IN ('1', 'true', 'yes', 'y', 'on', '0', 'false', 'no', 'n', 'off')
  AS 'QA-ODS-DAILY-0A: pipeline_dry_run must be true/false-like';

ASSERT p_require_business_partition_arg IN ('', '1', 'true', 'yes', 'y', 'on', '0', 'false', 'no', 'n', 'off')
  AS 'QA-ODS-DAILY-0B: require_business_partition must be empty or true/false-like';

ASSERT p_business_date IS NOT NULL AS 'QA-ODS-DAILY-0: business_date must be YYYY-MM-DD or YYYYMMDD';

-- =============================================================================
-- Strong endpoints: blocking on trading days
-- =============================================================================
CREATE TEMP TABLE qa_ods_strong_results AS
SELECT *
FROM (
  -- daily
  SELECT
    'market_eod' AS endpoint_group,
    'daily' AS endpoint,
    'strong' AS gate_type,
    p_trade_partition AS exact_partition,
    pd AS checked_partition,
    TRUE AS require_rows,
    TRUE AS require_exact_in_production,
    (
      SELECT COUNT(*)
      FROM `data-aquarium.ashare_ods.ods_tushare_daily`
      WHERE endpoint = 'daily'
        AND partition_date = pd
        AND trade_date = pd
        AND (close IS NULL OR close IS NOT NULL)
    ) AS row_count
  FROM (
    SELECT IF(
      p_require_business_partition,
      p_trade_partition,
      (
        SELECT MAX(partition_date)
        FROM `data-aquarium.ashare_ods.ods_tushare_daily`
        WHERE endpoint = 'daily'
          AND partition_date BETWEEN p_recent_start AND p_trade_partition
      )
    ) AS pd
  )

  UNION ALL
  -- daily_basic
  SELECT 'market_eod', 'daily_basic', 'strong', p_trade_partition, pd, TRUE, TRUE,
    (SELECT COUNT(*) FROM `data-aquarium.ashare_ods.ods_tushare_daily_basic` WHERE endpoint = 'daily_basic' AND partition_date = pd AND (close IS NULL OR close IS NOT NULL))
  FROM (SELECT IF(p_require_business_partition, p_trade_partition, (SELECT MAX(partition_date) FROM `data-aquarium.ashare_ods.ods_tushare_daily_basic` WHERE endpoint = 'daily_basic' AND partition_date BETWEEN p_recent_start AND p_trade_partition)) AS pd)

  UNION ALL
  -- adj_factor
  SELECT 'market_eod', 'adj_factor', 'strong', p_trade_partition, pd, TRUE, TRUE,
    (SELECT COUNT(*) FROM `data-aquarium.ashare_ods.ods_tushare_adj_factor` WHERE endpoint = 'adj_factor' AND partition_date = pd AND (adj_factor IS NULL OR adj_factor IS NOT NULL))
  FROM (SELECT IF(p_require_business_partition, p_trade_partition, (SELECT MAX(partition_date) FROM `data-aquarium.ashare_ods.ods_tushare_adj_factor` WHERE endpoint = 'adj_factor' AND partition_date BETWEEN p_recent_start AND p_trade_partition)) AS pd)

  UNION ALL
  -- stk_limit
  SELECT 'market_eod', 'stk_limit', 'strong', p_trade_partition, pd, TRUE, TRUE,
    (SELECT COUNT(*) FROM `data-aquarium.ashare_ods.ods_tushare_stk_limit` WHERE endpoint = 'stk_limit' AND partition_date = pd AND (up_limit IS NULL OR up_limit IS NOT NULL))
  FROM (SELECT IF(p_require_business_partition, p_trade_partition, (SELECT MAX(partition_date) FROM `data-aquarium.ashare_ods.ods_tushare_stk_limit` WHERE endpoint = 'stk_limit' AND partition_date BETWEEN p_recent_start AND p_trade_partition)) AS pd)

  UNION ALL
  -- index_daily
  SELECT 'index_eod', 'index_daily', 'strong', p_trade_partition, pd, TRUE, TRUE,
    (SELECT COUNT(*) FROM `data-aquarium.ashare_ods.ods_tushare_index_daily` WHERE endpoint LIKE 'index_daily_%' AND partition_date = pd AND trade_date = pd AND (close IS NULL OR close IS NOT NULL))
  FROM (SELECT IF(p_require_business_partition, p_trade_partition, (SELECT MAX(partition_date) FROM `data-aquarium.ashare_ods.ods_tushare_index_daily` WHERE endpoint LIKE 'index_daily_%' AND partition_date BETWEEN p_recent_start AND p_trade_partition)) AS pd)
);

-- =============================================================================
-- Weak endpoints: non-blocking, observational
-- =============================================================================
CREATE TEMP TABLE qa_ods_weak_results AS
SELECT *
FROM (
  -- suspend_d
  SELECT
    'market_eod' AS endpoint_group,
    'suspend_d' AS endpoint,
    'weak' AS gate_type,
    p_trade_partition AS exact_partition,
    pd AS checked_partition,
    FALSE AS require_rows,  -- empty_return may be normal (no suspensions)
    FALSE AS require_exact_in_production,
    (
      SELECT COUNT(*)
      FROM `data-aquarium.ashare_ods.ods_tushare_suspend_d`
      WHERE endpoint = 'suspend_d'
        AND partition_date = pd
    ) AS row_count
  FROM (
    SELECT IF(
      p_require_business_partition,
      p_trade_partition,
      (
        SELECT MAX(partition_date)
        FROM `data-aquarium.ashare_ods.ods_tushare_suspend_d`
        WHERE endpoint = 'suspend_d'
          AND partition_date BETWEEN p_recent_start AND p_trade_partition
      )
    ) AS pd
  )

  UNION ALL
  -- stock_basic
  SELECT 'dim_snapshot', 'stock_basic', 'weak', p_business_partition, pd, TRUE, FALSE,
    (SELECT COUNT(*) FROM `data-aquarium.ashare_ods.ods_tushare_stock_basic` WHERE endpoint IN ('stock_basic_listed', 'stock_basic_delisted') AND partition_date = pd AND (ts_code IS NULL OR ts_code IS NOT NULL))
  FROM (SELECT IF(p_require_business_partition, p_business_partition, (SELECT MAX(partition_date) FROM `data-aquarium.ashare_ods.ods_tushare_stock_basic` WHERE endpoint IN ('stock_basic_listed', 'stock_basic_delisted') AND partition_date BETWEEN p_recent_start AND p_business_partition)) AS pd)

  UNION ALL
  -- trade_cal
  SELECT 'dim_snapshot', 'trade_cal', 'weak', p_business_partition, pd, TRUE, FALSE,
    (SELECT COUNT(*) FROM `data-aquarium.ashare_ods.ods_tushare_trade_cal` WHERE endpoint = 'trade_cal' AND partition_date = pd AND (cal_date IS NULL OR cal_date IS NOT NULL))
  FROM (SELECT IF(p_require_business_partition, p_business_partition, (SELECT MAX(partition_date) FROM `data-aquarium.ashare_ods.ods_tushare_trade_cal` WHERE endpoint = 'trade_cal' AND partition_date BETWEEN p_recent_start AND p_business_partition)) AS pd)

  UNION ALL
  -- namechange
  SELECT 'dim_snapshot', 'namechange', 'weak', p_business_partition, pd, TRUE, FALSE,
    (SELECT COUNT(*) FROM `data-aquarium.ashare_ods.ods_tushare_namechange` WHERE endpoint = 'namechange' AND partition_date = pd AND (ts_code IS NULL OR ts_code IS NOT NULL))
  FROM (SELECT IF(p_require_business_partition, p_business_partition, (SELECT MAX(partition_date) FROM `data-aquarium.ashare_ods.ods_tushare_namechange` WHERE endpoint = 'namechange' AND partition_date BETWEEN p_recent_start AND p_business_partition)) AS pd)

  UNION ALL
  -- index_dailybasic
  SELECT 'index_eod', 'index_dailybasic', 'weak', p_trade_partition, pd, TRUE, FALSE,
    (SELECT COUNT(*) FROM `data-aquarium.ashare_ods.ods_tushare_index_dailybasic` WHERE endpoint LIKE 'index_dailybasic_%' AND partition_date = pd AND trade_date = pd AND (total_mv IS NULL OR total_mv IS NOT NULL))
  FROM (SELECT IF(p_require_business_partition, p_trade_partition, (SELECT MAX(partition_date) FROM `data-aquarium.ashare_ods.ods_tushare_index_dailybasic` WHERE endpoint LIKE 'index_dailybasic_%' AND partition_date BETWEEN p_recent_start AND p_trade_partition)) AS pd)

  UNION ALL
  -- fina_indicator
  SELECT 'finance_recent', 'fina_indicator', 'weak', NULL, pd, TRUE, FALSE,
    (SELECT COUNT(*) FROM `data-aquarium.ashare_ods.ods_tushare_fina_indicator` WHERE endpoint = 'fina_indicator' AND partition_date = pd AND (ann_date IS NULL OR ann_date IS NOT NULL))
  FROM (SELECT MAX(partition_date) AS pd FROM `data-aquarium.ashare_ods.ods_tushare_fina_indicator` WHERE endpoint = 'fina_indicator' AND partition_date BETWEEN p_finance_recent_start AND p_business_partition)

  UNION ALL
  -- income
  SELECT 'finance_recent', 'income', 'weak', NULL, pd, TRUE, FALSE,
    (SELECT COUNT(*) FROM `data-aquarium.ashare_ods.ods_tushare_income` WHERE endpoint = 'income' AND partition_date = pd AND (end_date IS NULL OR end_date IS NOT NULL))
  FROM (SELECT MAX(partition_date) AS pd FROM `data-aquarium.ashare_ods.ods_tushare_income` WHERE endpoint = 'income' AND partition_date BETWEEN p_finance_recent_start AND p_business_partition)

  UNION ALL
  -- balancesheet
  SELECT 'finance_recent', 'balancesheet', 'weak', NULL, pd, TRUE, FALSE,
    (SELECT COUNT(*) FROM `data-aquarium.ashare_ods.ods_tushare_balancesheet` WHERE endpoint = 'balancesheet' AND partition_date = pd AND (end_date IS NULL OR end_date IS NOT NULL))
  FROM (SELECT MAX(partition_date) AS pd FROM `data-aquarium.ashare_ods.ods_tushare_balancesheet` WHERE endpoint = 'balancesheet' AND partition_date BETWEEN p_finance_recent_start AND p_business_partition)

  UNION ALL
  -- cashflow
  SELECT 'finance_recent', 'cashflow', 'weak', NULL, pd, TRUE, FALSE,
    (SELECT COUNT(*) FROM `data-aquarium.ashare_ods.ods_tushare_cashflow` WHERE endpoint = 'cashflow' AND partition_date = pd AND (end_date IS NULL OR end_date IS NOT NULL))
  FROM (SELECT MAX(partition_date) AS pd FROM `data-aquarium.ashare_ods.ods_tushare_cashflow` WHERE endpoint = 'cashflow' AND partition_date BETWEEN p_finance_recent_start AND p_business_partition)
);

-- =============================================================================
-- Output results for observability
-- =============================================================================
CREATE TEMP TABLE qa_ods_readiness_results AS
SELECT
  p_business_date AS business_date,
  p_is_trading_day AS is_trading_day,
  p_trade_partition AS trade_partition,
  p_pipeline_dry_run AS pipeline_dry_run,
  p_require_business_partition AS require_business_partition,
  endpoint_group,
  endpoint,
  gate_type,
  exact_partition,
  checked_partition,
  row_count,
  require_rows,
  CASE
    WHEN row_count = p_api_row_limit THEN 'API_LIMIT_RISK'
    WHEN row_count = 0 AND require_rows AND (p_is_trading_day OR p_require_business_partition) THEN 'MISSING_REQUIRED'
    WHEN row_count = 0 AND NOT require_rows THEN 'EMPTY_OK'
    ELSE 'OK'
  END AS status
FROM (
  SELECT * FROM qa_ods_strong_results
  UNION ALL
  SELECT * FROM qa_ods_weak_results
)
ORDER BY gate_type, endpoint_group, endpoint;

-- Persist non-blocking readiness warnings before blocking ASSERTs so warning
-- context remains visible even when strong endpoint readiness fails.
IF NOT p_pipeline_dry_run THEN
  MERGE `data-aquarium.ashare_meta.pipeline_task_status` AS T
  USING (
    SELECT
      p_pipeline_run_id AS pipeline_run_id,
      CONCAT(
        'ods_daily_partition_readiness.',
        LOWER(status),
        '.',
        REPLACE(endpoint, '/', '_')
      ) AS task_id,
      'qa' AS task_type,
      CAST(business_date AS STRING) AS business_date,
      'warning' AS status,
      row_count,
      endpoint,
      CONCAT(
        'ODS readiness warning: endpoint=', endpoint,
        ', status=', status,
        ', checked_partition=', COALESCE(checked_partition, 'NULL'),
        ', exact_partition=', COALESCE(exact_partition, 'NULL'),
        ', row_count=', CAST(row_count AS STRING)
      ) AS error_summary
    FROM qa_ods_readiness_results
    WHERE status = 'API_LIMIT_RISK'
       OR (p_is_trading_day AND gate_type = 'weak' AND status = 'MISSING_REQUIRED')
  ) AS S
  ON T.pipeline_run_id = S.pipeline_run_id AND T.task_id = S.task_id
  WHEN MATCHED THEN UPDATE SET
    task_type = S.task_type,
    business_date = S.business_date,
    endpoint = S.endpoint,
    status = S.status,
    row_count = S.row_count,
    error_summary = S.error_summary,
    updated_at = CURRENT_TIMESTAMP()
  WHEN NOT MATCHED THEN INSERT (
    pipeline_run_id,
    task_id,
    task_type,
    business_date,
    endpoint,
    status,
    row_count,
    error_summary,
    created_at,
    updated_at
  ) VALUES (
    S.pipeline_run_id,
    S.task_id,
    S.task_type,
    S.business_date,
    S.endpoint,
    S.status,
    S.row_count,
    S.error_summary,
    CURRENT_TIMESTAMP(),
    CURRENT_TIMESTAMP()
  );
END IF;

-- =============================================================================
-- Assertions: only strong endpoints block on trading days
-- =============================================================================

-- QA-ODS-DAILY-1: no missing partition for strong endpoints
ASSERT (
  SELECT COUNTIF(checked_partition IS NULL) = 0
  FROM qa_ods_strong_results
) AS 'QA-ODS-DAILY-1: no recent partition found for strong ODS endpoints';

-- QA-ODS-DAILY-2: strong endpoints must have rows on trading days
-- Only enforced on trading days to avoid blocking on weekends/holidays
ASSERT (
  SELECT COUNTIF(require_rows AND row_count = 0) = 0
  FROM qa_ods_strong_results
  WHERE p_is_trading_day OR p_require_business_partition
) AS 'QA-ODS-DAILY-2: strong ODS endpoints must have data on trading days';

-- QA-ODS-DAILY-3: production run must find exact partition for strong endpoints
ASSERT (
  SELECT COUNTIF(
    p_require_business_partition
    AND require_exact_in_production
    AND checked_partition != exact_partition
  ) = 0
  FROM qa_ods_strong_results
) AS 'QA-ODS-DAILY-3: production run must find exact partition for strong endpoints';

-- QA-ODS-DAILY-4: detect API row limit hit (potential truncation)
-- This is a warning, not a blocker.

SELECT *
FROM qa_ods_readiness_results
ORDER BY gate_type, endpoint_group, endpoint;
