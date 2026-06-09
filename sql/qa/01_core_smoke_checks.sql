-- 文档维护：GPT-5 Codex（最近更新 2026-06-07）
-- BigQuery Standard SQL
-- P0 DIM/DWD 物化后的基础断言。全部通过才进入 DWS 特征构建。
-- daily_current / full rebuild 的 2019+ 生产写入下限由窗口 SQL 与窗口 QA
-- 约束；本脚本只校验已存在 DWD 行不早于 A 股日线支持历史下限。

DECLARE dwd_start_date DATE DEFAULT DATE '2019-01-01';
DECLARE dwd_end_date DATE DEFAULT CURRENT_DATE('Asia/Shanghai');
DECLARE dwd_supported_history_floor_date DATE DEFAULT DATE '1990-12-19';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT sec_code, COUNT(*) AS n
    FROM `data-aquarium.ashare_dim.dim_stock`
    GROUP BY sec_code
    HAVING n > 1
  )
) AS 'dim_stock.sec_code must be unique';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_dim.dim_stock`
  WHERE is_delisted
    AND (
      delist_date IS NULL
      OR delist_date_source = 'missing_delist_date'
      OR (list_date IS NOT NULL AND delist_date <= list_date)
    )
) AS 'delisted dim_stock rows must have valid delist_date after list_date';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    WITH latest AS (
      SELECT MAX(partition_date) AS partition_date
      FROM `data-aquarium.ashare_ods.ods_tushare_stock_basic`
      WHERE endpoint = 'stock_basic_delisted'
        AND partition_date BETWEEN '00000000' AND '99999999'
    )
    SELECT 1
    FROM `data-aquarium.ashare_ods.ods_tushare_stock_basic` AS s
    JOIN latest AS l
      ON s.partition_date = l.partition_date
    WHERE s.endpoint = 'stock_basic_delisted'
      AND s.partition_date BETWEEN '00000000' AND '99999999'
      AND NULLIF(s.delist_date, '') IS NOT NULL
      AND SAFE.PARSE_DATE('%Y%m%d', NULLIF(s.delist_date, '')) IS NULL
  )
) AS 'stock_basic_delisted.delist_date must be readable and parseable';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    WITH latest AS (
      SELECT MAX(partition_date) AS partition_date
      FROM `data-aquarium.ashare_ods.ods_tushare_stock_basic`
      WHERE endpoint = 'stock_basic_delisted'
        AND partition_date BETWEEN '00000000' AND '99999999'
    ),
    delisted AS (
      SELECT
        s.ts_code AS sec_code,
        SAFE.PARSE_DATE('%Y%m%d', NULLIF(s.delist_date, '')) AS ods_delist_date
      FROM `data-aquarium.ashare_ods.ods_tushare_stock_basic` AS s
      JOIN latest AS l
        ON s.partition_date = l.partition_date
      WHERE s.endpoint = 'stock_basic_delisted'
        AND s.partition_date BETWEEN '00000000' AND '99999999'
    )
    SELECT 1
    FROM delisted AS d
    LEFT JOIN `data-aquarium.ashare_dim.dim_stock` AS s
      ON d.sec_code = s.sec_code
    WHERE d.ods_delist_date IS NOT NULL
      AND (s.sec_code IS NULL OR s.delist_date IS NULL OR s.delist_date != d.ods_delist_date)
  )
) AS 'dim_stock.delist_date must use stock_basic_delisted.delist_date when ODS provides it';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT sec_code, trade_date, COUNT(*) AS n
    FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price`
    WHERE trade_date BETWEEN dwd_start_date AND dwd_end_date
    GROUP BY sec_code, trade_date
    HAVING n > 1
  )
) AS 'dwd_stock_eod_price key (sec_code, trade_date) must be unique';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price`
  WHERE trade_date < dwd_supported_history_floor_date
) AS 'dwd_stock_eod_price must not write rows before supported A-share daily history floor';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price`
  WHERE trade_date BETWEEN dwd_start_date AND dwd_end_date
    AND is_suspended
    AND close IS NOT NULL
    AND IFNULL(volume_lot, 0) > 0
) AS 'traded intraday halt rows must not be marked is_suspended';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS p
  JOIN `data-aquarium.ashare_ods.ods_tushare_suspend_d` AS s
    ON p.sec_code = s.ts_code
   AND FORMAT_DATE('%Y%m%d', p.trade_date) = s.trade_date
  WHERE p.trade_date BETWEEN dwd_start_date AND dwd_end_date
    AND s.endpoint = 'suspend_d'
    AND s.partition_date BETWEEN FORMAT_DATE('%Y%m%d', dwd_start_date) AND FORMAT_DATE('%Y%m%d', dwd_end_date)
    AND s.suspend_type = 'R'
    AND NOT EXISTS (
      SELECT 1
      FROM `data-aquarium.ashare_ods.ods_tushare_suspend_d` AS stop
      WHERE stop.endpoint = 'suspend_d'
        AND stop.partition_date BETWEEN FORMAT_DATE('%Y%m%d', dwd_start_date) AND FORMAT_DATE('%Y%m%d', dwd_end_date)
        AND stop.suspend_type = 'S'
        AND stop.ts_code = s.ts_code
        AND stop.trade_date = s.trade_date
    )
    AND p.close IS NOT NULL
    AND IFNULL(p.volume_lot, 0) > 0
    AND p.is_suspended
) AS 'R-only resumption rows with trading volume must not be marked suspended';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT sec_code, report_period, COUNT(*) AS n
    FROM `data-aquarium.ashare_dwd.dwd_fin_indicator_latest`
    GROUP BY sec_code, report_period
    HAVING n > 1
  )
) AS 'dwd_fin_indicator_latest key (sec_code, report_period) must be unique';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    WITH spec_order AS (
      SELECT
        sec_code,
        report_period,
        ann_date_eff,
        update_flag,
        ingested_at,
        source_partition_date,
        ROW_NUMBER() OVER (
          PARTITION BY sec_code, report_period
          ORDER BY update_flag DESC, ann_date_eff DESC, ingested_at DESC, source_partition_date DESC
        ) AS rn
      FROM `data-aquarium.ashare_dwd.dwd_fin_indicator`
    )
    SELECT 1
    FROM `data-aquarium.ashare_dwd.dwd_fin_indicator_latest` AS latest
    JOIN spec_order AS spec
      ON latest.sec_code = spec.sec_code
     AND latest.report_period = spec.report_period
    WHERE spec.rn = 1
      AND STRUCT(
        latest.ann_date_eff,
        latest.update_flag,
        latest.ingested_at,
        latest.source_partition_date
      ) != STRUCT(
        spec.ann_date_eff,
        spec.update_flag,
        spec.ingested_at,
        spec.source_partition_date
      )
  )
) AS 'dwd_fin_indicator_latest must follow spec ordering';

ASSERT (
  SELECT COUNTIF(
    sec_code IN ('000001.SH', '000016.SH', '000905.SH', '399001.SZ', '399006.SZ', '000300.SH')
    AND pe IS NOT NULL
    AND total_mv_cny IS NOT NULL
  ) > 0
  FROM `data-aquarium.ashare_dwd.dwd_index_eod`
  WHERE trade_date BETWEEN dwd_start_date AND dwd_end_date
) AS 'dwd_index_eod must include index_dailybasic valuation fields where available';

ASSERT (
  SELECT COUNT(*) > 0
  FROM `data-aquarium.ashare_dwd.dwd_index_eod`
  WHERE trade_date BETWEEN dwd_start_date AND dwd_end_date
    AND sec_code = '000300.SH'
    AND source_sec_code = '399300.SZ'
) AS 'dwd_index_eod must expose canonical sec_code and preserve source_sec_code for CSI300';
