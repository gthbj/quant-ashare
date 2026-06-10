-- BigQuery Standard SQL
-- Strategy1 annual rolling final-refit QA.

DECLARE p_run_id STRING DEFAULT 's1_annual_roll_unit__refit01';
DECLARE p_source_run_id STRING DEFAULT 's1_annual_roll_unit';
DECLARE p_source_panel_run_id STRING DEFAULT 's1_annual_roll_unit';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_refit_train_start DATE DEFAULT DATE '2021-01-04';
DECLARE p_refit_train_end DATE DEFAULT DATE '2025-12-24';
DECLARE p_predict_start DATE DEFAULT DATE '2026-01-05';
DECLARE p_predict_end DATE DEFAULT DATE '2026-06-09';

ASSERT (
  SELECT COUNT(*) = 1
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_source_run_id
) AS 'QA-REFIT-1: source selection run must have exactly one selected registry row';

ASSERT (
  SELECT COUNT(*) = 1
    AND LOGICAL_AND(reg.train_start_date = p_refit_train_start)
    AND LOGICAL_AND(reg.train_end_date = p_refit_train_end)
    AND LOGICAL_AND(JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id)
    AND LOGICAL_AND(JSON_VALUE(reg.model_params_json, '$.source_run_id') = p_source_run_id)
    AND LOGICAL_AND(JSON_VALUE(reg.model_params_json, '$.source_panel_run_id') = p_source_panel_run_id)
    AND LOGICAL_AND(JSON_VALUE(reg.model_params_json, '$.refit') = 'true')
    AND LOGICAL_AND(JSON_VALUE(reg.model_params_json, '$.refit_train_start') = CAST(p_refit_train_start AS STRING))
    AND LOGICAL_AND(JSON_VALUE(reg.model_params_json, '$.refit_train_end') = CAST(p_refit_train_end AS STRING))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
) AS 'QA-REFIT-2: refit registry must be single selected row with exact resolved window and source lineage';

ASSERT (
  SELECT COUNT(*) > 0
    AND MIN(tp.trade_date) <= p_refit_train_start
    AND MAX(tp.trade_date) >= p_predict_end
    AND COUNTIF(tp.trade_date BETWEEN p_refit_train_start AND p_refit_train_end AND tp.target_label IS NOT NULL) > 0
  FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
  WHERE tp.run_id = p_source_panel_run_id
    AND tp.trade_date BETWEEN p_refit_train_start AND p_predict_end
) AS 'QA-REFIT-3: source panel must cover refit train and prediction windows';

ASSERT (
  SELECT COUNT(*) > 0
    AND MIN(pred.predict_date) = p_predict_start
    AND MAX(pred.predict_date) = p_predict_end
    AND COUNTIF(pred.run_id != p_run_id) = 0
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  WHERE pred.run_id = p_run_id
    AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-REFIT-4: refit predictions must cover the exact predict window';

ASSERT (
  SELECT COUNT(*) = 1
    AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.selected_candidate_id') IS NOT NULL)
    AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.source_run_id') = p_source_run_id)
    AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.source_panel_run_id') = p_source_panel_run_id)
    AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.preprocess_fit_start') = CAST(p_refit_train_start AS STRING))
    AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.preprocess_fit_end') = CAST(p_refit_train_end AS STRING))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
) AS 'QA-REFIT-5: refit metrics_json must preserve selected candidate, source panel, and preprocess fit lineage';

ASSERT (
  SELECT COUNT(*) = 1
    AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.preprocess_artifact_uri') LIKE CONCAT('%/run_id=', p_run_id, '/%/preprocess.joblib'))
    AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.preprocess_stats_uri') LIKE CONCAT('%/run_id=', p_run_id, '/%/preprocess_stats.json'))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
) AS 'QA-REFIT-6: refit preprocess artifacts must belong to the refit run';
