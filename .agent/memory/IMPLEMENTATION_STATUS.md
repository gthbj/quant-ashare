# 实现状态（Implementation Status）

这是实现状态的唯一事实来源。面向「已完成/进行中/受阻的整体状态」；「下一步要做什么」见根目录 `TODO.md`。

Last updated: 2026-06-10

## 当前状态

### 最新补充（2026-06-10）：项目结构重构 Phase D0 research table contract 已实现

- 分支 `codex/add-research-table-contract` 已实现 `docs/prd/PRD_20260610_02_项目结构重构方案.md` 的 Phase D0。
- 新增 `sql/research/01_research_strategy1_tables.sql` 与 `sql/research/README.md`，定义 `data-aquarium.ashare_research` 的 Strategy1 research 表契约：训练面板、模型注册、预测、候选池、组合目标、订单计划、回测成交/持仓/NAV/ledger state/summary、信号监控、acceptance result、experiment run status 和 append-only promotion manifest。
- `sql/00_create_datasets.sql` 已新增 `ashare_research` schema contract；`configs/strategy1/active_step_catalog.yml` 已记录 research contract SQL，并校准 `model_prediction_daily` / `order_plan_daily` 的分区列元数据。
- 新增 `tests/strategy1/test_research_contract.py`，校验 catalog 中每个 `research_table` 都有 DDL、表名使用 `research_*`、分区列与 DDL 一致，且默认 `dataset_role="research"` 仍 fail-fast，只有 `allow_future_research=True` 才可解析 contract target。
- PR #140 review follow-up 已处理：`experiment_run_status` 当前侧通过 `ads_dataset: ashare_meta` 解析到既有 meta 状态表；`resolve_table_role` 支持 per-role dataset/project override；`build_order_plan.partition_columns` 已与 `order_plan_daily` 的 `rebalance_date` 对齐，并新增 step 输出分区一致性测试。
- 本轮不创建实际 BigQuery dataset / table，不切 runner 默认写入，不迁移历史 ADS，不实现 promotion job，也不改 Cloud Run / Workflows。
- 验证：`python3 -m pytest tests` 32 passed；`python3 scripts/dataform/generate_sqlx_from_sql.py --check` 通过；`npx --yes @dataform/cli compile dataform` 通过；`(cat sql/00_create_datasets.sql; cat sql/research/01_research_strategy1_tables.sql) | bq query --dry_run --use_legacy_sql=false --location=asia-east2` 通过；`git diff --check` 通过。

### 最新补充（2026-06-10）：OQ-005 Cloud Run Job IAM bootstrap TODO 已收口

- 复核确认 PR #126 `fix(orchestration): grant workflow runtime job override IAM` 已于 2026-06-09 合并到 `main`，merge commit `54fe077bb656f23b5ff9384f348e49b7a5259e94`。
- `orchestration/workflows/bootstrap_scheduler_iam.sh` 已包含 runtime SA 所需的 project-level `roles/run.viewer`、job-level `roles/run.jobsExecutorWithOverrides`，并移除旧 job-level `roles/run.invoker`。
- 本轮只清理过期状态：根目录 `TODO.md` 中 “OQ-005：合并 2026-06-09 scheduled ODS run 暴露的 Cloud Run Job IAM bootstrap 修正” 已勾选完成；未修改 Workflows、IAM bootstrap 脚本、Cloud Run、BigQuery 或生产配置。

### 最新补充（2026-06-10）：Dataform generated SQLX drift 已修复

- 分支 `codex/fix-dataform-generated-drift` 已从最新 `origin/main` 重新运行 `scripts/dataform/generate_sqlx_from_sql.py`，同步 6 个 stale generated SQLX 文件。
- 新增轻量 pytest `tests/dataform/test_generated_sqlx.py`，直接调用 `scripts/dataform/generate_sqlx_from_sql.py --check`，让后续跑测试时自动暴露 canonical SQL 与 generated SQLX 漂移。
- 改动包含 `dataform/definitions/**/*.sqlx` 生成产物、Dataform drift 防回归测试与项目记忆/TODO；未修改 canonical `sql/`、`dataform/action_manifest.json`、Workflows、Cloud Run 或 BigQuery 执行入口。
- 本轮验证：`python3 -m pytest tests` 25 passed；`python3 scripts/dataform/generate_sqlx_from_sql.py --check` 通过；`npx --yes @dataform/cli compile dataform > /tmp/quant_ashare_dataform_compile.json` 通过；`git diff --check` 通过。
- 根目录 `TODO.md` 中 “工程治理：修复 Dataform generated SQLX drift” 已勾选完成。

