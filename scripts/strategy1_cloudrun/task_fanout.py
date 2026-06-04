"""Shared helpers for Strategy 1 Cloud Run task fan-out training."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.strategy1_cloudrun.bq_io import (
    download_gcs_file,
    download_gcs_prefix,
    join_gs_uri,
    run_safe,
    write_json,
)
from scripts.strategy1_cloudrun.config import Experiment, RunnerConfig


MATRIX_MANIFEST_VERSION = "strategy1_task_fanout_matrix_v1"
WORK_UNITS_MANIFEST_VERSION = "strategy1_task_fanout_work_units_v1"


def candidate_grid_hash(config: RunnerConfig) -> str:
    payload = json.dumps(list(config.candidate_grid), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def default_matrix_id(config: RunnerConfig, experiment: Experiment) -> str:
    return f"{run_safe(experiment.run_id)}__matrix_{candidate_grid_hash(config)}"


def matrix_artifact_uri(config: RunnerConfig, experiment: Experiment, matrix_id: str) -> str:
    return join_gs_uri(
        config.model_artifact_base_uri,
        "ml_pv_clf_v0",
        f"run_id={experiment.run_id}",
        f"matrix_id={matrix_id}",
    )


def matrix_local_dir(config: RunnerConfig, experiment: Experiment, matrix_id: str) -> Path:
    return (
        Path(config.local_mirror_root)
        / "models"
        / "ml_pv_clf_v0"
        / f"run_id={experiment.run_id}"
        / f"matrix_id={matrix_id}"
    )


def candidate_local_dir(matrix_dir: Path, unit_index: int) -> Path:
    return matrix_dir / "candidates" / f"unit_index={unit_index}"


def candidate_output_uri(matrix_uri: str, unit_index: int) -> str:
    return join_gs_uri(matrix_uri, "candidates", f"unit_index={unit_index}")


def build_work_units(config: RunnerConfig, experiment: Experiment, matrix_uri: str) -> dict[str, Any]:
    units = []
    for idx, candidate in enumerate(config.candidate_grid):
        candidate_id = str(candidate["candidate_id"])
        units.append({
            "unit_index": idx,
            "unit_id": f"candidate={candidate_id}",
            "unit_type": "candidate_train",
            "candidate_id": candidate_id,
            "model_params": dict(candidate),
            "output_uri": candidate_output_uri(matrix_uri, idx),
            "experiment_id": experiment.experiment_id,
            "run_id": experiment.run_id,
        })
    return {
        "manifest_version": WORK_UNITS_MANIFEST_VERSION,
        "run_id": experiment.run_id,
        "experiment_id": experiment.experiment_id,
        "matrix_id": None,
        "unit_type": "candidate_train",
        "work_unit_count": len(units),
        "units": units,
    }


def stamp_work_units(work_units: dict[str, Any], matrix_id: str, matrix_uri: str) -> dict[str, Any]:
    payload = json.loads(json.dumps(work_units, ensure_ascii=False, default=str))
    payload["matrix_id"] = matrix_id
    for unit in payload.get("units", []):
        unit["matrix_id"] = matrix_id
        unit["matrix_uri"] = matrix_uri
    payload["work_units_sha256"] = sha256_json({k: v for k, v in payload.items() if k != "work_units_sha256"})
    return payload


def sha256_json(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)


def ensure_matrix_local(
    *,
    project: str,
    matrix_uri: str,
    matrix_local: str | Path | None,
    required_files: list[str] | None = None,
) -> Path:
    if matrix_local:
        return Path(matrix_local)
    tmp = Path(tempfile.mkdtemp(prefix="strategy1-matrix-"))
    if required_files is None:
        download_gcs_prefix(project, matrix_uri, tmp)
        return tmp
    for rel in required_files:
        download_gcs_file(project, join_gs_uri(matrix_uri, rel), tmp / rel)
    return tmp


def resolve_task_index(args_task_index: int | None) -> int:
    if args_task_index is not None:
        return args_task_index
    raw = os.environ.get("CLOUD_RUN_TASK_INDEX")
    if raw is None:
        raise ValueError("CLOUD_RUN_TASK_INDEX is not set; pass --task-index for local runs")
    return int(raw)


def resolve_global_unit_index(task_index: int, task_index_offset: int) -> int:
    if task_index < 0:
        raise ValueError("task index must be >= 0")
    if task_index_offset < 0:
        raise ValueError("task index offset must be >= 0")
    return task_index_offset + task_index


def load_work_unit(work_units: dict[str, Any], unit_index: int) -> dict[str, Any]:
    matches = [unit for unit in work_units.get("units", []) if int(unit.get("unit_index")) == unit_index]
    if len(matches) != 1:
        raise ValueError(f"unit_index={unit_index} matched {len(matches)} work units")
    return matches[0]
