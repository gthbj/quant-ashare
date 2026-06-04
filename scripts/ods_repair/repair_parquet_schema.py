#!/usr/bin/env python3
"""ODS Parquet Schema Repair Script.

Reads schema contracts from configs/ods_schema_contracts/*.yml, detects Parquet
schema mismatches against GCS files, casts fields to contract types, and
publishes repaired files with backup and manifest tracking.

Idempotent: skips files whose source schema already matches contract.
Backup write-once: never overwrites existing backup objects.

Usage:
    python scripts/ods_repair/repair_parquet_schema.py \
        --endpoint stk_limit \
        --run-id repair_20260603_01 \
        --partition-start 20190101 \
        [--dry-run] \
        [--manifest-path data_audit/reports/repair_manifest_<run_id>.csv]
"""

import argparse
import csv
import datetime
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import yaml
from google.cloud import bigquery, storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# IEEE-754 double precision threshold: 2^53
MAX_SAFE_INT_FLOAT64 = 2**53

GCS_BUCKET = "data-aquarium"
RAW_PREFIX = "a-share/tushare/raw_data"
STAGING_PREFIX = "a-share/tushare/repair_staging"
BACKUP_PREFIX = "a-share/tushare/repair_backup"


# ---------------------------------------------------------------------------
# Contract loading
# ---------------------------------------------------------------------------

def load_contract(contract_path: Path) -> Dict[str, Any]:
    with open(contract_path) as f:
        return yaml.safe_load(f)


def load_all_contracts(contracts_dir: Path) -> Dict[str, Dict[str, Any]]:
    contracts = {}
    for p in sorted(contracts_dir.glob("*.yml")):
        c = load_contract(p)
        contracts[c["endpoint"]] = c
    return contracts


def build_pyarrow_schema(contract: Dict[str, Any]) -> pa.Schema:
    type_map = {
        "string": pa.string(),
        "int64": pa.int64(),
        "float64": pa.float64(),
        "bool": pa.bool_(),
    }
    fields = []
    for f in contract["fields"]:
        pa_type = type_map[f["pyarrow_type"]]
        fields.append(pa.field(f["field_name"], pa_type, nullable=f.get("nullable", True)))
    return pa.schema(fields)


# ---------------------------------------------------------------------------
# GCS helpers
# ---------------------------------------------------------------------------

def parse_gcs_uri(uri: str) -> Tuple[str, str]:
    assert uri.startswith("gs://"), f"Not a GCS URI: {uri}"
    parts = uri[5:].split("/", 1)
    return parts[0], parts[1]


def list_gcs_parquet_files(client: storage.Client, prefix: str) -> List[str]:
    bucket = client.bucket(GCS_BUCKET)
    blobs = bucket.list_blobs(prefix=prefix)
    return [f"gs://{GCS_BUCKET}/{b.name}" for b in blobs if b.name.endswith(".parquet")]


def read_parquet_from_gcs(client: storage.Client, uri: str) -> pq.ParquetFile:
    bucket_name, blob_path = parse_gcs_uri(uri)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    data = blob.download_as_bytes()
    return pq.ParquetFile(pa.BufferReader(data))


def gcs_object_exists(client: storage.Client, uri: str) -> bool:
    bucket_name, blob_path = parse_gcs_uri(uri)
    bucket = client.bucket(bucket_name)
    return bucket.blob(blob_path).exists()


def upload_parquet_to_gcs(client: storage.Client, uri: str, table: pa.Table):
    bucket_name, blob_path = parse_gcs_uri(uri)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    buf = pa.BufferOutputStream()
    pq.write_table(table, buf, compression="snappy")
    blob.upload_from_string(buf.getvalue().to_pybytes())


def delete_gcs_object_if_exists(client: storage.Client, uri: str):
    bucket_name, blob_path = parse_gcs_uri(uri)
    blob = client.bucket(bucket_name).blob(blob_path)
    if blob.exists():
        blob.delete()
        logger.info(f"  Deleted staging object: {uri}")


