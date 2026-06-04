#!/usr/bin/env python3
"""Train sklearn logistic candidates and write Strategy 1 predictions.

This entrypoint is designed for Cloud Run Jobs but also supports local smoke
and dry-run. It consumes the existing BigQuery ADS training panel built by
`sql/ml/strategy1/01_build_training_panel.sql`; it does not rebuild DWS/PIT
features itself.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from google.cloud import bigquery

from scripts.strategy1_cloudrun import __version__
from scripts.strategy1_cloudrun.bq_io import (
    ADS,
    env_container_image,
    execute_query,
    get_git_commit,
    join_gs_uri,
    load_dataframe,
    make_client,
    query_dataframe,
    run_safe,
    upload_directory_to_gcs,
    write_json,
    write_text,
)
from scripts.strategy1_cloudrun.config import (
    Experiment,
    RunnerConfig,
    add_common_args,
    apply_cli_overrides,
    filter_experiments,
    load_manifest,
    load_runner_config,
    experiment_from_b64,
)
from scripts.strategy1_cloudrun.preprocess import (
    MedianWinsorZScorePreprocessor,
    feature_frame_from_panel,
)


def main() -> int:
    args = parse_args()
    config = apply_cli_overrides(load_runner_config(args.config), args)
    experiment = resolve_experiment(args)

    plan = {
        "entrypoint": "train_predict",
        "execution_backend": config.execution_backend,
        "project": config.project,
        "region": config.region,
        "experiment": experiment.to_params(),
        "model_artifact_base_uri": config.model_artifact_base_uri,
        "local_mirror_root": config.local_mirror_root,
        "candidate_grid_version": "sklearn_logistic_parity_v1",
        "candidate_grid_size": len(config.candidate_grid),
        "skip_gcs_upload": args.skip_gcs_upload,
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    result = run_train_predict(config, experiment, force_replace=args.force_replace, skip_gcs_upload=args.skip_gcs_upload)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategy 1 Cloud Run sklearn train/predict")
    add_common_args(parser)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--manifest-resolved", default=None, help="Resolved manifest JSON; optional in P0 local mode")
    parser.add_argument("--experiment-json", default=None, help="Base64 encoded resolved experiment payload")
    parser.add_argument("--force-replace", action="store_true")
    parser.add_argument("--skip-gcs-upload", action="store_true")
    return parser.parse_args()


def resolve_experiment(args: argparse.Namespace) -> Experiment:
    if args.experiment_json:
        exp = experiment_from_b64(args.experiment_json)
        if not exp.requires_retrain:
            raise ValueError(f"{exp.experiment_id} is portfolio-only and does not require train_predict")
        if not exp.is_executable:
            raise ValueError(f"{exp.experiment_id} contains unresolved placeholders or blocked status")
        return exp
    if args.manifest_resolved:
        resolved = json.loads(Path(args.manifest_resolved).read_text(encoding="utf-8"))
        matches = [item for item in resolved.get("experiments", []) if item.get("experiment_id") == args.experiment_id]
        if not matches:
            raise ValueError(f"experiment_id {args.experiment_id} not found in resolved manifest")
        raw = matches[0]
        manifest = {"default_windows": {}}
        _, base_experiments = load_manifest(args.manifest)
        by_id = {exp.experiment_id: exp for exp in base_experiments}
        if args.experiment_id in by_id:
            exp = by_id[args.experiment_id]
            return dataclasses.replace(exp, **{k: raw[k] for k in raw if hasattr(exp, k)})
    _, experiments = load_manifest(args.manifest)
    matches = filter_experiments(experiments, experiment_id=args.experiment_id, include_blocked=True)
    if not matches:
        raise ValueError(f"experiment_id {args.experiment_id} not found in {args.manifest}")
    exp = matches[0]
    if args.run_id and args.run_id != exp.run_id:
        exp = dataclasses.replace(exp, run_id=args.run_id, prediction_run_id=args.run_id)
    if not exp.requires_retrain:
        raise ValueError(f"{exp.experiment_id} is portfolio-only and does not require train_predict")
    if not exp.is_executable:
        raise ValueError(f"{exp.experiment_id} contains unresolved placeholders or blocked status")
    return exp


def run_train_predict(
    config: RunnerConfig,
    experiment: Experiment,
    *,
    force_replace: bool,
    skip_gcs_upload: bool,
) -> dict[str, Any]:
    client = make_client(config.project, config.region)
    panel = load_training_panel(client, experiment)
    if panel.empty:
        raise RuntimeError(f"ads_ml_training_panel_daily has no rows for run_id={experiment.run_id}")

    feature_frame, feature_columns = feature_frame_from_panel(panel)
    panel = panel.reset_index(drop=True)
    feature_frame = feature_frame.reset_index(drop=True)
    panel = panel.drop(columns=["feature_values_json", "feature_column_list"])

    train_mask = panel["split_tag"].eq("train") & panel["target_label"].notna()
    valid_mask = panel["split_tag"].eq("valid")
    predict_mask = panel["split_tag"].isin(["valid", "test"])
    if train_mask.sum() == 0:
        raise RuntimeError("train split has no labeled samples")
    if valid_mask.sum() == 0:
        raise RuntimeError("valid split has no prediction samples")

    preprocessor = MedianWinsorZScorePreprocessor(
        feature_columns=feature_columns,
        winsor_lower=config.winsor_lower,
        winsor_upper=config.winsor_upper,
    ).fit(feature_frame.loc[train_mask])
    x_train = preprocessor.transform(feature_frame.loc[train_mask])
    y_train = panel.loc[train_mask, "target_label"].astype(int).to_numpy()
    sample_weight = panel.loc[train_mask, "sample_weight"].fillna(1.0).astype(float).to_numpy()

    candidates: list[CandidateResult] = []
    for candidate_cfg in config.candidate_grid:
        result = train_candidate(config, candidate_cfg, x_train, y_train, sample_weight, panel, feature_frame, preprocessor)
        candidates.append(result)

    selected = sorted(
        candidates,
        key=lambda item: (
            _neg_inf_if_nan(item.metrics["oriented_valid_rank_ic_mean"]),
            _neg_inf_if_nan(item.metrics["valid_topn_fwd_ret_mean"]),
            _neg_inf_if_nan(item.metrics["roc_auc"]),
        ),
        reverse=True,
    )[0]

    selected.metrics["candidate_grid_version"] = "sklearn_logistic_parity_v1"
    selected.metrics["candidate_grid_size"] = len(candidates)

    bqml_reference = load_bqml_reference_metrics(client, config.bqml_reference_run_id)
    parity = compute_model_quality_parity(config, selected, bqml_reference)
    selected.metrics.update(parity)
    if parity["model_quality_parity_status"] == "passed":
        selected.metrics["model_quality_status"] = "model_quality_equivalent"
        selected.metrics["model_quality_status_reason"] = "sklearn_vs_bqml_parity_passed"
    else:
        selected.metrics["model_quality_status"] = "model_quality_not_equivalent"
        selected.metrics["model_quality_status_reason"] = "sklearn_vs_bqml_parity_failed"

    model_id = f"s1_sklearn_{run_safe(experiment.run_id)}__{selected.candidate_id}"
    artifact_local_dir = artifact_dir(config, experiment, model_id)
    artifact_uri = join_gs_uri(
        config.model_artifact_base_uri,
        "ml_pv_clf_v0",
        f"run_id={experiment.run_id}",
        f"model_id={model_id}",
    )
    selected.metrics["candidate_metrics_uri"] = join_gs_uri(artifact_uri, "candidate_metrics.csv")
    selected.metrics["implementation_audit_uri"] = join_gs_uri(artifact_uri, "implementation_audit.json")
    selected.metrics["selected_coefficients_uri"] = join_gs_uri(artifact_uri, "selected_coefficients.csv")
    selected.metrics["bqml_weight_alignment_uri"] = join_gs_uri(artifact_uri, "bqml_weight_alignment.csv")

    bqml_weights, bqml_weight_error = load_bqml_reference_weights(client, bqml_reference.get("model_uri"))
    selected_coefficients = selected_coefficients_frame(selected, feature_columns)
    bqml_weight_alignment = align_bqml_weights(selected_coefficients, bqml_weights, bqml_reference)
    implementation_audit = build_implementation_audit(
        config,
        experiment,
        panel,
        feature_frame,
        feature_columns,
        candidates,
        selected,
        bqml_reference,
        bqml_weight_alignment,
        bqml_weight_error,
    )
    materialize_artifacts(
        config,
        experiment,
        candidates,
        selected,
        preprocessor,
        feature_columns,
        selected_coefficients,
        bqml_weight_alignment,
        implementation_audit,
        artifact_local_dir,
        artifact_uri,
    )
    uploaded = [] if skip_gcs_upload else upload_directory_to_gcs(config.project, artifact_local_dir, artifact_uri)

    if force_replace:
        clear_train_predict_outputs(client, experiment)

    write_registry(client, config, experiment, candidates, selected, model_id, artifact_uri, force_replace=force_replace)
    write_predictions(client, config, experiment, panel.loc[predict_mask].copy(), feature_frame.loc[predict_mask], preprocessor, selected, model_id)

    return {
        "status": "succeeded",
        "run_id": experiment.run_id,
        "model_id": model_id,
        "selected_candidate_id": selected.candidate_id,
        "score_orientation": selected.score_orientation,
        "model_artifact_uri": artifact_uri,
        "uploaded_artifacts": uploaded,
        "prediction_rows": int(predict_mask.sum()),
        "model_quality_parity_status": selected.metrics.get("model_quality_parity_status"),
        "model_quality_status": selected.metrics.get("model_quality_status"),
    }


@dataclasses.dataclass
class CandidateResult:
    candidate_id: str
    model: Any
    score_orientation: str
    orientation_reason: str
    raw_valid_scores: np.ndarray
    oriented_valid_scores: np.ndarray
    metrics: dict[str, Any]
    model_params: dict[str, Any]


def load_training_panel(client: bigquery.Client, experiment: Experiment) -> pd.DataFrame:
    sql = f"""
    SELECT
      run_id, strategy_id, trade_date, sec_code, horizon, split_tag,
      sample_weight, target_label, target_return, feature_values_json,
      feature_column_list, feature_version, label_version, preprocess_version
    FROM `{ADS}.ads_ml_training_panel_daily`
    WHERE run_id = @run_id
      AND trade_date BETWEEN @train_start AND @test_end
    ORDER BY trade_date, sec_code
    """
    return query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("run_id", "STRING", experiment.run_id),
            bigquery.ScalarQueryParameter("train_start", "DATE", experiment.train_start),
            bigquery.ScalarQueryParameter("test_end", "DATE", experiment.test_end),
        ],
    )


def train_candidate(
    config: RunnerConfig,
    candidate_cfg: dict[str, Any],
    x_train: np.ndarray,
    y_train: np.ndarray,
    sample_weight: np.ndarray,
    panel: pd.DataFrame,
    feature_frame: pd.DataFrame,
    preprocessor: MedianWinsorZScorePreprocessor,
) -> CandidateResult:
    from sklearn.linear_model import LogisticRegression

    params = {
        "penalty": candidate_cfg["penalty"],
        "C": float(candidate_cfg["C"]),
        "solver": config.logistic_solver,
        "max_iter": config.logistic_max_iter,
        "random_state": config.random_state,
        "class_weight": config.logistic_class_weight,
        "n_jobs": None,
    }
    if candidate_cfg.get("l1_ratio") is not None:
        params["l1_ratio"] = float(candidate_cfg["l1_ratio"])
    model = LogisticRegression(**params)
    model.fit(x_train, y_train, sample_weight=sample_weight)

    valid_mask = panel["split_tag"].eq("valid")
    x_valid = preprocessor.transform(feature_frame.loc[valid_mask])
    raw_score = model.predict_proba(x_valid)[:, 1]
    valid_panel = panel.loc[valid_mask, ["trade_date", "sec_code", "target_label", "target_return"]].copy()

    raw_metrics = evaluate_scores(valid_panel, raw_score)
    rev_metrics = evaluate_scores(valid_panel, 1.0 - raw_score)
    orientation, reason = decide_orientation(raw_metrics, rev_metrics)
    oriented_score = 1.0 - raw_score if orientation == "reverse_probability" else raw_score
    oriented_metrics = evaluate_scores(valid_panel, oriented_score)
    class_metrics = evaluate_classification(valid_panel, raw_score)

    metrics = {
        "candidate_id": candidate_cfg["candidate_id"],
        "score_source": "sklearn_predict_proba_label_1",
        "score_orientation": orientation,
        "orientation_decision_split": "valid",
        "orientation_decision_reason": reason,
        "raw_valid_rank_ic_mean": raw_metrics["rank_ic_mean"],
        "reverse_valid_rank_ic_mean": rev_metrics["rank_ic_mean"],
        "reversed_valid_rank_ic_mean": rev_metrics["rank_ic_mean"],
        "oriented_valid_rank_ic_mean": oriented_metrics["rank_ic_mean"],
        "raw_valid_top_minus_bottom": raw_metrics["top_minus_bottom"],
        "reversed_valid_top_minus_bottom": rev_metrics["top_minus_bottom"],
        "valid_topn_fwd_ret_mean": oriented_metrics["topn_fwd_ret_mean"],
        "roc_auc": class_metrics["roc_auc"],
        "log_loss": class_metrics["log_loss"],
        "valid_prediction_rows": int(valid_mask.sum()),
        "valid_eval_rows": int(valid_panel["target_return"].notna().sum()),
        "valid_eval_coverage": safe_divide(valid_panel["target_return"].notna().sum(), valid_mask.sum()),
    }
    return CandidateResult(
        candidate_id=candidate_cfg["candidate_id"],
        model=model,
        score_orientation=orientation,
        orientation_reason=reason,
        raw_valid_scores=raw_score,
        oriented_valid_scores=oriented_score,
        metrics=metrics,
        model_params=params,
    )


def evaluate_scores(valid_panel: pd.DataFrame, scores: np.ndarray, topn: int = 30) -> dict[str, float]:
    frame = valid_panel.copy()
    frame["score"] = scores
    frame = frame[frame["target_return"].notna()]
    daily_ics = []
    topn_returns = []
    bucket_spreads = []
    for _, group in frame.groupby("trade_date"):
        if len(group) < 3 or group["target_return"].nunique(dropna=True) < 2:
            continue
        from scipy.stats import spearmanr
        ic = spearmanr(group["score"], group["target_return"], nan_policy="omit").correlation
        if ic is not None and np.isfinite(ic):
            daily_ics.append(float(ic))
        topn_returns.append(float(group.nlargest(min(topn, len(group)), "score")["target_return"].mean()))
        ranked = group.sort_values(["score", "sec_code"]).copy()
        try:
            ranked["bucket"] = pd.qcut(np.arange(len(ranked)), q=min(5, len(ranked)), labels=False) + 1
            low = ranked.loc[ranked["bucket"].eq(1), "target_return"].mean()
            high = ranked.loc[ranked["bucket"].eq(ranked["bucket"].max()), "target_return"].mean()
            if np.isfinite(high) and np.isfinite(low):
                bucket_spreads.append(float(high - low))
        except ValueError:
            pass
    return {
        "rank_ic_mean": _mean_or_nan(daily_ics),
        "rank_ic_std": _std_or_nan(daily_ics),
        "rank_ic_days": float(len(daily_ics)),
        "top_minus_bottom": _mean_or_nan(bucket_spreads),
        "topn_fwd_ret_mean": _mean_or_nan(topn_returns),
    }


def evaluate_classification(valid_panel: pd.DataFrame, raw_score: np.ndarray) -> dict[str, float]:
    from sklearn.metrics import log_loss, roc_auc_score

    frame = valid_panel.copy()
    frame["raw_score"] = raw_score
    frame = frame[frame["target_label"].notna()]
    if frame.empty or frame["target_label"].nunique() < 2:
        return {"roc_auc": math.nan, "log_loss": math.nan}
    y_true = frame["target_label"].astype(int).to_numpy()
    y_score = frame["raw_score"].clip(1e-9, 1 - 1e-9).to_numpy()
    return {
        "roc_auc": float(roc_auc_score(y_true, y_score)),
        "log_loss": float(log_loss(y_true, y_score, labels=[0, 1])),
    }


def decide_orientation(raw: dict[str, float], rev: dict[str, float]) -> tuple[str, str]:
    raw_ic = raw["rank_ic_mean"]
    rev_ic = rev["rank_ic_mean"]
    raw_lift = raw["top_minus_bottom"]
    rev_lift = rev["top_minus_bottom"]
    if raw_ic <= -0.03 and rev_ic >= 0.03 and _nan_to_zero(rev_lift) > _nan_to_zero(raw_lift):
        return "reverse_probability", "raw_rank_ic <= -0.03 AND reversed >= 0.03 AND reversed bucket lift better"
    if raw_ic <= -0.03 and rev_ic >= 0.03:
        return "identity", "raw_rank_ic <= -0.03 AND reversed >= 0.03 BUT bucket lift not better - kept identity"
    if raw_ic <= -0.03:
        return "identity", "raw_rank_ic <= -0.03 BUT reversed not >= 0.03 - kept identity"
    if abs(_nan_to_zero(raw_ic)) < 0.03 and abs(_nan_to_zero(rev_ic)) < 0.03:
        return "identity", "both RankIC near zero - weak signal, kept identity"
    return "identity", "raw_rank_ic non-negative - kept identity"


def compute_model_quality_parity(
    config: RunnerConfig,
    selected: CandidateResult,
    reference: dict[str, Any],
) -> dict[str, Any]:
    bqml_rank_ic = reference.get("oriented_valid_rank_ic_mean")
    bqml_topn = reference.get("valid_topn_fwd_ret_mean")
    bqml_coverage = reference.get("valid_eval_coverage")
    rank_delta = selected.metrics["oriented_valid_rank_ic_mean"] - bqml_rank_ic if bqml_rank_ic is not None else math.nan
    topn_delta = selected.metrics["valid_topn_fwd_ret_mean"] - bqml_topn if bqml_topn is not None else math.nan
    coverage_delta = selected.metrics["valid_eval_coverage"] - bqml_coverage if bqml_coverage is not None else math.nan
    rank_ok = bqml_rank_ic is None or selected.metrics["oriented_valid_rank_ic_mean"] >= bqml_rank_ic - 0.02
    topn_tol = max(0.002, 0.20 * abs(bqml_topn)) if bqml_topn is not None else math.inf
    topn_ok = bqml_topn is None or selected.metrics["valid_topn_fwd_ret_mean"] >= bqml_topn - topn_tol
    coverage_ok = bqml_coverage is None or selected.metrics["valid_eval_coverage"] >= bqml_coverage - 0.05
    status = "passed" if rank_ok and topn_ok and coverage_ok else "failed"
    return {
        "bqml_reference_run_id": config.bqml_reference_run_id,
        "bqml_reference_model_id": reference.get("model_id"),
        "bqml_reference_model_uri": reference.get("model_uri"),
        "bqml_reference_score_orientation": reference.get("score_orientation"),
        "bqml_reference_auto_class_weights": reference.get("auto_class_weights"),
        "bqml_oriented_valid_rank_ic_mean": bqml_rank_ic,
        "sklearn_oriented_valid_rank_ic_mean": selected.metrics["oriented_valid_rank_ic_mean"],
        "rank_ic_parity_passed": rank_ok,
        "rank_ic_parity_delta": rank_delta,
        "bqml_valid_topn_fwd_ret_mean": bqml_topn,
        "sklearn_valid_topn_fwd_ret_mean": selected.metrics["valid_topn_fwd_ret_mean"],
        "topn_ret_parity_passed": topn_ok,
        "topn_ret_parity_delta": topn_delta,
        "prediction_coverage_parity_passed": coverage_ok,
        "prediction_coverage_parity_delta": coverage_delta,
        "model_quality_parity_status": status,
    }


def load_bqml_reference_metrics(client: bigquery.Client, reference_run_id: str) -> dict[str, Any]:
    sql = f"""
    SELECT model_id, model_uri, model_params_json, metrics_json
    FROM `{ADS}.ads_model_registry`
    WHERE status = 'selected'
      AND JSON_VALUE(model_params_json, '$.run_id') = @run_id
    ORDER BY created_at DESC
    LIMIT 1
    """
    frame = query_dataframe(
        client,
        sql,
        [bigquery.ScalarQueryParameter("run_id", "STRING", reference_run_id)],
    )
    if frame.empty:
        return {}
    metrics = json.loads(frame.iloc[0]["metrics_json"] or "{}")
    params = json.loads(frame.iloc[0]["model_params_json"] or "{}")
    return {
        "model_id": frame.iloc[0]["model_id"],
        "model_uri": frame.iloc[0]["model_uri"],
        "auto_class_weights": params.get("auto_class_weights"),
        "oriented_valid_rank_ic_mean": _first_float(metrics, ["oriented_valid_rank_ic_mean", "rank_ic_mean"]),
        "valid_topn_fwd_ret_mean": _first_float(metrics, ["valid_topn_fwd_ret_mean", "topn_fwd_ret_mean"]),
        "valid_eval_coverage": _first_float(metrics, ["valid_eval_coverage"]),
        "score_orientation": metrics.get("score_orientation"),
    }


def load_bqml_reference_weights(client: bigquery.Client, model_uri: str | None) -> tuple[pd.DataFrame, str | None]:
    model_ref = bqml_model_ref_from_uri(model_uri)
    if model_ref is None:
        return pd.DataFrame(columns=["feature_name", "bqml_weight"]), "missing_or_invalid_bqml_model_uri"
    try:
        frame = query_dataframe(
            client,
            f"""
            SELECT
              processed_input AS feature_name,
              CAST(weight AS FLOAT64) AS bqml_weight
            FROM ML.WEIGHTS(MODEL `{model_ref}`)
            """,
            [],
        )
        return frame, None
    except Exception as exc:  # pragma: no cover - depends on remote BQML model state.
        return pd.DataFrame(columns=["feature_name", "bqml_weight"]), str(exc)


def bqml_model_ref_from_uri(model_uri: str | None) -> str | None:
    if not model_uri or not model_uri.startswith("bq://"):
        return None
    model_ref = model_uri[5:]
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+", model_ref):
        return None
    return model_ref


def materialize_artifacts(
    config: RunnerConfig,
    experiment: Experiment,
    candidates: list[CandidateResult],
    selected: CandidateResult,
    preprocessor: MedianWinsorZScorePreprocessor,
    feature_columns: list[str],
    selected_coefficients: pd.DataFrame,
    bqml_weight_alignment: pd.DataFrame,
    implementation_audit: dict[str, Any],
    artifact_local_dir: Path,
    artifact_uri: str,
) -> None:
    import joblib

    artifact_local_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(selected.model, artifact_local_dir / "model.joblib")
    joblib.dump(preprocessor, artifact_local_dir / "preprocess.joblib")
    candidate_metrics = candidate_metrics_frame(candidates, selected.candidate_id)
    candidate_metrics.to_csv(artifact_local_dir / "candidate_metrics.csv", index=False)
    write_json(
        artifact_local_dir / "candidate_metrics.json",
        {"candidates": candidate_metrics.to_dict(orient="records")},
    )
    selected_coefficients.to_csv(artifact_local_dir / "selected_coefficients.csv", index=False)
    bqml_weight_alignment.to_csv(artifact_local_dir / "bqml_weight_alignment.csv", index=False)
    write_json(artifact_local_dir / "implementation_audit.json", implementation_audit)
    write_json(
        artifact_local_dir / "feature_schema.json",
        {
            "feature_columns": feature_columns,
            "feature_count": len(feature_columns),
            "feature_set_id": experiment.feature_set_id,
            "feature_version": experiment.feature_version,
        },
    )
    write_json(artifact_local_dir / "training_metrics.json", selected.metrics)
    write_json(
        artifact_local_dir / "orientation.json",
        {
            "score_orientation": selected.score_orientation,
            "orientation_decision_reason": selected.orientation_reason,
            "orientation_decision_split": "valid",
            "score_source": "sklearn_predict_proba_label_1",
        },
    )
    write_json(
        artifact_local_dir / "model_quality_parity.json",
        {k: v for k, v in selected.metrics.items() if "parity" in k or k.startswith("bqml_") or k.startswith("sklearn_")},
    )
    write_json(
        artifact_local_dir / "manifest_resolved.json",
        {
            "experiment": experiment.to_params(),
            "execution_backend": config.execution_backend,
            "artifact_uri": artifact_uri,
            "runner_version": __version__,
        },
    )
    write_text(artifact_local_dir / "requirements_lock.txt", requirements_snapshot())
    write_text(artifact_local_dir / "container_image.txt", env_container_image() or "local")


def candidate_metrics_frame(candidates: list[CandidateResult], selected_candidate_id: str) -> pd.DataFrame:
    rows = []
    for candidate in candidates:
        row = dict(candidate.metrics)
        row["is_selected"] = candidate.candidate_id == selected_candidate_id
        row["penalty"] = candidate.model_params.get("penalty")
        row["C"] = candidate.model_params.get("C")
        row["l1_ratio"] = candidate.model_params.get("l1_ratio")
        row["solver"] = candidate.model_params.get("solver")
        row["class_weight"] = candidate.model_params.get("class_weight")
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["is_selected", "oriented_valid_rank_ic_mean", "valid_topn_fwd_ret_mean", "roc_auc"],
        ascending=[False, False, False, False],
    )


def selected_coefficients_frame(selected: CandidateResult, feature_columns: list[str]) -> pd.DataFrame:
    coef = np.asarray(getattr(selected.model, "coef_", [[]]), dtype=float)
    if coef.ndim != 2 or coef.shape[0] == 0:
        return pd.DataFrame(columns=[
            "feature_name", "raw_coefficient", "oriented_coefficient",
            "abs_oriented_coefficient", "abs_oriented_rank",
        ])
    raw = coef[0]
    orientation_multiplier = -1.0 if selected.score_orientation == "reverse_probability" else 1.0
    rows = []
    for idx, feature in enumerate(feature_columns):
        value = float(raw[idx]) if idx < len(raw) else math.nan
        oriented = orientation_multiplier * value if np.isfinite(value) else math.nan
        rows.append({
            "feature_name": feature,
            "raw_coefficient": value,
            "oriented_coefficient": oriented,
            "abs_oriented_coefficient": abs(oriented) if np.isfinite(oriented) else math.nan,
        })
    frame = pd.DataFrame(rows)
    frame["abs_oriented_rank"] = frame["abs_oriented_coefficient"].rank(method="first", ascending=False)
    return frame.sort_values("abs_oriented_rank")


def align_bqml_weights(
    selected_coefficients: pd.DataFrame,
    bqml_weights: pd.DataFrame,
    bqml_reference: dict[str, Any],
) -> pd.DataFrame:
    if selected_coefficients.empty or bqml_weights.empty:
        return pd.DataFrame(columns=[
            "feature_name", "oriented_coefficient", "bqml_oriented_weight",
            "coefficient_sign_matches_bqml",
        ])
    bqml = bqml_weights.rename(columns={"processed_input": "feature_name"}).copy()
    bqml = bqml[~bqml["feature_name"].isin(["__INTERCEPT__", "intercept", "Intercept"])]
    bqml["bqml_weight"] = pd.to_numeric(bqml["bqml_weight"], errors="coerce")
    orientation_multiplier = -1.0 if bqml_reference.get("score_orientation") == "reverse_probability" else 1.0
    bqml["bqml_oriented_weight"] = orientation_multiplier * bqml["bqml_weight"]
    merged = selected_coefficients.merge(
        bqml[["feature_name", "bqml_weight", "bqml_oriented_weight"]],
        on="feature_name",
        how="inner",
    )
    if merged.empty:
        return merged
    merged["coefficient_sign_matches_bqml"] = np.sign(merged["oriented_coefficient"]) == np.sign(merged["bqml_oriented_weight"])
    merged["abs_bqml_oriented_weight"] = merged["bqml_oriented_weight"].abs()
    merged["abs_bqml_rank"] = merged["abs_bqml_oriented_weight"].rank(method="first", ascending=False)
    merged["rank_gap"] = merged["abs_oriented_rank"] - merged["abs_bqml_rank"]
    return merged.sort_values("abs_oriented_rank")


def build_implementation_audit(
    config: RunnerConfig,
    experiment: Experiment,
    panel: pd.DataFrame,
    feature_frame: pd.DataFrame,
    feature_columns: list[str],
    candidates: list[CandidateResult],
    selected: CandidateResult,
    bqml_reference: dict[str, Any],
    bqml_weight_alignment: pd.DataFrame,
    bqml_weight_error: str | None,
) -> dict[str, Any]:
    feature_hash = hashlib.sha256("\n".join(feature_columns).encode("utf-8")).hexdigest()
    split_summary = []
    for split, group in panel.groupby("split_tag", dropna=False):
        labeled = group["target_label"].notna()
        split_summary.append({
            "split_tag": str(split),
            "row_count": int(len(group)),
            "labeled_rows": int(labeled.sum()),
            "target_positive_rate": _float_or_none(group.loc[labeled, "target_label"].astype(float).mean()) if labeled.any() else None,
            "target_return_available_rows": int(group["target_return"].notna().sum()),
        })

    missing_rates = feature_frame.isna().mean().sort_values(ascending=False)
    alignment_summary = summarize_bqml_weight_alignment(bqml_weight_alignment, bqml_weight_error)
    return {
        "audit_version": "sklearn_bqml_parity_audit_v1",
        "purpose": "debug sklearn vs BQML model-quality parity differences",
        "experiment": experiment.to_params(),
        "candidate_grid": {
            "version": "sklearn_logistic_parity_v1",
            "candidate_count": len(candidates),
            "candidate_ids": [candidate.candidate_id for candidate in candidates],
            "penalties": sorted({str(candidate.model_params.get("penalty")) for candidate in candidates}),
            "C_values": sorted({float(candidate.model_params.get("C")) for candidate in candidates}),
            "l1_ratios": sorted({
                float(candidate.model_params["l1_ratio"])
                for candidate in candidates
                if candidate.model_params.get("l1_ratio") is not None
            }),
            "solver": config.logistic_solver,
            "class_weight": config.logistic_class_weight,
            "max_iter": config.logistic_max_iter,
        },
        "selected": {
            "candidate_id": selected.candidate_id,
            "score_orientation": selected.score_orientation,
            "oriented_valid_rank_ic_mean": selected.metrics.get("oriented_valid_rank_ic_mean"),
            "valid_topn_fwd_ret_mean": selected.metrics.get("valid_topn_fwd_ret_mean"),
            "roc_auc": selected.metrics.get("roc_auc"),
            "model_quality_parity_status": selected.metrics.get("model_quality_parity_status"),
            "model_quality_status": selected.metrics.get("model_quality_status"),
        },
        "bqml_reference": bqml_reference,
        "split_summary": split_summary,
        "feature_schema": {
            "feature_count": len(feature_columns),
            "feature_order_sha256": feature_hash,
            "first_10_features": feature_columns[:10],
            "last_10_features": feature_columns[-10:],
        },
        "feature_missingness": {
            "mean_missing_rate": _float_or_none(missing_rates.mean()),
            "max_missing_rate": _float_or_none(missing_rates.max()),
            "all_missing_feature_count": int((missing_rates >= 1.0).sum()),
            "top_missing_features": [
                {"feature_name": str(name), "missing_rate": _float_or_none(value)}
                for name, value in missing_rates.head(15).items()
            ],
        },
        "preprocess": {
            "preprocess_version": config.preprocess_version,
            "winsor_lower": config.winsor_lower,
            "winsor_upper": config.winsor_upper,
            "train_only_statistics": True,
            "uses_median_fill": True,
            "uses_winsorization": True,
            "uses_zscore": True,
        },
        "known_semantic_differences": {
            "bqml_preprocess_version": "raw_v0",
            "sklearn_preprocess_version": config.preprocess_version,
            "bqml_auto_class_weights": bqml_reference.get("auto_class_weights"),
            "sklearn_class_weight": config.logistic_class_weight,
            "note": "Differences are recorded for audit; class_weight remains None per Cloud Run PRD.",
        },
        "bqml_weight_alignment": alignment_summary,
    }


def summarize_bqml_weight_alignment(frame: pd.DataFrame, error: str | None) -> dict[str, Any]:
    if error:
        return {"status": "unavailable", "error": error}
    if frame.empty:
        return {"status": "empty"}
    corr = frame[["oriented_coefficient", "bqml_oriented_weight"]].corr().iloc[0, 1]
    sign_rate = frame["coefficient_sign_matches_bqml"].mean()
    return {
        "status": "available",
        "matched_feature_count": int(len(frame)),
        "oriented_weight_correlation": _float_or_none(corr),
        "sign_agreement_rate": _float_or_none(sign_rate),
        "top_rank_gap_features": frame.reindex(frame["rank_gap"].abs().sort_values(ascending=False).index)
        .head(10)[["feature_name", "abs_oriented_rank", "abs_bqml_rank", "rank_gap"]]
        .to_dict(orient="records"),
    }


def write_registry(
    client: bigquery.Client,
    config: RunnerConfig,
    experiment: Experiment,
    candidates: list[CandidateResult],
    selected: CandidateResult,
    selected_model_id: str,
    selected_artifact_uri: str,
    *,
    force_replace: bool,
) -> None:
    if force_replace:
        execute_query(
            client,
            f"""
            DELETE FROM `{ADS}.ads_model_registry`
            WHERE strategy_id = @strategy_id
              AND JSON_VALUE(model_params_json, '$.run_id') = @run_id
            """,
            [
                bigquery.ScalarQueryParameter("strategy_id", "STRING", config.strategy_id),
                bigquery.ScalarQueryParameter("run_id", "STRING", experiment.run_id),
            ],
        )
    rows = []
    now = datetime.now(timezone.utc)
    git_commit = get_git_commit()
    for candidate in candidates:
        is_selected = candidate.candidate_id == selected.candidate_id
        model_id = selected_model_id if is_selected else f"s1_sklearn_{run_safe(experiment.run_id)}__{candidate.candidate_id}"
        model_uri = join_gs_uri(
            config.model_artifact_base_uri,
            "ml_pv_clf_v0",
            f"run_id={experiment.run_id}",
            f"model_id={model_id}",
        ) if is_selected else None
        params_json = {
            "run_id": experiment.run_id,
            "experiment_id": experiment.experiment_id,
            "prediction_run_id": experiment.prediction_run_id,
            "execution_backend": config.execution_backend,
            "candidate_id": candidate.candidate_id,
            "estimator": "sklearn.linear_model.LogisticRegression",
            "estimator_params": candidate.model_params,
            "label_horizon": experiment.label_horizon,
            "feature_set_id": experiment.feature_set_id,
            "preprocess_version": config.preprocess_version,
            "class_weight": config.logistic_class_weight,
        }
        metrics_json = dict(candidate.metrics)
        metrics_json["model_artifact_uri"] = model_uri
        metrics_json["preprocess_artifact_uri"] = join_gs_uri(model_uri, "preprocess.joblib") if model_uri else None
        metrics_json["selected_candidate_id"] = selected.candidate_id
        metrics_json["execution_backend"] = config.execution_backend
        rows.append({
            "model_id": model_id,
            "strategy_id": config.strategy_id,
            "model_family": "sklearn_logistic_regression",
            "horizon": experiment.label_horizon,
            "feature_version": experiment.feature_version,
            "label_version": "open_to_close_h1_5_10_20_v20260601",
            "preprocess_version": config.preprocess_version,
            "train_start_date": experiment.train_start,
            "train_end_date": experiment.train_end,
            "valid_start_date": experiment.valid_start,
            "valid_end_date": experiment.valid_end,
            "model_params_json": json.dumps(params_json, ensure_ascii=False, default=str),
            "metrics_json": json.dumps(metrics_json, ensure_ascii=False, default=str),
            "model_uri": model_uri,
            "git_commit": git_commit,
            "status": "selected" if is_selected else "candidate",
            "created_at": now,
        })
    load_dataframe(client, pd.DataFrame(rows), f"{ADS}.ads_model_registry")


def write_predictions(
    client: bigquery.Client,
    config: RunnerConfig,
    experiment: Experiment,
    predict_panel: pd.DataFrame,
    predict_feature_frame: pd.DataFrame,
    preprocessor: MedianWinsorZScorePreprocessor,
    selected: CandidateResult,
    model_id: str,
) -> None:
    x_pred = preprocessor.transform(predict_feature_frame)
    raw_score = selected.model.predict_proba(x_pred)[:, 1]
    oriented = 1.0 - raw_score if selected.score_orientation == "reverse_probability" else raw_score
    out = predict_panel[["trade_date", "sec_code"]].copy()
    out["model_id"] = model_id
    out["predict_date"] = pd.to_datetime(out["trade_date"]).dt.date
    out["horizon"] = experiment.label_horizon
    out["score"] = oriented
    out["raw_score"] = raw_score
    out["score_orientation"] = selected.score_orientation
    out["feature_version"] = experiment.feature_version
    out["run_id"] = experiment.run_id
    out = out.sort_values(["predict_date", "score", "sec_code"], ascending=[True, False, True])
    out["rank_raw"] = out.groupby("predict_date").cumcount() + 1
    counts = out.groupby("predict_date")["sec_code"].transform("count")
    out["rank_pct"] = 1.0 - ((out["rank_raw"] - 1) / (counts - 1).replace(0, np.nan))
    out["rank_pct"] = out["rank_pct"].fillna(1.0)
    out["created_at"] = datetime.now(timezone.utc)
    out = out[[
        "model_id", "predict_date", "horizon", "sec_code", "score", "raw_score",
        "score_orientation", "rank_raw", "rank_pct", "feature_version", "run_id", "created_at",
    ]]
    load_dataframe(client, out, f"{ADS}.ads_model_prediction_daily")


def clear_train_predict_outputs(client: bigquery.Client, experiment: Experiment) -> None:
    params = [
        bigquery.ScalarQueryParameter("run_id", "STRING", experiment.run_id),
        bigquery.ScalarQueryParameter("start_date", "DATE", experiment.valid_start),
        bigquery.ScalarQueryParameter("end_date", "DATE", experiment.test_end),
    ]
    execute_query(
        client,
        f"""
        DELETE FROM `{ADS}.ads_model_prediction_daily`
        WHERE run_id = @run_id
          AND predict_date BETWEEN @start_date AND @end_date
        """,
        params,
    )


def artifact_dir(config: RunnerConfig, experiment: Experiment, model_id: str) -> Path:
    return Path(config.local_mirror_root) / "models" / "ml_pv_clf_v0" / f"run_id={experiment.run_id}" / f"model_id={model_id}"


def requirements_snapshot() -> str:
    try:
        import sklearn
        return "\n".join([
            f"scikit-learn=={sklearn.__version__}",
            f"numpy=={np.__version__}",
            f"pandas=={pd.__version__}",
        ]) + "\n"
    except Exception:
        return "requirements snapshot unavailable\n"


def _mean_or_nan(values: list[float]) -> float:
    return float(np.mean(values)) if values else math.nan


def _std_or_nan(values: list[float]) -> float:
    return float(np.std(values, ddof=1)) if len(values) > 1 else math.nan


def _nan_to_zero(value: float) -> float:
    return 0.0 if value is None or not np.isfinite(value) else float(value)


def _neg_inf_if_nan(value: float) -> float:
    return -math.inf if value is None or not np.isfinite(value) else float(value)


def safe_divide(numerator: Any, denominator: Any) -> float:
    if denominator in (0, None) or pd.isna(denominator):
        return math.nan
    return float(numerator) / float(denominator)


def _float_or_none(value: Any) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(value):
        return None
    return value


def _first_float(payload: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


if __name__ == "__main__":
    raise SystemExit(main())
