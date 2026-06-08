-- BigQuery Standard SQL · Strategy 1 acceptance gate v3 replay QA
-- 24: 校验 v3 replay 的 contract identity、五次正式搜索 Top-K 覆盖、
--     五指数窗口覆盖、公式锁定和 final_holdout 交易日数前提。
--
-- 本 QA 不回写 ADS；它只从现有 registry / backtest / index DWD 复算
-- v3 所需的源数据不变量，确保 replay 和后续 live cutover 有一致口径。

DECLARE p_acceptance_gate_version STRING DEFAULT 'strategy1_acceptance_gate_v3';
DECLARE p_acceptance_contract_version STRING DEFAULT 'model_acceptance_contract_v3';
DECLARE p_acceptance_contract_sha256 STRING DEFAULT 'standalone_contract_hash_required';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_search_ids ARRAY<STRING> DEFAULT [
  'sklearn_native_pvfq_n30_bw_h5_20260605_01',
  'cloudrun_python_lgbm_pvfq_n30_bw_h5_20260605_01',
  'cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01',
  'cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_20260606_01',
  'cloudrun_python_riskfeat_lgbm_reg_pvfq_n30_bw_h5_20260606_01'
];
DECLARE p_top_k_per_search INT64 DEFAULT 5;
DECLARE p_primary_benchmark_sec_code STRING DEFAULT '000001.SH';
DECLARE p_comparison_benchmark_sec_codes ARRAY<STRING> DEFAULT [
  '000016.SH', '000300.SH', '000852.SH', '000001.SH', '399001.SZ'
];
DECLARE p_final_holdout_enforcement STRING DEFAULT 'standalone_final_holdout_enforcement_required';
DECLARE p_legacy_valid_as_cv_search_ids_json STRING DEFAULT 'standalone_legacy_valid_as_cv_search_ids_json_required';
DECLARE p_legacy_valid_as_cv_search_ids ARRAY<STRING> DEFAULT IFNULL(
  (
    SELECT ARRAY_AGG(JSON_VALUE(item))
    FROM UNNEST(JSON_QUERY_ARRAY(p_legacy_valid_as_cv_search_ids_json)) AS item
  ),
  ARRAY<STRING>[]
);
DECLARE p_full_start_date DATE DEFAULT DATE '2024-01-02';
DECLARE p_full_end_date DATE DEFAULT DATE '2026-04-30';
DECLARE p_valid_start_date DATE DEFAULT DATE '2024-01-02';
DECLARE p_valid_end_date DATE DEFAULT DATE '2024-12-31';
DECLARE p_test_start_date DATE DEFAULT DATE '2025-01-02';
DECLARE p_test_end_date DATE DEFAULT DATE '2025-12-31';
DECLARE p_final_holdout_start_date DATE DEFAULT DATE '2026-01-05';
DECLARE p_final_holdout_end_date DATE DEFAULT DATE '2026-04-30';
DECLARE p_min_valid_rank_ic FLOAT64 DEFAULT 0.0;
DECLARE p_min_valid_top_minus_bottom_fwd_ret FLOAT64 DEFAULT 0.0;
DECLARE p_min_test_rank_ic FLOAT64 DEFAULT 0.0;
DECLARE p_min_test_top_minus_bottom_fwd_ret FLOAT64 DEFAULT 0.0;
DECLARE p_min_sharpe FLOAT64 DEFAULT 0.70;
DECLARE p_min_calmar_ratio FLOAT64 DEFAULT 1.0;
DECLARE p_min_final_holdout_trading_days INT64 DEFAULT 40;
DECLARE p_allowed_score_orientations ARRAY<STRING> DEFAULT ['identity', 'reverse_probability'];

CREATE TEMP FUNCTION qa_required(condition BOOL) AS (IFNULL(condition, FALSE));
CREATE TEMP FUNCTION qa_gross_from_returns(log_sum FLOAT64) AS (EXP(log_sum));
CREATE TEMP FUNCTION qa_compound_annualized_return(gross_return FLOAT64, period_count INT64) AS (
  CASE
    WHEN gross_return IS NULL OR period_count IS NULL OR period_count <= 0 OR gross_return <= 0 THEN NULL
    ELSE POW(gross_return, 252.0 / period_count) - 1.0
  END
);
CREATE TEMP FUNCTION qa_zero_safe_ratio(numerator FLOAT64, denominator FLOAT64) AS (
  CASE
    WHEN numerator IS NULL OR denominator IS NULL THEN NULL
    WHEN ABS(denominator) < 1e-12 AND numerator > 0 THEN CAST('+inf' AS FLOAT64)
    WHEN ABS(denominator) < 1e-12 AND numerator < 0 THEN CAST('-inf' AS FLOAT64)
    WHEN ABS(denominator) < 1e-12 THEN 0.0
    ELSE numerator / denominator
  END
);

