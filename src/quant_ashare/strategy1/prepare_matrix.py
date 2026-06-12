#!/usr/bin/env python3
"""Prepare a frozen Strategy 1 training matrix for Cloud Run task fan-out."""

from __future__ import annotations

import argparse
import gc
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from google.cloud import bigquery

from .runner_version import __version__
from .bq_io import (
    env_container_image,
    get_git_commit,
    job_audit_dict,
    join_gs_uri,
    make_client,
    query_dataframe_with_job,
    upload_directory_to_gcs,
    write_json,
)
from .config import (
    Experiment,
    add_common_args,
    apply_cli_overrides,
    effective_candidate_parallelism,
    load_runner_config,
)
from .dataset_roles import TableResolver
from .feature_sets import (
    PV_FIN_RISK_FEATURE_SET_ID,
    boolean_feature_names,
    expected_feature_columns,
    feature_delta_vs_base,
    feature_metadata,
    market_state_feature_names,
    risk_feature_names,
)
from .preprocess import build_preprocessor, feature_frame_from_panel
from .task_fanout import (
    MATRIX_MANIFEST_VERSION,
    build_work_units,
    candidate_grid_hash,
    default_matrix_id,
    file_sha256,
    matrix_artifact_uri,
    matrix_local_dir,
    sha256_json,
    stamp_work_units,
    write_manifest,
    write_parquet,
)
from quant_ashare.strategy1.experiment_resolution import resolve_experiment_from_args


