-- BigQuery Standard SQL
-- OQ-010: strategy1_experiment_run_status
-- 实验并发调度状态表，记录每个 step 的调度生命周期、锁状态和审计信息。
-- 该表只用于审计追踪和 resume 输入，不承担低延迟锁管理职责。
-- 锁的原语是 GCS object create-if-not-exists (ifGenerationMatch=0)。
-- 本脚本幂等：CREATE OR REPLACE TABLE 重建 schema。

CREATE OR REPLACE TABLE `data-aquarium.ashare_meta.strategy1_experiment_run_status` (
  -- 实验身份
  experiment_id STRING NOT NULL OPTIONS(description="实验 ID，manifest 内唯一"),
  run_id STRING NOT NULL OPTIONS(description="当前实验输出 run_id"),
  prediction_run_id STRING OPTIONS(description="模型 / 预测来源 run_id，retrain 实验等于 run_id，portfolio-only 指向上游"),
  backtest_id STRING OPTIONS(description="当前实验回测 ID，05-12 相关步骤必填"),
  stage_id STRING OPTIONS(description="当前实验阶段，如 stage_a / stage_b"),
  experiment_group STRING OPTIONS(description="实验组，如 portfolio_concentration / rebalance_frequency"),
  experiment_type STRING OPTIONS(description="实验类型：portfolio_only / retrain"),

  -- step 标识
  step_id STRING NOT NULL OPTIONS(description="runner step，如 01_build_training_panel / 08_run_backtest"),
  step_display_name STRING OPTIONS(description="step 中文或可读名称"),

  -- 状态
  status STRING NOT NULL OPTIONS(description="step 运行状态：planned / running / succeeded / failed / cancelled"),
  status_reason STRING OPTIONS(description="状态附加说明，如失败原因摘要（脱敏）"),

  -- 时间戳
  started_at TIMESTAMP OPTIONS(description="step 开始时间"),
  finished_at TIMESTAMP OPTIONS(description="step 结束时间"),
  created_at TIMESTAMP NOT NULL OPTIONS(description="记录创建时间"),
  updated_at TIMESTAMP NOT NULL OPTIONS(description="记录最近更新时间"),

  -- 执行跟踪
  job_id STRING OPTIONS(description="BigQuery job id / 本地进程 id"),
  attempt INT64 OPTIONS(description="重试次数，首次为 1"),
  force_replace BOOL OPTIONS(description="本次是否启用 force replace"),

  -- 锁信息
  lock_key STRING OPTIONS(description="当前 step 使用的 GCS lock key"),
  lock_owner STRING OPTIONS(description="当前锁持有者，scheduler instance id"),
  lock_acquired_at TIMESTAMP OPTIONS(description="锁获取时间"),
  lock_expires_at TIMESTAMP OPTIONS(description="锁 lease 过期时间"),
  last_heartbeat_at TIMESTAMP OPTIONS(description="调度器最近一次心跳时间"),

  -- 产物
  artifact_uri STRING OPTIONS(description="当前 step 或实验 artifact 根路径"),
  report_uri STRING OPTIONS(description="report artifact URI"),
  diagnosis_uri STRING OPTIONS(description="diagnosis artifact URI"),
  diagnosis_status STRING OPTIONS(description="diagnosis 状态"),

  -- QA 与清单
  qa_status STRING OPTIONS(description="当前 step / 实验 QA 状态"),
  manifest_path STRING OPTIONS(description="manifest 文件路径"),
  manifest_hash STRING OPTIONS(description="manifest 内容 hash"),
  params_json STRING OPTIONS(description="当前实验参数的 JSON 快照"),
  runner_version STRING OPTIONS(description="runner 脚本版本或 commit"),
  scheduler_instance_id STRING OPTIONS(description="调度器实例 ID"),

  -- 日志
  log_dir STRING OPTIONS(description="本地调度日志目录路径"),
  error_message STRING OPTIONS(description="脱敏错误摘要")
)
OPTIONS (
  description = 'OQ-010 策略 1 实验并发调度状态表。记录每个实验 step 的调度生命周期、锁、审计与产物信息。该表只用于审计追踪和 resume 输入，不承担低延迟锁管理职责；锁原语是 GCS object create-if-not-exists (ifGenerationMatch=0)。'
);

-- 分区与聚簇
ALTER TABLE `data-aquarium.ashare_meta.strategy1_experiment_run_status`
SET OPTIONS (
  partition_expiration_days = 365
);
