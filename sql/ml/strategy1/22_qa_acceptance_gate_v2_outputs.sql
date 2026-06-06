-- BigQuery Standard SQL · Strategy 1 acceptance gate v2 QA
-- 22: 断言 PRD_20260606_04 的共享契约、reference run v2 状态和
--     10/20/30/40 组合诊断输入具备机器可校验的一致性。
--
-- The DECLARE defaults are standalone fallbacks, not the source of truth.
-- Production runs should inject them from
-- configs/strategy1/model_acceptance_contract_v2.yml.
-- The placeholder contract hash intentionally fails QA-V2-1 so standalone
-- execution is fail-loud unless the real contract hash is injected.

DECLARE p_acceptance_gate_version STRING DEFAULT 'strategy1_acceptance_gate_v2';
DECLARE p_acceptance_contract_version STRING DEFAULT 'model_acceptance_contract_v2';
DECLARE p_acceptance_contract_sha256 STRING DEFAULT 'standalone_contract_hash_required';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_reference_run_id STRING DEFAULT 's1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01';
DECLARE p_reference_backtest_id STRING DEFAULT 'bt_s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01';
DECLARE p_prediction_run_id STRING DEFAULT 's1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01';
DECLARE p_full_start_date DATE DEFAULT DATE '2024-01-02';
DECLARE p_full_end_date DATE DEFAULT DATE '2026-04-30';
DECLARE p_valid_start_date DATE DEFAULT DATE '2024-01-02';
DECLARE p_valid_end_date DATE DEFAULT DATE '2024-12-31';
DECLARE p_test_start_date DATE DEFAULT DATE '2025-01-02';
DECLARE p_test_end_date DATE DEFAULT DATE '2025-12-31';
DECLARE p_label_version STRING DEFAULT 'open_to_close_h1_5_10_20_v20260601';
DECLARE p_expected_target_holdings ARRAY<INT64> DEFAULT [10, 20, 30, 40];
DECLARE p_forbidden_target_holdings ARRAY<INT64> DEFAULT [50, 100, 150];
DECLARE p_hard_reject_full_period_excess_return_vs_000852 FLOAT64 DEFAULT -0.03;
DECLARE p_needs_more_evidence_full_period_excess_lower_open FLOAT64 DEFAULT -0.03;
DECLARE p_needs_more_evidence_full_period_excess_upper_closed FLOAT64 DEFAULT 0.03;

CREATE TEMP FUNCTION qa_required(condition BOOL) AS (IFNULL(condition, FALSE));

-- QA-V2-1: v2 gate and contract identity must be explicit and hash-backed.
ASSERT (
  p_acceptance_gate_version = 'strategy1_acceptance_gate_v2'
  AND p_acceptance_contract_version = 'model_acceptance_contract_v2'
  AND p_acceptance_contract_sha256 != 'standalone_contract_hash_required'
  AND LENGTH(p_acceptance_contract_sha256) >= 16
) AS 'QA-V2-1: acceptance gate v2 must use model_acceptance_contract_v2 with a non-empty hash';

-- QA-V2-2: target_holdings universe is exactly 10/20/30/40 and excludes 50/100/150.
ASSERT (
  SELECT
    ARRAY_TO_STRING(ARRAY(SELECT CAST(x AS STRING) FROM UNNEST(p_expected_target_holdings) AS x ORDER BY x), ',')
      = '10,20,30,40'
    AND NOT EXISTS (
      SELECT 1
      FROM UNNEST(p_expected_target_holdings) AS x
      JOIN UNNEST(p_forbidden_target_holdings) AS bad
        ON x = bad
    )
) AS 'QA-V2-2: target_holdings candidates must be exactly 10/20/30/40 and must not include 50/100/150';

-- QA-V2-3: boundary semantics are not ambiguous: -3% is hard reject, needs_more_evidence lower bound is open.
ASSERT (
  p_hard_reject_full_period_excess_return_vs_000852 = -0.03
  AND p_needs_more_evidence_full_period_excess_lower_open = -0.03
  AND p_needs_more_evidence_full_period_excess_upper_closed = 0.03
) AS 'QA-V2-3: full-period excess boundary must put -3pct into hard reject, not needs_more_evidence';

-- QA-V2-4: reference summary and NAV rows must exist under the full-period partition filter.
ASSERT (
  WITH nav AS (
    SELECT COUNT(*) AS nav_rows
    FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
    WHERE nav.backtest_id = p_reference_backtest_id
      AND nav.trade_date BETWEEN p_full_start_date AND p_full_end_date
  ),
  summary AS (
    SELECT COUNT(*) AS summary_rows
    FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
    WHERE bs.backtest_id = p_reference_backtest_id
  )
  SELECT nav.nav_rows > 0 AND summary.summary_rows = 1
  FROM nav CROSS JOIN summary
) AS 'QA-V2-4: reference run must have one summary and partition-filtered NAV rows';

