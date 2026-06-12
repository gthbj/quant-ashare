# Ashare Pipeline 补跑与故障恢复 Runbook

> 文档维护：GPT-5.5（最近更新 2026-06-13）
>
> 当前生产路径：Cloud Scheduler + Cloud Workflows

本 runbook 覆盖 Ashare pipeline 当前生产调度链路的常见故障与恢复步骤。Cloud Composer 环境 `ashare-composer` 已于 2026-06-08 删除；本文不再包含 Composer / Airflow 操作命令。

## 0. 当前入口速查

| 入口 | 类型 | 调度 / 用途 |
|---|---|---|
| `ashare-ods-ingestion-daily` | Cloud Scheduler job | 每天 `20:00 Asia/Shanghai` 触发 ODS daily workflow |
| `ashare-pipeline-alert-checker` | Cloud Scheduler job | 每小时触发 alert-check workflow |
| `ashare_ods_ingestion_daily` | Workflow | ODS 采集、非交易日 gate、ODS readiness，成功后同步触发 warehouse child workflow |
| `ashare_warehouse_window_refresh` | Workflow | `daily_current` / `backfill` / `qa_only` 的窗口刷新与 QA |
| `ashare_warehouse_full_rebuild` | Workflow | 手工全量维护重建，必须显式确认 |
| `ashare_pipeline_alert_checker` | Workflow | 调用 `ashare-pipeline-control /v1/tasks/alert-check` 写 heartbeat / alert log |

固定参数：

| 参数 | 说明 |
|---|---|
| `business_date` | 业务日期，格式 `YYYY-MM-DD` |
| `date_from` / `date_to` | backfill 或 full rebuild 窗口 |
| `pipeline_dry_run` | `true` 时只做低风险路径 |
| `warehouse_mode` | `daily_current` / `backfill` / `qa_only` / `full_rebuild` |
| `run_label` | 手工恢复标签，建议包含日期和原因 |
| `force_non_trading_day_gate` | 手工 smoke 非交易日 skip 时使用 |
| `confirm_full_rebuild` | full rebuild 写路径必须显式传 `true` |

## 1. 基础查询

最近 workflow executions：

```bash
gcloud workflows executions list ashare_ods_ingestion_daily \
  --project=data-aquarium \
  --location=asia-east2 \
  --limit=10

gcloud workflows executions list ashare_warehouse_window_refresh \
  --project=data-aquarium \
  --location=asia-east2 \
  --limit=10
```

查看单个 execution：

```bash
gcloud workflows executions describe EXECUTION_ID \
  --workflow=ashare_ods_ingestion_daily \
  --project=data-aquarium \
  --location=asia-east2
```

查看 scheduler 状态：

```bash
gcloud scheduler jobs describe ashare-ods-ingestion-daily \
  --project=data-aquarium \
  --location=asia-east2

gcloud scheduler jobs describe ashare-pipeline-alert-checker \
  --project=data-aquarium \
  --location=asia-east2
```

查看 pipeline 状态表：

```sql
SELECT
  pipeline_run_id,
  pipeline_name,
  business_date,
  warehouse_mode,
  status,
  started_at,
  finished_at,
  error_summary
FROM `data-aquarium.ashare_meta.pipeline_run`
WHERE started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
ORDER BY started_at DESC;
```

查看失败 task：

```sql
SELECT
  pipeline_run_id,
  task_id,
  task_type,
  status,
  bigquery_job_id,
  bigquery_job_url,
  cloud_run_execution_url,
  error_summary,
  updated_at
FROM `data-aquarium.ashare_meta.pipeline_task_status`
WHERE updated_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
  AND status = 'failed'
ORDER BY updated_at DESC;
```

## 2. ODS 某天没采集

症状：ODS readiness 失败，或 `QA-ODS-DAILY-*` 报缺分区 / 零行。

先确认缺失分区：

```sql
SELECT endpoint, partition_date, status, row_count, error_summary
FROM `data-aquarium.ashare_meta.ingestion_partition_status`
WHERE partition_date = FORMAT_DATE('%Y%m%d', DATE '2026-06-05')
ORDER BY endpoint;
```

如果需要补采，先手工执行 Cloud Run ingestion job：

