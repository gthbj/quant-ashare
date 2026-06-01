-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 08: 回测。完全由「成交」驱动，三张表同源、可对账：
--   * 成交：从 order_plan 出发，BUY 在 t+1 开盘成交（不可买→REJECTED 留现金）；
--     SELL 用预计算 next-sellable（≥ 执行日，60 日窗口），超窗口→SELL_BLOCKED_NO_NEXT_SELLABLE_60D。
--   * 订单名义按 initial_capital × |Δweight| 定（与 order_plan 一致，v0 不做按 NAV 复利的仓位放大）。
--   * 每日净持仓股数 = Σ 已成交签名股数（BUY +、SELL −），fill_date ≤ 当日；卖出顺延/封死自然 carry。
--   * 每日现金 = initial_capital + Σ cash_effect（fill_date ≤ 当日）；成本只在成交上计提。
--   * NAV = 现金 + Σ(净股数 × 当日收盘价)；建仓前为全现金。
--   * 持仓股数与价格统一用未复权口径，与成交现金口径一致（持有期内除权属 v0 简化，已记录）。
-- 日历额外延伸 90 天用于 t+1 执行与卖出顺延查找。

DECLARE p_run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_bqml_20260601_01';
DECLARE p_predict_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_predict_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_initial_capital FLOAT64 DEFAULT 100000.0;
DECLARE p_cost_bps FLOAT64 DEFAULT 30.0;        -- OQ-010 示例值
DECLARE p_benchmark STRING DEFAULT '000852.SH';  -- OQ-010 示例值
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

-- ── 每个调仓日 → t+1 执行日 ──
CREATE TEMP TABLE rebalance_exec AS
SELECT r.rebalance_date,
  (SELECT MIN(c2.trade_date) FROM cal AS c2
   WHERE c2.trade_date_seq = (SELECT c1.trade_date_seq FROM cal AS c1 WHERE c1.trade_date = r.rebalance_date) + 1) AS exec_date
FROM (
  SELECT DISTINCT op.rebalance_date
  FROM `data-aquarium.ashare_ads.ads_order_plan_daily` AS op
  WHERE op.strategy_id = p_strategy_id AND op.run_id = p_run_id
    AND op.rebalance_date BETWEEN p_predict_start AND p_predict_end
) AS r;

-- ── next-sellable（≥ 执行日，60 交易日窗口）──
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

-- ── 成交明细 ──
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_trade_daily`
(backtest_id, trade_date, sec_code, side, planned_shares, filled_shares,
 fill_price, turnover_cny, fee_cny, tax_cny, slippage_cny, cash_effect_cny,
 fill_status, run_id, created_at)
WITH mapped AS (
  SELECT op.sec_code, op.side, op.order_weight_delta, re.exec_date,
         ABS(op.order_weight_delta) * p_initial_capital AS planned_amount
  FROM `data-aquarium.ashare_ads.ads_order_plan_daily` AS op
  JOIN rebalance_exec AS re ON op.rebalance_date = re.rebalance_date
  WHERE op.strategy_id = p_strategy_id AND op.run_id = p_run_id
    AND op.rebalance_date BETWEEN p_predict_start AND p_predict_end
),
fills AS (
  SELECT
    m.sec_code, m.side, m.planned_amount, m.exec_date,
    CASE WHEN m.side = 'BUY' THEN IF(COALESCE(pe.can_buy_open, FALSE), m.exec_date, NULL)
         WHEN m.side = 'SELL' THEN ns.actual_sell_date END AS fill_date,
    CASE WHEN m.side = 'BUY' THEN IF(COALESCE(pe.can_buy_open, FALSE), 'FILLED', 'REJECTED')
         WHEN m.side = 'SELL' THEN IF(ns.actual_sell_date IS NOT NULL, 'FILLED', 'SELL_BLOCKED_NO_NEXT_SELLABLE_60D') END AS fill_status,
    CASE WHEN m.side = 'BUY' AND COALESCE(pe.can_buy_open, FALSE) THEN pe.open
         WHEN m.side = 'SELL' AND ns.actual_sell_date IS NOT NULL THEN ps.open END AS fill_price
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
  COALESCE(f.fill_date, f.exec_date) AS trade_date,
  f.sec_code, f.side,
  SAFE_DIVIDE(f.planned_amount, NULLIF(f.fill_price, 0)) AS planned_shares,
  IF(f.fill_status = 'FILLED', SAFE_DIVIDE(f.planned_amount, NULLIF(f.fill_price, 0)), 0) AS filled_shares,
  f.fill_price,
  IF(f.fill_status = 'FILLED', f.planned_amount, 0) AS turnover_cny,
  IF(f.fill_status = 'FILLED', f.planned_amount * p_cost_bps / 10000.0, 0) AS fee_cny,
  0.0, 0.0,
  CASE WHEN f.side = 'BUY' AND f.fill_status = 'FILLED' THEN -f.planned_amount * (1 + p_cost_bps / 10000.0)
       WHEN f.side = 'SELL' AND f.fill_status = 'FILLED' THEN f.planned_amount * (1 - p_cost_bps / 10000.0)
       ELSE 0 END AS cash_effect_cny,
  f.fill_status, p_run_id, CURRENT_TIMESTAMP()
FROM fills AS f;

-- ── 由成交派生每日净持仓（签名股数累加）──
CREATE TEMP TABLE signed_fills AS
SELECT t.sec_code, t.trade_date AS fill_date,
       IF(t.side = 'BUY', t.filled_shares, -t.filled_shares) AS signed_shares,
       t.cash_effect_cny
FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS t
WHERE t.backtest_id = p_backtest_id AND t.fill_status = 'FILLED'
  AND t.trade_date BETWEEN p_predict_start AND p_calendar_end;

-- 每只有成交的股票，从首次成交日到 predict_end 的每日净股数
CREATE TEMP TABLE stock_daily_shares AS
WITH traded AS (
  SELECT sec_code, MIN(fill_date) AS first_fill FROM signed_fills GROUP BY sec_code
)
SELECT
  tr.sec_code, c.trade_date,
  (SELECT SUM(sf.signed_shares) FROM signed_fills AS sf
   WHERE sf.sec_code = tr.sec_code AND sf.fill_date <= c.trade_date) AS net_shares
FROM traded AS tr
JOIN cal AS c ON c.trade_date >= tr.first_fill AND c.trade_date <= p_predict_end;

-- 每日持仓市值（净股数 > 0）
CREATE TEMP TABLE pos_value AS
SELECT
  sds.trade_date, sds.sec_code, sds.net_shares,
  px.close AS close_raw,
  sds.net_shares * px.close AS market_value
FROM stock_daily_shares AS sds
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
  ON px.sec_code = sds.sec_code AND px.trade_date = sds.trade_date
  AND px.trade_date BETWEEN p_predict_start AND p_calendar_end
WHERE sds.net_shares > 1e-6;

-- 每日现金（initial + 累计 cash_effect）与换手/成本
CREATE TEMP TABLE daily_cash AS
WITH cf AS (
  SELECT fill_date AS trade_date, SUM(cash_effect_cny) AS day_cash_effect
  FROM signed_fills GROUP BY fill_date
),
cost AS (
  SELECT t.trade_date, SUM(t.fee_cny) AS cost_cny, SUM(t.turnover_cny) AS turnover_cny
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS t
  WHERE t.backtest_id = p_backtest_id AND t.fill_status = 'FILLED'
    AND t.trade_date BETWEEN p_predict_start AND p_calendar_end
  GROUP BY t.trade_date
)
SELECT
  c.trade_date,
  p_initial_capital + COALESCE((SELECT SUM(cf2.day_cash_effect) FROM cf AS cf2 WHERE cf2.trade_date <= c.trade_date), 0) AS cash_cny,
  COALESCE(cost.cost_cny, 0) AS cost_cny,
  COALESCE(cost.turnover_cny, 0) AS turnover_cny
FROM cal AS c
LEFT JOIN cost ON cost.trade_date = c.trade_date
WHERE c.trade_date BETWEEN p_predict_start AND p_predict_end;

-- ── 写持仓表（weight = 市值 / 当日 NAV）──
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_position_daily`
(backtest_id, trade_date, sec_code, shares, close, market_value_cny, weight,
 unrealized_pnl_cny, run_id, created_at)
