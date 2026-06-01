-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 08: 回测。按周频 period 重构组合，用真实股数/现金/成本计 NAV。
-- 建模口径（v0，已文档化）：
--   * 每个调仓 period 在 t+1 开盘按目标权重重构持仓；不可买的目标票其权重转为现金。
--   * 持仓股数 = (period 起始资本 V_p × 权重) / 开盘后复权价；按后复权收盘价逐日估值。
--   * 现金 = V_p × (1 − 已建仓权重) − 成本；成本 = 实际换手 × cost_bps。
--   * NAV = 现金 + Σ 持仓市值；period 间用链式资本 V_p = 上一 period 末 NAV。
--   * 卖出顺延：trade 层用预计算 next-sellable（≥ 执行日，60 日窗口），
--     超窗口标记 SELL_BLOCKED_NO_NEXT_SELLABLE_60D；NAV 用 period 重构估值（顺延对 NAV 为二阶影响，已记录于 trade/统计）。
-- 日历额外延伸 90 天用于 t+1 执行与卖出顺延查找。

DECLARE p_run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_bqml_20260601_01';
DECLARE p_predict_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_predict_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_initial_capital FLOAT64 DEFAULT 100000.0;
DECLARE p_cost_bps FLOAT64 DEFAULT 30.0;       -- OQ-010 示例值
DECLARE p_benchmark STRING DEFAULT '000852.SH'; -- OQ-010 示例值
DECLARE p_force_replace BOOL DEFAULT FALSE;
DECLARE p_calendar_end DATE;

SET p_calendar_end = DATE_ADD(p_predict_end, INTERVAL 90 DAY);

IF p_force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS t WHERE t.backtest_id = p_backtest_id AND t.trade_date BETWEEN p_predict_start AND p_calendar_end;
  DELETE FROM `data-aquarium.ashare_ads.ads_backtest_position_daily` AS t WHERE t.backtest_id = p_backtest_id AND t.trade_date BETWEEN p_predict_start AND p_calendar_end;
  DELETE FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS t WHERE t.backtest_id = p_backtest_id AND t.trade_date BETWEEN p_predict_start AND p_calendar_end;
  DELETE FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS t WHERE t.backtest_id = p_backtest_id;
END IF;

-- ── 交易日历（含延伸窗口）──
CREATE TEMP TABLE cal AS
SELECT cal_date AS trade_date, trade_date_seq
FROM `data-aquarium.ashare_dim.dim_trade_calendar`
WHERE exchange = 'SSE' AND is_open = 1 AND cal_date BETWEEN p_predict_start AND p_calendar_end;

-- ── period 结构：rebalance_date → t+1 exec_date → period_idx / next_exec_date ──
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
SELECT rebalance_date, exec_date,
  ROW_NUMBER() OVER (ORDER BY exec_date) AS period_idx,
  LEAD(exec_date) OVER (ORDER BY exec_date) AS next_exec_date
FROM we WHERE exec_date IS NOT NULL;

-- ── 每个交易日归属的 period（exec_date <= day < next_exec_date，且 <= predict_end）──
CREATE TEMP TABLE day_period AS
SELECT c.trade_date, pr.period_idx, pr.exec_date
FROM cal AS c
JOIN periods AS pr
  ON c.trade_date >= pr.exec_date
 AND c.trade_date < COALESCE(pr.next_exec_date, DATE_ADD(p_predict_end, INTERVAL 1 DAY))
WHERE c.trade_date <= p_predict_end;

-- ── period 初始持仓：权重 + t+1 开盘后复权价 + 可买性 ──
CREATE TEMP TABLE pos_init AS
SELECT
  pr.period_idx, pr.exec_date, pr.next_exec_date,
  pt.sec_code, pt.target_weight AS w,
  px.open_hfq AS open_hfq_exec,
  COALESCE(px.can_buy_open, FALSE) AS acquirable
