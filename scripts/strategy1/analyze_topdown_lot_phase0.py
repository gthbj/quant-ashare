#!/usr/bin/env python3
"""Read-only Strategy1 top-down lot-aware Phase 0 paper prototype."""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from google.cloud import bigquery

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.strategy1.analyze_signal_ic_decomposition import (  # noqa: E402
    build_biweekly_rebalance_dates,
    fmt_float,
    fmt_int,
    fmt_pct,
    information_ratio,
    markdown_table,
    max_drawdown,
)
from scripts.strategy1_cloudrun.bq_io import make_client, query_dataframe  # noqa: E402


DEFAULT_PROJECT = "data-aquarium"
DEFAULT_LOCATION = "asia-east2"
DEFAULT_STRATEGY_ID = "ml_pv_clf_v0"
DEFAULT_PREDICTION_RUN_ID = "s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02"
DEFAULT_BACKTEST_ID = "bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02"
DEFAULT_START_DATE = "2021-01-04"
DEFAULT_END_DATE = "2026-06-09"
DEFAULT_FEATURE_VERSION = "strategy1_pv_v0_20260601"
DEFAULT_BENCHMARK_SEC_CODE = "000852.SH"
DEFAULT_INITIAL_CAPITAL = 100_000.0
DEFAULT_POSITION_FLOOR_COUNT = 20
DEFAULT_WALK_DEPTHS = (30, 50)
DEFAULT_COST_BPS = (0.0, 20.0)
DEFAULT_REPORT_MD = "docs/分析-策略1自上而下整手组合Phase0-20260612.md"
DEFAULT_METRICS_CSV = "docs/analysis_strategy1_topdown_lot_phase0_20260612_metrics.csv"
DEFAULT_DAILY_CSV = "docs/analysis_strategy1_topdown_lot_phase0_20260612_daily.csv"
DEFAULT_AUDIT_CSV = "docs/analysis_strategy1_topdown_lot_phase0_20260612_rebalance_audit.csv"
DEFAULT_PRD09_TRANSFER_CSV = "docs/analysis_strategy1_transfer_ladder_20260611_results.csv"
CRUNCH_START = "2024-01-01"
CRUNCH_END = "2024-02-07"
TRADING_DAYS_PER_YEAR = 252.0
LOT_SIZE = 100

P1_RULE_FIELDS = (
    "ret_20d",
    "drawdown_20d",
    "limit_down_days_20d",
    "one_word_limit_days_20d",
    "total_mv_cny",
    "circ_mv_cny",
)


@dataclass(frozen=True)
class Phase0Config:
    project: str
    location: str
    strategy_id: str
    prediction_run_id: str
    backtest_id: str
    start_date: str
    end_date: str
    feature_version: str
    benchmark_sec_code: str
    initial_capital: float
    position_floor_count: int
    walk_depths: tuple[int, ...]
    cost_bps_values: tuple[float, ...]
    report_md: Path
    metrics_csv: Path
    daily_csv: Path
    audit_csv: Path
    prd09_transfer_csv: Path
    skip_report: bool

    @property
    def min_position_weight(self) -> float:
        return 1.0 / float(self.position_floor_count)