-- QA-V2-5: current reference run must be rejected by v2 hard-reject evidence.
ASSERT (
  WITH nav AS (
    SELECT
      daily_return,
      benchmark_return
    FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
    WHERE nav.backtest_id = p_reference_backtest_id
      AND nav.trade_date BETWEEN p_full_start_date AND p_full_end_date
  ),
  perf AS (
    SELECT
      EXP(SUM(IF(daily_return IS NULL OR 1.0 + daily_return <= 0, 0.0, LN(1.0 + daily_return)))) - 1.0
        AS total_return,
      EXP(SUM(IF(benchmark_return IS NULL OR 1.0 + benchmark_return <= 0, 0.0, LN(1.0 + benchmark_return)))) - 1.0
        AS benchmark_return
    FROM nav
  )
  SELECT total_return - benchmark_return <= p_hard_reject_full_period_excess_return_vs_000852
  FROM perf
) AS 'QA-V2-5: current extended reference run must be rejected under v2 full-period excess hard reject';

-- QA-V2-6: candidate stream must contain enough ranked rows to simulate all 10/20/30/40 portfolios.
ASSERT (
  WITH days AS (
    SELECT
      cand.rebalance_date,
      MAX(cand.rank_raw) AS max_rank_raw
    FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
    WHERE cand.strategy_id = p_strategy_id
      AND cand.run_id = p_reference_run_id
      AND cand.rebalance_date BETWEEN p_full_start_date AND p_full_end_date
      AND cand.rank_raw IS NOT NULL
    GROUP BY cand.rebalance_date
  )
  SELECT COUNT(*) > 0 AND LOGICAL_AND(qa_required(max_rank_raw >= 40))
  FROM days
) AS 'QA-V2-6: reference candidate stream must have rank_raw through at least 40 on each rebalance day';

-- QA-V2-7: prediction rows must record score orientation and selected TopN must use the oriented score field.
ASSERT (
  WITH selected_model AS (
    SELECT reg.model_id
    FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
    WHERE reg.strategy_id = p_strategy_id
      AND reg.status = 'selected'
      AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_prediction_run_id
    ORDER BY reg.created_at DESC
    LIMIT 1
  ),
  pred AS (
    SELECT
      COUNT(*) AS pred_rows,
      COUNTIF(pred.raw_score IS NOT NULL) AS raw_score_rows,
      COUNTIF(pred.score_orientation IS NOT NULL) AS orientation_rows
    FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
    JOIN selected_model AS model
      ON model.model_id = pred.model_id
    WHERE pred.run_id = p_prediction_run_id
      AND pred.predict_date BETWEEN p_valid_start_date AND p_test_end_date
  )
  SELECT
    pred_rows > 0
    AND raw_score_rows = pred_rows
    AND orientation_rows = pred_rows
  FROM pred
) AS 'QA-V2-7: prediction rows must keep raw_score and score_orientation for orientation audit';

-- QA-V2-8: valid/test RankIC inputs must exist and use the same label horizon/split windows as the v2 contract.
ASSERT (
  WITH selected_model AS (
    SELECT reg.model_id
    FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
    WHERE reg.strategy_id = p_strategy_id
      AND reg.status = 'selected'
      AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_prediction_run_id
    ORDER BY reg.created_at DESC
    LIMIT 1
  ),
  scored AS (
    SELECT
      CASE
        WHEN pred.predict_date BETWEEN p_valid_start_date AND p_valid_end_date THEN 'valid'
        WHEN pred.predict_date BETWEEN p_test_start_date AND p_test_end_date THEN 'test'
        ELSE 'other'
      END AS split_tag,
      COUNT(*) AS rows_n
    FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
    JOIN selected_model AS model
      ON model.model_id = pred.model_id
    JOIN `data-aquarium.ashare_dws.dws_stock_sample_daily` AS sample
      ON sample.trade_date = pred.predict_date
     AND sample.sec_code = pred.sec_code
     AND sample.trade_date BETWEEN p_valid_start_date AND p_test_end_date
     AND sample.label_version = p_label_version
    WHERE pred.run_id = p_prediction_run_id
      AND pred.predict_date BETWEEN p_valid_start_date AND p_test_end_date
      AND sample.label_valid_5d
      AND sample.fwd_xs_ret_5d IS NOT NULL
    GROUP BY split_tag
  )
  SELECT
    COUNTIF(split_tag = 'valid' AND rows_n > 0) = 1
    AND COUNTIF(split_tag = 'test' AND rows_n > 0) = 1
  FROM scored
) AS 'QA-V2-8: valid/test signal audit inputs must exist with partition-filtered prediction and sample rows';

-- QA-V2-9: 20/30/40 accepted candidates must not be registered by BQML/SQL runner under v2 before v2 artifacts exist.
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND JSON_VALUE(reg.metrics_json, '$.acceptance_contract_version') = p_acceptance_contract_version
    AND JSON_VALUE(reg.metrics_json, '$.native_acceptance_status') = 'accepted'
    AND JSON_VALUE(reg.metrics_json, '$.model_backend') IN ('bqml', 'bigquery_ml', 'sql_runner')
) AS 'QA-V2-9: BQML/SQL runner must not register new production accepted baseline under v2';
