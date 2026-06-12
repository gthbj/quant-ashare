> 当前交接摘要（2026-06-12，GPT-5.5，PRD_20260612_05 Batch 3）
> - `codex/prd05-batch3` 已完成 Batch 3 代码与测试：`feature_sets.py` / `preprocess.py` / `training_panel.py` 迁入 `src/quant_ashare/strategy1/`，scripts 同名路径保留兼容 shim。
> - `annual_pipeline_scheduler.py` 不再 import 脚本 orchestrator；年度滚动计划层已抽到 `quant_ashare.strategy1.annual_rolling_plan`，旧 `orchestrate_annual_rolling_selection.py` 保留 CLI 主体并 re-export 计划函数。
> - `tests/strategy1/test_package_boundaries.py` 已把 src→`scripts.strategy1_cloudrun.*` 反向 import 改为硬断言 0，并新增非仓库 cwd / `PYTHONPATH=src` 的全包 import 自洽测试。
> - 本轮未触碰 Cloud Run job spec/args/镜像/IAM，未写 BigQuery/GCS；全量验证已通过，PR #206 已创建。
>
> Model: GPT-5.5

## 2026-06-12 GPT-5.5 - PRD_20260612_05 Batch 3 package cleanup

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-prd05-b3`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/prd05-batch3`
Run ID: N/A
相关 issue/PR: PRD `docs/prd/PRD_20260612_05_Strategy1包结构PhaseE收尾.md`；PR #206

### 已完成工作

- 将 `scripts/strategy1_cloudrun/feature_sets.py`、`preprocess.py`、`training_panel.py` 迁移到 `src/quant_ashare/strategy1/`，scripts 侧改为 thin re-export shim。
- 将 src 内对 `scripts.strategy1_cloudrun.feature_sets` / `preprocess` 的 import 改为包内直连；Batch 3 后 src→`scripts.strategy1_cloudrun.*` 反向 import 为 0。
- 新增 `src/quant_ashare/strategy1/annual_rolling_plan.py`，承载 annual rolling 计划层常量和 helper；scheduler 与脚本 orchestrator 均改从该模块 import。
- 更新 `tests/strategy1/test_package_boundaries.py` 的 Batch 3 兼容符号快照、硬断言 src 不导入 scripts，并新增非仓库 cwd / `PYTHONPATH=src` 的 package self-contained import 测试。
- 同步 `KNOWN_CONSTRAINTS.md` 兼容层条款、`docs/prd/PRD_20260610_02_项目结构重构方案.md` Phase E 状态注记、`IMPLEMENTATION_STATUS.md` 和 `TODO.md`。

### 重要上下文

- 本轮严格只做 PRD Batch 3；两个脚本 orchestrator 仍保留 CLI 主体和兼容导入面。
- `orchestrate_annual_rolling_selection.py` 的 CLI 参数面、dry-run JSON 输出路径和非 dry-run 拒绝行为保持不变；迁出的计划函数通过脚本顶层 import 继续兼容旧测试/调用方。
- 旧 `scripts.strategy1_cloudrun.feature_sets` / `preprocess` / `training_panel` 路径仍是合法兼容 shim，不应加入 retired-reference ban-list。
- 本轮未改训练、回测、ledger、Cloud Run job spec、args、镜像或 IAM；未写 BigQuery/GCS。

### 改动文件

