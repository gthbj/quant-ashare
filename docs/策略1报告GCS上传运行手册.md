> 文档维护：GPT-5（最近更新 2026-06-02）

# 策略 1 报告 GCS 上传运行手册

本文是策略 1 `render_report.py` 的 uploaded 模式运行手册，只覆盖 GCS bucket、ADC、报告上传和验收步骤；不改变策略训练、回测、成本、基准或 AI 诊断口径。

## 1. 目标

策略 1 runner 当前已支持两种报告产出模式：

| 模式 | 触发方式 | 本地报告 | GCS 报告 | ADS `metrics_json` |
|---|---|---|---|---|
| local-only | 带 `--skip-gcs-upload` | 写入 `reports/strategy1/...` | 不上传 | `report_upload_status=skipped`，`report_uri=NULL` |
| uploaded | 不带 `--skip-gcs-upload` | 写入本地镜像 | 上传 `gs://ashare-artifacts/...` | `report_upload_status=uploaded`，`report_uri` 写真实 GCS 路径 |

目标验收状态是 uploaded 模式跑通：报告文件既保留本地镜像，也上传到 GCS，`ashare_ads.ads_backtest_performance_summary.metrics_json` 中的 `report_uri` 可以长期读取。

## 2. 产物路径

默认 GCS 根路径：

```text
gs://ashare-artifacts/reports/strategy1
```

单次回测上传目录：

```text
gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=<run_id>/backtest_id=<backtest_id>/
```

本地镜像目录：

```text
reports/strategy1/ml_pv_clf_v0/run_id=<run_id>/backtest_id=<backtest_id>/
```

同一个 `run_id` + `backtest_id` 的上传路径是确定性的。若要保留旧报告，不要复用相同 `backtest_id`；若复用，需接受同路径文件被覆盖或刷新。

## 3. 前置条件

1. `sql/ml/strategy1/01-09` 已跑完，并且指定 `run_id` / `backtest_id` 在 ADS 中有完整结果。
2. Python 依赖已安装：

```bash
pip install -r scripts/strategy1/requirements.txt
```

3. `gcloud` 已安装，当前账号或运行环境具备 BigQuery 和 GCS 权限。
4. `gs://ashare-artifacts` bucket 已存在，或当前账号有权限创建。
5. 不把任何 service account key、OAuth token、API key 写入仓库、文档、日志或 `.agent/memory/`。

## 4. IAM 要求

执行 uploaded 模式的身份至少需要：

| 资源 | 用途 | 最小权限建议 |
|---|---|---|
| `gs://ashare-artifacts` | 上传报告文件，必要时覆盖同路径文件 | `roles/storage.objectAdmin` 或等价 bucket 级权限 |
| `data-aquarium.ashare_ads` | 读取回测 ADS、回写 summary `metrics_json` | 可读 ADS 且可更新 `ads_backtest_performance_summary` |
| `data-aquarium.ashare_dwd` | 读取展示基准指数 | 可读 `dwd_index_eod` |

如果执行身份只允许新增对象、不允许覆盖对象，可使用唯一 `backtest_id` 避免覆盖；否则重跑同一路径时可能失败。

## 5. Bucket 准备

先确认 bucket 是否存在：

```bash
gcloud storage buckets describe gs://ashare-artifacts --project=data-aquarium
```

如不存在，按 owner 确认的 location 创建。建议与 BigQuery runner 所在区域保持一致，默认示例为 `ASIA-EAST2`：

```bash
gcloud storage buckets create gs://ashare-artifacts \
  --project=data-aquarium \
  --location=ASIA-EAST2
```

可选但建议配置：

```bash
# 防止意外公开访问
gcloud storage buckets update gs://ashare-artifacts --uniform-bucket-level-access

# 如需保留历史版本，再开启版本控制；否则保持关闭，避免成本不可控
gcloud storage buckets update gs://ashare-artifacts --versioning
```

版本控制是否开启由 owner 决定；uploaded 模式本身不依赖版本控制。

## 6. ADC 准备

本机或手动执行环境可用 ADC：

```bash
gcloud config set project data-aquarium
gcloud auth login
gcloud auth application-default login
gcloud auth application-default print-access-token >/dev/null
```

云上 runner 环境优先使用绑定的 service account。只需要让运行环境能通过 Google 默认凭据链获取凭据，不需要也不应该把 key 文件放进仓库。

`render_report.py` 会优先用 ADC；ADC 不可用时会尝试 `gcloud auth print-access-token` 回退。因此本机调试时 `gcloud auth login` 也要保持有效。

## 7. 先跑 local-only smoke

在上传前先用 local-only 模式确认报告渲染本身正常：

```bash
python scripts/strategy1/render_report.py \
  --project data-aquarium \
  --backtest-id bt_s1_bqml_20260601_01 \
  --run-id s1_bqml_20260601_01 \
  --artifact-base-uri gs://ashare-artifacts/reports/strategy1 \
  --local-mirror-root reports/strategy1 \
  --skip-gcs-upload
```

