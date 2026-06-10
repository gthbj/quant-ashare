# 实现状态（Implementation Status）

这是实现状态的唯一事实来源。面向「已完成/进行中/受阻的整体状态」；「下一步要做什么」见根目录 `TODO.md`。

Last updated: 2026-06-11

## 当前状态

### 最新补充（2026-06-11）：PRD_04 research summary identity 修复已合并并完成 live migration / 回填

- PR #162 已合并到 `main`（merge commit `ce795e5`），三个年度滚动正式化 PRD 已进入主线；旧 PRD worktree 已清理，本地/远端 `claude/prd-refit-continuous-summary` 分支已删除。
- PR #163 已合并到 `main`（merge commit `f0ba555`），实现 `docs/prd/PRD_20260611_04_ResearchSummary落库修复.md` 的代码侧修复：新增 ADS additive migration `sql/ads/04_alter_strategy1_backtest_summary_identity_columns.sql`，为 `ads_backtest_performance_summary` 补 `run_id` / `created_date`；`09` summary INSERT 显式写入 `p_run_id` / `CURRENT_DATE()`；`qa_runner_outputs` 增加 summary identity NOT NULL / run_id 对账断言；`qa_cloudrun_schema_readiness` 将 ADS summary 两列纳入 required columns，并把失败信息指向新 migration。
- 新增 `tests/strategy1/test_backtest_summary_identity_contract.py`，锁住 migration、`09` INSERT、runner QA 和 schema readiness 四个契约点，防止后续 summary identity 列再次漂移。
- 已在 BigQuery live 执行 `sql/ads/04_alter_strategy1_backtest_summary_identity_columns.sql`，两条 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 均完成；随后复跑 `sql/strategy1/qa/qa_cloudrun_schema_readiness.sql`，4 条 schema assertion 全部 successful。
- 已按显式 6 个 annual rolling `backtest_id` 回填 `research_backtest_performance_summary.run_id` / `created_date`，UPDATE affected rows=6；`run_id` 取 `JSON_VALUE(metrics_json,'$.prediction_run_id')`，`created_date=DATE(created_at)`。只读复核确认：目标 6 行 `null_run_id=0`、`null_created_date=0`、`run_id_mismatch=0`、`created_date_mismatch=0`，`created_date=2026-06-10` 过滤可查到 6 行；time-travel hash 对比确认排除 `run_id` / `created_date` 后 6 行非目标字段无变化。
- 验证：`PYTHONPATH=src python3 -m pytest -q tests` 105 passed；`python3 scripts/dataform/generate_sqlx_from_sql.py --check` 通过；`PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint` 通过；`bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ads/04_alter_strategy1_backtest_summary_identity_columns.sql` 通过；`python3 -m compileall -q src scripts tests` 与 `git diff --check` 通过；live PRD_04 backfill NOT NULL assertion successful。

### 最新补充（2026-06-11）：年度滚动 refit / continuous / summary 修复三 PRD 已新增

- 分支 `claude/prd-refit-continuous-summary` 新增三个 PRD，收口 2021-2026 首轮年度滚动实跑暴露的问题：
  - `docs/prd/PRD_20260611_02_策略1年度滚动FinalRefit.md`：当前实现在 valid 选参后未执行 final refit（2026 selected model 训练窗口为 `2020-01-02 ~ 2024-12-24`，PRD 要求 `2021-01-04 ~ 2025-12-24`）；方案为 `refit_register_predict` 步骤复用既有 BigQuery panel（经 `source_panel_run_id` 读 selection run panel，重新 fit preprocessor，不消费冻结 matrix transformed arrays）+ 独立 refit run_id 溯源契约 + 训练窗口 QA 硬门，六年从 select 之后重跑，不重跑 panel/matrix/fanout。
  - `docs/prd/PRD_20260611_03_策略1SyntheticContinuous正式回测.md`：manifest 参数化的逐年 test 窗口切片 merge（排除 valid 段）、重叠/缺口/行数/溯源 QA、official continuous ledger（`2021-01-04` fresh-start 至 `2026-06-09`）；彩排用 pre-refit 预测可立即先行，正式执行依赖 02 完成。
  - `docs/prd/PRD_20260611_04_ResearchSummary落库修复.md`（简短）：6 行年度 summary `created_date`/`run_id` 为 NULL 的根因已实证（`09` INSERT 列清单不含这两列、ADS 表本无此两列、research 渲染只重写表名）；方案为 ADS additive 补列 + `09` 列清单修复 + 回填 + QA NOT NULL 断言；该修复必须先于 02/03 的任何重跑。
- 本轮 docs/记忆-only，未改代码、未执行 BigQuery / Cloud Run。当前 6 年年度 diagnostic 结果在 refit 修正前不得作指标解读。

### 最新补充（2026-06-11）：年度滚动 pipeline scheduler Phase 1 dry-run 已实现

- 分支 `codex/annual-pipeline-scheduler-impl` 基于 PR #161 PRD 分支新增 package entrypoint `quant_ashare.strategy1.annual_pipeline_scheduler`，实现年度滚动并发调度 Phase 1 dry-run。
- Scheduler 复用现有 annual rolling experiment/window 生成逻辑，输出 2021-2026 `panel` / `matrix` / `candidate` / `select` / `diagnostic_backtest` / `continuous_ledger` DAG；`select:yYYYY` 依赖本年全部 11 个 candidate unit，下一年 `panel` / `matrix` 不依赖上一年 `select`。
- Dry-run 输出 scheduler-level GCS generation-guarded lease lock 计划、GCS state generation-conditioned write 模型、stage token 表和资源模拟；prepare `8 CPU / 32Gi`、select/backtest `4 CPU / 16Gi` 与 candidate `2 CPU / 8Gi` 共享同一 `40 CPU / 160Gi` 全局资源池。
- 新增 `tests/strategy1/test_annual_pipeline_scheduler.py`，覆盖年度 DAG 依赖、scheduler lock ownership、candidate 饱和阻止 prepare、state generation mismatch 和 CLI JSON dry-run；catalog caller / package import 测试已同步。
- PR #161 follow-up 已明确 dry-run `simulation_model=synchronous_waves`：当前峰值是同步 wave 参考值，不是 live overlap 容量上限；dry-run fanout 计数仍是 candidate-year proxy，Phase 2 live scheduler 必须改为 Cloud Run execution 粒度。`--no-tail-fill-single-task` 下的尾部 candidate batch 现在标记为 `deferred`，不会被误记为 succeeded。
- 本轮未执行 Cloud Run、BigQuery 或 GCS 写入，未修改 job spec / IAM；后续进入 Phase 2 前仍需先合并 PRD / 实现 PR，并按小规模 candidate-only live smoke 验证真实状态恢复与 artifact skip。

### 最新补充（2026-06-11）：年度滚动跨年份并发调度 PRD 已新增

