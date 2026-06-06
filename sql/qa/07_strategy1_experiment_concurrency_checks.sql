-- BigQuery Standard SQL
-- 策略 1 实验并发串号 QA
-- 在并发执行后运行，校验同一 stage 内 run_id / backtest_id 唯一性、
-- ADS 表按 run_id / backtest_id 无串号、portfolio-only 实验未改写 registry
-- 以及 resume 后无重复输出。
--
-- 文档维护：DeepSeek V4（最近更新 2026-06-03）

-- ============================================================
-- QA-CONC-1: 同 stage 内 run_id 唯一
-- ============================================================
-- 如果同 stage 内有实验使用了相同的 run_id，说明实验身份设计有误或并发隔离失败。
SELECT
  'QA-CONC-1' AS qa_id,
  stage_id,
  run_id,
  COUNT(DISTINCT experiment_id) AS experiment_count
FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status`
WHERE status IN ('succeeded', 'running', 'failed')
GROUP BY stage_id, run_id
HAVING COUNT(DISTINCT experiment_id) > 1;

-- ASSERT: 以上查询返回 0 行
ASSERT (
  (SELECT COUNT(*) FROM (
    SELECT stage_id, run_id
    FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status`
    WHERE status IN ('succeeded', 'running', 'failed')
    GROUP BY stage_id, run_id
    HAVING COUNT(DISTINCT experiment_id) > 1
  )) = 0
) AS 'QA-CONC-1: 同 stage 内 run_id 不唯一';

-- ============================================================
-- QA-CONC-2: 同 stage 内 backtest_id 唯一
-- ============================================================
SELECT
  'QA-CONC-2' AS qa_id,
  stage_id,
  backtest_id,
  COUNT(DISTINCT experiment_id) AS experiment_count
FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status`
WHERE status IN ('succeeded', 'running', 'failed')
  AND backtest_id IS NOT NULL
GROUP BY stage_id, backtest_id
HAVING COUNT(DISTINCT experiment_id) > 1;

ASSERT (
  (SELECT COUNT(*) FROM (
    SELECT stage_id, backtest_id
    FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status`
    WHERE status IN ('succeeded', 'running', 'failed')
      AND backtest_id IS NOT NULL
    GROUP BY stage_id, backtest_id
    HAVING COUNT(DISTINCT experiment_id) > 1
  )) = 0
) AS 'QA-CONC-2: 同 stage 内 backtest_id 不唯一';

-- ============================================================
-- QA-CONC-3: 同一 run_id + step_id 不存在多个 active step
-- ============================================================
SELECT
  'QA-CONC-3' AS qa_id,
  run_id,
  step_id,
  COUNT(*) AS active_count
FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status`
WHERE status = 'running'
GROUP BY run_id, step_id
HAVING COUNT(*) > 1;

ASSERT (
  (SELECT COUNT(*) FROM (
    SELECT run_id, step_id
    FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status`
    WHERE status = 'running'
    GROUP BY run_id, step_id
    HAVING COUNT(*) > 1
  )) = 0
) AS 'QA-CONC-3: 同一 run_id+step_id 存在多个 active step';

-- ============================================================
-- QA-CONC-4: 同一 backtest_id + step_id 不存在多个 active step
-- ============================================================
SELECT
  'QA-CONC-4' AS qa_id,
  backtest_id,
  step_id,
  COUNT(*) AS active_count
FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status`
WHERE status = 'running'
  AND backtest_id IS NOT NULL
GROUP BY backtest_id, step_id
HAVING COUNT(*) > 1;

ASSERT (
  (SELECT COUNT(*) FROM (
    SELECT backtest_id, step_id
    FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status`
    WHERE status = 'running'
      AND backtest_id IS NOT NULL
    GROUP BY backtest_id, step_id
    HAVING COUNT(*) > 1
  )) = 0
) AS 'QA-CONC-4: 同一 backtest_id+step_id 存在多个 active step';

