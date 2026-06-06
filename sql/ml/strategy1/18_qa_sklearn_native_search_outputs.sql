-- BigQuery Standard SQL · Strategy 1 sklearn native search QA
-- 18: 断言 sklearn native search / Top-K 回测产物和 native acceptance 元数据。

DECLARE p_search_id STRING DEFAULT 'sklearn_native_pvfq_n30_bw_h5_20260605_01';
DECLARE p_source_run_id STRING DEFAULT 's1_sklearn_native_pvfq_n30_bw_h5_20260605_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_expected_candidate_count INT64 DEFAULT 36;
DECLARE p_top_k INT64 DEFAULT 5;
DECLARE p_test_reuse_wave_no INT64 DEFAULT 1;
DECLARE p_acceptance_contract_version STRING DEFAULT 'model_acceptance_contract_v1';
DECLARE p_min_test_rank_ic FLOAT64 DEFAULT 0.0;
DECLARE p_min_test_year_excess_return_vs_000852 FLOAT64 DEFAULT 0.0;
DECLARE p_min_sharpe FLOAT64 DEFAULT 0.70;
DECLARE p_min_max_drawdown FLOAT64 DEFAULT -0.25;
DECLARE p_required_valid_signal_status STRING DEFAULT 'stable';
DECLARE p_final_holdout_required_after_wave INT64 DEFAULT 3;
DECLARE p_final_holdout_passed_status STRING DEFAULT 'passed';

-- The DECLARE defaults are standalone fallbacks, not the source of truth.
-- Production orchestrators must inject these values from
-- configs/strategy1/model_acceptance_contract_v1.yml.
CREATE TEMP FUNCTION qa_required(condition BOOL) AS (IFNULL(condition, FALSE));

-- QA-SKN-1: search_id 下 Top-K registry 记录能追溯完整 candidate_count / source_run_id。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.source_run_id') = p_source_run_id))
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.work_unit_count') AS INT64) = p_expected_candidate_count))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-SKN-1: Top-K registry rows must record search_id, source_run_id and expected candidate_count';

-- QA-SKN-2: 每个 Top-K selected model 都有 terminal task-fanout / matrix audit 信息。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.task_fanout_mode') = 'task_fanout'))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.matrix_id') IS NOT NULL))
    AND LOGICAL_AND(qa_required(STARTS_WITH(JSON_VALUE(reg.metrics_json, '$.matrix_uri'), 'gs://')))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.feature_order_sha256') IS NOT NULL))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.preprocess_stats_sha256') IS NOT NULL))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.work_units_sha256') IS NOT NULL))
    AND COUNTIF(NOT qa_required(
      SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.succeeded_task_count') AS INT64)
      = SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.work_unit_count') AS INT64)
    )) = 0
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-SKN-2: Top-K selected models must have complete task-fanout matrix/task status metadata';

-- QA-SKN-3: candidate task 不得扫描全量训练面板，沿用 task-fanout audit 计数。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.candidate_task_bq_forbidden_table_query_count') AS INT64) = 0))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-SKN-3: candidate task BigQuery audit must show no forbidden full-panel scans';

-- QA-SKN-4 / QA-SKN-10: shortlist 排名只使用 valid 指标，不写 test 指标进排名 key。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.shortlist_ranking_uses_test_metrics') = 'false'))
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.shortlist_rank_valid_only') AS INT64) IS NOT NULL))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-SKN-4/10: Top-K shortlist rank must be valid-only and explicitly tagged as not using test metrics';

-- QA-SKN-5: Top-K 候选 run_id / backtest_id 独立且不超过 p_top_k。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND COUNT(DISTINCT JSON_VALUE(reg.metrics_json, '$.candidate_run_id')) = COUNT(*)
    AND COUNT(DISTINCT JSON_VALUE(reg.metrics_json, '$.candidate_backtest_id')) = COUNT(*)
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-SKN-5: Top-K candidates must have independent candidate_run_id and candidate_backtest_id';

-- QA-SKN-6: Top-K 候选报告和诊断均 uploaded。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(JSON_VALUE(bs.metrics_json, '$.report_upload_status') = 'uploaded'))
    AND LOGICAL_AND(qa_required(JSON_VALUE(bs.metrics_json, '$.model_diagnosis_upload_status') = 'uploaded'))
    AND LOGICAL_AND(qa_required(STARTS_WITH(JSON_VALUE(bs.metrics_json, '$.report_uri'), 'gs://')))
    AND LOGICAL_AND(qa_required(STARTS_WITH(JSON_VALUE(bs.metrics_json, '$.model_diagnosis_uri'), 'gs://')))
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  JOIN `data-aquarium.ashare_ads.ads_model_registry` AS reg
    ON reg.model_id = bs.model_id
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-SKN-6: Top-K candidates must have uploaded report and model diagnosis artifacts';

