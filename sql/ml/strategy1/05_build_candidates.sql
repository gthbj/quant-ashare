-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 05: 在每个周频调仓日，用 t 日已知信息生成候选池，写 ads_stock_candidate_daily。

-- ── 运行参数 ──
DECLARE run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE horizon INT64 DEFAULT 5;
DECLARE predict_start_date DATE DEFAULT DATE '2024-01-01';
DECLARE predict_end_date DATE DEFAULT DATE '2025-12-31';
-- OQ-010: 示例值，非业务定稿
DECLARE target_holdings INT64 DEFAULT 5;
DECLARE force_replace BOOL DEFAULT FALSE;

-- ── 获取 selected model ──
DECLARE selected_model_id STRING;
SET selected_model_id = (
  SELECT model_id
  FROM `data-aquarium.ashare_ads.ads_model_registry`
  WHERE strategy_id = strategy_id AND status = 'selected'
  ORDER BY created_at DESC LIMIT 1
);

-- ── 幂等 ──
IF force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily`
  WHERE strategy_id = strategy_id AND run_id = run_id
    AND rebalance_date BETWEEN predict_start_date AND predict_end_date;
END IF;

-- ── 周频调仓日：每个 ISO 周内最后一个开市日 ──
CREATE TEMP TABLE rebalance_dates AS
SELECT MAX(cal_date) AS rebalance_date
FROM `data-aquarium.ashare_dim.dim_trade_calendar`
WHERE exchange = 'SSE' AND is_open = 1
  AND cal_date BETWEEN predict_start_date AND predict_end_date
GROUP BY EXTRACT(ISOYEAR FROM cal_date), EXTRACT(ISOWEEK FROM cal_date);

-- ── 候选池：只用 t 日已知信息，禁止用 t+1 字段 ──
INSERT INTO `data-aquarium.ashare_ads.ads_stock_candidate_daily`
(strategy_id, rebalance_date, sec_code, model_id, horizon,
 score, rank_raw, rank_pct, in_universe_default, is_selected_candidate,
 filter_reason, run_id, created_at)
WITH scored AS (
  SELECT
    r.rebalance_date,
    pred.sec_code,
    pred.score,
    u.in_universe_default,
    CASE
      WHEN NOT COALESCE(u.in_universe_default, FALSE) THEN 'not_in_default_universe'
      ELSE NULL
    END AS filter_reason
  FROM rebalance_dates AS r
  JOIN `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
    ON pred.predict_date = r.rebalance_date
   AND pred.model_id = selected_model_id
   AND pred.predict_date BETWEEN predict_start_date AND predict_end_date
  LEFT JOIN `data-aquarium.ashare_dws.dws_stock_universe_daily` AS u
    ON u.sec_code = pred.sec_code
   AND u.trade_date = r.rebalance_date
   AND u.trade_date BETWEEN predict_start_date AND predict_end_date
),
ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY rebalance_date ORDER BY score DESC, sec_code) AS rank_raw,
    1.0 - SAFE_DIVIDE(
      ROW_NUMBER() OVER (PARTITION BY rebalance_date ORDER BY score DESC, sec_code) - 1,
      COUNT(*) OVER (PARTITION BY rebalance_date) - 1
    ) AS rank_pct
  FROM scored
  WHERE filter_reason IS NULL
)
SELECT
  strategy_id,
  rebalance_date,
  sec_code,
  selected_model_id,
  horizon,
  score,
  rank_raw,
  rank_pct,
  TRUE AS in_universe_default,
  rank_raw <= target_holdings AS is_selected_candidate,
  IF(rank_raw <= target_holdings, NULL, 'rank_below_target_holdings') AS filter_reason,
  run_id,
  CURRENT_TIMESTAMP()
FROM ranked

UNION ALL

SELECT
  strategy_id,
  rebalance_date,
  sec_code,
  selected_model_id,
  horizon,
  score,
  NULL, NULL,
  COALESCE(in_universe_default, FALSE),
  FALSE,
  filter_reason,
  run_id,
  CURRENT_TIMESTAMP()
FROM scored
WHERE filter_reason IS NOT NULL;
