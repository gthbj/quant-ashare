#!/usr/bin/env python3
"""Read-only NAV-level study: does a long-only cash / de-risk overlay lift Sharpe,
or is it only a robustness / drawdown (Calmar) layer?

只读探针（不写任何 BigQuery 表 / 不改 ledger / 不 promotion）：

针对研究 baseline NAV 日收益序列，叠加三类 long-only（exposure<=1，现金收益=0，不加杠杆）
overlay：
  1. vol-targeting：exposure = clip(min(1, target_ann_vol / trailing_realized_vol_{t-1}), 0, 1)
     trailing vol 用 lagged 20/60 日年化，严格无前视。
  2. trailing-drawdown de-risk：若 lagged 20 日累计收益 < 阈值则降仓 / 空仓。
  3. market-state de-risk（外生信号，cross-check）：用 dws_market_state_daily 的
     is_smallcap_trend_down / csi1000_drawdown_20d（lagged 1 日）触发降仓 / 空仓。

每个 overlay 报：长窗 + 近窗的 daily Sharpe（mean/std*sqrt(252)）、contract Sharpe
（CAGR/annual_vol）、MaxDD、Calmar、平均 exposure，对比 baseline。先零成本，再按
|delta exposure| * bps 粗扣 overlay 自身换手成本看净 Sharpe。

红线：只读 BigQuery、不写表、不 promotion、不标 accepted、不改默认 CA / tail_risk profile。
"""

from __future__ import annotations

import argparse
import itertools
import math
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from google.cloud import bigquery

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.strategy1_cloudrun.bq_io import make_client, query_dataframe

DEFAULT_PROJECT = "data-aquarium"
DEFAULT_LOCATION = "asia-east2"
DEFAULT_BACKTEST_ID = "bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01"
DEFAULT_START_DATE = "2021-01-04"
DEFAULT_END_DATE = "2026-06-09"
DEFAULT_NEAR_START = "2024-01-02"
DEFAULT_NEAR_END = "2026-04-30"
DEFAULT_MARKET_STATE_VERSION = "market_state_v1_20260607"
DEFAULT_OUTPUT_CSV = "docs/analysis_strategy1_cash_overlay_sharpe_20260613_results.csv"
DEFAULT_REPORT_MD = "docs/分析-策略1空仓降仓overlay对Sharpe贡献-20260613.md"

TRADING_DAYS_PER_YEAR = 252.0

# Anchors confirmed via direct BigQuery aggregation (see task background).
ANCHOR_LONG_DAILY_SHARPE = 0.7369151400001444
ANCHOR_LONG_CONTRACT_SHARPE = 0.668539787795112
ANCHOR_NEAR_DAILY_SHARPE = 1.3370331802474726

# Overlay self-cost grid in bps applied to abs(delta exposure).
# Project cost convention: commission ~1bp, sell stamp 5bps, slippage 5bps/side ->
# a unit |delta exposure| round-trip is roughly 6-11 bps; 10/20 bracket that.
DEFAULT_COST_BPS_GRID = "0,10,20"
DEFAULT_VOL_TARGET_GRID = "0.15,0.20,0.25,0.30"
DEFAULT_VOL_WINDOWS = "20,60"
DEFAULT_DD_LOOKBACK = 20
DEFAULT_DD_THRESHOLDS = "-0.05,-0.10"
DEFAULT_ELOW_GRID = "0.0,0.5"


