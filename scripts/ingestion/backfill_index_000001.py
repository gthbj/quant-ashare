#!/usr/bin/env python3
"""Backfill 000001.SH index ODS partitions by range fetch.

The script fetches index_daily and index_dailybasic by date range, validates that
all target SSE trading days are present, then writes one Parquet object per ODS
Hive partition:

  a-share/tushare/raw_data/api=<api>/endpoint=<partition_endpoint>/partition_date=<YYYYMMDD>/data.parquet

TUSHARE_TOKEN and TUSHARE_HTTP_URL must be provided by the runtime environment.
Do not pass or store tokens in args, files, logs, or git-tracked config.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ingestion.common.gcs_writer import read_schema_contract, write_parquet_to_gcs
from scripts.ingestion.common.manifest import load_manifest
from scripts.ingestion.common.parquet_schema import build_parquet_schema, cast_rows
from scripts.ingestion.common.status_writer import IngestionStatusWriter, utc_now
from scripts.ingestion.run_ingestion_job import build_plan


TS_CODE = "000001.SH"
VARIANTS_BY_ENDPOINT = {
    "index_daily": "index_daily_000001_SH",
    "index_dailybasic": "index_dailybasic_000001_SH",
}
DEFAULT_START_DATE = "2019-01-01"
DEFAULT_STATE_FILE = "~/.cache/quant-ashare/ods_index_000001_backfill_state.json"
DEFAULT_ROW_LIMIT = 5000
LINEAGE_FIELDS = [
    pa.field("_source", pa.string()),
    pa.field("_tushare_api", pa.string()),
    pa.field("_endpoint_key", pa.string()),
    pa.field("_run_id", pa.string()),
    pa.field("_ingested_at", pa.string()),
    pa.field("_logical_date", pa.string()),
    pa.field("_request_params_json", pa.string()),
]


@dataclass(frozen=True)
class PartitionTask:
    key: str
    ingestion_run_id: str
    source_system: str
    endpoint_group: str
    endpoint: str
    api: str
    variant: str
    partition_endpoint: str
    partition_date: str
    request_params: dict[str, Any]
    schema_contract: str
    schema_version: str | None
    gcs_bucket: str
    gcs_prefix: str


@dataclass(frozen=True)
class FetchTask:
    key: str
    endpoint: str
    api: str
    variant: str
    request_params: dict[str, Any]
    schema_contract: str
    partitions: list[PartitionTask]

    @property
    def start_date(self) -> str:
        return min(partition.partition_date for partition in self.partitions)

    @property
    def end_date(self) -> str:
        return max(partition.partition_date for partition in self.partitions)


class SharedRateLimiter:
    """Thread-safe request starter limiter using evenly spaced tokens."""

    def __init__(self, requests_per_minute: int):
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        self._interval_seconds = 60.0 / requests_per_minute
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait_seconds = max(0.0, self._next_allowed - now)
            self._next_allowed = max(now, self._next_allowed) + self._interval_seconds
        if wait_seconds > 0:
            time.sleep(wait_seconds)


class TushareRequestClient:
    def __init__(
        self,
        *,
        token: str,
        base_url: str,
        limiter: SharedRateLimiter,
        timeout_seconds: int,
        max_retries: int,
    ):
        self._token = token
        self._base_url = base_url
        self._limiter = limiter
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    def query(self, api_name: str, params: dict[str, Any], fields: str) -> list[dict[str, Any]]:
        payload = {
            "api_name": api_name,
            "token": self._token,
            "params": params,
            "fields": fields,
        }
        last_error: BaseException | None = None
        for attempt in range(self._max_retries + 1):
            self._limiter.wait()
            try:
                response = requests.post(self._base_url, json=payload, timeout=self._timeout_seconds)
                response.raise_for_status()
                data = response.json()
                if data.get("code") != 0:
                    raise RuntimeError(f"Tushare API error for {api_name}: {data.get('msg', 'unknown')}")
                columns = data.get("data", {}).get("fields", [])
                items = data.get("data", {}).get("items", [])
                return [dict(zip(columns, item)) for item in items]
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, RuntimeError) as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                time.sleep(min(30, 2 ** attempt))
            except requests.exceptions.HTTPError as exc:
                last_error = exc
                if response.status_code < 500 or attempt >= self._max_retries:
                    break
                time.sleep(min(30, 2 ** attempt))
        raise RuntimeError(f"Failed {api_name} {params} after {self._max_retries} retries: {last_error}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill 000001.SH index_daily/index_dailybasic ODS partitions.")
    parser.add_argument("--manifest", default=os.environ.get("INGESTION_MANIFEST", "configs/ingestion/ods_current_scope_v0.yml"))
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=_today_iso())
    parser.add_argument("--date-source", choices=["bq-trade-calendar", "calendar-days"], default="bq-trade-calendar")
    parser.add_argument("--endpoint", action="append", choices=sorted(VARIANTS_BY_ENDPOINT), help="Restrict to one endpoint. Repeatable.")
    parser.add_argument("--ingestion-run-id", default=_default_run_id())
    parser.add_argument("--base-url", default=os.environ.get("TUSHARE_HTTP_URL", "https://api.tushare.pro"))
    parser.add_argument("--row-limit", type=int, default=DEFAULT_ROW_LIMIT)
    parser.add_argument("--requests-per-minute", type=int, default=100)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--max-partitions", type=int, help="Limit target partitions for smoke/debug runs.")
    parser.add_argument("--state-file", default=DEFAULT_STATE_FILE)
    parser.add_argument("--no-resume", action="store_true", help="Ignore the local state file.")
    parser.add_argument("--retry-empty", action="store_true", help="Retry partitions previously recorded as empty_return.")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if state or target GCS object already exists.")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan only; do not call Tushare or GCS.")
    parser.add_argument("--skip-gcs-write", action="store_true", help="Call Tushare and validate Parquet casts, but do not write GCS.")
    parser.add_argument("--allow-gcs-write", action="store_true", help="Required for live GCS writes.")
    parser.add_argument("--write-status", action="store_true", help="Also write ashare_meta ingestion status rows for each partition.")
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT", "data-aquarium"))
    parser.add_argument("--bq-location", default=os.environ.get("BQ_LOCATION", "asia-east2"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _validate_args(args)

    manifest = load_manifest(args.manifest)
    trade_dates = load_dates(args)
    partition_tasks = build_partition_tasks(manifest, trade_dates, args)
    if args.max_partitions:
        partition_tasks = partition_tasks[: args.max_partitions]
    state_path = Path(args.state_file).expanduser()
    state = {} if args.no_resume else load_state(state_path)
    executable_partitions = filter_partitions(partition_tasks, state, args)
    fetch_tasks = build_fetch_tasks(executable_partitions)

    plan_payload = {
        "status": "dry_run" if args.dry_run else "planned",
        "ts_code": TS_CODE,
        "date_order": "descending",
        "fetch_mode": "range_fetch_then_partition_write",
        "requests_per_minute": args.requests_per_minute,
        "workers": args.workers,
        "row_limit_guard": args.row_limit,
        "total_partitions": len(partition_tasks),
        "executable_partitions": len(executable_partitions),
        "fetch_tasks": [
            {
                "key": task.key,
                "start_date": task.start_date,
                "end_date": task.end_date,
                "partition_count": len(task.partitions),
            }
            for task in fetch_tasks
        ],
        "first_partition": executable_partitions[0].key if executable_partitions else None,
        "last_partition": executable_partitions[-1].key if executable_partitions else None,
    }
    if args.dry_run:
        print(json.dumps(plan_payload, ensure_ascii=False, indent=2))
        return 0

    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is not set. Provide it through the runtime environment.")

    status_writer = None
    if args.write_status and not args.skip_gcs_write:
        status_writer = IngestionStatusWriter(project=args.project, location=args.bq_location)

    storage_client = None
    if not args.skip_gcs_write:
        from google.cloud import storage

        storage_client = storage.Client(project=args.project)

    limiter = SharedRateLimiter(args.requests_per_minute)
    client = TushareRequestClient(
        token=token,
        base_url=args.base_url,
        limiter=limiter,
        timeout_seconds=args.timeout_seconds,
        max_retries=args.max_retries,
    )

    failures = 0
    results: list[dict[str, Any]] = []
    state_path.parent.mkdir(parents=True, exist_ok=True)
    max_workers = max(1, min(args.workers, len(fetch_tasks) or 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {
            executor.submit(run_fetch_task, task, client, storage_client, args): task
            for task in fetch_tasks
        }
        for future in concurrent.futures.as_completed(future_to_task):
            task = future_to_task[future]
            try:
                task_results = future.result()
            except Exception as exc:
                failures += len(task.partitions)
                task_results = [failed_result(partition, exc) for partition in task.partitions]
            for result in task_results:
                results.append(result)
                update_state(state, result)
                save_state(state_path, state)
                if status_writer and result["status"] in {"success", "empty_return", "failed"}:
                    status_writer.write_results(
                        [result],
                        started_at=datetime.fromisoformat(result["started_at"]),
                        finished_at=datetime.fromisoformat(result["finished_at"]),
                    )

    payload = {
        **plan_payload,
        "status": "failed" if failures else "completed",
        "success": sum(1 for item in results if item["status"] == "success"),
        "api_read_only": sum(1 for item in results if item["status"] == "api_read_only"),
        "empty_return": sum(1 for item in results if item["status"] == "empty_return"),
        "skipped_existing": sum(1 for item in results if item["status"] == "skipped_existing"),
        "failed": failures,
        "state_file": str(state_path),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if failures else 0


def run_fetch_task(
    fetch_task: FetchTask,
    client: TushareRequestClient,
    storage_client: Any,
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    skipped_results: list[dict[str, Any]] = []
    active_partitions: list[PartitionTask] = []
    for partition in fetch_task.partitions:
        started_at = utc_now()
        if not args.skip_gcs_write and not args.force and target_object_exists(storage_client, partition):
            skipped_results.append(
                result_for_partition(
                    partition,
                    status="skipped_existing",
                    row_count=0,
                    gcs_uri=target_gcs_uri(partition),
                    started_at=started_at,
                    finished_at=utc_now(),
                )
            )
        else:
            active_partitions.append(partition)
    if not active_partitions:
        return skipped_results

    contract = read_schema_contract(Path(fetch_task.schema_contract))
    schema = schema_with_lineage(contract)
    fields = ",".join(field["name"] for field in contract["fields"])
    start_date = min(partition.partition_date for partition in active_partitions)
    end_date = max(partition.partition_date for partition in active_partitions)
    request_params = {
        **fetch_task.request_params,
        "start_date": start_date,
        "end_date": end_date,
        "limit": args.row_limit,
    }
    rows = fetch_rows_with_limit_guard(
        client=client,
        fetch_task=fetch_task,
        start_date=start_date,
        end_date=end_date,
        fields=fields,
        row_limit=args.row_limit,
    )
    rows_by_date = group_rows_by_trade_date(rows, start_date=start_date, end_date=end_date)
    missing_dates = sorted({partition.partition_date for partition in active_partitions} - set(rows_by_date))
    if missing_dates:
        preview = ", ".join(missing_dates[:10])
        raise RuntimeError(
            f"{fetch_task.key} missing rows for {len(missing_dates)} target trading days: {preview}"
        )

    results = list(skipped_results)
    for partition in active_partitions:
        started_at = utc_now()
        rows_for_partition = rows_by_date[partition.partition_date]
        enriched_rows = enrich_rows(
            rows=rows_for_partition,
            partition=partition,
            request_params=request_params,
        )
        if args.skip_gcs_write:
            cast_rows(enriched_rows, schema)
            gcs_uri = None
            status = "api_read_only"
        else:
            gcs_uri = write_parquet_to_gcs(
                rows=enriched_rows,
                schema=schema,
                bucket=partition.gcs_bucket,
                prefix=partition.gcs_prefix,
                ingestion_run_id=partition.ingestion_run_id,
            )
            status = "success"
        results.append(
            result_for_partition(
                partition,
                status=status,
                row_count=len(enriched_rows),
                gcs_uri=gcs_uri,
                started_at=started_at,
                finished_at=utc_now(),
                request_params=request_params,
            )
        )
    return results


def fetch_rows_with_limit_guard(
    *,
    client: TushareRequestClient,
    fetch_task: FetchTask,
    start_date: str,
    end_date: str,
    fields: str,
    row_limit: int,
) -> list[dict[str, Any]]:
    params = {
        **fetch_task.request_params,
        "start_date": start_date,
        "end_date": end_date,
        "limit": row_limit,
    }
    rows = client.query(fetch_task.api, params=params, fields=fields)
    if len(rows) < row_limit:
        return rows
    if start_date == end_date:
        raise RuntimeError(f"{fetch_task.key} hit row_limit={row_limit} for single date {start_date}")

    left_start, left_end, right_start, right_end = split_date_range(start_date, end_date)
    return [
        *fetch_rows_with_limit_guard(
            client=client,
            fetch_task=fetch_task,
            start_date=left_start,
            end_date=left_end,
            fields=fields,
            row_limit=row_limit,
        ),
        *fetch_rows_with_limit_guard(
            client=client,
            fetch_task=fetch_task,
            start_date=right_start,
            end_date=right_end,
            fields=fields,
            row_limit=row_limit,
        ),
    ]


def group_rows_by_trade_date(rows: list[dict[str, Any]], *, start_date: str, end_date: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        ts_code = row.get("ts_code")
        if ts_code != TS_CODE:
            raise RuntimeError(f"Unexpected ts_code in API response: {ts_code}")
        trade_date = str(row.get("trade_date") or "")
        if trade_date < start_date or trade_date > end_date:
            raise RuntimeError(f"Unexpected trade_date outside requested range: {trade_date}")
        grouped.setdefault(trade_date, []).append(row)
    duplicates = [trade_date for trade_date, bucket in grouped.items() if len(bucket) > 1]
    if duplicates:
        preview = ", ".join(sorted(duplicates)[:10])
        raise RuntimeError(f"API returned duplicate rows for {len(duplicates)} trade dates: {preview}")
    return grouped


def enrich_rows(
    *,
    rows: list[dict[str, Any]],
    partition: PartitionTask,
    request_params: dict[str, Any],
) -> list[dict[str, Any]]:
    ingested_at = utc_now().isoformat(timespec="seconds")
    return [
        {
            **row,
            "_source": partition.source_system,
            "_tushare_api": partition.api,
            "_endpoint_key": partition.partition_endpoint,
            "_run_id": partition.ingestion_run_id,
            "_ingested_at": ingested_at,
            "_logical_date": partition.partition_date,
            "_request_params_json": json.dumps(request_params, ensure_ascii=False, sort_keys=True),
        }
        for row in rows
    ]


def load_dates(args: argparse.Namespace) -> list[str]:
    start = parse_date(args.start_date)
    end = parse_date(args.end_date)
    if end < start:
        raise ValueError("--end-date must be >= --start-date")
    if args.date_source == "calendar-days":
        dates: list[str] = []
        current = end
        while current >= start:
            dates.append(current.strftime("%Y%m%d"))
            current -= timedelta(days=1)
        return dates
    return load_sse_trade_dates_from_bq(start, end, project=args.project, location=args.bq_location)


def load_sse_trade_dates_from_bq(start: date, end: date, *, project: str, location: str) -> list[str]:
    from google.cloud import bigquery

    client = bigquery.Client(project=project, location=location)
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("start_date", "DATE", start),
            bigquery.ScalarQueryParameter("end_date", "DATE", end),
        ]
    )
    rows = client.query(
        """
        SELECT FORMAT_DATE('%Y%m%d', cal_date) AS trade_date
        FROM `data-aquarium.ashare_dim.dim_trade_calendar`
        WHERE exchange = 'SSE'
          AND is_open = 1
          AND cal_date BETWEEN @start_date AND @end_date
        ORDER BY cal_date DESC
        """,
        job_config=job_config,
    ).result()
    return [row.trade_date for row in rows]


def build_partition_tasks(manifest: dict[str, Any], trade_dates: list[str], args: argparse.Namespace) -> list[PartitionTask]:
    endpoints = set(args.endpoint or VARIANTS_BY_ENDPOINT)
    variants = {VARIANTS_BY_ENDPOINT[endpoint] for endpoint in endpoints}
    tasks: list[PartitionTask] = []
    for trade_date in trade_dates:
        business_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
        plan = build_plan(
            manifest=manifest,
            endpoint_group="index_eod",
            business_date=business_date,
            ingestion_run_id=args.ingestion_run_id,
            endpoint_filters=endpoints,
            variant_filters=variants,
        )
        for item in plan:
            contract = read_schema_contract(Path(item["schema_contract"]))
            key = f"{item['partition_endpoint']}|{item['partition_date']}"
            tasks.append(
                PartitionTask(
                    key=key,
                    ingestion_run_id=item["ingestion_run_id"],
                    source_system=item["source_system"],
                    endpoint_group=item["endpoint_group"],
                    endpoint=item["endpoint"],
                    api=item["api"],
                    variant=item["variant"],
                    partition_endpoint=item["partition_endpoint"],
                    partition_date=item["partition_date"],
                    request_params=item["request_params"],
                    schema_contract=item["schema_contract"],
                    schema_version=contract.get("version"),
                    gcs_bucket=item["gcs_bucket"],
                    gcs_prefix=item["gcs_prefix"],
                )
            )
    return tasks


def build_fetch_tasks(partitions: list[PartitionTask]) -> list[FetchTask]:
    grouped: dict[tuple[str, str], list[PartitionTask]] = {}
    for partition in partitions:
        grouped.setdefault((partition.endpoint, partition.variant), []).append(partition)
    tasks: list[FetchTask] = []
    for (endpoint, variant), items in sorted(grouped.items()):
        items.sort(key=lambda item: item.partition_date, reverse=True)
        first = items[0]
        tasks.append(
            FetchTask(
                key=f"{endpoint}:{variant}",
                endpoint=endpoint,
                api=first.api,
                variant=variant,
                request_params=first.request_params,
                schema_contract=first.schema_contract,
                partitions=items,
            )
        )
    return tasks


def filter_partitions(tasks: list[PartitionTask], state: dict[str, Any], args: argparse.Namespace) -> list[PartitionTask]:
    if args.force or args.no_resume:
        return tasks
    completed = state.get("completed", {})
    output: list[PartitionTask] = []
    for task in tasks:
        previous = completed.get(task.key)
        if previous and previous.get("status") in {"success", "skipped_existing"}:
            continue
        if previous and previous.get("status") == "empty_return" and not args.retry_empty:
            continue
        output.append(task)
    return output


def result_for_partition(
    partition: PartitionTask,
    *,
    status: str,
    row_count: int,
    gcs_uri: str | None,
    started_at: datetime,
    finished_at: datetime,
    request_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params = request_params or {**partition.request_params, "trade_date": partition.partition_date}
    return {
        "task_key": partition.key,
        "ingestion_run_id": partition.ingestion_run_id,
        "source_system": partition.source_system,
        "endpoint_group": partition.endpoint_group,
        "endpoint": partition.endpoint,
        "api": partition.api,
        "variant": partition.variant,
        "partition_endpoint": partition.partition_endpoint,
        "partition_date": partition.partition_date,
        "logical_date": partition.partition_date,
        "request_params_hash": request_params_hash(partition, params),
        "schema_version": partition.schema_version,
        "row_count": row_count,
        "status": status,
        "gcs_uri": gcs_uri,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
    }


def failed_result(partition: PartitionTask, exc: BaseException) -> dict[str, Any]:
    now = utc_now()
    result = result_for_partition(
        partition,
        status="failed",
        row_count=0,
        gcs_uri=None,
        started_at=now,
        finished_at=now,
    )
    result["error_summary"] = str(exc)[:1000]
    return result


def schema_with_lineage(contract: dict[str, Any]) -> pa.Schema:
    base_schema = build_parquet_schema(contract["fields"])
    existing_names = {field.name for field in base_schema}
    lineage_fields = [field for field in LINEAGE_FIELDS if field.name not in existing_names]
    return pa.schema(list(base_schema) + lineage_fields)


def target_object_exists(storage_client: Any, partition: PartitionTask) -> bool:
    bucket = storage_client.bucket(partition.gcs_bucket)
    return bucket.blob(target_object_name(partition)).exists()


def target_object_name(partition: PartitionTask) -> str:
    return f"{partition.gcs_prefix.strip('/')}/data.parquet"


def target_gcs_uri(partition: PartitionTask) -> str:
    return f"gs://{partition.gcs_bucket}/{target_object_name(partition)}"


def request_params_hash(partition: PartitionTask, params: dict[str, Any]) -> str:
    payload = {
        "api": partition.api,
        "endpoint": partition.endpoint,
        "variant": partition.variant,
        "partition_endpoint": partition.partition_endpoint,
        "logical_date": partition.partition_date,
        "request_params": params,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def update_state(state: dict[str, Any], result: dict[str, Any]) -> None:
    state.setdefault("schema_version", 1)
    state["ts_code"] = TS_CODE
    state["updated_at"] = utc_now().isoformat(timespec="seconds")
    state.setdefault("completed", {})[result["task_key"]] = {
        "status": result["status"],
        "row_count": result["row_count"],
        "gcs_uri": result.get("gcs_uri"),
        "finished_at": result["finished_at"],
        "error_summary": result.get("error_summary"),
    }


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_state(path: Path, state: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))
    tmp_path.replace(path)


def split_date_range(start_date: str, end_date: str) -> tuple[str, str, str, str]:
    start = parse_date(start_date)
    end = parse_date(end_date)
    midpoint = start + timedelta(days=(end - start).days // 2)
    right_start = midpoint + timedelta(days=1)
    return (
        start.strftime("%Y%m%d"),
        midpoint.strftime("%Y%m%d"),
        right_start.strftime("%Y%m%d"),
        end.strftime("%Y%m%d"),
    )


def parse_date(value: str) -> date:
    compact = value.replace("-", "")
    if len(compact) != 8:
        raise ValueError(f"Invalid date: {value}")
    return date(int(compact[:4]), int(compact[4:6]), int(compact[6:]))


def _today_iso() -> str:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    except Exception:
        return date.today().isoformat()


def _default_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"ing_index_000001_backfill_{ts}"


def _validate_args(args: argparse.Namespace) -> None:
    if args.row_limit <= 0:
        raise ValueError("--row-limit must be positive")
    if args.requests_per_minute > 100:
        raise ValueError("--requests-per-minute must be <= 100 for the current token-level limit")
    if args.workers <= 0:
        raise ValueError("--workers must be positive")
    if not args.dry_run and not args.skip_gcs_write and not args.allow_gcs_write:
        raise RuntimeError("Use --dry-run, --skip-gcs-write, or --allow-gcs-write.")
    if args.skip_gcs_write and args.allow_gcs_write:
        raise RuntimeError("--skip-gcs-write and --allow-gcs-write are mutually exclusive.")


if __name__ == "__main__":
    raise SystemExit(main())