def copy_gcs_object(client: storage.Client, src_uri: str, dst_uri: str):
    src_bucket, src_blob = parse_gcs_uri(src_uri)
    dst_bucket, dst_blob = parse_gcs_uri(dst_uri)
    src = client.bucket(src_bucket).blob(src_blob)
    client.bucket(dst_bucket).copy_blob(src, client.bucket(dst_bucket), dst_blob)


def copy_gcs_object_atomic(client: storage.Client, src_uri: str, dst_uri: str) -> bool:
    """Copy with if_generation_match=0 precondition: fails if dst already exists.
    Returns True on success, False if dst already existed."""
    src_bucket, src_blob = parse_gcs_uri(src_uri)
    dst_bucket, dst_blob = parse_gcs_uri(dst_uri)
    src = client.bucket(src_bucket).blob(src_blob)
    dst = client.bucket(dst_bucket).blob(dst_blob)
    try:
        client.bucket(dst_bucket).copy_blob(
            src, client.bucket(dst_bucket), dst_blob,
            if_generation_match=0,
        )
        return True
    except Exception as e:
        if "conditionNotMet" in str(e) or "412" in str(e):
            return False
        raise


def source_uri_hash(source_uri: str) -> str:
    """Stable short hash from source GCS blob path, for unique staging/backup paths."""
    _, blob_path = parse_gcs_uri(source_uri)
    return hashlib.sha256(blob_path.encode()).hexdigest()[:12]


def hive_partition_value_from_uri(uri: str, key: str) -> Optional[str]:
    _, blob_path = parse_gcs_uri(uri)
    prefix = f"{key}="
    for part in blob_path.split("/"):
        if part.startswith(prefix):
            return part.split("=", 1)[1]
    return None


def contract_gcs_prefix_to_blob_prefix(contract: Dict[str, Any]) -> str:
    prefix_uri = contract.get("gcs_prefix")
    if not prefix_uri:
        prefix_uri = f"gs://{GCS_BUCKET}/{RAW_PREFIX}/api={contract['endpoint']}/endpoint={contract['endpoint']}"
    bucket_name, blob_prefix = parse_gcs_uri(prefix_uri)
    if bucket_name != GCS_BUCKET:
        raise ValueError(f"Unsupported contract bucket {bucket_name}; expected {GCS_BUCKET}")
    return blob_prefix.rstrip("/") + "/"


# ---------------------------------------------------------------------------
# Schema comparison and casting
# ---------------------------------------------------------------------------

PYARROW_TYPE_MAP = {
    "string": pa.string(),
    "int64": pa.int64(),
    "float64": pa.float64(),
    "bool": pa.bool_(),
}


def detect_mismatches(
    actual_schema: pa.Schema,
    contract: Dict[str, Any],
) -> List[Dict[str, Any]]:
    mismatches = []
    contract_fields = {f["field_name"]: f for f in contract["fields"]}
    for i in range(len(actual_schema)):
        actual_field = actual_schema.field(i)
        name = actual_field.name
        if name in contract_fields:
            expected_type = PYARROW_TYPE_MAP[contract_fields[name]["pyarrow_type"]]
            if actual_field.type != expected_type:
                mismatches.append({
                    "field_name": name,
                    "actual_type": str(actual_field.type),
                    "expected_type": str(expected_type),
                    "policy": contract_fields[name]["repair_policy"],
                })
    return mismatches


def check_int_to_float_precision(table: pa.Table, field_name: str) -> Dict[str, Any]:
    col = table.column(field_name)
    non_null = col.drop_null()
    if len(non_null) == 0:
        return {"safe": True, "max_value": None, "reason": "all_null"}
    try:
        min_val = pc.min(non_null).as_py()
        max_val = pc.max(non_null).as_py()
    except Exception as e:
        return {
            "safe": False,
            "max_value": None,
            "reason": f"min_max_computation_failed: {e}",
        }
    values = [v for v in (min_val, max_val) if v is not None]
    if not values:
        return {"safe": True, "max_value": None, "reason": "all_null"}
    max_abs = max(abs(v) for v in values)
    if max_abs >= MAX_SAFE_INT_FLOAT64:
        return {"safe": False, "max_value": max_abs, "reason": f"|value| {max_abs} >= 2^53"}
    return {"safe": True, "max_value": max_abs, "reason": "within_safe_range"}


