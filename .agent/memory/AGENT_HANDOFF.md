# Agent 交接（Agent Handoff）

本文件保存供后续 Agent 使用的最新交接记录。新交接用 `templates/HANDOFF_TEMPLATE.md` 追加到底部，并同步刷新下面的「当前交接摘要」。

## 当前交接摘要

`quant-ashare` 已完成**P0 DIM/DWD 物化**：ODS（54 表）探查清楚三类分区语义；产出 DWD/DIM 建模方案文档 `docs/数据仓库建模方案-DWD-DIM.md`；敲定全套规范——`sec_code` 主键、单位元/股、`ann_date_eff` PIT、复权 `_hfq/_qfq`、血缘 `source_system/ingested_at`、按月分区 + `sec_code` 聚簇、行情表 `require_partition_filter`、表+字段注释（含继承 ODS）。owner 已澄清：当前阶段先把 **2019+ 数据**做正确；2019 年以前正式样本/明细是下一步。主方案 §4.6 已修订为三类 2019 前支撑范围：财务/事件前移到 2017、行情仅读 lookback buffer、维度/日历取快照或全量历史事件。

**已物化表**：`data-aquarium.ashare_dim` 下 `dim_trade_calendar`、`dim_stock`、`dim_stock_name_hist`；`data-aquarium.ashare_dwd` 下 `dwd_stock_eod_price`、`dwd_stock_eod_valuation`、`dwd_fin_indicator`、`dwd_fin_indicator_latest`、`dwd_index_eod`。`sql/qa/01_p0_smoke_checks.sql` 已通过。

**评审协议（本会话确立）**：评审已提交代码/SQL 或设计文档,必须产出 `docs/reviews/` 评审文档;评审只读——不擅改被评审对象、不把发现直接写进 `.agent/memory/**`/`TODO.md`,发现是否转 OQ/TODO/决策由 owner 定（AGENTS.md §六 / DECISION-20260531-13）。首份代码评审 `docs/reviews/P0-建表SQL-review.md` 的 5 项发现已由 owner 要求修复并全部采纳，见 DECISION-20260531-14。

**重要执行结果**：`dwd_stock_eod_price` 8,495,462 行（2019-01-02 至 2026-05-29）；`dwd_stock_eod_valuation` 8,452,073 行；`dwd_fin_indicator` 332,960 行；`dwd_fin_indicator_latest` 198,030 行；`dwd_index_eod` 11,922 行，其中 8,899 行有 `index_dailybasic` 估值/市值/股本字段。上游已修复 `index_dailybasic` Parquet 类型问题，OQ-009 已关闭；STAR50/CSI1000 因 ODS 无 dailybasic endpoint 仍为空。

**下一步**：补 `dwd_fin_income` / `dwd_fin_balancesheet` / `dwd_fin_cashflow`，或衔接 `dws_stock_feature_daily` / `dws_stock_label_daily`。后续应把 `lookback_start_date` 从固定默认值改为按最大滚动窗口计算。

**待 owner 确认**：行业映射缺口（OQ-001）；dbt vs 纯 SQL（OQ-005）。

---

## 交接条目

## Handoff Entry

Date: 2026-05-31
Agent ID: Agent_RD（数仓建模）
Agent Instance ID: claude-opus-4.8 / Claude Code 会话
Model: Claude Opus 4.8
Runtime: Claude Code CLI
Run ID: —
Related issue/PR: —（尚无远程）

### Work Completed
- 探查 `data-aquarium.ashare_ods` 外部表的字段与分区语义（后续复核订正为 54 张）。
- 撰写并多轮迭代定稿 `docs/数据仓库建模方案-DWD-DIM.md`（含分层、ODS 表映射、五条铁律、DIM/DWD 设计、DWS 衔接、工程建议）。
- 敲定命名/单位/分区/回填/注释全套规范，写入文档与 DECISION_LOG。
- `git init` + `.gitignore` + 首个 commit（`main`）。
- 创建本 `.agent/` 工作记忆体系 + 根 `AGENTS.md` 读写协议。

### Important Context
- ODS 三类分区语义是建模地基（见 ARCHITECTURE_MEMORY）。
- 财务 PIT 用 `ann_date_eff`，绝不用 partition_date/报告期当可见时间。
- 行情按月分区（4000 分区上限），`sec_code` 聚簇。

### Files Changed
- `docs/数据仓库建模方案-DWD-DIM.md`、`.gitignore`、`AGENTS.md`、`CLAUDE.md`、`TODO.md`、`.agent/memory/**`。

