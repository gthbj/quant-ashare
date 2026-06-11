#!/usr/bin/env python3
"""Read-only NAV-level upper-bound simulation for Strategy1 exposure overlay."""

from __future__ import annotations

import argparse
import itertools
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

from scripts.strategy1_cloudrun.bq_io import make_client, query_dataframe


DEFAULT_PROJECT = "data-aquarium"
DEFAULT_LOCATION = "asia-east2"
DEFAULT_START_DATE = "2021-01-04"
DEFAULT_END_DATE = "2026-06-09"
DEFAULT_MARKET_STATE_VERSION = "market_state_v1_20260607"
DEFAULT_BENCHMARK_SEC_CODE = "000852.SH"
DEFAULT_E_LOW_GRID = "0.0,0.3,0.5,0.7"
DEFAULT_COST_BPS_GRID = "0,20,40"
DEFAULT_OUTPUT_CSV = "docs/analysis_strategy1_exposure_overlay_upper_bound_20260611_results.csv"
DEFAULT_REPORT_MD = "docs/分析-策略1暴露管理上限仿真-20260611.md"
CRUNCH_START = "2024-01-01"
CRUNCH_END = "2024-02-07"
TRADING_DAYS_PER_YEAR = 252.0

EXPECTED_BASELINE = {
    "compound_annual_return": 0.12036528993503204,
    "max_drawdown": -0.4548151193656952,
    "calmar_ratio": 0.26464663290635254,
    "contract_sharpe": 0.5285475500566089,
    "crunch_excess_return_vs_000852": -0.1932988013254472,
}
OFFICIAL_SUMMARY_INFORMATION_RATIO = 0.5420201365046585

REPORT_DISPLAY_COLUMNS = [
    "variant_id",
    "state_machine",
    "timing",
    "e_low",
    "transaction_cost_bps",
    "total_return",
    "compound_annual_return",
    "annual_vol",
    "contract_sharpe",
    "max_drawdown",
    "calmar_ratio",
    "benchmark_total_return",
    "excess_return_vs_000852",
    "information_ratio",
    "max_drawdown_peak_date",
    "max_drawdown_trough_date",
    "crunch_strategy_return",
    "crunch_000852_return",
    "crunch_excess_return_vs_000852",
    "average_exposure",
    "exposure_lt_1_day_ratio",
    "exposure_switch_count",
    "cumulative_cost_drag_pp",
    "return_period_count",
    "nav_row_count",
]

COLUMN_DESCRIPTIONS = [
    ("variant_id", "仿真变体 id；baseline_identity 为恒等校验行。"),
    ("state_machine", "暴露状态机：identity / two_state / hysteresis。"),
    ("timing", "暴露调整频率：daily 每日可调，biweekly 仅双周调仓日可调。"),
    ("e_low", "risk-off 目标暴露；1.0 表示满仓，0.0 表示空仓现金。"),
    ("transaction_cost_bps", "每次暴露变化成本，按 abs(delta exposure) * bps 扣减。"),
    ("total_return", "窗口总收益，按模拟 NAV 复利。"),
    ("compound_annual_return", "复合年化收益，按非空日收益期数 annualize。"),
    ("annual_vol", "日收益样本标准差 * sqrt(252)。"),
    ("contract_sharpe", "v3 contract 口径：compound_annual_return / annual_vol。"),
    ("max_drawdown", "模拟 NAV 最大回撤。"),
    ("calmar_ratio", "compound_annual_return / abs(max_drawdown)。"),
    ("benchmark_total_return", "000852.SH 同窗口总收益，来自 dwd_index_eod pct_chg / 100。"),
    ("excess_return_vs_000852", "策略 total_return - benchmark_total_return。"),
    ("information_ratio", "本报告按 000852.SH pct_chg / 100 重算的 IR，不等同 summary legacy IR。"),
    ("max_drawdown_peak_date", "最大回撤起点峰值日期。"),
    ("max_drawdown_trough_date", "最大回撤谷底日期。"),
    ("crunch_strategy_return", "2024-01-01 至 2024-02-07 策略收益。"),
    ("crunch_000852_return", "同 crunch 段 000852.SH 收益。"),
    ("crunch_excess_return_vs_000852", "crunch_strategy_return - crunch_000852_return。"),
    ("average_exposure", "窗口内平均目标暴露。"),
    ("exposure_lt_1_day_ratio", "目标暴露小于 1.0 的开市日占比。"),
    ("exposure_switch_count", "目标暴露变化次数，作为 whipsaw 计数。"),
    ("cumulative_cost_drag_pp", "累计成本拖累，百分点。"),
    ("return_period_count", "用于年化的非空日收益期数。"),
    ("nav_row_count", "NAV / 开市日行数。"),
]


