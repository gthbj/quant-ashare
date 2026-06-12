-- BigQuery Standard SQL · Strategy 1 corporate action ledger QA
-- Validates Phase B ledger outputs against the Phase A ledger-consumable event view.

DECLARE p_backtest_id STRING DEFAULT 'bt_s1_ca_ledger_unit';
DECLARE p_run_id STRING DEFAULT 's1_ca_ledger_unit';
DECLARE p_predict_start DATE DEFAULT DATE '2021-01-04';
DECLARE p_predict_end DATE DEFAULT DATE '2026-06-09';
DECLARE p_corporate_actions STRING DEFAULT 'none_v1';
DECLARE p_dividend_tax_mode STRING DEFAULT 'flat_10pct';
DECLARE p_share_tolerance FLOAT64 DEFAULT 1e-6;
DECLARE p_cash_tolerance_cny FLOAT64 DEFAULT 1.0;
DECLARE p_nav_event_abs_return_ceiling FLOAT64 DEFAULT 0.25;

IF p_corporate_actions NOT IN ('none_v1', 'cash_div_and_split_v1') THEN
  RAISE USING MESSAGE = CONCAT('unsupported p_corporate_actions: ', p_corporate_actions);
END IF;

IF p_dividend_tax_mode NOT IN ('flat_10pct') THEN
  RAISE USING MESSAGE = CONCAT('unsupported p_dividend_tax_mode: ', p_dividend_tax_mode);
END IF;

ASSERT (
  SELECT COUNT(*) = 1
    AND LOGICAL_AND(COALESCE(JSON_VALUE(bs.metrics_json, '$.corporate_actions'), 'none_v1') = p_corporate_actions)
    AND LOGICAL_AND(COALESCE(JSON_VALUE(bs.metrics_json, '$.dividend_tax_mode'), 'flat_10pct') = p_dividend_tax_mode)
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-CA-LEDGER-1: summary must record expected corporate_actions and dividend_tax_mode';

CREATE TEMP TABLE ca_events AS
SELECT
  sec_code,
  ex_date,
  record_date,
  cash_div_per_share_pretax,
  split_ratio,
  source_event_count
FROM `data-aquarium.ashare_dwd.v_dwd_stock_dividend_event_ledger_consumable`
WHERE ex_date BETWEEN p_predict_start AND p_predict_end
  AND (cash_div_per_share_pretax > 0 OR split_ratio > 0);

CREATE TEMP TABLE record_entitlements AS
SELECT
  e.sec_code,
  e.ex_date,
  e.record_date,
  e.cash_div_per_share_pretax,
  e.split_ratio,
  COALESCE(pos.shares, 0.0) AS record_shares
FROM ca_events AS e
LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
  ON pos.backtest_id = p_backtest_id
 AND pos.sec_code = e.sec_code
 AND pos.trade_date = e.record_date
 AND pos.trade_date BETWEEN p_predict_start AND p_predict_end;

CREATE TEMP TABLE ca_audit AS
SELECT
  trade_date,
  sec_code,
  fill_status,
  planned_shares,
  filled_shares,
  fill_price,
  turnover_cny,
  tax_cny,
  cash_effect_cny
FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily`
WHERE backtest_id = p_backtest_id
  AND trade_date BETWEEN p_predict_start AND p_predict_end
  AND fill_status IN ('CORPORATE_ACTION_SPLIT', 'CORPORATE_ACTION_CASH_DIVIDEND');

IF p_corporate_actions = 'none_v1' THEN
  ASSERT (
    SELECT COUNT(*) = 0
    FROM ca_audit
  ) AS 'QA-CA-LEDGER-5: corporate_actions=none_v1 must emit zero corporate action audit rows';
END IF;

IF p_corporate_actions = 'cash_div_and_split_v1' THEN
  ASSERT (
    SELECT COUNT(*) = 0
    FROM (
      SELECT
        re.sec_code,
        re.ex_date,
        re.record_shares,
        re.split_ratio,
        re.record_shares * (1.0 + re.split_ratio) AS expected_theoretical_post_shares,
        FLOOR(re.record_shares * (1.0 + re.split_ratio)) - re.record_shares AS expected_share_delta,
        audit.planned_shares,
        audit.filled_shares
      FROM record_entitlements AS re
      LEFT JOIN ca_audit AS audit
        ON audit.sec_code = re.sec_code
       AND audit.trade_date = re.ex_date
       AND audit.fill_status = 'CORPORATE_ACTION_SPLIT'
      WHERE re.split_ratio > 0
        AND re.record_shares > 0.000001
        AND (
          audit.sec_code IS NULL
          OR ABS(audit.planned_shares - re.record_shares * (1.0 + re.split_ratio)) > p_share_tolerance
          OR ABS(audit.filled_shares - (FLOOR(re.record_shares * (1.0 + re.split_ratio)) - re.record_shares)) > p_share_tolerance
        )
    )
  ) AS 'QA-CA-LEDGER-2: split audit rows must match record-date shares and split_ratio';

  ASSERT (
    SELECT COUNT(*) = 0
    FROM (
      SELECT
        re.sec_code,
        re.ex_date,
        re.record_shares,
        re.cash_div_per_share_pretax,
        re.record_shares * re.cash_div_per_share_pretax AS expected_pretax_cash,
        re.record_shares * re.cash_div_per_share_pretax * 0.10 AS expected_tax,
        re.record_shares * re.cash_div_per_share_pretax * 0.90 AS expected_cash_effect,
        audit.turnover_cny,
        audit.tax_cny,
        audit.cash_effect_cny
      FROM record_entitlements AS re
      LEFT JOIN ca_audit AS audit
        ON audit.sec_code = re.sec_code
       AND audit.trade_date = re.ex_date
       AND audit.fill_status = 'CORPORATE_ACTION_CASH_DIVIDEND'
      WHERE re.cash_div_per_share_pretax > 0
        AND re.record_shares > 0.000001
        AND (
          audit.sec_code IS NULL
          OR ABS(audit.turnover_cny - re.record_shares * re.cash_div_per_share_pretax) > p_cash_tolerance_cny
          OR ABS(audit.tax_cny - re.record_shares * re.cash_div_per_share_pretax * 0.10) > p_cash_tolerance_cny
          OR ABS(audit.cash_effect_cny - re.record_shares * re.cash_div_per_share_pretax * 0.90) > p_cash_tolerance_cny
        )
    )
  ) AS 'QA-CA-LEDGER-3: cash dividend audit rows must match record-date shares and flat 10pct tax';

  ASSERT (
    SELECT COUNT(*) = 0
    FROM (
      SELECT
        nav.trade_date,
        nav.daily_return
      FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
      JOIN (SELECT DISTINCT ex_date FROM record_entitlements WHERE record_shares > 0.000001) AS event_days
        ON event_days.ex_date = nav.trade_date
      WHERE nav.backtest_id = p_backtest_id
        AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
        AND (nav.daily_return IS NULL OR ABS(nav.daily_return) > p_nav_event_abs_return_ceiling)
    )
  ) AS 'QA-CA-LEDGER-4: corporate action event days must not have abnormal NAV jumps';
END IF;
