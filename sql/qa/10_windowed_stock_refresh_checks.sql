-- 文档维护：GPT-5（最近更新 2026-06-05）
-- BigQuery Standard SQL
-- Daily warehouse pipeline: 股票 DWD/DWS 窗口化刷新后的轻量 QA。
--
-- Parameters:
--   @business_date: STRING, YYYY-MM-DD
--   @date_from: STRING, optional YYYY-MM-DD
--   @date_to: STRING, optional YYYY-MM-DD
--   @warehouse_mode: STRING, daily_current / backfill
--
-- 新增估值覆盖检查（QA-WIN-16/17/18）：
-- - 最近 20 个交易日，ODS daily_basic 有数据时 dwd_stock_eod_valuation 必须有对应行。
-- - dwd_stock_eod_valuation 有数据时 dws_stock_feature_valuation_daily 必须有对应行。
-- - dws_stock_feature_daily_v0.has_valuation_data 覆盖不能出现异常空窗。

DECLARE p_business_date DATE DEFAULT COALESCE(SAFE_CAST(NULLIF(@business_date, '') AS DATE), CURRENT_DATE('Asia/Shanghai'));
DECLARE p_date_from DATE DEFAULT SAFE_CAST(NULLIF(@date_from, '') AS DATE);
DECLARE p_requested_date_to DATE DEFAULT COALESCE(SAFE_CAST(NULLIF(@date_to, '') AS DATE), p_business_date);
DECLARE p_warehouse_mode STRING DEFAULT LOWER(COALESCE(NULLIF(@warehouse_mode, ''), 'daily_current'));
DECLARE p_date_to DATE DEFAULT CASE
  WHEN p_warehouse_mode = 'daily_current' THEN COALESCE(
    (
      SELECT MAX(cal_date)
      FROM `data-aquarium.ashare_dim.dim_trade_calendar`
      WHERE exchange = 'SSE'
        AND is_open = 1
        AND cal_date <= p_requested_date_to
    ),
    p_requested_date_to
  )
  ELSE p_requested_date_to
END;
DECLARE p_daily_current_floor_date DATE DEFAULT DATE '2019-01-01';
DECLARE p_backfill_floor_date DATE DEFAULT DATE '1900-01-01';
DECLARE p_write_floor_date DATE DEFAULT CASE
  WHEN p_warehouse_mode = 'backfill' THEN p_backfill_floor_date
  ELSE p_daily_current_floor_date
END;
DECLARE p_feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_fin_feature_version STRING DEFAULT 'fin_default_v0_20260602';
DECLARE p_label_version STRING DEFAULT 'open_to_close_h1_5_10_20_v20260601';
DECLARE p_daily_current_lookback_td INT64 DEFAULT 20;

-- 与 01_refresh_stock_dwd_dws_window.sql 保持一致的窗口计算逻辑
DECLARE p_end_date_seq INT64 DEFAULT (
  SELECT trade_date_seq
  FROM `data-aquarium.ashare_dim.dim_trade_calendar`
  WHERE exchange = 'SSE'
    AND is_open = 1
    AND cal_date = p_date_to
  LIMIT 1
);
DECLARE p_daily_current_start_date DATE DEFAULT COALESCE(
  (
    SELECT MAX(cal_date)
    FROM `data-aquarium.ashare_dim.dim_trade_calendar`
    WHERE exchange = 'SSE'
      AND is_open = 1
      AND trade_date_seq <= p_end_date_seq - p_daily_current_lookback_td + 1
  ),
  p_date_to
);
DECLARE p_dwd_write_start_date DATE DEFAULT GREATEST(
  CASE
    WHEN p_warehouse_mode = 'daily_current' AND p_date_from IS NULL
      THEN p_daily_current_start_date
    ELSE COALESCE(p_date_from, p_date_to)
  END,
  p_write_floor_date
);
DECLARE p_write_end_date DATE DEFAULT p_date_to;
DECLARE p_anchor_seq INT64 DEFAULT (
  SELECT MIN(trade_date_seq)
  FROM `data-aquarium.ashare_dim.dim_trade_calendar`
  WHERE exchange = 'SSE'
    AND is_open = 1
    AND cal_date >= p_dwd_write_start_date
);
DECLARE p_label_write_start_date DATE DEFAULT GREATEST(
  COALESCE(
    (
      SELECT MAX(cal_date)
      FROM `data-aquarium.ashare_dim.dim_trade_calendar`
      WHERE exchange = 'SSE'
        AND is_open = 1
        AND trade_date_seq <= p_anchor_seq - 20
    ),
    DATE_SUB(p_dwd_write_start_date, INTERVAL 35 DAY)
  ),
  p_write_floor_date
);
DECLARE p_valuation_coverage_start_date DATE DEFAULT GREATEST(
  CASE
    WHEN p_warehouse_mode = 'daily_current' AND p_date_from IS NULL
      THEN p_daily_current_start_date
    ELSE p_dwd_write_start_date
  END,
  p_write_floor_date
);

