-- BigQuery Standard SQL · Strategy 1 top-down lot-aware construction QA

DECLARE p_run_id STRING DEFAULT 's1_topdown_unit';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_topdown_unit';
DECLARE p_predict_start DATE DEFAULT DATE '2021-01-04';
DECLARE p_predict_end DATE DEFAULT DATE '2026-06-09';
DECLARE p_ledger_version STRING DEFAULT 'ledger_exec_v2_lot100_topdown';
DECLARE p_lot_size INT64 DEFAULT 100;
DECLARE p_min_buy_lot INT64 DEFAULT 1;
DECLARE p_position_floor_count INT64 DEFAULT 20;
DECLARE p_min_position_weight FLOAT64 DEFAULT 0.05;
DECLARE p_walk_depth INT64 DEFAULT 50;
DECLARE p_tail_risk_profile_id STRING DEFAULT 'individual_risk_guard_v0';
DECLARE p_resume_policy_id STRING DEFAULT 'cloudrun_lot100_topdown_resume_v1';

ASSERT (
  SELECT COUNT(*) = 1
    AND LOGICAL_AND(JSON_VALUE(bs.metrics_json, '$.ledger_version') = p_ledger_version)
    AND LOGICAL_AND(JSON_VALUE(bs.metrics_json, '$.portfolio_construction_method') = 'topdown_lot100_v2')
    AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(bs.metrics_json, '$.lot_size') AS INT64) = p_lot_size)
    AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(bs.metrics_json, '$.min_buy_lot') AS INT64) = p_min_buy_lot)
    AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(bs.metrics_json, '$.position_floor_count') AS INT64) = p_position_floor_count)
    AND LOGICAL_AND(ABS(SAFE_CAST(JSON_VALUE(bs.metrics_json, '$.min_position_weight') AS FLOAT64) - p_min_position_weight) <= 1e-9)
    AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(bs.metrics_json, '$.walk_depth') AS INT64) = p_walk_depth)
    AND LOGICAL_AND(JSON_VALUE(bs.metrics_json, '$.cash_redistribution') = 'topdown_whole_order_skip_v2')
    AND LOGICAL_AND(JSON_VALUE(bs.metrics_json, '$.resume_policy_id') = p_resume_policy_id)
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-TOPDOWN-1: summary must record top-down ledger v2 construction parameters';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
  WHERE bt.backtest_id = p_backtest_id
    AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
    AND bt.fill_status IN ('FILLED_SCALED_CASH', 'BUY_SKIPPED_BELOW_LOT_AFTER_SCALE')
) AS 'QA-TOPDOWN-2: top-down v2 must not use cash scaling statuses';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
  WHERE bt.backtest_id = p_backtest_id
    AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
    AND bt.side = 'BUY'
    AND bt.fill_status = 'FILLED'
    AND (
      CAST(ROUND(bt.filled_shares) AS INT64) < p_lot_size * p_min_buy_lot
      OR MOD(CAST(ROUND(bt.filled_shares) AS INT64), p_lot_size) != 0
    )
) AS 'QA-TOPDOWN-3: filled BUY shares must be whole lots';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
  JOIN `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
    ON nav.backtest_id = bt.backtest_id
   AND nav.trade_date = bt.trade_date
   AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
  WHERE bt.backtest_id = p_backtest_id
    AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
    AND bt.side = 'BUY'
    AND bt.fill_status = 'FILLED'
    AND SAFE_DIVIDE(bt.turnover_cny, NULLIF(nav.net_value_cny, 0)) + 0.0005 < p_min_position_weight
) AS 'QA-TOPDOWN-4: each new filled BUY must meet min_position_weight at execution';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT
      cand.rebalance_date,
      COUNTIF(cand.rank_raw IS NOT NULL AND cand.rank_raw <= p_walk_depth) AS evaluated_count,
      COUNTIF(cand.rank_raw IS NOT NULL) AS ranked_count
    FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
    WHERE cand.strategy_id = p_strategy_id
      AND cand.run_id = p_run_id
      AND cand.rebalance_date BETWEEN p_predict_start AND p_predict_end
    GROUP BY cand.rebalance_date
    HAVING evaluated_count < LEAST(p_walk_depth, ranked_count)
  )
) AS 'QA-TOPDOWN-5: candidate input must cover full rank walk_depth';

IF p_tail_risk_profile_id IN ('individual_risk_guard_v0', 'individual_and_market_risk_guard_v0') THEN
  ASSERT (
    SELECT COUNT(*) > 0
    FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
    WHERE cand.strategy_id = p_strategy_id
      AND cand.run_id = p_run_id
      AND cand.rebalance_date BETWEEN p_predict_start AND p_predict_end
      AND cand.rank_raw <= p_walk_depth
      AND STARTS_WITH(COALESCE(cand.filter_reason, ''), 'tail_risk:')
  ) AS 'QA-TOPDOWN-6: P1-enabled top-down run must have tail_risk markers inside walk_depth';

  ASSERT (
    SELECT COUNT(*) = 0
    FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
    JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS sig_cal
      ON sig_cal.exchange = 'SSE'
     AND sig_cal.is_open = 1
     AND sig_cal.cal_date = cand.rebalance_date
    JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS exec_cal
      ON exec_cal.exchange = 'SSE'
     AND exec_cal.is_open = 1
     AND exec_cal.trade_date_seq = sig_cal.trade_date_seq + 1
    JOIN `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
      ON bt.backtest_id = p_backtest_id
     AND bt.trade_date = exec_cal.cal_date
     AND bt.sec_code = cand.sec_code
     AND bt.side = 'BUY'
     AND bt.fill_status = 'FILLED'
     AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
    WHERE cand.strategy_id = p_strategy_id
      AND cand.run_id = p_run_id
      AND cand.rebalance_date BETWEEN p_predict_start AND p_predict_end
      AND cand.rank_raw <= p_walk_depth
      AND STARTS_WITH(COALESCE(cand.filter_reason, ''), 'tail_risk:')
  ) AS 'QA-TOPDOWN-7: tail-risk marked candidates inside walk_depth must not create filled BUYs';
