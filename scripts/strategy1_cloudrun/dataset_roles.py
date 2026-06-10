"""Compatibility wrapper for Strategy1 dataset-role helpers."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists() and str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from quant_ashare.strategy1.dataset_roles import (  # noqa: E402,F401
    DEFAULT_OUTPUT_DATASET_ROLE,
    DEFAULT_SQL_REWRITE_EXCLUDED_ROLES,
    OUTPUT_DATASET_ROLE_CHOICES,
    TableResolver,
    allow_future_research,
    output_dataset_role_cli_args,
    rewrite_sql_dataset_role,
    table_id,
    validate_output_dataset_role,
)

__all__ = [
    "DEFAULT_OUTPUT_DATASET_ROLE",
    "DEFAULT_SQL_REWRITE_EXCLUDED_ROLES",
    "OUTPUT_DATASET_ROLE_CHOICES",
    "TableResolver",
    "allow_future_research",
    "output_dataset_role_cli_args",
    "rewrite_sql_dataset_role",
    "table_id",
    "validate_output_dataset_role",
]
