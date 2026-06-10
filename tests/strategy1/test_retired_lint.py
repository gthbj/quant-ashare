from __future__ import annotations

import copy

from quant_ashare.strategy1.catalog import REPO_ROOT, load_step_catalog
from quant_ashare.strategy1.retired_lint import iter_scope_files, lint_retired_references


def test_retired_reference_linter_passes_active_scopes() -> None:
    assert lint_retired_references() == []


def test_retired_reference_linter_scans_recursive_active_scopes() -> None:
    catalog = load_step_catalog()
    lint_cfg = catalog["retired_reference_lint"]
    files = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in iter_scope_files(lint_cfg["active_scopes"], lint_cfg["historical_allowed_scopes"])
    }

    assert "scripts/strategy1_cloudrun/backtest_report.py" in files
    assert "sql/strategy1/qa/qa_runner_outputs.sql" in files


def test_retired_reference_linter_reports_active_scope_violations() -> None:
    catalog = copy.deepcopy(load_step_catalog())
    catalog["retired_reference_lint"] = {
        "active_scopes": ["scripts/strategy1_cloudrun/backtest_report.py"],
        "historical_allowed_scopes": [],
        "required_marker_for_historical_refs": [],
        "banned_active_refs": ["def build_sql_params("],
    }

    violations = lint_retired_references(catalog)

    assert len(violations) == 1
    assert violations[0].path == "scripts/strategy1_cloudrun/backtest_report.py"
