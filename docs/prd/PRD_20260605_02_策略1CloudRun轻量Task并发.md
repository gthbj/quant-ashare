> 文档维护：GPT-5（最近更新 2026-06-05）

# PRD: 策略 1 Cloud Run 轻量 Task 并发训练

> 状态：草案，待 review / 合并。
> 范围声明：本文只定义策略 1 Cloud Run 训练侧的轻量 task fan-out 架构；不实现代码、不部署 Cloud Run Job、不执行 BigQuery、不生成或覆盖任何产物。
> 关联：`docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`、`docs/prd/PRD_20260603_05_策略1实验并发调度与隔离.md`、`docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`、`docs/prd/PRD_20260604_02_策略1月度滚动重训.md`。

---

## 1. 背景

策略 1 Cloud Run runner 首版已经证明链路可运行：Cloud Run Jobs 可以完成 sklearn 训练 / 预测、Python ledger 回测、报告、诊断和 QA。但当前训练入口仍是一个 `train_predict` execution 内顺序训练候选模型。

后续为了排查 sklearn vs BQML parity，候选网格会扩展到 35 个 logistic 候选；未来如果做 100 个候选、参数组合或实验组合，单 execution 顺序训练会产生两个问题：

1. 墙钟时间长，难以快速迭代。
2. 若用高配 Cloud Run execution 跑单候选或少量并发，会浪费 CPU / 内存，成本不经济。

owner 明确要求：

1. 35 个候选 / 实验可以同时并发。
2. 未来 100 个候选 / 实验也能并发。
3. 尽量减少 CPU 浪费，节约成本。

因此本文定义一个新的训练侧执行架构：把并发单位从高配 Cloud Run execution 改成轻量 Cloud Run Job task，把重数据读取集中到一次 `prepare_matrix`。

## 2. 目标

### 2.1 P0 目标

1. 支持候选模型或训练实验按 task fan-out 并发执行，`N` 个 work units 可启动 `N` 个 Cloud Run tasks。
2. `parallelism` 默认等于 work unit 数量，owner 可显式限流。
3. 每个 task 使用小规格资源，避免一个候选占用 4 CPU / 16Gi 但吃不满。
4. BigQuery 训练面板读取 / 导出只允许在 `prepare_matrix` 发生一次，禁止每个 candidate task 重复扫描 BigQuery 全量训练面板。
5. 冻结训练矩阵、特征顺序、label、split、预处理统计和 manifest hash 写入 GCS，供所有 task 共享。
6. `train_candidate_fanout` 只训练自己的 candidate / work unit，只写自己的 artifact 和状态。
7. `select_register_predict` 在所有 required task 成功后汇总候选、选型、写 registry 和 prediction。
8. 保持既有 ADS 契约、GCS artifact、QA、报告和诊断口径。

### 2.2 P1 目标

1. 支持同一个 fan-out 架构同时服务候选级并发和实验级并发。
2. 支持失败 task 只重跑失败分片，不重跑全部候选。
3. 支持月度滚动重训在同一 frozen matrix / fan-out 架构上执行。
4. 支持按实测内存 / CPU 利用率自动推荐 task CPU / memory，但不自动绕过 owner 的并发限制。

## 3. 非目标

1. 不改变模型族；P0 仍以 `sklearn.linear_model.LogisticRegression` 为主。
2. 不引入 Ray、Dask、Spark、Kubernetes 或自建队列。
3. 不把 BigQuery DWS/ADS 迁移到 Cloud Run 内生成。
4. 不在本文实现 preprocess 消融、模型族切换或业务参数重选。
5. 不改变 `ledger_exec_v1` 回测语义。
6. 不让每个 candidate task 直接写 `ads_model_registry` selected 记录或 `ads_model_prediction_daily`，避免多个 task 竞争写 ADS。

## 4. 总体架构

### 4.1 执行链路

```text
01_build_training_panel.sql
  -> prepare_matrix
      -> frozen matrix artifact on GCS
      -> matrix manifest / work unit manifest
  -> train_candidate_fanout --tasks=N --candidate-parallelism=M
      -> candidate artifact per task
      -> candidate status per task
  -> select_register_predict
      -> selected model
      -> ads_model_registry
      -> ads_model_prediction_daily
  -> backtest_report
      -> 05-07 / Python ledger / report / diagnosis / QA
```

