-- 文档维护：GPT-5 Codex（最近更新 2026-06-10）
-- BigQuery Standard SQL
-- Strategy1 research schema readiness QA.
--
-- This preflight checks ashare_research metadata before enabling the next
-- research-first phase. It does not inspect or mutate run data.

DECLARE required_tables ARRAY<STRING>;
DECLARE required_columns ARRAY<STRUCT<table_name STRING, column_name STRING, data_type STRING>>;
DECLARE expected_partitions ARRAY<STRUCT<table_name STRING, column_name STRING>>;
DECLARE expected_clustering ARRAY<STRUCT<table_name STRING, column_name STRING, ordinal_position INT64>>;
DECLARE expected_defaults ARRAY<STRUCT<table_name STRING, column_name STRING, column_default STRING>>;
DECLARE partition_filter_tables ARRAY<STRING>;

SET required_tables = [
  'research_ml_training_panel_daily',
  'research_model_registry',
  'research_model_prediction_daily',
  'research_stock_candidate_daily',
  'research_portfolio_target_daily',
  'research_order_plan_daily',
  'research_backtest_trade_daily',
  'research_backtest_position_daily',
  'research_backtest_nav_daily',
  'research_backtest_ledger_state_daily',
  'research_backtest_performance_summary',
  'research_signal_monitor_daily',
  'research_acceptance_result',
  'research_experiment_run_status',
  'research_promotion_manifest'
];

