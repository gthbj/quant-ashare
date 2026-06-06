-- BigQuery Standard SQL · GCP pipeline meta tables
-- 创建 ashare_meta 下的采集与流水线运行记录表。

-- ── 采集运行记录 ──
CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_meta.ingestion_run` (
  ingestion_run_id    STRING      NOT NULL,
  endpoint            STRING      NOT NULL,
  source_system       STRING      NOT NULL,
  business_date_start STRING,
  business_date_end   STRING,
  partition_date      STRING,
  request_params_hash STRING,
  row_count           INT64,
  schema_version      STRING,
  gcs_uri             STRING,
  status              STRING      NOT NULL,
  error_summary       STRING,
  started_at          TIMESTAMP   NOT NULL,
  finished_at         TIMESTAMP,
  created_at          TIMESTAMP   NOT NULL
)
OPTIONS(
  description = '采集运行记录：每次 Cloud Run Job 执行写入一行'
);

ALTER TABLE `data-aquarium.ashare_meta.ingestion_run`
ALTER COLUMN ingestion_run_id SET OPTIONS (description='采集运行唯一 ID（Cloud Run execution id 或自定义）'),
ALTER COLUMN endpoint SET OPTIONS (description='ODS API endpoint'),
ALTER COLUMN source_system SET OPTIONS (description='数据源（tushare / tinyshare）'),
ALTER COLUMN business_date_start SET OPTIONS (description='业务日期起（inclusive）'),
ALTER COLUMN business_date_end SET OPTIONS (description='业务日期止（inclusive）'),
ALTER COLUMN partition_date SET OPTIONS (description='本次写入的 ODS 分区日期'),
ALTER COLUMN request_params_hash SET OPTIONS (description='请求参数 SHA256（去重用）'),
ALTER COLUMN row_count SET OPTIONS (description='写入 GCS 行数'),
ALTER COLUMN schema_version SET OPTIONS (description='Parquet schema contract 版本'),
ALTER COLUMN gcs_uri SET OPTIONS (description='发布路径（gs://...）'),
ALTER COLUMN status SET OPTIONS (description='success / failed / skipped / empty_return / pending'),
ALTER COLUMN error_summary SET OPTIONS (description='脱敏错误摘要'),
ALTER COLUMN started_at SET OPTIONS (description='开始时间'),
ALTER COLUMN finished_at SET OPTIONS (description='结束时间'),
ALTER COLUMN created_at SET OPTIONS (description='记录创建时间');

-- ── 分区采集状态 ──
CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_meta.ingestion_partition_status` (
  endpoint            STRING      NOT NULL,
  partition_date      STRING      NOT NULL,
  status              STRING      NOT NULL,
  row_count           INT64,
  ingestion_run_id    STRING,
  gcs_uri             STRING,
  schema_version      STRING,
  updated_at          TIMESTAMP   NOT NULL
)
OPTIONS(
  description = '分区采集状态：每个 endpoint + partition_date 一行，记录最新采集状态'
);

ALTER TABLE `data-aquarium.ashare_meta.ingestion_partition_status`
ALTER COLUMN endpoint SET OPTIONS (description='ODS API endpoint'),
ALTER COLUMN partition_date SET OPTIONS (description='ODS 分区日期'),
ALTER COLUMN status SET OPTIONS (description='success / failed / empty_return / pending'),
ALTER COLUMN row_count SET OPTIONS (description='该分区最新行数'),
ALTER COLUMN ingestion_run_id SET OPTIONS (description='最近一次写入的 run id'),
ALTER COLUMN gcs_uri SET OPTIONS (description='发布路径'),
ALTER COLUMN schema_version SET OPTIONS (description='Parquet schema contract 版本'),
ALTER COLUMN updated_at SET OPTIONS (description='最近更新时间');

