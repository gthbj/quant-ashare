-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 08: 回测【ledger_exec_v1 = 日级账户 ledger】。
--
-- 交易语义：
--   * ads_portfolio_target_daily.rebalance_date 是 signal_date；本脚本推导 execution_date = 下一开市日。
--   * execution_date 开盘成交；目标市值用执行日前最近可用收盘价估算的执行前 NAV 定档。
--   * 卖出先于买入；买入受卖出后现金约束，现金不足时按买入需求等比例缩放。
--   * 所有订单都基于实际持仓与目标持仓的净差额 netting，旧仓重新入选时不重复全额建仓。
--   * 卖不出进入 pending_sell，并在后续每个开市日继续尝试卖出，直到成交、被 netting 取消或已达目标。
--   * 买不进不做候补，不每日追买，只在下一次目标生成或净买入机会重新评估。
--   * 非目标持仓允许继续存在，作为实际持仓计入 NAV。
--   * 每个开市日收盘 mark-to-market 生成 NAV；停牌/无收盘价用最近可用收盘价前向填充。
--
-- 不变量由 10_qa_runner_outputs.sql 校验：现金不为负、无杠杆、持仓唯一、NAV 覆盖全开市日、
-- 成交价匹配分项滑点、pending sell 日级重试。

DECLARE p_run_id STRING DEFAULT 's1_bqml_livepool_oriented_20260603_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_bqml_livepool_oriented_20260603_01';
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
DECLARE p_cost_bps FLOAT64 DEFAULT 30.0;        -- 兼容字段，不再作为默认撮合成本来源
DECLARE p_benchmark STRING DEFAULT '000852.SH';  -- OQ-010 示例值
DECLARE p_force_replace BOOL DEFAULT FALSE;
DECLARE p_calendar_end DATE;
DECLARE p_price_start DATE;
DECLARE p_max_day INT64;
-- ledger 循环状态变量
DECLARE v_d INT64;
DECLARE v_exec DATE;
DECLARE v_period_idx INT64;
DECLARE v_is_rebalance BOOL;
DECLARE v_cash FLOAT64;
DECLARE v_nav FLOAT64;
DECLARE v_scale FLOAT64;

SET p_calendar_end = DATE_ADD(p_predict_end, INTERVAL 90 DAY);
SET p_price_start = DATE_SUB(p_predict_start, INTERVAL 10 DAY);

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

CREATE TEMP TABLE exec_days AS
SELECT trade_date, ROW_NUMBER() OVER (ORDER BY trade_date) AS day_idx
FROM cal
WHERE trade_date BETWEEN p_predict_start AND p_predict_end;

SET p_max_day = (SELECT MAX(day_idx) FROM exec_days);

-- ── period：signal_date(rebalance_date) → execution_date(next open day) ──
CREATE TEMP TABLE periods AS
WITH rdates AS (
  SELECT DISTINCT pt.rebalance_date
  FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
  WHERE pt.strategy_id = p_strategy_id AND pt.run_id = p_run_id
    AND pt.rebalance_date BETWEEN p_predict_start AND p_predict_end
),
we AS (
  SELECT r.rebalance_date AS signal_date, nxt.trade_date AS exec_date
  FROM rdates AS r
  JOIN cal AS rc ON rc.trade_date = r.rebalance_date
  LEFT JOIN cal AS nxt ON nxt.trade_date_seq = rc.trade_date_seq + 1
)
SELECT
  signal_date,
  exec_date,
  ROW_NUMBER() OVER (ORDER BY exec_date, signal_date) AS period_idx
FROM we
WHERE exec_date IS NOT NULL
  AND exec_date BETWEEN p_predict_start AND p_predict_end;

