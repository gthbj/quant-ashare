-- BigQuery Standard SQL
-- Strategy1 ADS migration: add explicit compound annual return fields.
--
-- This migration is additive. It preserves the legacy arithmetic
-- annual_return / sharpe fields while allowing new runner outputs to write
-- compound_annual_return and its annualization metadata.

ALTER TABLE `data-aquarium.ashare_ads.ads_backtest_performance_summary`
ADD COLUMN IF NOT EXISTS compound_annual_return FLOAT64
OPTIONS(description = 'Compound annualized total return, calculated from full-period NAV total return using return_period_count');

ALTER TABLE `data-aquarium.ashare_ads.ads_backtest_performance_summary`
ADD COLUMN IF NOT EXISTS return_period_count INT64
OPTIONS(description = 'Effective NAV return intervals used for annualization, equal to effective NAV trading-day count minus one');

ALTER TABLE `data-aquarium.ashare_ads.ads_backtest_performance_summary`
ADD COLUMN IF NOT EXISTS annualization_target_period_count INT64
OPTIONS(description = 'Target period count for annualization; default is 252 trading-day periods per year');

ALTER TABLE `data-aquarium.ashare_ads.ads_backtest_performance_summary`
ADD COLUMN IF NOT EXISTS annualization_method STRING
OPTIONS(description = 'Annualization method used for compound_annual_return, expected value: compound');

ALTER TABLE `data-aquarium.ashare_ads.ads_backtest_performance_summary`
ALTER COLUMN annual_return SET OPTIONS(description = 'Legacy arithmetic annualized return, mean daily return times 252; use compound_annual_return for default reporting');

ALTER TABLE `data-aquarium.ashare_ads.ads_backtest_performance_summary`
ALTER COLUMN sharpe SET OPTIONS(description = 'Legacy Sharpe ratio using legacy arithmetic annual_return divided by annual_vol; v3 compound Sharpe is emitted in metrics_json');