### 4.2 Cloud Run Jobs

| Job | 任务数 | 推荐规格 | 职责 |
|---|---:|---|---|
| `strategy1-prepare-matrix-job` | 1 | 4 vCPU / 16Gi 起步 | 从 BigQuery 读取或导出训练面板，生成 frozen matrix |
| `strategy1-train-candidate-fanout-job` | `N` | 默认 1 vCPU / 2-4Gi | 每个 task 训练一个 candidate / work unit |
| `strategy1-select-register-predict-job` | 1 | 2-4 vCPU / 8-16Gi | 汇总候选，选型，预测，写 ADS |
| `strategy1-backtest-report-job` | 1 / 每实验 1 | 沿用现配置 | 回测、报告、诊断、QA |

`strategy1-train-candidate-fanout-job` 使用 Cloud Run Jobs 原生 task 机制。task 通过以下环境变量识别自己的分片：

```text
CLOUD_RUN_TASK_INDEX
CLOUD_RUN_TASK_COUNT
```

### 4.3 并发语义

```text
work_unit_count = N
owner 未设置 --candidate-parallelism 或设置为 0
  => resolved_candidate_parallelism = N
  => 单个 execution 执行 tasks=N

owner 设置 --candidate-parallelism M 且 M > 0
  => resolved_candidate_parallelism = MIN(M, N)
  => orchestrator 将 work units 分成若干批，每批最多 M 个 tasks
```

示例：

| work units | owner 未限流 | 实际 parallelism |
|---:|---:|---:|
| 35 | 未设置 | 35 |
| 100 | 未设置 | 100 |
| 100 | 20 | 20 |

项目代码不得把默认候选并发静默降到 2、4 或其他保守值。若 GCP quota 或预算不足，由 owner 设置显式并发上限。

实现注意：当前 `gcloud run jobs execute` 支持按 execution 覆盖 `--tasks`，但不支持按 execution 覆盖 `--parallelism`。因此 P0 不要求运行时修改共享 Job 的 `parallelism` 配置。推荐将 `strategy1-train-candidate-fanout-job` 的 Job spec `parallelism` 预设为 owner 允许的最大值；截至 OQ-010 Cloud Run Python baseline search，owner 确认的当前最大值为 40，对应 `candidate_count=40` / `candidate_parallelism=40`。默认全并发时单次执行 `--tasks=N`；owner 显式限流时，orchestrator 通过分批执行实现 cap，每批 `--tasks<=M`，并通过 batch manifest 或 `TASK_INDEX_OFFSET` 映射到原始 work unit。不得在多个 run 共享同一个 Job 时无锁执行 `gcloud run jobs update --parallelism`，避免并发 run 互相改配置。

## 5. Work Unit 定义

### 5.1 Work unit 类型

P0 支持两类 work unit：

| `unit_type` | 说明 | 示例 |
|---|---|---|
| `candidate_train` | 同一个实验 / run_id 下的一个候选模型 | `l2_c_0_1`、`elastic_c_1_l1_0_5` |
| `experiment_train` | 一个完整训练实验的 selected model 候选集合入口；P0 可先拆为候选级 units | `oq010_d1_pv_fin_quality` |

P0 推荐先实现 `candidate_train`。100 个“实验”如果本质是 100 个独立参数组合，也应先落成 100 个 work units，再用同一 task fan-out 执行；如果每个实验内部还有 35 个候选，则应按 `experiment_id + candidate_id` 展开为更细粒度 work units。

### 5.2 Work unit manifest

`prepare_matrix` 必须输出 work unit manifest：

```json
{
  "manifest_version": "strategy1_task_fanout_work_units_v1",
  "run_id": "<run_id>",
  "experiment_id": "<experiment_id>",
  "matrix_id": "<matrix_id>",
  "work_unit_count": 35,
  "unit_type": "candidate_train",
  "units": [
    {
      "unit_index": 0,
      "unit_id": "candidate=l2_c_0_01",
      "candidate_id": "l2_c_0_01",
      "model_params": {
        "penalty": "l2",
        "C": 0.01,
        "l1_ratio": null
      },
      "output_uri": "gs://ashare-artifacts/models/strategy1/.../candidates/l2_c_0_01/"
    }
  ]
}
```

映射规则：

```text
CLOUD_RUN_TASK_INDEX = unit_index
```

