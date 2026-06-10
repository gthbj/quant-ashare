from __future__ import annotations

import re
from pathlib import Path

import pytest

from quant_ashare.strategy1.catalog import load_step_catalog
from quant_ashare.strategy1.table_roles import resolve_table_role


REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_CONTRACT_SQL = REPO_ROOT / "sql/research/01_research_strategy1_tables.sql"
RESEARCH_MIGRATION_SQL = REPO_ROOT / "sql/research/02_research_strategy1_additive_migrations.sql"
RESEARCH_READINESS_SQL = REPO_ROOT / "sql/research/03_qa_research_schema_readiness.sql"


CREATE_TABLE_RE = re.compile(
    r"CREATE TABLE IF NOT EXISTS `data-aquarium\.ashare_research\.(research_[A-Za-z0-9_]+)`"
)
PARTITION_RE = re.compile(r"PARTITION BY DATE_TRUNC\(([A-Za-z0-9_]+), MONTH\)")
DDL_COLUMN_RE = re.compile(r"^\s+([A-Za-z_][A-Za-z0-9_]*)\s+(?:ARRAY<[^>]+>|[A-Z]+)", re.MULTILINE)
ALTER_LOG_DIR_RE = re.compile(
    r"ALTER\s+TABLE\s+`data-aquarium\.ashare_research\.research_experiment_run_status`"
    r"\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+log_dir\s+STRING",
    re.IGNORECASE,
)


def _research_sql() -> str:
    return RESEARCH_CONTRACT_SQL.read_text(encoding="utf-8")


def _research_readiness_sql() -> str:
    return RESEARCH_READINESS_SQL.read_text(encoding="utf-8")


def _research_tables() -> set[str]:
    return set(CREATE_TABLE_RE.findall(_research_sql()))


def _table_block(table_name: str) -> str:
    sql = _research_sql()
    marker = f"`data-aquarium.ashare_research.{table_name}`"
    start = sql.index(marker)
    next_match = CREATE_TABLE_RE.search(sql, start + len(marker))
    return sql[start : next_match.start() if next_match else len(sql)]


def test_catalog_research_tables_have_contracts() -> None:
    catalog = load_step_catalog()
    expected = {
        cfg["research_table"]
        for cfg in catalog["table_roles"].values()
        if cfg.get("research_table")
    }
    actual = _research_tables()

    assert expected <= actual
    assert all(table.startswith("research_") for table in actual)
    assert "research_promotion_manifest" in actual


def test_research_contract_partitions_match_catalog_roles() -> None:
    catalog = load_step_catalog()

    for role_name, cfg in catalog["table_roles"].items():
        research_table = cfg.get("research_table")
        partition_columns = cfg.get("partition_columns") or []
        if not research_table or not partition_columns:
            continue

        block = _table_block(research_table)
        partition_match = PARTITION_RE.search(block)
        assert partition_match, f"{role_name}: {research_table} is missing PARTITION BY"
        assert partition_match.group(1) == partition_columns[0]


def test_acceptance_contract_separates_acceptance_from_promotion() -> None:
    block = _table_block("research_acceptance_result")

    assert "acceptance_status STRING" in block
    assert "accepted BOOL" in block
    assert "promotion_status STRING" in block
    assert "promoted BOOL" in block
    assert "promotion_manifest_id STRING" in block


def test_research_lifecycle_columns_have_explicit_defaults() -> None:
    tables = _research_tables()
    research_status_tables = []
    promotion_lifecycle_tables = []

    for table in tables:
        block = _table_block(table)
        if "research_status STRING" in block:
            research_status_tables.append(table)
            assert "research_status STRING DEFAULT 'candidate'" in block, table
        if table != "research_promotion_manifest" and "promotion_status STRING" in block:
            promotion_lifecycle_tables.append(table)
            assert "promotion_status STRING DEFAULT 'not_promoted'" in block, table

    assert research_status_tables
    assert promotion_lifecycle_tables

    manifest_block = _table_block("research_promotion_manifest")
    assert "promotion_status STRING DEFAULT 'planned'" in manifest_block
    assert "not_promoted/promoted/deprecated" in _table_block("research_acceptance_result")


