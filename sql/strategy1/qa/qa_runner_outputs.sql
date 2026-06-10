-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 10: 运行后 QA 断言（全部用 p_ 前缀变量，别名限定表列）。

DECLARE p_run_id STRING DEFAULT 's1_bqml_livepool_oriented_20260603_01';
DECLARE p_prediction_run_id STRING DEFAULT NULL;  -- NULL 表示预测来源与 p_run_id 相同
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_bqml_livepool_oriented_20260603_01';
DECLARE p_experiment_id STRING DEFAULT 'oq010_base_oriented_weekly_h5_n5_w20_pv';
DECLARE p_rebalance_frequency STRING DEFAULT 'weekly';
DECLARE p_target_holdings INT64 DEFAULT 5;
DECLARE p_label_horizon INT64 DEFAULT 5;
DECLARE p_train_start DATE DEFAULT DATE '2019-04-03';
DECLARE p_train_end DATE DEFAULT DATE '2023-12-31';
DECLARE p_valid_start DATE DEFAULT DATE '2024-01-02';
DECLARE p_valid_end DATE DEFAULT DATE '2024-12-31';
DECLARE p_test_start DATE DEFAULT DATE '2025-01-02';
DECLARE p_test_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_final_holdout_start DATE DEFAULT NULL;
DECLARE p_final_holdout_end DATE DEFAULT NULL;
DECLARE p_predict_start DATE DEFAULT DATE '2024-01-02';
DECLARE p_predict_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_rebalance_anchor_start DATE DEFAULT NULL;  -- NULL 表示按 p_predict_start 作为调仓周序锚点
DECLARE p_max_single_weight FLOAT64 DEFAULT 0.20;
DECLARE p_tail_risk_profile_id STRING DEFAULT 'diagnostic_only';
DECLARE p_market_state_version STRING DEFAULT 'market_state_v0_20260606';
DECLARE p_ledger_version STRING DEFAULT 'ledger_exec_v1';
DECLARE p_lot_size INT64 DEFAULT NULL;
DECLARE p_min_buy_lot INT64 DEFAULT NULL;
DECLARE p_initial_state_mode STRING DEFAULT 'fresh';  -- fresh / resume_from_backtest
DECLARE p_parent_backtest_id STRING DEFAULT NULL;
DECLARE p_state_as_of_date DATE DEFAULT NULL;
DECLARE p_resume_policy_id STRING DEFAULT 'cloudrun_lot100_resume_v1';
DECLARE p_calendar_end DATE;
DECLARE v_rebalance_anchor_explicit BOOL;
SET p_calendar_end = DATE_ADD(p_predict_end, INTERVAL 90 DAY);
SET p_prediction_run_id = COALESCE(p_prediction_run_id, p_run_id);
SET v_rebalance_anchor_explicit = p_rebalance_anchor_start IS NOT NULL;
SET p_rebalance_anchor_start = COALESCE(p_rebalance_anchor_start, p_predict_start);

IF p_rebalance_anchor_start > p_predict_start THEN
  RAISE USING MESSAGE = 'p_rebalance_anchor_start must be <= p_predict_start';
END IF;

IF p_rebalance_frequency NOT IN ('weekly', 'biweekly', 'monthly') THEN
  RAISE USING MESSAGE = CONCAT('unsupported p_rebalance_frequency: ', p_rebalance_frequency);
END IF;

IF p_label_horizon NOT IN (5, 10, 20) THEN
  RAISE USING MESSAGE = 'p_label_horizon must be one of 5, 10, 20';
END IF;

IF p_initial_state_mode NOT IN ('fresh', 'resume_from_backtest') THEN
  RAISE USING MESSAGE = CONCAT('unsupported p_initial_state_mode: ', p_initial_state_mode);
END IF;

IF p_tail_risk_profile_id NOT IN (
  'diagnostic_only',
  'individual_risk_guard_v0',
  'market_risk_off_v0',
  'individual_and_market_risk_guard_v0'
) THEN
  RAISE USING MESSAGE = CONCAT('unsupported p_tail_risk_profile_id: ', p_tail_risk_profile_id);
END IF;

IF p_initial_state_mode = 'resume_from_backtest' THEN
  IF p_parent_backtest_id IS NULL OR p_state_as_of_date IS NULL OR NOT v_rebalance_anchor_explicit THEN
    RAISE USING MESSAGE = 'resume QA requires p_parent_backtest_id, p_state_as_of_date, and explicit p_rebalance_anchor_start';
  END IF;
  IF p_resume_policy_id IS NULL OR p_resume_policy_id != 'cloudrun_lot100_resume_v1' THEN
    RAISE USING MESSAGE = CONCAT('unsupported p_resume_policy_id: ', COALESCE(p_resume_policy_id, 'NULL'));
  END IF;
END IF;

-- ── 训练面板唯一性 ──
ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT tp.run_id, tp.sec_code, tp.trade_date, COUNT(*) AS n
    FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
    WHERE tp.run_id = p_prediction_run_id AND tp.trade_date BETWEEN DATE '2019-01-01' AND p_predict_end
    GROUP BY tp.run_id, tp.sec_code, tp.trade_date HAVING n > 1
  )
) AS 'training panel (prediction_run_id, sec_code, trade_date) must be unique';

