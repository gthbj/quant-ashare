> 当前交接补充（2026-06-08，GPT-5 Codex）
> - OQ-005 已完成 production cutover：生产调度入口固定为 `Cloud Scheduler + Cloud Workflows`，`ashare-composer` 环境已删除，Composer 业务 DAG 不再是现行生产路径。
> - `orchestration/composer/` 已收口为 retired / audit-only 历史目录，只保留审计、迁移对照和受控回滚参考价值。
> - Strategy1 `v3` replay 与 helper 驱动的 `24` QA 已按最新 contract 真执行通过；当前真正开放的主线只剩 OQ-010 可接受 Python baseline 和 OQ-012 是否正式归档。

## 当前交接摘要（2026-06-08）
- OQ-005 当前状态：`ashare-ods-ingestion-daily`（`0 20 * * *`）与 `ashare-pipeline-alert-checker`（`0 * * * *`）两个 Scheduler job 已是唯一生产调度入口，ODS parent -> warehouse child、alert checker、manual full rebuild dry-run 都已有 live smoke 证据。
- OQ-005 代码边界：`orchestration/workflows/**` 是唯一现行调度实现面；`orchestration/composer/**` 只保留历史快照，不再接受新的生产逻辑或运维 runbook 变更。
- Strategy1 当前状态：`v3` acceptance gate replay/QA 已 contract-driven 收口并通过；当前没有 accepted Python baseline，OQ-010 仍然 open。
- OQ-012 当前状态：schema contract / repair tooling / QA 都已具备，当前 BigQuery 读层无 mismatch 报警；剩余是 owner 是否把该问题正式关闭或保留防复发工程项。

# Agent 交接（Agent Handoff）

本文件只保留当前交接摘要和最近 3 条交接。更早内容已归档到 `archive/AGENT_HANDOFF_2026-06.md`。

> **语言约定（2026-06-01 起）**：新增交接条目一律用中文撰写；更早的英文条目保留在 archive 中，不再放回当前文件。

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
