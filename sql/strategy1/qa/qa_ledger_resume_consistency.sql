-- BigQuery Standard SQL · Strategy 1 Cloud Run Python lot100 ledger QA.
-- Ledger state resume consistency QA.
--
-- 用途：比较同一窗口内：
--   1) fresh-start 对照切片；
--   2) 从 parent backtest state 恢复的 resume segment。

DECLARE p_full_backtest_id STRING DEFAULT NULL;
DECLARE p_resume_backtest_id STRING DEFAULT NULL;
DECLARE p_compare_start DATE DEFAULT NULL;
DECLARE p_compare_end DATE DEFAULT NULL;
DECLARE p_state_as_of_date DATE DEFAULT NULL;
DECLARE p_resume_policy_id STRING DEFAULT 'cloudrun_lot100_resume_v1';
DECLARE p_ledger_version STRING DEFAULT 'ledger_exec_v1_lot100';
DECLARE p_rebalance_anchor_start DATE DEFAULT NULL;
DECLARE p_corporate_actions STRING DEFAULT 'none_v1';
DECLARE p_dividend_tax_mode STRING DEFAULT 'flat_10pct';
DECLARE p_cash_tolerance_cny FLOAT64 DEFAULT 1.0;
DECLARE p_value_tolerance_cny FLOAT64 DEFAULT 1.0;
DECLARE p_share_tolerance FLOAT64 DEFAULT 1e-6;

ASSERT p_full_backtest_id IS NOT NULL AS 'p_full_backtest_id is required';
ASSERT p_resume_backtest_id IS NOT NULL AS 'p_resume_backtest_id is required';
ASSERT p_compare_start IS NOT NULL AS 'p_compare_start is required';
ASSERT p_compare_end IS NOT NULL AS 'p_compare_end is required';
ASSERT p_state_as_of_date IS NOT NULL AS 'p_state_as_of_date is required';
ASSERT p_rebalance_anchor_start IS NOT NULL AS 'p_rebalance_anchor_start is required';

IF p_compare_start > p_compare_end THEN
  RAISE USING MESSAGE = 'p_compare_start must be <= p_compare_end';
END IF;

IF p_corporate_actions NOT IN ('none_v1', 'cash_div_and_split_v1') THEN
  RAISE USING MESSAGE = CONCAT('unsupported p_corporate_actions: ', p_corporate_actions);
END IF;

IF p_dividend_tax_mode NOT IN ('flat_10pct') THEN
  RAISE USING MESSAGE = CONCAT('unsupported p_dividend_tax_mode: ', p_dividend_tax_mode);
END IF;

ASSERT (
  SELECT COUNT(*) = 1
  FROM `data-aquarium.ashare_dim.dim_trade_calendar` AS cal
  WHERE cal.exchange = 'SSE'
    AND cal.is_open = 1
    AND cal.cal_date = p_compare_start
    AND p_compare_start = (
      SELECT MIN(next_cal.cal_date)
      FROM `data-aquarium.ashare_dim.dim_trade_calendar` AS next_cal
      WHERE next_cal.exchange = 'SSE'
        AND next_cal.is_open = 1
        AND next_cal.cal_date > p_state_as_of_date
    )
) AS 'QA-RESUME-CONSIST-0: compare_start must equal the next SSE open day after state_as_of_date';

ASSERT (
  SELECT COUNT(*) = 1
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_full_backtest_id
    AND JSON_VALUE(bs.metrics_json, '$.ledger_version') = p_ledger_version
    AND SAFE_CAST(JSON_VALUE(bs.metrics_json, '$.rebalance_anchor_start') AS DATE) = p_rebalance_anchor_start
    AND COALESCE(JSON_VALUE(bs.metrics_json, '$.corporate_actions'), 'none_v1') = p_corporate_actions
    AND COALESCE(JSON_VALUE(bs.metrics_json, '$.dividend_tax_mode'), 'flat_10pct') = p_dividend_tax_mode
) AS 'QA-RESUME-CONSIST-1: full backtest summary must exist exactly once and use expected lot100 ledger/anchor/corporate action params';