### Tests / Validation
- 无代码，无测试；ODS 探查通过若干 `bq query` 验证（分区语义、历史起点、endpoint 分布）。

### Blockers
- 无硬阻塞；OQ-001（行业映射）、OQ-002（财务前移确认）待 owner。

### Next Recommended Step
- 落地 P0 建表 SQL（见「当前交接摘要」清单）。

### Memory Files Updated
- 初始化全部记忆文件（本次为首次建立）。

## Handoff Entry

Date: 2026-05-31
Agent ID: Agent_RD（数仓建模）
Agent Instance ID: claude-opus-4.8 / Claude Code 会话
Model: Claude Opus 4.8
Runtime: Claude Code CLI
Run ID: —
Related issue/PR: —

### Work Completed
- 推送仓库到 GitHub（gthbj/quant-ashare，main）；新增模型署名协议（AGENTS.md §5 / CLAUDE.md）。
- 按实测 review 整改建模方案：9 项采纳并改文档、2 项调整执行；写 `docs/reviews/数据仓库建模方案-DWD-DIM-review-response.md`。

### Important Context
- review 复核确认：ODS **54** 张表、`fina_indicator` **无 `f_ann_date`**。
- 财务改「版本事实表 + 最新快照分离」；价格表改「交易日历×在市」骨架（含停牌日空行）；新增 `visible_trade_date`、表级可见日规则、ODS 元数据矩阵、lookback、方向性可交易。
- 调整项：P0-4（ODS delist_date 类型）不改 ODS、用 DWD 兜底（OQ-007）；P1-3 只加开盘侧、不加收盘四象限。

### Files Changed
- `docs/数据仓库建模方案-DWD-DIM.md`（多章节）、`docs/reviews/…-review-response.md`、`.agent/memory/{DECISION_LOG,OPEN_QUESTIONS,IMPLEMENTATION_STATUS,KNOWN_CONSTRAINTS,AGENT_HANDOFF}.md`。

### Tests / Validation
- 复核 ODS 事实用 `bq query`（表数=54、`fina_indicator` 字段）。SQL 为设计稿，未在 BQ 实跑。

### Blockers
- OQ-007（ODS `delist_date` 类型）待上游；OQ-001（行业映射缺口）待定。

### Next Recommended Step
- 落地 P0 建表 SQL（按整改后方案）。注意 `docs/数据仓库建模方案-DWD-DIM-review.md` 仍为**本地未跟踪、不提交**（owner 指示）。

### Memory Files Updated
- DECISION_LOG（改 04 + 加 09）、OPEN_QUESTIONS（关 02 + 加 07）、IMPLEMENTATION_STATUS、KNOWN_CONSTRAINTS、AGENT_HANDOFF。

## Handoff Entry

Date: 2026-05-31
Agent ID: Codex
Agent Instance ID: Codex desktop session
Model: GPT-5
Runtime: Codex desktop
Run ID: —
Related issue/PR: —

### Work Completed
- Review `docs/数据仓库建模方案-DWD-DIM.md` with an overbroad initial interpretation of 2019-before data scope (superseded by the following handoff entry).
- Added `docs/reviews/数据仓库建模方案-DWD-DIM-review-2019前数据范围修正.md`.
- Recorded DECISION-20260531-10, later superseded by DECISION-20260531-11.

### Important Context
- Current ODS remains 54 external tables with Hive partition filters.
- Early coverage gaps were checked, but are not P0 blockers under the corrected 2019+ scope.
- Latest `stock_basic` misses 4 all-history `daily` codes: `000022.SZ`, `000043.SZ`, `300114.SZ`, `920218.BJ`.
- `stock_basic_delisted.delist_date` still fails with Parquet type mismatch; keep daily-last-trade-date fallback until upstream fixes.

### Files Changed
- `docs/reviews/数据仓库建模方案-DWD-DIM-review-2019前数据范围修正.md`
- `TODO.md`
- `.agent/memory/{MEMORY_INDEX,PROJECT_CONTEXT,ARCHITECTURE_MEMORY,IMPLEMENTATION_STATUS,KNOWN_CONSTRAINTS,OPEN_QUESTIONS,DECISION_LOG,AGENT_HANDOFF}.md`

### Tests / Validation
- Queried BigQuery `data-aquarium.ashare_ods` metadata and key ODS tables with partition filters.
- Verified table count 54; daily history `19901219` to `20260529`; SSE calendar `19901219` to `20261231`; index endpoints and stock coverage.

