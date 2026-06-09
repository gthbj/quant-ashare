-- QA-V3-25: Cloud Run lot100 ledger resume parity checks.
-- Compares a resumed child run against a full parent run over the child window.

DECLARE p_full_backtest_id STRING DEFAULT NULL;
DECLARE p_resume_backtest_id STRING DEFAULT NULL;
DECLARE p_compare_start DATE DEFAULT NULL;
DECLARE p_compare_end DATE DEFAULT NULL;
DECLARE p_state_as_of_date DATE DEFAULT NULL;
DECLARE p_resume_policy_id STRING DEFAULT 'cloudrun_lot100_resume_v1';
DECLARE p_ledger_version STRING DEFAULT 'ledger_exec_v1_lot100';

ASSERT p_full_backtest_id IS NOT NULL AS 'p_full_backtest_id is required';
ASSERT p_resume_backtest_id IS NOT NULL AS 'p_resume_backtest_id is required';
ASSERT p_compare_start IS NOT NULL AS 'p_compare_start is required';
ASSERT p_compare_end IS NOT NULL AS 'p_compare_end is required';
ASSERT p_state_as_of_date IS NOT NULL AS 'p_state_as_of_date is required';
ASSERT p_compare_start <= p_compare_end AS 'compare window must be valid';
ASSERT p_state_as_of_date < p_compare_start AS 'state_as_of_date must be before compare_start';

CREATE TEMP TABLE full_nav AS
SELECT trade_date, nav, net_value_cny, cash_cny, gross_exposure, turnover, daily_return, cost_cny
FROM `data-aquarium.ashare_dws.ads_backtest_nav_daily`
WHERE backtest_id = p_full_backtest_id
  AND trade_date BETWEEN p_compare_start AND p_compare_end;

CREATE TEMP TABLE resume_nav AS
SELECT trade_date, nav, net_value_cny, cash_cny, gross_exposure, turnover, daily_return, cost_cny
FROM `data-aquarium.ashare_dws.ads_backtest_nav_daily`
WHERE backtest_id = p_resume_backtest_id
  AND trade_date BETWEEN p_compare_start AND p_compare_end;

CREATE TEMP TABLE full_position AS
SELECT trade_date, sec_code, shares, market_value_cny
FROM `data-aquarium.ashare_dws.ads_backtest_position_daily`
WHERE backtest_id = p_full_backtest_id
  AND trade_date BETWEEN p_compare_start AND p_compare_end;

CREATE TEMP TABLE resume_position AS
SELECT trade_date, sec_code, shares, market_value_cny
FROM `data-aquarium.ashare_dws.ads_backtest_position_daily`
WHERE backtest_id = p_resume_backtest_id
  AND trade_date BETWEEN p_compare_start AND p_compare_end;

CREATE TEMP TABLE full_trade AS
SELECT trade_date, sec_code, side, shares, price, amount_cny, fee_cny, tax_cny, slippage_cny, order_reason
FROM `data-aquarium.ashare_dws.ads_backtest_trade_daily`
WHERE backtest_id = p_full_backtest_id
  AND trade_date BETWEEN p_compare_start AND p_compare_end;

CREATE TEMP TABLE resume_trade AS
SELECT trade_date, sec_code, side, shares, price, amount_cny, fee_cny, tax_cny, slippage_cny, order_reason
FROM `data-aquarium.ashare_dws.ads_backtest_trade_daily`
WHERE backtest_id = p_resume_backtest_id
  AND trade_date BETWEEN p_compare_start AND p_compare_end;

CREATE TEMP TABLE resume_state AS
SELECT *
FROM `data-aquarium.ashare_dws.ads_backtest_ledger_state_daily`
WHERE backtest_id = p_resume_backtest_id
  AND trade_date BETWEEN p_compare_start AND p_compare_end;

CREATE TEMP TABLE parent_state AS
SELECT *
FROM `data-aquarium.ashare_dws.ads_backtest_ledger_state_daily`
WHERE backtest_id = p_full_backtest_id
  AND trade_date = p_state_as_of_date;

CREATE TEMP TABLE resume_summary AS
SELECT metrics_json
FROM `data-aquarium.ashare_dws.ads_backtest_performance_summary`
WHERE backtest_id = p_resume_backtest_id;

ASSERT (SELECT COUNT(*) FROM parent_state) = 1 AS 'Parent state snapshot must exist exactly once';
ASSERT (SELECT COUNT(*) FROM resume_nav) > 0 AS 'Resume NAV coverage is empty';
ASSERT (SELECT COUNT(*) FROM full_nav) = (SELECT COUNT(*) FROM resume_nav)
  AS 'Full and resume NAV row counts differ';
