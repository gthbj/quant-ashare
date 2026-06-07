-- BigQuery Standard SQL · Strategy 1 Cloud Run Python matrix panel
-- Builds run-scoped model input rows in ads_ml_training_panel_daily.
-- This path is backend-neutral for Cloud Run Python training; historical BQML
-- scripts remain reference/audit only.

DECLARE p_run_id STRING DEFAULT 's1_cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_20260606_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_experiment_id STRING DEFAULT 'cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_search_v0';
DECLARE p_experiment_group STRING DEFAULT 'cloudrun_python_risk_feature_search';
DECLARE p_baseline_experiment_id STRING DEFAULT 'oq010_bqml_baseline_pvfq_n30_bw_h5';
DECLARE p_parent_experiment_id STRING DEFAULT 'cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_search_v0';
DECLARE p_parent_run_id STRING DEFAULT 's1_cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01';
DECLARE p_preprocess_version STRING DEFAULT 'raw_v0';
DECLARE p_feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_feature_set_id STRING DEFAULT 'strategy1_pv_fin_risk_v0_20260606';
DECLARE p_fin_feature_version STRING DEFAULT 'fin_default_v0_20260602';
DECLARE p_market_state_version STRING DEFAULT 'market_state_v0_20260606';
DECLARE p_label_version STRING DEFAULT 'open_to_close_h1_5_10_20_v20260601';
DECLARE p_label_horizon INT64 DEFAULT 5;
DECLARE p_rebalance_frequency STRING DEFAULT 'biweekly';
DECLARE p_target_holdings INT64 DEFAULT 30;
DECLARE p_max_single_weight FLOAT64 DEFAULT 0.05;
DECLARE p_horizon_natural_frequency STRING DEFAULT 'weekly';
DECLARE p_train_start DATE DEFAULT DATE '2019-04-03';
DECLARE p_train_end DATE DEFAULT DATE '2023-12-31';
DECLARE p_valid_start DATE DEFAULT DATE '2024-01-02';
DECLARE p_valid_end DATE DEFAULT DATE '2024-12-31';
DECLARE p_test_start DATE DEFAULT DATE '2025-01-02';
DECLARE p_test_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_final_holdout_start DATE DEFAULT DATE '2026-01-05';
DECLARE p_final_holdout_end DATE DEFAULT DATE '2026-04-30';
DECLARE p_force_replace BOOL DEFAULT FALSE;
DECLARE p_panel_end DATE DEFAULT COALESCE(p_final_holdout_end, p_test_end);
DECLARE p_fin_enabled BOOL DEFAULT p_feature_set_id IN (
  'strategy1_pv_fin_quality_v0_20260603',
  'strategy1_pv_fin_risk_v0_20260606'
);
DECLARE p_risk_enabled BOOL DEFAULT p_feature_set_id = 'strategy1_pv_fin_risk_v0_20260606';

IF p_label_horizon NOT IN (5, 10, 20) THEN
  RAISE USING MESSAGE = 'p_label_horizon must be one of 5, 10, 20';
END IF;

IF p_feature_set_id NOT IN (
  'strategy1_pv_v0_20260601',
  'strategy1_pv_fin_quality_v0_20260603',
  'strategy1_pv_fin_risk_v0_20260606'
) THEN
  RAISE USING MESSAGE = CONCAT('unsupported p_feature_set_id: ', p_feature_set_id);
END IF;

IF p_risk_enabled THEN
  ASSERT (
    SELECT COUNT(*) = COUNT(DISTINCT ms.trade_date)
    FROM `data-aquarium.ashare_dws.dws_market_state_daily` AS ms
    WHERE ms.trade_date BETWEEN p_train_start AND p_panel_end
      AND ms.market_state_version = p_market_state_version
  ) AS 'dws_market_state_daily must be unique by trade_date for requested market_state_version';

  ASSERT (
    SELECT COUNT(*) = (
      SELECT COUNT(*)
      FROM `data-aquarium.ashare_dim.dim_trade_calendar` AS cal
      WHERE cal.exchange = 'SSE'
        AND cal.is_open = 1
        AND cal.cal_date BETWEEN p_train_start AND p_panel_end
    )
    FROM `data-aquarium.ashare_dws.dws_market_state_daily` AS ms
    WHERE ms.trade_date BETWEEN p_train_start AND p_panel_end
      AND ms.market_state_version = p_market_state_version
  ) AS 'dws_market_state_daily must cover every SSE trading day in panel window';
END IF;

