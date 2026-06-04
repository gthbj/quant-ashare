# Agent Handoff Archive 2026-06

本文件归档 2026-06 的历史交接条目。当前交接摘要和最近交接见 `../AGENT_HANDOFF.md`。

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