FROM periods AS pr
JOIN `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
  ON pt.rebalance_date = pr.rebalance_date
 AND pt.strategy_id = p_strategy_id AND pt.run_id = p_run_id
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
  ON px.sec_code = pt.sec_code AND px.trade_date = pr.exec_date
  AND px.trade_date BETWEEN p_predict_start AND p_calendar_end;

-- ── period 换手率（来自 order_plan 实际买卖 delta，用于成本）──
CREATE TEMP TABLE period_turnover AS
SELECT pr.period_idx, COALESCE(SUM(ABS(op.order_weight_delta)), 0) AS turnover_frac
FROM periods AS pr
LEFT JOIN `data-aquarium.ashare_ads.ads_order_plan_daily` AS op
  ON op.rebalance_date = pr.rebalance_date
 AND op.strategy_id = p_strategy_id AND op.run_id = p_run_id
GROUP BY pr.period_idx;

-- ── period 现金占比（净额，扣成本）──
CREATE TEMP TABLE period_frac AS
SELECT
  pi.period_idx,
  SUM(IF(pi.acquirable, pi.w, 0)) AS invested_frac,
  COALESCE(ANY_VALUE(pt.turnover_frac), 0) * p_cost_bps / 10000.0 AS cost_frac
FROM pos_init AS pi
LEFT JOIN period_turnover AS pt ON pt.period_idx = pi.period_idx
GROUP BY pi.period_idx;

-- ── period 末日 ──
CREATE TEMP TABLE period_end_day AS
SELECT dp.period_idx, MAX(dp.trade_date) AS end_day
FROM day_period AS dp GROUP BY dp.period_idx;

-- ── period 末 scale-free ratio（用于链式资本）──
CREATE TEMP TABLE period_ratio AS
SELECT
  pf.period_idx,
  (1.0 - pf.invested_frac - pf.cost_frac)
  + COALESCE(SUM(IF(pi.acquirable, pi.w * SAFE_DIVIDE(pe.close_hfq, NULLIF(pi.open_hfq_exec, 0)), 0)), 0) AS end_ratio,
  (1.0 - pf.invested_frac - pf.cost_frac) AS net_cash_frac
FROM period_frac AS pf
JOIN pos_init AS pi ON pi.period_idx = pf.period_idx
JOIN period_end_day AS ped ON ped.period_idx = pf.period_idx
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS pe
  ON pe.sec_code = pi.sec_code AND pe.trade_date = ped.end_day
  AND pe.trade_date BETWEEN p_predict_start AND p_calendar_end
GROUP BY pf.period_idx, pf.invested_frac, pf.cost_frac;

-- ── 链式起始资本 V_p = initial × Π(前序 end_ratio) ──
CREATE TEMP TABLE period_capital AS
SELECT
  period_idx, net_cash_frac,
  p_initial_capital * EXP(COALESCE(
    SUM(LN(NULLIF(end_ratio, 0))) OVER (ORDER BY period_idx ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0)) AS v_start
FROM period_ratio;

-- ── 成交明细（来自 order_plan，按 V_p 定 turnover；卖出用 next-sellable）──
CREATE TEMP TABLE next_sellable AS
SELECT
  px.sec_code, px.trade_date AS desired_date,
  (SELECT MIN(px2.trade_date)
   FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px2
   JOIN cal AS c2 ON px2.trade_date = c2.trade_date
   JOIN cal AS c1 ON c1.trade_date = px.trade_date
   WHERE px2.sec_code = px.sec_code
     AND px2.trade_date >= px.trade_date
     AND c2.trade_date_seq <= c1.trade_date_seq + 60
     AND px2.can_sell_open
     AND px2.trade_date BETWEEN p_predict_start AND p_calendar_end) AS actual_sell_date
FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
WHERE px.trade_date BETWEEN p_predict_start AND p_calendar_end;

INSERT INTO `data-aquarium.ashare_ads.ads_backtest_trade_daily`
(backtest_id, trade_date, sec_code, side, planned_shares, filled_shares,
 fill_price, turnover_cny, fee_cny, tax_cny, slippage_cny, cash_effect_cny,
 fill_status, run_id, created_at)
WITH mapped AS (
  SELECT op.rebalance_date, op.sec_code, op.side, op.order_weight_delta,
         pr.exec_date, cap.v_start
  FROM `data-aquarium.ashare_ads.ads_order_plan_daily` AS op
  JOIN periods AS pr ON op.rebalance_date = pr.rebalance_date
  JOIN period_capital AS cap ON cap.period_idx = pr.period_idx
  WHERE op.strategy_id = p_strategy_id AND op.run_id = p_run_id
    AND op.rebalance_date BETWEEN p_predict_start AND p_predict_end
),
fills AS (
  SELECT
    m.sec_code, m.side, m.order_weight_delta, m.exec_date, m.v_start,
    ABS(m.order_weight_delta) * m.v_start AS planned_amount,
    CASE
      WHEN m.side = 'BUY' THEN IF(COALESCE(pe.can_buy_open, FALSE), m.exec_date, NULL)
      WHEN m.side = 'SELL' THEN ns.actual_sell_date
    END AS fill_date,
    CASE
      WHEN m.side = 'BUY' THEN IF(COALESCE(pe.can_buy_open, FALSE), 'FILLED', 'REJECTED')
      WHEN m.side = 'SELL' THEN IF(ns.actual_sell_date IS NOT NULL, 'FILLED', 'SELL_BLOCKED_NO_NEXT_SELLABLE_60D')
    END AS fill_status,
    CASE
      WHEN m.side = 'BUY' AND COALESCE(pe.can_buy_open, FALSE) THEN pe.open
      WHEN m.side = 'SELL' AND ns.actual_sell_date IS NOT NULL THEN ps.open
    END AS fill_price
  FROM mapped AS m
  LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS pe
    ON pe.sec_code = m.sec_code AND pe.trade_date = m.exec_date
    AND pe.trade_date BETWEEN p_predict_start AND p_calendar_end
  LEFT JOIN next_sellable AS ns ON ns.sec_code = m.sec_code AND ns.desired_date = m.exec_date
  LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS ps
    ON ps.sec_code = m.sec_code AND ps.trade_date = ns.actual_sell_date
    AND ps.trade_date BETWEEN p_predict_start AND p_calendar_end
)
SELECT
  p_backtest_id,
  COALESCE(f.fill_date, f.exec_date),
  f.sec_code, f.side,
  SAFE_DIVIDE(f.planned_amount, NULLIF(f.fill_price, 0)) AS planned_shares,
  IF(f.fill_status = 'FILLED', SAFE_DIVIDE(f.planned_amount, NULLIF(f.fill_price, 0)), 0) AS filled_shares,
  f.fill_price,
  IF(f.fill_status = 'FILLED', f.planned_amount, 0) AS turnover_cny,
  IF(f.fill_status = 'FILLED', f.planned_amount * p_cost_bps / 10000.0, 0) AS fee_cny,
  0.0, 0.0,
  CASE
    WHEN f.side = 'BUY' AND f.fill_status = 'FILLED' THEN -f.planned_amount * (1 + p_cost_bps / 10000.0)
    WHEN f.side = 'SELL' AND f.fill_status = 'FILLED' THEN f.planned_amount * (1 - p_cost_bps / 10000.0)
    ELSE 0
  END AS cash_effect_cny,
  f.fill_status, p_run_id, CURRENT_TIMESTAMP()
FROM fills AS f;

-- ── 每日持仓（真实股数、市值、漂移权重）──
CREATE TEMP TABLE pos_daily AS
SELECT
  dp.trade_date, pi.sec_code, cap.v_start,
  SAFE_DIVIDE(cap.v_start * pi.w, NULLIF(pi.open_hfq_exec, 0)) AS shares,
  px.close AS close_raw, px.close_hfq,
  SAFE_DIVIDE(cap.v_start * pi.w, NULLIF(pi.open_hfq_exec, 0)) * px.close_hfq AS market_value
FROM pos_init AS pi
JOIN period_capital AS cap ON cap.period_idx = pi.period_idx
JOIN day_period AS dp ON dp.period_idx = pi.period_idx
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
  ON px.sec_code = pi.sec_code AND px.trade_date = dp.trade_date
  AND px.trade_date BETWEEN p_predict_start AND p_calendar_end
WHERE pi.acquirable;

-- ── 每日 NAV：现金 + 持仓市值（spine 覆盖全部开市日，建仓前为全现金）──
CREATE TEMP TABLE nav_value_daily AS
WITH mv AS (
  SELECT trade_date, SUM(market_value) AS mv_sum FROM pos_daily GROUP BY trade_date
),
cash AS (
  SELECT dp.trade_date, cap.v_start * cap.net_cash_frac AS cash_cny
  FROM day_period AS dp JOIN period_capital AS cap ON cap.period_idx = dp.period_idx
),
spine AS (
  SELECT c.trade_date FROM cal AS c WHERE c.trade_date BETWEEN p_predict_start AND p_predict_end
)
SELECT
  s.trade_date,
  COALESCE(cash.cash_cny, p_initial_capital) AS cash_cny,
  COALESCE(mv.mv_sum, 0) AS mv_sum,
  COALESCE(cash.cash_cny, p_initial_capital) + COALESCE(mv.mv_sum, 0) AS nav_value
FROM spine AS s
LEFT JOIN cash ON cash.trade_date = s.trade_date
LEFT JOIN mv ON mv.trade_date = s.trade_date;

-- ── 写持仓表（weight = 市值/当日 NAV）──
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_position_daily`
(backtest_id, trade_date, sec_code, shares, close, market_value_cny, weight,
 unrealized_pnl_cny, run_id, created_at)
