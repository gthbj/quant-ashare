> 当前交接补充（2026-06-11，GPT-5 Codex）
> - PRD 分支实现收口中：实现工作树 `/Users/fisher/Desktop/git/quant-ashare-annual-pipeline-impl` 从 PRD 分支派生，最终按 owner 要求 fast-forward 回 `codex/prd-annual-rolling-pipeline-scheduler`。
> - 新增 package entrypoint `quant_ashare.strategy1.annual_pipeline_scheduler`，实现年度滚动 pipeline scheduler Phase 1 dry-run；只输出 DAG / lock / state / resource plan，不执行 Cloud Run / BigQuery / GCS 写入。
> - PR #161 review follow-up 已补：dry-run 输出 `simulation_model=synchronous_waves`，峰值标记为 reference 而非 live capacity ceiling；fanout 计数声明为 candidate-year proxy；`--no-tail-fill-single-task` 的 deferred batch 不再误记 succeeded。
> - 新增测试覆盖年度 DAG、scheduler lock ownership、candidate 饱和阻止 prepare、GCS state generation mismatch、deferred batch 和 CLI dry-run JSON；catalog caller / package boundary / runbook 已同步。
> - 后续建议：PR #161 合并后进入 Phase 2 candidate-only live smoke，先用 2 年 * 2-3 candidate unit 验证真实状态恢复、artifact skip 和 Cloud Run execution 粒度 fanout 统计。

Model: GPT-5 Codex

## 2026-06-11 GPT-5 Codex - Annual pipeline scheduler Phase 1 dry-run

### 已完成工作

- 新增 `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`，实现 PRD Phase 1 dry-run package entrypoint。
- Scheduler 复用年度 rolling experiment/window 生成逻辑，输出 2021-2026 跨年度 DAG；本年 `select` 强依赖本年 11/11 candidate，下一年 `panel` / `matrix` 不依赖上一年 `select`。
- Dry-run 输出 scheduler-level GCS generation-guarded lease lock、GCS state generation-conditioned write 模型、stage token 表和资源模拟。
- 资源模型明确 candidate `2 CPU / 8Gi`、prepare `8 CPU / 32Gi`、select/backtest `4 CPU / 16Gi` 共用 `40 CPU / 160Gi` 全局资源池；单测覆盖 20 个 candidate running 时 prepare 不可 admission。
- PR #161 review follow-up：`simulation_model=synchronous_waves` 与 `peak_resource_usage_semantics=synchronous_wave_reference_not_live_capacity_ceiling` 已进入输出；fanout execution accounting 明确 Phase 1 为 candidate-year proxy；deferred candidate batch 不再标记 succeeded。
- 更新 `configs/strategy1/active_step_catalog.yml` caller、`docs/策略1CloudRun训练回测运行手册.md` 和相关测试。

### 重要上下文

- 本轮仍是 Phase 1：不启动 Cloud Run，不读写 BigQuery / GCS，不修改 job spec / IAM；dry-run 资源峰值只用于 admission 自检，不代表 live overlap 的容量上限。
- Owner 已要求不要单独开实现 PR；完成后把实现合回 `codex/prd-annual-rolling-pipeline-scheduler` / PR #161。
- Phase 2 live scheduler 必须按真实 Cloud Run execution 粒度统计 active fanout，而不能沿用 Phase 1 的 candidate-year proxy。

### 改动文件

- `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`
- `tests/strategy1/test_annual_pipeline_scheduler.py`
- `tests/strategy1/test_package_boundaries.py`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `configs/strategy1/active_step_catalog.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1 tests/strategy1_cloudrun`：98 passed。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.annual_pipeline_scheduler --start-year 2021 --end-year 2026 --run-version v20260611_followup --dry-run`：输出 `simulation_model=synchronous_waves`、`fanout_model=candidate_year_proxy`、`deferred_task_count=0`，峰值 `38 CPU / 152Gi / 11 candidate_slots`；该峰值是 synchronous wave reference，不是 live capacity ceiling。

### 阻塞项

- 无。

### 下一步建议

- 推回 PR #161 后 review。
- 合并后再做 Phase 2 candidate-only live smoke，并把 active fanout 计数从 candidate-year proxy 改为 Cloud Run execution 粒度。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - Annual rolling pipeline scheduler PRD

Model: GPT-5 Codex

### 已完成工作

- 在新 worktree `/Users/fisher/Desktop/git/quant-ashare-annual-pipeline-prd`、分支 `codex/prd-annual-rolling-pipeline-scheduler` 中新增年度滚动并发调度 PRD。
- PRD 定义从按年份串行执行升级为跨年份流水线调度：`build_training_panel`、`prepare_matrix` 和 candidate fanout 可跨年度并发；本年 `select_register_predict` 仍必须等本年全部候选成功。
- PRD 固化默认资源上限：全局 candidate task 并发 `20`，candidate task `2 CPU / 8Gi`，并把 prepare、select、backtest/report 纳入资源 token 模型。
- PR #161 review follow-up 已补齐两个 Medium 设计缺口：scheduler 必须持有 generation-guarded GCS lease lock 才能提交 execution，且 GCS state JSON 写入必须使用 generation precondition；prepare `8 CPU / 32Gi`、select `4 CPU / 16Gi`、backtest `4 CPU / 16Gi` 与 candidate 共享 `40 CPU / 160Gi` 全局 token 池。
- PRD 定义 scheduler 必须可 dry-run、可恢复、可按 `(year, unit_index)` 跟踪状态，并对 `gcloud --wait` / Cloud Run 控制面超时做 execution / task / GCS artifact 二次确认。
- 同步更新 `TODO.md` 和 `.agent/memory/IMPLEMENTATION_STATUS.md`。

### 重要上下文

- 2026-06-10 年度滚动实跑观察显示，每年候选训练中 `unit_index=6` 明显拖尾；该候选是 `risk_lgbm_prd_attack_lr005_n600_l63_lr005_n600_leaf800_ff07_bf09_l1_1_l2_1`，`n_estimators=600`、`num_threads=1`。
- 不能在本年 unit6 未完成时提前跑本年 select，否则会把 unit6 排除在年度选参之外，破坏实验口径。
- 可以在上一年慢候选仍 running 时启动下一年 training panel、prepare matrix 和候选训练，只要全局资源预算允许。
- Cloud Run `parallelism` 只限制单 execution；年度 pipeline scheduler 必须自己维护全局资源池和 scheduler 实例互斥，不能靠 job spec 防止跨 execution 超配额或重复提交。
- 正式年度滚动结果仍必须来自单一 continuous ledger 或通过 resume-continuous QA 的 segment ledger；年度 fresh backtest 只作 diagnostic。

### 改动文件

- `docs/prd/PRD_20260611_01_策略1年度滚动并发调度.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 文档只读校验：对照现有年度滚动 PRD、年度执行工程化 PRD、annual rolling orchestrator、`pipeline_control.build_task_fanout_steps`、`annual_rolling_lgbm_regression_v0.yml`。
- 未运行 BigQuery、Cloud Run、Dataform 或 pytest；本轮不改代码。

