-- BigQuery Standard SQL
-- Strategy 1 Cloud Run runner status extensions.
-- 文档维护：GPT-5（最近更新 2026-06-04）

ALTER TABLE `data-aquarium.ashare_meta.strategy1_experiment_run_status`
ADD COLUMN IF NOT EXISTS cloud_run_job_name STRING
OPTIONS(description = 'Cloud Run Job 名称，如 strategy1-train-predict-job');

ALTER TABLE `data-aquarium.ashare_meta.strategy1_experiment_run_status`
ADD COLUMN IF NOT EXISTS cloud_run_execution_id STRING
OPTIONS(description = 'Cloud Run execution id，用于追踪单次执行');

ALTER TABLE `data-aquarium.ashare_meta.strategy1_experiment_run_status`
ADD COLUMN IF NOT EXISTS cloud_run_task_index INT64
OPTIONS(description = 'Cloud Run task index，多 task job 时用于定位任务');

ALTER TABLE `data-aquarium.ashare_meta.strategy1_experiment_run_status`
ADD COLUMN IF NOT EXISTS container_image STRING
OPTIONS(description = 'Cloud Run 容器镜像 tag 或 digest');

ALTER TABLE `data-aquarium.ashare_meta.strategy1_experiment_run_status`
ADD COLUMN IF NOT EXISTS execution_backend STRING
OPTIONS(description = '执行后端，如 cloud_run_sklearn_ledger_v1');

ALTER TABLE `data-aquarium.ashare_meta.strategy1_experiment_run_status`
ADD COLUMN IF NOT EXISTS model_artifact_uri STRING
OPTIONS(description = 'sklearn 模型 artifact GCS URI');

ALTER TABLE `data-aquarium.ashare_meta.strategy1_experiment_run_status`
ADD COLUMN IF NOT EXISTS preprocess_artifact_uri STRING
OPTIONS(description = '预处理 artifact GCS URI');

ALTER TABLE `data-aquarium.ashare_meta.strategy1_experiment_run_status`
ADD COLUMN IF NOT EXISTS feature_snapshot_uri STRING
OPTIONS(description = '训练或预测数据快照 GCS URI');

ALTER TABLE `data-aquarium.ashare_meta.strategy1_experiment_run_status`
ADD COLUMN IF NOT EXISTS max_parallel_experiments INT64
OPTIONS(description = '本次 owner 设置或 resolved 后的实验并发数');
