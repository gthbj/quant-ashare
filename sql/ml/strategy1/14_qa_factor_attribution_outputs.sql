-- BigQuery Standard SQL · Strategy 1 Factor Attribution QA
-- 14: 断言 factor attribution artifact 状态、manifest、coverage 和路径语义。
-- 必须在 scripts/strategy1/attribute_factor_contribution.py 之后执行。

DECLARE p_run_id STRING DEFAULT 's1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01';
DECLARE p_prediction_run_id STRING DEFAULT NULL;  -- NULL 表示因子归因使用 p_run_id 对应的模型/预测
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01';
DECLARE p_selected_model_path STRING;

SET p_prediction_run_id = COALESCE(p_prediction_run_id, p_run_id);

SET p_selected_model_path = (
  SELECT REGEXP_REPLACE(reg.model_uri, r'^bq://', '')
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_prediction_run_id
  ORDER BY reg.created_at DESC
  LIMIT 1
);

IF p_selected_model_path IS NULL THEN
  RAISE USING MESSAGE = CONCAT('no selected model for p_prediction_run_id ', p_prediction_run_id);
END IF;

EXECUTE IMMEDIATE FORMAT("""
  CREATE TEMP TABLE selected_weights AS
  SELECT processed_input
  FROM ML.WEIGHTS(MODEL `%s`)
""", p_selected_model_path);

CREATE TEMP TABLE summary_metrics AS
SELECT
  bs.backtest_id,
  PARSE_JSON(COALESCE(bs.metrics_json, '{}'), wide_number_mode => 'round') AS metrics
FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
WHERE bs.backtest_id = p_backtest_id;

-- QA-FACTOR-1: factor_attribution status/version completed
ASSERT (
  SELECT COUNT(*) = 1
     AND LOGICAL_AND(JSON_VALUE(metrics, '$.factor_attribution_status') = 'completed')
     AND LOGICAL_AND(JSON_VALUE(metrics, '$.factor_attribution_version') = 'strategy1_factor_attribution_v1')
  FROM summary_metrics
) AS 'QA-FACTOR-1: factor_attribution_status/version must be completed/v1';

-- QA-FACTOR-2: attribution prediction source recorded
ASSERT (
  SELECT COUNT(*) = 1
     AND LOGICAL_AND(JSON_VALUE(metrics, '$.factor_attribution_prediction_run_id') = p_prediction_run_id)
     AND LOGICAL_AND(JSON_VALUE(metrics, '$.factor_attribution_model_id') IS NOT NULL)
  FROM summary_metrics
) AS 'QA-FACTOR-2: factor attribution must record prediction_run_id and model_id';

-- QA-FACTOR-3: artifact manifest contains all required files
ASSERT (
  SELECT COUNT(*) = 1 AND COUNTIF(missing) = 0
  FROM (
    SELECT
      JSON_QUERY(JSON_QUERY(metrics, '$.factor_attribution_artifact_manifest'), '$."factor_attribution.md"') IS NULL
      OR JSON_QUERY(JSON_QUERY(metrics, '$.factor_attribution_artifact_manifest'), '$."factor_attribution_summary.json"') IS NULL
      OR JSON_QUERY(JSON_QUERY(metrics, '$.factor_attribution_artifact_manifest'), '$."factor_model_weights.csv"') IS NULL
      OR JSON_QUERY(JSON_QUERY(metrics, '$.factor_attribution_artifact_manifest'), '$."factor_rank_ic_daily.csv"') IS NULL
      OR JSON_QUERY(JSON_QUERY(metrics, '$.factor_attribution_artifact_manifest'), '$."factor_rank_ic_summary.csv"') IS NULL
      OR JSON_QUERY(JSON_QUERY(metrics, '$.factor_attribution_artifact_manifest'), '$."factor_bucket_lift_summary.csv"') IS NULL
      OR JSON_QUERY(JSON_QUERY(metrics, '$.factor_attribution_artifact_manifest'), '$."factor_score_contribution_summary.csv"') IS NULL
      OR JSON_QUERY(JSON_QUERY(metrics, '$.factor_attribution_artifact_manifest'), '$."portfolio_factor_exposure_daily.csv"') IS NULL
      OR JSON_QUERY(JSON_QUERY(metrics, '$.factor_attribution_artifact_manifest'), '$."portfolio_factor_attribution_proxy.csv"') IS NULL
      OR JSON_QUERY(JSON_QUERY(metrics, '$.factor_attribution_artifact_manifest'), '$."factor_group_summary.csv"') IS NULL
      OR JSON_QUERY(JSON_QUERY(metrics, '$.factor_attribution_artifact_manifest'), '$."factor_correlation_summary.csv"') IS NULL
      OR JSON_QUERY(JSON_QUERY(metrics, '$.factor_attribution_artifact_manifest'), '$."artifact_manifest.json"') IS NULL
      AS missing
    FROM summary_metrics
  )
) AS 'QA-FACTOR-3: factor attribution manifest must contain all required artifacts';

-- QA-FACTOR-4: selected model non-intercept features covered by output
ASSERT (
  SELECT
    SAFE_CAST(JSON_VALUE(metrics, '$.factor_model_feature_count') AS INT64)
      = (SELECT COUNTIF(processed_input != '__INTERCEPT__') FROM selected_weights)
    AND SAFE_CAST(JSON_VALUE(metrics, '$.factor_model_feature_coverage_count') AS INT64)
      = (SELECT COUNTIF(processed_input != '__INTERCEPT__') FROM selected_weights)
  FROM summary_metrics
) AS 'QA-FACTOR-4: factor_model_weights must cover all selected model non-intercept features';

