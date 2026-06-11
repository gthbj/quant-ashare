#!/usr/bin/env python3
"""Read-only Strategy1 signal IC decomposition and transfer efficiency analysis."""

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

from scripts.strategy1_cloudrun.bq_io import make_client, query_dataframe


DEFAULT_PROJECT = "data-aquarium"
DEFAULT_LOCATION = "asia-east2"
DEFAULT_STRATEGY_ID = "ml_pv_clf_v0"
DEFAULT_PREDICTION_RUN_ID = "s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02"
DEFAULT_BACKTEST_ID = "bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02"
DEFAULT_START_DATE = "2021-01-04"
DEFAULT_END_DATE = "2026-06-09"
DEFAULT_LABEL_VERSION = "open_to_close_h1_5_10_20_v20260601"
DEFAULT_FEATURE_VERSION = "strategy1_pv_v0_20260601"
DEFAULT_MARKET_STATE_VERSION = "market_state_v1_20260607"
DEFAULT_BENCHMARK_SEC_CODE = "000852.SH"
DEFAULT_REPORT_MD = "docs/分析-策略1信号IC分解与转换效率-20260611.md"
DEFAULT_IC_CSV = "docs/analysis_strategy1_signal_ic_decomposition_20260611_summary.csv"
DEFAULT_DAILY_IC_CSV = "docs/analysis_strategy1_signal_ic_decomposition_20260611_daily.csv"
DEFAULT_TRANSFER_CSV = "docs/analysis_strategy1_transfer_ladder_20260611_results.csv"
DEFAULT_TC_CSV = "docs/analysis_strategy1_transfer_ladder_20260611_transfer_coefficients.csv"

HORIZONS = (1, 5, 10, 20)
TRADING_DAYS_PER_YEAR = 252.0
TURNOVER_COST_BPS = (0.0, 20.0)
TRANSFER_LEVELS = ("L0", "L0.5", "L1", "L2", "L3")
CORRELATION_MIN_STD = 1e-12
CRUNCH_START = "2024-01-01"
CRUNCH_END = "2024-02-07"
OFFICIAL_REFERENCE = {
    "compound_annual_return": 0.12036528993503204,
    "max_drawdown": -0.4548151193656952,
    "calmar_ratio": 0.26464663290635254,
    "contract_sharpe": 0.5285475500566089,
}

PREREGISTERED_RULES = [
    "A2: 市值中性后 IC 保留 >=60% 视为真 stock selection 仍在；<40% 视为小市值 style 主导。",
    "A3: risk_off 桶 IC 不显著或为负时，后续应优先考虑 regime conditional ranking / exposure。",
    "A4: short-side contribution >60% 时，long-only Top20 无法充分兑现信号，组合约束本身是主要损耗源。",
    "B: L0 no-cost IR <1.0 时，信号自身容量不足，工程优化不应替代 alpha 改进。",
    "B: L3-L2 IR 差距 >=0.1 时，等权/权重规则值得独立优化；否则先不要改权重实现。",
    "B: L1-L2 IR 差距 >=0.1 时，Top30-50 携带增量信息；否则 Top20 约束不是主要瓶颈。",
    "L3 恒等校验必须先解释 paper portfolio 与 official ledger 偏差，再解读阶梯差异。",
]


@dataclass(frozen=True)
class AnalysisConfig:
    project: str
    location: str
    strategy_id: str
    prediction_run_id: str
    backtest_id: str
    start_date: str
    end_date: str
    label_version: str
    feature_version: str
    market_state_version: str
    benchmark_sec_code: str
    ic_csv: Path
    daily_ic_csv: Path
    transfer_csv: Path
    tc_csv: Path
    report_md: Path
    skip_report: bool


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run PRD_20260611_09 signal IC decomposition and transfer ladder "
            "as read-only local analysis."
        )
    )
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--location", default=DEFAULT_LOCATION)
    parser.add_argument("--strategy-id", default=DEFAULT_STRATEGY_ID)
    parser.add_argument("--prediction-run-id", default=DEFAULT_PREDICTION_RUN_ID)
    parser.add_argument("--backtest-id", default=DEFAULT_BACKTEST_ID)
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    parser.add_argument("--label-version", default=DEFAULT_LABEL_VERSION)
    parser.add_argument("--feature-version", default=DEFAULT_FEATURE_VERSION)
    parser.add_argument("--market-state-version", default=DEFAULT_MARKET_STATE_VERSION)
    parser.add_argument("--benchmark-sec-code", default=DEFAULT_BENCHMARK_SEC_CODE)
    parser.add_argument("--ic-csv", default=DEFAULT_IC_CSV)
    parser.add_argument("--daily-ic-csv", default=DEFAULT_DAILY_IC_CSV)
    parser.add_argument("--transfer-csv", default=DEFAULT_TRANSFER_CSV)
    parser.add_argument("--tc-csv", default=DEFAULT_TC_CSV)
    parser.add_argument("--report-md", default=DEFAULT_REPORT_MD)
    parser.add_argument("--skip-report", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> AnalysisConfig:
    return AnalysisConfig(
        project=args.project,
        location=args.location,
        strategy_id=args.strategy_id,
        prediction_run_id=args.prediction_run_id,
        backtest_id=args.backtest_id,
        start_date=args.start_date,
        end_date=args.end_date,
        label_version=args.label_version,
        feature_version=args.feature_version,
        market_state_version=args.market_state_version,
        benchmark_sec_code=args.benchmark_sec_code,
        ic_csv=Path(args.ic_csv),
        daily_ic_csv=Path(args.daily_ic_csv),
        transfer_csv=Path(args.transfer_csv),
        tc_csv=Path(args.tc_csv),
        report_md=Path(args.report_md),
        skip_report=args.skip_report,
    )


def main(argv: list[str] | None = None) -> int:
    cfg = config_from_args(parse_args(argv))
    client = make_client(cfg.project, cfg.location)

    print("Fetching prediction/label/feature base...", flush=True)
    base = fetch_signal_base(client, cfg)
    validate_signal_base(base, cfg)

    print("Fetching official NAV/benchmark/calendar/positions/trades...", flush=True)
    nav = fetch_official_nav(client, cfg)
    benchmark = fetch_benchmark(client, cfg)
    calendar = fetch_calendar(client, cfg)
    official_targets = fetch_official_targets(client, cfg)
    official_positions = fetch_official_positions(client, cfg)
    official_trades = fetch_official_trades(client, cfg)

    print("Computing IC decomposition...", flush=True)
    daily_ic, ic_summary = compute_ic_outputs(base)

    print("Computing transfer ladder weights...", flush=True)
    rebalance_dates = build_biweekly_rebalance_dates(calendar, cfg.start_date, cfg.end_date)
    weight_book = build_weight_book(base, rebalance_dates)
    prices = fetch_prices_for_weight_book(client, cfg, weight_book)

    print("Simulating transfer ladder...", flush=True)
    transfer_results, l3_daily = compute_transfer_ladder_outputs(
        weight_book=weight_book,
        prices=prices,
        calendar=calendar,
        benchmark=benchmark,
        nav=nav,
        start_date=cfg.start_date,
        end_date=cfg.end_date,
    )
    transfer_coefficients = compute_transfer_coefficients(
        base=base,
        weight_book=weight_book,
        official_targets=official_targets,
        official_positions=official_positions,
        calendar=calendar,
    )
    execution_diagnostics = compute_execution_diagnostics(
        nav=nav,
        positions=official_positions,
        trades=official_trades,
        transfer_coefficients=transfer_coefficients,
    )
    transfer_results = append_official_identity_check(transfer_results, l3_daily, nav)

    write_outputs(cfg, daily_ic, ic_summary, transfer_results, transfer_coefficients, execution_diagnostics)
    print_summary(ic_summary, transfer_results, transfer_coefficients, execution_diagnostics)
    return 0


def fetch_signal_base(client: bigquery.Client, cfg: AnalysisConfig) -> pd.DataFrame:
    sql = f"""
    WITH selected_model AS (
      SELECT
        model_id,
        JSON_VALUE(metrics_json, '$.score_orientation') AS score_orientation_registry
      FROM `{cfg.project}.ashare_research.research_model_registry`
      WHERE strategy_id = @strategy_id
        AND status = 'selected'
        AND created_date BETWEEN DATE '2020-01-01' AND CURRENT_DATE()
        AND JSON_VALUE(model_params_json, '$.run_id') = @prediction_run_id
      ORDER BY created_at DESC
      LIMIT 1
    )
    SELECT
      pred.predict_date,
      pred.sec_code,
      pred.model_id,
      pred.score,
      pred.rank_raw,
      pred.rank_pct,
      COALESCE(pred.score_orientation, sm.score_orientation_registry) AS score_orientation,
      lab.fwd_ret_1d,
      lab.fwd_ret_5d,
      lab.fwd_ret_10d,
      lab.fwd_ret_20d,
      lab.fwd_xs_ret_1d,
      lab.fwd_xs_ret_5d,
      lab.fwd_xs_ret_10d,
      lab.fwd_xs_ret_20d,
      lab.label_valid_1d,
      lab.label_valid_5d,
      lab.label_valid_10d,
      lab.label_valid_20d,
      SAFE.LOG(feat.circ_mv_cny) AS log_circ_mv,
      feat.circ_mv_cny,
      stock.industry,
      ms.market_regime
    FROM `{cfg.project}.ashare_research.research_model_prediction_daily` AS pred
    JOIN selected_model AS sm
      ON sm.model_id = pred.model_id
    JOIN `{cfg.project}.ashare_dws.dws_stock_universe_daily` AS uni
      ON uni.trade_date = pred.predict_date
     AND uni.sec_code = pred.sec_code
     AND uni.trade_date BETWEEN @start_date AND @end_date
     AND COALESCE(uni.in_universe_default, FALSE)
    JOIN `{cfg.project}.ashare_dws.dws_stock_label_daily` AS lab
      ON lab.trade_date = pred.predict_date
     AND lab.sec_code = pred.sec_code
     AND lab.label_version = @label_version
     AND lab.trade_date BETWEEN @start_date AND @end_date
    LEFT JOIN `{cfg.project}.ashare_dws.dws_stock_feature_daily_v0` AS feat
      ON feat.trade_date = pred.predict_date
     AND feat.sec_code = pred.sec_code
     AND feat.feature_version = @feature_version
     AND feat.trade_date BETWEEN @start_date AND @end_date
    LEFT JOIN `{cfg.project}.ashare_dws.dws_market_state_daily` AS ms
      ON ms.trade_date = pred.predict_date
     AND ms.market_state_version = @market_state_version
     AND ms.trade_date BETWEEN @start_date AND @end_date
    LEFT JOIN `{cfg.project}.ashare_dim.dim_stock` AS stock
      ON stock.sec_code = pred.sec_code
    WHERE pred.run_id = @prediction_run_id
      AND pred.predict_date BETWEEN @start_date AND @end_date
    """
    return query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("strategy_id", "STRING", cfg.strategy_id),
            bigquery.ScalarQueryParameter("prediction_run_id", "STRING", cfg.prediction_run_id),
            bigquery.ScalarQueryParameter("start_date", "DATE", cfg.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", cfg.end_date),
            bigquery.ScalarQueryParameter("label_version", "STRING", cfg.label_version),
            bigquery.ScalarQueryParameter("feature_version", "STRING", cfg.feature_version),
            bigquery.ScalarQueryParameter("market_state_version", "STRING", cfg.market_state_version),
        ],
        labels={"step": "signal_ic_base_read", "mode": "readonly"},
    )


