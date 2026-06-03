-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 01: 从 DWS sample 构建冻结面板，写入 ads_ml_training_panel_daily。
-- 语义从"纯训练样本表"收敛为"run-scoped model input panel"（PRD-20260602-05）。
-- split-aware 入池：
--   train: horizon-aware trainable mask（含 label_entry_tradable / label_valid_*，训练允许）
--   valid/test: predict_live_available_mask（仅 t 日已知 universe/feature/history/valuation，不含未来标签）

DECLARE p_run_id STRING DEFAULT 's1_bqml_livepool_oriented_20260603_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_experiment_id STRING DEFAULT 'oq010_base_oriented_weekly_h5_n5_w20_pv';
DECLARE p_experiment_group STRING DEFAULT 'baseline';
DECLARE p_baseline_experiment_id STRING DEFAULT 'oq010_base_oriented_weekly_h5_n5_w20_pv';
DECLARE p_parent_experiment_id STRING DEFAULT 'oq010_base_oriented_weekly_h5_n5_w20_pv';
DECLARE p_parent_run_id STRING DEFAULT 's1_bqml_livepool_oriented_20260603_01';
DECLARE p_preprocess_version STRING DEFAULT 'raw_v0';
DECLARE p_feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_feature_set_id STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_fin_feature_version STRING DEFAULT 'fin_default_v0_20260602';
DECLARE p_label_version STRING DEFAULT 'open_to_close_h1_5_10_20_v20260601';
DECLARE p_label_horizon INT64 DEFAULT 5;
DECLARE p_rebalance_frequency STRING DEFAULT 'weekly';
DECLARE p_target_holdings INT64 DEFAULT 5;
DECLARE p_max_single_weight FLOAT64 DEFAULT 0.20;
DECLARE p_horizon_natural_frequency STRING DEFAULT 'weekly';
DECLARE p_train_start DATE DEFAULT DATE '2019-04-03';
DECLARE p_train_end DATE DEFAULT DATE '2023-12-31';
DECLARE p_valid_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_valid_end DATE DEFAULT DATE '2024-12-31';
DECLARE p_test_start DATE DEFAULT DATE '2025-01-01';
DECLARE p_test_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_force_replace BOOL DEFAULT FALSE;

IF p_label_horizon NOT IN (5, 10, 20) THEN
  RAISE USING MESSAGE = 'p_label_horizon must be one of 5, 10, 20';
END IF;

IF p_feature_set_id NOT IN ('strategy1_pv_v0_20260601', 'strategy1_pv_fin_quality_v0_20260603') THEN
  RAISE USING MESSAGE = CONCAT('unsupported p_feature_set_id: ', p_feature_set_id);
END IF;

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

