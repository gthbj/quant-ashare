-- 文档维护：GPT-5（最近更新 2026-06-01）
-- BigQuery Standard SQL
-- 策略 1 ADS 表契约。计算逻辑由 BigQuery ML + SQL runner 写入，当前脚本只创建消费表结构。

CREATE OR REPLACE TABLE `data-aquarium.ashare_ads.ads_ml_training_panel_daily` (
  run_id STRING OPTIONS(description = '训练 run id'),
  strategy_id STRING OPTIONS(description = '策略 id，如 ml_pv_clf_v0'),
  model_id STRING OPTIONS(description = '模型 id'),
  preprocess_version STRING OPTIONS(description = '预处理版本'),
  feature_version STRING OPTIONS(description = '特征版本'),
  label_version STRING OPTIONS(description = '标签版本'),
  universe_version STRING OPTIONS(description = '股票池版本'),
  trade_date DATE OPTIONS(description = '样本日，月分区字段'),
  sec_code STRING OPTIONS(description = '统一证券代码'),
  horizon INT64 OPTIONS(description = '预测/标签 horizon，交易日'),
  split_fold STRING OPTIONS(description = '滚动或静态切分 fold id'),
  split_tag STRING OPTIONS(description = 'train/valid/test/live'),
  sample_weight FLOAT64 OPTIONS(description = '样本权重'),
  target_label INT64 OPTIONS(description = '分类目标标签'),
  target_return FLOAT64 OPTIONS(description = '回归目标收益'),
  feature_values_json STRING OPTIONS(description = '本 run 固化后的预处理特征 JSON'),
  feature_column_list ARRAY<STRING> OPTIONS(description = '特征列清单，顺序与 feature_values_json 对齐'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY run_id, sec_code
OPTIONS (
  description = 'Frozen ML training panel for a concrete run_id; stores preprocessed features, targets and split tags',
  require_partition_filter = TRUE
);

CREATE OR REPLACE TABLE `data-aquarium.ashare_ads.ads_model_registry` (
  model_id STRING OPTIONS(description = '模型 id，主键'),
  strategy_id STRING OPTIONS(description = '策略 id'),
  model_family STRING OPTIONS(description = '模型族，如 logistic_elasticnet/ridge'),
  horizon INT64 OPTIONS(description = '主 horizon，交易日'),
  feature_version STRING OPTIONS(description = '特征版本'),
  label_version STRING OPTIONS(description = '标签版本'),
  preprocess_version STRING OPTIONS(description = '预处理版本'),
  train_start_date DATE OPTIONS(description = '训练开始日'),
  train_end_date DATE OPTIONS(description = '训练结束日'),
  valid_start_date DATE OPTIONS(description = '验证开始日'),
  valid_end_date DATE OPTIONS(description = '验证结束日'),
  model_params_json STRING OPTIONS(description = '模型参数 JSON'),
  metrics_json STRING OPTIONS(description = '验证/测试指标 JSON'),
  model_uri STRING OPTIONS(description = '模型二进制或 artifact URI，不在 BigQuery 存二进制'),
  git_commit STRING OPTIONS(description = '代码 commit hash'),
  status STRING OPTIONS(description = 'registered/active/deprecated 等状态'),
  created_at TIMESTAMP OPTIONS(description = '注册时间')
)
CLUSTER BY strategy_id, model_id
OPTIONS (description = 'Model registry metadata table; model binary artifacts are stored outside BigQuery');

CREATE OR REPLACE TABLE `data-aquarium.ashare_ads.ads_model_prediction_daily` (
  model_id STRING OPTIONS(description = '模型 id'),
  predict_date DATE OPTIONS(description = '预测日，月分区字段'),
  horizon INT64 OPTIONS(description = '预测 horizon，交易日'),
  sec_code STRING OPTIONS(description = '统一证券代码'),
  score FLOAT64 OPTIONS(description = '经 orientation 校准后的最终分数（identity 时 = raw_score，reverse_probability 时 = 1 - raw_score）；选股/排名使用此列'),
  raw_score FLOAT64 OPTIONS(description = 'ML.PREDICT 原始 label=1 正类概率，未经 orientation 校准'),
  score_orientation STRING OPTIONS(description = 'score 校准方向：identity（原样）或 reverse_probability（1-raw_score）'),
  rank_raw INT64 OPTIONS(description = '当日 score 降序名次，1 为最高（基于 oriented score）'),
  rank_pct FLOAT64 OPTIONS(description = '当日 score 横截面分位，1 为最高（基于 oriented score）'),
  feature_version STRING OPTIONS(description = '特征版本'),
  run_id STRING OPTIONS(description = '预测 run id'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(predict_date, MONTH)
CLUSTER BY model_id, sec_code
OPTIONS (
  description = 'Daily model predictions with orientation-calibrated scores and cross-sectional ranks',
  require_partition_filter = TRUE
);

CREATE OR REPLACE TABLE `data-aquarium.ashare_ads.ads_stock_candidate_daily` (
  strategy_id STRING OPTIONS(description = '策略 id'),
  rebalance_date DATE OPTIONS(description = '调仓信号日，月分区字段'),
  sec_code STRING OPTIONS(description = '统一证券代码'),
  model_id STRING OPTIONS(description = '模型 id'),
  horizon INT64 OPTIONS(description = '模型 horizon，交易日'),
  score FLOAT64 OPTIONS(description = '候选股模型分数'),
  rank_raw INT64 OPTIONS(description = '候选池名次，1 为最高'),
  rank_pct FLOAT64 OPTIONS(description = '候选池分位，1 为最高'),
  in_universe_default BOOL OPTIONS(description = '是否属于默认股票池'),
  is_selected_candidate BOOL OPTIONS(description = '是否进入目标候选名单'),
  filter_reason STRING OPTIONS(description = '未入选或过滤原因'),
  run_id STRING OPTIONS(description = '生成 run id'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(rebalance_date, MONTH)
CLUSTER BY strategy_id, sec_code
OPTIONS (
  description = 'Strategy rebalance-date candidate list with ranks and filter reasons',
  require_partition_filter = TRUE
);

CREATE OR REPLACE TABLE `data-aquarium.ashare_ads.ads_portfolio_target_daily` (
  strategy_id STRING OPTIONS(description = '策略 id'),
  rebalance_date DATE OPTIONS(description = '调仓信号日，月分区字段'),
  sec_code STRING OPTIONS(description = '统一证券代码'),
  target_weight FLOAT64 OPTIONS(description = '目标权重'),
  target_shares FLOAT64 OPTIONS(description = '目标股数'),
  target_amount_cny FLOAT64 OPTIONS(description = '目标市值，元'),
  model_id STRING OPTIONS(description = '模型 id'),
  horizon INT64 OPTIONS(description = '模型 horizon，交易日'),
  run_id STRING OPTIONS(description = '生成 run id'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(rebalance_date, MONTH)
CLUSTER BY strategy_id, sec_code
OPTIONS (
  description = 'Strategy target portfolio weights for each rebalance date',
  require_partition_filter = TRUE
);

CREATE OR REPLACE TABLE `data-aquarium.ashare_ads.ads_order_plan_daily` (
  strategy_id STRING OPTIONS(description = '策略 id'),
  rebalance_date DATE OPTIONS(description = '调仓信号日，月分区字段'),
  sec_code STRING OPTIONS(description = '统一证券代码'),
  side STRING OPTIONS(description = 'BUY/SELL'),
  order_weight_delta FLOAT64 OPTIONS(description = '目标权重变动'),
  order_shares FLOAT64 OPTIONS(description = '计划交易股数'),
  expected_price FLOAT64 OPTIONS(description = '预期成交价，元/股'),
  expected_amount_cny FLOAT64 OPTIONS(description = '预期成交金额，元'),
  order_reason STRING OPTIONS(description = '下单原因'),
  run_id STRING OPTIONS(description = '生成 run id'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(rebalance_date, MONTH)
CLUSTER BY strategy_id, sec_code, side
OPTIONS (
  description = 'Order plan table for backtest or simulation execution',
  require_partition_filter = TRUE
);

CREATE OR REPLACE TABLE `data-aquarium.ashare_ads.ads_backtest_trade_daily` (
  backtest_id STRING OPTIONS(description = '回测 id'),
  trade_date DATE OPTIONS(description = '成交日，月分区字段'),
  sec_code STRING OPTIONS(description = '统一证券代码'),
  side STRING OPTIONS(description = 'BUY/SELL'),
  planned_shares FLOAT64 OPTIONS(description = '计划股数'),
  filled_shares FLOAT64 OPTIONS(description = '实际成交股数'),
  fill_price FLOAT64 OPTIONS(description = '成交价，元/股'),
  turnover_cny FLOAT64 OPTIONS(description = '成交额，元'),
  fee_cny FLOAT64 OPTIONS(description = '手续费，元'),
  tax_cny FLOAT64 OPTIONS(description = '印花税，元'),
  slippage_cny FLOAT64 OPTIONS(description = '滑点成本，元'),
  cash_effect_cny FLOAT64 OPTIONS(description = '现金影响，元'),
  fill_status STRING OPTIONS(description = '成交状态。v1 ledger 实际产生：FILLED（已成交）、BUY_SKIPPED_UNTRADABLE / SELL_SKIPPED_UNTRADABLE（本期不可交易跳过的意图行，filled_shares=0、无现金/换手影响，持仓 carry 到下一调仓日再试）。PARTIAL/REJECTED 为契约预留，v1 ledger 当前不产生。'),
  run_id STRING OPTIONS(description = '回测 run id'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY backtest_id, sec_code
OPTIONS (
  description = 'Backtest execution fills and transaction costs',
  require_partition_filter = TRUE
);

CREATE OR REPLACE TABLE `data-aquarium.ashare_ads.ads_backtest_position_daily` (
  backtest_id STRING OPTIONS(description = '回测 id'),
  trade_date DATE OPTIONS(description = '持仓日，月分区字段'),
  sec_code STRING OPTIONS(description = '统一证券代码'),
  shares FLOAT64 OPTIONS(description = '持仓股数'),
  close FLOAT64 OPTIONS(description = '收盘价，元/股'),
  market_value_cny FLOAT64 OPTIONS(description = '持仓市值，元'),
  weight FLOAT64 OPTIONS(description = '组合权重'),
  unrealized_pnl_cny FLOAT64 OPTIONS(description = '未实现盈亏，元'),
  run_id STRING OPTIONS(description = '回测 run id'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY backtest_id, sec_code
OPTIONS (
  description = 'Backtest daily positions and market values',
  require_partition_filter = TRUE
);

CREATE OR REPLACE TABLE `data-aquarium.ashare_ads.ads_backtest_nav_daily` (
  backtest_id STRING OPTIONS(description = '回测 id'),
  trade_date DATE OPTIONS(description = '净值日，月分区字段'),
  nav FLOAT64 OPTIONS(description = '组合净值'),
  cash_cny FLOAT64 OPTIONS(description = '现金，元'),
  net_value_cny FLOAT64 OPTIONS(description = '组合净资产，元'),
  gross_exposure FLOAT64 OPTIONS(description = '总暴露'),
  turnover_cny FLOAT64 OPTIONS(description = '当日换手成交额，元'),
  cost_cny FLOAT64 OPTIONS(description = '当日交易成本，元'),
  daily_return FLOAT64 OPTIONS(description = '组合日收益'),
  benchmark_sec_code STRING OPTIONS(description = '基准指数 canonical sec_code'),
  benchmark_return FLOAT64 OPTIONS(description = '基准日收益'),
  excess_return FLOAT64 OPTIONS(description = '相对基准日超额收益'),
  run_id STRING OPTIONS(description = '回测 run id'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY backtest_id
OPTIONS (
  description = 'Backtest daily NAV, return, turnover and benchmark excess return',
  require_partition_filter = TRUE
);

CREATE OR REPLACE TABLE `data-aquarium.ashare_ads.ads_backtest_performance_summary` (
  backtest_id STRING OPTIONS(description = '回测 id'),
  strategy_id STRING OPTIONS(description = '策略 id'),
  model_id STRING OPTIONS(description = '模型 id'),
  start_date DATE OPTIONS(description = '回测开始日'),
  end_date DATE OPTIONS(description = '回测结束日'),
  total_return FLOAT64 OPTIONS(description = '累计收益'),
  annual_return FLOAT64 OPTIONS(description = '年化收益'),
  annual_vol FLOAT64 OPTIONS(description = '年化波动'),
  sharpe FLOAT64 OPTIONS(description = '夏普比率'),
  max_drawdown FLOAT64 OPTIONS(description = '最大回撤'),
  turnover_annual FLOAT64 OPTIONS(description = '年化换手'),
  benchmark_sec_code STRING OPTIONS(description = '基准指数 canonical sec_code'),
  excess_return FLOAT64 OPTIONS(description = '累计超额收益'),
  information_ratio FLOAT64 OPTIONS(description = '信息比率'),
  cost_bps FLOAT64 OPTIONS(description = '回测成本假设，bps'),
  metrics_json STRING OPTIONS(description = '扩展指标 JSON'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
CLUSTER BY strategy_id, model_id, backtest_id
OPTIONS (description = 'Backtest performance summary table');

CREATE OR REPLACE TABLE `data-aquarium.ashare_ads.ads_signal_monitor_daily` (
  strategy_id STRING OPTIONS(description = '策略 id'),
  model_id STRING OPTIONS(description = '模型 id'),
  trade_date DATE OPTIONS(description = '监控日，月分区字段'),
  sample_count INT64 OPTIONS(description = '样本数'),
  prediction_count INT64 OPTIONS(description = '预测数'),
  candidate_count INT64 OPTIONS(description = '候选数'),
  avg_score FLOAT64 OPTIONS(description = '平均分数'),
  score_std FLOAT64 OPTIONS(description = '分数标准差'),
  not_tradable_entry_count INT64 OPTIONS(description = '入场不可交易样本数'),
  metrics_json STRING OPTIONS(description = '扩展监控指标 JSON'),
  run_id STRING OPTIONS(description = '监控 run id'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY strategy_id, model_id
OPTIONS (
  description = 'Daily signal and data-quality monitor for model outputs',
  require_partition_filter = TRUE
);