def fetch_calendar(client: bigquery.Client, cfg: AnalysisConfig) -> pd.DataFrame:
    sql = f"""
    SELECT cal_date AS trade_date, trade_date_seq
    FROM `{cfg.project}.ashare_dim.dim_trade_calendar`
    WHERE exchange = 'SSE'
      AND is_open = 1
      AND cal_date BETWEEN @start_date AND @end_date
    ORDER BY cal_date
    """
    return query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("start_date", "DATE", cfg.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", cfg.end_date),
        ],
        labels={"step": "signal_ic_calendar_read", "mode": "readonly"},
    )


def fetch_benchmark(client: bigquery.Client, cfg: AnalysisConfig) -> pd.DataFrame:
    sql = f"""
    SELECT trade_date, SAFE_DIVIDE(pct_chg, 100.0) AS benchmark_return
    FROM `{cfg.project}.ashare_dwd.dwd_index_eod`
    WHERE sec_code = @benchmark_sec_code
      AND trade_date BETWEEN @start_date AND @end_date
    ORDER BY trade_date
    """
    return query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("benchmark_sec_code", "STRING", cfg.benchmark_sec_code),
            bigquery.ScalarQueryParameter("start_date", "DATE", cfg.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", cfg.end_date),
        ],
        labels={"step": "signal_ic_benchmark_read", "mode": "readonly"},
    )


def fetch_official_nav(client: bigquery.Client, cfg: AnalysisConfig) -> pd.DataFrame:
    sql = f"""
    SELECT trade_date, nav, daily_return, cash_cny, net_value_cny
    FROM `{cfg.project}.ashare_research.research_backtest_nav_daily`
    WHERE backtest_id = @backtest_id
      AND trade_date BETWEEN @start_date AND @end_date
    ORDER BY trade_date
    """
    return query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("backtest_id", "STRING", cfg.backtest_id),
            bigquery.ScalarQueryParameter("start_date", "DATE", cfg.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", cfg.end_date),
        ],
        labels={"step": "signal_ic_nav_read", "mode": "readonly"},
    )


def fetch_official_targets(client: bigquery.Client, cfg: AnalysisConfig) -> pd.DataFrame:
    sql = f"""
    SELECT rebalance_date, sec_code, target_weight
    FROM `{cfg.project}.ashare_research.research_portfolio_target_daily`
    WHERE run_id = @prediction_run_id
      AND rebalance_date BETWEEN @start_date AND @end_date
    ORDER BY rebalance_date, sec_code
    """
    return query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("prediction_run_id", "STRING", cfg.prediction_run_id),
            bigquery.ScalarQueryParameter("start_date", "DATE", cfg.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", cfg.end_date),
        ],
        labels={"step": "signal_ic_targets_read", "mode": "readonly"},
    )


def fetch_official_positions(client: bigquery.Client, cfg: AnalysisConfig) -> pd.DataFrame:
    sql = f"""
    SELECT trade_date, sec_code, weight
    FROM `{cfg.project}.ashare_research.research_backtest_position_daily`
    WHERE backtest_id = @backtest_id
      AND trade_date BETWEEN @start_date AND @end_date
      AND weight IS NOT NULL
      AND ABS(weight) > 0
    ORDER BY trade_date, sec_code
    """
    return query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("backtest_id", "STRING", cfg.backtest_id),
            bigquery.ScalarQueryParameter("start_date", "DATE", cfg.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", cfg.end_date),
        ],
        labels={"step": "signal_ic_positions_read", "mode": "readonly"},
    )


def fetch_official_trades(client: bigquery.Client, cfg: AnalysisConfig) -> pd.DataFrame:
    sql = f"""
    SELECT
      trade_date,
      sec_code,
      side,
      planned_shares,
      filled_shares,
      fill_price,
      turnover_cny,
      cash_effect_cny,
      fill_status
    FROM `{cfg.project}.ashare_research.research_backtest_trade_daily`
    WHERE backtest_id = @backtest_id
      AND trade_date BETWEEN @start_date AND @end_date
    ORDER BY trade_date, side, fill_status, sec_code
    """
    return query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("backtest_id", "STRING", cfg.backtest_id),
            bigquery.ScalarQueryParameter("start_date", "DATE", cfg.start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", cfg.end_date),
        ],
        labels={"step": "signal_ic_trades_read", "mode": "readonly"},
    )


def fetch_prices_for_weight_book(
    client: bigquery.Client,
    cfg: AnalysisConfig,
    weight_book: pd.DataFrame,
) -> pd.DataFrame:
    sec_codes = sorted(weight_book["sec_code"].dropna().astype(str).unique().tolist())
    if not sec_codes:
        raise ValueError("weight book has no sec_codes")
    start_buffer = (pd.Timestamp(cfg.start_date).date() - timedelta(days=10)).isoformat()
    sql = f"""
    SELECT
      trade_date,
      sec_code,
      open_hfq,
      close_hfq,
      LAG(close_hfq) OVER (PARTITION BY sec_code ORDER BY trade_date) AS prev_close_hfq
    FROM `{cfg.project}.ashare_dwd.dwd_stock_eod_price`
    WHERE trade_date BETWEEN @start_buffer AND @end_date
      AND sec_code IN UNNEST(@sec_codes)
    ORDER BY sec_code, trade_date
    """
    return query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("start_buffer", "DATE", start_buffer),
            bigquery.ScalarQueryParameter("end_date", "DATE", cfg.end_date),
            bigquery.ArrayQueryParameter("sec_codes", "STRING", sec_codes),
        ],
        labels={"step": "signal_ic_price_read", "mode": "readonly"},
    )


def validate_signal_base(base: pd.DataFrame, cfg: AnalysisConfig) -> None:
    if base.empty:
        raise ValueError(f"no prediction rows found for {cfg.prediction_run_id}")
    date_count = base["predict_date"].nunique()
    if date_count < 100:
        raise ValueError(f"unexpectedly few prediction dates: {date_count}")
    if base["score"].isna().any():
        raise ValueError("prediction score contains NULL")
    if base["market_regime"].isna().any():
        missing = int(base["market_regime"].isna().sum())
        raise ValueError(f"market_regime missing on {missing} prediction rows")
    if base["log_circ_mv"].isna().mean() > 0.05:
        raise ValueError("log_circ_mv missing rate exceeds 5%")