ASSERT p_warehouse_mode IN ('daily_current', 'backfill')
  AS 'QA-WIN-0A: warehouse_mode must be daily_current or backfill for windowed stock refresh QA';

ASSERT p_write_end_date >= p_dwd_write_start_date
  AS 'QA-WIN-0B: write_end_date must be >= dwd_write_start_date';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT sec_code, trade_date, COUNT(*) AS n
    FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price`
    WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date
    GROUP BY sec_code, trade_date
    HAVING n > 1
  )
) AS 'QA-WIN-1: dwd_stock_eod_price key must be unique in DWD window';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT sec_code, trade_date, COUNT(*) AS n
    FROM `data-aquarium.ashare_dwd.dwd_stock_eod_valuation`
    WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date
    GROUP BY sec_code, trade_date
    HAVING n > 1
  )
) AS 'QA-WIN-2: dwd_stock_eod_valuation key must be unique in DWD window';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT sec_code, trade_date, COUNT(*) AS n
    FROM `data-aquarium.ashare_dws.dws_stock_universe_daily`
    WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date
    GROUP BY sec_code, trade_date
    HAVING n > 1
  )
) AS 'QA-WIN-3: dws_stock_universe_daily key must be unique in DWD window';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT sec_code, trade_date, feature_version, COUNT(*) AS n
    FROM `data-aquarium.ashare_dws.dws_stock_feature_price_daily`
    WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date
      AND feature_version = p_feature_version
    GROUP BY sec_code, trade_date, feature_version
    HAVING n > 1
  )
) AS 'QA-WIN-4: dws_stock_feature_price_daily key must be unique in DWD window';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT sec_code, trade_date, feature_version, COUNT(*) AS n
    FROM `data-aquarium.ashare_dws.dws_stock_feature_valuation_daily`
    WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date
      AND feature_version = p_feature_version
    GROUP BY sec_code, trade_date, feature_version
    HAVING n > 1
  )
) AS 'QA-WIN-5: dws_stock_feature_valuation_daily key must be unique in DWD window';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT sec_code, trade_date, feature_version, COUNT(*) AS n
    FROM `data-aquarium.ashare_dws.dws_stock_feature_fin_daily`
    WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date
      AND feature_version = p_fin_feature_version
    GROUP BY sec_code, trade_date, feature_version
    HAVING n > 1
  )
) AS 'QA-WIN-6: dws_stock_feature_fin_daily key must be unique in DWD window';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT sec_code, trade_date, label_version, COUNT(*) AS n
    FROM `data-aquarium.ashare_dws.dws_stock_label_daily`
    WHERE trade_date BETWEEN p_label_write_start_date AND p_write_end_date
      AND label_version = p_label_version
    GROUP BY sec_code, trade_date, label_version
    HAVING n > 1
  )
) AS 'QA-WIN-7: dws_stock_label_daily key must be unique in label window';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT sec_code, trade_date, feature_version, COUNT(*) AS n
    FROM `data-aquarium.ashare_dws.dws_stock_feature_daily_v0`
    WHERE trade_date BETWEEN p_label_write_start_date AND p_write_end_date
      AND feature_version = p_feature_version
    GROUP BY sec_code, trade_date, feature_version
    HAVING n > 1
  )
) AS 'QA-WIN-8: dws_stock_feature_daily_v0 key must be unique in label window';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT sec_code, trade_date, feature_version, label_version, COUNT(*) AS n
    FROM `data-aquarium.ashare_dws.dws_stock_sample_daily`
    WHERE trade_date BETWEEN p_label_write_start_date AND p_write_end_date
      AND feature_version = p_feature_version
      AND label_version = p_label_version
    GROUP BY sec_code, trade_date, feature_version, label_version
    HAVING n > 1
  )
) AS 'QA-WIN-9: dws_stock_sample_daily key must be unique in label window';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS p
  JOIN `data-aquarium.ashare_dim.dim_stock` AS s
    ON p.sec_code = s.sec_code
  WHERE p.trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date
    AND (
      p.trade_date < COALESCE(s.list_date, DATE '1900-01-01')
      OR (s.delist_date IS NOT NULL AND p.trade_date >= s.delist_date)
    )
) AS 'QA-WIN-10: dwd_stock_eod_price must respect dim_stock lifecycle in DWD window';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_dws.dws_stock_universe_daily` AS u
  JOIN `data-aquarium.ashare_dim.dim_stock` AS s
    ON u.sec_code = s.sec_code
  WHERE u.trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date
    AND (
      u.trade_date < COALESCE(s.list_date, DATE '1900-01-01')
      OR (s.delist_date IS NOT NULL AND u.trade_date >= s.delist_date)
    )
) AS 'QA-WIN-11: dws_stock_universe_daily must respect dim_stock lifecycle in DWD window';

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
      AND d.ods_delist_date <= p_write_end_date
      AND (s.sec_code IS NULL OR s.delist_date IS NULL OR s.delist_date != d.ods_delist_date)
  )
) AS 'QA-WIN-12: dim_stock.delist_date must match latest ODS delisted snapshot for closed lifecycles';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    WITH ods_daily AS (
      SELECT
        ts_code AS sec_code,
        SAFE.PARSE_DATE('%Y%m%d', trade_date) AS trade_date,
        SAFE_CAST(close AS FLOAT64) AS close
      FROM `data-aquarium.ashare_ods.ods_tushare_daily`
      WHERE endpoint = 'daily'
        AND partition_date BETWEEN FORMAT_DATE('%Y%m%d', p_dwd_write_start_date) AND FORMAT_DATE('%Y%m%d', p_write_end_date)
        AND SAFE.PARSE_DATE('%Y%m%d', trade_date) BETWEEN p_dwd_write_start_date AND p_write_end_date
    )
    SELECT 1
    FROM ods_daily AS d
    LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS p
      ON d.sec_code = p.sec_code
     AND d.trade_date = p.trade_date
     AND p.trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date
    WHERE p.sec_code IS NULL
      OR p.close IS NULL
      OR ABS(p.close - d.close) > 1e-8
  )
) AS 'QA-WIN-13: ODS daily rows in DWD window must be represented in dwd_stock_eod_price';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price`
  WHERE trade_date BETWEEN p_dwd_write_start_date AND p_write_end_date
    AND is_suspended
    AND close IS NOT NULL
    AND IFNULL(volume_lot, 0) > 0
) AS 'QA-WIN-14: traded intraday halt rows must not be marked is_suspended in DWD window';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_dws.dws_stock_sample_daily`
  WHERE trade_date BETWEEN p_label_write_start_date AND p_write_end_date
    AND feature_version = p_feature_version
    AND label_version = p_label_version
    AND sample_trainable_default
    AND rank_pct_5d IS NULL
) AS 'QA-WIN-15: default trainable samples in label window must have rank_pct_5d';