- `src/quant_ashare/strategy1/feature_sets.py`
- `src/quant_ashare/strategy1/preprocess.py`
- `src/quant_ashare/strategy1/training_panel.py`
- `src/quant_ashare/strategy1/annual_rolling_plan.py`
- `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`
- `scripts/strategy1_cloudrun/feature_sets.py`
- `scripts/strategy1_cloudrun/preprocess.py`
- `scripts/strategy1_cloudrun/training_panel.py`
- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`
- 相关 `src/quant_ashare/strategy1/*.py` import
- `tests/strategy1/test_package_boundaries.py`
- `docs/prd/PRD_20260610_02_项目结构重构方案.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests`：276 passed。
- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_package_boundaries.py`：7 passed。
- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_cloudrun_package_entrypoints.py`：16 passed。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：passed。
- `python3 -m compileall -q src scripts tests`：passed。
- `git diff --check`：passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：passed。

### 阻塞项

- 无。

### 下一步建议

- 等待 Claude review；认可的 comment 在本分支修复，不认可的在 PR comment 说明理由。
- 若合并前 `origin/main` 有新提交，rebase 后重跑关键验证。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

## 2026-06-12 GPT-5.5 - dividend ODS backfill and CA resume

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-div-backfill`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/dividend-backfill-resume`
Run ID: `s1_dividend_backfill_resume_20260528_20260609_v20260612_01`
相关 issue/PR: PR #202 comment `4692136310`；PR #205

### 已完成工作

- 新增独立 dividend backfill manifest / endpoint group，并让 `current_scope` alias 显式排除 `dividend_backfill`，避免每日调度捡走 dividend。
- 构建 ingestion image `sha256:35acbc363408d05dd758d70ba5f293e8b0d333a000c6dfe8e8143ddadd0b8bba` 后，用 Cloud Run job `ashare-ingest-current-scope` 补采 `2026-05-28..2026-06-12` 12 个 SSE 开市日。
- 重建 `sql/dwd/12_dwd_stock_dividend_event.sql` 与 `sql/qa/14_corporate_action_event_checks.sql`；QA-CA-EVENT-1..6 通过。
- 从 parent `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01` 的 `2026-05-27` state resume 到 child `bt_s1_dividend_backfill_resume_20260528_20260609_v20260612_01`，Cloud Run execution `strategy1-backtest-report-job-tjn4j` 成功。
- 新增交付报告 `docs/分析-dividend-ODS补采与CA-Resume补跑-20260612.md`，包含补采执行记录、QA、差异归因表和拼接指标。

### 重要上下文

- child 只写 `ashare_research`；ADS nav/trade/position/state/summary 与 promotion manifest 反查均为 0 行。不得 promotion，不标 accepted。
- `qa_cloudrun_ledger_resume_outputs` 现有 catalog SQL 后半段仍包含 parent/child 等值断言；本轮 full run 预期失败于 `Full and resume NAV metrics differ`，结构 subset 8 个 ASSERT 通过。
- 差异归因闭合：新增 `002756.SZ` 2026-05-29 与 `001314.SZ` 2026-06-02 两条现金分红，税前 `76.0`、税 `7.6`、净现金 `68.4`；position/share 差异 0，非 CA 仅两条未成交 planned_shares 尾差且现金影响 0。
- 拼接 parent NAV `2021-01-04..2026-05-27` + child NAV `2026-05-28..2026-06-09` 后，CAGR=`0.15357789449949522`、contract Sharpe=`0.668539787795112`、Calmar=`0.41030930550903105`、MaxDD=`-0.3742978588042647`。本轮不改 `DECISION-20260612-03` 文本。
- 采纳结论：Claude review 已通过 PR #205 技术面，owner 预先决策影响很小则采纳；本轮展示数字修正采纳为 CAGR `15.36%` (`0.153578`) / contract Sharpe `0.6685` / Calmar `0.4103` / MaxDD 不变，`DECISION-20260612-03` 文本不改。

### 改动文件

- `configs/ingestion/ods_dividend_backfill_v0.yml`
- `configs/ingestion/schema_contracts/dividend.json`
- `configs/ods_schema_contracts/dividend.yml`
- `scripts/ingestion/endpoints/corporate_actions.py`
- `scripts/ingestion/common/endpoint_runner.py`
- `scripts/ingestion/run_ingestion_job.py`
- `tests/ingestion/test_dividend_backfill_manifest.py`
- `docs/分析-dividend-ODS补采与CA-Resume补跑-20260612.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/ingestion/test_dividend_backfill_manifest.py`：2 passed。
- local dry-run：dividend backfill plan 使用 `partition_endpoint=dividend`、`partition_date=20260528`、GCS prefix `api=dividend/endpoint=dividend/partition_date=20260528/`。
- local current_scope dry-run：27 个 endpoint partitions，无 dividend。
- ODS backfill 后 `2026-05-28..2026-06-12` 共 `1215` 行，2024/2025 同期 `1182`/`1184` 行；ingestion meta `12` 条 success。
- dwd/12 job `manual_dividend_dwd12_rebuild_20260612_01`；qa/14 job `manual_dividend_ca_event_qa_20260612_01`，QA-CA-EVENT-1..6 通过。
- resume child Cloud Run execution `strategy1-backtest-report-job-tjn4j` 成功，research NAV/state 各 9 行，summary metadata 匹配 parent / CA / resume 参数。
- QA：`qa_lot_aware_ledger_outputs` job `b697f4dc-1eaf-4eff-9df1-23e04fb809ac` passed；`qa_corporate_action_ledger_outputs` job `beefe3d8-0022-4aa9-a224-37eb82931760` passed；cloudrun resume structure subset job `bqjob_r8fe2168bb9d0164_0000019ebc5bb4d6_1` passed。
- ADS nav/trade/position/state/summary 反查 0 行，`research_promotion_manifest` 0 行。

### 阻塞项

- 无。

### 下一步建议

- 合并前 rebase 到最新 `origin/main`，冲突按 main 最新记忆结构重新并入本 PR 条目与 baseline 数字修正。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

## 2026-06-12 GPT-5.5 - PRD_20260612_05 Batch 2 package cleanup

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-prd05-b2`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/prd05-batch2`
Run ID: N/A
相关 issue/PR: PRD `docs/prd/PRD_20260612_05_Strategy1包结构PhaseE收尾.md`；PR #204

### 已完成工作

- 将 `scripts/strategy1_cloudrun/state.py` 与 `task_fanout.py` 迁移到 `src/quant_ashare/strategy1/`，scripts 侧改为 thin re-export shim。
- 将 src 内对 `scripts.strategy1_cloudrun.state` / `task_fanout` 的 import 改为包内直连；Batch 2 后反向 import 只剩 `feature_sets` / `preprocess` / `orchestrate_annual_rolling_selection`。
- `annual_pipeline_scheduler.py` 复用迁入后的 `_is_precondition_error` / `_is_not_found_error` / `utc_now` / `describe_cloud_run_execution`，统一 `GcloudExecutionClient.describe` 并恢复失败路径 warning。
- 为 `GcsLeaseLock` / `GcsSchedulerLease` / `PipelineStateStore` 补锁语义出处 docstring；未合并各自 reclaim / heartbeat 语义。
- 新增 `tests/strategy1/test_gcs_leases.py`，并更新 `tests/strategy1/test_package_boundaries.py` 的 Batch 2 兼容符号快照与反向 import 计数断言。

### 重要上下文

- 本轮严格只做 PRD Batch 2；`feature_sets` / `preprocess` / `training_panel` / `orchestrate_annual_rolling_selection` 留给 Batch 3。
- `GcloudExecutionClient.describe` 恢复失败 `LOGGER.warning` 是本 Batch 唯一允许的行为差异修复。
- 旧 `scripts.strategy1_cloudrun.state` / `task_fanout` 路径仍是合法兼容 shim，不应加入 retired-reference ban-list。
- 本轮未改训练、回测、ledger、Cloud Run job spec、args、镜像或 IAM；未写 BigQuery/GCS。

### 改动文件

- `src/quant_ashare/strategy1/state.py`
- `src/quant_ashare/strategy1/task_fanout.py`
- `scripts/strategy1_cloudrun/state.py`
- `scripts/strategy1_cloudrun/task_fanout.py`
- `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`
- 相关 `src/quant_ashare/strategy1/*.py` import
- `scripts/pipeline_control/state.py`
- `tests/strategy1/test_annual_pipeline_scheduler.py`
- `tests/strategy1/test_gcs_leases.py`
- `tests/strategy1/test_package_boundaries.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests`：275 passed。
- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_package_boundaries.py`：6 passed。
- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_cloudrun_package_entrypoints.py`：16 passed。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：passed。
- `python3 -m compileall -q src scripts tests`：passed。
- `git diff --check`：passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：passed。

### 阻塞项

- 无。

### 下一步建议

- 等待 Claude review；认可的 comment 在本分支修复，不认可的在 PR comment 说明理由。若合并前 `origin/main` 有新提交，rebase 后重跑关键验证。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