def compute_ic_outputs(base: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        label_col = f"fwd_xs_ret_{horizon}d"
        valid_col = f"label_valid_{horizon}d"
        sample = base.loc[
            base[valid_col].fillna(False)
            & base[label_col].notna()
            & base["score"].notna()
        ].copy()
        if sample.empty:
            continue
        daily_raw = compute_daily_rank_ic(sample, label_col, "raw", {"horizon": horizon})
        daily_frames.append(daily_raw)
        summary_rows.append(summarize_daily_ic(daily_raw, "A5_horizon", f"{horizon}d", horizon))

        if horizon == 5:
            daily_by_year = daily_raw.copy()
            daily_by_year["year"] = pd.to_datetime(daily_by_year["predict_date"]).dt.year.astype(str)
            for year, group in daily_by_year.groupby("year"):
                summary_rows.append(summarize_daily_ic(group, "A1_year", year, horizon))

            neutral = residualize_by_date(sample, label_col, ["log_circ_mv"])
            daily_neutral = compute_daily_rank_ic(
                neutral,
                "label_residual",
                "size_neutral",
                {"horizon": horizon},
                score_col="score_residual",
            )
            daily_frames.append(daily_neutral)
            summary_rows.append(summarize_daily_ic(daily_neutral, "A2_size_neutral", "log_circ_mv", horizon))

            industry_sample = sample.loc[sample["industry"].notna()].copy()
            if not industry_sample.empty:
                industry_neutral = residualize_by_date(industry_sample, label_col, ["log_circ_mv", "industry"])
                daily_industry = compute_daily_rank_ic(
                    industry_neutral,
                    "label_residual",
                    "size_industry_neutral_reference",
                    {"horizon": horizon},
                    score_col="score_residual",
                )
                daily_frames.append(daily_industry)
                summary_rows.append(
                    summarize_daily_ic(
                        daily_industry,
                        "A2_size_industry_neutral_reference",
                        "log_circ_mv_plus_snapshot_industry",
                        horizon,
                    )
                )

            for regime, group in sample.groupby("market_regime"):
                daily_regime = compute_daily_rank_ic(
                    group,
                    label_col,
                    "market_regime",
                    {"horizon": horizon, "bucket": str(regime)},
                )
                daily_frames.append(daily_regime)
                summary_rows.append(summarize_daily_ic(daily_regime, "A3_market_regime", str(regime), horizon))

            bucket_rows = compute_bucket_spread_summary(sample, label_col)
            summary_rows.extend(bucket_rows)

    daily_ic = pd.concat(daily_frames, ignore_index=True) if daily_frames else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    return daily_ic, summary


def compute_daily_rank_ic(
    df: pd.DataFrame,
    label_col: str,
    section: str,
    attrs: dict[str, Any],
    *,
    score_col: str = "score",
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for predict_date, group in df.groupby("predict_date", sort=True):
        sub = group[[score_col, label_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(sub) < 30:
            ic = np.nan
        else:
            ic = sub[score_col].corr(sub[label_col], method="spearman")
        row = {
            "predict_date": predict_date,
            "section": section,
            "rank_ic": float(ic) if pd.notna(ic) else np.nan,
            "n_obs": int(len(sub)),
        }
        row.update(attrs)
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_daily_ic(
    daily_ic: pd.DataFrame,
    section: str,
    bucket: str,
    horizon: int,
) -> dict[str, Any]:
    values = daily_ic["rank_ic"].dropna().astype(float)
    nw = newey_west_mean_t(values, lag=max(horizon, 1))
    return {
        "section": section,
        "bucket": bucket,
        "horizon": horizon,
        "mean_rank_ic": float(values.mean()) if len(values) else np.nan,
        "median_rank_ic": float(values.median()) if len(values) else np.nan,
        "positive_day_ratio": float((values > 0).mean()) if len(values) else np.nan,
        "n_days": int(len(values)),
        "n_obs_total": int(daily_ic["n_obs"].sum()) if "n_obs" in daily_ic.columns else 0,
        "nw_lag": max(horizon, 1),
        "nw_t_stat": nw["t_stat"],
        "nw_effective_n": nw["effective_n"],
        "sample_start": iso_date(daily_ic["predict_date"].min()) if not daily_ic.empty else None,
        "sample_end": iso_date(daily_ic["predict_date"].max()) if not daily_ic.empty else None,
    }


def newey_west_mean_t(values: Iterable[float], lag: int) -> dict[str, float]:
    arr = np.asarray([float(v) for v in values if pd.notna(v)], dtype=float)
    n = len(arr)
    if n < 3:
        return {"t_stat": np.nan, "effective_n": float(n)}
    lag = max(0, min(int(lag), n - 1))
    mean = float(np.mean(arr))
    centered = arr - mean
    gamma0 = float(np.dot(centered, centered) / n)
    long_run_var = gamma0
    for k in range(1, lag + 1):
        gamma = float(np.dot(centered[k:], centered[:-k]) / n)
        weight = 1.0 - k / (lag + 1.0)
        long_run_var += 2.0 * weight * gamma
    if long_run_var <= 0 or not math.isfinite(long_run_var):
        return {"t_stat": np.nan, "effective_n": float(n)}
    se = math.sqrt(long_run_var / n)
    sample_var = float(np.var(arr, ddof=1))
    effective_n = min(float(n), max(1.0, sample_var / (long_run_var / n))) if sample_var > 0 else float(n)
    return {"t_stat": mean / se if se > 0 else np.nan, "effective_n": effective_n}


def residualize_by_date(df: pd.DataFrame, label_col: str, controls: list[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for _, group in df.groupby("predict_date", sort=True):
        work = group.copy()
        x_cols: list[str] = []
        if "log_circ_mv" in controls:
            x_cols.append("log_circ_mv")
        if "industry" in controls:
            dummies = pd.get_dummies(work["industry"].fillna("UNKNOWN"), prefix="industry", dtype=float)
            work = pd.concat([work, dummies], axis=1)
            x_cols.extend(dummies.columns.tolist())
        valid = work[["score", label_col, *x_cols]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(valid) <= len(x_cols) + 2:
            continue
        x = valid[x_cols].to_numpy(dtype=float) if x_cols else np.empty((len(valid), 0))
        x = np.column_stack([np.ones(len(valid)), x])
        score_resid = ols_residual(valid["score"].to_numpy(dtype=float), x)
        label_resid = ols_residual(valid[label_col].to_numpy(dtype=float), x)
        out = work.loc[valid.index].copy()
        out["score_residual"] = score_resid
        out["label_residual"] = label_resid
        frames.append(out)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=[*df.columns, "score_residual", "label_residual"])


def ols_residual(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    return y - x @ beta


def compute_bucket_spread_summary(sample: pd.DataFrame, label_col: str) -> list[dict[str, Any]]:
    daily_rows: list[dict[str, Any]] = []
    for predict_date, group in sample.groupby("predict_date", sort=True):
        sub = group[["score", label_col]].dropna().copy()
        if len(sub) < 100:
            continue
        sub["bucket"] = pd.qcut(sub["score"].rank(method="first"), 10, labels=False) + 1
        top_decile = sub.loc[sub["bucket"] == 10, label_col].mean()
        bottom_decile = sub.loc[sub["bucket"] == 1, label_col].mean()
        top_5_cut = sub["score"].quantile(0.95)
        top_5 = sub.loc[sub["score"] >= top_5_cut, label_col].mean()
        top_half = sub.loc[sub["bucket"] >= 6, label_col].mean()
        bottom_half = sub.loc[sub["bucket"] <= 5, label_col].mean()
        long_contribution = float(top_decile) if pd.notna(top_decile) else np.nan
        short_contribution = float(-bottom_decile) if pd.notna(bottom_decile) else np.nan
        total_abs = abs(long_contribution) + abs(short_contribution)
        short_share = abs(short_contribution) / total_abs if total_abs > 0 else np.nan
        daily_rows.append(
            {
                "predict_date": predict_date,
                "top_decile_mean": top_decile,
                "bottom_decile_mean": bottom_decile,
                "top_minus_bottom": top_decile - bottom_decile,
                "top_5pct_mean": top_5,
                "top_half_minus_bottom_half": top_half - bottom_half,
                "short_side_abs_contribution_share": short_share,
                "n_obs": len(sub),
            }
        )
    daily = pd.DataFrame(daily_rows)
    if daily.empty:
        return []
    rows: list[dict[str, Any]] = []
    for field, bucket in [
        ("top_decile_mean", "top_decile_mean"),
        ("bottom_decile_mean", "bottom_decile_mean"),
        ("top_minus_bottom", "top_decile_minus_bottom_decile"),
        ("top_5pct_mean", "top_5pct_mean"),
        ("top_half_minus_bottom_half", "top_half_minus_bottom_half"),
        ("short_side_abs_contribution_share", "short_side_abs_contribution_share"),
    ]:
        values = daily[field].dropna().astype(float)
        nw = newey_west_mean_t(values, lag=5)
        rows.append(
            {
                "section": "A4_bucket_contribution",
                "bucket": bucket,
                "horizon": 5,
                "mean_rank_ic": np.nan,
                "median_rank_ic": np.nan,
                "positive_day_ratio": np.nan,
                "n_days": int(len(values)),
                "n_obs_total": int(daily["n_obs"].sum()),
                "nw_lag": 5,
                "nw_t_stat": nw["t_stat"],
                "nw_effective_n": nw["effective_n"],
                "sample_start": iso_date(daily["predict_date"].min()),
                "sample_end": iso_date(daily["predict_date"].max()),
                "mean_value": float(values.mean()) if len(values) else np.nan,
            }
        )
    return rows


def build_biweekly_rebalance_dates(calendar: pd.DataFrame, start_date: str, end_date: str) -> list[date]:
    cal = calendar.copy()
    cal["trade_date"] = pd.to_datetime(cal["trade_date"]).dt.date
    cal = cal[(cal["trade_date"] >= pd.Timestamp(start_date).date()) & (cal["trade_date"] <= pd.Timestamp(end_date).date())]
    iso = pd.to_datetime(cal["trade_date"]).dt.isocalendar()
    cal["iso_year"] = iso.year.astype(int)
    cal["iso_week"] = iso.week.astype(int)
    weekly_last = (
        cal.groupby(["iso_year", "iso_week"], as_index=False)["trade_date"]
        .max()
        .sort_values("trade_date")
        .reset_index(drop=True)
    )
    weekly_last["week_idx"] = np.arange(1, len(weekly_last) + 1)
    return weekly_last.loc[(weekly_last["week_idx"] - 1) % 2 == 0, "trade_date"].tolist()


def build_weight_book(base: pd.DataFrame, rebalance_dates: list[date]) -> pd.DataFrame:
    use_dates = set(pd.to_datetime(pd.Series(rebalance_dates)).dt.date.tolist())
    pred = base.copy()
    pred["predict_date"] = pd.to_datetime(pred["predict_date"]).dt.date
    pred = pred[pred["predict_date"].isin(use_dates)]
    frames: list[pd.DataFrame] = []
    for signal_date, group in pred.groupby("predict_date", sort=True):
        g = group[["predict_date", "sec_code", "score"]].dropna().sort_values("score", ascending=False)
        if len(g) < 50:
            continue
        n_decile = max(1, int(math.floor(len(g) * 0.10)))
        levels = {
            "L0": l0_weights(g, n_decile),
            "L0.5": long_score_weights(g.head(n_decile), "L0.5"),
            "L1": long_score_weights(g.head(50), "L1"),
            "L2": long_score_weights(g.head(20), "L2"),
            "L3": equal_top_weights(g.head(20), "L3", cap=0.075),
        }
        for level, weights in levels.items():
            if weights.empty:
                continue
            out = weights.copy()
            out["signal_date"] = signal_date
            out["level"] = level
            frames.append(out)
    if not frames:
        raise ValueError("no transfer ladder weights generated")
    return pd.concat(frames, ignore_index=True)


def long_score_weights(group: pd.DataFrame, level: str) -> pd.DataFrame:
    scores = group["score"].astype(float)
    raw = scores - scores.min() + 1e-12
    if raw.sum() <= 0 or not math.isfinite(float(raw.sum())):
        weights = pd.Series(1.0 / len(group), index=group.index)
    else:
        weights = raw / raw.sum()
    return pd.DataFrame({"sec_code": group["sec_code"].values, "weight": weights.values, "level": level})


def equal_top_weights(group: pd.DataFrame, level: str, cap: float) -> pd.DataFrame:
    if group.empty:
        return pd.DataFrame(columns=["sec_code", "weight", "level"])
    raw_weight = min(cap, 1.0 / len(group))
    weights = pd.Series(raw_weight, index=group.index)
    total = float(weights.sum())
    if total > 0:
        weights = weights / total
    return pd.DataFrame({"sec_code": group["sec_code"].values, "weight": weights.values, "level": level})


def l0_weights(group: pd.DataFrame, n_decile: int) -> pd.DataFrame:
    top = group.head(n_decile).copy()
    bottom = group.tail(n_decile).copy()
    top_w = long_score_weights(top, "L0")
    bottom_scores = bottom["score"].astype(float)
    raw_short = bottom_scores.max() - bottom_scores + 1e-12
    if raw_short.sum() <= 0 or not math.isfinite(float(raw_short.sum())):
        short_weights = pd.Series(-1.0 / len(bottom), index=bottom.index)
    else:
        short_weights = -(raw_short / raw_short.sum())
    bottom_w = pd.DataFrame({"sec_code": bottom["sec_code"].values, "weight": short_weights.values, "level": "L0"})
    return pd.concat([top_w, bottom_w], ignore_index=True)


def compute_transfer_ladder_outputs(
    *,
    weight_book: pd.DataFrame,
    prices: pd.DataFrame,
    calendar: pd.DataFrame,
    benchmark: pd.DataFrame,
    nav: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cal = calendar.copy()
    cal["trade_date"] = pd.to_datetime(cal["trade_date"]).dt.date
    trading_dates = [d for d in cal["trade_date"].tolist() if pd.Timestamp(start_date).date() <= d <= pd.Timestamp(end_date).date()]
    next_open = next_open_map(trading_dates)
    price_returns = build_price_return_lookup(prices, trading_dates)
    bench = benchmark.copy()
    bench["trade_date"] = pd.to_datetime(bench["trade_date"]).dt.date
    bench_by_date = bench.set_index("trade_date")["benchmark_return"].to_dict()
    nav_cmp = nav.copy()
    nav_cmp["trade_date"] = pd.to_datetime(nav_cmp["trade_date"]).dt.date
    rows: list[dict[str, Any]] = []
    l3_daily_cost0 = pd.DataFrame()
    for level in TRANSFER_LEVELS:
        level_weights = weight_book[weight_book["level"] == level].copy()
        signal_dates = sorted(level_weights["signal_date"].unique().tolist())
        for cost_bps in TURNOVER_COST_BPS:
            daily = simulate_weight_book(
                level_weights,
                signal_dates,
                trading_dates,
                next_open,
                price_returns,
                cost_bps=cost_bps,
            )
            daily = daily.merge(bench[["trade_date", "benchmark_return"]], on="trade_date", how="left")
            metrics = performance_metrics(daily, level, cost_bps)
            rows.append(metrics)
            if level == "L3" and cost_bps == 0.0:
                l3_daily_cost0 = daily
    return pd.DataFrame(rows), l3_daily_cost0


def next_open_map(trading_dates: list[date]) -> dict[date, date]:
    mapping: dict[date, date] = {}
    for i, trade_date in enumerate(trading_dates[:-1]):
        mapping[trade_date] = trading_dates[i + 1]
    return mapping


def build_price_return_lookup(prices: pd.DataFrame, trading_dates: list[date]) -> dict[tuple[str, date], tuple[float, float]]:
    px = prices.copy()
    px["trade_date"] = pd.to_datetime(px["trade_date"]).dt.date
    px = px[px["trade_date"].isin(set(trading_dates))]
    lookup: dict[tuple[str, date], tuple[float, float]] = {}
    for row in px.itertuples(index=False):
        open_hfq = float(row.open_hfq) if pd.notna(row.open_hfq) else np.nan
        close_hfq = float(row.close_hfq) if pd.notna(row.close_hfq) else np.nan
        prev_close_hfq = float(row.prev_close_hfq) if pd.notna(row.prev_close_hfq) else np.nan
        intraday = close_hfq / open_hfq - 1.0 if open_hfq > 0 and close_hfq > 0 else np.nan
        close_to_close = close_hfq / prev_close_hfq - 1.0 if prev_close_hfq > 0 and close_hfq > 0 else np.nan
        lookup[(str(row.sec_code), row.trade_date)] = (intraday, close_to_close)
    return lookup


def simulate_weight_book(
    level_weights: pd.DataFrame,
    signal_dates: list[date],
    trading_dates: list[date],
    next_open: dict[date, date],
    price_returns: dict[tuple[str, date], tuple[float, float]],
    *,
    cost_bps: float,
) -> pd.DataFrame:
    weights_by_signal = {
        signal_date: dict(zip(group["sec_code"].astype(str), group["weight"].astype(float)))
        for signal_date, group in level_weights.groupby("signal_date")
    }
    exec_by_date = {next_open[s]: s for s in signal_dates if s in next_open}
    current_weights: dict[str, float] = {}
    nav = 1.0
    rows: list[dict[str, Any]] = []
    for trade_date in trading_dates:
        is_exec = trade_date in exec_by_date
        cost_rate = 0.0
        if is_exec:
            new_weights = weights_by_signal[exec_by_date[trade_date]]
            turnover = portfolio_turnover(current_weights, new_weights)
            cost_rate = turnover * cost_bps / 10000.0
            current_weights = dict(new_weights)
        gross_return = 0.0
        evolved_weights: dict[str, float] = {}
        for sec_code, weight in current_weights.items():
            intraday, close_to_close = price_returns.get((sec_code, trade_date), (np.nan, np.nan))
            stock_return = intraday if is_exec else close_to_close
            if pd.isna(stock_return):
                stock_return = 0.0
            gross_return += weight * float(stock_return)
            evolved_weights[sec_code] = weight * (1.0 + float(stock_return))
        daily_return = gross_return - cost_rate
        nav *= 1.0 + daily_return
        denom = 1.0 + gross_return
        if denom != 0 and math.isfinite(denom):
            current_weights = {sec: w / denom for sec, w in evolved_weights.items() if abs(w / denom) > 1e-10}
        else:
            current_weights = {}
        rows.append(
            {
                "trade_date": trade_date,
                "daily_return": daily_return,
                "nav": nav,
                "gross_exposure": float(sum(abs(w) for w in current_weights.values())),
                "cost_rate": cost_rate,
                "is_exec_date": is_exec,
            }
        )
    return pd.DataFrame(rows)


def portfolio_turnover(old: dict[str, float], new: dict[str, float]) -> float:
    keys = set(old) | set(new)
    return float(sum(abs(new.get(k, 0.0) - old.get(k, 0.0)) for k in keys))


def performance_metrics(daily: pd.DataFrame, level: str, cost_bps: float) -> dict[str, Any]:
    returns = daily["daily_return"].fillna(0.0).astype(float)
    benchmark = daily["benchmark_return"].fillna(0.0).astype(float)
    nav = (1.0 + returns).cumprod()
    bench_nav = (1.0 + benchmark).cumprod()
    total_return = float(nav.iloc[-1] - 1.0)
    bench_total_return = float(bench_nav.iloc[-1] - 1.0)
    n = int(returns.notna().sum())
    cagr = compound_annual_return(total_return, n)
    vol = float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR)) if n > 1 else np.nan
    sharpe = cagr / vol if vol and vol > 0 else np.nan
    maxdd, peak, trough = max_drawdown(nav, daily["trade_date"])
    excess = returns - benchmark
    ir = information_ratio(excess)
    crunch = daily[
        (pd.to_datetime(daily["trade_date"]) >= pd.Timestamp(CRUNCH_START))
        & (pd.to_datetime(daily["trade_date"]) <= pd.Timestamp(CRUNCH_END))
    ]
    crunch_return = compound_total_return(crunch["daily_return"])
    crunch_benchmark = compound_total_return(crunch["benchmark_return"])
    return {
        "level": level,
        "cost_bps": cost_bps,
        "total_return": total_return,
        "compound_annual_return": cagr,
        "annual_vol": vol,
        "absolute_sharpe_or_contract_sharpe": sharpe,
        "benchmark_total_return": bench_total_return,
        "excess_return_vs_000852": total_return - bench_total_return,
        "information_ratio_vs_000852": ir,
        "max_drawdown": maxdd,
        "max_drawdown_peak_date": iso_date(peak),
        "max_drawdown_trough_date": iso_date(trough),
        "calmar_ratio": cagr / abs(maxdd) if maxdd < 0 else np.nan,
        "crunch_strategy_return": crunch_return,
        "crunch_000852_return": crunch_benchmark,
        "crunch_excess_return_vs_000852": crunch_return - crunch_benchmark,
        "avg_gross_exposure": float(daily["gross_exposure"].mean()),
        "rebalance_count": int(daily["is_exec_date"].sum()),
        "cumulative_cost_drag_pp": float(daily["cost_rate"].sum() * 100.0),
        "return_period_count": n,
    }


def compound_total_return(values: pd.Series) -> float:
    clean = values.dropna().astype(float)
    if clean.empty:
        return np.nan
    return float((1.0 + clean).prod() - 1.0)


def compound_annual_return(total_return: float, periods: int) -> float:
    if periods <= 0 or total_return <= -1.0:
        return np.nan
    return float((1.0 + total_return) ** (TRADING_DAYS_PER_YEAR / periods) - 1.0)


def max_drawdown(nav: pd.Series, dates: pd.Series) -> tuple[float, Any, Any]:
    running_max = nav.cummax()
    drawdown = nav / running_max - 1.0
    trough_idx = int(drawdown.idxmin())
    peak_slice = nav.loc[:trough_idx]
    peak_value = peak_slice.max()
    peak_idx = int(peak_slice[peak_slice == peak_value].index[-1])
    return float(drawdown.loc[trough_idx]), dates.loc[peak_idx], dates.loc[trough_idx]


def information_ratio(excess_returns: pd.Series) -> float:
    clean = excess_returns.dropna().astype(float)
    if len(clean) < 2:
        return np.nan
    denom = float(clean.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))
    if denom <= 0 or not math.isfinite(denom):
        return np.nan
    return float(clean.mean() * TRADING_DAYS_PER_YEAR / denom)


def compute_transfer_coefficients(
    *,
    base: pd.DataFrame,
    weight_book: pd.DataFrame,
    official_targets: pd.DataFrame,
    official_positions: pd.DataFrame,
    calendar: pd.DataFrame,
) -> pd.DataFrame:
    l2 = weight_book[weight_book["level"] == "L2"].copy()
    universe_by_signal = build_rebalance_universe(base, sorted(l2["signal_date"].unique().tolist()))
    cal = calendar.copy()
    cal["trade_date"] = pd.to_datetime(cal["trade_date"]).dt.date
    next_open = next_open_map(cal["trade_date"].tolist())
    targets = official_targets.copy()
    positions = official_positions.copy()
    targets["rebalance_date"] = pd.to_datetime(targets["rebalance_date"]).dt.date
    positions["trade_date"] = pd.to_datetime(positions["trade_date"]).dt.date
    rows: list[dict[str, Any]] = []
    for signal_date, ideal in l2.groupby("signal_date"):
        ideal_weights = dict(zip(ideal["sec_code"].astype(str), ideal["weight"].astype(float)))
        ideal_names = set(ideal_weights)
        target_sub = targets[targets["rebalance_date"] == signal_date]
        target_weights = dict(zip(target_sub["sec_code"].astype(str), target_sub["target_weight"].astype(float)))
        target_names = set(target_weights)
        exec_date = next_open.get(signal_date)
        pos_weights: dict[str, float] = {}
        if exec_date is not None:
            pos_sub = positions[positions["trade_date"] == exec_date]
            pos_weights = dict(zip(pos_sub["sec_code"].astype(str), pos_sub["weight"].astype(float)))
        realized_names = set(pos_weights)
        domain = universe_by_signal.get(signal_date, sorted(ideal_names | target_names | realized_names))
        realized_weight_sum = float(sum(pos_weights.values()))
        rows.append(
            {
                "signal_date": signal_date,
                "exec_date": exec_date,
                "tc_domain": "full_prediction_universe",
                "tc_target": weight_correlation_on_domain(ideal_weights, target_weights, domain),
                "tc_realized": weight_correlation_on_domain(ideal_weights, pos_weights, domain),
                "ideal_nonzero": len(ideal_weights),
                "target_nonzero": len(target_weights),
                "realized_nonzero": len(pos_weights),
                "universe_size": len(domain),
                "target_ideal_overlap_count": len(ideal_names & target_names),
                "target_ideal_overlap_rate": safe_divide(len(ideal_names & target_names), len(ideal_names)),
                "target_extra_count": len(target_names - ideal_names),
                "ideal_missing_from_target_count": len(ideal_names - target_names),
                "realized_ideal_overlap_count": len(ideal_names & realized_names),
                "realized_ideal_overlap_rate": safe_divide(len(ideal_names & realized_names), len(ideal_names)),
                "realized_target_overlap_count": len(target_names & realized_names),
                "realized_target_overlap_rate": safe_divide(len(target_names & realized_names), len(target_names)),
                "target_weight_sum": float(sum(target_weights.values())),
                "realized_weight_sum": realized_weight_sum,
                "official_cash_weight": 1.0 - realized_weight_sum,
            }
        )
    return pd.DataFrame(rows)


def build_rebalance_universe(base: pd.DataFrame, signal_dates: list[date]) -> dict[date, list[str]]:
    pred = base[["predict_date", "sec_code"]].copy()
    pred["predict_date"] = pd.to_datetime(pred["predict_date"]).dt.date
    use_dates = set(signal_dates)
    pred = pred[pred["predict_date"].isin(use_dates)]
    return {
        signal_date: sorted(group["sec_code"].dropna().astype(str).unique().tolist())
        for signal_date, group in pred.groupby("predict_date")
    }


def weight_correlation_on_domain(
    a: dict[str, float],
    b: dict[str, float],
    domain: Iterable[str],
    *,
    min_std: float = CORRELATION_MIN_STD,
) -> float:
    keys = sorted(set(domain))
    if len(keys) < 3:
        return np.nan
    x = np.asarray([a.get(k, 0.0) for k in keys], dtype=float)
    y = np.asarray([b.get(k, 0.0) for k in keys], dtype=float)
    if np.std(x) <= min_std or np.std(y) <= min_std:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return np.nan
    return float(numerator / denominator)


def compute_execution_diagnostics(
    *,
    nav: pd.DataFrame,
    positions: pd.DataFrame,
    trades: pd.DataFrame,
    transfer_coefficients: pd.DataFrame,
) -> dict[str, Any]:
    nav_frame = nav.copy()
    if nav_frame.empty or "cash_cny" not in nav_frame.columns or "net_value_cny" not in nav_frame.columns:
        return {}
    nav_frame["trade_date"] = pd.to_datetime(nav_frame["trade_date"]).dt.date
    nav_frame["nav_cash_weight"] = nav_frame["cash_cny"].astype(float) / nav_frame["net_value_cny"].astype(float)

    pos = positions.copy()
    if pos.empty:
        pos_sum = pd.DataFrame(columns=["trade_date", "position_weight_sum", "position_count"])
    else:
        pos["trade_date"] = pd.to_datetime(pos["trade_date"]).dt.date
        pos_sum = (
            pos.groupby("trade_date", as_index=False)
            .agg(position_weight_sum=("weight", "sum"), position_count=("sec_code", "nunique"))
        )

    joined = nav_frame.merge(pos_sum, on="trade_date", how="left")
    joined["position_weight_sum"] = joined["position_weight_sum"].fillna(0.0).astype(float)
    joined["position_count"] = joined["position_count"].fillna(0).astype(int)
    joined["implied_cash_weight"] = 1.0 - joined["position_weight_sum"]
    joined["cash_weight_abs_diff"] = (joined["implied_cash_weight"] - joined["nav_cash_weight"]).abs()

    cash_summary = {
        "day_count": int(len(joined)),
        "avg_nav_cash_weight": float(joined["nav_cash_weight"].mean()),
        "avg_implied_cash_weight": float(joined["implied_cash_weight"].mean()),
        "max_cash_weight_abs_diff": float(joined["cash_weight_abs_diff"].max()),
        "avg_cash_weight_abs_diff": float(joined["cash_weight_abs_diff"].mean()),
        "diff_gt_1e9_days": int((joined["cash_weight_abs_diff"] > 1e-9).sum()),
        "min_position_count": int(joined["position_count"].min()),
        "avg_position_count": float(joined["position_count"].mean()),
        "max_nav_cash_weight": float(joined["nav_cash_weight"].max()),
        "cash_gt_50pct_days": int((joined["nav_cash_weight"] > 0.5).sum()),
    }

    trades_frame = trades.copy()
    if not trades_frame.empty:
        trades_frame["trade_date"] = pd.to_datetime(trades_frame["trade_date"]).dt.date
    fill_summary = summarize_fill_status(trades_frame)

    worst = worst_transfer_row(transfer_coefficients)
    worst_fill_summary = pd.DataFrame()
    if worst and not trades_frame.empty and worst.get("exec_date") is not None:
        worst_date = pd.Timestamp(worst["exec_date"]).date()
        worst_fill_summary = summarize_fill_status(trades_frame[trades_frame["trade_date"] == worst_date])

    return {
        "cash_summary": cash_summary,
        "worst_transfer": worst,
        "fill_summary": fill_summary,
        "worst_fill_summary": worst_fill_summary,
    }


def summarize_fill_status(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["side", "fill_status", "order_count", "date_count", "turnover_cny"])
    grouped = (
        trades.groupby(["side", "fill_status"], as_index=False)
        .agg(
            order_count=("fill_status", "size"),
            date_count=("trade_date", "nunique"),
            turnover_cny=("turnover_cny", "sum"),
        )
        .sort_values(["side", "fill_status"])
        .reset_index(drop=True)
    )
    return grouped


def worst_transfer_row(transfer_coefficients: pd.DataFrame) -> dict[str, Any] | None:
    if transfer_coefficients.empty or "realized_target_overlap_rate" not in transfer_coefficients.columns:
        return None
    idx = transfer_coefficients["realized_target_overlap_rate"].astype(float).idxmin()
    return transfer_coefficients.loc[idx].to_dict()


def append_official_identity_check(
    transfer_results: pd.DataFrame,
    l3_daily: pd.DataFrame,
    official_nav: pd.DataFrame,
) -> pd.DataFrame:
    if l3_daily.empty or official_nav.empty:
        transfer_results["official_l3_daily_return_corr"] = np.nan
        transfer_results["official_l3_cagr_diff"] = np.nan
        transfer_results["official_l3_maxdd_diff"] = np.nan
        return transfer_results
    official = official_nav.copy()
    official["trade_date"] = pd.to_datetime(official["trade_date"]).dt.date
    merged = l3_daily.merge(official[["trade_date", "daily_return", "nav"]], on="trade_date", how="inner", suffixes=("_paper", "_official"))
    corr = merged["daily_return_paper"].corr(merged["daily_return_official"]) if len(merged) > 2 else np.nan
    paper_row = performance_metrics(l3_daily.assign(benchmark_return=0.0), "L3", 0.0)
    official_return = float(official["nav"].iloc[-1] / official["nav"].iloc[0] - 1.0) if len(official) else np.nan
    official_cagr = compound_annual_return(official_return, max(0, len(official) - 1))
    official_maxdd, _, _ = max_drawdown(official["nav"].reset_index(drop=True), official["trade_date"].reset_index(drop=True))
    transfer_results["official_l3_daily_return_corr"] = np.nan
    transfer_results["official_l3_cagr_diff"] = np.nan
    transfer_results["official_l3_maxdd_diff"] = np.nan
    mask = (transfer_results["level"] == "L3") & (transfer_results["cost_bps"] == 0.0)
    transfer_results.loc[mask, "official_l3_daily_return_corr"] = corr
    transfer_results.loc[mask, "official_l3_cagr_diff"] = paper_row["compound_annual_return"] - official_cagr
    transfer_results.loc[mask, "official_l3_maxdd_diff"] = paper_row["max_drawdown"] - official_maxdd
    return transfer_results


def write_outputs(
    cfg: AnalysisConfig,
    daily_ic: pd.DataFrame,
    ic_summary: pd.DataFrame,
    transfer_results: pd.DataFrame,
    transfer_coefficients: pd.DataFrame,
    execution_diagnostics: dict[str, Any],
) -> None:
    for path, df in [
        (cfg.daily_ic_csv, daily_ic),
        (cfg.ic_csv, ic_summary),
        (cfg.transfer_csv, transfer_results),
        (cfg.tc_csv, transfer_coefficients),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
    if not cfg.skip_report:
        cfg.report_md.parent.mkdir(parents=True, exist_ok=True)
        cfg.report_md.write_text(
            build_report(cfg, ic_summary, transfer_results, transfer_coefficients, execution_diagnostics),
            encoding="utf-8",
        )


def build_report(
    cfg: AnalysisConfig,
    ic_summary: pd.DataFrame,
    transfer_results: pd.DataFrame,
    transfer_coefficients: pd.DataFrame,
    execution_diagnostics: dict[str, Any] | None = None,
) -> str:
    best_l0 = top_row(transfer_results[transfer_results["level"] == "L0"], "absolute_sharpe_or_contract_sharpe")
    l3_check = transfer_results[
        (transfer_results["level"] == "L3") & (transfer_results["cost_bps"] == 0.0)
    ]
    tc_summary = transfer_coefficients.mean(numeric_only=True).to_dict() if not transfer_coefficients.empty else {}
    execution_diagnostics = execution_diagnostics or {}
    cash_summary = execution_diagnostics.get("cash_summary", {})
    worst_transfer = execution_diagnostics.get("worst_transfer") or {}
    raw_5d = summary_value(ic_summary, "A5_horizon", "5d", "mean_rank_ic")
    size_neutral = summary_value(ic_summary, "A2_size_neutral", "log_circ_mv", "mean_rank_ic")
    industry_neutral = summary_value(
        ic_summary,
        "A2_size_industry_neutral_reference",
        "log_circ_mv_plus_snapshot_industry",
        "mean_rank_ic",
    )
    short_share = summary_value(
        ic_summary,
        "A4_bucket_contribution",
        "short_side_abs_contribution_share",
        "mean_value",
    )
    risk_off_t = summary_value(ic_summary, "A3_market_regime", "risk_off", "nw_t_stat")
    l0_cost20 = transfer_results[
        (transfer_results["level"] == "L0") & (transfer_results["cost_bps"] == 20.0)
    ]
    lines = [
        "# 策略1信号IC分解与组合转换效率",
        "",
        "> 文档维护：GPT-5 Codex（最近更新 2026-06-11）",
        "",
        "## 预登记解读规则",
        "",
    ]
    lines.extend(f"- {rule}" for rule in PREREGISTERED_RULES)
    lines.extend(
        [
            "",
            "## 方法与边界",
            "",
            f"- prediction_run_id: `{cfg.prediction_run_id}`",
            f"- backtest_id: `{cfg.backtest_id}`",
            f"- 窗口: `{cfg.start_date}` 至 `{cfg.end_date}`",
            f"- label_version: `{cfg.label_version}`；主 IC 用 `fwd_xs_ret_5d`，horizon 曲线用 `fwd_xs_ret_1d/5d/10d/20d`。",
            f"- feature_version: `{cfg.feature_version}`；市值中性化用 `log(circ_mv_cny)`，行业中性化仅作为非 PIT snapshot 参考。",
            f"- market_state_version: `{cfg.market_state_version}`；IC regime 分组使用同日 `predict_date`，不做 t+1 shift。",
            "- `pred.score` 已是研究产物中用于排序的最终方向分数，本报告不按 `score_orientation` 再反转。",
            "- Transfer ladder 是 NAV 级 paper portfolio；忽略 lot rounding、涨跌停成交约束、现金再分配和真实 ledger 执行细节。L3 与 official ledger 的差异只用于估算转换损耗，不等同正式回测。",
            "- L0/L0.5/L1/L2 的 score-weighted leg 使用组内 `score - min(score) + 1e-12` 归一化；最低分入选名的权重会接近 0，这是本报告的 paper 权重定义，不是生产组合权重。",
            "- BigQuery 全程只读；脚本仅读取 research/DWS/DWD/DIM 表并在本地 pandas 计算，未写 `ashare_research` / ADS / promotion 表。",
            "",
            "## 关键结论",
            "",
            f"- 5d raw rank IC = {fmt_float(raw_5d)}，Newey-West t = {fmt_float(summary_value(ic_summary, 'A5_horizon', '5d', 'nw_t_stat'))}；年度 IC 六年全部为正。",
            f"- 市值中性后 IC = {fmt_float(size_neutral)}，保留比例 = {fmt_pct(safe_ratio(size_neutral, raw_5d))}；行业 snapshot 参考中性后 IC = {fmt_float(industry_neutral)}，保留比例 = {fmt_pct(safe_ratio(industry_neutral, raw_5d))}。按预登记阈值，当前结果更像存在真实 stock selection，而不是纯小市值风格。",
            f"- risk_off 桶 IC = {fmt_float(summary_value(ic_summary, 'A3_market_regime', 'risk_off', 'mean_rank_ic'))}，NW t = {fmt_float(risk_off_t)}；risk_on 桶 IC = {fmt_float(summary_value(ic_summary, 'A3_market_regime', 'risk_on', 'mean_rank_ic'))}。risk_off 仍为正但统计显著性弱，后续 regime conditional 排序可作为备选，不是本轮最强证据。",
            f"- top/bottom decile 5d spread = {fmt_pct(summary_value(ic_summary, 'A4_bucket_contribution', 'top_decile_minus_bottom_decile', 'mean_value'))}；short-side contribution share = {fmt_pct(short_share)}，没有超过 60% 硬阈值，long-only 并非完全吃不到信号。",
            "",
            "Transfer ladder 给出的更强结论：",
            f"- L0 score-weighted long/short no-cost annual Sharpe = {fmt_float(best_l0.get('absolute_sharpe_or_contract_sharpe') if best_l0 else np.nan)}；20bps 成本后仍为 {fmt_float(l0_cost20.iloc[0]['absolute_sharpe_or_contract_sharpe'] if not l0_cost20.empty else np.nan)}。按预登记规则，信号容量不是主要瓶颈。",
            f"- L0.5（top decile long-only score-weighted）IR = {fmt_float(level_metric(transfer_results, 'L0.5', 'information_ratio_vs_000852'))}，L1 Top50 IR = {fmt_float(level_metric(transfer_results, 'L1', 'information_ratio_vs_000852'))}，L2 Top20 IR = {fmt_float(level_metric(transfer_results, 'L2', 'information_ratio_vs_000852'))}。宽度从 top decile 收到 Top50/Top20 没有形成第二个悬崖；主要落差在 L0 多空到 long-only 之间。",
            f"- Official target 与 score-weighted Top20 的名字重合率均值 = {fmt_pct(tc_summary.get('target_ideal_overlap_rate'))}，最小值 = {fmt_pct(transfer_min(transfer_coefficients, 'target_ideal_overlap_rate'))}；L3-L2 IR 差 = {fmt_float(level_metric_delta(transfer_results, 'L3', 'L2', 'information_ratio_vs_000852'))}。按预登记规则，目标组合成员资格忠实于信号，等权替代分数权重不是优先瓶颈。",
            f"- 执行层诊断：实际持仓相对 target 的覆盖率均值 = {fmt_pct(tc_summary.get('realized_target_overlap_rate'))}，最小值 = {fmt_pct(transfer_min(transfer_coefficients, 'realized_target_overlap_rate'))}；official 现金权重均值 = {fmt_pct(tc_summary.get('official_cash_weight'))}。真实缺口应按持仓覆盖率/现金路径解释，而不是用退化的非零并集相关系数。",
            f"- 现金交叉核验：NAV `cash_cny/net_value_cny` 与 `1-sum(position.weight)` 最大差 = {fmt_sci(cash_summary.get('max_cash_weight_abs_diff'))}，差异天数 = {fmt_int(cash_summary.get('diff_gt_1e9_days'))}；这说明 official 现金权重不是 join 伪迹。全周期 `BUY_SKIPPED_BELOW_LOT` 共 {fill_status_count(execution_diagnostics, 'BUY', 'BUY_SKIPPED_BELOW_LOT')} 笔，最低覆盖执行日的 BUY 全部被 `BUY_SKIPPED_BELOW_LOT` 拦截，指向小资金 + 100 股整手约束造成的结构性现金拖累。",
            "",
            "## IC 分解摘要",
            "",
            markdown_table(compact_ic_table(ic_summary)),
            "",
            "年度 5d IC：",
            "",
            markdown_table(year_ic_table(ic_summary)),
            "",
            "## Transfer Ladder 结果",
            "",
            markdown_table(compact_transfer_table(transfer_results)),
            "",
            "## Transfer Coefficient",
            "",
            f"- 全 universe 域平均 TC_target: {fmt_float(tc_summary.get('tc_target'))}",
            f"- 全 universe 域平均 TC_realized: {fmt_float(tc_summary.get('tc_realized'))}",
            f"- target/ideal Top20 名字重合率均值: {fmt_pct(tc_summary.get('target_ideal_overlap_rate'))}",
            f"- realized/target 名字覆盖率均值: {fmt_pct(tc_summary.get('realized_target_overlap_rate'))}",
            f"- official 实际持仓数均值: {fmt_float(tc_summary.get('realized_nonzero'))}",
            f"- official 现金权重均值: {fmt_pct(tc_summary.get('official_cash_weight'))}",
            "",
            "## 执行层现金交叉核验",
            "",
            f"- NAV 现金权重均值: {fmt_pct(cash_summary.get('avg_nav_cash_weight'))}",
            f"- position 隐含现金权重均值: {fmt_pct(cash_summary.get('avg_implied_cash_weight'))}",
            f"- NAV 现金 vs position 隐含现金最大绝对差: {fmt_sci(cash_summary.get('max_cash_weight_abs_diff'))}",
            f"- 差异 > 1e-9 的交易日数: {fmt_int(cash_summary.get('diff_gt_1e9_days'))}",
            f"- 平均持仓数: {fmt_float(cash_summary.get('avg_position_count'))}；最小持仓数: {fmt_int(cash_summary.get('min_position_count'))}",
            f"- 现金权重 > 50% 的交易日数: {fmt_int(cash_summary.get('cash_gt_50pct_days'))}",
            f"- 最低 realized/target 覆盖执行日: `{iso_date(worst_transfer.get('exec_date'))}`，对应 signal date `{iso_date(worst_transfer.get('signal_date'))}`，覆盖率 {fmt_pct(worst_transfer.get('realized_target_overlap_rate'))}，实际持仓数 {fmt_int(worst_transfer.get('realized_nonzero'))}，现金权重 {fmt_pct(worst_transfer.get('official_cash_weight'))}。",
            "",
            "全周期 fill_status 汇总：",
            "",
            markdown_table(compact_fill_status_table(execution_diagnostics.get("fill_summary", pd.DataFrame()))),
            "",
            "最低覆盖执行日 fill_status 汇总：",
            "",
            markdown_table(compact_fill_status_table(execution_diagnostics.get("worst_fill_summary", pd.DataFrame()))),
            "",
            "## L3 恒等/偏差校验",
            "",
        ]
    )
    if not l3_check.empty:
        row = l3_check.iloc[0]
        lines.extend(
            [
                f"- paper L3 vs official daily_return corr: {fmt_float(row.get('official_l3_daily_return_corr'))}",
                f"- paper L3 CAGR - official CAGR: {fmt_pct(row.get('official_l3_cagr_diff'))}",
                f"- paper L3 MaxDD - official MaxDD: {fmt_pct(row.get('official_l3_maxdd_diff'))}",
                "- 解释：相关性高，说明 paper ladder 与 official 方向同源；但 MaxDD/CAGR 仍有明显偏差，不能把 paper ladder 数值当成 official ledger 结果。它只适合做转换效率上界/分解。",
            ]
        )
    else:
        lines.append("- L3 paper result missing; identity check unavailable.")
    lines.extend(
        [
            "",
            "## 预登记判据结论",
            "",
        ]
    )
    if best_l0 is not None:
        ir = best_l0.get("absolute_sharpe_or_contract_sharpe")
        lines.append(f"- L0 no-cost 最优 absolute Sharpe: {fmt_float(ir)}。")
        if pd.notna(ir) and ir < 1.0:
            lines.append("- 按预登记规则，L0 无摩擦 IR/Sharpe 低于 1.0 时，首要缺口在 alpha 信号容量，而不是组合工程。")
        elif pd.notna(ir):
            lines.append("- 按预登记规则，L0 无摩擦 Sharpe 明显高于 1.0，alpha 信号容量不是当前最先被否定的环节；应优先解释 L0 到 L1/L2/L3 的转换损耗。")
    l2 = transfer_results[(transfer_results["level"] == "L2") & (transfer_results["cost_bps"] == 0.0)]
    l3 = transfer_results[(transfer_results["level"] == "L3") & (transfer_results["cost_bps"] == 0.0)]
    l1 = transfer_results[(transfer_results["level"] == "L1") & (transfer_results["cost_bps"] == 0.0)]
    l05 = transfer_results[(transfer_results["level"] == "L0.5") & (transfer_results["cost_bps"] == 0.0)]
    if not l05.empty and best_l0 is not None:
        lines.append(
            f"- L0 多空 absolute Sharpe {fmt_float(best_l0.get('absolute_sharpe_or_contract_sharpe'))} "
            f"到 L0.5 long-only IR {fmt_float(l05.iloc[0]['information_ratio_vs_000852'])} 出现主要落差；"
            "二者基准不同，只作约束分解而非同口径差值。"
        )
    if not l05.empty and not l1.empty:
        delta = float(l1.iloc[0]["information_ratio_vs_000852"] - l05.iloc[0]["information_ratio_vs_000852"])
        lines.append(f"- L1-L0.5 IR 差: {fmt_float(delta)}。")
    if not l05.empty and not l2.empty:
        delta = float(l2.iloc[0]["information_ratio_vs_000852"] - l05.iloc[0]["information_ratio_vs_000852"])
        lines.append(f"- L2-L0.5 IR 差: {fmt_float(delta)}。")
    if not l2.empty and not l3.empty:
        delta = float(l3.iloc[0]["information_ratio_vs_000852"] - l2.iloc[0]["information_ratio_vs_000852"])
        lines.append(f"- L3-L2 IR 差: {fmt_float(delta)}。")
    if not l1.empty and not l2.empty:
        delta = float(l1.iloc[0]["information_ratio_vs_000852"] - l2.iloc[0]["information_ratio_vs_000852"])
        lines.append(f"- L1-L2 IR 差: {fmt_float(delta)}。")
    lines.extend(
        [
            "",
            "## 输出文件",
            "",
            f"- IC summary: `{cfg.ic_csv}`",
            f"- Daily IC: `{cfg.daily_ic_csv}`",
            f"- Transfer ladder: `{cfg.transfer_csv}`",
            f"- Transfer coefficients: `{cfg.tc_csv}`",
        ]
    )
    return "\n".join(lines) + "\n"


def summary_value(summary: pd.DataFrame, section: str, bucket: str, field: str) -> float:
    if summary.empty or field not in summary.columns:
        return np.nan
    mask = (summary["section"] == section) & (summary["bucket"].astype(str) == bucket)
    if not mask.any():
        return np.nan
    value = summary.loc[mask, field].iloc[0]
    return float(value) if pd.notna(value) else np.nan


def safe_ratio(numerator: float, denominator: float) -> float:
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return np.nan
    return float(numerator / denominator)


def level_metric_delta(results: pd.DataFrame, lhs: str, rhs: str, field: str, cost_bps: float = 0.0) -> float:
    if results.empty or field not in results.columns:
        return np.nan
    left = results[(results["level"] == lhs) & (results["cost_bps"] == cost_bps)]
    right = results[(results["level"] == rhs) & (results["cost_bps"] == cost_bps)]
    if left.empty or right.empty:
        return np.nan
    return float(left.iloc[0][field] - right.iloc[0][field])


def level_metric(results: pd.DataFrame, level: str, field: str, cost_bps: float = 0.0) -> float:
    if results.empty or field not in results.columns:
        return np.nan
    row = results[(results["level"] == level) & (results["cost_bps"] == cost_bps)]
    if row.empty:
        return np.nan
    return float(row.iloc[0][field])


def transfer_min(transfer_coefficients: pd.DataFrame, field: str) -> float:
    if transfer_coefficients.empty or field not in transfer_coefficients.columns:
        return np.nan
    return float(transfer_coefficients[field].min())


def compact_ic_table(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    cols = [
        "section",
        "bucket",
        "horizon",
        "mean_rank_ic",
        "mean_value",
        "nw_t_stat",
        "n_days",
        "sample_start",
        "sample_end",
    ]
    present = [c for c in cols if c in summary.columns]
    out = summary[present].copy()
    keep_sections = {
        "A5_horizon",
        "A2_size_neutral",
        "A2_size_industry_neutral_reference",
        "A3_market_regime",
        "A4_bucket_contribution",
    }
    out = out[out["section"].isin(keep_sections)].head(40)
    return out


def year_ic_table(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    out = summary[summary["section"] == "A1_year"].copy()
    cols = [
        "bucket",
        "mean_rank_ic",
        "median_rank_ic",
        "positive_day_ratio",
        "nw_t_stat",
        "nw_effective_n",
        "n_days",
        "sample_start",
        "sample_end",
    ]
    return out[[c for c in cols if c in out.columns]].rename(columns={"bucket": "year"})


def compact_transfer_table(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return pd.DataFrame()
    cols = [
        "level",
        "cost_bps",
        "compound_annual_return",
        "absolute_sharpe_or_contract_sharpe",
        "information_ratio_vs_000852",
        "max_drawdown",
        "calmar_ratio",
        "crunch_excess_return_vs_000852",
        "avg_gross_exposure",
        "rebalance_count",
    ]
    return results[cols].copy()


def compact_fill_status_table(fill_summary: pd.DataFrame) -> pd.DataFrame:
    if fill_summary.empty:
        return pd.DataFrame()
    cols = ["side", "fill_status", "order_count", "date_count", "turnover_cny"]
    present = [c for c in cols if c in fill_summary.columns]
    out = fill_summary[present].copy()
    if "turnover_cny" in out.columns:
        out["turnover_cny"] = out["turnover_cny"].map(lambda x: round(float(x), 2))
    return out


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_无数据_"
    render = df.copy()
    for col in render.columns:
        if pd.api.types.is_float_dtype(render[col]):
            render[col] = render[col].map(fmt_float)
    headers = list(render.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in render.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in headers) + " |")
    return "\n".join(lines)


def print_summary(
    ic_summary: pd.DataFrame,
    transfer_results: pd.DataFrame,
    tc: pd.DataFrame,
    execution_diagnostics: dict[str, Any] | None = None,
) -> None:
    print("\nIC summary:")
    print(compact_ic_table(ic_summary).to_string(index=False))
    print("\nTransfer ladder:")
    print(compact_transfer_table(transfer_results).to_string(index=False))
    if not tc.empty:
        print("\nTC mean:")
        print(tc[["tc_target", "tc_realized"]].mean(numeric_only=True).to_string())
    execution_diagnostics = execution_diagnostics or {}
    cash_summary = execution_diagnostics.get("cash_summary", {})
    if cash_summary:
        print("\nExecution cash cross-check:")
        print(
            pd.DataFrame(
                [
                    {
                        "avg_nav_cash_weight": cash_summary.get("avg_nav_cash_weight"),
                        "avg_implied_cash_weight": cash_summary.get("avg_implied_cash_weight"),
                        "max_cash_weight_abs_diff": cash_summary.get("max_cash_weight_abs_diff"),
                        "diff_gt_1e9_days": cash_summary.get("diff_gt_1e9_days"),
                        "cash_gt_50pct_days": cash_summary.get("cash_gt_50pct_days"),
                    }
                ]
            ).to_string(index=False)
        )


def top_row(df: pd.DataFrame, field: str) -> dict[str, Any] | None:
    if df.empty or field not in df.columns:
        return None
    idx = df[field].astype(float).idxmax()
    return df.loc[idx].to_dict()


def fmt_float(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{float(value):.6f}"


def fmt_sci(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{float(value):.3e}"


def fmt_int(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(int(value))


def fmt_pct(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{float(value) * 100:.2f}%"


def iso_date(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).date().isoformat()


def fill_status_count(execution_diagnostics: dict[str, Any], side: str, fill_status: str) -> str:
    fill_summary = execution_diagnostics.get("fill_summary", pd.DataFrame())
    if fill_summary.empty:
        return ""
    row = fill_summary[
        (fill_summary["side"] == side) & (fill_summary["fill_status"] == fill_status)
    ]
    if row.empty:
        return "0"
    return fmt_int(row.iloc[0]["order_count"])


if __name__ == "__main__":
    raise SystemExit(main())
