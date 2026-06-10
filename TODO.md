# TODO

本文件只保留“下一步可执行事项”。历史完成记录与背景说明以 `.agent/memory/IMPLEMENTATION_STATUS.md`、`.agent/memory/AGENT_HANDOFF.md`、`.agent/memory/OPEN_QUESTIONS.md` 为准。

## P0 — 当前优先

- [x] OQ-005：合并 2026-06-09 scheduled ODS run 暴露的 Cloud Run Job IAM bootstrap 修正
  说明：已由 PR #126 合并到 `main`。`orchestration/workflows/bootstrap_scheduler_iam.sh` 已固化 runtime SA 的 job-level `roles/run.jobsExecutorWithOverrides`、project-level `roles/run.viewer`，并移除旧 job-level `roles/run.invoker`，避免重新 bootstrap 后复现 scheduled ODS workflow 权限失败。

- [x] PR #124 review follow-up：active on-call runbook 已改写为 `Cloud Scheduler + Cloud Workflows` 恢复路径，告警链路文档不再指向已删除的 Composer 环境

- [ ] OQ-005：补一条 cutover 后短观察窗记录
  说明：当前生产入口已经是 `Cloud Scheduler + Cloud Workflows`，`ashare-composer` 也已删除；旧 Composer-era warehouse refresh helper 已清理；剩余只差一个简短的 post-cutover 观察记录，用于彻底收口 OQ-005。

- [ ] OQ-010：继续寻找 accepted 的 Cloud Run Python baseline
  说明：当前 Cloud Run Python 路线可运行，但 binary / regression / risk-feature 多轮候选都未建立 accepted baseline；PR #125 分支已完成 2 候选 live v3 smoke，registry、19 QA 和 `v3_relative_gate_by_benchmark.csv` 产物链路跑通。后续继续围绕可接受模型、特征集和风险控制方案推进。

- [ ] OQ-010：实现年度滚动选参回测实验
  说明：`docs/prd/PRD_20260610_03_策略1年度滚动选参.md` 已定义年度 walk-forward 参数选择方案；`docs/prd/PRD_20260610_04_策略1年度滚动执行工程化.md` 已补执行工程化方案。2021 单年度 Cloud Run smoke 已在正式 jobs 上闭环，CV fold 修复已实证为 11/11 候选 `cv_fold_count=3`，select/register/predict 与 backtest/report 均成功。下一步先实现 ADS additive migration、schema readiness QA 和 annual rolling orchestrator resolved payload 生成，再扩展完整 `2021-2026` 年度滚动，并用连续 ledger 评价，不拼接年度 fresh-run。


- [x] OQ-010：实现回测复合年化收益字段
  说明：PR #134 已扩展 ADS summary 契约并在 `09` 写出 `compound_annual_return` / `return_period_count` / annualization metadata，`10` 和 `24` QA 校验 `NAV 有效交易日数 - 1` 口径，report 默认展示复合年化；旧 `annual_return` / `sharpe` 保留 legacy 语义，不回填历史 run。



- [x] OQ-010：审计并删除旧 BQML / SQL ledger fallback
  说明：PR #131 分支已删除 BQML-only `sql/ml/strategy1/02-04`、SQL ledger fallback `08_run_backtest.sql` / `--use-bq-ledger` 和旧 `scripts/strategy1/run_oq010_experiments.py`，并同步收敛 README / runbook / memory 口径。

- [ ] OQ-010：实现 Cloud Run Python ledger resume
  说明：已新增 PRD `docs/prd/PRD_20260609_01_策略1CloudRunLedgerResume.md`；目标是在 `ledger_exec_v1_lot100` 下支持从父回测现金、持仓、pending sell、NAV anchor 和调仓锚点继续运行，先验收 `2020-2022 -> 2023-2026` 与 full fresh `2020-2026` 的一致性。
- [ ] OQ-010：按 R14 长训练窗口 PRD 做覆盖审计
  说明：`docs/prd/PRD_20260609_01_策略1R14长训练回测.md` 已定义固定 R14 方法、`2015-04-01 ~ 2019-12-31` 名义训练窗口和 `2020-2022` 的 `10` 只 / `20` 只双组合 diagnostic backtest；`2023-01 ~ 2026-06-09` 追加回测视 P0 结果和 owner 决策而定，若追加也跑两个组合。PR #130 已修复显式 `backfill` 历史窗口下限，PR #132 已修复 `dim_stock` 历史生命周期；2015 年重跑后又暴露 core smoke 仍用 2019 作为全表存在下限，分支 `codex/fix-historical-backfill-core-smoke` 已修复，待合并部署后重新触发 2015 年补数。

- [ ] OQ-012：决定是否正式关闭 schema mismatch 问题
  说明：schema contract、repair/validate 脚本和 `sql/qa/06_ods_parquet_schema_checks.sql` 都已具备，当前 BigQuery 读层没有 mismatch 暴露；剩余是 owner 决定归档关闭，还是保留防复发工程项。

