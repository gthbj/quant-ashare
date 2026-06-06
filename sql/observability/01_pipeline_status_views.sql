-- BigQuery Standard SQL · Ashare Pipeline Status Observability
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
  transform_backend,
  upstream_pipeline_run_id,
  triggered_by_dag_id,
  status,
  started_at,
  finished_at,
  TIMESTAMP_DIFF(COALESCE(finished_at, CURRENT_TIMESTAMP()), started_at, SECOND) AS duration_seconds,
  error_summary,
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
-- 4. Cloud Run ingestion 失败明细（只含 failed，不含 empty_return）
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
WHERE status = 'failed'
ORDER BY started_at DESC
LIMIT 100;

-- ────────────────────────────────────────────────────────────────────────────
-- 4b. Cloud Run ingestion empty_return 明细（需按 endpoint/date 判断是否正常）
-- ────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW `data-aquarium.ashare_meta.v_ingestion_empty_returns` AS
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
  finished_at
FROM `data-aquarium.ashare_meta.ingestion_run`
WHERE status = 'empty_return'
ORDER BY started_at DESC
LIMIT 100;

-- ────────────────────────────────────────────────────────────────────────────
-- 5. 每日 pipeline 健康仪表盘（用 pipeline_run_id join 避免串 run）
-- ────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW `data-aquarium.ashare_meta.v_pipeline_daily_health` AS
WITH latest_runs AS (
  SELECT
    pipeline_run_id,
    dag_id,
    business_date,
    warehouse_mode,
    status,
    started_at,
    finished_at,
    ROW_NUMBER() OVER (PARTITION BY business_date, dag_id, warehouse_mode ORDER BY started_at DESC) AS rn
  FROM `data-aquarium.ashare_meta.pipeline_run`
  WHERE started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
),
task_summary AS (
  SELECT
    t.pipeline_run_id,
    COUNTIF(t.status = 'success') AS tasks_success,
    COUNTIF(t.status = 'failed') AS tasks_failed,
    COUNTIF(t.status = 'skipped') AS tasks_skipped,
    COUNTIF(t.status = 'running') AS tasks_running,
    COUNT(*) AS tasks_total
  FROM `data-aquarium.ashare_meta.pipeline_task_status` t
  WHERE t.started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  GROUP BY t.pipeline_run_id
)
SELECT
  lr.business_date,
  lr.dag_id,
  lr.warehouse_mode,
  lr.status AS run_status,
  ts.tasks_success,
  ts.tasks_failed,
  ts.tasks_skipped,
  ts.tasks_running,
  ts.tasks_total,
  lr.started_at,
  lr.finished_at,
  TIMESTAMP_DIFF(COALESCE(lr.finished_at, CURRENT_TIMESTAMP()), lr.started_at, SECOND) AS duration_seconds,
  lr.pipeline_run_id
FROM latest_runs lr
LEFT JOIN task_summary ts
  ON lr.pipeline_run_id = ts.pipeline_run_id
WHERE lr.rn = 1
ORDER BY lr.business_date DESC, lr.warehouse_mode;

-- ────────────────────────────────────────────────────────────────────────────
-- 6. 最近 24 小时异常摘要（供告警查询）
--    - pipeline_failure: DAG run 失败
--    - task_failure: task 失败（含 QA、readiness、窗口刷新等）
--    - ingestion_failed: 采集执行失败（不含 empty_return）
--    - warehouse_refresh_missing: ingestion 成功后 60 分钟内没有 linked 下游窗口刷新 run
-- ────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW `data-aquarium.ashare_meta.v_pipeline_refresh_missing` AS
WITH ingestion_success AS (
  SELECT
    pipeline_run_id,
    dag_id,
    business_date,
    run_label,
    status,
    started_at,
    finished_at
  FROM `data-aquarium.ashare_meta.pipeline_run`
  WHERE dag_id = 'ashare_ods_ingestion_daily'
    AND status = 'success'
    AND finished_at IS NOT NULL
    AND started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
),
warehouse_refresh AS (
  SELECT
    upstream_pipeline_run_id,
    COUNT(*) AS linked_run_count,
    ARRAY_AGG(
      STRUCT(pipeline_run_id, status, started_at, finished_at)
      ORDER BY started_at DESC
      LIMIT 1
    )[SAFE_OFFSET(0)] AS latest_refresh
  FROM `data-aquarium.ashare_meta.pipeline_run`
  WHERE dag_id = 'ashare_warehouse_window_refresh'
    AND upstream_pipeline_run_id IS NOT NULL
    AND started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
  GROUP BY upstream_pipeline_run_id
)
SELECT
  i.pipeline_run_id AS ingestion_pipeline_run_id,
  i.business_date,
  'daily_current' AS warehouse_mode,
  'missing_downstream_refresh' AS status,
  CONCAT(
    'ODS ingestion run succeeded but no linked ashare_warehouse_window_refresh run was observed within 60 minutes. upstream_pipeline_run_id=',
    i.pipeline_run_id
  ) AS error_summary,
  i.started_at,
  CURRENT_TIMESTAMP() AS detected_at,
  w.latest_refresh.pipeline_run_id AS latest_refresh_pipeline_run_id,
  w.latest_refresh.status AS latest_refresh_status,
  w.latest_refresh.started_at AS latest_refresh_started_at,
  w.latest_refresh.finished_at AS latest_refresh_finished_at
FROM ingestion_success i
LEFT JOIN warehouse_refresh w
  ON w.upstream_pipeline_run_id = i.pipeline_run_id
WHERE TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), i.finished_at, MINUTE) >= 60
  AND COALESCE(w.linked_run_count, 0) = 0;

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
  'warehouse_refresh_missing',
  ingestion_pipeline_run_id,
  business_date,
  warehouse_mode,
  status,
  error_summary,
  started_at,
  detected_at
FROM `data-aquarium.ashare_meta.v_pipeline_refresh_missing`

UNION ALL

SELECT
  'ingestion_failed',
  ingestion_run_id,
  partition_date,
  endpoint,
  status,
  error_summary,
  started_at,
  finished_at
FROM `data-aquarium.ashare_meta.ingestion_run`
WHERE status = 'failed'
  AND started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)

ORDER BY finished_at DESC;

-- ────────────────────────────────────────────────────────────────────────────
-- 7. 告警探针（手工健康检查）
--    返回 v_alert_summary 固定 24 小时窗口内的异常数量。
--    定时告警请调用 check_alerts.py，并由 --lookback-minutes 控制检查窗口。
-- ────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW `data-aquarium.ashare_meta.v_alert_probe` AS
SELECT
  COUNT(*) AS alert_count,
  MIN(finished_at) AS earliest_alert,
  MAX(finished_at) AS latest_alert
FROM `data-aquarium.ashare_meta.v_alert_summary`;