SET required_columns = ARRAY<STRUCT<table_name STRING, column_name STRING, data_type STRING>>[
  STRUCT('research_ml_training_panel_daily', 'run_id', 'STRING'),
  STRUCT('research_ml_training_panel_daily', 'trade_date', 'DATE'),
  STRUCT('research_ml_training_panel_daily', 'sec_code', 'STRING'),
  STRUCT('research_ml_training_panel_daily', 'target_label', 'INT64'),
  STRUCT('research_ml_training_panel_daily', 'feature_values_json', 'STRING'),
  STRUCT('research_ml_training_panel_daily', 'research_status', 'STRING'),
  STRUCT('research_ml_training_panel_daily', 'promotion_status', 'STRING'),

  STRUCT('research_model_registry', 'model_id', 'STRING'),
  STRUCT('research_model_registry', 'run_id', 'STRING'),
  STRUCT('research_model_registry', 'search_id', 'STRING'),
  STRUCT('research_model_registry', 'experiment_id', 'STRING'),
  STRUCT('research_model_registry', 'model_uri', 'STRING'),
  STRUCT('research_model_registry', 'artifact_uri', 'STRING'),
  STRUCT('research_model_registry', 'acceptance_status', 'STRING'),
  STRUCT('research_model_registry', 'promotion_status', 'STRING'),
  STRUCT('research_model_registry', 'created_date', 'DATE'),

  STRUCT('research_model_prediction_daily', 'model_id', 'STRING'),
  STRUCT('research_model_prediction_daily', 'predict_date', 'DATE'),
  STRUCT('research_model_prediction_daily', 'sec_code', 'STRING'),
  STRUCT('research_model_prediction_daily', 'score', 'FLOAT64'),
  STRUCT('research_model_prediction_daily', 'raw_score', 'FLOAT64'),
  STRUCT('research_model_prediction_daily', 'rank_raw', 'INT64'),
  STRUCT('research_model_prediction_daily', 'run_id', 'STRING'),
  STRUCT('research_model_prediction_daily', 'research_status', 'STRING'),
  STRUCT('research_model_prediction_daily', 'promotion_status', 'STRING'),

  STRUCT('research_stock_candidate_daily', 'strategy_id', 'STRING'),
  STRUCT('research_stock_candidate_daily', 'rebalance_date', 'DATE'),
  STRUCT('research_stock_candidate_daily', 'sec_code', 'STRING'),
  STRUCT('research_stock_candidate_daily', 'model_id', 'STRING'),
  STRUCT('research_stock_candidate_daily', 'score', 'FLOAT64'),
  STRUCT('research_stock_candidate_daily', 'filter_reason', 'STRING'),
  STRUCT('research_stock_candidate_daily', 'run_id', 'STRING'),
  STRUCT('research_stock_candidate_daily', 'research_status', 'STRING'),
  STRUCT('research_stock_candidate_daily', 'promotion_status', 'STRING'),

  STRUCT('research_portfolio_target_daily', 'strategy_id', 'STRING'),
  STRUCT('research_portfolio_target_daily', 'rebalance_date', 'DATE'),
  STRUCT('research_portfolio_target_daily', 'sec_code', 'STRING'),
  STRUCT('research_portfolio_target_daily', 'target_weight', 'FLOAT64'),
  STRUCT('research_portfolio_target_daily', 'target_shares', 'FLOAT64'),
  STRUCT('research_portfolio_target_daily', 'run_id', 'STRING'),
  STRUCT('research_portfolio_target_daily', 'research_status', 'STRING'),
  STRUCT('research_portfolio_target_daily', 'promotion_status', 'STRING'),

  STRUCT('research_order_plan_daily', 'strategy_id', 'STRING'),
  STRUCT('research_order_plan_daily', 'rebalance_date', 'DATE'),
  STRUCT('research_order_plan_daily', 'sec_code', 'STRING'),
  STRUCT('research_order_plan_daily', 'side', 'STRING'),
  STRUCT('research_order_plan_daily', 'order_shares', 'FLOAT64'),
  STRUCT('research_order_plan_daily', 'expected_amount_cny', 'FLOAT64'),
  STRUCT('research_order_plan_daily', 'run_id', 'STRING'),
  STRUCT('research_order_plan_daily', 'research_status', 'STRING'),
  STRUCT('research_order_plan_daily', 'promotion_status', 'STRING'),

  STRUCT('research_backtest_trade_daily', 'backtest_id', 'STRING'),
  STRUCT('research_backtest_trade_daily', 'trade_date', 'DATE'),
  STRUCT('research_backtest_trade_daily', 'sec_code', 'STRING'),
  STRUCT('research_backtest_trade_daily', 'side', 'STRING'),
  STRUCT('research_backtest_trade_daily', 'filled_shares', 'FLOAT64'),
  STRUCT('research_backtest_trade_daily', 'fill_status', 'STRING'),
  STRUCT('research_backtest_trade_daily', 'run_id', 'STRING'),
  STRUCT('research_backtest_trade_daily', 'research_status', 'STRING'),
  STRUCT('research_backtest_trade_daily', 'promotion_status', 'STRING'),

  STRUCT('research_backtest_position_daily', 'backtest_id', 'STRING'),
  STRUCT('research_backtest_position_daily', 'trade_date', 'DATE'),
  STRUCT('research_backtest_position_daily', 'sec_code', 'STRING'),
  STRUCT('research_backtest_position_daily', 'shares', 'FLOAT64'),
  STRUCT('research_backtest_position_daily', 'market_value_cny', 'FLOAT64'),
  STRUCT('research_backtest_position_daily', 'weight', 'FLOAT64'),
  STRUCT('research_backtest_position_daily', 'run_id', 'STRING'),
  STRUCT('research_backtest_position_daily', 'research_status', 'STRING'),
  STRUCT('research_backtest_position_daily', 'promotion_status', 'STRING'),

  STRUCT('research_backtest_nav_daily', 'backtest_id', 'STRING'),
  STRUCT('research_backtest_nav_daily', 'trade_date', 'DATE'),
  STRUCT('research_backtest_nav_daily', 'nav', 'FLOAT64'),
  STRUCT('research_backtest_nav_daily', 'cash_cny', 'FLOAT64'),
  STRUCT('research_backtest_nav_daily', 'net_value_cny', 'FLOAT64'),
  STRUCT('research_backtest_nav_daily', 'benchmark_sec_code', 'STRING'),
  STRUCT('research_backtest_nav_daily', 'excess_return', 'FLOAT64'),
  STRUCT('research_backtest_nav_daily', 'run_id', 'STRING'),
  STRUCT('research_backtest_nav_daily', 'research_status', 'STRING'),
  STRUCT('research_backtest_nav_daily', 'promotion_status', 'STRING'),

  STRUCT('research_backtest_ledger_state_daily', 'backtest_id', 'STRING'),
  STRUCT('research_backtest_ledger_state_daily', 'trade_date', 'DATE'),
  STRUCT('research_backtest_ledger_state_daily', 'cash_cny', 'FLOAT64'),
  STRUCT('research_backtest_ledger_state_daily', 'net_value_cny', 'FLOAT64'),
  STRUCT('research_backtest_ledger_state_daily', 'nav', 'FLOAT64'),
  STRUCT('research_backtest_ledger_state_daily', 'pending_sell_sec_codes_json', 'STRING'),
  STRUCT('research_backtest_ledger_state_daily', 'active_signal_date', 'DATE'),
  STRUCT('research_backtest_ledger_state_daily', 'active_target_weights_json', 'STRING'),
  STRUCT('research_backtest_ledger_state_daily', 'holdings_hash', 'STRING'),
  STRUCT('research_backtest_ledger_state_daily', 'ledger_version', 'STRING'),
  STRUCT('research_backtest_ledger_state_daily', 'ledger_params_hash', 'STRING'),
  STRUCT('research_backtest_ledger_state_daily', 'resume_policy_id', 'STRING'),
  STRUCT('research_backtest_ledger_state_daily', 'rebalance_anchor_start', 'DATE'),
  STRUCT('research_backtest_ledger_state_daily', 'run_id', 'STRING'),
  STRUCT('research_backtest_ledger_state_daily', 'research_status', 'STRING'),
  STRUCT('research_backtest_ledger_state_daily', 'promotion_status', 'STRING'),

  STRUCT('research_backtest_performance_summary', 'backtest_id', 'STRING'),
  STRUCT('research_backtest_performance_summary', 'strategy_id', 'STRING'),
  STRUCT('research_backtest_performance_summary', 'model_id', 'STRING'),
  STRUCT('research_backtest_performance_summary', 'run_id', 'STRING'),
  STRUCT('research_backtest_performance_summary', 'start_date', 'DATE'),
  STRUCT('research_backtest_performance_summary', 'end_date', 'DATE'),
  STRUCT('research_backtest_performance_summary', 'total_return', 'FLOAT64'),
  STRUCT('research_backtest_performance_summary', 'annual_return', 'FLOAT64'),
  STRUCT('research_backtest_performance_summary', 'compound_annual_return', 'FLOAT64'),
  STRUCT('research_backtest_performance_summary', 'return_period_count', 'INT64'),
  STRUCT('research_backtest_performance_summary', 'annualization_target_period_count', 'INT64'),
  STRUCT('research_backtest_performance_summary', 'annualization_method', 'STRING'),
  STRUCT('research_backtest_performance_summary', 'metrics_json', 'STRING'),
  STRUCT('research_backtest_performance_summary', 'acceptance_status', 'STRING'),
  STRUCT('research_backtest_performance_summary', 'promotion_status', 'STRING'),
  STRUCT('research_backtest_performance_summary', 'created_date', 'DATE'),

  STRUCT('research_signal_monitor_daily', 'strategy_id', 'STRING'),
  STRUCT('research_signal_monitor_daily', 'model_id', 'STRING'),
  STRUCT('research_signal_monitor_daily', 'trade_date', 'DATE'),
  STRUCT('research_signal_monitor_daily', 'sample_count', 'INT64'),
  STRUCT('research_signal_monitor_daily', 'prediction_count', 'INT64'),
  STRUCT('research_signal_monitor_daily', 'candidate_count', 'INT64'),
  STRUCT('research_signal_monitor_daily', 'metrics_json', 'STRING'),
  STRUCT('research_signal_monitor_daily', 'run_id', 'STRING'),
  STRUCT('research_signal_monitor_daily', 'research_status', 'STRING'),
  STRUCT('research_signal_monitor_daily', 'promotion_status', 'STRING'),

  STRUCT('research_acceptance_result', 'acceptance_result_id', 'STRING'),
  STRUCT('research_acceptance_result', 'search_id', 'STRING'),
  STRUCT('research_acceptance_result', 'run_id', 'STRING'),
  STRUCT('research_acceptance_result', 'backtest_id', 'STRING'),
  STRUCT('research_acceptance_result', 'model_id', 'STRING'),
  STRUCT('research_acceptance_result', 'strategy_id', 'STRING'),
  STRUCT('research_acceptance_result', 'acceptance_gate_version', 'STRING'),
  STRUCT('research_acceptance_result', 'acceptance_contract_version', 'STRING'),
  STRUCT('research_acceptance_result', 'primary_benchmark_sec_code', 'STRING'),
  STRUCT('research_acceptance_result', 'acceptance_status', 'STRING'),
  STRUCT('research_acceptance_result', 'accepted', 'BOOL'),
  STRUCT('research_acceptance_result', 'promotion_status', 'STRING'),
  STRUCT('research_acceptance_result', 'promoted', 'BOOL'),
  STRUCT('research_acceptance_result', 'promotion_manifest_id', 'STRING'),
  STRUCT('research_acceptance_result', 'metrics_json', 'STRING'),
  STRUCT('research_acceptance_result', 'artifact_uri', 'STRING'),
  STRUCT('research_acceptance_result', 'created_date', 'DATE'),

  STRUCT('research_experiment_run_status', 'experiment_id', 'STRING'),
  STRUCT('research_experiment_run_status', 'run_id', 'STRING'),
  STRUCT('research_experiment_run_status', 'prediction_run_id', 'STRING'),
  STRUCT('research_experiment_run_status', 'backtest_id', 'STRING'),
  STRUCT('research_experiment_run_status', 'step_id', 'STRING'),
  STRUCT('research_experiment_run_status', 'status', 'STRING'),
  STRUCT('research_experiment_run_status', 'status_reason', 'STRING'),
  STRUCT('research_experiment_run_status', 'started_at', 'TIMESTAMP'),
  STRUCT('research_experiment_run_status', 'finished_at', 'TIMESTAMP'),
  STRUCT('research_experiment_run_status', 'created_date', 'DATE'),
  STRUCT('research_experiment_run_status', 'updated_date', 'DATE'),
  STRUCT('research_experiment_run_status', 'created_at', 'TIMESTAMP'),
  STRUCT('research_experiment_run_status', 'updated_at', 'TIMESTAMP'),
  STRUCT('research_experiment_run_status', 'artifact_uri', 'STRING'),
  STRUCT('research_experiment_run_status', 'report_uri', 'STRING'),
  STRUCT('research_experiment_run_status', 'diagnosis_uri', 'STRING'),
  STRUCT('research_experiment_run_status', 'qa_status', 'STRING'),
  STRUCT('research_experiment_run_status', 'manifest_path', 'STRING'),
  STRUCT('research_experiment_run_status', 'params_json', 'STRING'),
  STRUCT('research_experiment_run_status', 'runner_version', 'STRING'),
  STRUCT('research_experiment_run_status', 'scheduler_instance_id', 'STRING'),
  STRUCT('research_experiment_run_status', 'cloud_run_job_name', 'STRING'),
  STRUCT('research_experiment_run_status', 'cloud_run_execution_id', 'STRING'),
  STRUCT('research_experiment_run_status', 'container_image', 'STRING'),
  STRUCT('research_experiment_run_status', 'execution_backend', 'STRING'),
  STRUCT('research_experiment_run_status', 'model_artifact_uri', 'STRING'),
  STRUCT('research_experiment_run_status', 'preprocess_artifact_uri', 'STRING'),
  STRUCT('research_experiment_run_status', 'feature_snapshot_uri', 'STRING'),
  STRUCT('research_experiment_run_status', 'log_dir', 'STRING'),
  STRUCT('research_experiment_run_status', 'error_message', 'STRING'),

  STRUCT('research_promotion_manifest', 'promotion_id', 'STRING'),
  STRUCT('research_promotion_manifest', 'source_dataset', 'STRING'),
  STRUCT('research_promotion_manifest', 'source_run_id', 'STRING'),
  STRUCT('research_promotion_manifest', 'source_backtest_id', 'STRING'),
  STRUCT('research_promotion_manifest', 'source_model_id', 'STRING'),
  STRUCT('research_promotion_manifest', 'target_dataset', 'STRING'),
  STRUCT('research_promotion_manifest', 'target_ads_tables', 'ARRAY<STRING>'),
  STRUCT('research_promotion_manifest', 'acceptance_contract_version', 'STRING'),
  STRUCT('research_promotion_manifest', 'approval_ref', 'STRING'),
  STRUCT('research_promotion_manifest', 'approved_by', 'STRING'),
  STRUCT('research_promotion_manifest', 'approved_at', 'TIMESTAMP'),
  STRUCT('research_promotion_manifest', 'promotion_code_version', 'STRING'),
  STRUCT('research_promotion_manifest', 'promotion_status', 'STRING'),
  STRUCT('research_promotion_manifest', 'promoted_at', 'TIMESTAMP'),
  STRUCT('research_promotion_manifest', 'created_date', 'DATE')
];

