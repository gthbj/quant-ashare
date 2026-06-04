# Cloud Composer - 每日 A 股数据流水线

> 文档维护：GPT-5（最近更新 2026-06-04）

Composer 负责串联全流程：

1. Cloud Run Jobs 执行 Tushare 或 Tushare 兼容 API 到 GCS Parquet 采集。
2. BigQuery/ODS 每日分区 readiness 检查。
3. Dataform 或 BigQuery SQL 执行 ODS 到 DIM/DWD/DWS/ADS 转换。
4. 全量 schema 检查、P0 QA、策略 1 QA 和报告产物检查。
5. 失败重试、告警和运行状态追踪。

当前 DAG 是 Phase 1.7 生产采集入口，采集写入开关由 Airflow Variables 控制：

- `ashare_pipeline_dry_run=true` 时，Cloud Run Job 只执行采集计划展开，不写 GCS。
- `ashare_pipeline_dry_run=false` 时，DAG 会向 Cloud Run Job 传入 `--allow-gcs-write`，按业务日期写入当前范围 ODS 分区。
- 不直接保存 token。
- 每日默认主链只执行单个 Cloud Run ingestion（`ashare-ingest-current-scope`）和 `sql/qa/09_ods_daily_partition_readiness.sql`；该检查只读业务日分区或近期小窗口，不扫描 2019+ 全历史。
- `ashare_enable_full_refresh=false` 时，`sql/qa/06_ods_parquet_schema_checks.sql`、DIM、DWD、DWS、metadata、QA 全量链路不会进入每日主链。
- `ashare_enable_full_refresh=true` 时，DAG 在每日 readiness 之后进入 full refresh 分支，执行 schema P0、DIM、DWD、DWS、metadata、QA 节点。
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
```

## 部署 DAG

将 `orchestration/composer/dags/ashare_daily_pipeline_v0.py` 上传到 Composer 环境的 DAG bucket，并同步仓库 `sql/` 目录到 Composer bucket 下的 `data/sql/`。Composer 3 worker 会把该路径挂载为 `/home/airflow/gcs/data/sql`；当前 DAG 会在运行时读取这些 SQL 文件，缺少文件时对应 BigQuery task 会失败。

Cloud Run Job image 更新后，先用手工 DAG run 或临时变量做调度 smoke；确认 Cloud Run execution 和每日 ODS readiness 通过后，生产每日采集保持 `ashare_pipeline_dry_run=false`。完整 ODS→DIM/DWD/DWS/ADS 刷新需要单独将 `ashare_enable_full_refresh=true`。

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

设置 full refresh 开关：

```bash
gcloud composer environments run ashare-composer \
  --project=data-aquarium \
  --location=asia-east2 \
  variables set -- ashare_enable_full_refresh false
```

## 运行参数

手工触发时可传入业务日期：

```json
{
  "business_date": "2026-06-04"
}
```

未传入时使用 Airflow `ds`。
