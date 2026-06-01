-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 10: 运行后 QA 断言。

-- ── 运行参数 ──
DECLARE run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE backtest_id STRING DEFAULT 'bt_s1_bqml_20260601_01';
DECLARE predict_start_date DATE DEFAULT DATE '2024-01-01';
DECLARE predict_end_date DATE DEFAULT DATE '2025-12-31';
DECLARE max_single_weight FLOAT64 DEFAULT 0.20;

-- ── 训练面板唯一性 ──
ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT run_id, sec_code, trade_date, COUNT(*) AS n
    FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
    WHERE run_id = run_id
      AND trade_date BETWEEN DATE '2019-01-01' AND predict_end_date
    GROUP BY run_id, sec_code, trade_date
    HAVING n > 1
  )
) AS 'training panel (run_id, sec_code, trade_date) must be unique';

-- ── train/valid/test 日期互斥且有序 ──
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
  WHERE run_id = run_id
    AND trade_date BETWEEN DATE '2019-01-01' AND predict_end_date
    AND (
      (split_tag = 'train' AND trade_date >= DATE '2024-01-01')
      OR (split_tag = 'valid' AND (trade_date < DATE '2024-01-01' OR trade_date >= DATE '2025-01-01'))
      OR (split_tag = 'test' AND (trade_date < DATE '2025-01-01' OR trade_date >= DATE '2026-01-01'))
    )
) AS 'split_tag date ranges must be mutually exclusive and ordered';

-- ── 模型特征不含禁止列 ──
ASSERT (
  SELECT LOGICAL_AND(
    col NOT IN ('fwd_ret_1d','fwd_ret_5d','fwd_ret_10d','fwd_ret_20d',
                'fwd_xs_ret_5d','rank_pct_5d','label_top30_5d','label_above_median_5d',
                'label_entry_tradable','label_valid_1d','label_valid_5d',
                'label_valid_10d','label_valid_20d','board')
    AND col NOT LIKE '%qfq%'
  )
  FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`,
       UNNEST(feature_column_list) AS col
  WHERE run_id = run_id
    AND trade_date BETWEEN DATE '2019-01-01' AND predict_end_date
  LIMIT 1
) AS 'feature_column_list must not contain label/target/qfq/board columns';

-- ── 预测日 rank_raw=1 唯一，rank_pct 在 [0,1] ──
ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT predict_date, COUNT(*) AS n
    FROM `data-aquarium.ashare_ads.ads_model_prediction_daily`
    WHERE run_id = run_id AND rank_raw = 1
      AND predict_date BETWEEN predict_start_date AND predict_end_date
    GROUP BY predict_date
    HAVING n > 1
  )
) AS 'rank_raw=1 must be unique per predict_date';

ASSERT (
  SELECT COUNTIF(rank_pct < 0 OR rank_pct > 1.0001) = 0
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily`
  WHERE run_id = run_id
    AND predict_date BETWEEN predict_start_date AND predict_end_date
) AS 'rank_pct must be in [0,1]';

-- ── 组合权重约束 ──
ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT rebalance_date, SUM(target_weight) AS total_w
    FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily`
    WHERE strategy_id = strategy_id AND run_id = run_id
      AND rebalance_date BETWEEN predict_start_date AND predict_end_date
    GROUP BY rebalance_date
    HAVING total_w > 1.0001
  )
) AS 'portfolio target weights must sum to <=1 per rebalance_date';

ASSERT (
  SELECT COUNTIF(target_weight > max_single_weight + 0.0001) = 0
  FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily`
  WHERE strategy_id = strategy_id AND run_id = run_id
    AND rebalance_date BETWEEN predict_start_date AND predict_end_date
) AS 'single stock weight must not exceed max_single_weight';

-- ── 数据侧 PIT 验证：t+1 不可买但仍入选的样本统计 ──
-- 非零不直接 FAIL；生成统计供人工审核
CREATE TEMP TABLE pit_check AS
SELECT
  cand.rebalance_date,
  cand.sec_code,
  cand.is_selected_candidate,
  px.can_buy_open AS next_day_can_buy
FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS cal
  ON cal.cal_date = cand.rebalance_date AND cal.exchange = 'SSE' AND cal.is_open = 1
JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS cal2
  ON cal2.exchange = 'SSE' AND cal2.is_open = 1 AND cal2.trade_date_seq = cal.trade_date_seq + 1
LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
  ON px.sec_code = cand.sec_code AND px.trade_date = cal2.cal_date
  AND px.trade_date BETWEEN predict_start_date AND predict_end_date
WHERE cand.strategy_id = strategy_id AND cand.run_id = run_id
  AND cand.is_selected_candidate
  AND cand.rebalance_date BETWEEN predict_start_date AND predict_end_date;

SELECT
  COUNTIF(NOT COALESCE(next_day_can_buy, FALSE)) AS selected_but_next_day_not_buyable,
  COUNT(*) AS total_selected,
  SAFE_DIVIDE(COUNTIF(NOT COALESCE(next_day_can_buy, FALSE)), COUNT(*)) AS not_buyable_ratio
FROM pit_check;

-- ── NAV 连续性 ──
ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT trade_date,
           LEAD(trade_date) OVER (ORDER BY trade_date) AS next_date
    FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily`
    WHERE backtest_id = backtest_id
      AND trade_date BETWEEN predict_start_date AND predict_end_date
  )
  JOIN `data-aquarium.ashare_dim.dim_trade_calendar` AS c
    ON c.cal_date = trade_date AND c.exchange = 'SSE' AND c.is_open = 1
  WHERE next_date IS NOT NULL
    AND next_date != (
      SELECT MIN(c2.cal_date)
      FROM `data-aquarium.ashare_dim.dim_trade_calendar` AS c2
      WHERE c2.exchange = 'SSE' AND c2.is_open = 1 AND c2.cal_date > trade_date
    )
) AS 'NAV must cover consecutive open market days without gaps';

-- ── selected model 有唯一 model_uri ──
ASSERT (
  SELECT COUNT(*) = 1
  FROM `data-aquarium.ashare_ads.ads_model_registry`
  WHERE strategy_id = strategy_id AND status = 'selected'
    AND model_uri IS NOT NULL
) AS 'exactly one selected model must exist with a model_uri';

-- ── 回测 summary 存在 ──
ASSERT (
  SELECT COUNT(*) > 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary`
  WHERE backtest_id = backtest_id
) AS 'backtest performance summary must exist for this backtest_id';
