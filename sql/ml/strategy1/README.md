# Strategy 1 BigQuery ML Runner

基于 `ml_pv_clf_v0` 的 BigQuery ML + SQL 训练/预测/回测闭环。

## 前置条件

- `ashare_dws` 6 张 DWS 表已物化（`sql/dws/01-06`）
- `ashare_ads` 11 张 ADS 契约表已创建（`sql/ads/01`）
- `sql/qa/02_strategy1_dws_ads_checks.sql` 通过

## 执行顺序

所有 BigQuery job 显式指定 `--location=asia-east2`。

```bash
# M1: 训练面板 + 候选模型
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/01_build_training_panel.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/02_train_bqml_logistic_candidates.sql

# M2: 模型选择 + 预测
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/03_select_model_and_register.sql
# ⚠️ 04 中 MODEL 引用需替换为 03 选出的 selected model 名
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/04_predict_daily.sql

# M3: 候选/组合/订单
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/05_build_candidates.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/06_build_portfolio_targets.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/07_build_order_plan.sql

# M4: 回测
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/08_run_backtest.sql

# M5: 指标 + 报告 + QA
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/09_build_metrics_and_report_inputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql

# 报告渲染
python scripts/strategy1/render_report.py \
    --project data-aquarium \
    --backtest-id bt_s1_bqml_20260601_01 \
    --run-id s1_bqml_20260601_01 \
    --artifact-base-uri gs://ashare-artifacts/reports/strategy1 \
    --local-mirror-root reports/strategy1
```

## 参数说明

每个脚本顶部有 `DECLARE` 参数块。关键参数：

| 参数 | 说明 |
|---|---|
| `run_id` | 本次运行唯一 ID |
| `backtest_id` | 回测 ID |
| `train_start_date` | 训练起点（默认 2019-04-03，避开 60 日窗口不完整期） |
| `target_holdings` | 持股数（OQ-010 待确认，示例值 5） |
| `max_single_weight` | 单票权重上限（OQ-010 待确认，示例值 0.20） |
| `cost_bps` | 成本假设（OQ-010 待确认，示例值 30 bps） |
| `benchmark_sec_code` | 基准指数 canonical 代码（OQ-010 待确认，示例值 000852.SH） |
| `force_replace` | 是否覆盖同 run_id 结果（默认 FALSE） |

## 注意事项

- `04_predict_daily.sql` 中的 `MODEL` 引用目前硬编码了一个候选模型名。实际运行时需替换为 `03` 脚本选出的 selected model。BigQuery 不支持动态 MODEL 引用，这是已知限制。
- OQ-010 参数（持股数、权重上限、成本、基准）使用示例值，非业务定稿。
- 回测卖出顺延用预计算 `next_sellable_trade_date` 方案（60 交易日窗口），避免 WHILE 循环。
- `reports/` 目录被 `.gitignore` 忽略，不提交。
