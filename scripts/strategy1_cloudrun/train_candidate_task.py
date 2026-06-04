#!/usr/bin/env python3
"""Train one Strategy 1 sklearn candidate in a Cloud Run Job task."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from scripts.strategy1_cloudrun import __version__
from scripts.strategy1_cloudrun.bq_io import (
    env_container_image,
    get_git_commit,
    join_gs_uri,
    upload_directory_to_gcs,
    write_json,
)
from scripts.strategy1_cloudrun.config import add_common_args, apply_cli_overrides, load_runner_config
from scripts.strategy1_cloudrun.task_fanout import (
    candidate_local_dir,
    ensure_matrix_local,
    file_sha256,
    load_work_unit,
    read_json,
    resolve_global_unit_index,
    resolve_task_index,
)
from scripts.strategy1_cloudrun.train_predict import train_candidate_from_matrices


def main() -> int:
    args = parse_args()
    config = apply_cli_overrides(load_runner_config(args.config), args)
    matrix_local = ensure_matrix_local(
        project=config.project,
        matrix_uri=args.matrix_uri,
        matrix_local=args.matrix_local_dir,
        required_files=[
            "matrix_manifest.json",
            "work_units.json",
            "feature_schema.json",
            "preprocess_stats.json",
            "train_features.parquet",
            "train_labels.parquet",
            "valid_features.parquet",
            "valid_labels.parquet",
        ] if not args.dry_run else ["work_units.json"],
    )
    task_index = resolve_task_index(args.task_index)
    global_unit_index = resolve_global_unit_index(task_index, args.task_index_offset)
    work_units = read_json(matrix_local / "work_units.json")
    unit = load_work_unit(work_units, global_unit_index)
    plan = {
        "entrypoint": "train_candidate_task",
        "runner_version": __version__,
        "project": config.project,
        "region": config.region,
        "matrix_uri": args.matrix_uri,
        "matrix_local_dir": str(matrix_local),
        "cloud_run_task_index": task_index,
        "task_index_offset": args.task_index_offset,
        "global_unit_index": global_unit_index,
        "unit": unit,
        "skip_gcs_upload": args.skip_gcs_upload,
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2, default=str))
        return 0
    result = train_candidate_unit(
        config=config,
        matrix_local=matrix_local,
        matrix_uri=args.matrix_uri,
        unit=unit,
        cloud_run_task_index=task_index,
        task_index_offset=args.task_index_offset,
        skip_gcs_upload=args.skip_gcs_upload,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train one Strategy 1 candidate from a frozen matrix")
    add_common_args(parser)
    parser.add_argument("--matrix-uri", required=True)
    parser.add_argument("--matrix-local-dir", default=None)
    parser.add_argument("--task-index", type=int, default=None, help="Local override for CLOUD_RUN_TASK_INDEX")
    parser.add_argument("--task-index-offset", type=int, default=0)
    parser.add_argument("--skip-gcs-upload", action="store_true")
    return parser.parse_args()


def train_candidate_unit(
    *,
    config,
    matrix_local: Path,
    matrix_uri: str,
    unit: dict[str, Any],
    cloud_run_task_index: int,
    task_index_offset: int,
    skip_gcs_upload: bool,
) -> dict[str, Any]:
    manifest = read_json(matrix_local / "matrix_manifest.json")
    feature_schema = read_json(matrix_local / "feature_schema.json")
    preprocess_stats = read_json(matrix_local / "preprocess_stats.json")
    unit_index = int(unit["unit_index"])
    out_dir = candidate_local_dir(matrix_local, unit_index)
    out_uri = unit.get("output_uri") or join_gs_uri(matrix_uri, "candidates", f"unit_index={unit_index}")

    x_train = pd.read_parquet(matrix_local / "train_features.parquet").to_numpy(dtype=np.float32)
    train_labels = pd.read_parquet(matrix_local / "train_labels.parquet")
    x_valid = pd.read_parquet(matrix_local / "valid_features.parquet").to_numpy(dtype=np.float32)
    valid_labels = pd.read_parquet(matrix_local / "valid_labels.parquet")
    y_train = train_labels["target_label"].astype(int).to_numpy()
    sample_weight = train_labels["sample_weight"].fillna(1.0).astype(float).to_numpy()
    valid_panel = valid_labels[["trade_date", "sec_code", "target_label", "target_return"]].copy()

    started_at = datetime.now(timezone.utc)
    result = train_candidate_from_matrices(
        config,
        unit["model_params"],
        x_train,
        y_train,
        sample_weight,
        valid_panel,
        x_valid,
    )
    ended_at = datetime.now(timezone.utc)

    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(result.model, out_dir / "model.joblib")
    metrics = dict(result.metrics)
    metrics.update({
        "matrix_id": manifest["matrix_id"],
        "matrix_uri": matrix_uri,
        "unit_index": unit_index,
        "unit_id": unit["unit_id"],
        "feature_order_sha256": manifest["feature_order_sha256"],
        "preprocess_stats_sha256": manifest["preprocess_stats_sha256"],
        "work_units_sha256": manifest["work_units_sha256"],
        "execution_backend": config.execution_backend,
        "task_fanout_mode": "candidate_task",
    })
    write_json(out_dir / "candidate_metrics.json", metrics)
    write_json(out_dir / "training_log.json", {
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "runner_version": __version__,
        "container_image": env_container_image(),
        "git_commit": get_git_commit(),
        "feature_count": feature_schema.get("feature_count"),
        "preprocess_version": preprocess_stats.get("preprocess_version"),
    })
    write_json(out_dir / "task_status.json", {
        "unit_index": unit_index,
        "unit_id": unit["unit_id"],
        "candidate_id": unit["candidate_id"],
        "status": "succeeded",
        "matrix_id": manifest["matrix_id"],
        "matrix_uri": matrix_uri,
        "feature_order_sha256": manifest["feature_order_sha256"],
        "preprocess_stats_sha256": manifest["preprocess_stats_sha256"],
        "work_units_sha256": manifest["work_units_sha256"],
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "cloud_run_execution_id": None,
        "cloud_run_task_index": cloud_run_task_index,
        "task_index_offset": task_index_offset,
        "global_unit_index": unit_index,
        "error_summary": None,
        "model_sha256": file_sha256(out_dir / "model.joblib"),
    })
    uploaded = [] if skip_gcs_upload else upload_directory_to_gcs(config.project, out_dir, out_uri)
    return {
        "status": "succeeded",
        "matrix_id": manifest["matrix_id"],
        "unit_index": unit_index,
        "candidate_id": unit["candidate_id"],
        "candidate_output_uri": out_uri,
        "uploaded_artifacts": uploaded,
        "oriented_valid_rank_ic_mean": metrics.get("oriented_valid_rank_ic_mean"),
        "valid_topn_fwd_ret_mean": metrics.get("valid_topn_fwd_ret_mean"),
        "score_orientation": metrics.get("score_orientation"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
