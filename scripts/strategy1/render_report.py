#!/usr/bin/env python3
"""Strategy 1 backtest report renderer (v2 — Chinese report with attribution).

Reads metrics from BigQuery ADS tables, renders Chinese Markdown + HTML report,
generates CSV attachments (trades/positions/NAV/benchmark), evidence pack JSON,
optional AI diagnosis, and PNG charts. Uploads to GCS or writes local mirror.

Usage:
    python scripts/strategy1/render_report.py \
        --project data-aquarium \
        --backtest-id bt_s1_bqml_20260601_01 \
        --run-id s1_bqml_20260601_01 \
        --artifact-base-uri gs://ashare-artifacts/reports/strategy1 \
        --local-mirror-root reports/strategy1 \
        --skip-gcs-upload

Requirements: google-cloud-bigquery, google-cloud-storage, matplotlib, pandas, requests, db-dtypes
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import mimetypes
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import matplotlib
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import matplotlib.ticker as mticker
    import pandas as pd
    import requests as http_requests
    from google.cloud import bigquery, storage
except ImportError as e:
    print(f"Missing dependency: {e}.", file=sys.stderr)
    print("Install: pip install google-cloud-bigquery google-cloud-storage matplotlib pandas requests db-dtypes",
          file=sys.stderr)
    sys.exit(1)

# ── Chinese font setup (before any plt.subplots) ──────────────────────────────
try:
    import matplotlib.font_manager as fm
    _available_fonts = {f.name for f in fm.fontManager.ttflist}
    for _candidate in (
        "SimHei", "PingFang SC", "Heiti SC", "Noto Sans CJK SC", "Noto Sans CJK JP",
        "Noto Sans CJK TC", "Noto Sans CJK HK", "Noto Sans CJK KR",
        "Noto Serif CJK SC", "Noto Serif CJK JP",
        "WenQuanYi Micro Hei", "Microsoft YaHei", "STHeiti",
    ):
        if _candidate in _available_fonts:
            matplotlib.rcParams["font.sans-serif"] = [_candidate] + matplotlib.rcParams.get("font.sans-serif", [])
            break
    matplotlib.rcParams["axes.unicode_minus"] = False
except Exception:
    pass

# ── Constants ─────────────────────────────────────────────────────────────────
REPORT_VERSION = "strategy1_zh_report_v2"
EVIDENCE_SCHEMA_VERSION = "strategy1_report_evidence_v1"

ASSESSMENT_BENCHMARK = {"sec_code": "000852.SH", "name": "中证1000"}
DISPLAY_BENCHMARK = {"sec_code": "000300.SH", "name": "沪深300"}
AUXILIARY_BENCHMARKS = [{"sec_code": "000905.SH", "name": "中证500"}]

ALL_BENCHMARKS = [ASSESSMENT_BENCHMARK, DISPLAY_BENCHMARK] + AUXILIARY_BENCHMARKS

DIAGNOSIS_THRESHOLDS = {
    "max_drawdown_trigger": -0.15,
    "rolling_loss_trigger": -0.08,
    "cost_erosion_ratio_trigger": 0.2,
}

COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]


# ── CLI ───────────────────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(description="策略 1 回测报告渲染器")
    p.add_argument("--project", required=True, help="GCP project id")
    p.add_argument("--backtest-id", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--strategy-id", default="ml_pv_clf_v0")
    p.add_argument("--artifact-base-uri", required=True, help="gs://bucket/path")
    p.add_argument("--local-mirror-root", default="reports/strategy1")
    p.add_argument("--skip-gcs-upload", action="store_true",
                   help="Skip GCS upload; write local-only artifacts (no report_uri)")
    p.add_argument("--ai-analysis-mode", default="auto",
                   choices=["auto", "off", "evidence_only", "llm"])
    p.add_argument("--ai-timeout-seconds", type=int, default=60)
    p.add_argument("--ai-max-retries", type=int, default=2)
    p.add_argument("--ai-provider", default="openai",
                   choices=["openai", "http"],
                   help="LLM provider for AI diagnosis")
    return p.parse_args()


# ── Credential helpers ────────────────────────────────────────────────────────
def _gcloud_token_credentials():
    import subprocess
    import google.oauth2.credentials
    try:
        token = subprocess.check_output(
            ["gcloud", "auth", "print-access-token"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return None
    return google.oauth2.credentials.Credentials(token) if token else None


def make_bq_client(project: str) -> bigquery.Client:
    try:
        return bigquery.Client(project=project)
    except Exception as adc_err:
        creds = _gcloud_token_credentials()
        if creds is None:
            raise adc_err
        return bigquery.Client(project=project, credentials=creds)


def make_storage_client(project: str) -> storage.Client:
    try:
        return storage.Client(project=project)
    except Exception as adc_err:
        creds = _gcloud_token_credentials()
        if creds is None:
            raise adc_err
        return storage.Client(project=project, credentials=creds)


# ── BigQuery helpers ──────────────────────────────────────────────────────────
def bq_query(client: bigquery.Client, sql: str, params: list | None = None) -> pd.DataFrame:
    cfg = bigquery.QueryJobConfig(query_parameters=params or [])
    return client.query(sql, job_config=cfg).to_dataframe()


# ── Data fetching ─────────────────────────────────────────────────────────────
def fetch_summary(client: bigquery.Client, project: str, backtest_id: str) -> dict:
    sql = f"""
    SELECT bs.*
    FROM `{project}.ashare_ads.ads_backtest_performance_summary` AS bs
    WHERE bs.backtest_id = @bid
    LIMIT 1
    """
    rows = bq_query(client, sql, [bigquery.ScalarQueryParameter("bid", "STRING", backtest_id)])
    if rows.empty:
        raise SystemExit(f"No summary for backtest_id={backtest_id}")
    return rows.iloc[0].to_dict()


def fetch_nav(client: bigquery.Client, project: str, backtest_id: str,
              start_date: str, end_date: str) -> pd.DataFrame:
    sql = f"""
    SELECT n.trade_date, n.nav, n.daily_return, n.benchmark_return,
           n.excess_return, n.turnover_cny, n.cost_cny, n.cash_cny,
           n.net_value_cny, n.gross_exposure
    FROM `{project}.ashare_ads.ads_backtest_nav_daily` AS n
    WHERE n.backtest_id = @bid
      AND n.trade_date BETWEEN @sd AND @ed
    ORDER BY n.trade_date
    """
    df = bq_query(client, sql, [
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])
    if df.empty:
        raise SystemExit(f"No NAV data for backtest_id={backtest_id}")
    # Canonicalize: fail fast if ADS has inconsistent duplicates (same date,
    # different nav/cash/etc.); silently drop exact duplicates.
    dups = df[df.duplicated("trade_date", keep=False)]
    if not dups.empty:
        dup_dates = dups["trade_date"].unique()
        for dt in dup_dates:
            chunk = dups[dups["trade_date"] == dt]
            if chunk.drop(columns=["trade_date"]).drop_duplicates().shape[0] > 1:
                raise SystemExit(
                    f"NAV table has inconsistent duplicates for trade_date={dt} "
                    f"(backtest_id={backtest_id}). Fix ADS data before rendering."
                )
        df = df.drop_duplicates("trade_date", keep="first")
    return df


def fetch_display_benchmark(client: bigquery.Client, project: str,
                            sec_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    sql = f"""
    SELECT idx.trade_date, idx.close, idx.pct_chg
    FROM `{project}.ashare_dwd.dwd_index_eod` AS idx
    WHERE idx.sec_code = @sc
      AND idx.trade_date BETWEEN @sd AND @ed
    ORDER BY idx.trade_date
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("sc", "STRING", sec_code),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])


def fetch_trades(client: bigquery.Client, project: str, backtest_id: str,
                 start_date: str, end_date: str) -> pd.DataFrame:
    sql = f"""
    SELECT t.trade_date, t.sec_code, t.side, t.planned_shares, t.filled_shares,
           t.fill_price, t.turnover_cny, t.fee_cny, t.tax_cny, t.slippage_cny,
           t.cash_effect_cny, t.fill_status
    FROM `{project}.ashare_ads.ads_backtest_trade_daily` AS t
    WHERE t.backtest_id = @bid
      AND t.trade_date BETWEEN @sd AND @ed
    ORDER BY t.trade_date, t.sec_code
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])


def fetch_enriched_buy_trades(client: bigquery.Client, project: str,
                              run_id: str, backtest_id: str,
                              start_date: str, end_date: str) -> pd.DataFrame:
    sql = f"""
    SELECT t.trade_date, sig.cal_date AS signal_date, t.sec_code, t.fill_price,
           pred.score, pred.rank_raw
    FROM `{project}.ashare_ads.ads_backtest_trade_daily` AS t
    JOIN `{project}.ashare_dim.dim_trade_calendar` AS exec_cal
      ON exec_cal.exchange = 'SSE'
     AND exec_cal.is_open = 1
     AND exec_cal.cal_date = t.trade_date
    JOIN `{project}.ashare_dim.dim_trade_calendar` AS sig
      ON sig.exchange = 'SSE'
     AND sig.is_open = 1
     AND sig.trade_date_seq = exec_cal.trade_date_seq - 1
    JOIN `{project}.ashare_ads.ads_model_prediction_daily` AS pred
      ON pred.sec_code = t.sec_code
     AND pred.predict_date = sig.cal_date
     AND pred.run_id = @rid
    WHERE t.backtest_id = @bid
      AND t.side = 'BUY'
      AND t.fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
      AND t.trade_date BETWEEN @sd AND @ed
      AND pred.predict_date BETWEEN DATE_SUB(@sd, INTERVAL 10 DAY) AND @ed
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("rid", "STRING", run_id),
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])


def fetch_position_weights(client: bigquery.Client, project: str,
                           backtest_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    sql = f"""
    SELECT p.trade_date, p.sec_code, p.weight
    FROM `{project}.ashare_ads.ads_backtest_position_daily` AS p
    WHERE p.backtest_id = @bid
      AND p.trade_date BETWEEN @sd AND @ed
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])


def fetch_positions(client: bigquery.Client, project: str,
                    backtest_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    sql = f"""
    SELECT p.trade_date, p.sec_code, p.shares, p.close, p.market_value_cny, p.weight
    FROM `{project}.ashare_ads.ads_backtest_position_daily` AS p
    WHERE p.backtest_id = @bid
      AND p.trade_date BETWEEN @sd AND @ed
    ORDER BY p.trade_date, p.sec_code
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])


