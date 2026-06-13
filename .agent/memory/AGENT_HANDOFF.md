> 当前交接摘要（2026-06-13，Claude Opus 4.8，freeze-allowlist 热修 + topdown 构造路线收口）
> - 【最新】main 上 `test_metric_definition_freeze` 红：PR #222 新增 `simulate_cash_overlay_sharpe_contribution.py` 本地重定义被冻结的 `fmt_num/fmt_pct/markdown_table`，未复用既有/未更 allowlist（违反 DOC_CONVENTIONS「分析脚本指标定义」）。修复（branch `fix/freeze-allowlist-cash-overlay-fmt` off main）：抽共享模块 `src/quant_ashare/strategy1/report_format.py`（零重依赖、可安全 import），脚本改为 import 复用并删本地 4 个定义，allowlist 增 3 条共享模块路径。已验证 freeze 测试转绿 + 格式化输出 byte-identical（探针只读、计算未动、报告/CSV 数字不变）。
> - owner 裁决 topdown 自上而下整手构造路线**收口**（DECISION-20260613-02）：PR #217 修掉 retained 持仓销毁 ledger bug 后干净 `_v02` 已证伪 topdown（CAGR 11.96% / Calmar 0.21 / MaxDD -56.85% vs v1 15.36% / 0.4103 / -37.43%）；PR #218 严格 `max_single_weight` 单票上限只读 paper 探针证明上限也救不回（最好 Calmar 0.2018、MaxDD 未改善）。两 PR 均已合并。
> - 核心教训：topdown 深回撤是满仓小盘篮的系统性回撤，v1 的 ~30% 现金是回撤保险而非纯拖累；下一步方向 = market-state 条件化现金/仓位管理探针（待 owner 启动）。另一条待启动线：契约窗口语义修订含 MaxDD 硬门（DECISION-20260613-01）。
> - 保留：topdown ledger retained 修复 + QA-TOPDOWN-11/12 持仓守恒断言；paper harness opt-in `single_weight_cap`（默认关）。记忆已同步（DECISION_LOG/IMPLEMENTATION_STATUS/OPEN_QUESTIONS/TODO）。
> - 本会话工作模式（仅当前窗口）：Claude 实现、Codex 审核；PR #218 即按此跑通（Codex 审出软上限 bug → Claude 修为严格上限重跑 → Codex 复核可合并）。
>
> Model: Claude Opus 4.8

## 2026-06-13 Claude - freeze-allowlist 热修：cash-overlay 探针格式化函数抽共享模块

日期: 2026-06-13
Agent ID: Claude
Agent 实例 ID: 主仓库会话（/Users/fisher/Desktop/git/quant-ashare）
模型: Claude Opus 4.8
运行环境: macOS / zsh / branch `fix/freeze-allowlist-cash-overlay-fmt`（off main）
Run ID: N/A（纯本地，只改格式化函数来源 + 测试 allowlist，无 BQ / Cloud Run）
相关 issue/PR: 承接 PR #222（merge ecc811c 引入红测试）；本修复 PR 待开

### 已完成工作

- 定位 `test_metric_and_formatting_definitions_stay_on_explicit_allowlist` 红根因：PR #222 的 `scripts/strategy1/simulate_cash_overlay_sharpe_contribution.py` 本地定义 `fmt_pct/fmt_num/markdown_table`（+`_md_cell`），既未复用既有实现也未更 allowlist。
- 按 DOC_CONVENTIONS 优先级处理：既有 `fmt_*`/`markdown_table` 全部是各脚本本地副本且都藏在 `from google.cloud import bigquery` 重 import 之后，无可安全复用的共享实现 → 走「先抽共享模块再同步 allowlist」。
- 新建 `src/quant_ashare/strategy1/report_format.py`（仅 stdlib+numpy/pandas，零重依赖）承载 `fmt_pct/fmt_num/markdown_table`；`markdown_table` 加 `float_format` 关键字参数（默认 `{:.4f}` 与 cash-overlay 原行为一致，注：sibling `simulate_exposure_overlay_upper_bound` 用 `.6f`，故不能直接互用）。
- 脚本改为 `from quant_ashare.strategy1.report_format import ...` 并把 `src` 加入 sys.path（沿用 `promote_research_to_ads.py` 既有 pattern），删本地 4 个定义；allowlist 增 3 条 `report_format.py` 路径。

### 重要上下文

- 该脚本是只读 NAV 探针（不写表/不 promotion）；本修只改格式化函数来源，未碰任何计算（`window_metrics`/`simulate_variant` 等），故复现报告/CSV 数字不变。
- 等价性已硬验证：shared vs 原 local 实现在 NaN/inf/None/int/含 `|` 字符串等输入上 byte-identical。

### 改动文件