如果 task index 找不到 unit，必须 fail-fast，不得取默认候选。

## 6. Frozen Matrix 契约

### 6.1 GCS 路径

```text
gs://ashare-artifacts/models/strategy1/ml_pv_clf_v0/
  run_id=<run_id>/
  matrix_id=<matrix_id>/
    matrix_manifest.json
    work_units.json
    feature_schema.json
    preprocess_stats.json
    train_features.parquet
    train_labels.parquet
    valid_features.parquet
    valid_labels.parquet
    predict_features.parquet
    predict_index.parquet
```

大矩阵可以分片：

```text
train_features/part-00000.parquet
valid_features/part-00000.parquet
predict_features/part-00000.parquet
```

### 6.2 必备内容

P0 明确采用 `prepare_matrix` 一次性预处理方案：

1. `prepare_matrix` 是唯一允许 fit / 计算 / 应用训练集预处理统计量的步骤。
2. `train_features.parquet`、`valid_features.parquet`、`predict_features.parquet` 均为已按 train-only 统计量处理后的 float32 frozen matrix。
3. candidate task 只读取已预处理的 train / valid 矩阵，不重新 winsor、zscore、impute 或 fit 任何预处理器。
4. `preprocess_stats.json` 作为审计、复现、hash 校验和后续新增 predict 分片转换依据保留，不作为 candidate task 每次重新应用预处理的入口。

| 文件 | 内容 |
|---|---|
| `matrix_manifest.json` | run_id、matrix_id、source table、source row counts、schema hash、created_at、container image |
| `work_units.json` | task index 到 candidate / experiment 的映射 |
| `feature_schema.json` | 特征列顺序、类型、feature_set_id、feature_version |
| `preprocess_stats.json` | train-only median / winsor / mean / std 或对应 preprocess 版本统计 |
| `*_features.parquet` | 已预处理的 float32 特征矩阵 |
| `*_labels.parquet` | label、target_return、split_tag、trade_date、sec_code |
| `predict_index.parquet` | 预测写回所需 `(trade_date, sec_code, horizon)` |

candidate task 的读取范围必须只覆盖 `train_features`、`train_labels`、`valid_features`、`valid_labels` 和 manifest / schema / stats 小文件；`predict_features` 和 `predict_index` 仅由 reducer / predict step 读取。

### 6.3 Hash 与可追溯

`matrix_manifest.json` 必须记录：

| 字段 | 说明 |
|---|---|
| `matrix_id` | 唯一矩阵 ID，建议含 run_id + hash |
| `source_run_id` | `ads_ml_training_panel_daily.run_id` |
| `source_row_count` | 原始面板行数 |
| `train_row_count` / `valid_row_count` / `predict_row_count` | split 行数 |
| `feature_order_sha256` | 特征顺序 hash |
| `preprocess_stats_sha256` | 预处理统计 hash |
| `work_units_sha256` | work unit manifest hash |
| `created_by_job` / `created_by_execution` | Cloud Run execution id |

candidate task 输出必须回写这些 hash；reducer 只接受 hash 完全一致的候选输出。

## 7. 成本控制

### 7.1 资源规格

P0 推荐从小规格开始：

| task 类型 | 默认规格 | 升级条件 |
|---|---|---|
| candidate task | 1 vCPU / 2Gi | OOM 或单候选训练时间过长时升到 1 vCPU / 4Gi 或 2 vCPU / 4-8Gi |
| prepare matrix | 4 vCPU / 16Gi | Parquet 写入或矩阵构建 OOM 时上调 |
| reducer / predict | 2-4 vCPU / 8-16Gi | 预测矩阵过大或写 ADS 过慢时上调 |

不建议 candidate task 默认 4 vCPU / 16Gi。单候选 sklearn 训练未必吃满 4 CPU，高配 task 容易浪费。

### 7.2 BigQuery 扫描约束

硬规则：

1. 全量训练面板读取 / 导出只允许在 `prepare_matrix` 中发生。
2. candidate task 不得查询 `ads_ml_training_panel_daily` 全量面板。
3. candidate task 只允许读取 GCS frozen matrix 和必要的小 metadata。
4. reducer 可读取 candidate artifact 和 selected model 所需矩阵，但不得重新扫全量训练面板。

违反该规则时 QA 必须 fail。

执行机制：

