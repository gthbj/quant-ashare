-- BigQuery Standard SQL · OQ-005 Pipeline Status Observability
-- 基于 ashare_meta.pipeline_run / pipeline_task_status 的观测视图。
--
-- 使用方式：
--   bq query --use_legacy_sql=false --location=asia-east2 < 01_pipeline_status_views.sql
-- 或直接在 BigQuery Console 中执行。

-- ────────────────────────────────────────────────────────────────────────────
-- 1. 最近 DAG run 状态概览
-- ────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW `data-aquarium.ashare_meta.v_pipeline_recent_runs` AS
SELECT
  pipeline_run_id,
  dag_id,
  business_date,
  date_from,
  date_to,
  run_label,
  warehouse_mode,
  status,
  started_at,
  finished_at,
  TIMESTAMP_DIFF(COALESCE(finished_at, CURRENT_TIMESTAMP()), started_at, SECOND) AS duration_seconds,
  error_summary,
  -- 窗口范围
  CONCAT(COALESCE(date_from, business_date), ' → ', COALESCE(date_to, business_date)) AS window_range
FROM `data-aquarium.ashare_meta.pipeline_run`
ORDER BY started_at DESC
LIMIT 50;

-- ────────────────────────────────────────────────────────────────────────────
-- 2. 失败 task 明细（含 BQ job id、Airflow log URL）
-- ────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW `data-aquarium.ashare_meta.v_pipeline_failed_tasks` AS
SELECT
  t.pipeline_run_id,
  t.task_id,
  t.task_type,
  t.business_date,
  t.warehouse_mode,
  t.status,
  t.error_summary,
  t.bigquery_job_id,
  t.bigquery_job_url,
  t.airflow_log_url,
  t.cloud_run_execution_id,
  t.cloud_run_execution_url,
  t.started_at,
  t.finished_at,
  r.run_label,
  r.date_from,
  r.date_to
FROM `data-aquarium.ashare_meta.pipeline_task_status` t
JOIN `data-aquarium.ashare_meta.pipeline_run` r
  ON t.pipeline_run_id = r.pipeline_run_id
WHERE t.status = 'failed'
ORDER BY t.finished_at DESC
LIMIT 100;

-- ────────────────────────────────────────────────────────────────────────────
-- 3. QA 失败明细（QA-WIN-* 断言）
-- ────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW `data-aquarium.ashare_meta.v_pipeline_qa_failures` AS
SELECT
  t.pipeline_run_id,
  t.task_id,
  t.business_date,
  t.warehouse_mode,
  t.error_summary,
  t.bigquery_job_url,
  t.airflow_log_url,
  t.started_at,
  t.finished_at,
  r.run_label,
  r.date_from,
  r.date_to
FROM `data-aquarium.ashare_meta.pipeline_task_status` t
JOIN `data-aquarium.ashare_meta.pipeline_run` r
  ON t.pipeline_run_id = r.pipeline_run_id
WHERE t.status = 'failed'
  AND (t.task_id LIKE '%qa%' OR t.task_id LIKE '%checks%' OR t.task_id LIKE '%readiness%')
ORDER BY t.finished_at DESC
LIMIT 100;

-- ────────────────────────────────────────────────────────────────────────────
-- 4. Cloud Run ingestion 失败明细
-- ────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW `data-aquarium.ashare_meta.v_ingestion_failures` AS
SELECT
  ingestion_run_id,
  endpoint,
  source_system,
  business_date_start,
  business_date_end,
  partition_date,
  status,
  error_summary,
  gcs_uri,
  row_count,
  started_at,
  finished_at,
  TIMESTAMP_DIFF(COALESCE(finished_at, CURRENT_TIMESTAMP()), started_at, SECOND) AS duration_seconds
FROM `data-aquarium.ashare_meta.ingestion_run`
WHERE status IN ('failed', 'empty_return')
ORDER BY started_at DESC
LIMIT 100;

-- ────────────────────────────────────────────────────────────────────────────
-- 5. 每日 pipeline 健康仪表盘
-- ────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW `data-aquarium.ashare_meta.v_pipeline_daily_health` AS
WITH latest_runs AS (
  SELECT
    business_date,
    warehouse_mode,
    status,
    started_at,
    finished_at,
    ROW_NUMBER() OVER (PARTITION BY business_date, warehouse_mode ORDER BY started_at DESC) AS rn
  FROM `data-aquarium.ashare_meta.pipeline_run`
  WHERE started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
),
task_summary AS (
  SELECT
    r.business_date,
    r.warehouse_mode,
    r.pipeline_run_id,
    COUNTIF(t.status = 'success') AS tasks_success,
    COUNTIF(t.status = 'failed') AS tasks_failed,
    COUNTIF(t.status = 'skipped') AS tasks_skipped,
    COUNTIF(t.status = 'running') AS tasks_running,
    COUNT(*) AS tasks_total
  FROM `data-aquarium.ashare_meta.pipeline_run` r
  JOIN `data-aquarium.ashare_meta.pipeline_task_status` t
    ON r.pipeline_run_id = t.pipeline_run_id
  WHERE r.started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  GROUP BY r.business_date, r.warehouse_mode, r.pipeline_run_id
)
SELECT
  lr.business_date,
  lr.warehouse_mode,
  lr.status AS run_status,
  ts.tasks_success,
  ts.tasks_failed,
  ts.tasks_skipped,
  ts.tasks_running,
  ts.tasks_total,
  lr.started_at,
  lr.finished_at,
  TIMESTAMP_DIFF(COALESCE(lr.finished_at, CURRENT_TIMESTAMP()), lr.started_at, SECOND) AS duration_seconds
FROM latest_runs lr
LEFT JOIN task_summary ts
  ON lr.business_date = ts.business_date
  AND lr.warehouse_mode = ts.warehouse_mode
WHERE lr.rn = 1
ORDER BY lr.business_date DESC, lr.warehouse_mode;

-- ────────────────────────────────────────────────────────────────────────────
-- 6. 最近 24 小时异常摘要（供告警查询）
-- ────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW `data-aquarium.ashare_meta.v_alert_summary` AS
SELECT
  'pipeline_failure' AS alert_type,
  pipeline_run_id AS resource_id,
  business_date,
  warehouse_mode,
  status,
  error_summary,
  started_at,
  finished_at
FROM `data-aquarium.ashare_meta.pipeline_run`
WHERE status = 'failed'
  AND started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)

UNION ALL

SELECT
  'task_failure',
  CONCAT(pipeline_run_id, '/', task_id),
  business_date,
  warehouse_mode,
  status,
  error_summary,
  started_at,
  finished_at
FROM `data-aquarium.ashare_meta.pipeline_task_status`
WHERE status = 'failed'
  AND started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)

UNION ALL

SELECT
  'ingestion_failure',
  ingestion_run_id,
  partition_date,
  endpoint,
  status,
  error_summary,
  started_at,
  finished_at
FROM `data-aquarium.ashare_meta.ingestion_run`
WHERE status IN ('failed', 'empty_return')
  AND started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)

ORDER BY finished_at DESC;
