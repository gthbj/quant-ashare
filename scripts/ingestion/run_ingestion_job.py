#!/usr/bin/env python3
"""Cloud Run Job entrypoint for Ashare ingestion.

Production ingestion starts with deployable dry-run plumbing. Live endpoint ingestion
depends on the endpoint group implementations under scripts/ingestion/endpoints.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ingestion.common.api_client import TushareClient
from scripts.ingestion.common.manifest import load_manifest
from scripts.ingestion.common.status_writer import IngestionStatusWriter, utc_now


ENDPOINT_GROUPS: dict[str, dict[str, Any]] = {
    "market_eod": {
        "module": "scripts.ingestion.endpoints.daily",
        "endpoints": ["daily", "adj_factor", "stk_limit", "suspend_d", "daily_basic"],
    },
    "index_eod": {
        "module": "scripts.ingestion.endpoints.index",
        "endpoints": ["index_daily", "index_dailybasic"],
    },
    "dim_snapshot": {
        "module": "scripts.ingestion.endpoints.dim_snapshot",
        "endpoints": ["stock_basic", "trade_cal", "namechange"],
    },
    "finance_recent": {
        "module": "scripts.ingestion.endpoints.finance",
        "endpoints": ["fina_indicator", "income", "balancesheet", "cashflow"],
    },
    "corporate_actions": {
        "module": "scripts.ingestion.endpoints.corporate_actions",
        "endpoints": ["dividend"],
    },
    "dividend_backfill": {
        "module": "scripts.ingestion.endpoints.corporate_actions",
        "endpoints": ["dividend"],
    },
}
ENDPOINT_GROUP_ALIASES: dict[str, list[str]] = {
    "current_scope": ["market_eod", "index_eod", "dim_snapshot", "finance_recent", "corporate_actions"],
}


def _yyyymmdd(value: str) -> str:
    return value.replace("-", "")


def _build_default_run_id(endpoint_group: str, business_date: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"ing_{endpoint_group}_{_yyyymmdd(business_date)}_{ts}"


def _endpoint_by_name(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {endpoint["endpoint"]: endpoint for endpoint in manifest.get("endpoints", [])}


def _format_gcs_prefix(
    manifest: dict[str, Any],
    endpoint_cfg: dict[str, Any],
    partition_endpoint: str,
    partition_date: str,
) -> str:
    defaults = manifest.get("defaults", {})
    template = defaults["gcs_prefix_template"]
    api = endpoint_cfg.get("api", endpoint_cfg["endpoint"])
    return template.format(
        api=api,
        endpoint=endpoint_cfg["endpoint"],
        partition_endpoint=partition_endpoint,
        partition_date=partition_date,
    )


def _parse_business_date(value: str) -> date:
    value = value.strip()
    if "-" in value:
        return date.fromisoformat(value)
    return date.fromisoformat(f"{value[:4]}-{value[4:6]}-{value[6:8]}")


def _normalize_business_date(value: str) -> str:
    return _parse_business_date(value).isoformat()


def _lookback_open_days(endpoint_cfg: dict[str, Any]) -> int:
    raw = endpoint_cfg.get("lookback_open_days") or 1
    return max(1, int(raw))


def _group_lookback_open_days(
    manifest: dict[str, Any],
    endpoint_group: str,
    endpoint_filters: set[str] | None = None,
) -> int:
    endpoint_map = _endpoint_by_name(manifest)
    lookback = 1
    for endpoint_name in ENDPOINT_GROUPS[endpoint_group]["endpoints"]:
        if endpoint_filters and endpoint_name not in endpoint_filters:
            continue
        endpoint_cfg = endpoint_map[endpoint_name]
        lookback = max(lookback, _lookback_open_days(endpoint_cfg))
    return lookback


def resolve_open_business_dates(
    *,
    project: str,
    location: str,
    business_date: str,
    lookback_open_days: int,
) -> list[str]:
    """Resolve recent SSE open days from dim_trade_calendar, newest bound inclusive."""
    from google.cloud import bigquery

    parsed_business_date = _parse_business_date(business_date)
    query = f"""
SELECT FORMAT_DATE('%Y-%m-%d', cal_date) AS business_date
FROM `{project}.ashare_dim.dim_trade_calendar`
WHERE exchange = 'SSE'
  AND is_open = 1
  AND cal_date <= @business_date