-- ── 选股池在各 period 的目标权重 ──
CREATE TEMP TABLE presence AS
SELECT pr.period_idx, pr.signal_date, pr.exec_date, pt.sec_code, pt.target_weight AS w
FROM periods AS pr
JOIN `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
  ON pt.rebalance_date = pr.signal_date
 AND pt.strategy_id = p_strategy_id AND pt.run_id = p_run_id
WHERE pt.rebalance_date BETWEEN p_predict_start AND p_predict_end;

-- ── 价格底表：目标池涉及股票，额外读取 10 天用于执行前收盘估值 ──
CREATE TEMP TABLE px_all AS
SELECT
  px.sec_code, px.trade_date,
  px.open, px.close,
  COALESCE(px.can_buy_open, FALSE) AS can_buy_open,
  COALESCE(px.can_sell_open, FALSE) AS can_sell_open
FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
WHERE px.trade_date BETWEEN p_price_start AND p_calendar_end
  AND px.sec_code IN (SELECT DISTINCT sec_code FROM presence);

-- ── 收盘价前向填充：NAV 用当日 close_ffill，执行前 NAV 用 prev_close_ffill ──
CREATE TEMP TABLE px_ffill AS
SELECT
  sec_code, trade_date,
  LAST_VALUE(close IGNORE NULLS) OVER (
    PARTITION BY sec_code ORDER BY trade_date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS close_ffill,
  LAST_VALUE(close IGNORE NULLS) OVER (
    PARTITION BY sec_code ORDER BY trade_date
    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prev_close_ffill
FROM px_all;

-- ── ledger 状态表 ──
CREATE TEMP TABLE hold (sec_code STRING, shares FLOAT64);             -- 当前实际持仓（日级变更）
CREATE TEMP TABLE target (sec_code STRING, w FLOAT64);                -- 最新目标组合权重，仅在 execution_date 更新
CREATE TEMP TABLE pending_sell (sec_code STRING);                     -- 未卖出的退出/降仓意图，日级重试
CREATE TEMP TABLE snap (trade_date DATE, sec_code STRING, shares FLOAT64);  -- 每日收盘后持仓快照
CREATE TEMP TABLE cash_hist (trade_date DATE, cash_after FLOAT64);          -- 每日收盘后现金
CREATE TEMP TABLE ledger_trades (
  trade_date DATE, sec_code STRING, side STRING,
  planned_shares FLOAT64, filled_shares FLOAT64, fill_price FLOAT64, turnover_cny FLOAT64,
  fee_cny FLOAT64, cash_effect_cny FLOAT64, fill_status STRING);

SET v_cash = p_initial_capital;
SET v_d = 1;

WHILE v_d <= p_max_day DO
  SET v_exec = (SELECT trade_date FROM exec_days WHERE day_idx = v_d);
  SET v_period_idx = (SELECT period_idx FROM periods WHERE exec_date = v_exec ORDER BY period_idx LIMIT 1);
  SET v_is_rebalance = v_period_idx IS NOT NULL;

  IF v_is_rebalance THEN
    CREATE OR REPLACE TEMP TABLE target AS
    SELECT sec_code, w
    FROM presence
    WHERE period_idx = v_period_idx;
  END IF;

  -- 执行前 NAV：现金 + 实际持仓按执行日前最近可用收盘价估值，缺口兜底用当日开盘/ffill 收盘。
  SET v_nav = v_cash + (
    SELECT COALESCE(SUM(h.shares * COALESCE(pf.prev_close_ffill, pe.open, pf.close_ffill)), 0)
    FROM hold AS h
    LEFT JOIN (SELECT sec_code, open FROM px_all WHERE trade_date = v_exec) AS pe
      ON pe.sec_code = h.sec_code
    LEFT JOIN (SELECT sec_code, prev_close_ffill, close_ffill FROM px_ffill WHERE trade_date = v_exec) AS pf
      ON pf.sec_code = h.sec_code
  );

  -- 本日计划：
  --   * rebalance execution_date：实际持仓 ∪ 目标 ∪ pending_sell，做完整 netting。
  --   * 非 rebalance 日：仅 pending_sell/实际持仓参与，禁止每日追买，只重试 pending sell。
  CREATE OR REPLACE TEMP TABLE plan AS
  WITH universe AS (
    SELECT sec_code FROM hold
    UNION DISTINCT
    SELECT sec_code FROM target WHERE v_is_rebalance
    UNION DISTINCT
    SELECT sec_code FROM pending_sell
  ),
  joined AS (
    SELECT
      u.sec_code,
      COALESCE(h.shares, 0) AS cur_shares,
      pe.open AS exec_open,
      pe.open * (1 + p_slippage_buy_bps / 10000.0) AS buy_fill_price,
      pe.open * (1 - p_slippage_sell_bps / 10000.0) AS sell_fill_price,
      COALESCE(pe.can_buy_open, FALSE) AS can_buy,
      COALESCE(pe.can_sell_open, FALSE) AS can_sell,
      COALESCE(pf.prev_close_ffill, pe.open, pf.close_ffill) AS val_price,
      COALESCE(t.w, 0) AS w,
      ps.sec_code IS NOT NULL AS was_pending
    FROM universe AS u
    LEFT JOIN hold AS h ON h.sec_code = u.sec_code
    LEFT JOIN target AS t ON t.sec_code = u.sec_code
    LEFT JOIN pending_sell AS ps ON ps.sec_code = u.sec_code
    LEFT JOIN (SELECT sec_code, open, can_buy_open, can_sell_open FROM px_all WHERE trade_date = v_exec) AS pe
      ON pe.sec_code = u.sec_code
    LEFT JOIN (SELECT sec_code, prev_close_ffill, close_ffill FROM px_ffill WHERE trade_date = v_exec) AS pf
      ON pf.sec_code = u.sec_code
  ),
  valued AS (
    SELECT
      *,
      cur_shares * val_price AS cur_value,
      w * v_nav AS desired_value
    FROM joined
  )
  SELECT
    sec_code, cur_shares, exec_open, buy_fill_price, sell_fill_price,
    can_buy, can_sell, val_price, w, was_pending,
    cur_value, desired_value,
    -- 卖出：rebalance 日处理净卖出；非 rebalance 日只处理 pending sell。
    IF(
      cur_shares > 0
      AND (v_is_rebalance OR was_pending)
      AND cur_value - desired_value > 0.01
      AND can_sell
      AND exec_open IS NOT NULL,
      CASE
        WHEN desired_value <= 0.01 THEN cur_shares
        ELSE LEAST(cur_shares, SAFE_DIVIDE(cur_value - desired_value, exec_open))
      END,
      0.0
    ) AS sell_shares,
    -- 买入：只允许 rebalance 日按 netting 补差；此前买不进的缺口不每日追买。
    IF(
      v_is_rebalance
      AND can_buy
      AND exec_open IS NOT NULL
      AND desired_value - cur_value > 0.01,
      desired_value - cur_value,
      0.0
    ) AS want_value,
    -- 卖出失败：rebalance 日写 SELL_SKIPPED_UNTRADABLE；非 rebalance 日写 PENDING_SELL_CARRY。
    IF(
      cur_shares > 0
      AND (v_is_rebalance OR was_pending)
      AND cur_value - desired_value > 0.01
      AND NOT (can_sell AND exec_open IS NOT NULL),
      CASE
        WHEN desired_value <= 0.01 THEN cur_shares
        ELSE LEAST(cur_shares, SAFE_DIVIDE(cur_value - desired_value, COALESCE(exec_open, val_price)))
      END,
      0.0
    ) AS sell_skip_shares,
    -- 买入失败：只在 rebalance 日记录，不候补。
    IF(
      v_is_rebalance
      AND desired_value - cur_value > 0.01
      AND NOT (can_buy AND exec_open IS NOT NULL),
      desired_value - cur_value,
      0.0
    ) AS buy_skip_value,
    -- pending 已因目标提高/重新入选或市值变化达到目标，无需继续卖。
    IF(
      was_pending
      AND cur_shares > 0
      AND NOT (cur_value - desired_value > 0.01),
      TRUE,
      FALSE
    ) AS pending_noop
  FROM valued;

  -- 卖出先入账（现金 += 卖出净额 = gross_turnover - commission - stamp_tax）。
  SET v_cash = v_cash + (
    SELECT COALESCE(SUM(
      sell_shares * sell_fill_price
      - GREATEST(sell_shares * sell_fill_price * p_commission_bps / 10000.0, p_min_commission_cny)
      - sell_shares * sell_fill_price * p_stamp_tax_sell_bps / 10000.0
    ), 0)
    FROM plan
    WHERE sell_shares > 0.000001
  );

  -- 买入受现金约束：required_cash = gross_turnover + commission + stamp_tax。
  SET v_scale = (
    SELECT COALESCE(LEAST(1.0, SAFE_DIVIDE(v_cash, NULLIF(SUM(
      want_value * (1 + p_slippage_buy_bps / 10000.0)
      + GREATEST(
          want_value * (1 + p_slippage_buy_bps / 10000.0) * p_commission_bps / 10000.0,
          p_min_commission_cny
        )
      + want_value * (1 + p_slippage_buy_bps / 10000.0) * p_stamp_tax_buy_bps / 10000.0
    ), 0))), 1.0)
    FROM plan
    WHERE want_value > 0.000001
  );
  SET v_scale = COALESCE(v_scale, 1.0);

  -- 买入扣现金。
  SET v_cash = v_cash - (
    SELECT COALESCE(SUM(
      want_value * v_scale * (1 + p_slippage_buy_bps / 10000.0)
      + GREATEST(
          want_value * v_scale * (1 + p_slippage_buy_bps / 10000.0) * p_commission_bps / 10000.0,
          p_min_commission_cny
        )
      + want_value * v_scale * (1 + p_slippage_buy_bps / 10000.0) * p_stamp_tax_buy_bps / 10000.0
    ), 0)
    FROM plan
    WHERE want_value > 0.000001 AND v_scale > 0.000001
  );

  -- 记录成交、失败、缩放、取消/NOOP 状态。
  INSERT INTO ledger_trades (trade_date, sec_code, side, planned_shares, filled_shares, fill_price, turnover_cny, fee_cny, cash_effect_cny, fill_status)
  -- SELL filled.
  SELECT v_exec, sec_code, 'SELL',
    sell_shares, sell_shares, sell_fill_price,
    sell_shares * sell_fill_price,
    GREATEST(sell_shares * sell_fill_price * p_commission_bps / 10000.0, p_min_commission_cny)
      + sell_shares * sell_fill_price * p_stamp_tax_sell_bps / 10000.0,
    sell_shares * sell_fill_price
      - GREATEST(sell_shares * sell_fill_price * p_commission_bps / 10000.0, p_min_commission_cny)
      - sell_shares * sell_fill_price * p_stamp_tax_sell_bps / 10000.0,
    'FILLED'
  FROM plan
  WHERE sell_shares > 0.000001
  UNION ALL
  -- BUY filled, optionally scaled by cash.
  SELECT v_exec, sec_code, 'BUY',
    SAFE_DIVIDE(want_value, exec_open),
    SAFE_DIVIDE(want_value * v_scale, exec_open),
    buy_fill_price,
    want_value * v_scale * (1 + p_slippage_buy_bps / 10000.0),
    GREATEST(want_value * v_scale * (1 + p_slippage_buy_bps / 10000.0) * p_commission_bps / 10000.0, p_min_commission_cny)
      + want_value * v_scale * (1 + p_slippage_buy_bps / 10000.0) * p_stamp_tax_buy_bps / 10000.0,
    -(want_value * v_scale * (1 + p_slippage_buy_bps / 10000.0)
      + GREATEST(want_value * v_scale * (1 + p_slippage_buy_bps / 10000.0) * p_commission_bps / 10000.0, p_min_commission_cny)
      + want_value * v_scale * (1 + p_slippage_buy_bps / 10000.0) * p_stamp_tax_buy_bps / 10000.0),
    IF(v_scale < 0.999999, 'FILLED_SCALED_CASH', 'FILLED')
  FROM plan
  WHERE want_value > 0.000001 AND v_scale > 0.000001
  UNION ALL
  -- BUY skipped because available cash is effectively zero after scaling.
  SELECT v_exec, sec_code, 'BUY',
    SAFE_DIVIDE(want_value, exec_open), 0.0, CAST(NULL AS FLOAT64), 0.0, 0.0, 0.0,
    'SKIPPED_CASH_INSUFFICIENT'
  FROM plan
  WHERE want_value > 0.000001 AND v_scale <= 0.000001
  UNION ALL
  -- SELL skipped/carry: no fill, holding remains.
  SELECT v_exec, sec_code, 'SELL',
    sell_skip_shares, 0.0, CAST(NULL AS FLOAT64), 0.0, 0.0, 0.0,
    IF(v_is_rebalance, 'SELL_SKIPPED_UNTRADABLE', 'PENDING_SELL_CARRY')
  FROM plan
  WHERE sell_skip_shares > 0.000001
  UNION ALL
  -- BUY skipped: no fallback candidate.
  SELECT v_exec, sec_code, 'BUY',
    COALESCE(SAFE_DIVIDE(buy_skip_value, val_price), 0.0), 0.0, CAST(NULL AS FLOAT64), 0.0, 0.0, 0.0,
    'BUY_SKIPPED_UNTRADABLE'
  FROM plan
  WHERE buy_skip_value > 0.000001
  UNION ALL
  -- pending sell cancelled by rebalance netting / target increase.
  SELECT v_exec, sec_code, 'SELL',
    0.0, 0.0, CAST(NULL AS FLOAT64), 0.0, 0.0, 0.0,
    IF(v_is_rebalance, 'CANCELLED_BY_NETTING', 'NOOP_ALREADY_TARGET')
  FROM plan
  WHERE pending_noop;

  -- 更新实际持仓。
  CREATE OR REPLACE TEMP TABLE hold AS
  SELECT sec_code, shares
  FROM (
    SELECT
      sec_code,
      cur_shares - sell_shares
        + IF(v_scale > 0.000001, SAFE_DIVIDE(want_value * v_scale, exec_open), 0.0) AS shares
    FROM plan
  )
  WHERE shares > 0.000001;

  -- 更新 pending_sell：仍持有且仍高于目标的卖出意图继续保留。
  CREATE OR REPLACE TEMP TABLE pending_sell AS
  SELECT DISTINCT sec_code
  FROM (
    SELECT
      sec_code,
      cur_shares - sell_shares AS remaining_shares,
      (cur_shares - sell_shares) * val_price AS remaining_value,
      desired_value,
      sell_skip_shares,
      was_pending
    FROM plan
  )
  WHERE remaining_shares > 0.000001
    AND remaining_value - desired_value > 0.01
    AND (sell_skip_shares > 0.000001 OR was_pending OR v_is_rebalance);

  -- 每日收盘后快照持仓与现金。
  INSERT INTO snap SELECT v_exec, sec_code, shares FROM hold;
  INSERT INTO cash_hist VALUES (v_exec, v_cash);

  SET v_d = v_d + 1;
END WHILE;

-- ── 写成交表 ──
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_trade_daily`
(backtest_id, trade_date, sec_code, side, planned_shares, filled_shares,
 fill_price, turnover_cny, fee_cny, tax_cny, slippage_cny, cash_effect_cny,
 fill_status, run_id, created_at)
