-- 文档维护：GPT-5（最近更新 2026-06-01）
-- BigQuery Standard SQL
-- OQ-004 指数 canonical 映射、端点可用性与 runner benchmark 窗口断言。
-- 本脚本校验 OQ-004 示例 benchmark/window；真实 runner 参数窗口由 08_run_backtest.sql
-- 的前置 ASSERT 使用 p_benchmark / p_predict_start / p_predict_end 再校验。
-- A 股沪深两市交易日历实际一致，窗口覆盖断言统一使用 SSE 日历代表全市场开市日。

DECLARE dwd_start_date DATE DEFAULT DATE '2019-01-01';
DECLARE dwd_end_date DATE DEFAULT CURRENT_DATE('Asia/Shanghai');
DECLARE p_benchmark STRING DEFAULT '000852.SH';
DECLARE p_window_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_window_end DATE DEFAULT DATE '2025-12-31';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT source_sec_code, COUNT(*) AS n
    FROM `data-aquarium.ashare_dim.dim_index`
    WHERE source_sec_code IS NOT NULL
    GROUP BY source_sec_code
    HAVING n > 1
  )
) AS 'dim_index.source_sec_code must be unique';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT sec_code, source_sec_code, COUNT(*) AS n
    FROM `data-aquarium.ashare_dim.dim_index`
    GROUP BY sec_code, source_sec_code
    HAVING n > 1
  )
) AS 'dim_index canonical/source mapping must be unique';

ASSERT (
  SELECT COUNT(*) = 1
  FROM `data-aquarium.ashare_dim.dim_index`
  WHERE source_sec_code = '399300.SZ'
    AND sec_code = '000300.SH'
    AND daily_endpoint = 'index_daily_399300_SZ'
) AS 'dim_index must map ODS 399300.SZ to canonical 000300.SH';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_dim.dim_index`
  WHERE is_benchmark_candidate
    AND NOT has_daily
) AS 'dim_index cannot mark indexes without daily endpoint as benchmark candidates';

ASSERT (
  SELECT COUNT(*) = 1
  FROM `data-aquarium.ashare_dim.dim_index`
  WHERE sec_code = '000852.SH'
    AND source_sec_code = '000852.SH'
    AND has_daily
    AND NOT has_dailybasic
) AS 'CSI1000 must have daily data and no dailybasic availability in current ODS snapshot';

ASSERT (
  SELECT COUNT(*) > 0
  FROM `data-aquarium.ashare_dwd.dwd_index_eod`
  WHERE sec_code = '000852.SH'
    AND trade_date BETWEEN dwd_start_date AND dwd_end_date
    AND close IS NOT NULL
) AS 'dwd_index_eod must contain 2019+ CSI1000 price rows';

ASSERT (
  SELECT COUNT(*) > 0
  FROM `data-aquarium.ashare_dwd.dwd_index_eod`
  WHERE sec_code = '000300.SH'
    AND source_sec_code = '399300.SZ'
    AND trade_date BETWEEN dwd_start_date AND dwd_end_date
) AS 'dwd_index_eod must expose canonical CSI300 sec_code and preserve source_sec_code=399300.SZ';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_dwd.dwd_index_eod`
  WHERE sec_code = '000852.SH'
    AND trade_date BETWEEN dwd_start_date AND dwd_end_date
    AND (
      total_mv_cny IS NOT NULL
      OR float_mv_cny IS NOT NULL
      OR pe IS NOT NULL
      OR pe_ttm IS NOT NULL
      OR pb IS NOT NULL
    )
) AS 'CSI1000 must not expose dailybasic valuation fields until ODS dailybasic endpoint exists';

ASSERT (
  SELECT COUNT(*) = 1
  FROM `data-aquarium.ashare_dim.dim_index`
  WHERE sec_code = p_benchmark
    AND has_daily
    AND is_benchmark_candidate
) AS 'runner example benchmark must be a dim_index has_daily benchmark candidate';

ASSERT (
  WITH window_calendar AS (
    SELECT cal_date AS trade_date
    FROM `data-aquarium.ashare_dim.dim_trade_calendar`
    WHERE exchange = 'SSE'
      AND is_open = 1
      AND cal_date BETWEEN p_window_start AND p_window_end
  ),
  benchmark AS (
    SELECT
      idx.trade_date,
      COUNT(*) AS row_count,
      COUNTIF(idx.close IS NULL OR idx.pre_close IS NULL OR idx.pct_chg IS NULL) AS bad_price_count
    FROM `data-aquarium.ashare_dwd.dwd_index_eod` AS idx
    WHERE idx.sec_code = p_benchmark
      AND idx.trade_date BETWEEN p_window_start AND p_window_end
    GROUP BY idx.trade_date
  ),
  coverage AS (
    SELECT
      COUNT(*) AS open_days,
      COUNTIF(b.trade_date IS NULL) AS missing_open_days,
      COUNTIF(b.row_count > 1) AS duplicate_open_days,
      COUNTIF(b.bad_price_count > 0) AS bad_price_days
    FROM window_calendar AS c
    LEFT JOIN benchmark AS b
      ON b.trade_date = c.trade_date
  )
  SELECT
    open_days > 0
    AND missing_open_days = 0
    AND duplicate_open_days = 0
    AND bad_price_days = 0
  FROM coverage
) AS 'runner example benchmark must cover every open day in the backtest window with valid price rows';

ASSERT (
  WITH first_open AS (
    SELECT MIN(cal_date) AS first_trade_date
    FROM `data-aquarium.ashare_dim.dim_trade_calendar`
    WHERE exchange = 'SSE'
      AND is_open = 1
      AND cal_date BETWEEN p_window_start AND p_window_end
  ),
  prev_open AS (
    SELECT MAX(cal.cal_date) AS prev_trade_date
    FROM `data-aquarium.ashare_dim.dim_trade_calendar` AS cal
    CROSS JOIN first_open AS f
    WHERE cal.exchange = 'SSE'
      AND cal.is_open = 1
      AND cal.cal_date < f.first_trade_date
  )
  SELECT COUNT(*) = 1
  FROM `data-aquarium.ashare_dwd.dwd_index_eod` AS idx
  CROSS JOIN prev_open AS p
  WHERE idx.sec_code = p_benchmark
    AND idx.trade_date = p.prev_trade_date
    AND idx.trade_date BETWEEN DATE_SUB(p_window_start, INTERVAL 10 DAY) AND p_window_start
    AND idx.close IS NOT NULL
) AS 'runner example benchmark must have a previous close before the benchmark window';
