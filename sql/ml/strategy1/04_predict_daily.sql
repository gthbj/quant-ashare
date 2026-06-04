-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 04: 用 selected model 对 valid+test 预测，写 ads_model_prediction_daily。
-- 动态引用 selected model（EXECUTE IMMEDIATE），不依赖跨脚本临时表。
-- PRD-20260602-05: 预测输入来自 ads_ml_training_panel_daily（已按 live-available mask 构建），
-- 不引用 target_label / target_return / label_entry_tradable / label_valid_* / sample_trainable_default。
-- Score orientation: 从 registry metrics_json 读取 score_orientation，应用到最终 score。

DECLARE p_run_id STRING DEFAULT 's1_bqml_livepool_oriented_20260603_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_feature_set_id STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_label_horizon INT64 DEFAULT 5;
DECLARE p_valid_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_test_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_force_replace BOOL DEFAULT FALSE;
DECLARE p_selected_model_id STRING;
DECLARE p_selected_model_path STRING;
DECLARE p_score_orientation STRING;
DECLARE p_feat_sql STRING;

IF p_label_horizon NOT IN (5, 10, 20) THEN
  RAISE USING MESSAGE = 'p_label_horizon must be one of 5, 10, 20';
END IF;

IF p_feature_set_id NOT IN ('strategy1_pv_v0_20260601', 'strategy1_pv_fin_quality_v0_20260603') THEN
  RAISE USING MESSAGE = CONCAT('unsupported p_feature_set_id: ', p_feature_set_id);
END IF;

-- selected model（run-scoped）
SET (p_selected_model_id, p_selected_model_path) = (
  SELECT AS STRUCT reg.model_id, REPLACE(reg.model_uri, 'bq://', '')
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
  ORDER BY reg.created_at DESC LIMIT 1
);

IF p_selected_model_id IS NULL THEN
  RAISE USING MESSAGE = 'No selected model for this run_id. Run 03 first.';
END IF;

-- Read score_orientation from registry metrics_json (set by 03).
-- PRD requires failure if orientation is missing — no COALESCE fallback.
SET p_score_orientation = (
  SELECT JSON_VALUE(reg.metrics_json, '$.score_orientation')
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.model_id = p_selected_model_id
    AND reg.strategy_id = p_strategy_id
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
  LIMIT 1
);

IF p_score_orientation IS NULL OR p_score_orientation NOT IN ('identity', 'reverse_probability') THEN
  RAISE USING MESSAGE = CONCAT('score_orientation missing or invalid: ', COALESCE(p_score_orientation, 'NULL'),
                                '. Run 03 must set score_orientation in registry metrics_json.');
END IF;

-- 幂等
IF p_force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  WHERE pred.run_id = p_run_id
    AND pred.predict_date BETWEEN p_valid_start AND p_test_end;
ELSE
  IF (SELECT COUNT(*) > 0
      FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
      WHERE pred.run_id = p_run_id
        AND pred.predict_date BETWEEN p_valid_start AND p_test_end) THEN
    RAISE USING MESSAGE = CONCAT('Predictions exist for run_id=', p_run_id);
  END IF;
END IF;

SET p_feat_sql = """
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.list_age_td') AS FLOAT64) AS list_age_td,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ret_1d') AS FLOAT64) AS ret_1d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ret_3d') AS FLOAT64) AS ret_3d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ret_5d') AS FLOAT64) AS ret_5d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ret_10d') AS FLOAT64) AS ret_10d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ret_20d') AS FLOAT64) AS ret_20d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ret_60d') AS FLOAT64) AS ret_60d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.mom_20_5') AS FLOAT64) AS mom_20_5,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.mom_60_20') AS FLOAT64) AS mom_60_20,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.vol_5d') AS FLOAT64) AS vol_5d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.vol_20d') AS FLOAT64) AS vol_20d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.vol_60d') AS FLOAT64) AS vol_60d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.drawdown_20d') AS FLOAT64) AS drawdown_20d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.hl_range_20d') AS FLOAT64) AS hl_range_20d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.amount_ma20_cny') AS FLOAT64) AS amount_ma20_cny,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.amount_zscore_20d') AS FLOAT64) AS amount_zscore_20d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.turnover_rate') AS FLOAT64) AS turnover_rate,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.turnover_rate_free_float') AS FLOAT64) AS turnover_rate_free_float,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.turnover_rate_ma20') AS FLOAT64) AS turnover_rate_ma20,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.volume_ratio') AS FLOAT64) AS volume_ratio,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.pe_ttm') AS FLOAT64) AS pe_ttm,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.pb') AS FLOAT64) AS pb,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ps_ttm') AS FLOAT64) AS ps_ttm,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.dividend_yield_ttm') AS FLOAT64) AS dividend_yield_ttm,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ep_ttm') AS FLOAT64) AS ep_ttm,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.bp') AS FLOAT64) AS bp,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.sp_ttm') AS FLOAT64) AS sp_ttm,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.log_total_mv') AS FLOAT64) AS log_total_mv,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.log_circ_mv') AS FLOAT64) AS log_circ_mv
""";

