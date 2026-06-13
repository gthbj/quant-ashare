> 当前交接摘要（2026-06-13，GPT-5.5，topdown Phase 2 T0 live 完成）
> - PRD_20260613_04 Phase 2 live 已完成：从最新 `origin/main@779089d` + 本 PR hotfix 构建 one-off runner 镜像 `topdown-p2-t0-live-779089d-20260613-03`，digest `sha256:1e91a5733df2cd7a38c2275cdb3a75f246fabe539c1e57db992c3a36bef5c9db`；`latest` 未更新，`strategy1-backtest-report-job` pin 到 generation 54，boot smoke `strategy1-backtest-report-job-phtfj` 通过。
> - 正式 research-only run/backtest `s1_topdown_t0_continuous_true5y_2021_2026_v20260613_01` / `bt_s1_topdown_t0_continuous_true5y_2021_2026_v20260613_01` 已用 generation 54 `--force-replace` 完成，formal execution `strategy1-backtest-report-job-j9m5t` 成功；外接 QA 四件套全过，ADS 反查和 `research_promotion_manifest` 均为 0。
> - 预登记判读为 topdown 证伪：长窗 CAGR `-77.13%`、Calmar `-0.772`、MaxDD `-99.95%`、平均现金 `76.31%`，显著劣于 v1 official baseline；报告 `docs/分析-topdownPhase2三方对比-20260613.md` 与小 CSV 已生成。本轮不 promotion、不 accepted、不改 v1/default。
>
> Model: GPT-5.5

## 2026-06-13 GPT-5.5 - topdown Phase 2 T0 live rerun

日期: 2026-06-13
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-topdown-p2-live`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/topdown-phase2-live`
Run ID: Cloud Build `bc6cca10-565c-4244-a227-e2cefd9ad9d3`；boot smoke `strategy1-backtest-report-job-phtfj`；formal execution `strategy1-backtest-report-job-j9m5t`；run/backtest `s1_topdown_t0_continuous_true5y_2021_2026_v20260613_01` / `bt_s1_topdown_t0_continuous_true5y_2021_2026_v20260613_01`
相关 issue/PR: PRD `docs/prd/PRD_20260613_04_topdownPhase2T0口径修订与重跑.md`；PR #215 后续 live 交付

### 已完成工作

- 重新校验 PR #215 已真实合并，并把 live worktree rebase 到最新 `origin/main@779089d`（PR #216 为文档/记忆变更，未触碰 runner 代码）。
- live 初跑暴露 `QA-TOPDOWN-4`：topdown 构造层用 ceil-lot 接受的买入股数在执行层经 `want_value / exec_open` 浮点回算时可能被下取整，导致新开仓低于 5% 下限；已在本分支补 `PlanRow.planned_buy_shares`，topdown 执行直接使用构造层已审定股数，v1 路径不变，并新增单测覆盖 11.71 元 / 500 股回归。
- 从最新 main 基底 + hotfix 构建 one-off Strategy1 runner 镜像 `topdown-p2-t0-live-779089d-20260613-03`，digest `sha256:1e91a5733df2cd7a38c2275cdb3a75f246fabe539c1e57db992c3a36bef5c9db`；未更新 `latest`（仍为 `sha256:fdb61f8141e240c377b3faaa21b5e6efef9c783ebb9e04923ff3b675b8d54bc2`）。
- `strategy1-backtest-report-job` 已 pin 到 digest / generation 54；boot smoke `strategy1-backtest-report-job-phtfj` 成功；formal execution `strategy1-backtest-report-job-j9m5t` 成功完成。
- Phase 2 run 使用 resolver 解析的 synthetic prediction stream `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01`，参数为 CA-on `cash_div_and_split_v1` / `flat_10pct`、`tail_risk_profile_id=diagnostic_only`、`ledger_exec_v2_lot100_topdown`、`cloudrun_lot100_topdown_resume_v1`、fresh continuous `2021-01-04..2026-06-09`、`--skip-diagnosis --skip-tail-risk --skip-qa`、research-only。
- 外接 QA 四件套均通过：continuous `11cb7abb-f015-467c-be68-5f1f1827a569`（显式 topdown ledger/resume 覆盖）、lot-aware `849654cd-9802-43ff-afcf-aab3c14c5cea`、topdown `2e99bef8-dfab-4828-aced-1a6de40522e4`、CA ledger `413ff54a-be61-413a-9422-1ce5ad0bc611`。
- ADS 9 张 run/backtest scoped 表反查均 0；`ashare_research.research_promotion_manifest` 同 source 反查 0（job `f27c5e31-09af-46ac-9a66-5142509ede8b`）。
- 生成三方对比报告 `docs/分析-topdownPhase2三方对比-20260613.md` 与小 CSV `docs/analysis_topdown_phase2_comparison_20260613.csv`。