1. 所有 Cloud Run runner 发起的 BigQuery job 必须带 job labels，至少包含：
   - `pipeline_component=strategy1_cloudrun`
   - `pipeline_step=prepare_matrix` / `train_candidate_task` / `select_register_predict` / `backtest_report`
   - `run_id=<run_id>`
   - `matrix_id=<matrix_id>`（适用时）
2. `prepare_matrix` 是唯一允许读取 `ashare_ads.ads_ml_training_panel_daily` 全量训练面板的 step。
3. `train_candidate_task` 代码层必须使用受控 BigQuery wrapper；该 wrapper 默认禁止查询 `ashare_ads.ads_ml_training_panel_daily`、`ashare_dws.dws_stock_sample_daily` 等全量训练源表，只允许读取小 metadata 或不查 BigQuery。
4. QA-TASK-8 通过 `INFORMATION_SCHEMA.JOBS_BY_PROJECT`（region=`asia-east2`）或等价审计表检查 job labels / referenced tables：任一 `pipeline_step='train_candidate_task'` 的 job 引用全量训练面板或扫描字节超过 task metadata 阈值时 fail。
5. 若 BigQuery `INFORMATION_SCHEMA` 无法稳定暴露所需 referenced table 字段，则 runner 必须把每个 BigQuery job 的 `job_id`、labels、referenced tables、total bytes processed 写入 `strategy1_experiment_run_status` 或独立 audit artifact，再由 QA 读取该审计结果。

### 7.3 并发与预算

默认单批全并发是为了满足“能并发就并发”的要求；成本保护通过以下方式实现：

1. task 规格小，而不是高配 execution。
2. 重数据读取只做一次。
3. owner 可显式设置 `--candidate-parallelism M`。
4. 若 GCP quota 不足，失败要显式记录，不得静默降并发。
5. 可选增加 `--max-task-cpu` / `--max-task-memory` dry-run 检查，防止误用高规格候选 task。

## 8. Candidate Task 行为

每个 candidate task 必须：

1. 读取 `work_units.json`。
2. 用 `CLOUD_RUN_TASK_INDEX` 找到唯一 work unit。
3. 只读取 GCS frozen train / valid 已预处理矩阵，以及 labels / manifest / schema / stats 小文件。
4. 不读取 `predict_features` / `predict_index`。
5. 不重新 fit 或应用 winsor、zscore、impute 等预处理；`preprocess_stats.json` 仅用于 hash 校验和审计。
6. 训练自己的模型。
7. 在 valid split 上计算 raw / reversed / oriented metrics。
8. 写自己的 artifact。
9. 写自己的 task status。

输出路径：

```text
gs://ashare-artifacts/models/strategy1/ml_pv_clf_v0/
  run_id=<run_id>/
  matrix_id=<matrix_id>/
  candidates/
    unit_index=<i>/
      candidate_metrics.json
      model.joblib
      training_log.json
      task_status.json
```

`task_status.json` 必须包含：

| 字段 | 说明 |
|---|---|
| `unit_index` | task index |
| `unit_id` | work unit id |
| `candidate_id` | candidate id |
| `status` | `succeeded` / `failed` |
| `matrix_id` | frozen matrix id |
| `feature_order_sha256` | 特征顺序 hash |
| `started_at` / `ended_at` | 时间 |
| `cloud_run_execution_id` | execution id |
| `cloud_run_task_index` | task index |
| `error_summary` | 失败摘要 |

## 9. Reducer / Select / Predict

`select_register_predict` 必须：

1. 读取 `work_units.json`。
2. 确认 required candidate artifact 全部存在且状态为 `succeeded`。
3. 校验所有 candidate 的 `matrix_id`、`feature_order_sha256`、`preprocess_stats_sha256` 一致。
4. 汇总 `candidate_metrics.json`。
5. 按既有选型规则选择 selected model：

```text
oriented_valid_rank_ic_mean
  -> valid_topn_fwd_ret_mean
  -> roc_auc
```

6. 写 selected model artifact。
7. 写 `ads_model_registry`。
8. 用 selected model 对 predict split 生成预测。
9. 写 `ads_model_prediction_daily`。
10. 写 `model_quality_parity.json`、`candidate_metrics.csv/json` 和 `implementation_audit.json`。

若任一 required task 失败，reducer 必须 fail-fast，不得从部分候选中选模型，除非 owner 显式设置 `--allow-partial-candidates`，且该模式不得用于正式 baseline。

