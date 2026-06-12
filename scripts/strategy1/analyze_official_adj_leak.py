#!/usr/bin/env python3
"""Measure raw-price official ledger adjustment leakage for Strategy1."""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from google.cloud import bigquery

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.strategy1_cloudrun.bq_io import (  # noqa: E402
    job_audit_dict,
    json_dumps_strict,
    make_client,
    query_dataframe_with_job,
    upload_directory_to_gcs,
)


DEFAULT_PROJECT = "data-aquarium"
DEFAULT_LOCATION = "asia-east2"
DEFAULT_START_DATE = "2021-01-04"
DEFAULT_END_DATE = "2026-06-09"
DEFAULT_REPORT_MD = "docs/分析-官方Ledger复权漏损量化-20260612.md"
DEFAULT_METRICS_CSV = "docs/analysis_official_ledger_adj_leak_20260612_metrics.csv"
DEFAULT_OUTPUT_DIR = "reports/strategy1/official_adj_leak/analysis_date=20260612"
DEFAULT_GCS_URI = "gs://ashare-artifacts/reports/strategy1/official_adj_leak/analysis_date=20260612"
DEFAULT_BENCHMARK_SEC_CODE = "000852.SH"
TRUE5Y_BACKTEST_ID = "bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01"
EFFECTIVE_BACKTEST_ID = "bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02"
TRADING_DAYS_PER_YEAR = 252.0
CRUNCH_START = "2024-01-01"
CRUNCH_END = "2024-02-07"
EVENT_FACTOR_JUMP_THRESHOLD = 0.20
FACTOR_EVENT_EPS = 1e-9
CONTRIBUTION_EPS = 1e-12


DEFAULT_BACKTESTS = (
    ("true5y_research_baseline", TRUE5Y_BACKTEST_ID),
    ("effective_window_historical_reference", EFFECTIVE_BACKTEST_ID),
)


@dataclass(frozen=True)
class BacktestSpec:
    label: str
    backtest_id: str