- 新增 `docs/prd/PRD_20260611_01_策略1年度滚动并发调度.md`，定义 Strategy1 年度滚动执行从“按年份串行”升级为“跨年份流水线 + 全局资源上限调度”的后续工程方案。
- PRD 明确候选训练可以跨年度流水线并发：上一年慢候选仍在 running 时，下一年的 `build_training_panel`、`prepare_matrix` 和候选 fanout 可在资源空位内启动；但本年 `select_register_predict` 必须等待本年全部 candidate unit 成功，不能把慢候选隐式排除。
- PRD 将默认全局 candidate task 并发上限定为 `20`，并把 `2 CPU / 8Gi` candidate task、prepare、select 和 backtest/report 纳入资源 token 模型，避免 6 年 * 11 候选形成 66 task 无上限并发。
- PR #161 review follow-up 已补齐两个 P0 设计约束：scheduler 必须复用 GCS generation-guarded lease lock + heartbeat 做实例互斥，GCS state JSON 必须用 generation precondition 条件写；prepare `8 CPU / 32Gi`、select `4 CPU / 16Gi`、backtest `4 CPU / 16Gi` 与 candidate 共享同一 CPU / memory token 池，不能在 20 个 candidate 已占满 `40 CPU / 160Gi` 时额外启动 prepare。
- PRD 要求 scheduler 可 dry-run、可恢复、按 `(year, unit_index)` 跟踪状态，并在 `gcloud --wait` / 控制面轮询超时时通过 Cloud Run execution / task list / GCS artifact 二次确认，避免把已成功 execution 误判为失败。
- 本轮只写 PRD 并同步 TODO / 项目记忆；未改 runner 代码、未运行 BigQuery、未启动 Cloud Run、未改变 job spec 或 IAM。

### 最新补充（2026-06-10）：PR #159 后 Strategy1 main 镜像已部署

- PR #159 已合并到 `main`，merge commit `f30c1716a55995d169955e1a7c4663d39b82a382`。为让年度滚动 plan、`quant_ashare.strategy1.sql_runner` 和 reporting import 与线上运行时代码对齐，已从当前 `main@f30c171` 重新构建正式 Strategy1 runner 镜像。
- 本次构建使用一次性 Cloud Build config，只推固定 tag `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:annual-plan-main-f30c171-20260610-01`，未更新 `latest`；Cloud Build `4dfba35e-cbaf-4727-9596-137010c9d6ea` succeeded，digest 为 `sha256:b856f46f56ad5b9a9cd9ac8773e67090f702a06ff8931ca51e1d2e3bb24299d7`。
- 五个正式 Strategy1 Cloud Run jobs 已更新到该 immutable digest：`strategy1-train-predict-job`、`strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`。读回确认 command/args 仍为 `quant_ashare.strategy1.*` package entrypoint，SA 仍为 `241358486859-compute@developer.gserviceaccount.com`，`maxRetries=0`，CPU/memory/timeout 保持不变，fanout 仍为 `taskCount=40`、`parallelism=20`。
- 五个正式 jobs 的 `--help` boot smoke 均成功且 Cloud Logging 均匹配到 `usage:`：`strategy1-train-predict-job-gwpn7`、`strategy1-prepare-matrix-job-rjgzf`、`strategy1-train-candidate-fanout-job-njl4q`（本次 smoke 用 `--tasks=1`）、`strategy1-select-register-predict-job-njmxd`、`strategy1-backtest-report-job-jj7ng`。
- 本轮只更新五个普通 Strategy1 runner jobs 的 image 并做只读 help smoke；未修改 promotion job，未执行 BigQuery 写入，未启动年度滚动实跑。下一步可按最新 main 镜像执行完整 `2021-2026` 年度滚动，并用 continuous ledger 评价。
- PR #160 review follow-up：`KNOWN_CONSTRAINTS.md` 不再记录具体 Strategy1 runner image digest；该 digest 属滚动运维状态，以本节最新部署记录为准，约束文件只保留 package entrypoint、wrapper 已删和 retired linter 防回流等长期规则。

### 最新补充（2026-06-10）：年度滚动 resolved plan 已显式纳入 training panel build

- 分支 `codex/annual-training-panel-plan` 基于 `origin/main` commit `d8ac505`，修复 annual rolling orchestrator 的 plan 缺口：每个年度 command plan 第一项现在是 `build_training_panel`，执行 catalog step `build_training_panel_risk_feature`，后续才是 prepare matrix、candidate fanout、select/register/predict 和可选 yearly diagnostic backtest/report。
- 新增 package entrypoint `quant_ashare.strategy1.sql_runner` CLI，可用 `--step` + `--params-json-b64` 执行 catalog SQL step；annual plan 通过该 CLI 生成可直接运行的本地 BigQuery SQL 命令，并显式传 `--output-dataset-role=research`。`scripts.strategy1_cloudrun.sql_runner` 仅保留兼容 re-export。
- 抽出 `scripts/strategy1_cloudrun/training_panel.py`，让 native search 与 annual rolling 共用同一套 training panel SQL 参数生成逻辑，避免窗口字段漂移。
- `configs/strategy1/active_step_catalog.yml` 已把 `build_training_panel_risk_feature` 的 caller 补充为同时覆盖 annual rolling orchestrator。
- 旧 worktree `/Users/fisher/Desktop/git/quant-ashare-annual-rolling-exec` 中的 2021 后续 smoke 记录只作为历史证据保留：它发生在旧 `main@f57ff0a` / 旧 runner image 时代，确认 `s1_annual_roll_y2021_train2015_2019_valid2020_n20_w075_v20260610_01` 的 11/11 candidate 成功、`cv_fold_count=3`、select/register/predict 与 backtest/report 成功；但不代表当前 package entrypoint / wrapper 删除后的线上部署状态。
- 本轮不修改 Cloud Run job spec、不重建镜像、不执行 BigQuery 或 Cloud Run 写入；完整 `2021-2026` 年度滚动仍需后续按最新 plan 执行并用 continuous ledger 评价。

### 最新补充（2026-06-10）：缺失本机/运行依赖可直接安装的 owner 约定已记录

- 从已清理的旧 `codex/remove-composer-refresh-helper` 分支中只保留仍有效的 owner 约定：本项目执行过程中如缺失必要本机 / 运行依赖，Agent 可直接安装最小必要依赖并继续任务。
- 旧分支 PR #129 已合并；重复 PRD 暂存和基于旧记忆文件的冲突编号变更未沿用。旧分支本地脏改动已保存在 `stash@{0}`，未提交到 `main`。
- 新增 `DECISION-20260610-13`，并在 `KNOWN_CONSTRAINTS.md` 记录授权边界：不覆盖密钥 / 凭据 / 隐私、未脱敏敏感日志、显著云成本、生产权限边界或 job spec / IAM 变更、破坏性数据操作。

