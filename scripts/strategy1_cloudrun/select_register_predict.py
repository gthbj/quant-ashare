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
from google.cloud import bigquery

from scripts.strategy1_cloudrun import __version__
from scripts.strategy1_cloudrun.bq_io import (
    ADS,
    bq_label_value,
    execute_query,
    get_git_commit,
    join_gs_uri,
    make_client,
    query_dataframe,
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
    classify_valid_signal,
    clear_train_predict_outputs,
    compute_model_quality_parity,
    model_complexity_rank,
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
        "candidate_id": args.candidate_id,
        "search_id": args.search_id,
        "native_search": args.native_search,
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
        candidate_id=args.candidate_id,
        search_id=args.search_id,
        native_search=args.native_search,
        shortlist_rank_valid_only=args.shortlist_rank_valid_only,
        test_reuse_wave_no=args.test_reuse_wave_no,
        test_reuse_approval_ref=args.test_reuse_approval_ref,
        final_holdout_status=args.final_holdout_status,
        native_acceptance_status=args.native_acceptance_status,
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
    parser.add_argument("--candidate-id", default=None, help="Force a specific candidate artifact for Top-K backtest")
    parser.add_argument("--search-id", default=None, help="Sklearn native search id for metadata")
    parser.add_argument("--native-search", action="store_true", help="Write sklearn native search metadata")
    parser.add_argument("--shortlist-rank-valid-only", type=int, default=None)
    parser.add_argument("--test-reuse-wave-no", type=int, default=1)
    parser.add_argument("--test-reuse-approval-ref", default=None)
    parser.add_argument("--final-holdout-status", default=None)
    parser.add_argument("--native-acceptance-status", default="candidate")
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
    candidate_id: str | None = None,
    search_id: str | None = None,
    native_search: bool = False,
    shortlist_rank_valid_only: int | None = None,
    test_reuse_wave_no: int = 1,
    test_reuse_approval_ref: str | None = None,
    final_holdout_status: str | None = None,
    native_acceptance_status: str = "candidate",
) -> dict[str, Any]:
    manifest = read_json(matrix_local / "matrix_manifest.json")
    work_units = read_json(matrix_local / "work_units.json")
    feature_schema = read_json(matrix_local / "feature_schema.json")
    preprocess_stats = read_json(matrix_local / "preprocess_stats.json")
    candidates = load_candidates(matrix_local, manifest, work_units, require_all_candidates=require_all_candidates)
    candidate_ranking = rank_candidates(candidates, top_k=5)
    selected = select_candidate(candidates, candidate_ranking, candidate_id)
    selected_rank = next((row for row in candidate_ranking if row["candidate_id"] == selected.candidate_id), {})
    if shortlist_rank_valid_only is None:
        shortlist_rank_valid_only = selected_rank.get("shortlist_rank_valid_only")
    source_run_id = str(manifest.get("source_run_id") or manifest.get("run_id") or experiment.run_id)
    effective_search_id = search_id or str(manifest.get("search_id") or experiment.experiment_id)
    client = make_client(config.project, config.region)
    parity = compute_model_quality_parity(client, config, selected)
    candidate_task_bq_audit = audit_candidate_task_bigquery_usage(
        client, config, experiment, audit_run_id=source_run_id
    )
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
        "candidate_task_bq_forbidden_table_query_count": int(
            candidate_task_bq_audit["candidate_task_bq_forbidden_table_query_count"]
        ),
        "candidate_task_bq_job_count": int(candidate_task_bq_audit["candidate_task_bq_job_count"]),
        "candidate_task_bq_audit_window_days": int(candidate_task_bq_audit["candidate_task_bq_audit_window_days"]),
        "candidate_task_bq_max_bytes_threshold": int(candidate_task_bq_audit["candidate_task_bq_max_bytes_threshold"]),
        "candidate_task_bq_forbidden_tables": candidate_task_bq_audit["candidate_task_bq_forbidden_tables"],
        "candidate_task_bq_audit_run_id": source_run_id,
    })
    if native_search:
        selected.metrics.update(native_search_metrics(
            experiment=experiment,
            selected=selected,
            selected_rank=selected_rank,
            search_id=effective_search_id,
            source_run_id=source_run_id,
            shortlist_rank_valid_only=shortlist_rank_valid_only,
            test_reuse_wave_no=test_reuse_wave_no,
            test_reuse_approval_ref=test_reuse_approval_ref,
            final_holdout_status=final_holdout_status,
            native_acceptance_status=native_acceptance_status,
        ))

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
        candidate_ranking,
        matrix_local,
    )
    uploaded = [] if skip_gcs_upload else upload_directory_to_gcs(config.project, artifact_local_dir, artifact_uri)

    if force_replace:
        clear_train_predict_outputs(client, experiment)
    if source_run_id != experiment.run_id:
        copy_training_panel_alias(client, source_run_id, experiment.run_id, model_id, experiment, force_replace=force_replace)
    registry_candidates = [selected] if candidate_id else candidates
    write_registry(client, config, experiment, registry_candidates, selected, model_id, artifact_uri, force_replace=force_replace)
    predict_panel = pd.read_parquet(matrix_local / "predict_index.parquet")
    x_predict = pd.read_parquet(matrix_local / "predict_features.parquet").to_numpy(dtype=np.float32)
    write_predictions_from_preprocessed(client, config, experiment, predict_panel, x_predict, selected, model_id)
    return {
        "status": "succeeded",
        "run_id": experiment.run_id,
        "model_id": model_id,
        "selected_candidate_id": selected.candidate_id,
        "shortlist_rank_valid_only": shortlist_rank_valid_only,
        "search_id": effective_search_id if native_search else None,
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


def audit_candidate_task_bigquery_usage(
    client,
    config,
    experiment: Experiment,
    *,
    audit_run_id: str | None = None,
) -> dict[str, Any]:
    forbidden_tables = [
        f"{ADS}.ads_ml_training_panel_daily",
        "data-aquarium.ashare_dws.dws_stock_sample_daily",
    ]
    audit_window_days = 14
    max_bytes_threshold = 0
    jobs_table = f"`{config.project}.region-{config.region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`"
    sql = f"""
    WITH candidate_jobs AS (
      SELECT
        job_id,
        total_bytes_processed,
        referenced_tables
      FROM {jobs_table}
      WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @audit_window_days DAY)
        AND EXISTS (
          SELECT 1
          FROM UNNEST(labels) AS label
          WHERE label.key = 'pipeline_component'
            AND label.value = 'strategy1_cloudrun'
        )
        AND EXISTS (
          SELECT 1
          FROM UNNEST(labels) AS label
          WHERE label.key = 'pipeline_step'
            AND label.value = 'train_candidate_task'
        )
        AND EXISTS (
          SELECT 1
          FROM UNNEST(labels) AS label
          WHERE label.key = 'run_id'
            AND label.value = @run_id_label
        )
    )
    SELECT
      COUNT(*) AS candidate_task_bq_job_count,
      COUNTIF(
        IFNULL(total_bytes_processed, 0) > @max_bytes_threshold
        OR EXISTS (
          SELECT 1
          FROM UNNEST(IFNULL(
            referenced_tables,
            ARRAY<STRUCT<project_id STRING, dataset_id STRING, table_id STRING>>[]
          )) AS ref
          WHERE FORMAT('%s.%s.%s', ref.project_id, ref.dataset_id, ref.table_id) IN UNNEST(@forbidden_tables)
        )
      ) AS candidate_task_bq_forbidden_table_query_count
    FROM candidate_jobs
    """
    frame = query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("audit_window_days", "INT64", audit_window_days),
            bigquery.ScalarQueryParameter("max_bytes_threshold", "INT64", max_bytes_threshold),
            bigquery.ScalarQueryParameter("run_id_label", "STRING", bq_label_value(audit_run_id or experiment.run_id)),
            bigquery.ArrayQueryParameter("forbidden_tables", "STRING", forbidden_tables),
        ],
        labels={
            "pipeline_component": "strategy1_cloudrun",
            "pipeline_step": "select_register_predict_audit",
            "run_id": experiment.run_id,
        },
    )
    row = frame.iloc[0].to_dict()
    return {
        "candidate_task_bq_job_count": int(row.get("candidate_task_bq_job_count") or 0),
        "candidate_task_bq_forbidden_table_query_count": int(
            row.get("candidate_task_bq_forbidden_table_query_count") or 0
        ),
        "candidate_task_bq_audit_window_days": audit_window_days,
        "candidate_task_bq_max_bytes_threshold": max_bytes_threshold,
        "candidate_task_bq_forbidden_tables": forbidden_tables,
    }


