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
from quant_ashare.strategy1.ledger import LedgerParams, run_ledger
from quant_ashare.strategy1.ledger import (
    LEDGER_VERSION_FLOAT,
    LEDGER_VERSION_LOT100,
    LEDGER_VERSION_TOPDOWN_LOT100,
    RESUME_POLICY_CLOUDRUN_LOT100,
    RESUME_POLICY_CLOUDRUN_TOPDOWN_LOT100,
    cash_redistribution_id_for_ledger_version,
    CORPORATE_ACTIONS_CASH_DIV_AND_SPLIT,
    CORPORATE_ACTIONS_NONE,
    DIVIDEND_TAX_FLAT_10PCT,
)
from quant_ashare.strategy1.dataset_roles import allow_future_research, output_dataset_role_cli_args
from quant_ashare.strategy1.sql_runner import resolve_sql_step_path, run_sql_step


SQL_STEPS = [
    "build_candidates",
    "build_portfolio_targets",
    "build_order_plan",
]


def main() -> int:
    args = parse_args()
    config = apply_cli_overrides(load_runner_config(args.config), args)
    experiment = resolve_experiment(args)
    execution_backend, ledger_executor, ledger_version = resolve_backend_tags(
        args.use_float_ledger,
        args.use_topdown_ledger,
    )
    plan = {
        "entrypoint": "backtest_report",
        "execution_backend": execution_backend,
        "ledger_version": ledger_version,
        "ledger_executor": ledger_executor,
        "lot_size": None if ledger_version == LEDGER_VERSION_FLOAT else args.lot_size,
        "min_buy_lot": None if ledger_version == LEDGER_VERSION_FLOAT else args.min_buy_lot,
        "position_floor_count": args.position_floor_count if ledger_version == LEDGER_VERSION_TOPDOWN_LOT100 else None,
        "min_position_weight": topdown_min_position_weight(args) if ledger_version == LEDGER_VERSION_TOPDOWN_LOT100 else None,
        "walk_depth": args.walk_depth if ledger_version == LEDGER_VERSION_TOPDOWN_LOT100 else None,
        "corporate_actions": experiment.corporate_actions,
        "dividend_tax_mode": experiment.dividend_tax_mode,
        "project": config.project,
        "region": config.region,
        "output_dataset_role": config.output_dataset_role,
        "experiment": experiment.to_params(),
        "search_id": args.search_id,
        "use_python_ledger": True,
        "run_report": not args.skip_report,
        "run_diagnosis": not args.skip_diagnosis,
        "run_tail_risk": not args.skip_tail_risk,
        "run_qa": not args.skip_qa,
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    client = make_client(config.project, config.region)
    sql_params = build_sql_params(experiment, args.force_replace, args.use_float_ledger, args)
    job_ids = []
    for step in SQL_STEPS:
        job_ids.append(run_catalog_step(client, step, sql_params, config.output_dataset_role))
    ledger_result = run_ledger(client, build_ledger_params(config, experiment, args.force_replace, ledger_version, args))
    job_ids.append({"script": "python_ledger_exec_v1", "result": ledger_result})
    job_ids.append(run_catalog_step(client, "build_metrics_and_report_inputs", sql_params, config.output_dataset_role))
    if not args.skip_report:
        run_subprocess(report_command(config, experiment, args.skip_gcs_upload))
    if not args.skip_qa:
        job_ids.append(run_catalog_step(client, "qa_runner_outputs", sql_params, config.output_dataset_role))
        if ledger_version in {LEDGER_VERSION_LOT100, LEDGER_VERSION_TOPDOWN_LOT100}:
            job_ids.append(run_catalog_step(client, "qa_lot_aware_ledger_outputs", sql_params, config.output_dataset_role))
        if ledger_version == LEDGER_VERSION_TOPDOWN_LOT100:
            job_ids.append(run_catalog_step(client, "qa_topdown_construction_outputs", sql_params, config.output_dataset_role))
        job_ids.append(run_catalog_step(client, "qa_corporate_action_ledger_outputs", sql_params, config.output_dataset_role))
    if not args.skip_diagnosis:
        run_subprocess(diagnosis_command(config, experiment, args.skip_gcs_upload))
        if not args.skip_qa:
            job_ids.append(run_catalog_step(client, "qa_model_diagnosis_outputs", sql_params, config.output_dataset_role))
    if not args.skip_tail_risk:
        tail_risk_result = run_tail_risk_step(config, experiment, args.skip_gcs_upload, args.search_id)
        job_ids.append({"script": "scripts/strategy1/analyze_tail_risk.py", "result": tail_risk_result})
        if tail_risk_result["status"] == "succeeded" and not args.skip_qa:
            tail_risk_params = {**sql_params, **tail_risk_guard_sql_params(experiment)}
            job_ids.append(run_catalog_step(client, "qa_tail_risk_outputs", tail_risk_params, config.output_dataset_role))
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
    parser.add_argument("--use-float-ledger", action="store_true", help="Explicit legacy/audit Python float-share ledger")
    parser.add_argument("--use-topdown-ledger", action="store_true", help="Use ledger_exec_v2_lot100_topdown construction")
    parser.add_argument("--lot-size", type=int, default=100)
    parser.add_argument("--min-buy-lot", type=int, default=1)
    parser.add_argument("--position-floor-count", type=int, default=20)
    parser.add_argument("--min-position-weight", type=float, default=None)
    parser.add_argument("--walk-depth", type=int, default=50)
    parser.add_argument("--initial-state-mode", choices=["fresh", "resume_from_backtest"], default=None)
    parser.add_argument("--parent-backtest-id", default=None)
    parser.add_argument("--state-as-of-date", default=None)
    parser.add_argument("--resume-policy-id", default=None)
    parser.add_argument("--rebalance-anchor-start", default=None)
    parser.add_argument(
        "--corporate-actions",
        choices=[CORPORATE_ACTIONS_NONE, CORPORATE_ACTIONS_CASH_DIV_AND_SPLIT],
        default=None,
    )
    parser.add_argument("--dividend-tax-mode", choices=[DIVIDEND_TAX_FLAT_10PCT], default=None)
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
    for attr in (
        "run_id",
        "prediction_run_id",
        "backtest_id",
        "initial_state_mode",
        "parent_backtest_id",
        "state_as_of_date",
        "resume_policy_id",
        "rebalance_anchor_start",
        "corporate_actions",
        "dividend_tax_mode",
    ):
        value = getattr(args, attr)
        if value:
            replacements[attr] = value
    if replacements:
        import dataclasses
        exp = dataclasses.replace(exp, **replacements)
    if not exp.is_executable:
        raise ValueError(f"{exp.experiment_id} contains unresolved placeholders or blocked status")
    return exp


def resolve_backend_tags(use_float_ledger: bool = False, use_topdown_ledger: bool = False) -> tuple[str, str, str]:
    if use_float_ledger and use_topdown_ledger:
        raise ValueError("--use-float-ledger and --use-topdown-ledger are mutually exclusive")
    if use_float_ledger:
        return "cloud_run_sklearn_ledger_v1_legacy_float", "cloud_run_python", LEDGER_VERSION_FLOAT
    if use_topdown_ledger:
        return "cloud_run_sklearn_ledger_v2_lot100_topdown", "cloud_run_python", LEDGER_VERSION_TOPDOWN_LOT100
    return "cloud_run_sklearn_ledger_v1_lot100", "cloud_run_python", LEDGER_VERSION_LOT100


def build_sql_params(
    exp: Experiment,
    force_replace: bool,
    use_float_ledger: bool,
    args: argparse.Namespace,
) -> dict[str, object]:
    use_topdown_ledger = bool(getattr(args, "use_topdown_ledger", False))
    execution_backend, ledger_executor, ledger_version = resolve_backend_tags(use_float_ledger, use_topdown_ledger)
    resume_policy_id = effective_resume_policy_id(exp, ledger_version)
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
        "p_rebalance_anchor_start": exp.rebalance_anchor_start,
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
        "p_min_buy_shares": None if ledger_version == LEDGER_VERSION_FLOAT else args.lot_size * args.min_buy_lot,
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
        "p_initial_capital": 100000.0,
        "p_cost_profile_id": "cn_a_share_wanyi_no_min_slip5_v20260602",
        "p_commission_bps": 1.0,
        "p_min_commission_cny": 0.0,
        "p_stamp_tax_buy_bps": 0.0,
        "p_stamp_tax_sell_bps": 5.0,
        "p_slippage_buy_bps": 5.0,
        "p_slippage_sell_bps": 5.0,
        "p_cost_bps": 30.0,
        "p_benchmark": "000001.SH",
        "p_initial_state_mode": exp.initial_state_mode,
        "p_parent_backtest_id": exp.parent_backtest_id,
        "p_state_as_of_date": exp.state_as_of_date,
        "p_resume_policy_id": resume_policy_id,
        "p_position_floor_count": getattr(args, "position_floor_count", 20),
        "p_min_position_weight": topdown_min_position_weight(args),
        "p_walk_depth": getattr(args, "walk_depth", 50),
        "p_portfolio_construction_method": (
            "topdown_lot100_v2" if ledger_version == LEDGER_VERSION_TOPDOWN_LOT100 else "equal_weight_v1"
        ),
        "p_corporate_actions": exp.corporate_actions,
        "p_dividend_tax_mode": exp.dividend_tax_mode,
        "p_share_tolerance": 1e-6,
        "p_cash_tolerance_cny": 1.0,
        "p_nav_event_abs_return_ceiling": 0.25,
        "p_tail_risk_ret_20d_min": -0.30,
        "p_tail_risk_drawdown_20d_min": -0.30,
        "p_tail_risk_limit_down_days_20d_min": 2,
        "p_tail_risk_one_word_limit_days_20d_min": 1,
        "p_tail_risk_total_mv_min_cny": 30e8,
        "p_tail_risk_circ_mv_min_cny": 20e8,
        "p_force_replace": force_replace,
    }


