from pathlib import Path
from datetime import date

from scripts.ingestion.common import endpoint_runner
from scripts.ingestion.common.endpoint_runner import _build_request_groups
from scripts.ingestion.common.manifest import load_manifest
from scripts.ingestion.run_ingestion_job import ENDPOINT_GROUP_ALIASES, build_plan

REPO_ROOT = Path(__file__).resolve().parents[2]


LOOKBACK_DATES = [
    "2026-06-10",
    "2026-06-11",
    "2026-06-12",
    "2026-06-15",
    "2026-06-16",
]


def test_current_scope_alias_includes_corporate_actions_not_manual_backfill() -> None:
    assert ENDPOINT_GROUP_ALIASES["current_scope"] == [
        "market_eod",
        "index_eod",
        "dim_snapshot",
        "finance_recent",
        "corporate_actions",
    ]
    assert "dividend_backfill" not in ENDPOINT_GROUP_ALIASES["current_scope"]


def test_current_scope_dividend_expands_to_five_open_day_partitions() -> None:
    manifest = load_manifest(REPO_ROOT / "configs/ingestion/ods_current_scope_v0.yml")

    plan = build_plan(
        manifest=manifest,
        endpoint_group="corporate_actions",
        business_date="2026-06-16",
        ingestion_run_id="unit_current_scope_20260616",
        lookback_business_dates=LOOKBACK_DATES,
    )

    assert len(plan) == 5
    assert [item["partition_date"] for item in plan] == [
        "20260610",
        "20260611",
        "20260612",
        "20260615",
        "20260616",
    ]
    assert {item["endpoint_group"] for item in plan} == {"corporate_actions"}
    assert {item["endpoint"] for item in plan} == {"dividend"}
    assert {item["lookback_open_days"] for item in plan} == {5}
    assert {item["business_date_field"] for item in plan} == {"ex_date"}
    assert {item["request_date_param"] for item in plan} == {"ex_date"}
    assert all(item["gcs_prefix"].endswith(f"partition_date={item['partition_date']}/") for item in plan)
    assert [_build_request_groups(item, item["logical_date"]) for item in plan] == [
        [{"ex_date": "20260610"}],
        [{"ex_date": "20260611"}],
        [{"ex_date": "20260612"}],
        [{"ex_date": "20260615"}],
        [{"ex_date": "20260616"}],
    ]


def test_consecutive_current_scope_dividend_windows_recheck_prior_open_days() -> None:
    manifest = load_manifest(REPO_ROOT / "configs/ingestion/ods_current_scope_v0.yml")
    first_window = ["2026-06-09", "2026-06-10", "2026-06-11", "2026-06-12", "2026-06-15"]
    second_window = ["2026-06-10", "2026-06-11", "2026-06-12", "2026-06-15", "2026-06-16"]

    first_plan = build_plan(
        manifest=manifest,
        endpoint_group="corporate_actions",
        business_date="2026-06-15",
        ingestion_run_id="unit_current_scope_20260615",
        lookback_business_dates=first_window,
    )
    second_plan = build_plan(
        manifest=manifest,
        endpoint_group="corporate_actions",
        business_date="2026-06-16",
        ingestion_run_id="unit_current_scope_20260616",
        lookback_business_dates=second_window,
    )

    first_partitions = {item["partition_date"] for item in first_plan}
    second_partitions = {item["partition_date"] for item in second_plan}
    assert {"20260610", "20260611", "20260612", "20260615"}.issubset(first_partitions & second_partitions)


def test_current_scope_dividend_ingest_results_are_one_per_partition(monkeypatch) -> None:
    manifest = load_manifest(REPO_ROOT / "configs/ingestion/ods_current_scope_v0.yml")
    plan = build_plan(
        manifest=manifest,
        endpoint_group="corporate_actions",
        business_date="2026-06-16",
        ingestion_run_id="unit_current_scope_20260616",
        lookback_business_dates=LOOKBACK_DATES,
    )
    writes: list[dict[str, object]] = []

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, str]] = []

        def query(self, api: str, params: dict[str, str], fields: str) -> list[dict[str, object]]:
            assert api == "dividend"
            assert "ex_date" in params
            self.calls.append(dict(params))
            ex_date = params["ex_date"]
            return [
                {
                    "ts_code": "000001.SZ",
                    "end_date": "20251231",
                    "ann_date": ex_date,
                    "div_proc": "实施",
                    "stk_div": None,
                    "stk_bo_rate": None,
                    "stk_co_rate": None,
                    "cash_div": 0.1,
                    "cash_div_tax": 0.1,
                    "record_date": ex_date,
                    "ex_date": ex_date,
                    "pay_date": ex_date,
                    "div_listdate": None,
                    "imp_ann_date": ex_date,
                    "base_date": None,
                    "base_share": None,
                }
            ]

    def fake_write_parquet_to_gcs(**kwargs):
        assert kwargs["merge_existing"] is False
        writes.append(
            {
                "prefix": kwargs["prefix"],
                "row_count": len(kwargs["rows"]),
                "ingestion_run_id": kwargs["ingestion_run_id"],
            }
        )
        return f"gs://{kwargs['bucket']}/{kwargs['prefix']}data.parquet"

    monkeypatch.setattr(endpoint_runner, "write_parquet_to_gcs", fake_write_parquet_to_gcs)
    client = FakeClient()

    results = endpoint_runner.ingest_plan(
        client=client,
        plan=plan,
        business_date=date(2026, 6, 16),
        skip_gcs_write=False,
    )

    assert [call["ex_date"] for call in client.calls] == [
        "20260610",
        "20260611",
        "20260612",
        "20260615",
        "20260616",
    ]
    assert [result["partition_date"] for result in results] == [item["partition_date"] for item in plan]
    assert [result["logical_date"] for result in results] == [item["partition_date"] for item in plan]
    assert {result["status"] for result in results} == {"success"}
    assert len({result["request_params_hash"] for result in results}) == 5
    assert [write["row_count"] for write in writes] == [1, 1, 1, 1, 1]
    assert [write["prefix"].split("partition_date=", 1)[1] for write in writes] == [
        "20260610/",
        "20260611/",
        "20260612/",
        "20260615/",
        "20260616/",
    ]


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