def fetch_predictions(client: bigquery.Client, project: str,
                      run_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    sql = f"""
    SELECT pred.predict_date, pred.sec_code, pred.score, pred.rank_raw, pred.rank_pct
    FROM `{project}.ashare_ads.ads_model_prediction_daily` AS pred
    WHERE pred.run_id = @rid
      AND pred.predict_date BETWEEN @sd AND @ed
    ORDER BY pred.predict_date, pred.rank_raw
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("rid", "STRING", run_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])


def fetch_portfolio_targets(client: bigquery.Client, project: str,
                            strategy_id: str, run_id: str,
                            start_date: str, end_date: str) -> pd.DataFrame:
    sql = f"""
    SELECT pt.rebalance_date, pt.sec_code, pt.target_weight
    FROM `{project}.ashare_ads.ads_portfolio_target_daily` AS pt
    WHERE pt.strategy_id = @sid
      AND pt.run_id = @rid
      AND pt.rebalance_date BETWEEN @sd AND @ed
    ORDER BY pt.rebalance_date, pt.target_weight DESC
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("sid", "STRING", strategy_id),
        bigquery.ScalarQueryParameter("rid", "STRING", run_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])


def fetch_model_info(client: bigquery.Client, project: str,
                     strategy_id: str, run_id: str) -> dict:
    sql = f"""
    SELECT reg.model_id, reg.model_params_json, reg.metrics_json, reg.model_uri
    FROM `{project}.ashare_ads.ads_model_registry` AS reg
    WHERE reg.strategy_id = @sid
      AND reg.status = 'selected'
      AND JSON_VALUE(reg.model_params_json, '$.run_id') = @rid
    ORDER BY reg.created_at DESC
    LIMIT 1
    """
    rows = bq_query(client, sql, [
        bigquery.ScalarQueryParameter("sid", "STRING", strategy_id),
        bigquery.ScalarQueryParameter("rid", "STRING", run_id),
    ])
    return rows.iloc[0].to_dict() if not rows.empty else {}


# ── Evidence computation ──────────────────────────────────────────────────────
def compute_drawdown_events(nav_df: pd.DataFrame) -> list[dict]:
    nav_series = nav_df.set_index("trade_date")["nav"]
    cummax = nav_series.cummax()
    dd = nav_series / cummax - 1
    events = []
    in_dd = False
    peak_date = peak_val = trough_date = trough_val = None

    for dt, val in nav_series.items():
        cm = cummax.loc[dt]
        if val >= cm:
            if in_dd and trough_val is not None:
                dd_pct = trough_val / peak_val - 1
                if dd_pct < -0.01:
                    td_count = len(nav_series.loc[peak_date:trough_date])
                    events.append({
                        "peak_date": str(peak_date),
                        "trough_date": str(trough_date),
                        "drawdown_pct": round(dd_pct, 6),
                        "trading_days": int(td_count),
                        "peak_nav": round(peak_val, 6),
                        "trough_nav": round(trough_val, 6),
                    })
            in_dd = False
            peak_date = dt
            peak_val = val
        else:
            if not in_dd:
                in_dd = True
                trough_date = dt
                trough_val = val
            elif val < trough_val:
                trough_date = dt
                trough_val = val

    if in_dd and trough_val is not None:
        dd_pct = trough_val / peak_val - 1
        if dd_pct < -0.01:
            td_count = len(nav_series.loc[peak_date:trough_date])
            events.append({
                "peak_date": str(peak_date),
                "trough_date": str(trough_date),
                "drawdown_pct": round(dd_pct, 6),
                "trading_days": int(td_count),
                "peak_nav": round(peak_val, 6),
                "trough_nav": round(trough_val, 6),
            })

    events.sort(key=lambda e: e["drawdown_pct"])
    return events


def compute_rolling_loss_events(nav_df: pd.DataFrame) -> list[dict]:
    events = []
    ret = nav_df.set_index("trade_date")["daily_return"].fillna(0)
    for window in (5, 10, 20):
        roll = ret.rolling(window).sum()
        if roll.empty:
            continue
        min_val = roll.min()
        if pd.isna(min_val):
            continue
        min_date = roll.idxmin()
        loc = roll.index.get_loc(min_date)
        if isinstance(loc, slice):
            start_idx = max(0, loc.start - window + 1)
        else:
            start_idx = max(0, int(loc) - window + 1)
        events.append({
            "window": window,
            "worst_return": round(float(min_val), 6),
            "end_date": str(min_date),
            "start_date": str(roll.index[start_idx]),
        })
    return events


def compute_loss_attribution(client: bigquery.Client, project: str,
                             backtest_id: str, pos_df: pd.DataFrame,
                             start_date: str, end_date: str,
                             top_n: int = 20) -> tuple[list[dict], float]:
    if pos_df.empty:
        return [], 1.0

    pos_codes = pos_df["sec_code"].unique().tolist()
    if not pos_codes:
        return [], 1.0

    sql = f"""
    SELECT px.sec_code, px.trade_date, px.ret_1d
    FROM `{project}.ashare_dwd.dwd_stock_eod_price` AS px
    WHERE px.trade_date BETWEEN @sd AND @ed
      AND px.sec_code IN UNNEST(@codes)
    ORDER BY px.sec_code, px.trade_date
    """
    price_df = bq_query(client, sql, [
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
        bigquery.ArrayQueryParameter("codes", "STRING", pos_codes),
    ])

    if price_df.empty:
        return [], 0.0

    merged = pos_df.merge(
        price_df[["sec_code", "trade_date", "ret_1d"]],
        on=["sec_code", "trade_date"],
        how="left",
    )
    merged["contribution"] = merged["weight"] * merged["ret_1d"].fillna(0)

    total_pos_days = len(merged)
    covered_days = merged["ret_1d"].notna().sum()
    coverage_ratio = float(covered_days / total_pos_days) if total_pos_days > 0 else 0.0

    by_stock = (
        merged.groupby("sec_code")
        .agg(
            total_contribution=("contribution", "sum"),
            max_weight=("weight", "max"),
            trade_count=("trade_date", "count"),
        )
        .reset_index()
    )
    losers = by_stock[by_stock["total_contribution"] < 0].nsmallest(top_n, "total_contribution")

    result = []
    for _, row in losers.iterrows():
        result.append({
            "sec_code": row["sec_code"],
            "total_contribution": round(float(row["total_contribution"]), 6),
            "max_weight": round(float(row["max_weight"]), 6),
            "trade_count": int(row["trade_count"]),
        })

    return result, round(coverage_ratio, 6)


def compute_cost_breakdown(client: bigquery.Client, project: str,
                           backtest_id: str, start_date: str, end_date: str) -> dict:
    sql = f"""
    SELECT
      SUM(t.fee_cny - t.tax_cny) AS total_commission_cny,
      SUM(t.tax_cny) AS total_tax_cny,
      SUM(t.slippage_cny) AS total_slippage_cny,
      SUM(t.fee_cny + t.slippage_cny) AS total_economic_cost_cny
    FROM `{project}.ashare_ads.ads_backtest_trade_daily` AS t
    WHERE t.backtest_id = @bid
      AND t.fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
      AND t.trade_date BETWEEN @sd AND @ed
    """
    df = bq_query(client, sql, [
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])
    if df.empty:
        return {"total_commission_cny": 0.0, "total_tax_cny": 0.0,
                "total_slippage_cny": 0.0, "total_economic_cost_cny": 0.0}
    r = df.iloc[0]
    return {
        "total_commission_cny": round(float(r["total_commission_cny"] or 0), 2),
        "total_tax_cny": round(float(r["total_tax_cny"] or 0), 2),
        "total_slippage_cny": round(float(r["total_slippage_cny"] or 0), 2),
        "total_economic_cost_cny": round(float(r["total_economic_cost_cny"] or 0), 2),
    }


def compute_execution_diagnostics(client: bigquery.Client, project: str,
                                  backtest_id: str, start_date: str, end_date: str) -> dict:
    sql = f"""
    SELECT
      COUNTIF(t.side = 'BUY' AND t.fill_status IN ('FILLED', 'FILLED_SCALED_CASH')) AS buy_filled,
      COUNTIF(t.side = 'BUY' AND t.fill_status = 'FILLED_SCALED_CASH') AS buy_scaled_cash,
      COUNTIF(t.side = 'BUY' AND t.fill_status IN ('BUY_SKIPPED_UNTRADABLE', 'SKIPPED_CASH_INSUFFICIENT', 'SKIPPED_MIN_NOTIONAL')) AS buy_skip,
      COUNTIF(t.side = 'SELL' AND t.fill_status = 'FILLED') AS sell_filled,
      COUNTIF(t.side = 'SELL' AND t.fill_status IN ('SELL_SKIPPED_UNTRADABLE', 'PENDING_SELL_CARRY')) AS sell_skip,
      COUNTIF(t.fill_status = 'PENDING_SELL_CARRY') AS pending_sell_carry,
      COUNTIF(t.fill_status = 'CANCELLED_BY_NETTING') AS cancelled_by_netting,
      COUNTIF(t.fill_status = 'NOOP_ALREADY_TARGET') AS noop_already_target
    FROM `{project}.ashare_ads.ads_backtest_trade_daily` AS t
    WHERE t.backtest_id = @bid
      AND t.trade_date BETWEEN @sd AND @ed
    """
    diag = bq_query(client, sql, [
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])
    d = diag.iloc[0] if not diag.empty else {}

    nav_sql = f"""
    SELECT MIN(n.cash_cny) AS min_cash, MAX(n.gross_exposure) AS max_gross
    FROM `{project}.ashare_ads.ads_backtest_nav_daily` AS n
    WHERE n.backtest_id = @bid AND n.trade_date BETWEEN @sd AND @ed
    """
    nav_d = bq_query(client, nav_sql, [
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])
    n = nav_d.iloc[0] if not nav_d.empty else {}

    return {
        "buy_filled_count": int(d.get("buy_filled", 0) or 0),
        "buy_scaled_cash_count": int(d.get("buy_scaled_cash", 0) or 0),
        "buy_skip_count": int(d.get("buy_skip", 0) or 0),
        "sell_filled_count": int(d.get("sell_filled", 0) or 0),
        "sell_skip_count": int(d.get("sell_skip", 0) or 0),
        "pending_sell_carry_count": int(d.get("pending_sell_carry", 0) or 0),
        "cancelled_by_netting_count": int(d.get("cancelled_by_netting", 0) or 0),
        "noop_already_target_count": int(d.get("noop_already_target", 0) or 0),
        "min_cash_cny": round(float(n.get("min_cash", 0) or 0), 2),
        "max_gross_exposure": round(float(n.get("max_gross", 0) or 0), 6),
    }


