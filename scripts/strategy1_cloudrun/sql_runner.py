"""Run existing Strategy 1 BigQuery SQL scripts with explicit parameters."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

from google.cloud import bigquery


DECLARE_RE = re.compile(
    r"(?im)^(\s*DECLARE\s+(?P<name>p_[A-Za-z0-9_]+)\s+"
    r"(?P<type>STRING|INT64|FLOAT64|BOOL|DATE|TIMESTAMP)\s+DEFAULT\s+)(?P<value>[^;]*)(;)"
)


def render_sql(script_path: str | Path, params: dict[str, Any]) -> str:
    sql = Path(script_path).read_text(encoding="utf-8")
    seen: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        if name not in params:
            return match.group(0)
        seen.add(name)
        rendered = render_value(params[name], match.group("type"))
        return f"{match.group(1)}{rendered}{match.group(5)}"

    rendered = DECLARE_RE.sub(replace, sql)
    return rendered


def run_sql_script(
    client: bigquery.Client,
    script_path: str | Path,
    params: dict[str, Any],
    *,
    dry_run: bool = False,
) -> str:
    sql = render_sql(script_path, params)
    job_config = bigquery.QueryJobConfig(dry_run=dry_run, use_query_cache=False)
    job = client.query(sql, job_config=job_config)
    if dry_run:
        return job.job_id
    job.result()
    return job.job_id


def render_value(value: Any, sql_type: str) -> str:
    if value is None:
        return "NULL"
    if sql_type == "STRING":
        escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"
    if sql_type == "DATE":
        if isinstance(value, (dt.datetime, dt.date)):
            value = value.isoformat()[:10]
        return f"DATE '{value}'"
    if sql_type == "TIMESTAMP":
        if isinstance(value, dt.datetime):
            value = value.isoformat()
        return f"TIMESTAMP '{value}'"
    if sql_type == "BOOL":
        return "TRUE" if bool(value) else "FALSE"
    if sql_type in {"INT64", "FLOAT64"}:
        return str(value)
    raise ValueError(f"unsupported SQL type: {sql_type}")
