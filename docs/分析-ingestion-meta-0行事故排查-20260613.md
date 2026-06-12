> 文档维护：GPT-5.5（最近更新 2026-06-13）

# ashare_meta ingestion meta 0 行事故排查

## 结论

根因已确认：生产 `ashare-ingest-current-scope` job 模板一直使用 `ingestion:latest`，但 2026-06-04 旧镜像 `sha256:351dfd996b6ec066135d68c40f84eb1c2a52e43ea8e28208ba1711be90a7652d` 构建早于仓库接入 `IngestionStatusWriter`，因此 2026-06-09、06-10、06-11 的 live ingestion 虽然成功写 GCS、pipeline task 也成功，却没有任何代码路径写 `ashare_meta.ingestion_run` / `ingestion_partition_status`。

这不是 dry-run 或 `--skip-gcs-write` 设计行为：Workflows 生产路径传入的是 `--allow-gcs-write`。当前代码只在 dry-run 直接返回、或 `--skip-gcs-write` 时不初始化 `IngestionStatusWriter`；live 写入路径必须写 meta。

当前不需要更新 Cloud Run job spec：job spec 仍是 `asia-east2-docker.pkg.dev/data-aquarium/ashare/ingestion:latest`，不是 digest pin。Cloud Run execution 在创建时解析 tag；2026-06-12 20:00 CST scheduled execution 已解析到修复镜像 `sha256:5c78e8624584e9ee47471be087ba7e4090d00477a37ec276920f8696810c3f3b` 并落 27 条 meta。之后 dividend 补采构建把 `latest` 推到 `sha256:35acbc363408d05dd758d70ba5f293e8b0d333a000c6dfe8e8143ddadd0b8bba`，后续 dividend executions 也已实证写 meta。

## 根因链

1. 代码演进：`60fb242`（2026-06-04 23:57 CST）新增 `scripts/ingestion/common/status_writer.py`，并在 `run_ingestion_job.py` 中把 live 结果/失败写入 `ashare_meta`；同一变更让 `endpoint_runner` 返回 `request_params_hash`、`schema_version`、`gcs_uri`、`status` 等 meta 写入字段。
2. 镜像历史：2026-06-04 11:49 UTC 的 ingestion build 产物为旧 digest `351dfd...`；直到 2026-06-12 09:02 UTC build `8053b0d5` 之前，没有新的 ingestion image build。期间其他 builds 是 pipeline-control / Strategy1 runner，不会更新 ingestion job 使用的代码。
3. 执行历史：2026-06-09 `ashare-ingest-current-scope-hk9l8`、2026-06-10 `n4q4p`、2026-06-11 `k42np` 都使用 `351dfd...`。对应 `pipeline_task_status.task_id='ingestion.ingest_current_scope_write'` 为 success，但 `ingestion_run` 对应业务日 meta rows 均为 0。
4. 修复实证：2026-06-12 build `8053b0d5` 推 `5c78...` 到 `:latest`；同日手工 backfill 和 20:00 CST scheduled current_scope execution `9wnh8` 均使用 `5c78...`，并写入 meta。

## 时间线

| 时间 | 事件 | 证据 |
|---|---|---|
| 2026-06-04 11:49 UTC | 旧 ingestion image build 完成 | Cloud Build `35bca022...`，后续 executions 使用 digest `351dfd...` |
| 2026-06-04 15:57 UTC | 仓库接入 meta 写入 | commit `60fb242` 新增 `IngestionStatusWriter` |
| 2026-06-09 20:36 CST | live recovery ingestion 成功但 meta 0 行 | pipeline run `39e42cbf...`，meta_rows=0 |
| 2026-06-10 20:00 CST | scheduled ingestion 成功但 meta 0 行 | pipeline run `8c62ce42...`，meta_rows=0 |
| 2026-06-11 20:00 CST | scheduled ingestion 成功但 meta 0 行 | pipeline run `5e790d75...`，meta_rows=0 |
| 2026-06-12 17:04 CST | PR #196 修复镜像重建 | build `8053b0d5`，digest `5c78...` |
| 2026-06-12 20:00 CST | scheduled ingestion 写入 meta | execution `9wnh8`，`ingestion_run` 27 行 |
| 2026-06-12 22:42 CST | dividend 补采镜像重建 | build `8da0a512`，digest `35acbc...` 成为 `latest` |

