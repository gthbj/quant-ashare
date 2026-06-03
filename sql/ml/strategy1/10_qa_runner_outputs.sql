-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 10: 运行后 QA 断言（全部用 p_ 前缀变量，别名限定表列）。

DECLARE p_run_id STRING DEFAULT 's1_bqml_livepool_oriented_20260603_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_bqml_livepool_oriented_20260603_01';
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

-- ── selected model 唯一（run-scoped）──
ASSERT (
  SELECT COUNT(*) = 1
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
    AND reg.model_uri IS NOT NULL
) AS 'exactly one run-scoped selected model must exist';

-- ── selected model 必须有 score_orientation（identity 或 reverse_probability）──
ASSERT (
  SELECT COUNT(*) = 1 AND LOGICAL_AND(
    JSON_VALUE(reg.metrics_json, '$.score_orientation') IN ('identity', 'reverse_probability')
  )
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
) AS 'QA-ORIENT-1: selected model must have score_orientation = identity or reverse_probability';

-- ── selected model 必须有 score_source 和 orientation 诊断字段 ──
ASSERT (
  SELECT LOGICAL_AND(
    JSON_VALUE(reg.metrics_json, '$.score_source') IS NOT NULL
    AND JSON_VALUE(reg.metrics_json, '$.raw_valid_rank_ic_mean') IS NOT NULL
    AND JSON_VALUE(reg.metrics_json, '$.oriented_valid_rank_ic_mean') IS NOT NULL
    AND JSON_VALUE(reg.metrics_json, '$.orientation_decision_reason') IS NOT NULL
  )
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
) AS 'QA-ORIENT-2: selected model must have score_source, raw/oriented rank_ic, and decision reason';

-- ── prediction 表的 score_orientation 必须和 registry 一致 ──
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(
    pred.score_orientation != JSON_VALUE(reg.metrics_json, '$.score_orientation')
  ) = 0
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  JOIN `data-aquarium.ashare_ads.ads_model_registry` AS reg
    ON pred.model_id = reg.model_id
  WHERE pred.run_id = p_run_id
    AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
    AND reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
) AS 'QA-ORIENT-3: prediction score_orientation must match registry';

-- ── score 与 raw_score 的关系必须和 score_orientation 一致 ──
ASSERT (
  SELECT COUNTIF(
    CASE
      WHEN pred.score_orientation = 'identity'
        THEN ABS(pred.score - pred.raw_score) > 1e-9
      WHEN pred.score_orientation = 'reverse_probability'
        THEN ABS(pred.score - (1.0 - pred.raw_score)) > 1e-9
      ELSE TRUE
    END
  ) = 0
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  WHERE pred.run_id = p_run_id
    AND pred.predict_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-ORIENT-4: score must equal raw_score (identity) or 1-raw_score (reverse_probability)';

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
      AND bt.fill_status = 'FILLED'
      AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
  )
) AS 'QA-COST-6: fill_price must match exec_open * (1 +/- slippage/10000) exactly (BUY +5bps, SELL -5bps) and join must be non-empty';

-- QA-COST-6d: join 行数对账，确保没有 filled trade 被 inner join 丢掉
ASSERT (
  SELECT trade_cnt = joined_cnt AND trade_cnt > 0
  FROM (
    SELECT
      (SELECT COUNT(*) FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily`
       WHERE backtest_id = p_backtest_id AND fill_status = 'FILLED'
         AND trade_date BETWEEN p_predict_start AND p_predict_end) AS trade_cnt,
      (SELECT COUNT(*)
       FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
       JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
         ON px.sec_code = bt.sec_code AND px.trade_date = bt.trade_date
       WHERE bt.backtest_id = p_backtest_id AND bt.fill_status = 'FILLED'
         AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
         AND px.open IS NOT NULL) AS joined_cnt
  )
) AS 'QA-COST-6d: filled trade count must equal joined count with px.open IS NOT NULL (no rows dropped by inner join)';

-- QA-COST-7: fee_cny 只含佣金和印花税，不含滑点
-- BUY: fee/turnover ~ 1 bps (commission only); SELL: fee/turnover ~ 6 bps (commission + stamp_tax)
ASSERT (
  SELECT COUNTIF(ABS(SAFE_DIVIDE(fee_cny, turnover_cny) - 1.0/10000.0) > 1e-6) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily`
  WHERE backtest_id = p_backtest_id AND side = 'BUY' AND fill_status = 'FILLED'
    AND turnover_cny > 1.0 AND trade_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-COST-7a: BUY fee_cny/turnover must ~ 1 bps (commission only, no slippage in fee)';

ASSERT (
  SELECT COUNTIF(ABS(SAFE_DIVIDE(fee_cny, turnover_cny) - 6.0/10000.0) > 1e-6) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily`
  WHERE backtest_id = p_backtest_id AND side = 'SELL' AND fill_status = 'FILLED'
    AND turnover_cny > 1.0 AND trade_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-COST-7b: SELL fee_cny/turnover must ~ 6 bps (commission + stamp_tax, no slippage in fee)';

-- QA-COST-8: turnover/cash_effect/slippage 公式对账
-- BUY: cash_effect = -(turnover + fee); SELL: cash_effect = turnover - fee
ASSERT (
  SELECT COUNTIF(mismatch) = 0
  FROM (
    SELECT ABS(bt.cash_effect_cny + bt.turnover_cny + bt.fee_cny) > 1e-3 AS mismatch
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
    WHERE bt.backtest_id = p_backtest_id AND bt.side = 'BUY' AND bt.fill_status = 'FILLED'
      AND bt.trade_date BETWEEN p_predict_start AND p_predict_end
  )
) AS 'QA-COST-8a: BUY cash_effect_cny must equal -(turnover_cny + fee_cny)';

ASSERT (
  SELECT COUNTIF(mismatch) = 0
  FROM (
    SELECT ABS(bt.cash_effect_cny - bt.turnover_cny + bt.fee_cny) > 1e-3 AS mismatch
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS bt
    WHERE bt.backtest_id = p_backtest_id AND bt.side = 'SELL' AND bt.fill_status = 'FILLED'
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
    WHERE backtest_id = p_backtest_id AND fill_status = 'FILLED'
      AND trade_date BETWEEN p_predict_start AND p_predict_end
  )
) AS 'QA-COST-8c: slippage_cny must match turnover * slippage / (10000 +/- slippage)';

-- ============================================================
-- PRD-20260602-03 策略 1 中文报告与归因分析 QA
-- ============================================================

-- QA-REPORT-1: 评估主基准必须是中证 1000 (000852.SH)，不能是沪深 300
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(bs.benchmark_sec_code != '000852.SH') = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-REPORT-1: benchmark_sec_code in performance_summary must be 000852.SH (assessment benchmark)';

-- QA-REPORT-2: NAV 表的 benchmark_sec_code 也必须是 000852.SH
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(nav.benchmark_sec_code != '000852.SH') = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
  WHERE nav.backtest_id = p_backtest_id
    AND nav.trade_date BETWEEN p_predict_start AND p_predict_end
) AS 'QA-REPORT-2: benchmark_sec_code in nav_daily must be 000852.SH';

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