def main() -> int:
    args = parse_args()
    config = apply_cli_overrides(load_runner_config(args.config), args)
    experiment = resolve_experiment(args)
    matrix_id = args.matrix_id or default_matrix_id(config, experiment)
    matrix_uri = args.matrix_uri or matrix_artifact_uri(config, experiment, matrix_id)
    local_dir = Path(args.matrix_local_dir) if args.matrix_local_dir else matrix_local_dir(config, experiment, matrix_id)
    candidate_parallelism_arg = effective_candidate_parallelism(config, args.candidate_parallelism)
    candidate_parallelism_resolved = resolve_candidate_parallelism(len(config.candidate_grid), candidate_parallelism_arg)
    plan = {
        "entrypoint": "prepare_matrix",
        "runner_version": __version__,
        "project": config.project,
        "region": config.region,
        "output_dataset_role": config.output_dataset_role,
        "experiment": experiment.to_params(),
        "matrix_id": matrix_id,
        "matrix_uri": matrix_uri,
        "matrix_local_dir": str(local_dir),
        "work_unit_count": len(config.candidate_grid),
        "candidate_parallelism_arg": candidate_parallelism_arg,
        "candidate_parallelism_resolved": candidate_parallelism_resolved,
        "candidate_task_cpu": config.candidate_task_cpu,
        "candidate_task_memory": config.candidate_task_memory,
        "candidate_grid_hash": candidate_grid_hash(config),
        "skip_gcs_upload": args.skip_gcs_upload,
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2, default=str))
        return 0
    result = prepare_matrix(
        config=config,
        experiment=experiment,
        matrix_id=matrix_id,
        matrix_uri=matrix_uri,
        local_dir=local_dir,
        skip_gcs_upload=args.skip_gcs_upload,
        candidate_parallelism_requested=candidate_parallelism_arg,
        candidate_parallelism_resolved=candidate_parallelism_resolved,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Strategy 1 frozen matrix for Cloud Run task fan-out")
    add_common_args(parser)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--experiment-json", default=None, help="Base64 encoded resolved experiment payload")
    parser.add_argument("--matrix-id", default=None)
    parser.add_argument("--matrix-uri", default=None)
    parser.add_argument("--matrix-local-dir", default=None)
    parser.add_argument("--candidate-parallelism", type=int, default=0)
    parser.add_argument("--skip-gcs-upload", action="store_true")
    return parser.parse_args()


def resolve_experiment(args: argparse.Namespace) -> Experiment:
    return resolve_experiment_from_args(
        args,
        step_name="prepare_matrix",
        require_retrain=True,
    )


def prepare_matrix(
    *,
    config,
    experiment: Experiment,
    matrix_id: str,
    matrix_uri: str,
    local_dir: Path,
    skip_gcs_upload: bool,
    candidate_parallelism_requested: int,
    candidate_parallelism_resolved: int,
) -> dict[str, Any]:
    client = make_client(config.project, config.region)
    labels = {
        "pipeline_component": "strategy1_cloudrun",
        "pipeline_step": "prepare_matrix",
        "run_id": experiment.run_id,
        "matrix_id": matrix_id,
    }
    expected_columns = expected_feature_columns(experiment.feature_set_id)
    panel, job = load_training_panel_with_job(client, config, experiment, labels, expected_columns)
    if panel.empty:
        source_table = TableResolver(
            dataset_role=config.output_dataset_role,
            project=config.project,
        ).fqn("training_panel")
        raise RuntimeError(f"{source_table} has no rows for run_id={experiment.run_id}")

    if expected_columns is None:
        feature_frame, feature_columns = feature_frame_from_panel(panel)
        panel = panel.drop(columns=["feature_values_json", "feature_column_list"], errors="ignore")
    else:
        validate_expected_feature_columns(panel, expected_columns, experiment.run_id)
        feature_columns = expected_columns
        feature_frame = panel.loc[:, feature_columns].astype("float32", copy=False)
        panel = panel.drop(columns=feature_columns + ["feature_column_list"], errors="ignore")
    panel = panel.reset_index(drop=True)
    feature_frame = feature_frame.reset_index(drop=True)
    if expected_columns is not None and feature_columns != expected_columns:
        raise RuntimeError(
            "feature_column_list does not match feature_set contract for "
            f"{experiment.feature_set_id}: expected {len(expected_columns)} columns, got {len(feature_columns)}"
        )
    feature_meta = feature_metadata(experiment.feature_set_id, feature_columns)
    feature_delta = feature_delta_vs_base(experiment.feature_set_id, feature_columns)
    feature_schema = {
        "feature_columns": feature_columns,
        "feature_count": len(feature_columns),
        "feature_set_id": experiment.feature_set_id,
        "feature_version": experiment.feature_version,
        "base_feature_set_id": feature_delta.get("base_feature_set_id"),
        "feature_metadata": feature_meta,
        "feature_groups": sorted({item["feature_group"] for item in feature_meta}),
        "risk_features": [name for name in risk_feature_names() if name in feature_columns],
        "market_state_features": [name for name in market_state_feature_names() if name in feature_columns],
        "market_state_features_enabled": experiment.feature_set_id == PV_FIN_RISK_FEATURE_SET_ID,
        "feature_order_sha256": sha256_json(feature_columns),
    }
    train_mask = panel["split_tag"].eq("train") & panel["target_label"].notna()
    valid_mask = panel["split_tag"].eq("valid")
    cv_mask = panel["split_tag"].isin(["train", "valid"])
    predict_mask = panel["split_tag"].isin(["valid", "test", "final_holdout"])
    if int(train_mask.sum()) == 0:
        raise RuntimeError("train split has no labeled samples")
    if int(valid_mask.sum()) == 0:
        raise RuntimeError("valid split has no prediction samples")
    if int(predict_mask.sum()) == 0:
        raise RuntimeError("valid/test predict split has no samples")

    preprocessor = build_preprocessor(
        config.preprocess_version,
        feature_columns,
        winsor_lower=config.winsor_lower,
        winsor_upper=config.winsor_upper,
    ).fit(feature_frame.loc[train_mask])
    preprocess_stats = preprocessor.to_json_dict()
    preprocess_stats["feature_missing_rates"] = split_missing_rates(feature_frame, panel, feature_columns)
    preprocess_stats["risk_feature_missing_rates"] = {
        name: preprocess_stats["feature_missing_rates"][name]
        for name in feature_schema["risk_features"]
        if name in preprocess_stats["feature_missing_rates"]
    }
    preprocess_stats["market_state_missing_rates"] = {
        name: preprocess_stats["feature_missing_rates"][name]
        for name in feature_schema["market_state_features"]
        if name in preprocess_stats["feature_missing_rates"]
    }
    preprocess_stats["preprocess_stats_sha256"] = sha256_json(preprocess_stats)

    local_dir.mkdir(parents=True, exist_ok=True)
    write_transformed_features(
        preprocessor,
        feature_frame,
        train_mask,
        feature_columns,
        local_dir / "train_features.parquet",
    )
    write_parquet(label_frame(panel.loc[train_mask]), local_dir / "train_labels.parquet")
    write_transformed_features(
        preprocessor,
        feature_frame,
        valid_mask,
        feature_columns,
        local_dir / "valid_features.parquet",
    )
    write_parquet(label_frame(panel.loc[valid_mask]), local_dir / "valid_labels.parquet")
    write_transformed_features(
        preprocessor,
        feature_frame,
        cv_mask,
        feature_columns,
        local_dir / "cv_features.parquet",
    )
    write_parquet(label_frame(panel.loc[cv_mask]), local_dir / "cv_labels.parquet")
    write_transformed_features(
        preprocessor,
        feature_frame,
        predict_mask,
        feature_columns,
        local_dir / "predict_features.parquet",
    )
    write_parquet(predict_index_frame(panel.loc[predict_mask]), local_dir / "predict_index.parquet")
    write_json(local_dir / "feature_schema.json", feature_schema)
    write_json(local_dir / "feature_delta_vs_base.json", feature_delta)
    write_json(local_dir / "preprocess_stats.json", preprocess_stats)
    joblib.dump(preprocessor, local_dir / "preprocess.joblib")

    work_units = stamp_work_units(build_work_units(config, experiment, matrix_uri), matrix_id, matrix_uri)
    work_units["candidate_parallelism_resolved"] = candidate_parallelism_resolved
    work_units["candidate_parallelism_requested"] = candidate_parallelism_requested
    work_units["candidate_task_cpu"] = config.candidate_task_cpu
    work_units["candidate_task_memory"] = config.candidate_task_memory
    work_units["work_units_sha256"] = sha256_json({k: v for k, v in work_units.items() if k != "work_units_sha256"})
    write_json(local_dir / "work_units.json", work_units)
    bq_audit = {
        "jobs": [job_audit_dict(job)],
        "audit_rule": (
            "prepare_matrix is the only full-panel reader; candidate task BigQuery usage is "
            "audited by select_register_predict via INFORMATION_SCHEMA.JOBS_BY_PROJECT"
        ),
    }
    write_json(local_dir / "bq_audit.json", bq_audit)

    manifest = {
        "manifest_version": MATRIX_MANIFEST_VERSION,
        "run_id": experiment.run_id,
        "prediction_run_id": experiment.prediction_run_id,
        "experiment_id": experiment.experiment_id,
        "matrix_id": matrix_id,
        "matrix_uri": matrix_uri,
        "source_table": TableResolver(
            dataset_role=config.output_dataset_role,
            project=config.project,
        ).fqn("training_panel"),
        "source_run_id": experiment.run_id,
        "source_row_count": int(len(panel)),
        "train_row_count": int(train_mask.sum()),
        "valid_row_count": int(valid_mask.sum()),
        "cv_row_count": int(cv_mask.sum()),
        "predict_row_count": int(predict_mask.sum()),
        "final_holdout_start_date": experiment.final_holdout_start,
        "final_holdout_end_date": experiment.final_holdout_end,
        "data_end_date": experiment.final_holdout_end or experiment.predict_end,
        "feature_order_sha256": feature_schema["feature_order_sha256"],
        "feature_schema_sha256": file_sha256(local_dir / "feature_schema.json"),
        "feature_delta_vs_base_sha256": file_sha256(local_dir / "feature_delta_vs_base.json"),
        "preprocess_stats_sha256": preprocess_stats["preprocess_stats_sha256"],
        "work_units_sha256": work_units["work_units_sha256"],
        "candidate_parallelism_requested": candidate_parallelism_requested,
        "candidate_parallelism_resolved": candidate_parallelism_resolved,
        "candidate_task_cpu": config.candidate_task_cpu,
        "candidate_task_memory": config.candidate_task_memory,
        "candidate_grid_hash": candidate_grid_hash(config),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by_job": "prepare_matrix",
        "container_image": env_container_image(),
        "git_commit": get_git_commit(),
        "runner_version": __version__,
        "files_sha256": {
            "train_features.parquet": file_sha256(local_dir / "train_features.parquet"),
            "train_labels.parquet": file_sha256(local_dir / "train_labels.parquet"),
            "valid_features.parquet": file_sha256(local_dir / "valid_features.parquet"),
            "valid_labels.parquet": file_sha256(local_dir / "valid_labels.parquet"),
            "cv_features.parquet": file_sha256(local_dir / "cv_features.parquet"),
            "cv_labels.parquet": file_sha256(local_dir / "cv_labels.parquet"),
            "predict_features.parquet": file_sha256(local_dir / "predict_features.parquet"),
            "predict_index.parquet": file_sha256(local_dir / "predict_index.parquet"),
            "feature_schema.json": file_sha256(local_dir / "feature_schema.json"),
            "feature_delta_vs_base.json": file_sha256(local_dir / "feature_delta_vs_base.json"),
            "preprocess_stats.json": file_sha256(local_dir / "preprocess_stats.json"),
            "work_units.json": file_sha256(local_dir / "work_units.json"),
            "bq_audit.json": file_sha256(local_dir / "bq_audit.json"),
        },
    }
    write_manifest(local_dir / "matrix_manifest.json", manifest)

    uploaded = [] if skip_gcs_upload else upload_directory_to_gcs(config.project, local_dir, matrix_uri)
    return {
        "status": "succeeded",
        "run_id": experiment.run_id,
        "matrix_id": matrix_id,
        "matrix_uri": matrix_uri,
        "matrix_local_dir": str(local_dir),
        "source_row_count": manifest["source_row_count"],
        "train_row_count": manifest["train_row_count"],
        "valid_row_count": manifest["valid_row_count"],
        "predict_row_count": manifest["predict_row_count"],
        "work_unit_count": work_units["work_unit_count"],
        "feature_count": feature_schema["feature_count"],
        "feature_delta_vs_base_sha256": manifest["feature_delta_vs_base_sha256"],
        "candidate_parallelism_resolved": candidate_parallelism_resolved,
        "uploaded_artifacts": uploaded,
    }


def resolve_candidate_parallelism(work_unit_count: int, candidate_parallelism: int | None) -> int:
    if work_unit_count < 0:
        raise ValueError("work_unit_count must be non-negative")
    if candidate_parallelism is None or candidate_parallelism == 0:
        return work_unit_count
    if candidate_parallelism < 0:
        raise ValueError("--candidate-parallelism must be >= 0")
    return min(candidate_parallelism, work_unit_count)


def load_training_panel_with_job(
    client: bigquery.Client,
    config,
    experiment: Experiment,
    labels: dict[str, str],
    feature_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, bigquery.QueryJob]:
    training_panel = TableResolver(
        dataset_role=config.output_dataset_role,
        project=config.project,
    ).fqn("training_panel")
    if feature_columns is None:
        feature_select = """
      feature_values_json,
      feature_column_list,"""
    else:
        bool_feature_names = boolean_feature_names()
        feature_select = """
      feature_column_list,""" + "".join(
            f"""
      {feature_json_sql(column, column in bool_feature_names)} AS `{column}`,"""
            for column in feature_columns
        )
    sql = f"""
    SELECT
      run_id, strategy_id, trade_date, sec_code, horizon, split_tag,
      sample_weight, target_label, target_return,{feature_select}
      feature_version, label_version, preprocess_version
    FROM `{training_panel}`
    WHERE run_id = @run_id
      AND trade_date BETWEEN @train_start AND @test_end
    ORDER BY trade_date, sec_code
    """
    return query_dataframe_with_job(
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
        labels=labels,
    )


def normalize_feature_column_list(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = [part.strip() for part in value.split(",") if part.strip()]
    else:
        parsed = list(value)
    return [str(item) for item in parsed]


def feature_json_sql(column: str, is_bool_feature: bool) -> str:
    if is_bool_feature:
        return f"CAST(SAFE_CAST(JSON_VALUE(feature_values_json, '$.{column}') AS BOOL) AS INT64)"
    return f"SAFE_CAST(JSON_VALUE(feature_values_json, '$.{column}') AS FLOAT64)"


def validate_expected_feature_columns(
    panel: pd.DataFrame,
    expected_columns: list[str],
    run_id: str,
) -> None:
    if "feature_column_list" not in panel.columns:
        raise RuntimeError(f"training panel missing feature_column_list for run_id={run_id}")

    observed_values = panel["feature_column_list"].dropna()
    observed = normalize_feature_column_list(observed_values.iloc[0]) if not observed_values.empty else None

    expected_tuple = tuple(expected_columns)
    if tuple(observed or []) != expected_tuple:
        raise RuntimeError(
            "feature_column_list does not match feature_set contract for "
            f"run_id={run_id}; observed_count={len(observed or [])} "
            f"expected_count={len(expected_columns)}"
        )

    train = panel.loc[panel["split_tag"] == "train", expected_columns]
    all_null_columns = [column for column in expected_columns if train[column].notna().sum() == 0]
    if all_null_columns:
        raise RuntimeError(
            "training panel has all-null expected feature columns in train split "
            f"for run_id={run_id}: {all_null_columns[:20]}"
        )


def write_transformed_features(
    preprocessor,
    feature_frame: pd.DataFrame,
    mask: pd.Series,
    feature_columns: list[str],
    path: Path,
) -> None:
    features = pd.DataFrame(
        preprocessor.transform(feature_frame.loc[mask]),
        columns=feature_columns,
    )
    write_parquet(features, path)
    del features
    gc.collect()


def label_frame(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel[[
        "trade_date", "sec_code", "horizon", "split_tag", "sample_weight",
        "target_label", "target_return", "feature_version", "label_version", "preprocess_version",
    ]].copy()
    out["trade_date"] = pd.to_datetime(out["trade_date"]).dt.date
    return out


def split_missing_rates(
    feature_frame: pd.DataFrame,
    panel: pd.DataFrame,
    feature_columns: list[str],
) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    split_values = [str(value) for value in panel["split_tag"].dropna().unique()]
    for col in feature_columns:
        rates: dict[str, float] = {}
        series = feature_frame[col] if col in feature_frame.columns else pd.Series(index=feature_frame.index, dtype="float64")
        rates["all"] = missing_rate(series)
        for split in sorted(split_values):
            mask = panel["split_tag"].eq(split)
            rates[split] = missing_rate(series.loc[mask])
        stats[col] = rates
    return stats


def missing_rate(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    return float(series.isna().sum()) / float(len(series))


def predict_index_frame(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel[[
        "trade_date", "sec_code", "horizon", "split_tag", "feature_version", "label_version",
    ]].copy()
    out["trade_date"] = pd.to_datetime(out["trade_date"]).dt.date
    return out


if __name__ == "__main__":
    raise SystemExit(main())
