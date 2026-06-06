# Cloud Composer - 每日 A 股数据流水线

> 文档维护：GPT-5 Codex（最近更新 2026-06-06）

Composer 负责串联全流程：

1. Cloud Run Jobs 执行 Tushare 或 Tushare 兼容 API 到 GCS Parquet 采集。
2. BigQuery/ODS 每日分区 readiness 检查。
3. Dataform 或 BigQuery SQL 执行 ODS 到 DIM/DWD/DWS/ADS 转换。
4. 全量 schema 检查、P0 QA、策略 1 QA 和报告产物检查。
5. 失败重试、告警和运行状态追踪。

当前 DAG 是 Phase 2.2 BigQuery SQL 兼容路径入口，采集写入、ODS readiness、窗口转换、可选全量转换、可选只读 QA、ADS 契约初始化和状态表回写由 Airflow Variables / DAG run conf 控制：

- `ashare_pipeline_dry_run=true` 时，Cloud Run Job 只执行采集计划展开，不写 GCS。
- `ashare_pipeline_dry_run=false` 时，DAG 会向 Cloud Run Job 传入 `--allow-gcs-write`，按业务日期写入当前范围 ODS 分区。
- 单次手工 DAG run 可用 `pipeline_dry_run` 或 `dry_run` 覆盖 `ashare_pipeline_dry_run`；dry-run 会让 ODS readiness 默认检查近期可读分区，真实写入会默认要求精确业务日/交易日分区。
- 不直接保存 token。
- 每日默认主链只执行单个 Cloud Run ingestion（`ashare-ingest-current-scope`）和 `sql/qa/09_ods_daily_partition_readiness.sql`；该检查只读业务日分区或近期小窗口，不扫描 2019+ 全历史。
- `ashare_warehouse_mode=daily_current` 且 `ashare_pipeline_dry_run=false` 时，DAG 在采集和 ODS readiness 后刷新 DIM 小表、恢复 P0 metadata，并执行 `sql/incremental/01_refresh_stock_dwd_dws_window.sql` 与 `sql/qa/10_windowed_stock_refresh_checks.sql`，按业务日期窗口刷新股票 DWD 与策略 1 DWS；窗口 SQL 会把非交易日 `date_to` / `business_date` 归一到不晚于请求日期的最近 SSE 开市日。
- `warehouse_mode=backfill` 且 `ashare_pipeline_dry_run=false` 时，DAG 按 `date_from` / `date_to` 执行同一窗口刷新链路；未传 `date_from` 时只刷新 `date_to` 或 `business_date`。
- `warehouse_mode=full_rebuild` 或 `warehouse_mode=full_rebuild_compat` 时，DAG 在每日 readiness 之后进入 BigQuery SQL 兼容转换分支，执行 schema P0、DIM、DWD、DWS、metadata、QA 节点。
- 兼容变量 `ashare_enable_full_refresh=true` 会把 `daily_current` 映射为 `full_rebuild_compat` 记录，避免把现有 CTAS 全量重建标记成增量。
- `warehouse_mode=qa_only` 时，DAG 只执行 ODS readiness 之后的 `01-05` 只读 QA，不改生产表。
- `skip_ingestion=true` 时，DAG 跳过 Cloud Run Job，直接从 ODS readiness 继续。
- `enable_ads_contract_init=true` 时，DAG 执行 `sql/ads/01_ads_strategy1_tables.sql`，该分支只用于手工初始化或补齐 ADS 契约。
- `ashare_meta.pipeline_run` 记录 DAG run terminal 状态；`ashare_meta.pipeline_task_status` 记录 task 状态、Airflow log URL、BigQuery job URL 和 Cloud Run execution URL。
- `sql/qa/08_ods_external_readability_checks.sql` 和 `sql/qa/06_ods_parquet_schema_checks.sql` 是维护/全量刷新检查，不作为每日调度默认门禁。
- 策略 1 ADS 实验/回测产物仍由策略 runner 写入；每日 DAG 不重跑 `sql/ads/01_ads_strategy1_tables.sql`，避免覆盖已有实验产物。

## 每日调度时间

DAG 按 Asia/Shanghai 时区每天 20:00 执行当前 14 个 ODS endpoint 采集。当前范围内官方文档给出的最晚明确日频更新时间为 17:00，20:00 留出 3 小时稳定窗口。

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

