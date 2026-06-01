-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 01: 从 DWS sample 构建冻结训练面板，写入 ads_ml_training_panel_daily。
-- 同时写入物理特征列（供 BQML CREATE MODEL 直接读取）和 feature_values_json（审计快照）。

-- ── 运行参数（p_ 前缀避免与表列同名）──
DECLARE p_run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_preprocess_version STRING DEFAULT 'raw_v0';
DECLARE p_feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_label_version STRING DEFAULT 'open_to_close_h1_5_10_20_v20260601';
DECLARE p_horizon INT64 DEFAULT 5;
DECLARE p_train_start DATE DEFAULT DATE '2019-04-03';
DECLARE p_train_end DATE DEFAULT DATE '2023-12-31';
DECLARE p_valid_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_valid_end DATE DEFAULT DATE '2024-12-31';
DECLARE p_test_start DATE DEFAULT DATE '2025-01-01';
DECLARE p_test_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_force_replace BOOL DEFAULT FALSE;

-- ── ADS 契约扩展：确保物理特征列存在 ──
-- 首次运行时需要 ALTER TABLE 添加特征列；后续运行列已存在则跳过。
-- BigQuery ALTER COLUMN ADD IF NOT EXISTS 不支持，用 INFORMATION_SCHEMA 检查。
BEGIN
  DECLARE cols_exist INT64;
  SET cols_exist = (
    SELECT COUNT(*)
    FROM `data-aquarium.ashare_ads.INFORMATION_SCHEMA.COLUMNS`
    WHERE table_name = 'ads_ml_training_panel_daily' AND column_name = 'list_age_td'
  );
  IF cols_exist = 0 THEN
    ALTER TABLE `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
    ADD COLUMN IF NOT EXISTS list_age_td INT64,
    ADD COLUMN IF NOT EXISTS ret_1d FLOAT64, ADD COLUMN IF NOT EXISTS ret_3d FLOAT64,
    ADD COLUMN IF NOT EXISTS ret_5d FLOAT64, ADD COLUMN IF NOT EXISTS ret_10d FLOAT64,
    ADD COLUMN IF NOT EXISTS ret_20d FLOAT64, ADD COLUMN IF NOT EXISTS ret_60d FLOAT64,
    ADD COLUMN IF NOT EXISTS mom_20_5 FLOAT64, ADD COLUMN IF NOT EXISTS mom_60_20 FLOAT64,
    ADD COLUMN IF NOT EXISTS vol_5d FLOAT64, ADD COLUMN IF NOT EXISTS vol_20d FLOAT64,
    ADD COLUMN IF NOT EXISTS vol_60d FLOAT64,
    ADD COLUMN IF NOT EXISTS drawdown_20d FLOAT64, ADD COLUMN IF NOT EXISTS hl_range_20d FLOAT64,
    ADD COLUMN IF NOT EXISTS amount_ma20_cny FLOAT64, ADD COLUMN IF NOT EXISTS amount_zscore_20d FLOAT64,
    ADD COLUMN IF NOT EXISTS turnover_rate FLOAT64, ADD COLUMN IF NOT EXISTS turnover_rate_free_float FLOAT64,
    ADD COLUMN IF NOT EXISTS turnover_rate_ma20 FLOAT64, ADD COLUMN IF NOT EXISTS volume_ratio FLOAT64,
    ADD COLUMN IF NOT EXISTS pe_ttm FLOAT64, ADD COLUMN IF NOT EXISTS pb FLOAT64,
    ADD COLUMN IF NOT EXISTS ps_ttm FLOAT64, ADD COLUMN IF NOT EXISTS dividend_yield_ttm FLOAT64,
    ADD COLUMN IF NOT EXISTS ep_ttm FLOAT64, ADD COLUMN IF NOT EXISTS bp FLOAT64,
    ADD COLUMN IF NOT EXISTS sp_ttm FLOAT64,
    ADD COLUMN IF NOT EXISTS log_total_mv FLOAT64, ADD COLUMN IF NOT EXISTS log_circ_mv FLOAT64,
    ADD COLUMN IF NOT EXISTS board STRING;
  END IF;
END;

-- ── 幂等检查 ──
IF NOT p_force_replace THEN
  IF (SELECT COUNT(*) > 0
      FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
      WHERE tp.run_id = p_run_id
        AND tp.trade_date BETWEEN p_train_start AND p_test_end) THEN
    RAISE USING MESSAGE = CONCAT('run_id ', p_run_id, ' already exists. Set p_force_replace=TRUE to overwrite.');
  END IF;
END IF;

IF p_force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
  WHERE tp.run_id = p_run_id
    AND tp.trade_date BETWEEN p_train_start AND p_test_end;
END IF;

-- ── 写入训练面板 ──
INSERT INTO `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
(run_id, strategy_id, model_id, preprocess_version, feature_version, label_version,
 universe_version, trade_date, sec_code, horizon, split_fold, split_tag,
 sample_weight, target_label, target_return,
 feature_values_json, feature_column_list,
 list_age_td, ret_1d, ret_3d, ret_5d, ret_10d, ret_20d, ret_60d,
 mom_20_5, mom_60_20, vol_5d, vol_20d, vol_60d,
 drawdown_20d, hl_range_20d, amount_ma20_cny, amount_zscore_20d,
 turnover_rate, turnover_rate_free_float, turnover_rate_ma20, volume_ratio,
 pe_ttm, pb, ps_ttm, dividend_yield_ttm, ep_ttm, bp, sp_ttm,
 log_total_mv, log_circ_mv, board,
 created_at)
