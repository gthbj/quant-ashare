#!/usr/bin/env python3
"""Final-refit the selected annual rolling candidate and write predictions."""

from __future__ import annotations

import argparse
import dataclasses
import json
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from google.cloud import bigquery

from scripts.strategy1_cloudrun.bq_io import (
    join_gs_uri,
    make_client,
    query_dataframe,
    upload_directory_to_gcs,
    write_json,
)
from scripts.strategy1_cloudrun.config import (
    Experiment,
    add_common_args,
    apply_cli_overrides,
    experiment_from_b64,
    load_runner_config,
)
from scripts.strategy1_cloudrun.dataset_roles import TableResolver
from scripts.strategy1_cloudrun.preprocess import build_preprocessor, feature_frame_from_panel

from quant_ashare.strategy1.train_predict import (
    CandidateResult,
    artifact_dir,
    build_fit_kwargs,
    build_model,
    clear_train_predict_outputs,
    materialize_artifacts,
    model_id_for_candidate,
    training_target,
    write_predictions,
    write_registry,
)


def main() -> int:
    args = parse_args()
    config = apply_cli_overrides(load_runner_config(args.config), args)
    experiment = experiment_from_b64(args.experiment_json)
    source_run_id = args.source_run_id or experiment.raw.get("source_run_id") or experiment.parent_run_id
    source_panel_run_id = args.source_panel_run_id or experiment.raw.get("source_panel_run_id") or source_run_id
    refit_train_start = args.refit_train_start or experiment.raw.get("final_refit_train_start") or experiment.train_start
    refit_train_end = args.refit_train_end or experiment.raw.get("final_refit_train_end") or experiment.train_end
    if not source_run_id or not source_panel_run_id:
        raise ValueError("refit requires --source-run-id and --source-panel-run-id")

    plan = {
        "entrypoint": "refit_register_predict",
        "project": config.project,
        "region": config.region,
        "output_dataset_role": config.output_dataset_role,
        "experiment": experiment.to_params(),
        "source_run_id": source_run_id,
        "source_panel_run_id": source_panel_run_id,
        "selected_candidate_id": args.selected_candidate_id,
        "refit_train_start": refit_train_start,
        "refit_train_end": refit_train_end,
        "skip_gcs_upload": args.skip_gcs_upload,
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    result = run_refit_register_predict(
        config=config,
        experiment=experiment,
        source_run_id=source_run_id,
        source_panel_run_id=source_panel_run_id,
        refit_train_start=refit_train_start,
        refit_train_end=refit_train_end,
        selected_candidate_id=args.selected_candidate_id,
        force_replace=args.force_replace,
        skip_gcs_upload=args.skip_gcs_upload,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategy 1 annual rolling final refit")
    add_common_args(parser)
    parser.add_argument("--experiment-json", required=True, help="Base64 encoded refit experiment payload")
    parser.add_argument("--source-run-id", default=None, help="Selection run id that owns selected candidate registry")
    parser.add_argument("--source-panel-run-id", default=None, help="Run id that owns the reusable BigQuery panel")
    parser.add_argument("--selected-candidate-id", default=None, help="Optional guard for the selected candidate id")
    parser.add_argument("--refit-train-start", default=None, help="Resolved final refit training start date")
    parser.add_argument("--refit-train-end", default=None, help="Resolved final refit training end date")
    parser.add_argument("--force-replace", action="store_true")
    parser.add_argument("--skip-gcs-upload", action="store_true")
    return parser.parse_args()


def run_refit_register_predict(
    *,
    config,
    experiment: Experiment,
    source_run_id: str,
    source_panel_run_id: str,
    refit_train_start: str,
    refit_train_end: str,
    selected_candidate_id: str | None,
    force_replace: bool,
    skip_gcs_upload: bool,
) -> dict[str, Any]:
    client = make_client(config.project, config.region)
    source = load_source_selected_candidate(
        client,
        config,
        source_run_id=source_run_id,
        selected_candidate_id=selected_candidate_id,
    )
    refit_experiment = dataclasses.replace(
        experiment,
        train_start=refit_train_start,
        train_end=refit_train_end,
        prediction_run_id=experiment.run_id,
    )
    panel = load_source_panel(
        client,
        config,
        source_panel_run_id=source_panel_run_id,
        start_date=refit_train_start,
        end_date=refit_experiment.predict_end,
    )
    if panel.empty:
        raise RuntimeError(f"source panel has no rows for source_panel_run_id={source_panel_run_id}")

    refit_start = _date_value(refit_train_start)
    refit_end = _date_value(refit_train_end)
    predict_start = _date_value(refit_experiment.predict_start)
    predict_end = _date_value(refit_experiment.predict_end)
    trade_dates = pd.to_datetime(panel["trade_date"]).dt.date
    if trade_dates.min() > refit_start or trade_dates.max() < predict_end:
        raise RuntimeError(
            "source panel coverage does not cover refit/predict window: "
            f"{trade_dates.min()}..{trade_dates.max()} vs {refit_start}..{predict_end}"
        )
    open_train_dates = load_open_trade_dates(
        client,
        config.project,
        start_date=refit_start,
        end_date=refit_end,
    )
    open_predict_dates = load_open_trade_dates(
        client,
        config.project,
        start_date=predict_start,
        end_date=predict_end,
    )
    _assert_panel_covers_open_dates(
        panel_dates=trade_dates,
        open_dates=open_train_dates,
        context="source panel refit train window",
    )
    _assert_panel_covers_open_dates(
        panel_dates=trade_dates[panel["target_label"].notna()],
        open_dates=open_train_dates,
        context="source panel refit labeled train window",
    )
    _assert_panel_covers_open_dates(
        panel_dates=trade_dates,
        open_dates=open_predict_dates,
        context="source panel prediction window",
    )

    feature_frame, feature_columns = feature_frame_from_panel(panel)
    panel = panel.reset_index(drop=True)
    feature_frame = feature_frame.reset_index(drop=True)
    panel = panel.drop(columns=["feature_values_json", "feature_column_list"])
    trade_dates = pd.to_datetime(panel["trade_date"]).dt.date
    train_mask = (trade_dates >= refit_start) & (trade_dates <= refit_end) & panel["target_label"].notna()
    predict_mask = (trade_dates >= predict_start) & (trade_dates <= predict_end)
    if int(train_mask.sum()) == 0:
        raise RuntimeError("refit train window has no labeled samples")
    if int(predict_mask.sum()) == 0:
        raise RuntimeError("refit predict window has no rows")
    predict_dates = sorted(set(trade_dates[predict_mask]))
    if predict_dates[0] != predict_start or predict_dates[-1] != predict_end:
        raise RuntimeError(
            f"prediction boundary mismatch: {predict_dates[0]}..{predict_dates[-1]} "
            f"!= {predict_start}..{predict_end}"
        )

    preprocessor = build_preprocessor(
        config.preprocess_version,
        feature_columns,
        winsor_lower=config.winsor_lower,
        winsor_upper=config.winsor_upper,
    ).fit(feature_frame.loc[train_mask])
    x_train = preprocessor.transform(feature_frame.loc[train_mask])
    y_train = panel.loc[train_mask, "target_label"].astype(int).to_numpy()
    train_returns = panel.loc[train_mask, "target_return"].astype(float).to_numpy()
    sample_weight = panel.loc[train_mask, "sample_weight"].fillna(1.0).astype(float).to_numpy()
    candidate_cfg = source["candidate_cfg"]
    model_family = str(candidate_cfg.get("model_family") or "logistic_regression")
    random_state = int(candidate_cfg.get("random_state") or config.random_state)
    model, model_params, default_score_source, default_reverse_method = build_model(candidate_cfg, config, random_state=random_state)
    model.fit(
        x_train,
        training_target(model_family, y_train, train_returns),
        **build_fit_kwargs(model_family, sample_weight),
    )

    source_metrics = dict(source["metrics"])
    score_source = str(source_metrics.get("score_source") or default_score_source)
    reverse_method = str(source_metrics.get("score_reverse_method") or default_reverse_method)
    score_orientation = str(source_metrics.get("score_orientation") or "identity")
    orientation_reason = str(source_metrics.get("orientation_decision_reason") or "source_selection_orientation")
    candidate_id = str(candidate_cfg["candidate_id"])
    refit_metrics = {
        **source_metrics,
        "candidate_id": candidate_id,
        "selected_candidate_id": candidate_id,
        "source_model_id": source["model_id"],
        "source_run_id": source_run_id,
        "source_panel_run_id": source_panel_run_id,
        "refit": True,
        "refit_train_start": refit_train_start,
        "refit_train_end": refit_train_end,
        "train_start_date": refit_train_start,
        "train_end_date": refit_train_end,
        "preprocess_fit_start": refit_train_start,
        "preprocess_fit_end": refit_train_end,
        "refit_prediction_start": refit_experiment.predict_start,
        "refit_prediction_end": refit_experiment.predict_end,
        "score_source": score_source,
        "score_reverse_method": reverse_method,
        "score_orientation": score_orientation,
        "orientation_decision_reason": orientation_reason,
        "refit_train_row_count": int(train_mask.sum()),
        "refit_prediction_row_count": int(predict_mask.sum()),
        "model_family": model_family,
    }
    selected = CandidateResult(
        candidate_id=candidate_id,
        model=model,
        score_orientation=score_orientation,
        orientation_reason=orientation_reason,
        raw_valid_scores=np.array([], dtype=np.float64),
        oriented_valid_scores=np.array([], dtype=np.float64),
        metrics=refit_metrics,
        model_params=model_params,
    )
    model_id = model_id_for_candidate(refit_experiment.run_id, selected)
    artifact_local_dir = artifact_dir(config, refit_experiment, model_id)
    artifact_uri = join_gs_uri(
        config.model_artifact_base_uri,
        "ml_pv_clf_v0",
        f"run_id={refit_experiment.run_id}",
        f"model_id={model_id}",
    )
    selected.metrics["model_artifact_uri"] = artifact_uri
    selected.metrics["preprocess_artifact_uri"] = join_gs_uri(artifact_uri, "preprocess.joblib")
    selected.metrics["preprocess_stats_uri"] = join_gs_uri(artifact_uri, "preprocess_stats.json")
    materialize_artifacts(config, refit_experiment, selected, preprocessor, feature_columns, artifact_local_dir, artifact_uri)
    write_json(
        artifact_local_dir / "preprocess_stats.json",
        {
            "refit": True,
            "fit_start": refit_train_start,
            "fit_end": refit_train_end,
            "source_run_id": source_run_id,
            "source_panel_run_id": source_panel_run_id,
            "preprocess_version": config.preprocess_version,
            "feature_count": len(feature_columns),
        },
    )
    uploaded = [] if skip_gcs_upload else upload_directory_to_gcs(config.project, artifact_local_dir, artifact_uri)

    if force_replace:
        clear_train_predict_outputs(client, config, refit_experiment)
    write_registry(client, config, refit_experiment, [selected], selected, model_id, artifact_uri, force_replace=force_replace)
    write_predictions(
        client,
        config,
        refit_experiment,
        panel.loc[predict_mask].copy(),
        feature_frame.loc[predict_mask],
        preprocessor,
        selected,
        model_id,
    )
    return {
        "status": "succeeded",
        "run_id": refit_experiment.run_id,
        "source_run_id": source_run_id,
        "source_panel_run_id": source_panel_run_id,
        "model_id": model_id,
        "selected_candidate_id": selected.candidate_id,
        "refit_train_start": refit_train_start,
        "refit_train_end": refit_train_end,
        "prediction_rows": int(predict_mask.sum()),
        "model_artifact_uri": artifact_uri,
        "uploaded_artifacts": uploaded,
    }


def load_source_selected_candidate(
    client: bigquery.Client,
    config,
    *,
    source_run_id: str,
    selected_candidate_id: str | None,
) -> dict[str, Any]:
    model_registry = TableResolver(
        dataset_role=config.output_dataset_role,
        project=config.project,
    ).fqn("model_registry")
    frame = query_dataframe(
        client,
        f"""
        SELECT model_id, model_params_json, metrics_json, model_uri, created_at
        FROM `{model_registry}`
        WHERE strategy_id = @strategy_id
          AND status = 'selected'
          AND JSON_VALUE(model_params_json, '$.run_id') = @source_run_id
        ORDER BY created_at DESC
        LIMIT 2
        """,
        [
            bigquery.ScalarQueryParameter("strategy_id", "STRING", config.strategy_id),
            bigquery.ScalarQueryParameter("source_run_id", "STRING", source_run_id),
        ],
    )
    if len(frame) != 1:
        raise RuntimeError(f"expected exactly one selected source registry row for {source_run_id}, got {len(frame)}")
    row = frame.iloc[0]
    params = json.loads(row["model_params_json"] or "{}")
    metrics = json.loads(row["metrics_json"] or "{}")
    candidate_id = str(params.get("candidate_id") or metrics.get("selected_candidate_id") or metrics.get("candidate_id") or "")
    if not candidate_id:
        raise RuntimeError(f"source registry row for {source_run_id} has no candidate id")
    if selected_candidate_id and selected_candidate_id != candidate_id:
        raise RuntimeError(f"selected candidate mismatch: expected {selected_candidate_id}, got {candidate_id}")
    candidate_cfg = dict(params.get("estimator_params") or {})
    candidate_cfg["candidate_id"] = candidate_id
    model_family = params.get("estimator") or metrics.get("model_family") or candidate_cfg.get("model_family")
    if not model_family:
        raise RuntimeError(f"source registry row for {source_run_id} has no model family")
    candidate_cfg["model_family"] = model_family
    return {
        "model_id": row["model_id"],
        "model_uri": row["model_uri"],
        "params": params,
        "metrics": metrics,
        "candidate_cfg": candidate_cfg,
    }


def load_source_panel(
    client: bigquery.Client,
    config,
    *,
    source_panel_run_id: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    training_panel = TableResolver(
        dataset_role=config.output_dataset_role,
        project=config.project,
    ).fqn("training_panel")
    return query_dataframe(
        client,
        f"""
        SELECT
          run_id, strategy_id, trade_date, sec_code, horizon, split_tag,
          sample_weight, target_label, target_return, feature_values_json,
          feature_column_list, feature_version, label_version, preprocess_version
        FROM `{training_panel}`
        WHERE run_id = @run_id
          AND trade_date BETWEEN @start_date AND @end_date
        ORDER BY trade_date, sec_code
        """,
        [
            bigquery.ScalarQueryParameter("run_id", "STRING", source_panel_run_id),
            bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
        ],
    )


def load_open_trade_dates(
    client: bigquery.Client,
    project: str,
    *,
    start_date: str | date,
    end_date: str | date,
) -> list[date]:
    frame = query_dataframe(
        client,
        f"""
        SELECT cal_date
        FROM `{project}.ashare_dim.dim_trade_calendar`
        WHERE exchange = 'SSE'
          AND is_open = 1
          AND cal_date BETWEEN @start_date AND @end_date
        ORDER BY cal_date
        """,
        [
            bigquery.ScalarQueryParameter("start_date", "DATE", _date_value(start_date)),
            bigquery.ScalarQueryParameter("end_date", "DATE", _date_value(end_date)),
        ],
    )
    return [_date_value(value) for value in frame["cal_date"].tolist()]


def _assert_panel_covers_open_dates(
    *,
    panel_dates: pd.Series,
    open_dates: list[date],
    context: str,
) -> None:
    if not open_dates:
        raise RuntimeError(f"{context} has no SSE open dates")
    panel_date_set = set(pd.to_datetime(panel_dates).dt.date)
    missing = [trade_date for trade_date in open_dates if trade_date not in panel_date_set]
    if missing:
        raise RuntimeError(
            f"{context} is missing {len(missing)} SSE open dates: "
            f"first={missing[0]}, last={missing[-1]}"
        )


def _date_value(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


if __name__ == "__main__":
    raise SystemExit(main())