IF NOT p_force_replace THEN
  IF (SELECT COUNT(*) > 0
      FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
      WHERE tp.run_id = p_run_id
        AND tp.trade_date BETWEEN p_train_start AND p_panel_end) THEN
    RAISE USING MESSAGE = CONCAT('run_id ', p_run_id, ' already exists. Set p_force_replace=TRUE to overwrite.');
  END IF;
END IF;

IF p_force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
  WHERE tp.run_id = p_run_id
    AND tp.trade_date BETWEEN p_train_start AND p_panel_end;
END IF;

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
    WHEN p_final_holdout_start IS NOT NULL
      AND p_final_holdout_end IS NOT NULL
      AND s.trade_date BETWEEN p_final_holdout_start AND p_final_holdout_end THEN 'final_holdout'
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
    IF(p_fin_enabled, fin.has_fin_indicator, NULL) AS has_fin_indicator,
    IF(p_fin_enabled, fin.has_fin_income, NULL) AS has_fin_income,
    IF(p_fin_enabled, fin.has_fin_balancesheet, NULL) AS has_fin_balancesheet,
    IF(p_fin_enabled, fin.has_fin_cashflow, NULL) AS has_fin_cashflow,
    IF(p_fin_enabled, fin.report_age_days, NULL) AS report_age_days,
    IF(p_fin_enabled, fin.fin_report_lag_days, NULL) AS fin_report_lag_days,
    IF(p_fin_enabled, fin.roe, NULL) AS roe,
    IF(p_fin_enabled, fin.roe_deducted, NULL) AS roe_deducted,
    IF(p_fin_enabled, fin.roa, NULL) AS roa,
    IF(p_fin_enabled, fin.roic, NULL) AS roic,
    IF(p_fin_enabled, fin.grossprofit_margin, NULL) AS grossprofit_margin,
    IF(p_fin_enabled, fin.netprofit_margin, NULL) AS netprofit_margin,
    IF(p_fin_enabled, fin.debt_to_assets, NULL) AS debt_to_assets,
    IF(p_fin_enabled, fin.current_ratio, NULL) AS current_ratio,
    IF(p_fin_enabled, fin.quick_ratio, NULL) AS quick_ratio,
    IF(p_fin_enabled, fin.assets_to_equity, NULL) AS assets_to_equity,
    IF(p_fin_enabled, fin.ocf_to_or, NULL) AS ocf_to_or,
    IF(p_fin_enabled, fin.ocf_to_profit, NULL) AS ocf_to_profit,
    IF(p_fin_enabled, fin.cash_ratio, NULL) AS cash_ratio,
    IF(p_fin_enabled, fin.netprofit_yoy, NULL) AS netprofit_yoy,
    IF(p_fin_enabled, fin.operating_revenue_yoy, NULL) AS operating_revenue_yoy,
    IF(p_fin_enabled, fin.total_revenue_yoy, NULL) AS total_revenue_yoy,
    IF(p_fin_enabled, fin.basic_eps_yoy, NULL) AS basic_eps_yoy,
    IF(p_fin_enabled, fin.q_roe, NULL) AS q_roe,
    IF(p_fin_enabled, fin.q_netprofit_margin, NULL) AS q_netprofit_margin,
    IF(p_fin_enabled, fin.q_grossprofit_margin, NULL) AS q_grossprofit_margin,
    IF(p_risk_enabled, s.limit_down_days_20d, NULL) AS limit_down_days_20d,
    IF(p_risk_enabled, s.one_word_limit_days_20d, NULL) AS one_word_limit_days_20d,
    IF(p_risk_enabled, s.total_mv_cny, NULL) AS total_mv_cny,
    IF(p_risk_enabled, s.circ_mv_cny, NULL) AS circ_mv_cny,
    IF(p_risk_enabled, CASE WHEN s.ret_20d IS NULL THEN NULL WHEN s.ret_20d < -0.30 THEN 1.0 ELSE 0.0 END, NULL) AS risk_ret20_lt_30pct,
    IF(p_risk_enabled, CASE WHEN s.drawdown_20d IS NULL THEN NULL WHEN s.drawdown_20d < -0.30 THEN 1.0 ELSE 0.0 END, NULL) AS risk_drawdown20_lt_30pct,
    IF(p_risk_enabled, CASE WHEN s.limit_down_days_20d IS NULL THEN NULL WHEN s.limit_down_days_20d >= 2 THEN 1.0 ELSE 0.0 END, NULL) AS risk_limit_down_20d_ge2,
    IF(p_risk_enabled, CASE WHEN s.one_word_limit_days_20d IS NULL THEN NULL WHEN s.one_word_limit_days_20d >= 1 THEN 1.0 ELSE 0.0 END, NULL) AS risk_one_word_limit_20d_ge1,
    IF(p_risk_enabled, CASE WHEN s.total_mv_cny IS NULL THEN NULL WHEN s.total_mv_cny < 30e8 THEN 1.0 ELSE 0.0 END, NULL) AS risk_microcap_total_mv,
    IF(p_risk_enabled, CASE WHEN s.circ_mv_cny IS NULL THEN NULL WHEN s.circ_mv_cny < 20e8 THEN 1.0 ELSE 0.0 END, NULL) AS risk_microcap_circ_mv,
    IF(p_risk_enabled, ms.csi300_ret_5d, NULL) AS csi300_ret_5d,
    IF(p_risk_enabled, ms.csi300_ret_20d, NULL) AS csi300_ret_20d,
    IF(p_risk_enabled, ms.csi300_drawdown_20d, NULL) AS csi300_drawdown_20d,
    IF(p_risk_enabled, ms.csi1000_ret_5d, NULL) AS csi1000_ret_5d,
    IF(p_risk_enabled, ms.csi1000_ret_20d, NULL) AS csi1000_ret_20d,
    IF(p_risk_enabled, ms.csi1000_drawdown_20d, NULL) AS csi1000_drawdown_20d,
    IF(p_risk_enabled, ms.csi1000_close_to_ma20, NULL) AS csi1000_close_to_ma20,
    IF(p_risk_enabled, ms.csi1000_close_to_ma60, NULL) AS csi1000_close_to_ma60,
    IF(p_risk_enabled, ms.csi1000_ma20_to_ma60, NULL) AS csi1000_ma20_to_ma60,
    IF(p_risk_enabled, ms.csi300_vol_20d, NULL) AS csi300_vol_20d,
    IF(p_risk_enabled, ms.csi1000_vol_20d, NULL) AS csi1000_vol_20d,
    IF(p_risk_enabled, ms.avg_vol_20d, NULL) AS avg_vol_20d,
    IF(p_risk_enabled, ms.adv_ratio_1d, NULL) AS adv_ratio_1d,
    IF(p_risk_enabled, ms.above_ma20_ratio, NULL) AS above_ma20_ratio,
    IF(p_risk_enabled, ms.new_low_20d_ratio, NULL) AS new_low_20d_ratio,
    IF(p_risk_enabled, ms.ret_20d_p25, NULL) AS ret_20d_p25,
    IF(p_risk_enabled, ms.ret_20d_median, NULL) AS ret_20d_median,
    IF(p_risk_enabled, ms.drawdown_20d_median, NULL) AS drawdown_20d_median,
    IF(p_risk_enabled, ms.limit_down_count, NULL) AS limit_down_count,
    IF(p_risk_enabled, ms.one_word_limit_down_count, NULL) AS one_word_limit_down_count,
    IF(p_risk_enabled, ms.limit_down_mv_ratio, NULL) AS limit_down_mv_ratio,
    IF(p_risk_enabled, CAST(ms.is_smallcap_trend_down AS INT64), NULL) AS is_smallcap_trend_down,
    IF(p_risk_enabled, CAST(ms.is_breadth_weak AS INT64), NULL) AS is_breadth_weak,
    IF(p_risk_enabled, CAST(ms.is_limit_down_diffusion AS INT64), NULL) AS is_limit_down_diffusion,
    IF(p_risk_enabled, ms.risk_off_trigger_count, NULL) AS risk_off_trigger_count,
    IF(p_risk_enabled, CAST(ms.is_risk_off AS INT64), NULL) AS is_risk_off,
    IF(p_risk_enabled, CASE WHEN s.drawdown_20d IS NULL OR ms.is_risk_off IS NULL THEN NULL ELSE s.drawdown_20d * CAST(ms.is_risk_off AS INT64) END, NULL) AS stock_drawdown_x_market_riskoff,
    IF(p_risk_enabled, CASE WHEN s.vol_20d IS NULL OR ms.csi1000_vol_20d IS NULL THEN NULL ELSE s.vol_20d * ms.csi1000_vol_20d END, NULL) AS stock_vol_x_market_vol,
    IF(p_risk_enabled, CASE WHEN s.circ_mv_cny IS NULL OR ms.is_breadth_weak IS NULL THEN NULL ELSE IF(s.circ_mv_cny < 20e8, 1.0, 0.0) * CAST(ms.is_breadth_weak AS INT64) END, NULL) AS microcap_x_breadth_weak,
    IF(p_risk_enabled, CASE WHEN s.limit_down_days_20d IS NULL OR ms.is_limit_down_diffusion IS NULL THEN NULL ELSE IF(s.limit_down_days_20d >= 2, 1.0, 0.0) * CAST(ms.is_limit_down_diffusion AS INT64) END, NULL) AS limitdown_history_x_limitdown_diffusion,
    s.board AS board
  )),
  ARRAY_CONCAT(
    ['list_age_td','ret_1d','ret_3d','ret_5d','ret_10d','ret_20d','ret_60d',
     'mom_20_5','mom_60_20','vol_5d','vol_20d','vol_60d',
     'drawdown_20d','hl_range_20d','amount_ma20_cny','amount_zscore_20d',
     'turnover_rate','turnover_rate_free_float','turnover_rate_ma20','volume_ratio',
     'pe_ttm','pb','ps_ttm','dividend_yield_ttm','ep_ttm','bp','sp_ttm',
     'log_total_mv','log_circ_mv'],
    IF(p_fin_enabled,
      ['has_fin_indicator','has_fin_income','has_fin_balancesheet','has_fin_cashflow',
       'report_age_days','fin_report_lag_days',
       'roe','roe_deducted','roa','roic','grossprofit_margin','netprofit_margin',
       'debt_to_assets','current_ratio','quick_ratio','assets_to_equity',
       'ocf_to_or','ocf_to_profit','cash_ratio',
       'netprofit_yoy','operating_revenue_yoy','total_revenue_yoy','basic_eps_yoy',
       'q_roe','q_netprofit_margin','q_grossprofit_margin'],
      []),
    IF(p_risk_enabled,
      ['limit_down_days_20d','one_word_limit_days_20d','total_mv_cny','circ_mv_cny',
       'risk_ret20_lt_30pct','risk_drawdown20_lt_30pct','risk_limit_down_20d_ge2',
       'risk_one_word_limit_20d_ge1','risk_microcap_total_mv','risk_microcap_circ_mv',
       'csi300_ret_5d','csi300_ret_20d','csi300_drawdown_20d',
       'csi1000_ret_5d','csi1000_ret_20d','csi1000_drawdown_20d',
       'csi1000_close_to_ma20','csi1000_close_to_ma60','csi1000_ma20_to_ma60',
       'csi300_vol_20d','csi1000_vol_20d','avg_vol_20d','adv_ratio_1d',
       'above_ma20_ratio','new_low_20d_ratio','ret_20d_p25','ret_20d_median',
       'drawdown_20d_median','limit_down_count','one_word_limit_down_count',
       'limit_down_mv_ratio','is_smallcap_trend_down','is_breadth_weak',
       'is_limit_down_diffusion','risk_off_trigger_count','is_risk_off',
       'stock_drawdown_x_market_riskoff','stock_vol_x_market_vol',
       'microcap_x_breadth_weak','limitdown_history_x_limitdown_diffusion'],
      [])
  ),
  CURRENT_TIMESTAMP()