-- ============================================================
-- QA-CONC-5: portfolio-only 实验未改写 prediction_run_id 的 registry selected 状态
-- ============================================================
-- portfolio-only 实验的 run_id 与 prediction_run_id 不同时，
-- 其 prediction_run_id 对应的 registry selected 模型不应被改动。
-- 断言：对每个 portfolio-only 实验的 prediction_run_id，
-- registry 中必须存在 is_selected=TRUE 且 run_id 匹配的模型。
-- 若 selected 模型缺失，说明 portfolio-only 实验误删了上游 registry。

SELECT
  'QA-CONC-5' AS qa_id,
  rs.experiment_id,
  rs.run_id,
  rs.prediction_run_id
FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status` rs
WHERE rs.experiment_type = 'portfolio_only'
  AND rs.run_id != rs.prediction_run_id;

ASSERT (
  (SELECT COUNT(*) FROM (
    SELECT DISTINCT rs.prediction_run_id
    FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status` rs
    WHERE rs.experiment_type = 'portfolio_only'
      AND rs.run_id != rs.prediction_run_id
      AND NOT EXISTS (
        SELECT 1
        FROM `data-aquarium.ashare_ads.ads_model_registry` reg
        WHERE JSON_VALUE(reg.model_params_json, '$.run_id') = rs.prediction_run_id
          AND reg.is_selected = TRUE
      )
  )) = 0
) AS 'QA-CONC-5: portfolio-only 实验的 prediction_run_id 对应 registry selected 模型缺失';

-- ============================================================
-- QA-CONC-6: ads_stock_candidate_daily 按 run_id 无串号
-- ============================================================
SELECT
  'QA-CONC-6' AS qa_id,
  run_id,
  COUNT(DISTINCT experiment_id) AS experiment_count
FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily`
WHERE experiment_id IS NOT NULL AND experiment_id != ''
GROUP BY run_id
HAVING COUNT(DISTINCT experiment_id) > 1;

ASSERT (
  (SELECT COUNT(*) FROM (
    SELECT run_id
    FROM `data-aquarium.ashare_ads.ads_stock_candidate_daily`
    WHERE experiment_id IS NOT NULL AND experiment_id != ''
    GROUP BY run_id
    HAVING COUNT(DISTINCT experiment_id) > 1
  )) = 0
) AS 'QA-CONC-6: ads_stock_candidate_daily 按 run_id 串号';

-- ============================================================
-- QA-CONC-7: ads_portfolio_target_daily 按 run_id 无串号
-- ============================================================
SELECT
  'QA-CONC-7' AS qa_id,
  run_id,
  COUNT(DISTINCT experiment_id) AS experiment_count
FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily`
WHERE experiment_id IS NOT NULL AND experiment_id != ''
GROUP BY run_id
HAVING COUNT(DISTINCT experiment_id) > 1;