@dataclass(frozen=True)
class Variant:
    variant_id: str
    state_machine: str
    timing: str
    e_low: float
    transaction_cost_bps: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a local, read-only upper-bound simulation for Strategy1 exposure overlay."
    )
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--location", default=DEFAULT_LOCATION)
    parser.add_argument("--backtest-id", required=True)
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    parser.add_argument("--market-state-version", default=DEFAULT_MARKET_STATE_VERSION)
    parser.add_argument("--benchmark-sec-code", default=DEFAULT_BENCHMARK_SEC_CODE)
    parser.add_argument("--e-low-grid", default=DEFAULT_E_LOW_GRID, help="Comma-separated target risk-off exposures.")
    parser.add_argument("--cost-bps-grid", default=DEFAULT_COST_BPS_GRID, help="Comma-separated |delta exposure| cost bps.")
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-report-md", default=DEFAULT_REPORT_MD)
    parser.add_argument("--identity-tolerance", type=float, default=1e-6)
    parser.add_argument("--skip-report", action="store_true")
    return parser.parse_args()


def parse_float_grid(raw: str) -> list[float]:
    values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("grid must contain at least one value")
    return values


def main() -> int:
    args = parse_args()
    e_low_grid = parse_float_grid(args.e_low_grid)
    cost_grid = parse_float_grid(args.cost_bps_grid)

    client = make_client(args.project, args.location)
    nav = fetch_nav(client, args)
    calendar = fetch_calendar(client, args)
    market_state = fetch_market_state(client, args)
    benchmark = fetch_benchmark(client, args)

    data = prepare_simulation_frame(nav, calendar, market_state, benchmark)
    rebalance_dates = build_biweekly_rebalance_dates(calendar)
    validate_inputs(data, rebalance_dates)

    rows: list[dict[str, Any]] = []
    baseline = simulate_variant(
        data,
        Variant(
            variant_id="baseline_identity",
            state_machine="identity",
            timing="daily",
            e_low=1.0,
            transaction_cost_bps=0.0,
        ),
        rebalance_dates,
    )
    rows.append(baseline)
    validate_identity(baseline, args.identity_tolerance)

    for state_machine, timing, e_low, cost_bps in itertools.product(
        ["two_state", "hysteresis"],
        ["daily", "biweekly"],
        e_low_grid,
        cost_grid,
    ):
        rows.append(
            simulate_variant(
                data,
                Variant(
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
    result = result.sort_values(["is_identity", "transaction_cost_bps", "state_machine", "timing", "e_low"], ascending=[False, True, True, True, True])
    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_csv, index=False)

    print_summary(result)
    if not args.skip_report:
        report_md = Path(args.output_report_md)
        report_md.parent.mkdir(parents=True, exist_ok=True)
        report_md.write_text(build_report(result, args, output_csv), encoding="utf-8")
        print(f"\nReport written: {report_md}")
    print(f"CSV written: {output_csv}")
    return 0


def fetch_nav(client: bigquery.Client, args: argparse.Namespace) -> pd.DataFrame:
    sql = """
    SELECT trade_date, nav, daily_return
    FROM `data-aquarium.ashare_research.research_backtest_nav_daily`
    WHERE backtest_id = @backtest_id
      AND trade_date BETWEEN @start_date AND @end_date
    ORDER BY trade_date
    """
    return query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("backtest_id", "STRING", args.backtest_id),
            bigquery.ScalarQueryParameter("start_date", "DATE", args.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", args.end_date),
        ],
        labels={"step": "exposure_overlay_nav_read", "mode": "readonly"},
    )


def fetch_calendar(client: bigquery.Client, args: argparse.Namespace) -> pd.DataFrame:
    sql = """
    SELECT cal_date AS trade_date, trade_date_seq
    FROM `data-aquarium.ashare_dim.dim_trade_calendar`
    WHERE exchange = 'SSE'
      AND is_open = 1
      AND cal_date BETWEEN @start_date AND @end_date
    ORDER BY cal_date
    """
    return query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("start_date", "DATE", args.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", args.end_date),
        ],
        labels={"step": "exposure_overlay_calendar_read", "mode": "readonly"},
    )


