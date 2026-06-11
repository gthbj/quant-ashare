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


- [x] OQ-010：按 `PRD_20260611_04` 修复 research summary `created_date`/`run_id` 落库
  说明：PR #163 已合并到 `main`（merge commit `f0ba555`）：`09` summary INSERT 列清单补 `run_id`/`created_date`，ADS additive migration `sql/ads/04_alter_strategy1_backtest_summary_identity_columns.sql` 补列对齐 schema，`qa_runner_outputs` / `qa_cloudrun_schema_readiness` 加防复发断言。Live 已执行 ADS migration、schema readiness QA、现有 6 行 annual research summary 回填与 NOT NULL/created_date 查询复核；该前置已完成，可以进入 final refit / continuous 实现。

- [x] OQ-010：按 `PRD_20260611_02` 实现年度滚动 final refit 并六年重跑
  说明：PR #165 / #166 / #173 已合并并部署。正式 Strategy1 runner 镜像当前为 `sha256:4768d25f49de4bb1e8084476d6f1fe1542ed86750823751fa104738eb0947699`，annual plan 已按 OQ-014 工程缓解改为 `select -> build_refit_training_panel -> refit`，`source_panel_run_id` 指向独立 `__refit01` dedicated panel。2021-2026 dedicated refit panel / final refit 全部重跑成功，Cloud Run executions `strategy1-train-predict-job-t4vq7` / `bmdw6` / `jjblp` / `zwg82` / `9zm2h` / `qvc78`；六年 `qa_refit_register_predict_outputs` 全部通过。

- [x] OQ-010：按 `PRD_20260611_03` 实现 synthetic continuous merge 与正式 continuous ledger
  说明：PR #167/#168/#169/#170 已合并 synthetic continuous 能力、partition-filter hotfix、valid-window lineage hotfix 与 `QA-CONT-6` scope 修复。PR #173 后 official synthetic merge 已用 `--force-replace --require-source-refit` 基于 dedicated refit outputs 重写成功，registry rows=`1` / prediction rows=`2643406`（最新 insert job `d2f9beea-a58f-4650-82d2-07b135174ee9`，resolved manifest sha256=`2062d93544dd7c2bd12566f42da0ad3c973b5c6a63f00f4cd1c72a3a5269ba97`）；single continuous ledger 已成功（Cloud Run execution `strategy1-backtest-report-job-mq5d8`）；`qa_continuous_backtest_outputs` 已通过（job `fcd75906-ec42-454e-92e1-9b47d19a5727`）；`qa_lot_aware_ledger_outputs` 已通过（job `95dcee06-e912-481a-9c02-aafb14a823c5`）。Effective-window 正式结果：total_return=`0.8079208887460085`，compound_annual_return=`0.12036528993503204`，max_drawdown=`-0.4548151193656952`，information_ratio=`0.5420201365046585`。Rehearsal pre-refit continuous 保留为 diagnostic only。年度 fresh diagnostic backtest 是 optional，本轮未重跑；最终评价只用 single continuous ledger。

- [x] OQ-014：决定是否接受 effective-window annual final refit 结果进入 baseline 评估
  说明：DECISION-20260611-02 已关闭 OQ-014：接受当前 DWS 覆盖下的 effective-window annual final refit / continuous ledger 作为研究复盘与后续策略迭代事实口径，暂不投入 pre-2019 DWS lookback / valuation 覆盖重建。该关闭不等于 accepted baseline：最新 result 的 v3 contract Sharpe=`0.5285475500566089 < 0.70`、Calmar=`0.26464663290635254 < 1.0`，不得 promotion。

- [x] OQ-010：按 `PRD_20260611_05` 跑尾部风险 Overlay 三组 A/B
  说明：已在分支 `codex/strategy1-tail-risk-overlay-ab` 实现 `quant_ashare.strategy1.tail_risk_overlay_ab` 与 `qa_tail_risk_overlay_ab_outputs`，并完成 live research-only A/B：A1 `individual_risk_guard_v0`、A2 `market_risk_off_v0`、A3 `individual_and_market_risk_guard_v0` 三组 Cloud Run executions 全部成功，continuous / lot-aware / overlay QA 均通过。Review follow-up 后 enhanced overlay QA 与 research readiness QA 也通过。结果：A1/A3 能显著改善 2024-01-01~02-07 crunch 段 vs `000852.SH` 超额（baseline `-0.1932988013254472`，A1 `0.10932302982271269`，A3 `0.1226915291378361`），但全周期收益损耗过大；A2 将 MaxDD 从 `-0.4548151193656952` 降至 `-0.32883181037211673`，但 CAGR 从 `0.12036528993503204` 降至 `0.0850673652169256`，Calmar 从 `0.26464663290635254` 降至 `0.2586956691345056`。ADS 反向验证为 0 行，promotion manifest 为 0 行；结果仅研究口径，不改默认 profile、不 promotion。

- [ ] OQ-010：基于尾部风险 Overlay A/B 结果决定下一步风控路线
  说明：A1/A3 证明确实命中 crunch 段，但常年误伤过大；A2 是全周期 MaxDD/CAGR tradeoff 对照，但也未改善 Calmar。需 owner 决定是调窄 P1 规则、继续优化 market risk-off / A2，还是转向暴露管理 / 仓位控制 PRD；三种 overlay 均暂不设默认。

