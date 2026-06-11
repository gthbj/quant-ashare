-- BigQuery Standard SQL
-- Strategy1 tail-risk overlay A/B preflight and guard-effectiveness QA.

DECLARE p_baseline_run_id STRING DEFAULT 's1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02';
DECLARE p_baseline_backtest_id STRING DEFAULT 'bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02';
DECLARE p_prediction_run_id STRING DEFAULT 's1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_synthetic_model_id STRING DEFAULT NULL;
DECLARE p_manifest_sha256 STRING DEFAULT NULL;
DECLARE p_predict_start DATE DEFAULT DATE '2021-01-04';
DECLARE p_predict_end DATE DEFAULT DATE '2026-06-09';
DECLARE p_rebalance_anchor_start DATE DEFAULT NULL;
DECLARE p_feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_market_state_version STRING DEFAULT 'market_state_v1_20260607';
DECLARE p_a1_run_id STRING DEFAULT 's1_tailrisk_overlay_ab_continuous_2021_2026_n20_w075_p1_v20260611_01';
DECLARE p_a1_backtest_id STRING DEFAULT 'bt_s1_tailrisk_overlay_ab_continuous_2021_2026_n20_w075_p1_v20260611_01';
DECLARE p_a2_run_id STRING DEFAULT 's1_tailrisk_overlay_ab_continuous_2021_2026_n20_w075_p2_v20260611_01';
DECLARE p_a2_backtest_id STRING DEFAULT 'bt_s1_tailrisk_overlay_ab_continuous_2021_2026_n20_w075_p2_v20260611_01';
DECLARE p_a3_run_id STRING DEFAULT 's1_tailrisk_overlay_ab_continuous_2021_2026_n20_w075_p1p2_v20260611_01';
DECLARE p_a3_backtest_id STRING DEFAULT 'bt_s1_tailrisk_overlay_ab_continuous_2021_2026_n20_w075_p1p2_v20260611_01';
DECLARE p_min_tail_risk_skips INT64 DEFAULT 1;
DECLARE p_min_tail_risk_crunch_skips INT64 DEFAULT 1;
DECLARE p_crunch_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_crunch_end DATE DEFAULT DATE '2024-02-07';
DECLARE p_preflight_only BOOL DEFAULT FALSE;

SET p_rebalance_anchor_start = COALESCE(p_rebalance_anchor_start, p_predict_start);

CREATE TEMP TABLE arm_runs AS
SELECT * FROM UNNEST([
  STRUCT('baseline' AS arm, 'diagnostic_only' AS tail_risk_profile_id, p_baseline_run_id AS run_id, p_baseline_backtest_id AS backtest_id),
  STRUCT('A1' AS arm, 'individual_risk_guard_v0' AS tail_risk_profile_id, p_a1_run_id AS run_id, p_a1_backtest_id AS backtest_id),
  STRUCT('A2' AS arm, 'market_risk_off_v0' AS tail_risk_profile_id, p_a2_run_id AS run_id, p_a2_backtest_id AS backtest_id),
  STRUCT('A3' AS arm, 'individual_and_market_risk_guard_v0' AS tail_risk_profile_id, p_a3_run_id AS run_id, p_a3_backtest_id AS backtest_id)
]);

ASSERT p_predict_start <= p_predict_end
  AS 'QA-OVERLAY-0: predict start must be <= predict end';

ASSERT p_rebalance_anchor_start <= p_predict_start
  AS 'QA-OVERLAY-0A: rebalance anchor start must be <= predict start';

ASSERT (
  SELECT COUNT(*) = 1
    AND LOGICAL_AND(JSON_VALUE(reg.model_params_json, '$.synthetic_continuous') = 'true')
    AND LOGICAL_AND(JSON_VALUE(reg.model_params_json, '$.source_all_refit') = 'true')
    AND LOGICAL_AND(COALESCE(p_synthetic_model_id, reg.model_id) = reg.model_id)
    AND LOGICAL_AND(p_manifest_sha256 IS NULL OR JSON_VALUE(reg.metrics_json, '$.input_manifest_sha256') = p_manifest_sha256)
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_prediction_run_id
) AS 'QA-OVERLAY-1: prediction source must be exactly one refit-backed synthetic continuous selected registry row';