def compute_model_signal_diagnostics(predictions_df: pd.DataFrame) -> dict:
    if predictions_df.empty:
        return {"prediction_count": 0, "score_avg": None, "score_std": None}
    scores = predictions_df["score"].dropna()
    result = {
        "prediction_count": len(predictions_df),
        "score_avg": round(float(scores.mean()), 6) if len(scores) > 0 else None,
        "score_std": round(float(scores.std()), 6) if len(scores) > 1 else None,
    }
    for pct in (10, 25, 50, 75, 90):
        result[f"p{pct}_score"] = round(float(scores.quantile(pct / 100)), 6) if len(scores) > 0 else None
    top1 = predictions_df[predictions_df["rank_raw"] == 1].head(5)
    if not top1.empty:
        result["top_ranked_samples"] = [
            {"date": str(r["predict_date"]), "sec_code": r["sec_code"],
             "score": round(float(r["score"]), 6)}
            for _, r in top1.iterrows()
        ]
    return result


def get_loss_window_trades(client: bigquery.Client, project: str,
                           backtest_id: str, start_date: str, end_date: str) -> list[dict]:
    sql = f"""
    SELECT t.trade_date, t.sec_code, t.side, t.filled_shares, t.fill_price,
           t.turnover_cny, t.cash_effect_cny, t.fill_status
    FROM `{project}.ashare_ads.ads_backtest_trade_daily` AS t
    WHERE t.backtest_id = @bid
      AND t.fill_status IN ('FILLED', 'FILLED_SCALED_CASH')
      AND t.trade_date BETWEEN @sd AND @ed
    ORDER BY t.trade_date
    LIMIT 50
    """
    df = bq_query(client, sql, [
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])
    return [
        {"trade_date": str(r["trade_date"]), "sec_code": r["sec_code"],
         "side": r["side"], "filled_shares": float(r["filled_shares"] or 0),
         "fill_price": round(float(r["fill_price"] or 0), 4),
         "turnover_cny": round(float(r["turnover_cny"] or 0), 2),
         "cash_effect_cny": round(float(r["cash_effect_cny"] or 0), 2),
         "fill_status": r["fill_status"]}
        for _, r in df.iterrows()
    ] if not df.empty else []


def determine_diagnosis_triggers(summary: dict, nav_df: pd.DataFrame,
                                 evidence: dict) -> tuple[bool, list[str]]:
    triggers = []
    total_return = float(summary.get("total_return", 0) or 0)
    m = json.loads(summary.get("metrics_json") or "{}")
    max_dd = float(m.get("max_drawdown", 0) or 0)

    bench_ret = evidence.get("performance_summary", {}).get("assessment_benchmark", {}).get("total_return", 0)
    if total_return < bench_ret:
        triggers.append("策略累计收益低于评估主基准")
    disp_ret = evidence.get("performance_summary", {}).get("display_benchmark", {}).get("total_return", 0)
    if total_return < disp_ret:
        triggers.append("策略累计收益低于展示对比基准")
    if total_return < 0:
        triggers.append("策略累计收益为负")
    if max_dd <= DIAGNOSIS_THRESHOLDS["max_drawdown_trigger"]:
        triggers.append(f"最大回撤 {max_dd:.2%} <= {DIAGNOSIS_THRESHOLDS['max_drawdown_trigger']:.0%}")

    for ev in evidence.get("fast_loss_events", []):
        if ev.get("worst_return", 0) <= DIAGNOSIS_THRESHOLDS["rolling_loss_trigger"]:
            triggers.append(f"{ev['window']}日滚动亏损 {ev['worst_return']:.2%}")
            break

    cost = evidence.get("cost_breakdown", {})
    total_cost = cost.get("total_economic_cost_cny", 0)
    if total_cost > 0 and total_return < 0:
        nav_end = float(nav_df["nav"].iloc[-1]) if not nav_df.empty else 1
        loss_abs = abs(total_return) * 100000
        if loss_abs > 0 and total_cost / loss_abs >= DIAGNOSIS_THRESHOLDS["cost_erosion_ratio_trigger"]:
            triggers.append(f"成本/亏损比 >= {DIAGNOSIS_THRESHOLDS['cost_erosion_ratio_trigger']:.0%}")

    return len(triggers) > 0, triggers


def build_evidence_pack(summary: dict, nav_df: pd.DataFrame,
                        assessment_bench: pd.DataFrame,
                        display_bench: pd.DataFrame,
                        aux_benches: dict[str, pd.DataFrame],
                        trades_df: pd.DataFrame,
                        positions_df: pd.DataFrame,
                        drawdown_events: list[dict],
                        rolling_events: list[dict],
                        loss_contributors: list[dict],
                        trade_samples: list[dict],
                        cost_breakdown: dict,
                        exec_diag: dict,
                        signal_diag: dict,
                        coverage_ratio: float,
                        args) -> dict:
    m = json.loads(summary.get("metrics_json") or "{}")

    def bench_stats(bench_df: pd.DataFrame) -> dict:
        if bench_df.empty:
            return {"total_return": None, "note": "数据不可用"}
        pct = bench_df["pct_chg"].fillna(0) / 100.0
        cum = (1 + pct).cumprod()
        return {
            "total_return": round(float(cum.iloc[-1] - 1), 6),
            "annual_return": round(float(pct.mean() * 252), 6),
            "max_drawdown": round(float((cum / cum.cummax() - 1).min()), 6),
        }

    nav_dates = set(nav_df["trade_date"].astype(str))
    nav_count = len(nav_dates) or 1

    def bench_coverage_ratio(bench_df: pd.DataFrame) -> float:
        if bench_df.empty or not nav_dates:
            return 0.0
        bench_dates = set(bench_df["trade_date"].astype(str))
        return round(len(nav_dates & bench_dates) / nav_count, 4)

    bench_coverage = {ASSESSMENT_BENCHMARK["sec_code"]: bench_coverage_ratio(assessment_bench)}
    bench_coverage[DISPLAY_BENCHMARK["sec_code"]] = bench_coverage_ratio(display_bench)
    for b in AUXILIARY_BENCHMARKS:
        bench_coverage[b["sec_code"]] = bench_coverage_ratio(aux_benches.get(b["sec_code"], pd.DataFrame()))

    coverage_notes = []
    for code, ratio in bench_coverage.items():
        if 0 < ratio < 1.0:
            missing = int(nav_count * (1 - ratio))
            coverage_notes.append(f"{code} 基准覆盖 {ratio:.1%}，缺失 {missing} 个交易日")

    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "run_context": {
            "run_id": args.run_id,
            "backtest_id": args.backtest_id,
            "strategy_id": args.strategy_id,
            "model_id": summary.get("model_id"),
            "predict_start": str(summary.get("start_date", "")),
            "predict_end": str(summary.get("end_date", "")),
            "initial_capital": 100000.0,
            "cost_profile_id": m.get("cost_profile_id"),
            "assessment_benchmark": ASSESSMENT_BENCHMARK,
            "display_benchmark": DISPLAY_BENCHMARK,
            "auxiliary_benchmarks": AUXILIARY_BENCHMARKS,
            "thresholds": DIAGNOSIS_THRESHOLDS,
        },
        "performance_summary": {
            "strategy": {
                "total_return": round(float(summary.get("total_return", 0) or 0), 6),
                "annual_return": round(float(summary.get("annual_return", 0) or 0), 6),
                "annual_vol": round(float(summary.get("annual_vol", 0) or 0), 6),
                "sharpe": round(float(summary.get("sharpe", 0) or 0), 4),
                "max_drawdown": round(float(m.get("max_drawdown", 0) or 0), 6),
                "information_ratio": round(float(summary.get("information_ratio", 0) or 0), 4),
            },
            "assessment_benchmark": bench_stats(assessment_bench),
            "display_benchmark": bench_stats(display_bench),
            "auxiliary_benchmarks": {
                b["sec_code"]: bench_stats(aux_benches.get(b["sec_code"], pd.DataFrame()))
                for b in AUXILIARY_BENCHMARKS
            },
        },
        "drawdown_events": drawdown_events,
        "fast_loss_events": rolling_events,
        "loss_contributors": loss_contributors,
        "trade_samples": trade_samples,
        "cost_breakdown": cost_breakdown,
        "execution_diagnostics": exec_diag,
        "model_signal_diagnostics": signal_diag,
        "data_coverage": {
            "attribution_coverage_ratio": coverage_ratio,
            "benchmark_coverage": bench_coverage,
            "missing_fields": [],
            "notes": coverage_notes,
        },
    }


# ── AI analysis ───────────────────────────────────────────────────────────────
def run_ai_analysis(evidence: dict, args) -> dict:
    mode = args.ai_analysis_mode
    if mode == "off":
        return {"status": "off", "analysis": None}

    has_creds = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY"))

    if mode == "evidence_only":
        return build_evidence_only_analysis(evidence)
    elif mode == "llm":
        if not has_creds:
            return {"status": "failed", "error": "no_credentials",
                    "analysis": None}
        return invoke_llm(evidence, args)
    elif mode == "auto":
        if has_creds:
            result = invoke_llm(evidence, args, mode="auto")
            if result.get("status") == "success":
                return result
            result["status"] = "fallback_evidence_only"
            fallback = build_evidence_only_analysis(evidence)
            result["analysis"] = fallback.get("analysis", "")
            return result
        return build_evidence_only_analysis(evidence)
    return {"status": "off", "analysis": None}


