from pathlib import Path

from scripts.ingestion.common.endpoint_runner import _build_request_groups
from scripts.ingestion.common.manifest import load_manifest
from scripts.ingestion.run_ingestion_job import ENDPOINT_GROUP_ALIASES, build_plan

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_current_scope_alias_excludes_manual_dividend_backfill_group() -> None:
    assert ENDPOINT_GROUP_ALIASES["current_scope"] == [
        "market_eod",
        "index_eod",
        "dim_snapshot",
        "finance_recent",
    ]
    assert "dividend_backfill" not in ENDPOINT_GROUP_ALIASES["current_scope"]


def test_dividend_backfill_manifest_uses_ex_date_partition_and_canonical_gcs_path() -> None:
    manifest = load_manifest(REPO_ROOT / "configs/ingestion/ods_dividend_backfill_v0.yml")

    plan = build_plan(
        manifest=manifest,
        endpoint_group="dividend_backfill",
        business_date="2026-05-28",
        ingestion_run_id="unit_dividend_backfill_20260528",
    )

    assert len(plan) == 1
    item = plan[0]
    assert item["endpoint_group"] == "dividend_backfill"
    assert item["endpoint"] == "dividend"
    assert item["api"] == "dividend"
    assert item["partition_endpoint"] == "dividend"
    assert item["partition_date"] == "20260528"
    assert item["business_date_field"] == "ex_date"
    assert item["request_date_param"] == "ex_date"
    assert item["schema_contract"].endswith("configs/ingestion/schema_contracts/dividend.json")
    assert item["schema_contract_exists"] is True
    assert item["gcs_prefix"] == (
        "a-share/tushare/raw_data/api=dividend/endpoint=dividend/"
        "partition_date=20260528/"
    )
    assert _build_request_groups(item, "20260528") == [{"ex_date": "20260528"}]