ASSERT (
  WITH calendar AS (
    SELECT cal_date
    FROM `data-aquarium.ashare_dim.dim_trade_calendar`
    WHERE exchange = 'SSE'
      AND is_open = 1
      AND cal_date BETWEEN p_predict_start AND p_predict_end
  ),
  market_state AS (
    SELECT trade_date, COUNT(*) AS n, LOGICAL_AND(is_risk_off IS NOT NULL) AS is_risk_off_populated
    FROM `data-aquarium.ashare_dws.dws_market_state_daily`
    WHERE market_state_version = p_market_state_version
      AND trade_date BETWEEN p_predict_start AND p_predict_end
    GROUP BY trade_date
  )
  SELECT COUNTIF(market_state.n IS NULL) = 0
    AND COUNTIF(market_state.n != 1) = 0
    AND COUNTIF(NOT COALESCE(market_state.is_risk_off_populated, FALSE)) = 0
  FROM calendar
  LEFT JOIN market_state
    ON market_state.trade_date = calendar.cal_date
) AS 'QA-OVERLAY-2: market state must cover every SSE open date exactly once with non-NULL is_risk_off';

CREATE TEMP TABLE selected_synthetic_model AS
SELECT reg.model_id
FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
WHERE reg.strategy_id = p_strategy_id
  AND reg.status = 'selected'
  AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_prediction_run_id
ORDER BY reg.created_at DESC
LIMIT 1;

CREATE TEMP TABLE rebalance_dates AS
WITH cal AS (
  SELECT cal_date
  FROM `data-aquarium.ashare_dim.dim_trade_calendar`
  WHERE exchange = 'SSE'
    AND is_open = 1
    AND cal_date BETWEEN p_rebalance_anchor_start AND p_predict_end
),
weekly AS (
  SELECT MAX(cal_date) AS rebalance_date
  FROM cal
  GROUP BY EXTRACT(ISOYEAR FROM cal_date), EXTRACT(ISOWEEK FROM cal_date)
),
weekly_ranked AS (
  SELECT rebalance_date, ROW_NUMBER() OVER (ORDER BY rebalance_date) AS week_idx
  FROM weekly
)
SELECT rebalance_date
FROM weekly_ranked
WHERE MOD(week_idx - 1, 2) = 0
  AND rebalance_date BETWEEN p_predict_start AND p_predict_end;