WITH nav AS (
  SELECT dc.trade_date, dc.cash_cny + COALESCE(pv.mv_sum, 0) AS nav_value
  FROM daily_cash AS dc
  LEFT JOIN (SELECT trade_date, SUM(market_value) AS mv_sum FROM pos_value GROUP BY trade_date) AS pv
    ON pv.trade_date = dc.trade_date
)
SELECT
  p_backtest_id, pv.trade_date, pv.sec_code, pv.net_shares, pv.close_raw, pv.market_value,
  SAFE_DIVIDE(pv.market_value, NULLIF(nav.nav_value, 0)),
  CAST(NULL AS FLOAT64), p_run_id, CURRENT_TIMESTAMP()
FROM pos_value AS pv
JOIN nav ON nav.trade_date = pv.trade_date;

-- ── 写 NAV 表 ──
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_nav_daily`
(backtest_id, trade_date, nav, cash_cny, net_value_cny, gross_exposure,
 turnover_cny, cost_cny, daily_return, benchmark_sec_code, benchmark_return,
 excess_return, run_id, created_at)
WITH nav_calc AS (
  SELECT
    dc.trade_date, dc.cash_cny, dc.turnover_cny, dc.cost_cny,
    COALESCE(pv.mv_sum, 0) AS mv_sum,
    dc.cash_cny + COALESCE(pv.mv_sum, 0) AS nav_value
  FROM daily_cash AS dc
  LEFT JOIN (SELECT trade_date, SUM(market_value) AS mv_sum FROM pos_value GROUP BY trade_date) AS pv
    ON pv.trade_date = dc.trade_date
),
nav_norm AS (
  SELECT *, nav_value / p_initial_capital AS nav,
         nav_value / NULLIF(LAG(nav_value) OVER (ORDER BY trade_date), 0) - 1.0 AS daily_return
  FROM nav_calc
)
SELECT
  p_backtest_id, n.trade_date, n.nav, n.cash_cny, n.nav_value,
  SAFE_DIVIDE(n.mv_sum, NULLIF(n.nav_value, 0)) AS gross_exposure,
  n.turnover_cny, n.cost_cny, n.daily_return, p_benchmark,
  idx.pct_chg / 100.0,
  n.daily_return - COALESCE(idx.pct_chg / 100.0, 0),
  p_run_id, CURRENT_TIMESTAMP()
FROM nav_norm AS n
LEFT JOIN `data-aquarium.ashare_dwd.dwd_index_eod` AS idx
  ON idx.sec_code = p_benchmark AND idx.trade_date = n.trade_date
  AND idx.trade_date BETWEEN p_predict_start AND p_calendar_end;
