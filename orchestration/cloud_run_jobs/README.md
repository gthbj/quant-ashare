# Cloud Run Jobs - ODS 采集

> 文档维护：GPT-5（2026-06-04）；Claude Fable 5（最近更新 2026-06-12）

本目录定义每日 ODS 采集的 Cloud Run Jobs 部署入口。当前只覆盖现有 SQL 消费的 14 个 ODS endpoint。生产 DAG 使用单个 `ashare-ingest-current-scope` execution 顺序执行 4 个作业组，避免同一 Tushare token 在短时间内从多个 Cloud Run 出口 IP 请求 Tushare 兼容 API。分组 Job 保留为诊断和单组补救入口：

- `ashare-ingest-current-scope`：顺序执行以下 4 个作业组
- `ashare-ingest-market-eod`：`daily`、`adj_factor`、`stk_limit`、`suspend_d`、`daily_basic`
- `ashare-ingest-index-eod`：`index_daily`、`index_dailybasic`
- `ashare-ingest-dim-snapshot`：`stock_basic`、`trade_cal`、`namechange`
- `ashare-ingest-finance-recent`：`fina_indicator`、`income`、`balancesheet`、`cashflow`

## Secret Manager

Tushare token 只允许通过 Secret Manager 或运行时环境变量注入，不写入代码、配置、日志或文档。

```bash
printf '%s' "$TUSHARE_TOKEN" | gcloud secrets create tushare-token \
  --project=data-aquarium \
  --data-file=- \
  --replication-policy=automatic
```

已有 secret 时新增版本：

```bash
printf '%s' "$TUSHARE_TOKEN" | gcloud secrets versions add tushare-token \
  --project=data-aquarium \
  --data-file=-
```

Tushare 官方或兼容代理地址通过 `TUSHARE_HTTP_URL` 环境变量配置。

## 构建镜像

```bash
gcloud builds submit . \
  --project=data-aquarium \
  --config=orchestration/cloud_run_jobs/cloudbuild.ingestion.yaml \
  --substitutions=_IMAGE_URI=asia-east2-docker.pkg.dev/data-aquarium/ashare/ingestion:latest
```

## 部署 Jobs

部署脚本默认带 `--dry-run`，不会请求 API，也不会写 GCS。Tushare 官方或兼容代理地址从 `TUSHARE_HTTP_URL` 环境变量注入。

```bash
TUSHARE_HTTP_URL="$TUSHARE_HTTP_URL" \
  bash orchestration/cloud_run_jobs/deploy_ingestion_jobs.sh
```

执行 dry-run：

```bash
gcloud run jobs execute ashare-ingest-market-eod \
  --project=data-aquarium \
  --region=asia-east2 \
  --wait
```

## 真实写入安全门禁

worker 在非 dry-run 且非 `--skip-gcs-write` 模式下，必须显式传入 `--allow-gcs-write` 才会发布 Parquet 到 GCS。Cloud Run Job 默认模板仍保留 `--dry-run`；Composer DAG 只有在 `ashare_pipeline_dry_run=false` 时才会追加 `--allow-gcs-write`。

Cloud Run Job 模板默认 `--max-retries=0`。接口错误、schema cast 错误或写入错误由外层调度器记录并人工/显式 resume，避免 Cloud Run task 自动重试在短时间内重复请求 Tushare 兼容 API 并触发 token/IP 限制。

live GCS 写入会持久化运行审计：

- `ashare_meta.ingestion_run`：每个 endpoint/partition 结果一行，记录 run id、行数、状态、GCS URI、schema version 和脱敏错误摘要。
- `ashare_meta.ingestion_partition_status`：每个 `partition_endpoint + partition_date` 一行，记录最新采集状态。这里的 `endpoint` 字段存 ODS partition endpoint，而不是仅存 Tushare API 名，避免指数 variant 等同一 API + 同一日期互相覆盖。

dry-run 和 `--skip-gcs-write` 只读 API smoke 不写生产 meta 表。

## GCS Hive 路径口径

raw Parquet canonical 路径固定为：

```text
gs://data-aquarium/a-share/tushare/raw_data/api=<api>/endpoint=<partition_endpoint>/partition_date=<YYYYMMDD>/data.parquet
```