SELECT
  p_backtest_id, lt.trade_date, lt.sec_code, lt.side,
  lt.planned_shares, lt.filled_shares, lt.fill_price, lt.turnover_cny,
  lt.fee_cny,
  -- tax_cny: 印花税（买入 0，卖出按 stamp_tax_sell_bps）
  CASE WHEN lt.side = 'SELL' THEN lt.turnover_cny * p_stamp_tax_sell_bps / 10000.0
       WHEN lt.side = 'BUY'  THEN lt.turnover_cny * p_stamp_tax_buy_bps / 10000.0
       ELSE 0.0 END,
  -- slippage_cny: 滑点金额（从 fill_price 反推 exec_open 计算）
  CASE WHEN lt.side = 'SELL' AND lt.filled_shares > 0
         THEN lt.turnover_cny * p_slippage_sell_bps / (10000.0 - p_slippage_sell_bps)
       WHEN lt.side = 'BUY' AND lt.filled_shares > 0
         THEN lt.turnover_cny * p_slippage_buy_bps / (10000.0 + p_slippage_buy_bps)
       ELSE 0.0 END,
  lt.cash_effect_cny, lt.fill_status,
  p_run_id, CURRENT_TIMESTAMP()
FROM ledger_trades AS lt;

-- ── 每日持仓（每日快照 × 当日 ffill 收盘估值）──
CREATE TEMP TABLE pos_daily AS
SELECT
  s.trade_date, s.sec_code, s.shares AS net_shares,
  COALESCE(pf.close_ffill, pa.open) AS close_raw,
  s.shares * COALESCE(pf.close_ffill, pa.open) AS market_value