### 最新补充（2026-06-10）：Strategy1 旧五 job wrapper 已删除

- 分支 `codex/delete-strategy1-job-wrappers` 基于 `origin/main` commit `5772f30` 删除五个已退役 job wrapper：`scripts/strategy1_cloudrun/train_predict.py`、`prepare_matrix.py`、`train_candidate_task.py`、`select_register_predict.py`、`backtest_report.py`。
- 五个正式 Cloud Run jobs、pipeline-control / native search / annual rolling override args、catalog caller 和 active runbook 已在前序 PR 切到 `quant_ashare.strategy1.*` package entrypoint；本轮不修改线上 job spec、不重建镜像。
- 旧五模块路径仍保留在 `retired_reference_lint.banned_active_refs` 和测试清单中，继续防止 active scopes 回流；`tests/strategy1/test_package_boundaries.py` 新增断言确认五个旧 wrapper 文件不存在。
- `tests/strategy1/test_cloudrun_package_entrypoints.py` 已从 old/new wrapper parity 改为 package entrypoint `--help` smoke 与 dry-run JSON 解析测试；非 job wrapper 兼容层（如 `acceptance`、`ledger`、`orchestrate_experiments`）仍保留。
- 验证：`PYTHONPATH=src python3 -m pytest -q tests/strategy1 tests/strategy1_cloudrun` 92 passed；`PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint` 通过；`python3 -m compileall -q src scripts tests` 通过；`git diff --check` 通过。

### 最新补充（2026-06-10）：Strategy1 package entrypoint 代码侧 cutover 已随 main 镜像部署

- PR #156 已合并到 `main`，merge commit `2156bb4b5a1d40c358a738395e01c10803ffa825`。由于 orchestrator / search 会从镜像内代码生成 Cloud Run override args，合并后已从该 `origin/main` commit 重建正式 Strategy1 runner 镜像。
- 本次构建使用一次性 Cloud Build config，只推固定 tag `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:entrypoint-main-2156bb4-20260610-01`，未更新 `latest`；Cloud Build `a11eca10-db4a-478f-b69c-6f8866cc5598` succeeded，digest 为 `sha256:c84b47d8daea59d6d89dd5a1c218d6d1ee1a1195885a16c6d66a262a60f7305c`。
- 五个正式 Strategy1 Cloud Run jobs 已更新到上述 immutable digest：`strategy1-train-predict-job`、`strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`。读回确认 job args 仍为 `quant_ashare.strategy1.train_predict` / `prepare_matrix` / `train_candidate_task` / `select_register_predict` / `backtest_report`，SA 仍为 `241358486859-compute@developer.gserviceaccount.com`，`maxRetries=0`，CPU/memory 与 fanout `taskCount=40`、`parallelism=20` 保持不变。
- 五个正式 jobs 的 `--help` boot smoke 均成功，Cloud Logging 均匹配到对应 `usage:`：`strategy1-train-predict-job-vh59r`、`strategy1-prepare-matrix-job-fjshr`、`strategy1-train-candidate-fanout-job-cpxr2`（smoke 覆盖为单 task）、`strategy1-select-register-predict-job-82wsq`、`strategy1-backtest-report-job-44cmd`。
- 这次完成的是代码侧 cutover 合并后的 main 镜像部署闭环；旧 `scripts.strategy1_cloudrun.*` wrapper 仍保留为兼容层，后续删除需单独 PR，并同步调整 old/new wrapper parity 测试。

### 最新补充（2026-06-10）：Strategy1 legacy job entrypoint active-scope guard 已补强

- 分支 `codex/entrypoint-active-scope-guard` 在 PR #155 合并后的 `origin/main` 上补强代码侧 cutover 护栏。
- `tests/strategy1/test_retired_lint.py` 新增显式清单 `scripts.strategy1_cloudrun.train_predict` / `prepare_matrix` / `train_candidate_task` / `select_register_predict` / `backtest_report`，断言这五个旧 job module 必须保留在 `retired_reference_lint.banned_active_refs` 中，并直接扫描 non-historical active scopes 确认零命中。
- 该测试沿用 retired linter 的 historical exception 语义：`sql/ml/strategy1/README.md` 等 historical/audit 文档不作为 active 违规，active 代码、脚本、SQL、catalog caller 和 runbook 继续被 linter 守卫。
- 本地验证：`python3 -m pytest -q tests/strategy1/test_retired_lint.py` 5 passed；`PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint` 通过。

### 最新补充（2026-06-10）：Strategy1 package entrypoint 代码侧 cutover 已实现

- 分支 `codex/package-entrypoint-code-cutover` 基于 PR #154 合并后的 `origin/main`，同步代码侧仍硬编码旧五 job module 的 active 调用点。
- `quant_ashare.strategy1.pipeline_control` 生成的 Cloud Run command 已从 `scripts.strategy1_cloudrun.train_predict` / `prepare_matrix` / `train_candidate_task` / `select_register_predict` / `backtest_report` 切到对应 `quant_ashare.strategy1.*` package entrypoint。
- `scripts.strategy1_cloudrun.orchestrate_sklearn_native_search` 与 `orchestrate_annual_rolling_selection` 仍作为现有脚本入口保留，但其内部发出的 TopK select/register/predict、backtest/report 与 annual plan command 均改为 package module；两者显式加入本地 `src` path 以支持未安装 editable package 的 checkout 运行。
- `configs/strategy1/active_step_catalog.yml` 中由 backtest/report 执行的 active step caller 已切为 `quant_ashare.strategy1.backtest_report`。五个旧 job module 路径已加入 `retired_reference_lint.banned_active_refs`，且 `retired_lint` 新增 catalog caller 专门检查，避免 catalog 本身因规则配置跳过而漏报。
- Active runbook / 示例命令已切到 package 入口：单 job 入口使用 `quant_ashare.strategy1.train_predict` / `prepare_matrix` / `train_candidate_task` / `select_register_predict` / `backtest_report`，多实验 orchestrator 示例使用 `quant_ashare.strategy1.pipeline_control`。
- 旧五 job wrapper 本轮不删除，仍保留兼容 import / CLI 路径；删除需等代码侧 cutover 合并并验证后单独评估，同时调整 wrapper parity 测试。
- 本地验证：`python3 -m pytest -q tests/strategy1 tests/strategy1_cloudrun` 91 passed；`python3 -m compileall -q src scripts tests` 通过；`python3 scripts/dataform/generate_sqlx_from_sql.py --check` 通过；`git diff --check` 通过；`PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint` 通过；`quant_ashare.strategy1.pipeline_control`、native search、annual rolling 三个入口 `--help` smoke 通过。

### 最新补充（2026-06-10）：五个正式 Strategy1 Cloud Run jobs 已切到 package entrypoint