-- QA-FACTOR-5: feature group mapping complete
ASSERT (
  SELECT COUNT(*) = 1
     AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(metrics, '$.factor_unknown_group_count') AS INT64) = 0)
     AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(metrics, '$.factor_group_count') AS INT64) > 0)
  FROM summary_metrics
) AS 'QA-FACTOR-5: all model features must have factor group mapping';

-- QA-FACTOR-6: valid/test rank IC summary non-empty
ASSERT (
  SELECT COUNT(*) = 1
     AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(metrics, '$.factor_rank_ic_valid_rows') AS INT64) > 0)
     AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(metrics, '$.factor_rank_ic_test_rows') AS INT64) > 0)
  FROM summary_metrics
) AS 'QA-FACTOR-6: valid/test factor_rank_ic_summary must be non-empty';

-- QA-FACTOR-7: score contribution contains all required groups
ASSERT (
  SELECT COUNT(*) = 1
     AND LOGICAL_AND('all_predictions' IN UNNEST(IFNULL(JSON_VALUE_ARRAY(metrics, '$.factor_score_contribution_groups'), ARRAY<STRING>[])))
     AND LOGICAL_AND('top_30pct' IN UNNEST(IFNULL(JSON_VALUE_ARRAY(metrics, '$.factor_score_contribution_groups'), ARRAY<STRING>[])))
     AND LOGICAL_AND('bottom_30pct' IN UNNEST(IFNULL(JSON_VALUE_ARRAY(metrics, '$.factor_score_contribution_groups'), ARRAY<STRING>[])))
     AND LOGICAL_AND('selected_candidate' IN UNNEST(IFNULL(JSON_VALUE_ARRAY(metrics, '$.factor_score_contribution_groups'), ARRAY<STRING>[])))
     AND LOGICAL_AND('held_position' IN UNNEST(IFNULL(JSON_VALUE_ARRAY(metrics, '$.factor_score_contribution_groups'), ARRAY<STRING>[])))
  FROM summary_metrics
) AS 'QA-FACTOR-7: factor_score_contribution_summary must include all required groups';

-- QA-FACTOR-8: exposure covers holding days
ASSERT (
  SELECT COUNT(*) = 1
     AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(metrics, '$.factor_portfolio_exposure_days') AS INT64)
       >= SAFE_CAST(JSON_VALUE(metrics, '$.factor_position_holding_days') AS INT64))
     AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(metrics, '$.factor_position_holding_days') AS INT64) > 0)
  FROM summary_metrics
) AS 'QA-FACTOR-8: portfolio factor exposure must cover position holding days';

-- QA-FACTOR-9: local-only / uploaded path semantics
ASSERT (
  SELECT COUNT(*) = 1 AND LOGICAL_AND(
    (
      JSON_VALUE(metrics, '$.factor_attribution_upload_status') = 'uploaded'
      AND STARTS_WITH(JSON_VALUE(metrics, '$.factor_attribution_uri'), 'gs://')
      AND JSON_VALUE(metrics, '$.local_factor_attribution_path') IS NOT NULL
    )
    OR (
      JSON_VALUE(metrics, '$.factor_attribution_upload_status') = 'skipped'
      AND JSON_VALUE(metrics, '$.factor_attribution_uri') IS NULL
      AND JSON_VALUE(metrics, '$.local_factor_attribution_path') IS NOT NULL
    )
  )
  FROM summary_metrics
) AS 'QA-FACTOR-9: uploaded/local-only URI semantics must be valid';

-- QA-FACTOR-10: correlation summary exists and contains group summaries
ASSERT (
  SELECT COUNT(*) = 1
     AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(metrics, '$.factor_correlation_summary_rows') AS INT64) > 0)
     AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(metrics, '$.factor_correlation_group_summary_rows') AS INT64)
       >= SAFE_CAST(JSON_VALUE(metrics, '$.factor_group_count') AS INT64))
  FROM summary_metrics
) AS 'QA-FACTOR-10: factor correlation summary and group summaries must exist';

-- QA-FACTOR-11: markdown limitations included
ASSERT (
  SELECT COUNT(*) = 1
     AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(metrics, '$.factor_attribution_limitations_included') AS BOOL))
  FROM summary_metrics
) AS 'QA-FACTOR-11: factor attribution limitations must be included';

-- QA-FACTOR-12: no ablation/drop-feature fields
ASSERT (
  SELECT COUNT(*) = 1
     AND LOGICAL_AND(JSON_VALUE(metrics, '$.drop_feature_run_id') IS NULL)
     AND LOGICAL_AND(JSON_VALUE(metrics, '$.ablation_run_id') IS NULL)
     AND LOGICAL_AND(JSON_VALUE(metrics, '$.drop_feature_group_run_id') IS NULL)
  FROM summary_metrics
) AS 'QA-FACTOR-12: factor attribution must not write ablation/drop-feature fields';

SELECT
  'QA-FACTOR: all assertions passed' AS status,
  p_run_id AS run_id,
  p_prediction_run_id AS prediction_run_id,
  p_backtest_id AS backtest_id;
