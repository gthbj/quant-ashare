# orchestration - OQ-005 GCP 调度流水线

> 文档维护：GPT-5（最近更新 2026-06-04）

本目录放置 GCP 生产流水线的部署和调度配置：

- `cloud_run_jobs/`：Tushare 或 Tushare 兼容 API 到 GCS Parquet 的 Cloud Run Jobs 镜像、部署脚本和作业模板。
- `composer/`：Cloud Composer DAG，用于串联每日采集、ODS 可读性检查、Dataform/BigQuery 转换和 QA。

采集 worker 代码仍位于 `scripts/ingestion/`，ODS 到 DIM/DWD/DWS/ADS 的 SQL/建模资产仍位于现有 `sql/`、`configs/`、`docs/` 目录。本目录只承载调度和部署入口，不保存 token、service account key 或任何凭据。

当前 Phase 1 已提供可部署 jobs、真实 worker 和 Composer DAG：

- Cloud Run Jobs 使用 `TUSHARE_TOKEN` Secret Manager 注入方式；每日生产入口使用 `ashare-ingest-current-scope` 单 execution 顺序执行当前 14 个 ODS endpoint；Jobs 通过 Direct VPC egress + Cloud NAT + 区域静态 IP 固定出口。
- Tushare 官方或兼容 API 地址通过 `TUSHARE_HTTP_URL` 环境变量注入。
- Jobs 模板默认追加 `--dry-run`，不会请求 API，也不会写 GCS；Composer 生产路径在 `ashare_pipeline_dry_run=false` 时显式传入 `--allow-gcs-write`。
- 本地可用 `--skip-gcs-write` 做只读 API smoke，验证 API、分页和 schema cast。
- worker 真实写入要求显式传 `--allow-gcs-write`，防止误写生产 GCS。
- 已用小范围 `index_daily_000852_SH / 20260603` 做 GCS 写入 smoke，并通过 ODS 外部表读取验证。
- Composer DAG 已接入生产每日采集和 `sql/qa/09_ods_daily_partition_readiness.sql` 每日 ODS readiness 检查，当前 Airflow 变量为 `ashare_pipeline_dry_run=false`、`ashare_enable_full_refresh=false`。
- 每日默认主链只读业务日分区或近期小窗口；2019+ 全历史 schema 检查、DIM/DWD/DWS/metadata/QA 全量刷新放在 `ashare_enable_full_refresh=true` 显式分支。
- `sql/qa/06_ods_parquet_schema_checks.sql` 和 `sql/qa/08_ods_external_readability_checks.sql` 是维护/全量刷新检查，不作为每日调度默认门禁。
