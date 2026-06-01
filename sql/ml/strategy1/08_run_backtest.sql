-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 08: 回测撮合。从 order_plan 出发，用 t+1 开盘价撮合，预计算 next-sellable 处理卖出顺延，
--     按实际成交建持仓和 NAV。日历窗口额外延伸 90 交易日以支持最后一次调仓的 t+1 和卖出顺延。

DECLARE p_run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_bqml_20260601_01';
DECLARE p_predict_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_predict_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_initial_capital FLOAT64 DEFAULT 100000.0;
DECLARE p_cost_bps FLOAT64 DEFAULT 30.0;  -- OQ-010 示例值
DECLARE p_benchmark STRING DEFAULT '000852.SH';  -- OQ-010 示例值
DECLARE p_force_replace BOOL DEFAULT FALSE;

-- 日历延伸终点：predict_end + 90 个自然日覆盖 t+1 执行和 60 日卖出窗口
DECLARE p_calendar_end DATE;
SET p_calendar_end = DATE_ADD(p_predict_end, INTERVAL 90 DAY);

IF p_force_replace THEN
  DELETE FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt WHERE bt.backtest_id = p_backtest_id AND bt.trade_date BETWEEN p_predict_start AND p_calendar_end;
  DELETE FROM `data-aquarium.ashare_ads.ads_backtest_position_daily` AS bp WHERE bp.backtest_id = p_backtest_id AND bp.trade_date BETWEEN p_predict_start AND p_calendar_end;
  DELETE FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS bn WHERE bn.backtest_id = p_backtest_id AND bn.trade_date BETWEEN p_predict_start AND p_calendar_end;
  DELETE FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs WHERE bs.backtest_id = p_backtest_id;
END IF;

-- ── 交易日历（含延伸窗口）──
CREATE TEMP TABLE cal AS
SELECT cal_date AS trade_date, trade_date_seq
FROM `data-aquarium.ashare_dim.dim_trade_calendar`
WHERE exchange = 'SSE' AND is_open = 1
  AND cal_date BETWEEN p_predict_start AND p_calendar_end;

-- ── 调仓日 + t+1 执行日 ──
CREATE TEMP TABLE rebalance_exec AS
SELECT
  r_date AS rebalance_date,
  (SELECT MIN(c2.trade_date) FROM cal AS c2
   WHERE c2.trade_date_seq = (SELECT c1.trade_date_seq FROM cal AS c1 WHERE c1.trade_date = r_date) + 1
  ) AS exec_date
FROM (
  SELECT DISTINCT op.rebalance_date AS r_date
  FROM `data-aquarium.ashare_ads.ads_order_plan_daily` AS op
  WHERE op.strategy_id = p_strategy_id AND op.run_id = p_run_id
    AND op.rebalance_date BETWEEN p_predict_start AND p_predict_end
);

-- ── next-sellable 预计算：包含执行日本身（>= 而非 >）──
CREATE TEMP TABLE next_sellable AS
SELECT
  px.sec_code,
  px.trade_date AS desired_sell_date,
  (SELECT MIN(px2.trade_date)
   FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px2
   JOIN cal AS c2 ON px2.trade_date = c2.trade_date
   JOIN cal AS c1 ON c1.trade_date = px.trade_date
   WHERE px2.sec_code = px.sec_code
     AND px2.trade_date >= px.trade_date
     AND c2.trade_date_seq <= c1.trade_date_seq + 60
     AND px2.can_sell_open
     AND px2.trade_date BETWEEN p_predict_start AND p_calendar_end
  ) AS actual_sell_date
FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
WHERE px.trade_date BETWEEN p_predict_start AND p_calendar_end;

