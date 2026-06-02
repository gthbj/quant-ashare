> 文档维护：Claude Opus 4.6（最近更新 2026-06-01）

# Strategy 1 BigQuery ML Runner

基于 `ml_pv_clf_v0` 的 BigQuery ML + SQL 训练/预测/回测闭环。

## 前置条件

- `ashare_dws` 6 张 DWS 表已物化（`sql/dws/01-06`）
- `ashare_ads` 11 张 ADS 契约表已创建（`sql/ads/01`）
- `sql/qa/02_strategy1_dws_ads_checks.sql` 通过
- `ashare_dim.dim_index` 与 `ashare_dwd.dwd_index_eod` 已按 OQ-004 口径重建，`sql/qa/03_oq004_index_checks.sql` 通过
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

# render_report 必须在 10 之前：它把报告状态回写 summary.metrics_json（local_report_path +
# report_upload_status；report_uri 仅在真实上传 GCS 成功时写），10 做模式感知断言。
# 默认（无 --skip-gcs-upload）会上传 GCS 并写 report_uri，需要 ashare-artifacts bucket + ADC；
# 本地验证用 --skip-gcs-upload（不写 report_uri，report_upload_status=skipped）。
python scripts/strategy1/render_report.py \
    --project data-aquarium \
    --backtest-id bt_s1_bqml_20260601_01 \
    --run-id s1_bqml_20260601_01 \
    --artifact-base-uri gs://ashare-artifacts/reports/strategy1 \
    --local-mirror-root reports/strategy1 \
    --skip-gcs-upload   # 去掉则上传 GCS 并写真实 report_uri（需 bucket + ADC）

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
| `p_cost_bps` | 当前已跑通 v0 的旧一揽子成本示例值 30 bps；OQ-010 默认成本 profile 已由 `docs/prd/PRD_20260602_02_OQ010交易成本口径.md` 固化，待后续实现 PR 改为分项成本 |
| `p_benchmark` | 基准指数 canonical 代码（示例值 000852.SH）；执行前必须存在于 `dim_index` 且完整覆盖回测 NAV 窗口 |
| `p_force_replace` | 是否覆盖同 run_id 结果（默认 FALSE） |

## 关键设计

- **run 隔离**：模型对象名嵌入 `p_run_id`，registry 用 `JSON_VALUE(model_params_json, '$.run_id')` 过滤。
- **04 动态模型引用**：用 `EXECUTE IMMEDIATE FORMAT(...)` 自动引用 03 选出的 selected model URI，无需手动替换。
- **回测交易与卖出口径（v1 ledger）**：08 只在每个调仓 period 的 `t+1 exec_date` 按当日开盘价交易；不可交易腿（不可买/卖或无开盘价）本期跳过、记为 `BUY_SKIPPED_UNTRADABLE` / `SELL_SKIPPED_UNTRADABLE` 意图行（`filled_shares=0`、无现金/换手影响），持仓 carry 到下一个调仓执行日再尝试。**不做 60 交易日 daily next-sellable 顺延搜索，也没有 `SELL_BLOCKED_NO_NEXT_SELLABLE_60D`。** 09 的 skip 统计直接从 `ads_backtest_trade_daily` 这些意图/成交行 1:1 汇总，可对账。
- **基准窗口校验**：08 执行前校验 `p_benchmark` 是 `dim_index` 中的可用收益基准，并且 `dwd_index_eod` 对 NAV 窗口每个开市日有且只有一条有效价格记录。
- **报告渲染**：`render_report.py` 生成 Markdown + HTML + PNG。默认上传 GCS 并写回 `metrics_json.report_uri`（`report_upload_status='uploaded'`）；`--skip-gcs-upload` 仅写本地镜像，**不写 `report_uri`**，改写 `local_report_path` + `report_upload_status='skipped'`。BigQuery 与 Storage 客户端在无 ADC 时都回退用 gcloud 用户 access token。
- **OQ-010 参数**使用示例值，非业务定稿。

## 回测口径：v1 账户级有状态 ledger

`08_run_backtest.sql` 自 PR #12 为账户级有状态 ledger（BigQuery scripting `WHILE` 循环逐调仓 period）：
每个 `t+1 exec_date` 先按当前持仓估值得 NAV（停牌用 ffill 收盘）→ 目标仓位 = 目标权重 × 当前 NAV
（资金复利/回收）→ 卖出先于买入 → 买入受可用现金约束（超出按比例缩放）→ 对实际持仓 netting → 循环后按交易日展开每日持仓/NAV。
`10_qa_runner_outputs.sql` 的 `cash_cny >= -1`、`gross_exposure <= 1.005`、持仓 `(trade_date, sec_code)` 唯一、
NAV 覆盖全开市日由 ledger 构造保证。**v1 简化**：不可交易腿本期跳过 + carry（无 60 日 next-sellable 顺延）、未复权口径、持有期除权简化。
背景见 `.agent/memory/DECISION_LOG.md` DECISION-20260601-07（升级触发）与 DECISION-20260602-01（落地）。