CREATE TEMP TABLE qa_v3_selected_rows AS
WITH selected_registry AS (
  SELECT
    reg.model_id,
    bs.backtest_id,
    JSON_VALUE(reg.model_params_json, '$.run_id') AS run_id,
    JSON_VALUE(reg.metrics_json, '$.search_id') AS search_id,
    JSON_VALUE(reg.metrics_json, '$.cv_confirmation_status') AS cv_confirmation_status_raw,
    JSON_VALUE(reg.metrics_json, '$.valid_signal_status') AS valid_signal_status,
    JSON_VALUE(reg.metrics_json, '$.score_orientation') AS score_orientation,
    SAFE_CAST(COALESCE(JSON_VALUE(reg.metrics_json, '$.oriented_valid_rank_ic_mean'), JSON_VALUE(reg.metrics_json, '$.valid_rank_ic_mean')) AS FLOAT64) AS valid_rank_ic,
    SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.valid_top_minus_bottom_fwd_ret_mean') AS FLOAT64) AS valid_top_minus_bottom,
    SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.cv_rank_ic_mean') AS FLOAT64) AS cv_rank_ic_mean_raw,
    SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.cv_top_minus_bottom_fwd_ret_mean') AS FLOAT64) AS cv_top_minus_bottom_raw,
    SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.cv_fold_count') AS INT64) AS cv_fold_count_raw,
    SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_rank_ic_mean') AS FLOAT64) AS test_rank_ic_mean_raw,
    SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_top_minus_bottom_fwd_ret_mean') AS FLOAT64) AS test_top_minus_bottom_raw
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
    ON bs.model_id = reg.model_id
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') IN UNNEST(p_search_ids)
),
test_rank_ic AS (
  SELECT
    day_ic.run_id,
    AVG(day_ic.rank_ic) AS test_rank_ic_mean
  FROM (
    SELECT
      pred.run_id,
      pred.predict_date,
      CORR(CAST(score_rank AS FLOAT64), CAST(ret_rank AS FLOAT64)) AS rank_ic
    FROM (
      SELECT
        pred.run_id,
        pred.predict_date,
        pred.sec_code,
        RANK() OVER (PARTITION BY pred.run_id, pred.predict_date ORDER BY pred.score) AS score_rank,
        RANK() OVER (PARTITION BY pred.run_id, pred.predict_date ORDER BY tp.target_return) AS ret_rank
      FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
      JOIN `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
        ON tp.run_id = pred.run_id
       AND tp.trade_date = pred.predict_date
       AND tp.sec_code = pred.sec_code
      WHERE pred.run_id IN (SELECT DISTINCT run_id FROM selected_registry)
        AND pred.predict_date BETWEEN p_test_start_date AND p_test_end_date
        AND tp.split_tag = 'test'
        AND tp.target_return IS NOT NULL
    ) AS pred
    GROUP BY pred.run_id, pred.predict_date
  ) AS day_ic
  GROUP BY day_ic.run_id
),
test_bucket_spread AS (
  SELECT
    scored.run_id,
    AVG(scored.top_minus_bottom) AS test_top_minus_bottom_fwd_ret_mean
  FROM (
    SELECT
      bucketed.run_id,
      bucketed.predict_date,
      AVG(IF(bucketed.score_bucket = 5, bucketed.target_return, NULL))
        - AVG(IF(bucketed.score_bucket = 1, bucketed.target_return, NULL)) AS top_minus_bottom
    FROM (
      SELECT
        pred.run_id,
        pred.predict_date,
        tp.target_return,
        NTILE(5) OVER (PARTITION BY pred.run_id, pred.predict_date ORDER BY pred.score) AS score_bucket
      FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
      JOIN `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
        ON tp.run_id = pred.run_id
       AND tp.trade_date = pred.predict_date
       AND tp.sec_code = pred.sec_code
      WHERE pred.run_id IN (SELECT DISTINCT run_id FROM selected_registry)
        AND pred.predict_date BETWEEN p_test_start_date AND p_test_end_date
        AND tp.split_tag = 'test'
        AND tp.target_return IS NOT NULL
    ) AS bucketed
    GROUP BY bucketed.run_id, bucketed.predict_date
  ) AS scored
  GROUP BY scored.run_id
)
SELECT
  sr.model_id,
  sr.backtest_id,
  sr.run_id,
  sr.search_id,
  sr.valid_signal_status,
  sr.score_orientation,
  sr.valid_rank_ic,
  sr.valid_top_minus_bottom,
  CASE
    WHEN sr.cv_confirmation_status_raw IS NOT NULL THEN sr.cv_confirmation_status_raw
    WHEN sr.cv_rank_ic_mean_raw IS NOT NULL AND sr.cv_top_minus_bottom_raw IS NOT NULL THEN
      CASE
        WHEN COALESCE(sr.cv_fold_count_raw, 3) < 3 THEN 'failed'
        WHEN sr.cv_rank_ic_mean_raw > 0 AND sr.cv_top_minus_bottom_raw > 0 THEN 'passed'
        ELSE 'failed'
      END
    WHEN sr.search_id IN UNNEST(p_legacy_valid_as_cv_search_ids)
      AND sr.valid_signal_status IS NOT NULL
      AND sr.valid_rank_ic IS NOT NULL
      AND sr.valid_top_minus_bottom IS NOT NULL THEN
      CASE
        WHEN sr.valid_signal_status = 'stable'
          AND sr.valid_rank_ic > 0
          AND sr.valid_top_minus_bottom > 0 THEN 'passed'
        ELSE 'failed'
      END
    ELSE NULL
  END AS effective_cv_confirmation_status,
  COALESCE(sr.test_rank_ic_mean_raw, tri.test_rank_ic_mean) AS effective_test_rank_ic,
  COALESCE(sr.test_top_minus_bottom_raw, tbs.test_top_minus_bottom_fwd_ret_mean) AS effective_test_top_minus_bottom