## 当前变量

在 Composer/Airflow Variables 中配置：

```text
ashare_project_id=data-aquarium
ashare_region=asia-east2
ashare_bq_location=asia-east2
ashare_pipeline_dry_run=false
ashare_enable_full_refresh=false
ashare_warehouse_mode=daily_current
ashare_transform_backend=bq_sql
ashare_enable_ads_contract_init=false
```

## 部署 DAG

将 `orchestration/composer/dags/ashare_daily_pipeline_v0.py` 上传到 Composer 环境的 DAG bucket，并同步仓库 `sql/` 目录到 Composer bucket 下的 `data/sql/`。Composer 3 worker 会把该路径挂载为 `/home/airflow/gcs/data/sql`；当前 DAG 会在运行时读取这些 SQL 文件，缺少文件时对应 BigQuery task 会失败。

Cloud Run Job image 更新后，先用手工 DAG run 或临时变量做调度 smoke；确认 Cloud Run execution、每日 ODS readiness、窗口刷新、窗口 QA 和状态表回写通过后，生产每日采集保持 `ashare_pipeline_dry_run=false`、`ashare_warehouse_mode=daily_current`。完整 ODS→DIM/DWD/DWS 刷新使用手工 DAG run 参数 `warehouse_mode=full_rebuild_compat` 或 `warehouse_mode=full_rebuild`。

部署命令：

```bash
gcloud composer environments storage dags import \
  --project=data-aquarium \
  --location=asia-east2 \
  --environment=ashare-composer \
  --source=orchestration/composer/dags/ashare_daily_pipeline_v0.py
```

同步 SQL：

```bash
gcloud storage rsync -r sql gs://asia-east2-ashare-composer-b2629133-bucket/data/sql
```

如果只上传 DAG 文件而没有同步 `sql/`，BigQuery task 会 fail-closed。

设置默认调度变量：

```bash
gcloud composer environments run ashare-composer \
  --project=data-aquarium \
  --location=asia-east2 \
  variables set -- ashare_enable_full_refresh false

gcloud composer environments run ashare-composer \
  --project=data-aquarium \
  --location=asia-east2 \
  variables set -- ashare_warehouse_mode daily_current

gcloud composer environments run ashare-composer \
  --project=data-aquarium \
  --location=asia-east2 \
  variables set -- ashare_transform_backend bq_sql

gcloud composer environments run ashare-composer \
  --project=data-aquarium \
  --location=asia-east2 \
  variables set -- ashare_enable_ads_contract_init false
```

## 运行参数

手工触发时可传入业务日期：

```json
{
  "business_date": "2026-06-04"
}
```

未传入时使用 `data_interval_end.in_timezone('Asia/Shanghai')` 对应日期。

单次采集 dry-run：

```json
{
  "business_date": "2026-06-04",
  "pipeline_dry_run": true,
  "run_label": "manual_ingestion_dry_run"
}
```

单次真实采集写入：

```json
{
  "business_date": "2026-06-04",
  "pipeline_dry_run": false,
  "run_label": "manual_ingestion_write"
}
```

`require_business_partition` 可在手工 smoke 中覆盖 readiness 门禁；不传时，dry-run 默认 `false`，真实写入默认 `true`。

只重跑下游 readiness / QA：

```json
{
  "business_date": "2026-06-04",
  "skip_ingestion": true,
  "warehouse_mode": "qa_only",
  "run_label": "manual_smoke"
}
```

手工执行 BigQuery SQL 兼容全量转换：

```json
{
  "business_date": "2026-06-04",
  "skip_ingestion": true,
  "warehouse_mode": "full_rebuild_compat",
  "run_label": "maintenance"
}
```

手工执行股票 DWD/DWS 窗口补跑：

```json
{
  "business_date": "2026-06-04",
  "date_from": "2026-06-03",
  "date_to": "2026-06-04",
  "skip_ingestion": true,
  "pipeline_dry_run": false,
  "warehouse_mode": "backfill",
  "run_label": "windowed_stock_backfill"
}
```

手工初始化 ADS 契约：

```json
{
  "business_date": "2026-06-04",
  "skip_ingestion": true,
  "warehouse_mode": "daily_current",
  "enable_ads_contract_init": true,
  "run_label": "maintenance"
}
```
