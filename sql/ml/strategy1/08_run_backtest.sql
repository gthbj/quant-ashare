-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 08: 回测【v1 = 账户级有状态 ledger 循环】。逐调仓 period 维护现金与持仓：
--   * 每个 period 在 t+1 执行日 (exec_date) 先按当前持仓估值得到 NAV（停牌无价用最近可用收盘前向填充）。
--   * 目标仓位 = 目标权重 × 当前 NAV（按当前 NAV 定档，资金可复利/回收，非固定初始资金额）。
--   * 卖出先于买入：对「持有但目标更低/不在目标」的票按 exec 开盘卖到目标（可卖才卖），所得入现金。
--   * 买入受可用现金约束：对「目标高于现有」的票按 exec 开盘买入，若总买入额超现金则等比例缩放，保证现金不为负。
--   * netting：对实际持仓做增量买卖，滚动持有的票不重复全卖全买。
--   * 不可交易（can_buy_open/can_sell_open=FALSE 或当日无开盘价）的腿本期跳过、持仓 carry 到下一个 period 再试
--     （v1 简化：不做 60 交易日 next-sellable 顺延搜索，文档化）。
-- 循环结束后按交易日展开每日持仓/NAV：每个开市日取「<=该日的最近一次调仓快照」估值（close 前向填充）。
-- 不变量（由构造保证，10 的守卫会校验）：现金 >= 0、gross_exposure = 持仓市值/NAV <= 1、
--   每 (trade_date, sec_code) 持仓唯一、NAV 覆盖 predict 窗口每个开市日。
-- 价格/现金统一未复权口径；持有期内除权属简化（与 v0 一致）。日历额外延伸 90 天用于 t+1 执行查找。
-- 升级背景见 runner 设计 §14.1 / DECISION-20260601-07。

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
-- ledger 循环状态变量
DECLARE v_p INT64;
DECLARE v_exec DATE;
DECLARE v_cash FLOAT64;
DECLARE v_nav FLOAT64;
DECLARE v_scale FLOAT64;

SET p_calendar_end = DATE_ADD(p_predict_end, INTERVAL 90 DAY);

-- ── OQ-004 benchmark 前置校验：必须是 dim_index 中的可用收益基准，并完整覆盖 NAV 窗口 ──
ASSERT (
  SELECT COUNT(*) = 1
  FROM `data-aquarium.ashare_dim.dim_index` AS i
  WHERE i.sec_code = p_benchmark
    AND i.has_daily
    AND i.is_benchmark_candidate
) AS 'benchmark must exist in dim_index as a has_daily benchmark candidate';

CREATE TEMP TABLE benchmark_window_check AS
WITH window_calendar AS (
  -- A 股沪深两市交易日历实际一致；这里统一用 SSE 日历代表全市场开市日。
  SELECT cal_date AS trade_date
  FROM `data-aquarium.ashare_dim.dim_trade_calendar`
  WHERE exchange = 'SSE'
    AND is_open = 1
    AND cal_date BETWEEN p_predict_start AND p_predict_end
),
benchmark AS (
  SELECT
    idx.trade_date,
    COUNT(*) AS row_count,
    COUNTIF(idx.close IS NULL OR idx.pre_close IS NULL OR idx.pct_chg IS NULL) AS bad_price_count
  FROM `data-aquarium.ashare_dwd.dwd_index_eod` AS idx
  WHERE idx.sec_code = p_benchmark
    AND idx.trade_date BETWEEN p_predict_start AND p_predict_end
  GROUP BY idx.trade_date
),
window_bounds AS (
  SELECT MIN(trade_date) AS first_open_date
  FROM window_calendar
),
prev_open AS (
  SELECT MAX(cal.cal_date) AS prev_trade_date
  FROM `data-aquarium.ashare_dim.dim_trade_calendar` AS cal
  CROSS JOIN window_bounds AS wb
  WHERE cal.exchange = 'SSE'
    AND cal.is_open = 1
    AND cal.cal_date < wb.first_open_date
)
SELECT
  COUNT(*) AS open_days,
  COUNTIF(b.trade_date IS NULL) AS missing_open_days,
  COUNTIF(b.row_count > 1) AS duplicate_open_days,
  COUNTIF(b.bad_price_count > 0) AS bad_price_days,
  (
    SELECT COUNT(*)
    FROM `data-aquarium.ashare_dwd.dwd_index_eod` AS idx
    CROSS JOIN prev_open AS p
    WHERE idx.sec_code = p_benchmark
      AND idx.trade_date = p.prev_trade_date
      AND idx.trade_date BETWEEN DATE_SUB(p_predict_start, INTERVAL 10 DAY) AND p_predict_start
      AND idx.close IS NOT NULL
  ) AS previous_close_rows
