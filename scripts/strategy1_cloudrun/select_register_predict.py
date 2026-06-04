#!/usr/bin/env python3
"""Reduce task fan-out candidates, register the selected model and write predictions."""

from __future__ import annotations

import argparse
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from scripts.strategy1_cloudrun import __version__
from scripts.strategy1_cloudrun.bq_io import (
    get_git_commit,
    join_gs_uri,
    make_client,
    run_safe,
    upload_directory_to_gcs,
    write_json,
    write_text,
)
from scripts.strategy1_cloudrun.config import (
    Experiment,
    add_common_args,
    apply_cli_overrides,
    experiment_from_b64,
    filter_experiments,
    load_manifest,
    load_runner_config,
)
from scripts.strategy1_cloudrun.task_fanout import (
    ensure_matrix_local,
    read_json,
)
from scripts.strategy1_cloudrun.train_predict import (
    CandidateResult,
    clear_train_predict_outputs,
    compute_model_quality_parity,
    requirements_snapshot,
    write_predictions_from_preprocessed,
    write_registry,
)


def main() -> int:
    args = parse_args()
    config = apply_cli_overrides(load_runner_config(args.config), args)
    experiment = resolve_experiment(args)
    matrix_local = ensure_matrix_local(
        project=config.project,
        matrix_uri=args.matrix_uri,
        matrix_local=args.matrix_local_dir,
        required_files=None if not args.dry_run else ["matrix_manifest.json", "work_units.json"],
    )
    plan = {
        "entrypoint": "select_register_predict",
        "runner_version": __version__,
        "project": config.project,
        "region": config.region,
        "experiment": experiment.to_params(),
        "matrix_uri": args.matrix_uri,
        "matrix_local_dir": str(matrix_local),
        "require_all_candidates": not args.allow_partial_candidates,
        "skip_gcs_upload": args.skip_gcs_upload,
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2, default=str))
        return 0
    result = select_register_predict(
        config=config,
        experiment=experiment,
        matrix_local=matrix_local,
        matrix_uri=args.matrix_uri,
        force_replace=args.force_replace,
        skip_gcs_upload=args.skip_gcs_upload,
        require_all_candidates=not args.allow_partial_candidates,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select Strategy 1 task-fanout candidate and write predictions")
    add_common_args(parser)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--experiment-json", default=None, help="Base64 encoded resolved experiment payload")
    parser.add_argument("--matrix-uri", required=True)
    parser.add_argument("--matrix-local-dir", default=None)
    parser.add_argument("--force-replace", action="store_true")
    parser.add_argument("--skip-gcs-upload", action="store_true")
    parser.add_argument(
        "--allow-partial-candidates",
        action="store_true",
        help="Allow reducer to continue when some candidate task artifacts are missing or failed",
    )
    return parser.parse_args()


def resolve_experiment(args: argparse.Namespace) -> Experiment:
    if args.experiment_json:
        exp = experiment_from_b64(args.experiment_json)
    else:
        _, experiments = load_manifest(args.manifest)
        matches = filter_experiments(experiments, experiment_id=args.experiment_id, include_blocked=True)
        if not matches:
            raise ValueError(f"experiment_id {args.experiment_id} not found in {args.manifest}")
        exp = matches[0]
    if not exp.requires_retrain:
        raise ValueError(f"{exp.experiment_id} is portfolio-only and does not require select_register_predict")
    if not exp.is_executable:
        raise ValueError(f"{exp.experiment_id} contains unresolved placeholders or blocked status")
    return exp


def select_register_predict(
    *,
    config,
    experiment: Experiment,
    matrix_local: Path,
    matrix_uri: str,
    force_replace: bool,
    skip_gcs_upload: bool,
    require_all_candidates: bool,
) -> dict[str, Any]:
    manifest = read_json(matrix_local / "matrix_manifest.json")
    work_units = read_json(matrix_local / "work_units.json")
    feature_schema = read_json(matrix_local / "feature_schema.json")
    preprocess_stats = read_json(matrix_local / "preprocess_stats.json")
    bq_audit = read_json(matrix_local / "bq_audit.json") if (matrix_local / "bq_audit.json").exists() else {}
    candidates = load_candidates(matrix_local, manifest, work_units, require_all_candidates=require_all_candidates)
    selected = sorted(
        candidates,
        key=lambda item: (
            _neg_inf_if_nan(item.metrics.get("oriented_valid_rank_ic_mean")),
            _neg_inf_if_nan(item.metrics.get("valid_topn_fwd_ret_mean")),
            _neg_inf_if_nan(item.metrics.get("roc_auc")),
        ),
        reverse=True,
    )[0]
    client = make_client(config.project, config.region)
    parity = compute_model_quality_parity(client, config, selected)
    selected.metrics.update(parity)
    if parity["model_quality_parity_status"] == "passed":
        selected.metrics["model_quality_status"] = "model_quality_equivalent"
        selected.metrics["model_quality_status_reason"] = "sklearn_vs_bqml_parity_passed"
    else:
        selected.metrics["model_quality_status"] = "model_quality_not_equivalent"
        selected.metrics["model_quality_status_reason"] = "sklearn_vs_bqml_parity_failed"
    selected.metrics.update({
        "task_fanout_mode": "task_fanout",
        "matrix_id": manifest["matrix_id"],
        "matrix_uri": matrix_uri,
        "work_unit_count": int(work_units["work_unit_count"]),
        "succeeded_task_count": len(candidates),
        "candidate_parallelism_resolved": int(work_units.get("candidate_parallelism_resolved") or work_units["work_unit_count"]),
        "feature_order_sha256": manifest["feature_order_sha256"],
        "preprocess_stats_sha256": manifest["preprocess_stats_sha256"],
        "work_units_sha256": manifest["work_units_sha256"],
        "candidate_task_bq_forbidden_table_query_count": int(bq_audit.get("forbidden_candidate_query_count", 0)),
    })

    model_id = f"s1_sklearn_{run_safe(experiment.run_id)}__{selected.candidate_id}"
    artifact_local_dir = (
        Path(config.local_mirror_root)
        / "models"
        / "ml_pv_clf_v0"
        / f"run_id={experiment.run_id}"
        / f"model_id={model_id}"
    )
    artifact_uri = join_gs_uri(
        config.model_artifact_base_uri,
        "ml_pv_clf_v0",
        f"run_id={experiment.run_id}",
        f"model_id={model_id}",
    )
    materialize_selected_artifact(
        artifact_local_dir,
        artifact_uri,
        experiment,
        selected,
        feature_schema,
        preprocess_stats,
        manifest,
        work_units,
        candidates,
        matrix_local,
    )
    uploaded = [] if skip_gcs_upload else upload_directory_to_gcs(config.project, artifact_local_dir, artifact_uri)

    if force_replace:
        clear_train_predict_outputs(client, experiment)
    write_registry(client, config, experiment, candidates, selected, model_id, artifact_uri, force_replace=force_replace)
    predict_panel = pd.read_parquet(matrix_local / "predict_index.parquet")
    x_predict = pd.read_parquet(matrix_local / "predict_features.parquet").to_numpy(dtype=np.float32)
    write_predictions_from_preprocessed(client, config, experiment, predict_panel, x_predict, selected, model_id)
    return {
        "status": "succeeded",
        "run_id": experiment.run_id,
        "model_id": model_id,
        "selected_candidate_id": selected.candidate_id,
        "score_orientation": selected.score_orientation,
        "matrix_id": manifest["matrix_id"],
        "matrix_uri": matrix_uri,
        "work_unit_count": int(work_units["work_unit_count"]),
        "succeeded_task_count": len(candidates),
        "model_artifact_uri": artifact_uri,
        "uploaded_artifacts": uploaded,
        "prediction_rows": int(len(predict_panel)),
        "model_quality_parity_status": selected.metrics.get("model_quality_parity_status"),
        "model_quality_status": selected.metrics.get("model_quality_status"),
    }


def load_candidates(
    matrix_local: Path,
    manifest: dict[str, Any],
    work_units: dict[str, Any],
    *,
    require_all_candidates: bool,
) -> list[CandidateResult]:
    candidates = []
    missing = []
    for unit in work_units.get("units", []):
        unit_index = int(unit["unit_index"])
        unit_dir = matrix_local / "candidates" / f"unit_index={unit_index}"
        status_path = unit_dir / "task_status.json"
        metrics_path = unit_dir / "candidate_metrics.json"
        model_path = unit_dir / "model.joblib"
        if not status_path.exists() or not metrics_path.exists() or not model_path.exists():
            missing.append(unit_index)
            continue
        status = read_json(status_path)
        if status.get("status") != "succeeded":
            missing.append(unit_index)
            continue
        for key in ("matrix_id", "feature_order_sha256", "preprocess_stats_sha256", "work_units_sha256"):
            if status.get(key) != manifest.get(key):
                raise ValueError(f"candidate unit_index={unit_index} has mismatched {key}")
        metrics = read_json(metrics_path)
        model = joblib.load(model_path)
        candidates.append(CandidateResult(
            candidate_id=str(unit["candidate_id"]),
            model=model,
            score_orientation=str(metrics["score_orientation"]),
            orientation_reason=str(metrics.get("orientation_decision_reason") or ""),
            raw_valid_scores=np.array([], dtype=np.float32),
            oriented_valid_scores=np.array([], dtype=np.float32),
            metrics=metrics,
            model_params=dict(unit["model_params"]),
        ))
    if missing and require_all_candidates:
        raise RuntimeError(f"missing or failed candidate units: {missing}")
    if not candidates:
        raise RuntimeError("no succeeded candidate artifacts found")
    return candidates


def materialize_selected_artifact(
    artifact_local_dir: Path,
    artifact_uri: str,
    experiment: Experiment,
    selected: CandidateResult,
    feature_schema: dict[str, Any],
    preprocess_stats: dict[str, Any],
    manifest: dict[str, Any],
    work_units: dict[str, Any],
    candidates: list[CandidateResult],
    matrix_local: Path,
) -> None:
    artifact_local_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(selected.model, artifact_local_dir / "model.joblib")
    if (matrix_local / "preprocess.joblib").exists():
        shutil.copyfile(matrix_local / "preprocess.joblib", artifact_local_dir / "preprocess.joblib")
    write_json(artifact_local_dir / "feature_schema.json", feature_schema)
    write_json(artifact_local_dir / "preprocess_stats.json", preprocess_stats)
    write_json(artifact_local_dir / "matrix_manifest.json", manifest)
    write_json(artifact_local_dir / "work_units.json", work_units)
    write_json(artifact_local_dir / "training_metrics.json", selected.metrics)
    write_json(artifact_local_dir / "candidate_metrics.json", {
        "candidates": [candidate.metrics for candidate in candidates],
        "selected_candidate_id": selected.candidate_id,
    })
    write_json(artifact_local_dir / "orientation.json", {
        "score_orientation": selected.score_orientation,
        "orientation_decision_reason": selected.orientation_reason,
        "orientation_decision_split": "valid",
        "score_source": "sklearn_predict_proba_label_1",
    })
    write_json(
        artifact_local_dir / "model_quality_parity.json",
        {k: v for k, v in selected.metrics.items() if "parity" in k or k.startswith("bqml_") or k.startswith("sklearn_")},
    )
    write_json(artifact_local_dir / "manifest_resolved.json", {
        "experiment": experiment.to_params(),
        "execution_backend": "cloud_run_sklearn_ledger_v1",
        "artifact_uri": artifact_uri,
        "runner_version": __version__,
        "task_fanout_mode": "task_fanout",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
    })
    write_text(artifact_local_dir / "requirements_lock.txt", requirements_snapshot())


def _neg_inf_if_nan(value: Any) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return -math.inf
    return value if math.isfinite(value) else -math.inf


if __name__ == "__main__":
    raise SystemExit(main())
