> 文档维护：GPT-5 Codex（最近更新 2026-06-06）

# 策略 1 Cloud Run 训练回测运行手册

本文对应 `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md` 的第一版实现。

## 1. 当前边界

当前 Cloud Run runner 已提供：

1. `scripts/strategy1_cloudrun/train_predict.py`：读取既有 `ads_ml_training_panel_daily`，用 scikit-learn logistic regression 训练候选，做 valid 选型、score orientation、sklearn vs BQML parity，写 `ads_model_registry` 与 `ads_model_prediction_daily`。
2. `scripts/strategy1_cloudrun/backtest_report.py`：复用现有 `05-07` SQL 生成候选 / 组合 / 订单，默认使用 Cloud Run Python `ledger_exec_v1_lot100` fresh-start 回测，随后跑 `09`、报告、诊断和 QA。
3. `scripts/strategy1_cloudrun/orchestrate_experiments.py`：按 manifest 启动 Cloud Run Jobs，并写 `ashare_meta.strategy1_experiment_run_status`、使用 GCS generation-guarded lock。未设置 `--max-parallel-experiments` 或传 `0` 时，resolved 并发数等于本次可执行实验数。
4. `scripts/strategy1_cloudrun/prepare_matrix.py`、`train_candidate_task.py`、`select_register_predict.py`：task fan-out 训练路径。`prepare_matrix` 一次性读取 BigQuery 训练面板并生成 GCS frozen matrix；每个 Cloud Run task 只训练一个 candidate；reducer 统一选型、登记模型并写预测。
5. `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`：按 sklearn native PRD 执行 36 候选 search，valid-only 选 Top5，再为 Top5 生成独立 prediction / backtest / report / diagnosis；同一 orchestrator 也承载 Cloud Run Python baseline search 的通用 TopK 流程。
6. `scripts/strategy1_cloudrun/orchestrate_cloudrun_python_baseline_search.py`：Cloud Run Python baseline search 入口，当前用于 PRD04 LightGBM wave 2 / wave 3，以及 PRD-20260606-03 风险特征 wave 4。
7. `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`：校验 Cloud Run backend、sklearn artifact、prediction orientation、model-quality parity、resolved 并发契约，以及 task fan-out matrix/work-unit 审计字段。
8. `sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`：校验 Cloud Run orchestrator 状态表、锁元数据、execution id 和 task fan-out 状态行。
9. `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`：校验 sklearn native TopK 产物、valid-only 排名、uploaded 报告/诊断、native acceptance gate 和 test 复用记录。
10. `sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql`：校验 Cloud Run Python LightGBM baseline search 的 TopK、CV 证据、共享验收契约、test reuse 和 final_holdout watch。
11. `sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`：校验风险特征搜索的 feature schema/delta hash、市场状态覆盖、feature importance、wave 4 test reuse 和 `max_drawdown >= -18%` 风险目标。
12. `scripts/strategy1/analyze_tail_risk.py` 与 `sql/ml/strategy1/20_qa_tail_risk_outputs.sql`：在 TopK 回测完成后只读 ADS/DWD/DIM，输出最大回撤窗口、持仓贡献、跌停/不可卖暴露和选股画像，并校验 ADS pre/post hash 未变化。
13. `sql/dws/08_dws_market_state_daily.sql` 与 `sql/qa/11_market_state_checks.sql`：生成并校验 P2 市场状态 risk-off 证据表；`backtest_report.py` 在 `tail_risk_profile_id=market_risk_off_v0` 或 `individual_and_market_risk_guard_v0` 时由 Python ledger 读取该表并跳过 risk-off 次日买单。
14. `scripts/strategy1/diagnose_acceptance_gate_v2.py` 与 `sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`：按 `model_acceptance_contract_v2` 只读生成验收门 v2、10/20/30/40 组合可行性、eligible benchmark 和 score orientation audit artifact；不训练、不改 prediction、不写 ADS。
15. `sql/ml/strategy1/23_qa_lot_aware_ledger_outputs.sql`：校验 Cloud Run Python `ledger_exec_v1_lot100` 的整数手成交、odd-lot 清仓、below-lot 跳单、现金和 summary lot 参数。

当前限制：

