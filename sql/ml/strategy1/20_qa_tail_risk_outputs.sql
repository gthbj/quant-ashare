-- BigQuery Standard SQL · Strategy 1 Tail Risk Diagnosis QA
-- 20: P0 read-only tail-risk diagnostics sanity checks.
--
-- This SQL intentionally does not read local/GCS files. Artifact existence and
-- identity are enforced by scripts/strategy1/analyze_tail_risk.py via its
-- artifact_manifest.json and tail_risk_summary.json. This query recomputes the
-- ADS-derived invariants and, when expected hashes are supplied, verifies ADS
-- did not change after the tail-risk script completed.

DECLARE p_run_id STRING DEFAULT 's1_cloudrun_python_example';
DECLARE p_prediction_run_id STRING DEFAULT NULL;
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_cloudrun_python_example';
DECLARE p_predict_start DATE DEFAULT DATE '2024-01-02';
DECLARE p_predict_end DATE DEFAULT DATE '2026-04-30';
DECLARE p_tail_risk_profile_id STRING DEFAULT 'diagnostic_only';
DECLARE p_market_state_version STRING DEFAULT 'market_state_v0_20260606';
DECLARE p_expected_summary_hash STRING DEFAULT NULL;
DECLARE p_expected_nav_hash STRING DEFAULT NULL;

SET p_prediction_run_id = COALESCE(p_prediction_run_id, p_run_id);

IF p_tail_risk_profile_id NOT IN (
  'diagnostic_only',
  'individual_risk_guard_v0',
  'market_risk_off_v0',
  'individual_and_market_risk_guard_v0'
) THEN
  RAISE USING MESSAGE = CONCAT('unsupported p_tail_risk_profile_id: ', p_tail_risk_profile_id);
END IF;

CREATE TEMP TABLE summary_row AS
SELECT bs.*
FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
WHERE bs.backtest_id = p_backtest_id;

ASSERT (
  SELECT COUNT(*) = 1
  FROM summary_row
) AS 'QA-TAIL-1: exactly one backtest summary row must exist';

ASSERT (
  SELECT start_date >= p_predict_start AND end_date <= p_predict_end
  FROM summary_row
) AS 'QA-TAIL-1b: p_predict_start/end must cover the summary window for partition pruning';

CREATE TEMP TABLE nav_data AS
SELECT
  nav.trade_date,
  nav.nav,
  nav.daily_return,
  nav.benchmark_return,
  nav.excess_return,
  nav.cash_cny,
  nav.gross_exposure
FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
WHERE nav.backtest_id = p_backtest_id
  AND nav.trade_date BETWEEN p_predict_start AND p_predict_end;

ASSERT (
  SELECT COUNT(*) > 0
  FROM nav_data
) AS 'QA-TAIL-2: NAV rows must exist for the summary window';

