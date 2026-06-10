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
  说明：`docs/prd/PRD_20260610_03_策略1年度滚动选参.md` 已定义年度 walk-forward 参数选择方案；`docs/prd/PRD_20260610_04_策略1年度滚动执行工程化.md` 已补执行工程化方案；`docs/prd/PRD_20260611_01_策略1年度滚动并发调度.md` 已补跨年度流水线调度方案，要求全局 candidate task 并发默认不超过 20，允许下一年训练与上一年慢候选并行，但本年 `select_register_predict` 必须等本年 11/11 候选完成；PR #161 review follow-up 后还要求 scheduler-level GCS generation-guarded lease lock、GCS state generation 条件写，以及 prepare/select/backtest 与 candidate 共享 `40 CPU / 160Gi` 全局资源池。Phase 1 scheduler dry-run 已在 PR #161 分支实现：新增 `quant_ashare.strategy1.annual_pipeline_scheduler`，输出跨年度 DAG、互斥锁计划、generation-conditioned state 模型和共享资源池模拟，并有 pytest 覆盖 lock ownership / state generation / 资源 admission；后续 review follow-up 已明确 `simulation_model=synchronous_waves`，dry-run 峰值只是 reference 不是 live capacity ceiling，且 `--no-tail-fill-single-task` 的 deferred batch 不再误记 succeeded。2021 单年度 Cloud Run smoke 已在正式 jobs 上闭环，CV fold 修复已实证为 11/11 候选 `cv_fold_count=3`，select/register/predict 与 backtest/report 均成功；另有旧 `f57ff0a` 镜像时代的 2021 历史 smoke 证据，确认 11/11 candidate 成功和 `cv_fold_count=3`，但不代表当前线上状态。annual rolling resolved plan 已把 `build_training_panel_risk_feature` 作为每年第一步显式纳入；PR #159 合并后已从 `main@f30c171` 重建并部署正式 Strategy1 runner 镜像 `sha256:b856f46f56ad5b9a9cd9ac8773e67090f702a06ff8931ca51e1d2e3bb24299d7`，五个正式 jobs 的 `--help` boot smoke 均成功。下一步在 PR #161 合并后做 Phase 2 candidate-only live smoke，把 active fanout 计数从 candidate-year proxy 改为 Cloud Run execution 粒度，再扩展完整 `2021-2026` 年度滚动，并用连续 ledger 评价，不拼接年度 fresh-run。


- [ ] OQ-010：按 `PRD_20260611_04` 修复 research summary `created_date`/`run_id` 落库
  说明：`09` summary INSERT 列清单补 `run_id`/`created_date`，ADS additive 补列对齐 schema，回填现有 6 行（需 owner 批准），`qa_runner_outputs` 加 NOT NULL 断言。必须先于 final refit / continuous 任何重跑执行。

- [ ] OQ-010：按 `PRD_20260611_02` 实现年度滚动 final refit 并六年重跑
  说明：valid 选参后用最近 5 年 refit selected candidate——复用既有 BigQuery panel（经 `source_panel_run_id` 读 selection run panel），重新 fit preprocessor，不消费冻结 matrix transformed arrays；独立 refit run_id + 溯源契约 + 训练窗口 QA 硬门；2021-2026 从 select 之后重跑（refit + predict + 可选年度 diagnostic），不重跑 panel/matrix/fanout。

- [ ] OQ-010：按 `PRD_20260611_03` 实现 synthetic continuous merge 与正式 continuous ledger
  说明：manifest 参数化逐年 test 窗口切片（排除 valid 段）+ 重叠/缺口/行数/溯源 QA + official continuous ledger（`2021-01-04` fresh-start 至 `2026-06-09`）。merge/QA 实现与彩排（pre-refit manifest）可与 final refit 并行先行；正式执行依赖六年 refit 重跑完成。

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

- [x] OQ-010 / 工程治理：为五个 Strategy1 Cloud Run jobs 建立 package entrypoint
  说明：分支 `codex/package-entrypoints` 已新增 `quant_ashare.strategy1.train_predict`、`prepare_matrix`、`train_candidate_task`、`select_register_predict`、`backtest_report` 五个稳定 package entrypoint；旧 `scripts.strategy1_cloudrun.*` 对应文件已缩为兼容 wrapper，并在普通 import 下 alias 到 package 实现。新增 pytest 覆盖旧/新入口 `--help` 输出一致、关键 `--dry-run` JSON plan 一致，以及 wrapper alias 到同一实现模块。PR #153 review follow-up 后已构建验证镜像 `strategy1-cloudrun-runner:package-entrypoints-6b1b3c7-20260610-01` / digest `sha256:101eab22ac1504fc03f42392fdb2db984c23715b441955a1f7ae0316ca35c172`，并用临时 job 跑通五个新 package entrypoint 的 `--help` smoke。本轮不改正式 Cloud Run Job spec、不删旧 wrapper。