FROM selected_registry AS sr
LEFT JOIN test_rank_ic AS tri
  ON tri.run_id = sr.run_id
LEFT JOIN test_bucket_spread AS tbs
  ON tbs.run_id = sr.run_id
;

-- QA-V3-1: gate identity must be explicit and contract hash-backed.
ASSERT (
  p_acceptance_gate_version = 'strategy1_acceptance_gate_v3'
  AND p_acceptance_contract_version = 'model_acceptance_contract_v3'
  AND p_acceptance_contract_sha256 != 'standalone_contract_hash_required'
  AND LENGTH(p_acceptance_contract_sha256) >= 16
  AND p_primary_benchmark_sec_code = '000001.SH'
  AND p_final_holdout_enforcement IN ('diagnostic_only', 'blocking')
) AS 'QA-V3-1: acceptance gate v3 must use model_acceptance_contract_v3 with non-empty hash and primary benchmark 000001.SH';

-- QA-V3-2: replay default search universe must be exactly five unique completed searches.
ASSERT (
  ARRAY_LENGTH(p_search_ids) = 5
  AND ARRAY_LENGTH(ARRAY(SELECT DISTINCT x FROM UNNEST(p_search_ids) AS x)) = 5
  AND ARRAY_LENGTH(p_comparison_benchmark_sec_codes) = 5
  AND ARRAY_LENGTH(ARRAY(SELECT DISTINCT x FROM UNNEST(p_comparison_benchmark_sec_codes) AS x)) = 5
  AND p_primary_benchmark_sec_code IN UNNEST(p_comparison_benchmark_sec_codes)
) AS 'QA-V3-2: v3 replay default universe must be five unique searches and five unique comparison benchmarks';

