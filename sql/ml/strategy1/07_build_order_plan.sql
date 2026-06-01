-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 07: 对比上期持仓与本期目标组合，生成 BUY/SELL 订单计划。

-- ── 运行参数 ──
DECLARE run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE predict_start_date DATE DEFAULT DATE '2024-01-01';
DECLARE predict_end_date DATE DEFAULT DATE '2025-12-31';
DECLARE force_replace BOOL DEFAULT FALSE;

IF force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_order_plan_daily`
  WHERE strategy_id = strategy_id AND run_id = run_id
    AND rebalance_date BETWEEN predict_start_date AND predict_end_date;
END IF;

-- ── 调仓日序列 ──
CREATE TEMP TABLE rebalance_seq AS
SELECT
  rebalance_date,
  LAG(rebalance_date) OVER (ORDER BY rebalance_date) AS prev_rebalance_date
FROM (
  SELECT DISTINCT rebalance_date
  FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily`
  WHERE strategy_id = strategy_id AND run_id = run_id
    AND rebalance_date BETWEEN predict_start_date AND predict_end_date
);

INSERT INTO `data-aquarium.ashare_ads.ads_order_plan_daily`
(strategy_id, rebalance_date, sec_code, side, order_weight_delta,
 order_shares, expected_price, expected_amount_cny, order_reason, run_id, created_at)
WITH current_target AS (
  SELECT rebalance_date, sec_code, target_weight
  FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily`
  WHERE strategy_id = strategy_id AND run_id = run_id
    AND rebalance_date BETWEEN predict_start_date AND predict_end_date
),
prev_target AS (
  SELECT rs.rebalance_date, pt.sec_code, pt.target_weight AS prev_weight
  FROM rebalance_seq AS rs
  JOIN `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
    ON pt.rebalance_date = rs.prev_rebalance_date
   AND pt.strategy_id = strategy_id AND pt.run_id = run_id
  WHERE rs.prev_rebalance_date IS NOT NULL
),
combined AS (
  SELECT
    COALESCE(c.rebalance_date, p.rebalance_date) AS rebalance_date,
    COALESCE(c.sec_code, p.sec_code) AS sec_code,
    COALESCE(c.target_weight, 0) AS new_weight,
    COALESCE(p.prev_weight, 0) AS old_weight
  FROM current_target AS c
  FULL OUTER JOIN prev_target AS p
    ON c.rebalance_date = p.rebalance_date AND c.sec_code = p.sec_code
),
orders AS (
  SELECT
    rebalance_date,
    sec_code,
    new_weight - old_weight AS delta,
    CASE
      WHEN new_weight > old_weight THEN 'BUY'
      WHEN new_weight < old_weight THEN 'SELL'
    END AS side,
    CASE
      WHEN old_weight = 0 THEN 'new_position'
      WHEN new_weight = 0 THEN 'close_position'
      ELSE 'rebalance'
    END AS order_reason
  FROM combined
  WHERE new_weight != old_weight
)
SELECT
  strategy_id,
  o.rebalance_date,
  o.sec_code,
  o.side,
  o.delta AS order_weight_delta,
  CAST(NULL AS FLOAT64) AS order_shares,
  px.close AS expected_price,
  CAST(NULL AS FLOAT64) AS expected_amount_cny,
  o.order_reason,
  run_id,
  CURRENT_TIMESTAMP()
FROM orders AS o
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
  ON px.sec_code = o.sec_code AND px.trade_date = o.rebalance_date
  AND px.trade_date BETWEEN predict_start_date AND predict_end_date
WHERE o.side IS NOT NULL;
