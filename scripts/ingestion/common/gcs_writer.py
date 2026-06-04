"""GCS staging / publish 写入。"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pyarrow as pa
import pyarrow.parquet as pq

if TYPE_CHECKING:
    from google.cloud import storage

logger = logging.getLogger(__name__)


def write_parquet_to_gcs(
    rows: list[dict[str, Any]],
    schema: pa.Schema,
    bucket: str,
    prefix: str,
    ingestion_run_id: str,
    object_name: str = "data.parquet",
    staging_prefix: str = "_staging/",
    merge_existing: bool = False,
    dedupe_keys: list[str] | None = None,
) -> str:
    """将行数据写为 Parquet 到 GCS staging 路径，校验后 publish 到正式路径。

    流程：
    1. 可选读取正式 object，与新行合并并按主键去重。
    2. 写 staging object。
    3. 读取 staging object 做 schema 校验。
    4. publish 到正式 object。

    Returns: 正式 GCS URI
    """
    from scripts.ingestion.common.parquet_schema import cast_rows

    normalized_prefix = prefix.strip("/")
    final_object = f"{normalized_prefix}/{object_name}"
    staging_object = (
        f"{staging_prefix.strip('/')}/ingestion_run_id={ingestion_run_id}/"
        f"{normalized_prefix}/{object_name}"
    )

    from google.cloud import storage

    storage_client = storage.Client()
    gcs_bucket = storage_client.bucket(bucket)

    final_rows = rows
    if merge_existing:
        existing_rows = _read_existing_rows(gcs_bucket, final_object)
        if existing_rows:
            final_rows = _merge_rows(existing_rows, rows, dedupe_keys or [])

    table = cast_rows(final_rows, schema)

    fd, tmp_path = tempfile.mkstemp(suffix=".parquet")
    os.close(fd)
    try:
        pq.write_table(table, tmp_path)
        staging_blob = gcs_bucket.blob(staging_object)
        staging_blob.upload_from_filename(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass

    staged_table = _read_table_from_gcs(gcs_bucket, staging_object)
    if not staged_table.schema.equals(schema, check_metadata=False):
        gcs_bucket.blob(staging_object).delete()
        raise RuntimeError(
            f"Staged Parquet schema mismatch for gs://{bucket}/{staging_object}: "
            f"expected={schema}, actual={staged_table.schema}"
        )

    gcs_bucket.copy_blob(gcs_bucket.blob(staging_object), gcs_bucket, final_object)
    gcs_bucket.blob(staging_object).delete()
    return f"gs://{bucket}/{final_object}"


def read_schema_contract(contract_path: Path) -> dict[str, Any]:
    """读取 schema contract JSON。"""
    import json
    with open(contract_path) as f:
        return json.load(f)


def _read_existing_rows(bucket: "storage.Bucket", object_name: str) -> list[dict[str, Any]]:
    blob = bucket.blob(object_name)
    if not blob.exists():
        return []
    return _read_table_from_gcs(bucket, object_name).to_pylist()


def _read_table_from_gcs(bucket: "storage.Bucket", object_name: str) -> pa.Table:
    payload = bucket.blob(object_name).download_as_bytes()
    return pq.read_table(io.BytesIO(payload))


def _merge_rows(
    existing_rows: list[dict[str, Any]],
    new_rows: list[dict[str, Any]],
    dedupe_keys: list[str],
) -> list[dict[str, Any]]:
    if not dedupe_keys:
        return existing_rows + new_rows

    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in existing_rows + new_rows:
        key = tuple(row.get(field) for field in dedupe_keys)
        merged[key] = row
    return list(merged.values())
