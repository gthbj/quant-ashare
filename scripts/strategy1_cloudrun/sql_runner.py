"""Run Strategy 1 BigQuery SQL steps with explicit parameters."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

from google.cloud import bigquery

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists() and str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from quant_ashare.strategy1.catalog import load_step_catalog, resolve_step_path
from quant_ashare.strategy1.sql_render import (
    render_sql_file,
    render_sql_step as render_step_sql,
    render_value,
)


def render_sql(script_path: str | Path, params: dict[str, Any]) -> str:
    """Compatibility renderer for path callers.

    New active runners should call ``render_sql_step`` / ``run_sql_step`` so the
    catalog can enforce required parameters.
    """

    return render_sql_file(script_path, params, strict=False)


def run_sql_script(
    client: bigquery.Client,
    script_path: str | Path,
    params: dict[str, Any],
    *,
    dry_run: bool = False,
) -> str:
    sql = render_sql_file(script_path, params, strict=False)
    job_config = bigquery.QueryJobConfig(dry_run=dry_run, use_query_cache=False)
    job = client.query(sql, job_config=job_config)
    if dry_run:
        return job.job_id
    job.result()
    return job.job_id


def render_sql_step(step: str, params: dict[str, Any]) -> str:
    return render_step_sql(step, params)


def resolve_sql_step_path(step: str) -> Path:
    catalog = load_step_catalog()
    return resolve_step_path(step, catalog)


def run_sql_step(
    client: bigquery.Client,
    step: str,
    params: dict[str, Any],
    *,
    dry_run: bool = False,
) -> str:
    sql = render_step_sql(step, params)
    job_config = bigquery.QueryJobConfig(dry_run=dry_run, use_query_cache=False)
    job = client.query(sql, job_config=job_config)
    if dry_run:
        return job.job_id
    job.result()
    return job.job_id
