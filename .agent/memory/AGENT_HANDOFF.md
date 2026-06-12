> 当前交接摘要（2026-06-12，GPT-5.5，PRD_20260612_05 Batch 1）
> - `codex/prd05-batch1` 已完成 Batch 1 代码与测试：`bq_io.py` / `config.py` / runner `__version__` 迁入 `src/quant_ashare/strategy1/`，scripts 同名路径保留兼容 shim。
> - src 对 `scripts.strategy1_cloudrun.bq_io` / `config` / `dataset_roles` / `acceptance` / `__version__` 的反向 import 已清零；剩余反向 import 仅限 Batch 2/3 范围。
> - 兼容符号快照与反向 import 计数断言已加入 `tests/strategy1/test_package_boundaries.py`；旧 `bq_io/config` scripts 路径未加入 retired-lint ban-list。
> - 本轮未改运行语义，未触碰 Cloud Run job spec/args/镜像/IAM，未写 BigQuery/GCS；全量验证已通过，PR #203 已创建。
>
> Model: GPT-5.5

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
