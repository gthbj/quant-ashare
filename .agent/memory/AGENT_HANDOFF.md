> 当前交接补充（2026-06-11，GPT-5 Codex）
> - PR #166 已合并并部署正式 Strategy1 runner 镜像 `sha256:e379fdccb49281ec628f389de261929d37e60906b51538132b350314ba8db9da`；五个 jobs 已更新，`strategy1-train-predict-job` 已提升到 `8 CPU / 32Gi`，六个 boot smoke（含 `refit_register_predict --help`）均成功。
> - `v20260610_02` final refit 六年全部完成：2021/2022/2023 首轮成功，hotfix 后 2024/2025/2026 成功（executions `strategy1-train-predict-job-5s49j` / `mx272` / `d6g52`）；六年 `qa_refit_register_predict_outputs` 全部 succeeded。
> - 当前 PRD_03 分支 `codex/strategy1-synthetic-continuous` 已实现 synthetic continuous merge entrypoint 与 `qa_continuous_backtest_outputs`，focused tests / full pytest / Dataform / dry-run 均通过；待 PR 合并后执行 official synthetic merge + single continuous ledger。
> - 仍禁止把年度 fresh NAV 拼成正式结果；official `2021-2026` 结果必须等 synthetic run、continuous backtest、`qa_continuous_backtest_outputs` 与 lot-aware QA 全部通过。

Model: GPT-5 Codex

## 2026-06-11 GPT-5 Codex - PRD_03 synthetic continuous implementation

### 已完成工作

- 新增 package entrypoint `quant_ashare.strategy1.synthetic_continuous`，按 manifest 合并逐年 refit prediction slice，生成 synthetic selected registry 行和统一 `model_id` / `run_id` 的 prediction stream；默认只允许写 `ashare_research`，ADS 发布仍走 promotion。
- 新增 `sql/strategy1/qa/qa_continuous_backtest_outputs.sql` 并登记 catalog，覆盖 synthetic manifest hash、year slice 溯源、source/target prediction 行数、valid 段排除、交易日历覆盖、continuous summary / NAV / position / trade / ledger state 不变式。
- 更新 `docs/策略1CloudRun训练回测运行手册.md`，补 official synthetic merge、continuous backtest skip flags 和外接 QA 执行口径。
- 扩展 package entrypoint / catalog / SQL render / package boundary 测试，锁住新入口和 QA step。
- PR #166 合并后已从 `main@7b2bd67` 构建部署 hotfix 镜像 `sha256:e379fdccb49281ec628f389de261929d37e60906b51538132b350314ba8db9da`，五个 jobs 读回确认新 digest；`strategy1-train-predict-job` 资源已更新为 `8 CPU / 32Gi`。
- 使用 hotfix plan 重跑 2024/2025/2026 refit 成功：`strategy1-train-predict-job-5s49j`（约 7m20s）、`strategy1-train-predict-job-mx272`（约 9m50s）、`strategy1-train-predict-job-d6g52`（约 10m10s）。六年 refit registry 均为 1 行 selected，prediction 覆盖各年窗口。
- 六年 `qa_refit_register_predict_outputs` 均通过，job ids：`c6bcbf46-ec47-4917-a0a4-e67fbc467997`、`4f75fb48-52ce-4f1b-a270-e555b1358e3e`、`e90a2a1e-0802-4013-9356-e0544304e21d`、`4216cc23-3b09-4001-9291-d93380c44d40`、`04e923a0-e59c-4bfa-a333-2a6a806213e7`、`4e9d241f-7cf3-4def-bee0-0077f6b44d41`。

### 重要上下文

