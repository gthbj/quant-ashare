-- BigQuery Standard SQL · Strategy 1 Cloud Run Python baseline search QA
-- 19: 断言 PRD_20260605_04 LightGBM / Cloud Run Python search 产物和 acceptance 元数据。

DECLARE p_search_id STRING DEFAULT 'cloudrun_python_lgbm_pvfq_n30_bw_h5_20260605_01';
DECLARE p_source_run_id STRING DEFAULT 's1_cloudrun_python_lgbm_pvfq_n30_bw_h5_20260605_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_expected_candidate_count INT64 DEFAULT 40;
DECLARE p_expected_candidate_parallelism INT64 DEFAULT 20;
DECLARE p_expected_candidate_task_cpu INT64 DEFAULT 2;
DECLARE p_expected_candidate_task_memory STRING DEFAULT '8Gi';
DECLARE p_expected_model_family STRING DEFAULT 'lightgbm_gbdt';
DECLARE p_expected_model_search_wave_no INT64 DEFAULT 2;
DECLARE p_top_k INT64 DEFAULT 5;
DECLARE p_test_reuse_wave_no INT64 DEFAULT 2;
DECLARE p_acceptance_contract_version STRING DEFAULT 'model_acceptance_contract_v1';
DECLARE p_valid_start_date DATE DEFAULT DATE '2024-01-02';
DECLARE p_valid_end_date DATE DEFAULT DATE '2024-12-31';
DECLARE p_test_start_date DATE DEFAULT DATE '2025-01-02';
DECLARE p_test_end_date DATE DEFAULT DATE '2025-12-31';
DECLARE p_final_holdout_start_date DATE DEFAULT DATE '2026-01-05';
DECLARE p_final_holdout_end_date DATE DEFAULT DATE '2026-04-30';
DECLARE p_data_end_date DATE DEFAULT DATE '2026-04-30';
DECLARE p_min_valid_rank_ic FLOAT64 DEFAULT 0.0;
DECLARE p_min_valid_top_minus_bottom_fwd_ret FLOAT64 DEFAULT 0.0;
DECLARE p_min_test_rank_ic FLOAT64 DEFAULT 0.0;
DECLARE p_min_test_top_minus_bottom_fwd_ret FLOAT64 DEFAULT 0.0;
DECLARE p_min_test_year_excess_return_vs_000852 FLOAT64 DEFAULT 0.0;
DECLARE p_min_overall_excess_return_vs_000852 FLOAT64 DEFAULT 0.0;
DECLARE p_min_total_return FLOAT64 DEFAULT 0.0;
DECLARE p_min_sharpe FLOAT64 DEFAULT 0.70;
DECLARE p_min_max_drawdown FLOAT64 DEFAULT -0.25;
DECLARE p_min_final_holdout_excess_return_vs_000852 FLOAT64 DEFAULT -0.05;
DECLARE p_min_final_holdout_total_return FLOAT64 DEFAULT -0.08;
DECLARE p_min_final_holdout_trading_days INT64 DEFAULT 40;
DECLARE p_required_valid_signal_status STRING DEFAULT 'stable';
DECLARE p_required_cv_confirmation_status STRING DEFAULT 'passed';
DECLARE p_final_holdout_required_after_wave INT64 DEFAULT 3;
DECLARE p_final_holdout_passed_status STRING DEFAULT 'passed';

-- The DECLARE defaults are standalone fallbacks, not the source of truth.
-- Production orchestrators must inject these values from
-- configs/strategy1/model_acceptance_contract_v1.yml.
CREATE TEMP FUNCTION qa_required(condition BOOL) AS (IFNULL(condition, FALSE));

-- QA-PY-1: Top-K registry 记录必须完整追溯 search/source/candidate_count。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.source_run_id') = p_source_run_id))
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.work_unit_count') AS INT64) = p_expected_candidate_count))
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.succeeded_task_count') AS INT64) = p_expected_candidate_count))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-PY-1: Top-K registry rows must record search_id, source_run_id and expected candidate_count';