CREATE TEMP TABLE top20_rebalance_predictions AS
WITH scored AS (
  SELECT
    r.rebalance_date,
    pred.sec_code,
    pred.score,
    feat.ret_20d,
    feat.drawdown_20d,
    feat.limit_down_days_20d,
    feat.one_word_limit_days_20d,
    feat.total_mv_cny,
    feat.circ_mv_cny,
    ROW_NUMBER() OVER (PARTITION BY r.rebalance_date ORDER BY pred.score DESC, pred.sec_code) AS rk
  FROM rebalance_dates AS r
  JOIN selected_synthetic_model AS sm
    ON TRUE
  JOIN `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
    ON pred.run_id = p_prediction_run_id
   AND pred.model_id = sm.model_id
   AND pred.predict_date = r.rebalance_date
   AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
  JOIN `data-aquarium.ashare_dws.dws_stock_universe_daily` AS u
    ON u.sec_code = pred.sec_code
   AND u.trade_date = r.rebalance_date
   AND u.trade_date BETWEEN p_predict_start AND p_predict_end
   AND COALESCE(u.in_universe_default, FALSE)
  LEFT JOIN `data-aquarium.ashare_dws.dws_stock_feature_daily_v0` AS feat
    ON feat.sec_code = pred.sec_code
   AND feat.trade_date = r.rebalance_date
   AND feat.feature_version = p_feature_version
   AND feat.trade_date BETWEEN p_predict_start AND p_predict_end
)
SELECT *
FROM scored
WHERE rk <= 20;

ASSERT (
  SELECT COUNT(*) > 0
    AND COUNTIF(
      ret_20d IS NULL
      OR drawdown_20d IS NULL
      OR limit_down_days_20d IS NULL
      OR one_word_limit_days_20d IS NULL
      OR total_mv_cny IS NULL
      OR circ_mv_cny IS NULL
    ) = 0
  FROM top20_rebalance_predictions
) AS 'QA-OVERLAY-3: top20 rebalance predictions must have populated tail-risk required fields';

ASSERT (
  SELECT COUNTIF(
    ret_20d < -0.30
    OR drawdown_20d < -0.30
    OR limit_down_days_20d >= 2
    OR one_word_limit_days_20d >= 1
    OR total_mv_cny < 30e8
    OR circ_mv_cny < 20e8
  ) >= p_min_tail_risk_skips
    AND COUNTIF(
      rebalance_date BETWEEN p_crunch_start AND p_crunch_end
      AND (
        ret_20d < -0.30
        OR drawdown_20d < -0.30
        OR limit_down_days_20d >= 2
        OR one_word_limit_days_20d >= 1
        OR total_mv_cny < 30e8
        OR circ_mv_cny < 20e8
      )
    ) >= p_min_tail_risk_crunch_skips
  FROM top20_rebalance_predictions
) AS 'QA-OVERLAY-4: top20 prediction stream must contain actionable individual tail-risk rows overall and in the crunch window';

ASSERT (
  WITH calendar AS (
    SELECT cal_date
    FROM `data-aquarium.ashare_dim.dim_trade_calendar`
    WHERE exchange = 'SSE'
      AND is_open = 1
      AND cal_date BETWEEN p_crunch_start AND p_crunch_end
  ),
  csi1000 AS (
    SELECT trade_date, COUNT(*) AS n, LOGICAL_AND(pct_chg IS NOT NULL) AS pct_chg_populated
    FROM `data-aquarium.ashare_dwd.dwd_index_eod`
    WHERE sec_code = '000852.SH'
      AND trade_date BETWEEN p_crunch_start AND p_crunch_end
    GROUP BY trade_date
  )
  SELECT COUNTIF(csi1000.n IS NULL) = 0
    AND COUNTIF(csi1000.n != 1) = 0
    AND COUNTIF(NOT COALESCE(csi1000.pct_chg_populated, FALSE)) = 0
  FROM calendar
  LEFT JOIN csi1000
    ON csi1000.trade_date = calendar.cal_date
) AS 'QA-OVERLAY-4A: CSI1000 crunch benchmark must cover every SSE open date with pct_chg';

IF NOT p_preflight_only THEN
  ASSERT (
    SELECT COUNT(*) = 4
      AND LOGICAL_AND(bs.run_id = arms.run_id)
      AND LOGICAL_AND(bs.start_date = p_predict_start)
      AND LOGICAL_AND(bs.end_date = p_predict_end)
      AND LOGICAL_AND(JSON_VALUE(bs.metrics_json, '$.prediction_run_id') = p_prediction_run_id)
      AND LOGICAL_AND(JSON_VALUE(bs.metrics_json, '$.tail_risk_profile_id') = arms.tail_risk_profile_id)
    FROM arm_runs AS arms
    JOIN `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
      ON bs.backtest_id = arms.backtest_id
     AND bs.created_date BETWEEN p_predict_start AND CURRENT_DATE()
  ) AS 'QA-OVERLAY-5: baseline and three overlay arms must have summary rows with expected source prediction and profile';

  CREATE TEMP TABLE risk_off_exec_dates AS
  SELECT
    ms.trade_date AS signal_date,
    nxt.cal_date AS exec_date
  FROM `data-aquarium.ashare_dws.dws_market_state_daily` AS ms
  JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS sig_cal
    ON sig_cal.exchange = 'SSE'
   AND sig_cal.is_open = 1
   AND sig_cal.cal_date = ms.trade_date
  JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS nxt
    ON nxt.exchange = 'SSE'
   AND nxt.is_open = 1
   AND nxt.trade_date_seq = sig_cal.trade_date_seq + 1
  WHERE ms.market_state_version = p_market_state_version
    AND ms.is_risk_off
    AND ms.risk_off_action = 'skip_new_buys'
    AND ms.trade_date BETWEEN p_predict_start AND p_predict_end
    AND nxt.cal_date BETWEEN p_predict_start AND p_predict_end;

  ASSERT (
    SELECT COUNT(*) > 0
    FROM risk_off_exec_dates
  ) AS 'QA-OVERLAY-6: market risk-off profile must have risk-off execution dates in this window';

  ASSERT (
    WITH tail_risk_arms AS (
      SELECT arm, backtest_id
      FROM arm_runs
      WHERE arm IN ('A1', 'A3')
    ),
    per_arm AS (
      SELECT
        tail_risk_arms.arm,
        COUNTIF(bt.fill_status = 'BUY_SKIPPED_TAIL_RISK') AS skip_count,
        COUNTIF(bt.fill_status = 'BUY_SKIPPED_TAIL_RISK' AND bt.trade_date BETWEEN p_crunch_start AND p_crunch_end) AS crunch_skip_count
      FROM tail_risk_arms
      LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
        ON bt.backtest_id = tail_risk_arms.backtest_id
       AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
      GROUP BY tail_risk_arms.arm
    )
    SELECT COUNT(*) = 2
      AND LOGICAL_AND(skip_count >= p_min_tail_risk_skips)
      AND LOGICAL_AND(crunch_skip_count >= p_min_tail_risk_crunch_skips)
    FROM per_arm
  ) AS 'QA-OVERLAY-7: A1/A3 must emit BUY_SKIPPED_TAIL_RISK overall and in crunch window';

  ASSERT (
    SELECT COUNT(*) = 0
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
    JOIN risk_off_exec_dates AS rd
      ON rd.exec_date = bt.trade_date
    WHERE bt.backtest_id IN (p_a2_backtest_id, p_a3_backtest_id)
      AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
      AND bt.side = 'BUY'
      AND bt.fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
  ) AS 'QA-OVERLAY-8: A2/A3 risk-off execution dates must not have filled BUY trades';

  ASSERT (
    SELECT COUNT(*) = 0
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
    LEFT JOIN risk_off_exec_dates AS rd
      ON rd.exec_date = bt.trade_date
    WHERE bt.backtest_id IN (p_a2_backtest_id, p_a3_backtest_id)
      AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
      AND bt.fill_status = 'BUY_SKIPPED_MARKET_RISK_OFF'
      AND rd.exec_date IS NULL
  ) AS 'QA-OVERLAY-9: BUY_SKIPPED_MARKET_RISK_OFF must occur only on risk-off execution dates';

  ASSERT (
    WITH market_arms AS (
      SELECT arm, backtest_id
      FROM arm_runs
      WHERE arm IN ('A2', 'A3')
    ),
    per_arm AS (
      SELECT
        market_arms.arm,
        COUNTIF(bt.fill_status = 'BUY_SKIPPED_MARKET_RISK_OFF') AS skip_count
      FROM market_arms
      LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
        ON bt.backtest_id = market_arms.backtest_id
       AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
      GROUP BY market_arms.arm
    )
    SELECT COUNT(*) = 2
      AND LOGICAL_AND(skip_count > 0)
    FROM per_arm
  ) AS 'QA-OVERLAY-10: A2/A3 must leave BUY_SKIPPED_MARKET_RISK_OFF audit rows';

  ASSERT (
    WITH baseline_rows AS (
      SELECT
        rebalance_date,
        sec_code,
        TO_JSON_STRING(STRUCT(model_id, horizon, score, rank_raw, rank_pct, in_universe_default, is_selected_candidate, filter_reason)) AS fp
      FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily`
      WHERE run_id = p_baseline_run_id
        AND strategy_id = p_strategy_id
        AND rebalance_date BETWEEN p_predict_start AND p_predict_end
    ),
    a2_rows AS (
      SELECT
        rebalance_date,
        sec_code,
        TO_JSON_STRING(STRUCT(model_id, horizon, score, rank_raw, rank_pct, in_universe_default, is_selected_candidate, filter_reason)) AS fp
      FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily`
      WHERE run_id = p_a2_run_id
        AND strategy_id = p_strategy_id
        AND rebalance_date BETWEEN p_predict_start AND p_predict_end
    )
    SELECT COUNT(*) = 0
    FROM baseline_rows AS base
    FULL OUTER JOIN a2_rows AS a2
      USING (rebalance_date, sec_code)
    WHERE base.fp IS NULL OR a2.fp IS NULL OR base.fp != a2.fp
  ) AS 'QA-OVERLAY-11: A2 market-only arm must match baseline candidate rows before ledger guard';

  ASSERT (
    WITH baseline_rows AS (
      SELECT
        rebalance_date,
        sec_code,
        TO_JSON_STRING(STRUCT(target_weight, target_shares, target_amount_cny, model_id, horizon)) AS fp
      FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily`
      WHERE run_id = p_baseline_run_id
        AND strategy_id = p_strategy_id
        AND rebalance_date BETWEEN p_predict_start AND p_predict_end
    ),
    a2_rows AS (
      SELECT
        rebalance_date,
        sec_code,
        TO_JSON_STRING(STRUCT(target_weight, target_shares, target_amount_cny, model_id, horizon)) AS fp
      FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily`
      WHERE run_id = p_a2_run_id
        AND strategy_id = p_strategy_id
        AND rebalance_date BETWEEN p_predict_start AND p_predict_end
    )
    SELECT COUNT(*) = 0
    FROM baseline_rows AS base
    FULL OUTER JOIN a2_rows AS a2
      USING (rebalance_date, sec_code)
    WHERE base.fp IS NULL OR a2.fp IS NULL OR base.fp != a2.fp
  ) AS 'QA-OVERLAY-12: A2 market-only arm must match baseline portfolio targets before ledger guard';
