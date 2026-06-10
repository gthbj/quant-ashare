#!/usr/bin/env python3
"""Promote owner-approved Strategy1 research outputs into ADS."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from google.cloud import bigquery

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists() and str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from quant_ashare.strategy1.promotion import (  # noqa: E402
    DEFAULT_LOCATION,
    DEFAULT_PROJECT,
    DEFAULT_PROMOTION_ROLES,
    PROMOTION_TABLE_SPECS,
    PromotionRequest,
    build_promotion_plan,
    run_promotion,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--location", default=DEFAULT_LOCATION)
    parser.add_argument("--promotion-id", required=True)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-backtest-id", required=True)
    parser.add_argument("--source-model-id", required=True)
    parser.add_argument("--window-start", required=True, help="Inclusive partition/date window start")
    parser.add_argument("--window-end", required=True, help="Inclusive partition/date window end")
    parser.add_argument("--approval-ref", required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--approved-at")
    parser.add_argument("--acceptance-contract-version", required=True)
    parser.add_argument("--acceptance-contract-sha256", required=True)
    parser.add_argument("--source-artifact-uri")
    parser.add_argument("--source-git-commit", default=current_git_commit())
    parser.add_argument(
        "--target-role",
        action="append",
        choices=sorted(PROMOTION_TABLE_SPECS),
        help=(
            "Promotion table role to copy. Repeat to override the default publishable set. "
            "Use training_panel explicitly only when owner wants the large panel copied."
        ),
    )
    parser.add_argument(
        "--include-training-panel",
        action="store_true",
        help="Add research_ml_training_panel_daily to the default promotion target set.",
    )
    parser.add_argument(
        "--allow-unaccepted",
        action="store_true",
        help="Bypass the accepted-source guard. This should only be used with explicit owner approval.",
    )
    parser.add_argument("--force-replace", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Build and print the promotion plan without executing")
    parser.add_argument("--print-sql", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request = request_from_args(args)
    plan = build_promotion_plan(request)
    if args.dry_run or args.print_sql:
        print(json.dumps(plan_summary(plan), ensure_ascii=False, indent=2, default=str))
        if args.print_sql:
            print("\n--- SQL ---")
            print(plan.sql)
        if args.dry_run:
            return 0

    client = bigquery.Client(project=args.project, location=args.location)
    job = run_promotion(client, request)
    print(json.dumps({
        "promotion_id": request.promotion_id,
        "job_id": job.job_id,
        "location": job.location,
        "target_ads_tables": plan.target_ads_tables,
    }, ensure_ascii=False, indent=2, default=str))
    return 0


def request_from_args(args: argparse.Namespace) -> PromotionRequest:
    target_roles = tuple(args.target_role) if args.target_role else tuple(DEFAULT_PROMOTION_ROLES)
    if args.include_training_panel and "training_panel" not in target_roles:
        target_roles = ("training_panel", *target_roles)
    return PromotionRequest(
        project=args.project,
        promotion_id=args.promotion_id,
        source_run_id=args.source_run_id,
        source_backtest_id=args.source_backtest_id,
        source_model_id=args.source_model_id,
        window_start=args.window_start,
        window_end=args.window_end,
        approval_ref=args.approval_ref,
        approved_by=args.approved_by,
        approved_at=args.approved_at,
        acceptance_contract_version=args.acceptance_contract_version,
        acceptance_contract_sha256=args.acceptance_contract_sha256,
        source_artifact_uri=args.source_artifact_uri,
        source_git_commit=args.source_git_commit,
        target_roles=target_roles,
        allow_unaccepted=args.allow_unaccepted,
        force_replace=args.force_replace,
    )


def plan_summary(plan: Any) -> dict[str, Any]:
    params = {
        param.name: getattr(param, "values", getattr(param, "value", None))
        for param in plan.parameters
    }
    return {
        "promotion_id": plan.request.promotion_id,
        "project": plan.request.project,
        "source_run_id": plan.request.source_run_id,
        "source_backtest_id": plan.request.source_backtest_id,
        "source_model_id": plan.request.source_model_id,
        "window_start": plan.request.window_start,
        "window_end": plan.request.window_end,
        "target_roles": plan.request.target_roles,
        "target_ads_tables": plan.target_ads_tables,
        "allow_unaccepted": plan.request.allow_unaccepted,
        "force_replace": plan.request.force_replace,
        "query_parameters": params,
    }


def current_git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