- [ ] OQ-011：按 `PRD_20260611_06` 做历史数据回填（2010+）与 true-five-year refit 重跑
  说明：ODS 14 endpoint 已从 2010 起可用（2026-06-11 探查证实 `daily`/`daily_basic` 2010-2014 有行）；DWD 价格仅 2015 起，DWS `2015-Q1` 与 `2019-01-02..2019-04-02`（含 `2019-04-01/02` 两个开市日，超出自然 Q1）的 `has_full_history_60d` 全部 FALSE（后者为陈旧标记，重刷该窗口即可修，只刷自然 Q1 会留两天缺口）。Phase A 历史下限前移 + 旗标修复 + `2019-04-03` 后 parity 硬门；Phase B 2021-2024 名义五年 refit 重跑（不重做选参）；Phase C 新 synthetic continuous 对比表交 owner 口径决策。

- [ ] OQ-010：按 `PRD_20260611_07` 做年度滚动调度 Phase 2 live 化
  说明：代码 PR 准备已在分支 `codex/prd07-annual-live-smoke` 完成：scheduler 新增显式 `--execute-live --candidate-only-smoke` live gate、真实 GCS generation-conditioned lease/state、Cloud Run execution 粒度 fanout tracking、matrix 前置检查（缺 `matrix_manifest.json` / `work_units.json` 时本地失败且不提交 Cloud Run）、artifact skip、state recovery、describe + artifact 双确认和 focused pytest 覆盖。尚未执行真实 Cloud Run live smoke，合并/部署后仍需先准备/复用对应 run-version 的 matrix artifact，再按 PRD_07 五场景做 candidate-only live smoke（kill-restart 恢复、artifact skip、lease 竞争、超时二次确认）；不跑完整 live 年度滚动（Phase 3 owner 另批）。

- [ ] OQ-010：基于 official continuous 结果决定下一轮策略改进或 accepted baseline 路线
  说明：2021-2026 effective-window official continuous 已成为当前研究复盘口径，但尚未 accepted。最新 result：compound_annual_return=`0.12036528993503204`，max_drawdown=`-0.4548151193656952`，information_ratio=`0.5420201365046585`，v3 contract Sharpe=`0.5285475500566089`、Calmar=`0.26464663290635254`，未过 v3 absolute gates。下一步应围绕降低回撤、提升 risk-adjusted return、改进候选空间/风控/调仓参数或 acceptance gate 评估流程做独立方案；不得把本轮结果直接 promotion 或标 accepted。

- [x] OQ-010：实现回测复合年化收益字段
  说明：PR #134 已扩展 ADS summary 契约并在 `09` 写出 `compound_annual_return` / `return_period_count` / annualization metadata，`10` 和 `24` QA 校验 `NAV 有效交易日数 - 1` 口径，report 默认展示复合年化；旧 `annual_return` / `sharpe` 保留 legacy 语义，不回填历史 run。



- [x] OQ-010：审计并删除旧 BQML / SQL ledger fallback
  说明：PR #131 分支已删除 BQML-only `sql/ml/strategy1/02-04`、SQL ledger fallback `08_run_backtest.sql` / `--use-bq-ledger` 和旧 `scripts/strategy1/run_oq010_experiments.py`，并同步收敛 README / runbook / memory 口径。

- [x] OQ-010：实现 Cloud Run Python ledger resume
  说明：已新增 PRD `docs/prd/PRD_20260609_01_策略1CloudRunLedgerResume.md`；目标是在 `ledger_exec_v1_lot100` 下支持从父回测现金、持仓、pending sell、NAV anchor 和调仓锚点继续运行。2026-06-11 PRD_08 验收已完成：parent `bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`，cut `2024-12-31`，resume child `bt_s1_resume_acceptance_resume_20250102_20260609_v20260611_01`；Cloud Run execution `strategy1-backtest-report-job-82454` 成功，两套 resume QA job `eb99f350-feb4-4fdc-977d-d2e6b7c74201` / `8b2b1e17-42ad-44d2-8318-9f283c26eee2` 通过，ADS 同 run/backtest 零行。正式结果若采用 resume segment，仍需 owner 显式批准。
- [ ] OQ-010：按 R14 长训练窗口 PRD 做覆盖审计
  说明：`docs/prd/PRD_20260609_01_策略1R14长训练回测.md` 已定义固定 R14 方法、`2015-04-01 ~ 2019-12-31` 名义训练窗口和 `2020-2022` 的 `10` 只 / `20` 只双组合 diagnostic backtest；`2023-01 ~ 2026-06-09` 追加回测视 P0 结果和 owner 决策而定，若追加也跑两个组合。PR #130 已修复显式 `backfill` 历史窗口下限，PR #132 已修复 `dim_stock` 历史生命周期；2015 年重跑后又暴露 core smoke 仍用 2019 作为全表存在下限，分支 `codex/fix-historical-backfill-core-smoke` 已修复，待合并部署后重新触发 2015 年补数。

- [x] OQ-012：正式关闭 schema mismatch 问题
  说明：owner 已确认归档关闭。schema contract、repair/validate 脚本和 `sql/qa/06_ods_parquet_schema_checks.sql` 都已具备；2026-06-05 P0 与 all 范围只读复核通过，当前 BigQuery 读层没有 mismatch 暴露。防复发规则继续保留在 `KNOWN_CONSTRAINTS.md`：新增/修复 ODS Parquet 必须按 schema contract 显式 cast 并跑 QA，历史 raw 修复默认走 GCS 原 Parquet schema-preserving rewrite。

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

- [x] 实现 Cloud Run Python ledger resume：PR #127 实现已在 PRD_08 中补齐 research-only 真实数据验收，两套 resume QA 通过；正式结果若采用 resume segment 仍需 owner 显式批准。
