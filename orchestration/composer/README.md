# Cloud Composer - A 股数据流水线

> 文档维护：GPT-5 Codex（最近更新 2026-06-06）

Composer 负责串联 Cloud Run ingestion、BigQuery SQL 数仓刷新、状态回写、告警 checker 和故障恢复入口。当前 OQ-005 生产入口已按职责拆分，`ashare_daily_pipeline_v0` 保留为迁移期回滚参考。

## DAG 边界

| DAG | 调度 | 职责 |
|---|---|---|
| `ashare_ods_ingestion_daily` | 每日 20:00 Asia/Shanghai | 当前 14 个 ODS endpoint 采集、非交易日 gate、ODS readiness，真实写入成功后触发窗口刷新 |
| `ashare_warehouse_window_refresh` | 由 ingestion DAG 触发；也支持手工 | `daily_current` / `backfill` 的 DIM/DWD/DWS 窗口刷新、metadata 恢复、窗口 QA 和只读 QA |
| `ashare_warehouse_full_rebuild` | 手工触发 | 显式确认后的 DIM/DWD/DWS 全量维护重建 |
| `oq005_alert_checker` | 每 10 分钟 | 查询观测视图，写 Cloud Logging 告警和 heartbeat |

`ashare_meta.pipeline_run` 记录每个 DAG run 的 terminal 状态；`ashare_meta.pipeline_task_status` 记录 task 状态、Airflow log URL、BigQuery job URL 和 Cloud Run execution URL。跨 DAG 链路通过 `pipeline_run.upstream_pipeline_run_id` 与 `pipeline_run.triggered_by_dag_id` 记录。

`ashare_ods_ingestion_daily` 显式设置 `is_paused_upon_creation=True`。部署到 Composer 后先保持 paused；迁移生产定时时，先暂停旧 `ashare_daily_pipeline_v0`，再 unpause 新 ingestion DAG。迁移期任一时刻只允许一个 production scheduled DAG active。

`ashare_warehouse_window_refresh` 使用 `max_active_runs=1` 串行执行，避免 triggered `daily_current` 与手工 `backfill` 对同一 DWD/DWS 窗口并发 DML。手工 backfill 会排队等待当前窗口刷新结束。

## 每日链路

```text
ashare_ods_ingestion_daily
  -> non_trading_day_gate
  -> Cloud Run Job: ashare-ingest-current-scope
  -> sql/qa/09_ods_daily_partition_readiness.sql
  -> TriggerDagRunOperator: ashare_warehouse_window_refresh

ashare_warehouse_window_refresh
  -> sql/qa/09_ods_daily_partition_readiness.sql
  -> windowed_dim
  -> windowed_metadata
  -> sql/incremental/01_refresh_stock_dwd_dws_window.sql
  -> sql/qa/10_windowed_stock_refresh_checks.sql
  -> sql/qa/01-05
```

scheduled `ashare_ods_ingestion_daily` 在非交易日会查 `ashare_dim.dim_trade_calendar`。SSE 当天不开市时写入 `skip_non_trading_day` task 状态，且不触发 Cloud Run、ODS readiness 或 warehouse refresh。普通手工触发不自动走该 gate，除非显式设置 `force_non_trading_day_gate=true` 做 smoke。

每日真实写入链路使用 `pipeline_dry_run=false`。手工 dry-run 或 `skip_ingestion=true` 默认不触发下游 warehouse refresh；如需用只读 readiness 后继续触发窗口刷新，显式传 `trigger_downstream_refresh=true`。

## 每日调度时间

`ashare_ods_ingestion_daily` 按 Asia/Shanghai 每天 20:00 触发。当前范围内官方文档给出的最晚明确日频更新时间为 17:00，20:00 留出 3 小时稳定窗口。

