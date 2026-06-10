-- 文档维护：GPT-5 Codex（最近更新 2026-06-10）
-- BigQuery Standard SQL
-- Strategy1 research table contracts.
--
-- D0 only defines table contracts for data-aquarium.ashare_research.
-- It does not switch runner defaults, does not migrate historical ADS data,
-- and does not implement promotion writes.

CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_research.research_ml_training_panel_daily` (
  run_id STRING OPTIONS(description = '研究 run id'),
  strategy_id STRING OPTIONS(description = '策略 id，如 ml_pv_clf_v0'),
  model_id STRING OPTIONS(description = '候选模型 id；训练面板构建阶段可为空'),
  preprocess_version STRING OPTIONS(description = '预处理版本'),
  feature_version STRING OPTIONS(description = '特征版本'),
  label_version STRING OPTIONS(description = '标签版本'),
  universe_version STRING OPTIONS(description = '股票池版本'),
  trade_date DATE OPTIONS(description = '样本日，月分区字段'),
  sec_code STRING OPTIONS(description = '统一证券代码'),
  horizon INT64 OPTIONS(description = '预测/标签 horizon，交易日'),
  split_fold STRING OPTIONS(description = '滚动或静态切分 fold id'),
  split_tag STRING OPTIONS(description = 'train/valid/test/final_holdout/live'),
  sample_weight FLOAT64 OPTIONS(description = '样本权重'),
  target_label INT64 OPTIONS(description = '分类目标标签'),
  target_return FLOAT64 OPTIONS(description = '回归目标收益'),
  feature_values_json STRING OPTIONS(description = '本 run 固化后的预处理特征 JSON'),
  feature_column_list ARRAY<STRING> OPTIONS(description = '特征列清单，顺序与 feature_values_json 对齐'),
  research_status STRING OPTIONS(description = '研究生命周期状态：candidate/rejected/accepted/superseded 等'),
  promotion_status STRING OPTIONS(description = 'promotion 状态：not_promoted/promoted/deprecated；默认 not_promoted'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY run_id, sec_code
OPTIONS (
  description = 'Research frozen ML training panel for unpromoted Strategy1 runs; ADS-compatible columns plus research lifecycle metadata',
  require_partition_filter = TRUE
);

CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_research.research_model_registry` (
  model_id STRING OPTIONS(description = '候选模型 id'),
  strategy_id STRING OPTIONS(description = '策略 id'),
  run_id STRING OPTIONS(description = '训练 / 预测 run id'),
  search_id STRING OPTIONS(description = '候选搜索 id；单次非搜索实验可为空'),
  experiment_id STRING OPTIONS(description = '实验 id'),
  experiment_group STRING OPTIONS(description = '实验组'),
  model_family STRING OPTIONS(description = '模型族，如 lightgbm_regression/logistic_regression'),
  horizon INT64 OPTIONS(description = '主 horizon，交易日'),
  feature_version STRING OPTIONS(description = '特征版本'),
  label_version STRING OPTIONS(description = '标签版本'),
  preprocess_version STRING OPTIONS(description = '预处理版本'),
  train_start_date DATE OPTIONS(description = '训练开始日'),
  train_end_date DATE OPTIONS(description = '训练结束日'),
  valid_start_date DATE OPTIONS(description = '验证开始日'),
  valid_end_date DATE OPTIONS(description = '验证结束日'),
  test_start_date DATE OPTIONS(description = '测试开始日'),
  test_end_date DATE OPTIONS(description = '测试结束日'),
  final_holdout_start_date DATE OPTIONS(description = '最终 holdout 开始日'),
  final_holdout_end_date DATE OPTIONS(description = '最终 holdout 结束日'),
  model_params_json STRING OPTIONS(description = '模型参数 JSON'),
  metrics_json STRING OPTIONS(description = '验证/测试/holdout 指标 JSON'),
  model_uri STRING OPTIONS(description = '模型二进制或 artifact URI，不在 BigQuery 存二进制'),
  artifact_uri STRING OPTIONS(description = '研究 artifact 根 URI'),
  git_commit STRING OPTIONS(description = '代码 commit hash'),
  status STRING OPTIONS(description = '候选状态：registered/rejected/accepted/superseded 等'),
  acceptance_status STRING OPTIONS(description = 'acceptance gate 状态：not_evaluated/rejected/accepted/needs_more_evidence'),
  promotion_status STRING OPTIONS(description = 'promotion 状态：not_promoted/promoted/deprecated；accepted 不等于 promoted'),
  promotion_id STRING OPTIONS(description = '若已 promotion，对应 promotion id；否则为空'),
  approval_ref STRING OPTIONS(description = 'owner approval / PR / issue 引用；未 promotion 时为空'),
  created_date DATE OPTIONS(description = '注册日期，月分区字段'),
  created_at TIMESTAMP OPTIONS(description = '注册时间')
)
PARTITION BY DATE_TRUNC(created_date, MONTH)
CLUSTER BY strategy_id, model_id
OPTIONS (
  description = 'Research model registry for candidate and accepted-but-unpromoted Strategy1 models',
  require_partition_filter = FALSE
);

CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_research.research_model_prediction_daily` (
  model_id STRING OPTIONS(description = '候选模型 id'),
  predict_date DATE OPTIONS(description = '预测日，月分区字段'),
  horizon INT64 OPTIONS(description = '预测 horizon，交易日'),
  sec_code STRING OPTIONS(description = '统一证券代码'),
  score FLOAT64 OPTIONS(description = '经 orientation 校准后的最终分数'),
  raw_score FLOAT64 OPTIONS(description = '模型原始分数或概率，未经 orientation 校准'),
  score_orientation STRING OPTIONS(description = 'score 校准方向：identity/reverse_probability 等'),
  rank_raw INT64 OPTIONS(description = '当日 score 降序名次，1 为最高'),
  rank_pct FLOAT64 OPTIONS(description = '当日 score 横截面分位，1 为最高'),
  feature_version STRING OPTIONS(description = '特征版本'),
  run_id STRING OPTIONS(description = '预测 run id'),
  research_status STRING OPTIONS(description = '研究生命周期状态：candidate/rejected/accepted/superseded 等'),
  promotion_status STRING OPTIONS(description = 'promotion 状态：not_promoted/promoted/deprecated'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(predict_date, MONTH)
CLUSTER BY model_id, sec_code
OPTIONS (
  description = 'Daily research model predictions for unpromoted Strategy1 runs',
  require_partition_filter = TRUE
);

CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_research.research_stock_candidate_daily` (
  strategy_id STRING OPTIONS(description = '策略 id'),
  rebalance_date DATE OPTIONS(description = '调仓信号日，月分区字段'),
  sec_code STRING OPTIONS(description = '统一证券代码'),
  model_id STRING OPTIONS(description = '候选模型 id'),
  horizon INT64 OPTIONS(description = '模型 horizon，交易日'),
  score FLOAT64 OPTIONS(description = '候选股模型分数'),
  rank_raw INT64 OPTIONS(description = '候选池名次，1 为最高'),
  rank_pct FLOAT64 OPTIONS(description = '候选池分位，1 为最高'),
  in_universe_default BOOL OPTIONS(description = '是否属于默认股票池'),
  is_selected_candidate BOOL OPTIONS(description = '是否进入目标候选名单'),
  filter_reason STRING OPTIONS(description = '未入选或过滤原因'),
  run_id STRING OPTIONS(description = '生成 run id'),
  research_status STRING OPTIONS(description = '研究生命周期状态：candidate/rejected/accepted/superseded 等'),
  promotion_status STRING OPTIONS(description = 'promotion 状态：not_promoted/promoted/deprecated'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(rebalance_date, MONTH)
CLUSTER BY strategy_id, sec_code
OPTIONS (
  description = 'Research rebalance-date candidate list for unpromoted Strategy1 runs',
  require_partition_filter = TRUE
);

CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_research.research_portfolio_target_daily` (
  strategy_id STRING OPTIONS(description = '策略 id'),
  rebalance_date DATE OPTIONS(description = '调仓信号日，月分区字段'),
  sec_code STRING OPTIONS(description = '统一证券代码'),
  target_weight FLOAT64 OPTIONS(description = '目标权重'),
  target_shares FLOAT64 OPTIONS(description = '目标股数'),
  target_amount_cny FLOAT64 OPTIONS(description = '目标市值，元'),
  model_id STRING OPTIONS(description = '候选模型 id'),
  horizon INT64 OPTIONS(description = '模型 horizon，交易日'),
  run_id STRING OPTIONS(description = '生成 run id'),
  research_status STRING OPTIONS(description = '研究生命周期状态：candidate/rejected/accepted/superseded 等'),
  promotion_status STRING OPTIONS(description = 'promotion 状态：not_promoted/promoted/deprecated'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(rebalance_date, MONTH)
CLUSTER BY strategy_id, sec_code
OPTIONS (
  description = 'Research target portfolio weights for each rebalance date',
  require_partition_filter = TRUE
);

CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_research.research_order_plan_daily` (
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
  research_status STRING OPTIONS(description = '研究生命周期状态：candidate/rejected/accepted/superseded 等'),
  promotion_status STRING OPTIONS(description = 'promotion 状态：not_promoted/promoted/deprecated'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(rebalance_date, MONTH)
CLUSTER BY strategy_id, sec_code, side
OPTIONS (
  description = 'Research order plan table for unpromoted backtest or simulation execution',
  require_partition_filter = TRUE
);

CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_research.research_backtest_trade_daily` (
  backtest_id STRING OPTIONS(description = '研究回测 id'),
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
  fill_status STRING OPTIONS(description = '成交状态；非成交状态 filled_shares=0 且无现金/换手影响'),
  run_id STRING OPTIONS(description = '回测 run id'),
  research_status STRING OPTIONS(description = '研究生命周期状态：candidate/rejected/accepted/superseded 等'),
  promotion_status STRING OPTIONS(description = 'promotion 状态：not_promoted/promoted/deprecated'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY backtest_id, sec_code
OPTIONS (
  description = 'Research backtest execution fills and transaction costs',
  require_partition_filter = TRUE
);

CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_research.research_backtest_position_daily` (
  backtest_id STRING OPTIONS(description = '研究回测 id'),
  trade_date DATE OPTIONS(description = '持仓日，月分区字段'),
  sec_code STRING OPTIONS(description = '统一证券代码'),
  shares FLOAT64 OPTIONS(description = '持仓股数'),
  close FLOAT64 OPTIONS(description = '收盘价，元/股'),
  market_value_cny FLOAT64 OPTIONS(description = '持仓市值，元'),
  weight FLOAT64 OPTIONS(description = '组合权重'),
  unrealized_pnl_cny FLOAT64 OPTIONS(description = '未实现盈亏，元'),
  run_id STRING OPTIONS(description = '回测 run id'),
  research_status STRING OPTIONS(description = '研究生命周期状态：candidate/rejected/accepted/superseded 等'),
  promotion_status STRING OPTIONS(description = 'promotion 状态：not_promoted/promoted/deprecated'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY backtest_id, sec_code
OPTIONS (
  description = 'Research backtest daily positions and market values',
  require_partition_filter = TRUE
);

CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_research.research_backtest_nav_daily` (
  backtest_id STRING OPTIONS(description = '研究回测 id'),
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
  research_status STRING OPTIONS(description = '研究生命周期状态：candidate/rejected/accepted/superseded 等'),
  promotion_status STRING OPTIONS(description = 'promotion 状态：not_promoted/promoted/deprecated'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY backtest_id
OPTIONS (
  description = 'Research backtest daily NAV, return, turnover and benchmark excess return',
  require_partition_filter = TRUE
);

CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_research.research_backtest_ledger_state_daily` (
  backtest_id STRING OPTIONS(description = '研究回测 id'),
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
  research_status STRING OPTIONS(description = '研究生命周期状态：candidate/rejected/accepted/superseded 等'),
  promotion_status STRING OPTIONS(description = 'promotion 状态：not_promoted/promoted/deprecated'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY backtest_id
OPTIONS (
  description = 'Research Cloud Run Python ledger state snapshots for deterministic resume_from_backtest',
  require_partition_filter = TRUE
);

CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_research.research_backtest_performance_summary` (
  backtest_id STRING OPTIONS(description = '研究回测 id'),
  strategy_id STRING OPTIONS(description = '策略 id'),
  model_id STRING OPTIONS(description = '候选模型 id'),
  run_id STRING OPTIONS(description = '回测 run id'),
  start_date DATE OPTIONS(description = '回测开始日'),
  end_date DATE OPTIONS(description = '回测结束日'),
  total_return FLOAT64 OPTIONS(description = '累计收益'),
  annual_return FLOAT64 OPTIONS(description = 'Legacy 算术年化收益，保留兼容；默认复利年化请使用 compound_annual_return'),
  compound_annual_return FLOAT64 OPTIONS(description = '复合年化收益，按 NAV 有效日收益区间数年化'),
  return_period_count INT64 OPTIONS(description = '复合年化有效日收益区间数，等于 NAV 有效交易日数减 1'),
  annualization_target_period_count INT64 OPTIONS(description = '年化目标期数，交易日口径默认 252'),
  annualization_method STRING OPTIONS(description = '年化方法；compound 表示复利年化'),
  annual_vol FLOAT64 OPTIONS(description = '年化波动'),
  sharpe FLOAT64 OPTIONS(description = 'Legacy Sharpe，分子沿用 annual_return；v3 复合年化 Sharpe 写入 metrics_json.v3_sharpe_ratio'),
  max_drawdown FLOAT64 OPTIONS(description = '最大回撤'),
  turnover_annual FLOAT64 OPTIONS(description = '年化换手'),
  benchmark_sec_code STRING OPTIONS(description = '基准指数 canonical sec_code'),
  excess_return FLOAT64 OPTIONS(description = '累计超额收益'),
  information_ratio FLOAT64 OPTIONS(description = '信息比率'),
  cost_bps FLOAT64 OPTIONS(description = '回测成本假设，bps'),
  metrics_json STRING OPTIONS(description = '扩展指标 JSON'),
  acceptance_status STRING OPTIONS(description = 'acceptance gate 状态：not_evaluated/rejected/accepted/needs_more_evidence'),
  promotion_status STRING OPTIONS(description = 'promotion 状态：not_promoted/promoted/deprecated'),
  promotion_id STRING OPTIONS(description = '若已 promotion，对应 promotion id；否则为空'),
  approval_ref STRING OPTIONS(description = 'owner approval / PR / issue 引用；未 promotion 时为空'),
  created_date DATE OPTIONS(description = '写入日期，月分区字段'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(created_date, MONTH)
CLUSTER BY strategy_id, model_id, backtest_id
OPTIONS (
  description = 'Research backtest performance summary for unpromoted Strategy1 runs',
  require_partition_filter = FALSE
);

CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_research.research_signal_monitor_daily` (
  strategy_id STRING OPTIONS(description = '策略 id'),
  model_id STRING OPTIONS(description = '候选模型 id'),
  trade_date DATE OPTIONS(description = '监控日，月分区字段'),
  sample_count INT64 OPTIONS(description = '样本数'),
  prediction_count INT64 OPTIONS(description = '预测数'),
  candidate_count INT64 OPTIONS(description = '候选数'),
  avg_score FLOAT64 OPTIONS(description = '平均分数'),
  score_std FLOAT64 OPTIONS(description = '分数标准差'),
  not_tradable_entry_count INT64 OPTIONS(description = '入场不可交易样本数'),
  metrics_json STRING OPTIONS(description = '扩展监控指标 JSON'),
  run_id STRING OPTIONS(description = '监控 run id'),
  research_status STRING OPTIONS(description = '研究生命周期状态：candidate/rejected/accepted/superseded 等'),
  promotion_status STRING OPTIONS(description = 'promotion 状态：not_promoted/promoted/deprecated'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY strategy_id, model_id
OPTIONS (
  description = 'Research daily signal and data-quality monitor for unpromoted model outputs',
  require_partition_filter = TRUE
);

CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_research.research_acceptance_result` (
  acceptance_result_id STRING OPTIONS(description = 'acceptance result id'),
  search_id STRING OPTIONS(description = '候选搜索 id'),
  run_id STRING OPTIONS(description = 'run id'),
  backtest_id STRING OPTIONS(description = '回测 id'),
  model_id STRING OPTIONS(description = '候选模型 id'),
  strategy_id STRING OPTIONS(description = '策略 id'),
  acceptance_gate_version STRING OPTIONS(description = 'acceptance gate 版本'),
  acceptance_contract_version STRING OPTIONS(description = 'acceptance contract 版本'),
  acceptance_contract_sha256 STRING OPTIONS(description = 'acceptance contract 内容 hash'),
  evaluation_start_date DATE OPTIONS(description = '整体评价开始日'),
  evaluation_end_date DATE OPTIONS(description = '整体评价结束日'),
  valid_start_date DATE OPTIONS(description = 'valid 窗口开始日'),
  valid_end_date DATE OPTIONS(description = 'valid 窗口结束日'),
  test_start_date DATE OPTIONS(description = 'test 窗口开始日'),
  test_end_date DATE OPTIONS(description = 'test 窗口结束日'),
  final_holdout_start_date DATE OPTIONS(description = 'final holdout 窗口开始日'),
  final_holdout_end_date DATE OPTIONS(description = 'final holdout 窗口结束日'),
  primary_benchmark_sec_code STRING OPTIONS(description = '主基准指数 canonical sec_code'),
  comparison_benchmarks_json STRING OPTIONS(description = '对比基准 JSON array'),
  acceptance_status STRING OPTIONS(description = 'rejected/accepted/needs_more_evidence 等；accepted 仍属于 research'),
  accepted BOOL OPTIONS(description = 'TRUE 表示 acceptance gate 通过；不代表已 promotion'),
  promotion_status STRING OPTIONS(description = 'not_promoted/promoted/deprecated；accepted 不等于 promoted'),
  promoted BOOL OPTIONS(description = 'TRUE 表示已有 owner-approved promotion manifest 并完成 promotion'),
  promotion_manifest_id STRING OPTIONS(description = '关联 research_promotion_manifest.promotion_id；未 promotion 时为空'),
  metrics_json STRING OPTIONS(description = '结构化评价指标 JSON'),
  reason_json STRING OPTIONS(description = '拒绝 / 通过 / 需更多证据的结构化原因 JSON'),
  artifact_uri STRING OPTIONS(description = 'acceptance artifact URI'),
  approval_ref STRING OPTIONS(description = 'owner approval / PR / issue 引用；未 promotion 时为空'),
  created_date DATE OPTIONS(description = '写入日期，月分区字段'),
  created_at TIMESTAMP OPTIONS(description = '写入时间')
)
PARTITION BY DATE_TRUNC(created_date, MONTH)
CLUSTER BY strategy_id, model_id, backtest_id
OPTIONS (
  description = 'Research acceptance gate and replay results; accepted rows are not promoted unless a promotion manifest exists',
  require_partition_filter = FALSE
);

CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_research.research_experiment_run_status` (
  experiment_id STRING OPTIONS(description = '实验 ID，manifest 内唯一'),
  run_id STRING OPTIONS(description = '当前实验输出 run_id'),
  prediction_run_id STRING OPTIONS(description = '模型 / 预测来源 run_id，retrain 实验等于 run_id，portfolio-only 指向上游'),
  backtest_id STRING OPTIONS(description = '当前实验回测 ID'),
  stage_id STRING OPTIONS(description = '当前实验阶段'),
  experiment_group STRING OPTIONS(description = '实验组'),
  experiment_type STRING OPTIONS(description = '实验类型：portfolio_only / retrain / search'),
  step_id STRING OPTIONS(description = 'runner step'),
  step_display_name STRING OPTIONS(description = 'step 中文或可读名称'),
  status STRING OPTIONS(description = 'step 运行状态：planned / running / succeeded / failed / cancelled'),
  status_reason STRING OPTIONS(description = '状态附加说明，如失败原因摘要（脱敏）'),
  started_at TIMESTAMP OPTIONS(description = 'step 开始时间'),
  finished_at TIMESTAMP OPTIONS(description = 'step 结束时间'),
  created_date DATE OPTIONS(description = '记录创建日期'),
  updated_date DATE OPTIONS(description = '记录最近更新日期，月分区字段'),
  created_at TIMESTAMP OPTIONS(description = '记录创建时间'),
  updated_at TIMESTAMP OPTIONS(description = '记录最近更新时间'),
  job_id STRING OPTIONS(description = 'BigQuery job id / 本地进程 id'),
  attempt INT64 OPTIONS(description = '重试次数，首次为 1'),
  force_replace BOOL OPTIONS(description = '本次是否启用 force replace'),
  lock_key STRING OPTIONS(description = '当前 step 使用的 GCS lock key'),
  lock_owner STRING OPTIONS(description = '当前锁持有者，scheduler instance id'),
  lock_acquired_at TIMESTAMP OPTIONS(description = '锁获取时间'),
  lock_expires_at TIMESTAMP OPTIONS(description = '锁 lease 过期时间'),
  last_heartbeat_at TIMESTAMP OPTIONS(description = '调度器最近一次心跳时间'),
  artifact_uri STRING OPTIONS(description = '当前 step 或实验 artifact 根路径'),
  report_uri STRING OPTIONS(description = 'report artifact URI'),
  diagnosis_uri STRING OPTIONS(description = 'diagnosis artifact URI'),
  diagnosis_status STRING OPTIONS(description = 'diagnosis 状态'),
  qa_status STRING OPTIONS(description = '当前 step / 实验 QA 状态'),
  manifest_path STRING OPTIONS(description = 'manifest 文件路径'),
  manifest_hash STRING OPTIONS(description = 'manifest 内容 hash'),
  params_json STRING OPTIONS(description = '当前实验参数的 JSON 快照'),
  runner_version STRING OPTIONS(description = 'runner 脚本版本或 commit'),
  scheduler_instance_id STRING OPTIONS(description = '调度器实例 ID'),
  cloud_run_job_name STRING OPTIONS(description = 'Cloud Run Job 名称'),
  cloud_run_execution_id STRING OPTIONS(description = 'Cloud Run execution id'),
  cloud_run_task_index INT64 OPTIONS(description = 'Cloud Run task index'),
  container_image STRING OPTIONS(description = 'Cloud Run 容器镜像 tag 或 digest'),
  execution_backend STRING OPTIONS(description = '执行后端，如 cloud_run_sklearn_ledger_v1'),
  model_artifact_uri STRING OPTIONS(description = '模型 artifact GCS URI'),
  preprocess_artifact_uri STRING OPTIONS(description = '预处理 artifact GCS URI'),
  feature_snapshot_uri STRING OPTIONS(description = '训练或预测数据快照 GCS URI'),
  max_parallel_experiments INT64 OPTIONS(description = 'owner 设置或 resolved 后的实验并发数'),
  error_message STRING OPTIONS(description = '脱敏错误摘要')
)
PARTITION BY DATE_TRUNC(updated_date, MONTH)
CLUSTER BY experiment_id, run_id, step_id
OPTIONS (
  description = 'Research experiment orchestration status; run-scoped audit/resume state for unpromoted Strategy1 experiments',
  require_partition_filter = FALSE
);

CREATE TABLE IF NOT EXISTS `data-aquarium.ashare_research.research_promotion_manifest` (
  promotion_id STRING OPTIONS(description = 'promotion id，主键'),
  source_dataset STRING OPTIONS(description = 'source dataset，预期为 ashare_research'),
  source_run_id STRING OPTIONS(description = 'source research run id'),
  source_backtest_id STRING OPTIONS(description = 'source research backtest id'),
  source_model_id STRING OPTIONS(description = 'source research model id'),
  source_artifact_uri STRING OPTIONS(description = 'source research artifact URI'),
  target_dataset STRING OPTIONS(description = 'target dataset，预期为 ashare_ads'),
  target_ads_tables ARRAY<STRING> OPTIONS(description = 'promotion 写入或更新的 ADS 表清单'),
  acceptance_contract_version STRING OPTIONS(description = 'promotion 依据的 acceptance contract 版本'),
  acceptance_contract_sha256 STRING OPTIONS(description = 'promotion 依据的 acceptance contract hash'),
  approval_ref STRING OPTIONS(description = 'owner approval / PR / issue 引用'),
  approved_by STRING OPTIONS(description = '批准人或 owner 标识'),
  approved_at TIMESTAMP OPTIONS(description = '批准时间'),
  source_git_commit STRING OPTIONS(description = 'source run 使用的 git commit'),
  promotion_code_version STRING OPTIONS(description = 'promotion 代码版本'),
  promotion_status STRING OPTIONS(description = 'planned/running/succeeded/failed/cancelled/deprecated'),
  promoted_at TIMESTAMP OPTIONS(description = 'promotion 成功写入 ADS 的时间；未完成时为空'),
  created_date DATE OPTIONS(description = 'manifest 创建日期，月分区字段'),
  created_at TIMESTAMP OPTIONS(description = 'manifest 创建时间')
)
PARTITION BY DATE_TRUNC(created_date, MONTH)
CLUSTER BY promotion_id, source_model_id
OPTIONS (
  description = 'Append-only owner-approved promotion manifest from ashare_research to ashare_ads; D0 defines contract only, promotion job is not implemented',
  require_partition_filter = FALSE
);
