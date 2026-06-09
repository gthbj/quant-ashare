from __future__ import annotations

from pathlib import Path

from quant_ashare.strategy1.catalog import (
    load_step_catalog,
    resolve_step_path,
    step_name_for_path,
    validate_catalog,
)
from quant_ashare.strategy1.table_roles import resolve_table_role


def test_catalog_validates_paths_and_declared_params() -> None:
    assert validate_catalog() == []


def test_legacy_paths_resolve_to_stable_strategy1_namespace() -> None:
    catalog = load_step_catalog()

    assert step_name_for_path("sql/ml/strategy1/05_build_candidates.sql", catalog) == "build_candidates"
    resolved = resolve_step_path("sql/ml/strategy1/05_build_candidates.sql", catalog)

    assert resolved == Path.cwd() / "sql/strategy1/execution/build_candidates.sql"


def test_table_role_resolver_stays_ads_in_current_phase() -> None:
    assert (
        resolve_table_role("model_registry", dataset_role="research")
        == "data-aquarium.ashare_ads.ads_model_registry"
    )


def test_catalog_classifies_sql_16_to_25_individually() -> None:
    catalog = load_step_catalog()
    steps = catalog["steps"]

    assert steps["qa_cloudrun_runner_outputs"]["status"] == "active"
    assert steps["qa_acceptance_gate_v2_outputs"]["status"] == "audit_only"
    assert steps["qa_cloudrun_ledger_resume_outputs"]["execution_mode"] == "manual_resume_qa"

