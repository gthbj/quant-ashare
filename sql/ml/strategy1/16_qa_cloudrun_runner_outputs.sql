-- BigQuery Standard SQL · Strategy 1 Cloud Run Runner
-- 16: Cloud Run sklearn runner QA.

DECLARE p_run_id STRING DEFAULT 's1_cloudrun_sklearn_smoke_20260604_01';
DECLARE p_prediction_run_id STRING DEFAULT NULL;
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_cloudrun_sklearn_smoke_20260604_01';
DECLARE p_predict_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_predict_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_expected_execution_backend STRING DEFAULT 'cloud_run_sklearn_ledger_v1_lot100';
DECLARE p_expected_ledger_version STRING DEFAULT 'ledger_exec_v1_lot100';
DECLARE p_expected_ledger_executor STRING DEFAULT 'cloud_run_python';
DECLARE p_expected_executable_experiment_count INT64 DEFAULT NULL;
DECLARE p_resolved_max_parallel_experiments INT64 DEFAULT NULL;
DECLARE p_require_model_quality_parity_passed BOOL DEFAULT TRUE;
DECLARE p_require_task_fanout BOOL DEFAULT FALSE;
DECLARE p_candidate_task_bq_audit_window_days INT64 DEFAULT 14;
DECLARE p_candidate_task_max_bq_bytes INT64 DEFAULT 0;
DECLARE p_prediction_run_id_label STRING DEFAULT NULL;

SET p_prediction_run_id = COALESCE(p_prediction_run_id, p_run_id);
SET p_prediction_run_id_label = COALESCE(NULLIF(
  REGEXP_REPLACE(
    SUBSTR(REGEXP_REPLACE(LOWER(p_prediction_run_id), r'[^a-z0-9_-]', '_'), 1, 63),
    r'^[_-]+|[_-]+$',
    ''
  ),
  ''
), 'none');

-- QA-CR-1: selected sklearn model registry exists and is explicitly tagged as Cloud Run backend.
ASSERT (
  SELECT COUNT(*) = 1
    AND LOGICAL_AND(JSON_VALUE(reg.model_params_json, '$.execution_backend') = p_expected_execution_backend)
    AND LOGICAL_AND(reg.model_family = 'sklearn_logistic_regression')
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_prediction_run_id
) AS 'QA-CR-1: selected model must be sklearn and tagged with cloud_run_sklearn_ledger_v1';

-- QA-CR-2: selected model has GCS model/preprocess artifacts.
ASSERT (
  SELECT COUNT(*) = 1
    AND LOGICAL_AND(STARTS_WITH(reg.model_uri, 'gs://'))
    AND LOGICAL_AND(STARTS_WITH(JSON_VALUE(reg.metrics_json, '$.model_artifact_uri'), 'gs://'))
    AND LOGICAL_AND(STARTS_WITH(JSON_VALUE(reg.metrics_json, '$.preprocess_artifact_uri'), 'gs://'))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_prediction_run_id
) AS 'QA-CR-2: selected model must record GCS model/preprocess artifacts';

