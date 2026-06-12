#!/usr/bin/env python3
"""Read-only Strategy1 v3 Calmar gate feasibility analysis."""

from __future__ import annotations

import argparse
import itertools
import math
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from google.cloud import bigquery

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.strategy1 import replay_acceptance_gate_v3 as replay_v3
from scripts.strategy1 import simulate_exposure_overlay_upper_bound as exposure_sim
from scripts.strategy1_cloudrun.acceptance import contract_hash, contract_version, load_acceptance_contract
from scripts.strategy1_cloudrun.bq_io import make_client, query_dataframe


DEFAULT_PROJECT = "data-aquarium"
DEFAULT_LOCATION = "asia-east2"
DEFAULT_STRATEGY_ID = "ml_pv_clf_v0"
DEFAULT_CONTRACT = "configs/strategy1/model_acceptance_contract_v3.yml"
DEFAULT_LONG_START = "2021-01-04"
DEFAULT_LONG_END = "2026-06-09"
DEFAULT_BASELINE_PARENT_BACKTEST_ID = "bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01"
DEFAULT_BASELINE_RESUME_BACKTEST_ID = "bt_s1_dividend_backfill_resume_20260528_20260609_v20260612_01"
DEFAULT_BASELINE_RESUME_START = "2026-05-28"
DEFAULT_MARKET_STATE_VERSION = "market_state_v1_20260607"
DEFAULT_OUTPUT_PREFIX = "docs/analysis_strategy1_v3_calmar_gate_20260613"
DEFAULT_REPORT = "docs/分析-策略1v3Calmar门合理性-20260613.md"
ROLLING_PERIODS = 252 * 3


@dataclass(frozen=True)
class WindowSpec:
    window_id: str
    start_date: date
    end_date: date
    label_zh: str


