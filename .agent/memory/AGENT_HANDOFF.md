# Agent 交接（Agent Handoff）

本文件保存供后续 Agent 使用的最新交接记录。新交接用 `templates/HANDOFF_TEMPLATE.md` 追加到底部，并同步刷新下面的「当前交接摘要」。

## 当前交接摘要

`quant-ashare` 已完成**核心设计阶段**并落地 P0 DIM/DWD 建表 SQL：ODS 当前 56 表（新增 `index_member_all` / `ci_index_member`）探查清楚三类分区语义；产出 DWD/DIM 建模方案 `docs/数据仓库建模方案-DWD-DIM.md`、DWS/ADS 表设计 `docs/数据仓库建模方案-DWS-ADS.md`、策略方案 `docs/A股中低频小资金机器学习策略方案.md`。全套规范已敲定：`sec_code` 主键、单位元/股、`ann_date_eff`/`visible_trade_date` PIT、后复权 `_hfq`、行业归属用 `in_date/out_date` 时点区间、血缘 `source_system/ingested_at`、版本字段 `feature_version/label_version/universe_version/model_id/strategy_id/run_id`、按月分区 + 聚簇、表+字段注释。owner 已澄清：当前阶段先把 **2019+ 数据**做正确；2019 年以前正式样本/明细是下一步。主方案 §4.6 已修订为三类 2019 前支撑范围：财务/事件前移到 2017、行情仅读 lookback buffer、维度/日历取快照或全量历史事件。

**已落地 SQL**：`sql/00_create_datasets.sql`、`sql/dim/01_dim_trade_calendar.sql`、`sql/dim/02_dim_stock.sql`、`sql/dim/03_dim_stock_name_hist.sql`、`sql/dwd/01_dwd_stock_eod_price.sql`、`sql/dwd/02_dwd_stock_eod_valuation.sql`、`sql/dwd/03_dwd_fin_indicator.sql`、`sql/dwd/04_dwd_index_eod.sql`。所有脚本已 dry-run 校验；price/finance 因 DIM 尚未物化，用临时空维表替换方式完成完整语法校验。未实际写 BigQuery。

**DWS/ADS 设计**：P0 DWS 包含 `dws_stock_universe_daily`、价格/估值/财务特征、`dws_market_state_daily`、`dws_stock_label_daily`、`dws_stock_feature_daily_v0`、`dws_stock_sample_daily`。P1 行业路径已可落地：`dim_stock_sw_industry_hist` 使用 `index_member_all`，`dim_stock_ci_industry_hist` 使用 `ci_index_member`，历史 join 用 `in_date/out_date`，`is_new` 仅标当前归属。P0 ADS 包含训练面板、模型注册、预测、候选池、组合目标、订单计划、回测成交/持仓/NAV/绩效、信号监控。首个策略为 `ml_ranker_v0`：P0 特征横截面排序，长-only，`t` 日盘后信号、`t+1` 开盘/VWAP 建仓。

**下一步（P0）**：按 `sql/README.md` 执行 DIM/DWD 建表脚本并做基础 QA（行数、主键重复、分区范围、停牌骨架、PIT 可见日）；随后编写 P0 DWS/ADS SQL 并跑通 `ml_ranker_v0` 基线。关键参数：`@dwd_start_date = DATE '2019-01-01'`、`@fin_start_period = '20170101'`、`@lookback_start_date = DATE '2018-01-01'` 默认；后续应把 lookback 改为按最大滚动窗口计算。

**待 owner 确认**：dbt vs 纯 SQL（OQ-005）；P0 策略成本/调仓/持股数/北交所/训练工具链默认参数（OQ-009）。OQ-001 已关闭：行业映射 ODS 已补采。

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
- Created branch/worktree `docs/dws-ads-strategy` at `/Users/luna/Desktop/git/quant-ashare-dws-ads-docs` from current `main` HEAD `9942f14`.
- Added DWS/ADS design document `docs/数据仓库建模方案-DWS-ADS.md`.
- Added strategy design document `docs/A股中低频小资金机器学习策略方案.md`.
- Recorded DWS/ADS table families, ADS consumption tables, and first baseline strategy `ml_ranker_v0`.