@dataclass(frozen=True)
class AnalysisConfig:
    project: str
    location: str
    start_date: str
    end_date: str
    benchmark_sec_code: str
    output_dir: Path
    report_md: Path
    metrics_csv: Path
    gcs_uri: str
    skip_gcs_upload: bool
    skip_report: bool
    residual_max_abs_tolerance: float
    backtests: tuple[BacktestSpec, ...]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only measurement of NAV leakage caused by raw-price, constant-share "
            "official ledger convention. Use --backtest-id label=id to override defaults."
        )
    )
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--location", default=DEFAULT_LOCATION)
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    parser.add_argument("--benchmark-sec-code", default=DEFAULT_BENCHMARK_SEC_CODE)
    parser.add_argument(
        "--backtest-id",
        action="append",
        default=[],
        help="Backtest id to analyze. Accepts id or label=id. Repeat for multiple runs.",
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-md", default=DEFAULT_REPORT_MD)
    parser.add_argument("--metrics-csv", default=DEFAULT_METRICS_CSV)
    parser.add_argument("--gcs-uri", default=DEFAULT_GCS_URI)
    parser.add_argument("--skip-gcs-upload", action="store_true")
    parser.add_argument("--skip-report", action="store_true")
    parser.add_argument("--residual-max-abs-tolerance", type=float, default=1e-6)
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> AnalysisConfig:
    return AnalysisConfig(
        project=args.project,
        location=args.location,
        start_date=args.start_date,
        end_date=args.end_date,
        benchmark_sec_code=args.benchmark_sec_code,
        output_dir=Path(args.output_dir),
        report_md=Path(args.report_md),
        metrics_csv=Path(args.metrics_csv),
        gcs_uri=args.gcs_uri,
        skip_gcs_upload=args.skip_gcs_upload,
        skip_report=args.skip_report,
        residual_max_abs_tolerance=args.residual_max_abs_tolerance,
        backtests=parse_backtests(args.backtest_id),
    )


def parse_backtests(values: list[str]) -> tuple[BacktestSpec, ...]:
    if not values:
        return tuple(BacktestSpec(label, backtest_id) for label, backtest_id in DEFAULT_BACKTESTS)
    specs: list[BacktestSpec] = []
    for raw in values:
        if "=" in raw:
            label, backtest_id = raw.split("=", 1)
        else:
            backtest_id = raw
            label = backtest_id
        label = label.strip()
        backtest_id = backtest_id.strip()
        if not label or not backtest_id:
            raise ValueError(f"invalid --backtest-id value: {raw!r}")
        specs.append(BacktestSpec(label=label, backtest_id=backtest_id))
    return tuple(specs)


def main(argv: list[str] | None = None) -> int:
    cfg = config_from_args(parse_args(argv))
    client = make_client(cfg.project, cfg.location)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    all_metrics: list[pd.DataFrame] = []
    all_daily: list[pd.DataFrame] = []
    all_events: list[pd.DataFrame] = []
    all_annual: list[pd.DataFrame] = []
    all_event_summary: list[pd.DataFrame] = []
    all_residual: list[pd.DataFrame] = []
    all_top_events: list[pd.DataFrame] = []
    audit_jobs: list[dict[str, Any]] = []

    for spec in cfg.backtests:
        print(f"Analyzing {spec.label}: {spec.backtest_id}", flush=True)
        result = analyze_backtest(client, cfg, spec)
        audit_jobs.extend(result["audit_jobs"])
        write_backtest_artifacts(cfg.output_dir, spec, result)
        all_metrics.append(result["metrics"])
        all_daily.append(result["daily"])
        all_events.append(result["events"])
        all_annual.append(result["annual"])
        all_event_summary.append(result["event_summary"])
        all_residual.append(result["residual_stats"])
        all_top_events.append(result["top_events"])

    metrics = pd.concat(all_metrics, ignore_index=True)
    daily = pd.concat(all_daily, ignore_index=True)
    events = pd.concat(all_events, ignore_index=True)
    annual = pd.concat(all_annual, ignore_index=True)
    event_summary = pd.concat(all_event_summary, ignore_index=True)
    residual_stats = pd.concat(all_residual, ignore_index=True)
    top_events = pd.concat(all_top_events, ignore_index=True)

    cfg.metrics_csv.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(cfg.metrics_csv, index=False)
    write_json(cfg.output_dir / "bigquery_job_audit.json", {"jobs": audit_jobs})

    uploaded: list[str] = []
    if not cfg.skip_gcs_upload:
        uploaded = upload_directory_to_gcs(cfg.project, cfg.output_dir, cfg.gcs_uri)
        print(f"Uploaded {len(uploaded)} files to {cfg.gcs_uri}", flush=True)

    if not cfg.skip_report:
        cfg.report_md.parent.mkdir(parents=True, exist_ok=True)
        cfg.report_md.write_text(
            build_report(
                cfg=cfg,
                metrics=metrics,
                annual=annual,
                event_summary=event_summary,
                residual_stats=residual_stats,
                top_events=top_events,
                uploaded=uploaded,
            ),
            encoding="utf-8",
        )

    print_summary(metrics, residual_stats)
    print(f"Metrics CSV written: {cfg.metrics_csv}")
    if not cfg.skip_report:
        print(f"Report written: {cfg.report_md}")
    return 0


def analyze_backtest(client: bigquery.Client, cfg: AnalysisConfig, spec: BacktestSpec) -> dict[str, Any]:
    nav, nav_job = fetch_nav(client, cfg, spec)
    contributions, contrib_job = fetch_position_contributions(client, cfg, spec)
    trade_flags, trade_job = fetch_trade_flags(client, cfg, spec)
    benchmark, bench_job = fetch_benchmark(client, cfg)

    validate_nav(nav, spec)
    validate_contributions(contributions, spec)

    daily = build_daily_frame(nav, contributions, trade_flags, benchmark, spec)
    validate_no_trade_residuals(daily, spec, cfg.residual_max_abs_tolerance)

    events = build_event_frame(contributions, spec)
    metrics = build_metrics_frame(daily, spec)
    annual = build_annual_frame(daily, events, spec)
    event_summary = build_event_summary(events, spec)
    residual_stats = build_residual_stats(daily, spec)
    top_events = build_top_events(events, spec)

    return {
        "daily": daily,
        "events": events,
        "metrics": metrics,
        "annual": annual,
        "event_summary": event_summary,
        "residual_stats": residual_stats,
        "top_events": top_events,
        "audit_jobs": [
            job_audit_dict(nav_job),
            job_audit_dict(contrib_job),
            job_audit_dict(trade_job),
            job_audit_dict(bench_job),
        ],
    }


def fetch_nav(
    client: bigquery.Client,
    cfg: AnalysisConfig,
    spec: BacktestSpec,
) -> tuple[pd.DataFrame, bigquery.QueryJob]:
    sql = f"""
    SELECT
      trade_date,
      nav,
      daily_return,
      benchmark_return,
      cash_cny,
      net_value_cny,
      gross_exposure,
      turnover_cny,
      cost_cny
    FROM `{cfg.project}.ashare_research.research_backtest_nav_daily`
    WHERE backtest_id = @backtest_id
      AND trade_date BETWEEN @start_date AND @end_date
    ORDER BY trade_date
    """
    return query_dataframe_with_job(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("backtest_id", "STRING", spec.backtest_id),
            bigquery.ScalarQueryParameter("start_date", "DATE", cfg.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", cfg.end_date),
        ],
        labels={"step": "official_adj_nav_read", "mode": "readonly", "backtest": spec.label},
    )


def fetch_position_contributions(
    client: bigquery.Client,
    cfg: AnalysisConfig,
    spec: BacktestSpec,
) -> tuple[pd.DataFrame, bigquery.QueryJob]:
    sql = f"""
    WITH calendar AS (
      SELECT
        cal_date AS trade_date,
        LAG(cal_date) OVER (ORDER BY cal_date) AS prev_trade_date
      FROM `{cfg.project}.ashare_dim.dim_trade_calendar`
      WHERE exchange = 'SSE'
        AND is_open = 1
        AND cal_date BETWEEN @start_date AND @end_date
    ),
    held_sec AS (
      SELECT DISTINCT sec_code
      FROM `{cfg.project}.ashare_research.research_backtest_position_daily`
      WHERE backtest_id = @backtest_id
        AND trade_date BETWEEN @start_date AND @end_date
        AND weight IS NOT NULL
        AND ABS(weight) > 0
    ),
    price_base AS (
      SELECT
        px.trade_date,
        px.sec_code,
        px.close AS raw_close,
        px.close_hfq,
        px.adj_factor,
        LAST_VALUE(px.close IGNORE NULLS) OVER price_window AS raw_close_ffill,
        LAST_VALUE(px.close_hfq IGNORE NULLS) OVER price_window AS close_hfq_ffill,
        LAST_VALUE(px.adj_factor IGNORE NULLS) OVER price_window AS factor_ffill
      FROM `{cfg.project}.ashare_dwd.dwd_stock_eod_price` AS px
      JOIN held_sec AS held
        ON held.sec_code = px.sec_code
      WHERE px.trade_date BETWEEN @start_date AND @end_date
      WINDOW price_window AS (
        PARTITION BY px.sec_code
        ORDER BY px.trade_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
      )
    ),
    price_ret AS (
      SELECT
        trade_date,
        sec_code,
        raw_close,
        close_hfq,
        adj_factor,
        raw_close_ffill,
        close_hfq_ffill,
        factor_ffill,
        LAG(raw_close_ffill) OVER (PARTITION BY sec_code ORDER BY trade_date) AS prev_raw_close_ffill,
        LAG(close_hfq_ffill) OVER (PARTITION BY sec_code ORDER BY trade_date) AS prev_close_hfq_ffill,
        LAG(factor_ffill) OVER (PARTITION BY sec_code ORDER BY trade_date) AS prev_factor_ffill
      FROM price_base
    )
    SELECT
      cal.trade_date,
      cal.prev_trade_date,
      pos.sec_code,
      pos.weight AS prev_weight,
      pos.shares AS prev_shares,
      pos.close AS prev_ledger_close,
      ret.raw_close,
      ret.close_hfq,
      ret.adj_factor,
      ret.raw_close_ffill,
      ret.close_hfq_ffill,
      ret.prev_raw_close_ffill,
      ret.prev_close_hfq_ffill,
      SAFE_DIVIDE(ret.raw_close_ffill, ret.prev_raw_close_ffill) - 1.0 AS raw_return,
      SAFE_DIVIDE(ret.close_hfq_ffill, ret.prev_close_hfq_ffill) - 1.0 AS hfq_return,
      SAFE_DIVIDE(ret.factor_ffill, ret.prev_factor_ffill) - 1.0 AS factor_jump,
      pos.weight * (SAFE_DIVIDE(ret.raw_close_ffill, ret.prev_raw_close_ffill) - 1.0) AS raw_contribution,
      pos.weight * (
        (SAFE_DIVIDE(ret.close_hfq_ffill, ret.prev_close_hfq_ffill) - 1.0)
        - (SAFE_DIVIDE(ret.raw_close_ffill, ret.prev_raw_close_ffill) - 1.0)
      ) AS leak_contribution
    FROM calendar AS cal
    JOIN `{cfg.project}.ashare_research.research_backtest_position_daily` AS pos
      ON pos.backtest_id = @backtest_id
     AND pos.trade_date = cal.prev_trade_date
     AND pos.trade_date BETWEEN @start_date AND @end_date
     AND pos.weight IS NOT NULL
     AND ABS(pos.weight) > 0
    LEFT JOIN price_ret AS ret
      ON ret.trade_date = cal.trade_date
     AND ret.sec_code = pos.sec_code
    WHERE cal.prev_trade_date IS NOT NULL
    ORDER BY cal.trade_date, pos.sec_code
    """
    return query_dataframe_with_job(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("backtest_id", "STRING", spec.backtest_id),
            bigquery.ScalarQueryParameter("start_date", "DATE", cfg.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", cfg.end_date),
        ],
        labels={"step": "official_adj_position_read", "mode": "readonly", "backtest": spec.label},
    )


def fetch_trade_flags(
    client: bigquery.Client,
    cfg: AnalysisConfig,
    spec: BacktestSpec,
) -> tuple[pd.DataFrame, bigquery.QueryJob]:
    sql = f"""
    SELECT
      trade_date,
      COUNT(*) AS order_rows,
      COUNTIF(fill_status IN ('FILLED', 'FILLED_SCALED_CASH')) AS filled_trade_count,
      SUM(IF(fill_status IN ('FILLED', 'FILLED_SCALED_CASH'), ABS(filled_shares), 0.0)) AS filled_shares_abs,
      SUM(IF(fill_status IN ('FILLED', 'FILLED_SCALED_CASH'), turnover_cny, 0.0)) AS filled_turnover_cny,
      SUM(IF(fill_status IN ('FILLED', 'FILLED_SCALED_CASH'), fee_cny + tax_cny + slippage_cny, 0.0)) AS filled_cost_cny
    FROM `{cfg.project}.ashare_research.research_backtest_trade_daily`
    WHERE backtest_id = @backtest_id
      AND trade_date BETWEEN @start_date AND @end_date
    GROUP BY trade_date
    ORDER BY trade_date
    """
    return query_dataframe_with_job(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("backtest_id", "STRING", spec.backtest_id),
            bigquery.ScalarQueryParameter("start_date", "DATE", cfg.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", cfg.end_date),
        ],
        labels={"step": "official_adj_trade_read", "mode": "readonly", "backtest": spec.label},
    )


def fetch_benchmark(
    client: bigquery.Client,
    cfg: AnalysisConfig,
) -> tuple[pd.DataFrame, bigquery.QueryJob]:
    sql = f"""
    SELECT trade_date, SAFE_DIVIDE(pct_chg, 100.0) AS benchmark_return_from_index
    FROM `{cfg.project}.ashare_dwd.dwd_index_eod`
    WHERE sec_code = @benchmark_sec_code
      AND trade_date BETWEEN @start_date AND @end_date
    ORDER BY trade_date
    """
    return query_dataframe_with_job(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("benchmark_sec_code", "STRING", cfg.benchmark_sec_code),
            bigquery.ScalarQueryParameter("start_date", "DATE", cfg.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", cfg.end_date),
        ],
        labels={"step": "official_adj_benchmark_read", "mode": "readonly", "backtest": "shared"},
    )


def validate_nav(nav: pd.DataFrame, spec: BacktestSpec) -> None:
    if nav.empty:
        raise RuntimeError(f"no NAV rows found for {spec.backtest_id}")
    if nav["trade_date"].duplicated().any():
        raise RuntimeError(f"NAV duplicate trade_date rows for {spec.backtest_id}")
    if nav["daily_return"].notna().sum() < 100:
        raise RuntimeError(f"unexpectedly few daily returns for {spec.backtest_id}")


def validate_contributions(contributions: pd.DataFrame, spec: BacktestSpec) -> None:
    if contributions.empty:
        raise RuntimeError(f"no position contribution rows found for {spec.backtest_id}")
    required = ["raw_return", "hfq_return", "leak_contribution", "raw_contribution"]
    missing = contributions[required].isna().any(axis=1)
    if bool(missing.any()):
        sample = contributions.loc[missing, ["trade_date", "sec_code", *required]].head(10)
        raise RuntimeError(f"missing contribution return inputs for {spec.backtest_id}: {sample.to_dict('records')}")


def build_daily_frame(
    nav: pd.DataFrame,
    contributions: pd.DataFrame,
    trade_flags: pd.DataFrame,
    benchmark: pd.DataFrame,
    spec: BacktestSpec,
) -> pd.DataFrame:
    nav = with_date(nav)
    contributions = with_date(contributions)
    trade_flags = with_date(trade_flags) if not trade_flags.empty else empty_trade_flags()
    benchmark = with_date(benchmark)

    aggregate = (
        contributions.groupby("trade_date", as_index=False)
        .agg(
            prev_weight_sum=("prev_weight", "sum"),
            raw_replication_return=("raw_contribution", "sum"),
            daily_leak=("leak_contribution", "sum"),
            held_position_count=("sec_code", "nunique"),
            event_row_count=("factor_jump", lambda s: int((s.abs() > FACTOR_EVENT_EPS).sum())),
        )
    )
    daily = nav.merge(aggregate, on="trade_date", how="left", validate="one_to_one")
    daily = daily.merge(trade_flags, on="trade_date", how="left", validate="one_to_one")
    daily = daily.merge(benchmark, on="trade_date", how="left", validate="one_to_one")

    fill_zero_cols = [
        "prev_weight_sum",
        "raw_replication_return",
        "daily_leak",
        "held_position_count",
        "event_row_count",
        "order_rows",
        "filled_trade_count",
        "filled_shares_abs",
        "filled_turnover_cny",
        "filled_cost_cny",
    ]
    for col in fill_zero_cols:
        if col not in daily.columns:
            daily[col] = 0.0
        daily[col] = daily[col].fillna(0.0)

    daily["benchmark_return_effective"] = daily["benchmark_return_from_index"].combine_first(daily["benchmark_return"])
    daily["residual_raw_replication"] = daily["daily_return"] - daily["raw_replication_return"]
    daily["corrected_daily_return"] = daily["daily_return"] + daily["daily_leak"]
    daily.loc[daily["daily_return"].isna(), "corrected_daily_return"] = np.nan
    daily["base_nav_recalc"] = nav_from_returns(daily["daily_return"], initial_nav=float(daily["nav"].iloc[0]))
    daily["corrected_nav"] = nav_from_returns(daily["corrected_daily_return"], initial_nav=float(daily["nav"].iloc[0]))
    daily["leak_cumulative_pp"] = daily["daily_leak"].fillna(0.0).cumsum() * 100.0
    daily["backtest_label"] = spec.label
    daily["backtest_id"] = spec.backtest_id
    return daily


def build_event_frame(contributions: pd.DataFrame, spec: BacktestSpec) -> pd.DataFrame:
    events = contributions.copy()
    events["trade_date"] = pd.to_datetime(events["trade_date"]).dt.date
    events = events[
        (events["factor_jump"].abs() > FACTOR_EVENT_EPS)
        & (events["leak_contribution"].abs() > CONTRIBUTION_EPS)
        & (events["prev_weight"].abs() > CONTRIBUTION_EPS)
    ].copy()
    if events.empty:
        return pd.DataFrame(
            columns=[
                "backtest_label",
                "backtest_id",
                "trade_date",
                "sec_code",
                "event_type",
                "factor_jump",
                "prev_weight",
                "raw_return",
                "hfq_return",
                "leak_contribution",
                "leak_contribution_pp",
            ]
        )
    events["event_type"] = np.where(
        events["factor_jump"].abs() > EVENT_FACTOR_JUMP_THRESHOLD,
        "bonus_split_type_abs_factor_jump_gt_20pct",
        "dividend_or_small_event_type",
    )
    events["leak_contribution_pp"] = events["leak_contribution"] * 100.0
    events["backtest_label"] = spec.label
    events["backtest_id"] = spec.backtest_id
    keep = [
        "backtest_label",
        "backtest_id",
        "trade_date",
        "prev_trade_date",
        "sec_code",
        "event_type",
        "factor_jump",
        "prev_weight",
        "raw_return",
        "hfq_return",
        "leak_contribution",
        "leak_contribution_pp",
        "raw_close",
        "close_hfq",
        "adj_factor",
    ]
    return events[keep].sort_values(["trade_date", "sec_code"]).reset_index(drop=True)


def build_metrics_frame(daily: pd.DataFrame, spec: BacktestSpec) -> pd.DataFrame:
    before = compute_performance_metrics(
        daily,
        return_col="daily_return",
        nav_col="nav",
        variant="before_raw_official",
        spec=spec,
    )
    after = compute_performance_metrics(
        daily,
        return_col="corrected_daily_return",
        nav_col="corrected_nav",
        variant="after_hfq_total_return_proxy",
        spec=spec,
    )
    rows = [before, after]
    delta = {
        "backtest_label": spec.label,
        "backtest_id": spec.backtest_id,
        "variant": "delta_after_minus_before",
    }
    for key in [
        "total_return",
        "cagr",
        "annual_vol",
        "contract_sharpe",
        "max_drawdown",
        "calmar",
        "crunch_return",
        "crunch_excess_return",
    ]:
        delta[key] = after[key] - before[key]
    delta["max_drawdown_peak_date_before"] = before["max_drawdown_peak_date"]
    delta["max_drawdown_peak_date_after"] = after["max_drawdown_peak_date"]
    delta["max_drawdown_trough_date_before"] = before["max_drawdown_trough_date"]
    delta["max_drawdown_trough_date_after"] = after["max_drawdown_trough_date"]
    delta["max_drawdown_dates_moved"] = (
        before["max_drawdown_peak_date"] != after["max_drawdown_peak_date"]
        or before["max_drawdown_trough_date"] != after["max_drawdown_trough_date"]
    )
    delta["return_period_count"] = before["return_period_count"]
    delta["nav_row_count"] = before["nav_row_count"]
    rows.append(delta)
    return pd.DataFrame(rows)


def compute_performance_metrics(
    daily: pd.DataFrame,
    *,
    return_col: str,
    nav_col: str,
    variant: str,
    spec: BacktestSpec,
) -> dict[str, Any]:
    returns = daily[return_col].dropna().astype(float)
    return_period_count = int(len(returns))
    total_return = cumulative_return(returns) - 1.0
    cagr = compound_annualized_return(total_return, return_period_count)
    annual_vol = float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR)) if len(returns) >= 2 else math.nan
    contract_sharpe = safe_ratio(cagr, annual_vol)
    max_dd, peak_date, trough_date = max_drawdown(daily["trade_date"], daily[nav_col])
    calmar = safe_ratio(cagr, abs(max_dd))

    crunch = daily[
        (pd.to_datetime(daily["trade_date"]) >= pd.Timestamp(CRUNCH_START))
        & (pd.to_datetime(daily["trade_date"]) <= pd.Timestamp(CRUNCH_END))
    ]
    crunch_return = cumulative_return(crunch[return_col].dropna().astype(float)) - 1.0
    crunch_benchmark_return = cumulative_return(crunch["benchmark_return_effective"].dropna().astype(float)) - 1.0

    return {
        "backtest_label": spec.label,
        "backtest_id": spec.backtest_id,
        "variant": variant,
        "total_return": total_return,
        "cagr": cagr,
        "annual_vol": annual_vol,
        "contract_sharpe": contract_sharpe,
        "max_drawdown": max_dd,
        "max_drawdown_peak_date": peak_date.isoformat(),
        "max_drawdown_trough_date": trough_date.isoformat(),
        "calmar": calmar,
        "crunch_start": CRUNCH_START,
        "crunch_end": CRUNCH_END,
        "crunch_return": crunch_return,
        "crunch_benchmark_return": crunch_benchmark_return,
        "crunch_excess_return": crunch_return - crunch_benchmark_return,
        "return_period_count": return_period_count,
        "nav_row_count": int(len(daily)),
    }