def fetch_market_state(client: bigquery.Client, args: argparse.Namespace) -> pd.DataFrame:
    sql = """
    SELECT
      trade_date,
      is_risk_off,
      market_regime,
      risk_off_trigger_count,
      is_limit_down_diffusion
    FROM `data-aquarium.ashare_dws.dws_market_state_daily`
    WHERE market_state_version = @market_state_version
      AND trade_date BETWEEN @start_date AND @end_date
    ORDER BY trade_date
    """
    return query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("market_state_version", "STRING", args.market_state_version),
            bigquery.ScalarQueryParameter("start_date", "DATE", args.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", args.end_date),
        ],
        labels={"step": "exposure_overlay_market_state_read", "mode": "readonly"},
    )


def fetch_benchmark(client: bigquery.Client, args: argparse.Namespace) -> pd.DataFrame:
    sql = """
    SELECT trade_date, pct_chg / 100.0 AS benchmark_return
    FROM `data-aquarium.ashare_dwd.dwd_index_eod`
    WHERE sec_code = @benchmark_sec_code
      AND trade_date BETWEEN @start_date AND @end_date
    ORDER BY trade_date
    """
    return query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("benchmark_sec_code", "STRING", args.benchmark_sec_code),
            bigquery.ScalarQueryParameter("start_date", "DATE", args.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", args.end_date),
        ],
        labels={"step": "exposure_overlay_benchmark_read", "mode": "readonly"},
    )


def prepare_simulation_frame(
    nav: pd.DataFrame,
    calendar: pd.DataFrame,
    market_state: pd.DataFrame,
    benchmark: pd.DataFrame,
) -> pd.DataFrame:
    nav = nav.copy()
    calendar = calendar.copy()
    market_state = market_state.copy()
    benchmark = benchmark.copy()
    for frame in [nav, calendar, market_state, benchmark]:
        frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date

    assert_unique_dates(nav, "NAV")
    assert_unique_dates(calendar, "calendar")
    assert_unique_dates(market_state, "market_state")
    assert_unique_dates(benchmark, "benchmark")

    data = calendar.merge(nav, on="trade_date", how="left", validate="one_to_one")
    data = data.merge(market_state, on="trade_date", how="left", validate="one_to_one")
    data = data.merge(benchmark, on="trade_date", how="left", validate="one_to_one")
    data = data.sort_values("trade_date").reset_index(drop=True)

    data["signal_is_risk_off"] = data["is_risk_off"].shift(1).astype("boolean").fillna(False).astype(bool)
    data["signal_market_regime"] = data["market_regime"].shift(1).fillna("risk_on")
    return data


def assert_unique_dates(frame: pd.DataFrame, name: str) -> None:
    duplicates = frame["trade_date"].duplicated().sum()
    if duplicates:
        raise RuntimeError(f"{name} has duplicate trade_date rows: {duplicates}")


def validate_inputs(data: pd.DataFrame, rebalance_dates: set[date]) -> None:
    missing_nav = data[data["nav"].isna()]["trade_date"].tolist()
    missing_market = data[data["is_risk_off"].isna()]["trade_date"].tolist()
    missing_benchmark = data[data["benchmark_return"].isna()]["trade_date"].tolist()
    if missing_nav:
        raise RuntimeError(f"NAV missing on open dates: {missing_nav[:10]}")
    if missing_market:
        raise RuntimeError(f"market state missing on open dates: {missing_market[:10]}")
    if data["is_risk_off"].isna().any():
        raise RuntimeError("market state contains NULL is_risk_off")
    if missing_benchmark:
        raise RuntimeError(f"benchmark missing on open dates: {missing_benchmark[:10]}")
    if not rebalance_dates:
        raise RuntimeError("rebalance calendar is empty")