## P1 — 后续优化

- [x] OQ-010 / 工程治理：实现项目结构重构 PRD Phase A-C
  说明：分支 `codex/strategy1-structure-refactor` 已新增 Strategy1 active step catalog、retired reference linter、table-role/dataset-role resolver、`src/quant_ashare/**` package foundation，并把当前 active/shared Strategy1 SQL 迁移到 `sql/strategy1/**`；Cloud Run wrapper 仍保留，当前 table role 仍解析到 `ashare_ads`，不创建或写入 `ashare_research`。

- [x] OQ-010 / 工程治理：实现项目结构重构 PRD Phase D0 research table contract
  说明：新增 `sql/research/01_research_strategy1_tables.sql`、`sql/research/README.md` 和 `ashare_research` schema contract，覆盖 `research_*` 表族、`research_acceptance_result`、`research_experiment_run_status` 与 `research_promotion_manifest`；PR #140 review follow-up 已补 `experiment_run_status` 当前侧 `ads_dataset: ashare_meta` override、`build_order_plan` 分区列修正和防漂移测试；默认 runner 仍写 `ashare_ads`，research routing / default research-first / promotion job 尚未开启。

- [x] OQ-010 / 工程治理：实现项目结构重构 PRD Phase D1a SQL render table-role routing
  说明：`src/quant_ashare/strategy1/sql_render.py` 已按 catalog step 的 `inputs` / `outputs` 注入 table role 替换；默认 ADS 渲染不变，显式 `dataset_role="research"` 仍需 `allow_future_research=True`，并只用于 contract / dry-run / 后续 runner 接线验证。PR #142 review follow-up 已补全 step role 覆盖并新增 pytest，禁止 research 渲染残留 `data-aquarium.ashare_ads.`。Cloud Run 默认写入、实际 BigQuery `ashare_research` 写入和 promotion 尚未开启。

- [x] OQ-010 / 工程治理：实现项目结构重构 PRD Phase D1b runner research routing
  说明：分支 `codex/strategy1-research-routing-d1b` 已新增显式 `output_dataset_role` CLI/config 接线，并让 Cloud Run Python runner、ledger、orchestrator status、report / diagnosis / QA / acceptance / comparison / factor attribution 在显式 `research` 模式下按 resolver 读取或写入 `ashare_research.research_*`；默认 ADS 子命令不下发 `--output-dataset-role=ads`，保持旧 Cloud Run 镜像兼容；research DDL lifecycle 默认值已明确为 `research_status='candidate'`、`promotion_status='not_promoted'`。本阶段未部署 BigQuery / Cloud Run，未切 default research-first，未实现 promotion。

- [ ] OQ-010 / 工程治理：完成项目结构重构 PRD Phase D1 收尾验收
  说明：进入 D2 前必须部署 `sql/00_create_datasets.sql` + `sql/research/01_research_strategy1_tables.sql`，重建并部署 Strategy1 Cloud Run job 镜像，给 runtime service account 补 `ashare_research` 写权限，跑一次显式 research-mode smoke（search 或 backtest）并覆盖 report / diagnosis / QA / acceptance；验收需确认 research 表有写入、lifecycle 默认值正确、ADS run-scoped 表没有被 research run 污染。

- [ ] OQ-010 / 工程治理：后续单独实现项目结构重构 PRD Phase D2-D3/E
  说明：D1 收尾验收通过后，再做 default research-first、owner-approved promotion job，以及深层 package split / naming cleanup；Phase E 包化时同步收敛读侧 routing 的模块级全局态（当前 setter 与裸全局两种风格并存）。不得与 D1b 显式 routing 混做。

- [x] 工程治理：修复 Dataform generated SQLX drift
  说明：已在单独 cleanup 分支重新运行 `scripts/dataform/generate_sqlx_from_sql.py`，同步 6 个 stale generated SQLX 文件，并新增 pytest 防复发检查；`--check`、Dataform compile、`python3 -m pytest tests` 和 `git diff --check` 已通过。

- [ ] OQ-005：如真实运行暴露 stale-lock 边界，再为 `ashare-pipeline-control` 的 stale-lock reclaim 增加 Workflows execution liveness 检查

- [ ] 若继续推进数据扩展，补 `lookback-capable` 价格构建输入
  说明：当前 2019 年初 60 日窗口通过 `has_full_history_60d=FALSE` 显式暴露并由样本掩码剔除；若要求 2019-01 起完整窗口，需要补专用构建输入或调整 DWD/DWS 构建方式。

- [ ] P1+ 资金面 / 事件 / 行业族 DWD 扩展
  说明：包括 `dim_stock_sw_industry_hist`、`dim_stock_ci_industry_hist` 及对应 QA。

- [ ] 实现 Cloud Run Python ledger resume：PR #127 分支已修复 review 指出的 resume 实现断链与 QA 字段问题，尚未跑测试、Cloud Run 或 BigQuery 验收。
