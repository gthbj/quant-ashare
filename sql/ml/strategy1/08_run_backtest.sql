-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 08: 回测撮合、持仓、NAV。预计算 next-sellable 避免 WHILE 循环。

-- ── 运行参数 ──
DECLARE run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE backtest_id STRING DEFAULT 'bt_s1_bqml_20260601_01';
DECLARE predict_start_date DATE DEFAULT DATE '2024-01-01';
DECLARE predict_end_date DATE DEFAULT DATE '2025-12-31';
-- OQ-010: 示例值，非业务定稿
DECLARE initial_capital FLOAT64 DEFAULT 100000.0;
DECLARE cost_bps FLOAT64 DEFAULT 30.0;
DECLARE benchmark_sec_code STRING DEFAULT '000852.SH';
DECLARE force_replace BOOL DEFAULT FALSE;

IF force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily`   WHERE backtest_id = backtest_id AND trade_date BETWEEN predict_start_date AND predict_end_date;
  DELETE FROM `data-aquarium.ashare_ads.ads_backtest_position_daily` WHERE backtest_id = backtest_id AND trade_date BETWEEN predict_start_date AND predict_end_date;
  DELETE FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily`      WHERE backtest_id = backtest_id AND trade_date BETWEEN predict_start_date AND predict_end_date;
  DELETE FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` WHERE backtest_id = backtest_id;
END IF;

-- ── 交易日历 ──
CREATE TEMP TABLE cal AS
SELECT cal_date AS trade_date, trade_date_seq
FROM `data-aquarium.ashare_dim.dim_trade_calendar`
WHERE exchange = 'SSE' AND is_open = 1
  AND cal_date BETWEEN predict_start_date AND predict_end_date;

-- ── 调仓日 ──
CREATE TEMP TABLE rebalance_dates AS
SELECT MAX(trade_date) AS rebalance_date
FROM cal
GROUP BY EXTRACT(ISOYEAR FROM trade_date), EXTRACT(ISOWEEK FROM trade_date);

-- ── 每个调仓日的 t+1 开盘执行日 ──
CREATE TEMP TABLE exec_dates AS
SELECT
  r.rebalance_date,
  (SELECT MIN(c2.trade_date)
   FROM cal AS c2
   JOIN cal AS c1 ON c1.trade_date = r.rebalance_date
   WHERE c2.trade_date_seq = c1.trade_date_seq + 1
  ) AS exec_date
FROM rebalance_dates AS r;

-- ── 预计算 next-sellable：从每个 (sec_code, trade_date) 往后找 60 日内首个 can_sell_open=TRUE 的日期 ──
CREATE TEMP TABLE next_sellable AS
SELECT
  p.sec_code,
  p.trade_date,
  (SELECT MIN(p2.trade_date)
   FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS p2
   JOIN cal AS c2 ON p2.trade_date = c2.trade_date
   JOIN cal AS c1 ON c1.trade_date = p.trade_date
   WHERE p2.sec_code = p.sec_code
     AND p2.trade_date > p.trade_date
     AND c2.trade_date_seq <= c1.trade_date_seq + 60
     AND p2.can_sell_open
     AND p2.trade_date BETWEEN predict_start_date AND predict_end_date
  ) AS next_sellable_date
FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS p
WHERE p.trade_date BETWEEN predict_start_date AND predict_end_date;

-- ── 撮合：买入 ──
CREATE TEMP TABLE buy_fills AS
SELECT
  backtest_id,
  e.exec_date AS trade_date,
  t.sec_code,
  'BUY' AS side,
  t.target_weight,
  px.open AS fill_price,
  CASE WHEN COALESCE(px.can_buy_open, FALSE) THEN 'FILLED' ELSE 'REJECTED' END AS fill_status
FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS t
JOIN exec_dates AS e ON t.rebalance_date = e.rebalance_date
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
  ON px.sec_code = t.sec_code AND px.trade_date = e.exec_date
  AND px.trade_date BETWEEN predict_start_date AND predict_end_date
WHERE t.strategy_id = strategy_id AND t.run_id = run_id
  AND t.rebalance_date BETWEEN predict_start_date AND predict_end_date;

-- ── 撮合：卖出（持有但不在新目标中的股票）──
CREATE TEMP TABLE sell_fills AS
WITH prev_holdings AS (
  SELECT
    e.rebalance_date,
    e.exec_date,
    prev.sec_code
  FROM exec_dates AS e
  JOIN `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS prev
    ON prev.rebalance_date = (
      SELECT MAX(r2.rebalance_date) FROM rebalance_dates AS r2
      WHERE r2.rebalance_date < e.rebalance_date
    )
   AND prev.strategy_id = strategy_id AND prev.run_id = run_id
  LEFT JOIN `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS cur
    ON cur.rebalance_date = e.rebalance_date AND cur.sec_code = prev.sec_code
   AND cur.strategy_id = strategy_id AND cur.run_id = run_id
  WHERE cur.sec_code IS NULL
)
SELECT
  backtest_id,
  COALESCE(ns.next_sellable_date, ph.exec_date) AS trade_date,
  ph.sec_code,
  'SELL' AS side,
  px.open AS fill_price,
  CASE
    WHEN ns.next_sellable_date IS NULL THEN 'REJECTED'
    ELSE 'FILLED'
  END AS fill_status,
  DATE_DIFF(COALESCE(ns.next_sellable_date, ph.exec_date), ph.exec_date, DAY) AS sell_delay_days
FROM prev_holdings AS ph
LEFT JOIN next_sellable AS ns
  ON ns.sec_code = ph.sec_code AND ns.trade_date = ph.exec_date
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
  ON px.sec_code = ph.sec_code AND px.trade_date = COALESCE(ns.next_sellable_date, ph.exec_date)
  AND px.trade_date BETWEEN predict_start_date AND predict_end_date;

-- ── 写入成交表 ──
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_trade_daily`
(backtest_id, trade_date, sec_code, side, planned_shares, filled_shares,
 fill_price, turnover_cny, fee_cny, tax_cny, slippage_cny, cash_effect_cny,
 fill_status, run_id, created_at)