### Blockers
- Superseded by the following correction entry; no current blocker from OQ-008.

### Next Recommended Step
- Superseded by DECISION-20260531-11: implement P0 for 2019+ with finance/event 2017 support and market lookback buffer.

### Memory Files Updated
- MEMORY_INDEX、PROJECT_CONTEXT、ARCHITECTURE_MEMORY、IMPLEMENTATION_STATUS、KNOWN_CONSTRAINTS、OPEN_QUESTIONS、DECISION_LOG、AGENT_HANDOFF；TODO.md updated.

## Handoff Entry

Date: 2026-05-31
Agent ID: Codex
Agent Instance ID: Codex desktop session
Model: GPT-5
Runtime: Codex desktop
Run ID: —
Related issue/PR: —

### Work Completed
- Verified upstream GCS Parquet repair for `ods_tushare_index_dailybasic`; 2019+ reads of `float_mv`, `float_share`, `total_mv`, `total_share`, `pe`, `pe_ttm`, `pb` now succeed.
- Restored `sql/dwd/04_dwd_index_eod.sql` to join `index_dailybasic`.
- Rebuilt `data-aquarium.ashare_dwd.dwd_index_eod` with valuation/share fields.
- Updated `sql/qa/01_p0_smoke_checks.sql` to assert index valuation fields exist where dailybasic endpoints are available.

### Important Context
- `index_dailybasic` units are already yuan/share, unlike stock `daily_basic`; DWD does not multiply by 10000.
- `dwd_index_eod` now has 11,922 rows, 8,899 rows with non-null `pe`, `pe_ttm`, `pb`, `total_mv_cny`, `float_mv_cny`, `total_share`, and `float_share`.
- STAR50 (`000688.SH`) and CSI1000 (`000852.SH`) still have NULL valuation fields because ODS has no corresponding `index_dailybasic` endpoints.

### Files Changed
- `sql/dwd/04_dwd_index_eod.sql`
- `sql/qa/01_p0_smoke_checks.sql`
- `sql/README.md`
- `TODO.md`
- `.agent/memory/{MEMORY_INDEX,PROJECT_CONTEXT,ARCHITECTURE_MEMORY,IMPLEMENTATION_STATUS,KNOWN_CONSTRAINTS,OPEN_QUESTIONS,DECISION_LOG,AGENT_HANDOFF}.md`

### Tests / Validation
- `bq query --dry_run --location=asia-east2` passed for `sql/dwd/04_dwd_index_eod.sql` and QA script.
- Executed `sql/dwd/04_dwd_index_eod.sql`; table rebuilt successfully.
- Executed `sql/qa/01_p0_smoke_checks.sql`; all assertions passed.
- Queried non-null counts by index.

### Blockers
- None for OQ-009. Remaining open questions are OQ-001/OQ-003/OQ-004/OQ-005/OQ-006/OQ-007.

### Next Recommended Step
- Continue with `dwd_fin_income` / `dwd_fin_balancesheet` / `dwd_fin_cashflow`, or begin DWS feature/label tables.

### Memory Files Updated
- MEMORY_INDEX、PROJECT_CONTEXT、ARCHITECTURE_MEMORY、IMPLEMENTATION_STATUS、KNOWN_CONSTRAINTS、OPEN_QUESTIONS、DECISION_LOG、AGENT_HANDOFF；TODO.md updated.

## Handoff Entry

Date: 2026-05-31
Agent ID: Codex
Agent Instance ID: Codex desktop session
Model: GPT-5
Runtime: Codex desktop
Run ID: —
Related issue/PR: —

### Work Completed
- Created root `sql/` directory for P0 BigQuery build scripts.
- Added dataset bootstrap SQL plus DIM scripts for `dim_trade_calendar`, `dim_stock`, `dim_stock_name_hist`.
- Added DWD scripts for `dwd_stock_eod_price`, `dwd_stock_eod_valuation`, `dwd_fin_indicator`, `dwd_index_eod`.
- Encoded current scope parameters in SQL: `dwd_start_date=2019-01-01`, `fin_start_period=20170101`, `lookback_start_date=2018-01-01` default.

### Important Context
- Scripts are bootstrap BigQuery Standard SQL, not a final dbt/Airflow decision; OQ-005 remains open.
- BigQuery target datasets already exist in `asia-east2`, matching ODS. No script was executed to materialize tables.
- `dim_stock` still avoids reading `stock_basic_delisted.delist_date`; delist boundary comes from daily last trade date + 1.

