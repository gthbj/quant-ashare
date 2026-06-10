> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 新增 `docs/prd/PRD_20260610_03_策略1年度滚动选参.md`。
> - PRD 定义年度 walk-forward 参数选择：上一整年 valid 选择参数，选中参数在最近 5 年 final refit，再回测下一年；2021-2026 结果必须用年度预测合并后的一条连续 ledger 评价。
> - P0 固定 feature set、20 只、7.5% 单票上限、biweekly 和 `ledger_exec_v1_lot100`，只搜索 12 个冻结 LightGBM 参数候选。
> - valid 选参门按 owner 确认口径写入：去掉 `valid_total_return > 0`，最大回撤线为 `>= -33.33%`，五指数任一超额收益 `> 0`，五指数任一 Excess Calmar Ratio `> 0.3`。
> - 本轮只写方案和同步 `.agent/memory/IMPLEMENTATION_STATUS.md`、`.agent/memory/AGENT_HANDOFF.md`、`.agent/memory/DECISION_LOG.md`、`TODO.md`；未改代码、SQL、BigQuery、Cloud Run 或 Dataform。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 新增 `docs/prd/PRD_20260610_02_项目结构重构方案.md`，作为 `quant-ashare` 项目结构重构总 PRD。
> - Owner 已确认关键决策：采用 `ashare_research` dataset、`research_*` 表名前缀、`accepted != promoted`、先 table-role abstraction 后 research-first、`sql/strategy1/**` 目标 SQL 命名空间、`src/quant_ashare/**` Python 包根、短期保留 `scripts/strategy1_cloudrun/**` wrapper，且 P0 不强制创建 `docs/retired/`。
> - PRD 已改为已确认口径；新实验、候选、诊断和 acceptance replay 目标态默认写 research，`ashare_ads` 只承载 owner promotion 后的正式产物。
> - Review 指出的 `sql/cloudrun/strategy1/01_build_training_panel.sql`、ADS 硬编码耦合、retired linter allowlist、SQL `DECLARE p_*` 参数默认值漂移、`optional_params` schema 语义、`16-25` 逐个分类、`bqml_reference_run_id` exception registry 和 Python package 交付方式均已补进 PRD。
> - 本轮只写方案和同步 `.agent/memory/IMPLEMENTATION_STATUS.md`、`.agent/memory/AGENT_HANDOFF.md`、`.agent/memory/DECISION_LOG.md`、`TODO.md`；未改代码、SQL、BigQuery、Cloud Run 或 Dataform。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #134 已从 PRD-only 扩展为实现分支：新增 Strategy1 回测 `compound_annual_return`、`return_period_count`、`annualization_target_period_count`、`annualization_method` 字段与 ADS additive migration。
> - `09` summary、`10` runner QA、`24` v3 replay QA、`render_report.py` 与 `replay_acceptance_gate_v3.py` 已切到 NAV 首尾值 + NAV 有效交易日数减一的复合年化口径；legacy `annual_return` / `sharpe` 保留旧算术口径并显式标注。
> - PR #134 review follow-up 已修复 `total_return = -100%` 边界：SQL、report 和 v3 replay 统一允许 `gross == 0` 返回复合年化 `-100%`，仅拒绝 `gross < 0`。
> - 未运行 BigQuery / Cloud Run / pytest；后续需要 owner 决定是否部署 schema migration、是否重跑 2020-2022 R14 hold=10/20 报告或生成 sidecar，以及是否调整 compound Sharpe / Calmar 阈值。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #131 分支已完成 Strategy1 旧 BQML / SQL ledger runner P0 退役实现。
> - 已删除 BQML-only `sql/ml/strategy1/02-04`、SQL ledger fallback `08_run_backtest.sql` 和旧 `scripts/strategy1/run_oq010_experiments.py`；Cloud Run Python runner 已移除 `--use-bq-ledger` 参数和透传。
> - 当前 active path 收口为 Cloud Run Python training / prediction / ledger + 共享 SQL `01`、`05-07`、`09-10`、`12`、`16-24`；未运行 BigQuery / Cloud Run / pytest。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #132 已合并，`ashare-pipeline-control` 已重新部署到 revision `ashare-pipeline-control-00007-tst`。
> - 重新触发 2015 年 backfill execution `209bd2bf-86f4-455c-85c7-b6b1f4ec8025`，已越过 `dim_stock` 生命周期缺口。
> - 新失败点在 `sql/qa/01_core_smoke_checks.sql`：旧 core smoke 仍把 `2019-01-01` 当成 DWD 价格表全表存在下限；分支 `codex/fix-historical-backfill-core-smoke` 已改为只拒绝早于 `1990-12-19` 的异常行，`daily_current` 2019+ 下限继续由窗口 SQL/QA 约束。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #130 合并并部署 `ashare-pipeline-control` 后，重跑 2015 年 backfill execution `be12a12f-1e65-4cef-b60d-3945ef8da13a`，已越过指数窗口旧失败点。
> - 新失败点在股票窗口 QA `QA-WIN-13`：2015 ODS daily 有 `5,486` 行、`76` 个代码未写入 `dwd_stock_eod_price`。
> - 分支 `codex/fix-historical-dim-stock-lifecycle` 已修复 `dim_stock` 历史生命周期：缺主数据代码从全量 ODS daily 派生，`stock_basic.list_date` 晚于首个日线交易日时用 `first_trade_date` 兜底；PR #132 review follow-up 已改为直接复用 `daily_lifecycle`，避免重复全量扫描 ODS daily。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #127 review follow-up 已修复 Cloud Run ledger resume 代码断链：`LedgerParams`/manifest/CLI/SQL metadata 贯通，Python ledger 写入并恢复 `ads_backtest_ledger_state_daily`，`25` QA 改为 `ashare_ads` 与当前 ADS 字段。
> - 未运行测试、BigQuery 或 Cloud Run smoke；后续需要按 owner 指令做最小验证。