1. 训练面板 SQL 由 runner config 的 `training_panel_sql` 指定；风险特征搜索使用 `sql/cloudrun/strategy1/01_build_training_panel.sql`，历史 `sql/ml/strategy1/01_build_training_panel.sql` 仅作旧路径参考。
2. `05-07` 仍使用 BigQuery SQL。
3. Python ledger P0 先支持 fresh-start；resume 路径 fail-fast。`ledger_exec_v1_lot100` 是 Python-only 执行语义，不再要求与 SQL FLOAT-shares runner 等价。
4. Cloud Run Jobs、Artifact Registry、IAM 和服务账号需按本文部署，不在代码中保存任何凭据。

## 2. 本地 dry-run

```bash
python -m scripts.strategy1_cloudrun.orchestrate_experiments \
  --project data-aquarium \
  --region asia-east2 \
  --manifest configs/strategy1/oq010_experiments_v0.json \
  --config configs/strategy1/cloudrun_runner_default.yml \
  --experiment-id oq010_a0_n5_w20 \
  --max-parallel-experiments 0 \
  --dry-run
```

期望：

1. 输出 `selected_experiment_count=1`。
2. 输出 `resolved_max_parallel_experiments=1`。
3. 输出将执行的 `gcloud run jobs execute strategy1-train-predict-job` 和 `strategy1-backtest-report-job` 命令。

task fan-out 训练路径 dry-run：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_experiments \
  --project data-aquarium \
  --region asia-east2 \
  --manifest configs/strategy1/oq010_experiments_v0.json \
  --config configs/strategy1/cloudrun_runner_default.yml \
  --experiment-id oq010_a0_n5_w20 \
  --train-mode task_fanout \
  --candidate-parallelism 0 \
  --dry-run
```

期望：

1. 输出 `cloudrun_prepare_matrix`、`cloudrun_train_candidate_fanout`、`cloudrun_select_register_predict`、`cloudrun_backtest_report` 四类 step。
2. `--candidate-parallelism 0` 表示候选 work unit 默认全并发；若 owner 显式传 `N > 0`，orchestrator 按 N 个 task 一批分批执行。
3. candidate task 命令只读取 `matrix_uri`，不直接查询 BigQuery 训练面板。

sklearn native search dry-run：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_sklearn_native_search \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/sklearn_native_pvfq_n30_bw_h5_v0.yml \
  --manifest configs/strategy1/sklearn_native_pvfq_n30_bw_h5_v0.yml \
  --search-id sklearn_native_pvfq_n30_bw_h5_20260605_01 \
  --candidate-parallelism 0 \
  --top-k-backtest 5 \
  --dry-run
```

期望：

1. 输出 `candidate_count=36`。
2. `cloudrun_train_candidate_fanout` 命令包含 `--tasks=36`。
3. TopK 模板使用 `s1_<search_id>__<candidate_id>` / `bt_s1_<search_id>__<candidate_id>`，不出现重复前缀。
4. 子 Job 命令必须带 `--config configs/strategy1/sklearn_native_pvfq_n30_bw_h5_v0.yml`，避免 Cloud Run 内退回默认 5 候选。

Cloud Run Python LightGBM baseline search dry-run：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml \
  --manifest configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml \
  --build-training-panel \
  --dry-run
```

期望：

1. 输出 `candidate_count=40`。
2. `cloudrun_train_candidate_fanout` 命令包含 `--tasks=40`。
3. `expected_model_family=lightgbm_gbdt`、`expected_model_search_wave_no=2`。
4. `next_wave_manifest=configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml`，且 `auto_next_wave_on_needs_more_evidence=true`。若 Top5 全部没有 accepted 且存在 `needs_more_evidence`，orchestrator 会进入下一波 `lightgbm_regression`。

Wave 3 regression dry-run：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml \
  --manifest configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml \
  --build-training-panel \
  --dry-run
```

期望输出 `candidate_count=12`、`--tasks=12`、`expected_model_family=lightgbm_regression`、`expected_model_search_wave_no=3`。

风险特征 wave 4 binary dry-run：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_v0.yml \
  --manifest configs/strategy1/cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_v0.yml \
  --build-training-panel \
  --dry-run
```

风险特征 wave 4 regression dry-run：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/cloudrun_python_riskfeat_lgbm_regression_pvfq_n30_bw_h5_v0.yml \
  --manifest configs/strategy1/cloudrun_python_riskfeat_lgbm_regression_pvfq_n30_bw_h5_v0.yml \
  --build-training-panel \
  --dry-run
```

期望：