def build_annual_frame(daily: pd.DataFrame, events: pd.DataFrame, spec: BacktestSpec) -> pd.DataFrame:
    work = daily.copy()
    work["year"] = pd.to_datetime(work["trade_date"]).dt.year
    event_by_year = event_contribution_by_year(events)
    rows: list[dict[str, Any]] = []
    for year, group in work.groupby("year", sort=True):
        base_total = cumulative_return(group["daily_return"].dropna().astype(float)) - 1.0
        corrected_total = cumulative_return(group["corrected_daily_return"].dropna().astype(float)) - 1.0
        rows.append(
            {
                "backtest_label": spec.label,
                "backtest_id": spec.backtest_id,
                "year": int(year),
                "base_total_return": base_total,
                "corrected_total_return": corrected_total,
                "delta_total_return_pp": (corrected_total - base_total) * 100.0,
                "daily_leak_sum_pp": float(group["daily_leak"].sum() * 100.0),
                "event_count": int(event_by_year.get((int(year), "event_count"), 0)),
                "bonus_split_contribution_pp": float(event_by_year.get((int(year), "bonus_split"), 0.0) * 100.0),
                "dividend_small_contribution_pp": float(event_by_year.get((int(year), "dividend_small"), 0.0) * 100.0),
            }
        )
    return pd.DataFrame(rows)