### 最新补充（2026-06-10）：项目结构重构 Phase A-C 已实现并完成 PR #136 review follow-up

- 分支 `codex/strategy1-structure-refactor` 已按 `docs/prd/PRD_20260610_02_项目结构重构方案.md` 实现 Phase A/B/C。
- 新增 `configs/strategy1/active_step_catalog.yml`，覆盖当前 Strategy1 shared SQL、旧路径、目标路径、调用方、参数契约、table role、当前 ADS dataset role 和未来 research dataset role。
- 新增 `src/quant_ashare/strategy1/{catalog,sql_render,table_roles,retired_lint}.py` 与 `pyproject.toml`；Cloud Run image 在 `Dockerfile.strategy1-cloudrun` 中执行 `pip install --no-deps -e .`，旧 `scripts.strategy1_cloudrun.*` wrapper 保留。Review follow-up 已修复 retired linter 在 Python 3.11/3.12 下 `**` scope 只扫目录的问题，并补正向测试确认 active 文件确实被扫描。
- 当前 active/shared Strategy1 SQL 已迁移到 `sql/strategy1/**`；`sql/ml/strategy1/README.md` 与 `sql/cloudrun/strategy1/README.md` 只保留 historical/audit note。
- `backtest_report.py`、search orchestrator、risk-feature manifests 和 v3 replay QA helper 已改为通过 catalog step / 新路径解析；当前 resolver 默认仍解析到 `data-aquarium.ashare_ads.*`，显式 `dataset_role="research"` 在当前阶段 fail-fast，未创建或写入 `ashare_research`。
- PR #136 review follow-up 已明确：本 PR 合并 Phase A/A2/B/C 是 owner 对 `DECISION-20260610-05` 拆分顺序的一次性豁免，后续 Phase D/E 仍需单独 PR；`sql/strategy1/README.md` 已说明 `audit_only` SQL 与 active SQL 同 namespace 但执行状态以 catalog 为准。
- `ledger.py` 中被后置同名函数覆盖的 resume/fresh 参数校验已恢复到最终生效函数：非法 resume 参数现在 fail-fast，符合既有 resume 约束。
- PR #136 review follow-up 已删除 PASS 型自查文档；Dataform generated SQLX drift 已作为独立 TODO 记录。
- 本轮补测：`pytest tests/strategy1 tests/strategy1_cloudrun tests/pipeline_control` 24 passed；catalog validate、retired linter、active step render smoke、compileall、CLI dry-run/help 和 `git diff --check` 均通过。
- `scripts/dataform/generate_sqlx_from_sql.py --check` 仍失败，但本分支相对 `origin/main` 没有 `dataform/` diff；失败项是现有 generated SQLX stale/missing 文件，不由本次 Strategy1 SQL 迁移引入。

### 最新补充（2026-06-10）：Strategy1 年度滚动选参 PRD 已新增

- 新增 `docs/prd/PRD_20260610_03_策略1年度滚动选参.md`，定义年度 walk-forward 参数选择、上一整年 valid、选中参数 final refit 和连续 ledger 回测方案。
- PRD 固定 P0 为 `strategy1_pv_fin_risk_v0_20260606`、`20` 只持仓、`7.5%` 单票上限、`biweekly`、`ledger_exec_v1_lot100`，先只搜索 11 个预先冻结的 LightGBM regression 可选候选；B26 binary 只作为 diagnostic-only reference，不参与 `selected_candidate_id`。
- 年度窗口固定为：`2015-2019 train / 2020 valid / 2016-2020 final refit / 2021 backtest`，随后逐年滚动到 `2020-2024 train / 2025 valid / 2021-2025 final refit / 2026 backtest`。
- valid 选参门采用 owner 确认口径：`valid_rank_ic > 0`、`valid_top_minus_bottom > 0`、五指数任一 valid 超额收益 `> 0`、valid 最大回撤 `>= -33.33%`、`valid_sharpe >= 0.3`、`valid_calmar >= 0.3`、五指数任一 `valid_excess_calmar_ratio > 0.3`；不要求 `valid_total_return > 0`。
- PRD 明确 valid 年不能作为同年最终样本外成绩；年度预测可分年生成，但最终评价必须来自一条连续 ledger，不能拼接每年 fresh-run。
- PR #137 review follow-up 已补充：删除 `valid_total_return > 0` 的理由改为避免重复硬门，不表示允许负收益候选通过；label embargo 删除错误的 `final refit /` 措辞；B26 binary 明确为 diagnostic-only reference。
- 本轮只写 PRD、决策和项目记忆/TODO；未改 runner、SQL、BigQuery、Cloud Run 或 Dataform。