-- ────────────────────────────────────────────────────────────────────────────
-- 估值覆盖检查：daily_current 默认最近 20 个交易日；backfill 使用实际写入窗口。
-- ────────────────────────────────────────────────────────────────────────────

-- QA-WIN-16: 覆盖窗口内，ODS daily_basic 有数据时 dwd_stock_eod_valuation 必须有对应行
ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT
      o.sec_code,
      o.trade_date
    FROM (
      SELECT
        ts_code AS sec_code,
        SAFE.PARSE_DATE('%Y%m%d', trade_date) AS trade_date
      FROM `data-aquarium.ashare_ods.ods_tushare_daily_basic`
      WHERE endpoint = 'daily_basic'
        AND partition_date BETWEEN FORMAT_DATE('%Y%m%d', p_valuation_coverage_start_date) AND FORMAT_DATE('%Y%m%d', p_write_end_date)
        AND SAFE.PARSE_DATE('%Y%m%d', trade_date) BETWEEN p_valuation_coverage_start_date AND p_write_end_date
      GROUP BY ts_code, trade_date
    ) AS o
    LEFT JOIN (
      SELECT sec_code, trade_date
      FROM `data-aquarium.ashare_dwd.dwd_stock_eod_valuation`
      WHERE trade_date BETWEEN p_valuation_coverage_start_date AND p_write_end_date
    ) AS v
      ON o.sec_code = v.sec_code AND o.trade_date = v.trade_date
    WHERE v.sec_code IS NULL
  )
) AS 'QA-WIN-16: ODS daily_basic rows in valuation coverage window must have dwd_stock_eod_valuation match';

