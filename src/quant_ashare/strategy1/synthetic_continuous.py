#!/usr/bin/env python3
"""Build a synthetic continuous prediction run from annual prediction slices."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from google.cloud import bigquery

from scripts.strategy1_cloudrun.bq_io import (
    execute_query,
    get_git_commit,
    join_gs_uri,
    json_dumps_strict,
    load_dataframe,
    make_client,
    query_dataframe,
    upload_directory_to_gcs,
    write_json,
)
from scripts.strategy1_cloudrun.config import add_common_args, apply_cli_overrides, load_runner_config
from scripts.strategy1_cloudrun.dataset_roles import TableResolver, validate_output_dataset_role


@dataclass(frozen=True)
class YearSlice:
    backtest_year: int
    source_run_id: str
    predict_start: date
    predict_end: date
    valid_start: date | None = None
    valid_end: date | None = None


def main() -> int:
    args = parse_args()
    config = apply_cli_overrides(load_runner_config(args.config), args)
    if validate_output_dataset_role(config.output_dataset_role) != "research":
        raise ValueError("synthetic continuous merge is research-only; promotion is a separate owner-approved flow")
    manifest = load_synthetic_manifest(Path(args.manifest_json))
    synthetic_model_id = args.synthetic_model_id or default_synthetic_model_id(manifest["synthetic_run_id"])
    plan = {
        "entrypoint": "synthetic_continuous",
        "project": config.project,
        "region": config.region,
        "output_dataset_role": config.output_dataset_role,
        "manifest_json": args.manifest_json,
        "synthetic_run_id": manifest["synthetic_run_id"],
        "synthetic_model_id": synthetic_model_id,
        "year_count": len(manifest["years"]),
        "predict_start": manifest["years"][0].predict_start.isoformat(),
        "predict_end": manifest["years"][-1].predict_end.isoformat(),
        "force_replace": args.force_replace,
        "require_source_refit": args.require_source_refit,
        "skip_gcs_upload": args.skip_gcs_upload,
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    result = run_synthetic_merge(
        config=config,
        manifest=manifest,
        synthetic_model_id=synthetic_model_id,
        force_replace=args.force_replace,
        require_source_refit=args.require_source_refit,
        skip_gcs_upload=args.skip_gcs_upload,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Strategy1 synthetic continuous prediction run")
    add_common_args(parser)
    parser.add_argument("--manifest-json", required=True, help="Synthetic continuous manifest JSON path")
    parser.add_argument("--synthetic-model-id", default=None)
    parser.add_argument("--force-replace", action="store_true")
    parser.add_argument(
        "--require-source-refit",
        action="store_true",
        help="Require every source registry row to carry model_params_json.refit=true",
    )
    parser.add_argument("--skip-gcs-upload", action="store_true")
    return parser.parse_args()


def load_synthetic_manifest(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    synthetic_run_id = str(raw.get("synthetic_run_id") or "").strip()
    if not synthetic_run_id:
        raise ValueError("manifest requires synthetic_run_id")
    years_raw = raw.get("years")
    if not isinstance(years_raw, list) or not years_raw:
        raise ValueError("manifest requires non-empty years list")
    years = [
        YearSlice(
            backtest_year=int(item["backtest_year"]),
            source_run_id=str(item["source_run_id"]),
            predict_start=date.fromisoformat(str(item["predict_start"])),
            predict_end=date.fromisoformat(str(item["predict_end"])),
            valid_start=_optional_manifest_date(item, "valid_start"),
            valid_end=_optional_manifest_date(item, "valid_end"),
        )
        for item in years_raw
    ]
    years = sorted(years, key=lambda item: item.backtest_year)
    seen_years = [item.backtest_year for item in years]
    if len(seen_years) != len(set(seen_years)):
        raise ValueError(f"duplicate backtest_year in manifest: {seen_years}")
    for previous, current in zip(years, years[1:]):
        if current.backtest_year != previous.backtest_year + 1:
            raise ValueError("manifest years must be consecutive")
        if current.predict_start <= previous.predict_end:
            raise ValueError("manifest predict windows must be strictly increasing and non-overlapping")
    for item in years:
        if item.predict_start > item.predict_end:
            raise ValueError(f"invalid predict window for {item.backtest_year}")
        if bool(item.valid_start) != bool(item.valid_end):
            raise ValueError(f"valid_start and valid_end must be provided together for {item.backtest_year}")
        if item.valid_start and item.valid_start > item.valid_end:
            raise ValueError(f"invalid valid window for {item.backtest_year}")
        if not item.source_run_id:
            raise ValueError(f"missing source_run_id for {item.backtest_year}")
    return {
        "synthetic_run_id": synthetic_run_id,
        "years": years,
        "raw": raw,
    }


def default_synthetic_model_id(synthetic_run_id: str) -> str:
    return f"synth_{synthetic_run_id}"[:300]


def run_synthetic_merge(
    *,
    config,
    manifest: dict[str, Any],
    synthetic_model_id: str,
    force_replace: bool,
    require_source_refit: bool,
    skip_gcs_upload: bool,
) -> dict[str, Any]:
    client = make_client(config.project, config.region)
    resolver = TableResolver(dataset_role=config.output_dataset_role, project=config.project)
    registry_table = resolver.fqn("model_registry")
    prediction_table = resolver.fqn("model_prediction_daily")
    synthetic_run_id = manifest["synthetic_run_id"]
    years: list[YearSlice] = manifest["years"]
    input_manifest_sha256 = canonical_manifest_sha256(manifest)
    source_rows = load_source_registry_rows(
        client,
        config,
        registry_table=registry_table,
        years=years,
        require_source_refit=require_source_refit,
    )
    year_slices = build_year_slices(years, source_rows)
    artifact_uri = join_gs_uri(
        config.model_artifact_base_uri,
        "ml_pv_clf_v0",
        f"run_id={synthetic_run_id}",
        f"model_id={synthetic_model_id}",
        "synthetic_continuous",
    )
    resolved_manifest = {
        "synthetic_run_id": synthetic_run_id,
        "synthetic_model_id": synthetic_model_id,
        "input_manifest_sha256": input_manifest_sha256,
        "require_source_refit": require_source_refit,
        "year_slices": year_slices,
    }
    resolved_manifest_sha256 = hashlib.sha256(
        json_dumps_strict(resolved_manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    resolved_manifest["resolved_manifest_sha256"] = resolved_manifest_sha256
    local_dir = (
        Path(config.local_mirror_root)
        / "synthetic_continuous"
        / f"run_id={synthetic_run_id}"
        / f"model_id={synthetic_model_id}"
    )
    write_json(local_dir / "manifest.json", resolved_manifest)
    uploaded = [] if skip_gcs_upload else upload_directory_to_gcs(config.project, local_dir, artifact_uri)
    manifest_uri = join_gs_uri(artifact_uri, "manifest.json") if not skip_gcs_upload else None

    existing = count_existing_target_rows(
        client,
        registry_table=registry_table,
        prediction_table=prediction_table,
        synthetic_run_id=synthetic_run_id,
        predict_start=years[0].predict_start,
        predict_end=years[-1].predict_end,
    )
    if not force_replace and (existing["registry_rows"] or existing["prediction_rows"]):
        raise RuntimeError(
            f"synthetic target exists for {synthetic_run_id}: "
            f"registry={existing['registry_rows']} prediction={existing['prediction_rows']}; set --force-replace"
        )
    if force_replace:
        clear_synthetic_outputs(
            client,
            registry_table=registry_table,
            prediction_table=prediction_table,
            synthetic_run_id=synthetic_run_id,
            predict_start=years[0].predict_start,
            predict_end=years[-1].predict_end,
        )

    write_synthetic_registry(
        client,
        config,
        registry_table=registry_table,
        synthetic_run_id=synthetic_run_id,
        synthetic_model_id=synthetic_model_id,
        artifact_uri=artifact_uri,
        manifest_uri=manifest_uri,
        input_manifest_sha256=input_manifest_sha256,
        resolved_manifest_sha256=resolved_manifest_sha256,
        year_slices=year_slices,
        require_source_refit=require_source_refit,
        predict_start=years[0].predict_start,
        predict_end=years[-1].predict_end,
    )
    insert_job = insert_synthetic_predictions(
        client,
        prediction_table=prediction_table,
        synthetic_run_id=synthetic_run_id,
        synthetic_model_id=synthetic_model_id,
        years=years,
        source_rows=source_rows,
    )
    counts = count_existing_target_rows(
        client,
        registry_table=registry_table,
        prediction_table=prediction_table,
        synthetic_run_id=synthetic_run_id,
        predict_start=years[0].predict_start,
        predict_end=years[-1].predict_end,
    )
    return {
        "status": "succeeded",
        "synthetic_run_id": synthetic_run_id,
        "synthetic_model_id": synthetic_model_id,
        "year_count": len(years),
        "predict_start": years[0].predict_start.isoformat(),
        "predict_end": years[-1].predict_end.isoformat(),
        "input_manifest_sha256": input_manifest_sha256,
        "resolved_manifest_sha256": resolved_manifest_sha256,
        "manifest_uri": manifest_uri,
        "uploaded_artifacts": uploaded,
        "registry_rows": counts["registry_rows"],
        "prediction_rows": counts["prediction_rows"],
        "insert_job_id": insert_job.job_id,
    }


def canonical_manifest_sha256(manifest: dict[str, Any]) -> str:
    def year_payload(item: YearSlice) -> dict[str, Any]:
        payload = {
            "backtest_year": item.backtest_year,
            "source_run_id": item.source_run_id,
            "predict_start": item.predict_start.isoformat(),
            "predict_end": item.predict_end.isoformat(),
        }
        if item.valid_start and item.valid_end:
            payload["valid_start"] = item.valid_start.isoformat()
            payload["valid_end"] = item.valid_end.isoformat()
        return payload

    payload = {
        "synthetic_run_id": manifest["synthetic_run_id"],
        "years": [year_payload(item) for item in manifest["years"]],
    }
    return hashlib.sha256(json_dumps_strict(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _optional_manifest_date(item: dict[str, Any], key: str) -> date | None:
    value = item.get(key)
    if value in (None, ""):
        return None
    return date.fromisoformat(str(value))


def load_source_registry_rows(
    client: bigquery.Client,
    config,
    *,
    registry_table: str,
    years: list[YearSlice],
    require_source_refit: bool,
) -> dict[str, dict[str, Any]]:
    source_run_ids = [item.source_run_id for item in years]
    frame = query_dataframe(
        client,
        f"""
        SELECT
          JSON_VALUE(model_params_json, '$.run_id') AS source_run_id,
          model_id,
          model_family,
          horizon,
          feature_version,
          label_version,
          preprocess_version,
          train_start_date,
          train_end_date,
          valid_start_date,
          valid_end_date,
          test_start_date,
          test_end_date,
          model_params_json,
          metrics_json,
          model_uri,
          artifact_uri,
          created_at
        FROM `{registry_table}`
        WHERE strategy_id = @strategy_id
          AND status = 'selected'
          AND JSON_VALUE(model_params_json, '$.run_id') IN UNNEST(@source_run_ids)
        ORDER BY source_run_id, created_at DESC
        """,
        [
            bigquery.ScalarQueryParameter("strategy_id", "STRING", config.strategy_id),
            bigquery.ArrayQueryParameter("source_run_ids", "STRING", source_run_ids),
        ],
    )
    rows: dict[str, dict[str, Any]] = {}
    duplicates: dict[str, int] = {}
    for _, row in frame.iterrows():
        source_run_id = str(row["source_run_id"])
        duplicates[source_run_id] = duplicates.get(source_run_id, 0) + 1
        if source_run_id not in rows:
            params = json.loads(row["model_params_json"] or "{}")
            metrics = json.loads(row["metrics_json"] or "{}")
            if require_source_refit and params.get("refit") is not True:
                raise RuntimeError(f"source run {source_run_id} is not a refit registry row")
            rows[source_run_id] = {
                "source_run_id": source_run_id,
                "source_selection_run_id": params.get("source_run_id") if params.get("refit") is True else source_run_id,
                "source_model_id": row["model_id"],
                "model_family": row["model_family"],
                "horizon": int(row["horizon"]),
                "feature_version": row["feature_version"],
                "label_version": row["label_version"],
                "preprocess_version": row["preprocess_version"],
                "train_start_date": _date_str(row["train_start_date"]),
                "train_end_date": _date_str(row["train_end_date"]),
                "valid_start_date": _date_str(row["valid_start_date"]),
                "valid_end_date": _date_str(row["valid_end_date"]),
                "test_start_date": _date_str(row["test_start_date"]),
                "test_end_date": _date_str(row["test_end_date"]),
                "model_params": params,
                "metrics": metrics,
                "model_uri": row["model_uri"],
                "artifact_uri": row.get("artifact_uri"),
                "source_refit": params.get("refit") is True,
                "selected_candidate_id": (
                    params.get("candidate_id")
                    or metrics.get("selected_candidate_id")
                    or metrics.get("candidate_id")
                ),
            }
    missing = sorted(set(source_run_ids) - set(rows))
    multi = {run_id: count for run_id, count in duplicates.items() if count != 1}
    if missing or multi:
        raise RuntimeError(f"invalid selected source registry rows: missing={missing}, duplicate_counts={multi}")
    missing_selection_lineage = sorted(
        str(row["source_run_id"])
        for row in rows.values()
        if row.get("source_refit") and not row.get("source_selection_run_id")
    )
    if missing_selection_lineage:
        raise RuntimeError(
            "refit source registry rows must include model_params_json.source_run_id: "
            f"{missing_selection_lineage}"
        )
    selection_run_ids = sorted({
        str(row["source_selection_run_id"])
        for row in rows.values()
        if row.get("source_refit") and row.get("source_selection_run_id")
    })
    if selection_run_ids:
        selection_windows = load_selection_valid_windows(
            client,
            config,
            registry_table=registry_table,
            selection_run_ids=selection_run_ids,
        )
        for row in rows.values():
            selection_run_id = row.get("source_selection_run_id")
            if row.get("source_refit") and selection_run_id:
                window = selection_windows.get(str(selection_run_id))
                if not window:
                    raise RuntimeError(
                        f"missing selected source valid window for refit source_run_id={row['source_run_id']} "
                        f"source_selection_run_id={selection_run_id}"
                    )
                row["valid_start_date"] = window["valid_start_date"]
                row["valid_end_date"] = window["valid_end_date"]
    return rows


def load_selection_valid_windows(
    client: bigquery.Client,
    config,
    *,
    registry_table: str,
    selection_run_ids: list[str],
) -> dict[str, dict[str, str | None]]:
    frame = query_dataframe(
        client,
        f"""
        SELECT
          JSON_VALUE(model_params_json, '$.run_id') AS source_selection_run_id,
          valid_start_date,
          valid_end_date,
          created_at
        FROM `{registry_table}`
        WHERE strategy_id = @strategy_id
          AND status = 'selected'
          AND JSON_VALUE(model_params_json, '$.run_id') IN UNNEST(@selection_run_ids)
        ORDER BY source_selection_run_id, created_at DESC
        """,
        [
            bigquery.ScalarQueryParameter("strategy_id", "STRING", config.strategy_id),
            bigquery.ArrayQueryParameter("selection_run_ids", "STRING", selection_run_ids),
        ],
    )
    rows: dict[str, dict[str, str | None]] = {}
    duplicates: dict[str, int] = {}
    for _, row in frame.iterrows():
        run_id = str(row["source_selection_run_id"])
        duplicates[run_id] = duplicates.get(run_id, 0) + 1
        if run_id not in rows:
            rows[run_id] = {
                "valid_start_date": _date_str(row["valid_start_date"]),
                "valid_end_date": _date_str(row["valid_end_date"]),
            }
    missing = sorted(set(selection_run_ids) - set(rows))
    multi = {run_id: count for run_id, count in duplicates.items() if count != 1}
    invalid = sorted(
        run_id for run_id, window in rows.items()
        if not window["valid_start_date"] or not window["valid_end_date"]
    )
    if missing or multi or invalid:
        raise RuntimeError(
            "invalid selected source valid windows: "
            f"missing={missing}, duplicate_counts={multi}, invalid={invalid}"
        )
    return rows


def build_year_slices(years: list[YearSlice], source_rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in years:
        source = source_rows[item.source_run_id]
        rows.append({
            "backtest_year": item.backtest_year,
            "source_run_id": item.source_run_id,
            "source_model_id": source["source_model_id"],
            "source_refit": source["source_refit"],
            "selected_candidate_id": source["selected_candidate_id"],
            "predict_start": item.predict_start.isoformat(),
            "predict_end": item.predict_end.isoformat(),
            "valid_start": item.valid_start.isoformat() if item.valid_start else source["valid_start_date"],
            "valid_end": item.valid_end.isoformat() if item.valid_end else source["valid_end_date"],
        })
    return rows


def write_synthetic_registry(
    client: bigquery.Client,
    config,
    *,
    registry_table: str,
    synthetic_run_id: str,
    synthetic_model_id: str,
    artifact_uri: str,
    manifest_uri: str | None,
    input_manifest_sha256: str,
    resolved_manifest_sha256: str,
    year_slices: list[dict[str, Any]],
    require_source_refit: bool,
    predict_start: date,
    predict_end: date,
) -> None:
    now = datetime.now(timezone.utc)
    source_run_ids = [row["source_run_id"] for row in year_slices]
    year_model_map = {
        str(row["backtest_year"]): {
            "source_run_id": row["source_run_id"],
            "source_model_id": row["source_model_id"],
            "source_refit": row["source_refit"],
            "selected_candidate_id": row["selected_candidate_id"],
            "predict_start": row["predict_start"],
            "predict_end": row["predict_end"],
        }
        for row in year_slices
    }
    params_json = {
        "run_id": synthetic_run_id,
        "prediction_run_id": synthetic_run_id,
        "synthetic_continuous": True,
        "synthetic_model_id": synthetic_model_id,
        "source_run_ids": source_run_ids,
        "source_all_refit": all(bool(row["source_refit"]) for row in year_slices),
        "require_source_refit": require_source_refit,
        "input_manifest_sha256": input_manifest_sha256,
        "resolved_manifest_sha256": resolved_manifest_sha256,
        "manifest_uri": manifest_uri,
        "year_model_map": year_model_map,
        "predict_start_date": predict_start.isoformat(),
        "predict_end_date": predict_end.isoformat(),
        "label_horizon": 5,
        "feature_set_id": "strategy1_pv_fin_risk_v0_20260606",
        "tail_risk_profile_id": "diagnostic_only",
    }
    metrics_json = {
        "synthetic_continuous": True,
        "diagnostic_only": False,
        "manifest_uri": manifest_uri,
        "input_manifest_sha256": input_manifest_sha256,
        "resolved_manifest_sha256": resolved_manifest_sha256,
        "source_run_ids": source_run_ids,
        "year_slices": year_slices,
        "year_model_map": year_model_map,
        "source_all_refit": all(bool(row["source_refit"]) for row in year_slices),
        "require_source_refit": require_source_refit,
        "selected_candidate_id": "synthetic_continuous",
        "model_family": "synthetic_continuous",
        "model_artifact_uri": artifact_uri,
        "preprocess_artifact_uri": None,
    }
    import pandas as pd

    frame = pd.DataFrame([{
        "model_id": synthetic_model_id,
        "strategy_id": config.strategy_id,
        "run_id": synthetic_run_id,
        "search_id": "annual_rolling_synthetic_continuous",
        "experiment_id": synthetic_run_id,
        "experiment_group": "strategy1_annual_rolling_continuous",
        "model_family": "synthetic_continuous",
        "horizon": 5,
        "feature_version": "strategy1_pv_v0_20260601",
        "label_version": "open_to_close_h1_5_10_20_v20260601",
        "preprocess_version": "synthetic_continuous_v1",
        "train_start_date": None,
        "train_end_date": None,
        "valid_start_date": None,
        "valid_end_date": None,
        "test_start_date": predict_start,
        "test_end_date": predict_end,
        "final_holdout_start_date": None,
        "final_holdout_end_date": None,
        "model_params_json": json_dumps_strict(params_json, ensure_ascii=False),
        "metrics_json": json_dumps_strict(metrics_json, ensure_ascii=False),
        "model_uri": manifest_uri,
        "artifact_uri": artifact_uri,
        "git_commit": get_git_commit(),
        "status": "selected",
        "acceptance_status": "not_evaluated",
        "promotion_status": "not_promoted",
        "promotion_id": None,
        "approval_ref": None,
        "created_date": now.date(),
        "created_at": now,
    }])
    load_dataframe(client, frame, registry_table)


def insert_synthetic_predictions(
    client: bigquery.Client,
    *,
    prediction_table: str,
    synthetic_run_id: str,
    synthetic_model_id: str,
    years: list[YearSlice],
    source_rows: dict[str, dict[str, Any]],
) -> bigquery.QueryJob:
    predict_start = min(item.predict_start for item in years)
    predict_end = max(item.predict_end for item in years)
    manifest_sql = ",\n".join(
        "STRUCT("
        f"{item.backtest_year} AS backtest_year, "
        f"{_sql_string(item.source_run_id)} AS source_run_id, "
        f"{_sql_string(str(source_rows[item.source_run_id]['source_model_id']))} AS source_model_id, "
        f"DATE '{item.predict_start.isoformat()}' AS predict_start, "
        f"DATE '{item.predict_end.isoformat()}' AS predict_end"
        ")"
        for item in years
    )
    sql = f"""
    CREATE TEMP TABLE manifest AS
    SELECT * FROM UNNEST([
      {manifest_sql}
    ]);

    INSERT INTO `{prediction_table}`
    (model_id, predict_date, horizon, sec_code, score, raw_score, score_orientation,
     rank_raw, rank_pct, feature_version, run_id, research_status, promotion_status, created_at)
    SELECT
      @synthetic_model_id,
      pred.predict_date,
      pred.horizon,
      pred.sec_code,
      pred.score,
      pred.raw_score,
      pred.score_orientation,
      pred.rank_raw,
      pred.rank_pct,
      pred.feature_version,
      @synthetic_run_id,
      'candidate',
      'not_promoted',
      CURRENT_TIMESTAMP()
    FROM manifest AS m
    JOIN `{prediction_table}` AS pred
      ON pred.run_id = m.source_run_id
     AND pred.model_id = m.source_model_id
     AND pred.predict_date BETWEEN DATE '{predict_start.isoformat()}' AND DATE '{predict_end.isoformat()}'
     AND pred.predict_date BETWEEN m.predict_start AND m.predict_end
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("synthetic_model_id", "STRING", synthetic_model_id),
            bigquery.ScalarQueryParameter("synthetic_run_id", "STRING", synthetic_run_id),
        ],
        labels={"pipeline_component": "strategy1_cloudrun", "pipeline_step": "synthetic_continuous"},
    )
    job = client.query(sql, job_config=job_config)
    job.result()
    return job


