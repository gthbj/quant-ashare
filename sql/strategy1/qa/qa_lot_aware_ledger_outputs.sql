-- BigQuery Standard SQL · Strategy 1 lot-aware ledger QA
-- 23: Cloud Run Python `ledger_exec_v1_lot100` ADS output contract.

DECLARE p_backtest_id STRING DEFAULT 'bt_s1_lotaware_ref_pvfq_n30_bw_h5_20260606_01';
DECLARE p_run_id STRING DEFAULT 's1_lotaware_ref_pvfq_n30_bw_h5_20260606_01';
DECLARE p_predict_start DATE DEFAULT DATE '2024-01-02';
DECLARE p_predict_end DATE DEFAULT DATE '2026-04-30';
DECLARE p_ledger_version STRING DEFAULT 'ledger_exec_v1_lot100';
DECLARE p_lot_size INT64 DEFAULT 100;
DECLARE p_min_buy_lot INT64 DEFAULT 1;
DECLARE p_min_buy_shares INT64 DEFAULT 100;
DECLARE p_resume_policy_id STRING DEFAULT 'cloudrun_lot100_resume_v1';

SET p_min_buy_shares = p_lot_size * p_min_buy_lot;

ASSERT (
  SELECT COUNT(*) = 1
    AND LOGICAL_AND(IFNULL(JSON_VALUE(bs.metrics_json, '$.ledger_version') = p_ledger_version, FALSE))
    AND LOGICAL_AND(IFNULL(SAFE_CAST(JSON_VALUE(bs.metrics_json, '$.lot_size') AS INT64) = p_lot_size, FALSE))
    AND LOGICAL_AND(IFNULL(SAFE_CAST(JSON_VALUE(bs.metrics_json, '$.min_buy_lot') AS INT64) = p_min_buy_lot, FALSE))
    AND LOGICAL_AND(IFNULL(JSON_VALUE(bs.metrics_json, '$.buy_rounding') = 'floor_to_lot', FALSE))
    AND LOGICAL_AND(IFNULL(JSON_VALUE(bs.metrics_json, '$.sell_odd_lot_policy') = 'allow_full_exit_odd_lot', FALSE))
    AND LOGICAL_AND(IFNULL(JSON_VALUE(bs.metrics_json, '$.partial_sell_rounding') = 'floor_to_lot_keep_residual', FALSE))
    AND LOGICAL_AND(IFNULL(JSON_VALUE(bs.metrics_json, '$.cash_redistribution') = 'none_v1', FALSE))
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-LOT-1: summary must record lot-aware ledger version and parameters';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
  WHERE bt.backtest_id = p_backtest_id
    AND bt.run_id != p_run_id
    AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-LOT-2: trade rows must not mix run_id across backtest_id';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
  WHERE bt.backtest_id = p_backtest_id
    AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
    AND bt.fill_status NOT IN (
      'FILLED',
      'FILLED_SCALED_CASH',
      'BUY_SKIPPED_UNTRADABLE',
      'BUY_SKIPPED_TAIL_RISK',
      'BUY_SKIPPED_MARKET_RISK_OFF',
      'BUY_SKIPPED_BELOW_LOT',
      'BUY_SKIPPED_BELOW_LOT_AFTER_SCALE',
      'BUY_SKIPPED_CASH_INSUFFICIENT_AFTER_ROUNDING',
      'SELL_SKIPPED_UNTRADABLE',
      'SELL_SKIPPED_BELOW_LOT_PARTIAL',
      'PENDING_SELL_CARRY',
      'CANCELLED_BY_NETTING',
      'NOOP_ALREADY_TARGET'
    )
) AS 'QA-LOT-3: fill_status must be in lot-aware allowed set';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
  WHERE bt.backtest_id = p_backtest_id
    AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
    AND bt.side = 'BUY'
    AND bt.fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
    AND (
      ABS(bt.filled_shares - ROUND(bt.filled_shares)) > 1e-6
      OR CAST(ROUND(bt.filled_shares) AS INT64) < p_min_buy_shares
      OR MOD(CAST(ROUND(bt.filled_shares) AS INT64), p_lot_size) != 0
    )
) AS 'QA-LOT-4: all filled BUY shares must be integer lot multiples and at least one lot';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
  WHERE bt.backtest_id = p_backtest_id
    AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
    AND bt.fill_status IN (
      'BUY_SKIPPED_UNTRADABLE',
      'BUY_SKIPPED_TAIL_RISK',
      'BUY_SKIPPED_MARKET_RISK_OFF',
      'BUY_SKIPPED_BELOW_LOT',
      'BUY_SKIPPED_BELOW_LOT_AFTER_SCALE',
      'BUY_SKIPPED_CASH_INSUFFICIENT_AFTER_ROUNDING',
      'SELL_SKIPPED_UNTRADABLE',
      'SELL_SKIPPED_BELOW_LOT_PARTIAL',
      'PENDING_SELL_CARRY',
      'CANCELLED_BY_NETTING',
      'NOOP_ALREADY_TARGET'
    )
    AND (
      ABS(COALESCE(bt.filled_shares, 0)) > 1e-9
      OR ABS(COALESCE(bt.turnover_cny, 0)) > 1e-6
      OR ABS(COALESCE(bt.fee_cny, 0)) > 1e-6
      OR ABS(COALESCE(bt.tax_cny, 0)) > 1e-6
      OR ABS(COALESCE(bt.slippage_cny, 0)) > 1e-6
      OR ABS(COALESCE(bt.cash_effect_cny, 0)) > 1e-6
    )
) AS 'QA-LOT-5: skipped/cancel/noop statuses must have zero fill and cash impact';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
  LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
    ON pos.backtest_id = bt.backtest_id
   AND pos.trade_date = bt.trade_date
   AND pos.sec_code = bt.sec_code
   AND pos.trade_date BETWEEN p_predict_start AND p_predict_end
  WHERE bt.backtest_id = p_backtest_id
    AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
    AND bt.side = 'SELL'
    AND bt.fill_status = 'FILLED'
    AND MOD(CAST(ROUND(bt.filled_shares) AS INT64), p_lot_size) != 0
    AND COALESCE(pos.shares, 0) > 1e-6
) AS 'QA-LOT-6: odd-lot SELL fills are allowed only for full exit';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
  LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
    ON pos.backtest_id = bt.backtest_id
   AND pos.trade_date = bt.trade_date
   AND pos.sec_code = bt.sec_code
   AND pos.trade_date BETWEEN p_predict_start AND p_predict_end
  WHERE bt.backtest_id = p_backtest_id
    AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
    AND bt.fill_status = 'SELL_SKIPPED_BELOW_LOT_PARTIAL'
    AND COALESCE(pos.shares, 0) <= 1e-6
) AS 'QA-LOT-7: partial sell below one lot must retain a position';

