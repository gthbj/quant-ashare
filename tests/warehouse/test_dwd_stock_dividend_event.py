from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DWD_SQL = REPO_ROOT / "sql/dwd/12_dwd_stock_dividend_event.sql"
QA_SQL = REPO_ROOT / "sql/qa/14_corporate_action_event_checks.sql"
FIXTURE = REPO_ROOT / "tests/fixtures/corporate_actions/dividend_duplicate_events.json"
MANIFEST = REPO_ROOT / "dataform/action_manifest.json"


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    return f"{value[:4]}-{value[4:6]}-{value[6:]}"


def _decimal(value: object | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _canonicalize(rows: list[dict[str, object]]) -> dict[str, object]:
    record_dates = sorted({_parse_date(row.get("record_date")) for row in rows if row.get("record_date")})
    end_dates = sorted({_parse_date(row.get("end_date")) for row in rows if row.get("end_date")})
    ann_dates = sorted({_parse_date(row.get("ann_date")) for row in rows if row.get("ann_date")})

    return {
        "source_event_count": len(rows),
        "cash_div_per_share_pretax": sum(_decimal(row.get("cash_div_tax")) for row in rows),
        "bonus_ratio": sum(_decimal(row.get("stk_bo_rate")) for row in rows),
        "conversion_ratio": sum(_decimal(row.get("stk_co_rate")) for row in rows),
        "record_date": record_dates[-1],
        "source_end_dates": end_dates,
        "source_ann_dates": ann_dates,
    }


def test_duplicate_event_fixture_canonicalizes_by_sec_code_ex_date() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    for case in fixture["cases"]:
        rows = case["rows"]
        assert len(rows) > 1
        assert {row["ts_code"] for row in rows} == {case["sec_code"]}
        assert {_parse_date(row["ex_date"]) for row in rows} == {case["ex_date"]}
        assert {row["partition_date"] for row in rows} == {case["ex_date"].replace("-", "")}
        assert {row["div_proc"].strip() for row in rows} == {"实施"}

        actual = _canonicalize(rows)
        expected = case["expected"]
        assert actual["source_event_count"] == expected["source_event_count"]
        assert actual["cash_div_per_share_pretax"] == Decimal(expected["cash_div_per_share_pretax"])
        assert actual["bonus_ratio"] == Decimal(expected["bonus_ratio"])
        assert actual["conversion_ratio"] == Decimal(expected["conversion_ratio"])
        assert actual["record_date"] == expected["record_date"]
        assert actual["source_end_dates"] == expected["source_end_dates"]
        assert actual["source_ann_dates"] == expected["source_ann_dates"]


def test_dwd_dividend_event_sql_pins_canonical_contract() -> None:
    sql = DWD_SQL.read_text(encoding="utf-8")

    assert "CREATE OR REPLACE TABLE `data-aquarium.ashare_dwd.dwd_stock_dividend_event`" in sql
    assert "PARTITION BY DATE_TRUNC(ex_date, MONTH)" in sql
    assert "CLUSTER BY sec_code" in sql
    assert "`data-aquarium.ashare_ods.ods_tushare_dividend`" in sql
    assert "endpoint = 'dividend'" in sql
    assert "partition_date BETWEEN FORMAT_DATE('%Y%m%d', event_start_date)" in sql
    assert "TRIM(COALESCE(div_proc, '')) = '实施'" in sql
    assert "SAFE_CAST(cash_div_tax AS FLOAT64) AS cash_div_per_share_pretax" in sql
    assert "SUM(COALESCE(cash_div_per_share_pretax, 0.0)) AS cash_div_per_share_pretax" in sql
    assert "SUM(COALESCE(bonus_ratio, 0.0)) AS bonus_ratio" in sql
    assert "SUM(COALESCE(conversion_ratio, 0.0)) AS conversion_ratio" in sql
    assert "COUNT(*) AS source_event_count" in sql
    assert "ARRAY_AGG(DISTINCT report_period IGNORE NULLS ORDER BY report_period)" in sql


def test_corporate_action_event_qa_cross_checks_hfq_factor_jump() -> None:
    sql = QA_SQL.read_text(encoding="utf-8")

    assert "QA-CA-EVENT-1" in sql
    assert "QA-CA-EVENT-6" in sql
    assert "`data-aquarium.ashare_meta.qa_stock_dividend_event_hfq_mismatch`" in sql
    assert "`data-aquarium.ashare_dwd.v_dwd_stock_dividend_event_ledger_consumable`" in sql
    assert "prev_close * (1.0 + e.split_ratio)" in sql
    assert "prev_close - e.cash_div_per_share_pretax" in sql
    assert "SAFE_DIVIDE(xp.ex_adj_factor, pp.prev_adj_factor)" in sql
    assert "p_factor_abs_tolerance" in sql
    assert "p_factor_rel_tolerance" in sql
    assert "p_ex_right_reference_rounding_cny" in sql
    assert "rounding_rel_tolerance_floor" in sql
    assert "check_direction" in sql
    assert "'event_to_factor'" in sql
    assert "'factor_to_event'" in sql
    assert "orphan_factor_jump_without_dividend_event" in sql
    assert "same_day_orphan_corporate_action" in sql
    assert "special_dividend" in sql
    assert "data_anomaly" in sql
    assert "unclassified" in sql
    assert "600188.SH" in sql
    assert "601966.SH" in sql


def test_dataform_manifest_registers_dividend_event_source_action_and_qa() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source_names = {source["name"] for source in manifest["sources"]}
    actions = {action["name"]: action for action in manifest["actions"]}

    assert "ods_tushare_dividend" in source_names
    assert actions["dwd_stock_dividend_event"]["sql"] == "sql/dwd/12_dwd_stock_dividend_event.sql"
    assert "ods_tushare_dividend" in actions["dwd_stock_dividend_event"]["dependencies"]
    assert "dwd_stock_dividend_event" in actions["core_table_column_descriptions"]["dependencies"]
    assert "dwd_stock_dividend_event" in actions["unit_contract_checks"]["dependencies"]
    assert actions["corporate_action_event_checks"]["sql"] == "sql/qa/14_corporate_action_event_checks.sql"
    assert set(actions["corporate_action_event_checks"]["dependencies"]) == {
        "dim_trade_calendar",
        "dwd_stock_dividend_event",
        "dwd_stock_eod_price",
    }