### 最新补充（2026-06-10）：项目结构重构总 PRD 已新增

- 新增 `docs/prd/PRD_20260610_02_项目结构重构方案.md`，定义 `quant-ashare` 后续工程结构重构方案。
- Review follow-up 后，PRD 将实施顺序收敛为 active path catalog、防误用护栏、table role / dataset role resolver、Strategy1 shared SQL 稳定命名空间、Python package foundation、`ashare_research` / `ashare_ads` 生命周期隔离、深层包拆分与命名收敛。
- PRD 明确 active SQL catalog 必须覆盖 `sql/ml/strategy1/**` 和 `sql/cloudrun/strategy1/**`，并校验 SQL `DECLARE p_*` 参数契约，避免路径或默认值半迁移。
- 最新 review follow-up 已进一步明确 Phase A2 `optional_params` 必须使用结构化对象，`sql/ml/strategy1/16-25` 只能由 Phase A catalog 从调用方反推逐个分类，不能在 PRD 中预判整段均为 active。
- Owner 已确认结构重构关键决策：后续采用 `ashare_research` dataset、`research_*` 表名前缀、`accepted != promoted`、先 table-role abstraction 后 research-first、`sql/strategy1/**` 目标 SQL 命名空间、`src/quant_ashare/**` Python 包根、短期保留 `scripts/strategy1_cloudrun/**` wrapper，且 P0 不强制创建 `docs/retired/`。
- 方案明确旧 BQML-only SQL / SQL ledger runner 已退役，剩余 `sql/ml/strategy1/**` 与 `sql/cloudrun/strategy1/**` 中仍有当前 Cloud Run Python path 使用的 active shared SQL，应迁移到 `sql/strategy1/**` 而不是直接删除。
- 本轮只写 PRD 和项目记忆/TODO，并追加 `DECISION-20260610-05`；未改代码、SQL、BigQuery、Cloud Run 或 Dataform。

### 最新补充（2026-06-10）：2015 backfill 暴露 core smoke 2019 全表下限误杀

- PR #132 已合并，`ashare-pipeline-control` 已从 `main` 重新部署到 revision `ashare-pipeline-control-00007-tst`。
- 重新触发 2015 年 warehouse backfill：`209bd2bf-86f4-455c-85c7-b6b1f4ec8025`。
- 本次已越过 `dim_stock` 历史生命周期缺口，后续失败于 `sql/qa/01_core_smoke_checks.sql` 的旧全表断言：`dwd_stock_eod_price must not write rows before dwd_start_date`。
- 根因是 core smoke 仍把 `2019-01-01` 当成全表存在下限；但显式 historical `backfill` 已允许 2015-2018 行写入，且后续 `qa_only` 也不应因为已有历史行失败。
- 分支 `codex/fix-historical-backfill-core-smoke` 已将 core smoke 改为只拒绝早于 A 股日线支持历史下限 `1990-12-19` 的行；`daily_current` / full rebuild 的 2019+ 生产下限继续由窗口 SQL 和窗口 QA 约束。

### 最新补充（2026-06-10）：2015 backfill 暴露 dim_stock 历史生命周期缺口

- PR #130 合并并部署 `ashare-pipeline-control` 后，重新触发 2015 年 warehouse backfill：`be12a12f-1e65-4cef-b60d-3945ef8da13a`。
- 本次已越过原来的指数 DWD 2019 下限失败点，但失败于股票窗口 QA `QA-WIN-13: ODS daily rows in DWD window must be represented in dwd_stock_eod_price`。
- 诊断显示 2015 ODS daily 有 `5,486` 行、`76` 个代码未写入 DWD；其中 `75` 个代码是 `dim_stock.list_date` 晚于 2015 交易日，`1` 个代码 `000022.SZ` 不在 `dim_stock`。
- 分支 `codex/fix-historical-dim-stock-lifecycle` 已将 `dim_stock` 生命周期改为用全量 ODS daily 派生缺主数据代码，并在 `stock_basic.list_date` 晚于首个日线交易日时用 `first_trade_date` 作为历史生命周期下限；尚未重新部署或重跑 2015 backfill。
- PR #132 review follow-up 已去除重复的 `daily_codes` 全量 ODS daily 扫描，缺主数据派生直接复用 `daily_lifecycle`。

