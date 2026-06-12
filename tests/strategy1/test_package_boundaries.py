from __future__ import annotations

import ast
from collections import Counter
import importlib
from pathlib import Path

from quant_ashare.strategy1.legacy_names import (
    allowed_legacy_names,
    is_legacy_name_allowed,
    legacy_name_config,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_STRATEGY1_ROOT = REPO_ROOT / "src/quant_ashare/strategy1"

BATCH2_COMPAT_SYMBOLS = {
    "bq_io": (
        "ADS",
        "LABEL_SAFE_RE",
        "LOCATION",
        "META",
        "RUN_SAFE_RE",
        "bq_label_value",
        "download_gcs_file",
        "download_gcs_prefix",
        "env_container_image",
        "execute_query",
        "get_git_commit",
        "job_audit_dict",
        "join_gs_uri",
        "json_dumps_strict",
        "load_dataframe",
        "make_client",
        "parse_gs_uri",
        "query_dataframe",
        "query_dataframe_with_job",
        "run_safe",
        "upload_directory_to_gcs",
        "write_json",
        "write_text",
    ),
    "config": (
        "DEFAULT_ACCEPTANCE_CONTRACT_PATH",
        "DEFAULT_ARTIFACT_BASE_URI",
        "DEFAULT_CONFIG_PATH",
        "DEFAULT_CORPORATE_ACTIONS",
        "DEFAULT_DIVIDEND_TAX_MODE",
        "DEFAULT_EXECUTION_BACKEND",
        "DEFAULT_LOCAL_MIRROR_ROOT",
        "DEFAULT_LOCK_BUCKET",
        "DEFAULT_LOCK_PREFIX",
        "DEFAULT_MANIFEST_PATH",
        "DEFAULT_MODEL_ARTIFACT_BASE_URI",
        "DEFAULT_OUTPUT_DATASET_ROLE",
        "DEFAULT_PROJECT",
        "DEFAULT_REGION",
        "DEFAULT_STRATEGY_ID",
        "Experiment",
        "OUTPUT_DATASET_ROLE_CHOICES",
        "RunnerConfig",
        "add_common_args",
        "apply_cli_overrides",
        "dump_resolved_manifest",
        "effective_candidate_parallelism",
        "experiment_from_b64",
        "experiment_to_b64",
        "filter_experiments",
        "load_manifest",
        "load_runner_config",
        "manifest_hash",
        "read_mapping",
        "resolve_parallel_count",
    ),
    "state": (
        "GcsLeaseLock",
        "LockConfig",
        "OrchestratorStatusTable",
        "StepStateSpec",
        "build_lock_key",
        "cancel_cloud_run_execution",
        "cloud_run_execution_state",
        "describe_cloud_run_execution",
        "experiment_params_json",
        "extract_cloud_run_execution_id",
        "scheduler_instance_id",
        "status_table_ref",
    ),
    "task_fanout": (
        "MATRIX_MANIFEST_VERSION",
        "build_work_units",
        "candidate_grid_hash",
        "candidate_local_dir",
        "candidate_output_uri",
        "default_matrix_id",
        "ensure_matrix_local",
        "file_sha256",
        "load_work_unit",
        "matrix_artifact_uri",
        "matrix_local_dir",
        "read_json",
        "resolve_global_unit_index",
        "resolve_task_index",
        "sha256_json",
        "stamp_work_units",
        "write_manifest",
        "write_parquet",
    ),
}

EXPECTED_BATCH2_REVERSE_IMPORT_COUNTS = Counter(
    {
        "feature_sets": 1,
        "orchestrate_annual_rolling_selection": 1,
        "preprocess": 3,
    }
)

BATCH2_REVERSE_IMPORT_ZERO_MODULES = {
    "__version__",
    "acceptance",
    "bq_io",
    "config",
    "dataset_roles",
    "state",
    "task_fanout",
}


def test_strategy1_package_import_smoke_for_phase_e_boundaries() -> None:
    for module_name in (
        "quant_ashare.strategy1.acceptance",
        "quant_ashare.strategy1.annual_pipeline_scheduler",
        "quant_ashare.strategy1.backtest_report",
        "quant_ashare.strategy1.bq_io",
        "quant_ashare.strategy1.config",
        "quant_ashare.strategy1.dataset_roles",
        "quant_ashare.strategy1.ledger",
        "quant_ashare.strategy1.legacy_names",
        "quant_ashare.strategy1.pipeline_control",
        "quant_ashare.strategy1.prepare_matrix",
        "quant_ashare.strategy1.promotion",
        "quant_ashare.strategy1.refit_register_predict",
        "quant_ashare.strategy1.reporting",
        "quant_ashare.strategy1.runner_version",
        "quant_ashare.strategy1.select_register_predict",
        "quant_ashare.strategy1.state",
        "quant_ashare.strategy1.synthetic_continuous",
        "quant_ashare.strategy1.tail_risk_overlay_ab",
        "quant_ashare.strategy1.task_fanout",
        "quant_ashare.strategy1.train_candidate_task",
        "quant_ashare.strategy1.train_predict",
        "scripts.strategy1_cloudrun.bq_io",
        "scripts.strategy1_cloudrun.config",
        "scripts.strategy1_cloudrun.dataset_roles",
        "scripts.strategy1_cloudrun.state",
        "scripts.strategy1_cloudrun.task_fanout",
        "scripts.strategy1.promote_research_to_ads",
    ):
        assert importlib.import_module(module_name)


def test_cloudrun_wrappers_reexport_package_implementations() -> None:
    from scripts.strategy1_cloudrun import acceptance as acceptance_wrapper
    from scripts.strategy1_cloudrun import ledger as ledger_wrapper
    from scripts.strategy1_cloudrun import orchestrate_experiments as pipeline_wrapper
    from scripts.strategy1_cloudrun import __version__
    from quant_ashare.strategy1.runner_version import __version__ as package_version

    assert acceptance_wrapper.load_acceptance_contract.__module__ == "quant_ashare.strategy1.acceptance"
    assert ledger_wrapper.LedgerParams.__module__ == "quant_ashare.strategy1.ledger"
    assert pipeline_wrapper.build_chain_steps.__module__ == "quant_ashare.strategy1.pipeline_control"
    assert __version__ == package_version == "strategy1_cloudrun_runner_v0_20260606_lot100"


def test_batch2_cloudrun_shims_reexport_compatibility_symbol_snapshot() -> None:
    for module_name, symbols in BATCH2_COMPAT_SYMBOLS.items():
        wrapper_module = importlib.import_module(f"scripts.strategy1_cloudrun.{module_name}")
        package_module = importlib.import_module(f"quant_ashare.strategy1.{module_name}")
        for symbol in symbols:
            wrapper_value = getattr(wrapper_module, symbol)
            package_value = getattr(package_module, symbol)
            assert wrapper_value is package_value
            if hasattr(wrapper_value, "__module__"):
                assert wrapper_value.__module__ == f"quant_ashare.strategy1.{module_name}"


def test_batch2_src_reverse_import_counts_are_limited_to_batch3() -> None:
    counts: Counter[str] = Counter()
    for path in SRC_STRATEGY1_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "scripts.strategy1_cloudrun":
                    for alias in node.names:
                        counts["__version__" if alias.name == "__version__" else alias.name] += 1
                elif module.startswith("scripts.strategy1_cloudrun."):
                    name = module.removeprefix("scripts.strategy1_cloudrun.").split(".")[0]
                    counts[name] += 1
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "scripts.strategy1_cloudrun":
                        counts["<package>"] += 1
                    elif alias.name.startswith("scripts.strategy1_cloudrun."):
                        name = alias.name.removeprefix("scripts.strategy1_cloudrun.").split(".")[0]
                        counts[name] += 1

    assert counts == EXPECTED_BATCH2_REVERSE_IMPORT_COUNTS
    for module_name in BATCH2_REVERSE_IMPORT_ZERO_MODULES:
        assert counts[module_name] == 0


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