SELECT
  p_run_id,
  p_strategy_id,
  CAST(NULL AS STRING),
  p_preprocess_version,
  s.feature_version,
  s.label_version,
  s.universe_version,
  s.trade_date,
  s.sec_code,
  p_horizon,
  s.split_fold,
  CASE
    WHEN s.trade_date BETWEEN p_train_start AND p_train_end THEN 'train'
    WHEN s.trade_date BETWEEN p_valid_start AND p_valid_end THEN 'valid'
    WHEN s.trade_date BETWEEN p_test_start AND p_test_end THEN 'test'
    ELSE 'live'
  END,
  1.0,
  s.label_top30_5d,
  s.fwd_xs_ret_5d,
  TO_JSON_STRING(STRUCT(
    s.list_age_td, s.ret_1d, s.ret_3d, s.ret_5d, s.ret_10d, s.ret_20d, s.ret_60d,
    s.mom_20_5, s.mom_60_20, s.vol_5d, s.vol_20d, s.vol_60d,
    s.drawdown_20d, s.hl_range_20d, s.amount_ma20_cny, s.amount_zscore_20d,
    s.turnover_rate, s.turnover_rate_free_float, s.turnover_rate_ma20, s.volume_ratio,
    s.pe_ttm, s.pb, s.ps_ttm, s.dividend_yield_ttm, s.ep_ttm, s.bp, s.sp_ttm,
    s.log_total_mv, s.log_circ_mv, s.board
  )),
  ['list_age_td','ret_1d','ret_3d','ret_5d','ret_10d','ret_20d','ret_60d',
   'mom_20_5','mom_60_20','vol_5d','vol_20d','vol_60d',
   'drawdown_20d','hl_range_20d','amount_ma20_cny','amount_zscore_20d',
   'turnover_rate','turnover_rate_free_float','turnover_rate_ma20','volume_ratio',
   'pe_ttm','pb','ps_ttm','dividend_yield_ttm','ep_ttm','bp','sp_ttm',
   'log_total_mv','log_circ_mv'],
  -- 物理特征列
  s.list_age_td, s.ret_1d, s.ret_3d, s.ret_5d, s.ret_10d, s.ret_20d, s.ret_60d,
  s.mom_20_5, s.mom_60_20, s.vol_5d, s.vol_20d, s.vol_60d,
  s.drawdown_20d, s.hl_range_20d, s.amount_ma20_cny, s.amount_zscore_20d,
  s.turnover_rate, s.turnover_rate_free_float, s.turnover_rate_ma20, s.volume_ratio,
  s.pe_ttm, s.pb, s.ps_ttm, s.dividend_yield_ttm, s.ep_ttm, s.bp, s.sp_ttm,
  s.log_total_mv, s.log_circ_mv, s.board,
  CURRENT_TIMESTAMP()
FROM `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
WHERE s.trade_date BETWEEN p_train_start AND p_test_end
  AND s.feature_version = p_feature_version
  AND s.label_version = p_label_version
  AND s.sample_trainable_default;