### 最新补充（2026-06-10）：PR #127 Cloud Run ledger resume review follow-up 已修复

- PR #127 review follow-up 已在分支修复 Cloud Run ledger resume 实现问题：补齐 resume imports/params/dataclass、`run_ledger` parent-state restore 与 state table 写入、manifest/CLI/SQL metadata 贯通、`25` QA ADS 表/字段口径，以及测试 import。
- 尚未运行测试、BigQuery 或 Cloud Run 验证。

### 最新补充（2026-06-09）：2015-2018 手工 backfill 下限修复已在分支实现

- 为执行 Strategy1 R14 长训练窗口，手工触发 `ashare_warehouse_window_refresh` 的 2015 年 backfill 时，指数窗口刷新在 `sql/incremental/02_refresh_index_dwd_window.sql` 因固定 `2019-01-01` 下限失败，错误为 `index DWD window refresh requires write_end_date >= write_start_date`。
- 分支 `codex/fix-2015-index-backfill` 已将窗口刷新和窗口 QA 的日期下限改为按模式区分：`daily_current` 仍保持 `2019-01-01` 生产下限，显式 `backfill` 允许 owner 指定 2019 年以前历史窗口。
- 改动范围包括股票 DWD/DWS 窗口、指数 DWD 窗口、market-state 窗口，以及对应股票 / 指数窗口 QA；尚未重新触发 2015-2018 生产补数。

### 最新补充（2026-06-09）：Strategy1 R14 长训练窗口回测 PRD 已新增

- 新增 `docs/prd/PRD_20260609_01_策略1R14长训练回测.md`，定义固定当前 R14 LightGBM regression 方法，不重新搜索参数，使用名义训练窗口 `2015-04-01 ~ 2019-12-31`，先跑 `2020-01-02 ~ 2022-12-30` 的 `10` 只 / `20` 只双组合 diagnostic backtest；`2023-01 ~ 2026-06-09` 追加回测视 P0 结果和 owner 决策而定，若追加也跑两个组合。
- PRD 明确 `5d` 标签必须做 embargo：训练样本只保留未来 5 日标签完整落在 `2019-12-31` 及以前的信号日，避免 2019 年末样本使用 2020 回测期收益形成标签。
- PRD 将 P0 组合设为 `target_holdings=10` / `max_single_weight=15%` 与 `target_holdings=20` / `max_single_weight=7.5%` 两个变体，并明确当前 Cloud Run Python ledger P0 仍是 fresh-start；后续如单独跑 `2023-2026-06-09` 只能作为追加诊断，正式连续结果默认必须从 2020 重新 fresh-run，除非 Cloud Run Python ledger resume 已实现并通过 resume consistency QA。
- 该 PRD 只写方案，未执行 BigQuery / Cloud Run；下一步是只读覆盖审计 2015-2018 DWD/DWS、risk feature、market-state 和 label embargo 样本数。

### 最新补充（2026-06-10）：Strategy1 旧 BQML / SQL ledger runner P0 退役已实现

- PR #131 分支已按 owner 决策删除 BQML-only `sql/ml/strategy1/02-04`、SQL ledger fallback `sql/ml/strategy1/08_run_backtest.sql` 和旧 `scripts/strategy1/run_oq010_experiments.py`。
- `scripts/strategy1_cloudrun/backtest_report.py`、`orchestrate_experiments.py`、`orchestrate_sklearn_native_search.py` 已移除 `--use-bq-ledger` 入口；回测默认固定走 Cloud Run Python `ledger_exec_v1_lot100`，legacy FLOAT 审计只保留 Python `--use-float-ledger`。
- 当前仍保留并使用共享 SQL `01`、`05-07`、`09-10`、`12`、`16-24`，服务 Cloud Run Python path 的 training panel、candidate、portfolio、order、report、QA 和 replay；本次不删除历史 ADS / GCS artifact。
- 本轮未运行 BigQuery / Cloud Run / pytest；只做代码入口删除、文档口径收敛和项目记忆更新。