FROM window_calendar AS c
LEFT JOIN benchmark AS b
  ON b.trade_date = c.trade_date;

ASSERT (
  SELECT
    open_days > 0
    AND missing_open_days = 0
    AND duplicate_open_days = 0
    AND bad_price_days = 0
    AND previous_close_rows = 1
  FROM benchmark_window_check
) AS 'benchmark must have exactly one non-null close/pre_close/pct_chg row for every open day and a prior close before window start';

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
  -- t+1 执行日：用交易日历自连接按 seq+1 取下一交易日（去相关子查询）
  SELECT r.rebalance_date, nxt.trade_date AS exec_date
  FROM rdates AS r
  JOIN cal AS rc ON rc.trade_date = r.rebalance_date
  LEFT JOIN cal AS nxt ON nxt.trade_date_seq = rc.trade_date_seq + 1
)
SELECT rebalance_date, exec_date, ROW_NUMBER() OVER (ORDER BY exec_date) AS period_idx
FROM we WHERE exec_date IS NOT NULL;

SET p_max_period = (SELECT MAX(period_idx) FROM periods);

-- ── 选股池在各 period 的目标权重 ──
CREATE TEMP TABLE presence AS
SELECT pr.period_idx, pr.exec_date, pt.sec_code, pt.target_weight AS w
FROM periods AS pr
JOIN `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
  ON pt.rebalance_date = pr.rebalance_date
 AND pt.strategy_id = p_strategy_id AND pt.run_id = p_run_id
WHERE pt.rebalance_date BETWEEN p_predict_start AND p_predict_end;

-- ── 价格底表：选股池涉及的所有股票，predict_start..calendar_end ──
CREATE TEMP TABLE px_all AS
SELECT
  px.sec_code, px.trade_date,
  px.open, px.close,
  COALESCE(px.can_buy_open, FALSE) AS can_buy_open,
  COALESCE(px.can_sell_open, FALSE) AS can_sell_open
FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
WHERE px.trade_date BETWEEN p_predict_start AND p_calendar_end
  AND px.sec_code IN (SELECT DISTINCT sec_code FROM presence);

-- ── 估值用前向填充收盘价（停牌无价日沿用最近可用收盘）──
CREATE TEMP TABLE px_ffill AS
SELECT
  sec_code, trade_date,
  LAST_VALUE(close IGNORE NULLS) OVER (
    PARTITION BY sec_code ORDER BY trade_date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS close_ffill
FROM px_all;

-- ── ledger 状态表 ──
CREATE TEMP TABLE hold (sec_code STRING, shares FLOAT64);           -- 当前持仓（逐 period 变更）
CREATE TEMP TABLE snap (period_idx INT64, exec_date DATE, sec_code STRING, shares FLOAT64);  -- 每次调仓后持仓快照
CREATE TEMP TABLE cash_hist (period_idx INT64, exec_date DATE, cash_after FLOAT64);          -- 每次调仓后现金
CREATE TEMP TABLE ledger_trades (
  trade_date DATE, sec_code STRING, side STRING,
  filled_shares FLOAT64, fill_price FLOAT64, turnover_cny FLOAT64,
  fee_cny FLOAT64, cash_effect_cny FLOAT64, fill_status STRING);

SET v_cash = p_initial_capital;
SET v_p = 1;

WHILE v_p <= p_max_period DO
  SET v_exec = (SELECT exec_date FROM periods WHERE period_idx = v_p);

  -- 当前持仓在 exec 日的估值（开盘价优先，停牌无开盘价用 ffill 收盘）得到 NAV
  SET v_nav = v_cash + (
    SELECT COALESCE(SUM(h.shares * COALESCE(pe.open, pf.close_ffill)), 0)
    FROM hold AS h
    LEFT JOIN (SELECT sec_code, open FROM px_all WHERE trade_date = v_exec) AS pe ON pe.sec_code = h.sec_code
    LEFT JOIN (SELECT sec_code, close_ffill FROM px_ffill WHERE trade_date = v_exec) AS pf ON pf.sec_code = h.sec_code
  );

  -- 本 period 计划：持仓∪目标，计算各票当前价值、目标价值、应卖股数、应买金额
  CREATE OR REPLACE TEMP TABLE plan AS
  WITH universe AS (
    SELECT sec_code FROM hold
    UNION DISTINCT
    SELECT sec_code FROM presence WHERE period_idx = v_p
  ),
  joined AS (
    SELECT
      u.sec_code,
      COALESCE(h.shares, 0) AS cur_shares,
      pe.open AS exec_open,
      COALESCE(pe.can_buy_open, FALSE) AS can_buy,
      COALESCE(pe.can_sell_open, FALSE) AS can_sell,
      COALESCE(pe.open, pf.close_ffill) AS val_price,
      COALESCE(t.w, 0) AS w
    FROM universe AS u
    LEFT JOIN hold AS h ON h.sec_code = u.sec_code
    LEFT JOIN (SELECT sec_code, w FROM presence WHERE period_idx = v_p) AS t ON t.sec_code = u.sec_code
    LEFT JOIN (SELECT sec_code, open, can_buy_open, can_sell_open FROM px_all WHERE trade_date = v_exec) AS pe ON pe.sec_code = u.sec_code
    LEFT JOIN (SELECT sec_code, close_ffill FROM px_ffill WHERE trade_date = v_exec) AS pf ON pf.sec_code = u.sec_code
  ),
  valued AS (
    SELECT *,
      cur_shares * val_price AS cur_value,
      w * v_nav AS desired_value
    FROM joined
  )
  SELECT
    sec_code, cur_shares, exec_open, can_buy, can_sell, val_price, w, cur_value, desired_value,
    -- 应卖股数：目标价值低于现值且可卖且有开盘价
    IF(cur_shares > 0 AND can_sell AND exec_open IS NOT NULL AND cur_value - desired_value > 0.01,
       LEAST(cur_shares, SAFE_DIVIDE(cur_value - desired_value, exec_open)), 0.0) AS sell_shares,
    -- 应买金额：目标价值高于现值且可买且有开盘价
    IF(can_buy AND exec_open IS NOT NULL AND desired_value - cur_value > 0.01,
       desired_value - cur_value, 0.0) AS want_value
  FROM valued;

  -- 卖出先入账（现金 += 卖出净额）
  SET v_cash = v_cash + (
    SELECT COALESCE(SUM(sell_shares * exec_open * (1 - p_cost_bps / 10000.0)), 0)
    FROM plan WHERE sell_shares > 0.000001
  );

  -- 买入受现金约束：总买入含成本超现金则等比缩放
  SET v_scale = (
    SELECT COALESCE(LEAST(1.0,
      SAFE_DIVIDE(v_cash, NULLIF(SUM(want_value * (1 + p_cost_bps / 10000.0)), 0))), 1.0)
    FROM plan WHERE want_value > 0.000001
  );
  SET v_scale = COALESCE(v_scale, 1.0);

  -- 买入扣现金
  SET v_cash = v_cash - (
    SELECT COALESCE(SUM(want_value * v_scale * (1 + p_cost_bps / 10000.0)), 0)
    FROM plan WHERE want_value > 0.000001
  );

  -- 记录成交（卖出 + 买入）
  INSERT INTO ledger_trades (trade_date, sec_code, side, filled_shares, fill_price, turnover_cny, fee_cny, cash_effect_cny, fill_status)
  SELECT v_exec, sec_code, 'SELL',
    sell_shares, exec_open, sell_shares * exec_open,
    sell_shares * exec_open * (p_cost_bps / 10000.0),
    sell_shares * exec_open * (1 - p_cost_bps / 10000.0), 'FILLED'
  FROM plan WHERE sell_shares > 0.000001
  UNION ALL
  SELECT v_exec, sec_code, 'BUY',
    SAFE_DIVIDE(want_value * v_scale, exec_open), exec_open, want_value * v_scale,
    want_value * v_scale * (p_cost_bps / 10000.0),
    -(want_value * v_scale * (1 + p_cost_bps / 10000.0)), 'FILLED'
  FROM plan WHERE want_value > 0.000001 AND v_scale > 0;

  -- 更新持仓（netting：现有 − 卖出 + 买入），保留正持仓
  CREATE OR REPLACE TEMP TABLE hold AS
  SELECT sec_code, shares FROM (
    SELECT sec_code,
      cur_shares - sell_shares + SAFE_DIVIDE(want_value * v_scale, exec_open) AS shares
    FROM plan
  )
  WHERE shares > 0.000001;

  -- 快照本期持仓与现金
  INSERT INTO snap SELECT v_p, v_exec, sec_code, shares FROM hold;
  INSERT INTO cash_hist VALUES (v_p, v_exec, v_cash);

  SET v_p = v_p + 1;
END WHILE;

-- ── 写成交表 ──
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_trade_daily`
(backtest_id, trade_date, sec_code, side, planned_shares, filled_shares,
 fill_price, turnover_cny, fee_cny, tax_cny, slippage_cny, cash_effect_cny,
 fill_status, run_id, created_at)