1. 两个 manifest 分别输出 `candidate_count=20`、`--tasks=20`。
2. `build_training_panel` 使用 `sql/cloudrun/strategy1/01_build_training_panel.sql`。
3. `expected_model_search_wave_no=4`、`test_reuse_wave_no=4`。
4. Top5 完整回测后先跑 `19_qa_cloudrun_python_baseline_search_outputs.sql`，再跑 `21_qa_risk_feature_search_outputs.sql`。

多实验 dry-run：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_experiments \
  --project data-aquarium \
  --region asia-east2 \
  --stage-id stage_a \
  --dry-run
```

未显式限流时，`resolved_max_parallel_experiments` 必须等于本次可执行实验数量。

## 3. 本地单入口 dry-run

```bash
python -m scripts.strategy1_cloudrun.train_predict \
  --project data-aquarium \
  --region asia-east2 \
  --experiment-id oq010_a0_n5_w20 \
  --dry-run

python -m scripts.strategy1_cloudrun.backtest_report \
  --project data-aquarium \
  --region asia-east2 \
  --experiment-id oq010_a0_n5_w20 \
  --dry-run

python -m scripts.strategy1_cloudrun.prepare_matrix \
  --project data-aquarium \
  --region asia-east2 \
  --experiment-id oq010_a0_n5_w20 \
  --candidate-parallelism 0 \
  --dry-run
```

dry-run 只解析 manifest、参数、artifact 路径和执行计划，不写 ADS。

## 4. 构建镜像

```bash
gcloud builds submit \
  --project data-aquarium \
  --region asia-east2 \
  --config cloudbuild.strategy1-cloudrun.yaml
```

如需把当前 Git commit 写入镜像 tag，可显式传入：

```bash
gcloud builds submit \
  --project data-aquarium \
  --region asia-east2 \
  --config cloudbuild.strategy1-cloudrun.yaml \
  --substitutions=_TAG="$(git rev-parse --short HEAD)"
```

默认镜像：

```text
asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:latest
```

如 Artifact Registry repository 不存在，先创建：

```bash
gcloud artifacts repositories create quant-ashare \
  --project data-aquarium \
  --location asia-east2 \
  --repository-format docker
```

Cloud Run runtime service account 必须具备以下权限：

| 范围 | 权限 | 用途 |
|---|---|---|
| project 或源数据集 | `roles/bigquery.dataViewer` | 读取 DWD / DWS / ADS 输入表 |
| project | `roles/bigquery.jobUser` | 提交 BigQuery query / load job |
| `ashare_ads` dataset | `WRITER` / `roles/bigquery.dataEditor` | 删除并写入 prediction、candidate、portfolio、order、NAV、summary 等 ADS 输出 |
| `gs://ashare-artifacts` | `roles/storage.objectAdmin` | 上传模型、报告、诊断 artifact，并读写 orchestrator lock |
| Cloud Logging | `roles/logging.logWriter` | 写 Cloud Run job 日志 |

当前默认 Compute Engine service account 形如：

```text
<project-number>-compute@developer.gserviceaccount.com
```

## 5. 部署 Cloud Run Jobs

训练 / 预测 job：

```bash
gcloud run jobs deploy strategy1-train-predict-job \
  --project data-aquarium \
  --region asia-east2 \
  --image asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:latest \
  --command python \
  --args="-m,scripts.strategy1_cloudrun.train_predict" \
  --memory 16Gi \
  --cpu 4 \
  --task-timeout 3600 \
  --max-retries 0
```

回测 / 报告 job：

```bash
gcloud run jobs deploy strategy1-backtest-report-job \
  --project data-aquarium \
  --region asia-east2 \
  --image asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:latest \
  --command python \
  --args="-m,scripts.strategy1_cloudrun.backtest_report" \
  --memory 16Gi \
  --cpu 4 \
  --task-timeout 7200 \
  --max-retries 0
```

task fan-out 训练路径额外需要三个 job。`prepare_matrix` 和 reducer 读取 / 写入数据较多，沿用较高资源；candidate task 只训练单个模型，默认用轻量规格，并通过 Cloud Run Jobs task 数量实现并发。

```bash
gcloud run jobs deploy strategy1-prepare-matrix-job \
  --project data-aquarium \
  --region asia-east2 \
  --image asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:latest \
  --command python \
  --args="-m,scripts.strategy1_cloudrun.prepare_matrix" \
  --memory 32Gi \
  --cpu 8 \
  --task-timeout 3600 \
  --max-retries 0

gcloud run jobs deploy strategy1-train-candidate-fanout-job \
  --project data-aquarium \
  --region asia-east2 \
  --image asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:latest \
  --command python \
  --args="-m,scripts.strategy1_cloudrun.train_candidate_task" \
  --memory 8Gi \
  --cpu 2 \
  --parallelism 20 \
  --task-timeout 3600 \
  --max-retries 0
```