def event_contribution_by_year(events: pd.DataFrame) -> dict[tuple[int, str], float | int]:
    if events.empty:
        return {}
    work = events.copy()
    work["year"] = pd.to_datetime(work["trade_date"]).dt.year
    out: dict[tuple[int, str], float | int] = {}
    for year, group in work.groupby("year"):
        out[(int(year), "event_count")] = int(len(group))
        out[(int(year), "bonus_split")] = float(
            group.loc[group["event_type"].str.startswith("bonus_split"), "leak_contribution"].sum()
        )
        out[(int(year), "dividend_small")] = float(
            group.loc[group["event_type"].str.startswith("dividend"), "leak_contribution"].sum()
        )
    return out


def build_event_summary(events: pd.DataFrame, spec: BacktestSpec) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame(
            [
                {
                    "backtest_label": spec.label,
                    "backtest_id": spec.backtest_id,
                    "event_type": "all_events",
                    "event_count": 0,
                    "cumulative_nav_contribution_pp": 0.0,
                    "abs_nav_contribution_pp": 0.0,
                    "avg_prev_weight": math.nan,
                }
            ]
        )
    rows = []
    for event_type, group in events.groupby("event_type", sort=True):
        rows.append(event_summary_row(spec, event_type, group))
    rows.append(event_summary_row(spec, "all_events", events))
    return pd.DataFrame(rows)