def invoke_llm(evidence: dict, args, mode: str = "llm") -> dict:
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("LLM_MODEL", "gpt-4o")

    system_prompt = """你是一位 A 股量化策略分析师。请用中文分析以下回测证据包。

要求：
1. 只引用证据包中存在的事实（日期、股票代码、收益、成本、权重）。
2. 对证据包中没有的数据源（如新闻、公告、行业事件），必须写"当前证据不足，无法判断"。
3. 将"事实"和"推断"分段。
4. 列出关键日期、股票代码、窗口收益和贡献。
5. 输出结构：结论摘要、亏损最快的窗口、主要亏损股票、可能原因、不是原因/无法判断、下一步改进建议。"""

    evidence_json = json.dumps(evidence, ensure_ascii=False, indent=1)
    user_prompt = f"请分析以下策略回测证据包并输出中文诊断：\n\n{evidence_json}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    last_error = None
    for attempt in range(args.ai_max_retries + 1):
        try:
            resp = http_requests.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": model, "messages": messages, "temperature": 0.3, "max_tokens": 4000},
                timeout=args.ai_timeout_seconds,
            )
            if resp.status_code == 429:
                last_error = "rate_limited"
                if attempt < args.ai_max_retries:
                    time.sleep(2 ** attempt)
                    continue
                break
            if 400 <= resp.status_code < 500 and resp.status_code != 429:
                last_error = f"http_{resp.status_code}"
                break
            if resp.status_code >= 500:
                last_error = f"http_{resp.status_code}"
                if attempt < args.ai_max_retries:
                    time.sleep(2 ** attempt)
                    continue
                break

            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            evidence_hash = hashlib.sha256(
                evidence_json.encode("utf-8")).hexdigest()[:16]
            return {
                "status": "success",
                "analysis": content,
                "model": model,
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "evidence_hash": evidence_hash,
            }
        except http_requests.exceptions.Timeout:
            last_error = "timeout"
            if attempt < args.ai_max_retries:
                time.sleep(2 ** attempt)
                continue
        except Exception as e:
            last_error = str(e)[:100]
            break

    if mode == "auto":
        return {"status": "fallback_evidence_only", "error_type": last_error}
    return {"status": "failed", "error_type": last_error}


def build_evidence_only_analysis(evidence: dict) -> dict:
    ps = evidence.get("performance_summary", {})
    strat = ps.get("strategy", {})
    assess = ps.get("assessment_benchmark", {})
    lines = ["【证据摘要（规则模板生成，未调用 LLM）】", ""]

    lines.append("## 结论摘要")
    tr = strat.get("total_return", 0)
    bench_tr = assess.get("total_return", 0)
    if tr < bench_tr:
        lines.append(f"策略累计收益 {tr:.2%}，低于评估主基准（{ASSESSMENT_BENCHMARK['name']}）{bench_tr:.2%}，"
                     f"超额 {tr - bench_tr:.2%}。")
    elif tr < 0:
        lines.append(f"策略累计收益 {tr:.2%}，为负。")
    else:
        lines.append(f"策略累计收益 {tr:.2%}，优于评估主基准。")
    lines.append(f"最大回撤 {strat.get('max_drawdown', 0):.2%}，Sharpe {strat.get('sharpe', 0):.2f}。")
    lines.append("")

    dd_events = evidence.get("drawdown_events", [])
    if dd_events:
        lines.append("## 最大回撤窗口")
        for ev in dd_events[:3]:
            lines.append(f"- {ev['peak_date']} → {ev['trough_date']}: "
                         f"{ev['drawdown_pct']:.2%}，持续 {ev['trading_days']} 个交易日")
        lines.append("")

    fl_events = evidence.get("fast_loss_events", [])
    if fl_events:
        lines.append("## 快速亏损窗口")
        for ev in fl_events:
            lines.append(f"- {ev['window']}日窗口 {ev['start_date']} → {ev['end_date']}: "
                         f"{ev['worst_return']:.2%}")
        lines.append("")

    lc = evidence.get("loss_contributors", [])
    if lc:
        lines.append("## 主要亏损持仓")
        for c in lc[:10]:
            lines.append(f"- {c['sec_code']}: 贡献 {c['total_contribution']:.4f}，"
                         f"最大权重 {c['max_weight']:.2%}")
        lines.append("")

    lines.append("## 数据覆盖")
    cov = evidence.get("data_coverage", {})
    lines.append(f"- 归因覆盖率: {cov.get('attribution_coverage_ratio', 0):.1%}")
    lines.append("- 当前证据不足，无法判断外部原因（新闻/公告/行业事件）。")

    return {
        "status": "evidence_only",
        "analysis": "\n".join(lines),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }


# ── CSV generation ────────────────────────────────────────────────────────────
def build_trades_csv(trades_df: pd.DataFrame, buy_enriched: pd.DataFrame,
                     pos_weights: pd.DataFrame, targets: pd.DataFrame) -> list[list]:
    buy_map = {}
    if not buy_enriched.empty:
        for _, r in buy_enriched.iterrows():
            buy_map[(str(r["trade_date"]), r["sec_code"])] = (
                str(r.get("signal_date", "")),
                round(float(r.get("score", 0) or 0), 6),
                int(r.get("rank_raw", 0) or 0),
            )

    pw_map = {}
    if not pos_weights.empty:
        for _, r in pos_weights.iterrows():
            pw_map[(str(r["trade_date"]), r["sec_code"])] = round(float(r["weight"] or 0), 6)

    tgt_map = {}
    if not targets.empty:
        for _, r in targets.iterrows():
            tgt_map[(str(r["rebalance_date"]), r["sec_code"])] = round(float(r["target_weight"] or 0), 6)

    header = ["trade_date", "signal_date", "execution_date", "sec_code", "side", "planned_shares", "filled_shares",
              "fill_price", "turnover_cny", "fee_cny", "tax_cny", "slippage_cny",
              "cash_effect_cny", "fill_status", "score", "rank_raw",
              "target_weight", "position_weight_after"]
    rows = [header]
    for _, r in trades_df.iterrows():
        key = (str(r["trade_date"]), r["sec_code"])
        side = r["side"]
        signal_date = ""
        score_val, rank_val = "", ""
        tgt_w, pos_w = "", ""
        if side == "BUY":
            s = buy_map.get(key)
            if s:
                signal_date, score_val, rank_val = s[0], s[1], s[2]
            t = tgt_map.get((signal_date, r["sec_code"])) if signal_date else None
            if t is not None:
                tgt_w = t
        elif side == "SELL":
            p = pw_map.get(key)
            if p is not None:
                pos_w = p
        rows.append([
            key[0], signal_date, key[0], r["sec_code"], side,
            round(float(r.get("planned_shares", 0) or 0), 2),
            round(float(r.get("filled_shares", 0) or 0), 2),
            round(float(r.get("fill_price", 0) or 0), 4) if pd.notna(r.get("fill_price")) else "",
            round(float(r.get("turnover_cny", 0) or 0), 2),
            round(float(r.get("fee_cny", 0) or 0), 2),
            round(float(r.get("tax_cny", 0) or 0), 2),
            round(float(r.get("slippage_cny", 0) or 0), 2),
            round(float(r.get("cash_effect_cny", 0) or 0), 2),
            r.get("fill_status", ""),
            score_val, rank_val, tgt_w, pos_w,
        ])
    return rows


def build_positions_csv(positions_df: pd.DataFrame) -> list[list]:
    header = ["trade_date", "sec_code", "shares", "close", "market_value_cny", "weight"]
    rows = [header]
    for _, r in positions_df.iterrows():
        rows.append([
            str(r["trade_date"]), r["sec_code"],
            round(float(r.get("shares", 0) or 0), 2),
            round(float(r.get("close", 0) or 0), 4),
            round(float(r.get("market_value_cny", 0) or 0), 2),
            round(float(r.get("weight", 0) or 0), 6),
        ])
    return rows


def build_nav_csv(nav_df: pd.DataFrame) -> list[list]:
    header = ["trade_date", "nav", "cash_cny", "net_value_cny",
              "gross_exposure", "daily_return", "turnover_cny", "cost_cny"]
    rows = [header]
    for _, r in nav_df.iterrows():
        rows.append([
            str(r["trade_date"]),
            round(float(r.get("nav", 0) or 0), 6),
            round(float(r.get("cash_cny", 0) or 0), 2),
            round(float(r.get("net_value_cny", 0) or 0), 2),
            round(float(r.get("gross_exposure", 0) or 0), 6),
            round(float(r.get("daily_return", 0) or 0), 6),
            round(float(r.get("turnover_cny", 0) or 0), 2),
            round(float(r.get("cost_cny", 0) or 0), 2),
        ])
    return rows


def build_benchmark_csv(nav_df: pd.DataFrame, assessment_bench: pd.DataFrame,
                        display_bench: pd.DataFrame,
                        aux_benches: dict[str, pd.DataFrame]) -> list[list]:
    header = ["trade_date", "strategy_nav", "assessment_benchmark_nav",
              "display_benchmark_nav"] + [f"aux_{b['sec_code']}_nav" for b in AUXILIARY_BENCHMARKS]
    rows = [header]

    dates = nav_df["trade_date"].tolist()
    strat_nav = nav_df["nav"].tolist()

    def cum_nav(df: pd.DataFrame) -> dict:
        if df.empty:
            return {}
        pct = df["pct_chg"].fillna(0) / 100.0
        cum = (1 + pct).cumprod()
        return {str(d): round(float(v), 6) for d, v in zip(df["trade_date"], cum)}

    a_map = cum_nav(assessment_bench)
    d_map = cum_nav(display_bench)
    aux_maps = {b["sec_code"]: cum_nav(aux_benches.get(b["sec_code"], pd.DataFrame()))
                for b in AUXILIARY_BENCHMARKS}

    for i, dt in enumerate(dates):
        ds = str(dt)
        row = [ds, round(float(strat_nav[i]), 6),
               a_map.get(ds, ""), d_map.get(ds, "")]
        for b in AUXILIARY_BENCHMARKS:
            row.append(aux_maps.get(b["sec_code"], {}).get(ds, ""))
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[list]):
    import csv
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


# ── Charts ────────────────────────────────────────────────────────────────────
def _setup_charts():
    plt.rcParams.update({
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "figure.facecolor": "white",
    })