def build_ledger_params(
    config,
    exp: Experiment,
    force_replace: bool,
    ledger_version: str,
    args: argparse.Namespace,
) -> LedgerParams:
    resume_policy_id = effective_resume_policy_id(exp, ledger_version)
    return LedgerParams(
        project=config.project,
        run_id=exp.run_id,
        backtest_id=exp.backtest_id or f"bt_{exp.run_id}",
        output_dataset_role=config.output_dataset_role,
        predict_start=exp.predict_start,
        predict_end=exp.predict_end,
        ledger_version=ledger_version,
        lot_size=args.lot_size,
        min_buy_lot=args.min_buy_lot,
        cash_redistribution=cash_redistribution_id_for_ledger_version(ledger_version),
        force_replace=force_replace,
        rebalance_frequency=exp.rebalance_frequency,
        target_holdings=exp.target_holdings,
        max_single_weight=exp.max_single_weight,
        label_horizon=exp.label_horizon,
        horizon_natural_frequency=exp.horizon_natural_frequency,
        initial_state_mode=exp.initial_state_mode,
        parent_backtest_id=exp.parent_backtest_id,
        state_as_of_date=exp.state_as_of_date,
        resume_policy_id=resume_policy_id,
        rebalance_anchor_start=exp.rebalance_anchor_start,
        corporate_actions=exp.corporate_actions,
        dividend_tax_mode=exp.dividend_tax_mode,
        tail_risk_profile_id=exp.tail_risk_profile_id,
        market_state_version=exp.market_state_version,
        position_floor_count=getattr(args, "position_floor_count", 20),
        min_position_weight=topdown_min_position_weight(args),
        walk_depth=getattr(args, "walk_depth", 50),
    )


