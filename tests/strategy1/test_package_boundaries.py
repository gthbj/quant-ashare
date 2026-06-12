from __future__ import annotations

import ast
from collections import Counter
import importlib
import os
from pathlib import Path
import subprocess
import sys
import textwrap

from quant_ashare.strategy1.legacy_names import (
    allowed_legacy_names,
    is_legacy_name_allowed,
    legacy_name_config,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
SRC_STRATEGY1_ROOT = REPO_ROOT / "src/quant_ashare/strategy1"

COMPAT_SYMBOLS = {
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
    "feature_sets": (
        "PV_FIN_RISK_FEATURE_SET_ID",
        "boolean_feature_names",
        "expected_feature_columns",
        "feature_delta_vs_base",
        "feature_metadata",
        "market_state_feature_names",
        "risk_feature_names",
    ),
    "preprocess": (
        "build_preprocessor",
        "feature_frame_from_panel",
    ),
    "training_panel": (
        "build_training_panel_params",
    ),
}


def test_strategy1_package_import_smoke_for_phase_e_boundaries() -> None:
    for module_name in (
        "quant_ashare.strategy1.acceptance",
        "quant_ashare.strategy1.annual_pipeline_scheduler",
        "quant_ashare.strategy1.annual_rolling_plan",
        "quant_ashare.strategy1.backtest_report",
        "quant_ashare.strategy1.bq_io",
        "quant_ashare.strategy1.config",
        "quant_ashare.strategy1.dataset_roles",
        "quant_ashare.strategy1.feature_sets",
        "quant_ashare.strategy1.ledger",
        "quant_ashare.strategy1.legacy_names",
        "quant_ashare.strategy1.pipeline_control",
        "quant_ashare.strategy1.prepare_matrix",
        "quant_ashare.strategy1.preprocess",
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
        "quant_ashare.strategy1.training_panel",
        "scripts.strategy1_cloudrun.bq_io",
        "scripts.strategy1_cloudrun.config",
        "scripts.strategy1_cloudrun.dataset_roles",
        "scripts.strategy1_cloudrun.feature_sets",
        "scripts.strategy1_cloudrun.preprocess",
        "scripts.strategy1_cloudrun.state",
        "scripts.strategy1_cloudrun.task_fanout",
        "scripts.strategy1_cloudrun.training_panel",
        "scripts.strategy1.promote_research_to_ads",
    ):
        assert importlib.import_module(module_name)


def test_strategy1_package_imports_without_repo_root_on_pythonpath(tmp_path: Path) -> None:
    code = textwrap.dedent(
        f"""
        import importlib
        import pkgutil
        import sys
        from pathlib import Path

        repo_root = Path({str(REPO_ROOT)!r}).resolve()
        for entry in sys.path:
            if entry and Path(entry).resolve() == repo_root:
                raise AssertionError(f"repo root leaked onto sys.path: {{entry}}")

        import quant_ashare.strategy1 as strategy1

        failures = []
        for module_info in pkgutil.walk_packages(strategy1.__path__, strategy1.__name__ + "."):
            try:
                importlib.import_module(module_info.name)
            except Exception as exc:
                failures.append(f"{{module_info.name}}: {{type(exc).__name__}}: {{exc}}")
        if failures:
            raise AssertionError("\\n".join(failures))
        """
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_ROOT)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


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


def test_cloudrun_shims_reexport_compatibility_symbol_snapshot() -> None:
    for module_name, symbols in COMPAT_SYMBOLS.items():
        wrapper_module = importlib.import_module(f"scripts.strategy1_cloudrun.{module_name}")
        package_module = importlib.import_module(f"quant_ashare.strategy1.{module_name}")
        for symbol in symbols:
            wrapper_value = getattr(wrapper_module, symbol)
            package_value = getattr(package_module, symbol)
            assert wrapper_value is package_value
            if hasattr(wrapper_value, "__module__"):
                assert wrapper_value.__module__ == f"quant_ashare.strategy1.{module_name}"


def test_strategy1_src_does_not_import_cloudrun_scripts() -> None:
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

    assert counts == Counter()


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