## 10. 状态表与幂等

建议扩展或复用：

```text
ashare_meta.strategy1_experiment_run_status
```

新增 step：

| step | 说明 |
|---|---|
| `cloudrun_prepare_matrix` | frozen matrix 构建 |
| `cloudrun_train_candidate_fanout` | candidate task fan-out execution |
| `cloudrun_train_candidate_task` | 可选：按 task index 记录细粒度状态 |
| `cloudrun_select_register_predict` | reducer + selected model + prediction |
| `cloudrun_backtest_report` | 既有回测报告 |

幂等规则：

1. 同一 `run_id + matrix_id` 的 `prepare_matrix` 已成功且 manifest hash 一致时可复用。
2. candidate task 输出路径必须包含 `unit_index` 和 `candidate_id`，禁止多个 task 写同一对象。
3. reducer 写 ADS 前必须检查 selected registry / prediction 是否已存在。
4. `force_replace=true` 时按 run_id 清理本次训练 / 预测输出，但不得删除其他 run_id。
5. task 重试只能覆盖同一 `unit_index` 的 staging 输出；正式 `candidate_metrics.json` 发布需要写入完成标记。

## 11. QA

新增或扩展 Cloud Run QA：

| QA | 断言 |
|---|---|
| `QA-TASK-1` | `matrix_manifest.json`、`work_units.json`、`feature_schema.json` 存在 |
| `QA-TASK-2` | work unit count = Cloud Run task count |
| `QA-TASK-3` | 每个 required `unit_index` 只有一个 succeeded 输出 |
| `QA-TASK-4` | candidate outputs 的 `matrix_id` / feature hash / preprocess hash 全一致 |
| `QA-TASK-5` | reducer selected candidate 必须来自 succeeded candidate set |
| `QA-TASK-6` | selected registry 记录 `matrix_id`、`work_units_sha256`、`candidate_parallelism_resolved` |
| `QA-TASK-7` | `ads_model_prediction_daily` 只由 reducer 写入，candidate task 不写 prediction ADS |
| `QA-TASK-8` | BigQuery 全量训练面板读取只发生在 `cloudrun_prepare_matrix` step |
| `QA-TASK-9` | owner 未限流时执行批次数为 1，task count = work unit count，且 Job spec max parallelism >= work unit count |
| `QA-TASK-10` | candidate task CPU / memory 不超过 PRD 默认或 owner 显式配置 |

`16_qa_cloudrun_runner_outputs.sql` 可扩展为 task fan-out 模式感知 QA。若 BigQuery SQL 无法直接读取 GCS manifest，可由 reducer 将 manifest 摘要写入 `ads_model_registry.metrics_json` 和 `strategy1_experiment_run_status`，再由 QA 断言。

## 12. CLI 契约

### 12.1 Orchestrator

```bash
python -m scripts.strategy1_cloudrun.orchestrate_experiments \
  --project data-aquarium \
  --region asia-east2 \
  --experiment-id <experiment_id> \
  --train-mode task_fanout \
  --candidate-parallelism 0
```

### 12.2 Prepare matrix

```bash
python -m scripts.strategy1_cloudrun.prepare_matrix \
  --project data-aquarium \
  --region asia-east2 \
  --experiment-id <experiment_id> \
  --run-id <run_id> \
  --matrix-id <matrix_id> \
  --artifact-base-uri gs://ashare-artifacts/models/strategy1
```

### 12.3 Candidate fan-out

Cloud Run Jobs:

```bash
gcloud run jobs execute strategy1-train-candidate-fanout-job \
  --project data-aquarium \
  --region asia-east2 \
  --tasks <work_unit_count> \
  --update-env-vars=MATRIX_ID=<matrix_id>,WORK_UNITS_URI=<work_units_uri>,TASK_INDEX_OFFSET=0 \
  --args="train-candidate-task" \
  --wait
```

如果 owner 设置 `--candidate-parallelism M` 且 `M < work_unit_count`，orchestrator 不修改共享 Job 配置，而是分批执行：

```bash
gcloud run jobs execute strategy1-train-candidate-fanout-job \
  --project data-aquarium \
  --region asia-east2 \
  --tasks <batch_size> \
  --update-env-vars=MATRIX_ID=<matrix_id>,WORK_UNITS_URI=<work_units_uri>,TASK_INDEX_OFFSET=<batch_start_index> \
  --args="train-candidate-task" \
  --wait
```

