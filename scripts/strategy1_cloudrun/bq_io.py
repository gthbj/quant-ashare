"""BigQuery and GCS helpers for Strategy 1 Cloud Run runner."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
from google.cloud import bigquery, storage


ADS = "data-aquarium.ashare_ads"
META = "data-aquarium.ashare_meta"
LOCATION = "asia-east2"
RUN_SAFE_RE = re.compile(r"[^A-Za-z0-9_]")


def run_safe(value: str) -> str:
    return RUN_SAFE_RE.sub("_", value)


def make_client(project: str, location: str = LOCATION) -> bigquery.Client:
    return bigquery.Client(project=project, location=location)


def query_dataframe(client: bigquery.Client, sql: str, params: list[bigquery.ScalarQueryParameter]) -> pd.DataFrame:
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    return client.query(sql, job_config=job_config).result().to_dataframe(create_bqstorage_client=True)


def execute_query(client: bigquery.Client, sql: str, params: list[bigquery.ScalarQueryParameter] | None = None) -> None:
    job_config = bigquery.QueryJobConfig(query_parameters=params or [])
    client.query(sql, job_config=job_config).result()


def load_dataframe(
    client: bigquery.Client,
    frame: pd.DataFrame,
    table_id: str,
    *,
    write_disposition: str = "WRITE_APPEND",
) -> None:
    if frame.empty:
        return
    job_config = bigquery.LoadJobConfig(write_disposition=write_disposition)
    client.load_table_from_dataframe(frame, table_id, job_config=job_config).result()


def get_git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def parse_gs_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError(f"expected gs:// URI, got {uri!r}")
    rest = uri[5:]
    bucket, _, prefix = rest.partition("/")
    if not bucket:
        raise ValueError(f"missing bucket in URI {uri!r}")
    return bucket, prefix.rstrip("/")


def join_gs_uri(base_uri: str, *parts: str) -> str:
    return "/".join([base_uri.rstrip("/"), *[p.strip("/") for p in parts if p]])


def upload_directory_to_gcs(project: str, local_dir: Path, destination_uri: str) -> list[str]:
    bucket_name, prefix = parse_gs_uri(destination_uri)
    client = storage.Client(project=project)
    bucket = client.bucket(bucket_name)
    uploaded = []
    for path in local_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(local_dir).as_posix()
        blob_name = f"{prefix}/{rel}" if prefix else rel
        bucket.blob(blob_name).upload_from_filename(path)
        uploaded.append(f"gs://{bucket_name}/{blob_name}")
    return uploaded


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def env_container_image() -> str | None:
    return os.environ.get("K_REVISION") or os.environ.get("CONTAINER_IMAGE")