```bash
gcloud run jobs execute ashare-ingest-current-scope \
  --project=data-aquarium \
  --region=asia-east2 \
  --args="--endpoint-group,current_scope,--business-date,2026-06-05,--allow-gcs-write"
```

补采完成后，触发 warehouse daily window refresh：

```bash
gcloud workflows execute ashare_warehouse_window_refresh \
  --project=data-aquarium \
  --location=asia-east2 \
  --data='{
    "business_date": "2026-06-05",
    "warehouse_mode": "daily_current",
    "pipeline_dry_run": false,
    "run_label": "manual_recovery_daily_current_20260605"
  }'
```

## 3. 某 endpoint 采集失败

查看失败详情：

```sql
SELECT
  ingestion_run_id,
  endpoint,
  partition_date,
  status,
  row_count,
  error_summary,
  started_at,
  finished_at
FROM `data-aquarium.ashare_meta.ingestion_run`
WHERE status = 'failed'
  AND started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
ORDER BY started_at DESC;
```

单 endpoint 补跑示例：

```bash
gcloud run jobs execute ashare-ingest-current-scope \
  --project=data-aquarium \
  --region=asia-east2 \
  --args="--endpoint-group,current_scope,--endpoint,daily,--business-date,2026-06-05,--allow-gcs-write"
```

同一天多个 endpoint 可以重复传 `--endpoint`：

```bash
gcloud run jobs execute ashare-ingest-current-scope \
  --project=data-aquarium \
  --region=asia-east2 \
  --args="--endpoint-group,current_scope,--endpoint,daily,--endpoint,daily_basic,--business-date,2026-06-05,--allow-gcs-write"
```

补跑后用 `ingestion_partition_status` 确认分区成功，再触发 `ashare_warehouse_window_refresh`。

## 4. 窗口刷新或 QA 失败

先取失败 task 的 BigQuery job 和错误摘要：

```sql
SELECT
  task_id,
  status,
  bigquery_job_id,
  bigquery_job_url,
  error_summary
FROM `data-aquarium.ashare_meta.pipeline_task_status`
WHERE pipeline_run_id = 'PIPELINE_RUN_ID'
ORDER BY updated_at;
```

常见处理：

| 类型 | 处理 |
|---|---|
| BigQuery SQL error | 打开 `bigquery_job_url` 看具体 SQL 错误，修复后重跑同一窗口 |
| ODS readiness failed | 先按第 2 / 3 节补采或确认源端当天确实无数据 |
| `QA-WIN-*` failed | 看 `error_summary`，确认是源数据缺口、窗口 MERGE 问题还是下游 DWS 约束 |
| 权限错误 | 复核 `ashare-workflows-runtime` 对 BigQuery、Cloud Run Job、control service 和 lock bucket 的权限 |
| 锁冲突 | 确认没有另一个 warehouse workflow execution 正在写同一窗口 |

修复后重跑窗口：

```bash
gcloud workflows execute ashare_warehouse_window_refresh \
  --project=data-aquarium \
  --location=asia-east2 \
  --data='{
    "business_date": "2026-06-05",
    "date_from": "2026-06-05",
    "date_to": "2026-06-05",
    "warehouse_mode": "daily_current",
    "pipeline_dry_run": false,
    "run_label": "manual_recovery_window_20260605"
  }'
```

只跑 QA：

```bash
gcloud workflows execute ashare_warehouse_window_refresh \
  --project=data-aquarium \
  --location=asia-east2 \
  --data='{
    "business_date": "2026-06-05",
    "warehouse_mode": "qa_only",
    "pipeline_dry_run": false,
    "run_label": "manual_qa_only_20260605"
  }'
```

### 分红事件链路 / CA staleness

`daily_current` 会在价格/市场窗口刷新链尾以 weak 方式自动重建
`dwd_stock_dividend_event` 和 `qa/14`。这两步失败时，pipeline run 仍会
finalize success，但 `pipeline_task_status` 会保留 failed task 并触发
`task_failure` 告警。

先查事件链 task：

```sql
SELECT
  pipeline_run_id,
  task_id,
  status,
  error_summary,
  bigquery_job_url,
  updated_at
FROM `data-aquarium.ashare_meta.pipeline_task_status`
WHERE task_id IN (
  'windowed_weak_transform.dwd_stock_dividend_event',
  'windowed_weak_qa.corporate_action_event_checks'
)
  AND updated_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
ORDER BY updated_at DESC;
```

