-- BigQuery Standard SQL
-- Strategy1 synthetic continuous prediction merge and continuous ledger QA.

DECLARE p_run_id STRING DEFAULT 's1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02';
DECLARE p_prediction_run_id STRING DEFAULT NULL;
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02';
DECLARE p_synthetic_model_id STRING DEFAULT NULL;
DECLARE p_predict_start DATE DEFAULT DATE '2021-01-04';
DECLARE p_predict_end DATE DEFAULT DATE '2026-06-09';
DECLARE p_expected_year_count INT64 DEFAULT 6;
DECLARE p_manifest_sha256 STRING DEFAULT NULL;
DECLARE p_require_source_refit BOOL DEFAULT TRUE;
DECLARE p_expected_ledger_version STRING DEFAULT 'ledger_exec_v1_lot100';
DECLARE p_resume_policy_id STRING DEFAULT 'cloudrun_lot100_resume_v1';

SET p_prediction_run_id = COALESCE(p_prediction_run_id, p_run_id);

CREATE TEMP TABLE synthetic_registry AS
SELECT
  reg.*,
  JSON_VALUE(reg.metrics_json, '$.input_manifest_sha256') AS input_manifest_sha256,
  JSON_VALUE(reg.metrics_json, '$.resolved_manifest_sha256') AS resolved_manifest_sha256,
  JSON_VALUE(reg.metrics_json, '$.manifest_uri') AS manifest_uri,
  JSON_VALUE(reg.metrics_json, '$.source_all_refit') = 'true' AS source_all_refit
FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
WHERE reg.strategy_id = p_strategy_id
  AND reg.status = 'selected'
  AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_prediction_run_id;

ASSERT (
  SELECT COUNT(*) = 1
    AND LOGICAL_AND(JSON_VALUE(model_params_json, '$.synthetic_continuous') = 'true')
    AND LOGICAL_AND(COALESCE(p_synthetic_model_id, model_id) = model_id)
    AND LOGICAL_AND(input_manifest_sha256 IS NOT NULL)
    AND LOGICAL_AND(resolved_manifest_sha256 IS NOT NULL)
    AND LOGICAL_AND(manifest_uri IS NOT NULL)
    AND LOGICAL_AND(p_manifest_sha256 IS NULL OR input_manifest_sha256 = p_manifest_sha256)
    AND LOGICAL_AND(NOT p_require_source_refit OR source_all_refit)
  FROM synthetic_registry
) AS 'QA-CONT-1: synthetic run must have exactly one selected registry row with manifest lineage';

CREATE TEMP TABLE manifest AS
SELECT
  SAFE_CAST(JSON_VALUE(item, '$.backtest_year') AS INT64) AS backtest_year,
  JSON_VALUE(item, '$.source_run_id') AS source_run_id,
  JSON_VALUE(item, '$.source_model_id') AS source_model_id,
  JSON_VALUE(item, '$.source_refit') = 'true' AS source_refit,
  DATE(JSON_VALUE(item, '$.predict_start')) AS predict_start,
  DATE(JSON_VALUE(item, '$.predict_end')) AS predict_end,
  DATE(JSON_VALUE(item, '$.valid_start')) AS valid_start,
  DATE(JSON_VALUE(item, '$.valid_end')) AS valid_end
FROM synthetic_registry AS reg,
UNNEST(JSON_QUERY_ARRAY(reg.metrics_json, '$.year_slices')) AS item;

ASSERT (
  SELECT COUNT(*) = p_expected_year_count
    AND COUNT(DISTINCT backtest_year) = p_expected_year_count
    AND COUNTIF(source_run_id IS NULL OR source_model_id IS NULL OR predict_start IS NULL OR predict_end IS NULL) = 0
    AND MIN(predict_start) = p_predict_start
    AND MAX(predict_end) = p_predict_end
    AND LOGICAL_AND(NOT p_require_source_refit OR source_refit)
  FROM manifest
) AS 'QA-CONT-2: synthetic manifest year slices must cover expected official window and source lineage';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT predict_date, sec_code, COUNT(*) AS n
    FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
    WHERE pred.run_id = p_prediction_run_id
      AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
    GROUP BY predict_date, sec_code
    HAVING n > 1
  )
) AS 'QA-CONT-3: synthetic predictions must be unique per predict_date/sec_code';

