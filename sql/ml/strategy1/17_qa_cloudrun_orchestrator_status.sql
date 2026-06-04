-- BigQuery Standard SQL · Strategy 1 Cloud Run Runner
-- 17: Cloud Run orchestrator status/lock QA.

DECLARE p_experiment_id STRING DEFAULT 'oq010_a0_n5_w20';
DECLARE p_run_id STRING DEFAULT 's1_cloudrun_sklearn_smoke_20260604_01';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_cloudrun_sklearn_smoke_20260604_01';
DECLARE p_require_train_step BOOL DEFAULT TRUE;
DECLARE p_require_backtest_step BOOL DEFAULT TRUE;
DECLARE p_expected_execution_backend STRING DEFAULT 'cloud_run_sklearn_ledger_v1';

-- QA-CRO-1: no failed/cancelled status rows for the experiment/run.
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status`
  WHERE experiment_id = p_experiment_id
    AND run_id = p_run_id
    AND status IN ('failed', 'cancelled')
) AS 'QA-CRO-1: Cloud Run orchestrator must not leave failed/cancelled rows for this run';

-- QA-CRO-2: train/predict step is terminal succeeded when required.
ASSERT (
  SELECT
    NOT p_require_train_step
    OR (
      COUNT(*) = 1
      AND LOGICAL_AND(status = 'succeeded')
      AND LOGICAL_AND(lock_key = CONCAT('cloudrun:train:', prediction_run_id))
      AND LOGICAL_AND(lock_owner IS NOT NULL AND lock_owner != '')
      AND LOGICAL_AND(lock_acquired_at IS NOT NULL)
      AND LOGICAL_AND(lock_expires_at IS NOT NULL)
      AND LOGICAL_AND(scheduler_instance_id IS NOT NULL AND scheduler_instance_id != '')
      AND LOGICAL_AND(JSON_VALUE(params_json, '$.execution_backend') = p_expected_execution_backend)
    )
  FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status`
  WHERE experiment_id = p_experiment_id
    AND run_id = p_run_id
    AND step_id = 'cloudrun_train_predict'
) AS 'QA-CRO-2: train/predict status row must be succeeded with lock metadata';

-- QA-CRO-3: backtest/report step is terminal succeeded when required.
ASSERT (
  SELECT
    NOT p_require_backtest_step
    OR (
      COUNT(*) = 1
      AND LOGICAL_AND(status = 'succeeded')
      AND LOGICAL_AND(backtest_id = p_backtest_id)
      AND LOGICAL_AND(lock_key = CONCAT('cloudrun:backtest:', p_backtest_id))
      AND LOGICAL_AND(lock_owner IS NOT NULL AND lock_owner != '')
      AND LOGICAL_AND(lock_acquired_at IS NOT NULL)
      AND LOGICAL_AND(lock_expires_at IS NOT NULL)
      AND LOGICAL_AND(scheduler_instance_id IS NOT NULL AND scheduler_instance_id != '')
      AND LOGICAL_AND(JSON_VALUE(params_json, '$.execution_backend') = p_expected_execution_backend)
    )
  FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status`
  WHERE experiment_id = p_experiment_id
    AND run_id = p_run_id
    AND step_id = 'cloudrun_backtest_report'
) AS 'QA-CRO-3: backtest/report status row must be succeeded with lock metadata';

-- QA-CRO-4: no active duplicate Cloud Run status rows for the same run/step.
ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT step_id
    FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status`
    WHERE run_id = p_run_id
      AND step_id IN ('cloudrun_train_predict', 'cloudrun_backtest_report')
      AND status = 'running'
    GROUP BY step_id
    HAVING COUNT(*) > 1
  )
) AS 'QA-CRO-4: no duplicate running Cloud Run status rows for same run/step';

-- QA-CRO-5: succeeded Cloud Run rows must preserve manifest/runner audit metadata.
ASSERT (
  SELECT COUNT(*) > 0
    AND COUNTIF(manifest_path IS NULL OR manifest_path = '') = 0
    AND COUNTIF(manifest_hash IS NULL OR manifest_hash = '') = 0
    AND COUNTIF(runner_version IS NULL OR runner_version = '') = 0
    AND COUNTIF(params_json IS NULL OR params_json = '') = 0
  FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status`
  WHERE experiment_id = p_experiment_id
    AND run_id = p_run_id
    AND step_id IN ('cloudrun_train_predict', 'cloudrun_backtest_report')
    AND status = 'succeeded'
) AS 'QA-CRO-5: succeeded Cloud Run status rows must preserve audit metadata';
