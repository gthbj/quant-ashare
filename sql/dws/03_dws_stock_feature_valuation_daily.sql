-- 文档维护：GPT-5（最近更新 2026-06-01）
-- BigQuery Standard SQL
-- 策略 1 估值、市值、换手特征。保留原值和缺失/非法标记，横截面标准化放到 ADS run。

DECLARE dws_start_date DATE DEFAULT DATE '2019-01-01';
DECLARE dws_end_date DATE DEFAULT CURRENT_DATE('Asia/Shanghai');
DECLARE feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';

CREATE OR REPLACE TABLE `data-aquarium.ashare_dws.dws_stock_feature_valuation_daily`
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY sec_code, feature_version
OPTIONS (
  description = 'Daily raw valuation, market-cap and turnover features for strategy1_pv_v0; writes 2019+ rows',
  require_partition_filter = TRUE
) AS
WITH base AS (
  SELECT
    trade_date,
    sec_code,
    turnover_rate,
    turnover_rate_free_float,
    volume_ratio,
    pe,
    pe_ttm,
    pb,
    ps,
    ps_ttm,
    dividend_yield,
    dividend_yield_ttm,
    total_share,
    float_share,
    free_share,
    total_mv_cny,
    circ_mv_cny
  FROM `data-aquarium.ashare_dwd.dwd_stock_eod_valuation`
  WHERE trade_date BETWEEN dws_start_date AND dws_end_date
),
windowed AS (
  SELECT
    *,
    AVG(turnover_rate) OVER w5 AS turnover_rate_ma5,
    AVG(turnover_rate) OVER w20 AS turnover_rate_ma20,
    AVG(turnover_rate_free_float) OVER w20 AS turnover_rate_free_float_ma20,
    AVG(volume_ratio) OVER w20 AS volume_ratio_ma20,
    STDDEV_SAMP(turnover_rate) OVER w60 AS turnover_rate_std60,
    AVG(turnover_rate) OVER w60 AS turnover_rate_ma60
  FROM base
  WINDOW
    w5 AS (PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW),
    w20 AS (PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),
    w60 AS (PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW)
)
SELECT
  trade_date,
  sec_code,
  feature_version,
  turnover_rate,
  turnover_rate_free_float,
  turnover_rate_ma5,
  turnover_rate_ma20,
  turnover_rate_free_float_ma20,
  volume_ratio,
  volume_ratio_ma20,
  SAFE_DIVIDE(turnover_rate - turnover_rate_ma60, NULLIF(turnover_rate_std60, 0.0)) AS turnover_rate_zscore_60d,
  pe,
  pe_ttm,
  pb,
  ps,
  ps_ttm,
  dividend_yield,
  dividend_yield_ttm,
  pe_ttm > 0 AS is_pe_ttm_positive,
  pb > 0 AS is_pb_positive,
  ps_ttm > 0 AS is_ps_ttm_positive,
  IF(pe_ttm > 0, SAFE_DIVIDE(1.0, pe_ttm), NULL) AS ep_ttm,
  IF(pb > 0, SAFE_DIVIDE(1.0, pb), NULL) AS bp,
  IF(ps_ttm > 0, SAFE_DIVIDE(1.0, ps_ttm), NULL) AS sp_ttm,
  total_share,
  float_share,
  free_share,
  total_mv_cny,
  circ_mv_cny,
  IF(total_mv_cny > 0, LN(total_mv_cny), NULL) AS log_total_mv,
  IF(circ_mv_cny > 0, LN(circ_mv_cny), NULL) AS log_circ_mv,
  total_mv_cny IS NOT NULL AND circ_mv_cny IS NOT NULL AS has_valuation_data,
  CURRENT_TIMESTAMP() AS created_at
FROM windowed;

ALTER TABLE `data-aquarium.ashare_dws.dws_stock_feature_valuation_daily`
ALTER COLUMN trade_date SET OPTIONS (description = '特征日，月分区字段'),
ALTER COLUMN sec_code SET OPTIONS (description = '统一证券代码，Tushare ts_code 格式'),
ALTER COLUMN feature_version SET OPTIONS (description = '特征版本'),
ALTER COLUMN ep_ttm SET OPTIONS (description = 'PE TTM 的倒数；PE TTM 非正时为空'),
ALTER COLUMN log_total_mv SET OPTIONS (description = '总市值自然对数，市值单位为元'),
ALTER COLUMN has_valuation_data SET OPTIONS (description = '是否具备日频估值/市值数据');
