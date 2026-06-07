-- 文档维护：GPT-5 Codex（最近更新 2026-06-07）
-- BigQuery Standard SQL
-- ODS index external tables use explicit source URI lists. Keep the URI list in
-- sync with configs/ingestion/ods_current_scope_v0.yml request variants so new
-- GCS endpoint partitions are visible to BigQuery ODS reads.

CREATE OR REPLACE EXTERNAL TABLE `data-aquarium.ashare_ods.ods_tushare_index_daily`
WITH PARTITION COLUMNS (
  endpoint STRING,
  partition_date STRING
)
OPTIONS (
  description = '获取指数每日行情，还可以通过bar接口获取。由于服务器压力，目前规则是单次调取最多取8000行记录，可以设置start和end日期补全。指数行情也可以通过 通用行情接口 获取数据。本接口不包含 申万行业指数行情数据 。\nODS实际分区起始：1991-04-03（partition_date=19910403）。\nTushare官方口径：全部历史（官方文档 doc_id=108; doc_id=95）。',
  format = 'PARQUET',
  hive_partition_uri_prefix = 'gs://data-aquarium/a-share/tushare/raw_data/api=index_daily/',
  require_hive_partition_filter = TRUE,
  uris = [
    'gs://data-aquarium/a-share/tushare/raw_data/api=index_daily/endpoint=index_daily_000001_SH/partition_date=*/data.parquet',
    'gs://data-aquarium/a-share/tushare/raw_data/api=index_daily/endpoint=index_daily_000016_SH/partition_date=*/data.parquet',
    'gs://data-aquarium/a-share/tushare/raw_data/api=index_daily/endpoint=index_daily_000688_SH/partition_date=*/data.parquet',
    'gs://data-aquarium/a-share/tushare/raw_data/api=index_daily/endpoint=index_daily_000852_SH/partition_date=*/data.parquet',
    'gs://data-aquarium/a-share/tushare/raw_data/api=index_daily/endpoint=index_daily_000905_SH/partition_date=*/data.parquet',
    'gs://data-aquarium/a-share/tushare/raw_data/api=index_daily/endpoint=index_daily_399001_SZ/partition_date=*/data.parquet',
    'gs://data-aquarium/a-share/tushare/raw_data/api=index_daily/endpoint=index_daily_399006_SZ/partition_date=*/data.parquet',
    'gs://data-aquarium/a-share/tushare/raw_data/api=index_daily/endpoint=index_daily_399300_SZ/partition_date=*/data.parquet'
  ]
);

CREATE OR REPLACE EXTERNAL TABLE `data-aquarium.ashare_ods.ods_tushare_index_dailybasic`
WITH PARTITION COLUMNS (
  endpoint STRING,
  partition_date STRING
)
OPTIONS (
  description = '目前只提供上证综指，深证成指，上证50，中证500，中小板指，创业板指的每日指标数据\nODS实际分区起始：2004-01-02（partition_date=20040102）。\nTushare官方口径：从2004年1月开始提供 数据权（官方文档 doc_id=128）。',
  format = 'PARQUET',
  hive_partition_uri_prefix = 'gs://data-aquarium/a-share/tushare/raw_data/api=index_dailybasic/',
  require_hive_partition_filter = TRUE,
  uris = [
    'gs://data-aquarium/a-share/tushare/raw_data/api=index_dailybasic/endpoint=index_dailybasic_000001_SH/partition_date=*/data.parquet',
    'gs://data-aquarium/a-share/tushare/raw_data/api=index_dailybasic/endpoint=index_dailybasic_000016_SH/partition_date=*/data.parquet',
    'gs://data-aquarium/a-share/tushare/raw_data/api=index_dailybasic/endpoint=index_dailybasic_000905_SH/partition_date=*/data.parquet',
    'gs://data-aquarium/a-share/tushare/raw_data/api=index_dailybasic/endpoint=index_dailybasic_399001_SZ/partition_date=*/data.parquet',
    'gs://data-aquarium/a-share/tushare/raw_data/api=index_dailybasic/endpoint=index_dailybasic_399006_SZ/partition_date=*/data.parquet',
    'gs://data-aquarium/a-share/tushare/raw_data/api=index_dailybasic/endpoint=index_dailybasic_399300_SZ/partition_date=*/data.parquet'
  ]
);