-- ── 撮合：从 order_plan 出发 ──
-- BUY：t+1 开盘，可买则成交
-- SELL：t+1 开盘，不可卖则映射到 next-sellable
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_trade_daily`
(backtest_id, trade_date, sec_code, side, planned_shares, filled_shares,
 fill_price, turnover_cny, fee_cny, tax_cny, slippage_cny, cash_effect_cny,
 fill_status, run_id, created_at)
WITH orders_with_exec AS (
  SELECT op.rebalance_date, op.sec_code, op.side, op.order_weight_delta,
         re.exec_date
  FROM `data-aquarium.ashare_ads.ads_order_plan_daily` AS op
  JOIN rebalance_exec AS re ON op.rebalance_date = re.rebalance_date
  WHERE op.strategy_id = p_strategy_id AND op.run_id = p_run_id
    AND op.rebalance_date BETWEEN p_predict_start AND p_predict_end
),
fills AS (
  SELECT
    o.rebalance_date, o.sec_code, o.side, o.order_weight_delta,
    CASE
      WHEN o.side = 'BUY' THEN
        IF(COALESCE(px_exec.can_buy_open, FALSE), o.exec_date, NULL)
      WHEN o.side = 'SELL' THEN
        ns.actual_sell_date
    END AS fill_date,
    CASE
      WHEN o.side = 'BUY' THEN
        IF(COALESCE(px_exec.can_buy_open, FALSE), 'FILLED', 'REJECTED')
      WHEN o.side = 'SELL' THEN
        CASE
          WHEN ns.actual_sell_date IS NOT NULL THEN 'FILLED'
          ELSE 'SELL_BLOCKED_NO_NEXT_SELLABLE_60D'
        END
    END AS fill_status,
    CASE
      WHEN o.side = 'BUY' AND COALESCE(px_exec.can_buy_open, FALSE) THEN px_exec.open
      WHEN o.side = 'SELL' AND ns.actual_sell_date IS NOT NULL THEN px_sell.open
    END AS fill_price,
    ABS(o.order_weight_delta) * p_initial_capital AS planned_amount
  FROM orders_with_exec AS o
  LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px_exec
    ON px_exec.sec_code = o.sec_code AND px_exec.trade_date = o.exec_date
    AND px_exec.trade_date BETWEEN p_predict_start AND p_calendar_end
  LEFT JOIN next_sellable AS ns
    ON ns.sec_code = o.sec_code AND ns.desired_sell_date = o.exec_date
  LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px_sell
    ON px_sell.sec_code = o.sec_code AND px_sell.trade_date = ns.actual_sell_date
    AND px_sell.trade_date BETWEEN p_predict_start AND p_calendar_end
)
SELECT
  p_backtest_id,
  COALESCE(fill_date, (SELECT MIN(re2.exec_date) FROM rebalance_exec AS re2 WHERE re2.rebalance_date = f.rebalance_date)),
  f.sec_code, f.side,
  SAFE_DIVIDE(f.planned_amount, f.fill_price) AS planned_shares,
  IF(f.fill_status IN ('FILLED'), SAFE_DIVIDE(f.planned_amount, f.fill_price), 0) AS filled_shares,
  f.fill_price,
  IF(f.fill_status = 'FILLED', f.planned_amount, 0) AS turnover_cny,
  IF(f.fill_status = 'FILLED', f.planned_amount * p_cost_bps / 10000.0, 0) AS fee_cny,
  0.0 AS tax_cny,
  0.0 AS slippage_cny,
  CASE
    WHEN f.side = 'BUY' AND f.fill_status = 'FILLED' THEN -f.planned_amount * (1 + p_cost_bps / 10000.0)
    WHEN f.side = 'SELL' AND f.fill_status = 'FILLED' THEN f.planned_amount * (1 - p_cost_bps / 10000.0)
    ELSE 0
  END AS cash_effect_cny,
  f.fill_status,
  p_run_id,
  CURRENT_TIMESTAMP()
FROM fills AS f;

-- ── 持仓：按调仓区间展开目标持仓到每个交易日（只含已成交的 BUY）──
CREATE TEMP TABLE holding_intervals AS
WITH filled_buys AS (
  SELECT bt.sec_code, re.rebalance_date,
         COALESCE(
           (SELECT MIN(r2.rebalance_date) FROM (
             SELECT DISTINCT op2.rebalance_date FROM `data-aquarium.ashare_ads.ads_order_plan_daily` AS op2
             WHERE op2.strategy_id = p_strategy_id AND op2.run_id = p_run_id
               AND op2.rebalance_date > re.rebalance_date AND op2.rebalance_date BETWEEN p_predict_start AND p_predict_end
           ) AS r2),
           p_predict_end
         ) AS hold_until,
         pt.target_weight
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
  JOIN rebalance_exec AS re ON bt.trade_date = re.exec_date
  JOIN `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
    ON pt.sec_code = bt.sec_code AND pt.rebalance_date = re.rebalance_date
    AND pt.strategy_id = p_strategy_id AND pt.run_id = p_run_id
  WHERE bt.backtest_id = p_backtest_id AND bt.side = 'BUY' AND bt.fill_status = 'FILLED'
    AND bt.trade_date BETWEEN p_predict_start AND p_calendar_end
)
SELECT sec_code, rebalance_date, hold_until, target_weight
FROM filled_buys;