CREATE TEMP TABLE nav_dd AS
SELECT
  nav_data.*,
  MAX(nav) OVER(ORDER BY trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS run_max,
  SAFE_DIVIDE(nav, NULLIF(MAX(nav) OVER(ORDER BY trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 0.0)) - 1.0
    AS drawdown_pct
FROM nav_data;

ASSERT (
  SELECT ABS(MIN(drawdown_pct) - (SELECT max_drawdown FROM summary_row)) <= 1e-6
  FROM nav_dd
) AS 'QA-TAIL-3: recomputed max drawdown must match summary.max_drawdown';

CREATE TEMP TABLE max_dd_event AS
WITH trough AS (
  SELECT
    trade_date AS trough_date,
    nav AS trough_nav,
    run_max AS peak_nav,
    drawdown_pct
  FROM nav_dd
  ORDER BY drawdown_pct ASC, trade_date ASC
  LIMIT 1
)
SELECT
  (
    SELECT MIN(n.trade_date)
    FROM nav_dd AS n
    WHERE n.trade_date <= t.trough_date
      AND ABS(n.nav - t.peak_nav) <= 1e-10
  ) AS peak_date,
  t.trough_date,
  t.peak_nav,
  t.trough_nav,
  t.drawdown_pct
FROM trough AS t;

ASSERT (
  SELECT
    peak_date IS NOT NULL
    AND trough_date IS NOT NULL
    AND peak_date <= trough_date
    AND peak_date BETWEEN (SELECT MIN(trade_date) FROM nav_data) AND (SELECT MAX(trade_date) FROM nav_data)
    AND trough_date BETWEEN (SELECT MIN(trade_date) FROM nav_data) AND (SELECT MAX(trade_date) FROM nav_data)
  FROM max_dd_event
) AS 'QA-TAIL-4: max drawdown window dates must be inside NAV range';

ASSERT (
  SELECT COUNT(*) = 0
  FROM nav_data AS nav
  CROSS JOIN max_dd_event AS ev
  WHERE nav.trade_date BETWEEN ev.peak_date AND ev.trough_date
    AND COALESCE(nav.gross_exposure, 0.0) > 0.0001
    AND NOT EXISTS (
      SELECT 1
      FROM `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
      WHERE pos.backtest_id = p_backtest_id
        AND pos.trade_date = nav.trade_date
        AND pos.trade_date BETWEEN p_predict_start AND p_predict_end
    )
) AS 'QA-TAIL-5: position rows must cover drawdown dates with non-zero exposure';

CREATE TEMP TABLE limit_exposure AS
SELECT
  pos.trade_date,
  SUM(IF(
    COALESCE(px.is_limit_down, FALSE)
      OR (px.is_limit_down IS NULL AND px.ret_1d <= -0.095),
    COALESCE(pos.weight, 0.0),
    0.0
  )) AS limit_down_weight_eod,
  SUM(IF(COALESCE(px.is_one_word_limit_down, FALSE), COALESCE(pos.weight, 0.0), 0.0)) AS one_word_limit_down_weight_eod,
  SUM(IF(NOT COALESCE(px.can_sell_open, TRUE), COALESCE(pos.weight, 0.0), 0.0)) AS cannot_sell_open_weight_eod
FROM `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
CROSS JOIN max_dd_event AS ev
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
  ON px.sec_code = pos.sec_code
 AND px.trade_date = pos.trade_date
 AND px.trade_date BETWEEN p_predict_start AND p_predict_end
WHERE pos.backtest_id = p_backtest_id
  AND pos.trade_date BETWEEN p_predict_start AND p_predict_end
  AND pos.trade_date BETWEEN ev.peak_date AND ev.trough_date
GROUP BY pos.trade_date;

ASSERT (
  SELECT
    COALESCE(MAX(limit_down_weight_eod), 0.0) BETWEEN 0.0 AND 1.01
    AND COALESCE(MAX(one_word_limit_down_weight_eod), 0.0) BETWEEN 0.0 AND 1.01
    AND COALESCE(MAX(cannot_sell_open_weight_eod), 0.0) BETWEEN 0.0 AND 1.01
  FROM limit_exposure
) AS 'QA-TAIL-6: limit-down and liquidity exposure weights must be in [0, 1.01]';

CREATE TEMP TABLE latest_signal AS
SELECT COALESCE(
  MAX(IF(pt.rebalance_date <= ev.peak_date, pt.rebalance_date, NULL)),
  MIN(IF(pt.rebalance_date BETWEEN ev.peak_date AND ev.trough_date, pt.rebalance_date, NULL))
) AS signal_date
FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
CROSS JOIN max_dd_event AS ev
WHERE pt.strategy_id = p_strategy_id
  AND pt.run_id = p_run_id
  AND pt.rebalance_date BETWEEN p_predict_start AND p_predict_end
  AND pt.rebalance_date <= ev.trough_date;

ASSERT (
  SELECT signal_date IS NOT NULL
  FROM latest_signal
) AS 'QA-TAIL-7: a latest signal date must exist before the max drawdown peak';

ASSERT (
  SELECT COUNT(*) > 0
  FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
  JOIN latest_signal AS sig
    ON pt.rebalance_date = sig.signal_date
  WHERE pt.strategy_id = p_strategy_id
    AND pt.run_id = p_run_id
    AND pt.rebalance_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-TAIL-8: selected target rows must exist for the latest signal date';

ASSERT (
  SELECT COUNT(*) = 1
    AND LOGICAL_AND(COALESCE(JSON_VALUE(metrics_json, '$.tail_risk_profile_id'), 'diagnostic_only') = p_tail_risk_profile_id)
    AND LOGICAL_AND(COALESCE(JSON_VALUE(metrics_json, '$.market_state_version'), p_market_state_version) = p_market_state_version)
  FROM summary_row
) AS 'QA-TAIL-P1-1: backtest summary metrics_json must record tail_risk_profile_id';

IF p_tail_risk_profile_id IN ('individual_risk_guard_v0', 'individual_and_market_risk_guard_v0') THEN
  ASSERT (
    SELECT COUNT(*) > 0
    FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
    WHERE cand.strategy_id = p_strategy_id
      AND cand.run_id = p_run_id
      AND cand.rebalance_date BETWEEN p_predict_start AND p_predict_end
      AND cand.filter_reason LIKE 'tail_risk:%'
  ) AS 'QA-TAIL-P1-2: individual_risk_guard_v0 must leave auditable tail-risk guard flags';

  ASSERT (
    SELECT COUNT(*) = 0
    FROM (
      WITH tail_targets AS (
        SELECT cand.rebalance_date, cand.sec_code, nxt.cal_date AS exec_date
        FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
        JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS sig_cal
          ON sig_cal.exchange = 'SSE'
         AND sig_cal.is_open = 1
         AND sig_cal.cal_date = cand.rebalance_date
        JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS nxt
          ON nxt.exchange = 'SSE'
         AND nxt.is_open = 1
         AND nxt.trade_date_seq = sig_cal.trade_date_seq + 1
        WHERE cand.strategy_id = p_strategy_id
          AND cand.run_id = p_run_id
          AND cand.rebalance_date BETWEEN p_predict_start AND p_predict_end
          AND cand.is_selected_candidate
          AND STARTS_WITH(COALESCE(cand.filter_reason, ''), 'tail_risk:')
          AND nxt.cal_date BETWEEN p_predict_start AND p_predict_end
      ),
      prior_state AS (
        SELECT
          tt.*,
          COALESCE(pos.shares, 0.0) AS prior_shares
        FROM tail_targets AS tt
        JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS exec_cal
          ON exec_cal.exchange = 'SSE'
         AND exec_cal.is_open = 1
         AND exec_cal.cal_date = tt.exec_date
        LEFT JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS prev
          ON prev.exchange = 'SSE'
         AND prev.is_open = 1
         AND prev.trade_date_seq = exec_cal.trade_date_seq - 1
        LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
          ON pos.backtest_id = p_backtest_id
         AND pos.trade_date = prev.cal_date
         AND pos.sec_code = tt.sec_code
         AND pos.trade_date BETWEEN DATE_SUB(p_predict_start, INTERVAL 10 DAY) AND p_predict_end
      )
      SELECT ps.rebalance_date, ps.sec_code, ps.exec_date
      FROM prior_state AS ps
      JOIN `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
        ON bt.backtest_id = p_backtest_id
       AND bt.trade_date = ps.exec_date
       AND bt.sec_code = ps.sec_code
       AND bt.side = 'BUY'
       AND bt.fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
       AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
      WHERE ps.prior_shares <= 0.000001
    )
  ) AS 'QA-TAIL-P1-3: selected tail-risk names without prior holding must not have filled BUY trades';

  ASSERT (
    SELECT COUNT(*) = 0
    FROM (
      WITH tail_targets AS (
        SELECT cand.rebalance_date, cand.sec_code, nxt.cal_date AS exec_date
        FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
        JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS sig_cal
          ON sig_cal.exchange = 'SSE'
         AND sig_cal.is_open = 1
         AND sig_cal.cal_date = cand.rebalance_date
        JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS nxt
          ON nxt.exchange = 'SSE'
         AND nxt.is_open = 1
         AND nxt.trade_date_seq = sig_cal.trade_date_seq + 1
        WHERE cand.strategy_id = p_strategy_id
          AND cand.run_id = p_run_id
          AND cand.rebalance_date BETWEEN p_predict_start AND p_predict_end
          AND cand.is_selected_candidate
          AND STARTS_WITH(COALESCE(cand.filter_reason, ''), 'tail_risk:')
          AND nxt.cal_date BETWEEN p_predict_start AND p_predict_end
      ),
      prior_state AS (
        SELECT
          tt.*,
          COALESCE(pos.shares, 0.0) AS prior_shares
        FROM tail_targets AS tt
        JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS exec_cal
          ON exec_cal.exchange = 'SSE'
         AND exec_cal.is_open = 1
         AND exec_cal.cal_date = tt.exec_date
        LEFT JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS prev
          ON prev.exchange = 'SSE'
         AND prev.is_open = 1
         AND prev.trade_date_seq = exec_cal.trade_date_seq - 1
        LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
          ON pos.backtest_id = p_backtest_id
         AND pos.trade_date = prev.cal_date
         AND pos.sec_code = tt.sec_code
         AND pos.trade_date BETWEEN DATE_SUB(p_predict_start, INTERVAL 10 DAY) AND p_predict_end
      )
      SELECT ps.rebalance_date, ps.sec_code, ps.exec_date
      FROM prior_state AS ps
      LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
        ON bt.backtest_id = p_backtest_id
       AND bt.trade_date = ps.exec_date
       AND bt.sec_code = ps.sec_code
       AND bt.side = 'BUY'
       AND bt.fill_status = 'BUY_SKIPPED_TAIL_RISK'
       AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
      WHERE ps.prior_shares <= 0.000001
        AND bt.sec_code IS NULL
    )
  ) AS 'QA-TAIL-P1-4: selected tail-risk names without prior holding must emit BUY_SKIPPED_TAIL_RISK';
END IF;

IF p_tail_risk_profile_id IN ('market_risk_off_v0', 'individual_and_market_risk_guard_v0') THEN
  CREATE TEMP TABLE market_risk_off_exec_dates AS
  SELECT
    ms.trade_date AS signal_date,
    nxt.cal_date AS exec_date,
    ms.risk_off_reasons
  FROM `data-aquarium.ashare_dws.dws_market_state_daily` AS ms
  JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS sig_cal
    ON sig_cal.exchange = 'SSE'
   AND sig_cal.is_open = 1
   AND sig_cal.cal_date = ms.trade_date
  JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS nxt
    ON nxt.exchange = 'SSE'
   AND nxt.is_open = 1
   AND nxt.trade_date_seq = sig_cal.trade_date_seq + 1
  WHERE ms.trade_date BETWEEN p_predict_start AND p_predict_end
    AND ms.market_state_version = p_market_state_version
    AND ms.is_risk_off
    AND ms.risk_off_action = 'skip_new_buys'
    AND nxt.cal_date BETWEEN p_predict_start AND p_predict_end;

  ASSERT (
    SELECT COUNT(*) > 0
    FROM market_risk_off_exec_dates
  ) AS 'QA-TAIL-P2-1: market-risk profile must have auditable risk-off dates';

  ASSERT (
    SELECT COUNT(*) = 0
    FROM market_risk_off_exec_dates
    WHERE COALESCE(risk_off_reasons, '') = ''
  ) AS 'QA-TAIL-P2-2: risk-off dates must carry market-state trigger evidence';

  ASSERT (
    SELECT COUNT(*) = 0
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
    JOIN market_risk_off_exec_dates AS rd
      ON rd.exec_date = bt.trade_date
    WHERE bt.backtest_id = p_backtest_id
      AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
      AND bt.side = 'BUY'
      AND bt.fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
  ) AS 'QA-TAIL-P2-3: market risk-off execution dates must not have filled BUY trades';

  ASSERT (
    SELECT COUNT(*) = 0
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
    LEFT JOIN market_risk_off_exec_dates AS rd
      ON rd.exec_date = bt.trade_date
    WHERE bt.backtest_id = p_backtest_id
      AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
      AND bt.fill_status = 'BUY_SKIPPED_MARKET_RISK_OFF'
      AND rd.exec_date IS NULL
  ) AS 'QA-TAIL-P2-4: market-risk skipped buys must map to risk-off execution dates';

  ASSERT (
    SELECT COUNT(*) > 0
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
    WHERE bt.backtest_id = p_backtest_id
      AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
      AND bt.fill_status = 'BUY_SKIPPED_MARKET_RISK_OFF'
  ) AS 'QA-TAIL-P2-5: market-risk profile must leave skipped BUY audit rows';
END IF;

CREATE TEMP TABLE guard_hash AS
WITH summary_guard AS (
  SELECT
    TO_HEX(SHA256(COALESCE(STRING_AGG(TO_JSON_STRING(STRUCT(
      bs.backtest_id AS backtest_id,
      bs.strategy_id AS strategy_id,
      bs.model_id AS model_id,
      FORMAT_DATE('%F', bs.start_date) AS start_date,
      FORMAT_DATE('%F', bs.end_date) AS end_date,
      bs.total_return AS total_return,
      bs.excess_return AS excess_return,
      bs.annual_return AS annual_return,
      bs.annual_vol AS annual_vol,
      bs.sharpe AS sharpe,
      bs.max_drawdown AS max_drawdown,
      bs.turnover_annual AS turnover_annual,
      bs.cost_bps AS cost_bps,
      JSON_VALUE(bs.metrics_json, '$.report_uri') AS report_uri,
      JSON_VALUE(bs.metrics_json, '$.model_diagnosis_uri') AS model_diagnosis_uri
    )), '\n' ORDER BY bs.backtest_id), ''))) AS summary_hash
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
),
nav_guard AS (
  SELECT
    TO_HEX(SHA256(COALESCE(STRING_AGG(TO_JSON_STRING(STRUCT(
      FORMAT_DATE('%F', nav.trade_date) AS trade_date,
      nav.nav AS nav,
      nav.daily_return AS daily_return,
      nav.cash_cny AS cash_cny,
      nav.gross_exposure AS gross_exposure
    )), '\n' ORDER BY nav.trade_date), ''))) AS nav_hash
  FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
  WHERE nav.backtest_id = p_backtest_id
    AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
)
SELECT summary_hash, nav_hash
FROM summary_guard
CROSS JOIN nav_guard;

ASSERT (
  SELECT p_expected_summary_hash IS NULL OR summary_hash = p_expected_summary_hash
  FROM guard_hash
) AS 'QA-TAIL-9: summary hash must match analyze_tail_risk.py post-guard when supplied';

ASSERT (
  SELECT p_expected_nav_hash IS NULL OR nav_hash = p_expected_nav_hash
  FROM guard_hash
) AS 'QA-TAIL-10: NAV hash must match analyze_tail_risk.py post-guard when supplied';

SELECT
  'QA-TAIL completed' AS status,
  (SELECT peak_date FROM max_dd_event) AS peak_date,
  (SELECT trough_date FROM max_dd_event) AS trough_date,
  (SELECT drawdown_pct FROM max_dd_event) AS drawdown_pct,
  (SELECT summary_hash FROM guard_hash) AS summary_hash,
  (SELECT nav_hash FROM guard_hash) AS nav_hash;
