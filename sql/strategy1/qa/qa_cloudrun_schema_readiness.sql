-- BigQuery Standard SQL
-- Strategy 1 Cloud Run schema readiness QA.
--
-- This preflight checks the ADS schema needed by Cloud Run train/select/backtest
-- jobs before launching a live annual rolling run. It intentionally checks
-- metadata only; it does not inspect or mutate run data.

DECLARE required_tables ARRAY<STRING>;
DECLARE required_columns ARRAY<STRUCT<table_name STRING, column_name STRING, data_type STRING>>;

SET required_tables = [
  'ads_backtest_trade_daily',
  'ads_backtest_position_daily',
  'ads_backtest_nav_daily',
  'ads_backtest_ledger_state_daily',
  'ads_backtest_performance_summary'
];

SET required_columns = ARRAY<STRUCT<table_name STRING, column_name STRING, data_type STRING>>[
  STRUCT('ads_backtest_trade_daily', 'backtest_id', 'STRING'),
  STRUCT('ads_backtest_trade_daily', 'trade_date', 'DATE'),
  STRUCT('ads_backtest_trade_daily', 'fill_status', 'STRING'),
  STRUCT('ads_backtest_trade_daily', 'run_id', 'STRING'),
  STRUCT('ads_backtest_position_daily', 'backtest_id', 'STRING'),
  STRUCT('ads_backtest_position_daily', 'trade_date', 'DATE'),
  STRUCT('ads_backtest_position_daily', 'sec_code', 'STRING'),
  STRUCT('ads_backtest_position_daily', 'run_id', 'STRING'),
  STRUCT('ads_backtest_nav_daily', 'backtest_id', 'STRING'),
  STRUCT('ads_backtest_nav_daily', 'trade_date', 'DATE'),
  STRUCT('ads_backtest_nav_daily', 'nav', 'FLOAT64'),
  STRUCT('ads_backtest_nav_daily', 'cash_cny', 'FLOAT64'),
  STRUCT('ads_backtest_nav_daily', 'net_value_cny', 'FLOAT64'),
  STRUCT('ads_backtest_nav_daily', 'benchmark_sec_code', 'STRING'),
  STRUCT('ads_backtest_nav_daily', 'excess_return', 'FLOAT64'),
  STRUCT('ads_backtest_nav_daily', 'run_id', 'STRING'),
  STRUCT('ads_backtest_ledger_state_daily', 'backtest_id', 'STRING'),
  STRUCT('ads_backtest_ledger_state_daily', 'trade_date', 'DATE'),
  STRUCT('ads_backtest_ledger_state_daily', 'cash_cny', 'FLOAT64'),
  STRUCT('ads_backtest_ledger_state_daily', 'net_value_cny', 'FLOAT64'),
  STRUCT('ads_backtest_ledger_state_daily', 'nav', 'FLOAT64'),
  STRUCT('ads_backtest_ledger_state_daily', 'pending_sell_sec_codes_json', 'STRING'),
  STRUCT('ads_backtest_ledger_state_daily', 'active_signal_date', 'DATE'),
  STRUCT('ads_backtest_ledger_state_daily', 'active_target_weights_json', 'STRING'),
  STRUCT('ads_backtest_ledger_state_daily', 'holdings_hash', 'STRING'),
  STRUCT('ads_backtest_ledger_state_daily', 'ledger_version', 'STRING'),
  STRUCT('ads_backtest_ledger_state_daily', 'ledger_params_hash', 'STRING'),
  STRUCT('ads_backtest_ledger_state_daily', 'resume_policy_id', 'STRING'),
  STRUCT('ads_backtest_ledger_state_daily', 'rebalance_anchor_start', 'DATE'),
  STRUCT('ads_backtest_ledger_state_daily', 'run_id', 'STRING'),
  STRUCT('ads_backtest_ledger_state_daily', 'created_at', 'TIMESTAMP'),
  STRUCT('ads_backtest_performance_summary', 'backtest_id', 'STRING'),
  STRUCT('ads_backtest_performance_summary', 'run_id', 'STRING'),
  STRUCT('ads_backtest_performance_summary', 'benchmark_sec_code', 'STRING'),
  STRUCT('ads_backtest_performance_summary', 'excess_return', 'FLOAT64'),
  STRUCT('ads_backtest_performance_summary', 'metrics_json', 'STRING'),
  STRUCT('ads_backtest_performance_summary', 'compound_annual_return', 'FLOAT64'),
  STRUCT('ads_backtest_performance_summary', 'return_period_count', 'INT64'),
  STRUCT('ads_backtest_performance_summary', 'annualization_target_period_count', 'INT64'),
  STRUCT('ads_backtest_performance_summary', 'annualization_method', 'STRING'),
  STRUCT('ads_backtest_performance_summary', 'created_date', 'DATE')
];

ASSERT (
  SELECT COUNT(*) = ARRAY_LENGTH(required_tables)
  FROM `data-aquarium`.ashare_ads.INFORMATION_SCHEMA.TABLES
  WHERE table_name IN UNNEST(required_tables)
) AS 'QA-SCHEMA-1: required Cloud Run ADS tables are missing; run sql/ads/02_alter_strategy1_backtest_compound_annual_return.sql and sql/ads/03_create_strategy1_backtest_ledger_state_daily.sql before launching the job';

ASSERT (
  SELECT COUNT(*) = ARRAY_LENGTH(required_columns)
  FROM UNNEST(required_columns) AS req
  JOIN `data-aquarium`.ashare_ads.INFORMATION_SCHEMA.COLUMNS AS col
    ON col.table_name = req.table_name
   AND col.column_name = req.column_name
   AND col.data_type = req.data_type
) AS 'QA-SCHEMA-2: required Cloud Run ADS columns or types are missing; apply the additive ADS migrations, including sql/ads/04_alter_strategy1_backtest_summary_identity_columns.sql, before launching the job';

ASSERT (
  SELECT COUNT(*) = 4
  FROM `data-aquarium`.ashare_ads.INFORMATION_SCHEMA.COLUMNS
  WHERE table_name IN (
      'ads_backtest_trade_daily',
      'ads_backtest_position_daily',
      'ads_backtest_nav_daily',
      'ads_backtest_ledger_state_daily'
    )
    AND column_name = 'trade_date'
    AND is_partitioning_column = 'YES'
) AS 'QA-SCHEMA-3: run-scoped backtest daily tables must be partitioned by trade_date';

ASSERT (
  SELECT COUNT(*) = 5
  FROM `data-aquarium`.ashare_ads.INFORMATION_SCHEMA.COLUMNS
  WHERE (
      table_name IN (
        'ads_backtest_trade_daily',
        'ads_backtest_position_daily',
        'ads_backtest_nav_daily',
        'ads_backtest_ledger_state_daily',
        'ads_backtest_performance_summary'
      )
      AND column_name = 'backtest_id'
    )
    AND clustering_ordinal_position IS NOT NULL
) AS 'QA-SCHEMA-4: Cloud Run backtest output tables must cluster by backtest_id for run-scoped reads';