-- QA-CR-3: prediction scores are complete and orientation-consistent.
ASSERT (
  SELECT COUNT(*) > 0
    AND COUNTIF(raw_score IS NULL OR score IS NULL OR score_orientation IS NULL) = 0
    AND COUNTIF(
      CASE
        WHEN score_orientation = 'identity' THEN ABS(score - raw_score) > 1e-6
        WHEN score_orientation = 'reverse_probability' THEN ABS(score - (1.0 - raw_score)) > 1e-6
        ELSE TRUE
      END
    ) = 0
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily`
  WHERE run_id = p_prediction_run_id
    AND predict_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-CR-3: prediction raw_score/score/score_orientation must be complete and consistent';

-- QA-CR-4: model-quality parity evidence is present and passed when required.
ASSERT (
  SELECT COUNT(*) = 1
    AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.model_quality_parity_status') IN ('passed', 'warning', 'failed'))
    AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.model_quality_status') IN ('model_quality_equivalent', 'model_quality_not_equivalent'))
    AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.bqml_reference_run_id') IS NOT NULL)
    AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.sklearn_oriented_valid_rank_ic_mean') IS NOT NULL)
    AND LOGICAL_AND(
      NOT p_require_model_quality_parity_passed
      OR JSON_VALUE(reg.metrics_json, '$.model_quality_parity_status') = 'passed'
    )
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_prediction_run_id
 ) AS 'QA-CR-4: selected model must record sklearn vs BQML model-quality parity evidence and pass when required';

-- QA-CR-5: summary records the expected backend and ledger implementation.
ASSERT (
  SELECT COUNT(*) = 1
    AND LOGICAL_AND(JSON_VALUE(bs.metrics_json, '$.execution_backend') = p_expected_execution_backend)
    AND LOGICAL_AND(JSON_VALUE(bs.metrics_json, '$.ledger_version') = p_expected_ledger_version)
    AND LOGICAL_AND(JSON_VALUE(bs.metrics_json, '$.ledger_executor') = p_expected_ledger_executor)
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-CR-5: backtest summary must record expected backend and ledger executor';

-- QA-CR-6: no ADS串号 for this run/backtest.
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
  WHERE nav.backtest_id = p_backtest_id
    AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
    AND nav.run_id != p_run_id
) AS 'QA-CR-6: nav rows must not mix run_id across backtest_id';

-- QA-CR-7: default full-concurrency contract, when caller provides expected counts.
ASSERT (
  SELECT
    p_expected_executable_experiment_count IS NULL
    OR p_resolved_max_parallel_experiments IS NULL
    OR p_expected_executable_experiment_count = p_resolved_max_parallel_experiments
) AS 'QA-CR-7: unresolved max_parallel must resolve to executable experiment count';

-- QA-CR-8: task fan-out registry metrics are complete when the task fan-out path is required.
ASSERT (
  SELECT
    NOT p_require_task_fanout
    OR (
      COUNT(*) = 1
      AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.task_fanout_mode') = 'task_fanout')
      AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.matrix_id') IS NOT NULL)
      AND LOGICAL_AND(STARTS_WITH(JSON_VALUE(reg.metrics_json, '$.matrix_uri'), 'gs://'))
      AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.feature_order_sha256') IS NOT NULL)
      AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.preprocess_stats_sha256') IS NOT NULL)
      AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.work_units_sha256') IS NOT NULL)
      AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.work_unit_count') AS INT64) > 0)
      AND LOGICAL_AND(
        SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.succeeded_task_count') AS INT64)
        = SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.work_unit_count') AS INT64)
      )
      AND LOGICAL_AND(
        SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.candidate_parallelism_resolved') AS INT64)
        BETWEEN 1 AND SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.work_unit_count') AS INT64)
      )
      AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.candidate_task_bq_job_count') AS INT64) >= 0)
      AND LOGICAL_AND(
        SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.candidate_task_bq_forbidden_table_query_count') AS INT64) = 0
      )
    )
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_prediction_run_id
) AS 'QA-CR-8: task fan-out selected model must record complete matrix/work-unit audit metrics';

-- QA-CR-9: candidate task BigQuery usage audit must not show forbidden full-panel scans.
ASSERT (
  SELECT
    NOT p_require_task_fanout
    OR COUNT(*) = 0
  FROM `data-aquarium.region-asia-east2.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
  WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL p_candidate_task_bq_audit_window_days DAY)
    AND EXISTS (
      SELECT 1
      FROM UNNEST(labels) AS label
      WHERE label.key = 'pipeline_component'
        AND label.value = 'strategy1_cloudrun'
    )
    AND EXISTS (
      SELECT 1
      FROM UNNEST(labels) AS label
      WHERE label.key = 'pipeline_step'
        AND label.value = 'train_candidate_task'
    )
    AND EXISTS (
      SELECT 1
      FROM UNNEST(labels) AS label
      WHERE label.key = 'run_id'
        AND label.value = p_prediction_run_id_label
    )
    AND (
      IFNULL(total_bytes_processed, 0) > p_candidate_task_max_bq_bytes
      OR EXISTS (
        SELECT 1
        FROM UNNEST(IFNULL(
          referenced_tables,
          ARRAY<STRUCT<project_id STRING, dataset_id STRING, table_id STRING>>[]
        )) AS ref
        WHERE FORMAT('%s.%s.%s', ref.project_id, ref.dataset_id, ref.table_id) IN (
          'data-aquarium.ashare_ads.ads_ml_training_panel_daily',
          'data-aquarium.ashare_dws.dws_stock_sample_daily'
        )
      )
    )
) AS 'QA-CR-9: task fan-out candidate tasks must not scan forbidden BigQuery training tables';