@dataclass(frozen=True)
class PortfolioState:
    cash: float
    holdings: dict[str, float]
    previous_nav_value: float


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run PRD_20260611_10 Phase 0 top-down lot-aware paper prototype."
    )
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--location", default=DEFAULT_LOCATION)
    parser.add_argument("--strategy-id", default=DEFAULT_STRATEGY_ID)
    parser.add_argument("--prediction-run-id", default=DEFAULT_PREDICTION_RUN_ID)
    parser.add_argument("--backtest-id", default=DEFAULT_BACKTEST_ID)
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    parser.add_argument("--feature-version", default=DEFAULT_FEATURE_VERSION)
    parser.add_argument("--benchmark-sec-code", default=DEFAULT_BENCHMARK_SEC_CODE)
    parser.add_argument("--initial-capital", type=float, default=DEFAULT_INITIAL_CAPITAL)
    parser.add_argument("--position-floor-count", type=int, default=DEFAULT_POSITION_FLOOR_COUNT)
    parser.add_argument("--walk-depths", default=",".join(str(v) for v in DEFAULT_WALK_DEPTHS))
    parser.add_argument("--cost-bps", default=",".join(str(v) for v in DEFAULT_COST_BPS))
    parser.add_argument("--report-md", default=DEFAULT_REPORT_MD)
    parser.add_argument("--metrics-csv", default=DEFAULT_METRICS_CSV)
    parser.add_argument("--daily-csv", default=DEFAULT_DAILY_CSV)
    parser.add_argument("--audit-csv", default=DEFAULT_AUDIT_CSV)
    parser.add_argument("--prd09-transfer-csv", default=DEFAULT_PRD09_TRANSFER_CSV)
    parser.add_argument("--skip-report", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> Phase0Config:
    return Phase0Config(
        project=args.project,
        location=args.location,
        strategy_id=args.strategy_id,
        prediction_run_id=args.prediction_run_id,
        backtest_id=args.backtest_id,
        start_date=args.start_date,
        end_date=args.end_date,
        feature_version=args.feature_version,
        benchmark_sec_code=args.benchmark_sec_code,
        initial_capital=float(args.initial_capital),
        position_floor_count=int(args.position_floor_count),
        walk_depths=parse_int_tuple(args.walk_depths),
        cost_bps_values=parse_float_tuple(args.cost_bps),
        report_md=Path(args.report_md),
        metrics_csv=Path(args.metrics_csv),
        daily_csv=Path(args.daily_csv),
        audit_csv=Path(args.audit_csv),
        prd09_transfer_csv=Path(args.prd09_transfer_csv),
        skip_report=bool(args.skip_report),
    )


def parse_int_tuple(value: str) -> tuple[int, ...]:
    parsed = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    if not parsed or any(v <= 0 for v in parsed):
        raise ValueError("--walk-depths must contain positive integers")
    return parsed


def parse_float_tuple(value: str) -> tuple[float, ...]:
    parsed = tuple(float(part.strip()) for part in value.split(",") if part.strip())
    if not parsed or any(v < 0 for v in parsed):
        raise ValueError("--cost-bps must contain non-negative numbers")
    return parsed


def main(argv: list[str] | None = None) -> int:
    cfg = config_from_args(parse_args(argv))
    client = make_client(cfg.project, cfg.location)

    max_depth = max(cfg.walk_depths)
    print("Fetching top-ranked candidates and local P1 fields...", flush=True)
    candidates = fetch_candidates(client, cfg, max_depth)
    candidates = add_tail_risk_reasons(candidates)
    validate_candidates(candidates, cfg, max_depth)

    print("Fetching calendar, benchmark, prices, and official baseline...", flush=True)
    calendar = fetch_calendar(client, cfg)
    benchmark = fetch_benchmark(client, cfg)
    official_nav = fetch_official_nav(client, cfg)
    official_summary = fetch_official_summary(client, cfg)
    prices = fetch_prices(client, cfg, sorted(candidates["sec_code"].dropna().astype(str).unique()))
    price_book = PriceBook(prices)

    print("Simulating T0/T1 top-down paper arms...", flush=True)
    metrics_frames: list[pd.DataFrame] = []
    daily_frames: list[pd.DataFrame] = []
    audit_frames: list[pd.DataFrame] = []
    for walk_depth in cfg.walk_depths:
        for cost_bps in cfg.cost_bps_values:
            for arm in ("T0", "T1"):
                daily, audit = simulate_arm(
                    cfg=cfg,
                    arm=arm,
                    walk_depth=walk_depth,
                    cost_bps=cost_bps,
                    candidates=candidates,
                    calendar=calendar,
                    benchmark=benchmark,
                    price_book=price_book,
                )
                daily_frames.append(daily)
                audit_frames.append(audit)
                metrics_frames.append(pd.DataFrame([summarize_arm(daily, audit, cfg, arm, walk_depth, cost_bps)]))

    metrics = pd.concat(metrics_frames, ignore_index=True)
    daily_all = pd.concat(daily_frames, ignore_index=True)
    audit_all = pd.concat(audit_frames, ignore_index=True)
    official_metrics = summarize_official_baseline(official_nav, benchmark, official_summary, cfg)
    prd09_l3 = load_prd09_l3(cfg.prd09_transfer_csv)

    write_outputs(cfg, metrics, daily_all, audit_all, official_metrics, prd09_l3, candidates)
    print_summary(metrics, official_metrics)
    return 0


def fetch_candidates(client: bigquery.Client, cfg: Phase0Config, max_depth: int) -> pd.DataFrame:
    sql = f"""
    SELECT
      cand.rebalance_date,
      cand.sec_code,
      cand.score,
      cand.rank_raw,
      cand.filter_reason AS source_filter_reason,
      feat.ret_20d,
      feat.drawdown_20d,
      feat.limit_down_days_20d,
      feat.one_word_limit_days_20d,
      feat.total_mv_cny,
      feat.circ_mv_cny
    FROM `{cfg.project}.ashare_research.research_stock_candidate_daily` AS cand
    LEFT JOIN `{cfg.project}.ashare_dws.dws_stock_feature_daily_v0` AS feat
      ON feat.trade_date = cand.rebalance_date
     AND feat.sec_code = cand.sec_code
     AND feat.feature_version = @feature_version
     AND feat.trade_date BETWEEN @start_date AND @end_date
    WHERE cand.strategy_id = @strategy_id
      AND cand.run_id = @prediction_run_id
      AND cand.rebalance_date BETWEEN @start_date AND @end_date
      AND cand.rank_raw IS NOT NULL
      AND cand.rank_raw <= @max_depth
    ORDER BY cand.rebalance_date, cand.rank_raw, cand.sec_code
    """
    return normalize_dates(
        query_dataframe(
            client,
            sql,
            [
                bigquery.ScalarQueryParameter("strategy_id", "STRING", cfg.strategy_id),
                bigquery.ScalarQueryParameter("prediction_run_id", "STRING", cfg.prediction_run_id),
                bigquery.ScalarQueryParameter("feature_version", "STRING", cfg.feature_version),
                bigquery.ScalarQueryParameter("start_date", "DATE", cfg.start_date),
                bigquery.ScalarQueryParameter("end_date", "DATE", cfg.end_date),
                bigquery.ScalarQueryParameter("max_depth", "INT64", max_depth),
            ],
            labels={"step": "topdown_phase0_candidates", "mode": "readonly"},
        ),
        ["rebalance_date"],
    )


def fetch_calendar(client: bigquery.Client, cfg: Phase0Config) -> pd.DataFrame:
    sql = f"""
    SELECT cal_date AS trade_date, trade_date_seq
    FROM `{cfg.project}.ashare_dim.dim_trade_calendar`
    WHERE exchange = 'SSE'
      AND is_open = 1
      AND cal_date BETWEEN @start_date AND @end_date
    ORDER BY cal_date
    """
    return normalize_dates(
        query_dataframe(
            client,
            sql,
            [
                bigquery.ScalarQueryParameter("start_date", "DATE", cfg.start_date),
                bigquery.ScalarQueryParameter("end_date", "DATE", cfg.end_date),
            ],
            labels={"step": "topdown_phase0_calendar", "mode": "readonly"},
        ),
        ["trade_date"],
    )


def fetch_benchmark(client: bigquery.Client, cfg: Phase0Config) -> pd.DataFrame:
    sql = f"""
    SELECT trade_date, SAFE_DIVIDE(pct_chg, 100.0) AS benchmark_return
    FROM `{cfg.project}.ashare_dwd.dwd_index_eod`
    WHERE sec_code = @benchmark_sec_code
      AND trade_date BETWEEN @start_date AND @end_date
    ORDER BY trade_date
    """
    return normalize_dates(
        query_dataframe(
            client,
            sql,
            [
                bigquery.ScalarQueryParameter("benchmark_sec_code", "STRING", cfg.benchmark_sec_code),
                bigquery.ScalarQueryParameter("start_date", "DATE", cfg.start_date),
                bigquery.ScalarQueryParameter("end_date", "DATE", cfg.end_date),
            ],
            labels={"step": "topdown_phase0_benchmark", "mode": "readonly"},
        ),
        ["trade_date"],
    )


def fetch_official_nav(client: bigquery.Client, cfg: Phase0Config) -> pd.DataFrame:
    sql = f"""
    SELECT trade_date, nav, daily_return, cash_cny, net_value_cny, benchmark_return
    FROM `{cfg.project}.ashare_research.research_backtest_nav_daily`
    WHERE backtest_id = @backtest_id
      AND trade_date BETWEEN @start_date AND @end_date
    ORDER BY trade_date
    """
    return normalize_dates(
        query_dataframe(
            client,
            sql,
            [
                bigquery.ScalarQueryParameter("backtest_id", "STRING", cfg.backtest_id),
                bigquery.ScalarQueryParameter("start_date", "DATE", cfg.start_date),
                bigquery.ScalarQueryParameter("end_date", "DATE", cfg.end_date),
            ],
            labels={"step": "topdown_phase0_official_nav", "mode": "readonly"},
        ),
        ["trade_date"],
    )


def fetch_official_summary(client: bigquery.Client, cfg: Phase0Config) -> pd.DataFrame:
    sql = f"""
    SELECT
      backtest_id,
      run_id,
      compound_annual_return,
      annual_vol,
      sharpe,
      information_ratio,
      max_drawdown,
      return_period_count
    FROM `{cfg.project}.ashare_research.research_backtest_performance_summary`
    WHERE backtest_id = @backtest_id
      AND created_date BETWEEN DATE '2026-06-01' AND CURRENT_DATE()
    ORDER BY created_date DESC
    LIMIT 1
    """
    return query_dataframe(
        client,
        sql,
        [bigquery.ScalarQueryParameter("backtest_id", "STRING", cfg.backtest_id)],
        labels={"step": "topdown_phase0_official_summary", "mode": "readonly"},
    )


def fetch_prices(client: bigquery.Client, cfg: Phase0Config, sec_codes: list[str]) -> pd.DataFrame:
    if not sec_codes:
        raise ValueError("no candidate sec_codes")
    start_buffer = (pd.Timestamp(cfg.start_date).date() - timedelta(days=10)).isoformat()
    sql = f"""
    SELECT
      sec_code,
      trade_date,
      open,
      close,
      COALESCE(can_buy_open, FALSE) AS can_buy_open,
      COALESCE(can_sell_open, FALSE) AS can_sell_open
    FROM `{cfg.project}.ashare_dwd.dwd_stock_eod_price`
    WHERE trade_date BETWEEN @start_buffer AND @end_date
      AND sec_code IN UNNEST(@sec_codes)
    ORDER BY sec_code, trade_date
    """
    return normalize_dates(
        query_dataframe(
            client,
            sql,
            [
                bigquery.ScalarQueryParameter("start_buffer", "DATE", start_buffer),
                bigquery.ScalarQueryParameter("end_date", "DATE", cfg.end_date),
                bigquery.ArrayQueryParameter("sec_codes", "STRING", sec_codes),
            ],
            labels={"step": "topdown_phase0_prices", "mode": "readonly"},
        ),
        ["trade_date"],
    )


def normalize_dates(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col in frame.columns:
            frame[col] = pd.to_datetime(frame[col]).dt.date
    return frame


def add_tail_risk_reasons(candidates: pd.DataFrame) -> pd.DataFrame:
    out = candidates.copy()
    out["tail_risk_reason"] = [tail_risk_reason(row) for row in out.to_dict("records")]
    return out


def tail_risk_reason(row: dict[str, Any] | pd.Series) -> str | None:
    values = {field: row.get(field) for field in P1_RULE_FIELDS}
    if any(pd.isna(value) for value in values.values()):
        return "tail_risk:required_field_null"
    reasons: list[str] = []
    if float(values["ret_20d"]) < -0.30:
        reasons.append("tail_risk:ret_20d_lt_30pct")
    if float(values["drawdown_20d"]) < -0.30:
        reasons.append("tail_risk:drawdown_20d_lt_30pct")
    if float(values["limit_down_days_20d"]) >= 2:
        reasons.append("tail_risk:limit_down_days_20d_ge_2")
    if float(values["one_word_limit_days_20d"]) >= 1:
        reasons.append("tail_risk:one_word_limit_days_20d_ge_1")
    if float(values["total_mv_cny"]) < 30e8:
        reasons.append("tail_risk:total_mv_lt_30e8")
    if float(values["circ_mv_cny"]) < 20e8:
        reasons.append("tail_risk:circ_mv_lt_20e8")
    return "|".join(reasons) if reasons else None


def validate_candidates(candidates: pd.DataFrame, cfg: Phase0Config, max_depth: int) -> None:
    if candidates.empty:
        raise ValueError(f"no candidate rows for run {cfg.prediction_run_id}")
    per_day = candidates.groupby("rebalance_date")["rank_raw"].nunique()
    shallow = per_day[per_day < max_depth]
    if not shallow.empty:
        first = shallow.index[0]
        raise ValueError(f"candidate rows do not cover walk_depth={max_depth}; first shallow date {first}")
    if candidates["tail_risk_reason"].notna().sum() <= 0:
        raise ValueError("local P1 marker calculation produced zero tail-risk rows")


class PriceBook:
    def __init__(self, prices: pd.DataFrame):
        px = prices.sort_values(["sec_code", "trade_date"]).copy()
        px["close_ffill"] = px.groupby("sec_code")["close"].ffill()
        px["prev_close_ffill"] = px.groupby("sec_code")["close_ffill"].shift(1)
        self.by_key = {(str(row.sec_code), row.trade_date): row for row in px.itertuples(index=False)}

    def row(self, sec_code: str, trade_date: date) -> Any | None:
        return self.by_key.get((str(sec_code), trade_date))

    def valuation_price(self, sec_code: str, trade_date: date) -> float:
        row = self.row(sec_code, trade_date)
        if row is None:
            return 0.0
        return first_finite(row.prev_close_ffill, row.open, row.close_ffill, default=0.0)

    def open_price(self, sec_code: str, trade_date: date) -> float | None:
        row = self.row(sec_code, trade_date)
        if row is None:
            return None
        return first_finite(row.open, default=None)

    def close_price(self, sec_code: str, trade_date: date) -> float | None:
        row = self.row(sec_code, trade_date)
        if row is None:
            return None
        return first_finite(row.close_ffill, row.open, default=None)

    def can_buy_open(self, sec_code: str, trade_date: date) -> bool:
        row = self.row(sec_code, trade_date)
        return bool(getattr(row, "can_buy_open", False)) if row is not None else False


def first_finite(*values: Any, default: Any = None) -> Any:
    for value in values:
        if value is None:
            continue
        try:
            if np.isfinite(value):
                return float(value)
        except TypeError:
            continue
    return default


def simulate_arm(
    *,
    cfg: Phase0Config,
    arm: str,
    walk_depth: int,
    cost_bps: float,
    candidates: pd.DataFrame,
    calendar: pd.DataFrame,
    benchmark: pd.DataFrame,
    price_book: PriceBook,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    trading_dates = sorted(calendar["trade_date"].tolist())
    rebalance_dates = build_biweekly_rebalance_dates(calendar, cfg.start_date, cfg.end_date)
    next_open = next_open_map(trading_dates)
    signal_by_exec = {next_open[d]: d for d in rebalance_dates if d in next_open}
    candidates_by_date = {
        signal_date: group.sort_values(["rank_raw", "sec_code"]).copy()
        for signal_date, group in candidates[candidates["rank_raw"] <= walk_depth].groupby("rebalance_date")
    }
    benchmark_by_date = dict(zip(benchmark["trade_date"], benchmark["benchmark_return"].astype(float)))
    state = PortfolioState(
        cash=float(cfg.initial_capital),
        holdings={},
        previous_nav_value=float(cfg.initial_capital),
    )
    daily_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    for trade_date in trading_dates:
        signal_date = signal_by_exec.get(trade_date)
        is_rebalance = signal_date is not None
        nav_before = state.cash + sum(
            shares * price_book.valuation_price(sec, trade_date) for sec, shares in state.holdings.items()
        )
        day_turnover = 0.0
        day_cost = 0.0
        day_audit: dict[str, Any] = {}
        if is_rebalance:
            state, day_turnover, day_cost, day_audit = rebalance_topdown(
                cfg=cfg,
                state=state,
                trade_date=trade_date,
                signal_date=signal_date,
                arm=arm,
                walk_depth=walk_depth,
                cost_bps=cost_bps,
                nav_before=nav_before,
                candidates=candidates_by_date.get(signal_date, pd.DataFrame()),
                price_book=price_book,
            )
        position_value, holdings_count, max_weight = mark_positions(state.holdings, price_book, trade_date)
        nav_value = state.cash + position_value
        daily_return = nav_value / state.previous_nav_value - 1.0 if state.previous_nav_value else np.nan
        state = PortfolioState(cash=state.cash, holdings=state.holdings, previous_nav_value=nav_value)
        benchmark_return = float(benchmark_by_date.get(trade_date, 0.0) or 0.0)
        daily_rows.append(
            {
                "arm": arm,
                "walk_depth": walk_depth,
                "cost_bps": cost_bps,
                "trade_date": trade_date,
                "signal_date": signal_date,
                "is_rebalance": is_rebalance,
                "nav": nav_value / cfg.initial_capital,
                "net_value_cny": nav_value,
                "cash_cny": state.cash,
                "cash_weight": state.cash / nav_value if nav_value > 0 else np.nan,
                "position_value_cny": position_value,
                "gross_exposure": position_value / nav_value if nav_value > 0 else np.nan,
                "realized_holdings_count": holdings_count,
                "max_realized_weight": max_weight,
                "turnover_cny": day_turnover,
                "cost_cny": day_cost,
                "daily_return": daily_return,
                "benchmark_return": benchmark_return,
                "excess_return": daily_return - benchmark_return if pd.notna(daily_return) else np.nan,
            }
        )
        if is_rebalance:
            day_audit.update({"arm": arm, "walk_depth": walk_depth, "cost_bps": cost_bps})
            audit_rows.append(day_audit)
    return pd.DataFrame(daily_rows), pd.DataFrame(audit_rows)


def rebalance_topdown(
    *,
    cfg: Phase0Config,
    state: PortfolioState,
    trade_date: date,
    signal_date: date,
    arm: str,
    walk_depth: int,
    cost_bps: float,
    nav_before: float,
    candidates: pd.DataFrame,
    price_book: PriceBook,
) -> tuple[PortfolioState, float, float, dict[str, Any]]:
    cash = float(state.cash)
    holdings = dict(state.holdings)
    turnover = 0.0
    cost = 0.0
    retained = set()
    rank_by_sec = dict(zip(candidates["sec_code"].astype(str), candidates["rank_raw"].astype(float))) if not candidates.empty else {}
    candidate_secs = set(rank_by_sec)
    for sec, shares in list(holdings.items()):
        rank = rank_by_sec.get(sec)
        if rank is not None and rank <= walk_depth:
            retained.add(sec)
            continue
        sell_price = price_book.open_price(sec, trade_date) or price_book.valuation_price(sec, trade_date)
        if sell_price <= 0:
            continue
        gross = shares * sell_price
        sell_cost = gross * cost_bps / 10000.0
        cash += gross - sell_cost
        turnover += gross
        cost += sell_cost
        del holdings[sec]

    buy_filled = 0
    p1_skip = 0
    unbuyable_skip = 0
    cash_skip = 0
    below_lot_skip = 0
    evaluated_count = 0
    min_weight = cfg.min_position_weight
    min_cash_threshold = min_weight * nav_before * (1.0 + cost_bps / 10000.0)
    if not candidates.empty:
        for row in candidates.sort_values(["rank_raw", "sec_code"]).itertuples(index=False):
            sec = str(row.sec_code)
            evaluated_count += 1
            if sec in retained or sec in holdings:
                continue
            if arm == "T1" and pd.notna(getattr(row, "tail_risk_reason", None)):
                p1_skip += 1
                continue
            open_price = price_book.open_price(sec, trade_date)
            if open_price is None or open_price <= 0 or not price_book.can_buy_open(sec, trade_date):
                unbuyable_skip += 1
                continue
            desired_shares = min_buy_shares(nav_before, open_price, min_weight)
            if desired_shares < LOT_SIZE:
                below_lot_skip += 1
                continue
            gross = desired_shares * open_price
            buy_cost = gross * cost_bps / 10000.0
            required_cash = gross + buy_cost
            if cash + 1e-6 >= required_cash:
                holdings[sec] = holdings.get(sec, 0.0) + desired_shares
                cash -= required_cash
                turnover += gross
                cost += buy_cost
                buy_filled += 1
            else:
                cash_skip += 1
            if cash < min_cash_threshold:
                break
    audit = {
        "signal_date": signal_date,
        "exec_date": trade_date,
        "candidate_count": int(len(candidates)),
        "evaluated_count": int(evaluated_count),
        "retained_count": int(len(retained)),
        "sell_count": int(len(set(state.holdings) - set(holdings))),
        "buy_filled_count": int(buy_filled),
        "p1_skip_count": int(p1_skip),
        "unbuyable_skip_count": int(unbuyable_skip),
        "cash_insufficient_skip_count": int(cash_skip),
        "below_lot_skip_count": int(below_lot_skip),
        "ending_holdings_count": int(len(holdings)),
        "ending_cash_cny": cash,
        "ending_cash_weight_pre_close": cash / nav_before if nav_before > 0 else np.nan,
        "turnover_cny": turnover,
        "cost_cny": cost,
        "ranked_candidates_seen": int(len(candidate_secs)),
    }
    return PortfolioState(cash=cash, holdings=holdings, previous_nav_value=state.previous_nav_value), turnover, cost, audit


def min_buy_shares(nav_value: float, open_price: float, min_weight: float) -> float:
    lot_notional = LOT_SIZE * open_price
    if lot_notional <= 0:
        return 0.0
    lots = math.ceil((min_weight * nav_value) / lot_notional)
    return float(max(1, lots) * LOT_SIZE)


def mark_positions(holdings: dict[str, float], price_book: PriceBook, trade_date: date) -> tuple[float, int, float]:
    values: list[float] = []
    for sec, shares in holdings.items():
        close = price_book.close_price(sec, trade_date)
        if close is None or close <= 0:
            continue
        values.append(float(shares) * float(close))
    position_value = float(sum(values))
    max_weight = max(values) / position_value if position_value > 0 and values else 0.0
    return position_value, len(values), max_weight


def next_open_map(trading_dates: list[date]) -> dict[date, date]:
    return {trade_date: trading_dates[i + 1] for i, trade_date in enumerate(trading_dates[:-1])}


def summarize_arm(
    daily: pd.DataFrame,
    audit: pd.DataFrame,
    cfg: Phase0Config,
    arm: str,
    walk_depth: int,
    cost_bps: float,
) -> dict[str, Any]:
    clean_returns = daily["daily_return"].fillna(0.0).astype(float)
    benchmark = daily["benchmark_return"].fillna(0.0).astype(float)
    nav = (1.0 + clean_returns).cumprod()
    total_return = float(nav.iloc[-1] - 1.0)
    n = int(len(clean_returns))
    cagr = compound_annual_return(total_return, n)
    annual_vol = float(clean_returns.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR)) if n > 1 else np.nan
    maxdd, peak, trough = max_drawdown(nav.reset_index(drop=True), daily["trade_date"].reset_index(drop=True))
    excess = clean_returns - benchmark
    crunch = daily[
        (pd.to_datetime(daily["trade_date"]) >= pd.Timestamp(CRUNCH_START))
        & (pd.to_datetime(daily["trade_date"]) <= pd.Timestamp(CRUNCH_END))
    ]
    crunch_return = compound_total_return(crunch["daily_return"])
    crunch_benchmark = compound_total_return(crunch["benchmark_return"])
    turnover = float(audit["turnover_cny"].sum()) if not audit.empty else 0.0
    return {
        "arm": arm,
        "walk_depth": walk_depth,
        "cost_bps": cost_bps,
        "total_return": total_return,
        "compound_annual_return": cagr,
        "annual_vol": annual_vol,
        "absolute_sharpe_or_contract_sharpe": cagr / annual_vol if annual_vol > 0 else np.nan,
        "information_ratio_vs_000852": information_ratio(excess),
        "max_drawdown": maxdd,
        "max_drawdown_peak_date": peak,
        "max_drawdown_trough_date": trough,
        "calmar_ratio": cagr / abs(maxdd) if maxdd < 0 else np.nan,
        "crunch_strategy_return": crunch_return,
        "crunch_000852_return": crunch_benchmark,
        "crunch_excess_return_vs_000852": crunch_return - crunch_benchmark,
        "avg_cash_weight": float(daily["cash_weight"].mean()),
        "max_cash_weight": float(daily["cash_weight"].max()),
        "cash_gt_50pct_days": int((daily["cash_weight"] > 0.5).sum()),
        "avg_realized_holdings_count": float(daily["realized_holdings_count"].mean()),
        "min_realized_holdings_count": int(daily["realized_holdings_count"].min()),
        "p05_realized_holdings_count": float(daily["realized_holdings_count"].quantile(0.05)),
        "avg_max_realized_weight": float(daily["max_realized_weight"].mean()),
        "p95_max_realized_weight": float(daily["max_realized_weight"].quantile(0.95)),
        "max_realized_weight": float(daily["max_realized_weight"].max()),
        "max_weight_gt_40pct_days": int((daily["max_realized_weight"] > 0.40).sum()),
        "annual_turnover": turnover / cfg.initial_capital / (n / TRADING_DAYS_PER_YEAR) if n > 0 else np.nan,
        "total_cost_cny": float(audit["cost_cny"].sum()) if not audit.empty else 0.0,
        "rebalance_count": int(audit.shape[0]),
        "p1_skip_count": int(audit["p1_skip_count"].sum()) if "p1_skip_count" in audit.columns else 0,
        "unbuyable_skip_count": int(audit["unbuyable_skip_count"].sum()) if "unbuyable_skip_count" in audit.columns else 0,
        "cash_insufficient_skip_count": int(audit["cash_insufficient_skip_count"].sum()) if "cash_insufficient_skip_count" in audit.columns else 0,
        "return_period_count": n,
    }


def summarize_official_baseline(
    official_nav: pd.DataFrame,
    benchmark: pd.DataFrame,
    official_summary: pd.DataFrame,
    cfg: Phase0Config,
) -> dict[str, Any]:
    if official_nav.empty:
        return {}
    nav = official_nav.copy()
    bench = benchmark[["trade_date", "benchmark_return"]].copy()
    nav = nav.drop(columns=[c for c in ["benchmark_return"] if c in nav.columns]).merge(bench, on="trade_date", how="left")
    returns = nav["daily_return"].fillna(0.0).astype(float)
    benchmark_returns = nav["benchmark_return"].fillna(0.0).astype(float)
    total_return = float(nav["nav"].iloc[-1] / nav["nav"].iloc[0] - 1.0)
    n = int(len(returns))
    summary_row = official_summary.iloc[0].to_dict() if not official_summary.empty else {}
    cagr = float(summary_row.get("compound_annual_return", np.nan))
    if pd.isna(cagr):
        cagr = compound_annual_return(total_return, n)
    annual_vol = float(summary_row.get("annual_vol", np.nan))
    if pd.isna(annual_vol):
        annual_vol = float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR)) if n > 1 else np.nan
    maxdd, peak, trough = max_drawdown(nav["nav"].reset_index(drop=True), nav["trade_date"].reset_index(drop=True))
    if pd.notna(summary_row.get("max_drawdown", np.nan)):
        maxdd = float(summary_row["max_drawdown"])
    crunch = nav[
        (pd.to_datetime(nav["trade_date"]) >= pd.Timestamp(CRUNCH_START))
        & (pd.to_datetime(nav["trade_date"]) <= pd.Timestamp(CRUNCH_END))
    ]
    return_period_count = int(summary_row.get("return_period_count") or n)
    return {
        "label": "official_baseline_v1_lot100",
        "backtest_id": cfg.backtest_id,
        "compound_annual_return": cagr,
        "annual_vol": annual_vol,
        "absolute_sharpe_or_contract_sharpe": float(summary_row.get("sharpe", np.nan)),
        "information_ratio_vs_000852": float(summary_row.get("information_ratio", np.nan))
        if pd.notna(summary_row.get("information_ratio", np.nan))
        else information_ratio(returns - benchmark_returns),
        "max_drawdown": maxdd,
        "max_drawdown_peak_date": peak,
        "max_drawdown_trough_date": trough,
        "calmar_ratio": cagr / abs(maxdd) if maxdd < 0 else np.nan,
        "crunch_excess_return_vs_000852": compound_total_return(crunch["daily_return"]) - compound_total_return(crunch["benchmark_return"]),
        "avg_cash_weight": float((nav["cash_cny"] / nav["net_value_cny"]).mean()) if {"cash_cny", "net_value_cny"} <= set(nav.columns) else np.nan,
        "return_period_count": return_period_count,
    }