@dataclass(frozen=True)
class Variant:
    variant_id: str
    family: str  # baseline | vol_target | dd_derisk | market_state
    description: str
    exposure_fn: Callable[[pd.DataFrame], pd.Series]
    cost_bps: float


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project", default=DEFAULT_PROJECT)
    p.add_argument("--location", default=DEFAULT_LOCATION)
    p.add_argument("--backtest-id", default=DEFAULT_BACKTEST_ID)
    p.add_argument("--start-date", default=DEFAULT_START_DATE)
    p.add_argument("--end-date", default=DEFAULT_END_DATE)
    p.add_argument("--near-start", default=DEFAULT_NEAR_START)
    p.add_argument("--near-end", default=DEFAULT_NEAR_END)
    p.add_argument("--market-state-version", default=DEFAULT_MARKET_STATE_VERSION)
    p.add_argument("--vol-target-grid", default=DEFAULT_VOL_TARGET_GRID)
    p.add_argument("--vol-windows", default=DEFAULT_VOL_WINDOWS)
    p.add_argument("--dd-lookback", type=int, default=DEFAULT_DD_LOOKBACK)
    p.add_argument("--dd-thresholds", default=DEFAULT_DD_THRESHOLDS)
    p.add_argument("--elow-grid", default=DEFAULT_ELOW_GRID)
    p.add_argument("--cost-bps-grid", default=DEFAULT_COST_BPS_GRID)
    p.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV)
    p.add_argument("--output-report-md", default=DEFAULT_REPORT_MD)
    p.add_argument("--anchor-tolerance", type=float, default=5e-4)
    p.add_argument("--skip-report", action="store_true")
    return p.parse_args()


def parse_float_grid(raw: str) -> list[float]:
    vals = [float(x.strip()) for x in raw.split(",") if x.strip()]
    if not vals:
        raise ValueError("grid must be non-empty")
    return vals


