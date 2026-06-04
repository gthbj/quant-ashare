-- =============================================================================
-- QA: ODS Daily Partition Readiness Checks
-- 09_ods_daily_partition_readiness.sql
--
-- Daily scheduler guard for OQ-005. This checks only the business-date
-- partition or a recent small lookback window. Full-history schema checks and
-- repair validation remain in 06_ods_parquet_schema_checks.sql and must not
-- block the daily DAG by default.
--
-- Parameters:
--   @business_date: STRING, YYYY-MM-DD or YYYYMMDD
--   @require_business_partition: STRING, 'true' or 'false'
--
-- Dry-run Composer smoke passes require_business_partition='false', because
-- ingestion dry-run does not write new GCS partitions. Production write runs
-- pass 'true', requiring exact trade-day/snapshot partitions for daily sources.
-- =============================================================================

DECLARE p_business_date_arg STRING DEFAULT @business_date;
DECLARE p_require_business_partition BOOL DEFAULT LOWER(@require_business_partition) = 'true';

DECLARE p_business_date DATE DEFAULT COALESCE(
  SAFE.PARSE_DATE('%Y-%m-%d', p_business_date_arg),
  SAFE.PARSE_DATE('%Y%m%d', p_business_date_arg)
);

DECLARE p_business_partition STRING DEFAULT FORMAT_DATE('%Y%m%d', p_business_date);
DECLARE p_recent_start STRING DEFAULT FORMAT_DATE('%Y%m%d', DATE_SUB(p_business_date, INTERVAL 30 DAY));
DECLARE p_finance_recent_start STRING DEFAULT FORMAT_DATE('%Y%m%d', DATE_SUB(p_business_date, INTERVAL 800 DAY));

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

ASSERT p_business_date IS NOT NULL AS 'QA-ODS-DAILY-0: business_date must be YYYY-MM-DD or YYYYMMDD';