def count_existing_target_rows(
    client: bigquery.Client,
    *,
    registry_table: str,
    prediction_table: str,
    synthetic_run_id: str,
    predict_start: date,
    predict_end: date,
) -> dict[str, int]:
    frame = query_dataframe(
        client,
        f"""
        SELECT
          (SELECT COUNT(*)
           FROM `{registry_table}`
           WHERE run_id = @run_id OR JSON_VALUE(model_params_json, '$.run_id') = @run_id) AS registry_rows,
          (SELECT COUNT(*)
           FROM `{prediction_table}`
           WHERE run_id = @run_id
             AND predict_date BETWEEN @predict_start AND @predict_end) AS prediction_rows
        """,
        [
            bigquery.ScalarQueryParameter("run_id", "STRING", synthetic_run_id),
            bigquery.ScalarQueryParameter("predict_start", "DATE", predict_start.isoformat()),
            bigquery.ScalarQueryParameter("predict_end", "DATE", predict_end.isoformat()),
        ],
    )
    row = frame.iloc[0]
    return {"registry_rows": int(row["registry_rows"]), "prediction_rows": int(row["prediction_rows"])}


def clear_synthetic_outputs(
    client: bigquery.Client,
    *,
    registry_table: str,
    prediction_table: str,
    synthetic_run_id: str,
    predict_start: date,
    predict_end: date,
) -> None:
    execute_query(
        client,
        f"""
        DELETE FROM `{registry_table}`
        WHERE run_id = @run_id OR JSON_VALUE(model_params_json, '$.run_id') = @run_id;

        DELETE FROM `{prediction_table}`
        WHERE run_id = @run_id
          AND predict_date BETWEEN @predict_start AND @predict_end;
        """,
        [
            bigquery.ScalarQueryParameter("run_id", "STRING", synthetic_run_id),
            bigquery.ScalarQueryParameter("predict_start", "DATE", predict_start.isoformat()),
            bigquery.ScalarQueryParameter("predict_end", "DATE", predict_end.isoformat()),
        ],
    )


def _date_str(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