- `PRD_20260611_02` 的 final refit 执行与 QA 已完成；2021-2026 official 评价的剩余硬门是 PRD_03 synthetic continuous merge + single continuous ledger。
- `qa_continuous_backtest_outputs` 是 synthetic run 专用 QA；`10` / `12` / `20` 默认 QA/诊断不适用于无 training panel / 无真实 model artifact 的 synthetic run。continuous backtest 必须用 `--skip-diagnosis --skip-tail-risk --skip-qa`，再外接 `qa_continuous_backtest_outputs` 与 `qa_lot_aware_ledger_outputs`。
- 主工作树仍有 unrelated `scripts/strategy1_cloudrun/bq_io.py` 本地脏改，不属于本 PRD_03 分支，后续构建镜像必须继续使用干净 worktree。

### 改动文件

- `src/quant_ashare/strategy1/synthetic_continuous.py`
- `sql/strategy1/qa/qa_continuous_backtest_outputs.sql`
- `configs/strategy1/active_step_catalog.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `tests/strategy1/test_synthetic_continuous.py`
- `tests/strategy1/test_cloudrun_package_entrypoints.py`
- `tests/strategy1/test_package_boundaries.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests`：115 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `npx --yes @dataform/cli compile dataform`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。
- `python3 -m quant_ashare.strategy1.sql_runner --step=qa_continuous_backtest_outputs --output-dataset-role=research --dry-run`：BigQuery dry-run 通过。

### 阻塞项

- 无代码阻塞；official continuous ledger 尚未执行，需先合并 PRD_03 code PR。

### 下一步建议

- 提交 PRD_03 代码 PR，review / merge。
- 从合并后的 main 生成 official manifest，执行 `quant_ashare.strategy1.synthetic_continuous --require-source-refit` 写 synthetic run。
- 用 `strategy1-backtest-report-job` 跑 official continuous backtest（skip diagnosis/tail-risk/default QA），再执行 `qa_continuous_backtest_outputs` 与 `qa_lot_aware_ledger_outputs`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - PRD_02 deployment and refit hotfix

### 已完成工作

- 合并 PR #165 到 `main`，merge commit `ebb6dbf`。
- 从 `main@ebb6dbf` 构建固定 tag 镜像 `strategy1-cloudrun-runner:final-refit-main-ebb6dbf-20260611-01`，Cloud Build `8dcd4d62-a61d-459a-aeb8-86fc69a76313` succeeded，digest `sha256:fc94a02d388e0a988dac56366ea0dcba80e65c15dea10efc93ef38e11778b757`。
- 五个正式 Strategy1 jobs 已更新到该 digest；读回确认 package args、SA、maxRetries、资源和 fanout `taskCount=40 / parallelism=20` 保持预期。
- Boot smoke：`strategy1-train-predict-job-nmnkn`、`strategy1-prepare-matrix-job-bhpwm`、`strategy1-train-candidate-fanout-job-rrz6h`、`strategy1-select-register-predict-job-vfkzx`、`strategy1-backtest-report-job-ncn69`、`strategy1-train-predict-job-2kk7c`（`refit_register_predict --help` override）全部 Completed=True，Cloud Logging 均匹配到 `usage:`。
- 生成 `/tmp/strategy1_annual_refit_plan_v20260610_02.json` 并做 BigQuery preflight；六年 source selected registry / panel / target empty checks 通过。
- 启动 2021-2026 refit：2021、2022、2023 成功；2024 因 panel min date 晚于 resolved start 失败；2025、2026 因 train-predict job 16Gi memory limit 失败。
- 新建 hotfix worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-final-refit-hotfix`，分支 `codex/strategy1-final-refit-hotfix`，修复 2024+ 暴露的问题：2019 final-refit start override 为 `2019-04-03`，scheduler/runbook refit resource token 改为 `8 CPU / 32Gi`。

### 重要上下文

- 2021-2023 refit outputs 已实际写入 research；不要用 `--force-replace` 重跑它们，除非 owner 明确要求。
- 2024 失败发生在 coverage guard 之前，没有写出 refit registry/prediction；2025/2026 因内存限制失败，也需在重跑前复核目标 refit rows。
- Hotfix 合并后必须重建镜像，并把至少 `strategy1-train-predict-job` 更新到 `8 CPU / 32Gi` 后再重跑 2024-2026。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`
- `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`
- `docs/策略1CloudRun训练回测运行手册.md`
- `tests/strategy1/test_annual_pipeline_scheduler.py`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`