ORDER BY cal_date DESC
LIMIT @lookback_open_days
"""
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("business_date", "DATE", parsed_business_date),
            bigquery.ScalarQueryParameter("lookback_open_days", "INT64", lookback_open_days),
        ]
    )
    client = bigquery.Client(project=project, location=location)
    rows = list(client.query(query, job_config=job_config, location=location).result())
    dates = [row.business_date for row in reversed(rows)]
    if len(dates) != lookback_open_days:
        raise RuntimeError(
            "dim_trade_calendar did not return enough SSE open days for "
            f"business_date={business_date}, lookback_open_days={lookback_open_days}: {dates}"
        )
    return dates


def _partition_dates_for_endpoint(
    endpoint_cfg: dict[str, Any],
    business_date: str,
    lookback_business_dates: list[str] | None,
) -> list[str]:
    lookback = _lookback_open_days(endpoint_cfg)
    if lookback == 1:
        return [_normalize_business_date(business_date)]
    if lookback_business_dates is None:
        raise RuntimeError(
            f"Endpoint {endpoint_cfg['endpoint']} requires lookback_open_days={lookback} "
            "but no resolved open-day calendar was provided."
        )
    if len(lookback_business_dates) != lookback:
        raise RuntimeError(
            f"Endpoint {endpoint_cfg['endpoint']} requires {lookback} open days, "
            f"got {len(lookback_business_dates)}."
        )
    return [_normalize_business_date(value) for value in lookback_business_dates]


def build_plan(
    manifest: dict[str, Any],
    endpoint_group: str,
    business_date: str,
    ingestion_run_id: str,
    endpoint_filters: set[str] | None = None,
    variant_filters: set[str] | None = None,
    lookback_business_dates: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Build the endpoint/partition plan that a Cloud Run job would execute."""
    if endpoint_group not in ENDPOINT_GROUPS:
        raise ValueError(f"Unknown endpoint group: {endpoint_group}")

    defaults = manifest.get("defaults", {})
    contract_dir = Path(defaults["schema_contract_dir"])
    endpoint_map = _endpoint_by_name(manifest)
    plan: list[dict[str, Any]] = []

    for endpoint_name in ENDPOINT_GROUPS[endpoint_group]["endpoints"]:
        if endpoint_filters and endpoint_name not in endpoint_filters:
            continue
        endpoint_cfg = endpoint_map[endpoint_name]
        partition_business_dates = _partition_dates_for_endpoint(
            endpoint_cfg=endpoint_cfg,
            business_date=business_date,
            lookback_business_dates=lookback_business_dates,
        )
        request_variants = endpoint_cfg.get("request_variants") or [
            {
                "variant": endpoint_cfg["endpoint"],
                "params": {},
                "partition_endpoint": endpoint_cfg.get("partition_endpoint", endpoint_cfg["endpoint"]),
            }
        ]

        for variant in request_variants:
            variant_name = variant.get("variant", endpoint_cfg["endpoint"])
            if variant_filters and variant_name not in variant_filters:
                continue
            partition_endpoint = variant.get(
                "partition_endpoint",
                endpoint_cfg.get("partition_endpoint", endpoint_cfg["endpoint"]),
            )
            contract_path = contract_dir / f"{endpoint_cfg['endpoint']}.json"
            for partition_business_date in partition_business_dates:
                partition_date = _yyyymmdd(partition_business_date)
                plan.append(
                    {
                        "ingestion_run_id": ingestion_run_id,
                        "source_system": defaults.get("source_system", "tushare"),
                        "endpoint_group": endpoint_group,
                        "endpoint": endpoint_cfg["endpoint"],
                        "api": endpoint_cfg.get("api", endpoint_cfg["endpoint"]),
                        "variant": variant_name,
                        "partition_endpoint": partition_endpoint,
                        "business_date_field": endpoint_cfg.get("business_date_field"),
                        "request_date_param": endpoint_cfg.get("request_date_param"),
                        "partition_date": partition_date,
                        "logical_date": partition_date,
                        "partition_date_semantics": endpoint_cfg.get("partition_date_semantics"),
                        "lookback_open_days": endpoint_cfg.get("lookback_open_days"),
                        "request_params": variant.get("params", {}),
                        "schema_contract": str(contract_path),
                        "schema_contract_exists": contract_path.exists(),
                        "gcs_bucket": defaults.get("gcs_bucket"),
                        "gcs_prefix": _format_gcs_prefix(
                            manifest=manifest,
                            endpoint_cfg=endpoint_cfg,
                            partition_endpoint=partition_endpoint,
                            partition_date=partition_date,
                        ),
                        "status": "planned",
                    }
                )

    return plan


def _require_token() -> str:
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        raise RuntimeError(
            "TUSHARE_TOKEN is not set. In Cloud Run, inject it from Secret Manager; "
            "do not pass the token in args or commit it to the repo."
        )
    return token


def _endpoint_group_choices() -> list[str]:
    return sorted([*ENDPOINT_GROUPS, *ENDPOINT_GROUP_ALIASES])


