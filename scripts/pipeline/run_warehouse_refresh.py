#!/usr/bin/env python3
"""Plan and trigger warehouse backfill / QA runs.

The script is intentionally conservative:
- default mode only prints a plan;
- --execute is required before it calls Composer;
- --resume skips exact windows that already have a success or running
  ashare_warehouse_window_refresh pipeline_run row.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any


PROJECT_ID = "data-aquarium"
COMPOSER_ENVIRONMENT = "ashare-composer"
COMPOSER_LOCATION = "asia-east2"
BQ_LOCATION = "asia-east2"
WAREHOUSE_DAG_ID = "ashare_warehouse_window_refresh"
TERMINAL_STATUSES = {"success", "failed", "partial"}


@dataclass(frozen=True)
class PlannedRun:
    dag_id: str
    run_id: str
    conf: dict[str, Any]
    date_from: str
    date_to: str
    warehouse_mode: str
    skip_reason: str = ""


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid YYYY-MM-DD date: {value}") from exc


def _yyyymmdd(value: str) -> str:
    return value.replace("-", "")


def _run_id_token(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _date_chunks(start: date, end: date, chunk_days: int) -> list[tuple[date, date]]:
    if start > end:
        raise ValueError("date_from must be <= date_to")
    if chunk_days <= 0:
        raise ValueError("chunk_days must be positive")

    chunks: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def _composer_trigger_command(
    *,
    project: str,
    location: str,
    environment: str,
    run: PlannedRun,
) -> list[str]:
    return [
        "gcloud",
        "composer",
        "environments",
        "run",
        environment,
        f"--project={project}",
        f"--location={location}",
        "dags",
        "--",
        "trigger",
        run.dag_id,
        "--conf",
        json.dumps(run.conf, ensure_ascii=False, separators=(",", ":")),
        "--run-id",
        run.run_id,
    ]


def _bq_query_json(project: str, location: str, query: str) -> list[dict[str, Any]]:
    command = [
        "bq",
        f"--project_id={project}",
        f"--location={location}",
        "query",
        "--quiet",
        "--format=json",
        "--use_legacy_sql=false",
        query,
    ]
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    output = completed.stdout.strip()
    if not output:
        return []
    return json.loads(output)


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _resume_status_by_window(
    *,
    project: str,
    location: str,
    runs: list[PlannedRun],
) -> dict[tuple[str, str, str], str]:
    if not runs:
        return {}

    windows = sorted({(r.warehouse_mode, r.date_from, r.date_to) for r in runs})
    predicates = [
        "("
        f"warehouse_mode = {_sql_string(mode)} "
        f"AND COALESCE(date_from, business_date, '') = {_sql_string(start)} "
        f"AND COALESCE(date_to, business_date, '') = {_sql_string(end)}"
        ")"
        for mode, start, end in windows
    ]
    query = f"""
WITH ranked AS (
  SELECT
    warehouse_mode,
    COALESCE(date_from, business_date, '') AS date_from,
    COALESCE(date_to, business_date, '') AS date_to,
    status,
    started_at,
    ROW_NUMBER() OVER (
      PARTITION BY warehouse_mode, COALESCE(date_from, business_date, ''), COALESCE(date_to, business_date, '')
      ORDER BY started_at DESC
    ) AS rn
  FROM `{project}.ashare_meta.pipeline_run`
  WHERE dag_id = '{WAREHOUSE_DAG_ID}'
    AND ({' OR '.join(predicates)})
)
SELECT warehouse_mode, date_from, date_to, status
FROM ranked
WHERE rn = 1
"""
    rows = _bq_query_json(project, location, query)
    return {
        (row["warehouse_mode"], row["date_from"], row["date_to"]): row["status"]
        for row in rows
    }


def _query_run_status(project: str, location: str, run_id: str) -> dict[str, Any] | None:
    query = f"""
SELECT
  pipeline_run_id,
  dag_id,
  warehouse_mode,
  status,
  started_at,
  finished_at,
  error_summary
FROM `{project}.ashare_meta.pipeline_run`
WHERE pipeline_run_id = {_sql_string(run_id)}
ORDER BY started_at DESC
LIMIT 1
"""
    rows = _bq_query_json(project, location, query)
    return rows[0] if rows else None


def _status_for_prefix(project: str, location: str, run_id_prefix: str, limit: int) -> list[dict[str, Any]]:
    query = f"""
SELECT
  pipeline_run_id,
  dag_id,
  business_date,
  date_from,
  date_to,
  warehouse_mode,
  run_label,
  status,
  started_at,
  finished_at,
  error_summary