### 测试 / 验证

- Hotfix focused pytest：`tests/strategy1_cloudrun/test_dataset_role_routing.py::test_annual_year_plan_continuous_contract_uses_refit_run_id` 与 `tests/strategy1/test_annual_pipeline_scheduler.py::test_scheduler_plan_select_depends_on_all_candidates_and_cross_year_is_independent` 通过。
- Hotfix 2024 annual dry-run 确认 `final_refit.train_start='2019-04-03'`。
- 完整验证待 hotfix 提交前执行。

### 阻塞项

- 无代码阻塞；需完成 hotfix PR / merge / redeploy 后才能重跑 2024-2026。

### 下一步建议

- 完成 hotfix 全量验证、提交 PR、合并并部署新镜像。
- 更新 `strategy1-train-predict-job` 至 `8 CPU / 32Gi` 后重跑 2024、2025、2026 refit，并执行 `qa_refit_register_predict_outputs`。
- PRD_03 synthetic continuous merge / official continuous ledger 仍待实现，不能拼接年度 NAV。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - PRD_02 annual rolling final refit implementation

### 已完成工作

- 新增 package entrypoint `src/quant_ashare/strategy1/refit_register_predict.py`，实现年度滚动 selected candidate final refit：读 selection registry、读 `source_panel_run_id` 面板、重新 fit preprocessor、训练单模型、写 refit registry / prediction / artifact。
- 扩展 `train_predict.write_registry` 的 `model_params_json` lineage 白名单，写出 `source_panel_run_id`、`refit`、`refit_train_start/end`、`preprocess_fit_start/end`。
- 新增 `sql/strategy1/qa/qa_refit_register_predict_outputs.sql` 并登记 `configs/strategy1/active_step_catalog.yml`，覆盖 refit 硬门 QA。
- 更新 `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`：每年 plan 插入 `cloudrun_refit_register_predict`，root / yearly continuous metadata 指向 refit prediction run，年度 diagnostic backtest 指向 `__refit01` backtest。
- 更新 `quant_ashare.strategy1.annual_pipeline_scheduler`：新增 `refit` stage，continuous 依赖改为 refit runs。
- 更新 runbook 与测试，覆盖 package entrypoint、annual command plan、scheduler DAG 和 catalog/package boundary。

### 重要上下文

- 本轮只完成代码侧实现，不部署镜像、不执行 Cloud Run、不写 BigQuery research/ADS 产物；六年 refit 重跑仍待合并后用新镜像执行。
- refit 当前复用现有 `strategy1-train-predict-job`，资源 token 记录为 `4 CPU / 16Gi`；这是比 PRD 建议 `2 CPU / 8Gi` 更保守的现有 job envelope，不新增 job spec。
- 年度 diagnostic backtest 仍只作 diagnostic，正式结果必须等 PRD_03 synthetic continuous merge + single continuous ledger。

### 改动文件

- `src/quant_ashare/strategy1/refit_register_predict.py`
- `src/quant_ashare/strategy1/train_predict.py`
- `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`
- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`
- `sql/strategy1/qa/qa_refit_register_predict_outputs.sql`
- `configs/strategy1/active_step_catalog.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `tests/strategy1/test_annual_pipeline_scheduler.py`
- `tests/strategy1/test_cloudrun_package_entrypoints.py`
- `tests/strategy1/test_package_boundaries.py`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests`：108 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_refit_register_predict_outputs.sql`：通过。
- annual orchestrator / scheduler dry-run 复核：plan 顺序包含 `cloudrun_refit_register_predict`，scheduler `continuous_ledger` 依赖 `refit:*`。

### 阻塞项

- 无代码侧阻塞；上线前仍需 PR 合并后重建 Strategy1 runner 镜像。

### 下一步建议

