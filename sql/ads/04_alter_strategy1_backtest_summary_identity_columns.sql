-- BigQuery Standard SQL
-- Strategy1 ADS migration: add explicit run identity fields to backtest summary.
--
-- This migration is additive. Existing ADS summary rows remain legacy rows with
-- NULL values; new runner outputs populate these columns through 09 reporting.

ALTER TABLE `data-aquarium.ashare_ads.ads_backtest_performance_summary`
ADD COLUMN IF NOT EXISTS run_id STRING
OPTIONS(description = 'Run id that produced this backtest summary');

ALTER TABLE `data-aquarium.ashare_ads.ads_backtest_performance_summary`
ADD COLUMN IF NOT EXISTS created_date DATE
OPTIONS(description = 'Summary write date; mirrors research summary partition field');