> 当前交接补充（2026-06-09，GPT-5 Codex）
> - 手工触发 2015 年 `ashare_warehouse_window_refresh` backfill 时失败，根因是窗口刷新 SQL 固定以 `2019-01-01` 作为写入下限，导致 `2015-01-01 ~ 2015-12-31` 被推成 `write_start=2019-01-01`。
> - 分支 `codex/fix-2015-index-backfill` 已将股票、指数、market-state 窗口刷新及股票/指数窗口 QA 改为按 `warehouse_mode` 区分日期下限：`daily_current` 保持 2019+，显式 `backfill` 允许 2019 年以前历史窗口。
> - 合并并部署后，下一步重新触发 2015 年窗口补数；2015 成功后再按年触发 2016、2017、2018。

> 当前交接补充（2026-06-09，GPT-5 Codex）
> - 新增 `docs/prd/PRD_20260609_01_策略1R14长训练回测.md`。
> - PRD 固定当前 R14 LightGBM regression 方法，不重新搜索参数，名义训练窗口为 `2015-04-01 ~ 2019-12-31`，先跑 `2020-01-02 ~ 2022-12-30` 的 `10` 只 / `20` 只双组合 diagnostic backtest；`2023-01 ~ 2026-06-09` 追加回测视 P0 结果和 owner 决策而定，若追加也跑两个组合。
> - 关键边界：训练必须做 5d label embargo，避免 2019 年末训练样本使用 2020 回测期收益；追加段不能和 `2020-2022` fresh segment 拼接成正式连续回测，除非 Cloud Run Python ledger resume 已实现并通过 resume consistency QA。

> 当前交接补充（2026-06-09，GPT-5 Codex）
> - 旧 Composer-era 补跑 helper `scripts/pipeline/run_warehouse_refresh.py` 已删除。
> - 该脚本仍通过 `gcloud composer environments run` 触发已退役的 `ashare-composer`，与当前 `Cloud Scheduler + Cloud Workflows` 生产入口冲突。
> - 后续窗口补跑 / QA-only / full rebuild 恢复路径继续以 `docs/Pipeline-补跑与故障恢复-Runbook.md` 和 `orchestration/workflows/**` 为准。
> - PR #129 review follow-up 已同步清理 `.agent/memory/OPEN_QUESTIONS.md` 中对旧 helper 的现行工具描述。

> 当前交接补充（2026-06-09，GPT-5 Codex）
> - Strategy1 Cloud Run Python live acceptance gate 已在分支 `codex/implement-v3-live-gate` 从 v1 切到 v3。
> - live orchestrator 现在会在 ADS 写回前按实际 backtest span / manifest final_holdout window 重算五指数相对门、复合年化、Sharpe / Calmar 和 final_holdout 诊断字段，并写入 registry、backtest summary 与 comparison artifact。
> - PR #125 分支已完成 2 候选 live v3 smoke：prepare、candidate fanout、select/register/predict、backtest/report、19 QA 和 artifact 上传均 succeeded；smoke 中发现并修复了 `v3_relative_gate_by_benchmark.csv` 的 `search_id` 透传缺口。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - `TODO.md` 已从“完成历史 + 进行中事项混排”重写为短版，只保留当前可执行事项。
> - 当前 TODO 只剩 3 个主动作：OQ-005 补短观察窗记录、OQ-010 继续找 accepted Python baseline、OQ-012 决定是否正式归档关闭。
> - 完成历史不再放在 `TODO.md`，统一回到 `IMPLEMENTATION_STATUS.md` / `AGENT_HANDOFF.md` / `OPEN_QUESTIONS.md`。

> 当前交接补充（2026-06-09，GPT-5 Codex）
> - PR #124 review 指出 active on-call runbook 仍指向已删除的 `ashare-composer`；该问题已处理。
> - `docs/Pipeline-补跑与故障恢复-Runbook.md` 已改写为 Scheduler + Workflows 版恢复手册，当前恢复命令使用 Workflows executions、Scheduler jobs、Cloud Run Jobs 和 BigQuery 状态表。
> - `scripts/alerting/README.md` 与 `scripts/alerting/setup_alerts.py` 也已同步，不再把 alert checker 部署/故障描述指向 Composer。

> 当前交接补充（2026-06-09，GPT-5 Codex）
> - 2026-06-09 20:00 scheduled ODS workflow 已触发，但先后暴露 Cloud Run Job 权限缺口：缺 `run.jobs.runWithOverrides` 和 `run.operations.get`。
> - live IAM 已补：`ashare-ingest-current-scope` job-level `roles/run.jobsExecutorWithOverrides`，以及 workflows runtime SA 的 project-level `roles/run.viewer`。
> - `bootstrap_scheduler_iam.sh` 已同步改成该真实权限口径，避免后续 bootstrap 回到错误的 job-level `run.invoker`。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - OQ-005 已完成 production cutover：生产调度入口固定为 `Cloud Scheduler + Cloud Workflows`，`ashare-composer` 环境已删除，Composer 业务 DAG 不再是现行生产路径。
> - `orchestration/composer/` 已收口为 retired / audit-only 历史目录，只保留审计、迁移对照和受控回滚参考价值。
> - Strategy1 `v3` replay 与 helper 驱动的 `24` QA 已按最新 contract 真执行通过；当前真正开放的主线只剩 OQ-010 可接受 Python baseline 和 OQ-012 是否正式归档。

## 当前交接摘要