- `api=` 使用实际 Tushare API 名；财务三表和财务指标使用 `income_vip` / `balancesheet_vip` / `cashflow_vip` / `fina_indicator_vip`。
- `endpoint=` 使用 ODS 外部表读取的 partition endpoint / variant，例如 `index_daily_000852_SH`、`stock_basic_listed`。
- 不使用 `api=tushare`。
- 2026-06-04 已用 BigQuery `ashare_ods.INFORMATION_SCHEMA.TABLE_OPTIONS` 复核当前 14 张 ODS 与 10 张 schema repair 表的 external `source_uris`，均为 `api=<api>/endpoint=<partition_endpoint>/partition_date=*/data.parquet` 口径。

publish 流程会先写 staging object、读回校验 schema，再覆盖正式 `data.parquet`。采集重跑以 API 当前返回为准，正式 object 覆盖不做 write-once backup；如历史回填需要可回滚，应另加 backup 开关或单独回填流程。

## 固定出口 IP

Cloud Run Jobs 使用 Direct VPC egress 走 Cloud NAT 固定出口：

```text
network=default
subnet=default
vpc_egress=all-traffic
cloud_nat=ashare-cloudrun-nat-asia-east2
static_ip=ashare-cloudrun-nat-ip-asia-east2
```

该配置用于保证 Tushare 兼容 API 请求从同一个区域静态 IP 出口发起，避免同一 token 在短时间内被识别为多 IP 使用。部署脚本默认写入 `--network=default --subnet=default --vpc-egress=all-traffic`。

## 启用真实采集前置条件

- endpoint worker 已实现真实 API 拉取、limit/offset 分页、schema cast、GCS staging/publish。
- API 分页必须收敛；若接口忽略 offset 或达到最大分页数，必须失败，不能发布截断数据。
- 空返回只记录口径，不写伪空 Parquet。
- Parquet schema 必须按 `configs/ingestion/schema_contracts/` 显式 cast。
- ODS 外部表重建时必须保留表说明、字段说明和 external source URI 口径。
- Cloud Run Job 移除 `--dry-run` 后必须先在非生产日期或小范围 endpoint 上 smoke。

## 当前部署状态

2026-06-04 已部署 Cloud Run Jobs（模板默认保留 `--dry-run`）：

- `ashare-ingest-current-scope`
- `ashare-ingest-market-eod`
- `ashare-ingest-index-eod`
- `ashare-ingest-dim-snapshot`
- `ashare-ingest-finance-recent`

镜像：`asia-east2-docker.pkg.dev/data-aquarium/ashare/ingestion@sha256:5c78e8624584e9ee47471be087ba7e4090d00477a37ec276920f8696810c3f3b`（2026-06-12 重建，含 `60fb242` status_writer 接线与 `2e4d29b` 000001.SH variant）

⚠️ 镜像重建纪律：本镜像把 `scripts/ingestion/**` 与 `configs/ingestion/**`（含采集 manifest）打包进镜像，job 引用 `:latest` 并在 execution 创建时解析 digest。任何改动这两个路径的 PR 合并后**必须重建并推送本镜像**，否则生产采集继续运行旧代码/旧 manifest 且无显式报错（2026-06-12 事故：2026-06-04 旧镜像导致 `ashare_meta.ingestion_run` 8 天 0 行、000001.SH 自 06-10 停更）。

已完成 4 个分组 Cloud Run Job dry-run execution 验证；本地已用 Secret Manager token + `--skip-gcs-write` 对 4 个 endpoint group 做 API 只读 smoke。已完成小范围 GCS 写入 smoke：`index_daily_000852_SH / partition_date=20260603` 写入 1 行，并通过 `ashare_ods.ods_tushare_index_daily` 按 `_run_id` 读取验证。2026-06-04 生产写入 smoke 发现分组 Job 连续执行可能触发同一 Tushare token 多 IP 限制，因此新增 `ashare-ingest-current-scope` 并将 Composer DAG 默认采集任务收敛为单 execution。Direct VPC egress + Cloud NAT 固定出口已部署；`2026-05-20` 至 `2026-06-03` 的 SSE 开市日生产 GCS 回填均成功并通过 `sql/qa/09_ods_daily_partition_readiness.sql`，`manual_pipeline_daily_prod_20260604_01` 已通过 Composer 生产路径写入 `2026-06-04` 并成功完成 readiness。
