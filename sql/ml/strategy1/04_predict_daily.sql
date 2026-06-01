-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 04: 持久化 selected model 的 valid+test 预测到 ads_model_prediction_daily。
-- 03 已把全部候选在 valid 上的预测写入 _tmp_selected_valid_preds；
-- 本脚本对 test 窗口用 EXECUTE IMMEDIATE 动态引用 selected model 做增量预测，
-- 再合并 valid+test 写入 ADS。

DECLARE p_run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_horizon INT64 DEFAULT 5;
DECLARE p_valid_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_valid_end DATE DEFAULT DATE '2024-12-31';
DECLARE p_test_start DATE DEFAULT DATE '2025-01-01';
DECLARE p_test_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_force_replace BOOL DEFAULT FALSE;

-- ── 获取 selected model ──
DECLARE p_selected_model_id STRING;
DECLARE p_selected_model_uri STRING;
SET (p_selected_model_id, p_selected_model_uri) = (
  SELECT AS STRUCT reg.model_id, reg.model_uri
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
  ORDER BY reg.created_at DESC LIMIT 1
);

IF p_selected_model_id IS NULL THEN
  RAISE USING MESSAGE = 'No selected model for this run_id. Run 03 first.';
END IF;

-- ── 幂等 ──
IF NOT p_force_replace THEN
  IF (SELECT COUNT(*) > 0
      FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
      WHERE pred.model_id = p_selected_model_id AND pred.run_id = p_run_id
        AND pred.predict_date BETWEEN p_valid_start AND p_test_end) THEN
    RAISE USING MESSAGE = CONCAT('Predictions exist for model_id=', p_selected_model_id, ', run_id=', p_run_id);
  END IF;
END IF;

IF p_force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  WHERE pred.model_id = p_selected_model_id AND pred.run_id = p_run_id
    AND pred.predict_date BETWEEN p_valid_start AND p_test_end;
END IF;

-- ── test 窗口预测：用 EXECUTE IMMEDIATE 动态引用 selected model ──
-- 提取 model 的 BigQuery 路径（去掉 bq:// 前缀）
DECLARE p_model_bq_path STRING;
SET p_model_bq_path = REPLACE(p_selected_model_uri, 'bq://', '');

EXECUTE IMMEDIATE FORMAT("""
  CREATE OR REPLACE TEMP TABLE _test_preds AS
  SELECT p.trade_date, p.sec_code, prob.prob AS score
  FROM ML.PREDICT(MODEL `%s`,
    (SELECT tp.trade_date, tp.sec_code,
            tp.list_age_td, tp.ret_1d, tp.ret_3d, tp.ret_5d, tp.ret_10d, tp.ret_20d, tp.ret_60d,
            tp.mom_20_5, tp.mom_60_20, tp.vol_5d, tp.vol_20d, tp.vol_60d,
            tp.drawdown_20d, tp.hl_range_20d, tp.amount_ma20_cny, tp.amount_zscore_20d,
            tp.turnover_rate, tp.turnover_rate_free_float, tp.turnover_rate_ma20, tp.volume_ratio,
            tp.pe_ttm, tp.pb, tp.ps_ttm, tp.dividend_yield_ttm, tp.ep_ttm, tp.bp, tp.sp_ttm,
            tp.log_total_mv, tp.log_circ_mv
     FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
     WHERE tp.run_id = '%s' AND tp.split_tag = 'test'
       AND tp.trade_date BETWEEN '%s' AND '%s')
  ) AS p, UNNEST(p.predicted_target_label_probs) AS prob
  WHERE CAST(prob.label AS STRING) = '1'
""", p_model_bq_path, p_run_id,
     CAST(p_test_start AS STRING), CAST(p_test_end AS STRING));

-- ── 合并 valid（03 已计算）+ test 预测，做横截面排序，写入 ADS ──
INSERT INTO `data-aquarium.ashare_ads.ads_model_prediction_daily`
(model_id, predict_date, horizon, sec_code, score, rank_raw, rank_pct,
 feature_version, run_id, created_at)
WITH all_preds AS (
  SELECT trade_date AS predict_date, sec_code, score
  FROM `data-aquarium.ashare_ads._tmp_selected_valid_preds`
  UNION ALL
  SELECT trade_date, sec_code, score FROM _test_preds
)
SELECT
  p_selected_model_id,
  predict_date,
  p_horizon,
  sec_code,
  score,
  ROW_NUMBER() OVER (PARTITION BY predict_date ORDER BY score DESC, sec_code) AS rank_raw,
  1.0 - SAFE_DIVIDE(
    ROW_NUMBER() OVER (PARTITION BY predict_date ORDER BY score DESC, sec_code) - 1,
    COUNT(*) OVER (PARTITION BY predict_date) - 1
  ) AS rank_pct,
  p_feature_version,
  p_run_id,
  CURRENT_TIMESTAMP()
FROM all_preds;

-- ── 清理临时表 ──
DROP TABLE IF EXISTS `data-aquarium.ashare_ads._tmp_selected_valid_preds`;
