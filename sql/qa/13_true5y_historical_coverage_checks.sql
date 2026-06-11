-- 文档维护：GPT-5 Codex（最近更新 2026-06-11）
-- BigQuery Standard SQL
-- PRD_20260611_06 historical coverage gate for true-five-year refit.
--
-- This QA is intended for the explicit historical backfill/repair flow. It is
-- research-only and does not mutate warehouse or ADS tables.

DECLARE p_feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_label_version STRING DEFAULT 'open_to_close_h1_5_10_20_v20260601';
DECLARE p_fin_feature_version STRING DEFAULT 'fin_default_v0_20260602';
DECLARE p_true5y_start DATE DEFAULT DATE '2016-01-04';
DECLARE p_true5y_end DATE DEFAULT DATE '2024-12-24';
DECLARE p_repaired_2019_start DATE DEFAULT DATE '2019-01-02';
DECLARE p_repaired_2019_end DATE DEFAULT DATE '2019-04-02';
DECLARE p_min_history_start DATE DEFAULT DATE '2010-01-01';
DECLARE p_min_valuation_non_null_ratio FLOAT64 DEFAULT 0.50;

ASSERT p_repaired_2019_start = DATE '2019-01-02'
  AND p_repaired_2019_end = DATE '2019-04-02'
  AS 'QA-TRUE5Y-0: 2019 repair window must include 2019-04-01/02, not only natural Q1';

CREATE TEMP TABLE true5y_open_days AS
SELECT cal_date AS trade_date
FROM `data-aquarium.ashare_dim.dim_trade_calendar`
WHERE exchange = 'SSE'
  AND is_open = 1
  AND cal_date BETWEEN p_true5y_start AND p_true5y_end;

CREATE TEMP TABLE repaired_2019_full_history_candidates AS
SELECT
  f.trade_date,
  f.sec_code,
  f.has_full_history_60d,
  COUNT(prior.sec_code) AS price_obs_through_trade_date
FROM `data-aquarium.ashare_dws.dws_stock_feature_price_daily` AS f
JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS prior
  ON prior.sec_code = f.sec_code
 AND prior.trade_date BETWEEN DATE_SUB(f.trade_date, INTERVAL 180 DAY) AND f.trade_date
WHERE f.trade_date BETWEEN p_repaired_2019_start AND p_repaired_2019_end
  AND prior.trade_date BETWEEN DATE_SUB(p_repaired_2019_start, INTERVAL 180 DAY) AND p_repaired_2019_end
  AND f.feature_version = p_feature_version
GROUP BY f.trade_date, f.sec_code, f.has_full_history_60d
HAVING price_obs_through_trade_date >= 61;

ASSERT (
  SELECT COUNTIF(NOT COALESCE(has_full_history_60d, FALSE)) = 0
  FROM repaired_2019_full_history_candidates
) AS 'QA-TRUE5Y-1: eligible 2019-01-02..2019-04-02 rows must have recomputed has_full_history_60d=TRUE';

CREATE TEMP TABLE feature_day_coverage AS
SELECT
  d.trade_date,
  COUNT(f.sec_code) AS feature_row_count
FROM true5y_open_days AS d
LEFT JOIN `data-aquarium.ashare_dws.dws_stock_feature_daily_v0` AS f
  ON f.trade_date = d.trade_date
 AND f.trade_date BETWEEN p_true5y_start AND p_true5y_end
 AND f.feature_version = p_feature_version
GROUP BY d.trade_date;

ASSERT (
  SELECT COUNTIF(feature_row_count = 0) = 0
  FROM feature_day_coverage
) AS 'QA-TRUE5Y-2: every true-five-year open day must have feature rows';

CREATE TEMP TABLE sample_day_coverage AS
SELECT
  d.trade_date,
  COUNTIF(COALESCE(s.sample_trainable_default, FALSE)) AS trainable_sample_count