如果 `qa_corporate_action_ledger_outputs` 的 staleness 断言失败，处理顺序是：

1. 确认当日 scheduled ingestion 是否已有 `dividend` meta 行（`success` 或正常 `empty_return`）。
2. 确认当日 `daily_current` 事件两步 task 是否成功；失败时先修 SQL / 数据问题后手工重跑 dwd/12 和 qa/14。
3. 只有分区确实缺失、或需要恢复早于 5 个开市日 lookback 的历史缺口时，才运行 `dividend_backfill` 手工补采。

手工补采最近一个缺口日示例：

```bash
gcloud run jobs execute ashare-ingest-current-scope \
  --project=data-aquarium \
  --region=asia-east2 \
  --args="--manifest,configs/ingestion/ods_dividend_backfill_v0.yml,--endpoint-group,dividend_backfill,--business-date,2026-06-05,--allow-gcs-write"
```

补采后重建事件表和 QA：

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/dwd/12_dwd_stock_dividend_event.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/14_corporate_action_event_checks.sql
```

## 5. Backfill

适用场景：补采历史 ODS 分区后，需要重新刷新一段 DWD/DWS 窗口。

按较小窗口分批执行，避免扩大 BigQuery DML 风险：

```bash
gcloud workflows execute ashare_warehouse_window_refresh \
  --project=data-aquarium \
  --location=asia-east2 \
  --data='{
    "business_date": "2026-06-05",
    "date_from": "2026-05-27",
    "date_to": "2026-06-05",
    "warehouse_mode": "backfill",
    "pipeline_dry_run": false,
    "run_label": "manual_backfill_20260527_20260605"
  }'
```

验收：

```sql
SELECT
  pipeline_run_id,
  pipeline_name,
  business_date,
  warehouse_mode,
  status,
  error_summary
FROM `data-aquarium.ashare_meta.pipeline_run`
WHERE run_label = 'manual_backfill_20260527_20260605'
ORDER BY started_at DESC;
```

## 6. 非交易日 skip 验证

生产 scheduler 在非交易日应由 `ashare_ods_ingestion_daily` 自动 skip，不触发 ingestion 或 warehouse refresh。

手工 smoke：

```bash
gcloud workflows execute ashare_ods_ingestion_daily \
  --project=data-aquarium \
  --location=asia-east2 \
  --data='{
    "business_date": "2026-06-07",
    "force_non_trading_day_gate": true,
    "pipeline_dry_run": false,
    "run_label": "manual_non_trading_day_skip_20260607"
  }'
```

验收：

```sql
SELECT pipeline_run_id, task_id, status, error_summary
FROM `data-aquarium.ashare_meta.pipeline_task_status`
WHERE pipeline_run_id IN (
  SELECT pipeline_run_id
  FROM `data-aquarium.ashare_meta.pipeline_run`
  WHERE run_label = 'manual_non_trading_day_skip_20260607'
)
ORDER BY updated_at;
```

期望看到 `skip_non_trading_day` 成功，且没有 linked warehouse write run。

## 7. Scheduler 没触发

查看 scheduler job：

```bash
gcloud scheduler jobs describe ashare-ods-ingestion-daily \
  --project=data-aquarium \
  --location=asia-east2
```

手工触发 scheduler job：

```bash
gcloud scheduler jobs run ashare-ods-ingestion-daily \
  --project=data-aquarium \
  --location=asia-east2
```

如果 scheduler job 正常但 workflow 没创建 execution，复核 caller SA：

```bash
gcloud projects get-iam-policy data-aquarium \
  --flatten="bindings[].members" \
  --filter="bindings.members:ashare-scheduler-invoker@data-aquarium.iam.gserviceaccount.com AND bindings.role:roles/workflows.invoker"
```

也可以重新应用 IAM bootstrap：

```bash
orchestration/workflows/bootstrap_scheduler_iam.sh
```

## 8. Alert checker 异常

手工触发 workflow：

```bash
gcloud workflows execute ashare_pipeline_alert_checker \
  --project=data-aquarium \
  --location=asia-east2 \
  --data='{
    "lookback_minutes": 70,
    "write_log": true,
    "write_heartbeat": true,
    "run_label": "manual_alert_checker_smoke"
  }'