### 重要上下文

- 预登记判读为 **topdown 证伪**：长窗 topdown CAGR `-77.13%`、Calmar `-0.772`、MaxDD `-99.95%`、平均现金 `76.31%`，同时劣于 v1 official baseline CAGR `15.36%` / Calmar `0.4103`，也劣于 Phase 0 paper T0。
- 静态近窗 `2024-01-02..2026-04-30` 的 topdown 0% CAGR / 0% MaxDD 是因为近窗起点 NAV 已约 `0.000458`（净值约 45.82 元）且之后全现金不动，不代表风险改善。
- 本轮不 promotion、不 accepted、不改默认 profile / 默认 CA、不改 v1 黄金 hash；Phase 0 paper daily 大 CSV 只从 GCS 临时读取复算，不入库。

### 改动文件

- `src/quant_ashare/strategy1/ledger.py`
- `tests/strategy1_cloudrun/test_lot_aware_ledger.py`
- `docs/分析-topdownPhase2三方对比-20260613.md`
- `docs/analysis_topdown_phase2_comparison_20260613.csv`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1_cloudrun/test_lot_aware_ledger.py tests/strategy1/test_sql_render.py`：41 passed。
- `PYTHONPATH=src python3 -m pytest -q tests`：296 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：passed。
- `git diff --check`：passed。
- Cloud Build `bc6cca10-565c-4244-a227-e2cefd9ad9d3`：success；Artifact Registry digest `sha256:1e91a5733df2cd7a38c2275cdb3a75f246fabe539c1e57db992c3a36bef5c9db`。
- Cloud Run boot smoke `strategy1-backtest-report-job-phtfj`：success；formal execution `strategy1-backtest-report-job-j9m5t`：success。
- 外接 QA 四件套与 ADS/promotion 反查见上。

### 阻塞项

- 无 live 阻塞；结果已按 PRD 判读为 topdown 路线证伪。

### 下一步建议

- 提交本分支并开 PR，review hotfix + live 报告 + 记忆/TODO 更新。
- owner 后续若继续处理现金拖累，建议从碎股/资金口径或独立路线重新立项；当前 topdown v2 T0 不应进入 accepted/promotion/default。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

## 2026-06-13 Claude - 契约 v4 提案否决落档（DECISION-20260613-01）+ PR #215 合并事故修复

日期: 2026-06-13
Agent ID: Claude
Agent 实例 ID: 主仓库会话（/Users/fisher/Desktop/git/quant-ashare）
模型: Claude Fable 5
运行环境: macOS / zsh / branch `docs/decision-20260613-01-v4-rejected`
Run ID: N/A
相关 issue/PR: PRD_20260613_05（提案，PR #214 定稿）、PR #215（topdown T0 代码，合并事故后恢复合并）

### 已完成工作

- owner 否决 contract v4 提案本版，理由"最大回撤肯定要一个硬门"：落档 DECISION-20260613-01（主文件 + 月度归档），PRD_20260613_05 文首标注否决状态，KNOWN_CONSTRAINTS 新增"后续契约修订必须含长窗 MaxDD 硬门"约束，TODO 新增"修订重提待 owner 启动"项，IMPLEMENTATION_STATUS 同步。
- 修复 PR #215 合并事故：draft 未 ready 即 merge（静默失败）+ 删分支致 PR 自动关闭；从本地 commit `aa817f50` 重推分支 → reopen → ready → 真实 MERGED（mergedAt=2026-06-13T00:55:34Z），main 已含 T0 修订，295 tests 通过。

### 进行中

- topdown Phase 2 live（PRD_20260613_04）：Codex 会话（同一会话续接）执行镜像构建 + boot smoke + continuous 重跑 + 外接 QA 四件套 + 三方对比报告。

### 下一步

- Phase 2 交付后 review、按预登记判读整理给 owner；契约修订重提（含 MaxDD 硬门阈值/窗口设计）等 owner 启动。

Model: Claude Fable 5

## 2026-06-13 GPT-5.5 - topdown Phase 2 T0 code PR

日期: 2026-06-13
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-topdown-p2`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/topdown-phase2-t0`
Run ID: N/A
相关 issue/PR: PRD `docs/prd/PRD_20260613_04_topdownPhase2T0口径修订与重跑.md`

### 已完成工作

- `src/quant_ashare/strategy1/ledger.py` 放宽 topdown v2 profile 校验：允许 `diagnostic_only` 或显式 individual guard profile，仍拒绝 `market_risk_off_v0` 这类非 topdown 构造 profile；v1 默认行为与黄金 hash 不变。
- `sql/strategy1/qa/qa_topdown_construction_outputs.sql` 将 QA-TOPDOWN-6/7/8 改为 profile 条件化，并在 QA-TOPDOWN-1 对齐 summary 实际 `tail_risk_profile_id`：`diagnostic_only` 跳过 P1 专属断言，individual guard profile 仍要求 tail-risk marker 与零 filled BUY。
- `configs/strategy1/active_step_catalog.yml` 将 `p_has_individual_risk_guard` 登记为 `qa_topdown_construction_outputs` 的 internal param，保持 SQL render 不留 unmanaged default。
- 单测补齐 topdown + `diagnostic_only`：不再 raise、tail-risk 标记自然放行买入、`cash_redistribution` 仍为 `topdown_whole_order_skip_v2`；market-only profile 仍 fail-fast。
- `docs/prd/PRD_20260611_10_策略1自上而下整手组合构造.md` 文首加入 `PRD_20260613_04` supersede 指针。

### 重要上下文

- 本轮只做代码 PR；按 owner 指令，live 重跑需等代码 PR review 通过并合并后再执行。
- 未构建 Strategy1 runner 新镜像、未执行 Cloud Run、未写 BigQuery/GCS、未跑外接 QA 四件套、未产出三方对比报告；不 promotion、不 accepted。
- Phase 2 live 执行时仍必须显式 CA-on 参数、`tail_risk_profile_id=diagnostic_only`、`--use-topdown-ledger`、`--skip-diagnosis --skip-tail-risk --skip-qa`，并用外接 QA 参数表显式覆盖 topdown ledger / resume policy。

### 改动文件

- `src/quant_ashare/strategy1/ledger.py`
- `sql/strategy1/qa/qa_topdown_construction_outputs.sql`
- `configs/strategy1/active_step_catalog.yml`
- `tests/strategy1_cloudrun/test_lot_aware_ledger.py`
- `tests/strategy1/test_sql_render.py`
- `docs/prd/PRD_20260611_10_策略1自上而下整手组合构造.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1_cloudrun/test_lot_aware_ledger.py tests/strategy1/test_sql_render.py`：40 passed。
- `PYTHONPATH=src python3 -m pytest -q tests`：295 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：passed。
- `git diff --check`：passed。
- `bq query --project_id=data-aquarium --location=asia-east2 --use_legacy_sql=false --dry_run < sql/strategy1/qa/qa_topdown_construction_outputs.sql`：validated。

### 阻塞项

- 无代码阻塞；Phase 2 live 重跑等待 owner review 通过并合并代码 PR。

### 下一步建议

- PR 合并后构建包含本修订的 immutable Strategy1 runner 镜像，完成 backtest_report boot smoke。
- 按 `PRD_20260613_04` §2 执行 research-only topdown Phase 2 fresh continuous、外接 QA 四件套、ADS/promotion 反查、三方对比报告与预登记判读。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`