FROM `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
LEFT JOIN `data-aquarium.ashare_dws.dws_stock_feature_fin_daily` AS fin
  ON fin.trade_date = s.trade_date
 AND fin.sec_code = s.sec_code
 AND fin.feature_version = p_fin_feature_version
 AND fin.trade_date BETWEEN p_train_start AND p_panel_end
LEFT JOIN `data-aquarium.ashare_dws.dws_market_state_daily` AS ms
  ON ms.trade_date = s.trade_date
 AND ms.market_state_version = p_market_state_version
 AND ms.trade_date BETWEEN p_train_start AND p_panel_end
WHERE s.trade_date BETWEEN p_train_start AND p_panel_end
  AND s.feature_version = p_feature_version
  AND s.label_version = p_label_version
  AND (
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
    (s.trade_date BETWEEN p_valid_start AND p_panel_end
      AND COALESCE(s.in_universe_default, FALSE)
      AND COALESCE(s.has_full_history_60d, FALSE)
      AND COALESCE(s.has_valuation_data, FALSE))
  );

IF p_risk_enabled THEN
  ASSERT (
    SELECT SAFE_DIVIDE(COUNTIF(JSON_VALUE(tp.feature_values_json, '$.csi1000_ret_20d') IS NULL), COUNT(*)) <= 0.001
    FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
    WHERE tp.run_id = p_run_id
      AND tp.trade_date BETWEEN p_train_start AND p_panel_end
  ) AS 'risk feature panel market-state missing rate must be <= 0.1%';

  ASSERT NOT EXISTS (
    SELECT 1
    FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
    WHERE tp.run_id = p_run_id
      AND tp.trade_date BETWEEN p_train_start AND p_panel_end
    GROUP BY tp.trade_date
    HAVING COUNTIF(JSON_VALUE(tp.feature_values_json, '$.csi1000_ret_20d') IS NOT NULL) = 0
  ) AS 'risk feature panel must not contain a full trading day with missing market-state features';
END IF;