- 合并 PRD_02 代码 PR 后，重建并部署五个 Strategy1 runner jobs 镜像，至少做 refit entrypoint boot smoke。
- 继续实现 PRD_03 synthetic continuous merge / QA；PRD_02 refit 六年重跑完成后再跑正式 continuous ledger。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - PRD_04 research summary identity implementation and live backfill

### 已完成工作

- 合并 PR #162 到 `main`，并确认 `PRD_20260611_02/03/04` 三个文件已在 `origin/main@ce795e5`。
- 清理已合并的旧 PRD worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-refit-prds`，删除本地和远端 `claude/prd-refit-continuous-summary` 分支。
- 新建工作树 `/Users/fisher/Desktop/git/worktrees/quant-ashare-prd04-summary-fix`，分支 `codex/prd04-research-summary-fix`。
- PR #163 已自审并合并到 `main`，merge commit `f0ba555`。
- 新增 ADS additive migration `sql/ads/04_alter_strategy1_backtest_summary_identity_columns.sql`，为 `ads_backtest_performance_summary` 补 `run_id STRING` 与 `created_date DATE`。
- 修复 `sql/strategy1/reporting/build_metrics_and_report_inputs.sql`：summary INSERT 列清单与 SELECT 显式写入 `run_id=p_run_id`、`created_date=CURRENT_DATE()`。
- 修复 `sql/strategy1/qa/qa_runner_outputs.sql`：新增 summary row 的 `run_id=p_run_id` 与 `created_date IS NOT NULL` 断言。
- 修复 `sql/strategy1/qa/qa_cloudrun_schema_readiness.sql`：ADS summary required columns 增加 `run_id` / `created_date`，失败信息指向新 migration。
- 新增 `tests/strategy1/test_backtest_summary_identity_contract.py`，防止上述契约漂移。
- 已执行 live ADS migration，并复跑 `qa_cloudrun_schema_readiness` 通过。
- 已回填 6 条 annual rolling research summary 行：`run_id=metrics_json.prediction_run_id`，`created_date=DATE(created_at)`，affected rows=6。

### 重要上下文

- catalog 的 `backtest_summary.partition_columns=[created_date]` 继续代表 research 表语义；本轮不把 ADS summary 改成分区表，避免扩大 migration 面。
- Phase 1 ADS 写入例外只限 additive migration；普通 runner / 后续重跑仍必须默认 research-first。
- PRD_04 已不再阻塞后续 refit / continuous，但后续新 summary 行依赖已合并的 `09` 修复和新镜像部署；PRD_02/03 实现合并后仍需重建 Strategy1 runner 镜像。

### 改动文件

- `sql/ads/04_alter_strategy1_backtest_summary_identity_columns.sql`
- `sql/strategy1/reporting/build_metrics_and_report_inputs.sql`
- `sql/strategy1/qa/qa_runner_outputs.sql`
- `sql/strategy1/qa/qa_cloudrun_schema_readiness.sql`
- `tests/strategy1/test_backtest_summary_identity_contract.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests`：105 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ads/04_alter_strategy1_backtest_summary_identity_columns.sql`：通过。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。
- Live migration：两条 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 均完成。
- Live readiness：`qa_cloudrun_schema_readiness` 4 条 assertion 全部 successful。
- Live backfill：annual target rows=6，UPDATE affected rows=6；复核 `null_run_id=0`、`null_created_date=0`、`run_id_mismatch=0`、`created_date_mismatch=0`，`created_date=2026-06-10` 过滤查到 6 行；time-travel hash 对比确认排除 `run_id`/`created_date` 后非目标字段无变化。

### 阻塞项

- 无。

### 下一步建议

- 进入 PRD_02 final refit 与 PRD_03 synthetic continuous 实现；两者可按任务要求分独立 PR 推进。
- 任何重跑前仍需确认五个 Strategy1 jobs 镜像包含最新 main 代码；PRD_02/03 合并后必须重建并部署 runner 镜像。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