-- ── split 日期互斥 ──
ASSERT (
  p_train_start <= p_train_end
  AND p_valid_start <= p_valid_end
  AND p_test_start <= p_test_end
  AND p_train_end < p_valid_start
  AND p_valid_end < p_test_start
  AND (p_final_holdout_start IS NULL OR p_test_end < p_final_holdout_start)
  AND (p_final_holdout_start IS NULL OR p_final_holdout_start <= p_final_holdout_end)
) AS 'configured split date ranges must be ordered and mutually exclusive';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
  WHERE tp.run_id = p_prediction_run_id AND tp.trade_date BETWEEN DATE '2019-01-01' AND p_predict_end
    AND (
      (tp.split_tag = 'train' AND NOT tp.trade_date BETWEEN p_train_start AND p_train_end)
      OR (tp.split_tag = 'valid' AND NOT tp.trade_date BETWEEN p_valid_start AND p_valid_end)
      OR (tp.split_tag = 'test' AND NOT tp.trade_date BETWEEN p_test_start AND p_test_end)
      OR (
        tp.split_tag = 'final_holdout'
        AND (
          p_final_holdout_start IS NULL
          OR p_final_holdout_end IS NULL
          OR NOT tp.trade_date BETWEEN p_final_holdout_start AND p_final_holdout_end
        )
      )
    )
) AS 'split_tag must match configured split date ranges';

-- ── 特征列不含禁止项 ──
ASSERT (
  SELECT LOGICAL_AND(
    col NOT IN ('fwd_ret_1d','fwd_ret_5d','fwd_ret_10d','fwd_ret_20d',
                'fwd_xs_ret_1d','fwd_xs_ret_5d','fwd_xs_ret_10d','fwd_xs_ret_20d',
                'rank_pct_1d','rank_pct_5d','rank_pct_10d','rank_pct_20d',
                'label_top30_1d','label_top30_5d','label_top30_10d','label_top30_20d',
                'label_above_median_1d','label_above_median_5d',
                'label_above_median_10d','label_above_median_20d',
                'label_entry_tradable','label_valid_1d','label_valid_5d',
                'label_valid_10d','label_valid_20d','board')
    AND col NOT LIKE '%qfq%'
  )
  FROM (
    SELECT col
    FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp,
         UNNEST(tp.feature_column_list) AS col
    WHERE tp.run_id = p_prediction_run_id AND tp.trade_date BETWEEN DATE '2019-01-01' AND p_predict_end
    LIMIT 100
  )
) AS 'feature_column_list must not contain label/target/qfq/board columns';

-- ── 训练面板行数非零 ──
ASSERT (
  SELECT COUNT(*) > 0
  FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
  WHERE tp.run_id = p_prediction_run_id AND tp.trade_date BETWEEN DATE '2019-01-01' AND p_predict_end
) AS 'training panel must have rows for this prediction_run_id';

-- ── 预测表非空且 rank_raw=1 唯一 ──
ASSERT (
  SELECT COUNT(*) > 0
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  WHERE pred.run_id = p_prediction_run_id AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
) AS 'predictions must exist for this prediction_run_id';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT pred.predict_date, pred.sec_code, COUNT(*) AS n
    FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
    WHERE pred.run_id = p_prediction_run_id
      AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
    GROUP BY pred.predict_date, pred.sec_code HAVING n > 1
  )
) AS 'prediction rows must be unique per predict_date/sec_code';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT pred.predict_date, COUNT(*) AS n
    FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
    WHERE pred.run_id = p_prediction_run_id AND pred.rank_raw = 1
      AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
    GROUP BY pred.predict_date HAVING n > 1
  )
) AS 'rank_raw=1 must be unique per predict_date';

ASSERT (
  SELECT COUNTIF(pred.rank_pct < -0.0001 OR pred.rank_pct > 1.0001) = 0
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  WHERE pred.run_id = p_prediction_run_id AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
) AS 'rank_pct must be in [0,1]';

-- ── 组合权重约束 ──
ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT pt.rebalance_date, SUM(pt.target_weight) AS tw
    FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
    WHERE pt.strategy_id = p_strategy_id AND pt.run_id = p_run_id
      AND pt.rebalance_date BETWEEN p_predict_start AND p_predict_end
    GROUP BY pt.rebalance_date HAVING tw > 1.0001
  )
) AS 'portfolio weights must sum to <=1';

ASSERT (
  SELECT COUNTIF(pt.target_weight > p_max_single_weight + 0.0001) = 0
  FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
  WHERE pt.strategy_id = p_strategy_id AND pt.run_id = p_run_id
    AND pt.rebalance_date BETWEEN p_predict_start AND p_predict_end
) AS 'single stock weight must not exceed max_single_weight';

-- ── OQ-010 experiment identity and parameter QA ──
ASSERT (
  SELECT COUNT(*) = 1
    AND LOGICAL_AND(JSON_VALUE(bs.metrics_json, '$.experiment_id') = p_experiment_id)
    AND LOGICAL_AND(JSON_VALUE(bs.metrics_json, '$.prediction_run_id') = p_prediction_run_id)
    AND LOGICAL_AND(JSON_VALUE(bs.metrics_json, '$.rebalance_frequency') = p_rebalance_frequency)
    AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(bs.metrics_json, '$.target_holdings') AS INT64) = p_target_holdings)
    AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(bs.metrics_json, '$.label_horizon') AS INT64) = p_label_horizon)
    AND LOGICAL_AND(JSON_VALUE(bs.metrics_json, '$.feature_set_id') IS NOT NULL)
    AND LOGICAL_AND(COALESCE(JSON_VALUE(bs.metrics_json, '$.tail_risk_profile_id'), 'diagnostic_only') = p_tail_risk_profile_id)
    AND LOGICAL_AND(COALESCE(JSON_VALUE(bs.metrics_json, '$.market_state_version'), p_market_state_version) = p_market_state_version)
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-EXP-1: summary metrics_json must contain OQ-010 experiment identity and parameters';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT
      cand.rebalance_date,
      COUNTIF(cand.is_selected_candidate) AS selected_count
    FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
    WHERE cand.strategy_id = p_strategy_id AND cand.run_id = p_run_id
      AND cand.rebalance_date BETWEEN p_predict_start AND p_predict_end
    GROUP BY cand.rebalance_date
    HAVING selected_count > p_target_holdings
  )
) AS 'QA-EXP-2: selected candidates must not exceed p_target_holdings';

