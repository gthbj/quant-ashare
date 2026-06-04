-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 09: 从 ADS 回测表计算汇总绩效与信号监控，写 performance_summary / signal_monitor。

DECLARE p_run_id STRING DEFAULT 's1_bqml_livepool_oriented_20260603_01';
DECLARE p_prediction_run_id STRING DEFAULT NULL;  -- 组合层实验可独立输出 run_id，同时复用模型/预测来源 run_id
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_bqml_livepool_oriented_20260603_01';
DECLARE p_experiment_id STRING DEFAULT 'oq010_base_oriented_weekly_h5_n5_w20_pv';
DECLARE p_experiment_group STRING DEFAULT 'baseline';
DECLARE p_baseline_experiment_id STRING DEFAULT 'oq010_base_oriented_weekly_h5_n5_w20_pv';
DECLARE p_parent_experiment_id STRING DEFAULT 'oq010_base_oriented_weekly_h5_n5_w20_pv';
DECLARE p_parent_run_id STRING DEFAULT 's1_bqml_livepool_oriented_20260603_01';
DECLARE p_rebalance_frequency STRING DEFAULT 'weekly';
DECLARE p_target_holdings INT64 DEFAULT 5;
DECLARE p_max_single_weight FLOAT64 DEFAULT 0.20;
DECLARE p_label_horizon INT64 DEFAULT 5;
DECLARE p_horizon_natural_frequency STRING DEFAULT 'weekly';
DECLARE p_feature_set_id STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_predict_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_predict_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_initial_capital FLOAT64 DEFAULT 100000.0;
-- OQ-010 成本 profile：cn_a_share_wanyi_no_min_slip5_v20260602
DECLARE p_cost_profile_id STRING DEFAULT 'cn_a_share_wanyi_no_min_slip5_v20260602';
DECLARE p_commission_bps FLOAT64 DEFAULT 1.0;
DECLARE p_min_commission_cny FLOAT64 DEFAULT 0.0;
DECLARE p_stamp_tax_buy_bps FLOAT64 DEFAULT 0.0;
DECLARE p_stamp_tax_sell_bps FLOAT64 DEFAULT 5.0;
DECLARE p_slippage_buy_bps FLOAT64 DEFAULT 5.0;
DECLARE p_slippage_sell_bps FLOAT64 DEFAULT 5.0;
DECLARE p_cost_bps FLOAT64 DEFAULT 30.0;  -- 兼容字段
DECLARE p_benchmark STRING DEFAULT '000852.SH';
DECLARE p_initial_state_mode STRING DEFAULT 'fresh';  -- fresh / resume_from_backtest
DECLARE p_parent_backtest_id STRING DEFAULT NULL;
DECLARE p_state_as_of_date DATE DEFAULT NULL;
DECLARE p_resume_policy_id STRING DEFAULT 'ledger_exec_v1_resume_v20260604';
DECLARE p_calendar_end DATE;
DECLARE p_selected_model_id STRING;
DECLARE p_force_replace BOOL DEFAULT FALSE;

SET p_prediction_run_id = COALESCE(p_prediction_run_id, p_run_id);

IF p_rebalance_frequency NOT IN ('weekly', 'biweekly', 'monthly') THEN
  RAISE USING MESSAGE = CONCAT('unsupported p_rebalance_frequency: ', p_rebalance_frequency);
END IF;

IF p_label_horizon NOT IN (5, 10, 20) THEN
  RAISE USING MESSAGE = 'p_label_horizon must be one of 5, 10, 20';
END IF;

SET p_calendar_end = DATE_ADD(p_predict_end, INTERVAL 90 DAY);
SET p_selected_model_id = (
  SELECT reg.model_id
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_prediction_run_id
  ORDER BY reg.created_at DESC LIMIT 1
);

IF p_selected_model_id IS NULL THEN
  RAISE USING MESSAGE = CONCAT('no selected model for prediction_run_id ', p_prediction_run_id);
END IF;

-- ── 幂等 ──
IF NOT p_force_replace THEN
  -- 检查本脚本写入的所有表（summary + signal monitor）
  IF (
    (SELECT COUNT(*) FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
       WHERE bs.backtest_id = p_backtest_id)
  + (SELECT COUNT(*) FROM `data-aquarium.ashare_ads.ads_signal_monitor_daily` AS sm
       WHERE sm.strategy_id = p_strategy_id AND sm.run_id = p_run_id
         AND sm.trade_date BETWEEN p_predict_start AND p_predict_end)
  ) > 0 THEN
    RAISE USING MESSAGE = CONCAT('summary/monitor already exist for backtest_id ', p_backtest_id, '. Set p_force_replace=TRUE.');
  END IF;
