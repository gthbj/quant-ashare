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
LABEL_SAFE_RE = re.compile(r"[^a-z0-9_-]")


def run_safe(value: str) -> str:
    return RUN_SAFE_RE.sub("_", value)


def make_client(project: str, location: str = LOCATION) -> bigquery.Client:
    return bigquery.Client(project=project, location=location)


def bq_label_value(value: str | None) -> str:
    value = (value or "none").lower()
    value = LABEL_SAFE_RE.sub("_", value)[:63].strip("_-")
    return value or "none"


def normalize_bq_labels(labels: dict[str, str | None] | None) -> dict[str, str]:
    return {bq_label_value(k): bq_label_value(v) for k, v in (labels or {}).items()}


def query_dataframe(
    client: bigquery.Client,
    sql: str,
    params: list[bigquery.ScalarQueryParameter],
    *,
    labels: dict[str, str | None] | None = None,
) -> pd.DataFrame:
    frame, _ = query_dataframe_with_job(client, sql, params, labels=labels)
    return frame


def query_dataframe_with_job(
    client: bigquery.Client,
    sql: str,
    params: list[bigquery.ScalarQueryParameter],
    *,
    labels: dict[str, str | None] | None = None,
) -> tuple[pd.DataFrame, bigquery.QueryJob]:
    job_config = bigquery.QueryJobConfig(query_parameters=params, labels=normalize_bq_labels(labels))
    job = client.query(sql, job_config=job_config)
    result = job.result()
    return result.to_dataframe(create_bqstorage_client=True), job


def execute_query(
    client: bigquery.Client,
    sql: str,
    params: list[bigquery.ScalarQueryParameter] | None = None,
    *,
    labels: dict[str, str | None] | None = None,
) -> None:
    job_config = bigquery.QueryJobConfig(query_parameters=params or [], labels=normalize_bq_labels(labels))
    client.query(sql, job_config=job_config).result()


def load_dataframe(
    client: bigquery.Client,
    frame: pd.DataFrame,
    table_id: str,
    *,
    write_disposition: str = "WRITE_APPEND",
    labels: dict[str, str | None] | None = None,
) -> None:
    if frame.empty:
        return
    job_config = bigquery.LoadJobConfig(
        write_disposition=write_disposition,
        labels=normalize_bq_labels(labels),
    )
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


def download_gcs_prefix(project: str, source_uri: str, local_dir: Path) -> list[Path]:
    bucket_name, prefix = parse_gs_uri(source_uri)
    client = storage.Client(project=project)
    bucket = client.bucket(bucket_name)
    downloaded = []
    for blob in bucket.list_blobs(prefix=prefix.rstrip("/") + "/"):
        if blob.name.endswith("/"):
            continue
        rel = blob.name[len(prefix.rstrip("/") + "/"):]
        path = local_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(path)
        downloaded.append(path)
    return downloaded


def download_gcs_file(project: str, source_uri: str, local_path: Path) -> Path:
    bucket_name, blob_name = parse_gs_uri(source_uri)
    client = storage.Client(project=project)
    bucket = client.bucket(bucket_name)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    bucket.blob(blob_name).download_to_filename(local_path)
    return local_path


def job_audit_dict(job: bigquery.QueryJob) -> dict[str, Any]:
    referenced = []
    for table in job.referenced_tables or []:
        referenced.append(f"{table.project}.{table.dataset_id}.{table.table_id}")
    return {
        "job_id": job.job_id,
        "location": job.location,
        "labels": dict(job.labels or {}),
        "total_bytes_processed": int(job.total_bytes_processed or 0),
        "total_bytes_billed": int(job.total_bytes_billed or 0),
        "referenced_tables": referenced,
        "started": job.started.isoformat() if job.started else None,
        "ended": job.ended.isoformat() if job.ended else None,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def env_container_image() -> str | None:
    return os.environ.get("K_REVISION") or os.environ.get("CONTAINER_IMAGE")