def cast_table_to_contract(
    table: pa.Table,
    contract: Dict[str, Any],
    mismatches: List[Dict[str, Any]],
) -> Tuple[pa.Table, List[Dict[str, Any]]]:
    precision_warnings = []
    mismatch_fields = {m["field_name"] for m in mismatches}
    contract_fields = {f["field_name"]: f for f in contract["fields"]}

    new_columns = []
    new_names = []
    for i in range(table.num_columns):
        col_name = table.column_names[i]
        col = table.column(i)
        if col_name in mismatch_fields:
            target_type = PYARROW_TYPE_MAP[contract_fields[col_name]["pyarrow_type"]]
            if pa.types.is_integer(col.type) and target_type == pa.float64():
                precision = check_int_to_float_precision(table, col_name)
                if not precision["safe"]:
                    precision_warnings.append({
                        "field_name": col_name,
                        "max_value": precision["max_value"],
                        "reason": precision["reason"],
                    })
                    logger.warning(
                        f"  Field {col_name}: INT->FLOAT64 precision risk "
                        f"(max={precision['max_value']}), skipping auto-cast"
                    )
                    new_columns.append(col)
                    new_names.append(col_name)
                    continue
            try:
                casted = col.cast(target_type)
                new_columns.append(casted)
                logger.info(f"  Cast {col_name}: {col.type} -> {target_type}")
            except Exception as e:
                logger.error(f"  Failed to cast {col_name}: {e}")
                new_columns.append(col)
                precision_warnings.append({
                    "field_name": col_name,
                    "max_value": None,
                    "reason": f"cast_failed: {e}",
                })
        else:
            new_columns.append(col)
        new_names.append(col_name)

    return pa.table(new_columns, names=new_names), precision_warnings


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

MANIFEST_FIELDS = [
    "run_id", "endpoint", "partition_date", "source_uri",
    "staging_uri", "backup_uri", "backup_status",
    "published_uri", "source_row_count", "staging_row_count",
    "source_schema", "target_schema", "null_count_before",
    "null_count_after", "status", "error_summary",
]


def load_existing_manifest(manifest_path: Path) -> Dict[str, Dict[str, str]]:
    entries = {}
    if manifest_path.exists():
        with open(manifest_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row["endpoint"], row["partition_date"], row["source_uri"])
                entries[key] = row
    return entries