def plot_nav_vs_benchmark(nav_df: pd.DataFrame, assessment_bench: pd.DataFrame,
                          display_bench: pd.DataFrame,
                          aux_benches: dict[str, pd.DataFrame], out_path: Path):
    _setup_charts()
    fig, ax = plt.subplots(figsize=(14, 6))
    dates = nav_df["trade_date"]
    ax.plot(dates, nav_df["nav"], label="策略净值", linewidth=1.4, color=COLORS[0])

    def plot_bench(df, label, color, alpha=0.8):
        if df.empty:
            return
        pct = df["pct_chg"].fillna(0) / 100.0
        cum = (1 + pct).cumprod()
        ax.plot(df["trade_date"], cum, label=label, linewidth=1.0, color=color, alpha=alpha)

    plot_bench(assessment_bench, ASSESSMENT_BENCHMARK["name"], COLORS[1])
    plot_bench(display_bench, DISPLAY_BENCHMARK["name"], COLORS[2])
    for i, b in enumerate(AUXILIARY_BENCHMARKS):
        plot_bench(aux_benches.get(b["sec_code"], pd.DataFrame()), b["name"], COLORS[3 + i], alpha=0.6)

    ax.set_title("策略净值 vs 基准")
    ax.set_ylabel("净值")
    ax.legend(fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_drawdown(nav_df: pd.DataFrame, out_path: Path):
    _setup_charts()
    dd = nav_df["nav"] / nav_df["nav"].cummax() - 1
    fig, ax = plt.subplots(figsize=(14, 3.5))
    ax.fill_between(nav_df["trade_date"], dd, 0, alpha=0.5, color="red")
    ax.set_title("策略回撤")
    ax.set_ylabel("回撤")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_excess_return(nav_df: pd.DataFrame, assessment_bench: pd.DataFrame, out_path: Path):
    _setup_charts()
    if assessment_bench.empty:
        return
    merged = nav_df[["trade_date", "daily_return"]].merge(
        assessment_bench[["trade_date", "pct_chg"]], on="trade_date", how="inner")
    if merged.empty:
        return
    excess = merged["daily_return"].fillna(0) - merged["pct_chg"].fillna(0) / 100.0
    cum_excess = excess.cumsum()
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(merged["trade_date"], cum_excess, color=COLORS[0], linewidth=1.2)
    ax.axhline(0, color="gray", linewidth=0.8, linestyle="--")
    ax.set_title(f"相对 {ASSESSMENT_BENCHMARK['name']} 累计超额收益")
    ax.set_ylabel("累计超额收益")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_turnover_cost(nav_df: pd.DataFrame, out_path: Path):
    _setup_charts()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), sharex=True)
    ax1.bar(nav_df["trade_date"], nav_df["turnover_cny"], width=2, color=COLORS[0], alpha=0.7)
    ax1.set_ylabel("成交额（元）")
    ax1.set_title("日成交额与交易成本")
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/10000:.1f}万"))
    ax2.bar(nav_df["trade_date"], nav_df["cost_cny"], width=2, color=COLORS[3], alpha=0.7)
    ax2.set_ylabel("交易成本（元）")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# ── Markdown report ───────────────────────────────────────────────────────────
def _one_line_verdict(summary: dict, bench_ret: float, disp_ret: float) -> str:
    tr = float(summary.get("total_return", 0) or 0)
    parts = []
    if tr < bench_ret:
        parts.append(f"跑输 {ASSESSMENT_BENCHMARK['name']}（超额 {tr - bench_ret:.2%}）")
    else:
        parts.append(f"跑赢 {ASSESSMENT_BENCHMARK['name']}（超额 +{tr - bench_ret:.2%}）")
    if tr < disp_ret:
        parts.append(f"低于 {DISPLAY_BENCHMARK['name']}（差 {tr - disp_ret:.2%}）")
    else:
        parts.append(f"高于 {DISPLAY_BENCHMARK['name']}（好 +{tr - disp_ret:.2%}）")
    m = json.loads(summary.get("metrics_json") or "{}")
    dd = float(m.get("max_drawdown", 0) or 0)
    if dd <= -0.15:
        parts.append(f"最大回撤 {dd:.1%} 较大")
    return "；".join(parts) + "。"


def _fmt(v, decimals=4):
    if v is None or (isinstance(v, float) and v != v):
        return "N/A"
    return f"{v:.{decimals}f}"


def _pct(v):
    if v is None or (isinstance(v, float) and v != v):
        return "N/A"
    return f"{v:.2%}"