def parse_int_grid(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


# --------------------------------------------------------------------------- IO


def fetch_nav(client: bigquery.Client, args: argparse.Namespace) -> pd.DataFrame:
    sql = """
    SELECT trade_date, daily_return, benchmark_return, cost_cny, turnover_cny, net_value_cny
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
        labels={"step": "cash_overlay_nav_read", "mode": "readonly"},
    )


def fetch_market_state(client: bigquery.Client, args: argparse.Namespace) -> pd.DataFrame:
    sql = """
    SELECT trade_date, is_smallcap_trend_down, csi1000_drawdown_20d
    FROM `data-aquarium.ashare_dws.dws_market_state_daily`
    WHERE market_state_version = @msv
      AND trade_date BETWEEN @start_date AND @end_date
    ORDER BY trade_date
    """
    return query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("msv", "STRING", args.market_state_version),
            bigquery.ScalarQueryParameter("start_date", "DATE", args.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", args.end_date),
        ],
        labels={"step": "cash_overlay_market_state_read", "mode": "readonly"},
    )


def prepare_frame(nav: pd.DataFrame, market_state: pd.DataFrame) -> pd.DataFrame:
    nav = nav.copy()
    market_state = market_state.copy()
    for f in (nav, market_state):
        f["trade_date"] = pd.to_datetime(f["trade_date"]).dt.date
    if nav["trade_date"].duplicated().any():
        raise RuntimeError("NAV has duplicate trade_date rows")
    if market_state["trade_date"].duplicated().any():
        raise RuntimeError("market_state has duplicate trade_date rows")

    data = nav.merge(market_state, on="trade_date", how="left", validate="one_to_one")
    data = data.sort_values("trade_date").reset_index(drop=True)
    data["daily_return"] = data["daily_return"].astype(float)
    data["benchmark_return"] = data["benchmark_return"].astype(float)

    # Lagged signals (strictly use info up to t-1 to set exposure for day t).
    r = data["daily_return"]
    gross = 1.0 + r

    # trailing realized annualized vol, lagged one day, for each requested window
    for w in (20, 60):
        roll_std = r.rolling(w, min_periods=w).std(ddof=1)
        data[f"lag_vol_ann_{w}"] = roll_std.shift(1) * math.sqrt(TRADING_DAYS_PER_YEAR)

    # trailing cumulative return over lookbacks, lagged one day
    for lb in (20,):
        roll_prod = gross.rolling(lb, min_periods=lb).apply(np.prod, raw=True)
        data[f"lag_cumret_{lb}"] = roll_prod.shift(1) - 1.0

    # exogenous market-state signals, lagged one day
    data["lag_smallcap_down"] = (
        data["is_smallcap_trend_down"].shift(1).astype("boolean").fillna(False).astype(bool)
    )
    data["lag_csi1000_dd_20d"] = data["csi1000_drawdown_20d"].shift(1)
    return data


# ------------------------------------------------------------------ exposures


def exposure_identity(data: pd.DataFrame) -> pd.Series:
    return pd.Series(1.0, index=data.index)


def make_vol_target_exposure(window: int, target_ann_vol: float) -> Callable[[pd.DataFrame], pd.Series]:
    col = f"lag_vol_ann_{window}"

    def fn(data: pd.DataFrame) -> pd.Series:
        lag_vol = data[col]
        raw = target_ann_vol / lag_vol
        exposure = raw.clip(upper=1.0).clip(lower=0.0)
        # warm-up (no vol estimate yet) -> stay fully invested (no fake skill)
        return exposure.fillna(1.0)

    return fn


def make_dd_derisk_exposure(lookback: int, threshold: float, e_low: float) -> Callable[[pd.DataFrame], pd.Series]:
    col = f"lag_cumret_{lookback}"

    def fn(data: pd.DataFrame) -> pd.Series:
        lag_cumret = data[col]
        risk_off = lag_cumret < threshold
        exposure = pd.Series(np.where(risk_off.fillna(False), e_low, 1.0), index=data.index, dtype=float)
        return exposure

    return fn


def make_smallcap_derisk_exposure(e_low: float) -> Callable[[pd.DataFrame], pd.Series]:
    def fn(data: pd.DataFrame) -> pd.Series:
        risk_off = data["lag_smallcap_down"].astype(bool)
        return pd.Series(np.where(risk_off, e_low, 1.0), index=data.index, dtype=float)

    return fn


def make_csi1000_dd_derisk_exposure(threshold: float, e_low: float) -> Callable[[pd.DataFrame], pd.Series]:
    def fn(data: pd.DataFrame) -> pd.Series:
        risk_off = data["lag_csi1000_dd_20d"] < threshold
        return pd.Series(np.where(risk_off.fillna(False), e_low, 1.0), index=data.index, dtype=float)

    return fn


# -------------------------------------------------------------------- metrics


def window_metrics(frame: pd.DataFrame, net_col: str, exposure_col: str) -> dict[str, float]:
    """Metrics over a (already-sliced) window; NAV is rebased to 1.0 at slice start."""
    sub = frame.dropna(subset=[net_col]).copy()
    ret = sub[net_col].astype(float)
    n = int(len(ret))
    if n < 2:
        return {k: math.nan for k in _METRIC_KEYS} | {"return_period_count": n}

    nav = (1.0 + ret).cumprod()
    final_nav = float(nav.iloc[-1])
    total_return = final_nav - 1.0
    cagr = (final_nav ** (TRADING_DAYS_PER_YEAR / n) - 1.0) if final_nav > 0 else math.nan
    mean_d = float(ret.mean())
    std_d = float(ret.std(ddof=1))
    daily_sharpe = mean_d / std_d * math.sqrt(TRADING_DAYS_PER_YEAR) if std_d > 0 else math.nan
    annual_vol = std_d * math.sqrt(TRADING_DAYS_PER_YEAR)
    contract_sharpe = cagr / annual_vol if annual_vol and math.isfinite(cagr) else math.nan

    running_peak = nav.cummax()
    drawdown = nav / running_peak - 1.0
    max_dd = float(drawdown.min())
    calmar = cagr / abs(max_dd) if max_dd < 0 and math.isfinite(cagr) else math.nan

    exposure = sub[exposure_col].astype(float)
    avg_exposure = float(exposure.mean())
    frac_lt1 = float((exposure < 1.0 - 1e-12).mean())
    switches = int((exposure.diff().abs().fillna(0.0) > 1e-12).sum())

    return {
        "total_return": total_return,
        "cagr": cagr,
        "daily_sharpe": daily_sharpe,
        "contract_sharpe": contract_sharpe,
        "annual_vol": annual_vol,
        "max_drawdown": max_dd,
        "calmar": calmar,
        "avg_exposure": avg_exposure,
        "frac_days_exposure_lt1": frac_lt1,
        "exposure_switch_count": switches,
        "return_period_count": n,
    }


_METRIC_KEYS = [
    "total_return",
    "cagr",
    "daily_sharpe",
    "contract_sharpe",
    "annual_vol",
    "max_drawdown",
    "calmar",
    "avg_exposure",
    "frac_days_exposure_lt1",
    "exposure_switch_count",
]


def simulate_variant(
    data: pd.DataFrame,
    variant: Variant,
    near_start: date,
    near_end: date,
) -> dict[str, Any]:
    frame = data.copy()
    exposure = variant.exposure_fn(frame).astype(float)
    delta = exposure.diff().abs().fillna(0.0)
    cost_rate = delta * (variant.cost_bps / 10000.0)
    base = frame["daily_return"].astype(float)
    net = exposure * base - cost_rate
    net[base.isna()] = np.nan
    frame["exposure"] = exposure
    frame["net_return"] = net

    long_m = window_metrics(frame, "net_return", "exposure")

    near = frame[
        (pd.to_datetime(frame["trade_date"]) >= pd.Timestamp(near_start))
        & (pd.to_datetime(frame["trade_date"]) <= pd.Timestamp(near_end))
    ].copy()
    near_m = window_metrics(near, "net_return", "exposure")

    cum_cost_pp = float(cost_rate.sum() * 100.0)

    row: dict[str, Any] = {
        "variant_id": variant.variant_id,
        "family": variant.family,
        "description": variant.description,
        "cost_bps": variant.cost_bps,
        "cumulative_cost_drag_pp": cum_cost_pp,
    }
    for k, v in long_m.items():
        row[f"long_{k}"] = v
    for k, v in near_m.items():
        row[f"near_{k}"] = v
    return row


# ------------------------------------------------------------------- variants


def build_variants(args: argparse.Namespace) -> list[Variant]:
    vol_targets = parse_float_grid(args.vol_target_grid)
    vol_windows = parse_int_grid(args.vol_windows)
    dd_thresholds = parse_float_grid(args.dd_thresholds)
    e_lows = parse_float_grid(args.elow_grid)
    cost_grid = parse_float_grid(args.cost_bps_grid)

    variants: list[Variant] = []
    # baseline appears once per cost level (cost is irrelevant: zero turnover)
    for cost in cost_grid:
        variants.append(
            Variant(
                variant_id=f"baseline_cost{cost:g}bps",
                family="baseline",
                description="exposure==1 全程满仓（恒等基线）",
                exposure_fn=exposure_identity,
                cost_bps=cost,
            )
        )

    for window, target, cost in itertools.product(vol_windows, vol_targets, cost_grid):
        variants.append(
            Variant(
                variant_id=f"voltarget_w{window}_t{target:g}_cost{cost:g}bps",
                family="vol_target",
                description=f"vol-targeting：{window}日lagged年化vol，目标{target:g}，exposure<=1",
                exposure_fn=make_vol_target_exposure(window, target),
                cost_bps=cost,
            )
        )

    for thr, e_low, cost in itertools.product(dd_thresholds, e_lows, cost_grid):
        variants.append(
            Variant(
                variant_id=f"ddderisk_lb{args.dd_lookback}_thr{thr:g}_elow{e_low:g}_cost{cost:g}bps",
                family="dd_derisk",
                description=f"trailing {args.dd_lookback}日累计收益<{thr:g}降仓到{e_low:g}",
                exposure_fn=make_dd_derisk_exposure(args.dd_lookback, thr, e_low),
                cost_bps=cost,
            )
        )

    for e_low, cost in itertools.product(e_lows, cost_grid):
        variants.append(
            Variant(
                variant_id=f"smallcapdown_elow{e_low:g}_cost{cost:g}bps",
                family="market_state",
                description=f"市场状态 is_smallcap_trend_down(lagged) 降仓到{e_low:g}",
                exposure_fn=make_smallcap_derisk_exposure(e_low),
                cost_bps=cost,
            )
        )

    for thr, e_low, cost in itertools.product(dd_thresholds, e_lows, cost_grid):
        variants.append(
            Variant(
                variant_id=f"csi1000dd_thr{thr:g}_elow{e_low:g}_cost{cost:g}bps",
                family="market_state",
                description=f"市场状态 csi1000_drawdown_20d(lagged)<{thr:g} 降仓到{e_low:g}",
                exposure_fn=make_csi1000_dd_derisk_exposure(thr, e_low),
                cost_bps=cost,
            )
        )
    return variants


def validate_anchor(rows: list[dict[str, Any]], tol: float) -> None:
    baseline = next(r for r in rows if r["family"] == "baseline" and r["cost_bps"] == 0)
    checks = {
        "long_daily_sharpe": (baseline["long_daily_sharpe"], ANCHOR_LONG_DAILY_SHARPE),
        "long_contract_sharpe": (baseline["long_contract_sharpe"], ANCHOR_LONG_CONTRACT_SHARPE),
        "near_daily_sharpe": (baseline["near_daily_sharpe"], ANCHOR_NEAR_DAILY_SHARPE),
    }
    for name, (actual, expected) in checks.items():
        if abs(actual - expected) > tol:
            raise RuntimeError(f"anchor check failed: {name} actual={actual} expected={expected}")
    print("Anchor check passed:")
    print(f"  long  daily Sharpe = {baseline['long_daily_sharpe']:.6f} (expect ~{ANCHOR_LONG_DAILY_SHARPE:.6f})")
    print(f"  long  contract Sharpe = {baseline['long_contract_sharpe']:.6f} (expect ~{ANCHOR_LONG_CONTRACT_SHARPE:.6f})")
    print(f"  long  MaxDD = {baseline['long_max_drawdown']:.6f}  Calmar = {baseline['long_calmar']:.6f}")
    print(f"  near  daily Sharpe = {baseline['near_daily_sharpe']:.6f} (expect ~{ANCHOR_NEAR_DAILY_SHARPE:.6f})")
    print(f"  near  contract Sharpe = {baseline['near_contract_sharpe']:.6f}")


# -------------------------------------------------------------------- reporting


def fmt_pct(v: float) -> str:
    return "NA" if v is None or not math.isfinite(float(v)) else f"{float(v) * 100:.2f}%"


def fmt_num(v: float) -> str:
    return "NA" if v is None or not math.isfinite(float(v)) else f"{float(v):.4f}"


def best_zero_cost_by(result: pd.DataFrame, family: str, metric: str) -> pd.Series | None:
    sub = result[(result["family"] == family) & (result["cost_bps"] == 0)].copy()
    if sub.empty:
        return None
    return sub.sort_values(metric, ascending=False).iloc[0]


def print_summary(result: pd.DataFrame) -> None:
    base = result[(result["family"] == "baseline") & (result["cost_bps"] == 0)].iloc[0]
    cols = [
        "variant_id",
        "long_daily_sharpe",
        "long_contract_sharpe",
        "long_max_drawdown",
        "long_calmar",
        "long_avg_exposure",
        "near_daily_sharpe",
        "near_calmar",
    ]
    print("\n=== baseline (zero cost) ===")
    print(
        f"long dailySharpe={fmt_num(base['long_daily_sharpe'])} contractSharpe={fmt_num(base['long_contract_sharpe'])} "
        f"MaxDD={fmt_pct(base['long_max_drawdown'])} Calmar={fmt_num(base['long_calmar'])} | "
        f"near dailySharpe={fmt_num(base['near_daily_sharpe'])} Calmar={fmt_num(base['near_calmar'])}"
    )
    for family in ("vol_target", "dd_derisk", "market_state"):
        print(f"\n=== {family}: zero-cost variants (sorted by long Calmar) ===")
        sub = (
            result[(result["family"] == family) & (result["cost_bps"] == 0)]
            .sort_values("long_calmar", ascending=False)[cols]
        )
        print(
            sub.to_string(
                index=False,
                formatters={
                    "long_daily_sharpe": fmt_num,
                    "long_contract_sharpe": fmt_num,
                    "long_max_drawdown": fmt_pct,
                    "long_calmar": fmt_num,
                    "long_avg_exposure": fmt_num,
                    "near_daily_sharpe": fmt_num,
                    "near_calmar": fmt_num,
                },
            )
        )


REPORT_COLUMNS = [
    "variant_id",
    "family",
    "cost_bps",
    "long_daily_sharpe",
    "long_contract_sharpe",
    "long_cagr",
    "long_annual_vol",
    "long_max_drawdown",
    "long_calmar",
    "long_avg_exposure",
    "long_frac_days_exposure_lt1",
    "long_exposure_switch_count",
    "near_daily_sharpe",
    "near_contract_sharpe",
    "near_cagr",
    "near_max_drawdown",
    "near_calmar",
    "near_avg_exposure",
    "cumulative_cost_drag_pp",
]


def markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    out = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in frame.iterrows():
        out.append("| " + " | ".join(_md_cell(row[c]) for c in columns) + " |")
    return "\n".join(out)


def _md_cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (float, np.floating)):
        return "" if not math.isfinite(float(v)) else f"{float(v):.4f}"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    return str(v).replace("|", "\\|")


def build_report(result: pd.DataFrame, args: argparse.Namespace, output_csv: Path) -> str:
    base = result[(result["family"] == "baseline") & (result["cost_bps"] == 0)].iloc[0]

    def fam_zero(fam: str) -> pd.DataFrame:
        return (
            result[(result["family"] == fam) & (result["cost_bps"] == 0)]
            .sort_values("long_calmar", ascending=False)[REPORT_COLUMNS]
        )

    best_sharpe_overlay = (
        result[(result["family"] != "baseline") & (result["cost_bps"] == 0)]
        .sort_values("long_daily_sharpe", ascending=False)
        .iloc[0]
    )
    best_calmar_overlay = (
        result[(result["family"] != "baseline") & (result["cost_bps"] == 0)]
        .sort_values("long_calmar", ascending=False)
        .iloc[0]
    )

    long_sharpe_gain = best_sharpe_overlay["long_daily_sharpe"] - base["long_daily_sharpe"]
    long_calmar_gain = best_calmar_overlay["long_calmar"] - base["long_calmar"]
    long_dd_improve = best_calmar_overlay["long_max_drawdown"] - base["long_max_drawdown"]

    matrix_md = markdown_table(result[REPORT_COLUMNS])

    return f"""> 文档维护：Claude Opus 4.8（最近更新 2026-06-13）

# 分析：long-only 现金/降仓 overlay 对 Sharpe 的真实贡献（NAV 级只读）

## 问题

确认"适当空仓"（long-only 兼容的现金 / 降仓 overlay）对策略 Sharpe 的真实贡献——
它是 **Sharpe 杠杆**，还是只是 **稳健 / 回撤（Calmar）层**？

## 数据与方法

- Baseline backtest：`{args.backtest_id}`（true-five-year CA-on 研究 baseline，**≠ accepted**）。
- 长窗：`{args.start_date}` 至 `{args.end_date}`；近窗：`{args.near_start}` 至 `{args.near_end}`。
- 收益源：`research_backtest_nav_daily.daily_return`（已含策略自身交易成本）。
- overlay 公式：`r'(t) = e(t) * r(t) - cost(t)`，现金部分收益 = 0，`e(t) ∈ [0, 1]`（不加杠杆）。
- **严格无前视**：所有 exposure 信号都用 lagged（截至 `t-1`）数据。vol-targeting 用
  `exposure = clip(min(1, target_ann_vol / trailing_vol_{{t-1}}), 0, 1)`，trailing vol 为
  20/60 日 lagged 年化样本标准差；trailing-drawdown 用 lagged 20 日累计收益；market-state
  用 `dws_market_state_daily`（`{args.market_state_version}`）的 `is_smallcap_trend_down` /
  `csi1000_drawdown_20d`，均 shift(1)。warm-up（无 vol 估计）期 exposure=1，不注入伪 skill。
- exposure 路径在**完整长窗**上构建（近窗指标用同一路径切片，避免冷启动），近窗 NAV 重置为 1.0。
- 两个 Sharpe 口径并报：**daily Sharpe** = `mean(r)/std(r)*sqrt(252)`（长窗 baseline 锚点 `0.737`）；
  **contract Sharpe** = `CAGR / annual_vol`（长窗 baseline 锚点 `0.6685`，近窗 `~1.46`）。
- overlay 自身换手成本：按 `abs(delta exposure) * cost_bps` 粗扣（grid `{args.cost_bps_grid}` bps），
  零成本先做再看净 Sharpe。10/20 bps 对应项目成本口径（佣金~1bp + 卖出印花 5bps + 滑点 5bps/边）下
  单位 |delta exposure| 的换手成本量级。

## 锚点与恒等校验

- baseline（exposure≡1、零成本）恒等复现：长窗 daily Sharpe `{base['long_daily_sharpe']:.6f}`、
  contract Sharpe `{base['long_contract_sharpe']:.6f}`、MaxDD `{fmt_pct(base['long_max_drawdown'])}`、
  Calmar `{fmt_num(base['long_calmar'])}`；近窗 daily Sharpe `{base['near_daily_sharpe']:.6f}`、
  contract Sharpe `{fmt_num(base['near_contract_sharpe'])}`、Calmar `{fmt_num(base['near_calmar'])}`。
- 与任务给定锚点一致（长窗 `0.737` / `0.6685`，近窗 daily `1.337` / contract `~1.46`）。

## 局限性

NAV 级线性缩放上界估计，**不是真实可交易回测**：忽略 lot 取整、成分股卖出可达性、现金再分配与
选股的交互、冲击成本，以及 exposure 改变对后续持仓结构的反馈。grid 内"最优"变体在同一段历史上
选出，存在 in-sample selection bias，会高估样本外上界。结论只用于回答"机制天花板"的定性问题，
不作为可实现收益、不改默认 profile、不 promotion、不标 accepted。

## 关键读数（零成本）

- baseline 长窗 daily Sharpe = `{fmt_num(base['long_daily_sharpe'])}`，Calmar = `{fmt_num(base['long_calmar'])}`，MaxDD = `{fmt_pct(base['long_max_drawdown'])}`。
- 所有 overlay 中**长窗 daily Sharpe 最高**：`{best_sharpe_overlay['variant_id']}` →
  Sharpe `{fmt_num(best_sharpe_overlay['long_daily_sharpe'])}`（较 baseline {long_sharpe_gain:+.4f}），
  Calmar `{fmt_num(best_sharpe_overlay['long_calmar'])}`，MaxDD `{fmt_pct(best_sharpe_overlay['long_max_drawdown'])}`。
- 所有 overlay 中**长窗 Calmar 最高**：`{best_calmar_overlay['variant_id']}` →
  Calmar `{fmt_num(best_calmar_overlay['long_calmar'])}`（较 baseline {long_calmar_gain:+.4f}），
  MaxDD `{fmt_pct(best_calmar_overlay['long_max_drawdown'])}`（较 baseline 改善 {(-long_dd_improve)*100:+.2f}pp），
  Sharpe `{fmt_num(best_calmar_overlay['long_daily_sharpe'])}`。

## 结论

见正文「给 owner 的结论」一节（由运行后人工依据上表填写定性判断）。

## vol-targeting（零成本）

{markdown_table(fam_zero('vol_target'))}

## trailing-drawdown 降仓（零成本）

{markdown_table(fam_zero('dd_derisk'))}

## market-state 降仓（零成本，外生信号）

{markdown_table(fam_zero('market_state'))}

## 完整结果矩阵（含成本档）

{matrix_md}

- 完整 CSV：`{output_csv.as_posix()}`
"""


def main() -> int:
    args = parse_args()
    client = make_client(args.project, args.location)
    nav = fetch_nav(client, args)
    market_state = fetch_market_state(client, args)
    data = prepare_frame(nav, market_state)

    near_start = pd.Timestamp(args.near_start).date()
    near_end = pd.Timestamp(args.near_end).date()

    variants = build_variants(args)
    rows = [simulate_variant(data, v, near_start, near_end) for v in variants]
    validate_anchor(rows, args.anchor_tolerance)

    result = pd.DataFrame(rows)
    family_order = {"baseline": 0, "vol_target": 1, "dd_derisk": 2, "market_state": 3}
    result["_fam_order"] = result["family"].map(family_order)
    result = result.sort_values(["cost_bps", "_fam_order", "variant_id"]).drop(columns="_fam_order").reset_index(drop=True)

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


if __name__ == "__main__":
    raise SystemExit(main())