### 最新补充（2026-06-09）：OQ-005 旧 Composer 补跑 helper 已清理

- `scripts/pipeline/run_warehouse_refresh.py` 是 Composer 时代通过 `gcloud composer environments run` 触发 `ashare_warehouse_window_refresh` 的补跑 / resume helper；当前生产入口已切到 `Cloud Scheduler + Cloud Workflows` 且 `ashare-composer` 已删除，因此该脚本已从仓库移除。
- 后续窗口补跑 / QA-only / full rebuild 恢复路径以 `docs/Pipeline-补跑与故障恢复-Runbook.md` 和 `orchestration/workflows/**` 为准；不得把旧 Composer helper 重新作为 active 运维入口。
- PR #129 review follow-up 已同步清理 `.agent/memory/OPEN_QUESTIONS.md` 中对旧 helper 的现行工具描述，避免后续 agent 继续按 Composer-era 脚本补跑。

### 最新补充（2026-06-09）：Strategy1 live acceptance gate 已在分支切到 v3

- Cloud Run Python search 的默认 acceptance contract 已从 `model_acceptance_contract_v1.yml` 切到 `model_acceptance_contract_v3.yml`；v1 保留为历史搜索审计契约。
- live orchestrator 在回写 ADS 前会按实际 backtest span / manifest final_holdout window 和 v3 contract 的五指数集合重算候选级 Sharpe / Calmar / 复合年化、策略最大回撤同期超额和 Excess Calmar，并把 v3 状态写入 registry / backtest summary / comparison artifact；contract 的 replay 默认窗口不再无条件套用于 live。
- `19` QA 已改成 v3-aware：v3 accepted 不再套用旧的 000852 / final_holdout hard gate，而是检查 v3 信号质量、Sharpe、Calmar 和五指数相对门摘要；`21` risk-feature QA 已把旧的风险回撤 overlay 约束限定在 legacy contract。
- 已用 PR #125 分支镜像 `strategy1-cloudrun-runner:pr125-smoke-3210a7f` 和临时 `*-pr125-smoke` Cloud Run jobs 跑通 2 候选 live v3 smoke：prepare matrix、2 个 candidate fanout、select/register/predict、backtest/report、19 QA 和 comparison artifact 上传均 succeeded。smoke 结果为 Top-K 1 rejected，registry 写出 `model_acceptance_contract_v3`、`strategy1_acceptance_gate_v3`、`000001.SH`、5 个 comparison benchmark 和 v3 Sharpe / Calmar；`v3_relative_gate_by_benchmark.csv` 已生成。smoke 过程中发现逐指数 artifact 的 `search_id` 未透传，已在分支修复。

### 最新补充（2026-06-08）：OQ-005 调度迁移已完成 production cutover

- 生产调度唯一入口已经切到 `Cloud Scheduler + Cloud Workflows`：`ashare-ods-ingestion-daily`（`0 20 * * *`）负责 ODS daily + child warehouse refresh，`ashare-pipeline-alert-checker`（`0 * * * *`）负责小时级告警检查。
- `ashare_pipeline_alert_checker`、`ashare_ods_ingestion_daily`、`ashare_warehouse_window_refresh` 与 `ashare_warehouse_full_rebuild` 的 Workflows 路径都已完成部署；`qa_only`、`daily_current`、`backfill`、非交易日 skip、alert checker 和 full rebuild dry-run 都已有真实 smoke 证据。
- `ashare-composer` 环境已于 2026-06-08 删除完成；`orchestration/composer/**` 现在只保留为 retired / audit-only 历史快照，不再是现行生产路径。
- `docs/Pipeline-补跑与故障恢复-Runbook.md` 已改写为 Workflows 版恢复手册，告警链路不会再把 on-call 指向已删除的 `ashare-composer` 操作命令；`scripts/alerting/README.md` 与 `setup_alerts.py` 的描述也已同步到 Scheduler + Workflows 路径。
- 2026-06-09 首次 20:00 scheduled ODS run 暴露 runtime SA 权限缺口：Cloud Run Job 需要 `run.jobs.runWithOverrides`，operation polling 需要 `run.operations.get`；live IAM 已补 `roles/run.jobsExecutorWithOverrides`（job-level）和 `roles/run.viewer`（project-level），bootstrap 脚本也已同步修正。
- 2026-06-09：在 PR #127 分支开始实现 Cloud Run Python ledger resume：manifest/CLI 透传 resume 字段，Python ledger 写入 `ads_backtest_ledger_state_daily` 并支持从父 backtest 状态恢复，SQL contract/QA 增加 `rebalance_anchor_start` 与 `cloudrun_lot100_resume_v1` 口径。尚未运行 BigQuery/Cloud Run 验证。

