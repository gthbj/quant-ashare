# Agent 交接（Agent Handoff）

本文件保存供后续 Agent 使用的最新交接记录。新交接用 `templates/HANDOFF_TEMPLATE.md` 追加到底部，并同步刷新下面的「当前交接摘要」。

> **语言约定（2026-06-01 起）**：新增交接条目一律用中文撰写；下方此前的英文历史条目保留原样作为记录，不回译。

## 当前交接摘要

`quant-ashare` 已完成 P0 DIM/DWD 物化、OQ-004 指数基准口径、策略 1 DWS/ADS、策略 1 BigQuery ML runner 端到端实跑、OQ-006 单位契约、OQ-003 财务三表 DWD/DWS、OQ-010 交易成本 profile、策略 1 中文报告与归因分析、策略 1 报告 GCS uploaded 模式，以及策略 1 模型质量诊断 PRD。2026-06-02 已创建 `gs://ashare-artifacts`（`ASIA-EAST2`）、配置本机 ADC（quota project=`data-aquarium`）、去掉 `--skip-gcs-upload` 重跑 `render_report.py`，ADS 已回写 `report_upload_status=uploaded` 和真实 `report_uri=gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_bqml_20260601_01/backtest_id=bt_s1_bqml_20260601_01`，`sql/ml/strategy1/10_qa_runner_outputs.sql` 全部通过。`docs/prd/PRD_20260602_04_策略1模型质量诊断.md` 已定义下一步先诊断 signal / label / sample-universe / candidate / portfolio / cost / style，再进入 OQ-010 参数和模型实验；PR #24 comment feedback 已补入正文，RankIC 明确为 Spearman、bucket 明确为日截面 quantile、`sample_filter_risk` 阈值明确只针对不可解释排除率。核心规范保持：`sec_code` 主键、单位元/股、`ann_date_eff`/`visible_trade_date` PIT、后复权 `_hfq`、行业归属时点区间、血缘与版本字段、按月分区 + 聚簇；当前阶段先把 2019+ 数据做正确，2019 年以前正式样本/明细是下一步。

**已物化表**：`data-aquarium.ashare_meta` 下 `ods_field_unit_map`；`data-aquarium.ashare_dim` 下 `dim_trade_calendar`、`dim_stock`、`dim_stock_name_hist`、`dim_index`；`data-aquarium.ashare_dwd` 下 `dwd_stock_eod_price`、`dwd_stock_eod_valuation`、`dwd_fin_indicator`、`dwd_fin_indicator_latest`、`dwd_index_eod`，以及 OQ-003 财务三大报表 `dwd_fin_income`/`dwd_fin_balancesheet`/`dwd_fin_cashflow` 及各自 `_latest`（PR #13）；`data-aquarium.ashare_dws` 下策略 1 六表（universe、价格特征、估值特征、标签、特征宽表、样本表）和 `dws_stock_feature_fin_daily`（默认合并口径 PIT 财务特征，PR #13）；`data-aquarium.ashare_ads` 下 11 张训练/预测/组合/回测/监控契约表。PR #9 合并后的 `dim_stock` 依赖链已在 2026-06-02 重建：`dim_stock`、`dwd_stock_eod_price`、策略 1 DWS 六表和 ADS 契约表均已刷新，`sql/metadata/01_p0_table_column_descriptions.sql` 已执行，`sql/qa/01_p0_smoke_checks.sql` 与 `sql/qa/02_strategy1_dws_ads_checks.sql` 均通过；`sql/qa/03_oq004_index_checks.sql` 近期通过。二轮评审发现已修复：盘中临停不再误标全天停牌，财务 latest 改为 `update_flag DESC` 优先。P0 DIM/DWD 字段说明缺失数为 0。

**评审协议（2026-06-01 更新）**：评审已提交代码/SQL 或设计文档时，GitHub PR review 默认写 PR comment；一条写不下拆多条。只有 owner 明确要求或无 PR comment 承载面时，才另写 `docs/reviews/` 评审文档。评审只读——不擅改被评审对象、不把发现直接写进 `.agent/memory/**`/`TODO.md`，发现是否转 OQ/TODO/决策由 owner 定（AGENTS.md §六 / DECISION-20260601-03）。历史 `docs/reviews/P0-建表SQL-review.md` 等评审文档保留作审计记录。

