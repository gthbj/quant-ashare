-- BigQuery Standard SQL · Strategy 1 risk-feature search QA
-- 21: 断言 PRD_20260606_03 风险特征入模搜索的特征契约、市场状态覆盖和风险回撤门。

DECLARE p_search_id STRING DEFAULT 'cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_20260606_01';
DECLARE p_source_run_id STRING DEFAULT 's1_cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_20260606_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_expected_feature_set_id STRING DEFAULT 'strategy1_pv_fin_risk_v0_20260606';
DECLARE p_expected_model_search_wave_no INT64 DEFAULT 4;
DECLARE p_top_k INT64 DEFAULT 5;
DECLARE p_test_reuse_wave_no INT64 DEFAULT 4;
DECLARE p_test_reuse_approval_ref STRING DEFAULT 'docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md';
DECLARE p_market_state_version STRING DEFAULT 'market_state_v0_20260606';
DECLARE p_train_start_date DATE DEFAULT DATE '2019-04-03';
DECLARE p_data_end_date DATE DEFAULT DATE '2026-04-30';
DECLARE p_final_holdout_start_date DATE DEFAULT DATE '2026-01-05';
DECLARE p_final_holdout_end_date DATE DEFAULT DATE '2026-04-30';
DECLARE p_risk_feature_max_drawdown_target FLOAT64 DEFAULT NULL;

CREATE TEMP FUNCTION qa_required(condition BOOL) AS (IFNULL(condition, FALSE));

-- QA-RISK-0: 风险回撤目标必须由 acceptance contract 注入，standalone 默认不得静默通过。
ASSERT p_risk_feature_max_drawdown_target IS NOT NULL
  AS 'QA-RISK-0: p_risk_feature_max_drawdown_target must be injected from acceptance contract';

-- QA-RISK-1: Top-K registry 必须登记风险特征集、feature schema/delta hash 和特征计数。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.source_run_id') = p_source_run_id))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.feature_set_id') = p_expected_feature_set_id))
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.feature_count') AS INT64) >= 90))
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.risk_feature_count') AS INT64) >= 40))
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.market_state_feature_count') AS INT64) >= 26))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.market_state_features_enabled') = 'true'))
    AND LOGICAL_AND(qa_required(LENGTH(JSON_VALUE(reg.metrics_json, '$.feature_schema_sha256')) >= 16))
    AND LOGICAL_AND(qa_required(LENGTH(JSON_VALUE(reg.metrics_json, '$.feature_delta_vs_base_sha256')) >= 16))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-RISK-1: registry must trace risk feature set, feature counts and feature schema/delta hashes';

-- QA-RISK-2: 训练面板 feature_column_list 必须包含风险特征和市场状态核心字段。
ASSERT (
  WITH required_features AS (
    SELECT feature_name
    FROM UNNEST([
      'limit_down_days_20d',
      'one_word_limit_days_20d',
      'total_mv_cny',
      'circ_mv_cny',
      'risk_ret20_lt_30pct',
      'risk_drawdown20_lt_30pct',
      'risk_limit_down_20d_ge2',
      'risk_one_word_limit_20d_ge1',
      'risk_microcap_total_mv',
      'risk_microcap_circ_mv',
      'csi300_ret_20d',
      'csi1000_ret_20d',
      'csi1000_drawdown_20d',
      'adv_ratio_1d',
      'above_ma20_ratio',
      'new_low_20d_ratio',
      'limit_down_count',
      'one_word_limit_down_count',
      'limit_down_mv_ratio',
      'is_smallcap_trend_down',
      'is_breadth_weak',
      'is_limit_down_diffusion',
      'risk_off_trigger_count',
      'is_risk_off',
      'stock_drawdown_x_market_riskoff',
      'stock_vol_x_market_vol',
      'microcap_x_breadth_weak',
      'limitdown_history_x_limitdown_diffusion'
    ]) AS feature_name
  ),
  panel_columns AS (
    SELECT DISTINCT col AS feature_name
    FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp,
    UNNEST(tp.feature_column_list) AS col
    WHERE tp.run_id = p_source_run_id
      AND tp.trade_date BETWEEN p_train_start_date AND p_data_end_date
  )
  SELECT COUNT(*) = 0
  FROM required_features AS req
  LEFT JOIN panel_columns AS pc USING (feature_name)
  WHERE pc.feature_name IS NULL
) AS 'QA-RISK-2: training panel feature_column_list must contain required risk and market-state features';

-- QA-RISK-3: 市场状态表必须覆盖本轮所有训练面板交易日，且按版本唯一。
ASSERT (
  WITH panel_dates AS (
    SELECT DISTINCT tp.trade_date
    FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
    WHERE tp.run_id = p_source_run_id
      AND tp.trade_date BETWEEN p_train_start_date AND p_data_end_date
  ),
  market_state AS (
    SELECT ms.trade_date, COUNT(*) AS n
    FROM `data-aquarium.ashare_dws.dws_market_state_daily` AS ms
    WHERE ms.trade_date BETWEEN p_train_start_date AND p_data_end_date
      AND ms.market_state_version = p_market_state_version
    GROUP BY ms.trade_date
  )
  SELECT COUNT(*) = 0
  FROM panel_dates AS pd
  LEFT JOIN market_state AS ms USING (trade_date)
  WHERE IFNULL(ms.n, 0) != 1
) AS 'QA-RISK-3: market-state table must cover every panel trade_date exactly once';