ASSERT (
  SELECT COUNTIF(pt.horizon != p_label_horizon) = 0
  FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
  WHERE pt.strategy_id = p_strategy_id AND pt.run_id = p_run_id
    AND pt.rebalance_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-EXP-3: portfolio target horizon must match p_label_horizon';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    WITH cal AS (
      SELECT cal_date
      FROM `data-aquarium.ashare_dim.dim_trade_calendar`
      WHERE exchange = 'SSE' AND is_open = 1
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
    ),
    monthly AS (
      SELECT MAX(cal_date) AS rebalance_date
      FROM cal
      GROUP BY DATE_TRUNC(cal_date, MONTH)
    ),
    expected AS (
      SELECT rebalance_date FROM weekly_ranked WHERE p_rebalance_frequency = 'weekly'
      UNION ALL
      SELECT rebalance_date FROM weekly_ranked WHERE p_rebalance_frequency = 'biweekly' AND MOD(week_idx - 1, 2) = 0
      UNION ALL
      SELECT rebalance_date FROM monthly WHERE p_rebalance_frequency = 'monthly'
    ),
    actual AS (
      SELECT DISTINCT cand.rebalance_date
      FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
      WHERE cand.strategy_id = p_strategy_id AND cand.run_id = p_run_id
        AND cand.rebalance_date BETWEEN p_predict_start AND p_predict_end
    )
    SELECT COALESCE(e.rebalance_date, a.rebalance_date) AS rebalance_date
    FROM expected AS e
    FULL OUTER JOIN actual AS a USING (rebalance_date)
    WHERE COALESCE(e.rebalance_date, a.rebalance_date) BETWEEN p_predict_start AND p_predict_end
      AND (e.rebalance_date IS NULL OR a.rebalance_date IS NULL)
  )
) AS 'QA-EXP-4: rebalance dates must match p_rebalance_frequency definition';

IF p_tail_risk_profile_id IN ('individual_risk_guard_v0', 'individual_and_market_risk_guard_v0') THEN
  ASSERT (
    SELECT COUNT(*) > 0
    FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
    WHERE cand.strategy_id = p_strategy_id
      AND cand.run_id = p_run_id
      AND cand.rebalance_date BETWEEN p_predict_start AND p_predict_end
      AND cand.filter_reason LIKE 'tail_risk:%'
  ) AS 'QA-TAIL-P1-1: individual_risk_guard_v0 should produce auditable tail_risk guard flags in this run';

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
          prev.cal_date AS prev_trade_date,
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
  ) AS 'QA-TAIL-P1-2: selected tail-risk names without prior holding must not have filled BUY trades';

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
          prev.cal_date AS prev_trade_date,
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
  ) AS 'QA-TAIL-P1-3: selected tail-risk names without prior holding must emit BUY_SKIPPED_TAIL_RISK';
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
  ) AS 'QA-TAIL-P2-1: market_risk_off profile must have auditable risk-off signal dates';

  ASSERT (
    SELECT COUNT(*) = 0
    FROM market_risk_off_exec_dates
    WHERE COALESCE(risk_off_reasons, '') = ''
  ) AS 'QA-TAIL-P2-2: risk-off dates must carry trigger evidence';

  ASSERT (
    SELECT COUNT(*) = 0
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
    JOIN market_risk_off_exec_dates AS rd
      ON rd.exec_date = bt.trade_date
    WHERE bt.backtest_id = p_backtest_id
      AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
      AND bt.side = 'BUY'
      AND bt.fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
  ) AS 'QA-TAIL-P2-3: risk-off execution dates must not have filled BUY trades';

  ASSERT (
    SELECT COUNT(*) = 0
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
    LEFT JOIN market_risk_off_exec_dates AS rd
      ON rd.exec_date = bt.trade_date
    WHERE bt.backtest_id = p_backtest_id
      AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
      AND bt.fill_status = 'BUY_SKIPPED_MARKET_RISK_OFF'
      AND rd.exec_date IS NULL
  ) AS 'QA-TAIL-P2-4: BUY_SKIPPED_MARKET_RISK_OFF must occur only on risk-off execution dates';

  ASSERT (
    SELECT COUNT(*) > 0
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
    WHERE bt.backtest_id = p_backtest_id
      AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
      AND bt.fill_status = 'BUY_SKIPPED_MARKET_RISK_OFF'
  ) AS 'QA-TAIL-P2-5: market_risk_off profile must leave skipped BUY audit rows';
END IF;

-- ── 数据侧 PIT 验证：t+1 不可买但仍入选的统计 ──
SELECT
  COUNTIF(NOT COALESCE(px_t1.can_buy_open, FALSE)) AS selected_but_next_day_not_buyable,
  COUNT(*) AS total_selected,
  SAFE_DIVIDE(COUNTIF(NOT COALESCE(px_t1.can_buy_open, FALSE)), COUNT(*)) AS not_buyable_ratio
FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS cal1
  ON cal1.cal_date = cand.rebalance_date AND cal1.exchange = 'SSE' AND cal1.is_open = 1
JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS cal2
  ON cal2.exchange = 'SSE' AND cal2.is_open = 1 AND cal2.trade_date_seq = cal1.trade_date_seq + 1
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px_t1
  ON px_t1.sec_code = cand.sec_code AND px_t1.trade_date = cal2.cal_date
  AND px_t1.trade_date BETWEEN p_predict_start AND p_calendar_end
WHERE cand.strategy_id = p_strategy_id AND cand.run_id = p_run_id
  AND cand.is_selected_candidate
  AND cand.rebalance_date BETWEEN p_predict_start AND p_predict_end;

-- ── SELL fill_status 分布（v1 ledger：FILLED 成交 vs SELL_SKIPPED_UNTRADABLE 跳过意图）──
SELECT
  bt.fill_status,
  COUNT(*) AS count
FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
WHERE bt.backtest_id = p_backtest_id AND bt.side = 'SELL'
  AND bt.trade_date BETWEEN p_predict_start AND p_calendar_end
GROUP BY bt.fill_status;

-- ── NAV 连续性：期望的开市日 vs 实际 NAV 日 ──
ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT c.cal_date AS expected_date
    FROM `data-aquarium.ashare_dim.dim_trade_calendar` AS c
    WHERE c.exchange = 'SSE' AND c.is_open = 1
      AND c.cal_date BETWEEN p_predict_start AND p_predict_end
  ) AS expected
  LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
    ON nav.trade_date = expected.expected_date
   AND nav.backtest_id = p_backtest_id
   AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
  WHERE nav.trade_date IS NULL
) AS 'NAV must cover all open market days in predict window';

-- ── NAV 唯一性：同一 (backtest_id, trade_date) 必须只有一行 ──
ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT nav.trade_date, COUNT(*) AS n
    FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
    WHERE nav.backtest_id = p_backtest_id
      AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
    GROUP BY nav.trade_date HAVING n > 1
  )
) AS 'NAV rows must be unique per (backtest_id, trade_date)';

-- ── 无负现金（long-only 不允许隐性杠杆；容忍 1 元舍入）──
ASSERT (
  SELECT COUNTIF(nav.cash_cny < -1.0) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
  WHERE nav.backtest_id = p_backtest_id
    AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
) AS 'cash_cny must not go negative (no implicit leverage)';

-- ── 总暴露不超过 1（含 0.5% 容忍，long-only 无杠杆）──
ASSERT (
  SELECT COUNTIF(nav.gross_exposure > 1.005) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
  WHERE nav.backtest_id = p_backtest_id
    AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
) AS 'gross_exposure must not exceed 1 (no leverage)';

