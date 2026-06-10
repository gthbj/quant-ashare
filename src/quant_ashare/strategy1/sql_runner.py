"""Run Strategy 1 BigQuery SQL steps with explicit parameters."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any

from google.cloud import bigquery

from quant_ashare.strategy1.catalog import load_step_catalog, resolve_step_path
from quant_ashare.strategy1.dataset_roles import (
    DEFAULT_OUTPUT_DATASET_ROLE,
    OUTPUT_DATASET_ROLE_CHOICES,
    allow_future_research,
)
from quant_ashare.strategy1.sql_render import (
    render_sql_file,
    render_sql_step as render_step_sql,
    render_value,
)


def render_sql(
    script_path: str | Path,
    params: dict[str, Any],
    *,
    dataset_role: str = DEFAULT_OUTPUT_DATASET_ROLE,
    allow_future_research: bool = False,
) -> str:
    """Compatibility renderer for path callers.

    New active runners should call ``render_sql_step`` / ``run_sql_step`` so the
    catalog can enforce required parameters.
    """

    return render_sql_file(
        script_path,
        params,
        strict=False,
        dataset_role=dataset_role,
        allow_future_research=allow_future_research,
    )


def run_sql_script(
    client: bigquery.Client,
    script_path: str | Path,
    params: dict[str, Any],
    *,
    dry_run: bool = False,
    dataset_role: str = DEFAULT_OUTPUT_DATASET_ROLE,
    allow_future_research: bool = False,
) -> str:
    sql = render_sql_file(
        script_path,
        params,
        strict=False,
        dataset_role=dataset_role,
        allow_future_research=allow_future_research,
    )
    job_config = bigquery.QueryJobConfig(dry_run=dry_run, use_query_cache=False)
    job = client.query(sql, job_config=job_config)
    if dry_run:
        return job.job_id
    job.result()
    return job.job_id


def render_sql_step(
    step: str,
    params: dict[str, Any],
    *,
    dataset_role: str = DEFAULT_OUTPUT_DATASET_ROLE,
    allow_future_research: bool = False,
) -> str:
    return render_step_sql(
        step,
        params,
        dataset_role=dataset_role,
        allow_future_research=allow_future_research,
    )


def resolve_sql_step_path(step: str) -> Path:
    catalog = load_step_catalog()
    return resolve_step_path(step, catalog)


def run_sql_step(
    client: bigquery.Client,
    step: str,
    params: dict[str, Any],
    *,
    dry_run: bool = False,
    dataset_role: str = DEFAULT_OUTPUT_DATASET_ROLE,
    allow_future_research: bool = False,
) -> str:
    sql = render_step_sql(
        step,
        params,
        dataset_role=dataset_role,
        allow_future_research=allow_future_research,
    )
    job_config = bigquery.QueryJobConfig(dry_run=dry_run, use_query_cache=False)
    job = client.query(sql, job_config=job_config)
    if dry_run:
        return job.job_id
    job.result()
    return job.job_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a cataloged Strategy 1 SQL step")
    parser.add_argument("--project", default="data-aquarium")
    parser.add_argument("--region", default="asia-east2")
    parser.add_argument("--step", required=True)
    parser.add_argument("--params-json-b64", required=True)
    parser.add_argument(
        "--output-dataset-role",
        choices=OUTPUT_DATASET_ROLE_CHOICES,
        default=DEFAULT_OUTPUT_DATASET_ROLE,
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    params = json.loads(base64.urlsafe_b64decode(args.params_json_b64.encode("ascii")).decode("utf-8"))
    client = bigquery.Client(project=args.project, location=args.region)
    job_id = run_sql_step(
        client,
        args.step,
        params,
        dry_run=args.dry_run,
        dataset_role=args.output_dataset_role,
        allow_future_research=allow_future_research(args.output_dataset_role),
    )
    print(json.dumps(
        {
            "status": "dry_run" if args.dry_run else "succeeded",
            "step": args.step,
            "job_id": job_id,
            "output_dataset_role": args.output_dataset_role,
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
