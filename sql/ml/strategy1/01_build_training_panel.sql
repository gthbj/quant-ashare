-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 01: 从 DWS sample 构建冻结训练面板，写入 ads_ml_training_panel_daily。

-- ── 运行参数 ──
DECLARE run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE model_id_prefix STRING DEFAULT 'ml_pv_clf_v0_bqml_logit';
DECLARE preprocess_version STRING DEFAULT 'raw_v0';
DECLARE feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE label_version STRING DEFAULT 'open_to_close_h1_5_10_20_v20260601';
DECLARE horizon INT64 DEFAULT 5;
DECLARE train_start_date DATE DEFAULT DATE '2019-04-03';
DECLARE train_end_date DATE DEFAULT DATE '2023-12-31';
DECLARE valid_start_date DATE DEFAULT DATE '2024-01-01';
DECLARE valid_end_date DATE DEFAULT DATE '2024-12-31';
DECLARE test_start_date DATE DEFAULT DATE '2025-01-01';
DECLARE test_end_date DATE DEFAULT DATE '2025-12-31';
DECLARE force_replace BOOL DEFAULT FALSE;

-- ── 幂等检查 ──
IF NOT force_replace THEN
  IF (SELECT COUNT(*) > 0
      FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
      WHERE run_id = run_id
        AND trade_date BETWEEN train_start_date AND test_end_date) THEN
    RAISE USING MESSAGE = CONCAT('run_id ', run_id, ' already exists in training panel. Set force_replace=TRUE to overwrite.');
  END IF;
END IF;

IF force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
  WHERE run_id = run_id
    AND trade_date BETWEEN train_start_date AND test_end_date;
END IF;

-- ── 特征列清单（与 runner 设计 §5.2 白名单一致）──
-- board 保留在面板做暴露监控，但不进入模型训练列

INSERT INTO `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
(run_id, strategy_id, model_id, preprocess_version, feature_version, label_version,
 universe_version, trade_date, sec_code, horizon, split_fold, split_tag,
 sample_weight, target_label, target_return,
 feature_values_json, feature_column_list, created_at)
SELECT
  run_id,
  strategy_id,
  CAST(NULL AS STRING) AS model_id,
  preprocess_version,
  s.feature_version,
  s.label_version,
  s.universe_version,
  s.trade_date,
  s.sec_code,
  horizon,
  s.split_fold,
  CASE
    WHEN s.trade_date BETWEEN train_start_date AND train_end_date THEN 'train'
    WHEN s.trade_date BETWEEN valid_start_date AND valid_end_date THEN 'valid'
    WHEN s.trade_date BETWEEN test_start_date AND test_end_date THEN 'test'
    ELSE 'live'
  END AS split_tag,
  1.0 AS sample_weight,
  s.label_top30_5d AS target_label,
  s.fwd_xs_ret_5d AS target_return,
  TO_JSON_STRING(STRUCT(
    s.list_age_td,
    s.ret_1d, s.ret_3d, s.ret_5d, s.ret_10d, s.ret_20d, s.ret_60d,
    s.mom_20_5, s.mom_60_20,
    s.vol_5d, s.vol_20d, s.vol_60d,
    s.drawdown_20d, s.hl_range_20d,
    s.amount_ma20_cny, s.amount_zscore_20d,
    s.turnover_rate, s.turnover_rate_free_float, s.turnover_rate_ma20, s.volume_ratio,
    s.pe_ttm, s.pb, s.ps_ttm, s.dividend_yield_ttm, s.ep_ttm, s.bp, s.sp_ttm,
    s.log_total_mv, s.log_circ_mv,
    s.board
  )) AS feature_values_json,
  ['list_age_td',
   'ret_1d','ret_3d','ret_5d','ret_10d','ret_20d','ret_60d',
   'mom_20_5','mom_60_20',
   'vol_5d','vol_20d','vol_60d',
   'drawdown_20d','hl_range_20d',
   'amount_ma20_cny','amount_zscore_20d',
   'turnover_rate','turnover_rate_free_float','turnover_rate_ma20','volume_ratio',
   'pe_ttm','pb','ps_ttm','dividend_yield_ttm','ep_ttm','bp','sp_ttm',
   'log_total_mv','log_circ_mv'] AS feature_column_list,
  CURRENT_TIMESTAMP() AS created_at
FROM `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
WHERE s.trade_date BETWEEN train_start_date AND test_end_date
  AND s.feature_version = feature_version
  AND s.label_version = label_version
  AND s.sample_trainable_default;
