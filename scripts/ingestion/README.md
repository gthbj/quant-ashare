# scripts/ingestion — Tushare/Tinyshare → GCS Parquet 采集框架
#
# Phase 0: 目录结构与 stub。Phase 1 补充实现。
#
# 目录结构：
#   common/
#     api_client.py    — Tushare/Tinyshare API 客户端（节流、重试、分页）
#     gcs_writer.py    — GCS staging / publish 写入
#     parquet_schema.py — Parquet schema 校验与 cast
#     manifest.py      — 读取 ods_current_scope_v0.yml
#     logging.py       — 结构化日志（脱敏）
#   endpoints/
#     daily.py         — daily, adj_factor, stk_limit, suspend_d, daily_basic
#     index.py         — index_daily, index_dailybasic
#     dim_snapshot.py  — stock_basic, trade_cal, namechange
#     finance.py       — fina_indicator, income, balancesheet, cashflow
