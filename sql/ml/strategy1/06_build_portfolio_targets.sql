-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 06: 从候选池生成目标组合权重，写 ads_portfolio_target_daily。

-- ── 运行参数 ──
DECLARE run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE horizon INT64 DEFAULT 5;
DECLARE predict_start_date DATE DEFAULT DATE '2024-01-01';
DECLARE predict_end_date DATE DEFAULT DATE '2025-12-31';
-- OQ-010: 示例值，非业务定稿
DECLARE max_single_weight FLOAT64 DEFAULT 0.20;
DECLARE force_replace BOOL DEFAULT FALSE;

DECLARE selected_model_id STRING;
SET selected_model_id = (
  SELECT model_id
  FROM `data-aquarium.ashare_ads.ads_model_registry`
  WHERE strategy_id = strategy_id AND status = 'selected'
  ORDER BY created_at DESC LIMIT 1
);

IF force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily`
  WHERE strategy_id = strategy_id AND run_id = run_id
    AND rebalance_date BETWEEN predict_start_date AND predict_end_date;
END IF;

INSERT INTO `data-aquarium.ashare_ads.ads_portfolio_target_daily`
(strategy_id, rebalance_date, sec_code, target_weight, target_shares, target_amount_cny,
 model_id, horizon, run_id, created_at)
WITH selected_stocks AS (
  SELECT rebalance_date, sec_code,
         COUNT(*) OVER (PARTITION BY rebalance_date) AS n_selected
  FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily`
  WHERE strategy_id = strategy_id AND run_id = run_id AND is_selected_candidate
    AND rebalance_date BETWEEN predict_start_date AND predict_end_date
)
SELECT
  strategy_id,
  rebalance_date,
  sec_code,
  LEAST(SAFE_DIVIDE(1.0, n_selected), max_single_weight) AS target_weight,
  CAST(NULL AS FLOAT64) AS target_shares,
  CAST(NULL AS FLOAT64) AS target_amount_cny,
  selected_model_id,
  horizon,
  run_id,
  CURRENT_TIMESTAMP()
FROM selected_stocks;