### 阻塞项

- 无。

### 下一步建议

- 若 owner 确认 PRD，下一步实现 Phase 1：scheduler dry-run，输出跨年度 DAG、资源峰值和预计提交顺序。
- Phase 1 完成后再做 2 年 * 2-3 candidate unit 的 candidate-only live smoke，验证部分 batch、恢复和 artifact skip。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - Strategy1 main image deploy after PR #159

### 已完成工作

- 从当前 `main@f30c1716a55995d169955e1a7c4663d39b82a382` 构建正式 Strategy1 runner 镜像。
- 使用一次性 Cloud Build config，只推固定 tag `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:annual-plan-main-f30c171-20260610-01`，未更新 `latest`。
- Cloud Build `4dfba35e-cbaf-4727-9596-137010c9d6ea` succeeded，镜像 digest 为 `sha256:b856f46f56ad5b9a9cd9ac8773e67090f702a06ff8931ca51e1d2e3bb24299d7`。
- 将五个正式 Strategy1 Cloud Run jobs 更新到该 immutable digest：
  - `strategy1-train-predict-job`
  - `strategy1-prepare-matrix-job`
  - `strategy1-train-candidate-fanout-job`
  - `strategy1-select-register-predict-job`
  - `strategy1-backtest-report-job`
- 读回确认五个 jobs 的 command/args 仍为 `python -m quant_ashare.strategy1.*` package entrypoint，SA 仍为 `241358486859-compute@developer.gserviceaccount.com`，`maxRetries=0`，CPU/memory/timeout 保持不变；fanout 仍为 `taskCount=40`、`parallelism=20`。
- 跑通五个正式 jobs 的只读 `--help` boot smoke，并在 Cloud Logging 确认每个 execution 输出 `usage:`。
- 按 owner 要求清理项目记忆：将旧 active `AGENT_HANDOFF.md` 归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`，当前 handoff 只保留本次部署交接。
- PR #160 review follow-up：把 Strategy1 runner image digest 从长期约束中移除，改为引用 `IMPLEMENTATION_STATUS.md` 最新部署记录。

### 重要上下文

- 本轮只更新五个普通 Strategy1 runner jobs 的 image；没有更新 `strategy1-promote-research-to-ads-job`。
- 本轮没有执行 BigQuery 写入，也没有启动年度滚动真实运行。
- 当前线上五个 Strategy1 jobs 已包含 PR #159 的 annual rolling training panel plan 和 `quant_ashare.strategy1.sql_runner` package CLI。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

### 测试 / 验证

- Cloud Build `4dfba35e-cbaf-4727-9596-137010c9d6ea`：SUCCESS。
- `gcloud run jobs describe` 读回五个 jobs：image 均为 `sha256:b856f46f56ad5b9a9cd9ac8773e67090f702a06ff8931ca51e1d2e3bb24299d7`，args / resources / SA / retries / fanout 并发均保持预期。
- `strategy1-train-predict-job-gwpn7`：Completed=True，Cloud Logging 匹配 `usage: train_predict.py`。
- `strategy1-prepare-matrix-job-rjgzf`：Completed=True，Cloud Logging 匹配 `usage: prepare_matrix.py`。
- `strategy1-train-candidate-fanout-job-njl4q`：Completed=True，本次 smoke 用 `--tasks=1`，Cloud Logging 匹配 `usage: train_candidate_task.py`。
- `strategy1-select-register-predict-job-njmxd`：Completed=True，Cloud Logging 匹配 `usage: select_register_predict.py`。
- `strategy1-backtest-report-job-jj7ng`：Completed=True，Cloud Logging 匹配 `usage: backtest_report.py`。
- `git diff --check`：通过。

### 阻塞项

- 无。

### 下一步建议

- 执行完整 `2021-2026` 年度滚动选参实验。
- 正式结果必须来自单一 continuous ledger，或经过 resume-continuous QA 的 segment ledger；不要拼接年度 fresh-run NAV。
- 若年度滚动结果接近可接受，再按 promotion runbook 先 review-only 后 owner-approved `--execute`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`