IF p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603' THEN
  SET p_feat_sql = CONCAT(p_feat_sql, """,
  CAST(SAFE_CAST(JSON_VALUE(feature_values_json,'$.has_fin_indicator') AS BOOL) AS INT64) AS has_fin_indicator,
  CAST(SAFE_CAST(JSON_VALUE(feature_values_json,'$.has_fin_income') AS BOOL) AS INT64) AS has_fin_income,
  CAST(SAFE_CAST(JSON_VALUE(feature_values_json,'$.has_fin_balancesheet') AS BOOL) AS INT64) AS has_fin_balancesheet,
  CAST(SAFE_CAST(JSON_VALUE(feature_values_json,'$.has_fin_cashflow') AS BOOL) AS INT64) AS has_fin_cashflow,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.report_age_days') AS FLOAT64) AS report_age_days,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.fin_report_lag_days') AS FLOAT64) AS fin_report_lag_days,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.roe') AS FLOAT64) AS roe,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.roe_deducted') AS FLOAT64) AS roe_deducted,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.roa') AS FLOAT64) AS roa,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.roic') AS FLOAT64) AS roic,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.grossprofit_margin') AS FLOAT64) AS grossprofit_margin,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.netprofit_margin') AS FLOAT64) AS netprofit_margin,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.debt_to_assets') AS FLOAT64) AS debt_to_assets,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.current_ratio') AS FLOAT64) AS current_ratio,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.quick_ratio') AS FLOAT64) AS quick_ratio,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.assets_to_equity') AS FLOAT64) AS assets_to_equity,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ocf_to_or') AS FLOAT64) AS ocf_to_or,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ocf_to_profit') AS FLOAT64) AS ocf_to_profit,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.cash_ratio') AS FLOAT64) AS cash_ratio,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.netprofit_yoy') AS FLOAT64) AS netprofit_yoy,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.operating_revenue_yoy') AS FLOAT64) AS operating_revenue_yoy,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.total_revenue_yoy') AS FLOAT64) AS total_revenue_yoy,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.basic_eps_yoy') AS FLOAT64) AS basic_eps_yoy,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.q_roe') AS FLOAT64) AS q_roe,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.q_netprofit_margin') AS FLOAT64) AS q_netprofit_margin,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.q_grossprofit_margin') AS FLOAT64) AS q_grossprofit_margin
""");
END IF;

-- ── 动态预测并写入（横截面排序）──
-- raw_score = ML.PREDICT label='1' probability
-- score = oriented score: identity keeps raw, reverse_probability uses 1.0 - raw
-- rank_raw / rank_pct 按最终 oriented score DESC 计算
EXECUTE IMMEDIATE FORMAT("""
  INSERT INTO `data-aquarium.ashare_ads.ads_model_prediction_daily`
  (model_id, predict_date, horizon, sec_code, score, raw_score, score_orientation,
   rank_raw, rank_pct, feature_version, run_id, created_at)
  WITH preds AS (
    SELECT p.trade_date AS predict_date, p.sec_code,
           prob.prob AS raw_score,
           IF('%s' = 'reverse_probability', 1.0 - prob.prob, prob.prob) AS oriented_score
    FROM ML.PREDICT(MODEL `%s`,
      (SELECT trade_date, sec_code, %s
       FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
       WHERE run_id='%s' AND split_tag IN ('valid','test')
         AND trade_date BETWEEN '%s' AND '%s')
    ) AS p, UNNEST(p.predicted_target_label_probs) AS prob
    WHERE CAST(prob.label AS STRING) = '1'
  )
  SELECT
    '%s', predict_date, %d, sec_code,
    oriented_score,
    raw_score,
    '%s',
    ROW_NUMBER() OVER (PARTITION BY predict_date ORDER BY oriented_score DESC, sec_code),
    1.0 - SAFE_DIVIDE(
      ROW_NUMBER() OVER (PARTITION BY predict_date ORDER BY oriented_score DESC, sec_code) - 1,
      COUNT(*) OVER (PARTITION BY predict_date) - 1),
    '%s', '%s', CURRENT_TIMESTAMP()
  FROM preds
""", p_score_orientation, p_selected_model_path, p_feat_sql, p_run_id,
     CAST(p_valid_start AS STRING), CAST(p_test_end AS STRING),
    p_selected_model_id, p_label_horizon,
     p_score_orientation,
     p_feature_version, p_run_id);