def rank_candidates(candidates: list[CandidateResult], *, top_k: int = 5) -> list[dict[str, Any]]:
    coverages = [
        _float_or_nan(candidate.metrics.get("valid_eval_coverage"))
        for candidate in candidates
        if math.isfinite(_float_or_nan(candidate.metrics.get("valid_eval_coverage")))
    ]
    median_coverage = float(np.median(coverages)) if coverages else math.nan
    has_positive_rank_ic = any(
        _float_or_nan(candidate.metrics.get("oriented_valid_rank_ic_mean")) > 0
        for candidate in candidates
    )
    rows = []
    for candidate in candidates:
        metrics = candidate.metrics
        if not metrics.get("valid_signal_status"):
            metrics["valid_signal_status"] = classify_valid_signal(metrics)
        metrics["model_complexity_rank"] = int(metrics.get("model_complexity_rank", model_complexity_rank(metrics)))
        rank_ic = _float_or_nan(metrics.get("oriented_valid_rank_ic_mean"))
        coverage = _float_or_nan(metrics.get("valid_eval_coverage"))
        hard_reasons = []
        rank_reasons = []
        if not rank_ic > 0:
            rank_reasons.append("valid_rank_ic_not_positive")
        if math.isfinite(median_coverage) and math.isfinite(coverage) and coverage < median_coverage - 0.05:
            hard_reasons.append("valid_eval_coverage_below_peer_median_minus_5pp")
        if metrics.get("score_orientation") not in {"identity", "reverse_probability"}:
            hard_reasons.append("score_orientation_missing")
        if not metrics.get("convergence_status"):
            hard_reasons.append("convergence_status_missing")
        elif metrics.get("convergence_status") != "converged":
            hard_reasons.append("convergence_status_not_converged")
        reasons = hard_reasons + rank_reasons
        eligible = not reasons
        rows.append({
            "candidate_id": candidate.candidate_id,
            "eligible_for_shortlist": eligible,
            "eligible_after_hard_filters": not hard_reasons,
            "shortlist_filter_reason": ";".join(reasons),
            "valid_oriented_rank_ic_mean": rank_ic,
            "valid_oriented_rank_ic_icir": _float_or_nan(metrics.get("oriented_valid_rank_ic_icir")),
            "valid_topn_fwd_ret_mean": _float_or_nan(metrics.get("valid_topn_fwd_ret_mean")),
            "valid_top_minus_bottom_fwd_ret_mean": _float_or_nan(metrics.get("valid_top_minus_bottom_fwd_ret_mean")),
            "valid_roc_auc": _float_or_nan(metrics.get("roc_auc")),
            "valid_eval_coverage": coverage,
            "valid_signal_status": metrics.get("valid_signal_status"),
            "score_orientation": metrics.get("score_orientation"),
            "convergence_status": metrics.get("convergence_status"),
            "model_family": metrics.get("model_family"),
            "solver": metrics.get("solver"),
            "penalty": metrics.get("penalty"),
            "C": metrics.get("C"),
            "l1_ratio": metrics.get("l1_ratio"),
            "class_weight": metrics.get("class_weight"),
            "model_complexity_rank": metrics.get("model_complexity_rank"),
        })
    rows = sorted(rows, key=ranking_sort_key, reverse=True)
    eligible_assigned = 0
    fallback_assigned = 0
    has_eligible = any(row["eligible_for_shortlist"] for row in rows)
    no_positive_valid_signal = not has_positive_rank_ic
    for position, row in enumerate(rows, start=1):
        row["valid_only_rank"] = position
        row["shortlist_ranking_uses_test_metrics"] = False
        if row["eligible_for_shortlist"]:
            eligible_assigned += 1
            row["shortlist_rank_valid_only"] = eligible_assigned if eligible_assigned <= top_k else None
        elif not has_eligible and no_positive_valid_signal and row.get("eligible_after_hard_filters"):
            fallback_assigned += 1
            row["shortlist_rank_valid_only"] = fallback_assigned if fallback_assigned <= top_k else None
            row["search_failure_status"] = "failed_no_positive_valid_signal"
            row["shortlist_fallback_reason"] = "all_candidates_nonpositive_valid_rank_ic"
        else:
            row["shortlist_rank_valid_only"] = None
    return rows