ASSERT (
  (SELECT COUNT(*) FROM (
    SELECT run_id
    FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily`
    WHERE experiment_id IS NOT NULL AND experiment_id != ''
    GROUP BY run_id
    HAVING COUNT(DISTINCT experiment_id) > 1
  )) = 0
) AS 'QA-CONC-7: ads_portfolio_target_daily 按 run_id 串号';

-- ============================================================
-- QA-CONC-8: ads_order_plan_daily 按 run_id / backtest_id 无串号
-- ============================================================
SELECT
  'QA-CONC-8' AS qa_id,
  run_id,
  backtest_id,
  COUNT(DISTINCT experiment_id) AS experiment_count
FROM `data-aquarium.ashare_ads.ads_order_plan_daily`
WHERE experiment_id IS NOT NULL AND experiment_id != ''
GROUP BY run_id, backtest_id
HAVING COUNT(DISTINCT experiment_id) > 1;

ASSERT (
  (SELECT COUNT(*) FROM (
    SELECT run_id, backtest_id
    FROM `data-aquarium.ashare_ads.ads_order_plan_daily`
    WHERE experiment_id IS NOT NULL AND experiment_id != ''
    GROUP BY run_id, backtest_id
    HAVING COUNT(DISTINCT experiment_id) > 1
  )) = 0
) AS 'QA-CONC-8: ads_order_plan_daily 按 run_id/backtest_id 串号';

-- ============================================================
-- QA-CONC-9: 回测四表按 backtest_id 无串号
-- ============================================================
-- ads_backtest_trade_daily
SELECT
  'QA-CONC-9a' AS qa_id,
  backtest_id,
  COUNT(DISTINCT run_id) AS run_count
FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily`
GROUP BY backtest_id
HAVING COUNT(DISTINCT run_id) > 1;

ASSERT (
  (SELECT COUNT(*) FROM (
    SELECT backtest_id
    FROM `data-aquarium.ashare_ads.ads_backtest_trade_daily`
    GROUP BY backtest_id
    HAVING COUNT(DISTINCT run_id) > 1
  )) = 0
) AS 'QA-CONC-9a: ads_backtest_trade_daily 按 backtest_id 串号';

-- ads_backtest_position_daily
SELECT
  'QA-CONC-9b' AS qa_id,
  backtest_id,
  COUNT(DISTINCT run_id) AS run_count
FROM `data-aquarium.ashare_ads.ads_backtest_position_daily`
GROUP BY backtest_id
HAVING COUNT(DISTINCT run_id) > 1;

ASSERT (
  (SELECT COUNT(*) FROM (
    SELECT backtest_id
    FROM `data-aquarium.ashare_ads.ads_backtest_position_daily`
    GROUP BY backtest_id
    HAVING COUNT(DISTINCT run_id) > 1
  )) = 0
) AS 'QA-CONC-9b: ads_backtest_position_daily 按 backtest_id 串号';

-- ads_backtest_nav_daily
SELECT
  'QA-CONC-9c' AS qa_id,
  backtest_id,
  COUNT(DISTINCT run_id) AS run_count
FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily`
GROUP BY backtest_id
HAVING COUNT(DISTINCT run_id) > 1;

ASSERT (
  (SELECT COUNT(*) FROM (
    SELECT backtest_id
    FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily`
    GROUP BY backtest_id
    HAVING COUNT(DISTINCT run_id) > 1
  )) = 0
) AS 'QA-CONC-9c: ads_backtest_nav_daily 按 backtest_id 串号';

-- ads_backtest_summary
SELECT
  'QA-CONC-9d' AS qa_id,
  backtest_id,
  COUNT(DISTINCT run_id) AS run_count
FROM `data-aquarium.ashare_ads.ads_backtest_summary`
GROUP BY backtest_id
HAVING COUNT(DISTINCT run_id) > 1;

ASSERT (
  (SELECT COUNT(*) FROM (
    SELECT backtest_id
    FROM `data-aquarium.ashare_ads.ads_backtest_summary`
    GROUP BY backtest_id
    HAVING COUNT(DISTINCT run_id) > 1
  )) = 0
) AS 'QA-CONC-9d: ads_backtest_summary 按 backtest_id 串号';

-- ============================================================
-- QA-CONC-10: summary metrics_json 中实验身份字段完整
-- ============================================================
SELECT
  'QA-CONC-10' AS qa_id,
  backtest_id,
  run_id,
  JSON_VALUE(metrics_json, '$.experiment_id') AS experiment_id,
  JSON_VALUE(metrics_json, '$.run_id') AS summary_run_id,
  JSON_VALUE(metrics_json, '$.prediction_run_id') AS summary_prediction_run_id,
  JSON_VALUE(metrics_json, '$.backtest_id') AS summary_backtest_id,
  JSON_VALUE(metrics_json, '$.report_uri') AS report_uri,
  JSON_VALUE(metrics_json, '$.diagnosis_status') AS diagnosis_status
FROM `data-aquarium.ashare_ads.ads_backtest_summary`
WHERE metrics_json IS NOT NULL
  AND (
    JSON_VALUE(metrics_json, '$.experiment_id') IS NULL
    OR JSON_VALUE(metrics_json, '$.run_id') IS NULL
    OR JSON_VALUE(metrics_json, '$.backtest_id') IS NULL
  );

