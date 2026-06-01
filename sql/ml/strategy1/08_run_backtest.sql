-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 08: 回测。【v0 = 有守卫的简化版，非最终账户级回测引擎】持仓 episode 模型，卖出按「实际建仓股数」走，三张表同源可对账。
-- 已知边界：延迟/封死卖出未平仓时同股再入选会重叠建仓（双倍暴露）。10 的 QA（cash>=-1、gross<=1.005、
-- 持仓 (trade_date,sec_code) 唯一）会在该边界真实发生时报错；一旦失败则该回测结果不可接受，
-- 必须升级为账户级有状态 ledger 循环（见 runner 设计 §14.1 / DECISION-20260601-07）。
-- 建模口径（v0，已文档化）：
--   * episode = 一只股在选股池里的一段连续持有（进入→退出）；进入 BUY 建仓，退出 SELL 全平。
--   * 仓位名义 = initial_capital × 进入时目标权重（固定额、不按 NAV 复利放大，v0 简化）。
--   * BUY 在进入 period 的 t+1 开盘成交；不可买→REJECTED，该 episode 无持仓、后续无卖出（不产生幻影仓）。
--   * SELL 股数 = 该 episode 建仓「实际成交股数」（永不超卖/欠卖）；卖出日 = 退出 period 的 t+1，
--     不可卖则用 next-sellable（≥ 该日、60 交易日窗口）顺延；超窗口→SELL_BLOCKED，持仓 carry 至 predict_end 继续估值。
--   * 退出前一直持有该 episode 股数；停牌等无价日用「最近可用收盘」前向填充估值（不丢市值）。
--   * 每日现金 = initial_capital + Σcash_effect（fill_date≤当日，成本只在成交计提）；NAV = 现金 + Σ持仓市值。
--   * 价格/现金统一未复权口径；持有期内除权属 v0 简化。
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
DECLARE p_max_period INT64;

SET p_calendar_end = DATE_ADD(p_predict_end, INTERVAL 90 DAY);

-- ── 幂等：默认存在即报错，force_replace 才清理 ──
IF NOT p_force_replace THEN
  -- 检查本脚本写入的所有表（含部分失败残留），任一非空即报错
  IF (
    (SELECT COUNT(*) FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS t
       WHERE t.backtest_id = p_backtest_id AND t.trade_date BETWEEN p_predict_start AND p_calendar_end)
  + (SELECT COUNT(*) FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS t
       WHERE t.backtest_id = p_backtest_id AND t.trade_date BETWEEN p_predict_start AND p_calendar_end)
  + (SELECT COUNT(*) FROM `data-aquarium.ashare_ads.ads_backtest_position_daily` AS t
       WHERE t.backtest_id = p_backtest_id AND t.trade_date BETWEEN p_predict_start AND p_calendar_end)
  + (SELECT COUNT(*) FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS t
       WHERE t.backtest_id = p_backtest_id)
  ) > 0 THEN
    RAISE USING MESSAGE = CONCAT('backtest_id ', p_backtest_id, ' already has results (trade/position/nav/summary). Set p_force_replace=TRUE.');
  END IF;
END IF;
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

-- ── period：rebalance_date → t+1 exec_date → period_idx ──
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

SET p_max_period = (SELECT MAX(period_idx) FROM periods);