### Files Changed
- `sql/README.md`
- `sql/00_create_datasets.sql`
- `sql/dim/01_dim_trade_calendar.sql`
- `sql/dim/02_dim_stock.sql`
- `sql/dim/03_dim_stock_name_hist.sql`
- `sql/dwd/01_dwd_stock_eod_price.sql`
- `sql/dwd/02_dwd_stock_eod_valuation.sql`
- `sql/dwd/03_dwd_fin_indicator.sql`
- `sql/dwd/04_dwd_index_eod.sql`
- `TODO.md`
- `.agent/memory/{ARCHITECTURE_MEMORY,DECISION_LOG,IMPLEMENTATION_STATUS,AGENT_HANDOFF}.md`

### Tests / Validation
- `bq show` confirmed `data-aquarium.ashare_ods` location is `asia-east2`.
- `bq query --dry_run` passed for dataset bootstrap and all DIM scripts.
- `bq query --dry_run` passed for `dwd_stock_eod_valuation` and `dwd_index_eod`.
- `dwd_stock_eod_price` and `dwd_fin_indicator` initially stopped at missing DIM dependencies; full-script dry-run passed after replacing DIM references with temporary empty tables. No BigQuery data was written.
- `git diff --check` passed.

### Blockers
- None for SQL generation. Physical table creation and QA are still pending.

### Next Recommended Step
- Execute scripts in `sql/README.md` order, then run QA checks for row counts, unique keys, partition ranges, suspension skeleton rows, and finance `visible_trade_date`.

### Memory Files Updated
- ARCHITECTURE_MEMORY、DECISION_LOG、IMPLEMENTATION_STATUS、AGENT_HANDOFF；TODO.md updated.

## Handoff Entry

Date: 2026-05-31
Agent ID: Codex
Agent Instance ID: Codex desktop session
Model: GPT-5
Runtime: Codex desktop
Run ID: —
Related issue/PR: —

### Work Completed
- Made the current scope explicit in `docs/数据仓库建模方案-DWD-DIM.md` front matter and TL;DR: current modeling target is A-share daily DWD/DWS from `2019-01-01` onward.
- Clarified that pre-2019 data is only support data for finance/event PIT, market lookback warm-up, and dimension/calendar history; formal pre-2019 modeling is future work.

### Important Context
- This did not change the scope decision in DECISION-20260531-11; it only made the scope visible at the top of the design document.

### Files Changed
- `docs/数据仓库建模方案-DWD-DIM.md`
- `.agent/memory/{IMPLEMENTATION_STATUS,AGENT_HANDOFF}.md`

### Tests / Validation
- Documentation-only change.

### Blockers
- None.

### Next Recommended Step
- Implement P0 SQL with `dwd_start_date=2019-01-01`, `fin_start_period=20170101`, and computed `lookback_start_date`.

### Memory Files Updated
- IMPLEMENTATION_STATUS、AGENT_HANDOFF。

## Handoff Entry

Date: 2026-05-31
Agent ID: Codex
Agent Instance ID: Codex desktop session
Model: GPT-5
Runtime: Codex desktop
Run ID: —
Related issue/PR: —

### Work Completed
- Corrected the previous overbroad “full-history write” interpretation after owner clarified current priority is 2019+ data.
- Updated `docs/数据仓库建模方案-DWD-DIM.md` §4.6 with a table separating: finance/event 2017 pull, market lookback buffer, and dimension/calendar historical support.
- Rewrote `docs/reviews/数据仓库建模方案-DWD-DIM-review-2019前数据范围修正.md` as a correction note.
- Superseded DECISION-20260531-10 and added DECISION-20260531-11 with the accurate current-phase scope.

### Important Context
- Current P0 output scope is 2019+.
- Finance/event ODS/DWD starts at `20170101` only to support 2019 PIT and YoY/base periods.
- Market data before 2019 is only read as a build buffer; buffer rows do not land in final DWD/DWS.
- `trade_cal`, `stock_basic`, and `namechange` use latest snapshots or full history because they are dimensions, not old market facts.

### Files Changed
- `docs/数据仓库建模方案-DWD-DIM.md`
- `docs/reviews/数据仓库建模方案-DWD-DIM-review-2019前数据范围修正.md`
- `TODO.md`
- `.agent/memory/{MEMORY_INDEX,PROJECT_CONTEXT,ARCHITECTURE_MEMORY,IMPLEMENTATION_STATUS,KNOWN_CONSTRAINTS,OPEN_QUESTIONS,DECISION_LOG,AGENT_HANDOFF}.md`