## 当前状态

- `ashare-ingest-current-scope` job spec image 仍是 `ingestion:latest`，job generation 仍为 1；本轮未改 job spec、IAM、Workflow 或 Scheduler 参数。
- Artifact Registry 当前 `latest` 指向 `sha256:35acbc363408d05dd758d70ba5f293e8b0d333a000c6dfe8e8143ddadd0b8bba`。
- BigQuery 当前 `ingestion_run` 共 43 行：40 success、3 empty_return、0 failed；最早 `created_at=2026-06-12 09:06:23 UTC`，最晚 `2026-06-12 14:48:05 UTC`。
- 2026-06-12 scheduled current_scope meta 分布：market_eod 5 success，index_eod 14 success，dim_snapshot 4 success，finance_recent 1 success + 3 empty_return，合计 27 行。
- 2026-06-12 下游 `daily_current` window refresh 失败于 SSE Composite 000001.SH 历史覆盖 QA；这与 ingestion meta 修复是独立问题，且 alert checker 已能通过 pipeline/task failure 报出。

## 告警静默缺口

原 `ashare-pipeline-alert-checker` 路径是：

`Cloud Scheduler -> Workflows -> ashare-pipeline-control /v1/tasks/alert-check -> check_alerts.py -> v_alert_summary`

原 `v_alert_summary` 覆盖 pipeline failure、task failure、warehouse refresh missing、`ingestion_run.status='failed'`。它没有覆盖“live ingestion task success，但 `ingestion_run` 完全没行”的情况；而旧镜像正好不会写 `ingestion_run`，所以 `ingestion_failed` 也没有数据来源。这就是告警全程静默的缺口。

本 PR 新增：

- `ashare_meta.v_ingestion_meta_missing`：检测 `ashare_ods_ingestion_daily` 的 `ingestion.ingest_current_scope_write` task 已 success，但对应 business_date 在任务窗口内没有 `ingestion_run` 行。
- `v_alert_summary` 新增 `alert_type='ingestion_meta_missing'`。
- `setup_alerts.py` 新增 `ashare_pipeline_ingestion_meta_missing` log metric 和 `Ashare Pipeline: Ingestion Meta Missing` policy。

用历史数据回放该检测逻辑：2026-06-09、06-10、06-11 会 `would_alert`；2026-06-12 修复后 `meta_rows=27`，不会误报。

## 历史缺口处置

建议不回填历史 meta 行。

理由：缺失的 2026-06-09 至 06-11 meta 是观测链路缺口，不是 ODS raw 数据缺失本身；事后根据 GCS / Cloud Run / pipeline_task_status 生成伪 meta 会混淆“当时真实写入的审计记录”和“事后重建记录”。本报告、PR #196 记录、Cloud Run execution history、BigQuery pipeline status 足以作为审计证据。若 owner 后续需要，可另建只读 audit report 或 derived view，不直接补写生产 `ingestion_run` / `ingestion_partition_status`。

## 2026-06-13 晚间验证计划

本机当前时间为 2026-06-13 00:16 CST。Cloud Scheduler 下一次 `ashare-ods-ingestion-daily` 触发时间是 2026-06-13 20:00 CST。

但 2026-06-13 是周六，`ashare_dim.dim_trade_calendar` 显示 SSE `is_open=0`；2026-06-14 也不开市，下一开市日是 2026-06-15。因此 2026-06-13 20:00 CST 应验证的是非交易日 gate，而不是 live ingestion meta 写入：

1. Scheduler execution 成功启动 `ashare_ods_ingestion_daily`。
2. `pipeline_task_status` 有 `non_trading_day_gate` success 和 `skip_non_trading_day` skipped/success 记录。
3. 不应创建新的 `ashare-ingest-current-scope` live execution，也不应期待 `ingestion_run` 新增 20260613 行。

下一次 live ingestion meta 验证应放在 2026-06-15 20:00 CST 后：

1. `gcloud run jobs executions list --job=ashare-ingest-current-scope` 确认 execution image digest。若没有新的 ingestion build，预期为 `35acbc...`。
2. 查询 `ingestion_run`：业务日 `20260615` 应出现 current_scope 约 27 行，且 success / empty_return 分布符合 endpoint 当日返回。
3. 查询 `v_ingestion_meta_missing` 和 `v_alert_summary`，确认无 `ingestion_meta_missing`。