def event_summary_row(spec: BacktestSpec, event_type: str, group: pd.DataFrame) -> dict[str, Any]:
    return {
        "backtest_label": spec.label,
        "backtest_id": spec.backtest_id,
        "event_type": event_type,
        "event_count": int(len(group)),
        "cumulative_nav_contribution_pp": float(group["leak_contribution"].sum() * 100.0),
        "abs_nav_contribution_pp": float(group["leak_contribution"].abs().sum() * 100.0),
        "avg_prev_weight": float(group["prev_weight"].mean()) if len(group) else math.nan,
    }


def build_residual_stats(daily: pd.DataFrame, spec: BacktestSpec) -> pd.DataFrame:
    all_days = daily[daily["daily_return"].notna()].copy()
    no_trade = no_filled_trade_days(daily)
    rows = [
        residual_stat_row(spec, "all_return_days", all_days["residual_raw_replication"]),
        residual_stat_row(spec, "no_filled_trade_days", no_trade["residual_raw_replication"]),
    ]
    return pd.DataFrame(rows)


def residual_stat_row(spec: BacktestSpec, scope: str, residual: pd.Series) -> dict[str, Any]:
    values = residual.dropna().astype(float)
    abs_values = values.abs()
    return {
        "backtest_label": spec.label,
        "backtest_id": spec.backtest_id,
        "scope": scope,
        "n_days": int(len(values)),
        "mean_residual": float(values.mean()) if len(values) else math.nan,
        "median_residual": float(values.median()) if len(values) else math.nan,
        "p95_abs_residual": float(abs_values.quantile(0.95)) if len(values) else math.nan,
        "p99_abs_residual": float(abs_values.quantile(0.99)) if len(values) else math.nan,
        "max_abs_residual": float(abs_values.max()) if len(values) else math.nan,
    }


