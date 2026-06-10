from __future__ import annotations

import re
from pathlib import Path

from quant_ashare.strategy1.catalog import (
    load_step_catalog,
    repo_path,
    resolve_step_path,
    step_name_for_path,
    validate_catalog,
)
from quant_ashare.strategy1.table_roles import resolve_table_role


ADS_REF_RE = re.compile(r"data-aquarium\.ashare_ads\.[A-Za-z0-9_]+")
LEDGER_STATE_DDL_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"`data-aquarium\.ashare_ads\.ads_backtest_ledger_state_daily`\s*"
    r"\((?P<body>.*?)\)\s*PARTITION BY",
    re.DOTALL,
)
DDL_COLUMN_RE = re.compile(r"^\s+([A-Za-z_][A-Za-z0-9_]*)\s+[A-Z0-9_]+", re.MULTILINE)


def test_catalog_validates_paths_and_declared_params() -> None:
    assert validate_catalog() == []


def test_legacy_paths_resolve_to_stable_strategy1_namespace() -> None:
    catalog = load_step_catalog()

    assert step_name_for_path("sql/ml/strategy1/05_build_candidates.sql", catalog) == "build_candidates"
    resolved = resolve_step_path("sql/ml/strategy1/05_build_candidates.sql", catalog)

    assert resolved == Path.cwd() / "sql/strategy1/execution/build_candidates.sql"


def test_table_role_resolver_defaults_to_research_first_and_keeps_explicit_ads() -> None:
    assert (
        resolve_table_role("model_registry")
        == "data-aquarium.ashare_research.research_model_registry"
    )
    assert (
        resolve_table_role("model_registry", dataset_role="ads")
        == "data-aquarium.ashare_ads.ads_model_registry"
    )
    assert (
        resolve_table_role("experiment_run_status", dataset_role="ads")
        == "data-aquarium.ashare_meta.strategy1_experiment_run_status"
    )
    assert (
        resolve_table_role("experiment_run_status")
        == "data-aquarium.ashare_research.research_experiment_run_status"
    )


def test_single_output_step_partition_columns_match_output_role() -> None:
    catalog = load_step_catalog()
    table_roles = catalog["table_roles"]

    for step_name, cfg in catalog["steps"].items():
        outputs = cfg.get("outputs") or []
        if len(outputs) != 1:
            continue
        step_partition_columns = cfg.get("partition_columns") or []
        role_partition_columns = table_roles[outputs[0]].get("partition_columns") or []
        assert step_partition_columns == role_partition_columns, step_name


def test_step_role_contract_covers_ads_sql_references() -> None:
    catalog = load_step_catalog()
    source_to_roles: dict[str, set[str]] = {}
    for role in catalog["table_roles"]:
        source_to_roles.setdefault(resolve_table_role(role, dataset_role="ads", catalog=catalog), set()).add(role)

    failures: list[str] = []
    for step_name, cfg in catalog["steps"].items():
        if cfg.get("status") == "retired":
            continue
        sql_path = repo_path(cfg.get("sql_path") or cfg["target_path"])
        actual_sources = set(ADS_REF_RE.findall(sql_path.read_text(encoding="utf-8")))
        declared_roles = set(cfg.get("inputs") or []) | set(cfg.get("outputs") or [])
        covered_sources = {
            resolve_table_role(role, dataset_role="ads", catalog=catalog)
            for role in declared_roles
            if role in catalog["table_roles"]
        }
        missing_sources = sorted(actual_sources - covered_sources)
        if missing_sources:
            missing_roles = {
                source: sorted(source_to_roles.get(source, []))
                for source in missing_sources
            }
            failures.append(f"{step_name}: missing ADS role coverage {missing_roles}")

    assert failures == []


def test_catalog_classifies_sql_16_to_25_individually() -> None:
    catalog = load_step_catalog()
    steps = catalog["steps"]

    assert steps["qa_cloudrun_runner_outputs"]["status"] == "active"
    assert steps["qa_acceptance_gate_v2_outputs"]["status"] == "audit_only"
    assert steps["qa_cloudrun_ledger_resume_outputs"]["execution_mode"] == "manual_resume_qa"


def test_ledger_state_additive_migration_matches_canonical_ads_contract() -> None:
    canonical_columns = _ledger_state_columns("sql/ads/01_ads_strategy1_tables.sql")
    additive_columns = _ledger_state_columns("sql/ads/03_create_strategy1_backtest_ledger_state_daily.sql")

    assert additive_columns == canonical_columns


def _ledger_state_columns(path: str) -> list[str]:
    sql = repo_path(path).read_text(encoding="utf-8")
    match = LEDGER_STATE_DDL_RE.search(sql)
    assert match is not None, path
    return DDL_COLUMN_RE.findall(match.group("body"))