ASSERT (
  (SELECT COUNT(*) FROM (
    SELECT backtest_id
    FROM `data-aquarium.ashare_ads.ads_backtest_summary`
    WHERE metrics_json IS NOT NULL
      AND (
        JSON_VALUE(metrics_json, '$.experiment_id') IS NULL
        OR JSON_VALUE(metrics_json, '$.run_id') IS NULL
        OR JSON_VALUE(metrics_json, '$.backtest_id') IS NULL
      )
  )) = 0
) AS 'QA-CONC-10: summary metrics_json 实验身份字段不完整';

-- ============================================================
-- QA-CONC-11: report / diagnosis artifact URI 包含当前 run_id / backtest_id
-- ============================================================
SELECT
  'QA-CONC-11' AS qa_id,
  backtest_id,
  run_id,
  JSON_VALUE(metrics_json, '$.report_uri') AS report_uri,
  JSON_VALUE(metrics_json, '$.diagnosis_uri') AS diagnosis_uri
FROM `data-aquarium.ashare_ads.ads_backtest_summary`
WHERE metrics_json IS NOT NULL
  AND (
    (JSON_VALUE(metrics_json, '$.report_uri') IS NOT NULL
     AND JSON_VALUE(metrics_json, '$.report_uri') != ''
     AND INSTR(JSON_VALUE(metrics_json, '$.report_uri'), JSON_VALUE(metrics_json, '$.backtest_id')) = 0)
    OR
    (JSON_VALUE(metrics_json, '$.diagnosis_uri') IS NOT NULL
     AND JSON_VALUE(metrics_json, '$.diagnosis_uri') != ''
     AND INSTR(JSON_VALUE(metrics_json, '$.diagnosis_uri'), JSON_VALUE(metrics_json, '$.backtest_id')) = 0)
  );

ASSERT (
  (SELECT COUNT(*) FROM (
    SELECT backtest_id
    FROM `data-aquarium.ashare_ads.ads_backtest_summary`
    WHERE metrics_json IS NOT NULL
      AND (
        (JSON_VALUE(metrics_json, '$.report_uri') IS NOT NULL
         AND JSON_VALUE(metrics_json, '$.report_uri') != ''
         AND INSTR(JSON_VALUE(metrics_json, '$.report_uri'), JSON_VALUE(metrics_json, '$.backtest_id')) = 0)
        OR
        (JSON_VALUE(metrics_json, '$.diagnosis_uri') IS NOT NULL
         AND JSON_VALUE(metrics_json, '$.diagnosis_uri') != ''
         AND INSTR(JSON_VALUE(metrics_json, '$.diagnosis_uri'), JSON_VALUE(metrics_json, '$.backtest_id')) = 0)
      )
  )) = 0
) AS 'QA-CONC-11: artifact URI 缺失 backtest_id';

-- ============================================================
-- QA-CONC-12: failed 实验 resume 后没有重复 ADS 输出
-- ============================================================
-- 检查：同一 run_id 在 status 表中有多个 succeeded step 记录，
-- 排除正常的 retrain 覆盖（force_replace=TRUE），其余视为重复。
SELECT
  'QA-CONC-12' AS qa_id,
  run_id,
  step_id,
  COUNT(*) AS succeeded_count,
  LOGICAL_OR(force_replace) AS has_force_replace
FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status`
WHERE status = 'succeeded'
GROUP BY run_id, step_id
HAVING COUNT(*) > 1 AND NOT LOGICAL_OR(force_replace);

ASSERT (
  (SELECT COUNT(*) FROM (
    SELECT run_id, step_id
    FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status`
    WHERE status = 'succeeded'
    GROUP BY run_id, step_id
    HAVING COUNT(*) > 1 AND NOT LOGICAL_OR(force_replace)
  )) = 0
) AS 'QA-CONC-12: failed 实验 resume 后存在重复输出（非 force_replace）';

-- ============================================================
-- 汇总
-- ============================================================
SELECT 'ALL QA-CONC ASSERTIONS PASSED' AS result;
