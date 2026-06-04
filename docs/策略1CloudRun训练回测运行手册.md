> 文档维护：GPT-5（最近更新 2026-06-04）

# 策略 1 Cloud Run 训练回测运行手册

本文对应 `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md` 的第一版实现。

## 1. 当前边界

当前 Cloud Run runner 已提供：

1. `scripts/strategy1_cloudrun/train_predict.py`：读取既有 `ads_ml_training_panel_daily`，用 scikit-learn logistic regression 训练候选，做 valid 选型、score orientation、sklearn vs BQML parity，写 `ads_model_registry` 与 `ads_model_prediction_daily`。
2. `scripts/strategy1_cloudrun/backtest_report.py`：复用现有 `05-07` SQL 生成候选 / 组合 / 订单，默认使用 Cloud Run Python `ledger_exec_v1` fresh-start 回测，随后跑 `09`、报告、诊断和 QA。
3. `scripts/strategy1_cloudrun/orchestrate_experiments.py`：按 manifest 启动 Cloud Run Jobs，并写 `ashare_meta.strategy1_experiment_run_status`、使用 GCS generation-guarded lock。未设置 `--max-parallel-experiments` 或传 `0` 时，resolved 并发数等于本次可执行实验数。
4. `scripts/strategy1_cloudrun/prepare_matrix.py`、`train_candidate_task.py`、`select_register_predict.py`：task fan-out 训练路径。`prepare_matrix` 一次性读取 BigQuery 训练面板并生成 GCS frozen matrix；每个 Cloud Run task 只训练一个 candidate；reducer 统一选型、登记模型并写预测。
5. `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`：校验 Cloud Run backend、sklearn artifact、prediction orientation、model-quality parity、resolved 并发契约，以及 task fan-out matrix/work-unit 审计字段。
6. `sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`：校验 Cloud Run orchestrator 状态表、锁元数据、execution id 和 task fan-out 状态行。

当前限制：

1. 训练面板仍由现有 `01_build_training_panel.sql` 生成。
2. `05-07` 仍使用 BigQuery SQL。
3. Python ledger P0 先支持 fresh-start；resume 路径 fail-fast，等 fresh-start 与 BigQuery ledger 等价验证通过后再扩展。
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
  --memory 16Gi \
  --cpu 4 \
  --task-timeout 3600 \
  --max-retries 0

gcloud run jobs deploy strategy1-train-candidate-fanout-job \
  --project data-aquarium \
  --region asia-east2 \
  --image asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:latest \
  --command python \
  --args="-m,scripts.strategy1_cloudrun.train_candidate_task" \
  --memory 4Gi \
  --cpu 1 \
  --parallelism 100 \
  --task-timeout 3600 \
  --max-retries 0

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

若只做 ledger 对照，可在 `backtest_report` 加 `--use-bq-ledger` 走原 `08` SQL fallback。
该 fallback 会把 summary 标记为 `execution_backend='cloud_run_sklearn_bq_sql_ledger_v1'`、`ledger_executor='bigquery_sql'`；默认 Python ledger 路径为 `execution_backend='cloud_run_sklearn_ledger_v1'`、`ledger_executor='cloud_run_python'`。

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

## 8. QA

Cloud Run smoke 后执行：

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql
```

`16` 需要按实际 `p_run_id` / `p_prediction_run_id` / `p_backtest_id` 修改脚本顶部参数，或由后续调度器注入参数。
task fan-out 路径还需把 `16` 的 `p_require_task_fanout` 设为 `TRUE`。`16` 会同时断言 selected registry 已写入 matrix/work-unit 审计字段、所有 candidate task 成功、reducer 写入的 `candidate_task_bq_*` 审计计数为 0，并直接查询 `JOBS_BY_PROJECT` 兜底确认 candidate task 未读取 BigQuery 训练面板。
`17` 需要按实际 `p_experiment_id` / `p_run_id` / `p_backtest_id` 修改脚本顶部参数；task fan-out 路径需把 `p_require_train_step=FALSE`、`p_require_task_fanout=TRUE`。如果单独直接运行 train/backtest job、没有经过 orchestrator，则不运行 `17`。

## 9. 安全

1. 不提交 service account key、ADC 文件、OAuth token、OpenAI key 或 Tushare token。
2. Cloud Run 使用 service account 权限访问 BigQuery、GCS 和 Cloud Logging。
3. 本地 ADC 仅用于开发机 smoke，不写入仓库和日志。