-- QA-V3-3: each replayed search must contribute exactly Top-K selected registry rows with backtest ids.
ASSERT (
  WITH selected AS (
    SELECT
      search_id,
      COUNT(*) AS selected_rows,
      COUNTIF(search_id IS NOT NULL) AS nonnull_search_rows,
      COUNTIF(backtest_id IS NOT NULL) AS backtest_rows
    FROM qa_v3_selected_rows
    GROUP BY search_id
  )
  SELECT
    COUNT(*) = ARRAY_LENGTH(p_search_ids)
    AND LOGICAL_AND(qa_required(selected_rows = p_top_k_per_search))
    AND LOGICAL_AND(qa_required(nonnull_search_rows = p_top_k_per_search))
    AND LOGICAL_AND(qa_required(backtest_rows = p_top_k_per_search))
  FROM selected
) AS 'QA-V3-3: each replayed search must have exactly Top-K selected rows with backtest ids';

-- QA-V3-4: comparison benchmarks must cover every candidate NAV trade_date in the replay window.
ASSERT (
  WITH selected_backtests AS (
    SELECT DISTINCT backtest_id
    FROM qa_v3_selected_rows
  ),
  expected_dates AS (
    SELECT DISTINCT nav.trade_date
    FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
    JOIN selected_backtests AS sb
      ON sb.backtest_id = nav.backtest_id
    WHERE nav.trade_date BETWEEN p_full_start_date AND p_full_end_date
  ),
  benchmark_coverage AS (
    SELECT
      bench.sec_code,
      COUNT(*) AS matched_dates,
      COUNTIF(bench.close IS NOT NULL) AS nonnull_close_dates
    FROM `data-aquarium.ashare_dwd.dwd_index_eod` AS bench
    JOIN expected_dates AS d
      ON d.trade_date = bench.trade_date
    WHERE bench.sec_code IN UNNEST(p_comparison_benchmark_sec_codes)
    GROUP BY bench.sec_code
  ),
  expected AS (
    SELECT COUNT(*) AS expected_date_count FROM expected_dates
  )
  SELECT
    COUNT(*) = ARRAY_LENGTH(p_comparison_benchmark_sec_codes)
    AND LOGICAL_AND(qa_required(matched_dates = expected.expected_date_count))
    AND LOGICAL_AND(qa_required(nonnull_close_dates = expected.expected_date_count))
  FROM benchmark_coverage
  CROSS JOIN expected
) AS 'QA-V3-4: all five comparison benchmarks must fully cover every replay NAV trade_date';

-- QA-V3-5: signal-quality inputs required by v3 must exist or be source-derivable on all selected rows.
ASSERT (
  SELECT
    COUNT(*) = ARRAY_LENGTH(p_search_ids) * p_top_k_per_search
    AND LOGICAL_AND(qa_required(effective_cv_confirmation_status IS NOT NULL))
    AND LOGICAL_AND(qa_required(valid_signal_status IS NOT NULL))
    AND LOGICAL_AND(qa_required(score_orientation IN UNNEST(p_allowed_score_orientations)))
    AND LOGICAL_AND(qa_required(valid_rank_ic IS NOT NULL))
    AND LOGICAL_AND(qa_required(valid_top_minus_bottom IS NOT NULL))
    AND LOGICAL_AND(qa_required(effective_test_rank_ic IS NOT NULL))
    AND LOGICAL_AND(qa_required(effective_test_top_minus_bottom IS NOT NULL))
  FROM qa_v3_selected_rows
) AS 'QA-V3-5: v3 signal-quality fields must exist or be source-derivable on all replayed selected rows';

CREATE TEMP TABLE qa_v3_final_holdout_days AS
WITH selected_backtests AS (
  SELECT DISTINCT backtest_id
  FROM qa_v3_selected_rows
)
SELECT
  sb.backtest_id,
  COUNT(nav.trade_date) AS trading_days
FROM selected_backtests AS sb
LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
  ON nav.backtest_id = sb.backtest_id
 AND nav.trade_date BETWEEN p_final_holdout_start_date AND p_final_holdout_end_date
GROUP BY sb.backtest_id
;

-- QA-V3-6: final_holdout enforcement must follow the contract; if diagnostic_only, do not hard-fail on the threshold.
ASSERT (
  SELECT
    COUNT(*) = ARRAY_LENGTH(p_search_ids) * p_top_k_per_search
    AND (
      p_final_holdout_enforcement = 'diagnostic_only'
      OR LOGICAL_AND(qa_required(trading_days >= p_min_final_holdout_trading_days))
    )
  FROM qa_v3_final_holdout_days
) AS 'QA-V3-6: final_holdout enforcement must match the contract-defined blocking behavior';