SET expected_partitions = ARRAY<STRUCT<table_name STRING, column_name STRING>>[
  STRUCT('research_ml_training_panel_daily', 'trade_date'),
  STRUCT('research_model_registry', 'created_date'),
  STRUCT('research_model_prediction_daily', 'predict_date'),
  STRUCT('research_stock_candidate_daily', 'rebalance_date'),
  STRUCT('research_portfolio_target_daily', 'rebalance_date'),
  STRUCT('research_order_plan_daily', 'rebalance_date'),
  STRUCT('research_backtest_trade_daily', 'trade_date'),
  STRUCT('research_backtest_position_daily', 'trade_date'),
  STRUCT('research_backtest_nav_daily', 'trade_date'),
  STRUCT('research_backtest_ledger_state_daily', 'trade_date'),
  STRUCT('research_backtest_performance_summary', 'created_date'),
  STRUCT('research_signal_monitor_daily', 'trade_date'),
  STRUCT('research_acceptance_result', 'created_date'),
  STRUCT('research_experiment_run_status', 'updated_date'),
  STRUCT('research_promotion_manifest', 'created_date')
];

SET expected_clustering = ARRAY<STRUCT<table_name STRING, column_name STRING, ordinal_position INT64>>[
  STRUCT('research_ml_training_panel_daily', 'run_id', 1),
  STRUCT('research_ml_training_panel_daily', 'sec_code', 2),
  STRUCT('research_model_registry', 'strategy_id', 1),
  STRUCT('research_model_registry', 'model_id', 2),
  STRUCT('research_model_prediction_daily', 'model_id', 1),
  STRUCT('research_model_prediction_daily', 'sec_code', 2),
  STRUCT('research_stock_candidate_daily', 'strategy_id', 1),
  STRUCT('research_stock_candidate_daily', 'sec_code', 2),
  STRUCT('research_portfolio_target_daily', 'strategy_id', 1),
  STRUCT('research_portfolio_target_daily', 'sec_code', 2),
  STRUCT('research_order_plan_daily', 'strategy_id', 1),
  STRUCT('research_order_plan_daily', 'sec_code', 2),
  STRUCT('research_order_plan_daily', 'side', 3),
  STRUCT('research_backtest_trade_daily', 'backtest_id', 1),
  STRUCT('research_backtest_trade_daily', 'sec_code', 2),
  STRUCT('research_backtest_position_daily', 'backtest_id', 1),
  STRUCT('research_backtest_position_daily', 'sec_code', 2),
  STRUCT('research_backtest_nav_daily', 'backtest_id', 1),
  STRUCT('research_backtest_ledger_state_daily', 'backtest_id', 1),
  STRUCT('research_backtest_performance_summary', 'strategy_id', 1),
  STRUCT('research_backtest_performance_summary', 'model_id', 2),
  STRUCT('research_backtest_performance_summary', 'backtest_id', 3),
  STRUCT('research_signal_monitor_daily', 'strategy_id', 1),
  STRUCT('research_signal_monitor_daily', 'model_id', 2),
  STRUCT('research_acceptance_result', 'strategy_id', 1),
  STRUCT('research_acceptance_result', 'model_id', 2),
  STRUCT('research_acceptance_result', 'backtest_id', 3),
  STRUCT('research_experiment_run_status', 'experiment_id', 1),
  STRUCT('research_experiment_run_status', 'run_id', 2),
  STRUCT('research_experiment_run_status', 'step_id', 3),
  STRUCT('research_promotion_manifest', 'promotion_id', 1),
  STRUCT('research_promotion_manifest', 'source_model_id', 2)
];