CREATE TEMP TABLE qa_ods_daily_partition_results AS
SELECT *
FROM (
  SELECT
    'market_eod' AS endpoint_group,
    'daily' AS endpoint,
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
  SELECT
    'market_eod',
    'adj_factor',
    p_trade_partition,
    pd,
    TRUE,
    TRUE,
    (
      SELECT COUNT(*)
      FROM `data-aquarium.ashare_ods.ods_tushare_adj_factor`
      WHERE endpoint = 'adj_factor'
        AND partition_date = pd
        AND trade_date = pd
        AND (adj_factor IS NULL OR adj_factor IS NOT NULL)
    )
  FROM (
    SELECT IF(
      p_require_business_partition,
      p_trade_partition,
      (
        SELECT MAX(partition_date)
        FROM `data-aquarium.ashare_ods.ods_tushare_adj_factor`
        WHERE endpoint = 'adj_factor'
          AND partition_date BETWEEN p_recent_start AND p_trade_partition
      )
    ) AS pd
  )

  UNION ALL
  SELECT
    'market_eod',
    'stk_limit',
    p_trade_partition,
    pd,
    TRUE,
    TRUE,
    (
      SELECT COUNT(*)
      FROM `data-aquarium.ashare_ods.ods_tushare_stk_limit`
      WHERE endpoint = 'stk_limit'
        AND partition_date = pd
        AND trade_date = pd
        AND (up_limit IS NULL OR up_limit IS NOT NULL)
        AND (down_limit IS NULL OR down_limit IS NOT NULL)
    )
  FROM (
    SELECT IF(
      p_require_business_partition,
      p_trade_partition,
      (
        SELECT MAX(partition_date)
        FROM `data-aquarium.ashare_ods.ods_tushare_stk_limit`
        WHERE endpoint = 'stk_limit'
          AND partition_date BETWEEN p_recent_start AND p_trade_partition
      )
    ) AS pd
  )

  UNION ALL
  SELECT
    'market_eod',
    'suspend_d',
    p_trade_partition,
    pd,
    FALSE,
    TRUE,
    (
      SELECT COUNT(*)
      FROM `data-aquarium.ashare_ods.ods_tushare_suspend_d`
      WHERE endpoint = 'suspend_d'
        AND partition_date = pd
        AND (suspend_type IS NULL OR suspend_type IS NOT NULL)
    )
  FROM (
    SELECT IF(
      p_require_business_partition,
      p_trade_partition,
      COALESCE(
        (
          SELECT MAX(partition_date)
          FROM `data-aquarium.ashare_ods.ods_tushare_suspend_d`
          WHERE endpoint = 'suspend_d'
            AND partition_date BETWEEN p_recent_start AND p_trade_partition
        ),
        p_trade_partition
      )
    ) AS pd
  )

  UNION ALL
  SELECT
    'market_eod',
    'daily_basic',
    p_trade_partition,
    pd,
    TRUE,
    TRUE,
    (
      SELECT COUNT(*)
      FROM `data-aquarium.ashare_ods.ods_tushare_daily_basic`
      WHERE endpoint = 'daily_basic'
        AND partition_date = pd
        AND trade_date = pd
        AND (total_mv IS NULL OR total_mv IS NOT NULL)
    )
  FROM (
    SELECT IF(
      p_require_business_partition,
      p_trade_partition,
      (
        SELECT MAX(partition_date)
        FROM `data-aquarium.ashare_ods.ods_tushare_daily_basic`
        WHERE endpoint = 'daily_basic'
          AND partition_date BETWEEN p_recent_start AND p_trade_partition
      )
    ) AS pd
  )

  UNION ALL
  SELECT
    'index_eod',
    'index_daily',
    p_trade_partition,
    pd,
    TRUE,
    TRUE,
    (
      SELECT COUNT(*)
      FROM `data-aquarium.ashare_ods.ods_tushare_index_daily`
      WHERE endpoint LIKE 'index_daily_%'
        AND partition_date = pd
        AND trade_date = pd
        AND (close IS NULL OR close IS NOT NULL)
    )
  FROM (
    SELECT IF(
      p_require_business_partition,
      p_trade_partition,
      (
        SELECT MAX(partition_date)
        FROM `data-aquarium.ashare_ods.ods_tushare_index_daily`
        WHERE endpoint LIKE 'index_daily_%'
          AND partition_date BETWEEN p_recent_start AND p_trade_partition
      )
    ) AS pd
  )

  UNION ALL
  SELECT
    'index_eod',
    'index_dailybasic',
    p_trade_partition,
    pd,
    TRUE,
    TRUE,
    (
      SELECT COUNT(*)
      FROM `data-aquarium.ashare_ods.ods_tushare_index_dailybasic`
      WHERE endpoint LIKE 'index_dailybasic_%'
        AND partition_date = pd
        AND trade_date = pd
        AND (total_mv IS NULL OR total_mv IS NOT NULL)
    )
  FROM (
    SELECT IF(
      p_require_business_partition,
      p_trade_partition,
      (
        SELECT MAX(partition_date)
        FROM `data-aquarium.ashare_ods.ods_tushare_index_dailybasic`
        WHERE endpoint LIKE 'index_dailybasic_%'
          AND partition_date BETWEEN p_recent_start AND p_trade_partition
      )
    ) AS pd
  )

  UNION ALL
  SELECT
    'dim_snapshot',
    'stock_basic',
    p_business_partition,
    pd,
    TRUE,
    TRUE,
    (
      SELECT COUNT(*)
      FROM `data-aquarium.ashare_ods.ods_tushare_stock_basic`
      WHERE endpoint IN ('stock_basic_listed', 'stock_basic_delisted')
        AND partition_date = pd
        AND (ts_code IS NULL OR ts_code IS NOT NULL)
    )
  FROM (
    SELECT IF(
      p_require_business_partition,
      p_business_partition,
      (
        SELECT MAX(partition_date)
        FROM `data-aquarium.ashare_ods.ods_tushare_stock_basic`
        WHERE endpoint IN ('stock_basic_listed', 'stock_basic_delisted')
          AND partition_date BETWEEN p_recent_start AND p_business_partition
      )
    ) AS pd
  )

  UNION ALL
  SELECT
    'dim_snapshot',
    'trade_cal',
    p_business_partition,
    pd,
    TRUE,
    TRUE,
    (
      SELECT COUNT(*)
      FROM `data-aquarium.ashare_ods.ods_tushare_trade_cal`
      WHERE endpoint = 'trade_cal'
        AND partition_date = pd
        AND (cal_date IS NULL OR cal_date IS NOT NULL)
    )
  FROM (
    SELECT IF(
      p_require_business_partition,
      p_business_partition,
      (
        SELECT MAX(partition_date)
        FROM `data-aquarium.ashare_ods.ods_tushare_trade_cal`
        WHERE endpoint = 'trade_cal'
          AND partition_date BETWEEN p_recent_start AND p_business_partition
      )
    ) AS pd
  )

  UNION ALL
  SELECT
    'dim_snapshot',
    'namechange',
    p_business_partition,
    pd,
    TRUE,
    TRUE,
    (
      SELECT COUNT(*)
      FROM `data-aquarium.ashare_ods.ods_tushare_namechange`
      WHERE endpoint = 'namechange'
        AND partition_date = pd
        AND (ts_code IS NULL OR ts_code IS NOT NULL)
    )
  FROM (
    SELECT IF(
      p_require_business_partition,
      p_business_partition,
      (
        SELECT MAX(partition_date)
        FROM `data-aquarium.ashare_ods.ods_tushare_namechange`
        WHERE endpoint = 'namechange'
          AND partition_date BETWEEN p_recent_start AND p_business_partition
      )
    ) AS pd
  )

  UNION ALL
  SELECT
    'finance_recent',
    'fina_indicator',
    NULL,
    pd,
    TRUE,
    FALSE,
    (
      SELECT COUNT(*)
      FROM `data-aquarium.ashare_ods.ods_tushare_fina_indicator`
      WHERE endpoint = 'fina_indicator'
        AND partition_date = pd
        AND (ann_date IS NULL OR ann_date IS NOT NULL)
    )
  FROM (
    SELECT MAX(partition_date) AS pd
    FROM `data-aquarium.ashare_ods.ods_tushare_fina_indicator`
    WHERE endpoint = 'fina_indicator'
      AND partition_date BETWEEN p_finance_recent_start AND p_business_partition
  )

  UNION ALL
  SELECT
    'finance_recent',
    'income',
    NULL,
    pd,
    TRUE,
    FALSE,
    (
      SELECT COUNT(*)
      FROM `data-aquarium.ashare_ods.ods_tushare_income`
      WHERE endpoint = 'income'
        AND partition_date = pd
        AND (end_date IS NULL OR end_date IS NOT NULL)
    )
  FROM (
    SELECT MAX(partition_date) AS pd
    FROM `data-aquarium.ashare_ods.ods_tushare_income`
    WHERE endpoint = 'income'
      AND partition_date BETWEEN p_finance_recent_start AND p_business_partition
  )

  UNION ALL
  SELECT
    'finance_recent',
    'balancesheet',
    NULL,
    pd,
    TRUE,
    FALSE,
    (
      SELECT COUNT(*)
      FROM `data-aquarium.ashare_ods.ods_tushare_balancesheet`
      WHERE endpoint = 'balancesheet'
        AND partition_date = pd
        AND (end_date IS NULL OR end_date IS NOT NULL)
    )
  FROM (
    SELECT MAX(partition_date) AS pd
    FROM `data-aquarium.ashare_ods.ods_tushare_balancesheet`
    WHERE endpoint = 'balancesheet'
      AND partition_date BETWEEN p_finance_recent_start AND p_business_partition
  )

  UNION ALL
  SELECT
    'finance_recent',
    'cashflow',
    NULL,
    pd,
    TRUE,
    FALSE,
    (
      SELECT COUNT(*)
      FROM `data-aquarium.ashare_ods.ods_tushare_cashflow`
      WHERE endpoint = 'cashflow'
        AND partition_date = pd
        AND (end_date IS NULL OR end_date IS NOT NULL)
    )
  FROM (
    SELECT MAX(partition_date) AS pd
    FROM `data-aquarium.ashare_ods.ods_tushare_cashflow`
    WHERE endpoint = 'cashflow'
      AND partition_date BETWEEN p_finance_recent_start AND p_business_partition
  )
);

ASSERT (
  SELECT COUNTIF(checked_partition IS NULL) = 0
  FROM qa_ods_daily_partition_results
) AS 'QA-ODS-DAILY-1: no recent partition found for one or more current-scope ODS endpoints';

ASSERT (
  SELECT COUNTIF(require_rows AND row_count = 0) = 0
  FROM qa_ods_daily_partition_results
) AS 'QA-ODS-DAILY-2: required daily/recent ODS partition has zero rows';

ASSERT (
  SELECT COUNTIF(
    p_require_business_partition
    AND require_exact_in_production
    AND checked_partition != exact_partition
  ) = 0
  FROM qa_ods_daily_partition_results
) AS 'QA-ODS-DAILY-3: production run did not find exact business/trade partition';

SELECT
  p_business_partition AS business_partition,
  p_trade_partition AS trade_partition,
  p_require_business_partition AS require_business_partition,
  endpoint_group,
  endpoint,
  exact_partition,
  checked_partition,
  row_count
FROM qa_ods_daily_partition_results
ORDER BY endpoint_group, endpoint;