-- ── 同一 (backtest_id, trade_date, sec_code) 持仓唯一（重叠 episode 诊断）──
ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT pos.trade_date, pos.sec_code, COUNT(*) AS n
    FROM `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
    WHERE pos.backtest_id = p_backtest_id
      AND pos.trade_date BETWEEN p_predict_start AND p_predict_end
    GROUP BY pos.trade_date, pos.sec_code HAVING n > 1
  )
) AS 'position rows must be unique per (trade_date, sec_code) — overlapping episodes would duplicate';

-- ── Ledger v1 P0: execution semantics and order-status QA ──
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(COALESCE(JSON_VALUE(bs.metrics_json, '$.ledger_version'), '') != p_ledger_version) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-LEDGER-1: summary metrics_json.ledger_version must match p_ledger_version';

IF p_ledger_version = 'ledger_exec_v1_lot100' THEN
  ASSERT (
    SELECT COUNT(*) > 0
      AND LOGICAL_AND(IFNULL(SAFE_CAST(JSON_VALUE(bs.metrics_json, '$.lot_size') AS INT64) = p_lot_size, FALSE))
      AND LOGICAL_AND(IFNULL(SAFE_CAST(JSON_VALUE(bs.metrics_json, '$.min_buy_lot') AS INT64) = p_min_buy_lot, FALSE))
      AND LOGICAL_AND(IFNULL(JSON_VALUE(bs.metrics_json, '$.buy_rounding') = 'floor_to_lot', FALSE))
      AND LOGICAL_AND(IFNULL(JSON_VALUE(bs.metrics_json, '$.sell_odd_lot_policy') = 'allow_full_exit_odd_lot', FALSE))
      AND LOGICAL_AND(IFNULL(JSON_VALUE(bs.metrics_json, '$.partial_sell_rounding') = 'floor_to_lot_keep_residual', FALSE))
      AND LOGICAL_AND(IFNULL(JSON_VALUE(bs.metrics_json, '$.cash_redistribution') = 'none_v1', FALSE))
    FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
    WHERE bs.backtest_id = p_backtest_id
  ) AS 'QA-LEDGER-1b: lot-aware summary metrics_json must record lot parameters';
END IF;

ASSERT (
  SELECT COUNT(*) > 0
    AND COUNTIF(JSON_VALUE(bs.metrics_json, '$.initial_state_mode') != p_initial_state_mode) = 0
    AND COUNTIF(JSON_VALUE(bs.metrics_json, '$.resume_policy_id') != p_resume_policy_id) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-RESUME-1: summary metrics_json must record initial_state_mode and resume_policy_id';

IF p_initial_state_mode = 'resume_from_backtest' THEN
  ASSERT (
    SELECT COUNT(*) = 1
      AND LOGICAL_AND(JSON_VALUE(bs.metrics_json, '$.ledger_version') = 'ledger_exec_v1')
    FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
    WHERE bs.backtest_id = p_parent_backtest_id
  ) AS 'QA-RESUME-2: parent summary must exist exactly once and use ledger_exec_v1';

  ASSERT (
    SELECT COUNT(*) = 1
      AND LOGICAL_AND(nav.cash_cny IS NOT NULL)
      AND LOGICAL_AND(nav.net_value_cny IS NOT NULL AND nav.net_value_cny > 0)
    FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
    WHERE nav.backtest_id = p_parent_backtest_id
      AND nav.trade_date = p_state_as_of_date
  ) AS 'QA-RESUME-3: parent NAV state must exist exactly once on state_as_of_date';

  ASSERT (
    SELECT MIN(cal.cal_date) = p_predict_start
    FROM `data-aquarium.ashare_dim.dim_trade_calendar` AS cal
    WHERE cal.exchange = 'SSE'
      AND cal.is_open = 1
      AND cal.cal_date > p_state_as_of_date
  ) AS 'QA-RESUME-4: resume p_predict_start must be the next open date after state_as_of_date';

  ASSERT (
    SELECT COUNT(*) > 0
      AND COUNTIF(
        JSON_VALUE(bs.metrics_json, '$.parent_backtest_id') != p_parent_backtest_id
        OR JSON_VALUE(bs.metrics_json, '$.state_as_of_date') != CAST(p_state_as_of_date AS STRING)
        OR JSON_VALUE(bs.metrics_json, '$.is_resumed_backtest') != 'true'
      ) = 0
    FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
    WHERE bs.backtest_id = p_backtest_id
  ) AS 'QA-RESUME-5: resumed summary must record parent backtest, state date and is_resumed_backtest=true';

  ASSERT (
    SELECT COUNT(*) = 1
      AND LOGICAL_AND(nav.daily_return IS NOT NULL)
    FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
    WHERE nav.backtest_id = p_backtest_id
      AND nav.trade_date = p_predict_start
  ) AS 'QA-RESUME-6: first resumed NAV day must have daily_return anchored to parent state NAV';
END IF;

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
      'SKIPPED_CASH_INSUFFICIENT',
      'SKIPPED_MIN_NOTIONAL',
      'NOOP_ALREADY_TARGET'
    )
) AS 'QA-LEDGER-2: trade fill_status must be in ledger_exec_v1 allowed status set';

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
      'SKIPPED_CASH_INSUFFICIENT',
      'SKIPPED_MIN_NOTIONAL',
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
) AS 'QA-LEDGER-3: skipped/cancel/noop statuses must have zero fill, turnover, fee, tax, slippage and cash effect';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT bt.trade_date, bt.sec_code, COUNT(DISTINCT bt.side) AS filled_sides
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
    WHERE bt.backtest_id = p_backtest_id
      AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
      AND bt.fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
    GROUP BY bt.trade_date, bt.sec_code
    HAVING filled_sides > 1
  )
) AS 'QA-LEDGER-4: same stock cannot have both filled BUY and filled SELL on one execution_date after netting';

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
    AND bt.fill_status IN ('SELL_SKIPPED_UNTRADABLE', 'PENDING_SELL_CARRY')
    AND COALESCE(pos.shares, 0) <= 0
) AS 'QA-LEDGER-5: skipped/carry SELL must not reduce the position on that date';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    WITH signal_exec AS (
      SELECT nxt.cal_date AS exec_date
      FROM (
        SELECT DISTINCT pt.rebalance_date
        FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
        WHERE pt.strategy_id = p_strategy_id AND pt.run_id = p_run_id
          AND pt.rebalance_date BETWEEN p_predict_start AND p_predict_end
      ) AS rd
      JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS c
        ON c.exchange = 'SSE' AND c.is_open = 1 AND c.cal_date = rd.rebalance_date
      JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS nxt
        ON nxt.exchange = 'SSE' AND nxt.is_open = 1 AND nxt.trade_date_seq = c.trade_date_seq + 1
      WHERE nxt.cal_date BETWEEN p_predict_start AND p_predict_end
    )
    SELECT bt.trade_date, bt.sec_code
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
    JOIN signal_exec AS se ON se.exec_date = bt.trade_date
    WHERE bt.backtest_id = p_backtest_id
      AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
      AND bt.fill_status = 'PENDING_SELL_CARRY'
  )
) AS 'QA-LEDGER-6: PENDING_SELL_CARRY must only be emitted on non-rebalance retry days';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    WITH open_days AS (
      SELECT
        c.cal_date AS trade_date,
        LEAD(c.cal_date) OVER (ORDER BY c.cal_date) AS next_trade_date
      FROM `data-aquarium.ashare_dim.dim_trade_calendar` AS c
      WHERE c.exchange = 'SSE' AND c.is_open = 1
        AND c.cal_date BETWEEN p_predict_start AND p_predict_end
    ),
    skipped AS (
      SELECT bt.trade_date, bt.sec_code, od.next_trade_date
      FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
      JOIN open_days AS od ON od.trade_date = bt.trade_date
      JOIN `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
        ON pos.backtest_id = bt.backtest_id
       AND pos.trade_date = bt.trade_date
       AND pos.sec_code = bt.sec_code
       AND pos.trade_date BETWEEN p_predict_start AND p_predict_end
      WHERE bt.backtest_id = p_backtest_id
        AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
        AND bt.fill_status IN ('SELL_SKIPPED_UNTRADABLE', 'PENDING_SELL_CARRY')
        AND od.next_trade_date IS NOT NULL
        AND pos.shares > 0
    )
    SELECT s.trade_date, s.sec_code, s.next_trade_date
    FROM skipped AS s
    LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS nt
      ON nt.backtest_id = p_backtest_id
     AND nt.trade_date = s.next_trade_date
     AND nt.sec_code = s.sec_code
     AND nt.trade_date BETWEEN p_predict_start AND p_predict_end
     AND nt.fill_status IN ('FILLED', 'SELL_SKIPPED_UNTRADABLE', 'SELL_SKIPPED_BELOW_LOT_PARTIAL', 'PENDING_SELL_CARRY', 'CANCELLED_BY_NETTING', 'NOOP_ALREADY_TARGET')
    WHERE nt.sec_code IS NULL
  )
) AS 'QA-LEDGER-7: pending sell must be retried, filled, cancelled or marked noop on the next open day';