def ranking_sort_key(row: dict[str, Any]) -> tuple[float, float, float, float, float, float]:
    return (
        1.0 if row.get("eligible_for_shortlist") else 0.0,
        _neg_inf_if_nan(row.get("valid_oriented_rank_ic_mean")),
        _neg_inf_if_nan(row.get("valid_topn_fwd_ret_mean")),
        _neg_inf_if_nan(row.get("valid_top_minus_bottom_fwd_ret_mean")),
        _neg_inf_if_nan(row.get("valid_roc_auc")),
        -float(row.get("model_complexity_rank") or 0),
    )


def select_candidate(
    candidates: list[CandidateResult],
    ranking: list[dict[str, Any]],
    candidate_id: str | None,
) -> CandidateResult:
    by_id = {candidate.candidate_id: candidate for candidate in candidates}
    if candidate_id:
        if candidate_id not in by_id:
            raise ValueError(f"candidate_id {candidate_id!r} not found in trained artifacts")
        return by_id[candidate_id]
    shortlisted = [row for row in ranking if row.get("shortlist_rank_valid_only") == 1]
    if shortlisted:
        return by_id[shortlisted[0]["candidate_id"]]
    return by_id[ranking[0]["candidate_id"]]


def native_search_metrics(
    *,
    experiment: Experiment,
    selected: CandidateResult,
    selected_rank: dict[str, Any],
    search_id: str,
    source_run_id: str,
    shortlist_rank_valid_only: int | None,
    test_reuse_wave_no: int,
    test_reuse_approval_ref: str | None,
    final_holdout_status: str | None,
    native_acceptance_status: str,
) -> dict[str, Any]:
    status = native_acceptance_status or "candidate"
    return {
        "search_id": search_id,
        "source_run_id": source_run_id,
        "candidate_id": selected.candidate_id,
        "candidate_run_id": experiment.run_id,
        "candidate_backtest_id": experiment.backtest_id,
        "sklearn_native_mode": True,
        "native_acceptance_status": status,
        "native_acceptance_reason": "pending_top5_backtest" if status == "candidate" else status,
        "shortlist_rank_valid_only": shortlist_rank_valid_only,
        "shortlist_ranking_uses_test_metrics": False,
        "shortlist_filter_reason": selected_rank.get("shortlist_filter_reason"),
        "shortlist_fallback_reason": selected_rank.get("shortlist_fallback_reason"),
        "search_failure_status": selected_rank.get("search_failure_status"),
        "valid_signal_status": selected.metrics.get("valid_signal_status"),
        "test_reuse_wave_no": int(test_reuse_wave_no),
        "test_reuse_approval_ref": test_reuse_approval_ref,
        "final_holdout_status": final_holdout_status,
    }