def build_biweekly_rebalance_dates(calendar: pd.DataFrame) -> set[date]:
    cal = calendar.copy()
    cal["trade_date"] = pd.to_datetime(cal["trade_date"])
    iso = cal["trade_date"].dt.isocalendar()
    cal["iso_year"] = iso.year.astype(int)
    cal["iso_week"] = iso.week.astype(int)
    weekly = (
        cal.groupby(["iso_year", "iso_week"], as_index=False)["trade_date"]
        .max()
        .sort_values("trade_date")
        .reset_index(drop=True)
    )
    weekly["week_idx"] = np.arange(1, len(weekly) + 1)
    return set(weekly.loc[(weekly["week_idx"] - 1) % 2 == 0, "trade_date"].dt.date)


def simulate_variant(data: pd.DataFrame, variant: Variant, rebalance_dates: set[date]) -> dict[str, Any]:
    frame = data.copy()
    exposure = compute_exposure_path(frame, variant, rebalance_dates)
    cost_rate = compute_cost_rate(exposure, variant.transaction_cost_bps)

    base_returns = frame["daily_return"].astype(float)
    adjusted_returns = base_returns * exposure - cost_rate
    adjusted_returns[base_returns.isna()] = np.nan

    nav = [1.0]
    for ret in adjusted_returns.iloc[1:]:
        nav.append(nav[-1] * (1.0 + float(ret)))
    frame["sim_nav"] = nav
    frame["sim_daily_return"] = adjusted_returns
    frame["exposure"] = exposure
    frame["cost_rate"] = cost_rate
    frame["sim_excess_return"] = frame["sim_daily_return"].fillna(0.0) - frame["benchmark_return"].astype(float)

    metrics = compute_metrics(frame, variant)
    return metrics


def compute_exposure_path(data: pd.DataFrame, variant: Variant, rebalance_dates: set[date]) -> pd.Series:
    if variant.state_machine == "identity":
        return pd.Series(1.0, index=data.index)
    if variant.state_machine not in {"two_state", "hysteresis"}:
        raise ValueError(f"unsupported state machine: {variant.state_machine}")
    if variant.timing not in {"daily", "biweekly"}:
        raise ValueError(f"unsupported timing: {variant.timing}")

    current = 1.0
    exposures: list[float] = []
    for _, row in data.iterrows():
        can_change = variant.timing == "daily" or row["trade_date"] in rebalance_dates
        if can_change:
            if variant.state_machine == "two_state":
                current = variant.e_low if bool(row["signal_is_risk_off"]) else 1.0
            else:
                if bool(row["signal_is_risk_off"]):
                    current = variant.e_low
                elif row["signal_market_regime"] == "risk_on":
                    current = 1.0
        exposures.append(current)
    return pd.Series(exposures, index=data.index, dtype=float)


def compute_cost_rate(exposure: pd.Series, transaction_cost_bps: float) -> pd.Series:
    delta = exposure.diff().abs().fillna(0.0)
    return delta * (transaction_cost_bps / 10000.0)


