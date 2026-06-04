-- =============================================================================
-- QA: ODS Parquet Schema Readability Checks
-- 06_ods_parquet_schema_checks.sql
-- Validates that repaired ODS external tables have readable business columns
-- for partition_date >= '20190101'.
-- Readability checks reference each column without requiring non-null values.
--
-- Run P0 only (after repairing stk_limit):
--   bq query --location=asia-east2 --use_legacy_sql=false \
--     --parameter='priority_filter::P0' \
--     < sql/qa/06_ods_parquet_schema_checks.sql
--
-- Run all (after all 10 tables repaired):
--   bq query --location=asia-east2 --use_legacy_sql=false \
--     --parameter='priority_filter::all' \
--     < sql/qa/06_ods_parquet_schema_checks.sql
--
-- Each ASSERT raises an error if the condition fails, blocking downstream
-- merge/publish workflows.
-- =============================================================================

DECLARE priority_filter STRING DEFAULT @priority_filter;

-- ===========================================================================
-- P0 ASSERTS (always run)
-- ===========================================================================

-- ASSERT 1: ods_tushare_stk_limit - P0 所有业务列可读
ASSERT (
  SELECT
    COUNT(*) > 0
    AND COUNTIF(`pre_close` IS NULL OR `pre_close` IS NOT NULL) = COUNT(*)
    AND COUNTIF(`up_limit` IS NULL OR `up_limit` IS NOT NULL) = COUNT(*)
    AND COUNTIF(`down_limit` IS NULL OR `down_limit` IS NOT NULL) = COUNT(*)
    AND COUNTIF(`ts_code` IS NULL OR `ts_code` IS NOT NULL) = COUNT(*)
    AND COUNTIF(`trade_date` IS NULL OR `trade_date` IS NOT NULL) = COUNT(*)
  FROM `data-aquarium.ashare_ods.ods_tushare_stk_limit`
  WHERE endpoint = 'stk_limit'
    AND partition_date >= '20190101'
) AS 'QA-SCHEMA-1: ods_tushare_stk_limit business columns not readable for 2019+';

-- ASSERT 11: ods_tushare_stk_limit - P0 pre_close 范围合理
ASSERT (
  SELECT
    COUNT(pre_close) > 0
    AND MIN(pre_close) >= 0
    AND MAX(pre_close) < 100000
  FROM `data-aquarium.ashare_ods.ods_tushare_stk_limit`
  WHERE endpoint = 'stk_limit'
    AND partition_date >= '20190101'
) AS 'QA-SCHEMA-11: ods_tushare_stk_limit pre_close range invalid';

-- ===========================================================================
-- P1/P2/P3 ASSERTS (only when priority_filter != 'P0')
-- ===========================================================================