ASSERT (
  SELECT COUNT(*) = 1
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_resume_backtest_id
    AND JSON_VALUE(bs.metrics_json, '$.ledger_version') = p_ledger_version
    AND JSON_VALUE(bs.metrics_json, '$.initial_state_mode') = 'resume_from_backtest'
    AND JSON_VALUE(bs.metrics_json, '$.is_resumed_backtest') = 'true'
    AND SAFE_CAST(JSON_VALUE(bs.metrics_json, '$.state_as_of_date') AS DATE) = p_state_as_of_date
    AND JSON_VALUE(bs.metrics_json, '$.resume_policy_id') = p_resume_policy_id
    AND SAFE_CAST(JSON_VALUE(bs.metrics_json, '$.rebalance_anchor_start') AS DATE) = p_rebalance_anchor_start
    AND COALESCE(JSON_VALUE(bs.metrics_json, '$.corporate_actions'), 'none_v1') = p_corporate_actions
    AND COALESCE(JSON_VALUE(bs.metrics_json, '$.dividend_tax_mode'), 'flat_10pct') = p_dividend_tax_mode
) AS 'QA-RESUME-CONSIST-2: resume backtest summary must exist exactly once and be marked with resume/corporate action metadata';

ASSERT (
  SELECT COUNT(*) = 1
  FROM `data-aquarium.ashare_ads.ads_backtest_ledger_state_daily` AS state
  WHERE state.backtest_id = p_resume_backtest_id
    AND state.trade_date = p_compare_start
    AND state.ledger_version = p_ledger_version
    AND state.resume_policy_id = p_resume_policy_id
    AND state.rebalance_anchor_start = p_rebalance_anchor_start
) AS 'QA-RESUME-CONSIST-2B: resume first-day ledger state must record expected ledger metadata';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    WITH expected AS (
      SELECT cal.cal_date AS trade_date
      FROM `data-aquarium.ashare_dim.dim_trade_calendar` AS cal
      WHERE cal.exchange = 'SSE'
        AND cal.is_open = 1
        AND cal.cal_date BETWEEN p_compare_start AND p_compare_end
    ),
    nav_presence AS (
      SELECT
        e.trade_date,
        full_nav.trade_date IS NOT NULL AS has_full,
        resume_nav.trade_date IS NOT NULL AS has_resume
      FROM expected AS e
      LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS full_nav
        ON full_nav.backtest_id = p_full_backtest_id
       AND full_nav.trade_date = e.trade_date
       AND full_nav.trade_date BETWEEN p_compare_start AND p_compare_end
      LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS resume_nav
        ON resume_nav.backtest_id = p_resume_backtest_id
       AND resume_nav.trade_date = e.trade_date
       AND resume_nav.trade_date BETWEEN p_compare_start AND p_compare_end
    )
    SELECT trade_date
    FROM nav_presence
    WHERE NOT has_full OR NOT has_resume
  )
) AS 'QA-RESUME-CONSIST-3: both backtests must have NAV rows for every open day in compare window';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    WITH full_nav AS (
      SELECT *
      FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily`
      WHERE backtest_id = p_full_backtest_id
        AND trade_date BETWEEN p_compare_start AND p_compare_end
    ),
    resume_nav AS (
      SELECT *
      FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily`
      WHERE backtest_id = p_resume_backtest_id
        AND trade_date BETWEEN p_compare_start AND p_compare_end
    )
    SELECT
      COALESCE(f.trade_date, r.trade_date) AS trade_date,
      ABS(COALESCE(f.cash_cny, 0) - COALESCE(r.cash_cny, 0)) AS cash_diff,
      ABS(COALESCE(f.net_value_cny, 0) - COALESCE(r.net_value_cny, 0)) AS value_diff,
      ABS(COALESCE(f.nav, 0) - COALESCE(r.nav, 0)) AS nav_diff,
      (f.daily_return IS NULL) != (r.daily_return IS NULL) AS daily_return_null_mismatch,
      ABS(COALESCE(f.daily_return, 0) - COALESCE(r.daily_return, 0)) AS daily_return_diff,
      ABS(COALESCE(f.gross_exposure, 0) - COALESCE(r.gross_exposure, 0)) AS exposure_diff,
      ABS(COALESCE(f.turnover_cny, 0) - COALESCE(r.turnover_cny, 0)) AS turnover_diff,
      ABS(COALESCE(f.cost_cny, 0) - COALESCE(r.cost_cny, 0)) AS cost_diff
    FROM full_nav AS f
    FULL OUTER JOIN resume_nav AS r
      USING (trade_date)
  )
  WHERE cash_diff > p_cash_tolerance_cny
     OR value_diff > p_value_tolerance_cny
     OR nav_diff > 1e-6
     OR daily_return_null_mismatch
     OR daily_return_diff > 1e-9
     OR exposure_diff > 1e-6
     OR turnover_diff > p_value_tolerance_cny
     OR cost_diff > p_value_tolerance_cny
) AS 'QA-RESUME-CONSIST-4: full and resume NAV/cash/value/daily_return/turnover/cost must match in compare window';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    WITH full_pos AS (
      SELECT *
      FROM `data-aquarium.ashare_ads.ads_backtest_position_daily`
      WHERE backtest_id = p_full_backtest_id
        AND trade_date BETWEEN p_compare_start AND p_compare_end
    ),
    resume_pos AS (
      SELECT *
      FROM `data-aquarium.ashare_ads.ads_backtest_position_daily`
      WHERE backtest_id = p_resume_backtest_id
        AND trade_date BETWEEN p_compare_start AND p_compare_end
    )
    SELECT
      COALESCE(f.trade_date, r.trade_date) AS trade_date,
      COALESCE(f.sec_code, r.sec_code) AS sec_code,
      ABS(COALESCE(f.shares, 0) - COALESCE(r.shares, 0)) AS share_diff,
      ABS(COALESCE(f.market_value_cny, 0) - COALESCE(r.market_value_cny, 0)) AS value_diff,
      ABS(COALESCE(f.weight, 0) - COALESCE(r.weight, 0)) AS weight_diff
    FROM full_pos AS f
    FULL OUTER JOIN resume_pos AS r
      USING (trade_date, sec_code)
  )
  WHERE share_diff > p_share_tolerance
     OR value_diff > p_value_tolerance_cny
     OR weight_diff > 1e-6
) AS 'QA-RESUME-CONSIST-5: full and resume positions must match by trade_date/sec_code';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    WITH full_trades AS (
      SELECT
        trade_date, sec_code, side, fill_status,
        SUM(planned_shares) AS planned_shares,
        SUM(filled_shares) AS filled_shares,
        SUM(turnover_cny) AS turnover_cny,
        SUM(fee_cny) AS fee_cny,
        SUM(tax_cny) AS tax_cny,
        SUM(slippage_cny) AS slippage_cny,
        SUM(cash_effect_cny) AS cash_effect_cny
      FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily`
      WHERE backtest_id = p_full_backtest_id
        AND trade_date BETWEEN p_compare_start AND p_compare_end
      GROUP BY trade_date, sec_code, side, fill_status
    ),
    resume_trades AS (
      SELECT
        trade_date, sec_code, side, fill_status,
        SUM(planned_shares) AS planned_shares,
        SUM(filled_shares) AS filled_shares,
        SUM(turnover_cny) AS turnover_cny,
        SUM(fee_cny) AS fee_cny,
        SUM(tax_cny) AS tax_cny,
        SUM(slippage_cny) AS slippage_cny,
        SUM(cash_effect_cny) AS cash_effect_cny
      FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily`
      WHERE backtest_id = p_resume_backtest_id
        AND trade_date BETWEEN p_compare_start AND p_compare_end
      GROUP BY trade_date, sec_code, side, fill_status
    )
    SELECT
      COALESCE(f.trade_date, r.trade_date) AS trade_date,
      COALESCE(f.sec_code, r.sec_code) AS sec_code,
      COALESCE(f.side, r.side) AS side,
      COALESCE(f.fill_status, r.fill_status) AS fill_status,
      ABS(COALESCE(f.planned_shares, 0) - COALESCE(r.planned_shares, 0)) AS planned_diff,
      ABS(COALESCE(f.filled_shares, 0) - COALESCE(r.filled_shares, 0)) AS filled_diff,
      ABS(COALESCE(f.turnover_cny, 0) - COALESCE(r.turnover_cny, 0)) AS turnover_diff,
      ABS(COALESCE(f.fee_cny, 0) - COALESCE(r.fee_cny, 0)) AS fee_diff,
      ABS(COALESCE(f.tax_cny, 0) - COALESCE(r.tax_cny, 0)) AS tax_diff,
      ABS(COALESCE(f.slippage_cny, 0) - COALESCE(r.slippage_cny, 0)) AS slippage_diff,
      ABS(COALESCE(f.cash_effect_cny, 0) - COALESCE(r.cash_effect_cny, 0)) AS cash_effect_diff
    FROM full_trades AS f
    FULL OUTER JOIN resume_trades AS r
      USING (trade_date, sec_code, side, fill_status)
  )
  WHERE planned_diff > p_share_tolerance
     OR filled_diff > p_share_tolerance
     OR turnover_diff > p_value_tolerance_cny
     OR fee_diff > p_value_tolerance_cny
     OR tax_diff > p_value_tolerance_cny
     OR slippage_diff > p_value_tolerance_cny
     OR cash_effect_diff > p_value_tolerance_cny
) AS 'QA-RESUME-CONSIST-6: full and resume trade facts must match by date/security/side/status';
