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
  说明：`docs/prd/PRD_20260610_03_策略1年度滚动选参.md` 已定义年度 walk-forward 参数选择方案；`docs/prd/PRD_20260610_04_策略1年度滚动执行工程化.md` 已补执行工程化方案。2021 单年度 Cloud Run smoke 已在正式 jobs 上闭环，CV fold 修复已实证为 11/11 候选 `cv_fold_count=3`，select/register/predict 与 backtest/report 均成功。分支 `codex/annual-rolling-exec-impl` 已实现 ADS additive migration、schema readiness QA、annual rolling 11 候选 config 和 resolved payload dry-run wrapper；下一步先运行 readiness QA 和 dry-run 审核，再扩展完整 `2021-2026` 年度滚动，并用连续 ledger 评价，不拼接年度 fresh-run。


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

- [x] OQ-010 / 工程治理：完成项目结构重构 PRD Phase D1 收尾验收
  说明：已在独立 worktree `codex/strategy1-research-d1-smoke` 部署 D0 research DDL、给 runtime SA 补 `ashare_research` 写权限、重建并部署 Strategy1 Cloud Run jobs 到 D1 smoke 镜像 `sha256:7ef5601980f1b202654b504a52c96e33c09f95d009ebdcf455b002e4913571f9`，并跑通显式 research-mode smoke `sklearn_native_research_d1_smoke_20260610_04`。验收确认 research 表写入、lifecycle 默认值正确、registry 显式 `run_id/search_id/created_date/acceptance_status` 写出、report / diagnosis / QA / acceptance 链路通过，且 ADS run-scoped 表同 run/backtest 零污染。

- [x] OQ-010 / 工程治理：D1 收尾合并后重建正式 main 镜像并部署
  说明：PR #146 已合并到 `main`，merge commit `bca0e79`。已从 merge 后 `origin/main` 重建正式 runner 镜像 `sha256:c0ae9b2ec72b1299a08db66eb02881d0d3156735c14f08193d60e4388c9cc357`，并把五个 Strategy1 Cloud Run jobs 更新到该 immutable digest；只读 boot smoke execution `strategy1-backtest-report-job-8krjt` 成功。

- [x] OQ-010 / 工程治理：D2 前补 research additive migration 约定与 research readiness QA
  说明：分支 `codex/research-schema-readiness` 新增 `sql/research/02_research_strategy1_additive_migrations.sql` 和 `sql/research/03_qa_research_schema_readiness.sql`，固化 research additive migration 约定，并用 readiness QA 覆盖 15 张 research 表、关键列/类型、分区、聚簇、lifecycle 默认值、partition filter 与 `research_experiment_run_status.log_dir`。live BigQuery readiness QA 已通过。

- [x] OQ-010 / 工程治理：实现项目结构重构 PRD Phase D2 default research-first
  说明：PR #148 已合并到 `main`，merge commit `13bf0b5`。已从 merge 后 `origin/main` 重建正式 runner 镜像 `sha256:92c348536776cbcd8fb4f09def63509f0f1dfdf2f13f54d472dc078582b410f0`，并把五个 Strategy1 Cloud Run jobs 更新到该 immutable digest；真实默认 research-first smoke execution `strategy1-backtest-report-job-2xr6f` 成功，未传 `--output-dataset-role`，run/backtest `s1_default_research_d2_smoke_20260610_03` / `bt_s1_default_research_d2_smoke_20260610_03` 写入 research candidate/target/order/trade/position/NAV/ledger state/summary/signal monitor，ADS 同 run/backtest 零污染。D2 已从代码、正式镜像、job spec 和真实写入 smoke 闭环。

- [x] OQ-010 / 工程治理：实现项目结构重构 PRD Phase D3/E
  说明：分支 `codex/strategy1-d3e-promotion-package` 已新增 owner-approved promotion job `python -m scripts.strategy1.promote_research_to_ads`，默认仅 promotion accepted research 产物，显式复制/映射到 ADS 并写 `research_promotion_manifest`；默认目标不含大体量 training panel，需 owner opt-in。PR #150 review follow-up 已明确真实写入必须传 `--execute`、`--print-sql` / 默认模式只做 review-only，promotion 不反写 acceptance/research accepted 状态，并补 source trade/NAV 窗口完整性 guard。Phase E 已把 dataset routing、acceptance、ledger、reporting/backtest 和 pipeline-control/orchestrator 实现迁入 `src/quant_ashare/strategy1/**`，旧 `scripts.strategy1_cloudrun.*` 仅保留兼容 wrapper，并补 package/import smoke 与 wrapper re-export 测试。PR #150 合并后已构建正式 main 镜像 `sha256:fdb61f8141e240c377b3faaa21b5e6efef9c783ebb9e04923ff3b675b8d54bc2`，更新五个现有 Strategy1 jobs，并新建专用 `strategy1-promote-research-to-ads-job`；promotion job help smoke 与完整参数 review-only dry-run 已成功，dry-run promotion manifest 行数确认为 0。尚未执行真实 owner-approved promotion。

- [ ] OQ-013 / 工程治理：决策并收敛 Strategy1 普通 runner 的 ADS 写权限
  说明：PR #151 review follow-up 已实证五个普通 Strategy1 runner jobs 仍使用 `241358486859-compute@developer.gserviceaccount.com`，且 `ashare_ads` dataset 仍授予该 SA WRITER；显式 `--output-dataset-role ads` 仍可绕过 promotion job 直接写 ADS。不能直接 revoke，因为 ADS audit / 历史报告重渲染仍可能需要回写 summary `metrics_json`。需 owner 在三种方案中决策：接受现状但保留流程约束、收回普通 runner ADS WRITER 并为 audit 做特批路径、或按表级 / 专用 SA 收窄 ADS 写权限。

- [x] 工程治理：修复 Dataform generated SQLX drift
  说明：已在单独 cleanup 分支重新运行 `scripts/dataform/generate_sqlx_from_sql.py`，同步 6 个 stale generated SQLX 文件，并新增 pytest 防复发检查；`--check`、Dataform compile、`python3 -m pytest tests` 和 `git diff --check` 已通过。

- [ ] OQ-005：如真实运行暴露 stale-lock 边界，再为 `ashare-pipeline-control` 的 stale-lock reclaim 增加 Workflows execution liveness 检查

- [ ] 若继续推进数据扩展，补 `lookback-capable` 价格构建输入
  说明：当前 2019 年初 60 日窗口通过 `has_full_history_60d=FALSE` 显式暴露并由样本掩码剔除；若要求 2019-01 起完整窗口，需要补专用构建输入或调整 DWD/DWS 构建方式。

- [ ] P1+ 资金面 / 事件 / 行业族 DWD 扩展
  说明：包括 `dim_stock_sw_industry_hist`、`dim_stock_ci_industry_hist` 及对应 QA。

- [ ] 实现 Cloud Run Python ledger resume：PR #127 分支已修复 review 指出的 resume 实现断链与 QA 字段问题，尚未跑测试、Cloud Run 或 BigQuery 验收。