- 2026-06-10：新增 Strategy1 年度滚动选参 PRD `docs/prd/PRD_20260610_03_策略1年度滚动选参.md`；P0 固定 12 个 LightGBM 参数候选、20 只持仓、7.5% 单票上限、biweekly 和 `ledger_exec_v1_lot100`，每年用上一整年 valid 选参数，再用最近 5 年 final refit，最终用年度预测合并后的一条连续 ledger 评价 `2021-2026`。
- 2026-06-10：新增项目结构重构总 PRD `docs/prd/PRD_20260610_02_项目结构重构方案.md`；owner 已确认采用 `ashare_research` / `research_*` / `accepted != promoted`、`sql/strategy1/**`、`src/quant_ashare/**`、短期保留 `scripts/strategy1_cloudrun/**` wrapper，且 P0 不强制创建 `docs/retired/`。实施顺序为先做 active path catalog、防误用护栏和 table role / dataset role resolver，再迁移 Strategy1 active shared SQL（同时覆盖 `sql/ml/strategy1/**` 与 `sql/cloudrun/strategy1/**`）到 `sql/strategy1/**`，随后抽 Strategy1 package foundation，最后再分段实现 `ashare_research` / `ashare_ads` 生命周期隔离和 deeper package split。
- 2026-06-10：新增 Strategy1 回测复合年化收益 PRD，范围为 summary / report / v3 gate 的复利年化字段口径；本 PR 不改代码、不跑 BigQuery / Cloud Run。
- OQ-005 当前状态：`ashare-ods-ingestion-daily`（`0 20 * * *`）与 `ashare-pipeline-alert-checker`（`0 * * * *`）两个 Scheduler job 已是唯一生产调度入口，ODS parent -> warehouse child、alert checker、manual full rebuild dry-run 都已有 live smoke 证据。
- OQ-005 代码边界：`orchestration/workflows/**` 是唯一现行调度实现面；`orchestration/composer/**` 只保留历史快照，不再接受新的生产逻辑或运维 runbook 变更；旧 Composer-era 补跑 helper `scripts/pipeline/run_warehouse_refresh.py` 已删除。
- Strategy1 当前状态：`v3` acceptance gate replay/QA 已 contract-driven 收口并通过；旧 BQML-only `02-04`、SQL ledger fallback `08` / `--use-bq-ledger` 和旧 `run_oq010_experiments.py` 已在 PR #131 分支退役删除；当前没有 accepted Python baseline，OQ-010 仍然 open；R14 长训练补数已越过历史 backfill 日期下限和 `dim_stock` 生命周期问题，但 2015 年重跑又暴露 core smoke 2019 全表下限误杀，需合并部署 `codex/fix-historical-backfill-core-smoke` 后再重跑 2015 年窗口。
- OQ-012 当前状态：schema contract / repair tooling / QA 都已具备，当前 BigQuery 读层无 mismatch 报警；剩余是 owner 是否把该问题正式关闭或保留防复发工程项。
- 下一步：owner review 年度滚动选参 PRD 后，若认可，先实现 2021 单年度 smoke，再跑完整 2021-2026 annual walk-forward 参数选择与连续 ledger 对比。


# Agent 交接（Agent Handoff）

本文件只保留当前交接摘要和最近 3 条交接。更早内容已归档到 `archive/AGENT_HANDOFF_2026-06.md`。

> **语言约定（2026-06-01 起）**：新增交接条目一律用中文撰写；更早的英文条目保留在 archive 中，不再放回当前文件。


## 2026-06-10 GPT-5 Codex - Strategy1 年度滚动选参 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260610_03_策略1年度滚动选参.md`。
- PRD 定义年度 walk-forward 参数选择方案：用上一整年 valid 选择参数和方向，再用选中参数在最近 5 年 final refit，预测并回测下一年。
- 年度窗口固定为 `2021` 至 `2026`：从 `2015-2019 train / 2020 valid / 2016-2020 final refit / 2021 backtest` 开始逐年滚动。
- P0 固定 feature set、股票池、成本、`20` 只持仓、`7.5%` 单票上限、`biweekly` 和 Cloud Run Python `ledger_exec_v1_lot100`，只搜索 12 个预先冻结的 LightGBM 参数候选。
- valid 选参门按 owner 确认口径写入：`valid_rank_ic > 0`、`valid_top_minus_bottom > 0`、五指数任一 valid 超额收益 `> 0`、valid 最大回撤 `>= -33.33%`、`valid_sharpe >= 0.3`、`valid_calmar >= 0.3`、五指数任一 `valid_excess_calmar_ratio > 0.3`，且不要求 `valid_total_return > 0`。
- PRD 明确年度预测可分年生成，但最终评价必须来自一条连续 ledger，不能拼接每年 fresh-run。
- 同步更新 `IMPLEMENTATION_STATUS`、`AGENT_HANDOFF`、`DECISION_LOG` 和 `TODO`。

### 重要上下文

- 本轮是 PRD-only，不改 runner、不改 SQL、不运行 BigQuery / Cloud Run / Dataform。
- 该方案和刚完成的固定 R14 annual walk-forward 不同：固定 R14 只验证一个参数；本文要求每年从固定候选池中重新选参数。
- valid 年只用于选择下一年参数，不能作为同年最终样本外成绩。
- 候选池必须先冻结并生成 hash；如果后续新增候选，必须新开 experiment version。

### 改动文件

- `docs/prd/PRD_20260610_03_策略1年度滚动选参.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

### 测试 / 验证

- 未执行。此次为 PRD 与项目记忆更新。

### 阻塞项

- 无代码阻塞。

### 下一步建议

- owner review PRD。若认可，先实现 `2021` 单年度 smoke，再扩展到完整 `2021-2026` annual walk-forward 参数选择和连续 ledger 对比。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - 项目结构重构总 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260610_02_项目结构重构方案.md`。
- Review follow-up 后，PRD 将项目结构重构拆为：active path catalog 与防误用护栏、table role / dataset role resolver、Strategy1 shared SQL 稳定命名空间、Python package foundation、`ashare_research` / `ashare_ads` 生命周期隔离、深层包拆分与阶段性命名收敛。
- Owner 已确认 PRD 关键决策：新增 BigQuery `ashare_research` dataset，使用 `research_*` 表名前缀，`accepted != promoted`，先做 table-role abstraction 后 research-first，采用 `sql/strategy1/**` 和 `src/quant_ashare/**`，短期保留 `scripts/strategy1_cloudrun/**` wrapper，P0 不强制创建 `docs/retired/`。
- PRD 明确旧 BQML-only SQL / SQL ledger runner 已按前置 PRD 退役；当前剩余 Strategy1 SQL 多数是 Cloud Run Python path 仍使用的 active shared SQL，应从调用方反推并覆盖 `sql/ml/strategy1/**`、`sql/cloudrun/strategy1/**`，再迁移到 `sql/strategy1/**`。
- PRD 增补 retired linter allowlist、SQL 参数契约校验、`bqml_reference_run_id` legacy exception registry、Python package 交付策略和 research promotion manifest 口径。
- 同步更新 `.agent/memory/IMPLEMENTATION_STATUS.md`、`.agent/memory/AGENT_HANDOFF.md`、`.agent/memory/DECISION_LOG.md` 和 `TODO.md`。