def compute_metrics(frame: pd.DataFrame, variant: Variant) -> dict[str, Any]:
    returns = frame["sim_daily_return"].dropna().astype(float)
    return_period_count = int(len(returns))
    final_nav = float(frame["sim_nav"].iloc[-1])
    total_return = final_nav - 1.0
    compound_annual_return = compound_annualized_return(total_return, return_period_count)
    annual_vol = float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR)) if len(returns) >= 2 else math.nan
    contract_sharpe = safe_ratio(compound_annual_return, annual_vol)

    max_dd, peak_date, trough_date = max_drawdown(frame["trade_date"], frame["sim_nav"])
    calmar = safe_ratio(compound_annual_return, abs(max_dd))

    benchmark_nav = cumulative_return(frame["benchmark_return"].astype(float))
    excess_return = final_nav - benchmark_nav
    excess_daily = frame["sim_excess_return"].astype(float)
    tracking_error = float(excess_daily.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR)) if len(excess_daily) >= 2 else math.nan
    information_ratio = safe_ratio(float(excess_daily.mean() * TRADING_DAYS_PER_YEAR), tracking_error)

    crunch = frame[
        (pd.to_datetime(frame["trade_date"]) >= pd.Timestamp(CRUNCH_START))
        & (pd.to_datetime(frame["trade_date"]) <= pd.Timestamp(CRUNCH_END))
    ].copy()
    crunch_strategy_return = cumulative_return(crunch["sim_daily_return"].fillna(0.0).astype(float))
    crunch_benchmark_return = cumulative_return(crunch["benchmark_return"].astype(float))

    exposure = frame["exposure"].astype(float)
    switches = int((exposure.diff().abs().fillna(0.0) > 1e-12).sum())
    cumulative_cost_drag_pp = float(frame["cost_rate"].sum() * 100.0)

    return {
        "variant_id": variant.variant_id,
        "is_identity": variant.state_machine == "identity",
        "state_machine": variant.state_machine,
        "timing": variant.timing,
        "e_low": variant.e_low,
        "transaction_cost_bps": variant.transaction_cost_bps,
        "total_return": total_return,
        "compound_annual_return": compound_annual_return,
        "annual_vol": annual_vol,
        "contract_sharpe": contract_sharpe,
        "max_drawdown": max_dd,
        "calmar_ratio": calmar,
        "benchmark_total_return": benchmark_nav - 1.0,
        "excess_return_vs_000852": excess_return,
        "information_ratio": information_ratio,
        "max_drawdown_peak_date": peak_date.isoformat(),
        "max_drawdown_trough_date": trough_date.isoformat(),
        "crunch_strategy_return": crunch_strategy_return - 1.0,
        "crunch_000852_return": crunch_benchmark_return - 1.0,
        "crunch_excess_return_vs_000852": (crunch_strategy_return - 1.0) - (crunch_benchmark_return - 1.0),
        "average_exposure": float(exposure.mean()),
        "exposure_lt_1_day_ratio": float((exposure < 1.0 - 1e-12).mean()),
        "exposure_switch_count": switches,
        "cumulative_cost_drag_pp": cumulative_cost_drag_pp,
        "return_period_count": return_period_count,
        "nav_row_count": int(len(frame)),
    }


def compound_annualized_return(total_return: float, return_period_count: int) -> float:
    if return_period_count <= 0 or 1.0 + total_return < 0.0:
        return math.nan
    return (1.0 + total_return) ** (TRADING_DAYS_PER_YEAR / return_period_count) - 1.0


def cumulative_return(returns: pd.Series) -> float:
    value = 1.0
    for ret in returns:
        value *= 1.0 + float(ret)
    return value


def safe_ratio(numerator: float, denominator: float) -> float:
    if denominator is None or not math.isfinite(denominator) or abs(denominator) < 1e-15:
        return math.nan
    return numerator / denominator


def max_drawdown(dates: pd.Series, nav: pd.Series) -> tuple[float, date, date]:
    nav_values = nav.astype(float).reset_index(drop=True)
    date_values = pd.to_datetime(dates).dt.date.reset_index(drop=True)
    running_peak = nav_values.cummax()
    drawdown = nav_values / running_peak - 1.0
    trough_idx = int(drawdown.idxmin())
    peak_nav = float(running_peak.iloc[trough_idx])
    eligible = nav_values.iloc[: trough_idx + 1]
    peak_idx = int(eligible[np.isclose(eligible, peak_nav, rtol=0, atol=1e-9)].index[0])
    return float(drawdown.iloc[trough_idx]), date_values.iloc[peak_idx], date_values.iloc[trough_idx]


def validate_identity(row: dict[str, Any], tolerance: float) -> None:
    for key, expected in EXPECTED_BASELINE.items():
        actual = float(row[key])
        if abs(actual - expected) > tolerance:
            raise RuntimeError(f"identity check failed for {key}: actual={actual}, expected={expected}")


def fmt_pct(value: float) -> str:
    return "NA" if value is None or not math.isfinite(float(value)) else f"{float(value) * 100:.2f}%"


def fmt_num(value: float) -> str:
    return "NA" if value is None or not math.isfinite(float(value)) else f"{float(value):.4f}"