task 内部使用：

```text
global_unit_index = TASK_INDEX_OFFSET + CLOUD_RUN_TASK_INDEX
```

若使用 batch-specific `work_units.json`，则 `TASK_INDEX_OFFSET` 可为 0，但 reducer 必须能追溯原始 `unit_index`。

### 12.4 Reducer

```bash
python -m scripts.strategy1_cloudrun.select_register_predict \
  --project data-aquarium \
  --region asia-east2 \
  --experiment-id <experiment_id> \
  --run-id <run_id> \
  --matrix-id <matrix_id> \
  --require-all-candidates
```

## 13. 分阶段实现

### Phase 1: PRD 与 dry-run 计划

交付：

1. 本 PRD。
2. Orchestrator dry-run 输出 task fan-out 计划。
3. 不执行 Cloud Run、不写 GCS、不写 ADS。

验收：

1. PRD review 通过。
2. dry-run 能显示 work unit count、resolved parallelism、task resource 和 GCS 路径。

### Phase 2: prepare_matrix

交付：

1. `prepare_matrix.py`。
2. frozen matrix GCS artifact。
3. manifest hash / row count / feature hash。

验收：

1. 与 `ads_ml_training_panel_daily` 行数一致。
2. train / valid / predict split 行数一致。
3. 特征顺序与原 `feature_column_list` 一致。
4. 不泄露 valid/test 统计量到预处理。

### Phase 3: candidate task fan-out

交付：

1. `train_candidate_task.py`。
2. `strategy1-train-candidate-fanout-job`。
3. 每 task 小规格资源配置。
4. task status 和 candidate artifact。

验收：

1. 35 个 candidate 能以 `tasks=35` 执行。
2. owner 可用 `--candidate-parallelism` 通过 batch chunking 限流，且不运行时修改共享 Job spec。
3. candidate task 不扫 BigQuery 全量训练面板。
4. 单 task OOM 不影响其他 task artifact 完整性。

### Phase 4: reducer / select / predict

交付：

1. `select_register_predict.py`。
2. selected model artifact。
3. `ads_model_registry` / `ads_model_prediction_daily` 写入。
4. `16` QA task fan-out 断言。

验收：

1. selected candidate 来自 succeeded set。
2. parity metrics 与旧 `train_predict` 口径一致。
3. `16` QA 通过。

### Phase 5: 100 work units smoke

交付：

1. 100 work units dry-run。
2. 如 GCP quota 允许，100 task smoke。
3. 成本 / 时间 / OOM 观测报告。

验收：

1. 不因代码默认限流导致并发低于 work unit count。
2. owner 显式限流生效。
3. 成本报告显示 BigQuery 扫描只发生在 prepare step。

## 14. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 100 tasks 同时读 GCS 矩阵造成 I/O 压力 | task 变慢或失败 | Parquet 分片、按列读取、必要时 owner 限流 |
| 单 task 1 vCPU 训练过慢 | 墙钟时间不达预期 | 升到 2 vCPU，小步实测，不默认 4 vCPU |
| 每 task 复制大矩阵导致内存高 | OOM | float32、按 split / row group 读取、只读本 task 必需数据 |
| partial candidates 被误选 | 选型不完整 | reducer 默认 require all candidates |
| task 重试覆盖正确结果 | artifact 污染 | staging + completion marker + generation precondition |
| GCP quota 不足 | 全并发失败 | 显式记录失败，owner 设置 `--candidate-parallelism` 或提高 quota |
| 与实验级并发混淆 | 状态和成本难追踪 | work unit manifest 统一记录 `unit_type`，candidate fan-out 与 experiment fan-out 不混写 ADS |

## 15. 关闭标准

本文关闭需满足：

1. `prepare_matrix -> train_candidate_fanout -> select_register_predict` 端到端跑通。
2. 35 个 candidate task 在默认模式下能单批并发执行。
3. owner 显式限流能通过分批执行生效。
4. BigQuery 全量训练面板读取只发生在 `prepare_matrix`。
5. selected model / prediction / artifact 与 ADS 契约对齐。
6. `16` QA 扩展断言通过。
7. 产出一次 35 work units 的成本 / 时间 / 资源利用率对照。
8. 文档说明何时用 35/100 全并发，何时 owner 应限流。
