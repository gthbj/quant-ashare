# scripts/ingestion — Tushare 兼容 API → GCS Parquet 采集框架
#
# ODS 采集：endpoint-group worker、分页 API client、schema cast、GCS staging/publish。
#
# 目录结构：
#   common/
#     api_client.py    — Tushare 兼容 API 客户端（节流、重试、limit/offset 分页）
#     endpoint_runner.py — endpoint group 计划执行、血缘列、分区写入
#     gcs_writer.py    — GCS staging / publish 写入
#     parquet_schema.py — Parquet schema 校验与 cast
#     manifest.py      — 读取 ods_current_scope_v0.yml
#     logging.py       — 结构化日志（脱敏）
#   endpoints/
#     daily.py         — daily, adj_factor, stk_limit, suspend_d, daily_basic
#     index.py         — index_daily, index_dailybasic
#     dim_snapshot.py  — stock_basic, trade_cal, namechange
#     finance.py       — fina_indicator, income, balancesheet, cashflow
#     corporate_actions.py — dividend
#
# Cloud Run Job dry-run 示例：
#
#   python scripts/ingestion/run_ingestion_job.py \
#     --endpoint-group market_eod \
#     --business-date 2026-06-04 \
#     --dry-run \
#     --output-json
#
# 真实运行时，TUSHARE_TOKEN 必须通过运行时环境变量或 GCP Secret Manager
# 注入；Tushare 官方或兼容 API 地址通过 TUSHARE_HTTP_URL 配置。不要把 token
# 写入代码、配置、日志或文档。
#
# 只读 API smoke 示例（调用 API 并做 schema cast，不写 GCS）：
#
#   TUSHARE_TOKEN="$(gcloud secrets versions access latest \
#     --secret=tushare-token --project=data-aquarium)" \
#   TUSHARE_HTTP_URL="$TUSHARE_HTTP_URL" \
#   python scripts/ingestion/run_ingestion_job.py \
#     --endpoint-group index_eod \
#     --business-date 2026-06-03 \
#     --skip-gcs-write \
#     --output-json
#
# 口径：
# - 日频行情按业务日期整分区写 `data.parquet`。
# - 指数行情按 dim_index 中真实 ODS endpoint key 拆成多个 partition endpoint。
# - 财务表调用 `*_vip` API，按返回的 `end_date` 写报告期分区；正式写入时会读取
#   既有 `data.parquet` 并按业务主键 merge，避免公告日增量覆盖整个报告期历史。
# - `corporate_actions` 的 `dividend` 按 `lookback_open_days=5` 从
#   `ashare_dim.dim_trade_calendar` 解析最近 5 个 SSE 开市日，逐日请求 `ex_date`
#   并覆盖对应 `partition_date=ex_date` 分区；`dividend_backfill` 保留为历史缺口手工组。
# - 空返回只返回 `empty_return` 状态，不写伪空 Parquet。
# - live 写入会写 `ashare_meta.ingestion_run` 和
#   `ashare_meta.ingestion_partition_status`；dry-run / API 只读 smoke 不写 meta。
# - GCS canonical 路径为 `api=<api>/endpoint=<partition_endpoint>/partition_date=...`，
#   不使用 `api=tushare`。
