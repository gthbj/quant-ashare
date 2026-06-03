-- 文档维护：GPT-5（最近更新 2026-06-01）
-- BigQuery Standard SQL
-- 策略 1 样本表：universe ∩ 特征 ∩ 标签，保留资格掩码和默认切分。

DECLARE dws_start_date DATE DEFAULT DATE '2019-01-01';
DECLARE dws_end_date DATE DEFAULT CURRENT_DATE('Asia/Shanghai');
DECLARE target_feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE target_label_version STRING DEFAULT 'open_to_close_h1_5_10_20_v20260601';

CREATE OR REPLACE TABLE `data-aquarium.ashare_dws.dws_stock_sample_daily`
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY sec_code, feature_version, label_version
OPTIONS (
  description = 'Strategy 1 sample table joining default universe, raw features and open-to-close labels; preprocessing remains in ADS run',
  require_partition_filter = TRUE
) AS
SELECT
  f.trade_date,
  f.sec_code,
  f.feature_version,
  l.label_version,
  f.universe_version,
  f.market,
  f.board,
  f.list_age_td,
  f.is_st,
  f.is_tradable_hard,
  f.in_universe_default,
  f.has_full_history_60d,
  f.has_valuation_data,
  l.label_entry_tradable,
  l.label_valid_1d,
  l.label_valid_5d,
  l.label_valid_10d,
  l.label_valid_20d,
  l.fwd_ret_1d,
  l.fwd_ret_5d,
  l.fwd_ret_10d,
  l.fwd_ret_20d,
  l.fwd_xs_ret_5d,
  l.fwd_xs_ret_10d,
  l.fwd_xs_ret_20d,
  l.rank_pct_5d,
  l.rank_pct_10d,
  l.rank_pct_20d,
  l.label_top30_5d,
  l.label_top30_10d,
  l.label_top30_20d,
  l.label_above_median_5d,
  l.label_above_median_10d,
  l.label_above_median_20d,
  f.ret_1d,
  f.ret_3d,
  f.ret_5d,
  f.ret_10d,
  f.ret_20d,
  f.ret_60d,
  f.mom_20_5,
  f.mom_60_20,
  f.vol_5d,
  f.vol_20d,
  f.vol_60d,
  f.drawdown_20d,
  f.hl_range_20d,
  f.amount_ma20_cny,
  f.amount_zscore_20d,
  f.turnover_rate,
  f.turnover_rate_free_float,
  f.turnover_rate_ma20,
  f.volume_ratio,
  f.pe_ttm,
  f.pb,
  f.ps_ttm,
  f.dividend_yield_ttm,
  f.ep_ttm,
  f.bp,
  f.sp_ttm,
  f.log_total_mv,
  f.log_circ_mv,
  f.in_universe_default
    AND f.has_full_history_60d
    AND COALESCE(f.has_valuation_data, FALSE)
    AND l.label_entry_tradable
    AND l.label_valid_5d AS sample_trainable_default,
  'fold_default_2019_2026' AS split_fold,
  CASE
    WHEN f.trade_date < DATE '2024-01-01' THEN 'train'
    WHEN f.trade_date < DATE '2025-01-01' THEN 'valid'
    WHEN f.trade_date < DATE '2026-01-01' THEN 'test'
    ELSE 'live'
  END AS split_tag,
  CURRENT_TIMESTAMP() AS created_at
FROM `data-aquarium.ashare_dws.dws_stock_feature_daily_v0` AS f
JOIN `data-aquarium.ashare_dws.dws_stock_label_daily` AS l
  ON f.trade_date = l.trade_date
 AND f.sec_code = l.sec_code
 AND l.trade_date BETWEEN dws_start_date AND dws_end_date
WHERE f.trade_date BETWEEN dws_start_date AND dws_end_date
  AND f.feature_version = target_feature_version
  AND l.label_version = target_label_version;

ALTER TABLE `data-aquarium.ashare_dws.dws_stock_sample_daily`
ALTER COLUMN trade_date SET OPTIONS (description = '样本日，月分区字段'),
ALTER COLUMN sample_trainable_default SET OPTIONS (description = '策略 1 默认可训练样本掩码：默认池、完整 60 日历史、估值数据、t+1 可买且 5 日标签有效'),
ALTER COLUMN split_fold SET OPTIONS (description = '默认静态切分版本；滚动 fold 在 ADS training panel run 中固化'),
ALTER COLUMN split_tag SET OPTIONS (description = '默认切分：2019-2023 train、2024 valid、2025 test、2026+ live');
