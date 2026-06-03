-- BigQuery Standard SQL · GCP Pipeline Phase 0
-- 创建 ashare_meta 下的采集与流水线运行记录表。

-- ── 采集运行记录 ──
CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_meta.ingestion_run` (
  ingestion_run_id    STRING      NOT NULL  COMMENT '采集运行唯一 ID（Cloud Run execution id 或自定义）',
  endpoint            STRING      NOT NULL  COMMENT 'ODS API endpoint',
  source_system       STRING      NOT NULL  COMMENT '数据源（tushare / tinyshare）',
  business_date_start STRING                COMMENT '业务日期起（inclusive）',
  business_date_end   STRING                COMMENT '业务日期止（inclusive）',
  partition_date      STRING                COMMENT '本次写入的 ODS 分区日期',
  request_params_hash STRING                COMMENT '请求参数 SHA256（去重用）',
  row_count           INT64                 COMMENT '写入 GCS 行数',
  schema_version      STRING                COMMENT 'Parquet schema contract 版本',
  gcs_uri             STRING                COMMENT '发布路径（gs://...）',
  status              STRING      NOT NULL  COMMENT 'success / failed / skipped / empty_return / pending',
  error_summary       STRING                COMMENT '脱敏错误摘要',
  started_at          TIMESTAMP   NOT NULL  COMMENT '开始时间',
  finished_at         TIMESTAMP             COMMENT '结束时间',
  created_at          TIMESTAMP   NOT NULL  COMMENT '记录创建时间'
)
OPTIONS(
  description = '采集运行记录：每次 Cloud Run Job 执行写入一行'
);

-- ── 分区采集状态 ──
CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_meta.ingestion_partition_status` (
  endpoint            STRING      NOT NULL  COMMENT 'ODS API endpoint',
  partition_date      STRING      NOT NULL  COMMENT 'ODS 分区日期',
  status              STRING      NOT NULL  COMMENT 'success / failed / empty_return / pending',
  row_count           INT64                 COMMENT '该分区最新行数',
  ingestion_run_id    STRING                COMMENT '最近一次写入的 run id',
  gcs_uri             STRING                COMMENT '发布路径',
  schema_version      STRING                COMMENT 'Parquet schema contract 版本',
  updated_at          TIMESTAMP   NOT NULL  COMMENT '最近更新时间'
)
OPTIONS(
  description = '分区采集状态：每个 endpoint + partition_date 一行，记录最新采集状态'
);

-- ── 流水线运行记录 ──
CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_meta.pipeline_run` (
  pipeline_run_id     STRING      NOT NULL  COMMENT 'Composer DAG run id',
  dag_id              STRING      NOT NULL  COMMENT 'DAG 名称',
  business_date       STRING                COMMENT '业务日期',
  status              STRING      NOT NULL  COMMENT 'running / success / failed / partial',
  started_at          TIMESTAMP   NOT NULL  COMMENT '开始时间',
  finished_at         TIMESTAMP             COMMENT '结束时间',
  error_summary       STRING                COMMENT '脱敏错误摘要',
  created_at          TIMESTAMP   NOT NULL  COMMENT '记录创建时间'
)
OPTIONS(
  description = '流水线运行记录：每次 Composer DAG 执行写入一行'
);

-- ── 流水线任务状态 ──
CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_meta.pipeline_task_status` (
  pipeline_run_id     STRING      NOT NULL  COMMENT 'Composer DAG run id',
  task_id             STRING      NOT NULL  COMMENT 'Airflow task id',
  task_type           STRING                COMMENT 'ingestion / dataform / qa / runner / report',
  endpoint            STRING                COMMENT '采集 endpoint（采集任务时）',
  bigquery_job_id     STRING                COMMENT 'BigQuery job id',
  dataform_invocation_id STRING             COMMENT 'Dataform workflow invocation id',
  cloud_run_execution_id STRING              COMMENT 'Cloud Run execution id',
  status              STRING      NOT NULL  COMMENT 'success / failed / skipped / running',
  row_count           INT64                 COMMENT '影响行数',
  error_summary       STRING                COMMENT '脱敏错误摘要',
  started_at          TIMESTAMP             COMMENT '开始时间',
  finished_at         TIMESTAMP             COMMENT '结束时间',
  created_at          TIMESTAMP   NOT NULL  COMMENT '记录创建时间'
)
OPTIONS(
  description = '流水线任务状态：每个 Composer task 写入一行'
);
