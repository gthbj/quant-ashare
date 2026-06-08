#!/usr/bin/env python3
"""Strategy 1 acceptance-gate v3 read-only replay.

This replays v3 against historical Cloud Run search outputs without retraining
models and without mutating ADS acceptance state.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from google.cloud import bigquery

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.strategy1_cloudrun.acceptance import contract_hash, contract_version, load_acceptance_contract
from scripts.strategy1_cloudrun.bq_io import (
    get_git_commit,
    join_gs_uri,
    make_client,
    query_dataframe,
    upload_directory_to_gcs,
    write_json,
    write_text,
)


ACCEPTANCE_GATE_VERSION = "strategy1_acceptance_gate_v3"
DEFAULT_CONTRACT_PATH = "configs/strategy1/model_acceptance_contract_v3.yml"
DEFAULT_REPLAY_ID = "acceptance_gate_v3_replay_20260608_01"
DEFAULT_SEARCH_IDS = [
    "sklearn_native_pvfq_n30_bw_h5_20260605_01",
    "cloudrun_python_lgbm_pvfq_n30_bw_h5_20260605_01",
    "cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01",
    "cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_20260606_01",
    "cloudrun_python_riskfeat_lgbm_reg_pvfq_n30_bw_h5_20260606_01",
]
LEGACY_VALID_AS_CV_SEARCH_IDS = {
    "sklearn_native_pvfq_n30_bw_h5_20260605_01",
}
REQUIRED_ARTIFACTS = [
    "acceptance_gate_v3_replay_summary.json",
    "acceptance_gate_v3_replay_summary.md",
    "acceptance_gate_v3_candidates.csv",
    "acceptance_gate_v3_by_benchmark.csv",
    "artifact_manifest.json",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="策略 1 验收门 v3 只读 replay")
    parser.add_argument("--project", default="data-aquarium")
    parser.add_argument("--region", default="asia-east2")
    parser.add_argument("--strategy-id", default="ml_pv_clf_v0")
    parser.add_argument("--replay-id", default=DEFAULT_REPLAY_ID)
    parser.add_argument("--contract", default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--search-id", action="append", dest="search_ids", default=[])
    parser.add_argument("--top-k-per-search", type=int, default=5)
    parser.add_argument("--artifact-base-uri", default="gs://ashare-artifacts/reports/strategy1")
    parser.add_argument("--local-mirror-root", default="reports/strategy1")
    parser.add_argument("--skip-gcs-upload", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.search_ids = args.search_ids or list(DEFAULT_SEARCH_IDS)
    contract = load_acceptance_contract(args.contract)
    apply_contract_defaults(args, contract)
    validate_args(args, contract)

    client = make_client(args.project, args.region)
    out_dir = artifact_local_dir(args)
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates = fetch_selected_candidates(client, args)
    ensure_expected_top_k(candidates, args)

    nav_frame = fetch_nav_rows(client, args, candidates["backtest_id"].tolist())
    nav_map = split_nav_by_backtest(nav_frame)
    benchmark_meta = comparison_benchmarks(contract)
    benchmark_codes = [row["sec_code"] for row in benchmark_meta]
    benchmark_frame = fetch_benchmark_rows(client, args, benchmark_codes)
    benchmark_price_map = split_prices_by_benchmark(benchmark_frame)
    ensure_benchmark_coverage(contract, nav_map, benchmark_price_map, benchmark_codes)

    candidate_rows: list[dict[str, Any]] = []
    benchmark_rows: list[dict[str, Any]] = []
    for record in candidates.to_dict(orient="records"):
        candidate_summary, per_benchmark = evaluate_candidate(record, nav_map[record["backtest_id"]], benchmark_price_map, benchmark_meta, contract, args)
        candidate_rows.append(candidate_summary)
        benchmark_rows.extend(per_benchmark)

    candidate_df = pd.DataFrame(candidate_rows).sort_values(["search_id", "search_rank_valid_only", "model_id"], na_position="last")
    benchmark_df = pd.DataFrame(benchmark_rows).sort_values(["search_id", "search_rank_valid_only", "model_id", "benchmark_sec_code"], na_position="last")

    candidate_df.to_csv(out_dir / "acceptance_gate_v3_candidates.csv", index=False)
    benchmark_df.to_csv(out_dir / "acceptance_gate_v3_by_benchmark.csv", index=False)

    summary = build_summary(args, contract, candidate_df, benchmark_df, out_dir)
    write_json(out_dir / "acceptance_gate_v3_replay_summary.json", summary)
    write_text(out_dir / "acceptance_gate_v3_replay_summary.md", render_markdown(summary, candidate_df))
    write_json(out_dir / "artifact_manifest.json", build_artifact_manifest(out_dir))

    missing = [name for name in REQUIRED_ARTIFACTS if not (out_dir / name).is_file()]
    if missing:
        raise SystemExit(f"missing acceptance-gate-v3 replay artifacts: {missing}")

    uploaded: list[str] = []
    if not args.skip_gcs_upload:
        uploaded = upload_directory_to_gcs(args.project, out_dir, artifact_gcs_uri(args))
        summary["artifact_upload_status"] = "uploaded"
        summary["artifact_uri"] = artifact_gcs_uri(args)
        summary["uploaded_artifacts"] = uploaded
        write_json(out_dir / "acceptance_gate_v3_replay_summary.json", summary)
        write_json(out_dir / "artifact_manifest.json", build_artifact_manifest(out_dir))
    else:
        summary["artifact_upload_status"] = "skipped"
        summary["artifact_uri"] = None
        write_json(out_dir / "acceptance_gate_v3_replay_summary.json", summary)

    print(json.dumps({
        "status": "succeeded",
        "replay_id": args.replay_id,
        "acceptance_gate_version": ACCEPTANCE_GATE_VERSION,
        "acceptance_contract_version": contract_version(contract),
        "acceptance_contract_sha256": contract_hash(contract),
        "search_ids": args.search_ids,
        "candidate_count": int(candidate_df.shape[0]),
        "accepted_count": int((candidate_df["v3_acceptance_status"] == "accepted").sum()),
        "rejected_count": int((candidate_df["v3_acceptance_status"] == "rejected").sum()),
        "artifact_uri": summary.get("artifact_uri"),
        "uploaded_artifact_count": len(uploaded),
        "local_dir": str(out_dir),
    }, ensure_ascii=False, indent=2))
    return 0


def apply_contract_defaults(args: argparse.Namespace, contract: dict[str, Any]) -> None:
    windows = contract.get("windows") or {}
    full = windows.get("default_replay_and_initial_cutover_full_period") or {}
    valid = windows.get("valid") or {}
    test = windows.get("test") or {}
    final = windows.get("final_holdout") or {}
    args.full_start_date = parse_date(full.get("start_date"))
    args.full_end_date = parse_date(full.get("end_date"))
    args.valid_start_date = parse_date(valid.get("start_date"))
    args.valid_end_date = parse_date(valid.get("end_date"))
    args.test_start_date = parse_date(test.get("start_date"))
    args.test_end_date = parse_date(test.get("end_date"))
    args.final_holdout_start_date = parse_date(final.get("start_date"))
    args.final_holdout_end_date = parse_date(final.get("end_date"))


def validate_args(args: argparse.Namespace, contract: dict[str, Any]) -> None:
    if contract_version(contract) != "model_acceptance_contract_v3":
        raise SystemExit("--contract must point to model_acceptance_contract_v3 for this replay")
    required_dates = [
        args.full_start_date,
        args.full_end_date,
        args.valid_start_date,
        args.valid_end_date,
        args.test_start_date,
        args.test_end_date,
        args.final_holdout_start_date,
        args.final_holdout_end_date,
    ]
    if any(value is None for value in required_dates):
        raise SystemExit("contract windows must define full/valid/test/final_holdout dates")
    if len(set(args.search_ids)) != len(args.search_ids):
        raise SystemExit("--search-id values must be unique")
    if args.top_k_per_search <= 0:
        raise SystemExit("--top-k-per-search must be positive")
    benchmarks = comparison_benchmarks(contract)
    if len(benchmarks) != 5:
        raise SystemExit(f"v3 comparison benchmark set must contain 5 indexes, got {len(benchmarks)}")


def artifact_local_dir(args: argparse.Namespace) -> Path:
    return (
        Path(args.local_mirror_root)
        / args.strategy_id
        / "acceptance_gate_v3_replay"
        / f"replay_id={args.replay_id}"
    )


def artifact_gcs_uri(args: argparse.Namespace) -> str:
    return join_gs_uri(
        args.artifact_base_uri,
        args.strategy_id,
        "acceptance_gate_v3_replay",
        f"replay_id={args.replay_id}",
    )


def comparison_benchmarks(contract: dict[str, Any]) -> list[dict[str, Any]]:
    benchmarks = ((contract.get("benchmarks") or {}).get("comparison_benchmarks") or [])
    return [dict(item) for item in benchmarks]


def fetch_selected_candidates(client: bigquery.Client, args: argparse.Namespace) -> pd.DataFrame:
    sql = f"""
    WITH selected_registry AS (
      SELECT
        reg.model_id,
        reg.strategy_id,
        reg.train_start_date,
        reg.train_end_date,
        reg.valid_start_date,
        reg.valid_end_date,
        reg.created_at,
        JSON_VALUE(reg.model_params_json, '$.run_id') AS run_id,
        JSON_VALUE(reg.metrics_json, '$.search_id') AS search_id,
        JSON_VALUE(reg.metrics_json, '$.source_run_id') AS source_run_id,
        JSON_VALUE(reg.metrics_json, '$.model_family') AS model_family,
        JSON_VALUE(reg.metrics_json, '$.model_backend') AS model_backend,
        JSON_VALUE(reg.metrics_json, '$.cv_confirmation_status') AS cv_confirmation_status,
        JSON_VALUE(reg.metrics_json, '$.valid_signal_status') AS valid_signal_status,
        JSON_VALUE(reg.metrics_json, '$.score_orientation') AS score_orientation,
        JSON_VALUE(reg.metrics_json, '$.primary_diagnosis') AS primary_diagnosis,
        JSON_VALUE(reg.metrics_json, '$.sample_filter_risk') AS sample_filter_risk,
        SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.shortlist_rank_valid_only') AS INT64) AS shortlist_rank_valid_only,
        SAFE_CAST(COALESCE(JSON_VALUE(reg.metrics_json, '$.oriented_valid_rank_ic_mean'), JSON_VALUE(reg.metrics_json, '$.valid_rank_ic_mean')) AS FLOAT64) AS effective_valid_rank_ic_mean,
        SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.valid_top_minus_bottom_fwd_ret_mean') AS FLOAT64) AS valid_top_minus_bottom_fwd_ret_mean,
        SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.cv_rank_ic_mean') AS FLOAT64) AS cv_rank_ic_mean,
        SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.cv_top_minus_bottom_fwd_ret_mean') AS FLOAT64) AS cv_top_minus_bottom_fwd_ret_mean,
        SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.cv_fold_count') AS INT64) AS cv_fold_count,
        SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_rank_ic_mean') AS FLOAT64) AS test_rank_ic_mean,
        SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_top_minus_bottom_fwd_ret_mean') AS FLOAT64) AS test_top_minus_bottom_fwd_ret_mean,
        reg.metrics_json,
        reg.model_params_json
      FROM `{args.project}.ashare_ads.ads_model_registry` AS reg
      WHERE reg.strategy_id = @strategy_id
        AND reg.status = 'selected'
        AND JSON_VALUE(reg.metrics_json, '$.search_id') IN UNNEST(@search_ids)
    ),
    test_rank_ic AS (
      SELECT
        day_ic.run_id,
        AVG(day_ic.rank_ic) AS test_rank_ic_mean
      FROM (
        SELECT
          pred.run_id,
          pred.predict_date,
          CORR(CAST(score_rank AS FLOAT64), CAST(ret_rank AS FLOAT64)) AS rank_ic
        FROM (
          SELECT
            pred.run_id,
            pred.predict_date,
            pred.sec_code,
            RANK() OVER (PARTITION BY pred.run_id, pred.predict_date ORDER BY pred.score) AS score_rank,
            RANK() OVER (PARTITION BY pred.run_id, pred.predict_date ORDER BY tp.target_return) AS ret_rank
          FROM `{args.project}.ashare_ads.ads_model_prediction_daily` AS pred
          JOIN `{args.project}.ashare_ads.ads_ml_training_panel_daily` AS tp
            ON tp.run_id = pred.run_id
           AND tp.trade_date = pred.predict_date
           AND tp.sec_code = pred.sec_code
          WHERE pred.run_id IN (SELECT DISTINCT run_id FROM selected_registry)
            AND pred.predict_date BETWEEN @test_start_date AND @test_end_date
            AND tp.split_tag = 'test'
            AND tp.target_return IS NOT NULL
        ) AS pred
        GROUP BY pred.run_id, pred.predict_date
      ) AS day_ic
      GROUP BY day_ic.run_id
    ),
    test_bucket_spread AS (
      SELECT
        scored.run_id,
        AVG(scored.top_minus_bottom) AS test_top_minus_bottom_fwd_ret_mean
      FROM (
        SELECT
          bucketed.run_id,
          bucketed.predict_date,
          AVG(IF(bucketed.score_bucket = 5, bucketed.target_return, NULL))
            - AVG(IF(bucketed.score_bucket = 1, bucketed.target_return, NULL)) AS top_minus_bottom
        FROM (
          SELECT
            pred.run_id,
            pred.predict_date,
            tp.target_return,
            NTILE(5) OVER (PARTITION BY pred.run_id, pred.predict_date ORDER BY pred.score) AS score_bucket
          FROM `{args.project}.ashare_ads.ads_model_prediction_daily` AS pred
          JOIN `{args.project}.ashare_ads.ads_ml_training_panel_daily` AS tp
            ON tp.run_id = pred.run_id
           AND tp.trade_date = pred.predict_date
           AND tp.sec_code = pred.sec_code
          WHERE pred.run_id IN (SELECT DISTINCT run_id FROM selected_registry)
            AND pred.predict_date BETWEEN @test_start_date AND @test_end_date
            AND tp.split_tag = 'test'
            AND tp.target_return IS NOT NULL
        ) AS bucketed
        GROUP BY bucketed.run_id, bucketed.predict_date
      ) AS scored
      GROUP BY scored.run_id
    )
    SELECT
      reg.model_id,
      reg.strategy_id,
      reg.train_start_date,
      reg.train_end_date,
      reg.valid_start_date,
      reg.valid_end_date,
      reg.created_at,
      reg.run_id,
      reg.search_id,
      reg.source_run_id,
      reg.model_family,
      reg.model_backend,
      reg.cv_confirmation_status,
      reg.valid_signal_status,
      reg.score_orientation,
      reg.primary_diagnosis,
      reg.sample_filter_risk,
      reg.shortlist_rank_valid_only,
      reg.effective_valid_rank_ic_mean,
      reg.valid_top_minus_bottom_fwd_ret_mean,
      reg.cv_rank_ic_mean,
      reg.cv_top_minus_bottom_fwd_ret_mean,
      reg.cv_fold_count,
      reg.test_rank_ic_mean,
      reg.test_top_minus_bottom_fwd_ret_mean,
      test_rank_ic.test_rank_ic_mean AS test_rank_ic_mean_fallback,
      test_bucket_spread.test_top_minus_bottom_fwd_ret_mean AS test_top_minus_bottom_fwd_ret_mean_fallback,
      reg.metrics_json,
      reg.model_params_json,
      bs.backtest_id,
      bs.start_date AS backtest_start_date,
      bs.end_date AS backtest_end_date,
      bs.total_return AS summary_total_return,
      bs.sharpe AS summary_sharpe,
      bs.max_drawdown AS summary_max_drawdown
    FROM selected_registry AS reg
    LEFT JOIN `{args.project}.ashare_ads.ads_backtest_performance_summary` AS bs
      ON bs.model_id = reg.model_id
    LEFT JOIN test_rank_ic
      ON test_rank_ic.run_id = reg.run_id
    LEFT JOIN test_bucket_spread
      ON test_bucket_spread.run_id = reg.run_id
    ORDER BY search_id, shortlist_rank_valid_only, reg.created_at, reg.model_id
    """
    frame = query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("strategy_id", "STRING", args.strategy_id),
            bigquery.ArrayQueryParameter("search_ids", "STRING", args.search_ids),
            bigquery.ScalarQueryParameter("test_start_date", "DATE", args.test_start_date),
            bigquery.ScalarQueryParameter("test_end_date", "DATE", args.test_end_date),
        ],
        labels={"component": "strategy1", "step": "accept_v3_replay_candidates"},
    )
    if frame.empty:
        raise RuntimeError(f"no selected registry rows found for search_ids={args.search_ids}")
    for column in [
        "train_start_date", "train_end_date", "valid_start_date", "valid_end_date",
        "backtest_start_date", "backtest_end_date",
    ]:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column]).dt.date
    return frame


def ensure_expected_top_k(frame: pd.DataFrame, args: argparse.Namespace) -> None:
    if frame["backtest_id"].isna().any():
        missing = frame.loc[frame["backtest_id"].isna(), ["search_id", "model_id"]].to_dict(orient="records")
        raise RuntimeError(f"selected rows missing backtest_id: {missing}")
    counts = frame.groupby("search_id").size().to_dict()
    expected = {search_id: args.top_k_per_search for search_id in args.search_ids}
    if counts != expected:
        raise RuntimeError(f"expected selected rows per search {expected}, got {counts}")


def fetch_nav_rows(client: bigquery.Client, args: argparse.Namespace, backtest_ids: list[str]) -> pd.DataFrame:
    sql = f"""
    SELECT
      backtest_id,
      trade_date,
      nav AS nav_value,
      daily_return
    FROM `{args.project}.ashare_ads.ads_backtest_nav_daily`
    WHERE backtest_id IN UNNEST(@backtest_ids)
      AND trade_date BETWEEN @full_start_date AND @full_end_date
    ORDER BY backtest_id, trade_date
    """
    frame = query_dataframe(
        client,
        sql,
        [
            bigquery.ArrayQueryParameter("backtest_ids", "STRING", backtest_ids),
            bigquery.ScalarQueryParameter("full_start_date", "DATE", args.full_start_date),
            bigquery.ScalarQueryParameter("full_end_date", "DATE", args.full_end_date),
        ],
        labels={"component": "strategy1", "step": "accept_v3_replay_nav"},
    )
    if frame.empty:
        raise RuntimeError("no NAV rows found for replay backtests")
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    return frame


def split_nav_by_backtest(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    grouped: dict[str, pd.DataFrame] = {}
    for backtest_id, group in frame.groupby("backtest_id", sort=False):
        grouped[str(backtest_id)] = group.sort_values("trade_date").reset_index(drop=True)
    return grouped


def fetch_benchmark_rows(client: bigquery.Client, args: argparse.Namespace, benchmark_codes: list[str]) -> pd.DataFrame:
    sql = f"""
    SELECT
      sec_code,
      trade_date,
      close
    FROM `{args.project}.ashare_dwd.dwd_index_eod`
    WHERE sec_code IN UNNEST(@benchmark_codes)
      AND trade_date BETWEEN @full_start_date AND @full_end_date
    ORDER BY sec_code, trade_date
    """
    frame = query_dataframe(
        client,
        sql,
        [
            bigquery.ArrayQueryParameter("benchmark_codes", "STRING", benchmark_codes),
            bigquery.ScalarQueryParameter("full_start_date", "DATE", args.full_start_date),
            bigquery.ScalarQueryParameter("full_end_date", "DATE", args.full_end_date),
        ],
        labels={"component": "strategy1", "step": "accept_v3_replay_benchmarks"},
    )
    if frame.empty:
        raise RuntimeError("no benchmark rows found for v3 replay")
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    return frame


def split_prices_by_benchmark(frame: pd.DataFrame) -> dict[str, pd.Series]:
    result: dict[str, pd.Series] = {}
    for sec_code, group in frame.groupby("sec_code", sort=False):
        ordered = group.sort_values("trade_date")
        series = pd.Series(ordered["close"].astype(float).values, index=list(ordered["trade_date"]), name=str(sec_code))
        result[str(sec_code)] = series
    return result


def ensure_benchmark_coverage(
    contract: dict[str, Any],
    nav_map: dict[str, pd.DataFrame],
    benchmark_price_map: dict[str, pd.Series],
    benchmark_codes: list[str],
) -> None:
    required = (((contract.get("replay_and_qa_requirements") or {}).get("comparison_benchmark_full_window_coverage_required")) is True)
    block_on_missing = (((contract.get("replay_and_qa_requirements") or {}).get("initial_cutover_block_on_missing_comparison_benchmark_window")) is True)
    expected_dates = sorted({trade_date for nav in nav_map.values() for trade_date in nav["trade_date"].tolist()})
    missing: dict[str, list[str]] = {}
    for benchmark_code in benchmark_codes:
        series = benchmark_price_map.get(benchmark_code)
        if series is None:
            missing[benchmark_code] = ["all_dates_missing"]
            continue
        missing_dates = [value.isoformat() for value in expected_dates if value not in series.index]
        if missing_dates:
            missing[benchmark_code] = missing_dates[:10]
    if missing and required and block_on_missing:
        raise RuntimeError(f"v3 replay blocked by missing benchmark coverage: {missing}")


def evaluate_candidate(
    record: dict[str, Any],
    nav_df: pd.DataFrame,
    benchmark_price_map: dict[str, pd.Series],
    benchmark_meta: list[dict[str, Any]],
    contract: dict[str, Any],
    args: argparse.Namespace,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metrics = parse_json(record.get("metrics_json"))
    strategy_total_return, return_period_count = total_return_from_daily_returns(nav_df["daily_return"])
    strategy_compound_annualized_return = compound_annualized_return(strategy_total_return, return_period_count)
    annualized_volatility = annualized_volatility_from_daily_returns(nav_df["daily_return"])
    sharpe_ratio = signed_zero_safe_ratio(strategy_compound_annualized_return, annualized_volatility)
    max_drawdown, peak_date, trough_date = max_drawdown_window(nav_df)
    calmar_ratio = signed_zero_safe_ratio(
        strategy_compound_annualized_return,
        abs(max_drawdown) if max_drawdown is not None else None,
    )
    final_holdout_days = int(nav_df[nav_df["trade_date"].between(args.final_holdout_start_date, args.final_holdout_end_date)].shape[0])

    benchmark_rows: list[dict[str, Any]] = []
    passed_benchmarks: list[str] = []
    for benchmark in benchmark_meta:
        benchmark_row = evaluate_relative_benchmark(
            record=record,
            nav_df=nav_df,
            benchmark=benchmark,
            benchmark_prices=benchmark_price_map[benchmark["sec_code"]],
            strategy_compound_annualized_return=strategy_compound_annualized_return,
            return_period_count=return_period_count,
            strategy_max_drawdown=max_drawdown,
            peak_date=peak_date,
            trough_date=trough_date,
        )
        benchmark_rows.append(benchmark_row)
        if benchmark_row["relative_gate_pass"]:
            passed_benchmarks.append(benchmark_row["benchmark_sec_code"])

    reasons = signal_quality_failures(record, metrics, contract)
    reasons.extend(absolute_gate_failures(sharpe_ratio, calmar_ratio, final_holdout_days, contract))
    if not passed_benchmarks:
        reasons.append("no_comparison_benchmark_passed_v3_relative_gate")
    status = "accepted" if not reasons else "rejected"
    cv_confirmation_status, cv_confirmation_status_from_fallback = effective_cv_confirmation_status(record, metrics)
    test_rank_ic, test_rank_ic_from_fallback = effective_test_metric(record, metrics, "test_rank_ic_mean")
    test_top_minus_bottom, test_top_minus_bottom_from_fallback = effective_test_metric(
        record,
        metrics,
        "test_top_minus_bottom_fwd_ret_mean",
    )

    candidate_summary = {
        "search_id": record.get("search_id"),
        "source_run_id": record.get("source_run_id"),
        "run_id": record.get("run_id"),
        "model_id": record.get("model_id"),
        "backtest_id": record.get("backtest_id"),
        "model_family": record.get("model_family"),
        "model_backend": record.get("model_backend"),
        "search_rank_valid_only": safe_int(record.get("shortlist_rank_valid_only")),
        "cv_confirmation_status": cv_confirmation_status,
        "cv_confirmation_status_from_fallback": cv_confirmation_status_from_fallback,
        "valid_signal_status": coalesce_text(record.get("valid_signal_status"), metrics.get("valid_signal_status")),
        "score_orientation": coalesce_text(record.get("score_orientation"), metrics.get("score_orientation")),
        "primary_diagnosis": coalesce_text(record.get("primary_diagnosis"), metrics.get("primary_diagnosis")),
        "sample_filter_risk": coalesce_text(record.get("sample_filter_risk"), metrics.get("sample_filter_risk")),
        "valid_rank_ic": first_finite(record.get("effective_valid_rank_ic_mean"), metrics.get("oriented_valid_rank_ic_mean"), metrics.get("valid_rank_ic_mean")),
        "valid_top_minus_bottom_fwd_ret": safe_float(coalesce_value(record.get("valid_top_minus_bottom_fwd_ret_mean"), metrics.get("valid_top_minus_bottom_fwd_ret_mean"))),
        "test_rank_ic": test_rank_ic,
        "test_rank_ic_from_fallback": test_rank_ic_from_fallback,
        "test_top_minus_bottom_fwd_ret": test_top_minus_bottom,
        "test_top_minus_bottom_fwd_ret_from_fallback": test_top_minus_bottom_from_fallback,
        "strategy_total_return": strategy_total_return,
        "strategy_compound_annualized_return": strategy_compound_annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "max_drawdown_peak_date": peak_date.isoformat() if peak_date else None,
        "max_drawdown_trough_date": trough_date.isoformat() if trough_date else None,
        "calmar_ratio": calmar_ratio,
        "final_holdout_trading_day_count": final_holdout_days,
        "final_holdout_gate_status": final_holdout_gate_status(final_holdout_days, contract),
        "passed_benchmark_sec_codes": passed_benchmarks,
        "passed_benchmark_count": len(passed_benchmarks),
        "v3_acceptance_status": status,
        "v3_acceptance_reasons": reasons,
        "acceptance_contract_version": contract_version(contract),
        "acceptance_contract_sha256": contract_hash(contract),
    }
    return candidate_summary, benchmark_rows


def evaluate_relative_benchmark(
    record: dict[str, Any],
    nav_df: pd.DataFrame,
    benchmark: dict[str, Any],
    benchmark_prices: pd.Series,
    strategy_compound_annualized_return: float | None,
    return_period_count: int,
    strategy_max_drawdown: float | None,
    peak_date: date | None,
    trough_date: date | None,
) -> dict[str, Any]:
    dates = list(nav_df["trade_date"])
    start_date = dates[0]
    end_date = dates[-1]
    benchmark_total_return, benchmark_effective_return_period_count = benchmark_total_return_from_strategy_dates(
        nav_df,
        benchmark_prices,
    )
    benchmark_compound_annualized_return = compound_annualized_return(
        benchmark_total_return,
        benchmark_effective_return_period_count,
    )
    strategy_excess_compound_annualized_return = subtract_or_none(
        strategy_compound_annualized_return,
        benchmark_compound_annualized_return,
    )

    peak_close = benchmark_prices.get(peak_date) if peak_date is not None else None
    trough_close = benchmark_prices.get(trough_date) if trough_date is not None else None
    benchmark_same_window_return = subtract_or_none(safe_divide(trough_close, peak_close), 1.0)
    strategy_max_drawdown_same_window_excess = subtract_or_none(strategy_max_drawdown, benchmark_same_window_return)
    excess_calmar_ratio, relative_gate_pass, pass_branch, failure_reason = evaluate_excess_calmar_branch(
        strategy_excess_compound_annualized_return,
        strategy_max_drawdown_same_window_excess,
    )

    return {
        "search_id": record.get("search_id"),
        "run_id": record.get("run_id"),
        "model_id": record.get("model_id"),
        "backtest_id": record.get("backtest_id"),
        "search_rank_valid_only": safe_int(record.get("shortlist_rank_valid_only")),
        "benchmark_sec_code": benchmark["sec_code"],
        "benchmark_name_zh": benchmark.get("benchmark_name_zh"),
        "window_start_date": start_date.isoformat(),
        "window_end_date": end_date.isoformat(),
        "strategy_effective_return_period_count": return_period_count,
        "benchmark_effective_return_period_count": benchmark_effective_return_period_count,
        "strategy_compound_annualized_return": strategy_compound_annualized_return,
        "benchmark_compound_annualized_return": benchmark_compound_annualized_return,
        "strategy_excess_compound_annualized_return": strategy_excess_compound_annualized_return,
        "benchmark_same_window_return": benchmark_same_window_return,
        "strategy_max_drawdown_same_window_excess": strategy_max_drawdown_same_window_excess,
        "excess_calmar_ratio": excess_calmar_ratio,
        "relative_gate_pass": relative_gate_pass,
        "relative_gate_pass_branch": pass_branch,
        "relative_gate_failure_reason": failure_reason,
    }


def signal_quality_failures(record: dict[str, Any], metrics: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    required = contract.get("required") or {}
    signal_gate = contract.get("signal_quality_gate") or {}
    thresholds = signal_gate.get("thresholds") or {}
    diagnosis = contract.get("diagnosis") or {}

    cv_status, _ = effective_cv_confirmation_status(record, metrics)
    if cv_status != required.get("cv_confirmation_status", "passed"):
        failures.append(f"cv_confirmation_status!={required.get('cv_confirmation_status', 'passed')}")

    valid_signal_status = coalesce_text(record.get("valid_signal_status"), metrics.get("valid_signal_status"))
    if valid_signal_status != required.get("valid_signal_status", "stable"):
        failures.append(f"valid_signal_status!={required.get('valid_signal_status', 'stable')}")

    score_orientation = coalesce_text(record.get("score_orientation"), metrics.get("score_orientation"))
    allowed_orientations = set(required.get("allowed_score_orientation") or [])
    if score_orientation not in allowed_orientations:
        failures.append("score_orientation_not_allowed")

    valid_rank_ic = first_finite(record.get("effective_valid_rank_ic_mean"), metrics.get("oriented_valid_rank_ic_mean"), metrics.get("valid_rank_ic_mean"))
    if not compare_metric(valid_rank_ic, threshold_operator(thresholds, "valid_rank_ic"), threshold_value(thresholds, "valid_rank_ic")):
        failures.append("valid_rank_ic<=0")

    valid_tb = safe_float(coalesce_value(record.get("valid_top_minus_bottom_fwd_ret_mean"), metrics.get("valid_top_minus_bottom_fwd_ret_mean")))
    if not compare_metric(valid_tb, threshold_operator(thresholds, "valid_top_minus_bottom_fwd_ret"), threshold_value(thresholds, "valid_top_minus_bottom_fwd_ret")):
        failures.append("valid_top_minus_bottom<=0")

    test_rank_ic, _ = effective_test_metric(record, metrics, "test_rank_ic_mean")
    if not compare_metric(test_rank_ic, threshold_operator(thresholds, "test_rank_ic"), threshold_value(thresholds, "test_rank_ic")):
        failures.append("test_rank_ic<=0")

    test_tb, _ = effective_test_metric(record, metrics, "test_top_minus_bottom_fwd_ret_mean")
    if not compare_metric(test_tb, threshold_operator(thresholds, "test_top_minus_bottom_fwd_ret"), threshold_value(thresholds, "test_top_minus_bottom_fwd_ret")):
        failures.append("test_top_minus_bottom<=0")

    primary_diagnosis = coalesce_text(record.get("primary_diagnosis"), metrics.get("primary_diagnosis"))
    hard_reject_diagnoses = set(diagnosis.get("hard_reject_primary_diagnosis") or [])
    if primary_diagnosis in hard_reject_diagnoses:
        failures.append(f"primary_diagnosis={primary_diagnosis}")

    sample_filter_risk = coalesce_text(record.get("sample_filter_risk"), metrics.get("sample_filter_risk"))
    bad_sample_filter_risk = set(((diagnosis.get("hard_reject_confidence_by_diagnosis") or {}).get("sample_filter_risk") or []))
    if sample_filter_risk in bad_sample_filter_risk:
        failures.append(f"sample_filter_risk={sample_filter_risk}")
    return failures


def effective_cv_confirmation_status(record: dict[str, Any], metrics: dict[str, Any]) -> tuple[str | None, bool]:
    raw_status = coalesce_text(record.get("cv_confirmation_status"), metrics.get("cv_confirmation_status"))
    if raw_status is not None:
        return raw_status, False
    cv_rank_ic = first_finite(record.get("cv_rank_ic_mean"), metrics.get("cv_rank_ic_mean"))
    cv_top_minus_bottom = safe_float(coalesce_value(record.get("cv_top_minus_bottom_fwd_ret_mean"), metrics.get("cv_top_minus_bottom_fwd_ret_mean")))
    cv_fold_count = safe_int(coalesce_value(record.get("cv_fold_count"), metrics.get("cv_fold_count")))
    if cv_rank_ic is not None and cv_top_minus_bottom is not None:
        if cv_fold_count is not None and cv_fold_count < 3:
            return "failed", True
        return ("passed" if cv_rank_ic > 0 and cv_top_minus_bottom > 0 else "failed"), True

    legacy_status = legacy_valid_as_cv_confirmation_status(record, metrics)
    if legacy_status is not None:
        return legacy_status, True
    return None, False


def legacy_valid_as_cv_confirmation_status(record: dict[str, Any], metrics: dict[str, Any]) -> str | None:
    search_id = coalesce_text(record.get("search_id"), metrics.get("search_id"))
    if search_id not in LEGACY_VALID_AS_CV_SEARCH_IDS:
        return None
    valid_signal_status = coalesce_text(record.get("valid_signal_status"), metrics.get("valid_signal_status"))
    valid_rank_ic = first_finite(
        record.get("effective_valid_rank_ic_mean"),
        metrics.get("oriented_valid_rank_ic_mean"),
        metrics.get("valid_rank_ic_mean"),
    )
    valid_top_minus_bottom = safe_float(
        coalesce_value(
            record.get("valid_top_minus_bottom_fwd_ret_mean"),
            metrics.get("valid_top_minus_bottom_fwd_ret_mean"),
        )
    )
    if valid_signal_status is None or valid_rank_ic is None or valid_top_minus_bottom is None:
        return None
    return (
        "passed"
        if valid_signal_status == "stable" and valid_rank_ic > 0 and valid_top_minus_bottom > 0
        else "failed"
    )


def effective_test_metric(record: dict[str, Any], metrics: dict[str, Any], field_name: str) -> tuple[float | None, bool]:
    fallback_field_name = f"{field_name}_fallback"
    raw_value = first_finite(record.get(field_name), metrics.get(field_name))
    if raw_value is not None:
        return raw_value, False
    fallback_value = first_finite(record.get(fallback_field_name))
    if fallback_value is not None:
        return fallback_value, True
    return None, False


def absolute_gate_failures(
    sharpe_ratio: float | None,
    calmar_ratio: float | None,
    final_holdout_days: int,
    contract: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    absolute_gate = contract.get("absolute_performance_gate") or {}
    final_holdout_gate = contract.get("final_holdout_gate") or {}

    if not compare_metric(sharpe_ratio, (absolute_gate.get("sharpe_ratio") or {}).get("operator"), (absolute_gate.get("sharpe_ratio") or {}).get("value")):
        failures.append("sharpe_ratio_below_v3_gate")
    if not compare_metric(calmar_ratio, (absolute_gate.get("calmar_ratio") or {}).get("operator"), (absolute_gate.get("calmar_ratio") or {}).get("value")):
        failures.append("calmar_ratio_below_v3_gate")
    if (
        coalesce_text(final_holdout_gate.get("enforcement")) != "diagnostic_only"
        and not compare_metric(
            float(final_holdout_days),
            (final_holdout_gate.get("trading_day_count") or {}).get("operator"),
            (final_holdout_gate.get("trading_day_count") or {}).get("value"),
        )
    ):
        failures.append("final_holdout_trading_day_count_below_v3_gate")
    return failures


def final_holdout_gate_status(final_holdout_days: int, contract: dict[str, Any]) -> str:
    final_holdout_gate = contract.get("final_holdout_gate") or {}
    passed = compare_metric(
        float(final_holdout_days),
        (final_holdout_gate.get("trading_day_count") or {}).get("operator"),
        (final_holdout_gate.get("trading_day_count") or {}).get("value"),
    )
    enforcement = coalesce_text(final_holdout_gate.get("enforcement")) or "blocking"
    if passed:
        return "passed"
    if enforcement == "diagnostic_only":
        return "diagnostic_warn"
    return "failed"


def build_summary(
    args: argparse.Namespace,
    contract: dict[str, Any],
    candidate_df: pd.DataFrame,
    benchmark_df: pd.DataFrame,
    out_dir: Path,
) -> dict[str, Any]:
    accepted = candidate_df[candidate_df["v3_acceptance_status"] == "accepted"]
    rejected = candidate_df[candidate_df["v3_acceptance_status"] == "rejected"]
    by_search = []
    for search_id, group in candidate_df.groupby("search_id", sort=False):
        by_search.append({
            "search_id": search_id,
            "candidate_count": int(group.shape[0]),
            "accepted_count": int((group["v3_acceptance_status"] == "accepted").sum()),
            "rejected_count": int((group["v3_acceptance_status"] == "rejected").sum()),
        })
    rejection_reason_counts = (
        rejected.explode("v3_acceptance_reasons")["v3_acceptance_reasons"].dropna().value_counts().to_dict()
        if not rejected.empty else {}
    )
    return {
        "replay_id": args.replay_id,
        "strategy_id": args.strategy_id,
        "acceptance_gate_version": ACCEPTANCE_GATE_VERSION,
        "acceptance_contract_version": contract_version(contract),
        "acceptance_contract_sha256": contract_hash(contract),
        "search_ids": args.search_ids,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "artifact_local_dir": str(out_dir),
        "artifact_uri": None,
        "artifact_upload_status": "skipped" if args.skip_gcs_upload else "uploaded",
        "candidate_count": int(candidate_df.shape[0]),
        "accepted_count": int(accepted.shape[0]),
        "rejected_count": int(rejected.shape[0]),
        "accepted_model_ids": accepted["model_id"].tolist(),
        "accepted_backtest_ids": accepted["backtest_id"].tolist(),
        "accepted_search_ids": sorted(set(accepted["search_id"].tolist())),
        "by_search": by_search,
        "rejection_reason_counts": rejection_reason_counts,
        "comparison_benchmark_codes": sorted(set(benchmark_df["benchmark_sec_code"].tolist())),
    }


def render_markdown(summary: dict[str, Any], candidate_df: pd.DataFrame) -> str:
    lines = [
        "# Strategy 1 acceptance gate v3 replay",
        "",
        f"- replay_id: `{summary['replay_id']}`",
        f"- contract_version: `{summary['acceptance_contract_version']}`",
        f"- contract_sha256: `{summary['acceptance_contract_sha256']}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- accepted_count: `{summary['accepted_count']}`",
        f"- rejected_count: `{summary['rejected_count']}`",
        "",
        "## by_search",
        "",
        "| search_id | candidate_count | accepted_count | rejected_count |",
        "|---|---:|---:|---:|",
    ]
    for row in summary["by_search"]:
        lines.append(
            f"| {row['search_id']} | {row['candidate_count']} | {row['accepted_count']} | {row['rejected_count']} |"
        )
    lines.extend(["", "## accepted_candidates", ""])
    accepted = candidate_df[candidate_df["v3_acceptance_status"] == "accepted"]
    if accepted.empty:
        lines.append("- none")
    else:
        for row in accepted.sort_values(["search_id", "search_rank_valid_only"]).to_dict(orient="records"):
            lines.append(
                f"- `{row['search_id']}` rank `{row.get('search_rank_valid_only')}` model `{row['model_id']}` backtest `{row['backtest_id']}` passed `{','.join(row.get('passed_benchmark_sec_codes') or [])}`"
            )
    lines.extend(["", "## rejected_reason_counts", ""])
    if not summary["rejection_reason_counts"]:
        lines.append("- none")
    else:
        for reason, count in summary["rejection_reason_counts"].items():
            lines.append(f"- `{reason}`: {count}")
    return "\n".join(lines) + "\n"


def build_artifact_manifest(out_dir: Path) -> dict[str, Any]:
    files = []
    for path in sorted(out_dir.rglob("*")):
        if path.is_file():
            files.append({
                "relative_path": path.relative_to(out_dir).as_posix(),
                "size_bytes": path.stat().st_size,
            })
    return {"files": files}


def parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return pd.to_datetime(value).date()


def parse_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def coalesce_value(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        try:
            if pd.isna(value):
                continue
        except Exception:
            pass
        return value
    return None


def coalesce_text(*values: Any) -> str | None:
    value = coalesce_value(*values)
    return None if value is None else str(value)


def safe_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
    except Exception:
        pass
    try:
        result = float(value)
    except Exception:
        return None
    return result if math.isfinite(result) else None


def safe_int(value: Any) -> int | None:
    try:
        if value is None or pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return int(value)
    except Exception:
        return None


def first_finite(*values: Any) -> float | None:
    for value in values:
        numeric = safe_float(value)
        if numeric is not None:
            return numeric
    return None


def threshold_value(thresholds: dict[str, Any], key: str) -> float | None:
    payload = thresholds.get(key) or {}
    return safe_float(payload.get("value"))


def threshold_operator(thresholds: dict[str, Any], key: str) -> str:
    payload = thresholds.get(key) or {}
    return str(payload.get("operator") or ">")


def compare_metric(actual: float | None, operator: Any, threshold: Any) -> bool:
    actual_value = numeric_value(actual)
    threshold_value_local = numeric_value(threshold)
    if actual_value is None or threshold_value_local is None or math.isnan(actual_value) or math.isnan(threshold_value_local):
        return False
    if operator == ">":
        return actual_value > threshold_value_local
    if operator == ">=":
        return actual_value >= threshold_value_local
    if operator == "=":
        return math.isclose(actual_value, threshold_value_local, rel_tol=0.0, abs_tol=1e-12)
    raise ValueError(f"unsupported operator: {operator}")


def total_return_from_daily_returns(series: pd.Series) -> tuple[float | None, int]:
    valid = [float(value) for value in series.dropna().tolist() if 1.0 + float(value) > 0]
    if not valid:
        return None, 0
    gross = math.exp(sum(math.log1p(value) for value in valid))
    return gross - 1.0, len(valid)


def compound_annualized_return(total_return: float | None, return_period_count: int, annual_factor: int = 252) -> float | None:
    if total_return is None or return_period_count <= 0:
        return None
    gross = 1.0 + total_return
    if gross <= 0:
        return None
    return gross ** (annual_factor / return_period_count) - 1.0


def compound_annualized_return_from_gross(gross: float | None, return_period_count: int, annual_factor: int = 252) -> float | None:
    if gross is None or return_period_count <= 0 or gross <= 0:
        return None
    return gross ** (annual_factor / return_period_count) - 1.0


def annualized_volatility_from_daily_returns(series: pd.Series, annual_factor: int = 252) -> float | None:
    valid = pd.to_numeric(series, errors="coerce").dropna()
    if valid.empty:
        return None
    std = valid.std(ddof=1)
    if pd.isna(std):
        return 0.0
    return float(std) * math.sqrt(annual_factor)


def benchmark_total_return_from_strategy_dates(nav_df: pd.DataFrame, benchmark_prices: pd.Series) -> tuple[float | None, int]:
    gross = 1.0
    periods = 0
    previous_trade_date: date | None = None
    for row in nav_df.itertuples(index=False):
        current_trade_date = row.trade_date
        strategy_daily_return = safe_float(row.daily_return)
        if strategy_daily_return is None or 1.0 + strategy_daily_return <= 0:
            previous_trade_date = current_trade_date
            continue
        if previous_trade_date is None:
            gross *= 1.0
            periods += 1
            previous_trade_date = current_trade_date
            continue
        previous_close = benchmark_prices.get(previous_trade_date)
        current_close = benchmark_prices.get(current_trade_date)
        gross_factor = safe_divide(current_close, previous_close)
        if gross_factor is None or gross_factor <= 0:
            return None, periods
        gross *= gross_factor
        periods += 1
        previous_trade_date = current_trade_date
    return gross - 1.0, periods


def signed_zero_safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    if math.isclose(denominator, 0.0, rel_tol=0.0, abs_tol=1e-12):
        if numerator > 0:
            return float("inf")
        if numerator < 0:
            return float("-inf")
        return 0.0
    return numerator / denominator


def max_drawdown_window(nav_df: pd.DataFrame) -> tuple[float | None, date | None, date | None]:
    nav_values = pd.to_numeric(nav_df["nav_value"], errors="coerce")
    if nav_values.empty or nav_values.isna().all():
        return None, None, None
    running_peak = nav_values.cummax()
    drawdown = nav_values / running_peak - 1.0
    trough_pos = int(drawdown.values.argmin())
    max_drawdown = safe_float(drawdown.iloc[trough_pos])
    peak_value = running_peak.iloc[trough_pos]
    subset = nav_values.iloc[: trough_pos + 1]
    peak_positions = [idx for idx, value in enumerate(subset.tolist()) if math.isclose(value, float(peak_value), rel_tol=0.0, abs_tol=1e-12)]
    peak_pos = peak_positions[-1] if peak_positions else 0
    peak_date = nav_df.iloc[peak_pos]["trade_date"]
    trough_date = nav_df.iloc[trough_pos]["trade_date"]
    return max_drawdown, peak_date, trough_date


def safe_divide(numerator: Any, denominator: Any) -> float | None:
    num = safe_float(numerator)
    den = safe_float(denominator)
    if num is None or den is None or math.isclose(den, 0.0, rel_tol=0.0, abs_tol=1e-12):
        return None
    return num / den


def numeric_value(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return None


def subtract_or_none(left: Any, right: Any) -> float | None:
    left_value = safe_float(left)
    right_value = safe_float(right)
    if left_value is None or right_value is None:
        return None
    return left_value - right_value


def evaluate_excess_calmar_branch(
    strategy_excess_compound_annualized_return: float | None,
    strategy_max_drawdown_same_window_excess: float | None,
) -> tuple[float | None, bool, str | None, str | None]:
    excess = safe_float(strategy_excess_compound_annualized_return)
    same_window_excess = safe_float(strategy_max_drawdown_same_window_excess)
    if excess is None or same_window_excess is None:
        return None, False, None, "relative_gate_inputs_missing"
    if excess <= 0:
        return None, False, None, "strategy_excess_compound_annualized_return<=0"
    if same_window_excess > 0:
        return None, True, "strategy_max_drawdown_same_window_excess", None
    if math.isclose(same_window_excess, 0.0, rel_tol=0.0, abs_tol=1e-12):
        return None, False, None, "strategy_max_drawdown_same_window_excess=0"
    excess_calmar_ratio = excess / abs(same_window_excess)
    if excess_calmar_ratio > 1.0:
        return excess_calmar_ratio, True, "excess_calmar_ratio", None
    return excess_calmar_ratio, False, None, "excess_calmar_ratio<=1"


if __name__ == "__main__":
    raise SystemExit(main())
