-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 09: 计算汇总绩效指标，写 performance_summary 和 signal_monitor。

DECLARE p_run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_bqml_20260601_01';
DECLARE p_predict_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_predict_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_calendar_end DATE;
SET p_calendar_end = DATE_ADD(p_predict_end, INTERVAL 90 DAY);
DECLARE p_cost_bps FLOAT64 DEFAULT 30.0;
DECLARE p_benchmark STRING DEFAULT '000852.SH';

DECLARE p_selected_model_id STRING;
SET p_selected_model_id = (
  SELECT reg.model_id
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
  ORDER BY reg.created_at DESC LIMIT 1
);

-- ── 汇总绩效 ──
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_performance_summary`
(backtest_id, strategy_id, model_id, start_date, end_date,
 total_return, annual_return, annual_vol, sharpe, max_drawdown,
 turnover_annual, benchmark_sec_code, excess_return, information_ratio,
 cost_bps, metrics_json, created_at)
WITH nav_data AS (
  SELECT n.trade_date, n.nav, n.daily_return,
         COALESCE(n.benchmark_return, 0) AS bench_ret,
         n.excess_return, n.turnover_cny, n.cost_cny
  FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS n
  WHERE n.backtest_id = p_backtest_id
    AND n.trade_date BETWEEN p_predict_start AND p_calendar_end
),
bench_nav AS (
  SELECT
    nd.trade_date,
    EXP(SUM(LN(1 + nd.bench_ret)) OVER (ORDER BY nd.trade_date)) AS bench_cum_nav
  FROM nav_data AS nd
),
drawdown_calc AS (
  SELECT MIN(nd.nav / MAX(nd.nav) OVER (ORDER BY nd.trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) - 1.0) AS max_dd
  FROM nav_data AS nd
),
trade_stats AS (
  SELECT
    COUNTIF(bt.side = 'BUY' AND bt.fill_status != 'FILLED') AS buy_fail_count,
    COUNTIF(bt.side = 'BUY') AS buy_total,
    COUNTIF(bt.side = 'SELL' AND bt.fill_status = 'SELL_BLOCKED_NO_NEXT_SELLABLE_60D') AS sell_blocked_count,
    COUNTIF(bt.side = 'SELL' AND bt.fill_status = 'FILLED' AND bt.trade_date != (
      SELECT re.exec_date FROM `data-aquarium.ashare_dim.dim_trade_calendar` AS c1
      JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS c2 ON c2.trade_date_seq = c1.trade_date_seq + 1 AND c2.exchange = 'SSE' AND c2.is_open = 1
      WHERE c1.cal_date = bt.trade_date AND c1.exchange = 'SSE' AND c1.is_open = 1
      LIMIT 1
    )) AS sell_delayed_count,
    COUNTIF(bt.side = 'SELL') AS sell_total
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
  WHERE bt.backtest_id = p_backtest_id
    AND bt.trade_date BETWEEN p_predict_start AND p_calendar_end
),
agg AS (
  SELECT
    MIN(nd.trade_date) AS start_date,
    MAX(nd.trade_date) AS end_date,
    COUNT(*) AS n_days,
    (ARRAY_AGG(nd.nav ORDER BY nd.trade_date DESC LIMIT 1)[OFFSET(0)]) AS final_nav,
    AVG(nd.daily_return) * 252 AS annual_return,
    STDDEV_SAMP(nd.daily_return) * SQRT(252.0) AS annual_vol,
    AVG(nd.excess_return) * 252 AS excess_annual,
    STDDEV_SAMP(nd.excess_return) * SQRT(252.0) AS tracking_error,
    SUM(nd.turnover_cny) AS total_turnover,
    SUM(nd.cost_cny) AS total_cost
  FROM nav_data AS nd
)
SELECT
  p_backtest_id, p_strategy_id, p_selected_model_id,
  a.start_date, a.end_date,
  a.final_nav - 1.0 AS total_return,
  a.annual_return, a.annual_vol,
  SAFE_DIVIDE(a.annual_return, a.annual_vol) AS sharpe,
  dd.max_dd,
  SAFE_DIVIDE(a.total_turnover, (a.n_days / 252.0) * p_initial_capital) AS turnover_annual,
  p_benchmark,
  a.final_nav - (SELECT bn.bench_cum_nav FROM bench_nav AS bn ORDER BY bn.trade_date DESC LIMIT 1) AS excess_return,
  SAFE_DIVIDE(a.excess_annual, NULLIF(a.tracking_error, 0)) AS information_ratio,
  p_cost_bps,
  TO_JSON_STRING(STRUCT(
    a.n_days, a.annual_return, a.annual_vol,
    SAFE_DIVIDE(a.annual_return, a.annual_vol) AS sharpe,
    dd.max_dd AS max_drawdown,
    a.excess_annual AS excess_annual_return,
    SAFE_DIVIDE(a.excess_annual, NULLIF(a.tracking_error, 0)) AS information_ratio,
    SAFE_DIVIDE(CAST(ts.buy_fail_count AS FLOAT64), NULLIF(ts.buy_total, 0)) AS buy_fail_rate,
    SAFE_DIVIDE(CAST(ts.sell_delayed_count AS FLOAT64), NULLIF(ts.sell_total, 0)) AS sell_delay_rate,
    ts.sell_blocked_count,
    a.total_turnover, a.total_cost
  )),
  CURRENT_TIMESTAMP()
FROM agg AS a, drawdown_calc AS dd, trade_stats AS ts;

-- ── 信号监控（按预测日，用 t+1 可买性统计）──
INSERT INTO `data-aquarium.ashare_ads.ads_signal_monitor_daily`
(strategy_id, model_id, trade_date, sample_count, prediction_count,
 candidate_count, avg_score, score_std, not_tradable_entry_count,
 metrics_json, run_id, created_at)
WITH t1_exec AS (
  SELECT c1.cal_date AS signal_date, c2.cal_date AS exec_date
  FROM `data-aquarium.ashare_dim.dim_trade_calendar` AS c1
  JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS c2
    ON c2.trade_date_seq = c1.trade_date_seq + 1
   AND c2.exchange = 'SSE' AND c2.is_open = 1
  WHERE c1.exchange = 'SSE' AND c1.is_open = 1
    AND c1.cal_date BETWEEN p_predict_start AND p_predict_end
)
SELECT
  p_strategy_id, p_selected_model_id,
  pred.predict_date,
  (SELECT COUNT(*) FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
   WHERE tp.run_id = p_run_id AND tp.trade_date = pred.predict_date
     AND tp.trade_date BETWEEN p_predict_start AND p_predict_end),
  COUNT(*),
  COUNTIF(cand.is_selected_candidate),
  AVG(pred.score), STDDEV_SAMP(pred.score),
  COUNTIF(cand.is_selected_candidate AND NOT COALESCE(px_t1.can_buy_open, FALSE)),
  CAST(NULL AS STRING),
  p_run_id, CURRENT_TIMESTAMP()
FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
LEFT JOIN `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
  ON cand.sec_code = pred.sec_code AND cand.rebalance_date = pred.predict_date
  AND cand.strategy_id = p_strategy_id AND cand.run_id = p_run_id
  AND cand.rebalance_date BETWEEN p_predict_start AND p_predict_end
LEFT JOIN t1_exec ON t1_exec.signal_date = pred.predict_date
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px_t1
  ON px_t1.sec_code = pred.sec_code AND px_t1.trade_date = t1_exec.exec_date
  AND px_t1.trade_date BETWEEN p_predict_start AND p_calendar_end
WHERE pred.model_id = p_selected_model_id AND pred.run_id = p_run_id
  AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
GROUP BY pred.predict_date;
