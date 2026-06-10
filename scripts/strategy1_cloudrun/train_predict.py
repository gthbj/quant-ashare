#!/usr/bin/env python3
"""Train sklearn logistic candidates and write Strategy 1 predictions.

This entrypoint is designed for Cloud Run Jobs but also supports local smoke
and dry-run. It consumes the existing BigQuery ADS training panel built by
the cataloged `build_training_panel_*` SQL under `sql/strategy1/panel/`;
it does not rebuild DWS/PIT
features itself.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import warnings

import numpy as np
import pandas as pd
from google.cloud import bigquery

from scripts.strategy1_cloudrun import __version__
from scripts.strategy1_cloudrun.acceptance import load_acceptance_contract
from scripts.strategy1_cloudrun.bq_io import (
    ADS,
    env_container_image,
    execute_query,
    get_git_commit,
    join_gs_uri,
    json_dumps_strict,
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
from scripts.strategy1_cloudrun.preprocess import build_preprocessor, feature_frame_from_panel


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
    predict_mask = panel["split_tag"].isin(["valid", "test", "final_holdout"])
    if train_mask.sum() == 0:
        raise RuntimeError("train split has no labeled samples")
    if valid_mask.sum() == 0:
        raise RuntimeError("valid split has no prediction samples")

    preprocessor = build_preprocessor(
        config.preprocess_version,
        feature_columns,
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

    parity = compute_model_quality_parity(client, config, selected)
    selected.metrics.update(parity)
    if parity["model_quality_parity_status"] == "passed":
        selected.metrics["model_quality_status"] = "model_quality_equivalent"
        selected.metrics["model_quality_status_reason"] = "sklearn_vs_bqml_parity_passed"
    else:
        selected.metrics["model_quality_status"] = "model_quality_not_equivalent"
        selected.metrics["model_quality_status_reason"] = "sklearn_vs_bqml_parity_failed"

    model_id = model_id_for_candidate(experiment.run_id, selected)
    artifact_local_dir = artifact_dir(config, experiment, model_id)
    artifact_uri = join_gs_uri(
        config.model_artifact_base_uri,
        "ml_pv_clf_v0",
        f"run_id={experiment.run_id}",
        f"model_id={model_id}",
    )
    materialize_artifacts(config, experiment, selected, preprocessor, feature_columns, artifact_local_dir, artifact_uri)
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
            bigquery.ScalarQueryParameter(
                "test_end",
                "DATE",
                experiment.final_holdout_end or experiment.predict_end or experiment.test_end,
            ),
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
    preprocessor,
) -> CandidateResult:
    valid_mask = panel["split_tag"].eq("valid")
    train_mask = panel["split_tag"].eq("train") & panel["target_label"].notna()
    x_valid = preprocessor.transform(feature_frame.loc[valid_mask])
    valid_panel = panel.loc[valid_mask, ["trade_date", "sec_code", "target_label", "target_return"]].copy()
    return train_candidate_from_matrices(
        config,
        candidate_cfg,
        x_train,
        y_train,
        panel.loc[train_mask, "target_return"].astype(float).to_numpy(),
        sample_weight,
        valid_panel,
        x_valid,
    )


def train_candidate_from_matrices(
    config: RunnerConfig,
    candidate_cfg: dict[str, Any],
    x_train: np.ndarray,
    y_train: np.ndarray,
    train_returns: np.ndarray | None,
    sample_weight: np.ndarray,
    valid_panel: pd.DataFrame,
    x_valid: np.ndarray,
    *,
    cv_panel: pd.DataFrame | None = None,
    x_cv: np.ndarray | None = None,
) -> CandidateResult:
    from sklearn.exceptions import ConvergenceWarning

    model_family = candidate_cfg.get("model_family", "logistic_regression")
    max_iter = int(candidate_cfg.get("max_iter") or candidate_cfg.get("n_estimators") or config.logistic_max_iter)
    random_state = int(candidate_cfg.get("random_state") or config.random_state)
    model, params, score_source, reverse_method = build_model(candidate_cfg, config, random_state=random_state)
    fit_kwargs = build_fit_kwargs(model_family, sample_weight)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        model.fit(x_train, training_target(model_family, y_train, train_returns), **fit_kwargs)
    convergence_warnings = [
        str(item.message)
        for item in caught
        if issubclass(item.category, ConvergenceWarning)
    ]
    n_iter_max = int(np.max(getattr(model, "n_iter_", [0])))
    converged = lightgbm_converged(model_family, model) if model_family.startswith("lightgbm_") else (
        not convergence_warnings and n_iter_max < max_iter
    )
    convergence_check_type = (
        "booster_present_no_early_stopping"
        if model_family.startswith("lightgbm_")
        else "sklearn_convergence_warning_and_n_iter"
    )

    raw_score = score_model(model, x_valid, score_source)

    raw_metrics = evaluate_scores(valid_panel, raw_score)
    rev_score = reverse_scores(raw_score, reverse_method)
    rev_metrics = evaluate_scores(valid_panel, rev_score)
    orientation, reason = decide_orientation(raw_metrics, rev_metrics)
    oriented_score = reverse_scores(raw_score, reverse_method) if orientation == "reverse_probability" else raw_score
    oriented_metrics = evaluate_scores(valid_panel, oriented_score)
    class_metrics = evaluate_classification(valid_panel, raw_score) if score_source.endswith("label_1") else {
        "roc_auc": math.nan,
        "log_loss": math.nan,
    }
    cv_metrics = evaluate_cv_folds(
        config=config,
        candidate_cfg=candidate_cfg,
        model_family=model_family,
        cv_panel=cv_panel,
        x_cv=x_cv,
        random_state=random_state,
        score_source=score_source,
        reverse_method=reverse_method,
    )

    metrics = {
        "candidate_id": candidate_cfg["candidate_id"],
        "score_source": score_source,
        "score_orientation": orientation,
        "orientation_decision_split": "valid",
        "orientation_decision_reason": reason,
        "score_reverse_method": reverse_method,
        "raw_valid_rank_ic_mean": raw_metrics["rank_ic_mean"],
        "reverse_valid_rank_ic_mean": rev_metrics["rank_ic_mean"],
        "reversed_valid_rank_ic_mean": rev_metrics["rank_ic_mean"],
        "oriented_valid_rank_ic_mean": oriented_metrics["rank_ic_mean"],
        "oriented_valid_rank_ic_std": oriented_metrics["rank_ic_std"],
        "oriented_valid_rank_ic_icir": safe_divide(oriented_metrics["rank_ic_mean"], oriented_metrics["rank_ic_std"]),
        "oriented_valid_rank_ic_days": oriented_metrics["rank_ic_days"],
        "raw_valid_top_minus_bottom": raw_metrics["top_minus_bottom"],
        "reversed_valid_top_minus_bottom": rev_metrics["top_minus_bottom"],
        "valid_top_minus_bottom_fwd_ret_mean": oriented_metrics["top_minus_bottom"],
        "valid_topn_fwd_ret_mean": oriented_metrics["topn_fwd_ret_mean"],
        "roc_auc": class_metrics["roc_auc"],
        "log_loss": class_metrics["log_loss"],
        "valid_prediction_rows": int(len(valid_panel)),
        "valid_eval_rows": int(valid_panel["target_return"].notna().sum()),
        "valid_eval_coverage": safe_divide(valid_panel["target_return"].notna().sum(), len(valid_panel)),
        "model_family": model_family,
        "model_library": model_library_for_family(model_family),
        "model_library_version": model_library_version(model_family),
        "solver": params.get("solver"),
        "penalty": params.get("penalty"),
        "C": candidate_cfg.get("C"),
        "l1_ratio": candidate_cfg.get("l1_ratio"),
        "class_weight": params.get("class_weight"),
        "num_leaves": params.get("num_leaves"),
        "learning_rate": params.get("learning_rate"),
        "n_estimators": params.get("n_estimators"),
        "min_data_in_leaf": params.get("min_child_samples"),
        "feature_fraction": params.get("colsample_bytree"),
        "bagging_fraction": params.get("subsample"),
        "lambda_l1": params.get("reg_alpha"),
        "lambda_l2": params.get("reg_lambda"),
        "num_threads": params.get("n_jobs"),
        "max_iter": max_iter,
        "random_state": random_state,
        "n_iter_max": n_iter_max,
        "converged": converged,
        "convergence_status": "converged" if converged else "not_converged",
        "convergence_check_type": convergence_check_type,
        "early_stopping_used": False,
        "lightgbm_best_iteration": getattr(model, "best_iteration_", None) if model_family.startswith("lightgbm_") else None,
        "convergence_warning_count": len(convergence_warnings),
        "convergence_warnings": convergence_warnings[:3],
    }
    metrics.update(cv_metrics)
    metrics["valid_signal_status"] = classify_valid_signal(
        metrics,
        weak_rank_ic_threshold=weak_valid_rank_ic_threshold(config),
    )
    metrics["model_complexity_rank"] = model_complexity_rank(metrics)
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


def build_model(candidate_cfg: dict[str, Any], config: RunnerConfig, *, random_state: int):
    model_family = candidate_cfg.get("model_family", "logistic_regression")
    if model_family == "logistic_regression":
        from sklearn.linear_model import LogisticRegression

        penalty = _normalize_penalty(candidate_cfg.get("penalty"))
        solver = candidate_cfg.get("solver") or config.logistic_solver
        class_weight = _normalize_optional_string(
            candidate_cfg.get("class_weight", config.logistic_class_weight)
        )
        params = {
            "penalty": penalty,
            "solver": solver,
            "max_iter": int(candidate_cfg.get("max_iter") or config.logistic_max_iter),
            "random_state": random_state,
            "class_weight": class_weight,
            "n_jobs": None,
        }
        if penalty is not None:
            params["C"] = float(candidate_cfg["C"])
        if candidate_cfg.get("l1_ratio") is not None:
            params["l1_ratio"] = float(candidate_cfg["l1_ratio"])
        return LogisticRegression(**params), params, "sklearn_predict_proba_label_1", "probability_complement"

    if model_family == "lightgbm_gbdt":
        from lightgbm import LGBMClassifier

        params = lightgbm_params(candidate_cfg, random_state=random_state, objective="binary")
        return LGBMClassifier(**params), params, "lightgbm_predict_proba_label_1", "probability_complement"

    if model_family == "lightgbm_regression":
        from lightgbm import LGBMRegressor

        params = lightgbm_params(candidate_cfg, random_state=random_state, objective="regression")
        return LGBMRegressor(**params), params, "lightgbm_predict", "negate"

    raise ValueError(f"unsupported model_family: {model_family!r}")


def lightgbm_params(candidate_cfg: dict[str, Any], *, random_state: int, objective: str) -> dict[str, Any]:
    params = {
        "objective": objective,
        "num_leaves": int(candidate_cfg.get("num_leaves", 31)),
        "learning_rate": float(candidate_cfg.get("learning_rate", 0.05)),
        "n_estimators": int(candidate_cfg.get("n_estimators", 300)),
        "min_child_samples": int(candidate_cfg.get("min_data_in_leaf", candidate_cfg.get("min_child_samples", 300))),
        "subsample": float(candidate_cfg.get("bagging_fraction", candidate_cfg.get("subsample", 0.9))),
        "subsample_freq": int(candidate_cfg.get("bagging_freq", 1)),
        "colsample_bytree": float(candidate_cfg.get("feature_fraction", candidate_cfg.get("colsample_bytree", 0.9))),
        "reg_alpha": float(candidate_cfg.get("lambda_l1", candidate_cfg.get("reg_alpha", 0.0))),
        "reg_lambda": float(candidate_cfg.get("lambda_l2", candidate_cfg.get("reg_lambda", 0.0))),
        "random_state": random_state,
        "n_jobs": int(candidate_cfg.get("num_threads", 1)),
        "verbosity": int(candidate_cfg.get("verbosity", -1)),
    }
    if candidate_cfg.get("is_unbalance") is not None:
        params["is_unbalance"] = bool(candidate_cfg.get("is_unbalance"))
    if candidate_cfg.get("scale_pos_weight") is not None:
        params["scale_pos_weight"] = float(candidate_cfg["scale_pos_weight"])
    return params


def build_fit_kwargs(model_family: str, sample_weight: np.ndarray | None) -> dict[str, Any]:
    if sample_weight is None:
        return {}
    if model_family in {"logistic_regression", "lightgbm_gbdt", "lightgbm_regression"}:
        return {"sample_weight": sample_weight}
    return {}


def training_target(model_family: str, labels: np.ndarray, returns: np.ndarray | None) -> np.ndarray:
    if model_family == "lightgbm_regression":
        if returns is None:
            raise ValueError("lightgbm_regression requires train target_return")
        return returns.astype(np.float32)
    return labels.astype(int)


def score_model(model: Any, x: np.ndarray, score_source: str) -> np.ndarray:
    if score_source.endswith("predict_proba_label_1"):
        return model.predict_proba(x)[:, 1]
    return np.asarray(model.predict(x), dtype=np.float64)


def reverse_scores(scores: np.ndarray, reverse_method: str) -> np.ndarray:
    if reverse_method == "probability_complement":
        return 1.0 - scores
    if reverse_method == "negate":
        return -scores
    raise ValueError(f"unsupported reverse method: {reverse_method}")


def lightgbm_converged(model_family: str, model: Any) -> bool:
    if not model_family.startswith("lightgbm_"):
        return False
    return getattr(model, "booster_", None) is not None


def evaluate_cv_folds(
    *,
    config: RunnerConfig,
    candidate_cfg: dict[str, Any],
    model_family: str,
    cv_panel: pd.DataFrame | None,
    x_cv: np.ndarray | None,
    random_state: int,
    score_source: str,
    reverse_method: str,
) -> dict[str, Any]:
    if cv_panel is None or x_cv is None or cv_panel.empty:
        return {
            "cv_confirmation_status": "missing",
            "cv_fold_count": 0,
        }
    panel = cv_panel.copy()
    panel["trade_date"] = pd.to_datetime(panel["trade_date"])
    folds = dynamic_cv_folds(panel)
    all_dates = sorted(panel["trade_date"].dropna().unique())
    rows = []
    for fold_id, train_start, train_end, eval_start, eval_end in folds:
        embargoed_train_end = embargo_end_date(all_dates, pd.Timestamp(eval_start), int(candidate_cfg.get("label_horizon") or 5))
        effective_train_end = min(pd.Timestamp(train_end), embargoed_train_end)
        train_mask = (
            panel["trade_date"].between(pd.Timestamp(train_start), effective_train_end)
            & panel["target_label"].notna()
            & (panel["target_return"].notna() if model_family == "lightgbm_regression" else True)
        )
        eval_mask = panel["trade_date"].between(pd.Timestamp(eval_start), pd.Timestamp(eval_end))
        if int(train_mask.sum()) == 0 or int(eval_mask.sum()) == 0:
            rows.append({"fold_id": fold_id, "status": "missing", "rank_ic_mean": math.nan, "top_minus_bottom": math.nan})
            continue
        model, _, _, _ = build_model(candidate_cfg, config, random_state=random_state)
        y_fold = training_target(
            model_family,
            panel.loc[train_mask, "target_label"].astype(int).to_numpy(),
            panel.loc[train_mask, "target_return"].astype(float).to_numpy(),
        )
        weights = panel.loc[train_mask, "sample_weight"].fillna(1.0).astype(float).to_numpy()
        model.fit(x_cv[train_mask.to_numpy()], y_fold, **build_fit_kwargs(model_family, weights))
        raw_score = score_model(model, x_cv[eval_mask.to_numpy()], score_source)
        raw_metrics = evaluate_scores(panel.loc[eval_mask, ["trade_date", "sec_code", "target_label", "target_return"]], raw_score)
        rev_metrics = evaluate_scores(
            panel.loc[eval_mask, ["trade_date", "sec_code", "target_label", "target_return"]],
            reverse_scores(raw_score, reverse_method),
        )
        orientation, _ = decide_orientation(raw_metrics, rev_metrics)
        oriented = reverse_scores(raw_score, reverse_method) if orientation == "reverse_probability" else raw_score
        metrics = evaluate_scores(panel.loc[eval_mask, ["trade_date", "sec_code", "target_label", "target_return"]], oriented)
        rows.append({
            "fold_id": fold_id,
            "status": "succeeded",
            "score_orientation": orientation,
            "rank_ic_mean": metrics["rank_ic_mean"],
            "top_minus_bottom": metrics["top_minus_bottom"],
            "topn_fwd_ret_mean": metrics["topn_fwd_ret_mean"],
            "rank_ic_days": metrics["rank_ic_days"],
        })
    ok_rows = [row for row in rows if row["status"] == "succeeded"]
    rank_values = [float(row["rank_ic_mean"]) for row in ok_rows if math.isfinite(safe_metric(row["rank_ic_mean"]))]
    spread_values = [float(row["top_minus_bottom"]) for row in ok_rows if math.isfinite(safe_metric(row["top_minus_bottom"]))]
    rank_mean = _mean_or_nan(rank_values)
    spread_mean = _mean_or_nan(spread_values)
    passed = len(ok_rows) == 3 and _nan_to_zero(rank_mean) > 0 and _nan_to_zero(spread_mean) > 0
    return {
        "cv_confirmation_status": "passed" if passed else "failed",
        "cv_fold_count": len(ok_rows),
        "cv_rank_ic_mean": rank_mean,
        "cv_rank_ic_std": _std_or_nan(rank_values),
        "cv_top_minus_bottom_fwd_ret_mean": spread_mean,
        "cv_topn_fwd_ret_mean": _mean_or_nan([
            float(row["topn_fwd_ret_mean"])
            for row in ok_rows
            if math.isfinite(safe_metric(row["topn_fwd_ret_mean"]))
        ]),
        "cv_fold_metrics": rows,
    }


def dynamic_cv_folds(
    panel: pd.DataFrame,
    *,
    max_folds: int = 3,
    min_train_years: int = 2,
) -> list[tuple[str, str, str, str, str]]:
    train_panel = panel
    if "split_tag" in panel.columns:
        train_panel = panel.loc[panel["split_tag"].eq("train")]
    train_panel = train_panel.loc[train_panel["trade_date"].notna()].copy()
    if train_panel.empty:
        return []

    train_panel["trade_date"] = pd.to_datetime(train_panel["trade_date"])
    years = sorted(int(year) for year in train_panel["trade_date"].dt.year.dropna().unique())
    eval_years = years[min_train_years:][-max_folds:]
    if not eval_years:
        return []

    train_start = pd.Timestamp(train_panel["trade_date"].min()).date().isoformat()
    folds = []
    for eval_year in eval_years:
        prior_dates = train_panel.loc[train_panel["trade_date"].dt.year < eval_year, "trade_date"]
        eval_dates = train_panel.loc[train_panel["trade_date"].dt.year == eval_year, "trade_date"]
        if prior_dates.empty or eval_dates.empty:
            continue
        folds.append((
            f"cv_{eval_year}",
            train_start,
            pd.Timestamp(prior_dates.max()).date().isoformat(),
            pd.Timestamp(eval_dates.min()).date().isoformat(),
            pd.Timestamp(eval_dates.max()).date().isoformat(),
        ))
    return folds


def safe_metric(value: Any) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return math.nan
    return value if math.isfinite(value) else math.nan


def embargo_end_date(all_dates: list[pd.Timestamp], eval_start: pd.Timestamp, embargo_days: int) -> pd.Timestamp:
    prior = [date for date in all_dates if date < eval_start]
    if not prior:
        return eval_start - pd.Timedelta(days=embargo_days)
    index = max(0, len(prior) - embargo_days)
    return pd.Timestamp(prior[index - 1 if index > 0 else 0])


def model_library_for_family(model_family: str) -> str:
    if model_family.startswith("lightgbm_"):
        return "lightgbm"
    if model_family == "logistic_regression":
        return "sklearn"
    return model_family


def model_library_version(model_family: str) -> str | None:
    try:
        from importlib.metadata import version
        if model_family.startswith("lightgbm_"):
            return version("lightgbm")
        if model_family == "logistic_regression":
            return version("scikit-learn")
    except Exception:
        return None
    return None


def _normalize_penalty(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"", "none", "null"}:
        return None
    return text


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in {"", "none", "null"}:
        return None
    return text


def classify_valid_signal(metrics: dict[str, Any], *, weak_rank_ic_threshold: float = 0.01) -> str:
    rank_ic = _nan_to_zero(float(metrics.get("oriented_valid_rank_ic_mean") or math.nan))
    icir = _nan_to_zero(float(metrics.get("oriented_valid_rank_ic_icir") or math.nan))
    topn = _nan_to_zero(float(metrics.get("valid_topn_fwd_ret_mean") or math.nan))
    spread = _nan_to_zero(float(metrics.get("valid_top_minus_bottom_fwd_ret_mean") or math.nan))
    if rank_ic <= 0:
        return "failed"
    if rank_ic <= weak_rank_ic_threshold or icir <= 0 or (topn <= 0 and spread <= 0):
        return "weak"
    return "stable"


def weak_valid_rank_ic_threshold(config: RunnerConfig) -> float:
    try:
        contract = load_acceptance_contract(config.acceptance_contract_path)
        return float((contract.get("thresholds") or {}).get("weak_valid_rank_ic_threshold", 0.01))
    except Exception:
        return 0.01


def model_complexity_rank(metrics_or_params: dict[str, Any]) -> int:
    model_family = metrics_or_params.get("model_family")
    if model_family == "lightgbm_gbdt":
        leaves = int(metrics_or_params.get("num_leaves") or 31)
        estimators = int(metrics_or_params.get("n_estimators") or 300)
        return 10 + leaves + estimators // 100
    if model_family == "lightgbm_regression":
        leaves = int(metrics_or_params.get("num_leaves") or 31)
        estimators = int(metrics_or_params.get("n_estimators") or 300)
        return 20 + leaves + estimators // 100
    penalty = _normalize_penalty(metrics_or_params.get("penalty"))
    if penalty is None:
        return 0
    if penalty == "l2":
        return 1
    if penalty == "l1":
        return 2
    if penalty == "elasticnet":
        return 3
    return 9


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


def compute_model_quality_parity(client: bigquery.Client, config: RunnerConfig, selected: CandidateResult) -> dict[str, Any]:
    reference = load_bqml_reference_metrics(client, config.bqml_reference_run_id)
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
        "bqml_oriented_valid_rank_ic_mean": bqml_rank_ic,
        "sklearn_oriented_valid_rank_ic_mean": selected.metrics["oriented_valid_rank_ic_mean"],
        "rank_ic_parity_delta": rank_delta,
        "bqml_valid_topn_fwd_ret_mean": bqml_topn,
        "sklearn_valid_topn_fwd_ret_mean": selected.metrics["valid_topn_fwd_ret_mean"],
        "topn_ret_parity_delta": topn_delta,
        "prediction_coverage_parity_delta": coverage_delta,
        "model_quality_parity_status": status,
    }


def load_bqml_reference_metrics(client: bigquery.Client, reference_run_id: str) -> dict[str, Any]:
    sql = f"""
    SELECT model_id, metrics_json
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
    return {
        "model_id": frame.iloc[0]["model_id"],
        "oriented_valid_rank_ic_mean": _first_float(metrics, ["oriented_valid_rank_ic_mean", "rank_ic_mean"]),
        "valid_topn_fwd_ret_mean": _first_float(metrics, ["valid_topn_fwd_ret_mean", "topn_fwd_ret_mean"]),
        "valid_eval_coverage": _first_float(metrics, ["valid_eval_coverage"]),
    }


