-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 07: 对比上期持仓与本期目标生成 BUY/SELL 订单计划。

DECLARE p_run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_predict_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_predict_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_initial_capital FLOAT64 DEFAULT 100000.0;  -- OQ-010 示例值，用于估算订单金额
DECLARE p_force_replace BOOL DEFAULT FALSE;

IF NOT p_force_replace THEN
  IF (SELECT COUNT(*) > 0 FROM `data-aquarium.ashare_ads.ads_order_plan_daily` AS op
      WHERE op.strategy_id = p_strategy_id AND op.run_id = p_run_id
        AND op.rebalance_date BETWEEN p_predict_start AND p_predict_end) THEN
    RAISE USING MESSAGE = CONCAT('order plan already exists for run_id ', p_run_id, '. Set p_force_replace=TRUE.');
  END IF;
END IF;
IF p_force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_order_plan_daily` AS op
  WHERE op.strategy_id = p_strategy_id AND op.run_id = p_run_id
    AND op.rebalance_date BETWEEN p_predict_start AND p_predict_end;
END IF;

CREATE TEMP TABLE rebalance_seq AS
SELECT
  rebalance_date,
  LAG(rebalance_date) OVER (ORDER BY rebalance_date) AS prev_rebalance_date
FROM (
  SELECT DISTINCT pt.rebalance_date
  FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
  WHERE pt.strategy_id = p_strategy_id AND pt.run_id = p_run_id
    AND pt.rebalance_date BETWEEN p_predict_start AND p_predict_end
);

INSERT INTO `data-aquarium.ashare_ads.ads_order_plan_daily`
(strategy_id, rebalance_date, sec_code, side, order_weight_delta,
 order_shares, expected_price, expected_amount_cny, order_reason, run_id, created_at)
WITH cur AS (
  SELECT pt.rebalance_date, pt.sec_code, pt.target_weight
  FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
  WHERE pt.strategy_id = p_strategy_id AND pt.run_id = p_run_id
    AND pt.rebalance_date BETWEEN p_predict_start AND p_predict_end
),
prev AS (
  SELECT rs.rebalance_date, pt.sec_code, pt.target_weight AS prev_weight
  FROM rebalance_seq AS rs
  JOIN `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
    ON pt.rebalance_date = rs.prev_rebalance_date
   AND pt.strategy_id = p_strategy_id AND pt.run_id = p_run_id
  WHERE rs.prev_rebalance_date IS NOT NULL
),
combined AS (
  SELECT
    COALESCE(c.rebalance_date, pv.rebalance_date) AS rebalance_date,
    COALESCE(c.sec_code, pv.sec_code) AS sec_code,
    COALESCE(c.target_weight, 0) AS new_w,
    COALESCE(pv.prev_weight, 0) AS old_w
  FROM cur AS c FULL OUTER JOIN prev AS pv
    ON c.rebalance_date = pv.rebalance_date AND c.sec_code = pv.sec_code
),
orders AS (
  SELECT rebalance_date, sec_code, new_w - old_w AS delta,
    IF(new_w > old_w, 'BUY', 'SELL') AS side,
    CASE WHEN old_w = 0 THEN 'new_position'
         WHEN new_w = 0 THEN 'close_position'
         ELSE 'rebalance' END AS reason
  FROM combined WHERE new_w != old_w
)
SELECT p_strategy_id, o.rebalance_date, o.sec_code, o.side, o.delta AS order_weight_delta,
       SAFE_DIVIDE(ABS(o.delta) * p_initial_capital, NULLIF(px.close, 0)) AS order_shares,
       px.close AS expected_price,
       ABS(o.delta) * p_initial_capital AS expected_amount_cny,
       o.reason AS order_reason, p_run_id, CURRENT_TIMESTAMP()
FROM orders AS o
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
  ON px.sec_code = o.sec_code AND px.trade_date = o.rebalance_date
  AND px.trade_date BETWEEN p_predict_start AND p_predict_end
WHERE o.side IS NOT NULL;
