-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 04: 用 selected model 对 valid/test 全量预测，写 ads_model_prediction_daily。

-- ── 运行参数 ──
DECLARE run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE horizon INT64 DEFAULT 5;
DECLARE predict_start_date DATE DEFAULT DATE '2024-01-01';
DECLARE predict_end_date DATE DEFAULT DATE '2025-12-31';
DECLARE force_replace BOOL DEFAULT FALSE;

-- ── 获取 selected model_id ──
DECLARE selected_model_id STRING;
SET selected_model_id = (
  SELECT model_id
  FROM `data-aquarium.ashare_ads.ads_model_registry`
  WHERE strategy_id = strategy_id AND status = 'selected'
  ORDER BY created_at DESC LIMIT 1
);

IF selected_model_id IS NULL THEN
  RAISE USING MESSAGE = 'No selected model found. Run 03_select_model_and_register.sql first.';
END IF;

-- ── 幂等 ──
IF NOT force_replace THEN
  IF (SELECT COUNT(*) > 0
      FROM `data-aquarium.ashare_ads.ads_model_prediction_daily`
      WHERE model_id = selected_model_id AND run_id = run_id
        AND predict_date BETWEEN predict_start_date AND predict_end_date) THEN
    RAISE USING MESSAGE = CONCAT('Predictions already exist for model_id=', selected_model_id, ', run_id=', run_id);
  END IF;
END IF;

IF force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_model_prediction_daily`
  WHERE model_id = selected_model_id AND run_id = run_id
    AND predict_date BETWEEN predict_start_date AND predict_end_date;
END IF;

-- ── 动态模型引用无法参数化，用 selected model 的 URI 回查模型名 ──
-- 此处假设 selected model 是 5 个候选之一，按 model_id 后缀定位
-- 实际执行时需要把下面的 MODEL 引用替换为 selected model 的完整名

-- 首版用两步走：先预测到临时表，再做排序写入 ADS
CREATE TEMP TABLE raw_predictions AS
SELECT
  p.trade_date AS predict_date,
  p.sec_code,
  prob.prob AS score
FROM ML.PREDICT(
  MODEL `data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_0_l2_1e_3`,
  (SELECT trade_date, sec_code,
          list_age_td, ret_1d, ret_3d, ret_5d, ret_10d, ret_20d, ret_60d,
          mom_20_5, mom_60_20, vol_5d, vol_20d, vol_60d,
          drawdown_20d, hl_range_20d, amount_ma20_cny, amount_zscore_20d,
          turnover_rate, turnover_rate_free_float, turnover_rate_ma20, volume_ratio,
          pe_ttm, pb, ps_ttm, dividend_yield_ttm, ep_ttm, bp, sp_ttm,
          log_total_mv, log_circ_mv
   FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
   WHERE run_id = run_id
     AND split_tag IN ('valid', 'test')
     AND trade_date BETWEEN predict_start_date AND predict_end_date)
) AS p, UNNEST(p.predicted_target_label_probs) AS prob
WHERE prob.label = 1;

INSERT INTO `data-aquarium.ashare_ads.ads_model_prediction_daily`
(model_id, predict_date, horizon, sec_code, score, rank_raw, rank_pct,
 feature_version, run_id, created_at)
SELECT
  selected_model_id AS model_id,
  predict_date,
  horizon,
  sec_code,
  score,
  ROW_NUMBER() OVER (PARTITION BY predict_date ORDER BY score DESC, sec_code) AS rank_raw,
  1.0 - SAFE_DIVIDE(
    ROW_NUMBER() OVER (PARTITION BY predict_date ORDER BY score DESC, sec_code) - 1,
    COUNT(*) OVER (PARTITION BY predict_date) - 1
  ) AS rank_pct,
  feature_version,
  run_id,
  CURRENT_TIMESTAMP()
FROM raw_predictions;