预期：

- 本地目录生成 `report.md`、`report.html`、`metrics.json`、CSV 附件、图表和 AI 诊断证据包。
- ADS summary 中 `report_upload_status=skipped`。
- ADS summary 中 `report_uri` 为空。

## 8. 跑 uploaded 模式

确认 bucket、IAM、ADC 都可用后，去掉 `--skip-gcs-upload`：

```bash
python scripts/strategy1/render_report.py \
  --project data-aquarium \
  --backtest-id bt_s1_bqml_20260601_01 \
  --run-id s1_bqml_20260601_01 \
  --artifact-base-uri gs://ashare-artifacts/reports/strategy1 \
  --local-mirror-root reports/strategy1
```

预期：

- 本地镜像仍然存在，方便用户直接读取。
- GCS 目录存在并包含完整报告产物。
- ADS summary 中 `report_upload_status=uploaded`。
- ADS summary 中 `report_uri` 是真实 `gs://ashare-artifacts/...` 路径。

## 9. 验收检查

检查 GCS 文件：

```bash
gcloud storage ls \
  gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_bqml_20260601_01/backtest_id=bt_s1_bqml_20260601_01/
```

检查 ADS 回写：

```bash
bq query --use_legacy_sql=false --location=asia-east2 '
SELECT
  JSON_VALUE(metrics_json, "$.report_upload_status") AS report_upload_status,
  JSON_VALUE(metrics_json, "$.report_uri") AS report_uri,
  JSON_VALUE(metrics_json, "$.local_report_path") AS local_report_path,
  JSON_QUERY(metrics_json, "$.artifact_manifest") AS artifact_manifest
FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary`
WHERE backtest_id = "bt_s1_bqml_20260601_01"
'
```

最后跑 runner QA：

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql
```

uploaded 模式的合格标准：

- `report_upload_status = 'uploaded'`
- `report_uri` 非空，且以 `gs://ashare-artifacts/reports/strategy1/` 开头
- `local_report_path` 非空
- `artifact_manifest` 包含 `report.md`、`report.html`、`benchmark_nav.csv`、`diagnosis_evidence.json`、`ai_analysis.json`
- `10_qa_runner_outputs.sql` 全部 ASSERT 通过

## 10. 常见问题

| 现象 | 常见原因 | 处理 |
|---|---|---|
| `bucket not found` | bucket 未创建或 project 错误 | 先 `gcloud config set project data-aquarium`，再 describe/create bucket |
| `403 Permission denied` | GCS 或 BigQuery 权限不足 | 给执行身份补 bucket 写权限、ADS summary 更新权限和相关表读取权限 |
| `report_uri` 仍为空 | 命令仍带 `--skip-gcs-upload`，或上传失败后未回写 | 去掉 `--skip-gcs-upload` 重跑，并检查错误日志 |
| `10_qa_runner_outputs.sql` 报 report 断言失败 | render 未跑、上传状态不一致或 manifest 缺文件 | 先重跑 render，再检查 ADS `metrics_json` 和本地/GCS 文件 |
| 本地有报告但 GCS 没有 | local-only 模式或 GCS 上传失败 | 确认命令参数、ADC、bucket 权限和 bucket 路径 |
| LLM 诊断失败 | AI 凭据缺失或外部服务失败 | `auto` 会退化为 `evidence_only`；uploaded 验收不要求 LLM 必须成功 |

## 11. 安全约束

- 不提交任何凭据文件、token、key 或未脱敏日志。
- 不手工把虚假的 `report_uri` 写进 ADS；必须由 `render_report.py` 上传成功后回写。
- local-only 模式必须保持 `report_uri=NULL`，不能把未上传的 `gs://` 路径当成真实报告地址。
- 若报告用于长期归档，优先用唯一 `run_id` / `backtest_id`，避免重跑覆盖旧产物。

## 12. 执行清单

- [ ] 确认 `sql/ml/strategy1/01-09` 已针对目标 `run_id` / `backtest_id` 跑完。
- [ ] 确认 `gs://ashare-artifacts` 存在，location 已由 owner 确认。
- [ ] 确认执行身份具备 GCS 写权限、ADS summary 更新权限和 DWD/ADS 读取权限。
- [ ] 配置 ADC 或云上 service account 默认凭据。
- [ ] 先用 `--skip-gcs-upload` 跑 local-only smoke。
- [ ] 去掉 `--skip-gcs-upload` 跑 uploaded 模式。
- [ ] 用 `gcloud storage ls` 验证 GCS 文件存在。
- [ ] 查询 ADS `metrics_json`，确认 `report_upload_status=uploaded` 且 `report_uri` 非空。
- [ ] 跑通 `sql/ml/strategy1/10_qa_runner_outputs.sql`。
