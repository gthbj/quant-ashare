from __future__ import annotations

from quant_ashare.strategy1.catalog import load_step_catalog, repo_path
from quant_ashare.strategy1.sql_render import render_sql_step


RESUME_QA_STEPS = (
    "qa_ledger_resume_consistency",
    "qa_cloudrun_ledger_resume_outputs",
)

RESUME_QA_PARAMS = {
    "p_full_backtest_id": "bt_unit_full",
    "p_resume_backtest_id": "bt_unit_resume",
    "p_compare_start": "2025-01-02",
    "p_compare_end": "2026-06-09",
    "p_state_as_of_date": "2024-12-31",
    "p_resume_policy_id": "cloudrun_lot100_resume_v1",
    "p_ledger_version": "ledger_exec_v1_lot100",
    "p_rebalance_anchor_start": "2021-01-04",
    "p_cash_tolerance_cny": 1.0,
    "p_value_tolerance_cny": 1.0,
    "p_share_tolerance": 1e-6,
}


def test_resume_qa_catalog_contracts_are_live_research_steps() -> None:
    catalog = load_step_catalog()
    required_params = {
        "p_full_backtest_id",
        "p_resume_backtest_id",
        "p_compare_start",
        "p_compare_end",
        "p_state_as_of_date",
        "p_resume_policy_id",
        "p_ledger_version",
        "p_rebalance_anchor_start",
    }

    for step_name in RESUME_QA_STEPS:
        step = catalog["steps"][step_name]
        assert step["status"] == "active"
        assert step["execution_mode"] == "manual_resume_qa"
        assert required_params <= set(step["required_params"])
        assert "backtest_ledger_state_daily" in step["inputs"]


def test_resume_qa_steps_render_research_without_ads_residue() -> None:
    for step_name in RESUME_QA_STEPS:
        rendered = render_sql_step(
            step_name,
            RESUME_QA_PARAMS,
            dataset_role="research",
            allow_future_research=True,
        )

        assert "data-aquarium.ashare_ads." not in rendered
        assert "data-aquarium.ashare_research.research_backtest_ledger_state_daily" in rendered
        assert "next SSE open day after state_as_of_date" in rendered
        assert "DATE '2021-01-04'" in rendered
        assert "ledger_exec_v1_lot100" in rendered


def test_resume_consistency_qa_is_not_legacy_bqml_contract() -> None:
    sql = repo_path("sql/strategy1/qa/qa_ledger_resume_consistency.sql").read_text(encoding="utf-8")

    assert "Strategy 1 BQML Runner" not in sql
    assert "bt_s1_bqml_baseline" not in sql
    assert "p_ledger_version STRING DEFAULT 'ledger_exec_v1_lot100'" in sql
    assert "p_rebalance_anchor_start DATE DEFAULT NULL" in sql
    assert "ads_backtest_ledger_state_daily" in sql


def test_cloudrun_resume_qa_qualifies_diff_columns() -> None:
    sql = repo_path("sql/strategy1/qa/qa_cloudrun_ledger_resume_outputs.sql").read_text(encoding="utf-8")

    assert "FROM nav_diff AS diff" in sql
    assert "WHERE diff.nav_diff > 1e-10" in sql
    assert "FROM position_diff AS diff" in sql
    assert "FROM trade_diff AS diff" in sql