SELECT backtest_id, trade_date, sec_code, side,
  CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64),
  fill_price, CAST(NULL AS FLOAT64),
  CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64),
  fill_status, run_id, CURRENT_TIMESTAMP()
FROM buy_fills

UNION ALL

SELECT backtest_id, trade_date, sec_code, side,
  CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64),
  fill_price, CAST(NULL AS FLOAT64),
  CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64),
  fill_status, run_id, CURRENT_TIMESTAMP()
FROM sell_fills;

-- ── 每日持仓（简化版：按调仓区间展开目标持仓到每个交易日）──
CREATE TEMP TABLE holding_periods AS
SELECT
  t.rebalance_date,
  COALESCE(
    (SELECT MIN(r2.rebalance_date) FROM rebalance_dates AS r2 WHERE r2.rebalance_date > t.rebalance_date),
    predict_end_date
  ) AS next_rebalance_date,
  t.sec_code,
  t.target_weight
FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS t
WHERE t.strategy_id = strategy_id AND t.run_id = run_id
  AND t.rebalance_date BETWEEN predict_start_date AND predict_end_date;

INSERT INTO `data-aquarium.ashare_ads.ads_backtest_position_daily`
(backtest_id, trade_date, sec_code, shares, close, market_value_cny, weight,
 unrealized_pnl_cny, run_id, created_at)
SELECT
  backtest_id,
  c.trade_date,
  h.sec_code,
  CAST(NULL AS FLOAT64) AS shares,
  px.close,
  CAST(NULL AS FLOAT64) AS market_value_cny,
  h.target_weight AS weight,
  CAST(NULL AS FLOAT64) AS unrealized_pnl_cny,
  run_id,
  CURRENT_TIMESTAMP()
FROM holding_periods AS h
JOIN cal AS c ON c.trade_date > h.rebalance_date AND c.trade_date <= h.next_rebalance_date
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
  ON px.sec_code = h.sec_code AND px.trade_date = c.trade_date
  AND px.trade_date BETWEEN predict_start_date AND predict_end_date;

-- ── NAV（简化版：按持仓权重加权日收益）──
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_nav_daily`
(backtest_id, trade_date, nav, cash_cny, net_value_cny, gross_exposure,
 turnover_cny, cost_cny, daily_return, benchmark_sec_code, benchmark_return,
 excess_return, run_id, created_at)
WITH portfolio_ret AS (
  SELECT
    pos.trade_date,
    SUM(pos.weight * COALESCE(px.ret_1d, 0)) AS weighted_ret
  FROM `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
  LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
    ON px.sec_code = pos.sec_code AND px.trade_date = pos.trade_date
    AND px.trade_date BETWEEN predict_start_date AND predict_end_date
  WHERE pos.backtest_id = backtest_id
    AND pos.trade_date BETWEEN predict_start_date AND predict_end_date
  GROUP BY pos.trade_date
),
nav_series AS (
  SELECT
    trade_date,
    weighted_ret AS daily_return,
    EXP(SUM(LN(1 + weighted_ret)) OVER (ORDER BY trade_date)) AS nav
  FROM portfolio_ret
)
SELECT
  backtest_id,
  n.trade_date,
  n.nav,
  CAST(NULL AS FLOAT64) AS cash_cny,
  initial_capital * n.nav AS net_value_cny,
  1.0 AS gross_exposure,
  CAST(NULL AS FLOAT64) AS turnover_cny,
  CAST(NULL AS FLOAT64) AS cost_cny,
  n.daily_return,
  benchmark_sec_code,
  idx.pct_change / 100.0 AS benchmark_return,
  n.daily_return - COALESCE(idx.pct_change / 100.0, 0) AS excess_return,
  run_id,
  CURRENT_TIMESTAMP()
FROM nav_series AS n
LEFT JOIN `data-aquarium.ashare_dwd.dwd_index_eod` AS idx
  ON idx.sec_code = benchmark_sec_code AND idx.trade_date = n.trade_date
  AND idx.trade_date BETWEEN predict_start_date AND predict_end_date;