-- ── 选股池在各 period 的归属（带权重）──
CREATE TEMP TABLE presence AS
SELECT pr.period_idx, pr.exec_date, pt.sec_code, pt.target_weight AS w
FROM periods AS pr
JOIN `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
  ON pt.rebalance_date = pr.rebalance_date
 AND pt.strategy_id = p_strategy_id AND pt.run_id = p_run_id;

-- ── episode：gaps-and-islands 切分连续持有段 ──
CREATE TEMP TABLE episodes AS
WITH grp AS (
  SELECT sec_code, period_idx, w,
    period_idx - ROW_NUMBER() OVER (PARTITION BY sec_code ORDER BY period_idx) AS island
  FROM presence
),
ep AS (
  SELECT sec_code, island,
    MIN(period_idx) AS entry_period,
    MAX(period_idx) AS last_present_period,
    ARRAY_AGG(w ORDER BY period_idx LIMIT 1)[OFFSET(0)] AS entry_weight
  FROM grp GROUP BY sec_code, island
)
SELECT
  ep.sec_code, ep.entry_period, ep.entry_weight,
  pe.exec_date AS entry_exec_date,
  -- 退出 period = 最后在池 period 的下一个；超出则无退出（持有到 predict_end）
  IF(ep.last_present_period + 1 <= p_max_period, ep.last_present_period + 1, NULL) AS exit_period,
  px.exec_date AS exit_exec_date
FROM ep
JOIN periods AS pe ON pe.period_idx = ep.entry_period
LEFT JOIN periods AS px ON px.period_idx = ep.last_present_period + 1;

-- ── 建仓成交（BUY at entry_exec）──
-- 预算口径：每个仓位「含成本的总现金支出」= initial_capital × weight（slot budget）。
-- 故买入额 invest_amount = budget /(1+费率)，买入额+成本 = budget；首个调仓 Σbudget = capital → 现金归零不为负。
CREATE TEMP TABLE entry_fills AS
SELECT
  e.sec_code, e.entry_period, e.exit_period, e.entry_exec_date, e.exit_exec_date,
  p_initial_capital * e.entry_weight AS slot_budget,
  p_initial_capital * e.entry_weight / (1 + p_cost_bps / 10000.0) AS invest_amount,
  COALESCE(pe.can_buy_open, FALSE) AS can_buy,
  pe.open AS buy_price,
  IF(COALESCE(pe.can_buy_open, FALSE),
     SAFE_DIVIDE(p_initial_capital * e.entry_weight / (1 + p_cost_bps / 10000.0), NULLIF(pe.open, 0)), 0) AS filled_shares
FROM episodes AS e
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS pe
  ON pe.sec_code = e.sec_code AND pe.trade_date = e.entry_exec_date
  AND pe.trade_date BETWEEN p_predict_start AND p_calendar_end;

-- ── 退出成交（SELL = 建仓实际股数；卖出日用 next-sellable 顺延）──
CREATE TEMP TABLE exit_fills AS
SELECT
  ef.sec_code, ef.entry_period, ef.entry_exec_date, ef.filled_shares,
  ef.exit_exec_date AS desired_sell_date,
  (SELECT MIN(px2.trade_date)
   FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px2
   JOIN cal AS c2 ON px2.trade_date = c2.trade_date
   JOIN cal AS c1 ON c1.trade_date = ef.exit_exec_date
   WHERE px2.sec_code = ef.sec_code
     AND px2.trade_date >= ef.exit_exec_date
     AND c2.trade_date_seq <= c1.trade_date_seq + 60
     AND px2.can_sell_open
     AND px2.trade_date BETWEEN p_predict_start AND p_calendar_end) AS actual_sell_date
FROM entry_fills AS ef
WHERE ef.exit_exec_date IS NOT NULL AND ef.filled_shares > 0;

-- ── 写成交表（建仓 BUY + 退出 SELL）──
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_trade_daily`
(backtest_id, trade_date, sec_code, side, planned_shares, filled_shares,
 fill_price, turnover_cny, fee_cny, tax_cny, slippage_cny, cash_effect_cny,
 fill_status, run_id, created_at)
-- 建仓：现金支出 = invest_amount + 成本 = slot_budget（含成本不超预算，杜绝负现金）
SELECT
  p_backtest_id, ef.entry_exec_date, ef.sec_code, 'BUY',
  SAFE_DIVIDE(ef.invest_amount, NULLIF(ef.buy_price, 0)),
  ef.filled_shares, ef.buy_price,
  IF(ef.can_buy, ef.invest_amount, 0),
  IF(ef.can_buy, ef.invest_amount * p_cost_bps / 10000.0, 0),
  0.0, 0.0,
  IF(ef.can_buy, -ef.slot_budget, 0),
  IF(ef.can_buy, 'FILLED', 'REJECTED'),
  p_run_id, CURRENT_TIMESTAMP()
FROM entry_fills AS ef
UNION ALL
-- 退出
SELECT
  p_backtest_id, COALESCE(xf.actual_sell_date, xf.desired_sell_date), xf.sec_code, 'SELL',
  xf.filled_shares,
  IF(xf.actual_sell_date IS NOT NULL, xf.filled_shares, 0),
  ps.open,
  IF(xf.actual_sell_date IS NOT NULL, xf.filled_shares * ps.open, 0),
  IF(xf.actual_sell_date IS NOT NULL, xf.filled_shares * ps.open * p_cost_bps / 10000.0, 0),
  0.0, 0.0,
  IF(xf.actual_sell_date IS NOT NULL, xf.filled_shares * ps.open * (1 - p_cost_bps / 10000.0), 0),
  IF(xf.actual_sell_date IS NOT NULL, 'FILLED', 'SELL_BLOCKED_NO_NEXT_SELLABLE_60D'),
  p_run_id, CURRENT_TIMESTAMP()