### 重要上下文

- 本轮是 PRD-only，不改代码、不改 SQL、不运行 BigQuery / Cloud Run / Dataform。
- 已追加 `DECISION-20260610-05` 记录 owner 确认的结构重构决策；不新增 `KNOWN_CONSTRAINTS.md` 约束，因为本 PRD 尚未实现代码或物理 BigQuery 资源。
- 结构重构事项仍在 `TODO.md` P1；当 owner 决定启动 P1 工程治理或在 OQ-010/R14 空档穿插推进时，第一步是 PR-A：建立 active step catalog、retired reference linter 和 README/runbook 口径护栏；第二步 PR-A2 做 table role / dataset role resolver 且仍解析到 `ashare_ads`。`ashare_research` dataset / table contract 应后置为单独 PR，不和目录搬迁或默认写入切换混做。

### 改动文件

- `docs/prd/PRD_20260610_02_项目结构重构方案.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

### 测试 / 验证

- 文档改动；未运行 BigQuery、Cloud Run、pytest 或 Dataform。
- 建议提交前至少运行 `git diff --check`。

### 阻塞项

- 无。

### 下一步建议

- 结构重构仍按 `TODO.md` 的 P1 工程治理项处理；当 owner 决定启动或在 OQ-010/R14 空档穿插推进时，从 PR-A 开始：建立 active step catalog、retired reference linter 和 README/runbook 口径护栏；不移动文件、不改运行行为。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - Strategy1 旧 BQML / SQL ledger runner P0 退役实现

### 已完成工作

- 删除 BQML-only `sql/ml/strategy1/02_train_bqml_logistic_candidates.sql`、`03_select_model_and_register.sql`、`04_predict_daily.sql`。
- 删除 SQL ledger fallback `sql/ml/strategy1/08_run_backtest.sql`。
- 删除旧 OQ-010 SQL/BQML 调度器 `scripts/strategy1/run_oq010_experiments.py`，避免保留会调用已删除 `02-04` / `08` 的失效入口。
- `scripts/strategy1_cloudrun/backtest_report.py` 已移除 `--use-bq-ledger` 参数、`bigquery_sql` backend 分支和对 `08_run_backtest.sql` 的调用；默认固定走 Cloud Run Python ledger。
- `scripts/strategy1_cloudrun/orchestrate_experiments.py` 与 `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py` 已移除 `--use-bq-ledger` 透传。
- 文档和项目记忆已同步为当前口径：active path 为 Cloud Run Python training / prediction / ledger + 共享 SQL `01`、`05-07`、`09-10`、`12`、`16-24`。

### 重要上下文

- 本次只删除旧执行入口，不删除历史 ADS / GCS artifact、历史 BQML run/backtest id 或 v3 replay/QA。
- `sql/ml/strategy1/01_build_training_panel.sql`、`05_build_candidates.sql`、`06_build_portfolio_targets.sql`、`07_build_order_plan.sql`、`09_build_metrics_and_report_inputs.sql`、`10_qa_runner_outputs.sql`、`12_qa_model_diagnosis_outputs.sql` 和 `16-24` 仍是当前 Cloud Run Python path 的共享 SQL / QA 面。
- legacy FLOAT 股数审计只保留 Python `--use-float-ledger`；`--use-bq-ledger` 不再存在。

### 改动文件

- `scripts/strategy1_cloudrun/backtest_report.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1/run_oq010_experiments.py`
- `sql/ml/strategy1/02_train_bqml_logistic_candidates.sql`
- `sql/ml/strategy1/03_select_model_and_register.sql`
- `sql/ml/strategy1/04_predict_daily.sql`
- `sql/ml/strategy1/08_run_backtest.sql`
- `sql/ml/strategy1/README.md`
- `sql/README.md`
- `docs/prd/PRD_20260609_02_策略1旧BQMLSQLRunner退役.md`
- `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`
- `docs/prd/PRD_20260603_05_策略1实验并发调度与隔离.md`
- `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`
- `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`
- `docs/策略1-ml_pv_clf_v0-runner设计.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `docs/策略1实验并发调度器运行手册.md`
- `dataform/definitions/assertions/03_index_benchmark_checks.sqlx`
- `sql/meta/02_strategy1_experiment_run_status.sql`
- `sql/qa/03_index_benchmark_checks.sql`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

### 测试 / 验证

- 未执行 BigQuery、Cloud Run、pytest 或 replay。

### 阻塞项

- 无。

### 下一步建议

- 等 PR review；如果 reviewer 只要求补文档口径或移除残余引用，直接在本分支修。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - historical backfill core smoke 修复

### 已完成工作

- 合并 PR #132 并删除远端分支。
- 从最新 `main` 重新部署 `ashare-pipeline-control`，新 revision 为 `ashare-pipeline-control-00007-tst`。
- 重新触发 2015 年 warehouse backfill execution `209bd2bf-86f4-455c-85c7-b6b1f4ec8025`。
- 诊断新失败点：流程已越过 `dim_stock` 生命周期缺口，失败于 core smoke 的旧全表下限断言。
- 新建分支 `codex/fix-historical-backfill-core-smoke`，将 core smoke 从“不得有 2019 前行”改为“不得早于 A 股日线支持历史下限 `1990-12-19`”。
- 同步更新 DWD price / valuation metadata 描述，明确默认全量/日常路径仍是 2019+，owner 显式 backfill 可写指定历史训练窗口。

### 重要上下文