> 当前交接补充（2026-06-11，Claude Fable 5）
> - 分支 `claude/prd-refit-continuous-summary` 新增三个 PRD，收口 2021-2026 首轮年度滚动实跑暴露的三类问题：`PRD_20260611_02`（final refit 方法论修正）、`PRD_20260611_03`（synthetic continuous prediction + 正式 continuous ledger）、`PRD_20260611_04`（research summary `created_date`/`run_id` 落库修复，简短）。
> - 关键依赖关系已写入 PRD：04 的修复必须先于任何重跑；02 与 03 的代码实现可并行（03 的 merge 输入参数化为 manifest，彩排用 pre-refit 预测），只有 03 的正式执行依赖 02 的六年 refit 重跑。
> - 04 的根因已实证：`09` SQL summary INSERT 列清单不含 `run_id`/`created_date`（ADS 表本无这两列，research 表是 D0 新增），research 渲染只重写表名不重写列清单 → 未列出且无 DEFAULT 的列写 NULL。
> - 本轮 docs/记忆-only：不改代码、不执行 BigQuery / Cloud Run。当前 6 年年度结果（含 2025 +53.32%）仍只是 diagnostic，final refit 修正前不得解读指标。
> - PR #162 review 三条 follow-up 已全部采纳修正：①（实证确认 `prepare_matrix` 在 selection train 上 fit preprocessor、matrix 冻结 transformed arrays）PRD_02 复用层级从 matrix 改为 panel，refit 必须重新 fit preprocessor，新增 preprocessing 契约与 QA；② PRD_03 新增 synthetic registry 契约（单 selected synthetic model、prediction model_id 统一改写、逐年溯源入 manifest + `year_model_map`）与专用 `qa_continuous_backtest_outputs` QA 套件，保住下游"每 run 单 selected"不变式；③ PRD_04 扩展 `qa_cloudrun_schema_readiness` 覆盖 ADS summary 新增两列，preflight 拦截漏跑 migration。

Model: Claude Fable 5

## 2026-06-11 Claude Fable 5 - 年度滚动 refit / continuous / summary 三 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260611_02_策略1年度滚动FinalRefit.md`：refit 窗口口径（resolved plan `final_refit` 块为权威）、复用既有 BigQuery panel（经 `source_panel_run_id` 读 selection run panel，重新 fit preprocessor，不消费冻结 matrix transformed arrays）、`refit_register_predict` 步骤、独立 refit run_id 的 registry 溯源契约、QA 硬门（训练窗口逐年断言）、六年从 select 之后重跑的范围声明。
- 新增 `docs/prd/PRD_20260611_03_策略1SyntheticContinuous正式回测.md`：manifest 参数化 merge（彩排/正式同代码）、逐年 test 窗口切片排除 valid 段、重叠/缺口/行数/溯源 QA、official continuous ledger 口径、rehearsal 与 official 的强制区分。
- 新增 `docs/prd/PRD_20260611_04_ResearchSummary落库修复.md`（简短）：根因实证、ADS additive 补列 + `09` 列清单修复 + 6 行回填（需 owner 批准）+ `qa_runner_outputs` NOT NULL 断言。
- 同步 `IMPLEMENTATION_STATUS.md`、`AGENT_HANDOFF.md`、`TODO.md`。

### 重要上下文

- 实跑暴露的其余问题不另开 PRD：`gcloud --wait` 误报与控制面滞后是 `PRD_20260611_01` §8.1 既定 Phase 2 要求（本次为实证）；慢候选长尾归 scheduler PRD P1；registry 11 行需筛 `status='selected'` 拟作为约定写入 KNOWN_CONSTRAINTS（随实现 PR 落，本轮不动约束文件）。
- 执行顺序：04 修复 PR → 02/03 并行实现（03 彩排可先行）→ 02 六年 refit 重跑 → 03 正式 merge + continuous ledger。

### 改动文件