INSERT INTO `data-aquarium.ashare_ads.ads_backtest_position_daily`
(backtest_id, trade_date, sec_code, shares, close, market_value_cny, weight,
 unrealized_pnl_cny, run_id, created_at)
SELECT
  p_backtest_id, c.trade_date, h.sec_code,
  CAST(NULL AS FLOAT64),
  COALESCE(px.close, LAST_VALUE(px.close IGNORE NULLS) OVER (PARTITION BY h.sec_code ORDER BY c.trade_date)) AS close_price,
  CAST(NULL AS FLOAT64),
  h.target_weight,
  CAST(NULL AS FLOAT64),
  p_run_id, CURRENT_TIMESTAMP()
FROM holding_intervals AS h
JOIN cal AS c ON c.trade_date > h.rebalance_date AND c.trade_date <= h.hold_until
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
  ON px.sec_code = h.sec_code AND px.trade_date = c.trade_date
  AND px.trade_date BETWEEN p_predict_start AND p_calendar_end;

-- ── NAV：按实际持仓权重加权日收益 + 现金（买入失败保留的部分）──
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_nav_daily`
(backtest_id, trade_date, nav, cash_cny, net_value_cny, gross_exposure,
 turnover_cny, cost_cny, daily_return, benchmark_sec_code, benchmark_return,
 excess_return, run_id, created_at)
WITH daily_port_ret AS (
  SELECT pos.trade_date,
         SUM(pos.weight * COALESCE(px.ret_1d, 0)) AS weighted_ret,
         SUM(pos.weight) AS total_weight
  FROM `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
  LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
    ON px.sec_code = pos.sec_code AND px.trade_date = pos.trade_date
    AND px.trade_date BETWEEN p_predict_start AND p_calendar_end
  WHERE pos.backtest_id = p_backtest_id
    AND pos.trade_date BETWEEN p_predict_start AND p_calendar_end
  GROUP BY pos.trade_date
),
daily_cost AS (
  SELECT bt.trade_date, SUM(bt.fee_cny) AS cost_cny, SUM(bt.turnover_cny) AS turnover_cny
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
  WHERE bt.backtest_id = p_backtest_id AND bt.fill_status = 'FILLED'
    AND bt.trade_date BETWEEN p_predict_start AND p_calendar_end
  GROUP BY bt.trade_date
),
nav_series AS (
  SELECT
    pr.trade_date,
    pr.weighted_ret AS daily_return,
    pr.total_weight AS gross_exposure,
    COALESCE(dc.cost_cny, 0) AS cost_cny,
    COALESCE(dc.turnover_cny, 0) AS turnover_cny,
    EXP(SUM(LN(1 + pr.weighted_ret)) OVER (ORDER BY pr.trade_date)) AS nav
  FROM daily_port_ret AS pr
  LEFT JOIN daily_cost AS dc ON pr.trade_date = dc.trade_date
)
SELECT
  p_backtest_id,
  ns.trade_date,
  ns.nav,
  p_initial_capital * (1 - ns.gross_exposure) AS cash_cny,
  p_initial_capital * ns.nav AS net_value_cny,
  ns.gross_exposure,
  ns.turnover_cny,
  ns.cost_cny,
  ns.daily_return,
  p_benchmark,
  idx.pct_chg / 100.0,
  ns.daily_return - COALESCE(idx.pct_chg / 100.0, 0),
  p_run_id,
  CURRENT_TIMESTAMP()
FROM nav_series AS ns
LEFT JOIN `data-aquarium.ashare_dwd.dwd_index_eod` AS idx
  ON idx.sec_code = p_benchmark AND idx.trade_date = ns.trade_date
  AND idx.trade_date BETWEEN p_predict_start AND p_calendar_end;