- 新增 `src/quant_ashare/strategy1/report_format.py`
- 改 `scripts/strategy1/simulate_cash_overlay_sharpe_contribution.py`（import + 删本地定义 + sys.path 加 src）
- 改 `tests/strategy1/test_metric_definition_freeze.py`（allowlist +3）

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_metric_definition_freeze.py` 转绿。
- `py_compile` 通过；脚本可正常 import，三函数来源指向 `quant_ashare.strategy1.report_format`。
- 格式化输出 byte-identical 等价测试通过。

### 阻塞项

- 无（待 Codex GPT-5.5+xhigh review → 修到零问题 → 合并）。

### 下一步建议

- 后续可将 `simulate_exposure_overlay_upper_bound.py` / `analyze_official_adj_leak.py` 等其余本地副本逐步迁到 `report_format.py`（用 `float_format` 兼容 `.6f`），收敛 allowlist；非本 PR 范围。

### 已更新记忆文件

- AGENT_HANDOFF.md（本条 + 摘要）、IMPLEMENTATION_STATUS.md（工程治理段补一行）。

Model: Claude Opus 4.8

## 2026-06-13 Claude - topdown 构造路线收口（单票上限探针 #218）+ 记忆同步

日期: 2026-06-13
Agent ID: Claude
Agent 实例 ID: 主仓库会话（/Users/fisher/Desktop/git/quant-ashare）
模型: Claude Opus 4.8
运行环境: macOS / zsh / branch `experiment/topdown-single-weight-cap`（已合并清理）
Run ID: N/A（只读 paper 探针，无 Cloud Run）
相关 issue/PR: PR #218（单票上限探针归档）；承接 PR #217（retained bug 修复 + `_v02`）

### 已完成工作

- 独立取证确认 PR #217 `_v01` 灾难根因（retained 持仓经 `update_holdings(plan)` 销毁），驱动 Codex 修复并复核（同会话 #217）。
- 角色反转模式下亲自实现单票上限探针（PR #218）：paper harness 加 opt-in `single_weight_cap`（默认 None=行为不变）+ `analyze_topdown_single_weight_cap_probe.py`；只读、未跑 live、未改 ledger 默认。Codex 审出"软上限（floor 取卖出手数留超 cap 残仓）"阻断项，已修为严格 ceil-trim 重跑，Codex 复核"无阻断、可合并"，已合并。
- 结论：严格单票上限也救不回 topdown（最好 Calmar 0.2018 ≈ 无上限、仍是 v1 一半，MaxDD 未改善）→ owner 裁决 topdown 收口（DECISION-20260613-02）。
- 记忆同步：DECISION-20260613-02（含归档滚动）、IMPLEMENTATION_STATUS、OPEN_QUESTIONS（OQ-010 子路线收口）、TODO（关闭 ceil-lot 决策项 + 新增 market-state 现金管理候选）。

### 下一步

- 待 owner 启动：① market-state 条件化现金/仓位管理探针；② 契约窗口语义修订（含 MaxDD 硬门，DECISION-20260613-01）。OQ-010 主问题仍 open（尚无 accepted baseline）。

Model: Claude Opus 4.8

## 2026-06-13 GPT-5.5 - topdown Phase 2 T0 retained ledger fix and v02 rerun

日期: 2026-06-13
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-topdown-p2-live`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/topdown-phase2-live`
Run ID: Cloud Build `a0aa7fb7-a26c-4480-bdb9-1163ed410b5d`；boot smoke `strategy1-backtest-report-job-4hh4d`；formal execution `strategy1-backtest-report-job-2lpzn`；run/backtest `s1_topdown_t0_continuous_true5y_2021_2026_v20260613_02` / `bt_s1_topdown_t0_continuous_true5y_2021_2026_v20260613_02`
相关 issue/PR: PRD `docs/prd/PRD_20260613_04_topdownPhase2T0口径修订与重跑.md`；PR #217 live 修复与报告交付

### 已完成工作

- 独立复核 PR #217 两条评论和 BigQuery 只读证据：`_v01` 真正根因不是 ceil-lot，而是 `build_daily_plan_topdown` 对 rank ≤ `walk_depth` 的 retained 持仓只记录 `retained.add(sec)`、不输出 `PlanRow`；主循环 `update_holdings(plan)` 只从 plan 重建持仓，导致 retained 持仓在调仓日无 SELL / 无现金回款地归零。`002245.SZ` 2021-07-26 案例和全局“股数减少且无 SELL/CA 行”查询吻合。
- 修复限定在 `build_daily_plan_topdown`：retained 持仓显式输出 hold/no-op `PlanRow`，保留 `cur_shares`、`sell_shares=0`、`want_value=0`、无 skip 状态；不改 v1 共用的 `update_holdings`。保留上一轮 `PlanRow.planned_buy_shares` 修复，避免 topdown ceil-lot 股数被执行层浮点回算改变。
- 新增回归单测覆盖 retained 持仓股数、现金、phantom trade 与持仓守恒；`qa_topdown_construction_outputs.sql` 新增 `QA-TOPDOWN-11`（股数减少必须由 SELL/CA 解释）与 `QA-TOPDOWN-12`（单日收益 `< -50%` hard sanity）。旧 `_v01` 已被新增 QA 挡下，job `bqjob_ra6e754e0d10734_0000019ebef0b5ce_1` 按预期失败。
- 从分支 `codex/topdown-phase2-live` 构建 one-off Strategy1 runner 镜像 `topdown-p2-retained-fix-7a70d98-20260613-04`，digest `sha256:0e3f3c7751ab4be4cbcefc94529c5ef51f663a89ef7609e4d5d4c662779cb016`；未更新 `latest`（仍为 `sha256:fdb61f8141e240c377b3faaa21b5e6efef9c783ebb9e04923ff3b675b8d54bc2`）。
- `strategy1-backtest-report-job` 已 pin 到 digest / generation 55；boot smoke `strategy1-backtest-report-job-4hh4d` 成功；formal execution `strategy1-backtest-report-job-2lpzn` 成功完成。
- Phase 2 `_v02` run 使用 resolver 解析的 synthetic prediction stream `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01`，参数为 CA-on `cash_div_and_split_v1` / `flat_10pct`、`tail_risk_profile_id=diagnostic_only`、`ledger_exec_v2_lot100_topdown`、`cloudrun_lot100_topdown_resume_v1`、fresh continuous `2021-01-04..2026-06-09`、`--skip-diagnosis --skip-tail-risk --skip-qa`、research-only。
- 外接 QA 四件套均通过：continuous `bqjob_r13624ec7b8c6f625_0000019ebefb96b8_1`（显式 topdown ledger/resume 覆盖）、lot-aware `bqjob_r34586777e4e7223b_0000019ebefbcda9_1`、topdown `bqjob_r4eaa32102a6d2982_0000019ebefbedf2_1`、CA ledger `bqjob_r15a60913a1b1c58c_0000019ebefc0d61_1`。
- ADS 9 张 run/backtest scoped 表反查均 0（job `bqjob_r7238d2f3c49e6c60_0000019ebefca18a_1`）；`ashare_research.research_promotion_manifest` 同 source 反查 0。
- 重做三方对比报告 `docs/分析-topdownPhase2三方对比-20260613.md` 与小 CSV `docs/analysis_topdown_phase2_comparison_20260613.csv`，并明确撤回 `_v01` 结论。

### 重要上下文

- 预登记判读仍为 **topdown 证伪**，但依据是修复后 `_v02`：长窗 topdown CAGR `11.96%`、compound Sharpe `0.3821`、Calmar `0.2104`、MaxDD `-56.85%`、平均现金 `2.51%`；v1 official baseline 为 CAGR `15.36%` / Sharpe `0.6685` / Calmar `0.4103` / MaxDD `-37.43%`。
- 静态近窗 `2024-01-02..2026-04-30`：topdown `_v02` CAGR `35.47%`、Sharpe `1.1776`、Calmar `0.8841`、MaxDD `-40.12%`；v1 为 CAGR `38.28%`、Sharpe `1.4642`、Calmar `1.1041`、MaxDD `-34.67%`；Phase 0 paper T0 为 CAGR `37.17%`、Sharpe `1.2301`、Calmar `0.9143`、MaxDD `-40.66%`。
- 修复后平均现金已降至 `2.51%`，但 ceil-lot 单票集中仍明显：长窗最大单票权重 `46.28%`、p95 最大单票权重 `31.20%`。本 PR 不改 sizing 语义，是否加 max single weight cap 留 owner 决策。
- 本轮不 promotion、不 accepted、不改默认 profile / 默认 CA、不改 v1 黄金 hash；Phase 0 paper daily 大 CSV 只从 GCS 临时读取复算，不入库。

### 改动文件

- `src/quant_ashare/strategy1/ledger.py`
- `tests/strategy1_cloudrun/test_lot_aware_ledger.py`
- `sql/strategy1/qa/qa_topdown_construction_outputs.sql`
- `docs/分析-topdownPhase2三方对比-20260613.md`
- `docs/analysis_topdown_phase2_comparison_20260613.csv`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1_cloudrun/test_lot_aware_ledger.py tests/strategy1/test_sql_render.py`：42 passed。
- `PYTHONPATH=src python3 -m pytest -q tests`：297 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：passed。
- `git diff --check`：passed。
- Cloud Build `a0aa7fb7-a26c-4480-bdb9-1163ed410b5d`：success；Artifact Registry digest `sha256:0e3f3c7751ab4be4cbcefc94529c5ef51f663a89ef7609e4d5d4c662779cb016`。
- Cloud Run boot smoke `strategy1-backtest-report-job-4hh4d`：success；formal execution `strategy1-backtest-report-job-2lpzn`：success。
- 外接 QA 四件套与 ADS/promotion 反查见上。

### 阻塞项

- 无 live 阻塞；`_v01` 作废，`_v02` 已按 PRD 预登记规则判读为 topdown 路线证伪。

### 下一步建议

- 提交并推送到 PR #217，等待 review retained fix + QA hardening + live 报告。
- owner 后续若继续处理 topdown，可单独评估 max single weight cap / sizing 语义；当前 topdown v2 T0 不应进入 accepted/promotion/default。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
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