- 失败 execution：`209bd2bf-86f4-455c-85c7-b6b1f4ec8025`。
- 失败 BigQuery job：`4a6b55a4-4cbc-4bad-9c22-8ed8265f8072`。
- 失败文案：`dwd_stock_eod_price must not write rows before dwd_start_date`。
- 该失败不是缺 ODS 数据，也不是 #132 未生效；它是 core smoke 旧全局不变量和 explicit historical backfill 新语义冲突。

### 改动文件

- `sql/qa/01_core_smoke_checks.sql`
- `sql/metadata/01_core_table_column_descriptions.sql`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 已执行生产 backfill 重跑并定位失败点。
- 未执行 SQL dry-run 或重新触发 backfill；需合并部署后再跑。

### 阻塞项

- 合并部署前，2015 年 backfill 仍会命中旧线上 core smoke。

### 下一步建议

- 提交并合并本分支。
- 部署新的 `ashare-pipeline-control` SQL bundle。
- 重新触发 `2015-01-01 ~ 2015-12-31` backfill；若通过，再按年触发 2016-2018。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - dim_stock 历史生命周期修复

### 已完成工作

- 诊断 2015 年 backfill execution `be12a12f-1e65-4cef-b60d-3945ef8da13a` 的新失败点。
- 确认 PR #130 修复有效：execution 已越过指数 DWD 和指数 QA，进入股票 DWD/DWS 后失败于 `QA-WIN-13`。
- 新建分支 `codex/fix-historical-dim-stock-lifecycle`，修复 `dim_stock` 历史生命周期：
  - `missing_from_stock_basic` 从全量 ODS daily 派生，不再只看 2019+ daily。
  - `stock_basic_enriched.list_date` 在 `stock_basic.list_date` 晚于首个日线交易日时，用 `first_trade_date` 作为历史生命周期下限。
- PR #132 review follow-up：删除重复的 `daily_codes` CTE，让 `missing_from_stock_basic` 直接复用 `daily_lifecycle`，避免同一全量 ODS daily 外表被扫描两次。

### 重要上下文

- 2015 年 QA 缺口为 `5,486` 行、`76` 个代码。
- 分类结果：`75` 个代码是 `before_list_date`，`1` 个代码 `000022.SZ` 是 `missing_dim_stock`。
- 当前失败后的 2015 DWD/DWS 已有部分写入；后续重跑窗口 SQL 会按窗口 DELETE/INSERT 覆盖，不需要单独清理。

### 改动文件

- `sql/dim/02_dim_stock.sql`
- `sql/metadata/01_core_table_column_descriptions.sql`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 已执行只读诊断 BigQuery 查询，确认缺口原因。
- 未执行 SQL dry-run 或重新触发 backfill；需合并部署后再跑。

### 阻塞项

- 合并部署前不要继续触发 2015/2016/2017/2018 补数，否则仍会命中旧 `dim_stock` 生命周期口径。

### 下一步建议

- 提交并合并本分支。
- 部署新的 `ashare-pipeline-control` SQL bundle。
- 重新触发 `2015-01-01 ~ 2015-12-31` backfill；成功后再按年跑 2016-2018。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-09 GPT-5 Codex - 2015-2018 历史 backfill 下限修复

### 已完成工作

- 新建 worktree `/Users/fisher/Desktop/git/quant-ashare-fix-2015-index-backfill`，分支 `codex/fix-2015-index-backfill`。
- 修复 `ashare_warehouse_window_refresh` 历史 backfill 被 `2019-01-01` 下限拦截的问题。
- 股票 DWD/DWS 窗口、指数 DWD 窗口、market-state 窗口和股票 / 指数窗口 QA 均改为按 `warehouse_mode` 区分日期下限：`daily_current` 保持 2019+，显式 `backfill` 允许 owner 指定 2019 年以前窗口。

### 重要上下文

- 2015 年 backfill execution `2eea35d1-21bc-4c4c-b610-90b57170819a` 失败于指数 DWD 窗口刷新，错误为 `index DWD window refresh requires write_end_date >= write_start_date`。
- 根因不是 workflow 参数入口或 ODS readiness；ODS readiness 已通过，失败发生在指数窗口 SQL 的固定下限计算。
- 本 PR 不自动执行补数；合并部署后需要重新从 2015 年窗口开始触发。

### 改动文件

- `sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `sql/incremental/02_refresh_index_dwd_window.sql`
- `sql/incremental/03_refresh_market_state_window.sql`
- `sql/qa/10_windowed_stock_refresh_checks.sql`
- `sql/qa/12_windowed_index_refresh_checks.sql`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未执行 SQL dry-run 或生产补数验证；本轮按 owner 要求先修代码并提 PR。

### 阻塞项

- 无代码阻塞。
- 合并部署前不要继续触发 2016-2018 补数，否则仍会命中旧线上 SQL。

### 下一步建议

- 合并并部署 Workflows SQL bundle 后，重新触发 `2015-01-01 ~ 2015-12-31` backfill。
- 2015 年成功后，再按年触发 `2016`、`2017`、`2018`。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-09 GPT-5 Codex - Strategy1 R14 长训练窗口回测 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260609_01_策略1R14长训练回测.md`。
- 文档定义固定 R14 方法的长训练窗口实验：名义训练窗口 `2015-04-01 ~ 2019-12-31`，先跑 `2020-01-02 ~ 2022-12-30` 的 `10` 只 / `20` 只双组合 diagnostic backtest；`2023-01 ~ 2026-06-09` 追加回测视 P0 结果和 owner 决策而定，若追加也跑两个组合。
- P0 组合设为 `target_holdings=10` / `max_single_weight=15%` 与 `target_holdings=20` / `max_single_weight=7.5%`，`rebalance_frequency=biweekly`。
- 文档明确 5d 标签 embargo、2015-2018 DWD/DWS 前置补建、2020-2022 diagnostic 不写 production accepted registry，以及追加段不能和 P0 fresh segment 拼接成正式连续回测，除非 Cloud Run Python ledger resume 已实现并通过 resume consistency QA。

### 重要上下文