def load_prd09_l3(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    return frame[frame["level"].astype(str).eq("L3")].copy()


def compound_total_return(values: pd.Series) -> float:
    clean = values.dropna().astype(float)
    if clean.empty:
        return np.nan
    return float((1.0 + clean).prod() - 1.0)


def compound_annual_return(total_return: float, periods: int) -> float:
    if periods <= 0 or total_return <= -1.0:
        return np.nan
    return float((1.0 + total_return) ** (TRADING_DAYS_PER_YEAR / periods) - 1.0)


def write_outputs(
    cfg: Phase0Config,
    metrics: pd.DataFrame,
    daily: pd.DataFrame,
    audit: pd.DataFrame,
    official_metrics: dict[str, Any],
    prd09_l3: pd.DataFrame,
    candidates: pd.DataFrame,
) -> None:
    for path, frame in [(cfg.metrics_csv, metrics), (cfg.daily_csv, daily), (cfg.audit_csv, audit)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    if not cfg.skip_report:
        cfg.report_md.parent.mkdir(parents=True, exist_ok=True)
        cfg.report_md.write_text(
            build_report(cfg, metrics, official_metrics, prd09_l3, candidates),
            encoding="utf-8",
        )


def build_report(
    cfg: Phase0Config,
    metrics: pd.DataFrame,
    official_metrics: dict[str, Any],
    prd09_l3: pd.DataFrame,
    candidates: pd.DataFrame,
) -> str:
    primary = metrics[(metrics["walk_depth"] == 50) & (metrics["cost_bps"] == 20.0)].copy()
    t0 = row_for(primary, "T0")
    t1 = row_for(primary, "T1")
    cagr_diff = metric_diff(t1, t0, "compound_annual_return")
    crunch_diff = metric_diff(t1, t0, "crunch_excess_return_vs_000852")
    p1_count = int(candidates["tail_risk_reason"].notna().sum())
    p1_in_depth = int(candidates[(candidates["rank_raw"] <= 50) & candidates["tail_risk_reason"].notna()].shape[0])
    p1_reason_table = (
        candidates["tail_risk_reason"]
        .fillna("none")
        .value_counts()
        .head(12)
        .rename_axis("tail_risk_reason")
        .reset_index(name="row_count")
    )
    lines = [
        "# 策略1自上而下整手组合构造 Phase 0",
        "",
        "> 文档维护：GPT-5 Codex（最近更新 2026-06-12）",
        "",
        "## 方法与边界",
        "",
        f"- prediction_run_id: `{cfg.prediction_run_id}`",
        f"- official backtest_id: `{cfg.backtest_id}`",
        f"- 窗口: `{cfg.start_date}` 至 `{cfg.end_date}`；初始资金 `{cfg.initial_capital:,.0f}` 元；整手 `100` 股。",
        f"- `position_floor_count={cfg.position_floor_count}`，新开仓最小仓位 `{fmt_pct(cfg.min_position_weight)}`；walk_depth 敏感性 `{', '.join(map(str, cfg.walk_depths))}`；成本档 `{', '.join(str(v) for v in cfg.cost_bps_values)} bps`。",
        "- T0：自上而下整手构造，不启用 P1 个股过滤；T1：同构造，但新买入遇到本地计算的 P1 `tail_risk:*` 标记时跳过并继续走下一名。",
        "- P1 标记在本地从 `dws_stock_feature_daily_v0` 六条规则现算；source candidate 当前没有 `tail_risk:*` 标记。该处理是 research-only helper artifact，不是模型重训。",
        "- paper 原型模拟买入可交易性和整手/现金约束；卖出失败与 `PENDING_SELL_CARRY` 不模拟，超深度持仓按当日 open/valuation 假定卖出。Phase 2 真实 ledger 需量化这部分偏差。",
        "- 成本档按单边 turnover bps 处理；20bps 档买入可负担性使用含费现金，卖出按扣费后回款。",
        "- BigQuery 全程只读；脚本只读取 research/DWS/DWD/DIM 表并在本地 pandas 计算，未写 `ashare_research` / ADS / promotion 表。",
        "",
        "## 输入覆盖",
        "",
        f"- rebalance 日期数: {fmt_int(candidates['rebalance_date'].nunique())}",
        f"- 候选行数（rank <= max walk_depth）: {fmt_int(len(candidates))}",
        f"- 本地 P1 标记行数: {fmt_int(p1_count)}；rank<=50 内 P1 标记行数: {fmt_int(p1_in_depth)}",
        "",
        "P1 标记原因 Top12：",
        "",
        markdown_table(p1_reason_table),
        "",
        "## 主结果（walk_depth=50, 20bps）",
        "",
        markdown_table(compact_metrics(primary)),
        "",
        "预登记判读：",
        f"- T1 - T0 CAGR 差: {fmt_pct(cagr_diff)}；T1 - T0 crunch 段超额差: {fmt_pct(crunch_diff)}。",
    ]
    lines.extend(preregistered_interpretation(t0, t1, official_metrics))
    lines.extend(
        [
            "",
            "## 全部 Phase 0 矩阵",
            "",
            markdown_table(compact_metrics(metrics)),
            "",
            "## 对照组",
            "",
            "Official continuous baseline：",
            "",
            markdown_table(pd.DataFrame([official_metrics]) if official_metrics else pd.DataFrame()),
            "",
            "PRD_09 满仓等权 paper L3：",
            "",
            markdown_table(compact_prd09_l3(prd09_l3)),
            "",
            "## 输出文件",
            "",
            f"- Metrics: `{cfg.metrics_csv}`",
            f"- Daily series: `{cfg.daily_csv}`",
            f"- Rebalance audit: `{cfg.audit_csv}`",
        ]
    )
    return "\n".join(lines) + "\n"


def preregistered_interpretation(t0: dict[str, Any], t1: dict[str, Any], official: dict[str, Any]) -> list[str]:
    if not t0 or not t1:
        return ["- T0/T1 主结果缺失，无法判读。"]
    lines: list[str] = []
    cagr_diff = metric_diff(t1, t0, "compound_annual_return")
    crunch_diff = metric_diff(t1, t0, "crunch_excess_return_vs_000852")
    if pd.notna(cagr_diff) and pd.notna(crunch_diff) and abs(cagr_diff) < 0.01 and crunch_diff > 0:
        lines.append("- 符合第一条预登记：T1 全周期 CAGR 成本 <1pp 且 crunch 改善，P1 替换语义初步成立。")
    elif pd.notna(cagr_diff) and cagr_diff < -0.02:
        lines.append("- 触发第二条预登记：T1 全周期 CAGR 比 T0 低超过 2pp，P1 替换成本假设需回 owner 重议。")
    else:
        lines.append("- 未完全命中第一/第二条预登记，需结合成本档、walk_depth 和风险指标人工判断。")
    if official:
        t0_dd_gap = t0.get("max_drawdown", np.nan) - official.get("max_drawdown", np.nan)
        t1_dd_gap = t1.get("max_drawdown", np.nan) - official.get("max_drawdown", np.nan)
        if pd.notna(t0_dd_gap) and pd.notna(t1_dd_gap) and t0_dd_gap < -0.15 and t1_dd_gap < -0.15:
            lines.append("- 触发第三条预登记：双臂 MaxDD 均比 official 深超过 15pp，满仓代价超预期，Phase 1/2 前需 owner 复核。")
    max_tail = max(float(t0.get("max_realized_weight", 0.0)), float(t1.get("max_realized_weight", 0.0)))
    if max_tail > 0.40:
        lines.append("- 触发第四条预登记：`max_realized_weight` 尾部超过 40%，需如实交 owner 复核无上限决策。")
    return lines


def row_for(frame: pd.DataFrame, arm: str) -> dict[str, Any]:
    row = frame[frame["arm"] == arm]
    return row.iloc[0].to_dict() if not row.empty else {}


def metric_diff(lhs: dict[str, Any], rhs: dict[str, Any], field: str) -> float:
    if not lhs or not rhs:
        return np.nan
    left = lhs.get(field)
    right = rhs.get(field)
    if pd.isna(left) or pd.isna(right):
        return np.nan
    return float(left) - float(right)


def compact_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    cols = [
        "arm",
        "walk_depth",
        "cost_bps",
        "compound_annual_return",
        "annual_vol",
        "information_ratio_vs_000852",
        "max_drawdown",
        "calmar_ratio",
        "crunch_excess_return_vs_000852",
        "avg_cash_weight",
        "avg_realized_holdings_count",
        "p95_max_realized_weight",
        "max_realized_weight",
        "annual_turnover",
        "p1_skip_count",
    ]
    return frame[[c for c in cols if c in frame.columns]].copy()


def compact_prd09_l3(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    cols = [
        "level",
        "cost_bps",
        "compound_annual_return",
        "annual_vol",
        "information_ratio_vs_000852",
        "max_drawdown",
        "calmar_ratio",
        "crunch_excess_return_vs_000852",
        "avg_gross_exposure",
    ]
    return frame[[c for c in cols if c in frame.columns]].copy()


def print_summary(metrics: pd.DataFrame, official: dict[str, Any]) -> None:
    primary = metrics[(metrics["walk_depth"] == 50) & (metrics["cost_bps"] == 20.0)]
    print("Primary walk_depth=50 cost=20bps:")
    for row in primary.sort_values("arm").to_dict("records"):
        print(
            f"  {row['arm']}: CAGR={fmt_pct(row['compound_annual_return'])}, "
            f"MaxDD={fmt_pct(row['max_drawdown'])}, "
            f"Calmar={fmt_float(row['calmar_ratio'])}, "
            f"crunch excess={fmt_pct(row['crunch_excess_return_vs_000852'])}, "
            f"avg cash={fmt_pct(row['avg_cash_weight'])}, "
            f"avg holdings={fmt_float(row['avg_realized_holdings_count'])}"
        )
    if official:
        print(
            "Official: "
            f"CAGR={fmt_pct(official.get('compound_annual_return'))}, "
            f"MaxDD={fmt_pct(official.get('max_drawdown'))}, "
            f"Calmar={fmt_float(official.get('calmar_ratio'))}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