### Tests / Validation
- Documentation-only change; no SQL executed in this correction step.

### Blockers
- None for the scope correction.

### Next Recommended Step
- Implement P0 SQL with explicit parameters: `dwd_start_date=2019-01-01`, `fin_start_period=20170101`, and `lookback_start_date` derived from the max rolling window.

### Memory Files Updated
- MEMORY_INDEX、PROJECT_CONTEXT、ARCHITECTURE_MEMORY、IMPLEMENTATION_STATUS、KNOWN_CONSTRAINTS、OPEN_QUESTIONS、DECISION_LOG、AGENT_HANDOFF；TODO.md updated.

## Handoff Entry

Date: 2026-05-31
Agent ID: Agent_RD（数仓建模 / 评审）
Agent Instance ID: claude-opus-4.8 / Claude Code 会话
Model: Claude Opus 4.8
Runtime: Claude Code CLI
Run ID: —
Related issue/PR: —

### Work Completed
- 评审已提交的 P0 建表 SQL（commit 9942f14），产出评审文档 `docs/reviews/P0-建表SQL-review.md`（5 项发现，分级 + 依据/影响/建议 + 与决策一致性核对）。
- 按 owner 要求把「评审须产出 docs/reviews/ 评审文档、评审只读」固化为协议：AGENTS.md 新增「六、评审协议」+ DECISION-20260531-13。
- 记忆与代码同步提交（§四）。

### Important Context
- 评审 2 项物化前必修：①README `bq query` 缺 `--location=asia-east2`（`00_create_datasets` 无法自动推断区域，新环境落 US → 建集/跨区读 ODS 失败）；②`dwd_stock_eod_price` 的 `suspend_event` 未过滤 `suspend_d` 复牌行（`suspend_type='R'`），复牌日可能被误判 `is_suspended`（须先实跑核 `suspend_type` 取值域）。
- 3 项随 QA 补：`fina_indicator` 版本键精确去重兜底、`dim_stock` `sec_code` 唯一性断言 / 退市 heuristic、补 `dwd_fin_indicator_latest`。
- 评审与 active 决策无冲突（DECISION-04 印证 `visible_trade_date` 右移、DECISION-09 印证版本事实表与开盘侧方向字段）。
- 评审发现**尚未**转为 OQ/TODO —— 按新协议（§六）等 owner 决定。

### Files Changed
- `docs/reviews/P0-建表SQL-review.md`（新）、`AGENTS.md`（§六）、`.agent/memory/{DECISION_LOG,IMPLEMENTATION_STATUS,AGENT_HANDOFF}.md`。未改 `sql/`。

### Tests / Validation
- 纯静态评审，未跑 BQ；`suspend_d` 复牌行行为待实跑验证。

### Blockers
- 无硬阻塞；物化前建议先修 R1/R2。

### Next Recommended Step
- owner 决定评审发现是否转 TODO/OQ；随后按 `sql/README.md`（补 `--location`）物化 + QA，并先修 `suspend_event` 过滤。

### Memory Files Updated
- DECISION_LOG（加 13）、IMPLEMENTATION_STATUS、AGENT_HANDOFF；AGENTS.md §六。

## Handoff Entry

Date: 2026-05-31
Agent ID: Codex
Agent Instance ID: Codex desktop session
Model: GPT-5
Runtime: Codex desktop
Run ID: —
Related issue/PR: —

### Work Completed
- Fixed all accepted findings from `docs/reviews/P0-建表SQL-review.md`.
- Added explicit `--location=asia-east2` to `sql/README.md` execution commands.
- Updated `dwd_stock_eod_price` so `suspend_d` only treats `suspend_type='S'` as suspension; `R` resumption rows no longer mark `is_suspended`.
- Hardened `dim_stock`: latest `stock_basic` rows are de-duplicated by `sec_code`; `derived_from_daily` inferred delist dates use ODS latest market trade date with a 30-day grace instead of `CURRENT_DATE`.
- Added `dwd_fin_indicator` version-key dedup, `dwd_fin_indicator_latest`, and `sql/qa/01_p0_smoke_checks.sql`.

### Important Context
- No BigQuery DWD/DIM tables were materialized in this step.
- Verification found 2019 `suspend_d` has 585 `R` rows; 558 had same-day daily trading rows, confirming the original false-suspension risk.
- The derived `dim_stock` fallback now marks `000043.SZ` and `300114.SZ` as inferred delisted, while leaving latest-trade `920218.BJ` active under the 30-day grace rule.

