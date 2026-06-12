"""Shared endpoint-group ingestion helpers."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa

from scripts.ingestion.common.gcs_writer import read_schema_contract, write_parquet_to_gcs
from scripts.ingestion.common.parquet_schema import build_parquet_schema


LINEAGE_FIELDS = [
    pa.field("_source", pa.string()),
    pa.field("_tushare_api", pa.string()),
    pa.field("_endpoint_key", pa.string()),
    pa.field("_run_id", pa.string()),
    pa.field("_ingested_at", pa.string()),
    pa.field("_logical_date", pa.string()),
    pa.field("_request_params_json", pa.string()),
]


def ingest_plan(
    *,
    client: Any,
    plan: list[dict[str, Any]],
    business_date: date,
    skip_gcs_write: bool = False,
) -> list[dict[str, Any]]:
    """Execute a run_ingestion_job plan.

    The function writes full business-date partitions for daily endpoints. For
    report-period endpoints it merges new announcement-date rows into the
    existing report-period partition to avoid dropping historical versions.
    """
    results: list[dict[str, Any]] = []
    logical_date = business_date.strftime("%Y%m%d")
    ingested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for item in plan:
        contract = read_schema_contract(Path(item["schema_contract"]))
        item["schema_version"] = contract.get("version")
        item["request_params_hash"] = _request_params_hash(item, logical_date)
        schema = _schema_with_lineage(contract)
        fields = ",".join(field["name"] for field in contract["fields"])
        request_groups = _build_request_groups(item, logical_date)

        all_rows: list[dict[str, Any]] = []
        for request_params in request_groups:
            rows = client.query(item["api"], params=request_params, fields=fields)
            all_rows.extend(rows)

        if not all_rows:
            results.append(_result(item, status="empty_return", row_count=0, gcs_uri=None))
            continue

        partition_groups = _partition_rows(item, all_rows)
        for partition_date, rows in partition_groups.items():
            enriched_rows = [
                _enrich_row(
                    row=row,
                    item=item,
                    request_params=item["request_params"],
                    logical_date=logical_date,
                    ingested_at=ingested_at,
                )
                for row in rows
            ]
            prefix = _prefix_for_partition(item, partition_date)
            if skip_gcs_write:
                # Build the table to validate schema/cast while avoiding GCS mutation.
                from scripts.ingestion.common.parquet_schema import cast_rows

                cast_rows(enriched_rows, schema)
                gcs_uri = None
                status = "api_read_only"
            else:
                gcs_uri = write_parquet_to_gcs(
                    rows=enriched_rows,
                    schema=schema,
                    bucket=item["gcs_bucket"],
                    prefix=prefix,
                    ingestion_run_id=item["ingestion_run_id"],
                    merge_existing=item["partition_date_semantics"] == "report_period",
                    dedupe_keys=contract.get("business_fields", {}).get("primary_key", []),
                )
                status = "success"

            results.append(
                _result(
                    item,
                    status=status,
                    row_count=len(enriched_rows),
                    gcs_uri=gcs_uri,
                    partition_date=partition_date,
                )
            )

    return results


def _schema_with_lineage(contract: dict[str, Any]) -> pa.Schema:
    base_schema = build_parquet_schema(contract["fields"])
    existing_names = {field.name for field in base_schema}
    lineage_fields = [field for field in LINEAGE_FIELDS if field.name not in existing_names]
    return pa.schema(list(base_schema) + lineage_fields)


def _build_request_groups(item: dict[str, Any], logical_date: str) -> list[dict[str, Any]]:
    params = dict(item["request_params"])
    endpoint = item["endpoint"]

    if item["partition_date_semantics"] == "business_date":
        request_date_param = item.get("request_date_param") or item.get("business_date_field") or "trade_date"
        params.setdefault(request_date_param, logical_date)
        return [params]

    if item["partition_date_semantics"] == "report_period":
        params.setdefault("ann_date", logical_date)
        return [params]

    if endpoint == "stock_basic":
        return [
            {**params, "exchange": exchange}
            for exchange in ["SSE", "SZSE", "BSE"]
        ]

    if endpoint == "trade_cal":
        return [
            {"exchange": "SSE", "start_date": start_date, "end_date": end_date}
            for start_date, end_date in _calendar_windows(logical_date)
        ]

    return [params]


def _calendar_windows(logical_date: str) -> list[tuple[str, str]]:
    end_year = int(logical_date[:4]) + 1
    windows: list[tuple[str, str]] = []
    for start_year in range(1990, end_year + 1, 4):
        end_window_year = min(start_year + 3, end_year)
        windows.append((f"{start_year}0101", f"{end_window_year}1231"))
    return windows


def _partition_rows(item: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    if item["partition_date_semantics"] != "report_period":
        return {item["partition_date"]: rows}

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        partition_date = row.get("end_date")
        if not partition_date:
            raise RuntimeError(f"{item['endpoint']} returned row without end_date")
        grouped[str(partition_date)].append(row)
    return dict(grouped)


def _prefix_for_partition(item: dict[str, Any], partition_date: str) -> str:
    marker = "partition_date="
    if marker not in item["gcs_prefix"]:
        raise RuntimeError(f"Unexpected GCS prefix: {item['gcs_prefix']}")
    base = item["gcs_prefix"].split(marker, 1)[0]
    return f"{base}{marker}{partition_date}/"


def _enrich_row(
    *,
    row: dict[str, Any],
    item: dict[str, Any],
    request_params: dict[str, Any],
    logical_date: str,
    ingested_at: str,
) -> dict[str, Any]:
    return {
        **row,
        "_source": item["source_system"],
        "_tushare_api": item["api"],
        "_endpoint_key": item["partition_endpoint"],
        "_run_id": item["ingestion_run_id"],
        "_ingested_at": ingested_at,
        "_logical_date": logical_date,
        "_request_params_json": json.dumps(request_params, ensure_ascii=False, sort_keys=True),
    }


def _result(
    item: dict[str, Any],
    *,
    status: str,
    row_count: int,
    gcs_uri: str | None,
    partition_date: str | None = None,
) -> dict[str, Any]:
    return {
        "ingestion_run_id": item["ingestion_run_id"],
        "source_system": item["source_system"],
        "endpoint_group": item["endpoint_group"],
        "endpoint": item["endpoint"],
        "api": item["api"],
        "variant": item["variant"],
        "partition_endpoint": item["partition_endpoint"],
        "partition_date": partition_date or item["partition_date"],
        "logical_date": item["partition_date"],
        "request_params_hash": item.get("request_params_hash"),
        "schema_version": item.get("schema_version"),
        "row_count": row_count,
        "status": status,
        "gcs_uri": gcs_uri,
    }


def _request_params_hash(item: dict[str, Any], logical_date: str) -> str:
    payload = {
        "api": item["api"],
        "endpoint": item["endpoint"],
        "variant": item["variant"],
        "partition_endpoint": item["partition_endpoint"],
        "logical_date": logical_date,
        "request_params": item["request_params"],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