def build_top_events(events: pd.DataFrame, spec: BacktestSpec, n: int = 10) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame(
            columns=[
                "backtest_label",
                "backtest_id",
                "rank",
                "trade_date",
                "sec_code",
                "event_type",
                "factor_jump",
                "prev_weight",
                "leak_contribution_pp",
            ]
        )
    top = events.assign(abs_pp=events["leak_contribution_pp"].abs()).sort_values("abs_pp", ascending=False).head(n)
    top = top.copy()
    top["rank"] = np.arange(1, len(top) + 1)
    cols = [
        "backtest_label",
        "backtest_id",
        "rank",
        "trade_date",
        "sec_code",
        "event_type",
        "factor_jump",
        "prev_weight",
        "raw_return",
        "hfq_return",
        "leak_contribution_pp",
    ]
    return top[cols].reset_index(drop=True)


def validate_no_trade_residuals(daily: pd.DataFrame, spec: BacktestSpec, tolerance: float) -> None:
    no_trade = no_filled_trade_days(daily)
    if no_trade.empty:
        raise RuntimeError(f"no no-filled-trade return days available for residual check: {spec.backtest_id}")
    max_abs = float(no_trade["residual_raw_replication"].abs().max())
    if max_abs > tolerance:
        sample = (
            no_trade.assign(abs_residual=no_trade["residual_raw_replication"].abs())
            .sort_values("abs_residual", ascending=False)
            .head(10)[
                [
                    "trade_date",
                    "daily_return",
                    "raw_replication_return",
                    "residual_raw_replication",
                    "prev_weight_sum",
                    "held_position_count",
                ]
            ]
        )
        raise RuntimeError(
            f"raw-return residual check failed for {spec.backtest_id}: "
            f"max_abs={max_abs:.6g}, tolerance={tolerance:.6g}, sample={sample.to_dict('records')}"
        )


def no_filled_trade_days(daily: pd.DataFrame) -> pd.DataFrame:
    return daily[
        daily["daily_return"].notna()
        & (daily["filled_trade_count"].fillna(0).astype(float) == 0.0)
    ].copy()


def write_backtest_artifacts(output_dir: Path, spec: BacktestSpec, result: dict[str, Any]) -> None:
    safe_label = safe_path_part(spec.label)
    prefix = output_dir / safe_label
    prefix.mkdir(parents=True, exist_ok=True)
    result["daily"].to_csv(prefix / "daily_adjusted_returns.csv", index=False)
    result["events"].to_csv(prefix / "event_contributions.csv", index=False)
    result["annual"].to_csv(prefix / "annual_decomposition.csv", index=False)
    result["event_summary"].to_csv(prefix / "event_summary.csv", index=False)
    result["residual_stats"].to_csv(prefix / "residual_stats.csv", index=False)
    result["top_events"].to_csv(prefix / "top10_events.csv", index=False)


def print_summary(metrics: pd.DataFrame, residual_stats: pd.DataFrame) -> None:
    deltas = metrics[metrics["variant"] == "delta_after_minus_before"].copy()
    for row in deltas.itertuples(index=False):
        print(
            f"{row.backtest_label}: "
            f"CAGR delta={fmt_pp(row.cagr)}, "
            f"Calmar delta={fmt_num(row.calmar)}, "
            f"Crunch excess delta={fmt_pp(row.crunch_excess_return)}"
        )
    no_trade = residual_stats[residual_stats["scope"] == "no_filled_trade_days"]
    for row in no_trade.itertuples(index=False):
        print(
            f"{row.backtest_label}: no-trade residual "
            f"n={row.n_days}, p99_abs={row.p99_abs_residual:.3g}, max_abs={row.max_abs_residual:.3g}"
        )