-- QA-PY-2: 本轮必须是 Cloud Run Python LightGBM 搜索，且 task fan-out 不扫 BigQuery 全量训练面板。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.task_fanout_mode') = 'task_fanout'))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.model_backend') = 'cloud_run_python'))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.model_family') = p_expected_model_family))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.model_library') = 'lightgbm'))
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.model_search_wave_no') AS INT64) = p_expected_model_search_wave_no))
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.candidate_parallelism_resolved') AS INT64) = p_expected_candidate_parallelism))
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.candidate_task_cpu') AS INT64) = p_expected_candidate_task_cpu))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.candidate_task_memory') = p_expected_candidate_task_memory))
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.candidate_task_bq_forbidden_table_query_count') AS INT64) = 0))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-PY-2: Top-K must be Cloud Run Python LightGBM search and candidate tasks must not scan forbidden BQ tables';

-- QA-PY-3: matrix 和 split 边界必须固定到 PRD04 口径。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.data_end_date') = CAST(p_data_end_date AS STRING)))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.final_holdout_start_date') = CAST(p_final_holdout_start_date AS STRING)))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.final_holdout_end_date') = CAST(p_final_holdout_end_date AS STRING)))
    AND LOGICAL_AND(qa_required(reg.train_start_date = DATE '2019-04-03'))
    AND LOGICAL_AND(qa_required(reg.train_end_date = DATE '2023-12-31'))
    AND LOGICAL_AND(qa_required(reg.valid_start_date = p_valid_start_date))
    AND LOGICAL_AND(qa_required(reg.valid_end_date = p_valid_end_date))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.model_params_json, '$.test_start_date') = CAST(p_test_start_date AS STRING)))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.model_params_json, '$.test_end_date') = CAST(p_test_end_date AS STRING)))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-PY-3: matrix data_end and split boundaries must match PRD04';

-- QA-PY-4: Top-K 排名不得使用 test/final_holdout，且必须有 CV confirmation 证据。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.shortlist_ranking_uses_test_metrics') = 'false'))
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.shortlist_rank_valid_only') AS INT64) IS NOT NULL))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.cv_confirmation_status') IS NOT NULL))
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.cv_fold_count') AS INT64) >= 3))
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
) AS 'QA-PY-4: Top-K shortlist must be CV+valid based and not use test metrics';

-- QA-PY-5: Top-K 候选报告和诊断均 uploaded。
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
) AS 'QA-PY-5: Top-K candidates must have uploaded report and diagnosis artifacts';

