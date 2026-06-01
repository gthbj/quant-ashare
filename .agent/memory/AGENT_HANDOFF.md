# Agent 交接（Agent Handoff）

本文件保存供后续 Agent 使用的最新交接记录。新交接用 `templates/HANDOFF_TEMPLATE.md` 追加到底部，并同步刷新下面的「当前交接摘要」。

> **语言约定（2026-06-01 起）**：新增交接条目一律用中文撰写；下方此前的英文历史条目保留原样作为记录，不回译。

## 当前交接摘要

`quant-ashare` 已完成**P0 DIM/DWD 物化**并完成 DWS/ADS 与策略设计：ODS 当前 57 表（含 `index_member_all` / `ci_index_member` / `bak_basic`）探查清楚三类分区语义；产出 DWD/DIM 建模方案 `docs/数据仓库建模方案-DWD-DIM.md`、DWS/ADS 表设计 `docs/数据仓库建模方案-DWS-ADS.md`、策略方案 `docs/A股中低频小资金机器学习策略方案.md`。全套规范已敲定：`sec_code` 主键、单位元/股、`ann_date_eff`/`visible_trade_date` PIT、后复权 `_hfq`、行业归属用 `in_date/out_date` 时点区间、血缘 `source_system/ingested_at`、版本字段 `feature_version/label_version/universe_version/model_id/strategy_id/run_id`、按月分区 + 聚簇、表+字段注释。owner 已澄清：当前阶段先把 **2019+ 数据**做正确；2019 年以前正式样本/明细是下一步。主方案 §4.6 已修订为三类 2019 前支撑范围：财务/事件前移到 2017、行情仅读 lookback buffer、维度/日历取快照或全量历史事件。

**已物化表**：`data-aquarium.ashare_dim` 下 `dim_trade_calendar`、`dim_stock`、`dim_stock_name_hist`；`data-aquarium.ashare_dwd` 下 `dwd_stock_eod_price`、`dwd_stock_eod_valuation`、`dwd_fin_indicator`、`dwd_fin_indicator_latest`、`dwd_index_eod`。`sql/qa/01_p0_smoke_checks.sql` 已通过。二轮评审发现已修复：盘中临停不再误标全天停牌，财务 latest 改为 `update_flag DESC` 优先。`sql/metadata/01_p0_table_column_descriptions.sql` 已补齐全部 P0 表/字段说明，BigQuery 验证 missing description = 0。

**评审协议（本会话确立）**：评审已提交代码/SQL 或设计文档,必须产出 `docs/reviews/` 评审文档;评审只读——不擅改被评审对象、不把发现直接写进 `.agent/memory/**`/`TODO.md`,发现是否转 OQ/TODO/决策由 owner 定（AGENTS.md §六 / DECISION-20260531-13）。首份代码评审 `docs/reviews/P0-建表SQL-review.md` 的 5 项发现已由 owner 要求修复并全部采纳，见 DECISION-20260531-14。

**重要执行结果**：`dwd_stock_eod_price` 8,495,462 行（2019-01-02 至 2026-05-29）；`dwd_stock_eod_valuation` 8,452,073 行；`dwd_fin_indicator` 332,960 行；`dwd_fin_indicator_latest` 198,030 行；`dwd_index_eod` 11,922 行，其中 8,899 行有 `index_dailybasic` 估值/市值/股本字段。上游已修复 `index_dailybasic` Parquet 类型问题，OQ-009 已关闭；STAR50/CSI1000 因 ODS 无 dailybasic endpoint 仍为空。最新 QA 验证：有成交但 `is_suspended=TRUE` 为 0，`has_intraday_halt` 为 897 行，`has_open_halt` 为 498 行，财务 latest 排序差异为 0。

**待重建提醒**：2026-06-01 已按 owner 口径更新 `dwd_index_eod` 脚本，改为 canonical `sec_code` + `source_sec_code`；当前 BigQuery 实表尚未按该脚本重建，重建后需重新执行 metadata 和 QA。

**DWS/ADS 设计**：P0 DWS 包含 `dws_stock_universe_daily`、价格/估值/财务特征、`dws_market_state_daily`、`dws_stock_label_daily`、`dws_stock_feature_daily_v0`、`dws_stock_sample_daily`。P1 行业路径已可落地：`dim_stock_sw_industry_hist` 使用 `index_member_all`，`dim_stock_ci_industry_hist` 使用 `ci_index_member`，历史 join 用 `in_date/out_date`，`is_new` 仅标当前归属。P0 ADS 包含训练面板、模型注册、预测、候选池、组合目标、订单计划、回测成交/持仓/NAV/绩效、信号监控。首个策略为 `ml_ranker_v0`：P0 特征横截面排序，长-only，`t` 日盘后信号、`t+1` 开盘/VWAP 建仓。

**下一步（P0/P1）**：补 `dwd_fin_income` / `dwd_fin_balancesheet` / `dwd_fin_cashflow`，或编写 P0 DWS/ADS SQL 并跑通 `ml_ranker_v0` 基线。关键参数：`@dwd_start_date = DATE '2019-01-01'`、`@fin_start_period = '20170101'`、`@lookback_start_date = DATE '2018-01-01'` 默认；后续应把 lookback 改为按最大滚动窗口计算。

**待 owner 确认**：dbt vs 纯 SQL（OQ-005）；P0 策略成本/调仓/持股数/北交所/训练工具链默认参数（OQ-010）。OQ-001 已关闭：行业映射 ODS 已补采。

> 历史交接已归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-05.md`。常规启动只需阅读本文件的当前摘要和最近交接；归档仅用于审计追溯。

---

## 交接条目

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
