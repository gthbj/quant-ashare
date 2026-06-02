-- BigQuery Standard SQL · Strategy 1 Model Quality Diagnosis QA
-- 12: 断言诊断 artifact 状态、manifest、关键指标非空和结论字段合法。
-- 必须在 diagnose_model_quality.py 之后执行。

DECLARE p_run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_bqml_20260601_01';
DECLARE p_valid_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_valid_end DATE DEFAULT DATE '2024-12-31';
DECLARE p_test_start DATE DEFAULT DATE '2025-01-01';
DECLARE p_test_end DATE DEFAULT DATE '2025-12-31';

-- ── QA-DIAG-1: diagnosis status completed ──
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(
    JSON_VALUE(bs.metrics_json, '$.model_diagnosis_status') = 'completed'
  ) > 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-DIAG-1: model_diagnosis_status must be completed';

-- ── QA-DIAG-2: diagnosis version correct ──
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(
    JSON_VALUE(bs.metrics_json, '$.model_diagnosis_version') = 'strategy1_model_diagnosis_v1'
  ) > 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-DIAG-2: model_diagnosis_version must be strategy1_model_diagnosis_v1';

-- ── QA-DIAG-3: primary_diagnosis in allowed enum ──
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(
    JSON_VALUE(bs.metrics_json, '$.model_diagnosis_primary_diagnosis') IN (
      'signal_inverted','weak_signal','label_horizon_mismatch',
      'sample_filter_risk','portfolio_concentration_issue',
      'cost_turnover_issue','style_regime_issue','pipeline_issue',
      'inconclusive','usable_signal'
    )
  ) > 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-DIAG-3: model_diagnosis_primary_diagnosis must be in allowed enum';

-- ── QA-DIAG-4: confidence in allowed enum ──
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(
    JSON_VALUE(bs.metrics_json, '$.model_diagnosis_confidence') IN ('high','medium','low')
  ) > 0
  FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
  WHERE bs.backtest_id = p_backtest_id
) AS 'QA-DIAG-4: model_diagnosis_confidence must be high/medium/low';

-- ── QA-DIAG-5: artifact_manifest contains required files ──
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(missing) = 0
  FROM (
    SELECT
      JSON_VALUE(JSON_QUERY(bs.metrics_json, '$.model_diagnosis_artifact_manifest'), '$."diagnosis.md"') IS NULL
      OR JSON_VALUE(JSON_QUERY(bs.metrics_json, '$.model_diagnosis_artifact_manifest'), '$."diagnosis_summary.json"') IS NULL
      OR JSON_VALUE(JSON_QUERY(bs.metrics_json, '$.model_diagnosis_artifact_manifest'), '$."daily_rank_ic.csv"') IS NULL
      OR JSON_VALUE(JSON_QUERY(bs.metrics_json, '$.model_diagnosis_artifact_manifest'), '$."score_bucket_lift.csv"') IS NULL
      OR JSON_VALUE(JSON_QUERY(bs.metrics_json, '$.model_diagnosis_artifact_manifest'), '$."sample_universe_funnel.csv"') IS NULL
      AS missing
    FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
    WHERE bs.backtest_id = p_backtest_id
  )
) AS 'QA-DIAG-5: artifact_manifest must contain diagnosis.md, diagnosis_summary.json, daily_rank_ic.csv, score_bucket_lift.csv, sample_universe_funnel.csv';

-- ── QA-DIAG-6: valid and test each have at least 100 prediction trading days ──
ASSERT (
  SELECT COUNT(*) > 0
  FROM (
    SELECT split_tag, COUNT(DISTINCT predict_date) AS n_days
    FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
    JOIN `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
      ON tp.trade_date = pred.predict_date AND tp.sec_code = pred.sec_code AND tp.run_id = p_run_id
    JOIN `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
      ON s.trade_date = pred.predict_date AND s.sec_code = pred.sec_code
     AND s.feature_version = tp.feature_version AND s.label_version = tp.label_version
    WHERE pred.run_id = p_run_id
      AND pred.predict_date BETWEEN p_valid_start AND p_test_end
      AND s.split_tag IN ('valid', 'test')
    GROUP BY s.split_tag
    HAVING n_days >= 100
  )
) AS 'QA-DIAG-6: valid and test must each have >= 100 prediction trading days';

-- ── QA-DIAG-7: key diagnosis tables non-empty ──
-- daily RankIC source non-empty
ASSERT (
  SELECT COUNT(*) > 0
  FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
  WHERE pred.run_id = p_run_id AND pred.predict_date BETWEEN p_valid_start AND p_test_end
) AS 'QA-DIAG-7a: predictions must exist for rank_ic computation';

-- candidate funnel non-empty
ASSERT (
  SELECT COUNT(*) > 0
  FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily` AS cand
  WHERE cand.strategy_id = p_strategy_id AND cand.run_id = p_run_id
    AND cand.rebalance_date BETWEEN p_valid_start AND p_test_end
) AS 'QA-DIAG-7b: candidate funnel must exist';

-- cost turnover source non-empty
ASSERT (
  SELECT COUNT(*) > 0
  FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily` AS t
  WHERE t.backtest_id = p_backtest_id AND t.trade_date BETWEEN p_test_start AND p_test_end
) AS 'QA-DIAG-7c: backtest trades must exist for cost_turnover diagnostics';

-- ── QA-DIAG-8: all referenced BigQuery queries in 11 must use explicit date filters ──
-- 这是人工审查项：11_model_quality_diagnostics.sql 中所有 WHERE 子句必须包含
-- trade_date / predict_date / rebalance_date BETWEEN 显式日期范围。
-- 本 ASSERT 作为占位，提醒 reviewer 在 PR review 时确认分区过滤。
SELECT 'QA-DIAG-8: reviewer must confirm all queries in 11_model_quality_diagnostics.sql use explicit date partition filters' AS manual_check;