### Important Context
- Current BigQuery `ashare_ods` still has 54 external tables / 1492 columns.
- `ashare_dim` and `ashare_dwd` datasets exist but currently have no materialized tables; `ashare_dws` and `ashare_ads` datasets do not exist yet.
- P0 DWS/ADS design depends on P0 DIM/DWD materialization first.
- `ml_ranker_v0` assumes t-day close features, t+1 open/VWAP entry, long-only, 5/10 day rank labels.

### Files Changed
- `docs/数据仓库建模方案-DWS-ADS.md`
- `docs/A股中低频小资金机器学习策略方案.md`
- `TODO.md`
- `.agent/memory/{MEMORY_INDEX,PROJECT_CONTEXT,ARCHITECTURE_MEMORY,IMPLEMENTATION_STATUS,DECISION_LOG,OPEN_QUESTIONS,GLOSSARY,AGENT_HANDOFF}.md`

### Tests / Validation
- Documentation-only change.
- Rechecked BigQuery metadata: `ashare_ods` = 54 tables / 1492 columns; `ashare_dws` and `ashare_ads` datasets not found.

### Blockers
- None for documentation.
- OQ-009 added for owner confirmation of P0 strategy defaults.

### Next Recommended Step
- Execute and QA P0 DIM/DWD SQL, then write P0 DWS/ADS SQL and run `ml_ranker_v0` baseline backtest.

### Memory Files Updated
- MEMORY_INDEX、PROJECT_CONTEXT、ARCHITECTURE_MEMORY、IMPLEMENTATION_STATUS、DECISION_LOG、OPEN_QUESTIONS、GLOSSARY、AGENT_HANDOFF；TODO.md updated.

## Handoff Entry

Date: 2026-05-31
Agent ID: Codex
Agent Instance ID: Codex desktop session
Model: GPT-5
Runtime: Codex desktop
Run ID: —
Related issue/PR: —

### Work Completed
- Rechecked BigQuery ODS after owner reported industry member tables were added.
- Verified `ashare_ods` now has 56 tables / 1532 columns.
- Verified new tables `ods_tushare_index_member_all` and `ods_tushare_ci_index_member` have `l1/l2/l3` industry fields, `ts_code`, `in_date`, `out_date`, `is_new`.
- Updated DWD/DIM, DWS/ADS, and strategy docs to use industry time-range mappings instead of treating industry mapping as a missing data gap.
- Closed OQ-001 and recorded DECISION-20260531-14.

### Important Context
- `index_member_all` has endpoint `index_member_all`, latest partition `20260531`, and contains full history ranges.
- `ci_index_member` has endpoint `ci_index_member`, latest partition `20260531`, and contains full history ranges.
- Historical industry joins must use `in_date/out_date`; `is_new='Y'` is current-only and must not be used for backtest history.
- Default interval rule is `[valid_from, valid_to)`; SQL implementation should QA `out_date` boundary and overlapping/gapped intervals.

### Files Changed
- `docs/数据仓库建模方案-DWD-DIM.md`
- `docs/数据仓库建模方案-DWS-ADS.md`
- `docs/A股中低频小资金机器学习策略方案.md`
- `TODO.md`
- `.agent/memory/{PROJECT_CONTEXT,ARCHITECTURE_MEMORY,IMPLEMENTATION_STATUS,KNOWN_CONSTRAINTS,OPEN_QUESTIONS,DECISION_LOG,AGENT_HANDOFF}.md`

### Tests / Validation
- BigQuery metadata query confirmed `ashare_ods` table count 56 and column count 1532.
- `INFORMATION_SCHEMA.COLUMNS` verified the two new ODS tables' schemas.
- Sample rows verified `endpoint`, `in_date`, `out_date`, `is_new`, and L1/L2/L3 fields exist.

### Blockers
- None for documentation.
- SQL implementation still needs interval QA before production use.

### Next Recommended Step
- Add SQL for `dim_stock_sw_industry_hist` and `dim_stock_ci_industry_hist`, then use those dims in P1 `dws_stock_feature_industry_daily`.

### Memory Files Updated
- PROJECT_CONTEXT、ARCHITECTURE_MEMORY、IMPLEMENTATION_STATUS、KNOWN_CONSTRAINTS、OPEN_QUESTIONS、DECISION_LOG、AGENT_HANDOFF；TODO.md updated.

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