ASSERT (
  WITH source_counts AS (
    SELECT
      m.backtest_year,
      COUNT(*) AS source_rows,
      MIN(pred.predict_date) AS source_min_date,
      MAX(pred.predict_date) AS source_max_date
    FROM manifest AS m
    JOIN `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
      ON pred.run_id = m.source_run_id
     AND pred.model_id = m.source_model_id
     AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
     AND pred.predict_date BETWEEN m.predict_start AND m.predict_end
    GROUP BY m.backtest_year
  ),
  target_counts AS (
    SELECT COUNT(*) AS target_rows
    FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
    WHERE pred.run_id = p_prediction_run_id
      AND pred.model_id = (SELECT model_id FROM synthetic_registry LIMIT 1)
      AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
  )
  SELECT
    COUNT(*) = p_expected_year_count
    AND SUM(source_rows) = (SELECT target_rows FROM target_counts)
    AND MIN(source_min_date) = p_predict_start
    AND MAX(source_max_date) = p_predict_end
    AND MIN(source_rows) > 0
  FROM source_counts
) AS 'QA-CONT-4: synthetic prediction row count must equal the sum of source annual slices';

ASSERT (
  WITH calendar AS (
    SELECT cal_date
    FROM `data-aquarium.ashare_dim.dim_trade_calendar`
    WHERE exchange = 'SSE'
      AND is_open = 1
      AND cal_date BETWEEN p_predict_start AND p_predict_end
  ),
  target_daily AS (
    SELECT pred.predict_date, COUNT(*) AS rows_per_day
    FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
    WHERE pred.run_id = p_prediction_run_id
      AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
    GROUP BY pred.predict_date
  )
  SELECT COUNTIF(target_daily.rows_per_day IS NULL OR target_daily.rows_per_day = 0) = 0
  FROM calendar
  LEFT JOIN target_daily
    ON target_daily.predict_date = calendar.cal_date
) AS 'QA-CONT-5: synthetic prediction stream must cover every open trading day';

ASSERT (
  SELECT COUNT(*) = 0
  FROM manifest AS m
  JOIN `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
    ON pred.run_id = p_prediction_run_id
   AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
   AND pred.predict_date BETWEEN m.valid_start AND m.valid_end
  WHERE m.valid_start IS NOT NULL
    AND m.valid_end IS NOT NULL
) AS 'QA-CONT-6: synthetic prediction stream must exclude source validation windows';

ASSERT (
  SELECT COUNT(*) = 1
    AND LOGICAL_AND(run_id = p_run_id)
    AND LOGICAL_AND(start_date = p_predict_start)
    AND LOGICAL_AND(end_date = p_predict_end)
    AND LOGICAL_AND(model_id = (SELECT model_id FROM synthetic_registry LIMIT 1))
    AND LOGICAL_AND(JSON_VALUE(metrics_json, '$.prediction_run_id') = p_prediction_run_id)
    AND LOGICAL_AND(JSON_VALUE(metrics_json, '$.ledger_version') = p_expected_ledger_version)
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-CONT-7: continuous summary must identify the synthetic run and exact official window';

ASSERT (
  WITH calendar AS (
    SELECT cal_date
    FROM `data-aquarium.ashare_dim.dim_trade_calendar`
    WHERE exchange = 'SSE'
      AND is_open = 1
      AND cal_date BETWEEN p_predict_start AND p_predict_end
  ),
  nav AS (
    SELECT trade_date, COUNT(*) AS n
    FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily`
    WHERE backtest_id = p_backtest_id
      AND trade_date BETWEEN p_predict_start AND p_predict_end
    GROUP BY trade_date
  )
  SELECT
    COUNTIF(nav.n IS NULL) = 0
    AND COUNTIF(nav.n != 1) = 0
  FROM calendar
  LEFT JOIN nav
    ON nav.trade_date = calendar.cal_date
) AS 'QA-CONT-8: continuous NAV must have exactly one row for every open trading day';

ASSERT (
  SELECT COUNTIF(nav.cash_cny < -1.0) = 0
    AND COUNTIF(nav.gross_exposure > 1.005) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
  WHERE nav.backtest_id = p_backtest_id
    AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-CONT-9: continuous NAV cash and exposure must stay within long-only tolerances';

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
) AS 'QA-CONT-10: continuous positions must be unique per trade_date/sec_code';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS trade
  WHERE trade.backtest_id = p_backtest_id
    AND trade.trade_date BETWEEN p_predict_start AND p_predict_end
    AND trade.fill_status IN (
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
      ABS(COALESCE(trade.filled_shares, 0)) > 1e-9
      OR ABS(COALESCE(trade.turnover_cny, 0)) > 1e-6
      OR ABS(COALESCE(trade.fee_cny, 0)) > 1e-6
      OR ABS(COALESCE(trade.tax_cny, 0)) > 1e-6
      OR ABS(COALESCE(trade.slippage_cny, 0)) > 1e-6
      OR ABS(COALESCE(trade.cash_effect_cny, 0)) > 1e-6
    )
) AS 'QA-CONT-11: skipped/cancel/noop trade rows must have zero fill and cash impact';

ASSERT (
  SELECT COUNT(*) = (
    SELECT COUNT(*)
    FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
    WHERE nav.backtest_id = p_backtest_id
      AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
  )
    AND LOGICAL_AND(state.run_id = p_run_id)
    AND LOGICAL_AND(state.ledger_version = p_expected_ledger_version)
    AND LOGICAL_AND(state.resume_policy_id = p_resume_policy_id)
    AND LOGICAL_AND(state.ledger_params_hash IS NOT NULL)
    AND LOGICAL_AND(state.holdings_hash IS NOT NULL)
  FROM `data-aquarium.ashare_ads.ads_backtest_ledger_state_daily` AS state
  WHERE state.backtest_id = p_backtest_id
    AND state.trade_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-CONT-12: continuous ledger state must match NAV coverage and lot-aware metadata';