-- ── selected model 唯一（run-scoped）──
ASSERT (
  SELECT COUNT(*) = 1
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_prediction_run_id
    AND reg.model_uri IS NOT NULL
) AS 'exactly one prediction-run-scoped selected model must exist';

-- ── selected model 必须有 score_orientation（identity 或 reverse_probability）──
ASSERT (
  SELECT COUNT(*) = 1 AND LOGICAL_AND(
    JSON_VALUE(reg.metrics_json, '$.score_orientation') IN ('identity', 'reverse_probability')
  )
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_prediction_run_id
) AS 'QA-ORIENT-1: selected model must have score_orientation = identity or reverse_probability';

-- ── selected model 必须有 score_source、orientation 诊断字段和 bucket lift 证据 ──
ASSERT (
  SELECT LOGICAL_AND(
    JSON_VALUE(reg.metrics_json, '$.score_source') IS NOT NULL
    AND JSON_VALUE(reg.metrics_json, '$.raw_valid_rank_ic_mean') IS NOT NULL
    AND JSON_VALUE(reg.metrics_json, '$.oriented_valid_rank_ic_mean') IS NOT NULL
    AND JSON_VALUE(reg.metrics_json, '$.raw_valid_top_minus_bottom') IS NOT NULL
    AND JSON_VALUE(reg.metrics_json, '$.reversed_valid_top_minus_bottom') IS NOT NULL
    AND JSON_VALUE(reg.metrics_json, '$.orientation_decision_reason') IS NOT NULL
    AND JSON_VALUE(reg.metrics_json, '$.orientation_decision_split') = 'valid'
  )
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_prediction_run_id
) AS 'QA-ORIENT-2: selected model must have score_source, raw/oriented rank_ic, bucket lift, decision_split=valid, and decision reason';

-- ── prediction 表的 score_orientation 必须和 registry 一致 ──
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(
    pred.score_orientation != JSON_VALUE(reg.metrics_json, '$.score_orientation')
  ) = 0
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  JOIN `data-aquarium.ashare_ads.ads_model_registry` AS reg
    ON pred.model_id = reg.model_id
  WHERE pred.run_id = p_prediction_run_id
    AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
    AND reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_prediction_run_id
) AS 'QA-ORIENT-3: prediction score_orientation must match registry';

-- ── score 与 raw_score 的关系必须和 score_orientation 一致 ──
ASSERT (
  SELECT COUNTIF(
    CASE
      WHEN pred.score_orientation = 'identity'
        THEN ABS(pred.score - pred.raw_score) > 1e-6
      WHEN pred.score_orientation = 'reverse_probability'
        THEN ABS(pred.score - (1.0 - pred.raw_score)) > 1e-6
      ELSE TRUE
    END
  ) = 0
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  WHERE pred.run_id = p_prediction_run_id
    AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-ORIENT-4: score must equal raw_score (identity) or 1-raw_score (reverse_probability)';

-- ── 回测 summary 存在且有 metrics_json ──
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(bs.metrics_json IS NOT NULL) > 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'backtest summary must exist with metrics_json';

-- ── 复合年化收益口径：return_period_count = NAV 有效交易日数 - 1，旧 annual_return/sharpe 保留 legacy ──
ASSERT (
  WITH nav_count AS (
    SELECT COUNT(*) AS nav_day_count
    FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
    WHERE nav.backtest_id = p_backtest_id
      AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
  ),
  summary AS (
    SELECT
      bs.compound_annual_return,
      bs.return_period_count,
      bs.annualization_target_period_count,
      bs.annualization_method,
      bs.total_return,
      bs.metrics_json,
      GREATEST(nav_count.nav_day_count - 1, 0) AS expected_return_period_count
    FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
    CROSS JOIN nav_count
    WHERE bs.backtest_id = p_backtest_id
  )
  SELECT
    COUNT(*) = 1
    AND LOGICAL_AND(compound_annual_return IS NOT NULL)
    AND LOGICAL_AND(return_period_count = expected_return_period_count)
    AND LOGICAL_AND(return_period_count > 0)
    AND LOGICAL_AND(annualization_target_period_count = 252)
    AND LOGICAL_AND(annualization_method = 'compound')
    AND LOGICAL_AND(JSON_VALUE(metrics_json, '$.annualization.method') = 'compound')
    AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(metrics_json, '$.annualization.target_period_count') AS INT64) = 252)
    AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(metrics_json, '$.annualization.return_period_count') AS INT64) = return_period_count)
    AND LOGICAL_AND(ABS(
      (CASE
        WHEN total_return IS NULL OR total_return < -1.0 OR return_period_count <= 0 THEN NULL
        ELSE POW(1.0 + total_return, 252.0 / return_period_count) - 1.0
      END) - compound_annual_return
    ) <= 1e-9)
  FROM summary
) AS 'QA-ANNUALIZATION-1: compound_annual_return must match total_return annualized by NAV day count minus one';

