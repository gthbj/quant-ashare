"""Compatibility wrapper for Strategy1 task fan-out helpers."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists() and str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from quant_ashare.strategy1.task_fanout import *  # noqa: E402,F401,F403
from quant_ashare.strategy1.task_fanout import (  # noqa: E402,F401
    MATRIX_MANIFEST_VERSION,
    WORK_UNITS_MANIFEST_VERSION,
    build_work_units,
    candidate_grid_hash,
    candidate_local_dir,
    candidate_output_uri,
    default_matrix_id,
    ensure_matrix_local,
    file_sha256,
    load_work_unit,
    matrix_artifact_uri,
    matrix_local_dir,
    read_json,
    resolve_global_unit_index,
    resolve_task_index,
    sha256_json,
    stamp_work_units,
    write_manifest,
    write_parquet,
)
