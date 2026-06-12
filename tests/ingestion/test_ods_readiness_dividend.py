from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ods_readiness_registers_dividend_as_weak_empty_ok() -> None:
    sql = (REPO_ROOT / "sql/qa/09_ods_daily_partition_readiness.sql").read_text()

    assert "-- dividend" in sql
    assert "'corporate_actions', 'dividend', 'weak', p_trade_partition, pd, FALSE, FALSE" in sql
    assert "`data-aquarium.ashare_ods.ods_tushare_dividend`" in sql
    assert "endpoint = 'dividend'" in sql
    assert "no dividend events on a given day" in sql
    assert "gate_type = 'weak' AND status = 'MISSING_REQUIRED'" in sql