-- QA-V3-7: v3 absolute metrics must be source-computable and the formula-locked thresholds must be evaluable.
ASSERT (
  WITH selected_rows AS (
    SELECT
      model_id,
      backtest_id,
      search_id,
      valid_rank_ic,
      valid_top_minus_bottom,
      effective_test_rank_ic AS test_rank_ic,
      effective_test_top_minus_bottom AS test_top_minus_bottom
    FROM qa_v3_selected_rows
  ),
  nav AS (
    SELECT
      nav.backtest_id,
      nav.trade_date,
      nav.nav,
      nav.daily_return,
      MAX(nav.nav) OVER (PARTITION BY nav.backtest_id ORDER BY nav.trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_peak_nav
    FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
    JOIN selected_rows AS sr
      ON sr.backtest_id = nav.backtest_id
    WHERE nav.trade_date BETWEEN p_full_start_date AND p_full_end_date
  ),
  nav_drawdown AS (
    SELECT
      backtest_id,
      trade_date,
      nav.nav AS nav,
      daily_return,
      running_peak_nav,
      SAFE_DIVIDE(nav.nav, running_peak_nav) - 1.0 AS drawdown
    FROM nav
  ),
  trough AS (
    SELECT * EXCEPT(rn)
    FROM (
      SELECT
        backtest_id,
        trade_date AS trough_date,
        drawdown AS max_drawdown,
        running_peak_nav,
        ROW_NUMBER() OVER (PARTITION BY backtest_id ORDER BY drawdown ASC, trade_date ASC) AS rn
      FROM nav_drawdown
    )
    WHERE rn = 1
  ),
  peak AS (
    SELECT * EXCEPT(rn)
    FROM (
      SELECT
        nd.backtest_id,
        nd.trade_date AS peak_date,
        ROW_NUMBER() OVER (PARTITION BY nd.backtest_id ORDER BY nd.trade_date DESC) AS rn
      FROM nav_drawdown AS nd
      JOIN trough AS t
        ON t.backtest_id = nd.backtest_id
      WHERE nd.trade_date <= t.trough_date
        AND ABS(nd.nav - t.running_peak_nav) < 1e-9
    )
    WHERE rn = 1
  ),
  strategy_metrics AS (
    SELECT
      sr.model_id,
      sr.backtest_id,
      sr.search_id,
      sr.valid_rank_ic,
      sr.valid_top_minus_bottom,
      sr.test_rank_ic,
      sr.test_top_minus_bottom,
      COUNTIF(nav.daily_return IS NOT NULL AND 1.0 + nav.daily_return > 0) AS return_period_count,
      qa_gross_from_returns(SUM(IF(nav.daily_return IS NULL OR 1.0 + nav.daily_return <= 0, 0.0, LN(1.0 + nav.daily_return)))) AS strategy_gross_return,
      STDDEV_SAMP(nav.daily_return) * SQRT(252.0) AS annualized_volatility,
      t.max_drawdown,
      p.peak_date,
      t.trough_date
    FROM selected_rows AS sr
    JOIN nav
      ON nav.backtest_id = sr.backtest_id
    JOIN trough AS t
      ON t.backtest_id = sr.backtest_id
    JOIN peak AS p
      ON p.backtest_id = sr.backtest_id
    GROUP BY sr.model_id, sr.backtest_id, sr.search_id, sr.valid_rank_ic, sr.valid_top_minus_bottom, sr.test_rank_ic, sr.test_top_minus_bottom, t.max_drawdown, p.peak_date, t.trough_date
  )
  SELECT
    COUNT(*) = ARRAY_LENGTH(p_search_ids) * p_top_k_per_search
    AND LOGICAL_AND(qa_required(valid_rank_ic IS NOT NULL))
    AND LOGICAL_AND(qa_required(valid_top_minus_bottom IS NOT NULL))
    AND LOGICAL_AND(qa_required(test_rank_ic IS NOT NULL))
    AND LOGICAL_AND(qa_required(test_top_minus_bottom IS NOT NULL))
    AND LOGICAL_AND(qa_required(qa_compound_annualized_return(strategy_gross_return, return_period_count) IS NOT NULL))
    AND LOGICAL_AND(qa_required(qa_zero_safe_ratio(qa_compound_annualized_return(strategy_gross_return, return_period_count), annualized_volatility) IS NOT NULL))
    AND LOGICAL_AND(qa_required(qa_zero_safe_ratio(qa_compound_annualized_return(strategy_gross_return, return_period_count), ABS(max_drawdown)) IS NOT NULL))
  FROM strategy_metrics
) AS 'QA-V3-7: v3 absolute metrics must be source-computable for all replayed candidates';

-- QA-V3-8: direct-pass branch cannot bypass positive excess annualized return, and zero same-window excess must not yield a ratio.
ASSERT (
  WITH selected_rows AS (
    SELECT
      model_id,
      backtest_id,
      search_id
    FROM qa_v3_selected_rows
  ),
  nav AS (
    SELECT
      nav.backtest_id,
      nav.trade_date,
      nav.nav,
      nav.daily_return,
      LAG(nav.trade_date) OVER (PARTITION BY nav.backtest_id ORDER BY nav.trade_date) AS previous_trade_date,
      MAX(nav.nav) OVER (PARTITION BY nav.backtest_id ORDER BY nav.trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_peak_nav,
      MIN(nav.trade_date) OVER (PARTITION BY nav.backtest_id) AS window_start_date,
      MAX(nav.trade_date) OVER (PARTITION BY nav.backtest_id) AS window_end_date
    FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
    JOIN selected_rows AS sr
      ON sr.backtest_id = nav.backtest_id
    WHERE nav.trade_date BETWEEN p_full_start_date AND p_full_end_date
  ),
  nav_drawdown AS (
    SELECT
      backtest_id,
      trade_date,
      nav.nav AS nav,
      daily_return,
      running_peak_nav,
      window_start_date,
      window_end_date,
      SAFE_DIVIDE(nav.nav, running_peak_nav) - 1.0 AS drawdown
    FROM nav
  ),
  trough AS (
    SELECT * EXCEPT(rn)
    FROM (
      SELECT
        backtest_id,
        trade_date AS trough_date,
        drawdown AS max_drawdown,
        running_peak_nav,
        ROW_NUMBER() OVER (PARTITION BY backtest_id ORDER BY drawdown ASC, trade_date ASC) AS rn
      FROM nav_drawdown
    )
    WHERE rn = 1
  ),
  peak AS (
    SELECT * EXCEPT(rn)
    FROM (
      SELECT
        nd.backtest_id,
        nd.trade_date AS peak_date,
        ROW_NUMBER() OVER (PARTITION BY nd.backtest_id ORDER BY nd.trade_date DESC) AS rn
      FROM nav_drawdown AS nd
      JOIN trough AS t
        ON t.backtest_id = nd.backtest_id
      WHERE nd.trade_date <= t.trough_date
        AND ABS(nd.nav - t.running_peak_nav) < 1e-9
    )
    WHERE rn = 1
  ),
  strategy_metrics AS (
    SELECT
      sr.model_id,
      sr.backtest_id,
      sr.search_id,
      COUNTIF(nav.daily_return IS NOT NULL AND 1.0 + nav.daily_return > 0) AS return_period_count,
      qa_gross_from_returns(SUM(IF(nav.daily_return IS NULL OR 1.0 + nav.daily_return <= 0, 0.0, LN(1.0 + nav.daily_return)))) AS strategy_gross_return,
      t.max_drawdown,
      p.peak_date,
      t.trough_date,
      MIN(nav.trade_date) AS window_start_date,
      MAX(nav.trade_date) AS window_end_date
    FROM selected_rows AS sr
    JOIN nav
      ON nav.backtest_id = sr.backtest_id
    JOIN trough AS t
      ON t.backtest_id = sr.backtest_id
    JOIN peak AS p
      ON p.backtest_id = sr.backtest_id
    GROUP BY sr.model_id, sr.backtest_id, sr.search_id, t.max_drawdown, p.peak_date, t.trough_date
  ),
  benchmark_steps AS (
    SELECT
      nav.backtest_id,
      bench_code AS benchmark_sec_code,
      COUNTIF(nav.daily_return IS NOT NULL AND 1.0 + nav.daily_return > 0) AS benchmark_effective_return_period_count,
      qa_gross_from_returns(SUM(
        CASE
          WHEN nav.daily_return IS NULL OR 1.0 + nav.daily_return <= 0 THEN 0.0
          WHEN nav.previous_trade_date IS NULL THEN 0.0
          ELSE LN(SAFE_DIVIDE(b_curr.close, b_prev.close))
        END
      )) AS benchmark_gross_return
    FROM nav
    CROSS JOIN UNNEST(p_comparison_benchmark_sec_codes) AS bench_code
    LEFT JOIN `data-aquarium.ashare_dwd.dwd_index_eod` AS b_prev
      ON b_prev.sec_code = bench_code
     AND b_prev.trade_date = nav.previous_trade_date
     AND b_prev.trade_date BETWEEN p_full_start_date AND p_full_end_date
    LEFT JOIN `data-aquarium.ashare_dwd.dwd_index_eod` AS b_curr
      ON b_curr.sec_code = bench_code
     AND b_curr.trade_date = nav.trade_date
     AND b_curr.trade_date BETWEEN p_full_start_date AND p_full_end_date
    GROUP BY nav.backtest_id, benchmark_sec_code
  ),
  candidate_benchmark AS (
    SELECT
      sm.model_id,
      sm.backtest_id,
      sm.search_id,
      bench.sec_code AS benchmark_sec_code,
      qa_compound_annualized_return(sm.strategy_gross_return, sm.return_period_count) AS strategy_compound_annualized_return,
      qa_compound_annualized_return(bs.benchmark_gross_return, bs.benchmark_effective_return_period_count) AS benchmark_compound_annualized_return,
      sm.max_drawdown,
      SAFE_DIVIDE(b_trough.close, b_peak.close) - 1.0 AS benchmark_same_window_return
    FROM strategy_metrics AS sm
    CROSS JOIN UNNEST(p_comparison_benchmark_sec_codes) AS bench_code
    JOIN benchmark_steps AS bs
      ON bs.backtest_id = sm.backtest_id
     AND bs.benchmark_sec_code = bench_code
    JOIN `data-aquarium.ashare_dwd.dwd_index_eod` AS b_peak
      ON b_peak.sec_code = bench_code
     AND b_peak.trade_date = sm.peak_date
     AND b_peak.trade_date BETWEEN p_full_start_date AND p_full_end_date
    JOIN `data-aquarium.ashare_dwd.dwd_index_eod` AS b_trough
      ON b_trough.sec_code = bench_code
     AND b_trough.trade_date = sm.trough_date
     AND b_trough.trade_date BETWEEN p_full_start_date AND p_full_end_date
    JOIN UNNEST([STRUCT(bench_code AS sec_code)]) AS bench
  ),
  scored AS (
    SELECT
      model_id,
      backtest_id,
      search_id,
      benchmark_sec_code,
      strategy_compound_annualized_return - benchmark_compound_annualized_return AS strategy_excess_compound_annualized_return,
      max_drawdown - benchmark_same_window_return AS strategy_max_drawdown_same_window_excess,
      CASE
        WHEN max_drawdown - benchmark_same_window_return < 0 THEN (strategy_compound_annualized_return - benchmark_compound_annualized_return) / ABS(max_drawdown - benchmark_same_window_return)
        ELSE NULL
      END AS excess_calmar_ratio,
      (
        strategy_compound_annualized_return - benchmark_compound_annualized_return > 0
        AND (
          max_drawdown - benchmark_same_window_return > 0
          OR (
            max_drawdown - benchmark_same_window_return < 0
            AND (strategy_compound_annualized_return - benchmark_compound_annualized_return) / ABS(max_drawdown - benchmark_same_window_return) > 1.0
          )
        )
      ) AS relative_gate_pass
    FROM candidate_benchmark
  )
  SELECT
    COUNTIF(relative_gate_pass AND NOT qa_required(strategy_excess_compound_annualized_return > 0)) = 0
    AND COUNTIF(ABS(strategy_max_drawdown_same_window_excess) < 1e-12 AND excess_calmar_ratio IS NOT NULL) = 0
    AND COUNTIF(strategy_max_drawdown_same_window_excess < 0 AND excess_calmar_ratio IS NULL) = 0
  FROM scored
) AS 'QA-V3-8: direct-pass must still require positive excess annualized return, and zero same-window excess must not produce a ratio';
