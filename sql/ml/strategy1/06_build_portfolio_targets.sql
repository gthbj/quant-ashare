-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 06: 从候选池生成等权目标组合，写 ads_portfolio_target_daily。

DECLARE p_run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_horizon INT64 DEFAULT 5;
DECLARE p_predict_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_predict_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_max_single_weight FLOAT64 DEFAULT 0.20;  -- OQ-010 示例值
DECLARE p_initial_capital FLOAT64 DEFAULT 100000.0;  -- OQ-010 示例值，用于估算目标金额
DECLARE p_force_replace BOOL DEFAULT FALSE;

DECLARE p_selected_model_id STRING;
SET p_selected_model_id = (
  SELECT reg.model_id
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
  ORDER BY reg.created_at DESC LIMIT 1
);

IF p_force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
  WHERE pt.strategy_id = p_strategy_id AND pt.run_id = p_run_id
    AND pt.rebalance_date BETWEEN p_predict_start AND p_predict_end;
END IF;

INSERT INTO `data-aquarium.ashare_ads.ads_portfolio_target_daily`
(strategy_id, rebalance_date, sec_code, target_weight, target_shares, target_amount_cny,
 model_id, horizon, run_id, created_at)
WITH sel AS (
  SELECT cand.rebalance_date, cand.sec_code,
         COUNT(*) OVER (PARTITION BY cand.rebalance_date) AS n_selected
  FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
  WHERE cand.strategy_id = p_strategy_id AND cand.run_id = p_run_id
    AND cand.is_selected_candidate
    AND cand.rebalance_date BETWEEN p_predict_start AND p_predict_end
)
SELECT
  p_strategy_id, rebalance_date, sec_code,
  LEAST(SAFE_DIVIDE(1.0, n_selected), p_max_single_weight) AS target_weight,
  CAST(NULL AS FLOAT64) AS target_shares,  -- 实际股数由 08 按 t+1 开盘价和滚动 NAV 计算
  LEAST(SAFE_DIVIDE(1.0, n_selected), p_max_single_weight) * p_initial_capital AS target_amount_cny,
  p_selected_model_id, p_horizon, p_run_id, CURRENT_TIMESTAMP()
FROM sel;
