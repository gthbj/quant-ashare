-- 文档维护：GPT-5（最近更新 2026-06-01）
-- BigQuery Standard SQL
-- 股票主维表：取 stock_basic 最新快照，补充少量缺主数据代码的生命周期边界。

DECLARE dwd_start_date DATE DEFAULT DATE '2019-01-01';
DECLARE derived_delist_grace_days INT64 DEFAULT 30;

CREATE OR REPLACE TABLE `data-aquarium.ashare_dim.dim_stock`
CLUSTER BY sec_code
OPTIONS (
  description = 'Stock security master dimension with lifecycle boundaries for 2019+ DWD universe'
) AS
WITH stock_basic_latest AS (
  SELECT
    endpoint,
    MAX(partition_date) AS partition_date
  FROM `data-aquarium.ashare_ods.ods_tushare_stock_basic`
  WHERE endpoint IN ('stock_basic_listed', 'stock_basic_delisted')
    AND partition_date BETWEEN '00000000' AND '99999999'
  GROUP BY endpoint
),
stock_basic AS (
  SELECT
    s.ts_code,
    s.symbol,
    s.name,
    s.area,
    s.industry,
    s.market,
    s.exchange,
    s.curr_type,
    s.list_status,
    SAFE.PARSE_DATE('%Y%m%d', NULLIF(s.list_date, '')) AS list_date,
    SAFE.PARSE_DATE('%Y%m%d', NULLIF(s.delist_date, '')) AS source_delist_date,
    s.endpoint,
    s.partition_date,
    SAFE_CAST(s._ingested_at AS TIMESTAMP) AS ingested_at
  FROM `data-aquarium.ashare_ods.ods_tushare_stock_basic` AS s
  JOIN stock_basic_latest AS l
    ON s.endpoint = l.endpoint
   AND s.partition_date = l.partition_date
  WHERE s.endpoint IN ('stock_basic_listed', 'stock_basic_delisted')
    AND s.ts_code IS NOT NULL
),
daily_lifecycle AS (
  SELECT
    ts_code,
    MIN(SAFE.PARSE_DATE('%Y%m%d', trade_date)) AS first_trade_date,
    MAX(SAFE.PARSE_DATE('%Y%m%d', trade_date)) AS last_trade_date
  FROM `data-aquarium.ashare_ods.ods_tushare_daily`
  WHERE endpoint = 'daily'
    AND partition_date BETWEEN '00000000' AND '99999999'
    AND trade_date IS NOT NULL
  GROUP BY ts_code
),
latest_market_trade AS (
  SELECT MAX(SAFE.PARSE_DATE('%Y%m%d', trade_date)) AS market_last_trade_date
  FROM `data-aquarium.ashare_ods.ods_tushare_daily`
  WHERE endpoint = 'daily'
    AND partition_date >= FORMAT_DATE('%Y%m%d', dwd_start_date)
    AND trade_date IS NOT NULL
),
stock_basic_enriched AS (
  SELECT
    s.ts_code AS sec_code,
    s.symbol,
    s.name AS sec_name,
    'stock' AS sec_type,
    s.area,
    s.industry,
    s.market,
    CASE
      WHEN s.ts_code LIKE '%.SH' THEN 'SSE'
      WHEN s.ts_code LIKE '%.SZ' THEN 'SZSE'
      WHEN s.ts_code LIKE '%.BJ' THEN 'BSE'
      ELSE s.exchange
    END AS exchange,
    CASE
      WHEN s.ts_code LIKE '%.BJ' THEN 'BSE'
      WHEN STARTS_WITH(s.ts_code, '688') THEN 'STAR'
      WHEN STARTS_WITH(s.ts_code, '300') OR STARTS_WITH(s.ts_code, '301') THEN 'CHINEXT'
      WHEN s.ts_code LIKE '%.SH' THEN 'SSE_MAIN'
      WHEN s.ts_code LIKE '%.SZ' THEN 'SZSE_MAIN'
      ELSE NULL
    END AS board,
    s.curr_type,
    s.list_status,
    s.list_date,
    IF(
      s.list_status = 'D',
      COALESCE(s.source_delist_date, DATE_ADD(d.last_trade_date, INTERVAL 1 DAY)),
      NULL
    ) AS delist_date,
    d.first_trade_date,
    d.last_trade_date,
    s.list_status = 'D' AS is_delisted,
    'stock_basic' AS stock_master_source,
    CASE
      WHEN s.list_status != 'D' THEN NULL
      WHEN s.source_delist_date IS NOT NULL THEN 'stock_basic_delist_date'
      WHEN d.last_trade_date IS NOT NULL THEN 'last_trade_date_plus_1_fallback'
      ELSE 'missing_delist_date'
    END AS delist_date_source,
    s.partition_date AS source_partition_date,
    s.ingested_at
  FROM stock_basic AS s
  LEFT JOIN daily_lifecycle AS d
    ON s.ts_code = d.ts_code
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY s.ts_code
    ORDER BY
      IF(s.endpoint = 'stock_basic_listed', 0, 1),
      s.partition_date DESC,
      s.ingested_at DESC
  ) = 1
),
daily_codes_2019 AS (
  SELECT
    d.ts_code,
    MIN(SAFE.PARSE_DATE('%Y%m%d', d.trade_date)) AS first_trade_date,
    MAX(SAFE.PARSE_DATE('%Y%m%d', d.trade_date)) AS last_trade_date
  FROM `data-aquarium.ashare_ods.ods_tushare_daily` AS d
  WHERE d.endpoint = 'daily'
    AND d.partition_date >= FORMAT_DATE('%Y%m%d', dwd_start_date)
    AND d.trade_date IS NOT NULL
  GROUP BY d.ts_code
),
missing_from_stock_basic AS (
  SELECT
    d.ts_code AS sec_code,
    REGEXP_EXTRACT(d.ts_code, r'^([0-9]+)') AS symbol,
    CAST(NULL AS STRING) AS sec_name,
    'stock' AS sec_type,
    CAST(NULL AS STRING) AS area,
    CAST(NULL AS STRING) AS industry,
    CAST(NULL AS STRING) AS market,
    CASE
      WHEN d.ts_code LIKE '%.SH' THEN 'SSE'
      WHEN d.ts_code LIKE '%.SZ' THEN 'SZSE'
      WHEN d.ts_code LIKE '%.BJ' THEN 'BSE'
      ELSE NULL
    END AS exchange,
    CASE
      WHEN d.ts_code LIKE '%.BJ' THEN 'BSE'
      WHEN STARTS_WITH(d.ts_code, '688') THEN 'STAR'
      WHEN STARTS_WITH(d.ts_code, '300') OR STARTS_WITH(d.ts_code, '301') THEN 'CHINEXT'
      WHEN d.ts_code LIKE '%.SH' THEN 'SSE_MAIN'
      WHEN d.ts_code LIKE '%.SZ' THEN 'SZSE_MAIN'
      ELSE NULL
    END AS board,
    'CNY' AS curr_type,
    'UNKNOWN' AS list_status,
    d.first_trade_date AS list_date,
    IF(
      d.last_trade_date < DATE_SUB(m.market_last_trade_date, INTERVAL derived_delist_grace_days DAY),
      DATE_ADD(d.last_trade_date, INTERVAL 1 DAY),
      NULL
    ) AS delist_date,
    d.first_trade_date,
    d.last_trade_date,
    d.last_trade_date < DATE_SUB(m.market_last_trade_date, INTERVAL derived_delist_grace_days DAY) AS is_delisted,
    'derived_from_daily' AS stock_master_source,
    IF(
      d.last_trade_date < DATE_SUB(m.market_last_trade_date, INTERVAL derived_delist_grace_days DAY),
      'last_trade_date_plus_1_after_market_grace',
      NULL
    ) AS delist_date_source,
    CAST(NULL AS STRING) AS source_partition_date,
    CAST(NULL AS TIMESTAMP) AS ingested_at
  FROM daily_codes_2019 AS d
  CROSS JOIN latest_market_trade AS m
  LEFT JOIN stock_basic_enriched AS s
    ON d.ts_code = s.sec_code
  WHERE s.sec_code IS NULL
)
SELECT * FROM stock_basic_enriched
UNION ALL
SELECT * FROM missing_from_stock_basic;

ALTER TABLE `data-aquarium.ashare_dim.dim_stock`
ALTER COLUMN sec_code SET OPTIONS (description = '证券代码，Tushare ts_code 格式，如 600000.SH'),
ALTER COLUMN list_date SET OPTIONS (description = '上市日期'),
ALTER COLUMN delist_date SET OPTIONS (description = '退市后第一天，用于生命周期半开区间 trade_date < delist_date'),
ALTER COLUMN stock_master_source SET OPTIONS (description = '股票主数据来源：stock_basic 或 derived_from_daily'),
ALTER COLUMN delist_date_source SET OPTIONS (description = '退市边界来源：stock_basic_delist_date、last_trade_date_plus_1_fallback、last_trade_date_plus_1_after_market_grace、missing_delist_date（QA 阻断态）或 NULL');