- 当前 raw ODS 股票行情层已有 2015 起数据，但策略实际 DWD/DWS 输入层当前从 2019 起；该实验前必须先审计并补齐 2015-2018 策略输入层。
- R14 是 `lightgbm_regression`，训练目标为 `target_return=fwd_xs_ret_5d`；若不做 embargo，2019 年末训练样本会读取 2020 回测期收益形成标签。
- 本轮只写 PRD，未执行 BigQuery / Cloud Run。

### 改动文件

- `docs/prd/PRD_20260609_01_策略1R14长训练回测.md`

### 测试 / 验证

- 未执行。此次为 PRD 与项目记忆更新。

### 阻塞项

- 无代码阻塞。
- 实验执行前需要先做 2015-2018 DWD/DWS、risk feature、market-state 和 5d label embargo 覆盖审计。

### 下一步建议

- 执行 PRD P0-A 只读覆盖审计。
- 若缺 2015-2018 DWD/DWS，制定最小 backfill / rebuild 计划。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-09 GPT-5 Codex - 清理旧 Composer warehouse refresh helper

### 已完成工作

- 删除 `scripts/pipeline/run_warehouse_refresh.py`，避免后续误用 `gcloud composer environments run` 触发已退役的 Composer 环境。
- 更新 OQ-005 约束与交接，明确后续补跑 / QA-only / full rebuild 以 Workflows runbook 和 `orchestration/workflows/**` 为准。

### 重要上下文

- 当前生产调度入口已经是 `Cloud Scheduler + Cloud Workflows`，`ashare-composer` 已删除。
- `orchestration/composer/**` 仍只保留为 retired / audit-only 历史快照；本轮没有改该目录。

### 改动文件

- `scripts/pipeline/run_warehouse_refresh.py`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未执行。此次为删除旧运维 helper 和记忆同步，不跑生产任务。

### 阻塞项

- 无。

### 下一步建议

- 等 PR review；若通过，合并后可继续 OQ-005 cutover 后短观察窗记录。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-09 GPT-5 Codex - Strategy1 live acceptance gate v3 cutover

### 已完成工作

- 将 Cloud Run Python search 默认 acceptance contract 从 `model_acceptance_contract_v1.yml` 切到 `model_acceptance_contract_v3.yml`。
- `orchestrate_sklearn_native_search.py` 在 ADS 写回前接入 v3 replay 已验证的五指数指标计算，按实际 backtest span / manifest final_holdout window 输出候选级 v3 状态和逐指数相对门明细。
- ADS registry / backtest summary 写回新增 v3 contract hash、gate version、primary benchmark、复合年化、Sharpe / Calmar、final_holdout 诊断和五指数相对门摘要。
- `19` QA 改为 v3-aware；`21` risk-feature QA 把旧 risk overlay 限定到 legacy contract。
- 使用 PR #125 分支 smoke 镜像和临时 Cloud Run jobs 跑通 2 候选 live v3 smoke；过程发现 `v3_relative_gate_by_benchmark.csv` 的 `search_id` 列为空，已补 `fetch_topk_ads_outputs` 的 search_id 透传。

### 重要上下文

- owner 已明确后续不再经过 v2；当前切门路径是 v1 -> v3。
- v3 final_holdout 是 diagnostic-only，不再是 hard veto。
- 本轮没有重跑历史 replay，也没有启动新的 Cloud Run search。

### 改动文件

- `configs/strategy1/model_acceptance_contract_v3.yml`
- `configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml`
- `configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml`
- `configs/strategy1/cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_v0.yml`
- `configs/strategy1/cloudrun_python_riskfeat_lgbm_regression_pvfq_n30_bw_h5_v0.yml`
- `scripts/strategy1_cloudrun/acceptance.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql`
- `sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`
- `sql/ml/strategy1/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 已执行 2 候选 Cloud Run live v3 smoke：`search_id=cloudrun_python_lgbm_v3_live_smoke_20260609_01`，`candidate_count=2`，`top_k=1`。
- 结果：prepare matrix、2 个 candidate fanout、select/register/predict、backtest/report、19 QA 和 artifact upload 均 succeeded；Top-K 1 的 native/v3 status 为 `rejected`，原因 `test_top_minus_bottom<=0;no_comparison_benchmark_passed_v3_relative_gate`。
- registry 验证：`acceptance_contract_version=model_acceptance_contract_v3`、`acceptance_gate_version=strategy1_acceptance_gate_v3`、`primary_benchmark_sec_code=000001.SH`、`v3_relative_gate_evaluated_benchmark_count=5`。
- artifact 验证：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/search_id=cloudrun_python_lgbm_v3_live_smoke_20260609_01/v3_relative_gate_by_benchmark.csv` 已生成 5 个 benchmark 明细；本轮修复后后续运行会写出非空 `search_id`。

### 阻塞项

- 无代码阻塞。

### 下一步建议

- 等 PR #125 review；若 reviewer 接受 smoke 证据，可以合并。
- 合并后清理临时 `*-pr125-smoke` Cloud Run jobs 和未提交 smoke manifest。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-09 GPT-5 Codex - Workflows Cloud Run Job IAM follow-up

### 已完成工作

- 给 `ashare-workflows-runtime@data-aquarium.iam.gserviceaccount.com` 在 `ashare-ingest-current-scope` Cloud Run Job 上补 `roles/run.jobsExecutorWithOverrides`。
- 给同一 runtime SA 补项目级 `roles/run.viewer`，用于读取 Cloud Run operation / execution 状态。
- 更新 `orchestration/workflows/bootstrap_scheduler_iam.sh`，将 ODS ingestion job 权限从 job-level `roles/run.invoker` 改为 `roles/run.jobsExecutorWithOverrides`，并移除旧 job-level `run.invoker`。
- 更新 `orchestration/workflows/README.md` 与项目记忆，记录真实运行暴露的权限口径。

### 重要上下文

- `roles/run.invoker` 只包含 `run.jobs.run`，不足以支持 workflow 传 overrides 启动 Cloud Run Job。
- `roles/run.jobsExecutorWithOverrides` 允许启动带 overrides 的 Job，但不包含 `run.operations.get`；Workflows 轮询 Cloud Run operation 还需要 `roles/run.viewer`。

### 改动文件

