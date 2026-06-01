-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 09: 从 ADS 回测表计算汇总绩效，写 performance_summary 和 signal_monitor。

-- ── 运行参数 ──
DECLARE run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE backtest_id STRING DEFAULT 'bt_s1_bqml_20260601_01';
DECLARE predict_start_date DATE DEFAULT DATE '2024-01-01';
DECLARE predict_end_date DATE DEFAULT DATE '2025-12-31';
DECLARE cost_bps FLOAT64 DEFAULT 30.0;
DECLARE benchmark_sec_code STRING DEFAULT '000852.SH';

DECLARE selected_model_id STRING;
SET selected_model_id = (
  SELECT model_id
  FROM `data-aquarium.ashare_ads.ads_model_registry`
  WHERE strategy_id = strategy_id AND status = 'selected'
  ORDER BY created_at DESC LIMIT 1
);

-- ── 汇总绩效 ──
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_performance_summary`
(backtest_id, strategy_id, model_id, start_date, end_date,
 total_return, annual_return, annual_vol, sharpe, max_drawdown,
 turnover_annual, benchmark_sec_code, excess_return, information_ratio,
 cost_bps, metrics_json, created_at)
WITH nav AS (
  SELECT trade_date, nav, daily_return, benchmark_return, excess_return
  FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily`
  WHERE backtest_id = backtest_id
    AND trade_date BETWEEN predict_start_date AND predict_end_date
),
stats AS (
  SELECT
    MIN(trade_date) AS start_date,
    MAX(trade_date) AS end_date,
    COUNT(*) AS n_days,
    (SELECT nav FROM nav ORDER BY trade_date DESC LIMIT 1) - 1.0 AS total_return,
    AVG(daily_return) * 252 AS annual_return,
    STDDEV_SAMP(daily_return) * SQRT(252.0) AS annual_vol,
    AVG(excess_return) * 252 AS excess_annual,
    STDDEV_SAMP(excess_return) * SQRT(252.0) AS tracking_error,
    (SELECT nav FROM nav ORDER BY trade_date DESC LIMIT 1)
      / (SELECT MAX(nav) FROM nav) - 1.0 AS approx_max_dd
  FROM nav
),
drawdown AS (
  SELECT MIN(nav / MAX(nav) OVER (ORDER BY trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) - 1.0) AS max_drawdown
  FROM nav
)
SELECT
  backtest_id,
  strategy_id,
  selected_model_id,
  s.start_date,
  s.end_date,
  s.total_return,
  s.annual_return,
  s.annual_vol,
  SAFE_DIVIDE(s.annual_return, s.annual_vol) AS sharpe,
  d.max_drawdown,
  CAST(NULL AS FLOAT64) AS turnover_annual,
  benchmark_sec_code,
  s.total_return - ((SELECT nav FROM nav ORDER BY trade_date DESC LIMIT 1) - 1.0) AS excess_return,
  SAFE_DIVIDE(s.excess_annual, NULLIF(s.tracking_error, 0)) AS information_ratio,
  cost_bps,
  TO_JSON_STRING(STRUCT(
    s.n_days,
    s.annual_return,
    s.annual_vol,
    SAFE_DIVIDE(s.annual_return, s.annual_vol) AS sharpe,
    d.max_drawdown,
    s.excess_annual AS excess_annual_return,
    SAFE_DIVIDE(s.excess_annual, NULLIF(s.tracking_error, 0)) AS information_ratio
  )) AS metrics_json,
  CURRENT_TIMESTAMP()
FROM stats AS s, drawdown AS d;

-- ── 信号监控 ──
INSERT INTO `data-aquarium.ashare_ads.ads_signal_monitor_daily`
(strategy_id, model_id, trade_date, sample_count, prediction_count,
 candidate_count, avg_score, score_std, not_tradable_entry_count,
 metrics_json, run_id, created_at)
SELECT
  strategy_id,
  selected_model_id,
  pred.predict_date AS trade_date,
  (SELECT COUNT(*) FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
   WHERE tp.run_id = run_id AND tp.trade_date = pred.predict_date
     AND tp.trade_date BETWEEN predict_start_date AND predict_end_date) AS sample_count,
  COUNT(*) AS prediction_count,
  COUNTIF(cand.is_selected_candidate) AS candidate_count,
  AVG(pred.score) AS avg_score,
  STDDEV_SAMP(pred.score) AS score_std,
  COUNTIF(NOT COALESCE(u.can_buy_open, FALSE)) AS not_tradable_entry_count,
  CAST(NULL AS STRING) AS metrics_json,
  run_id,
  CURRENT_TIMESTAMP()
FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
LEFT JOIN `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
  ON cand.sec_code = pred.sec_code AND cand.rebalance_date = pred.predict_date
  AND cand.strategy_id = strategy_id AND cand.run_id = run_id
LEFT JOIN `data-aquarium.ashare_dws.dws_stock_universe_daily` AS u
  ON u.sec_code = pred.sec_code AND u.trade_date = pred.predict_date
  AND u.trade_date BETWEEN predict_start_date AND predict_end_date
WHERE pred.model_id = selected_model_id AND pred.run_id = run_id
  AND pred.predict_date BETWEEN predict_start_date AND predict_end_date
GROUP BY pred.predict_date;
