-- 文档维护：GPT-5（最近更新 2026-06-01）
-- BigQuery Standard SQL
-- 策略 1 P0 原始特征宽表：只做域表拼接，不做 winsorize/z-score/one-hot。

DECLARE dws_start_date DATE DEFAULT DATE '2019-01-01';
DECLARE dws_end_date DATE DEFAULT CURRENT_DATE('Asia/Shanghai');
DECLARE target_feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';

CREATE OR REPLACE TABLE `data-aquarium.ashare_dws.dws_stock_feature_daily_v0`
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY sec_code, feature_version
OPTIONS (
  description = 'Strategy 1 raw feature wide table assembled from price and valuation feature domains; writes 2019+ rows',
  require_partition_filter = TRUE
) AS
SELECT
  p.trade_date,
  p.sec_code,
  p.feature_version,
  u.universe_version,
  u.market,
  u.board,
  u.list_age_td,
  u.is_st,
  u.is_tradable_hard,
  u.in_universe_default,
  p.ret_1d,
  p.ret_3d,
  p.ret_5d,
  p.ret_10d,
  p.ret_20d,
  p.ret_60d,
  p.mom_20_5,
  p.mom_60_20,
  p.vol_5d,
  p.vol_20d,
  p.vol_60d,
  p.drawdown_20d,
  p.close_to_low_20d,
  p.amplitude_1d,
  p.gap_open_1d,
  p.intraday_ret_1d,
  p.hl_range_20d,
  p.amount_cny,
  p.amount_ma5_cny,
  p.amount_ma20_cny,
  p.amount_zscore_20d,
  p.suspend_days_20d,
  p.limit_up_days_20d,
  p.limit_down_days_20d,
  p.one_word_limit_days_20d,
  p.tradable_days_20d,
  p.history_obs_60d,
  p.has_full_history_60d,
  v.turnover_rate,
  v.turnover_rate_free_float,
  v.turnover_rate_ma5,
  v.turnover_rate_ma20,
  v.turnover_rate_free_float_ma20,
  v.volume_ratio,
  v.volume_ratio_ma20,
  v.turnover_rate_zscore_60d,
  v.pe,
  v.pe_ttm,
  v.pb,
  v.ps,
  v.ps_ttm,
  v.dividend_yield_ttm,
  v.ep_ttm,
  v.bp,
  v.sp_ttm,
  v.total_mv_cny,
  v.circ_mv_cny,
  v.log_total_mv,
  v.log_circ_mv,
  v.has_valuation_data,
  CURRENT_TIMESTAMP() AS created_at
FROM `data-aquarium.ashare_dws.dws_stock_feature_price_daily` AS p
JOIN `data-aquarium.ashare_dws.dws_stock_universe_daily` AS u
  ON p.trade_date = u.trade_date
 AND p.sec_code = u.sec_code
 AND u.trade_date BETWEEN dws_start_date AND dws_end_date
LEFT JOIN `data-aquarium.ashare_dws.dws_stock_feature_valuation_daily` AS v
  ON p.trade_date = v.trade_date
 AND p.sec_code = v.sec_code
 AND p.feature_version = v.feature_version
 AND v.trade_date BETWEEN dws_start_date AND dws_end_date
WHERE p.trade_date BETWEEN dws_start_date AND dws_end_date
  AND p.feature_version = target_feature_version;

ALTER TABLE `data-aquarium.ashare_dws.dws_stock_feature_daily_v0`
ALTER COLUMN trade_date SET OPTIONS (description = '特征日，月分区字段'),
ALTER COLUMN feature_version SET OPTIONS (description = '特征版本'),
ALTER COLUMN universe_version SET OPTIONS (description = '股票池规则版本'),
ALTER COLUMN in_universe_default SET OPTIONS (description = '策略 1 默认股票池掩码'),
ALTER COLUMN has_full_history_60d SET OPTIONS (description = '是否具备 60 日窗口完整历史'),
ALTER COLUMN has_valuation_data SET OPTIONS (description = '是否具备日频估值/市值数据');
