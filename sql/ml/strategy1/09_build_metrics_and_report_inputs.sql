-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 09: 从 ADS 回测表计算汇总绩效与信号监控，写 performance_summary / signal_monitor。

DECLARE p_run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_bqml_20260601_01';
DECLARE p_predict_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_predict_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_initial_capital FLOAT64 DEFAULT 100000.0;
DECLARE p_cost_bps FLOAT64 DEFAULT 30.0;
DECLARE p_benchmark STRING DEFAULT '000852.SH';
DECLARE p_calendar_end DATE;
DECLARE p_selected_model_id STRING;

SET p_calendar_end = DATE_ADD(p_predict_end, INTERVAL 90 DAY);
SET p_selected_model_id = (
  SELECT reg.model_id
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
  ORDER BY reg.created_at DESC LIMIT 1
);

-- exec_date 集合（用于判定卖出是否顺延）
CREATE TEMP TABLE exec_dates AS
WITH rdates AS (
  SELECT DISTINCT pt.rebalance_date
  FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
  WHERE pt.strategy_id = p_strategy_id AND pt.run_id = p_run_id
    AND pt.rebalance_date BETWEEN p_predict_start AND p_predict_end
)
SELECT (SELECT MIN(c2.cal_date) FROM `data-aquarium.ashare_dim.dim_trade_calendar` AS c2
        WHERE c2.exchange = 'SSE' AND c2.is_open = 1
          AND c2.trade_date_seq = (SELECT c1.trade_date_seq FROM `data-aquarium.ashare_dim.dim_trade_calendar` AS c1
                                   WHERE c1.exchange = 'SSE' AND c1.cal_date = r.rebalance_date) + 1) AS exec_date
FROM rdates AS r;

-- 卖出统计
CREATE TEMP TABLE sell_stats AS
SELECT
  COUNTIF(t.side = 'SELL') AS sell_total,
  COUNTIF(t.side = 'SELL' AND t.fill_status = 'SELL_BLOCKED_NO_NEXT_SELLABLE_60D') AS sell_blocked_count,
  COUNTIF(t.side = 'SELL' AND t.fill_status = 'FILLED'
          AND t.trade_date NOT IN (SELECT exec_date FROM exec_dates)) AS sell_delayed_count,
  COUNTIF(t.side = 'BUY' AND t.fill_status != 'FILLED') AS buy_fail_count,
  COUNTIF(t.side = 'BUY') AS buy_total
FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS t
WHERE t.backtest_id = p_backtest_id
  AND t.trade_date BETWEEN p_predict_start AND p_calendar_end;

-- 汇总绩效
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
    AND n.trade_date BETWEEN p_predict_start AND p_predict_end
),
nav_with_max AS (
  SELECT nd.*,
         MAX(nd.nav) OVER (ORDER BY nd.trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS run_max
  FROM nav_data AS nd
),
drawdown AS (
  SELECT MIN(nav / NULLIF(run_max, 0) - 1.0) AS max_dd FROM nav_with_max
),
bench AS (
  SELECT EXP(SUM(LN(1 + bench_ret)) OVER (ORDER BY trade_date)) AS bench_cum_nav, trade_date
  FROM nav_data
),
agg AS (
  SELECT
    MIN(nd.trade_date) AS start_date,
    MAX(nd.trade_date) AS end_date,
    COUNT(*) AS n_days,
    (ARRAY_AGG(nd.nav ORDER BY nd.trade_date DESC LIMIT 1))[OFFSET(0)] AS final_nav,
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
  a.final_nav - 1.0,
  a.annual_return, a.annual_vol,
  SAFE_DIVIDE(a.annual_return, a.annual_vol),
  dd.max_dd,
  SAFE_DIVIDE(a.total_turnover, (a.n_days / 252.0) * p_initial_capital),
  p_benchmark,
  a.final_nav - (SELECT b.bench_cum_nav FROM bench AS b ORDER BY b.trade_date DESC LIMIT 1),
  SAFE_DIVIDE(a.excess_annual, NULLIF(a.tracking_error, 0)),
  p_cost_bps,
  TO_JSON_STRING(STRUCT(
    a.n_days, a.annual_return, a.annual_vol,
    SAFE_DIVIDE(a.annual_return, a.annual_vol) AS sharpe,
    dd.max_dd AS max_drawdown,
    a.excess_annual AS excess_annual_return,
    SAFE_DIVIDE(a.excess_annual, NULLIF(a.tracking_error, 0)) AS information_ratio,
    SAFE_DIVIDE(CAST(ss.buy_fail_count AS FLOAT64), NULLIF(ss.buy_total, 0)) AS buy_fail_rate,
    SAFE_DIVIDE(CAST(ss.sell_delayed_count AS FLOAT64), NULLIF(ss.sell_total, 0)) AS sell_delay_rate,
    ss.sell_blocked_count,
    a.total_turnover, a.total_cost
  )),
  CURRENT_TIMESTAMP()
FROM agg AS a, drawdown AS dd, sell_stats AS ss;

-- 信号监控（t+1 可买性）
INSERT INTO `data-aquarium.ashare_ads.ads_signal_monitor_daily`
(strategy_id, model_id, trade_date, sample_count, prediction_count,
 candidate_count, avg_score, score_std, not_tradable_entry_count,
 metrics_json, run_id, created_at)
WITH t1 AS (
  SELECT c1.cal_date AS signal_date, c2.cal_date AS exec_date
  FROM `data-aquarium.ashare_dim.dim_trade_calendar` AS c1
  JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS c2
    ON c2.trade_date_seq = c1.trade_date_seq + 1 AND c2.exchange = 'SSE' AND c2.is_open = 1
  WHERE c1.exchange = 'SSE' AND c1.is_open = 1
    AND c1.cal_date BETWEEN p_predict_start AND p_predict_end
)
SELECT
  p_strategy_id, p_selected_model_id, pred.predict_date,
  (SELECT COUNT(*) FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
   WHERE tp.run_id = p_run_id AND tp.trade_date = pred.predict_date
     AND tp.trade_date BETWEEN p_predict_start AND p_predict_end),
  COUNT(*),
  COUNTIF(cand.is_selected_candidate),
  AVG(pred.score), STDDEV_SAMP(pred.score),
  COUNTIF(cand.is_selected_candidate AND NOT COALESCE(px.can_buy_open, FALSE)),
  CAST(NULL AS STRING),
  p_run_id, CURRENT_TIMESTAMP()
FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
LEFT JOIN `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
  ON cand.sec_code = pred.sec_code AND cand.rebalance_date = pred.predict_date
  AND cand.strategy_id = p_strategy_id AND cand.run_id = p_run_id
  AND cand.rebalance_date BETWEEN p_predict_start AND p_predict_end
LEFT JOIN t1 ON t1.signal_date = pred.predict_date
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
  ON px.sec_code = pred.sec_code AND px.trade_date = t1.exec_date
  AND px.trade_date BETWEEN p_predict_start AND p_calendar_end
WHERE pred.model_id = p_selected_model_id AND pred.run_id = p_run_id
  AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
GROUP BY pred.predict_date;