- `docs/prd/PRD_20260611_02_策略1年度滚动FinalRefit.md`
- `docs/prd/PRD_20260611_03_策略1SyntheticContinuous正式回测.md`
- `docs/prd/PRD_20260611_04_ResearchSummary落库修复.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 文档与记忆更新；未运行 pytest / BigQuery / Cloud Run。`git diff --check` 通过。

### 阻塞项

- 无。三个 PRD 均待 owner review。

### 下一步建议

- owner review 三个 PRD 后，先实现 `PRD_20260611_04` 的修复 PR（成本最低且阻塞重跑）。
- `PRD_20260611_03` 的 merge/QA 实现与彩排可与 `PRD_20260611_02` 并行启动。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

> 当前交接补充（2026-06-11，GPT-5 Codex）
> - PRD 分支实现收口中：实现工作树 `/Users/fisher/Desktop/git/quant-ashare-annual-pipeline-impl` 从 PRD 分支派生，最终按 owner 要求 fast-forward 回 `codex/prd-annual-rolling-pipeline-scheduler`。
> - 新增 package entrypoint `quant_ashare.strategy1.annual_pipeline_scheduler`，实现年度滚动 pipeline scheduler Phase 1 dry-run；只输出 DAG / lock / state / resource plan，不执行 Cloud Run / BigQuery / GCS 写入。
> - PR #161 review follow-up 已补：dry-run 输出 `simulation_model=synchronous_waves`，峰值标记为 reference 而非 live capacity ceiling；fanout 计数声明为 candidate-year proxy；`--no-tail-fill-single-task` 的 deferred batch 不再误记 succeeded。
> - 新增测试覆盖年度 DAG、scheduler lock ownership、candidate 饱和阻止 prepare、GCS state generation mismatch、deferred batch 和 CLI dry-run JSON；catalog caller / package boundary / runbook 已同步。
> - 后续建议：PR #161 合并后进入 Phase 2 candidate-only live smoke，先用 2 年 * 2-3 candidate unit 验证真实状态恢复、artifact skip 和 Cloud Run execution 粒度 fanout 统计。

Model: GPT-5 Codex

## 2026-06-11 GPT-5 Codex - Annual pipeline scheduler Phase 1 dry-run

### 已完成工作

- 新增 `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`，实现 PRD Phase 1 dry-run package entrypoint。
- Scheduler 复用年度 rolling experiment/window 生成逻辑，输出 2021-2026 跨年度 DAG；本年 `select` 强依赖本年 11/11 candidate，下一年 `panel` / `matrix` 不依赖上一年 `select`。
- Dry-run 输出 scheduler-level GCS generation-guarded lease lock、GCS state generation-conditioned write 模型、stage token 表和资源模拟。
- 资源模型明确 candidate `2 CPU / 8Gi`、prepare `8 CPU / 32Gi`、select/backtest `4 CPU / 16Gi` 共用 `40 CPU / 160Gi` 全局资源池；单测覆盖 20 个 candidate running 时 prepare 不可 admission。
- PR #161 review follow-up：`simulation_model=synchronous_waves` 与 `peak_resource_usage_semantics=synchronous_wave_reference_not_live_capacity_ceiling` 已进入输出；fanout execution accounting 明确 Phase 1 为 candidate-year proxy；deferred candidate batch 不再标记 succeeded。
- 更新 `configs/strategy1/active_step_catalog.yml` caller、`docs/策略1CloudRun训练回测运行手册.md` 和相关测试。

### 重要上下文

- 本轮仍是 Phase 1：不启动 Cloud Run，不读写 BigQuery / GCS，不修改 job spec / IAM；dry-run 资源峰值只用于 admission 自检，不代表 live overlap 的容量上限。
- Owner 已要求不要单独开实现 PR；完成后把实现合回 `codex/prd-annual-rolling-pipeline-scheduler` / PR #161。
- Phase 2 live scheduler 必须按真实 Cloud Run execution 粒度统计 active fanout，而不能沿用 Phase 1 的 candidate-year proxy。

### 改动文件

- `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`
- `tests/strategy1/test_annual_pipeline_scheduler.py`
- `tests/strategy1/test_package_boundaries.py`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `configs/strategy1/active_step_catalog.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1 tests/strategy1_cloudrun`：98 passed。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.annual_pipeline_scheduler --start-year 2021 --end-year 2026 --run-version v20260611_followup --dry-run`：输出 `simulation_model=synchronous_waves`、`fanout_model=candidate_year_proxy`、`deferred_task_count=0`，峰值 `38 CPU / 152Gi / 11 candidate_slots`；该峰值是 synchronous wave reference，不是 live capacity ceiling。