```

手工触发 scheduler：

```bash
gcloud scheduler jobs run ashare-pipeline-alert-checker \
  --project=data-aquarium \
  --location=asia-east2
```

查询 heartbeat：

```bash
gcloud logging read \
  'jsonPayload.alert_type="alert_checker_heartbeat" AND jsonPayload.resource_id="ashare_pipeline_alert_checker"' \
  --project=data-aquarium \
  --limit=10 \
  --format=json
```

如果 heartbeat 缺失：

- 检查 `ashare_pipeline_alert_checker` workflow execution 是否失败。
- 检查 `ashare-pipeline-control` Cloud Run service 是否可被 workflows runtime SA invoke。
- 检查 `scripts/alerting/check_alerts.py` 依赖的 BigQuery 视图是否存在。
- 检查 Cloud Logging 写入权限。

### Ingestion Meta Missing

`Ashare Pipeline: Ingestion Meta Missing` 表示 live `ingestion.ingest_current_scope_write`
task 已成功，但对应业务日没有 `ashare_meta.ingestion_run` 行。先查检测视图：

```sql
SELECT *
FROM `data-aquarium.ashare_meta.v_ingestion_meta_missing`
ORDER BY detected_at DESC;
```

核对 Cloud Run execution 实际镜像 digest：

```bash
gcloud run jobs executions list \
  --job=ashare-ingest-current-scope \
  --project=data-aquarium \
  --region=asia-east2 \
  --format=json \
  --limit=20 \
| jq -r '.[] | [.metadata.name, .metadata.creationTimestamp, .spec.template.spec.containers[0].image, ((.spec.template.spec.containers[0].args // []) | join(" "))] | @tsv'
```

若 execution 使用旧 ingestion digest，按部署纪律从当前 `main` 重建 ingestion 镜像并确认
`ingestion:latest` 指向新 digest；若 job spec pin 旧 digest，则最小动作更新
`ashare-ingest-current-scope` 镜像，不改 args/IAM/Workflows 其他参数。不要补写历史
`ingestion_run` / `ingestion_partition_status` 行，除非 owner 另批。

## 9. Full rebuild

Full rebuild 是手工维护动作，不是日常恢复的默认选项。只有需要重建 DIM/DWD/DWS 全窗口时才使用。

低风险 dry-run：

```bash
gcloud workflows execute ashare_warehouse_full_rebuild \
  --project=data-aquarium \
  --location=asia-east2 \
  --data='{
    "business_date": "2026-06-05",
    "date_from": "2026-06-05",
    "date_to": "2026-06-05",
    "pipeline_dry_run": true,
    "confirm_full_rebuild": true,
    "run_label": "manual_full_rebuild_dryrun_20260605"
  }'
```

真实写入必须显式确认：

```bash
gcloud workflows execute ashare_warehouse_full_rebuild \
  --project=data-aquarium \
  --location=asia-east2 \
  --data='{
    "business_date": "2026-06-05",
    "date_from": "2019-01-01",
    "date_to": "2026-06-05",
    "pipeline_dry_run": false,
    "confirm_full_rebuild": true,
    "run_label": "manual_full_rebuild_20190101_20260605"
  }'
```

## 10. 什么时候不要重跑

- 非交易日 scheduler skip 成功时，不要为了“补当天”触发 ODS ingestion。
- 源端当天确实无数据时，不要手工写伪空 Parquet。
- 只有 QA 失败但 ODS 分区完整时，优先修窗口 SQL / DWD / DWS，不要重复采集。
- full rebuild 不用于普通单日恢复；优先用 `ashare_warehouse_window_refresh` 的 `daily_current` 或 `backfill`。

## 11. 相关文档

- `orchestration/workflows/README.md`
- `orchestration/workflows/bootstrap_scheduler_iam.sh`
- `orchestration/workflows/deploy_scheduler_jobs.sh`
- `orchestration/workflows/cutover_scheduler_jobs.sh`
- `scripts/alerting/README.md`
- `sql/observability/01_pipeline_status_views.sql`