SET expected_defaults = ARRAY<STRUCT<table_name STRING, column_name STRING, column_default STRING>>[
  STRUCT('research_ml_training_panel_daily', 'research_status', "'candidate'"),
  STRUCT('research_ml_training_panel_daily', 'promotion_status', "'not_promoted'"),
  STRUCT('research_model_registry', 'promotion_status', "'not_promoted'"),
  STRUCT('research_model_prediction_daily', 'research_status', "'candidate'"),
  STRUCT('research_model_prediction_daily', 'promotion_status', "'not_promoted'"),
  STRUCT('research_stock_candidate_daily', 'research_status', "'candidate'"),
  STRUCT('research_stock_candidate_daily', 'promotion_status', "'not_promoted'"),
  STRUCT('research_portfolio_target_daily', 'research_status', "'candidate'"),
  STRUCT('research_portfolio_target_daily', 'promotion_status', "'not_promoted'"),
  STRUCT('research_order_plan_daily', 'research_status', "'candidate'"),
  STRUCT('research_order_plan_daily', 'promotion_status', "'not_promoted'"),
  STRUCT('research_backtest_trade_daily', 'research_status', "'candidate'"),
  STRUCT('research_backtest_trade_daily', 'promotion_status', "'not_promoted'"),
  STRUCT('research_backtest_position_daily', 'research_status', "'candidate'"),
  STRUCT('research_backtest_position_daily', 'promotion_status', "'not_promoted'"),
  STRUCT('research_backtest_nav_daily', 'research_status', "'candidate'"),
  STRUCT('research_backtest_nav_daily', 'promotion_status', "'not_promoted'"),
  STRUCT('research_backtest_ledger_state_daily', 'research_status', "'candidate'"),
  STRUCT('research_backtest_ledger_state_daily', 'promotion_status', "'not_promoted'"),
  STRUCT('research_backtest_performance_summary', 'promotion_status', "'not_promoted'"),
  STRUCT('research_signal_monitor_daily', 'research_status', "'candidate'"),
  STRUCT('research_signal_monitor_daily', 'promotion_status', "'not_promoted'"),
  STRUCT('research_acceptance_result', 'promotion_status', "'not_promoted'"),
  STRUCT('research_promotion_manifest', 'promotion_status', "'planned'")
];

