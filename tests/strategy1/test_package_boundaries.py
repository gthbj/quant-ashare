from __future__ import annotations

import importlib
from pathlib import Path

from quant_ashare.strategy1.legacy_names import (
    allowed_legacy_names,
    is_legacy_name_allowed,
    legacy_name_config,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_strategy1_package_import_smoke_for_phase_e_boundaries() -> None:
    for module_name in (
        "quant_ashare.strategy1.acceptance",
        "quant_ashare.strategy1.backtest_report",
        "quant_ashare.strategy1.dataset_roles",
        "quant_ashare.strategy1.ledger",
        "quant_ashare.strategy1.legacy_names",
        "quant_ashare.strategy1.pipeline_control",
        "quant_ashare.strategy1.prepare_matrix",
        "quant_ashare.strategy1.promotion",
        "quant_ashare.strategy1.reporting",
        "quant_ashare.strategy1.select_register_predict",
        "quant_ashare.strategy1.train_candidate_task",
        "quant_ashare.strategy1.train_predict",
        "scripts.strategy1_cloudrun.dataset_roles",
        "scripts.strategy1.promote_research_to_ads",
    ):
        assert importlib.import_module(module_name)


def test_cloudrun_wrappers_reexport_package_implementations() -> None:
    from scripts.strategy1_cloudrun import acceptance as acceptance_wrapper
    from scripts.strategy1_cloudrun import ledger as ledger_wrapper
    from scripts.strategy1_cloudrun import orchestrate_experiments as pipeline_wrapper

    assert acceptance_wrapper.load_acceptance_contract.__module__ == "quant_ashare.strategy1.acceptance"
    assert ledger_wrapper.LedgerParams.__module__ == "quant_ashare.strategy1.ledger"
    assert pipeline_wrapper.build_chain_steps.__module__ == "quant_ashare.strategy1.pipeline_control"


def test_retired_cloudrun_job_wrapper_files_are_removed() -> None:
    for rel_path in (
        "scripts/strategy1_cloudrun/train_predict.py",
        "scripts/strategy1_cloudrun/prepare_matrix.py",
        "scripts/strategy1_cloudrun/train_candidate_task.py",
        "scripts/strategy1_cloudrun/select_register_predict.py",
        "scripts/strategy1_cloudrun/backtest_report.py",
    ):
        assert not (REPO_ROOT / rel_path).exists()


def test_legacy_name_exception_registry_keeps_audit_fields_explicit() -> None:
    registry = allowed_legacy_names()

    assert "bqml_reference_run_id" in registry
    cfg = legacy_name_config("bqml_reference_run_id")
    assert "historical reference" in cfg["reason"]
    assert is_legacy_name_allowed(
        "bqml_reference_run_id",
        "scripts/strategy1_cloudrun/config.py",
    )
    assert not is_legacy_name_allowed(
        "bqml_reference_run_id",
        "src/quant_ashare/strategy1/promotion.py",
    )