FROM snap AS s
LEFT JOIN px_ffill AS pf ON pf.sec_code = s.sec_code AND pf.trade_date = s.trade_date
LEFT JOIN px_all AS pa ON pa.sec_code = s.sec_code AND pa.trade_date = s.trade_date;

-- ── 每日 NAV ──
CREATE TEMP TABLE nav_daily AS
SELECT
  ch.trade_date,
  ch.cash_after AS cash_cny,
  COALESCE(pv.mv_sum, 0) AS mv_sum,
  ch.cash_after + COALESCE(pv.mv_sum, 0) AS nav_value
FROM cash_hist AS ch
LEFT JOIN (SELECT trade_date, SUM(market_value) AS mv_sum FROM pos_daily GROUP BY trade_date) AS pv
  ON pv.trade_date = ch.trade_date;

-- ── 写持仓表 ──
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_position_daily`
(backtest_id, trade_date, sec_code, shares, close, market_value_cny, weight,
 unrealized_pnl_cny, run_id, created_at)
SELECT
  p_backtest_id, pd.trade_date, pd.sec_code, pd.net_shares, pd.close_raw, pd.market_value,
  SAFE_DIVIDE(pd.market_value, NULLIF(nav.nav_value, 0)),
  CAST(NULL AS FLOAT64), p_run_id, CURRENT_TIMESTAMP()
FROM pos_daily AS pd
JOIN nav_daily AS nav ON nav.trade_date = pd.trade_date
WHERE pd.market_value IS NOT NULL;

-- ── 写 NAV 表（含 benchmark 与超额收益）──
INSERT INTO `data-aquarium.ashare_ads.ads_backtest_nav_daily`
(backtest_id, trade_date, nav, cash_cny, net_value_cny, gross_exposure,
 turnover_cny, cost_cny, daily_return, benchmark_sec_code, benchmark_return,
 excess_return, run_id, created_at)
WITH day_cost AS (
  SELECT
    trade_date,
    SUM(turnover_cny) AS turnover_cny,
    SUM(fee_cny) AS cost_cny
  FROM ledger_trades
  WHERE fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
  GROUP BY trade_date
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