SET partition_filter_tables = [
  'research_ml_training_panel_daily',
  'research_model_prediction_daily',
  'research_stock_candidate_daily',
  'research_portfolio_target_daily',
  'research_order_plan_daily',
  'research_backtest_trade_daily',
  'research_backtest_position_daily',
  'research_backtest_nav_daily',
  'research_backtest_ledger_state_daily',
  'research_signal_monitor_daily'
];

ASSERT (
  SELECT COUNT(*) = ARRAY_LENGTH(required_tables)
  FROM `data-aquarium`.ashare_research.INFORMATION_SCHEMA.TABLES
  WHERE table_name IN UNNEST(required_tables)
) AS 'QA-RESEARCH-SCHEMA-1: required Strategy1 research tables are missing; run sql/research/01_research_strategy1_tables.sql first';

ASSERT (
  SELECT COUNT(*) = ARRAY_LENGTH(required_columns)
  FROM UNNEST(required_columns) AS req
  JOIN `data-aquarium`.ashare_research.INFORMATION_SCHEMA.COLUMNS AS col
    ON col.table_name = req.table_name
   AND col.column_name = req.column_name
   AND col.data_type = req.data_type
) AS 'QA-RESEARCH-SCHEMA-2: required research columns or types are missing; run sql/research/02_research_strategy1_additive_migrations.sql and re-check the contract';