-- QA-RISK-4: 核心市场状态字段不得在面板中整日缺失，整体缺失率必须很低。
ASSERT (
  WITH panel AS (
    SELECT
      tp.trade_date,
      JSON_VALUE(tp.feature_values_json, '$.csi1000_ret_20d') AS csi1000_ret_20d
    FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
    WHERE tp.run_id = p_source_run_id
      AND tp.trade_date BETWEEN p_train_start_date AND p_data_end_date
  ),
  day_missing AS (
    SELECT trade_date, COUNTIF(csi1000_ret_20d IS NOT NULL) AS non_null_rows
    FROM panel
    GROUP BY trade_date
  )
  SELECT SAFE_DIVIDE(COUNTIF(csi1000_ret_20d IS NULL), COUNT(*)) <= 0.001
    AND (SELECT COUNTIF(non_null_rows = 0) = 0 FROM day_missing)
  FROM panel
) AS 'QA-RISK-4: csi1000_ret_20d must not be materially missing in risk feature panel';

-- QA-RISK-5: Top-K 必须记录 wave 4/test reuse approval，避免把复用测试集误当全新证据。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.model_search_wave_no') AS INT64) = p_expected_model_search_wave_no))
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_reuse_wave_no') AS INT64) = p_test_reuse_wave_no))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.test_reuse_approval_ref') = p_test_reuse_approval_ref))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-RISK-5: risk feature search must record wave 4 test reuse approval';

-- QA-RISK-6: accepted 风险特征候选必须满足 -18% 最大回撤目标和 final_holdout passed。
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  JOIN `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
    ON bs.model_id = reg.model_id
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
    AND JSON_VALUE(reg.metrics_json, '$.native_acceptance_status') = 'accepted'
    AND (
      NOT IFNULL(bs.max_drawdown >= p_risk_feature_max_drawdown_target, FALSE)
      OR NOT IFNULL(JSON_VALUE(reg.metrics_json, '$.final_holdout_status') = 'passed', FALSE)
      OR NOT IFNULL(
        SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.risk_feature_max_drawdown_target') AS FLOAT64)
          = p_risk_feature_max_drawdown_target,
        FALSE
      )
    )
) AS 'QA-RISK-6: accepted risk-feature candidates must pass final_holdout and -18% max-drawdown target';

-- QA-RISK-7: 未达 -18% 风险目标的候选不得 accepted，且原因应显式记录。
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  JOIN `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
    ON bs.model_id = reg.model_id
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
    AND bs.max_drawdown < p_risk_feature_max_drawdown_target
    AND JSON_VALUE(reg.metrics_json, '$.native_acceptance_status') = 'accepted'
) AS 'QA-RISK-7: candidates below risk max-drawdown target must not be accepted';

-- QA-RISK-8: 风险特征搜索必须输出特征重要性聚合，支持判断新增风险特征是否被模型使用。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.feature_importance_available') = 'true'))
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.risk_feature_importance_gain_share') AS FLOAT64) IS NOT NULL))
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.market_state_importance_gain_share') AS FLOAT64) IS NOT NULL))
    AND LOGICAL_AND(qa_required(JSON_QUERY(reg.metrics_json, '$.feature_group_importance') IS NOT NULL))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-RISK-8: risk feature search must publish feature group importance metrics';

-- QA-RISK-9: 回测摘要必须沿用 diagnostic_only tail-risk profile。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(JSON_VALUE(bs.metrics_json, '$.tail_risk_profile_id') = 'diagnostic_only'))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  JOIN `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
    ON bs.model_id = reg.model_id
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-RISK-9: risk feature search must keep tail-risk profile diagnostic_only';

-- QA-RISK-10: final holdout 分区必须有预测和 NAV 产物，防止只跑到 2025。
ASSERT (
  WITH topk AS (
    SELECT
      JSON_VALUE(reg.model_params_json, '$.run_id') AS run_id,
      bs.backtest_id
    FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
    JOIN `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
      ON bs.model_id = reg.model_id
    WHERE reg.strategy_id = p_strategy_id
      AND reg.status = 'selected'
      AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
  ),
  pred AS (
    SELECT COUNT(*) AS n
    FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
    JOIN topk USING (run_id)
    WHERE pred.predict_date BETWEEN p_final_holdout_start_date AND p_final_holdout_end_date
  ),
  nav AS (
    SELECT COUNT(*) AS n
    FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
    JOIN topk USING (run_id)
    WHERE nav.trade_date BETWEEN p_final_holdout_start_date AND p_final_holdout_end_date
  )
  SELECT (SELECT n FROM pred) > 0 AND (SELECT n FROM nav) > 0
) AS 'QA-RISK-10: final holdout prediction and NAV outputs must exist';
