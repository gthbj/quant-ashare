-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 02: 训练 5 个 LOGISTIC_REG 候选模型（run-scoped model names）并登记到 registry。

DECLARE p_run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_label_version STRING DEFAULT 'open_to_close_h1_5_10_20_v20260601';
DECLARE p_preprocess_version STRING DEFAULT 'raw_v0';
DECLARE p_horizon INT64 DEFAULT 5;
DECLARE p_train_start DATE DEFAULT DATE '2019-04-03';
DECLARE p_train_end DATE DEFAULT DATE '2023-12-31';
DECLARE p_valid_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_valid_end DATE DEFAULT DATE '2024-12-31';
-- run_id 嵌入模型对象名，避免跨 run 覆盖
-- 模型对象名中 run_id 的 '-' '.' 需替换为 '_'

-- ── 候选 1: l1_0_l2_0 ──
CREATE OR REPLACE MODEL `data-aquarium.ashare_ads.s1_bqml_20260601_01__l1_0_l2_0`
OPTIONS (
  MODEL_TYPE = 'LOGISTIC_REG', INPUT_LABEL_COLS = ['target_label'],
  DATA_SPLIT_METHOD = 'NO_SPLIT', AUTO_CLASS_WEIGHTS = TRUE,
  L1_REG = 0.0, L2_REG = 0.0, MAX_ITERATIONS = 50
) AS
SELECT tp.target_label,
       tp.list_age_td, tp.ret_1d, tp.ret_3d, tp.ret_5d, tp.ret_10d, tp.ret_20d, tp.ret_60d,
       tp.mom_20_5, tp.mom_60_20, tp.vol_5d, tp.vol_20d, tp.vol_60d,
       tp.drawdown_20d, tp.hl_range_20d, tp.amount_ma20_cny, tp.amount_zscore_20d,
       tp.turnover_rate, tp.turnover_rate_free_float, tp.turnover_rate_ma20, tp.volume_ratio,
       tp.pe_ttm, tp.pb, tp.ps_ttm, tp.dividend_yield_ttm, tp.ep_ttm, tp.bp, tp.sp_ttm,
       tp.log_total_mv, tp.log_circ_mv
FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
WHERE tp.run_id = p_run_id AND tp.split_tag = 'train'
  AND tp.trade_date BETWEEN p_train_start AND p_train_end;

-- ── 候选 2: l1_0_l2_1e_4 ──
CREATE OR REPLACE MODEL `data-aquarium.ashare_ads.s1_bqml_20260601_01__l1_0_l2_1e_4`
OPTIONS (
  MODEL_TYPE = 'LOGISTIC_REG', INPUT_LABEL_COLS = ['target_label'],
  DATA_SPLIT_METHOD = 'NO_SPLIT', AUTO_CLASS_WEIGHTS = TRUE,
  L1_REG = 0.0, L2_REG = 0.0001, MAX_ITERATIONS = 50
) AS
SELECT tp.target_label,
       tp.list_age_td, tp.ret_1d, tp.ret_3d, tp.ret_5d, tp.ret_10d, tp.ret_20d, tp.ret_60d,
       tp.mom_20_5, tp.mom_60_20, tp.vol_5d, tp.vol_20d, tp.vol_60d,
       tp.drawdown_20d, tp.hl_range_20d, tp.amount_ma20_cny, tp.amount_zscore_20d,
       tp.turnover_rate, tp.turnover_rate_free_float, tp.turnover_rate_ma20, tp.volume_ratio,
       tp.pe_ttm, tp.pb, tp.ps_ttm, tp.dividend_yield_ttm, tp.ep_ttm, tp.bp, tp.sp_ttm,
       tp.log_total_mv, tp.log_circ_mv
FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
WHERE tp.run_id = p_run_id AND tp.split_tag = 'train'
  AND tp.trade_date BETWEEN p_train_start AND p_train_end;

