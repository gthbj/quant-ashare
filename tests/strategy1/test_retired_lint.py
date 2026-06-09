from __future__ import annotations

from quant_ashare.strategy1.retired_lint import lint_retired_references


def test_retired_reference_linter_passes_active_scopes() -> None:
    assert lint_retired_references() == []

