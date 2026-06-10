#!/usr/bin/env python3
"""Strategy 1 acceptance-gate v2 read-only diagnosis.

This implements PRD_20260606_04 Phase B/C. It reads existing ADS/DWD/DWS
artifacts, does not train, does not change predictions, and does not write ADS.
Outputs are local/GCS artifacts used to decide whether the current reference run
is rejected, needs more evidence, or can become a future baseline candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
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
    query_dataframe as bq_query_dataframe,
    upload_directory_to_gcs,
    write_json,
    write_text,
)
from scripts.strategy1_cloudrun.dataset_roles import (
    OUTPUT_DATASET_ROLE_CHOICES,
    rewrite_sql_dataset_role,
)


ACCEPTANCE_GATE_VERSION = "strategy1_acceptance_gate_v2"
OUTPUT_DATASET_ROLE = "ads"
DEFAULT_CONTRACT_PATH = "configs/strategy1/model_acceptance_contract_v2.yml"
DEFAULT_DIAGNOSIS_ID = "acceptance_gate_v2_reference_20260606_01"
DEFAULT_REFERENCE_RUN_ID = "s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01"
DEFAULT_REFERENCE_BACKTEST_ID = "bt_s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01"
DEFAULT_FEATURE_VERSION = "strategy1_pv_v0_20260601"
DEFAULT_LABEL_VERSION = "open_to_close_h1_5_10_20_v20260601"
REQUIRED_ARTIFACTS = [
    "acceptance_gate_v2_summary.json",
    "acceptance_gate_v2_summary.md",
    "portfolio_feasibility.json",
    "portfolio_feasibility_daily.csv",
    "portfolio_feasibility_by_target_holdings.csv",
    "lot_constraint_skipped_orders.csv",
    "actual_holdings_distribution.csv",
    "cash_weight_distribution.csv",
    "low_price_tilt_diagnostics.csv",
    "exposure_adjusted_return.csv",
    "eligible_universe_benchmark_nav.csv",
    "eligible_universe_benchmark_summary.json",
    "eligible_universe_benchmark_constituents.csv",
    "score_orientation_audit.json",
    "style_exposure_diagnostics.csv",
    "artifact_manifest.json",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="策略 1验收门 v2 只读诊断")
    parser.add_argument("--project", default="data-aquarium")
    parser.add_argument("--region", default="asia-east2")
    parser.add_argument("--strategy-id", default="ml_pv_clf_v0")
    parser.add_argument("--diagnosis-id", default=DEFAULT_DIAGNOSIS_ID)
    parser.add_argument("--reference-run-id", default=DEFAULT_REFERENCE_RUN_ID)
    parser.add_argument("--reference-backtest-id", default=DEFAULT_REFERENCE_BACKTEST_ID)
    parser.add_argument("--prediction-run-id", default=None)
    parser.add_argument("--contract", default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--feature-version", default=DEFAULT_FEATURE_VERSION)
    parser.add_argument("--label-version", default=DEFAULT_LABEL_VERSION)
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--full-start-date", default=None)
    parser.add_argument("--full-end-date", default=None)
    parser.add_argument("--valid-start-date", default=None)
    parser.add_argument("--valid-end-date", default=None)
    parser.add_argument("--test-start-date", default=None)
    parser.add_argument("--test-end-date", default=None)
    parser.add_argument("--final-holdout-start-date", default=None)
    parser.add_argument("--final-holdout-end-date", default=None)
    parser.add_argument("--benchmark-sec-code", default=None)
    parser.add_argument("--eligible-benchmark-cost-bps", type=float, default=12.0)
    parser.add_argument("--artifact-base-uri", default="gs://ashare-artifacts/reports/strategy1")
    parser.add_argument("--local-mirror-root", default="reports/strategy1")
    parser.add_argument("--output-dataset-role", choices=OUTPUT_DATASET_ROLE_CHOICES, default="ads")
    parser.add_argument("--skip-gcs-upload", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    set_output_dataset_role(args.output_dataset_role)
    args.prediction_run_id = args.prediction_run_id or args.reference_run_id
    contract = load_acceptance_contract(args.contract)
    apply_contract_defaults(args, contract)
    validate_args(args, contract)

    client = make_client(args.project, args.region)
    out_dir = artifact_local_dir(args)
    out_dir.mkdir(parents=True, exist_ok=True)

    model_meta = fetch_model_metadata(client, args)
    reference_metrics = fetch_reference_metrics(client, args)
    signal_metrics, bucket_lift = fetch_signal_metrics(client, args, model_meta)
    feasibility_inputs = fetch_portfolio_feasibility_inputs(client, args, contract, model_meta)
    feasibility = build_portfolio_feasibility(feasibility_inputs, contract, args)
    eligible_nav, eligible_summary, eligible_constituents = fetch_eligible_benchmark(client, args, contract)
    reference_metrics["full_period_excess_return_vs_eligible_executable"] = subtract_or_none(
        reference_metrics.get("full_period_total_return"),
        eligible_summary.get("eligible_executable_total_return_costed"),
    )
    style_exposure = fetch_style_exposure(client, args)
    score_audit = build_score_orientation_audit(model_meta, signal_metrics, bucket_lift)

    status, reasons = decide_acceptance_v2(
        contract=contract,
        reference_metrics=reference_metrics,
        signal_metrics=signal_metrics,
        portfolio_summary=feasibility["by_target_holdings"],
        eligible_summary=eligible_summary,
        score_audit=score_audit,
    )
    summary = build_summary(
        args=args,
        contract=contract,
        model_meta=model_meta,
        reference_metrics=reference_metrics,
        signal_metrics=signal_metrics,
        bucket_lift=bucket_lift,
        feasibility=feasibility,
        eligible_summary=eligible_summary,
        score_audit=score_audit,
        style_exposure=style_exposure,
        acceptance_status=status,
        acceptance_reasons=reasons,
        out_dir=out_dir,
    )

    write_outputs(
        out_dir=out_dir,
        summary=summary,
        markdown=render_markdown(summary),
        feasibility=feasibility,
        eligible_nav=eligible_nav,
        eligible_summary=eligible_summary,
        eligible_constituents=eligible_constituents,
        score_audit=score_audit,
        style_exposure=style_exposure,
    )

    manifest = build_artifact_manifest(out_dir)
    write_json(out_dir / "artifact_manifest.json", manifest)
    missing = [name for name in REQUIRED_ARTIFACTS if not (out_dir / name).is_file()]
    if missing:
        raise SystemExit(f"missing acceptance-gate-v2 artifacts: {missing}")

    summary["artifact_uri"] = None if args.skip_gcs_upload else artifact_gcs_uri(args)
    summary["artifact_upload_status"] = "skipped" if args.skip_gcs_upload else "uploaded"
    summary["artifact_manifest"] = manifest
    write_json(out_dir / "acceptance_gate_v2_summary.json", summary)
    write_text(out_dir / "acceptance_gate_v2_summary.md", render_markdown(summary))
    write_json(out_dir / "artifact_manifest.json", build_artifact_manifest(out_dir))

    uploaded: list[str] = []
    if not args.skip_gcs_upload:
        uploaded = upload_directory_to_gcs(args.project, out_dir, artifact_gcs_uri(args))
        summary["uploaded_artifacts"] = uploaded
        write_json(out_dir / "acceptance_gate_v2_summary.json", summary)
        write_json(out_dir / "artifact_manifest.json", build_artifact_manifest(out_dir))
        upload_directory_to_gcs(args.project, out_dir, artifact_gcs_uri(args))

    print(json.dumps({
        "status": "succeeded",
        "diagnosis_id": args.diagnosis_id,
        "acceptance_gate_version": ACCEPTANCE_GATE_VERSION,
        "acceptance_contract_version": contract_version(contract),
        "acceptance_contract_sha256": contract_hash(contract),
        "reference_run_id": args.reference_run_id,
        "reference_backtest_id": args.reference_backtest_id,
        "v2_acceptance_status": status,
        "v2_acceptance_reasons": reasons,
        "artifact_uri": summary.get("artifact_uri"),
        "uploaded_artifact_count": len(uploaded),
        "local_dir": str(out_dir),
    }, ensure_ascii=False, indent=2))
    return 0


def set_output_dataset_role(dataset_role: str) -> None:
    global OUTPUT_DATASET_ROLE
    OUTPUT_DATASET_ROLE = dataset_role


def query_dataframe(
    client: bigquery.Client,
    sql: str,
    params: list[bigquery.ScalarQueryParameter],
    *,
    labels: dict[str, str | None] | None = None,
) -> pd.DataFrame:
    sql = rewrite_sql_dataset_role(
        sql,
        dataset_role=OUTPUT_DATASET_ROLE,
        project=client.project,
    )
    return bq_query_dataframe(client, sql, params, labels=labels)


def apply_contract_defaults(args: argparse.Namespace, contract: dict[str, Any]) -> None:
    windows = contract.get("windows") or {}
    full = windows.get("full_period") or {}
    valid = windows.get("valid") or {}
    test = windows.get("test") or {}
    final = windows.get("final_holdout") or {}
    benchmarks = contract.get("benchmarks") or {}
    args.full_start_date = args.full_start_date or full.get("start_date")
    args.full_end_date = args.full_end_date or full.get("end_date")
    args.valid_start_date = args.valid_start_date or valid.get("start_date")
    args.valid_end_date = args.valid_end_date or valid.get("end_date")
    args.test_start_date = args.test_start_date or test.get("start_date")
    args.test_end_date = args.test_end_date or test.get("end_date")
    args.final_holdout_start_date = args.final_holdout_start_date or final.get("start_date")
    args.final_holdout_end_date = args.final_holdout_end_date or final.get("end_date")
    args.benchmark_sec_code = args.benchmark_sec_code or benchmarks.get("primary_benchmark_sec_code", "000001.SH")


def validate_args(args: argparse.Namespace, contract: dict[str, Any]) -> None:
    if contract_version(contract) != "model_acceptance_contract_v2":
        raise SystemExit("--contract must point to model_acceptance_contract_v2 for this diagnostic")
    missing = [
        name for name in [
            "full_start_date", "full_end_date", "valid_start_date", "valid_end_date",
            "test_start_date", "test_end_date", "final_holdout_start_date", "final_holdout_end_date",
        ]
        if getattr(args, name) is None
    ]
    if missing:
        raise SystemExit(f"missing date args or contract windows: {missing}")
    expected_targets = [10, 20, 30, 40]
    actual_targets = sorted(int(row["target_holdings"]) for row in portfolio_candidates(contract))
    if actual_targets != expected_targets:
        raise SystemExit(f"v2 target_holdings must be {expected_targets}, got {actual_targets}")
    if args.horizon != 5:
        raise SystemExit("acceptance gate v2 P0 currently expects horizon=5")


def artifact_local_dir(args: argparse.Namespace) -> Path:
    return (
        Path(args.local_mirror_root)
        / args.strategy_id
        / "acceptance_gate_v2"
        / f"diagnosis_id={args.diagnosis_id}"
    )


def artifact_gcs_uri(args: argparse.Namespace) -> str:
    return join_gs_uri(
        args.artifact_base_uri,
        args.strategy_id,
        "acceptance_gate_v2",
        f"diagnosis_id={args.diagnosis_id}",
    )


def fetch_model_metadata(client: bigquery.Client, args: argparse.Namespace) -> dict[str, Any]:
    sql = f"""
    SELECT
      reg.model_id,
      reg.strategy_id,
      reg.status,
      reg.train_start_date,
      reg.train_end_date,
      reg.valid_start_date,
      reg.valid_end_date,
      JSON_VALUE(reg.model_params_json, '$.run_id') AS prediction_run_id,
      JSON_VALUE(reg.metrics_json, '$.score_orientation') AS score_orientation,
      JSON_VALUE(reg.metrics_json, '$.model_backend') AS model_backend,
      JSON_VALUE(reg.metrics_json, '$.model_family') AS model_family,
      reg.model_params_json,
      reg.metrics_json
    FROM `{args.project}.ashare_ads.ads_model_registry` AS reg
    WHERE reg.strategy_id = @strategy_id
      AND reg.status = 'selected'
      AND JSON_VALUE(reg.model_params_json, '$.run_id') = @prediction_run_id
    ORDER BY reg.created_at DESC
    LIMIT 1
    """
    frame = query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("strategy_id", "STRING", args.strategy_id),
            bigquery.ScalarQueryParameter("prediction_run_id", "STRING", args.prediction_run_id),
        ],
        labels={"component": "strategy1", "step": "accept_v2_model"},
    )
    if frame.empty:
        raise RuntimeError(f"no selected model found for prediction_run_id={args.prediction_run_id}")
    record = normalize_record(frame.iloc[0].to_dict())
    record["metrics"] = parse_json(record.get("metrics_json"))
    record["params"] = parse_json(record.get("model_params_json"))
    record["score_orientation"] = record.get("score_orientation") or record["metrics"].get("score_orientation") or "unknown"
    return record


def fetch_reference_metrics(client: bigquery.Client, args: argparse.Namespace) -> dict[str, Any]:
    sql = f"""
    WITH nav AS (
      SELECT
        trade_date,
        nav AS nav_value,
        daily_return,
        benchmark_return,
        excess_return,
        benchmark_sec_code
      FROM `{args.project}.ashare_ads.ads_backtest_nav_daily`
      WHERE backtest_id = @backtest_id
        AND trade_date BETWEEN @full_start AND @full_end
    ),
    summary AS (
      SELECT
        backtest_id,
        strategy_id,
        model_id,
        start_date,
        end_date,
        total_return AS summary_total_return,
        annual_return,
        annual_vol,
        sharpe,
        max_drawdown AS summary_max_drawdown,
        turnover_annual,
        benchmark_sec_code AS summary_benchmark_sec_code,
        excess_return AS summary_excess_return,
        information_ratio AS summary_information_ratio,
        cost_bps,
        metrics_json
      FROM `{args.project}.ashare_ads.ads_backtest_performance_summary`
      WHERE backtest_id = @backtest_id
      LIMIT 1
    ),
    full_perf AS (
      SELECT
        COUNT(*) AS full_trading_days,
        EXP(SUM(IF(daily_return IS NULL OR 1.0 + daily_return <= 0, 0.0, LN(1.0 + daily_return)))) - 1.0
          AS full_period_total_return,
        EXP(SUM(IF(benchmark_return IS NULL OR 1.0 + benchmark_return <= 0, 0.0, LN(1.0 + benchmark_return)))) - 1.0
          AS full_period_benchmark_return,
        SAFE_MULTIPLY(SAFE_DIVIDE(AVG(excess_return), STDDEV_SAMP(excess_return)), SQRT(252.0))
          AS full_period_information_ratio,
        ARRAY_AGG(benchmark_sec_code IGNORE NULLS ORDER BY trade_date DESC LIMIT 1)[SAFE_OFFSET(0)]
          AS benchmark_sec_code
      FROM nav
    ),
    strategy_dd AS (
      SELECT MIN(nav_value / NULLIF(running_peak, 0) - 1.0) AS full_period_max_drawdown
      FROM (
        SELECT
          trade_date,
          nav_value,
          MAX(nav_value) OVER (
            ORDER BY trade_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
          ) AS running_peak
        FROM nav
      )
    ),
    benchmark_curve AS (
      SELECT
        trade_date,
        EXP(SUM(IF(benchmark_return IS NULL OR 1.0 + benchmark_return <= 0, 0.0, LN(1.0 + benchmark_return))) OVER (
          ORDER BY trade_date
          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )) AS benchmark_nav
      FROM nav
    ),
    benchmark_dd AS (
      SELECT MIN(benchmark_nav / NULLIF(benchmark_peak, 0) - 1.0) AS benchmark_max_drawdown
      FROM (
        SELECT
          trade_date,
          benchmark_nav,
          MAX(benchmark_nav) OVER (
            ORDER BY trade_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
          ) AS benchmark_peak
        FROM benchmark_curve
      )
    ),
    final_nav AS (
      SELECT *
      FROM nav
      WHERE trade_date BETWEEN @final_start AND @final_end
    ),
    final_perf AS (
      SELECT
        COUNT(*) AS final_holdout_trading_days,
        EXP(SUM(IF(daily_return IS NULL OR 1.0 + daily_return <= 0, 0.0, LN(1.0 + daily_return)))) - 1.0
          AS final_holdout_total_return,
        EXP(SUM(IF(benchmark_return IS NULL OR 1.0 + benchmark_return <= 0, 0.0, LN(1.0 + benchmark_return)))) - 1.0
          AS final_holdout_benchmark_return
      FROM final_nav
    )
    SELECT
      @backtest_id AS backtest_id,
      @full_start AS full_start_date,
      @full_end AS full_end_date,
      @final_start AS final_holdout_start_date,
      @final_end AS final_holdout_end_date,
      summary.strategy_id,
      summary.model_id,
      summary.start_date AS summary_start_date,
      summary.end_date AS summary_end_date,
      COALESCE(full_perf.benchmark_sec_code, summary.summary_benchmark_sec_code) AS benchmark_sec_code,
      full_perf.full_trading_days,
      full_perf.full_period_total_return,
      full_perf.full_period_benchmark_return,
      full_perf.full_period_total_return - full_perf.full_period_benchmark_return
        AS full_period_excess_return_vs_primary_benchmark,
      full_perf.full_period_information_ratio,
      COALESCE(strategy_dd.full_period_max_drawdown, summary.summary_max_drawdown) AS full_period_max_drawdown,
      benchmark_dd.benchmark_max_drawdown AS full_period_benchmark_max_drawdown,
      COALESCE(strategy_dd.full_period_max_drawdown, summary.summary_max_drawdown) - benchmark_dd.benchmark_max_drawdown
        AS full_period_relative_max_drawdown_vs_primary_benchmark,
      final_perf.final_holdout_trading_days,
      final_perf.final_holdout_total_return,
      final_perf.final_holdout_benchmark_return,
      final_perf.final_holdout_total_return - final_perf.final_holdout_benchmark_return
        AS final_holdout_excess_return_vs_primary_benchmark,
      summary.sharpe,
      summary.annual_return,
      summary.annual_vol,
      summary.turnover_annual,
      summary.cost_bps,
      summary.metrics_json
    FROM full_perf
    CROSS JOIN strategy_dd
    CROSS JOIN benchmark_dd
    CROSS JOIN final_perf
    LEFT JOIN summary ON TRUE
    """
    frame = query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("backtest_id", "STRING", args.reference_backtest_id),
            bigquery.ScalarQueryParameter("full_start", "DATE", args.full_start_date),
            bigquery.ScalarQueryParameter("full_end", "DATE", args.full_end_date),
            bigquery.ScalarQueryParameter("final_start", "DATE", args.final_holdout_start_date),
            bigquery.ScalarQueryParameter("final_end", "DATE", args.final_holdout_end_date),
        ],
        labels={"component": "strategy1", "step": "accept_v2_ref"},
    )
    if frame.empty:
        raise RuntimeError(f"no NAV/summary rows found for backtest_id={args.reference_backtest_id}")
    record = normalize_record(frame.iloc[0].to_dict())
    summary_metrics = parse_json(record.get("metrics_json"))
    record["summary_metrics"] = summary_metrics
    record["ledger_version"] = summary_metrics.get("ledger_version")
    record["lot_size"] = summary_metrics.get("lot_size")
    record["min_buy_lot"] = summary_metrics.get("min_buy_lot")
    return record


def fetch_signal_metrics(
    client: bigquery.Client,
    args: argparse.Namespace,
    model_meta: dict[str, Any],
) -> tuple[dict[str, Any], pd.DataFrame]:
    sql = f"""
    WITH scored AS (
      SELECT
        CASE
          WHEN pred.predict_date BETWEEN @valid_start AND @valid_end THEN 'valid'
          WHEN pred.predict_date BETWEEN @test_start AND @test_end THEN 'test'
          ELSE 'other'
        END AS split_tag,
        pred.predict_date,
        pred.sec_code,
        pred.score,
        sample.fwd_xs_ret_5d,
        sample.fwd_ret_5d
      FROM `{args.project}.ashare_ads.ads_model_prediction_daily` AS pred
      JOIN `{args.project}.ashare_dws.dws_stock_sample_daily` AS sample
        ON sample.trade_date = pred.predict_date
       AND sample.sec_code = pred.sec_code
       AND sample.trade_date BETWEEN @valid_start AND @test_end
       AND sample.label_version = @label_version
      WHERE pred.run_id = @prediction_run_id
        AND pred.model_id = @model_id
        AND pred.predict_date BETWEEN @valid_start AND @test_end
        AND sample.label_valid_5d
        AND sample.fwd_xs_ret_5d IS NOT NULL
    ),
    ranked AS (
      SELECT
        split_tag,
        predict_date,
        sec_code,
        score,
        fwd_xs_ret_5d,
        fwd_ret_5d,
        PERCENT_RANK() OVER (PARTITION BY split_tag, predict_date ORDER BY score) AS score_rank,
        PERCENT_RANK() OVER (PARTITION BY split_tag, predict_date ORDER BY fwd_xs_ret_5d) AS return_rank,
        NTILE(5) OVER (PARTITION BY split_tag, predict_date ORDER BY score) AS score_bucket_q5
      FROM scored
      WHERE split_tag IN ('valid', 'test')
    ),
    daily_ic AS (
      SELECT
        split_tag,
        predict_date,
        COUNT(*) AS sample_count,
        CORR(score_rank, return_rank) AS rank_ic
      FROM ranked
      GROUP BY split_tag, predict_date
      HAVING sample_count >= 30
    ),
    ic_summary AS (
      SELECT
        split_tag,
        COUNT(*) AS rank_ic_day_count,
        AVG(rank_ic) AS rank_ic_mean,
        STDDEV_SAMP(rank_ic) AS rank_ic_std,
        SAFE_DIVIDE(AVG(rank_ic), SAFE_DIVIDE(STDDEV_SAMP(rank_ic), SQRT(COUNT(*)))) AS rank_ic_t_stat
      FROM daily_ic
      GROUP BY split_tag
    ),
    bucket_daily AS (
      SELECT
        split_tag,
        predict_date,
        score_bucket_q5,
        AVG(fwd_xs_ret_5d) AS avg_fwd_xs_ret_5d,
        AVG(fwd_ret_5d) AS avg_fwd_ret_5d,
        COUNT(*) AS n
      FROM ranked
      GROUP BY split_tag, predict_date, score_bucket_q5
    ),
    bucket_summary AS (
      SELECT
        split_tag,
        score_bucket_q5,
        AVG(avg_fwd_xs_ret_5d) AS avg_fwd_xs_ret_5d,
        AVG(avg_fwd_ret_5d) AS avg_fwd_ret_5d,
        AVG(n) AS avg_bucket_count
      FROM bucket_daily
      GROUP BY split_tag, score_bucket_q5
    ),
    tmb AS (
      SELECT
        top.split_tag,
        top.avg_fwd_xs_ret_5d - bottom.avg_fwd_xs_ret_5d AS top_minus_bottom_fwd_ret_mean,
        top.avg_fwd_xs_ret_5d AS actual_long_side_fwd_xs_ret_mean,
        bottom.avg_fwd_xs_ret_5d AS opposite_side_fwd_xs_ret_mean
      FROM bucket_summary AS top
      JOIN bucket_summary AS bottom
        ON top.split_tag = bottom.split_tag
       AND top.score_bucket_q5 = 5
       AND bottom.score_bucket_q5 = 1
    )
    SELECT
      ic.split_tag,
      ic.rank_ic_day_count,
      ic.rank_ic_mean,
      ic.rank_ic_std,
      ic.rank_ic_t_stat,
      tmb.top_minus_bottom_fwd_ret_mean,
      tmb.actual_long_side_fwd_xs_ret_mean,
      tmb.opposite_side_fwd_xs_ret_mean
    FROM ic_summary AS ic
    LEFT JOIN tmb USING (split_tag)
    ORDER BY split_tag
    """
    frame = query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("prediction_run_id", "STRING", args.prediction_run_id),
            bigquery.ScalarQueryParameter("model_id", "STRING", model_meta["model_id"]),
            bigquery.ScalarQueryParameter("valid_start", "DATE", args.valid_start_date),
            bigquery.ScalarQueryParameter("valid_end", "DATE", args.valid_end_date),
            bigquery.ScalarQueryParameter("test_start", "DATE", args.test_start_date),
            bigquery.ScalarQueryParameter("test_end", "DATE", args.test_end_date),
            bigquery.ScalarQueryParameter("label_version", "STRING", args.label_version),
        ],
        labels={"component": "strategy1", "step": "accept_v2_signal"},
    )
    records = {row["split_tag"]: normalize_record(row) for row in frame.to_dict("records")}
    out: dict[str, Any] = {}
    for split in ("valid", "test"):
        item = records.get(split, {})
        for key, value in item.items():
            if key != "split_tag":
                out[f"{split}_{key}"] = value

    # The summary query above is the gate input. Bucket details are fetched with a
    # compact companion query to keep the artifact audit human-readable.
    bucket_detail_sql = f"""
    WITH scored AS (
      SELECT
        CASE
          WHEN pred.predict_date BETWEEN @valid_start AND @valid_end THEN 'valid'
          WHEN pred.predict_date BETWEEN @test_start AND @test_end THEN 'test'
          ELSE 'other'
        END AS split_tag,
        pred.predict_date,
        pred.sec_code,
        pred.score,
        sample.fwd_xs_ret_5d,
        sample.fwd_ret_5d
      FROM `{args.project}.ashare_ads.ads_model_prediction_daily` AS pred
      JOIN `{args.project}.ashare_dws.dws_stock_sample_daily` AS sample
        ON sample.trade_date = pred.predict_date
       AND sample.sec_code = pred.sec_code
       AND sample.trade_date BETWEEN @valid_start AND @test_end
       AND sample.label_version = @label_version
      WHERE pred.run_id = @prediction_run_id
        AND pred.model_id = @model_id
        AND pred.predict_date BETWEEN @valid_start AND @test_end
        AND sample.label_valid_5d
        AND sample.fwd_xs_ret_5d IS NOT NULL
    ),
    bucketed AS (
      SELECT
        split_tag,
        predict_date,
        NTILE(5) OVER (PARTITION BY split_tag, predict_date ORDER BY score) AS score_bucket_q5,
        fwd_xs_ret_5d,
        fwd_ret_5d
      FROM scored
      WHERE split_tag IN ('valid', 'test')
    )
    SELECT
      split_tag,
      score_bucket_q5,
      AVG(fwd_xs_ret_5d) AS avg_fwd_xs_ret_5d,
      AVG(fwd_ret_5d) AS avg_fwd_ret_5d,
      COUNT(*) AS row_count
    FROM bucketed
    GROUP BY split_tag, score_bucket_q5
    ORDER BY split_tag, score_bucket_q5
    """
    bucket_frame = query_dataframe(
        client,
        bucket_detail_sql,
        [
            bigquery.ScalarQueryParameter("prediction_run_id", "STRING", args.prediction_run_id),
            bigquery.ScalarQueryParameter("model_id", "STRING", model_meta["model_id"]),
            bigquery.ScalarQueryParameter("valid_start", "DATE", args.valid_start_date),
            bigquery.ScalarQueryParameter("valid_end", "DATE", args.valid_end_date),
            bigquery.ScalarQueryParameter("test_start", "DATE", args.test_start_date),
            bigquery.ScalarQueryParameter("test_end", "DATE", args.test_end_date),
            bigquery.ScalarQueryParameter("label_version", "STRING", args.label_version),
        ],
        labels={"component": "strategy1", "step": "accept_v2_bucket"},
    )
    return out, normalize_frame(bucket_frame)


def fetch_portfolio_feasibility_inputs(
    client: bigquery.Client,
    args: argparse.Namespace,
    contract: dict[str, Any],
    model_meta: dict[str, Any],
) -> pd.DataFrame:
    targets = [int(row["target_holdings"]) for row in portfolio_candidates(contract)]
    max_target = max(targets)
    price_end = (pd.Timestamp(args.full_end_date) + pd.Timedelta(days=10)).date().isoformat()
    sql = f"""
    WITH target_config AS (
      SELECT
        CAST(JSON_VALUE(item, '$.target_holdings') AS INT64) AS target_holdings,
        JSON_VALUE(item, '$.portfolio_candidate_role') AS portfolio_candidate_role,
        SAFE_CAST(JSON_VALUE(item, '$.target_weight') AS FLOAT64) AS target_weight,
        SAFE_CAST(JSON_VALUE(item, '$.participates_in_accepted_gate') AS BOOL) AS participates_in_accepted_gate,
        SAFE_CAST(JSON_VALUE(item, '$.applies_full_investment_cash_gate') AS BOOL) AS applies_full_investment_cash_gate
      FROM UNNEST(JSON_EXTRACT_ARRAY(@target_config_json)) AS item
    ),
    rebalance_dates AS (
      SELECT DISTINCT cand.rebalance_date
      FROM `{args.project}.ashare_ads.ads_stock_candidate_daily` AS cand
      WHERE cand.strategy_id = @strategy_id
        AND cand.run_id = @reference_run_id
        AND cand.rebalance_date BETWEEN @full_start AND @full_end
        AND cand.rank_raw BETWEEN 1 AND @max_target
    ),
    exec_dates AS (
      SELECT
        r.rebalance_date,
        MIN(cal.cal_date) AS execution_date
      FROM rebalance_dates AS r
      JOIN `{args.project}.ashare_dim.dim_trade_calendar` AS cal
        ON cal.exchange = 'SSE'
       AND cal.is_open = 1
       AND cal.cal_date > r.rebalance_date
      GROUP BY r.rebalance_date
    ),
    top_candidates AS (
      SELECT
        cand.rebalance_date,
        cand.sec_code,
        cand.model_id,
        cand.score,
        cand.rank_raw,
        cand.rank_pct
      FROM `{args.project}.ashare_ads.ads_stock_candidate_daily` AS cand
      WHERE cand.strategy_id = @strategy_id
        AND cand.run_id = @reference_run_id
        AND cand.rebalance_date BETWEEN @full_start AND @full_end
        AND cand.rank_raw BETWEEN 1 AND @max_target
    ),
    expanded AS (
      SELECT
        cfg.*,
        cand.rebalance_date,
        exec.execution_date,
        cand.sec_code,
        cand.model_id,
        cand.score,
        cand.rank_raw,
        cand.rank_pct
      FROM top_candidates AS cand
      JOIN target_config AS cfg
        ON cand.rank_raw <= cfg.target_holdings
      JOIN exec_dates AS exec USING (rebalance_date)
    ),
    priced AS (
      SELECT
        expanded.*,
        price.open AS execution_open,
        price.close AS execution_close,
        price.can_buy_open,
        price.can_sell_open,
        price.is_one_word_limit_up,
        price.is_one_word_limit_down,
        feature.total_mv_cny,
        feature.circ_mv_cny,
        feature.vol_20d,
        feature.drawdown_20d,
        feature.ret_5d,
        feature.ret_20d,
        feature.amount_ma20_cny,
        stock.sec_name,
        stock.board,
        stock.industry,
        sample.fwd_ret_5d,
        sample.fwd_xs_ret_5d
      FROM expanded
      LEFT JOIN `{args.project}.ashare_dwd.dwd_stock_eod_price` AS price
        ON price.trade_date = expanded.execution_date
       AND price.sec_code = expanded.sec_code
       AND price.trade_date BETWEEN @full_start AND @price_end
      LEFT JOIN `{args.project}.ashare_dws.dws_stock_feature_daily_v0` AS feature
        ON feature.trade_date = expanded.rebalance_date
       AND feature.sec_code = expanded.sec_code
       AND feature.feature_version = @feature_version
       AND feature.trade_date BETWEEN @full_start AND @full_end
      LEFT JOIN `{args.project}.ashare_dws.dws_stock_sample_daily` AS sample
        ON sample.trade_date = expanded.rebalance_date
       AND sample.sec_code = expanded.sec_code
       AND sample.label_version = @label_version
       AND sample.trade_date BETWEEN @full_start AND @full_end
      LEFT JOIN `{args.project}.ashare_dim.dim_stock` AS stock
        ON stock.sec_code = expanded.sec_code
    ),
    with_quantiles AS (
      SELECT
        priced.*,
        PERCENTILE_CONT(execution_open, 0.25) OVER (
          PARTITION BY target_holdings, rebalance_date
        ) AS selected_price_p25,
        PERCENTILE_CONT(execution_open, 0.75) OVER (
          PARTITION BY target_holdings, rebalance_date
        ) AS selected_price_p75
      FROM priced
    )
    SELECT *
    FROM with_quantiles
    ORDER BY target_holdings, rebalance_date, rank_raw
    """
    frame = query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("strategy_id", "STRING", args.strategy_id),
            bigquery.ScalarQueryParameter("reference_run_id", "STRING", args.reference_run_id),
            bigquery.ScalarQueryParameter("full_start", "DATE", args.full_start_date),
            bigquery.ScalarQueryParameter("full_end", "DATE", args.full_end_date),
            bigquery.ScalarQueryParameter("price_end", "DATE", price_end),
            bigquery.ScalarQueryParameter("max_target", "INT64", max_target),
            bigquery.ScalarQueryParameter("target_config_json", "STRING", json.dumps(portfolio_candidates(contract), ensure_ascii=False)),
            bigquery.ScalarQueryParameter("feature_version", "STRING", args.feature_version),
            bigquery.ScalarQueryParameter("label_version", "STRING", args.label_version),
        ],
        labels={"component": "strategy1", "step": "accept_v2_feas"},
    )
    if frame.empty:
        raise RuntimeError(f"no candidate rows found for reference_run_id={args.reference_run_id}")
    _ = model_meta
    return normalize_frame(frame)


def build_portfolio_feasibility(
    inputs: pd.DataFrame,
    contract: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    cfg = contract.get("portfolio_candidates") or {}
    implementation = contract.get("implementation_gate") or {}
    initial_capital = float(cfg.get("initial_capital_cny", 100000.0))
    lot_size = int(cfg.get("lot_size", 100))

    df = inputs.copy()
    df["execution_open"] = pd.to_numeric(df["execution_open"], errors="coerce")
    df["target_weight"] = pd.to_numeric(df["target_weight"], errors="coerce")
    df["target_cash_cny"] = initial_capital * df["target_weight"]
    df["raw_shares"] = df["target_cash_cny"] / df["execution_open"]
    df["lot_shares"] = (df["raw_shares"].fillna(0).floordiv(lot_size) * lot_size).astype("int64")
    df["can_buy_open_bool"] = df["can_buy_open"].fillna(False).astype(bool)
    df["bought"] = df["can_buy_open_bool"] & df["execution_open"].notna() & (df["lot_shares"] >= lot_size)
    df["filled_amount_cny"] = df["lot_shares"] * df["execution_open"]
    df.loc[~df["bought"], "filled_amount_cny"] = 0.0
    df["filled_weight"] = df["filled_amount_cny"] / initial_capital
    df["planned_weight"] = df["target_weight"]
    df["skip_reason"] = None
    df.loc[df["execution_open"].isna(), "skip_reason"] = "missing_execution_open"
    df.loc[df["skip_reason"].isna() & ~df["can_buy_open_bool"], "skip_reason"] = "not_can_buy_open"
    df.loc[df["skip_reason"].isna() & (df["lot_shares"] < lot_size), "skip_reason"] = "below_one_lot"
    df.loc[df["bought"], "skip_reason"] = None
    df["fwd_ret_5d"] = pd.to_numeric(df["fwd_ret_5d"], errors="coerce").fillna(0.0)
    df["weighted_fwd_return"] = df["filled_weight"] * df["fwd_ret_5d"]
    df["selected_low_price"] = df["execution_open"] <= pd.to_numeric(df["selected_price_p25"], errors="coerce")
    df["selected_high_price"] = df["execution_open"] >= pd.to_numeric(df["selected_price_p75"], errors="coerce")

    daily = []
    skipped = []
    low_price = []
    actual_hold_dist = []
    cash_dist = []
    exposure_rows = []
    for (target, day), group in df.groupby(["target_holdings", "rebalance_date"], dropna=False):
        selected_count = int(len(group))
        bought_count = int(group["bought"].sum())
        skipped_count = selected_count - bought_count
        gross_exposure = float(group["filled_weight"].sum())
        cash_weight = float(1.0 - gross_exposure)
        max_weight = float(group["filled_weight"].max() if not group.empty else 0.0)
        selected_price_median = safe_float(group["execution_open"].median())
        bought_prices = group.loc[group["bought"], "execution_open"]
        bought_price_median = safe_float(bought_prices.median())
        selected_price_p25 = safe_float(group["execution_open"].quantile(0.25))
        bought_price_p25 = safe_float(bought_prices.quantile(0.25))
        high_group = group[group["selected_high_price"].fillna(False)]
        high_skip_rate = float((~high_group["bought"]).mean()) if not high_group.empty else 0.0
        selected_low_weight = float(group.loc[group["selected_low_price"].fillna(False), "planned_weight"].sum())
        bought_low_weight = float(group.loc[group["selected_low_price"].fillna(False), "filled_weight"].sum())
        low_active = bought_low_weight - selected_low_weight
        return_contrib_low = float(group.loc[group["selected_low_price"].fillna(False), "weighted_fwd_return"].sum())
        daily_return_estimate = float(group["weighted_fwd_return"].sum())
        row = {
            "target_holdings": int(target),
            "rebalance_date": str(day),
            "execution_date": str(group["execution_date"].iloc[0]),
            "portfolio_candidate_role": group["portfolio_candidate_role"].iloc[0],
            "selected_count": selected_count,
            "actual_holdings": bought_count,
            "actual_holdings_ratio": divide(bought_count, int(target)),
            "skipped_buy_count": skipped_count,
            "skipped_buy_rate": divide(skipped_count, selected_count),
            "gross_exposure": gross_exposure,
            "cash_weight": cash_weight,
            "negative_cash": cash_weight < -1e-8,
            "max_single_weight_realized": max_weight,
            "selected_price_median": selected_price_median,
            "bought_price_median": bought_price_median,
            "selected_price_p25": selected_price_p25,
            "bought_price_p25": bought_price_p25,
            "bought_vs_selected_price_median_ratio": divide(bought_price_median, selected_price_median),
            "selected_high_price_skip_rate": high_skip_rate,
            "selected_low_price_weight": selected_low_weight,
            "bought_low_price_weight": bought_low_weight,
            "low_price_active_weight_from_lot": low_active,
            "return_contribution_low_price_bucket": return_contrib_low,
            "estimated_rebalance_fwd_return": daily_return_estimate,
        }
        daily.append(row)
        actual_hold_dist.append({
            "target_holdings": int(target),
            "rebalance_date": str(day),
            "actual_holdings": bought_count,
            "target_holdings_ratio": divide(bought_count, int(target)),
        })
        cash_dist.append({
            "target_holdings": int(target),
            "rebalance_date": str(day),
            "cash_weight": cash_weight,
            "gross_exposure": gross_exposure,
        })
        low_price.append({key: row[key] for key in [
            "target_holdings", "rebalance_date", "selected_price_median", "bought_price_median",
            "selected_price_p25", "bought_price_p25", "bought_vs_selected_price_median_ratio",
            "selected_high_price_skip_rate", "selected_low_price_weight", "bought_low_price_weight",
            "low_price_active_weight_from_lot", "return_contribution_low_price_bucket",
        ]})
        exposure_rows.append({
            "target_holdings": int(target),
            "rebalance_date": str(day),
            "gross_exposure": gross_exposure,
            "estimated_rebalance_fwd_return": daily_return_estimate,
            "return_on_deployed_capital": divide(daily_return_estimate, gross_exposure),
            "cash_drag_return": subtract_or_none(daily_return_estimate, divide(daily_return_estimate, gross_exposure)),
            "exposure_adjusted_return": divide(daily_return_estimate, gross_exposure),
        })
        for _, item in group.loc[~group["bought"]].iterrows():
            skipped.append({
                "target_holdings": int(target),
                "rebalance_date": str(day),
                "execution_date": str(item.get("execution_date")),
                "sec_code": item.get("sec_code"),
                "sec_name": item.get("sec_name"),
                "rank_raw": safe_int(item.get("rank_raw")),
                "score": safe_float(item.get("score")),
                "execution_open": safe_float(item.get("execution_open")),
                "planned_weight": safe_float(item.get("planned_weight")),
                "raw_shares": safe_float(item.get("raw_shares")),
                "lot_shares": safe_int(item.get("lot_shares")),
                "can_buy_open": bool(item.get("can_buy_open_bool")),
                "skip_reason": item.get("skip_reason"),
            })

    daily_df = pd.DataFrame(daily)
    summary_rows = []
    for target, group in daily_df.groupby("target_holdings", dropna=False):
        role = group["portfolio_candidate_role"].iloc[0]
        daily_returns = pd.to_numeric(group["estimated_rebalance_fwd_return"], errors="coerce").fillna(0.0)
        total_return_est = compound_returns(daily_returns)
        gross_mean = safe_float(group["gross_exposure"].mean())
        row = {
            "target_holdings": int(target),
            "portfolio_candidate_role": role,
            "rebalance_day_count": int(len(group)),
            "actual_holdings_median": safe_float(group["actual_holdings"].median()),
            "actual_holdings_ratio_median": safe_float(group["actual_holdings_ratio"].median()),
            "avg_cash_weight": safe_float(group["cash_weight"].mean()),
            "max_cash_weight": safe_float(group["cash_weight"].max()),
            "skipped_buy_rate": safe_float(group["skipped_buy_rate"].mean()),
            "negative_cash_days": int(group["negative_cash"].sum()),
            "max_single_weight_realized": safe_float(group["max_single_weight_realized"].max()),
            "gross_exposure_mean": gross_mean,
            "gross_exposure_max": safe_float(group["gross_exposure"].max()),
            "estimated_account_total_return": total_return_est,
            "return_on_deployed_capital": divide(total_return_est, gross_mean),
            "cash_drag_return": subtract_or_none(total_return_est, divide(total_return_est, gross_mean)),
            "exposure_adjusted_return": divide(total_return_est, gross_mean),
            "exposure_adjusted_excess_return": None,
            "bought_vs_selected_price_median_ratio": safe_float(group["bought_vs_selected_price_median_ratio"].median()),
            "low_price_active_weight_from_lot": safe_float(group["low_price_active_weight_from_lot"].mean()),
            "return_contribution_low_price_bucket": safe_float(group["return_contribution_low_price_bucket"].sum()),
        }
        row["implementation_gate_status"] = implementation_gate_status(row, implementation)
        row["implementation_gate_reasons"] = ";".join(implementation_gate_reasons(row, implementation))
        summary_rows.append(row)

    by_target = pd.DataFrame(summary_rows).sort_values("target_holdings")
    skipped_df = pd.DataFrame(skipped)
    return {
        "summary": {
            "initial_capital_cny": initial_capital,
            "lot_size": lot_size,
            "target_holdings": [int(row["target_holdings"]) for row in portfolio_candidates(contract)],
            "reference_run_id": args.reference_run_id,
            "full_start_date": args.full_start_date,
            "full_end_date": args.full_end_date,
        },
        "daily": normalize_frame(daily_df),
        "by_target_holdings": normalize_frame(by_target),
        "skipped_orders": normalize_frame(skipped_df),
        "actual_holdings_distribution": normalize_frame(pd.DataFrame(actual_hold_dist)),
        "cash_weight_distribution": normalize_frame(pd.DataFrame(cash_dist)),
        "low_price_tilt": normalize_frame(pd.DataFrame(low_price)),
        "exposure_adjusted_return": normalize_frame(pd.DataFrame(exposure_rows)),
    }


def fetch_eligible_benchmark(
    client: bigquery.Client,
    args: argparse.Namespace,
    contract: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    price_end = (pd.Timestamp(args.full_end_date) + pd.Timedelta(days=10)).date().isoformat()
    cost_rate = args.eligible_benchmark_cost_bps / 10000.0
    sql = f"""
    WITH rebalance_dates AS (
      SELECT DISTINCT cand.rebalance_date
      FROM `{args.project}.ashare_ads.ads_stock_candidate_daily` AS cand
      WHERE cand.strategy_id = @strategy_id
        AND cand.run_id = @reference_run_id
        AND cand.rebalance_date BETWEEN @full_start AND @full_end
        AND cand.rank_raw IS NOT NULL
    ),
    exec_dates AS (
      SELECT
        r.rebalance_date,
        MIN(cal.cal_date) AS execution_date
      FROM rebalance_dates AS r
      JOIN `{args.project}.ashare_dim.dim_trade_calendar` AS cal
        ON cal.exchange = 'SSE'
       AND cal.is_open = 1
       AND cal.cal_date > r.rebalance_date
      GROUP BY r.rebalance_date
    ),
    pool AS (
      SELECT
        cand.rebalance_date,
        exec.execution_date,
        cand.sec_code,
        cand.rank_raw,
        cand.score,
        sample.fwd_ret_5d,
        price.can_buy_open,
        price.can_sell_open
      FROM `{args.project}.ashare_ads.ads_stock_candidate_daily` AS cand
      JOIN exec_dates AS exec USING (rebalance_date)
      JOIN `{args.project}.ashare_dws.dws_stock_sample_daily` AS sample
        ON sample.trade_date = cand.rebalance_date
       AND sample.sec_code = cand.sec_code
       AND sample.label_version = @label_version
       AND sample.trade_date BETWEEN @full_start AND @full_end
      LEFT JOIN `{args.project}.ashare_dwd.dwd_stock_eod_price` AS price
        ON price.trade_date = exec.execution_date
       AND price.sec_code = cand.sec_code
       AND price.trade_date BETWEEN @full_start AND @price_end
      WHERE cand.strategy_id = @strategy_id
        AND cand.run_id = @reference_run_id
        AND cand.rebalance_date BETWEEN @full_start AND @full_end
        AND cand.rank_raw IS NOT NULL
        AND sample.fwd_ret_5d IS NOT NULL
    ),
    daily AS (
      SELECT
        rebalance_date,
        execution_date,
        COUNT(*) AS signal_constituent_count,
        AVG(fwd_ret_5d) AS eligible_signal_pool_return,
        COUNTIF(COALESCE(can_buy_open, FALSE) AND COALESCE(can_sell_open, FALSE)) AS executable_constituent_count,
        AVG(IF(COALESCE(can_buy_open, FALSE) AND COALESCE(can_sell_open, FALSE), fwd_ret_5d, NULL))
          AS eligible_executable_return_no_cost
      FROM pool
      GROUP BY rebalance_date, execution_date
    )
    SELECT
      rebalance_date,
      execution_date,
      signal_constituent_count,
      executable_constituent_count,
      eligible_signal_pool_return,
      eligible_executable_return_no_cost,
      eligible_executable_return_no_cost - @cost_rate AS eligible_executable_return_costed
    FROM daily
    ORDER BY rebalance_date
    """
    nav = query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("strategy_id", "STRING", args.strategy_id),
            bigquery.ScalarQueryParameter("reference_run_id", "STRING", args.reference_run_id),
            bigquery.ScalarQueryParameter("full_start", "DATE", args.full_start_date),
            bigquery.ScalarQueryParameter("full_end", "DATE", args.full_end_date),
            bigquery.ScalarQueryParameter("price_end", "DATE", price_end),
            bigquery.ScalarQueryParameter("label_version", "STRING", args.label_version),
            bigquery.ScalarQueryParameter("cost_rate", "FLOAT64", cost_rate),
        ],
        labels={"component": "strategy1", "step": "accept_v2_bench"},
    )
    nav = normalize_frame(nav)
    if not nav.empty:
        for col in ["eligible_signal_pool_return", "eligible_executable_return_no_cost", "eligible_executable_return_costed"]:
            nav[col] = pd.to_numeric(nav[col], errors="coerce").fillna(0.0)
            nav[col.replace("_return", "_nav")] = (1.0 + nav[col]).cumprod()
    constituents_sql = f"""
    WITH rebalance_dates AS (
      SELECT DISTINCT cand.rebalance_date
      FROM `{args.project}.ashare_ads.ads_stock_candidate_daily` AS cand
      WHERE cand.strategy_id = @strategy_id
        AND cand.run_id = @reference_run_id
        AND cand.rebalance_date BETWEEN @full_start AND @full_end
        AND cand.rank_raw IS NOT NULL
    ),
    sample_days AS (
      SELECT rebalance_date
      FROM rebalance_dates
      QUALIFY ROW_NUMBER() OVER (ORDER BY rebalance_date DESC) <= 5
    )
    SELECT
      cand.rebalance_date,
      cand.sec_code,
      cand.rank_raw,
      cand.score
    FROM `{args.project}.ashare_ads.ads_stock_candidate_daily` AS cand
    JOIN sample_days USING (rebalance_date)
    WHERE cand.strategy_id = @strategy_id
      AND cand.run_id = @reference_run_id
      AND cand.rebalance_date BETWEEN @full_start AND @full_end
      AND cand.rank_raw IS NOT NULL
    ORDER BY cand.rebalance_date DESC, cand.rank_raw
    LIMIT 5000
    """
    constituents = query_dataframe(
        client,
        constituents_sql,
        [
            bigquery.ScalarQueryParameter("strategy_id", "STRING", args.strategy_id),
            bigquery.ScalarQueryParameter("reference_run_id", "STRING", args.reference_run_id),
            bigquery.ScalarQueryParameter("full_start", "DATE", args.full_start_date),
            bigquery.ScalarQueryParameter("full_end", "DATE", args.full_end_date),
        ],
        labels={"component": "strategy1", "step": "accept_v2_bench_const"},
    )
    constituents = normalize_frame(constituents)
    summary = {
        "eligible_benchmark_version": "eligible_universe_benchmark_v1",
        "cost_bps": args.eligible_benchmark_cost_bps,
        "rebalance_day_count": int(len(nav)),
        "eligible_signal_pool_total_return": compound_returns(nav.get("eligible_signal_pool_return", [])),
        "eligible_executable_total_return_no_cost": compound_returns(nav.get("eligible_executable_return_no_cost", [])),
        "eligible_executable_total_return_costed": compound_returns(nav.get("eligible_executable_return_costed", [])),
        "eligible_signal_pool_avg_constituent_count": safe_float(nav.get("signal_constituent_count", pd.Series(dtype=float)).mean()) if not nav.empty else None,
        "eligible_executable_avg_constituent_count": safe_float(nav.get("executable_constituent_count", pd.Series(dtype=float)).mean()) if not nav.empty else None,
    }
    _ = contract
    return nav, summary, constituents


def fetch_style_exposure(client: bigquery.Client, args: argparse.Namespace) -> pd.DataFrame:
    sql = f"""
    WITH positions AS (
      SELECT
        pos.trade_date,
        pos.sec_code,
        pos.weight
      FROM `{args.project}.ashare_ads.ads_backtest_position_daily` AS pos
      WHERE pos.backtest_id = @backtest_id
        AND pos.trade_date BETWEEN @full_start AND @full_end
        AND pos.weight > 0
    )
    SELECT
      DATE_TRUNC(pos.trade_date, MONTH) AS month,
      COALESCE(stock.board, 'unknown') AS board,
      COALESCE(stock.industry, 'unknown') AS industry_tushare_raw,
      SUM(pos.weight) AS position_weight,
      AVG(feature.total_mv_cny) AS avg_total_mv_cny,
      AVG(feature.circ_mv_cny) AS avg_circ_mv_cny,
      AVG(feature.vol_20d) AS avg_vol_20d,
      AVG(feature.drawdown_20d) AS avg_drawdown_20d,
      AVG(feature.ret_5d) AS avg_ret_5d,
      AVG(feature.ret_20d) AS avg_ret_20d,
      AVG(feature.amount_ma20_cny) AS avg_amount_ma20_cny,
      COUNT(DISTINCT pos.sec_code) AS held_stock_count
    FROM positions AS pos
    LEFT JOIN `{args.project}.ashare_dws.dws_stock_feature_daily_v0` AS feature
      ON feature.trade_date = pos.trade_date
     AND feature.sec_code = pos.sec_code
     AND feature.feature_version = @feature_version
     AND feature.trade_date BETWEEN @full_start AND @full_end
    LEFT JOIN `{args.project}.ashare_dim.dim_stock` AS stock
      ON stock.sec_code = pos.sec_code
    GROUP BY month, board, industry_tushare_raw
    ORDER BY month, position_weight DESC
    """
    return normalize_frame(query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("backtest_id", "STRING", args.reference_backtest_id),
            bigquery.ScalarQueryParameter("full_start", "DATE", args.full_start_date),
            bigquery.ScalarQueryParameter("full_end", "DATE", args.full_end_date),
            bigquery.ScalarQueryParameter("feature_version", "STRING", args.feature_version),
        ],
        labels={"component": "strategy1", "step": "accept_v2_style"},
    ))


def build_score_orientation_audit(
    model_meta: dict[str, Any],
    signal_metrics: dict[str, Any],
    bucket_lift: pd.DataFrame,
) -> dict[str, Any]:
    test_rank_ic = safe_float(signal_metrics.get("test_rank_ic_mean"))
    test_long_side = safe_float(signal_metrics.get("test_actual_long_side_fwd_xs_ret_mean"))
    valid_rank_ic = safe_float(signal_metrics.get("valid_rank_ic_mean"))
    valid_long_side = safe_float(signal_metrics.get("valid_actual_long_side_fwd_xs_ret_mean"))
    mismatch = (
        (math.isfinite(test_rank_ic) and test_rank_ic > 0 and math.isfinite(test_long_side) and test_long_side < 0)
        or (math.isfinite(valid_rank_ic) and valid_rank_ic > 0 and math.isfinite(valid_long_side) and valid_long_side < 0)
    )
    return {
        "raw_score_field": "raw_score",
        "oriented_score_field": "score",
        "score_orientation": model_meta.get("score_orientation"),
        "higher_oriented_score_is_better": True,
        "actual_long_side_bucket": "Q5",
        "top_minus_bottom_definition": "Q5 mean fwd_xs_ret_5d minus Q1 mean fwd_xs_ret_5d using oriented score",
        "rank_ic_score_field": "score",
        "rank_ic_forward_return_field": "fwd_xs_ret_5d",
        "bucket_return_definition": "NTILE(5) by oriented score per prediction date; high score is Q5",
        "selected_top_n_matches_bucket_side": True,
        "signal_top_tail_mismatch": bool(mismatch),
        "valid_rank_ic_mean": signal_metrics.get("valid_rank_ic_mean"),
        "test_rank_ic_mean": signal_metrics.get("test_rank_ic_mean"),
        "valid_actual_long_side_fwd_xs_ret_mean": signal_metrics.get("valid_actual_long_side_fwd_xs_ret_mean"),
        "test_actual_long_side_fwd_xs_ret_mean": signal_metrics.get("test_actual_long_side_fwd_xs_ret_mean"),
        "bucket_count": 5,
        "bucket_lift_rows": len(bucket_lift),
    }


def decide_acceptance_v2(
    *,
    contract: dict[str, Any],
    reference_metrics: dict[str, Any],
    signal_metrics: dict[str, Any],
    portfolio_summary: pd.DataFrame,
    eligible_summary: dict[str, Any],
    score_audit: dict[str, Any],
) -> tuple[str, list[str]]:
    thresholds = contract.get("thresholds") or {}
    required = contract.get("required") or {}
    hard: list[str] = []
    evidence: list[str] = []
    accepted_missing: list[str] = []

    full_excess = safe_float(reference_metrics.get("full_period_excess_return_vs_primary_benchmark"))
    full_total = safe_float(reference_metrics.get("full_period_total_return"))
    full_ir = safe_float(reference_metrics.get("full_period_information_ratio"))
    full_dd = safe_float(reference_metrics.get("full_period_max_drawdown"))
    rel_dd = safe_float(reference_metrics.get("full_period_relative_max_drawdown_vs_primary_benchmark"))
    final_excess = safe_float(reference_metrics.get("final_holdout_excess_return_vs_primary_benchmark"))
    eligible_return = safe_float(eligible_summary.get("eligible_executable_total_return_costed"))
    eligible_excess = full_total - eligible_return if math.isfinite(full_total) and math.isfinite(eligible_return) else math.nan
    eligible_ir = math.nan

    hard_checks = [
        ("full_period_excess_return_vs_primary_benchmark", full_excess, thresholds.get("hard_reject_full_period_excess_return_vs_000852", -0.03), "le"),
        ("full_period_information_ratio", full_ir, thresholds.get("hard_reject_full_period_information_ratio", 0.0), "lt"),
        ("full_period_excess_return_vs_eligible_executable", eligible_excess, thresholds.get("hard_reject_full_period_excess_return_vs_eligible_executable", -0.03), "le"),
        ("full_period_max_drawdown", full_dd, thresholds.get("hard_reject_full_period_max_drawdown", -0.25), "lt"),
        ("full_period_relative_max_drawdown_vs_primary_benchmark", rel_dd, thresholds.get("hard_reject_full_period_relative_max_drawdown_vs_000852", -0.25), "lt"),
        ("final_holdout_excess_return_vs_primary_benchmark", final_excess, thresholds.get("hard_reject_final_holdout_excess_return_vs_000852", -0.10), "le"),
    ]
    for name, actual, threshold, op in hard_checks:
        if not math.isfinite(actual):
            continue
        if (op == "le" and actual <= float(threshold)) or (op == "lt" and actual < float(threshold)):
            hard.append(f"{name}{'<=' if op == 'le' else '<'}{threshold}")
    if not score_audit.get("selected_top_n_matches_bucket_side"):
        hard.append("selected_top_n_matches_bucket_side=false")

    required_ledger_version = required.get("required_ledger_version")
    if required_ledger_version and reference_metrics.get("ledger_version") != required_ledger_version:
        evidence.append(
            f"ledger_version!={required_ledger_version}"
            f"(actual={reference_metrics.get('ledger_version') or 'missing'})"
        )

    viable = portfolio_summary[
        portfolio_summary.get("portfolio_candidate_role", pd.Series(dtype=str)).ne("diagnostic_cash_control")
    ]
    if not viable.empty and not viable["implementation_gate_status"].eq("passed").any():
        evidence.append("no_20_30_40_candidate_passed_implementation_gate")

    accepted_checks = [
        ("full_period_excess_return_vs_primary_benchmark", full_excess, thresholds.get("min_full_period_excess_return_vs_000852", 0.03), "gt"),
        ("full_period_information_ratio", full_ir, thresholds.get("min_full_period_information_ratio", 0.25), "gt"),
        ("full_period_excess_return_vs_eligible_executable", eligible_excess, thresholds.get("min_full_period_excess_return_vs_eligible_executable", 0.0), "gt"),
        ("full_period_information_ratio_vs_eligible_executable", eligible_ir, thresholds.get("min_full_period_information_ratio_vs_eligible_executable", 0.0), "gt"),
        ("full_period_max_drawdown", full_dd, thresholds.get("min_full_period_max_drawdown", -0.18), "ge"),
        ("full_period_relative_max_drawdown_vs_primary_benchmark", rel_dd, thresholds.get("min_full_period_relative_max_drawdown_vs_000852", -0.18), "ge"),
        ("final_holdout_excess_return_vs_primary_benchmark", final_excess, thresholds.get("min_final_holdout_excess_return_vs_000852", -0.05), "gt"),
        ("valid_rank_ic_mean", safe_float(signal_metrics.get("valid_rank_ic_mean")), thresholds.get("min_valid_rank_ic", 0.0), "gt"),
        ("valid_rank_ic_t_stat", safe_float(signal_metrics.get("valid_rank_ic_t_stat")), thresholds.get("min_valid_rank_ic_t_stat", 1.0), "gt"),
        ("valid_top_minus_bottom_fwd_ret_mean", safe_float(signal_metrics.get("valid_top_minus_bottom_fwd_ret_mean")), thresholds.get("min_valid_top_minus_bottom_fwd_ret", 0.0), "gt"),
        ("test_rank_ic_mean", safe_float(signal_metrics.get("test_rank_ic_mean")), thresholds.get("min_test_rank_ic", 0.0), "gt"),
        ("test_rank_ic_t_stat", safe_float(signal_metrics.get("test_rank_ic_t_stat")), thresholds.get("min_test_rank_ic_t_stat", 1.0), "gt"),
        ("test_top_minus_bottom_fwd_ret_mean", safe_float(signal_metrics.get("test_top_minus_bottom_fwd_ret_mean")), thresholds.get("min_test_top_minus_bottom_fwd_ret", 0.0), "ge"),
    ]
    for name, actual, threshold, op in accepted_checks:
        if not math.isfinite(actual):
            accepted_missing.append(f"{name}=missing")
        elif op == "gt" and not actual > float(threshold):
            accepted_missing.append(f"{name}<={threshold}")
        elif op == "ge" and not actual >= float(threshold):
            accepted_missing.append(f"{name}<{threshold}")

    if hard:
        return "rejected", hard
    if evidence or accepted_missing:
        return "needs_more_evidence", evidence + accepted_missing
    return "accepted", ["all_acceptance_gate_v2_checks_passed"]


def build_summary(
    *,
    args: argparse.Namespace,
    contract: dict[str, Any],
    model_meta: dict[str, Any],
    reference_metrics: dict[str, Any],
    signal_metrics: dict[str, Any],
    bucket_lift: pd.DataFrame,
    feasibility: dict[str, Any],
    eligible_summary: dict[str, Any],
    score_audit: dict[str, Any],
    style_exposure: pd.DataFrame,
    acceptance_status: str,
    acceptance_reasons: list[str],
    out_dir: Path,
) -> dict[str, Any]:
    return {
        "diagnosis_id": args.diagnosis_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "project": args.project,
        "region": args.region,
        "strategy_id": args.strategy_id,
        "reference_run_id": args.reference_run_id,
        "reference_backtest_id": args.reference_backtest_id,
        "ledger_version": reference_metrics.get("ledger_version"),
        "lot_size": reference_metrics.get("lot_size"),
        "min_buy_lot": reference_metrics.get("min_buy_lot"),
        "prediction_run_id": args.prediction_run_id,
        "model_id": model_meta.get("model_id"),
        "model_backend": model_meta.get("model_backend"),
        "model_family": model_meta.get("model_family"),
        "acceptance_gate_version": ACCEPTANCE_GATE_VERSION,
        "acceptance_contract_version": contract_version(contract),
        "acceptance_contract_sha256": contract_hash(contract),
        "v2_acceptance_status": acceptance_status,
        "v2_acceptance_reasons": acceptance_reasons,
        "rejection_scope": "current_top30_long_only_implementation_only",
        "signal_family_rejected": False,
        "full_start_date": args.full_start_date,
        "full_end_date": args.full_end_date,
        "valid_start_date": args.valid_start_date,
        "valid_end_date": args.valid_end_date,
        "test_start_date": args.test_start_date,
        "test_end_date": args.test_end_date,
        "final_holdout_start_date": args.final_holdout_start_date,
        "final_holdout_end_date": args.final_holdout_end_date,
        "benchmark_sec_code": args.benchmark_sec_code,
        "reference_metrics": reference_metrics,
        "signal_metrics": signal_metrics,
        "bucket_lift_row_count": int(len(bucket_lift)),
        "portfolio_feasibility_summary": table_records(feasibility["by_target_holdings"]),
        "eligible_universe_benchmark_summary": eligible_summary,
        "score_orientation_audit": score_audit,
        "style_exposure_row_count": int(len(style_exposure)),
        "local_path": str(out_dir),
        "notes": [
            "This diagnostic is read-only and does not train or alter predictions.",
            "Current v2 rejection only applies to the current top-30 long-only implementation.",
            "10/5% is diagnostic_cash_control and is excluded from accepted production baseline decisions.",
            "Industry exposure uses dim_stock.industry as a coarse raw label until PIT industry dimensions are implemented.",
        ],
    }


def write_outputs(
    *,
    out_dir: Path,
    summary: dict[str, Any],
    markdown: str,
    feasibility: dict[str, Any],
    eligible_nav: pd.DataFrame,
    eligible_summary: dict[str, Any],
    eligible_constituents: pd.DataFrame,
    score_audit: dict[str, Any],
    style_exposure: pd.DataFrame,
) -> None:
    write_json(out_dir / "acceptance_gate_v2_summary.json", summary)
    write_text(out_dir / "acceptance_gate_v2_summary.md", markdown)
    write_json(out_dir / "portfolio_feasibility.json", {
        **feasibility["summary"],
        "by_target_holdings": table_records(feasibility["by_target_holdings"]),
    })
    write_csv(out_dir / "portfolio_feasibility_daily.csv", feasibility["daily"])
    write_csv(out_dir / "portfolio_feasibility_by_target_holdings.csv", feasibility["by_target_holdings"])
    write_csv(out_dir / "lot_constraint_skipped_orders.csv", feasibility["skipped_orders"])
    write_csv(out_dir / "actual_holdings_distribution.csv", feasibility["actual_holdings_distribution"])
    write_csv(out_dir / "cash_weight_distribution.csv", feasibility["cash_weight_distribution"])
    write_csv(out_dir / "low_price_tilt_diagnostics.csv", feasibility["low_price_tilt"])
    write_csv(out_dir / "exposure_adjusted_return.csv", feasibility["exposure_adjusted_return"])
    write_csv(out_dir / "eligible_universe_benchmark_nav.csv", eligible_nav)
    write_json(out_dir / "eligible_universe_benchmark_summary.json", eligible_summary)
    write_csv(out_dir / "eligible_universe_benchmark_constituents.csv", eligible_constituents)
    write_json(out_dir / "score_orientation_audit.json", score_audit)
    write_csv(out_dir / "style_exposure_diagnostics.csv", style_exposure)


def render_markdown(summary: dict[str, Any]) -> str:
    ref = summary["reference_metrics"]
    sig = summary["signal_metrics"]
    lines = [
        "# 策略 1验收门 v2 诊断",
        "",
        f"- diagnosis_id: `{summary['diagnosis_id']}`",
        f"- acceptance_gate_version: `{summary['acceptance_gate_version']}`",
        f"- acceptance_contract_version: `{summary['acceptance_contract_version']}`",
        f"- acceptance_contract_sha256: `{summary['acceptance_contract_sha256']}`",
        f"- reference_run_id: `{summary['reference_run_id']}`",
        f"- reference_backtest_id: `{summary['reference_backtest_id']}`",
        f"- ledger_version: `{summary.get('ledger_version')}`",
        f"- v2_status: `{summary['v2_acceptance_status']}`",
        f"- rejection_scope: `{summary['rejection_scope']}`",
        "",
        "## 拒绝原因",
        "",
    ]
    lines.extend([f"- `{reason}`" for reason in summary["v2_acceptance_reasons"]])
    lines.extend([
        "",
        "## Reference Run",
        "",
        "| metric | value |",
        "|---|---:|",
        f"| full_period_total_return | {pct(ref.get('full_period_total_return'))} |",
        f"| full_period_benchmark_return | {pct(ref.get('full_period_benchmark_return'))} |",
        f"| full_period_excess_return_vs_primary_benchmark | {pct(ref.get('full_period_excess_return_vs_primary_benchmark'))} |",
        f"| full_period_excess_return_vs_eligible_executable | {pct(ref.get('full_period_excess_return_vs_eligible_executable'))} |",
        f"| full_period_information_ratio | {num(ref.get('full_period_information_ratio'))} |",
        f"| full_period_max_drawdown | {pct(ref.get('full_period_max_drawdown'))} |",
        f"| full_period_relative_max_drawdown_vs_primary_benchmark | {pct(ref.get('full_period_relative_max_drawdown_vs_primary_benchmark'))} |",
        f"| final_holdout_excess_return_vs_primary_benchmark | {pct(ref.get('final_holdout_excess_return_vs_primary_benchmark'))} |",
        "",
        "## Signal Metrics",
        "",
        "| split | RankIC | t-stat | top-minus-bottom | long-side return |",
        "|---|---:|---:|---:|---:|",
        (
            f"| valid | {num(sig.get('valid_rank_ic_mean'))} | {num(sig.get('valid_rank_ic_t_stat'))} | "
            f"{pct(sig.get('valid_top_minus_bottom_fwd_ret_mean'))} | {pct(sig.get('valid_actual_long_side_fwd_xs_ret_mean'))} |"
        ),
        (
            f"| test | {num(sig.get('test_rank_ic_mean'))} | {num(sig.get('test_rank_ic_t_stat'))} | "
            f"{pct(sig.get('test_top_minus_bottom_fwd_ret_mean'))} | {pct(sig.get('test_actual_long_side_fwd_xs_ret_mean'))} |"
        ),
        "",
        "## Portfolio Feasibility",
        "",
        "| target | role | status | actual holdings median | avg cash | skip rate | max single weight |",
        "|---:|---|---|---:|---:|---:|---:|",
    ])
    for row in summary["portfolio_feasibility_summary"]:
        lines.append(
            f"| {row.get('target_holdings')} | `{row.get('portfolio_candidate_role')}` | "
            f"`{row.get('implementation_gate_status')}` | {num(row.get('actual_holdings_median'))} | "
            f"{pct(row.get('avg_cash_weight'))} | {pct(row.get('skipped_buy_rate'))} | "
            f"{pct(row.get('max_single_weight_realized'))} |"
        )
    bench = summary["eligible_universe_benchmark_summary"]
    lines.extend([
        "",
        "## Eligible Benchmark",
        "",
        f"- signal_pool_total_return: {pct(bench.get('eligible_signal_pool_total_return'))}",
        f"- executable_total_return_costed: {pct(bench.get('eligible_executable_total_return_costed'))}",
        "",
        "## 约束",
        "",
        "- 本诊断只读 ADS/DWD/DWS，不训练模型、不改预测、不写 ADS。",
        "- 分区表查询均显式带日期过滤。",
        "- `10/5%` 仅作 diagnostic cash control，不参与 production baseline accepted 判定。",
    ])
    return "\n".join(lines) + "\n"


def implementation_gate_reasons(row: dict[str, Any] | pd.Series, gate: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    role = row.get("portfolio_candidate_role")
    target = safe_int(row.get("target_holdings"))
    if role == "diagnostic_cash_control":
        return ["diagnostic_cash_control_excluded_from_full_investment_gate"]
    if safe_float(row.get("actual_holdings_ratio_median")) < float(gate.get("actual_holdings_ratio_hard_fail", 0.60)):
        reasons.append("actual_holdings_ratio_hard_fail")
    elif safe_float(row.get("actual_holdings_ratio_median")) < float(gate.get("actual_holdings_ratio_min", 0.80)):
        reasons.append("actual_holdings_ratio_needs_more_evidence")
    if safe_float(row.get("avg_cash_weight")) > float(gate.get("avg_cash_weight_hard_fail", 0.20)):
        reasons.append("avg_cash_weight_hard_fail")
    elif safe_float(row.get("avg_cash_weight")) > float(gate.get("avg_cash_weight_max", 0.10)):
        reasons.append("avg_cash_weight_needs_more_evidence")
    if safe_float(row.get("max_cash_weight")) > float(gate.get("max_cash_weight_max", 0.20)):
        reasons.append("max_cash_weight_needs_more_evidence")
    if safe_float(row.get("skipped_buy_rate")) > float(gate.get("skipped_buy_rate_hard_fail", 0.35)):
        reasons.append("skipped_buy_rate_hard_fail")
    elif safe_float(row.get("skipped_buy_rate")) > float(gate.get("skipped_buy_rate_max", 0.20)):
        reasons.append("skipped_buy_rate_needs_more_evidence")
    if safe_int(row.get("negative_cash_days")) > 0:
        reasons.append("negative_cash_days_gt_0")
    if safe_float(row.get("max_single_weight_realized")) > float(gate.get("max_single_weight_realized_max", 0.055)):
        reasons.append("max_single_weight_realized_gt_5_5pct")
    if safe_float(row.get("bought_vs_selected_price_median_ratio")) < float(gate.get("low_price_median_ratio_hard_fail", 0.50)):
        reasons.append("low_price_median_ratio_hard_fail")
    elif safe_float(row.get("bought_vs_selected_price_median_ratio")) < float(gate.get("low_price_median_ratio_needs_evidence", 0.70)):
        reasons.append("low_price_median_ratio_needs_more_evidence")
    if safe_float(row.get("low_price_active_weight_from_lot")) > float(gate.get("low_price_active_weight_needs_evidence", 0.20)):
        reasons.append("low_price_active_weight_needs_more_evidence")
    _ = target
    return reasons


def implementation_gate_status(row: dict[str, Any] | pd.Series, gate: dict[str, Any]) -> str:
    reasons = implementation_gate_reasons(row, gate)
    if reasons == ["diagnostic_cash_control_excluded_from_full_investment_gate"]:
        return "diagnostic_only"
    if any(reason.endswith("hard_fail") or reason == "negative_cash_days_gt_0" for reason in reasons):
        return "hard_failed"
    if reasons:
        return "needs_more_evidence"
    return "passed"


def portfolio_candidates(contract: dict[str, Any]) -> list[dict[str, Any]]:
    cfg = contract.get("portfolio_candidates") or {}
    return list(cfg.get("target_holdings") or [])


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def build_artifact_manifest(out_dir: Path) -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        rel = path.relative_to(out_dir).as_posix()
        manifest[rel] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
    return manifest


def table_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [normalize_record(row) for row in frame.to_dict("records")]


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    for column in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[column]):
            out[column] = out[column].dt.date.astype(str)
    return out.where(pd.notna(out), None)


def normalize_record(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if pd.isna(value):
            out[key] = None
        elif hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def parse_json(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def safe_float(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return math.nan
    return out if math.isfinite(out) else math.nan


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def divide(numerator: Any, denominator: Any) -> float | None:
    num_value = safe_float(numerator)
    den_value = safe_float(denominator)
    if not math.isfinite(num_value) or not math.isfinite(den_value) or den_value == 0:
        return None
    return num_value / den_value


def subtract_or_none(left: Any, right: Any) -> float | None:
    left_value = safe_float(left)
    right_value = safe_float(right)
    if not math.isfinite(left_value) or not math.isfinite(right_value):
        return None
    return left_value - right_value


def compound_returns(values: Any) -> float | None:
    series = pd.Series(values, dtype="float64").dropna()
    if series.empty:
        return None
    return float((1.0 + series).prod() - 1.0)


def pct(value: Any) -> str:
    number = safe_float(value)
    return "NA" if not math.isfinite(number) else f"{number:.2%}"


def num(value: Any) -> str:
    number = safe_float(value)
    return "NA" if not math.isfinite(number) else f"{number:.4f}"


if __name__ == "__main__":
    raise SystemExit(main())
