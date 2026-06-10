from __future__ import annotations

from quant_ashare.strategy1.catalog import repo_path


def _read(path: str) -> str:
    return repo_path(path).read_text(encoding="utf-8")


def test_ads_summary_identity_additive_migration_exists() -> None:
    sql = _read("sql/ads/04_alter_strategy1_backtest_summary_identity_columns.sql")

    assert "ALTER TABLE `data-aquarium.ashare_ads.ads_backtest_performance_summary`" in sql
    assert "ADD COLUMN IF NOT EXISTS run_id STRING" in sql
    assert "ADD COLUMN IF NOT EXISTS created_date DATE" in sql


def test_reporting_summary_insert_populates_run_identity_columns() -> None:
    sql = _read("sql/strategy1/reporting/build_metrics_and_report_inputs.sql")

    assert "(backtest_id, strategy_id, model_id, run_id, start_date, end_date," in sql
    assert "cost_bps, metrics_json, created_date, created_at)" in sql
    assert "p_backtest_id, p_strategy_id, p_selected_model_id, p_run_id," in sql
    assert "CURRENT_DATE(),\n  CURRENT_TIMESTAMP()" in sql


def test_runner_qa_requires_summary_identity_columns() -> None:
    sql = _read("sql/strategy1/qa/qa_runner_outputs.sql")

    assert "QA-SUMMARY-1: summary row must include run_id and non-null created_date" in sql
    assert "LOGICAL_AND(bs.run_id = p_run_id)" in sql
    assert "LOGICAL_AND(bs.created_date IS NOT NULL)" in sql


def test_ads_schema_readiness_requires_summary_identity_columns() -> None:
    sql = _read("sql/strategy1/qa/qa_cloudrun_schema_readiness.sql")

    assert "STRUCT('ads_backtest_performance_summary', 'run_id', 'STRING')" in sql
    assert "STRUCT('ads_backtest_performance_summary', 'created_date', 'DATE')" in sql
    assert "sql/ads/04_alter_strategy1_backtest_summary_identity_columns.sql" in sql
