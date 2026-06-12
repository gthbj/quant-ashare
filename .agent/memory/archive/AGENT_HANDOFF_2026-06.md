# Agent Handoff Archive 2026-06

本文件归档 2026-06 的历史交接条目。当前交接摘要和最近交接见 `../AGENT_HANDOFF.md`。

## 2026-06-13 GPT-5.5 - ingestion meta incident follow-up

日期: 2026-06-13
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-meta-incident`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/ingestion-meta-incident`
Run ID: N/A
相关 issue/PR: PR #196 事故修复复核；本分支待创建 PR

### 已完成工作

- 只读复核 `ashare-ingest-current-scope` job spec、execution image digest 历史、Cloud Build / Artifact Registry、git ingestion 代码演进、BigQuery `ingestion_run` / `ingestion_partition_status` 行分布和 alert checker 覆盖面。
- 新增事故报告 `docs/分析-ingestion-meta-0行事故排查-20260613.md`，记录根因链、时间线、当前镜像状态、历史缺口处置建议和 2026-06-13 / 2026-06-15 验证计划。
- 在 `sql/observability/01_pipeline_status_views.sql` 新增 `v_ingestion_meta_missing`，并把 `alert_type='ingestion_meta_missing'` 接入 `v_alert_summary`。
- 在 `scripts/alerting/setup_alerts.py` 新增 `ashare_pipeline_ingestion_meta_missing` log metric 和 `Ashare Pipeline: Ingestion Meta Missing` policy；同步更新 alert README 与 active runbook。
- 新增 `tests/alerting/test_ingestion_meta_missing_alert.py`，固定 SQL、setup 和 README 的告警接线。

### 重要上下文

- 当前 job spec image 仍是 `ingestion:latest`，不是 digest pin；execution 创建时解析 tag。本轮确认 2026-06-12 scheduled current_scope execution `ashare-ingest-current-scope-9wnh8` 使用修复镜像 `sha256:5c78e8624584e9ee47471be087ba7e4090d00477a37ec276920f8696810c3f3b` 并落 27 条 meta。
- Artifact Registry 当前 `latest` 指向 dividend 补采镜像 `sha256:35acbc363408d05dd758d70ba5f293e8b0d333a000c6dfe8e8143ddadd0b8bba`；该镜像后续 dividend executions 已实证写 meta。本轮无需、也未执行生产 job 更新。
- 2026-06-13 是周六，SSE `is_open=0`；20:00 CST scheduled workflow 应走非交易日 gate，不会触发 live ingestion，不应期待 20260613 meta 行。下一次 live meta 验证应看 2026-06-15 20:00 CST 后的 current_scope 行。
- 历史 2026-06-09/10/11 meta 缺口建议不回填，保留报告/PR/Cloud Run/pipeline status 作为审计记录，避免混淆真实运行时审计与事后重建记录。

### 改动文件

- `docs/分析-ingestion-meta-0行事故排查-20260613.md`
- `sql/observability/01_pipeline_status_views.sql`
- `scripts/alerting/setup_alerts.py`
- `scripts/alerting/README.md`
- `docs/Pipeline-补跑与故障恢复-Runbook.md`
- `tests/alerting/test_ingestion_meta_missing_alert.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

### 测试 / 验证

- `bq query --project_id=data-aquarium --location=asia-east2 --use_legacy_sql=false --dry_run < sql/observability/01_pipeline_status_views.sql`：validated。
- `python3 -m pytest -q tests/alerting/test_ingestion_meta_missing_alert.py`：1 passed。
- `python3 scripts/alerting/setup_alerts.py --dry-run`：新 metric/policy 可见。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：passed。
- `git diff --check`：passed。

### 阻塞项

- 无。

### 下一步建议

- PR 合并并部署观测 SQL / alert policy 后，2026-06-15 20:00 CST 后复核 `v_ingestion_meta_missing` 为空、`ingestion_run` 有 20260615 current_scope 行。
- 2026-06-13 20:00 CST 只验证非交易日 gate；若触发 live ingestion，反而需要按非交易日 gate 异常处理。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
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

## 2026-06-12 GPT-5.5 - PRD_20260612_05 Batch 1 package cleanup

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-prd05-b1`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/prd05-batch1`
Run ID: N/A
相关 issue/PR: PRD `docs/prd/PRD_20260612_05_Strategy1包结构PhaseE收尾.md`；PR #203

### 已完成工作

- 将 `scripts/strategy1_cloudrun/bq_io.py` 与 `config.py` 迁移到 `src/quant_ashare/strategy1/`，scripts 侧改为 thin re-export shim。
- 新增 `src/quant_ashare/strategy1/runner_version.py`，保持 `strategy1_cloudrun_runner_v0_20260606_lot100` 值不变，并让 `scripts.strategy1_cloudrun.__version__` 从 src re-export。
- 将 src 内对 `scripts.strategy1_cloudrun.bq_io` / `config` / `dataset_roles` / `acceptance` / `__version__` 的 import 改为包内直连。
- 在 `tests/strategy1/test_package_boundaries.py` 固化 Batch 1 兼容符号快照与反向 import 计数断言。

### 重要上下文

- 本轮严格只做 PRD Batch 1；`state` / `task_fanout` / `feature_sets` / `preprocess` / `training_panel` / `orchestrate_annual_rolling_selection` 留给 Batch 2/3。
- 旧 `scripts.strategy1_cloudrun.bq_io` / `config` 路径仍是合法兼容 shim，不应加入 retired-reference ban-list。
- 本轮未改训练、回测、ledger、orchestrator 调度语义；未触碰 Cloud Run job spec、args、镜像或 IAM；未写 BigQuery/GCS。

### 改动文件

- `src/quant_ashare/strategy1/bq_io.py`
- `src/quant_ashare/strategy1/config.py`
- `src/quant_ashare/strategy1/runner_version.py`
- `scripts/strategy1_cloudrun/bq_io.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/__init__.py`
- 相关 `src/quant_ashare/strategy1/*.py` import
- `tests/strategy1/test_package_boundaries.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest -q tests`：268 passed。
- `python3 -m pytest -q tests/strategy1/test_package_boundaries.py`：6 passed。
- `python3 -m pytest -q tests/strategy1/test_cloudrun_package_entrypoints.py`：16 passed。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：passed。
- `python3 -m compileall -q src scripts tests`：passed。
- `git diff --check`：passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：passed。
- `PYTHONPATH=src` import smoke：passed。

### 阻塞项

- 无。

### 下一步建议

- 等待 Claude review；认可的 comment 在本分支修复，不认可的在 PR comment 说明理由。若合并前 `origin/main` 有新提交，rebase 后重跑关键验证。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

## 2026-06-12 GPT-5.5 - PR #202 review follow-up

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-prd04`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/prd04-guardrails`
Run ID: N/A
相关 issue/PR: PR #202；review comment `4692136310`

### 已完成工作

- F2：`qa_corporate_action_ledger_outputs` 的 dividend staleness watermark 改为读取 full-table 可见上界，上限使用 `CURRENT_DATE('Asia/Shanghai')`，不再被 `p_predict_end` 截断。
- F3：`experiment_resolution.resolve_experiment_from_args()` 恢复 `experiment_json` 最高优先级；新增 reporting 组合传参测试，确认 `--experiment-json` + `--manifest-resolved` 同传时走 `experiment_json` 成功。
- F4：`qa_corporate_action_ledger_outputs` catalog inputs 补 direct base table `dwd_stock_dividend_event`，测试同时检查 SQL 直接引用和 catalog input。
- F5/F9/F10：window SQL 同构 guard 收紧 dws/03 精确锚点与 dwd/01、dws/04 token 角色映射；新增 review seeded mutations，覆盖 `pe_ttm -> pe`、观测窗写死、边界互换三类失败。
- F6：补 `_failed_reasons`、legacy `_hard_reject_reasons` gate 表驱动覆盖和 `evaluate_cv_folds` 成功路径；v3 contract 对缺 v3 metrics 先返回 `v3_acceptance_metrics=missing`，不强造 legacy main path。
- F7/F8：`--manifest-resolved` scanner 缩到 backtest report command builders，manifest fixture 改为 repo-root 绝对路径。
- F11：`select_candidate([], [], None)` 的 `IndexError` 明确作为当前行为 characterization test 固定，本 PR 不改生产语义。

### 重要上下文

- F1 为 owner 数据决策项：Claude 实跑发现现存 CA-on baseline 的 staleness 断言会失败，dividend 数据缺口为 `2026-05-28..2026-06-09`，`ods_tushare_dividend` 当前 max partition/date 为 `2026-05-27`。本轮不执行补采、不写 BigQuery/GCS，断言语义不放宽，PR body 已改为如实陈述。
- 精确 ingestion watermark 仍需要新增 source ingestion 列或修复 ingestion meta；ingestion meta 当前 0-row 事件不在本 PR 处理。

### 改动文件

- `sql/strategy1/qa/qa_corporate_action_ledger_outputs.sql`
- `configs/strategy1/active_step_catalog.yml`
- `src/quant_ashare/strategy1/experiment_resolution.py`
- `tests/strategy1/test_experiment_resolution.py`
- `tests/strategy1/test_sql_render.py`
- `tests/strategy1/test_strategy1_catalog.py`
- `tests/strategy1/test_strategy1_pure_functions.py`
- `tests/warehouse/test_windowed_sql_isomorphism.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

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

### 测试 / 验证

- `python3 -m pytest -q tests`：266 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：passed。
- `git diff --check`：passed。
- `cd /tmp && python3 -m pytest /Users/fisher/Desktop/git/worktrees/quant-ashare-prd04/tests --collect-only -q`：266 collected。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_corporate_action_ledger_outputs.sql`：Query successfully validated。

### 阻塞项

- 无代码阻塞；F1 dividend ODS 补采与 CA-on baseline 复核留 owner 决策。

### 下一步建议

- push 后在 PR #202 回帖逐条说明 F2-F11 修复与 F1/F2 取舍；等待 Claude 复审。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 交接条目

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-006 / 单位契约 PRD

### 已完成工作

- 创建 OQ-006 PRD 草案：`docs/prd/PRD_20260602_01_OQ006接口单位换算口径.md`。
- PRD 将 OQ-006 定义为单位契约 + 覆盖检查 + DWD 准入门禁，建议新增 `ashare_meta.ods_field_unit_map` 和 `sql/qa/05_oq006_unit_checks.sql`。
- 根据 review feedback 修订 PRD：PR #13 `income` / `balancesheet` / `cashflow` 纳入首批覆盖，OQ-006 QA 编号改为 `05_oq006_unit_checks.sql`，契约表增加 `naming_exception_type` / `naming_exception_expires_at`，P0 覆盖补价格/比率字段。
- 更新 `OPEN_QUESTIONS.md`，将 OQ-006 标记为 PRD 草案已写、待 owner review 与实现。
- 更新 `TODO.md`，补 OQ-006 PRD 完成项和后续实现项。
- 更新 `IMPLEMENTATION_STATUS.md` 与当前交接摘要。

### 重要上下文

- 本次只写 PRD 和记忆/TODO，未创建 BigQuery `ashare_meta`、未写 `sql/qa/05_oq006_unit_checks.sql`，也未关闭 OQ-006。
- PRD 明确 P0 实现阶段需要处理 `dwd_index_eod.volume/amount` 未带单位后缀的命名债务：迁移为标准字段或登记 `naming_exception_type='legacy_unsuffixed'`，且 `verification_status` 仍必须为 `verified`。

### 改动文件

- `docs/prd/PRD_20260602_01_OQ006接口单位换算口径.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 文档与记忆更新，未执行 SQL。

### 阻塞项

- OQ-006 仍需 owner review：确认 meta 表字段、P0 + PR #13 首批补契约范围、`dwd_index_eod.volume/amount` 处理策略，以及是否将 `05_oq006_unit_checks.sql` 纳入 DWD PR 必跑 QA。

### 下一步建议

- 实现 `ashare_meta.ods_field_unit_map` 与 P0 + PR #13 财务三表首批 seed。
- 新增 `sql/qa/05_oq006_unit_checks.sql` 并跑通 P0 + PR #13 单位覆盖、状态、命名和自洽检查。

### 已更新记忆文件

- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: gthbj/quant-ashare#9 / OQ-007

### 已完成工作

- 在 BigQuery 上应用 PR #9 后的 OQ-007 退市日口径，重建 `data-aquarium.ashare_dim.dim_stock`。
- 按依赖重建 `data-aquarium.ashare_dwd.dwd_stock_eod_price`、策略 1 DWS 六表和 ADS 11 张契约表。
- 执行 `sql/metadata/01_p0_table_column_descriptions.sql`，恢复 P0 DIM/DWD 表和字段说明。
- 将根目录 `TODO.md` 中 PR #9 后依赖链重建待办勾选为完成。

### 重要上下文

- ADS 11 张表在重建前均为 0 行，因此执行 `sql/ads/01_ads_strategy1_tables.sql` 未覆盖已有 runner 产物。
- 重建后 `dim_stock` 5,853 行，其中 326 个退市股使用 ODS `stock_basic_delist_date`；`dwd_stock_eod_price` 8,506,688 行；策略 1 DWS 样本表 8,506,688 行，默认可训练样本 3,274,084 行。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dim/02_dim_stock.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dwd/01_dwd_stock_eod_price.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/01_dws_stock_universe_daily.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/02_dws_stock_feature_price_daily.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/03_dws_stock_feature_valuation_daily.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/04_dws_stock_label_daily.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/05_dws_stock_feature_daily_v0.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/06_dws_stock_sample_daily.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/ads/01_ads_strategy1_tables.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/metadata/01_p0_table_column_descriptions.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/01_p0_smoke_checks.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/02_strategy1_dws_ads_checks.sql`
- P0 DIM/DWD 字段说明缺失数复核：0。

### 阻塞项

- 无。

### 下一步建议

- 在 BigQuery 上端到端执行策略 1 runner 01-10，并跑通 `sql/ml/strategy1/10_qa_runner_outputs.sql`。
- 若要补通用特征，继续实现 `dws_stock_feature_fin_daily`、`dws_market_state_daily` 和财务三表。

### 已更新记忆文件

- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`

---

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: s1_bqml_20260601_01 / bt_s1_bqml_20260601_01
相关 issue/PR: 待创建 PR / 策略 1 模型质量诊断 smoke 修复

### 已完成工作

- 根据执行 agent 反馈，确认 `scripts/strategy1/diagnose_model_quality.py` 的 local smoke 在 `compute_cost_turnover()` 崩溃。
- 根因：`merged.fillna(0)` 对整张 DataFrame 生效，会尝试用整数 0 填充 BigQuery `db_dtypes` 日期列，触发 `TypeError: ('Invalid value type', 0)`。
- 在 `codex/fix-diagnosis-cost-fillna` 分支修复：成本归因合并后只填充数值列；交易成本列先 `pd.to_numeric(...).fillna(0.0)`；`trades_df` 为空时返回带 0 成本列的 NAV 基表。
- 同步 `TODO.md` 与 `IMPLEMENTATION_STATUS.md`，明确修复合并后需要重跑诊断 local smoke、uploaded 模式和 `12_qa_model_diagnosis_outputs.sql`。

### 重要上下文

- 本次未重跑完整 `diagnose_model_quality.py`，避免在未合并修复分支上回写 ADS / 上传 GCS。
- 已做针对性单元场景，模拟 `db_dtypes.DateDtype` 的 `trade_date` 列，确认不会再对日期列填 0。

### 改动文件

- `scripts/strategy1/diagnose_model_quality.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/diagnose_model_quality.py`
- 针对性 Python 场景：`compute_cost_turnover()` 处理 `db_dtypes.DateDtype` 日期列、缺失成本列和 `economic_cost=fee+slippage`
- `git diff --check`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/11_model_quality_diagnostics.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`

### 阻塞项

- 无代码阻塞；完整诊断 local smoke / uploaded / QA 仍需在修复 PR 合并后执行。

### 下一步建议

- 合并修复 PR。
- 重新执行 `diagnose_model_quality.py --skip-gcs-upload` local smoke。
- local smoke 成功后去掉 `--skip-gcs-upload` 跑 uploaded 模式，并执行 `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`。

### 已更新记忆文件

- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

---

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: gthbj/quant-ashare#11

### 已完成工作

- 合并 PR #11 到 `main`。
- 本地 `main` 已 fast-forward 到远端合并结果。
- 删除远端 `codex/implement-oq004-index` 分支，并删除本地同名分支。
- 补充本次 merge 状态到记忆和 TODO。

### 重要上下文

- PR #11 合并后，OQ-004 实现与 review feedback 修复均已进入 `main`。
- 合并操作未重跑 BigQuery QA；本次仅做 GitHub merge、本地同步和分支清理。PR 合并前最近验证记录见上一条交接。

### 改动文件

- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `gh pr view 11` 显示合并前 `mergeable=MERGEABLE` 且无 status checks。
- `gh pr merge 11 --merge --delete-branch` 成功。
- `git fetch --prune origin && git switch main && git pull --ff-only origin main` 成功。
- `git branch -d codex/implement-oq004-index` 成功。

### 阻塞项

- 无。

### 下一步建议

- 在 BigQuery 上执行策略 1 runner 01-10 并跑通 `10_qa_runner_outputs.sql`，或先重建 PR #9 相关 `dim_stock` 依赖链后再执行全量 QA。

### 已更新记忆文件

- `MEMORY_INDEX.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: gthbj/quant-ashare#11

### 已完成工作

- 查看 PR #11 comment 4594329002，并按问题逐项处理。
- 认可并修复 M1/L1/L2/L3：`dim_index` 建表脚本补充 ODS 端点准入说明；字段描述从 `sql/dim/04_dim_index.sql` 收敛到 `sql/metadata/01_p0_table_column_descriptions.sql`；`sql/qa/03_oq004_index_checks.sql` 明确示例 benchmark/window；runner 08 注明统一使用 SSE 日历代表 A 股开市日。
- 不认可 M2：`sql/metadata/01_p0_table_column_descriptions.sql` 在 PR 前后均已覆盖 `dwd_index_eod` 全 26 列；BigQuery 复核 `dwd_index_eod` missing description = 0。
- 重新物化 `data-aquarium.ashare_dim.dim_index` 并执行 metadata，保证 `dim_index` 字段描述由集中 metadata 脚本恢复。

### 重要上下文

- ODS `ods_tushare_index_daily` 的 `sourceUris` 当前只有 7 个 endpoint：SSE50、STAR50、CSI1000、CSI500、深成指、创业板指、CSI300 来源 `399300.SZ`。未见中证2000/国证2000相关 endpoint，因此不应 seed 到 `dim_index`。
- `sql/qa/03_oq004_index_checks.sql` 是 OQ-004 示例窗口门禁；真实 runner 参数窗口仍由 `sql/ml/strategy1/08_run_backtest.sql` 前置 ASSERT 负责。

### 改动文件

- `sql/dim/04_dim_index.sql`
- `sql/qa/03_oq004_index_checks.sql`
- `sql/ml/strategy1/08_run_backtest.sql`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `git diff --check`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/dim/04_dim_index.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/qa/03_oq004_index_checks.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/08_run_backtest.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dim/04_dim_index.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/metadata/01_p0_table_column_descriptions.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/03_oq004_index_checks.sql`
- BigQuery metadata 复核：`dim_index` missing description = 0；`dwd_index_eod` missing description = 0。

### 阻塞项

- 无。

### 下一步建议

- 已完成：本次修复已提交、推送并随 PR #11 合并入 `main`。

### 已更新记忆文件

- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

## Handoff Entry

Date: 2026-05-31
Agent ID: Codex
Agent Instance ID: Codex desktop session
Model: GPT-5
Runtime: Codex desktop
Run ID: —
Related issue/PR: gthbj/quant-ashare#1

### Work Completed
- Committed local P0 second-review fixes as `d009b36`.
- Merged remote PR #1 content into local `main`, preserving the later local P0 materialization/QA status.
- Resolved memory/TODO conflicts by keeping both the DWS/ADS strategy design additions and the later P0 materialized + QA-passed state.
- Renumbered the strategy-default open question to OQ-010 to avoid colliding with closed OQ-009 for `index_dailybasic`.

### Important Context
- PR #1 had been merged remotely first; local `main` also had later commits and local fixes.
- Conflict resolution preserved `DECISION-20260531-13` through `17`, and recorded PR #1 decisions as `DECISION-20260531-18` and `19`.
- No BigQuery tables were rebuilt during the merge operation.

### Files Changed
- `.agent/memory/{AGENT_HANDOFF,ARCHITECTURE_MEMORY,DECISION_LOG,GLOSSARY,IMPLEMENTATION_STATUS,KNOWN_CONSTRAINTS,MEMORY_INDEX,OPEN_QUESTIONS,PROJECT_CONTEXT}.md`
- `TODO.md`
- `docs/数据仓库建模方案-DWD-DIM.md`
- `docs/数据仓库建模方案-DWS-ADS.md`
- `docs/A股中低频小资金机器学习策略方案.md`
- `sql/dwd/01_dwd_stock_eod_price.sql`
- `sql/dwd/05_dwd_fin_indicator_latest.sql`
- `sql/qa/01_p0_smoke_checks.sql`

### Tests / Validation
- Conflict markers removed from repository.
- `git diff --check` and SQL dry-runs should be rerun before final push.

### Blockers
- None.

### Next Recommended Step
- Push merged `main`, then continue with financial statement DWDs or P0 DWS/ADS SQL.

### Memory Files Updated
- AGENT_HANDOFF、DECISION_LOG、IMPLEMENTATION_STATUS、MEMORY_INDEX、OPEN_QUESTIONS、PROJECT_CONTEXT；TODO.md updated.

## Handoff Entry

Date: 2026-05-31
Agent ID: Codex
Agent Instance ID: Codex desktop session
Model: GPT-5
Runtime: Codex desktop
Run ID: —
Related issue/PR: —

### Work Completed
- Added `sql/metadata/01_p0_table_column_descriptions.sql` to maintain P0 DIM/DWD table and column descriptions.
- Updated `sql/README.md` so the metadata script runs after P0 table creation/rebuild.
- Executed the metadata script in BigQuery for 3 DIM + 5 DWD tables.
- Reviewed current P0 partitioning/clustering and kept the existing physical layout.

### Important Context
- All 8 P0 tables now have table descriptions and every schema field has a description; verification returned missing description count = 0 for each table.
- Existing physical layout remains: daily DWDs monthly partitioned by `trade_date` with `sec_code` clustering and `require_partition_filter`; financial indicator monthly partitioned by `ann_date_eff` and clustered by `sec_code`; small DIMs are unpartitioned and clustered by lookup keys.
- Finance partitioning/clustering is acceptable for current P0 size; future as-of-heavy workloads may revisit `visible_trade_date` partitioning or add `report_period` clustering.

### Files Changed
- `sql/metadata/01_p0_table_column_descriptions.sql`
- `sql/README.md`
- `TODO.md`
- `.agent/memory/{MEMORY_INDEX,ARCHITECTURE_MEMORY,IMPLEMENTATION_STATUS,KNOWN_CONSTRAINTS,DECISION_LOG,AGENT_HANDOFF}.md`

### Tests / Validation
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/metadata/01_p0_table_column_descriptions.sql` passed.
- Executed the metadata script successfully in BigQuery.
- `bq show --format=prettyjson` verified table description missing = 0 and field description missing = 0 for all 8 P0 tables.

### Blockers
- None.

### Next Recommended Step
- Continue with `dwd_fin_income` / `dwd_fin_balancesheet` / `dwd_fin_cashflow`, or begin P0 DWS/ADS SQL.

### Memory Files Updated
- MEMORY_INDEX、ARCHITECTURE_MEMORY、IMPLEMENTATION_STATUS、KNOWN_CONSTRAINTS、DECISION_LOG、AGENT_HANDOFF；TODO.md updated.

## Handoff Entry

Date: 2026-06-01
Agent ID: Codex
Agent Instance ID: Codex desktop session
Model: GPT-5
Runtime: Codex desktop
Run ID: —
Related issue/PR: —

### Work Completed
- 按 owner 要求整理 `.agent/memory/`：将旧交接完整归档到 `archive/AGENT_HANDOFF_2026-05.md`，活跃 `AGENT_HANDOFF.md` 仅保留当前摘要、最近交接和本条记录。
- 将关闭的 open questions 迁移到 `archive/CLOSED_QUESTIONS.md`，使 `OPEN_QUESTIONS.md` 只保留待 owner 决策的开放问题。
- 压缩 `DECISION_LOG.md` 中已废弃决策的正文，并修正 `TODO.md` / `IMPLEMENTATION_STATUS.md` 中与当前物化状态不一致的陈旧描述。
- 更新 `AGENTS.md` 和 `UPDATE_PROTOCOL.md`，规定只读盘点或无状态变化任务不追加交接、不更新状态/TODO；新增归档规则。

### Important Context
- 归档文件仍是 Git 可审计历史，但不属于常规启动必读路径；需要追溯历史时再读。
- 当前事实来源保持不变：整体状态看 `IMPLEMENTATION_STATUS.md`，下一步看 `TODO.md`，开放决策看 `OPEN_QUESTIONS.md`。

### Files Changed
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-05.md`
- `.agent/memory/archive/CLOSED_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/UPDATE_PROTOCOL.md`
- `AGENTS.md`
- `TODO.md`

### Tests / Validation
- `git diff --check` 通过。
- 冲突标记扫描无命中；活跃记忆/TODO/AGENTS 中关键陈旧状态关键词扫描无命中。
- 活跃启动记忆行数从整理前约 1683 行降至 1200 行；归档历史不属于常规启动必读路径。

### Blockers
- 无。

### Next Recommended Step
- 继续补 `dwd_fin_income` / `dwd_fin_balancesheet` / `dwd_fin_cashflow`，或落地 P0 DWS/ADS SQL 与 `ml_ranker_v0` 基线。

### Memory Files Updated
- AGENT_HANDOFF、MEMORY_INDEX、UPDATE_PROTOCOL、OPEN_QUESTIONS、DECISION_LOG、IMPLEMENTATION_STATUS；TODO.md updated.

---

## 交接条目

日期: 2026-06-01
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: —

### 已完成工作
- 根据 owner 对 DWS-ADS review P1-5 的确认，调整指数代码归一口径：`dwd_index_eod.sec_code` 输出 canonical 指数代码，新增 `source_sec_code` 保留 ODS/Tushare 实际代码。
- 更新 `sql/dwd/04_dwd_index_eod.sql`、metadata 描述脚本和 QA 断言，使沪深300来源 `399300.SZ` 输出为 `sec_code='000300.SH'` 并保留 `source_sec_code='399300.SZ'`。
- 更新 DWD-DIM、DWS-ADS、策略方案和策略 1 PRD，明确 DWS/ADS 基准指数 join 只使用 canonical `sec_code`。
- 记录 DECISION-20260601-01，并更新约束、架构记忆、开放问题和 TODO。

### 重要上下文
- 本次只改仓库 SQL/文档/记忆，未重建 BigQuery `data-aquarium.ashare_dwd.dwd_index_eod` 实表。
- 重建 `dwd_index_eod` 后必须重新执行 `sql/metadata/01_p0_table_column_descriptions.sql` 和 `sql/qa/01_p0_smoke_checks.sql`。

### 改动文件
- `sql/dwd/04_dwd_index_eod.sql`
- `sql/metadata/01_p0_table_column_descriptions.sql`
- `sql/qa/01_p0_smoke_checks.sql`
- `sql/README.md`
- `docs/数据仓库建模方案-DWD-DIM.md`
- `docs/数据仓库建模方案-DWS-ADS.md`
- `docs/A股中低频小资金机器学习策略方案.md`
- `docs/prd/PRD_20260601_01_策略1价格量价基础分类模型.md`
- `.agent/memory/{AGENT_HANDOFF,ARCHITECTURE_MEMORY,DECISION_LOG,IMPLEMENTATION_STATUS,KNOWN_CONSTRAINTS,OPEN_QUESTIONS}.md`
- `TODO.md`

### 测试 / 验证
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/dwd/04_dwd_index_eod.sql` 通过。
- 当前 BigQuery 实表未重建，metadata/QA 需在重建后运行。

### 阻塞项
- 无。

### 下一步建议
- 重建 `dwd_index_eod`，执行 metadata 与 QA；或继续处理 DWS-ADS review 的 P0/P1 其余发现。

### 已更新记忆文件
- AGENT_HANDOFF、ARCHITECTURE_MEMORY、DECISION_LOG、IMPLEMENTATION_STATUS、KNOWN_CONSTRAINTS、OPEN_QUESTIONS；TODO.md updated.

---

## 交接条目

日期: 2026-06-01
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-007 / 待创建 PR

### 已完成工作

- 在独立 worktree `/Users/luna/Desktop/git/quant-ashare-oq007` 创建分支 `codex/resolve-oq007-delist-date`，避免触碰主工作树未提交改动。
- 复核 BigQuery ODS：`stock_basic_delisted.delist_date` 当前 schema 为 `STRING`，最新 delisted 分区 326 行均可解析。
- 更新 `dim_stock` SQL：退市股优先使用 ODS `delist_date`，仅缺值时回退到 `daily` 最后交易日加一天。
- 更新 P0 QA、metadata、SQL README、DWD-DIM 文档，并关闭 OQ-007、追加 DECISION-20260601-04。
- 跟进 PR #9 comment：新增退市股生命周期 QA，禁止 `is_delisted=TRUE` 且退市边界缺失/非法；补全 `delist_date_source` 实际枚举说明。

### 重要上下文

- 本次没有重建 BigQuery 实表；当前生产 `dim_stock` 仍是历史 daily 兜底口径。
- 当前实表与 ODS 退市日对比，326 个退市代码中 259 个与 ODS 不一致；2019+ 口径切换预计会为 143 个退市代码补回正式退市日前的停牌生命周期行。
- 合并后需重建 `dim_stock`，再按依赖重建 `dwd_stock_eod_price` 与策略 1 DWS/ADS 派生产物，并执行 metadata / P0 QA / 策略 1 QA。

### 改动文件

- `sql/dim/02_dim_stock.sql`
- `sql/qa/01_p0_smoke_checks.sql`
- `sql/metadata/01_p0_table_column_descriptions.sql`
- `sql/README.md`
- `docs/数据仓库建模方案-DWD-DIM.md`
- `.agent/memory/{AGENT_HANDOFF,ARCHITECTURE_MEMORY,DECISION_LOG,IMPLEMENTATION_STATUS,KNOWN_CONSTRAINTS,OPEN_QUESTIONS}.md`
- `.agent/memory/archive/CLOSED_QUESTIONS.md`
- `TODO.md`

### 测试 / 验证

- ODS schema 与可解析性已用 BigQuery 查询复核。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/dim/02_dim_stock.sql` 通过。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/metadata/01_p0_table_column_descriptions.sql` 通过。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/qa/01_p0_smoke_checks.sql` 通过（含 PR #9 comment 新增生命周期断言）。
- 新 `dim_stock` 逻辑只读预览：5853 行、5853 个唯一 `sec_code`；326 个退市股使用 `stock_basic_delist_date`，2 个缺主数据代码继续用 `derived_from_daily` 兜底。
- `git diff --check` 通过。

### 阻塞项

- 无。实表重建留到 PR 合并后执行。

### 下一步建议

- 合并 PR 后重建 `dim_stock` 及依赖表，并执行 `sql/metadata/01_p0_table_column_descriptions.sql`、`sql/qa/01_p0_smoke_checks.sql`、`sql/qa/02_strategy1_dws_ads_checks.sql`。

### 已更新记忆文件

- AGENT_HANDOFF、ARCHITECTURE_MEMORY、DECISION_LOG、IMPLEMENTATION_STATUS、KNOWN_CONSTRAINTS、OPEN_QUESTIONS；archive/CLOSED_QUESTIONS、TODO.md updated.

---

## 交接条目

日期: 2026-06-01
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: —

### 已完成工作
- 合并后的 `main` 已进入新实现分支 `codex/implement-strategy1-prd`。
- 重建 BigQuery `data-aquarium.ashare_dwd.dwd_index_eod`，应用 canonical `sec_code` + `source_sec_code` 口径；重新执行 P0 metadata 与 smoke QA。
- 新增/更新 SQL：`sql/00_create_datasets.sql` 创建 `ashare_dws`/`ashare_ads`；`sql/dws/01-06_*.sql` 物化策略 1 universe、价格/估值特征、标签、特征宽表、样本表；`sql/ads/01_ads_strategy1_tables.sql` 创建 ADS 表契约；`sql/qa/02_strategy1_dws_ads_checks.sql` 增加策略 1 QA。
- 更新 `sql/README.md`、`TODO.md` 与工作记忆，记录已物化状态、验证结果和下一步。

### 重要上下文
- 策略 1 DWS/ADS SQL 已物化并通过 QA，但模型训练/预测/组合/回测 Python run 尚未实现。
- 当前策略 1 DWS 只读取最终 DWD/DIM，不直接读 ODS；由于最终 DWD 价格表不落 2018 buffer 行，2019 年初 60 日窗口用 `has_full_history_60d=FALSE` 显式标记，默认样本掩码剔除不完整窗口。是否补 lookback-capable 构建输入见 OQ-011。
- 默认样本切分当前为静态 `fold_default_2019_2026`：2019-2023 train、2024 valid、2025 test、2026+ live；滚动 fold 应在 ADS training run 中固化。

### 改动文件
- `sql/00_create_datasets.sql`
- `sql/dws/01_dws_stock_universe_daily.sql`
- `sql/dws/02_dws_stock_feature_price_daily.sql`
- `sql/dws/03_dws_stock_feature_valuation_daily.sql`
- `sql/dws/04_dws_stock_label_daily.sql`
- `sql/dws/05_dws_stock_feature_daily_v0.sql`
- `sql/dws/06_dws_stock_sample_daily.sql`
- `sql/ads/01_ads_strategy1_tables.sql`
- `sql/qa/02_strategy1_dws_ads_checks.sql`
- `sql/README.md`
- `.agent/memory/{AGENT_HANDOFF,ARCHITECTURE_MEMORY,IMPLEMENTATION_STATUS,KNOWN_CONSTRAINTS,MEMORY_INDEX,OPEN_QUESTIONS,PROJECT_CONTEXT}.md`
- `TODO.md`

### 测试 / 验证
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2` 通过：所有新增 DWS/ADS/QA SQL。
- 已执行：`sql/00_create_datasets.sql`、`sql/dwd/04_dwd_index_eod.sql`、`sql/metadata/01_p0_table_column_descriptions.sql`、`sql/qa/01_p0_smoke_checks.sql`、`sql/dws/01-06_*.sql`、`sql/ads/01_ads_strategy1_tables.sql`、`sql/qa/02_strategy1_dws_ads_checks.sql`。
- `sql/qa/02_strategy1_dws_ads_checks.sql` 全部 assertion successful。
- 策略 1 DWS 物化行数：universe 8,495,462；价格特征 8,495,462；估值特征 8,452,073；标签 8,495,462；特征宽表 8,495,462；样本表 8,495,462，默认可训练 3,274,084。

### 阻塞项
- 无阻塞。待 owner 确认 OQ-010/OQ-011 会影响训练/回测默认参数和 2019 初窗口完整性处理。

### 下一步建议
- 实现 `ml_pv_clf_v0` Python run：从 `dws_stock_sample_daily` 生成 `ads_ml_training_panel_daily`，训练 Logistic/Ridge/ElasticNet，写 `ads_model_prediction_daily`、候选/组合/订单和回测 ADS 表，输出 RankIC、分层收益、NAV、换手和不可成交比例。

### 已更新记忆文件
- AGENT_HANDOFF、ARCHITECTURE_MEMORY、IMPLEMENTATION_STATUS、KNOWN_CONSTRAINTS、MEMORY_INDEX、OPEN_QUESTIONS、PROJECT_CONTEXT；TODO.md updated.

---

## 交接条目

日期: 2026-06-01
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #4 comment `4592089459`

### 已完成工作
- 跟进 PR #4 owner comment 的 P1/P2 建议。
- `sql/dws/04_dws_stock_label_daily.sql` 去掉 `ce/c1` 冗余日历 JOIN，复用 `ce` 作为 1 日入场/退出日期。
- 补充 `label_valid_*d` 与 `exit_reachable_*d` 字段说明，明确 `label_valid` 只检查入场可交易和标签价格可用；退出可卖性交给 `exit_reachable` 与回测撮合。
- `sql/qa/02_strategy1_dws_ads_checks.sql` 增加默认可训练样本最早日期断言：当前为 `2019-04-03`，2019Q1 无默认可训练样本。
- 更新 DWS-ADS 与 DWD-DIM 文档：同步 `label_valid` 语义和 `dwd_stock_eod_price` 实表字段名 `volume_share` / `amount_cny`。

### 重要上下文
- 本次未改变标签收益公式，也未把退出不可卖合并进 `label_valid_*d`；这是按 PRD 的“标签不顺延，退出侧由回测撮合处理”口径执行。

### 改动文件
- `sql/dws/04_dws_stock_label_daily.sql`
- `sql/qa/02_strategy1_dws_ads_checks.sql`
- `sql/README.md`
- `docs/数据仓库建模方案-DWS-ADS.md`
- `docs/数据仓库建模方案-DWD-DIM.md`
- `.agent/memory/{AGENT_HANDOFF,IMPLEMENTATION_STATUS}.md`
- `TODO.md`

### 测试 / 验证
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/dws/04_dws_stock_label_daily.sql` 通过。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/qa/02_strategy1_dws_ads_checks.sql` 通过。
- 已重建 `data-aquarium.ashare_dws.dws_stock_label_daily` 和 `dws_stock_sample_daily`。
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/02_strategy1_dws_ads_checks.sql` 全部 assertion successful。

### 阻塞项
- 无。

### 下一步建议
- 将本次修复提交并推送到 `codex/implement-strategy1-prd`，更新 PR #4。

### 已更新记忆文件
- AGENT_HANDOFF、IMPLEMENTATION_STATUS；TODO.md updated.

---

## 交接条目

日期: 2026-06-01
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #4

### 已完成工作
- 删除已合并的本地分支 `codex/implement-strategy1-prd`。
- 删除远端分支 `origin/codex/implement-strategy1-prd`。
- 在 `KNOWN_CONSTRAINTS.md` 增加分支卫生规则：PR 合并后，若 owner 未要求保留工作分支，应删除已合并且不再使用的 `codex/*` 本地分支和对应远端分支。

### 重要上下文
- 当前本地分支为 `main`，已同步 `origin/main`。
- 本次仅更新工作记忆文件，未提交。

### 改动文件
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`

### 测试 / 验证
- `git branch --list codex/implement-strategy1-prd` 无输出。
- `git branch -r --list origin/codex/implement-strategy1-prd` 无输出。

### 阻塞项
- 无。

### 下一步建议
- 若需要把本次 memory 规则持久化到远端，提交并推送当前 `main` 上的记忆文件改动。

### 已更新记忆文件
- KNOWN_CONSTRAINTS、AGENT_HANDOFF、IMPLEMENTATION_STATUS.

---

## 交接条目

日期: 2026-06-01
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: —

### 已完成工作
- 新增策略 1 runner 设计文档 `docs/策略1-ml_pv_clf_v0-runner设计.md`，限定执行路径为 BigQuery SQL + BigQuery ML。
- 文档覆盖 runner 参数、训练面板、BQML `LOGISTIC_REG` 主模型、`LINEAR_REG` 对照、`ML.PREDICT`、候选池、组合、订单、回测、GCS 报告产物、本地报告镜像、幂等、安全、QA 和验收。
- 同步策略 1 PRD、策略方案、SQL README 与 ADS 表契约注释，将旧的 Python runner 表述改为 BigQuery ML + SQL runner。
- 记录 DECISION-20260601-02，并更新 TODO、架构记忆、实现状态、项目上下文和开放问题；OQ-010 不再包含训练工具链选择。

### 重要上下文
- 本次只完成设计与文档/记忆同步，尚未实现 `sql/ml/strategy1/` runner SQL。
- 策略 1 首版模型执行口径：训练面板写 `ads_ml_training_panel_daily`，BQML 模型对象放 `ashare_ads`，预测写 `ads_model_prediction_daily`，候选/组合/订单/回测/监控继续复用已物化 ADS 契约表。
- 回测报告文件设计为 GCS-first + 本地镜像：BigQuery ADS 是结构化事实来源，Markdown/HTML/图表/JSON artifact 持久放 `gs://<ashare-artifact-bucket>/reports/strategy1/ml_pv_clf_v0/run_id=<run_id>/backtest_id=<backtest_id>/`，同时镜像到本地 `reports/strategy1/ml_pv_clf_v0/run_id=<run_id>/backtest_id=<backtest_id>/` 方便用户读取；本地 `reports/` 默认不提交 git。
- PR #5 comment 已跟进：BQML 正则化改为 `L1_REG/L2_REG` 手动候选网格并按 valid RankIC/分层收益选择；`board` 从 v0 主模型训练列移除，保留为分组和暴露监控字段。PR #3 已 merged，当前 PR #5 `mergeStateStatus=CLEAN`，无需等待 PR #3。

### 改动文件
- `docs/策略1-ml_pv_clf_v0-runner设计.md`
- `docs/prd/PRD_20260601_01_策略1价格量价基础分类模型.md`
- `docs/数据仓库建模方案-DWS-ADS.md`
- `docs/A股中低频小资金机器学习策略方案.md`
- `.gitignore`
- `sql/README.md`
- `sql/ads/01_ads_strategy1_tables.sql`
- `.agent/memory/{AGENT_HANDOFF,ARCHITECTURE_MEMORY,DECISION_LOG,IMPLEMENTATION_STATUS,MEMORY_INDEX,OPEN_QUESTIONS,PROJECT_CONTEXT}.md`
- `TODO.md`

### 测试 / 验证
- 待提交前运行 `git diff --check`。
- 本次未执行 BigQuery SQL；无运行时表变更。

### 阻塞项
- 无。实现阶段仍需 owner 确认 OQ-010 的成本、调仓、持股数/权重上限和板块纳入参数。

### 下一步建议
- 实现 `sql/ml/strategy1/` BigQuery ML runner 脚本，并补 `10_qa_runner_outputs.sql`。

### 已更新记忆文件
- AGENT_HANDOFF、ARCHITECTURE_MEMORY、DECISION_LOG、IMPLEMENTATION_STATUS、MEMORY_INDEX、OPEN_QUESTIONS、PROJECT_CONTEXT；TODO.md updated.

---

## 交接条目

日期: 2026-06-01
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: —

### 已完成工作
- 新增实现型 PRD：`docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`。
- PRD 范围限定为策略 1 BigQuery ML + SQL runner 与回测闭环实现，定义 `sql/ml/strategy1/01-10` 脚本、README、QA、GCS 报告产物、本地 `reports/` 镜像和必需报告渲染脚本 `scripts/strategy1/render_report.py`。
- PRD 明确不回改上一份已通过策略 1 PRD，不解决 OQ-010/OQ-004/OQ-011，只把相关参数暴露为 runner 配置。
- 更新 TODO 和工作记忆，记录 runner 实现 PRD 已完成、runner SQL 仍未实现。

### 重要上下文
- 当前仍不能直接跑回测；下一步是按 `PRD_20260601_02_策略1BQML回测闭环.md` 实现 `sql/ml/strategy1/` 脚本。
- 结构化回测结果事实来源仍是 BigQuery ADS；人读报告持久化到 GCS，并镜像到本地 `reports/`。
- PR #6 comment 已跟进：卖出顺延首版采用预计算 `next_sellable_trade_date` 方案；连续超过 60 个交易日仍不可卖时标记异常并继续估值；报告渲染由 `scripts/strategy1/render_report.py` 完成；“候选池禁用 t+1 字段”作为 code review 项，运行时 QA 改为统计 t+1 不可买但仍入选样本和买入失败率。

### 改动文件
- `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`
- `.agent/memory/{AGENT_HANDOFF,ARCHITECTURE_MEMORY,IMPLEMENTATION_STATUS,MEMORY_INDEX,OPEN_QUESTIONS,PROJECT_CONTEXT}.md`
- `TODO.md`

### 测试 / 验证
- 待提交前运行 `git diff --check`。
- 本次未执行 BigQuery SQL；无运行时表变更。

### 阻塞项
- 无。实现 runner 时仍需 owner 决策或配置 OQ-010/OQ-004 参数。

### 下一步建议
- 实现 `sql/ml/strategy1/01-10` BigQuery ML runner 脚本，并补执行 README。

### 已更新记忆文件
- AGENT_HANDOFF、ARCHITECTURE_MEMORY、IMPLEMENTATION_STATUS、MEMORY_INDEX、OPEN_QUESTIONS、PROJECT_CONTEXT；TODO.md updated.

---

## 交接条目

日期: 2026-06-01
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #7 review protocol update

### 已完成工作

- 按 owner 最新要求更新评审协议：GitHub PR review 默认写 PR comment；一条写不下拆多条。
- 明确只有 owner 明确要求或无 PR comment 承载面时，才另写 `docs/reviews/` 评审文档。
- 将 DECISION-20260531-13 标记为被 DECISION-20260601-03 supersede。

### 重要上下文

- 历史 `docs/reviews/` 评审文档继续保留作审计记录。
- 评审过程仍保持只读：不擅改被评审对象，不把发现直接写进 `.agent/memory/**` 或 `TODO.md`；发现是否转 OQ/TODO/决策由 owner 拍板。

### 改动文件

- `AGENTS.md`
- `.agent/memory/UPDATE_PROTOCOL.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`

### 测试 / 验证

- 使用 `rg` 检查旧“评审必须产出文档”规则的位置并同步更新当前协议入口。

### 阻塞项

- 无。

### 下一步建议

- 后续 PR review 直接在 GitHub PR comment 中写发现；长评审拆多条 comment。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/UPDATE_PROTOCOL.md`

---

## 交接条目

日期: 2026-06-01
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-003 / 待创建 PR

### 已完成工作

- 新增 OQ-003 实现型 PRD：`docs/prd/PRD_20260601_03_财务报表口径维度.md`。
- PRD 推荐 P0 默认消费合并报表 `report_type='1'`，带 `report_type` 的财务 DWD 保留 `report_type` / `report_caliber` / `is_default_report_caliber`，P0 财务 DWS 默认只过滤默认口径。
- PRD 明确 `fina_indicator` 若源表无 `report_type`，不伪造多口径，只可用 `report_caliber='source_default'` 做元数据标识。
- 同步 `TODO.md`、`OPEN_QUESTIONS.md` 和 `IMPLEMENTATION_STATUS.md`，将 OQ-003 标记为 PRD 待 owner review。

### 重要上下文

- OQ-003 尚未关闭；关闭条件是 owner 采纳或调整 PRD 中的财务口径决策。
- 当前没有执行 BigQuery SQL，也没有重建任何 DWD/DWS/ADS 表。
- 后续实现 `dwd_fin_income` / `dwd_fin_balancesheet` / `dwd_fin_cashflow` 时，应按该 PRD 保留源 `report_type` 并让默认 latest / DWS 只消费默认合并报表口径。

### 改动文件

- `docs/prd/PRD_20260601_03_财务报表口径维度.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

### 测试 / 验证

- 文档改动，未执行 BigQuery SQL。
- 提交前运行 `git diff --check`。

### 阻塞项

- 无。OQ-003 仍需 owner review。

### 下一步建议

- owner review `docs/prd/PRD_20260601_03_财务报表口径维度.md`，确认是否采纳 P0 默认合并报表、DWD 保留多口径字段、DWS 默认过滤的方案。

### 已更新记忆文件

- AGENT_HANDOFF、IMPLEMENTATION_STATUS、OPEN_QUESTIONS；TODO.md updated.

---

## 交接条目

日期: 2026-06-01
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #8 review comment 4593381799

### 已完成工作

- 跟进 PR #8 owner review comment 的 2 个 P1 和 1 个 P2 反馈。
- 修订 `docs/prd/PRD_20260601_03_财务报表口径维度.md`：DWS PIT as-of 排序改为 `report_period DESC, ann_date_eff DESC, update_flag DESC, ingested_at DESC, source_partition_date DESC`，与主方案 §7.3 保持一致。
- 将 DWS 默认口径过滤示例改为预过滤子查询，避免把 `LEFT JOIN` 误写成隐式 inner join；统一 alias。
- 在 QA 章节补 DWD 版本事实表 schema、版本键唯一、NULL `report_type` 映射和默认口径映射断言，并明确三大财务表都要套用。
- 按 owner 追加反馈，将 QA 示例改为 NULL-safe 写法：`report_caliber IS DISTINCT FROM 'unknown'`，默认口径映射使用 `COALESCE(report_type = '1', FALSE)`。
- 同步 `TODO.md`、`OPEN_QUESTIONS.md` 和 `IMPLEMENTATION_STATUS.md`，记录 PR #8 review comment 已跟进。

### 重要上下文

- 本次只改 PR #8 分支文档和记忆，不执行 BigQuery SQL，也不重建任何表。
- OQ-003 仍未关闭，仍需 owner review 是否采纳默认合并报表 / DWD 保留多口径字段 / DWS 默认过滤方案。
- 主工作区 `/Users/luna/Desktop/git/quant-ashare` 当前在 `main` 上有未提交改动；本次修复在独立 worktree `/Users/luna/Desktop/git/quant-ashare-pr8` 完成，未触碰主工作区改动。

### 改动文件

- `docs/prd/PRD_20260601_03_财务报表口径维度.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

### 测试 / 验证

- 待提交前运行 `git diff --check`。

### 阻塞项

- 无。OQ-003 仍待 owner review。

### 下一步建议

- owner 复核 PR #8 最新版本；若采纳，关闭 OQ-003 并在后续三大财务表实现 PR 中按该 PRD 补 SQL 与 QA。

### 已更新记忆文件

- AGENT_HANDOFF、IMPLEMENTATION_STATUS、OPEN_QUESTIONS；TODO.md updated.

---

## 交接条目

日期: 2026-06-01
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #8 merge-conflict resolution proposal

### 已完成工作

- 按 owner 要求在 PR #8 分支上生成可审查的合并方案，而不是直接合并到 `main`。
- 将 `origin/main` 合入 `codex/oq-003-fin-report-type-prd`，解决 `AGENT_HANDOFF.md`、`IMPLEMENTATION_STATUS.md`、`TODO.md` 冲突。
- 冲突解决保留 `main` 的 OQ-007 退市日修复状态与待重建说明，同时保留 PR #8 的 OQ-003 财务报表口径 PRD 和 NULL-safe QA 状态。

### 重要上下文

- 本次是 PR 分支上的 merge-resolution 提案，供 reviewer/owner 审查；未合并到 `main`。
- 主工作区 `/Users/luna/Desktop/git/quant-ashare` 仍有未提交改动，本次只在 `/Users/luna/Desktop/git/quant-ashare-pr8` 操作。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`
- 以及 `origin/main` 带入的 OQ-007 相关文件。

### 测试 / 验证

- 待提交前运行 `git diff --check`。
- 本次未执行 BigQuery SQL。

### 阻塞项

- 无。PR #8 仍需 reviewer/owner 审查后再决定是否合并。

### 下一步建议

- reviewer 检查 PR #8 的 merge commit，确认 OQ-007 与 OQ-003 状态合并无误后再合并 PR。

### 已更新记忆文件

- AGENT_HANDOFF、IMPLEMENTATION_STATUS；TODO.md updated.

---

## 交接条目

日期: 2026-06-01
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-003 / PR #8

### 已完成工作

- 按 owner 最新确认采纳 `docs/prd/PRD_20260601_03_财务报表口径维度.md` 的推荐方案。
- 关闭 OQ-003 并迁移到 `archive/CLOSED_QUESTIONS.md`。
- 追加 `DECISION-20260601-05`：P0 默认合并报表 `report_type='1'`，DWD 保留 `report_type`/`report_caliber`/`is_default_report_caliber`，DWS 默认过滤默认口径，多口径特征后续另建/扩展。
- 更新当前交接摘要、实现状态、已知约束、架构记忆和 TODO。

### 重要上下文

- 当前 PR #8 关闭的是 OQ-003 决策与 PRD；不直接实现三大财务表 SQL。
- 后续实现 PR 需要同步 `docs/数据仓库建模方案-DWD-DIM.md` / `docs/数据仓库建模方案-DWS-ADS.md` 和 SQL。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/archive/CLOSED_QUESTIONS.md`
- `TODO.md`

### 测试 / 验证

- 待提交前运行 `git diff --check`。
- 本次未执行 BigQuery SQL。

### 阻塞项

- 无。

### 下一步建议

- 合并 PR #8 后，删除已合并的 `codex/oq-003-fin-report-type-prd` 分支；后续实现财务三表和财务 DWS 时按 DECISION-20260601-05 落 SQL 与文档同步。

### 已更新记忆文件

- AGENT_HANDOFF、ARCHITECTURE_MEMORY、DECISION_LOG、IMPLEMENTATION_STATUS、KNOWN_CONSTRAINTS、OPEN_QUESTIONS、archive/CLOSED_QUESTIONS；TODO.md updated.

---

## 交接条目

日期: 2026-06-01
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 board scope update

### 已完成工作

- 按 owner 最新确认同步策略 1 首个基线股票池口径：仅沪深主板（`SSE_MAIN` / `SZSE_MAIN`）。
- 明确首个基线不纳入北交所、创业板、科创板；后续如需纳入，应通过 `board_allowlist` 另开对照实验或单独模型。
- 将 OQ-010 缩小为成本、调仓频率、持股数和单票权重上限待确认；训练工具链和板块纳入口径均已定。
- 追加 `DECISION-20260601-06` 记录该板块范围决策。

### 重要上下文

- `sql/dws/01_dws_stock_universe_daily.sql` 原本默认 `board_allowlist = ['SSE_MAIN','SZSE_MAIN']`，本次仅补充注释和文档/记忆同步，未改变 SQL 行为。
- 现有已物化策略 1 DWS 默认池口径与本决策一致；未重跑 BigQuery 表。

### 改动文件

- `docs/prd/PRD_20260601_01_策略1价格量价基础分类模型.md`
- `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`
- `docs/策略1-ml_pv_clf_v0-runner设计.md`
- `docs/A股中低频小资金机器学习策略方案.md`
- `docs/数据仓库建模方案-DWS-ADS.md`
- `sql/dws/01_dws_stock_universe_daily.sql`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

### 测试 / 验证

- 提交前运行 `git diff --check`。
- 本次未执行 BigQuery SQL；无运行时表变更。

### 阻塞项

- 无。OQ-010 仍需 owner 确认成本、调仓频率、持股数和单票权重上限。

### 下一步建议

- 继续确认 OQ-010 剩余参数，或在实现 `sql/ml/strategy1/` runner 时先以配置参数保留占位。

### 已更新记忆文件

- AGENT_HANDOFF、ARCHITECTURE_MEMORY、DECISION_LOG、IMPLEMENTATION_STATUS、OPEN_QUESTIONS；TODO.md updated.

---

## 交接条目

日期: 2026-06-01
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-004 / PR #10

### 已完成工作

- 将 PR #10 分支 rebase 到 `origin/main`（`6199576`），并在冲突文件中保留主线 OQ-003、OQ-007、OQ-010 状态。
- 删除旧的跨问题合并口径 PRD，新增 OQ-004 专项 PRD：`docs/prd/PRD_20260601_04_OQ004基准指数口径.md`。
- 将 PR #10 范围收窄为指数 endpoint/canonical 映射、`dim_index`、映射驱动 `dwd_index_eod`、OQ-004 QA 和 runner benchmark 窗口契约。
- 同步 `TODO.md`、`OPEN_QUESTIONS.md`、`IMPLEMENTATION_STATUS.md`、`MEMORY_INDEX.md` 和当前交接摘要；OQ-004 仍保持 open，等待 owner review 与后续 SQL 实现。

### 重要上下文

- PR #10 不再承载财务报表口径事项；OQ-003 已由 `docs/prd/PRD_20260601_03_财务报表口径维度.md` 关闭。
- OQ-010 的主线状态保持不变：首个基线股票池仅沪深主板，剩余仅成本、调仓、持股数/权重上限待确认。
- 临时合并方案说明没有保留为最终 PRD 内容。

### 改动文件

- `docs/prd/PRD_20260601_04_OQ004基准指数口径.md`
- 旧的跨问题合并口径 PRD（删除）
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

### 测试 / 验证

- 待提交前运行 `git diff --check`。
- 本次未执行 BigQuery SQL；无运行时表变更。

### 阻塞项

- 无。OQ-004 仍需 owner review 后进入 SQL 实现。

### 下一步建议

- 合并 PR #10 后，按 PRD 补 `dim_index`、`sql/qa/03_oq004_index_checks.sql`、映射驱动的 `dwd_index_eod` 和 runner benchmark 窗口校验。

### 已更新记忆文件

- AGENT_HANDOFF、IMPLEMENTATION_STATUS、MEMORY_INDEX、OPEN_QUESTIONS；TODO.md updated.

---

## 交接条目

日期: 2026-06-01
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #7 / main memory sync

### 已完成工作

- 同步主线记忆状态：PR #7 已合并到 `main`，策略 1 BigQuery ML runner 脚本已进入仓库。
- 将 `IMPLEMENTATION_STATUS.md`、`MEMORY_INDEX.md`、`PROJECT_CONTEXT.md` 和当前交接摘要中“runner 待落地”的旧描述改为“runner 脚本已合并、dry-run 通过、尚未端到端实跑”。
- 同步 `TODO.md` 中 PR #9 合并后的重建待办和 OQ-004 待实现描述；runner 脚本完成项和端到端实跑待办已存在。

### 重要上下文

- 当前仓库已有 `sql/ml/strategy1/01-10`、`sql/ml/strategy1/README.md`、`scripts/strategy1/render_report.py` 和 `scripts/strategy1/requirements.txt`。
- 本次只是记忆同步，没有执行 BigQuery runner，也没有产出 ADS 回测结果或报告文件。
- 下一步若要跑策略，应在 BigQuery 上按 README 执行 runner 01-10，并通过 `10_qa_runner_outputs.sql` 的 cash、gross exposure、持仓唯一性等 v0 守卫。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `TODO.md`

### 测试 / 验证

- 待提交前运行 `git diff --check`。
- 本次未执行 BigQuery SQL；状态来自 `main` 当前文件和 PR #7 合并结果。

### 阻塞项

- 无。

### 下一步建议

- 在 BigQuery 上端到端执行策略 1 runner 01-10，或先补 OQ-004 的 `dim_index`、OQ-004 QA 和 runner benchmark 窗口校验。

### 已更新记忆文件

- AGENT_HANDOFF、IMPLEMENTATION_STATUS、MEMORY_INDEX、PROJECT_CONTEXT；TODO.md updated.

---

## 交接条目

日期: 2026-06-01
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-004 / PRD4 implementation

### 已完成工作

- 实现 PRD4 / OQ-004：新增 `sql/dim/04_dim_index.sql`，将指数 canonical 映射、ODS 实际代码、端点可用性、起止日期和 benchmark 候选状态沉淀到 `ashare_dim.dim_index`。
- 更新 `sql/dwd/04_dwd_index_eod.sql`，从 `dim_index` 读取 `source_sec_code -> sec_code` 映射和可用端点；沪深300继续由 ODS `399300.SZ` 输出 canonical `000300.SH`。
- 新增 `sql/qa/03_oq004_index_checks.sql`，覆盖 `dim_index` 唯一性、沪深300映射、中证1000 daily/dailybasic 口径、DWD 价格行和 runner benchmark 窗口覆盖。
- 更新 `sql/ml/strategy1/08_run_backtest.sql`，在写回测结果前校验 `p_benchmark` 是 `dim_index` 中可用 benchmark，且完整 NAV 窗口逐开市日有且只有一条非空基准价格记录。
- 更新 SQL README、runner README、DWD-DIM/DWS-ADS 文档、runner 设计、PRD2、PRD4、工作记忆和 TODO；追加 DECISION-20260601-08；关闭 OQ-004。

### 重要上下文

- BigQuery 已物化 `data-aquarium.ashare_dim.dim_index`（7 行）并重建 `data-aquarium.ashare_dwd.dwd_index_eod`（11,922 行）。
- 当前 `dim_index` 中 `000852.SH` 可作为收益 benchmark，但 `has_dailybasic=FALSE`，因此不能用于依赖指数估值字段的市场状态特征。
- 本次没有跑策略 1 runner 端到端，也没有生成 `run_id/backtest_id` 结果。
- 本次没有重建 PR #9 后仍待重建的 `dim_stock` 依赖链，因此未重跑全量 `sql/qa/01_p0_smoke_checks.sql`。

### 改动文件

- `sql/dim/04_dim_index.sql`
- `sql/dwd/04_dwd_index_eod.sql`
- `sql/qa/03_oq004_index_checks.sql`
- `sql/ml/strategy1/08_run_backtest.sql`
- `sql/ml/strategy1/README.md`
- `sql/metadata/01_p0_table_column_descriptions.sql`
- `sql/README.md`
- `docs/数据仓库建模方案-DWD-DIM.md`
- `docs/数据仓库建模方案-DWS-ADS.md`
- `docs/策略1-ml_pv_clf_v0-runner设计.md`
- `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`
- `docs/prd/PRD_20260601_04_OQ004基准指数口径.md`
- `.agent/memory/{AGENT_HANDOFF,ARCHITECTURE_MEMORY,DECISION_LOG,IMPLEMENTATION_STATUS,KNOWN_CONSTRAINTS,MEMORY_INDEX,OPEN_QUESTIONS,PROJECT_CONTEXT}.md`
- `.agent/memory/archive/CLOSED_QUESTIONS.md`
- `TODO.md`

### 测试 / 验证

- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/dim/04_dim_index.sql` 通过。
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dim/04_dim_index.sql` 通过，已创建 `dim_index`。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/dwd/04_dwd_index_eod.sql` 通过。
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dwd/04_dwd_index_eod.sql` 通过，已重建 `dwd_index_eod`。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/metadata/01_p0_table_column_descriptions.sql` 通过。
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/metadata/01_p0_table_column_descriptions.sql` 通过。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/qa/03_oq004_index_checks.sql` 通过。
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/03_oq004_index_checks.sql` 全部 assertion successful。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/08_run_backtest.sql` 通过。

### 阻塞项

- 无。

### 下一步建议

- 提 PR review；合并后可继续处理 PR #9 后的 `dim_stock` 依赖链重建，或开始端到端执行策略 1 runner 01-10。

### 已更新记忆文件

- AGENT_HANDOFF、ARCHITECTURE_MEMORY、DECISION_LOG、IMPLEMENTATION_STATUS、KNOWN_CONSTRAINTS、MEMORY_INDEX、OPEN_QUESTIONS、PROJECT_CONTEXT、archive/CLOSED_QUESTIONS；TODO.md updated.

---

## Handoff Entry

Date: 2026-06-02
Agent ID: Claude
Model: Claude Opus 4.8
Runtime: Claude Code
Related issue/PR: gthbj/quant-ashare#12

### Work Completed
- 在 BigQuery 上端到端实跑策略 1 runner `sql/ml/strategy1/01-10` 并通过全部 QA（run_id `s1_bqml_20260601_01` / backtest `bt_s1_bqml_20260601_01`）。
- 行数：训练面板 3,051,752；预测 1,052,687；候选 224,648；组合 520；订单 565；NAV 485 天。03 选 `l1_0_l2_1e_3`。`10_qa_runner_outputs.sql` 16 断言全过（cash≥-1、gross≤1.005、持仓唯一、NAV 全覆盖、report_uri 已回写等）。
- 实跑修复（均在 PR #12）：
  - 03/07/08/09 多处 BigQuery「相关子查询引用其它表」错误 → 去相关（cal 自连接取 t+1、cal/价格 JOIN+MIN 取可卖日、窗口累计现金、预聚合 + LEFT JOIN）。
  - 07/08/09 读分区表 `ads_portfolio_target_daily` 仅靠 JOIN 等值 → 补 `rebalance_date BETWEEN` 强制分区裁剪。
  - 10 NAV 连续性断言误用 `c.trade_date`（应 `c.cal_date`）。
  - `render_report.py`：无 ADC 时回退用 `gcloud auth print-access-token` 构造 BQ 客户端；`PARSE_JSON(..., wide_number_mode => 'round')` 处理 metrics_json 宽浮点回写。GCS bucket `ashare-artifacts` 不存在，用 `--skip-gcs-upload`（本地镜像 + 回写 report_uri）。
  - **08 重写为账户级 ledger**：v0 set-based 在真实数据上违反守卫（固定 `initial_capital×weight` 不回收资金 → 现金 -34 万、gross 2803 倍）；按 DECISION-20260601-07 改为 scripting WHILE 循环逐 period 维护现金/持仓、卖先于买、买受现金约束、netting、按 NAV 定档。守卫由构造保证并经实跑验证。

### Important Context
- v0 模型为反向预测基线（valid rank_ic≈-0.10、AUC≈0.50），回测 NAV 收于≈0.02——管线正确，模型质量是 OQ-010 待迭代项，不是管线缺陷。
- 08 ledger 为 v1 简化：不可交易腿本期跳过、carry 到下一 period，不做 60 交易日 next-sellable 顺延；未复权口径。
- BQML 实跑教训：runner 步骤禁止并发执行，被中断/拒绝的 bq 命令会在服务端继续跑；清理模型对象前先确认无 RUNNING job（见 KNOWN_CONSTRAINTS 工程约束）。
- 工作流：代码修复一律走 PR（PR #12），不直接提交 `main`。

### 阻塞项
- 无（流程已跑通）。PR #12 待 owner review / 合并。

### 下一步建议
- review 并合并 PR #12。
- 提升 v0 模型质量（特征/标签/选股口径，OQ-010）；或补 lookback-capable 价格输入（OQ-011）；或补通用财务/市场状态 DWS。
- 若需真实 GCS 报告产物：创建 `ashare-artifacts` bucket 并配置 ADC（`gcloud auth application-default login`）后去掉 `--skip-gcs-upload` 重跑 render。

### 已更新记忆文件
- IMPLEMENTATION_STATUS、KNOWN_CONSTRAINTS、AGENT_HANDOFF、DECISION_LOG；TODO.md。

---

## Handoff Entry

Date: 2026-06-02
Agent ID: Claude
Model: Claude Opus 4.8
Runtime: Claude Code
Related issue/PR: gthbj/quant-ashare#12（review follow-up）

> 本条为 PR #12 三轮 review follow-up 后的**最终状态**，口径以本条为准（早于本条的 PR #12 条目里「回写 report_uri」「render 本地报告 + 回写 report_uri」属早期描述，已被本条与代码取代，append-only 故保留不回改）。

### Work Completed（review follow-up）
- 第一轮 review：08 增写不可交易 skip 意图行（`BUY_SKIPPED_UNTRADABLE` / `SELL_SKIPPED_UNTRADABLE`，`filled_shares=0`、无现金/换手影响、持仓 carry）；09 改为从 `ads_backtest_trade_daily` 1:1 汇总 buy/sell attempt/filled/skipped 与 skip rate（删旧 episode/60 日 next-sellable 口径）；`render_report.py` skip 模式不写 `report_uri`（写 `local_report_path` + `report_upload_status=skipped`），上传模式才写真实 `report_uri`，Storage 与 BQ 客户端共用 gcloud token 回退；`10` 报告断言改为模式感知。重跑 08-10、16 断言全过。
- 第二轮 review：`ads_backtest_trade_daily.fill_status` 契约描述补 skip 枚举（源文件 + live 表 `ALTER`，数据保留）；README / PRD_02 / runner 设计 / 工作记忆从 v0 set-based + next-sellable + 无条件 GCS report_uri 收敛到 v1 ledger + 模式感知报告。
- 第三轮 review：PRD M4/M5 里程碑、PRD 风险行、`10` 注释、`AGENT_HANDOFF` 下一步、`PROJECT_CONTEXT` 当前阶段/下一步全部收敛到 v1 口径。

### 最终事实状态（bt_s1_bqml_20260601_01）
- runner 01-10 端到端通过；08 = 账户级有状态 ledger；现金>=0、gross<=1、持仓唯一、NAV 覆盖 485 开市日。
- 成交：BUY FILLED 363、SELL FILLED 422、SELL_SKIPPED_UNTRADABLE 21 → `sell_skip_rate=21/443=0.0474`（与 summary 一致）。
- 报告：local-only 模式，`report_upload_status=skipped`、`local_report_path` 有值、`report_uri=NULL`。
- v0 模型反向预测（valid rank_ic≈-0.10），NAV 收于≈0.02，属 OQ-010 模型质量、非管线缺陷。

### 下一步建议
- review/合并 PR #12；之后 OQ-010 模型质量与参数迭代；GCS bucket + ADC 后重跑 render 产出 `uploaded` 真实 `report_uri`；或 P1 财务/市场状态 DWS。

### 已更新记忆文件
- PROJECT_CONTEXT、MEMORY_INDEX、IMPLEMENTATION_STATUS、ARCHITECTURE_MEMORY、KNOWN_CONSTRAINTS、DECISION_LOG、AGENT_HANDOFF；TODO.md。

---

## 交接条目

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: TODO / memory housekeeping

### 已完成工作

- 整理根目录 `TODO.md`：移除大段历史完成项和重复的 OQ 汇总，改为“P0 当前优先 / P1 数据特征扩展 / 工程调度 / 近期完成”四块。
- 明确 `TODO.md` 与 `OPEN_QUESTIONS.md` 分工：TODO 面向下一步动作，开放问题仍由 `OPEN_QUESTIONS.md` 作为唯一来源。
- 同步 `IMPLEMENTATION_STATUS.md` 和当前交接摘要，记录本次维护状态。

### 重要上下文

- 本次只整理文档和工作记忆，未改 SQL / PRD / 代码，未执行 BigQuery。
- `OPEN_QUESTIONS.md` 内容未改；OQ-005、OQ-006、OQ-010、OQ-011 仍 open。

### 改动文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 优先实现 OQ-006 单位契约，随后处理 PRD03 / PR #13 财务三表落地与单位契约依赖。

### 已更新记忆文件

- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

---

## 交接条目

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-006 / unit contract PRD

### 已完成工作

- 按 owner 最新确认修订 `docs/prd/PRD_20260602_01_OQ006接口单位换算口径.md`：将四项待确认问题改为已确认决策。
- 明确 `ashare_meta.ods_field_unit_map` 为单位换算唯一事实来源。
- 明确 `dwd_index_eod.volume/amount` 必须迁移为 `volume_share/amount_cny`，legacy exception 只允许短期兼容。
- 明确 OQ-006 最小实现先于 P1 资金流、财务扩展等高单位风险 DWD 正式落地。
- 明确 `sql/qa/05_oq006_unit_checks.sql` 加入所有新增或修改 DWD 标准字段 PR 的必跑 QA。
- 追加 DECISION-20260602-02，并同步 OQ、TODO、实现状态、已知约束和当前交接摘要。

### 重要上下文

- 本次只改 PRD 和记忆/TODO，未实现 `ashare_meta.ods_field_unit_map`、未写 `sql/qa/05_oq006_unit_checks.sql`，也未迁移 `dwd_index_eod` 字段。
- OQ-006 仍 open，状态是 owner 决策已确认、待实现。

### 改动文件

- `docs/prd/PRD_20260602_01_OQ006接口单位换算口径.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 实现 OQ-006 最小版本：meta 表 + seed、`05_oq006_unit_checks.sql`、`dwd_index_eod` 命名迁移、DWD-DIM / README / `KNOWN_CONSTRAINTS.md` 同步，然后关闭 OQ-006。

### 已更新记忆文件

- `DECISION_LOG.md`
- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `KNOWN_CONSTRAINTS.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

---

## 交接条目

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-006 / PRD review follow-up

### 已完成工作

- 复核 Claude 对 OQ-006 PRD 的 4 条 review，全部认可并修订。
- 确认 `sql/dwd/04_dwd_index_eod.sql` 当前对 `index_daily.vol/amount` 仅直接 `SAFE_CAST`，因此 `dwd_index_eod.volume/amount` 实际仍是手 / 千元，不只是字段名未带单位后缀。
- 修订 OQ-006 PRD：将 §7.3 改为“P0 命名债务 + 换算缺失”，明确 OQ-006 实现必须补 `vol*100` / `amount*1000` 换算、迁移为 `volume_share/amount_cny` 并重建 `dwd_index_eod`。
- 修订 §7.1 首批补契约表，补 `source_unit`、`canonical_unit`、`multiplier` 列，并补充比率字段 percent / ratio / multiple 的方向性规则。
- 修订 QA-UNIT-6，将 `index_basic` 改为 `index_dailybasic`，并增加 `index_daily` 成交额自洽检查。
- 同步 TODO、OPEN_QUESTIONS、KNOWN_CONSTRAINTS、IMPLEMENTATION_STATUS、MEMORY_INDEX、PROJECT_CONTEXT、DECISION_LOG 和当前交接摘要。

### 重要上下文

- 本次只改 PRD 和记忆/TODO，未修改 SQL、未重建 BigQuery 表。
- OQ-006 仍 open；下一步实现时必须同时处理 index daily 换算和字段命名迁移。

### 改动文件

- `docs/prd/PRD_20260602_01_OQ006接口单位换算口径.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 实现 OQ-006 最小版本时，先修 `dwd_index_eod`：从 `index_daily.vol/amount` 生成 `volume_lot/amount_k_cny` raw 字段和 `volume_share/amount_cny` 标准字段，重建表并同步 metadata、下游引用和 QA。

### 已更新记忆文件

- `AGENT_HANDOFF.md`
- `DECISION_LOG.md`
- `IMPLEMENTATION_STATUS.md`
- `KNOWN_CONSTRAINTS.md`
- `MEMORY_INDEX.md`
- `OPEN_QUESTIONS.md`
- `PROJECT_CONTEXT.md`
- `TODO.md`

---

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-006 / PR #16

### 已完成工作

- 将 OQ-006 状态从 open / PR #16 修复中同步为已实现并关闭。
- 从 `OPEN_QUESTIONS.md` 移除 OQ-006，并在 `archive/CLOSED_QUESTIONS.md` 归档关闭记录。
- 从 `TODO.md` 的 P0 当前优先移除 OQ-006 实现项，并加入近期完成项。
- 同步 `MEMORY_INDEX.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要，去掉 “OQ-006 待实现 / 待 BQ 验证” 的旧状态。

### 重要上下文

- PR #16 已合并到 `main`，合并提交为 `db1e786`。
- OQ-006 交付物已进入 `main`：`sql/meta/01_ods_field_unit_map.sql`、`sql/qa/05_oq006_unit_checks.sql`、`sql/dwd/04_dwd_index_eod.sql` 换算修复、DWD-DIM 单位准入规则与 README / metadata 同步。
- 本次只同步项目状态与记忆，未修改 SQL，未重建 BigQuery 表。

### 改动文件

- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/CLOSED_QUESTIONS.md`

### 测试 / 验证

- `git diff --check`
- `rg -n "OQ-006|PR #16" TODO.md .agent/memory`

### 阻塞项

- 无。

### 下一步建议

- 落地 PR #13 / OQ-003 财务三表 DWD，并随表补全 `ods_field_unit_map` 剩余财务字段映射、跑通 `sql/qa/05_oq006_unit_checks.sql`。
- 随后推进 PRD03 财务特征 DWS，或并行处理 OQ-010 策略参数和模型质量。

### 已更新记忆文件

- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `IMPLEMENTATION_STATUS.md`
- `KNOWN_CONSTRAINTS.md`
- `OPEN_QUESTIONS.md`
- `AGENT_HANDOFF.md`
- `archive/CLOSED_QUESTIONS.md`
- `TODO.md`

---

## 交接条目

日期: 2026-06-02
Agent ID: Claude
Agent 实例 ID: Claude Code desktop session
模型: Claude Opus 4.8
运行环境: Claude Code
Run ID: —
相关 issue/PR: gthbj/quant-ashare#13（OQ-003 财务三表 + OQ-006 单位契约集成）

### 已完成工作

- 将 PR #13 财务分支 `feat/implement-prd03-finance-caliber` rebase 到含 OQ-006 的最新 `origin/main`（9d52e3f）：丢弃 owner 早先手工 merge 32c7f4f 的中间 merge commit，replay 单个财务 commit。解决 `sql/README.md`、`TODO.md`、`MEMORY_INDEX.md`、`IMPLEMENTATION_STATUS.md`、`AGENT_HANDOFF.md`、`DECISION_LOG.md` 冲突（取 main 新内容 + 重并财务事实；`DECISION_LOG`/`AGENT_HANDOFF` 用 `checkout --ours` + 重并避免 append 交错）。
- 决策撞号修复：财务实现决策与 main 已有 `DECISION-20260602-01`（ledger）/`-02`（OQ-006）撞号，renumber 为 **DECISION-20260602-03**，并更新 `IMPLEMENTATION_STATUS`/`KNOWN_CONSTRAINTS` 引用。
- 按 OQ-006 单位契约补全 `sql/meta/01_ods_field_unit_map.sql`：main 已预 seed 财务三表 QA-UNIT-2 必需子集 + 全部 `dwd_fin_indicator` 字段；本 PR 追加 31 条，覆盖财务三表 DWD **全部**单位字段（income 20、balancesheet 19、cashflow 13）。金额字段 `source_unit=canonical_unit=元`、`multiplier=1`、`source_name_passthrough`；`basic_eps/diluted_eps` 为 `per_share` 元/股。
- 在 BigQuery 重新物化 `ashare_meta.ods_field_unit_map` 并跑通全部 QA。

### 重要上下文

- `dwd_index_eod` 已在 main OQ-006 阶段迁移为 `volume_share/amount_cny`（实表已含这些列），qa/05 的 QA-UNIT-6 算术自洽断言可直接运行。
- 财务金额字段命名沿用 Tushare 源名（不带 `_cny` 后缀），靠 `source_name_passthrough` 例外通过 QA-UNIT-4a（要求 source_unit=canonical_unit 且 multiplier=1，无 expires_at）。
- 财务 DWD/DWS 实表此前已物化（上一会话），本次未重建，仅补单位映射 + 重跑 QA。

### 改动文件

- `sql/meta/01_ods_field_unit_map.sql`（追加财务三表全字段映射）
- 冲突解决涉及：`sql/README.md`、`TODO.md`、`.agent/memory/{MEMORY_INDEX,IMPLEMENTATION_STATUS,AGENT_HANDOFF,DECISION_LOG,KNOWN_CONSTRAINTS}.md`

### 测试 / 验证

- `bq query --dry_run`：`sql/meta/01_ods_field_unit_map.sql` 通过（列数自洽）。
- 物化 `ods_field_unit_map`；财务覆盖：income 20 / balancesheet 19 / cashflow 13 / indicator 32。
- QA 全过：`sql/qa/04`(25) + `sql/qa/05`(15，含 QA-UNIT-2 财务字段命中、QA-UNIT-4/7/8/9 命名例外约束、QA-UNIT-6 算术自洽) + 既有 `01`(12)/`02`(13)/`03`(11)，合计 76 断言，0 失败。

### 阻塞项

- 无。PR #13 已 rebase + 单位契约集成，待 owner review / 合并。

### 下一步建议

- review/合并 PR #13。
- 后续可补 `dws_market_state_daily`、三大报表单季 `q_*` 派生（P1），或推进 OQ-010 模型质量。

### 已更新记忆文件

- AGENT_HANDOFF、DECISION_LOG、IMPLEMENTATION_STATUS、KNOWN_CONSTRAINTS、MEMORY_INDEX；TODO.md updated.

---

## 交接条目

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #13 / PR #16 状态收尾

### 已完成工作

- 清理已合并 PR 的旧状态文字：PR #16 / OQ-006 已关闭，PR #13 / OQ-003 财务三表 DWD + DWS 已合并并实现。
- 从 `TODO.md` 的 P0 当前优先中移除“PR #13 待 owner 合并”旧项，并将 PR #13 移入近期完成。
- 更新 `PROJECT_CONTEXT.md` 和 `AGENT_HANDOFF.md` 顶部摘要，把“下一步落地 PR #13 / 财务三表”改为当前真实下一步：OQ-010 策略质量、`dws_market_state_daily`、GCS report、P1 单季/行业/资金/事件扩展。
- 轻微同步 `IMPLEMENTATION_STATUS.md` 中 OQ-003 与 TODO 整理描述，避免后续 agent 误判 PR #13 仍待合并。

### 重要上下文

- 本次未改 SQL、未重建 BigQuery 表、未新增决策。
- `OPEN_QUESTIONS.md` 当前仍只保留 OQ-005 / OQ-010 / OQ-011；OQ-003 / OQ-006 已关闭。

### 改动文件

- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check` 通过。
- `rg` 检查确认 `TODO.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md` 和 `AGENT_HANDOFF.md` 当前摘要已不再把 PR #13 / OQ-003 或 PR #16 / OQ-006 当作待办；`AGENT_HANDOFF.md` 历史交接条目仍保留旧阶段记录，仅用于审计追溯。

### 阻塞项

- 无。

### 下一步建议

- 推进 OQ-010：先定策略参数与财务增强特征接入方案，再跑可复现对照实验。
- 或补 P0 `dws_market_state_daily` / GCS uploaded report。

### 已更新记忆文件

- `PROJECT_CONTEXT.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / 策略 1 score orientation PRD

### 已完成工作

- 创建独立 worktree：`/Users/luna/Desktop/git/quant-ashare-score-orientation-prd`。
- 创建分支：`codex/prd-score-orientation`，基于 `origin/main` 的 `d5f7d82`。
- 新增 PRD：`docs/prd/PRD_20260603_01_策略1分数方向校准.md`。
- PRD 基于 livepool source run 与 reverse-score shadow run 的事实对照，定义策略 1 score orientation 机制：`raw_score` 是 BQML 正类概率，`score` 是最终用于排序的方向校准分数，`score_orientation` 为 `identity` / `reverse_probability`。
- PRD 要求 03 选型阶段用 valid 期 RankIC + bucket lift 判定并登记方向，04 预测阶段应用方向，05 以后继续按最终 `score DESC`，并同步 QA/report/diagnosis。

### 重要上下文

- 本次只写 PRD 和记忆/TODO，不实现 SQL/Python。
- 当前主目录 `/Users/luna/Desktop/git/quant-ashare` 已有另一个未提交的 `codex/fix-strategy1-score-orientation` 实现分支改动；本次 worktree 从 `origin/main` 新建，未触碰该目录的未提交改动。
- PRD 不建议硬编码反向策略；它要求以 valid 期方向校准机制选择 `identity` 或 `reverse_probability`，test 只作样本外验收。

### 改动文件

- `docs/prd/PRD_20260603_01_策略1分数方向校准.md`
- `TODO.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- 文档变更，未执行 SQL。
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- owner review PRD。
- PRD 认可后，实现 score orientation 校准：ADS 契约新增 `raw_score` / `score_orientation`，03 登记方向，04 应用方向，扩展 QA/report/diagnosis，并用新 `run_id/backtest_id` 完整验证。

### 已更新记忆文件

- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

---

## 交接条目

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / 策略 1 交易成本口径 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260602_02_OQ010交易成本口径.md`，将策略 1 默认成本 profile 定为佣金万一免五、卖出印花税 5 bps、买/卖滑点各 5 bps。
- 同步 `docs/策略1-ml_pv_clf_v0-runner设计.md` 与 `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`，把成本从“待确认 `cost_bps`”改为引用新成本 PRD；明确代码实现仍需后续 PR。
- 追加 `DECISION-20260602-04`，记录 OQ-010 成本子项的 owner 决策。
- 更新 `OPEN_QUESTIONS.md` / `TODO.md` / 项目记忆：OQ-010 成本子项已决策待实现；调仓频率、持股数、单票权重上限仍 open。

### 重要上下文

- 本次只写 PRD 和状态同步，未修改 runner SQL；当前可执行 runner 仍使用旧的单一 `p_cost_bps=30.0`，直到后续实现 PR 改 08/09/10/report/README。
- 印花税口径按财政部、税务总局 2023 年第 39 号公告后的常用卖出侧 5 bps；PRD 中已附官方来源链接。

### 改动文件

- `docs/prd/PRD_20260602_02_OQ010交易成本口径.md`
- `docs/A股中低频小资金机器学习策略方案.md`
- `docs/策略1-ml_pv_clf_v0-runner设计.md`
- `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`
- `docs/prd/PRD_20260601_04_OQ004基准指数口径.md`
- `sql/ml/strategy1/README.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `git diff --check` 通过。
- 文档引用与 stale 状态 `rg` 检查通过；当前文档已不再把成本参数表述为待 owner 确认，仅保留“代码实现待后续 PR”的状态。

### 阻塞项

- 无。

### 下一步建议

- 提实现 PR：改 `sql/ml/strategy1/08_run_backtest.sql`、`09_build_metrics_and_report_inputs.sql`、`10_qa_runner_outputs.sql`、`scripts/strategy1/render_report.py` 和 `sql/ml/strategy1/README.md`，用新成本 profile 重跑 runner。

### 已更新记忆文件

- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `IMPLEMENTATION_STATUS.md`
- `OPEN_QUESTIONS.md`
- `DECISION_LOG.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

---

## 交接条目

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: 策略 1 报告 GCS uploaded 模式运行手册

### 已完成工作

- 新增 `docs/策略1报告GCS上传运行手册.md`，覆盖 `ashare-artifacts` bucket、ADC、IAM、local-only smoke、uploaded 模式执行、GCS/ADS/QA 验收、故障处理和安全约束。
- 更新 `TODO.md`：GCS uploaded 仍是 P0 待执行项，但改为按运行手册执行；补充运行手册已新增的完成记录。
- 同步项目记忆，把策略 1 中文报告与归因分析状态从“PRD 待实现”更新为 PR #20 已实现并合并。
- 更新 `OPEN_QUESTIONS.md`，将 OQ-010 open 范围收敛为剩余调仓/持仓参数与模型质量迭代，不再把报告实现列为待办。

### 重要上下文

- 本次只写运行手册和状态同步，没有创建 GCS bucket，没有配置 ADC，也没有去掉 `--skip-gcs-upload` 实跑 uploaded 模式。
- uploaded 模式的下一步是按 `docs/策略1报告GCS上传运行手册.md` 准备 `gs://ashare-artifacts`、确认执行身份权限，然后重跑 `scripts/strategy1/render_report.py` 并执行 `sql/ml/strategy1/10_qa_runner_outputs.sql`。
- 主工作区 `/Users/luna/Desktop/git/quant-ashare` 当前有其他分支上的未提交改动；本次使用独立 worktree `/Users/luna/Desktop/git/quant-ashare-gcs-report-runbook` 完成，未触碰那些改动。

### 改动文件

- `docs/策略1报告GCS上传运行手册.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check` 通过。
- 凭据模式扫描未发现实际 key/token/private key。
- 过期“报告待实现”表述扫描仅命中旧历史交接条目，未命中新状态摘要、TODO、OQ 或项目背景。

### 阻塞项

- 无。

### 下一步建议

- 准备 `gs://ashare-artifacts` bucket 和 ADC / service account 权限。
- 去掉 `--skip-gcs-upload` 重跑 `scripts/strategy1/render_report.py`，确认 ADS `metrics_json.report_upload_status='uploaded'` 且 `report_uri` 非空。
- 跑通 `sql/ml/strategy1/10_qa_runner_outputs.sql`，完成 GCS uploaded 模式验收。

### 已更新记忆文件

- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `IMPLEMENTATION_STATUS.md`
- `OPEN_QUESTIONS.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

---

## 交接条目

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #18 / 策略 1 中文报告与归因分析 PRD review comment

### 已完成工作

- 按 PR #18 review comment 修订 `docs/prd/PRD_20260602_03_策略1中文报告归因分析.md`。
- 基准口径改为：中证1000 `000852.SH` 是 runner / ADS 评估主基准和归因主基准；沪深300 `000300.SH` 仅作为报告展示对比基准，不替代评估基准。
- 补充 `diagnosis_evidence.json` P0 schema：`schema_version=strategy1_report_evidence_v1`、required key、空数组 / `null` 语义、最小 JSON 示例。
- 补充持仓窗口贡献法口径：`ads_backtest_position_daily.weight * dwd_stock_eod_price.ret_1d`，并要求记录归因覆盖率。
- 补充展示 / 辅助基准必须固化到 `benchmark_nav.csv` 和 `metrics.json.artifact_manifest`。
- 补充 AI `auto` 模式 timeout / retry / fallback 规则，`llm` 模式失败非零退出。
- 标记并压缩 `DECISION-20260602-05`：该旧口径已被 `DECISION-20260602-06` supersede，正文不再保留废弃 benchmark 口径的肯定表述。
- 将 PRD §6 失败触发条件中的沪深300比较改写为“展示对比基准”表述，避免被误读为评估主基准。

### 重要上下文

- owner 明确要求第一个 review 问题按 Claude 建议处理，不再按原“沪深300作为主基准”的说法执行。
- 后续实现 PR 不应把 `08/09` 的 `p_benchmark` 改为 `000300.SH`；应保持 / 明确为 `000852.SH`，并由报告脚本查询和固化 `000300.SH` 展示对比基准。
- 本次仍只修 PRD 和记忆/TODO，未改 runner SQL 或 `render_report.py`。

### 改动文件

- `docs/prd/PRD_20260602_03_策略1中文报告归因分析.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 文档型变更；未执行 SQL。

### 阻塞项

- 无。

### 下一步建议

- 请 review PR #18 最新 PRD 文案；通过后再进入报告实现 PR。
- 实现时优先做 `benchmark_nav.csv`、`diagnosis_evidence.json` schema 校验和 deterministic 证据摘要，再接 LLM。

### 已更新记忆文件

- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `IMPLEMENTATION_STATUS.md`
- `OPEN_QUESTIONS.md`
- `DECISION_LOG.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

---

## 交接条目

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: 策略 1 中文报告与归因分析 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260602_03_策略1中文报告归因分析.md`。
- PRD 定义策略 1 报告增强：报告中文化、评估主基准中证1000 `000852.SH`、展示对比基准沪深300 `000300.SH`、辅助风格基准中证500、交易/持仓/NAV 附件、回撤/快速亏损证据包、AI 诊断。
- 追加 `DECISION-20260602-05`，记录策略 1 报告主基准与中文归因口径；该决策后续被 `DECISION-20260602-06` 修订。
- 更新 `OPEN_QUESTIONS.md` / `TODO.md` / 项目记忆：报告 PRD 已定待实现；OQ-010 仍保留调仓频率、持股数、单票权重上限等 open 项。

### 重要上下文

- 本次只写 PRD 和状态同步，未修改 runner SQL 或 `render_report.py` 行为。
- 当前可执行 runner 仍使用旧报告脚本和旧示例基准；后续实现 PR 需要改 `08/09/10`、`scripts/strategy1/render_report.py` 和 README。
- AI 诊断被设计为先生成 `diagnosis_evidence.json`，再基于证据输出中文分析；无新闻/公告等外部证据时必须明确“当前证据不足”，不得编造外部原因。

### 改动文件

- `docs/prd/PRD_20260602_03_策略1中文报告归因分析.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 文档型变更；未执行 SQL。

### 阻塞项

- 无。

### 下一步建议

- 实现策略 1 报告增强：保持 / 明确 `p_benchmark='000852.SH'` 为评估主基准，扩展中文报告、沪深300展示对比、附件、证据包和 AI 诊断，更新 `10_qa_runner_outputs.sql` 与 README。
- OQ-010 分项成本已在 runner SQL 中实现；报告实现时沿用该分项成本展示，避免回退到旧 `p_cost_bps=30` 示例口径。

### 已更新记忆文件

- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `IMPLEMENTATION_STATUS.md`
- `OPEN_QUESTIONS.md`
- `DECISION_LOG.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

---

## 交接条目

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: s1_bqml_20260601_01 / bt_s1_bqml_20260601_01
相关 issue/PR: PR #23 / 策略 1 报告 GCS uploaded 模式

### 已完成工作

- 确认 PR #23 已合并到 `main`，本地 `main` fast-forward 到合并提交。
- 删除已合并且不再使用的 PR #23 分支 `feat/implement-gcs-upload-runbook`：先移除干净 worktree `/Users/luna/Desktop/git/quant-ashare-wt`，再删除本地与远端分支。
- 创建 `gs://ashare-artifacts` bucket（`ASIA-EAST2`，project=`data-aquarium`）。
- 配置本机 Application Default Credentials，quota project 为 `data-aquarium`；未向仓库写入任何凭据。
- 去掉 `--skip-gcs-upload` 重跑 `scripts/strategy1/render_report.py`，GCS 上传完成并回写 ADS。

### 重要上下文

- 本机 ADC 已可供 Google client libraries 使用；`render_report.py` 现在可通过默认凭据访问 BigQuery 与 GCS，不再依赖 gcloud token fallback。
- 报告 GCS 路径：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_bqml_20260601_01/backtest_id=bt_s1_bqml_20260601_01`。
- ADS `metrics_json` 当前为 `report_upload_status='uploaded'`，`report_uri` 为上述 GCS 路径，`local_report_path` 仍保留本地镜像路径，`ai_analysis_status='evidence_only'`。
- 重跑 `render_report.py` 时仍出现 Python 3.9 版本 warning、未安装 BigQuery Storage 模块 warning，以及 Matplotlib 缺 CJK 字体的图表字形 warning；这些不影响本次 GCS/ADS/QA 验收，但图表中文字形后续可单独优化。

### 改动文件

- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `gcloud auth application-default print-access-token >/dev/null`：通过。
- Python `google.auth.default()` + BigQuery/Storage client 访问 `ashare_ads` dataset 与 `ashare-artifacts` bucket：通过。
- `python scripts/strategy1/render_report.py --project data-aquarium --backtest-id bt_s1_bqml_20260601_01 --run-id s1_bqml_20260601_01 --artifact-base-uri gs://ashare-artifacts/reports/strategy1 --local-mirror-root reports/strategy1 --ai-analysis-mode evidence_only`：通过，上传报告产物并回写 ADS。
- `gcloud storage ls gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_bqml_20260601_01/backtest_id=bt_s1_bqml_20260601_01/`：可列出 `report.md`、`report.html`、`metrics.json`、`nav.csv`、`trades.csv`、`positions.csv`、`benchmark_nav.csv`、`diagnosis_evidence.json`、`ai_analysis.json`、图表 assets 等产物。
- ADS 查询确认 `report_upload_status='uploaded'`、`report_uri` 非空、`report.md`/`report.html`/`diagnosis_evidence.json` 均在 manifest 中。
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql`：全部 ASSERT 通过。

### 阻塞项

- 无。

### 下一步建议

- 进入策略 1 模型质量诊断：先做信号/标签/选股/组合归因诊断，不直接改模型参数；确认问题来自反向信号、标签定义、股票池/样本过滤、成本换手、市场风格暴露还是执行口径。
- 可单独补报告图表 CJK 字体配置，消除 Matplotlib 中文字形 warning。

### 已更新记忆文件

- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

---

## 交接条目

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / 策略 1 模型质量诊断 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260602_04_策略1模型质量诊断.md`。
- PRD 将下一步 OQ-010 工作收敛为“先诊断、后实验”：先诊断 signal / label / sample-universe / candidate / portfolio / cost / style，再进入反向分数、标签、参数或特征实验。
- PRD 定义后续实现交付物：`sql/ml/strategy1/11_model_quality_diagnostics.sql`、`scripts/strategy1/diagnose_model_quality.py`、`sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`、诊断 artifact 和 `metrics_json` 诊断状态。
- 更新 `TODO.md`，将 P0 模型质量工作拆成“实现模型质量诊断”和“基于诊断做参数/模型实验”。
- 更新 OQ-010 记忆状态：成本、报告和诊断 PRD 已完成；仍 open 的是诊断实现与后续调仓/持仓参数和模型质量实验。

### 重要上下文

- 本次只写 PRD 和记忆/TODO，未实现诊断 SQL、Python 脚本或 QA。
- PRD 明确不直接修改模型、标签、选股、持仓或成本，避免根据 2025 单次 test 结果直接调参。
- 当前 baseline 仍是 `run_id=s1_bqml_20260601_01` / `backtest_id=bt_s1_bqml_20260601_01`；诊断实现必须参数化 run/backtest，不得写死。

### 改动文件

- `docs/prd/PRD_20260602_04_策略1模型质量诊断.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 文档型变更；未执行 SQL。
- 计划执行 `git diff --check` 后提交。

### 阻塞项

- 无。

### 下一步建议

- 实现 `PRD_20260602_04`：先写诊断 SQL / Python artifact 生成 / QA，再基于诊断结论决定是否做反向分数、标签 horizon、持股数/权重上限、调仓频率或特征扩展实验。

### 已更新记忆文件

- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `IMPLEMENTATION_STATUS.md`
- `OPEN_QUESTIONS.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

---

## 交接条目

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #24 / issuecomment-4602768596

### 已完成工作

- 查看 PR #24 comment `4602768596`，认可 1 个中优先级和 2 个低优先级建议。
- 修订 `docs/prd/PRD_20260602_04_策略1模型质量诊断.md`：
  - FR-DIAG-2 明确 RankIC 为 Spearman rank correlation。
  - FR-DIAG-3 明确 score bucket 按每个交易日的日截面 quantile 分组。
  - FR-DIAG-5 明确 `sample_filter_risk` 的 10% 阈值只针对不可解释排除率，并定义可解释 / 不可解释排除。
- 同步更新实现状态和当前交接摘要。

### 重要上下文

- 本次仍是文档型修订，未实现诊断 SQL、Python 脚本或 QA。
- 修订不改变“先诊断、后调参”的方案方向，只降低后续实现歧义。

### 改动文件

- `docs/prd/PRD_20260602_04_策略1模型质量诊断.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- 文档型变更；未执行 SQL。
- 计划执行 `git diff --check` 后提交。

### 阻塞项

- 无。

### 下一步建议

- 推送 PR #24 修订后，可继续 review / 合并；合并后开始实现模型质量诊断 SQL、artifact 生成和 QA。

### 已更新记忆文件

- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`

---

日期: 2026-06-02
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: s1_bqml_20260601_01 / bt_s1_bqml_20260601_01
相关 issue/PR: OQ-010 / 策略 1 预测池口径修正 PRD

### 已完成工作

- 新增 PRD：`docs/prd/PRD_20260602_05_策略1预测池口径修正.md`。
- PRD 明确只处理 valid/test 预测池 live-available 口径，不同时处理 `12` QA bug、信号反向、标签重做、模型类型或组合参数。
- 根据已执行诊断结果记录根因：当前主结论为 `sample_filter_risk` high；valid/test 预测池由 `sample_trainable_default` 派生，依赖 `label_entry_tradable` / `label_valid_5d` 等 live 不可得字段。
- PRD 固化三类 mask：`train_fit_mask`、`predict_live_available_mask`、`eval_label_available_mask`；要求 train 用 trainable labeled sample，valid/test 预测用 t 日 live-available feature universe，标签有效性只用于事后评价。
- 同步 `TODO.md`、`OPEN_QUESTIONS.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要。

### 重要上下文

- 当前诊断 local smoke 与 uploaded 模式已成功，GCS/ADS 回写成功；但 `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql` 因 `split_tag` 歧义未通过，需先单独 bugfix。
- PRD 05 不承诺策略收益改善，只要求评估口径正确；修正后需要用新 `run_id/backtest_id` 重跑 runner、报告和诊断。

### 改动文件

- `docs/prd/PRD_20260602_05_策略1预测池口径修正.md`
- `TODO.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`
- 文档/记忆型变更，未执行 SQL。

### 阻塞项

- 无文档阻塞。
- 实现前需先修 `12_qa_model_diagnosis_outputs.sql` 的 `split_tag` 歧义，以便诊断 QA 可用。

### 下一步建议

- 提交 / 提 PR 前可先 review PRD 05 范围。
- 单独小 PR 修 `12` QA bug。
- 按 PRD 05 实现 runner 01/03/04、诊断 11/12 和 `diagnose_model_quality.py` 的预测池 coverage 证据。

### 已更新记忆文件

- `OPEN_QUESTIONS.md`
- `PROJECT_CONTEXT.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

---

## 交接条目

日期: 2026-06-03
Agent ID: Kimi
Agent 实例 ID: Kimi Code CLI
模型: Kimi-k2.6
运行环境: Kimi Code CLI
Run ID: s1_bqml_livepool_oriented_20260603_01 / s1_bqml_livepool_revscore_20260603_01
相关 issue/PR: gthbj/quant-ashare#27~#32 / 诊断 QA 修复 + livepool 口径 + score orientation

### 已完成工作

- 确认 `origin/main`（8564311）已包含并合并 PR #27/28（`split_tag` 歧义修复）、PR #29/30（live-available 预测池口径）、PR #32（score orientation 校准）。本地分支 `codex/fix-diagnosis-qa-livepool` 已与 `origin/main` 对齐。
- 验证 `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql` 全部断言通过（ oriented run_id `s1_bqml_livepool_oriented_20260603_01`）：QA-DIAG-1~5 诊断状态/版本/结论/置信度/产物清单通过；QA-DIAG-6 valid/test 各 >=100 预测交易日通过；QA-DIAG-7a~7c 预测/候选/回测存在性通过；QA-POOL-1~6 训练/预测池口径语义通过；QA-ORIENT-DIAG-1 `score_orientation` 登记通过。
- 2026-06-03 已完成 livepool reverse-score shadow run（`s1_bqml_livepool_revscore_20260603_01`）：复制 3,055,781 训练面板行，插入 1,056,716 条反向预测（score = 1.0 - source_score），完整执行 05→08→09→report→10→diagnosis→12，全部 QA 通过；shadow backtest total_return=0.2787（source run 为 -0.9712），验证方向反转可将策略从亏损转为正收益。
- 更新 `TODO.md`：将诊断 QA 修复、livepool 预测池口径、score orientation 校准标记为已完成。
- 更新 `IMPLEMENTATION_STATUS.md`：刷新「进行中」和「未开始」状态，明确 split_tag 修复、livepool 口径、score orientation 均已实现并验证。
- 更新 `OPEN_QUESTIONS.md`：刷新 OQ-010 状态，明确诊断、预测池口径和分数方向校准均已完成。
- 更新 `AGENT_HANDOFF.md` 当前交接摘要和待 owner 确认项。

### 重要上下文

- 当前 `main`（8564311）已是全量合并后的最新状态；`codex/fix-diagnosis-qa-livepool` 分支无代码改动，仅文档/记忆更新。
- `ads_model_prediction_daily` 当前仅有 oriented run（`s1_bqml_livepool_oriented_20260603_01`）的 1,056,716 行预测；source run 预测已被覆盖/清理。
- 诊断 QA 全部通过后，管线已具备：训练 → 选型（含方向校准）→ 预测（含 live-available 池）→ 候选 → 组合 → 回测 → 报告 → 诊断 → QA 验收的完整闭环。

### 改动文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`：全部 11 个 ASSERT successful + 1 条 manual_check 输出。
- shadow run 端到端验证：05→08→09→report→10→diagnosis→12 全部通过。

### 阻塞项

- 无。

### 下一步建议

- 合并本 PR（文档/记忆状态同步）。
- 由 owner 决策 OQ-010 剩余参数（调仓频率、持股数/单票权重上限）和模型质量迭代方向（特征/标签/选股口径实验）。
- 如需新一轮正式 run，使用新的 `run_id/backtest_id` 执行完整 01→12 流程。

### 已更新记忆文件

- `TODO.md`
- `IMPLEMENTATION_STATUS.md`
- `OPEN_QUESTIONS.md`
- `AGENT_HANDOFF.md`

---

---

## 交接条目

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / 策略 1 首轮质量迭代实验 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`。
- PRD 将 OQ-010 剩余项拆为四阶段实验：组合集中度（持股数 / 单票权重）、调仓频率、标签 horizon、财务特征。
- PRD 固定当前 oriented run 为比较基线，并要求后续实现产出实验 manifest、独立 run/backtest、中文对比报告、10/12 QA 和诊断 artifact。
- 更新 `TODO.md`，把 OQ-010 下一步从“owner 决策”收敛为“按 PRD review 结果实现实验参数化与第一轮实验”。
- 更新 `OPEN_QUESTIONS.md`，记录首轮质量迭代 PRD 已新增、仍待 owner review。
- 更新 `MEMORY_INDEX.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md` 与当前交接摘要，清理旧的“诊断 QA 未通过 / 预测池待实现”表述。

### 重要上下文

- 本次只写 PRD 和记忆/TODO，未修改 runner SQL 或 Python。
- PRD 推荐第一轮继续使用 BigQuery ML `LOGISTIC_REG`，不切换模型族；股票池仍为沪深主板。
- PRD 推荐财务特征第一轮只加入比率、可用性和新鲜度字段，不加入原始金额字段，避免缺失和规模暴露直接污染预测池。

### 改动文件

- `docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`
- 文档 / 记忆更新，未执行 SQL。

### 阻塞项

- 无。

### 下一步建议

- owner review 首轮实验矩阵。
- 根据 review 结果实现实验参数化、manifest 和对比报告。
- 按阶段执行 OQ-010 第一轮实验，并用 10/12 QA 与诊断 artifact 验收。

### 已更新记忆文件

- `TODO.md`
- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`

---

---

---

## 交接条目

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: 记忆瘦身 / handoff 归档

### 已完成工作

- 按 `.agent/memory/UPDATE_PROTOCOL.md` 的归档规则，创建 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。
- 将 `.agent/memory/AGENT_HANDOFF.md` 中较早的 2026-06 历史交接块迁入 6 月归档。
- 主 handoff 文件仅保留当前交接摘要、最近几段交接和本次清理交接，降低常规启动读取成本。

### 重要上下文

- 本次为记忆维护，不涉及 SQL、BigQuery 数据、策略逻辑或 PRD 内容变更。
- 历史交接仍可通过 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md` 审计追溯。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`

### 测试 / 验证

- `git diff --check`
- `wc -l .agent/memory/AGENT_HANDOFF.md .agent/memory/archive/AGENT_HANDOFF_2026-06.md`

### 阻塞项

- 无。

### 下一步建议

- 继续保持 `AGENT_HANDOFF.md` 只存摘要和最近 2-3 条交接；更早条目按月归档。

### 已更新记忆文件

- `AGENT_HANDOFF.md`

---

---

## 2026-06-04 memory cleanup archived entries

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #42 / PR #44 / PR #46 / OQ-005

### 已完成工作

- 为合并 PR #42，将最新 `origin/main` 合入 `feat/gcp-pipeline-phase0`，解决 `.agent/memory/**` 与 `TODO.md` 冲突。
- 保留 `main` 已新增的 OQ-010 并发调度 Phase 1 状态和文件，同时补回 OQ-005 Phase 0 实现分支状态。
- 记录 PR #44 已合入 #42；PR #46 因冲突已手动整合其有效修复并关闭。
- 同步 `TODO.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要。

### 重要上下文

- OQ-005 仍为 open。当前只完成 Phase 0 采集侧基础代码与 review 修复，Cloud Run Jobs、Dataform P0 转换和 Composer DAG 仍待后续实现。
- `endpoint` 是 Tushare API endpoint，`partition_endpoint` 是 GCS Hive 分区 `endpoint=` 值；`stock_basic` 变体必须用后者分开写入，避免下游 `dim_stock` 消费不到 listed/delisted 分区。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

### 测试 / 验证

- `git diff --check`
- `git diff --cached --check`
- conflict marker scan
- PR #42 mergeability check

### 阻塞项

- 无。

### 下一步建议

- 合并 PR #42 后继续实现 Cloud Run Jobs 镜像/任务、Dataform P0 转换、Composer DAG 与端到端 dry-run。


---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #45 / issuecomment-4612729919 / OQ-010

### 已完成工作

- 跟进 PR #45 最新 review comment `issuecomment-4612729919`，直接修复并发调度 Phase 1 实现。
- 将 SQL `DECLARE p_* DEFAULT` 参数注入改为强校验：扫描所有可注入参数，缺少 manifest/default 值、格式不匹配、类型不匹配或必需隔离参数缺失时直接失败。
- dry-run 新增可执行实验 SQL 参数注入预检；blocked placeholder 实验仅打印计划，不用 placeholder 做类型预检。
- 锁释放改为获取 GCS lock 后统一 `finally` 释放；`running` 状态写失败、step 执行失败或异常均不会泄漏 GCS lock。
- heartbeat 线程改为非 daemon，step 结束后先停止并 join，再写 `succeeded` / `failed`，避免 heartbeat 后写 `running` 覆盖 terminal status。
- 状态表 DDL 从 `CREATE OR REPLACE TABLE` 改为 `CREATE TABLE IF NOT EXISTS`，保留 audit/resume 历史。
- 文件编号避冲突：状态表 DDL 使用 `sql/meta/02_strategy1_experiment_run_status.sql`；并发 QA 使用 `sql/qa/07_strategy1_experiment_concurrency_checks.sql`，并同步文档/记忆/TODO 引用。

### 重要上下文

- 本次没有执行 BigQuery 实验、没有触碰正在运行的 A3 实验、没有删除或覆盖 `reports/strategy1` 已有产物。
- 状态表仍只用于审计和 resume 输入；GCS object generation 条件操作仍是锁安全边界。
- 后续若再调整 SQL runner，必须保持 dry-run 参数注入预检，否则会重新暴露静默沿用默认 `run_id` / `backtest_id` 的风险。

### 改动文件

- `scripts/strategy1/run_oq010_experiments.py`
- `sql/meta/02_strategy1_experiment_run_status.sql`
- `sql/qa/07_strategy1_experiment_concurrency_checks.sql`
- `docs/策略1实验并发调度器运行手册.md`
- `docs/prd/PRD_20260603_05_策略1实验并发调度与隔离.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/run_oq010_experiments.py`
- `python3 scripts/strategy1/run_oq010_experiments.py --dry-run --stage-id stage_a`
- `python3 scripts/strategy1/run_oq010_experiments.py --dry-run --experiment-id oq010_a1_n10_w10`
- `python3 scripts/strategy1/run_oq010_experiments.py --dry-run`
- 直接参数注入断言：确认 `05_build_candidates.sql` 的 `p_run_id` 被替换为实验 run_id，未保留 SQL 默认值。
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 等 PR #45 合并后再按 owner 决定是否在真实 OQ-010 实验中启用并发；首次实跑仍建议 `max_parallel_backtest=1`。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`（追加 `DECISION-20260603-05`，并同步本 PR 内改名后的文件路径引用）
- `.agent/memory/OPEN_QUESTIONS.md`（仅同步本 PR 内改名后的文件路径引用）
- `TODO.md`


---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #41 / issuecomment-4612007495 / OQ-010

### 已完成工作

- 跟进 PR #41 review comment `issuecomment-4612007495`。
- 将策略 1 实验并发调度与隔离 PRD 从 `_04_` 改名为 `_05_`，避免与已合并 PR #40 的 `PRD_20260603_04_ODS外部表ParquetSchema修复.md` 撞号。
- rebase 到当前 `origin/main`，保留 #40 的 ODS schema 修复记忆/TODO，并重新接入 OQ-010 并发 PRD 状态。
- 在 PRD 第 6 章补充真实原子锁获取机制：P0 推荐 GCS object `ifGenerationMatch=0` create-if-not-exists，BigQuery 状态表只做审计和 resume 输入。
- 在 PRD 中补充 `lock_owner`、`lock_acquired_at`、`lock_expires_at`、`last_heartbeat_at`、lease TTL、heartbeat、stale lock reclaim 和多调度器约束。
- 在调度器设计中补充 `--scheduler-instance-id`、`--lock-ttl-minutes` 和后续 Cloud Composer / Airflow 映射。
- 同步 `TODO.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`KNOWN_CONSTRAINTS.md`、`OPEN_QUESTIONS.md`、`MEMORY_INDEX.md` 和当前交接摘要。

### 重要上下文

- 本次仍只修订 PRD 和记忆/TODO，未修改 SQL runner、未执行 BigQuery、未触碰正在运行的 A3 实验，也未改 `reports/strategy1`。
- 当前 runner 仍遵守“不并发”约束；PRD 合并不等于允许并发，必须等状态表、GCS 原子锁、调度器和并发 QA 实现并验收后再启用。

### 改动文件

- `docs/prd/PRD_20260603_05_策略1实验并发调度与隔离.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- `git diff --check`
- `git diff --cached --check`
- conflict marker scan
- PRD 编号复核

### 阻塞项

- 无。

### 下一步建议

- 合并 PR #41。
- 后续实现 `ashare_meta.strategy1_experiment_run_status`、GCS lock、`scripts/strategy1/run_oq010_experiments.py`、runner 参数接口和 `sql/qa/07_strategy1_experiment_concurrency_checks.sql`。


---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #40 / issuecomment-4611909699 / OQ-012

### 已完成工作

- 跟进 PR #40 review comment `issuecomment-4611909699` 的 1 个 P2 和 2 个 P3 建议。
- 在 `docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md` 补充 backup write-once 规则：每个 `(endpoint, partition_date, source_uri)` 已存在 backup 时不得覆盖，重复执行只记录 `backup_status='existing'`。
- 在 Phase 0 / 发布规则中补充 `ok` 文件跳过重写、跳过发布，保证修复脚本幂等。
- 在临时 BigQuery external table QA 中补充 schema 必须显式取自 schema contract，禁止 autodetect。
- 在类型策略 / 风险控制中补充 INT→FLOAT64 仅对 `<2^53` 整数无损，超阈值字段进入 `manual_review`。
- 同步 `DECISION_LOG.md`、`KNOWN_CONSTRAINTS.md`、`IMPLEMENTATION_STATUS.md`、`TODO.md` 和当前交接摘要。

### 重要上下文

- PR #40 review 结论为可以合并，无阻断项。
- 本次仍只修订 PRD 和记忆/TODO，未修改 GCS、BigQuery ODS 外部表或生产数据。

### 改动文件

- `docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`

### 测试 / 验证

- `git diff --check`
- `git diff --cached --check`
- conflict marker / credential keyword scan

### 阻塞项

- 无。

### 下一步建议

- 合并 PR #40。
- 合并后实现 schema contract、repair manifest 和 `ods_tushare_stk_limit` staging 修复验证。

### 已更新记忆文件

- `TODO.md`
- `AGENT_HANDOFF.md`
- `DECISION_LOG.md`
- `IMPLEMENTATION_STATUS.md`
- `KNOWN_CONSTRAINTS.md`


---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-012 / ODS 外部表 Parquet schema 修复 PRD

### 已完成工作

- 新建 worktree `/Users/luna/Desktop/git/quant-ashare-ods-parquet-schema-repair-prd` 和分支 `codex/prd-ods-parquet-schema-repair`。
- 新增 `docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md`，定义 10 张 ODS 外部表 Parquet 物理类型 mismatch 的修复方案。
- PRD 明确默认修复路径为 schema contract → GCS 原 Parquet 读取 → 显式 cast → staging → 临时 external table 验证 → backup → 发布正式 prefix → 正式 ODS QA。
- PRD 明确 API 重拉只作为原文件损坏、缺失、行数无法复原或 owner 明确要求的补救路径，不作为默认修复方式。
- PRD 明确优先修当前 P0 源表 `ods_tushare_stk_limit`，再分批修 `limit_list_d`、`moneyflow`、`margin_detail`、`dividend`、`margin`、`daily_info`、`sz_daily_info`、`fina_audit`、`stk_rewards`。
- 新增 `DECISION-20260603-03` 和 OQ-012，更新 `KNOWN_CONSTRAINTS.md`、`ARCHITECTURE_MEMORY.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`MEMORY_INDEX.md` 和 `TODO.md`。

### 重要上下文

- 本次只写 PRD 和记忆/TODO，未修改 GCS、BigQuery ODS 外部表或生产数据。
- 10 张表中当前策略相关的只有 `ods_tushare_stk_limit`；现有 DWD 只读取 `up_limit/down_limit`，但 `pre_close` mismatch 仍需修复，避免未来全字段读取或扩展失败。
- API 6000 行上限和值级差异问题继续按数据审查流程复核，不纳入本 PRD 的默认修复输入。

### 改动文件

- `docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review 并合并本 PRD。
- 合并后先实现 schema contract、repair manifest 和 `ods_tushare_stk_limit` 的 staging 修复验证。

### 已更新记忆文件

- `TODO.md`
- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `ARCHITECTURE_MEMORY.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `DECISION_LOG.md`
- `KNOWN_CONSTRAINTS.md`
- `AGENT_HANDOFF.md`


---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #39 / issuecomment-4611682018 / OQ-005

### 已完成工作

- 跟进 PR #39 review comment `issuecomment-4611682018` 的 2 个低优先级建议。
- 在 `docs/prd/PRD_20260603_03_GCP数据流水线方案.md` §6.4 明确财务报告期 endpoint 每日执行近期公告 / 修正滚动检查，有新增或修正行时写回对应报告期分区；空返回记录 `expected_empty` / `empty_return` event，正式 GCS prefix 保持无新增对象。
- 在 PRD Phase 1 交付与验收中补充 Cloud Scheduler 与 Composer 两种触发入口，明确 Cloud Run Jobs 可由 Cloud Scheduler 或 Composer 触发并写入统一 run id / execution id。
- 同步 `TODO.md`、`OPEN_QUESTIONS.md`、`PROJECT_CONTEXT.md`、`ARCHITECTURE_MEMORY.md`、`IMPLEMENTATION_STATUS.md`、`MEMORY_INDEX.md` 和当前交接摘要。

### 重要上下文

- PR #39 review 结论为可以合并、0 个阻塞发现。
- 本次只修订 PRD 与记忆/TODO，未实现 Cloud Run、Dataform 或 Composer。
- 架构决策和首批 14 张 ODS 采集范围未改变。

### 改动文件

- `docs/prd/PRD_20260603_03_GCP数据流水线方案.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review 并合并 PR #39。
- 合并后按 Phase 0 实现 `configs/ingestion/ods_current_scope_v0.yml` 与首批 14 张 ODS schema contract。

### 已更新记忆文件

- `TODO.md`
- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `ARCHITECTURE_MEMORY.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`


---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #45 / OQ-010 实验并发调度 Phase 1

### 已完成工作

- 跟进 PR #45 最新 review comment，修复 OQ-010 并发调度器的 GCS lock 安全问题。
- `scripts/strategy1/run_oq010_experiments.py` 的 GCS lock acquire 记录 `acquired_at`、`lease_expires_at` 和 object generation。
- stale lock reclaim 改为读取并删除同一 generation：只删除刚检查过且已过期的 lock object，避免多个调度器竞争时误删对方刚创建的新锁。
- heartbeat 和 release 也改为 generation 条件操作，旧进程不会刷新或删除新 generation 的 lock object。
- 状态表 upsert 支持写入真实 `lock_acquired_at`、`lock_expires_at` 和 `last_heartbeat_at`；running 状态写入失败仍会释放 GCS lock 并取消 step。
- heartbeat loop 同步刷新 BigQuery 状态表中的 `last_heartbeat_at` 和 `lock_expires_at`，让审计字段与 GCS lease 对齐。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`KNOWN_CONSTRAINTS.md` 和当前交接摘要。

### 重要上下文

- 本次未执行 BigQuery，不触碰正在运行的 A3 实验，不删除或覆盖 `reports/strategy1` 下已有产物。
- 该修复只收口 PR #45 Phase 1 锁安全与审计字段；Phase 2-4 仍待后续实现和端到端验收。

### 改动文件

- `scripts/strategy1/run_oq010_experiments.py`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/run_oq010_experiments.py`
- `git diff --check origin/main..HEAD`
- `git diff --check`
- `python3 scripts/strategy1/run_oq010_experiments.py --dry-run --stage-id stage_a`
- `python3 scripts/strategy1/run_oq010_experiments.py --dry-run --experiment-id oq010_a1_n10_w10`
- fake GCS blob 测试：stale reclaim 使用被检查到的 generation 条件删除，非过期锁不删除。

### 阻塞项

- 无。

### 下一步建议

- Review PR #45 最新提交后合并。
- 合并后先继续 dry-run / 单实验执行验证，再按 Phase 2-4 推进 portfolio-only 并发、08 ledger 并发和 retrain 混合队列。

### 已更新记忆文件

- `TODO.md`
- `IMPLEMENTATION_STATUS.md`
- `KNOWN_CONSTRAINTS.md`
- `AGENT_HANDOFF.md`


---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-005 / GCP 数据流水线 PRD

### 已完成工作

- 新建 worktree `/Users/luna/Desktop/git/quant-ashare-gcp-data-pipeline-prd` 和分支 `codex/prd-gcp-data-pipeline`。
- 新增 `docs/prd/PRD_20260603_03_GCP数据流水线方案.md`，定义长期生产架构：Cloud Run Jobs 负责 Tushare/Tinyshare→GCS Parquet，Dataform / BigQuery Studio pipeline 负责 ODS→DIM/DWD/DWS/ADS，Cloud Composer 负责调度、重试、补跑和告警。
- 从当前 SQL 引用提取首批每日生产采集范围：`daily`、`adj_factor`、`stk_limit`、`suspend_d`、`daily_basic`、`index_daily`、`index_dailybasic`、`stock_basic`、`trade_cal`、`namechange`、`fina_indicator`、`income`、`balancesheet`、`cashflow`；明确未消费 ODS 暂不安排定时任务。
- 追加 `DECISION-20260603-02`，同步 `OPEN_QUESTIONS.md`、`ARCHITECTURE_MEMORY.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`MEMORY_INDEX.md`、`TODO.md` 和当前交接摘要。

### 重要上下文

- 本次是 PRD / 记忆 / 决策更新，未实现 Cloud Run、Dataform、Composer 或采集代码。
- OQ-005 仍标记为 open，状态为 PRD 草案已新增，待 review/合并与实施后关闭。
- PRD 明确首批生产采集不做 57 张 ODS 全量调度；新增 endpoint 必须先更新采集 manifest、schema contract、单位契约和 QA。

### 改动文件

- `docs/prd/PRD_20260603_03_GCP数据流水线方案.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- review/合并本 PRD。
- 合并后按 Phase 0 新增 `configs/ingestion/ods_current_scope_v0.yml` 与首批 14 张 ODS schema contract。
- 后续实现 Cloud Run Jobs、Dataform P0 转换和 Cloud Composer DAG。

### 已更新记忆文件

- `TODO.md`
- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `ARCHITECTURE_MEMORY.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `DECISION_LOG.md`
- `AGENT_HANDOFF.md`


---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: ODS/GCS 数据审查提示词直接入 main

### 已完成工作

- 新增根目录 `data_audit/`，作为 ODS/GCS 数据审查入口。
- 新增 `data_audit/ODS_GCS_DATA_AUDIT_PROMPT.md`，提示词要求审查 Agent 通过 BigQuery ODS 外部表和 Tushare/Tinyshare API 做只读审查，审查范围限定 2019-01-01 及之后。
- 明确审查脚本由执行 Agent 自行编写；若请求参数、并发、限速、schema 检测、报告生成等审查代码有问题，执行 Agent 应自行修正审查代码后继续。
- 明确审查脚本必须按 endpoint 或主题拆分，不能把所有接口请求堆进一个大脚本。
- 补充 Tushare 官方数据索引和常见 endpoint 文档链接；要求报告记录每个实际审查 endpoint 使用的官方文档 URL。
- 补充 API 返回行数命中官方单次上限或脚本 page size / limit 时的风险处理：标记 `row_limit_hit=true`、拆细条件复查，复查前不得把响应当完整样本做结论。
- 新增 `data_audit/reports/README.md`，要求审查报告记录审查时间、数据范围、审查 LLM、run id、Git 状态、BQ 范围、token 数量、限速、请求统计、官方文档链接、row limit 命中复查、Findings 和只读声明。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要。

### 重要上下文

- 本次只新增审查提示词和报告目录约定，未执行实际审查，未调用 Tushare/Tinyshare，未修改 GCS 或 BigQuery 生产数据。
- 提示词允许修正审查脚本本身，但禁止补采数据、写伪空 Parquet、改写 raw、重建或覆盖生产表。

### 改动文件

- `data_audit/README.md`
- `data_audit/ODS_GCS_DATA_AUDIT_PROMPT.md`
- `data_audit/reports/README.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 使用 `data_audit/ODS_GCS_DATA_AUDIT_PROMPT.md` 启动审查 Agent。
- 审查完成后将报告写入 `data_audit/reports/`。

### 已更新记忆文件

- `TODO.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`


---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: gthbj/quant-ashare#35 / issuecomment-4609670537

### 已完成工作

- 评估 PR #35 comment 中两条 P2，均认可并修订 PRD。
- 将 `baseline_experiment_id` 改为 canonical `oq010_base_oriented_weekly_h5_n5_w20_pv`，阶段 A/B/C 使用独立 `experiment_id` 并通过 `parent_experiment_id` 追溯来源。
- 明确阶段 C 固定使用阶段 B 晋级调仓频率，以隔离 label horizon 变量；`horizon_natural_frequency` 仅写入 manifest / 报告作解释。
- 同步 `TODO.md`、`OPEN_QUESTIONS.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`MEMORY_INDEX.md` 和当前交接摘要。

### 重要上下文

- 本次仍是 PRD / 记忆修订，未修改 runner SQL 或 Python。
- 后续实现应按修订后的 manifest 字段补 `baseline_experiment_id` / `parent_experiment_id`，并在 QA 中校验阶段 C 频率不被 horizon 硬绑覆盖。

### 改动文件

- `docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`

### 测试 / 验证

- `git diff --check`
- 复核旧 baseline id、旧“建议调仓频率”表头和 conflict marker 均无正文残留。
- 文档 / 记忆更新，未执行 SQL。

### 阻塞项

- 无。

### 下一步建议

- owner 确认修订后的首轮实验矩阵。
- 根据确认结果实现实验参数化、manifest、对比报告和 QA。

### 已更新记忆文件

- `TODO.md`
- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`


---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-005 / PR #39 / `codex/prd-gcp-data-pipeline`

### 已完成工作

- 按 owner 反馈修订 `docs/prd/PRD_20260603_03_GCP数据流水线方案.md`，将正文从“选型说明 / 为什么不”收敛为陈述性目标实现方案。
- 移除“为什么不用纯 BigQuery Scheduled Queries”“为什么不把每日采集写在 BigQuery Studio notebook 里”等反向论证段落。
- 将“非目标”改为“实施边界”，将“推荐架构”改为“目标架构”，并用职责边界表描述 Cloud Run Jobs、Dataform / BigQuery Studio pipeline、Cloud Composer、SQL QA 和 notebook / 手工 SQL 的生产职责。
- 将每日生产请求口径明确为单授权上下文 / 授权代理 + endpoint group 有限并发 + job 级基础节流；数据审查并发模式和生产采集模式分开管理。
- 同步 `TODO.md`、`OPEN_QUESTIONS.md`、`ARCHITECTURE_MEMORY.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`MEMORY_INDEX.md` 和当前交接摘要。

### 重要上下文

- 架构决策未改变：仍是 Cloud Run Jobs 采集、Dataform / BigQuery Studio pipeline 转换、Cloud Composer 编排。
- 首批每日生产采集范围未改变：14 个当前实际消费 ODS endpoint。
- OQ-005 仍为 open，待 PRD review/合并与后续实现后关闭。

### 改动文件

- `docs/prd/PRD_20260603_03_GCP数据流水线方案.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `rg -n "为什么|非目标|不建议|不采用|不要|避免|原因：|暂不|不把|\\b建议\\b|可选|可以|如果|适合" docs/prd/PRD_20260603_03_GCP数据流水线方案.md`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review 并合并 PR #39。
- 合并后按 Phase 0 实现 `configs/ingestion/ods_current_scope_v0.yml` 与首批 14 张 ODS schema contract。

### 已更新记忆文件

- `TODO.md`
- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `ARCHITECTURE_MEMORY.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`


---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: `s1_bqml_oq010_oq010_a0_n5_w20_20260603_01`
相关 issue/PR: `codex/fix-diagnosis-bqstorage-fetch`

### 已完成工作

- 配置本机 BigQuery Storage API 客户端：`data-aquarium` 已启用 `bigquerystorage.googleapis.com`；本机 conda Python 与默认 `python3` 均已安装 `google-cloud-bigquery-storage==2.38.0`。
- 修复 `scripts/strategy1/diagnose_model_quality.py` 的本地大 DataFrame 拉取不稳定问题：
  - `bq_query()` 显式使用 `BigQueryReadClient`，优先 ADC，ADC 不可用时复用 `gcloud auth print-access-token` fallback；缺依赖或无可用凭据时保留 REST fallback。
  - valid/test 预测标签改为一次拉取 2024-2025 后按 `split_tag` 分片，减少重复查询和本地对象复制。
  - feature exposure 改为 BigQuery 侧聚合，只回传聚合统计行，不再把预测池全部特征拉回本地。
- 更新 `scripts/strategy1/requirements.txt`，新增 `google-cloud-bigquery-storage>=2.0`。
- 完成 A0（`oq010_a0_n5_w20`）后续诊断与 QA：`diagnose_model_quality.py` uploaded 模式成功，`sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql` 全部 ASSERT 通过。

### 重要上下文

- A0 已端到端跑通 01-12：`run_id=s1_bqml_oq010_oq010_a0_n5_w20_20260603_01`，`backtest_id=bt_s1_bqml_oq010_oq010_a0_n5_w20_20260603_01`。
- A0 summary：`total_return=0.27868`，`sharpe=0.7258`，`max_drawdown=-0.2217`，相对中证1000 `excess_return=-0.01145`。
- A0 诊断：`primary_diagnosis=usable_signal`，`confidence=low`，valid RankIC mean `0.098666`，test RankIC mean `0.055965`；诊断 artifact 上传至 `gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_bqml_oq010_oq010_a0_n5_w20_20260603_01/backtest_id=bt_s1_bqml_oq010_oq010_a0_n5_w20_20260603_01/model_diagnosis`。
- 继续 A1-A3 前应先合并本修复 PR，避免诊断阶段重复出现本地拉取不稳定。

### 改动文件

- `scripts/strategy1/diagnose_model_quality.py`
- `scripts/strategy1/requirements.txt`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `/Users/luna/miniconda3/bin/python -m py_compile scripts/strategy1/diagnose_model_quality.py scripts/strategy1/render_report.py scripts/strategy1/compare_oq010_experiments.py`
- 仓库 `bq_query()` helper 验证：`rest_endpoint_warning=False`，`BigQueryReadClient` fallback 路径可导入和编译
- 受控预测标签拉取：1,055,737 行，DataFrame 约 195.8 MB，BigQuery Storage 生效
- `fetch_feature_exposure()` 聚合验证：返回 90 行
- A0 `diagnose_model_quality.py`：`diagnose_rc=0`
- A0 `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`：全部 ASSERT successful

### 阻塞项

- 无代码阻塞；需 review/合并诊断稳定性修复 PR 后继续 A1-A3。

### 下一步建议

- 合并诊断稳定性修复 PR。
- 回到 `main` 后继续阶段 A：A1/A2/A3 只跑 05-12，并使用 `prediction_run_id=s1_bqml_livepool_oriented_20260603_01`。
- 阶段 A 全部完成后再运行 `compare_oq010_experiments.py`，只记录事实，不直接下默认参数结论。

### 已更新记忆文件

- `TODO.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`


---

## 交接条目

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #37 / merge commit `57cff1852a9386bbc06a43d35d5e18ea7cc4ec58`

### 已完成工作

- 合并 PR #37 到 `main`：OQ-010 首轮实验 runner 参数化、manifest、对比报告脚本、portfolio-only `prediction_run_id` 复用预测源路径、horizon-aware 诊断/QA 已进入主线。
- rebase PR #37 到最新 `origin/main` 并解决 `TODO.md` 状态记录冲突；保留 ODS/GCS 数据审查完成项和 OQ-010 runner 完成项。
- GitHub merge 后已同步本地 `main`，并通过 `git fetch --prune origin` 清理 `origin/codex/implement-oq010-experiment-runner` stale 引用；远端 PR 分支已删除，本地无该分支。
- 同步 `TODO.md`、`MEMORY_INDEX.md`、`PROJECT_CONTEXT.md`、`OPEN_QUESTIONS.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要：明确 PR #37 已合并，但 OQ-010 端到端实验尚未跑。

### 重要上下文

- OQ-010 实验执行仍未开始；下一步应先跑 A0 基线复现，再跑 A1-A3 portfolio-only 阶段 A 实验。
- A0 可重训，用于对账 5d 基线；A1-A3/B0-B2 只跑 05-12，并用 `p_prediction_run_id` / `--prediction-run-id` 复用预测源。

### 改动文件

- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- PR #37 合并前已通过：JSON 校验、Python `py_compile`、`git diff --check`、BigQuery dry-run。
- 本次状态同步为文档 / 记忆更新，未执行 SQL。

### 阻塞项

- 无代码阻塞；等待执行 OQ-010 第一轮实验。

### 下一步建议

- 执行 OQ-010 阶段 A：先 A0 基线复现，再 A1-A3 portfolio-only。
- 每个实验跑 `10`、`render_report.py`、`diagnose_model_quality.py`、`12`，再用 `compare_oq010_experiments.py` 汇总事实 artifact。


---

## 交接条目

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #37 / issuecomment-4610284627

### 已完成工作

- 处理 PR #37 review feedback：认可组合层实验不应全量重训，并实现 portfolio-only `prediction_run_id` 复用模型/预测路径。
- 更新 `configs/strategy1/oq010_experiments_v0.json`：A0 保留 `requires_retrain=true` 作为 5d 基线复现检查；A1-A3 与 B0-B2 改为 `requires_retrain=false`，并显式记录 `prediction_run_id`。
- 修改 `05/09/10/11/12` 与 `diagnose_model_quality.py`：输出仍写实验 `run_id/backtest_id`，模型注册、预测表、训练面板和分数方向 QA 改查 `prediction_run_id`。
- 修改 `06_build_portfolio_targets.sql`：目标权重按 `min(1 / p_target_holdings, p_max_single_weight)` 计算；实际入选不足时保留现金，不按实际入选数重新满仓。
- 更新 `compare_oq010_experiments.py` 和 README：对比脚本可从 summary 或 manifest 的 `prediction_run_id` 读取 registry 指标；执行说明区分 `requires_retrain=true` 的 01-12 和 `requires_retrain=false` 的 05-12 路径。

### 重要上下文

- 本轮仍未端到端实跑 OQ-010 实验；只做 SQL/Python/manifest/文档修订和 dry-run 级验证。
- Claude review 的 P2 已采纳；P3 目标权重口径选择直接对齐 PRD 留现金要求；P3 基线复现建议通过 A0 保留重训检查承载。

### 改动文件

- `configs/strategy1/oq010_experiments_v0.json`
- `scripts/strategy1/compare_oq010_experiments.py`
- `scripts/strategy1/diagnose_model_quality.py`
- `sql/ml/strategy1/05_build_candidates.sql`
- `sql/ml/strategy1/06_build_portfolio_targets.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/11_model_quality_diagnostics.sql`
- `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m json.tool configs/strategy1/oq010_experiments_v0.json`
- `python3 -m py_compile scripts/strategy1/compare_oq010_experiments.py scripts/strategy1/diagnose_model_quality.py scripts/strategy1/render_report.py`
- `git diff --check`
- BigQuery dry-run：`sql/ml/strategy1/05_build_candidates.sql`、`06_build_portfolio_targets.sql`、`09_build_metrics_and_report_inputs.sql`、`10_qa_runner_outputs.sql`、`11_model_quality_diagnostics.sql`、`12_qa_model_diagnosis_outputs.sql`

### 阻塞项

- 无代码阻塞；尚需提交并推送 PR #37。

### 下一步建议

- 完成验证并推送 PR #37 修订。
- PR 合并后先跑 A0 基线复现，再执行 A1-A3 portfolio-only 实验。


---

---

## 交接条目

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: gthbj/quant-ashare#35

### 已完成工作

- 合并 PR #35 到 `main`：OQ-010 策略 1 首轮质量迭代实验 PRD 已进入主线。
- 同步本地 `main` 到 `origin/main` 合并提交 `8de0498`。
- 确认远端 `codex/prd-oq010-quality-iteration` 分支已删除，并通过 `git fetch --prune origin` 清理本地 remote-tracking 引用。
- 更新 PRD 状态、`TODO.md`、`MEMORY_INDEX.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要，收敛到“按已合并 PRD 实现实验参数化 / manifest / 对比报告 / 第一轮实验”。

### 重要上下文

- PR #35 是文档 / 记忆 PR，未修改 runner SQL 或 Python。
- OQ-010 仍保持 open：首轮实验 PRD 已合并，但默认调仓频率、持股数、单票权重上限和特征 / 标签口径需等实验结果再确认。

### 改动文件

- `docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`

### 测试 / 验证

- `git diff --check`
- 已复核 PRD / TODO / memory 正文无 PR #35 合并前 review 状态残留。

### 阻塞项

- 无。

### 下一步建议

- 开始实现 OQ-010 第一轮实验参数化、manifest、对比报告和 QA。

### 已更新记忆文件

- `TODO.md`
- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`


---

## 交接条目

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / 策略 1 首轮实验非笛卡尔积口径

### 已完成工作

- 按 owner 确认修订 `docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`。
- 明确阶段 A/B/C 不做 `4 * 3 * 3` 全量笛卡尔积；基础执行为阶段 A 固定 weekly + 5d 跑 4 个持股 / 权重实验，再用阶段 A 晋级组合跑阶段 B 的 3 个调仓频率实验，再用阶段 A/B 晋级参数跑阶段 C 的 3 个 label horizon 实验，即 `4 + 3 + 3 = 10`。
- 明确阶段 D 只使用阶段 C 或最终保底复核晋级参数跑 2 个特征集合；完整第一轮基础实验数为 12。
- 增加可选小型交互复核规则：阶段 A/B、A/C 或 B/C 暴露明显交互风险时，补最多 `2 * 2 = 4` 个 pairwise 实验；最终 `2 * 2 * 2` 只在至少两类 pairwise 复核显示明显联动、晋级结果不稳或 owner 明确要求时作为保底复核。
- 补充 `30/5%` 解释：表示目标持股 30 只、单票权重上限 5%，目标单票等权约 3.33%，不是每只买 5%。
- 采纳 PR #36 comment：补充 A/C（持股数 * label horizon）pairwise 复核，防止 5d+weekly 下选出的持股数在 10d/20d 胜出时不再稳。
- 追加 `DECISION-20260603-01`，同步 `TODO.md`、`OPEN_QUESTIONS.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`MEMORY_INDEX.md` 和当前交接摘要。

### 重要上下文

- 本次仍是 PRD / 记忆修订，未修改 runner SQL 或 Python。
- 后续实现 manifest / 对比报告 / QA 应以 `4 + 3 + 3` 为 A/B/C 基础路径、包含阶段 D 为 12 个基础实验；只有满足触发条件时才补 A/B、A/C、B/C pairwise 或最终 `2 * 2 * 2` 复核，不应默认生成 36 个 A/B/C 全量组合。

### 改动文件

- `docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`

### 测试 / 验证

- `git diff --check`
- 已复核 PRD / TODO / memory 中阶段 A/B/C 非笛卡尔积、基础 `4 + 3 + 3`、阶段 D 12 个基础实验、可选 A/B、A/C、B/C `2 * 2` pairwise 和最终 `2 * 2 * 2` 保底复核口径一致。
- 文档 / 记忆更新，未执行 SQL。

### 阻塞项

- 无。

### 下一步建议

- 实现 OQ-010 第一轮实验参数化、manifest、对比报告和 QA。

### 已更新记忆文件

- `TODO.md`
- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`


---

## 交接条目

日期: 2026-06-03
Agent ID: DeepSeek V4
Agent 实例 ID: opencode desktop session
模型: DeepSeek V4
运行环境: opencode desktop
Run ID: —
相关 issue/PR: OQ-010 / PRD_20260603_05 策略1实验并发调度与隔离

### 已完成工作

- 新建 worktree `/Users/luna/Desktop/git/quant-ashare-oq010-parallel-runner` 和分支 `codex/implement-oq010-parallel-runner`（基于 `main`）。
- 新增 `sql/meta/02_strategy1_experiment_run_status.sql`：`ashare_meta.strategy1_experiment_run_status` 状态表 DDL，覆盖实验身份、step 状态、锁信息、产物和调度追踪字段。
- 新增 `scripts/strategy1/run_oq010_experiments.py`：OQ-010 并发调度器，支持全部 PRD 定义 CLI 参数。实现 GCS `ifGenerationMatch=0` 原子锁、lease/heartbeat/stale reclaim、manifest 解析与依赖拓扑排序、BigQuery 状态表 upsert（`MERGE`）、step 执行（bq / python subprocess）、实验参数注入 SQL `DECLARE`、ThreadPoolExecutor 并发控制、backtest semaphore。dry-run 展开完整计划（step 列表、锁 key、ADS 表、并发分组、依赖阻断）。
- 新增 `sql/qa/07_strategy1_experiment_concurrency_checks.sql`：12 个 QA-CONC 断言。
- 新增 `docs/策略1实验并发调度器运行手册.md`。
- 追加 `DECISION-20260603-04`（GCS 原子锁 + BigQuery 状态表架构决策）。
- 更新 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`KNOWN_CONSTRAINTS.md`、`OPEN_QUESTIONS.md`、`AGENT_HANDOFF.md` 和当前交接摘要。

### 重要上下文

- 本次只实现 Phase 1（状态表 DDL、调度器 dry-run、GCS 锁原语、并发 QA SQL），未修改现有 SQL runner 脚本，未在 BigQuery 执行真正并发实验，未触碰正在运行的 A3 实验，未删除或覆盖 `reports/strategy1` 下已有产物。
- 调度器使用 `subprocess` 调用 `bq query` 执行 SQL 和 `python` 执行报告/诊断脚本。SQL 参数注入使用 `_inject_parameter()` 替换 `DECLARE ... DEFAULT` 值。
- GCS 锁 bucket 为 `ashare-artifacts`，锁前缀 `locks/strategy1/oq010/`。锁默认 TTL 30 分钟，heartbeat 每 60 秒刷新。
- Phase 2-4（portfolio-only 并发执行、08 ledger 并发、retrain 训练锁与混合队列）仍待实现和验收。当前约束下禁止本机裸多进程直接并发跑 SQL。

### 改动文件

- `sql/meta/02_strategy1_experiment_run_status.sql`（新）
- `scripts/strategy1/run_oq010_experiments.py`（新）
- `sql/qa/07_strategy1_experiment_concurrency_checks.sql`（新）
- `docs/策略1实验并发调度器运行手册.md`（新）
- `TODO.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/run_oq010_experiments.py`
- `python3 scripts/strategy1/run_oq010_experiments.py --dry-run`（通过：展开 stage_a 多实验计划）
- `python3 scripts/strategy1/run_oq010_experiments.py --experiment-id oq010_a1_n10_w10 --dry-run`（通过：单实验 dry-run）
- `git diff --check`（无 whitespace error）
- 未执行 BigQuery，未触碰 A3 / reports 产物

### 阻塞项

- 无。

### 下一步建议

- Review 并合并本 PR。
- 合并后先用调度器 dry-run 验证同 stage 计划展开，再选择适当实验用调度器执行。
- 后续实现 Phase 2-4 以支持真正的并发执行。


---

## 交接条目

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #37 / `codex/implement-oq010-experiment-runner`

### 已完成工作

- 新增 OQ-010 实验 manifest：`configs/strategy1/oq010_experiments_v0.json`，覆盖阶段 A/B/C/D 基础路径、blocked 依赖和非笛卡尔积执行策略。
- 新增实验对比报告脚本：`scripts/strategy1/compare_oq010_experiments.py`，从 manifest + ADS summary/registry 生成 Markdown/JSON/CSV 对比 artifact。
- 参数化策略 1 runner：`sql/ml/strategy1/01-06/09-12` 支持 `experiment_id`、`experiment_group`、`baseline_experiment_id`、`parent_experiment_id`、`parent_run_id`、`p_rebalance_frequency`、`p_target_holdings`、`p_max_single_weight`、`p_label_horizon`、`p_feature_set_id`，并在 05/09/10/11/12 与诊断脚本支持 portfolio-only `p_prediction_run_id` 复用预测源。
- 扩展 `dws_stock_sample_daily` 输出 10d/20d 标签和收益字段，供 `p_label_horizon` 选择目标列。
- 将 `diagnose_model_quality.py`、`11_model_quality_diagnostics.sql`、`12_qa_model_diagnosis_outputs.sql` 改为 horizon-aware，避免 10d/20d 实验仍按 5d 诊断或 QA。
- 更新 `sql/ml/strategy1/README.md` 的 OQ-010 执行说明和参数表。

### 重要上下文

- 本轮只做实现和 dry-run 验证，尚未在 BigQuery 端到端执行任何 OQ-010 实验。
- 财务特征实验中 `feature_version` 仍保留基础量价样本版本 `strategy1_pv_v0_20260601`，财务扩展通过 `feature_set_id='strategy1_pv_fin_quality_v0_20260603'` 控制；财务 DWS 来源版本为 `fin_default_v0_20260602`。
- `30/5%` 由 `06_build_portfolio_targets.sql` 计算为 `min(1 / target_holdings, max_single_weight)`，30 只时目标单票约 3.33%，实际入选不足持股数时保留现金，不按实际入选数重新满仓、不突破单票上限。

### 改动文件

- `configs/strategy1/oq010_experiments_v0.json`
- `scripts/strategy1/compare_oq010_experiments.py`
- `scripts/strategy1/diagnose_model_quality.py`
- `sql/dws/06_dws_stock_sample_daily.sql`
- `sql/ml/strategy1/01_build_training_panel.sql`
- `sql/ml/strategy1/02_train_bqml_logistic_candidates.sql`
- `sql/ml/strategy1/03_select_model_and_register.sql`
- `sql/ml/strategy1/04_predict_daily.sql`
- `sql/ml/strategy1/05_build_candidates.sql`
- `sql/ml/strategy1/06_build_portfolio_targets.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/11_model_quality_diagnostics.sql`
- `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m json.tool configs/strategy1/oq010_experiments_v0.json`
- `python3 -m py_compile scripts/strategy1/compare_oq010_experiments.py scripts/strategy1/diagnose_model_quality.py scripts/strategy1/render_report.py`
- `git diff --check`
- BigQuery dry-run：`sql/dws/06_dws_stock_sample_daily.sql`、`sql/ml/strategy1/01_build_training_panel.sql`、`02_train_bqml_logistic_candidates.sql`、`03_select_model_and_register.sql`、`04_predict_daily.sql`、`05_build_candidates.sql`、`06_build_portfolio_targets.sql`、`09_build_metrics_and_report_inputs.sql`、`10_qa_runner_outputs.sql`、`11_model_quality_diagnostics.sql`、`12_qa_model_diagnosis_outputs.sql`

### 阻塞项

- 无代码阻塞；尚需 PR review/合并后才能开始端到端实验执行。

### 下一步建议

- Review 并合并 PR #37。
- 合并后先重建 `sql/dws/06_dws_stock_sample_daily.sql`，再按 manifest 阶段 A 开始跑第一批实验。
- 每批实验跑完 `10`、`render_report.py`、`diagnose_model_quality.py`、`12`，再用 `compare_oq010_experiments.py` 生成对比 artifact。

### 已更新记忆文件

- `TODO.md`
- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`

---

## 2026-06-04 post-PRD memory cleanup archived entries

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: stage_c resolved manifest `oq010_stage_c_resolved_20260603_01`
相关 issue/PR: OQ-010 / Stage C runner QA fix

### 已完成工作

- 修复 `scripts/strategy1/run_oq010_experiments.py` 缺少 `google.cloud.bigquery` import，避免写状态表时 `name 'bigquery' is not defined`。
- 修复 OQ-010 调度顺序：`render_report.py` 现在排在 `10_qa_runner_outputs.sql` 之前，符合 README 和 QA 对 report 状态回写的要求。
- 修复 `sql/ml/strategy1/04_predict_daily.sql` 幂等边界：`p_force_replace` 和非 force 存在性检查均按 `run_id` 处理预测，避免同一 run 重训后旧 `model_id` 预测残留。
- 在 `sql/ml/strategy1/10_qa_runner_outputs.sql` 新增预测表 `(predict_date, sec_code)` 唯一性断言。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要。

### 重要上下文

- Stage C 的 C0/C1/C2 已跑到 09；当前失败不是策略结果结论，而是 runner/QA 执行链问题。
- C0 的 `rank_raw=1` 重复由同一 `run_id` 下旧模型预测残留触发；修复后需重新生成预测和下游结果。
- C1/C2 的 report QA 失败由 runner 把 `10_qa_runner_outputs` 放在 `render_report.py` 前触发。

### 改动文件

- `scripts/strategy1/run_oq010_experiments.py`
- `sql/ml/strategy1/04_predict_daily.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`

### 测试 / 验证

- `/Users/luna/miniconda3/bin/python -m py_compile scripts/strategy1/run_oq010_experiments.py`
- `git diff --check`
- Stage C resolved manifest dry-run with `--force-replace --max-parallel 3 --max-parallel-backtest 3`
- BigQuery dry-run: `sql/ml/strategy1/04_predict_daily.sql`
- BigQuery dry-run: `sql/ml/strategy1/10_qa_runner_outputs.sql`

### 阻塞项

- 无代码阻塞；PR 合并后仍需重跑 Stage C 才能判断实验结果。

### 下一步建议

- 合并本修复 PR 后，使用 resolved Stage C manifest 和 `--force-replace` 重跑 C0/C1/C2，完成 report、10 QA、diagnosis 和 12 QA。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: `s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01`
相关 issue/PR: OQ-010 / official baseline run

### 已完成工作

- 在独立 worktree `/Users/luna/Desktop/git/quant-ashare-oq010-parallel-experiments` 运行 OQ-010 正式基线。
- 使用参数 `pv_fin_quality + 30/5% + biweekly + 5d` 重新训练并完整执行 01-12。
- `10_qa_runner_outputs.sql` 和 `12_qa_model_diagnosis_outputs.sql` 均通过。
- 中文报告和模型诊断均已 uploaded 到 GCS。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要。

### 重要上下文

- `backtest_id=bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01`。
- 回测区间为 `2024-01-02` 至 `2025-12-31`，不是只覆盖 2025；2024 仍同时承担 valid/诊断角色。
- 评估主基准为 `000852.SH`；同期沪深300 `000300.SH` 可作为展示对比基准。
- 报告路径：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01/backtest_id=bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01`。

### 改动文件

- `logs/strategy1/oq010_manifests/oq010_official_baseline_pvfq_n30_bw_h5_20260604_01.json`（日志目录，可能被 gitignore 忽略）
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- OQ-010 runner 01-12 全部成功，调度器退出码 0。
- `10_qa_runner_outputs.sql` 通过。
- `12_qa_model_diagnosis_outputs.sql` 通过。
- summary：total_return=41.10%、excess_return=12.09% vs `000852.SH`、Sharpe=1.043、max_drawdown=-14.48%、turnover_annual=19.38、cost_bps=17.0。
- 诊断：`primary_diagnosis=usable_signal`、confidence=`low`；valid RankIC=0.0968，test RankIC=0.0559。

### 阻塞项

- 无运行阻塞；OQ-010 仍需 owner 确认是否正式采纳该默认参数。

### 下一步建议

- 补跑 2026 YTD OOS。
- 做稳健性检查后再关闭 OQ-010。
- 在做 05-08 联动 / stateful ledger v1 前，先写 PRD 明确组合目标、订单计划和实际成交反馈的日内/次日边界。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: `oq010_ff24_fill_20260604_01`
相关 issue/PR: OQ-010 / 3*2*2*2 full-factor fill

### 已完成工作

- 补齐并运行 OQ-010 3*2*2*2 全因子网格中缺失的 19 个组合。
- 24 个组合最终均通过 `12_qa_model_diagnosis_outputs`；benchmark 口径均为 `000852.SH`。
- 本轮最佳组合为 `pv_fin_quality + 30/5% + biweekly + 5d`：total_return=41.10%、excess_return=12.09%、Sharpe=1.043、max_drawdown=-14.48%。
- 本地修复 `scripts/strategy1/run_oq010_experiments.py` 的同 stage dependency batching 问题，以及 `scripts/strategy1/diagnose_model_quality.py` 的诊断完成状态与 GCS 上传状态混用问题。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要。

### 重要上下文

- `pv` 组合层实验较快，因为多数复用既有 `prediction_run_id`，只跑 05-12；`pv_fin_quality` 的 source run 需要重训和重预测。
- 5 个早期 `pv` 补跑点曾因诊断脚本写入 `model_diagnosis_status=skipped` 导致 `12` 失败；已用修复后的诊断脚本重写 ADS，并重新跑 `12` 成功。
- 本轮代码修复仍在本地 worktree，尚未提 PR。

### 改动文件

- `scripts/strategy1/run_oq010_experiments.py`
- `scripts/strategy1/diagnose_model_quality.py`
- `logs/strategy1/oq010_manifests/oq010_ff24_fill_20260604_01.json`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`

### 测试 / 验证

- 19 个补跑实验最终状态：`12_qa_model_diagnosis_outputs=succeeded`
- 5 个旧失败诊断点手动补诊断并重跑 `12` 成功
- BigQuery summary 核对：24 条 `benchmark_sec_code=000852.SH`

### 阻塞项

- 无运行阻塞；后续需提 PR 合入本轮 runner/diagnosis 修复。

### 下一步建议

- 提 PR 合入本轮 runner/diagnosis 修复。
- 由 owner 确认是否采用 `pv_fin_quality + 30/5% + biweekly + 5d` 作为 OQ-010 第一轮默认参数。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

## 2026-06-05 追加归档：AGENT_HANDOFF 当前文件瘦身

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: sklearn_native_pvfq_n30_bw_h5_20260605_01
相关 issue/PR: PR #73 / sklearn native search result closeout

### 已完成工作

- 合并 PR #73 后构建并部署镜像 `sklearn-native-topk-fix-6856a46-20260605154227` 到策略 1 Cloud Run Jobs。
- 未从头重跑 `prepare_matrix` 或 36 个 candidate fan-out；复用已完成的 `strategy1-prepare-matrix-job-d697c` 和 `strategy1-train-candidate-fanout-job-tpl9v`。
- 补跑并完成 Top5 select/register/predict 与 backtest/report/diagnosis；5 个 Top5 backtest/report execution 均成功。
- 修正 3 条因本地 orchestrator 中断而遗留为 `cancelled` 的 backtest 状态，并清理对应 stale GCS locks。
- 重新生成并上传 sklearn native comparison artifacts 到 GCS，执行 `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql` 且通过。
- 按 PR #74 comment 清理当前交接摘要中已被收口结论取代的 PR #71 / 实现分支旧块，并把 `IMPLEMENTATION_STATUS.md` 中对应 dry-run 记录标为历史补充，避免当前摘要区残留“未实跑”断言。

### 重要上下文

- 最终 comparison URI：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/search_id=sklearn_native_pvfq_n30_bw_h5_20260605_01`。
- Top5 全部 `native_acceptance_status=rejected`，拒绝原因为 `test_year_excess_return<=0.0`。
- Top1 `elastic_saga_c_0_1_l1_0_5_balanced` full-period total_return 45.31%、excess_return 16.30%、Sharpe 1.089、test RankIC 0.034，但 2025 test-year excess_return -14.92%。
- 本轮不建立 `cloud_run_sklearn_native_baseline_v1`；BQML baseline 仅作历史 reference / audit。

### 改动文件

- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- Cloud Run execution 核对：Top5 backtest/report 5/5 succeeded。
- `gsutil ls gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/search_id=sklearn_native_pvfq_n30_bw_h5_20260605_01` 返回 7 个 comparison artifacts。
- `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql` 执行通过。
- 本地 comparison JSON / CSV 与 GCS 上传结果一致。

### 阻塞项

- 无执行阻塞；结果层面 sklearn native 首轮未达到 acceptance，不能接受为新 baseline。

### 下一步建议

- 不再重复跑本轮 search；下一步先回到 BQML baseline / Ledger P1+P2 / 2026 扩展验证，或另开新一波 sklearn native 实验并按 `test_reuse_wave_no` 规则记录。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/OPEN_QUESTIONS.md`
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #72

### 已完成工作

- 查看 PR #72 最新 comment，确认并修复新 P1：`setup_alerts.py` 创建 Cloud Logging `LogMetric` 时改用正确 proto 字段 `filter`。
- 修复告警查询脚本的 fail-open 风险：`--write-log` 缺 `google-cloud-logging` 时 exit 1；默认 lookback 从 60 分钟改为 10 分钟；写日志时按 `alert_type/resource_id/finished_at` 生成稳定 `insert_id`，降低定时重跑造成的重复日志。
- 同步 runbook / README / SQL 注释：`task_failure` 覆盖所有失败 task，`ingestion_failed` 只覆盖 `status='failed'` 且不含 `empty_return`；`v_alert_probe` 明确为固定 24 小时手工健康检查视图。
- 同步 `TODO.md` 与实现状态 / 交接记忆。

### 重要上下文

- 本次未部署 BigQuery 视图、未配置 Cloud Monitoring policy、未执行生产 smoke；PR #72 合并后仍需在 GCP 环境创建视图、部署定时 checker、创建 log-based metrics / alert policies 并验证告警链路。
- 本机 Python 缺 `google-cloud-logging`，已验证缺依赖时 `--write-log` fail-closed；真实 `LogMetric(filter=...)` apply 需在安装依赖的运行环境验证。

### 改动文件

- `sql/observability/01_pipeline_status_views.sql`
- `scripts/alerting/setup_alerts.py`
- `scripts/alerting/check_alerts.py`
- `scripts/alerting/README.md`
- `docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/alerting/check_alerts.py scripts/alerting/setup_alerts.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/observability/01_pipeline_status_views.sql`
- `python3 scripts/alerting/check_alerts.py --lookback-minutes 1 --json`（本地因 `v_alert_summary` 未部署 exit 1，符合查询失败 fail-closed）
- `write_to_cloud_logging` 缺 `google-cloud-logging` 时抛 `AlertLogWriteError`
- `git diff --check`

### 阻塞项

- 无代码阻塞；生产部署/验收待 PR 合并后执行。

### 下一步建议

- 合并 PR #72 后执行 `sql/observability/01_pipeline_status_views.sql` 创建视图。
- 在安装 `google-cloud-logging` / `google-cloud-monitoring` 的运行环境执行 `setup_alerts.py` 创建 log-based metrics 和 alert policies。
- 部署 `check_alerts.py --write-log --lookback-minutes 10` 为 Cloud Scheduler / Cloud Run 定时检查，并做故障样本 smoke。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #71 final follow-up

### 已完成工作

- 接受 PR #71 非阻断观察：valid 侧 `top_minus_bottom_fwd_ret_mean` 用 5 分桶，test 侧之前用 10 分桶，指标同名但粒度不一致。
- 将 `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py` 中 test 侧分桶从 `NTILE(10)` 改为 `NTILE(5)`，高分桶从 `score_bucket=10` 改为 `score_bucket=5`。
- 在 `sql/ml/strategy1/README.md` 标明 valid/test 的 `top_minus_bottom` 均按 5 分桶计算。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要。

### 重要上下文

- 这次只统一指标口径，不改变 native acceptance 的业务门槛，也不部署镜像、不执行真实 36 候选 search。
- 后续仍需部署 Cloud Run 镜像并执行真实 sklearn native search，才能决定是否接受 `cloud_run_sklearn_native_baseline_v1`。

### 改动文件

- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py scripts/strategy1_cloudrun/select_register_predict.py scripts/strategy1_cloudrun/train_predict.py scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `python3 -m compileall -q scripts/strategy1_cloudrun`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_sklearn_native_search ... --candidate-parallelism 0 --top-k-backtest 5 --dry-run`
- `fetch_topk_ads_outputs` runtime SQL BigQuery dry-run
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 合并 PR #71 后构建 / 部署 Cloud Run 镜像。
- 执行真实 36 候选 sklearn native search、Top5 完整回测和 `18` QA。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #71 review follow-up

### 已完成工作

- 查看 PR #71 comment，认可全部 6 条 review 发现并在分支 `codex/implement-sklearn-native-search` 修复。
- `fetch_topk_ads_outputs` 新增 test 期分层高低差 `test_top_minus_bottom_fwd_ret_mean`，并写回 registry / summary metrics。
- `decide_acceptance` 和 `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql` 现在都要求 accepted 候选满足 valid/test top-minus-bottom 不能同时为负。
- QA-SKN-13 改为 `IFNULL(final_holdout_status, '') != 'passed'`，修复 wave>3 accepted 但无 final holdout 证据时被 SQL 三值逻辑放过的问题。
- Python acceptance 的 `test_rank_ic_mean` 与 QA 统一为严格 `> 0`。
- `rank_candidates` 的 fallback 仅限“全员 valid RankIC 非正”，且只允许通过 coverage/orientation/convergence hard filters 的候选 fallback；fallback 候选写 `failed_no_positive_valid_signal`。`convergence_status != 'converged'` 的候选不再能进 Top5。
- Top5 单候选 select/backtest 失败改为 fail-soft：记录该候选失败并等待其余 Top5；最终 `18` QA 仍要求完整 Top5，避免部分成功被误判为验收通过。
- 额外修复 runtime fetch SQL 中无 `predict_date` 分区过滤的多余 `ads_model_prediction_daily` distinct join。
- 同步运行手册、README、TODO 和记忆。

### 重要上下文

- 本轮仍未部署 Cloud Run 镜像，未实跑 36 个候选，未写 ADS/GCS 正式产物。
- 所有 review 点均采纳并修复；没有不认可项。
- Top5 fail-soft 只提高诊断和对比产物完整性；最终通过与否仍由 `18` QA 的完整 Top5 断言决定。

### 改动文件

- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1_cloudrun/select_register_predict.py`
- `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`
- `docs/策略1CloudRun训练回测运行手册.md`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py scripts/strategy1_cloudrun/select_register_predict.py scripts/strategy1_cloudrun/train_predict.py scripts/strategy1_cloudrun/orchestrate_experiments.py`
- ranking fallback 小样例：全员 RankIC 非正、全员 hard fail、正/负混合三类分支均符合预期。
- `python3 -m scripts.strategy1_cloudrun.orchestrate_sklearn_native_search ... --candidate-parallelism 0 --top-k-backtest 5 --dry-run`
- `fetch_topk_ads_outputs` runtime SQL BigQuery dry-run
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`
- `git diff --check`

### 阻塞项

- 无代码阻塞；真实 36 候选尚未执行。

### 下一步建议

- 推送 PR #71 follow-up commit。
- 复核通过后合并 PR #71，构建/部署 Cloud Run 镜像并执行真实 36 候选 search。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #70 / OQ-005 daily_current window hardening

### 已完成工作

- 修复 `sql/incremental/01_refresh_stock_dwd_dws_window.sql` 的 `p_date_to` 表达式，改为显式 `CASE` 分支：`daily_current` 才查最近 SSE 开市日，`backfill` 直接使用请求 `date_to`。
- 修复 `sql/qa/10_windowed_stock_refresh_checks.sql`：估值覆盖 QA 在 `daily_current` 默认使用 20 个交易日窗口，在 `backfill` 使用实际写入窗口。
- 修复 QA-WIN-18：不再按 `pe/pb` 或所有 DWD valuation 行触发；改为在 price-driven feature universe 内，按 `total_mv_cny/circ_mv_cny` 非空检查最终宽表 `has_valuation_data=TRUE`。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`ARCHITECTURE_MEMORY.md`、`KNOWN_CONSTRAINTS.md` 和当前交接摘要。

### 重要上下文

- PR #70 review comment 的 P1/P2/P3 建议均采纳并修复；当前分支仍未部署到 Composer。
- 本次只改 SQL 和记忆/TODO，不执行生产 DML，不触碰 Composer bucket，不覆盖 BigQuery/GCS/ADS 产物。

### 改动文件

- `sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `sql/qa/10_windowed_stock_refresh_checks.sql`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- BigQuery dry-run：窗口 SQL，`warehouse_mode=daily_current`，`business_date=2026-06-06`。
- BigQuery dry-run：窗口 QA，`warehouse_mode=daily_current`，`business_date=2026-06-06`。
- BigQuery dry-run：窗口 SQL，`warehouse_mode=backfill`，`date_from=2026-06-03`，`date_to=2026-06-04`。
- BigQuery dry-run：窗口 QA，`warehouse_mode=backfill`，`date_from=2026-06-03`，`date_to=2026-06-04`。
- 只读窗口计算：`2026-06-06` 归一为 `2026-06-05`，daily_current 估值覆盖起点 `2026-05-11`；backfill `2026-06-03..2026-06-04` 估值覆盖起点 `2026-06-03`。

### 阻塞项

- 无。

### 下一步建议

- 跑 `git diff --check` 后提交并推送 PR #70 分支。
- 合并后同步 `sql/` 到 Composer bucket，再按部署流程做需要的 smoke。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-010 / Strategy 1 sklearn native search implementation

### 已完成工作

- 在工作树 `/Users/luna/Desktop/git/quant-ashare-sklearn-native-search`、分支 `codex/implement-sklearn-native-search` 实现 `docs/prd/PRD_20260605_03_策略1Sklearn模型实验.md` 的 P0 代码路径。
- 新增 `configs/strategy1/sklearn_native_pvfq_n30_bw_h5_v0.yml`，固定当前最优交易参数 `pv_fin_quality + 30/5% + biweekly + 5d`、训练窗口 `2019-04-03` 至 `2023-12-31`、valid 2024、test/predict 2025，并定义 36 个 sklearn LogisticRegression 原生候选。
- 扩展 `train_predict.py`：candidate 级 `penalty` / `solver` / `C` / `l1_ratio` / `class_weight` / `max_iter` / `random_state`，记录 convergence warning、`n_iter_max`、`valid_signal_status`、valid RankIC ICIR、valid top-minus-bottom 等元数据。
- 扩展 `select_register_predict.py`：支持强选 candidate、valid-only ranking、Top5 metadata、training panel alias、native search 初始状态、candidate ranking artifact。
- 新增 `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`：一次 prepare matrix、36-task candidate fan-out、valid-only Top5、Top5 独立 select/predict/backtest/report/diagnosis、native acceptance 回写、comparison artifact 和 `18` QA。
- 新增 `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`，覆盖 search_id/source_run_id、candidate_count、task fan-out metadata、valid-only ranking、TopK 独立 run/backtest、report/diagnosis uploaded、accepted gates、BQML reference、test reuse/final holdout 等断言。
- 修复 `orchestrate_experiments.py` 的配置透传：candidate task 命令现在包含 `--config=...`，避免容器端回退默认 5 候选。
- 同步 Cloud Run 运行手册、runner README、TODO 和项目记忆。

### 重要上下文

- 这只是实现分支和 dry-run 验证，尚未部署 Cloud Run 镜像、未实跑 36 个候选、未写 ADS/GCS 正式产物。
- 当前真实执行建议在 PR review/merge 后进行：重新构建/部署包含新脚本的镜像，再运行 `orchestrate_sklearn_native_search.py`。
- 已知 `asia-east2` Cloud Run 配额提升到约 40 vCPU / 160Gi，第一轮 36 个 candidate task 可按 `1 CPU / 4Gi`、`--tasks=36` 并发尝试。
- 新 native baseline path 不要求 BQML parity passed，但必须保留 BQML reference 证据，并按 PRD 的 native acceptance gate 决定 accepted / rejected / needs_more_evidence。

### 改动文件

- `configs/strategy1/sklearn_native_pvfq_n30_bw_h5_v0.yml`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `scripts/strategy1_cloudrun/select_register_predict.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`
- `sql/ml/strategy1/README.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py scripts/strategy1_cloudrun/select_register_predict.py scripts/strategy1_cloudrun/train_predict.py scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_sklearn_native_search ... --candidate-parallelism 0 --top-k-backtest 5 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments ... --train-mode task_fanout --candidate-parallelism 0 --dry-run`
- 配置校验：36 个 candidate_id 全部唯一，manifest 只含 1 个 search experiment。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`
- `git diff --check`

### 阻塞项

- 无代码阻塞；真实 36 候选尚未执行。

### 下一步建议

- 创建 PR 并 review。
- 合并后构建/部署 Cloud Run 镜像到 `strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`。
- 执行真实 sklearn native search：36 候选并发训练、Top5 完整回测、`18` QA，通过 comparison artifact 决定是否接受 `cloud_run_sklearn_native_baseline_v1`。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-010 / Strategy 1 sklearn native model experiment PRD

### 已完成工作

- 在独立工作树 `/Users/luna/Desktop/git/quant-ashare-sklearn-native-prd` 和分支 `codex/prd-sklearn-native-experiment` 新增 `docs/prd/PRD_20260605_03_策略1Sklearn模型实验.md`。
- PRD 固定当前交易口径 `pv_fin_quality + 30/5% + biweekly + 5d`，避免把模型实验和交易参数变化混在一起。
- PRD 定义第一轮 36 个 LogisticRegression sklearn 原生候选：无正则、L2、ElasticNet，覆盖 `C`、`class_weight`、`l1_ratio` 和 solver 语义。
- PRD 定义搜索流程：一次 `prepare_matrix`，candidate task fan-out 并发训练全部候选，valid-only 选 Top 5，再对 Top 5 跑完整预测、组合、回测、报告、诊断和 QA。
- PRD 定义 sklearn native acceptance gate：valid/test RankIC、2025 test-year 收益和相对中证1000超额、Sharpe、max drawdown、成本、`10/12/16/17/18` QA 和 Python ledger vs SQL ledger 等价边界。
- 同步 `TODO.md`、`PROJECT_CONTEXT.md`、`OPEN_QUESTIONS.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要。

### 重要上下文

- 本 PRD 是 Cloud Run sklearn backend 在 BQML parity 未通过后的后续方案；它不删除既有 BQML parity gate，只新增 native baseline path。
- BQML baseline 当时仍作为 reference / fallback；2026-06-05 owner 决策已将其改为历史 reference / audit，native / 后续 Python baseline 是否接受由 native acceptance 或新模型 PRD 决定。
- 本次没有实现代码，没有部署 Cloud Run Job，没有执行 BigQuery，没有生成或覆盖 ADS / GCS 产物。

### 改动文件

- `docs/prd/PRD_20260605_03_策略1Sklearn模型实验.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review / 合并本 PRD。
- 合并后实现 `configs/strategy1/sklearn_native_pvfq_n30_bw_h5_v0.yml`、candidate search orchestrator、Top 5 backtest flow 和 `18_qa_sklearn_native_search_outputs.sql`。
- 再跑第一轮 36 个 LogisticRegression 候选并产出 comparison report。

### 已更新记忆文件

- `TODO.md`
- `PROJECT_CONTEXT.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`

---
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01
相关 issue/PR: Strategy 1 Cloud Run task fan-out formal validation

### 已完成工作

- 将 `strategy1-prepare-matrix-job` 资源从 `4 CPU / 16Gi` 提升到 `8 CPU / 32Gi`，用于解决全量 2019-2025 训练面板 prepare 阶段 16Gi OOM 风险。
- 为正式验收创建独立 run/backtest：`s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01` / `bt_s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01`，不覆盖既有 BQML baseline。
- 重建该 run 的训练面板，行数 3,055,781（train 1,999,065 / valid 476,346 / test 580,370），注意样本 `p_feature_version` 仍使用 DWS 现有 `strategy1_pv_v0_20260601`，`p_feature_set_id` 使用 `strategy1_pv_fin_quality_v0_20260603`。
- 执行完整 Cloud Run task fan-out 链路：`cloudrun_prepare_matrix`、5 个 candidate task、`cloudrun_select_register_predict`、`cloudrun_backtest_report` 全部 succeeded。
- `cloudrun_backtest_report` 内部跑通 `05_build_candidates`、`06_build_portfolio_targets`、`07_build_order_plan`、Python `ledger_exec_v1`、`09_build_metrics_and_report_inputs`、报告上传、`10_qa_runner_outputs.sql`、诊断脚本和 `12_qa_model_diagnosis_outputs.sql`。

### 重要上下文

- `prepare_matrix` execution：`strategy1-prepare-matrix-job-q4zd5`，Cloud Run 侧耗时约 4m10s。
- candidate fan-out execution：`strategy1-train-candidate-fanout-job-fpk9d`，5 个 task 全部 succeeded。
- select/register/predict execution：`strategy1-select-register-predict-job-d5kj2`。
- backtest/report execution：`strategy1-backtest-report-job-4shcl`。
- selected sklearn candidate 为 `elastic_c_1_l1_0_5`，`score_orientation=reverse_probability`。
- 报告 URI：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01/backtest_id=bt_s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01`。
- 模型诊断 URI：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01/backtest_id=bt_s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01/model_diagnosis`。

### 测试 / 验证

- orchestrator 全链路返回 `status=succeeded`、`failure_count=0`。
- `10_qa_runner_outputs.sql` 和 `12_qa_model_diagnosis_outputs.sql` 在 `cloudrun_backtest_report` 内部通过。
- `16_qa_cloudrun_runner_outputs.sql` 在 `p_require_model_quality_parity_passed=FALSE` 的 smoke/evidence 模式通过。
- `17_qa_cloudrun_orchestrator_status.sql` 在 `p_require_task_fanout=TRUE` 下通过。
- 正式 `16_qa_cloudrun_runner_outputs.sql` 在默认 `p_require_model_quality_parity_passed=TRUE` 下未通过，失败点为 `QA-CR-4`。

### 结果摘要

- 回测 total_return `46.29%`、annual_return `21.72%`、Sharpe `1.111`、max_drawdown `-13.94%`。
- benchmark 为 `000852.SH`，excess_return `17.28%`，information_ratio `0.237`。
- prediction 行数 1,056,716，日期范围 `2024-01-02` 至 `2025-12-31`，score NULL 行数 0。
- diagnosis 结论 `usable_signal`，confidence `low`；valid RankIC mean `0.06665`，test RankIC mean `0.03359`。
- sklearn vs BQML parity 未通过：sklearn valid RankIC `0.06665`，BQML reference `0.09676`，delta `-0.03011`；`model_quality_status=model_quality_not_equivalent`。

### 阻塞项

- 无执行链路阻塞；正式替代 BQML 的模型质量门槛未过。

### 下一步建议

- 不要把本 run 直接标记为 BQML 替代 baseline；它目前只能证明 Cloud Run task fan-out 执行链路可用。
- 下一步应先做 sklearn parity 提升（候选网格、预处理、模型族或参数）或由 owner 明确接受新的 Cloud Run baseline。
- 另需补 Python ledger vs SQL ledger 完整等价验收，再考虑让 Cloud Run runner 成为默认执行路径。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: s1_cloudrun_taskfanout_smoke_20260605_03
相关 issue/PR: Strategy 1 Cloud Run task fan-out smoke / fix branch `codex/fix-task-fanout-force-replace`

### 已完成工作

- 构建并部署 task fan-out 修复镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner@sha256:8cc8470014cb3b54272d4c7f47afb396d91cf7b97967f0c3ffab947f7432c38a`。
- 更新 Cloud Run Jobs：`strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`。
- 执行低成本 task fan-out smoke：2023 train、2024H1 valid、2024H2 test/predict，5 个默认候选全部用 candidate task 并发训练。
- 修复 smoke 暴露的问题：`prepare_matrix` 不支持 `--force-replace`；`10` QA split 边界写死；`12` QA-DIAG-6 使用 DWS 固定 split 导致短窗口 test 误判为 0 天。

### 重要上下文

- 当前 job CPU：prepare/select/backtest 为 `4 CPU / 16Gi`；candidate task 为 `1 CPU / 4Gi`。
- 当前区域配额限制为 `asia-east2` 约 `20 vCPU / 40Gi`，所以 candidate job 设置 `parallelism=10`；本次默认 5 候选 smoke 实际并发为 5。
- 全量 2019-2025 训练面板的 `prepare_matrix` 曾在 `16Gi` 下 OOM；本次 smoke 改用短窗口验证链路。后续正式全量 matrix 可能需要提高 prepare job 内存或做分片/流式构建。

### 改动文件

- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/backtest_report.py`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/orchestrate_experiments.py scripts/strategy1_cloudrun/backtest_report.py`
- `git diff --check`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`
- Cloud Run smoke 状态表 4 步 succeeded：`cloudrun_prepare_matrix`、`cloudrun_train_candidate_fanout`、`cloudrun_select_register_predict`、`cloudrun_backtest_report`
- `10_qa_runner_outputs.sql`、`12_qa_model_diagnosis_outputs.sql`、`16_qa_cloudrun_runner_outputs.sql`、`17_qa_cloudrun_orchestrator_status.sql` 全部通过

### 阻塞项

- 无执行链路阻塞；正式替代 BQML 仍需 sklearn parity passed 或 owner 明确采纳新 Cloud Run baseline。

### 下一步建议

- 提 PR review 并合并本次 smoke 修复。
- 后续若要 35/100 候选并发，需要先决定是提升 Cloud Run 区域配额，还是降低 candidate task 内存并验证 OOM 风险。
- 针对全量窗口 `prepare_matrix` 的 16Gi OOM，单独做 prepare 阶段内存优化或提高 job 规格。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

---
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: Strategy 1 Cloud Run lightweight task fan-out implementation

### 已完成工作

- 在工作树 `/Users/luna/Desktop/git/quant-ashare-cloudrun-task-fanout-impl`、分支 `codex/cloudrun-task-fanout` 实现 task fan-out P0。
- 新增 `prepare_matrix.py`，集中读取 `ads_ml_training_panel_daily`，按 train split fit 预处理器，输出已预处理 train/valid/predict parquet、feature schema、preprocess stats、work units、matrix manifest 和 BigQuery job audit。
- 新增 `train_candidate_task.py`，按 `CLOUD_RUN_TASK_INDEX + TASK_INDEX_OFFSET` 训练单个 candidate，输出 candidate model、metrics、training log 和 task status。
- 新增 `select_register_predict.py`，汇总 candidate artifact，校验 matrix/hash，一致通过后选型、写 selected model artifact、registry 和 prediction。
- `orchestrate_experiments.py` 新增 `--train-mode task_fanout` / `--candidate-parallelism`；owner 不限流时单批 `--tasks=N` 全并发，显式限流时按批次执行。
- `16_qa_cloudrun_runner_outputs.sql` 与 `17_qa_cloudrun_orchestrator_status.sql` 增加 task fan-out 模式断言；运行手册和 runner README 已同步。

### 重要上下文

- 该条为 PR #64 合并前 dry-run 阶段交接；真实 task fan-out smoke 已在后续 2026-06-05 交接完成。
- 当前默认 candidate grid 仍是 5 个；未擅自扩到 35 个。扩网格和真实成本实验需要 owner 再确认。
- `prepare_matrix` 依赖既有 `ads_ml_training_panel_daily`，不会自动执行 `01_build_training_panel.sql`；真实执行前必须先确认对应 `run_id` 的训练面板已存在。
- 本机默认 Python 3.9 起初缺 `joblib/scikit-learn`；已按 `scripts/strategy1/requirements.txt` 用 `pip install --user` 补齐本地 dry-run 依赖。

### 改动文件

- `configs/strategy1/cloudrun_runner_default.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1_cloudrun/bq_io.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/prepare_matrix.py`
- `scripts/strategy1_cloudrun/select_register_predict.py`
- `scripts/strategy1_cloudrun/task_fanout.py`
- `scripts/strategy1_cloudrun/train_candidate_task.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/*.py`
- `python3 -m scripts.strategy1_cloudrun.prepare_matrix --project data-aquarium --region asia-east2 --experiment-id oq010_a0_n5_w20 --candidate-parallelism 0 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.train_candidate_task --project data-aquarium --region asia-east2 --matrix-uri gs://dummy/matrix --matrix-local-dir <tmp> --task-index 0 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.select_register_predict --project data-aquarium --region asia-east2 --experiment-id oq010_a0_n5_w20 --matrix-uri gs://dummy/matrix --matrix-local-dir <tmp> --dry-run`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --project data-aquarium --region asia-east2 --manifest configs/strategy1/oq010_experiments_v0.json --config configs/strategy1/cloudrun_runner_default.yml --experiment-id oq010_a0_n5_w20 --train-mode task_fanout --candidate-parallelism 0 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --project data-aquarium --region asia-east2 --manifest configs/strategy1/oq010_experiments_v0.json --config configs/strategy1/cloudrun_runner_default.yml --experiment-id oq010_a0_n5_w20 --train-mode task_fanout --candidate-parallelism 2 --dry-run`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`
- `gcloud run jobs execute --help | rg -n -- '--tasks|--update-env-vars|--args'`
- `git diff --check`

### 阻塞项

- 无代码阻塞；该历史交接的部署与 5 候选 smoke 已在后续 2026-06-05 完成。

### 下一步建议

- 提 PR review。
- PR 合并后部署 `strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`。
- 先用 5 个默认候选跑低成本 task fan-out smoke，通过 `16`/`17` task fan-out QA 后，再讨论是否扩到 35 候选并做 sklearn parity 实验。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`

---
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-010 / Strategy 1 Cloud Run lightweight task fan-out PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260605_02_策略1CloudRun轻量Task并发.md`。
- PRD 定义 `prepare_matrix -> train_candidate_fanout --tasks=N --candidate-parallelism=M -> select_register_predict -> backtest_report` 链路。
- 固化 GCS frozen matrix 契约、work units manifest、`CLOUD_RUN_TASK_INDEX` 分片映射、小规格 candidate task、owner 显式限流、reducer 选型、QA、状态表与幂等规则。
- 跟进 PR #63 review comment：明确 frozen features 为 `prepare_matrix` 输出的已预处理矩阵，candidate task 不重新预处理；补 BigQuery job labels / audit 机制来验证训练面板只在 `prepare_matrix` 读取；补 candidate task 不读 `predict_features` / `predict_index`。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和本交接文件。

### 重要上下文

- 工作树：`/Users/luna/Desktop/git/quant-ashare-cloudrun-task-fanout-prd`。
- 分支：`codex/prd-cloudrun-task-fanout`。
- 本次只写文档；未实现代码、未部署 Cloud Run Job、未执行 BigQuery、未生成或覆盖 GCS / ADS 产物。
- 该 PRD 是 `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md` 的训练侧并发补充，不替代 Cloud Run runner / orchestrator 已有 PRD。

### 改动文件

- `docs/prd/PRD_20260605_02_策略1CloudRun轻量Task并发.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- review / merge 本 PRD。
- 合并后按阶段实现：Phase 1 先做 dry-run / manifest 展开，Phase 2 做 `prepare_matrix` frozen matrix，Phase 3 做 Cloud Run task fan-out，Phase 4 做 reducer / prediction / QA，最后做 35/100 work units smoke。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

---
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #61 / OQ-005 Phase 2.0 BigQuery SQL 兼容调度路径

### 已完成工作

- 跟进 PR #61 review comment。
- `orchestration/composer/dags/ashare_daily_pipeline_v0.py` 移除模块顶层 `Variable.get()`：project/region/location 改为 operator 模板参数，callback URL / BigQuery client 改为运行期 helper 读取。
- `pipeline_dry_run` / `dry_run` 支持单次 DAG run 覆盖 Airflow Variable；DAG 通过 branch 在运行期选择 `ingest_current_scope_dry_run` 或 `ingest_current_scope_write`，避免全局翻转变量才能做真实采集。
- `sql/qa/09_ods_daily_partition_readiness.sql` 新增 `pipeline_dry_run` 参数；`require_business_partition` 为空时由 dry-run 运行期口径推导，dry-run 默认不要求精确业务日分区，真实写入默认要求精确业务日/交易日分区。
- 删除冗余 `ods_daily_partition_readiness >> finish` 依赖。
- 抽出 `_build_qa_chain(group_id)`，复用 `qa` 与 `qa_only` 的 5 个 QA task 定义。
- 同步 `orchestration/composer/README.md` / `orchestration/README.md` 的手工运行参数说明。

### 重要上下文

- 本次只改仓库文件；未部署 Composer、未触发 DAG、未执行生产 BigQuery 转换、未写 GCS。
- PR #61 仍是 OQ-005 Phase 2.0 代码入口；OQ-005 仍保持 open，后续还需要 Composer 部署 smoke、生产验收、Dataform 生产链路、增量影响窗口、告警和补跑闭环。

### 改动文件

- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `sql/qa/09_ods_daily_partition_readiness.sql`
- `orchestration/composer/README.md`
- `orchestration/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=pipeline_dry_run:STRING:true --parameter=require_business_partition:STRING: < sql/qa/09_ods_daily_partition_readiness.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=pipeline_dry_run:STRING:false --parameter=require_business_partition:STRING: < sql/qa/09_ods_daily_partition_readiness.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/meta/01_create_meta_tables.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/meta/04_ods_field_unit_map.sql`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 推送 PR #61 follow-up commit 并在 PR comment 回复验证结果。
- 部署到 Composer 后先做 `skip_ingestion=true` smoke，再做 `warehouse_mode=qa_only` 只读 QA 和 `warehouse_mode=full_rebuild_compat` 维护链路 smoke。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

---
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-005 / Phase 2.0 BigQuery SQL 兼容调度路径

### 已完成工作

- 在新工作树 `/private/tmp/quant-ashare-oq005-scheduler-phase2`、分支 `codex/oq005-scheduler-phase2` 开始实现已合并的 `docs/prd/PRD_20260605_01_OQ005剩余调度链路.md`。
- `orchestration/composer/dags/ashare_daily_pipeline_v0.py` 新增 `pipeline_run` / `pipeline_task_status` 状态回写、task success/failure callback、DAG failed callback、`warehouse_mode` 分支、legacy `ashare_enable_full_refresh=true` 到 `full_rebuild_compat` 的记录映射、`skip_ingestion` 分支、`qa_only` 只读 QA 分支和 ADS 契约手工初始化分支。
- `sql/meta/01_create_meta_tables.sql` 扩展 `pipeline_run` / `pipeline_task_status` 字段，新增 `date_from`、`date_to`、`run_label`、`warehouse_mode`、`transform_backend`、`updated_at` 和 Airflow / BigQuery / Cloud Run URL 字段。
- 将 OQ-006 单位映射脚本从 `sql/meta/01_ods_field_unit_map.sql` 重命名为 `sql/meta/04_ods_field_unit_map.sql`，并同步 DAG、SQL README 和 PRD 引用。
- 同步 `orchestration/composer/README.md`、`orchestration/README.md`、`sql/README.md` 和 OQ-005 PRD 中的 Phase 2.0 口径。
- 新增 `DECISION-20260605-01`，记录 `warehouse_mode` 显式区分每日、只读 QA、兼容全量转换和 ADS 契约初始化。

### 重要上下文

- 本次只改仓库文件；未部署 Composer、未触发 DAG、未执行生产 BigQuery 转换、未写 GCS。
- Phase 2.0 现有 CTAS 转换只允许 `warehouse_mode=full_rebuild` 或 `warehouse_mode=full_rebuild_compat` 手工进入；默认 `daily_current` 只做采集、ODS readiness 和状态回写。
- `warehouse_mode=qa_only` 只跑 ODS readiness 后的 `01-05` QA，不改生产表。
- `enable_ads_contract_init=true` 才会执行 `sql/ads/01_ads_strategy1_tables.sql`。

### 改动文件

- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `sql/meta/01_create_meta_tables.sql`
- `sql/meta/04_ods_field_unit_map.sql`
- `orchestration/composer/README.md`
- `orchestration/README.md`
- `sql/README.md`
- `docs/prd/PRD_20260605_01_OQ005剩余调度链路.md`
- `docs/prd/PRD_20260602_01_OQ006接口单位换算口径.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/meta/01_create_meta_tables.sql`
- `git diff --check`

### 阻塞项

- 未阻塞；下一步需要提 PR / review 后部署到 Composer 做 smoke。

### 下一步建议

- 提 PR 并 review Phase 2.0 DAG 变更。
- 部署后先用 `skip_ingestion=true` 做调度 smoke，确认不创建 Cloud Run execution 且 ODS readiness / 状态表回写正常。
- 再用 `warehouse_mode=qa_only` 验证只读 QA 不改生产表。
- 最后用 `warehouse_mode=full_rebuild_compat` 手工 smoke BigQuery SQL 兼容转换链路，确认 metadata / QA / `pipeline_run` terminal 状态完整。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

---
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-005 / 剩余 ODS→ADS 调度链路 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260605_01_OQ005剩余调度链路.md`。
- PRD 聚焦当前 `ashare-ingest-current-scope` 生产采集之后的剩余链路，覆盖 ODS gate、ODS→DIM/DWD/DWS/ADS 转换、ADS 契约隔离、metadata、QA、pipeline 状态、告警、补跑、Dataform / BigQuery SQL 双路径、策略 runner/report 可选分支和 OQ-005 关闭标准。
- PR #59 review follow-up：澄清 Phase 2.0/2.1 使用现有 CTAS 时是 `full_rebuild_compat` / maintenance 路径，真正默认每日不扫 2019+ 全史从 Phase 2.2 增量化开始；修正 ADS 脚本现状为已使用 `CREATE TABLE IF NOT EXISTS`；补充 `sql/meta/` 编号整理要求；明确字段说明迁移期生产来源为 `sql/metadata/01,02`。
- 同步 `TODO.md`、`PROJECT_CONTEXT.md`、`OPEN_QUESTIONS.md`、`IMPLEMENTATION_STATUS.md`、`ARCHITECTURE_MEMORY.md` 和当前交接摘要。

### 重要上下文

- 工作树：`/private/tmp/quant-ashare-oq005-ods-ads-scheduler-prd`。
- 分支：`codex/oq005-ods-ads-scheduler-prd`。
- 本次只写 PRD 和必要状态记录，未实现代码、未部署 Composer/Dataform/Cloud Run、未执行 BigQuery。
- OQ-005 继续保持 open，下一步按 PRD Phase 2.0/2.1/2.2/2.3 实现 BigQuery SQL 兼容路径闭环、Dataform definitions、增量影响窗口、策略 runner/report 分支和告警/补跑/状态闭环。

### 改动文件

- `docs/prd/PRD_20260605_01_OQ005剩余调度链路.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- review/merge 本 PRD。
- 合并后按 Phase 2.0 先补 `ashare_daily_pipeline_v0` 的 pipeline status、BigQuery SQL 兼容路径和 ADS 契约初始化隔离。
- Phase 2.1 再接 Dataform definitions 和 workflow invocation。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

---
日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01 / bt_ledger_resume_smoke_20260604_01
相关 issue/PR: OQ-010 / Ledger v1 P2 state resume implementation

### 已完成工作

- 实现 Ledger v1 state resume。
- `08_run_backtest.sql` 新增 `p_initial_state_mode='resume_from_backtest'`、`p_parent_backtest_id`、`p_state_as_of_date` 和 `p_resume_policy_id`，从父回测恢复现金、实际持仓、active target 和 pending sell。
- resume 前置校验 fail-fast：父 summary 必须存在且 `ledger_version='ledger_exec_v1'`，父 NAV state 必须唯一且含 cash/net value/run_id，父持仓必须唯一且非负，父 NAV 必须能与现金+持仓市值对齐，`p_predict_start` 必须等于 state date 后下一 SSE 开市日。
- `09_build_metrics_and_report_inputs.sql` 在 summary `metrics_json` 写入 `initial_state_mode`、`parent_backtest_id`、`state_as_of_date`、`resume_policy_id` 和 `is_resumed_backtest`。
- `10_qa_runner_outputs.sql` 新增 `QA-RESUME-1..6`；biweekly resume 强制显式传 `p_rebalance_anchor_start` 原实验锚点，首个 resume 日 `daily_return` 必须非空。
- 新增 `sql/ml/strategy1/15_qa_ledger_resume_consistency.sql`，用于后续 full fresh vs resume segment 一致性验收，并比较 `daily_return`。
- `sql/ml/strategy1/README.md` 已同步 resume 参数、运行顺序和 consistency QA 说明。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`KNOWN_CONSTRAINTS.md` 和当前交接摘要。

### 重要上下文

- 当前实现分支：`codex/ledger-state-resume`，工作树 `/Users/luna/Desktop/git/quant-ashare-ledger-resume`。
- 基于 `origin/main` commit `602baea`，该 commit 已包含 Ledger v1 P0。
- smoke 父回测：`bt_ledger_v1_p0_smoke_20260604_01`，`state_as_of_date=2024-02-29`。
- smoke resume 回测：`bt_ledger_resume_smoke_20260604_01`，窗口 `2024-03-01` 至 `2024-03-15`。
- smoke 首日现金恢复为父状态现金 `135.9692847801162`，首日 `daily_return=-0.0031135`，NAV 11 行无 NULL daily_return，持仓 330 行，成交 36 行；本地报告使用 `--skip-gcs-upload`。
- 完整 consistency QA 需要先具备 full fresh extended backtest 与 resume segment backtest；本次只新增 QA 脚本并完成 dry-run。

### 改动文件

- `sql/ml/strategy1/08_run_backtest.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/15_qa_ledger_resume_consistency.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/08_run_backtest.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/15_qa_ledger_resume_consistency.sql`
- BigQuery smoke：PR #54 review follow-up 后，`08` resume、`09` resume、本地 `render_report.py --skip-gcs-upload`、`10_qa_runner_outputs.sql` 全部通过。
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 提 PR review 本次 Ledger v1 P2 resume 实现。
- 合并后补 Ledger v1 P1 fixed-model extended backtest 至 `2026-04-30`。
- 有 full fresh extended 与 resume segment 后，执行 `15_qa_ledger_resume_consistency.sql` 做一致性验收。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

---
日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01
相关 issue/PR: OQ-010 / factor attribution implementation

### 已完成工作

- 实现策略 1 因子贡献度分析 P0。
- 新增 `scripts/strategy1/attribute_factor_contribution.py`，只读 selected BQML model、冻结训练面板、预测池、候选池、回测持仓和 summary，不重新训练、不做消融实验。
- 新增 `sql/ml/strategy1/14_qa_factor_attribution_outputs.sql`，断言状态、版本、manifest、模型特征覆盖、因子组映射、valid/test RankIC、score contribution 分组、持仓暴露覆盖、路径语义、相关性摘要、限制说明和禁止消融字段。
- `scripts/strategy1/render_report.py` 已接入可选“因子贡献度摘要”：第 13 步回写 completed 后，主报告展示 factor attribution 路径、top 因子组和 top score factors。
- `sql/ml/strategy1/README.md` 已补 13/14 执行命令、参数和 artifact 契约。
- `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要已同步。

### 重要上下文

- 正式 baseline local-only smoke 已成功生成 `reports/strategy1/ml_pv_clf_v0/run_id=s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01/backtest_id=bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01/factor_attribution/`。
- 本次覆盖 selected model 55 个非截距特征、13 个因子组；`factor_attribution_upload_status=skipped`，`local_factor_attribution_path` 已回写 ADS，`factor_attribution_uri` 为空。
- 计算过程中修复了 BigQuery 动态 JSON path 限制：脚本使用 `PARSE_JSON(feature_values_json, wide_number_mode => 'round')[feature]` 取动态特征值。
- 本 PR 只提交代码/SQL/文档/记忆；生成的 `reports/` 本地产物不纳入 git。

### 改动文件

- `scripts/strategy1/attribute_factor_contribution.py`
- `sql/ml/strategy1/14_qa_factor_attribution_outputs.sql`
- `scripts/strategy1/render_report.py`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/attribute_factor_contribution.py scripts/strategy1/render_report.py scripts/strategy1/diagnose_model_quality.py`
- `python3 scripts/strategy1/attribute_factor_contribution.py --help`
- `git diff --check`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/14_qa_factor_attribution_outputs.sql`
- `python3 scripts/strategy1/attribute_factor_contribution.py --project data-aquarium --run-id s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01 --backtest-id bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01 --artifact-base-uri gs://ashare-artifacts/reports/strategy1 --local-mirror-root reports/strategy1 --skip-gcs-upload`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/14_qa_factor_attribution_outputs.sql`，全部 ASSERT 通过。

### 阻塞项

- 无。

### 下一步建议

- 提 PR review 本次因子贡献度实现。
- 合并后按 Ledger v1 PRD 实现 P0 交易语义 A/B，再做 P1 fixed-model 连续扩展回测到 `2026-04-30` 和 P2 ledger state resume。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #69 / OQ-010 / Strategy 1 sklearn native model experiment PRD

### 已完成工作

- 按 PR #69 review comment 修订 `docs/prd/PRD_20260605_03_策略1Sklearn模型实验.md`。
- 将训练窗口从自然年简写改为 `2019-04-03` 至 `2023-12-31`，确保和 BQML baseline / livepool 训练起点一致。
- 新增 `valid_signal_status` 规则：accepted 候选必须为 `stable`；valid 弱但 test 过门只能标记 `needs_more_evidence`。
- 新增跨模型族 test 复用控制：记录 `test_reuse_wave_no` / `test_reuse_approval_ref`，第二波及以后需 owner 批准，超过 3 个波次后必须新增最终 holdout 证据。
- 同步输出报告、ADS/GCS JSON、QA、manifest、Phase 4 和风险表约束。
- 同步 `PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`TODO.md` 和当前交接摘要。

### 重要上下文

- 本次仍是纯文档/记忆修订，未实现代码、未部署 Cloud Run Job、未执行 BigQuery、未生成或覆盖 ADS / GCS 产物。
- `OPEN_QUESTIONS.md` 的 OQ-010 仍保持原 open 状态；关键修订已在 PROJECT_CONTEXT / STATUS / TODO / handoff 记录。

### 改动文件

- `docs/prd/PRD_20260605_03_策略1Sklearn模型实验.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review / 合并 PR #69。
- 合并后实现 sklearn native search manifest、candidate metrics、Top 5 full backtest flow 和 `18_qa_sklearn_native_search_outputs.sql`。

### 已更新记忆文件

- `PROJECT_CONTEXT.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

---
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-005 Phase 2.2 / PR #65 post-merge hotfix / branch `codex/fix-windowed-refresh-equivalence`

### 已完成工作

- 在独立工作树 `/private/tmp/quant-ashare-oq005-window-prod` 从最新 `origin/main` 创建热修复分支 `codex/fix-windowed-refresh-equivalence`。
- 运行真实 scratch full-vs-window 等价 QA，确认 PR #65 合并后生产部署前存在两个阻断：QA runner 复制 `_full` 表时缺少分区过滤；估值特征读取窗口不足导致 `turnover_rate_zscore_60d` 漂移。
- 修复 `scripts/qa/run_windowed_refresh_equivalence.py`：复制 canonical `_full` 到 `_window` seed 时按 `trade_date BETWEEN build_start_date AND full_end_date` 过滤，兼容 `require_partition_filter=true`。
- 修复 `sql/incremental/01_refresh_stock_dwd_dws_window.sql`：估值特征读取边界按每只股票写入窗口首日前的实际 60 条估值观测推导，价格特征仍读取 60 个 SSE 交易日，标签/宽表/样本写入仍向前回补 20 个交易日。
- 修复 `scripts/qa/run_windowed_refresh_equivalence.py`：真实运行前用生产 DWD 估值表校验 `build_start_date` 足够早，避免 full/window shadow 被同样截断后假通过。
- 跟进 PR #68 comment：不采用固定 180 个交易日作为最终方案，改为 per-stock 实际观测边界，并用 QA guard 覆盖早期窗口假通过风险。
- 同步 `sql/README.md`、`TODO.md`、OQ-005 架构记忆、约束、状态和开放问题。

### 重要上下文

- 本次真实 QA 只写 scratch dataset `ashare_qa_windowed_equivalence` 的 `_full` / `_window` shadow 表，不写生产 DWD/DWS/ADS。
- 首次真实 QA 的 drift 集中在 `dws_stock_feature_valuation_daily.turnover_rate_zscore_60d` 和继承该字段的 `dws_stock_feature_daily_v0`，原因是 `daily_basic` 对部分股票不是每日完整观测，60 条观测窗口可能跨越超过 60 个交易日。
- 修复后 full-vs-window 等价 QA 对 9 张目标表 mismatch 均为 0；guard 结果为 `required_build_start_date<=2025-01-23`、`sec_code_count=5407`、`less_than_60_obs=32`。
- 仍未部署 Composer，未执行生产 DML，未写生产 BigQuery/GCS/ADS 产物。

### 改动文件

- `scripts/qa/run_windowed_refresh_equivalence.py`
- `sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `sql/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/qa/run_windowed_refresh_equivalence.py`
- `python3 scripts/qa/run_windowed_refresh_equivalence.py --dry-run`
- `bq query --dry_run`：窗口 SQL `backfill` 参数。
- `bq query --dry_run`：窗口 SQL `daily_current` 参数。
- 真实 scratch 等价 QA：9 张目标表 full-vs-window mismatch 均为 0。

### 阻塞项

- 无代码阻塞；生产部署和生产 DML smoke 需等待本 hotfix 合并。

### 下一步建议

- 合并 hotfix PR。
- 合并后部署 Composer DAG 与 SQL 到 Composer bucket。
- 先跑 `skip_ingestion=true` + `warehouse_mode=backfill` 小窗口生产 DML smoke，再跑 `daily_current` scheduler smoke 和 `qa_only` 验收。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

---
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #65 / OQ-005 Phase 2.2 股票 DWD/DWS 窗口刷新

### 已完成工作

- 将分支 `codex/windowed-dwd-dws-refresh` rebase 到 `origin/main` 最新提交 `96861b5`。
- 跟进 PR #65 review comment：`sql/incremental/01_refresh_stock_dwd_dws_window.sql` 增加目标表存在性 ASSERT，并用 BigQuery transaction 包住 9 张 DWD/DWS 目标表的窗口 DELETE/INSERT。
- 新增 `scripts/qa/run_windowed_refresh_equivalence.py`，用于发布前/定期在 scratch 表中对比 canonical full SQL 与 window SQL 的窗口内逐列数值等价。
- 同步 `sql/README.md`、`TODO.md` 和 OQ-005 相关记忆，明确大区间 backfill 按年/季/月分块执行，窗口 SQL 与 canonical full SQL 双实现并存期间必须跑等价 QA。

### 重要上下文

- 本次只修改 PR #65 分支内容，未部署 Composer，未执行生产 DML，未写 BigQuery/GCS/ADS 产物。
- 等价 QA runner 默认 scratch dataset 为 `ashare_qa_windowed_equivalence`；真实执行会创建 `_full` / `_window` shadow 表，不应修改生产 DWD/DWS 表。
- `git stash pop` 后的冲突已解决；本次 rebase 前安全备份 stash 已删除，仓库里剩余的 `stash@{0}: autostash` 不是本次 PR #65 follow-up 备份。

### 改动文件

- `sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `scripts/qa/run_windowed_refresh_equivalence.py`
- `sql/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py scripts/qa/run_windowed_refresh_equivalence.py`
- `python3 scripts/qa/run_windowed_refresh_equivalence.py --dry-run`
- `bq query --dry_run`：窗口 SQL `backfill` / `daily_current` 参数各一次。
- `bq query --dry_run`：`sql/qa/10_windowed_stock_refresh_checks.sql` `backfill` / `daily_current` 参数各一次。
- `git diff --check --cached`

### 阻塞项

- 无。

### 下一步建议

- 提交并 force-with-lease 推送 rebase 后的 PR #65 分支。
- PR 合并后先做 `skip_ingestion=true` + `warehouse_mode=backfill` 小窗口 Composer smoke，再做 `daily_current` scheduler smoke 和 `qa_only` 验收。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

---
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-005 Phase 2.2 / 股票 DWD-DWS 窗口刷新

### 已完成工作

- 在工作树 `/private/tmp/quant-ashare-windowed-refresh`、分支 `codex/windowed-dwd-dws-refresh` 实现股票 DWD/DWS 窗口刷新。
- 新增 `sql/incremental/01_refresh_stock_dwd_dws_window.sql`，对 `dwd_stock_eod_price`、`dwd_stock_eod_valuation`、策略 1 universe/price/valuation/finance/label/feature/sample DWS 做参数化窗口 DELETE/INSERT。
- 新增 `sql/qa/10_windowed_stock_refresh_checks.sql`，覆盖窗口内主键唯一、生命周期、退市日、ODS daily 表示性、停牌语义和 trainable sample 基础断言。
- `orchestration/composer/dags/ashare_daily_pipeline_v0.py` 新增 `daily_current/backfill` 窗口分支：真实写入时刷新 DIM 小表、恢复 P0 metadata、执行窗口刷新和窗口 QA；`pipeline_dry_run=true` 不写表。
- 同步修复 Composer project/region/location 常量，避免 BigQuery operator `location` 使用未渲染 Jinja。
- `sql/meta/01_create_meta_tables.sql` 合并同表多列 `ADD COLUMN IF NOT EXISTS`，降低连续 table update 限流风险。
- 更新 `orchestration/README.md`、`orchestration/composer/README.md`、`sql/README.md`、`TODO.md` 和相关记忆。

### 重要上下文

- 本次未部署 Composer，未触发 DAG，未执行生产 BigQuery DML，未写 GCS/ADS/report 产物。
- 窗口脚本假设目标 DIM/DWD/DWS 表已由全量 CTAS 路径初始化；ADS runner/backtest/report 仍由策略 runner 独立写入。
- `full_rebuild` / `full_rebuild_compat` 保留原全量兼容链路；`qa_only` 保持只读；`enable_ads_contract_init=true` 仍是 ADS 契约初始化的唯一入口。
- 窗口标签回补是 20 个 SSE 交易日，价格特征读取回看是 60 个 SSE 交易日；后续 hotfix 已把估值特征读取边界改为按每只股票实际 60 条估值观测推导，以覆盖 `daily_basic` 缺口。

### 改动文件

- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `orchestration/composer/README.md`
- `orchestration/README.md`
- `sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `sql/qa/10_windowed_stock_refresh_checks.sql`
- `sql/meta/01_create_meta_tables.sql`
- `sql/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=date_from:STRING:2026-06-03 --parameter=date_to:STRING:2026-06-04 --parameter=warehouse_mode:STRING:backfill < sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=date_from:STRING: --parameter=date_to:STRING:2026-06-04 --parameter=warehouse_mode:STRING:daily_current < sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=date_from:STRING:2026-06-03 --parameter=date_to:STRING:2026-06-04 --parameter=warehouse_mode:STRING:backfill < sql/qa/10_windowed_stock_refresh_checks.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=date_from:STRING: --parameter=date_to:STRING:2026-06-04 --parameter=warehouse_mode:STRING:daily_current < sql/qa/10_windowed_stock_refresh_checks.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/meta/01_create_meta_tables.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/metadata/01_p0_table_column_descriptions.sql`

### 阻塞项

- 无代码阻塞；生产前仍需部署 Composer 并做 `skip_ingestion=true` + `warehouse_mode=backfill` 窗口 smoke、`daily_current` scheduler smoke 和 `qa_only` 验收。

### 下一步建议

- 运行 `git diff --check` 后提交 PR。
- PR 合并后同步 DAG 与 `sql/` 到 Composer bucket。
- 先用 `skip_ingestion=true`、`pipeline_dry_run=false`、`warehouse_mode=backfill`、小日期窗口做生产 DML smoke，再恢复/观察 `daily_current` scheduler。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

---
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: s1_cloudrun_sklearn_smoke_20260604_02 / bt_s1_cloudrun_sklearn_smoke_20260604_02
相关 issue/PR: OQ-010 / Strategy 1 Cloud Run real smoke

### 已完成工作

- 在独立工作树 `/Users/luna/Desktop/git/quant-ashare-cloudrun-smoke`、分支 `codex/cloudrun-smoke` 上完成策略 1 Cloud Run 真实 smoke 收尾。
- 修复 `orchestrate_experiments.py` 的 `gcloud run jobs execute --args`，确保通过 orchestrator 启动 Cloud Run Job 时包含 `python -m scripts.strategy1_cloudrun.train_predict` / `backtest_report` module。
- 修复 `cloudbuild.strategy1-cloudrun.yaml` 本地 build 时 `$SHORT_SHA` 为空的问题，改为显式 `_TAG` substitution，并同步运行手册 build/deploy 命令。
- 优化 Cloud Run 训练内存：`feature_column_list` 兼容 BigQuery Storage / pandas array-like `.tolist()`；特征矩阵改为预分配 `float32`；展开特征后丢弃 raw JSON 列。
- 将 sklearn vs BQML parity 未通过从 fail-fast 改为记录证据：未通过时仍写 selected registry / prediction / artifact，但必须标记 `model_quality_status=model_quality_not_equivalent`，正式 baseline QA 默认仍要求 parity passed。
- 放宽 score orientation QA 容差到 `1e-6`，覆盖 Python / BigQuery float round-trip 的 `~3e-8` 误差。
- 给 Cloud Run 容器安装 `fonts-noto-cjk`，并在 `render_report.py` 扩展 Noto CJK 字体候选，消除中文报告图表 glyph missing 警告。
- 补充运行手册中的 Cloud Run runtime service account IAM、16Gi/4CPU/`--max-retries=0` 和 smoke / 正式 parity QA 区分。

### 重要上下文

- 使用 Artifact Registry repo `quant-ashare` 和镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner@sha256:6564434f9f216aec6c86cae3923bc44450c3ca26ead14a248b05ca77087d8ead`。
- Cloud Run Jobs：`strategy1-train-predict-job`、`strategy1-backtest-report-job`，均配置 16Gi/4CPU/`--max-retries=0`。
- runtime service account：`241358486859-compute@developer.gserviceaccount.com`，已补 `ashare_ads` dataset WRITER 权限。
- smoke experiment：`cloudrun_smoke_pvfq_n30_bw_h5`，对应正式 BQML reference run `s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01`。
- train/predict execution：`strategy1-train-predict-job-s5725`，prediction 1,056,716 行，selected candidate `elastic_c_1_l1_0_5`，score orientation `reverse_probability`。
- backtest/report execution：`strategy1-backtest-report-job-6fzvr`，完成时间约 2m58s，无 ERROR / CJK glyph warning。
- report URI：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_cloudrun_sklearn_smoke_20260604_02/backtest_id=bt_s1_cloudrun_sklearn_smoke_20260604_02`。
- 回测指标：total_return 46.29%、annual_return 21.72%、Sharpe 1.111、max_drawdown -13.94%、excess_return 17.28% vs `000852.SH`。
- 模型质量 caveat：BQML valid RankIC 0.09676，sklearn valid RankIC 0.06665，rank delta -0.03011 超出 0.02 阈值；`model_quality_parity_status=failed`，`model_quality_status=model_quality_not_equivalent`。

### 改动文件

- `Dockerfile.strategy1-cloudrun`
- `cloudbuild.strategy1-cloudrun.yaml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1/render_report.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/preprocess.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/train_predict.py scripts/strategy1_cloudrun/backtest_report.py scripts/strategy1_cloudrun/orchestrate_experiments.py scripts/strategy1_cloudrun/preprocess.py scripts/strategy1/render_report.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`
- Cloud Build 成功：build id `52191460-108a-404b-8017-c65eaa8ef259`。
- Cloud Run orchestrator resume from `cloudrun_backtest_report` 成功，final execution `strategy1-backtest-report-job-6fzvr` succeeded。
- `16_qa_cloudrun_runner_outputs.sql` 以 smoke 参数 `p_require_model_quality_parity_passed=FALSE` 通过。
- `17_qa_cloudrun_orchestrator_status.sql` 通过。
- `gcloud logging read` 未发现 final execution ERROR 或 CJK glyph warning。
- `git diff --check`。

### 阻塞项

- 无运行链路阻塞。模型质量阻塞仍存在：当前 sklearn backend 未达到 BQML baseline parity，不能作为正式替代。

### 下一步建议

- 提 PR review 本次 Cloud Run smoke 修复。
- 合并后做 sklearn backend 参数 / 模型族迭代，使 parity gate 通过，或由 owner 明确接受新的 sklearn baseline。
- 补 Python ledger vs SQL ledger 的完整等价验收；当前真实 smoke 已证明 Cloud Run Python ledger 能跑通，但还不是正式等价证明。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`

---
日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: manual_oq005_scheduler_smoke_default_queue_20260604_01 / manual_oq005_daily_prod_20260604_01
相关 issue/PR: OQ-005 / GCP pipeline production ingestion phase 1.7

### 已完成工作

- 在工作树 `/private/tmp/quant-ashare-oq005-deploy-phase1`、分支 `codex/oq005-deploy-phase1` 继续推进 OQ-005 生产采集部署，并在 rebase 到最新 `origin/main` 后保留 main 的策略 1 Cloud Run runner 状态。
- 新增并部署 `ashare-ingest-current-scope` Cloud Run Job，单 execution 顺序执行当前实际消费的 14 个 ODS endpoint；4 个分组 Jobs 保留为诊断和单组补救入口。
- PR #58 review follow-up 已补 live BigQuery meta 状态写入：`ashare_meta.ingestion_run` 和 `ashare_meta.ingestion_partition_status`。
- 已把 raw GCS canonical 路径固定为 `api=<api>/endpoint=<partition_endpoint>/partition_date=...`，并用 BigQuery `INFORMATION_SCHEMA.TABLE_OPTIONS` 只读复核当前 14 张 ODS 与 10 张 schema repair 表 source URI。
- 已明确 ingestion publish 覆盖正式 `data.parquet` 不做 write-once backup；历史可回滚回填留后续独立开关/流程。
- Cloud Run Jobs 已配置 Direct VPC egress + Cloud NAT + 区域静态外部 IP 固定出口；Job 模板默认保留 `--dry-run`，Composer 生产路径显式传入 `--allow-gcs-write`。
- `ashare_daily_pipeline_v0` 已移除 `queue="kubernetes"`，使用 default Celery queue；纯 scheduler smoke `manual_oq005_scheduler_smoke_default_queue_20260604_01` 成功。
- 生产 GCS 回填已完成：`2026-05-20` 至 `2026-06-03` 区间内 SSE 开市日全部写入成功，并逐日通过 `sql/qa/09_ods_daily_partition_readiness.sql`。
- Composer 生产 DAG 首跑 `manual_oq005_daily_prod_20260604_01` 已写入 `2026-06-04` 数据并成功完成 readiness。
- Airflow 变量当前为 `ashare_pipeline_dry_run=false`、`ashare_enable_full_refresh=false`。

### 重要上下文

- 当前只启用 ODS 生产采集和每日分区 readiness；完整 ODS→DIM/DWD/DWS/ADS 转换仍在 `ashare_enable_full_refresh=true` 显式分支之后，尚未作为生产链路验收。
- Cloud Run Job 模板保留 `--dry-run` 是安全门禁；生产写入依赖 Composer 传参，不能在脚本中移除 token/dry-run guard。
- Token 只保存在 Secret Manager，不写仓库、文档、日志或记忆。
- `ods_tushare_stk_limit` 历史 Parquet schema mismatch 仍属于 OQ-012 维护/修复工作，不阻断每日生产采集。

### 改动文件

- `scripts/ingestion/run_ingestion_job.py`
- `scripts/ingestion/README.md`
- `scripts/ingestion/common/gcs_writer.py`
- `scripts/ingestion/common/status_writer.py`
- `configs/ingestion/schema_contracts/suspend_d.json`
- `orchestration/cloud_run_jobs/deploy_ingestion_jobs.sh`
- `orchestration/cloud_run_jobs/ingestion_jobs.yaml`
- `orchestration/cloud_run_jobs/README.md`
- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `orchestration/composer/README.md`
- `orchestration/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- Artifact Registry latest digest 确认为 `sha256:351dfd996b6ec066135d68c40f84eb1c2a52e43ea8e28208ba1711be90a7652d`。
- `gcloud composer environments run ... variables get -- ashare_pipeline_dry_run` 返回 `false`。
- `gcloud composer environments run ... variables get -- ashare_enable_full_refresh` 返回 `false`。
- `gcloud composer environments run ... dags state -- ashare_daily_pipeline_v0 2026-06-04T15:15:08+00:00` 返回 `success, {"business_date": "2026-06-04"}`。
- `2026-05-20` 至 `2026-06-03` SSE 开市日生产回填均有对应 Cloud Run execution 成功记录，并逐日通过 `sql/qa/09_ods_daily_partition_readiness.sql`。
- `git rebase origin/main` 成功。
- `git diff --check` 通过。

### 阻塞项

- 无当前采集阻塞。OQ-005 仍未关闭，因完整 ODS→ADS 生产转换、告警、补跑和运维观测尚未验收。

### 下一步建议

- 接入/验证 Dataform 或 BigQuery SQL 生产转换链路。
- 补 Cloud Composer 告警、补跑和运行状态观测。
- 明确 ODS→ADS full refresh 的生产启用窗口，再将 `ashare_enable_full_refresh=true` 作为单独维护/补跑任务验收。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

---
日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / Cloud Run orchestrator status and lock implementation

### 已完成工作

- 通过 GitHub API 合并 PR #56，并删除远端 `codex/implement-strategy1-cloudrun-runner` 分支。
- 创建工作树 `/Users/luna/Desktop/git/quant-ashare-cloudrun-orchestrator-state-lock`，分支 `codex/cloudrun-orchestrator-state-lock`。
- 新增 `scripts/strategy1_cloudrun/state.py`，封装 `OrchestratorStatusTable`、GCS generation-guarded lease lock、heartbeat/release、experiment params JSON 和 Cloud Run execution id 提取。
- 改造 `scripts/strategy1_cloudrun/orchestrate_experiments.py`：每个实验链的 `cloudrun_train_predict` / `cloudrun_backtest_report` step 写入 `ashare_meta.strategy1_experiment_run_status`，执行前获取 GCS lock，执行中 heartbeat，支持 `--resume` 跳过已成功 step，支持 `--resume-from-step cloudrun_backtest_report` 从指定 step 继续。
- 新增 `sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`，校验 orchestrator 状态、锁元数据、审计字段和 execution id 记录。
- 跟进 PR #57 review comment：Cloud Run orchestrator 改为先启动 execution、记录 execution id 到 GCS lock/status table，再轮询 execution terminal 状态；stale lock 回收前会检查原 execution 是否 terminal；失锁时 cancel 当前 execution；heartbeat 的 GCS/BQ 瞬时错误不再杀线程；QA-CRO-4 改为断言 succeeded step 必须记录 execution id。
- 同步 Cloud Run 默认配置、运行手册、runner README、`TODO.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要。

### 重要上下文

- 当前分支只做 orchestrator 状态/锁/resume 增强；没有启动真实 Cloud Run Job，没有重建 ADS 表，没有上传真实 sklearn model artifact。
- 状态表复用既有 `sql/meta/02_strategy1_experiment_run_status.sql`；执行 Cloud Run orchestrator 前必须先确保该表存在。
- GCS lock 默认路径为 `gs://ashare-artifacts/locks/strategy1/cloudrun/<lock_key>.lock`，lock key 使用 prediction run 或 backtest id 分离 train/predict 与 backtest/report step。
- `attempt` 只在非 running 状态进入 running 时增加；heartbeat 只刷新 lease 和 running 状态，不反复增加 attempt。
- `gcloud run jobs execute` 不再加 `--wait`；orchestrator 启动 execution 后用 `gcloud run jobs executions describe` 轮询状态，因此 stale lock payload 中能保留可检查的 execution id。

### 改动文件

- `configs/strategy1/cloudrun_runner_default.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/state.py`
- `sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`

### 测试 / 验证

- `python3 -m compileall scripts/strategy1_cloudrun`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --experiment-id oq010_a0_n5_w20 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --experiment-id oq010_a0_n5_w20 --resume-from-step cloudrun_backtest_report --dry-run`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --stage-id stage_a --resume --dry-run`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/meta/02_strategy1_experiment_run_status.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`
- 小单元式校验：`extract_cloud_run_execution_id` 可从 `metadata.name` 和完整 `/executions/` resource name 提取 execution id；`cloud_run_execution_state` 可识别 succeeded / failed / completionTime。
- `git diff --check`

### 阻塞项

- 无代码阻塞。真实验收仍需部署/确认 Cloud Run Jobs 后跑单实验 smoke。

### 下一步建议

- 提 PR review 本次 Cloud Run orchestrator 状态/锁增强。
- 合并后执行单实验真实 Cloud Run smoke，跑 `16_qa_cloudrun_runner_outputs.sql` 与 `17_qa_cloudrun_orchestrator_status.sql`。
- 用真实 smoke 结果验证 sklearn vs BQML parity、Python ledger vs SQL ledger 等价性、GCS model/report artifact 和 ADS 回写。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

---
日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / Cloud Run strategy1 runner implementation

### 已完成工作

- 启动并完成策略 1 Cloud Run 训练回测执行器首版实现，工作分支 `codex/implement-strategy1-cloudrun-runner`，worktree `/Users/luna/Desktop/git/quant-ashare-strategy1-cloudrun-runner`。
- 新增 `scripts/strategy1_cloudrun/` Python 包：配置/实验 manifest 解析、BigQuery/GCS IO、sklearn 训练预测、Python fresh-start ledger、SQL 参数化 runner、Cloud Run 多实验 orchestrator。
- 新增 `Dockerfile.strategy1-cloudrun`、`cloudbuild.strategy1-cloudrun.yaml`、`configs/strategy1/cloudrun_runner_default.yml` 和 `docs/策略1CloudRun训练回测运行手册.md`。
- 新增 `sql/meta/03_strategy1_cloudrun_status_extensions.sql` 和 `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`；`09_build_metrics_and_report_inputs.sql` 已把 `execution_backend` 写入 summary `metrics_json`。
- `sql/ml/strategy1/README.md` 和 `scripts/strategy1/requirements.txt` 已同步 Cloud Run / sklearn runner 运行说明和依赖。
- 跟进 PR #56 review comment：确认 QA-CR-5 提到的 `ledger_version` 缺失不成立（`09` 已写入该字段）；同时补 `p_ledger_version` / `p_ledger_executor` 参数化、`--use-bq-ledger` fallback backend 标记、parity failed fail-fast 与 QA hard gate、orchestrator 失败结果汇总和 `--continue-on-error`。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要。

### 重要上下文

- 当前首版边界：`01_build_training_panel.sql` 仍是前置 SQL；`05/06/07` 仍复用 BigQuery SQL；Python ledger P0 只支持 fresh-start，resume 先 fail-fast，等 Python ledger vs SQL ledger 等价验收后再补。
- Cloud Run orchestrator 遵守 PRD 并发契约：未设置或传 `0` 时，默认并发数等于 manifest 中可执行实验数量；owner 可用 `--max-parallel-experiments N` 显式限流。P0 采用唯一 `run_id` / `backtest_id` + Cloud Run execution 轻隔离，尚未写 `strategy1_experiment_run_status` / GCS lock，真实多实验 smoke 后再对齐状态框架。
- 为避免 Cloud Run job 读取本地临时 manifest，orchestrator 已把 resolved experiment payload 通过 URL-safe base64 `--experiment-json` 传入 job。
- 本地 Python 3.9 环境未安装 sklearn/joblib；代码已使用 lazy import，使 dry-run 不依赖本地 sklearn。真实训练应在 Cloud Run 镜像内用 Python 3.11 和 requirements 执行。
- 本次没有执行真实 Cloud Run job，没有重建 ADS 表，没有上传真实 sklearn model artifact。

### 改动文件

- `Dockerfile.strategy1-cloudrun`
- `cloudbuild.strategy1-cloudrun.yaml`
- `configs/strategy1/cloudrun_runner_default.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1/requirements.txt`
- `scripts/strategy1_cloudrun/*`
- `sql/meta/03_strategy1_cloudrun_status_extensions.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`

### 测试 / 验证

- `python3 -m compileall scripts/strategy1_cloudrun`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --experiment-id oq010_a0_n5_w20 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --stage-id stage_a --dry-run`
- `python3 -m scripts.strategy1_cloudrun.train_predict --experiment-id oq010_a0_n5_w20 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.backtest_report --experiment-id oq010_a0_n5_w20 --dry-run`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/meta/03_strategy1_cloudrun_status_extensions.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `git diff --check`
- PR #56 review follow-up 后补跑：`python3 -m compileall scripts/strategy1_cloudrun`、`python3 -m scripts.strategy1_cloudrun.backtest_report --experiment-id oq010_a0_n5_w20 --dry-run`、`python3 -m scripts.strategy1_cloudrun.backtest_report --experiment-id oq010_a0_n5_w20 --use-bq-ledger --dry-run`、`python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --stage-id stage_a --dry-run`、`09` / `16` BigQuery dry-run、`git diff --check`。

### 阻塞项

- 无代码阻塞。真实验收仍需部署 Cloud Run Jobs 并跑单实验 smoke。

### 下一步建议

- 提 PR review 本次 Cloud Run runner 首版实现。
- PR review 通过后部署 Cloud Run image/jobs，跑单实验真实 smoke。
- 真实 smoke 后补 sklearn vs BQML parity、Python ledger vs SQL ledger 等价验收；等 fresh-start 等价通过后再实现 resume path。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

---
日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / Cloud Run training and backtest PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`。
- PRD 决定只写一篇统一文档，不拆训练 PRD 和回测 PRD，避免训练、预测、回测、实验并发和 artifact 契约漂移。
- PRD 定义 Cloud Run Jobs + scikit-learn logistic 训练 / 预测 + Python `ledger_exec_v1` 回测的目标执行路径。
- PRD 明确 scikit-learn 只替代 BQML `LOGISTIC_REG` 的模型训练 / 预测，不替代 BigQuery DWS/ADS、GCS artifact、报告诊断和 QA；P0 仍需 BigQuery / GCS 客户端、`pyarrow`、`polars` 或 `pandas`、`joblib` 等依赖。
- PRD 固化 Cloud Run 多实验默认并发规则：`--max-parallel-experiments` 未设置或为 0 时，并发数等于 manifest 可执行实验数量；owner 显式传 N 时才限流。
- 跟进 PR #55 review comment `issuecomment-4622638415`：补 sklearn vs BQML 模型质量对等门槛；P0 默认 `class_weight=None`；明确 sklearn 正则网格是重新定义，不直接翻译 BQML `L1_REG` / `L2_REG`。
- 新增 `DECISION-20260604-03`，并同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`KNOWN_CONSTRAINTS.md`、`PROJECT_CONTEXT.md`、`ARCHITECTURE_MEMORY.md` 和当前交接摘要。

### 重要上下文

- 本次只写 PRD 和记忆/TODO，没有实现 Cloud Run 代码，没有创建 GCP 资源，没有执行 BigQuery，也没有生成或覆盖报告 artifact。
- 既有 BigQuery ML + SQL runner 当时保留为 reference / fallback；2026-06-05 owner 决策已 supersede，本路径仅保留为 historical reference / audit。
- Cloud Run runner 的默认全实验并发是 owner 明确要求；不要沿用本地 OQ-010 调度器 `max_parallel=2` / `max_parallel_backtest=1` 的保守默认值。

### 改动文件

- `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review 并合并 Cloud Run 训练回测 PRD。
- 实现前先确认 Cloud Run region、service account、artifact bucket 和容器构建方式；默认沿用 `asia-east2`、`data-aquarium`、`gs://ashare-artifacts`。
- PRD 合并后新增 `scripts/strategy1_cloudrun/`、Cloud Run Dockerfile / build config、`sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql` 和运行手册。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

---
日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01 / bt_ledger_v1_p0_smoke_20260604_01
相关 issue/PR: OQ-010 / Ledger v1 P0 implementation

### 已完成工作

- 实现策略 1 `ledger_exec_v1` P0 交易执行语义。
- `08_run_backtest.sql` 改为日级账户 ledger：t-1 信号 / t 开盘执行、每日 pending sell retry、卖出先于买入、实际持仓 netting、现金缩放、非目标持仓继续 mark-to-market、订单状态显式记录。
- 同步 `09` 指标汇总、`10` runner QA、`11` 诊断 SQL、ADS 字段说明、报告脚本、诊断脚本和 README。
- 修复报告买入明细关联预测表时缺少 `predict_date` 分区过滤的问题。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`KNOWN_CONSTRAINTS.md` 和当前交接摘要。

### 重要上下文

- P0 仍保留 PRD 定义的简化：FLOAT 股数、不做 100 股手数约束、不显式 T+1 卖出锁定、不做买入候补、不做 partial-fill 深度模型。
- 短区间 smoke 使用正式 baseline prediction run：`s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01`，新建 smoke backtest：`bt_ledger_v1_p0_smoke_20260604_01`，窗口 `2024-01-02` 至 `2024-02-29`。
- smoke `render_report.py` 使用 `--skip-gcs-upload`，只验证本地报告和 ADS 回写，不上传 GCS。

### 改动文件

- `sql/ml/strategy1/08_run_backtest.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/11_model_quality_diagnostics.sql`
- `sql/ads/01_ads_strategy1_tables.sql`
- `scripts/strategy1/render_report.py`
- `scripts/strategy1/diagnose_model_quality.py`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `bq query --dry_run`：`08_run_backtest.sql`、`09_build_metrics_and_report_inputs.sql`、`10_qa_runner_outputs.sql`、`11_model_quality_diagnostics.sql`、`sql/ads/01_ads_strategy1_tables.sql`
- `python3 -m py_compile scripts/strategy1/render_report.py scripts/strategy1/diagnose_model_quality.py`
- 短区间 BigQuery smoke：`08`、`09`、`render_report.py --skip-gcs-upload`、`10_qa_runner_outputs.sql` 全部通过
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review/merge Ledger v1 P0 实现 PR。
- 合并后用正式 baseline 参数跑完整 `2024-01-02` 至 `2025-12-31` 同区间 A/B，对比旧 ledger 与 `ledger_exec_v1`。
- A/B 收敛后再做 P1 fixed-model 连续扩展回测至 `2026-04-30` 和 P2 state resume。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

---
日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / factor attribution PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260604_03_策略1因子贡献度分析.md`。
- 明确本轮因子贡献度分析不做消融实验，不重训、不 drop factor，只读当前 baseline。
- 因子贡献度 PRD 定义模型系数/标准化系数、单因子 RankIC/bucket lift、score contribution、组合因子暴露、归因 proxy 和因子相关性/共线性摘要。
- 更新 Ledger PRD 和月度重训 PRD 的推荐实施顺序：因子贡献度分析 → Ledger v1 P0/P1/P2 → 月度滚动重训。
- 跟进 PR #51 comment，补充多重共线性解释边界：单因子系数排名不稳定、组级解读优先、单因子 RankIC 与多变量系数可能不一致、proxy 贡献不可跨相关因子加总。
- 新增 `DECISION-20260604-02` 并同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要。

### 重要上下文

- 因子贡献度分析只是实施顺序上的前置解释基准，不代表优先级高于 Ledger 或月度重训。
- 当前 PRD 已把高相关因子问题写成解释约束；实现时必须输出 `factor_correlation_summary.csv` 并在中文摘要提示共线性限制。
- P0 推荐实现为独立 `scripts/strategy1/attribute_factor_contribution.py`，产出 `factor_attribution/` artifact，再用 `14_qa_factor_attribution_outputs.sql` 验收。
- 若未来要做消融实验，需要另写 PRD；本 PRD 明确禁止把消融路径混进 P0。

### 改动文件

- `docs/prd/PRD_20260604_03_策略1因子贡献度分析.md`
- `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review 并合并因子贡献度 PRD。
- 合并后实现 `attribute_factor_contribution.py` 和 `14_qa_factor_attribution_outputs.sql`，先对正式 baseline 生成 factor attribution artifact。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

---
日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / Ledger v1 PRD / monthly retrain PRD

### 已完成工作

- 按 owner 采纳的方案改造两篇 PRD：不新增第三篇 PRD。
- `PRD_20260604_01_策略1LedgerV1交易执行语义.md` 已扩展为 Ledger P0/P1/P2：P0 交易执行语义、P1 `2024-01-02` 至 `2026-04-30` fixed-model 连续扩展回测、P2 ledger state resume。
- `PRD_20260604_02_策略1月度滚动重训.md` 已收敛为只定义模型生命周期、失败回退和 PIT-safe prediction stream，并明确依赖 Ledger P0/P1/P2。
- 新增 `DECISION-20260604-01`，固化实现顺序为 Ledger v1 P0 → Ledger v1 P1 → Ledger v1 P2 → 月度滚动重训。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要。

### 重要上下文

- 2026 扩展回测和 resume 均归入 Ledger/backtest 执行能力，不归入月度重训。
- P1 扩展回测必须 fixed-model fresh-start 从 `2024-01-02` 连续跑到 `2026-04-30`；不能用只跑 2026 片段再简单拼接替代。
- 月度重训正式效果归因必须等 Ledger P0/P1/P2 稳定后再做。

### 改动文件

- `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 提 PR review 两篇 PRD 改造。
- PRD 合并后先实现 Ledger v1 P0 交易执行语义并用正式 baseline 参数 A/B。
- P0 稳定后再做 P1 fixed-model 扩展回测和 P2 resume；最后实现月度滚动重训。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`
---
日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / Ledger v1 PRD / monthly retrain PRD / memory cleanup

### 已完成工作

- 清理工作记忆：`AGENT_HANDOFF.md` 缩到当前摘要 + 最近 3 条交接，19 条旧交接归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。
- 新增 `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`。
- 新增 `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`。
- 跟进 PR #49 review comment，补充 Ledger PRD 的 T+1 卖出锁定非目标、月度重训 PRD 的 oriented RankIC 通过标准和 test split 事后评价口径。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要。

### 重要上下文

- Ledger v1 PRD 固化 t-1 信号 / t 开盘执行、pending sell 每日继续卖、实际持仓 netting、现金缩放、订单状态和每日 mark-to-market NAV；明确不改变模型训练/预测来源。
- 月度滚动重训 PRD 定义 monthly cadence、rolling 5 年训练窗口、12 个月 valid 窗口、月内固定模型、失败回退和 PIT-safe prediction stream。
- 实现顺序必须先 Ledger v1 A/B，再月度重训，避免交易执行语义变化和模型生命周期变化混在一起。

### 改动文件

- `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 提 PR review 两篇 PRD。
- PRD 合并后先实现 Ledger v1 交易执行语义，并用正式 baseline 参数 A/B。
- Ledger v1 A/B 收敛后，再实现月度滚动重训 prediction stream。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

---
日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #70 / OQ-005 / OQ-012 memory update

### 已完成工作

- 确认 PR #70 实现工作树为 `/private/tmp/quant-ashare-oq005-daily-window-hardening`，分支 `codex/oq005-daily-window-hardening`；该工作树与分支已在 PR #70 合并后清理。
- 在当前主工作树 `/Users/luna/Desktop/git/quant-ashare` 更新项目记忆与 TODO，补齐 PR #70 合并后的 Composer SQL 同步和 smoke 事实。
- 记录 Composer bucket `data/sql/` 中 `sql/incremental/01_refresh_stock_dwd_dws_window.sql` 与 `sql/qa/10_windowed_stock_refresh_checks.sql` 哈希均与当前 `main` 一致。
- 记录 OQ-005 smoke：`manual_oq005_backfill_smoke_pr70_20260605_01` 成功；`manual_oq005_daily_current_nontd_20260606_01` 因 `2026-06-05` ODS 未采集在 readiness 阶段以 `QA-ODS-DAILY-2` 阻断，窗口写入未执行。
- 记录 QA-WIN-18 只读复核：`2026-06-03..2026-06-04` expected rows 11,022，false/missing 0。
- 更新 OQ-012 状态：`sql/qa/06_ods_parquet_schema_checks.sql` 对 P0 与 all 范围均通过，当前 BigQuery 读层未再暴露 schema mismatch。

### 重要上下文

- 本次只更新记忆/TODO，没有修改 SQL、DAG、部署配置或生产资源。
- OQ-005 仍 open，剩余 Dataform definitions、告警、补跑和完整运维观测闭环。
- OQ-012 当前读层 QA 已通过；是否关闭/归档，或保留 schema contract / ingestion 显式 cast 防复发任务，待 owner 决定。
- `2026-06-05` ODS 尚未采集时，非交易日 daily_current 只能验证 readiness 阻断，不能验证“有 ODS 时的非交易日正向窗口刷新”。

### 改动文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`
- `git status --short --branch`

### 阻塞项

- 无。

### 下一步建议

- 等 `2026-06-05` ODS 采集完成后，再跑一次非交易日 daily_current 正向 smoke，验证归一到最近交易日且窗口刷新成功。
- 继续 OQ-005 的 Dataform definitions、告警、补跑和 pipeline 观测闭环。
- 由 owner 决定 OQ-012 是否关闭/归档。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

## 2026-06-05 追加归档：PR #75 main 交接在 PR #76 瘦身前归档

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: sklearn_native_pvfq_n30_bw_h5_20260605_01
相关 issue/PR: PR #73 / sklearn native search result closeout

### 已完成工作

- 合并 PR #73 后构建并部署镜像 `sklearn-native-topk-fix-6856a46-20260605154227` 到策略 1 Cloud Run Jobs。
- 未从头重跑 `prepare_matrix` 或 36 个 candidate fan-out；复用已完成的 `strategy1-prepare-matrix-job-d697c` 和 `strategy1-train-candidate-fanout-job-tpl9v`。
- 补跑并完成 Top5 select/register/predict 与 backtest/report/diagnosis；5 个 Top5 backtest/report execution 均成功。
- 修正 3 条因本地 orchestrator 中断而遗留为 `cancelled` 的 backtest 状态，并清理对应 stale GCS locks。
- 重新生成并上传 sklearn native comparison artifacts 到 GCS，执行 `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql` 且通过。
- 按 PR #74 comment 清理当前交接摘要中已被收口结论取代的 PR #71 / 实现分支旧块，并把 `IMPLEMENTATION_STATUS.md` 中对应 dry-run 记录标为历史补充，避免当前摘要区残留“未实跑”断言。

### 重要上下文

- 最终 comparison URI：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/search_id=sklearn_native_pvfq_n30_bw_h5_20260605_01`。
- Top5 全部 `native_acceptance_status=rejected`，拒绝原因为 `test_year_excess_return<=0.0`。
- Top1 `elastic_saga_c_0_1_l1_0_5_balanced` full-period total_return 45.31%、excess_return 16.30%、Sharpe 1.089、test RankIC 0.034，但 2025 test-year excess_return -14.92%。
- 本轮不建立 `cloud_run_sklearn_native_baseline_v1`；BQML baseline 仍是当前正式 baseline / fallback。

### 改动文件

- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- Cloud Run execution 核对：Top5 backtest/report 5/5 succeeded。
- `gsutil ls gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/search_id=sklearn_native_pvfq_n30_bw_h5_20260605_01` 返回 7 个 comparison artifacts。
- `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql` 执行通过。
- 本地 comparison JSON / CSV 与 GCS 上传结果一致。

### 阻塞项

- 无执行阻塞；结果层面 sklearn native 首轮未达到 acceptance，不能接受为新 baseline。

### 下一步建议

- 不再重复跑本轮 search；下一步先回到 BQML baseline / Ledger P1+P2 / 2026 扩展验证，或另开新一波 sklearn native 实验并按 `test_reuse_wave_no` 规则记录。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/OPEN_QUESTIONS.md`

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #72

### 已完成工作

- 查看 PR #72 最新 comment，确认并修复新 P1：`setup_alerts.py` 创建 Cloud Logging `LogMetric` 时改用正确 proto 字段 `filter`。
- 修复告警查询脚本的 fail-open 风险：`--write-log` 缺 `google-cloud-logging` 时 exit 1；默认 lookback 从 60 分钟改为 10 分钟；写日志时按 `alert_type/resource_id/finished_at` 生成稳定 `insert_id`，降低定时重跑造成的重复日志。
- 同步 runbook / README / SQL 注释：`task_failure` 覆盖所有失败 task，`ingestion_failed` 只覆盖 `status='failed'` 且不含 `empty_return`；`v_alert_probe` 明确为固定 24 小时手工健康检查视图。
- 同步 `TODO.md` 与实现状态 / 交接记忆。

### 重要上下文

- 本次未部署 BigQuery 视图、未配置 Cloud Monitoring policy、未执行生产 smoke；PR #72 合并后仍需在 GCP 环境创建视图、部署定时 checker、创建 log-based metrics / alert policies 并验证告警链路。
- 本机 Python 缺 `google-cloud-logging`，已验证缺依赖时 `--write-log` fail-closed；真实 `LogMetric(filter=...)` apply 需在安装依赖的运行环境验证。

### 改动文件

- `sql/observability/01_pipeline_status_views.sql`
- `scripts/alerting/setup_alerts.py`
- `scripts/alerting/check_alerts.py`
- `scripts/alerting/README.md`
- `docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/alerting/check_alerts.py scripts/alerting/setup_alerts.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/observability/01_pipeline_status_views.sql`
- `python3 scripts/alerting/check_alerts.py --lookback-minutes 1 --json`（本地因 `v_alert_summary` 未部署 exit 1，符合查询失败 fail-closed）
- `write_to_cloud_logging` 缺 `google-cloud-logging` 时抛 `AlertLogWriteError`
- `git diff --check`

### 阻塞项

- 无代码阻塞；生产部署/验收待 PR 合并后执行。

### 下一步建议

- 合并 PR #72 后执行 `sql/observability/01_pipeline_status_views.sql` 创建视图。
- 在安装 `google-cloud-logging` / `google-cloud-monitoring` 的运行环境执行 `setup_alerts.py` 创建 log-based metrics 和 alert policies。
- 部署 `check_alerts.py --write-log --lookback-minutes 10` 为 Cloud Scheduler / Cloud Run 定时检查，并做故障样本 smoke。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #71 final follow-up

### 已完成工作

- 接受 PR #71 非阻断观察：valid 侧 `top_minus_bottom_fwd_ret_mean` 用 5 分桶，test 侧之前用 10 分桶，指标同名但粒度不一致。
- 将 `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py` 中 test 侧分桶从 `NTILE(10)` 改为 `NTILE(5)`，高分桶从 `score_bucket=10` 改为 `score_bucket=5`。
- 在 `sql/ml/strategy1/README.md` 标明 valid/test 的 `top_minus_bottom` 均按 5 分桶计算。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要。

### 重要上下文

- 这次只统一指标口径，不改变 native acceptance 的业务门槛，也不部署镜像、不执行真实 36 候选 search。
- 后续仍需部署 Cloud Run 镜像并执行真实 sklearn native search，才能决定是否接受 `cloud_run_sklearn_native_baseline_v1`。

### 改动文件

- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py scripts/strategy1_cloudrun/select_register_predict.py scripts/strategy1_cloudrun/train_predict.py scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `python3 -m compileall -q scripts/strategy1_cloudrun`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_sklearn_native_search ... --candidate-parallelism 0 --top-k-backtest 5 --dry-run`
- `fetch_topk_ads_outputs` runtime SQL BigQuery dry-run
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 合并 PR #71 后构建 / 部署 Cloud Run 镜像。
- 执行真实 36 候选 sklearn native search、Top5 完整回测和 `18` QA。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #71 review follow-up

### 已完成工作

- 查看 PR #71 comment，认可全部 6 条 review 发现并在分支 `codex/implement-sklearn-native-search` 修复。
- `fetch_topk_ads_outputs` 新增 test 期分层高低差 `test_top_minus_bottom_fwd_ret_mean`，并写回 registry / summary metrics。
- `decide_acceptance` 和 `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql` 现在都要求 accepted 候选满足 valid/test top-minus-bottom 不能同时为负。
- QA-SKN-13 改为 `IFNULL(final_holdout_status, '') != 'passed'`，修复 wave>3 accepted 但无 final holdout 证据时被 SQL 三值逻辑放过的问题。
- Python acceptance 的 `test_rank_ic_mean` 与 QA 统一为严格 `> 0`。
- `rank_candidates` 的 fallback 仅限“全员 valid RankIC 非正”，且只允许通过 coverage/orientation/convergence hard filters 的候选 fallback；fallback 候选写 `failed_no_positive_valid_signal`。`convergence_status != 'converged'` 的候选不再能进 Top5。
- Top5 单候选 select/backtest 失败改为 fail-soft：记录该候选失败并等待其余 Top5；最终 `18` QA 仍要求完整 Top5，避免部分成功被误判为验收通过。
- 额外修复 runtime fetch SQL 中无 `predict_date` 分区过滤的多余 `ads_model_prediction_daily` distinct join。
- 同步运行手册、README、TODO 和记忆。

### 重要上下文

- 本轮仍未部署 Cloud Run 镜像，未实跑 36 个候选，未写 ADS/GCS 正式产物。
- 所有 review 点均采纳并修复；没有不认可项。
- Top5 fail-soft 只提高诊断和对比产物完整性；最终通过与否仍由 `18` QA 的完整 Top5 断言决定。

### 改动文件

- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1_cloudrun/select_register_predict.py`
- `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`
- `docs/策略1CloudRun训练回测运行手册.md`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py scripts/strategy1_cloudrun/select_register_predict.py scripts/strategy1_cloudrun/train_predict.py scripts/strategy1_cloudrun/orchestrate_experiments.py`
- ranking fallback 小样例：全员 RankIC 非正、全员 hard fail、正/负混合三类分支均符合预期。
- `python3 -m scripts.strategy1_cloudrun.orchestrate_sklearn_native_search ... --candidate-parallelism 0 --top-k-backtest 5 --dry-run`
- `fetch_topk_ads_outputs` runtime SQL BigQuery dry-run
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`
- `git diff --check`

### 阻塞项

- 无代码阻塞；真实 36 候选尚未执行。

### 下一步建议

- 推送 PR #71 follow-up commit。
- 复核通过后合并 PR #71，构建/部署 Cloud Run 镜像并执行真实 36 候选 search。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #70 / OQ-005 daily_current window hardening

### 已完成工作

- 修复 `sql/incremental/01_refresh_stock_dwd_dws_window.sql` 的 `p_date_to` 表达式，改为显式 `CASE` 分支：`daily_current` 才查最近 SSE 开市日，`backfill` 直接使用请求 `date_to`。
- 修复 `sql/qa/10_windowed_stock_refresh_checks.sql`：估值覆盖 QA 在 `daily_current` 默认使用 20 个交易日窗口，在 `backfill` 使用实际写入窗口。
- 修复 QA-WIN-18：不再按 `pe/pb` 或所有 DWD valuation 行触发；改为在 price-driven feature universe 内，按 `total_mv_cny/circ_mv_cny` 非空检查最终宽表 `has_valuation_data=TRUE`。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`ARCHITECTURE_MEMORY.md`、`KNOWN_CONSTRAINTS.md` 和当前交接摘要。

### 重要上下文

- PR #70 review comment 的 P1/P2/P3 建议均采纳并修复；当前分支仍未部署到 Composer。
- 本次只改 SQL 和记忆/TODO，不执行生产 DML，不触碰 Composer bucket，不覆盖 BigQuery/GCS/ADS 产物。

### 改动文件

- `sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `sql/qa/10_windowed_stock_refresh_checks.sql`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- BigQuery dry-run：窗口 SQL，`warehouse_mode=daily_current`，`business_date=2026-06-06`。
- BigQuery dry-run：窗口 QA，`warehouse_mode=daily_current`，`business_date=2026-06-06`。
- BigQuery dry-run：窗口 SQL，`warehouse_mode=backfill`，`date_from=2026-06-03`，`date_to=2026-06-04`。
- BigQuery dry-run：窗口 QA，`warehouse_mode=backfill`，`date_from=2026-06-03`，`date_to=2026-06-04`。
- 只读窗口计算：`2026-06-06` 归一为 `2026-06-05`，daily_current 估值覆盖起点 `2026-05-11`；backfill `2026-06-03..2026-06-04` 估值覆盖起点 `2026-06-03`。

### 阻塞项

- 无。

### 下一步建议

- 跑 `git diff --check` 后提交并推送 PR #70 分支。
- 合并后同步 `sql/` 到 Composer bucket，再按部署流程做需要的 smoke。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #75 / OQ-005 alerting ops review follow-up

### 已完成工作

- 修复 `scripts/alerting/README.md` 的生产部署口径：当前生产定时入口为 Composer DAG `oq005_alert_checker`，每 10 分钟运行；Cloud Scheduler / cron 仅可作为非生产替代入口。
- 将 `TODO.md` 中 OQ-005 状态从已完成改为进行中，保留告警/观测生产闭环已验收事实，并明确剩余 Dataform definitions、策略 runner/report 可选分支、补跑和完整 ODS→ADS 运维观测闭环。
- 更新 `OPEN_QUESTIONS.md`：OQ-005 不再把“告警”列为剩余关闭项，新增 2026-06-05 告警/观测生产闭环完成事实。
- 刷新本文件顶部交接摘要，移除“提交 PR，更新文档/记忆”的过期下一步。

### 重要上下文

- 本次只修文档和记忆状态，不修改 DAG、SQL、告警策略或任何生产资源。
- OQ-005 仍 open；告警/观测闭环已完成，后续重点是 Dataform 生产链路、补跑和完整 ODS→ADS 运维观测闭环。

### 改动文件

- `scripts/alerting/README.md`
- `TODO.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #75 / OQ-005 alert checker reliability follow-up

### 已完成工作

- 修复 `oq005_alert_checker` DAG 返回码处理：`rc=0` 表示无异常成功，`rc=1` 表示 checker 查询/写日志失败并让 DAG failed，`rc=2` 表示发现业务告警但 DAG 成功；其他意外返回码一律 fail-closed。
- 将 DAG 调用 `check_alerts.py` 的生产 lookback 从 10 分钟放宽为 20 分钟，和 10 分钟调度形成重叠。
- `check_alerts.py` 新增 `--write-heartbeat`，成功查询后写入 `alert_checker_heartbeat` 日志，用于监控告警链自身存活。
- `setup_alerts.py` 新增 `oq005_alert_checker_heartbeat` log-based metric，以及 30 分钟无 heartbeat 的 absence alert policy。
- 修复 `setup_alerts.py` 里 Cloud Monitoring API 的 duration / condition enum / condition field 写法，避免真实 apply 创建策略时失败。
- README 同步 Composer DAG、20 分钟 lookback、heartbeat 和 dead-man's-switch 口径。
- TODO / OPEN_QUESTIONS / IMPLEMENTATION_STATUS 同步为“主告警链路已部署验收，checker liveness follow-up 待合并后部署验收”。

### 重要上下文

- 本次只改 PR 分支中的代码与文档，未同步 Composer bucket，未实际创建新增 heartbeat metric / absence policy。
- 合并后需要部署 `orchestration/composer/dags/oq005_alert_checker.py` 与 `scripts/alerting/check_alerts.py` 到 Composer bucket，并运行 `setup_alerts.py` 应用新增 heartbeat metric / absence policy。

### 改动文件

- `orchestration/composer/dags/oq005_alert_checker.py`
- `scripts/alerting/check_alerts.py`
- `scripts/alerting/setup_alerts.py`
- `scripts/alerting/README.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `/tmp/oq005-alerts-venv/bin/python -m py_compile scripts/alerting/check_alerts.py scripts/alerting/setup_alerts.py orchestration/composer/dags/oq005_alert_checker.py`
- `/tmp/oq005-alerts-venv/bin/python scripts/alerting/setup_alerts.py --dry-run`
- `/tmp/oq005-alerts-venv/bin/python scripts/alerting/check_alerts.py --lookback-minutes 20 --json`
- 临时 monkeypatch 验证：告警日志写入失败时不会写成功 heartbeat
- 临时构造验证：3 个 threshold policy 生成 `condition_threshold`，checker heartbeat 缺失策略生成 `condition_absent`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/observability/01_pipeline_status_views.sql`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- PR #75 合并后部署 checker DAG / checker script 到 Composer bucket，应用新增 heartbeat metric / absence policy，并做 heartbeat liveness smoke。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/alerting/check_alerts.py scripts/alerting/setup_alerts.py orchestration/composer/dags/oq005_alert_checker.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/observability/01_pipeline_status_views.sql`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 合并 PR #75 后继续 OQ-005 的 Dataform definitions、补跑和完整 ODS→ADS 运维观测闭环。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-010 / Strategy 1 sklearn native search implementation

### 已完成工作

- 在工作树 `/Users/luna/Desktop/git/quant-ashare-sklearn-native-search`、分支 `codex/implement-sklearn-native-search` 实现 `docs/prd/PRD_20260605_03_策略1Sklearn模型实验.md` 的 P0 代码路径。
- 新增 `configs/strategy1/sklearn_native_pvfq_n30_bw_h5_v0.yml`，固定当前最优交易参数 `pv_fin_quality + 30/5% + biweekly + 5d`、训练窗口 `2019-04-03` 至 `2023-12-31`、valid 2024、test/predict 2025，并定义 36 个 sklearn LogisticRegression 原生候选。
- 扩展 `train_predict.py`：candidate 级 `penalty` / `solver` / `C` / `l1_ratio` / `class_weight` / `max_iter` / `random_state`，记录 convergence warning、`n_iter_max`、`valid_signal_status`、valid RankIC ICIR、valid top-minus-bottom 等元数据。
- 扩展 `select_register_predict.py`：支持强选 candidate、valid-only ranking、Top5 metadata、training panel alias、native search 初始状态、candidate ranking artifact。
- 新增 `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`：一次 prepare matrix、36-task candidate fan-out、valid-only Top5、Top5 独立 select/predict/backtest/report/diagnosis、native acceptance 回写、comparison artifact 和 `18` QA。
- 新增 `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`，覆盖 search_id/source_run_id、candidate_count、task fan-out metadata、valid-only ranking、TopK 独立 run/backtest、report/diagnosis uploaded、accepted gates、BQML reference、test reuse/final holdout 等断言。
- 修复 `orchestrate_experiments.py` 的配置透传：candidate task 命令现在包含 `--config=...`，避免容器端回退默认 5 候选。
- 同步 Cloud Run 运行手册、runner README、TODO 和项目记忆。

### 重要上下文

- 这只是实现分支和 dry-run 验证，尚未部署 Cloud Run 镜像、未实跑 36 个候选、未写 ADS/GCS 正式产物。
- 当前真实执行建议在 PR review/merge 后进行：重新构建/部署包含新脚本的镜像，再运行 `orchestrate_sklearn_native_search.py`。
- 已知 `asia-east2` Cloud Run 配额提升到约 40 vCPU / 160Gi，第一轮 36 个 candidate task 可按 `1 CPU / 4Gi`、`--tasks=36` 并发尝试。
- 新 native baseline path 不要求 BQML parity passed，但必须保留 BQML reference 证据，并按 PRD 的 native acceptance gate 决定 accepted / rejected / needs_more_evidence。

### 改动文件

- `configs/strategy1/sklearn_native_pvfq_n30_bw_h5_v0.yml`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `scripts/strategy1_cloudrun/select_register_predict.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`
- `sql/ml/strategy1/README.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py scripts/strategy1_cloudrun/select_register_predict.py scripts/strategy1_cloudrun/train_predict.py scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_sklearn_native_search ... --candidate-parallelism 0 --top-k-backtest 5 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments ... --train-mode task_fanout --candidate-parallelism 0 --dry-run`
- 配置校验：36 个 candidate_id 全部唯一，manifest 只含 1 个 search experiment。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`
- `git diff --check`

### 阻塞项

- 无代码阻塞；真实 36 候选尚未执行。

### 下一步建议

- 创建 PR 并 review。
- 合并后构建/部署 Cloud Run 镜像到 `strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`。
- 执行真实 sklearn native search：36 候选并发训练、Top5 完整回测、`18` QA，通过 comparison artifact 决定是否接受 `cloud_run_sklearn_native_baseline_v1`。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-010 / Strategy 1 sklearn native model experiment PRD

### 已完成工作

- 在独立工作树 `/Users/luna/Desktop/git/quant-ashare-sklearn-native-prd` 和分支 `codex/prd-sklearn-native-experiment` 新增 `docs/prd/PRD_20260605_03_策略1Sklearn模型实验.md`。
- PRD 固定当前交易口径 `pv_fin_quality + 30/5% + biweekly + 5d`，避免把模型实验和交易参数变化混在一起。
- PRD 定义第一轮 36 个 LogisticRegression sklearn 原生候选：无正则、L2、ElasticNet，覆盖 `C`、`class_weight`、`l1_ratio` 和 solver 语义。
- PRD 定义搜索流程：一次 `prepare_matrix`，candidate task fan-out 并发训练全部候选，valid-only 选 Top 5，再对 Top 5 跑完整预测、组合、回测、报告、诊断和 QA。
- PRD 定义 sklearn native acceptance gate：valid/test RankIC、2025 test-year 收益和相对中证1000超额、Sharpe、max drawdown、成本、`10/12/16/17/18` QA 和 Python ledger vs SQL ledger 等价边界。
- 同步 `TODO.md`、`PROJECT_CONTEXT.md`、`OPEN_QUESTIONS.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要。

### 重要上下文

- 本 PRD 是 Cloud Run sklearn backend 在 BQML parity 未通过后的后续方案；它不删除既有 BQML parity gate，只新增 native baseline path。
- BQML baseline 继续作为 reference / fallback；native baseline 是否接受由后续 36 候选 + Top 5 回测结果决定。
- 本次没有实现代码，没有部署 Cloud Run Job，没有执行 BigQuery，没有生成或覆盖 ADS / GCS 产物。

### 改动文件

- `docs/prd/PRD_20260605_03_策略1Sklearn模型实验.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review / 合并本 PRD。
- 合并后实现 `configs/strategy1/sklearn_native_pvfq_n30_bw_h5_v0.yml`、candidate search orchestrator、Top 5 backtest flow 和 `18_qa_sklearn_native_search_outputs.sql`。
- 再跑第一轮 36 个 LogisticRegression 候选并产出 comparison report。

### 已更新记忆文件

- `TODO.md`
- `PROJECT_CONTEXT.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01
相关 issue/PR: Strategy 1 Cloud Run task fan-out formal validation

### 已完成工作

- 将 `strategy1-prepare-matrix-job` 资源从 `4 CPU / 16Gi` 提升到 `8 CPU / 32Gi`，用于解决全量 2019-2025 训练面板 prepare 阶段 16Gi OOM 风险。
- 为正式验收创建独立 run/backtest：`s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01` / `bt_s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01`，不覆盖既有 BQML baseline。
- 重建该 run 的训练面板，行数 3,055,781（train 1,999,065 / valid 476,346 / test 580,370），注意样本 `p_feature_version` 仍使用 DWS 现有 `strategy1_pv_v0_20260601`，`p_feature_set_id` 使用 `strategy1_pv_fin_quality_v0_20260603`。
- 执行完整 Cloud Run task fan-out 链路：`cloudrun_prepare_matrix`、5 个 candidate task、`cloudrun_select_register_predict`、`cloudrun_backtest_report` 全部 succeeded。
- `cloudrun_backtest_report` 内部跑通 `05_build_candidates`、`06_build_portfolio_targets`、`07_build_order_plan`、Python `ledger_exec_v1`、`09_build_metrics_and_report_inputs`、报告上传、`10_qa_runner_outputs.sql`、诊断脚本和 `12_qa_model_diagnosis_outputs.sql`。

### 重要上下文

- `prepare_matrix` execution：`strategy1-prepare-matrix-job-q4zd5`，Cloud Run 侧耗时约 4m10s。
- candidate fan-out execution：`strategy1-train-candidate-fanout-job-fpk9d`，5 个 task 全部 succeeded。
- select/register/predict execution：`strategy1-select-register-predict-job-d5kj2`。
- backtest/report execution：`strategy1-backtest-report-job-4shcl`。
- selected sklearn candidate 为 `elastic_c_1_l1_0_5`，`score_orientation=reverse_probability`。
- 报告 URI：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01/backtest_id=bt_s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01`。
- 模型诊断 URI：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01/backtest_id=bt_s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01/model_diagnosis`。

### 测试 / 验证

- orchestrator 全链路返回 `status=succeeded`、`failure_count=0`。
- `10_qa_runner_outputs.sql` 和 `12_qa_model_diagnosis_outputs.sql` 在 `cloudrun_backtest_report` 内部通过。
- `16_qa_cloudrun_runner_outputs.sql` 在 `p_require_model_quality_parity_passed=FALSE` 的 smoke/evidence 模式通过。
- `17_qa_cloudrun_orchestrator_status.sql` 在 `p_require_task_fanout=TRUE` 下通过。
- 正式 `16_qa_cloudrun_runner_outputs.sql` 在默认 `p_require_model_quality_parity_passed=TRUE` 下未通过，失败点为 `QA-CR-4`。

### 结果摘要

- 回测 total_return `46.29%`、annual_return `21.72%`、Sharpe `1.111`、max_drawdown `-13.94%`。
- benchmark 为 `000852.SH`，excess_return `17.28%`，information_ratio `0.237`。
- prediction 行数 1,056,716，日期范围 `2024-01-02` 至 `2025-12-31`，score NULL 行数 0。
- diagnosis 结论 `usable_signal`，confidence `low`；valid RankIC mean `0.06665`，test RankIC mean `0.03359`。
- sklearn vs BQML parity 未通过：sklearn valid RankIC `0.06665`，BQML reference `0.09676`，delta `-0.03011`；`model_quality_status=model_quality_not_equivalent`。

### 阻塞项

- 无执行链路阻塞；正式替代 BQML 的模型质量门槛未过。

### 下一步建议

- 不要把本 run 直接标记为 BQML 替代 baseline；它目前只能证明 Cloud Run task fan-out 执行链路可用。
- 下一步应先做 sklearn parity 提升（候选网格、预处理、模型族或参数）或由 owner 明确接受新的 Cloud Run baseline。
- 另需补 Python ledger vs SQL ledger 完整等价验收，再考虑让 Cloud Run runner 成为默认执行路径。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: s1_cloudrun_taskfanout_smoke_20260605_03
相关 issue/PR: Strategy 1 Cloud Run task fan-out smoke / fix branch `codex/fix-task-fanout-force-replace`

### 已完成工作

- 构建并部署 task fan-out 修复镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner@sha256:8cc8470014cb3b54272d4c7f47afb396d91cf7b97967f0c3ffab947f7432c38a`。
- 更新 Cloud Run Jobs：`strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`。
- 执行低成本 task fan-out smoke：2023 train、2024H1 valid、2024H2 test/predict，5 个默认候选全部用 candidate task 并发训练。
- 修复 smoke 暴露的问题：`prepare_matrix` 不支持 `--force-replace`；`10` QA split 边界写死；`12` QA-DIAG-6 使用 DWS 固定 split 导致短窗口 test 误判为 0 天。

### 重要上下文

- 当前 job CPU：prepare/select/backtest 为 `4 CPU / 16Gi`；candidate task 为 `1 CPU / 4Gi`。
- 当前区域配额限制为 `asia-east2` 约 `20 vCPU / 40Gi`，所以 candidate job 设置 `parallelism=10`；本次默认 5 候选 smoke 实际并发为 5。
- 全量 2019-2025 训练面板的 `prepare_matrix` 曾在 `16Gi` 下 OOM；本次 smoke 改用短窗口验证链路。后续正式全量 matrix 可能需要提高 prepare job 内存或做分片/流式构建。

### 改动文件

- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/backtest_report.py`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/orchestrate_experiments.py scripts/strategy1_cloudrun/backtest_report.py`
- `git diff --check`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`
- Cloud Run smoke 状态表 4 步 succeeded：`cloudrun_prepare_matrix`、`cloudrun_train_candidate_fanout`、`cloudrun_select_register_predict`、`cloudrun_backtest_report`
- `10_qa_runner_outputs.sql`、`12_qa_model_diagnosis_outputs.sql`、`16_qa_cloudrun_runner_outputs.sql`、`17_qa_cloudrun_orchestrator_status.sql` 全部通过

### 阻塞项

- 无执行链路阻塞；正式替代 BQML 仍需 sklearn parity passed 或 owner 明确采纳新 Cloud Run baseline。

### 下一步建议

- 提 PR review 并合并本次 smoke 修复。
- 后续若要 35/100 候选并发，需要先决定是提升 Cloud Run 区域配额，还是降低 candidate task 内存并验证 OOM 风险。
- 针对全量窗口 `prepare_matrix` 的 16Gi OOM，单独做 prepare 阶段内存优化或提高 job 规格。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: Strategy 1 Cloud Run lightweight task fan-out implementation

### 已完成工作

- 在工作树 `/Users/luna/Desktop/git/quant-ashare-cloudrun-task-fanout-impl`、分支 `codex/cloudrun-task-fanout` 实现 task fan-out P0。
- 新增 `prepare_matrix.py`，集中读取 `ads_ml_training_panel_daily`，按 train split fit 预处理器，输出已预处理 train/valid/predict parquet、feature schema、preprocess stats、work units、matrix manifest 和 BigQuery job audit。
- 新增 `train_candidate_task.py`，按 `CLOUD_RUN_TASK_INDEX + TASK_INDEX_OFFSET` 训练单个 candidate，输出 candidate model、metrics、training log 和 task status。
- 新增 `select_register_predict.py`，汇总 candidate artifact，校验 matrix/hash，一致通过后选型、写 selected model artifact、registry 和 prediction。
- `orchestrate_experiments.py` 新增 `--train-mode task_fanout` / `--candidate-parallelism`；owner 不限流时单批 `--tasks=N` 全并发，显式限流时按批次执行。
- `16_qa_cloudrun_runner_outputs.sql` 与 `17_qa_cloudrun_orchestrator_status.sql` 增加 task fan-out 模式断言；运行手册和 runner README 已同步。

### 重要上下文

- 该条为 PR #64 合并前 dry-run 阶段交接；真实 task fan-out smoke 已在后续 2026-06-05 交接完成。
- 当前默认 candidate grid 仍是 5 个；未擅自扩到 35 个。扩网格和真实成本实验需要 owner 再确认。
- `prepare_matrix` 依赖既有 `ads_ml_training_panel_daily`，不会自动执行 `01_build_training_panel.sql`；真实执行前必须先确认对应 `run_id` 的训练面板已存在。
- 本机默认 Python 3.9 起初缺 `joblib/scikit-learn`；已按 `scripts/strategy1/requirements.txt` 用 `pip install --user` 补齐本地 dry-run 依赖。

### 改动文件

- `configs/strategy1/cloudrun_runner_default.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1_cloudrun/bq_io.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/prepare_matrix.py`
- `scripts/strategy1_cloudrun/select_register_predict.py`
- `scripts/strategy1_cloudrun/task_fanout.py`
- `scripts/strategy1_cloudrun/train_candidate_task.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/*.py`
- `python3 -m scripts.strategy1_cloudrun.prepare_matrix --project data-aquarium --region asia-east2 --experiment-id oq010_a0_n5_w20 --candidate-parallelism 0 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.train_candidate_task --project data-aquarium --region asia-east2 --matrix-uri gs://dummy/matrix --matrix-local-dir <tmp> --task-index 0 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.select_register_predict --project data-aquarium --region asia-east2 --experiment-id oq010_a0_n5_w20 --matrix-uri gs://dummy/matrix --matrix-local-dir <tmp> --dry-run`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --project data-aquarium --region asia-east2 --manifest configs/strategy1/oq010_experiments_v0.json --config configs/strategy1/cloudrun_runner_default.yml --experiment-id oq010_a0_n5_w20 --train-mode task_fanout --candidate-parallelism 0 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --project data-aquarium --region asia-east2 --manifest configs/strategy1/oq010_experiments_v0.json --config configs/strategy1/cloudrun_runner_default.yml --experiment-id oq010_a0_n5_w20 --train-mode task_fanout --candidate-parallelism 2 --dry-run`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`
- `gcloud run jobs execute --help | rg -n -- '--tasks|--update-env-vars|--args'`
- `git diff --check`

### 阻塞项

- 无代码阻塞；该历史交接的部署与 5 候选 smoke 已在后续 2026-06-05 完成。

### 下一步建议

- 提 PR review。
- PR 合并后部署 `strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`。
- 先用 5 个默认候选跑低成本 task fan-out smoke，通过 `16`/`17` task fan-out QA 后，再讨论是否扩到 35 候选并做 sklearn parity 实验。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-010 / Strategy 1 Cloud Run lightweight task fan-out PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260605_02_策略1CloudRun轻量Task并发.md`。
- PRD 定义 `prepare_matrix -> train_candidate_fanout --tasks=N --candidate-parallelism=M -> select_register_predict -> backtest_report` 链路。
- 固化 GCS frozen matrix 契约、work units manifest、`CLOUD_RUN_TASK_INDEX` 分片映射、小规格 candidate task、owner 显式限流、reducer 选型、QA、状态表与幂等规则。
- 跟进 PR #63 review comment：明确 frozen features 为 `prepare_matrix` 输出的已预处理矩阵，candidate task 不重新预处理；补 BigQuery job labels / audit 机制来验证训练面板只在 `prepare_matrix` 读取；补 candidate task 不读 `predict_features` / `predict_index`。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和本交接文件。

### 重要上下文

- 工作树：`/Users/luna/Desktop/git/quant-ashare-cloudrun-task-fanout-prd`。
- 分支：`codex/prd-cloudrun-task-fanout`。
- 本次只写文档；未实现代码、未部署 Cloud Run Job、未执行 BigQuery、未生成或覆盖 GCS / ADS 产物。
- 该 PRD 是 `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md` 的训练侧并发补充，不替代 Cloud Run runner / orchestrator 已有 PRD。

### 改动文件

- `docs/prd/PRD_20260605_02_策略1CloudRun轻量Task并发.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- review / merge 本 PRD。
- 合并后按阶段实现：Phase 1 先做 dry-run / manifest 展开，Phase 2 做 `prepare_matrix` frozen matrix，Phase 3 做 Cloud Run task fan-out，Phase 4 做 reducer / prediction / QA，最后做 35/100 work units smoke。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #61 / OQ-005 Phase 2.0 BigQuery SQL 兼容调度路径

### 已完成工作

- 跟进 PR #61 review comment。
- `orchestration/composer/dags/ashare_daily_pipeline_v0.py` 移除模块顶层 `Variable.get()`：project/region/location 改为 operator 模板参数，callback URL / BigQuery client 改为运行期 helper 读取。
- `pipeline_dry_run` / `dry_run` 支持单次 DAG run 覆盖 Airflow Variable；DAG 通过 branch 在运行期选择 `ingest_current_scope_dry_run` 或 `ingest_current_scope_write`，避免全局翻转变量才能做真实采集。
- `sql/qa/09_ods_daily_partition_readiness.sql` 新增 `pipeline_dry_run` 参数；`require_business_partition` 为空时由 dry-run 运行期口径推导，dry-run 默认不要求精确业务日分区，真实写入默认要求精确业务日/交易日分区。
- 删除冗余 `ods_daily_partition_readiness >> finish` 依赖。
- 抽出 `_build_qa_chain(group_id)`，复用 `qa` 与 `qa_only` 的 5 个 QA task 定义。
- 同步 `orchestration/composer/README.md` / `orchestration/README.md` 的手工运行参数说明。

### 重要上下文

- 本次只改仓库文件；未部署 Composer、未触发 DAG、未执行生产 BigQuery 转换、未写 GCS。
- PR #61 仍是 OQ-005 Phase 2.0 代码入口；OQ-005 仍保持 open，后续还需要 Composer 部署 smoke、生产验收、Dataform 生产链路、增量影响窗口、告警和补跑闭环。

### 改动文件

- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `sql/qa/09_ods_daily_partition_readiness.sql`
- `orchestration/composer/README.md`
- `orchestration/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=pipeline_dry_run:STRING:true --parameter=require_business_partition:STRING: < sql/qa/09_ods_daily_partition_readiness.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=pipeline_dry_run:STRING:false --parameter=require_business_partition:STRING: < sql/qa/09_ods_daily_partition_readiness.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/meta/01_create_meta_tables.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/meta/04_ods_field_unit_map.sql`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 推送 PR #61 follow-up commit 并在 PR comment 回复验证结果。
- 部署到 Composer 后先做 `skip_ingestion=true` smoke，再做 `warehouse_mode=qa_only` 只读 QA 和 `warehouse_mode=full_rebuild_compat` 维护链路 smoke。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-005 / Phase 2.0 BigQuery SQL 兼容调度路径

### 已完成工作

- 在新工作树 `/private/tmp/quant-ashare-oq005-scheduler-phase2`、分支 `codex/oq005-scheduler-phase2` 开始实现已合并的 `docs/prd/PRD_20260605_01_OQ005剩余调度链路.md`。
- `orchestration/composer/dags/ashare_daily_pipeline_v0.py` 新增 `pipeline_run` / `pipeline_task_status` 状态回写、task success/failure callback、DAG failed callback、`warehouse_mode` 分支、legacy `ashare_enable_full_refresh=true` 到 `full_rebuild_compat` 的记录映射、`skip_ingestion` 分支、`qa_only` 只读 QA 分支和 ADS 契约手工初始化分支。
- `sql/meta/01_create_meta_tables.sql` 扩展 `pipeline_run` / `pipeline_task_status` 字段，新增 `date_from`、`date_to`、`run_label`、`warehouse_mode`、`transform_backend`、`updated_at` 和 Airflow / BigQuery / Cloud Run URL 字段。
- 将 OQ-006 单位映射脚本从 `sql/meta/01_ods_field_unit_map.sql` 重命名为 `sql/meta/04_ods_field_unit_map.sql`，并同步 DAG、SQL README 和 PRD 引用。
- 同步 `orchestration/composer/README.md`、`orchestration/README.md`、`sql/README.md` 和 OQ-005 PRD 中的 Phase 2.0 口径。
- 新增 `DECISION-20260605-01`，记录 `warehouse_mode` 显式区分每日、只读 QA、兼容全量转换和 ADS 契约初始化。

### 重要上下文

- 本次只改仓库文件；未部署 Composer、未触发 DAG、未执行生产 BigQuery 转换、未写 GCS。
- Phase 2.0 现有 CTAS 转换只允许 `warehouse_mode=full_rebuild` 或 `warehouse_mode=full_rebuild_compat` 手工进入；默认 `daily_current` 只做采集、ODS readiness 和状态回写。
- `warehouse_mode=qa_only` 只跑 ODS readiness 后的 `01-05` QA，不改生产表。
- `enable_ads_contract_init=true` 才会执行 `sql/ads/01_ads_strategy1_tables.sql`。

### 改动文件

- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `sql/meta/01_create_meta_tables.sql`
- `sql/meta/04_ods_field_unit_map.sql`
- `orchestration/composer/README.md`
- `orchestration/README.md`
- `sql/README.md`
- `docs/prd/PRD_20260605_01_OQ005剩余调度链路.md`
- `docs/prd/PRD_20260602_01_OQ006接口单位换算口径.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/meta/01_create_meta_tables.sql`
- `git diff --check`

### 阻塞项

- 未阻塞；下一步需要提 PR / review 后部署到 Composer 做 smoke。

### 下一步建议

- 提 PR 并 review Phase 2.0 DAG 变更。
- 部署后先用 `skip_ingestion=true` 做调度 smoke，确认不创建 Cloud Run execution 且 ODS readiness / 状态表回写正常。
- 再用 `warehouse_mode=qa_only` 验证只读 QA 不改生产表。
- 最后用 `warehouse_mode=full_rebuild_compat` 手工 smoke BigQuery SQL 兼容转换链路，确认 metadata / QA / `pipeline_run` terminal 状态完整。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-005 / 剩余 ODS→ADS 调度链路 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260605_01_OQ005剩余调度链路.md`。
- PRD 聚焦当前 `ashare-ingest-current-scope` 生产采集之后的剩余链路，覆盖 ODS gate、ODS→DIM/DWD/DWS/ADS 转换、ADS 契约隔离、metadata、QA、pipeline 状态、告警、补跑、Dataform / BigQuery SQL 双路径、策略 runner/report 可选分支和 OQ-005 关闭标准。
- PR #59 review follow-up：澄清 Phase 2.0/2.1 使用现有 CTAS 时是 `full_rebuild_compat` / maintenance 路径，真正默认每日不扫 2019+ 全史从 Phase 2.2 增量化开始；修正 ADS 脚本现状为已使用 `CREATE TABLE IF NOT EXISTS`；补充 `sql/meta/` 编号整理要求；明确字段说明迁移期生产来源为 `sql/metadata/01,02`。
- 同步 `TODO.md`、`PROJECT_CONTEXT.md`、`OPEN_QUESTIONS.md`、`IMPLEMENTATION_STATUS.md`、`ARCHITECTURE_MEMORY.md` 和当前交接摘要。

### 重要上下文

- 工作树：`/private/tmp/quant-ashare-oq005-ods-ads-scheduler-prd`。
- 分支：`codex/oq005-ods-ads-scheduler-prd`。
- 本次只写 PRD 和必要状态记录，未实现代码、未部署 Composer/Dataform/Cloud Run、未执行 BigQuery。
- OQ-005 继续保持 open，下一步按 PRD Phase 2.0/2.1/2.2/2.3 实现 BigQuery SQL 兼容路径闭环、Dataform definitions、增量影响窗口、策略 runner/report 分支和告警/补跑/状态闭环。

### 改动文件

- `docs/prd/PRD_20260605_01_OQ005剩余调度链路.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- review/merge 本 PRD。
- 合并后按 Phase 2.0 先补 `ashare_daily_pipeline_v0` 的 pipeline status、BigQuery SQL 兼容路径和 ADS 契约初始化隔离。
- Phase 2.1 再接 Dataform definitions 和 workflow invocation。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01 / bt_ledger_resume_smoke_20260604_01
相关 issue/PR: OQ-010 / Ledger v1 P2 state resume implementation

### 已完成工作

- 实现 Ledger v1 state resume。
- `08_run_backtest.sql` 新增 `p_initial_state_mode='resume_from_backtest'`、`p_parent_backtest_id`、`p_state_as_of_date` 和 `p_resume_policy_id`，从父回测恢复现金、实际持仓、active target 和 pending sell。
- resume 前置校验 fail-fast：父 summary 必须存在且 `ledger_version='ledger_exec_v1'`，父 NAV state 必须唯一且含 cash/net value/run_id，父持仓必须唯一且非负，父 NAV 必须能与现金+持仓市值对齐，`p_predict_start` 必须等于 state date 后下一 SSE 开市日。
- `09_build_metrics_and_report_inputs.sql` 在 summary `metrics_json` 写入 `initial_state_mode`、`parent_backtest_id`、`state_as_of_date`、`resume_policy_id` 和 `is_resumed_backtest`。
- `10_qa_runner_outputs.sql` 新增 `QA-RESUME-1..6`；biweekly resume 强制显式传 `p_rebalance_anchor_start` 原实验锚点，首个 resume 日 `daily_return` 必须非空。
- 新增 `sql/ml/strategy1/15_qa_ledger_resume_consistency.sql`，用于后续 full fresh vs resume segment 一致性验收，并比较 `daily_return`。
- `sql/ml/strategy1/README.md` 已同步 resume 参数、运行顺序和 consistency QA 说明。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`KNOWN_CONSTRAINTS.md` 和当前交接摘要。

### 重要上下文

- 当前实现分支：`codex/ledger-state-resume`，工作树 `/Users/luna/Desktop/git/quant-ashare-ledger-resume`。
- 基于 `origin/main` commit `602baea`，该 commit 已包含 Ledger v1 P0。
- smoke 父回测：`bt_ledger_v1_p0_smoke_20260604_01`，`state_as_of_date=2024-02-29`。
- smoke resume 回测：`bt_ledger_resume_smoke_20260604_01`，窗口 `2024-03-01` 至 `2024-03-15`。
- smoke 首日现金恢复为父状态现金 `135.9692847801162`，首日 `daily_return=-0.0031135`，NAV 11 行无 NULL daily_return，持仓 330 行，成交 36 行；本地报告使用 `--skip-gcs-upload`。
- 完整 consistency QA 需要先具备 full fresh extended backtest 与 resume segment backtest；本次只新增 QA 脚本并完成 dry-run。

### 改动文件

- `sql/ml/strategy1/08_run_backtest.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/15_qa_ledger_resume_consistency.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/08_run_backtest.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/15_qa_ledger_resume_consistency.sql`
- BigQuery smoke：PR #54 review follow-up 后，`08` resume、`09` resume、本地 `render_report.py --skip-gcs-upload`、`10_qa_runner_outputs.sql` 全部通过。
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 提 PR review 本次 Ledger v1 P2 resume 实现。
- 合并后补 Ledger v1 P1 fixed-model extended backtest 至 `2026-04-30`。
- 有 full fresh extended 与 resume segment 后，执行 `15_qa_ledger_resume_consistency.sql` 做一致性验收。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01
相关 issue/PR: OQ-010 / factor attribution implementation

### 已完成工作

- 实现策略 1 因子贡献度分析 P0。
- 新增 `scripts/strategy1/attribute_factor_contribution.py`，只读 selected BQML model、冻结训练面板、预测池、候选池、回测持仓和 summary，不重新训练、不做消融实验。
- 新增 `sql/ml/strategy1/14_qa_factor_attribution_outputs.sql`，断言状态、版本、manifest、模型特征覆盖、因子组映射、valid/test RankIC、score contribution 分组、持仓暴露覆盖、路径语义、相关性摘要、限制说明和禁止消融字段。
- `scripts/strategy1/render_report.py` 已接入可选“因子贡献度摘要”：第 13 步回写 completed 后，主报告展示 factor attribution 路径、top 因子组和 top score factors。
- `sql/ml/strategy1/README.md` 已补 13/14 执行命令、参数和 artifact 契约。
- `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要已同步。

### 重要上下文

- 正式 baseline local-only smoke 已成功生成 `reports/strategy1/ml_pv_clf_v0/run_id=s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01/backtest_id=bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01/factor_attribution/`。
- 本次覆盖 selected model 55 个非截距特征、13 个因子组；`factor_attribution_upload_status=skipped`，`local_factor_attribution_path` 已回写 ADS，`factor_attribution_uri` 为空。
- 计算过程中修复了 BigQuery 动态 JSON path 限制：脚本使用 `PARSE_JSON(feature_values_json, wide_number_mode => 'round')[feature]` 取动态特征值。
- 本 PR 只提交代码/SQL/文档/记忆；生成的 `reports/` 本地产物不纳入 git。

### 改动文件

- `scripts/strategy1/attribute_factor_contribution.py`
- `sql/ml/strategy1/14_qa_factor_attribution_outputs.sql`
- `scripts/strategy1/render_report.py`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/attribute_factor_contribution.py scripts/strategy1/render_report.py scripts/strategy1/diagnose_model_quality.py`
- `python3 scripts/strategy1/attribute_factor_contribution.py --help`
- `git diff --check`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/14_qa_factor_attribution_outputs.sql`
- `python3 scripts/strategy1/attribute_factor_contribution.py --project data-aquarium --run-id s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01 --backtest-id bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01 --artifact-base-uri gs://ashare-artifacts/reports/strategy1 --local-mirror-root reports/strategy1 --skip-gcs-upload`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/14_qa_factor_attribution_outputs.sql`，全部 ASSERT 通过。

### 阻塞项

- 无。

### 下一步建议

- 提 PR review 本次因子贡献度实现。
- 合并后按 Ledger v1 PRD 实现 P0 交易语义 A/B，再做 P1 fixed-model 连续扩展回测到 `2026-04-30` 和 P2 ledger state resume。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #69 / OQ-010 / Strategy 1 sklearn native model experiment PRD

### 已完成工作

- 按 PR #69 review comment 修订 `docs/prd/PRD_20260605_03_策略1Sklearn模型实验.md`。
- 将训练窗口从自然年简写改为 `2019-04-03` 至 `2023-12-31`，确保和 BQML baseline / livepool 训练起点一致。
- 新增 `valid_signal_status` 规则：accepted 候选必须为 `stable`；valid 弱但 test 过门只能标记 `needs_more_evidence`。
- 新增跨模型族 test 复用控制：记录 `test_reuse_wave_no` / `test_reuse_approval_ref`，第二波及以后需 owner 批准，超过 3 个波次后必须新增最终 holdout 证据。
- 同步输出报告、ADS/GCS JSON、QA、manifest、Phase 4 和风险表约束。
- 同步 `PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`TODO.md` 和当前交接摘要。

### 重要上下文

- 本次仍是纯文档/记忆修订，未实现代码、未部署 Cloud Run Job、未执行 BigQuery、未生成或覆盖 ADS / GCS 产物。
- `OPEN_QUESTIONS.md` 的 OQ-010 仍保持原 open 状态；关键修订已在 PROJECT_CONTEXT / STATUS / TODO / handoff 记录。

### 改动文件

- `docs/prd/PRD_20260605_03_策略1Sklearn模型实验.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review / 合并 PR #69。
- 合并后实现 sklearn native search manifest、candidate metrics、Top 5 full backtest flow 和 `18_qa_sklearn_native_search_outputs.sql`。

### 已更新记忆文件

- `PROJECT_CONTEXT.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-005 Phase 2.2 / PR #65 post-merge hotfix / branch `codex/fix-windowed-refresh-equivalence`

### 已完成工作

- 在独立工作树 `/private/tmp/quant-ashare-oq005-window-prod` 从最新 `origin/main` 创建热修复分支 `codex/fix-windowed-refresh-equivalence`。
- 运行真实 scratch full-vs-window 等价 QA，确认 PR #65 合并后生产部署前存在两个阻断：QA runner 复制 `_full` 表时缺少分区过滤；估值特征读取窗口不足导致 `turnover_rate_zscore_60d` 漂移。
- 修复 `scripts/qa/run_windowed_refresh_equivalence.py`：复制 canonical `_full` 到 `_window` seed 时按 `trade_date BETWEEN build_start_date AND full_end_date` 过滤，兼容 `require_partition_filter=true`。
- 修复 `sql/incremental/01_refresh_stock_dwd_dws_window.sql`：估值特征读取边界按每只股票写入窗口首日前的实际 60 条估值观测推导，价格特征仍读取 60 个 SSE 交易日，标签/宽表/样本写入仍向前回补 20 个交易日。
- 修复 `scripts/qa/run_windowed_refresh_equivalence.py`：真实运行前用生产 DWD 估值表校验 `build_start_date` 足够早，避免 full/window shadow 被同样截断后假通过。
- 跟进 PR #68 comment：不采用固定 180 个交易日作为最终方案，改为 per-stock 实际观测边界，并用 QA guard 覆盖早期窗口假通过风险。
- 同步 `sql/README.md`、`TODO.md`、OQ-005 架构记忆、约束、状态和开放问题。

### 重要上下文

- 本次真实 QA 只写 scratch dataset `ashare_qa_windowed_equivalence` 的 `_full` / `_window` shadow 表，不写生产 DWD/DWS/ADS。
- 首次真实 QA 的 drift 集中在 `dws_stock_feature_valuation_daily.turnover_rate_zscore_60d` 和继承该字段的 `dws_stock_feature_daily_v0`，原因是 `daily_basic` 对部分股票不是每日完整观测，60 条观测窗口可能跨越超过 60 个交易日。
- 修复后 full-vs-window 等价 QA 对 9 张目标表 mismatch 均为 0；guard 结果为 `required_build_start_date<=2025-01-23`、`sec_code_count=5407`、`less_than_60_obs=32`。
- 仍未部署 Composer，未执行生产 DML，未写生产 BigQuery/GCS/ADS 产物。

### 改动文件

- `scripts/qa/run_windowed_refresh_equivalence.py`
- `sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `sql/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/qa/run_windowed_refresh_equivalence.py`
- `python3 scripts/qa/run_windowed_refresh_equivalence.py --dry-run`
- `bq query --dry_run`：窗口 SQL `backfill` 参数。
- `bq query --dry_run`：窗口 SQL `daily_current` 参数。
- 真实 scratch 等价 QA：9 张目标表 full-vs-window mismatch 均为 0。

### 阻塞项

- 无代码阻塞；生产部署和生产 DML smoke 需等待本 hotfix 合并。

### 下一步建议

- 合并 hotfix PR。
- 合并后部署 Composer DAG 与 SQL 到 Composer bucket。
- 先跑 `skip_ingestion=true` + `warehouse_mode=backfill` 小窗口生产 DML smoke，再跑 `daily_current` scheduler smoke 和 `qa_only` 验收。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #65 / OQ-005 Phase 2.2 股票 DWD/DWS 窗口刷新

### 已完成工作

- 将分支 `codex/windowed-dwd-dws-refresh` rebase 到 `origin/main` 最新提交 `96861b5`。
- 跟进 PR #65 review comment：`sql/incremental/01_refresh_stock_dwd_dws_window.sql` 增加目标表存在性 ASSERT，并用 BigQuery transaction 包住 9 张 DWD/DWS 目标表的窗口 DELETE/INSERT。
- 新增 `scripts/qa/run_windowed_refresh_equivalence.py`，用于发布前/定期在 scratch 表中对比 canonical full SQL 与 window SQL 的窗口内逐列数值等价。
- 同步 `sql/README.md`、`TODO.md` 和 OQ-005 相关记忆，明确大区间 backfill 按年/季/月分块执行，窗口 SQL 与 canonical full SQL 双实现并存期间必须跑等价 QA。

### 重要上下文

- 本次只修改 PR #65 分支内容，未部署 Composer，未执行生产 DML，未写 BigQuery/GCS/ADS 产物。
- 等价 QA runner 默认 scratch dataset 为 `ashare_qa_windowed_equivalence`；真实执行会创建 `_full` / `_window` shadow 表，不应修改生产 DWD/DWS 表。
- `git stash pop` 后的冲突已解决；本次 rebase 前安全备份 stash 已删除，仓库里剩余的 `stash@{0}: autostash` 不是本次 PR #65 follow-up 备份。

### 改动文件

- `sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `scripts/qa/run_windowed_refresh_equivalence.py`
- `sql/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py scripts/qa/run_windowed_refresh_equivalence.py`
- `python3 scripts/qa/run_windowed_refresh_equivalence.py --dry-run`
- `bq query --dry_run`：窗口 SQL `backfill` / `daily_current` 参数各一次。
- `bq query --dry_run`：`sql/qa/10_windowed_stock_refresh_checks.sql` `backfill` / `daily_current` 参数各一次。
- `git diff --check --cached`

### 阻塞项

- 无。

### 下一步建议

- 提交并 force-with-lease 推送 rebase 后的 PR #65 分支。
- PR 合并后先做 `skip_ingestion=true` + `warehouse_mode=backfill` 小窗口 Composer smoke，再做 `daily_current` scheduler smoke 和 `qa_only` 验收。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-005 Phase 2.2 / 股票 DWD-DWS 窗口刷新

### 已完成工作

- 在工作树 `/private/tmp/quant-ashare-windowed-refresh`、分支 `codex/windowed-dwd-dws-refresh` 实现股票 DWD/DWS 窗口刷新。
- 新增 `sql/incremental/01_refresh_stock_dwd_dws_window.sql`，对 `dwd_stock_eod_price`、`dwd_stock_eod_valuation`、策略 1 universe/price/valuation/finance/label/feature/sample DWS 做参数化窗口 DELETE/INSERT。
- 新增 `sql/qa/10_windowed_stock_refresh_checks.sql`，覆盖窗口内主键唯一、生命周期、退市日、ODS daily 表示性、停牌语义和 trainable sample 基础断言。
- `orchestration/composer/dags/ashare_daily_pipeline_v0.py` 新增 `daily_current/backfill` 窗口分支：真实写入时刷新 DIM 小表、恢复 P0 metadata、执行窗口刷新和窗口 QA；`pipeline_dry_run=true` 不写表。
- 同步修复 Composer project/region/location 常量，避免 BigQuery operator `location` 使用未渲染 Jinja。
- `sql/meta/01_create_meta_tables.sql` 合并同表多列 `ADD COLUMN IF NOT EXISTS`，降低连续 table update 限流风险。
- 更新 `orchestration/README.md`、`orchestration/composer/README.md`、`sql/README.md`、`TODO.md` 和相关记忆。

### 重要上下文

- 本次未部署 Composer，未触发 DAG，未执行生产 BigQuery DML，未写 GCS/ADS/report 产物。
- 窗口脚本假设目标 DIM/DWD/DWS 表已由全量 CTAS 路径初始化；ADS runner/backtest/report 仍由策略 runner 独立写入。
- `full_rebuild` / `full_rebuild_compat` 保留原全量兼容链路；`qa_only` 保持只读；`enable_ads_contract_init=true` 仍是 ADS 契约初始化的唯一入口。
- 窗口标签回补是 20 个 SSE 交易日，价格特征读取回看是 60 个 SSE 交易日；后续 hotfix 已把估值特征读取边界改为按每只股票实际 60 条估值观测推导，以覆盖 `daily_basic` 缺口。

### 改动文件

- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `orchestration/composer/README.md`
- `orchestration/README.md`
- `sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `sql/qa/10_windowed_stock_refresh_checks.sql`
- `sql/meta/01_create_meta_tables.sql`
- `sql/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=date_from:STRING:2026-06-03 --parameter=date_to:STRING:2026-06-04 --parameter=warehouse_mode:STRING:backfill < sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=date_from:STRING: --parameter=date_to:STRING:2026-06-04 --parameter=warehouse_mode:STRING:daily_current < sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=date_from:STRING:2026-06-03 --parameter=date_to:STRING:2026-06-04 --parameter=warehouse_mode:STRING:backfill < sql/qa/10_windowed_stock_refresh_checks.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=date_from:STRING: --parameter=date_to:STRING:2026-06-04 --parameter=warehouse_mode:STRING:daily_current < sql/qa/10_windowed_stock_refresh_checks.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/meta/01_create_meta_tables.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/metadata/01_p0_table_column_descriptions.sql`

### 阻塞项

- 无代码阻塞；生产前仍需部署 Composer 并做 `skip_ingestion=true` + `warehouse_mode=backfill` 窗口 smoke、`daily_current` scheduler smoke 和 `qa_only` 验收。

### 下一步建议

- 运行 `git diff --check` 后提交 PR。
- PR 合并后同步 DAG 与 `sql/` 到 Composer bucket。
- 先用 `skip_ingestion=true`、`pipeline_dry_run=false`、`warehouse_mode=backfill`、小日期窗口做生产 DML smoke，再恢复/观察 `daily_current` scheduler。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: s1_cloudrun_sklearn_smoke_20260604_02 / bt_s1_cloudrun_sklearn_smoke_20260604_02
相关 issue/PR: OQ-010 / Strategy 1 Cloud Run real smoke

### 已完成工作

- 在独立工作树 `/Users/luna/Desktop/git/quant-ashare-cloudrun-smoke`、分支 `codex/cloudrun-smoke` 上完成策略 1 Cloud Run 真实 smoke 收尾。
- 修复 `orchestrate_experiments.py` 的 `gcloud run jobs execute --args`，确保通过 orchestrator 启动 Cloud Run Job 时包含 `python -m scripts.strategy1_cloudrun.train_predict` / `backtest_report` module。
- 修复 `cloudbuild.strategy1-cloudrun.yaml` 本地 build 时 `$SHORT_SHA` 为空的问题，改为显式 `_TAG` substitution，并同步运行手册 build/deploy 命令。
- 优化 Cloud Run 训练内存：`feature_column_list` 兼容 BigQuery Storage / pandas array-like `.tolist()`；特征矩阵改为预分配 `float32`；展开特征后丢弃 raw JSON 列。
- 将 sklearn vs BQML parity 未通过从 fail-fast 改为记录证据：未通过时仍写 selected registry / prediction / artifact，但必须标记 `model_quality_status=model_quality_not_equivalent`，正式 baseline QA 默认仍要求 parity passed。
- 放宽 score orientation QA 容差到 `1e-6`，覆盖 Python / BigQuery float round-trip 的 `~3e-8` 误差。
- 给 Cloud Run 容器安装 `fonts-noto-cjk`，并在 `render_report.py` 扩展 Noto CJK 字体候选，消除中文报告图表 glyph missing 警告。
- 补充运行手册中的 Cloud Run runtime service account IAM、16Gi/4CPU/`--max-retries=0` 和 smoke / 正式 parity QA 区分。

### 重要上下文

- 使用 Artifact Registry repo `quant-ashare` 和镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner@sha256:6564434f9f216aec6c86cae3923bc44450c3ca26ead14a248b05ca77087d8ead`。
- Cloud Run Jobs：`strategy1-train-predict-job`、`strategy1-backtest-report-job`，均配置 16Gi/4CPU/`--max-retries=0`。
- runtime service account：`241358486859-compute@developer.gserviceaccount.com`，已补 `ashare_ads` dataset WRITER 权限。
- smoke experiment：`cloudrun_smoke_pvfq_n30_bw_h5`，对应正式 BQML reference run `s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01`。
- train/predict execution：`strategy1-train-predict-job-s5725`，prediction 1,056,716 行，selected candidate `elastic_c_1_l1_0_5`，score orientation `reverse_probability`。
- backtest/report execution：`strategy1-backtest-report-job-6fzvr`，完成时间约 2m58s，无 ERROR / CJK glyph warning。
- report URI：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_cloudrun_sklearn_smoke_20260604_02/backtest_id=bt_s1_cloudrun_sklearn_smoke_20260604_02`。
- 回测指标：total_return 46.29%、annual_return 21.72%、Sharpe 1.111、max_drawdown -13.94%、excess_return 17.28% vs `000852.SH`。
- 模型质量 caveat：BQML valid RankIC 0.09676，sklearn valid RankIC 0.06665，rank delta -0.03011 超出 0.02 阈值；`model_quality_parity_status=failed`，`model_quality_status=model_quality_not_equivalent`。

### 改动文件

- `Dockerfile.strategy1-cloudrun`
- `cloudbuild.strategy1-cloudrun.yaml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1/render_report.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/preprocess.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/train_predict.py scripts/strategy1_cloudrun/backtest_report.py scripts/strategy1_cloudrun/orchestrate_experiments.py scripts/strategy1_cloudrun/preprocess.py scripts/strategy1/render_report.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`
- Cloud Build 成功：build id `52191460-108a-404b-8017-c65eaa8ef259`。
- Cloud Run orchestrator resume from `cloudrun_backtest_report` 成功，final execution `strategy1-backtest-report-job-6fzvr` succeeded。
- `16_qa_cloudrun_runner_outputs.sql` 以 smoke 参数 `p_require_model_quality_parity_passed=FALSE` 通过。
- `17_qa_cloudrun_orchestrator_status.sql` 通过。
- `gcloud logging read` 未发现 final execution ERROR 或 CJK glyph warning。
- `git diff --check`。

### 阻塞项

- 无运行链路阻塞。模型质量阻塞仍存在：当前 sklearn backend 未达到 BQML baseline parity，不能作为正式替代。

### 下一步建议

- 提 PR review 本次 Cloud Run smoke 修复。
- 合并后做 sklearn backend 参数 / 模型族迭代，使 parity gate 通过，或由 owner 明确接受新的 sklearn baseline。
- 补 Python ledger vs SQL ledger 的完整等价验收；当前真实 smoke 已证明 Cloud Run Python ledger 能跑通，但还不是正式等价证明。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: manual_oq005_scheduler_smoke_default_queue_20260604_01 / manual_oq005_daily_prod_20260604_01
相关 issue/PR: OQ-005 / GCP pipeline production ingestion phase 1.7

### 已完成工作

- 在工作树 `/private/tmp/quant-ashare-oq005-deploy-phase1`、分支 `codex/oq005-deploy-phase1` 继续推进 OQ-005 生产采集部署，并在 rebase 到最新 `origin/main` 后保留 main 的策略 1 Cloud Run runner 状态。
- 新增并部署 `ashare-ingest-current-scope` Cloud Run Job，单 execution 顺序执行当前实际消费的 14 个 ODS endpoint；4 个分组 Jobs 保留为诊断和单组补救入口。
- PR #58 review follow-up 已补 live BigQuery meta 状态写入：`ashare_meta.ingestion_run` 和 `ashare_meta.ingestion_partition_status`。
- 已把 raw GCS canonical 路径固定为 `api=<api>/endpoint=<partition_endpoint>/partition_date=...`，并用 BigQuery `INFORMATION_SCHEMA.TABLE_OPTIONS` 只读复核当前 14 张 ODS 与 10 张 schema repair 表 source URI。
- 已明确 ingestion publish 覆盖正式 `data.parquet` 不做 write-once backup；历史可回滚回填留后续独立开关/流程。
- Cloud Run Jobs 已配置 Direct VPC egress + Cloud NAT + 区域静态外部 IP 固定出口；Job 模板默认保留 `--dry-run`，Composer 生产路径显式传入 `--allow-gcs-write`。
- `ashare_daily_pipeline_v0` 已移除 `queue="kubernetes"`，使用 default Celery queue；纯 scheduler smoke `manual_oq005_scheduler_smoke_default_queue_20260604_01` 成功。
- 生产 GCS 回填已完成：`2026-05-20` 至 `2026-06-03` 区间内 SSE 开市日全部写入成功，并逐日通过 `sql/qa/09_ods_daily_partition_readiness.sql`。
- Composer 生产 DAG 首跑 `manual_oq005_daily_prod_20260604_01` 已写入 `2026-06-04` 数据并成功完成 readiness。
- Airflow 变量当前为 `ashare_pipeline_dry_run=false`、`ashare_enable_full_refresh=false`。

### 重要上下文

- 当前只启用 ODS 生产采集和每日分区 readiness；完整 ODS→DIM/DWD/DWS/ADS 转换仍在 `ashare_enable_full_refresh=true` 显式分支之后，尚未作为生产链路验收。
- Cloud Run Job 模板保留 `--dry-run` 是安全门禁；生产写入依赖 Composer 传参，不能在脚本中移除 token/dry-run guard。
- Token 只保存在 Secret Manager，不写仓库、文档、日志或记忆。
- `ods_tushare_stk_limit` 历史 Parquet schema mismatch 仍属于 OQ-012 维护/修复工作，不阻断每日生产采集。

### 改动文件

- `scripts/ingestion/run_ingestion_job.py`
- `scripts/ingestion/README.md`
- `scripts/ingestion/common/gcs_writer.py`
- `scripts/ingestion/common/status_writer.py`
- `configs/ingestion/schema_contracts/suspend_d.json`
- `orchestration/cloud_run_jobs/deploy_ingestion_jobs.sh`
- `orchestration/cloud_run_jobs/ingestion_jobs.yaml`
- `orchestration/cloud_run_jobs/README.md`
- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `orchestration/composer/README.md`
- `orchestration/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- Artifact Registry latest digest 确认为 `sha256:351dfd996b6ec066135d68c40f84eb1c2a52e43ea8e28208ba1711be90a7652d`。
- `gcloud composer environments run ... variables get -- ashare_pipeline_dry_run` 返回 `false`。
- `gcloud composer environments run ... variables get -- ashare_enable_full_refresh` 返回 `false`。
- `gcloud composer environments run ... dags state -- ashare_daily_pipeline_v0 2026-06-04T15:15:08+00:00` 返回 `success, {"business_date": "2026-06-04"}`。
- `2026-05-20` 至 `2026-06-03` SSE 开市日生产回填均有对应 Cloud Run execution 成功记录，并逐日通过 `sql/qa/09_ods_daily_partition_readiness.sql`。
- `git rebase origin/main` 成功。
- `git diff --check` 通过。

### 阻塞项

- 无当前采集阻塞。OQ-005 仍未关闭，因完整 ODS→ADS 生产转换、告警、补跑和运维观测尚未验收。

### 下一步建议

- 接入/验证 Dataform 或 BigQuery SQL 生产转换链路。
- 补 Cloud Composer 告警、补跑和运行状态观测。
- 明确 ODS→ADS full refresh 的生产启用窗口，再将 `ashare_enable_full_refresh=true` 作为单独维护/补跑任务验收。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / Cloud Run orchestrator status and lock implementation

### 已完成工作

- 通过 GitHub API 合并 PR #56，并删除远端 `codex/implement-strategy1-cloudrun-runner` 分支。
- 创建工作树 `/Users/luna/Desktop/git/quant-ashare-cloudrun-orchestrator-state-lock`，分支 `codex/cloudrun-orchestrator-state-lock`。
- 新增 `scripts/strategy1_cloudrun/state.py`，封装 `OrchestratorStatusTable`、GCS generation-guarded lease lock、heartbeat/release、experiment params JSON 和 Cloud Run execution id 提取。
- 改造 `scripts/strategy1_cloudrun/orchestrate_experiments.py`：每个实验链的 `cloudrun_train_predict` / `cloudrun_backtest_report` step 写入 `ashare_meta.strategy1_experiment_run_status`，执行前获取 GCS lock，执行中 heartbeat，支持 `--resume` 跳过已成功 step，支持 `--resume-from-step cloudrun_backtest_report` 从指定 step 继续。
- 新增 `sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`，校验 orchestrator 状态、锁元数据、审计字段和 execution id 记录。
- 跟进 PR #57 review comment：Cloud Run orchestrator 改为先启动 execution、记录 execution id 到 GCS lock/status table，再轮询 execution terminal 状态；stale lock 回收前会检查原 execution 是否 terminal；失锁时 cancel 当前 execution；heartbeat 的 GCS/BQ 瞬时错误不再杀线程；QA-CRO-4 改为断言 succeeded step 必须记录 execution id。
- 同步 Cloud Run 默认配置、运行手册、runner README、`TODO.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要。

### 重要上下文

- 当前分支只做 orchestrator 状态/锁/resume 增强；没有启动真实 Cloud Run Job，没有重建 ADS 表，没有上传真实 sklearn model artifact。
- 状态表复用既有 `sql/meta/02_strategy1_experiment_run_status.sql`；执行 Cloud Run orchestrator 前必须先确保该表存在。
- GCS lock 默认路径为 `gs://ashare-artifacts/locks/strategy1/cloudrun/<lock_key>.lock`，lock key 使用 prediction run 或 backtest id 分离 train/predict 与 backtest/report step。
- `attempt` 只在非 running 状态进入 running 时增加；heartbeat 只刷新 lease 和 running 状态，不反复增加 attempt。
- `gcloud run jobs execute` 不再加 `--wait`；orchestrator 启动 execution 后用 `gcloud run jobs executions describe` 轮询状态，因此 stale lock payload 中能保留可检查的 execution id。

### 改动文件

- `configs/strategy1/cloudrun_runner_default.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/state.py`
- `sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`

### 测试 / 验证

- `python3 -m compileall scripts/strategy1_cloudrun`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --experiment-id oq010_a0_n5_w20 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --experiment-id oq010_a0_n5_w20 --resume-from-step cloudrun_backtest_report --dry-run`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --stage-id stage_a --resume --dry-run`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/meta/02_strategy1_experiment_run_status.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`
- 小单元式校验：`extract_cloud_run_execution_id` 可从 `metadata.name` 和完整 `/executions/` resource name 提取 execution id；`cloud_run_execution_state` 可识别 succeeded / failed / completionTime。
- `git diff --check`

### 阻塞项

- 无代码阻塞。真实验收仍需部署/确认 Cloud Run Jobs 后跑单实验 smoke。

### 下一步建议

- 提 PR review 本次 Cloud Run orchestrator 状态/锁增强。
- 合并后执行单实验真实 Cloud Run smoke，跑 `16_qa_cloudrun_runner_outputs.sql` 与 `17_qa_cloudrun_orchestrator_status.sql`。
- 用真实 smoke 结果验证 sklearn vs BQML parity、Python ledger vs SQL ledger 等价性、GCS model/report artifact 和 ADS 回写。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / Cloud Run strategy1 runner implementation

### 已完成工作

- 启动并完成策略 1 Cloud Run 训练回测执行器首版实现，工作分支 `codex/implement-strategy1-cloudrun-runner`，worktree `/Users/luna/Desktop/git/quant-ashare-strategy1-cloudrun-runner`。
- 新增 `scripts/strategy1_cloudrun/` Python 包：配置/实验 manifest 解析、BigQuery/GCS IO、sklearn 训练预测、Python fresh-start ledger、SQL 参数化 runner、Cloud Run 多实验 orchestrator。
- 新增 `Dockerfile.strategy1-cloudrun`、`cloudbuild.strategy1-cloudrun.yaml`、`configs/strategy1/cloudrun_runner_default.yml` 和 `docs/策略1CloudRun训练回测运行手册.md`。
- 新增 `sql/meta/03_strategy1_cloudrun_status_extensions.sql` 和 `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`；`09_build_metrics_and_report_inputs.sql` 已把 `execution_backend` 写入 summary `metrics_json`。
- `sql/ml/strategy1/README.md` 和 `scripts/strategy1/requirements.txt` 已同步 Cloud Run / sklearn runner 运行说明和依赖。
- 跟进 PR #56 review comment：确认 QA-CR-5 提到的 `ledger_version` 缺失不成立（`09` 已写入该字段）；同时补 `p_ledger_version` / `p_ledger_executor` 参数化、`--use-bq-ledger` fallback backend 标记、parity failed fail-fast 与 QA hard gate、orchestrator 失败结果汇总和 `--continue-on-error`。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要。

### 重要上下文

- 当前首版边界：`01_build_training_panel.sql` 仍是前置 SQL；`05/06/07` 仍复用 BigQuery SQL；Python ledger P0 只支持 fresh-start，resume 先 fail-fast，等 Python ledger vs SQL ledger 等价验收后再补。
- Cloud Run orchestrator 遵守 PRD 并发契约：未设置或传 `0` 时，默认并发数等于 manifest 中可执行实验数量；owner 可用 `--max-parallel-experiments N` 显式限流。P0 采用唯一 `run_id` / `backtest_id` + Cloud Run execution 轻隔离，尚未写 `strategy1_experiment_run_status` / GCS lock，真实多实验 smoke 后再对齐状态框架。
- 为避免 Cloud Run job 读取本地临时 manifest，orchestrator 已把 resolved experiment payload 通过 URL-safe base64 `--experiment-json` 传入 job。
- 本地 Python 3.9 环境未安装 sklearn/joblib；代码已使用 lazy import，使 dry-run 不依赖本地 sklearn。真实训练应在 Cloud Run 镜像内用 Python 3.11 和 requirements 执行。
- 本次没有执行真实 Cloud Run job，没有重建 ADS 表，没有上传真实 sklearn model artifact。

### 改动文件

- `Dockerfile.strategy1-cloudrun`
- `cloudbuild.strategy1-cloudrun.yaml`
- `configs/strategy1/cloudrun_runner_default.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1/requirements.txt`
- `scripts/strategy1_cloudrun/*`
- `sql/meta/03_strategy1_cloudrun_status_extensions.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`

### 测试 / 验证

- `python3 -m compileall scripts/strategy1_cloudrun`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --experiment-id oq010_a0_n5_w20 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --stage-id stage_a --dry-run`
- `python3 -m scripts.strategy1_cloudrun.train_predict --experiment-id oq010_a0_n5_w20 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.backtest_report --experiment-id oq010_a0_n5_w20 --dry-run`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/meta/03_strategy1_cloudrun_status_extensions.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `git diff --check`
- PR #56 review follow-up 后补跑：`python3 -m compileall scripts/strategy1_cloudrun`、`python3 -m scripts.strategy1_cloudrun.backtest_report --experiment-id oq010_a0_n5_w20 --dry-run`、`python3 -m scripts.strategy1_cloudrun.backtest_report --experiment-id oq010_a0_n5_w20 --use-bq-ledger --dry-run`、`python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --stage-id stage_a --dry-run`、`09` / `16` BigQuery dry-run、`git diff --check`。

### 阻塞项

- 无代码阻塞。真实验收仍需部署 Cloud Run Jobs 并跑单实验 smoke。

### 下一步建议

- 提 PR review 本次 Cloud Run runner 首版实现。
- PR review 通过后部署 Cloud Run image/jobs，跑单实验真实 smoke。
- 真实 smoke 后补 sklearn vs BQML parity、Python ledger vs SQL ledger 等价验收；等 fresh-start 等价通过后再实现 resume path。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / Cloud Run training and backtest PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`。
- PRD 决定只写一篇统一文档，不拆训练 PRD 和回测 PRD，避免训练、预测、回测、实验并发和 artifact 契约漂移。
- PRD 定义 Cloud Run Jobs + scikit-learn logistic 训练 / 预测 + Python `ledger_exec_v1` 回测的目标执行路径。
- PRD 明确 scikit-learn 只替代 BQML `LOGISTIC_REG` 的模型训练 / 预测，不替代 BigQuery DWS/ADS、GCS artifact、报告诊断和 QA；P0 仍需 BigQuery / GCS 客户端、`pyarrow`、`polars` 或 `pandas`、`joblib` 等依赖。
- PRD 固化 Cloud Run 多实验默认并发规则：`--max-parallel-experiments` 未设置或为 0 时，并发数等于 manifest 可执行实验数量；owner 显式传 N 时才限流。
- 跟进 PR #55 review comment `issuecomment-4622638415`：补 sklearn vs BQML 模型质量对等门槛；P0 默认 `class_weight=None`；明确 sklearn 正则网格是重新定义，不直接翻译 BQML `L1_REG` / `L2_REG`。
- 新增 `DECISION-20260604-03`，并同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`KNOWN_CONSTRAINTS.md`、`PROJECT_CONTEXT.md`、`ARCHITECTURE_MEMORY.md` 和当前交接摘要。

### 重要上下文

- 本次只写 PRD 和记忆/TODO，没有实现 Cloud Run 代码，没有创建 GCP 资源，没有执行 BigQuery，也没有生成或覆盖报告 artifact。
- 既有 BigQuery ML + SQL runner 保留为 reference / fallback，直到 Cloud Run sklearn + Python ledger 路径通过契约、QA 和回测语义一致性验收。
- Cloud Run runner 的默认全实验并发是 owner 明确要求；不要沿用本地 OQ-010 调度器 `max_parallel=2` / `max_parallel_backtest=1` 的保守默认值。

### 改动文件

- `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review 并合并 Cloud Run 训练回测 PRD。
- 实现前先确认 Cloud Run region、service account、artifact bucket 和容器构建方式；默认沿用 `asia-east2`、`data-aquarium`、`gs://ashare-artifacts`。
- PRD 合并后新增 `scripts/strategy1_cloudrun/`、Cloud Run Dockerfile / build config、`sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql` 和运行手册。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01 / bt_ledger_v1_p0_smoke_20260604_01
相关 issue/PR: OQ-010 / Ledger v1 P0 implementation

### 已完成工作

- 实现策略 1 `ledger_exec_v1` P0 交易执行语义。
- `08_run_backtest.sql` 改为日级账户 ledger：t-1 信号 / t 开盘执行、每日 pending sell retry、卖出先于买入、实际持仓 netting、现金缩放、非目标持仓继续 mark-to-market、订单状态显式记录。
- 同步 `09` 指标汇总、`10` runner QA、`11` 诊断 SQL、ADS 字段说明、报告脚本、诊断脚本和 README。
- 修复报告买入明细关联预测表时缺少 `predict_date` 分区过滤的问题。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`KNOWN_CONSTRAINTS.md` 和当前交接摘要。

### 重要上下文

- P0 仍保留 PRD 定义的简化：FLOAT 股数、不做 100 股手数约束、不显式 T+1 卖出锁定、不做买入候补、不做 partial-fill 深度模型。
- 短区间 smoke 使用正式 baseline prediction run：`s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01`，新建 smoke backtest：`bt_ledger_v1_p0_smoke_20260604_01`，窗口 `2024-01-02` 至 `2024-02-29`。
- smoke `render_report.py` 使用 `--skip-gcs-upload`，只验证本地报告和 ADS 回写，不上传 GCS。

### 改动文件

- `sql/ml/strategy1/08_run_backtest.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/11_model_quality_diagnostics.sql`
- `sql/ads/01_ads_strategy1_tables.sql`
- `scripts/strategy1/render_report.py`
- `scripts/strategy1/diagnose_model_quality.py`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `bq query --dry_run`：`08_run_backtest.sql`、`09_build_metrics_and_report_inputs.sql`、`10_qa_runner_outputs.sql`、`11_model_quality_diagnostics.sql`、`sql/ads/01_ads_strategy1_tables.sql`
- `python3 -m py_compile scripts/strategy1/render_report.py scripts/strategy1/diagnose_model_quality.py`
- 短区间 BigQuery smoke：`08`、`09`、`render_report.py --skip-gcs-upload`、`10_qa_runner_outputs.sql` 全部通过
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review/merge Ledger v1 P0 实现 PR。
- 合并后用正式 baseline 参数跑完整 `2024-01-02` 至 `2025-12-31` 同区间 A/B，对比旧 ledger 与 `ledger_exec_v1`。
- A/B 收敛后再做 P1 fixed-model 连续扩展回测至 `2026-04-30` 和 P2 state resume。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / factor attribution PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260604_03_策略1因子贡献度分析.md`。
- 明确本轮因子贡献度分析不做消融实验，不重训、不 drop factor，只读当前 baseline。
- 因子贡献度 PRD 定义模型系数/标准化系数、单因子 RankIC/bucket lift、score contribution、组合因子暴露、归因 proxy 和因子相关性/共线性摘要。
- 更新 Ledger PRD 和月度重训 PRD 的推荐实施顺序：因子贡献度分析 → Ledger v1 P0/P1/P2 → 月度滚动重训。
- 跟进 PR #51 comment，补充多重共线性解释边界：单因子系数排名不稳定、组级解读优先、单因子 RankIC 与多变量系数可能不一致、proxy 贡献不可跨相关因子加总。
- 新增 `DECISION-20260604-02` 并同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要。

### 重要上下文

- 因子贡献度分析只是实施顺序上的前置解释基准，不代表优先级高于 Ledger 或月度重训。
- 当前 PRD 已把高相关因子问题写成解释约束；实现时必须输出 `factor_correlation_summary.csv` 并在中文摘要提示共线性限制。
- P0 推荐实现为独立 `scripts/strategy1/attribute_factor_contribution.py`，产出 `factor_attribution/` artifact，再用 `14_qa_factor_attribution_outputs.sql` 验收。
- 若未来要做消融实验，需要另写 PRD；本 PRD 明确禁止把消融路径混进 P0。

### 改动文件

- `docs/prd/PRD_20260604_03_策略1因子贡献度分析.md`
- `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review 并合并因子贡献度 PRD。
- 合并后实现 `attribute_factor_contribution.py` 和 `14_qa_factor_attribution_outputs.sql`，先对正式 baseline 生成 factor attribution artifact。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / Ledger v1 PRD / monthly retrain PRD

### 已完成工作

- 按 owner 采纳的方案改造两篇 PRD：不新增第三篇 PRD。
- `PRD_20260604_01_策略1LedgerV1交易执行语义.md` 已扩展为 Ledger P0/P1/P2：P0 交易执行语义、P1 `2024-01-02` 至 `2026-04-30` fixed-model 连续扩展回测、P2 ledger state resume。
- `PRD_20260604_02_策略1月度滚动重训.md` 已收敛为只定义模型生命周期、失败回退和 PIT-safe prediction stream，并明确依赖 Ledger P0/P1/P2。
- 新增 `DECISION-20260604-01`，固化实现顺序为 Ledger v1 P0 → Ledger v1 P1 → Ledger v1 P2 → 月度滚动重训。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要。

### 重要上下文

- 2026 扩展回测和 resume 均归入 Ledger/backtest 执行能力，不归入月度重训。
- P1 扩展回测必须 fixed-model fresh-start 从 `2024-01-02` 连续跑到 `2026-04-30`；不能用只跑 2026 片段再简单拼接替代。
- 月度重训正式效果归因必须等 Ledger P0/P1/P2 稳定后再做。

### 改动文件

- `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 提 PR review 两篇 PRD 改造。
- PRD 合并后先实现 Ledger v1 P0 交易执行语义并用正式 baseline 参数 A/B。
- P0 稳定后再做 P1 fixed-model 扩展回测和 P2 resume；最后实现月度滚动重训。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`
---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / Ledger v1 PRD / monthly retrain PRD / memory cleanup

### 已完成工作

- 清理工作记忆：`AGENT_HANDOFF.md` 缩到当前摘要 + 最近 3 条交接，19 条旧交接归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。
- 新增 `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`。
- 新增 `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`。
- 跟进 PR #49 review comment，补充 Ledger PRD 的 T+1 卖出锁定非目标、月度重训 PRD 的 oriented RankIC 通过标准和 test split 事后评价口径。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要。

### 重要上下文

- Ledger v1 PRD 固化 t-1 信号 / t 开盘执行、pending sell 每日继续卖、实际持仓 netting、现金缩放、订单状态和每日 mark-to-market NAV；明确不改变模型训练/预测来源。
- 月度滚动重训 PRD 定义 monthly cadence、rolling 5 年训练窗口、12 个月 valid 窗口、月内固定模型、失败回退和 PIT-safe prediction stream。
- 实现顺序必须先 Ledger v1 A/B，再月度重训，避免交易执行语义变化和模型生命周期变化混在一起。

### 改动文件

- `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 提 PR review 两篇 PRD。
- PRD 合并后先实现 Ledger v1 交易执行语义，并用正式 baseline 参数 A/B。
- Ledger v1 A/B 收敛后，再实现月度滚动重训 prediction stream。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #70 / OQ-005 / OQ-012 memory update

### 已完成工作

- 确认 PR #70 实现工作树为 `/private/tmp/quant-ashare-oq005-daily-window-hardening`，分支 `codex/oq005-daily-window-hardening`；该工作树与分支已在 PR #70 合并后清理。
- 在当前主工作树 `/Users/luna/Desktop/git/quant-ashare` 更新项目记忆与 TODO，补齐 PR #70 合并后的 Composer SQL 同步和 smoke 事实。
- 记录 Composer bucket `data/sql/` 中 `sql/incremental/01_refresh_stock_dwd_dws_window.sql` 与 `sql/qa/10_windowed_stock_refresh_checks.sql` 哈希均与当前 `main` 一致。
- 记录 OQ-005 smoke：`manual_oq005_backfill_smoke_pr70_20260605_01` 成功；`manual_oq005_daily_current_nontd_20260606_01` 因 `2026-06-05` ODS 未采集在 readiness 阶段以 `QA-ODS-DAILY-2` 阻断，窗口写入未执行。
- 记录 QA-WIN-18 只读复核：`2026-06-03..2026-06-04` expected rows 11,022，false/missing 0。
- 更新 OQ-012 状态：`sql/qa/06_ods_parquet_schema_checks.sql` 对 P0 与 all 范围均通过，当前 BigQuery 读层未再暴露 schema mismatch。

### 重要上下文

- 本次只更新记忆/TODO，没有修改 SQL、DAG、部署配置或生产资源。
- OQ-005 仍 open，剩余 Dataform definitions、告警、补跑和完整运维观测闭环。
- OQ-012 当前读层 QA 已通过；是否关闭/归档，或保留 schema contract / ingestion 显式 cast 防复发任务，待 owner 决定。
- `2026-06-05` ODS 尚未采集时，非交易日 daily_current 只能验证 readiness 阻断，不能验证“有 ODS 时的非交易日正向窗口刷新”。

### 改动文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`
- `git status --short --branch`

### 阻塞项

- 无。

### 下一步建议

- 等 `2026-06-05` ODS 采集完成后，再跑一次非交易日 daily_current 正向 smoke，验证归一到最近交易日且窗口刷新成功。
- 继续 OQ-005 的 Dataform definitions、告警、补跑和 pipeline 观测闭环。
- 由 owner 决定 OQ-012 是否关闭/归档。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

## 2026-06-08 pre-trim snapshot from AGENT_HANDOFF.md

This snapshot was archived during the 2026-06-08 memory cleanup pass. The
current `AGENT_HANDOFF.md` was reduced to the active summary plus the most
recent three handoff entries. The full pre-trim content is preserved below.

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - `orchestration/composer/` 已收口为历史审计目录：README 改成 retired / audit-only 边界说明，并移除了针对已删除 `ashare-composer` 环境的操作命令。
> - `ashare_common.py` 与 5 个 Composer DAG 顶部都已明确标记“仅保留为 2026-06-08 前最后一版 Composer 实现快照，不再接受新的生产调度变更”。
> - 当前生产部署与调度变更入口继续只保留 `orchestration/workflows/**`；后续如果再碰 Composer，应该视为新的架构决策，不是现行运维路径。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - PR #122 最新 re-review 指出的 `QA-V3-1` sentinel/render bug 已修：`run_acceptance_gate_v3_replay_qa.py` 对 placeholder 改回单次替换，`24_qa_acceptance_gate_v3_replay_outputs.sql` 的 primary benchmark 断言恢复成对固定 `000001.SH` 的真校验。
> - 按这版代码已重新真跑 `replay_acceptance_gate_v3.py` 和 `run_acceptance_gate_v3_replay_qa.py --project data-aquarium`；结果仍为 `25` 个候选里 `1 accepted / 24 rejected`，且 `24` QA 全部通过。
> - 最新 replay / QA contract hash 已更新为 `8a84447e8190290fef2ae61b71a31678bc02fffda52b5a4701be36593e1ea1ed`，PR #122 body 也已同步刷新。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - PR #122 新一轮 comment follow-up 已继续收口 `24` QA 的 contract 边界：`run_acceptance_gate_v3_replay_qa.py` 现在不只渲染 `contract_hash / legacy_valid_as_cv_search_ids / final_holdout_enforcement`，还会把 replay search scope、Top-K、benchmark 集合、窗口、signal/absolute gate 阈值、final_holdout trading-day 阈值和允许的 score orientation 一并从 `model_acceptance_contract_v3.yml` 注入 SQL。
> - `model_acceptance_contract_v3.yml` 已新增 `replay_scope`，把五次正式搜索 `search_id` 列表和 `top_k_per_search` 纳入 contract；`24_qa_acceptance_gate_v3_replay_outputs.sql` 因此不再维护第二份 search scope 默认值。
> - 这轮没有再重跑 replay / `24` QA；目的是收口“QA 仍有残留硬编码，contract 还不是完整唯一事实来源”的 review。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - PR #121 review follow-up 已收紧两处生产边界：`ashare-workflows-runtime` 不再依赖项目级 `roles/run.developer`，而改为 `ashare-ingest-current-scope` job 级 `roles/run.invoker`；`cutover_scheduler_jobs.sh` 也改成默认先创建 paused Scheduler jobs、再 pause Composer，只有显式 `RESUME_SCHEDULER_JOBS=true` 才启用。
> - 这轮没有再重跑生产 scheduler；只会把最小权限变更打到 live IAM，避免为了验证 comment 再额外触发一次真实生产链。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - OQ-005 scheduled production cutover 已完成：`ashare-ods-ingestion-daily`（`0 20 * * *`）和 `ashare-pipeline-alert-checker`（`0 * * * *`）两个 scheduler 已 `ENABLED`，目标分别为 `ashare_ods_ingestion_daily` / `ashare_pipeline_alert_checker` workflows。
> - 真实 cutover 证据：alert-checker scheduler execution `978c920c-3810-4299-b904-3c954e8d221d` succeeded；ODS parent execution `31ac0d61-d40c-4a88-9865-b13f61d369c1` 与 child warehouse execution `919f2aba-b9d4-4181-9915-fa848487bb90` succeeded。
> - Composer 业务 DAG 已全部停用；`ashare-composer` 环境已于 2026-06-08 删除完成，`gcloud composer environments describe ashare-composer --location=asia-east2` 返回 `NOT_FOUND`。后续只需补短观察窗记录。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - PR #123 review follow-up 已把 OQ-005 的状态源彻底闭合：`OPEN_QUESTIONS.md` 中的 OQ-005 已删除，只保留在 `archive/CLOSED_QUESTIONS.md`。
> - `DECISION-20260603-02` 现已被新的 superseding 决策覆盖，明确长期编排从 Composer 改为 `Cloud Scheduler + Cloud Workflows`。
> - `orchestration/composer/README.md` 现已标注为历史路径，`orchestration/workflows/cutover_scheduler_jobs.sh` 在 Composer 环境已删除时也会 fail-soft 跳过 `dags pause`，避免后续再因为 `NOT_FOUND` 误把旧 cutover helper 当现行生产脚本。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - PR #120 合并后已做 live deploy：`ashare-pipeline-control` 升到 revision `ashare-pipeline-control-00005-mk5`，`ashare_warehouse_full_rebuild` 升到 workflow revision `000002-e70`。
> - post-merge dry-run smoke `773f26c1-2a80-41ab-9b85-fa7c208f0342` 已 success，说明这轮补进去的 poll 失败终态写回和 `bigquery_max_polls` 输入化至少没有造成新的接线回归。
> - 本轮仍然没有执行真实 full rebuild 写路径；OQ-005 在 full rebuild 这条线上的剩余风险，已经收敛回 cutover 前是否要做一次更大范围 dry-run 或真实写入验证。
> - `v3` replay 与 helper 驱动的 `24` QA 已按最新 contract 真执行成功：`replay_acceptance_gate_v3.py` 结果仍为 `25` 个候选里 `1 accepted / 24 rejected`，最新 contract hash 为 `6e6d77881e8ca8f437154be9bec9b4972e35140c0b2562e7732150e37b9e8418`。
> - `run_acceptance_gate_v3_replay_qa.py` 已成功驱动 `24_qa_acceptance_gate_v3_replay_outputs.sql` 全部通过；这意味着 legacy valid-as-CV carve-out、`final_holdout=diagnostic_only`、五指数公式锁定和 contract-driven 参数注入都已在真实 BigQuery 执行中收口。
> - 为让 `24` QA 跑通，本轮额外修了两个 SQL 实现问题：`nav_drawdown` 曾误把整行 `nav` struct 当成数值列，现已改成 `nav.nav AS nav`；`QA-V3-8` 对 `dwd_index_eod` 的 4 个 join 已补显式分区过滤，避免 BigQuery partition elimination 报错。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - `24` QA 现在不再靠 SQL 里的手工镜像默认值维持语义一致性。已新增 `scripts/strategy1/run_acceptance_gate_v3_replay_qa.py`，从 `model_acceptance_contract_v3.yml` 注入 `contract_hash`、`legacy_valid_as_cv_search_ids` 和 `final_holdout_enforcement` 后再执行 BigQuery QA。
> - `replay_acceptance_gate_v3.py` 也已改成从 contract 读取 `replay_compatibility.legacy_valid_as_cv_search_ids`，不再保留 Python 侧硬编码 allowlist。
> - 这套 helper / 新语义现已完成真实 replay 与真实 `24` QA 验证，不再停留在代码就绪状态。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - owner 已明确：`final_holdout` 在 `v3` 中不再是 hard veto。contract 现在把 `final_holdout_gate.enforcement` 标成 `diagnostic_only`，`trading_day_count >= 40` 只保留为诊断阈值。
> - `replay_acceptance_gate_v3.py` 已同步：`absolute_gate_failures()` 不再因 final_holdout 天数不足而拒绝，candidate artifact 新增 `final_holdout_gate_status`。
> - `24` QA 的 `QA-V3-6` 也已同步降级，只要求 final_holdout trading day count 可计算，不再要求 `>= 40`。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - `v3` replay 已在新工作树重跑成功，结果仍是 `25` 个候选里 `1 accepted / 24 rejected`；contract hash 仍为 `03be9f1c6c392973c8c298eba7f68ea8e957b760cbb5e9761d44e0cf0d075283`。
> - `24` QA 现在已经从 `QA-V3-5` 推进到 `QA-V3-6`：legacy valid-as-CV fallback 生效后，字段缺口不再阻塞。
> - 当前唯一剩余失败项是首轮 `sklearn_native_pvfq_n30_bw_h5_20260605_01` 的 5 个 historical selected row 在 `2026-01-05..2026-04-30` 没有任何 NAV 行，因此 `final_holdout trading days = 0`；下一步需要 owner 决定这类“没有 2026 holdout 的历史 search”在 `v3` replay 中是保持 hard fail，还是再定义历史兼容规则。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - `v3` replay / `24` QA 现在又补了一层只对首轮 native search 生效的 legacy 兼容：`sklearn_native_pvfq_n30_bw_h5_20260605_01` 缺 `cv_confirmation_status` / `cv_*` 字段时，不再判成不可算，而是用同 row 已持久化的 `valid_signal_status`、`valid_rank_ic`、`valid_top_minus_bottom_fwd_ret_mean` 代替 CV 证据。
> - 兼容规则已经钉死：`stable + valid_rank_ic>0 + valid_top_minus_bottom>0 => passed`，否则 `failed`；只对这轮历史 sklearn search 生效，不推广到后续 LightGBM / risk-feature 搜索。
> - 这次还没有重跑 replay / `24` QA；下一步应直接验证 `QA-V3-5` 是否被这条 legacy fallback 打通。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - PR #120 第二轮 review follow-up 已继续收口 full rebuild poll 终态：`get_job(...)` 用尽内部重试后，现在会显式把 task 写成 `failed`，不再让 `pipeline_task_status` 卡在 `running`。
> - `ashare_warehouse_full_rebuild` 还补了 `bigquery_max_polls` workflow 输入化，默认仍是 `1440`；以后若全量窗口继续变大，可以只调 workflow 参数，不必改 YAML 常量。
> - 另外已把 control service 当前 poll 重试的同步 `time.sleep` 约束写进 README 和 `KNOWN_CONSTRAINTS.md`：单次 `/v1/tasks/bigquery/poll` 最坏会多占一个 worker 约 `15s`，这是 cutover 前需要接受的显式容量边界。
> - PR #119 review follow-up 已继续收口 `v3` replay fallback：`effective_test_metric` 两个 test 字段现在都按“有限 raw 值优先，否则 fallback”处理，避免 spread 字段的 `inf`/非有限 raw 值吞掉 fallback。
> - replay candidate artifact 已新增 `cv_confirmation_status_from_fallback`、`test_rank_ic_from_fallback`、`test_top_minus_bottom_fwd_ret_from_fallback`，便于审计值是来自历史 `metrics_json` 还是 source-fallback。
> - `24` QA 里的 `qa_v3_selected_rows` 已把 backtest summary 连接改回 `LEFT JOIN`，继续显式暴露“selected row 缺 summary”而不是在 CTE 前置静默过滤。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - Strategy1 `v3` replay / `24` QA 已补历史 search 字段缺口兼容：不再要求旧 `metrics_json` 必须原生带齐 `cv_confirmation_status` / `test_*`，而是按 source-of-truth fallback 读取。
> - 具体口径：`cv_confirmation_status` 缺失时按 `cv_rank_ic_mean` + `cv_top_minus_bottom_fwd_ret_mean`（以及存在时的 `cv_fold_count`）回推；`test_rank_ic_mean` / `test_top_minus_bottom_fwd_ret_mean` 缺失时，从 `ads_model_prediction_daily` + `ads_ml_training_panel_daily` 的 `test` 窗口按原 orchestrator 公式现算。
> - 这次没有重跑 replay 或 `24` QA；下一步应先重新执行这两步，确认 `QA-V3-5` 不再被历史字段缺口阻断。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - PR #117 review 的 P1 已按建议收敛：`ashare_pipeline_alert_checker.yaml` 不再写 `pipeline_run` / `pipeline_task_status`，只做参数归一后调用 `/v1/tasks/alert-check`。
> - 原因是避免 checker 失败被下一轮 checker 自己读回成 pipeline failure 告警，以及避免 `v_pipeline_recent_runs` 被每小时 checker 行刷满。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - OQ-005 alert checker 的 `Cloud Scheduler -> Workflows -> ashare-pipeline-control` 已完成真实部署与 smoke：manual execution `a2743da9-2654-4521-9222-4fbf2b5dc113` succeeded，Scheduler execution `ca8b6bdd-f137-4727-9311-29b5b8fb9d20` 也 succeeded。
> - 这次 live 路径补出了两个真实运行期问题并已修复：`deploy_scheduler_jobs.sh` 需要区分 `create http --headers` 与 `update http --update-headers`，以及 Workflow resolve 分支里原生 `int/bool` 不能再直接和 `\"\"` 比较。
> - 当前 scheduler job 已重新置回 `PAUSED`，避免在整体 OQ-005 cutover 前引入双跑。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - OQ-005 alert checker 的实现代码已在工作树落地：新增 `orchestration/workflows/ashare_pipeline_alert_checker.yaml`，并把 `orchestration/workflows/deploy_scheduler_jobs.sh` 从直连 Cloud Run 改成调用 Workflows Executions API。
> - 这次没有做真实部署；当前状态是“代码已实现，Scheduler caller SA `workflows.invoker` + live smoke 仍待执行”。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - PR #115 第二轮复评里指出的本地绝对路径 nit 已修：OQ-005 PRD 不再把 `/Users/fisher/...` 写进提交文本，已统一改回仓库相对路径 `orchestration/workflows/deploy_scheduler_jobs.sh`。
> - 这次没有新增实现决策，只是把文档表述从“机器本地路径”收敛回“仓库路径”。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - PR #115 review follow-up 已把 OQ-005 alert checker 改道写成实现级硬约束：Scheduler caller service account 必须具备目标 workflow 的 `roles/workflows.invoker`，Workflows runtime service account 必须保留 `ashare-pipeline-control` 的 `roles/run.invoker`。
> - 也已明确：`main` 上现有 `orchestration/workflows/deploy_scheduler_jobs.sh` 仍是被放弃的 `Scheduler -> authenticated Cloud Run` 直连实现，在改写为 Workflows Executions API 之前视为 `superseded / do-not-run`。
> - 此次还会把分支 rebase 到最新 `main`，把已合入 `main` 的 `v3` PRD 噪音从 PR #115 中清掉；本 PR 继续保持 OQ-005 doc-only 范围。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - PR #114 review follow-up 已加硬 `v3` 切门 PRD：补了 `Sharpe` / `Calmar` / `Excess Calmar` 的除零规则、`max_drawdown` 负号约定、`策略最大回撤同期超额` 的窗口与价格字段定义。
> - 也补了五指数 `sec_code`、`000001.SH` 主 benchmark 的职责说明，以及“默认 `2024-01-02..2026-04-30` 只是首次 replay / cutover 默认窗口，不是未来月度滚动重训的永久硬编码窗口”。
> - 本次仍是 doc-only，不改 acceptance 实现；下一步继续是 `model_acceptance_contract_v3.yml -> replay -> QA -> live cutover`。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - 已新增 `docs/prd/PRD_20260608_02_策略1验收门v3切换实施.md`，把后续切门路线冻结为直接 `v1 -> v3`，明确忽略 `v2`。
> - 本次只写 PRD，不改 acceptance 实现、不改 manifest、不改 QA；当前 live search 仍使用 `model_acceptance_contract_v1.yml`。
> - `v3` 何时可用的标准已写清：先落 `model_acceptance_contract_v3.yml`，再做历史正式搜索 replay、补 `v3` QA，最后才切主写回门。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - Strategy1 Cloud Run `prepare_matrix` 已修复 JSON 布尔特征误按 `FLOAT64` 解包导致 `train split` 预期列全 `NULL` 的问题；已改为 `BOOL -> INT64`。
> - 已用 `configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml` 跑通 `12` 候选 LightGBM regression smoke，主 benchmark 为 `000001.SH`，`*_vs_primary_benchmark`、Top1 backtest、comparison artifacts 链路已验证。
> - 最终 smoke `search_id=cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_smoke_20260608_05`，Top1 为 `lgbm_r03_l63_lr002_n600_leaf300_ff09_bf09_l1_01_l2_1`，结果 `rejected`，原因为 `overall_excess_return_vs_primary_benchmark<=0.0;sharpe<0.7;max_drawdown<-0.25`。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - OQ-005 `ashare_pipeline_alert_checker` 的迁移目标已从 `Cloud Scheduler -> authenticated Cloud Run` 改为 `Cloud Scheduler -> Workflows -> ashare-pipeline-control`。
> - 改道原因是 2026-06-08 live 验证里，`Scheduler -> authenticated Cloud Run` 持续命中 Cloud Run 鉴权层 `403`，而 `Workflows -> ashare-pipeline-control` 已有真实 smoke 成功证据。
> - 本次按 owner 要求只先收敛 PRD 和项目记忆/TODO，不改实现代码；下一步应单独提实现 PR。

## 当前交接摘要（2026-06-08）
- OQ-005 phase 1 foundation 仍保持已部署状态：`ashare-pipeline-control` Cloud Run service、`ashare_ods_ingestion_daily` 和 `ashare_warehouse_window_refresh` 两个 Workflows 已上线，既有 `qa_only` 与 `daily_current` smoke 继续作为当前 live 通过证据。
- `ashare_pipeline_alert_checker` 已按 owner 要求改为“最多每小时 1 次”：Composer 过渡态 DAG schedule 改为 `0 * * * *`，lookback 统一到 `70` 分钟，heartbeat 缺失告警窗口统一到 `120` 分钟；当前 PRD 层的 cutover 目标已从 `Cloud Scheduler + Cloud Run` 收敛为 `Cloud Scheduler -> Workflows -> ashare-pipeline-control`。实现前提已钉死为 Scheduler caller service account 拥有 `roles/workflows.invoker`、Workflows runtime service account 保留 `ashare-pipeline-control` 的 `roles/run.invoker`。
- `airflow_monitoring` 已确认是 Composer 平台托管健康监控 DAG，不能在仓库代码里单独降频；只要 Composer 环境还在，它就会继续按平台频率运行。要真正把这部分 run 和固定底座费用降掉，必须完成 OQ-005 cutover 并删除 Composer 环境。
- `ashare_warehouse_full_rebuild` 已推进为可部署的 manual workflow：`ashare-pipeline-control` 的 BigQuery task 已改成服务端 async `submit + poll`，workflow 也已切到异步轮询并部署为 revision `000001-36a`。本轮 direct async control-plane smoke 已成功（BigQuery job `fd1f6751-4861-4685-8377-e7dd9843ff57`），manual dry-run execution `cb8d1267-2909-4bf6-b725-29c6c8ee17e1` 也 succeeded；仍未执行真实全量 rebuild，因为那会重建整套 warehouse。
- `ashare-pipeline-control` 镜像现在会一起打包 `scripts/alerting`，避免 `service.py` 模块级导入 alert checker 时报 `ModuleNotFoundError` 导致整个控制面启动崩溃。后续启用 `Cloud Scheduler` alert checker 时，必须同时 pause / delete Composer DAG `ashare_pipeline_alert_checker`，避免双跑；在实现 PR 把 scheduler deploy 脚本改写为 Workflows Executions API 前，`orchestration/workflows/deploy_scheduler_jobs.sh` 视为 `superseded / do-not-run`。

# Agent 交接（Agent Handoff）

本文件保存供后续 Agent 使用的最新交接记录。新交接用 `templates/HANDOFF_TEMPLATE.md` 追加到底部，并同步刷新下面的「当前交接摘要」。

> **语言约定（2026-06-01 起）**：新增交接条目一律用中文撰写；下方此前的英文历史条目保留原样作为记录，不回译。

## 当前交接摘要

- **2026-06-08 GPT-5 Codex：PR #122 最新 re-review 已闭环。** `run_acceptance_gate_v3_replay_qa.py` 的 placeholder 渲染现已改回单次替换，`QA-V3-1` 不再把 hash sentinel 一起替掉；`24_qa_acceptance_gate_v3_replay_outputs.sql` 的 primary benchmark 断言也恢复成对固定 `000001.SH` 的真校验。按这版代码已重新真跑 replay 与 helper 驱动的 `24` QA，结果仍为 `25` 个候选里 `1 accepted / 24 rejected`，`24` QA 全部通过，最新 contract hash 为 `8a84447e8190290fef2ae61b71a31678bc02fffda52b5a4701be36593e1ea1ed`。
- **2026-06-08 GPT-5 Codex：`24` QA 剩余业务口径已继续收口到 v3 contract。** `run_acceptance_gate_v3_replay_qa.py` 现在会把 replay search scope、Top-K、benchmark 集合、窗口、signal/absolute gate 阈值、`final_holdout` trading-day 阈值和允许的 `score_orientation` 一并从 `model_acceptance_contract_v3.yml` 注入 `24_qa_acceptance_gate_v3_replay_outputs.sql`；contract 新增 `replay_scope` 后，QA 不再维护第二份 search scope 默认值。这轮没有再重跑 replay / `24` QA，目的是收口 PR #122 关于“contract 还不是完整唯一事实来源”的 review。
- **2026-06-08 GPT-5 Codex：`v3` replay 和 helper 驱动的 `24` QA 已真执行成功。** `replay_acceptance_gate_v3.py` 在最新 `model_acceptance_contract_v3.yml` 下结果仍为 `25` 个候选里 `1 accepted / 24 rejected`，contract hash 为 `6e6d77881e8ca8f437154be9bec9b4972e35140c0b2562e7732150e37b9e8418`。`run_acceptance_gate_v3_replay_qa.py` 也已成功驱动 `24_qa_acceptance_gate_v3_replay_outputs.sql` 全部通过；legacy valid-as-CV carve-out、`final_holdout=diagnostic_only` 和五指数公式锁定都已在真实 BigQuery 执行中验证。过程中补修了两个 SQL 实现问题：`nav_drawdown` 改为 `nav.nav AS nav`，`QA-V3-8` 对 `dwd_index_eod` 的 4 个 join 补了显式分区过滤。
- **2026-06-08 GPT-5 Codex：`24` QA 已改成 contract-driven helper 执行。** 新增 `scripts/strategy1/run_acceptance_gate_v3_replay_qa.py` 后，`24_qa_acceptance_gate_v3_replay_outputs.sql` 不再依赖手工在 SQL 顶部镜像 `contract_hash`、legacy replay carve-out 或 `final_holdout` enforcement；这些值都由 helper 从 `model_acceptance_contract_v3.yml` 注入，`sql/ml/strategy1/README.md` 也已改成通过 helper 跑 `24` QA。`replay_acceptance_gate_v3.py` 同时移除了 Python 常量里的 legacy search allowlist，统一从 contract 的 `replay_compatibility` 读取。
- **2026-06-08 GPT-5 Codex：`v3` final_holdout 已被 owner 降成 diagnostic-only。** `model_acceptance_contract_v3.yml` 现在显式声明 `final_holdout_gate.enforcement=diagnostic_only`；`final_holdout trading days >= 40` 保留为 replay artifact / QA 的诊断字段，但不再阻断 `v3` accepted / rejected。`replay_acceptance_gate_v3.py` 已新增 `final_holdout_gate_status`，`24_qa_acceptance_gate_v3_replay_outputs.sql` 的 `QA-V3-6` 也已同步改为只要求可计算。当前尚未按这条新口径重跑 replay / `24` QA。
- **2026-06-08 GPT-5 Codex：`v3` replay 已成功重跑，旧阻塞已定位到 final_holdout 历史覆盖缺口。** replay 结果未变，仍是 `25` 个候选里 `1 accepted / 24 rejected`。应用 legacy valid-as-CV fallback 后，`24` QA 已通过 `QA-V3-5`，说明历史字段缺口问题已被消化；当时剩余的 `QA-V3-6` 失败来自首轮 `sklearn_native_pvfq_n30_bw_h5_20260605_01` 的 5 个 historical selected row 在 `2026-01-05..2026-04-30` 没有任何 NAV 行，`final_holdout trading days = 0`。该问题现已被 owner 通过“final_holdout 非硬 veto”决策收口，后续只需按新口径重跑 replay / `24` QA。
- **2026-06-08 GPT-5 Codex：`v3` replay / `24` QA 已为首轮 sklearn native search 增加 legacy valid-as-CV 兼容口径。** `sklearn_native_pvfq_n30_bw_h5_20260605_01` 的 5 个 historical selected row 缺 `cv_confirmation_status` / `cv_*` 持久化字段时，不再直接判成不可算，而是用已持久化的 `valid_signal_status`、`valid_rank_ic`、`valid_top_minus_bottom_fwd_ret_mean` 作为兼容代理：`stable + valid_rank_ic>0 + valid_top_minus_bottom>0 => passed`，否则 `failed`。这条规则只对该首轮 native search 生效，不推广到后续 LightGBM / risk-feature 搜索。当前尚未重跑 replay / `24` QA，下一步先验证 `QA-V3-5` 是否已打通。
- **2026-06-08 GPT-5 Codex：PR #119 review follow-up 已把 `v3` replay fallback 再收口一轮。** `effective_test_metric` 现在对 `test_rank_ic_mean` 和 `test_top_minus_bottom_fwd_ret_mean` 统一走“有限 raw 值优先，否则 fallback”，避免 spread 字段遇到 `inf`/非有限 raw 值时把 fallback 吞掉。candidate artifact 也新增了 `cv_confirmation_status_from_fallback`、`test_rank_ic_from_fallback`、`test_top_minus_bottom_fwd_ret_from_fallback`，便于审计值来源；`24` QA 则把 `selected_registry -> backtest_summary` 改回 `LEFT JOIN`，继续显式暴露缺 summary 的 selected row。当前仍未重跑 replay / `24` QA。
- **2026-06-08 GPT-5 Codex：Strategy1 `v3` replay / `24` QA 已改为兼容历史 search 的信号字段缺口。** `replay_acceptance_gate_v3.py` 不再把历史 `cv_confirmation_status` / `test_rank_ic_mean` / `test_top_minus_bottom_fwd_ret_mean` 缺失当硬阻断，而是按 source-of-truth fallback 读取：`cv_confirmation_status` 用已有 `cv_rank_ic_mean` + `cv_top_minus_bottom_fwd_ret_mean`（以及存在时的 `cv_fold_count`）回推，`test_*` 则从 `ads_model_prediction_daily` + `ads_ml_training_panel_daily` 的 `test` 窗口按原 orchestrator 公式现算。`24_qa_acceptance_gate_v3_replay_outputs.sql` 已同步改成校验“字段存在或可由 source 推导”。本轮尚未重跑 replay / `24` QA，下一步先执行这两步。
- **2026-06-08 GPT-5 Codex：OQ-005 scheduled production cutover 与 Composer 下线均已完成。** `ashare-ods-ingestion-daily`（`0 20 * * *`）和 `ashare-pipeline-alert-checker`（`0 * * * *`）两个 scheduler 已 `ENABLED`，目标分别为 `ashare_ods_ingestion_daily` / `ashare_pipeline_alert_checker` workflows；真实 cutover 证据是 alert-checker execution `978c920c-3810-4299-b904-3c954e8d221d` succeeded，以及 ODS parent `31ac0d61-d40c-4a88-9865-b13f61d369c1` 和 child warehouse `919f2aba-b9d4-4181-9915-fa848487bb90` 均 succeeded。Composer 业务 DAG 已全部停用，`ashare-composer` 环境已删除，`gcloud composer environments describe ashare-composer --location=asia-east2` 返回 `NOT_FOUND`。后续只需补短观察窗记录。
- **2026-06-08 GPT-5 Codex：PR #112 review follow-up 已把不安全路径真正封住。** `Dockerfile.pipeline_control` 已补 `scripts/alerting` 到镜像，避免 `service.py` 模块级导入 `scripts.alerting.check_alerts` 时导致整个 `ashare-pipeline-control` 启动崩溃。`deploy_workflows.sh` 默认只部署 `ashare_ods_ingestion_daily` 和 `ashare_warehouse_window_refresh`；`ashare_warehouse_full_rebuild` 改为显式 `DEPLOY_FULL_REBUILD=true` 的 opt-in 路径，直到控制层 BigQuery 改成 async submit + poll 为止。README 也已补明：启用 `Cloud Scheduler` alert checker 时需同时 pause / delete Composer DAG `ashare_pipeline_alert_checker`，避免双跑。
- **2026-06-08 GPT-5 Codex：OQ-005 告警检查已统一限频到每小时。** `ashare_pipeline_alert_checker` 在 Composer 过渡态中的 schedule 已改为 `0 * * * *`，`check_alerts.py` lookback 调整为 `70` 分钟，heartbeat 缺失告警窗口调整为 `120` 分钟；cutover 后同一小时级口径将由 `Cloud Scheduler -> Workflows -> ashare-pipeline-control` 延续。注意：`main` 上现有 `orchestration/workflows/deploy_scheduler_jobs.sh` 仍是旧的直连 Cloud Run 版本，在实现 PR 改写为 Workflows Executions API 前视为 `superseded / do-not-run`。
- **2026-06-08 GPT-5 Codex：`airflow_monitoring` 不能在仓库内单独降频。** 已确认它是 Composer 平台托管健康监控 DAG；只要 Composer 环境存在，它就会继续按平台频率运行。停止这类 run 和固定 `standard milli DCU-hours` 费用的路径是完成 OQ-005 cutover 并删除 Composer 环境，而不是继续在 repo 中找调频开关。
- **2026-06-08 GPT-5 Codex：`ashare_warehouse_full_rebuild` 已补齐 async 控制面并完成 deploy + 低风险 smoke。** `scripts/pipeline_control/state.py` / `service.py` 已新增 BigQuery `submit + poll`，control service 已部署到 revision `ashare-pipeline-control-00004-b2g`，`ashare_warehouse_full_rebuild` 已部署为 workflow revision `000001-36a`。本轮 direct async control-plane smoke 成功轮询只读 QA job `fd1f6751-4861-4685-8377-e7dd9843ff57`，manual dry-run execution `cb8d1267-2909-4bf6-b725-29c6c8ee17e1` succeeded；同时，`backfill` execution `7cfbf799-1ace-4440-8577-95ddd45e7645` 和非交易日 skip execution `29121fdb-8452-4398-85f1-052708ac7cb7` 也都已 success。真实全量 rebuild 仍未执行，因为那会重建整套 warehouse。
- **2026-06-08 GPT-5 Codex：OQ-005 Workflows phase 1 foundation 已部署并通过最小 live smoke。** 已新增 `tests/pipeline_control/test_state_lock.py` 覆盖 `acquire -> generation lookup -> heartbeat -> release`，并本地跑通 `unittest`。GCP 侧已启用 `workflows.googleapis.com`、创建并授权 runtime service account、部署 `ashare-pipeline-control` Cloud Run service，以及 `ashare_ods_ingestion_daily` / `ashare_warehouse_window_refresh` 两个 Workflows。真实 `qa_only` execution `aaad21db-7c1a-4cb2-92fb-55158edfa3a3` 与 `daily_current` 父/子 executions `2085f593-0fe9-483c-8888-6fa48fe7bb2f` / `d305d8a3-99a1-4007-9fb2-94e3698ff55c` 已 success。live 部署同时暴露并修正了 Workflows `http.* timeout <= 1800s`、布尔参数比较、窗口 SQL 必须透传 `warehouse_mode` 等运行期契约问题。该阶段性基础设施随后已在同日扩展到 alert checker、full rebuild、Scheduler cutover 和 Composer 删除完成。 

- **2026-06-08 GPT-5 Codex：PR #108 comment follow-up 已把迁出 Composer PRD 加硬到实现级。** 已补 4 个 Workflows 易静默退化点：每个业务步骤都要显式写 `pipeline_task_status`，不能只写 start/finalize；`ashare_warehouse_window_refresh` 必须有显式分布式锁，不能假设存在 `max_active_runs=1`；生产 scheduled ingestion -> refresh 固定为同步 child workflow 调用，旧 `warehouse_refresh_missing` watchdog 只保留到迁移期；BigQuery / Cloud Run 调用按“提交 -> 轮询终态 -> 写状态”建模，并要求 Phase 1 先复核 Workflows 限额和 `full_rebuild` 是否要拆分。

- **2026-06-08 GPT-5 Codex：OQ-005 长期目标改为迁出 Composer。** 已新增 `docs/prd/PRD_20260608_01_OQ005调度完全迁出Composer.md`，明确当前 Composer 费用主体是常驻 `standard milli DCU-hours` 底座，而现有 DAG 主要只做编排。长期架构改为 `Cloud Scheduler + Cloud Workflows + Cloud Run Jobs + BigQuery SQL/Dataform`，`ashare_pipeline_alert_checker` 也走 `Cloud Scheduler -> Workflows -> ashare-pipeline-control`；当前 Composer DAG 拆分、window refresh、alert checker 和 smoke 只视为 cutover 前过渡态，目标是在迁移验收后删除 Composer 环境。

- **2026-06-08 GPT-5 Codex：策略 1 runner / acceptance 默认 benchmark 切到上证指数并完成独立 replay。** 已把 BigQuery SQL runner `08/09`、Cloud Run Python ledger、OQ-010 调度器默认 `p_benchmark`、v2 acceptance contract、报告渲染和相关 QA/诊断默认 benchmark 从 `000852.SH` 切到 `000001.SH`，并把 v2 诊断 artifact 与 live 搜索 acceptance 路径的主 benchmark 字段名统一为 `*_vs_primary_benchmark`。随后用新 ids `s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01` / `bt_s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01` 重跑 fixed-prediction lot-aware reference，不覆盖旧 `000852.SH` 审计结果；`10` 采用 fixed-prediction split override 手工补跑，`10/12/20/22/23` QA 已通过。新的 acceptance artifact `acceptance_gate_v2_lotaware_ref_bm000001_20260608_01` 仍为 `rejected`，原因是 `full_period_excess_return_vs_primary_benchmark<=-0.03` 与 `full_period_information_ratio<0.0`。

- **2026-06-08 GPT-5 Codex：index benchmark QA 日期上限修复。** PR #106 合并后的 Composer smoke 验证新增 `market_state_dws` / `market_state_checks` 成功，但后置 `qa_after_window.index_benchmark_checks` 因默认扫到 `CURRENT_DATE` 而在 2026-06-08 当天 000001.SH 未到数时误失败。新分支 `codex/fix-index-benchmark-qa-date-bound` 已将 `sql/qa/03_index_benchmark_checks.sql` 默认 `dwd_end_date` 改为 DWD 中 `000001.SH` 完整 price + dailybasic 可用的最新 SSE 开市日，并真实跑通 `03` QA。

- **2026-06-08 GPT-5 Codex：PR #106 comment follow-up。** 已按 review 修复 market-state 日更全表重建问题：新增 `sql/incremental/03_refresh_market_state_window.sql`，Composer `windowed_transform` 改为窗口 MERGE；`sql/dws/08_dws_market_state_daily.sql` 只保留初始化 / full rebuild。`market_state_v0_20260606` 的 `sse_composite_*` 字段改为 `NULL`，`market_state_v1_20260607` 才填充上证指数指标，`11_market_state_checks` 已补断言。ODS index external table URI SQL 改为由 `scripts/ingestion/generate_index_external_table_uris.py` 从 current-scope manifest 生成，可用 `--check` 防漂移。

- **2026-06-07 GPT-5 Codex：上证指数 `000001.SH` ODS/DIM/DWD/DWS 补齐。** 已把 `index_daily_000001_SH` / `index_dailybasic_000001_SH` 加入 current-scope manifest、ODS external table 显式 `sourceUris`、`dim_index` seed 和 `dwd_index_eod`；BigQuery 手工补数和 2019-01-01 至 2026-06-05 指数窗口 backfill 均完成，`03` / `05` / `12` QA 通过。后续按 owner 要求创建 `ashare_backup`，把修改前 `dws_market_state_daily` 备份为 `ashare_backup.dws_market_state_daily_v0`，生产 DWS 已重建为 `market_state_v0_20260606` 兼容行 + `market_state_v1_20260607` 上证指数字段行；本次不写 ADS，不改变 risk-off 触发逻辑。

- **2026-06-07 GPT-5 Codex：合并后分支 / worktree 清理约束扩展。** Owner 要求把已有分支卫生规则扩展到对应独立 `git worktree`：PR 合并后，若 owner 未要求保留，应删除已合并且不再使用的 `codex/*` 本地分支、对应远端分支，并移除为该分支创建的独立 worktree；若 worktree 仍有未提交或未合并改动，先暂停并请 owner 决策，不得强删。

- **2026-06-07 GPT-5 Codex：Strategy1 风险特征 wave 4 Cloud Run 真实执行完成。** 在 `main=10cbd46c1524888d03c71c643ed7959eb1c998be` 基线上构建/部署 runner `riskfeatfix-10cbd46-20260607-04`（digest `sha256:e7d6c5e3c86293046166b8930f6016256fb6f43a46d02be54552b303fc9a6ada`），binary 与 regression 两条风险特征 manifest 均完成 20/20 candidate fanout、Top5 backtest/report、`19` QA、`21` QA；两条 Top5 均被 acceptance contract 拒绝，未产生 accepted baseline。Runtime 修复已并入 PR #103，并已同步到 `main`。

**OQ-010 风险特征入模 PR #102 review follow-up（2026-06-07）**：工作树 `/Users/luna/Desktop/git/quant-ashare-risk-feature-impl`，分支 `codex/implement-risk-feature-search`。已按 PR #102 comment 修复两项：风险专项 `max_drawdown >= -18%` 目标不再由 Python 常量 / SQL 默认值硬编码，而是写入 `configs/strategy1/model_acceptance_contract_v1.yml` 的 `thresholds.min_full_period_max_drawdown` 并由 `acceptance.py` 统一输出 `p_risk_feature_max_drawdown_target`；`21_qa_risk_feature_search_outputs.sql` 默认改为 `NULL` 并新增 `QA-RISK-0`，未注入 contract 参数的 standalone 真执行会 fail-loud。`final_holdout_status` 派生逻辑已移入共享 `acceptance.py`，orchestrator 删除重复函数。验证通过 Python `py_compile`、v1 contract 参数确认、原始/注入版 `21` QA BigQuery dry-run、risk feature orchestrator dry-run 和 `git diff --check`。尚未真实跑 Cloud Run 40 候选 / Top5 回测。

**OQ-010 风险特征入模第 4 波实现（2026-06-07）**：工作树 `/Users/luna/Desktop/git/quant-ashare-risk-feature-impl`，分支 `codex/implement-risk-feature-search`。已实现 `strategy1_pv_fin_risk_v0_20260606` 训练路径：新增 95 列 feature set 契约、Cloud Run 专用训练面板 SQL、binary/regression 各 20 候选 manifest、矩阵 `feature_delta_vs_base.json`、feature schema hash、风险/市场特征缺失率、LightGBM feature importance、风险专项 acceptance overlay 和 `sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`。验证已通过 Python 编译、manifest/orchestrator/prepare_matrix dry-run、训练面板 SQL 与 `21` QA BigQuery dry-run、feature_column_list 顺序一致性检查和 `git diff --check`。尚未执行真实 Cloud Run 40 候选训练 / Top5 回测，未建立 baseline；合并后下一步是构建/部署 runner 镜像，依次跑 binary 20 与 regression 20，并用 `19` + `21` QA 收口。

**OQ-010 整数手交易执行收口（2026-06-07）**：PR #100 已合并，PR #101 已修复 portfolio-only 报告/诊断的 `prediction_run_id` 透传并合并；临时分支/工作树已清理。镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:lotaware-c018ef5-20260607-01` 已构建并部署到 `strategy1-backtest-report-job`。Cloud Run execution `strategy1-backtest-report-job-h7vtl` 成功完成 fixed-prediction lot-aware reference：`run_id=s1_lotaware_ref_pvfq_n30_bw_h5_20260606_01`、`backtest_id=bt_s1_lotaware_ref_pvfq_n30_bw_h5_20260606_01`、`prediction_run_id=s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01`，覆盖 `2024-01-02` 至 `2026-04-30`，`ledger_version=ledger_exec_v1_lot100`。结果：total_return 35.17%、excess_return -7.20pct vs `000852.SH`、Sharpe 0.872、max_drawdown -13.59%；report、model diagnosis、tail-risk artifact 和 acceptance gate v2 artifact 均 uploaded。`10`/`12`/`20` 在 Cloud Run 内通过，手工复核 `22`/`23` 通过。acceptance gate v2 diagnosis `acceptance_gate_v2_lotaware_ref_20260607_01` 仍为 `rejected`，原因是全期跑输中证1000超过 3pct、IR 为负、2026 final_holdout 跑输中证1000 12.75pct。当前可进入下一模型族 / 风险特征训练路线。

**OQ-010 验收门 v2 实现（2026-06-06）**：PR #98 已合并；实现工作树 `/Users/luna/Desktop/git/quant-ashare-acceptance-gate-v2-impl`、分支 `codex/implement-acceptance-gate-v2` 的 v2 契约、只读诊断脚本和 `22` QA 已进入 `main`。已新增 `configs/strategy1/model_acceptance_contract_v2.yml`、只读脚本 `scripts/strategy1/diagnose_acceptance_gate_v2.py` 和 `sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`，并扩展 `scripts/strategy1_cloudrun/acceptance.py` 支持 contract hash / v2 SQL 参数。诊断脚本只读 ADS/DWD/DWS，不训练、不改 prediction、不写 ADS；默认 reference run/backtest 为 `s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01`，输出 `acceptance_gate_v2/` artifact、10/20/30/40 组合可行性、eligible benchmark、score orientation audit、低价股偏移、现金/实际持仓和风格暴露诊断。uploaded 模式成功，GCS URI：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/acceptance_gate_v2/diagnosis_id=acceptance_gate_v2_reference_20260606_01`，16 个对象；`22_qa_acceptance_gate_v2_outputs.sql` 注入真实 contract hash 后真实执行 9 个 ASSERT 全部通过，默认 standalone placeholder 已改为在 `QA-V2-1` fail-loud。当前 v2 结论：reference run 为 `rejected`，原因是跑输 `000852.SH`、full-period IR 为负、2026 final_holdout 严重跑输；拒绝范围仅限当前 top-30 long-only 实现，不否定信号家族。`10/5%` 是 `diagnostic_only`，`20/30/40` 因局部现金峰值为 `needs_more_evidence`，没有 implementation hard fail。后续已转为先实现整数手 lot-aware ledger。

**OQ-010 风险特征入模 Phase B0 实现（2026-06-06）**：PR #94 已合并；工作树 `/Users/luna/Desktop/git/quant-ashare-risk-feature-impl`，分支 `codex/implement-risk-feature-acceptance-diagnosis`。新增 `scripts/strategy1/diagnose_acceptance_window.py`，用于 PRD Phase B0 只读诊断：读取既有 ADS / artifact，重切 BQML historical reference 的 2025-only 指标，并汇总 sklearn native、LightGBM binary、LightGBM regression 三波已拒 Python Top5 候选；不训练模型、不重跑 BQML、不执行 `sql/ml/strategy1` SQL runner、不写 ADS。PR #96 review follow-up 已统一 maxDD 门口径：2025 excess 仍看 2025 段，风险 maxDD 门使用 full-period summary，报告同时展示 test maxDD 与 full maxDD。uploaded 模式已成功，artifact URI 为 `gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/acceptance_window_diagnosis/diagnosis_id=riskfeat_acceptance_window_20260606_01`。诊断结论 `primary_blocker=mixed_evidence`：BQML historical reference 2025-only excess -23.43%、test maxDD -10.06%、full-period maxDD -14.48%；15 个 Python 候选中 10 个 2025 excess 未过、5 个 full-period maxDD 未过，same-side fraction 66.67% 低于 80% 阈值。后续不应自动启动第 4 波风险特征训练，应先由 owner / 审查者复核诊断结论。

**OQ-010 风险特征入模 PRD（2026-06-06）**：工作树 `/Users/luna/Desktop/git/quant-ashare-risk-feature-prd`，分支 `codex/prd-strategy1-risk-feature-baseline`，PR #94。新增 `docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md`，承接 PRD04 LightGBM binary/regression 均 rejected、尾部风险 P1 轻度改善但仍跑输、P2 v0 `skip_new_buys` 降收益且未改善回撤的事实。PRD 将下一步收敛为风险特征入模：新增 `feature_set_id=strategy1_pv_fin_risk_v0_20260606`，把个股尾部风险字段、`dws_market_state_daily` 市场状态字段和风险 flag 纳入 Cloud Run frozen matrix；P0 固定 `diagnostic_only`、40 候选 / 20 并发 / 2 vCPU 8Gi、LightGBM binary + regression、共享 acceptance contract；P1 才评估 `risk_score_penalty_v0` 候选风险评分。PR #94 review follow-up 已补 `test_reuse_wave_no=4` / final_holdout passed 要求、训练前只读 `acceptance_window_diagnosis`、`feature_delta_vs_base.json`、market-state 贡献展示，以及风险专项 accepted 目标 `max_drawdown >= -18%`。本次只写 PRD 和记忆/TODO，未改代码、未运行 BigQuery / Cloud Run。

**OQ-010 尾部风险 P2 market risk-off 实跑结论（2026-06-06）**：PR #92 已合并；`dws_market_state_daily` 已物化并通过 `sql/qa/11_market_state_checks.sql`（562 行，risk-off 91 日）。已构建/部署 runner 镜像 `tailrisk-p2-6db6bd9-20260606-01`，并用 `configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml` 并发跑完 diagnostic-only、`market_risk_off_v0`、`individual_and_market_risk_guard_v0` 三条 portfolio-only A/B。结果：diagnostic-only total_return 38.25%、Sharpe 0.882、max_drawdown -14.46%；market-only total_return 28.20%、Sharpe 0.734、max_drawdown -15.72%，market skip 217 笔；combo total_return 30.04%、Sharpe 0.773、max_drawdown -14.71%，market skip 217 笔、tail-risk skip 3 笔。三条 report / model diagnosis / tail-risk diagnosis / `10` / `12` / `20` 均 succeeded 并上传 GCS。结论：P2 v0 `skip_new_buys` 降低仓位但未改善回撤且显著拖累收益，不采纳为默认策略；后续若继续市场风控，应另写 v1 风险动作/阈值。

**OQ-005 调度运行稳定命名生产 cutover + PR #93 部署（2026-06-06）**：PR #91 已完成生产 cutover：Composer bucket `data/sql/`、新 DAG / alert checker 和 `check_alerts.py` 已同步；旧 `oq005_alert_checker.py`、旧命名 QA/metadata SQL 和旧 `oq005_*` log metrics 已清理；`ashare_pipeline_alert_checker` active，`ashare_ods_ingestion_daily` unpaused，旧 `ashare_daily_pipeline_v0` paused。PR #93 已合并并部署：`ashare_common.py`、`ashare_ods_ingestion_daily.py` 和 `sql/observability/01_pipeline_status_views.sql` 已同步到 Composer bucket / BigQuery。ODS-only skip smoke `manual_pr93_ods_only_skip_20260605_20260606_01` 成功，Cloud Run ingestion tasks skipped，`trigger_warehouse_window_refresh` skipped，`skip_downstream_refresh` 在 `pipeline_task_status` 中为 `skipped`，无 linked warehouse run，`v_pipeline_refresh_missing` / `v_alert_summary` / `check_alerts.py --lookback-minutes 20 --json` 均为空。后续只剩新 DAG 至少两个开市日 scheduled run 和一个真实非交易日 scheduled skip 自然观察，以及 Dataform 生产接入 / shadow 验证。

**Dataform definitions 与调度运行命名清理（2026-06-06）**：工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-dataform-definitions`，分支 `codex/oq005-dataform-definitions`，PR #91。已新增 Dataform 首版 `workflow_settings.yaml`、`action_manifest.json`、生成器 `scripts/dataform/generate_sqlx_from_sql.py` 和 45 个 `definitions/**/*.sqlx`，以 canonical `sql/` 生成 31 个 Dataform operations；`npx --yes @dataform/cli compile dataform` 通过。按 owner 要求清理调度运行代码中的阶段性命名：告警 DAG 文件改为 `ashare_pipeline_alert_checker.py`，QA/metadata SQL 改为 `01_core_smoke_checks.sql`、`03_index_benchmark_checks.sql`、`05_unit_contract_checks.sql`、`01_core_table_column_descriptions.sql`，Composer task_id / Dataform action/tag 改为 `core_*`、`index_benchmark_checks`、`unit_contract_checks`、`qa_core`、`qa_contract` 等稳定命名。PR #91 review follow-up 已补运行命名 cutover runbook、Dataform `--check` 防漂移检查和“线上旧名 vs 目标新名”记忆说明；运行命名已在后续 cutover 中成为线上事实。Dataform definitions 尚未接入 Dataform 生产 / shadow。

**OQ-010 尾部风险 P1 comment follow-up（2026-06-06）**：工作树 `/Users/luna/Desktop/git/quant-ashare-tail-risk-p1`，分支 `codex/implement-tail-risk-p1`，PR #88 已 rebase 到最新 `origin/main` 并按 review comment 修正。最新语义：`05_build_candidates.sql` 只写 `tail_risk:*` 风险标记，不把风险标记股票从 TopN / target 剔除；必需风险字段 NULL 记为 `tail_risk_required_field_null`。Python Ledger v1 与 BigQuery SQL fallback 均新增 `BUY_SKIPPED_TAIL_RISK`：未持仓风险目标跳过新买入，已有持仓不因 P1 标记被强制卖出。`10` / `20` QA 已改为验证未持仓风险目标无真实买入成交且留下 skip 状态。验证：Python `py_compile`、`05/08/09/10/11/20` dry-run 均通过；短区间 smoke 因跳过报告触发 `10` report guard 失败，已确认是 smoke 参数问题并清理临时 ADS 残留为 0。另已在 `KNOWN_CONSTRAINTS.md` 写入 BigQuery 分区表查询/删除/更新必须显式带分区列过滤的项目硬约束。

**OQ-005 warehouse refresh 补跑/resume helper（2026-06-06）**：工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-backfill-resume`，分支 `codex/oq005-backfill-resume`，PR #90。新增通用脚本 `scripts/pipeline/run_warehouse_refresh.py`（文件名不绑定 OQ 编号），支持 `backfill` 分块计划、`qa-only` 计划、`status` 查询、显式 `--execute` 触发 Composer、`--wait --fail-fast` 等待 terminal 状态，以及 `--resume` 按 `ashare_meta.pipeline_run` 精确跳过同一 `warehouse_mode/date_from/date_to` 已 `success` 或 `running` 的窗口。PR #90 review follow-up 已补 `--max-execute-runs` 默认 20 个非 skipped run 的执行上限，超过需缩小日期范围或显式 `--yes`。Composer README 与 OQ-005 runbook 已补脚本入口和手工 `gcloud` fallback。本次只做本地 plan/静态验证，不触发 Composer、不运行 BigQuery DML、不部署生产。按 owner 要求，`KNOWN_CONSTRAINTS.md` 已写入“需要代码在工作树中改，改完推 PR。”

**OQ-005 alert setup review follow-up（2026-06-06）**：分支 `codex/oq005-alert-logmetric-alreadyexists`。针对 `fd8aefe` review 的 Low finding，`scripts/alerting/setup_alerts.py` 已将 log metric 已存在的幂等判断从异常 message substring 改为显式捕获 `google.api_core.exceptions.AlreadyExists`，其他异常仍 fail-fast。该分支只改告警配置脚本和记忆，不改 Composer DAG、BigQuery SQL 或生产调度状态；验证为 `python3 -m py_compile scripts/alerting/setup_alerts.py` 和 `git diff --check`。

## 交接条目

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: main-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: oq005-composer-delete-and-memory-closeout-20260608
相关 issue/PR: N/A

### 已完成工作

- 已完成 `ashare-composer` 环境删除；当前 `gcloud composer environments describe ashare-composer --location=asia-east2` 返回 `NOT_FOUND`。
- 把 OQ-005 的仓库记忆从“待 cutover”收口到“scheduled production cutover 已完成、Composer 业务 DAG 已停用、Composer 环境已删除、仅剩短观察窗”的状态。
- 在 `DECISION_LOG.md` 追加持久决策：生产业务调度正式切到 `Cloud Scheduler + Cloud Workflows`。

### 重要上下文

- 现在生产 daily / hourly 业务调度事实来源已经不是 Composer，而是两个 Scheduler job：
  - `ashare-ods-ingestion-daily` -> `ashare_ods_ingestion_daily`
  - `ashare-pipeline-alert-checker` -> `ashare_pipeline_alert_checker`
- Composer 业务 DAG 即使还存在于仓库或历史 bucket 中，也不再是生产入口；后续如果有人想“临时恢复” Composer 跑业务，应视为违背当前架构决策。
- 这次没有新建 PR，也没有提交 git；只是更新本地记忆/TODO 并执行真实 GCP 环境删除。

### 改动文件

- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `gcloud scheduler jobs describe ashare-ods-ingestion-daily --location=asia-east2`
- `gcloud scheduler jobs describe ashare-pipeline-alert-checker --location=asia-east2`
- `gcloud composer environments describe ashare-composer --location=asia-east2`
- 已确认两个 scheduler job 当前均为 `ENABLED`
- 已确认 `gcloud composer environments describe ashare-composer --location=asia-east2` 返回 `NOT_FOUND`

### 阻塞项

- 无

### 下一步建议

- 保留一个很短的 post-cutover 观察记录即可，不需要再把 OQ-005 当设计问题继续拉长。

### 已更新记忆文件

- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: main-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: strategy1-benchmark-default-switch-20260608
相关 issue/PR: N/A

### 已完成工作

- 把策略 1 runner / acceptance 的默认 benchmark 从 `000852.SH` 切到 `000001.SH`。
- 更新 BigQuery SQL runner `08/09`、Cloud Run Python ledger、OQ-010 调度器默认 `p_benchmark`、v2 acceptance contract、报告渲染默认评估主基准、runner/benchmark QA 默认断言与诊断默认参数。
- 把 v2 acceptance 诊断 artifact 中主 benchmark 相关字段名从 `*_vs_000852` 改成 `*_vs_primary_benchmark`，避免在默认 benchmark 切换后继续输出误导字段名。

### 重要上下文

- 这次只改了默认值和直接耦合的 QA/报告/诊断口径，没有重跑任何 Cloud Run / BigQuery 历史 reference，也没有改历史 PRD 对 `000852.SH` 的叙述。
- 现有已落库的 historical summary / report / diagnosis / acceptance artifact 仍然是相对 `000852.SH` 的审计结果；如果要正式启用新默认值，下一步必须先做 reference / acceptance replay。

### 改动文件

- `configs/strategy1/model_acceptance_contract_v2.yml`
- `scripts/strategy1_cloudrun/ledger.py`
- `scripts/strategy1/run_oq010_experiments.py`
- `scripts/strategy1/render_report.py`
- `scripts/strategy1/analyze_tail_risk.py`
- `scripts/strategy1/diagnose_acceptance_window.py`
- `scripts/strategy1/diagnose_acceptance_gate_v2.py`
- `scripts/strategy1/diagnose_model_quality.py`
- `sql/ml/strategy1/08_run_backtest.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/11_model_quality_diagnostics.sql`
- `sql/qa/03_index_benchmark_checks.sql`
- `sql/ml/strategy1/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

### 测试 / 验证

- 未运行 Cloud Run / BigQuery runner。
- 未重跑 `03` / `10` / `19` / `22` QA。
- 本次为默认值与口径切换，后续需要 replay 验证历史 reference / acceptance artifact。

### 阻塞项

- 无硬阻塞。

### 下一步建议

- 先用 `000001.SH` 重跑 fixed reference / acceptance replay，确认 summary、report、diagnosis 与 gate artifact 全部换到新主 benchmark。
- 再决定是否把 v1/v2 contract / QA 内部仍沿用的 `*_vs_000852` 阈值键名做兼容重命名。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: workflows-smoke-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: oq005-workflows-smoke-20260608
相关 issue/PR: 待创建 PR

### 已完成工作

- 新增 `tests/pipeline_control/test_state_lock.py`，用 mock GCS 覆盖 `acquire -> lock_generation_for_owner -> heartbeat -> release` 的最小锁契约，并本地跑通 `unittest`。
- 已启用 `workflows.googleapis.com`，创建/授权 `ashare-workflows-runtime@data-aquarium.iam.gserviceaccount.com`，并部署 `ashare-pipeline-control` Cloud Run service 与 `ashare_ods_ingestion_daily` / `ashare_warehouse_window_refresh` 两个 Workflows。
- 为通过真实部署补了 3 处关键 Workflow 修正：BigQuery control call `timeout` 从 `3300` 收敛到 Workflows 上限 `1800`；所有布尔条件改为按布尔值判断，不再和 `"true"` 字符串比较；`index_dwd_window`、`stock_dwd_dws_window`、`market_state_dws` 与 `windowed_stock_refresh_checks` 统一透传 `warehouse_mode`。
- 真实 `qa_only` smoke 已成功：`ashare_warehouse_window_refresh` execution `aaad21db-7c1a-4cb2-92fb-55158edfa3a3`，`business_date=date_to=2026-06-05`、`warehouse_mode=qa_only`。
- 真实 `daily_current` smoke 已成功：父 workflow execution `2085f593-0fe9-483c-8888-6fa48fe7bb2f`，子 workflow execution `d305d8a3-99a1-4007-9fb2-94e3698ff55c`；child 内 `index_dwd_window`、`stock_dwd_dws_window`、`market_state_dws`、`core_smoke_checks`、`index_benchmark_checks`、`finance_caliber_checks`、`unit_contract_checks`、`pipeline_finalize_status`、`finish` 全部 success。

### 重要上下文

- 本轮验证的是 OQ-005 phase 1 foundation，不是生产 cutover。Composer 仍是生产调度入口；Workflows 现在只是并行存在且已证明主链路可跑通。
- 这次暴露的错误几乎都属于运行期接线/类型问题：`http timeout`、bool 判断、参数透传、锁兼容路径。`py_compile` 抓不到，后续做 `full_rebuild` / Scheduler / cutover 前仍应继续坚持“本地最小集成测试 + 真实 smoke”这套门。
- `ashare_warehouse_full_rebuild`、`ashare_pipeline_alert_checker`、Cloud Scheduler / IAM bootstrap 还没迁完；`backfill` 和非交易日 skip 的 Workflows smoke 也还没补。

### 改动文件

- `tests/pipeline_control/test_state_lock.py`
- `orchestration/workflows/ashare_ods_ingestion_daily.yaml`
- `orchestration/workflows/ashare_warehouse_window_refresh.yaml`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m unittest discover -s tests/pipeline_control -p 'test_state_lock.py'`
- `ashare_warehouse_window_refresh` `qa_only` execution `aaad21db-7c1a-4cb2-92fb-55158edfa3a3` succeeded
- `ashare_ods_ingestion_daily` `daily_current` execution `2085f593-0fe9-483c-8888-6fa48fe7bb2f` succeeded
- child `ashare_warehouse_window_refresh` execution `d305d8a3-99a1-4007-9fb2-94e3698ff55c` succeeded

### 阻塞项

- 无硬阻塞。

### 下一步建议

- 迁移 `ashare_warehouse_full_rebuild` 到 Workflows，并保持显式状态写回、同步终态轮询和锁语义。
- 迁移 `ashare_pipeline_alert_checker` 到 `Cloud Scheduler + Cloud Run`。
- 补 `backfill` 与非交易日 skip 的 Workflows smoke，再接入 Cloud Scheduler / IAM bootstrap，进入 shadow run 与最终 cutover。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: composer-exit-next-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: pr112-review-followup-20260608
相关 issue/PR: PR #112

### 已完成工作

- 修复 `ashare-pipeline-control` 镜像启动崩溃风险：`Dockerfile.pipeline_control` 现已打包 `scripts/alerting`，使 `service.py` 的 alert-check 模块级导入可在运行镜像中解析。
- 把 `ashare_warehouse_full_rebuild` 从标准 `deploy_workflows.sh` 路径移出，改成显式 `DEPLOY_FULL_REBUILD=true` 的 opt-in 部署。
- 更新 `orchestration/workflows/README.md`，明确 full rebuild 仍未 deployment-ready，且启用 `Cloud Scheduler` alert-check 时必须同步 pause / delete Composer DAG `ashare_pipeline_alert_checker`。

### 重要上下文

- 这轮是 review follow-up，没有新增部署或 smoke。
- full rebuild 现在虽然仍存在 workflow 文件，但默认部署脚本不会再把它注册到 GCP；这样“code-only”不再只是文档声明，而是代码层的真实约束。
- alert checker 双跑问题当前靠部署约束解决，不靠运行时去重。

### 改动文件

- `orchestration/workflows/Dockerfile.pipeline_control`
- `orchestration/workflows/deploy_workflows.sh`
- `orchestration/workflows/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未运行新的本地测试。
- 未部署新的 Cloud Run / Workflows / Cloud Scheduler。

### 阻塞项

- `ashare_warehouse_full_rebuild` 的核心阻塞不变：控制层 BigQuery 仍同步 `job.result()`，未解决前不应投入生产。

### 下一步建议

- 若继续收口 PR #112，优先看是否还需要把“pause Composer checker”写进实际 cutover runbook / deploy script 输出。
- 后续继续做 full rebuild 时，先实现 async submit + poll，或把 workflow 继续拆成可稳定落在 step 时限内的更小单元。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

**OQ-005 Composer DAG 拆分生产切换（2026-06-06）**：PR #86 已合并并完成 Composer 部署 / smoke。已应用 meta DDL 与观测视图，部署 `ashare_common.py`、`ashare_ods_ingestion_daily.py`、`ashare_warehouse_window_refresh.py`、`ashare_warehouse_full_rebuild.py` 和仓库 `sql/` 到 Composer bucket。旧 `ashare_daily_pipeline_v0` 已暂停，新 scheduled DAG `ashare_ods_ingestion_daily` 已 unpause；`ashare_warehouse_window_refresh` 与 `ashare_warehouse_full_rebuild` 无 schedule。`setup_alerts.py` 已补真实 GCP apply 兼容修复，`ashare_pipeline_warehouse_refresh_missing` metric 与 `Ashare Pipeline: Warehouse Refresh Missing` policy 已创建 / 对齐。Smoke：`manual_split_skip_gate_20260606_01` 非交易日 gate 成功且 Cloud Run 未触发；`manual_split_qa_only_20260605_01` 5 个 QA success；`manual_split_backfill_20260605_01` 1 日窗口刷新和全部 QA success；refresh-missing synthetic transaction smoke 通过；`check_alerts.py --lookback-minutes 20` 返回空。后续只剩新 DAG 至少两个开市日 scheduled run 和一个真实非交易日 scheduled skip 自然观察，以及 Dataform 生产接入 / shadow 验证、完整 ODS→ADS 运维观测闭环和后续自然 scheduled 观察。

**OQ-010 尾部风险 P0/P1/P2 当前版收口（2026-06-06）**：PR #84（`docs/prd/PRD_20260606_01_策略1尾部风险控制.md`）已合并，P0 固定最大回撤诊断已由 PR #87 实现并通过真实 `20` QA；P1 个股硬风险过滤 profile A/B 已完成，`individual_risk_guard_v0` 对回撤有轻度改善但仍跑输中证1000；P2 market risk-off 已由 PR #92 合并、物化 DWS 并完成 A/B。当前可复用的事实链路是 `tail_risk/` artifact、`20_qa_tail_risk_outputs.sql` 和 P1/P2 A/B 结果；当前不应把 P2 v0 `skip_new_buys` 设为默认策略。

**OQ-005 Composer DAG 拆分 PRD（2026-06-06）**：工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-dag-split-prd`，分支 `codex/oq005-dag-split-prd`。新增 `docs/prd/PRD_20260606_02_OQ005ComposerDAG拆分.md`，定义将当前 `ashare_daily_pipeline_v0` 拆成 `ashare_ods_ingestion_daily`、`ashare_warehouse_window_refresh`、`ashare_warehouse_full_rebuild`、`ashare_research_model_experiment`、`ashare_research_model_fanout`，`ashare_pipeline_alert_checker` 继续独立。本次只写 PRD 和记忆/TODO，不改 DAG、不部署 Composer、不运行 BigQuery / Dataform / Cloud Run。后续建议先实现 production DAG 拆分 Phase B/C/D：抽共享 helper，新增 ingestion daily DAG 与 warehouse window refresh DAG，完成开市日、非交易日和 backfill smoke 后再继续 Dataform 生产接入 / shadow 验证 / resume 自动化。

**OQ-010 PRD04 Wave 3 执行收口（2026-06-06）**：工作树 `/Users/luna/Desktop/git/quant-ashare-prd04-wave3`，分支 `codex/fix-prd04-prepare-matrix-parallelism`，PR #82。PR #79 合并后已部署 Cloud Run runner；本分支修复 `prepare_matrix()` requested parallelism 作用域 bug，并补 BigQuery JSON sanitizer，避免 regression `roc_auc/log_loss` 的 NaN 写入非法 `metrics_json`；PR #82 review follow-up 已补 `NaT` / `pd.NA` / `NaN` / `inf` 转 `null`、`np.ndarray` / pandas 标量递归转换和 `default=str` 兜底，并把状态表 `params_json`、GCS lock payload、work-unit manifest/hash 等 runner JSON 路径统一到 strict helper。最终镜像 `prd04-7d8daec-20260606-01` 已构建并部署到五个策略 Cloud Run Jobs。Wave 3 `cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01` 已完成：12 个 regression 候选、Top5 回测/报告/诊断和 `19` QA 全部通过，Top5 全部 rejected，当前仍不建立 `cloud_run_python_baseline_v1`。后续建议进入 PRD04 下一模型族 / 特征增强路线，或先分析回撤过大原因。

**OQ-005 非交易日 skip gate 已部署验收（2026-06-06）**：PR #83 已合并到 `main`（`3723f52`），`ashare_daily_pipeline_v0.py` 已同步到 Composer bucket `gs://asia-east2-ashare-composer-b2629133-bucket/dags/`，本地与 bucket SHA256 均为 `e4b07ba402716b914bfbd6fe27fa38f97fab8e1c12f6a0bcce9e5fd8c58696af`。`manual_smoke_skip_non_trading_day_pr83_20260606_02` 使用 `business_date=2026-06-06`、`warehouse_mode=daily_current`、`force_non_trading_day_gate=true`、`pipeline_dry_run=true` 成功：`non_trading_day_gate=success`、`skip_non_trading_day=success`，`pipeline_task_status` 写入 `skip_non_trading_day status='skipped'`，ingestion/readiness/transform 全部 skipped，Cloud Run 最新 execution 仍为 01:53 的旧 PR #80 run，未被 smoke 触发。DAG 当前 active/unpaused、无 import errors。首次 smoke `manual_smoke_skip_non_trading_day_pr83_20260606_01` 在 Composer 新旧 serialized DAG 切换窗口内走到旧路径，已中止、确认未触发 Cloud Run，并在 `pipeline_run` 标为 `partial` 防止假告警；`v_alert_summary` 对两次 smoke 为空。

**OQ-005 PR #83 记忆一致性 follow-up（2026-06-06）**：PR #83 review comment `4637354942` 指出 `IMPLEMENTATION_STATUS.md` 已完成区仍残留旧的部署等待状态。已将相关 durable bullet 改为“后续已由 PR #80/PR #83 部署与 smoke 覆盖”，并把几条历史补充明确标为部署前状态，避免同一记忆文件内当前状态自相矛盾。

## 交接条目

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: main-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: pr109_comment_followup_primary_benchmark_fields_20260608
相关 issue/PR: PR #109

### 已完成工作

- 处理 PR #109 的 P2 comment：补齐 live 搜索 acceptance 路径的 benchmark 输出字段命名。
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py` 不再输出 `test_year_excess_return_vs_000852`、`overall_excess_return_vs_000852`、`final_holdout_excess_return_vs_000852`，统一改为 `*_vs_primary_benchmark`。
- `scripts/strategy1_cloudrun/acceptance.py` 读取时优先使用新字段名，并兼容回退旧字段名与通用字段，保持阈值键 `*_vs_000852` 暂不重命名的兼容策略。

### 重要上下文

- 本次只修正 live 搜索 acceptance 的输出字段名，不改阈值键名，不改 benchmark 数值逻辑。
- 目的不是改计算口径，而是避免 benchmark 已切到 `000001.SH` 后，registry / comparison artifact 继续写 `*_vs_000852` 的误导命名。
- v2 diagnosis 路径和 live 搜索 acceptance 路径现在都统一到 `*_vs_primary_benchmark` 输出命名。

### 改动文件

- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1_cloudrun/acceptance.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未运行新的 Cloud Run / BigQuery replay。
- 本次是 PR comment follow-up 的命名一致性修复，未改数值计算逻辑。

### 阻塞项

- 无。

### 下一步建议

- 把本次 follow-up 追加到 PR #109。
- 如果后续要彻底清理 benchmark 历史命名债，再单独重构 contract / QA 内部阈值键 `*_vs_000852`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-12 GPT-5.5 - PR #201 pre-merge rebase after PR #202

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-prd03`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/prd03-memory-archive`
Run ID: N/A
相关 issue/PR: PR #201；PR #202；PRD_20260612_03

### 已完成工作

- 将 `codex/prd03-memory-archive` rebase 到 `origin/main@a5ca9e5`（PR #202 已合并）。
- 按 PRD_03 滚动结构处置 #202 新记忆内容：`IMPLEMENTATION_STATUS.md` 按小节日期重切最近 7 条，`AGENT_HANDOFF.md` 保留当前条目 + PR #202 两条交接，超出条目按月归档。
- 保留 #202 在 `KNOWN_CONSTRAINTS.md` 新增的 dividend 过渡政策条款；`TODO.md` 中 PRD_20260612_04 工程护栏完成项和 dividend backfill 待办继承自 `main`。

### 重要上下文

- 本轮只做合并前 rebase、记忆滚动归档和验证，不修改 resolver 代码，不执行 BigQuery/GCS 写入，不触碰 Cloud Run job spec/镜像/IAM。
- PR #202 F1 数据缺口仍留 owner 决策：现存 CA-on baseline 的 dividend 数据缺口为 `2026-05-28..2026-06-09`，补采与 baseline 复核不在 PR #201 范围。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`

### 测试 / 验证

- DECISION id 集合对账：before=`99`、after main index=`99`、missing=`0`、extra=`0`。
- 决策全文归档按 ID 对账：before=`99`、archive=`99`、missing=`0`、extra=`0`、text_mismatches=`0`。
- `IMPLEMENTATION_STATUS.md` 编年史对账：before=`75`、after main=`7`、archive=`68`、total=`75`，heading multiset match=`True`，nonblank body line multiset match=`True`。
- PRD_10 / PR #189 小节边界仍保持 review 修复：PRD_10 moved bullets=`5`，PR #189 bullets=`4`。
- Handoff 滚动对账：origin/main entries=`35`、after main entries=`3`、origin entries missing=`0`；PRD_03 实现 handoff 已归档。
- #202 记忆继承检查：`KNOWN_CONSTRAINTS.md` dividend 过渡政策存在；`TODO.md` PRD_04 完成项与 dividend ODS 补采待办存在。
- `PYTHONPATH=src python3 -m pytest -q tests`：266 passed。
- 真实项目记忆解析实测返回 CA-on baseline：`s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01` / `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01`。
- `git diff --check`：passed。

### 阻塞项

- 无。

### 下一步建议

- 对账与 pytest 通过后，提交、`--force-with-lease` 推送 PR #201，并在 PR 回帖最新结果。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`

## 交接条目

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: main-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: strategy1-benchmark-replay-000001-20260608
相关 issue/PR: N/A

### 已完成工作

- 在默认 benchmark 已切到 `000001.SH` 的前提下，完成不覆盖旧审计结果的 fixed-prediction lot-aware replay：
  `run_id=s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01`
  `backtest_id=bt_s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01`
  `prediction_run_id=s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01`
- 已重新生成并上传新 replay 的 report、model diagnosis、tail-risk 和 acceptance gate v2 artifact。
- 已手工补跑 `10`、`12`、`20`、`22`、`23` QA，均通过。
- 新 acceptance artifact `acceptance_gate_v2_lotaware_ref_bm000001_20260608_01` 已上传，状态为 `rejected`。

### 重要上下文

- 旧 `000852.SH` 口径 historical summary / report / diagnosis / gate artifact 保留不动，继续作为审计对照。
- 这次 replay 复用的 source prediction stream 没有独立 `final_holdout` split_tag，所以 `10_qa_runner_outputs.sql` 必须按 fixed-prediction override 跑：
  `p_test_end=2026-04-30`
  `p_final_holdout_start=NULL`
  `p_final_holdout_end=NULL`
- acceptance gate v2 仍按 replay NAV 的时间窗计算 final holdout；override 只用于 runner QA 的 split_tag 一致性。
- 新 gate 的拒绝原因是：
  `full_period_excess_return_vs_primary_benchmark<=-0.03`
  `full_period_information_ratio<0.0`

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m scripts.strategy1_cloudrun.backtest_report --experiment-json ...`
- `python3 scripts/strategy1/diagnose_model_quality.py --project data-aquarium --run-id s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01 --prediction-run-id s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01 --backtest-id bt_s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01 --artifact-base-uri gs://ashare-artifacts/reports/strategy1 --local-mirror-root reports/strategy1`
- `python3 scripts/strategy1/analyze_tail_risk.py --project data-aquarium --run-id s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01 --prediction-run-id s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01 --backtest-id bt_s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01 --artifact-base-uri gs://ashare-artifacts/reports/strategy1 --local-mirror-root reports/strategy1`
- `python3 scripts/strategy1/diagnose_acceptance_gate_v2.py --project data-aquarium --diagnosis-id acceptance_gate_v2_lotaware_ref_bm000001_20260608_01 --reference-run-id s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01 --reference-backtest-id bt_s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01 --prediction-run-id s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01 --contract configs/strategy1/model_acceptance_contract_v2.yml --feature-version strategy1_pv_fin_quality_v0_20260603 --label-version open_to_close_h1_5_10_20_v20260601 --horizon 5 --full-start-date 2024-01-02 --full-end-date 2026-04-30 --valid-start-date 2024-01-02 --valid-end-date 2024-12-31 --test-start-date 2025-01-02 --test-end-date 2025-12-31 --final-holdout-start-date 2026-01-05 --final-holdout-end-date 2026-04-30 --artifact-base-uri gs://ashare-artifacts/reports/strategy1 --local-mirror-root reports/strategy1`
- 通过 `scripts.strategy1_cloudrun.sql_runner.run_sql_script` 手工执行：
  `sql/ml/strategy1/10_qa_runner_outputs.sql`
  `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`
  `sql/ml/strategy1/20_qa_tail_risk_outputs.sql`
  `sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`
  `sql/ml/strategy1/23_qa_lot_aware_ledger_outputs.sql`

### 阻塞项

- 无硬阻塞。

### 下一步建议

- 若 owner 要把 `000001.SH` 口径作为后续统一对外口径，可继续补 v1/v2 契约和 QA 内部历史 `*_vs_000852` 阈值键名的 benchmark-neutral 重命名。
- 若要继续 OQ-010 训练 / 搜索，后续相对 benchmark 的新结论应统一引用这次 `000001.SH` replay，而不是混用旧 `000852.SH` audit。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

**OQ-010 PRD04 Cloud Run Python baseline search 实现（2026-06-06）**：PR #79 review follow-up、PR #82 runtime 修复和真实 wave 2 / wave 3 执行均已完成。真实 LightGBM binary wave 2 `cloudrun_python_lgbm_pvfq_n30_bw_h5_20260605_01` 与 regression wave 3 `cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01` 均完成 Top5 回测/报告/诊断和 QA，Top5 全部 rejected，当前不建立 `cloud_run_python_baseline_v1`。运行资源口径为 40 候选 / 20 并发 / 2 vCPU 8Gi；后续建议进入下一模型族、特征增强或训练目标改造，而不是继续围绕已拒绝的两波 LightGBM 搜索。

**项目记忆瘦身归档（2026-06-05）**：`AGENT_HANDOFF.md` 已按 owner 要求整理，当前文件只保留启动摘要、归档清理交接和最近 3 条交接；较早的 30 条交接已追加到 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。常规启动优先读本文件；需要审计历史时再读 archive。

**OQ-005 PR #80 部署与 2026-06-05 smoke（2026-06-06）**：当前 `main` 已包含 PR #80，并已完成生产部署：`ashare_daily_pipeline_v0.py` 同步到 Composer `dags/`，仓库 `sql/` 同步到 `gs://asia-east2-ashare-composer-b2629133-bucket/data/sql/`，本地 / bucket DAG 与 `09_ods_daily_partition_readiness.sql` SHA256 一致。`manual_pr80_daily_current_20260605_20260606_01` 使用 `business_date=2026-06-05` 成功完成 current_scope 采集、ODS readiness、窗口 DIM/DWD/DWS 刷新和窗口 QA；采集后 2026-06-05 strong endpoint 行数为 daily 5514、daily_basic 5514、adj_factor 5526、stk_limit 7634、index_daily 7。`manual_pr80_qa_only_20260605_20260606_01` 使用 `skip_ingestion=true` 成功完成 readiness + P0 / strategy1 / OQ004 / finance / OQ006 五个只读 QA。最近 20 个交易日 `2026-05-11..2026-06-05` ODS daily_basic → DWD valuation → DWS valuation 行数均为 110,035，错配天数 0。下一步仍是 Dataform 生产链路、完整 ODS→ADS 运维观测闭环和新 DAG 自然 scheduled 观察；非交易日自动 skip gate 已由 PR #83 合并部署，并通过 `manual_smoke_skip_non_trading_day_pr83_20260606_02` 验收。

**OQ-010 Cloud Run Python baseline 搜索 PRD（2026-06-05）**：工作树 `/Users/luna/Desktop/git/quant-ashare-cloudrun-python-baseline-search`，分支 `codex/prd-cloudrun-python-baseline-search`。新增 `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`：本轮数据截止 `2026-04-30`；train/valid/test/final_holdout 为 `2019-04-03..2023-12-31` / 2024 / 2025 / `2026-01-05..2026-04-30`；固定 `pv_fin_quality + 30/5% + biweekly + 5d`、沪深主板股票池、成本 profile 和 Ledger v1；P0 推荐 LightGBM wave 2。PR #78 review follow-up 后，候选排序改为 2021/2022/2023 三折 purged walk-forward CV + 2024 valid confirmation，2025 test 做硬接受门，2026 final_holdout 只做明显坏结果 veto / holdout watch；实现 smoke 后当前资源口径已从最初 40 并发 / 1 vCPU 4Gi 调整为 40 候选 / 20 并发 / 2 vCPU 8Gi；若 binary LightGBM rejected，后续优先试 `lightgbm_regression`。

**OQ-005 告警/观测生产闭环部署与 PR #75 follow-up（2026-06-05）**：PR #75 已合并并完成生产部署；后续代码收敛工作树 `/private/tmp/oq005-alerting-deploy-followup`，分支 `codex/oq005-alerting-deploy-followup`。已完成：8 个 BigQuery 观测视图创建、旧线上名 `oq005_pipeline_failure` / `oq005_task_failure` / `oq005_ingestion_failed` log-based metrics 创建、3 个 `OQ-005: ...` Cloud Monitoring alert policies 启用（Ingestion severity 已从 CRITICAL 修正为 WARNING）、Email 通知渠道配置并关联到告警策略、定时 checker DAG `oq005_alert_checker` 部署（每 10 分钟）、三类告警 smoke 验证（pipeline_failure / task_failure / ingestion_failed 均在 timeSeries 中 value=1）。PR #75 follow-up 已部署并验收：Composer bucket 已同步旧 checker DAG 与 `check_alerts.py`；新增旧线上名 `oq005_alert_checker_heartbeat` log-based metric 和 `OQ-005: Alert Checker Heartbeat Missing` 30 分钟 absence policy，策略已启用并绑定 1 个 Email 通知渠道；`check_alerts.py` 显式使用 `resource.type=global` 写业务告警与 heartbeat，避免 Composer 默认 `k8s_container` resource 与现有告警策略不匹配。PR #77 review follow-up 已修复告警策略幂等键：`setup_alerts.py` 使用稳定 `user_labels.oq005_policy` 并兼容旧 display name 迁移，避免旧名环境重复创建新旧两份策略。manual smoke `manual_oq005_alert_checker_heartbeat_global_20260605_01` 成功，随后的 scheduled run 也成功；Cloud Logging 中 heartbeat 为 `resource.type=global`、`lookback_minutes=20`、`alerts_count=0`，Cloud Monitoring global timeSeries 已有点。PR #91 的 `ashare_pipeline_*` 是后续 cutover 目标名。下一步：继续 Dataform definitions、补跑和完整 ODS→ADS 运维观测闭环。

**OQ-005 告警/观测 PR #72 review follow-up（2026-06-05）**：工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-alerts-runbook`，分支 `codex/oq005-alerts-runbook`。PR #72 新增 BigQuery 观测视图、Cloud Logging / Cloud Monitoring 告警配置脚本、告警查询脚本和补跑 runbook。本轮按 comment 修复：`setup_alerts.py` 的 `LogMetric` 使用正确 `filter` 字段；`check_alerts.py` 查询失败和缺 `google-cloud-logging` 写日志路径均 fail-closed，默认 lookback 改 10 分钟并用稳定 `insert_id` 降低重复日志；runbook §9 的 `task_failure` / `ingestion_failed` 与 SQL 实现一致；`v_alert_probe` 注释改为固定 24 小时手工健康检查口径。验证通过 Python `py_compile`、观测 SQL BigQuery dry-run、`git diff --check`；本机缺 `google-cloud-logging`，未做真实 log metric API apply。合并后仍需部署视图、配置 Cloud Scheduler/Cloud Run checker、log-based metrics、alert policies，并做生产 smoke。

**OQ-010 当前路线（2026-06-05）**：owner 已决定后续不再使用 BQML 或 `sql/ml/strategy1` SQL runner 作为策略训练、预测、回测、报告、诊断、月度滚动重训或多实验搜索的默认 / fallback / 新增开发路线；该决策已写入 `DECISION-20260605-03`。历史 BQML 最优组合 `pv_fin_quality + 30/5% + biweekly + 5d` 仅作 reference / audit。PR #76 follow-up 已在 `docs/prd/PRD_20260604_02_策略1月度滚动重训.md` 文首补 superseded banner；正文仍待后续改造成 Cloud Run Python / backend-neutral prediction stream。下一步应寻找可接受的 Cloud Run Python 模型 / backend baseline。

**OQ-010 已收口事实（2026-06-05）**：Ledger v1 P1 extended fresh run `s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` 覆盖 `2024-01-02` 至 `2026-04-30`，total_return 35.16%、excess_return -7.22% vs `000852.SH`；P2 resume run `s1_bqml_baseline_pvfq_n30_bw_h5_resume_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_resume_20260604_01` 通过 `sql/ml/strategy1/15_qa_ledger_resume_consistency.sql`。sklearn native search 首轮 `sklearn_native_pvfq_n30_bw_h5_20260605_01` 已完成，Top5 均因 `test_year_excess_return<=0.0` 被拒绝，本轮不建立 `cloud_run_sklearn_native_baseline_v1`。

**OQ-005 / OQ-012 当前状态（2026-06-06）**：OQ-005 已完成 current-scope 生产采集至 `2026-06-05`、Composer DAG/SQL 部署验收、20 日窗口 DWD/DWS smoke、readiness 门禁复核、告警/观测与 alert checker heartbeat；scheduled 非交易日 skip gate 已由 PR #83 合并部署并完成 force hook smoke。OQ-005 仍 open，剩余 Dataform 生产链路、完整 ODS→ADS 运维观测闭环和新 DAG 自然 scheduled 观察。OQ-012 当前 BigQuery 读层 `sql/qa/06_ods_parquet_schema_checks.sql` 对 P0 与 all 范围均通过，待 owner 决定关闭/归档或保留 schema contract / ingestion 显式 cast 防复发任务。

**常规约定**：评审默认写 GitHub PR comment；TODO 只保留下一步可执行事项，待 owner 决策问题以 `OPEN_QUESTIONS.md` 为唯一来源。PR 合并后，若 owner 未要求保留工作分支，应删除已合并且不再使用的 `codex/*` 本地分支、对应远端分支，并移除为该分支创建的独立 `git worktree`；若 worktree 仍有未提交或未合并改动，先暂停并请 owner 决策，不得强删。

> 历史交接已归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-05.md` 和 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。常规启动只需阅读本文件的当前摘要和最近交接；归档仅用于审计追溯。

---

---

## 交接条目

日期: 2026-06-07
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: index_000001_warehouse_backfill_20260607
相关 issue/PR: 待创建 PR

### 已完成工作

- 新增 `sql/ods/01_index_external_table_uris.sql`，用 `CREATE OR REPLACE EXTERNAL TABLE` 维护 `ods_tushare_index_daily` / `ods_tushare_index_dailybasic` 的显式 source URI 列表，并补入 `000001.SH` 两个 endpoint。
- `configs/ingestion/ods_current_scope_v0.yml` 已补 `index_daily_000001_SH` 和 `index_dailybasic_000001_SH` request variants。
- `sql/dim/04_dim_index.sql` 已加入上证指数 `SSE_COMPOSITE` seed。
- 新增 `sql/incremental/02_refresh_index_dwd_window.sql` 与 `sql/qa/12_windowed_index_refresh_checks.sql`，并接入 `orchestration/composer/dags/ashare_common.py` 的 setup / windowed transform 链路。
- 同步 `dataform/action_manifest.json` 和生成的 SQLX 文件。
- `sql/qa/03_index_benchmark_checks.sql`、`sql/qa/08_ods_external_readability_checks.sql`、`sql/qa/01_core_smoke_checks.sql` 已补 `000001.SH` 相关检查。

### 重要上下文

- ODS index external tables 当前使用显式 `sourceUris`，不是自动发现所有 `endpoint=*`。GCS 写入成功后，如果不更新 external table URI，BigQuery ODS 仍读不到新 endpoint。
- `000001.SH` 两个 endpoint 在 BigQuery ODS 中均已确认有 1,799 个 2019+ SSE 开市日分区 / 行。
- 为保持既有训练结果可复现，本次没有修改 `dws_market_state_daily` 或 `market_state_v0_20260606`，也没有写 ADS。后续如要把上证指数纳入训练市场状态，应新建 market-state 版本或新 feature set。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`
- `configs/ingestion/ods_current_scope_v0.yml`
- `dataform/action_manifest.json`
- `dataform/definitions/**`
- `docs/Pipeline-补跑与故障恢复-Runbook.md`
- `orchestration/composer/dags/ashare_common.py`
- `sql/dim/04_dim_index.sql`
- `sql/incremental/02_refresh_index_dwd_window.sql`
- `sql/ods/01_index_external_table_uris.sql`
- `sql/qa/01_core_smoke_checks.sql`
- `sql/qa/03_index_benchmark_checks.sql`
- `sql/qa/08_ods_external_readability_checks.sql`
- `sql/qa/12_windowed_index_refresh_checks.sql`

### 测试 / 验证

- `python3 scripts/dataform/generate_sqlx_from_sql.py`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/ods/01_index_external_table_uris.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dim/04_dim_index.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dwd/04_dwd_index_eod.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/03_index_benchmark_checks.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/05_unit_contract_checks.sql`
- `sql/incremental/02_refresh_index_dwd_window.sql` 使用 `warehouse_mode=backfill`、`date_from=2019-01-01`、`date_to=2026-06-05` 实跑，删除并重插 13,770 行，其中 `000001.SH` 1,799 行。
- `sql/qa/12_windowed_index_refresh_checks.sql` 同窗口通过。
- 复跑 `sql/qa/03_index_benchmark_checks.sql` 通过。

### 阻塞项

- 无。

### 下一步建议

- 提 PR 后合并并同步 `sql/` 与 Composer DAG 到 Composer bucket。
- 合并部署后触发一次 `ashare_warehouse_window_refresh` 小窗口 backfill 或等待下一次 scheduled ingestion 触发，确认 Airflow task 链路中的 `index_dwd_window` 与 `windowed_index_refresh_checks` 成功。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

---

日期: 2026-06-07
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_risk_feature_pr102_review_followup_20260607
相关 issue/PR: PR #102

### 已完成工作

- 按 PR #102 comment 修复风险特征实现的两个 review 点。
- 将风险专项最大回撤目标接入共享 acceptance contract：`model_acceptance_contract_v1.yml` 显式加入 `min_full_period_max_drawdown: -0.18`，`acceptance.py` 新增 `full_period_max_drawdown_threshold()` / `risk_feature_max_drawdown_target()`，`contract_sql_params()` 输出 `p_risk_feature_max_drawdown_target`。
- `21_qa_risk_feature_search_outputs.sql` 的 `p_risk_feature_max_drawdown_target` 默认改为 `NULL`，并新增 `QA-RISK-0`，防止 standalone 真执行时静默使用硬编码阈值。
- 将 `derive_final_holdout_status()` 从 orchestrator 移入共享 `acceptance.py`，orchestrator 删除本地重复函数并调用共享规则。

### 重要上下文

- 本次只修 PR #102 review follow-up，不执行真实 Cloud Run 训练，不更新 ADS，不建立 baseline。
- v1 contract hash 因新增阈值字段发生变化；这是预期结果，用于让风险专项阈值进入契约审计链。
- 合并后仍需构建/部署 runner 镜像，再执行 binary 20 与 regression 20 候选训练、Top5 回测和 `19` + `21` QA。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`
- `configs/strategy1/model_acceptance_contract_v1.yml`
- `scripts/strategy1_cloudrun/acceptance.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/acceptance.py scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- v1 contract hash / `p_min_full_period_max_drawdown` / `p_risk_feature_max_drawdown_target` 参数确认。
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`
- 使用 `contract_sql_params()` 渲染后的 `21_qa_risk_feature_search_outputs.sql` BigQuery dry-run。
- risk feature orchestrator `--build-training-panel --dry-run`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- PR #102 合并后构建/部署 runner 镜像。
- 执行 binary risk feature search，再执行 regression risk feature search。
- Top5 回测后以共享 `19` QA 和风险专项 `21` QA 收口，并按结果判断是否 accepted / needs_more_evidence / rejected。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

---

日期: 2026-06-07
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_risk_feature_search_implementation_20260607
相关 issue/PR: 待创建 PR

---

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: oq005_exit_composer_prd_20260608
相关 issue/PR: 待创建 PR

### 已完成工作

- 新增 `docs/prd/PRD_20260608_01_OQ005调度完全迁出Composer.md`，将 OQ-005 的长期编排方向从“长期保留 Composer”调整为“迁出 Composer 后删除环境”。
- PRD 明确推荐架构为 `Cloud Scheduler + Cloud Workflows + Cloud Run Jobs + BigQuery SQL/Dataform`，并将 `ashare_pipeline_alert_checker` 迁到 `Cloud Scheduler + Cloud Run`。
- 已同步更新 `PROJECT_CONTEXT.md`、`ARCHITECTURE_MEMORY.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`TODO.md`，把当前 Composer DAG 拆分、window refresh、alert checker 与 smoke 统一标注为 cutover 前过渡态。
- 已按 PR #108 comment follow-up 补强 PRD：把 per-task 状态写回、显式分布式锁、同步 child workflow / 退役 refresh-missing watchdog、BigQuery/Cloud Run 轮询模型和 Workflows 限额复核写成实现硬要求。

### 重要上下文

- 当前 Composer 费用问题的核心不是 DAG 次数，而是常驻 `Cloud Composer 3 standard milli DCU-hours` 底座费；迁移完成前，减少 DAG 次数本身不能显著降本。
- 本次只写 PRD 和记忆/TODO，不改现有 DAG、Cloud Run、BigQuery SQL 或告警实现。
- PRD 默认路径不要求 owner 额外拍板：多步编排使用 Workflows，单步 alert checker 直接走 Scheduler + Cloud Run。
- PR #108 review 已指出 4 个 Airflow -> Workflows 容易静默回退的点；这些已全部在 PRD 中转成硬要求，不再留到实现时自由发挥。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `TODO.md`
- `docs/prd/PRD_20260608_01_OQ005调度完全迁出Composer.md`

### 测试 / 验证

- 本次未运行 BigQuery / Cloud Run / Composer 验证。
- 仅完成文档与记忆同步。

### 阻塞项

- 无当前阻塞；下一阶段才需要实现 Workflows/Scheduler 基础设施和 cutover smoke。

### 下一步建议

- 新开实现分支，先落 Workflows/Scheduler 基础设施。
- 保持现有 SQL、metadata、QA 和 alert checker 语义不变，优先做无语义漂移迁移。
- 完成 `qa_only` / `daily_current` / `backfill` / 非交易日 skip 手工 smoke 后，再安排 scheduled cutover。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `TODO.md`

### 已完成工作

- 在工作树 `/Users/luna/Desktop/git/quant-ashare-risk-feature-impl`、分支 `codex/implement-risk-feature-search` 实现 PRD `docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md` 的风险特征第 4 波训练路径。
- 新增 `scripts/strategy1_cloudrun/feature_sets.py`，固化 `strategy1_pv_fin_risk_v0_20260606` 95 列特征契约，覆盖 `pv_fin_quality` 基础特征、个股风险、市场状态和风险交互项。
- `prepare_matrix.py` 增加 feature set 契约校验，输出 `feature_delta_vs_base.json`、feature schema hash、风险/市场特征列表和 split missing-rate。
- `train_candidate_task.py` 输出 LightGBM / sklearn-like feature importance，聚合到 feature group，并记录 `risk_feature_importance_gain_share`、`market_state_importance_gain_share`。
- `select_register_predict.py` 将 feature schema/delta hash、feature count、risk feature count 和 market-state feature count 写入 registry metrics。
- `orchestrate_sklearn_native_search.py` 支持 config 指定训练面板 SQL，风险特征 search 自动追加 `21` QA，并增加 final_holdout passed 派生与 `max_drawdown >= -18%` 风险专项 overlay。
- 新增 Cloud Run 专用训练面板 SQL `sql/cloudrun/strategy1/01_build_training_panel.sql`，按 PRD 写入个股风险、市场状态和交互特征。
- 新增 binary/regression 各 20 候选 manifest，以及 `sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`。

### 重要上下文

- 本次只完成实现和 dry-run 验证，未执行真实 Cloud Run 40 候选训练，未跑 Top5 回测，未建立 baseline。
- 两个 manifest 分别是 `configs/strategy1/cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_v0.yml` 和 `configs/strategy1/cloudrun_python_riskfeat_lgbm_regression_pvfq_n30_bw_h5_v0.yml`，均为 20 候选 / 20 并发 / 2 vCPU / 8Gi / wave 4 / `test_reuse_wave_no=4`。
- 合并后下一步应先构建/部署 runner 镜像，再依次跑 binary 20 与 regression 20；Top5 完整回测后必须跑共享 `19` QA 和风险特征 `21` QA。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`
- `configs/strategy1/cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_v0.yml`
- `configs/strategy1/cloudrun_python_riskfeat_lgbm_regression_pvfq_n30_bw_h5_v0.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/feature_sets.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1_cloudrun/prepare_matrix.py`
- `scripts/strategy1_cloudrun/select_register_predict.py`
- `scripts/strategy1_cloudrun/train_candidate_task.py`
- `sql/cloudrun/strategy1/01_build_training_panel.sql`
- `sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`
- `sql/ml/strategy1/README.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/feature_sets.py scripts/strategy1_cloudrun/prepare_matrix.py scripts/strategy1_cloudrun/train_candidate_task.py scripts/strategy1_cloudrun/select_register_predict.py scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- manifest parse 校验：两个 riskfeat manifest 均为 20 候选、20 并发、2 vCPU / 8Gi、wave 4、风险特征集。
- `python3 -m scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search ... --build-training-panel --dry-run`，binary 和 regression 两个 manifest 均通过。
- `python3 -m scripts.strategy1_cloudrun.prepare_matrix ... --dry-run`，binary 和 regression 两个 manifest 均通过。
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/cloudrun/strategy1/01_build_training_panel.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`
- SQL/Python feature_column_list 95 列顺序一致性检查通过。
- `git diff --check`

### 阻塞项

- 无。真实训练需要合并后构建/部署 Cloud Run 镜像，并消耗 Cloud Run / BigQuery / GCS 资源。

### 下一步建议

- 创建并合并实现 PR。
- 合并后构建/部署 runner 镜像。
- 先跑 `cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_20260606_01`，再跑 `cloudrun_python_riskfeat_lgbm_reg_pvfq_n30_bw_h5_20260606_01`。
- 汇总 40 个候选和 Top5 回测结果，以 `19` + `21` QA 作为验收门。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

日期: 2026-06-07
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_lotaware_reference_execution_20260607
相关 issue/PR: PR #100, PR #101

### 已完成工作

- 合并 PR #101 `fix(strategy1): pass prediction source to portfolio reports`，清理远端/本地分支 `codex/fix-portfolio-only-report-source-run` 和工作树 `/Users/luna/Desktop/git/quant-ashare-lotaware-runner-fix`。
- 构建并部署 runner 镜像 `lotaware-c018ef5-20260607-01` 到 `strategy1-backtest-report-job`。
- 执行 fixed-prediction lot-aware reference：`s1_lotaware_ref_pvfq_n30_bw_h5_20260606_01` / `bt_s1_lotaware_ref_pvfq_n30_bw_h5_20260606_01`，复用 prediction run `s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01`，窗口 `2024-01-02..2026-04-30`，Cloud Run execution `strategy1-backtest-report-job-h7vtl` 成功。
- 生成并上传 report、model diagnosis、tail-risk artifact 和 acceptance gate v2 artifact `acceptance_gate_v2_lotaware_ref_20260607_01`。

### 结果

- lot-aware reference：total_return 35.17%、excess_return -7.20pct vs `000852.SH`、Sharpe 0.872、max_drawdown -13.59%、ledger_version `ledger_exec_v1_lot100`。
- 行数：prediction 1,247,888；candidate 132,909；target 1,800；order 962；trade 2,276；position 16,749；NAV 562。
- 成交状态：BUY filled 601 笔、BUY below-lot skipped 1,034 笔；SELL filled 467 笔、SELL below-lot partial skipped 160 笔、pending sell carry 8 笔。
- acceptance gate v2：`rejected`；拒绝原因是全期跑输中证1000超过 3pct、IR 为负、2026 final_holdout 跑输中证1000 12.75pct。

### 验证

- Cloud Run 内部：`10_qa_runner_outputs.sql`、`12_qa_model_diagnosis_outputs.sql`、`20_qa_tail_risk_outputs.sql` 通过。
- 手工复核：`22_qa_acceptance_gate_v2_outputs.sql` job `5a90c3d6-8d46-469a-b096-c92c5e7a7d55` 通过；`23_qa_lot_aware_ledger_outputs.sql` job `11ad8837-5e56-46c2-adbe-d275b919036f` 通过。

### 后续

- lot-aware 交易语义收口已完成；下一步可继续 `docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md` 的风险特征 / 下一模型族训练路线。

日期: 2026-06-07
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_lotaware_source_run_fix_20260607
相关 issue/PR: 待创建 PR

### 已完成工作

- 预检 fixed-prediction lot-aware reference 输入：源 prediction run `s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` 在 `2024-01-02` 至 `2026-04-30` 有 1,247,888 行预测；目标 `s1_lotaware_ref_pvfq_n30_bw_h5_20260606_01` / `bt_s1_lotaware_ref_pvfq_n30_bw_h5_20260606_01` 无 candidate / portfolio / order / trade / NAV 残留。
- 确认源模型 registry 为 `bqml_logistic_reg`、`feature_set_id=strategy1_pv_fin_quality_v0_20260603`、`target_holdings=30`、`rebalance_frequency=biweekly`。
- 修复 portfolio-only / lot-aware 报告和诊断的 source-run 口径：`render_report.py` 支持 `--prediction-run-id`，`backtest_report.py` 向 report / diagnosis 同时传新回测 run 与源预测 run。

### 验证

- `python3 -m py_compile scripts/strategy1/render_report.py scripts/strategy1_cloudrun/backtest_report.py`
- `python3 -m scripts.strategy1_cloudrun.backtest_report ... --experiment-json <lotaware_ref> --force-replace --dry-run`
- `git diff --check`

### 后续

- 创建并合并该修复 PR。
- 合并后构建/部署新 Cloud Run runner 镜像，执行 lot-aware reference，并运行 `23_qa_lot_aware_ledger_outputs.sql` 与 acceptance gate v2。

日期: 2026-06-07
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_lot_aware_ledger_merge_20260607
相关 issue/PR: PR #100

### 已完成工作

- 合并 PR #100 `feat(strategy1): implement lot-aware ledger` 到 `main`，merge commit 为 `4a1657d`。
- 本地 `main` 已 `git pull --ff-only origin main` 同步到 merge commit。
- 删除远端分支 `codex/implement-lot-aware-ledger`。
- 移除实现工作树 `/Users/luna/Desktop/git/quant-ashare-lot-aware-ledger-impl`。
- 删除本地分支 `codex/implement-lot-aware-ledger`。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要，明确 PR #100 已合并但 fixed-prediction lot-aware reference 尚未执行。

### 重要上下文

- `ledger_exec_v1_lot100` 代码、`sql/ml/strategy1/23_qa_lot_aware_ledger_outputs.sql`、golden-case 单测、report / summary / acceptance gate v2 对齐和运行手册已进入 `main`。
- PR #100 合并不等于策略 reference 已重跑；尚未部署 Cloud Run 镜像，也尚未执行 `2024-01-02` 至 `2026-04-30` 的 fixed-prediction lot-aware reference。
- 下一步策略训练 / 风险特征工作前，应先部署 runner 镜像，跑 lot-aware reference，执行 `23` QA 和 acceptance gate v2。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

### 测试 / 验证

- `gh pr view 100 --json state,mergedAt,mergeCommit,url,headRefName`
- `git pull --ff-only origin main`
- `git push origin --delete codex/implement-lot-aware-ledger`
- `git worktree remove /Users/luna/Desktop/git/quant-ashare-lot-aware-ledger-impl`
- `git branch -d codex/implement-lot-aware-ledger`

### 阻塞项

- 无。

### 下一步建议

- 构建并部署包含 PR #100 的 Cloud Run runner 镜像。
- 复用当前 prediction stream 跑 `2024-01-02` 至 `2026-04-30` fixed-prediction lot-aware reference。
- 执行 `23_qa_lot_aware_ledger_outputs.sql`、报告/诊断和 acceptance gate v2。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_lot_aware_ledger_implementation_20260606
相关 issue/PR: PR #99 / 待创建实现 PR

### 已完成工作

- 新建实现工作树 `/Users/luna/Desktop/git/quant-ashare-lot-aware-ledger-impl` 与分支 `codex/implement-lot-aware-ledger`。
- 将 Cloud Run Python 默认回测路径切到 `ledger_exec_v1_lot100` / `cloud_run_sklearn_ledger_v1_lot100`；保留显式 `--use-float-ledger` 与 `--use-bq-ledger` 作为 legacy / audit 路径。
- 在 `scripts/strategy1_cloudrun/ledger.py` 实现 lot-aware 执行：买入按 100 股整数手向下取整、below-lot 跳单、现金缩放后低于 1 手跳单、现金仍不足时按 rank 优先级回退低优先级买单、清仓 odd-lot 全额卖出、部分卖出向下取整到 100 股并保留残股、未成交 full-exit pending sell 继续重试。
- 在 `scripts/strategy1_cloudrun/backtest_report.py` 注入 `p_ledger_version` / `p_lot_size` / `p_min_buy_lot`，默认在 lot100 路径追加执行 `sql/ml/strategy1/23_qa_lot_aware_ledger_outputs.sql`。
- 扩展 `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`、`10_qa_runner_outputs.sql`、`16_qa_cloudrun_runner_outputs.sql`、`22_qa_acceptance_gate_v2_outputs.sql` 和 `configs/strategy1/model_acceptance_contract_v2.yml`，让 summary、runner QA 和 v2 acceptance gate 都能识别并要求 lot-aware ledger。
- 扩展 `scripts/strategy1/render_report.py`，在中文报告中展示 ledger version、整数手参数、跳单状态、odd-lot 清仓和现金权重。
- 新增 `sql/ml/strategy1/23_qa_lot_aware_ledger_outputs.sql`，验证 BUY filled shares 为 100 股整数倍、skipped 零成交、odd-lot 只出现在清仓 SELL、部分卖出 below-lot 后仍保留持仓、现金/暴露/持仓唯一性等。
- 新增 `tests/strategy1_cloudrun/test_lot_aware_ledger.py` golden-case 单元测试，覆盖买入取整、低于 1 手跳单、现金缩放后低于 1 手、现金回退、odd-lot 清仓、partial sell 残股保留和 pending sell 重试。
- 更新 `sql/README.md`、`sql/ml/strategy1/README.md` 和 `docs/策略1CloudRun训练回测运行手册.md`。

### 重要上下文

- 本 PR 只完成代码、QA 和文档实现；尚未部署 Cloud Run 镜像，尚未执行 `2024-01-02` 至 `2026-04-30` 的 fixed-prediction lot-aware reference。
- 后续 production acceptance 不得使用 FLOAT-shares backtest；需要先跑 lot-aware reference、执行 `23` QA，并重跑 acceptance gate v2。
- 余股的来源是历史买入 / 现金缩放 / corporate action 或历史 FLOAT position 等造成的非 100 股整数持仓；lot100 P0 允许清仓 odd-lot，但 partial sell 不卖碎股。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`
- `configs/strategy1/cloudrun_runner_default.yml`
- `configs/strategy1/model_acceptance_contract_v2.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1/diagnose_acceptance_gate_v2.py`
- `scripts/strategy1/render_report.py`
- `scripts/strategy1_cloudrun/__init__.py`
- `scripts/strategy1_cloudrun/acceptance.py`
- `scripts/strategy1_cloudrun/backtest_report.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/ledger.py`
- `sql/README.md`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`
- `sql/ml/strategy1/23_qa_lot_aware_ledger_outputs.sql`
- `sql/ml/strategy1/README.md`
- `tests/strategy1_cloudrun/test_lot_aware_ledger.py`

### 测试 / 验证

- `python3 -m unittest tests/strategy1_cloudrun/test_lot_aware_ledger.py`
- `python3 -m py_compile scripts/strategy1_cloudrun/ledger.py scripts/strategy1_cloudrun/backtest_report.py scripts/strategy1/render_report.py scripts/strategy1/diagnose_acceptance_gate_v2.py scripts/strategy1_cloudrun/acceptance.py scripts/strategy1_cloudrun/config.py scripts/strategy1_cloudrun/__init__.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/23_qa_lot_aware_ledger_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`
- `python3 -m scripts.strategy1_cloudrun.backtest_report --project data-aquarium --region asia-east2 --experiment-id oq010_a0_n5_w20 --dry-run`

### 阻塞项

- 无代码阻塞；真实 reference / Cloud Run 部署留待 PR 合并后执行。

### 下一步建议

- 创建并 review/merge 实现 PR。
- 合并后构建并部署 Cloud Run runner 镜像，复用当前 prediction stream 跑 `2024-01-02` 至 `2026-04-30` fixed-prediction lot-aware reference。
- reference 成功后执行 `23` QA、报告/诊断和 acceptance gate v2，确认能否进入下一轮风险特征训练或模型搜索。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_acceptance_gate_v2_implementation_20260606
相关 issue/PR: PR #97 / 待创建实现 PR

### 已完成工作

- 合并 PR #97，并清理已合并 PRD 分支 / worktree。
- 新建实现工作树 `/Users/luna/Desktop/git/quant-ashare-acceptance-gate-v2-impl` 与分支 `codex/implement-acceptance-gate-v2`。
- 新增 `configs/strategy1/model_acceptance_contract_v2.yml`，固化 v2 accepted / needs_more_evidence / hard reject 阈值、10/20/30/40 组合候选、eligible benchmark、score orientation audit 与 split 复用口径。
- 扩展 `scripts/strategy1_cloudrun/acceptance.py`，为共享契约增加 `contract_sha256` 与 v2 SQL 参数导出，同时保持 v1 历史搜索兼容。
- 新增只读诊断脚本 `scripts/strategy1/diagnose_acceptance_gate_v2.py`：读取当前 extended reference run、prediction、candidate、DWS 标签、DWD 价格和持仓，输出 v2 summary、10/20/30/40 组合可行性、eligible universe benchmark、score orientation audit、低价股偏移、实际持股、现金和风格暴露诊断；不训练、不改 prediction、不写 ADS。
- 新增 `sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`，校验 v2 contract、目标持股集合、reference rejected、候选 top40、score orientation 输入、valid/test 标签输入，以及 BQML/SQL runner 不得登记 v2 accepted baseline。

### 重要上下文

- 默认诊断 run：`acceptance_gate_v2_reference_20260606_01`。
- Reference run/backtest：`s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01`。
- 当前 v2 结论：`rejected`，原因是 `full_period_excess_return_vs_000852<=-0.03`、`full_period_information_ratio<0.0`、`final_holdout_excess_return_vs_000852<=-0.1`。该 rejection 只针对当前 top-30 long-only 组合实现，不否定信号家族。
- 组合可行性摘要：`10/5%` 为 `diagnostic_only`；`20/30/40` 因局部 `max_cash_weight` 或平均现金偏高进入 `needs_more_evidence`，未出现 implementation hard fail。
- uploaded artifact URI：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/acceptance_gate_v2/diagnosis_id=acceptance_gate_v2_reference_20260606_01`。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`
- `configs/strategy1/model_acceptance_contract_v2.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1/diagnose_acceptance_gate_v2.py`
- `scripts/strategy1_cloudrun/acceptance.py`
- `sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`
- `sql/ml/strategy1/README.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/diagnose_acceptance_gate_v2.py scripts/strategy1_cloudrun/acceptance.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`
- `python3 scripts/strategy1/diagnose_acceptance_gate_v2.py --project data-aquarium --skip-gcs-upload`
- `bq query --use_legacy_sql=false --location=asia-east2 < /tmp/22_qa_acceptance_gate_v2_outputs.injected.sql`（注入真实 contract hash 后 9 个 ASSERT 全部 successful）
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`（默认 standalone placeholder 预期在 `QA-V2-1` fail-loud）
- `python3 scripts/strategy1/diagnose_acceptance_gate_v2.py --project data-aquarium`（uploaded 成功，16 个 GCS artifact）
- `gcloud storage ls gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/acceptance_gate_v2/diagnosis_id=acceptance_gate_v2_reference_20260606_01/`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 创建并 review/merge 实现 PR。
- 合并后根据 v2 结论决定：继续 PRD03 风险特征训练，或先复核组合现金/执行语义（尤其 `20/30/40` 的局部现金峰值）。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_acceptance_gate_v2_qa_hash_hardening_20260606
相关 issue/PR: PR #98

### 已完成工作

- 采纳 PR #98 review 的可选加固建议：`sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql` 的 `QA-V2-1` 明确拒绝 standalone placeholder hash。
- 保持 production / 真实验证路径不变：由契约注入真实 `acceptance_contract_sha256` 后执行 `22` QA。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`KNOWN_CONSTRAINTS.md` 和当前交接摘要。

### 重要上下文

- 默认直接执行 `22_qa_acceptance_gate_v2_outputs.sql` 现在会在 `QA-V2-1` fail-loud；这是预期行为，用于防止忘记注入真实契约 hash。
- 当前 v2 契约 hash 为 `e7f26a5f33713d9c740abaf9f4a60aa3d3adba119aad514519c30761d3cb8608`。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`
- `sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/diagnose_acceptance_gate_v2.py scripts/strategy1_cloudrun/acceptance.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < /tmp/22_qa_acceptance_gate_v2_outputs.injected.sql`（注入真实 contract hash 后 9 个 ASSERT 全部 successful）
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`（默认 standalone placeholder 预期在 `QA-V2-1` fail-loud）

### 阻塞项

- 无。

### 下一步建议

- PR #98 可继续按 review 结论合并；合并后删除不再使用的 `codex/implement-acceptance-gate-v2` 本地/远端分支。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_acceptance_gate_v2_review_followup_20260606
相关 issue/PR: PR #97 review

### 已完成工作

- 阅读 review 文本，认可全部实质问题，无反驳项。
- 修改 `docs/prd/PRD_20260606_04_策略1验收门v2与组合可行性诊断.md`：
  - `10/5%` 改为 `diagnostic_cash_control`，不参与 `accepted`，不适用满仓现金占比 hard gate。
  - accepted 条件新增跑赢 `eligible_executable_benchmark`，并把 eligible benchmark 拆成 signal-pool 与 executable 两版。
  - split 表新增 `reuse_status`，明确 2025 test / 2026 final_holdout 已被多轮查看，负向证据可 reject，正向证据不能单独 accepted。
  - 新增 `score_orientation_audit.json` 与 QA 断言，检查 actual long side、top-minus-bottom 定义和 RankIC 使用字段。
  - low-price tilt 从文字描述改为可计算字段和 needs_more_evidence / hard_failed 阈值。
  - 新增 gross exposure / deployed capital / exposure-adjusted return 视图。
  - 新增共享验收契约 v2 要求：`configs/strategy1/model_acceptance_contract_v2.yml` 是 v2 阈值和指标定义唯一事实来源，Python acceptance 与 `18/19/22` QA 必须读取同一契约。
  - 修正 `full_period_excess_return_vs_000852=-3%` 的边界归属：`-3%` 属 hard reject，needs-more-evidence 下边界改为开区间。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`DECISION_LOG.md` 和本交接文件。

### 重要上下文

- PRD 仍然只写方案，不改代码、不运行 BigQuery / Cloud Run。
- 10/20/30/40 仍是唯一持股数集合；50 仍被明确排除。
- 后续实现应先落 `model_acceptance_contract_v2.yml`，再做只读 `acceptance_gate_v2` 诊断和组合可行性模拟，之后再决定是否启动 PRD03 风险特征训练。

### 改动文件

- `docs/prd/PRD_20260606_04_策略1验收门v2与组合可行性诊断.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 复核后合并 PRD。
- 合并后先实现 `model_acceptance_contract_v2.yml`，再实现 `acceptance_gate_v2` 诊断和组合可行性模拟。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_acceptance_gate_v2_prd_20260606
相关 issue/PR: OQ-010

### 已完成工作

- 新增 `docs/prd/PRD_20260606_04_策略1验收门v2与组合可行性诊断.md`。
- PRD 明确当前 extended reference run `s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` 在 v2 下为 `rejected`，但拒绝范围只针对当前 top-30 long-only 组合实现，不否定信号家族。
- 按 owner 最新口径固定组合候选为 `target_holdings=10/20/30/40`，明确不包含 `50`；首轮单票权重上限仍为 5%。
- PRD 新增 10 万 CNY、100 股整数手、实际持股数、现金占比、买入跳单率、低价股偏移和 eligible universe benchmark 诊断。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`DECISION_LOG.md` 和本交接文件。

### 重要上下文

- 本文是 PRD03 风险特征训练前置门：先实现只读 `acceptance_gate_v2` 诊断和组合可行性模拟，再决定是否启动第 4 波风险特征训练。
- `10/5%` 理论最多部署约 50% 资金，只作为低仓位 / 高现金 / 集中选股对照；`20/5%` 是 5% 上限下理论满仓边界；`30/5%` 是 current reference；`40/5%` 用于验证更分散组合。
- 本次只写 PRD 和记忆/TODO，不改代码、不运行 BigQuery / Cloud Run。

### 改动文件

- `docs/prd/PRD_20260606_04_策略1验收门v2与组合可行性诊断.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`
- `git diff --check --no-index /dev/null docs/prd/PRD_20260606_04_策略1验收门v2与组合可行性诊断.md`

### 阻塞项

- 无。

### 下一步建议

- review / 合并 PRD。
- 合并后实现只读 `acceptance_gate_v2` 诊断、10/20/30/40 组合可行性模拟和 eligible universe benchmark，再决定是否启动风险特征入模。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: pr96_acceptance_window_review_followup_20260606
相关 issue/PR: PR #96 comment `4638273442`

### 已完成工作

- 查看 PR #96 comment `4638273442`，认可 P3：BQML reference 的风险 maxDD 门原先使用 2025 段 maxDD，而 Python 候选风险门使用 full-period summary maxDD，口径不一致。
- 修改 `scripts/strategy1/diagnose_acceptance_window.py`：
  - BQML reference 仍用 2025 段计算 `total_return` / `benchmark_return` / `excess_return`。
  - BQML risk maxDD 门改为读取 `ads_backtest_performance_summary.max_drawdown` 的 full-period 口径。
  - 报告表同时展示 `test_maxDD` 与 `full_maxDD`，Python 候选 summary 文案改为 `failed_full_period_risk_drawdown_target_count`。
- 重新 uploaded 诊断 artifact 到同一路径：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/acceptance_window_diagnosis/diagnosis_id=riskfeat_acceptance_window_20260606_01`。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和本交接文件。

### 重要上下文

- 修正后结论不变：`primary_blocker=mixed_evidence`。
- BQML historical reference 2025-only：total_return 4.05%、benchmark_return 27.49%、excess_return -23.43%、test maxDD -10.06%、full-period maxDD -14.48%。
- Python 15 个已拒 Top5 候选仍为 10 个 2025 excess 未过、5 个 full-period maxDD 未过。
- comment 中关于 2025 小盘基准暴涨导致 `2025-excess` 门与 maxDD 门冲突的策略解读成立，但这是 owner 需要决策的接受门问题，当前 PR 只修诊断口径，不修改 acceptance contract。

### 改动文件

- `scripts/strategy1/diagnose_acceptance_window.py`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/diagnose_acceptance_window.py`
- `git diff --check`
- `python3 scripts/strategy1/diagnose_acceptance_window.py --project data-aquarium --region asia-east2`
- `gcloud storage ls gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/acceptance_window_diagnosis/diagnosis_id=riskfeat_acceptance_window_20260606_01/`

### 阻塞项

- 无代码阻塞；是否调整 2025 test excess / maxDD 接受门仍需 owner 决策。

### 下一步建议

- review / 合并 PR #96。
- 合并后先让 owner 决定是否调整接受门，再决定是否启动第 4 波风险特征训练。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: v3-replay-fallback-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: strategy1-v3-replay-fallback-fix-20260608
相关 issue/PR: N/A

### 已完成工作

- 在独立工作树 `codex/fix-v3-replay-fallbacks` 中修复 `scripts/strategy1/replay_acceptance_gate_v3.py`，让 `v3` replay 对历史 search 缺失的 `cv_confirmation_status`、`test_rank_ic_mean`、`test_top_minus_bottom_fwd_ret_mean` 使用可追溯 fallback，而不是直接失败。
- `cv_confirmation_status` 的 fallback 采用既有训练期语义：优先读历史原字段；若缺失，则按 `cv_rank_ic_mean > 0` 且 `cv_top_minus_bottom_fwd_ret_mean > 0` 回推，并在存在 `cv_fold_count < 3` 时判 `failed`。
- `test_rank_ic_mean` / `test_top_minus_bottom_fwd_ret_mean` 的 fallback 直接复用原 search orchestrator 的 source-of-truth 公式，从 `ads_model_prediction_daily` + `ads_ml_training_panel_daily` 的 `test` 窗口现算。
- 同步修复 `sql/ml/strategy1/24_qa_acceptance_gate_v3_replay_outputs.sql`：新增临时表汇总这些有效字段，`QA-V3-5` 改成校验“字段存在或可由 source 推导”，`QA-V3-3/4/6/7/8` 也改为复用同一 selected-row 视图，避免 Python replay 和 SQL QA 口径分叉。

### 重要上下文

- 本修复是针对已经实跑暴露出来的 `QA-V3-5` 阻塞：历史 selected rows 的 `metrics_json` 不完整，不是 v3 公式本身错，也不是 benchmark 覆盖缺失。
- 这次明确不回填历史 registry / summary；fallback 只用于 `v3` replay 和其 SQL QA 的只读判定。
- 本轮没有重跑 `replay_acceptance_gate_v3.py` 或 `24_qa_acceptance_gate_v3_replay_outputs.sql`；下一步应先执行这两步，确认 `QA-V3-5` 已解除。

### 改动文件

- `scripts/strategy1/replay_acceptance_gate_v3.py`
- `sql/ml/strategy1/24_qa_acceptance_gate_v3_replay_outputs.sql`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未运行新的 replay。
- 未运行新的 `24_qa_acceptance_gate_v3_replay_outputs.sql`。
- 本次为代码修复与记忆更新。

### 阻塞项

- 无新的实现阻塞；当前待执行的是 replay / QA 复跑。

### 下一步建议

- 重新执行 `scripts/strategy1/replay_acceptance_gate_v3.py`。
- 再执行 `sql/ml/strategy1/24_qa_acceptance_gate_v3_replay_outputs.sql`，确认 `QA-V3-5` 不再因为历史字段缺口失败。
- 若 replay / QA 通过，再继续 live gate cutover。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 交接条目

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: main-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: oq005-alert-checker-live-smoke-20260608
相关 issue/PR: 待创建

### 已完成工作

- 重新部署 `ashare-pipeline-control` 到 Cloud Run revision `ashare-pipeline-control-00003-sfd`，确保镜像已包含 `scripts/alerting`。
- 重新部署 `ashare_ods_ingestion_daily`、`ashare_warehouse_window_refresh` 和 `ashare_pipeline_alert_checker` 三个 workflow；alert checker 当前 revision 为 `000002-31c`。
- 修复 `orchestration/workflows/deploy_scheduler_jobs.sh` 对当前 `gcloud` CLI 的兼容问题：`create http` 仍用 `--headers`，`update http` 改为 `--update-headers`。
- 修复 workflow resolve 阶段对原生 JSON `int/bool` 输入的运行期类型错误：相关 workflow 现在统一使用 `input == null or string(input) == ""` 判空，覆盖 alert-check、ODS、window-refresh 和 full-rebuild 四个 workflow 文件。
- 给 `ashare-workflows-runtime@data-aquarium.iam.gserviceaccount.com` 补 `roles/logging.logWriter`，收口 alert-check endpoint 写 Cloud Logging 时的 `logging.logEntries.create` 403。
- 完成真实 manual smoke：`ashare_pipeline_alert_checker` execution `a2743da9-2654-4521-9222-4fbf2b5dc113` succeeded，返回 `status=no_alerts`、`alerts_count=0`、`log_entries_written=0`。
- 完成真实 Scheduler smoke：job `ashare-pipeline-alert-checker` 已切到 Workflows Executions API，手工 `run` 触发 execution `ca8b6bdd-f137-4727-9311-29b5b8fb9d20`，状态 `SUCCEEDED`。
- smoke 完成后已把 scheduler job 重新置回 `PAUSED`，避免在整体 OQ-005 cutover 前引入双跑。

### 重要上下文

- 这次 live 路径先后暴露了两类真实问题，而且都不是静态检查能抓到的：一是 scheduler deploy 脚本对 `gcloud scheduler jobs update http` 的 flag 使用错误；二是 Workflows resolve 分支对原生 `int/bool` 与空字符串比较导致 execution 直接失败。
- alert checker 新路径本身现在已可用，但当前仍不等于“生产已切走 Composer”；只是证明 `Cloud Scheduler -> Workflows -> ashare-pipeline-control` 技术链路跑通。
- 当前 scheduler job 刻意保留 `PAUSED` 是为了防止 cutover 前双跑，不是因为新路径失败。

### 改动文件

- `orchestration/workflows/deploy_scheduler_jobs.sh`
- `orchestration/workflows/ashare_pipeline_alert_checker.yaml`
- `orchestration/workflows/ashare_ods_ingestion_daily.yaml`
- `orchestration/workflows/ashare_warehouse_window_refresh.yaml`
- `orchestration/workflows/ashare_warehouse_full_rebuild.yaml`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- Cloud Build + Cloud Run deploy：`ashare-pipeline-control-00003-sfd`
- Manual workflow execute success: `a2743da9-2654-4521-9222-4fbf2b5dc113`
- Scheduler-triggered workflow execute success: `ca8b6bdd-f137-4727-9311-29b5b8fb9d20`

### 阻塞项

- 无新的硬阻塞；剩余都是 OQ-005 总体 cutover 范围内未完成项。

### 下一步建议

- 继续做 `ashare_warehouse_full_rebuild` 的可部署方案（async submit+poll 或进一步拆步）。
- 补 `backfill` 与非交易日 skip 的 Workflows smoke。
- 做 shadow run / cutover 验收后，再统一决定何时启用 scheduler job 并删除 Composer 环境。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: risk_feature_acceptance_window_impl_20260606
相关 issue/PR: PR #94 / OQ-010 风险特征入模

### 已完成工作

- 合并 PR #94，并清理不再使用的 PRD worktree、本地分支和远端分支。
- 创建实现工作树 `/Users/luna/Desktop/git/quant-ashare-risk-feature-impl` 和分支 `codex/implement-risk-feature-acceptance-diagnosis`。
- 新增 `scripts/strategy1/diagnose_acceptance_window.py`：
  - 只读 `ashare_ads` 既有 ADS / artifact，不写 ADS。
  - 重切 BQML historical reference `bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01` 的 2025-only 指标。
  - 汇总 `sklearn_native_pvfq_n30_bw_h5_20260605_01`、`cloudrun_python_lgbm_pvfq_n30_bw_h5_20260605_01`、`cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01` 的 Top5 已拒候选。
  - 输出 `acceptance_window_diagnosis.json` / `.md`、`bqml_2025_reference_metrics.json`、`python_candidate_acceptance_window.csv`。
- uploaded 模式已成功上传到 `gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/acceptance_window_diagnosis/diagnosis_id=riskfeat_acceptance_window_20260606_01`。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和本交接文件。

### 重要上下文

- 诊断结论为 `primary_blocker=mixed_evidence`，不是可自动继续训练的 `model_feature_gap`，也不是明确暂停的 `acceptance_window_risk`。
- BQML historical reference 2025-only：total_return 4.05%、benchmark_return 27.49%、excess_return -23.43%、test maxDD -10.06%；full-period maxDD -14.48%。
- 15 个已拒 Python Top5 候选：10 个 2025 excess 未过，5 个 full-period max_drawdown 未过；same-side fraction 66.67% 低于 80% 阈值。
- 脚本读取 `ads_backtest_nav_daily` 时显式使用 `trade_date BETWEEN ...` 分区过滤，符合项目硬约束。
- 后续进入第 4 波 `feature_set_id=strategy1_pv_fin_risk_v0_20260606` 训练前，应先由 owner / 审查者复核本诊断。

### 改动文件

- `scripts/strategy1/diagnose_acceptance_window.py`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/diagnose_acceptance_window.py`
- `git diff --check`
- `python3 scripts/strategy1/diagnose_acceptance_window.py --project data-aquarium --region asia-east2`
- `gcloud storage ls gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/acceptance_window_diagnosis/diagnosis_id=riskfeat_acceptance_window_20260606_01/`

### 阻塞项

- 无代码阻塞；下一步训练决策需要 owner / 审查者复核 mixed-evidence 诊断。

### 下一步建议

- 先 review / 合并本实现 PR。
- 若认可 mixed-evidence 下仍继续特征增强，再实现 PRD Phase B 的 `strategy1_pv_fin_risk_v0_20260606` frozen matrix、`feature_delta_vs_base.json`、候选训练和 `21_qa_risk_feature_search_outputs.sql`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: risk_feature_prd_review_followup_20260606
相关 issue/PR: PR #94 / OQ-010 风险特征入模

### 已完成工作

- 查看 PR #94 comment `4638193883`，认可其中 test 复用、个股风险特征增量、回撤目标和零成本前置诊断建议。
- 修改 `docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md`：
  - 明确本轮是 `model_search_wave_no=4` / `test_reuse_wave_no=4`，accepted 必须 `final_holdout_status='passed'`。
  - 增加 Cloud Run 训练前只读 `acceptance_window_diagnosis`，重切既有 BQML historical reference 的 2025-only 指标并汇总已拒 Python 候选。
  - 明确多数个股风险字段可能已在 base feature set 中，必须输出 `feature_delta_vs_base.json`。
  - 明确 market-state 在 hard-action A/B 中为净负，P0 只作特征，必须单独展示贡献。
  - 将共享 `max_drawdown >= -25%` 定义为拒绝地板，本文风险专项 accepted 目标为 `max_drawdown >= -18%`。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和本交接文件。

### 重要上下文

- 不再新增或扩展 BQML / `sql/ml/strategy1` 策略执行路线；PRD 中涉及 BQML 只读 historical reference 是读取已产出 ADS/GCS artifact，不重跑。
- 若 `acceptance_window_diagnosis` 输出 `primary_blocker='acceptance_window_risk'`，后续实现应先停下让 owner 复核接受门 / 年份区间，不应直接启动第 4 波 Cloud Run 训练。
- 如果继续实现 P0，`21_qa_risk_feature_search_outputs.sql` 需校验 `test_reuse_wave_no=4`、final_holdout passed、`risk_feature_max_drawdown_target=-0.18`、`feature_delta_vs_base.json` 和 `acceptance_window_diagnosis.json`。

### 改动文件

- `docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`
- `git diff --cached --check`

### 阻塞项

- 无。

### 下一步建议

- 等 PR #94 review 通过并合并后，先实现只读 `acceptance_window_diagnosis`，再决定是否启动风险特征 Cloud Run search。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: pr93_deploy_smoke_20260606
相关 issue/PR: PR #93 / OQ-005 scheduler runtime naming cutover

### 已完成工作

- 合并 PR #93 后，从 `main` 同步 `orchestration/composer/dags/ashare_common.py`、`orchestration/composer/dags/ashare_ods_ingestion_daily.py` 和 `sql/observability/01_pipeline_status_views.sql` 到 Composer bucket。
- 重新应用 `sql/observability/01_pipeline_status_views.sql` 到 BigQuery。
- 验证 Composer bucket 文件 SHA256 与本地一致，`dags list-import-errors` 返回 `No data found`。
- 触发 ODS-only skip smoke `manual_pr93_ods_only_skip_20260605_20260606_01`，使用 `business_date=2026-06-05`、`skip_ingestion=true`、`skip_downstream_refresh=true`、`pipeline_dry_run=false`、`require_business_partition=true`。
- smoke 结果：DAG success；Cloud Run ingestion dry/write task 均 skipped；`ods_daily_partition_readiness` success；`trigger_warehouse_window_refresh` skipped；`skip_downstream_refresh` Airflow task success 且 `pipeline_task_status.status='skipped'`；无 linked `ashare_warehouse_window_refresh` run；`v_pipeline_refresh_missing`、`v_alert_summary` 和 `check_alerts.py --lookback-minutes 20 --json` 均为空。

### 重要上下文

- 这次 smoke 只验证显式 ODS-only skip 路径，不替代后续两个开市日 scheduled run 观察，也不替代真实非交易日 scheduled skip 自然观察。
- Cloud Run 最新 `ashare-ingest-current-scope` execution 仍为 PR #80 的 `ashare-ingest-current-scope-rf729`（2026-06-06 01:53 UTC 创建），本次 smoke 未创建新 execution。
- PR #93 远端分支因 `gh pr merge --delete-branch` 的本地 worktree 限制未自动删除，后续已清理。

### 改动文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_common.py orchestration/composer/dags/ashare_ods_ingestion_daily.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/observability/01_pipeline_status_views.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/observability/01_pipeline_status_views.sql`
- `gcloud composer environments run ashare-composer --location asia-east2 dags -- list-import-errors`
- `manual_pr93_ods_only_skip_20260605_20260606_01` Airflow task/state + BigQuery status table checks
- `python3 scripts/alerting/check_alerts.py --lookback-minutes 20 --json`

### 阻塞项

- 无当前部署阻塞。

### 下一步建议

- 等至少两个开市日 scheduled run 自然完成，确认采集成功后自动触发 `ashare_warehouse_window_refresh`。
- 等一个真实非交易日 scheduled skip 自然通过，确认 `skip_non_trading_day` 状态落库且 Cloud Run 未触发。
- 继续 Dataform 生产接入 / shadow 验证和完整 ODS→ADS 运维观测闭环。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: pipeline_runtime_naming_cutover_20260606
相关 issue/PR: PR #91 / PR #93 / OQ-005 scheduler runtime naming cutover

### 已完成工作

- 在 PR #91 合并后的最新 `main` 上创建工作树 `/Users/luna/Desktop/git/quant-ashare-pipeline-cutover-hotfix` 和分支 `codex/pipeline-cutover-refresh-missing-fix`。
- 执行生产 cutover：同步 Composer bucket `data/sql/`、新 DAG / alert checker 和 `check_alerts.py`，清理旧 `oq005_alert_checker.py`、旧命名 QA/metadata SQL 与旧 `oq005_*` metrics。
- 通过 `scripts/alerting/setup_alerts.py --notification-channels ...` 将 Cloud Monitoring policies 迁移为 `Ashare Pipeline: ...`，创建 / 对齐 `ashare_pipeline_*` log-based metrics，并保留 Email 通知渠道。
- 触发 alert checker cutover run 和 `qa_only` run，均成功。
- cutover smoke 暴露 `warehouse_refresh_missing` 对非交易日 skip 的误报，已修改 `sql/observability/01_pipeline_status_views.sql`：`v_pipeline_refresh_missing` 排除 `skip_non_trading_day` 与显式 `skip_downstream_refresh`，避免把预期不触发下游刷新报成异常。
- 将修复后的观测 SQL 应用到 BigQuery，并同步到 Composer bucket `data/sql/observability/01_pipeline_status_views.sql`。
- 按 PR #93 review comment 加固 `skip_downstream_refresh`：新增实体 Python task 显式写 `pipeline_task_status.status='skipped'`，不再依赖 `EmptyOperator` success callback 作为唯一豁免证据；观测视图兼容旧 `success` 与新 `skipped` 两种状态。
- 同步 TODO、IMPLEMENTATION_STATUS、OPEN_QUESTIONS、KNOWN_CONSTRAINTS 和本交接。

### 重要上下文

- `warehouse_refresh_missing` 现在只监控“应该触发下游刷新但完全没有 linked warehouse run”的异常。
- 非交易日 scheduled skip 和显式 ODS-only run 不应触发 warehouse refresh；这类 run 以 `pipeline_task_status` 中的 `skip_non_trading_day=skipped` 或 `skip_downstream_refresh=success/skipped` 作为豁免证据。
- 当前生产告警资源已改为稳定命名：`ashare_pipeline_failure`、`ashare_pipeline_task_failure`、`ashare_pipeline_ingestion_failed`、`ashare_pipeline_warehouse_refresh_missing`、`ashare_pipeline_alert_checker_heartbeat`。
- PR #93 review follow-up 的 DAG 加固已部署到 Composer，并通过 ODS-only skip smoke `manual_pr93_ods_only_skip_20260605_20260606_01` 验证不触发 Cloud Run 或 warehouse refresh。

### 改动文件

- `sql/observability/01_pipeline_status_views.sql`
- `orchestration/composer/dags/ashare_common.py`
- `orchestration/composer/dags/ashare_ods_ingestion_daily.py`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/observability/01_pipeline_status_views.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/observability/01_pipeline_status_views.sql`
- 查询 `data-aquarium.ashare_meta.v_pipeline_refresh_missing` 最新 10 行返回 `[]`。
- 查询 `data-aquarium.ashare_meta.v_alert_summary` 最近 20 分钟窗口返回 `[]`。
- `python3 scripts/alerting/check_alerts.py --lookback-minutes 20 --json` 返回 `[]`。
- `python3 -m py_compile orchestration/composer/dags/ashare_common.py orchestration/composer/dags/ashare_ods_ingestion_daily.py`

### 阻塞项

- 无当前切换阻塞。

### 下一步建议

- 观察新 `ashare_ods_ingestion_daily` 至少两个开市日 scheduled run，确认采集成功后自动触发 `ashare_warehouse_window_refresh`。
- 等待一个真实非交易日 scheduled skip 自然通过，确认 `skip_non_trading_day` 状态落库且 Cloud Run 未触发。
- 继续 Dataform 生产接入 / shadow 验证和完整 ODS→ADS 运维观测闭环。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: tailrisk_p2_market_riskoff_run_20260606
相关 issue/PR: PR #92 / OQ-010 尾部风险 P2

### 已完成工作

- 合并后的 `main` 上物化 `sql/dws/08_dws_market_state_daily.sql`，并跑通 `sql/qa/11_market_state_checks.sql`。
- 构建 Cloud Run runner 镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:tailrisk-p2-6db6bd9-20260606-01`，Cloud Build `564b6223-908c-4123-a7b4-f59e7d5fe8dc` succeeded。
- 将 `strategy1-backtest-report-job` 更新到该镜像，使用 `configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml` 跑完 3 条 P2 portfolio-only A/B。
- 查询 ADS summary、trade、NAV 和 tail-risk summary，完成结果判断，并同步 TODO / memory。

### 重要上下文

- `dws_market_state_daily` 结果：`market_state_v0_20260606` 在 `2024-01-02` 至 `2026-04-30` 窗口共 562 行，risk-off 91 日。
- P2 diagnostic-only：run `s1_tailrisk_p2_diag_pvfq_n30_bw_h5_20260606_01` / backtest `bt_s1_tailrisk_p2_diag_pvfq_n30_bw_h5_20260606_01`，total_return 38.25%、excess_return -4.13% vs `000852.SH`、Sharpe 0.882、max_drawdown -14.46%。
- P2 market-only：run `s1_tailrisk_p2_mkt_pvfq_n30_bw_h5_20260606_01` / backtest `bt_s1_tailrisk_p2_mkt_pvfq_n30_bw_h5_20260606_01`，total_return 28.20%、excess_return -14.18% vs `000852.SH`、Sharpe 0.734、max_drawdown -15.72%，`BUY_SKIPPED_MARKET_RISK_OFF` 217 笔。
- P2 combo：run `s1_tailrisk_p2_combo_pvfq_n30_bw_h5_20260606_01` / backtest `bt_s1_tailrisk_p2_combo_pvfq_n30_bw_h5_20260606_01`，total_return 30.04%、excess_return -12.34% vs `000852.SH`、Sharpe 0.773、max_drawdown -14.71%，market skip 217 笔、tail-risk skip 3 笔。
- 最大回撤窗口均落在 2024-05 至 2024-09；market-only 最大回撤更深。P2 v0 `skip_new_buys` 降低平均仓位和交易成本，但错过买点/反弹，当前不应作为默认策略。
- Tail-risk artifact 成功上传，但路径带 `search_id=...`；summary 表的 `tail_risk_report_uri` 仍为空，这是可追溯性小缺口，不影响本轮结论。

### 改动文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/08_dws_market_state_daily.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/11_market_state_checks.sql`
- `python -m scripts.strategy1_cloudrun.orchestrate_experiments --project data-aquarium --region asia-east2 --manifest configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml --config configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml --stage-id tailrisk_p2 --dry-run`
- Cloud Build succeeded：`564b6223-908c-4123-a7b4-f59e7d5fe8dc`
- Cloud Run executions succeeded：`strategy1-backtest-report-job-fg7kr`、`strategy1-backtest-report-job-p8phq`、`strategy1-backtest-report-job-jnzjc`
- Orchestrator final status：`succeeded`，failure_count 0。

### 阻塞项

- 无执行阻塞。策略结论是 P2 v0 不应默认启用。

### 下一步建议

- OQ-010 继续寻找可接受的 Cloud Run Python baseline：下一模型族、特征增强或训练目标改造优先于启用 P2 v0。
- 若继续做市场风控，单独写 P2 v1 方案，考虑更强但可验证的动作，例如风险仓位缩放、风险恢复条件、或按市场状态切换持股/行业暴露，而不是复用当前 `skip_new_buys`。
- 保留 P1 个股风险过滤作为可继续观察的候选 profile；它改善了回撤但收益仍跑输中证1000。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: oq005_dag_split_prd_20260606
相关 issue/PR: OQ-005 / Composer DAG split PRD

### 已完成工作

- 新建工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-dag-split-prd` 和分支 `codex/oq005-dag-split-prd`。
- 新增 PRD `docs/prd/PRD_20260606_02_OQ005ComposerDAG拆分.md`，定义 OQ-005 多 DAG 目标边界、参数契约、状态观测、迁移顺序、QA 和验收条件。
- 同步 TODO、IMPLEMENTATION_STATUS、OPEN_QUESTIONS、ARCHITECTURE_MEMORY 和 DECISION_LOG；新增 `DECISION-20260606-01`。

### 重要上下文

- 本次只写文档，不改 `orchestration/composer/dags/ashare_daily_pipeline_v0.py`，不部署 Composer，不运行 BigQuery / Dataform / Cloud Run。
- PRD 规定后续先做 production DAG 拆分，再继续 Dataform definitions、补跑 / resume 自动化和完整 ODS→ADS 运维观测闭环；P0 必须包含 `upstream_pipeline_run_id` 跨 DAG 血缘和 refresh-missing watchdog。
- 目标生产拆分的 P0 是 `ashare_ods_ingestion_daily` 与 `ashare_warehouse_window_refresh`；全量重建和研究 DAG 放在后续阶段。

### 改动文件

- `docs/prd/PRD_20260606_02_OQ005ComposerDAG拆分.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check origin/main...HEAD` 通过。

### 阻塞项

- 无。

### 下一步建议

- 实现 Phase B/C/D：抽共享 Composer helper，新增 `ashare_ods_ingestion_daily` 与 `ashare_warehouse_window_refresh`，补 `upstream_pipeline_run_id` 和 refresh-missing watchdog，完成开市日、非交易日和 backfill smoke。
- 生产迁移时先暂停旧 `ashare_daily_pipeline_v0`，再 unpause 新 production DAG；新 DAG 后续连续通过至少两个开市日 scheduled run 和一个非交易日 skip smoke。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: oq005_dag_split_impl_20260606
相关 issue/PR: OQ-005 / Composer DAG split implementation

### 已完成工作

- 在 PRD PR #85 合并后的最新 `main` 上创建工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-dag-split-impl` 和分支 `codex/implement-oq005-dag-split`。
- 新增共享 helper `orchestration/composer/dags/ashare_common.py`，封装 SQL 读取、BigQuery task、Cloud Run ingestion task、runtime conf、非交易日 gate、pipeline/task status 回写、窗口/全量 TaskGroup 和 QA chain。
- 新增 `ashare_ods_ingestion_daily`：每日 20:00 采当前 14 个 ODS endpoint，scheduled 非交易日 skip，ODS readiness 通过后用 `TriggerDagRunOperator` 触发 `ashare_warehouse_window_refresh`；手工 dry-run 或 `skip_ingestion=true` 默认不触发下游。
- 新增 `ashare_warehouse_window_refresh`：支持 `daily_current` / `backfill` 窗口刷新、metadata 恢复、`10_windowed_stock_refresh_checks.sql`、`01-05` QA 和 `qa_only` 只读 QA。
- 新增 `ashare_warehouse_full_rebuild`：手工维护 DAG，无 schedule；必须 `confirm_full_rebuild=true` 且 `date_from/date_to` 必填，`pipeline_dry_run=true` 不执行写入。
- 扩展 `pipeline_run` 元数据字段 `upstream_pipeline_run_id` / `triggered_by_dag_id`；新增 `v_pipeline_refresh_missing`，并将 `warehouse_refresh_missing` 接入 `v_alert_summary` 和 `setup_alerts.py`。
- 按 PR #86 review follow-up 补新 scheduled DAG `is_paused_upon_creation=True`、`ashare_warehouse_window_refresh max_active_runs=1`、refresh-missing watchdog 仅在没有任何 linked warehouse run 时触发。
- 将 Composer README 与 OQ-005 runbook 更新为拆分后的 DAG 入口和手工恢复命令。
- 同步 TODO 与实现状态 / 交接记忆。

### 重要上下文

- 本次只提交仓库文件，未部署 Composer，未运行 BigQuery / Dataform / Cloud Run，未触碰生产 GCS 或 ADS 产物。
- 旧 `ashare_daily_pipeline_v0` 没有在本 PR 中改动，保留为迁移期回滚入口；生产切换时必须先暂停旧 DAG，再 unpause 新 `ashare_ods_ingestion_daily`，迁移期任一时刻只保留一个 production scheduled DAG active。
- P0 使用 `TriggerDagRunOperator` 作为跨 DAG 触发入口，并通过 `upstream_pipeline_run_id` 与 refresh-missing watchdog 做可观测链路；后续如 Composer 版本和运行环境适配，可再升级为 Airflow Datasets。
- `ashare_warehouse_window_refresh` 的 `qa_only` 分支保留旧只读 QA 能力；`ashare_ods_ingestion_daily` 的 ODS-only 手工触发可用 `skip_downstream_refresh=true`。

### 改动文件

- `orchestration/composer/dags/ashare_common.py`
- `orchestration/composer/dags/ashare_ods_ingestion_daily.py`
- `orchestration/composer/dags/ashare_warehouse_window_refresh.py`
- `orchestration/composer/dags/ashare_warehouse_full_rebuild.py`
- `sql/meta/01_create_meta_tables.sql`
- `sql/observability/01_pipeline_status_views.sql`
- `scripts/alerting/setup_alerts.py`
- `orchestration/composer/README.md`
- `docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_common.py orchestration/composer/dags/ashare_ods_ingestion_daily.py orchestration/composer/dags/ashare_warehouse_window_refresh.py orchestration/composer/dags/ashare_warehouse_full_rebuild.py scripts/alerting/setup_alerts.py scripts/alerting/check_alerts.py`
- `git diff --check`

### 阻塞项

- 无代码阻塞。生产启用前必须部署到 Composer 并完成 smoke。

### 下一步建议

- PR 合并后同步新 DAG、`sql/`、观测视图和 `setup_alerts.py` 到 Composer / GCP。
- Composer import 后确认 `ashare_ods_ingestion_daily` 仍为 paused；先暂停 `ashare_daily_pipeline_v0`，再 unpause 新 ingestion DAG。
- 依次验证：开市日 `ashare_ods_ingestion_daily` 真实采集后触发 `ashare_warehouse_window_refresh`；非交易日 `force_non_trading_day_gate=true` 不触发 Cloud Run；手工 `backfill` 小窗口通过；`qa_only` 通过；人工构造 ingestion success 但下游完全未创建 run 时触发 `v_pipeline_refresh_missing` / `warehouse_refresh_missing`。
- 新 DAG 连续通过至少两个开市日 scheduled run 和一个非交易日 skip smoke，旧 `ashare_daily_pipeline_v0` 保持 paused。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: tail_risk_p1_comment_followup_20260606
相关 issue/PR: PR #88 / OQ-010 尾部风险 P1

### 已完成工作

- 拉取并 rebase 到最新 `origin/main`，解决 `.agent/memory/AGENT_HANDOFF.md` 与 `.agent/memory/IMPLEMENTATION_STATUS.md` 的记忆冲突。
- 采纳 PR #88 comment 的两条发现：候选层 P1 风控不能强制卖出已有持仓；必需风险字段 NULL 不能 fail-open。
- 修改 `05_build_candidates.sql`：`individual_risk_guard_v0` 只写 `tail_risk:*` 风险标记，风险标记股票仍参与 TopN / target；必需风险字段 NULL 写 `tail_risk_required_field_null`。
- 修改 Python Ledger v1 与 BigQuery SQL fallback：对 selected tail-risk target，若执行前没有持仓则写 `BUY_SKIPPED_TAIL_RISK` 并跳过新买入；已有持仓不因 P1 标记被强制卖出。
- 更新 `09` 汇总、`10` runner QA、`11` 诊断 SQL、`20` tail-risk QA、报告统计、ADS fill_status 描述、README 和 PRD 正文。
- 按 owner 要求在 `KNOWN_CONSTRAINTS.md` 写入 BigQuery 分区表硬约束：所有启用 `require_partition_filter=TRUE` 的表查询 / DML / 清理 / 断言必须显式带分区列过滤；只按 `run_id` / `backtest_id` 等普通列过滤不满足 BigQuery 必要条件。

### 重要上下文

- 当前 P1 语义保持 PRD 原意：只拦截未持仓新买入，不把已持仓风险股从 target 层强制剔除。
- 短区间 smoke 使用 `--skip-report` 导致 `10_qa_runner_outputs.sql` 的 report guard 按预期失败；这不是 P1 风控逻辑失败。临时 run/backtest 的 ADS 残留已全部清理为 0。
- PR #88 仍需合并部署后跑 full-period `diagnostic_only` vs `individual_risk_guard_v0` A/B。

### 改动文件

- `docs/prd/PRD_20260606_01_策略1尾部风险控制.md`
- `scripts/strategy1/analyze_tail_risk.py`
- `scripts/strategy1/render_report.py`
- `scripts/strategy1_cloudrun/backtest_report.py`
- `scripts/strategy1_cloudrun/ledger.py`
- `sql/ads/01_ads_strategy1_tables.sql`
- `sql/ml/strategy1/05_build_candidates.sql`
- `sql/ml/strategy1/08_run_backtest.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/11_model_quality_diagnostics.sql`
- `sql/ml/strategy1/20_qa_tail_risk_outputs.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python -m py_compile scripts/strategy1_cloudrun/ledger.py scripts/strategy1_cloudrun/backtest_report.py scripts/strategy1/analyze_tail_risk.py scripts/strategy1/render_report.py`
- BigQuery dry-run：`sql/ml/strategy1/05_build_candidates.sql`
- BigQuery dry-run：`sql/ml/strategy1/08_run_backtest.sql`
- BigQuery dry-run：`sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- BigQuery dry-run：`sql/ml/strategy1/10_qa_runner_outputs.sql`
- BigQuery dry-run：`sql/ml/strategy1/11_model_quality_diagnostics.sql`
- BigQuery dry-run：`sql/ml/strategy1/20_qa_tail_risk_outputs.sql`
- 临时 smoke 残留清理查询确认 candidate / target / order / trade / position / nav / summary / monitor 均为 0。

### 阻塞项

- 无代码阻塞；full-period A/B 需等 PR #88 合并并部署新 runner 镜像。

### 下一步建议

- 提交并推送 PR #88 follow-up。
- 合并部署后执行 full-period `diagnostic_only` vs `individual_risk_guard_v0` A/B，重点比较收益、最大回撤、跌停/不可卖暴露、换手、`BUY_SKIPPED_TAIL_RISK` 次数和 acceptance 状态。

### 已更新记忆文件

- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: oq010_tailrisk_p2_market_riskoff_impl_20260606
相关 issue/PR: PR #92 / OQ-010 尾部风险 P2

### 已完成工作

- 在工作树 `/Users/luna/Desktop/git/quant-ashare-tailrisk-p2-market-riskoff`、分支 `codex/implement-tailrisk-p2-market-riskoff` 实现尾部风险 P2 market risk-off。
- 新增 `sql/dws/08_dws_market_state_daily.sql`，生成 `market_state_v0_20260606` 市场状态日表；新增 `sql/qa/11_market_state_checks.sql` 作为市场状态 DWS 门禁。
- Cloud Run Python ledger、SQL fallback `08_run_backtest.sql`、候选生成、汇总、`10` / `11` / `20` QA、中文报告和 tail-risk 诊断均支持 `market_risk_off_v0` / `individual_and_market_risk_guard_v0`。
- 新增 `configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml`，定义复用既有 prediction source、不重新训练的 P2 portfolio-only A/B。

### 重要上下文

- P2 风控动作固定为 `skip_new_buys`：risk-off 执行日只阻止新买 / 加仓，卖出和 pending sell 继续执行。
- risk-off 判定使用 t-1 signal date，执行日写 `BUY_SKIPPED_MARKET_RISK_OFF` 审计行。
- 本次没有实际物化 `dws_market_state_daily`，没有部署新 Cloud Run runner，也没有跑 P2 A/B；这些必须在 PR 合并后继续。

### 改动文件

- `sql/dws/08_dws_market_state_daily.sql`
- `sql/qa/11_market_state_checks.sql`
- `configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml`
- `scripts/strategy1_cloudrun/ledger.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/backtest_report.py`
- `scripts/strategy1/analyze_tail_risk.py`
- `scripts/strategy1/render_report.py`
- `sql/ml/strategy1/05_build_candidates.sql`
- `sql/ml/strategy1/08_run_backtest.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/11_model_quality_diagnostics.sql`
- `sql/ml/strategy1/20_qa_tail_risk_outputs.sql`
- `sql/ads/01_ads_strategy1_tables.sql`
- `sql/ml/strategy1/README.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `docs/数据仓库建模方案-DWS-ADS.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python -m py_compile scripts/strategy1_cloudrun/ledger.py scripts/strategy1_cloudrun/config.py scripts/strategy1_cloudrun/backtest_report.py scripts/strategy1/analyze_tail_risk.py scripts/strategy1/render_report.py`
- P2 manifest 解析：3 个实验均为 portfolio-only，`requires_retrain=false`
- BigQuery dry-run：`sql/dws/08_dws_market_state_daily.sql`、`sql/qa/11_market_state_checks.sql`、`sql/ml/strategy1/05_build_candidates.sql`、`08_run_backtest.sql`、`09_build_metrics_and_report_inputs.sql`、`10_qa_runner_outputs.sql`、`11_model_quality_diagnostics.sql`、`20_qa_tail_risk_outputs.sql`
- `python -m scripts.strategy1_cloudrun.backtest_report --project data-aquarium --region asia-east2 --config configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml --manifest configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml --experiment-id tailrisk_p2_market_riskoff_pvfq_n30_bw_h5_20260606 --dry-run`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- PR 合并后先执行 `sql/dws/08_dws_market_state_daily.sql` 和 `sql/qa/11_market_state_checks.sql`。
- 构建并部署包含 P2 改动的新 Cloud Run runner 镜像。
- 用 `configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml` 跑 diagnostic / market-only / combo 三条 P2 A/B，并比较收益、回撤、skip 笔数和风险暴露。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`


日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01
相关 issue/PR: PR #82 / OQ-010 / PRD04 Cloud Run Python baseline search / Wave 3 `lightgbm_regression`

### 已完成工作

- 合并后构建并部署 PR #79 镜像 `prd04-e54cd54-20260606103115` 到五个策略 Cloud Run Jobs。
- 启动 `lightgbm_regression` wave 3；首次执行因未带 `--build-training-panel`，`ads_ml_training_panel_daily` 对当前 run_id 为空而失败。
- 使用 `--build-training-panel --force-replace` 重跑，训练面板构建成功：3,246,953 行，日期范围 `2019-04-03` 至 `2026-04-30`。
- 定位并修复 `prepare_matrix.py` 在 Cloud Run 中引用函数外局部变量 `candidate_parallelism_arg` 的 NameError；requested parallelism 现显式传入函数并写入 work units / summary。
- 补 `json_dumps_strict()` / `json_compatible()`，确保写入 BigQuery JSON 字符串列前将 NaN / inf 转成 null；清理本轮 5 条 Top5 registry 中已写入的非法 `roc_auc/log_loss` NaN。
- 按 PR #82 review follow-up 补强 strict JSON helper：保留 `default=str` 兜底，将 `pd.NaT` / `pd.NA` / `NaN` / `inf` 转 `null`，支持 `np.ndarray` 和 pandas 标量，并把状态表 `params_json`、GCS lock payload、work-unit manifest/hash 等 runner JSON 路径统一到该 helper。
- 使用 `--resume` 复用已成功的训练和 Top5 回测步骤，完成 comparison artifacts 上传和 acceptance 回写。
- 构建最终镜像 `prd04-7d8daec-20260606-01` 并部署到五个策略 Cloud Run Jobs。
- PR #82 已 rebase 到最新 `main`。

### 重要上下文

- 当前修复不改变 PRD04 搜索口径、候选配置、验收阈值或 Cloud Run 资源口径。
- Wave 3 已完成；不需要重跑训练或回测。
- Wave 3 的更准确结论：regression 信号在 test 期有正向 RankIC 和正 test excess，但回撤风险不达标，且多数候选 final_holdout 明显跑输中证1000。

### 改动文件

- `scripts/strategy1_cloudrun/prepare_matrix.py`
- `scripts/strategy1_cloudrun/bq_io.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/state.py`
- `scripts/strategy1_cloudrun/task_fanout.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check` 通过。
- `py_compile` 覆盖 `bq_io.py`、`train_predict.py`、`prepare_matrix.py`、`orchestrate_cloudrun_python_baseline_search.py`、`orchestrate_sklearn_native_search.py`。
- `prepare_matrix.py --dry-run` 使用 regression manifest 和 `--candidate-parallelism 12` 通过，输出 `candidate_parallelism_requested=12` / `candidate_parallelism_resolved=12`。
- strict JSON sanitizer 小测试通过：NaN / inf / `pd.NaT` 输出为 JSON null，`np.ndarray` 转为 JSON array。
- Cloud Build 镜像 `prd04-318e79f-20260606-01` 和最终镜像 `prd04-7d8daec-20260606-01` 构建成功；最终镜像已部署到五个策略 Cloud Run Jobs。
- Wave 3 真实执行：`prepare_matrix` succeeded；`train_candidate_fanout` 12/12 succeeded；Top5 `select_register_predict` 与 `backtest_report` 全部 succeeded。
- `sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql` 全部断言通过。

### 阻塞项

- 无。

### 下一步建议

- 合并 PR #82 后删除不再使用的本地和远端分支。
- 若继续 PRD04，进入下一模型族或特征增强；重点分析 regression 候选 max drawdown 超过 -25% 的原因。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: 无
相关 issue/PR: OQ-010 / PRD04 Wave 3 regression tail risk follow-up

### 已完成工作

- 新建工作树 `/Users/luna/Desktop/git/quant-ashare-tail-risk-prd` 和分支 `codex/prd-strategy1-tail-risk-diagnostics`。
- 新增 `docs/prd/PRD_20260606_01_策略1尾部风险控制.md` 草案。
- 创建 PR #84，并按 review comment 完成 5 条 follow-up。
- PRD 基于 Wave 3 `lightgbm_regression` Top5 因 `max_drawdown < -25%` 全部 rejected 的复核结论，定义三阶段方案：
  - P0 固定最大回撤诊断 artifact / 报告 / QA，不改变交易结果。
  - P1 `individual_risk_guard_v0` 个股硬风险过滤 profile A/B。
  - P2 依赖 `dws_market_state_daily` 或等价 artifact 的 market risk-off 风控。
- 同步更新 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和本交接文件。
- Review follow-up 内容：P0 改为 ADS 严格只读并要求 pre/post hash；补 P1 风险字段可得性 / PIT 映射；持仓贡献权重口径钉死为 beginning-of-day；跌停主判据改为 DWD / `stk_limit` 派生源标记，收益阈值只作 fallback；补 top-K 回撤事件切分规则。

### 重要上下文

- P0 是诊断能力，不改变模型、候选池、交易、回测或 NAV；P0 禁止写入任何 ADS 核心表，诊断只落 GCS / 本地镜像 / comparison artifact。
- P1/P2 会改变选股或买入动作，必须作为独立实验验收，不能直接替换 PRD04 baseline search 默认口径。
- PRD 推荐 P1 首轮过滤阈值：`ret_20d < -30%`、`drawdown_20d < -30%`、`limit_down_days_20d >= 2`、`one_word_limit_days_20d >= 1`、`total_mv_cny < 30e8`、`circ_mv_cny < 20e8`；`vol_20d p95` 和 `turnover_rate_ma20 p98` 首轮只标记、不默认硬排除。
- P2 首轮推荐动作是 `skip_new_buys`，不是强制清仓或日内止损。

### 改动文件

- `docs/prd/PRD_20260606_01_策略1尾部风险控制.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check` 通过。

### 阻塞项

- 无。

### 下一步建议

- owner review PRD。
- 若认可，先实现 P0 固定最大回撤诊断和 `20_qa_tail_risk_outputs.sql`，用 Wave 3 Top5 回测做验收。
- P0 合并后再单独做 P1 风险过滤 profile A/B。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: cloudrun_python_lgbm_pvfq_n30_bw_h5_20260605_01
相关 issue/PR: PR #79 / OQ-010 / PRD04 Cloud Run Python baseline search review follow-up

### 已完成工作

- 复核 PR #79 comment，采纳 H1/H2/M1/M2/M3/L1/L2，并对 L3 补充运行元数据澄清；L4 不在本 PR 修改，原因是 CV eval-fold orientation 改成 held-in 定向会改变候选排序语义并要求重跑 wave 2。
- 将共享验收契约 `configs/strategy1/model_acceptance_contract_v1.yml` 的关键阈值注入 `18/19` QA，避免 Python acceptance 与 SQL QA 各自硬编码门槛。
- 修复 final_holdout 缺证据口径：缺失 final_holdout 不再 hard rejected，改为 `needs_more_evidence`；实际明显坏结果仍按契约 veto。
- 修复 `18/19` QA 的 NULL 空过问题、补 prediction / backtest 数据上界断言，并将 split 边界对齐 PRD 的 `2024-01-02` / `2025-01-02`。
- 调整 auto-next-wave：当前 wave QA 先执行，下一波失败不再让父 wave 失败。
- 接入 `allowed_score_orientation` 和 `weak_valid_rank_ic_threshold`，补 `unmatched_acceptance_state` 兜底和 QA。
- 根据真实 LightGBM smoke，将 P0 资源口径从 40 并发 / 1 vCPU 4Gi 调整为 40 候选 / 20 并发 / 2 vCPU 8Gi；Cloud Run Job spec `parallelism=20`，manifest 默认不再二次分批。
- 已把 wave 2 ADS metadata / run status 表中的资源、split、contract、convergence 元数据补齐，真实 `18_qa_sklearn_native_search_outputs.sql` 和 `19_qa_cloudrun_python_baseline_search_outputs.sql` 均通过。
- 继续完成 residual follow-up：运行手册部署命令和兜底示例已同步到 `parallelism=20` / `2 CPU / 8Gi`；`config.py`、Python ledger、`01_build_training_panel.sql` 和 `10_qa_runner_outputs.sql` 的 fallback 默认日期已对齐为 `2024-01-02` / `2025-01-02`；`18/19` QA 用 `qa_required()` 包住 remaining `LOGICAL_AND` 条件，单行 NULL 不再被聚合忽略。
- `18/19` QA 的 `DECLARE` 默认仍保留为 standalone fallback；生产和 orchestrator 路径的事实来源是 `configs/strategy1/model_acceptance_contract_v1.yml` 注入，已在 SQL 注释中写明。

### 重要上下文

- 真实 LightGBM binary wave 2 search `cloudrun_python_lgbm_pvfq_n30_bw_h5_20260605_01` 已完成，Top5 均 rejected，当前不建立 `cloud_run_python_baseline_v1`。
- Wave 2 的更准确结论是：valid / test RankIC 有正向证据，但 2025 test top-minus-bottom、2025 中证1000超额和 2026 final_holdout 风险门没有转化为可接受基线；不要再表述为“test 完全反转”。
- PR #79 合并后需要先构建 / 部署包含 review follow-up 的新镜像，再执行 `lightgbm_regression` wave 3。

### 改动文件

- `Dockerfile.strategy1-cloudrun`
- `configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml`
- `configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`
- `scripts/strategy1_cloudrun/acceptance.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/ledger.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1_cloudrun/prepare_matrix.py`
- `scripts/strategy1_cloudrun/select_register_predict.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `sql/ml/strategy1/01_build_training_panel.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`
- `sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- Python `py_compile` 通过。
- `git diff --check` 通过。
- `01_build_training_panel.sql` / `10_qa_runner_outputs.sql` BigQuery dry-run 通过。
- `18_qa_sklearn_native_search_outputs.sql` / `19_qa_cloudrun_python_baseline_search_outputs.sql` BigQuery dry-run 通过。
- Orchestrator dry-run 确认 manifest 默认 `candidate_parallelism=20` 时产生单个 `--tasks=40` train fan-out step，不再拆两批。
- Orchestrator dry-run 确认 wave 3 regression manifest 解析为 12 候选 / 12 并发 / 2 CPU / 8Gi，split 日期为 `2024-01-02` / `2025-01-02`。
- 真实 BigQuery `18` / `19` QA 均通过。

### 阻塞项

- 无。

### 下一步建议

- 合并 PR #79。
- 构建并部署新 Cloud Run runner 镜像。
- 执行 `lightgbm_regression` wave 3；若仍 rejected，再按 PRD04 进入下一模型族或特征增强讨论。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: manual_pr80_daily_current_20260605_20260606_01 / manual_pr80_qa_only_20260605_20260606_01
相关 issue/PR: PR #80 / OQ-005 production deploy and 2026-06-05 smoke

### 已完成工作

- 将 PR #80 后的 `orchestration/composer/dags/ashare_daily_pipeline_v0.py` 同步到 Composer `dags/`。
- 将仓库 `sql/` 同步到 Composer bucket `gs://asia-east2-ashare-composer-b2629133-bucket/data/sql/`。
- 触发 `business_date=2026-06-05`、`warehouse_mode=daily_current`、`pipeline_dry_run=false` 的生产 run，完成 current_scope 采集、ODS readiness、窗口 DIM/DWD/DWS 刷新和窗口 QA。
- 触发 `business_date=2026-06-05`、`warehouse_mode=qa_only`、`skip_ingestion=true` 的独立只读 QA smoke。
- 更新 `orchestration/composer/README.md`，把手动触发默认日期说明改为 `data_interval_end` 口径。
- 更新 TODO 和项目记忆，去掉 PR #80 “待部署 / 2026-06-05 未采集”的过期状态。

### 重要上下文

- 触发生产 run 前，BigQuery ODS strong endpoint 的 `20260605` 分区仍为 0 行；本次 `daily_current` 因此先执行了 current_scope 采集，再通过 readiness 和窗口刷新。
- PR #80 部署后本地 / Composer bucket 哈希一致：DAG SHA256 为 `e3d4e7a75dc64b28ce8d93081922b62f2a77f201bf99b79f684b661570476b31`，`sql/qa/09_ods_daily_partition_readiness.sql` SHA256 为 `52fe8070a9145756775614cc387724dc35d6a45c29d99b4194eed28f4c3ff0c4`。
- OQ-005 未关闭；非交易日自动 skip ingestion / transform gate、Dataform 生产链路、补跑/resume 自动化仍待完成。

### 改动文件

- `orchestration/composer/README.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 ... < sql/qa/09_ods_daily_partition_readiness.sql`
- `manual_pr80_daily_current_20260605_20260606_01`：Airflow terminal state `success`，2026-06-05 strong endpoint 行数为 daily 5514、daily_basic 5514、adj_factor 5526、stk_limit 7634、index_daily 7。
- `manual_pr80_qa_only_20260605_20260606_01`：Airflow terminal state `success`，readiness + P0 / strategy1 / OQ004 / finance / OQ006 五个只读 QA 均 success。
- `2026-06-05` DWD/DWS 主键唯一；`2026-05-11..2026-06-05` 最近 20 个交易日 ODS daily_basic → DWD valuation → DWS valuation 行数均为 110,035，错配天数 0。

### 阻塞项

- 无。

### 下一步建议

- 实现非交易日自动 skip gate：scheduled 非交易日自动跳过 ingestion / transform 并写 `skip_non_trading_day` 状态行。
- 推进 Dataform definitions / BigQuery Studio pipeline 生产链路。
- 做补跑/resume 自动化和完整 ODS→ADS 运维观测闭环。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: manual_verify_oq005_warning_before_assert_20260606_01 / manual_verify_oq005_dryrun_no_warning_20260606_01 / manual_verify_oq005_nontd_weak_suppressed_20260606_01
相关 issue/PR: PR #80 / OQ-005 readiness review follow-up

### 已完成工作

- 复核 PR #80 comment，认可 warning MERGE 没有实际运行验证、strong ASSERT 前未持久化 warning、dry-run 会写 warning、非交易日 weak 缺失会产生噪声等问题。
- 修改 `sql/qa/09_ods_daily_partition_readiness.sql`：先生成 readiness 结果并在非 dry-run 下前置 MERGE warning，再执行 strong endpoint 阻断 ASSERT。
- MERGE 过滤条件改为 API 行数上限风险或交易日 weak `MISSING_REQUIRED`；非交易日 weak 缺失不写 warning。
- 更新 `docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md`、`TODO.md`、`KNOWN_CONSTRAINTS.md`、`OPEN_QUESTIONS.md`、`IMPLEMENTATION_STATUS.md` 和本交接。

### 重要上下文

- 本 follow-up 只改 PR #80 分支内容；后续 PR #80 已合并，并已按上方 2026-06-06 部署交接同步 Composer bucket。
- 该条记录中的 `2026-06-05` ODS strong endpoint 缺失是合并前验证时点事实；后续 `manual_pr80_daily_current_20260605_20260606_01` 已完成 2026-06-05 采集并通过 readiness。

### 改动文件

- `sql/qa/09_ods_daily_partition_readiness.sql`
- `docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `bq query --dry_run` 验证 `sql/qa/09_ods_daily_partition_readiness.sql`。
- `manual_verify_oq005_warning_before_assert_20260606_01`：`2026-06-05` strong 缺失失败前写入 4 条 weak warning。
- `manual_verify_oq005_dryrun_no_warning_20260606_01`：dry-run 强制分区失败后 `pipeline_task_status` 0 行。
- `manual_verify_oq005_nontd_weak_suppressed_20260606_01`：`2026-06-06` 非交易日强门禁失败后 `pipeline_task_status` 0 行。

### 阻塞项

- 无。

### 下一步建议

- PR #80 合并后，同步最新 `sql/qa/09_ods_daily_partition_readiness.sql` 到 Composer bucket，并按生产路径重跑小 smoke。
- 继续实现非交易日自动 skip ingestion / transform gate 和 `skip_non_trading_day` 状态行。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`


日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #78 / OQ-010 / Cloud Run Python baseline search PRD re-review follow-up

### 已完成工作

- 按 PR #78 re-review comment 继续修订 `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`。
- 采纳建议 A：§9.1 和 Phase B 明确共享验收契约 `configs/strategy1/model_acceptance_contract_v1.yml` 必须取代 sklearn native search 的 `decide_acceptance` 和 `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql` 内联阈值；Python acceptance 与 SQL QA 必须通过同一契约版本追溯。
- 采纳建议 B：Wave 3 顺序改为 binary LightGBM rejected 后优先尝试 `lightgbm_regression`，再考虑 XGBoost / HistGradientBoosting / CatBoost 或特征增强。
- 澄清 CV 表述：独立 walk-forward folds 为 2021/2022/2023，2024 是 valid confirmation，不再重复命名为 `cv_2024`。
- 按 owner 最新确认采纳可选加固：新增 `cv_2021`（train `2019-04-03..2020-12-31`，eval 2021）作为第三个独立 CV fold；`cv_2021` 参与三折排序稳定性计算，但不单独一票否决候选。
- 按 owner 最新要求把 P0 候选规模固定为 `candidate_count=40` / `candidate_parallelism=40` / 单 task 1 vCPU / 4Gi，并写入 PRD、TODO 和记忆。
- 真实执行 `gcloud run jobs update strategy1-train-candidate-fanout-job --region=asia-east2 --parallelism=40`，随后 `gcloud run jobs describe` 复核 `parallelism: 40`。
- 同步 `docs/策略1CloudRun训练回测运行手册.md` 的 candidate fan-out job 部署命令，将共享 Job spec parallelism 从 100 收敛到当前 P0 的 40；同步 `docs/prd/PRD_20260605_02_策略1CloudRun轻量Task并发.md` 的当前最大并发说明。
- 不加换手 / 成本硬门；PRD 风险表要求 comparison report 展示 turnover / cost / economic cost watch，待真实候选暴露问题后再纳入共享契约硬阈值。
- 同步更新 `TODO.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和本交接。

### 重要上下文

- 本次只改 PRD/运行手册/记忆/TODO，并更新真实 Cloud Run Job parallelism；未实现 LightGBM 代码、未执行 BigQuery search。
- 后续实现顺序必须先落共享契约并迁移旧 sklearn acceptance / `18_qa`，再实现新的 LightGBM `19_qa` 和 baseline search。

### 改动文件

- `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`
- `docs/prd/PRD_20260605_02_策略1CloudRun轻量Task并发.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `gcloud run jobs describe strategy1-train-candidate-fanout-job --region=asia-east2` 复核 `parallelism: 40`。
- `git diff --check` 通过。

### 阻塞项

- 无。

### 下一步建议

- 合并 PRD 后，按 Phase B 顺序实现：共享契约 / sklearn acceptance 与 `18_qa` 迁移 / LightGBM candidate fan-out / 2021/2022/2023 三折 CV ranking / Top 5 完整回测 / `19` QA。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #78 / OQ-010 / Cloud Run Python baseline search PRD review follow-up

### 已完成工作

- 复核 PR #78 comment，认可验收状态机不完备、accepted/rejected 门槛不一致、阈值与 sklearn native PRD 漂移、2026 final_holdout 过短、单一年份 valid 选高容量候选方差过高、binary objective 与排序评估不完全一致、缺少共享验收契约等问题。
- 修订 `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`：候选排序改为 2021/2022/2023 三折 purged walk-forward CV + 2024 valid confirmation；后续 follow-up 已将 P0 固定为 `candidate_count=40` / `candidate_parallelism=40`，且必须有 CV 证据，否则不得 accepted。
- 重写 §9 接受标准：新增共享验收配置 `configs/strategy1/model_acceptance_contract_v1.yml`，状态机改为互斥完整且机器可校验；补 Sharpe `>=0.70`、max drawdown `>=-25%` 等风险门槛；`RankIC == 0`、`top_minus_bottom == 0`、`test_year_excess_return == 0` 等边界显式 rejected。
- 将 2026 final_holdout 定位改为明显坏结果 veto / holdout watch：不再要求 `final_holdout_excess_return_vs_000852 >= 0`，但 `<= -5pct` 或 `final_holdout_total_return <= -8%` 仍 hard reject。
- 补充 objective 路线：P0 保留 LightGBM binary 兼容当前链路，ranking / regression objective 留作后续波次。
- 同步更新 `TODO.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和本交接。

### 重要上下文

- 未采纳“本轮直接扩展到 2026 年 5 月”：owner 已明确本轮先用到 `2026-04-30`，且 5 月尚未进入 Ledger P1/P2 固定验收窗口。
- 未把 P0 直接切为 `lambdarank`：当前 runner、候选池、报告和 QA 仍以正类概率排序分为契约，ranking objective 需要另行定义按日 group、score 可比性和 QA。
- 本次只改 PRD 和记忆/TODO，未实现代码、未部署 Cloud Run Job、未执行 BigQuery。

### 改动文件

- `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check` 通过。

### 阻塞项

- 无。

### 下一步建议

- 合并 PRD 后，先实现 `configs/strategy1/model_acceptance_contract_v1.yml`，再实现 LightGBM wave 2 candidate fan-out / CV ranking / Top 5 完整回测 / `19` QA。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-010 / Cloud Run Python baseline search PRD

### 已完成工作

- 在独立工作树 `/Users/luna/Desktop/git/quant-ashare-cloudrun-python-baseline-search`、分支 `codex/prd-cloudrun-python-baseline-search` 新增 `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`。
- PRD 固定本轮数据截止 `2026-04-30`，明确不用 2026 年 5 月数据参与本轮模型搜索。
- PRD 固定 train/valid/test/final_holdout 为 `2019-04-03..2023-12-31` / 2024 / 2025 / `2026-01-05..2026-04-30`。
- PRD 固定交易参数、股票池、成本和 Ledger v1，只比较 Cloud Run Python 模型 backend / 模型族 / 参数。
- PRD 将 P0 模型族定为 LightGBM wave 2；PR #78 review follow-up 后已改为 2021/2022/2023 三折 purged walk-forward CV + 2024 valid confirmation 选 Top 5，2025 test 做硬接受门，2026 final_holdout 只做明显坏结果 veto / holdout watch。
- 同步更新 `TODO.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和本交接。

### 重要上下文

- 本次只写 PRD 和记忆/TODO，未实现代码、未部署 Cloud Run Job、未执行 BigQuery。
- 历史 BQML / SQL runner 仍仅作 reference / audit，不得作为后续新增模型搜索路径。
- accepted baseline 建立前，不建议实现月度滚动重训正文改造之外的生产重训逻辑。

### 改动文件

- `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check` 通过。
- 未执行 SQL / Python / Cloud Run。

### 阻塞项

- 无。

### 下一步建议

- 合并 PRD 后，实现 LightGBM wave 2 Cloud Run Python baseline search。
- 若 Wave 2 rejected，再进入 XGBoost / HistGradientBoosting 或补 `dws_market_state_daily` 后重搜。
- accepted baseline 建立后，再改造月度滚动重训 PRD 正文。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: memory archive cleanup

### 已完成工作

- 按 owner 要求整理项目记忆，将 `AGENT_HANDOFF.md` 中较早的 30 条交接追加归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。
- 当前 `AGENT_HANDOFF.md` 保留当前摘要、归档清理交接和最近 3 条交接，降低常规启动读取成本。
- 保留 `DECISION-20260605-03` 与当前 OQ-010 路线：后续不再使用 BQML / `sql/ml/strategy1` SQL runner，历史 BQML 仅作 reference / audit。
- 按 PR #76 review comment，在 `docs/prd/PRD_20260604_02_策略1月度滚动重训.md` 文首补 superseded banner，提示不得按旧 BQML / SQL runner 口径直接实现。

### 重要上下文

- 本次整理记忆文件，并给月度滚动重训 PRD 增加状态 banner；不改代码、SQL 或 BigQuery/GCS 产物。
- 归档是搬运历史交接，不删除审计信息。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`

### 测试 / 验证

- `git diff --check` 通过。

### 阻塞项

- 无。

### 下一步建议

- 后续常规启动只读 `AGENT_HANDOFF.md` 的当前摘要和最近交接；需要审计历史时再读 archive。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-010 / DECISION-20260605-03 / memory-only update

### 已完成工作

- 按 owner 明确指令，将“后续不再使用 BQML 以及 `sql/ml/strategy1` SQL runner”写入项目长期记忆。
- 新增 `DECISION-20260605-03: 策略执行层后续停止使用 BQML 与 SQL runner`。
- 同步约束、项目上下文、实现状态、开放问题和 TODO，使后续 OQ-010 不再把 BQML baseline / SQL runner 作为默认或 fallback 路线。

### 重要上下文

- 历史 BQML baseline、SQL runner、报告和 QA 结果仍保留为 reference / audit，不删除、不改写历史事实。
- BigQuery SQL 仍继续用于 ODS→DIM/DWD/DWS/ADS 数仓转换、metadata、单位契约、QA、状态表和只读分析；本决策只废弃策略执行层 SQL runner。
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md` 仍是旧口径，真正实现前必须先改为 Cloud Run Python / backend-neutral 口径。

### 改动文件

- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 待执行 `git diff --check`。
- 未执行 SQL / Python / Cloud Run，本次仅更新项目记忆。

### 阻塞项

- 无。

### 下一步建议

- 先寻找可接受的 Cloud Run Python 模型 / backend baseline。
- 在实现月度滚动重训前，先改造 `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`，移除 BQML / SQL runner 执行口径。

### 已更新记忆文件

- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01 / s1_bqml_baseline_pvfq_n30_bw_h5_resume_20260604_01
相关 issue/PR: OQ-010 / Ledger v1 P1/P2 2026 extended and resume closeout

### 已完成工作

- 取消误启动的重复 2026 扩展 BigQuery job `bqjob_r2337986e7fdea586_0000019e9752fad3_1`。
- 删除无效 run_id `s1_bqml_baseline_pvfq_n30_bw_h5_ext20260430_v20260605_01` / backtest_id `bt_s1_bqml_baseline_pvfq_n30_bw_h5_ext20260430_v20260605_01` 在 ADS 训练面板、registry、prediction、candidate、portfolio、order 和 backtest 相关表中的残留。
- 复核无效 run 在 10 张相关 ADS 表中均为 0 行。
- 复核已有 P1 extended fresh run：`s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01`，窗口 `2024-01-02` 至 `2026-04-30`。
- 复核已有 P2 resume run：`s1_bqml_baseline_pvfq_n30_bw_h5_resume_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_resume_20260604_01`，从父回测 `2025-12-31` 状态恢复。
- 执行 `sql/ml/strategy1/15_qa_ledger_resume_consistency.sql`，6 个断言全部通过。

### 重要上下文

- Extended fresh run 指标：total_return 35.16%、excess_return -7.22% vs `000852.SH`、Sharpe 0.819、max_drawdown -14.46%。
- 2026 段（`2026-01-05` 至 `2026-04-30`）策略收益 -2.45%；同期中证1000 +10.36%、沪深300 +3.83%、上证50 -1.51%，策略分别跑输 12.81pct / 6.28pct / 0.95pct。
- Resume consistency QA 证明 resume segment 与 full fresh run 在 NAV、现金、日收益、持仓和成交事实上一致。
- 该 BQML baseline 已转为历史 reference / audit；Cloud Run sklearn parity/native acceptance 仍未通过，后续需寻找可接受的 Cloud Run Python baseline。

### 改动文件

- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- BigQuery cleanup DML 成功，删除无效 run 残留。
- BigQuery 计数复核：10 张相关 ADS 表中该无效 run/backtest 均为 0 行。
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/15_qa_ledger_resume_consistency.sql`
- BigQuery 查询复核 extended/resume summary、2026 分段和季度 benchmark 对比。
- `git diff --check`

### 阻塞项

- 无执行阻塞。

### 下一步建议

- 寻找可接受的 Cloud Run Python 模型 / backend baseline。
- 实现月度滚动重训前，先把 `docs/prd/PRD_20260604_02_策略1月度滚动重训.md` 改造为 Cloud Run Python / backend-neutral 口径。
- 继续 OQ-005 Dataform、告警、补跑和运维观测闭环。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: sklearn_native_pvfq_n30_bw_h5_20260605_01
相关 issue/PR: sklearn native search Top5 runtime fix

### 已完成工作

- 在 `main` 部署镜像后启动真实 sklearn native search；补建 `s1_sklearn_native_pvfq_n30_bw_h5_20260605_01` 训练面板 3,055,781 行。
- 确认 `prepare_matrix` 成功（`strategy1-prepare-matrix-job-d697c`，4m04s）和 36 个 candidate task 全部成功（`strategy1-train-candidate-fanout-job-tpl9v`，1m24s）。
- 定位 Top5 后处理两个工程问题：本地 ranking 阶段下载/反序列化 `model.joblib` 不必要；Top5 并发写 `ads_model_registry` 触发 BigQuery 429 table update 限流。
- 修复 ranking-only candidate 加载：orchestrator 本地阶段只下载 `candidate_metrics.json` / `task_status.json`，`load_candidates(load_models=False)` 不要求也不加载 `model.joblib`。
- 修复 BigQuery load 瞬时限流：`load_dataframe` 对 `google.api_core.exceptions.TooManyRequests` 做退避重试。
- 取消不完整 Top5 backtest execution：`strategy1-backtest-report-job-pbr24`、`strategy1-backtest-report-job-mcpmc`、`strategy1-backtest-report-job-44qml`。

### 重要上下文

- 36 candidate 并发训练本身没有失败；失败发生在 Top5 select/register/predict 同时写同一张 ADS 表。
- 本修复需要合并并重建/部署 Cloud Run 镜像后才会影响容器端 select/register/predict。
- 后续可复用已成功的 prepare/fanout artifact，用同一 `search_id` 加 `--resume --force-replace` 重跑 Top5。

### 改动文件

- `scripts/strategy1_cloudrun/bq_io.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1_cloudrun/select_register_predict.py`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/bq_io.py scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py scripts/strategy1_cloudrun/select_register_predict.py scripts/strategy1_cloudrun/train_predict.py`
- 小样例验证 `load_candidates(load_models=False)` 不需要 `model.joblib` 且不调用 `joblib.load`。
- 小样例验证 `load_dataframe` 对 `TooManyRequests` 重试并按 10s/20s 退避。
- `orchestrate_sklearn_native_search --dry-run` 展开 36 candidate / Top5 plan。
- `git diff --check`

### 阻塞项

- 无代码阻塞；需要合并后重建 Cloud Run 镜像并重跑 Top5 才能完成 native search 验收。

### 下一步建议

- 提 PR 并合并本修复。
- 重建并部署 `strategy1-cloudrun-runner` 镜像到 prepare/candidate/select/backtest jobs。
- 用 `search_id=sklearn_native_pvfq_n30_bw_h5_20260605_01` 执行 `orchestrate_sklearn_native_search --resume --force-replace`，重跑 Top5，随后跑 `18` QA 并判断是否接受 sklearn native baseline。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: manual_oq005_alert_checker_heartbeat_global_20260605_01
相关 issue/PR: PR #77 / OQ-005 alert checker liveness deployment follow-up

### 已完成工作

- 在 PR #75 合并后完成 OQ-005 alert checker liveness 生产部署验收，并把仓库脚本与生产状态对齐。
- 修复 `check_alerts.py`，让业务告警与 heartbeat 显式写入 Cloud Logging global resource。
- 修复 `setup_alerts.py`：正确导入 Logging Metrics client / LogMetric，设置 alert policy combiner，threshold / absence filter 统一加 `resource.type="global"`。
- 按 PR #77 review comment 修复告警策略幂等：使用当时旧线上稳定键 `user_labels.oq005_policy` 做幂等，并兼容旧 display name 迁移，避免旧名环境重复创建新旧两份策略。
- 更新 alerting README、TODO 和 OQ-005 记忆状态。

### 重要上下文

- 生产 smoke `manual_oq005_alert_checker_heartbeat_global_20260605_01` 成功；随后 scheduled run 也成功。
- Cloud Logging 中 heartbeat 已确认为 `resource.type=global`、`lookback_minutes=20`、`alerts_count=0`。
- Cloud Monitoring `logging.googleapis.com/user/oq005_alert_checker_heartbeat` 的 global timeSeries 已有点；旧的 `k8s_container` heartbeat 只来自修复前第一次 smoke。PR #91 的 `ashare_pipeline_alert_checker_heartbeat` 是后续 cutover 目标名。
- OQ-005 告警主链路和 checker liveness 均已上线；OQ-005 仍 open，剩余 Dataform 生产链路、补跑与完整 ODS→ADS 运维观测闭环。

### 改动文件

- `scripts/alerting/check_alerts.py`
- `scripts/alerting/setup_alerts.py`
- `scripts/alerting/README.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- Composer manual smoke：`manual_oq005_alert_checker_heartbeat_global_20260605_01` 成功。
- Composer scheduled run 成功。
- Cloud Logging 查询确认 heartbeat 使用 global resource。
- Cloud Monitoring timeSeries 查询确认 `oq005_alert_checker_heartbeat` global metric 有数据点。
- Cloud Monitoring alert policies 查询确认 4 个 OQ-005 policy 均启用并绑定通知渠道。
- 本地 py_compile、`setup_alerts.py --dry-run`、只读 `check_alerts.py --lookback-minutes 20 --json`、观测 SQL dry-run、旧名 policy 匹配断言和 `git diff --check` 均通过。

### 阻塞项

- 无。

### 下一步建议

- 继续 OQ-005 Dataform definitions、补跑自动化、生产 DAG 参数化闭环和 ODS→ADS 运行状态观测。
- 修复 `ashare_daily_pipeline_v0` scheduled run 默认 business_date 口径：每日 20 点定时任务必须跑当天数据，而不是 Airflow `ds` 的上一天。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-010 / PRD04 Cloud Run Python baseline search implementation

### 已完成工作

- 在工作树 `/Users/luna/Desktop/git/quant-ashare-prd04-cloudrun-python-baseline`、分支 `codex/implement-prd04-cloudrun-python-baseline` 实现 `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md` 的 P0 代码路径。
- 新增共享验收契约 `configs/strategy1/model_acceptance_contract_v1.yml`，并让 sklearn native `18_qa` 追溯同一契约版本。
- 新增 LightGBM binary wave 2 manifest（40 候选、默认 40 task）和 LightGBM regression wave 3 manifest（12 候选、默认 12 task）。
- 扩展 Cloud Run Python task fan-out：tree 预处理、LightGBM classifier/regressor、raw/oriented score、CV folds、Top5 ranking、final_holdout 指标、shared acceptance、`needs_more_evidence` 自动进入下一波。
- 新增 `scripts/strategy1_cloudrun/orchestrate_cloudrun_python_baseline_search.py` 入口和 `sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql`。
- 同步运行手册、SQL README、TODO、PROJECT_CONTEXT、IMPLEMENTATION_STATUS、OPEN_QUESTIONS 和本交接。

### 重要上下文

- 本次只完成代码实现和本地/dry-run 验证，未构建/部署新 Cloud Run 镜像，未执行真实 40 候选 search，未生成新的 ADS/GCS search 产物。
- 若真实 LightGBM CV smoke 证明单 task `1 vCPU / 4Gi` 不够，应提高 candidate task 内存并降低并发；运行手册已给出 `8Gi / parallelism=20` 示例。
- 若 wave 2 Top5 无 accepted 且存在 `needs_more_evidence`，orchestrator 会按 manifest 进入 `lightgbm_regression` wave 3。

### 改动文件

- `configs/strategy1/model_acceptance_contract_v1.yml`
- `configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml`
- `configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml`
- `scripts/strategy1_cloudrun/*.py`
- `sql/ml/strategy1/01_build_training_panel.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`
- `sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql`
- `scripts/strategy1/requirements.txt`
- `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python -m py_compile scripts/strategy1_cloudrun/*.py`
- `python -m scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search --config configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml --manifest configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml --build-training-panel --dry-run`
- `python -m scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search --config configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml --manifest configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml --build-training-panel --dry-run`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/01_build_training_panel.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql`
- `git diff --check`

### 阻塞项

- 无代码阻塞；真实 search 需合并后构建/部署新镜像再执行。

### 下一步建议

- 合并 PR 后构建并部署 `strategy1-cloudrun-runner` 镜像到 prepare / candidate / select / backtest jobs。
- 执行 PRD04 wave 2 真实 search；若 candidate task 内存不足，按运行手册升内存并降低并发。
- 根据 Top5 acceptance 结论决定是否建立 `cloud_run_python_baseline_v1` 或进入 `lightgbm_regression` wave 3。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-005 / scheduled non-trading day skip gate

### 已完成工作

- 在新工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-nontrading-skip`、分支 `codex/oq005-nontrading-skip` 实现 `ashare_daily_pipeline_v0` 非交易日 skip gate。
- DAG 在 `pipeline_start_status` 后新增 `non_trading_day_gate`，仅对 scheduled `daily_current` 生效。
- gate 查询 `ashare_dim.dim_trade_calendar` 的 SSE 当日开市状态；非开市日进入 `skip_non_trading_day`，跳过 ingestion、ODS readiness 和 transform，并写 `pipeline_task_status.status='skipped'`。
- 手工触发、`backfill`、`qa_only`、`full_rebuild` 和 legacy full refresh 继续走原链路；上一交易日修复仍必须显式 `backfill`。
- 同步更新 Composer README、OQ-005 runbook、TODO、IMPLEMENTATION_STATUS、ARCHITECTURE_MEMORY、KNOWN_CONSTRAINTS、OPEN_QUESTIONS 和本交接。

### 重要上下文

- 本次只改代码和文档，未部署到 Composer，未触发生产 DAG，未执行 BigQuery。
- 非交易日 gate 依赖 `ashare_dim.dim_trade_calendar` 已有 SSE 当日行；若日历缺行会 fail-closed，不会静默跳过。
- 合并部署后需要用周末/节假日 scheduled 口径 smoke，确认 `skip_non_trading_day` 状态写入且 Cloud Run ingestion 没有触发。

### 改动文件

- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `orchestration/composer/README.md`
- `docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: s1_cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01__lgbm_r03_l63_lr002_n600_leaf300_ff09_bf09_l1_01_l2_1
相关 issue/PR: PR #87 comment 4637582821 / OQ-010 / Tail-risk diagnostics P0

### 已完成工作

- 采纳 PR #87 review comment 三条反馈并直接修复。
- `scripts/strategy1/analyze_tail_risk.py` 新增 `--feature-version`，并在 `fetch_positions_enriched` / `fetch_selection_pool` 对 `dws_stock_feature_daily_v0` join 加 `feat.feature_version = @feature_version`，避免多版本特征表行数扇出；summary / search summary / markdown 同步记录 `feature_version`。
- 修复 `compute_drawdown_windows()` 峰值日期口径：回撤 episode 在 `nav >= peak_nav` 时关闭，但只有 `nav > peak_nav` 才更新 peak，保留首次高点日期。
- `scripts/strategy1_cloudrun/backtest_report.py` 调用尾部风险诊断时传入 experiment 的 `feature_version`；非 ADS guard 类尾部风险诊断失败改为 fail-soft，写 `tail_risk/tail_risk_failure.json` 并跳过 `20`，ADS read-only guard 失败仍 hard fail。
- 同步更新 `sql/ml/strategy1/README.md`、`docs/策略1CloudRun训练回测运行手册.md`、`TODO.md` 和相关记忆。

### 重要上下文

- 本次不改变 candidate、target、order、trade、position、NAV、summary 或 acceptance 结果。
- review follow-up 后，Wave 3 regression Top1 最大回撤窗口峰值日按首次高点口径为 `2024-01-02`，谷底日仍为 `2024-02-07`，回撤 `-34.80%`。
- `backtest_report.py` 的 fail-soft 只适用于尾部风险诊断普通异常；只读 guard 一旦发现 ADS summary / NAV hash 改变仍立即失败。

### 改动文件

- `scripts/strategy1/analyze_tail_risk.py`
- `scripts/strategy1_cloudrun/backtest_report.py`
- `sql/ml/strategy1/README.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python -m py_compile scripts/strategy1/analyze_tail_risk.py scripts/strategy1_cloudrun/backtest_report.py`
- `python scripts/strategy1/analyze_tail_risk.py --help`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/20_qa_tail_risk_outputs.sql`
- `python -m scripts.strategy1_cloudrun.backtest_report --config configs/strategy1/cloudrun_runner_default.yml --manifest configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml --experiment-id cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_search_v0 --dry-run`
- `git diff --check`
- Wave 3 regression Top1 `analyze_tail_risk.py --feature-version strategy1_pv_v0_20260601 --skip-gcs-upload` 本地 artifact smoke 成功。
- 使用脚本 post-guard hash 执行真实 `sql/ml/strategy1/20_qa_tail_risk_outputs.sql`，job id `838dadcb-1d38-41ca-aea2-0cda757e738e`，无异常。

### 阻塞项

- 无。

### 下一步建议

- 合并 PR #87 后构建 / 部署新的 `strategy1-cloudrun-runner` 镜像。
- 对 Wave 3 Top5 统一生成 uploaded `tail_risk/` artifact 和 comparison summary。
- 基于尾部风险证据实现 P1 `individual_risk_guard_v0` profile A/B。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date::2026-06-06 ...`
- `git diff --check`

### 阻塞项

- 无代码阻塞；生产生效需要合并后部署 Composer。

### 下一步建议

- 合并后同步 DAG 到 Composer bucket。
- 触发周末/节假日 scheduled 口径 smoke，验收 `skip_non_trading_day` 状态行、pipeline terminal success 和 Cloud Run ingestion 未触发。
- 继续 OQ-005 Dataform 生产链路和补跑/resume 自动化。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: manual_smoke_skip_non_trading_day_pr83_20260606_02
相关 issue/PR: PR #83 / issuecomment-4637354942 / OQ-005 memory consistency follow-up

### 已完成工作

- 复核 PR #83 review comment `4637354942`，采纳 low finding。
- 修正 `.agent/memory/IMPLEMENTATION_STATUS.md` 已完成区残留的部署等待状态。
- 将几条 OQ-005 历史补充改为明确的部署前记录，并指向后续 PR #70 / PR #80 / PR #83 部署和 smoke 状态，避免和顶部当前状态冲突。

### 重要上下文

- 本次只修项目记忆一致性，不改 DAG / SQL / Python 代码，不重新部署 Composer，不重跑 BigQuery。
- PR #83 DAG 实现和 `manual_smoke_skip_non_trading_day_pr83_20260606_02` 验收结论不变。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `rg` 检查当前 OQ-005 记忆中不再有部署等待语义的自相矛盾状态。
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 继续 OQ-005 Dataform 生产接入 / shadow 验证、补跑/resume 自动化和完整 ODS→ADS 运维观测闭环。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #83 / OQ-005 non-trading day skip gate review follow-up

### 已完成工作

- 复核 PR #83 comment `4637223843`，认可全部 4 条问题。
- 补 `force_non_trading_day_gate=true` smoke-only 显式钩子：普通手工 `daily_current` 仍不自动走 gate，部署验收必须是真正 scheduled run 或显式 smoke hook，普通 `dags trigger` 不算 skip gate smoke。
- 将 `skip_non_trading_day` 从 `EmptyOperator` callback 状态写入改为实体 `PythonOperator`，在 task body 写 `pipeline_task_status.status='skipped'`，并保留 skipped callback 作为最终状态覆盖。
- 日历 gate 查询增加 `COUNTIF(is_open IS NULL)` 与 `COALESCE(LOGICAL_OR(...), FALSE)`；日历缺行或 `is_open` 为空均 fail-closed。
- Runbook 补充 `dim_trade_calendar` 覆盖边界：若未来日历未延展或 `is_open` 为空，需要先采集/刷新 `trade_cal` 与 `dim_trade_calendar`。
- 同步更新 Composer README、OQ-005 runbook、TODO、IMPLEMENTATION_STATUS、ARCHITECTURE_MEMORY、KNOWN_CONSTRAINTS、OPEN_QUESTIONS 和本交接。

### 重要上下文

- 本次只改 PR #83 分支代码和文档，未部署到 Composer，未触发生产 DAG。
- `force_non_trading_day_gate=true` 仅为 smoke-only 测试钩子；上一交易日修复仍必须显式 `backfill`。

### 改动文件

- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `orchestration/composer/README.md`
- `docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date::2026-06-06 ...`
- `git diff --check`

### 阻塞项

- 无代码阻塞；生产生效需要合并后部署 Composer。

### 下一步建议

- 合并后同步 DAG 到 Composer bucket。
- 用真正 scheduled run 或 `force_non_trading_day_gate=true` smoke-only 手工 run 验证 `skip_non_trading_day` 状态行、pipeline terminal success 和 Cloud Run ingestion 未触发。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: manual_smoke_skip_non_trading_day_pr83_20260606_02
相关 issue/PR: PR #83 / OQ-005 scheduled non-trading day skip gate deployment

### 已完成工作

- 将 `main` 快进到 PR #83 merge commit `3723f52`。
- 将 `orchestration/composer/dags/ashare_daily_pipeline_v0.py` 同步到 Composer DAG bucket：`gs://asia-east2-ashare-composer-b2629133-bucket/dags/ashare_daily_pipeline_v0.py`。
- 复核本地与 bucket DAG SHA256 一致：`e4b07ba402716b914bfbd6fe27fa38f97fab8e1c12f6a0bcce9e5fd8c58696af`。
- 用 `business_date=2026-06-06`、`warehouse_mode=daily_current`、`force_non_trading_day_gate=true`、`pipeline_dry_run=true` 触发 smoke `manual_smoke_skip_non_trading_day_pr83_20260606_02`。
- 验证 smoke 成功：`non_trading_day_gate=success`、`skip_non_trading_day=success`、`pipeline_finalize_status=success`、`finish=success`。
- 验证 `pipeline_task_status` 已写入 `skip_non_trading_day status='skipped'`，`pipeline_run.status='success'`。
- 验证 ingestion/readiness/window/full/qa 分支均 skipped，Cloud Run `ashare-ingest-current-scope` 没有新 execution。
- 验证 DAG 当前 active/unpaused、无 import errors；`v_alert_summary` 对本次 smoke 为空。

### 重要上下文

- 首次 smoke `manual_smoke_skip_non_trading_day_pr83_20260606_01` 在 Composer 新旧 serialized DAG 切换窗口内被创建，`non_trading_day_gate` / `skip_non_trading_day` 一度显示 `removed` 且旧 `branch_ingestion` 进入 scheduled。
- 已立即暂停 DAG、确认 Cloud Run 未触发、通过 Airflow API 将该 DagRun 标为 failed，并将 `ashare_meta.pipeline_run` 对应行修正为 `partial`，error_summary 写明被第二次成功 smoke supersede，避免假告警。
- 生产 20:00 scheduled run 当前保持启用；下一次真实周末 scheduled run 仍可作为自然验收补充，但本次 force hook smoke 已验证 skip 分支落库与 Cloud Run 未触发。

### 改动文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `gcloud storage cp` 部署 DAG，并下载回 `/tmp/ashare_daily_pipeline_v0.py.bucket` 做 SHA256 对比。
- Airflow REST API 验证 DAG `is_active=true`、`is_paused=false`、`has_import_errors=false`。
- Airflow task 状态验证 `manual_smoke_skip_non_trading_day_pr83_20260606_02` 成功走 skip 分支。
- BigQuery 查询验证 `pipeline_run` / `pipeline_task_status` 状态。
- Cloud Run execution list 验证最近 execution 仍为 PR #80 的 `manual_pr80_daily_current_20260605_20260606_01_current_scope_write`，本次 smoke 未触发 Cloud Run。
- BigQuery `v_alert_summary` 查询返回空。

### 阻塞项

- 无部署阻塞。

### 下一步建议

- 继续 OQ-005 Dataform definitions。
- 继续补跑/resume 自动化。
- 继续完整 ODS→ADS 运维观测闭环收尾。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: s1_cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01__lgbm_r03_l63_lr002_n600_leaf300_ff09_bf09_l1_01_l2_1
相关 issue/PR: PR #87 / OQ-010 / PRD_20260606_01 / Tail-risk diagnostics P0

### 已完成工作

- 通过 GitHub API squash merge PR #84，合并 `docs/prd/PRD_20260606_01_策略1尾部风险控制.md`，并删除远端 / 本地 `codex/prd-strategy1-tail-risk-diagnostics` 与对应工作树。
- 新建工作树 `/Users/luna/Desktop/git/quant-ashare-tail-risk-impl`，分支 `codex/implement-tail-risk-diagnostics-p0`。
- 新增 `scripts/strategy1/analyze_tail_risk.py`：只读 ADS/DWD/DIM，输出 `tail_risk/` 最大回撤事件、持仓贡献、行业 / 板块贡献、跌停 / 不可卖暴露、选股画像、风险股票名单、search summary、ADS read-only guard 和中文 `tail_risk.md`。
- 修改 `scripts/strategy1_cloudrun/backtest_report.py`：默认在报告、模型诊断和 `12` QA 后执行尾部风险诊断；新增 `--skip-tail-risk` 和 `--search-id`；诊断后自动执行 `20_qa_tail_risk_outputs.sql`，并注入脚本产出的 summary/NAV expected hash。
- 修改 `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`：TopK 回测传递 `search_id`，comparison report 增加最大回撤窗口和跌停仓位峰值，并输出 `tail_risk/search_tail_risk_summary.csv`。
- 新增 `sql/ml/strategy1/20_qa_tail_risk_outputs.sql`：复算最大回撤、持仓覆盖、跌停 / 不可卖权重和 summary/NAV hash，作为 P0 诊断 QA。
- 更新 `sql/ml/strategy1/README.md`、`docs/策略1CloudRun训练回测运行手册.md`、`TODO.md` 和相关记忆。

### 重要上下文

- P0 尾部风险诊断不写 ADS 核心表，不改变任何策略交易结果；artifact 文件存在性由 Python 脚本和 `artifact_manifest.json` 强制，`20` QA 只校验 BigQuery 派生不变量和只读 hash。
- 本地 smoke 使用 Wave 3 regression Top1：最大回撤区间 `2024-01-05` 至 `2024-02-07`，策略回撤 `-34.80%`，同期 benchmark return `-15.47%`，跌停仓位峰值约 `86.46%`（2024-02-05）。
- `candidate_overlap_by_signal_date.csv` / `common_crash_names.csv` 在单候选脚本中保留为空表头；TopK 横向诊断由 orchestrator comparison 生成，包含两两选股重叠、共同选中股票和回撤窗口近似贡献。
- P1/P2 尚未开始：P1 是个股硬风险过滤 profile A/B，P2 依赖 `dws_market_state_daily` 或等价 market state artifact 做 risk-off。

### 改动文件

- `scripts/strategy1/analyze_tail_risk.py`
- `scripts/strategy1_cloudrun/backtest_report.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `sql/ml/strategy1/20_qa_tail_risk_outputs.sql`
- `sql/ml/strategy1/README.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python -m py_compile scripts/strategy1/analyze_tail_risk.py scripts/strategy1_cloudrun/backtest_report.py scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `python scripts/strategy1/analyze_tail_risk.py --help`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/20_qa_tail_risk_outputs.sql`
- `python -m scripts.strategy1_cloudrun.backtest_report ... --dry-run`
- `python -m scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search ... --dry-run`
- Wave 3 regression Top1 `analyze_tail_risk.py --skip-gcs-upload` 本地 artifact smoke 成功。
- 使用脚本 post-guard hash 执行真实 `sql/ml/strategy1/20_qa_tail_risk_outputs.sql`，全部 ASSERT 通过。

### 阻塞项

- 无代码阻塞；生产生效需要合并本实现 PR 并部署 Cloud Run runner 镜像。

### 下一步建议

- 合并本实现 PR 后构建 / 部署新的 `strategy1-cloudrun-runner` 镜像。
- 对 Wave 3 Top5 统一生成 uploaded `tail_risk/` artifact 和 comparison summary。
- 基于尾部风险证据实现 P1 `individual_risk_guard_v0` profile A/B。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: oq005_dag_split_deploy_smoke_20260606
相关 issue/PR: OQ-005 / PR #86 / Composer DAG split production switch

### 已完成工作

- 将 OQ-005 DAG 拆分后的 meta DDL、观测视图、Composer DAG 和仓库 `sql/` 部署到 GCP / Composer bucket。
- 在真实 GCP apply 中修复 `scripts/alerting/setup_alerts.py` 两处兼容问题：log metric 已存在错误识别改为 case-insensitive `already exists`；Monitoring threshold 始终显式设置 `Duration(seconds=...)`，包括 0 秒。
- 创建 / 对齐 `ashare_pipeline_warehouse_refresh_missing` log-based metric 和 `Ashare Pipeline: Warehouse Refresh Missing` alert policy。
- 确认 Composer import errors 为 `[]`，暂停旧 scheduled DAG `ashare_daily_pipeline_v0`，unpause 新 scheduled DAG `ashare_ods_ingestion_daily`。
- 完成三类手工 smoke：非交易日 skip gate、`qa_only`、2026-06-05 1 日 backfill；完成 refresh-missing watchdog synthetic transaction smoke。
- 同步 TODO、IMPLEMENTATION_STATUS、ARCHITECTURE_MEMORY、KNOWN_CONSTRAINTS、OPEN_QUESTIONS 和本交接。

### 重要上下文

- 旧 `ashare_daily_pipeline_v0` 当前已暂停，只作为迁移期回滚参考；新增生产能力不要继续加到旧 DAG。
- 新 production scheduled 入口是 `ashare_ods_ingestion_daily`，每日 20:00 CST 采集当天数据，成功后触发 `ashare_warehouse_window_refresh`。
- `ashare_warehouse_window_refresh` 无 schedule，负责 `daily_current` / `backfill` / `qa_only`，并保持 `max_active_runs=1` 串行。
- 本次没有触发真实 opening-day ingestion→warehouse scheduled run；`manual_split_backfill_20260605_01` 是手工 backfill smoke。

### 改动文件

- `scripts/alerting/setup_alerts.py`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- BigQuery meta DDL 与观测视图 apply 成功。
- Composer DAG import errors 为 `[]`。
- `manual_split_skip_gate_20260606_01` success，`skip_non_trading_day` 状态行落库，Cloud Run execution 未新增。
- `manual_split_qa_only_20260605_01` success，P0 / strategy1 / OQ004 / finance / OQ006 五个只读 QA 均通过。
- `manual_split_backfill_20260605_01` success，窗口刷新和窗口 / P0 QA 均通过；2026-06-05 DWD/DWS 估值链路复核通过。
- refresh-missing synthetic transaction smoke 命中后清理归零，`check_alerts.py --lookback-minutes 20 --json` 返回 `[]`。
- `python3 -m py_compile scripts/alerting/setup_alerts.py` 与 `git diff --check` 通过。

### 阻塞项

- 无阻塞；剩余是 scheduled 自然观察项。

### 下一步建议

- 等新 `ashare_ods_ingestion_daily` 至少两个开市日 scheduled run 自然完成，确认 ingestion success 后自动触发 `ashare_warehouse_window_refresh`。
- 等一个真实非交易日 scheduled run 自然通过，确认 `skip_non_trading_day` 状态行落库且 Cloud Run 不触发。
- 继续 OQ-005 剩余 Dataform 生产接入 / shadow 验证、补跑/resume 自动化和完整 ODS→ADS 运维观测闭环。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: oq005_alert_setup_alreadyexists_followup_20260606
相关 issue/PR: OQ-005 / fd8aefe review follow-up

### 已完成工作

- 评估 `fd8aefe` review：认同 code finding，`create_log_metric()` 不应继续依赖异常 message substring 判断 log metric already exists。
- 在分支 `codex/oq005-alert-logmetric-alreadyexists` 修改 `scripts/alerting/setup_alerts.py`，导入并显式捕获 `google.api_core.exceptions.AlreadyExists`。
- 保留其他异常 fail-fast 行为，不改变告警策略定义、Cloud Monitoring policy 语义或生产调度状态。
- 同步 `IMPLEMENTATION_STATUS.md` 和本交接。

### 重要上下文

- process note 也成立：这次 follow-up 通过分支 / PR 提交，不再直接推 `main`。
- 本分支是对告警配置脚本的稳健性修复；不需要重新部署 Composer DAG，也不触发 BigQuery / Cloud Run。

### 改动文件

- `scripts/alerting/setup_alerts.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/alerting/setup_alerts.py`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 合并 PR 后如需重新应用告警配置，可直接运行 `python scripts/alerting/setup_alerts.py --notification-channels ...`，预期已存在的 log metric 会被类型化 `AlreadyExists` 分支幂等跳过。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: oq005_backfill_resume_helper_20260606
相关 issue/PR: OQ-005 / warehouse refresh backfill-resume automation

### 已完成工作

- 在工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-backfill-resume`、分支 `codex/oq005-backfill-resume` 新增通用补跑脚本 `scripts/pipeline/run_warehouse_refresh.py`。
- 脚本支持 `backfill` 分块计划、`qa-only` 计划、`status` 查询，默认只打印 `gcloud composer ... dags trigger` 计划；只有显式 `--execute` 才触发 Composer。
- `--resume` 查询 `ashare_meta.pipeline_run`，按同一 `warehouse_mode/date_from/date_to` 精确跳过已 `success` 或 `running` 的窗口；`--wait --fail-fast` 支持逐个等待 terminal 状态并在失败时停止。
- PR #90 review follow-up 已补 `--max-execute-runs` 默认 20 个非 skipped run 的执行上限；超过上限时拒绝触发，需缩小日期范围或显式 `--yes`。
- Composer README 与 OQ-005 runbook 已补脚本入口、手工 `gcloud` fallback 和状态查询示例。
- 按 owner 要求在 `KNOWN_CONSTRAINTS.md` 写入：需要代码在工作树中改，改完推 PR。

### 重要上下文

- 文件名使用 `run_warehouse_refresh.py`，不绑定 OQ 编号；OQ-005 只作为当前调度阶段和 runbook 背景保留。
- 本次不部署 Composer、不运行 BigQuery DML、不触发生产 DAG、不修改 Cloud Run / GCS / ADS 产物。
- 后续如需真实补跑，应先不带 `--execute` 生成计划，确认分块窗口和 run id 后再加 `--execute --wait --fail-fast`。

### 改动文件

- `scripts/pipeline/run_warehouse_refresh.py`
- `orchestration/composer/README.md`
- `docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/pipeline/run_warehouse_refresh.py`
- `python3 scripts/pipeline/run_warehouse_refresh.py backfill --date-from 2026-06-03 --date-to 2026-06-04 --chunk-days 1`
- `python3 scripts/pipeline/run_warehouse_refresh.py qa-only --business-date 2026-06-05`
- `python3 scripts/pipeline/run_warehouse_refresh.py backfill --date-from 2026-06-03 --date-to 2026-06-04 --chunk-days 1 --execute --max-execute-runs 1` 返回 2，未触发 Composer。
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- PR 合并后，若需要真实补跑，先用 plan-only 确认窗口，再用 `--execute --wait --fail-fast` 触发。
- 继续 OQ-005 剩余项：新 DAG 至少两个开市日 scheduled run 和一个真实非交易日 scheduled skip 自然观察，Dataform definitions，完整 ODS→ADS 运维观测闭环。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: dataform_definitions_runtime_naming_cleanup_20260606
相关 issue/PR: OQ-005 / Dataform definitions / scheduler runtime naming

### 已完成工作

- 新增 Dataform 首版定义目录：`dataform/workflow_settings.yaml`、`dataform/action_manifest.json`、`dataform/README.md`、`dataform/definitions/**/*.sqlx`。
- 新增生成器 `scripts/dataform/generate_sqlx_from_sql.py`，从 canonical `sql/` 文件生成 SQLX operations / source declarations。
- 按 owner 要求清理调度运行链路阶段性命名：Composer DAG tag、告警 DAG 文件名、告警 metric/policy key、QA task_id、Dataform action/tag、生产 QA / metadata SQL 文件名均改为长期稳定命名。
- 重命名生产 QA / metadata SQL：`01_core_smoke_checks.sql`、`03_index_benchmark_checks.sql`、`05_unit_contract_checks.sql`、`01_core_table_column_descriptions.sql`。
- 同步 runbook、Composer / alerting / Dataform README、SQL README、当前记忆和 TODO 的活动路径。

### 重要上下文

- 本次未部署 Composer / Dataform，未运行 BigQuery DML，未触发 Cloud Run。
- 历史 PRD / archive 中的问题编号可保留为审计记录；运行时命名不得再使用 OQ、Phase、P0/P1 等阶段性编号。
- Dataform 首版目前以 `operations` 包装现有 BigQuery SQL / ASSERT 脚本；生产接入前还需要 shadow / diff 验证和 Composer 调用方式设计。

### 改动文件

- `dataform/**`
- `scripts/dataform/generate_sqlx_from_sql.py`
- `orchestration/composer/dags/ashare_common.py`
- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `orchestration/composer/dags/ashare_ods_ingestion_daily.py`
- `orchestration/composer/dags/ashare_warehouse_window_refresh.py`
- `orchestration/composer/dags/ashare_warehouse_full_rebuild.py`
- `orchestration/composer/dags/ashare_pipeline_alert_checker.py`
- `scripts/alerting/check_alerts.py`
- `scripts/alerting/setup_alerts.py`
- `sql/qa/01_core_smoke_checks.sql`
- `sql/qa/03_index_benchmark_checks.sql`
- `sql/qa/05_unit_contract_checks.sql`
- `sql/metadata/01_core_table_column_descriptions.sql`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 scripts/dataform/generate_sqlx_from_sql.py`
- `npx --yes @dataform/cli compile dataform`：编译通过 31 个 operations。
- `python3 -m py_compile scripts/dataform/generate_sqlx_from_sql.py scripts/alerting/setup_alerts.py scripts/alerting/check_alerts.py scripts/ingestion/run_ingestion_job.py`
- `rg` 确认调度 / alerting / ingestion / QA / metadata / Dataform 范围内无 `oq*`、`OQ-*`、`phase`、旧 `p0_*` task/tag 命中。
- `git diff --check`

### 阻塞项

- 无代码阻塞；生产接入仍需单独实现和 smoke。

### 下一步建议

- 对 Dataform definitions 做 shadow / diff 方案，明确 Composer 如何传 tag / workflow invocation id 并写入 `pipeline_task_status`。
- 部署新命名后的 alert checker DAG 与告警配置前，先确认旧命名资源的迁移 / 清理顺序，避免新旧 policy 并存。
- 新 DAG 继续等待至少两个开市日 scheduled run 和一个真实非交易日 scheduled skip 自然观察。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: prd_strategy1_risk_feature_baseline_20260606
相关 issue/PR: OQ-010 / 策略 1 风险特征入模

### 已完成工作

- 新建工作树 `/Users/luna/Desktop/git/quant-ashare-risk-feature-prd`，分支 `codex/prd-strategy1-risk-feature-baseline`。
- 新增 `docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md`。
- PRD 明确下一轮 OQ-010 不默认启用 P2 v0 `skip_new_buys`，而是把个股尾部风险、市场状态和风险 flag 纳入 Cloud Run frozen matrix。
- 同步 TODO、IMPLEMENTATION_STATUS、PROJECT_CONTEXT、OPEN_QUESTIONS 和本 handoff。

### 重要上下文

- P2 `market_risk_off_v0` / combo A/B 已完成且不采纳为默认策略：market-only total_return 28.20%、max_drawdown -15.72%；combo total_return 30.04%、max_drawdown -14.71%，均弱于 diagnostic-only。
- 新 PRD 默认 `feature_set_id=strategy1_pv_fin_risk_v0_20260606`。
- P0 固定 `tail_risk_profile_id=diagnostic_only`，默认 40 候选 / 20 并发 / 2 vCPU 8Gi，复用 LightGBM binary + regression 和共享 acceptance contract。
- P1 才评估 `candidate_risk_adjustment_profile_id=risk_score_penalty_v0`，并要求与 P0 feature-only 做 A/B。

### 改动文件

- `docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。本文为 PRD，未实现代码、未运行 BigQuery / Cloud Run。

### 下一步建议

- PRD 合并后先实现 backend-neutral training panel / frozen matrix 的风险特征集合，再跑 P0 feature-only risk search。
- 不要直接把 P2 v0 `skip_new_buys` 设为默认策略。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: pr91_dataform_naming_review_followup_20260606
相关 issue/PR: PR #91 / OQ-005 Dataform definitions / scheduler runtime naming

### 已完成工作

- 按 PR #91 review comment 补 `docs/Pipeline-补跑与故障恢复-Runbook.md` 的调度运行命名 cutover checklist。
- `scripts/dataform/generate_sqlx_from_sql.py` 新增 `--check` 模式，用于检查 generated SQLX 是否和 canonical `sql/` / manifest 一致；`dataform/README.md` 补对应命令和 PR 规则。
- `KNOWN_CONSTRAINTS.md` 新增 Dataform 生成物约束：改 manifest 覆盖范围内 canonical SQL 时必须重跑生成器并通过 `--check`。
- 记忆中补充“线上旧名 vs 目标新名”说明：PR #91 尚未部署，2026-06-05 / PR #75 历史线上资源仍按旧 `oq005_*` / `oq005_alert_checker` 名称审计；`ashare_pipeline_*` 是 cutover 后目标稳定名。

### 重要上下文

- 本次仍未部署 Composer / Dataform，未运行 BigQuery DML，未触发 Cloud Run。
- 生产 cutover 必须在同一维护窗口同步 Composer bucket `data/sql/`、新 DAG / alert checker、`ashare_pipeline_*` alert resources，并清理旧 `oq005_*` metrics / policies / checker DAG 文件；新 heartbeat metric 有点前不要视为切换完成。
- Dataform definitions 仍是生成产物，canonical 来源是 `sql/` 和 `dataform/action_manifest.json`。

### 改动文件

- `docs/Pipeline-补跑与故障恢复-Runbook.md`
- `scripts/dataform/generate_sqlx_from_sql.py`
- `dataform/README.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`
- `npx --yes @dataform/cli compile dataform`
- `python3 -m py_compile scripts/dataform/generate_sqlx_from_sql.py`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- PR #91 合并后，按 runbook 在维护窗口执行命名 cutover，并验证 `ashare_pipeline_alert_checker` heartbeat、`qa_only` smoke 和旧 `oq005_*` 资源清理。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: prd_strategy1_lot_aware_ledger_20260606
相关 issue/PR: OQ-010 / 策略 1 整数手交易执行

### 已完成工作

- 新建工作树 `/Users/luna/Desktop/git/quant-ashare-lot-aware-ledger-prd`，分支 `codex/prd-strategy1-lot-aware-ledger`。
- 新增 PRD `docs/prd/PRD_20260606_05_策略1整数手交易执行.md`。
- PRD 明确后续 production acceptance 必须使用 Cloud Run Python `ledger_exec_v1_lot100` 或后续明确升级版，不得用 FLOAT-shares backtest 判定 accepted。
- 按 PR #99 review comment 补充 lot100 Python-only 后不再被现有 Python / SQL parity 覆盖，要求新增 Python 单元 / golden-case 测试独立复算现金、费用、PnL 和 NAV。
- 修正 §5.6.5 的 `min commission` 表述：当前成本 profile 为佣金万一免五，不存在 5 元最低佣金触发条件；现金回退只保留为费用 / 滑点 / 执行价 / 舍入防御性兜底。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`KNOWN_CONSTRAINTS.md`、`OPEN_QUESTIONS.md`、`DECISION_LOG.md` 和本 handoff。

### 重要上下文

- PR #98 已合并，验收门 v2 产物已进入 `main`。
- 当前 extended reference backtest `bt_s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` 的 1291 笔 `FILLED` 成交全部为 FLOAT shares，约 98.2% 四舍五入后也不是 100 股整数倍。
- 新 PRD 固化默认交易规则：买入按 100 股整数手向下取整；清仓卖出允许 odd-lot 全额卖出；部分卖出向下取整到 100 股并保留残股；P0 不做余现金二次分配。
- `15_qa_ledger_resume_consistency.sql` 和 `scripts/qa/run_windowed_refresh_equivalence.py` 不覆盖 lot100；实现时不能只依赖结构性 QA，必须补手工期望值 golden cases。
- 进入下一轮风险特征训练前，必须先实现 lot-aware ledger、补 `23` 或等价 QA、复用当前 prediction stream 跑 `2024-01-02` 至 `2026-04-30` fixed-prediction lot-aware reference，并重跑 acceptance gate v2。

### 改动文件

- `docs/prd/PRD_20260606_05_策略1整数手交易执行.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。本文为 PRD，未实现代码、未运行 BigQuery / Cloud Run。

### 下一步建议

- 合并本文 PRD 后，在实现工作树中实现 Cloud Run Python lot-aware ledger。
- 实现时先补参数 / QA / 报告口径，再跑 fixed-prediction reference；不要直接继续 PRD03 风险特征训练。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

---

## 交接记录：Strategy1 风险特征 wave 4 Cloud Run 真实执行完成

- Date: 2026-06-07
- Agent ID: Codex
- Agent Instance ID: Codex desktop session
- Model: GPT-5 Codex
- Environment: Codex desktop, `/Users/fisher/Desktop/git/quant-ashare`
- Run ID: strategy1_risk_feature_wave4_cloudrun_execution_20260607
- Related issue/PR: owner 已要求创建 PR

### 本轮完成

- 已将误放项目根目录的个人会话包移出仓库，保留在 `~/Downloads` 归档位置；未使用 `.agent/archive/`，未改 `.gitignore`。
- 已确认本地 `main` 到达 `10cbd46c1524888d03c71c643ed7959eb1c998be` 后，在 `codex/fix-riskfeat-training-panel-fields` 上处理 runtime 问题。
- 已构建并部署 Strategy1 runner 镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:riskfeatfix-10cbd46-20260607-04`，digest `sha256:e7d6c5e3c86293046166b8930f6016256fb6f43a46d02be54552b303fc9a6ada`。
- Binary manifest `configs/strategy1/cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_v0.yml` 已完成真实 Cloud Run 执行：`search_id=cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_20260606_01`，`source_run_id=s1_cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_20260606_01`，20/20 fanout 成功，Top5 backtest/report 完成，`19` 和 `21` QA 通过；Top5 全部 rejected，未建立 accepted baseline。
- Regression manifest `configs/strategy1/cloudrun_python_riskfeat_lgbm_regression_pvfq_n30_bw_h5_v0.yml` 已完成真实 Cloud Run 执行：`search_id=cloudrun_python_riskfeat_lgbm_reg_pvfq_n30_bw_h5_20260606_01`，`source_run_id=s1_cloudrun_python_riskfeat_lgbm_reg_pvfq_n30_bw_h5_20260606_01`，20/20 fanout 成功，Top5 backtest/report 完成，`19` 和 `21` QA 通过；Top5 全部 rejected，主要包含 `max_drawdown<-0.25`，未建立 accepted baseline。

### 代码与 SQL 变更

- `sql/cloudrun/strategy1/01_build_training_panel.sql`：补齐 `limit_down_days_20d`、`one_word_limit_days_20d`、`total_mv_cny`、`circ_mv_cny` 的 DWS feature source，并加入 PIT-safe market-state forward-fill。
- `scripts/strategy1_cloudrun/prepare_matrix.py`：将 feature JSON 在 BigQuery 端展开为数值列，按 split 顺序写 transformed features，减少 Cloud Run memory 峰值。
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`：修复 tail-risk enrich alias 冲突，acceptance writeback 改为按 `model_id` 更新并补齐 contract version，同时禁用 BigQuery Storage API dataframe path。
- `sql/ml/strategy1/10_qa_runner_outputs.sql`：`QA-LEDGER-7` 增加 `SELL_SKIPPED_BELOW_LOT_PARTIAL`，覆盖不可交易卖出后次日低于 lot 的合法处理状态。

### 验证

- Binary 风险特征 manifest：真实 Cloud Run fanout 20/20 成功，Top5 backtest/report 完成，`19_qa_cloudrun_python_baseline_search_outputs.sql` 通过，`21_qa_risk_feature_search_outputs.sql` 在 `p_risk_feature_max_drawdown_target=-0.18` 下通过。
- Regression 风险特征 manifest：真实 Cloud Run fanout 20/20 成功，Top5 backtest/report 完成；修复 QA 后手动重跑失败 backtest execution `strategy1-backtest-report-job-jn49x` 成功；`19` QA 通过，`21` QA 在 `p_risk_feature_max_drawdown_target=-0.18` 下通过。

### 后续建议

- Owner 已要求提交当前 `codex/fix-riskfeat-training-panel-fields` 并推送创建 PR；PR #103 已合并到 `main`。
- 当前 wave 4 风险特征 binary/regression 均无 accepted baseline；后续建模应优先评估新模型族、目标函数、样本窗口或 acceptance gate，而不是继续假设本轮风险特征配置可直接晋级。

---

## 交接记录：PR #103 review comment follow-up

- Date: 2026-06-07
- Agent ID: Codex
- Agent Instance ID: Codex desktop session
- Model: GPT-5 Codex
- Environment: Codex desktop, `/Users/fisher/Desktop/git/quant-ashare`
- Run ID: pr103_review_comment_followup_20260607
- Related issue/PR: PR #103

### 本轮完成

- 处理 PR #103 review comment 中认同的 2 个 P2 与 1 个 P3。
- `prepare_matrix.py`：expected feature-set 路径重新读取并校验 `feature_column_list`，且 train split 中任一 expected feature 全空时 fail-fast，避免缺列被 JSON 抽取静默转成全 NaN。
- `sql/cloudrun/strategy1/01_build_training_panel.sql`：新增 `p_market_state_ffill_max_trade_days=5`，market-state forward-fill 只允许沿用最近 5 个源表交易日内的非空值；同时将 `ret_20d`、`drawdown_20d`、`vol_20d` 统一从 `dws_stock_feature_daily_v0` 读取。
- `sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`：`QA-RISK-4` 改查源表 `dws_market_state_daily.csi1000_ret_20d` 缺失率，避免 post-fill 训练面板掩盖源表稀疏。

### 验证

- 本次仅处理 PR comment follow-up，未重新执行 Cloud Run 训练、回测或 BigQuery QA。

### 后续建议

- 如 CI 或 reviewer 要求，可对训练面板 SQL 与 `21` QA 做 BigQuery dry-run，再决定是否需要重建 runner 和局部重跑 matrix。

---

## 交接记录：合并后分支与工作树清理约束扩展

日期: 2026-06-07
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop, `/Users/fisher/Desktop/git/quant-ashare`
Run ID: post_merge_branch_worktree_cleanup_constraint_20260607
相关 issue/PR: owner 直接要求推送到 main

### 已完成工作

- 扩展 `KNOWN_CONSTRAINTS.md` 中已有 PR 合并后分支卫生规则：除删除已合并且不再使用的 `codex/*` 本地分支和对应远端分支外，还必须移除为该分支创建的独立 `git worktree`。
- 明确若对应 worktree 仍有未提交或未合并改动，先暂停并请 owner 决策，不得强删。
- 同步刷新 `AGENT_HANDOFF.md` 当前交接摘要和常规约定。

### 重要上下文

- 本次是项目工作记忆 / 工程约束更新，不涉及代码、SQL、BigQuery、Cloud Run 或生产资源。

### 改动文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- 未运行测试；本次为文档 / 记忆更新。

### 阻塞项

- 无。

### 下一步建议

- 后续合并 PR 后按该约束同步清理本地分支、远端分支和对应独立 worktree。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

## 2026-06-07 上证指数 DWS market-state 补齐

Model: GPT-5 Codex

## 2026-06-08 GPT-5 Codex - post-merge deploy and dry-run smoke

### 本轮完成

- 重新部署 `ashare-pipeline-control`，Cloud Run revision 更新为 `ashare-pipeline-control-00005-mk5`。
- 重新部署 workflows，`ashare_warehouse_full_rebuild` 更新为 revision `000002-e70`。
- 执行 post-merge manual dry-run smoke：`ashare_warehouse_full_rebuild` execution `773f26c1-2a80-41ab-9b85-fa7c208f0342` succeeded。

### 本轮未做

- 没有执行真实 full rebuild 写路径。
- 没有继续做 Cloud Scheduler / IAM bootstrap / shadow run。

### 影响文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 下一步建议

- 继续做 OQ-005 cutover：补 ODS / warehouse 的 Cloud Scheduler 和 IAM bootstrap。
- 然后做 shadow run，观察真实开市日和非交易日各至少 1 个样本。

Model: GPT-5 Codex
运行环境: Codex desktop
Run ID: index_000001_dws_market_state_v1_20260607
相关 issue/PR: PR #106 后续提交

### 已完成工作

- 创建 BigQuery 数据集 `data-aquarium.ashare_backup`，用于保存数仓生产契约变更前的备份表。
- 将修改前 `data-aquarium.ashare_dws.dws_market_state_daily` 复制为 `data-aquarium.ashare_backup.dws_market_state_daily_v0`，并写入表说明，明确其是 2026-06-07 添加上证指数 market-state 覆盖前的 v0 生产快照。
- 修改 `sql/dws/08_dws_market_state_daily.sql`：生产表现在同时输出 `market_state_v0_20260606` 兼容行和 `market_state_v1_20260607` 行；v1 增加 `000001.SH` / `SSE_COMPOSITE` 的 5/20 日收益、20 日回撤、20 日波动、20/60 日均线偏离字段。
- 修改 `sql/qa/11_market_state_checks.sql`：默认检查 `market_state_v1_20260607`，并检查默认窗口内 legacy v0 与 current v1 每个交易日各一行。
- 将 `sql/dws/08_dws_market_state_daily.sql` 与 `sql/qa/11_market_state_checks.sql` 接入 `dataform/action_manifest.json` 并重新生成 SQLX。
- 将 `ashare_warehouse_window_refresh` 的 `windowed_transform` 链路补为：指数 DWD 窗口刷新 -> 指数窗口 QA -> 股票 DWD/DWS 窗口刷新 -> 股票窗口 QA -> market-state DWS 重建 -> market-state QA。
- 更新 DWS/ADS 设计文档、架构记忆、实现状态和 TODO。

### 重要上下文

- 本次没有把上证指数纳入 `is_risk_off` / `risk_off_trigger_count` 的触发逻辑，只补 DWS 字段和 v1 版本行，避免静默改变 P2 v0 risk-off 历史结论。
- 既有 runner/config 仍可继续指定 `market_state_v0_20260606`；如后续训练要使用新增上证指数字段，应显式切到 `market_state_v1_20260607` 或另建 feature-set 变更。
- 生产 `dws_market_state_daily` 已用更新后的 SQL 重建成功；`sql/qa/11_market_state_checks.sql` 已更新但本轮未单独执行 QA。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`
- `dataform/action_manifest.json`
- `dataform/definitions/assertions/11_market_state_checks.sqlx`
- `dataform/definitions/dws/08_dws_market_state_daily.sqlx`
- `docs/数据仓库建模方案-DWS-ADS.md`
- `orchestration/composer/dags/ashare_common.py`
- `sql/dws/08_dws_market_state_daily.sql`
- `sql/qa/11_market_state_checks.sql`

### 测试 / 验证

- `python3 scripts/dataform/generate_sqlx_from_sql.py`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/08_dws_market_state_daily.sql`

### 阻塞项

- 无。

### 下一步建议

- 如 owner 需要，可单独执行 `bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/11_market_state_checks.sql` 做 market-state QA。
- 合并部署后同步 Composer bucket 的 `data/sql/` 与 `ashare_common.py`，再触发一次 `ashare_warehouse_window_refresh` 小窗口 smoke 或等待下一次 scheduled refresh。

---

## 2026-06-08 PR #106 review follow-up

Model: GPT-5 Codex
运行环境: Codex desktop
Run ID: pr106_review_followup_market_state_window_20260608
相关 issue/PR: PR #106

### 已完成工作

- 处理 PR #106 review 的 P2：新增 `sql/incremental/03_refresh_market_state_window.sql`，用 `business_date/date_from/date_to/warehouse_mode` 计算写入窗口，向前读取 80 个 SSE 交易日覆盖 20/60 日滚动指标，并用 `MERGE` 更新 `ashare_dws.dws_market_state_daily`，不再在 daily/backfill 路径全表 `CREATE OR REPLACE`。
- `orchestration/composer/dags/ashare_common.py` 的 `build_windowed_transform_group` 已把 `market_state_dws` 从 `sql/dws/08_dws_market_state_daily.sql` 改为 `sql/incremental/03_refresh_market_state_window.sql`，并传入 `_window_refresh_parameters()`；`sql/dws/08_dws_market_state_daily.sql` 只作为初始化 / full rebuild 路径。
- 处理 PR #106 review 的 P3 设计点：`market_state_v0_20260606` 行的 `sse_composite_*` 字段保持 `NULL`，`market_state_v1_20260607` 行才填充上证指数指标；`sql/qa/11_market_state_checks.sql` 新增断言 legacy v0 不得填充 SSE Composite 字段。
- 处理 PR #106 review 的 P3 ODS URI 漂移点：新增 `scripts/ingestion/generate_index_external_table_uris.py`，从 `configs/ingestion/ods_current_scope_v0.yml` 生成 `sql/ods/01_index_external_table_uris.sql`，并支持 `--check` 防止 index endpoint 配置与 external table URI SQL 漂移。
- 重新生成 Dataform SQLX，并更新 DWS/ADS 文档、架构记忆、实现状态和 TODO。

### 重要上下文

- 本次只改代码 / 文档 / 记忆；没有重新执行 BigQuery DWS 重建或 QA。
- 若要让生产 BigQuery 表体现 v0 上证字段为 NULL 的新语义，需要重新执行 `sql/dws/08_dws_market_state_daily.sql` 或按覆盖窗口执行 `sql/incremental/03_refresh_market_state_window.sql`，随后跑 `sql/qa/11_market_state_checks.sql`。
- `sql/ods/01_index_external_table_uris.sql` 以后不要手改 URI 列表；新增指数 endpoint 应先改 `configs/ingestion/ods_current_scope_v0.yml`，再运行 `scripts/ingestion/generate_index_external_table_uris.py`。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`
- `dataform/definitions/**`
- `docs/数据仓库建模方案-DWS-ADS.md`
- `orchestration/composer/dags/ashare_common.py`
- `scripts/ingestion/generate_index_external_table_uris.py`
- `sql/dws/08_dws_market_state_daily.sql`
- `sql/incremental/03_refresh_market_state_window.sql`
- `sql/ods/01_index_external_table_uris.sql`
- `sql/qa/11_market_state_checks.sql`

### 测试 / 验证

- `scripts/ingestion/generate_index_external_table_uris.py`
- `python3 scripts/dataform/generate_sqlx_from_sql.py`

### 阻塞项

- 无。

### 下一步建议

- 如 owner 要求生产即时落地，执行 market-state 全量或窗口刷新并跑 `11_market_state_checks.sql`。
- 更新 PR #106 正文 / 回复 review comment，说明三条 comment 已处理。

---

## 2026-06-08 index benchmark QA 日期上限修复

Model: GPT-5 Codex
运行环境: Codex desktop
Run ID: fix_index_benchmark_qa_date_bound_20260608
相关 issue/PR: 待创建 PR

### 已完成工作

- PR #106 合并后，生产 `dws_market_state_daily` 已重建并通过 `sql/qa/11_market_state_checks.sql`（`QA-MKT-0..9` 全部 successful）。
- Composer 已同步 PR #106 相关 SQL 与 `ashare_common.py`，并触发 smoke `manual_pr106_market_state_window_smoke_20260605_20260608_01`。
- smoke 中 `index_dwd_window`、`windowed_index_refresh_checks`、`stock_dwd_dws_window`、`windowed_stock_refresh_checks`、`market_state_dws`、`market_state_checks` 均 success。
- smoke 后置 `qa_after_window.index_benchmark_checks` 暴露默认 `dwd_end_date = CURRENT_DATE('Asia/Shanghai')` 问题：2026-06-08 当天 000001.SH ODS/DWD 未到数时，backfill smoke 被误判为“000001.SH 未覆盖每个 2019+ SSE 开市日”。
- 新分支 `codex/fix-index-benchmark-qa-date-bound` 已修复 `sql/qa/03_index_benchmark_checks.sql`：默认 `dwd_end_date` 改为 `dwd_index_eod` 中 `000001.SH` 已有完整 price + dailybasic 的最新 SSE 开市日，并新增 `dwd_end_date` 非空 / 不早于 `dwd_start_date` 断言。
- 同步生成 `dataform/definitions/assertions/03_index_benchmark_checks.sqlx`。

### 重要上下文

- 该修复不降低 000001.SH 覆盖质量门，只是把默认检查终点从“不确定的今天”改成“DWD 中已完整落库的最新可用日期”。
- 若后续需要强制检查某个最新业务日，应通过补齐 ODS/DWD 后再运行 QA，或显式改参数化版本；不要把调度默认恢复为 `CURRENT_DATE`。
- 当前仍有未跟踪临时文件 `scripts/ingestion/backfill_index_000001.py`，本修复未纳入该文件。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`
- `dataform/definitions/assertions/03_index_benchmark_checks.sqlx`
- `sql/qa/03_index_benchmark_checks.sql`

### 测试 / 验证

- `python3 scripts/dataform/generate_sqlx_from_sql.py`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/03_index_benchmark_checks.sql`

### 阻塞项

- 无。

### 下一步建议

- 提 PR 并合并后，同步 `sql/qa/03_index_benchmark_checks.sql` 到 Composer bucket。
- 重新触发或等待当前 smoke retry，让 `qa_after_window.index_benchmark_checks` 使用新口径通过。

---
Date: 2026-06-08
Model: GPT-5 Codex
Branch: codex/implement-composer-exit
Summary:
- Added first implementation slice for OQ-005 Composer exit on a dedicated worktree branch.
- Added thin `ashare-pipeline-control` Cloud Run service for pipeline status writeback, bundled SQL execution, SSE trading-day gate, and GCS-backed orchestration locks.
- Added Workflows definitions for `ashare_ods_ingestion_daily` and `ashare_warehouse_window_refresh` with explicit per-task status writes and synchronous child workflow invocation.
- Added deployment scaffolding and directory README for the workflows migration path.
Files:
- scripts/pipeline_control/__init__.py
- scripts/pipeline_control/requirements.txt
- scripts/pipeline_control/state.py
- scripts/pipeline_control/service.py
- orchestration/workflows/Dockerfile.pipeline_control
- orchestration/workflows/cloudbuild.pipeline_control.yaml
- orchestration/workflows/deploy_pipeline_control_service.sh
- orchestration/workflows/deploy_workflows.sh
- orchestration/workflows/README.md
- orchestration/workflows/ashare_ods_ingestion_daily.yaml
- orchestration/workflows/ashare_warehouse_window_refresh.yaml
- sql/meta/01_create_meta_tables.sql
Open follow-ups:
- Migrate `ashare_warehouse_full_rebuild` to Workflows with the same hard constraints.
- Migrate `ashare_pipeline_alert_checker` off Composer.
- Add Cloud Scheduler jobs, runtime IAM bootstrap, and shadow-run / cutover scripts.
- Review Workflows YAML semantics against PRD hard constraints before deployment.
Validation:
- Not run in this turn by owner instruction.

---
Date: 2026-06-08
Model: GPT-5 Codex
Branch: codex/implement-composer-exit
Summary:
- Addressed PR #110 review P2 items and one additional runtime blocker in the control service.
- Added explicit Workflow `http.post` timeout for `/v1/tasks/bigquery` and increased warehouse lock lease headroom.
- Wired lock lease semantics end-to-end in seconds and made lock endpoints backward-compatible with current workflow payload shape while resolving generation by owner when omitted.
- Fixed `/v1/tasks/bigquery` to accept the current flattened workflow payload as context, not only nested `context` form.
Files:
- orchestration/workflows/ashare_ods_ingestion_daily.yaml
- orchestration/workflows/ashare_warehouse_window_refresh.yaml
- scripts/pipeline_control/service.py
- scripts/pipeline_control/state.py
Open follow-ups:
- Consider adding Workflow execution liveness checks before stale-lock reclaim if phase 1 runtime shows lock-expiry edge cases.
Validation:
- Not run in this turn by owner instruction.

---
Date: 2026-06-08
Model: GPT-5 Codex
Branch: codex/implement-composer-exit
Summary:
- Addressed PR #110 re-review runtime bug in the lock compatibility path.
- Fixed `lock_generation_for_owner` to construct the GCS blob and read lock content correctly before deriving generation by owner.
- This restores the intended heartbeat/release path for workflows that omit explicit `generation` and rely on backward-compatible `lock_name`/`owner` payloads.
Files:
- scripts/pipeline_control/state.py
Validation:
- Not run in this turn by owner instruction.

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: composer-exit-next-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: oq005-composer-exit-next-20260608
相关 issue/PR: 待创建 PR

### 已完成工作

- 把 Composer 过渡态的 `ashare_pipeline_alert_checker` 调整为每小时 1 次：DAG schedule 改为 `0 * * * *`，`check_alerts.py` lookback 改为 `70` 分钟。
- 补了 cutover 后的小时级告警检查骨架：`ashare-pipeline-control` 新增 `/v1/tasks/alert-check`，并新增 `orchestration/workflows/deploy_scheduler_jobs.sh`，用 `Cloud Scheduler` 以 OIDC 调用 Cloud Run。
- 同步把 `scripts/alerting/setup_alerts.py` / `scripts/alerting/README.md` / `orchestration/composer/README.md` / `orchestration/workflows/README.md` 改到小时级口径。
- 补出 `orchestration/workflows/ashare_warehouse_full_rebuild.yaml` 工作流草案，并把部署脚本接上该 workflow。
- 确认 `airflow_monitoring` 是 Composer 平台托管健康监控 DAG，不是项目可控调度项；无法在仓库代码中降到每小时，只能在 cutover 后随 Composer 环境删除而消失。

### 重要上下文

- 这轮没有部署新的 Cloud Run service / Workflow / Scheduler job，也没有跑新的 smoke；当前变更仍停留在代码和记忆层。
- `ashare_warehouse_full_rebuild` 当前只是草案。`scripts/pipeline_control/state.py` 的 BigQuery 执行仍同步等待 `job.result()`，full rebuild 长 SQL 可能超过 Cloud Run request timeout 或 Workflows step timeout；在改成 submit + poll 或进一步拆步之前，不应部署到生产。
- owner 对告警链路的要求现在已经固化为“最多每小时 1 次”。后续如果还有频率相关需求，迁移后的 `Cloud Scheduler` 配置应继续沿用同一上限。

### 改动文件

- `orchestration/composer/dags/ashare_pipeline_alert_checker.py`
- `orchestration/composer/README.md`
- `orchestration/workflows/README.md`
- `orchestration/workflows/deploy_workflows.sh`
- `orchestration/workflows/deploy_scheduler_jobs.sh`
- `orchestration/workflows/ashare_warehouse_full_rebuild.yaml`
- `scripts/alerting/README.md`
- `scripts/alerting/setup_alerts.py`
- `scripts/pipeline_control/requirements.txt`
- `scripts/pipeline_control/service.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未运行新的本地测试。
- 未部署新的 Cloud Run / Workflows / Cloud Scheduler。
- `airflow_monitoring` 不可调频这一点基于官方 Composer 文档确认，不是本地代码推断。

### 阻塞项

- `ashare_warehouse_full_rebuild` 仍受控制层同步 `job.result()` 设计限制，未解决前不能安全部署。

### 下一步建议

- 先决定 `ashare_warehouse_full_rebuild` 是改控制层为 submit + poll，还是继续拆成更小、可轮询的 SQL 步骤。
- 把 `ashare_pipeline_alert_checker` 的 Cloud Scheduler job 和 `ashare-pipeline-control` alert-check endpoint 做一次真实部署 / smoke。
- 再继续补 `backfill` / 非交易日 skip smoke 和 cutover runbook，收口 Composer exit。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - PR #113 review 已确认上一版 bool 白名单过宽：`risk_*` 6 列与 `is_*` 4 列在 training panel JSON 中是数字 `1.0/0.0` 或 `1/0`，不能按 `BOOL` 解包。
> - 已将 Strategy1 Cloud Run `BOOLEAN_FEATURE_COLUMNS` 收窄为仅 4 个 `has_fin_*`；它们继续走 `BOOL -> INT64`，其余 `risk_*` / `is_*` 恢复走 `FLOAT64`。
> - 这次是针对 review 的最小纠偏，不改 runner 其他逻辑；现有 PR #113 需以这版为准，上一条 handoff 中“新增布尔特征时同步更新布尔清单”仍成立，但布尔清单只应收录真实 JSON 布尔字段。

## 2026-06-08 - GPT-5 Codex
- Date: 2026-06-08
- Model: GPT-5 Codex
- Branch: `codex/cloudrun-boolfix-benchmark-smoke`
- Summary: 修复 Strategy1 Cloud Run `prepare_matrix` 把 JSON 布尔特征按 `FLOAT64` 解包而导致矩阵构建失败的问题，并完成 `000001.SH` 主 benchmark 下的 `12` 候选 LightGBM regression smoke。
- Files: `scripts/strategy1_cloudrun/feature_sets.py`, `scripts/strategy1_cloudrun/prepare_matrix.py`
- Validation: Cloud Run smoke `search_id=cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_smoke_20260608_05` 成功；Top1 `lgbm_r03_l63_lr002_n600_leaf300_ff09_bf09_l1_01_l2_1` 的最终 artifact 已写出 `benchmark_sec_code=000001.SH` 和 `*_vs_primary_benchmark` 路径结果。
- Notes: 本地 `gcloud` 若需继续追 execution describe，需显式绑定 `CLOUDSDK_PYTHON` 到仓库运行时的 Python 3.10+；这是工作站环境事项，不属于仓库代码变更。
- Next Steps: 继续基于当前 `v1` 门做下一轮模型/特征搜索；`v2` 路径后续忽略。

## 2026-06-08 - GPT-5 Codex
- Date: 2026-06-08
- Model: GPT-5 Codex
- Branch: `codex/cloudrun-boolfix-benchmark-smoke`
- Summary: 处理 PR #113 review，纠正 Strategy1 Cloud Run JSON 布尔特征白名单过宽的问题，避免把 10 个数值型 `risk_*` / `is_*` 特征静默解码为 `NULL`。
- Files: `scripts/strategy1_cloudrun/feature_sets.py`
- Validation: 基于 `sql/cloudrun/strategy1/01_build_training_panel.sql` 的字段类型复核，确认仅 4 个 `has_fin_*` 是 JSON 布尔；`risk_*` 为 `1.0/0.0`，`is_*` 为 `1/0`，必须继续走数值解包路径。
- Notes: 这是对同一 PR 的后续修复，未重跑新的 Cloud Run smoke；现有 smoke 结果只说明链路跑通，不再作为这 10 个字段解码正确性的证据。
- Next Steps: push 到 PR #113，并按该 review 结论继续后续搜索。

## 2026-06-08 - GPT-5 Codex
- Date: 2026-06-08
- Model: GPT-5 Codex
- Branch: `main`
- Summary: 新增策略 1 验收门 `v3` 切换实施 PRD，明确当前仍是 `v1` 主写回门，后续直接 `v1 -> v3`，不经过 `v2`。
- Files: `docs/prd/PRD_20260608_02_策略1验收门v3切换实施.md`
- Validation: 文档级变更；未改代码、未跑 Cloud Run、未跑 BigQuery QA。
- Notes: `v3` 当前仍是 doc + replay gate，不是 production write-back gate。实现前置顺序已经固定为 contract -> replay -> QA -> live cutover。
- Next Steps: 新增 `configs/strategy1/model_acceptance_contract_v3.yml`，再实现 `v3` replay 和对应 QA。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - 已在独立 worktree `/Users/fisher/Desktop/git/quant-ashare-v3-contract`、分支 `codex/implement-v3-contract` 落下 `configs/strategy1/model_acceptance_contract_v3.yml`。
> - 本轮只完成 Phase A：把 `v3` 的 benchmark、复利、Sharpe / Calmar、五指数相对门和除零规则写成 contract；没有实现 replay、QA 或 live cutover。
> - 当前 live write-back gate 仍是 `v1`；下一步应该直接读取该 contract 去实现只读 replay。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - 已继续在同一独立 worktree 上实现 Phase B/C：新增 `scripts/strategy1/replay_acceptance_gate_v3.py` 与 `sql/ml/strategy1/24_qa_acceptance_gate_v3_replay_outputs.sql`。
> - `v3 replay` 当前是独立只读 artifact 路径，不会覆盖历史 `v1` report、comparison artifact 或 `accepted/rejected`。
> - 本轮仍未执行 replay 或 `24` QA；下一步若要继续，应先做一次只读 replay / QA 实跑，再决定 live cutover。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - PR #116 review follow-up 已修三点：`inf` Sharpe/Calmar 不再被误判 gate 失败；信号质量门改为读取 contract 的 `operator`；指数复合年化收益改为沿用策略有效收益期的同一交易日步长。
> - 我没有把 `24` 做成“读取 replay artifact 数值对账”的 QA；当前 `24` 仍是源数据/公式不变量 QA。这是本 PR 仍保留的边界。

## 2026-06-08 - GPT-5 Codex
- Date: 2026-06-08
- Model: GPT-5 Codex
- Branch: `codex/implement-v3-contract`
- Summary: 新增 `configs/strategy1/model_acceptance_contract_v3.yml`，把 PR #114 已冻结的策略 1 `v3` 规则正式落成唯一事实来源，不提前实现 replay、QA 或 live gate 切换。
- Files: `configs/strategy1/model_acceptance_contract_v3.yml`
- Validation: 未运行新的 Cloud Run、BigQuery QA 或 replay；本轮仅完成 contract 与记忆/TODO 同步。
- Notes: `v3` contract 已包含 `000001.SH` 主 benchmark、五指数 `sec_code`、复利年化、`Sharpe >= 0.70`、`Calmar > 1`、`Final holdout 交易日数 >= 40`、五指数同指数相对门，以及 `max_drawdown` / `Sharpe` / `Calmar` / `Excess Calmar` 的符号与除零约定。
- Next Steps: 基于该 contract 实现只读 `v3` replay，并新增 `v3` QA；在 replay + QA 完成前，不切 live search 默认 gate。

## 2026-06-08 - GPT-5 Codex
- Date: 2026-06-08
- Model: GPT-5 Codex
- Branch: `codex/implement-v3-contract`
- Summary: 新增 `v3` 只读 replay 脚本和 `24` 号 BigQuery QA，把五次正式搜索的 `v3` 重评路径落成独立 artifact / SQL 骨架，但仍不改 live gate。
- Files: `scripts/strategy1/replay_acceptance_gate_v3.py`, `sql/ml/strategy1/24_qa_acceptance_gate_v3_replay_outputs.sql`, `sql/ml/strategy1/README.md`
- Validation: 未运行 replay、未执行 `24` QA、未跑 Cloud Run；本轮只完成代码/SQL/文档与记忆同步。
- Notes: `v3 replay` 保持只读，不覆盖历史 `v1` 结论；`24` QA 只校验源数据和公式不变量，不回填 ADS 状态。
- Next Steps: 先按 `model_acceptance_contract_v3.yml` 真实跑一遍 replay 和 `24` QA，再决定是否开始 live cutover。

## 2026-06-08 - GPT-5 Codex
- Date: 2026-06-08
- Model: GPT-5 Codex
- Branch: `codex/implement-v3-contract`
- Summary: 处理 PR #116 review follow-up，修正 `v3 replay` 中 `inf` absolute gate 语义、信号门 operator 读取和指数年化的同策略有效交易日口径。
- Files: `scripts/strategy1/replay_acceptance_gate_v3.py`, `sql/ml/strategy1/24_qa_acceptance_gate_v3_replay_outputs.sql`
- Validation: 未执行 replay、未执行 `24` QA；本轮只修实现与 SQL 口径。
- Notes: `24` 仍是源数据/公式不变量 QA，不是读取 replay artifact 做数值对账的 artifact QA。
- Next Steps: 继续看 PR #116 剩余 comment；若 owner 要求再加 Python-vs-SQL 数值对账，需要单独引入 replay 结果对账路径。

## 交接条目

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: main-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: pr115-oq005-review-followup-20260608
相关 issue/PR: PR #115

### 已完成工作

- 将 PR #115 rebase 到最新 `main` 的冲突收敛方案落到文档与记忆层，准备去掉已合入 `main` 的 `v3` PRD 噪音。
- 在 OQ-005 PRD、`OPEN_QUESTIONS.md`、`IMPLEMENTATION_STATUS.md`、`TODO.md` 中补齐 alert checker 新路径的 IAM 前提：Scheduler caller service account 必须具备目标 workflow 的 `roles/workflows.invoker`，Workflows runtime service account 必须保留 `ashare-pipeline-control` 的 `roles/run.invoker`。
- 明确 `main` 上现有 `orchestration/workflows/deploy_scheduler_jobs.sh` 仍是被放弃的 `Scheduler -> authenticated Cloud Run` 直连实现；在改写为 Workflows Executions API 之前视为 `superseded / do-not-run`。
- 在 `DECISION_LOG.md` 追加持久决策 `DECISION-20260608-13`，固定 OQ-005 alert checker cutover 路径与上述 IAM / deploy 约束。

### 重要上下文

- 本次仍是 OQ-005 doc-only follow-up，不改实现代码、不部署 GCP 资源、不跑 smoke。
- comment 的核心问题不是业务逻辑，而是避免把 `Scheduler -> Cloud Run` 的 live `403` 风险平移到 `Scheduler -> Workflows` 却不写清新的 IAM 前提。
- 另一个重点是 PR 可评审性：分支必须 rebase 到最新 `main`，避免把已合并的 `docs/prd/PRD_20260608_02_策略1验收门v3切换实施.md` 继续夹带在 PR #115 里。

### 改动文件

- `docs/prd/PRD_20260608_01_OQ005调度完全迁出Composer.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未运行代码测试。
- 本次只做文档 / 记忆 / rebase 冲突收敛；待 rebase 完成后再推回 PR。

### 阻塞项

- 仍需完成 `git rebase --continue`、推送分支，并确认 PR #115 文件列表已不再包含已合入 `main` 的 `v3` PRD。

### 下一步建议

- 完成 rebase 并 force-push PR #115。
- 复核 PR #115 的文件列表只剩 OQ-005 相关文档 / 记忆改动。
- 等 owner 再看 comment；后续实现 PR 再真正改 `deploy_scheduler_jobs.sh` 与 alert checker workflow。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 交接条目

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: main-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: oq005-alert-checker-workflow-impl-20260608
相关 issue/PR: 待创建

### 已完成工作

- 新增 `orchestration/workflows/ashare_pipeline_alert_checker.yaml`，把 `ashare_pipeline_alert_checker` 从“Scheduler 直连 Cloud Run”改成“Scheduler -> Workflows -> ashare-pipeline-control”的实现骨架。
- PR #117 review follow-up 后，alert-check workflow 已收敛为“参数归一 + 调 `/v1/tasks/alert-check` + 失败直接抛出”，不再写 `pipeline_run` / `pipeline_task_status`，避免自指告警和观测污染。
- 将 `orchestration/workflows/deploy_workflows.sh` 扩展为同时部署 `ashare_pipeline_alert_checker`。
- 将 `orchestration/workflows/deploy_scheduler_jobs.sh` 从直连 `ashare-pipeline-control` 的 OIDC 调用改为调用 Workflows Executions API 的 OAuth 调用；默认 job 目标 workflow 为 `ashare_pipeline_alert_checker`。
- 更新 `orchestration/workflows/README.md` 与 `scripts/alerting/README.md`，把 alert checker 的迁移目标路径统一为 `Cloud Scheduler -> Workflows -> ashare-pipeline-control`。
- 同步更新 `IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`TODO.md`，把 alert checker 的当前状态推进到“代码已实现，部署/真实 smoke 待执行”。

### 重要上下文

- 这次只做实现代码和项目记忆更新，没有部署 Cloud Run / Workflows / Cloud Scheduler，没有跑真实 smoke。
- `deploy_scheduler_jobs.sh` 现在不再依赖 `PIPELINE_CONTROL_URL`，而是直接调用 `workflowexecutions.googleapis.com`；对应 caller service account 仍需具备目标 workflow 的 `roles/workflows.invoker`。
- `ashare_pipeline_alert_checker.yaml` 内部调用 `/v1/tasks/alert-check` 仍沿用 Workflows -> Cloud Run 的 OIDC 模式，因此 Workflows runtime service account 仍需保留 `ashare-pipeline-control` 的 `roles/run.invoker`。

### 改动文件

- `orchestration/workflows/ashare_pipeline_alert_checker.yaml`
- `orchestration/workflows/deploy_workflows.sh`
- `orchestration/workflows/deploy_scheduler_jobs.sh`
- `orchestration/workflows/README.md`
- `scripts/alerting/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未运行测试。
- 未做部署。
- 未做 manual workflow execute 或 Cloud Scheduler fire smoke。

### 阻塞项

- 仍需真实部署 `ashare_pipeline_alert_checker` workflow。
- 仍需给 Scheduler caller service account 补 `roles/workflows.invoker`（若当前 caller 尚未具备）。
- 仍需做至少一次 manual execute 和一次真实 Scheduler 触发，确认 heartbeat / alert log / control service 调用链正常。

### 下一步建议

- 部署更新后的 workflow 和 scheduler job。
- 做一次 manual workflow execute，再做一次真实 Scheduler fire。
- smoke 通过后，停用 Composer DAG `ashare_pipeline_alert_checker`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 交接条目

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: main-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: oq005-full-rebuild-and-smokes-20260608
相关 issue/PR: 待创建

### 已完成工作

- 将 `scripts/pipeline_control/state.py` / `service.py` 的 BigQuery 控制面从同步 `job.result()` 扩展为 async `submit + poll`，新增 `/v1/tasks/bigquery/submit` 和 `/v1/tasks/bigquery/poll`。
- 将 `orchestration/workflows/ashare_warehouse_full_rebuild.yaml` 的 BigQuery helper 全量切到 async `submit + poll`，并把 full rebuild 共享写锁 lease 提高到 `21600s`。
- 更新 `orchestration/workflows/README.md` 与 `deploy_workflows.sh`：`ashare_warehouse_full_rebuild` 不再被描述为“未就绪草案”，但仍保持 `DEPLOY_FULL_REBUILD=true` 的 manual opt-in 部署。
- 重新部署 `ashare-pipeline-control` 到 revision `ashare-pipeline-control-00004-b2g`。
- 部署 `ashare_warehouse_full_rebuild` workflow 到 revision `000001-36a`。
- 完成 direct async control-plane smoke：通过 Cloud Run 认证调用 `/v1/tasks/bigquery/submit` + `/poll`，成功轮询只读 QA job `fd1f6751-4861-4685-8377-e7dd9843ff57` 到 `DONE/success`。
- 完成 `ashare_warehouse_full_rebuild` manual dry-run smoke：execution `cb8d1267-2909-4bf6-b725-29c6c8ee17e1` succeeded。
- 完成 `ashare_warehouse_window_refresh` 的 `backfill` smoke：execution `7cfbf799-1ace-4440-8577-95ddd45e7645` succeeded。
- 完成 `ashare_ods_ingestion_daily` 的非交易日 skip smoke：execution `29121fdb-8452-4398-85f1-052708ac7cb7` succeeded。

### 重要上下文

- 本轮没有执行一次真实 `ashare_warehouse_full_rebuild` 写路径；只做了 async 控制面只读 smoke 和 workflow `pipeline_dry_run=true` smoke。原因不是代码未就绪，而是一次真实 full rebuild 会重建整套 warehouse，破坏面太大，不适合作为默认验证。
- `ashare_pipeline_alert_checker` 的 Scheduler job 仍保持 `PAUSED`，以避免整体 cutover 前双跑；本轮没有改这个状态。
- `ashare_ods_ingestion_daily` / `ashare_warehouse_window_refresh` 的 live smoke 现在已覆盖 `qa_only`、`daily_current`、`backfill` 和非交易日 skip 四条关键分支。

### 改动文件

- `scripts/pipeline_control/state.py`
- `scripts/pipeline_control/service.py`
- `orchestration/workflows/ashare_warehouse_full_rebuild.yaml`
- `orchestration/workflows/deploy_workflows.sh`
- `orchestration/workflows/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 重新部署 `ashare-pipeline-control`：revision `ashare-pipeline-control-00004-b2g`
- 部署 `ashare_warehouse_full_rebuild` workflow：revision `000001-36a`
- direct async control-plane smoke：BigQuery job `fd1f6751-4861-4685-8377-e7dd9843ff57` success
- `ashare_warehouse_full_rebuild` dry-run smoke：execution `cb8d1267-2909-4bf6-b725-29c6c8ee17e1` success
- `ashare_warehouse_window_refresh` backfill smoke：execution `7cfbf799-1ace-4440-8577-95ddd45e7645` success
- `ashare_ods_ingestion_daily` 非交易日 skip smoke：execution `29121fdb-8452-4398-85f1-052708ac7cb7` success

### 阻塞项

- 无新的技术阻塞。
- OQ-005 仍未 cutover；剩余是 scheduled 入口、shadow run 和删除 Composer 环境。

### 下一步建议

- 补 ODS / warehouse scheduled cutover 的 Cloud Scheduler job 与 IAM bootstrap。
- 做 shadow run，并至少观察 2 个自然开市日和 1 个自然非交易日。
- cutover 验收后删除 Composer 环境，真正停止固定 `Cloud Composer` 底座费用。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
> 当前交接补充（2026-06-08，GPT-5 Codex）
> - `ashare_warehouse_full_rebuild` 已不再是仅限本地草案：`ashare-pipeline-control` 新增 BigQuery async `submit + poll`，control service 已升到 revision `ashare-pipeline-control-00004-b2g`，`ashare_warehouse_full_rebuild` workflow 已部署为 revision `000001-36a`。
> - 本轮没有跑真实全量 rebuild，但已完成两层低风险验证：direct async control-plane smoke 成功轮询只读 QA job `fd1f6751-4861-4685-8377-e7dd9843ff57`，manual dry-run execution `cb8d1267-2909-4bf6-b725-29c6c8ee17e1` succeeded。
> - `ashare_warehouse_window_refresh` 的 `backfill` execution `7cfbf799-1ace-4440-8577-95ddd45e7645` 和 `ashare_ods_ingestion_daily` 的非交易日 skip execution `29121fdb-8452-4398-85f1-052708ac7cb7` 也都已 success；OQ-005 剩余项现在收敛为 scheduled cutover 的 Cloud Scheduler / IAM bootstrap、shadow run 和最终删除 Composer 环境。
> - PR #120 review follow-up 已继续加固 full rebuild：poll 循环未完成时也会 `heartbeat_lock`，不再把锁存活建立在“单个 step < 6h lease”的隐含假设上；`get_job(...)` 瞬时失败改为控制面内部重试，且不再直接把 task status 写成 failed。workflow 侧也补了 `submit/poll` HTTP retry、max-poll 上限和 `location` 透传。

## 2026-06-08 GPT-5 Codex - PR #120 second review follow-up

### 本轮完成

- `scripts/pipeline_control/state.py`：`poll_sql_task(...)` 现在在 `get_job(...)` 内部重试全部耗尽后，会显式把对应 task 写成 `failed`，避免 `pipeline_task_status` 长时间残留 `running`。
- `orchestration/workflows/ashare_warehouse_full_rebuild.yaml`：新增 workflow 输入 `bigquery_max_polls`，默认 `1440`，并透传到所有 `run_bigquery_task` 调用点。
- `orchestration/workflows/README.md`、`.agent/memory/KNOWN_CONSTRAINTS.md`：补充当前 control-plane poll 重试的同步阻塞约束，说明单次 `/v1/tasks/bigquery/poll` 最坏会额外阻塞约 `15s`。

### 本轮未做

- 没有重新部署 `ashare-pipeline-control`。
- 没有重新部署 `ashare_warehouse_full_rebuild` workflow。
- 没有新跑 smoke / real rebuild。

### 影响文件

- `scripts/pipeline_control/state.py`
- `orchestration/workflows/ashare_warehouse_full_rebuild.yaml`
- `orchestration/workflows/README.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 下一步建议

- 推回 PR #120 并继续看 review。
- 若 comment 收敛，可再决定是否需要做一次只读 dry-run / deploy smoke 来闭环这轮失败终态与 `bigquery_max_polls` 输入化。

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

## 2026-06-08 GPT-5 Codex - PR #121 review follow-up

### 本轮完成

- `bootstrap_scheduler_iam.sh` 不再给 `ashare-workflows-runtime` 授项目级 `roles/run.developer`；改为对 `ashare-ingest-current-scope` 单授 job-level `roles/run.invoker`，并在脚本里显式移除旧的项目级 `run.developer` 绑定。
- `cutover_scheduler_jobs.sh` 改为更安全的 staged 顺序：先用 `ENABLE_JOBS=false` 创建/更新 paused Scheduler jobs，再 pause Composer 业务 DAG；只有显式 `RESUME_SCHEDULER_JOBS=true` 才会 resume。
- `README.md`、`KNOWN_CONSTRAINTS.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`TODO.md` 已同步更新到新的 least-privilege / staged-cutover 语义。

### 本轮未做

- 没有重新触发 ODS / warehouse scheduler execution。
- 没有处理 review 提到的 lock bucket 前缀最小化问题；当前仍沿用整桶 `roles/storage.objectAdmin`。

### 原因说明

- 对 lock bucket 的 minor 我认同风险判断，但这已经从“Scheduler cutover 修正”扩展成“锁桶/存储边界重构”。当前 PR 先收敛 runtime SA 的 Cloud Run 过权和 cutover 顺序；桶级最小化建议后续单开处理更稳。

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


---

## Archived from active AGENT_HANDOFF during 2026-06-10 memory cleanup

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 分支 `codex/annual-training-panel-plan` 从最新 `origin/main@d8ac505` 新开，未复用旧 annual worktree 的脏改。
> - annual rolling resolved plan 已显式把 `build_training_panel_risk_feature` 放到每年第一步，命令通过 `python -m quant_ashare.strategy1.sql_runner` 运行 catalog SQL step，后面才是 prepare/fanout/select/backtest。
> - 旧 `/Users/fisher/Desktop/git/quant-ashare-annual-rolling-exec` 中的 2021 后续 smoke 只作为历史证据记录：它发生在 `main@f57ff0a` / 旧 runner image 时代，不代表当前线上 package entrypoint 状态。
> - 本轮不修改 Cloud Run job spec、不重建镜像、不执行 BigQuery / Cloud Run 写入；下一步是 PR 合并后按新 plan 跑完整 `2021-2026` 年度滚动并用 continuous ledger 评价。

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - Annual rolling training panel plan

### 已完成工作

- 从 `origin/main@d8ac505` 新建干净 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-annual-training-panel-plan`，分支 `codex/annual-training-panel-plan`。
- 新增 `scripts/strategy1_cloudrun/training_panel.py`，把 training panel SQL 参数生成逻辑从 native search 中抽为共享 helper。
- 新增 package CLI `quant_ashare.strategy1.sql_runner`：`--step` + `--params-json-b64` 执行 catalog SQL step，支持 `--output-dataset-role` 和 `--dry-run`；`scripts.strategy1_cloudrun.sql_runner` 只保留兼容 re-export。
- 修改 `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`：年度 command plan 第一项固定为 `build_training_panel`，使用 `build_training_panel_risk_feature`，后续才进入 prepare matrix、candidate fanout、select/register/predict 和可选 yearly diagnostic backtest/report。
- 更新 `configs/strategy1/active_step_catalog.yml`，把 `build_training_panel_risk_feature` caller 补充为 annual rolling orchestrator。
- 更新运行手册、TODO 和实现状态；旧 annual worktree 的 2021 后续 smoke 仅作为历史证据记录，未原样搬运。

### 重要上下文

- 旧 annual worktree `/Users/fisher/Desktop/git/quant-ashare-annual-rolling-exec` 仍落后最新 main 且有 3 个脏记忆/TODO 文件；本轮不继续把它作为开发源。
- 历史 smoke 证据发生在 `main@f57ff0a` / 旧 runner image 时代，只证明当时 2021 单年链路可跑，不代表当前线上部署状态。
- 本 PR 不修改线上 Cloud Run job spec、不重建镜像、不执行真实 BigQuery / Cloud Run 写入。

### 改动文件

- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `src/quant_ashare/strategy1/sql_runner.py`
- `src/quant_ashare/strategy1/reporting.py`
- `scripts/strategy1_cloudrun/sql_runner.py`
- `scripts/strategy1_cloudrun/training_panel.py`
- `configs/strategy1/active_step_catalog.yml`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `docs/策略1CloudRun训练回测运行手册.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1_cloudrun/test_dataset_role_routing.py::test_annual_rolling_command_plan_uses_package_entrypoints`：通过。
- `PYTHONPATH=src python3 -m pytest -q tests/strategy1_cloudrun/test_dataset_role_routing.py tests/strategy1/test_retired_lint.py`：27 passed。
- `PYTHONPATH=src python3 -m pytest -q tests/strategy1_cloudrun`：35 passed。
- `PYTHONPATH=src python3 -m pytest -q tests/strategy1_cloudrun tests/strategy1/test_sql_render.py tests/strategy1/test_research_contract.py tests/strategy1/test_retired_lint.py`：64 passed。
- `PYTHONPATH=src python3 -m pytest -q tests/strategy1_cloudrun tests/strategy1/test_sql_render.py tests/strategy1/test_research_contract.py tests/strategy1/test_retired_lint.py tests/strategy1/test_package_boundaries.py`：68 passed。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.sql_runner --help`：通过。
- `PYTHONPATH=src python3 - <<'PY' ...`：确认 `scripts.strategy1_cloudrun.sql_runner.run_sql_step` re-export 到 package implementation。
- `PYTHONPATH=src python3 -m scripts.strategy1_cloudrun.orchestrate_annual_rolling_selection --start-year 2021 --end-year 2021 --run-version vunit --include-yearly-backtest-commands --dry-run`：输出 5 步，第一步为 `build_training_panel` / `build_training_panel_risk_feature`，命令使用 `quant_ashare.strategy1.sql_runner`，不再使用 `scripts.strategy1_cloudrun.sql_runner`。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。

### 阻塞项

- 无。

### 下一步建议

- 提 PR。
- PR 合并后再清理旧 annual worktree；清理前不要恢复其脏记忆/TODO 改动。
- 按新 plan 执行完整 `2021-2026` 年度滚动，并用 continuous ledger 评价，不拼接年度 fresh-run。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 旧分支 `codex/remove-composer-refresh-helper` 已确认 PR #129 合并且本地改动过时；重复 PRD 暂存和冲突编号记忆改动未沿用。
> - 旧分支本地脏改动已保存在 `stash@{0}`，随后清理本地/远端旧分支，并从最新 `origin/main` 新开 `codex/record-dependency-install-convention`。
> - 已追加 `DECISION-20260610-13`：本项目执行过程中若缺失必要本机 / 运行依赖，Agent 可直接安装最小必要依赖并继续任务，无需再次询问。
> - 授权边界已写入 `KNOWN_CONSTRAINTS.md`：不覆盖密钥 / 凭据 / 隐私、未脱敏敏感日志、显著云成本、生产权限边界或 job spec / IAM 变更、破坏性数据操作。

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - Dependency install convention recorded

### 已完成工作

- 核对 `origin/main` 后确认旧分支 `codex/remove-composer-refresh-helper` 的 PR #129 已合并，且本地 staged PRD 与 main 内容重复。
- 确认旧分支本地记忆改动基于过时上下文并复用了当前 main 已占用的 `DECISION-20260610-01` 编号，因此不直接提交。
- 将旧分支本地脏改动保存为 `stash@{0}`，清理本地/远端旧分支，并从最新 `origin/main` 新建 `codex/record-dependency-install-convention`。
- 追加 `DECISION-20260610-13`，记录 owner 约定：缺失必要本机 / 运行依赖时，Agent 可直接安装最小必要依赖并继续任务。
- 在 `KNOWN_CONSTRAINTS.md` 写明授权边界，避免把该约定误用到密钥、权限、生产 job spec / IAM 或破坏性操作。

### 重要上下文

- 该记录只保留旧分支中仍有效的 owner 约定，不恢复旧 PRD 暂存，也不沿用旧分支冲突编号的记忆内容。
- 依赖安装授权适用于本机 / 运行环境准备；生产权限边界、显著云成本、破坏性数据操作和任何凭据处理仍需遵守既有安全约束。

### 改动文件

- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`：通过。

### 阻塞项

- 无。

### 下一步建议

- 如需进入仓库历史，可提交并推送本分支后开小 PR。
- `stash@{0}` 只是旧分支过时改动备份；除非 owner 明确要求，不应再恢复提交。

### 已更新记忆文件

- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 分支 `codex/delete-strategy1-job-wrappers` 已删除五个旧 job wrapper 文件：`scripts/strategy1_cloudrun/train_predict.py`、`prepare_matrix.py`、`train_candidate_task.py`、`select_register_predict.py`、`backtest_report.py`。
> - 本轮不改正式 Cloud Run job spec、不重建镜像；线上 jobs 和代码侧 override args 已在前序 PR 切到 `quant_ashare.strategy1.*` package entrypoint。
> - `tests/strategy1/test_cloudrun_package_entrypoints.py` 已从 old/new wrapper parity 改为 package entrypoint `--help` smoke 与 dry-run JSON 解析；`tests/strategy1/test_package_boundaries.py` 新增旧五 wrapper 文件不存在断言。
> - 五个旧模块路径仍保留在 `retired_reference_lint.banned_active_refs` 和 `tests/strategy1/test_retired_lint.py` 清单中，继续防止 active scopes 回流。
> - 验证已通过：`PYTHONPATH=src python3 -m pytest -q tests/strategy1 tests/strategy1_cloudrun` 92 passed；`PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint` 通过；`python3 -m compileall -q src scripts tests` 通过；`git diff --check` 通过。
> - 仍未执行真实 owner-approved promotion；后续必须 owner 指定 accepted research run 后，按 runbook 先 review-only 再带 `--execute`。

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - Strategy1 retired job wrapper deletion

### 已完成工作

- 在独立 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-delete-job-wrappers` 基于 `origin/main` commit `5772f30` 开分支 `codex/delete-strategy1-job-wrappers`。
- 删除五个旧 job wrapper 文件：
  - `scripts/strategy1_cloudrun/train_predict.py`
  - `scripts/strategy1_cloudrun/prepare_matrix.py`
  - `scripts/strategy1_cloudrun/train_candidate_task.py`
  - `scripts/strategy1_cloudrun/select_register_predict.py`
  - `scripts/strategy1_cloudrun/backtest_report.py`
- 将 `tests/strategy1/test_cloudrun_package_entrypoints.py` 从 old/new wrapper parity 改为 package entrypoint `--help` smoke 与 dry-run JSON 解析。
- 将 `tests/strategy1/test_package_boundaries.py` 中五个 job wrapper alias 测试替换为旧 wrapper 文件不存在断言；保留其他非 job wrapper re-export 测试。
- 更新 `tests/strategy1/test_retired_lint.py`，避免已删除 wrapper 文件被当作 active-scope 扫描样本。

### 重要上下文

- 本轮不修改正式 Cloud Run job spec、不重建镜像；线上五个 jobs 已在前序部署指向 package entrypoint。
- 五个旧模块点分路径仍保留在 retired-reference linter ban-list 和测试清单中，用于防回流。

### 改动文件

- `scripts/strategy1_cloudrun/train_predict.py`（删除）
- `scripts/strategy1_cloudrun/prepare_matrix.py`（删除）
- `scripts/strategy1_cloudrun/train_candidate_task.py`（删除）
- `scripts/strategy1_cloudrun/select_register_predict.py`（删除）
- `scripts/strategy1_cloudrun/backtest_report.py`（删除）
- `tests/strategy1/test_cloudrun_package_entrypoints.py`
- `tests/strategy1/test_package_boundaries.py`
- `tests/strategy1/test_retired_lint.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_package_boundaries.py tests/strategy1/test_cloudrun_package_entrypoints.py tests/strategy1/test_retired_lint.py tests/strategy1_cloudrun/test_dataset_role_routing.py`：41 passed。
- `PYTHONPATH=src python3 -m pytest -q tests/strategy1 tests/strategy1_cloudrun`：92 passed。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过，active scopes 无旧五模块路径。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。

### 阻塞项

- 无。

### 下一步建议

- 提 PR。
- 真实 owner-approved promotion 仍需 owner 指定 accepted research run 后，按 runbook 先 review-only 再带 `--execute`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - Strategy1 code-side entrypoint cutover main deploy

### 已完成工作

- 在独立 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-entrypoint-main-deploy-156` 基于 `origin/main` merge commit `2156bb4b5a1d40c358a738395e01c10803ffa825` 执行代码侧 cutover 后的部署收尾。
- 使用一次性 Cloud Build config 构建并推送固定 tag `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:entrypoint-main-2156bb4-20260610-01`，未更新 `latest`。
- Cloud Build `a11eca10-db4a-478f-b69c-6f8866cc5598` succeeded，镜像 digest 为 `sha256:c84b47d8daea59d6d89dd5a1c218d6d1ee1a1195885a16c6d66a262a60f7305c`。
- 五个正式 Strategy1 Cloud Run jobs 已更新到该 immutable digest：
  - `strategy1-train-predict-job`
  - `strategy1-prepare-matrix-job`
  - `strategy1-train-candidate-fanout-job`
  - `strategy1-select-register-predict-job`
  - `strategy1-backtest-report-job`

### 重要上下文

- 本次部署是必要的：orchestrator / native search / annual rolling 会从镜像内代码生成 Cloud Run override args，仅合并 PR #156 不足以让线上运行时使用 package module。
- 旧五 job wrapper 仍保留为兼容层；删除需单独 PR，并同步移除或替换 old/new wrapper parity 测试。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 读回五个 jobs，确认 image digest 已更新为 `sha256:c84b47d8daea59d6d89dd5a1c218d6d1ee1a1195885a16c6d66a262a60f7305c`。
- 读回确认 job args 仍为 package entrypoint，SA 仍为 `241358486859-compute@developer.gserviceaccount.com`，`maxRetries=0`，CPU/memory 和 fanout `taskCount=40` / `parallelism=20` 未变。
- 五个正式 jobs 的 `--help` boot smoke 均成功，且 Cloud Logging 均匹配到 `usage:`：
  - `strategy1-train-predict-job-vh59r`
  - `strategy1-prepare-matrix-job-fjshr`
  - `strategy1-train-candidate-fanout-job-cpxr2`
  - `strategy1-select-register-predict-job-82wsq`
  - `strategy1-backtest-report-job-44cmd`

### 阻塞项

- 无。

### 下一步建议

- 单独 PR 删除旧五 job wrapper，并同步调整 wrapper parity 测试；删除 PR 内先确认 active scopes 仍无旧五模块路径。
- 真实 owner-approved promotion 仍需 owner 指定 accepted research run 后，按 runbook 先 review-only 再带 `--execute`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - Strategy1 legacy job entrypoint active-scope guard

### 已完成工作

- 在 `tests/strategy1/test_retired_lint.py` 新增 `LEGACY_JOB_ENTRYPOINT_MODULES`，显式列出五个旧 job module：
  - `scripts.strategy1_cloudrun.train_predict`
  - `scripts.strategy1_cloudrun.prepare_matrix`
  - `scripts.strategy1_cloudrun.train_candidate_task`
  - `scripts.strategy1_cloudrun.select_register_predict`
  - `scripts.strategy1_cloudrun.backtest_report`
- 新增测试 `test_legacy_cloudrun_job_entrypoints_are_banned_from_active_scopes`，同时断言：
  - 五个旧入口路径必须存在于 `retired_reference_lint.banned_active_refs`。
  - non-historical active scopes 中不得再出现这些旧入口路径。
- 测试复用 retired linter 的 historical scope 语义，避免 historical/audit 文档中的旧路径说明误报。

### 重要上下文

- 本轮只补测试护栏，不改运行路径、不删 wrapper、不改 Cloud Run job spec。

### 改动文件

- `tests/strategy1/test_retired_lint.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest -q tests/strategy1/test_retired_lint.py`：5 passed。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。

### 阻塞项

- 无。

### 下一步建议

- 可作为小 PR 合入；后续若删除旧 wrapper，需要同步调整 wrapper parity 测试。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - Strategy1 package entrypoint code-side cutover

### 已完成工作

- 将 `src/quant_ashare/strategy1/pipeline_control.py` 生成的五个 Cloud Run job module 从旧 `scripts.strategy1_cloudrun.*` 切到 `quant_ashare.strategy1.*`。
- 将 `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py` 与 `orchestrate_annual_rolling_selection.py` 内部发出的 select/register/predict、backtest/report 和 annual plan command 切到 package module；两个脚本保留现有 CLI 入口。
- 将 `configs/strategy1/active_step_catalog.yml` 的 backtest/report active step caller 切到 `quant_ashare.strategy1.backtest_report`。
- 将 active runbook / 示例命令中的五个 job 入口与多实验 orchestrator 示例更新到 package 入口。
- 将五个旧 job module 路径加入 retired-reference linter，并补 catalog caller 检查，避免 catalog caller 因跳过配置文件本身而漏报。
- 更新 active tests 的入口导入到 package module，并新增 direct / fanout / native TopK / annual rolling command-plan 断言。

### 重要上下文

- 本 PR 不删除旧五 job wrapper；它们仍用于兼容旧 CLI/import 和 old/new parity 测试。
- 删除旧 wrapper 前，需要先合并并验证本代码侧 cutover，再确认 active scopes 内旧五模块路径仍为 0，并同步移除或替换 wrapper parity 测试。

### 改动文件

- `src/quant_ashare/strategy1/pipeline_control.py`
- `src/quant_ashare/strategy1/retired_lint.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`
- `configs/strategy1/active_step_catalog.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `docs/策略1实验并发调度器运行手册.md`
- `tests/strategy1/test_retired_lint.py`
- `tests/strategy1/test_sql_render.py`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `tests/strategy1_cloudrun/test_dynamic_cv_folds.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest -q tests/strategy1 tests/strategy1_cloudrun`：91 passed。
- `python3 -m compileall -q src scripts tests`：通过。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `git diff --check`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.pipeline_control --help`、`python3 -m scripts.strategy1_cloudrun.orchestrate_sklearn_native_search --help`、`python3 -m scripts.strategy1_cloudrun.orchestrate_annual_rolling_selection --help`：通过。

### 阻塞项

- 无。

### 下一步建议

- 合并本代码 PR 后，如需继续收口，可单独评估删除旧五 job wrapper，并同步调整兼容性测试。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - 五个正式 Strategy1 Cloud Run jobs package entrypoint cutover

### 已完成工作

- 从 PR #153 merge commit `1775099a6f8e3722dcf6ecead60f4fc0263115a1` 构建正式镜像 `strategy1-cloudrun-runner:package-entrypoints-main-1775099-20260610-01`，digest `sha256:0dce0e78256140a92d7b73bc083e028b377b9a132f9e08ccfd57d4730d7ac8b7`，Cloud Build `6c91beb7-1ac7-4401-8218-a9b657455de9`。
- 更新五个正式 Cloud Run jobs 的 image digest 和 args：
  - `strategy1-train-predict-job` -> `quant_ashare.strategy1.train_predict`
  - `strategy1-prepare-matrix-job` -> `quant_ashare.strategy1.prepare_matrix`
  - `strategy1-train-candidate-fanout-job` -> `quant_ashare.strategy1.train_candidate_task`
  - `strategy1-select-register-predict-job` -> `quant_ashare.strategy1.select_register_predict`
  - `strategy1-backtest-report-job` -> `quant_ashare.strategy1.backtest_report`
- 读回确认 command、SA、maxRetries、CPU/memory、timeout、taskCount/parallelism 保持预期。
- 删除 PR #153 验证遗留的临时 Cloud Run job `strategy1-package-entrypoint-help-smoke`。

### 测试 / 验证

- 五个正式 jobs 的 `--help` boot smoke 均 `Completed=True`，且 Cloud Logging 均匹配到 `usage:`：
  - `strategy1-train-predict-job-wdfv4`
  - `strategy1-prepare-matrix-job-rxc5n`
  - `strategy1-train-candidate-fanout-job-rltvm`
  - `strategy1-select-register-predict-job-sh2bz`
  - `strategy1-backtest-report-job-mtj4t`

### 后续

- 单独代码 PR 同步 orchestrator / pipeline-control / native search / annual rolling 的 Cloud Run override args、catalog `caller` 字段和 active runbook / 示例命令。
- 旧 wrapper 删除前，active scopes 内五个旧模块路径 grep 必须为 0，并把旧模块路径纳入 retired-reference linter 防回流。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - 五个 Strategy1 Cloud Run package entrypoint

### 已完成工作

- 新增五个稳定 package entrypoint：`quant_ashare.strategy1.train_predict`、`quant_ashare.strategy1.prepare_matrix`、`quant_ashare.strategy1.train_candidate_task`、`quant_ashare.strategy1.select_register_predict`、`quant_ashare.strategy1.backtest_report`。
- 将旧 `scripts.strategy1_cloudrun.train_predict`、`prepare_matrix`、`train_candidate_task`、`select_register_predict`、`backtest_report` 缩为兼容 wrapper；普通 import 下 alias 到 package 实现模块，CLI 运行仍调用同一 `main()`。
- PR #153 review follow-up 已给五个 wrapper 的 `sys.modules[__name__] = _impl` alias 加注释，明确这是 legacy import / monkeypatch 兼容关键路径。
- 新增 `tests/strategy1/test_cloudrun_package_entrypoints.py`，覆盖五个旧/新入口 `--help` 输出一致和关键 `--dry-run` JSON plan 一致。
- 扩展 `tests/strategy1/test_package_boundaries.py` 的 package import smoke 与 wrapper alias 检查。
- 构建验证镜像 `strategy1-cloudrun-runner:package-entrypoints-6b1b3c7-20260610-01`，digest `sha256:101eab22ac1504fc03f42392fdb2db984c23715b441955a1f7ae0316ca35c172`，Cloud Build `b906160e-1ae3-4acb-851f-bd19ac248f47`。
- 用临时 Cloud Run job `strategy1-package-entrypoint-help-smoke` 分别跑通五个新 package entrypoint 的 `--help`：`strategy1-package-entrypoint-help-smoke-w2g7d`、`...-tcf7s`、`...-df6vr`、`...-b2lc5`、`...-vbfgg`，全部 `Completed=True`，Cloud Logging 均匹配到 `usage:`。

### 重要上下文

- 本轮是代码入口准备，不修改正式 Cloud Run Job command，不构建镜像，不部署线上 jobs，不删除旧 wrapper。
- 线上五个 jobs 仍通过 `scripts.strategy1_cloudrun.*` command 启动；后续迁到 `quant_ashare.strategy1.*` 必须单独 PR、构建镜像并做五 job boot smoke。
- Cutover PR 范围不能只改 job spec；还必须同步 orchestrator / pipeline-control / native search / annual rolling 的 Cloud Run override args、catalog `caller` 字段和 active runbook / 示例命令。删除旧 wrapper 前，active scopes 内五个旧模块路径 grep 必须为 0，并应把旧模块路径纳入 retired-reference linter 防回流。

### 改动文件

- `src/quant_ashare/strategy1/train_predict.py`
- `src/quant_ashare/strategy1/prepare_matrix.py`
- `src/quant_ashare/strategy1/train_candidate_task.py`
- `src/quant_ashare/strategy1/select_register_predict.py`
- `src/quant_ashare/strategy1/backtest_report.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `scripts/strategy1_cloudrun/prepare_matrix.py`
- `scripts/strategy1_cloudrun/train_candidate_task.py`
- `scripts/strategy1_cloudrun/select_register_predict.py`
- `scripts/strategy1_cloudrun/backtest_report.py`
- `tests/strategy1/test_cloudrun_package_entrypoints.py`
- `tests/strategy1/test_package_boundaries.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 手工五入口 old/new `--help` smoke：通过。
- 手工五入口 old/new 关键 `--dry-run` JSON plan parity：通过。
- 验证镜像五入口 Cloud Run `--help` smoke：通过。
- `python3 -m pytest -q tests/strategy1/test_package_boundaries.py tests/strategy1/test_cloudrun_package_entrypoints.py tests/strategy1_cloudrun/test_dataset_role_routing.py tests/strategy1_cloudrun/test_dynamic_cv_folds.py`：35 passed。
- `python3 -m pytest -q tests/strategy1 tests/strategy1_cloudrun`：87 passed。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。

### 阻塞项

- 无代码阻塞。生产 job command 尚未迁移。

### 下一步建议

- 合并代码入口 PR 后，单独构建 main 镜像，把五个正式 Cloud Run jobs 的 command args、override args、catalog caller 和 active runbook / 示例命令迁到 `quant_ashare.strategy1.*`，并跑五 job boot smoke。
- 旧 wrapper 只能在正式 job command 迁移且 smoke 通过后再考虑删除。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - OQ-013 IAM 收敛决策记录

### 已完成工作

- 记录 owner 对 OQ-013 的选择：采用方案 1，接受现状但保留流程约束。
- 将 `TODO.md` 中 OQ-013 勾选完成。
- 将 OQ-013 从 `OPEN_QUESTIONS.md` 移出并归档到 `archive/CLOSED_QUESTIONS.md`。
- 追加 `DECISION-20260610-12`，明确普通 runner compute SA 暂保留 `ashare_ads` WRITER，但普通新实验不得以 ADS 为默认写入路径。
- 更新 `KNOWN_CONSTRAINTS.md` 和 `IMPLEMENTATION_STATUS.md`，说明本轮不修改线上 IAM。

### 重要上下文

- 本决策不改变 D2/D3 的流程边界：普通实验默认 research-first，ADS 正式发布只走 owner-approved promotion job。
- 显式 `--output-dataset-role ads` / `dataset_role="ads"` 仅保留为历史 ADS audit / 兼容路径。
- 后续若要做 IAM 硬隔离，需要新的 owner 决策，并先设计 ADS audit / 历史报告重渲染替代路径。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/archive/CLOSED_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

### 测试 / 验证

- 本轮为文档 / 记忆决策记录；未改代码、SQL、BigQuery、Cloud Run 或 IAM。

### 阻塞项

- 无。

### 下一步建议

- 继续按 promotion runbook 等待 owner 指定 accepted research run 后执行首次真实 promotion。
- Cloud Run entrypoint 从 wrapper 迁到 package module 仍需单独 PR 和镜像 smoke。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/archive/CLOSED_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - PR #151 review follow-up IAM 收敛留痕

### 已完成工作

- 复核 PR #151 review 指出的 IAM 收敛缺口：五个普通 Strategy1 runner jobs 仍使用 `241358486859-compute@developer.gserviceaccount.com`。
- 复核 `ashare_ads` dataset access，确认该 compute SA 仍具备 WRITER；promotion 专用 SA 也具备 WRITER。
- 新增 OQ-013 / TODO，记录普通 runner ADS 写权限的 owner 决策点：接受现状、收回并为 ADS audit 特批、或按表级 / 专用 SA 收窄。
- 更新 `KNOWN_CONSTRAINTS.md`，明确在 OQ-013 决策前不要直接 revoke 普通 runner ADS 写权限，避免破坏 ADS audit / 历史报告重渲染回写路径。

### 重要上下文

- 本轮没有修改线上 IAM、Cloud Run job spec、BigQuery table 或 dataset。
- 当前流程边界仍成立：普通实验默认 research-first，正式发布 ADS 必须走 owner-approved promotion job；但 IAM 层硬隔离尚未闭合。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

### 测试 / 验证

- `gcloud run jobs describe` 确认五个普通 Strategy1 runner jobs 的 service account 均为 `241358486859-compute@developer.gserviceaccount.com`。
- `bq show --format=json data-aquarium:ashare_ads` 确认 `241358486859-compute@developer.gserviceaccount.com` 仍有 WRITER access。

### 阻塞项

- OQ-013 需要 owner 决策后才能调整 live IAM。

### 下一步建议

- 在 owner 选择 IAM 收敛方案前，不要直接 revoke 普通 runner 的 `ashare_ads` 写权限。
- 若选择收窄权限，先设计 ADS audit / 历史报告重渲染的特批路径，再执行 live IAM 变更和 smoke。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - D3/E main 镜像部署与 promotion job dry-run

### 已完成工作

- 从 `origin/main` merge commit `f421c83c1987d5f8eb067991e9d4f6624206306a` 创建 detached 部署 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-d3e-main-deploy`。
- 构建正式 Strategy1 runner 镜像 `research-d3e-main-f421c83-20260610-01`；Cloud Build id `e6b385e7-c386-40be-8adb-e00fc48045c1`，digest `sha256:fdb61f8141e240c377b3faaa21b5e6efef9c783ebb9e04923ff3b675b8d54bc2`。
- 将五个现有 Strategy1 jobs 更新到该 digest：`strategy1-train-predict-job`、`strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`。
- 新建 promotion 专用 service account `strategy1-promotion-runner@data-aquarium.iam.gserviceaccount.com`，授予 project `roles/bigquery.jobUser`，以及 `ashare_research` / `ashare_ads` dataset WRITER。
- 新建 promotion 专用 Cloud Run job `strategy1-promote-research-to-ads-job`，使用同一 digest，command 为 `python -m scripts.strategy1.promote_research_to_ads`，SA 为 `strategy1-promotion-runner@data-aquarium.iam.gserviceaccount.com`。

### 重要上下文

- 普通五个 Strategy1 runner jobs 仍使用原 compute SA 和旧 wrapper command；本轮只更新 image digest，没有迁移 Cloud Run entrypoint。
- Promotion job 已部署但只做 review-only dry-run，没有执行真实 promotion，没有写 ADS，也没有写 manifest。
- 真实 promotion 仍必须由 owner 指定 accepted research run/backtest/model 和 approval metadata 后，按 runbook 先 review-only，再显式加 `--execute`。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 本地 targeted tests：`python3 -m pytest -q tests/strategy1/test_promotion.py tests/strategy1/test_package_boundaries.py tests/strategy1_cloudrun/test_dataset_role_routing.py`，29 passed。
- `python3 -m compileall -q src scripts`：通过。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- 五个 existing jobs `--help` boot smoke 成功：`strategy1-train-predict-job-rrjmf`、`strategy1-prepare-matrix-job-7bgfl`、`strategy1-train-candidate-fanout-job-jtw78`、`strategy1-select-register-predict-job-p88c9`、`strategy1-backtest-report-job-glntc`。
- Promotion job `--help` boot smoke：`strategy1-promote-research-to-ads-job-6kqd7` succeeded。
- Promotion job 完整参数 review-only dry-run：`strategy1-promote-research-to-ads-job-4mkrv` succeeded，日志包含 review-only 提示。
- BigQuery 反向确认：`research_promotion_manifest` 中 `promotion_id='promo_deploy_smoke_20260610_01'` 行数为 `0`。
- `bq query --project_id=data-aquarium --location=asia-east2 --use_legacy_sql=false < sql/research/03_qa_research_schema_readiness.sql`：7 条断言全部 successful。

### 阻塞项

- 无部署阻塞。真实 promotion 仍待 owner 指定具体 accepted research source 和 approval。

### 下一步建议

- 若需要首次真实 promotion，先用 `strategy1-promote-research-to-ads-job` 对 owner 指定 run 跑 review-only dry-run，确认 SQL/target tables/window 后再加 `--execute`。
- Cloud Run entrypoint 从 `scripts.strategy1_cloudrun.*` 迁到 package module 仍需单独 PR 和镜像 smoke。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - PR #150 review follow-up

### 已完成工作

- 修复 `--allow-unaccepted` 路径下 promotion 伪造验收状态的问题：registry / summary / 普通 research 输出只写 promotion lifecycle 字段，不再写 `acceptance_status='accepted'` 或 `research_status='accepted'`。
- 为 source backtest trade / NAV 增加 promotion window 外行数为 0 的 ASSERT，并检查 summary `start_date` / `end_date` 被本次 promotion window 完整覆盖。
- 将 promotion CLI 改为默认 review-only；真实写 ADS / manifest 必须显式传 `--execute`，单独 `--print-sql` 只打印 plan + SQL。
- 更新 runbook、research README、ARCHITECTURE / KNOWN_CONSTRAINTS / DECISION / TODO，记录失败 attempt 审计方式和 D3/E 同 PR 交付的一次性边界豁免。

### 重要上下文

- Promotion ASSERT 失败会整体回滚，因此不会留下 `research_promotion_manifest` 成功行；失败 attempt 需要查 BigQuery job history 或 Cloud Run execution logs。
- 本轮仍未执行真实 promotion，未部署专用 promotion Cloud Run job，也未迁移 Cloud Run entrypoint。

### 改动文件

- `src/quant_ashare/strategy1/promotion.py`
- `scripts/strategy1/promote_research_to_ads.py`
- `tests/strategy1/test_promotion.py`
- `docs/策略1ResearchPromotion运行手册.md`
- `sql/research/README.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest -q tests`：79 passed。
- `python3 -m compileall -q src scripts tests`：通过。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `npx --yes @dataform/cli compile dataform`：通过，35 actions。
- `git diff --check`：通过。
- `python3 -m scripts.strategy1.promote_research_to_ads ... --dry-run --print-sql`：成功输出 plan + SQL，未执行写入。
- `python3 -m scripts.strategy1.promote_research_to_ads ... --print-sql`：review-only，未执行写入。
- BigQuery client dry-run：`dry_run=True`。
- 程序化 self-review invariant：55 PASS / 0 FAIL。

### 阻塞项

- 无代码阻塞。真实 promotion / promotion Cloud Run job 部署未在本轮执行。

### 下一步建议

- PR #150 合并后如需线上 promotion，基于 main 构建/部署 owner-approved promotion job，或按 runbook 手工先 review-only 再 `--execute`。
- Cloud Run entrypoint 从 `scripts.strategy1_cloudrun.*` 迁到 package module 仍需单独 PR 和镜像 smoke。

### 已更新记忆文件

- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - 项目结构重构 Phase D3/E promotion 与包化

### 已完成工作

- 新增 D3 promotion package：`src/quant_ashare/strategy1/promotion.py`，生成并执行 owner-approved research-to-ADS BigQuery promotion script。
- 新增 CLI：`scripts/strategy1/promote_research_to_ads.py`，支持 `--dry-run` / `--print-sql`、显式 approval metadata、source run/backtest/model、date window、`--force-replace` 和 `--allow-unaccepted`。
- Promotion 默认复制 publishable outputs：model registry、prediction、candidate、portfolio target、order plan、backtest trade/position/NAV/ledger state/summary、signal monitor；training panel 默认不复制，只能显式 opt-in。
- Promotion SQL 默认要求 accepted research，ADS 目标已有行时 fail-fast，成功后更新 research lifecycle 并写 `research_promotion_manifest`。
- Phase E 包化：把 `acceptance`、`ledger`、`backtest_report`、`orchestrate_experiments` 实现迁入 `src/quant_ashare/strategy1/{acceptance,ledger,reporting,pipeline_control}.py`；旧 `scripts.strategy1_cloudrun.*` 文件只保留兼容 wrapper。
- Dataset role helper 迁入 `src/quant_ashare/strategy1/dataset_roles.py`；旧 `scripts.strategy1_cloudrun.dataset_roles` re-export package API。
- 新增 `src/quant_ashare/strategy1/legacy_names.py`，并把 retired-reference linter active scope 扩展到 `src/**`。
- 新增 `docs/策略1ResearchPromotion运行手册.md`，更新 `sql/research/README.md`。

### 重要上下文

- 本轮没有执行真实 promotion，没有部署专用 promotion Cloud Run job，也没有迁移 Cloud Run job command；旧 `python -m scripts.strategy1_cloudrun.backtest_report` 和 `python -m scripts.strategy1_cloudrun.orchestrate_experiments` 仍是兼容入口。
- 上线 promotion 前，应给 owner-approved promotion identity 配置 research 读写、ADS 写和 manifest 写权限；普通 experiment runner 不应因此获得常规 ADS 写权限。
- `accepted != promoted` 仍是硬边界；`--allow-unaccepted` 只是显式 owner override 开关，默认关闭。

### 改动文件

- `src/quant_ashare/strategy1/promotion.py`
- `scripts/strategy1/promote_research_to_ads.py`
- `src/quant_ashare/strategy1/dataset_roles.py`
- `src/quant_ashare/strategy1/{acceptance,ledger,reporting,pipeline_control,legacy_names}.py`
- `scripts/strategy1_cloudrun/{dataset_roles,acceptance,ledger,backtest_report,orchestrate_experiments}.py`
- `configs/strategy1/active_step_catalog.yml`
- `tests/strategy1/test_promotion.py`
- `tests/strategy1/test_package_boundaries.py`
- `tests/strategy1/test_retired_lint.py`
- `docs/策略1ResearchPromotion运行手册.md`
- `sql/research/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest -q tests`：77 passed。
- `python3 -m compileall -q src scripts tests`：通过。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `npx --yes @dataform/cli compile dataform`：通过，35 actions。
- `git diff --check`：通过。
- `python3 -m scripts.strategy1.promote_research_to_ads ... --dry-run`：成功输出 promotion plan。
- BigQuery client dry-run 对 generated promotion script 返回 `dry_run=True`。
- 旧 wrapper help smoke：`python3 -m scripts.strategy1_cloudrun.backtest_report --help`、`python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --help`、`python3 -m scripts.strategy1.promote_research_to_ads --help` 均可启动。
- 41 条程序化 self-review invariant 全部 PASS。

### 阻塞项

- 无代码阻塞。真实 promotion / promotion Cloud Run job 部署未在本轮执行。

### 下一步建议

- 开 PR review；合并后如需线上 promotion，基于 main 构建/部署 owner-approved promotion job，或按 `docs/策略1ResearchPromotion运行手册.md` 手工执行一次 accepted research promotion dry-run 后再 execute。
- Cloud Run entrypoint 从 `scripts.strategy1_cloudrun.*` 迁到 package module 仍需单独 PR 和镜像 smoke。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - 项目结构重构 Phase D2 main 镜像部署与默认 research smoke

### 已完成工作

- 合并 PR #148 到 `main`，merge commit `13bf0b512b5def2b2ef51c42e504f439f87a4dcf`。
- 从合并后的 `origin/main` 在独立 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-d2-main-deploy` 构建正式 Strategy1 runner 镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:research-d2-main-13bf0b5-20260610-01`。
- Cloud Build `e874d1bf-faad-4262-bacd-33cf01551425` 成功，immutable digest 为 `sha256:92c348536776cbcd8fb4f09def63509f0f1dfdf2f13f54d472dc078582b410f0`。
- 已把五个 Strategy1 Cloud Run jobs 更新到该 digest：`strategy1-train-predict-job`、`strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`。
- 读回 job spec，确认 image、service account、command/args、CPU/memory、taskCount/parallelism 保持预期。
- 跑通只读 boot smoke `strategy1-backtest-report-job-7g2mj`；入口 args 未传 `--output-dataset-role`，stdout plan 显示默认 `output_dataset_role=research`。
- 跑通真实默认 research-first smoke `strategy1-backtest-report-job-2xr6f`，run/backtest 为 `s1_default_research_d2_smoke_20260610_03` / `bt_s1_default_research_d2_smoke_20260610_03`，复用 D1 research prediction run `s1_sklearn_native_research_d1_smoke_20260610_04__l2_c_0_1` 的连续 2025H1 窗口。

### 重要上下文

- 真实 smoke 未传 `--output-dataset-role`；Cloud Run entrypoint 使用 main 镜像默认配置进入 `research`。
- `_01` smoke 跨了 D1 prediction 的不连续 2024H1 + 2025H1 窗口，触发 `QA-EXP-4`；`_02` 的 valid 窗口仍覆盖未预测的 2024H2，触发 `QA-POOL-5`。最终 `_03` 将 valid/test 与 D1 prediction 实际覆盖段对齐后成功。
- 本轮只完成 D2 部署与验收，不实现 promotion，不把 research run 自动复制到 ADS。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `sql/strategy1/README.md`
- `TODO.md`

### 测试 / 验证

- Cloud Build 成功：build id `e874d1bf-faad-4262-bacd-33cf01551425`，digest `sha256:92c348536776cbcd8fb4f09def63509f0f1dfdf2f13f54d472dc078582b410f0`。
- 五个 Cloud Run jobs spec 读回通过：image、SA、command/args、resources、taskCount/parallelism 均符合预期。
- Boot smoke `strategy1-backtest-report-job-7g2mj` succeeded，未传 `--output-dataset-role` 时默认 plan 为 `research`。
- Default research-first smoke `strategy1-backtest-report-job-2xr6f` succeeded，耗时约 `3m22s`；日志中 `build_candidates`、`build_portfolio_targets`、`build_order_plan`、`build_metrics_and_report_inputs`、`qa_runner_outputs`、`qa_lot_aware_ledger_outputs`、`qa_model_diagnosis_outputs`、`qa_tail_risk_outputs` 均记录 `dataset_role=research`。
- BigQuery 验收：research candidate `61,620`、target `135`、order `157`、trade `203`、position `570`、NAV `117`、ledger state `117`、summary `1`、signal monitor `117`；ADS candidate/target/order/trade/NAV/summary 同 run/backtest 均为 `0`。
- `bq query --project_id=data-aquarium --use_legacy_sql=false < sql/research/03_qa_research_schema_readiness.sql` 通过，7 条 assertion successful。

### 阻塞项

- 无。

### 下一步建议

- 继续单独实现 PRD Phase D3 owner-approved promotion job；promotion 前不得让普通 research run 隐式写 ADS。
- Phase E 包化时收敛读侧 routing 模块级全局态。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - 项目结构重构 Phase D2 default research-first

### 已完成工作

- 将 Strategy1 默认 `output_dataset_role` 从 `ads` 切为 `research`。
- 更新 `RunnerConfig`、默认 Cloud Run 配置、年度滚动配置、SQL runner、report、model diagnosis、tail-risk、acceptance v2/window/v3 replay、comparison 和 factor attribution 的默认 role。
- 更新 `configs/strategy1/active_step_catalog.yml`：`current_dataset_role=research`、`previous_dataset_role=ads`、`research.enabled_by_default=true`，并把 step 级 `output_dataset_role_current` 同步为 `research`。
- `resolve_table_role()` 与 SQL render 的裸默认现在跟随 catalog 当前 role；显式 `dataset_role="ads"` 保留 ADS / meta status 回放路径。
- Cloud Run command helper 改为始终显式下发 `--output-dataset-role=research|ads`，candidate fanout task 也显式下发 role，避免子 job 在镜像滚动更新期间继承错误默认值。

### 重要上下文

- 本轮只做 D2 default research-first，不实现 owner-approved promotion job，不把普通 runner 隐式写 ADS。
- PR 合并后仍需从 merge/main commit 重建正式 runner 镜像并更新五个 Strategy1 Cloud Run jobs；当前生产 jobs 仍跑 PR #147 后部署的 main 镜像。
- D3 需单独实现 promotion manifest / ADS copy；Phase E 仍需收敛读侧 routing 模块级全局态。

### 改动文件

- `configs/strategy1/active_step_catalog.yml`
- `configs/strategy1/cloudrun_runner_default.yml`
- `configs/strategy1/annual_rolling_lgbm_regression_v0.yml`
- `src/quant_ashare/strategy1/sql_render.py`
- `src/quant_ashare/strategy1/table_roles.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/dataset_roles.py`
- `scripts/strategy1_cloudrun/sql_runner.py`
- `scripts/strategy1_cloudrun/ledger.py`
- `scripts/strategy1_cloudrun/state.py`
- `scripts/strategy1/*.py` 相关 report / diagnosis / acceptance / comparison 脚本
- `tests/strategy1/**`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `sql/research/README.md`
- `sql/strategy1/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest -q tests` -> 69 passed（Python / SSL environment warnings only）。
- `python3 -m pytest -q tests/strategy1_cloudrun/test_dataset_role_routing.py` -> 19 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check` 通过。
- `npx --yes @dataform/cli compile dataform` 通过。
- `python3 -m compileall -q src scripts/strategy1 scripts/strategy1_cloudrun` 通过。
- `git diff --check` 通过。
- Programmatic smoke / self-review 42 条 invariant 全部通过：覆盖默认 research、显式 ADS fallback、candidate fanout 显式 role flag、catalog current role、renderer 默认、测试覆盖、文档、TODO 和记忆状态。
- 普通 orchestrator、sklearn native search、annual rolling dry-run 共 9 条 `train_candidate_task` 命令均显式包含 `--output-dataset-role=research`。
- Live BigQuery `bq query --use_legacy_sql=false --location=asia-east2 < sql/research/03_qa_research_schema_readiness.sql` 通过，7 条 `QA-RESEARCH-SCHEMA-*` assertion successful。

### 阻塞项

- 无代码阻塞；PR #148 已创建为 draft，待 review 后再转正式 / 合并。

### 下一步建议

- PR review 通过后再转正式 / 合并。
- PR 合并后从 merge/main commit 重建正式 runner 镜像并更新五个 Strategy1 Cloud Run jobs。
- D3 promotion job 和 Phase E 包化继续单独 PR。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - 项目结构重构 Phase D1 收尾 research smoke

### 已完成工作

- 部署 `sql/00_create_datasets.sql` 与 `sql/research/01_research_strategy1_tables.sql`，确认 `ashare_research` 15 张表存在。
- 给 runtime service account `241358486859-compute@developer.gserviceaccount.com` 补 `ashare_research` dataset 写权限。
- 修复 D1 smoke 暴露的运行问题：`research_experiment_run_status.log_dir` 缺列、search QA 参数缺 `p_strategy_id`、heartbeat 覆盖 terminal status、`QA-POOL-5` 把 valid/test gap 算入 DWS legacy 行数、research registry 显式契约列未写出。
- 重建并部署 Strategy1 Cloud Run jobs 到 D1 smoke 镜像 digest `sha256:7ef5601980f1b202654b504a52c96e33c09f95d009ebdcf455b002e4913571f9`。
- 跑通显式 research-mode smoke `sklearn_native_research_d1_smoke_20260610_04`，覆盖 prepare、5 候选 fanout、select/register/predict、Top-1 backtest/report、diagnosis、tail-risk、acceptance patch 和 search-level QA。

### 重要上下文

- 本轮只验证显式 `--output-dataset-role=research`，没有切 default research-first，也没有实现 promotion。
- Research 验收行数：training panel `2,742,853`、prediction `502,501`、candidate `61,620`、target `135`、order `157`、trade `203`、position `570`、NAV `117`、ledger state `117`、summary `1`、registry `1`；lifecycle bad count 全部为 `0`。
- ADS 污染检查同一 run/backtest 在 ADS run-scoped 表均为 `0` 行。
- 当前五个 Strategy1 Cloud Run jobs 指向 D1 smoke 验证镜像；正式 PR 合并后应以 merge/main commit 重建并部署 runner 镜像，避免长期运行未合并分支镜像。
- PR #146 review Low follow-up 已登记到 TODO：D2 default research-first 前补 research additive migration 约定和 research schema/readiness QA；`QA-POOL-5` 双窗口修复对 ADS 模式同样生效，未来复跑历史组合时 QA 结论可能翻转。

### 改动文件

- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `sql/research/01_research_strategy1_tables.sql`
- `sql/strategy1/qa/qa_model_diagnosis_outputs.sql`
- `tests/strategy1/test_research_contract.py`
- `tests/strategy1/test_sql_render.py`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest -q tests` -> 63 passed（4 个 Python / SSL 环境 warning）。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check` 通过。
- `npx --yes @dataform/cli compile dataform` 通过。
- `python3 -m compileall scripts/strategy1_cloudrun/orchestrate_experiments.py scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py scripts/strategy1_cloudrun/train_predict.py sql src` 通过。
- `git diff --check` 通过。
- BigQuery / Cloud Run research-mode smoke `sklearn_native_research_d1_smoke_20260610_04` 通过，ADS 污染检查为 0。

### 阻塞项

- 无代码阻塞；尚未 commit / push / open PR。

### 下一步建议

- 提 PR 前复核 diff 并提交。
- 合并后用 merge/main commit 重建正式 runner 镜像并更新五个 Strategy1 Cloud Run jobs。
- D1 合并后再进入 D2 default research-first 或 D3 owner-approved promotion job。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - Strategy1 年度滚动执行 P0 工程骨架

### 已完成工作

- 新增 `sql/ads/03_create_strategy1_backtest_ledger_state_daily.sql`，用 additive `CREATE TABLE IF NOT EXISTS` 补齐 Cloud Run ledger resume state 表。
- 新增 `sql/strategy1/qa/qa_cloudrun_schema_readiness.sql`，检查 Cloud Run backtest/report 所需 ADS 表、字段类型、分区和 `backtest_id` clustering。
- 在 `configs/strategy1/active_step_catalog.yml` 注册 `qa_cloudrun_schema_readiness`，并声明其 ADS role 覆盖。
- 新增 `configs/strategy1/annual_rolling_lgbm_regression_v0.yml`，固定 PRD_03 的 11 个 LightGBM regression 候选。
- 新增 `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`，生成年度 resolved experiment payload、matrix URI、Cloud Run command plan、B26 diagnostic-only reference 标记和连续 ledger backtest id。
- Review follow-up：`subtract_weekdays` 明确限制为 12 月年末 label window，新增 ledger state DDL 漂移测试，并在 D1 TODO 标注 research readiness 缺口。

### 重要上下文

- 本实现只覆盖 PRD_04 的 P0 工程骨架和 dry-run / resolved plan，不启动 Cloud Run。
- 非 dry-run 现在 fail-fast；完整 live annual rolling 仍需要先跑 readiness QA 和 dry-run，再按 owner 指令执行。
- continuous ledger 结果仍必须来自单条连续 ledger 或已验收 resume-continuous segment，不能拼接 yearly fresh-run NAV。

### 改动文件

- `sql/ads/03_create_strategy1_backtest_ledger_state_daily.sql`
- `sql/strategy1/qa/qa_cloudrun_schema_readiness.sql`
- `configs/strategy1/annual_rolling_lgbm_regression_v0.yml`
- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`
- `configs/strategy1/active_step_catalog.yml`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest tests` 58 passed（4 个 Python / SSL 环境 warning）。
- 未运行 BigQuery、Cloud Run 或 Dataform。

### 阻塞项

- 无代码阻塞；live 执行前需要 owner 明确允许运行 readiness QA / dry-run / Cloud Run smoke。

### 下一步建议

- 先跑 `qa_cloudrun_schema_readiness`。
- 再跑 `orchestrate_annual_rolling_selection.py --dry-run` 审核 resolved payload 和 command plan。
- 若 dry-run 正常，再执行 2021 单年 smoke 或完整 2021-2026 年度链路。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 新增 `docs/prd/PRD_20260610_04_策略1年度滚动执行工程化.md`。
> - PRD 把 2021 smoke 暴露的三个工程问题转成后续实现要求：annual rolling orchestrator 自动生成 resolved experiment payload、ADS additive migration、Cloud Run schema readiness QA。
> - PRD 明确 P0 不改模型、不扩参数、不调 v3 gate、不切 `ashare_research`；完整 `2021-2026` 正式结果必须来自单一 continuous ledger，或通过 resume-continuous QA 的 segment ledger，禁止拼年度 fresh-run。
> - PR #144 review follow-up 已处理：`biweekly` 口径、既有 `02` migration 关系、无数字前缀 QA + catalog step、过渡 namespace 和 B26 diagnostic-only reference 均已补齐。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #141 已合并，正式 Strategy1 Cloud Run runner 已构建并部署到镜像 `strategy1-cloudrun-runner:2565e0f`。
> - 2021 annual-selection smoke 已在正式 jobs 上闭环：candidate fanout `5f6qg`、select/register/predict `pxtbw`、backtest/report `t5fg6` 均 succeeded。
> - CV 修复实证：11 个候选全部 `cv_confirmation_status=passed`、`cv_fold_count=3`，fold 为 `cv_2018/cv_2019/cv_2020`；选中候选为 `risk_lgbm_prd_strong_regularized_l5_l63_lr002_n300_leaf800_ff07_bf10`。
> - 本次手工补齐生产 ADS additive schema：创建 `ads_backtest_ledger_state_daily`，并为 `ads_backtest_performance_summary` 补 4 个复合年化字段。2021 回测结果为 total_return -8.08%、compound annual -8.39%、Sharpe -0.382、MaxDD -19.54%、vs `000001.SH` excess -12.88%。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 分支 `codex/strategy1-research-routing-d1b` 已处理 PR #143 review follow-up：默认 ADS 子命令不下发 `--output-dataset-role=ads`，保持旧 Cloud Run 镜像兼容；显式 research 仍下发 role flag。
> - Research contract 已补 lifecycle 默认值：普通 research 输出默认 `research_status='candidate'`、`promotion_status='not_promoted'`，`research_promotion_manifest.promotion_status` 默认 `planned`。
> - D1 真实 research smoke 仍是独立收尾项：部署 D0 DDL、重建镜像、补 runtime SA `ashare_research` 写权限并跑显式 research-mode smoke 后，才能进入 D2 default research-first；读侧 routing 全局态收敛已登记到 Phase E。验证包括 `python3 -m pytest tests` 57 passed、Dataform `--check`、Dataform compile、BigQuery DDL dry-run、主要 CLI help/dry-run、41 条程序化 self-review checks、compileall 和 `git diff --check`。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 分支 `codex/strategy1-research-routing-d1a` 已 rebase 到最新 `origin/main`（含 PR #141 dynamic CV fold 修复），并继续用于 PR #142。
> - PR #142 review follow-up 已处理：补全非 retired Strategy1 step 的 catalog `inputs` / `outputs`，使其覆盖 SQL 中实际 `data-aquarium.ashare_ads.*` 引用；新增 pytest 校验 catalog role 覆盖和 research 渲染无 ADS 残留。
> - 验证：`python3 -m pytest tests` 42 passed；Dataform `--check`、Dataform compile、catalog ADS role 覆盖扫描、88 条程序化 self-review checks、compileall 和 `git diff --check` 均通过。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 分支 `codex/fix-dynamic-cv-folds` 修复 Strategy1 Cloud Run Python CV fold 硬编码问题：`train_predict.py` 现在基于 `cv_panel` 中 `split_tag='train'` 的年份动态生成最多 3 个 rolling fold，并排除外部 valid 年。
> - 新增 `tests/strategy1_cloudrun/test_dynamic_cv_folds.py` 覆盖年度滚动选参窗口 `2015-2019 -> cv_2017/cv_2018/cv_2019`，以及旧窗口完整边界 `2019-04-03..2023-12-31 -> cv_2021/cv_2022/cv_2023`。
> - 验证：`python3 -m pytest tests` 34 passed。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 分支 `codex/strategy1-research-routing-d1a` 已实现项目结构重构 Phase D1a：Strategy1 SQL render 支持按 catalog step 的 `inputs` / `outputs` 做 table role / dataset role 改写。
> - 默认渲染仍是 `data-aquarium.ashare_ads.*`；显式 `dataset_role="research"` 必须传 `allow_future_research=True`，并且只作为 contract / dry-run / 后续 runner 接线验证。本轮不改 Cloud Run 默认写入、不创建或写入 BigQuery `ashare_research`。
> - 已处理共享 ADS 源表歧义：无 step 上下文的全局 research 替换会 fail-fast，避免 `ads_model_registry` 被误替到 `research_acceptance_result`。
> - 验证：`pytest tests` 38 passed、Dataform `--check`、Dataform compile、21 个 catalog step ADS/research 双渲染 smoke、40 条 self-review checks、compileall 和 `git diff --check` 均通过。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 分支 `codex/add-research-table-contract` 已实现项目结构重构 Phase D0：新增 `ashare_research` schema contract、`sql/research/01_research_strategy1_tables.sql`、research README 和 catalog contract metadata。
> - D0 只定义 `research_*` 表族、`research_acceptance_result`、`research_experiment_run_status` 与 `research_promotion_manifest`；不部署 BigQuery、不切 runner 默认写入、不迁移历史 ADS、不实现 promotion job。
> - PR #140 review follow-up 已处理：`experiment_run_status` 当前侧通过 `ads_dataset: ashare_meta` 解析到既有 meta 表；`build_order_plan.partition_columns` 已改为 `rebalance_date`；新增测试防止 step/output 分区和 resolver dataset 漂移。
> - 验证：`pytest tests` 32 passed、Dataform `--check`、Dataform compile、BigQuery combined dry-run 和 `git diff --check` 均通过。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - OQ-005 Cloud Run Job IAM bootstrap TODO 已收口：PR #126 已合并到 `main`，`bootstrap_scheduler_iam.sh` 已固化 `roles/run.jobsExecutorWithOverrides`、`roles/run.viewer` 并移除旧 job-level `run.invoker`。
> - 本轮只清理过期状态，勾选 `TODO.md` 对应项并同步 `IMPLEMENTATION_STATUS` / `AGENT_HANDOFF`；未修改 Workflows、IAM bootstrap 脚本、Cloud Run、BigQuery 或生产配置。
> - 验证：复核 PR #126 merge commit `54fe077bb656f23b5ff9384f348e49b7a5259e94`，并确认 `origin/main` 当前 bootstrap 脚本仍包含正确 IAM 绑定。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 分支 `codex/fix-dataform-generated-drift` 已修复 Dataform generated SQLX drift：从 canonical `sql/` 与 `dataform/action_manifest.json` 重新生成 6 个 stale `dataform/definitions/**/*.sqlx` 文件。
> - PR review 的 Low 防复发建议已处理：新增 `tests/dataform/test_generated_sqlx.py`，直接调用 `generate_sqlx_from_sql.py --check`，让 pytest 暴露后续 generated SQLX drift。
> - 本轮未修改 canonical `sql/`、manifest、Workflows、Cloud Run 或 BigQuery 执行入口；只同步 generated SQLX、测试和项目记忆/TODO。
> - 验证：`python3 -m pytest tests` 25 passed、`generate_sqlx_from_sql.py --check`、Dataform compile 和 `git diff --check` 均通过。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #136 review follow-up 已处理：retired linter 在 Python 3.11/3.12 下递归扫描 active scope，不再空跑；当时显式 `dataset_role="research"` fail-fast，不再静默降级 ADS。
> - Owner 已确认 PR #136 可一次性合并项目结构重构 Phase A/A2/B/C；该豁免已记录为 `DECISION-20260610-07`，后续 Phase D/E 仍需单独 PR。
> - 已删除 PASS 型 self-review 文档，`sql/strategy1/README.md` 已说明 `audit_only` SQL 同 namespace 但执行状态以 catalog 为准，`TODO.md` 已补 Dataform generated SQLX drift cleanup 项。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 分支 `codex/strategy1-structure-refactor` 已实现项目结构重构 PRD Phase A/B/C：active step catalog、retired linter、table role / dataset role resolver、`src/quant_ashare/**` package foundation、`sql/strategy1/**` active SQL 命名空间。
> - 当时 table role 默认仍解析到 `ashare_ads`；显式 `dataset_role="research"` fail-fast，未创建或写入 `ashare_research`，也未迁移 Cloud Run entrypoint。
> - 验证：pytest 24 passed、catalog validate、retired linter、active step render smoke、compileall、CLI dry-run/help 和 `git diff --check` 均通过；Dataform `--check` 仍因既有 generated SQLX stale/missing 失败，本分支无 `dataform/` diff。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 新增 `docs/prd/PRD_20260610_03_策略1年度滚动选参.md`。
> - PRD 定义年度 walk-forward 参数选择：上一整年 valid 选择参数，选中参数在最近 5 年 final refit，再回测下一年；2021-2026 结果必须用年度预测合并后的一条连续 ledger 评价。
> - P0 固定 feature set、20 只、7.5% 单票上限、biweekly 和 `ledger_exec_v1_lot100`，只搜索 11 个冻结 LightGBM regression 可选候选；B26 binary 只作为 diagnostic-only reference。
> - PR #137 review follow-up 已处理：第 1 点只修理由、不改门；第 2 点修正 label embargo 措辞；第 3 点明确 B26 binary 不参与 `selected_candidate_id`。
> - 本轮只写方案和同步 `.agent/memory/IMPLEMENTATION_STATUS.md`、`.agent/memory/AGENT_HANDOFF.md`、`.agent/memory/DECISION_LOG.md`、`TODO.md`；未改代码、SQL、BigQuery、Cloud Run 或 Dataform。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 新增 `docs/prd/PRD_20260610_02_项目结构重构方案.md`，作为 `quant-ashare` 项目结构重构总 PRD。
> - Owner 已确认关键决策：采用 `ashare_research` dataset、`research_*` 表名前缀、`accepted != promoted`、先 table-role abstraction 后 research-first、`sql/strategy1/**` 目标 SQL 命名空间、`src/quant_ashare/**` Python 包根、短期保留 `scripts/strategy1_cloudrun/**` wrapper，且 P0 不强制创建 `docs/retired/`。
> - PRD 已改为已确认口径；新实验、候选、诊断和 acceptance replay 目标态默认写 research，`ashare_ads` 只承载 owner promotion 后的正式产物。
> - Review 指出的 `sql/cloudrun/strategy1/01_build_training_panel.sql`、ADS 硬编码耦合、retired linter allowlist、SQL `DECLARE p_*` 参数默认值漂移、`optional_params` schema 语义、`16-25` 逐个分类、`bqml_reference_run_id` exception registry 和 Python package 交付方式均已补进 PRD。
> - 本轮只写方案和同步 `.agent/memory/IMPLEMENTATION_STATUS.md`、`.agent/memory/AGENT_HANDOFF.md`、`.agent/memory/DECISION_LOG.md`、`TODO.md`；未改代码、SQL、BigQuery、Cloud Run 或 Dataform。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #134 已从 PRD-only 扩展为实现分支：新增 Strategy1 回测 `compound_annual_return`、`return_period_count`、`annualization_target_period_count`、`annualization_method` 字段与 ADS additive migration。
> - `09` summary、`10` runner QA、`24` v3 replay QA、`render_report.py` 与 `replay_acceptance_gate_v3.py` 已切到 NAV 首尾值 + NAV 有效交易日数减一的复合年化口径；legacy `annual_return` / `sharpe` 保留旧算术口径并显式标注。
> - PR #134 review follow-up 已修复 `total_return = -100%` 边界：SQL、report 和 v3 replay 统一允许 `gross == 0` 返回复合年化 `-100%`，仅拒绝 `gross < 0`。
> - 未运行 BigQuery / Cloud Run / pytest；后续需要 owner 决定是否部署 schema migration、是否重跑 2020-2022 R14 hold=10/20 报告或生成 sidecar，以及是否调整 compound Sharpe / Calmar 阈值。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #131 分支已完成 Strategy1 旧 BQML / SQL ledger runner P0 退役实现。
> - 已删除 BQML-only `sql/ml/strategy1/02-04`、SQL ledger fallback `08_run_backtest.sql` 和旧 `scripts/strategy1/run_oq010_experiments.py`；Cloud Run Python runner 已移除 `--use-bq-ledger` 参数和透传。
> - 当前 active path 收口为 Cloud Run Python training / prediction / ledger + 共享 SQL `01`、`05-07`、`09-10`、`12`、`16-24`；未运行 BigQuery / Cloud Run / pytest。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #132 已合并，`ashare-pipeline-control` 已重新部署到 revision `ashare-pipeline-control-00007-tst`。
> - 重新触发 2015 年 backfill execution `209bd2bf-86f4-455c-85c7-b6b1f4ec8025`，已越过 `dim_stock` 生命周期缺口。
> - 新失败点在 `sql/qa/01_core_smoke_checks.sql`：旧 core smoke 仍把 `2019-01-01` 当成 DWD 价格表全表存在下限；分支 `codex/fix-historical-backfill-core-smoke` 已改为只拒绝早于 `1990-12-19` 的异常行，`daily_current` 2019+ 下限继续由窗口 SQL/QA 约束。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #130 合并并部署 `ashare-pipeline-control` 后，重跑 2015 年 backfill execution `be12a12f-1e65-4cef-b60d-3945ef8da13a`，已越过指数窗口旧失败点。
> - 新失败点在股票窗口 QA `QA-WIN-13`：2015 ODS daily 有 `5,486` 行、`76` 个代码未写入 `dwd_stock_eod_price`。
> - 分支 `codex/fix-historical-dim-stock-lifecycle` 已修复 `dim_stock` 历史生命周期：缺主数据代码从全量 ODS daily 派生，`stock_basic.list_date` 晚于首个日线交易日时用 `first_trade_date` 兜底；PR #132 review follow-up 已改为直接复用 `daily_lifecycle`，避免重复全量扫描 ODS daily。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #127 review follow-up 已修复 Cloud Run ledger resume 代码断链：`LedgerParams`/manifest/CLI/SQL metadata 贯通，Python ledger 写入并恢复 `ads_backtest_ledger_state_daily`，`25` QA 改为 `ashare_ads` 与当前 ADS 字段。
> - 未运行测试、BigQuery 或 Cloud Run smoke；后续需要按 owner 指令做最小验证。

> 当前交接补充（2026-06-09，GPT-5 Codex）
> - 手工触发 2015 年 `ashare_warehouse_window_refresh` backfill 时失败，根因是窗口刷新 SQL 固定以 `2019-01-01` 作为写入下限，导致 `2015-01-01 ~ 2015-12-31` 被推成 `write_start=2019-01-01`。
> - 分支 `codex/fix-2015-index-backfill` 已将股票、指数、market-state 窗口刷新及股票/指数窗口 QA 改为按 `warehouse_mode` 区分日期下限：`daily_current` 保持 2019+，显式 `backfill` 允许 2019 年以前历史窗口。
> - 合并并部署后，下一步重新触发 2015 年窗口补数；2015 成功后再按年触发 2016、2017、2018。

> 当前交接补充（2026-06-09，GPT-5 Codex）
> - 新增 `docs/prd/PRD_20260609_01_策略1R14长训练回测.md`。
> - PRD 固定当前 R14 LightGBM regression 方法，不重新搜索参数，名义训练窗口为 `2015-04-01 ~ 2019-12-31`，先跑 `2020-01-02 ~ 2022-12-30` 的 `10` 只 / `20` 只双组合 diagnostic backtest；`2023-01 ~ 2026-06-09` 追加回测视 P0 结果和 owner 决策而定，若追加也跑两个组合。
> - 关键边界：训练必须做 5d label embargo，避免 2019 年末训练样本使用 2020 回测期收益；追加段不能和 `2020-2022` fresh segment 拼接成正式连续回测，除非 Cloud Run Python ledger resume 已实现并通过 resume consistency QA。

> 当前交接补充（2026-06-09，GPT-5 Codex）
> - 旧 Composer-era 补跑 helper `scripts/pipeline/run_warehouse_refresh.py` 已删除。
> - 该脚本仍通过 `gcloud composer environments run` 触发已退役的 `ashare-composer`，与当前 `Cloud Scheduler + Cloud Workflows` 生产入口冲突。
> - 后续窗口补跑 / QA-only / full rebuild 恢复路径继续以 `docs/Pipeline-补跑与故障恢复-Runbook.md` 和 `orchestration/workflows/**` 为准。
> - PR #129 review follow-up 已同步清理 `.agent/memory/OPEN_QUESTIONS.md` 中对旧 helper 的现行工具描述。

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

> 当前交接补充（2026-06-09，GPT-5 Codex）
> - 2026-06-09 20:00 scheduled ODS workflow 已触发，但先后暴露 Cloud Run Job 权限缺口：缺 `run.jobs.runWithOverrides` 和 `run.operations.get`。
> - live IAM 已补：`ashare-ingest-current-scope` job-level `roles/run.jobsExecutorWithOverrides`，以及 workflows runtime SA 的 project-level `roles/run.viewer`。
> - `bootstrap_scheduler_iam.sh` 已同步改成该真实权限口径，避免后续 bootstrap 回到错误的 job-level `run.invoker`。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - OQ-005 已完成 production cutover：生产调度入口固定为 `Cloud Scheduler + Cloud Workflows`，`ashare-composer` 环境已删除，Composer 业务 DAG 不再是现行生产路径。
> - `orchestration/composer/` 已收口为 retired / audit-only 历史目录，只保留审计、迁移对照和受控回滚参考价值。
> - Strategy1 `v3` replay 与 helper 驱动的 `24` QA 已按最新 contract 真执行通过；当前真正开放的主线只剩 OQ-010 可接受 Python baseline 和 OQ-012 是否正式归档。

## 当前交接摘要

- 2026-06-10：PR #146 已合并到 `main`（merge commit `bca0e791abb57b3fb7efaa01b46e7444ac15cfb2`），并已从 merge 后 `origin/main` 重建正式 Strategy1 runner 镜像 `sha256:c0ae9b2ec72b1299a08db66eb02881d0d3156735c14f08193d60e4388c9cc357`。五个 Strategy1 Cloud Run jobs 已更新到该 immutable digest，读回确认资源/SA/args 未改乱；只读 boot smoke execution `strategy1-backtest-report-job-8krjt` succeeded。
- 2026-06-10：分支 `codex/research-schema-readiness` 已补 D2 前 research additive migration 约定与 readiness QA：新增 `sql/research/02_research_strategy1_additive_migrations.sql` 和 `sql/research/03_qa_research_schema_readiness.sql`，catalog 登记 `qa_research_schema_readiness`，README 写明 `01 contract -> 02 additive migrations -> 03 readiness QA`。live BigQuery readiness QA 7 条断言全部 successful；本地 `python3 -m pytest -q tests` 66 passed，Dataform check/compile、compileall、`git diff --check` 均通过。
- 下一步：合并 `codex/research-schema-readiness` PR 后，再单独开 Phase D2 default research-first PR；D3 promotion job 和 Phase E 包化/命名收敛仍保持后续独立 PR。
- 2026-06-10：新增年度滚动执行工程化 PRD `docs/prd/PRD_20260610_04_策略1年度滚动执行工程化.md`；范围只解决 annual rolling 从手工 smoke 到可重复正式执行的工程路径，包括 resolved experiment payload 自动生成、ADS additive migration、schema readiness QA、run_id/artifact 规则和 continuous ledger 执行规则。不改模型、不扩参数、不调 v3 gate、不切 `ashare_research`；正式 `2021-2026` 结果不得拼接年度 fresh-run。
- 2026-06-10：2021 annual-selection Cloud Run smoke 已在正式 Strategy1 jobs 上闭环。PR #141 合并后构建部署 `strategy1-cloudrun-runner:2565e0f`；candidate fanout `strategy1-train-candidate-fanout-job-5f6qg` 成功，11 个候选全部 `cv_fold_count=3`、CV passed；select/register/predict `strategy1-select-register-predict-job-pxtbw` 成功并选中 `risk_lgbm_prd_strong_regularized_l5_l63_lr002_n300_leaf800_ff07_bf10`；backtest/report `strategy1-backtest-report-job-t5fg6` 成功，2021 结果 total_return -8.08%、compound annual -8.39%、Sharpe -0.382、MaxDD -19.54%、vs `000001.SH` excess -12.88%。运行中已用 additive DDL 补齐 `ads_backtest_ledger_state_daily` 和 performance summary 复合年化字段。
- 2026-06-10：项目结构重构 Phase D1b runner research routing 已在 `codex/strategy1-research-routing-d1b` 实现并处理 PR #143 review follow-up；新增 `output_dataset_role` 配置/CLI、`dataset_roles.py` helper 和 runner/report/diagnosis/QA/acceptance/comparison/factor attribution 显式 research routing。默认仍是 ADS，且默认 ADS 子命令不下发 `--output-dataset-role=ads`，保持旧 Cloud Run 镜像兼容；显式 `research` 模式下 run-scoped Strategy1 表解析到 `ashare_research.research_*`，research status 表解析到 `ashare_research.research_experiment_run_status`。Research DDL 已补 lifecycle 默认值：普通输出为 `candidate/not_promoted`，promotion manifest 为 `planned`。本轮不创建或部署 BigQuery `ashare_research` 对象、不修改 Cloud Run Job spec、不切 default research-first、不实现 promotion；D2 前新增 D1 收尾验收项，读侧 routing 全局态风格收敛登记到 Phase E。验证：`python3 -m pytest tests` 57 passed、Dataform `--check`、Dataform compile、BigQuery DDL dry-run、主要 CLI help/dry-run、41 条程序化 self-review checks、compileall 和 `git diff --check` 均通过。
- 2026-06-10：项目结构重构 Phase D1a SQL render table-role routing 已在 `codex/strategy1-research-routing-d1a` 实现并 rebase 到最新 `origin/main`；PR #142 review follow-up 已补全 catalog step role 覆盖，并新增 pytest 防止 research 渲染残留 `data-aquarium.ashare_ads.`。`sql_render.py` 可按 catalog step 的 role 集合把 ADS 表引用显式改写为 `ashare_research.research_*`，`sql_runner.py` wrapper 已透传 `dataset_role` / `allow_future_research`，默认 ADS 行为不变。无 step 上下文的全局 research 替换会 fail-fast，防止 `model_registry` / `acceptance_result` 共享 ADS 表造成误替换。本轮不启用 Cloud Run 默认写 research、不写 BigQuery、不做 promotion；D1b 仍需单独接 runner config / report / diagnosis / QA / acceptance/comparison research source。
- 2026-06-10：项目结构重构 Phase D0 research table contract 已在 `codex/add-research-table-contract` 实现；新增 `sql/research/**`、`ashare_research` schema contract、catalog research contract metadata 和 DDL drift tests。PR #140 review follow-up 已补 `experiment_run_status` 当前侧 `ashare_meta` dataset override 和 `build_order_plan` 分区列一致性测试；D0 不部署 BigQuery、不写 research、不迁移历史 ADS、不实现 promotion。D1a 已新增 render-only research opt-in，真正 runner 写 research 仍需 D1b 单独 PR。
- 2026-06-10：OQ-005 Cloud Run Job IAM bootstrap TODO 已收口；PR #126 已合并到 `main`，`orchestration/workflows/bootstrap_scheduler_iam.sh` 已固化 runtime SA 的 job-level `roles/run.jobsExecutorWithOverrides`、project-level `roles/run.viewer` 并移除旧 job-level `roles/run.invoker`；本轮只清理过期 TODO / 记忆状态，不改运行代码。
- 2026-06-10：Dataform generated SQLX drift 已在 `codex/fix-dataform-generated-drift` 单独 cleanup 分支修复；重新生成 `dataform/definitions/**/*.sqlx` 中 6 个 stale 文件，并新增 `tests/dataform/test_generated_sqlx.py` 直接调用 `generate_sqlx_from_sql.py --check` 防复发；未修改 canonical `sql/` 或 `dataform/action_manifest.json`，`python3 -m pytest tests` 25 passed，`--check`、Dataform compile 和 `git diff --check` 均通过。
- 2026-06-10：项目结构重构 PRD Phase A/A2/B/C 已在 `codex/strategy1-structure-refactor` 实现并完成 PR #136 review follow-up：新增 Strategy1 active step catalog、retired linter、table-role/dataset-role resolver 与 `src/quant_ashare/**` 包基础，active/shared SQL 已迁到 `sql/strategy1/**`；旧 `sql/ml/strategy1/**`、`sql/cloudrun/strategy1/**` 只保留 historical/audit README。当时默认仍解析/写入 `ashare_ads`，显式 `dataset_role="research"` fail-fast，不创建 `ashare_research`；D1a 已在后续分支补 render-only research opt-in。Owner 已确认 PR #136 一次性合并 Phase A/A2/B/C 的豁免，记录为 `DECISION-20260610-07`。
- 2026-06-10：新增 Strategy1 年度滚动选参 PRD `docs/prd/PRD_20260610_03_策略1年度滚动选参.md`；P0 固定 11 个 LightGBM regression 可选候选、B26 binary diagnostic-only reference、20 只持仓、7.5% 单票上限、biweekly 和 `ledger_exec_v1_lot100`，每年用上一整年 valid 选参数，再用最近 5 年 final refit，最终用年度预测合并后的一条连续 ledger 评价 `2021-2026`。
- 2026-06-10：新增项目结构重构总 PRD `docs/prd/PRD_20260610_02_项目结构重构方案.md`；owner 已确认采用 `ashare_research` / `research_*` / `accepted != promoted`、`sql/strategy1/**`、`src/quant_ashare/**`、短期保留 `scripts/strategy1_cloudrun/**` wrapper，且 P0 不强制创建 `docs/retired/`。实施顺序为先做 active path catalog、防误用护栏和 table role / dataset role resolver，再迁移 Strategy1 active shared SQL（同时覆盖 `sql/ml/strategy1/**` 与 `sql/cloudrun/strategy1/**`）到 `sql/strategy1/**`，随后抽 Strategy1 package foundation，最后再分段实现 `ashare_research` / `ashare_ads` 生命周期隔离和 deeper package split。
- 2026-06-10：新增 Strategy1 回测复合年化收益 PRD，范围为 summary / report / v3 gate 的复利年化字段口径；本 PR 不改代码、不跑 BigQuery / Cloud Run。
- OQ-005 当前状态：`ashare-ods-ingestion-daily`（`0 20 * * *`）与 `ashare-pipeline-alert-checker`（`0 * * * *`）两个 Scheduler job 已是唯一生产调度入口，ODS parent -> warehouse child、alert checker、manual full rebuild dry-run 都已有 live smoke 证据。
- OQ-005 代码边界：`orchestration/workflows/**` 是唯一现行调度实现面；`orchestration/composer/**` 只保留历史快照，不再接受新的生产逻辑或运维 runbook 变更；旧 Composer-era 补跑 helper `scripts/pipeline/run_warehouse_refresh.py` 已删除。
- Strategy1 当前状态：`v3` acceptance gate replay/QA 已 contract-driven 收口并通过；旧 BQML-only `02-04`、SQL ledger fallback `08` / `--use-bq-ledger` 和旧 `run_oq010_experiments.py` 已在 PR #131 分支退役删除；当前没有 accepted Python baseline，OQ-010 仍然 open；R14 长训练补数已越过历史 backfill 日期下限和 `dim_stock` 生命周期问题，但 2015 年重跑又暴露 core smoke 2019 全表下限误杀，需合并部署 `codex/fix-historical-backfill-core-smoke` 后再重跑 2015 年窗口。
- OQ-012 当前状态：schema contract / repair tooling / QA 都已具备，当前 BigQuery 读层无 mismatch 报警；剩余是 owner 是否把该问题正式关闭或保留防复发工程项。
- 下一步：结构重构若继续推进，应单独做 Phase D2 default research-first 或 Phase D3 owner-approved promotion job；D1b 合并前不应切默认写入，也不应把 research 结果自动 promotion 到 ADS。


# Agent 交接（Agent Handoff）

本文件只保留当前交接摘要和最近 3 条交接。更早内容已归档到 `archive/AGENT_HANDOFF_2026-06.md`。

> **语言约定（2026-06-01 起）**：新增交接条目一律用中文撰写；更早的英文条目保留在 archive 中，不再放回当前文件。

## 2026-06-10 GPT-5 Codex - Research additive migration 与 readiness QA

### 已完成工作

- 合并 PR #146 到 `main`，merge commit 为 `bca0e791abb57b3fb7efaa01b46e7444ac15cfb2`。
- 从 merge 后 `origin/main` 新建部署 worktree，使用 Cloud Build 构建正式 Strategy1 runner 镜像 `research-d1-main-bca0e79-20260610-01`，digest 为 `sha256:c0ae9b2ec72b1299a08db66eb02881d0d3156735c14f08193d60e4388c9cc357`。
- 将五个 Strategy1 Cloud Run jobs 更新到该 immutable digest：`strategy1-train-predict-job`、`strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`。
- 新增 `sql/research/02_research_strategy1_additive_migrations.sql`，用 idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 固化 `research_experiment_run_status.log_dir`。
- 新增 `sql/research/03_qa_research_schema_readiness.sql`，只读 `INFORMATION_SCHEMA` 检查 15 张 research 表、关键列/类型、分区、聚簇、lifecycle DEFAULT、partition filter 和 `log_dir`。
- 在 `configs/strategy1/active_step_catalog.yml` 登记 `qa_research_schema_readiness`，并更新 `sql/research/README.md`、`sql/README.md`、`sql/strategy1/README.md`。
- 新增 pytest 覆盖 research additive migration、readiness QA catalog 登记、表覆盖、lifecycle 默认值和 `log_dir`。
- 追加 `DECISION-20260610-09`，并同步 `KNOWN_CONSTRAINTS.md` / `IMPLEMENTATION_STATUS.md` / `TODO.md`。

### 重要上下文

- `01_research_strategy1_tables.sql` 仍是新环境 canonical contract，但 `CREATE TABLE IF NOT EXISTS` 不会更新已有表；后续新增 research 列必须同步 `02` migration 和 `03` readiness QA。
- 本 PR 不切 default research-first，不实现 promotion，不迁移 ADS 历史数据。
- D2 的前置变为：本 PR 合并后，再单独开 D2 default research-first PR。

### 改动文件

- `configs/strategy1/active_step_catalog.yml`
- `sql/research/02_research_strategy1_additive_migrations.sql`
- `sql/research/03_qa_research_schema_readiness.sql`
- `sql/research/README.md`
- `sql/README.md`
- `sql/strategy1/README.md`
- `tests/strategy1/test_research_contract.py`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- Cloud Build `ce178068-c6eb-4921-a3f4-c1a8ba18f917` succeeded。
- 五个 Strategy1 jobs 读回均指向 `sha256:c0ae9b2ec72b1299a08db66eb02881d0d3156735c14f08193d60e4388c9cc357`，资源/SA/args 保持原配置。
- 只读 Cloud Run boot smoke `strategy1-backtest-report-job-8krjt` succeeded。
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/research/02_research_strategy1_additive_migrations.sql` 执行为 no-op skip。
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/research/03_qa_research_schema_readiness.sql` 7 条断言全部 successful。
- `python3 -m pytest -q tests` -> 66 passed（4 个 Python / SSL 环境 warning）。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check` 通过。
- `npx --yes @dataform/cli compile dataform` 通过。
- `python3 -m compileall -q src scripts/strategy1_cloudrun scripts/strategy1` 通过。
- `git diff --check` 通过。

### 阻塞项

- 无。

### 下一步建议

- 提交并推送 `codex/research-schema-readiness`，开单独 PR。
- PR 合并后进入 Phase D2 default research-first；D3 promotion job 和 Phase E 包化继续单独 PR。

### 已更新记忆文件

- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - 年度滚动执行工程化 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260610_04_策略1年度滚动执行工程化.md`。
- PRD 将 2021 annual-selection smoke 暴露的问题收敛为三个 P0 工程要求：resolved experiment payload 自动生成、ADS additive migration、schema readiness QA。
- PRD 明确年度 rolling orchestrator 的建议入口、输入输出、run_id 命名、artifact 要求、连续 ledger 执行规则和验收标准。
- PR #144 review follow-up 已处理 5 项：`--rebalance-frequency` 固定为 `biweekly`；migration 文件不再建议冲突的 `02_strategy1_additive_migrations.sql`；schema readiness QA 使用无数字前缀并要求登记 catalog；`scripts/strategy1_cloudrun/` 标记为过渡 wrapper namespace；B26 binary 明确为 diagnostic-only reference。
- 同步更新 `IMPLEMENTATION_STATUS`、`AGENT_HANDOFF` 和 `TODO.md`。

### 重要上下文

- 本轮只写 PRD，不改 runner、不改 SQL、不改 BigQuery、不跑 Cloud Run。
- PRD 明确 P0 不改模型、不扩 LightGBM 参数、不调整 v3 gate、不把默认输出切到 `ashare_research`。
- 正式 `2021-2026` 结果必须来自单一 continuous ledger，或经过 resume-continuous QA 的 segment ledger；不能拼接年度 fresh-run。

### 改动文件

- `docs/prd/PRD_20260610_04_策略1年度滚动执行工程化.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未运行测试；本轮为文档和记忆更新。

### 阻塞项

- 无。

### 下一步建议

- 按 PRD 实现 ADS additive migration 与 schema readiness QA。
- 再实现 annual rolling orchestrator dry-run / resolved payload 生成，并用它重跑 2021 smoke。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - 年度滚动选参 2021 smoke 闭环

### 已完成工作

- 合并 PR #141 后，从 `main` commit `2565e0f` 构建并部署正式 Strategy1 Cloud Run runner 镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:2565e0f`。
- 四个正式 jobs 已更新到该镜像：`strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`。
- 重跑 2021 annual-selection candidate fanout：execution `strategy1-train-candidate-fanout-job-5f6qg` 成功，11 个候选全部 `cv_confirmation_status=passed`、`cv_fold_count=3`。
- 重跑 `select_register_predict`：execution `strategy1-select-register-predict-job-pxtbw` 成功，选中 `risk_lgbm_prd_strong_regularized_l5_l63_lr002_n300_leaf800_ff07_bf10`，`prediction_rows=808433`。
- 重跑 `backtest_report`：execution `strategy1-backtest-report-job-t5fg6` 成功，ledger、report、runner QA、lot-aware ledger QA、model diagnosis QA、tail-risk diagnosis 和 tail-risk QA 全部走完。
- 手工补齐生产 ADS additive schema：创建 `ashare_ads.ads_backtest_ledger_state_daily`，并为 `ashare_ads.ads_backtest_performance_summary` 补 4 个复合年化字段。

### 重要上下文

- 第一次 `select_register_predict` 失败是因为 annual-selection experiment 不在 `configs/strategy1/oq010_experiments_v0.json` 中；后续使用 base64 resolved experiment payload 解决。
- 第一次 `backtest_report` 失败是因为缺 `ads_backtest_ledger_state_daily`；第二次失败是因为 `ads_backtest_performance_summary` 缺复合年化字段；两者均为 BigQuery schema 未同步最新代码契约，不是模型训练或 CV 逻辑失败。
- 2021 smoke 只验证单年度链路闭环；还没有执行完整 `2021-2026` 年度滚动参数选择和连续 ledger。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- Cloud Build `945cead1-c916-42af-a471-193928c8ca78`：SUCCESS。
- `strategy1-train-candidate-fanout-job-5f6qg`：succeeded，11/11 candidate metrics updated。
- Candidate metrics：全部 `cv_confirmation_status=passed`、`cv_fold_count=3`，fold ids `cv_2018/cv_2019/cv_2020`。
- `strategy1-select-register-predict-job-pxtbw`：succeeded，selected candidate `risk_lgbm_prd_strong_regularized_l5_l63_lr002_n300_leaf800_ff07_bf10`。
- `strategy1-backtest-report-job-t5fg6`：succeeded。
- BigQuery summary：`bt_s1_annual_param_select_train2015_2019_valid2020_pred2021_n20_w075_v20260610_01` 覆盖 `2021-01-04..2021-12-31`，`total_return=-0.08075416625099796`、`compound_annual_return=-0.08394704034322242`、`annual_vol=0.18489507632796431`、`sharpe=-0.3820502523215857`、`max_drawdown=-0.1953798536113548`、`excess_return=-0.12875580760744898`。

### 阻塞项

- 无当前阻塞。2021 单年度 smoke 已闭环，但策略表现不达可接受 baseline。

### 下一步建议

- 扩展实现完整年度滚动 `2021-2026`：逐年参数选择、逐年预测生成，最后用一条连续 `ledger_exec_v1_lot100` 评价，不拼接年度 fresh-run。
- 后续正式 annual walk-forward 建议使用新的 run_id，不复用本次 smoke 的 `s1_annual_param_select_train2015_2019_valid2020_pred2021_n20_w075_v20260610_01`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - Runner research routing D1b

### 已完成工作

- 从最新 `origin/main` 新建 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-research-routing-d1b` 和分支 `codex/strategy1-research-routing-d1b`；未触碰主工作树 `/Users/fisher/Desktop/git/quant-ashare`。
- 新增 `scripts/strategy1_cloudrun/dataset_roles.py`，封装 `TableResolver`、`output_dataset_role` 校验、research opt-in 和 SQL dataset-role rewrite；默认 rewrite 排除 `acceptance_result`，避免 `ads_model_registry` 双 role 歧义。
- `RunnerConfig`、通用 CLI、resolved manifest、orchestrator status payload 和 Cloud Run job args 已透传 `output_dataset_role`；默认值保持 `ads`。
- `train_predict.py`、`prepare_matrix.py`、`select_register_predict.py`、`ledger.py`、`backtest_report.py`、`orchestrate_experiments.py`、`orchestrate_sklearn_native_search.py` 和 `state.py` 已接入 resolver；显式 research 模式下 run-scoped 表指向 `ashare_research.research_*`。
- `render_report.py`、`diagnose_model_quality.py`、`analyze_tail_risk.py`、`replay_acceptance_gate_v3.py`、`compare_oq010_experiments.py`、`diagnose_acceptance_gate_v2.py`、`diagnose_acceptance_window.py` 和 `attribute_factor_contribution.py` 已新增 `--output-dataset-role`，并在查询或 summary 回写前做 dataset-role rewrite。
- 新增 `tests/strategy1_cloudrun/test_dataset_role_routing.py`，覆盖默认 ADS、显式 research、resolver/SQL rewrite、subcommand 透传、ledger/status routing、native query helper、acceptance diagnostic helper 和 factor attribution summary 回写。
- PR #143 review follow-up 已处理：默认 ADS 子命令不下发 `--output-dataset-role=ads`，保持旧 Cloud Run 镜像兼容；显式 research 仍下发 role flag。
- `sql/research/01_research_strategy1_tables.sql` 已补 lifecycle 默认值：普通 research 输出默认 `research_status='candidate'`、`promotion_status='not_promoted'`，`research_promotion_manifest.promotion_status` 默认 `planned`。
- 新增 D1 收尾 TODO 和 `DECISION-20260610-08`，明确 D2 前必须完成 D0 DDL 部署、Cloud Run 镜像重建、runtime SA `ashare_research` 写权限和真实 research-mode smoke。
- 同步更新 `TODO.md`、`IMPLEMENTATION_STATUS`、`KNOWN_CONSTRAINTS`、`ARCHITECTURE_MEMORY`、`DECISION_LOG` 和 `AGENT_HANDOFF`。

### 重要上下文

- D1b 仍是 explicit opt-in；不切 default research-first。
- 本轮不创建或部署实际 BigQuery `ashare_research` 表，不修改 Cloud Run Job spec，不迁移历史 ADS，不实现 promotion job。
- historical BQML parity reference 仍按设计读取 ADS，不随当前 run 的 output role 改写。
- D1b 单测 / dry-run 不是 PRD D1 的真实验收；进入 D2 前必须完成显式 research-mode smoke。

### 改动文件

- `scripts/strategy1_cloudrun/dataset_roles.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `scripts/strategy1_cloudrun/prepare_matrix.py`
- `scripts/strategy1_cloudrun/select_register_predict.py`
- `scripts/strategy1_cloudrun/ledger.py`
- `scripts/strategy1_cloudrun/backtest_report.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1_cloudrun/state.py`
- `scripts/strategy1/*.py` report / diagnosis / acceptance / comparison helpers
- `configs/strategy1/cloudrun_runner_default.yml`
- `sql/research/01_research_strategy1_tables.sql`
- `sql/research/README.md`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `tests/strategy1/test_research_contract.py`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest tests -q`：57 passed。
- `PYTHONPATH=src python3 -m pytest tests/strategy1_cloudrun/test_dataset_role_routing.py tests/strategy1/test_research_contract.py -q`：21 passed。
- `python3 -m compileall -q src/quant_ashare/strategy1 scripts/strategy1_cloudrun scripts/strategy1 tests/strategy1_cloudrun/test_dataset_role_routing.py tests/strategy1/test_research_contract.py`：通过。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `npx --yes @dataform/cli compile dataform`：通过。
- `(cat sql/00_create_datasets.sql; cat sql/research/01_research_strategy1_tables.sql) | bq query --dry_run --use_legacy_sql=false --location=asia-east2`：通过。
- CLI help 覆盖 `orchestrate_experiments`、`orchestrate_sklearn_native_search` 和 `backtest_report`。
- CLI dry-run 覆盖 `orchestrate_experiments`、`orchestrate_sklearn_native_search` 和 `backtest_report` 默认 ADS 路径；两个 orchestrator dry-run 均确认默认计划不含 `--output-dataset-role`。
- 41 条程序化 self-review checks：通过。
- `git diff --check`：通过。

### 阻塞项

- 无。

### 下一步建议

- 合并 D1b 前继续保持默认 ADS；后续先做 D1 收尾验收，再单独推进 Phase D2 default research-first，Phase D3 单独实现 owner-approved promotion job；Phase E 包化时收敛读侧 routing 全局态。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - SQL render table-role routing D1a

### 已完成工作

- 从最新 `origin/main` 新建 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-research-routing-d1a` 和分支 `codex/strategy1-research-routing-d1a`；未触碰主工作树 `/Users/fisher/Desktop/git/quant-ashare`。
- 已 rebase 到最新 `origin/main`，吸收 PR #141 dynamic CV fold 修复；本分支继续承载 PR #142。
- 在 `src/quant_ashare/strategy1/sql_render.py` 接入 table role / dataset role resolver：按 catalog step 的 `inputs` / `outputs` 构造替换表，默认 ADS 不变，显式 research 需 `allow_future_research=True`。
- 增加无 step 上下文的 research 替换 fail-fast，以及重复 ADS 源表不同 research 目标的歧义保护，避免 `ads_model_registry` 被误替换到 `research_acceptance_result`。
- `scripts/strategy1_cloudrun/sql_runner.py` 的 path / step wrapper 已透传 `dataset_role` 与 `allow_future_research`，但现有调用默认仍是 ADS。
- PR #142 review follow-up 已补全非 retired Strategy1 step 的 catalog `inputs` / `outputs`，使其覆盖 SQL 中实际 `data-aquarium.ashare_ads.*` 引用。
- 新增 `tests/strategy1/test_sql_render.py` 覆盖默认 ADS、显式 research、meta dataset override、字符串字面量替换、全局 research 歧义保护和所有 active step 的 research 渲染无 ADS 残留。
- 新增 `tests/strategy1/test_strategy1_catalog.py` 覆盖 step role contract 与 SQL 实际 ADS 引用一致，避免 catalog 欠声明导致 research 渲染混写。
- 同步更新 `sql/strategy1/README.md`、`TODO.md`、`IMPLEMENTATION_STATUS`、`KNOWN_CONSTRAINTS`、`ARCHITECTURE_MEMORY` 和 `AGENT_HANDOFF`。

### 重要上下文

- 本轮是 Phase D1a render-only；未修改 `backtest_report.py` 默认参数，未部署 Cloud Run，未执行 BigQuery 写入，未创建实际 `ashare_research` 表。
- `dataset_role="research"` 仍不是普通调用默认能力；只有显式 `allow_future_research=True` 的 contract / dry-run / 后续接线验证可以使用。
- 后续新增或修改 Strategy1 SQL 中的 run-scoped ADS 引用时，必须同步 catalog `inputs` / `outputs`，否则 pytest 会在 role 覆盖或 research residual 断言中失败。
- D1b 仍需单独实现 runner CLI/config `output_dataset_role=research`、report / diagnosis / QA / acceptance/comparison 全链路读取 research output。

### 改动文件

- `src/quant_ashare/strategy1/sql_render.py`
- `configs/strategy1/active_step_catalog.yml`
- `scripts/strategy1_cloudrun/sql_runner.py`
- `tests/strategy1/test_sql_render.py`
- `tests/strategy1/test_strategy1_catalog.py`
- `sql/strategy1/README.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m pytest tests`：42 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `npx --yes @dataform/cli compile dataform > /tmp/quant_ashare_dataform_compile_d1a_rebased.json`：通过。
- catalog ADS role 覆盖扫描：`missing_count=0`。
- 88 条程序化 self-review checks：通过。
- `python3 -m compileall -q src/quant_ashare/strategy1 scripts/strategy1_cloudrun`：通过。
- `git diff --check`：通过。

### 阻塞项

- 无。

### 下一步建议

- Phase D1b 单独 PR：为 Cloud Run runner 增加显式 `output_dataset_role=research` CLI/config 接线，并让 report、diagnosis、QA、acceptance/comparison 从同一 resolver 读取 research output；完成前不要切 default research-first。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - Research table contract D0

### 已完成工作

- 从最新 `origin/main` 新建 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-research-contract` 和分支 `codex/add-research-table-contract`；未触碰主工作树 `/Users/fisher/Desktop/git/quant-ashare`。
- 在 `sql/00_create_datasets.sql` 中新增 `data-aquarium.ashare_research` schema contract。
- 新增 `sql/research/01_research_strategy1_tables.sql`，定义 Strategy1 research 表契约：训练面板、模型注册、预测、候选池、组合目标、订单计划、回测成交/持仓/NAV/ledger state/summary、信号监控、acceptance result、experiment run status 和 append-only promotion manifest。
- 新增 `sql/research/README.md`，说明 D0 只定义 contract，不切 runner 默认写入。
- 更新 `configs/strategy1/active_step_catalog.yml`，记录 research contract SQL，并校准 `model_prediction_daily` / `order_plan_daily` 的分区列元数据。
- 新增 `tests/strategy1/test_research_contract.py`，校验 catalog research target 与 DDL 一致、表名使用 `research_*`、分区列一致，且默认 `dataset_role="research"` 仍 fail-fast。
- PR #140 review follow-up 已处理：`experiment_run_status` 当前侧通过 `ads_dataset: ashare_meta` 解析到既有 `ashare_meta.strategy1_experiment_run_status`；`resolve_table_role` 支持 per-role dataset/project override；`build_order_plan.partition_columns` 与 `order_plan_daily` 的 `rebalance_date` 对齐，并新增 step 输出分区一致性测试。
- 同步更新 `TODO.md`、`IMPLEMENTATION_STATUS`、`KNOWN_CONSTRAINTS`、`ARCHITECTURE_MEMORY` 和 `AGENT_HANDOFF`。

### 重要上下文

- 本轮是 Phase D0 contract-only；未创建实际 BigQuery dataset / table，未切 `output_dataset_role=research`，未迁移历史 ADS，未实现 promotion job。
- `resolve_table_role(..., dataset_role="research")` 默认仍必须 fail-fast；`allow_future_research=True` 在 D0 用于 contract-only 解析与测试，D1a 后也用于 SQL render-only / dry-run 接线验证。
- 当前策略产出表默认仍指向 `ashare_ads`；meta / orchestration role 可用 per-role dataset override，当前只用于 `experiment_run_status`。
- 后续 D1b 才做实际 runner 显式 research routing，D2 才做 default research-first，D3 才做 owner-approved promotion。

### 改动文件

- `sql/00_create_datasets.sql`
- `sql/research/01_research_strategy1_tables.sql`
- `sql/research/README.md`
- `configs/strategy1/active_step_catalog.yml`
- `src/quant_ashare/strategy1/table_roles.py`
- `tests/strategy1/test_research_contract.py`
- `tests/strategy1/test_strategy1_catalog.py`
- `sql/README.md`
- `sql/strategy1/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest tests`：32 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `npx --yes @dataform/cli compile dataform > /tmp/quant_ashare_dataform_compile_research_contract.json`：通过。
- `(cat sql/00_create_datasets.sql; cat sql/research/01_research_strategy1_tables.sql) | bq query --dry_run --use_legacy_sql=false --location=asia-east2`：通过。
- `git diff --check`：通过。

### 阻塞项

- 无。

### 下一步建议

- Phase D1b 单独 PR：新增显式 runner `output_dataset_role=research` routing，并让 report / diagnosis / QA / acceptance 从同一 table-role resolver 读取 research output。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - OQ-005 IAM bootstrap TODO 收口

### 已完成工作

- 复核 [PR #126](https://github.com/gthbj/quant-ashare/pull/126) 已合并到 `main`，merge commit 为 `54fe077bb656f23b5ff9384f348e49b7a5259e94`。
- 复核 `orchestration/workflows/bootstrap_scheduler_iam.sh` 已包含 Workflows runtime SA 所需的 `roles/run.viewer` 与 `roles/run.jobsExecutorWithOverrides`，并移除旧 job-level `roles/run.invoker`。
- 将 `TODO.md` 中 “OQ-005：合并 2026-06-09 scheduled ODS run 暴露的 Cloud Run Job IAM bootstrap 修正” 勾选完成。
- 同步更新 `IMPLEMENTATION_STATUS` 与 `AGENT_HANDOFF`，说明该项是过期 TODO 清理，不是新增运行逻辑。

### 重要上下文

- 本轮未修改 `orchestration/workflows/bootstrap_scheduler_iam.sh`；代码修复已由 PR #126 进入 `main`。
- 仍未关闭 OQ-005；剩余主要是 cutover 后短观察窗记录和少量非阻断运维收尾。

### 改动文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `gh pr view 126 --json number,title,state,mergedAt,url,mergeCommit,headRefName,baseRefName`：确认 PR #126 为 `MERGED`。
- `git grep` / `git show origin/main:orchestration/workflows/bootstrap_scheduler_iam.sh`：确认 `roles/run.viewer`、`roles/run.jobsExecutorWithOverrides` 和移除旧 job-level `roles/run.invoker` 的 bootstrap 口径仍在 `main`。

### 阻塞项

- 无。

### 下一步建议

- 继续处理 OQ-005 cutover 后短观察窗记录；该项完成后再判断 OQ-005 是否可以正式收口。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - Dataform generated SQLX drift cleanup

### 已完成工作

- 从最新 `origin/main` 新建分支 `codex/fix-dataform-generated-drift`。
- 运行 `scripts/dataform/generate_sqlx_from_sql.py`，同步 6 个 stale generated SQLX 文件：
  - `dataform/definitions/setup/01_create_meta_tables.sqlx`
  - `dataform/definitions/dim/02_dim_stock.sqlx`
  - `dataform/definitions/metadata/01_core_table_column_descriptions.sqlx`
  - `dataform/definitions/assertions/01_core_smoke_checks.sqlx`
  - `dataform/definitions/assertions/03_index_benchmark_checks.sqlx`
  - `dataform/definitions/assertions/12_windowed_index_refresh_checks.sqlx`
- 勾选 `TODO.md` 中的 Dataform generated SQLX drift cleanup 项，并同步 `IMPLEMENTATION_STATUS` / `AGENT_HANDOFF`。
- 按 PR review 的 Low 防复发建议，新增 `tests/dataform/test_generated_sqlx.py`，直接调用 `generate_sqlx_from_sql.py --check`。

### 重要上下文

- 本轮只修 generated SQLX drift；canonical `sql/` 与 `dataform/action_manifest.json` 没有改动。
- 防复发测试复用真实生成脚本的 check 模式，不复制生成逻辑，也不会写出文件。
- 未运行 BigQuery、Cloud Run、Workflows 或生产 Dataform invocation。

### 改动文件

- `dataform/definitions/setup/01_create_meta_tables.sqlx`
- `dataform/definitions/dim/02_dim_stock.sqlx`
- `dataform/definitions/metadata/01_core_table_column_descriptions.sqlx`
- `dataform/definitions/assertions/01_core_smoke_checks.sqlx`
- `dataform/definitions/assertions/03_index_benchmark_checks.sqlx`
- `dataform/definitions/assertions/12_windowed_index_refresh_checks.sqlx`
- `tests/dataform/test_generated_sqlx.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `python3 -m pytest tests/dataform/test_generated_sqlx.py`：通过。
- `python3 -m pytest tests`：25 passed。
- `npx --yes @dataform/cli compile dataform > /tmp/quant_ashare_dataform_compile.json`：通过。
- `git diff --check`：通过。

### 阻塞项

- 无。

### 下一步建议

- 合并本 cleanup PR 后，后续修改 manifest 覆盖的 canonical SQL 时继续同时提交 generated SQLX，并保持 `--check` clean。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - 项目结构重构 Phase A-C 实现

### 已完成工作

- 新增 `configs/strategy1/active_step_catalog.yml`，记录 Strategy1 SQL stable step、旧路径、目标路径、调用方、参数契约、table role、当前 ADS role 与未来 research role。
- 新增 `src/quant_ashare/strategy1/catalog.py`、`sql_render.py`、`table_roles.py`、`retired_lint.py` 和 `pyproject.toml`。
- 将当前 active/shared Strategy1 SQL 从旧 `sql/ml/strategy1/**`、`sql/cloudrun/strategy1/**` 迁移到 `sql/strategy1/**`；旧目录只保留 historical/audit README。
- `backtest_report.py`、`orchestrate_sklearn_native_search.py`、risk-feature manifest、v3 replay QA helper 和 SQL runbook 已切到 catalog step / 新命名空间。
- 恢复 `ledger.py` 中被后置同名函数覆盖的 resume 参数校验，使现有 ledger resume 单测通过。
- PR #136 review follow-up 已修复 retired linter 递归扫描、research role fail-fast、audit-only README 说明、Dataform drift TODO 和自查文档协议问题。

### 重要上下文

- 本轮只实现 PRD Phase A/B/C；未创建 `ashare_research` dataset，未默认 research-first，未迁移历史 ADS/GCS，未迁移 Cloud Run Job entrypoint。
- 当前 `table_roles.resolve_table_role(..., dataset_role="research")` 会 fail-fast；默认不传 `dataset_role` 时仍返回 `data-aquarium.ashare_ads.*`。
- Owner 已确认 PR #136 可一次性合并 Phase A/A2/B/C；后续 Phase D/E 仍按 PRD 单独拆分。
- Dataform `--check` 失败是既有 generated SQLX stale/missing；本分支相对 `origin/main` 没有 `dataform/` diff。

### 改动文件

- `configs/strategy1/active_step_catalog.yml`
- `src/quant_ashare/strategy1/**`
- `sql/strategy1/**`
- `scripts/strategy1_cloudrun/**` wrapper 相关文件
- `scripts/strategy1/run_acceptance_gate_v3_replay_qa.py`
- `docs/策略1CloudRun训练回测运行手册.md`
- `docs/策略1报告GCS上传运行手册.md`
- `sql/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src:. <venv>/bin/python -m pytest tests/strategy1 tests/strategy1_cloudrun tests/pipeline_control`：24 passed。
- `PYTHONPATH=src /tmp/quant-ashare-structure-venv/bin/python -m quant_ashare.strategy1.retired_lint`：通过。
- catalog validate、active step render smoke、compileall、`backtest_report --dry-run`、search orchestrator `--help`、v3 replay QA helper `--help`、`git diff --check` 均通过。
- `scripts/dataform/generate_sqlx_from_sql.py --check`：失败，原因是既有 `dataform/definitions/**` generated SQLX stale/missing；本分支无 `dataform/` diff。

### 阻塞项

- 无实现阻塞；Dataform generated SQLX stale 需要单独 cleanup PR 或 owner 决策。

### 下一步建议

- 后续 Phase D/E 单独做 `ashare_research` table contract、optional research routing、default research-first、promotion job 和 deeper package split。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - Strategy1 年度滚动选参 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260610_03_策略1年度滚动选参.md`。
- PRD 定义年度 walk-forward 参数选择方案：用上一整年 valid 选择参数和方向，再用选中参数在最近 5 年 final refit，预测并回测下一年。
- 年度窗口固定为 `2021` 至 `2026`：从 `2015-2019 train / 2020 valid / 2016-2020 final refit / 2021 backtest` 开始逐年滚动。
- P0 固定 feature set、股票池、成本、`20` 只持仓、`7.5%` 单票上限、`biweekly` 和 Cloud Run Python `ledger_exec_v1_lot100`，只搜索 11 个预先冻结的 LightGBM regression 可选候选；B26 binary 只作为 diagnostic-only reference。
- valid 选参门按 owner 确认口径写入：`valid_rank_ic > 0`、`valid_top_minus_bottom > 0`、五指数任一 valid 超额收益 `> 0`、valid 最大回撤 `>= -33.33%`、`valid_sharpe >= 0.3`、`valid_calmar >= 0.3`、五指数任一 `valid_excess_calmar_ratio > 0.3`；PR #137 review follow-up 后明确删除 `valid_total_return > 0` 只是避免重复硬门，不表示允许负收益候选通过。
- PRD 明确年度预测可分年生成，但最终评价必须来自一条连续 ledger，不能拼接每年 fresh-run。
- 同步更新 `IMPLEMENTATION_STATUS`、`AGENT_HANDOFF`、`DECISION_LOG` 和 `TODO`。

### 重要上下文

- 本轮是 PRD-only，不改 runner、不改 SQL、不运行 BigQuery / Cloud Run / Dataform。
- 该方案和刚完成的固定 R14 annual walk-forward 不同：固定 R14 只验证一个参数；本文要求每年从固定 regression 可选候选池中重新选参数。
- valid 年只用于选择下一年参数，不能作为同年最终样本外成绩。
- 候选池必须先冻结并生成 hash；如果后续新增候选，必须新开 experiment version。

### 改动文件

- `docs/prd/PRD_20260610_03_策略1年度滚动选参.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

### 测试 / 验证

- 未执行。此次为 PRD 与项目记忆更新。

### 阻塞项

- 无代码阻塞。

### 下一步建议

- owner review PRD。若认可，先实现 `2021` 单年度 smoke，再扩展到完整 `2021-2026` annual walk-forward 参数选择和连续 ledger 对比。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - 项目结构重构总 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260610_02_项目结构重构方案.md`。
- Review follow-up 后，PRD 将项目结构重构拆为：active path catalog 与防误用护栏、table role / dataset role resolver、Strategy1 shared SQL 稳定命名空间、Python package foundation、`ashare_research` / `ashare_ads` 生命周期隔离、深层包拆分与阶段性命名收敛。
- Owner 已确认 PRD 关键决策：新增 BigQuery `ashare_research` dataset，使用 `research_*` 表名前缀，`accepted != promoted`，先做 table-role abstraction 后 research-first，采用 `sql/strategy1/**` 和 `src/quant_ashare/**`，短期保留 `scripts/strategy1_cloudrun/**` wrapper，P0 不强制创建 `docs/retired/`。
- PRD 明确旧 BQML-only SQL / SQL ledger runner 已按前置 PRD 退役；当前剩余 Strategy1 SQL 多数是 Cloud Run Python path 仍使用的 active shared SQL，应从调用方反推并覆盖 `sql/ml/strategy1/**`、`sql/cloudrun/strategy1/**`，再迁移到 `sql/strategy1/**`。
- PRD 增补 retired linter allowlist、SQL 参数契约校验、`bqml_reference_run_id` legacy exception registry、Python package 交付策略和 research promotion manifest 口径。
- 同步更新 `.agent/memory/IMPLEMENTATION_STATUS.md`、`.agent/memory/AGENT_HANDOFF.md`、`.agent/memory/DECISION_LOG.md` 和 `TODO.md`。

### 重要上下文

- 本轮是 PRD-only，不改代码、不改 SQL、不运行 BigQuery / Cloud Run / Dataform。
- 已追加 `DECISION-20260610-05` 记录 owner 确认的结构重构决策；不新增 `KNOWN_CONSTRAINTS.md` 约束，因为本 PRD 尚未实现代码或物理 BigQuery 资源。
- 结构重构事项仍在 `TODO.md` P1；当 owner 决定启动 P1 工程治理或在 OQ-010/R14 空档穿插推进时，第一步是 PR-A：建立 active step catalog、retired reference linter 和 README/runbook 口径护栏；第二步 PR-A2 做 table role / dataset role resolver 且仍解析到 `ashare_ads`。`ashare_research` dataset / table contract 应后置为单独 PR，不和目录搬迁或默认写入切换混做。

### 改动文件

- `docs/prd/PRD_20260610_02_项目结构重构方案.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

### 测试 / 验证

- 文档改动；未运行 BigQuery、Cloud Run、pytest 或 Dataform。
- 建议提交前至少运行 `git diff --check`。

### 阻塞项

- 无。

### 下一步建议

- 结构重构仍按 `TODO.md` 的 P1 工程治理项处理；当 owner 决定启动或在 OQ-010/R14 空档穿插推进时，从 PR-A 开始：建立 active step catalog、retired reference linter 和 README/runbook 口径护栏；不移动文件、不改运行行为。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - Strategy1 旧 BQML / SQL ledger runner P0 退役实现

### 已完成工作

- 删除 BQML-only `sql/ml/strategy1/02_train_bqml_logistic_candidates.sql`、`03_select_model_and_register.sql`、`04_predict_daily.sql`。
- 删除 SQL ledger fallback `sql/ml/strategy1/08_run_backtest.sql`。
- 删除旧 OQ-010 SQL/BQML 调度器 `scripts/strategy1/run_oq010_experiments.py`，避免保留会调用已删除 `02-04` / `08` 的失效入口。
- `scripts/strategy1_cloudrun/backtest_report.py` 已移除 `--use-bq-ledger` 参数、`bigquery_sql` backend 分支和对 `08_run_backtest.sql` 的调用；默认固定走 Cloud Run Python ledger。
- `scripts/strategy1_cloudrun/orchestrate_experiments.py` 与 `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py` 已移除 `--use-bq-ledger` 透传。
- 文档和项目记忆已同步为当前口径：active path 为 Cloud Run Python training / prediction / ledger + 共享 SQL `01`、`05-07`、`09-10`、`12`、`16-24`。

### 重要上下文

- 本次只删除旧执行入口，不删除历史 ADS / GCS artifact、历史 BQML run/backtest id 或 v3 replay/QA。
- `sql/ml/strategy1/01_build_training_panel.sql`、`05_build_candidates.sql`、`06_build_portfolio_targets.sql`、`07_build_order_plan.sql`、`09_build_metrics_and_report_inputs.sql`、`10_qa_runner_outputs.sql`、`12_qa_model_diagnosis_outputs.sql` 和 `16-24` 仍是当前 Cloud Run Python path 的共享 SQL / QA 面。
- legacy FLOAT 股数审计只保留 Python `--use-float-ledger`；`--use-bq-ledger` 不再存在。

### 改动文件

- `scripts/strategy1_cloudrun/backtest_report.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1/run_oq010_experiments.py`
- `sql/ml/strategy1/02_train_bqml_logistic_candidates.sql`
- `sql/ml/strategy1/03_select_model_and_register.sql`
- `sql/ml/strategy1/04_predict_daily.sql`
- `sql/ml/strategy1/08_run_backtest.sql`
- `sql/ml/strategy1/README.md`
- `sql/README.md`
- `docs/prd/PRD_20260609_02_策略1旧BQMLSQLRunner退役.md`
- `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`
- `docs/prd/PRD_20260603_05_策略1实验并发调度与隔离.md`
- `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`
- `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`
- `docs/策略1-ml_pv_clf_v0-runner设计.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `docs/策略1实验并发调度器运行手册.md`
- `dataform/definitions/assertions/03_index_benchmark_checks.sqlx`
- `sql/meta/02_strategy1_experiment_run_status.sql`
- `sql/qa/03_index_benchmark_checks.sql`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

### 测试 / 验证

- 未执行 BigQuery、Cloud Run、pytest 或 replay。

### 阻塞项

- 无。

### 下一步建议

- 等 PR review；如果 reviewer 只要求补文档口径或移除残余引用，直接在本分支修。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - historical backfill core smoke 修复

### 已完成工作

- 合并 PR #132 并删除远端分支。
- 从最新 `main` 重新部署 `ashare-pipeline-control`，新 revision 为 `ashare-pipeline-control-00007-tst`。
- 重新触发 2015 年 warehouse backfill execution `209bd2bf-86f4-455c-85c7-b6b1f4ec8025`。
- 诊断新失败点：流程已越过 `dim_stock` 生命周期缺口，失败于 core smoke 的旧全表下限断言。
- 新建分支 `codex/fix-historical-backfill-core-smoke`，将 core smoke 从“不得有 2019 前行”改为“不得早于 A 股日线支持历史下限 `1990-12-19`”。
- 同步更新 DWD price / valuation metadata 描述，明确默认全量/日常路径仍是 2019+，owner 显式 backfill 可写指定历史训练窗口。

### 重要上下文

- 失败 execution：`209bd2bf-86f4-455c-85c7-b6b1f4ec8025`。
- 失败 BigQuery job：`4a6b55a4-4cbc-4bad-9c22-8ed8265f8072`。
- 失败文案：`dwd_stock_eod_price must not write rows before dwd_start_date`。
- 该失败不是缺 ODS 数据，也不是 #132 未生效；它是 core smoke 旧全局不变量和 explicit historical backfill 新语义冲突。

### 改动文件

- `sql/qa/01_core_smoke_checks.sql`
- `sql/metadata/01_core_table_column_descriptions.sql`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 已执行生产 backfill 重跑并定位失败点。
- 未执行 SQL dry-run 或重新触发 backfill；需合并部署后再跑。

### 阻塞项

- 合并部署前，2015 年 backfill 仍会命中旧线上 core smoke。

### 下一步建议

- 提交并合并本分支。
- 部署新的 `ashare-pipeline-control` SQL bundle。
- 重新触发 `2015-01-01 ~ 2015-12-31` backfill；若通过，再按年触发 2016-2018。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - dim_stock 历史生命周期修复

### 已完成工作

- 诊断 2015 年 backfill execution `be12a12f-1e65-4cef-b60d-3945ef8da13a` 的新失败点。
- 确认 PR #130 修复有效：execution 已越过指数 DWD 和指数 QA，进入股票 DWD/DWS 后失败于 `QA-WIN-13`。
- 新建分支 `codex/fix-historical-dim-stock-lifecycle`，修复 `dim_stock` 历史生命周期：
  - `missing_from_stock_basic` 从全量 ODS daily 派生，不再只看 2019+ daily。
  - `stock_basic_enriched.list_date` 在 `stock_basic.list_date` 晚于首个日线交易日时，用 `first_trade_date` 作为历史生命周期下限。
- PR #132 review follow-up：删除重复的 `daily_codes` CTE，让 `missing_from_stock_basic` 直接复用 `daily_lifecycle`，避免同一全量 ODS daily 外表被扫描两次。

### 重要上下文

- 2015 年 QA 缺口为 `5,486` 行、`76` 个代码。
- 分类结果：`75` 个代码是 `before_list_date`，`1` 个代码 `000022.SZ` 是 `missing_dim_stock`。
- 当前失败后的 2015 DWD/DWS 已有部分写入；后续重跑窗口 SQL 会按窗口 DELETE/INSERT 覆盖，不需要单独清理。

### 改动文件

- `sql/dim/02_dim_stock.sql`
- `sql/metadata/01_core_table_column_descriptions.sql`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 已执行只读诊断 BigQuery 查询，确认缺口原因。
- 未执行 SQL dry-run 或重新触发 backfill；需合并部署后再跑。

### 阻塞项

- 合并部署前不要继续触发 2015/2016/2017/2018 补数，否则仍会命中旧 `dim_stock` 生命周期口径。

### 下一步建议

- 提交并合并本分支。
- 部署新的 `ashare-pipeline-control` SQL bundle。
- 重新触发 `2015-01-01 ~ 2015-12-31` backfill；成功后再按年跑 2016-2018。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-09 GPT-5 Codex - 2015-2018 历史 backfill 下限修复

### 已完成工作

- 新建 worktree `/Users/fisher/Desktop/git/quant-ashare-fix-2015-index-backfill`，分支 `codex/fix-2015-index-backfill`。
- 修复 `ashare_warehouse_window_refresh` 历史 backfill 被 `2019-01-01` 下限拦截的问题。
- 股票 DWD/DWS 窗口、指数 DWD 窗口、market-state 窗口和股票 / 指数窗口 QA 均改为按 `warehouse_mode` 区分日期下限：`daily_current` 保持 2019+，显式 `backfill` 允许 owner 指定 2019 年以前窗口。

### 重要上下文

- 2015 年 backfill execution `2eea35d1-21bc-4c4c-b610-90b57170819a` 失败于指数 DWD 窗口刷新，错误为 `index DWD window refresh requires write_end_date >= write_start_date`。
- 根因不是 workflow 参数入口或 ODS readiness；ODS readiness 已通过，失败发生在指数窗口 SQL 的固定下限计算。
- 本 PR 不自动执行补数；合并部署后需要重新从 2015 年窗口开始触发。

### 改动文件

- `sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `sql/incremental/02_refresh_index_dwd_window.sql`
- `sql/incremental/03_refresh_market_state_window.sql`
- `sql/qa/10_windowed_stock_refresh_checks.sql`
- `sql/qa/12_windowed_index_refresh_checks.sql`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未执行 SQL dry-run 或生产补数验证；本轮按 owner 要求先修代码并提 PR。

### 阻塞项

- 无代码阻塞。
- 合并部署前不要继续触发 2016-2018 补数，否则仍会命中旧线上 SQL。

### 下一步建议

- 合并并部署 Workflows SQL bundle 后，重新触发 `2015-01-01 ~ 2015-12-31` backfill。
- 2015 年成功后，再按年触发 `2016`、`2017`、`2018`。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-09 GPT-5 Codex - Strategy1 R14 长训练窗口回测 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260609_01_策略1R14长训练回测.md`。
- 文档定义固定 R14 方法的长训练窗口实验：名义训练窗口 `2015-04-01 ~ 2019-12-31`，先跑 `2020-01-02 ~ 2022-12-30` 的 `10` 只 / `20` 只双组合 diagnostic backtest；`2023-01 ~ 2026-06-09` 追加回测视 P0 结果和 owner 决策而定，若追加也跑两个组合。
- P0 组合设为 `target_holdings=10` / `max_single_weight=15%` 与 `target_holdings=20` / `max_single_weight=7.5%`，`rebalance_frequency=biweekly`。
- 文档明确 5d 标签 embargo、2015-2018 DWD/DWS 前置补建、2020-2022 diagnostic 不写 production accepted registry，以及追加段不能和 P0 fresh segment 拼接成正式连续回测，除非 Cloud Run Python ledger resume 已实现并通过 resume consistency QA。

### 重要上下文

- 当前 raw ODS 股票行情层已有 2015 起数据，但策略实际 DWD/DWS 输入层当前从 2019 起；该实验前必须先审计并补齐 2015-2018 策略输入层。
- R14 是 `lightgbm_regression`，训练目标为 `target_return=fwd_xs_ret_5d`；若不做 embargo，2019 年末训练样本会读取 2020 回测期收益形成标签。
- 本轮只写 PRD，未执行 BigQuery / Cloud Run。

### 改动文件

- `docs/prd/PRD_20260609_01_策略1R14长训练回测.md`

### 测试 / 验证

- 未执行。此次为 PRD 与项目记忆更新。

### 阻塞项

- 无代码阻塞。
- 实验执行前需要先做 2015-2018 DWD/DWS、risk feature、market-state 和 5d label embargo 覆盖审计。

### 下一步建议

- 执行 PRD P0-A 只读覆盖审计。
- 若缺 2015-2018 DWD/DWS，制定最小 backfill / rebuild 计划。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-09 GPT-5 Codex - 清理旧 Composer warehouse refresh helper

### 已完成工作

- 删除 `scripts/pipeline/run_warehouse_refresh.py`，避免后续误用 `gcloud composer environments run` 触发已退役的 Composer 环境。
- 更新 OQ-005 约束与交接，明确后续补跑 / QA-only / full rebuild 以 Workflows runbook 和 `orchestration/workflows/**` 为准。

### 重要上下文

- 当前生产调度入口已经是 `Cloud Scheduler + Cloud Workflows`，`ashare-composer` 已删除。
- `orchestration/composer/**` 仍只保留为 retired / audit-only 历史快照；本轮没有改该目录。

### 改动文件

- `scripts/pipeline/run_warehouse_refresh.py`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未执行。此次为删除旧运维 helper 和记忆同步，不跑生产任务。

### 阻塞项

- 无。

### 下一步建议

- 等 PR review；若通过，合并后可继续 OQ-005 cutover 后短观察窗记录。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

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

## 2026-06-09 GPT-5 Codex - Workflows Cloud Run Job IAM follow-up

### 已完成工作

- 给 `ashare-workflows-runtime@data-aquarium.iam.gserviceaccount.com` 在 `ashare-ingest-current-scope` Cloud Run Job 上补 `roles/run.jobsExecutorWithOverrides`。
- 给同一 runtime SA 补项目级 `roles/run.viewer`，用于读取 Cloud Run operation / execution 状态。
- 更新 `orchestration/workflows/bootstrap_scheduler_iam.sh`，将 ODS ingestion job 权限从 job-level `roles/run.invoker` 改为 `roles/run.jobsExecutorWithOverrides`，并移除旧 job-level `run.invoker`。
- 更新 `orchestration/workflows/README.md` 与项目记忆，记录真实运行暴露的权限口径。

### 重要上下文

- `roles/run.invoker` 只包含 `run.jobs.run`，不足以支持 workflow 传 overrides 启动 Cloud Run Job。
- `roles/run.jobsExecutorWithOverrides` 允许启动带 overrides 的 Job，但不包含 `run.operations.get`；Workflows 轮询 Cloud Run operation 还需要 `roles/run.viewer`。

### 改动文件

- `orchestration/workflows/bootstrap_scheduler_iam.sh`
- `orchestration/workflows/README.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 正在用 `ashare_ods_ingestion_daily` manual recovery execution `39e42cbf-c140-4e04-9207-27bfff637ee8` 验证。

### 阻塞项

- 无代码阻塞；等待重跑 execution terminal 状态。

### 下一步建议

- 若重跑成功，继续看 child `ashare_warehouse_window_refresh` 是否完成。
- 合并 IAM bootstrap 修正 PR，避免未来重新 bootstrap 后复现 20:00 权限失败。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
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


---

## Handoff - 2026-06-09 - Cloud Run ledger resume implementation start

- Model: GPT-5 Codex
- Branch/worktree: `codex/prd-cloudrun-ledger-resume` / `/Users/fisher/Desktop/git/quant-ashare-ledger-resume-prd`
- Owner request: 在 PR #127 分支上开始实现 Cloud Run Python ledger resume。
- Changed: added resume fields to Strategy1 experiment config/CLI params; added Cloud Run Python ledger state persistence and parent-state restore path; added ADS state table DDL; updated SQL contract defaults/QA for `rebalance_anchor_start` and `cloudrun_lot100_resume_v1`; added full-vs-resume QA SQL.
- Validation: not run per owner workflow unless explicitly requested.
- Next: review PR #127 comments/CI after push; then run targeted unit/SQL/Cloud Run smoke only if owner asks.


---

## Handoff - 2026-06-10 - PR #127 ledger resume review follow-up

- Model: GPT-5 Codex
- Branch/worktree: `codex/prd-cloudrun-ledger-resume` / `/Users/fisher/Desktop/git/quant-ashare-ledger-resume-prd`
- Owner request: 看 PR #127 comment；认可实现 review 中的 6 个问题并直接修复。
- Changed: fixed missing imports/constants/dataclass fields, wired resume manifest/CLI/SQL params into `LedgerParams`, replaced fresh-only fail-fast with lot100 parent-state restore, added ledger state writes/deletes, corrected resume policy and rebalance anchor QA, and fixed `25_qa_cloudrun_ledger_resume_outputs.sql` to use `ashare_ads` plus current ADS trade/nav columns.
- Validation: not run per owner workflow unless explicitly requested.
- Next: review PR #127 comments/CI after push; run targeted unit tests and a small full-vs-resume smoke only if owner asks.

## 2026-06-10 - Strategy1 回测复合年化收益 PRD

日期: 2026-06-10
Agent ID: Codex
Agent 实例 ID: 当前 Codex desktop session
模型: GPT-5 Codex
运行环境: `/Users/fisher/Desktop/git/quant-ashare-compound-annual-prd`
Run ID: doc-only
相关 issue/PR: 待创建 PR

### 已完成工作

- 新增 `docs/prd/PRD_20260610_01_策略1回测复合年化收益.md`。
- PRD 定义新增 `compound_annual_return`、`return_period_count`、`annualization_target_period_count`、`annualization_method`，并要求旧 `annual_return` 保留为 legacy。
- PRD 明确后续 report、diagnosis、v3 acceptance gate、replay QA 默认读复合年化口径；v3 缺复合字段不得 fallback 到 legacy 年化后通过。
- 根据 PR #134 review 补充：`return_period_count` 固定为 NAV 有效交易日数减 1；compound Sharpe 会系统性影响阈值，启用前需 replay 差异表和 owner 阈值确认；`select_register_predict.py` 纳入 registry 指标传播影响面。
- 更新 `TODO.md` 和 `IMPLEMENTATION_STATUS.md`。

### 重要上下文

- owner 已确认项目中年化 / 月化 / 日化默认按复利口径。
- 近期 R14 长训练回测暴露 `ads_backtest_performance_summary.annual_return` 与按 NAV 交易日数补算的复合年化不同，需避免后续混用。
- 本次 PRD 是后续代码实现前置说明，不改变任何历史 backtest artifact。

### 改动文件

- `docs/prd/PRD_20260610_01_策略1回测复合年化收益.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- 未运行测试；文档-only 变更。

### 阻塞项

- 无。后续是否批量回填历史 run 的复合年化字段需要 owner 决策。

### 下一步建议

1. review PRD。
2. 另开实现 PR，扩展 summary schema / SQL / report / v3 acceptance / QA。
3. 用一个小规模 backtest smoke 验证 `compound_annual_return` 可从 NAV 重算。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

## 2026-06-10 - Strategy1 年度滚动选参动态 CV fold 修复

日期: 2026-06-10
Agent ID: Codex
Agent 实例 ID: codex/fix-dynamic-cv-folds
模型: GPT-5 Codex
运行环境: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-dynamic-cv`
Run ID: n/a
相关 issue/PR: pending

### 已完成工作
- 修复 Strategy1 Cloud Run Python CV fold 硬编码 `2021/2022/2023` 的问题，改为基于当前 `cv_panel` 的 train 年份动态生成最多 3 个 rolling fold。
- 新增单元测试覆盖年度滚动选参窗口 `2015-2019 train + 2020 valid` 应生成 `cv_2017/cv_2018/cv_2019`，以及旧搜索窗口完整边界仍保持 `2019-04-03..2023-12-31 -> cv_2021/cv_2022/cv_2023`。

### 重要上下文
- 2021 annual-selection smoke 暴露 `cv_fold_count=0`，原因是 CV panel 实际覆盖 `2015-2020`，但旧代码固定寻找 `2021/2022/2023` eval 年。
- 本修复只解决 CV fold 生成口径；不改变 valid/test/backtest gate，也不实现 selected final refit 云端化。

### 改动文件
- `scripts/strategy1_cloudrun/train_predict.py`
- `tests/strategy1_cloudrun/test_dynamic_cv_folds.py`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证
- `python3 -m pytest tests` 34 passed。

### 阻塞项
- 无。

### 下一步建议
- 合并后重跑 2021 annual-selection smoke 的 candidate fanout，确认 `cv_fold_count=3` 且 CV 指标不再为 NULL/NaN。
- 后续单独实现 selected final refit 云端化，避免本地下载大 matrix。

### 已更新记忆文件
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

## 2026-06-10 - OPEN_QUESTIONS 格式收口

日期: 2026-06-10
Agent ID: Codex
Agent 实例 ID: main
模型: GPT-5 Codex
运行环境: main worktree `/Users/fisher/Desktop/git/quant-ashare`
Run ID: n/a
相关 issue/PR: memory hygiene

### 已完成工作
- 将 `.agent/memory/OPEN_QUESTIONS.md` 收敛为只包含当前开放问题表格。
- 删除 OQ-010 与 OQ-011 之间导致 Markdown 表格断开的空行。
- 从 `OPEN_QUESTIONS.md` 移除冗余历史执行备注；历史细节继续以本 archive、`IMPLEMENTATION_STATUS.md` 和相关 PR / PRD 为追溯来源。

### 重要上下文
- 当前开放问题表只保留 OQ-010、OQ-011、OQ-012。
- OQ-005 已归档到 `.agent/memory/archive/CLOSED_QUESTIONS.md`，后续短观察窗属于运维记录，不再作为开放问题放回 `OPEN_QUESTIONS.md`。
- `OPEN_QUESTIONS.md` 后续不应继续追加流水账式执行备注；开放问题关闭后应移入 `archive/CLOSED_QUESTIONS.md`，执行交接写入本 archive 或 `IMPLEMENTATION_STATUS.md`。

### 测试 / 验证
- 用脚本检查 `OPEN_QUESTIONS.md` 表格行列数一致。
- `git diff --check` 通过。


<!-- PRD_20260612_03 active handoff rotation: original text below is moved without rewriting. -->

## 2026-06-12 - Active handoff summary blocks before PRD_03 rotation

> 当前交接补充（2026-06-12，GPT-5.5，PR #199 确认轮微修）
> - 复核 Claude commit `1fa12c4` 时发现 resolver 真实记忆解析仍回落 CA-off：已改为可从最高优先级 CA-on 段取 backtest、从后续段补 prediction，并新增真实记忆形态 fixture；实测解析到 `bt_..._ca01`。
> - `TODO.md` 删除残留的旧 true-five-year baseline open 路线项；本轮未改 ledger 默认值、未跑 live/BigQuery 写入、未 promotion、未改默认 profile。
>
> Model: GPT-5.5

> 当前交接补充（2026-06-12，Claude Fable 5，DECISION-20260612-03）
> - PRD_20260612_02 全三阶段收口：Phase C CA-on 重跑 `bt_..._ca01` 三套 QA 通过，六项偏差分解桥 unexplained < 1e-9pp。owner 三项决策落地为 DECISION-20260612-03：baseline 数字切 CA-on（CAGR `15.35%`/Sharpe `0.6682`/Calmar `0.4101`）、"未复权简化"约定 superseded、后续实验一律显式 CA-on（代码默认 none_v1 不变）。
> - v3 gates：Sharpe 距 0.70 门 0.032、Calmar 未过——baseline ≠ accepted；剩余缺口为真实 alpha/结构（OQ-010）。
> - 同日并行会话撞号教训已固化 CLAUDE.md：PRD/DECISION 创建前 fetch 后实查 origin/main 最新编号，撞号时未合并方让号。
>
> Model: Claude Fable 5

> 当前交接补充（2026-06-12，GPT-5.5，Ledger CA Phase C）
> - `codex/ledger-corporate-actions` 已完成 PRD_20260612_02 Phase C research-only CA-on 重跑：Cloud Run runner digest `sha256:769c8e911cc7c660f53cad3cbe3ea5f1a9f6dd502f6e188e7ebfa3dc001ab957`，正式 execution `strategy1-backtest-report-job-dnt4b` 成功。
> - 新 run/backtest：`s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01` / `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01`，参数 `cash_div_and_split_v1` / `flat_10pct`，只写 `ashare_research`；ADS 反向验证和 promotion manifest 均为 0 行。
> - Phase C QA 全过：continuous job `06273525-830b-4603-8503-2dc8f3091ca4`、lot-aware job `1eec4250-5da4-44c1-bab7-ba3183dc14d5`、CA ledger job `37674e4f-06ee-4998-9d1e-75ace14cb965`。报告 `docs/分析-Ledger CA 重跑对照-20260612.md` 已产出；CA-on contract Sharpe `0.6682`、Calmar `0.4101`，仍未 accepted / promotion。
>
> Model: GPT-5.5
## 2026-06-12 GPT-5.5 - Ledger 分红送转 Phase C research-only 重跑

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-ca-ledger`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/ledger-corporate-actions`
Run ID: `s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01`
相关 issue/PR: PR #198；PRD `docs/prd/PRD_20260612_02_策略1Ledger分红送转记账修复.md`

### 已完成工作

- 按不可变 digest 纪律构建并部署 Phase C runner：Cloud Build `6de3b089-5574-4a15-9097-331696fcb6e5`，tag `ledger-ca-phasec-43404e6-20260612-01`，digest `sha256:769c8e911cc7c660f53cad3cbe3ea5f1a9f6dd502f6e188e7ebfa3dc001ab957`；未更新 `latest` tag。`strategy1-backtest-report-job` pin 到该 digest，boot smoke `strategy1-backtest-report-job-97b5v` 成功。
- 执行 CA-on true-five-year continuous research run：formal execution `strategy1-backtest-report-job-dnt4b` 成功，run/backtest 为 `s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01` / `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01`，复用 synthetic prediction run `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01`。
- 完成三条 QA 实跑与 ADS 反向验证：continuous `06273525-830b-4603-8503-2dc8f3091ca4`、lot-aware `1eec4250-5da4-44c1-bab7-ba3183dc14d5`、CA ledger `37674e4f-06ee-4998-9d1e-75ace14cb965`；ADS run/backtest scoped 表 0 行，`research_promotion_manifest` 0 行。
- 新增报告 `docs/分析-Ledger CA 重跑对照-20260612.md`，包含原 true5y baseline / CA-on / PR #194 hfq proxy 三方对照、六项偏差分解、税率 0%/20% 敏感性、v3 gate 重评与 owner 三项待决选项。

### 重要上下文

- CA-on 指标：total return `1.1044714853774122`、compound CAGR `0.15350594766603387`、MaxDD `-0.3742978588042647`、contract Sharpe `0.6682084282261871`、Calmar `0.4101170873817589`、IR `0.6971241900405605`。
- CA 审计：75 行（现金分红 73、送转 2），税后现金入账 `6554.9556` 元，flat 10% 税 `728.3284` 元，送转增股 `90` 股。
- 六项分解闭合：tax `+0.7283pp`、cash_not_reinvested bridge `+2.7920pp`、split fractional `0`、same ex-date held aggregation `0`、event-vs-adj-factor residual `-0.0138pp`、unexplained residual `0`。
- 本轮没有改现役 baseline 数据、没有 promotion、没有改全局默认 profile、没有进入 PRD_10 Phase 2。

### 改动文件

- `tests/strategy1_cloudrun/test_lot_aware_ledger.py`（Claude Low：默认 CA 参数中性测试改名/docstring）
- `docs/分析-Ledger CA 重跑对照-20260612.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest tests/strategy1_cloudrun/test_lot_aware_ledger.py -q`：16 passed。
- Cloud Run boot smoke `strategy1-backtest-report-job-97b5v`：Completed=True。
- Cloud Run formal execution `strategy1-backtest-report-job-dnt4b`：Completed=True，succeededCount=1。
- `qa_continuous_backtest_outputs` / `qa_lot_aware_ledger_outputs` / `qa_corporate_action_ledger_outputs`：dry-run 与实跑均通过。
- ADS 反向验证：model registry / prediction / candidate / target / order / summary / NAV / ledger_state / trade / position 均为 0 行；promotion manifest 0 行。

### 阻塞项

- 无工程阻塞。结果是否切换 baseline 口径、是否 supersede 旧未复权约定、后续实验是否一律 CA-on，均等待 owner 决策。

### 下一步建议

- 提交并推送 `codex/ledger-corporate-actions`，在 PR #198 comment 报告 Phase C 结果、QA、ADS 反查、三方对照和六项分解。
- owner 裁决前，不把 CA-on 结果标 accepted，不 promotion，不改默认 profile。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`
## 2026-06-12 GPT-5.5 - Ledger 分红送转 Phase B 实现

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-ca-ledger`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/ledger-corporate-actions`
Run ID: N/A
相关 issue/PR: PR #198（Phase A + Phase B 实现分支），PR #195（PRD）；PRD `docs/prd/PRD_20260612_02_策略1Ledger分红送转记账修复.md`

### 已完成工作

- 实现 `corporate_actions` / `dividend_tax_mode` 参数链：Experiment/manifest、`backtest_report` CLI、Cloud Run dry-run plan、`build_sql_params`、`LedgerParams`、`ledger_params_hash`、summary metrics_json、catalog required_params、runner QA、lot-aware QA、新 CA QA、两套 resume QA。
- `run_ledger` 新增 ex_date 开盘前 CA 结算：只读 `ashare_dwd.v_dwd_stock_dividend_event_ledger_consumable`；先按 record_date entitlement 送转调股数并写 `CORPORATE_ACTION_SPLIT` 审计行，再按 record_date 股数和 `flat_10pct` 税率写 `CORPORATE_ACTION_CASH_DIVIDEND` 现金入账；调仓日先 CA 后交易。
- 新增 `sql/strategy1/qa/qa_corporate_action_ledger_outputs.sql`，覆盖 summary 参数、送转审计、现金分红审计、事件日 NAV 跳变基本护栏、`none_v1` 零 CA 审计行。
- 默认不变量已用固定时间戳小 fixture 做逐表 JSON 字节比较，并锁定默认 `ledger_params_hash` 黄金值 `2108e411d056418b09c84f99b75021a5329fea58eb474d5906e0e4287f69cc0d`。

### 重要上下文

- Phase B 未执行任何 live backtest / Phase C 重跑；只做 BigQuery dry-run。
- 未写既有 run、未 promotion、未修改全局默认 profile、未触碰 `scripts/strategy1_cloudrun/bq_io.py`。
- 新 CA 审计行写入既有 trade 表，状态为 `CORPORATE_ACTION_SPLIT` / `CORPORATE_ACTION_CASH_DIVIDEND`；它们不进入 `FILLED` 成交状态，因此不计入成交换手/交易成本汇总。
- Resume Python 与两套 SQL QA 均用 summary `metrics_json` 的 COALESCE 默认值兼容旧 `none_v1` parent；CA-on/off 或 tax mode 不一致会 fail-fast。

### 改动文件

- `src/quant_ashare/strategy1/ledger.py`
- `src/quant_ashare/strategy1/reporting.py`
- `scripts/strategy1_cloudrun/config.py`
- `src/quant_ashare/strategy1/tail_risk_overlay_ab.py`
- `sql/strategy1/reporting/build_metrics_and_report_inputs.sql`
- `sql/strategy1/qa/qa_runner_outputs.sql`
- `sql/strategy1/qa/qa_lot_aware_ledger_outputs.sql`
- `sql/strategy1/qa/qa_corporate_action_ledger_outputs.sql`
- `sql/strategy1/qa/qa_ledger_resume_consistency.sql`
- `sql/strategy1/qa/qa_cloudrun_ledger_resume_outputs.sql`
- `configs/strategy1/active_step_catalog.yml`
- related tests and memory/TODO

### 测试 / 验证

- `python3 -m pytest tests`：176 passed。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `python3 -m compileall src scripts`：通过。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `npx --yes @dataform/cli compile dataform > /tmp/quant_ashare_dataform_compile.json`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.sql_runner --step qa_corporate_action_ledger_outputs --output-dataset-role research --dry-run ...`：通过（dry_run status）。
- `git diff --check`：通过。

### 阻塞项

- 无 Phase B 代码阻塞；Phase C 必须等待 Claude review 通过后再执行。

### 下一步建议

- 提交并推送 `codex/ledger-corporate-actions`，在 PR #198 comment/body 报告 11 项传播清单与验证结果。
- Claude review 通过后，再按 PRD Phase C 做 research-only CA-on continuous 重跑与三方对照；不得提前 promotion 或覆盖现有 baseline。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
## 2026-06-12 GPT-5.5 - Ledger 分红送转 Phase A 落地

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-ca-ledger`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/ledger-corporate-actions`
Run ID: N/A
相关 issue/PR: PR #195（PRD review/裁决）；实现 PR 待创建；PRD `docs/prd/PRD_20260612_02_策略1Ledger分红送转记账修复.md`

### 已完成工作

- 实现 Phase A DWD：`sql/dwd/12_dwd_stock_dividend_event.sql` 过滤 `TRIM(div_proc)='实施'`，按 `(sec_code, ex_date)` canonical 聚合 `cash_div_tax`、`stk_bo_rate`、`stk_co_rate`，保留多事件审计数组与 `source_event_count`。
- 实现 Phase A QA：`sql/qa/14_corporate_action_event_checks.sql` 覆盖键唯一、范围、ex_date 开市日、record_date 边界、重复样例 fixture，以及 hfq factor 双向交叉校验；落 `ashare_meta.qa_stock_dividend_event_hfq_mismatch`，创建 `ashare_dwd.v_dwd_stock_dividend_event_ledger_consumable`。
- OQ-015 裁决已应用：不修 `stk_co_rate` 口径；不使用人工 allowlist；容差为 abs/rel 加 `0.01 / prev_close` floor；mismatch 机制化归类，QA ASSERT 语义为 `unclassified mismatch = 0`。
- 同步 Dataform manifest/generated SQLX、ODS dividend schema consumer、单位契约、metadata、重复样例 fixture 和 warehouse 测试。

### 重要上下文

- BigQuery 已执行：`04_ods_field_unit_map` job `bqjob_r4bf6b56437413e50_0000019ebb5cc600_1`；DWD event table job `bqjob_r323943fdb6fe8d66_0000019ebb4706b9_1`；metadata job `bqjob_r5bcddfc324d985c8_0000019ebb4741ce_1`；unit QA job `bqjob_r63dbdce269a7fb79_0000019ebb5d3981_1`；CA QA job `bqjob_r1aadacca42b9e6_0000019ebb47ed1f_1`。
- 2010+ event table：canonical events=`46431`、source rows=`46470`、同股同 ex_date 聚合键=`37`。2021+ QA 窗口：canonical events=`22009`、source rows=`22029`、同股同 ex_date 聚合键=`20`。
- mismatch 明细：event_to_factor `data_anomaly=1106`（`missing_prev_price=1033`、`factor_jump_mismatch=73`）、`special_dividend=1`；factor_to_event `same_day_orphan_corporate_action=405`；`unclassified=0`。ledger-consumable view 行数=`46431`、未归类行=`0`。
- 本轮未改 `src/quant_ashare/strategy1/ledger.py` 或任何 ledger 代码，未写 ADS/research/promotion，不改变 accepted / baseline 状态。

### 改动文件

- `sql/dwd/12_dwd_stock_dividend_event.sql`
- `sql/qa/14_corporate_action_event_checks.sql`
- `configs/ods_schema_contracts/dividend.yml`
- `sql/meta/04_ods_field_unit_map.sql`
- `sql/metadata/01_core_table_column_descriptions.sql`
- `sql/qa/05_unit_contract_checks.sql`
- `dataform/action_manifest.json` 与 generated SQLX
- `tests/fixtures/corporate_actions/dividend_duplicate_events.json`
- `tests/warehouse/test_dwd_stock_dividend_event.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md` / `.agent/memory/AGENT_HANDOFF.md` / `.agent/memory/OPEN_QUESTIONS.md` / `.agent/memory/KNOWN_CONSTRAINTS.md` / `.agent/memory/ARCHITECTURE_MEMORY.md` / `TODO.md`

### 测试 / 验证

- `python3 -m pytest -q tests/warehouse/test_dwd_stock_dividend_event.py tests/dataform/test_generated_sqlx.py`：5 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `npx --yes @dataform/cli compile dataform`：37 actions。
- `bq query --dry_run < sql/dwd/12_dwd_stock_dividend_event.sql`：通过。
- `bq query --dry_run < sql/qa/14_corporate_action_event_checks.sql`：通过。
- BigQuery 实跑 `sql/qa/05_unit_contract_checks.sql` 与 `sql/qa/14_corporate_action_event_checks.sql`：全部 ASSERT successful。

### 阻塞项

- 无 Phase A 阻塞。

### 下一步建议

- Phase B 单独实现 ledger 参数、run loop “先 CA 后交易”、resume/hash/QA 接线与默认逐字节回归；不得把 Phase A 事件表直接视为策略结果或 promotion 依据。
- Phase C 对照报告需要解释 `special_dividend`、`same_day_orphan_corporate_action`、零股取整、现金滞留与事件/adj_factor residual，不得把孤儿因子跳变静默混入 unexplained residual。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `TODO.md`

> 当前交接补充（2026-06-12，Claude Fable 5，PRD_20260612_01 执行收口）
> - PRD 经 PR #193 三轮 Codex review 收敛合并（merge `d9963cf`）；Phase B 实现 PR #197 经 Claude review 零发现合并（merge `2312f30`，166 pytest 通过）。
> - 三个 BigQuery 操作已执行并通过对账（证据贴 PR #197 comment）：Phase A 审计日志预检通过（30 天窗口仅 owner 与项目 compute SA 的 2026-05-24 遗留 InsertJob，2026-05-27 起零活动，无外部消费方）后删除 `ashare` @ `2026-06-12T09:41:45Z`；Phase B 删除 `ashare_qa_windowed_equivalence` @ `09:41:48Z`；两者 `bq show` 复核 Not found，项目剩 9 个数据集。
> - Phase C：DELETE `ads_ml_training_panel_daily` `s1_bqml%` 行 affected=`36,853,582`（与 PRD 预期精确一致），pre/post manifest 13 项全部 IDENTICAL：panel 剩 61 run / `184,596,703` 行、`s1_bqml%`=0；prediction/candidate/target/order/trade/position/NAV/ledger/signal、registry 151/52、summary 90、model 50 全部不变。
> - 回滚窗口截止 `2026-06-19` ~`09:4x`Z（UNDROP / `FOR SYSTEM_TIME AS OF`，均须 `--location=asia-east2`，DML 另需分区过滤）。TODO 对应项已勾选。本条目同时修复 `0786d97` 带入 main 的 AGENT_HANDOFF 未解冲突标记（双方条目均保留、按时间排序）。
>
> Model: Claude Fable 5

> 当前交接补充（2026-06-12，Claude Fable 5，ingestion 镜像 stale 修复）
> - 确诊 `ashare_meta.ingestion_run` / `ingestion_partition_status` 0 行根因：采集 Cloud Run 镜像 `351dfd99...` 构建于 2026-06-04 11:50 UTC，早于 status_writer 接线 commit `60fb242`（15:57 UTC）约 4 小时，此后从未重建；live 采集成功但镜像内无写表代码。次生后果：镜像内打包的 manifest 缺 `2e4d29b` 新增的 000001.SH variant，ODS 000001.SH 自 06-10 停更，`dws_market_state_daily` 06-10/11 `sse_composite_*` 全 NULL（06-10 `risk_off` 判定为退化输入产物）。
> - 已重建镜像（新 digest `5c78e862...`，build `8053b0d5`）推 `:latest`，job spec 未动；boot dry-run `4vq5v` 实证新 digest 生效、plan 27 端点含 000001.SH。已补采 000001.SH 06-10/11（executions `zh88k`/`q4prv`/`fr44m`/`v9k6h`），两张 meta 表落首批 4 行 success，ODS 可读。
> - 待 2026-06-12 20:00 CST scheduled run 后验证：当日 `ingestion_run` 27 端点行、06-10/11 index DWD 与 market-state 被 `daily_current` 20 交易日写窗自动重写、`v_alert_summary` 采集分支恢复。`orchestration/cloud_run_jobs/README.md` 部署记录与 `KNOWN_CONSTRAINTS.md` 镜像重建约束已更新。
>
> Model: Claude Fable 5
## 2026-06-12 Claude Fable 5 - ingestion 镜像 stale 修复（meta 审计静默 + 000001.SH 缺口）

日期: 2026-06-12
Agent ID: Claude Code
Agent 实例 ID: 当前本地会话
模型: Claude Fable 5
运行环境: `/Users/fisher/Desktop/git/quant-ashare`（诊断/云端操作）；PR 分支 `claude/ingestion-image-stale-fix`
Run ID: `manual_backfill_sse_composite_20260610_index_eod` / `manual_backfill_sse_composite_20260611_index_eod`（meta 表内完整 `ingestion_run_id` = CLI 传入值 + `_<endpoint_group>` 后缀）
相关 issue/PR: 本次修复记录 PR（见分支）

### 已完成工作

- 诊断闭环：Cloud Build 历史 + Artifact Registry + execution describe 证明线上 9 次成功采集全部运行 `351dfd99...`（2026-06-04 11:50 UTC 构建），不含 `60fb242`（15:57 UTC）的 `IngestionStatusWriter` 接线；旧版 live 代码无任何 BigQuery 写入逻辑，与「execution 成功 + 两表零 DML」自洽。
- 重建镜像：`gcloud builds submit`（cloudbuild.ingestion.yaml，build `8053b0d5`），新 digest `sha256:5c78e8624584e9ee47471be087ba7e4090d00477a37ec276920f8696810c3f3b`；boot dry-run execution `ashare-ingest-current-scope-4vq5v` 验证新 digest 自动解析、plan 27 分区端点含 `index_daily_000001_SH` / `index_dailybasic_000001_SH`。
- 补采 000001.SH 2026-06-10/11：4 个 live execution（`zh88k`/`q4prv`/`fr44m`/`v9k6h`，每次单 variant，`gcloud run jobs execute --args` 不允许重复 flag）；`ingestion_run` 4 行 success / `ingestion_partition_status` 4 行（两表首批生产行），ODS 外部表可读。
- 部署前风险排除：两表 schema 与 INSERT/MERGE 列匹配（06-08 ALTER_TABLE 仅列描述）；`sa-ashare-ingestion` 有 jobs.create + `ashare_meta` 写权限（其 06-08 ALTER_TABLE 即实证）；requirements 含 `google-cloud-bigquery`；`60fb242..HEAD` ingestion 变更面：manifest 新增 000001.SH variants，`run_ingestion_job.py` / `common/logging.py` / `common/manifest.py` / `common/parquet_schema.py` 仅 docstring/描述文案改动，另新增独立辅助脚本 `scripts/ingestion/generate_index_external_table_uris.py`（随 `COPY scripts/ingestion` 打包进镜像，但不在 job ENTRYPOINT 运行路径）。

### 重要上下文

- job spec / scheduler / workflow / IAM 全部未动；job 引用 `:latest`，execution 创建时解析 digest，2026-06-12 20:00 CST scheduled run 自动用新镜像。
- `dws_market_state_daily` 06-10/11 的 `sse_composite_*` 为 NULL、06-10 `market_regime='risk_off'` 是退化输入下的判定；当晚 `daily_current` 窗口刷新（`02`/`03` 写窗回看 20 个交易日）会自动重写，无需手工 backfill。正式研究窗口（至 06-09）未消费退化行。
- `v_alert_summary` 当前 2 行 pipeline/task_failure 是 06-11 PRD_06 backfill 期间的历史 QA 失败记录（2019Q1 旗标断言），与本次无关。

### 改动文件

- `orchestration/cloud_run_jobs/README.md`（部署状态：新 digest + 镜像重建纪律）
- `.agent/memory/IMPLEMENTATION_STATUS.md` / `.agent/memory/AGENT_HANDOFF.md` / `.agent/memory/KNOWN_CONSTRAINTS.md` / `TODO.md`

### 测试 / 验证

- boot dry-run execution 成功 + 日志含 000001.SH plan 行；4 个补采 execution 成功；`ingestion_run` / `ingestion_partition_status` / ODS 06-10/11 查询验证；`v_alert_summary` / `v_ingestion_failures` 可查询。

### 阻塞项

- 2026-06-12 20:00 CST scheduled run 的全链路验证尚未发生（验证清单见 TODO）。

### 下一步建议

- 20:00 CST 后按 TODO 验证清单复核；若 `ingestion_run` 当日仍无行，查 execution 日志与 BigQuery 写入错误。
- 考虑给 `scripts/ingestion/**` / `configs/ingestion/**` 变更加 CI 或 PR checklist 强制「重建镜像」步骤（已写入 KNOWN_CONSTRAINTS，流程硬约束待 owner 决定形式）。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`


> 当前交接补充（2026-06-12，GPT-5.5，PRD_20260612_01 Phase B implementation）
> - 分支 `codex/bq-dataset-cleanup-impl` 已完成 PRD_20260612_01 Phase B 代码层：退役两个 windowed equivalence parity 脚本并移除空 `scripts/qa/`，清理契约测试、`sql/README.md` 示例和 Strategy1 Cloud Run runbook active 前置条件。
> - `active_step_catalog.yml` 已加入两条退役脚本 ban-list，并补齐相关 `.agent/memory` 历史白名单；`KNOWN_CONSTRAINTS.md` 已把 OQ-005 window parity 与 true-five-year overlap parity 硬门改写为 PRD 定稿口径，BQML audit 条款补充面板裁剪后的复算入口。
> - 验证已通过：`PYTHONPATH=src python3 -m pytest -q tests`（166 passed）、`python3 -m pytest -q tests/strategy1/test_retired_lint.py`（5 passed）、active scope grep 退役脚本 `.py` 路径零引用、`git diff --check`。
> - 本轮未执行 BigQuery 操作；Phase A/Phase B scratch dataset/Phase C panel DELETE 仍是实现 PR 合并后的手工步骤。
>
> Model: GPT-5.5

## 交接条目

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-bq-cleanup-impl`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/bq-dataset-cleanup-impl`
Run ID: N/A
相关 issue/PR: PR #193（PRD 已合并），实现 PR 待创建；PRD `docs/prd/PRD_20260612_01_BigQuery数据集清理退役.md`

### 已完成工作

- 实现 PRD_20260612_01 Phase B 第 1-7 项：删除退役 QA 脚本和空目录，移除对应契约测试，清理 `sql/README.md` windowed equivalence 示例，改写 Strategy1 Cloud Run runbook true-five-year refit 前置条件。
- `configs/strategy1/active_step_catalog.yml` 增加退役脚本 ban-list，并补齐相关 `.agent/memory` 历史白名单。
- `.agent/memory/KNOWN_CONSTRAINTS.md` 改写 OQ-005 window parity、true-five-year overlap parity 和 BQML historical panel 裁剪后的复算约束；`.agent/memory/ARCHITECTURE_MEMORY.md` 保留历史叙述并补退役注记。

### 重要上下文

- 本轮只做代码/文档/记忆改动，未执行任何 BigQuery 操作。
- Phase A `ashare` 数据集硬删除、Phase B scratch dataset 删除和 Phase C `ads_ml_training_panel_daily` `s1_bqml%` DELETE 仍需在实现 PR 合并后按 PRD 手工执行并留对账证据。
- 若未来需要恢复 full/window parity 工具，应从本实现 PR 的 parent commit 通过 git history 恢复脚本后另行评估。

### 改动文件

- `scripts/qa/run_windowed_refresh_equivalence.py`（删除）
- `scripts/qa/run_index_market_windowed_equivalence.py`（删除）
- `tests/strategy1/test_true5y_prd06_contracts.py`
- `sql/README.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `configs/strategy1/active_step_catalog.yml`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`

> 当前交接补充（2026-06-12，GPT-5.5，PR #190 true5y baseline resolver follow-up）
> - 按 PR #192 review 发现 1，PR #190 的 `scripts/strategy1/analyze_topdown_lot_phase0.py` 默认 id resolver 已支持 true5y prediction/backtest id，并从“effective-window official ids”改为“当前研究 baseline（从记忆解析）”语义。
> - resolver 优先解析含 `DECISION-20260612-02` / “采纳/切换/研究 baseline”语义的记忆段落；同一记忆文本同时出现旧 effective-window ids 与新 true5y ids 时，默认返回 true5y。找不到 baseline 语义时回退全文首个匹配。
> - 新增 fixture 单测，不依赖真实记忆文件；本轮未重跑 Phase 0 数据，未改报告数字，未触碰 `scripts/strategy1_cloudrun/bq_io.py`、ledger v1 / Phase 1、默认 tail_risk profile 或 promotion。
>
> Model: GPT-5.5
## 2026-06-12 GPT-5.5 - PR #190 true5y baseline resolver follow-up

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: 当前本地会话
模型: GPT-5.5
运行环境: `/Users/fisher/Desktop/git/quant-ashare`，分支 `codex/strategy1-topdown-phase0`
Run ID: N/A（未重跑 Phase 0）
相关 issue/PR: PR #190，关联 PR #192 review comment `4689225423`

### 已完成工作

- 修复 `resolve_default_run_ids()`：支持 `*_true5y_*` id 形状，并优先解析当前研究 baseline 语义段落。
- 增加 `resolve_run_ids_from_memory_text()` / baseline 段落解析 helper，便于单测用 fixture 文本覆盖，不依赖真实项目记忆文件。
- 更新 CLI help：省略 `--prediction-run-id` / `--backtest-id` 时从项目记忆解析当前研究 baseline。

### 重要上下文

- 这是 PR #192 的 baseline 切换纪律对 PR #190 的前置兼容修复；本轮没有把 Phase 0 数字切到 true5y 重跑。
- `scripts/strategy1_cloudrun/bq_io.py` 是 owner 既有未提交改动，本轮未修改、未暂存。

### 改动文件

- `scripts/strategy1/analyze_topdown_lot_phase0.py`
- `tests/strategy1/test_topdown_lot_phase0.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests`：166 passed，5 warnings。
- `python3 -m pytest -q tests/strategy1/test_retired_lint.py`：5 passed。
- active scope grep 退役脚本 `.py` 路径：零引用；bare path 只保留在 catalog ban-list 和历史承载面。
- `git diff --check`：通过。

### 阻塞项

- 无代码阻塞。

### 下一步建议

- 提交并推送 `codex/bq-dataset-cleanup-impl`，创建 base `main` 的实现 PR。
- 实现 PR 合并后，再按 PRD 手工执行 BigQuery Phase A/B/C 清理；执行时必须遵守 `--location=asia-east2`、分区过滤和删除前/后 manifest 对账要求。

- `python3 -m pytest -q tests/strategy1/test_topdown_lot_phase0.py`
- `python3 -m py_compile scripts/strategy1/analyze_topdown_lot_phase0.py tests/strategy1/test_topdown_lot_phase0.py`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- PR #192 合入后，后续如 owner 决策重跑 Phase 0，再让脚本默认解析 true5y baseline 并刷新报告/产物。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `TODO.md`

> 当前交接补充（2026-06-12，Claude Fable 5，BigQuery 数据集清理 PRD）
> - 完成 `data-aquarium` 全数据集盘点：核心分层（dim/dwd/dws/ads/research）与 `sql/` 契约双向零差异；杂物为遗留数据集 `ashare`（250.4 GiB、零引用、2026-05-25 后零写入）、`ashare_meta` 5 张 `_repair_val_*`、`ashare_qa_windowed_equivalence` 18 张 shadow 残留、ads 训练面板 12 个 `s1_bqml%` 旧 run（约 115 GB）。
> - 第 1 类清理已执行（owner 批准）：上述 5 + 18 共 23 张表已删，`bq ls` 复核清空。18 张 native shadow 表 7 天 time travel 内可恢复；5 张 `_repair_val_*` 是外部表（time travel 不覆盖），删除仅移除 BQ definition，GCS 无涉，需要时由 repair 脚本重建。
> - 新增 `docs/prd/PRD_20260612_01_BigQuery数据集清理退役.md`（分支 `claude/prd-bq-dataset-cleanup`）：Phase A `ashare` 硬删除（审计日志预检硬门）/ Phase B windowed equivalence QA 退役（两脚本 + 引用 + KNOWN_CONSTRAINTS 两处硬门改写 + scratch 数据集删除）/ Phase C 面板 `s1_bqml%` 行裁剪。owner 决策记入 DECISION-20260612-01；`tushare_api_catalog`/`params`、`ashare_backup`、50 个 BQML model、prediction、回测事实、ODS scope 外外部表均保留。
> - 注意：KNOWN_CONSTRAINTS 的「双实现并存必须跑 equivalence QA」与「true5y 重跑必须先过 overlap parity」两条届时改写（随实现 PR），不是静默失效；两脚本恢复入口为实现 PR 的 parent commit。
> - 盘点顺带发现 `ingestion_run` / `ingestion_partition_status` 0 行与 live 采集成功矛盾（疑似采集镜像 stale、采集级告警静默），已挂独立排查任务，本轮未修。

> 当前交接补充（2026-06-12，Claude Fable 5，DECISION-20260612-02）
> - Owner 已采纳 **true-five-year continuous 为策略 1 研究 baseline**（run `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01` / backtest `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01`），effective-window 降级为历史参照；OQ-011 关闭归档，`OPEN_QUESTIONS.md` 仅剩 OQ-010。
> - 采纳依据为方法论性（effective-window 的覆盖约束前提已被 PRD_06 拆除且 parity/覆盖/refit/continuous QA 全过），非结果驱动；baseline 指标锚点 CAGR `13.85%` / MaxDD `-37.19%` / contract Sharpe `0.6076` / Calmar `0.3725`，仍未过 v3 双门，**baseline ≠ accepted、不得 promotion**。
> - 切换纪律：新实验 prediction 流/对照从记忆解析 true5y ids 且报告注明基线版本；PRD_10 §6 基线兼容条款生效；进行中的复权漏损量化需补 true5y backtest 覆盖；旧 baseline 的机制级结论可迁移、数字级结论引用时注明口径。
> - 改动文件：DECISION_LOG（新条目）、OPEN_QUESTIONS / archive、MEMORY_INDEX、IMPLEMENTATION_STATUS、KNOWN_CONSTRAINTS（true5y 条目追加切换纪律句）、TODO（OQ-010 路线项改写）。>
> Model: Claude Fable 5


> 当前交接补充（2026-06-12，GPT-5.5，official ledger 复权漏损量化）
> - 已在独立 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-adj-leak`、分支 `codex/official-ledger-adj-leak` 完成 official ledger "未复权价 + 恒定股数"复权漏损测量；新增只读脚本 `scripts/strategy1/analyze_official_adj_leak.py`、报告 `docs/分析-官方Ledger复权漏损量化-20260612.md`、小结果 CSV `docs/analysis_official_ledger_adj_leak_20260612_metrics.csv`。
> - 主结果 true-five-year continuous 修正前/后：CAGR `13.85% -> 15.72%`、MaxDD `-37.19% -> -36.76%`、contract Sharpe `0.6076 -> 0.6894`、Calmar `0.3725 -> 0.4275`；CAGR `+1.86pp` 且 Calmar `+0.0550` 触发预登记判据，报告建议 owner 立 PRD 修 ledger 并排在 Phase 2 之前。
> - effective-window 参照修正前/后：CAGR `12.04% -> 13.56%`、MaxDD `-45.48% -> -44.99%`、contract Sharpe `0.5285 -> 0.5961`、Calmar `0.2646 -> 0.3014`。无交易日对账残差通过硬门（两条 backtest `max_abs` 均约 `1e-16`），逐日/事件/年度大 CSV 已上传到 `gs://ashare-artifacts/reports/strategy1/official_adj_leak/analysis_date=20260612/`。
> - 本轮仅测量，不修改 ledger / 生产 SQL / 既有 run 数据，不 promotion，不替 owner 重开 `DECISION_LOG` 中已接受的未复权/除权简化约定。
>
> Model: GPT-5.5


> 当前交接补充（2026-06-12，Claude Fable 5，PRD_20260612_01）
> - 新增 `docs/prd/PRD_20260612_02_策略1Ledger分红送转记账修复.md`：PR #194 量化触发预登记判据（true5y CAGR +1.86pp、Calmar +0.055、修正后 contract Sharpe 0.6894 距 0.70 门仅 0.011）后，按判据立项重开"未复权口径、持有期除权简化"约定。
> - 核心设计：公司行为记账做成**参数**（`corporate_actions`，默认 `none_v1`；`cash_div_and_split_v1` 送转调股数+税后现金分红入账）而非新版本号——与构造维度正交，v1/v2 同获能力；hash 仅非默认值入 payload（PR #189 教训）；红利税主口径 **`flat_10pct`**（tax-lot 精确化经 review 裁定为非目标，Phase C 附 0%/20% 敏感性界）。
> - 三阶段：Phase A DWD 分红送转事件表（同股同 ex_date 多事件 canonical 聚合）+ hfq 因子交叉校验硬门 → Phase B ledger 实现 + 参数传播清单 + 默认回归（trade/position/NAV/state/hash 逐字节，summary additive）→ Phase C true5y CA 重跑与 #194 hfq 估计三方对照（六项可审计偏差分解，验收只卡 unexplained_residual）。排在 PRD_10 Phase 2 之前。单门通过不触发 accepted。
>
> Model: Claude Fable 5

> 当前交接补充（2026-06-12，GPT-5 Codex，PR #186 CSV cleanup）
> - 已按 owner 要求直接从 `main` 删除 PR #186 带入的四份分析 CSV：`docs/analysis_strategy1_signal_ic_decomposition_20260611_daily.csv`、`docs/analysis_strategy1_signal_ic_decomposition_20260611_summary.csv`、`docs/analysis_strategy1_transfer_ladder_20260611_results.csv`、`docs/analysis_strategy1_transfer_ladder_20260611_transfer_coefficients.csv`。
> - 保留 PR #186 的只读分析脚本、测试和 Markdown 报告；CSV 视为可再生成的本地/临时分析产物，不再跟随 git。`docs/analysis_strategy1_exposure_overlay_upper_bound_20260611_results.csv` 属于其他 PR，本轮未动。
> - 本轮未运行 BigQuery、未启动 Cloud Run、未改策略结果、未改变 accepted / promotion 状态。
>
> Model: GPT-5 Codex

> 当前交接补充（2026-06-12，GPT-5 Codex，GCS checkpoint archive）
> - 已将 `configs/ingestion/ods_current_scope_v0.yml` 当前生产 14 个 ODS endpoint 及其 current partition variants 的 2010+ checkpoint 做可逆归档；scope 为 `gs://data-aquarium/a-share/tushare/_checkpoints/endpoint=*/logical_date=*.json` 且 `logical_date >= 20100101`。
> - 归档 run：`checkpoint_archive_current14_20260612T035604Z`；根路径 `gs://data-aquarium/a-share/tushare/checkpoint_archive/run_id=checkpoint_archive_current14_20260612T035604Z/`；产物为 26 个 gzip JSONL 归档对象 + `manifest.json`，共 65,891 条 checkpoint 记录，源 checkpoint 47,955,858 bytes，gzip 后 7,951,990 bytes。
> - 每条归档记录保存原始 `source_uri` / bucket / object name / endpoint / logical_date / generation / size / crc32c / md5 / sha256 / `content_base64`，可按 manifest 反向恢复；校验已完成：逐 gzip 重算行数、字节数、`jsonl_sha256`，逐条校验 content sha256，并抽样 5 个原对象按 generation 比对通过。
> - 本轮没有删除原 `_checkpoints/` 对象；后续如要真正减少对象数，仍需 owner 另行明确批准 lifecycle 或删除策略。manifest 记录 4 个 current-scope endpoint 为空：`index_daily`、`index_daily_000001_SH`、`index_dailybasic`、`index_dailybasic_000001_SH`。
>
> Model: GPT-5 Codex

- `TODO.md`

> 当前交接补充（2026-06-12，GPT-5.5，PR #190 Phase 0 review follow-up）
> - PR #190 的 Phase 0 paper 报告已按多代理 review 修订：主判读改 official matched 分腿费率（买 `6bps`、卖 `11bps`），保留 `0bps` / `20bps` 敏感性；新增逐票持仓审计、P1 饱和机制、四通道归因、2022-05 episode、最差 3 个 10 日窗口持仓明细。
> - 主结果（`walk_depth=50`, matched official cost）：T0 CAGR `10.91%`、MaxDD `-63.66%`、Calmar `0.171`；T1 CAGR `-2.79%`、MaxDD `-66.32%`、Calmar `-0.042`；T1-T0 CAGR gap `-13.70pp`，crunch excess 改善 `+8.96pp`。20bps 旧口径 gap `-14.81pp` 已作为敏感性保留。
> - P1 失败归因改为市值规则饱和：matched 归因中现金差约 `-8.93pp/年`、持仓构成差约 `-4.53pp/年`；2022-05-06 top-50 P1 标记率 `98%`、市值规则标记率 `96%`，后续 10 个交易日 T1 平均现金 `94.48%`、T1-T0 return gap `-9.07pp`。
> - 大 CSV 已上传并由报告引用：`gs://ashare-artifacts/reports/strategy1/topdown_phase0/analysis_date=20260612/analysis_strategy1_topdown_lot_phase0_20260612_daily.csv` 与 `..._rebalance_audit.csv`；小 `metrics.csv` 需随 PR 入库。仍未改 ledger v1 / Phase 1、未改默认 tail_risk profile、未 promotion。
>
> Model: GPT-5.5
## 2026-06-12 GPT-5.5 - PR #190 Phase 0 review follow-up

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: 当前本地会话
模型: GPT-5.5
运行环境: `/Users/fisher/Desktop/git/quant-ashare`，分支 `codex/strategy1-topdown-phase0`
Run ID: `s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02`
相关 issue/PR: PR #190

### 已完成工作

- 修订 `scripts/strategy1/analyze_topdown_lot_phase0.py`：加入 matched official split cost profile、逐票持仓 JSON 审计、NAV 分母集中度、P1 饱和归因表、日期集合断言、卖出价格缺失审计、N-1 收益期数、平均 NAV 换手归一。
- 重跑 Phase 0，刷新 `docs/分析-策略1自上而下整手组合Phase0-20260612.md` 与三份 CSV；报告主判读使用 matched official cost，`0bps` / `20bps` 保留为敏感性。
- 上传大 CSV 到 GCS：daily `32114025` bytes，rebalance audit `804585` bytes；报告引用 `gs://ashare-artifacts/reports/strategy1/topdown_phase0/analysis_date=20260612/` 下对应对象。

### 重要上下文

- BigQuery 全程只读；本轮未训练、未写 BQ、未启动 Cloud Run、未 promotion。
- `scripts/strategy1_cloudrun/bq_io.py` 是 owner 既有未提交改动，本轮未修改、未暂存。
- Claude review 中 `T0 @8.5bps CAGR≈13.64%` / trigger-3 T0 不触发的数值未按 split `6/11bps` 或 uniform `8.5bps` 路径级重跑复现；当前脚本主结果仍触发 trigger-3 合取条件。

### 改动文件

- `scripts/strategy1/analyze_topdown_lot_phase0.py`
- `tests/strategy1/test_topdown_lot_phase0.py`
- `docs/分析-策略1自上而下整手组合Phase0-20260612.md`
- `docs/analysis_strategy1_topdown_lot_phase0_20260612_metrics.csv`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 scripts/strategy1/analyze_topdown_lot_phase0.py`
- `python3 -m pytest -q tests/strategy1/test_topdown_lot_phase0.py`
- `python3 -m py_compile scripts/strategy1/analyze_topdown_lot_phase0.py tests/strategy1/test_topdown_lot_phase0.py`
- GCS `gcloud storage cp` + `gcloud storage ls -l`

### 阻塞项

- 无技术阻塞；Phase 1 是否继续仍需 owner 决策。

### 下一步建议

- Owner 决定 P1 市值两条规则是否剔除（保留崩盘形态规则）或增加饱和回退。
- 若继续 Phase 1，再实现 `ledger_exec_v2_lot100_topdown`，仍不动 v1、不改默认 profile。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`


> 当前交接补充（2026-06-11，GPT-5 Codex，PR #189 top-down review follow-up）
> - 按 Claude comment 全量处理 PR #189 发现并补齐：
>   1) 修复 v1 与 topdown 的参数哈希口径（`walk_depth / min_position_weight / position_floor_count` 仅在 topdown 加入；v1 不变）；
>   2) `ledger_exec_v2_lot100_topdown` 中仅 `can_sell` 时才回收卖出现金，避免未卖出却回款；
>   3) topdown 强制 require individual 风控 profile（`validate_ledger_params` 拦截）；
>   4) `qa_topdown_construction_outputs.sql` 从 `QA-TOPDOWN-6` 起补充 topdown 专用约束与 hard gate（topdown profile 必须个券风险、tail risk 标记存在、标记日不得 fill BUY、候选输入覆盖 full-rank、NAV 前一天对齐检查）；二轮复核指出第一版 NAV 子查询仍取 `bt.trade_date` 当天，本轮已改为显式 `cal -> prev -> nav.trade_date = prev.cal_date` join；
>   5) topdown `LedgerParams.cash_redistribution` 已收敛到 `topdown_whole_order_skip_v2`，与 summary 自述一致；v1 仍保持 `none_v1`；
>   6) 增强测试覆盖 `BUY_SKIPPED_TAIL_RISK`、topdown hash 回归、v1 hash 不变、topdown cash redistribution 运行参数和错误口径 fail-fast。
> - 验证：`tests/strategy1_cloudrun/test_lot_aware_ledger.py` + `tests/strategy1_cloudrun/test_dataset_role_routing.py` + `tests/strategy1/test_sql_render.py` focused pytest 58 passed、`git diff --check` 通过；此前全量 `tests/strategy1 + tests/strategy1_cloudrun` 173 passed、retired linter、compileall、Dataform SQLX check 通过；BigQuery 只读 dry-run 已由 Claude 在授权环境代跑通过。
> - 本次修改不改默认 v1（`ledger_exec_v1_lot100`）语义，不改全局 tail-risk profile，不 promotion，未做 live BigQuery/Cloud Run 写入。

> 当前交接补充（2026-06-11，GPT-5 Codex，PRD_10 code prep）
> - 分支 `codex/topdown-lot-construction` 基于 `origin/main@a21cf97` 实现 PRD_20260611_10 Phase 1 代码准备：新增 `ledger_exec_v2_lot100_topdown` / `cloudrun_lot100_topdown_resume_v1`，由 `backtest_report --use-topdown-ledger` 显式 opt-in，默认 `ledger_exec_v1_lot100` 不变。
> - v2 ledger 直接读取 `stock_candidate_daily.rank_raw <= walk_depth` 的 full ranked candidates；`portfolio_target_daily` / `order_plan_daily` 仍是兼容产物，不作为 v2 构造输入。构造按 rank 自上而下行走，新开仓最小权重默认 5%，整手买入，禁止 `FILLED_SCALED_CASH`，现金不足时按低排名整笔放弃买入。
> - P1 语义已按 profile 绑定：只有启用 individual guard 时 `tail_risk:*` 新增候选才跳过并由后续排名顶上；`diagnostic_only` 下 marker 不触发跳买。P2 risk-off 次日跳过所有新增买入。持仓保留阈值统一 `walk_depth`；超深度持仓必须卖出，仍持有必须追溯到 `SELL_SKIPPED_UNTRADABLE` / `PENDING_SELL_CARRY`。
> - 新增 `qa_topdown_construction_outputs` 并登记 catalog；`09` summary metrics_json、Markdown report 和 Cloud Run runbook 已同步记录/展示 topdown 参数、实际持仓数和最大单票权重。验证：Strategy1/Cloud Run 全量 pytest、retired linter、compileall、Dataform SQLX check、`git diff --check` 通过。本轮未部署镜像、未执行 BigQuery/Cloud Run live run；Phase 0 paper、Phase 2 research-only continuous 和 owner 决策仍待办。
>
> Model: GPT-5 Codex

> 当前交接补充（2026-06-11，Claude Fable 5，PRD_10）
> - 新增 `docs/prd/PRD_20260611_10_策略1自上而下整手组合构造.md`：针对 PR #186 确认的结构性现金拖累（10 万 + 整手 + 等权 5% + 无再分配 → 25% 买单跳过、现金均值 29.4%），owner 决定重新设计构造规则而非修复等权。
> - 核心规则：自上而下贪心买入，新开仓最小权重 5%（`position_floor_count=20` 仅作门槛基数，`target_holdings` 退役为观测指标 `realized_holdings_count`）；**无单票上限**（owner 决策 2026-06-11）；`walk_depth=50` 统一买入深度与卖出保留阈值；P1 六条规则以"跳过→下一名顶上"替换语义绑定进构造（实现红线：禁止复用 ledger 层跳过留现金语义，防止复活 #179 A1 的现金拖累）；可负担性与 P1 标记均只约束新增买入、不强制卖出。
> - 三阶段：Phase 0 paper 双臂原型（带/不带 P1，预登记判读）→ Phase 1 `ledger_exec_v2_lot100_topdown` + 新 QA（不动 v1）→ Phase 2 research-only continuous 重跑 + 三方对比。含基线兼容条款（true-five-year 若被采纳则随之切换）。仅 docs+记忆改动。
>
> Model: Claude Fable 5

> 当前交接补充（2026-06-11，GPT-5 Codex，PRD_06/07/08 live 收口）
> - PRD_07 Phase 2 candidate-only live smoke 已在正式 runner 镜像 `sha256:45b4d257878afa91192410a8e300ad9c358c6a2b3412a6be6d1e5e1732843eb7` 上通过：run-version `v20260611_prd07smoke01`，2021/2022 matrix 预置后由 scheduler 提交 fanout executions `strategy1-train-candidate-fanout-job-g65hx` / `btvgv`，各 3/3 tasks succeeded；dry-run/live state plan hash 均为 `7ef90a481f0e64ad`，两个 live unit 均 `present_after_describe_success`，12 个候选 artifact 文件均可读；同 run_id recovery 重跑提交数 0，artifact-skip 新 run 提交数 0，missing-matrix preflight 本地失败且提交数 0，真实 GCS 临时 lock smoke 验证 lease 竞争语义。
> - PRD_06 Phase A 已完成生产历史修复：2010-2014、2015Q1、`2019-01-02..2019-04-02` 窗口重刷；发现并修复 57 个早期 `daily_basic` 市值字段全空开市日，暂停 `ashare-ods-ingestion-daily` 后补采并在 20:00 前恢复，随后日常 workflow execution `5e790d75-1351-4fb3-aea7-6a396675e3bc` 成功。
> - 本轮代码修复：窗口股票 DWD prev_close warm-up 不再被 730 自然日截断；market-state backfill 读取 `p_write_floor_date` 以覆盖稀疏股票 20-row rolling；`13_true5y_historical_coverage_checks.sql` 改为用 `history_obs_60d >= 61` 判定 2019 旗标修复，并新增 ODS `daily_basic` 市值字段 open-day 覆盖护栏。
> - PRD_06 宽窗口 overlap parity 已补证：stock/DWD/DWS 9 表在 `2019-04-03..2026-06-09`（label/feature/sample 从 `2019-03-06` 比较）以 `float_tolerance=1e-8` 全部 0 mismatch；index DWD 与 market-state DWS 在 `2019-04-03..2026-06-09` 以 `float_tolerance=1e-4` 全部 0 mismatch。严格 `1e-8/1e-5` 对 market-state 只剩浮点聚合 roundoff，非 regime/action 业务差异。
> - PRD_06 Phase B/C 已完成：2021-2024 true-five-year refit 使用 `__true5y01` 非默认 suffix，四年 train windows 均为名义五年实际开市日，refit panel coverage 缺口为 0，四个 refit Cloud Run executions `zj4t4` / `wqwpx` / `tdv5j` / `998sc` 成功，四年 `qa_refit_register_predict_outputs` 通过。
> - 新 true-five-year synthetic continuous `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01` / `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01` 已完成：merge prediction rows `2643406`，backtest execution `strategy1-backtest-report-job-4zbd4` 成功，`qa_continuous_backtest_outputs` job `20cf1a26-93ce-48c9-9c7a-d10587d37ae3` 与 `qa_lot_aware_ledger_outputs` job `afa4be4e-bd47-4eb4-add1-a80f39cef082` 通过；ADS run-scoped 表与 `research_promotion_manifest` 同 source 为 0 行。
> - 结果对比：effective-window continuous CAGR `12.04%`、MaxDD `-45.48%`、legacy Sharpe `0.613`、v3 contract Sharpe `0.5285`、contract Calmar `0.265`；true-five-year continuous CAGR `13.85%`、MaxDD `-37.19%`、legacy Sharpe `0.683`、v3 contract Sharpe `0.6076`、contract Calmar `0.372`。true-five-year 明显改善但仍未过 v3 hard gates（contract Sharpe `<0.70`，contract Calmar `<1.0`），不得自动标 accepted 或 promotion；是否采纳为新研究 baseline 仍需 owner 决策。

Model: GPT-5 Codex

> 当前交接补充（2026-06-11，GPT-5 Codex，PRD_09）
> - 分支 `codex/signal-ic-transfer-analysis` 已完成 PRD_20260611_09 信号 IC 分解与组合转换效率分析：新增只读脚本 `scripts/strategy1/analyze_signal_ic_decomposition.py`、兼容入口 `scripts/strategy1/analyze_transfer_ladder.py`、报告 `docs/分析-策略1信号IC分解与转换效率-20260611.md` 与四份结果 CSV。
> - 全程 BigQuery 只读：读取 official synthetic prediction run `s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02`、official backtest `bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`、DWS labels/features/market state、DWD price/index 和 research target/position；未写 `ashare_research` / ADS / promotion。
> - 关键结论：5d raw rank IC=`0.040908`、NW t=`5.586351`，2021-2026 年度 IC 全正；市值中性后 IC 保留 `90.52%`，行业 snapshot 参考保留 `88.20%`。L0 score-weighted long/short no-cost Sharpe=`2.800047`（20bps 后 `1.807056`）；新增 L0.5 top-decile long-only IR=`0.509749`，L1/L2/L3 long-only IR 约 `0.491`/`0.544`/`0.486`。
> - Review follow-up 修正了旧 TC 伪迹：TC 改为 full prediction universe 域，平均 `TC_target=0.712888`、`TC_realized=0.628765`；target 与 score-weighted Top20 名字重合率均值/最小值均 `100%`，L3-L2 IR 差仅 `-0.058363`，等权替代分数权重不是优先瓶颈。真实执行缺口来自持仓覆盖率/现金路径：realized/target 覆盖率均值 `81.51%`、最小 `5%`，TC 行内 `official_cash_weight` 均值 `29.07%`。
> - 现金交叉核验已做实：NAV 表 `cash_cny/net_value_cny` 与 `1-sum(position.weight)` 最大差 `2.22e-16`、差异天数 `0`，NAV 现金权重均值 `29.36%`，现金 >50% 交易日 `265` 天。全周期 `BUY_SKIPPED_BELOW_LOT=690`，最低覆盖执行日 `2021-12-27` 的 20 个 BUY 全部 `BUY_SKIPPED_BELOW_LOT`，指向小资金 + 100 股整手约束造成的结构性现金拖累，而不是测量伪迹。
> - L3 paper 与 official daily_return corr=`0.913059`，但 paper CAGR 比 official 高 `2.90pp`、MaxDD 比 official 差 `12.30pp`；报告已声明 paper ladder 只作转换效率上界/分解，不等同正式回测。OQ-010 路线决策仍留 owner，本轮不 accepted、不 promotion。
>
> Model: GPT-5 Codex

> 当前交接补充（2026-06-11，Claude Fable 5，PRD_09）
> - 新增 `docs/prd/PRD_20260611_09_策略1信号IC分解与组合转换效率.md`：纯只读研究分析 PRD，把度量衡从组合 NAV 切换到信号层。动机：组合超额 t≈1.26（统计上不显著）而六个 refit 模型 valid rank IC 六年全正（`0.039~0.098`、日度 ICIR `0.30~0.81`），指向"信号真实、转换浪费"。
> - Part A IC 分解五维：按年（真 OOS）/ 市值+行业中性化 / market regime / 分数分位（多头侧 vs 空头侧贡献）/ horizon 1/5/10/20d 衰减；前向收益直接读 `dws_stock_label_daily` 的同口径标签并按 `label_valid_{h}d` 过滤；所有 t 值须 NW / block bootstrap 修正。
> - Part B 转换阶梯：L0 分数加权多空 → L1 long-only 分数加权 Top50 → L2 Top20 → L3 等权 Top20+7.5% cap（现行口径），逐级 IR 落差定价每条约束；L3 与 official 实际结果做恒等校验；TC 分拆为 `TC_target`（目标权重 vs 分数隐含权重）和 `TC_realized`（实际持仓权重 vs 分数隐含权重）。
> - §6 预登记解读规则先写后跑（中性化阈值 60%/40%、L0 IR<1.0、阶梯落差 0.1 IR 等），支撑 owner 三个决策：组合构造改进 / 对冲结构评估 / 回炉模型。仅 docs+记忆改动，无代码、无 BQ 操作。
>
> Model: Claude Fable 5

> 当前交接补充（2026-06-11，GPT-5 Codex，PRD_08）
> - PRD_08 Cloud Run Python ledger resume 已完成 research-only 真实数据验收：parent `bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`，cut `2024-12-31`，next open `2025-01-02`，anchor `2021-01-04`；resume child execution `strategy1-backtest-report-job-82454` 成功。
> - 两套 resume QA 均通过：`qa_cloudrun_ledger_resume_outputs` job `eb99f350-feb4-4fdc-977d-d2e6b7c74201`，`qa_ledger_resume_consistency` job `8b2b1e17-42ad-44d2-8318-9f283c26eee2`。验收产物仅写 research，ADS 同 run/backtest 为 0 行。
> - 代码/契约更新：`qa_ledger_resume_consistency` 从旧 BQML / `ledger_exec_v1` 默认升级到 Cloud Run lot100 / research-first 口径；两套 QA 都要求 state date、resume policy、ledger version、原始 rebalance anchor 和 next-open 边界；runbook 明确等价参照是 full fresh continuous parent 的同窗口切片，不是 cut 后 segment fresh-start。
> - 后续：PRD_07 worker 已在独立 worktree 提交分支 `codex/prd07-annual-live-smoke`；PRD_06 只读审计建议已回报，尚未整合到本 PRD_08 分支。

Model: GPT-5 Codex

> 当前交接补充（2026-06-11，GPT-5 Codex，PRD_06）
> - PR #182（PRD_07 annual scheduler live smoke code-prep）已合并到 `main@dab646d`；PRD06 分支已在该主线基础上继续 rebase，避免覆盖 scheduler live-smoke 记忆和 runbook 状态。
> - PRD06 true-five-year refit code-prep 已实现：annual rolling resolved plan 支持 `--true-five-year-refit` / `--emit-refit-only` / 非默认 refit suffix，只输出 `build_refit_training_panel` 与 `cloudrun_refit_register_predict`，不重建 selection matrix 或候选 fanout。
> - 新增/增强 QA 工具：stock window equivalence 可落 summary/sample JSONL；新增 index/market full-vs-window shadow parity；新增 `sql/qa/13_true5y_historical_coverage_checks.sql` 覆盖 `2019-01-02..2019-04-02` 旗标修复、true-five-year 每开市日 coverage 与估值/财务完备度。
> - 本轮只做代码准备和护栏，未执行生产 backfill、未写 DWD/DWS、未重跑 true-five-year refit 或 continuous ledger；后续必须先跑 PRD06 Phase A parity/coverage QA，再进入 2021-2024 true-five-year refit。

Model: GPT-5 Codex

> 当前交接补充（2026-06-11，GPT-5 Codex，PRD_07）
> - PR #182 已合并到 `main@dab646d`，完成 PRD_07 年度滚动调度 Phase 2 live smoke 代码 PR 准备；只改 scheduler、focused test、Strategy1 Cloud Run runbook 和记忆/TODO。
> - `annual_pipeline_scheduler` 默认仍 dry-run 安全；真实提交必须显式 `--execute-live --candidate-only-smoke`，并且 live 路径只支持 candidate-only smoke，不会跑 select/refit/synthetic continuous 或完整 2021-2026 pipeline。
> - 新增 GCS generation-conditioned lease/state、execution 粒度 fanout、matrix 前置检查、artifact skip、state recovery、describe + artifact 双确认；未执行真实 Cloud Run live smoke、未改 job spec/IAM/镜像。

Model: GPT-5 Codex

> 当前交接补充（2026-06-11，GPT-5 Codex）
> - 已完成 Strategy1 暴露管理 NAV 级上限仿真（纯 BigQuery 只读 + 本地 pandas）：新增 `scripts/strategy1/simulate_exposure_overlay_upper_bound.py`、报告 `docs/分析-策略1暴露管理上限仿真-20260611.md`、结果矩阵 `docs/analysis_strategy1_exposure_overlay_upper_bound_20260611_results.csv`。
> - 恒等校验通过：`e(t)==1` 复现 official continuous baseline CAGR `0.12036528993503293`、MaxDD `-0.45481511936569563`、Calmar `0.26464663290635421`、contract Sharpe `0.5285475500566128`；crunch excess vs `000852.SH`=`-0.19329880132544719`，与 PR #179 对比表一致。
> - 最优无摩擦 exposure 变体为 `two_state_biweekly_elow0_cost0bps`：CAGR `0.12130091898447448`、MaxDD `-0.297527701723727`、Calmar `0.4076962188116182`、contract Sharpe `0.6005994875878142`、平均暴露 `0.8873668188736682`、切换 `24` 次。
> - 按预登记判据，Calmar `<0.5`，建议真实 exposure ledger 工程缓做/降优先级；所有 exposure 变体 contract Sharpe 最高仅 `0.6006 < 0.70`，v3 双门仍不可达。报告 follow-up 已把 Markdown 结果表扩展为 25 列详细矩阵并补字段说明；review follow-up 又补入 hysteresis 被 two_state 系统性证伪、48 变体 in-sample selection bias、重算 IR 与官方 summary IR 不可跨文档误比三点。未写任何 BigQuery dataset、未改默认 profile、未 accepted、未 promotion，OQ-010 路线决策仍留给 owner。

Model: GPT-5 Codex

> 当前交接补充（2026-06-11，GPT-5 Codex）
> - PR #179 实现 `quant_ashare.strategy1.tail_risk_overlay_ab` 与 `qa_tail_risk_overlay_ab_outputs`，并完成 live research-only A/B：A1 `strategy1-backtest-report-job-8rqwl`、A2 `strategy1-backtest-report-job-hwqbl`、A3 `strategy1-backtest-report-job-6kbtz` 全部成功。
> - Review follow-up 后增强版 full overlay QA `bqjob_r6fb9e5810c470426_0000019eb59868de_1` 与 research readiness `bqjob_r15d88cd3e8df4d38_0000019eb59868de_1` 均通过；QA-OVERLAY-7/10 已改为逐 arm 硬门，对比表补齐 contract Sharpe、peak/trough、逐年 skip JSON、2024-01~02 vs `000852.SH` crunch excess。
> - 结果：baseline CAGR `0.12036528993503204` / MaxDD `-0.4548151193656952` / Calmar `0.26464663290635254` / crunch excess `-0.1932988013254472`；A1/A3 在 crunch 段转正（`0.10932302982271269` / `0.1226915291378361`）但全周期收益损耗过大；A2 MaxDD 降到 `-0.32883181037211673`，CAGR 降到 `0.0850673652169256`、Calmar 降到 `0.2586956691345056`、crunch excess `0.039028737788334156`。
> - 反向验证：三组 run/backtest 在 ADS run-scoped 表为 0 行，`research_promotion_manifest` 为 0 行。本轮结果仅 research evidence，不改默认 profile、不 accepted、不 promotion。

Model: GPT-5 Codex

> 当前交接补充（2026-06-11，Claude Fable 5，第二批）
> - 新增三个后续工程 PRD：`PRD_20260611_06_策略1历史数据回填与TrueFiveYearRefit.md`（ODS 2010 起历史回填 + 2015Q1/2019Q1 `has_full_history_60d` 旗标修复 + 2021-2024 true-five-year refit 重跑 + 新 synthetic continuous 对比）、`PRD_20260611_07_策略1年度滚动调度Phase2Live化.md`（真实 GCS lease/state、execution 粒度 fanout、candidate-only live smoke）、`PRD_20260611_08_策略1LedgerResume验收闭环.md`（PR #127 已合入但从未验收的 resume 做测试 + research-only 真实数据一致性验收）。
> - 关键探查事实（2026-06-11 只读 BigQuery）：ODS `daily`/`daily_basic` 已有 2010-2014 行（owner 确认 14 endpoint 从 2010 可用）；DWD 价格 2015 起；DWS `2015-Q1` 全部 150,726 行与 `2019-Q1` 全部 208,007 行 `has_full_history_60d=FALSE`——后者是陈旧标记，DWD 已有 2018 行，重刷 `2019-01-02..2019-04-02` 窗口即可修复（实证缺口含 4-01/4-02 两个开市日，不止自然 Q1），无需新数据。
> - PRD_06 的 parity 硬门：重刷不得改变 `2019-04-03` 后任何现有行特征值，保护既有 selection/refit/official continuous 可复现性；不重做选参，2025/2026 refit 不重跑。
> - 本轮 docs/记忆-only，未改代码、未写任何 BigQuery 数据（只读探查）。

Model: Claude Fable 5

> 当前交接补充（2026-06-11，Claude Fable 5）
> - 新增 `docs/prd/PRD_20260611_05_策略1尾部风险OverlayAB.md`：在最新 effective-window synthetic prediction 流上做 P1 / P2 / P1+P2 三组 portfolio-only continuous A/B，对照 baseline 量化 MaxDD / Calmar 改善与 CAGR 损耗；零训练、零 merge。
> - 设计要点：复用 official synthetic run（从记忆/manifest 解析，禁止硬编码 id）、与 official 相同 skip-flags 执行模式（`--skip-tail-risk` 只跳诊断不影响 guard）、guard 生效性断言为硬门（`BUY_SKIPPED_TAIL_RISK` 计数 / risk-off 次日零买单）、risk-off 期现金占比曲线量化"只禁买"的隐性减仓效应。
> - 背景动机：official continuous MaxDD `-45.48%`；回撤窗口 `2021-10-21→2024-02-07` 分解显示 beta≈-36pp、超额损失≈-10pp（疑似集中 2024 踩踏段）。本 A/B 同时是"P1 设默认前必须 full-period A/B"既有约束的前置执行。
> - 本轮 docs/记忆-only，不改代码、不执行 BigQuery / Cloud Run；A/B 结果出来前不改默认 profile、不立暴露管理 PRD。

Model: Claude Fable 5

> 当前交接补充（2026-06-11，GPT-5 Codex）
> - PR #173 已合并到 `main@f1abf46`，dedicated refit panel + `effective_refit_train_start=max(nominal_start, 2019-04-03)` 口径进入主线。
> - 已从 `main@f1abf46` 构建并部署正式 runner digest `sha256:4768d25f49de4bb1e8084476d6f1fe1542ed86750823751fa104738eb0947699`，五个 Strategy1 jobs 的 boot smoke 全过。
> - 2021-2026 dedicated refit panel、final refit、refit QA、synthetic continuous merge、official continuous ledger、continuous QA 均已重跑通过。
> - 最新 official continuous（effective-window）指标：compound_annual_return=`0.12036528993503204`，max_drawdown=`-0.4548151193656952`，information_ratio=`0.5420201365046585`，return_period_count=`1313`。
> - DECISION-20260611-02 已关闭 OQ-014：接受 effective-window result 作为研究复盘口径，暂不修 pre-2019 DWS/lookback；但 result 未过 v3 absolute gates，不得标 accepted baseline 或 promotion。

Model: GPT-5 Codex
## 2026-06-12 GPT-5.5 - Official ledger adjustment leakage quantification

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local Codex session
模型: GPT-5.5
运行环境: `/Users/fisher/Desktop/git/worktrees/quant-ashare-adj-leak`
Run ID: `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01`, `bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`
相关 issue/PR: PR #194（draft）

### 已完成工作

- 新增 `scripts/strategy1/analyze_official_adj_leak.py`，以 BigQuery 只读查询 + 本地 pandas 量化 official ledger "未复权价 + 恒定股数"约定造成的漏损。脚本参数化 backtest_id、时间窗口、本地输出目录和 GCS 前缀，并为查询附带 readonly labels。
- 新增报告 `docs/分析-官方Ledger复权漏损量化-20260612.md`，按预登记判据先写后填，覆盖修正前/后指标、年度分解、事件类型拆分、Top10 单事件、无交易日残差对账和口径声明。
- 新增小结果 CSV `docs/analysis_official_ledger_adj_leak_20260612_metrics.csv`；逐日序列、事件明细、年度分解、残差统计和 BigQuery job audit JSON 上传至 `gs://ashare-artifacts/reports/strategy1/official_adj_leak/analysis_date=20260612/`。
- 新增轻量单测 `tests/strategy1/test_official_adj_leak.py`，覆盖 NAV 复合、N-1 年化波动/Sharpe、事件分类、残差硬门和预登记判读。

### 关键结果

- true-five-year 主结果：修正前 CAGR `13.85%`、MaxDD `-37.19%`、contract Sharpe `0.6076`、Calmar `0.3725`；hfq 代理修正后 CAGR `15.72%`、MaxDD `-36.76%`、contract Sharpe `0.6894`、Calmar `0.4275`。变化为 CAGR `+1.86pp`、Calmar `+0.0550`，触发预登记判据，报告建议 owner 立 PRD 修 ledger 并排在 Phase 2 之前。
- effective-window 参照：修正前 CAGR `12.04%`、MaxDD `-45.48%`、contract Sharpe `0.5285`、Calmar `0.2646`；修正后 CAGR `13.56%`、MaxDD `-44.99%`、contract Sharpe `0.5961`、Calmar `0.3014`。
- 对账硬门：无交易日上 `SUM(prev_day_weight * raw_return)` 与 official `daily_return` 残差通过，true-five-year `max_abs=1.44e-16`，effective-window `max_abs=2.25e-16`。
- 漏损分解：true-five-year 事件累计 `8.4670pp`（送转型 `2.2118pp`，分红/小事件型 `6.2552pp`）；effective-window 事件累计 `7.0161pp`（送转型 `0.6126pp`，分红/小事件型 `6.4035pp`）。

### 重要边界

- 本轮只做 measurement，不修改 ledger / 生产 SQL / Cloud Run job spec / 既有 run 数据，不执行 promotion。
- hfq 修正近似总回报口径，隐含分红再投资；真实 ledger 修复应是现金入账，不能把本报告直接当作 production ledger 实现方案。
- 不关闭 OQ、不替 owner 重开 `DECISION_LOG` 中已接受的未复权/除权简化约定。

### 改动文件

- `scripts/strategy1/analyze_official_adj_leak.py`
- `tests/strategy1/test_official_adj_leak.py`
- `docs/分析-官方Ledger复权漏损量化-20260612.md`
- `docs/analysis_official_ledger_adj_leak_20260612_metrics.csv`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 scripts/strategy1/analyze_official_adj_leak.py`
- `gcloud storage ls -l 'gs://ashare-artifacts/reports/strategy1/official_adj_leak/analysis_date=20260612/**'`
- `python3 -m pytest -q tests/strategy1/test_official_adj_leak.py`
- `python3 -m py_compile scripts/strategy1/analyze_official_adj_leak.py tests/strategy1/test_official_adj_leak.py`
- `git diff --check`

### 下一步建议

- owner 决定是否按报告建议立 ledger 修复 PRD，并明确该修复与 PRD_10 topdown / Phase 2 的排序。
- 若暂不修 ledger，应把量化后的漏损幅度写入 `KNOWN_CONSTRAINTS.md` 做永久披露；本轮未提前执行该决策。
## 2026-06-12 GPT-5 Codex - Current-scope ODS checkpoint archive

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local Codex session
模型: GPT-5 Codex
运行环境: `/Users/fisher/Desktop/git/worktrees/quant-ashare-checkpoint-archive`
Run ID: `checkpoint_archive_current14_20260612T035604Z`
相关 issue/PR: N/A

### 已完成工作

- 按 owner 要求，将现有项目当前生产范围的 14 个 ODS checkpoint 中 `logical_date >= 20100101` 的对象归档到 `gs://data-aquarium/a-share/tushare/checkpoint_archive/run_id=checkpoint_archive_current14_20260612T035604Z/`。
- 归档范围来自 `configs/ingestion/ods_current_scope_v0.yml` 的 14 个 endpoint 及现有 current partition variants；未纳入非 current-scope endpoint。
- 生成 26 个 endpoint gzip JSONL 归档对象和 `manifest.json`；共 65,891 条 checkpoint 记录，源 checkpoint 47,955,858 bytes，gzip 归档 7,951,990 bytes。
- 每条 JSONL 保存原 GCS 路径、generation、校验值和 `content_base64`，因此可从归档反向恢复原 checkpoint 内容。
- 本轮未删除任何原始 `_checkpoints/` 对象，也未设置 lifecycle。

### 重要上下文

- manifest 路径：`gs://data-aquarium/a-share/tushare/checkpoint_archive/run_id=checkpoint_archive_current14_20260612T035604Z/manifest.json`。
- 4 个 current-scope checkpoint endpoint 在当前 GCS 扫描中为空：`index_daily`、`index_daily_000001_SH`、`index_dailybasic`、`index_dailybasic_000001_SH`。
- 归档过程只处理 `_checkpoints` 小 JSON 内容；不处理也不下载 `raw_data`。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 已回读 manifest 和全部 26 个 gzip 归档对象，重算每个归档的行数、源字节数、gzip 字节数和 `jsonl_sha256`，与 manifest 一致。
- 已逐条校验 `content_base64` 解码后的 sha256 与记录的 `content_sha256` 一致。
- 已抽样 5 个原 checkpoint 对象，按 GCS generation 回读并比对 sha256 通过。

### 阻塞项

- 无归档阻塞项。
- 如要通过删除或 lifecycle 真正减少对象数，需要 owner 另行明确批准保留窗口、删除范围和恢复演练要求。

### 下一步建议

- 删除前保留最近 30-90 天 checkpoint，或先按 manifest 恢复抽样 checkpoint 到临时前缀验证完整恢复流程。
- 若 owner 确认减少对象数，再对原 `_checkpoints/` 制定 age=90/180 lifecycle 或批量删除计划。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
## 2026-06-11 GPT-5 Codex - PRD_09 signal IC transfer efficiency analysis

### 已完成工作

- 基于 `origin/main@d411144` 新建 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-signal-ic-analysis`，分支 `codex/signal-ic-transfer-analysis`。
- 新增 `scripts/strategy1/analyze_signal_ic_decomposition.py`，实现 PRD_09 的 Part A IC decomposition 与 Part B transfer ladder；`scripts/strategy1/analyze_transfer_ladder.py` 为兼容入口，复用同一实现，避免两套逻辑漂移。
- 新增报告 `docs/分析-策略1信号IC分解与转换效率-20260611.md` 与四份 CSV：IC summary、daily IC、transfer ladder results、transfer coefficients。CSV 因仓库 `*.csv` ignore 规则需 `git add -f` 纳入 PR。
- 本地执行时安装了缺失的 `google-cloud-bigquery-storage` 用户级 Python 依赖，用于加速 BigQuery Storage API 结果读取；未改仓库依赖文件。

### 重要上下文

- official synthetic prediction run：`s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02`；official backtest：`bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`；窗口 `2021-01-04..2026-06-09`；label version `open_to_close_h1_5_10_20_v20260601`；feature version `strategy1_pv_v0_20260601`；market state version `market_state_v1_20260607`；benchmark `000852.SH`。
- 初次运行曾因默认 `strategy_id=strategy1_lgbm_v1` 查不到 synthetic registry join；只读断点查询确认 registry 实际 `strategy_id=ml_pv_clf_v0`，脚本默认值已修正为 `ml_pv_clf_v0`，仍可 CLI 覆写。
- Part A 结果：5d raw rank IC=`0.040908`，NW t=`5.586351`；年度 5d IC 全正（2021=`0.030861`、2022=`0.027927`、2023=`0.016943`、2024=`0.064402`、2025=`0.055560`、2026 YTD=`0.062493`）；市值中性后 IC=`0.037032`，保留 raw `90.52%`；snapshot 行业参考中性后 IC=`0.036080`，保留 `88.20%`。
- Regime / bucket：risk_off IC=`0.030273` 但 NW t=`1.189055`，risk_on IC=`0.058193`；top/bottom decile 5d spread=`0.7486pp`，short-side contribution share=`52.51%`，未超过 60% 阈值。
- Part B：L0 score-weighted long/short no-cost annual Sharpe=`2.800047`，20bps 成本后 `1.807056`；L0.5 top-decile long-only IR=`0.509749`，L1/L2/L3 long-only IR 分别约 `0.491` / `0.544` / `0.486`。L3-L2 IR 差=`-0.058363`，L1-L2 IR 差=`-0.053236`，宽度从 top decile 收到 Top50/Top20 没有形成第二个悬崖。
- Review follow-up 修正旧 TC 伪迹：非零并集相关会退化为对等权常数向量求相关，不能解释为 `TC≈0`。现改用 full prediction universe 域并补 membership 诊断：平均 `TC_target=0.712888`、`TC_realized=0.628765`；target 与 score-weighted Top20 名字重合率均值/最小值均 `100%`，说明目标组合成员资格忠实于信号，等权替代分数权重不是优先瓶颈。执行层缺口用 realized/target 覆盖率与现金解释：覆盖率均值 `81.51%`、最小 `5%`，TC 行内 `official_cash_weight` 均值 `29.07%`。
- 交叉核验确认 official 现金不是 join 伪迹：NAV `cash_cny/net_value_cny` 与 `1-sum(position.weight)` 最大差 `2.22e-16`，差异天数 `0`；NAV 现金权重均值 `29.36%`，现金 >50% 交易日 `265` 天。全周期 `BUY_SKIPPED_BELOW_LOT=690`；最低覆盖执行日 `2021-12-27` 的 20 个 BUY 全部为 `BUY_SKIPPED_BELOW_LOT`。
- L3 paper 与 official daily_return corr=`0.913059`，但 paper CAGR 比 official 高 `2.90pp`、MaxDD 比 official 差 `12.30pp`；报告明确 paper ladder 只用于转换效率上界/分解，不等同 official ledger。
- 全程 BigQuery 只读，未写任何 dataset，未改 run/backtest，未 accepted，未 promotion。OQ-010 路线决策仍留 owner。

### 改动文件

- `scripts/strategy1/analyze_signal_ic_decomposition.py`
- `scripts/strategy1/analyze_transfer_ladder.py`
- `tests/strategy1/test_signal_ic_transfer_analysis.py`
- `docs/分析-策略1信号IC分解与转换效率-20260611.md`
- `docs/analysis_strategy1_signal_ic_decomposition_20260611_summary.csv`
- `docs/analysis_strategy1_signal_ic_decomposition_20260611_daily.csv`
- `docs/analysis_strategy1_transfer_ladder_20260611_results.csv`
- `docs/analysis_strategy1_transfer_ladder_20260611_transfer_coefficients.csv`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- Live read-only analysis：`python3 scripts/strategy1/analyze_signal_ic_decomposition.py` 成功生成报告和四份 CSV。
- `python3 scripts/strategy1/analyze_signal_ic_decomposition.py --help` 与 `python3 scripts/strategy1/analyze_transfer_ladder.py --help` 均成功。
- `python3 -m pytest -q tests/strategy1/test_signal_ic_transfer_analysis.py tests/strategy1/test_exposure_overlay_upper_bound.py`：16 passed。
- `python3 -m py_compile scripts/strategy1/analyze_signal_ic_decomposition.py scripts/strategy1/analyze_transfer_ladder.py`：通过。
- `python3 -m compileall -q scripts/strategy1 tests/strategy1`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `git diff --check`：通过。

### 阻塞项

- 无实现阻塞。本报告不关闭 OQ-010，不替 owner 做下一步策略路线决策。

### 下一步建议

- 基于 PRD_09 结果，下一步优先讨论组合转换方向：long-only 相对多空的约束损耗、真实 ledger 的 100 股整手 / 小资金现金拖累、以及是否需要把 target 名字忠实但实际持仓覆盖不足的问题纳入后续组合/执行层改造；等权 Top20 和 Top50 扩宽暂非优先瓶颈。
- 不建议把本次 paper ladder 数值当正式回测结果；任何策略默认/accepted/promotion 仍需独立 PRD、真实 ledger 与 QA。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
## 2026-06-11 GPT-5 Codex - Cloud Run ledger resume acceptance

### 已完成工作

- 基于 `origin/main@6b619b0` 新建分支 `codex/strategy1-resume-acceptance`，实施 `docs/prd/PRD_20260611_08_策略1LedgerResume验收闭环.md`。
- `qa_ledger_resume_consistency` 已从旧 BQML / `ledger_exec_v1` 默认值升级为 Cloud Run Python `ledger_exec_v1_lot100` / research-first 口径。
- `qa_cloudrun_ledger_resume_outputs` 与 `qa_ledger_resume_consistency` 均纳入 `manual_resume_qa` active contract，要求 `p_state_as_of_date`、`p_resume_policy_id`、`p_ledger_version`、`p_rebalance_anchor_start`，并断言 `p_compare_start` 为 `state_as_of_date` 后下一 SSE 开市日。
- 真实 research-only resume child 已跑通：`s1_resume_acceptance_resume_20250102_20260609_v20260611_01` / `bt_s1_resume_acceptance_resume_20250102_20260609_v20260611_01`，Cloud Run execution `strategy1-backtest-report-job-82454`。
- 两套 QA 均通过：`qa_cloudrun_ledger_resume_outputs` job `eb99f350-feb4-4fdc-977d-d2e6b7c74201`；`qa_ledger_resume_consistency` job `8b2b1e17-42ad-44d2-8318-9f283c26eee2`。

### 重要上下文

- 验收 parent 为 latest effective-window official continuous backtest `bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`，cut `2024-12-31`，next open `2025-01-02`，rebalance anchor `2021-01-04`。
- 等价参照必须是 full fresh continuous parent 的同窗口切片；cut 后重新 fresh-start 的短段会重置现金、持仓和 NAV，不能作为 resume 等价参照。本轮曾跑过 short fresh diagnostic，但不纳入验收。
- 验收产物行数：candidate `89315`、target `740`、order `1340`、trade `1392`、position `6554`、NAV `345`、ledger state `345`、summary `1`。ADS 同 run/backtest candidate/trade/NAV/ledger state/summary 均为 `0` 行。
- 默认正式 continuous 仍为 fresh-run；resume 已是可用工具，但正式结果若采用 resume segment 仍需 owner 显式批准并重跑两套 resume QA。

### 改动文件

- `configs/strategy1/active_step_catalog.yml`
- `sql/strategy1/qa/qa_cloudrun_ledger_resume_outputs.sql`
- `sql/strategy1/qa/qa_ledger_resume_consistency.sql`
- `tests/strategy1/test_ledger_resume_acceptance.py`
- `docs/prd/PRD_20260611_08_策略1LedgerResume验收闭环.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest -q tests/strategy1/test_ledger_resume_acceptance.py tests/strategy1/test_strategy1_catalog.py tests/strategy1/test_sql_render.py`：24 passed。
- Cloud Run resume child execution `strategy1-backtest-report-job-82454`：succeeded。
- BigQuery QA jobs `eb99f350-feb4-4fdc-977d-d2e6b7c74201` / `8b2b1e17-42ad-44d2-8318-9f283c26eee2`：succeeded。
- BigQuery readback confirmed research output rows present and ADS output rows zero for the resume child run/backtest.

### 阻塞项

- 无。

### 下一步建议

- 若正式结果采用 resume segment，仍需 owner 显式批准并重跑两套 resume QA。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
## 2026-06-12 GPT-5 Codex - PR #186 CSV cleanup

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: 本地 Codex desktop session
模型: GPT-5 Codex
运行环境: `/Users/fisher/Desktop/git/worktrees/quant-ashare-remove-pr186-csv`
Run ID: N/A
相关 issue/PR: PR #186

### 已完成工作

- 按 owner 要求直接从 `main` 删除 PR #186 带入的四份分析 CSV。
- 保留 PR #186 的只读分析脚本、测试和 Markdown 报告；未删除其他 PR 的 CSV。
- 同步更新 `IMPLEMENTATION_STATUS.md`、`AGENT_HANDOFF.md` 和 `TODO.md`，记录 CSV 作为可再生成临时产物的清理口径。

### 重要上下文

- 删除文件为 `docs/analysis_strategy1_signal_ic_decomposition_20260611_daily.csv`、`docs/analysis_strategy1_signal_ic_decomposition_20260611_summary.csv`、`docs/analysis_strategy1_transfer_ladder_20260611_results.csv`、`docs/analysis_strategy1_transfer_ladder_20260611_transfer_coefficients.csv`。
- `docs/analysis_strategy1_exposure_overlay_upper_bound_20260611_results.csv` 属于其他 PR，本轮未动。
- 本轮未运行 BigQuery、未启动 Cloud Run、未改策略结论、未改变 accepted / promotion 状态。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
- `docs/analysis_strategy1_signal_ic_decomposition_20260611_daily.csv`
- `docs/analysis_strategy1_signal_ic_decomposition_20260611_summary.csv`
- `docs/analysis_strategy1_transfer_ladder_20260611_results.csv`
- `docs/analysis_strategy1_transfer_ladder_20260611_transfer_coefficients.csv`

### 测试 / 验证

- `git diff --name-status HEAD -- '*.csv'` 确认仅删除 PR #186 的四份 CSV。
- `git diff --check` 通过。

### 阻塞项

- 无。

### 下一步建议

- 后续分析 CSV 默认作为本地临时产物；只有 owner 明确要求或测试 fixture 必需时才纳入 git。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
## 2026-06-11 GPT-5 Codex - PRD_07 annual scheduler live smoke code prep

### 已完成工作

- PR #182 已合并到 `main@dab646d`。原独立 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-prd07-live-smoke`，分支 `codex/prd07-annual-live-smoke`。
- `quant_ashare.strategy1.annual_pipeline_scheduler` 新增 Phase 2 candidate-only live smoke 路径，入口必须同时传 `--execute-live --candidate-only-smoke`；默认 dry-run / 非 live 仍保持安全。
- 新增真实 GCS generation-conditioned annual scheduler lease/state 抽象；state create/update 使用 generation precondition，冲突重读/重试，丢失 lease ownership 停止提交。
- live smoke 按 Cloud Run execution 记账，先检查对应 matrix `matrix_manifest.json` / `work_units.json` 已存在，缺失则本地失败且不提交 Cloud Run；支持 artifact precheck skip、state recovery 不重复提交、共享资源池 admission、execution describe + candidate artifact 双确认；`gcloud execute` 非零但有 execution id 时按 describe/artifact 二次确认。
- 更新 `docs/策略1CloudRun训练回测运行手册.md` 的 Phase 2 live smoke 命令与边界说明。

### 重要上下文

- 本轮没有执行真实 Cloud Run live smoke，没有跑完整 2021-2026 pipeline，没有修改 Cloud Run job spec、IAM 或镜像。
- PRD_07 后续真实验收仍需在合并/部署后按 candidate-only 五场景执行并记录 execution id / artifact 路径；执行前必须先准备/复用对应 run-version 的 matrix artifact。

### 改动文件

- `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`
- `tests/strategy1/test_annual_pipeline_scheduler.py`
- `docs/策略1CloudRun训练回测运行手册.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_annual_pipeline_scheduler.py`：13 passed。
- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_annual_pipeline_scheduler.py tests/strategy1/test_strategy1_catalog.py tests/strategy1/test_tail_risk_overlay_ab.py`：25 passed。

### 阻塞项

- 无代码阻塞。真实 candidate-only live smoke 尚未执行。

### 下一步建议

- 合并并部署含本分支代码的 runner 镜像后，按 runbook 执行 PRD_07 candidate-only live smoke 五场景；通过前不要声称 annual scheduler live 化已经生产验收。
- Phase 3 完整 2021-2026 live pipeline 仍需 owner 另批。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
## 2026-06-11 GPT-5 Codex - Exposure overlay upper-bound simulation

### 已完成工作

- 新增 `scripts/strategy1/simulate_exposure_overlay_upper_bound.py`，对 official continuous baseline NAV 做本地 pandas 暴露缩放上限仿真；BigQuery 查询全为只读，不写 `ashare_research` / ADS / promotion 相关表。
- 新增 `docs/分析-策略1暴露管理上限仿真-20260611.md`，按预登记判据报告方法、局限、恒等校验、完整矩阵摘要和结论；review follow-up 后补充 hysteresis 明显弱于 two_state、best-of-grid 存在 in-sample selection bias、重算 IR 与官方 summary IR 口径差异。
- 新增结果 CSV `docs/analysis_strategy1_exposure_overlay_upper_bound_20260611_results.csv`，包含 identity + `e_low` / 状态机 / 生效时点 / 成本档共 49 行结果；review follow-up 后 Markdown 报告也展示同一 25 列详细结果矩阵和字段说明。
- 新增 `tests/strategy1/test_exposure_overlay_upper_bound.py`，覆盖 PIT 信号、三态迟滞、biweekly 调仓约束、成本扣减、identity metric 复现和 markdown 表输出。

### 重要上下文

- Baseline backtest：`bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`；窗口 `2021-01-04..2026-06-09`；market state version `market_state_v1_20260607`；基准 `000852.SH` 使用 `dwd_index_eod.pct_chg / 100`。
- 恒等校验通过：CAGR `0.12036528993503293`、MaxDD `-0.45481511936569563`、Calmar `0.26464663290635421`、contract Sharpe `0.5285475500566128`；crunch excess vs `000852.SH`=`-0.19329880132544719`。
- 最优无摩擦变体：`two_state_biweekly_elow0_cost0bps`，CAGR `0.12130091898447448`、MaxDD `-0.297527701723727`、Calmar `0.4076962188116182`、contract Sharpe `0.6005994875878142`、平均暴露 `0.8873668188736682`、暴露切换 `24` 次。
- 预登记判据结论：最优 Calmar `<0.5`，真实 exposure ledger 工程建议缓做/降优先级，剩余主要缺口在 alpha / 信号 / 组合构造。所有 exposure 变体最高 contract Sharpe `0.6006 < 0.70`，即使达到上界也不能通过 v3 双门。

### 改动文件

- `scripts/strategy1/simulate_exposure_overlay_upper_bound.py`
- `tests/strategy1/test_exposure_overlay_upper_bound.py`
- `docs/分析-策略1暴露管理上限仿真-20260611.md`
- `docs/analysis_strategy1_exposure_overlay_upper_bound_20260611_results.csv`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- Live read-only simulation：`Identity check passed`，market state / NAV / benchmark SSE 开市日覆盖一致，`is_risk_off` 无 NULL。
- Focused pytest：`tests/strategy1/test_exposure_overlay_upper_bound.py` 通过，含 detailed report column guard 和 review caveat guard。
- `compileall`、retired linter、Dataform generated SQLX check、`git diff --check` 已通过；`tests/strategy1` 已通过。

### 阻塞项

- 无实现阻塞。本报告不关闭 OQ-010，不替 owner 做路线决策。

### 下一步建议

- 若继续策略侧推进，优先把资源放在 alpha / 信号 / 组合构造或更强的回撤控制设计上；真实 exposure ledger 在当前上界证据下不宜作为下一阶段 P0。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
## 2026-06-11 GPT-5 Codex - PRD06 true-five-year refit code-prep

### 已完成工作

- 基于 `origin/main@dab646d` rebase，worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-prd06-true5y`，分支 `codex/prd06-true5y-refit`。
- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py` 新增 true-five-year refit-only plan 能力：`--true-five-year-refit` 禁用 `2019-04-03` floor，`--final-refit-run-suffix` 强制使用非默认 suffix，`--emit-refit-only` 只输出 refit panel / refit-register-predict 两步。
- `scripts/qa/run_windowed_refresh_equivalence.py` 增强 summary JSONL 与 mismatch sample JSONL 输出，便于 PRD06 overlap parity 留档。
- 新增 `scripts/qa/run_index_market_windowed_equivalence.py`，用 scratch full/window shadow 表对比 `dwd_index_eod` 与 `dws_market_state_daily` 的 window refresh 等价性。
- 新增 `sql/qa/13_true5y_historical_coverage_checks.sql`，覆盖 `2019-01-02..2019-04-02` 旗标修复、true-five-year open-day feature/sample coverage、估值完备度硬门与财务完备度报告。
- 更新 Strategy1 Cloud Run runbook、`KNOWN_CONSTRAINTS.md`、`IMPLEMENTATION_STATUS.md`、`TODO.md`。

### 重要上下文

- 本轮是代码准备，不是生产执行：没有执行 BigQuery backfill，没有写 DWD/DWS，没有重跑 2021-2024 true-five-year refit，也没有生成新的 continuous ledger。
- `--true-five-year-refit` 只能在 PRD06 Phase A 完成后使用：历史 DWD/DWS 回填、`2019-01-02..2019-04-02` 旗标修复、`sql/qa/13_true5y_historical_coverage_checks.sql`、stock/index/market parity 全过。
- true-five-year refit run 必须使用非默认 suffix（例如 `__true5y01`），不得覆盖 current effective-window `__refit01` 产物。

### 改动文件

- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`
- `scripts/qa/run_windowed_refresh_equivalence.py`
- `scripts/qa/run_index_market_windowed_equivalence.py`
- `sql/qa/13_true5y_historical_coverage_checks.sql`
- `docs/策略1CloudRun训练回测运行手册.md`
- `tests/strategy1/test_true5y_prd06_contracts.py`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_true5y_prd06_contracts.py tests/strategy1_cloudrun/test_dataset_role_routing.py tests/strategy1/test_refit_panel_coverage_contract.py`：32 passed。
- `python3 -m py_compile scripts/qa/run_windowed_refresh_equivalence.py scripts/qa/run_index_market_windowed_equivalence.py scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`：通过。

### 阻塞项

- 生产 backfill / true-five-year refit / continuous ledger 尚未执行；需合并部署后按 PRD06 Phase A/B/C 分步跑，并逐步记录证据。

### 下一步建议

- 合并 code-prep PR 后先跑 `2019-01-02..2019-04-02` 最小旗标修复与 parity QA；确认 `2019-04-03` 后零变化后，再扩到 2010+ 历史回填和 2021-2024 true-five-year refit。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`
## 2026-06-11 GPT-5 Codex - Tail-risk overlay A/B implementation and live run

### 已完成工作

- 合并 PR #176，merge commit `5c27e28`。
- 基于 `origin/main@5c27e28` 新建 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-tail-risk-overlay-ab`，分支 `codex/strategy1-tail-risk-overlay-ab`。
- 新增 `quant_ashare.strategy1.tail_risk_overlay_ab`：research-only，自动发现 latest refit-backed synthetic continuous source，构造 A1 / A2 / A3 三组 overlay arm，可 `--parallel-arms` 并发提交 Cloud Run backtest-report jobs，并串接 continuous / lot-aware / overlay QA。
- 新增 `qa_tail_risk_overlay_ab_outputs` 并登记 catalog；QA 覆盖 source/preflight、market state 全窗口覆盖、tail-risk required fields、生效性、risk-off 次日零 filled BUY、market skip 只在 risk-off execution dates、A2 guard 前 candidate / target 与 baseline 一致。
- 更新 Cloud Run runbook，补 Tail-risk overlay continuous A/B dry-run / preflight / execute 示例。

### 重要上下文

- Source synthetic run：`s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02`；synthetic model `synth_s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02`；input manifest sha256 `bfd1e3c3e251954ae5ffa1a58102570e4c4538a92b24c9c181c7e41368877166`。
- Baseline backtest：`bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`。
- Live preflight job：`721577f5-35dc-4609-ab23-683af2e12c5b`。
- Cloud Run executions：A1 `strategy1-backtest-report-job-8rqwl`、A2 `strategy1-backtest-report-job-hwqbl`、A3 `strategy1-backtest-report-job-6kbtz`，均 succeeded。
- QA jobs：A1 continuous `e9637a8b-9c04-4d1a-be9e-267ce75ea886` / lot-aware `c6b62f19-daf0-4253-8917-ce4b5d04c790`；A2 continuous `f970f701-d5aa-4efe-8dbd-1e5ac2dd4c6d` / lot-aware `78935e7c-e6cf-45ab-9b00-bab668b8ec42`；A3 continuous `430a0a94-4a86-413b-a9af-38edfa3f46db` / lot-aware `40a8ebb7-3a90-4a2c-9ea7-4c5d6b408dca`；initial full overlay QA `cb94dc74-9e73-4921-b709-d02cae615bb2`；review follow-up 后 enhanced full overlay QA `bqjob_r6fb9e5810c470426_0000019eb59868de_1`；research readiness QA `bqjob_r15d88cd3e8df4d38_0000019eb59868de_1`。
- 结果：A1/A3 证明确实能改善 2024-01~02 crunch 段超额（baseline `-0.1932988013254472`，A1 `0.10932302982271269`，A3 `0.1226915291378361`），但全周期 CAGR/Calmar 损耗过大，不建议设默认；A2 是全周期 MaxDD/CAGR 取舍相对可讨论的 overlay（MaxDD `-0.32883181037211673`、CAGR `0.0850673652169256`、Calmar `0.2586956691345056`、crunch excess `0.039028737788334156`），但也未改善 Calmar。
- 本轮没有 promotion；ADS run-scoped 表对三组 run/backtest 反向验证为 0 行，`research_promotion_manifest` 同 source 为 0 行。

### 改动文件

- `src/quant_ashare/strategy1/tail_risk_overlay_ab.py`
- `sql/strategy1/qa/qa_tail_risk_overlay_ab_outputs.sql`
- `configs/strategy1/active_step_catalog.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `tests/strategy1/test_tail_risk_overlay_ab.py`
- `tests/strategy1/test_cloudrun_package_entrypoints.py`
- `tests/strategy1/test_package_boundaries.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

### 测试 / 验证

- Focused pytest：21 passed；新增 `--parallel-arms` 后 focused pytest：6 passed。
- BigQuery dry-run：`qa_tail_risk_overlay_ab_outputs.sql` 通过。
- Research render check：无 `ashare_ads` 残留，命中 `ashare_research.research_backtest_trade_daily`。
- Live preflight、三组 Cloud Run executions、三组 continuous / lot-aware QA、full overlay QA、review follow-up 后 enhanced full overlay QA 和 research readiness QA 均通过。
- BigQuery 反向验证 ADS run-scoped 表与 promotion manifest 均为 0 行。

### 阻塞项

- 无实现阻塞。是否继续优化 A2、转向暴露管理 PRD，或保持研究证据，需要 owner 决策。

### 下一步建议

- 不要把任何 overlay profile 直接设为默认。若继续沿风控路线推进，优先拆成两条：调窄 P1 规则以减少常年误伤，或另写暴露管理 / 仓位控制方案；A2 可作为全周期 drawdown/carry tradeoff 对照。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`
## 2026-06-11 GPT-5 Codex - Effective-window result decision

### 已完成工作

- 基于 PR #174 合并后的 `main@f8cf151` 新建分支 `codex/decide-effective-window-baseline`。
- 复核 latest effective-window official continuous result 与 `model_acceptance_contract_v3`：contract Sharpe=`0.5285475500566089`，低于 `0.70`；Calmar=`0.26464663290635254`，低于 `1.0`。
- 只读 BigQuery 复核 synthetic registry：run `s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02` 仍为 `status='selected'`，无 `acceptance_status` / `native_acceptance_status`。
- 追加 `DECISION-20260611-02`：接受 effective-window annual final refit / continuous ledger 作为当前研究复盘事实口径，暂不投入 pre-2019 DWS lookback / valuation 覆盖重建；不得标 accepted baseline，不得 promotion。
- 关闭 OQ-014 并移入 `.agent/memory/archive/CLOSED_QUESTIONS.md`。

### 重要上下文

- 当前结果可用于下一轮策略复盘和实验设计，但不是 production accepted baseline。
- 2021-2024 仍不能描述为名义完整五年 refit。
- 若未来需要 true five-year annual evidence，需要重新开专项：先修复 / 重建 DWS lookback 与历史 valuation 覆盖，再重跑 dedicated panel / refit / continuous。

### 改动文件

- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/archive/CLOSED_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- BigQuery 只读复核 effective-window summary / registry acceptance state。
- `git diff --check`：通过。

### 阻塞项

- 无。

### 下一步建议

- 基于 latest effective-window official continuous 做下一轮 OQ-010 策略改进方案，重点处理回撤与 risk-adjusted return；不要 promotion 当前 result。

### 已更新记忆文件

- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/archive/CLOSED_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
## 2026-06-11 GPT-5 Codex - Annual final refit dedicated panel rerun

### 已完成工作

- PR #173 已合并到 `main`，merge commit `f1abf46`，annual plan / scheduler 已正式切到 `select -> build_refit_training_panel -> refit`。
- 从 `main@f1abf46` 构建并部署正式镜像 `strategy1-cloudrun-runner@sha256:4768d25f49de4bb1e8084476d6f1fe1542ed86750823751fa104738eb0947699`；五个正式 Strategy1 jobs 已更新，`latest` tag 未改。
- 六个 boot smoke 全部成功：`strategy1-train-predict-job-f5bs7`、`strategy1-prepare-matrix-job-s7bww`、`strategy1-train-candidate-fanout-job-w925b`、`strategy1-select-register-predict-job-w66fd`、`strategy1-backtest-report-job-whbxz`、`strategy1-train-predict-job-jtx7r`（`refit_register_predict --help`）。
- 2021-2026 dedicated refit panels 已重建成功，BigQuery jobs：`a967f6fe-9382-4a27-a18c-be3bd7e2fd4a`、`d69aeb3c-bc63-47d1-bd07-e89c224cf37c`、`00bf60cf-f0e5-4688-aa1b-c2bd9a9f8d27`、`41ed2c12-5d24-49a7-a81b-dab91fc1e6fc`、`b75ee22c-662b-4413-9e7e-5538f7d487a8`、`0c5a0656-407d-4c1e-9c99-3eeef5e09ab9`。
- 六年 final refit 全部成功，Cloud Run executions：`strategy1-train-predict-job-t4vq7`、`strategy1-train-predict-job-bmdw6`、`strategy1-train-predict-job-jjblp`、`strategy1-train-predict-job-zwg82`、`strategy1-train-predict-job-9zm2h`、`strategy1-train-predict-job-qvc78`。
- 六年 `qa_refit_register_predict_outputs` 全部通过：`27b9ffcc-4ecc-433b-b830-110551d08d0b`、`03213822-637a-4b37-92e3-2dc6d179faaa`、`e5136216-1e9f-4b51-80ba-cc9c93c2cc15`、`ca85715d-94f7-4c5d-bcef-cb44aff62253`、`df3e1750-9952-424b-94c3-af2d5403ac21`、`52f6ae15-9dec-4cc1-a0de-bffac8ed4d89`。
- Official synthetic continuous 以同一 run id `s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02` 重写成功，insert job `d2f9beea-a58f-4650-82d2-07b135174ee9`，prediction rows=`2643406`，resolved manifest sha256=`2062d93544dd7c2bd12566f42da0ad3c973b5c6a63f00f4cd1c72a3a5269ba97`。
- Official continuous ledger 重跑成功，execution `strategy1-backtest-report-job-mq5d8`；continuous QA `fcd75906-ec42-454e-92e1-9b47d19a5727` 与 lot-aware QA `95dcee06-e912-481a-9c02-aafb14a823c5` 均通过。

### 重要上下文

- Effective-window official continuous summary：total_return=`0.8079208887460085`，compound_annual_return=`0.12036528993503204`，max_drawdown=`-0.4548151193656952`，information_ratio=`0.5420201365046585`，turnover_annual=`38.4823484768493`，total_economic_cost_cny=`17041.911125399998`。
- 输出行数：prediction `2643406`、NAV `1314`、ledger_state `1314`、signal_monitor `1314`、candidate `279625`、order `4806`、trade `4776`、position `21401`、summary `1`。
- `research_promotion_manifest` 行数为 `0`，ADS registry / prediction / summary 对同 synthetic run/backtest 均为 `0`。本轮没有 promotion、没有 ADS 写入。
- 本轮结果是 current DWS coverage 下的 effective-window refit。2021-2024 不得表述为名义完整五年 refit；是否可进入 baseline 评估仍由 OQ-014 owner 决策。

### 改动文件

- `docs/策略1CloudRun训练回测运行手册.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

### 测试 / 验证

- PR #173 合并前：focused pytest 32 passed；full pytest 122 passed；retired lint、Dataform generated SQLX `--check`、compileall、`git diff --check` 均通过。
- 部署后六个 Cloud Run `--help` boot smoke 均 Completed=True。
- 六年 `qa_refit_register_predict_outputs` 均通过。
- Official continuous `qa_continuous_backtest_outputs` 与 `qa_lot_aware_ledger_outputs` 均通过。
- BigQuery 审计确认 research outputs 存在、promotion manifest 为 0、ADS 同 synthetic run/backtest 为 0。

### 阻塞项

- 无执行阻塞。OQ-014 仍需 owner 方法论决策。

### 下一步建议

- 决定 OQ-014：接受 effective-window annual result 进入下一轮策略评估，或投入 DWS/lookback 修复后追求 true pre-2019 五年窗口。
- 若接受 effective-window 口径，再基于最新 official continuous 指标决定是否推进 accepted baseline 方案；仍不得直接 promotion。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`
## 2026-06-11 GPT-5 Codex - Annual final refit dedicated panel implementation

### 已完成工作

- 基于 `origin/main@d6a40e6` 新建干净 worktree `/Users/fisher/Desktop/git/quant-ashare-refit-panel`，分支 `codex/fix-annual-refit-dedicated-panel`。
- 在 `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py` 中新增 dedicated refit panel plan step：selection panel 仍作为每年第一步服务 matrix / fanout / select，`build_refit_training_panel` 在 select 后用 refit run_id 写 panel。
- `cloudrun_refit_register_predict` 仍用 `--source-run-id=<selection run>` 读取 selected candidate lineage，但 `--source-panel-run-id=<refit run>` 读取 dedicated refit panel。
- final refit actual/effective 起点改为 `max(nominal_start, 2019-04-03)`，并在 raw metadata 记录 `effective_final_refit_min_train_start`；2021/2022/2023/2024 起点均为 `2019-04-03`，2025/2026 不受影响。
- 在 `quant_ashare.strategy1.annual_pipeline_scheduler` 中新增 `refit_panel` stage，依赖顺序改为 `select:yYYYY -> refit_panel:yYYYY -> refit:yYYYY`，continuous ledger 仍依赖六个 `refit:*`。
- 更新 PRD_02、KNOWN_CONSTRAINTS、OPEN_QUESTIONS、IMPLEMENTATION_STATUS、TODO，并追加 `DECISION-20260611-01` 记录 effective-window 口径。

### 重要上下文

- 这是 OQ-014 的工程缓解，不是 historical DWS 根因修复。若 owner 要求 true pre-2019 五年窗口，需要先修复 / 重建 DWS lookback 与历史 valuation 覆盖。
- 合并本分支后必须重建 Strategy1 runner 镜像；annual orchestrator / scheduler 的 resolved plan 由镜像内代码生成。
- 旧 official continuous 结果仍是已生成事实，但不能直接升级为 accepted baseline 或 promotion source。

### 改动文件

- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`
- `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `tests/strategy1/test_annual_pipeline_scheduler.py`
- `docs/prd/PRD_20260611_02_策略1年度滚动FinalRefit.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

### 测试 / 验证

- Focused pytest：`PYTHONPATH=src python3 -m pytest -q tests/strategy1_cloudrun/test_dataset_role_routing.py tests/strategy1/test_annual_pipeline_scheduler.py tests/strategy1/test_refit_panel_coverage_contract.py`：32 passed。
- Full pytest：`PYTHONPATH=src python3 -m pytest -q tests`：122 passed。
- Scheduler dry-run：`python3 -m quant_ashare.strategy1.annual_pipeline_scheduler --dry-run --start-year 2021 --end-year 2026 ...` 生成 97 tasks，确认 `refit_panel:y2021` 依赖 `select:y2021`、`refit:y2021` 依赖 `refit_panel:y2021`、continuous 依赖六个 refit。
- BigQuery 覆盖审计（代码修改前执行）：以 `effective_refit_start=max(nominal_start, 2019-04-03)` 对 2021-2026 六年检查 SSE 开市日 labeled sample 覆盖，missing_labeled_days 均为 0。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。

### 阻塞项

- 无代码阻塞；尚未合并、重建镜像或重跑 live annual refit / continuous。

### 下一步建议

- 提交并发 PR；合并后重建 runner 镜像，更新 jobs，并以新 plan 重跑 2021-2026 dedicated refit panel / refit / synthetic continuous。

### 已更新记忆文件

- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`
## 2026-06-11 GPT-5 Codex - Annual refit source-panel coverage review follow-up

### 已完成工作

- 基于 `origin/main@00f2265` 在干净 worktree 审计 PR #171 后 review 的两条发现。
- BigQuery 按六个 annual selection source panel 与 SSE 交易日历对账，确认 review 指出的 `2019Q1` panel 空洞成立，并发现 selection split / label-embargo 内部年末缺口。
- `src/quant_ashare/strategy1/refit_register_predict.py` 已新增 SSE 开市日覆盖检查，source panel 在 refit train window 任一开市日缺 labeled 行、或 prediction source window 任一开市日缺 panel 行都会 fail-fast。
- `sql/strategy1/qa/qa_refit_register_predict_outputs.sql` 已新增 source panel labeled train 行与 refit prediction 的逐开市日覆盖断言，不再只依赖 min/max 日期端点。
- 新增 `tests/strategy1/test_refit_panel_coverage_contract.py`，锁住 Python helper 与 SQL QA 覆盖断言。
- 新增 `OQ-014`，并在 `KNOWN_CONSTRAINTS.md` / `TODO.md` / PRD_02 post-implementation note 中写明：`2019-04-03` override 是 observed alignment，不是根因修复；OQ-014 关闭前不得把本轮结果标记 accepted baseline 或 promotion source。

### 重要上下文

- 当前 official continuous 结果是已生成并已通过旧 QA 的事实记录，但 source selection panel 并未覆盖完整 refit 训练窗口。后续 owner 需选择接受当前结果为 diagnostic/provisional，或重建 DWS/lookback / dedicated refit panel 后重跑六年 refit + continuous。
- 集中自主决策清单已写入 `IMPLEMENTATION_STATUS.md`：`2019-04-03` 起点 override、train-predict 升 `8 CPU / 32Gi`、rehearsal 后置补跑、年度 diagnostic skipped、synthetic run 跳过默认 QA/诊断并外接专用 QA。
- 失败 / 跳过门清单也已集中写入 `IMPLEMENTATION_STATUS.md`：2024 refit panel coverage failure、2025/2026 OOM、synthetic partition filter failure、`QA-CONT-6` 两轮 failure、年度 diagnostic skipped、synthetic 默认 `10/12/20` QA/诊断 skipped。

### 改动文件

- `src/quant_ashare/strategy1/refit_register_predict.py`
- `sql/strategy1/qa/qa_refit_register_predict_outputs.sql`
- `tests/strategy1/test_refit_panel_coverage_contract.py`
- `docs/prd/PRD_20260611_02_策略1年度滚动FinalRefit.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests`：122 passed。
- Focused pytest：`tests/strategy1/test_refit_panel_coverage_contract.py`、package entrypoint、catalog、SQL render 合计 37 passed。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_refit_register_predict_outputs.sql`：通过。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。

### 阻塞项

- OQ-014 需要 owner 决策；当前 PR 只补护栏和记录，不重建 DWS / panel，不重跑 annual refit 或 continuous ledger。

### 下一步建议

- 合并本 follow-up 后，优先决定 OQ-014：若要把年度结果推进 accepted baseline，需要先实现 dedicated refit panel 或 DWS/lookback 重算并重跑六年 refit + continuous。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`
## 2026-06-11 GPT-5 Codex - Annual rolling official continuous results

### 已完成工作

- PR #170 已合并到 `main`（merge commit `d105f9f`），修复 `QA-CONT-6` 跨年度误匹配；PRD_03 official continuous QA 口径进入主线。
- Official synthetic continuous 已在 `main@d0f9e4d` 后以 `--force-replace` 重跑成功：run `s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02`，model `synth_s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02`，manifest URI `gs://ashare-artifacts/models/strategy1/ml_pv_clf_v0/run_id=s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02/model_id=synth_s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02/synthetic_continuous/manifest.json`，input sha256=`bfd1e3c3e251954ae5ffa1a58102570e4c4538a92b24c9c181c7e41368877166`，resolved sha256=`2062d93544dd7c2bd12566f42da0ad3c973b5c6a63f00f4cd1c72a3a5269ba97`，prediction rows=`2643406`，insert job `f566b4dd-14b8-4419-8225-4747adcb045a`。
- Official continuous ledger 已成功：Cloud Run execution `strategy1-backtest-report-job-w5k24`，backtest `bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`，fresh start，`2021-01-04..2026-06-09`，`ledger_exec_v1_lot100`，biweekly，target holdings 20，max weight 7.5%。
- Official QA 全部通过：`qa_continuous_backtest_outputs` job `843cfc18-054a-4910-b303-61e47f82f249`；`qa_lot_aware_ledger_outputs` job `0b5ec09d-0aad-41e3-871e-67766f2a4f5c`。
- Rehearsal pre-refit continuous 已补跑（diagnostic only）：synthetic run `s1_annual_roll_synth_continuous_rehearsal_2021_2026_n20_w075_v20260610_02`，manifest URI `gs://ashare-artifacts/models/strategy1/ml_pv_clf_v0/run_id=s1_annual_roll_synth_continuous_rehearsal_2021_2026_n20_w075_v20260610_02/model_id=synth_s1_annual_roll_synth_continuous_rehearsal_2021_2026_n20_w075_v20260610_02/synthetic_continuous/manifest.json`，input sha256=`d2908798e8b07ad126ca433f798b9f5187b8d2677726d8a1e4d35ef26d4d5699`，resolved sha256=`f3ebdba79deb10a05e9ad1cf50d7a6c9353172ddef6b66b6215a677e80812410`，prediction rows=`2643406`，insert job `36465e3e-90b6-43d6-b538-350f102311ac`；continuous backtest execution `strategy1-backtest-report-job-s88hz`；QA jobs `ae56421b-e316-492e-be5b-48584c7917c5` / `3a98e8d0-5ace-4a74-8170-36ac71e68ca9`。

### 重要上下文

- Official continuous summary（正式口径，不能用年度 fresh NAV 拼接替代）：total_return=`0.5012920494620134`，compound_annual_return=`0.08110633748103813`，annual_return=`0.10393379031649487`，annual_vol=`0.2273481486583799`，sharpe=`0.4571569679798399`，compound_sharpe=`0.35674949613471857`，max_drawdown=`-0.45925758365200664`，excess_return=`0.3466780784898209`，information_ratio=`0.3510127136837824`，turnover_annual=`37.6911874509589`，total_economic_cost_cny=`16695.7950538`。
- Rehearsal pre-refit continuous summary（diagnostic only）：total_return=`0.2857702525025081`，compound_annual_return=`0.04942495234912747`，annual_return=`0.06926784540786153`，annual_vol=`0.20478557532530298`，sharpe=`0.3382457250606113`，compound_sharpe=`0.2413497741265012`，max_drawdown=`-0.3845969073500922`，excess_return=`0.13115628153031555`，information_ratio=`0.16428853419676318`，turnover_annual=`30.586732030821928`。
- Official output row counts: prediction `2643406` / NAV `1314` / ledger_state `1314` / signal_monitor `1314` / candidate `279625` / order `4822` / trade `4820` / position `21536`。
- 年度 fresh diagnostic backtest 是 Phase 3 optional，本轮未重跑；最终评价只使用 single continuous ledger。
- 本轮没有 promotion，没有 ADS 写入（除 PRD_04 已完成的 additive migration），没有删除或修改 selection run 历史数据。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- PR #170 合并前：29 passed、Dataform `--check`、retired lint、compileall、BigQuery dry-run、live continuous QA、live lot-aware QA、`git diff --check` 均通过。
- Official continuous live QA: `qa_continuous_backtest_outputs` job `843cfc18-054a-4910-b303-61e47f82f249`；`qa_lot_aware_ledger_outputs` job `0b5ec09d-0aad-41e3-871e-67766f2a4f5c`。
- Rehearsal live QA: `qa_continuous_backtest_outputs` job `ae56421b-e316-492e-be5b-48584c7917c5`；`qa_lot_aware_ledger_outputs` job `3a98e8d0-5ace-4a74-8170-36ac71e68ca9`。

### 阻塞项

- 无执行阻塞；是否基于 official continuous 结果继续做策略改进或 accepted baseline 决策，需后续 owner 决策。

### 下一步建议

- 如需推进 OQ-010 accepted baseline，基于 official continuous 结果做特征/风控/候选空间复盘；不要把本结果直接标记 accepted。
- 清理本轮临时 worktree / 本地分支前，确认本记录 PR 已合并。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
## 2026-06-11 GPT-5 Codex - PRD_03 continuous QA scope hotfix

### 已完成工作

- PR #169 已合并到 `main`（merge commit `d0f9e4d`），synthetic manifest valid window 已从原 selection registry 行解析。
- 从 `main@d0f9e4d` 以 `--force-replace` 重跑 official synthetic merge 成功：prediction rows=`2643406`，registry rows=`1`，input manifest sha256=`bfd1e3c3e251954ae5ffa1a58102570e4c4538a92b24c9c181c7e41368877166`，resolved manifest sha256=`2062d93544dd7c2bd12566f42da0ad3c973b5c6a63f00f4cd1c72a3a5269ba97`，insert job `f566b4dd-14b8-4419-8225-4747adcb045a`。
- `qa_continuous_backtest_outputs` 仍暴露 `QA-CONT-6` scope bug：SQL 把所有 target prediction date 与所有 year slice 的 valid window 交叉检查，导致 2021 official prediction 被 2022 source 的 2021 valid window 误伤。
- 当前分支 `codex/synthetic-continuous-qa-valid-scope` 已把 `QA-CONT-6` 收窄到同一 manifest year slice：`pred.predict_date` 同时满足 `m.predict_start..m.predict_end` 和 `m.valid_start..m.valid_end` 才算违规。
- 使用修正后 SQL 对 live official continuous run 执行 `qa_continuous_backtest_outputs` 已通过，job `843cfc18-054a-4910-b303-61e47f82f249`。
- `qa_lot_aware_ledger_outputs` 已再次通过，job `0b5ec09d-0aad-41e3-871e-67766f2a4f5c`。

### 重要上下文

- Official synthetic merge、single continuous ledger、continuous QA、lot-aware QA 均已实质通过；本分支合并后 PRD_03 执行层闭环。
- continuous ledger execution 仍是 `strategy1-backtest-report-job-w5k24`，窗口 `2021-01-04..2026-06-09`，fresh start，`ledger_exec_v1_lot100`。

### 改动文件

- `sql/strategy1/qa/qa_continuous_backtest_outputs.sql`
- `tests/strategy1/test_synthetic_continuous.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_synthetic_continuous.py tests/strategy1/test_strategy1_catalog.py tests/strategy1/test_sql_render.py`：29 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.sql_runner --step=qa_continuous_backtest_outputs --output-dataset-role=research --params-json-b64=<official continuous QA params> --dry-run`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.sql_runner --step=qa_continuous_backtest_outputs --output-dataset-role=research --params-json-b64=<official continuous QA params>`：通过，job `843cfc18-054a-4910-b303-61e47f82f249`。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.sql_runner --step=qa_lot_aware_ledger_outputs --output-dataset-role=research --params-json-b64=<official lot-aware QA params>`：通过，job `0b5ec09d-0aad-41e3-871e-67766f2a4f5c`。
- `git diff --check`：通过。

### 阻塞项

- 无；本分支合并后可查询 continuous summary 指标并解释结果。

### 下一步建议

- 合并 `codex/synthetic-continuous-qa-valid-scope`。
- 查询 `research_backtest_performance_summary` / NAV / trade / position 行数，给出 single continuous ledger 指标。
- 更新最终运维记录后清理临时 worktree / 分支。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
## 2026-06-11 GPT-5 Codex - PRD_03 synthetic continuous valid-window hotfix

### 已完成工作

- PR #168 已合并到 `main`（merge commit `41ef1cf`），修复 official synthetic merge 首次失败的 source prediction partition filter 缺口。
- 从 `main@41ef1cf` 以 `--force-replace` 重跑 official synthetic merge 成功：synthetic run `s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02`，prediction rows=`2643406`，registry rows=`1`，input manifest sha256=`bfd1e3c3e251954ae5ffa1a58102570e4c4538a92b24c9c181c7e41368877166`，resolved manifest sha256=`0be2815342ab53543dbeee84918a3723433c3cc772502677c2a7a4ec24066ef6`，insert job `f8953afd-b95b-4b20-82f7-2af153bed998`。
- 跑 single continuous ledger 成功：Cloud Run execution `strategy1-backtest-report-job-w5k24`，backtest id `bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`，窗口 `2021-01-04..2026-06-09`，fresh start，`ledger_exec_v1_lot100`，skip diagnosis / tail-risk / default QA。
- `qa_lot_aware_ledger_outputs` 已通过，job `4dcfd716-6cea-4efd-b1f9-d7f195d1f004`。
- `qa_continuous_backtest_outputs` 暴露第二个契约缺口：`QA-CONT-6` valid 排除断言失败，因为 resolved manifest 从 refit registry 行的 `valid_start_date` / `valid_end_date` 取值，而 refit registry 中这两个字段等于 refit train window；正确 selection valid window 需要从 refit row 的 `model_params_json.source_run_id` 指向的原 selection registry 行读取。
- 当前分支 `codex/synthetic-continuous-valid-windows` 已实现修复：refit source 通过 source selection registry 解析 valid window，manifest 显式 `valid_start/end` 可覆盖，并补单测覆盖。

### 重要上下文

- continuous ledger 本体已生成且 lot-aware QA 通过，但 official 指标仍需等 synthetic manifest valid-window 修复后重跑 synthetic merge，并让 `qa_continuous_backtest_outputs` 通过。
- `qa_continuous_backtest_outputs` 是当前唯一未通过的 PRD_03 硬门；不要把年度 fresh NAV 或未过 continuous QA 的结果当正式结论。

### 改动文件

- `src/quant_ashare/strategy1/synthetic_continuous.py`
- `tests/strategy1/test_synthetic_continuous.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_synthetic_continuous.py tests/strategy1/test_strategy1_catalog.py tests/strategy1/test_sql_render.py`：28 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `git diff --check`：通过。

### 阻塞项

- 需合并 `codex/synthetic-continuous-valid-windows` 后，以 `--force-replace` 重跑 official synthetic merge，再跑 `qa_continuous_backtest_outputs`。

### 下一步建议

- 提交并合并 valid-window hotfix PR。
- 重跑 synthetic merge；如 prediction stream 内容不变，可不重跑 continuous ledger，但必须重跑 `qa_continuous_backtest_outputs` 与结果复核。
- 若 `qa_continuous_backtest_outputs` 通过，再查询并记录 continuous summary 指标。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
## 2026-06-11 GPT-5 Codex - PRD_03 synthetic continuous partition filter hotfix

### 已完成工作

- PR #167 合并后，从 `main@c72cd8f` 执行 official synthetic merge，首次 BigQuery prediction insert 暴露 partition filter 缺口：source `research_model_prediction_daily` join 只有 manifest 动态窗口，缺少静态 `predict_date` 过滤，BigQuery job `cde0ff0e-fe0a-4124-89d1-c5406a8c5caa` 失败。
- 当前分支 `codex/synthetic-continuous-partition-filter` 已补 synthetic prediction insert 的整体 `predict_date` 静态窗口过滤，并同步补 `qa_continuous_backtest_outputs` source count 的 `p_predict_start` / `p_predict_end` 分区过滤。
- `TODO.md` 与 `IMPLEMENTATION_STATUS.md` 已更新为“PR #167 代码已合并，但 official synthetic merge 需 hotfix 合并后 `--force-replace` 重跑”的状态。

### 重要上下文

- 首次 official merge 已可能写入 synthetic registry partial row，但 prediction insert 未完成；hotfix 合并后必须用 `--force-replace` 重跑，避免 partial registry 干扰。
- Official continuous 结果仍未产生；禁止把年度 fresh NAV 拼成正式结果。

### 改动文件

- `src/quant_ashare/strategy1/synthetic_continuous.py`
- `sql/strategy1/qa/qa_continuous_backtest_outputs.sql`
- `tests/strategy1/test_synthetic_continuous.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_synthetic_continuous.py tests/strategy1/test_strategy1_catalog.py tests/strategy1/test_sql_render.py`：25 passed。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.sql_runner --step=qa_continuous_backtest_outputs --output-dataset-role=research --params-json-b64=<official continuous QA params> --dry-run`：BigQuery dry-run 通过。
- `git diff --check`：通过。

### 阻塞项

- 需合并 hotfix 后再继续 official synthetic merge / continuous ledger。

### 下一步建议

- 提交并合并 `codex/synthetic-continuous-partition-filter`。
- 从最新 main 以 `--force-replace` 重跑 official synthetic merge。
- 跑 single continuous backtest，再执行 `qa_continuous_backtest_outputs` 与 `qa_lot_aware_ledger_outputs`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
## 2026-06-11 GPT-5 Codex - PRD_03 synthetic continuous implementation

### 已完成工作

- 新增 package entrypoint `quant_ashare.strategy1.synthetic_continuous`，按 manifest 合并逐年 refit prediction slice，生成 synthetic selected registry 行和统一 `model_id` / `run_id` 的 prediction stream；默认只允许写 `ashare_research`，ADS 发布仍走 promotion。
- 新增 `sql/strategy1/qa/qa_continuous_backtest_outputs.sql` 并登记 catalog，覆盖 synthetic manifest hash、year slice 溯源、source/target prediction 行数、valid 段排除、交易日历覆盖、continuous summary / NAV / position / trade / ledger state 不变式。
- 更新 `docs/策略1CloudRun训练回测运行手册.md`，补 official synthetic merge、continuous backtest skip flags 和外接 QA 执行口径。
- 扩展 package entrypoint / catalog / SQL render / package boundary 测试，锁住新入口和 QA step。
- PR #166 合并后已从 `main@7b2bd67` 构建部署 hotfix 镜像 `sha256:e379fdccb49281ec628f389de261929d37e60906b51538132b350314ba8db9da`，五个 jobs 读回确认新 digest；`strategy1-train-predict-job` 资源已更新为 `8 CPU / 32Gi`。
- 使用 hotfix plan 重跑 2024/2025/2026 refit 成功：`strategy1-train-predict-job-5s49j`（约 7m20s）、`strategy1-train-predict-job-mx272`（约 9m50s）、`strategy1-train-predict-job-d6g52`（约 10m10s）。六年 refit registry 均为 1 行 selected，prediction 覆盖各年窗口。
- 六年 `qa_refit_register_predict_outputs` 均通过，job ids：`c6bcbf46-ec47-4917-a0a4-e67fbc467997`、`4f75fb48-52ce-4f1b-a270-e555b1358e3e`、`e90a2a1e-0802-4013-9356-e0544304e21d`、`4216cc23-3b09-4001-9291-d93380c44d40`、`04e923a0-e59c-4bfa-a333-2a6a806213e7`、`4e9d241f-7cf3-4def-bee0-0077f6b44d41`。

### 重要上下文

- `PRD_20260611_02` 的 final refit 执行与 QA 已完成；2021-2026 official 评价的剩余硬门是 PRD_03 synthetic continuous merge + single continuous ledger。
- `qa_continuous_backtest_outputs` 是 synthetic run 专用 QA；`10` / `12` / `20` 默认 QA/诊断不适用于无 training panel / 无真实 model artifact 的 synthetic run。continuous backtest 必须用 `--skip-diagnosis --skip-tail-risk --skip-qa`，再外接 `qa_continuous_backtest_outputs` 与 `qa_lot_aware_ledger_outputs`。
- 主工作树仍有 unrelated `scripts/strategy1_cloudrun/bq_io.py` 本地脏改，不属于本 PRD_03 分支，后续构建镜像必须继续使用干净 worktree。

### 改动文件

- `src/quant_ashare/strategy1/synthetic_continuous.py`
- `sql/strategy1/qa/qa_continuous_backtest_outputs.sql`
- `configs/strategy1/active_step_catalog.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `tests/strategy1/test_synthetic_continuous.py`
- `tests/strategy1/test_cloudrun_package_entrypoints.py`
- `tests/strategy1/test_package_boundaries.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests`：115 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `npx --yes @dataform/cli compile dataform`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。
- `python3 -m quant_ashare.strategy1.sql_runner --step=qa_continuous_backtest_outputs --output-dataset-role=research --dry-run`：BigQuery dry-run 通过。

### 阻塞项

- 无代码阻塞；official continuous ledger 尚未执行，需先合并 PRD_03 code PR。

### 下一步建议

- 提交 PRD_03 代码 PR，review / merge。
- 从合并后的 main 生成 official manifest，执行 `quant_ashare.strategy1.synthetic_continuous --require-source-refit` 写 synthetic run。
- 用 `strategy1-backtest-report-job` 跑 official continuous backtest（skip diagnosis/tail-risk/default QA），再执行 `qa_continuous_backtest_outputs` 与 `qa_lot_aware_ledger_outputs`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`
## 2026-06-11 GPT-5 Codex - PRD_02 deployment and refit hotfix

### 已完成工作

- 合并 PR #165 到 `main`，merge commit `ebb6dbf`。
- 从 `main@ebb6dbf` 构建固定 tag 镜像 `strategy1-cloudrun-runner:final-refit-main-ebb6dbf-20260611-01`，Cloud Build `8dcd4d62-a61d-459a-aeb8-86fc69a76313` succeeded，digest `sha256:fc94a02d388e0a988dac56366ea0dcba80e65c15dea10efc93ef38e11778b757`。
- 五个正式 Strategy1 jobs 已更新到该 digest；读回确认 package args、SA、maxRetries、资源和 fanout `taskCount=40 / parallelism=20` 保持预期。
- Boot smoke：`strategy1-train-predict-job-nmnkn`、`strategy1-prepare-matrix-job-bhpwm`、`strategy1-train-candidate-fanout-job-rrz6h`、`strategy1-select-register-predict-job-vfkzx`、`strategy1-backtest-report-job-ncn69`、`strategy1-train-predict-job-2kk7c`（`refit_register_predict --help` override）全部 Completed=True，Cloud Logging 均匹配到 `usage:`。
- 生成 `/tmp/strategy1_annual_refit_plan_v20260610_02.json` 并做 BigQuery preflight；六年 source selected registry / panel / target empty checks 通过。
- 启动 2021-2026 refit：2021、2022、2023 成功；2024 因 panel min date 晚于 resolved start 失败；2025、2026 因 train-predict job 16Gi memory limit 失败。
- 新建 hotfix worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-final-refit-hotfix`，分支 `codex/strategy1-final-refit-hotfix`，修复 2024+ 暴露的问题：2019 final-refit start override 为 `2019-04-03`，scheduler/runbook refit resource token 改为 `8 CPU / 32Gi`。

### 重要上下文

- 2021-2023 refit outputs 已实际写入 research；不要用 `--force-replace` 重跑它们，除非 owner 明确要求。
- 2024 失败发生在 coverage guard 之前，没有写出 refit registry/prediction；2025/2026 因内存限制失败，也需在重跑前复核目标 refit rows。
- Hotfix 合并后必须重建镜像，并把至少 `strategy1-train-predict-job` 更新到 `8 CPU / 32Gi` 后再重跑 2024-2026。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`
- `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`
- `docs/策略1CloudRun训练回测运行手册.md`
- `tests/strategy1/test_annual_pipeline_scheduler.py`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`

### 测试 / 验证

- Hotfix focused pytest：`tests/strategy1_cloudrun/test_dataset_role_routing.py::test_annual_year_plan_continuous_contract_uses_refit_run_id` 与 `tests/strategy1/test_annual_pipeline_scheduler.py::test_scheduler_plan_select_depends_on_all_candidates_and_cross_year_is_independent` 通过。
- Hotfix 2024 annual dry-run 确认 `final_refit.train_start='2019-04-03'`。
- 完整验证待 hotfix 提交前执行。

### 阻塞项

- 无代码阻塞；需完成 hotfix PR / merge / redeploy 后才能重跑 2024-2026。

### 下一步建议

- 完成 hotfix 全量验证、提交 PR、合并并部署新镜像。
- 更新 `strategy1-train-predict-job` 至 `8 CPU / 32Gi` 后重跑 2024、2025、2026 refit，并执行 `qa_refit_register_predict_outputs`。
- PRD_03 synthetic continuous merge / official continuous ledger 仍待实现，不能拼接年度 NAV。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
## 2026-06-11 GPT-5 Codex - PRD_02 annual rolling final refit implementation

### 已完成工作

- 新增 package entrypoint `src/quant_ashare/strategy1/refit_register_predict.py`，实现年度滚动 selected candidate final refit：读 selection registry、读 `source_panel_run_id` 面板、重新 fit preprocessor、训练单模型、写 refit registry / prediction / artifact。
- 扩展 `train_predict.write_registry` 的 `model_params_json` lineage 白名单，写出 `source_panel_run_id`、`refit`、`refit_train_start/end`、`preprocess_fit_start/end`。
- 新增 `sql/strategy1/qa/qa_refit_register_predict_outputs.sql` 并登记 `configs/strategy1/active_step_catalog.yml`，覆盖 refit 硬门 QA。
- 更新 `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`：每年 plan 插入 `cloudrun_refit_register_predict`，root / yearly continuous metadata 指向 refit prediction run，年度 diagnostic backtest 指向 `__refit01` backtest。
- 更新 `quant_ashare.strategy1.annual_pipeline_scheduler`：新增 `refit` stage，continuous 依赖改为 refit runs。
- 更新 runbook 与测试，覆盖 package entrypoint、annual command plan、scheduler DAG 和 catalog/package boundary。

### 重要上下文

- 本轮只完成代码侧实现，不部署镜像、不执行 Cloud Run、不写 BigQuery research/ADS 产物；六年 refit 重跑仍待合并后用新镜像执行。
- refit 当前复用现有 `strategy1-train-predict-job`，资源 token 记录为 `4 CPU / 16Gi`；这是比 PRD 建议 `2 CPU / 8Gi` 更保守的现有 job envelope，不新增 job spec。
- 年度 diagnostic backtest 仍只作 diagnostic，正式结果必须等 PRD_03 synthetic continuous merge + single continuous ledger。

### 改动文件

- `src/quant_ashare/strategy1/refit_register_predict.py`
- `src/quant_ashare/strategy1/train_predict.py`
- `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`
- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`
- `sql/strategy1/qa/qa_refit_register_predict_outputs.sql`
- `configs/strategy1/active_step_catalog.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `tests/strategy1/test_annual_pipeline_scheduler.py`
- `tests/strategy1/test_cloudrun_package_entrypoints.py`
- `tests/strategy1/test_package_boundaries.py`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests`：108 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_refit_register_predict_outputs.sql`：通过。
- annual orchestrator / scheduler dry-run 复核：plan 顺序包含 `cloudrun_refit_register_predict`，scheduler `continuous_ledger` 依赖 `refit:*`。

### 阻塞项

- 无代码侧阻塞；上线前仍需 PR 合并后重建 Strategy1 runner 镜像。

### 下一步建议

- 合并 PRD_02 代码 PR 后，重建并部署五个 Strategy1 runner jobs 镜像，至少做 refit entrypoint boot smoke。
- 继续实现 PRD_03 synthetic continuous merge / QA；PRD_02 refit 六年重跑完成后再跑正式 continuous ledger。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
## 2026-06-11 GPT-5 Codex - PRD_04 research summary identity implementation and live backfill

### 已完成工作

- 合并 PR #162 到 `main`，并确认 `PRD_20260611_02/03/04` 三个文件已在 `origin/main@ce795e5`。
- 清理已合并的旧 PRD worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-refit-prds`，删除本地和远端 `claude/prd-refit-continuous-summary` 分支。
- 新建工作树 `/Users/fisher/Desktop/git/worktrees/quant-ashare-prd04-summary-fix`，分支 `codex/prd04-research-summary-fix`。
- PR #163 已自审并合并到 `main`，merge commit `f0ba555`。
- 新增 ADS additive migration `sql/ads/04_alter_strategy1_backtest_summary_identity_columns.sql`，为 `ads_backtest_performance_summary` 补 `run_id STRING` 与 `created_date DATE`。
- 修复 `sql/strategy1/reporting/build_metrics_and_report_inputs.sql`：summary INSERT 列清单与 SELECT 显式写入 `run_id=p_run_id`、`created_date=CURRENT_DATE()`。
- 修复 `sql/strategy1/qa/qa_runner_outputs.sql`：新增 summary row 的 `run_id=p_run_id` 与 `created_date IS NOT NULL` 断言。
- 修复 `sql/strategy1/qa/qa_cloudrun_schema_readiness.sql`：ADS summary required columns 增加 `run_id` / `created_date`，失败信息指向新 migration。
- 新增 `tests/strategy1/test_backtest_summary_identity_contract.py`，防止上述契约漂移。
- 已执行 live ADS migration，并复跑 `qa_cloudrun_schema_readiness` 通过。
- 已回填 6 条 annual rolling research summary 行：`run_id=metrics_json.prediction_run_id`，`created_date=DATE(created_at)`，affected rows=6。

### 重要上下文

- catalog 的 `backtest_summary.partition_columns=[created_date]` 继续代表 research 表语义；本轮不把 ADS summary 改成分区表，避免扩大 migration 面。
- Phase 1 ADS 写入例外只限 additive migration；普通 runner / 后续重跑仍必须默认 research-first。
- PRD_04 已不再阻塞后续 refit / continuous，但后续新 summary 行依赖已合并的 `09` 修复和新镜像部署；PRD_02/03 实现合并后仍需重建 Strategy1 runner 镜像。

### 改动文件

- `sql/ads/04_alter_strategy1_backtest_summary_identity_columns.sql`
- `sql/strategy1/reporting/build_metrics_and_report_inputs.sql`
- `sql/strategy1/qa/qa_runner_outputs.sql`
- `sql/strategy1/qa/qa_cloudrun_schema_readiness.sql`
- `tests/strategy1/test_backtest_summary_identity_contract.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests`：105 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ads/04_alter_strategy1_backtest_summary_identity_columns.sql`：通过。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。
- Live migration：两条 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 均完成。
- Live readiness：`qa_cloudrun_schema_readiness` 4 条 assertion 全部 successful。
- Live backfill：annual target rows=6，UPDATE affected rows=6；复核 `null_run_id=0`、`null_created_date=0`、`run_id_mismatch=0`、`created_date_mismatch=0`，`created_date=2026-06-10` 过滤查到 6 行；time-travel hash 对比确认排除 `run_id`/`created_date` 后非目标字段无变化。

### 阻塞项

- 无。

### 下一步建议

- 进入 PRD_02 final refit 与 PRD_03 synthetic continuous 实现；两者可按任务要求分独立 PR 推进。
- 任何重跑前仍需确认五个 Strategy1 jobs 镜像包含最新 main 代码；PRD_02/03 合并后必须重建并部署 runner 镜像。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

> 当前交接补充（2026-06-11，Claude Fable 5）
> - 分支 `claude/prd-refit-continuous-summary` 新增三个 PRD，收口 2021-2026 首轮年度滚动实跑暴露的三类问题：`PRD_20260611_02`（final refit 方法论修正）、`PRD_20260611_03`（synthetic continuous prediction + 正式 continuous ledger）、`PRD_20260611_04`（research summary `created_date`/`run_id` 落库修复，简短）。
> - 关键依赖关系已写入 PRD：04 的修复必须先于任何重跑；02 与 03 的代码实现可并行（03 的 merge 输入参数化为 manifest，彩排用 pre-refit 预测），只有 03 的正式执行依赖 02 的六年 refit 重跑。
> - 04 的根因已实证：`09` SQL summary INSERT 列清单不含 `run_id`/`created_date`（ADS 表本无这两列，research 表是 D0 新增），research 渲染只重写表名不重写列清单 → 未列出且无 DEFAULT 的列写 NULL。
> - 本轮 docs/记忆-only：不改代码、不执行 BigQuery / Cloud Run。当前 6 年年度结果（含 2025 +53.32%）仍只是 diagnostic，final refit 修正前不得解读指标。
> - PR #162 review 三条 follow-up 已全部采纳修正：①（实证确认 `prepare_matrix` 在 selection train 上 fit preprocessor、matrix 冻结 transformed arrays）PRD_02 复用层级从 matrix 改为 panel，refit 必须重新 fit preprocessor，新增 preprocessing 契约与 QA；② PRD_03 新增 synthetic registry 契约（单 selected synthetic model、prediction model_id 统一改写、逐年溯源入 manifest + `year_model_map`）与专用 `qa_continuous_backtest_outputs` QA 套件，保住下游"每 run 单 selected"不变式；③ PRD_04 扩展 `qa_cloudrun_schema_readiness` 覆盖 ADS summary 新增两列，preflight 拦截漏跑 migration。

Model: Claude Fable 5
## 2026-06-11 Claude Fable 5 - 年度滚动 refit / continuous / summary 三 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260611_02_策略1年度滚动FinalRefit.md`：refit 窗口口径（resolved plan `final_refit` 块为权威）、初稿复用 BigQuery panel / 重新 fit preprocessor / 不消费冻结 matrix transformed arrays、`refit_register_predict` 步骤、独立 refit run_id 的 registry 溯源契约、QA 硬门（训练窗口逐年断言）。注：该初稿 panel 复用口径已被 2026-06-11 coverage revision 替代，当前权威方案为 dedicated refit panel + effective coverage floor。
- 新增 `docs/prd/PRD_20260611_03_策略1SyntheticContinuous正式回测.md`：manifest 参数化 merge（彩排/正式同代码）、逐年 test 窗口切片排除 valid 段、重叠/缺口/行数/溯源 QA、official continuous ledger 口径、rehearsal 与 official 的强制区分。
- 新增 `docs/prd/PRD_20260611_04_ResearchSummary落库修复.md`（简短）：根因实证、ADS additive 补列 + `09` 列清单修复 + 6 行回填（需 owner 批准）+ `qa_runner_outputs` NOT NULL 断言。
- 同步 `IMPLEMENTATION_STATUS.md`、`AGENT_HANDOFF.md`、`TODO.md`。

### 重要上下文

- 实跑暴露的其余问题不另开 PRD：`gcloud --wait` 误报与控制面滞后是 `PRD_20260611_01` §8.1 既定 Phase 2 要求（本次为实证）；慢候选长尾归 scheduler PRD P1；registry 11 行需筛 `status='selected'` 拟作为约定写入 KNOWN_CONSTRAINTS（随实现 PR 落，本轮不动约束文件）。
- 执行顺序：04 修复 PR → 02/03 并行实现（03 彩排可先行）→ 02 六年 refit 重跑 → 03 正式 merge + continuous ledger。

### 改动文件

- `docs/prd/PRD_20260611_02_策略1年度滚动FinalRefit.md`
- `docs/prd/PRD_20260611_03_策略1SyntheticContinuous正式回测.md`
- `docs/prd/PRD_20260611_04_ResearchSummary落库修复.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 文档与记忆更新；未运行 pytest / BigQuery / Cloud Run。`git diff --check` 通过。

### 阻塞项

- 无。三个 PRD 均待 owner review。

### 下一步建议

- owner review 三个 PRD 后，先实现 `PRD_20260611_04` 的修复 PR（成本最低且阻塞重跑）。
- `PRD_20260611_03` 的 merge/QA 实现与彩排可与 `PRD_20260611_02` 并行启动。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

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

## 2026-06-12 PR #201 pre-merge rebase archived handoff entries

## 2026-06-12 GPT-5.5 - PR #199 确认轮复核与微修

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-ca-decision`
模型: GPT-5.5
运行环境: macOS / zsh / branch `claude/decision-ca-baseline`
Run ID: N/A
相关 issue/PR: PR #199

### 已完成工作

- 按 owner 要求拉取 Claude 裁决回帖并同步 `claude/decision-ca-baseline` 到 commit `1fa12c4`。
- 逐条复核 5 条 review 发现：tail_risk_overlay_ab 显式 CA-on、KNOWN_CONSTRAINTS 去重/拆黏、AGENT_HANDOFF 完整条目已到位；复核时发现 resolver 真实记忆解析仍回落 CA-off，且 TODO 仍残留旧 true-five-year baseline open 项。
- 直接微修 resolver：`find_baseline_ids()` 允许从最高优先级 CA-on baseline 段落取 backtest，再从后续最佳 baseline 段补 prediction；新增 fixture 覆盖“DECISION-20260612-03 只有 CA-on backtest、DECISION-20260612-02 同时有 prediction+CA-off backtest”的真实记忆形态。
- 删除 `TODO.md` 残留旧 true-five-year baseline open 路线项，保留已纳入 CA-on 的当前 OQ-010 路线项。

### 重要上下文

- 本轮未改 ledger 默认值：`corporate_actions` 代码默认仍为 `none_v1`；只在实验编排/解析纪律上保证 CA-on。
- 未执行 live / BigQuery 写入，未 promotion，未改默认 profile。

### 改动文件

- `scripts/strategy1/analyze_topdown_lot_phase0.py`
- `tests/strategy1/test_topdown_lot_phase0.py`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_topdown_lot_phase0.py`：9 passed。
- 真实项目记忆解析实测返回 `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01` / `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01`。
- `PYTHONPATH=src python3 -m pytest -q tests`：201 passed。
- `python3 -m compileall -q src scripts tests`：passed。
- `git diff --check`：passed。

### 阻塞项

- 无。

### 下一步建议

- 提交、push，并在 PR #199 comment 给出确认轮结论。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-12 Claude Fable 5 - 六 PR 合并队列 + DECISION-20260612-03 CA-on baseline 落地（PR #199）

日期: 2026-06-12
Agent ID: Claude Code
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-ca-decision`
模型: Claude Fable 5
运行环境: macOS / zsh / branch `claude/decision-ca-baseline`
Run ID: 无（决策落地与记忆同步，未跑新 run）
相关 issue/PR: PR #199；已合并 #192、#190、#194、#195、#198、#189

### 已完成工作

- 按 owner 指令完成六 PR 合并队列（#192→#190→#194→#195→#198→#189）；#189 与 CA 链路的集成冲突以 union 方式收口：`ledger.py` 常量/参数/hash/校验合并、`active_step_catalog.yml` required_params 合一、删除过时 QA 断言与 reporting 重复 dict key、重建被黏连的测试函数，合并后全量 pytest 200 passed。
- 新建 PR #199 落地 DECISION-20260612-03：研究 baseline 数字切换为 CA-on 口径（`bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01`，CAGR `15.35%`/contract Sharpe `0.6682`/Calmar `0.4101`），supersede v1 ledger"未复权口径、持有期除权简化"约定，后续实验一律显式 `corporate_actions=cash_div_and_split_v1` / `dividend_tax_mode=flat_10pct`（代码默认 `none_v1` 不变）。
- 同步记忆与 TODO：DECISION_LOG 追加 -03；KNOWN_CONSTRAINTS / IMPLEMENTATION_STATUS / MEMORY_INDEX 刷新 baseline 锚点；TODO 勾掉已裁决三项并删除重复旧路线项。
- 按 Codex review（GPT-5.5 xhigh，5 条发现全采纳）修复：`analyze_topdown_lot_phase0.py` resolver 支持 `_ca01` id 形状且 baseline 段落优先级从硬编码 -02 改为"最新 DECISION id 优先"；`tail_risk_overlay_ab.py` 编排层显式 CA-on；KNOWN_CONSTRAINTS 去重并拆开与 IAM 黏连行；TODO 三处过时待定项收口；本 handoff 条目补全。

### 重要上下文

- v3 gates 仍未过：contract Sharpe 距 0.70 门 `0.032`、Calmar `0.4101 < 1.0`——baseline ≠ accepted，不得 promotion；剩余缺口判定为真实 alpha/结构问题（OQ-010 唯一开放主线）。
- 同日并行会话撞号（DECISION/PRD 编号）教训已固化进 CLAUDE.md 操作要点：创建前 fetch 并实查 origin/main 最新编号，撞号时未合并方让号并连锁更新字面引用。
- Codex review 会话续接纪律：同一 PR 复用同一会话（`codex exec resume`），review 结论与逐条裁决都落 PR comment。

### 改动文件

- `.agent/memory/DECISION_LOG.md`、`KNOWN_CONSTRAINTS.md`、`IMPLEMENTATION_STATUS.md`、`MEMORY_INDEX.md`、`AGENT_HANDOFF.md`、`TODO.md`
- `scripts/strategy1/analyze_topdown_lot_phase0.py`、`tests/strategy1/test_topdown_lot_phase0.py`、`src/quant_ashare/strategy1/tail_risk_overlay_ab.py`

### 后续

- PR #199：回帖逐条裁决 → Codex 确认轮 → 合并（先 `gh pr ready`）。
- 合并后：PRD_20260611_10 Phase 2 重跑与 P1 市值规则两选项 paper batch 仍是 OQ-010 下的 owner 路线项。

Model: Claude Fable 5

## 2026-06-12 GPT-5.5 - PRD_03 记忆体系归档压缩实现

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-prd03`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/prd03-memory-archive`
Run ID: N/A
相关 issue/PR: PRD_20260612_03；PR #201

### 已完成工作

- 按 PRD_20260612_03 将主记忆文件改为滚动压缩结构：`IMPLEMENTATION_STATUS.md` 快照 + 最近 7 条补充，`AGENT_HANDOFF.md` 当前摘要 + 最近 3 条交接，`DECISION_LOG.md` 全量索引 + 最近 10 条全文。
- 将移出的实现状态编年史与决策全文原文归档到 `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`、`DECISION_LOG_2026-05.md`、`DECISION_LOG_2026-06.md`；旧 handoff 按滚动规则继续归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。
- 保守重构 `KNOWN_CONSTRAINTS.md`：只对超长条款做拆行重排，未删除操作性语义；全量映射附件已生成。
- 更新 `PROJECT_CONTEXT.md` 当前阶段、`UPDATE_PROTOCOL.md` 滚动瘦身规则、`MEMORY_INDEX.md` archive 登记。
- PR #201 Claude review F1-F5 已全采纳修复：`DECISION-20260608-10..18/-21/-22/-23/-25/-26` 索引改回 `2026-06-08 / active`，`-02/-04/-19` 保留 unknown 并注明归档原文无 Date / Status；`IMPLEMENTATION_STATUS.md` 最近 7 条改按小节日期重切；`UPDATE_PROTOCOL.md` 补日期口径和已归档全文不改写边界；PRD_10 的 5 条 Phase 1 bullet 已归回对应小节；映射表补充拆分行核对说明。

### 重要上下文

- `DECISION_LOG.md` 主文件仍可 grep 命中全部 `DECISION-YYYYMMDD-NN`，并指向归档全文。
- `IMPLEMENTATION_STATUS.md` 与 `DECISION_LOG.md` 主文件保留 CA-on baseline 段落；`tests/strategy1/test_topdown_lot_phase0.py` 的 resolver 不应因本次重排失效。本轮已实测真实记忆解析仍返回 CA-on backtest。
- 本轮不产生新的持久决策，不更新 `DECISION_LOG.md` 决策条目，不改 `TODO.md` 实质内容。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/UPDATE_PROTOCOL.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/archive/*`
- `docs/prd/PRD_20260612_03_KNOWN_CONSTRAINTS映射表.md`

### 测试 / 验证

- DECISION id 集合对账：before=`99`、after main=`99`、missing=`0`、extra=`0`。
- `IMPLEMENTATION_STATUS.md` 编年史小节对账：before=`73`、after main=`7`、archive=`66`、total=`73`，heading multiset match=`True`，nonblank body line multiset match=`True`。
- PRD_10 / PR #189 小节边界对账：PRD_10 moved bullets=`5`，PR #189 bullets=`4`，正文非空行集合未变化。
- 决策全文归档按 ID 对账：before=`99`、archive=`99`、missing=`0`、extra=`0`、text_mismatches=`0`。
- Handoff 归档存在性对账：原主文件 33 条，移出 31 条，archive missing=`0`。
- 最终发布前已 rebase `origin/main`；期间新增 main 提交为 PRD 文档合入，未新增 `.agent/memory` 条目，无需追加归档处置。
- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_topdown_lot_phase0.py`：9 passed。
- 真实项目记忆解析实测返回 CA-on baseline：`s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01` / `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01`。
- `PYTHONPATH=src python3 -m pytest -q tests`：201 passed。
- `git diff --check`：passed。

### 阻塞项

- 无。

### 下一步建议

- 等待 Claude review；认可的 comment 继续在本分支修复，不认可的在 PR comment 说明理由。合并前如 `origin/main` 再变化，按 PRD §6 rebase 并重新跑对账。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/UPDATE_PROTOCOL.md`
- `.agent/memory/MEMORY_INDEX.md`

## 2026-06-12 GPT-5.5 - PRD_04 工程护栏与测试补强实现

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-prd04`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/prd04-guardrails`
Run ID: N/A
相关 issue/PR: PRD `docs/prd/PRD_20260612_04_工程护栏与测试补强.md`；PR #200 为 PRD 定稿来源

### 已完成工作

- §2.1：`qa_corporate_action_ledger_outputs` 增加 CA-on dividend staleness fail-fast 断言；`sql/README.md` 补 dwd/12、qa/14 与 ledger QA 的完整恢复路径；catalog 声明 `v_dwd_stock_dividend_event_ledger_consumable` 输入；`KNOWN_CONSTRAINTS.md` 增加过渡政策。
- §2.2：补齐 `qa_topdown_construction_outputs` / `qa_corporate_action_ledger_outputs` 的 active step catalog 必填键，并让 `validate_catalog()` 对非 retired step 强制校验。
- §2.3：新增 AST-based metric definition freeze pytest 与显式 allowlist；`DOC_CONVENTIONS.md` 增加指标/格式函数不得在新脚本本地重定义的规则。
- §2.4：新增 11 对 canonical/window SQL 文本同构 guard，包含显式归一化映射、无扩大豁免清单、seeded mutation 负向自检。
- §2.5：新增 `experiment_resolution.py` 统一四入口 resolver；`train_predict` resolved manifest 分支保持旧语义，`backtest_report/reporting --manifest-resolved` 改为显式 fail-fast，并补兼容测试与当前 command builder 扫描。
- §2.6：只新增 acceptance / selection / train_predict 纯函数表驱动测试；未改生产逻辑。
- §2.7：`tests/conftest.py` 插入 repo root + `src`，新增 `run_module` fixture；`pyproject.toml` 增加 pytest `testpaths` / `pythonpath`；替换 5+ 处重复 subprocess/PYTHONPATH scaffold。

### 重要上下文

- 本轮没有改回测、训练、组合或 ledger 默认语义；`corporate_actions='none_v1'` 默认不变。
- 未触碰 Cloud Run job spec、镜像或 IAM；除 BigQuery dry-run 外未执行 BigQuery 写入。
- reporting 的 `--manifest-resolved` 选择 fail-fast，理由是该入口原先静默忽略 resolved manifest，且当前 orchestrator/backtest command builder 不下发该参数；若未来要支持，应单独定义完整语义与测试。

### 改动文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`、`.agent/memory/DOC_CONVENTIONS.md`、`.agent/memory/IMPLEMENTATION_STATUS.md`、`.agent/memory/AGENT_HANDOFF.md`、`TODO.md`
- `configs/strategy1/active_step_catalog.yml`
- `sql/strategy1/qa/qa_corporate_action_ledger_outputs.sql`、`sql/README.md`
- `src/quant_ashare/strategy1/catalog.py`、`experiment_resolution.py`、`train_predict.py`、`prepare_matrix.py`、`select_register_predict.py`、`reporting.py`
- `tests/conftest.py`、`pyproject.toml`、相关 Strategy1/warehouse 测试

### 测试 / 验证

- `python3 -m pytest -q tests`：243 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：passed。
- `git diff --check`：passed。
- `cd /tmp && python3 -m pytest /Users/fisher/Desktop/git/worktrees/quant-ashare-prd04/tests --collect-only -q`：243 collected。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_corporate_action_ledger_outputs.sql`：Query successfully validated。

### 阻塞项

- 无。

### 下一步建议

- 提交第七个 commit 后 push `codex/prd04-guardrails`，创建 base `main` 的实现 PR。
- PR 创建后在 PR #200 回帖一行：`PRD_04 实现 PR #<number>`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DOC_CONVENTIONS.md`
- `TODO.md`

## 2026-06-12 GPT-5.5 - PR #202 review follow-up

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-prd04`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/prd04-guardrails`
Run ID: N/A
相关 issue/PR: PR #202；review comment `4692136310`

### 已完成工作

- F2：`qa_corporate_action_ledger_outputs` 的 dividend staleness watermark 改为读取 full-table 可见上界，上限使用 `CURRENT_DATE('Asia/Shanghai')`，不再被 `p_predict_end` 截断。
- F3：`experiment_resolution.resolve_experiment_from_args()` 恢复 `experiment_json` 最高优先级；新增 reporting 组合传参测试，确认 `--experiment-json` + `--manifest-resolved` 同传时走 `experiment_json` 成功。
- F4：`qa_corporate_action_ledger_outputs` catalog inputs 补 direct base table `dwd_stock_dividend_event`，测试同时检查 SQL 直接引用和 catalog input。
- F5/F9/F10：window SQL 同构 guard 收紧 dws/03 精确锚点与 dwd/01、dws/04 token 角色映射；新增 review seeded mutations，覆盖 `pe_ttm -> pe`、观测窗写死、边界互换三类失败。
- F6：补 `_failed_reasons`、legacy `_hard_reject_reasons` gate 表驱动覆盖和 `evaluate_cv_folds` 成功路径；v3 contract 对缺 v3 metrics 先返回 `v3_acceptance_metrics=missing`，不强造 legacy main path。
- F7/F8：`--manifest-resolved` scanner 缩到 backtest report command builders，manifest fixture 改为 repo-root 绝对路径。
- F11：`select_candidate([], [], None)` 的 `IndexError` 明确作为当前行为 characterization test 固定，本 PR 不改生产语义。

### 重要上下文

- F1 为 owner 数据决策项：Claude 实跑发现现存 CA-on baseline 的 staleness 断言会失败，dividend 数据缺口为 `2026-05-28..2026-06-09`，`ods_tushare_dividend` 当前 max partition/date 为 `2026-05-27`。本轮不执行补采、不写 BigQuery/GCS，断言语义不放宽，PR body 已改为如实陈述。
- 精确 ingestion watermark 仍需要新增 source ingestion 列或修复 ingestion meta；ingestion meta 当前 0-row 事件不在本 PR 处理。

### 改动文件

- `sql/strategy1/qa/qa_corporate_action_ledger_outputs.sql`
- `configs/strategy1/active_step_catalog.yml`
- `src/quant_ashare/strategy1/experiment_resolution.py`
- `tests/strategy1/test_experiment_resolution.py`
- `tests/strategy1/test_sql_render.py`
- `tests/strategy1/test_strategy1_catalog.py`
- `tests/strategy1/test_strategy1_pure_functions.py`
- `tests/warehouse/test_windowed_sql_isomorphism.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest -q tests`：266 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：passed。
- `git diff --check`：passed。
- `cd /tmp && python3 -m pytest /Users/fisher/Desktop/git/worktrees/quant-ashare-prd04/tests --collect-only -q`：266 collected。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_corporate_action_ledger_outputs.sql`：Query successfully validated。

### 阻塞项

- 无代码阻塞；F1 dividend ODS 补采与 CA-on baseline 复核留 owner 决策。

### 下一步建议

- push 后在 PR #202 回帖逐条说明 F2-F11 修复与 F1/F2 取舍；等待 Claude 复审。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
