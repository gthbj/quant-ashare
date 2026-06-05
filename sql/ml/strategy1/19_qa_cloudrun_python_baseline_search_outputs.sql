-- BigQuery Standard SQL · Strategy 1 Cloud Run Python baseline search QA
-- 19: 断言 PRD_20260605_04 LightGBM / Cloud Run Python search 产物和 acceptance 元数据。

DECLARE p_search_id STRING DEFAULT 'cloudrun_python_lgbm_pvfq_n30_bw_h5_20260605_01';
DECLARE p_source_run_id STRING DEFAULT 's1_cloudrun_python_lgbm_pvfq_n30_bw_h5_20260605_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_expected_candidate_count INT64 DEFAULT 40;
DECLARE p_expected_candidate_parallelism INT64 DEFAULT 40;
DECLARE p_expected_model_family STRING DEFAULT 'lightgbm_gbdt';
DECLARE p_expected_model_search_wave_no INT64 DEFAULT 2;
DECLARE p_top_k INT64 DEFAULT 5;
DECLARE p_test_reuse_wave_no INT64 DEFAULT 2;
DECLARE p_acceptance_contract_version STRING DEFAULT 'model_acceptance_contract_v1';

-- QA-PY-1: Top-K registry 记录必须完整追溯 search/source/candidate_count。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id)
    AND LOGICAL_AND(JSON_VALUE(reg.metrics_json, '$.source_run_id') = p_source_run_id)
    AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.work_unit_count') AS INT64) = p_expected_candidate_count)
    AND LOGICAL_AND(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.succeeded_task_count') AS INT64) = p_expected_candidate_count)
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-PY-1: Top-K registry rows must record search_id, source_run_id and expected candidate_count';

-- QA-PY-2: 本轮必须是 Cloud Run Python LightGBM 搜索，且 task fan-out 不扫 BigQuery 全量训练面板。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND COUNTIF(JSON_VALUE(reg.metrics_json, '$.task_fanout_mode') != 'task_fanout') = 0
    AND COUNTIF(JSON_VALUE(reg.metrics_json, '$.model_backend') != 'cloud_run_python') = 0
    AND COUNTIF(JSON_VALUE(reg.metrics_json, '$.model_family') != p_expected_model_family) = 0
    AND COUNTIF(JSON_VALUE(reg.metrics_json, '$.model_library') != 'lightgbm') = 0
    AND COUNTIF(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.model_search_wave_no') AS INT64) != p_expected_model_search_wave_no) = 0
    AND COUNTIF(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.candidate_parallelism_resolved') AS INT64) != p_expected_candidate_parallelism) = 0
    AND COUNTIF(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.candidate_task_bq_forbidden_table_query_count') AS INT64) != 0) = 0
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-PY-2: Top-K must be Cloud Run Python LightGBM search and candidate tasks must not scan forbidden BQ tables';

-- QA-PY-3: matrix 和 split 边界必须固定到 PRD04 口径。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND COUNTIF(JSON_VALUE(reg.metrics_json, '$.data_end_date') != '2026-04-30') = 0
    AND COUNTIF(JSON_VALUE(reg.metrics_json, '$.final_holdout_start_date') != '2026-01-05') = 0
    AND COUNTIF(JSON_VALUE(reg.metrics_json, '$.final_holdout_end_date') != '2026-04-30') = 0
    AND COUNTIF(reg.train_start_date != DATE '2019-04-03') = 0
    AND COUNTIF(reg.train_end_date != DATE '2023-12-31') = 0
    AND COUNTIF(reg.valid_start_date != DATE '2024-01-01') = 0
    AND COUNTIF(reg.valid_end_date != DATE '2024-12-31') = 0
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-PY-3: matrix data_end and split boundaries must match PRD04';

-- QA-PY-4: Top-K 排名不得使用 test/final_holdout，且必须有 CV confirmation 证据。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND COUNTIF(JSON_VALUE(reg.metrics_json, '$.shortlist_ranking_uses_test_metrics') != 'false') = 0
    AND COUNTIF(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.shortlist_rank_valid_only') AS INT64) IS NULL) = 0
    AND COUNTIF(JSON_VALUE(reg.metrics_json, '$.cv_confirmation_status') IS NULL) = 0
    AND COUNTIF(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.cv_fold_count') AS INT64) < 3) = 0
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-PY-4: Top-K shortlist must be CV+valid based and not use test metrics';

-- QA-PY-5: Top-K 候选报告和诊断均 uploaded。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND COUNTIF(JSON_VALUE(bs.metrics_json, '$.report_upload_status') != 'uploaded') = 0
    AND COUNTIF(JSON_VALUE(bs.metrics_json, '$.model_diagnosis_upload_status') != 'uploaded') = 0
    AND COUNTIF(NOT STARTS_WITH(JSON_VALUE(bs.metrics_json, '$.report_uri'), 'gs://')) = 0
    AND COUNTIF(NOT STARTS_WITH(JSON_VALUE(bs.metrics_json, '$.model_diagnosis_uri'), 'gs://')) = 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  JOIN `data-aquarium.ashare_ads.ads_model_registry` AS reg
    ON reg.model_id = bs.model_id
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-PY-5: Top-K candidates must have uploaded report and diagnosis artifacts';

-- QA-PY-6: acceptance 状态必须互斥完整并追溯共享契约。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND COUNTIF(JSON_VALUE(reg.metrics_json, '$.native_acceptance_status') NOT IN (
      'accepted', 'rejected', 'needs_more_evidence', 'failed'
    )) = 0
    AND COUNTIF(JSON_VALUE(reg.metrics_json, '$.native_acceptance_reason') IS NULL) = 0
    AND COUNTIF(JSON_VALUE(reg.metrics_json, '$.acceptance_contract_version') != p_acceptance_contract_version) = 0
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-PY-6: acceptance status must be terminal and contract-versioned';

-- QA-PY-7: accepted 候选必须满足 PRD04 hard gates。
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
      JSON_VALUE(reg.metrics_json, '$.cv_confirmation_status') != 'passed'
      OR JSON_VALUE(reg.metrics_json, '$.valid_signal_status') != 'stable'
      OR SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.oriented_valid_rank_ic_mean') AS FLOAT64) <= 0
      OR SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.valid_top_minus_bottom_fwd_ret_mean') AS FLOAT64) <= 0
      OR SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_rank_ic_mean') AS FLOAT64) <= 0
      OR SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_top_minus_bottom_fwd_ret_mean') AS FLOAT64) <= 0
      OR SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_year_excess_return') AS FLOAT64) <= 0
      OR bs.excess_return <= 0
      OR bs.total_return <= 0
      OR bs.sharpe < 0.70
      OR bs.max_drawdown < -0.25
      OR SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.final_holdout_excess_return') AS FLOAT64) <= -0.05
      OR SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.final_holdout_total_return') AS FLOAT64) <= -0.08
    )
) AS 'QA-PY-7: accepted Cloud Run Python candidates must satisfy PRD04 gates';

-- QA-PY-8: needs_more_evidence 不得被登记为正式 baseline。
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
    AND JSON_VALUE(reg.metrics_json, '$.native_acceptance_status') = 'needs_more_evidence'
    AND JSON_VALUE(reg.metrics_json, '$.baseline_id') = 'cloud_run_python_baseline_v1'
) AS 'QA-PY-8: needs_more_evidence candidates must not be registered as cloud_run_python_baseline_v1';

-- QA-PY-9: wave 2+ 复用 2025 test 必须记录 owner approval ref，且 wave_no 与调用参数一致。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND COUNTIF(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_reuse_wave_no') AS INT64) != p_test_reuse_wave_no) = 0
    AND COUNTIF(NULLIF(JSON_VALUE(reg.metrics_json, '$.test_reuse_approval_ref'), '') IS NULL) = 0
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-PY-9: test reuse wave and approval ref must be recorded';

-- QA-PY-10: final_holdout 小幅为负但未触发 hard reject 时，必须写 holdout_watch_flag。
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
    AND JSON_VALUE(reg.metrics_json, '$.native_acceptance_status') = 'accepted'
    AND (
      SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.final_holdout_excess_return') AS FLOAT64) < 0
      OR SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.final_holdout_total_return') AS FLOAT64) < 0
    )
    AND JSON_VALUE(reg.metrics_json, '$.holdout_watch_flag') != 'true'
) AS 'QA-PY-10: accepted candidates with negative final_holdout observation must set holdout_watch_flag';