ASSERT (
  SELECT COUNT(*) = ARRAY_LENGTH(expected_partitions)
  FROM UNNEST(expected_partitions) AS req
  JOIN `data-aquarium`.ashare_research.INFORMATION_SCHEMA.COLUMNS AS col
    ON col.table_name = req.table_name
   AND col.column_name = req.column_name
   AND col.is_partitioning_column = 'YES'
) AS 'QA-RESEARCH-SCHEMA-3: research tables must use the expected monthly partition columns';

ASSERT (
  SELECT COUNT(*) = ARRAY_LENGTH(expected_clustering)
  FROM UNNEST(expected_clustering) AS req
  JOIN `data-aquarium`.ashare_research.INFORMATION_SCHEMA.COLUMNS AS col
    ON col.table_name = req.table_name
   AND col.column_name = req.column_name
   AND col.clustering_ordinal_position = req.ordinal_position
) AS 'QA-RESEARCH-SCHEMA-4: research tables must keep expected clustering columns and order';

ASSERT (
  SELECT COUNT(*) = ARRAY_LENGTH(expected_defaults)
  FROM UNNEST(expected_defaults) AS req
  JOIN `data-aquarium`.ashare_research.INFORMATION_SCHEMA.COLUMNS AS col
    ON col.table_name = req.table_name
   AND col.column_name = req.column_name
   AND col.column_default = req.column_default
) AS 'QA-RESEARCH-SCHEMA-5: research lifecycle columns must keep explicit DEFAULT values';

ASSERT (
  SELECT COUNT(*) = ARRAY_LENGTH(partition_filter_tables)
  FROM `data-aquarium`.ashare_research.INFORMATION_SCHEMA.TABLE_OPTIONS
  WHERE table_name IN UNNEST(partition_filter_tables)
    AND option_name = 'require_partition_filter'
    AND option_value = 'true'
) AS 'QA-RESEARCH-SCHEMA-6: partitioned daily research tables must require partition filters';

ASSERT (
  SELECT COUNT(*) = 1
  FROM `data-aquarium`.ashare_research.INFORMATION_SCHEMA.COLUMNS
  WHERE table_name = 'research_experiment_run_status'
    AND column_name = 'log_dir'
    AND data_type = 'STRING'
) AS 'QA-RESEARCH-SCHEMA-7: research_experiment_run_status.log_dir must exist; apply additive migration 02';