### 最新补充（2026-06-08）：Strategy1 `v3` replay / `24` QA 已收口为 contract-driven 路径

- `configs/strategy1/model_acceptance_contract_v3.yml` 已作为 `v3` 口径唯一事实来源。
- `scripts/strategy1/replay_acceptance_gate_v3.py` 与 `scripts/strategy1/run_acceptance_gate_v3_replay_qa.py` 已按最新 contract 真执行通过；当前结果仍为 `25` 个候选里 `1 accepted / 24 rejected`。
- `24_qa_acceptance_gate_v3_replay_outputs.sql` 已不再依赖手工镜像默认值：replay scope、Top-K、benchmark 集合、窗口、阈值和允许的 `score_orientation` 都由 helper 从 contract 渲染。

### 最新补充（2026-06-08）：当前仍开放的主线只剩 OQ-010 与 OQ-012

- OQ-010：Cloud Run Python 路径已打通，但当前仍没有 accepted Python baseline；后续重点仍是寻找可接受模型 / 特征 / 风险控制组合。
- OQ-012：schema contract、修复/验证脚本和 `06_ods_parquet_schema_checks.sql` 都已具备，当前 BigQuery 读层无 mismatch 暴露；剩余是 owner 是否正式关闭该问题，或保留防复发工程项。

## 已完成（Completed）

- P0 数仓底座已完成：4 张 DIM、5 张 DWD、核心 QA 和单位契约均已落地并通过 BigQuery smoke。
- OQ-003 / OQ-004 / OQ-006 已实现并关闭：财务三大报表 DWD + `dws_stock_feature_fin_daily`、`dim_index` / `dwd_index_eod` benchmark 口径、`ods_field_unit_map` 与 `05_unit_contract_checks.sql` 均已进入 `main`。
- OQ-005 已完成从 Composer 迁出：thin control-plane、ODS daily / warehouse window refresh / alert checker / full rebuild 四条 Workflows 路径已落地，生产 scheduler 已切换，Composer 环境已删除。
- `orchestration/composer/**` 已完成历史目录收口：README 改为 retired / audit-only 说明，保留的 DAG/helper 只用于审计、迁移对照和受控回滚参考。
- OQ-005 active recovery runbook 已完成 Workflows 改写：当前恢复命令使用 `gcloud workflows execute`、`gcloud scheduler jobs run/describe`、Cloud Run Jobs 与 BigQuery 状态表，不再使用 Composer / Airflow。
- 策略 1 历史 BigQuery ML runner、中文报告、GCS uploaded 模式、模型质量诊断、live-available 预测池口径和 score orientation 校准都已完成；这些结果只保留为 historical reference / audit，不再作为未来默认执行路径。
- Strategy1 `v3` acceptance gate 的只读 replay、helper 驱动的 `24` QA 和 contract-driven 参数注入已实现并真执行通过。
- `000001.SH` 的 ODS / DIM / DWD / DWS 链路已补齐，`dws_market_state_daily` 已保留 `market_state_v0_20260606` 兼容行并新增 `market_state_v1_20260607` 上证指数字段。

## 进行中 / 部分（In Progress）

- OQ-010：Cloud Run Python / native 模型路线仍在探索，当前 binary / regression / risk-feature 多轮候选都未产生 accepted baseline；live acceptance gate 正在从 v1 切到 v3，PR #125 分支已完成 2 候选 smoke。
- OQ-012：schema repair 工具链和 QA 已 ready，当前问题更偏向收口决策，而不是缺实现。
- OQ-005：主迁移已完成，只剩 cutover 后短观察窗记录和少量非阻断运维收尾。

## 未开始 / 未来（Not Started / Future）