-- QA-SKN-7 / QA-SKN-11: accepted 候选必须满足 hard gates，且 valid_signal_status=stable。
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  JOIN `data-aquarium.ashare_ads.ads_model_registry` AS reg
    ON reg.model_id = bs.model_id
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
    AND JSON_VALUE(reg.metrics_json, '$.native_acceptance_status') = 'accepted'
    AND (
      NOT IFNULL(JSON_VALUE(reg.metrics_json, '$.valid_signal_status') = p_required_valid_signal_status, FALSE)
      OR NOT IFNULL(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_rank_ic_mean') AS FLOAT64) > p_min_test_rank_ic, FALSE)
      OR SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.valid_top_minus_bottom_fwd_ret_mean') AS FLOAT64) IS NULL
      OR SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_top_minus_bottom_fwd_ret_mean') AS FLOAT64) IS NULL
      OR (
        SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.valid_top_minus_bottom_fwd_ret_mean') AS FLOAT64) < 0
        AND SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_top_minus_bottom_fwd_ret_mean') AS FLOAT64) < 0
      )
      OR SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_year_total_return') AS FLOAT64) <= 0
      OR NOT IFNULL(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_year_excess_return') AS FLOAT64) > p_min_test_year_excess_return_vs_000852, FALSE)
      OR NOT IFNULL(bs.sharpe >= p_min_sharpe, FALSE)
      OR NOT IFNULL(bs.max_drawdown >= p_min_max_drawdown, FALSE)
    )
) AS 'QA-SKN-7/11: accepted sklearn native candidates must satisfy hard gates and have stable valid signal';

-- QA-SKN-8: native path 仍必须记录 BQML reference 字段，但不要求 parity passed。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.bqml_reference_run_id') IS NOT NULL))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.model_quality_parity_status') IN ('passed', 'failed', 'warning')))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-SKN-8: native candidates must keep BQML reference evidence without requiring parity pass';

-- QA-SKN-9: 若无 accepted，至少明确 rejected / needs_more_evidence / candidate 之一，不能留空。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.native_acceptance_status') IN (
      'candidate', 'accepted', 'rejected', 'needs_more_evidence'
    )))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-SKN-9: native_acceptance_status must be populated with an allowed value';

-- QA-SKN-12: 第二波及以后复用 2025 test 必须写 owner approval ref。
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
    AND SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_reuse_wave_no') AS INT64) >= 2
    AND NULLIF(JSON_VALUE(reg.metrics_json, '$.test_reuse_approval_ref'), '') IS NULL
) AS 'QA-SKN-12: wave 2+ test reuse must record owner approval reference';

-- QA-SKN-13: 超过 3 波且没有最终 holdout 通过证据时，不得 accepted。
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
    AND SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_reuse_wave_no') AS INT64) > p_final_holdout_required_after_wave
    AND JSON_VALUE(reg.metrics_json, '$.native_acceptance_status') = 'accepted'
    AND IFNULL(JSON_VALUE(reg.metrics_json, '$.final_holdout_status'), '') != p_final_holdout_passed_status
) AS 'QA-SKN-13: wave >3 cannot be accepted without final holdout passed evidence';

-- Sanity: caller-provided wave number must match registry rows.
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_reuse_wave_no') AS INT64) = p_test_reuse_wave_no))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-SKN-14: registry test_reuse_wave_no must match QA parameter';

-- QA-SKN-15: sklearn native search acceptance 必须追溯共享验收契约版本。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.acceptance_contract_version') = p_acceptance_contract_version))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-SKN-15: sklearn native search must record shared acceptance_contract_version';

-- QA-SKN-16: unmatched_acceptance_state 只能作为 rejected 兜底原因。
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
    AND JSON_VALUE(reg.metrics_json, '$.native_acceptance_reason') = 'unmatched_acceptance_state'
    AND JSON_VALUE(reg.metrics_json, '$.native_acceptance_status') != 'rejected'
) AS 'QA-SKN-16: unmatched_acceptance_state must only appear on rejected candidates';