def materialize_artifacts(
    config: RunnerConfig,
    experiment: Experiment,
    selected: CandidateResult,
    preprocessor: MedianWinsorZScorePreprocessor,
    feature_columns: list[str],
    artifact_local_dir: Path,
    artifact_uri: str,
) -> None:
    import joblib

    artifact_local_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(selected.model, artifact_local_dir / "model.joblib")
    joblib.dump(preprocessor, artifact_local_dir / "preprocess.joblib")
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
            "score_source": selected.metrics.get("score_source"),
            "score_reverse_method": selected.metrics.get("score_reverse_method"),
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
        model_id = selected_model_id if is_selected else model_id_for_candidate(experiment.run_id, candidate)
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
            "estimator": candidate.metrics.get("model_family"),
            "estimator_params": candidate.model_params,
            "label_horizon": experiment.label_horizon,
            "feature_set_id": experiment.feature_set_id,
            "tail_risk_profile_id": experiment.tail_risk_profile_id,
            "preprocess_version": config.preprocess_version,
            "class_weight": candidate.metrics.get("class_weight"),
            "train_start_date": experiment.train_start,
            "train_end_date": experiment.train_end,
            "valid_start_date": experiment.valid_start,
            "valid_end_date": experiment.valid_end,
            "test_start_date": experiment.test_start,
            "test_end_date": experiment.test_end,
            "final_holdout_start_date": experiment.final_holdout_start,
            "final_holdout_end_date": experiment.final_holdout_end,
            "predict_start_date": experiment.predict_start,
            "predict_end_date": experiment.predict_end,
        }
        for key in (
            "search_id", "source_run_id", "sklearn_native_mode",
            "candidate_run_id", "candidate_backtest_id", "shortlist_rank_valid_only",
            "test_reuse_wave_no", "test_reuse_approval_ref", "final_holdout_status",
            "model_backend", "model_library", "model_library_version", "model_search_wave_no",
            "acceptance_contract_version", "cv_confirmation_status", "holdout_watch_flag",
        ):
            if candidate.metrics.get(key) is not None:
                params_json[key] = candidate.metrics.get(key)
        metrics_json = dict(candidate.metrics)
        metrics_json["model_artifact_uri"] = model_uri
        metrics_json["preprocess_artifact_uri"] = join_gs_uri(model_uri, "preprocess.joblib") if model_uri else None
        metrics_json["selected_candidate_id"] = selected.candidate_id
        metrics_json["execution_backend"] = config.execution_backend
        metrics_json["tail_risk_profile_id"] = experiment.tail_risk_profile_id
        rows.append({
            "model_id": model_id,
            "strategy_id": config.strategy_id,
            "model_family": str(candidate.metrics.get("model_family") or "logistic_regression"),
            "horizon": experiment.label_horizon,
            "feature_version": experiment.feature_version,
            "label_version": "open_to_close_h1_5_10_20_v20260601",
            "preprocess_version": config.preprocess_version,
            "train_start_date": experiment.train_start,
            "train_end_date": experiment.train_end,
            "valid_start_date": experiment.valid_start,
            "valid_end_date": experiment.valid_end,
            "model_params_json": json_dumps_strict(params_json, ensure_ascii=False),
            "metrics_json": json_dumps_strict(metrics_json, ensure_ascii=False),
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
    write_predictions_from_preprocessed(client, config, experiment, predict_panel, x_pred, selected, model_id)


def write_predictions_from_preprocessed(
    client: bigquery.Client,
    config: RunnerConfig,
    experiment: Experiment,
    predict_panel: pd.DataFrame,
    x_pred: np.ndarray,
    selected: CandidateResult,
    model_id: str,
) -> None:
    raw_score = score_model(selected.model, x_pred, str(selected.metrics.get("score_source") or "sklearn_predict_proba_label_1"))
    reverse_method = str(selected.metrics.get("score_reverse_method") or "probability_complement")
    oriented = reverse_scores(raw_score, reverse_method) if selected.score_orientation == "reverse_probability" else raw_score
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
        bigquery.ScalarQueryParameter("end_date", "DATE", experiment.final_holdout_end or experiment.predict_end or experiment.test_end),
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
        extras = []
        try:
            import lightgbm
            extras.append(f"lightgbm=={lightgbm.__version__}")
        except Exception:
            pass
        return "\n".join([
            f"scikit-learn=={sklearn.__version__}",
            f"numpy=={np.__version__}",
            f"pandas=={pd.__version__}",
            *extras,
        ]) + "\n"
    except Exception:
        return "requirements snapshot unavailable\n"


def model_id_for_candidate(run_id: str, candidate: CandidateResult) -> str:
    family = str(candidate.metrics.get("model_family") or "logistic_regression")
    if family.startswith("lightgbm_"):
        prefix = "s1_lgbm"
    elif family == "logistic_regression":
        prefix = "s1_sklearn"
    else:
        prefix = "s1_python"
    return f"{prefix}_{run_safe(run_id)}__{candidate.candidate_id}"


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
