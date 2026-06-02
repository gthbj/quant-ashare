-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 05: 周频调仓日候选池，只用 t 日已知字段，写 ads_stock_candidate_daily。

DECLARE p_run_id STRING DEFAULT 's1_bqml_livepool_20260602_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_horizon INT64 DEFAULT 5;
DECLARE p_predict_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_predict_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_target_holdings INT64 DEFAULT 5;  -- OQ-010 示例值
DECLARE p_force_replace BOOL DEFAULT FALSE;

DECLARE p_selected_model_id STRING;
SET p_selected_model_id = (
  SELECT reg.model_id
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
  ORDER BY reg.created_at DESC LIMIT 1
);

IF NOT p_force_replace THEN
  IF (SELECT COUNT(*) > 0 FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
      WHERE cand.strategy_id = p_strategy_id AND cand.run_id = p_run_id
        AND cand.rebalance_date BETWEEN p_predict_start AND p_predict_end) THEN
    RAISE USING MESSAGE = CONCAT('candidates already exist for run_id ', p_run_id, '. Set p_force_replace=TRUE.');
  END IF;
END IF;
IF p_force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
  WHERE cand.strategy_id = p_strategy_id AND cand.run_id = p_run_id
    AND cand.rebalance_date BETWEEN p_predict_start AND p_predict_end;
END IF;

CREATE TEMP TABLE rebalance_dates AS
SELECT MAX(cal_date) AS rebalance_date
FROM `data-aquarium.ashare_dim.dim_trade_calendar`
WHERE exchange = 'SSE' AND is_open = 1
  AND cal_date BETWEEN p_predict_start AND p_predict_end
GROUP BY EXTRACT(ISOYEAR FROM cal_date), EXTRACT(ISOWEEK FROM cal_date);

INSERT INTO `data-aquarium.ashare_ads.ads_stock_candidate_daily`
(strategy_id, rebalance_date, sec_code, model_id, horizon,
 score, rank_raw, rank_pct, in_universe_default, is_selected_candidate,
 filter_reason, run_id, created_at)
WITH scored AS (
  SELECT
    r.rebalance_date,
    pred.sec_code,
    pred.score,
    COALESCE(u.in_universe_default, FALSE) AS in_universe_default,
    CASE
      WHEN NOT COALESCE(u.in_universe_default, FALSE) THEN 'not_in_default_universe'
      ELSE NULL
    END AS filter_reason
  FROM rebalance_dates AS r
  JOIN `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
    ON pred.predict_date = r.rebalance_date
   AND pred.model_id = p_selected_model_id
   AND pred.run_id = p_run_id
   AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
  LEFT JOIN `data-aquarium.ashare_dws.dws_stock_universe_daily` AS u
    ON u.sec_code = pred.sec_code
   AND u.trade_date = r.rebalance_date
   AND u.trade_date BETWEEN p_predict_start AND p_predict_end
),
universe_only AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY rebalance_date ORDER BY score DESC, sec_code) AS rk
  FROM scored
  WHERE filter_reason IS NULL
)
SELECT p_strategy_id, rebalance_date, sec_code, p_selected_model_id, p_horizon,
       score, rk,
       1.0 - SAFE_DIVIDE(rk - 1, COUNT(*) OVER (PARTITION BY rebalance_date) - 1),
       TRUE, rk <= p_target_holdings,
       IF(rk <= p_target_holdings, NULL, 'rank_below_target_holdings'),
       p_run_id, CURRENT_TIMESTAMP()
FROM universe_only

UNION ALL

SELECT p_strategy_id, rebalance_date, sec_code, p_selected_model_id, p_horizon,
       score, NULL, NULL, in_universe_default, FALSE,
       filter_reason, p_run_id, CURRENT_TIMESTAMP()
FROM scored WHERE filter_reason IS NOT NULL;