- PR #153 已合并到 `main`，merge commit `1775099a6f8e3722dcf6ecead60f4fc0263115a1`。从该 `origin/main` merge commit 构建正式镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:package-entrypoints-main-1775099-20260610-01`，Cloud Build `6c91beb7-1ac7-4401-8218-a9b657455de9` succeeded，digest `sha256:0dce0e78256140a92d7b73bc083e028b377b9a132f9e08ccfd57d4730d7ac8b7`。该构建使用一次性 Cloud Build config，只推固定 tag，未更新 `latest`。
- 五个正式 Strategy1 Cloud Run jobs 已更新到上述 immutable digest，并把容器 args 从旧 `scripts.strategy1_cloudrun.*` module 切到 package module：`strategy1-train-predict-job` -> `quant_ashare.strategy1.train_predict`、`strategy1-prepare-matrix-job` -> `quant_ashare.strategy1.prepare_matrix`、`strategy1-train-candidate-fanout-job` -> `quant_ashare.strategy1.train_candidate_task`、`strategy1-select-register-predict-job` -> `quant_ashare.strategy1.select_register_predict`、`strategy1-backtest-report-job` -> `quant_ashare.strategy1.backtest_report`。
- 读回确认五个 jobs 的 command 仍为 `python`，SA 仍为 `241358486859-compute@developer.gserviceaccount.com`，`maxRetries=0`，CPU/memory、timeout、taskCount/parallelism 保持原值；fanout job 仍为 `taskCount=40`、`parallelism=20`、`2 CPU / 8Gi`。
- 五个正式 jobs 的 `--help` boot smoke 均成功且 Cloud Logging 均存在 `usage:`：`strategy1-train-predict-job-wdfv4`、`strategy1-prepare-matrix-job-rxc5n`、`strategy1-train-candidate-fanout-job-rltvm`、`strategy1-select-register-predict-job-sh2bz`、`strategy1-backtest-report-job-mtj4t`。
- PR #153 验证遗留的临时 job `strategy1-package-entrypoint-help-smoke` 已删除并确认不存在。
- 本轮只切正式 Cloud Run job spec 和镜像，不修改 repo 代码中的 orchestrator override args、catalog `caller` 或 runbook 示例；这些代码侧 cutover 与旧 wrapper 删除护栏仍需单独 PR。

### 补充（2026-06-10）：五个 Strategy1 Cloud Run package entrypoint 已建立，线上 job command 后续已迁移

- 分支 `codex/package-entrypoints` 基于 PR #152 后的 `origin/main`，为五个现有 Strategy1 Cloud Run jobs 建立稳定 package entrypoint：`quant_ashare.strategy1.train_predict`、`quant_ashare.strategy1.prepare_matrix`、`quant_ashare.strategy1.train_candidate_task`、`quant_ashare.strategy1.select_register_predict`、`quant_ashare.strategy1.backtest_report`。
- 旧 `scripts.strategy1_cloudrun.train_predict`、`prepare_matrix`、`train_candidate_task`、`select_register_predict`、`backtest_report` 已缩为兼容 wrapper；普通 import 下 alias 到 package 实现模块，CLI `python -m scripts.strategy1_cloudrun.*` 仍调用同一 `main()`，保持旧入口可运行。
- 新增 `tests/strategy1/test_cloudrun_package_entrypoints.py`，用 subprocess 对五个旧/新入口分别校验 `--help` 输出一致、关键 `--dry-run` JSON plan 一致；`tests/strategy1/test_package_boundaries.py` 补 package import smoke 和 wrapper alias 检查。
- 验证：手工五入口 old/new `--help` 与 dry-run parity 通过；`python3 -m pytest -q tests/strategy1/test_package_boundaries.py tests/strategy1/test_cloudrun_package_entrypoints.py tests/strategy1_cloudrun/test_dataset_role_routing.py tests/strategy1_cloudrun/test_dynamic_cv_folds.py` 35 passed；`python3 -m pytest -q tests/strategy1 tests/strategy1_cloudrun` 87 passed；`python3 -m compileall -q src scripts tests` 和 `git diff --check` 通过。
- PR #153 review follow-up：五个 wrapper 的 `sys.modules` alias 已补注释，避免未来误删；cutover TODO / 约束已补全为 job spec、override args、catalog caller、runbook 示例四类范围，并明确删 wrapper 前 active scopes 内旧路径 grep 必须为 0 且 retired linter 兜底。
- 已从 PR #153 HEAD `6b1b3c7` 构建验证镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:package-entrypoints-6b1b3c7-20260610-01`，Cloud Build `b906160e-1ae3-4acb-851f-bd19ac248f47` succeeded，digest `sha256:101eab22ac1504fc03f42392fdb2db984c23715b441955a1f7ae0316ca35c172`。该构建使用一次性 Cloud Build config，只推固定 tag，未更新 `latest`。
- 临时 Cloud Run job `strategy1-package-entrypoint-help-smoke` 指向上述 digest，分别 override args 跑通五个新 package entrypoint 的 `--help` smoke，execution 均 `Completed=True` 且日志存在 `usage:`：`train_predict`=`...-w2g7d`、`prepare_matrix`=`...-tcf7s`、`train_candidate_task`=`...-df6vr`、`select_register_predict`=`...-b2lc5`、`backtest_report`=`...-vbfgg`。
- PR #153 本身不修改正式 Cloud Run Job spec、不部署五个线上 jobs、不删除旧 wrapper；正式 job command 迁移已在后续 cutover 执行，见上一节。代码侧 override args / catalog caller / runbook 示例迁移仍需单独 PR。

### 最新补充（2026-06-10）：项目结构重构 D3/E main 镜像已部署，promotion job 已上线 dry-run