- `orchestration/workflows/bootstrap_scheduler_iam.sh`
- `orchestration/workflows/README.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 正在用 `ashare_ods_ingestion_daily` manual recovery execution `39e42cbf-c140-4e04-9207-27bfff637ee8` 验证。

### 阻塞项

- 无代码阻塞；等待重跑 execution terminal 状态。

### 下一步建议

- 若重跑成功，继续看 child `ashare_warehouse_window_refresh` 是否完成。
- 合并 IAM bootstrap 修正 PR，避免未来重新 bootstrap 后复现 20:00 权限失败。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-08 GPT-5 Codex - OQ-005 direct cutover to Scheduler + Workflows

### 本轮完成

- 新增 `orchestration/workflows/bootstrap_scheduler_iam.sh`，把 `ashare-scheduler-invoker` 与 `ashare-workflows-runtime` 当前真实依赖的 IAM 绑定固化为可重放脚本。
- 重写 `orchestration/workflows/deploy_scheduler_jobs.sh`，统一管理 `ashare-pipeline-alert-checker` 与 `ashare-ods-ingestion-daily` 两个 Scheduler jobs。
- 新增 `orchestration/workflows/cutover_scheduler_jobs.sh`，用于 bootstrap IAM、启用 Scheduler jobs，并保持 Composer 业务 DAG paused。
- 已真实执行 cutover：
  - alert-checker scheduler execution `978c920c-3810-4299-b904-3c954e8d221d` succeeded
  - ODS parent execution `31ac0d61-d40c-4a88-9865-b13f61d369c1` succeeded
  - child warehouse execution `919f2aba-b9d4-4181-9915-fa848487bb90` succeeded
- 两个生产 Scheduler jobs 当前都为 `ENABLED`，caller SA 为 `ashare-scheduler-invoker@data-aquarium.iam.gserviceaccount.com`。

### 本轮未做

- 没有删除 Composer 环境。
- 没有执行真实 full rebuild 写路径。

### 影响文件

- `orchestration/workflows/bootstrap_scheduler_iam.sh`
- `orchestration/workflows/deploy_scheduler_jobs.sh`
- `orchestration/workflows/cutover_scheduler_jobs.sh`
- `orchestration/workflows/README.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 阻塞项

- 无新的技术阻塞。
- OQ-005 现在只剩是否保留短期观测窗口，以及何时删除 Composer 环境。

### 下一步建议

- 若不再需要额外观察窗口，下一步就是删除 Composer 环境，停止固定 `Cloud Composer 3 standard milli DCU-hours` 成本。
- 若仍想保守一点，可先观察下一次自然 scheduled ODS run，再删环境。

Model: GPT-5 Codex

## 2026-06-09 GPT-5 Codex - PR #124 runbook review follow-up

### 已完成工作

- 按 PR #124 review，改写 `docs/Pipeline-补跑与故障恢复-Runbook.md`，把 active recovery path 从 Composer / Airflow 改为 Cloud Scheduler + Cloud Workflows。
- Runbook 现在覆盖 ODS 缺采、endpoint 失败、窗口刷新/QA 失败、backfill、非交易日 skip、Scheduler 触发异常、alert checker 异常和 full rebuild。
- 同步更新 `scripts/alerting/README.md` 与 `scripts/alerting/setup_alerts.py`，避免告警链路文档继续提 Composer DAG / Composer 调度异常。

### 重要上下文

- `orchestration/composer/**` 仍只是历史审计目录。
- 当前 active on-call runbook 是 `docs/Pipeline-补跑与故障恢复-Runbook.md`，它现在应该跟 `orchestration/workflows/**` 保持一致。

### 改动文件

- `docs/Pipeline-补跑与故障恢复-Runbook.md`
- `scripts/alerting/README.md`
- `scripts/alerting/setup_alerts.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- 未执行。此次为文档和告警说明更新，不涉及运行代码路径。

### 阻塞项

- 无。

### 下一步建议

- 继续看 PR #124 是否还有新 comment。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

Model: GPT-5 Codex

## 2026-06-08 GPT-5 Codex - PR #121 review follow-up

### 本轮完成

- `bootstrap_scheduler_iam.sh` 不再给 `ashare-workflows-runtime` 授项目级 `roles/run.developer`；改为对 `ashare-ingest-current-scope` 单授 job-level `roles/run.invoker`，并在脚本里显式移除旧的项目级 `run.developer` 绑定。
- `cutover_scheduler_jobs.sh` 改为更安全的 staged 顺序：先用 `ENABLE_JOBS=false` 创建/更新 paused Scheduler jobs，再 pause Composer 业务 DAG；只有显式 `RESUME_SCHEDULER_JOBS=true` 才会 resume。
- `README.md`、`KNOWN_CONSTRAINTS.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`TODO.md` 已同步更新到新的 least-privilege / staged-cutover 语义。

### 本轮未做

- 没有重新触发 ODS / warehouse scheduler execution。
- 没有处理 review 提到的 lock bucket 前缀最小化问题；当前仍沿用整桶 `roles/storage.objectAdmin`。

### 影响文件

