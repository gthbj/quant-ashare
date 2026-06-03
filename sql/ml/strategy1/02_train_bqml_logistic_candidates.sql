-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 02: 训练 5 个 LOGISTIC_REG 候选模型。模型对象名嵌入 sanitized run_id（真正 run-scoped）。
-- 特征从 feature_values_json 抽取（ADS 契约不变）。用 FOR + EXECUTE IMMEDIATE 动态建模。

DECLARE p_run_id STRING DEFAULT 's1_bqml_livepool_oriented_20260603_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_experiment_id STRING DEFAULT 'oq010_base_oriented_weekly_h5_n5_w20_pv';
DECLARE p_experiment_group STRING DEFAULT 'baseline';
DECLARE p_baseline_experiment_id STRING DEFAULT 'oq010_base_oriented_weekly_h5_n5_w20_pv';
DECLARE p_parent_experiment_id STRING DEFAULT 'oq010_base_oriented_weekly_h5_n5_w20_pv';
DECLARE p_parent_run_id STRING DEFAULT 's1_bqml_livepool_oriented_20260603_01';
DECLARE p_feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_feature_set_id STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_label_version STRING DEFAULT 'open_to_close_h1_5_10_20_v20260601';
DECLARE p_preprocess_version STRING DEFAULT 'raw_v0';
DECLARE p_label_horizon INT64 DEFAULT 5;
DECLARE p_rebalance_frequency STRING DEFAULT 'weekly';
DECLARE p_target_holdings INT64 DEFAULT 5;
DECLARE p_max_single_weight FLOAT64 DEFAULT 0.20;
DECLARE p_horizon_natural_frequency STRING DEFAULT 'weekly';
DECLARE p_train_start DATE DEFAULT DATE '2019-04-03';
DECLARE p_train_end DATE DEFAULT DATE '2023-12-31';
DECLARE p_valid_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_valid_end DATE DEFAULT DATE '2024-12-31';
DECLARE p_force_replace BOOL DEFAULT FALSE;
DECLARE p_run_safe STRING;
DECLARE p_feat_sql STRING;

IF p_label_horizon NOT IN (5, 10, 20) THEN
  RAISE USING MESSAGE = 'p_label_horizon must be one of 5, 10, 20';
END IF;

IF p_feature_set_id NOT IN ('strategy1_pv_v0_20260601', 'strategy1_pv_fin_quality_v0_20260603') THEN
  RAISE USING MESSAGE = CONCAT('unsupported p_feature_set_id: ', p_feature_set_id);
END IF;

-- run_id 净化为合法 BigQuery 标识符片段
SET p_run_safe = REGEXP_REPLACE(p_run_id, r'[^A-Za-z0-9_]', '_');

-- ── registry 幂等：同 run_id 已登记则按 force_replace 决定报错或清理 ──
IF NOT p_force_replace THEN
  IF (SELECT COUNT(*) > 0
      FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
      WHERE reg.strategy_id = p_strategy_id
        AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id) THEN
    RAISE USING MESSAGE = CONCAT('registry already has candidates for run_id ', p_run_id, '. Set p_force_replace=TRUE to retrain.');
  END IF;
END IF;

IF p_force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id;
END IF;

-- 特征抽取片段（JSON_VALUE → SAFE_CAST），训练/预测复用
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

-- ── 逐候选训练（run-scoped 模型名）──
FOR cand IN (
  SELECT id, l1, l2 FROM UNNEST([
    STRUCT('l1_0_l2_0' AS id, 0.0 AS l1, 0.0 AS l2),
    STRUCT('l1_0_l2_1e_4' AS id, 0.0 AS l1, 0.0001 AS l2),
    STRUCT('l1_0_l2_1e_3' AS id, 0.0 AS l1, 0.001 AS l2),
    STRUCT('l1_1e_5_l2_1e_4' AS id, 0.00001 AS l1, 0.0001 AS l2),
    STRUCT('l1_1e_4_l2_1e_3' AS id, 0.0001 AS l1, 0.001 AS l2)
  ])
) DO
  EXECUTE IMMEDIATE FORMAT("""
    CREATE OR REPLACE MODEL `data-aquarium.ashare_ads.%s__%s`
    OPTIONS (MODEL_TYPE='LOGISTIC_REG', INPUT_LABEL_COLS=['target_label'],
             DATA_SPLIT_METHOD='NO_SPLIT', AUTO_CLASS_WEIGHTS=TRUE,
             L1_REG=%f, L2_REG=%f, MAX_ITERATIONS=50) AS
    SELECT target_label, %s
    FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
    WHERE run_id='%s' AND split_tag='train' AND trade_date BETWEEN '%s' AND '%s'
  """, p_run_safe, cand.id, cand.l1, cand.l2, p_feat_sql,
       p_run_id, CAST(p_train_start AS STRING), CAST(p_train_end AS STRING));
END FOR;

-- ── 登记全部候选到 registry（model_id 含 run_safe，model_uri 指向真实对象）──
INSERT INTO `data-aquarium.ashare_ads.ads_model_registry`
(model_id, strategy_id, model_family, horizon,
 feature_version, label_version, preprocess_version,
 train_start_date, train_end_date, valid_start_date, valid_end_date,
 model_params_json, metrics_json, model_uri, git_commit, status, created_at)
SELECT
  CONCAT(p_run_safe, '__', g.id),
  p_strategy_id, 'bqml_logistic_reg', p_label_horizon,
  p_feature_version, p_label_version, p_preprocess_version,
  p_train_start, p_train_end, p_valid_start, p_valid_end,
  CONCAT('{"l1_reg":', CAST(g.l1 AS STRING), ',"l2_reg":', CAST(g.l2 AS STRING),
         ',"max_iterations":50,"auto_class_weights":true,"candidate_id":"', g.id,
         '","run_id":"', p_run_id,
         '","experiment_id":"', p_experiment_id,
         '","experiment_group":"', p_experiment_group,
         '","baseline_experiment_id":"', p_baseline_experiment_id,
         '","parent_experiment_id":"', p_parent_experiment_id,
         '","parent_run_id":"', p_parent_run_id,
         '","rebalance_frequency":"', p_rebalance_frequency,
         '","feature_set_id":"', p_feature_set_id,
         '","horizon_natural_frequency":"', p_horizon_natural_frequency,
         '","target_holdings":', CAST(p_target_holdings AS STRING),
         ',"max_single_weight":', CAST(p_max_single_weight AS STRING),
         ',"label_horizon":', CAST(p_label_horizon AS STRING), '}'),
  CAST(NULL AS STRING),
  CONCAT('bq://data-aquarium.ashare_ads.', p_run_safe, '__', g.id),
  CAST(NULL AS STRING),
  'candidate',
  CURRENT_TIMESTAMP()
FROM UNNEST([
  STRUCT('l1_0_l2_0' AS id, 0.0 AS l1, 0.0 AS l2),
  STRUCT('l1_0_l2_1e_4' AS id, 0.0 AS l1, 0.0001 AS l2),
  STRUCT('l1_0_l2_1e_3' AS id, 0.0 AS l1, 0.001 AS l2),
  STRUCT('l1_1e_5_l2_1e_4' AS id, 0.00001 AS l1, 0.0001 AS l2),
  STRUCT('l1_1e_4_l2_1e_3' AS id, 0.0001 AS l1, 0.001 AS l2)
]) AS g;