IF priority_filter != 'P0' THEN

  -- ASSERT 2: ods_tushare_limit_list_d - P1 所有业务列可读
  ASSERT (
    SELECT
      COUNT(*) > 0
      AND COUNTIF(`amount` IS NULL OR `amount` IS NOT NULL) = COUNT(*)
      AND COUNTIF(`limit_amount` IS NULL OR `limit_amount` IS NOT NULL) = COUNT(*)
      AND COUNTIF(`fd_amount` IS NULL OR `fd_amount` IS NOT NULL) = COUNT(*)
      AND COUNTIF(`open_times` IS NULL OR `open_times` IS NOT NULL) = COUNT(*)
      AND COUNTIF(`limit_times` IS NULL OR `limit_times` IS NOT NULL) = COUNT(*)
    FROM `data-aquarium.ashare_ods.ods_tushare_limit_list_d`
    WHERE endpoint = 'limit_list_d'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-2: ods_tushare_limit_list_d business columns not readable for 2019+';

  -- ASSERT 3: ods_tushare_moneyflow - P1 所有业务列可读
  ASSERT (
    SELECT
      COUNT(*) > 0
      AND COUNTIF(`buy_md_vol` IS NULL OR `buy_md_vol` IS NOT NULL) = COUNT(*)
      AND COUNTIF(`sell_md_vol` IS NULL OR `sell_md_vol` IS NOT NULL) = COUNT(*)
      AND COUNTIF(`net_mf_amount` IS NULL OR `net_mf_amount` IS NOT NULL) = COUNT(*)
    FROM `data-aquarium.ashare_ods.ods_tushare_moneyflow`
    WHERE endpoint = 'moneyflow'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-3: ods_tushare_moneyflow business columns not readable for 2019+';

  -- ASSERT 4: ods_tushare_margin_detail - P1 所有业务列可读
  ASSERT (
    SELECT
      COUNT(*) > 0
      AND COUNTIF(`rqye` IS NULL OR `rqye` IS NOT NULL) = COUNT(*)
      AND COUNTIF(`rzrqye` IS NULL OR `rzrqye` IS NOT NULL) = COUNT(*)
      AND COUNTIF(`rzye` IS NULL OR `rzye` IS NOT NULL) = COUNT(*)
    FROM `data-aquarium.ashare_ods.ods_tushare_margin_detail`
    WHERE endpoint = 'margin_detail'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-4: ods_tushare_margin_detail business columns not readable for 2019+';

  -- ASSERT 5: ods_tushare_dividend - P1 所有业务列可读
  ASSERT (
    SELECT
      COUNT(*) > 0
      AND COUNTIF(`stk_bo_rate` IS NULL OR `stk_bo_rate` IS NOT NULL) = COUNT(*)
      AND COUNTIF(`stk_co_rate` IS NULL OR `stk_co_rate` IS NOT NULL) = COUNT(*)
    FROM `data-aquarium.ashare_ods.ods_tushare_dividend`
    WHERE endpoint = 'dividend'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-5: ods_tushare_dividend business columns not readable for 2019+';

  -- ASSERT 6: ods_tushare_margin - P2 所有业务列可读
  ASSERT (
    SELECT
      COUNT(*) > 0
      AND COUNTIF(`rqyl` IS NULL OR `rqyl` IS NOT NULL) = COUNT(*)
      AND COUNTIF(`rzye` IS NULL OR `rzye` IS NOT NULL) = COUNT(*)
    FROM `data-aquarium.ashare_ods.ods_tushare_margin`
    WHERE endpoint = 'margin'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-6: ods_tushare_margin business columns not readable for 2019+';

  -- ASSERT 7: ods_tushare_daily_info - P2 所有业务列可读
  ASSERT (
    SELECT
      COUNT(*) > 0
      AND COUNTIF(`com_count` IS NULL OR `com_count` IS NOT NULL) = COUNT(*)
      AND COUNTIF(`trans_count` IS NULL OR `trans_count` IS NOT NULL) = COUNT(*)
    FROM `data-aquarium.ashare_ods.ods_tushare_daily_info`
    WHERE endpoint = 'daily_info'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-7: ods_tushare_daily_info business columns not readable for 2019+';

  -- ASSERT 8: ods_tushare_sz_daily_info - P2 所有业务列可读
  ASSERT (
    SELECT
      COUNT(*) > 0
      AND COUNTIF(`total_share` IS NULL OR `total_share` IS NOT NULL) = COUNT(*)
      AND COUNTIF(`total_mv` IS NULL OR `total_mv` IS NOT NULL) = COUNT(*)
      AND COUNTIF(`float_share` IS NULL OR `float_share` IS NOT NULL) = COUNT(*)
      AND COUNTIF(`float_mv` IS NULL OR `float_mv` IS NOT NULL) = COUNT(*)
    FROM `data-aquarium.ashare_ods.ods_tushare_sz_daily_info`
    WHERE endpoint = 'sz_daily_info'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-8: ods_tushare_sz_daily_info business columns not readable for 2019+';

  -- ASSERT 9: ods_tushare_fina_audit - P2 所有业务列可读
  ASSERT (
    SELECT
      COUNT(*) > 0
      AND COUNTIF(`audit_fees` IS NULL OR `audit_fees` IS NOT NULL) = COUNT(*)
    FROM `data-aquarium.ashare_ods.ods_tushare_fina_audit`
    WHERE endpoint = 'fina_audit'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-9: ods_tushare_fina_audit business columns not readable for 2019+';

  -- ASSERT 10: ods_tushare_stk_rewards - P3 所有业务列可读
  ASSERT (
    SELECT
      COUNT(*) > 0
      AND COUNTIF(`hold_vol` IS NULL OR `hold_vol` IS NOT NULL) = COUNT(*)
    FROM `data-aquarium.ashare_ods.ods_tushare_stk_rewards`
    WHERE endpoint = 'stk_rewards'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-10: ods_tushare_stk_rewards business columns not readable for 2019+';

END IF;