SELECT
  p_backtest_id, pd.trade_date, pd.sec_code,
  pd.shares, pd.close_raw, pd.market_value,
  SAFE_DIVIDE(pd.market_value, NULLIF(nv.nav_value, 0)),
  CAST(NULL AS FLOAT64),
  p_run_id, CURRENT_TIMESTAMP()
FROM pos_daily AS pd
JOIN nav_value_daily AS nv ON nv.trade_date = pd.trade_date;

-- ── 写 NAV 表 ──
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_nav_daily`
(backtest_id, trade_date, nav, cash_cny, net_value_cny, gross_exposure,
 turnover_cny, cost_cny, daily_return, benchmark_sec_code, benchmark_return,
 excess_return, run_id, created_at)
WITH daily_cost AS (
  SELECT t.trade_date, SUM(t.fee_cny) AS cost_cny, SUM(t.turnover_cny) AS turnover_cny
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS t
  WHERE t.backtest_id = p_backtest_id AND t.fill_status = 'FILLED'
    AND t.trade_date BETWEEN p_predict_start AND p_calendar_end
  GROUP BY t.trade_date
),
nav_norm AS (
  SELECT
    nv.trade_date,
    nv.nav_value / p_initial_capital AS nav,
    nv.cash_cny, nv.nav_value, nv.mv_sum,
    nv.nav_value / NULLIF(LAG(nv.nav_value) OVER (ORDER BY nv.trade_date), 0) - 1.0 AS daily_return
  FROM nav_value_daily AS nv
)
SELECT
  p_backtest_id, n.trade_date, n.nav, n.cash_cny, n.nav_value,
  SAFE_DIVIDE(n.mv_sum, NULLIF(n.nav_value, 0)) AS gross_exposure,
  COALESCE(dc.turnover_cny, 0), COALESCE(dc.cost_cny, 0),
  n.daily_return, p_benchmark,
  idx.pct_chg / 100.0,
  n.daily_return - COALESCE(idx.pct_chg / 100.0, 0),
  p_run_id, CURRENT_TIMESTAMP()
FROM nav_norm AS n
LEFT JOIN daily_cost AS dc ON dc.trade_date = n.trade_date
LEFT JOIN `data-aquarium.ashare_dwd.dwd_index_eod` AS idx
  ON idx.sec_code = p_benchmark AND idx.trade_date = n.trade_date
  AND idx.trade_date BETWEEN p_predict_start AND p_calendar_end;