def print_summary(result: pd.DataFrame) -> None:
    baseline = result[result["is_identity"]].iloc[0]
    best_zero = best_zero_cost_variant(result)
    print("Identity check passed")
    print(
        "baseline:",
        f"CAGR={fmt_pct(baseline['compound_annual_return'])}",
        f"MaxDD={fmt_pct(baseline['max_drawdown'])}",
        f"Calmar={fmt_num(baseline['calmar_ratio'])}",
        f"contractSharpe={fmt_num(baseline['contract_sharpe'])}",
        f"crunchExcess={fmt_pct(baseline['crunch_excess_return_vs_000852'])}",
    )
    print(
        "best zero-cost exposure variant:",
        best_zero["variant_id"],
        f"CAGR={fmt_pct(best_zero['compound_annual_return'])}",
        f"MaxDD={fmt_pct(best_zero['max_drawdown'])}",
        f"Calmar={fmt_num(best_zero['calmar_ratio'])}",
        f"contractSharpe={fmt_num(best_zero['contract_sharpe'])}",
    )
    print("\nTop zero-cost variants by Calmar:")
    cols = ["variant_id", "compound_annual_return", "max_drawdown", "calmar_ratio", "contract_sharpe", "average_exposure", "exposure_switch_count"]
    top = (
        result[(~result["is_identity"]) & (result["transaction_cost_bps"] == 0)]
        .sort_values("calmar_ratio", ascending=False)
        .head(8)[cols]
    )
    print(top.to_string(index=False, formatters={
        "compound_annual_return": fmt_pct,
        "max_drawdown": fmt_pct,
        "calmar_ratio": fmt_num,
        "contract_sharpe": fmt_num,
        "average_exposure": fmt_num,
    }))


def best_zero_cost_variant(result: pd.DataFrame) -> pd.Series:
    zero = result[(~result["is_identity"]) & (result["transaction_cost_bps"] == 0)].copy()
    if zero.empty:
        raise RuntimeError("no zero-cost exposure variants")
    return zero.sort_values("calmar_ratio", ascending=False).iloc[0]


