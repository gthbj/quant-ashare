-- BigQuery Standard SQL · Strategy 1 Model Quality Diagnostics
-- 11: 诊断查询集合（dry-run / review 参考）。
-- 实际执行由 diagnose_model_quality.py 驱动；本文件供独立 review 和分区扫描验证。
-- 所有查询必须显式过滤分区日期（trade_date / predict_date / rebalance_date）。

DECLARE p_run_id STRING DEFAULT 's1_bqml_livepool_20260602_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_bqml_livepool_20260602_01';
DECLARE p_valid_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_valid_end DATE DEFAULT DATE '2024-12-31';
DECLARE p_test_start DATE DEFAULT DATE '2025-01-01';
DECLARE p_test_end DATE DEFAULT DATE '2025-12-31';
DECLARE p_target_holdings INT64 DEFAULT 5;
DECLARE p_label_horizon INT64 DEFAULT 5;

IF p_label_horizon NOT IN (5, 10, 20) THEN
  RAISE USING MESSAGE = 'p_label_horizon must be one of 5, 10, 20';
END IF;

-- ── FR-DIAG-2: daily RankIC (Spearman proxy via rank correlation) ────────────
-- 事后评价：prediction + label-available join（PRD-20260602-05 eval_label_available_mask）
WITH ranked AS (
  SELECT
    pred.predict_date,
    pred.score,
    tp.target_return,
    DENSE_RANK() OVER (PARTITION BY pred.predict_date ORDER BY pred.score) AS score_rank,
    DENSE_RANK() OVER (PARTITION BY pred.predict_date ORDER BY tp.target_return) AS ret_rank
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  JOIN `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
    ON tp.trade_date = pred.predict_date
   AND tp.sec_code = pred.sec_code
   AND tp.run_id = p_run_id
   AND tp.trade_date BETWEEN p_valid_start AND p_test_end
  JOIN `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
    ON s.trade_date = pred.predict_date
   AND s.sec_code = pred.sec_code
   AND s.feature_version = tp.feature_version
   AND s.label_version = tp.label_version
  WHERE pred.run_id = p_run_id
    AND pred.predict_date BETWEEN p_valid_start AND p_test_end
    AND tp.split_tag IN ('valid', 'test')
    AND tp.horizon = p_label_horizon
    AND tp.target_label IS NOT NULL
    AND tp.target_return IS NOT NULL
)
SELECT
  predict_date AS trade_date,
  COUNT(*) AS n,
  CORR(score, target_return) AS pearson_ic,
  CORR(score_rank, ret_rank) AS rank_ic_approx,
  AVG(score) AS avg_score,
  STDDEV_SAMP(score) AS std_score,
  AVG(target_return) AS avg_target_return
FROM ranked
GROUP BY predict_date
ORDER BY predict_date;

-- ── FR-DIAG-3: 5-bucket lift ─────────────────────────────────────────────────
WITH scored AS (
  SELECT
    pred.predict_date,
    pred.sec_code,
    pred.score,
    pred.rank_pct,
    tp.target_return,
    CASE p_label_horizon
      WHEN 5 THEN s.fwd_ret_5d
      WHEN 10 THEN s.fwd_ret_10d
      WHEN 20 THEN s.fwd_ret_20d
    END AS target_abs_return,
    tp.target_label,
    NTILE(5) OVER (PARTITION BY pred.predict_date ORDER BY pred.score DESC, pred.sec_code) AS bucket
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  JOIN `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
    ON tp.trade_date = pred.predict_date
   AND tp.sec_code = pred.sec_code
   AND tp.run_id = p_run_id
   AND tp.trade_date BETWEEN p_valid_start AND p_test_end
  JOIN `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
    ON s.trade_date = pred.predict_date
   AND s.sec_code = pred.sec_code
   AND s.feature_version = tp.feature_version
   AND s.label_version = tp.label_version
  WHERE pred.run_id = p_run_id
    AND pred.predict_date BETWEEN p_valid_start AND p_test_end
    AND tp.split_tag IN ('valid', 'test')
    AND tp.horizon = p_label_horizon
    AND tp.target_label IS NOT NULL
    AND tp.target_return IS NOT NULL
)
SELECT
  bucket,
  COUNT(*) AS n,
  AVG(score) AS avg_score,
  AVG(target_return) AS avg_target_return,
  AVG(target_abs_return) AS avg_target_abs_return,
  AVG(target_label) AS hit_rate,
  STDDEV_SAMP(target_return) AS std_target_return