def write_manifest_row(manifest_path: Path, row: Dict[str, str], write_header: bool):
    with open(manifest_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


# ---------------------------------------------------------------------------
# Per-file repair
# ---------------------------------------------------------------------------

def quote_bq_identifier(identifier: str) -> str:
    return f"`{identifier.replace('`', '``')}`"


def validate_staging_with_bigquery(
    bq_client: bigquery.Client,
    staging_uri: str,
    contract: Dict[str, Any],
    run_id: str,
    src_hash: str,
    expected_row_count: int,
    temp_dataset: str = "ashare_meta",
) -> List[str]:
    """Create a temp external table from staging URI with explicit contract schema,
    then run SELECT to verify BigQuery can read all business columns.
    Returns list of errors (empty = pass)."""
    errors = []
    endpoint = contract["endpoint"]
    temp_table_id = (
        f"{temp_dataset}._repair_val_{endpoint}_{run_id}_{src_hash}"
    )

    schema_fields = []
    for f in contract["fields"]:
        bq_type = f["bigquery_type"]
        schema_fields.append(bigquery.SchemaField(f["field_name"], bq_type, mode="NULLABLE"))

    ext_config = bigquery.ExternalConfig("PARQUET")
    ext_config.source_uris = [staging_uri]
    ext_config.schema = schema_fields

    table = bigquery.Table(temp_table_id)
    table.external_data_configuration = ext_config

    try:
        bq_client.delete_table(temp_table_id, not_found_ok=True)
        bq_client.create_table(table)
    except Exception as e:
        return [f"temp_table_create_failed: {e}"]

    business_cols = [f["field_name"] for f in contract["fields"]]
    col_exprs = [
        f"COUNTIF({quote_bq_identifier(c)} IS NULL OR {quote_bq_identifier(c)} IS NOT NULL) "
        f"AS {quote_bq_identifier(c + '_read_rows')}"
        for c in business_cols
    ]
    query = f"SELECT COUNT(*) AS total_rows, {', '.join(col_exprs)} FROM `{temp_table_id}`"

    try:
        result = bq_client.query(query).result()
        row = next(iter(result))
        total_rows = row["total_rows"]
        if total_rows != expected_row_count:
            errors.append(f"bq_row_count_mismatch: expected={expected_row_count} actual={total_rows}")
        for c in business_cols:
            read_rows = row[f"{c}_read_rows"]
            if read_rows != total_rows:
                errors.append(f"bq_col_readability_mismatch: {c} rows={read_rows} total={total_rows}")
    except Exception as e:
        errors.append(f"bq_query_failed: {e}")

    try:
        bq_client.delete_table(temp_table_id, not_found_ok=True)
    except Exception:
        pass

    return errors


def repair_file(
    client: storage.Client,
    bq_client: bigquery.Client,
    contract: Dict[str, Any],
    source_uri: str,
    run_id: str,
    endpoint: str,
    partition_date: str,
    dry_run: bool,
    existing_manifest: Dict[str, Dict[str, str]],
    manifest_path: Path,
    write_header: bool,
) -> bool:
    manifest_key = (endpoint, partition_date, source_uri)

    if manifest_key in existing_manifest:
        prev = existing_manifest[manifest_key]
        if prev["status"] == "ok":
            logger.info(f"  SKIP (already repaired): {source_uri}")
            return True

    src_hash = source_uri_hash(source_uri)
    api_partition = hive_partition_value_from_uri(source_uri, "api") or endpoint
    staging_uri = (
        f"gs://{GCS_BUCKET}/{STAGING_PREFIX}/run_id={run_id}"
        f"/api={api_partition}/endpoint={endpoint}/partition_date={partition_date}"
        f"/src_{src_hash}/data.parquet"
    )
    backup_uri = (
        f"gs://{GCS_BUCKET}/{BACKUP_PREFIX}/run_id={run_id}"
        f"/api={api_partition}/endpoint={endpoint}/partition_date={partition_date}"
        f"/src_{src_hash}/data.parquet"
    )

    row = {k: "" for k in MANIFEST_FIELDS}
    row.update({
        "run_id": run_id,
        "endpoint": endpoint,
        "partition_date": partition_date,
        "source_uri": source_uri,
        "staging_uri": staging_uri,
        "backup_uri": backup_uri,
    })

    try:
        pf = read_parquet_from_gcs(client, source_uri)
        table = pf.read()
    except Exception as e:
        row.update({"status": "read_failed", "error_summary": str(e)})
        write_manifest_row(manifest_path, row, write_header)
        logger.error(f"  READ FAILED: {source_uri}: {e}")
        return False

    source_row_count = table.num_rows
    row["source_row_count"] = str(source_row_count)
    row["source_schema"] = str(table.schema)

    contract_schema = build_pyarrow_schema(contract)
    row["target_schema"] = str(contract_schema)

    null_counts = {}
    for name in table.column_names:
        null_counts[name] = table.column(name).null_count
    row["null_count_before"] = json.dumps(null_counts)

    mismatches = detect_mismatches(table.schema, contract)

    if not mismatches:
        row.update({
            "status": "ok",
            "staging_row_count": str(source_row_count),
            "null_count_after": row["null_count_before"],
            "published_uri": source_uri,
            "backup_status": "skipped_schema_match",
        })
        write_manifest_row(manifest_path, row, write_header)
        logger.info(f"  OK (schema matches contract): {source_uri}")
        return True

    logger.info(f"  Found {len(mismatches)} mismatch(es):")
    for m in mismatches:
        logger.info(f"    {m['field_name']}: {m['actual_type']} -> {m['expected_type']}")

    if dry_run:
        row.update({"status": "dry_run_mismatch", "error_summary": json.dumps(mismatches)})
        write_manifest_row(manifest_path, row, write_header)
        logger.info(f"  DRY RUN: would repair {source_uri}")
        return True

    casted_table, precision_warnings = cast_table_to_contract(table, contract, mismatches)

    if precision_warnings:
        manual_fields = [w["field_name"] for w in precision_warnings]
        row.update({
            "status": "manual_review",
            "error_summary": f"precision_risk: {json.dumps(precision_warnings)}",
        })
        write_manifest_row(manifest_path, row, write_header)
        logger.warning(f"  MANUAL REVIEW needed for fields: {manual_fields}")
        return False

    new_null_counts = {}
    for name in casted_table.column_names:
        new_null_counts[name] = casted_table.column(name).null_count
    row["null_count_after"] = json.dumps(new_null_counts)

    null_mismatch = False
    for name in table.column_names:
        before = null_counts.get(name, 0)
        after = new_null_counts.get(name, 0)
        if before != after:
            logger.warning(f"  Null count changed for {name}: {before} -> {after}")
            null_mismatch = True

    if casted_table.num_rows != source_row_count:
        row.update({
            "status": "error",
            "error_summary": f"row_count_mismatch: {source_row_count} -> {casted_table.num_rows}",
        })
        write_manifest_row(manifest_path, row, write_header)
        logger.error(f"  Row count mismatch after cast!")
        return False

    if null_mismatch:
        row.update({
            "status": "null_count_changed",
            "error_summary": f"null_count_changed: before={json.dumps(null_counts)} after={json.dumps(new_null_counts)}",
        })
        write_manifest_row(manifest_path, row, write_header)
        logger.error("  Null count changed after cast; blocking publish")
        return False

    row["staging_row_count"] = str(casted_table.num_rows)

    try:
        logger.info(f"  Writing staging: {staging_uri}")
        upload_parquet_to_gcs(client, staging_uri, casted_table)
    except Exception as e:
        row.update({"status": "staging_write_failed", "error_summary": str(e)})
        write_manifest_row(manifest_path, row, write_header)
        logger.error(f"  Staging write failed: {e}")
        return False

    bq_errors = validate_staging_with_bigquery(
        bq_client,
        staging_uri,
        contract,
        run_id,
        src_hash,
        source_row_count,
    )
    if bq_errors:
        delete_gcs_object_if_exists(client, staging_uri)
        row.update({
            "status": "bq_validation_failed",
            "error_summary": f"bq_validation: {json.dumps(bq_errors)}",
        })
        write_manifest_row(manifest_path, row, write_header)
        logger.error(f"  BQ validation failed: {bq_errors}")
        return False
    logger.info(f"  BQ validation passed for staging")

    backup_status = "created"
    if gcs_object_exists(client, backup_uri):
        backup_status = "existing"
        logger.info(f"  Backup already exists, skipping backup write: {backup_uri}")
    else:
        try:
            logger.info(f"  Creating backup: {backup_uri}")
            created = copy_gcs_object_atomic(client, source_uri, backup_uri)
            if not created:
                backup_status = "existing"
                logger.info(f"  Backup created by concurrent worker, continuing: {backup_uri}")
        except Exception as e:
            delete_gcs_object_if_exists(client, staging_uri)
            row.update({"status": "backup_failed", "error_summary": str(e)})
            write_manifest_row(manifest_path, row, write_header)
            logger.error(f"  Backup failed: {e}")
            return False

    try:
        logger.info(f"  Publishing to production: {source_uri}")
        copy_gcs_object(client, staging_uri, source_uri)
        published_uri = source_uri
    except Exception as e:
        delete_gcs_object_if_exists(client, staging_uri)
        row.update({
            "status": "publish_failed",
            "error_summary": str(e),
            "backup_status": backup_status,
        })
        write_manifest_row(manifest_path, row, write_header)
        logger.error(f"  Publish failed: {e}")
        return False

    row.update({
        "backup_status": backup_status,
        "published_uri": published_uri,
        "status": "ok",
        "staging_row_count": str(casted_table.num_rows),
        "null_count_after": json.dumps(new_null_counts),
    })
    delete_gcs_object_if_exists(client, staging_uri)
    write_manifest_row(manifest_path, row, write_header)
    logger.info(f"  REPAIRED: {source_uri}")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ODS Parquet Schema Repair")
    parser.add_argument("--endpoint", required=True, help="Endpoint name (e.g. stk_limit)")
    parser.add_argument("--run-id", required=True, help="Repair run ID")
    parser.add_argument("--partition-start", default="20190101", help="Earliest partition_date")
    parser.add_argument("--partition-end", default=None, help="Latest partition_date (inclusive)")
    parser.add_argument("--contracts-dir", default="configs/ods_schema_contracts", help="Contracts directory")
    parser.add_argument("--manifest-path", default=None, help="Manifest CSV output path")
    parser.add_argument("--dry-run", action="store_true", help="Detect mismatches without writing")
    parser.add_argument("--gcs-project", default="data-aquarium", help="GCP project")
    args = parser.parse_args()

    contracts_dir = Path(args.contracts_dir)
    contracts = load_all_contracts(contracts_dir)

    if args.endpoint not in contracts:
        logger.error(f"Unknown endpoint: {args.endpoint}")
        logger.error(f"Available: {list(contracts.keys())}")
        sys.exit(1)

    contract = contracts[args.endpoint]
    logger.info(f"Loaded contract for {args.endpoint} ({contract['priority']})")

    manifest_path = Path(args.manifest_path or f"data_audit/reports/repair_manifest_{args.run_id}.csv")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    existing_manifest = load_existing_manifest(manifest_path)
    write_header = not manifest_path.exists() or manifest_path.stat().st_size == 0

    client = storage.Client(project=args.gcs_project)
    bq_client = bigquery.Client(project=args.gcs_project)

    prefix = contract_gcs_prefix_to_blob_prefix(contract)
    logger.info(f"Listing GCS files: gs://{GCS_BUCKET}/{prefix}")
    all_files = list_gcs_parquet_files(client, prefix)
    logger.info(f"Found {len(all_files)} total Parquet files")

    filtered = []
    for uri in all_files:
        parts = uri.split("/")
        pd = None
        for part in parts:
            if part.startswith("partition_date="):
                pd = part.split("=", 1)[1]
                break
        if pd is None:
            continue
        if pd < args.partition_start:
            continue
        if args.partition_end and pd > args.partition_end:
            continue
        filtered.append((uri, pd))

    logger.info(f"Filtered to {len(filtered)} partitions [{args.partition_start}..{args.partition_end or 'latest'}]")
    logger.info(f"Dry run: {args.dry_run}")

    success = 0
    failed = 0
    skipped = 0

    for uri, pd in sorted(filtered, key=lambda x: x[1]):
        logger.info(f"\nProcessing {args.endpoint} partition_date={pd}")
        key = (args.endpoint, pd, uri)
        if key in existing_manifest and existing_manifest[key]["status"] == "ok":
            skipped += 1
            logger.info(f"  SKIP (manifest): {uri}")
            continue

        result = repair_file(
            client=client,
            bq_client=bq_client,
            contract=contract,
            source_uri=uri,
            run_id=args.run_id,
            endpoint=args.endpoint,
            partition_date=pd,
            dry_run=args.dry_run,
            existing_manifest=existing_manifest,
            manifest_path=manifest_path,
            write_header=write_header,
        )
        write_header = False

        if result:
            success += 1
        else:
            failed += 1

    logger.info(f"\n{'='*60}")
    logger.info(f"Repair complete: {success} succeeded, {failed} failed, {skipped} skipped")
    logger.info(f"Manifest: {manifest_path}")
    if failed > 0:
        logger.warning("Some files need manual review or had errors. Check manifest.")
        sys.exit(2)


if __name__ == "__main__":
    main()