-- ── 报告已产出（render_report.py 必须在本 QA 之前运行），且 report_uri 口径真实可信 ──
-- 见 README：执行顺序为 01-09 → render_report.py → 10。
-- 模式感知：render 必须写 report_upload_status 与 local_report_path；
--   - uploaded：必须有真实 GCS report_uri；
--   - skipped（local-only）：必须没有 report_uri（避免把不存在的 gs:// 当成已产出）。
ASSERT (
  SELECT COUNT(*) > 0 AND LOGICAL_AND(
    JSON_VALUE(bs.metrics_json, '$.report_upload_status') IS NOT NULL
    AND JSON_VALUE(bs.metrics_json, '$.local_report_path') IS NOT NULL
    AND (
      (JSON_VALUE(bs.metrics_json, '$.report_upload_status') = 'uploaded'
        AND JSON_VALUE(bs.metrics_json, '$.report_uri') IS NOT NULL)
      OR (JSON_VALUE(bs.metrics_json, '$.report_upload_status') = 'skipped'
        AND JSON_VALUE(bs.metrics_json, '$.report_uri') IS NULL)
    )
  )
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'report must be rendered: report_upload_status + local_report_path set, and report_uri present iff uploaded (run render_report.py before this QA)';

-- ============================================================
-- OQ-010 成本 profile QA
-- ============================================================
-- QA-COST-1: cost_profile_id 正确
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(JSON_VALUE(bs.metrics_json, '$.cost_profile_id') != 'cn_a_share_wanyi_no_min_slip5_v20260602') = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-COST-1: metrics_json.cost_profile_id must be cn_a_share_wanyi_no_min_slip5_v20260602';

-- QA-COST-2: commission_bps = 1.0
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(ABS(CAST(JSON_VALUE(bs.metrics_json, '$.commission_bps') AS FLOAT64) - 1.0) > 1e-6) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-COST-2: metrics_json.commission_bps must be 1.0';

-- QA-COST-3: min_commission_cny = 0.0
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(ABS(CAST(JSON_VALUE(bs.metrics_json, '$.min_commission_cny') AS FLOAT64) - 0.0) > 1e-6) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-COST-3: metrics_json.min_commission_cny must be 0.0';

-- QA-COST-4: stamp_tax_buy_bps = 0.0, stamp_tax_sell_bps = 5.0
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(
    ABS(CAST(JSON_VALUE(bs.metrics_json, '$.stamp_tax_buy_bps') AS FLOAT64) - 0.0) > 1e-6
    OR ABS(CAST(JSON_VALUE(bs.metrics_json, '$.stamp_tax_sell_bps') AS FLOAT64) - 5.0) > 1e-6
  ) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-COST-4: metrics_json.stamp_tax_buy_bps must be 0.0 and stamp_tax_sell_bps must be 5.0';

-- QA-COST-5: slippage_buy_bps = 5.0, slippage_sell_bps = 5.0
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(
    ABS(CAST(JSON_VALUE(bs.metrics_json, '$.slippage_buy_bps') AS FLOAT64) - 5.0) > 1e-6
    OR ABS(CAST(JSON_VALUE(bs.metrics_json, '$.slippage_sell_bps') AS FLOAT64) - 5.0) > 1e-6
  ) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-COST-5: metrics_json.slippage_buy_bps and slippage_sell_bps must be 5.0';

-- QA-COST-6: fill_price 精确匹配滑点公式（带小容差）
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(mismatch) = 0
  FROM (
    SELECT
      bt.side,
      bt.fill_price,
      px.open AS exec_open,
      CASE
        WHEN bt.side = 'BUY' THEN ABS(SAFE_DIVIDE(bt.fill_price, px.open) - 1.0005) > 1e-4
        WHEN bt.side = 'SELL' THEN ABS(SAFE_DIVIDE(bt.fill_price, px.open) - 0.9995) > 1e-4
        ELSE FALSE
      END AS mismatch
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
    JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
      ON px.sec_code = bt.sec_code AND px.trade_date = bt.trade_date
    WHERE bt.backtest_id = p_backtest_id
      AND bt.fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
      AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
  )
) AS 'QA-COST-6: fill_price must match exec_open * (1 +/- slippage/10000) exactly (BUY +5bps, SELL -5bps) and join must be non-empty';

