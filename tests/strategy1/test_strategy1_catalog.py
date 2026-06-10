from __future__ import annotations

from pathlib import Path

import pytest

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
        resolve_table_role("model_registry")
        == "data-aquarium.ashare_ads.ads_model_registry"
    )
    assert (
        resolve_table_role("experiment_run_status")
        == "data-aquarium.ashare_meta.strategy1_experiment_run_status"
    )
    with pytest.raises(ValueError, match="dataset_role=research is not enabled"):
        resolve_table_role("model_registry", dataset_role="research")


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


def test_catalog_classifies_sql_16_to_25_individually() -> None:
    catalog = load_step_catalog()
    steps = catalog["steps"]

    assert steps["qa_cloudrun_runner_outputs"]["status"] == "active"
    assert steps["qa_acceptance_gate_v2_outputs"]["status"] == "audit_only"
    assert steps["qa_cloudrun_ledger_resume_outputs"]["execution_mode"] == "manual_resume_qa"
