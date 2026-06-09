> 当前交接补充（2026-06-09，GPT-5 Codex）
> - Strategy1 Cloud Run Python live acceptance gate 已在分支 `codex/implement-v3-live-gate` 从 v1 切到 v3。
> - live orchestrator 现在会在 ADS 写回前按实际 backtest span / manifest final_holdout window 重算五指数相对门、复合年化、Sharpe / Calmar 和 final_holdout 诊断字段，并写入 registry、backtest summary 与 comparison artifact。
> - PR #125 分支已完成 2 候选 live v3 smoke：prepare、candidate fanout、select/register/predict、backtest/report、19 QA 和 artifact 上传均 succeeded；smoke 中发现并修复了 `v3_relative_gate_by_benchmark.csv` 的 `search_id` 透传缺口。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - `TODO.md` 已从“完成历史 + 进行中事项混排”重写为短版，只保留当前可执行事项。
> - 当前 TODO 只剩 3 个主动作：OQ-005 补短观察窗记录、OQ-010 继续找 accepted Python baseline、OQ-012 决定是否正式归档关闭。
> - 完成历史不再放在 `TODO.md`，统一回到 `IMPLEMENTATION_STATUS.md` / `AGENT_HANDOFF.md` / `OPEN_QUESTIONS.md`。

> 当前交接补充（2026-06-09，GPT-5 Codex）
> - PR #124 review 指出 active on-call runbook 仍指向已删除的 `ashare-composer`；该问题已处理。
> - `docs/Pipeline-补跑与故障恢复-Runbook.md` 已改写为 Scheduler + Workflows 版恢复手册，当前恢复命令使用 Workflows executions、Scheduler jobs、Cloud Run Jobs 和 BigQuery 状态表。
> - `scripts/alerting/README.md` 与 `scripts/alerting/setup_alerts.py` 也已同步，不再把 alert checker 部署/故障描述指向 Composer。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - OQ-005 已完成 production cutover：生产调度入口固定为 `Cloud Scheduler + Cloud Workflows`，`ashare-composer` 环境已删除，Composer 业务 DAG 不再是现行生产路径。
> - `orchestration/composer/` 已收口为 retired / audit-only 历史目录，只保留审计、迁移对照和受控回滚参考价值。
> - Strategy1 `v3` replay 与 helper 驱动的 `24` QA 已按最新 contract 真执行通过；当前真正开放的主线只剩 OQ-010 可接受 Python baseline 和 OQ-012 是否正式归档。

## 当前交接摘要（2026-06-09）
- OQ-005 当前状态：`ashare-ods-ingestion-daily`（`0 20 * * *`）与 `ashare-pipeline-alert-checker`（`0 * * * *`）两个 Scheduler job 已是唯一生产调度入口，ODS parent -> warehouse child、alert checker、manual full rebuild dry-run 都已有 live smoke 证据。
- OQ-005 代码边界：`orchestration/workflows/**` 是唯一现行调度实现面；`orchestration/composer/**` 只保留历史快照，不再接受新的生产逻辑或运维 runbook 变更。
- Strategy1 当前状态：`v3` acceptance gate replay/QA 已 contract-driven 收口并通过；live Cloud Run Python write-back gate 已在分支切到 v3，待小规模 smoke；当前没有 accepted Python baseline，OQ-010 仍然 open。
- OQ-012 当前状态：schema contract / repair tooling / QA 都已具备，当前 BigQuery 读层无 mismatch 报警；剩余是 owner 是否把该问题正式关闭或保留防复发工程项。

# Agent 交接（Agent Handoff）

本文件只保留当前交接摘要和最近 3 条交接。更早内容已归档到 `archive/AGENT_HANDOFF_2026-06.md`。

> **语言约定（2026-06-01 起）**：新增交接条目一律用中文撰写；更早的英文条目保留在 archive 中，不再放回当前文件。

## 2026-06-09 GPT-5 Codex - Strategy1 live acceptance gate v3 cutover

### 已完成工作

- 将 Cloud Run Python search 默认 acceptance contract 从 `model_acceptance_contract_v1.yml` 切到 `model_acceptance_contract_v3.yml`。
- `orchestrate_sklearn_native_search.py` 在 ADS 写回前接入 v3 replay 已验证的五指数指标计算，按实际 backtest span / manifest final_holdout window 输出候选级 v3 状态和逐指数相对门明细。
- ADS registry / backtest summary 写回新增 v3 contract hash、gate version、primary benchmark、复合年化、Sharpe / Calmar、final_holdout 诊断和五指数相对门摘要。
- `19` QA 改为 v3-aware；`21` risk-feature QA 把旧 risk overlay 限定到 legacy contract。
- 使用 PR #125 分支 smoke 镜像和临时 Cloud Run jobs 跑通 2 候选 live v3 smoke；过程发现 `v3_relative_gate_by_benchmark.csv` 的 `search_id` 列为空，已补 `fetch_topk_ads_outputs` 的 search_id 透传。

