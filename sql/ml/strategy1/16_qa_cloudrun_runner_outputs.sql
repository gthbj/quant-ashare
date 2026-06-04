-- BigQuery Standard SQL · Strategy 1 Cloud Run Runner
-- 16: Cloud Run sklearn runner QA.

DECLARE p_run_id STRING DEFAULT 's1_cloudrun_sklearn_smoke_20260604_01';
DECLARE p_prediction_run_id STRING DEFAULT NULL;
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_cloudrun_sklearn_smoke_20260604_01';
DECLARE p_predict_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_predict_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_expected_execution_backend STRING DEFAULT 'cloud_run_sklearn_ledger_v1';
DECLARE p_expected_executable_experiment_count INT64 DEFAULT NULL;
DECLARE p_resolved_max_parallel_experiments INT64 DEFAULT NULL;

SET p_prediction_run_id = COALESCE(p_prediction_run_id, p_run_id);

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
        WHEN score_orientation = 'identity' THEN ABS(score - raw_score) > 1e-9
        WHEN score_orientation = 'reverse_probability' THEN ABS(score - (1.0 - raw_score)) > 1e-9
        ELSE TRUE
      END
    ) = 0
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily`
  WHERE run_id = p_prediction_run_id
    AND predict_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-CR-3: prediction raw_score/score/score_orientation must be complete and consistent';

-- QA-CR-4: model-quality parity status is present and internally consistent.
ASSERT (
  SELECT COUNT(*) = 1
    AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.model_quality_parity_status') IN ('passed', 'failed', 'warning'))
    AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.bqml_reference_run_id') IS NOT NULL)
    AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.sklearn_oriented_valid_rank_ic_mean') IS NOT NULL)
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_prediction_run_id
) AS 'QA-CR-4: selected model must record sklearn vs BQML model-quality parity evidence';

-- QA-CR-5: summary records Cloud Run backend.
ASSERT (
  SELECT COUNT(*) = 1
    AND LOGICAL_AND(JSON_VALUE(bs.metrics_json, '$.execution_backend') = p_expected_execution_backend)
    AND LOGICAL_AND(JSON_VALUE(bs.metrics_json, '$.ledger_version') = 'ledger_exec_v1')
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-CR-5: backtest summary must record Cloud Run backend and ledger_exec_v1';

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