def _resolve_endpoint_groups(endpoint_group: str) -> list[str]:
    return ENDPOINT_GROUP_ALIASES.get(endpoint_group, [endpoint_group])


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Ashare ingestion endpoint group.")
    parser.add_argument("--manifest", default=os.environ.get("INGESTION_MANIFEST", "configs/ingestion/ods_current_scope_v0.yml"))
    parser.add_argument("--endpoint-group", choices=_endpoint_group_choices(), required=True)
    parser.add_argument("--endpoint", action="append", help="Restrict execution to one endpoint name. Repeatable.")
    parser.add_argument("--variant", action="append", help="Restrict execution to one request variant. Repeatable.")
    parser.add_argument("--business-date", default=date.today().isoformat())
    parser.add_argument("--ingestion-run-id")
    parser.add_argument("--dry-run", action="store_true", help="Only print the execution plan; do not call Tushare or write GCS.")
    parser.add_argument("--skip-gcs-write", action="store_true", help="Call the API and validate schema/cast, but do not write GCS.")
    parser.add_argument("--allow-gcs-write", action="store_true", help="Required for live GCS writes.")
    parser.add_argument("--output-json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--base-url", default=os.environ.get("TUSHARE_HTTP_URL", "https://api.tushare.pro"))
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT", "data-aquarium"))
    parser.add_argument("--bq-location", default=os.environ.get("BQ_LOCATION", "asia-east2"))
    parser.add_argument("--row-limit", type=int, default=int(os.environ.get("TUSHARE_ROW_LIMIT", "5000")))
    parser.add_argument("--throttle-seconds", type=float, default=float(os.environ.get("TUSHARE_THROTTLE_SECONDS", "0.3")))
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = load_manifest(args.manifest)
    ingestion_run_id = args.ingestion_run_id or _build_default_run_id(args.endpoint_group, args.business_date)
    endpoint_groups = _resolve_endpoint_groups(args.endpoint_group)
    all_plan: list[dict[str, Any]] = []
    for endpoint_group in endpoint_groups:
        group_run_id = ingestion_run_id if len(endpoint_groups) == 1 else f"{ingestion_run_id}_{endpoint_group}"
        lookback_open_days = _group_lookback_open_days(
            manifest=manifest,
            endpoint_group=endpoint_group,
            endpoint_filters=set(args.endpoint or []) or None,
        )
        lookback_business_dates = None
        if lookback_open_days > 1:
            lookback_business_dates = resolve_open_business_dates(
                project=args.project,
                location=args.bq_location,
                business_date=args.business_date,
                lookback_open_days=lookback_open_days,
            )
        all_plan.extend(
            build_plan(
                manifest=manifest,
                endpoint_group=endpoint_group,
                business_date=args.business_date,
                ingestion_run_id=group_run_id,
                endpoint_filters=set(args.endpoint or []) or None,
                variant_filters=set(args.variant or []) or None,
                lookback_business_dates=lookback_business_dates,
            )
        )
    plan = all_plan
    if not plan:
        raise RuntimeError("No endpoint plan items matched the requested filters.")

    missing_contracts = [item["schema_contract"] for item in plan if not item["schema_contract_exists"]]
    if missing_contracts:
        raise RuntimeError(f"Missing schema contracts: {missing_contracts}")

    if args.dry_run:
        payload = {"status": "dry_run", "plan": plan}
        if args.output_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"Dry-run ingestion plan: {len(plan)} endpoint partitions")
            for item in plan:
                print(
                    f"- {item['endpoint_group']} {item['variant']} "
                    f"partition_endpoint={item['partition_endpoint']} "
                    f"partition_date={item['partition_date']}"
                )
        return 0

    if not args.skip_gcs_write and not args.allow_gcs_write:
        raise RuntimeError("Live GCS writes require --allow-gcs-write.")

    status_writer = None
    if not args.skip_gcs_write:
        status_writer = IngestionStatusWriter(project=args.project, location=args.bq_location)
    started_at = utc_now()
    results: list[dict[str, Any]] = []
    try:
        token = _require_token()
        client = TushareClient(
            token=token,
            base_url=args.base_url,
            throttle=args.throttle_seconds,
            row_limit=args.row_limit,
        )
        business_date = date.fromisoformat(args.business_date)
        for endpoint_group in endpoint_groups:
            group_plan = [item for item in plan if item["endpoint_group"] == endpoint_group]
            if not group_plan:
                continue
            module = importlib.import_module(ENDPOINT_GROUPS[endpoint_group]["module"])
            group_results = module.ingest(
                client=client,
                manifest=manifest,
                business_date=business_date,
                ingestion_run_id=group_plan[0]["ingestion_run_id"],
                plan=group_plan,
                skip_gcs_write=args.skip_gcs_write,
            )
            results.extend(group_results)
    except Exception as exc:
        if status_writer is not None:
            status_writer.write_failure(plan, started_at=started_at, finished_at=utc_now(), error=exc)
        raise

    if status_writer is not None:
        status_writer.write_results(results, started_at=started_at, finished_at=utc_now())
    print(json.dumps({"status": "completed", "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