def build_report(
    *,
    cfg: AnalysisConfig,
    metrics: pd.DataFrame,
    annual: pd.DataFrame,
    event_summary: pd.DataFrame,
    residual_stats: pd.DataFrame,
    top_events: pd.DataFrame,
    uploaded: list[str],
) -> str:
    true_delta = metrics[
        (metrics["backtest_label"] == "true5y_research_baseline")
        & (metrics["variant"] == "delta_after_minus_before")
    ]
    if true_delta.empty:
        true_delta = metrics[metrics["variant"] == "delta_after_minus_before"].head(1)
    delta_row = true_delta.iloc[0]
    verdict = preregistered_verdict(delta_row)

    perf_table = performance_table(metrics)
    annual_table = annual.copy()
    event_table = event_summary.copy()
    residual_table = residual_stats.copy()
    top_table = top_events.copy()

    uploaded_lines = "\n".join(f"- `{uri}`" for uri in uploaded) if uploaded else "- GCS upload skipped."
    daily_gcs = f"{cfg.gcs_uri.rstrip('/')}/<backtest_label>/daily_adjusted_returns.csv"
    events_gcs = f"{cfg.gcs_uri.rstrip('/')}/<backtest_label>/event_contributions.csv"

    return f"""> 文档维护：GPT-5.5（最近更新 2026-06-12）

# 分析：官方 Ledger 复权漏损量化（2026-06-12）

## 预登记判据

本任务只做测量，不修改 ledger、不改变 `DECISION_LOG` 中“未复权口径、持有期除权简化”的既有接受约定。

以 true-five-year research baseline 的修正幅度为准：

- 若 CAGR 改善 >= +1.00pp，或 Calmar 改善 >= +0.05：建议立 PRD 修 ledger，并排在 Phase 2 之前；
- 若幅度小于上述阈值：维持既有约定，并把量化幅度写入 `KNOWN_CONSTRAINTS` 永久披露。

本次结果：true5y CAGR 变化 `{fmt_pp(delta_row['cagr'])}`，Calmar 变化 `{fmt_num(delta_row['calmar'])}`。判据结论：**{verdict}**。

## 口径声明

- 主结果 backtest：`{TRUE5Y_BACKTEST_ID}`（DECISION-20260612-02 已采纳为研究 baseline；baseline != accepted，仍不得 promotion）。
- 历史参照 backtest：`{EFFECTIVE_BACKTEST_ID}`。
- 窗口：`{cfg.start_date}` 至 `{cfg.end_date}`。
- 测量公式：`daily_leak = SUM(prev_day_weight * (hfq_return - raw_return))`。
- 修正收益：`corrected_daily_return = official_daily_return + daily_leak`。
- `hfq` 修正近似总回报口径，隐含分红再投资；真实 ledger 修复应是现金入账和股数/价格状态修正。本文结果只用于量化方向和量级。
- 结论外推到其他 run：方向通常相同，幅度随持仓股票的分红、送转和除权倾向变化。

## 指标对照

{markdown_table(perf_table)}

## 对账校验

硬门：无 filled trade 的交易日上，`SUM(prev_weight * raw_return)` 应复现 official `daily_return`。下表 residual = official `daily_return - raw_replication_return`。

{markdown_table(format_residual_table(residual_table))}

该校验通过后，修正前后指标才有解释意义。

## 年度分解

{markdown_table(format_annual_table(annual_table))}

## 事件类型分解

事件分类：`abs(adj_factor_t / adj_factor_{{t-1}} - 1) > 20%` 记为送转型，其余 factor jump 记为分红/小事件型。贡献为对当日 NAV 的百分点影响。

{markdown_table(format_event_summary_table(event_table))}

## Top10 单事件

{markdown_table(format_top_events_table(top_table))}

## Artifact

- 入库小结果 CSV：`{cfg.metrics_csv.as_posix()}`
- 逐日序列 GCS：`{daily_gcs}`
- 逐票事件明细 GCS：`{events_gcs}`
- 本地临时目录（git ignored）：`{cfg.output_dir.as_posix()}`
- BigQuery job audit：`{cfg.gcs_uri.rstrip('/')}/bigquery_job_audit.json`

上传对象：

{uploaded_lines}

## 解释边界

本报告没有重开 ledger 约定，也没有把任何结果标记为 accepted / promotion。若 owner 后续决定修 ledger，需要单独 PRD 明确现金分红入账、送转股数调整、停牌/不可交易日处理、成本与恢复 QA，并重新跑 formal baseline。
"""


def preregistered_verdict(delta_row: pd.Series) -> str:
    cagr_delta = float(delta_row["cagr"])
    calmar_delta = float(delta_row["calmar"])
    if cagr_delta >= 0.01 or calmar_delta >= 0.05:
        return "建议立 PRD 修 ledger，并排在 Phase 2 之前"
    return "幅度小，维持约定并永久披露量化影响"