- PR #150 已合并到 `main`，merge commit `f421c83c1987d5f8eb067991e9d4f6624206306a`。
- 已从合并后的 `origin/main` 新建 detached 部署 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-d3e-main-deploy`，用 Cloud Build 构建正式 Strategy1 runner 镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:research-d3e-main-f421c83-20260610-01`，build id `e6b385e7-c386-40be-8adb-e00fc48045c1`，digest 为 `sha256:fdb61f8141e240c377b3faaa21b5e6efef9c783ebb9e04923ff3b675b8d54bc2`。
- 五个现有 Strategy1 Cloud Run jobs 已更新到该 immutable digest：`strategy1-train-predict-job`、`strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`；读回确认 command/args、CPU/memory、taskCount/parallelism、SA 和 maxRetries 保持预期。
- 只读 boot smoke 全部成功：`strategy1-train-predict-job-rrjmf`、`strategy1-prepare-matrix-job-7bgfl`、`strategy1-train-candidate-fanout-job-jtw78`、`strategy1-select-register-predict-job-p88c9`、`strategy1-backtest-report-job-glntc`。这些 execution 均用 `--help` 覆盖 args，不写 BigQuery。
- 新建专用 service account `strategy1-promotion-runner@data-aquarium.iam.gserviceaccount.com`，授予 project `roles/bigquery.jobUser`，并在 `ashare_research` / `ashare_ads` dataset 授予 WRITER；普通五个 runner jobs 仍使用原 compute SA，未改 command。
- 新建 promotion 专用 Cloud Run job `strategy1-promote-research-to-ads-job`，使用同一 D3/E digest，command 为 `python -m scripts.strategy1.promote_research_to_ads`，SA 为 `strategy1-promotion-runner@data-aquarium.iam.gserviceaccount.com`，`taskCount=1`、`cpu=1`、`memory=2Gi`、`maxRetries=0`。
- Promotion job boot smoke `strategy1-promote-research-to-ads-job-6kqd7` 成功；完整参数 review-only dry-run `strategy1-promote-research-to-ads-job-4mkrv` 成功，日志包含 `Review-only mode. Re-run with --execute to write ADS and promotion manifest.`。验收查询确认 `promotion_id='promo_deploy_smoke_20260610_01'` 在 `research_promotion_manifest` 行数为 `0`，未写 ADS / manifest。
- 部署后复跑 live BigQuery `sql/research/03_qa_research_schema_readiness.sql` 通过，7 条 `QA-RESEARCH-SCHEMA-*` assertion successful。
- PR #151 review follow-up 已确认普通 runner jobs 使用的 compute SA 仍具备 `ashare_ads` WRITER；owner 已选择方案 1，接受现状但保留流程约束，不修改线上 IAM。OQ-013 已关闭归档；普通实验仍默认 research-first，ADS 正式发布仍只走 owner-approved promotion job。
- 本轮仍未执行真实 owner-approved promotion；后续只有 owner 明确批准具体 accepted research run 后，才按 runbook 先 review-only 再带 `--execute` promotion。

### 最新补充（2026-06-10）：项目结构重构 Phase D3/E promotion job 与包化已实现