-- ── 候选 3: l1_0_l2_1e_3 ──
CREATE OR REPLACE MODEL `data-aquarium.ashare_ads.s1_bqml_20260601_01__l1_0_l2_1e_3`
OPTIONS (
  MODEL_TYPE = 'LOGISTIC_REG', INPUT_LABEL_COLS = ['target_label'],
  DATA_SPLIT_METHOD = 'NO_SPLIT', AUTO_CLASS_WEIGHTS = TRUE,
  L1_REG = 0.0, L2_REG = 0.001, MAX_ITERATIONS = 50
) AS
SELECT tp.target_label,
       tp.list_age_td, tp.ret_1d, tp.ret_3d, tp.ret_5d, tp.ret_10d, tp.ret_20d, tp.ret_60d,
       tp.mom_20_5, tp.mom_60_20, tp.vol_5d, tp.vol_20d, tp.vol_60d,
       tp.drawdown_20d, tp.hl_range_20d, tp.amount_ma20_cny, tp.amount_zscore_20d,
       tp.turnover_rate, tp.turnover_rate_free_float, tp.turnover_rate_ma20, tp.volume_ratio,
       tp.pe_ttm, tp.pb, tp.ps_ttm, tp.dividend_yield_ttm, tp.ep_ttm, tp.bp, tp.sp_ttm,
       tp.log_total_mv, tp.log_circ_mv
FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
WHERE tp.run_id = p_run_id AND tp.split_tag = 'train'
  AND tp.trade_date BETWEEN p_train_start AND p_train_end;

-- ── 候选 4: l1_1e_5_l2_1e_4 ──
CREATE OR REPLACE MODEL `data-aquarium.ashare_ads.s1_bqml_20260601_01__l1_1e_5_l2_1e_4`
OPTIONS (
  MODEL_TYPE = 'LOGISTIC_REG', INPUT_LABEL_COLS = ['target_label'],
  DATA_SPLIT_METHOD = 'NO_SPLIT', AUTO_CLASS_WEIGHTS = TRUE,
  L1_REG = 0.00001, L2_REG = 0.0001, MAX_ITERATIONS = 50
) AS
SELECT tp.target_label,
       tp.list_age_td, tp.ret_1d, tp.ret_3d, tp.ret_5d, tp.ret_10d, tp.ret_20d, tp.ret_60d,
       tp.mom_20_5, tp.mom_60_20, tp.vol_5d, tp.vol_20d, tp.vol_60d,
       tp.drawdown_20d, tp.hl_range_20d, tp.amount_ma20_cny, tp.amount_zscore_20d,
       tp.turnover_rate, tp.turnover_rate_free_float, tp.turnover_rate_ma20, tp.volume_ratio,
       tp.pe_ttm, tp.pb, tp.ps_ttm, tp.dividend_yield_ttm, tp.ep_ttm, tp.bp, tp.sp_ttm,
       tp.log_total_mv, tp.log_circ_mv
FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
WHERE tp.run_id = p_run_id AND tp.split_tag = 'train'
  AND tp.trade_date BETWEEN p_train_start AND p_train_end;

-- ── 候选 5: l1_1e_4_l2_1e_3 ──
CREATE OR REPLACE MODEL `data-aquarium.ashare_ads.s1_bqml_20260601_01__l1_1e_4_l2_1e_3`
OPTIONS (
  MODEL_TYPE = 'LOGISTIC_REG', INPUT_LABEL_COLS = ['target_label'],
  DATA_SPLIT_METHOD = 'NO_SPLIT', AUTO_CLASS_WEIGHTS = TRUE,
  L1_REG = 0.0001, L2_REG = 0.001, MAX_ITERATIONS = 50
) AS
SELECT tp.target_label,
       tp.list_age_td, tp.ret_1d, tp.ret_3d, tp.ret_5d, tp.ret_10d, tp.ret_20d, tp.ret_60d,
       tp.mom_20_5, tp.mom_60_20, tp.vol_5d, tp.vol_20d, tp.vol_60d,
       tp.drawdown_20d, tp.hl_range_20d, tp.amount_ma20_cny, tp.amount_zscore_20d,
       tp.turnover_rate, tp.turnover_rate_free_float, tp.turnover_rate_ma20, tp.volume_ratio,
       tp.pe_ttm, tp.pb, tp.ps_ttm, tp.dividend_yield_ttm, tp.ep_ttm, tp.bp, tp.sp_ttm,
       tp.log_total_mv, tp.log_circ_mv
FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
WHERE tp.run_id = p_run_id AND tp.split_tag = 'train'
  AND tp.trade_date BETWEEN p_train_start AND p_train_end;

-- ── 登记全部候选到 model registry ──
-- model_id 包含 run_id 以保证 run 隔离
INSERT INTO `data-aquarium.ashare_ads.ads_model_registry`
(model_id, strategy_id, model_family, horizon,
 feature_version, label_version, preprocess_version,
 train_start_date, train_end_date, valid_start_date, valid_end_date,
 model_params_json, metrics_json, model_uri, git_commit, status, created_at)
SELECT * FROM UNNEST([
  STRUCT(
    CONCAT(p_run_id, '__l1_0_l2_0') AS model_id,
    p_strategy_id AS strategy_id, 'bqml_logistic_reg' AS model_family, p_horizon AS horizon,
    p_feature_version AS feature_version, p_label_version AS label_version, p_preprocess_version AS preprocess_version,
    p_train_start AS train_start_date, p_train_end AS train_end_date,
    p_valid_start AS valid_start_date, p_valid_end AS valid_end_date,
    CONCAT('{"l1_reg":0,"l2_reg":0,"max_iterations":50,"auto_class_weights":true,"run_id":"', p_run_id, '"}') AS model_params_json,
    CAST(NULL AS STRING) AS metrics_json,
    CONCAT('bq://data-aquarium.ashare_ads.', p_run_id, '__l1_0_l2_0') AS model_uri,
    CAST(NULL AS STRING) AS git_commit,
    'candidate' AS status,
    CURRENT_TIMESTAMP() AS created_at),
  STRUCT(CONCAT(p_run_id, '__l1_0_l2_1e_4'), p_strategy_id, 'bqml_logistic_reg', p_horizon,
    p_feature_version, p_label_version, p_preprocess_version, p_train_start, p_train_end, p_valid_start, p_valid_end,
    CONCAT('{"l1_reg":0,"l2_reg":0.0001,"max_iterations":50,"auto_class_weights":true,"run_id":"', p_run_id, '"}'),
    NULL, CONCAT('bq://data-aquarium.ashare_ads.', p_run_id, '__l1_0_l2_1e_4'), NULL, 'candidate', CURRENT_TIMESTAMP()),
  STRUCT(CONCAT(p_run_id, '__l1_0_l2_1e_3'), p_strategy_id, 'bqml_logistic_reg', p_horizon,
    p_feature_version, p_label_version, p_preprocess_version, p_train_start, p_train_end, p_valid_start, p_valid_end,
    CONCAT('{"l1_reg":0,"l2_reg":0.001,"max_iterations":50,"auto_class_weights":true,"run_id":"', p_run_id, '"}'),
    NULL, CONCAT('bq://data-aquarium.ashare_ads.', p_run_id, '__l1_0_l2_1e_3'), NULL, 'candidate', CURRENT_TIMESTAMP()),
  STRUCT(CONCAT(p_run_id, '__l1_1e_5_l2_1e_4'), p_strategy_id, 'bqml_logistic_reg', p_horizon,
    p_feature_version, p_label_version, p_preprocess_version, p_train_start, p_train_end, p_valid_start, p_valid_end,
    CONCAT('{"l1_reg":0.00001,"l2_reg":0.0001,"max_iterations":50,"auto_class_weights":true,"run_id":"', p_run_id, '"}'),
    NULL, CONCAT('bq://data-aquarium.ashare_ads.', p_run_id, '__l1_1e_5_l2_1e_4'), NULL, 'candidate', CURRENT_TIMESTAMP()),
  STRUCT(CONCAT(p_run_id, '__l1_1e_4_l2_1e_3'), p_strategy_id, 'bqml_logistic_reg', p_horizon,
    p_feature_version, p_label_version, p_preprocess_version, p_train_start, p_train_end, p_valid_start, p_valid_end,
    CONCAT('{"l1_reg":0.0001,"l2_reg":0.001,"max_iterations":50,"auto_class_weights":true,"run_id":"', p_run_id, '"}'),
    NULL, CONCAT('bq://data-aquarium.ashare_ads.', p_run_id, '__l1_1e_4_l2_1e_3'), NULL, 'candidate', CURRENT_TIMESTAMP())
]);
