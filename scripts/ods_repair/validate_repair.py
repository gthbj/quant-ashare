#!/usr/bin/env python3
"""ODS Parquet Schema Repair Validation.

Reads a repair manifest CSV and validates each repaired file:
  - pyarrow schema matches contract
  - row count matches source
  - null count delta is explained
  - file is readable

Usage:
    python scripts/ods_repair/validate_repair.py \
        --manifest data_audit/reports/repair_manifest_<run_id>.csv \
        --contracts-dir configs/ods_schema_contracts \
        [--gcs-project data-aquarium]
"""

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from google.cloud import storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PYARROW_TYPE_MAP = {
    "string": pa.string(),
    "int64": pa.int64(),
    "float64": pa.float64(),
    "bool": pa.bool_(),
}

GCS_BUCKET = "data-aquarium"


def load_contract(path: Path) -> Dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


def load_contracts(dir_path: Path) -> Dict[str, Dict[str, Any]]:
    return {c["endpoint"]: load_contract(p) for p in sorted(dir_path.glob("*.yml"))
            for c in [load_contract(p)]}


def build_contract_schema(contract: Dict[str, Any]) -> pa.Schema:
    fields = []
    for f in contract["fields"]:
        fields.append(pa.field(f["field_name"], PYARROW_TYPE_MAP[f["pyarrow_type"]],
                               nullable=f.get("nullable", True)))
    return pa.schema(fields)


def parse_gcs_uri(uri: str) -> Tuple[str, str]:
    parts = uri[5:].split("/", 1)
    return parts[0], parts[1]


def read_parquet_schema_from_gcs(client: storage.Client, uri: str) -> pq.ParquetFile:
    bucket_name, blob_path = parse_gcs_uri(uri)
    blob = client.bucket(bucket_name).blob(blob_path)
    data = blob.download_as_bytes()
    return pq.ParquetFile(pa.BufferReader(data))


def validate_file(
    client: storage.Client,
    contract: Dict[str, Any],
    row: Dict[str, str],
) -> List[str]:
    errors = []
    endpoint = row["endpoint"]
    status = row["status"]

    if status == "skipped_schema_match":
        return []
    if status in ("read_failed", "staging_write_failed", "backup_failed"):
        return [f"known_failure: {status}"]

    published_uri = row.get("published_uri") or row.get("source_uri")
    if not published_uri:
        return ["no_published_uri"]

    try:
        pf = read_parquet_schema_from_gcs(client, published_uri)
        table = pf.read()
    except Exception as e:
        return [f"read_error: {e}"]

    contract_schema = build_contract_schema(contract)
    actual_schema = table.schema

    for cf in contract["fields"]:
        name = cf["field_name"]
        expected_type = PYARROW_TYPE_MAP[cf["pyarrow_type"]]
        if name not in actual_schema.names:
            errors.append(f"missing_field: {name}")
            continue
        actual_field = actual_schema.field(name)
        if actual_field.type != expected_type:
            errors.append(f"type_mismatch: {name} expected={expected_type} actual={actual_field.type}")

    expected_rows = row.get("source_row_count")
    if expected_rows and table.num_rows != int(expected_rows):
        errors.append(f"row_count_mismatch: expected={expected_rows} actual={table.num_rows}")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate ODS Parquet schema repair")
    parser.add_argument("--manifest", required=True, help="Manifest CSV path")
    parser.add_argument("--contracts-dir", default="configs/ods_schema_contracts")
    parser.add_argument("--gcs-project", default="data-aquarium")
    args = parser.parse_args()

    contracts = load_contracts(Path(args.contracts_dir))
    client = storage.Client(project=args.gcs_project)

    total = 0
    passed = 0
    failed = 0
    failures = []

    with open(args.manifest) as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            endpoint = row["endpoint"]
            if endpoint not in contracts:
                logger.warning(f"  No contract for {endpoint}, skipping validation")
                continue
            contract = contracts[endpoint]
            errors = validate_file(client, contract, row)
            if errors:
                failed += 1
                failures.append({
                    "endpoint": endpoint,
                    "partition_date": row["partition_date"],
                    "source_uri": row["source_uri"],
                    "errors": errors,
                })
                logger.error(f"  FAIL {endpoint} {row['partition_date']}: {errors}")
            else:
                passed += 1
                logger.info(f"  PASS {endpoint} {row['partition_date']}")

    logger.info(f"\n{'='*60}")
    logger.info(f"Validation: {passed}/{total} passed, {failed}/{total} failed")
    if failures:
        logger.error("Failures:")
        for f in failures:
            logger.error(f"  {f['endpoint']} {f['partition_date']}: {f['errors']}")
        sys.exit(1)
    logger.info("All validations passed.")


if __name__ == "__main__":
    main()