- `orchestration/workflows/bootstrap_scheduler_iam.sh`
- `orchestration/workflows/cutover_scheduler_jobs.sh`
- `orchestration/workflows/README.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 下一步建议

- 运行更新后的 `bootstrap_scheduler_iam.sh`，把 live runtime SA 真的收敛到 job-level `run.invoker`。
- PR 合并后，再单独决定是否要为 lock 前缀拆专用 bucket / IAM condition，随后删除 Composer 环境。

Model: GPT-5 Codex

## 2026-06-08 GPT-5 Codex - Composer historical directory cleanup

### 已完成工作

- 将 `orchestration/composer/README.md` 从“可操作 Composer runbook”改成 retired / audit-only 说明，明确 `ashare-composer` 已删除，当前生产入口只保留 `orchestration/workflows/**`。
- 主动移除了 README 里针对已删除 Composer 环境的同步、触发、变量和手工操作命令，避免后续误操作。
- 给 `orchestration/composer/dags/ashare_common.py` 与 5 个 Composer DAG 顶部都加了 retired 标识，明确这里只保留历史快照，不再接受新的生产逻辑。

### 重要上下文

- 这次没有改任何调度语义，也没有重新部署或 smoke。
- 目标只是收口仓库内“哪些 Composer 资产继续保留、哪些路径已经彻底退出生产”的边界。
- 当前生产入口仍然是 `Cloud Scheduler + Cloud Workflows`，不是 Composer。

### 改动文件

- `orchestration/composer/README.md`
- `orchestration/composer/dags/ashare_common.py`
- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `orchestration/composer/dags/ashare_ods_ingestion_daily.py`
- `orchestration/composer/dags/ashare_pipeline_alert_checker.py`
- `orchestration/composer/dags/ashare_warehouse_full_rebuild.py`
- `orchestration/composer/dags/ashare_warehouse_window_refresh.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未执行。此次为文档/标识清理，不涉及行为变更。

### 阻塞项

- 无。

### 下一步建议

- 若要继续收口 OQ-005，可补一条 cutover 后短观察窗记录，然后把这部分也归档到 OQ-005 完成态。
- 若后续还要碰调度实现，直接改 `orchestration/workflows/**`，不要再在 Composer 目录叠加新逻辑。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-08 GPT-5 Codex - TODO cleanup

### 已完成工作

- 将 `TODO.md` 从长版状态流水重写为短版行动清单。
- 删除已完成历史、重复背景和大量上下文，只保留当前仍需执行的事项。
- 保留的主线现在只有：OQ-005 补短观察窗记录、OQ-010 accepted Python baseline、OQ-012 关闭/保留决策，以及少量 P1 优化项。

### 重要上下文

- 这次没有改代码、没有改调度语义，只是收口任务视图。
- 历史完成记录统一以 `IMPLEMENTATION_STATUS.md` / `AGENT_HANDOFF.md` 为准，不再堆在 `TODO.md` 里。

### 改动文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- 未执行。此次为任务清单精简，不涉及行为变更。

### 阻塞项

- 无。

### 下一步建议

- 若继续收口 OQ-005，先补 cutover 后短观察窗记录。
- 若转回策略主线，直接继续 OQ-010 accepted baseline 探索。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex


---

## Handoff - 2026-06-09 - Cloud Run ledger resume implementation start

- Model: GPT-5 Codex
- Branch/worktree: `codex/prd-cloudrun-ledger-resume` / `/Users/fisher/Desktop/git/quant-ashare-ledger-resume-prd`
- Owner request: 在 PR #127 分支上开始实现 Cloud Run Python ledger resume。
- Changed: added resume fields to Strategy1 experiment config/CLI params; added Cloud Run Python ledger state persistence and parent-state restore path; added ADS state table DDL; updated SQL contract defaults/QA for `rebalance_anchor_start` and `cloudrun_lot100_resume_v1`; added full-vs-resume QA SQL.
- Validation: not run per owner workflow unless explicitly requested.
- Next: review PR #127 comments/CI after push; then run targeted unit/SQL/Cloud Run smoke only if owner asks.


---

## Handoff - 2026-06-10 - PR #127 ledger resume review follow-up

- Model: GPT-5 Codex
- Branch/worktree: `codex/prd-cloudrun-ledger-resume` / `/Users/fisher/Desktop/git/quant-ashare-ledger-resume-prd`
- Owner request: 看 PR #127 comment；认可实现 review 中的 6 个问题并直接修复。
- Changed: fixed missing imports/constants/dataclass fields, wired resume manifest/CLI/SQL params into `LedgerParams`, replaced fresh-only fail-fast with lot100 parent-state restore, added ledger state writes/deletes, corrected resume policy and rebalance anchor QA, and fixed `25_qa_cloudrun_ledger_resume_outputs.sql` to use `ashare_ads` plus current ADS trade/nav columns.
- Validation: not run per owner workflow unless explicitly requested.
- Next: review PR #127 comments/CI after push; run targeted unit tests and a small full-vs-resume smoke only if owner asks.

## 2026-06-10 - Strategy1 回测复合年化收益 PRD

日期: 2026-06-10
Agent ID: Codex
Agent 实例 ID: 当前 Codex desktop session
模型: GPT-5 Codex
运行环境: `/Users/fisher/Desktop/git/quant-ashare-compound-annual-prd`
Run ID: doc-only
相关 issue/PR: 待创建 PR

### 已完成工作

- 新增 `docs/prd/PRD_20260610_01_策略1回测复合年化收益.md`。
- PRD 定义新增 `compound_annual_return`、`return_period_count`、`annualization_target_period_count`、`annualization_method`，并要求旧 `annual_return` 保留为 legacy。
- PRD 明确后续 report、diagnosis、v3 acceptance gate、replay QA 默认读复合年化口径；v3 缺复合字段不得 fallback 到 legacy 年化后通过。
- 根据 PR #134 review 补充：`return_period_count` 固定为 NAV 有效交易日数减 1；compound Sharpe 会系统性影响阈值，启用前需 replay 差异表和 owner 阈值确认；`select_register_predict.py` 纳入 registry 指标传播影响面。
- 更新 `TODO.md` 和 `IMPLEMENTATION_STATUS.md`。

### 重要上下文

- owner 已确认项目中年化 / 月化 / 日化默认按复利口径。
- 近期 R14 长训练回测暴露 `ads_backtest_performance_summary.annual_return` 与按 NAV 交易日数补算的复合年化不同，需避免后续混用。
- 本次 PRD 是后续代码实现前置说明，不改变任何历史 backtest artifact。

### 改动文件

- `docs/prd/PRD_20260610_01_策略1回测复合年化收益.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- 未运行测试；文档-only 变更。

### 阻塞项

- 无。后续是否批量回填历史 run 的复合年化字段需要 owner 决策。

### 下一步建议

1. review PRD。
2. 另开实现 PR，扩展 summary schema / SQL / report / v3 acceptance / QA。
3. 用一个小规模 backtest smoke 验证 `compound_annual_return` 可从 NAV 重算。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