FROM scored
GROUP BY bucket
ORDER BY bucket;

-- ── FR-DIAG-3: 10-bucket calibration ─────────────────────────────────────────
WITH scored AS (
  SELECT
    pred.predict_date,
    pred.sec_code,
    pred.score,
    tp.target_return,
    tp.target_label,
    CASE p_label_horizon
      WHEN 5 THEN s.label_above_median_5d
      WHEN 10 THEN s.label_above_median_10d
      WHEN 20 THEN s.label_above_median_20d
    END AS target_above_median,
    NTILE(10) OVER (PARTITION BY pred.predict_date ORDER BY pred.score DESC, pred.sec_code) AS bucket
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  JOIN `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
    ON tp.trade_date = pred.predict_date
   AND tp.sec_code = pred.sec_code
   AND tp.run_id = p_run_id
   AND tp.trade_date BETWEEN p_valid_start AND p_test_end
  JOIN `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
    ON s.trade_date = pred.predict_date
   AND s.sec_code = pred.sec_code
   AND s.feature_version = tp.feature_version
   AND s.label_version = tp.label_version
  WHERE pred.run_id = p_run_id
    AND pred.predict_date BETWEEN p_valid_start AND p_test_end
    AND tp.split_tag IN ('valid', 'test')
    AND tp.horizon = p_label_horizon
    AND tp.target_label IS NOT NULL
    AND tp.target_return IS NOT NULL
)
SELECT
  bucket,
  COUNT(*) AS n,
  AVG(score) AS avg_score,
  AVG(target_label) AS actual_pos_rate,
  AVG(target_above_median) AS actual_above_median_rate,
  AVG(target_return) AS avg_target_return
FROM scored
GROUP BY bucket
ORDER BY bucket;

