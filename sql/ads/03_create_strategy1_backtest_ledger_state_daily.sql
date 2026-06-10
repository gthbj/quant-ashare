-- BigQuery Standard SQL
-- Strategy1 ADS additive migration: create Cloud Run ledger resume state table.
--
-- This migration is intentionally additive and idempotent. It must not rebuild
-- existing ADS tables or backfill historical runs. Run
-- 02_alter_strategy1_backtest_compound_annual_return.sql separately for
-- performance summary compound annualization columns.

CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_ads.ads_backtest_ledger_state_daily` (
  backtest_id STRING OPTIONS(description = '回测 id'),
  trade_date DATE OPTIONS(description = '状态快照日，月分区字段'),
  cash_cny FLOAT64 OPTIONS(description = '现金，元'),
  net_value_cny FLOAT64 OPTIONS(description = '组合净资产，元'),
  nav FLOAT64 OPTIONS(description = '组合净值'),
  pending_sell_sec_codes_json STRING OPTIONS(description = '待卖证券代码 JSON array'),
  active_signal_date DATE OPTIONS(description = '当前生效调仓信号日'),
  active_target_weights_json STRING OPTIONS(description = '当前生效目标权重 JSON object'),
  holdings_hash STRING OPTIONS(description = '持仓股数快照哈希'),
  ledger_version STRING OPTIONS(description = 'ledger 版本'),
  ledger_params_hash STRING OPTIONS(description = 'resume 兼容参数哈希'),
  resume_policy_id STRING OPTIONS(description = 'resume 策略语义 id'),
  rebalance_anchor_start DATE OPTIONS(description = '调仓 cadence 锚点起始日'),
  run_id STRING OPTIONS(description = '回测 run id'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY backtest_id
OPTIONS (
  description = 'Daily Cloud Run Python ledger state snapshots for deterministic resume_from_backtest',
  require_partition_filter = TRUE
);