**重要执行结果**：`dim_stock` 5,853 行，其中 326 个退市股使用 ODS `stock_basic_delist_date`；`dwd_stock_eod_price` 8,506,688 行；`dwd_stock_eod_valuation` 8,452,073 行；`dwd_fin_indicator` 332,960 行；`dwd_fin_indicator_latest` 198,030 行；`dim_index` 7 行；`dwd_index_eod` 11,922 行，其中 8,899 行有 `index_dailybasic` 估值/市值/股本字段，且沪深300已归一为 `sec_code='000300.SH'` / `source_sec_code='399300.SZ'`。`dim_index` 当前记录：SSE50、CSI300、STAR50、CSI1000、CSI500、深证成指、创业板指；`000852.SH` 可作收益 benchmark，但 `has_dailybasic=FALSE`。策略 1 DWS 行数：universe 8,506,688 行、价格特征 8,506,688 行、估值特征 8,452,073 行、标签 8,506,688 行、特征宽表 8,506,688 行、样本表 8,506,688 行（默认可训练 3,274,084 行）。上游已修复 `index_dailybasic` Parquet 类型问题，OQ-009 已关闭；STAR50/CSI1000 因 ODS 无 dailybasic endpoint 仍为空。2026-06-02 已应用 PR #9 的 ODS 正式退市日口径并完成依赖重建。

**DWS/ADS 设计与已落地范围**：P0 DWS 设计包含 `dws_stock_universe_daily`、价格/估值/财务特征、`dws_market_state_daily`、`dws_stock_label_daily`、`dws_stock_feature_daily_v0`、`dws_stock_sample_daily`；当前策略 1 已落地 universe、价格/估值特征、open-to-close 标签（rank/xs return 按默认 universe 截面计算）、特征宽表、样本表，以及 OQ-003 财务特征 `dws_stock_feature_fin_daily`；市场状态 `dws_market_state_daily` 待补。财务特征口径 PRD 已采纳、关闭并实现 OQ-003（PR #13）：P0 默认消费合并报表 `report_type='1'`，三大报表 DWD（`income/balancesheet/cashflow` + `_latest`）保留 `report_type`/`report_caliber`/`is_default_report_caliber`，`dws_stock_feature_fin_daily` 默认只过滤默认口径（口径契约 + `has_fin_*` 掩码），已物化并通过 `sql/qa/04_finance_caliber_checks.sql`，并按 OQ-006 单位契约补全 `ods_field_unit_map` 财务字段、跑通 `sql/qa/05_oq006_unit_checks.sql`。PR #4 comment 的 P1/P2 已跟进：`label_valid` 语义说明、去冗余 JOIN、最早可训练样本日 QA、DWD 字段名文档同步。P1 行业路径已可落地：`dim_stock_sw_industry_hist` 使用 `index_member_all`，`dim_stock_ci_industry_hist` 使用 `ci_index_member`，历史 join 用 `in_date/out_date`，`is_new` 仅标当前归属。P0 ADS 表契约已落地。策略 1 PRD 名称为 `ml_pv_clf_v0`；首个基线默认股票池仅沪深主板（`SSE_MAIN` / `SZSE_MAIN`），不含北交所、创业板、科创板；runner 设计 `docs/策略1-ml_pv_clf_v0-runner设计.md`、runner 实现 PRD `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md` 和 runner SQL 已完成，执行路径为 BigQuery ML + SQL：训练面板、BQML model object、预测、候选、组合、订单、回测、监控均写既有 ADS 表。**runner 已于 PR #12 端到端实跑并通过全部 QA**（08 已重写为账户级 ledger，详见本文件末尾 2026-06-02 交接条目与摘要顶部）。

**下一步（P0/P1）**：优先按 `docs/prd/PRD_20260602_04_策略1模型质量诊断.md` 实现策略 1 v0 模型质量诊断，再基于诊断结论推进调仓频率、持股数/单票权重上限、特征/标签/选股口径实验；也可补 P0 通用 `dws_market_state_daily`。P1 再做三大报表单季 `q_*` 派生、行业/资金/事件特征扩展。关键参数：`@dwd_start_date = DATE '2019-01-01'`、`@fin_start_period = '20170101'`、`@lookback_start_date = DATE '2018-01-01'` 默认；后续应把 lookback 改为按最大滚动窗口计算，并决定是否补 lookback-capable 价格构建输入（OQ-011）。

**待 owner 确认**：dbt vs 纯 SQL（OQ-005）；P0 策略调仓频率、持股数/单票权重上限（OQ-010，成本子项已定、策略报告已定为中证1000评估主基准 + 沪深300展示对比基准、训练工具链已定为 BigQuery ML + SQL runner，首个基线股票池已定为仅沪深主板）；是否补 lookback-capable 价格构建输入以填满 2019-01 起 60 日窗口（OQ-011）。OQ-001/OQ-003/OQ-004/OQ-006/OQ-007 已关闭。

**TODO / OQ 维护约定**：`TODO.md` 只保留下一步可执行事项和少量近期完成项；待 owner 决策的问题以 `.agent/memory/OPEN_QUESTIONS.md` 为唯一来源，TODO 仅引用 OQ 编号和对应行动。

**分支卫生**：PR 合并后，若 owner 未要求保留工作分支，应删除已合并且不再使用的 `codex/*` 本地分支和对应远端分支。`codex/implement-strategy1-prd` 和 `codex/implement-oq004-index` 已在本地和远端删除。

> 历史交接已归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-05.md`。常规启动只需阅读本文件的当前摘要和最近交接；归档仅用于审计追溯。

---

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
