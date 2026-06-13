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

from .bq_io import (
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
from .annual_rolling_plan import horizon_natural_frequency_for
from .config import (
    Experiment,
    add_common_args,
    apply_cli_overrides,
    experiment_to_b64,
    load_runner_config,
)
from .dataset_roles import TableResolver, validate_output_dataset_role

# Official CA-on continuous backtest 口径（DECISION-20260612-03）。
# 与 ledger.py 的 CORPORATE_ACTIONS_CASH_DIV_AND_SPLIT / DIVIDEND_TAX_FLAT_10PCT 一致，
# 这里用字面量避免把重量级 ledger 依赖拖进合成工具的 import 路径。
CA_ON_CORPORATE_ACTIONS = "cash_div_and_split_v1"
CA_ON_DIVIDEND_TAX_MODE = "flat_10pct"
SYNTH_BACKTEST_TAIL_RISK_PROFILE_ID = "diagnostic_only"


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
    if args.emit_backtest_experiment_json:
        payload_b64 = emit_backtest_experiment_json(config, args)
        print(payload_b64)
        return 0
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
    parser.add_argument(
        "--emit-backtest-experiment-json",
        action="store_true",
        help=(
            "Emit a base64 CA-on Experiment payload for the official synthetic continuous "
            "backtest (backtest_report --experiment-json). Derives label_horizon/feature_set_id/"
            "feature_version/weight_version from the source registry rows and bakes in "
            "corporate_actions=cash_div_and_split_v1 / dividend_tax_mode=flat_10pct."
        ),
    )
    parser.add_argument("--backtest-id", default=None, help="Required with --emit-backtest-experiment-json")
    parser.add_argument(
        "--backtest-experiment-id",
        default=None,
        help="Optional experiment_id for the emitted backtest payload (defaults to synthetic_run_id)",
    )
    parser.add_argument("--rebalance-frequency", default="biweekly")
    parser.add_argument("--target-holdings", type=int, default=20)
    parser.add_argument("--max-single-weight", type=float, default=0.075)
    parser.add_argument("--market-state-version", default="market_state_v0_20260606")
    return parser.parse_args()


def emit_backtest_experiment_json(config, args: argparse.Namespace) -> str:
    """Resolve the synthetic source lineage from the registry and emit the CA-on payload.

    Uses the same source registry derivation as the merge path so the emitted payload's
    label_horizon / feature_set_id / feature_version / weight_version exactly match the
    synthetic registry written by run_synthetic_merge.
    """
    if not args.backtest_id:
        raise ValueError("--emit-backtest-experiment-json requires --backtest-id")
    manifest = load_synthetic_manifest(Path(args.manifest_json))
    synthetic_run_id = manifest["synthetic_run_id"]
    years: list[YearSlice] = manifest["years"]
    client = make_client(config.project, config.region)
    resolver = TableResolver(dataset_role=config.output_dataset_role, project=config.project)
    registry_table = resolver.fqn("model_registry")
    source_rows = load_source_registry_rows(
        client,
        config,
        registry_table=registry_table,
        years=years,
        require_source_refit=args.require_source_refit,
    )
    source_lineage = unify_source_lineage(years, source_rows)
    experiment = build_synthetic_backtest_experiment(
        synthetic_run_id=synthetic_run_id,
        backtest_id=args.backtest_id,
        predict_start=years[0].predict_start.isoformat(),
        predict_end=years[-1].predict_end.isoformat(),
        source_lineage=source_lineage,
        rebalance_frequency=args.rebalance_frequency,
        target_holdings=args.target_holdings,
        max_single_weight=args.max_single_weight,
        market_state_version=args.market_state_version,
        experiment_id=args.backtest_experiment_id,
    )
    return experiment_to_b64(experiment)


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
    source_lineage = unify_source_lineage(years, source_rows)
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
        source_lineage=source_lineage,
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
          created_at,
          JSON_VALUE(model_params_json, '$.feature_set_id') AS params_feature_set_id,
          JSON_VALUE(model_params_json, '$.label_horizon') AS params_label_horizon,
          JSON_VALUE(model_params_json, '$.weight_version') AS params_weight_version
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
            horizon_col = int(row["horizon"])
            # label_horizon 与 registry horizon 列同源（write_registry: horizon=label_horizon），
            # 优先取 model_params_json.$.label_horizon，缺失时回退 horizon 列。
            label_horizon = _coerce_optional_int(row.get("params_label_horizon"))
            if label_horizon is None:
                label_horizon = horizon_col
            # 旧 source 行无 weight_version JSON 键时默认 constant_1p0_v0（等价 v1）。
            weight_version = _normalize_str(row.get("params_weight_version")) or "constant_1p0_v0"
            rows[source_run_id] = {
                "source_run_id": source_run_id,
                "source_selection_run_id": params.get("source_run_id") if params.get("refit") is True else source_run_id,
                "source_model_id": row["model_id"],
                "model_family": row["model_family"],
                "horizon": horizon_col,
                "label_horizon": label_horizon,
                "feature_set_id": _normalize_str(row.get("params_feature_set_id")),
                "weight_version": weight_version,
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


def unify_source_lineage(
    years: list[YearSlice],
    source_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Derive the single (label_horizon, feature_set_id, feature_version, weight_version)
    lineage shared by every source run, fail-fast if the source runs disagree.

    The synthetic registry historically hard-coded label_horizon=5 /
    feature_set_id=strategy1_pv_fin_risk_v0_20260606 / feature_version=
    strategy1_pv_v0_20260601. We now derive those from the source registry rows so a
    20d / large-cap-value arm produces a synthetic registry that matches its real
    prediction horizon instead of silently inheriting v1 constants.
    """
    # 每个维度收集 (source_run_id -> 值)；feature_version 与 feature_set_id 是两回事，分别派生。
    label_horizon: dict[str, int | None] = {}
    feature_set_id: dict[str, str | None] = {}
    feature_version: dict[str, str | None] = {}
    weight_version: dict[str, str] = {}
    for item in years:
        source = source_rows[item.source_run_id]
        label_horizon[item.source_run_id] = source.get("label_horizon")
        feature_set_id[item.source_run_id] = source.get("feature_set_id")
        feature_version[item.source_run_id] = source.get("feature_version")
        # weight_version 缺失已在 load_source_registry_rows 归一为 constant_1p0_v0。
        weight_version[item.source_run_id] = source.get("weight_version") or "constant_1p0_v0"

    def _unique(field: str, mapping: dict[str, Any]) -> Any:
        distinct = sorted({json.dumps(value, sort_keys=True) for value in mapping.values()})
        if len(distinct) != 1:
            detail = ", ".join(f"{run_id}={mapping[run_id]!r}" for run_id in sorted(mapping))
            raise RuntimeError(
                f"source runs disagree on {field}; synthetic registry cannot derive a unique value: {detail}"
            )
        return next(iter(mapping.values()))

    lineage = {
        "label_horizon": _unique("label_horizon", label_horizon),
        "feature_set_id": _unique("feature_set_id", feature_set_id),
        "feature_version": _unique("feature_version", feature_version),
        "weight_version": _unique("weight_version", weight_version),
    }
    # 必填 lineage 不能为空，否则 synth registry 会写出 NULL horizon / feature_set / feature_version。
    missing_required = [
        field for field in ("label_horizon", "feature_set_id", "feature_version")
        if lineage[field] in (None, "")
    ]
    if missing_required:
        raise RuntimeError(
            "source registry rows are missing required lineage fields "
            f"{missing_required}; synthetic registry cannot derive them"
        )
    return lineage


def build_synthetic_backtest_experiment(
    *,
    synthetic_run_id: str,
    backtest_id: str,
    predict_start: str,
    predict_end: str,
    source_lineage: dict[str, Any],
    rebalance_frequency: str = "biweekly",
    target_holdings: int = 20,
    max_single_weight: float = 0.075,
    market_state_version: str = "market_state_v0_20260606",
    experiment_id: str | None = None,
    experiment_group: str = "strategy1_annual_rolling_continuous",
) -> Experiment:
    """Build the CA-on continuous backtest Experiment payload for a synthetic run.

    `backtest_report --experiment-json` returns the payload Experiment verbatim and
    does NOT apply CLI overrides (experiment_resolution.py:30-33; Codex round-4 Blocker),
    so corporate_actions / synth run+backtest ids / lineage must be encoded in the
    payload itself. CA-on口径 is mandatory (DECISION-20260612-03): corporate_actions=
    cash_div_and_split_v1 / dividend_tax_mode=flat_10pct. tail_risk_profile_id stays
    diagnostic_only (default profile unchanged). Ledger defaults to v1 lot100 — that is a
    backtest_report CLI concern (no --use-float-ledger / --use-topdown-ledger), not an
    Experiment field, so nothing topdown-related is set here.
    """
    label_horizon = int(source_lineage["label_horizon"])
    return Experiment(
        experiment_id=experiment_id or synthetic_run_id,
        run_id=synthetic_run_id,
        backtest_id=backtest_id,
        prediction_run_id=synthetic_run_id,
        experiment_group=experiment_group,
        rebalance_frequency=rebalance_frequency,
        target_holdings=int(target_holdings),
        max_single_weight=float(max_single_weight),
        label_horizon=label_horizon,
        horizon_natural_frequency=horizon_natural_frequency_for(label_horizon),
        initial_state_mode="fresh",
        corporate_actions=CA_ON_CORPORATE_ACTIONS,
        dividend_tax_mode=CA_ON_DIVIDEND_TAX_MODE,
        feature_set_id=str(source_lineage["feature_set_id"]),
        feature_version=str(source_lineage["feature_version"]),
        weight_version=str(source_lineage["weight_version"]),
        tail_risk_profile_id=SYNTH_BACKTEST_TAIL_RISK_PROFILE_ID,
        market_state_version=market_state_version,
        requires_retrain=False,
        status="planned",
        # synthetic run 没有训练窗口；continuous 段由 predict_start/predict_end 界定。
        train_start=predict_start,
        train_end=predict_start,
        valid_start=predict_start,
        valid_end=predict_start,
        test_start=predict_start,
        test_end=predict_end,
        predict_start=predict_start,
        predict_end=predict_end,
    )


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
    source_lineage: dict[str, Any],
    require_source_refit: bool,
    predict_start: date,
    predict_end: date,
) -> None:
    now = datetime.now(timezone.utc)
    source_run_ids = [row["source_run_id"] for row in year_slices]
    # 从 source registry 行派生的唯一 lineage（去硬编码，Codex round-3 High-3）。
    # v1 复现红线：源是 h5 / strategy1_pv_fin_risk_v0_20260606 /
    # strategy1_pv_v0_20260601 / weight_version 缺失→constant_1p0_v0 时，派生值等于旧硬编码，
    # 故下面 label_horizon/feature_set_id/horizon/feature_version 字节级不变。
    derived_label_horizon = source_lineage["label_horizon"]
    derived_feature_set_id = source_lineage["feature_set_id"]
    derived_feature_version = source_lineage["feature_version"]
    derived_weight_version = source_lineage["weight_version"]
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
        "label_horizon": derived_label_horizon,
        "feature_set_id": derived_feature_set_id,
        "tail_risk_profile_id": "diagnostic_only",
    }
    # weight_version 仅当为非 v1 默认时写入 params_json，保持 v1 (constant_1p0_v0) 字节级不变。
    if derived_weight_version != "constant_1p0_v0":
        params_json["weight_version"] = derived_weight_version
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
        "horizon": derived_label_horizon,
        "feature_version": derived_feature_version,
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


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float):
        # pandas 将缺失 JSON_VALUE 读成 NaN
        return value != value
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _normalize_str(value: Any) -> str | None:
    if _is_missing(value):
        return None
    return str(value).strip()


def _coerce_optional_int(value: Any) -> int | None:
    if _is_missing(value):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