-- ── FR-DIAG-4: label horizon comparison ──────────────────────────────────────
WITH base AS (
  SELECT
    pred.predict_date,
    pred.score,
    l.fwd_xs_ret_1d,
    l.fwd_xs_ret_5d,
    l.fwd_xs_ret_10d,
    l.fwd_xs_ret_20d,
    tp.split_tag
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  JOIN `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
    ON tp.trade_date = pred.predict_date
   AND tp.sec_code = pred.sec_code
   AND tp.run_id = p_run_id
   AND tp.trade_date BETWEEN p_valid_start AND p_test_end
  JOIN `data-aquarium.ashare_dws.dws_stock_label_daily` AS l
    ON l.trade_date = pred.predict_date
   AND l.sec_code = pred.sec_code
   AND l.label_version = tp.label_version
  WHERE pred.run_id = p_run_id
    AND pred.predict_date BETWEEN p_valid_start AND p_test_end
    AND tp.split_tag IN ('valid', 'test')
    AND tp.horizon = p_label_horizon
)
SELECT split_tag, 'fwd_xs_ret_1d'  AS horizon, CORR(score, fwd_xs_ret_1d)  AS rank_ic_approx FROM base GROUP BY split_tag
UNION ALL
SELECT split_tag, 'fwd_xs_ret_5d'  AS horizon, CORR(score, fwd_xs_ret_5d)  AS rank_ic_approx FROM base GROUP BY split_tag
UNION ALL
SELECT split_tag, 'fwd_xs_ret_10d' AS horizon, CORR(score, fwd_xs_ret_10d) AS rank_ic_approx FROM base GROUP BY split_tag
UNION ALL
SELECT split_tag, 'fwd_xs_ret_20d' AS horizon, CORR(score, fwd_xs_ret_20d) AS rank_ic_approx FROM base GROUP BY split_tag;

-- ── FR-DIAG-5: sample universe funnel ────────────────────────────────────────
SELECT
  s.trade_date,
  s.split_tag,
  COUNT(*) AS pure_universe,
  COUNTIF(
    COALESCE(s.in_universe_default, FALSE)
    AND COALESCE(s.has_full_history_60d, FALSE)
    AND COALESCE(s.has_valuation_data, FALSE)
    AND COALESCE(s.label_entry_tradable, FALSE)
    AND CASE p_label_horizon
      WHEN 5 THEN COALESCE(s.label_valid_5d, FALSE) AND s.label_top30_5d IS NOT NULL AND s.fwd_xs_ret_5d IS NOT NULL
      WHEN 10 THEN COALESCE(s.label_valid_10d, FALSE) AND s.label_top30_10d IS NOT NULL AND s.fwd_xs_ret_10d IS NOT NULL
      WHEN 20 THEN COALESCE(s.label_valid_20d, FALSE) AND s.label_top30_20d IS NOT NULL AND s.fwd_xs_ret_20d IS NOT NULL
    END
  ) AS sample_trainable,
  COUNTIF(u.in_universe_default) AS in_universe_default,
  COUNTIF(s.has_full_history_60d) AS has_full_history,
  COUNTIF(s.has_valuation_data) AS has_valuation_data,
  COUNTIF(CASE p_label_horizon
    WHEN 5 THEN COALESCE(s.label_valid_5d, FALSE)
    WHEN 10 THEN COALESCE(s.label_valid_10d, FALSE)
    WHEN 20 THEN COALESCE(s.label_valid_20d, FALSE)
  END) AS label_valid_target,
  COUNTIF(s.label_entry_tradable) AS label_entry_tradable,
  COUNTIF(s.is_st) AS is_st_count,
  COUNTIF(NOT COALESCE(s.is_tradable_hard, FALSE)) AS not_tradable_hard
FROM `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
LEFT JOIN `data-aquarium.ashare_dws.dws_stock_universe_daily` AS u
  ON u.sec_code = s.sec_code AND u.trade_date = s.trade_date
 AND u.trade_date BETWEEN p_valid_start AND p_test_end
WHERE s.trade_date BETWEEN p_valid_start AND p_test_end
  AND s.feature_version = (SELECT ANY_VALUE(tp.feature_version)
                           FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
                           WHERE tp.run_id = p_run_id
                             AND tp.trade_date BETWEEN p_valid_start AND p_test_end
                           LIMIT 1)
GROUP BY s.trade_date, s.split_tag
ORDER BY s.trade_date;

-- ── FR-DIAG-5: candidate funnel ──────────────────────────────────────────────
SELECT
  pred.predict_date AS trade_date,
  COUNT(*) AS prediction_count,
  COUNTIF(cand.is_selected_candidate) AS selected_count,
  COUNTIF(cand.in_universe_default) AS in_universe_pred
FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
LEFT JOIN `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
  ON cand.sec_code = pred.sec_code
 AND cand.rebalance_date = pred.predict_date
 AND cand.strategy_id = p_strategy_id
 AND cand.run_id = p_run_id
WHERE pred.run_id = p_run_id
  AND pred.predict_date BETWEEN p_valid_start AND p_test_end
GROUP BY pred.predict_date
ORDER BY pred.predict_date;

-- ── FR-DIAG-6: feature exposure by group ─────────────────────────────────────
WITH base AS (
  SELECT
    pred.predict_date AS trade_date,
    pred.sec_code,
    pred.score,
    pred.rank_pct,
    cand.is_selected_candidate,
    pos.weight AS position_weight,
    f.ret_1d, f.ret_5d, f.ret_20d, f.ret_60d,
    f.mom_20_5, f.mom_60_20,
    f.vol_20d, f.drawdown_20d,
    f.amount_ma20_cny, f.amount_zscore_20d,
    f.turnover_rate, f.volume_ratio,
    f.pe_ttm, f.pb, f.ep_ttm, f.bp,
    f.log_total_mv, f.log_circ_mv
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  LEFT JOIN `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
    ON cand.sec_code = pred.sec_code
   AND cand.rebalance_date = pred.predict_date
   AND cand.strategy_id = p_strategy_id
   AND cand.run_id = p_run_id
  LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
    ON pos.sec_code = pred.sec_code
   AND pos.trade_date = pred.predict_date
   AND pos.backtest_id = p_backtest_id
  LEFT JOIN `data-aquarium.ashare_dws.dws_stock_feature_daily_v0` AS f
    ON f.sec_code = pred.sec_code
   AND f.trade_date = pred.predict_date
   AND f.trade_date BETWEEN p_test_start AND p_test_end
  WHERE pred.run_id = p_run_id
    AND pred.predict_date BETWEEN p_test_start AND p_test_end
)
SELECT
  'all_predictions' AS group_name,
  AVG(log_total_mv) AS avg_log_total_mv,
  AVG(vol_20d) AS avg_vol_20d,
  AVG(amount_ma20_cny) AS avg_amount_ma20_cny,
  AVG(pe_ttm) AS avg_pe_ttm,
  AVG(pb) AS avg_pb
FROM base

