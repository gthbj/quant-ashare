#!/usr/bin/env python3
"""Run candidate/portfolio/order SQL, Python ledger, report and QA."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from scripts.strategy1_cloudrun.bq_io import make_client
from scripts.strategy1_cloudrun.config import (
    Experiment,
    add_common_args,
    apply_cli_overrides,
    filter_experiments,
    load_manifest,
    load_runner_config,
    experiment_from_b64,
)
from scripts.strategy1_cloudrun.ledger import LedgerParams, run_ledger
from scripts.strategy1_cloudrun.sql_runner import run_sql_script


SQL_STEPS = [
    "sql/ml/strategy1/05_build_candidates.sql",
    "sql/ml/strategy1/06_build_portfolio_targets.sql",
    "sql/ml/strategy1/07_build_order_plan.sql",
]


def main() -> int:
    args = parse_args()
    config = apply_cli_overrides(load_runner_config(args.config), args)
    experiment = resolve_experiment(args)
    plan = {
        "entrypoint": "backtest_report",
        "execution_backend": config.execution_backend,
        "project": config.project,
        "region": config.region,
        "experiment": experiment.to_params(),
        "use_python_ledger": not args.use_bq_ledger,
        "run_report": not args.skip_report,
        "run_diagnosis": not args.skip_diagnosis,
        "run_qa": not args.skip_qa,
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    client = make_client(config.project, config.region)
    sql_params = build_sql_params(experiment, args.force_replace)
    job_ids = []
    for script in SQL_STEPS:
        job_ids.append({"script": script, "job_id": run_sql_script(client, script, sql_params)})
    if args.use_bq_ledger:
        job_ids.append({
            "script": "sql/ml/strategy1/08_run_backtest.sql",
            "job_id": run_sql_script(client, "sql/ml/strategy1/08_run_backtest.sql", sql_params),
        })
    else:
        ledger_result = run_ledger(client, build_ledger_params(config.project, experiment, args.force_replace))
        job_ids.append({"script": "python_ledger_exec_v1", "result": ledger_result})
    job_ids.append({
        "script": "sql/ml/strategy1/09_build_metrics_and_report_inputs.sql",
        "job_id": run_sql_script(client, "sql/ml/strategy1/09_build_metrics_and_report_inputs.sql", sql_params),
    })
    if not args.skip_report:
        run_subprocess(report_command(config, experiment, args.skip_gcs_upload))
    if not args.skip_qa:
        job_ids.append({
            "script": "sql/ml/strategy1/10_qa_runner_outputs.sql",
            "job_id": run_sql_script(client, "sql/ml/strategy1/10_qa_runner_outputs.sql", sql_params),
        })
    if not args.skip_diagnosis:
        run_subprocess(diagnosis_command(config, experiment, args.skip_gcs_upload))
        if not args.skip_qa:
            job_ids.append({
                "script": "sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql",
                "job_id": run_sql_script(client, "sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql", sql_params),
            })
    print(json.dumps({"status": "succeeded", "steps": job_ids}, ensure_ascii=False, indent=2, default=str))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategy 1 Cloud Run backtest/report")
    add_common_args(parser)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--prediction-run-id", default=None)
    parser.add_argument("--backtest-id", default=None)
    parser.add_argument("--manifest-resolved", default=None)
    parser.add_argument("--experiment-json", default=None, help="Base64 encoded resolved experiment payload")
    parser.add_argument("--force-replace", action="store_true")
    parser.add_argument("--skip-gcs-upload", action="store_true")
    parser.add_argument("--skip-report", action="store_true")
    parser.add_argument("--skip-diagnosis", action="store_true")
    parser.add_argument("--skip-qa", action="store_true")
    parser.add_argument("--use-bq-ledger", action="store_true", help="Fallback path for equivalence tests")
    return parser.parse_args()


def resolve_experiment(args: argparse.Namespace) -> Experiment:
    if args.experiment_json:
        exp = experiment_from_b64(args.experiment_json)
        if not exp.is_executable:
            raise ValueError(f"{exp.experiment_id} contains unresolved placeholders or blocked status")
        return exp
    _, experiments = load_manifest(args.manifest)
    matches = filter_experiments(experiments, experiment_id=args.experiment_id, include_blocked=True)
    if not matches:
        raise ValueError(f"experiment_id {args.experiment_id} not found")
    exp = matches[0]
    replacements = {}
    for attr in ("run_id", "prediction_run_id", "backtest_id"):
        value = getattr(args, attr)
        if value:
            replacements[attr] = value
    if replacements:
        import dataclasses
        exp = dataclasses.replace(exp, **replacements)
    if not exp.is_executable:
        raise ValueError(f"{exp.experiment_id} contains unresolved placeholders or blocked status")
    return exp


def build_sql_params(exp: Experiment, force_replace: bool) -> dict[str, object]:
    return {
        "p_run_id": exp.run_id,
        "p_prediction_run_id": exp.prediction_run_id,
        "p_strategy_id": "ml_pv_clf_v0",
        "p_backtest_id": exp.backtest_id,
        "p_experiment_id": exp.experiment_id,
        "p_experiment_group": exp.experiment_group,
        "p_baseline_experiment_id": exp.baseline_experiment_id,
        "p_parent_experiment_id": exp.parent_experiment_id,
        "p_parent_run_id": exp.parent_run_id,
        "p_rebalance_frequency": exp.rebalance_frequency,
        "p_target_holdings": exp.target_holdings,
        "p_max_single_weight": exp.max_single_weight,
        "p_label_horizon": exp.label_horizon,
        "p_horizon_natural_frequency": exp.horizon_natural_frequency,
        "p_feature_set_id": exp.feature_set_id,
        "p_execution_backend": "cloud_run_sklearn_ledger_v1",
        "p_predict_start": exp.predict_start,
        "p_predict_end": exp.predict_end,
        "p_force_replace": force_replace,
    }


def build_ledger_params(project: str, exp: Experiment, force_replace: bool) -> LedgerParams:
    return LedgerParams(
        project=project,
        run_id=exp.run_id,
        backtest_id=exp.backtest_id or f"bt_{exp.run_id}",
        predict_start=exp.predict_start,
        predict_end=exp.predict_end,
        force_replace=force_replace,
    )


def report_command(config, exp: Experiment, skip_gcs_upload: bool) -> list[str]:
    cmd = [
        sys.executable, "scripts/strategy1/render_report.py",
        "--project", config.project,
        "--run-id", exp.run_id,
        "--backtest-id", exp.backtest_id,
        "--artifact-base-uri", config.artifact_base_uri,
        "--local-mirror-root", "reports/strategy1",
    ]
    if skip_gcs_upload:
        cmd.append("--skip-gcs-upload")
    return cmd


def diagnosis_command(config, exp: Experiment, skip_gcs_upload: bool) -> list[str]:
    cmd = [
        sys.executable, "scripts/strategy1/diagnose_model_quality.py",
        "--project", config.project,
        "--run-id", exp.prediction_run_id,
        "--backtest-id", exp.backtest_id,
        "--artifact-base-uri", config.artifact_base_uri,
        "--local-mirror-root", "reports/strategy1",
        "--p-target-holdings", str(exp.target_holdings),
        "--p-label-horizon", str(exp.label_horizon),
    ]
    if skip_gcs_upload:
        cmd.append("--skip-gcs-upload")
    return cmd


def run_subprocess(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