-- ── 写入训练面板（特征进 JSON，target 进物理列）──
INSERT INTO `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
(run_id, strategy_id, model_id, preprocess_version, feature_version, label_version,
 universe_version, trade_date, sec_code, horizon, split_fold, split_tag,
 sample_weight, target_label, target_return,
 feature_values_json, feature_column_list, created_at)
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
  p_label_horizon,
  s.split_fold,
  CASE
    WHEN s.trade_date BETWEEN p_train_start AND p_train_end THEN 'train'
    WHEN s.trade_date BETWEEN p_valid_start AND p_valid_end THEN 'valid'
    WHEN s.trade_date BETWEEN p_test_start AND p_test_end THEN 'test'
    ELSE 'live'
  END,
  1.0,
  CASE p_label_horizon
    WHEN 5 THEN s.label_top30_5d
    WHEN 10 THEN s.label_top30_10d
    WHEN 20 THEN s.label_top30_20d
  END,
  CASE p_label_horizon
    WHEN 5 THEN s.fwd_xs_ret_5d
    WHEN 10 THEN s.fwd_xs_ret_10d
    WHEN 20 THEN s.fwd_xs_ret_20d
  END,
  TO_JSON_STRING(STRUCT(
    s.list_age_td AS list_age_td,
    s.ret_1d AS ret_1d, s.ret_3d AS ret_3d, s.ret_5d AS ret_5d,
    s.ret_10d AS ret_10d, s.ret_20d AS ret_20d, s.ret_60d AS ret_60d,
    s.mom_20_5 AS mom_20_5, s.mom_60_20 AS mom_60_20,
    s.vol_5d AS vol_5d, s.vol_20d AS vol_20d, s.vol_60d AS vol_60d,
    s.drawdown_20d AS drawdown_20d, s.hl_range_20d AS hl_range_20d,
    s.amount_ma20_cny AS amount_ma20_cny, s.amount_zscore_20d AS amount_zscore_20d,
    s.turnover_rate AS turnover_rate, s.turnover_rate_free_float AS turnover_rate_free_float,
    s.turnover_rate_ma20 AS turnover_rate_ma20, s.volume_ratio AS volume_ratio,
    s.pe_ttm AS pe_ttm, s.pb AS pb, s.ps_ttm AS ps_ttm,
    s.dividend_yield_ttm AS dividend_yield_ttm, s.ep_ttm AS ep_ttm, s.bp AS bp, s.sp_ttm AS sp_ttm,
    s.log_total_mv AS log_total_mv, s.log_circ_mv AS log_circ_mv,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.has_fin_indicator, NULL) AS has_fin_indicator,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.has_fin_income, NULL) AS has_fin_income,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.has_fin_balancesheet, NULL) AS has_fin_balancesheet,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.has_fin_cashflow, NULL) AS has_fin_cashflow,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.report_age_days, NULL) AS report_age_days,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.fin_report_lag_days, NULL) AS fin_report_lag_days,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.roe, NULL) AS roe,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.roe_deducted, NULL) AS roe_deducted,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.roa, NULL) AS roa,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.roic, NULL) AS roic,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.grossprofit_margin, NULL) AS grossprofit_margin,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.netprofit_margin, NULL) AS netprofit_margin,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.debt_to_assets, NULL) AS debt_to_assets,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.current_ratio, NULL) AS current_ratio,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.quick_ratio, NULL) AS quick_ratio,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.assets_to_equity, NULL) AS assets_to_equity,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.ocf_to_or, NULL) AS ocf_to_or,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.ocf_to_profit, NULL) AS ocf_to_profit,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.cash_ratio, NULL) AS cash_ratio,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.netprofit_yoy, NULL) AS netprofit_yoy,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.operating_revenue_yoy, NULL) AS operating_revenue_yoy,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.total_revenue_yoy, NULL) AS total_revenue_yoy,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.basic_eps_yoy, NULL) AS basic_eps_yoy,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.q_roe, NULL) AS q_roe,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.q_netprofit_margin, NULL) AS q_netprofit_margin,
    IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603', fin.q_grossprofit_margin, NULL) AS q_grossprofit_margin,
    s.board AS board
  )),
  ARRAY_CONCAT(
  ['list_age_td','ret_1d','ret_3d','ret_5d','ret_10d','ret_20d','ret_60d',
   'mom_20_5','mom_60_20','vol_5d','vol_20d','vol_60d',
   'drawdown_20d','hl_range_20d','amount_ma20_cny','amount_zscore_20d',
   'turnover_rate','turnover_rate_free_float','turnover_rate_ma20','volume_ratio',
   'pe_ttm','pb','ps_ttm','dividend_yield_ttm','ep_ttm','bp','sp_ttm',
   'log_total_mv','log_circ_mv'],
  IF(p_feature_set_id = 'strategy1_pv_fin_quality_v0_20260603',
    ['has_fin_indicator','has_fin_income','has_fin_balancesheet','has_fin_cashflow',
     'report_age_days','fin_report_lag_days',
     'roe','roe_deducted','roa','roic','grossprofit_margin','netprofit_margin',
     'debt_to_assets','current_ratio','quick_ratio','assets_to_equity',
     'ocf_to_or','ocf_to_profit','cash_ratio',
     'netprofit_yoy','operating_revenue_yoy','total_revenue_yoy','basic_eps_yoy',
     'q_roe','q_netprofit_margin','q_grossprofit_margin'],
    [])
  ),
  CURRENT_TIMESTAMP()
FROM `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
LEFT JOIN `data-aquarium.ashare_dws.dws_stock_feature_fin_daily` AS fin
  ON fin.trade_date = s.trade_date
 AND fin.sec_code = s.sec_code
 AND fin.feature_version = p_fin_feature_version
 AND fin.trade_date BETWEEN p_train_start AND p_test_end
WHERE s.trade_date BETWEEN p_train_start AND p_test_end
  AND s.feature_version = p_feature_version
  AND s.label_version = p_label_version
  AND (
    -- train: 允许使用标签有效性筛选（训练需要目标标签）
    (s.trade_date BETWEEN p_train_start AND p_train_end
      AND COALESCE(s.in_universe_default, FALSE)
      AND COALESCE(s.has_full_history_60d, FALSE)
      AND COALESCE(s.has_valuation_data, FALSE)
      AND COALESCE(s.label_entry_tradable, FALSE)
      AND CASE p_label_horizon
        WHEN 5 THEN COALESCE(s.label_valid_5d, FALSE) AND s.label_top30_5d IS NOT NULL AND s.fwd_xs_ret_5d IS NOT NULL
        WHEN 10 THEN COALESCE(s.label_valid_10d, FALSE) AND s.label_top30_10d IS NOT NULL AND s.fwd_xs_ret_10d IS NOT NULL
        WHEN 20 THEN COALESCE(s.label_valid_20d, FALSE) AND s.label_top30_20d IS NOT NULL AND s.fwd_xs_ret_20d IS NOT NULL
      END)
    OR
    -- valid/test: live-available prediction pool（t 日已知条件，不含未来标签/可交易性）
    (s.trade_date BETWEEN p_valid_start AND p_test_end
      AND COALESCE(s.in_universe_default, FALSE)
      AND COALESCE(s.has_full_history_60d, FALSE)
      AND COALESCE(s.has_valuation_data, FALSE))
  );