UNION ALL

SELECT
  'top_30pct' AS group_name,
  AVG(log_total_mv),
  AVG(vol_20d),
  AVG(amount_ma20_cny),
  AVG(pe_ttm),
  AVG(pb)
FROM base WHERE rank_pct >= 0.7

UNION ALL

SELECT
  'bottom_30pct' AS group_name,
  AVG(log_total_mv),
  AVG(vol_20d),
  AVG(amount_ma20_cny),
  AVG(pe_ttm),
  AVG(pb)
FROM base WHERE rank_pct <= 0.3

UNION ALL

SELECT
  'selected_candidate' AS group_name,
  AVG(log_total_mv),
  AVG(vol_20d),
  AVG(amount_ma20_cny),
  AVG(pe_ttm),
  AVG(pb)
FROM base WHERE is_selected_candidate

UNION ALL

SELECT
  'held_position' AS group_name,
  AVG(log_total_mv),
  AVG(vol_20d),
  AVG(amount_ma20_cny),
  AVG(pe_ttm),
  AVG(pb)
FROM base WHERE position_weight > 0;

-- ── FR-DIAG-7: drawdown windows ──────────────────────────────────────────────
WITH nav_data AS (
  SELECT trade_date, nav,
         MAX(nav) OVER (ORDER BY trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cummax
  FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily`
  WHERE backtest_id = p_backtest_id
    AND trade_date BETWEEN p_test_start AND p_test_end
)
SELECT trade_date, nav, cummax, nav / NULLIF(cummax, 0) - 1.0 AS drawdown
FROM nav_data
ORDER BY trade_date;

-- ── FR-DIAG-7: portfolio concentration ───────────────────────────────────────
SELECT
  trade_date,
  COUNT(*) AS position_count,
  MAX(weight) AS top_weight,
  SUM(POW(weight, 2)) AS hhi,
  SUM(market_value_cny) AS total_mv
FROM `data-aquarium.ashare_ads.ads_backtest_position_daily`
WHERE backtest_id = p_backtest_id AND trade_date BETWEEN p_test_start AND p_test_end
GROUP BY trade_date
ORDER BY trade_date;

-- ── FR-DIAG-7: cost turnover diagnostics ─────────────────────────────────────
SELECT
  t.trade_date,
  SUM(t.turnover_cny) AS turnover_cny,
  SUM(t.fee_cny) AS fee_cny,
  SUM(t.tax_cny) AS tax_cny,
  SUM(t.slippage_cny) AS slippage_cny,
  SUM(t.fee_cny + t.slippage_cny) AS economic_cost_cny,
  COUNTIF(t.side = 'BUY' AND t.fill_status = 'FILLED') AS buy_filled,
  COUNTIF(t.side = 'BUY' AND t.fill_status = 'BUY_SKIPPED_UNTRADABLE') AS buy_skipped,
  COUNTIF(t.side = 'SELL' AND t.fill_status = 'FILLED') AS sell_filled,
  COUNTIF(t.side = 'SELL' AND t.fill_status = 'SELL_SKIPPED_UNTRADABLE') AS sell_skipped
FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS t
WHERE t.backtest_id = p_backtest_id
  AND t.trade_date BETWEEN p_test_start AND p_test_end
GROUP BY t.trade_date
ORDER BY t.trade_date;

-- ── FR-DIAG-8: market regime (中证 1000) ─────────────────────────────────────
SELECT trade_date, close, pct_chg
FROM `data-aquarium.ashare_dwd.dwd_index_eod`
WHERE sec_code = '000852.SH'
  AND trade_date BETWEEN p_test_start AND p_test_end
ORDER BY trade_date;

-- ── FR-DIAG-8: style exposure (持仓 vs 预测池) ───────────────────────────────
SELECT
  pos.trade_date,
  pos.sec_code,
  pos.weight,
  f.log_total_mv,
  f.vol_20d,
  f.amount_ma20_cny,
  f.pe_ttm,
  f.pb,
  pred.score
FROM `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
LEFT JOIN `data-aquarium.ashare_dws.dws_stock_feature_daily_v0` AS f
  ON f.sec_code = pos.sec_code AND f.trade_date = pos.trade_date
 AND f.trade_date BETWEEN p_test_start AND p_test_end
LEFT JOIN `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  ON pred.sec_code = pos.sec_code AND pred.predict_date = pos.trade_date
 AND pred.run_id = p_run_id
WHERE pos.backtest_id = p_backtest_id
  AND pos.trade_date BETWEEN p_test_start AND p_test_end
ORDER BY pos.trade_date, pos.weight DESC;

-- ── FR-DIAG-9: prediction pool coverage (PRD-20260602-05 FR-LIVE-5) ──────────
-- 对比 live-available prediction pool vs legacy trainable vs label-available eval
SELECT
  tp.split_tag,
  COUNT(*) AS total_panel_rows,
  COUNTIF(
    COALESCE(s.in_universe_default, FALSE)
    AND COALESCE(s.has_full_history_60d, FALSE)
    AND COALESCE(s.has_valuation_data, FALSE)
    AND COALESCE(s.label_entry_tradable, FALSE)
    AND CASE p_label_horizon
      WHEN 5 THEN COALESCE(s.label_valid_5d, FALSE) AND s.label_top30_5d IS NOT NULL AND s.fwd_xs_ret_5d IS NOT NULL
      WHEN 10 THEN COALESCE(s.label_valid_10d, FALSE) AND s.label_top30_10d IS NOT NULL AND s.fwd_xs_ret_10d IS NOT NULL
      WHEN 20 THEN COALESCE(s.label_valid_20d, FALSE) AND s.label_top30_20d IS NOT NULL AND s.fwd_xs_ret_20d IS NOT NULL
    END
  ) AS legacy_trainable_rows,
  COUNTIF(COALESCE(s.in_universe_default, FALSE)
      AND COALESCE(s.has_full_history_60d, FALSE)
      AND COALESCE(s.has_valuation_data, FALSE)) AS live_available_rows,
  COUNTIF(CASE p_label_horizon
    WHEN 5 THEN COALESCE(s.label_valid_5d, FALSE) AND s.fwd_xs_ret_5d IS NOT NULL
    WHEN 10 THEN COALESCE(s.label_valid_10d, FALSE) AND s.fwd_xs_ret_10d IS NOT NULL
    WHEN 20 THEN COALESCE(s.label_valid_20d, FALSE) AND s.fwd_xs_ret_20d IS NOT NULL
  END) AS label_available_eval_rows,
  SAFE_DIVIDE(COUNTIF(
    COALESCE(s.in_universe_default, FALSE)
    AND COALESCE(s.has_full_history_60d, FALSE)
    AND COALESCE(s.has_valuation_data, FALSE)
    AND COALESCE(s.label_entry_tradable, FALSE)
    AND CASE p_label_horizon
      WHEN 5 THEN COALESCE(s.label_valid_5d, FALSE) AND s.label_top30_5d IS NOT NULL AND s.fwd_xs_ret_5d IS NOT NULL
      WHEN 10 THEN COALESCE(s.label_valid_10d, FALSE) AND s.label_top30_10d IS NOT NULL AND s.fwd_xs_ret_10d IS NOT NULL
      WHEN 20 THEN COALESCE(s.label_valid_20d, FALSE) AND s.label_top30_20d IS NOT NULL AND s.fwd_xs_ret_20d IS NOT NULL
    END
  ), COUNT(*)) AS legacy_trainable_ratio,
  SAFE_DIVIDE(COUNTIF(COALESCE(s.in_universe_default, FALSE)
      AND COALESCE(s.has_full_history_60d, FALSE)
      AND COALESCE(s.has_valuation_data, FALSE)), COUNT(*)) AS live_available_ratio,
  SAFE_DIVIDE(COUNTIF(CASE p_label_horizon
    WHEN 5 THEN COALESCE(s.label_valid_5d, FALSE) AND s.fwd_xs_ret_5d IS NOT NULL
    WHEN 10 THEN COALESCE(s.label_valid_10d, FALSE) AND s.fwd_xs_ret_10d IS NOT NULL
    WHEN 20 THEN COALESCE(s.label_valid_20d, FALSE) AND s.fwd_xs_ret_20d IS NOT NULL
  END), COUNT(*)) AS label_eval_ratio
FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
JOIN `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
  ON s.trade_date = tp.trade_date AND s.sec_code = tp.sec_code
 AND s.feature_version = tp.feature_version AND s.label_version = tp.label_version
WHERE tp.run_id = p_run_id
  AND tp.trade_date BETWEEN p_valid_start AND p_test_end
  AND tp.split_tag IN ('valid', 'test')
  AND tp.horizon = p_label_horizon
GROUP BY tp.split_tag;
