#!/usr/bin/env python3
"""Strategy 1 tail-risk and maximum-drawdown diagnostics.

This P0 diagnostic is intentionally read-only with respect to ADS. It reads
backtest outputs and risk features, writes local/GCS artifacts, and verifies
pre/post ADS hashes for the current run/backtest.
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

import numpy as np
import pandas as pd
from google.cloud import bigquery

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.strategy1_cloudrun.bq_io import (
    get_git_commit,
    join_gs_uri,
    json_dumps_strict,
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


TAIL_RISK_VERSION = "strategy1_tail_risk_v1"
TAIL_RISK_PROFILE_ID = "diagnostic_only"
OUTPUT_DATASET_ROLE = "ads"
REQUIRED_ARTIFACTS = [
    "max_drawdown_windows.csv",
    "max_drawdown_windows.json",
    "drawdown_position_contribution.csv",
    "drawdown_industry_contribution.csv",
    "drawdown_board_contribution.csv",
    "limit_down_exposure_daily.csv",
    "selection_profile_by_signal_date.csv",
    "selection_profile_summary.json",
    "risky_selected_names.csv",
    "risk_filter_funnel_daily.csv",
    "risk_filter_excluded_names.csv",
    "market_risk_off_dates.csv",
    "candidate_overlap_by_signal_date.csv",
    "common_crash_names.csv",
    "search_tail_risk_summary.csv",
    "tail_risk_summary.json",
    "ads_readonly_guard.json",
    "tail_risk.md",
]
PROFILE_FIELDS = [
    "total_mv_cny",
    "circ_mv_cny",
    "log_total_mv",
    "log_circ_mv",
    "ret_5d",
    "ret_20d",
    "ret_60d",
    "drawdown_20d",
    "vol_20d",
    "vol_60d",
    "hl_range_20d",
    "amount_ma20_cny",
    "turnover_rate_ma20",
    "volume_ratio",
    "limit_down_days_20d",
    "one_word_limit_days_20d",
    "list_age_td",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="策略 1 尾部风险诊断")
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", default="asia-east2")
    parser.add_argument("--strategy-id", default="ml_pv_clf_v0")
    parser.add_argument("--run-id", required=True, help="Candidate/portfolio/backtest run_id")
    parser.add_argument("--prediction-run-id", default=None, help="Prediction source run_id; defaults to --run-id")
    parser.add_argument("--backtest-id", required=True)
    parser.add_argument("--search-id", default=None)
    parser.add_argument("--feature-version", default="strategy1_pv_v0_20260601")
    parser.add_argument("--benchmark-sec-code", default="000001.SH")
    parser.add_argument("--analysis-start-date", default=None)
    parser.add_argument("--analysis-end-date", default=None)
    parser.add_argument("--max-drawdown-top-k", type=int, default=5)
    parser.add_argument("--artifact-base-uri", required=True)
    parser.add_argument("--local-mirror-root", default="reports/strategy1")
    parser.add_argument("--output-dataset-role", choices=OUTPUT_DATASET_ROLE_CHOICES, default="ads")
    parser.add_argument("--skip-gcs-upload", action="store_true")
    return parser.parse_args()


def main() -> int:
    global OUTPUT_DATASET_ROLE
    args = parse_args()
    args.prediction_run_id = args.prediction_run_id or args.run_id
    OUTPUT_DATASET_ROLE = args.output_dataset_role
    if args.max_drawdown_top_k <= 0:
        raise SystemExit("--max-drawdown-top-k must be positive")

    client = make_client(args.project, args.region)
    out_dir = artifact_local_dir(args)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = fetch_summary(client, args.project, args.backtest_id)
    start_date = args.analysis_start_date or date_str(summary["start_date"])
    end_date = args.analysis_end_date or date_str(summary["end_date"])
    benchmark_sec_code = summary.get("benchmark_sec_code") or args.benchmark_sec_code

    pre_guard = fetch_ads_readonly_guard(
        client,
        args.project,
        run_id=args.run_id,
        prediction_run_id=args.prediction_run_id,
        backtest_id=args.backtest_id,
        start_date=start_date,
        end_date=end_date,
    )
    nav_df = fetch_nav(client, args.project, args.backtest_id, start_date, end_date)
    windows = compute_drawdown_windows(nav_df, top_k=args.max_drawdown_top_k)
    validate_max_drawdown(summary, windows)

    positions = fetch_positions_enriched(
        client,
        args.project,
        args.backtest_id,
        start_date,
        end_date,
        feature_version=args.feature_version,
    )
    targets = fetch_targets(
        client,
        args.project,
        strategy_id=args.strategy_id,
        run_id=args.run_id,
        start_date=start_date,
        end_date=end_date,
    )
    position_contrib = build_position_contribution(windows, positions, targets)
    industry_contrib = aggregate_group_contribution(position_contrib, "industry")
    board_contrib = aggregate_group_contribution(position_contrib, "board")
    limit_exposure = build_limit_down_exposure(windows, positions, nav_df)

    signal_dates = recent_signal_dates_for_events(windows, targets)
    selection_pool = fetch_selection_pool(
        client,
        args.project,
        strategy_id=args.strategy_id,
        candidate_run_id=args.run_id,
        prediction_run_id=args.prediction_run_id,
        signal_dates=sorted(set(signal_dates.values())),
        feature_version=args.feature_version,
    )
    selection_profile, selection_summary, risky_names = build_selection_profile(
        windows,
        signal_dates,
        selection_pool,
    )
    tail_risk_profile_id = tail_risk_profile_from_summary(summary)
    market_state_version = market_state_version_from_summary(summary)
    risk_filter_candidates = fetch_risk_filter_candidates(
        client,
        args.project,
        strategy_id=args.strategy_id,
        run_id=args.run_id,
        start_date=start_date,
        end_date=end_date,
        feature_version=args.feature_version,
    )
    risk_filter_funnel, risk_filter_excluded = build_risk_filter_outputs(
        risk_filter_candidates,
        tail_risk_profile_id=tail_risk_profile_id,
    )
    market_risk_off_dates = fetch_market_risk_off_dates(
        client,
        args.project,
        start_date=start_date,
        end_date=end_date,
        tail_risk_profile_id=tail_risk_profile_id,
        market_state_version=market_state_version,
    )
    candidate_overlap = empty_frame([
        "search_id", "signal_date", "left_run_id", "right_run_id",
        "left_selected_count", "right_selected_count", "overlap_count",
    ])
    common_crash_names = empty_frame([
        "search_id", "signal_date", "sec_code", "sec_name",
        "selected_run_count", "run_ids", "window_cumulative_contribution",
    ])
    search_summary = build_search_tail_risk_summary(
        args=args,
        summary=summary,
        windows=windows,
        limit_exposure=limit_exposure,
    )

    write_csv(out_dir / "max_drawdown_windows.csv", pd.DataFrame(windows))
    write_json(out_dir / "max_drawdown_windows.json", {"events": windows})
    write_csv(out_dir / "drawdown_position_contribution.csv", position_contrib)
    write_csv(out_dir / "drawdown_industry_contribution.csv", industry_contrib)
    write_csv(out_dir / "drawdown_board_contribution.csv", board_contrib)
    write_csv(out_dir / "limit_down_exposure_daily.csv", limit_exposure)
    write_csv(out_dir / "selection_profile_by_signal_date.csv", selection_profile)
    write_json(out_dir / "selection_profile_summary.json", selection_summary)
    write_csv(out_dir / "risky_selected_names.csv", risky_names)
    write_csv(out_dir / "risk_filter_funnel_daily.csv", risk_filter_funnel)
    write_csv(out_dir / "risk_filter_excluded_names.csv", risk_filter_excluded)
    write_csv(out_dir / "market_risk_off_dates.csv", market_risk_off_dates)
    write_csv(out_dir / "candidate_overlap_by_signal_date.csv", candidate_overlap)
    write_csv(out_dir / "common_crash_names.csv", common_crash_names)
    write_csv(out_dir / "search_tail_risk_summary.csv", pd.DataFrame([search_summary]))

    post_guard = fetch_ads_readonly_guard(
        client,
        args.project,
        run_id=args.run_id,
        prediction_run_id=args.prediction_run_id,
        backtest_id=args.backtest_id,
        start_date=start_date,
        end_date=end_date,
    )
    guard = {
        "status": "passed" if pre_guard == post_guard else "failed",
        "pre": pre_guard,
        "post": post_guard,
    }
    if guard["status"] != "passed":
        write_json(out_dir / "ads_readonly_guard.json", guard)
        raise SystemExit("ADS read-only guard failed: pre/post summary or NAV hashes changed")
    write_json(out_dir / "ads_readonly_guard.json", guard)

    tail_summary = build_tail_risk_summary(
        args=args,
        summary=summary,
        start_date=start_date,
        end_date=end_date,
        benchmark_sec_code=benchmark_sec_code,
        windows=windows,
        limit_exposure=limit_exposure,
        selection_summary=selection_summary,
        risk_filter_funnel=risk_filter_funnel,
        market_risk_off_dates=market_risk_off_dates,
        guard=guard,
        local_path=str(out_dir),
        gcs_uri=None if args.skip_gcs_upload else artifact_gcs_uri(args),
    )
    write_json(out_dir / "tail_risk_summary.json", tail_summary)
    write_text(
        out_dir / "tail_risk.md",
        render_tail_risk_markdown(
            tail_summary,
            windows,
            limit_exposure,
            risky_names,
            risk_filter_funnel,
            market_risk_off_dates,
        ),
    )

    manifest = build_artifact_manifest(out_dir)
    missing = [name for name in REQUIRED_ARTIFACTS if name not in manifest]
    if missing:
        raise SystemExit(f"missing tail risk artifacts: {missing}")
    write_json(out_dir / "artifact_manifest.json", manifest)

    uploaded: list[str] = []
    if not args.skip_gcs_upload:
        uploaded = upload_directory_to_gcs(args.project, out_dir, artifact_gcs_uri(args))

    result = {
        "status": "succeeded",
        "tail_risk_uri": None if args.skip_gcs_upload else artifact_gcs_uri(args),
        "local_path": str(out_dir),
        "uploaded_artifacts": uploaded,
        "top_drawdown": windows[0] if windows else None,
        "ads_guard": guard,
    }
    print(json_dumps_strict(result, ensure_ascii=False, indent=2))
    return 0


def query_dataframe(
    client: bigquery.Client,
    sql: str,
    params: list[bigquery.ScalarQueryParameter],
    **kwargs: Any,
) -> pd.DataFrame:
    sql = rewrite_sql_dataset_role(
        sql,
        dataset_role=OUTPUT_DATASET_ROLE,
        project=client.project,
    )
    return bq_query_dataframe(client, sql, params, **kwargs)


def artifact_local_dir(args: argparse.Namespace) -> Path:
    return (
        Path(args.local_mirror_root)
        / args.strategy_id
        / f"run_id={args.run_id}"
        / f"backtest_id={args.backtest_id}"
        / "tail_risk"
    )


def artifact_gcs_uri(args: argparse.Namespace) -> str:
    parts = [args.strategy_id]
    if args.search_id:
        parts.append(f"search_id={args.search_id}")
    parts.extend([f"run_id={args.run_id}", f"backtest_id={args.backtest_id}", "tail_risk"])
    return join_gs_uri(args.artifact_base_uri, *parts)


def fetch_summary(client: bigquery.Client, project: str, backtest_id: str) -> dict[str, Any]:
    sql = f"""
    SELECT bs.*
    FROM `{project}.ashare_ads.ads_backtest_performance_summary` AS bs
    WHERE bs.backtest_id = @backtest_id
    """
    df = query_dataframe(client, sql, [bigquery.ScalarQueryParameter("backtest_id", "STRING", backtest_id)])
    if len(df) != 1:
        raise SystemExit(f"expected exactly one summary row for backtest_id={backtest_id}, got {len(df)}")
    return df.iloc[0].to_dict()


def fetch_nav(client: bigquery.Client, project: str, backtest_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    sql = f"""
    SELECT
      n.trade_date,
      n.nav,
      n.cash_cny,
      n.net_value_cny,
      n.gross_exposure,
      n.turnover_cny,
      n.cost_cny,
      n.daily_return,
      n.benchmark_sec_code,
      n.benchmark_return,
      n.excess_return,
      n.run_id
    FROM `{project}.ashare_ads.ads_backtest_nav_daily` AS n
    WHERE n.backtest_id = @backtest_id
      AND n.trade_date BETWEEN @start_date AND @end_date
    ORDER BY n.trade_date
    """
    df = query_dataframe(client, sql, [
        bigquery.ScalarQueryParameter("backtest_id", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
        bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
    ])
    if df.empty:
        raise SystemExit(f"no NAV rows for backtest_id={backtest_id}")
    df = normalize_date_columns(df, ["trade_date"])
    duplicated = df[df.duplicated("trade_date", keep=False)]
    if not duplicated.empty:
        bad_dates = []
        for dt, chunk in duplicated.groupby("trade_date"):
            if chunk.drop(columns=["trade_date"]).drop_duplicates().shape[0] > 1:
                bad_dates.append(date_str(dt))
        if bad_dates:
            raise SystemExit(f"NAV has inconsistent duplicate dates: {bad_dates[:5]}")
        df = df.drop_duplicates("trade_date", keep="first")
    return df.sort_values("trade_date").reset_index(drop=True)


def fetch_ads_readonly_guard(
    client: bigquery.Client,
    project: str,
    *,
    run_id: str,
    prediction_run_id: str,
    backtest_id: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    sql = f"""
    WITH summary_guard AS (
      SELECT
        COUNT(*) AS summary_row_count,
        TO_HEX(SHA256(COALESCE(STRING_AGG(TO_JSON_STRING(STRUCT(
          bs.backtest_id AS backtest_id,
          bs.strategy_id AS strategy_id,
          bs.model_id AS model_id,
          FORMAT_DATE('%F', bs.start_date) AS start_date,
          FORMAT_DATE('%F', bs.end_date) AS end_date,
          bs.total_return AS total_return,
          bs.excess_return AS excess_return,
          bs.annual_return AS annual_return,
          bs.annual_vol AS annual_vol,
          bs.sharpe AS sharpe,
          bs.max_drawdown AS max_drawdown,
          bs.turnover_annual AS turnover_annual,
          bs.cost_bps AS cost_bps,
          JSON_VALUE(bs.metrics_json, '$.report_uri') AS report_uri,
          JSON_VALUE(bs.metrics_json, '$.model_diagnosis_uri') AS model_diagnosis_uri
        )), '\\n' ORDER BY bs.backtest_id), ''))) AS summary_hash
      FROM `{project}.ashare_ads.ads_backtest_performance_summary` AS bs
      WHERE bs.backtest_id = @backtest_id
    ),
    nav_guard AS (
      SELECT
        COUNT(*) AS nav_row_count,
        TO_HEX(SHA256(COALESCE(STRING_AGG(TO_JSON_STRING(STRUCT(
          FORMAT_DATE('%F', nav.trade_date) AS trade_date,
          nav.nav AS nav,
          nav.daily_return AS daily_return,
          nav.cash_cny AS cash_cny,
          nav.gross_exposure AS gross_exposure
        )), '\\n' ORDER BY nav.trade_date), ''))) AS nav_hash
      FROM `{project}.ashare_ads.ads_backtest_nav_daily` AS nav
      WHERE nav.backtest_id = @backtest_id
        AND nav.trade_date BETWEEN @start_date AND @end_date
    )
    SELECT
      sg.summary_row_count,
      sg.summary_hash,
      ng.nav_row_count,
      ng.nav_hash,
      (SELECT COUNT(*) FROM `{project}.ashare_ads.ads_model_registry` AS reg
       WHERE JSON_VALUE(reg.model_params_json, '$.run_id') = @prediction_run_id
         AND reg.status = 'selected') AS registry_row_count,
      (SELECT COUNT(*) FROM `{project}.ashare_ads.ads_model_prediction_daily` AS pred
       WHERE pred.run_id = @prediction_run_id
         AND pred.predict_date BETWEEN @start_date AND @end_date) AS prediction_row_count,
      (SELECT COUNT(*) FROM `{project}.ashare_ads.ads_stock_candidate_daily` AS cand
       WHERE cand.run_id = @run_id
         AND cand.rebalance_date BETWEEN @start_date AND @end_date) AS candidate_row_count,
      (SELECT COUNT(*) FROM `{project}.ashare_ads.ads_portfolio_target_daily` AS pt
       WHERE pt.run_id = @run_id
         AND pt.rebalance_date BETWEEN @start_date AND @end_date) AS target_row_count,
      (SELECT COUNT(*) FROM `{project}.ashare_ads.ads_order_plan_daily` AS op
       WHERE op.run_id = @run_id
         AND op.rebalance_date BETWEEN @start_date AND @end_date) AS order_row_count,
      (SELECT COUNT(*) FROM `{project}.ashare_ads.ads_backtest_trade_daily` AS tr
       WHERE tr.backtest_id = @backtest_id
         AND tr.trade_date BETWEEN @start_date AND @end_date) AS trade_row_count,
      (SELECT COUNT(*) FROM `{project}.ashare_ads.ads_backtest_position_daily` AS pos
       WHERE pos.backtest_id = @backtest_id
         AND pos.trade_date BETWEEN @start_date AND @end_date) AS position_row_count
    FROM summary_guard AS sg
    CROSS JOIN nav_guard AS ng
    """
    df = query_dataframe(client, sql, [
        bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
        bigquery.ScalarQueryParameter("prediction_run_id", "STRING", prediction_run_id),
        bigquery.ScalarQueryParameter("backtest_id", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
        bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
    ])
    row = df.iloc[0].to_dict()
    return {key: scalar(row.get(key)) for key in row}


def fetch_positions_enriched(
    client: bigquery.Client,
    project: str,
    backtest_id: str,
    start_date: str,
    end_date: str,
    *,
    feature_version: str,
) -> pd.DataFrame:
    sql = f"""
    WITH base AS (
      SELECT
        p.backtest_id,
        p.trade_date,
        cal.trade_date_seq,
        p.sec_code,
        p.shares,
        p.close,
        p.market_value_cny,
        p.weight AS position_weight_eod,
        LAG(p.weight) OVER(PARTITION BY p.sec_code ORDER BY p.trade_date) AS prev_position_weight,
        LAG(cal.trade_date_seq) OVER(PARTITION BY p.sec_code ORDER BY p.trade_date) AS prev_trade_date_seq
      FROM `{project}.ashare_ads.ads_backtest_position_daily` AS p
      JOIN `{project}.ashare_dim.dim_trade_calendar` AS cal
        ON cal.exchange = 'SSE'
       AND cal.is_open = 1
       AND cal.cal_date = p.trade_date
      WHERE p.backtest_id = @backtest_id
        AND p.trade_date BETWEEN @start_date AND @end_date
    )
    SELECT
      b.trade_date,
      b.sec_code,
      st.sec_name,
      st.industry,
      COALESCE(feat.board, st.board) AS board,
      b.shares,
      b.close,
      b.market_value_cny,
      b.position_weight_eod,
      IF(b.prev_trade_date_seq = b.trade_date_seq - 1, b.prev_position_weight, NULL) AS position_weight_bod,
      px.ret_1d,
      px.is_limit_down,
      px.is_one_word_limit_down,
      px.can_sell_open,
      px.is_tradable,
      feat.market,
      feat.list_age_td,
      feat.is_st,
      feat.is_tradable_hard,
      feat.in_universe_default,
      feat.ret_5d,
      feat.ret_20d,
      feat.ret_60d,
      feat.drawdown_20d,
      feat.vol_20d,
      feat.vol_60d,
      feat.hl_range_20d,
      feat.amount_ma20_cny,
      feat.turnover_rate_ma20,
      feat.volume_ratio,
      feat.limit_down_days_20d,
      feat.one_word_limit_days_20d,
      feat.total_mv_cny,
      feat.circ_mv_cny,
      feat.log_total_mv,
      feat.log_circ_mv,
      feat.has_full_history_60d
    FROM base AS b
    LEFT JOIN `{project}.ashare_dwd.dwd_stock_eod_price` AS px
      ON px.sec_code = b.sec_code
     AND px.trade_date = b.trade_date
     AND px.trade_date BETWEEN @start_date AND @end_date
    LEFT JOIN `{project}.ashare_dws.dws_stock_feature_daily_v0` AS feat
      ON feat.sec_code = b.sec_code
     AND feat.trade_date = b.trade_date
     AND feat.feature_version = @feature_version
     AND feat.trade_date BETWEEN @start_date AND @end_date
    LEFT JOIN `{project}.ashare_dim.dim_stock` AS st
      ON st.sec_code = b.sec_code
    ORDER BY b.trade_date, b.sec_code
    """
    df = query_dataframe(client, sql, [
        bigquery.ScalarQueryParameter("backtest_id", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
        bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
        bigquery.ScalarQueryParameter("feature_version", "STRING", feature_version),
    ])
    return normalize_date_columns(df, ["trade_date"])


def fetch_targets(
    client: bigquery.Client,
    project: str,
    *,
    strategy_id: str,
    run_id: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    sql = f"""
    SELECT
      pt.rebalance_date,
      pt.sec_code,
      pt.target_weight,
      cand.score,
      cand.rank_raw,
      cand.rank_pct,
      st.sec_name,
      st.industry,
      st.board
    FROM `{project}.ashare_ads.ads_portfolio_target_daily` AS pt
    LEFT JOIN `{project}.ashare_ads.ads_stock_candidate_daily` AS cand
      ON cand.strategy_id = pt.strategy_id
     AND cand.run_id = pt.run_id
     AND cand.rebalance_date = pt.rebalance_date
     AND cand.sec_code = pt.sec_code
     AND cand.rebalance_date BETWEEN DATE_SUB(@start_date, INTERVAL 120 DAY) AND @end_date
    LEFT JOIN `{project}.ashare_dim.dim_stock` AS st
      ON st.sec_code = pt.sec_code
    WHERE pt.strategy_id = @strategy_id
      AND pt.run_id = @run_id
      AND pt.rebalance_date BETWEEN DATE_SUB(@start_date, INTERVAL 120 DAY) AND @end_date
    ORDER BY pt.rebalance_date, pt.target_weight DESC, pt.sec_code
    """
    df = query_dataframe(client, sql, [
        bigquery.ScalarQueryParameter("strategy_id", "STRING", strategy_id),
        bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
        bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
        bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
    ])
    return normalize_date_columns(df, ["rebalance_date"])


def fetch_selection_pool(
    client: bigquery.Client,
    project: str,
    *,
    strategy_id: str,
    candidate_run_id: str,
    prediction_run_id: str,
    signal_dates: list[Any],
    feature_version: str,
) -> pd.DataFrame:
    if not signal_dates:
        return empty_frame(["signal_date", "sec_code", "is_selected"])
    signal_dates = [date_str(d) for d in signal_dates]
    min_date, max_date = min(signal_dates), max(signal_dates)
    sql = f"""
    SELECT
      pred.predict_date AS signal_date,
      pred.sec_code,
      pred.score,
      pred.rank_raw,
      pred.rank_pct,
      COALESCE(cand.is_selected_candidate, pt.sec_code IS NOT NULL, FALSE) AS is_selected,
      pt.target_weight,
      st.sec_name,
      st.industry,
      COALESCE(feat.board, st.board) AS board,
      feat.market,
      feat.list_age_td,
      feat.is_st,
      feat.is_tradable_hard,
      feat.in_universe_default,
      feat.ret_5d,
      feat.ret_20d,
      feat.ret_60d,
      feat.drawdown_20d,
      feat.vol_20d,
      feat.vol_60d,
      feat.hl_range_20d,
      feat.amount_ma20_cny,
      feat.turnover_rate_ma20,
      feat.volume_ratio,
      feat.limit_down_days_20d,
      feat.one_word_limit_days_20d,
      feat.total_mv_cny,
      feat.circ_mv_cny,
      feat.log_total_mv,
      feat.log_circ_mv,
      feat.has_full_history_60d
    FROM `{project}.ashare_ads.ads_model_prediction_daily` AS pred
    LEFT JOIN `{project}.ashare_ads.ads_stock_candidate_daily` AS cand
      ON cand.strategy_id = @strategy_id
     AND cand.run_id = @candidate_run_id
     AND cand.rebalance_date = pred.predict_date
     AND cand.sec_code = pred.sec_code
     AND cand.rebalance_date BETWEEN @min_date AND @max_date
    LEFT JOIN `{project}.ashare_ads.ads_portfolio_target_daily` AS pt
      ON pt.strategy_id = @strategy_id
     AND pt.run_id = @candidate_run_id
     AND pt.rebalance_date = pred.predict_date
     AND pt.sec_code = pred.sec_code
     AND pt.rebalance_date BETWEEN @min_date AND @max_date
    LEFT JOIN `{project}.ashare_dws.dws_stock_feature_daily_v0` AS feat
      ON feat.trade_date = pred.predict_date
     AND feat.sec_code = pred.sec_code
     AND feat.feature_version = @feature_version
     AND feat.trade_date BETWEEN @min_date AND @max_date
    LEFT JOIN `{project}.ashare_dim.dim_stock` AS st
      ON st.sec_code = pred.sec_code
    WHERE pred.run_id = @prediction_run_id
      AND pred.predict_date BETWEEN @min_date AND @max_date
      AND pred.predict_date IN UNNEST(@signal_dates)
    ORDER BY pred.predict_date, pred.rank_raw
    """
    df = query_dataframe(client, sql, [
        bigquery.ScalarQueryParameter("strategy_id", "STRING", strategy_id),
        bigquery.ScalarQueryParameter("candidate_run_id", "STRING", candidate_run_id),
        bigquery.ScalarQueryParameter("prediction_run_id", "STRING", prediction_run_id),
        bigquery.ScalarQueryParameter("min_date", "DATE", min_date),
        bigquery.ScalarQueryParameter("max_date", "DATE", max_date),
        bigquery.ScalarQueryParameter("feature_version", "STRING", feature_version),
        bigquery.ArrayQueryParameter("signal_dates", "DATE", signal_dates),
    ])
    return normalize_date_columns(df, ["signal_date"])


def fetch_risk_filter_candidates(
    client: bigquery.Client,
    project: str,
    *,
    strategy_id: str,
    run_id: str,
    start_date: str,
    end_date: str,
    feature_version: str,
) -> pd.DataFrame:
    sql = f"""
    SELECT
      cand.rebalance_date,
      cand.sec_code,
      st.sec_name,
      st.industry,
      COALESCE(feat.board, st.board) AS board,
      cand.score,
      cand.rank_raw,
      cand.rank_pct,
      cand.in_universe_default,
      cand.is_selected_candidate,
      cand.filter_reason,
      pt.target_weight,
      feat.market,
      feat.list_age_td,
      feat.is_st,
      feat.is_tradable_hard,
      feat.in_universe_default AS feature_in_universe_default,
      feat.ret_5d,
      feat.ret_20d,
      feat.ret_60d,
      feat.drawdown_20d,
      feat.vol_20d,
      feat.vol_60d,
      feat.hl_range_20d,
      feat.amount_ma20_cny,
      feat.turnover_rate_ma20,
      feat.volume_ratio,
      feat.limit_down_days_20d,
      feat.one_word_limit_days_20d,
      feat.total_mv_cny,
      feat.circ_mv_cny,
      feat.log_total_mv,
      feat.log_circ_mv,
      feat.has_full_history_60d
    FROM `{project}.ashare_ads.ads_stock_candidate_daily` AS cand
    LEFT JOIN `{project}.ashare_ads.ads_portfolio_target_daily` AS pt
      ON pt.strategy_id = cand.strategy_id
     AND pt.run_id = cand.run_id
     AND pt.rebalance_date = cand.rebalance_date
     AND pt.sec_code = cand.sec_code
     AND pt.rebalance_date BETWEEN @start_date AND @end_date
    LEFT JOIN `{project}.ashare_dws.dws_stock_feature_daily_v0` AS feat
      ON feat.trade_date = cand.rebalance_date
     AND feat.sec_code = cand.sec_code
     AND feat.feature_version = @feature_version
     AND feat.trade_date BETWEEN @start_date AND @end_date
    LEFT JOIN `{project}.ashare_dim.dim_stock` AS st
      ON st.sec_code = cand.sec_code
    WHERE cand.strategy_id = @strategy_id
      AND cand.run_id = @run_id
      AND cand.rebalance_date BETWEEN @start_date AND @end_date
    ORDER BY cand.rebalance_date, cand.is_selected_candidate DESC, cand.rank_raw, cand.sec_code
    """
    df = query_dataframe(client, sql, [
        bigquery.ScalarQueryParameter("strategy_id", "STRING", strategy_id),
        bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
        bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
        bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
        bigquery.ScalarQueryParameter("feature_version", "STRING", feature_version),
    ])
    return normalize_date_columns(df, ["rebalance_date"])


def compute_drawdown_windows(nav_df: pd.DataFrame, *, top_k: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    rows = nav_df.sort_values("trade_date").reset_index(drop=True)
    peak_date = rows.loc[0, "trade_date"]
    peak_nav = float(rows.loc[0, "nav"])
    current: dict[str, Any] | None = None

    for idx in range(1, len(rows)):
        row = rows.loc[idx]
        nav = float(row["nav"])
        trade_date = row["trade_date"]
        if nav >= peak_nav:
            if current is not None:
                events.append(finalize_drawdown_event(current, rows))
                current = None
            if nav > peak_nav:
                peak_date = trade_date
                peak_nav = nav
            continue
        drawdown = nav / peak_nav - 1.0
        if current is None:
            current = {
                "peak_date": peak_date,
                "peak_nav": peak_nav,
                "trough_date": trade_date,
                "trough_nav": nav,
                "drawdown_pct": drawdown,
            }
        elif drawdown < current["drawdown_pct"]:
            current.update({"trough_date": trade_date, "trough_nav": nav, "drawdown_pct": drawdown})

    if current is not None:
        events.append(finalize_drawdown_event(current, rows))

    events = sorted(events, key=lambda item: item["drawdown_pct"])[:top_k]
    for i, event in enumerate(events, start=1):
        event["event_id"] = i
        event["rank_by_drawdown"] = i
    return events


def finalize_drawdown_event(event: dict[str, Any], nav_df: pd.DataFrame) -> dict[str, Any]:
    peak_date = event["peak_date"]
    trough_date = event["trough_date"]
    window = nav_df[(nav_df["trade_date"] >= peak_date) & (nav_df["trade_date"] <= trough_date)].copy()
    loss_window = nav_df[(nav_df["trade_date"] > peak_date) & (nav_df["trade_date"] <= trough_date)].copy()
    if loss_window.empty:
        loss_window = window
    benchmark_return = compound_return(loss_window["benchmark_return"]) if "benchmark_return" in loss_window else None
    strategy_return = float(event["trough_nav"] / event["peak_nav"] - 1.0)
    return {
        "peak_date": date_str(peak_date),
        "trough_date": date_str(trough_date),
        "trading_days": int(len(window)),
        "peak_nav": round_float(event["peak_nav"], 10),
        "trough_nav": round_float(event["trough_nav"], 10),
        "drawdown_pct": round_float(strategy_return, 10),
        "benchmark_return": round_float(benchmark_return, 10),
        "excess_return": round_float(strategy_return - benchmark_return, 10) if benchmark_return is not None else None,
        "worst_daily_return": round_float(loss_window["daily_return"].min(), 10),
        "worst_daily_excess_return": round_float(loss_window["excess_return"].min(), 10),
        "window_start_date": date_str(window["trade_date"].min()),
        "window_end_date": date_str(window["trade_date"].max()),
    }


def validate_max_drawdown(summary: dict[str, Any], windows: list[dict[str, Any]]) -> None:
    if not windows:
        raise SystemExit("no drawdown windows found")
    expected = float(summary.get("max_drawdown") or 0.0)
    actual = float(windows[0]["drawdown_pct"])
    if abs(expected - actual) > 1e-6:
        raise SystemExit(f"max_drawdown mismatch: summary={expected}, computed={actual}")


def build_position_contribution(
    windows: list[dict[str, Any]],
    positions: pd.DataFrame,
    targets: pd.DataFrame,
) -> pd.DataFrame:
    columns = [
        "event_id", "rank_by_drawdown", "peak_date", "trough_date", "trade_date",
        "recent_signal_date", "sec_code", "sec_name", "industry", "board",
        "is_recent_selected", "is_common_topk_holding", "position_weight_bod",
        "position_weight_bod_missing", "position_weight_eod", "ret_1d",
        "approx_daily_contribution", "window_cumulative_contribution",
        "window_worst_daily_contribution", "window_avg_weight_bod",
        "window_avg_weight_eod", "window_holding_days", "limit_down_or_near",
        "is_one_word_limit_down", "can_sell_open",
    ]
    if positions.empty or not windows:
        return empty_frame(columns)
    pos = positions.copy()
    pos["trade_date"] = to_datetime_date(pos["trade_date"])
    target_by_signal = target_sec_sets(targets)
    frames = []
    for event in windows:
        peak = pd.Timestamp(event["peak_date"]).date()
        trough = pd.Timestamp(event["trough_date"]).date()
        recent_signal = latest_signal_date(targets, peak, trough)
        selected_set = target_by_signal.get(recent_signal, set())
        win = pos[(pos["trade_date"] >= peak) & (pos["trade_date"] <= trough)].copy()
        if win.empty:
            continue
        win["event_id"] = event["event_id"]
        win["rank_by_drawdown"] = event["rank_by_drawdown"]
        win["peak_date"] = event["peak_date"]
        win["trough_date"] = event["trough_date"]
        win["recent_signal_date"] = date_str(recent_signal) if recent_signal else None
        win["is_recent_selected"] = win["sec_code"].isin(selected_set)
        win["is_common_topk_holding"] = False
        win["position_weight_bod_missing"] = win["position_weight_bod"].isna()
        win["position_weight_bod"] = to_numeric(win["position_weight_bod"]).fillna(0.0)
        win["position_weight_eod"] = to_numeric(win["position_weight_eod"]).fillna(0.0)
        win["ret_1d"] = to_numeric(win["ret_1d"])
        win["approx_daily_contribution"] = win["position_weight_bod"] * win["ret_1d"].fillna(0.0)
        win = add_limit_flags(win)
        group_cols = ["event_id", "sec_code"]
        grouped = win.groupby(group_cols, dropna=False)
        win["window_cumulative_contribution"] = grouped["approx_daily_contribution"].transform("sum")
        win["window_worst_daily_contribution"] = grouped["approx_daily_contribution"].transform("min")
        win["window_avg_weight_bod"] = grouped["position_weight_bod"].transform("mean")
        win["window_avg_weight_eod"] = grouped["position_weight_eod"].transform("mean")
        win["window_holding_days"] = grouped["trade_date"].transform("nunique")
        frames.append(win[columns])
    if not frames:
        return empty_frame(columns)
    out = pd.concat(frames, ignore_index=True)
    out["trade_date"] = out["trade_date"].map(date_str)
    return out.sort_values(["event_id", "trade_date", "approx_daily_contribution", "sec_code"]).reset_index(drop=True)


def aggregate_group_contribution(contrib: pd.DataFrame, group_col: str) -> pd.DataFrame:
    columns = [
        "event_id", "rank_by_drawdown", "peak_date", "trough_date", group_col,
        "cumulative_contribution", "worst_daily_contribution", "avg_weight_bod",
        "avg_weight_eod", "holding_name_count", "holding_days",
    ]
    if contrib.empty:
        return empty_frame(columns)
    daily = (
        contrib.groupby(["event_id", "rank_by_drawdown", "peak_date", "trough_date", "trade_date", group_col], dropna=False)
        .agg(
            daily_contribution=("approx_daily_contribution", "sum"),
            daily_weight_bod=("position_weight_bod", "sum"),
            daily_weight_eod=("position_weight_eod", "sum"),
            daily_name_count=("sec_code", "nunique"),
        )
        .reset_index()
    )
    out = (
        daily.groupby(["event_id", "rank_by_drawdown", "peak_date", "trough_date", group_col], dropna=False)
        .agg(
            cumulative_contribution=("daily_contribution", "sum"),
            worst_daily_contribution=("daily_contribution", "min"),
            avg_weight_bod=("daily_weight_bod", "mean"),
            avg_weight_eod=("daily_weight_eod", "mean"),
            holding_name_count=("daily_name_count", "max"),
            holding_days=("trade_date", "nunique"),
        )
        .reset_index()
    )
    return out.sort_values(["event_id", "cumulative_contribution"]).reset_index(drop=True)


def build_limit_down_exposure(
    windows: list[dict[str, Any]],
    positions: pd.DataFrame,
    nav_df: pd.DataFrame,
) -> pd.DataFrame:
    columns = [
        "event_id", "rank_by_drawdown", "peak_date", "trough_date", "trade_date",
        "position_count", "limit_down_or_near_count", "one_word_limit_down_count",
        "cannot_sell_open_count", "limit_down_weight_eod", "limit_down_weight_bod_approx",
        "one_word_limit_down_weight_eod", "cannot_sell_open_weight_eod",
        "source_flag_count", "return_fallback_count", "unknown_source_count",
        "strategy_daily_return", "benchmark_daily_return", "excess_daily_return",
        "gross_exposure",
    ]
    if not windows:
        return empty_frame(columns)
    nav = nav_df.copy()
    nav["trade_date"] = to_datetime_date(nav["trade_date"])
    pos = add_limit_flags(positions.copy()) if not positions.empty else positions.copy()
    if not pos.empty:
        pos["trade_date"] = to_datetime_date(pos["trade_date"])
        pos["position_weight_eod"] = to_numeric(pos["position_weight_eod"]).fillna(0.0)
        pos["position_weight_bod"] = to_numeric(pos["position_weight_bod"]).fillna(0.0)
    frames = []
    for event in windows:
        peak = pd.Timestamp(event["peak_date"]).date()
        trough = pd.Timestamp(event["trough_date"]).date()
        nav_win = nav[(nav["trade_date"] >= peak) & (nav["trade_date"] <= trough)].copy()
        pos_win = pos[(pos["trade_date"] >= peak) & (pos["trade_date"] <= trough)].copy() if not pos.empty else pos
        if pos_win.empty:
            grouped = pd.DataFrame(columns=["trade_date"])
        else:
            grouped = (
                pos_win.groupby("trade_date", dropna=False)
                .agg(
                    position_count=("sec_code", "nunique"),
                    limit_down_or_near_count=("limit_down_or_near", "sum"),
                    one_word_limit_down_count=("is_one_word_limit_down_bool", "sum"),
                    cannot_sell_open_count=("cannot_sell_open", "sum"),
                    limit_down_weight_eod=("limit_down_weight_eod", "sum"),
                    limit_down_weight_bod_approx=("limit_down_weight_bod", "sum"),
                    one_word_limit_down_weight_eod=("one_word_limit_down_weight_eod", "sum"),
                    cannot_sell_open_weight_eod=("cannot_sell_open_weight_eod", "sum"),
                    source_flag_count=("limit_down_source_flag", "sum"),
                    return_fallback_count=("limit_down_return_fallback", "sum"),
                    unknown_source_count=("limit_down_unknown_source", "sum"),
                )
                .reset_index()
            )
        merged = nav_win.merge(grouped, on="trade_date", how="left")
        count_cols = [
            "position_count", "limit_down_or_near_count", "one_word_limit_down_count",
            "cannot_sell_open_count", "source_flag_count", "return_fallback_count",
            "unknown_source_count",
        ]
        weight_cols = [
            "limit_down_weight_eod", "limit_down_weight_bod_approx",
            "one_word_limit_down_weight_eod", "cannot_sell_open_weight_eod",
        ]
        for col in count_cols:
            merged[col] = to_numeric(merged.get(col)).fillna(0).astype(int)
        for col in weight_cols:
            merged[col] = to_numeric(merged.get(col)).fillna(0.0)
        merged["event_id"] = event["event_id"]
        merged["rank_by_drawdown"] = event["rank_by_drawdown"]
        merged["peak_date"] = event["peak_date"]
        merged["trough_date"] = event["trough_date"]
        merged = merged.rename(columns={
            "daily_return": "strategy_daily_return",
            "benchmark_return": "benchmark_daily_return",
            "excess_return": "excess_daily_return",
        })
        frames.append(merged[columns])
    out = pd.concat(frames, ignore_index=True) if frames else empty_frame(columns)
    out["trade_date"] = out["trade_date"].map(date_str)
    return out.sort_values(["event_id", "trade_date"]).reset_index(drop=True)


def build_selection_profile(
    windows: list[dict[str, Any]],
    signal_dates: dict[int, Any],
    pool: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    profile_cols = [
        "event_id", "rank_by_drawdown", "peak_date", "trough_date", "signal_date",
        "feature", "selected_count", "pool_count", "selected_mean", "selected_median",
        "selected_p10", "selected_p90", "pool_mean", "pool_median", "pool_p10",
        "pool_p90", "median_diff", "median_ratio", "extreme_rule", "extreme_selected_count",
    ]
    risky_cols = [
        "event_id", "signal_date", "sec_code", "sec_name", "industry", "board",
        "target_weight", "score", "rank_raw", "rank_pct", "risk_reasons",
        *PROFILE_FIELDS,
    ]
    if pool.empty:
        return empty_frame(profile_cols), {
            "signal_dates": {str(k): date_str(v) for k, v in signal_dates.items()},
            "profile_status": "missing_selection_pool",
        }, empty_frame(risky_cols)
    pool = pool.copy()
    pool["signal_date"] = to_datetime_date(pool["signal_date"])
    pool["is_selected"] = pool["is_selected"].fillna(False).astype(bool)
    risk_thresholds = build_risk_thresholds(pool)
    rows = []
    risky = []
    event_by_id = {event["event_id"]: event for event in windows}
    for event_id, signal_date in signal_dates.items():
        event = event_by_id[event_id]
        if signal_date is None:
            continue
        day_pool = pool[pool["signal_date"] == signal_date].copy()
        selected = day_pool[day_pool["is_selected"]].copy()
        for field in PROFILE_FIELDS:
            if field not in day_pool.columns:
                continue
            pool_values = to_numeric(day_pool[field]).dropna()
            selected_values = to_numeric(selected[field]).dropna()
            rule_name, extreme_count = extreme_rule_count(selected, field, risk_thresholds.get((date_str(signal_date), field)))
            rows.append({
                "event_id": event_id,
                "rank_by_drawdown": event["rank_by_drawdown"],
                "peak_date": event["peak_date"],
                "trough_date": event["trough_date"],
                "signal_date": date_str(signal_date),
                "feature": field,
                "selected_count": int(len(selected)),
                "pool_count": int(len(day_pool)),
                "selected_mean": series_stat(selected_values, "mean"),
                "selected_median": series_stat(selected_values, "median"),
                "selected_p10": series_stat(selected_values, "p10"),
                "selected_p90": series_stat(selected_values, "p90"),
                "pool_mean": series_stat(pool_values, "mean"),
                "pool_median": series_stat(pool_values, "median"),
                "pool_p10": series_stat(pool_values, "p10"),
                "pool_p90": series_stat(pool_values, "p90"),
                "median_diff": diff_or_none(series_stat(selected_values, "median"), series_stat(pool_values, "median")),
                "median_ratio": ratio_or_none(series_stat(selected_values, "median"), series_stat(pool_values, "median")),
                "extreme_rule": rule_name,
                "extreme_selected_count": extreme_count,
            })
        for _, stock in selected.iterrows():
            reasons = risk_reasons(stock, risk_thresholds, signal_date)
            if reasons:
                risky.append({
                    "event_id": event_id,
                    "signal_date": date_str(signal_date),
                    "sec_code": stock.get("sec_code"),
                    "sec_name": stock.get("sec_name"),
                    "industry": stock.get("industry"),
                    "board": stock.get("board"),
                    "target_weight": scalar(stock.get("target_weight")),
                    "score": scalar(stock.get("score")),
                    "rank_raw": scalar(stock.get("rank_raw")),
                    "rank_pct": scalar(stock.get("rank_pct")),
                    "risk_reasons": ";".join(reasons),
                    **{field: scalar(stock.get(field)) for field in PROFILE_FIELDS},
                })
    profile = pd.DataFrame(rows, columns=profile_cols)
    risky_df = pd.DataFrame(risky, columns=risky_cols) if risky else empty_frame(risky_cols)
    summary = {
        "profile_status": "completed",
        "signal_dates": {str(k): date_str(v) for k, v in signal_dates.items()},
        "selected_counts": {
            date_str(d): int(pool[(pool["signal_date"] == d) & (pool["is_selected"])].shape[0])
            for d in sorted(set(signal_dates.values()))
            if d is not None
        },
        "pool_counts": {
            date_str(d): int(pool[pool["signal_date"] == d].shape[0])
            for d in sorted(set(signal_dates.values()))
            if d is not None
        },
        "risk_thresholds": {
            f"{date_key}:{field}": threshold
            for (date_key, field), threshold in risk_thresholds.items()
        },
        "risky_selected_count": int(len(risky_df)),
    }
    return profile, summary, risky_df


RISK_FILTER_REASON_COLUMNS = [
    "tail_risk_feature_missing_count",
    "tail_risk_required_field_null_count",
    "ret_20d_lt_30pct_count",
    "drawdown_20d_lt_30pct_count",
    "limit_down_days_20d_gte_2_count",
    "one_word_limit_days_20d_gte_1_count",
    "total_mv_cny_lt_30e8_count",
    "circ_mv_cny_lt_20e8_count",
]


def build_risk_filter_outputs(
    candidates: pd.DataFrame,
    *,
    tail_risk_profile_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    funnel_cols = [
        "rebalance_date", "tail_risk_profile_id", "prediction_count",
        "not_in_universe_count", "risk_excluded_count", "eligible_count",
        "selected_count", "vol_20d_pool_p95", "vol_20d_mark_count",
        "turnover_rate_ma20_pool_p98", "turnover_rate_ma20_mark_count",
        *RISK_FILTER_REASON_COLUMNS,
    ]
    excluded_cols = [
        "rebalance_date", "tail_risk_profile_id", "sec_code", "sec_name",
        "industry", "board", "score", "rank_raw", "rank_pct",
        "filter_reason", "risk_reasons", *PROFILE_FIELDS,
    ]
    if candidates.empty:
        return empty_frame(funnel_cols), empty_frame(excluded_cols)

    frame = candidates.copy()
    frame["rebalance_date"] = to_datetime_date(frame["rebalance_date"])
    frame["filter_reason"] = frame["filter_reason"].fillna("")
    frame["is_selected_candidate"] = frame["is_selected_candidate"].fillna(False).astype(bool)
    frame["is_risk_excluded"] = frame["filter_reason"].str.startswith("tail_risk:")
    frame["is_not_in_universe"] = frame["filter_reason"].eq("not_in_default_universe")
    frame["is_eligible_after_risk_filter"] = ~frame["is_not_in_universe"] & ~frame["is_risk_excluded"]
    for col in RISK_FILTER_REASON_COLUMNS:
        reason = col.removesuffix("_count")
        frame[col] = frame["filter_reason"].str.contains(reason, regex=False)

    funnel_rows = []
    for rebalance_date, group in frame.groupby("rebalance_date", dropna=False):
        vol_threshold = series_stat(to_numeric(group.get("vol_20d")), "p95")
        turnover_threshold = series_stat(to_numeric(group.get("turnover_rate_ma20")), "p98")
        row = {
            "rebalance_date": date_str(rebalance_date),
            "tail_risk_profile_id": tail_risk_profile_id,
            "prediction_count": int(len(group)),
            "not_in_universe_count": int(group["is_not_in_universe"].sum()),
            "risk_excluded_count": int(group["is_risk_excluded"].sum()),
            "eligible_count": int(group["is_eligible_after_risk_filter"].sum()),
            "selected_count": int(group["is_selected_candidate"].sum()),
            "vol_20d_pool_p95": vol_threshold,
            "vol_20d_mark_count": int((to_numeric(group.get("vol_20d")) > vol_threshold).sum()) if vol_threshold is not None else 0,
            "turnover_rate_ma20_pool_p98": turnover_threshold,
            "turnover_rate_ma20_mark_count": int((to_numeric(group.get("turnover_rate_ma20")) > turnover_threshold).sum()) if turnover_threshold is not None else 0,
        }
        for col in RISK_FILTER_REASON_COLUMNS:
            row[col] = int(group[col].sum())
        funnel_rows.append(row)

    excluded = frame[frame["is_risk_excluded"]].copy()
    if excluded.empty:
        excluded_df = empty_frame(excluded_cols)
    else:
        excluded["tail_risk_profile_id"] = tail_risk_profile_id
        excluded["risk_reasons"] = excluded["filter_reason"].str.replace("tail_risk:", "", n=1, regex=False)
        excluded["rebalance_date"] = excluded["rebalance_date"].map(date_str)
        for field in PROFILE_FIELDS:
            if field not in excluded:
                excluded[field] = None
        excluded_df = excluded[excluded_cols].sort_values(["rebalance_date", "rank_raw", "sec_code"]).reset_index(drop=True)
    funnel = pd.DataFrame(funnel_rows, columns=funnel_cols).sort_values("rebalance_date").reset_index(drop=True)
    return funnel, excluded_df


def summarize_risk_filter_funnel(funnel: pd.DataFrame) -> dict[str, Any]:
    if funnel.empty:
        return {
            "rebalance_day_count": 0,
            "risk_excluded_count": 0,
            "selected_count": 0,
        }
    return {
        "rebalance_day_count": int(len(funnel)),
        "prediction_count": int(to_numeric(funnel["prediction_count"]).sum()),
        "not_in_universe_count": int(to_numeric(funnel["not_in_universe_count"]).sum()),
        "risk_excluded_count": int(to_numeric(funnel["risk_excluded_count"]).sum()),
        "eligible_count": int(to_numeric(funnel["eligible_count"]).sum()),
        "selected_count": int(to_numeric(funnel["selected_count"]).sum()),
        "max_daily_risk_excluded_count": int(to_numeric(funnel["risk_excluded_count"]).max()),
    }


def tail_risk_profile_from_summary(summary: dict[str, Any]) -> str:
    metrics = parse_json(summary.get("metrics_json"))
    return str(metrics.get("tail_risk_profile_id") or TAIL_RISK_PROFILE_ID)


def market_state_version_from_summary(summary: dict[str, Any]) -> str:
    metrics = parse_json(summary.get("metrics_json"))
    return str(metrics.get("market_state_version") or "market_state_v0_20260606")


def has_market_risk_guard(profile_id: str) -> bool:
    return profile_id in {"market_risk_off_v0", "individual_and_market_risk_guard_v0"}


def fetch_market_risk_off_dates(
    client: bigquery.Client,
    project: str,
    *,
    start_date: str,
    end_date: str,
    tail_risk_profile_id: str,
    market_state_version: str,
) -> pd.DataFrame:
    columns = [
        "trade_date", "market_state_version", "market_regime", "risk_off_action",
        "risk_off_reasons", "risk_off_trigger_count", "is_smallcap_trend_down",
        "is_breadth_weak", "is_limit_down_diffusion", "csi1000_ret_20d",
        "csi1000_drawdown_20d", "adv_ratio_1d", "above_ma20_ratio",
        "new_low_20d_ratio", "limit_down_count", "limit_down_mv_ratio",
    ]
    if not has_market_risk_guard(tail_risk_profile_id):
        return empty_frame(columns)
    sql = f"""
    SELECT
      ms.trade_date,
      ms.market_state_version,
      ms.market_regime,
      ms.risk_off_action,
      ms.risk_off_reasons,
      ms.risk_off_trigger_count,
      ms.is_smallcap_trend_down,
      ms.is_breadth_weak,
      ms.is_limit_down_diffusion,
      ms.csi1000_ret_20d,
      ms.csi1000_drawdown_20d,
      ms.adv_ratio_1d,
      ms.above_ma20_ratio,
      ms.new_low_20d_ratio,
      ms.limit_down_count,
      ms.limit_down_mv_ratio
    FROM `{project}.ashare_dws.dws_market_state_daily` AS ms
    WHERE ms.trade_date BETWEEN @start_date AND @end_date
      AND ms.market_state_version = @market_state_version
      AND ms.is_risk_off
    ORDER BY ms.trade_date
    """
    df = query_dataframe(client, sql, [
        bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
        bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
        bigquery.ScalarQueryParameter("market_state_version", "STRING", market_state_version),
    ])
    if df.empty:
        return empty_frame(columns)
    return normalize_date_columns(df[columns], ["trade_date"])


def recent_signal_dates_for_events(windows: list[dict[str, Any]], targets: pd.DataFrame) -> dict[int, Any]:
    out: dict[int, Any] = {}
    if targets.empty:
        return {event["event_id"]: None for event in windows}
    for event in windows:
        peak = pd.Timestamp(event["peak_date"]).date()
        trough = pd.Timestamp(event["trough_date"]).date()
        signal_date = latest_signal_date(targets, peak, trough)
        out[event["event_id"]] = signal_date
    return out


def latest_signal_date(targets: pd.DataFrame, as_of_date: Any, fallback_until: Any | None = None) -> Any:
    if targets.empty:
        return None
    dates = sorted(set(to_datetime_date(targets["rebalance_date"])))
    as_of = pd.Timestamp(as_of_date).date()
    eligible = [d for d in dates if d <= as_of]
    if eligible:
        return eligible[-1]
    if fallback_until is not None:
        until = pd.Timestamp(fallback_until).date()
        in_window = [d for d in dates if as_of <= d <= until]
        if in_window:
            return in_window[0]
    return None


def target_sec_sets(targets: pd.DataFrame) -> dict[Any, set[str]]:
    if targets.empty:
        return {}
    target_dates = to_datetime_date(targets["rebalance_date"])
    result: dict[Any, set[str]] = {}
    for dt, group in targets.assign(_date=target_dates).groupby("_date"):
        result[dt] = set(group["sec_code"].dropna().astype(str))
    return result


def add_limit_flags(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    ret = to_numeric(out.get("ret_1d"))
    source_flag_known = out.get("is_limit_down").notna() if "is_limit_down" in out else pd.Series(False, index=out.index)
    source_limit = out.get("is_limit_down").fillna(False).astype(bool) if "is_limit_down" in out else pd.Series(False, index=out.index)
    fallback = (~source_flag_known) & (ret <= -0.095)
    out["near_limit_down_by_return"] = fallback
    out["limit_down_source_flag"] = source_limit
    out["limit_down_return_fallback"] = fallback
    out["limit_down_unknown_source"] = (~source_flag_known) & ret.isna()
    out["limit_down_or_near"] = source_limit | fallback
    out["limit_down_source"] = np.select(
        [source_limit, fallback, out["limit_down_unknown_source"]],
        ["source_flag", "return_fallback", "unknown"],
        default="not_limit_down",
    )
    out["is_one_word_limit_down_bool"] = out.get("is_one_word_limit_down", False).fillna(False).astype(bool)
    out["cannot_sell_open"] = ~(out.get("can_sell_open", True).fillna(True).astype(bool))
    out["limit_down_weight_eod"] = np.where(out["limit_down_or_near"], to_numeric(out.get("position_weight_eod")).fillna(0.0), 0.0)
    out["limit_down_weight_bod"] = np.where(out["limit_down_or_near"], to_numeric(out.get("position_weight_bod")).fillna(0.0), 0.0)
    out["one_word_limit_down_weight_eod"] = np.where(out["is_one_word_limit_down_bool"], to_numeric(out.get("position_weight_eod")).fillna(0.0), 0.0)
    out["cannot_sell_open_weight_eod"] = np.where(out["cannot_sell_open"], to_numeric(out.get("position_weight_eod")).fillna(0.0), 0.0)
    return out


def build_risk_thresholds(pool: pd.DataFrame) -> dict[tuple[str, str], float]:
    thresholds: dict[tuple[str, str], float] = {}
    for signal_date, group in pool.groupby("signal_date"):
        date_key = date_str(signal_date)
        if "vol_20d" in group:
            thresholds[(date_key, "vol_20d")] = scalar(to_numeric(group["vol_20d"]).quantile(0.95))
        if "turnover_rate_ma20" in group:
            thresholds[(date_key, "turnover_rate_ma20")] = scalar(to_numeric(group["turnover_rate_ma20"]).quantile(0.98))
    return thresholds


def extreme_rule_count(selected: pd.DataFrame, field: str, threshold: float | None) -> tuple[str | None, int | None]:
    if selected.empty or field not in selected:
        return None, None
    values = to_numeric(selected[field])
    rules = {
        "ret_20d": ("ret_20d < -30%", values < -0.30),
        "drawdown_20d": ("drawdown_20d < -30%", values < -0.30),
        "limit_down_days_20d": ("limit_down_days_20d >= 2", values >= 2),
        "one_word_limit_days_20d": ("one_word_limit_days_20d >= 1", values >= 1),
        "total_mv_cny": ("total_mv_cny < 30e8", values < 30e8),
        "circ_mv_cny": ("circ_mv_cny < 20e8", values < 20e8),
    }
    if field in {"vol_20d", "turnover_rate_ma20"} and threshold is not None:
        return f"{field} above pool tail threshold", int((values > threshold).sum())
    if field not in rules:
        return None, None
    name, mask = rules[field]
    return name, int(mask.sum())


def risk_reasons(stock: pd.Series, thresholds: dict[tuple[str, str], float], signal_date: Any) -> list[str]:
    reasons = []
    checks = [
        ("ret_20d<-30%", stock.get("ret_20d"), lambda v: v < -0.30),
        ("drawdown_20d<-30%", stock.get("drawdown_20d"), lambda v: v < -0.30),
        ("limit_down_days_20d>=2", stock.get("limit_down_days_20d"), lambda v: v >= 2),
        ("one_word_limit_days_20d>=1", stock.get("one_word_limit_days_20d"), lambda v: v >= 1),
        ("total_mv_cny<30e8", stock.get("total_mv_cny"), lambda v: v < 30e8),
        ("circ_mv_cny<20e8", stock.get("circ_mv_cny"), lambda v: v < 20e8),
    ]
    for name, value, predicate in checks:
        value = numeric_or_none(value)
        if value is not None and predicate(value):
            reasons.append(name)
    date_key = date_str(signal_date)
    for field, label in (("vol_20d", "vol_20d>pool_p95"), ("turnover_rate_ma20", "turnover_rate_ma20>pool_p98")):
        threshold = thresholds.get((date_key, field))
        value = numeric_or_none(stock.get(field))
        if threshold is not None and value is not None and value > threshold:
            reasons.append(label)
    return reasons


def build_search_tail_risk_summary(
    *,
    args: argparse.Namespace,
    summary: dict[str, Any],
    windows: list[dict[str, Any]],
    limit_exposure: pd.DataFrame,
) -> dict[str, Any]:
    top = windows[0] if windows else {}
    tail_risk_profile_id = tail_risk_profile_from_summary(summary)
    limit_peak = None
    if not limit_exposure.empty and "limit_down_weight_eod" in limit_exposure:
        limit_peak = scalar(to_numeric(limit_exposure["limit_down_weight_eod"]).max())
    return {
        "search_id": args.search_id,
        "run_id": args.run_id,
        "prediction_run_id": args.prediction_run_id,
        "backtest_id": args.backtest_id,
        "strategy_id": args.strategy_id,
        "feature_version": args.feature_version,
        "tail_risk_profile_id": tail_risk_profile_id,
        "total_return": scalar(summary.get("total_return")),
        "excess_return": scalar(summary.get("excess_return")),
        "sharpe": scalar(summary.get("sharpe")),
        "summary_max_drawdown": scalar(summary.get("max_drawdown")),
        "tail_risk_drawdown_pct": top.get("drawdown_pct"),
        "tail_risk_peak_date": top.get("peak_date"),
        "tail_risk_trough_date": top.get("trough_date"),
        "tail_risk_benchmark_return": top.get("benchmark_return"),
        "tail_risk_excess_return": top.get("excess_return"),
        "tail_risk_limit_down_weight_peak": limit_peak,
        "tail_risk_uri": None if args.skip_gcs_upload else artifact_gcs_uri(args),
    }


def build_tail_risk_summary(
    *,
    args: argparse.Namespace,
    summary: dict[str, Any],
    start_date: str,
    end_date: str,
    benchmark_sec_code: str,
    windows: list[dict[str, Any]],
    limit_exposure: pd.DataFrame,
    selection_summary: dict[str, Any],
    risk_filter_funnel: pd.DataFrame,
    market_risk_off_dates: pd.DataFrame,
    guard: dict[str, Any],
    local_path: str,
    gcs_uri: str | None,
) -> dict[str, Any]:
    metrics_json = parse_json(summary.get("metrics_json"))
    tail_risk_profile_id = tail_risk_profile_from_summary(summary)
    top = windows[0] if windows else {}
    limit_peak = None
    if not limit_exposure.empty:
        limit_peak = scalar(to_numeric(limit_exposure["limit_down_weight_eod"]).max())
    return {
        "tail_risk_diagnosis_version": TAIL_RISK_VERSION,
        "tail_risk_profile_id": tail_risk_profile_id,
        "strategy_id": args.strategy_id,
        "search_id": args.search_id,
        "run_id": args.run_id,
        "prediction_run_id": args.prediction_run_id,
        "backtest_id": args.backtest_id,
        "feature_version": args.feature_version,
        "model_id": summary.get("model_id"),
        "benchmark_sec_code": benchmark_sec_code,
        "ledger_version": metrics_json.get("ledger_version"),
        "analysis_start_date": start_date,
        "analysis_end_date": end_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "local_path": local_path,
        "tail_risk_uri": gcs_uri,
        "summary_max_drawdown": scalar(summary.get("max_drawdown")),
        "computed_max_drawdown": top.get("drawdown_pct"),
        "max_drawdown_matches_summary": bool(abs(float(summary.get("max_drawdown") or 0) - float(top.get("drawdown_pct") or 0)) <= 1e-6),
        "top_drawdown_event": top,
        "drawdown_event_count": len(windows),
        "limit_down_weight_peak": limit_peak,
        "selection_profile_summary": selection_summary,
        "risk_filter_summary": summarize_risk_filter_funnel(risk_filter_funnel),
        "market_state_version": metrics_json.get("market_state_version") or "market_state_v0_20260606",
        "market_risk_off_signal_count": int(len(market_risk_off_dates)),
        "market_risk_action": metrics_json.get("market_risk_action") or "skip_new_buys",
        "ads_readonly_guard_status": guard["status"],
        "ads_readonly_guard": guard,
    }


def render_tail_risk_markdown(
    summary: dict[str, Any],
    windows: list[dict[str, Any]],
    limit_exposure: pd.DataFrame,
    risky_names: pd.DataFrame,
    risk_filter_funnel: pd.DataFrame,
    market_risk_off_dates: pd.DataFrame,
) -> str:
    top = windows[0] if windows else {}
    lines = [
        "# 策略 1 尾部风险诊断",
        "",
        f"- run_id: `{summary['run_id']}`",
        f"- prediction_run_id: `{summary['prediction_run_id']}`",
        f"- backtest_id: `{summary['backtest_id']}`",
        f"- feature_version: `{summary['feature_version']}`",
        f"- 诊断版本: `{summary['tail_risk_diagnosis_version']}`",
        f"- 诊断 profile: `{summary['tail_risk_profile_id']}`",
        f"- 市场状态版本: `{summary.get('market_state_version')}`",
        f"- ADS 只读校验: `{summary['ads_readonly_guard_status']}`",
        "",
        "## 最大回撤",
        "",
        f"- 峰值日: `{top.get('peak_date', 'NA')}`",
        f"- 谷底日: `{top.get('trough_date', 'NA')}`",
        f"- 策略回撤: {fmt_pct(top.get('drawdown_pct'))}",
        f"- 同期基准收益: {fmt_pct(top.get('benchmark_return'))}",
        f"- 同期超额: {fmt_pct(top.get('excess_return'))}",
        "",
    ]
    if not limit_exposure.empty:
        peak_row = limit_exposure.sort_values("limit_down_weight_eod", ascending=False).head(1).iloc[0].to_dict()
        lines.extend([
            "## 跌停/流动性风险峰值",
            "",
            f"- 日期: `{peak_row.get('trade_date')}`",
            f"- 跌停或接近跌停仓位权重: {fmt_pct(peak_row.get('limit_down_weight_eod'))}",
            f"- 一字跌停仓位权重: {fmt_pct(peak_row.get('one_word_limit_down_weight_eod'))}",
            f"- 开盘不可卖仓位权重: {fmt_pct(peak_row.get('cannot_sell_open_weight_eod'))}",
            "",
        ])
    if not risky_names.empty:
        lines.extend([
            "## 高风险入选样例",
            "",
            "| signal_date | sec_code | name | weight | rank | reasons |",
            "|---|---|---|---:|---:|---|",
        ])
        for _, row in risky_names.head(20).iterrows():
            lines.append(
                f"| {row.get('signal_date')} | `{row.get('sec_code')}` | {row.get('sec_name') or ''} | "
                f"{fmt_pct(row.get('target_weight'))} | {row.get('rank_raw')} | {row.get('risk_reasons')} |"
            )
        lines.append("")
    if not risk_filter_funnel.empty:
        risk_summary = summary.get("risk_filter_summary") or {}
        lines.extend([
            "## 个股风险过滤漏斗",
            "",
            f"- profile: `{summary['tail_risk_profile_id']}`",
            f"- 调仓日数: `{risk_summary.get('rebalance_day_count', 0)}`",
            f"- 预测样本数: `{risk_summary.get('prediction_count', 0)}`",
            f"- 风险标记数: `{risk_summary.get('risk_excluded_count', 0)}`",
            f"- 未标记可选样本数: `{risk_summary.get('eligible_count', 0)}`",
            f"- 最终入选数: `{risk_summary.get('selected_count', 0)}`",
            "",
        ])
    if not market_risk_off_dates.empty:
        lines.extend([
            "## 市场 risk-off 信号",
            "",
            f"- 风险关闭信号日数: `{summary.get('market_risk_off_signal_count', 0)}`",
            f"- 执行动作: `{summary.get('market_risk_action')}`",
            "",
            "| trade_date | reasons | csi1000_ret_20d | adv_ratio | limit_down_count |",
            "|---|---|---:|---:|---:|",
        ])
        for _, row in market_risk_off_dates.head(30).iterrows():
            lines.append(
                f"| {row.get('trade_date')} | {row.get('risk_off_reasons') or ''} | "
                f"{fmt_pct(row.get('csi1000_ret_20d'))} | {fmt_pct(row.get('adv_ratio_1d'))} | "
                f"{int(row.get('limit_down_count') or 0)} |"
            )
        lines.append("")
    lines.extend([
        "## 产物",
        "",
        "- `max_drawdown_windows.csv`：最大回撤事件列表。",
        "- `drawdown_position_contribution.csv`：回撤窗口内 BOD 权重近似持仓贡献。",
        "- `limit_down_exposure_daily.csv`：每日跌停/一字板/不可卖仓位暴露。",
        "- `selection_profile_by_signal_date.csv`：回撤前信号日的选股画像。",
        "- `risk_filter_funnel_daily.csv`：P1 个股风险过滤漏斗。",
        "- `risk_filter_excluded_names.csv`：P1 个股风险过滤排除名单。",
        "- `market_risk_off_dates.csv`：P2 市场 risk-off 信号日和触发证据。",
        "",
    ])
    return "\n".join(lines)


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


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def normalize_date_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    for col in columns:
        if col in out:
            out[col] = to_datetime_date(out[col])
    return out


def to_datetime_date(value: Any) -> Any:
    if isinstance(value, pd.Series):
        return pd.to_datetime(value).dt.date
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).date()


def date_str(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).date().isoformat()


def to_numeric(value: Any) -> pd.Series:
    if isinstance(value, pd.Series):
        return pd.to_numeric(value, errors="coerce")
    return pd.Series(value)


def numeric_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, np.generic):
        return scalar(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def round_float(value: Any, digits: int = 6) -> float | None:
    value = numeric_or_none(value)
    return round(value, digits) if value is not None else None


def compound_return(series: pd.Series) -> float | None:
    values = to_numeric(series).dropna()
    values = values[values > -1.0]
    if values.empty:
        return 0.0
    return float(np.prod(1.0 + values) - 1.0)


def series_stat(values: pd.Series, stat: str) -> float | None:
    values = to_numeric(values).dropna()
    if values.empty:
        return None
    if stat == "mean":
        return scalar(values.mean())
    if stat == "median":
        return scalar(values.median())
    if stat == "p10":
        return scalar(values.quantile(0.10))
    if stat == "p90":
        return scalar(values.quantile(0.90))
    if stat == "p95":
        return scalar(values.quantile(0.95))
    if stat == "p98":
        return scalar(values.quantile(0.98))
    raise ValueError(stat)


def diff_or_none(left: Any, right: Any) -> float | None:
    left = numeric_or_none(left)
    right = numeric_or_none(right)
    return None if left is None or right is None else left - right


def ratio_or_none(left: Any, right: Any) -> float | None:
    left = numeric_or_none(left)
    right = numeric_or_none(right)
    if left is None or right is None or abs(right) < 1e-12:
        return None
    return left / right


def parse_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


def empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def fmt_pct(value: Any) -> str:
    value = numeric_or_none(value)
    return "NA" if value is None else f"{value:.2%}"


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise
