from __future__ import annotations

import copy

from quant_ashare.strategy1.catalog import REPO_ROOT, load_step_catalog
from quant_ashare.strategy1.retired_lint import iter_scope_files, lint_retired_references, matches_any


LEGACY_JOB_ENTRYPOINT_MODULES = (
    "scripts.strategy1_cloudrun.train_predict",
    "scripts.strategy1_cloudrun.prepare_matrix",
    "scripts.strategy1_cloudrun.train_candidate_task",
    "scripts.strategy1_cloudrun.select_register_predict",
    "scripts.strategy1_cloudrun.backtest_report",
)


def test_retired_reference_linter_passes_active_scopes() -> None:
    assert lint_retired_references() == []


def test_retired_reference_linter_scans_recursive_active_scopes() -> None:
    catalog = load_step_catalog()
    lint_cfg = catalog["retired_reference_lint"]
    files = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in iter_scope_files(lint_cfg["active_scopes"], lint_cfg["historical_allowed_scopes"])
    }

    assert "scripts/strategy1_cloudrun/orchestrate_experiments.py" in files
    assert "src/quant_ashare/strategy1/reporting.py" in files
    assert "sql/strategy1/qa/qa_runner_outputs.sql" in files


def test_retired_reference_linter_reports_active_scope_violations() -> None:
    catalog = copy.deepcopy(load_step_catalog())
    catalog["retired_reference_lint"] = {
        "active_scopes": ["src/quant_ashare/strategy1/reporting.py"],
        "historical_allowed_scopes": [],
        "required_marker_for_historical_refs": [],
        "banned_active_refs": ["def build_sql_params("],
    }

    violations = lint_retired_references(catalog)

    assert len(violations) == 1
    assert violations[0].path == "src/quant_ashare/strategy1/reporting.py"


def test_legacy_cloudrun_job_entrypoints_are_banned_from_active_scopes() -> None:
    catalog = load_step_catalog()
    lint_cfg = catalog["retired_reference_lint"]
    banned_refs = set(lint_cfg["banned_active_refs"])

    assert set(LEGACY_JOB_ENTRYPOINT_MODULES) <= banned_refs

    hits = []
    historical_scopes = lint_cfg["historical_allowed_scopes"]
    for path in iter_scope_files(lint_cfg["active_scopes"], historical_scopes):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if matches_any(rel, historical_scopes):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for ref in LEGACY_JOB_ENTRYPOINT_MODULES:
            if ref in text:
                hits.append(f"{rel}: {ref}")

    assert hits == []


def test_retired_reference_linter_reports_catalog_caller_violations() -> None:
    catalog = copy.deepcopy(load_step_catalog())
    catalog["retired_reference_lint"] = {
        "active_scopes": [],
        "historical_allowed_scopes": [],
        "required_marker_for_historical_refs": [],
        "banned_active_refs": ["scripts.strategy1_cloudrun.backtest_report"],
    }
    catalog["steps"]["build_candidates"]["caller"] = ["scripts.strategy1_cloudrun.backtest_report"]

    violations = lint_retired_references(catalog)

    assert len(violations) == 1
    assert violations[0].path == "configs/strategy1/active_step_catalog.yml"
    assert violations[0].line.endswith("scripts.strategy1_cloudrun.backtest_report")