END IF;

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
  WHERE nav.backtest_id = p_backtest_id
    AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
    AND (nav.cash_cny < -1.0 OR nav.gross_exposure > 1.005)
) AS 'QA-TOPDOWN-8: top-down v2 must remain long-only without negative cash';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    WITH signal_exec AS (
      SELECT
        cand.rebalance_date AS signal_date,
        exec_cal.cal_date AS exec_date,
        cand.sec_code,
        cand.rank_raw
      FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
      JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS sig_cal
        ON sig_cal.exchange = 'SSE'
       AND sig_cal.is_open = 1
       AND sig_cal.cal_date = cand.rebalance_date
      JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS exec_cal
        ON exec_cal.exchange = 'SSE'
       AND exec_cal.is_open = 1
       AND exec_cal.trade_date_seq = sig_cal.trade_date_seq + 1
      WHERE cand.strategy_id = p_strategy_id
        AND cand.run_id = p_run_id
        AND cand.rebalance_date BETWEEN p_predict_start AND p_predict_end
        AND exec_cal.cal_date BETWEEN p_predict_start AND p_predict_end
    )
    SELECT pos.trade_date, pos.sec_code
    FROM `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
    JOIN (
      SELECT DISTINCT exec_date FROM signal_exec
    ) AS rebalance_exec
      ON rebalance_exec.exec_date = pos.trade_date
    LEFT JOIN signal_exec AS se
      ON se.exec_date = pos.trade_date
     AND se.sec_code = pos.sec_code
    LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
      ON bt.backtest_id = p_backtest_id
     AND bt.trade_date = pos.trade_date
     AND bt.sec_code = pos.sec_code
     AND bt.side = 'SELL'
     AND bt.fill_status IN ('SELL_SKIPPED_UNTRADABLE', 'PENDING_SELL_CARRY')
     AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
    WHERE pos.backtest_id = p_backtest_id
      AND pos.trade_date BETWEEN p_predict_start AND p_predict_end
      AND COALESCE(se.rank_raw, 1000000000) > p_walk_depth
      AND bt.sec_code IS NULL
  )
) AS 'QA-TOPDOWN-9: over-depth holdings after rebalance must trace to sell failure';