- 若后续真实运行暴露 stale-lock 边界，再为 `ashare-pipeline-control` 的 stale-lock reclaim 增加 Workflows execution liveness 检查。
- 若 owner 决定继续精修 OQ-012，可把 schema contract / cast 防复发要求进一步前推到 ingestion 发布链路。
- 若 owner 决定继续推进策略侧，优先做 OQ-010 可接受 Python baseline，而不是恢复 BQML / SQL runner 路线。
- `lookback-capable` 价格构建输入、P1+ 资金面/事件/行业族 DWD、`dim_stock_sw_industry_hist` / `dim_stock_ci_industry_hist` 仍是后续扩展项。

## Coverage Snapshot

| 能力 | 状态 | 备注 |
|---|---|---|
| ODS 理解 | 高 | 57 张外部表字段与分区语义已摸清 |
| DWD/DIM 设计 | 高 | 主文档与命名/单位/分区约束已稳定 |
| P0 表物化/QA | 已完成 | 4 张 DIM + 5 张 DWD + 核心 QA 已通过 |
| DWS/ADS 设计 | 已完成 | 两篇设计文档已完成；策略 1 主体契约已落地 |
| OQ-005 调度迁移 | 已完成 | 生产入口已切到 `Cloud Scheduler + Cloud Workflows`，Composer 已删除 |
| 财务三大报表 DWD | 已完成 | `dwd_fin_income/balancesheet/cashflow` + `_latest` 与 `04/05` QA 已通过 |
| 市场状态 DWS | 已完成首版 | `dws_market_state_daily` 已进入生产链路，保留 v0 + v1 口径 |
| Strategy1 历史 BQML runner | 已完成 | 只保留为历史 reference / audit |
| Strategy1 Cloud Run Python 路线 | 部分完成 | 执行链路已可运行；live acceptance gate 已在分支切到 v3 并通过 2 候选 smoke，但仍无 accepted baseline |
| ODS schema repair | 部分完成 | contract / tooling / QA 已具备，待 owner 决定最终收口 |

## 2026-06-10 - Strategy1 回测复合年化收益 PRD

- 状态：已在 PR #134 实现，待 owner review / 部署。
- 新增 `docs/prd/PRD_20260610_01_策略1回测复合年化收益.md`，定义 `compound_annual_return`、`return_period_count`、`annualization_target_period_count` 和 `annualization_method` 的 P0 字段方案。
- PR #134 扩展 `ads_backtest_performance_summary` 契约，新增 `compound_annual_return`、`return_period_count`、`annualization_target_period_count`、`annualization_method`；`09_build_metrics_and_report_inputs.sql` 对新 run 写出复合年化字段和 `metrics_json.annualization`。
- `return_period_count` 固定为 `NAV 有效交易日数 - 1`；`10_qa_runner_outputs.sql` 和 `24_qa_acceptance_gate_v3_replay_outputs.sql` 均按该口径重算校验。
- 明确保留旧 `ads_backtest_performance_summary.annual_return` / `sharpe` 为 legacy 字段，P0 不静默改义、不追溯覆盖历史回测。
- `render_report.py` 默认展示复合年化收益，并把旧 `annual_return` 标为 `Legacy annual_return`。
- PR #134 review follow-up 修复 `total_return = -100%` 边界：`09`、`10`、`24`、`render_report.py` 和 `replay_acceptance_gate_v3.py` 统一允许 `gross == 0` 返回复合年化 `-100%`，仅拒绝 `gross < 0`。
- 本次未执行 BigQuery / Cloud Run；部署后只对新 run 生效，历史 run 如需复合年化需 owner 单独批准回填。

最新执行备注（2026-06-10 / OQ-010 年度滚动选参 CV）：分支 `codex/fix-dynamic-cv-folds` 修复 Strategy1 Cloud Run Python CV fold 生成逻辑。旧代码在 `evaluate_cv_folds` 中硬编码 `cv_2021/cv_2022/cv_2023`，导致 `2015-2019 train + 2020 valid` 年度滚动选参 smoke 的 `cv_panel` 虽有 1,707,710 行但 `cv_fold_count=0`。新逻辑基于 `cv_panel` 里 `split_tag='train'` 的年份动态生成最多 3 个 rolling fold，并排除外部 valid 年；新增单元测试覆盖新旧窗口形态。未运行测试；合并后需重跑 2021 smoke 验证 CV 指标实际产出。