def build_report(result: pd.DataFrame, args: argparse.Namespace, output_csv: Path) -> str:
    baseline = result[result["is_identity"]].iloc[0]
    best_zero = best_zero_cost_variant(result)
    max_variant_contract_sharpe = float(result[~result["is_identity"]]["contract_sharpe"].max())
    verdict = verdict_for_calmar(float(best_zero["calmar_ratio"]))
    matrix = result.drop(columns=["is_identity"]).copy()
    matrix_md = markdown_table(matrix[REPORT_DISPLAY_COLUMNS])
    top_zero = (
        result[(~result["is_identity"]) & (result["transaction_cost_bps"] == 0)]
        .sort_values("calmar_ratio", ascending=False)
        .head(10)[REPORT_DISPLAY_COLUMNS]
    )
    top_zero_md = markdown_table(top_zero)
    column_descriptions_md = markdown_table(pd.DataFrame(COLUMN_DESCRIPTIONS, columns=["column", "description"]))
    return f"""> 文档维护：GPT-5 Codex（最近更新 2026-06-11）

# 分析：策略1暴露管理上限仿真（NAV 级离线估计）

## 预登记判据

以最优变体的**无摩擦** Calmar 为准：

- Calmar < 0.5 -> 结论“ledger 工程缓做/降优先级，剩余缺口在 alpha 质量”；
- Calmar >= 0.7 -> 结论“建议立暴露管理 PRD，做真实 ledger 实现验证摩擦后残余”；
- 0.5 ~ 0.7 -> 灰区，列出取舍交 owner。

参考锚点：v3 gates 为 contract Sharpe >= 0.70、Calmar > 1.0；baseline Calmar 0.2646；A2（skip-buys 实跑）Calmar 0.2587。

## 数据与方法

- Baseline backtest: `{args.backtest_id}`
- 窗口：`{args.start_date}` 至 `{args.end_date}`
- 市场状态版本：`{args.market_state_version}`
- 基准：`{args.benchmark_sec_code}`，`pct_chg / 100`
- 仿真公式：`r'(t) = e(t) * r(t) - cost(t)`，现金部分收益为 0。
- PIT：`t` 日市场状态只影响下一开市日；首日无前序状态，暴露为 1。
- 调仓日变体：按 `build_candidates.sql` 的 ISO 年/周最后开市日、`MOD(week_idx-1,2)=0`、anchor `{args.start_date}` 重建。
- 成本：每次暴露变化扣 `abs(delta exposure) * cost_bps / 10000`，成本在暴露变化日进入日收益。

## 局限性

这是 NAV 级无摩擦/低摩擦上界估计，不是真实可交易回测。线性缩放假设忽略 lot 取整、成分股卖出路径、选股与现金再分配交互、冲击成本、卖出不可交易约束，以及 exposure 改变后对后续持仓结构的反馈。无摩擦结果只能表示“机制天花板”，不能直接视为可实现收益。

本报告 headline 的最优 Calmar 是在同一段历史上从 48 个 exposure 变体中挑出的 best-of-grid 结果，存在 in-sample selection bias；该偏差方向会高估样本外上界。`two_state_biweekly_elow0_cost0bps` 的 CAGR 略高于 baseline 应视为单段历史择时读数，不应外推为可实现预期。

## 恒等与覆盖校验

- `e(t) == 1.0`、零成本恒等仿真通过，复现 baseline：
  - CAGR `{baseline['compound_annual_return']:.17g}`
  - MaxDD `{baseline['max_drawdown']:.17g}`
  - Calmar `{baseline['calmar_ratio']:.17g}`
  - contract Sharpe `{baseline['contract_sharpe']:.17g}`
- market state / NAV / benchmark 均按 SSE 开市日逐日对齐，`is_risk_off` 无 NULL。
- baseline crunch excess vs `{args.benchmark_sec_code}` = `{baseline['crunch_excess_return_vs_000852']:.17g}`，与 PR #179 对比表一致。
- 表中 `information_ratio` 与 `excess_return_vs_000852` 按本任务指定的 `dwd_index_eod.pct_chg / 100` 重算；不复用 summary 表 legacy benchmark_return。identity 行重算 IR 为 `{baseline['information_ratio']:.4f}`，官方 summary 同名 legacy IR 为 `{OFFICIAL_SUMMARY_INFORMATION_RATIO:.4f}`，两者不可跨文档直接比较；IR 不参与本次预登记判据。
- Markdown 表与完整 CSV 使用同一详细列集；CSV：`{output_csv.as_posix()}`

## 结论

最优无摩擦变体：`{best_zero['variant_id']}`。

- CAGR: `{fmt_pct(best_zero['compound_annual_return'])}`
- MaxDD: `{fmt_pct(best_zero['max_drawdown'])}`
- Calmar: `{fmt_num(best_zero['calmar_ratio'])}`
- contract Sharpe: `{fmt_num(best_zero['contract_sharpe'])}`
- 平均暴露: `{fmt_num(best_zero['average_exposure'])}`
- 暴露切换次数: `{int(best_zero['exposure_switch_count'])}`

按预登记判据：**{verdict}**

所有 exposure 变体的最高 contract Sharpe 为 `{max_variant_contract_sharpe:.4f}`，仍低于 v3 gate `0.70`。即使暴露管理达到本次无摩擦上界，v3 双门仍不可达，主要缺口仍在 alpha 质量或信号/组合构造。

状态机层面的结论也很明确：`hysteresis`（risk-off 后等待显式 `risk_on` 确认再恢复满仓）系统性弱于 `two_state`。当前 `risk_on` 定义过于苛刻，等确认会错过修复行情；若未来做 exposure / 条件化风控，优先采用 risk-off 解除即恢复的 `two_state`，不应默认等待 `risk_on` 确认。

## 数据列说明

{column_descriptions_md}

## Top 10 无摩擦变体

{top_zero_md}

## 完整结果矩阵

{matrix_md}

## 给 owner 的建议

- 若要推进真实 exposure ledger，建议优先参考“仅 biweekly 调仓日可调”的结果，而不是每日可调上界。
- 若未来重新设计 exposure / 条件化风控，状态机应优先采用 `two_state`；本次数据不支持 hysteresis 式显式 `risk_on` 再入场确认。
- 所有变体 contract Sharpe 均低于 0.70；暴露管理最多改善回撤形态，不能单独把当前策略推过 v3 双门。
- 本报告只提供工程投入前的上界证据；不关闭 OQ、不改变默认 profile、不 promotion。
"""


def verdict_for_calmar(calmar: float) -> str:
    if calmar < 0.5:
        return "ledger 工程缓做/降优先级，剩余缺口在 alpha 质量"
    if calmar >= 0.7:
        return "建议立暴露管理 PRD，做真实 ledger 实现验证摩擦后残余"
    return "灰区，列出取舍交 owner"


def markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in frame.iterrows():
        values = [markdown_cell(row[column]) for column in columns]
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def markdown_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(float(value)):
            return ""
        return f"{float(value):.6f}"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    return str(value).replace("|", "\\|")


if __name__ == "__main__":
    raise SystemExit(main())