当前 OQ-010 Cloud Run Python baseline search 的 P0 口径固定为 40 个候选、20 并发、单 task `2 vCPU / 8Gi`。`strategy1-train-candidate-fanout-job` 的共享 Job spec 应保持 `parallelism=20`；40 个候选仍由一次 `--tasks=40` execution 启动，实际同时运行的 task 数由 Job spec 控制。若后续扩到 60 / 80 / 100 个候选，需要先更新对应 PRD、Cloud Run 区域配额和本部署命令。

若后续模型族发现单个 candidate task 的 `2 vCPU / 8Gi` 仍不足，先提高单 task 内存并按区域配额降低并发，而不是直接维持原并发：

```bash
gcloud run jobs update strategy1-train-candidate-fanout-job \
  --project data-aquarium \
  --region asia-east2 \
  --cpu 4 \
  --memory 16Gi \
  --parallelism 10
```

调整后，manifest 和执行参数中的 `candidate_parallelism` 必须同步改为新的并发值，并在 PR / 交接中记录 smoke 证据。

```bash
gcloud run jobs deploy strategy1-select-register-predict-job \
  --project data-aquarium \
  --region asia-east2 \
  --image asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:latest \
  --command python \
  --args="-m,scripts.strategy1_cloudrun.select_register_predict" \
  --memory 16Gi \
  --cpu 4 \
  --task-timeout 3600 \
  --max-retries 0
```

## 6. 单实验 smoke

前置：先用现有 SQL 生成训练面板，例如修改 `01_build_training_panel.sql` 参数后执行：

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/01_build_training_panel.sql
```

然后执行：

```bash
python -m scripts.strategy1_cloudrun.train_predict \
  --project data-aquarium \
  --region asia-east2 \
  --experiment-id oq010_a0_n5_w20 \
  --force-replace

python -m scripts.strategy1_cloudrun.backtest_report \
  --project data-aquarium \
  --region asia-east2 \
  --experiment-id oq010_a0_n5_w20 \
  --force-replace
```

SQL ledger 对照入口已退役，`backtest_report` 不再支持 `--use-bq-ledger`，也不再调用原 `08` SQL fallback。当前默认 Python ledger 路径为 `execution_backend='cloud_run_sklearn_ledger_v1_lot100'`、`ledger_executor='cloud_run_python'`；如需历史 FLOAT 股数审计，只能显式使用 Python `--use-float-ledger`。

`train_predict` 会把 sklearn selected model 与配置中的 BQML reference run 做模型质量对等检查；若 `model_quality_parity_status != 'passed'`，仍会写 selected registry、prediction、model artifact 和 parity 证据，但 `metrics_json.model_quality_status` 必须标记为 `model_quality_not_equivalent`，不得声明 sklearn backend 已等价替代 BQML baseline。
正式 baseline 验收继续要求 `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql` 默认通过；只做 smoke / 证据留存时，可以显式把 `p_require_model_quality_parity_passed` 设为 `FALSE`，此时 QA 只要求 parity 证据完整。

## 7. Cloud Run orchestrator

首次使用前先确保状态表存在：

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/meta/02_strategy1_experiment_run_status.sql
```

默认全并发：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_experiments \
  --project data-aquarium \
  --region asia-east2 \
  --manifest configs/strategy1/oq010_experiments_v0.json \
  --stage-id stage_a \
  --max-parallel-experiments 0
```

显式限流：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_experiments \
  --project data-aquarium \
  --region asia-east2 \
  --stage-id stage_a \
  --max-parallel-experiments 4
```

规则：

