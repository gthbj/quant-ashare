-- 文档维护：GPT-5（最近更新 2026-06-01）
-- BigQuery Standard SQL
-- 策略 1 价格量价特征。全部基于 t 日及以前的后复权价格和成交字段。

DECLARE dws_start_date DATE DEFAULT DATE '2019-01-01';
DECLARE dws_end_date DATE DEFAULT CURRENT_DATE('Asia/Shanghai');
DECLARE feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';

CREATE OR REPLACE TABLE `data-aquarium.ashare_dws.dws_stock_feature_price_daily`
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY sec_code, feature_version
OPTIONS (
  description = 'Daily raw price/volume features for strategy1_pv_v0; writes 2019+ rows and marks incomplete 60d history explicitly',
  require_partition_filter = TRUE
) AS
WITH base AS (
  SELECT
    trade_date,
    sec_code,
    open_hfq,
    high_hfq,
    low_hfq,
    close_hfq,
    ret_1d,
    volume_share,
    amount_cny,
    is_suspended,
    is_limit_up,
    is_limit_down,
    is_one_word_limit_up,
    is_one_word_limit_down,
    is_tradable
  FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price`
  WHERE trade_date BETWEEN dws_start_date AND dws_end_date
),
windowed AS (
  SELECT
    *,
    LAG(close_hfq, 1) OVER w AS close_hfq_lag_1d,
    LAG(close_hfq, 3) OVER w AS close_hfq_lag_3d,
    LAG(close_hfq, 5) OVER w AS close_hfq_lag_5d,
    LAG(close_hfq, 10) OVER w AS close_hfq_lag_10d,
    LAG(close_hfq, 20) OVER w AS close_hfq_lag_20d,
    LAG(close_hfq, 60) OVER w AS close_hfq_lag_60d,
    AVG(amount_cny) OVER w5 AS amount_ma5_cny,
    AVG(amount_cny) OVER w20 AS amount_ma20_cny,
    STDDEV_SAMP(amount_cny) OVER w20 AS amount_std20_cny,
    STDDEV_SAMP(ret_1d) OVER w5 AS vol_5d,
    STDDEV_SAMP(ret_1d) OVER w20 AS vol_20d,
    STDDEV_SAMP(ret_1d) OVER w60 AS vol_60d,
    MAX(close_hfq) OVER w20 AS close_hfq_max_20d,
    MIN(close_hfq) OVER w20 AS close_hfq_min_20d,
    AVG(SAFE_DIVIDE(high_hfq - low_hfq, close_hfq)) OVER w20 AS hl_range_20d,
    COUNT(close_hfq) OVER w60_plus AS history_obs_60d,
    SUM(CAST(COALESCE(is_suspended, FALSE) AS INT64)) OVER w20 AS suspend_days_20d,
    SUM(CAST(COALESCE(is_limit_up, FALSE) AS INT64)) OVER w20 AS limit_up_days_20d,
    SUM(CAST(COALESCE(is_limit_down, FALSE) AS INT64)) OVER w20 AS limit_down_days_20d,
    SUM(CAST(COALESCE(is_one_word_limit_up, FALSE) OR COALESCE(is_one_word_limit_down, FALSE) AS INT64)) OVER w20 AS one_word_limit_days_20d,
    SUM(CAST(COALESCE(is_tradable, FALSE) AS INT64)) OVER w20 AS tradable_days_20d
  FROM base
  WINDOW
    w AS (PARTITION BY sec_code ORDER BY trade_date),
    w5 AS (PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW),
    w20 AS (PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),
    w60 AS (PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW),
    w60_plus AS (PARTITION BY sec_code ORDER BY trade_date ROWS BETWEEN 60 PRECEDING AND CURRENT ROW)
)
SELECT
  trade_date,
  sec_code,
  feature_version,
  ret_1d,
  SAFE_DIVIDE(close_hfq, close_hfq_lag_3d) - 1.0 AS ret_3d,
  SAFE_DIVIDE(close_hfq, close_hfq_lag_5d) - 1.0 AS ret_5d,
  SAFE_DIVIDE(close_hfq, close_hfq_lag_10d) - 1.0 AS ret_10d,
  SAFE_DIVIDE(close_hfq, close_hfq_lag_20d) - 1.0 AS ret_20d,
  SAFE_DIVIDE(close_hfq, close_hfq_lag_60d) - 1.0 AS ret_60d,
  SAFE_DIVIDE(close_hfq_lag_5d, close_hfq_lag_20d) - 1.0 AS mom_20_5,
  SAFE_DIVIDE(close_hfq_lag_20d, close_hfq_lag_60d) - 1.0 AS mom_60_20,
  vol_5d,
  vol_20d,
  vol_60d,
  SAFE_DIVIDE(close_hfq, close_hfq_max_20d) - 1.0 AS drawdown_20d,
  SAFE_DIVIDE(close_hfq, close_hfq_min_20d) - 1.0 AS close_to_low_20d,
  SAFE_DIVIDE(high_hfq - low_hfq, close_hfq) AS amplitude_1d,
  SAFE_DIVIDE(open_hfq, close_hfq_lag_1d) - 1.0 AS gap_open_1d,
  SAFE_DIVIDE(close_hfq, open_hfq) - 1.0 AS intraday_ret_1d,
  hl_range_20d,
  amount_cny,
  amount_ma5_cny,
  amount_ma20_cny,
  SAFE_DIVIDE(amount_cny - amount_ma20_cny, NULLIF(amount_std20_cny, 0.0)) AS amount_zscore_20d,
  volume_share,
  suspend_days_20d,
  limit_up_days_20d,
  limit_down_days_20d,
  one_word_limit_days_20d,
  tradable_days_20d,
  history_obs_60d,
  history_obs_60d >= 61 AND close_hfq_lag_60d IS NOT NULL AS has_full_history_60d,
  CURRENT_TIMESTAMP() AS created_at
FROM windowed;

ALTER TABLE `data-aquarium.ashare_dws.dws_stock_feature_price_daily`
ALTER COLUMN trade_date SET OPTIONS (description = '特征日，月分区字段'),
ALTER COLUMN sec_code SET OPTIONS (description = '统一证券代码，Tushare ts_code 格式'),
ALTER COLUMN feature_version SET OPTIONS (description = '特征版本'),
ALTER COLUMN ret_60d SET OPTIONS (description = '基于后复权收盘价的 60 交易日累计收益；历史不足时为空'),
ALTER COLUMN has_full_history_60d SET OPTIONS (description = '是否具备计算 60 日窗口所需的完整 61 个价格观测'),
ALTER COLUMN amount_zscore_20d SET OPTIONS (description = '当日成交额相对过去 20 个交易日成交额的 z-score');