-- QA-WIN-17: dwd_stock_eod_valuation 有数据时 dws_stock_feature_valuation_daily 必须有对应行
ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT
      v.sec_code,
      v.trade_date
    FROM (
      SELECT sec_code, trade_date
      FROM `data-aquarium.ashare_dwd.dwd_stock_eod_valuation`
      WHERE trade_date BETWEEN p_valuation_coverage_start_date AND p_write_end_date
    ) AS v
    LEFT JOIN (
      SELECT sec_code, trade_date
      FROM `data-aquarium.ashare_dws.dws_stock_feature_valuation_daily`
      WHERE trade_date BETWEEN p_valuation_coverage_start_date AND p_write_end_date
        AND feature_version = p_feature_version
    ) AS f
      ON v.sec_code = f.sec_code AND v.trade_date = f.trade_date
    WHERE f.sec_code IS NULL
  )
) AS 'QA-WIN-17: dwd_stock_eod_valuation rows in valuation coverage window must have dws valuation feature match';

-- QA-WIN-18: dws_stock_feature_daily_v0.has_valuation_data 覆盖不能出现异常空窗
-- 检查：price-driven feature universe 中有 total_mv_cny/circ_mv_cny 的估值行，
-- 在 feature_daily_v0 中 has_valuation_data 必须为 TRUE。
ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT
      p.sec_code,
      p.trade_date
    FROM `data-aquarium.ashare_dws.dws_stock_feature_price_daily` AS p
    JOIN `data-aquarium.ashare_dws.dws_stock_universe_daily` AS u
      ON p.trade_date = u.trade_date
     AND p.sec_code = u.sec_code
    JOIN `data-aquarium.ashare_dws.dws_stock_feature_valuation_daily` AS v
      ON p.trade_date = v.trade_date
     AND p.sec_code = v.sec_code
     AND p.feature_version = v.feature_version
    WHERE p.trade_date BETWEEN p_valuation_coverage_start_date AND p_write_end_date
      AND p.feature_version = p_feature_version
      AND v.trade_date BETWEEN p_valuation_coverage_start_date AND p_write_end_date
      AND v.feature_version = p_feature_version
      AND v.total_mv_cny IS NOT NULL
      AND v.circ_mv_cny IS NOT NULL
  ) AS expected
    LEFT JOIN (
      SELECT sec_code, trade_date, has_valuation_data
      FROM `data-aquarium.ashare_dws.dws_stock_feature_daily_v0`
      WHERE trade_date BETWEEN p_valuation_coverage_start_date AND p_write_end_date
        AND feature_version = p_feature_version
    ) AS f
      ON expected.sec_code = f.sec_code AND expected.trade_date = f.trade_date
    WHERE f.sec_code IS NULL
      OR f.has_valuation_data IS NULL
      OR f.has_valuation_data = FALSE
) AS 'QA-WIN-18: has_valuation_data must be TRUE where price-driven feature universe has valuation market-cap data in coverage window';

SELECT
  p_business_date AS business_date,
  p_requested_date_to AS requested_date_to,
  p_date_to AS effective_date_to,
  p_warehouse_mode AS warehouse_mode,
  p_dwd_write_start_date AS dwd_write_start_date,
  p_label_write_start_date AS label_write_start_date,
  p_valuation_coverage_start_date AS valuation_coverage_start_date,
  p_write_end_date AS write_end_date;