### 阻塞项

- 无。

### 下一步建议

- 推回 PR #161 后 review。
- 合并后再做 Phase 2 candidate-only live smoke，并把 active fanout 计数从 candidate-year proxy 改为 Cloud Run execution 粒度。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - Annual rolling pipeline scheduler PRD

Model: GPT-5 Codex

### 已完成工作

- 在新 worktree `/Users/fisher/Desktop/git/quant-ashare-annual-pipeline-prd`、分支 `codex/prd-annual-rolling-pipeline-scheduler` 中新增年度滚动并发调度 PRD。
- PRD 定义从按年份串行执行升级为跨年份流水线调度：`build_training_panel`、`prepare_matrix` 和 candidate fanout 可跨年度并发；本年 `select_register_predict` 仍必须等本年全部候选成功。
- PRD 固化默认资源上限：全局 candidate task 并发 `20`，candidate task `2 CPU / 8Gi`，并把 prepare、select、backtest/report 纳入资源 token 模型。
- PR #161 review follow-up 已补齐两个 Medium 设计缺口：scheduler 必须持有 generation-guarded GCS lease lock 才能提交 execution，且 GCS state JSON 写入必须使用 generation precondition；prepare `8 CPU / 32Gi`、select `4 CPU / 16Gi`、backtest `4 CPU / 16Gi` 与 candidate 共享 `40 CPU / 160Gi` 全局 token 池。
- PRD 定义 scheduler 必须可 dry-run、可恢复、可按 `(year, unit_index)` 跟踪状态，并对 `gcloud --wait` / Cloud Run 控制面超时做 execution / task / GCS artifact 二次确认。
- 同步更新 `TODO.md` 和 `.agent/memory/IMPLEMENTATION_STATUS.md`。

### 重要上下文

- 2026-06-10 年度滚动实跑观察显示，每年候选训练中 `unit_index=6` 明显拖尾；该候选是 `risk_lgbm_prd_attack_lr005_n600_l63_lr005_n600_leaf800_ff07_bf09_l1_1_l2_1`，`n_estimators=600`、`num_threads=1`。
- 不能在本年 unit6 未完成时提前跑本年 select，否则会把 unit6 排除在年度选参之外，破坏实验口径。
- 可以在上一年慢候选仍 running 时启动下一年 training panel、prepare matrix 和候选训练，只要全局资源预算允许。
- Cloud Run `parallelism` 只限制单 execution；年度 pipeline scheduler 必须自己维护全局资源池和 scheduler 实例互斥，不能靠 job spec 防止跨 execution 超配额或重复提交。
- 正式年度滚动结果仍必须来自单一 continuous ledger 或通过 resume-continuous QA 的 segment ledger；年度 fresh backtest 只作 diagnostic。

### 改动文件

