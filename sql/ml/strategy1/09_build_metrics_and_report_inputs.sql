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
DECLARE p_force_replace BOOL DEFAULT FALSE;

SET p_calendar_end = DATE_ADD(p_predict_end, INTERVAL 90 DAY);
SET p_selected_model_id = (
  SELECT reg.model_id
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
  ORDER BY reg.created_at DESC LIMIT 1
);

-- ── 幂等 ──
IF NOT p_force_replace THEN
  IF (SELECT COUNT(*) > 0 FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
      WHERE bs.backtest_id = p_backtest_id) THEN
    RAISE USING MESSAGE = CONCAT('performance summary already exists for backtest_id ', p_backtest_id, '. Set p_force_replace=TRUE.');
  END IF;
END IF;
IF p_force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs WHERE bs.backtest_id = p_backtest_id;
  DELETE FROM `data-aquarium.ashare_ads.ads_signal_monitor_daily` AS sm
    WHERE sm.strategy_id = p_strategy_id AND sm.run_id = p_run_id
      AND sm.trade_date BETWEEN p_predict_start AND p_predict_end;
END IF;

-- ── 卖出顺延统计：重建 episode 退出，精确比对「期望卖出日 vs 实际可卖日」──
CREATE TEMP TABLE cal AS
SELECT cal_date AS trade_date, trade_date_seq
FROM `data-aquarium.ashare_dim.dim_trade_calendar`
WHERE exchange = 'SSE' AND is_open = 1 AND cal_date BETWEEN p_predict_start AND p_calendar_end;

CREATE TEMP TABLE periods AS
WITH rdates AS (
  SELECT DISTINCT pt.rebalance_date
  FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
  WHERE pt.strategy_id = p_strategy_id AND pt.run_id = p_run_id
    AND pt.rebalance_date BETWEEN p_predict_start AND p_predict_end
),
we AS (
  SELECT r.rebalance_date,
    (SELECT MIN(c2.trade_date) FROM cal AS c2
     WHERE c2.trade_date_seq = (SELECT c1.trade_date_seq FROM cal AS c1 WHERE c1.trade_date = r.rebalance_date) + 1) AS exec_date
  FROM rdates AS r
)
SELECT rebalance_date, exec_date, ROW_NUMBER() OVER (ORDER BY exec_date) AS period_idx
FROM we WHERE exec_date IS NOT NULL;

-- episode 退出（期望卖出日）+ next-sellable（实际可卖日）+ 顺延交易日数
CREATE TEMP TABLE sell_delay AS
WITH presence AS (
  SELECT pr.period_idx, pt.sec_code
  FROM periods AS pr
  JOIN `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
    ON pt.rebalance_date = pr.rebalance_date
   AND pt.strategy_id = p_strategy_id AND pt.run_id = p_run_id
),
grp AS (
  SELECT sec_code, period_idx,
    period_idx - ROW_NUMBER() OVER (PARTITION BY sec_code ORDER BY period_idx) AS island
  FROM presence
),
ep AS (
  SELECT sec_code, MAX(period_idx) AS last_present FROM grp GROUP BY sec_code, island
),
exits AS (
  SELECT ep.sec_code, px.exec_date AS desired_sell_date
  FROM ep JOIN periods AS px ON px.period_idx = ep.last_present + 1
),
with_actual AS (
  SELECT
    e.sec_code, e.desired_sell_date,
    (SELECT MIN(px2.trade_date)
     FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px2
     JOIN cal AS c2 ON px2.trade_date = c2.trade_date
     JOIN cal AS c1 ON c1.trade_date = e.desired_sell_date
     WHERE px2.sec_code = e.sec_code AND px2.trade_date >= e.desired_sell_date
       AND c2.trade_date_seq <= c1.trade_date_seq + 60
       AND px2.can_sell_open
       AND px2.trade_date BETWEEN p_predict_start AND p_calendar_end) AS actual_sell_date
  FROM exits AS e
)
SELECT
  sec_code, desired_sell_date, actual_sell_date,
  CASE WHEN actual_sell_date IS NULL THEN NULL
       ELSE (SELECT ca.trade_date_seq FROM cal AS ca WHERE ca.trade_date = actual_sell_date)
          - (SELECT cd.trade_date_seq FROM cal AS cd WHERE cd.trade_date = desired_sell_date)
  END AS delay_td
FROM with_actual;

CREATE TEMP TABLE sell_stats AS
SELECT
  (SELECT COUNT(*) FROM sell_delay) AS sell_total,
  (SELECT COUNTIF(actual_sell_date IS NULL) FROM sell_delay) AS sell_blocked_count,
  (SELECT COUNTIF(delay_td > 0) FROM sell_delay) AS sell_delayed_count,
  (SELECT AVG(delay_td) FROM sell_delay WHERE delay_td IS NOT NULL) AS sell_delay_td_avg,
  (SELECT MAX(delay_td) FROM sell_delay WHERE delay_td IS NOT NULL) AS sell_delay_td_max,
  (SELECT COUNTIF(t.side = 'BUY' AND t.fill_status != 'FILLED')
   FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS t
   WHERE t.backtest_id = p_backtest_id AND t.trade_date BETWEEN p_predict_start AND p_calendar_end) AS buy_fail_count,
  (SELECT COUNTIF(t.side = 'BUY')
   FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS t
   WHERE t.backtest_id = p_backtest_id AND t.trade_date BETWEEN p_predict_start AND p_calendar_end) AS buy_total;

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
    ss.sell_blocked_count, ss.sell_delayed_count, ss.sell_total,
    ss.sell_delay_td_avg, ss.sell_delay_td_max,
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
