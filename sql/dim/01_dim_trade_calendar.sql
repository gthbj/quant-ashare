-- 文档维护：GPT-5（最近更新 2026-05-31）
-- BigQuery Standard SQL
-- 交易日历维表：取 trade_cal 最新快照。cal_date 可覆盖 2019 以前历史，用于 t-1/t-k 和 lookback 边界。

CREATE OR REPLACE TABLE `data-aquarium.ashare_dim.dim_trade_calendar`
CLUSTER BY exchange, cal_date
OPTIONS (
  description = 'Trading calendar dimension from latest Tushare trade_cal snapshot'
) AS
WITH latest_snapshot AS (
  SELECT MAX(partition_date) AS partition_date
  FROM `data-aquarium.ashare_ods.ods_tushare_trade_cal`
  WHERE endpoint = 'trade_cal'
    AND partition_date BETWEEN '00000000' AND '99999999'
),
base AS (
  SELECT
    t.exchange,
    SAFE.PARSE_DATE('%Y%m%d', t.cal_date) AS cal_date,
    SAFE_CAST(t.is_open AS INT64) AS is_open,
    SAFE.PARSE_DATE('%Y%m%d', NULLIF(t.pretrade_date, '')) AS pre_trade_date,
    COALESCE(t._source, 'tushare') AS source_system,
    t.partition_date AS source_partition_date,
    SAFE_CAST(t._ingested_at AS TIMESTAMP) AS ingested_at
  FROM `data-aquarium.ashare_ods.ods_tushare_trade_cal` AS t
  JOIN latest_snapshot AS s
    ON t.partition_date = s.partition_date
  WHERE t.endpoint = 'trade_cal'
    AND t.cal_date IS NOT NULL
)
SELECT
  exchange,
  cal_date,
  is_open,
  pre_trade_date,
  IF(
    is_open = 1,
    COUNTIF(is_open = 1) OVER (PARTITION BY exchange ORDER BY cal_date),
    NULL
  ) AS trade_date_seq,
  source_system,
  source_partition_date,
  ingested_at
FROM base
WHERE cal_date IS NOT NULL;

ALTER TABLE `data-aquarium.ashare_dim.dim_trade_calendar`
ALTER COLUMN exchange SET OPTIONS (description = '交易所代码，如 SSE/SZSE/CFFEX'),
ALTER COLUMN cal_date SET OPTIONS (description = '自然日期'),
ALTER COLUMN is_open SET OPTIONS (description = '是否交易日，1=开市，0=休市'),
ALTER COLUMN pre_trade_date SET OPTIONS (description = '上一交易日'),
ALTER COLUMN trade_date_seq SET OPTIONS (description = '交易日序号，仅开市日有值');
