-- =============================================================================
-- QA: ODS Parquet Schema Readability Checks
-- 06_ods_parquet_schema_checks.sql
-- Validates that repaired ODS external tables have readable business columns
-- for partition_date >= '20190101'.
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
    AND COUNT(pre_close) > 0
    AND COUNT(up_limit) > 0
    AND COUNT(down_limit) > 0
    AND COUNT(ts_code) > 0
    AND COUNT(trade_date) > 0
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
      AND COUNT(amount) > 0
      AND COUNT(limit_amount) > 0
      AND COUNT(fd_amount) > 0
      AND COUNT(open_times) > 0
      AND COUNT(limit_times) > 0
    FROM `data-aquarium.ashare_ods.ods_tushare_limit_list_d`
    WHERE endpoint = 'limit_list_d'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-2: ods_tushare_limit_list_d business columns not readable for 2019+';

  -- ASSERT 3: ods_tushare_moneyflow - P1 所有业务列可读
  ASSERT (
    SELECT
      COUNT(*) > 0
      AND COUNT(buy_md_vol) > 0
      AND COUNT(sell_md_vol) > 0
      AND COUNT(net_mf_amount) > 0
    FROM `data-aquarium.ashare_ods.ods_tushare_moneyflow`
    WHERE endpoint = 'moneyflow'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-3: ods_tushare_moneyflow business columns not readable for 2019+';

  -- ASSERT 4: ods_tushare_margin_detail - P1 所有业务列可读
  ASSERT (
    SELECT
      COUNT(*) > 0
      AND COUNT(rqye) > 0
      AND COUNT(rzrqye) > 0
      AND COUNT(rzye) > 0
    FROM `data-aquarium.ashare_ods.ods_tushare_margin_detail`
    WHERE endpoint = 'margin_detail'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-4: ods_tushare_margin_detail business columns not readable for 2019+';

  -- ASSERT 5: ods_tushare_dividend - P1 所有业务列可读
  ASSERT (
    SELECT
      COUNT(*) > 0
      AND COUNT(stk_bo_rate) > 0
      AND COUNT(stk_co_rate) > 0
    FROM `data-aquarium.ashare_ods.ods_tushare_dividend`
    WHERE endpoint = 'dividend'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-5: ods_tushare_dividend business columns not readable for 2019+';

  -- ASSERT 6: ods_tushare_margin - P2 所有业务列可读
  ASSERT (
    SELECT
      COUNT(*) > 0
      AND COUNT(rqyl) > 0
      AND COUNT(rzye) > 0
    FROM `data-aquarium.ashare_ods.ods_tushare_margin`
    WHERE endpoint = 'margin'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-6: ods_tushare_margin business columns not readable for 2019+';

  -- ASSERT 7: ods_tushare_daily_info - P2 所有业务列可读
  ASSERT (
    SELECT
      COUNT(*) > 0
      AND COUNT(com_count) > 0
      AND COUNT(trans_count) > 0
    FROM `data-aquarium.ashare_ods.ods_tushare_daily_info`
    WHERE endpoint = 'daily_info'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-7: ods_tushare_daily_info business columns not readable for 2019+';

  -- ASSERT 8: ods_tushare_sz_daily_info - P2 所有业务列可读
  ASSERT (
    SELECT
      COUNT(*) > 0
      AND COUNT(total_share) > 0
      AND COUNT(total_mv) > 0
      AND COUNT(float_share) > 0
      AND COUNT(float_mv) > 0
    FROM `data-aquarium.ashare_ods.ods_tushare_sz_daily_info`
    WHERE endpoint = 'sz_daily_info'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-8: ods_tushare_sz_daily_info business columns not readable for 2019+';

  -- ASSERT 9: ods_tushare_fina_audit - P2 所有业务列可读
  ASSERT (
    SELECT
      COUNT(*) > 0
      AND COUNT(audit_fees) > 0
    FROM `data-aquarium.ashare_ods.ods_tushare_fina_audit`
    WHERE endpoint = 'fina_audit'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-9: ods_tushare_fina_audit business columns not readable for 2019+';

  -- ASSERT 10: ods_tushare_stk_rewards - P3 所有业务列可读
  ASSERT (
    SELECT
      COUNT(*) > 0
      AND COUNT(hold_vol) > 0
    FROM `data-aquarium.ashare_ods.ods_tushare_stk_rewards`
    WHERE endpoint = 'stk_rewards'
      AND partition_date >= '20190101'
  ) AS 'QA-SCHEMA-10: ods_tushare_stk_rewards business columns not readable for 2019+';

END IF;
