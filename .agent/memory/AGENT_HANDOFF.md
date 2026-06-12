> 当前交接摘要（2026-06-12，GPT-5.5，PR #201 pre-merge rebase）
> - `codex/prd03-memory-archive` 已 rebase 到 `origin/main@a5ca9e5`（PR #202 已合并），#202 新记忆内容已按 PRD_03 滚动结构处置。
> - `IMPLEMENTATION_STATUS.md` 保留最近 7 条（含 PR #202 两条）；`AGENT_HANDOFF.md` 保留当前 rebase 条目 + PR #202 两条交接；超出条目按月归档。
> - `KNOWN_CONSTRAINTS.md` 保留 #202 dividend 过渡政策条款；`TODO.md` 继承 PRD_04 完成项与 dividend backfill 待办。
> - 本轮未改 resolver 代码、未写 BigQuery/GCS、未触碰 Cloud Run job spec/镜像/IAM；对账和全量 pytest 已通过，结果见当前交接条目和 PR #201 comment。
>
> Model: GPT-5.5

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