def render_markdown(summary: dict, model_info: dict, evidence: dict,
                    ai_result: dict, nav_df: pd.DataFrame,
                    assessment_bench: pd.DataFrame, display_bench: pd.DataFrame,
                    aux_benches: dict[str, pd.DataFrame],
                    trades_df: pd.DataFrame, positions_df: pd.DataFrame,
                    top_loss_stocks: list[dict], args) -> str:
    m = json.loads(summary.get("metrics_json") or "{}")
    ps = evidence.get("performance_summary", {})
    strat = ps.get("strategy", {})
    ab = ps.get("assessment_benchmark", {})
    db = ps.get("display_benchmark", {})
    exec_d = evidence.get("execution_diagnostics", {})
    cov = evidence.get("data_coverage", {})
    diag_triggered = len(evidence.get("drawdown_events", [])) > 0 or \
        strat.get("total_return", 0) < 0 or \
        strat.get("total_return", 0) < ab.get("total_return", 0)
    bench_ret = ab.get("total_return", 0) or 0
    disp_ret = db.get("total_return", 0) or 0

    sections = []

    # §8.1 首页摘要
    sections.append("# 策略 1 回测报告\n")
    sections.append(f"- **策略名称**: `{args.strategy_id}`")
    sections.append(f"- **run_id**: `{args.run_id}`")
    sections.append(f"- **backtest_id**: `{args.backtest_id}`")
    sections.append(f"- **model_id**: `{model_info.get('model_id', 'N/A')}`")
    model_metrics = json.loads(model_info.get("metrics_json") or "{}")
    _orientation = model_metrics.get("score_orientation", "identity")
    _orient_label = "原样（identity）" if _orientation == "identity" else "反向（reverse_probability: score = 1 - raw_prob）"
    sections.append(f"- **score 方向**: {_orient_label}")
    sections.append(f"- **生成时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    sections.append(f"- **评估主基准**: {ASSESSMENT_BENCHMARK['name']} `{ASSESSMENT_BENCHMARK['sec_code']}`")
    sections.append(f"- **展示对比基准**: {DISPLAY_BENCHMARK['name']} `{DISPLAY_BENCHMARK['sec_code']}`")
    for b in AUXILIARY_BENCHMARKS:
        sections.append(f"- **辅助基准**: {b['name']} `{b['sec_code']}`")
    sections.append(f"- **回测窗口**: {summary.get('start_date', '')} 至 {summary.get('end_date', '')}")
    sections.append(f"- **初始资金**: ¥100,000")
    sections.append(f"- **成本 profile**: `{m.get('cost_profile_id', 'N/A')}`")
    sections.append("")
    sections.append(f"**一句话结论**: {_one_line_verdict(summary, bench_ret, disp_ret)}")
    sections.append("")

    # §8.2 绩效总览
    sections.append("## 绩效总览\n")
    sections.append("| 指标 | 策略 | 基准 |")
    sections.append("|---|---|---|")
    sections.append(f"| 累计收益 | {_pct(strat.get('total_return'))} | {_pct(bench_ret)} |")
    sections.append(f"| 年化收益 | {_pct(strat.get('annual_return'))} | {_pct(ab.get('annual_return'))} |")
    sections.append(f"| 年化波动 | {_pct(strat.get('annual_vol'))} | — |")
    sections.append(f"| Sharpe | {_fmt(strat.get('sharpe'))} | — |")
    sections.append(f"| 最大回撤 | {_pct(strat.get('max_drawdown'))} | {_pct(ab.get('max_drawdown'))} |")
    sections.append(f"| 信息比率 | {_fmt(strat.get('information_ratio'))} | — |")
    sections.append(f"| 累计超额（vs {ASSESSMENT_BENCHMARK['name']}） | {_pct(strat.get('total_return', 0) - bench_ret)} | — |")
    sections.append("")
    sections.append(f"**{DISPLAY_BENCHMARK['name']} 累计收益**: {_pct(db.get('total_return'))}")
    for b in AUXILIARY_BENCHMARKS:
        aux_s = ps.get("auxiliary_benchmarks", {}).get(b["sec_code"], {})
        sections.append(f"**{b['name']} 累计收益**: {_pct(aux_s.get('total_return'))}")
    sections.append("")
    sections.append("### 成本分析\n")
    sections.append(f"- 佣金: {_fmt(m.get('total_commission_cny'), 2)} 元")
    sections.append(f"- 印花税: {_fmt(m.get('total_tax_cny'), 2)} 元")
    sections.append(f"- 滑点（隐性）: {_fmt(m.get('total_slippage_cny'), 2)} 元")
    sections.append(f"- 经济总成本: {_fmt(m.get('total_economic_cost_cny'), 2)} 元")
    sections.append(f"- 成本 profile: 佣金万一免五 / 卖出印花税 5 bps / 买卖滑点各 5 bps")
    sections.append("")
    sections.append("### 执行诊断\n")
    sections.append(f"- 买入成交: {exec_d.get('buy_filled_count', 0)}，"
                     f"现金缩放成交: {exec_d.get('buy_scaled_cash_count', 0)}，"
                     f"跳过: {exec_d.get('buy_skip_count', 0)}")
    sections.append(f"- 卖出成交: {exec_d.get('sell_filled_count', 0)}，"
                     f"跳过/延续: {exec_d.get('sell_skip_count', 0)}，"
                     f"pending sell 延续: {exec_d.get('pending_sell_carry_count', 0)}")
    sections.append(f"- netting 取消 pending sell: {exec_d.get('cancelled_by_netting_count', 0)}，"
                     f"已达目标无需继续卖: {exec_d.get('noop_already_target_count', 0)}")
    sections.append(f"- 最低现金: ¥{exec_d.get('min_cash_cny', 0):,.2f}")
    sections.append(f"- 最大总暴露: {exec_d.get('max_gross_exposure', 0):.2%}")
    sections.append("")

    # §8.3 图表
    sections.append("## 图表\n")
    sections.append("![策略净值 vs 基准](assets/nav_vs_benchmark.png)\n")
    sections.append("![策略回撤](assets/drawdown.png)\n")
    sections.append(f"![相对 {ASSESSMENT_BENCHMARK['name']} 超额收益](assets/excess_return.png)\n")
    sections.append("![换手与交易成本](assets/turnover_cost.png)\n")

    # §8.4 买卖细节
    sections.append("## 买卖细节\n")
    filled = trades_df[trades_df["fill_status"] == "FILLED"].copy() if not trades_df.empty else pd.DataFrame()

    if not filled.empty:
        sections.append("### 最近 20 笔成交\n")
        recent = filled.tail(20)
        sections.append("| 日期 | 代码 | 方向 | 股数 | 成交价 | 成交额 | 费用 |")
        sections.append("|---|---|---|---|---|---|---|")
        for _, r in recent.iterrows():
            sections.append(
                f"| {r['trade_date']} | {r['sec_code']} | {r['side']} | "
                f"{float(r.get('filled_shares', 0) or 0):,.0f} | "
                f"{float(r.get('fill_price', 0) or 0):.4f} | "
                f"¥{float(r.get('turnover_cny', 0) or 0):,.2f} | "
                f"¥{float(r.get('fee_cny', 0) or 0):,.2f} |"
            )
        sections.append("")

        sections.append("### 成交额最大的 20 笔\n")
        top_val = filled.nlargest(20, "turnover_cny")
        sections.append("| 日期 | 代码 | 方向 | 成交额 | 成本 |")
        sections.append("|---|---|---|---|---|")
        for _, r in top_val.iterrows():
            cost = float(r.get("fee_cny", 0) or 0) + float(r.get("slippage_cny", 0) or 0)
            sections.append(
                f"| {r['trade_date']} | {r['sec_code']} | {r['side']} | "
                f"¥{float(r.get('turnover_cny', 0) or 0):,.2f} | ¥{cost:,.2f} |"
            )
        sections.append("")

    skipped = trades_df[trades_df["fill_status"].str.contains("SKIPPED", na=False)] if not trades_df.empty else pd.DataFrame()
    if not skipped.empty:
        sections.append("### 不可交易跳过样例\n")
        sections.append("| 日期 | 代码 | 方向 | 计划股数 | 状态 |")
        sections.append("|---|---|---|---|---|")
        for _, r in skipped.head(10).iterrows():
            sections.append(
                f"| {r['trade_date']} | {r['sec_code']} | {r['side']} | "
                f"{float(r.get('planned_shares', 0) or 0):,.0f} | {r['fill_status']} |"
            )
        sections.append("")

    if top_loss_stocks:
        sections.append("### 亏损贡献最大的 20 个持仓\n")
        sections.append("| 代码 | 累计贡献 | 最大权重 | 持仓天数 |")
        sections.append("|---|---|---|---|")
        for s in top_loss_stocks:
            sections.append(
                f"| {s['sec_code']} | {s['total_contribution']:.4f} | "
                f"{s['max_weight']:.2%} | {s['trade_count']} |"
            )
        sections.append("")

    # §8.6 风险与归因
    dd_events = evidence.get("drawdown_events", [])
    fl_events = evidence.get("fast_loss_events", [])
    sections.append("## 风险与归因\n")
    if dd_events:
        sections.append("### 回撤事件\n")
        sections.append("| 峰值日 | 谷底日 | 回撤幅度 | 持续天数 |")
        sections.append("|---|---|---|---|")
        for ev in dd_events[:5]:
            sections.append(
                f"| {ev['peak_date']} | {ev['trough_date']} | "
                f"{ev['drawdown_pct']:.2%} | {ev['trading_days']} |"
            )
        sections.append("")

    if fl_events:
        sections.append("### 快速亏损窗口\n")
        sections.append("| 窗口 | 起始日 | 截止日 | 滚动收益 |")
        sections.append("|---|---|---|---|")
        for ev in fl_events:
            sections.append(
                f"| {ev['window']}日 | {ev['start_date']} | {ev['end_date']} | "
                f"{ev['worst_return']:.2%} |"
            )
        sections.append("")

    lc = evidence.get("loss_contributors", [])
    if lc:
        sections.append("### 持仓亏损归因\n")
        sections.append("口径: 每日持仓权重 × 股票当日收益的累计贡献。\n")
        sections.append("| 代码 | 累计贡献 | 最大权重 | 持仓天数 |")
        sections.append("|---|---|---|---|")
        for c in lc[:20]:
            sections.append(
                f"| {c['sec_code']} | {c['total_contribution']:.4f} | "
                f"{c['max_weight']:.2%} | {c['trade_count']} |"
            )
        sections.append(f"\n归因覆盖率: {cov.get('attribution_coverage_ratio', 0):.1%}")
        if cov.get("attribution_coverage_ratio", 1) < 0.95:
            sections.append(" **⚠ 归因覆盖不完整 (< 95%)**")
        sections.append("")

    # AI 诊断
    if diag_triggered and ai_result.get("analysis"):
        sections.append("## AI 诊断\n")
        status_label = {
            "success": "LLM 诊断",
            "evidence_only": "证据摘要（规则模板）",
            "fallback_evidence_only": "证据摘要（LLM 调用失败，已退化）",
        }.get(ai_result.get("status", ""), ai_result.get("status", ""))
        sections.append(f"**诊断模式**: {status_label}")
        if ai_result.get("model"):
            sections.append(f"**模型**: {ai_result['model']}")
        if ai_result.get("generated_utc"):
            sections.append(f"**生成时间**: {ai_result['generated_utc']}")
        sections.append("")
        sections.append(ai_result.get("analysis", ""))
        sections.append("")
    elif diag_triggered:
        sections.append("## AI 诊断\n")
        sections.append("AI 分析未启用或无输出。请检查 `--ai-analysis-mode` 参数。")
        sections.append("")

    # 因子贡献度摘要（可选第 13 步产物）
    if m.get("factor_attribution_status") == "completed":
        sections.append("## 因子贡献度摘要\n")
        if m.get("factor_attribution_uri"):
            sections.append(f"- GCS: `{m.get('factor_attribution_uri')}`")
        sections.append(f"- 本地: `{m.get('local_factor_attribution_path', '')}`")
        sections.append(f"- 版本: `{m.get('factor_attribution_version', '')}`")
        top_groups = m.get("top_score_factor_groups", []) or []
        if top_groups:
            sections.append("")
            sections.append("| 因子组 | 特征数 | 模型标准化贡献 | 持仓分数贡献 | Test RankIC |")
            sections.append("|---|---:|---:|---:|---:|")
            for g in top_groups[:5]:
                sections.append(
                    f"| {g.get('factor_group', '')} | {g.get('feature_count', '')} | "
                    f"{_fmt(g.get('model_abs_oriented_standardized_coefficient_sum'))} | "
                    f"{_fmt(g.get('held_position_score_contribution_sum'))} | "
                    f"{_fmt(g.get('test_mean_rank_ic_avg'))} |"
                )
        pos_factors = m.get("top_positive_score_factors", []) or []
        neg_factors = m.get("top_negative_score_factors", []) or []
        if pos_factors:
            sections.append("")
            sections.append("正向分数贡献靠前: " + "、".join(
                f"{x.get('feature')}({x.get('factor_group')})" for x in pos_factors[:5]
            ))
        if neg_factors:
            sections.append("负向分数贡献靠前: " + "、".join(
                f"{x.get('feature')}({x.get('factor_group')})" for x in neg_factors[:5]
            ))
        sections.append("")

    # 附件说明
    sections.append("## 附件\n")
    sections.append("| 文件 | 说明 |")
    sections.append("|---|---|")
    sections.append("| `trades.csv` | 完整成交明细（含 score/rank/权重） |")
    sections.append("| `positions.csv` | 每日持仓明细 |")
    sections.append("| `nav.csv` | 每日净值、现金、暴露、成本 |")
    sections.append("| `benchmark_nav.csv` | 策略与各基准净值对比（已固化） |")
    sections.append("| `drawdown_events.csv` | 回撤事件列表 |")
    sections.append("| `loss_attribution.csv` | 持仓亏损归因 |")
    sections.append("| `diagnosis_evidence.json` | AI 诊断证据包（可离线复核） |")
    sections.append("| `ai_analysis.json` | AI 诊断输出 |")
    sections.append("")

    sections.append("---\n")
    sections.append(f"*报告版本: {REPORT_VERSION} | "
                    f"证据 schema: {EVIDENCE_SCHEMA_VERSION} | "
                    f"评估主基准: {ASSESSMENT_BENCHMARK['name']} | "
                    f"展示基准: {DISPLAY_BENCHMARK['name']}*")

    return "\n".join(sections)


# ── HTML report ───────────────────────────────────────────────────────────────
def render_html(summary: dict, model_info: dict, evidence: dict,
                ai_result: dict, nav_df: pd.DataFrame,
                assessment_bench: pd.DataFrame, display_bench: pd.DataFrame,
                top_loss_stocks: list[dict], args) -> str:
    m = json.loads(summary.get("metrics_json") or "{}")
    model_metrics = json.loads(model_info.get("metrics_json") or "{}")
    ps = evidence.get("performance_summary", {})
    strat = ps.get("strategy", {})
    ab = ps.get("assessment_benchmark", {})
    db_ = ps.get("display_benchmark", {})
    exec_d = evidence.get("execution_diagnostics", {})
    cov = evidence.get("data_coverage", {})
    bench_ret = ab.get("total_return", 0) or 0
    diag_triggered = strat.get("total_return", 0) < 0 or strat.get("total_return", 0) < bench_ret

    def row(label, value):
        return f"<tr><th>{html.escape(str(label))}</th><td>{html.escape(str(value))}</td></tr>"

    perf_rows = "".join([
        row("回测窗口", f"{summary.get('start_date', '')} 至 {summary.get('end_date', '')}"),
        row("累计收益", _pct(strat.get("total_return"))),
        row("年化收益", _pct(strat.get("annual_return"))),
        row("年化波动", _pct(strat.get("annual_vol"))),
        row("Sharpe", _fmt(strat.get("sharpe"))),
        row("最大回撤", _pct(strat.get("max_drawdown"))),
        row(f"累计超额（vs {ASSESSMENT_BENCHMARK['name']}）",
            _pct(strat.get("total_return", 0) - bench_ret)),
        row("信息比率", _fmt(strat.get("information_ratio"))),
        row(f"{ASSESSMENT_BENCHMARK['name']} 累计收益", _pct(bench_ret)),
        row(f"{DISPLAY_BENCHMARK['name']} 累计收益", _pct(db_.get("total_return"))),
        row("佣金（元）", _fmt(m.get("total_commission_cny"), 2)),
        row("印花税（元）", _fmt(m.get("total_tax_cny"), 2)),
        row("滑点（元）", _fmt(m.get("total_slippage_cny"), 2)),
        row("经济总成本（元）", _fmt(m.get("total_economic_cost_cny"), 2)),
    ])
    exec_rows = "".join([
        row("买入成交", exec_d.get("buy_filled_count", 0)),
        row("买入现金缩放成交", exec_d.get("buy_scaled_cash_count", 0)),
        row("买入跳过", exec_d.get("buy_skip_count", 0)),
        row("卖出成交", exec_d.get("sell_filled_count", 0)),
        row("卖出跳过/延续", exec_d.get("sell_skip_count", 0)),
        row("pending sell 延续", exec_d.get("pending_sell_carry_count", 0)),
        row("netting 取消 pending sell", exec_d.get("cancelled_by_netting_count", 0)),
        row("已达目标无需继续卖", exec_d.get("noop_already_target_count", 0)),
        row("最低现金", f"¥{exec_d.get('min_cash_cny', 0):,.2f}"),
        row("最大总暴露", f"{exec_d.get('max_gross_exposure', 0):.2%}"),
    ])

    dd_html = ""
    for ev in evidence.get("drawdown_events", [])[:5]:
        dd_html += (f"<tr><td>{ev['peak_date']}</td><td>{ev['trough_date']}</td>"
                    f"<td>{ev['drawdown_pct']:.2%}</td><td>{ev['trading_days']}</td></tr>\n")
    dd_table = (f"<table><tr><th>峰值日</th><th>谷底日</th><th>回撤</th><th>天数</th></tr>\n"
                f"{dd_html}</table>") if dd_html else "<p>无显著回撤事件。</p>"

    loss_html = ""
    for s in top_loss_stocks[:10]:
        loss_html += (f"<tr><td>{s['sec_code']}</td><td>{s['total_contribution']:.4f}</td>"
                      f"<td>{s['max_weight']:.2%}</td><td>{s['trade_count']}</td></tr>\n")
    loss_table = (f"<table><tr><th>代码</th><th>累计贡献</th><th>最大权重</th><th>天数</th></tr>\n"
                  f"{loss_html}</table>") if loss_html else "<p>无亏损归因数据。</p>"

    ai_html = ""
    if diag_triggered and ai_result.get("analysis"):
        status_label = {"success": "LLM 诊断", "evidence_only": "证据摘要"}.get(
            ai_result.get("status", ""), "")
        ai_html = f"""<h2>AI 诊断</h2>
<p><b>模式</b>: {html.escape(status_label)} {'| <b>模型</b>: ' + html.escape(ai_result.get('model', '')) if ai_result.get('model') else ''}</p>
<div style="white-space:pre-wrap;background:#f9f9f9;padding:16px;border-radius:4px;font-size:0.95em">{html.escape(ai_result.get('analysis', ''))}</div>"""

    factor_html = ""
    if m.get("factor_attribution_status") == "completed":
        group_rows = ""
        for g in (m.get("top_score_factor_groups", []) or [])[:5]:
            group_rows += (
                f"<tr><td>{html.escape(str(g.get('factor_group', '')))}</td>"
                f"<td>{html.escape(str(g.get('feature_count', '')))}</td>"
                f"<td>{html.escape(_fmt(g.get('model_abs_oriented_standardized_coefficient_sum')))}</td>"
                f"<td>{html.escape(_fmt(g.get('held_position_score_contribution_sum')))}</td>"
                f"<td>{html.escape(_fmt(g.get('test_mean_rank_ic_avg')))}</td></tr>\n"
            )
        group_table = (
            "<table><tr><th>因子组</th><th>特征数</th><th>模型标准化贡献</th>"
            "<th>持仓分数贡献</th><th>Test RankIC</th></tr>"
            f"{group_rows}</table>"
        ) if group_rows else "<p>无因子组摘要。</p>"
        uri_line = (
            f"<p><b>GCS</b>: <code>{html.escape(str(m.get('factor_attribution_uri')))}</code></p>"
            if m.get("factor_attribution_uri") else ""
        )
        factor_html = f"""<h2>因子贡献度摘要</h2>
{uri_line}
<p><b>本地</b>: <code>{html.escape(str(m.get('local_factor_attribution_path', '')))}</code> |
<b>版本</b>: <code>{html.escape(str(m.get('factor_attribution_version', '')))}</code></p>
{group_table}
<p class="muted">该摘要为贡献度 proxy，不是消融实验，也不是因果归因。</p>"""

    model_metrics_pre = html.escape(json.dumps(json.loads(model_info.get("metrics_json") or "{}"), indent=2))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8">
<title>策略 1 回测报告</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;max-width:960px;margin:auto;padding:24px;color:#222;line-height:1.6}}
h1,h2{{border-bottom:1px solid #eee;padding-bottom:4px;margin-top:24px}}
table{{border-collapse:collapse;margin:12px 0;width:100%}}
td,th{{border:1px solid #ccc;padding:6px 12px;text-align:left}}
th{{background:#f6f6f6}}img{{max-width:100%;margin:8px 0}}
pre{{background:#f6f6f6;padding:12px;overflow:auto;font-size:0.85em}}
.muted{{color:#888;font-size:0.9em}}.summary-box{{background:#f0f7ff;padding:16px;border-radius:6px;margin:12px 0}}
</style></head>
<body>
<h1>策略 1 回测报告</h1>
<div class="summary-box">
<p><b>策略</b>: {html.escape(args.strategy_id)} | <b>run_id</b>: <code>{html.escape(args.run_id)}</code> | <b>backtest_id</b>: <code>{html.escape(args.backtest_id)}</code></p>
<p><b>评估主基准</b>: {ASSESSMENT_BENCHMARK['name']} ({ASSESSMENT_BENCHMARK['sec_code']}) |
   <b>展示基准</b>: {DISPLAY_BENCHMARK['name']} ({DISPLAY_BENCHMARK['sec_code']}) |
   <b>score 方向</b>: {html.escape(model_metrics.get('score_orientation', 'identity'))}</p>
<p><b>一句话结论</b>: {html.escape(_one_line_verdict(summary, bench_ret, db_.get('total_return', 0) or 0))}</p>
</div>
<h2>绩效总览</h2><table>{perf_rows}</table>
<h2>执行诊断</h2><table>{exec_rows}</table>
<h2>图表</h2>
<img src="assets/nav_vs_benchmark.png" alt="净值对比">
<img src="assets/drawdown.png" alt="回撤">
<img src="assets/excess_return.png" alt="超额收益">
<img src="assets/turnover_cost.png" alt="换手成本">
<h2>回撤事件</h2>{dd_table}
<h2>亏损归因</h2>
<p>口径: 每日持仓权重 × 股票当日收益的累计贡献（覆盖率 {cov.get('attribution_coverage_ratio', 0):.1%}）</p>
{loss_table}
{ai_html}
{factor_html}
<h2>模型选型</h2><pre>{model_metrics_pre}</pre>
<h2>附件说明</h2>
<table>
<tr><th>文件</th><th>说明</th></tr>
<tr><td>trades.csv</td><td>完整成交明细</td></tr>
<tr><td>positions.csv</td><td>每日持仓明细</td></tr>
<tr><td>nav.csv</td><td>每日净值与成本</td></tr>
<tr><td>benchmark_nav.csv</td><td>基准净值对比（已固化）</td></tr>
<tr><td>diagnosis_evidence.json</td><td>AI 证据包</td></tr>
<tr><td>ai_analysis.json</td><td>AI 诊断输出</td></tr>
</table>
<p class="muted">报告版本: {REPORT_VERSION} | 证据 schema: {EVIDENCE_SCHEMA_VERSION} | 生成时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
</body></html>"""


# ── Upload & metrics ──────────────────────────────────────────────────────────
def upload_dir_to_gcs(project: str, local_dir: Path, gcs_uri: str) -> bool:
    bucket_name = gcs_uri.replace("gs://", "").split("/")[0]
    prefix = "/".join(gcs_uri.replace("gs://", "").split("/")[1:])
    client = make_storage_client(project)
    bucket = client.bucket(bucket_name)
    for path in sorted(local_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(local_dir).as_posix()
            blob = bucket.blob(f"{prefix}/{rel}")
            content_type, _ = mimetypes.guess_type(str(path))
            blob.upload_from_filename(str(path), content_type=content_type)
            print(f"  Uploaded {blob.name}")
    return True


def write_report_status_to_ads(client: bigquery.Client, project: str,
                               backtest_id: str, local_path: str,
                               upload_status: str, report_uri: str | None,
                               metrics_patch: dict | None = None):
    base = "PARSE_JSON(COALESCE(bs.metrics_json, '{}'), wide_number_mode => 'round')"
    params = [
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("local_path", "STRING", local_path),
        bigquery.ScalarQueryParameter("upload_status", "STRING", upload_status),
        bigquery.ScalarQueryParameter("ts", "STRING", datetime.now(timezone.utc).isoformat()),
        bigquery.ScalarQueryParameter("report_ver", "STRING", REPORT_VERSION),
    ]

    json_expr = f"""JSON_SET({base},
      '$.local_report_path', @local_path,
      '$.report_upload_status', @upload_status,
      '$.report_generated_utc', @ts,
      '$.report_version', @report_ver"""

    if report_uri is not None:
        json_expr += ", '$.report_uri', @report_uri"
        params.append(bigquery.ScalarQueryParameter("report_uri", "STRING", report_uri))
    else:
        json_expr = f"""JSON_SET(JSON_REMOVE({base}, '$.report_uri'),
      '$.local_report_path', @local_path,
      '$.report_upload_status', @upload_status,
      '$.report_generated_utc', @ts,
      '$.report_version', @report_ver"""

    if metrics_patch:
        for k, v in metrics_patch.items():
            safe_k = k.replace("'", "\\'")
            if isinstance(v, bool):
                json_expr += f", '$.{safe_k}', {str(v).lower()}"
            elif isinstance(v, str):
                safe_v = v.replace("'", "\\'")
                json_expr += f", '$.{safe_k}', '{safe_v}'"
            elif isinstance(v, (int, float)):
                json_expr += f", '$.{safe_k}', {v}"
            elif v is None:
                json_expr += f", '$.{safe_k}', NULL"
            elif isinstance(v, (dict, list)):
                json_str = json.dumps(v, ensure_ascii=False, default=str).replace("'", "\\'")
                p_name = f"patch_{safe_k}"
                json_expr += f", '$.{safe_k}', PARSE_JSON(@{p_name})"
                params.append(bigquery.ScalarQueryParameter(p_name, "STRING", json_str))

    json_expr += ")"

    sql = f"""
    UPDATE `{project}.ashare_ads.ads_backtest_performance_summary` AS bs
    SET bs.metrics_json = TO_JSON_STRING({json_expr})
    WHERE bs.backtest_id = @bid
    """
    client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
    print(f"  Updated summary.metrics_json (status={upload_status})")


# ── Schema validation ─────────────────────────────────────────────────────────
REQUIRED_EVIDENCE_KEYS = [
    "schema_version", "run_context", "performance_summary",
    "drawdown_events", "fast_loss_events", "loss_contributors",
    "trade_samples", "cost_breakdown", "execution_diagnostics",
    "model_signal_diagnostics", "data_coverage",
]


def validate_evidence_schema(evidence: dict) -> list[str]:
    errors = []
    if evidence.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        errors.append(f"schema_version must be '{EVIDENCE_SCHEMA_VERSION}'")
    for k in REQUIRED_EVIDENCE_KEYS:
        if k not in evidence:
            errors.append(f"missing required key: {k}")
    return errors


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    args = parse_args()
    bq = make_bq_client(args.project)

    # 1. Fetch data
    print("获取回测汇总...")
    summary = fetch_summary(bq, args.project, args.backtest_id)
    sd = str(summary.get("start_date", "2024-01-01"))
    ed = str(summary.get("end_date", "2025-12-31"))
    m = json.loads(summary.get("metrics_json") or "{}")

    print("获取 NAV...")
    nav_df = fetch_nav(bq, args.project, args.backtest_id, sd, ed)

    print("获取模型信息...")
    model_info = fetch_model_info(bq, args.project, args.strategy_id, args.run_id)

    print("获取展示基准...")
    assessment_bench = fetch_display_benchmark(bq, args.project,
                                               ASSESSMENT_BENCHMARK["sec_code"], sd, ed)
    display_bench = fetch_display_benchmark(bq, args.project,
                                            DISPLAY_BENCHMARK["sec_code"], sd, ed)
    aux_benches = {}
    for b in AUXILIARY_BENCHMARKS:
        aux_benches[b["sec_code"]] = fetch_display_benchmark(bq, args.project, b["sec_code"], sd, ed)

    print("获取成交记录...")
    trades_df = fetch_trades(bq, args.project, args.backtest_id, sd, ed)
    buy_enriched = fetch_enriched_buy_trades(bq, args.project, args.run_id, args.backtest_id, sd, ed)
    pos_weights = fetch_position_weights(bq, args.project, args.backtest_id, sd, ed)

    print("获取持仓...")
    positions_df = fetch_positions(bq, args.project, args.backtest_id, sd, ed)

    print("获取预测...")
    predictions_df = fetch_predictions(bq, args.project, args.run_id, sd, ed)

    print("获取组合目标...")
    targets = fetch_portfolio_targets(bq, args.project, args.strategy_id, args.run_id, sd, ed)

    # 2. Setup directories
    report_dir = Path(args.local_mirror_root) / f"ml_pv_clf_v0/run_id={args.run_id}/backtest_id={args.backtest_id}"
    assets_dir = report_dir / "assets"
    report_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    # 3. Generate CSVs
    print("生成 CSV 附件...")
    write_csv(report_dir / "trades.csv",
              build_trades_csv(trades_df, buy_enriched, pos_weights, targets))
    write_csv(report_dir / "positions.csv", build_positions_csv(positions_df))
    write_csv(report_dir / "nav.csv", build_nav_csv(nav_df))
    write_csv(report_dir / "benchmark_nav.csv",
              build_benchmark_csv(nav_df, assessment_bench, display_bench, aux_benches))

    # 4. Compute evidence
    print("计算证据包...")
    drawdown_events = compute_drawdown_events(nav_df)
    rolling_events = compute_rolling_loss_events(nav_df)
    loss_contributors, coverage_ratio = compute_loss_attribution(
        bq, args.project, args.backtest_id, positions_df, sd, ed)
    cost_breakdown = compute_cost_breakdown(bq, args.project, args.backtest_id, sd, ed)
    exec_diag = compute_execution_diagnostics(bq, args.project, args.backtest_id, sd, ed)
    signal_diag = compute_model_signal_diagnostics(predictions_df)

    trade_samples = []
    if rolling_events:
        worst = min(rolling_events, key=lambda e: e.get("worst_return", 0))
        trade_samples = get_loss_window_trades(
            bq, args.project, args.backtest_id, worst["start_date"], worst["end_date"])

    evidence = build_evidence_pack(
        summary, nav_df, assessment_bench, display_bench, aux_benches,
        trades_df, positions_df, drawdown_events, rolling_events,
        loss_contributors, trade_samples, cost_breakdown, exec_diag,
        signal_diag, coverage_ratio, args)

    schema_errors = validate_evidence_schema(evidence)
    if schema_errors:
        print(f"  ⚠ 证据 schema 警告: {schema_errors}", file=sys.stderr)

    # Write CSVs that depend on evidence
    dd_rows = [["peak_date", "trough_date", "drawdown_pct", "trading_days", "peak_nav", "trough_nav"]]
    for ev in drawdown_events:
        dd_rows.append([ev["peak_date"], ev["trough_date"], ev["drawdown_pct"],
                        ev["trading_days"], ev["peak_nav"], ev["trough_nav"]])
    write_csv(report_dir / "drawdown_events.csv", dd_rows)

    la_rows = [["sec_code", "total_contribution", "max_weight", "trade_count"]]
    for c in loss_contributors:
        la_rows.append([c["sec_code"], c["total_contribution"], c["max_weight"], c["trade_count"]])
    write_csv(report_dir / "loss_attribution.csv", la_rows)

    (report_dir / "diagnosis_evidence.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False, default=str))

    # 5. AI analysis
    print("运行 AI 分析...")
    ai_result = run_ai_analysis(evidence, args)
    evidence_hash = hashlib.sha256(
        json.dumps(evidence, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:16]
    ai_output = {
        "status": ai_result.get("status", "off"),
        "model": ai_result.get("model"),
        "generated_utc": ai_result.get("generated_utc"),
        "evidence_hash": evidence_hash,
        "analysis": ai_result.get("analysis"),
        "error_type": ai_result.get("error_type"),
    }
    (report_dir / "ai_analysis.json").write_text(
        json.dumps(ai_output, indent=2, ensure_ascii=False, default=str))
    print(f"  AI 状态: {ai_result.get('status', 'off')}")

    # llm 模式失败时非零退出（PRD §10.1）
    if args.ai_analysis_mode == "llm" and ai_result.get("status") != "success":
        print(f"  ✗ llm 模式失败: {ai_result.get('error_type', 'unknown')}", file=sys.stderr)
        sys.exit(1)

    # 6. Render charts
    print("渲染图表...")
    plot_nav_vs_benchmark(nav_df, assessment_bench, display_bench, aux_benches,
                          assets_dir / "nav_vs_benchmark.png")
    plot_drawdown(nav_df, assets_dir / "drawdown.png")
    plot_excess_return(nav_df, assessment_bench, assets_dir / "excess_return.png")
    plot_turnover_cost(nav_df, assets_dir / "turnover_cost.png")

    # 7. Render reports
    print("渲染报告...")
    top_loss_stocks = evidence.get("loss_contributors", [])
    md = render_markdown(summary, model_info, evidence, ai_result, nav_df,
                         assessment_bench, display_bench, aux_benches,
                         trades_df, positions_df, top_loss_stocks, args)
    (report_dir / "report.md").write_text(md)
    (report_dir / "report.html").write_text(
        render_html(summary, model_info, evidence, ai_result, nav_df,
                    assessment_bench, display_bench, top_loss_stocks, args))

    # 8. Metrics
    diag_triggered, _ = determine_diagnosis_triggers(summary, nav_df, evidence)
    artifact_manifest = {}
    for p in sorted(report_dir.rglob("*")):
        if p.is_file():
            h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
            artifact_manifest[str(p.relative_to(report_dir))] = h
    metrics_ext = {
        "report_version": REPORT_VERSION,
        "diagnosis_triggered": diag_triggered,
        "ai_analysis_status": ai_result.get("status", "off"),
        "artifact_manifest": artifact_manifest,
    }
    metrics = {
        "backtest_id": args.backtest_id,
        "run_id": args.run_id,
        "strategy_id": args.strategy_id,
        "model_id": model_info.get("model_id"),
        "report_version": REPORT_VERSION,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "assessment_benchmark": ASSESSMENT_BENCHMARK,
        "display_benchmark": DISPLAY_BENCHMARK,
        "diagnosis_triggered": diag_triggered,
        "ai_analysis_status": ai_result.get("status", "off"),
        "artifact_manifest": artifact_manifest,
        "summary": {k: str(v) if not isinstance(v, (int, float, bool, type(None))) else v
                    for k, v in summary.items()},
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    (report_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))

    # 9. GCS upload
    gcs_uri = f"{args.artifact_base_uri}/ml_pv_clf_v0/run_id={args.run_id}/backtest_id={args.backtest_id}"
    upload_status, report_uri = "skipped", None

    if not args.skip_gcs_upload:
        try:
            print(f"上传至 GCS: {gcs_uri}")
            upload_dir_to_gcs(args.project, report_dir, gcs_uri)
            upload_status, report_uri = "uploaded", gcs_uri
        except Exception as e:
            print(f"  ⚠ GCS 上传失败: {e}", file=sys.stderr)
            upload_status = "skipped"

    # 10. Write back to ADS
    print("回写 ADS...")
    write_report_status_to_ads(bq, args.project, args.backtest_id,
                               str(report_dir), upload_status, report_uri, metrics_ext)

    print(f"完成。本地: {report_dir}")


if __name__ == "__main__":
    main()