FROM exit_fills AS xf
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS ps
  ON ps.sec_code = xf.sec_code AND ps.trade_date = xf.actual_sell_date
  AND ps.trade_date BETWEEN p_predict_start AND p_calendar_end;

-- ── 每只股票的持有区间 [entry_exec, 平仓日)，平仓日=实际卖出日；无退出/封死则到 predict_end ──
CREATE TEMP TABLE hold_spans AS
SELECT
  ef.sec_code, ef.entry_exec_date AS hold_from, ef.filled_shares,
  COALESCE(xf.actual_sell_date, DATE_ADD(p_predict_end, INTERVAL 1 DAY)) AS hold_until_excl
FROM entry_fills AS ef
LEFT JOIN exit_fills AS xf ON xf.sec_code = ef.sec_code AND xf.entry_period = ef.entry_period
WHERE ef.filled_shares > 0;

-- ── 前向填充收盘价（停牌无价日沿用最近可用收盘）──
CREATE TEMP TABLE price_ffill AS
SELECT
  px.sec_code, px.trade_date,
  LAST_VALUE(px.close IGNORE NULLS) OVER (
    PARTITION BY px.sec_code ORDER BY px.trade_date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS close_ffill
FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
WHERE px.trade_date BETWEEN p_predict_start AND p_predict_end;

-- ── 每日持仓市值 ──
CREATE TEMP TABLE pos_value AS
SELECT
  c.trade_date, hs.sec_code, hs.filled_shares AS net_shares,
  pf.close_ffill AS close_raw,
  hs.filled_shares * pf.close_ffill AS market_value
FROM hold_spans AS hs
JOIN cal AS c ON c.trade_date >= hs.hold_from AND c.trade_date < hs.hold_until_excl AND c.trade_date <= p_predict_end
LEFT JOIN price_ffill AS pf ON pf.sec_code = hs.sec_code AND pf.trade_date = c.trade_date;

-- ── 每日现金（initial + 累计 cash_effect）+ 换手/成本 ──
CREATE TEMP TABLE daily_cash AS
WITH cf AS (
  SELECT t.trade_date, SUM(t.cash_effect_cny) AS day_cash_effect,
         SUM(t.fee_cny) AS cost_cny, SUM(t.turnover_cny) AS turnover_cny
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS t
  WHERE t.backtest_id = p_backtest_id AND t.fill_status = 'FILLED'
    AND t.trade_date BETWEEN p_predict_start AND p_calendar_end
  GROUP BY t.trade_date
)
SELECT
  c.trade_date,
  p_initial_capital + COALESCE((SELECT SUM(cf2.day_cash_effect) FROM cf AS cf2 WHERE cf2.trade_date <= c.trade_date), 0) AS cash_cny,
  COALESCE(cf.cost_cny, 0) AS cost_cny,
  COALESCE(cf.turnover_cny, 0) AS turnover_cny
FROM cal AS c
LEFT JOIN cf ON cf.trade_date = c.trade_date
WHERE c.trade_date BETWEEN p_predict_start AND p_predict_end;

-- ── 写持仓表 ──
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
  SELECT dc.trade_date, dc.cash_cny, dc.turnover_cny, dc.cost_cny,
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
  SAFE_DIVIDE(n.mv_sum, NULLIF(n.nav_value, 0)),
  n.turnover_cny, n.cost_cny, n.daily_return, p_benchmark,
  idx.pct_chg / 100.0,
  n.daily_return - COALESCE(idx.pct_chg / 100.0, 0),
  p_run_id, CURRENT_TIMESTAMP()
FROM nav_norm AS n
LEFT JOIN `data-aquarium.ashare_dwd.dwd_index_eod` AS idx
  ON idx.sec_code = p_benchmark AND idx.trade_date = n.trade_date
  AND idx.trade_date BETWEEN p_predict_start AND p_calendar_end;