### 重要上下文

- owner 已明确后续不再经过 v2；当前切门路径是 v1 -> v3。
- v3 final_holdout 是 diagnostic-only，不再是 hard veto。
- 本轮没有重跑历史 replay，也没有启动新的 Cloud Run search。

### 改动文件

- `configs/strategy1/model_acceptance_contract_v3.yml`
- `configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml`
- `configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml`
- `configs/strategy1/cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_v0.yml`
- `configs/strategy1/cloudrun_python_riskfeat_lgbm_regression_pvfq_n30_bw_h5_v0.yml`
- `scripts/strategy1_cloudrun/acceptance.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql`
- `sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`
- `sql/ml/strategy1/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 已执行 2 候选 Cloud Run live v3 smoke：`search_id=cloudrun_python_lgbm_v3_live_smoke_20260609_01`，`candidate_count=2`，`top_k=1`。
- 结果：prepare matrix、2 个 candidate fanout、select/register/predict、backtest/report、19 QA 和 artifact upload 均 succeeded；Top-K 1 的 native/v3 status 为 `rejected`，原因 `test_top_minus_bottom<=0;no_comparison_benchmark_passed_v3_relative_gate`。
- registry 验证：`acceptance_contract_version=model_acceptance_contract_v3`、`acceptance_gate_version=strategy1_acceptance_gate_v3`、`primary_benchmark_sec_code=000001.SH`、`v3_relative_gate_evaluated_benchmark_count=5`。
- artifact 验证：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/search_id=cloudrun_python_lgbm_v3_live_smoke_20260609_01/v3_relative_gate_by_benchmark.csv` 已生成 5 个 benchmark 明细；本轮修复后后续运行会写出非空 `search_id`。

### 阻塞项

- 无代码阻塞。

### 下一步建议

- 等 PR #125 review；若 reviewer 接受 smoke 证据，可以合并。
- 合并后清理临时 `*-pr125-smoke` Cloud Run jobs 和未提交 smoke manifest。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-08 GPT-5 Codex - OQ-005 direct cutover to Scheduler + Workflows

### 本轮完成

- 新增 `orchestration/workflows/bootstrap_scheduler_iam.sh`，把 `ashare-scheduler-invoker` 与 `ashare-workflows-runtime` 当前真实依赖的 IAM 绑定固化为可重放脚本。
- 重写 `orchestration/workflows/deploy_scheduler_jobs.sh`，统一管理 `ashare-pipeline-alert-checker` 与 `ashare-ods-ingestion-daily` 两个 Scheduler jobs。
- 新增 `orchestration/workflows/cutover_scheduler_jobs.sh`，用于 bootstrap IAM、启用 Scheduler jobs，并保持 Composer 业务 DAG paused。
- 已真实执行 cutover：
  - alert-checker scheduler execution `978c920c-3810-4299-b904-3c954e8d221d` succeeded
  - ODS parent execution `31ac0d61-d40c-4a88-9865-b13f61d369c1` succeeded
  - child warehouse execution `919f2aba-b9d4-4181-9915-fa848487bb90` succeeded
- 两个生产 Scheduler jobs 当前都为 `ENABLED`，caller SA 为 `ashare-scheduler-invoker@data-aquarium.iam.gserviceaccount.com`。

### 本轮未做

- 没有删除 Composer 环境。
- 没有执行真实 full rebuild 写路径。

### 影响文件

