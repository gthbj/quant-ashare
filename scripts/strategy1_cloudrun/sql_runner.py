"""Compatibility wrapper for Strategy1 SQL runner helpers."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists() and str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from quant_ashare.strategy1.sql_runner import (  # noqa: E402,F401
    main,
    render_sql,
    render_sql_step,
    render_value,
    resolve_sql_step_path,
    run_sql_script,
    run_sql_step,
)

__all__ = [
    "main",
    "render_sql",
    "render_sql_step",
    "render_value",
    "resolve_sql_step_path",
    "run_sql_script",
    "run_sql_step",
]