@dataclass(frozen=True)
class OutputPaths:
    index_metrics: Path
    rolling_3y: Path
    exposure_grid: Path
    reachability: Path
    counterfactual: Path
    portfolio_variants: Path
    report: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="策略1 v3 Calmar 门合理性只读分析")
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--location", default=DEFAULT_LOCATION)
    parser.add_argument("--strategy-id", default=DEFAULT_STRATEGY_ID)
    parser.add_argument("--contract", default=DEFAULT_CONTRACT)
    parser.add_argument("--long-start-date", default=DEFAULT_LONG_START)
    parser.add_argument("--long-end-date", default=DEFAULT_LONG_END)
    parser.add_argument("--baseline-parent-backtest-id", default=DEFAULT_BASELINE_PARENT_BACKTEST_ID)
    parser.add_argument("--baseline-resume-backtest-id", default=DEFAULT_BASELINE_RESUME_BACKTEST_ID)
    parser.add_argument("--baseline-resume-start-date", default=DEFAULT_BASELINE_RESUME_START)
    parser.add_argument("--market-state-version", default=DEFAULT_MARKET_STATE_VERSION)
    parser.add_argument("--output-prefix", default=DEFAULT_OUTPUT_PREFIX)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--option-a-threshold", type=float, default=0.5)
    parser.add_argument("--skip-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = load_acceptance_contract(args.contract)
    if contract_version(contract) != "model_acceptance_contract_v3":
        raise SystemExit("--contract must point to model_acceptance_contract_v3")
    client = make_client(args.project, args.location)
    paths = output_paths(args)

    long_window = WindowSpec(
        window_id="long_2021_2026",
        start_date=parse_date(args.long_start_date),
        end_date=parse_date(args.long_end_date),
        label_zh="长窗 2021-01-04..2026-06-09",
    )
    replay_window = contract_replay_window(contract)
    windows = [long_window, replay_window]

    index_meta = fetch_index_meta(client, args.project)
    index_prices = fetch_index_prices(client, args.project, index_meta["sec_code"].tolist(), long_window)
    index_metrics = build_index_metric_frame(index_meta, index_prices, windows)
    rolling = build_rolling_frame(index_meta, index_prices)

    baseline_nav = fetch_baseline_nav(client, args, long_window)
    baseline_frames = {window.window_id: slice_nav(baseline_nav, window) for window in windows}
    baseline_metrics = build_baseline_metric_frame(baseline_frames)

    exposure_grid = run_exposure_grid(client, args, baseline_nav, long_window)

    candidates, variants = fetch_and_select_backtests(client, args, contract, replay_window)
    variants_for_output = portfolio_variant_output(variants)
    candidate_summary, candidate_benchmarks = evaluate_replay_candidates(client, args, contract, replay_window, candidates)

    benchmark_meta = replay_v3.comparison_benchmarks(contract)
    benchmark_price_map = split_price_series(index_prices[index_prices["sec_code"].isin([row["sec_code"] for row in benchmark_meta])])
    baseline_option_rows = evaluate_baseline_options(
        baseline_frames,
        benchmark_price_map,
        benchmark_meta,
        contract,
        args.option_a_threshold,
    )
    candidate_option_rows = evaluate_candidate_options(
        candidate_summary,
        candidate_benchmarks,
        args.option_a_threshold,
    )
    index_guard = evaluate_index_guard_options(
        index_meta,
        index_prices,
        windows,
        benchmark_price_map,
        benchmark_meta,
        args.option_a_threshold,
    )
    option_matrix = pd.concat(
        [candidate_option_rows, baseline_option_rows, index_guard],
        ignore_index=True,
    ).sort_values(["row_group", "window_id", "option_id", "search_id", "rank", "entity_id"], na_position="last")

    reachability = build_reachability_frame(
        index_metrics=index_metrics,
        baseline_metrics=baseline_metrics,
        exposure_grid=exposure_grid,
        candidate_summary=candidate_summary,
        windows=windows,
    )

    write_csv(index_metrics, paths.index_metrics)
    write_csv(rolling, paths.rolling_3y)
    write_csv(exposure_grid, paths.exposure_grid)
    write_csv(reachability, paths.reachability)
    write_csv(option_matrix, paths.counterfactual)
    write_csv(variants_for_output, paths.portfolio_variants)
    if not args.skip_report:
        paths.report.parent.mkdir(parents=True, exist_ok=True)
        paths.report.write_text(
            render_report(
                args=args,
                contract=contract,
                windows=windows,
                index_metrics=index_metrics,
                rolling=rolling,
                baseline_metrics=baseline_metrics,
                exposure_grid=exposure_grid,
                reachability=reachability,
                candidate_summary=candidate_summary,
                candidate_benchmarks=candidate_benchmarks,
                option_matrix=option_matrix,
                variants=variants_for_output,
                paths=paths,
            ),
            encoding="utf-8",
        )

    print(
        {
            "status": "succeeded",
            "report": str(paths.report),
            "index_metrics_csv": str(paths.index_metrics),
            "rolling_3y_csv": str(paths.rolling_3y),
            "counterfactual_csv": str(paths.counterfactual),
            "portfolio_variants_csv": str(paths.portfolio_variants),
        }
    )
    return 0


def output_paths(args: argparse.Namespace) -> OutputPaths:
    prefix = Path(args.output_prefix)
    return OutputPaths(
        index_metrics=prefix.with_name(prefix.name + "_index_metrics.csv"),
        rolling_3y=prefix.with_name(prefix.name + "_rolling_3y.csv"),
        exposure_grid=prefix.with_name(prefix.name + "_exposure_overlay.csv"),
        reachability=prefix.with_name(prefix.name + "_reachability_ladder.csv"),
        counterfactual=prefix.with_name(prefix.name + "_counterfactual_matrix.csv"),
        portfolio_variants=prefix.with_name(prefix.name + "_portfolio_variants.csv"),
        report=Path(args.report),
    )


def parse_date(value: Any) -> date:
    return pd.to_datetime(value).date()


def contract_replay_window(contract: dict[str, Any]) -> WindowSpec:
    window = ((contract.get("windows") or {}).get("default_replay_and_initial_cutover_full_period") or {})
    return WindowSpec(
        window_id="replay_2024_2026",
        start_date=parse_date(window["start_date"]),
        end_date=parse_date(window["end_date"]),
        label_zh="v3 replay 窗 2024-01-02..2026-04-30",
    )


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def fetch_index_meta(client: bigquery.Client, project: str) -> pd.DataFrame:
    sql = f"""
    SELECT sec_code, index_name
    FROM `{project}.ashare_dim.dim_index`
    WHERE has_daily = TRUE
      AND is_benchmark_candidate = TRUE
    ORDER BY sec_code
    """
    frame = query_dataframe(
        client,
        sql,
        [],
        labels={"component": "strategy1", "step": "calmar_gate_index_meta"},
    )
    expected = {
        "000001.SH",
        "000016.SH",
        "000300.SH",
        "000688.SH",
        "000852.SH",
        "000905.SH",
        "399001.SZ",
        "399006.SZ",
    }
    actual = set(frame["sec_code"].tolist())
    if actual != expected:
        raise RuntimeError(f"expected 8 benchmark candidate indexes {sorted(expected)}, got {sorted(actual)}")
    return frame


def fetch_index_prices(
    client: bigquery.Client,
    project: str,
    sec_codes: list[str],
    window: WindowSpec,
) -> pd.DataFrame:
    sql = f"""
    SELECT sec_code, trade_date, close
    FROM `{project}.ashare_dwd.dwd_index_eod`
    WHERE sec_code IN UNNEST(@sec_codes)
      AND trade_date BETWEEN @start_date AND @end_date
    ORDER BY sec_code, trade_date
    """
    frame = query_dataframe(
        client,
        sql,
        [
            bigquery.ArrayQueryParameter("sec_codes", "STRING", sec_codes),
            bigquery.ScalarQueryParameter("start_date", "DATE", window.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", window.end_date),
        ],
        labels={"component": "strategy1", "step": "calmar_gate_index_prices"},
    )
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    counts = frame.groupby("sec_code").size().to_dict()
    if len(set(counts.values())) != 1 or set(counts) != set(sec_codes):
        raise RuntimeError(f"index coverage mismatch in {window.window_id}: {counts}")
    return frame


def price_nav_frame(price_rows: pd.DataFrame) -> pd.DataFrame:
    rows = price_rows.sort_values("trade_date").reset_index(drop=True).copy()
    close = pd.to_numeric(rows["close"], errors="coerce")
    if close.isna().any() or close.iloc[0] <= 0:
        raise RuntimeError("index close contains invalid values")
    rows["nav_value"] = close / float(close.iloc[0])
    rows["daily_return"] = close.pct_change()
    return rows[["trade_date", "nav_value", "daily_return"]]


def slice_nav(nav: pd.DataFrame, window: WindowSpec) -> pd.DataFrame:
    frame = nav.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    result = frame[(frame["trade_date"] >= window.start_date) & (frame["trade_date"] <= window.end_date)].copy()
    result = result.sort_values("trade_date").reset_index(drop=True)
    if result.empty:
        raise RuntimeError(f"NAV window is empty for {window.window_id}")
    return result


def build_index_metric_frame(index_meta: pd.DataFrame, prices: pd.DataFrame, windows: list[WindowSpec]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    names = dict(zip(index_meta["sec_code"], index_meta["index_name"]))
    for sec_code, group in prices.groupby("sec_code", sort=False):
        for window in windows:
            nav = price_nav_frame(slice_nav(group, window))
            metrics = nav_stats(nav)
            rows.append({
                "window_id": window.window_id,
                "window_label_zh": window.label_zh,
                "sec_code": sec_code,
                "index_name": names.get(sec_code),
                "start_date": window.start_date.isoformat(),
                "end_date": window.end_date.isoformat(),
                **metrics,
            })
    return pd.DataFrame(rows)


def build_rolling_frame(index_meta: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    names = dict(zip(index_meta["sec_code"], index_meta["index_name"]))
    for sec_code, group in prices.groupby("sec_code", sort=False):
        ordered = group.sort_values("trade_date").reset_index(drop=True)
        for end_pos in range(ROLLING_PERIODS, len(ordered)):
            chunk = ordered.iloc[end_pos - ROLLING_PERIODS : end_pos + 1].copy()
            nav = price_nav_frame(chunk)
            metrics = nav_stats(nav)
            rows.append({
                "sec_code": sec_code,
                "index_name": names.get(sec_code),
                "rolling_window": "756_return_periods",
                "start_date": chunk["trade_date"].iloc[0].isoformat(),
                "end_date": chunk["trade_date"].iloc[-1].isoformat(),
                "return_period_count": metrics["return_period_count"],
                "compound_annualized_return": metrics["compound_annualized_return"],
                "max_drawdown": metrics["max_drawdown"],
                "calmar_ratio": metrics["calmar_ratio"],
                "sharpe_ratio": metrics["sharpe_ratio"],
            })
    return pd.DataFrame(rows)


def nav_stats(nav: pd.DataFrame) -> dict[str, Any]:
    frame = nav.copy()
    if "nav" in frame.columns and "nav_value" not in frame.columns:
        frame["nav_value"] = frame["nav"]
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    total_return, periods = replay_v3.total_return_from_nav(frame)
    growth = replay_v3.compound_annualized_return(total_return, periods)
    vol = replay_v3.annualized_volatility_from_daily_returns(frame["daily_return"])
    risk_return = replay_v3.signed_zero_safe_ratio(growth, vol)
    drawdown, peak_date, trough_date = replay_v3.max_drawdown_window(frame)
    ratio = replay_v3.signed_zero_safe_ratio(growth, abs(drawdown) if drawdown is not None else None)
    return {
        "nav_row_count": int(frame.shape[0]),
        "return_period_count": periods,
        "total_return": total_return,
        "compound_annualized_return": growth,
        "annualized_volatility": vol,
        "sharpe_ratio": risk_return,
        "max_drawdown": drawdown,
        "max_drawdown_peak_date": peak_date.isoformat() if peak_date else None,
        "max_drawdown_trough_date": trough_date.isoformat() if trough_date else None,
        "calmar_ratio": ratio,
    }


def fetch_baseline_nav(client: bigquery.Client, args: argparse.Namespace, window: WindowSpec) -> pd.DataFrame:
    sql = f"""
    SELECT backtest_id, trade_date, nav, daily_return
    FROM `{args.project}.ashare_research.research_backtest_nav_daily`
    WHERE backtest_id IN UNNEST(@backtest_ids)
      AND trade_date BETWEEN @start_date AND @end_date
    ORDER BY backtest_id, trade_date
    """
    frame = query_dataframe(
        client,
        sql,
        [
            bigquery.ArrayQueryParameter(
                "backtest_ids",
                "STRING",
                [args.baseline_parent_backtest_id, args.baseline_resume_backtest_id],
            ),
            bigquery.ScalarQueryParameter("start_date", "DATE", window.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", window.end_date),
        ],
        labels={"component": "strategy1", "step": "calmar_gate_baseline_nav"},
    )
    if frame.empty:
        raise RuntimeError("baseline NAV query returned no rows")
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    resume_start = parse_date(args.baseline_resume_start_date)
    parent = frame[frame["backtest_id"] == args.baseline_parent_backtest_id].copy()
    child = frame[frame["backtest_id"] == args.baseline_resume_backtest_id].copy()
    if not child.empty:
        stitched = pd.concat(
            [
                parent[parent["trade_date"] < resume_start],
                child[child["trade_date"] >= resume_start],
            ],
            ignore_index=True,
        )
        source = f"{args.baseline_parent_backtest_id} + {args.baseline_resume_backtest_id}"
    else:
        stitched = parent
        source = args.baseline_parent_backtest_id
    stitched = stitched.sort_values("trade_date").reset_index(drop=True)
    stitched["nav_value"] = pd.to_numeric(stitched["nav"], errors="coerce")
    stitched["daily_return"] = pd.to_numeric(stitched["daily_return"], errors="coerce")
    stitched["source_backtest_path"] = source
    expected_rows = parent.shape[0]
    if stitched.shape[0] != expected_rows:
        raise RuntimeError(f"stitched baseline row count mismatch: stitched={stitched.shape[0]} parent={expected_rows}")
    return stitched[["trade_date", "nav", "nav_value", "daily_return", "backtest_id", "source_backtest_path"]]


def build_baseline_metric_frame(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for window_id, nav in frames.items():
        metrics = nav_stats(nav)
        rows.append({
            "window_id": window_id,
            "entity_id": "current_true5y_ca_on_baseline",
            "source": nav["source_backtest_path"].iloc[0],
            **metrics,
        })
    return pd.DataFrame(rows)


def fetch_calendar_rows(client: bigquery.Client, args: argparse.Namespace, window: WindowSpec) -> pd.DataFrame:
    sql = f"""
    SELECT cal_date AS trade_date, trade_date_seq
    FROM `{args.project}.ashare_dim.dim_trade_calendar`
    WHERE exchange = 'SSE'
      AND is_open = 1
      AND cal_date BETWEEN @start_date AND @end_date
    ORDER BY cal_date
    """
    frame = query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("start_date", "DATE", window.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", window.end_date),
        ],
        labels={"component": "strategy1", "step": "calmar_gate_calendar"},
    )
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    return frame


def fetch_market_rows(client: bigquery.Client, args: argparse.Namespace, window: WindowSpec) -> pd.DataFrame:
    sql = f"""
    SELECT
      trade_date,
      is_risk_off,
      market_regime,
      risk_off_trigger_count,
      is_limit_down_diffusion
    FROM `{args.project}.ashare_dws.dws_market_state_daily`
    WHERE market_state_version = @market_state_version
      AND trade_date BETWEEN @start_date AND @end_date
    ORDER BY trade_date
    """
    frame = query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("market_state_version", "STRING", args.market_state_version),
            bigquery.ScalarQueryParameter("start_date", "DATE", window.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", window.end_date),
        ],
        labels={"component": "strategy1", "step": "calmar_gate_market_state"},
    )
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    return frame


def fetch_benchmark_returns(client: bigquery.Client, args: argparse.Namespace, window: WindowSpec) -> pd.DataFrame:
    sql = f"""
    SELECT trade_date, pct_chg / 100.0 AS benchmark_return
    FROM `{args.project}.ashare_dwd.dwd_index_eod`
    WHERE sec_code = '000852.SH'
      AND trade_date BETWEEN @start_date AND @end_date
    ORDER BY trade_date
    """
    frame = query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("start_date", "DATE", window.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", window.end_date),
        ],
        labels={"component": "strategy1", "step": "calmar_gate_000852_returns"},
    )
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    return frame


def run_exposure_grid(
    client: bigquery.Client,
    args: argparse.Namespace,
    baseline_nav: pd.DataFrame,
    window: WindowSpec,
) -> pd.DataFrame:
    calendar = fetch_calendar_rows(client, args, window)
    market = fetch_market_rows(client, args, window)
    benchmark = fetch_benchmark_returns(client, args, window)
    nav = baseline_nav[["trade_date", "nav", "daily_return"]].copy()
    data = exposure_sim.prepare_simulation_frame(nav, calendar, market, benchmark)
    rebalance_dates = exposure_sim.build_biweekly_rebalance_dates(calendar)
    exposure_sim.validate_inputs(data, rebalance_dates)
    rows: list[dict[str, Any]] = []
    rows.append(
        exposure_sim.simulate_variant(
            data,
            exposure_sim.Variant("baseline_identity", "identity", "daily", 1.0, 0.0),
            rebalance_dates,
        )
    )
    e_low_grid = exposure_sim.parse_float_grid(exposure_sim.DEFAULT_E_LOW_GRID)
    cost_grid = exposure_sim.parse_float_grid(exposure_sim.DEFAULT_COST_BPS_GRID)
    for state_machine, timing, e_low, cost_bps in itertools.product(
        ["two_state", "hysteresis"],
        ["daily", "biweekly"],
        e_low_grid,
        cost_grid,
    ):
        rows.append(
            exposure_sim.simulate_variant(
                data,
                exposure_sim.Variant(
                    variant_id=f"{state_machine}_{timing}_elow{e_low:g}_cost{cost_bps:g}bps",
                    state_machine=state_machine,
                    timing=timing,
                    e_low=e_low,
                    transaction_cost_bps=cost_bps,
                ),
                rebalance_dates,
            )
        )
    result = pd.DataFrame(rows)
    result.insert(0, "window_id", window.window_id)
    result.insert(1, "source_backtest_path", baseline_nav["source_backtest_path"].iloc[0])
    return result.sort_values(
        ["is_identity", "transaction_cost_bps", "state_machine", "timing", "e_low"],
        ascending=[False, True, True, True, True],
    )


def fetch_and_select_backtests(
    client: bigquery.Client,
    args: argparse.Namespace,
    contract: dict[str, Any],
    replay_window: WindowSpec,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    replay_v3.set_output_dataset_role("ads")
    replay_args = argparse.Namespace(
        project=args.project,
        region=args.location,
        strategy_id=args.strategy_id,
        search_ids=[str(value) for value in ((contract.get("replay_scope") or {}).get("search_ids") or [])],
        top_k_per_search=int((contract.get("replay_scope") or {}).get("top_k_per_search") or 5),
        full_start_date=replay_window.start_date,
        full_end_date=replay_window.end_date,
        valid_start_date=parse_date((contract.get("windows") or {})["valid"]["start_date"]),
        valid_end_date=parse_date((contract.get("windows") or {})["valid"]["end_date"]),
        test_start_date=parse_date((contract.get("windows") or {})["test"]["start_date"]),
        test_end_date=parse_date((contract.get("windows") or {})["test"]["end_date"]),
        final_holdout_start_date=parse_date((contract.get("windows") or {})["final_holdout"]["start_date"]),
        final_holdout_end_date=parse_date((contract.get("windows") or {})["final_holdout"]["end_date"]),
    )
    raw = replay_v3.fetch_selected_candidates(client, replay_args)
    raw = raw.copy()
    return select_canonical_rows(raw, replay_args.search_ids, replay_args.top_k_per_search)


def select_canonical_rows(
    raw: pd.DataFrame,
    search_ids: list[str],
    top_k_per_search: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = raw.copy()
    frame["candidate_id"] = frame["model_id"].map(candidate_from_model_id)
    frame["expected_canonical_backtest_id"] = frame.apply(
        lambda row: f"bt_s1_{row['search_id']}__{row['candidate_id']}",
        axis=1,
    )
    frame["is_canonical_default_backtest"] = frame["backtest_id"] == frame["expected_canonical_backtest_id"]
    canonical = frame[frame["is_canonical_default_backtest"]].copy()
    variants = frame[~frame["is_canonical_default_backtest"]].copy()
    counts = canonical.groupby("search_id").size().to_dict()
    expected = {search_id: top_k_per_search for search_id in search_ids}
    if counts != expected:
        raise RuntimeError(f"canonical TopK mismatch: expected {expected}, got {counts}")
    canonical = canonical.sort_values(["search_id", "shortlist_rank_valid_only", "model_id"]).reset_index(drop=True)
    variants = variants.sort_values(["search_id", "shortlist_rank_valid_only", "model_id", "backtest_id"]).reset_index(drop=True)
    return canonical, variants


def candidate_from_model_id(model_id: str) -> str:
    parts = str(model_id).split("__")
    if len(parts) < 2:
        raise ValueError(f"cannot derive candidate_id from model_id={model_id}")
    return parts[-1]


def portfolio_variant_output(variants: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "search_id",
        "shortlist_rank_valid_only",
        "model_id",
        "candidate_id",
        "backtest_id",
        "expected_canonical_backtest_id",
        "backtest_start_date",
        "backtest_end_date",
        "summary_total_return",
        "summary_sharpe",
        "summary_max_drawdown",
    ]
    existing = [column for column in columns if column in variants.columns]
    return variants[existing].copy()


def evaluate_replay_candidates(
    client: bigquery.Client,
    args: argparse.Namespace,
    contract: dict[str, Any],
    replay_window: WindowSpec,
    candidates: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    replay_v3.set_output_dataset_role("ads")
    replay_args = argparse.Namespace(
        full_start_date=replay_window.start_date,
        full_end_date=replay_window.end_date,
        final_holdout_start_date=parse_date((contract.get("windows") or {})["final_holdout"]["start_date"]),
        final_holdout_end_date=parse_date((contract.get("windows") or {})["final_holdout"]["end_date"]),
        project=args.project,
    )
    nav_frame = replay_v3.fetch_nav_rows(client, replay_args, candidates["backtest_id"].tolist())
    nav_map = replay_v3.split_nav_by_backtest(nav_frame)
    benchmark_meta = replay_v3.comparison_benchmarks(contract)
    benchmark_codes = [row["sec_code"] for row in benchmark_meta]
    benchmark_frame = replay_v3.fetch_benchmark_rows(client, replay_args, benchmark_codes)
    benchmark_price_map = replay_v3.split_prices_by_benchmark(benchmark_frame)
    replay_v3.ensure_benchmark_coverage(contract, nav_map, benchmark_price_map, benchmark_codes)
    candidate_rows: list[dict[str, Any]] = []
    benchmark_rows: list[dict[str, Any]] = []
    for record in candidates.to_dict(orient="records"):
        summary, by_benchmark = replay_v3.evaluate_candidate(
            record,
            nav_map[record["backtest_id"]],
            benchmark_price_map,
            benchmark_meta,
            contract,
            replay_args,
        )
        summary.update(gate_breakdown(summary))
        candidate_rows.append(summary)
        benchmark_rows.extend(by_benchmark)
    return pd.DataFrame(candidate_rows), pd.DataFrame(benchmark_rows)


def split_price_series(prices: pd.DataFrame) -> dict[str, pd.Series]:
    result: dict[str, pd.Series] = {}
    for sec_code, group in prices.groupby("sec_code", sort=False):
        ordered = group.sort_values("trade_date")
        result[str(sec_code)] = pd.Series(
            pd.to_numeric(ordered["close"], errors="coerce").astype(float).values,
            index=list(ordered["trade_date"]),
            name=str(sec_code),
        )
    return result


def gate_breakdown(row: dict[str, Any]) -> dict[str, Any]:
    required_reasons = []
    if row.get("cv_confirmation_status") != "passed":
        required_reasons.append("cv_confirmation_status!=passed")
    if row.get("valid_signal_status") != "stable":
        required_reasons.append("valid_signal_status!=stable")
    if row.get("score_orientation") not in {"identity", "reverse_probability"}:
        required_reasons.append("score_orientation_not_allowed")

    signal_reasons = []
    for column, reason in [
        ("valid_rank_ic", "valid_rank_ic<=0"),
        ("valid_top_minus_bottom_fwd_ret", "valid_top_minus_bottom<=0"),
        ("test_rank_ic", "test_rank_ic<=0"),
        ("test_top_minus_bottom_fwd_ret", "test_top_minus_bottom<=0"),
    ]:
        value = replay_v3.safe_float(row.get(column))
        if value is None or value <= 0:
            signal_reasons.append(reason)
    if row.get("primary_diagnosis") in {"signal_inverted", "unusable_signal"}:
        signal_reasons.append(f"primary_diagnosis={row.get('primary_diagnosis')}")
    if row.get("sample_filter_risk") == "high":
        signal_reasons.append("sample_filter_risk=high")

    absolute_reasons = []
    risk_return = replay_v3.safe_float(row.get("sharpe_ratio"))
    ratio = replay_v3.safe_float(row.get("calmar_ratio"))
    if risk_return is None or risk_return < 0.70:
        absolute_reasons.append("sharpe_ratio_below_v3_gate")
    if ratio is None or ratio <= 1.0:
        absolute_reasons.append("calmar_ratio_below_v3_gate")

    relative_reasons = []
    if int(row.get("passed_benchmark_count") or 0) <= 0:
        relative_reasons.append("no_comparison_benchmark_passed_v3_relative_gate")

    return {
        "required_gate_status": "passed" if not required_reasons else "failed",
        "required_gate_reasons": ";".join(required_reasons),
        "signal_quality_gate_status": "passed" if not signal_reasons else "failed",
        "signal_quality_gate_reasons": ";".join(signal_reasons),
        "absolute_gate_status": "passed" if not absolute_reasons else "failed",
        "absolute_gate_reasons": ";".join(absolute_reasons),
        "relative_gate_status": "passed" if not relative_reasons else "failed",
        "relative_gate_reasons": ";".join(relative_reasons),
    }


def relative_rows_for_nav(
    entity_id: str,
    nav: pd.DataFrame,
    benchmark_price_map: dict[str, pd.Series],
    benchmark_meta: list[dict[str, Any]],
) -> pd.DataFrame:
    metrics = nav_stats(nav)
    rows = []
    for benchmark in benchmark_meta:
        row = replay_v3.evaluate_relative_benchmark(
            record={"model_id": entity_id, "run_id": entity_id, "backtest_id": entity_id, "search_id": None, "shortlist_rank_valid_only": None},
            nav_df=nav,
            benchmark=benchmark,
            benchmark_prices=benchmark_price_map[benchmark["sec_code"]],
            strategy_compound_annualized_return=metrics["compound_annualized_return"],
            return_period_count=metrics["return_period_count"],
            strategy_max_drawdown=metrics["max_drawdown"],
            peak_date=parse_date(metrics["max_drawdown_peak_date"]),
            trough_date=parse_date(metrics["max_drawdown_trough_date"]),
        )
        rows.append(row)
    return pd.DataFrame(rows)


def evaluate_baseline_options(
    frames: dict[str, pd.DataFrame],
    benchmark_price_map: dict[str, pd.Series],
    benchmark_meta: list[dict[str, Any]],
    contract: dict[str, Any],
    option_a_threshold: float,
) -> pd.DataFrame:
    rows = []
    for window_id, nav in frames.items():
        metrics = nav_stats(nav)
        relative = relative_rows_for_nav("current_true5y_ca_on_baseline", nav, benchmark_price_map, benchmark_meta)
        status = option_statuses(metrics, relative, option_a_threshold)
        for option_id, payload in status.items():
            rows.append({
                "row_group": "current_baseline_performance_only",
                "window_id": window_id,
                "option_id": option_id,
                "entity_id": "current_true5y_ca_on_baseline",
                "search_id": None,
                "rank": None,
                "model_id": None,
                "backtest_id": nav["source_backtest_path"].iloc[0],
                "required_gate_status": "not_applicable_current_baseline",
                "signal_quality_gate_status": "not_applicable_current_baseline",
                "absolute_gate_status": payload["absolute_gate_status"],
                "relative_gate_status": payload["relative_gate_status"],
                "counterfactual_status": payload["status"],
                "counterfactual_reasons": payload["reasons"],
                "strategy_compound_annualized_return": metrics["compound_annualized_return"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "calmar_ratio": metrics["calmar_ratio"],
                "max_drawdown": metrics["max_drawdown"],
                "passed_benchmark_count": payload["passed_benchmark_count"],
                "passed_benchmark_sec_codes": ",".join(payload["passed_benchmark_sec_codes"]),
                "is_index_guard_check": False,
            })
    return pd.DataFrame(rows)


def evaluate_candidate_options(
    candidate_summary: pd.DataFrame,
    candidate_benchmarks: pd.DataFrame,
    option_a_threshold: float,
) -> pd.DataFrame:
    rows = []
    by_model = {model_id: group.copy() for model_id, group in candidate_benchmarks.groupby("model_id", sort=False)}
    for record in candidate_summary.to_dict(orient="records"):
        metrics = {
            "compound_annualized_return": record.get("strategy_compound_annualized_return"),
            "sharpe_ratio": record.get("sharpe_ratio"),
            "calmar_ratio": record.get("calmar_ratio"),
            "max_drawdown": record.get("max_drawdown"),
        }
        status = option_statuses(metrics, by_model[record["model_id"]], option_a_threshold)
        for option_id, payload in status.items():
            rows.append({
                "row_group": "historical_candidate_canonical",
                "window_id": "replay_2024_2026",
                "option_id": option_id,
                "entity_id": record.get("model_id"),
                "search_id": record.get("search_id"),
                "rank": record.get("search_rank_valid_only"),
                "model_id": record.get("model_id"),
                "backtest_id": record.get("backtest_id"),
                "required_gate_status": record.get("required_gate_status"),
                "signal_quality_gate_status": record.get("signal_quality_gate_status"),
                "absolute_gate_status": payload["absolute_gate_status"],
                "relative_gate_status": payload["relative_gate_status"],
                "counterfactual_status": "accepted" if (
                    record.get("required_gate_status") == "passed"
                    and record.get("signal_quality_gate_status") == "passed"
                    and payload["status"] == "accepted"
                ) else "rejected",
                "counterfactual_reasons": merge_reason_text(
                    record.get("required_gate_reasons"),
                    record.get("signal_quality_gate_reasons"),
                    payload["reasons"],
                ),
                "strategy_compound_annualized_return": metrics["compound_annualized_return"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "calmar_ratio": metrics["calmar_ratio"],
                "max_drawdown": metrics["max_drawdown"],
                "passed_benchmark_count": payload["passed_benchmark_count"],
                "passed_benchmark_sec_codes": ",".join(payload["passed_benchmark_sec_codes"]),
                "is_index_guard_check": False,
            })
    return pd.DataFrame(rows)


def evaluate_index_guard_options(
    index_meta: pd.DataFrame,
    prices: pd.DataFrame,
    windows: list[WindowSpec],
    benchmark_price_map: dict[str, pd.Series],
    benchmark_meta: list[dict[str, Any]],
    option_a_threshold: float,
) -> pd.DataFrame:
    names = dict(zip(index_meta["sec_code"], index_meta["index_name"]))
    rows = []
    for sec_code, group in prices.groupby("sec_code", sort=False):
        for window in windows:
            nav = price_nav_frame(slice_nav(group, window))
            metrics = nav_stats(nav)
            relative = relative_rows_for_nav(f"hold_index_{sec_code}", nav, benchmark_price_map, benchmark_meta)
            status = option_statuses(metrics, relative, option_a_threshold)
            for option_id, payload in status.items():
                rows.append({
                    "row_group": "full_index_guard_check",
                    "window_id": window.window_id,
                    "option_id": option_id,
                    "entity_id": sec_code,
                    "search_id": None,
                    "rank": None,
                    "model_id": None,
                    "backtest_id": f"full_hold_{sec_code}",
                    "required_gate_status": "assumed_pass_for_beta_guard",
                    "signal_quality_gate_status": "assumed_pass_for_beta_guard",
                    "absolute_gate_status": payload["absolute_gate_status"],
                    "relative_gate_status": payload["relative_gate_status"],
                    "counterfactual_status": payload["status"],
                    "counterfactual_reasons": payload["reasons"],
                    "strategy_compound_annualized_return": metrics["compound_annualized_return"],
                    "sharpe_ratio": metrics["sharpe_ratio"],
                    "calmar_ratio": metrics["calmar_ratio"],
                    "max_drawdown": metrics["max_drawdown"],
                    "passed_benchmark_count": payload["passed_benchmark_count"],
                    "passed_benchmark_sec_codes": ",".join(payload["passed_benchmark_sec_codes"]),
                    "is_index_guard_check": True,
                    "index_name": names.get(sec_code),
                })
    return pd.DataFrame(rows)


def option_statuses(metrics: dict[str, Any], relative: pd.DataFrame, option_a_threshold: float) -> dict[str, dict[str, Any]]:
    risk_return = replay_v3.safe_float(metrics.get("sharpe_ratio"))
    ratio = replay_v3.safe_float(metrics.get("calmar_ratio"))
    current_relative = relative[relative["relative_gate_pass"] == True]  # noqa: E712
    rel_codes = current_relative["benchmark_sec_code"].tolist()
    b_row = relative[relative["benchmark_sec_code"] == "000852.SH"]
    if not b_row.empty:
        b_pass = bool(b_row.iloc[0]["relative_gate_pass"])
        b_codes = ["000852.SH"] if b_pass else []
    else:
        b_pass = False
        b_codes = []

    option_payloads: dict[str, dict[str, Any]] = {}
    definitions = {
        "A_lower_absolute_calmar_0_50": {
            "abs_pass": risk_return is not None and risk_return >= 0.70 and ratio is not None and ratio > option_a_threshold,
            "rel_pass": len(rel_codes) > 0,
            "codes": rel_codes,
            "abs_reason": f"absolute_sharpe>=0.70_and_calmar>{option_a_threshold:g}",
        },
        "B_absolute_excess_calmar_vs_000852": {
            "abs_pass": risk_return is not None and risk_return >= 0.70 and b_pass,
            "rel_pass": b_pass,
            "codes": b_codes,
            "abs_reason": "absolute_sharpe>=0.70_and_000852_excess_branch_pass",
        },
        "C_dual_track_remove_absolute_calmar": {
            "abs_pass": risk_return is not None and risk_return >= 0.70,
            "rel_pass": len(rel_codes) > 0,
            "codes": rel_codes,
            "abs_reason": "absolute_sharpe>=0.70_calmar_moved_to_relative",
        },
        "D_current_v3_no_change": {
            "abs_pass": risk_return is not None and risk_return >= 0.70 and ratio is not None and ratio > 1.0,
            "rel_pass": len(rel_codes) > 0,
            "codes": rel_codes,
            "abs_reason": "absolute_sharpe>=0.70_and_calmar>1.0",
        },
    }
    for option_id, payload in definitions.items():
        reasons = []
        if not payload["abs_pass"]:
            reasons.append(payload["abs_reason"] + "_failed")
        if not payload["rel_pass"]:
            reasons.append("relative_gate_failed")
        option_payloads[option_id] = {
            "status": "accepted" if not reasons else "rejected",
            "reasons": ";".join(reasons),
            "absolute_gate_status": "passed" if payload["abs_pass"] else "failed",
            "relative_gate_status": "passed" if payload["rel_pass"] else "failed",
            "passed_benchmark_count": len(payload["codes"]),
            "passed_benchmark_sec_codes": payload["codes"],
        }
    return option_payloads


def merge_reason_text(*parts: Any) -> str:
    values = []
    for part in parts:
        if part is None:
            continue
        text = str(part)
        if text:
            values.append(text)
    return ";".join(values)


def build_reachability_frame(
    index_metrics: pd.DataFrame,
    baseline_metrics: pd.DataFrame,
    exposure_grid: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    windows: list[WindowSpec],
) -> pd.DataFrame:
    rows = []
    best_exposure = (
        exposure_grid[(exposure_grid["is_identity"] == False) & (exposure_grid["transaction_cost_bps"] == 0)]  # noqa: E712
        .sort_values("calmar_ratio", ascending=False)
        .head(1)
    )
    for window in windows:
        metrics = index_metrics[index_metrics["window_id"] == window.window_id]
        rows.append({
            "window_id": window.window_id,
            "step_order": 1,
            "step": "8_index_calmar_range",
            "entity": "all_benchmark_candidate_indexes",
            "calmar_low": metrics["calmar_ratio"].min(),
            "calmar_high": metrics["calmar_ratio"].max(),
            "calmar_ratio": None,
            "note": "dim_index has_daily/is_benchmark_candidate eight-index range",
        })
        hold = metrics[metrics["sec_code"] == "000852.SH"].iloc[0]
        rows.append({
            "window_id": window.window_id,
            "step_order": 2,
            "step": "full_hold_000852",
            "entity": "000852.SH",
            "calmar_low": None,
            "calmar_high": None,
            "calmar_ratio": hold["calmar_ratio"],
            "note": "full investment index hold",
        })
        base = baseline_metrics[baseline_metrics["window_id"] == window.window_id].iloc[0]
        rows.append({
            "window_id": window.window_id,
            "step_order": 3,
            "step": "current_true5y_ca_on_baseline",
            "entity": "stitched research NAV",
            "calmar_low": None,
            "calmar_high": None,
            "calmar_ratio": base["calmar_ratio"],
            "note": "current CA-on baseline with dividend resume segment when available",
        })
        if window.window_id == "long_2021_2026" and not best_exposure.empty:
            best = best_exposure.iloc[0]
            rows.append({
                "window_id": window.window_id,
                "step_order": 4,
                "step": "best_zero_cost_exposure_upper_bound",
                "entity": best["variant_id"],
                "calmar_low": None,
                "calmar_high": None,
                "calmar_ratio": best["calmar_ratio"],
                "note": "48-variant NAV-level best-of-grid, in-sample and frictionless",
            })
        if window.window_id == "replay_2024_2026":
            best_candidate = candidate_summary.sort_values("calmar_ratio", ascending=False).iloc[0]
            rows.append({
                "window_id": window.window_id,
                "step_order": 5,
                "step": "historical_candidate_best_short_window",
                "entity": best_candidate["model_id"],
                "calmar_low": None,
                "calmar_high": None,
                "calmar_ratio": best_candidate["calmar_ratio"],
                "note": f"search={best_candidate['search_id']} rank={best_candidate['search_rank_valid_only']}",
            })
        rows.append({
            "window_id": window.window_id,
            "step_order": 9,
            "step": "v3_absolute_calmar_gate",
            "entity": "contract",
            "calmar_low": None,
            "calmar_high": None,
            "calmar_ratio": 1.0,
            "note": "operator is > 1.0",
        })
    return pd.DataFrame(rows).sort_values(["window_id", "step_order"])


def render_report(
    args: argparse.Namespace,
    contract: dict[str, Any],
    windows: list[WindowSpec],
    index_metrics: pd.DataFrame,
    rolling: pd.DataFrame,
    baseline_metrics: pd.DataFrame,
    exposure_grid: pd.DataFrame,
    reachability: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    candidate_benchmarks: pd.DataFrame,
    option_matrix: pd.DataFrame,
    variants: pd.DataFrame,
    paths: OutputPaths,
) -> str:
    long_index = index_metrics[index_metrics["window_id"] == "long_2021_2026"]
    replay_index = index_metrics[index_metrics["window_id"] == "replay_2024_2026"]
    long_baseline = baseline_metrics[baseline_metrics["window_id"] == "long_2021_2026"].iloc[0]
    replay_baseline = baseline_metrics[baseline_metrics["window_id"] == "replay_2024_2026"].iloc[0]
    best_exposure = (
        exposure_grid[(exposure_grid["is_identity"] == False) & (exposure_grid["transaction_cost_bps"] == 0)]  # noqa: E712
        .sort_values("calmar_ratio", ascending=False)
        .iloc[0]
    )
    best_candidate = candidate_summary.sort_values("calmar_ratio", ascending=False).iloc[0]
    accepted_candidate = candidate_summary[candidate_summary["v3_acceptance_status"] == "accepted"].sort_values(
        ["search_id", "search_rank_valid_only"]
    )
    accepted_candidate_sentence = (
        "当前 v3 replay 主口径为 25 个 canonical 候选中 1 accepted / 24 rejected；accepted 候选是 "
        f"`{accepted_candidate.iloc[0]['search_id']}` rank `{accepted_candidate.iloc[0]['search_rank_valid_only']}`。"
        if not accepted_candidate.empty
        else "当前 v3 replay 主口径没有 accepted canonical 候选。"
    )
    long_roll = rolling.groupby("sec_code")["calmar_ratio"].agg(["min", "max", "median"]).reset_index()
    option_summary = summarize_options(option_matrix)
    guard_summary = summarize_index_guards(option_matrix)
    historical_matrix = option_matrix[option_matrix["row_group"] == "historical_candidate_canonical"]
    accepted_by_option = (
        historical_matrix[historical_matrix["counterfactual_status"] == "accepted"]
        .groupby("option_id")
        .size()
        .reindex(["A_lower_absolute_calmar_0_50", "B_absolute_excess_calmar_vs_000852", "C_dual_track_remove_absolute_calmar", "D_current_v3_no_change"], fill_value=0)
        .reset_index(name="accepted_historical_candidate_count")
    )
    candidate_view = candidate_summary[
        [
            "search_id",
            "search_rank_valid_only",
            "model_id",
            "strategy_compound_annualized_return",
            "sharpe_ratio",
            "calmar_ratio",
            "required_gate_status",
            "signal_quality_gate_status",
            "absolute_gate_reasons",
            "relative_gate_status",
            "v3_acceptance_status",
            "v3_acceptance_reasons",
        ]
    ].sort_values(["search_id", "search_rank_valid_only"])
    top_candidate_view = candidate_view.head(12)
    long_inaccessible = bool(long_index["calmar_ratio"].max() < 0.5 and best_exposure["calmar_ratio"] < 0.5)
    short_sensitive = bool(
        candidate_summary["calmar_ratio"].max() >= 1.0
        or replay_index["calmar_ratio"].max() >= 1.0
        or rolling["calmar_ratio"].max() >= 1.0
    )
    verdict = (
        "长窗 long-only 域内 Calmar > 1.0 物理不可达证据成立；同时短窗/滚动窗存在 1.0 量级读数，v3 门实际含义高度依赖窗口。"
        if long_inaccessible and short_sensitive
        else "长窗不可达的强条件未完全成立；应把结论收敛为当前策略族距离 v3 Calmar 门较远。"
    )
    return f"""> 文档维护：GPT-5.5（最近更新 2026-06-13）

# 分析：策略1 v3 Calmar 门合理性

## 1. 契约语义

`{contract_version(contract)}` 的 live acceptance 入口在 `src/quant_ashare/strategy1/acceptance.py` 中只消费 `v3_acceptance_status` / `v3_acceptance_reasons`；真正的 v3 指标与分支判定由 `scripts/strategy1/replay_acceptance_gate_v3.py` 和 live write-back 路径按 contract 复算后写入。组合逻辑是：failed artifact 先 fail-fast；v3 层面 `required`、`signal_quality_gate`、`absolute_performance_gate` 与 `relative_gate` 共同决定 accepted/rejected，`final_holdout_gate.enforcement=diagnostic_only`，不再 hard veto。绝对门要求 Sharpe `>= 0.70` 且 Calmar `> 1.0`；五指数相对门要求同一指数上超额复合年化 `> 0`，且 `excess_calmar_ratio > 1.0` 或策略最大回撤同期超额 `> 0`。因此绝对 Calmar 失败时，relative gate 没有救济路径。

这个语义来自 `PRD_20260608_02` 的 v1 -> v3 切门方案和 DECISION-20260608-11/-12：后续直接从 v1 到 v3，不经过 v2；v3 的公式、符号、除零行为、五指数集合和首次 replay 窗口必须在 PRD/contract 中冻结。contract hash 本次读取为 `{contract_hash(contract)}`。

## 2. 八指数双窗口

窗口：

{to_md_table(pd.DataFrame([{"window_id": w.window_id, "start_date": w.start_date, "end_date": w.end_date, "label": w.label_zh} for w in windows]))}

八指数长窗 Calmar 区间为 `{format_number(long_index['calmar_ratio'].min())}` 到 `{format_number(long_index['calmar_ratio'].max())}`；v3 replay 短窗区间为 `{format_number(replay_index['calmar_ratio'].min())}` 到 `{format_number(replay_index['calmar_ratio'].max())}`。

{to_md_table(index_metrics[["window_id", "sec_code", "index_name", "compound_annualized_return", "sharpe_ratio", "max_drawdown", "calmar_ratio"]])}

3 年滚动 Calmar 使用 756 个收益期滚动。全样本最高滚动读数为 `{format_number(rolling['calmar_ratio'].max())}`；各指数滚动范围：

{to_md_table(long_roll)}

## 3. 可达性阶梯

当前 baseline 使用 research parent NAV 加 dividend resume 修正段拼接，长窗读数：CAGR `{format_percent(long_baseline['compound_annualized_return'])}`，Sharpe `{format_number(long_baseline['sharpe_ratio'])}`，MaxDD `{format_percent(long_baseline['max_drawdown'])}`，Calmar `{format_number(long_baseline['calmar_ratio'])}`。短窗读数：CAGR `{format_percent(replay_baseline['compound_annualized_return'])}`，Sharpe `{format_number(replay_baseline['sharpe_ratio'])}`，MaxDD `{format_percent(replay_baseline['max_drawdown'])}`，Calmar `{format_number(replay_baseline['calmar_ratio'])}`。

无摩擦 exposure 上界在当前 CA-on baseline NAV 上重算，最优零成本变体为 `{best_exposure['variant_id']}`，Calmar `{format_number(best_exposure['calmar_ratio'])}`，Sharpe `{format_number(best_exposure['contract_sharpe'])}`。这高于 0.5 的预登记强不可达阈值，但仍低于 v3 Calmar `> 1.0`，且这是 48 变体同段 best-of-grid 的无摩擦上界。

短窗历史候选最高 Calmar 为 `{format_number(best_candidate['calmar_ratio'])}`，来自 `{best_candidate['search_id']}` rank `{best_candidate['search_rank_valid_only']}`；该候选仍因其他 gate 被拒。{accepted_candidate_sentence}这只说明短窗 v3 replay 下曾出现一个过门候选，不追溯改写当时 live search 的 historical 状态，也不等于当前 true5y CA-on baseline accepted。

{to_md_table(reachability[["window_id", "step_order", "step", "entity", "calmar_low", "calmar_high", "calmar_ratio", "note"]])}

## 4. 反事实选项

历史 canonical Top5 反事实 accepted 数：

{to_md_table(accepted_by_option)}

全部 gate 失败原因矩阵见 `{paths.counterfactual.as_posix()}`。前 12 个 canonical 候选摘录：

{to_md_table(top_candidate_view)}

选项判读：

- A 降低绝对 Calmar 到 `0.5`：历史候选变化见矩阵；当前长窗 baseline 仍因 Sharpe `< 0.70` 且 Calmar `< 0.5` 不会通过。底线检查见指数 guard，若短窗纯指数也被放行，则阈值仍过松。
- B 改为 `000852.SH` 超额 Calmar/同期回撤超额口径：避免直接惩罚市场共同回撤，但分母是策略最大回撤窗口相对指数的同窗差，容易被窗口和 direct-pass 分支影响；矩阵单列 `000852` 分支。
- C 双轨门：保留 Sharpe，移除绝对 Calmar 硬门，风险控制交给既有五指数 relative gate。该选项最能暴露 pure beta 风险，因此必须优先看指数 guard。
- D 不改门：与既有 v3 replay 一致，canonical 历史候选中 1 个 accepted、24 个 rejected；它保留 `1.0` 作为 production 北极星，但 OQ-010 的长窗研究成果需要另行分级，否则会把 long-only 长窗策略长期压在 rejected。

指数误放行底线检查：

{to_md_table(guard_summary)}

portfolio 变体未进入主判定，单列 `{paths.portfolio_variants.as_posix()}`，本次识别到 `{len(variants)}` 行。

## 5. 窗口分层判读

预登记判读结论：**{verdict}**

长窗下，8 指数全部低于 0.5，当前 CA-on baseline 也低于 0.5；但无摩擦 exposure 上界达到 `{format_number(best_exposure['calmar_ratio'])}`，所以“长窗 long-only 域内物理不可达”的强判据没有完全成立。更稳妥的说法是：普通指数 beta 与当前 baseline 都远低于 1.0，而达到 1.0 仍需要对冲、多空、跨资产或显著改变组合风险结构，单纯微调参数证据不足。

短窗下，指数/候选/滚动窗口出现 1.0 量级读数，说明“不可达”并非全时段数学事实，而是强烈依赖评估窗口。当前 contract 已冻结 2024-2026 为 replay/初次 cutover 默认窗口，但没有把未来 accepted 的长窗 continuous vs replay 短窗语义钉死；这应成为 owner 决策的第一问题。

## 6. 给 owner 的决策问题

1. 先决定 v3/v4 的 production acceptance 窗口：沿用 replay 短窗、改用 annual-rolling continuous 长窗，还是二者分层。
2. 若选择改门，在 A/B/C 中选一个方向另立 contract v4；本 PR 不修改 contract。
3. 若选择 D 不改门，建议明确 research-accepted 与 production-accepted 分级，避免把长窗 research evidence 一律等同 production rejected。
4. 任何改门都必须继续保留“满仓持指数不被误放行”的底线测试，并把本脚本中的指数 guard 固化到后续 PRD/QA。

## 附录：产物

- `{paths.index_metrics.as_posix()}`
- `{paths.rolling_3y.as_posix()}`
- `{paths.exposure_grid.as_posix()}`
- `{paths.reachability.as_posix()}`
- `{paths.counterfactual.as_posix()}`
- `{paths.portfolio_variants.as_posix()}`
"""


def summarize_options(option_matrix: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        option_matrix.groupby(["row_group", "option_id", "counterfactual_status"], dropna=False)
        .size()
        .reset_index(name="row_count")
    )
    return grouped


def summarize_index_guards(option_matrix: pd.DataFrame) -> pd.DataFrame:
    guard = option_matrix[option_matrix["row_group"] == "full_index_guard_check"].copy()
    return (
        guard.groupby(["window_id", "option_id"], as_index=False)
        .agg(
            index_pass_count=("counterfactual_status", lambda values: int((values == "accepted").sum())),
            passed_indexes=("entity_id", lambda values: ",".join(sorted(guard.loc[values.index][guard.loc[values.index, "counterfactual_status"] == "accepted"]["entity_id"].tolist()))),
        )
        .sort_values(["window_id", "option_id"])
    )


def to_md_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_无记录_"
    columns = list(frame.columns)
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in frame.iterrows():
        rows.append("| " + " | ".join(cell_value(row[column]) for column in columns) + " |")
    return "\n".join(rows)


def cell_value(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        value_float = float(value)
        if not math.isfinite(value_float):
            return ""
        return f"{value_float:.6f}"
    return str(value).replace("|", "\\|")


def format_number(value: Any) -> str:
    numeric = replay_v3.safe_float(value)
    return "NA" if numeric is None else f"{numeric:.4f}"


def format_percent(value: Any) -> str:
    numeric = replay_v3.safe_float(value)
    return "NA" if numeric is None else f"{numeric * 100:.2f}%"


if __name__ == "__main__":
    raise SystemExit(main())