END IF;

IF p_preflight_only THEN
  SELECT
    'QA-OVERLAY preflight completed' AS status,
    p_prediction_run_id AS prediction_run_id,
    p_market_state_version AS market_state_version,
    (SELECT COUNT(*) FROM rebalance_dates) AS rebalance_count,
    (SELECT COUNT(*) FROM top20_rebalance_predictions) AS top20_selected_rows,
    (SELECT COUNTIF(
      ret_20d < -0.30
      OR drawdown_20d < -0.30
      OR limit_down_days_20d >= 2
      OR one_word_limit_days_20d >= 1
      OR total_mv_cny < 30e8
      OR circ_mv_cny < 20e8
    ) FROM top20_rebalance_predictions) AS top20_tail_risk_rows;
ELSE
  WITH skip_counts AS (
    SELECT
      arms.arm,
      COUNTIF(bt.fill_status = 'BUY_SKIPPED_TAIL_RISK') AS buy_skipped_tail_risk,
      COUNTIF(bt.fill_status = 'BUY_SKIPPED_MARKET_RISK_OFF') AS buy_skipped_market_risk_off
    FROM arm_runs AS arms
    LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
      ON bt.backtest_id = arms.backtest_id
     AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
    GROUP BY arms.arm
  ),
  years AS (
    SELECT DISTINCT EXTRACT(YEAR FROM cal_date) AS year
    FROM `data-aquarium.ashare_dim.dim_trade_calendar`
    WHERE exchange = 'SSE'
      AND is_open = 1
      AND cal_date BETWEEN p_predict_start AND p_predict_end
  ),
  yearly_skip_counts AS (
    WITH arm_years AS (
      SELECT arms.arm, years.year
      FROM arm_runs AS arms
      CROSS JOIN years
    ),
    counts AS (
      SELECT
        arms.arm,
        EXTRACT(YEAR FROM bt.trade_date) AS year,
        COUNTIF(bt.fill_status = 'BUY_SKIPPED_TAIL_RISK') AS buy_skipped_tail_risk,
        COUNTIF(bt.fill_status = 'BUY_SKIPPED_MARKET_RISK_OFF') AS buy_skipped_market_risk_off
      FROM arm_runs AS arms
      JOIN `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
        ON bt.backtest_id = arms.backtest_id
       AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
      GROUP BY arms.arm, year
    )
    SELECT
      arm_years.arm,
      TO_JSON_STRING(ARRAY_AGG(STRUCT(
        arm_years.year AS year,
        COALESCE(counts.buy_skipped_tail_risk, 0) AS buy_skipped_tail_risk,
        COALESCE(counts.buy_skipped_market_risk_off, 0) AS buy_skipped_market_risk_off
      ) ORDER BY arm_years.year)) AS buy_skipped_yearly_json
    FROM arm_years
    LEFT JOIN counts
      ON counts.arm = arm_years.arm
     AND counts.year = arm_years.year
    GROUP BY arm_years.arm
  ),
  risk_off_cash AS (
    SELECT
      arms.arm,
      AVG(nav.cash_cny / NULLIF(nav.net_value_cny, 0)) AS risk_off_cash_ratio_avg,
      MAX(nav.cash_cny / NULLIF(nav.net_value_cny, 0)) AS risk_off_cash_ratio_max
    FROM arm_runs AS arms
    JOIN `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
      ON nav.backtest_id = arms.backtest_id
     AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
    JOIN risk_off_exec_dates AS rd
      ON rd.exec_date = nav.trade_date
    GROUP BY arms.arm
  ),
  nav_series AS (
    SELECT
      arms.arm,
      nav.trade_date,
      nav.nav,
      nav.daily_return
    FROM arm_runs AS arms
    JOIN `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
      ON nav.backtest_id = arms.backtest_id
     AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
  ),
  running_peak AS (
    SELECT
      *,
      MAX(nav) OVER (PARTITION BY arm ORDER BY trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS peak_nav
    FROM nav_series
  ),
  drawdown_ranked AS (
    SELECT
      *,
      SAFE_DIVIDE(nav, peak_nav) - 1.0 AS drawdown,
      ROW_NUMBER() OVER (
        PARTITION BY arm
        ORDER BY SAFE_DIVIDE(nav, peak_nav) - 1.0 ASC, trade_date ASC
      ) AS rn
    FROM running_peak
  ),
  drawdown_windows AS (
    SELECT
      ranked.arm,
      (
        SELECT MIN(series.trade_date)
        FROM nav_series AS series
        WHERE series.arm = ranked.arm
          AND series.trade_date <= ranked.trade_date
          AND ABS(series.nav - ranked.peak_nav) < 1e-9
      ) AS max_drawdown_peak_date,
      ranked.trade_date AS max_drawdown_trough_date,
      ranked.drawdown AS computed_max_drawdown
    FROM drawdown_ranked AS ranked
    WHERE ranked.rn = 1
  ),
  crunch_strategy_returns AS (
    SELECT
      arms.arm,
      EXP(SUM(IF(1.0 + COALESCE(nav.daily_return, 0.0) > 0.0, LN(1.0 + COALESCE(nav.daily_return, 0.0)), NULL))) - 1.0 AS crunch_strategy_return
    FROM arm_runs AS arms
    JOIN `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
      ON nav.backtest_id = arms.backtest_id
     AND nav.trade_date BETWEEN p_crunch_start AND p_crunch_end
    GROUP BY arms.arm
  ),
  crunch_csi1000_return AS (
    SELECT
      EXP(SUM(IF(1.0 + pct_chg / 100.0 > 0.0, LN(1.0 + pct_chg / 100.0), NULL))) - 1.0 AS csi1000_return,
      COUNT(*) AS csi1000_row_count
    FROM `data-aquarium.ashare_dwd.dwd_index_eod`
    WHERE sec_code = '000852.SH'
      AND trade_date BETWEEN p_crunch_start AND p_crunch_end
  )
  SELECT
    arms.arm,
    arms.tail_risk_profile_id,
    arms.run_id,
    arms.backtest_id,
    bs.compound_annual_return,
    bs.max_drawdown,
    bs.sharpe AS summary_sharpe,
    SAFE_DIVIDE(bs.compound_annual_return, NULLIF(bs.annual_vol, 0.0)) AS contract_sharpe,
    bs.information_ratio,
    SAFE_DIVIDE(bs.compound_annual_return, ABS(bs.max_drawdown)) AS calmar_ratio,
    bs.turnover_annual,
    drawdown_windows.max_drawdown_peak_date,
    drawdown_windows.max_drawdown_trough_date,
    drawdown_windows.computed_max_drawdown,
    skips.buy_skipped_tail_risk,
    skips.buy_skipped_market_risk_off,
    yearly_skips.buy_skipped_yearly_json,
    risk_off_cash.risk_off_cash_ratio_avg,
    risk_off_cash.risk_off_cash_ratio_max,
    crunch_returns.crunch_strategy_return,
    csi1000.csi1000_return AS crunch_csi1000_return,
    crunch_returns.crunch_strategy_return - csi1000.csi1000_return AS crunch_excess_return_vs_000852,
    csi1000.csi1000_row_count AS crunch_csi1000_row_count
  FROM arm_runs AS arms
  JOIN `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
    ON bs.backtest_id = arms.backtest_id
   AND bs.created_date BETWEEN p_predict_start AND CURRENT_DATE()
  LEFT JOIN skip_counts AS skips
    ON skips.arm = arms.arm
  LEFT JOIN yearly_skip_counts AS yearly_skips
    ON yearly_skips.arm = arms.arm
  LEFT JOIN risk_off_cash
    ON risk_off_cash.arm = arms.arm
  LEFT JOIN drawdown_windows
    ON drawdown_windows.arm = arms.arm
  LEFT JOIN crunch_strategy_returns AS crunch_returns
    ON crunch_returns.arm = arms.arm
  CROSS JOIN crunch_csi1000_return AS csi1000
  ORDER BY
    CASE arms.arm
      WHEN 'baseline' THEN 0
      WHEN 'A1' THEN 1
      WHEN 'A2' THEN 2
      WHEN 'A3' THEN 3
      ELSE 99
    END;
END IF;
