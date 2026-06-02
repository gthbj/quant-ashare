-- BigQuery Standard SQL · Strategy 1 Model Quality Diagnosis QA
-- 12: 断言诊断 artifact 状态、manifest、关键指标非空和结论字段合法。
-- 必须在 diagnose_model_quality.py 之后执行。

DECLARE p_run_id STRING DEFAULT 's1_bqml_livepool_20260602_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_backtest_id STRING DEFAULT 'bt_s1_bqml_livepool_20260602_01';
DECLARE p_train_start DATE DEFAULT DATE '2019-04-03';
DECLARE p_train_end DATE DEFAULT DATE '2023-12-31';
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
  SELECT COUNTIF(split_tag = 'valid' AND n_days >= 100) = 1
     AND COUNTIF(split_tag = 'test'  AND n_days >= 100) = 1
  FROM (
    SELECT s.split_tag AS split_tag, COUNT(DISTINCT predict_date) AS n_days
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

-- ============================================================
-- PRD-20260602-05 预测池口径 QA
-- ============================================================

-- QA-POOL-1: train rows 全部满足 sample_trainable_default=TRUE
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(NOT s.sample_trainable_default) = 0
  FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
  JOIN `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
    ON s.trade_date = tp.trade_date AND s.sec_code = tp.sec_code
   AND s.feature_version = tp.feature_version AND s.label_version = tp.label_version
  WHERE tp.run_id = p_run_id AND tp.split_tag = 'train'
    AND tp.trade_date BETWEEN p_train_start AND p_train_end
) AS 'QA-POOL-1: train rows must all satisfy sample_trainable_default=TRUE';

-- QA-POOL-2: valid/test prediction rows 全部满足 predict_live_available_mask
ASSERT (
  SELECT COUNTIF(NOT (
    COALESCE(s.in_universe_default, FALSE)
    AND COALESCE(s.has_full_history_60d, FALSE)
    AND COALESCE(s.has_valuation_data, FALSE)
  )) = 0
  FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
  JOIN `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
    ON s.trade_date = tp.trade_date AND s.sec_code = tp.sec_code
   AND s.feature_version = tp.feature_version AND s.label_version = tp.label_version
  WHERE tp.run_id = p_run_id AND tp.split_tag IN ('valid', 'test')
    AND tp.trade_date BETWEEN p_valid_start AND p_test_end
) AS 'QA-POOL-2: valid/test rows must all satisfy predict_live_available_mask';

-- QA-POOL-3: valid/test prediction rows 不要求 label_entry_tradable 或 label_valid_5d
-- 如果全部满足反而说明预测池可能仍被未来字段过滤
ASSERT (
  SELECT COUNTIF(NOT s.label_entry_tradable AND NOT s.label_valid_5d) > 0
  FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
  JOIN `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
    ON s.trade_date = tp.trade_date AND s.sec_code = tp.sec_code
   AND s.feature_version = tp.feature_version AND s.label_version = tp.label_version
  WHERE tp.run_id = p_run_id AND tp.split_tag IN ('valid', 'test')
    AND tp.trade_date BETWEEN p_valid_start AND p_test_end
) AS 'QA-POOL-3: valid/test pool must contain rows failing label_entry_tradable or label_valid_5d (proves live-available mask is active)';

-- QA-POOL-4: train target_label 和 target_return 不得为空
ASSERT (
  SELECT COUNT(*) > 0 AND COUNTIF(tp.target_label IS NULL OR tp.target_return IS NULL) = 0
  FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
  WHERE tp.run_id = p_run_id AND tp.split_tag = 'train'
    AND tp.trade_date BETWEEN p_train_start AND p_train_end
) AS 'QA-POOL-4: train target_label and target_return must not be NULL';

-- QA-POOL-5: valid/test prediction panel 行数 >= DWS 同条件 legacy trainable 行数
ASSERT (
  SELECT panel_rows >= legacy_trainable
  FROM (
    SELECT
      (SELECT COUNT(*)
       FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
       WHERE tp.run_id = p_run_id AND tp.split_tag IN ('valid', 'test')
         AND tp.trade_date BETWEEN p_valid_start AND p_test_end) AS panel_rows,
      (SELECT COUNT(*)
       FROM `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
       WHERE s.trade_date BETWEEN p_valid_start AND p_test_end
         AND s.split_tag IN ('valid', 'test')
         AND s.sample_trainable_default
         AND s.feature_version = (
           SELECT ANY_VALUE(tp.feature_version)
           FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
           WHERE tp.run_id = p_run_id LIMIT 1)) AS legacy_trainable
  )
) AS 'QA-POOL-5: valid/test prediction panel rows must be >= DWS legacy trainable rows';

-- QA-POOL-6: valid/test panel 包含 live-only 行（证明 live-available mask 生效）
ASSERT (
  SELECT COUNTIF(
    COALESCE(s.in_universe_default, FALSE)
    AND COALESCE(s.has_full_history_60d, FALSE)
    AND COALESCE(s.has_valuation_data, FALSE)
    AND NOT s.sample_trainable_default
  ) > 0
  FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
  JOIN `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
    ON s.trade_date = tp.trade_date AND s.sec_code = tp.sec_code
   AND s.feature_version = tp.feature_version AND s.label_version = tp.label_version
  WHERE tp.run_id = p_run_id AND tp.split_tag IN ('valid', 'test')
    AND tp.trade_date BETWEEN p_valid_start AND p_test_end
) AS 'QA-POOL-6: valid/test panel must contain live-only rows (live-available mask is active)';
