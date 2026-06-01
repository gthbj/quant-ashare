-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 02: 训练 5 个 LOGISTIC_REG 候选模型并登记到 model registry。

-- ── 运行参数 ──
DECLARE run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE model_id_prefix STRING DEFAULT 'ml_pv_clf_v0_bqml_logit';
DECLARE feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE label_version STRING DEFAULT 'open_to_close_h1_5_10_20_v20260601';
DECLARE preprocess_version STRING DEFAULT 'raw_v0';
DECLARE horizon INT64 DEFAULT 5;
DECLARE train_start_date DATE DEFAULT DATE '2019-04-03';
DECLARE train_end_date DATE DEFAULT DATE '2023-12-31';
DECLARE valid_start_date DATE DEFAULT DATE '2024-01-01';
DECLARE valid_end_date DATE DEFAULT DATE '2024-12-31';

-- ── 候选 1: l1_0_l2_0 ──
CREATE OR REPLACE MODEL `data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_0_l2_0`
OPTIONS (
  MODEL_TYPE = 'LOGISTIC_REG',
  INPUT_LABEL_COLS = ['target_label'],
  DATA_SPLIT_METHOD = 'NO_SPLIT',
  AUTO_CLASS_WEIGHTS = TRUE,
  L1_REG = 0.0,
  L2_REG = 0.0,
  MAX_ITERATIONS = 50
) AS
SELECT target_label,
       list_age_td, ret_1d, ret_3d, ret_5d, ret_10d, ret_20d, ret_60d,
       mom_20_5, mom_60_20, vol_5d, vol_20d, vol_60d,
       drawdown_20d, hl_range_20d, amount_ma20_cny, amount_zscore_20d,
       turnover_rate, turnover_rate_free_float, turnover_rate_ma20, volume_ratio,
       pe_ttm, pb, ps_ttm, dividend_yield_ttm, ep_ttm, bp, sp_ttm,
       log_total_mv, log_circ_mv
FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
WHERE run_id = run_id AND split_tag = 'train'
  AND trade_date BETWEEN train_start_date AND train_end_date;

-- ── 候选 2: l1_0_l2_1e_4 ──
CREATE OR REPLACE MODEL `data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_0_l2_1e_4`
OPTIONS (
  MODEL_TYPE = 'LOGISTIC_REG',
  INPUT_LABEL_COLS = ['target_label'],
  DATA_SPLIT_METHOD = 'NO_SPLIT',
  AUTO_CLASS_WEIGHTS = TRUE,
  L1_REG = 0.0,
  L2_REG = 0.0001,
  MAX_ITERATIONS = 50
) AS
SELECT target_label,
       list_age_td, ret_1d, ret_3d, ret_5d, ret_10d, ret_20d, ret_60d,
       mom_20_5, mom_60_20, vol_5d, vol_20d, vol_60d,
       drawdown_20d, hl_range_20d, amount_ma20_cny, amount_zscore_20d,
       turnover_rate, turnover_rate_free_float, turnover_rate_ma20, volume_ratio,
       pe_ttm, pb, ps_ttm, dividend_yield_ttm, ep_ttm, bp, sp_ttm,
       log_total_mv, log_circ_mv
FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
WHERE run_id = run_id AND split_tag = 'train'
  AND trade_date BETWEEN train_start_date AND train_end_date;

-- ── 候选 3: l1_0_l2_1e_3 ──
CREATE OR REPLACE MODEL `data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_0_l2_1e_3`
OPTIONS (
  MODEL_TYPE = 'LOGISTIC_REG',
  INPUT_LABEL_COLS = ['target_label'],
  DATA_SPLIT_METHOD = 'NO_SPLIT',
  AUTO_CLASS_WEIGHTS = TRUE,
  L1_REG = 0.0,
  L2_REG = 0.001,
  MAX_ITERATIONS = 50
) AS
SELECT target_label,
       list_age_td, ret_1d, ret_3d, ret_5d, ret_10d, ret_20d, ret_60d,
       mom_20_5, mom_60_20, vol_5d, vol_20d, vol_60d,
       drawdown_20d, hl_range_20d, amount_ma20_cny, amount_zscore_20d,
       turnover_rate, turnover_rate_free_float, turnover_rate_ma20, volume_ratio,
       pe_ttm, pb, ps_ttm, dividend_yield_ttm, ep_ttm, bp, sp_ttm,
       log_total_mv, log_circ_mv
FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
WHERE run_id = run_id AND split_tag = 'train'
  AND trade_date BETWEEN train_start_date AND train_end_date;

-- ── 候选 4: l1_1e_5_l2_1e_4 ──
CREATE OR REPLACE MODEL `data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_1e_5_l2_1e_4`
OPTIONS (
  MODEL_TYPE = 'LOGISTIC_REG',
  INPUT_LABEL_COLS = ['target_label'],
  DATA_SPLIT_METHOD = 'NO_SPLIT',
  AUTO_CLASS_WEIGHTS = TRUE,
  L1_REG = 0.00001,
  L2_REG = 0.0001,
  MAX_ITERATIONS = 50
) AS
SELECT target_label,
       list_age_td, ret_1d, ret_3d, ret_5d, ret_10d, ret_20d, ret_60d,
       mom_20_5, mom_60_20, vol_5d, vol_20d, vol_60d,
       drawdown_20d, hl_range_20d, amount_ma20_cny, amount_zscore_20d,
       turnover_rate, turnover_rate_free_float, turnover_rate_ma20, volume_ratio,
       pe_ttm, pb, ps_ttm, dividend_yield_ttm, ep_ttm, bp, sp_ttm,
       log_total_mv, log_circ_mv
FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
WHERE run_id = run_id AND split_tag = 'train'
  AND trade_date BETWEEN train_start_date AND train_end_date;

-- ── 候选 5: l1_1e_4_l2_1e_3 ──
CREATE OR REPLACE MODEL `data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_1e_4_l2_1e_3`
OPTIONS (
  MODEL_TYPE = 'LOGISTIC_REG',
  INPUT_LABEL_COLS = ['target_label'],
  DATA_SPLIT_METHOD = 'NO_SPLIT',
  AUTO_CLASS_WEIGHTS = TRUE,
  L1_REG = 0.0001,
  L2_REG = 0.001,
  MAX_ITERATIONS = 50
) AS
SELECT target_label,
       list_age_td, ret_1d, ret_3d, ret_5d, ret_10d, ret_20d, ret_60d,
       mom_20_5, mom_60_20, vol_5d, vol_20d, vol_60d,
       drawdown_20d, hl_range_20d, amount_ma20_cny, amount_zscore_20d,
       turnover_rate, turnover_rate_free_float, turnover_rate_ma20, volume_ratio,
       pe_ttm, pb, ps_ttm, dividend_yield_ttm, ep_ttm, bp, sp_ttm,
       log_total_mv, log_circ_mv
FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
WHERE run_id = run_id AND split_tag = 'train'
  AND trade_date BETWEEN train_start_date AND train_end_date;

-- ── 登记全部候选到 model registry ──
INSERT INTO `data-aquarium.ashare_ads.ads_model_registry`
(model_id, strategy_id, model_family, horizon,
 feature_version, label_version, preprocess_version,
 train_start_date, train_end_date, valid_start_date, valid_end_date,
 model_params_json, metrics_json, model_uri, git_commit, status, created_at)
SELECT * FROM UNNEST([
  STRUCT(
    CONCAT(model_id_prefix, '_l1_0_l2_0') AS model_id,
    strategy_id, 'bqml_logistic_reg' AS model_family, horizon,
    feature_version, label_version, preprocess_version,
    train_start_date, train_end_date, valid_start_date, valid_end_date,
    '{"l1_reg":0,"l2_reg":0,"max_iterations":50,"auto_class_weights":true}' AS model_params_json,
    CAST(NULL AS STRING) AS metrics_json,
    'bq://data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_0_l2_0' AS model_uri,
    CAST(NULL AS STRING) AS git_commit,
    'candidate' AS status,
    CURRENT_TIMESTAMP() AS created_at),
  STRUCT(
    CONCAT(model_id_prefix, '_l1_0_l2_1e_4'),
    strategy_id, 'bqml_logistic_reg', horizon,
    feature_version, label_version, preprocess_version,
    train_start_date, train_end_date, valid_start_date, valid_end_date,
    '{"l1_reg":0,"l2_reg":0.0001,"max_iterations":50,"auto_class_weights":true}',
    NULL,
    'bq://data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_0_l2_1e_4',
    NULL, 'candidate', CURRENT_TIMESTAMP()),
  STRUCT(
    CONCAT(model_id_prefix, '_l1_0_l2_1e_3'),
    strategy_id, 'bqml_logistic_reg', horizon,
    feature_version, label_version, preprocess_version,
    train_start_date, train_end_date, valid_start_date, valid_end_date,
    '{"l1_reg":0,"l2_reg":0.001,"max_iterations":50,"auto_class_weights":true}',
    NULL,
    'bq://data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_0_l2_1e_3',
    NULL, 'candidate', CURRENT_TIMESTAMP()),
  STRUCT(
    CONCAT(model_id_prefix, '_l1_1e_5_l2_1e_4'),
    strategy_id, 'bqml_logistic_reg', horizon,
    feature_version, label_version, preprocess_version,
    train_start_date, train_end_date, valid_start_date, valid_end_date,
    '{"l1_reg":0.00001,"l2_reg":0.0001,"max_iterations":50,"auto_class_weights":true}',
    NULL,
    'bq://data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_1e_5_l2_1e_4',
    NULL, 'candidate', CURRENT_TIMESTAMP()),
  STRUCT(
    CONCAT(model_id_prefix, '_l1_1e_4_l2_1e_3'),
    strategy_id, 'bqml_logistic_reg', horizon,
    feature_version, label_version, preprocess_version,
    train_start_date, train_end_date, valid_start_date, valid_end_date,
    '{"l1_reg":0.0001,"l2_reg":0.001,"max_iterations":50,"auto_class_weights":true}',
    NULL,
    'bq://data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_1e_4_l2_1e_3',
    NULL, 'candidate', CURRENT_TIMESTAMP())
]);