- `docs/prd/PRD_20260611_01_策略1年度滚动并发调度.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 文档只读校验：对照现有年度滚动 PRD、年度执行工程化 PRD、annual rolling orchestrator、`pipeline_control.build_task_fanout_steps`、`annual_rolling_lgbm_regression_v0.yml`。
- 未运行 BigQuery、Cloud Run、Dataform 或 pytest；本轮不改代码。

### 阻塞项

- 无。

### 下一步建议

- 若 owner 确认 PRD，下一步实现 Phase 1：scheduler dry-run，输出跨年度 DAG、资源峰值和预计提交顺序。
- Phase 1 完成后再做 2 年 * 2-3 candidate unit 的 candidate-only live smoke，验证部分 batch、恢复和 artifact skip。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - Strategy1 main image deploy after PR #159

### 已完成工作

- 从当前 `main@f30c1716a55995d169955e1a7c4663d39b82a382` 构建正式 Strategy1 runner 镜像。
- 使用一次性 Cloud Build config，只推固定 tag `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:annual-plan-main-f30c171-20260610-01`，未更新 `latest`。
- Cloud Build `4dfba35e-cbaf-4727-9596-137010c9d6ea` succeeded，镜像 digest 为 `sha256:b856f46f56ad5b9a9cd9ac8773e67090f702a06ff8931ca51e1d2e3bb24299d7`。
- 将五个正式 Strategy1 Cloud Run jobs 更新到该 immutable digest：
  - `strategy1-train-predict-job`
  - `strategy1-prepare-matrix-job`
  - `strategy1-train-candidate-fanout-job`
  - `strategy1-select-register-predict-job`
  - `strategy1-backtest-report-job`
- 读回确认五个 jobs 的 command/args 仍为 `python -m quant_ashare.strategy1.*` package entrypoint，SA 仍为 `241358486859-compute@developer.gserviceaccount.com`，`maxRetries=0`，CPU/memory/timeout 保持不变；fanout 仍为 `taskCount=40`、`parallelism=20`。
- 跑通五个正式 jobs 的只读 `--help` boot smoke，并在 Cloud Logging 确认每个 execution 输出 `usage:`。
- 按 owner 要求清理项目记忆：将旧 active `AGENT_HANDOFF.md` 归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`，当前 handoff 只保留本次部署交接。
- PR #160 review follow-up：把 Strategy1 runner image digest 从长期约束中移除，改为引用 `IMPLEMENTATION_STATUS.md` 最新部署记录。

### 重要上下文

- 本轮只更新五个普通 Strategy1 runner jobs 的 image；没有更新 `strategy1-promote-research-to-ads-job`。
- 本轮没有执行 BigQuery 写入，也没有启动年度滚动真实运行。
- 当前线上五个 Strategy1 jobs 已包含 PR #159 的 annual rolling training panel plan 和 `quant_ashare.strategy1.sql_runner` package CLI。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

### 测试 / 验证

- Cloud Build `4dfba35e-cbaf-4727-9596-137010c9d6ea`：SUCCESS。
- `gcloud run jobs describe` 读回五个 jobs：image 均为 `sha256:b856f46f56ad5b9a9cd9ac8773e67090f702a06ff8931ca51e1d2e3bb24299d7`，args / resources / SA / retries / fanout 并发均保持预期。
- `strategy1-train-predict-job-gwpn7`：Completed=True，Cloud Logging 匹配 `usage: train_predict.py`。
- `strategy1-prepare-matrix-job-rjgzf`：Completed=True，Cloud Logging 匹配 `usage: prepare_matrix.py`。
- `strategy1-train-candidate-fanout-job-njl4q`：Completed=True，本次 smoke 用 `--tasks=1`，Cloud Logging 匹配 `usage: train_candidate_task.py`。
- `strategy1-select-register-predict-job-njmxd`：Completed=True，Cloud Logging 匹配 `usage: select_register_predict.py`。
- `strategy1-backtest-report-job-jj7ng`：Completed=True，Cloud Logging 匹配 `usage: backtest_report.py`。
- `git diff --check`：通过。

### 阻塞项

- 无。

### 下一步建议

- 执行完整 `2021-2026` 年度滚动选参实验。
- 正式结果必须来自单一 continuous ledger，或经过 resume-continuous QA 的 segment ledger；不要拼接年度 fresh-run NAV。
- 若年度滚动结果接近可接受，再按 promotion runbook 先 review-only 后 owner-approved `--execute`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`