1. `0` 或未传：resolved 并发数 = 本次可执行实验数。
2. `N > 0`：同一时刻最多 N 条实验链。
3. 默认训练路径每个子 job 使用状态表 step：`cloudrun_train_predict` / `cloudrun_backtest_report`。
4. task fan-out 训练路径使用状态表 step：`cloudrun_prepare_matrix` / `cloudrun_train_candidate_fanout`（或带 batch 后缀）/ `cloudrun_select_register_predict` / `cloudrun_backtest_report`。
5. `--train-mode task_fanout` 只替换训练 / 选型 / 预测部分，后续 `05-07`、ledger、报告和诊断仍由 `backtest_report` 负责。
6. `--candidate-parallelism 0` 表示一个训练实验内的全部 candidate work unit 同批并发；显式传 `N > 0` 时按 N 个 task 分批，前一批 terminal succeeded 后再启动下一批。
7. task fan-out P0 要求 reducer 默认所有 candidate artifact 都成功才进入选型；只有显式使用 reducer 的 `--allow-partial-candidates` 才允许缺候选继续。
8. 每个子 job 先获取 GCS lock：`gs://ashare-artifacts/locks/strategy1/cloudrun/<lock_key>.lock`，锁创建、heartbeat、release 均使用 object generation 条件操作。
9. 获取锁后启动 Cloud Run execution，立即把 execution id 写入 GCS lock 和状态表，然后由 orchestrator 轮询 execution terminal 状态。
10. stale lock 回收前会先检查原 Cloud Run execution；execution 仍在运行时不得抢占。当前执行失锁时会 cancel 对应 execution，避免两个 writer 写同一 run/backtest。
11. 默认遇到实验失败时停止提交新的排队实验；所有已完成 / 失败 / 跳过结果都会在最终 JSON 中列出。
12. 如需继续执行剩余排队实验，加 `--continue-on-error`；最终仍会按失败数量返回非零退出码。
13. 如需从状态表恢复，使用 `--resume` 跳过已 `succeeded` 的 step；或用 `--resume-from-step cloudrun_backtest_report` 从指定 step 重跑。
14. 如果 GCP quota 不足，失败实验必须以 Cloud Run execution 和日志追踪，不允许 runner 静默降到内部默认 2 或 1。

## 7.1 sklearn native search

执行入口：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_sklearn_native_search \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/sklearn_native_pvfq_n30_bw_h5_v0.yml \
  --manifest configs/strategy1/sklearn_native_pvfq_n30_bw_h5_v0.yml \
  --search-id sklearn_native_pvfq_n30_bw_h5_20260605_01 \
  --candidate-parallelism 0 \
  --top-k-backtest 5 \
  --force-replace
```

执行语义：

1. `prepare_matrix` 只跑一次，source run 为 manifest 中的 search run。
2. `--candidate-parallelism 0` 表示 36 个 candidate task 同批并发；显式传 `N > 0` 才分批。
3. 候选训练完成后，orchestrator 只下载 `matrix_manifest.json`、`work_units.json` 和每个候选的 `candidate_metrics.json` / `task_status.json` / `model.joblib`，不下载完整 frozen matrix。
4. Top5 排名只使用 valid 指标；test 指标只在 Top5 完整回测后用于验收。
5. 每个 Top5 候选会生成独立 `candidate_run_id` / `candidate_backtest_id`，并复制一份同 run_id 的 `ads_ml_training_panel_daily` 别名，保证 `10` / `12` QA 和诊断可按独立 run_id join。
6. Top5 select/register/predict 与 backtest/report 仍使用 GCS lock 和状态表 step，避免同一 run/backtest 被两个 writer 同时写。
7. 单个 Top5 候选失败时，orchestrator 记录该候选失败并继续等待其他 Top5；最终 `18` QA 仍要求完整 Top5 产物，避免部分成功被误判为通过。
8. 搜索报告写入 `reports/strategy1_cloudrun/sklearn_native_search/search_id=<search_id>/`，uploaded 模式同步到 `gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/search_id=<search_id>/`。
9. 完成后运行 `18_qa_sklearn_native_search_outputs.sql`；该 QA 不要求 BQML parity passed，而是检查 native acceptance gate。

## 7.2 尾部风险诊断

Cloud Run `backtest_report.py` 默认在 `09`、报告、模型诊断、`10/12` QA 后执行尾部风险诊断：

```bash
python -m scripts.strategy1_cloudrun.backtest_report \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml \
  --manifest configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml \
  --experiment-id cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_search_v0 \
  --search-id cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01 \
  --run-id <candidate_run_id> \
  --prediction-run-id <candidate_prediction_run_id> \
  --backtest-id <candidate_backtest_id>