FROM true5y_open_days AS d
LEFT JOIN `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
  ON s.trade_date = d.trade_date
 AND s.trade_date BETWEEN p_true5y_start AND p_true5y_end
 AND s.feature_version = p_feature_version
 AND s.label_version = p_label_version
GROUP BY d.trade_date;

ASSERT (
  SELECT COUNTIF(trainable_sample_count = 0) = 0
  FROM sample_day_coverage
) AS 'QA-TRUE5Y-3: every true-five-year open day must have trainable labeled samples';

CREATE TEMP TABLE valuation_completeness_by_year AS
SELECT
  EXTRACT(YEAR FROM f.trade_date) AS year,
  COUNTIF(COALESCE(f.in_universe_default, FALSE)) AS universe_row_count,
  COUNTIF(COALESCE(f.in_universe_default, FALSE) AND f.total_mv_cny IS NOT NULL AND f.circ_mv_cny IS NOT NULL) AS valuation_non_null_count,
  SAFE_DIVIDE(
    COUNTIF(COALESCE(f.in_universe_default, FALSE) AND f.total_mv_cny IS NOT NULL AND f.circ_mv_cny IS NOT NULL),
    NULLIF(COUNTIF(COALESCE(f.in_universe_default, FALSE)), 0)
  ) AS valuation_non_null_ratio
FROM `data-aquarium.ashare_dws.dws_stock_feature_daily_v0` AS f
WHERE f.trade_date BETWEEN p_true5y_start AND p_true5y_end
  AND f.feature_version = p_feature_version
GROUP BY year;

ASSERT (
  SELECT COUNTIF(valuation_non_null_ratio < p_min_valuation_non_null_ratio OR valuation_non_null_ratio IS NULL) = 0
  FROM valuation_completeness_by_year
) AS 'QA-TRUE5Y-4: valuation completeness must clear the configured floor for true-five-year windows';

CREATE TEMP TABLE fin_completeness_by_year AS
SELECT
  EXTRACT(YEAR FROM u.trade_date) AS year,
  COUNT(*) AS universe_row_count,
  COUNTIF(fin.has_fin_indicator) AS has_fin_indicator_count,
  COUNTIF(fin.has_fin_income) AS has_fin_income_count,
  COUNTIF(fin.has_fin_balancesheet) AS has_fin_balancesheet_count,
  COUNTIF(fin.has_fin_cashflow) AS has_fin_cashflow_count,
  SAFE_DIVIDE(COUNTIF(fin.has_fin_indicator), COUNT(*)) AS has_fin_indicator_ratio,
  SAFE_DIVIDE(COUNTIF(fin.has_fin_income), COUNT(*)) AS has_fin_income_ratio,
  SAFE_DIVIDE(COUNTIF(fin.has_fin_balancesheet), COUNT(*)) AS has_fin_balancesheet_ratio,
  SAFE_DIVIDE(COUNTIF(fin.has_fin_cashflow), COUNT(*)) AS has_fin_cashflow_ratio
FROM `data-aquarium.ashare_dws.dws_stock_universe_daily` AS u
LEFT JOIN `data-aquarium.ashare_dws.dws_stock_feature_fin_daily` AS fin
  ON fin.trade_date = u.trade_date
 AND fin.sec_code = u.sec_code
 AND fin.trade_date BETWEEN p_true5y_start AND p_true5y_end
 AND fin.feature_version = p_fin_feature_version
WHERE u.trade_date BETWEEN p_true5y_start AND p_true5y_end
  AND COALESCE(u.in_universe_default, FALSE)
GROUP BY year;

ASSERT (
  SELECT COUNT(*) > 0
  FROM valuation_completeness_by_year
) AS 'QA-TRUE5Y-5: valuation completeness report must be non-empty';

SELECT
  'price_flag_repair_window' AS check_name,
  p_repaired_2019_start AS scope_start,
  p_repaired_2019_end AS scope_end,
  COUNT(*) AS row_count,
  COUNTIF(NOT COALESCE(has_full_history_60d, FALSE)) AS bad_count,
  SAFE_DIVIDE(COUNTIF(COALESCE(has_full_history_60d, FALSE)), COUNT(*)) AS metric_value,
  'eligible rows with at least 61 price observations must be full-history TRUE' AS details
FROM repaired_2019_full_history_candidates
UNION ALL
SELECT
  'feature_daily_open_day_coverage' AS check_name,
  p_true5y_start AS scope_start,
  p_true5y_end AS scope_end,
  COUNT(*) AS row_count,
  COUNTIF(feature_row_count = 0) AS bad_count,
  SAFE_DIVIDE(COUNTIF(feature_row_count > 0), COUNT(*)) AS metric_value,
  'open-day feature coverage for true-five-year refit windows' AS details
FROM feature_day_coverage
UNION ALL
SELECT
  'sample_trainable_open_day_coverage' AS check_name,
  p_true5y_start AS scope_start,
  p_true5y_end AS scope_end,
  COUNT(*) AS row_count,
  COUNTIF(trainable_sample_count = 0) AS bad_count,
  SAFE_DIVIDE(COUNTIF(trainable_sample_count > 0), COUNT(*)) AS metric_value,
  'open-day trainable labeled sample coverage for true-five-year refit windows' AS details
FROM sample_day_coverage
UNION ALL
SELECT
  CONCAT('valuation_completeness_', CAST(year AS STRING)) AS check_name,
  DATE(year, 1, 1) AS scope_start,
  DATE(year, 12, 31) AS scope_end,
  universe_row_count AS row_count,
  universe_row_count - valuation_non_null_count AS bad_count,
  valuation_non_null_ratio AS metric_value,
  'universe rows with total_mv_cny and circ_mv_cny present' AS details
FROM valuation_completeness_by_year
UNION ALL
SELECT
  CONCAT('financial_completeness_', CAST(year AS STRING)) AS check_name,
  DATE(year, 1, 1) AS scope_start,
  DATE(year, 12, 31) AS scope_end,
  universe_row_count AS row_count,
  universe_row_count - has_fin_indicator_count AS bad_count,
  has_fin_indicator_ratio AS metric_value,
  CONCAT(
    'indicator=', CAST(has_fin_indicator_ratio AS STRING),
    ';income=', CAST(has_fin_income_ratio AS STRING),
    ';balancesheet=', CAST(has_fin_balancesheet_ratio AS STRING),
    ';cashflow=', CAST(has_fin_cashflow_ratio AS STRING)
  ) AS details
FROM fin_completeness_by_year
ORDER BY check_name;