- `orchestration/workflows/bootstrap_scheduler_iam.sh`
- `orchestration/workflows/deploy_scheduler_jobs.sh`
- `orchestration/workflows/cutover_scheduler_jobs.sh`
- `orchestration/workflows/README.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 阻塞项

- 无新的技术阻塞。
- OQ-005 现在只剩是否保留短期观测窗口，以及何时删除 Composer 环境。

### 下一步建议

- 若不再需要额外观察窗口，下一步就是删除 Composer 环境，停止固定 `Cloud Composer 3 standard milli DCU-hours` 成本。
- 若仍想保守一点，可先观察下一次自然 scheduled ODS run，再删环境。

Model: GPT-5 Codex

## 2026-06-09 GPT-5 Codex - PR #124 runbook review follow-up

### 已完成工作

- 按 PR #124 review，改写 `docs/Pipeline-补跑与故障恢复-Runbook.md`，把 active recovery path 从 Composer / Airflow 改为 Cloud Scheduler + Cloud Workflows。
- Runbook 现在覆盖 ODS 缺采、endpoint 失败、窗口刷新/QA 失败、backfill、非交易日 skip、Scheduler 触发异常、alert checker 异常和 full rebuild。
- 同步更新 `scripts/alerting/README.md` 与 `scripts/alerting/setup_alerts.py`，避免告警链路文档继续提 Composer DAG / Composer 调度异常。

### 重要上下文

- `orchestration/composer/**` 仍只是历史审计目录。
- 当前 active on-call runbook 是 `docs/Pipeline-补跑与故障恢复-Runbook.md`，它现在应该跟 `orchestration/workflows/**` 保持一致。

### 改动文件

- `docs/Pipeline-补跑与故障恢复-Runbook.md`
- `scripts/alerting/README.md`
- `scripts/alerting/setup_alerts.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- 未执行。此次为文档和告警说明更新，不涉及运行代码路径。

### 阻塞项

- 无。

### 下一步建议

- 继续看 PR #124 是否还有新 comment。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

Model: GPT-5 Codex

## 2026-06-08 GPT-5 Codex - PR #121 review follow-up

### 本轮完成

- `bootstrap_scheduler_iam.sh` 不再给 `ashare-workflows-runtime` 授项目级 `roles/run.developer`；改为对 `ashare-ingest-current-scope` 单授 job-level `roles/run.invoker`，并在脚本里显式移除旧的项目级 `run.developer` 绑定。
- `cutover_scheduler_jobs.sh` 改为更安全的 staged 顺序：先用 `ENABLE_JOBS=false` 创建/更新 paused Scheduler jobs，再 pause Composer 业务 DAG；只有显式 `RESUME_SCHEDULER_JOBS=true` 才会 resume。
- `README.md`、`KNOWN_CONSTRAINTS.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`TODO.md` 已同步更新到新的 least-privilege / staged-cutover 语义。

### 本轮未做

- 没有重新触发 ODS / warehouse scheduler execution。
- 没有处理 review 提到的 lock bucket 前缀最小化问题；当前仍沿用整桶 `roles/storage.objectAdmin`。

### 影响文件

- `orchestration/workflows/bootstrap_scheduler_iam.sh`
- `orchestration/workflows/cutover_scheduler_jobs.sh`
- `orchestration/workflows/README.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 下一步建议

- 运行更新后的 `bootstrap_scheduler_iam.sh`，把 live runtime SA 真的收敛到 job-level `run.invoker`。
- PR 合并后，再单独决定是否要为 lock 前缀拆专用 bucket / IAM condition，随后删除 Composer 环境。

Model: GPT-5 Codex

## 2026-06-08 GPT-5 Codex - Composer historical directory cleanup

### 已完成工作

- 将 `orchestration/composer/README.md` 从“可操作 Composer runbook”改成 retired / audit-only 说明，明确 `ashare-composer` 已删除，当前生产入口只保留 `orchestration/workflows/**`。
- 主动移除了 README 里针对已删除 Composer 环境的同步、触发、变量和手工操作命令，避免后续误操作。
- 给 `orchestration/composer/dags/ashare_common.py` 与 5 个 Composer DAG 顶部都加了 retired 标识，明确这里只保留历史快照，不再接受新的生产逻辑。

### 重要上下文

- 这次没有改任何调度语义，也没有重新部署或 smoke。
- 目标只是收口仓库内“哪些 Composer 资产继续保留、哪些路径已经彻底退出生产”的边界。
- 当前生产入口仍然是 `Cloud Scheduler + Cloud Workflows`，不是 Composer。

### 改动文件

- `orchestration/composer/README.md`
- `orchestration/composer/dags/ashare_common.py`
- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `orchestration/composer/dags/ashare_ods_ingestion_daily.py`
- `orchestration/composer/dags/ashare_pipeline_alert_checker.py`
- `orchestration/composer/dags/ashare_warehouse_full_rebuild.py`
- `orchestration/composer/dags/ashare_warehouse_window_refresh.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未执行。此次为文档/标识清理，不涉及行为变更。

### 阻塞项

- 无。

### 下一步建议

- 若要继续收口 OQ-005，可补一条 cutover 后短观察窗记录，然后把这部分也归档到 OQ-005 完成态。
- 若后续还要碰调度实现，直接改 `orchestration/workflows/**`，不要再在 Composer 目录叠加新逻辑。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-08 GPT-5 Codex - TODO cleanup

### 已完成工作

- 将 `TODO.md` 从长版状态流水重写为短版行动清单。
- 删除已完成历史、重复背景和大量上下文，只保留当前仍需执行的事项。
- 保留的主线现在只有：OQ-005 补短观察窗记录、OQ-010 accepted Python baseline、OQ-012 关闭/保留决策，以及少量 P1 优化项。

### 重要上下文

- 这次没有改代码、没有改调度语义，只是收口任务视图。
- 历史完成记录统一以 `IMPLEMENTATION_STATUS.md` / `AGENT_HANDOFF.md` 为准，不再堆在 `TODO.md` 里。

### 改动文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- 未执行。此次为任务清单精简，不涉及行为变更。

### 阻塞项

- 无。

### 下一步建议

- 若继续收口 OQ-005，先补 cutover 后短观察窗记录。
- 若转回策略主线，直接继续 OQ-010 accepted baseline 探索。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex
