# Agent 交接（Agent Handoff）

本文件保存供后续 Agent 使用的最新交接记录。新交接用 `templates/HANDOFF_TEMPLATE.md` 追加到底部，并同步刷新下面的「当前交接摘要」。

> **语言约定（2026-06-01 起）**：新增交接条目一律用中文撰写；下方此前的英文历史条目保留原样作为记录，不回译。

## 当前交接摘要

`quant-ashare` 已完成**P0 DIM/DWD 物化**和**策略 1 价格量价 DWS/ADS SQL 物化**：ODS 当前 57 表（含 `index_member_all` / `ci_index_member` / `bak_basic`）探查清楚三类分区语义；产出 DWD/DIM 建模方案 `docs/数据仓库建模方案-DWD-DIM.md`、DWS/ADS 表设计 `docs/数据仓库建模方案-DWS-ADS.md`、策略方案 `docs/A股中低频小资金机器学习策略方案.md`、策略 1 PRD `docs/prd/PRD_20260601_01_策略1价格量价基础分类模型.md`、策略 1 runner 实现 PRD `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`、OQ-003 财务报表口径 PRD `docs/prd/PRD_20260601_03_财务报表口径维度.md`。全套规范已敲定：`sec_code` 主键、单位元/股、`ann_date_eff`/`visible_trade_date` PIT、后复权 `_hfq`、行业归属用 `in_date/out_date` 时点区间、血缘 `source_system/ingested_at`、版本字段 `feature_version/label_version/universe_version/model_id/strategy_id/run_id`、按月分区 + 聚簇、表+字段注释。owner 已澄清：当前阶段先把 **2019+ 数据**做正确；2019 年以前正式样本/明细是下一步；OQ-003 已采纳 P0 默认合并报表 `report_type='1'`、DWD 保留口径字段、DWS 默认过滤默认口径。主方案 §4.6 已修订为三类 2019 前支撑范围：财务/事件前移到 2017、行情仅读 lookback buffer、维度/日历取快照或全量历史事件。

**已物化表**：`data-aquarium.ashare_dim` 下 `dim_trade_calendar`、`dim_stock`、`dim_stock_name_hist`；`data-aquarium.ashare_dwd` 下 `dwd_stock_eod_price`、`dwd_stock_eod_valuation`、`dwd_fin_indicator`、`dwd_fin_indicator_latest`、`dwd_index_eod`；`data-aquarium.ashare_dws` 下策略 1 六表（universe、价格特征、估值特征、标签、特征宽表、样本表）；`data-aquarium.ashare_ads` 下 11 张训练/预测/组合/回测/监控契约表。`sql/qa/01_p0_smoke_checks.sql` 与 `sql/qa/02_strategy1_dws_ads_checks.sql` 均通过。二轮评审发现已修复：盘中临停不再误标全天停牌，财务 latest 改为 `update_flag DESC` 优先。`sql/metadata/01_p0_table_column_descriptions.sql` 已补齐全部 P0 DIM/DWD 表/字段说明，BigQuery 验证 missing description = 0。

**评审协议（2026-06-01 更新）**：评审已提交代码/SQL 或设计文档时，GitHub PR review 默认写 PR comment；一条写不下拆多条。只有 owner 明确要求或无 PR comment 承载面时，才另写 `docs/reviews/` 评审文档。评审只读——不擅改被评审对象、不把发现直接写进 `.agent/memory/**`/`TODO.md`，发现是否转 OQ/TODO/决策由 owner 定（AGENTS.md §六 / DECISION-20260601-03）。历史 `docs/reviews/P0-建表SQL-review.md` 等评审文档保留作审计记录。

**重要执行结果**：`dwd_stock_eod_price` 8,495,462 行（2019-01-02 至 2026-05-29）；`dwd_stock_eod_valuation` 8,452,073 行；`dwd_fin_indicator` 332,960 行；`dwd_fin_indicator_latest` 198,030 行；`dwd_index_eod` 11,922 行，其中 8,899 行有 `index_dailybasic` 估值/市值/股本字段，且沪深300已归一为 `sec_code='000300.SH'` / `source_sec_code='399300.SZ'`。策略 1 DWS 行数：universe 8,495,462 行（默认池 3,403,501 行）、价格特征 8,495,462 行（完整 60 日历史 7,936,431 行）、估值特征 8,452,073 行、标签 8,495,462 行（5 日有效标签 8,388,177 行）、样本表 8,495,462 行（默认可训练 3,274,084 行）。上游已修复 `index_dailybasic` Parquet 类型问题，OQ-009 已关闭；STAR50/CSI1000 因 ODS 无 dailybasic endpoint 仍为空。2026-06-01 复核 OQ-007：`stock_basic_delisted.delist_date` 已为可解析 `STRING`，`dim_stock` SQL 已改为优先使用 ODS 退市日；实际 BigQuery 依赖表需合并后重建。

**DWS/ADS 设计与已落地范围**：P0 DWS 设计包含 `dws_stock_universe_daily`、价格/估值/财务特征、`dws_market_state_daily`、`dws_stock_label_daily`、`dws_stock_feature_daily_v0`、`dws_stock_sample_daily`；当前策略 1 先落地 universe、价格/估值特征、open-to-close 标签（rank/xs return 按默认 universe 截面计算）、特征宽表、样本表，财务特征和市场状态待补。财务特征口径 PRD 已采纳并关闭 OQ-003：P0 默认消费合并报表 `report_type='1'`，DWD 保留 `report_type`/`report_caliber`，DWS 默认过滤默认口径，后续实现 PR 需同步主建模方案文档和 SQL。PR #4 comment 的 P1/P2 已跟进：`label_valid` 语义说明、去冗余 JOIN、最早可训练样本日 QA、DWD 字段名文档同步。P1 行业路径已可落地：`dim_stock_sw_industry_hist` 使用 `index_member_all`，`dim_stock_ci_industry_hist` 使用 `ci_index_member`，历史 join 用 `in_date/out_date`，`is_new` 仅标当前归属。P0 ADS 表契约已落地。策略 1 PRD 名称为 `ml_pv_clf_v0`；首个基线默认股票池仅沪深主板（`SSE_MAIN` / `SZSE_MAIN`），不含北交所、创业板、科创板；runner 设计 `docs/策略1-ml_pv_clf_v0-runner设计.md` 已完成，runner 实现 PRD `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md` 已完成，执行路径为 BigQuery ML + SQL：训练面板、BQML model object、预测、候选、组合、订单、回测、监控均写既有 ADS 表。

**下一步（P0/P1）**：OQ-007 合并后先重建 `dim_stock`，并按依赖重建 `dwd_stock_eod_price` 与策略 1 DWS/ADS 派生产物，执行 metadata / P0 QA / 策略 1 QA；或按 `PRD_20260601_02_策略1BQML回测闭环.md` 落地策略 1 BigQuery ML + SQL runner（生成 `ads_ml_training_panel_daily`，训练 BQML `LOGISTIC_REG` 主模型和 `LINEAR_REG` 对照，写预测/候选/组合/回测 ADS 表，输出 RankIC/分层收益/NAV/换手/不可成交比例）；也可按 `PRD_20260601_03_财务报表口径维度.md` 的默认合并报表口径补 P0 通用 DWS 扩展表（财务特征、市场状态）与 `dwd_fin_income` / `dwd_fin_balancesheet` / `dwd_fin_cashflow`。关键参数：`@dwd_start_date = DATE '2019-01-01'`、`@fin_start_period = '20170101'`、`@lookback_start_date = DATE '2018-01-01'` 默认；后续应把 lookback 改为按最大滚动窗口计算，并决定是否补 lookback-capable 价格构建输入（OQ-011）。

**待 owner 确认**：dbt vs 纯 SQL（OQ-005）；P0 策略成本/调仓/持股数/单票权重上限（OQ-010，训练工具链已定为 BigQuery ML + SQL runner，首个基线股票池已定为仅沪深主板）；是否补 lookback-capable 价格构建输入以填满 2019-01 起 60 日窗口（OQ-011）。OQ-001/OQ-003/OQ-007 已关闭。

**分支卫生**：PR 合并后，若 owner 未要求保留工作分支，应删除已合并且不再使用的 `codex/*` 本地分支和对应远端分支。`codex/implement-strategy1-prd` 已在本地和远端删除。

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