```

执行语义：

1. `analyze_tail_risk.py` 只读 `ashare_ads` / `ashare_dwd` / `ashare_dim`，不写 ADS，不改变回测结果。
2. 单候选 artifact 写到 `reports/strategy1/ml_pv_clf_v0/run_id=<run_id>/backtest_id=<backtest_id>/tail_risk/`；uploaded 模式同步到对应 GCS 报告路径下的 `tail_risk/`。
3. 主要产物包括 `max_drawdown_windows.*`、`drawdown_position_contribution.csv`、`limit_down_exposure_daily.csv`、`selection_profile_by_signal_date.csv`、`risky_selected_names.csv`、`ads_readonly_guard.json` 和中文 `tail_risk.md`。
4. `ads_readonly_guard.json` 记录 summary / NAV hash 和 ADS 相关行数的 pre/post 对比；pre/post 不一致时脚本 fail-fast，不能降级跳过。
5. `20_qa_tail_risk_outputs.sql` 复算最大回撤、持仓覆盖、跌停/不可卖权重和 summary/NAV hash；由 `backtest_report.py` 自动注入脚本产出的 expected hash。
6. `backtest_report.py` 对非 guard 类尾部风险诊断失败采用 fail-soft：原报告、模型诊断和 `10` / `12` 已完成时不回滚，写入 `tail_risk/tail_risk_failure.json` 并跳过 `20`；后续可单独复跑尾部风险诊断。
7. 若只想跳过本诊断，可传 `--skip-tail-risk`；这只影响尾部风险 artifact，不影响原报告和模型诊断。

## 7.3 市场状态 risk-off

P2 market risk-off 先构建市场状态 DWS，再跑 portfolio-only A/B，不重新训练：

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/08_dws_market_state_daily.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/11_market_state_checks.sql

python -m scripts.strategy1_cloudrun.orchestrate_experiments \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml \
  --manifest configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml \
  --force-replace
```

执行语义：

1. `dws_market_state_daily` 的 `trade_date` 是信号日；risk-off 在 `t` 日收盘后形成，只能影响 `t+1` 开盘执行。
2. `market_risk_off_v0` 只启用市场状态风控；`individual_and_market_risk_guard_v0` 同时启用 P1 个股风险和 P2 市场状态。
3. P2 v0 动作固定为 `skip_new_buys`：risk-off 次日允许卖出和 pending sell 继续处理，但所有 BUY 侧新增/加仓订单写 `BUY_SKIPPED_MARKET_RISK_OFF`，不成交、不候补。
4. `tail_risk/market_risk_off_dates.csv` 记录 risk-off 日期、触发原因和关键指标；`10` / `20` QA 会校验 risk-off 执行日没有真实 BUY 成交。

## 8. QA

Cloud Run smoke 后执行：

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/23_qa_lot_aware_ledger_outputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/20_qa_tail_risk_outputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/11_market_state_checks.sql
```

`16` 需要按实际 `p_run_id` / `p_prediction_run_id` / `p_backtest_id` 修改脚本顶部参数，或由后续调度器注入参数。
task fan-out 路径还需把 `16` 的 `p_require_task_fanout` 设为 `TRUE`。`16` 会同时断言 selected registry 已写入 matrix/work-unit 审计字段、所有 candidate task 成功、reducer 写入的 `candidate_task_bq_*` 审计计数为 0，并直接查询 `JOBS_BY_PROJECT` 兜底确认 candidate task 未读取 BigQuery 训练面板。
`17` 需要按实际 `p_experiment_id` / `p_run_id` / `p_backtest_id` 修改脚本顶部参数；task fan-out 路径需把 `p_require_train_step=FALSE`、`p_require_task_fanout=TRUE`。如果单独直接运行 train/backtest job、没有经过 orchestrator，则不运行 `17`。
`18` 只用于 sklearn native search。它需要按实际 `p_search_id` / `p_source_run_id` 修改脚本顶部参数，或由 `orchestrate_sklearn_native_search.py` 注入参数执行。
`20` 用于尾部风险诊断、P1 个股风险和 P2 market risk-off。它需要按实际 `p_run_id` / `p_prediction_run_id` / `p_backtest_id` / `p_predict_start` / `p_predict_end` 修改参数，或由 `backtest_report.py` 注入参数执行；`p_expected_summary_hash` / `p_expected_nav_hash` 应来自 `tail_risk/ads_readonly_guard.json`。
`11_market_state_checks.sql` 用于 `dws_market_state_daily` 表级 QA；P2 A/B 前必须先跑通。

## 9. 安全

1. 不提交 service account key、ADC 文件、OAuth token、OpenAI key 或 Tushare token。
2. Cloud Run 使用 service account 权限访问 BigQuery、GCS 和 Cloud Logging。
3. 本地 ADC 仅用于开发机 smoke，不写入仓库和日志。