END IF;
IF p_force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs WHERE bs.backtest_id = p_backtest_id;
  DELETE FROM `data-aquarium.ashare_ads.ads_signal_monitor_daily` AS sm
    WHERE sm.strategy_id = p_strategy_id AND sm.run_id = p_run_id
      AND sm.trade_date BETWEEN p_predict_start AND p_predict_end;
END IF;

-- ── 成交统计（ledger_exec_v1 口径）：直接从实际成交表 ads_backtest_trade_daily 汇总 ──
-- 卖不出会进入 pending_sell 并在后续每个开市日重试；买不进不候补、不每日追买。
CREATE TEMP TABLE sell_stats AS
SELECT
  COUNTIF(t.side = 'BUY')  AS buy_attempt_count,
  COUNTIF(t.side = 'BUY'  AND t.fill_status IN ('FILLED', 'FILLED_SCALED_CASH')) AS buy_filled_count,
  COUNTIF(t.side = 'BUY'  AND t.fill_status = 'FILLED_SCALED_CASH') AS buy_scaled_cash_count,
  COUNTIF(t.side = 'BUY'  AND t.fill_status IN ('BUY_SKIPPED_UNTRADABLE', 'SKIPPED_CASH_INSUFFICIENT', 'SKIPPED_MIN_NOTIONAL')) AS buy_skipped_count,
  COUNTIF(t.side = 'SELL') AS sell_attempt_count,
  COUNTIF(t.side = 'SELL' AND t.fill_status = 'FILLED') AS sell_filled_count,
  COUNTIF(t.side = 'SELL' AND t.fill_status IN ('SELL_SKIPPED_UNTRADABLE', 'PENDING_SELL_CARRY')) AS sell_skipped_count,
  COUNTIF(t.fill_status = 'PENDING_SELL_CARRY') AS pending_sell_carry_count,
  COUNTIF(t.fill_status = 'CANCELLED_BY_NETTING') AS cancelled_by_netting_count,
  COUNTIF(t.fill_status = 'NOOP_ALREADY_TARGET') AS noop_already_target_count,
  COUNTIF(t.fill_status = 'SKIPPED_CASH_INSUFFICIENT') AS cash_insufficient_skip_count
FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS t
WHERE t.backtest_id = p_backtest_id AND t.trade_date BETWEEN p_predict_start AND p_calendar_end;

-- ── OQ-010 成本分解：从 trade 表直接汇总 fee/tax/slippage/economic_cost ──
CREATE TEMP TABLE cost_stats AS
SELECT
  SUM(t.fee_cny - t.tax_cny) AS total_commission_cny,
  SUM(t.tax_cny) AS total_tax_cny,
  SUM(t.slippage_cny) AS total_slippage_cny,
  SUM(t.fee_cny + t.slippage_cny) AS total_economic_cost_cny
FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS t
WHERE t.backtest_id = p_backtest_id
  AND t.fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
  AND t.trade_date BETWEEN p_predict_start AND p_predict_end;

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
  -- cost_bps 作为兼容字段写入往返总经济成本（从参数计算，支持敏感性实验）
  p_commission_bps + p_stamp_tax_buy_bps + p_slippage_buy_bps
    + p_commission_bps + p_stamp_tax_sell_bps + p_slippage_sell_bps,
  TO_JSON_STRING(STRUCT(
    -- OQ-010 experiment identity and parameters
    p_experiment_id AS experiment_id,
    p_experiment_group AS experiment_group,
    p_baseline_experiment_id AS baseline_experiment_id,
    p_parent_experiment_id AS parent_experiment_id,
    p_parent_run_id AS parent_run_id,
    p_prediction_run_id AS prediction_run_id,
    p_rebalance_frequency AS rebalance_frequency,
    p_target_holdings AS target_holdings,
    p_max_single_weight AS max_single_weight,
    p_label_horizon AS label_horizon,
    p_horizon_natural_frequency AS horizon_natural_frequency,
    p_feature_set_id AS feature_set_id,
    a.n_days, a.annual_return, a.annual_vol,
    SAFE_DIVIDE(a.annual_return, a.annual_vol) AS sharpe,
    dd.max_dd AS max_drawdown,
    a.excess_annual AS excess_annual_return,
    SAFE_DIVIDE(a.excess_annual, NULLIF(a.tracking_error, 0)) AS information_ratio,
    -- PRD-20260602-03 报告增强字段
    'strategy1_zh_report_v2' AS report_version,
    -- diagnosis_triggered: 初始预估值（3 条件）。render_report.py 会按完整 5 条件
    --（+ 滚动亏损 ≤-8%、成本侵蚀 ≥20%）重新计算并覆盖写入，以此为准。
    ((a.final_nav - 1.0) < (SELECT b.bench_cum_nav FROM bench AS b ORDER BY b.trade_date DESC LIMIT 1) - 1.0
     OR (a.final_nav - 1.0) < 0
     OR dd.max_dd <= -0.15) AS diagnosis_triggered,
    -- ledger_exec_v1 成交口径（与 ads_backtest_trade_daily 1:1 可对账）
    'ledger_exec_v1' AS ledger_version,
    'signal_date_next_open_execution' AS execution_semantics,
    p_initial_state_mode AS initial_state_mode,
    p_parent_backtest_id AS parent_backtest_id,
    p_state_as_of_date AS state_as_of_date,
    p_resume_policy_id AS resume_policy_id,
    p_initial_state_mode = 'resume_from_backtest' AS is_resumed_backtest,
    TRUE AS pending_sell_daily_retry,
    TRUE AS buy_no_fallback,
    ss.buy_attempt_count, ss.buy_filled_count, ss.buy_skipped_count,
    ss.buy_scaled_cash_count,
    SAFE_DIVIDE(CAST(ss.buy_skipped_count AS FLOAT64), NULLIF(ss.buy_attempt_count, 0)) AS buy_skip_rate,
    ss.sell_attempt_count, ss.sell_filled_count, ss.sell_skipped_count,
    ss.pending_sell_carry_count, ss.cancelled_by_netting_count,
    ss.noop_already_target_count, ss.cash_insufficient_skip_count,
    SAFE_DIVIDE(CAST(ss.sell_skipped_count AS FLOAT64), NULLIF(ss.sell_attempt_count, 0)) AS sell_skip_rate,
    a.total_turnover, a.total_cost,
    -- OQ-010 成本 profile
    p_cost_profile_id AS cost_profile_id,
    p_commission_bps AS commission_bps,
    p_min_commission_cny AS min_commission_cny,
    p_stamp_tax_buy_bps AS stamp_tax_buy_bps,
    p_stamp_tax_sell_bps AS stamp_tax_sell_bps,
    p_slippage_buy_bps AS slippage_buy_bps,
    p_slippage_sell_bps AS slippage_sell_bps,
    (p_commission_bps + p_stamp_tax_buy_bps + p_slippage_buy_bps) AS effective_buy_cost_bps,
    (p_commission_bps + p_stamp_tax_sell_bps + p_slippage_sell_bps) AS effective_sell_cost_bps,
    (p_commission_bps + p_stamp_tax_buy_bps + p_slippage_buy_bps
      + p_commission_bps + p_stamp_tax_sell_bps + p_slippage_sell_bps) AS round_trip_cost_bps,
    -- OQ-010 成本分解（从 trade 表汇总：commission + stamp_tax + slippage = economic_cost）
    cs.total_commission_cny, cs.total_tax_cny, cs.total_slippage_cny, cs.total_economic_cost_cny
  )),
  CURRENT_TIMESTAMP()
FROM agg AS a, drawdown AS dd, sell_stats AS ss, cost_stats AS cs;

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
),
-- 每个交易日的训练面板样本量（预聚合，去相关子查询）
panel_cnt AS (
  SELECT tp.trade_date, COUNT(*) AS sample_count
  FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
  WHERE tp.run_id = p_prediction_run_id AND tp.trade_date BETWEEN p_predict_start AND p_predict_end
  GROUP BY tp.trade_date
)
SELECT
  p_strategy_id, p_selected_model_id, pred.predict_date,
  ANY_VALUE(pc.sample_count),
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
LEFT JOIN panel_cnt AS pc ON pc.trade_date = pred.predict_date
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
  ON px.sec_code = pred.sec_code AND px.trade_date = t1.exec_date
  AND px.trade_date BETWEEN p_predict_start AND p_calendar_end
WHERE pred.model_id = p_selected_model_id AND pred.run_id = p_prediction_run_id
  AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
GROUP BY pred.predict_date;