FROM `{project}.ashare_meta.pipeline_run`
WHERE STARTS_WITH(pipeline_run_id, {_sql_string(run_id_prefix)})
ORDER BY started_at DESC
LIMIT {int(limit)}
"""
    return _bq_query_json(project, location, query)


def _print_plan(
    *,
    runs: list[PlannedRun],
    project: str,
    location: str,
    environment: str,
) -> None:
    for index, run in enumerate(runs, start=1):
        prefix = "SKIP" if run.skip_reason else "RUN "
        print(f"{prefix} {index:03d} {run.run_id} {run.date_from}..{run.date_to} mode={run.warehouse_mode}")
        if run.skip_reason:
            print(f"      reason: {run.skip_reason}")
            continue
        command = _composer_trigger_command(
            project=project,
            location=location,
            environment=environment,
            run=run,
        )
        print(f"      {shlex.join(command)}")


def _trigger_run(
    *,
    run: PlannedRun,
    project: str,
    location: str,
    environment: str,
) -> None:
    command = _composer_trigger_command(
        project=project,
        location=location,
        environment=environment,
        run=run,
    )
    subprocess.run(command, check=True)


def _wait_for_run(
    *,
    project: str,
    location: str,
    run_id: str,
    timeout_seconds: int,
    poll_seconds: int,
) -> str:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        row = _query_run_status(project, location, run_id)
        status = str(row.get("status")) if row else "not_found"
        print(f"poll {run_id}: {status}")
        if status in TERMINAL_STATUSES:
            return status
        time.sleep(poll_seconds)
    raise TimeoutError(f"timed out waiting for {run_id}")


def _apply_resume(
    *,
    runs: list[PlannedRun],
    project: str,
    location: str,
    resume: bool,
) -> list[PlannedRun]:
    if not resume:
        return runs

    status_by_window = _resume_status_by_window(project=project, location=location, runs=runs)
    updated: list[PlannedRun] = []
    for run in runs:
        status = status_by_window.get((run.warehouse_mode, run.date_from, run.date_to))
        if status in {"success", "running"}:
            updated.append(
                PlannedRun(
                    dag_id=run.dag_id,
                    run_id=run.run_id,
                    conf=run.conf,
                    date_from=run.date_from,
                    date_to=run.date_to,
                    warehouse_mode=run.warehouse_mode,
                    skip_reason=f"existing exact-window pipeline_run status={status}",
                )
            )
        else:
            updated.append(run)
    return updated


def build_backfill_runs(args: argparse.Namespace) -> list[PlannedRun]:
    run_id_prefix = args.run_id_prefix or f"manual_warehouse_backfill_{_utc_stamp()}"
    chunks = _date_chunks(args.date_from, args.date_to, args.chunk_days)

    runs: list[PlannedRun] = []
    for chunk_start, chunk_end in chunks:
        start_text = chunk_start.isoformat()
        end_text = chunk_end.isoformat()
        run_id = (
            f"{_run_id_token(run_id_prefix)}_"
            f"{_yyyymmdd(start_text)}_{_yyyymmdd(end_text)}"
        )
        conf = {
            "pipeline_dry_run": args.pipeline_dry_run,
            "warehouse_mode": "backfill",
            "business_date": end_text,
            "date_from": start_text,
            "date_to": end_text,
            "run_label": args.run_label,
        }
        runs.append(
            PlannedRun(
                dag_id=WAREHOUSE_DAG_ID,
                run_id=run_id,
                conf=conf,
                date_from=start_text,
                date_to=end_text,
                warehouse_mode="backfill",
            )
        )
    return runs


def build_qa_only_runs(args: argparse.Namespace) -> list[PlannedRun]:
    business_date = args.business_date.isoformat()
    run_id_prefix = args.run_id_prefix or f"manual_warehouse_qa_only_{_utc_stamp()}"
    run_id = f"{_run_id_token(run_id_prefix)}_{_yyyymmdd(business_date)}"
    conf = {
        "warehouse_mode": "qa_only",
        "business_date": business_date,
        "pipeline_dry_run": args.pipeline_dry_run,
        "run_label": args.run_label,
    }
    return [
        PlannedRun(
            dag_id=WAREHOUSE_DAG_ID,
            run_id=run_id,
            conf=conf,
            date_from=business_date,
            date_to=business_date,
            warehouse_mode="qa_only",
        )
    ]


def _execute_plan(args: argparse.Namespace, runs: list[PlannedRun]) -> int:
    executable = [run for run in runs if not run.skip_reason]
    _print_plan(
        runs=runs,
        project=args.project,
        location=args.composer_location,
        environment=args.environment,
    )

    if not args.execute:
        print("\nPlan only. Re-run with --execute to trigger Composer.")
        return 0

    for run in executable:
        print(f"\ntrigger {run.run_id}")
        _trigger_run(
            run=run,
            project=args.project,
            location=args.composer_location,
            environment=args.environment,
        )
        if args.wait:
            status = _wait_for_run(
                project=args.project,
                location=args.bq_location,
                run_id=run.run_id,
                timeout_seconds=args.wait_timeout_seconds,
                poll_seconds=args.poll_seconds,
            )
            if status != "success" and args.fail_fast:
                return 2

    return 0


def cmd_backfill(args: argparse.Namespace) -> int:
    runs = build_backfill_runs(args)
    runs = _apply_resume(
        runs=runs,
        project=args.project,
        location=args.bq_location,
        resume=args.resume,
    )
    return _execute_plan(args, runs)


def cmd_qa_only(args: argparse.Namespace) -> int:
    runs = build_qa_only_runs(args)
    runs = _apply_resume(
        runs=runs,
        project=args.project,
        location=args.bq_location,
        resume=args.resume,
    )
    return _execute_plan(args, runs)


def cmd_status(args: argparse.Namespace) -> int:
    rows = _status_for_prefix(args.project, args.bq_location, args.run_id_prefix, args.limit)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
        return 0
    if not rows:
        print("No pipeline_run rows matched.")
        return 0
    for row in rows:
        print(
            "{pipeline_run_id}\t{status}\t{warehouse_mode}\t{date_from}->{date_to}\t{started_at}\t{finished_at}".format(
                **{key: row.get(key, "") for key in (
                    "pipeline_run_id",
                    "status",
                    "warehouse_mode",
                    "date_from",
                    "date_to",
                    "started_at",
                    "finished_at",
                )}
            )
        )
    return 0


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", default=PROJECT_ID, help=f"GCP project (default: {PROJECT_ID})")
    parser.add_argument("--environment", default=COMPOSER_ENVIRONMENT, help=f"Composer environment (default: {COMPOSER_ENVIRONMENT})")
    parser.add_argument("--composer-location", default=COMPOSER_LOCATION, help=f"Composer location (default: {COMPOSER_LOCATION})")
    parser.add_argument("--bq-location", default=BQ_LOCATION, help=f"BigQuery location (default: {BQ_LOCATION})")


def add_trigger_args(parser: argparse.ArgumentParser) -> None:
    add_common_args(parser)
    parser.add_argument("--execute", action="store_true", help="Actually trigger Composer DAG runs. Default is plan-only.")
    parser.add_argument("--resume", action="store_true", help="Skip exact windows that already have success or running pipeline_run rows.")
    parser.add_argument("--pipeline-dry-run", action="store_true", help="Pass pipeline_dry_run=true to the DAG. Default is false for production backfill.")
    parser.add_argument("--run-id-prefix", help="Run id prefix. Default includes a UTC timestamp.")
    parser.add_argument("--run-label", default="manual_warehouse_refresh", help="DAG run_label.")
    parser.add_argument("--wait", action="store_true", help="Poll ashare_meta.pipeline_run after each trigger.")
    parser.add_argument("--wait-timeout-seconds", type=int, default=7200, help="Per-run wait timeout.")
    parser.add_argument("--poll-seconds", type=int, default=30, help="Polling interval when --wait is used.")
    parser.add_argument("--fail-fast", action="store_true", help="With --wait, stop on first non-success terminal run.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Warehouse refresh backfill / resume helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backfill = subparsers.add_parser("backfill", help="Plan or trigger warehouse backfill chunks.")
    add_trigger_args(backfill)
    backfill.add_argument("--date-from", required=True, type=_parse_date, help="Backfill start date, YYYY-MM-DD.")
    backfill.add_argument("--date-to", required=True, type=_parse_date, help="Backfill end date, YYYY-MM-DD.")
    backfill.add_argument("--chunk-days", type=int, default=5, help="Calendar days per Composer run (default: 5).")
    backfill.set_defaults(func=cmd_backfill)

    qa_only = subparsers.add_parser("qa-only", help="Plan or trigger a qa_only warehouse run.")
    add_trigger_args(qa_only)
    qa_only.add_argument("--business-date", required=True, type=_parse_date, help="Business date, YYYY-MM-DD.")
    qa_only.set_defaults(func=cmd_qa_only)

    status = subparsers.add_parser("status", help="Show pipeline_run rows by run_id prefix.")
    add_common_args(status)
    status.add_argument("--run-id-prefix", required=True, help="pipeline_run_id prefix to query.")
    status.add_argument("--limit", type=int, default=50, help="Maximum rows to print.")
    status.add_argument("--json", action="store_true", help="Print raw JSON rows.")
    status.set_defaults(func=cmd_status)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except subprocess.CalledProcessError as exc:
        print(f"command failed: {shlex.join(exc.cmd)}", file=sys.stderr)
        if exc.stdout:
            print(exc.stdout, file=sys.stderr)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        return exc.returncode or 1
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