-- QA-COST-6d: join 行数对账，确保没有 filled trade 被 inner join 丢掉
ASSERT (
  SELECT trade_cnt = joined_cnt AND trade_cnt > 0
  FROM (
    SELECT
      (SELECT COUNT(*) FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily`
       WHERE backtest_id = p_backtest_id AND fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
         AND trade_date BETWEEN p_predict_start AND p_predict_end) AS trade_cnt,
      (SELECT COUNT(*)
       FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
       JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
         ON px.sec_code = bt.sec_code AND px.trade_date = bt.trade_date
       WHERE bt.backtest_id = p_backtest_id AND bt.fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
         AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
         AND px.open IS NOT NULL) AS joined_cnt
  )
) AS 'QA-COST-6d: filled trade count must equal joined count with px.open IS NOT NULL (no rows dropped by inner join)';

-- QA-COST-7: fee_cny 只含佣金和印花税，不含滑点
-- BUY: fee/turnover ~ 1 bps (commission only); SELL: fee/turnover ~ 6 bps (commission + stamp_tax)
ASSERT (
  SELECT COUNTIF(ABS(SAFE_DIVIDE(fee_cny, turnover_cny) - 1.0/10000.0) > 1e-6) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily`
  WHERE backtest_id = p_backtest_id AND side = 'BUY' AND fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
    AND turnover_cny > 1.0 AND trade_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-COST-7a: BUY fee_cny/turnover must ~ 1 bps (commission only, no slippage in fee)';

ASSERT (
  SELECT COUNTIF(ABS(SAFE_DIVIDE(fee_cny, turnover_cny) - 6.0/10000.0) > 1e-6) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily`
  WHERE backtest_id = p_backtest_id AND side = 'SELL' AND fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
    AND turnover_cny > 1.0 AND trade_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-COST-7b: SELL fee_cny/turnover must ~ 6 bps (commission + stamp_tax, no slippage in fee)';

-- QA-COST-8: turnover/cash_effect/slippage 公式对账
-- BUY: cash_effect = -(turnover + fee); SELL: cash_effect = turnover - fee
ASSERT (
  SELECT COUNTIF(mismatch) = 0
  FROM (
    SELECT ABS(bt.cash_effect_cny + bt.turnover_cny + bt.fee_cny) > 1e-3 AS mismatch
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
    WHERE bt.backtest_id = p_backtest_id AND bt.side = 'BUY' AND bt.fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
      AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
  )
) AS 'QA-COST-8a: BUY cash_effect_cny must equal -(turnover_cny + fee_cny)';

ASSERT (
  SELECT COUNTIF(mismatch) = 0
  FROM (
    SELECT ABS(bt.cash_effect_cny - bt.turnover_cny + bt.fee_cny) > 1e-3 AS mismatch
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
    WHERE bt.backtest_id = p_backtest_id AND bt.side = 'SELL' AND bt.fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
      AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
  )
) AS 'QA-COST-8b: SELL cash_effect_cny must equal turnover_cny - fee_cny';

-- QA-COST-8c: slippage_cny 计算正确（从 trade 表直接验证公式）
-- BUY: slippage = turnover * 5 / 10005; SELL: slippage = turnover * 5 / 9995
ASSERT (
  SELECT COUNTIF(mismatch) = 0
  FROM (
    SELECT
      CASE
        WHEN side = 'BUY' THEN ABS(slippage_cny - turnover_cny * 5.0 / 10005.0) > 1e-3
        WHEN side = 'SELL' THEN ABS(slippage_cny - turnover_cny * 5.0 / 9995.0) > 1e-3
        ELSE FALSE
      END AS mismatch
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily`
    WHERE backtest_id = p_backtest_id AND fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
      AND trade_date BETWEEN p_predict_start AND p_predict_end
  )
) AS 'QA-COST-8c: slippage_cny must match turnover * slippage / (10000 +/- slippage)';

-- ============================================================
-- PRD-20260602-03 策略 1 中文报告与归因分析 QA
-- ============================================================

-- QA-REPORT-1: 评估主基准必须是上证指数 (000001.SH)
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(bs.benchmark_sec_code != '000001.SH') = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-REPORT-1: benchmark_sec_code in performance_summary must be 000001.SH (assessment benchmark)';

-- QA-REPORT-2: NAV 表的 benchmark_sec_code 也必须是 000001.SH
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(nav.benchmark_sec_code != '000001.SH') = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
  WHERE nav.backtest_id = p_backtest_id
    AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-REPORT-2: benchmark_sec_code in nav_daily must be 000001.SH';

-- QA-REPORT-3: report_version 已写入 metrics_json（render_report.py 回写）
ASSERT (
  SELECT COUNT(*) > 0
    AND COUNTIF(JSON_VALUE(bs.metrics_json, '$.report_version') IS NULL) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-REPORT-3: metrics_json.report_version must be set by render_report.py';

-- QA-REPORT-4: diagnosis_triggered 已写入 metrics_json（render 或 09 写入）
ASSERT (
  SELECT COUNT(*) > 0
    AND COUNTIF(JSON_VALUE(bs.metrics_json, '$.diagnosis_triggered') IS NULL) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-REPORT-4: metrics_json.diagnosis_triggered must be set';

-- QA-REPORT-5: ai_analysis_status 已写入 metrics_json（render 回写）
ASSERT (
  SELECT COUNT(*) > 0
    AND COUNTIF(JSON_VALUE(bs.metrics_json, '$.ai_analysis_status') IS NULL) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-REPORT-5: metrics_json.ai_analysis_status must be set by render_report.py';

-- QA-REPORT-6: artifact_manifest 已写入（render 回写），且包含必需 artifact
-- 用 JSON_QUERY 检查 object（JSON_VALUE 只适合 scalar）
ASSERT (
  SELECT COUNT(*) > 0
    AND COUNTIF(JSON_QUERY(bs.metrics_json, '$.artifact_manifest') IS NULL) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-REPORT-6: metrics_json.artifact_manifest must be a JSON object set by render_report.py';

-- QA-REPORT-7: artifact_manifest 包含必需文件
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(missing) = 0
  FROM (
    SELECT
      JSON_VALUE(JSON_QUERY(bs.metrics_json, '$.artifact_manifest'), '$."report.md"') IS NULL
      OR JSON_VALUE(JSON_QUERY(bs.metrics_json, '$.artifact_manifest'), '$."report.html"') IS NULL
      OR JSON_VALUE(JSON_QUERY(bs.metrics_json, '$.artifact_manifest'), '$."benchmark_nav.csv"') IS NULL
      OR JSON_VALUE(JSON_QUERY(bs.metrics_json, '$.artifact_manifest'), '$."diagnosis_evidence.json"') IS NULL
      OR JSON_VALUE(JSON_QUERY(bs.metrics_json, '$.artifact_manifest'), '$."ai_analysis.json"') IS NULL
      AS missing
    FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
    WHERE bs.backtest_id = p_backtest_id
  )
) AS 'QA-REPORT-7: artifact_manifest must contain report.md, report.html, benchmark_nav.csv, diagnosis_evidence.json, ai_analysis.json';