-- QA-PY-6: acceptance 状态必须互斥完整并追溯共享契约。
ASSERT (
  SELECT COUNT(*) = p_top_k
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.native_acceptance_status') IN (
      'accepted', 'rejected', 'needs_more_evidence', 'failed'
    )))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.native_acceptance_reason') IS NOT NULL))
    AND LOGICAL_AND(qa_required(JSON_VALUE(reg.metrics_json, '$.acceptance_contract_version') = p_acceptance_contract_version))
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
      NOT IFNULL(JSON_VALUE(reg.metrics_json, '$.cv_confirmation_status') = p_required_cv_confirmation_status, FALSE)
      OR NOT IFNULL(JSON_VALUE(reg.metrics_json, '$.valid_signal_status') = p_required_valid_signal_status, FALSE)
      OR NOT IFNULL(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.oriented_valid_rank_ic_mean') AS FLOAT64) > p_min_valid_rank_ic, FALSE)
      OR NOT IFNULL(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.valid_top_minus_bottom_fwd_ret_mean') AS FLOAT64) > p_min_valid_top_minus_bottom_fwd_ret, FALSE)
      OR NOT IFNULL(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_rank_ic_mean') AS FLOAT64) > p_min_test_rank_ic, FALSE)
      OR NOT IFNULL(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_top_minus_bottom_fwd_ret_mean') AS FLOAT64) > p_min_test_top_minus_bottom_fwd_ret, FALSE)
      OR NOT IFNULL(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_year_excess_return') AS FLOAT64) > p_min_test_year_excess_return_vs_000852, FALSE)
      OR NOT IFNULL(bs.excess_return > p_min_overall_excess_return_vs_000852, FALSE)
      OR NOT IFNULL(bs.total_return > p_min_total_return, FALSE)
      OR NOT IFNULL(bs.sharpe >= p_min_sharpe, FALSE)
      OR NOT IFNULL(bs.max_drawdown >= p_min_max_drawdown, FALSE)
      OR NOT IFNULL(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.final_holdout_trading_days') AS INT64) >= p_min_final_holdout_trading_days, FALSE)
      OR NOT IFNULL(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.final_holdout_excess_return') AS FLOAT64) > p_min_final_holdout_excess_return_vs_000852, FALSE)
      OR NOT IFNULL(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.final_holdout_total_return') AS FLOAT64) > p_min_final_holdout_total_return, FALSE)
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
    AND LOGICAL_AND(qa_required(SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_reuse_wave_no') AS INT64) = p_test_reuse_wave_no))
    AND LOGICAL_AND(qa_required(NULLIF(JSON_VALUE(reg.metrics_json, '$.test_reuse_approval_ref'), '') IS NOT NULL))
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
    AND NOT IFNULL(JSON_VALUE(reg.metrics_json, '$.holdout_watch_flag') = 'true', FALSE)
) AS 'QA-PY-10: accepted candidates with negative final_holdout observation must set holdout_watch_flag';

-- QA-PY-11: 产物不得超过本轮数据截止日。
ASSERT (
  WITH topk AS (
    SELECT
      JSON_VALUE(reg.model_params_json, '$.run_id') AS run_id,
      bs.backtest_id
    FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
    LEFT JOIN `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
      ON bs.model_id = reg.model_id
    WHERE reg.strategy_id = p_strategy_id
      AND reg.status = 'selected'
      AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
  ),
  violations AS (
    SELECT 'prediction' AS source_name, COUNT(*) AS n
    FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
    JOIN topk USING (run_id)
    WHERE pred.predict_date > p_data_end_date
    UNION ALL
    SELECT 'nav', COUNT(*)
    FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS nav
    JOIN topk USING (run_id)
    WHERE nav.trade_date > p_data_end_date
    UNION ALL
    SELECT 'trade', COUNT(*)
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS trade
    JOIN topk USING (run_id)
    WHERE trade.trade_date > p_data_end_date
    UNION ALL
    SELECT 'position', COUNT(*)
    FROM `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
    JOIN topk USING (run_id)
    WHERE pos.trade_date > p_data_end_date
    UNION ALL
    SELECT 'summary', COUNT(*)
    FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
    JOIN topk USING (backtest_id)
    WHERE bs.end_date > p_data_end_date
  )
  SELECT SUM(n) = 0 FROM violations
) AS 'QA-PY-11: prediction/backtest artifacts must not exceed data_end_date';

-- QA-PY-12: unmatched_acceptance_state 只能作为 rejected 兜底原因。
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
    AND JSON_VALUE(reg.metrics_json, '$.native_acceptance_reason') = 'unmatched_acceptance_state'
    AND JSON_VALUE(reg.metrics_json, '$.native_acceptance_status') != 'rejected'
) AS 'QA-PY-12: unmatched_acceptance_state must only appear on rejected candidates';

-- QA-PY-13: 超过契约允许的 test reuse 波次后，accepted 必须有 final holdout passed 证据。
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
  WHERE reg.strategy_id = p_strategy_id
    AND reg.status = 'selected'
    AND JSON_VALUE(reg.metrics_json, '$.search_id') = p_search_id
    AND SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_reuse_wave_no') AS INT64) > p_final_holdout_required_after_wave
    AND JSON_VALUE(reg.metrics_json, '$.native_acceptance_status') = 'accepted'
    AND IFNULL(JSON_VALUE(reg.metrics_json, '$.final_holdout_status'), '') != p_final_holdout_passed_status
) AS 'QA-PY-13: wave above contract threshold cannot be accepted without final holdout passed evidence';