ASSERT (
  SELECT COUNTIF(nav.cash_cny < -1.0) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
  WHERE nav.backtest_id = p_backtest_id
    AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-LOT-8: cash_cny must not go negative';

ASSERT (
  SELECT COUNTIF(nav.gross_exposure > 1.005) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
  WHERE nav.backtest_id = p_backtest_id
    AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-LOT-9: gross_exposure must not exceed long-only tolerance';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT pos.trade_date, pos.sec_code, COUNT(*) AS n
    FROM `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
    WHERE pos.backtest_id = p_backtest_id
      AND pos.trade_date BETWEEN p_predict_start AND p_predict_end
    GROUP BY pos.trade_date, pos.sec_code
    HAVING n > 1
  )
) AS 'QA-LOT-10: position rows must be unique per trade_date/sec_code';


ASSERT (
  SELECT COUNT(*)
  FROM `data-aquarium.ashare_ads.ads_backtest_ledger_state_daily` AS state
  WHERE state.backtest_id = p_backtest_id
    AND state.trade_date BETWEEN p_predict_start AND p_predict_end
) = (
  SELECT COUNT(*)
  FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
  WHERE nav.backtest_id = p_backtest_id
    AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-LOT-11: ledger state rows must match nav coverage';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_ledger_state_daily` AS state
  WHERE state.backtest_id = p_backtest_id
    AND state.trade_date BETWEEN p_predict_start AND p_predict_end
    AND (
      state.ledger_version != p_ledger_version
      OR state.resume_policy_id != p_resume_policy_id
      OR state.ledger_params_hash IS NULL
      OR state.holdings_hash IS NULL
    )
) AS 'QA-LOT-12: ledger state metadata must match lot-aware contract';