def topdown_min_position_weight(args: argparse.Namespace) -> float:
    explicit = getattr(args, "min_position_weight", None)
    if explicit is not None:
        return float(explicit)
    return 1.0 / float(getattr(args, "position_floor_count", 20))


def effective_resume_policy_id(exp: Experiment, ledger_version: str) -> str:
    if ledger_version == LEDGER_VERSION_TOPDOWN_LOT100 and exp.resume_policy_id == RESUME_POLICY_CLOUDRUN_LOT100:
        return RESUME_POLICY_CLOUDRUN_TOPDOWN_LOT100
    return exp.resume_policy_id


def report_command(config, exp: Experiment, skip_gcs_upload: bool) -> list[str]:
    cmd = [
        sys.executable, "scripts/strategy1/render_report.py",
        "--project", config.project,
        "--run-id", exp.run_id,
        "--prediction-run-id", exp.prediction_run_id,
        "--backtest-id", exp.backtest_id,
        *output_dataset_role_cli_args(config.output_dataset_role),
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
        *output_dataset_role_cli_args(config.output_dataset_role),
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
        *output_dataset_role_cli_args(config.output_dataset_role),
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


def run_catalog_step(
    client,
    step: str,
    params: dict[str, object],
    output_dataset_role: str,
) -> dict[str, str]:
    return {
        "step": step,
        "script": str(resolve_sql_step_path(step)),
        "dataset_role": output_dataset_role,
        "job_id": run_sql_step(
            client,
            step,
            params,
            dataset_role=output_dataset_role,
            allow_future_research=allow_future_research(output_dataset_role),
        ),
    }


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
