#!/usr/bin/env python3
"""Run candidate/portfolio/order SQL, Python ledger, report and QA."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

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
from scripts.strategy1_cloudrun.ledger import LEDGER_VERSION_FLOAT, LEDGER_VERSION_LOT100
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
    execution_backend, ledger_executor, ledger_version = resolve_backend_tags(args.use_bq_ledger, args.use_float_ledger)
    plan = {
        "entrypoint": "backtest_report",
        "execution_backend": execution_backend,
        "ledger_version": ledger_version,
        "ledger_executor": ledger_executor,
        "lot_size": None if ledger_version == LEDGER_VERSION_FLOAT else args.lot_size,
        "min_buy_lot": None if ledger_version == LEDGER_VERSION_FLOAT else args.min_buy_lot,
        "project": config.project,
        "region": config.region,
        "experiment": experiment.to_params(),
        "search_id": args.search_id,
        "use_python_ledger": not args.use_bq_ledger,
        "run_report": not args.skip_report,
        "run_diagnosis": not args.skip_diagnosis,
        "run_tail_risk": not args.skip_tail_risk,
        "run_qa": not args.skip_qa,
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    client = make_client(config.project, config.region)
    sql_params = build_sql_params(experiment, args.force_replace, args.use_bq_ledger, args.use_float_ledger, args)
    job_ids = []
    for script in SQL_STEPS:
        job_ids.append({"script": script, "job_id": run_sql_script(client, script, sql_params)})
    if args.use_bq_ledger:
        job_ids.append({
            "script": "sql/ml/strategy1/08_run_backtest.sql",
            "job_id": run_sql_script(client, "sql/ml/strategy1/08_run_backtest.sql", sql_params),
        })
    else:
        ledger_result = run_ledger(client, build_ledger_params(config.project, experiment, args.force_replace, ledger_version, args))
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
        if ledger_version == LEDGER_VERSION_LOT100:
            job_ids.append({
                "script": "sql/ml/strategy1/23_qa_lot_aware_ledger_outputs.sql",
                "job_id": run_sql_script(client, "sql/ml/strategy1/23_qa_lot_aware_ledger_outputs.sql", sql_params),
            })
    if not args.skip_diagnosis:
        run_subprocess(diagnosis_command(config, experiment, args.skip_gcs_upload))
        if not args.skip_qa:
            job_ids.append({
                "script": "sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql",
                "job_id": run_sql_script(client, "sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql", sql_params),
            })
    if not args.skip_tail_risk:
        tail_risk_result = run_tail_risk_step(config, experiment, args.skip_gcs_upload, args.search_id)
        job_ids.append({"script": "scripts/strategy1/analyze_tail_risk.py", "result": tail_risk_result})
        if tail_risk_result["status"] == "succeeded" and not args.skip_qa:
            tail_risk_params = {**sql_params, **tail_risk_guard_sql_params(experiment)}
            job_ids.append({
                "script": "sql/ml/strategy1/20_qa_tail_risk_outputs.sql",
                "job_id": run_sql_script(client, "sql/ml/strategy1/20_qa_tail_risk_outputs.sql", tail_risk_params),
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
    parser.add_argument("--search-id", default=None)
    parser.add_argument("--manifest-resolved", default=None)
    parser.add_argument("--experiment-json", default=None, help="Base64 encoded resolved experiment payload")
    parser.add_argument("--force-replace", action="store_true")
    parser.add_argument("--skip-gcs-upload", action="store_true")
    parser.add_argument("--skip-report", action="store_true")
    parser.add_argument("--skip-diagnosis", action="store_true")
    parser.add_argument("--skip-tail-risk", action="store_true")
    parser.add_argument("--skip-qa", action="store_true")
    parser.add_argument("--use-bq-ledger", action="store_true", help="Fallback path for equivalence tests")
    parser.add_argument("--use-float-ledger", action="store_true", help="Explicit legacy/audit Python float-share ledger")
    parser.add_argument("--lot-size", type=int, default=100)
    parser.add_argument("--min-buy-lot", type=int, default=1)
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


def resolve_backend_tags(use_bq_ledger: bool, use_float_ledger: bool = False) -> tuple[str, str, str]:
    if use_bq_ledger and use_float_ledger:
        raise ValueError("--use-bq-ledger and --use-float-ledger are mutually exclusive")
    if use_bq_ledger:
        return "cloud_run_sklearn_bq_sql_ledger_v1", "bigquery_sql", LEDGER_VERSION_FLOAT
    if use_float_ledger:
        return "cloud_run_sklearn_ledger_v1_legacy_float", "cloud_run_python", LEDGER_VERSION_FLOAT
    return "cloud_run_sklearn_ledger_v1_lot100", "cloud_run_python", LEDGER_VERSION_LOT100


def build_sql_params(
    exp: Experiment,
    force_replace: bool,
    use_bq_ledger: bool,
    use_float_ledger: bool,
    args: argparse.Namespace,
) -> dict[str, object]:
    execution_backend, ledger_executor, ledger_version = resolve_backend_tags(use_bq_ledger, use_float_ledger)
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
        "p_feature_version": exp.feature_version,
        "p_tail_risk_profile_id": exp.tail_risk_profile_id,
        "p_market_state_version": exp.market_state_version,
        "p_execution_backend": execution_backend,
        "p_ledger_version": ledger_version,
        "p_ledger_executor": ledger_executor,
        "p_lot_size": None if ledger_version == LEDGER_VERSION_FLOAT else args.lot_size,
        "p_min_buy_lot": None if ledger_version == LEDGER_VERSION_FLOAT else args.min_buy_lot,
        "p_train_start": exp.train_start,
        "p_train_end": exp.train_end,
        "p_valid_start": exp.valid_start,
        "p_valid_end": exp.valid_end,
        "p_test_start": exp.test_start,
        "p_test_end": exp.test_end,
        "p_final_holdout_start": exp.final_holdout_start,
        "p_final_holdout_end": exp.final_holdout_end,
        "p_predict_start": exp.predict_start,
        "p_predict_end": exp.predict_end,
        "p_force_replace": force_replace,
    }


def build_ledger_params(
    project: str,
    exp: Experiment,
    force_replace: bool,
    ledger_version: str,
    args: argparse.Namespace,
) -> LedgerParams:
    return LedgerParams(
        project=project,
        run_id=exp.run_id,
        backtest_id=exp.backtest_id or f"bt_{exp.run_id}",
        predict_start=exp.predict_start,
        predict_end=exp.predict_end,
        ledger_version=ledger_version,
        lot_size=args.lot_size,
        min_buy_lot=args.min_buy_lot,
        force_replace=force_replace,
        tail_risk_profile_id=exp.tail_risk_profile_id,
        market_state_version=exp.market_state_version,
    )


def report_command(config, exp: Experiment, skip_gcs_upload: bool) -> list[str]:
    cmd = [
        sys.executable, "scripts/strategy1/render_report.py",
        "--project", config.project,
        "--run-id", exp.run_id,
        "--prediction-run-id", exp.prediction_run_id,
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
        "--run-id", exp.run_id,
        "--prediction-run-id", exp.prediction_run_id,
        "--backtest-id", exp.backtest_id,
        "--artifact-base-uri", config.artifact_base_uri,
        "--local-mirror-root", "reports/strategy1",
        "--p-target-holdings", str(exp.target_holdings),
        "--p-label-horizon", str(exp.label_horizon),
    ]
    if skip_gcs_upload:
        cmd.append("--skip-gcs-upload")
    return cmd


def tail_risk_command(config, exp: Experiment, skip_gcs_upload: bool, search_id: str | None) -> list[str]:
    cmd = [
        sys.executable, "scripts/strategy1/analyze_tail_risk.py",
        "--project", config.project,
        "--region", config.region,
        "--run-id", exp.run_id,
        "--prediction-run-id", exp.prediction_run_id,
        "--backtest-id", exp.backtest_id,
        "--feature-version", exp.feature_version,
        "--artifact-base-uri", config.artifact_base_uri,
        "--local-mirror-root", "reports/strategy1",
    ]
    search_id = search_id or exp.parent_experiment_id
    if search_id:
        cmd.extend(["--search-id", search_id])
    if skip_gcs_upload:
        cmd.append("--skip-gcs-upload")
    return cmd


def tail_risk_local_dir(exp: Experiment) -> Path:
    return (
        Path("reports/strategy1")
        / "ml_pv_clf_v0"
        / f"run_id={exp.run_id}"
        / f"backtest_id={exp.backtest_id}"
        / "tail_risk"
    )


def tail_risk_guard_sql_params(exp: Experiment) -> dict[str, str | None]:
    guard_path = tail_risk_local_dir(exp) / "ads_readonly_guard.json"
    if not guard_path.exists():
        raise FileNotFoundError(f"tail risk guard missing: {guard_path}")
    guard = json.loads(guard_path.read_text(encoding="utf-8"))
    post = guard.get("post") or {}
    return {
        "p_expected_summary_hash": post.get("summary_hash"),
        "p_expected_nav_hash": post.get("nav_hash"),
    }


def run_subprocess(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def run_tail_risk_step(config, exp: Experiment, skip_gcs_upload: bool, search_id: str | None) -> dict[str, object]:
    cmd = tail_risk_command(config, exp, skip_gcs_upload, search_id)
    proc = subprocess.run(cmd, check=False, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="")
    if proc.returncode == 0:
        return {"status": "succeeded", "command": cmd}

    combined_output = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
    if "ADS read-only guard failed" in combined_output:
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr)

    failure_dir = tail_risk_local_dir(exp)
    failure_dir.mkdir(parents=True, exist_ok=True)
    failure_path = failure_dir / "tail_risk_failure.json"
    failure = {
        "status": "failed_soft",
        "returncode": proc.returncode,
        "command": cmd,
        "stdout_tail": tail_text(proc.stdout),
        "stderr_tail": tail_text(proc.stderr),
    }
    failure_path.write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "warning",
                "tail_risk_status": "failed_soft",
                "failure_path": str(failure_path),
                "message": "tail-risk diagnostics failed after core report/QA; continuing without 20_qa_tail_risk_outputs.sql",
            },
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )
    return {"status": "failed_soft", "returncode": proc.returncode, "failure_path": str(failure_path)}


def tail_text(value: str | None, max_chars: int = 4000) -> str:
    if not value:
        return ""
    return value[-max_chars:]


if __name__ == "__main__":
    raise SystemExit(main())