- [x] OQ-010 / 工程治理：迁移五个正式 Strategy1 Cloud Run Job command 到 package entrypoint
  说明：PR #153 合并后，已从 `origin/main` merge commit `1775099` 构建正式镜像 `strategy1-cloudrun-runner:package-entrypoints-main-1775099-20260610-01`，digest `sha256:0dce0e78256140a92d7b73bc083e028b377b9a132f9e08ccfd57d4730d7ac8b7`；五个正式 jobs 已更新到该 digest，并把 `args` 从 `scripts.strategy1_cloudrun.*` 切到 `quant_ashare.strategy1.*`。五个正式 jobs 的 `--help` boot smoke 均成功：`strategy1-train-predict-job-wdfv4`、`strategy1-prepare-matrix-job-rxc5n`、`strategy1-train-candidate-fanout-job-rltvm`、`strategy1-select-register-predict-job-sh2bz`、`strategy1-backtest-report-job-mtj4t`；日志均匹配到 `usage:`。PR #153 临时 job `strategy1-package-entrypoint-help-smoke` 已删除。

- [x] OQ-010 / 工程治理：完成 package entrypoint 代码侧 cutover 与 wrapper 删除护栏
  说明：分支 `codex/package-entrypoint-code-cutover` 已同步 `pipeline_control`、native search、annual rolling 的 Cloud Run override args 到 `quant_ashare.strategy1.*` 五个 package entrypoint；`configs/strategy1/active_step_catalog.yml` 的 backtest/report caller 已切到 `quant_ashare.strategy1.backtest_report`；active runbook / 示例命令已更新。五个旧 job module 路径已纳入 retired-reference linter，且 linter 新增 catalog caller 检查；分支 `codex/entrypoint-active-scope-guard` 进一步补显式 pytest，断言五个旧入口路径必须在 banned refs 中且 non-historical active scopes 零命中。PR #156 已合并到 `main` 后重建正式镜像并部署到五个 jobs，digest `sha256:c84b47d8daea59d6d89dd5a1c218d6d1ee1a1195885a16c6d66a262a60f7305c`；五个正式 jobs 的 `--help` boot smoke 均成功：`strategy1-train-predict-job-vh59r`、`strategy1-prepare-matrix-job-fjshr`、`strategy1-train-candidate-fanout-job-cpxr2`、`strategy1-select-register-predict-job-82wsq`、`strategy1-backtest-report-job-44cmd`。旧 wrapper 仍保留兼容 import / CLI 路径。

- [x] OQ-010 / 工程治理：删除旧五 job wrapper
  说明：分支 `codex/delete-strategy1-job-wrappers` 已删除 `scripts/strategy1_cloudrun/train_predict.py` / `prepare_matrix.py` / `train_candidate_task.py` / `select_register_predict.py` / `backtest_report.py` 五个旧 job wrapper。old/new wrapper parity 测试已改为 package entrypoint `--help` / dry-run JSON smoke，且 package boundary 测试新增旧 wrapper 文件不存在断言；旧五模块路径仍留在 retired linter ban-list 和测试清单中防回流。

- [x] OQ-013 / 工程治理：决策并收敛 Strategy1 普通 runner 的 ADS 写权限
  说明：owner 已选择方案 1：接受现状但保留流程约束。五个普通 Strategy1 runner jobs 暂继续使用 `241358486859-compute@developer.gserviceaccount.com`，且该 SA 暂保留 `ashare_ads` WRITER，用于 ADS audit / 历史报告重渲染等兼容路径；不做 live IAM revoke。正式流程仍要求普通实验默认写 `ashare_research`，ADS 正式发布只走 owner-approved promotion job，显式 `--output-dataset-role ads` 仅作为历史 ADS audit / 兼容路径。

- [x] 工程治理：修复 Dataform generated SQLX drift
  说明：已在单独 cleanup 分支重新运行 `scripts/dataform/generate_sqlx_from_sql.py`，同步 6 个 stale generated SQLX 文件，并新增 pytest 防复发检查；`--check`、Dataform compile、`python3 -m pytest tests` 和 `git diff --check` 已通过。

- [ ] OQ-005：如真实运行暴露 stale-lock 边界，再为 `ashare-pipeline-control` 的 stale-lock reclaim 增加 Workflows execution liveness 检查

- [ ] 若继续推进数据扩展，补 `lookback-capable` 价格构建输入
  说明：当前 2019 年初 60 日窗口通过 `has_full_history_60d=FALSE` 显式暴露并由样本掩码剔除；若要求 2019-01 起完整窗口，需要补专用构建输入或调整 DWD/DWS 构建方式。

- [ ] P1+ 资金面 / 事件 / 行业族 DWD 扩展
  说明：包括 `dim_stock_sw_industry_hist`、`dim_stock_ci_industry_hist` 及对应 QA。

- [ ] 实现 Cloud Run Python ledger resume：PR #127 分支已修复 review 指出的 resume 实现断链与 QA 字段问题，尚未跑测试、Cloud Run 或 BigQuery 验收。
