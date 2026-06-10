#!/usr/bin/env python3
"""Generate Strategy 1 annual rolling selection payloads.

This entrypoint implements the P0 resolved-payload layer from
`PRD_20260610_04_策略1年度滚动执行工程化.md`. It does not replace the existing
Cloud Run job modules; it builds year-by-year `experiment-json` payloads,
matrix URIs and gcloud commands from the frozen annual rolling candidate config.
"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists() and str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scripts.strategy1_cloudrun import __version__
from scripts.strategy1_cloudrun.bq_io import json_dumps_strict
from scripts.strategy1_cloudrun.config import (
    Experiment,
    add_common_args,
    apply_cli_overrides,
    experiment_to_b64,
    load_runner_config,
)
from scripts.strategy1_cloudrun.dataset_roles import output_dataset_role_cli_args
from scripts.strategy1_cloudrun.training_panel import build_training_panel_params
from quant_ashare.strategy1.pipeline_control import (
    build_task_fanout_steps,
    gcloud_execute_command,
)
from scripts.strategy1_cloudrun.task_fanout import (
    candidate_grid_hash,
    default_matrix_id,
    matrix_artifact_uri,
)


DEFAULT_CONFIG_PATH = "configs/strategy1/annual_rolling_lgbm_regression_v0.yml"
DEFAULT_CANDIDATE_SET_ID = "strategy1_annual_rolling_lgbm_regression_11_v0"
DEFAULT_FEATURE_SET_ID = "strategy1_pv_fin_risk_v0_20260606"
DEFAULT_AS_OF_DATE = "2026-06-09"
DEFAULT_STAGE_ID = "annual_rolling_selection"
DEFAULT_EXPERIMENT_GROUP = "strategy1_annual_rolling_selection"
DEFAULT_RESUME_POLICY_ID = "cloudrun_lot100_resume_v1"

FIRST_TRADING_DAY_BY_YEAR = {
    2015: "2015-04-01",
    2016: "2016-01-04",
    2017: "2017-01-03",
    2018: "2018-01-02",
    2019: "2019-01-02",
    2020: "2020-01-02",
    2021: "2021-01-04",
    2022: "2022-01-04",
    2023: "2023-01-03",
    2024: "2024-01-02",
    2025: "2025-01-02",
    2026: "2026-01-05",
}

LAST_TRADING_DAY_BY_YEAR = {
    2015: "2015-12-31",
    2016: "2016-12-30",
    2017: "2017-12-29",
    2018: "2018-12-28",
    2019: "2019-12-31",
    2020: "2020-12-31",
    2021: "2021-12-31",
    2022: "2022-12-30",
    2023: "2023-12-29",
    2024: "2024-12-31",
    2025: "2025-12-31",
}


def main() -> int:
    args = parse_args()
    config = apply_cli_overrides(load_runner_config(args.config), args)
    validate_config(config, args)
    as_of = parse_iso_date(args.as_of_date)
    version = args.run_version or f"v{datetime.now().strftime('%Y%m%d')}_01"
    years = list(range(args.start_year, args.end_year + 1))
    if not years:
        raise SystemExit("--start-year/--end-year produced an empty range")

    experiments = [
        build_year_experiment(
            backtest_year=year,
            args=args,
            version=version,
            as_of=as_of,
            continuous_anchor_start=actual_first_trading_day(args.start_year),
        )
        for year in years
    ]
    continuous_backtest_id = continuous_backtest_id_for(
        start_year=args.start_year,
        end_year=args.end_year,
        target_holdings=args.target_holdings,
        max_single_weight=args.max_single_weight,
        version=version,
    )

    plan = {
        "entrypoint": "annual_rolling_selection_orchestrator",
        "runner_version": __version__,
        "status": "dry_run" if args.dry_run else "planned_not_executed",
        "project": config.project,
        "region": config.region,
        "output_dataset_role": config.output_dataset_role,
        "config": args.config,
        "manifest": args.manifest,
        "candidate_set_id": args.candidate_set_id,
        "candidate_count": len(config.candidate_grid),
        "candidate_grid_hash": candidate_grid_hash(config),
        "candidate_ids": [str(item["candidate_id"]) for item in config.candidate_grid],
        "b26_diagnostic_reference": None if args.skip_b26_diagnostic_reference else b26_reference_plan(args),
        "start_year": args.start_year,
        "end_year": args.end_year,
        "as_of_date": args.as_of_date,
        "target_holdings": args.target_holdings,
        "max_single_weight": args.max_single_weight,
        "rebalance_frequency": args.rebalance_frequency,
        "continuous_ledger": {
            "backtest_id": continuous_backtest_id,
            "prediction_run_ids": [final_refit_experiment(exp).prediction_run_id for exp in experiments],
            "prediction_merge_required": True,
            "fresh_segment_stitching_allowed": False,
            "resume_segment_allowed_if_qa_passed": True,
            "selected_candidate_id": None,
            "selected_candidate_source": "yearly final refit outputs",
        },
        "years": [
            year_plan(
                config=config,
                exp=exp,
                args=args,
                continuous_backtest_id=continuous_backtest_id,
            )
            for exp in experiments
        ],
    }
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_dumps_strict(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json_dumps_strict(plan, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0
    raise SystemExit(
        "non-dry-run annual rolling execution is not implemented in this P0 wrapper; "
        "run with --dry-run and execute the emitted Cloud Run commands explicitly"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategy 1 annual rolling selection payload generator")
    add_common_args(parser)
    parser.set_defaults(config=DEFAULT_CONFIG_PATH, manifest=DEFAULT_CONFIG_PATH)
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--as-of-date", default=DEFAULT_AS_OF_DATE)
    parser.add_argument("--run-version", default=None)
    parser.add_argument("--target-holdings", type=int, default=20)
    parser.add_argument("--max-single-weight", type=float, default=0.075)
    parser.add_argument("--rebalance-frequency", default="biweekly")
    parser.add_argument("--feature-set-id", default=DEFAULT_FEATURE_SET_ID)
    parser.add_argument("--feature-version", default="strategy1_pv_v0_20260601")
    parser.add_argument("--fin-feature-version", default="fin_default_v0_20260602")
    parser.add_argument("--market-state-version", default="market_state_v0_20260606")
    parser.add_argument("--tail-risk-profile-id", default="diagnostic_only")
    parser.add_argument("--candidate-set-id", default=DEFAULT_CANDIDATE_SET_ID)
    parser.add_argument("--candidate-parallelism", type=int, default=0)
    parser.add_argument("--force-replace", action="store_true")
    parser.add_argument("--skip-gcs-upload", action="store_true")
    parser.add_argument("--skip-diagnosis", action="store_true")
    parser.add_argument("--skip-qa", action="store_true")
    parser.add_argument("--include-yearly-backtest-commands", action="store_true")
    parser.add_argument("--skip-b26-diagnostic-reference", action="store_true")
    parser.add_argument("--output", default=None, help="Optional local path for resolved plan JSON")
    return parser.parse_args()


def validate_config(config, args: argparse.Namespace) -> None:
    if args.candidate_set_id != DEFAULT_CANDIDATE_SET_ID:
        raise ValueError(f"unsupported candidate_set_id: {args.candidate_set_id}")
    if len(config.candidate_grid) != 11:
        raise ValueError(
            f"{args.candidate_set_id} must contain exactly 11 candidates, got {len(config.candidate_grid)}"
        )
    families = {str(item.get("model_family") or "logistic_regression") for item in config.candidate_grid}
    if families != {"lightgbm_regression"}:
        raise ValueError(f"{args.candidate_set_id} must contain only lightgbm_regression candidates, got {sorted(families)}")
    if args.rebalance_frequency != "biweekly":
        raise ValueError("annual rolling P0 requires --rebalance-frequency=biweekly")
    if args.target_holdings <= 0:
        raise ValueError("--target-holdings must be positive")
    if args.max_single_weight <= 0:
        raise ValueError("--max-single-weight must be positive")


def build_year_experiment(
    *,
    backtest_year: int,
    args: argparse.Namespace,
    version: str,
    as_of: date,
    continuous_anchor_start: str,
) -> Experiment:
    selection_train_start_year = backtest_year - 6
    selection_train_end_year = backtest_year - 2
    valid_year = backtest_year - 1
    final_refit_start_year = backtest_year - 5
    final_refit_end_year = backtest_year - 1
    weight_code = max_weight_code(args.max_single_weight)
    run_id = (
        f"s1_annual_roll_y{backtest_year}_"
        f"train{selection_train_start_year}_{selection_train_end_year}_"
        f"valid{valid_year}_n{args.target_holdings}_w{weight_code}_{version}"
    )
    experiment_id = (
        f"annual_roll_y{backtest_year}_"
        f"train{selection_train_start_year}_{selection_train_end_year}_"
        f"valid{valid_year}_n{args.target_holdings}_w{weight_code}_{version}"
    )
    backtest_id = (
        f"bt_s1_annual_roll_y{backtest_year}_"
        f"train{selection_train_start_year}_{selection_train_end_year}_"
        f"valid{valid_year}_n{args.target_holdings}_w{weight_code}_{version}"
    )
    selection_train_start = (
        "2015-04-01"
        if selection_train_start_year == 2015
        else actual_first_trading_day(selection_train_start_year)
    )
    backtest_end = bounded_year_end(backtest_year, as_of)
    selection_train_end = label_safe_year_end(selection_train_end_year, 5)
    valid_start = actual_first_trading_day(valid_year)
    valid_end = label_safe_year_end(valid_year, 5)
    backtest_start = actual_first_trading_day(backtest_year)
    final_refit_start = actual_first_trading_day(final_refit_start_year)
    final_refit_end = label_safe_year_end(final_refit_end_year, 5)
    return Experiment(
        experiment_id=experiment_id,
        run_id=run_id,
        backtest_id=backtest_id,
        prediction_run_id=run_id,
        stage_id=DEFAULT_STAGE_ID,
        experiment_group=DEFAULT_EXPERIMENT_GROUP,
        baseline_experiment_id="strategy1_annual_rolling_selection_p0",
        parent_experiment_id=None,
        parent_run_id=None,
        rebalance_frequency=args.rebalance_frequency,
        target_holdings=args.target_holdings,
        max_single_weight=args.max_single_weight,
        label_horizon=5,
        horizon_natural_frequency="weekly",
        initial_state_mode="fresh",
        parent_backtest_id=None,
        state_as_of_date=None,
        resume_policy_id=DEFAULT_RESUME_POLICY_ID,
        rebalance_anchor_start=continuous_anchor_start,
        feature_set_id=args.feature_set_id,
        feature_version=args.feature_version,
        fin_feature_version=args.fin_feature_version,
        tail_risk_profile_id=args.tail_risk_profile_id,
        market_state_version=args.market_state_version,
        requires_retrain=True,
        status="planned",
        train_start=selection_train_start,
        train_end=selection_train_end,
        valid_start=valid_start,
        valid_end=valid_end,
        test_start=backtest_start,
        test_end=backtest_end,
        final_holdout_start=None,
        final_holdout_end=None,
        predict_start=backtest_start,
        predict_end=backtest_end,
        raw={
            "selection_train_start_year": selection_train_start_year,
            "selection_train_end_year": selection_train_end_year,
            "valid_year": valid_year,
            "nominal_selection_train_start": "2015-04-01" if selection_train_start_year == 2015 else f"{selection_train_start_year}-01-01",
            "nominal_selection_train_end": f"{selection_train_end_year}-12-31",
            "actual_selection_train_start": selection_train_start,
            "actual_selection_train_end": selection_train_end,
            "nominal_valid_start": f"{valid_year}-01-01",
            "nominal_valid_end": f"{valid_year}-12-31",
            "actual_valid_start": valid_start,
            "actual_valid_end": valid_end,
            "final_refit_train_start": final_refit_start,
            "final_refit_train_end": final_refit_end,
            "nominal_final_refit_train_start": f"{final_refit_start_year}-01-01",
            "nominal_final_refit_train_end": f"{final_refit_end_year}-12-31",
            "actual_final_refit_train_start": final_refit_start,
            "actual_final_refit_train_end": final_refit_end,
            "nominal_backtest_start": f"{backtest_year}-01-01",
            "nominal_backtest_end": args.as_of_date if backtest_year == as_of.year else f"{backtest_year}-12-31",
            "actual_backtest_start": backtest_start,
            "actual_backtest_end": backtest_end,
            "backtest_year": backtest_year,
        },
    )


def year_plan(*, config, exp: Experiment, args: argparse.Namespace, continuous_backtest_id: str) -> dict[str, Any]:
    matrix_id = default_matrix_id(config, exp)
    matrix_uri = matrix_artifact_uri(config, exp, matrix_id)
    refit_exp = final_refit_experiment(exp)
    selection_commands = command_plan(config=config, exp=exp, args=args, include_backtest=args.include_yearly_backtest_commands)
    return {
        "backtest_year": int(exp.raw["backtest_year"]),
        "experiment": exp.to_params(),
        "experiment_json": experiment_to_b64(exp),
        "refit_experiment": refit_exp.to_params(),
        "refit_experiment_json": experiment_to_b64(refit_exp),
        "matrix_id": matrix_id,
        "matrix_uri": matrix_uri,
        "selected_candidate_id": None,
        "selected_candidate_source": "select_register_predict output",
        "window_contract": {
            key: value
            for key, value in exp.raw.items()
            if key.startswith("nominal_") or key.startswith("actual_")
        },
        "final_refit": {
            "experiment_id": refit_exp.experiment_id,
            "run_id": refit_exp.run_id,
            "prediction_run_id": refit_exp.prediction_run_id,
            "backtest_id": refit_exp.backtest_id,
            "source_run_id": exp.run_id,
            "source_panel_run_id": exp.run_id,
            "train_start": exp.raw["final_refit_train_start"],
            "train_end": exp.raw["final_refit_train_end"],
            "predict_start": refit_exp.predict_start,
            "predict_end": refit_exp.predict_end,
            "selected_candidate_required": True,
            "status": "executable_after_candidate_selection",
        },
        "single_year_backtest": {
            "backtest_id": refit_exp.backtest_id,
            "diagnostic_only": True,
            "official_continuous_backtest_id": continuous_backtest_id,
        },
        "commands": selection_commands,
    }


def command_plan(*, config, exp: Experiment, args: argparse.Namespace, include_backtest: bool) -> list[dict[str, Any]]:
    common_flags = [
        f"--project={config.project}",
        f"--region={config.region}",
        f"--config={args.config}",
        f"--manifest={args.manifest}",
        *output_dataset_role_cli_args(config.output_dataset_role, equals=True),
        f"--experiment-id={exp.experiment_id}",
        f"--experiment-json={experiment_to_b64(exp)}",
    ]
    if args.force_replace:
        common_flags.append("--force-replace")
    if args.skip_gcs_upload:
        common_flags.append("--skip-gcs-upload")
    task_args = SimpleNamespace(
        config=args.config,
        manifest=args.manifest,
        candidate_parallelism=args.candidate_parallelism,
        candidate_parallelism_from_cli=args.candidate_parallelism not in (None, 0),
    )
    refit_exp = final_refit_experiment(exp)
    steps = [training_panel_step(config, exp, args)]
    steps.extend(build_task_fanout_steps(config, exp, task_args, common_flags))
    refit_flags = [
        f"--project={config.project}",
        f"--region={config.region}",
        f"--config={args.config}",
        f"--manifest={args.manifest}",
        *output_dataset_role_cli_args(config.output_dataset_role, equals=True),
        f"--experiment-json={experiment_to_b64(refit_exp)}",
        f"--source-run-id={exp.run_id}",
        f"--source-panel-run-id={exp.run_id}",
        f"--refit-train-start={refit_exp.train_start}",
        f"--refit-train-end={refit_exp.train_end}",
    ]
    if args.force_replace:
        refit_flags.append("--force-replace")
    if args.skip_gcs_upload:
        refit_flags.append("--skip-gcs-upload")
    steps.append(SimpleNamespace(
        step_id="cloudrun_refit_register_predict",
        display_name="Cloud Run final refit/register/predict",
        job_name=config.train_predict_job,
        command=gcloud_execute_command(
            config.project,
            config.region,
            config.train_predict_job,
            "quant_ashare.strategy1.refit_register_predict",
            refit_flags,
        ),
    ))
    if include_backtest:
        backtest_flags = [
            f"--project={config.project}",
            f"--region={config.region}",
            f"--config={args.config}",
            f"--manifest={args.manifest}",
            *output_dataset_role_cli_args(config.output_dataset_role, equals=True),
            f"--experiment-id={refit_exp.experiment_id}",
            f"--experiment-json={experiment_to_b64(refit_exp)}",
            f"--run-id={refit_exp.run_id}",
            f"--prediction-run-id={refit_exp.prediction_run_id}",
            f"--backtest-id={refit_exp.backtest_id}",
            "--skip-diagnosis",
            "--skip-tail-risk",
            "--skip-qa",
        ]
        steps.append(SimpleNamespace(
            step_id="cloudrun_backtest_report",
            display_name="Cloud Run yearly diagnostic backtest/report",
            job_name=config.backtest_report_job,
            command=gcloud_execute_command(
                config.project,
                config.region,
                config.backtest_report_job,
                "quant_ashare.strategy1.backtest_report",
                backtest_flags,
            ),
        ))
    return [
        {
            "step_id": step.step_id,
            "display_name": step.display_name,
            "job_name": step.job_name,
            "command": step.command,
            **({"sql_step": step.sql_step, "params": step.params} if getattr(step, "sql_step", None) else {}),
        }
        for step in steps
    ]


def final_refit_run_id(exp: Experiment) -> str:
    return f"{exp.run_id}__refit01"


def final_refit_backtest_id(exp: Experiment) -> str | None:
    if not exp.backtest_id:
        return None
    return f"{exp.backtest_id}__refit01"


def final_refit_experiment(exp: Experiment) -> Experiment:
    refit_train_start = str(exp.raw.get("final_refit_train_start") or exp.train_start)
    refit_train_end = str(exp.raw.get("final_refit_train_end") or exp.train_end)
    raw = dict(exp.raw)
    raw.update({
        "source_run_id": exp.run_id,
        "source_panel_run_id": exp.run_id,
        "selection_run_id": exp.run_id,
        "selection_experiment_id": exp.experiment_id,
        "selection_backtest_id": exp.backtest_id,
        "selection_prediction_run_id": exp.prediction_run_id,
        "final_refit_train_start": refit_train_start,
        "final_refit_train_end": refit_train_end,
        "refit": True,
    })
    return dataclasses.replace(
        exp,
        experiment_id=f"{exp.experiment_id}__final_refit",
        run_id=final_refit_run_id(exp),
        backtest_id=final_refit_backtest_id(exp),
        prediction_run_id=final_refit_run_id(exp),
        parent_experiment_id=exp.experiment_id,
        parent_run_id=exp.run_id,
        requires_retrain=True,
        status="planned",
        train_start=refit_train_start,
        train_end=refit_train_end,
        valid_start=refit_train_start,
        valid_end=refit_train_end,
        raw=raw,
    )


def training_panel_step(config, exp: Experiment, args: argparse.Namespace) -> SimpleNamespace:
    params = build_training_panel_params(exp, force_replace=args.force_replace)
    encoded = base64.urlsafe_b64encode(
        json_dumps_strict(params, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).decode("ascii")
    return SimpleNamespace(
        step_id="build_training_panel",
        display_name="Build annual rolling training panel",
        job_name=None,
        sql_step=config.training_panel_step,
        params=params,
        command=[
            sys.executable,
            "-m",
            "quant_ashare.strategy1.sql_runner",
            f"--project={config.project}",
            f"--region={config.region}",
            f"--step={config.training_panel_step}",
            f"--params-json-b64={encoded}",
            *output_dataset_role_cli_args(config.output_dataset_role, equals=True),
        ],
    )


def continuous_backtest_id_for(
    *,
    start_year: int,
    end_year: int,
    target_holdings: int,
    max_single_weight: float,
    version: str,
) -> str:
    return (
        f"bt_s1_annual_roll_continuous_{start_year}_{end_year}_"
        f"n{target_holdings}_w{max_weight_code(max_single_weight)}_{version}"
    )


def b26_reference_plan(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "reference_id": "b26_baseline_binary_ref",
        "status": "diagnostic_only_reference_not_scheduled",
        "participates_in_candidate_ranking": False,
        "participates_in_selected_candidate_id": False,
        "participates_in_acceptance": False,
        "target_holdings": args.target_holdings,
        "max_single_weight": args.max_single_weight,
    }


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def actual_first_trading_day(year: int) -> str:
    try:
        return FIRST_TRADING_DAY_BY_YEAR[year]
    except KeyError as exc:
        raise ValueError(f"missing first trading day mapping for year {year}") from exc


def actual_last_trading_day(year: int) -> str:
    try:
        return LAST_TRADING_DAY_BY_YEAR[year]
    except KeyError as exc:
        raise ValueError(f"missing last trading day mapping for year {year}") from exc


def bounded_year_end(year: int, as_of: date) -> str:
    if year == as_of.year:
        return as_of.isoformat()
    if year > as_of.year:
        raise ValueError(f"backtest year {year} is after as_of_date {as_of.isoformat()}")
    return actual_last_trading_day(year)


def label_safe_year_end(year: int, label_horizon: int) -> str:
    end = parse_iso_date(actual_last_trading_day(year))
    return subtract_weekdays(end, label_horizon).isoformat()


def subtract_weekdays(value: date, count: int) -> date:
    """Subtract weekday count from year-end label windows.

    This helper is intentionally limited to December year-end windows used by
    the annual rolling PRD. A real trading-calendar lookup is required before
    reusing it for windows that may cross Chinese market holidays.
    """
    if value.month != 12:
        raise ValueError("subtract_weekdays is only valid for December year-end label windows")
    current = value
    remaining = count
    while remaining > 0:
        current -= timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def max_weight_code(value: float) -> str:
    return f"{int(round(value * 1000)):03d}"


if __name__ == "__main__":
    raise SystemExit(main())