- 分支 `codex/strategy1-d3e-promotion-package` 在独立 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-d3e-promotion-package` 基于 PR #149 合并后的 `origin/main` 实现 Phase D3/E。
- D3：新增 `src/quant_ashare/strategy1/promotion.py` 和 CLI `scripts/strategy1/promote_research_to_ads.py`。Promotion 需要显式 `promotion_id`、source run/backtest/model、date window、`approval_ref`、`approved_by`、acceptance contract version/hash；默认要求 source research 已 accepted，只有显式 `--allow-unaccepted` 才绕过；ADS 目标已有行时 fail-fast，只有显式 `--force-replace` 才清理覆盖。
- Promotion 默认复制 publishable research outputs 到 ADS：model registry、prediction、candidate、portfolio target、order plan、backtest trade/position/NAV/ledger state/summary 和 signal monitor；大体量 training panel 默认不复制，需 `--include-training-panel` 或显式 `--target-role training_panel`。写入后只更新 research promotion lifecycle 字段，并向 `research_promotion_manifest` 写 `promotion_status='succeeded'`、`target_ads_tables`、approval metadata 和 promotion code version；promotion 不反写 `acceptance_status='accepted'` 或 `research_status='accepted'`。
- PR #150 review follow-up 已修复：CLI 默认 / `--print-sql` 均为 review-only，真实写 ADS 必须显式 `--execute`；source backtest trade / NAV 增加窗口外行数为 0 的完整性 guard，summary 检查 `start_date` / `end_date` 被 promotion window 覆盖；runbook 说明失败 attempt 会因事务回滚不写 manifest 成功行，需通过 BigQuery job history / Cloud Run logs 审计；DECISION-20260610-11 记录 D3/E 同 PR 交付是本次 owner 接受的一次性边界豁免。
- Phase E：把 dataset routing helper、acceptance、ledger、reporting/backtest 和 pipeline-control/orchestrator 实现迁入 `src/quant_ashare/strategy1/**`；`scripts.strategy1_cloudrun.dataset_roles`、`acceptance`、`ledger`、`backtest_report`、`orchestrate_experiments` 改为短兼容 wrapper，Cloud Run entrypoint 名称暂不迁移。
- 新增 `src/quant_ashare/strategy1/legacy_names.py` 读取 catalog 的 `allowed_legacy_names`，并将 retired-reference linter active scope 扩展到 `src/**`，防止 Phase E 后新包路径绕过历史引用护栏。
- 新增运行手册 `docs/策略1ResearchPromotion运行手册.md`，明确 ordinary runner 不得隐式 promotion、promotion IAM 边界、dry-run/execute 命令、training panel opt-in 和验证口径。
- 验证：`python3 -m pytest -q tests` 79 passed；`python3 -m compileall -q src scripts tests` 通过；`python3 scripts/dataform/generate_sqlx_from_sql.py --check` 通过；`npx --yes @dataform/cli compile dataform` 通过（35 actions）；`git diff --check` 通过；promotion CLI `--dry-run --print-sql` 与单独 `--print-sql` 均停在 review-only 输出；BigQuery client dry-run 对 promotion script 返回 `dry_run=True`；55 条程序化 self-review invariant 全部通过。
- 本轮未执行真实 promotion、未部署专用 promotion Cloud Run job、未修改已有 Cloud Run job entrypoint；后续合并后如要线上使用，需要基于 main 镜像/环境部署 owner-approved promotion job 或按 runbook 手工执行。

### 最新补充（2026-06-10）：项目结构重构 Phase D2 default research-first 已部署并验收

- PR #148 已合并到 `main`，merge commit `13bf0b512b5def2b2ef51c42e504f439f87a4dcf`。
- 已从合并后的 `origin/main` 新建部署 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-d2-main-deploy`，用 Cloud Build 构建正式 Strategy1 runner 镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:research-d2-main-13bf0b5-20260610-01`，build id `e874d1bf-faad-4262-bacd-33cf01551425`，digest 为 `sha256:92c348536776cbcd8fb4f09def63509f0f1dfdf2f13f54d472dc078582b410f0`。
- 五个 Strategy1 Cloud Run jobs 已更新到该 immutable digest：`strategy1-train-predict-job`、`strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`；读回确认 image、SA、command/args、CPU/memory、taskCount/parallelism 保持预期。
- 只读 boot smoke execution `strategy1-backtest-report-job-7g2mj` 成功；Cloud Run args 未传 `--output-dataset-role`，stdout plan 显示默认 `output_dataset_role=research`。
- 真实默认 research-first smoke execution `strategy1-backtest-report-job-2xr6f` 成功，run/backtest 为 `s1_default_research_d2_smoke_20260610_03` / `bt_s1_default_research_d2_smoke_20260610_03`。本次未传 `--output-dataset-role`，复用 D1 research prediction run `s1_sklearn_native_research_d1_smoke_20260610_04__l2_c_0_1`，覆盖连续 2025H1 窗口；report、runner QA、lot-aware ledger QA、model diagnosis QA、tail-risk diagnosis 与 tail-risk QA 全部 succeeded，日志中各 catalog step 均为 `dataset_role=research`。
- 验收查询确认 research 表写入完整且 ADS 同 run/backtest 零污染：candidate `61,620` 行、target `135` 行、order `157` 行、trade `203` 行、position `570` 行、NAV `117` 行、ledger state `117` 行、summary `1` 行、signal monitor `117` 行；ADS candidate/target/order/trade/NAV/summary 均为 `0` 行。summary `promotion_status='not_promoted'`，metrics_json 记录 D2 smoke experiment id、prediction run、weekly 调仓、5 只持仓与 market state。
- live BigQuery `sql/research/03_qa_research_schema_readiness.sql` 在 D2 部署后复跑通过，7 条 `QA-RESEARCH-SCHEMA-*` assertion successful。
- D2 的默认 research-first 已从代码、main 镜像、五个 jobs 和真实 research 写入 smoke 四层闭环；下一步保持 D3 promotion job 与 Phase E 包化为独立后续工作。

### 最新补充（2026-06-10）：项目结构重构 Phase D2 default research-first 已实现

- 分支 `codex/default-research-first` 在独立 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-default-research-first` 基于 PR #147 合并后的 `origin/main` 实现 Phase D2。
- Strategy1 默认输出 dataset role 已从 `ads` 切到 `research`：`RunnerConfig`、`configs/strategy1/cloudrun_runner_default.yml`、`configs/strategy1/annual_rolling_lgbm_regression_v0.yml`、SQL runner、report / diagnosis / tail-risk / acceptance / comparison / factor attribution 脚本默认均使用 `research`。
- `configs/strategy1/active_step_catalog.yml` 已把 `current_dataset_role` 和所有 active step 的 `output_dataset_role_current` 同步为 `research`，`research.enabled_by_default=true`；`resolve_table_role()` 与 SQL render 的裸默认跟随 catalog 当前 role。
- 显式历史 ADS fallback 保留：传 `--output-dataset-role ads` 时解析到 `ashare_ads` / `ashare_meta`；Cloud Run 子命令 / next-wave / orchestrator command / candidate fanout task 会始终显式下发 `--output-dataset-role=research|ads`，避免 job 镜像滚动更新期间继承错误默认值。
- 本轮不实现 owner-approved promotion job，不把普通 runner 隐式写入 ADS；D3 仍需单独实现 promotion manifest / ADS copy。
- 当前仅完成代码和本地验证，未用该分支重建或部署正式 Cloud Run jobs；合并后必须用 merge/main commit 重建正式 runner 镜像并更新五个 Strategy1 jobs。
- 验证：`python3 -m pytest -q tests` 69 passed；`tests/strategy1_cloudrun/test_dataset_role_routing.py` 19 passed；Dataform generated SQLX `--check` 通过；Dataform compile 通过；`compileall`、`git diff --check` 和 42 条程序化 self-review invariant 均通过；普通 orchestrator / sklearn native search / annual rolling dry-run 中 9 条 `train_candidate_task` 命令均含 `--output-dataset-role=research`；live BigQuery `sql/research/03_qa_research_schema_readiness.sql` 7 条断言全部 successful。

### 最新补充（2026-06-10）：D1 正式 main 镜像已部署，research readiness QA 已补齐

- PR #146 已合并到 `main`，merge commit `bca0e791abb57b3fb7efaa01b46e7444ac15cfb2`。
- 已从合并后的 `origin/main` 新建部署 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-research-d1-main-deploy`，用 Cloud Build 构建正式 Strategy1 runner 镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:research-d1-main-bca0e79-20260610-01`，digest 为 `sha256:c0ae9b2ec72b1299a08db66eb02881d0d3156735c14f08193d60e4388c9cc357`。
- 五个 Strategy1 Cloud Run jobs 已更新到该 immutable digest：`strategy1-train-predict-job`、`strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`；读回确认资源、SA、args、taskCount/parallelism 未被改乱。只读 boot smoke execution `strategy1-backtest-report-job-8krjt` 成功，验证镜像可启动。
- 分支 `codex/research-schema-readiness` 新增 research additive migration 与 readiness QA：`sql/research/02_research_strategy1_additive_migrations.sql` 用 idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 固化 `research_experiment_run_status.log_dir`；`sql/research/03_qa_research_schema_readiness.sql` 覆盖 15 张 research 表、关键列/类型、分区、聚簇、lifecycle DEFAULT、partition filter 与 `log_dir`。
- `configs/strategy1/active_step_catalog.yml` 已登记 `qa_research_schema_readiness`；`sql/research/README.md` 与 `sql/README.md` 已写明执行顺序 `01 contract -> 02 additive migrations -> 03 readiness QA`，并明确 `CREATE TABLE IF NOT EXISTS` 不会传播既有表新增列。
- live BigQuery 验证：`02_research_strategy1_additive_migrations.sql` 已执行为 no-op（`log_dir` 已存在），`03_qa_research_schema_readiness.sql` 7 条断言全部 successful。
- 本地验证：`python3 -m pytest -q tests` 66 passed（4 个 Python / SSL 环境 warning）；`python3 scripts/dataform/generate_sqlx_from_sql.py --check` 通过；`npx --yes @dataform/cli compile dataform` 通过；`compileall` 与 `git diff --check` 通过。
- D2 default research-first 的直接前置 now 是：合并本 research readiness PR 后，再单独开 D2 PR 切默认写入；promotion job 仍留 D3。

### 最新补充（2026-06-10）：项目结构重构 Phase D1 收尾 research smoke 已通过

- 分支 `codex/strategy1-research-d1-smoke` 在独立 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-research-d1-smoke` 基于最新 `origin/main` 完成 D1 收尾验收。
- 已部署 D0 research DDL：`sql/00_create_datasets.sql` 与 `sql/research/01_research_strategy1_tables.sql`；`ashare_research` 当前包含 15 张 research 表，runtime service account `241358486859-compute@developer.gserviceaccount.com` 已具备 dataset 写权限。
- 本轮修复 D1 smoke 暴露的问题：`research_experiment_run_status` 补 `log_dir` 字段；search QA 参数补 `p_strategy_id`；orchestrator heartbeat 在写 terminal status 前停止，避免覆盖 failed/succeeded；`qa_model_diagnosis_outputs` 的 `QA-POOL-5` 改为按显式 valid/test 窗口比较，避免把 valid/test 中间 gap 算入 DWS legacy 行数；research registry 在显式 research 模式下写出 `run_id/search_id/experiment_id/created_date/acceptance_status` 等契约列。
- 已重建并部署 Strategy1 Cloud Run jobs 到 D1 smoke 镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner@sha256:7ef5601980f1b202654b504a52c96e33c09f95d009ebdcf455b002e4913571f9`，随后跑通 research-mode smoke `sklearn_native_research_d1_smoke_20260610_04`：prepare、5 候选 fanout、select/register/predict、Top-1 backtest/report、diagnosis、tail-risk、acceptance patch 和 search-level QA 均 succeeded。
- 验收查询确认 research 表写入完整且 lifecycle 默认值正确：training panel `2,742,853` 行、prediction `502,501` 行、candidate `61,620` 行、target `135` 行、order `157` 行、trade `203` 行、position `570` 行、NAV `117` 行、ledger state `117` 行、summary `1` 行、registry `1` 行；所有 lifecycle bad count 为 `0`。ADS 侧同一 run/backtest 在 training panel、registry、prediction、candidate、target、order、trade、position、NAV、ledger state、summary 均为 `0` 行。
- 当前五个 Strategy1 Cloud Run jobs 仍指向 D1 smoke 验证镜像 digest；正式合并后应以 merge/main commit 重新构建部署，避免长期运行未合并分支镜像。
- PR #146 review Low follow-up 已登记：D2 default research-first 前需补 research additive migration 约定与 research 版 schema/readiness QA；`QA-POOL-5` 双窗口修复会同时影响 ADS 模式，未来复跑历史组合时 QA 结论可能改变，属于已知行为变更。
- 验证：`python3 -m pytest -q tests` 63 passed；`python3 scripts/dataform/generate_sqlx_from_sql.py --check` 通过；`npx --yes @dataform/cli compile dataform` 通过；`compileall` 与 `git diff --check` 通过；真实 BigQuery / Cloud Run D1 research smoke 通过。

### 最新补充（2026-06-10）：年度滚动执行 P0 工程骨架已实现

- 分支 `codex/annual-rolling-exec-impl` 在独立 worktree `/Users/fisher/Desktop/git/quant-ashare-annual-rolling-exec` 基于 `origin/main` 实现年度滚动执行 P0 工程骨架。
- 新增 ADS additive migration `sql/ads/03_create_strategy1_backtest_ledger_state_daily.sql`，只用 `CREATE TABLE IF NOT EXISTS` 补齐 Cloud Run ledger resume state 表；既有 `02_alter_strategy1_backtest_compound_annual_return.sql` 继续负责 performance summary 复合年化字段。
- 新增 `sql/strategy1/qa/qa_cloudrun_schema_readiness.sql`，检查 Cloud Run backtest/report 所需 ADS 表、字段类型、分区和 backtest_id clustering；并在 `configs/strategy1/active_step_catalog.yml` 注册稳定 step `qa_cloudrun_schema_readiness`。
- 新增年度滚动专用候选配置 `configs/strategy1/annual_rolling_lgbm_regression_v0.yml`，固定 PRD_03 的 11 个 LightGBM regression 候选、`20` 只持仓、`7.5%` 单票上限、`biweekly` 和 `strategy1_pv_fin_risk_v0_20260606`。
- 新增 `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`，可生成 `2021-2026` 年度 resolved experiment payload、matrix URI、Cloud Run command plan、B26 diagnostic-only reference 标记和连续 ledger backtest id；P0 wrapper 当前只实现 dry-run / resolved plan，非 dry-run 会 fail-fast，避免误把年度 fresh-run 拼接当正式结果。
- 本地 review follow-up 已处理：`subtract_weekdays` 明确限制为 12 月年末 label window，新增 pytest 防止 canonical ADS ledger state DDL 与 additive migration 漂移，并在 TODO 中标记 research smoke 前需补充 research readiness。
- 验证：`python3 -m pytest tests` 58 passed（4 个 Python / SSL 环境 warning）；未运行 BigQuery、Cloud Run 或 Dataform。

### 最新补充（2026-06-10）：年度滚动执行工程化 PRD 已新增

- 新增 `docs/prd/PRD_20260610_04_策略1年度滚动执行工程化.md`，把 2021 annual-selection smoke 暴露的三个工程问题固化为后续实现要求：annual rolling resolved experiment payload 自动生成、ADS additive schema migration、Cloud Run schema readiness QA。
- PRD 明确 P0 不改模型、不扩参数、不调 v3 gate、不切 `ashare_research`，只解决年度滚动从手工 smoke 到可重复正式执行的工程路径。
- PRD 要求 additive migration 只用 `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ADD COLUMN IF NOT EXISTS`，不得 `CREATE OR REPLACE` 已有 ADS 表，不回填历史 run。
- PRD 定义完整 `2021-2026` 结果必须来自单一 continuous ledger，或经过 resume-continuous QA 的 segment ledger；禁止把年度 fresh-run NAV 拼接成正式结果。
- PR #144 review follow-up 已处理：调仓频率固定为 `biweekly`；migration 文件避免与既有 `02_alter_strategy1_backtest_compound_annual_return.sql` 冲突；schema readiness QA 使用无数字前缀并要求登记 catalog；`scripts/strategy1_cloudrun` 标记为过渡 namespace；B26 binary 明确为 diagnostic-only reference。

### 最新补充（2026-06-10）：2021 年度滚动选参 Cloud Run smoke 已闭环

- PR #141 已合并到 `main`（merge commit `2565e0f`），正式 Strategy1 Cloud Run runner 已从该提交构建并部署为镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:2565e0f`。
- 使用正式 `strategy1-train-candidate-fanout-job` 重跑 2021 annual-selection candidate fanout，execution `strategy1-train-candidate-fanout-job-5f6qg` 成功完成；11 个候选全部 `cv_confirmation_status=passed`、`cv_fold_count=3`，fold 为 `cv_2018/cv_2019/cv_2020`。
- 使用 resolved experiment payload 重跑 `select_register_predict`，execution `strategy1-select-register-predict-job-pxtbw` 成功；选中候选为 `risk_lgbm_prd_strong_regularized_l5_l63_lr002_n300_leaf800_ff07_bf10`，`prediction_rows=808433`。
- 使用同一 payload 重跑 `backtest_report`，execution `strategy1-backtest-report-job-t5fg6` 成功；ledger 输出 `trades=1632`、`positions=3862`、`nav=243`、`state=243`，report、runner QA、lot-aware ledger QA、model diagnosis QA、tail-risk diagnosis 和 tail-risk QA 均完成。
- 本次运行暴露生产 BigQuery ADS schema 未完全应用最新代码契约：已用 additive DDL 补建 `ashare_ads.ads_backtest_ledger_state_daily`，并为 `ashare_ads.ads_backtest_performance_summary` 补列 `compound_annual_return`、`return_period_count`、`annualization_target_period_count`、`annualization_method`；未重建或覆盖已有 ADS 表。
- 2021 smoke 结果：`bt_s1_annual_param_select_train2015_2019_valid2020_pred2021_n20_w075_v20260610_01` 覆盖 `2021-01-04..2021-12-31`，`total_return=-8.08%`、`compound_annual_return=-8.39%`、`annual_vol=18.49%`、`sharpe=-0.382`、`max_drawdown=-19.54%`、相对 `000001.SH` `excess_return=-12.88%`。这只证明 2021 单年度链路闭环，不代表年度滚动 2021-2026 连续 ledger 已完成。

### 最新补充（2026-06-10）：项目结构重构 Phase D1b runner research routing 已实现，D1 smoke 待收尾

- 分支 `codex/strategy1-research-routing-d1b` 已实现 `docs/prd/PRD_20260610_02_项目结构重构方案.md` 的 Phase D1b：为 Strategy1 Cloud Run Python runner 增加显式 `output_dataset_role` routing。
- `RunnerConfig`、通用 CLI、resolved manifest 和 orchestrator status payload 均已记录 `output_dataset_role`；默认值仍是 `ads`，显式 `--output-dataset-role research` 才走 research 表族。为兼容已部署旧 Cloud Run 镜像，默认 ADS 子命令不下发 `--output-dataset-role=ads`，只有显式 research 才向子命令 / Cloud Run job 追加该 flag。
- 新增 `scripts/strategy1_cloudrun/dataset_roles.py`，封装 `TableResolver`、SQL dataset-role rewrite 和 research opt-in 校验；默认 SQL rewrite 排除 `acceptance_result`，避免 `ads_model_registry` 同时对应 `model_registry` / `acceptance_result` 时误替换。
- `train_predict.py`、`prepare_matrix.py`、`select_register_predict.py`、`ledger.py`、`backtest_report.py`、`orchestrate_experiments.py`、`orchestrate_sklearn_native_search.py` 和 `state.py` 已按 resolver 读取/写入 run-scoped Strategy1 表；ADS 模式保持现有表，research 模式指向 `ashare_research.research_*`，其中 research status 表为 `ashare_research.research_experiment_run_status`。
- 报告、诊断、尾部风险、acceptance replay/v2/window、comparison 和 factor attribution 脚本均新增 `--output-dataset-role`，并在 BigQuery 查询/summary 回写前做 dataset-role rewrite；historical BQML parity reference 仍按设计读取 ADS。
- 新增 `tests/strategy1_cloudrun/test_dataset_role_routing.py` 覆盖默认 ADS、显式 research、resolver/SQL rewrite、`ads_model_registry` 歧义、subcommand 透传、ledger/status routing、native query helper、acceptance diagnostic helper 和 factor attribution summary 回写。
- PR #143 review follow-up 已处理 research lifecycle 默认值：普通 research 输出默认 `research_status='candidate'`、`promotion_status='not_promoted'`，`research_promotion_manifest.promotion_status` 默认 `planned`，并新增 contract 测试防止回退为 NULL 语义。
- 本轮不创建或部署实际 BigQuery `ashare_research` 表，不修改 Cloud Run Job spec，不切 default research-first，不实现 promotion job；D1 真实验收仍需单独完成 D0 DDL 部署、Cloud Run 镜像重建、runtime service account 的 `ashare_research` 写权限，以及一次显式 research-mode smoke。读侧 routing 的模块级全局态风格收敛留到 Phase E 包化处理。
- 验证：`python3 -m pytest tests` 57 passed；`python3 scripts/dataform/generate_sqlx_from_sql.py --check` 通过；`npx --yes @dataform/cli compile dataform` 通过；BigQuery research DDL dry-run 通过；compileall、主要 CLI help/dry-run、41 条程序化 self-review checks 和 `git diff --check` 均通过。

### 最新补充（2026-06-10）：年度滚动选参动态 CV fold 已修复

- 分支 `codex/fix-dynamic-cv-folds` 修复 Strategy1 Cloud Run Python CV fold 生成逻辑。旧代码在 `evaluate_cv_folds` 中硬编码 `cv_2021/cv_2022/cv_2023`，导致 `2015-2019 train + 2020 valid` 年度滚动选参 smoke 的 `cv_panel` 虽有 1,707,710 行但 `cv_fold_count=0`。
- 新逻辑基于 `cv_panel` 里 `split_tag='train'` 的年份动态生成最多 3 个 rolling fold，并排除外部 valid 年；年度窗口会生成 `cv_2017/cv_2018/cv_2019`，旧 `2019-2023` 搜索窗口仍保持 `cv_2021/cv_2022/cv_2023` 及原边界形态。
- 新增 `tests/strategy1_cloudrun/test_dynamic_cv_folds.py` 覆盖新旧窗口形态；`python3 -m pytest tests` 34 passed。合并后需重跑 2021 smoke 验证 CV 指标实际产出。

### 最新补充（2026-06-10）：项目结构重构 Phase D1a SQL render table-role routing 已实现

- 分支 `codex/strategy1-research-routing-d1a` 已实现 `docs/prd/PRD_20260610_02_项目结构重构方案.md` 的 Phase D1a：把 table role / dataset role resolver 接入 Strategy1 SQL render。
- `src/quant_ashare/strategy1/sql_render.py` 现在可按 catalog step 的 `inputs` / `outputs` 生成 table role 替换表；默认 `dataset_role="ads"` 行为不变，显式 `dataset_role="research"` 必须同时传 `allow_future_research=True`，并只改写当前 step 相关 role，避免 `model_registry` / `acceptance_result` 等共享 ADS 源表被全局误替换。
- PR #142 review follow-up 已处理：分支已 rebase 到最新 `origin/main`，并按 SQL 实际 `ashare_ads` 引用补全非 retired step 的 catalog `inputs` / `outputs` 覆盖；新增 pytest 同时校验 catalog role 覆盖每个 ADS FQN，且所有 active step 的 research 渲染结果不得残留 `data-aquarium.ashare_ads.`。
- `scripts/strategy1_cloudrun/sql_runner.py` 的 path / step wrapper 已透传 `dataset_role` 与 `allow_future_research`，但现有调用默认仍渲染 ADS；本轮未改 `backtest_report.py` 默认参数、未部署 Cloud Run、未创建或写入 BigQuery `ashare_research`。
- 新增测试覆盖默认 ADS 渲染、显式 research 渲染、`ashare_meta.strategy1_experiment_run_status` per-role dataset override、字符串字面量表名替换，以及无 step 上下文的全局 research 替换歧义保护。
- `sql/strategy1/README.md` 已同步说明 D1a 是 render-only / explicit opt-in；actual research writes、default research-first 和 promotion job 仍需后续单独 PR。
- 验证：`python3 -m pytest tests` 42 passed；`python3 scripts/dataform/generate_sqlx_from_sql.py --check` 通过；`npx --yes @dataform/cli compile dataform` 通过；catalog ADS role 覆盖扫描 `missing_count=0`；88 条程序化 self-review checks 通过；`python3 -m compileall -q src/quant_ashare/strategy1 scripts/strategy1_cloudrun` 与 `git diff --check` 通过。

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
