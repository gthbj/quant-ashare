> 文档维护：Claude Opus 4.6（最近更新 2026-06-01）

# Strategy 1 BigQuery ML Runner

基于 `ml_pv_clf_v0` 的 BigQuery ML + SQL 训练/预测/回测闭环。

## 前置条件

- `ashare_dws` 6 张 DWS 表已物化（`sql/dws/01-06`）
- `ashare_ads` 11 张 ADS 契约表已创建（`sql/ads/01`）
- `sql/qa/02_strategy1_dws_ads_checks.sql` 通过
- `pip install google-cloud-bigquery google-cloud-storage matplotlib pandas db-dtypes`

## 执行顺序

所有 BigQuery job 显式指定 `--location=asia-east2`。脚本可按顺序执行，无需手动替换。

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/01_build_training_panel.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/02_train_bqml_logistic_candidates.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/03_select_model_and_register.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/04_predict_daily.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/05_build_candidates.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/06_build_portfolio_targets.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/07_build_order_plan.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/08_run_backtest.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/09_build_metrics_and_report_inputs.sql

# render_report 必须在 10 之前：它把 report_uri 回写 summary.metrics_json，10 会断言其存在
python scripts/strategy1/render_report.py \
    --project data-aquarium \
    --backtest-id bt_s1_bqml_20260601_01 \
    --run-id s1_bqml_20260601_01 \
    --artifact-base-uri gs://ashare-artifacts/reports/strategy1 \
    --local-mirror-root reports/strategy1

bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql
```

## 参数说明

每个脚本顶部有 `DECLARE p_*` 参数块（`p_` 前缀避免与表列同名）。

| 参数 | 说明 |
|---|---|
| `p_run_id` | 本次运行唯一 ID；嵌入模型对象名以保证 run 隔离 |
| `p_backtest_id` | 回测 ID |
| `p_train_start` | 训练起点（默认 2019-04-03，避开 60 日窗口不完整期） |
| `p_target_holdings` | 持股数（OQ-010 待确认，示例值 5） |
| `p_max_single_weight` | 单票权重上限（OQ-010 待确认，示例值 0.20） |
| `p_cost_bps` | 成本假设（OQ-010 待确认，示例值 30 bps） |
| `p_benchmark` | 基准指数 canonical 代码（OQ-010 待确认，示例值 000852.SH） |
| `p_force_replace` | 是否覆盖同 run_id 结果（默认 FALSE） |

## 关键设计

- **run 隔离**：模型对象名嵌入 `p_run_id`，registry 用 `JSON_VALUE(model_params_json, '$.run_id')` 过滤。
- **04 动态模型引用**：用 `EXECUTE IMMEDIATE FORMAT(...)` 自动引用 03 选出的 selected model URI，无需手动替换。
- **回测卖出顺延**：预计算 `next_sellable_trade_date`（>= desired date, 60 交易日窗口），超窗口标记 `SELL_BLOCKED_NO_NEXT_SELLABLE_60D`。
- **报告渲染**：`render_report.py` 生成 Markdown + HTML + PNG，上传 GCS，写回 ADS `metrics_json.report_uri`。
- **OQ-010 参数**使用示例值，非业务定稿。
