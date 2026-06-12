#!/usr/bin/env python3
"""Generate Strategy 1 annual rolling selection payloads.

This entrypoint implements the P0 resolved-payload layer from
`PRD_20260610_04_策略1年度滚动执行工程化.md`. It does not replace the existing
Cloud Run job modules; it builds year-by-year `experiment-json` payloads,
matrix URIs and gcloud commands from the frozen annual rolling candidate config.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists() and str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scripts.strategy1_cloudrun import __version__
from scripts.strategy1_cloudrun.bq_io import json_dumps_strict
from scripts.strategy1_cloudrun.config import (
    add_common_args,
    apply_cli_overrides,
    load_runner_config,
)
from quant_ashare.strategy1.annual_rolling_plan import (
    DEFAULT_AS_OF_DATE,
    DEFAULT_CANDIDATE_SET_ID,
    DEFAULT_CONFIG_PATH,
    DEFAULT_FEATURE_SET_ID,
    DEFAULT_FINAL_REFIT_RUN_SUFFIX,
    FINAL_REFIT_MIN_TRAINING_DAY,
    actual_first_trading_day,
    b26_reference_plan,
    build_year_experiment,
    command_plan,
    continuous_backtest_id_for,
    final_refit_experiment,
    parse_iso_date,
    validate_config,
    year_plan,
)
from scripts.strategy1_cloudrun.task_fanout import candidate_grid_hash


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
            final_refit_min_training_day=args.final_refit_min_training_day,
            final_refit_run_suffix=args.final_refit_run_suffix,
            true_five_year_refit=args.true_five_year_refit,
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
        "execution_scope": "refit_only" if args.emit_refit_only else "full_selection_refit_plan",
        "true_five_year_refit": bool(args.true_five_year_refit),
        "final_refit_min_training_day": args.final_refit_min_training_day,
        "final_refit_run_suffix": args.final_refit_run_suffix,
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
    parser.add_argument(
        "--final-refit-min-training-day",
        default=FINAL_REFIT_MIN_TRAINING_DAY,
        help=(
            "Earliest allowed annual final-refit train start. "
            "Use --true-five-year-refit after PRD_06 historical coverage repair to disable the clamp."
        ),
    )
    parser.add_argument(
        "--true-five-year-refit",
        action="store_true",
        help="Disable the current 2019-04-03 refit floor and require a non-default refit run suffix.",
    )
    parser.add_argument(
        "--final-refit-run-suffix",
        default=DEFAULT_FINAL_REFIT_RUN_SUFFIX,
        help="Suffix for annual final-refit run/backtest ids, e.g. __refit01 or __true5y01.",
    )
    parser.add_argument(
        "--emit-refit-only",
        action="store_true",
        help="Emit only build_refit_training_panel and cloudrun_refit_register_predict steps for each year.",
    )
    parser.add_argument("--output", default=None, help="Optional local path for resolved plan JSON")
    args = parser.parse_args()
    if args.true_five_year_refit:
        if args.final_refit_run_suffix == DEFAULT_FINAL_REFIT_RUN_SUFFIX:
            parser.error("--true-five-year-refit requires an explicit non-default --final-refit-run-suffix")
        args.final_refit_min_training_day = None
    if args.final_refit_run_suffix and not str(args.final_refit_run_suffix).startswith("__"):
        parser.error("--final-refit-run-suffix must start with '__'")
    if args.emit_refit_only and args.include_yearly_backtest_commands:
        parser.error("--emit-refit-only cannot be combined with --include-yearly-backtest-commands")
    return args


if __name__ == "__main__":
    raise SystemExit(main())
