-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 10: 运行后 QA 断言（全部用 p_ 前缀变量，别名限定表列）。

DECLARE p_run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_bqml_20260601_01';
DECLARE p_predict_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_predict_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_max_single_weight FLOAT64 DEFAULT 0.20;
DECLARE p_calendar_end DATE;
SET p_calendar_end = DATE_ADD(p_predict_end, INTERVAL 90 DAY);

-- ── 训练面板唯一性 ──
ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT tp.run_id, tp.sec_code, tp.trade_date, COUNT(*) AS n
    FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
    WHERE tp.run_id = p_run_id AND tp.trade_date BETWEEN DATE '2019-01-01' AND p_predict_end
    GROUP BY tp.run_id, tp.sec_code, tp.trade_date HAVING n > 1
  )
) AS 'training panel (run_id, sec_code, trade_date) must be unique';

-- ── split 日期互斥 ──
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
  WHERE tp.run_id = p_run_id AND tp.trade_date BETWEEN DATE '2019-01-01' AND p_predict_end
    AND (
      (tp.split_tag = 'train' AND tp.trade_date >= DATE '2024-01-01')
      OR (tp.split_tag = 'valid' AND (tp.trade_date < DATE '2024-01-01' OR tp.trade_date >= DATE '2025-01-01'))
      OR (tp.split_tag = 'test' AND (tp.trade_date < DATE '2025-01-01' OR tp.trade_date >= DATE '2026-01-01'))
    )
) AS 'split_tag date ranges must be mutually exclusive';

-- ── 特征列不含禁止项 ──
ASSERT (
  SELECT LOGICAL_AND(
    col NOT IN ('fwd_ret_1d','fwd_ret_5d','fwd_ret_10d','fwd_ret_20d',
                'fwd_xs_ret_5d','rank_pct_5d','label_top30_5d','label_above_median_5d',
                'label_entry_tradable','label_valid_1d','label_valid_5d',
                'label_valid_10d','label_valid_20d','board')
    AND col NOT LIKE '%qfq%'
  )
  FROM (
    SELECT col
    FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp,
         UNNEST(tp.feature_column_list) AS col
    WHERE tp.run_id = p_run_id AND tp.trade_date BETWEEN DATE '2019-01-01' AND p_predict_end
    LIMIT 100
  )
) AS 'feature_column_list must not contain label/target/qfq/board columns';

-- ── 训练面板行数非零 ──
ASSERT (
  SELECT COUNT(*) > 0
  FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
  WHERE tp.run_id = p_run_id AND tp.trade_date BETWEEN DATE '2019-01-01' AND p_predict_end
) AS 'training panel must have rows for this run_id';

-- ── 预测表非空且 rank_raw=1 唯一 ──
ASSERT (
  SELECT COUNT(*) > 0
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  WHERE pred.run_id = p_run_id AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
) AS 'predictions must exist for this run_id';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT pred.predict_date, COUNT(*) AS n
    FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
    WHERE pred.run_id = p_run_id AND pred.rank_raw = 1
      AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
    GROUP BY pred.predict_date HAVING n > 1
  )
) AS 'rank_raw=1 must be unique per predict_date';

ASSERT (
  SELECT COUNTIF(pred.rank_pct < -0.0001 OR pred.rank_pct > 1.0001) = 0
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  WHERE pred.run_id = p_run_id AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
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

-- ── 卖出顺延统计 ──
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

-- ── selected model 唯一（run-scoped）──
ASSERT (
  SELECT COUNT(*) = 1
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
    AND reg.model_uri IS NOT NULL
) AS 'exactly one run-scoped selected model must exist';

-- ── 回测 summary 存在且有 metrics_json ──
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(bs.metrics_json IS NOT NULL) > 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'backtest summary must exist with metrics_json';

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