def copy_training_panel_alias(
    client: bigquery.Client,
    source_run_id: str,
    target_run_id: str,
    model_id: str,
    experiment: Experiment,
    *,
    force_replace: bool,
) -> None:
    if source_run_id == target_run_id:
        return
    if force_replace:
        execute_query(
            client,
            f"""
            DELETE FROM `{ADS}.ads_ml_training_panel_daily`
            WHERE run_id = @target_run_id
              AND trade_date BETWEEN @train_start AND @test_end
            """,
            [
                bigquery.ScalarQueryParameter("target_run_id", "STRING", target_run_id),
                bigquery.ScalarQueryParameter("train_start", "DATE", experiment.train_start),
                bigquery.ScalarQueryParameter("test_end", "DATE", experiment.test_end),
            ],
        )
    existing = query_dataframe(
        client,
        f"""
        SELECT COUNT(*) AS n
        FROM `{ADS}.ads_ml_training_panel_daily`
        WHERE run_id = @target_run_id
          AND trade_date BETWEEN @train_start AND @test_end
        """,
        [
            bigquery.ScalarQueryParameter("target_run_id", "STRING", target_run_id),
            bigquery.ScalarQueryParameter("train_start", "DATE", experiment.train_start),
            bigquery.ScalarQueryParameter("test_end", "DATE", experiment.test_end),
        ],
    )
    if int(existing.iloc[0]["n"] or 0) > 0:
        raise RuntimeError(f"training panel alias already exists for run_id={target_run_id}; set --force-replace")
    execute_query(
        client,
        f"""
        INSERT INTO `{ADS}.ads_ml_training_panel_daily`
        (
          run_id, strategy_id, model_id, preprocess_version, feature_version,
          label_version, universe_version, trade_date, sec_code, horizon,
          split_fold, split_tag, sample_weight, target_label, target_return,
          feature_values_json, feature_column_list, created_at
        )
        SELECT
          @target_run_id AS run_id,
          strategy_id,
          @model_id AS model_id,
          preprocess_version,
          feature_version,
          label_version,
          universe_version,
          trade_date,
          sec_code,
          horizon,
          split_fold,
          split_tag,
          sample_weight,
          target_label,
          target_return,
          feature_values_json,
          feature_column_list,
          CURRENT_TIMESTAMP() AS created_at
        FROM `{ADS}.ads_ml_training_panel_daily`
        WHERE run_id = @source_run_id
          AND trade_date BETWEEN @train_start AND @test_end
        """,
        [
            bigquery.ScalarQueryParameter("target_run_id", "STRING", target_run_id),
            bigquery.ScalarQueryParameter("source_run_id", "STRING", source_run_id),
            bigquery.ScalarQueryParameter("model_id", "STRING", model_id),
            bigquery.ScalarQueryParameter("train_start", "DATE", experiment.train_start),
            bigquery.ScalarQueryParameter("test_end", "DATE", experiment.test_end),
        ],
    )


def load_candidates(
    matrix_local: Path,
    manifest: dict[str, Any],
    work_units: dict[str, Any],
    *,
    require_all_candidates: bool,
    load_models: bool = True,
) -> list[CandidateResult]:
    candidates = []
    missing = []
    for unit in work_units.get("units", []):
        unit_index = int(unit["unit_index"])
        unit_dir = matrix_local / "candidates" / f"unit_index={unit_index}"
        status_path = unit_dir / "task_status.json"
        metrics_path = unit_dir / "candidate_metrics.json"
        model_path = unit_dir / "model.joblib"
        if not status_path.exists() or not metrics_path.exists() or (load_models and not model_path.exists()):
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
        model = joblib.load(model_path) if load_models else None
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
    candidate_ranking: list[dict[str, Any]],
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
    write_json(artifact_local_dir / "candidate_ranking.json", {
        "ranking": candidate_ranking,
        "selected_candidate_id": selected.candidate_id,
        "ranking_uses_test_metrics": False,
    })
    pd.DataFrame(candidate_ranking).to_csv(artifact_local_dir / "candidate_ranking.csv", index=False)
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


def _float_or_nan(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return math.nan
    return out if math.isfinite(out) else math.nan


if __name__ == "__main__":
    raise SystemExit(main())