| endpoint | 官方更新时间口径 | 官方文档 |
|---|---|---|
| `daily` | 交易日每天 15:00-16:00 入库 | [A股日线行情](https://www.tushare.pro/document/2?doc_id=27) |
| `daily_basic` | 交易日每日 15:00-17:00 之间 | [每日指标](https://tushare.pro/document/2?doc_id=32) |
| `adj_factor` | 盘前 9:15-9:20 完成当日复权因子入库 | [复权因子](https://tushare.pro/document/2?doc_id=28) |
| `stk_limit` | 每个交易日 8:40 左右更新当日涨跌停价格 | [每日涨跌停价格](https://www.tushare.pro/document/2?doc_id=183) |
| `suspend_d` | 不定期 | [每日停复牌信息](https://tushare.pro/document/2?doc_id=214) |
| `index_daily` | 交易日 15:00-17:00 更新 | [积分权限/接口列表](https://www.tushare.pro/document/2?doc_id=108) |
| `index_dailybasic` | 每日盘后更新 | [大盘指数每日指标](https://tushare.pro/document/2?doc_id=128) |
| `stock_basic` | 基础信息接口，无明确日内更新时间；每日快照采集 | [股票基础信息](https://tushare.pro/document/2?doc_id=25) |
| `trade_cal` | 交易日历接口，无明确日内更新时间；每日快照采集 | [交易日历](https://www.tushare.pro/document/2?doc_id=26) |
| `namechange` | 历史名称变更记录，无明确日内更新时间；每日快照采集 | [股票曾用名](https://tushare.pro/document/2?doc_id=100) |
| `fina_indicator` | 随财报实时更新 | [财务指标数据](https://tushare.pro/document/2?doc_id=79) |
| `income` | 财务数据接口，官方接口列表口径为实时更新 | [利润表](https://tushare.pro/document/2?doc_id=33) |
| `balancesheet` | 财务数据接口，官方接口列表口径为实时更新 | [资产负债表](https://tushare.pro/document/2?doc_id=36) |
| `cashflow` | 财务数据接口，官方接口列表口径为实时更新 | [现金流量表](https://www.tushare.pro/document/2?doc_id=44) |

## 当前环境

```text
project=data-aquarium
region=asia-east2
composer_environment=ashare-composer
service_account=sa-ashare-ingestion@data-aquarium.iam.gserviceaccount.com
```

## Airflow Variables

```text
ashare_project_id=data-aquarium
ashare_region=asia-east2
ashare_bq_location=asia-east2
ashare_pipeline_dry_run=false
ashare_enable_full_refresh=false
ashare_warehouse_mode=daily_current
ashare_transform_backend=bq_sql
```

## 部署

同步 DAG 文件：

```bash
gcloud composer environments storage dags import \
  --project=data-aquarium \
  --location=asia-east2 \
  --environment=ashare-composer \
  --source=orchestration/composer/dags/ashare_common.py

gcloud composer environments storage dags import \
  --project=data-aquarium \
  --location=asia-east2 \
  --environment=ashare-composer \
  --source=orchestration/composer/dags/ashare_ods_ingestion_daily.py

gcloud composer environments storage dags import \
  --project=data-aquarium \
  --location=asia-east2 \
  --environment=ashare-composer \
  --source=orchestration/composer/dags/ashare_warehouse_window_refresh.py

gcloud composer environments storage dags import \
  --project=data-aquarium \
  --location=asia-east2 \
  --environment=ashare-composer \
  --source=orchestration/composer/dags/ashare_warehouse_full_rebuild.py
```

同步 SQL：

```bash
gcloud storage rsync -r sql gs://asia-east2-ashare-composer-b2629133-bucket/data/sql
```

应用观测视图和告警规则：

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/observability/01_pipeline_status_views.sql
python scripts/alerting/setup_alerts.py --dry-run
```

如果只上传 DAG 文件而没有同步 `sql/`，BigQuery task 会 fail-closed。

## 手工触发示例

单次真实采集写入，成功后自动触发窗口刷新：

```json
{
  "business_date": "2026-06-05",
  "pipeline_dry_run": false,
  "run_label": "manual_ingestion_write"
}
```

单次采集 dry-run，不触发下游刷新：

```json
{
  "business_date": "2026-06-05",
  "pipeline_dry_run": true,
  "run_label": "manual_ingestion_dry_run"
}
```

只跑 ODS readiness：

```json
{
  "business_date": "2026-06-05",
  "skip_ingestion": true,
  "pipeline_dry_run": false,
  "run_label": "manual_readiness_only"
}
```

手工窗口 backfill：

```bash
python scripts/pipeline/run_warehouse_refresh.py backfill \
  --date-from 2026-05-11 \
  --date-to 2026-06-05 \
  --chunk-days 5 \
  --resume

python scripts/pipeline/run_warehouse_refresh.py backfill \
  --date-from 2026-05-11 \
  --date-to 2026-06-05 \
  --chunk-days 5 \
  --resume \
  --execute \
  --wait \
  --fail-fast
```

```json
{
  "business_date": "2026-06-05",
  "date_from": "2026-05-11",
  "date_to": "2026-06-05",
  "pipeline_dry_run": false,
  "warehouse_mode": "backfill",
  "run_label": "manual_window_backfill"
}
```

只跑 warehouse QA：

```bash
python scripts/pipeline/run_warehouse_refresh.py qa-only \
  --business-date 2026-06-05

python scripts/pipeline/run_warehouse_refresh.py qa-only \
  --business-date 2026-06-05 \
  --execute \
  --wait \
  --fail-fast
```

手工全量维护重建：

```json
{
  "business_date": "2026-06-05",
  "date_from": "2019-01-01",
  "date_to": "2026-06-05",
  "warehouse_mode": "full_rebuild",
  "pipeline_dry_run": false,
  "confirm_full_rebuild": true,
  "run_label": "manual_full_rebuild"
}
```

非交易日 gate smoke：

```json
{
  "business_date": "2026-06-06",
  "force_non_trading_day_gate": true,
  "pipeline_dry_run": false,
  "run_label": "manual_skip_gate_smoke"
}
```

## 迁移验收

1. 新 DAG 全部通过 Composer import，并确认 `ashare_ods_ingestion_daily` 仍为 paused。
2. 暂停旧 `ashare_daily_pipeline_v0` 后，再 unpause 新 `ashare_ods_ingestion_daily`；迁移期任一时刻只允许一个 production scheduled DAG active。
3. `ashare_ods_ingestion_daily` 开市日真实写入成功，并触发 `ashare_warehouse_window_refresh`。
4. `ashare_ods_ingestion_daily` 非交易日 smoke 写入 `skip_non_trading_day`，且 Cloud Run execution 未新增。
5. `ashare_warehouse_window_refresh` 小窗口 backfill 通过 `10_windowed_stock_refresh_checks.sql` 和 `01-05` QA。
6. `v_pipeline_refresh_missing` 能发现 ingestion 成功但没有 linked warehouse refresh run 的链路缺失。
7. 新生产 DAG 连续通过至少两个开市日 scheduled run 和一个非交易日 skip smoke，旧 `ashare_daily_pipeline_v0` 保持 paused。
