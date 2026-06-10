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
| `qa_cloudrun_runner_outputs` | `sql/strategy1/qa/qa_cloudrun_runner_outputs.sql` |
| `qa_cloudrun_orchestrator_status` | `sql/strategy1/qa/qa_cloudrun_orchestrator_status.sql` |
| `qa_cloudrun_ledger_resume_outputs` | `sql/strategy1/qa/qa_cloudrun_ledger_resume_outputs.sql` |

## Audit-Only Steps

Some historical diagnostic and replay SQL files live under this namespace so their
stable paths are discoverable, but their execution status is controlled by
`configs/strategy1/active_step_catalog.yml`. Files marked `audit_only` are not
active migration targets for new runner flows.

| Step | SQL |
|---|---|
| `model_quality_diagnostics` | `sql/strategy1/diagnostics/model_quality_diagnostics.sql` |
| `qa_factor_attribution_outputs` | `sql/strategy1/qa/qa_factor_attribution_outputs.sql` |
| `qa_ledger_resume_consistency` | `sql/strategy1/qa/qa_ledger_resume_consistency.sql` |
| `qa_acceptance_gate_v2_outputs` | `sql/strategy1/acceptance/qa_acceptance_gate_v2_outputs.sql` |

## Current Dataset Role

当前 Phase D2 已切换为 research-first。默认 table role 解析到
`data-aquarium.ashare_research.research_*`；`ads` 只用于显式历史审计或后续
owner-approved promotion target。meta / orchestration role 可在 catalog 中声明
per-role dataset override，例如显式 ADS 模式下 `experiment_run_status` 解析到
`data-aquarium.ashare_meta.*`。

SQL render 会按当前 step 的 catalog `inputs` / `outputs` 改写 run-scoped 表，
默认写/读 research。需要回放历史 ADS 产物时显式传 `dataset_role="ads"` 或
runner CLI 的 `--output-dataset-role ads`。无 step 上下文的全局 research 替换仍会
fail-fast，避免 `model_registry` / `acceptance_result` 等共享 ADS 源表被误替换。
Promotion job 仍需 Phase D3 单独实现，普通 runner 不会隐式写 ADS。