SELECT
  p_backtest_id, lt.trade_date, lt.sec_code, lt.side,
  lt.filled_shares, lt.filled_shares, lt.fill_price, lt.turnover_cny,
  lt.fee_cny, 0.0, 0.0, lt.cash_effect_cny, lt.fill_status,
  p_run_id, CURRENT_TIMESTAMP()
FROM ledger_trades AS lt;

-- ── 每个开市日映射到「<=该日的最近一次调仓」──
CREATE TEMP TABLE day_period AS
SELECT c.trade_date, MAX(ch.exec_date) AS active_exec
FROM cal AS c
LEFT JOIN cash_hist AS ch ON ch.exec_date <= c.trade_date
WHERE c.trade_date BETWEEN p_predict_start AND p_predict_end
GROUP BY c.trade_date;

-- ── 每日持仓（按最近快照 × 当日 ffill 收盘估值）──
CREATE TEMP TABLE pos_daily AS
SELECT
  dp.trade_date, s.sec_code, s.shares AS net_shares,
  pf.close_ffill AS close_raw,
  s.shares * pf.close_ffill AS market_value
FROM day_period AS dp
JOIN snap AS s ON s.exec_date = dp.active_exec
LEFT JOIN px_ffill AS pf ON pf.sec_code = s.sec_code AND pf.trade_date = dp.trade_date;