ASSERT (SELECT COUNT(*) FROM resume_state) = (SELECT COUNT(*) FROM resume_nav)
  AS 'Resume state row count must equal resume NAV row count';
ASSERT (
  SELECT COUNT(*)
  FROM resume_state
  WHERE ledger_version != p_ledger_version
     OR resume_policy_id != p_resume_policy_id
     OR ledger_params_hash IS NULL
     OR holdings_hash IS NULL
) = 0 AS 'Resume state metadata mismatch';
ASSERT (
  SELECT COUNT(*)
  FROM resume_summary
  WHERE JSON_VALUE(metrics_json, '$.initial_state_mode') = 'resume_from_backtest'
    AND JSON_VALUE(metrics_json, '$.parent_backtest_id') = p_full_backtest_id
    AND SAFE_CAST(JSON_VALUE(metrics_json, '$.state_as_of_date') AS DATE) = p_state_as_of_date
    AND JSON_VALUE(metrics_json, '$.resume_policy_id') = p_resume_policy_id
) = 1 AS 'Resume summary metadata mismatch';

CREATE TEMP TABLE nav_diff AS
SELECT
  COALESCE(f.trade_date, r.trade_date) AS trade_date,
  ABS(COALESCE(f.nav, 0) - COALESCE(r.nav, 0)) AS nav_diff,
  ABS(COALESCE(f.net_value_cny, 0) - COALESCE(r.net_value_cny, 0)) AS net_value_diff,
  ABS(COALESCE(f.cash_cny, 0) - COALESCE(r.cash_cny, 0)) AS cash_diff,
  ABS(COALESCE(f.gross_exposure, 0) - COALESCE(r.gross_exposure, 0)) AS exposure_diff,
  ABS(COALESCE(f.turnover, 0) - COALESCE(r.turnover, 0)) AS turnover_diff,
  ABS(COALESCE(f.daily_return, 0) - COALESCE(r.daily_return, 0)) AS daily_return_diff,
  ABS(COALESCE(f.cost_cny, 0) - COALESCE(r.cost_cny, 0)) AS cost_diff
FROM full_nav f
FULL OUTER JOIN resume_nav r USING (trade_date);

ASSERT (
  SELECT COUNT(*)
  FROM nav_diff
  WHERE nav_diff > 1e-10
     OR net_value_diff > 1e-4
     OR cash_diff > 1e-4
     OR exposure_diff > 1e-10
     OR turnover_diff > 1e-10
     OR daily_return_diff > 1e-10
     OR cost_diff > 1e-4
) = 0 AS 'Full and resume NAV metrics differ';

CREATE TEMP TABLE position_diff AS
SELECT
  COALESCE(f.trade_date, r.trade_date) AS trade_date,
  COALESCE(f.sec_code, r.sec_code) AS sec_code,
  ABS(COALESCE(f.shares, 0) - COALESCE(r.shares, 0)) AS shares_diff,
  ABS(COALESCE(f.market_value_cny, 0) - COALESCE(r.market_value_cny, 0)) AS market_value_diff
FROM full_position f
FULL OUTER JOIN resume_position r USING (trade_date, sec_code);

ASSERT (
  SELECT COUNT(*)
  FROM position_diff
  WHERE shares_diff != 0 OR market_value_diff > 1e-4
) = 0 AS 'Full and resume positions differ';

CREATE TEMP TABLE trade_diff AS
SELECT
  COALESCE(f.trade_date, r.trade_date) AS trade_date,
  COALESCE(f.sec_code, r.sec_code) AS sec_code,
  COALESCE(f.side, r.side) AS side,
  COALESCE(f.order_reason, r.order_reason) AS order_reason,
  ABS(COALESCE(f.shares, 0) - COALESCE(r.shares, 0)) AS shares_diff,
  ABS(COALESCE(f.price, 0) - COALESCE(r.price, 0)) AS price_diff,
  ABS(COALESCE(f.amount_cny, 0) - COALESCE(r.amount_cny, 0)) AS amount_diff,
  ABS(COALESCE(f.fee_cny, 0) - COALESCE(r.fee_cny, 0)) AS fee_diff,
  ABS(COALESCE(f.tax_cny, 0) - COALESCE(r.tax_cny, 0)) AS tax_diff,
  ABS(COALESCE(f.slippage_cny, 0) - COALESCE(r.slippage_cny, 0)) AS slippage_diff
FROM full_trade f
FULL OUTER JOIN resume_trade r USING (trade_date, sec_code, side, order_reason);

ASSERT (
  SELECT COUNT(*)
  FROM trade_diff
  WHERE shares_diff != 0
     OR price_diff > 1e-10
     OR amount_diff > 1e-4
     OR fee_diff > 1e-4
     OR tax_diff > 1e-4
     OR slippage_diff > 1e-4
) = 0 AS 'Full and resume trades differ';