-- ── 流水线运行记录 ──
CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_meta.pipeline_run` (
  pipeline_run_id     STRING      NOT NULL,
  dag_id              STRING      NOT NULL,
  business_date       STRING,
  date_from           STRING,
  date_to             STRING,
  run_label           STRING,
  warehouse_mode      STRING,
  transform_backend   STRING,
  upstream_pipeline_run_id STRING,
  triggered_by_dag_id STRING,
  status              STRING      NOT NULL,
  started_at          TIMESTAMP   NOT NULL,
  finished_at         TIMESTAMP,
  error_summary       STRING,
  created_at          TIMESTAMP   NOT NULL,
  updated_at          TIMESTAMP
)
OPTIONS(
  description = '流水线运行记录：每次 Composer DAG 执行写入一行'
);

ALTER TABLE `data-aquarium.ashare_meta.pipeline_run`
ADD COLUMN IF NOT EXISTS date_from STRING,
ADD COLUMN IF NOT EXISTS date_to STRING,
ADD COLUMN IF NOT EXISTS run_label STRING,
ADD COLUMN IF NOT EXISTS warehouse_mode STRING,
ADD COLUMN IF NOT EXISTS transform_backend STRING,
ADD COLUMN IF NOT EXISTS upstream_pipeline_run_id STRING,
ADD COLUMN IF NOT EXISTS triggered_by_dag_id STRING,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;

ALTER TABLE `data-aquarium.ashare_meta.pipeline_run`
ALTER COLUMN pipeline_run_id SET OPTIONS (description='Composer DAG run id'),
ALTER COLUMN dag_id SET OPTIONS (description='DAG 名称'),
ALTER COLUMN business_date SET OPTIONS (description='业务日期'),
ALTER COLUMN date_from SET OPTIONS (description='区间补跑开始日期（YYYY-MM-DD，可空）'),
ALTER COLUMN date_to SET OPTIONS (description='区间补跑结束日期（YYYY-MM-DD，可空）'),
ALTER COLUMN run_label SET OPTIONS (description='production_daily / manual_smoke / backfill / maintenance 等运行标签'),
ALTER COLUMN warehouse_mode SET OPTIONS (description='daily_current / full_rebuild / full_rebuild_compat / backfill / qa_only'),
ALTER COLUMN transform_backend SET OPTIONS (description='bq_sql / dataform'),
ALTER COLUMN upstream_pipeline_run_id SET OPTIONS (description='触发本 DAG run 的上游 pipeline_run_id；如 ODS ingestion run 触发 warehouse refresh'),
ALTER COLUMN triggered_by_dag_id SET OPTIONS (description='触发本 DAG run 的上游 DAG 名称；手工触发可空'),
ALTER COLUMN status SET OPTIONS (description='running / success / failed / partial'),
ALTER COLUMN started_at SET OPTIONS (description='开始时间'),
ALTER COLUMN finished_at SET OPTIONS (description='结束时间'),
ALTER COLUMN error_summary SET OPTIONS (description='脱敏错误摘要'),
ALTER COLUMN created_at SET OPTIONS (description='记录创建时间'),
ALTER COLUMN updated_at SET OPTIONS (description='记录更新时间');

-- ── 流水线任务状态 ──
CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_meta.pipeline_task_status` (
  pipeline_run_id     STRING      NOT NULL,
  task_id             STRING      NOT NULL,
  task_type           STRING,
  business_date       STRING,
  date_from           STRING,
  date_to             STRING,
  run_label           STRING,
  warehouse_mode      STRING,
  transform_backend   STRING,
  endpoint            STRING,
  bigquery_job_id     STRING,
  dataform_invocation_id STRING,
  cloud_run_execution_id STRING,
  airflow_log_url     STRING,
  bigquery_job_url    STRING,
  cloud_run_execution_url STRING,
  status              STRING      NOT NULL,
  row_count           INT64,
  error_summary       STRING,
  started_at          TIMESTAMP,
  finished_at         TIMESTAMP,
  created_at          TIMESTAMP   NOT NULL,
  updated_at          TIMESTAMP
)
OPTIONS(
  description = '流水线任务状态：每个 Composer task 写入一行'
);

ALTER TABLE `data-aquarium.ashare_meta.pipeline_task_status`
ADD COLUMN IF NOT EXISTS business_date STRING,
ADD COLUMN IF NOT EXISTS date_from STRING,
ADD COLUMN IF NOT EXISTS date_to STRING,
ADD COLUMN IF NOT EXISTS run_label STRING,
ADD COLUMN IF NOT EXISTS warehouse_mode STRING,
ADD COLUMN IF NOT EXISTS transform_backend STRING,
ADD COLUMN IF NOT EXISTS airflow_log_url STRING,
ADD COLUMN IF NOT EXISTS bigquery_job_url STRING,
ADD COLUMN IF NOT EXISTS cloud_run_execution_url STRING,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;

ALTER TABLE `data-aquarium.ashare_meta.pipeline_task_status`
ALTER COLUMN pipeline_run_id SET OPTIONS (description='Composer DAG run id'),
ALTER COLUMN task_id SET OPTIONS (description='Airflow task id'),
ALTER COLUMN task_type SET OPTIONS (description='ingestion / dataform / qa / runner / report'),
ALTER COLUMN business_date SET OPTIONS (description='业务日期'),
ALTER COLUMN date_from SET OPTIONS (description='区间补跑开始日期（YYYY-MM-DD，可空）'),
ALTER COLUMN date_to SET OPTIONS (description='区间补跑结束日期（YYYY-MM-DD，可空）'),
ALTER COLUMN run_label SET OPTIONS (description='production_daily / manual_smoke / backfill / maintenance 等运行标签'),
ALTER COLUMN warehouse_mode SET OPTIONS (description='daily_current / full_rebuild / full_rebuild_compat / backfill / qa_only'),
ALTER COLUMN transform_backend SET OPTIONS (description='bq_sql / dataform'),
ALTER COLUMN endpoint SET OPTIONS (description='采集 endpoint（采集任务时）'),
ALTER COLUMN bigquery_job_id SET OPTIONS (description='BigQuery job id'),
ALTER COLUMN dataform_invocation_id SET OPTIONS (description='Dataform workflow invocation id'),
ALTER COLUMN cloud_run_execution_id SET OPTIONS (description='Cloud Run execution id'),
ALTER COLUMN airflow_log_url SET OPTIONS (description='Airflow task log URL'),
ALTER COLUMN bigquery_job_url SET OPTIONS (description='BigQuery job console URL'),
ALTER COLUMN cloud_run_execution_url SET OPTIONS (description='Cloud Run execution console URL'),
ALTER COLUMN status SET OPTIONS (description='success / failed / skipped / running / warning'),
ALTER COLUMN row_count SET OPTIONS (description='影响行数'),
ALTER COLUMN error_summary SET OPTIONS (description='脱敏错误摘要'),
ALTER COLUMN started_at SET OPTIONS (description='开始时间'),
ALTER COLUMN finished_at SET OPTIONS (description='结束时间'),
ALTER COLUMN created_at SET OPTIONS (description='记录创建时间'),
ALTER COLUMN updated_at SET OPTIONS (description='记录更新时间');