### Files Changed
- `sql/README.md`
- `sql/dim/02_dim_stock.sql`
- `sql/dwd/01_dwd_stock_eod_price.sql`
- `sql/dwd/03_dwd_fin_indicator.sql`
- `sql/dwd/05_dwd_fin_indicator_latest.sql`
- `sql/qa/01_p0_smoke_checks.sql`
- `TODO.md`
- `.agent/memory/{MEMORY_INDEX,PROJECT_CONTEXT,ARCHITECTURE_MEMORY,IMPLEMENTATION_STATUS,KNOWN_CONSTRAINTS,DECISION_LOG,AGENT_HANDOFF}.md`

### Tests / Validation
- `bq query --dry_run --location=asia-east2` passed for dataset bootstrap and DIM scripts.
- `bq query --dry_run --location=asia-east2` passed for DWD scripts; scripts depending on unmaterialized DIM/DWD were validated with temporary empty replacement tables.
- `sql/qa/01_p0_smoke_checks.sql` dry-run passed with temporary replacement tables.
- Read-only BigQuery checks confirmed `suspend_type` distribution and derived `dim_stock` fallback behavior.
- `git diff --check` passed before memory updates; rerun before final response.

### Blockers
- None for SQL repair. Physical table creation and QA remain pending.

### Next Recommended Step
- Execute scripts in `sql/README.md` order, then run `sql/qa/01_p0_smoke_checks.sql`.

### Memory Files Updated
- MEMORY_INDEX、PROJECT_CONTEXT、ARCHITECTURE_MEMORY、IMPLEMENTATION_STATUS、KNOWN_CONSTRAINTS、DECISION_LOG、AGENT_HANDOFF；TODO.md updated.

## Handoff Entry

Date: 2026-05-31
Agent ID: Codex
Agent Instance ID: Codex desktop session
Model: GPT-5
Runtime: Codex desktop
Run ID: —
Related issue/PR: —

### Work Completed
- Executed P0 BigQuery build scripts in `sql/README.md` order.
- Materialized 3 DIM tables and 5 DWD tables in `data-aquarium.ashare_dim` / `data-aquarium.ashare_dwd`.
- Ran `sql/qa/01_p0_smoke_checks.sql`; all assertions passed after narrowing the resumption check to R-only rows without same-day S events.
- Updated `dwd_index_eod` to price-only because `ods_tushare_index_dailybasic` failed at runtime with Parquet type mismatches.

### Important Context
- `dwd_index_eod` currently does not read `index_dailybasic`; valuation/share fields are NULL until OQ-009 is resolved.
- Row counts after materialization: `dim_trade_calendar` 13,162; `dim_stock` 5,853; `dim_stock_name_hist` 3,776; `dwd_stock_eod_price` 8,495,462; `dwd_stock_eod_valuation` 8,452,073; `dwd_index_eod` 11,922; `dwd_fin_indicator` 332,960; `dwd_fin_indicator_latest` 198,030.
- Price/valuation/index DWD min trade date is 2019-01-02; finance min `ann_date_eff` is 2017-04-06.

### Files Changed
- `sql/README.md`
- `sql/dwd/04_dwd_index_eod.sql`
- `sql/qa/01_p0_smoke_checks.sql`
- `TODO.md`
- `.agent/memory/{MEMORY_INDEX,PROJECT_CONTEXT,ARCHITECTURE_MEMORY,IMPLEMENTATION_STATUS,KNOWN_CONSTRAINTS,OPEN_QUESTIONS,DECISION_LOG,AGENT_HANDOFF}.md`

### Tests / Validation
- All build scripts executed with `bq query --use_legacy_sql=false --location=asia-east2`.
- `sql/qa/01_p0_smoke_checks.sql` passed all assertions.
- Queried row counts and date ranges for every materialized P0 table.
- `git diff --check` should be rerun before final/commit.

### Blockers
- OQ-009: `index_dailybasic` external table has Parquet type mismatches (`float_mv`, `float_share`, likely more), blocking index valuation fields.

### Next Recommended Step
- Add P0/P1 finance statement DWDs (`income`, `balancesheet`, `cashflow`) or start DWS feature/label build on the materialized P0 tables.

### Memory Files Updated
- MEMORY_INDEX、PROJECT_CONTEXT、ARCHITECTURE_MEMORY、IMPLEMENTATION_STATUS、KNOWN_CONSTRAINTS、OPEN_QUESTIONS、DECISION_LOG、AGENT_HANDOFF；TODO.md updated.
