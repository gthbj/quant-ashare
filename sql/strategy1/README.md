> 文档维护：GPT-5 Codex（最近更新 2026-06-10）

# Strategy1 Shared SQL Contract

本目录是当前 Strategy1 active shared BigQuery SQL 命名空间。Cloud Run Python
runner 仍负责训练、预测和 Python ledger；本目录负责 panel、candidate、
portfolio target、order plan、report input、QA、diagnostics 和 acceptance replay
SQL contract。

路径和参数契约由 `configs/strategy1/active_step_catalog.yml` 维护。active Python
caller 不应手写 `sql/ml/strategy1/**` 或 `sql/cloudrun/strategy1/**` 旧路径，应通过
catalog step name 调用。

## Active Steps

| Step | SQL |
|---|---|
| `build_training_panel_base` | `sql/strategy1/panel/build_training_panel_base.sql` |
| `build_training_panel_risk_feature` | `sql/strategy1/panel/build_training_panel_risk_feature.sql` |
| `build_candidates` | `sql/strategy1/execution/build_candidates.sql` |
| `build_portfolio_targets` | `sql/strategy1/execution/build_portfolio_targets.sql` |
| `build_order_plan` | `sql/strategy1/execution/build_order_plan.sql` |
| `build_metrics_and_report_inputs` | `sql/strategy1/reporting/build_metrics_and_report_inputs.sql` |
| `qa_runner_outputs` | `sql/strategy1/qa/qa_runner_outputs.sql` |
| `qa_model_diagnosis_outputs` | `sql/strategy1/qa/qa_model_diagnosis_outputs.sql` |
| `qa_tail_risk_outputs` | `sql/strategy1/qa/qa_tail_risk_outputs.sql` |
| `qa_lot_aware_ledger_outputs` | `sql/strategy1/qa/qa_lot_aware_ledger_outputs.sql` |
| `qa_sklearn_native_search_outputs` | `sql/strategy1/qa/qa_sklearn_native_search_outputs.sql` |
| `qa_cloudrun_python_baseline_search_outputs` | `sql/strategy1/qa/qa_cloudrun_python_baseline_search_outputs.sql` |
| `qa_risk_feature_search_outputs` | `sql/strategy1/qa/qa_risk_feature_search_outputs.sql` |
| `qa_acceptance_gate_v3_replay_outputs` | `sql/strategy1/acceptance/qa_acceptance_gate_v3_replay_outputs.sql` |

## Current Dataset Role

当前 Phase A-C 只建立 resolver 和 catalog；所有 table role 仍解析到
`data-aquarium.ashare_ads.*`，不创建、不写入 `ashare_research`。后续 research-first
和 promotion job 需要单独 PR。