-- ── 每日现金（取最近一次调仓后的现金；首个调仓前为初始资金）──
CREATE TEMP TABLE cash_daily AS
SELECT dp.trade_date, COALESCE(ch.cash_after, p_initial_capital) AS cash_cny
FROM day_period AS dp
LEFT JOIN cash_hist AS ch ON ch.exec_date = dp.active_exec;

-- ── 每日 NAV ──
CREATE TEMP TABLE nav_daily AS
SELECT
  cd.trade_date, cd.cash_cny,
  COALESCE(pv.mv_sum, 0) AS mv_sum,
  cd.cash_cny + COALESCE(pv.mv_sum, 0) AS nav_value
FROM cash_daily AS cd
LEFT JOIN (SELECT trade_date, SUM(market_value) AS mv_sum FROM pos_daily GROUP BY trade_date) AS pv
  ON pv.trade_date = cd.trade_date;

-- ── 写持仓表 ──
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_position_daily`
(backtest_id, trade_date, sec_code, shares, close, market_value_cny, weight,
 unrealized_pnl_cny, run_id, created_at)
SELECT
  p_backtest_id, pd.trade_date, pd.sec_code, pd.net_shares, pd.close_raw, pd.market_value,
  SAFE_DIVIDE(pd.market_value, NULLIF(nav.nav_value, 0)),
  CAST(NULL AS FLOAT64), p_run_id, CURRENT_TIMESTAMP()
FROM pos_daily AS pd
JOIN nav_daily AS nav ON nav.trade_date = pd.trade_date;

-- ── 写 NAV 表（含 benchmark 与超额收益）──
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_nav_daily`
(backtest_id, trade_date, nav, cash_cny, net_value_cny, gross_exposure,
 turnover_cny, cost_cny, daily_return, benchmark_sec_code, benchmark_return,
 excess_return, run_id, created_at)
WITH day_cost AS (
  SELECT trade_date, SUM(turnover_cny) AS turnover_cny, SUM(fee_cny) AS cost_cny
  FROM ledger_trades GROUP BY trade_date
),
nav_norm AS (
  SELECT
    n.trade_date, n.cash_cny, n.mv_sum, n.nav_value,
    n.nav_value / p_initial_capital AS nav,
    n.nav_value / NULLIF(LAG(n.nav_value) OVER (ORDER BY n.trade_date), 0) - 1.0 AS daily_return,
    COALESCE(dc.turnover_cny, 0) AS turnover_cny,
    COALESCE(dc.cost_cny, 0) AS cost_cny
  FROM nav_daily AS n
  LEFT JOIN day_cost AS dc ON dc.trade_date = n.trade_date
)
SELECT
  p_backtest_id, nn.trade_date, nn.nav, nn.cash_cny, nn.nav_value,
  SAFE_DIVIDE(nn.mv_sum, NULLIF(nn.nav_value, 0)),
  nn.turnover_cny, nn.cost_cny, nn.daily_return, p_benchmark,
  idx.pct_chg / 100.0,
  nn.daily_return - COALESCE(idx.pct_chg / 100.0, 0),
  p_run_id, CURRENT_TIMESTAMP()
FROM nav_norm AS nn
LEFT JOIN `data-aquarium.ashare_dwd.dwd_index_eod` AS idx
  ON idx.sec_code = p_benchmark AND idx.trade_date = nn.trade_date
  AND idx.trade_date BETWEEN p_predict_start AND p_calendar_end;