def test_research_status_contract_covers_runtime_upsert_columns() -> None:
    block = _table_block("research_experiment_run_status")
    actual_columns = set(DDL_COLUMN_RE.findall(block))
    runtime_upsert_columns = {
        "experiment_id",
        "run_id",
        "prediction_run_id",
        "backtest_id",
        "stage_id",
        "experiment_group",
        "experiment_type",
        "step_id",
        "step_display_name",
        "status",
        "status_reason",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
        "job_id",
        "attempt",
        "force_replace",
        "lock_key",
        "lock_owner",
        "lock_acquired_at",
        "lock_expires_at",
        "last_heartbeat_at",
        "artifact_uri",
        "report_uri",
        "diagnosis_uri",
        "diagnosis_status",
        "qa_status",
        "manifest_path",
        "manifest_hash",
        "params_json",
        "runner_version",
        "scheduler_instance_id",
        "log_dir",
        "error_message",
    }

    assert runtime_upsert_columns <= actual_columns


def test_promotion_manifest_records_target_and_completion_fields() -> None:
    block = _table_block("research_promotion_manifest")

    assert "target_dataset STRING" in block
    assert "target_ads_tables ARRAY<STRING>" in block
    assert "approved_by STRING" in block
    assert "approved_at TIMESTAMP" in block
    assert "promoted_at TIMESTAMP" in block


def test_research_role_resolver_is_contract_only_in_current_phase() -> None:
    with pytest.raises(ValueError, match="dataset_role=research is not enabled"):
        resolve_table_role("model_prediction_daily", dataset_role="research")

    assert (
        resolve_table_role(
            "model_prediction_daily",
            dataset_role="research",
            allow_future_research=True,
        )
        == "data-aquarium.ashare_research.research_model_prediction_daily"
    )
    assert (
        resolve_table_role(
            "experiment_run_status",
            dataset_role="research",
            allow_future_research=True,
        )
        == "data-aquarium.ashare_research.research_experiment_run_status"
    )


def test_research_dataset_role_points_to_d0_contract() -> None:
    catalog = load_step_catalog()
    research_role = catalog["dataset_roles"]["research"]

    assert research_role["dataset"] == "ashare_research"
    assert research_role["enabled_by_default"] is False
    assert research_role["contract_sql"] == "sql/research/01_research_strategy1_tables.sql"
    assert (REPO_ROOT / research_role["contract_sql"]).exists()


def test_research_additive_migration_propagates_runtime_log_dir() -> None:
    contract_block = _table_block("research_experiment_run_status")
    migration_sql = RESEARCH_MIGRATION_SQL.read_text(encoding="utf-8")

    assert "log_dir STRING" in contract_block
    assert ALTER_LOG_DIR_RE.search(migration_sql)
    assert "CREATE OR REPLACE" not in migration_sql.upper()


def test_research_schema_readiness_is_cataloged_and_covers_all_tables() -> None:
    catalog = load_step_catalog()
    step = catalog["steps"]["qa_research_schema_readiness"]
    readiness_sql = _research_readiness_sql()

    assert step["sql_path"] == "sql/research/03_qa_research_schema_readiness.sql"
    assert step["execution_mode"] == "manual_schema_readiness_qa"
    assert (REPO_ROOT / step["sql_path"]).exists()

    readiness_tables = set(re.findall(r"'(research_[A-Za-z0-9_]+)'", readiness_sql))
    assert _research_tables() <= readiness_tables
    assert "data-aquarium`.ashare_research.INFORMATION_SCHEMA" in readiness_sql


def test_research_schema_readiness_checks_lifecycle_defaults_and_log_dir() -> None:
    readiness_sql = _research_readiness_sql()

    assert "expected_defaults" in readiness_sql
    assert "\"'candidate'\"" in readiness_sql
    assert "\"'not_promoted'\"" in readiness_sql
    assert "\"'planned'\"" in readiness_sql
    assert "STRUCT('research_experiment_run_status', 'log_dir', 'STRING')" in readiness_sql
    assert "QA-RESEARCH-SCHEMA-7" in readiness_sql
    assert "require_partition_filter" in readiness_sql
    assert "clustering_ordinal_position" in readiness_sql