def performance_table(metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in metrics.itertuples(index=False):
        if row.variant == "delta_after_minus_before":
            rows.append(
                {
                    "backtest": row.backtest_label,
                    "variant": "delta",
                    "CAGR": fmt_pp(row.cagr),
                    "MaxDD": fmt_pp(row.max_drawdown),
                    "Peak": getattr(row, "max_drawdown_peak_date_after", ""),
                    "Trough": getattr(row, "max_drawdown_trough_date_after", ""),
                    "MDD dates moved": str(bool(getattr(row, "max_drawdown_dates_moved", False))),
                    "Sharpe": fmt_num(row.contract_sharpe),
                    "Calmar": fmt_num(row.calmar),
                    "Crunch ret": fmt_pp(row.crunch_return),
                    "Crunch excess": fmt_pp(row.crunch_excess_return),
                }
            )
        else:
            rows.append(
                {
                    "backtest": row.backtest_label,
                    "variant": "before" if row.variant.startswith("before") else "after",
                    "CAGR": fmt_pct(row.cagr),
                    "MaxDD": fmt_pct(row.max_drawdown),
                    "Peak": row.max_drawdown_peak_date,
                    "Trough": row.max_drawdown_trough_date,
                    "MDD dates moved": "",
                    "Sharpe": fmt_num(row.contract_sharpe),
                    "Calmar": fmt_num(row.calmar),
                    "Crunch ret": fmt_pct(row.crunch_return),
                    "Crunch excess": fmt_pct(row.crunch_excess_return),
                }
            )
    return pd.DataFrame(rows)


def format_annual_table(annual: pd.DataFrame) -> pd.DataFrame:
    out = annual.copy()
    keep = [
        "backtest_label",
        "year",
        "base_total_return",
        "corrected_total_return",
        "delta_total_return_pp",
        "daily_leak_sum_pp",
        "event_count",
        "bonus_split_contribution_pp",
        "dividend_small_contribution_pp",
    ]
    out = out[keep]
    out["base_total_return"] = out["base_total_return"].map(fmt_pct)
    out["corrected_total_return"] = out["corrected_total_return"].map(fmt_pct)
    for col in ["delta_total_return_pp", "daily_leak_sum_pp", "bonus_split_contribution_pp", "dividend_small_contribution_pp"]:
        out[col] = out[col].map(lambda v: f"{float(v):.4f}pp")
    return out


def format_event_summary_table(event_summary: pd.DataFrame) -> pd.DataFrame:
    out = event_summary.copy()
    out["cumulative_nav_contribution_pp"] = out["cumulative_nav_contribution_pp"].map(lambda v: f"{float(v):.4f}pp")
    out["abs_nav_contribution_pp"] = out["abs_nav_contribution_pp"].map(lambda v: f"{float(v):.4f}pp")
    out["avg_prev_weight"] = out["avg_prev_weight"].map(fmt_pct)
    return out[
        [
            "backtest_label",
            "event_type",
            "event_count",
            "cumulative_nav_contribution_pp",
            "abs_nav_contribution_pp",
            "avg_prev_weight",
        ]
    ]


def format_residual_table(residual: pd.DataFrame) -> pd.DataFrame:
    out = residual.copy()
    for col in ["mean_residual", "median_residual", "p95_abs_residual", "p99_abs_residual", "max_abs_residual"]:
        out[col] = out[col].map(lambda v: "NA" if pd.isna(v) else f"{float(v):.3e}")
    return out


def format_top_events_table(top_events: pd.DataFrame) -> pd.DataFrame:
    if top_events.empty:
        return top_events
    out = top_events.copy()
    out["factor_jump"] = out["factor_jump"].map(fmt_pct)
    out["prev_weight"] = out["prev_weight"].map(fmt_pct)
    out["raw_return"] = out["raw_return"].map(fmt_pct)
    out["hfq_return"] = out["hfq_return"].map(fmt_pct)
    out["leak_contribution_pp"] = out["leak_contribution_pp"].map(lambda v: f"{float(v):.4f}pp")
    return out


def nav_from_returns(returns: pd.Series, initial_nav: float = 1.0) -> pd.Series:
    values: list[float] = []
    current = initial_nav
    for ret in returns:
        if pd.notna(ret):
            current *= 1.0 + float(ret)
        values.append(current)
    return pd.Series(values, index=returns.index, dtype=float)


def cumulative_return(returns: pd.Series) -> float:
    value = 1.0
    for ret in returns:
        if pd.notna(ret):
            value *= 1.0 + float(ret)
    return value


def compound_annualized_return(total_return: float, return_period_count: int) -> float:
    if return_period_count <= 0 or 1.0 + total_return <= 0.0:
        return math.nan
    return (1.0 + total_return) ** (TRADING_DAYS_PER_YEAR / return_period_count) - 1.0


def max_drawdown(dates: pd.Series, nav: pd.Series) -> tuple[float, date, date]:
    nav_values = pd.Series(nav, dtype=float).reset_index(drop=True)
    date_values = pd.to_datetime(dates).dt.date.reset_index(drop=True)
    running_peak = nav_values.cummax()
    drawdown = nav_values / running_peak - 1.0
    trough_idx = int(drawdown.idxmin())
    peak_nav = float(running_peak.iloc[trough_idx])
    eligible = nav_values.iloc[: trough_idx + 1]
    peak_idx = int(eligible[np.isclose(eligible, peak_nav, rtol=0, atol=1e-9)].index[0])
    return float(drawdown.iloc[trough_idx]), date_values.iloc[peak_idx], date_values.iloc[trough_idx]


def safe_ratio(numerator: float, denominator: float) -> float:
    if denominator is None or not math.isfinite(float(denominator)) or abs(float(denominator)) < 1e-15:
        return math.nan
    return float(numerator) / float(denominator)


def with_date(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if "trade_date" in out.columns and not out.empty:
        out["trade_date"] = pd.to_datetime(out["trade_date"]).dt.date
    return out


def empty_trade_flags() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "trade_date",
            "order_rows",
            "filled_trade_count",
            "filled_shares_abs",
            "filled_turnover_cny",
            "filled_cost_cny",
        ]
    )


def safe_path_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value)[:120]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dumps_strict(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    text = frame.copy()
    for col in text.columns:
        text[col] = text[col].map(lambda v: "" if pd.isna(v) else str(v))
    headers = list(text.columns)
    rows = text.values.tolist()
    widths = [
        max(len(str(header)), *(len(str(row[idx])) for row in rows))
        for idx, header in enumerate(headers)
    ]
    header_line = "| " + " | ".join(str(header).ljust(widths[idx]) for idx, header in enumerate(headers)) + " |"
    sep_line = "| " + " | ".join("-" * widths[idx] for idx in range(len(headers))) + " |"
    body = [
        "| " + " | ".join(str(value).ljust(widths[idx]) for idx, value in enumerate(row)) + " |"
        for row in rows
    ]
    return "\n".join([header_line, sep_line, *body])


def fmt_pct(value: Any) -> str:
    if value is None or pd.isna(value) or not math.isfinite(float(value)):
        return "NA"
    return f"{float(value) * 100:.2f}%"


def fmt_pp(value: Any) -> str:
    if value is None or pd.isna(value) or not math.isfinite(float(value)):
        return "NA"
    return f"{float(value) * 100:.2f}pp"


def fmt_num(value: Any) -> str:
    if value is None or pd.isna(value) or not math.isfinite(float(value)):
        return "NA"
    return f"{float(value):.4f}"


if __name__ == "__main__":
    raise SystemExit(main())
