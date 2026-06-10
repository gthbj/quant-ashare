#!/usr/bin/env python3
"""Strategy 1 model quality diagnosis (FR-DIAG-1 .. FR-DIAG-10).

Reads model predictions, training panel, backtest results and DWS features
from BigQuery, computes structured diagnosis artifacts, writes local/GCS
output, and patches ads_backtest_performance_summary.metrics_json.

Usage:
    python scripts/strategy1/diagnose_model_quality.py \
        --project data-aquarium \
        --run-id s1_bqml_20260601_01 \
        --backtest-id bt_s1_bqml_20260601_01 \
        --artifact-base-uri gs://ashare-artifacts/reports/strategy1 \
        --local-mirror-root reports/strategy1

Requirements: google-cloud-bigquery, google-cloud-bigquery-storage,
google-cloud-storage, pandas, db-dtypes, scipy
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import pandas as pd
    import numpy as np
    from google.cloud import bigquery, storage
    try:
        from google.cloud import bigquery_storage
    except ImportError:
        bigquery_storage = None
    from scipy import stats
except ImportError as e:
    print(f"Missing dependency: {e}.", file=sys.stderr)
    print("Install: pip install google-cloud-bigquery google-cloud-bigquery-storage "
          "google-cloud-storage pandas db-dtypes scipy",
          file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.strategy1_cloudrun.dataset_roles import (
    OUTPUT_DATASET_ROLE_CHOICES,
    rewrite_sql_dataset_role,
)

# ── Constants ─────────────────────────────────────────────────────────────────
DIAGNOSIS_VERSION = "strategy1_model_diagnosis_v1"
OUTPUT_DATASET_ROLE = "ads"

# Feature columns referenced in FR-DIAG-6
FEATURE_COLS = [
    "ret_1d", "ret_5d", "ret_20d", "ret_60d",
    "mom_20_5", "mom_60_20",
    "vol_20d", "drawdown_20d",
    "amount_ma20_cny", "amount_zscore_20d",
    "turnover_rate", "volume_ratio",
    "pe_ttm", "pb", "ep_ttm", "bp",
    "log_total_mv", "log_circ_mv",
]

# ── CLI ───────────────────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(description="策略 1 模型质量诊断")
    p.add_argument("--project", required=True, help="GCP project id")
    p.add_argument("--run-id", required=True)
    p.add_argument("--prediction-run-id", default=None,
                   help="Model/prediction source run_id; defaults to --run-id. "
                        "Use this for OQ-010 portfolio-only experiments.")
    p.add_argument("--backtest-id", required=True)
    p.add_argument("--strategy-id", default="ml_pv_clf_v0")
    p.add_argument("--artifact-base-uri", required=True, help="gs://bucket/path")
    p.add_argument("--local-mirror-root", default="reports/strategy1")
    p.add_argument("--output-dataset-role", choices=OUTPUT_DATASET_ROLE_CHOICES, default="ads")
    p.add_argument("--skip-gcs-upload", action="store_true")
    p.add_argument("--p-target-holdings", type=int, default=5,
                   help="Current portfolio target holdings (OQ-010 default)")
    p.add_argument("--p-label-horizon", type=int, default=None,
                   help="Current target label horizon in trading days; default reads registry model_params_json, then 5")
    return p.parse_args()


# ── Credential helpers (same pattern as render_report.py) ─────────────────────
def _gcloud_token_credentials():
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
_BQSTORAGE_CLIENTS: dict[str, Any] = {}


def make_bqstorage_client(project: str):
    if bigquery_storage is None:
        return None
    if project not in _BQSTORAGE_CLIENTS:
        try:
            _BQSTORAGE_CLIENTS[project] = bigquery_storage.BigQueryReadClient()
        except Exception:
            creds = _gcloud_token_credentials()
            if creds is None:
                return None
            try:
                _BQSTORAGE_CLIENTS[project] = bigquery_storage.BigQueryReadClient(credentials=creds)
            except Exception:
                return None
    return _BQSTORAGE_CLIENTS[project]


def bq_query(client: bigquery.Client, sql: str, params: list | None = None) -> pd.DataFrame:
    sql = rewrite_sql_dataset_role(
        sql,
        dataset_role=OUTPUT_DATASET_ROLE,
        project=client.project,
    )
    cfg = bigquery.QueryJobConfig(query_parameters=params or [])
    bqstorage_client = make_bqstorage_client(client.project)
    if bqstorage_client is None:
        return client.query(sql, job_config=cfg).to_dataframe()
    return client.query(sql, job_config=cfg).to_dataframe(bqstorage_client=bqstorage_client)


def bq_query_scalar(client: bigquery.Client, sql: str, params: list | None = None) -> Any:
    df = bq_query(client, sql, params)
    if df.empty or df.columns.empty:
        return None
    return df.iloc[0, 0]


def normalize_label_horizon(value: Any) -> int:
    horizon = int(value or 5)
    if horizon not in (5, 10, 20):
        raise SystemExit("--p-label-horizon must be one of 5, 10, 20")
    return horizon


# ── FR-DIAG-1 运行身份冻结 ────────────────────────────────────────────────────
def fetch_model_identity(client: bigquery.Client, project: str,
                         strategy_id: str, run_id: str) -> dict:
    sql = f"""
    SELECT reg.model_id, reg.feature_version, reg.label_version,
           reg.preprocess_version, reg.metrics_json, reg.model_params_json
    FROM `{project}.ashare_ads.ads_model_registry` AS reg
    WHERE reg.strategy_id = @sid AND reg.status = 'selected'
      AND JSON_VALUE(reg.model_params_json, '$.run_id') = @rid
    ORDER BY reg.created_at DESC
    LIMIT 1
    """
    df = bq_query(client, sql, [
        bigquery.ScalarQueryParameter("sid", "STRING", strategy_id),
        bigquery.ScalarQueryParameter("rid", "STRING", run_id),
    ])
    if df.empty:
        raise SystemExit(f"No selected model for run_id={run_id}")
    row = df.iloc[0]
    m = json.loads(row.get("metrics_json") or "{}")
    p = json.loads(row.get("model_params_json") or "{}")
    return {
        "model_id": row["model_id"],
        "feature_version": row["feature_version"],
        "label_version": row["label_version"],
        "preprocess_version": row["preprocess_version"],
        "model_params_json": p,
        "metrics_json": m,
        "score_orientation": m.get("score_orientation", "identity"),
        "score_source": m.get("score_source", "positive_class_probability"),
        "raw_valid_rank_ic_mean": m.get("raw_valid_rank_ic_mean"),
        "oriented_valid_rank_ic_mean": m.get("oriented_valid_rank_ic_mean"),
        "orientation_decision_reason": m.get("orientation_decision_reason"),
    }


# ── FR-DIAG-2 信号方向与稳定性 ────────────────────────────────────────────────
def fetch_predictions_with_labels(client: bigquery.Client, project: str,
                                  run_id: str, start_date: str, end_date: str,
                                  label_horizon: int) -> pd.DataFrame:
    sql = f"""
    SELECT
      pred.predict_date AS trade_date,
      pred.sec_code,
      pred.score,
      pred.rank_raw,
      pred.rank_pct,
      tp.target_return,
      CASE @h
        WHEN 5 THEN s.fwd_ret_5d
        WHEN 10 THEN s.fwd_ret_10d
        WHEN 20 THEN s.fwd_ret_20d
      END AS target_abs_return,
      tp.target_label,
      CASE @h
        WHEN 5 THEN s.label_above_median_5d
        WHEN 10 THEN s.label_above_median_10d
        WHEN 20 THEN s.label_above_median_20d
      END AS target_above_median,
      tp.split_tag
    FROM `{project}.ashare_ads.ads_model_prediction_daily` AS pred
    JOIN `{project}.ashare_ads.ads_ml_training_panel_daily` AS tp
      ON tp.trade_date = pred.predict_date
     AND tp.sec_code = pred.sec_code
     AND tp.run_id = @rid
     AND tp.trade_date BETWEEN @sd AND @ed
    JOIN `{project}.ashare_dws.dws_stock_sample_daily` AS s
      ON s.trade_date = pred.predict_date
     AND s.sec_code = pred.sec_code
     AND s.feature_version = tp.feature_version
     AND s.label_version = tp.label_version
    WHERE pred.run_id = @rid
      AND pred.predict_date BETWEEN @sd AND @ed
      AND tp.split_tag IN ('valid', 'test')
      AND tp.horizon = @h
      AND tp.target_label IS NOT NULL
      AND tp.target_return IS NOT NULL
    ORDER BY pred.predict_date, pred.score DESC
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("rid", "STRING", run_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
        bigquery.ScalarQueryParameter("h", "INT64", label_horizon),
    ])


def compute_rank_ic(pred_df: pd.DataFrame) -> pd.DataFrame:
    if pred_df.empty:
        return pd.DataFrame()
    records = []
    for dt, g in pred_df.groupby("trade_date"):
        if len(g) < 3:
            records.append({"trade_date": dt, "rank_ic": np.nan})
        else:
            records.append({"trade_date": dt, "rank_ic": g["score"].corr(g["target_return"], method="spearman")})
    ic = pd.DataFrame.from_records(records)
    if not ic.empty:
        ic["year"] = pd.to_datetime(ic["trade_date"]).dt.year
        ic["month"] = pd.to_datetime(ic["trade_date"]).dt.to_period("M").astype(str)
    return ic


def compute_rank_ic_summary(ic_df: pd.DataFrame) -> dict:
    if ic_df.empty:
        return {}
    vals = ic_df["rank_ic"].dropna()
    return {
        "mean": round(float(vals.mean()), 6) if len(vals) > 0 else None,
        "std": round(float(vals.std()), 6) if len(vals) > 1 else None,
        "icir": round(float(vals.mean() / vals.std()), 4) if len(vals) > 1 and vals.std() > 0 else None,
        "positive_ratio": round(float((vals > 0).sum() / len(vals)), 4) if len(vals) > 0 else None,
        "count": int(len(vals)),
    }


def compute_bucket_lift(pred_df: pd.DataFrame, n_buckets: int = 5) -> pd.DataFrame:
    if pred_df.empty:
        return pd.DataFrame()
    df = pred_df.copy()
    df["bucket"] = df.groupby("trade_date")["score"].transform(
        lambda x: pd.qcut(x.rank(method="first"), n_buckets, labels=False, duplicates="drop") + 1
    )
    # bucket 1 = lowest score, bucket n = highest score (after +1)
    # Re-map: bucket n = top score
    agg = df.groupby("bucket").agg(
        n=("score", "count"),
        avg_score=("score", "mean"),
        hit_rate=("target_label", "mean"),
        avg_target_return=("target_return", "mean"),
        median_target_return=("target_return", "median"),
        avg_target_abs_return=("target_abs_return", "mean"),
    ).reset_index()
    agg = agg.sort_values("bucket", ascending=False).reset_index(drop=True)
    if len(agg) >= 2:
        agg["top_minus_bottom"] = agg["avg_target_return"] - agg.iloc[-1]["avg_target_return"]
    else:
        agg["top_minus_bottom"] = np.nan
    # Monotonicity: correlation between bucket rank and avg target return.
    if len(agg) >= 3:
        agg["monotonicity"] = agg["bucket"].corr(agg["avg_target_return"], method="spearman")
    else:
        agg["monotonicity"] = np.nan
    return agg


def compute_topn_ret(pred_df: pd.DataFrame, top_n: int) -> dict:
    if pred_df.empty:
        return {}
    top = pred_df[pred_df["rank_raw"] <= top_n]
    return {
        "top_n": top_n,
        "count": int(len(top)),
        "avg_target_return": round(float(top["target_return"].mean()), 6),
        "median_target_return": round(float(top["target_return"].median()), 6),
    }


# ── FR-DIAG-3 校准 ────────────────────────────────────────────────────────────
def compute_score_calibration(pred_df: pd.DataFrame, n_buckets: int = 10) -> pd.DataFrame:
    if pred_df.empty:
        return pd.DataFrame()
    df = pred_df.copy()
    df["bucket"] = df.groupby("trade_date")["score"].transform(
        lambda x: pd.qcut(x.rank(method="first"), n_buckets, labels=False, duplicates="drop") + 1
    )
    agg = df.groupby("bucket").agg(
        n=("score", "count"),
        avg_score=("score", "mean"),
        actual_pos_rate=("target_label", "mean"),
        actual_above_median_rate=("target_above_median", "mean"),
        avg_target_return=("target_return", "mean"),
        std_target_return=("target_return", "std"),
    ).reset_index()
    agg = agg.sort_values("bucket", ascending=False).reset_index(drop=True)
    # Score spread
    if len(agg) >= 2:
        agg["score_spread"] = agg.iloc[0]["avg_score"] - agg.iloc[-1]["avg_score"]
    else:
        agg["score_spread"] = np.nan
    return agg


# ── FR-DIAG-4 标签 horizon 对照 ──────────────────────────────────────────────
def fetch_label_horizon(client: bigquery.Client, project: str,
                        run_id: str, start_date: str, end_date: str,
                        label_horizon: int) -> pd.DataFrame:
    sql = f"""
    SELECT
      pred.predict_date AS trade_date,
      pred.sec_code,
      pred.score,
      pred.rank_pct,
      l.fwd_xs_ret_1d,
      l.fwd_xs_ret_5d,
      l.fwd_xs_ret_10d,
      l.fwd_xs_ret_20d,
      CASE @h
        WHEN 5 THEN l.label_top30_5d
        WHEN 10 THEN l.label_top30_10d
        WHEN 20 THEN l.label_top30_20d
      END AS target_label,
      CASE @h
        WHEN 5 THEN l.label_above_median_5d
        WHEN 10 THEN l.label_above_median_10d
        WHEN 20 THEN l.label_above_median_20d
      END AS target_above_median,
      tp.split_tag
    FROM `{project}.ashare_ads.ads_model_prediction_daily` AS pred
    JOIN `{project}.ashare_ads.ads_ml_training_panel_daily` AS tp
      ON tp.trade_date = pred.predict_date
     AND tp.sec_code = pred.sec_code
     AND tp.run_id = @rid
     AND tp.trade_date BETWEEN @sd AND @ed
    JOIN `{project}.ashare_dws.dws_stock_label_daily` AS l
      ON l.trade_date = pred.predict_date
     AND l.sec_code = pred.sec_code
     AND l.label_version = tp.label_version
    WHERE pred.run_id = @rid
      AND pred.predict_date BETWEEN @sd AND @ed
      AND tp.split_tag IN ('valid', 'test')
      AND tp.horizon = @h
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("rid", "STRING", run_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
        bigquery.ScalarQueryParameter("h", "INT64", label_horizon),
    ])


def compute_label_horizon_comparison(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    records = []
    for split in ("valid", "test"):
        sub = df[df["split_tag"] == split]
        if sub.empty:
            continue
        for horizon in ("1d", "5d", "10d", "20d"):
            col = f"fwd_xs_ret_{horizon}"
            if col not in sub.columns:
                continue
            records.append({
                "split": split,
                "horizon": horizon,
                "rank_ic": round(float(sub["score"].corr(sub[col], method="spearman")), 6),
                "target_top30_avg_return": round(float(sub[sub["target_label"] == 1][col].mean()), 6)
                    if (sub["target_label"] == 1).sum() > 0 else None,
                "target_bottom70_avg_return": round(float(sub[sub["target_label"] == 0][col].mean()), 6)
                    if (sub["target_label"] == 0).sum() > 0 else None,
                "top_minus_bottom": round(float(
                    sub.nlargest(int(max(1, len(sub) * 0.3)), "score")[col].mean() -
                    sub.nsmallest(int(max(1, len(sub) * 0.3)), "score")[col].mean()
                ), 6),
            })
    return pd.DataFrame.from_records(records)


# ── FR-DIAG-5 样本和股票池漏斗 ───────────────────────────────────────────────
def fetch_funnel_data(client: bigquery.Client, project: str,
                      run_id: str, strategy_id: str,
                      start_date: str, end_date: str,
                      label_horizon: int) -> pd.DataFrame:
    sql = f"""
    SELECT
      s.trade_date,
      s.split_tag,
      COUNT(*) AS pure_universe,
      COUNTIF(
        COALESCE(s.in_universe_default, FALSE)
        AND COALESCE(s.has_full_history_60d, FALSE)
        AND COALESCE(s.has_valuation_data, FALSE)
        AND COALESCE(s.label_entry_tradable, FALSE)
        AND CASE @h
          WHEN 5 THEN COALESCE(s.label_valid_5d, FALSE) AND s.label_top30_5d IS NOT NULL AND s.fwd_xs_ret_5d IS NOT NULL
          WHEN 10 THEN COALESCE(s.label_valid_10d, FALSE) AND s.label_top30_10d IS NOT NULL AND s.fwd_xs_ret_10d IS NOT NULL
          WHEN 20 THEN COALESCE(s.label_valid_20d, FALSE) AND s.label_top30_20d IS NOT NULL AND s.fwd_xs_ret_20d IS NOT NULL
        END
      ) AS sample_trainable,
      COUNTIF(u.in_universe_default) AS in_universe_default,
      COUNTIF(s.has_full_history_60d) AS has_full_history,
      COUNTIF(s.has_valuation_data) AS has_valuation_data,
      COUNTIF(CASE @h
        WHEN 5 THEN COALESCE(s.label_valid_5d, FALSE)
        WHEN 10 THEN COALESCE(s.label_valid_10d, FALSE)
        WHEN 20 THEN COALESCE(s.label_valid_20d, FALSE)
      END) AS label_valid_target,
      COUNTIF(s.label_entry_tradable) AS label_entry_tradable,
      COUNTIF(s.is_st) AS is_st_count,
      COUNTIF(NOT COALESCE(s.is_tradable_hard, FALSE)) AS not_tradable_hard
    FROM `{project}.ashare_dws.dws_stock_sample_daily` AS s
    LEFT JOIN `{project}.ashare_dws.dws_stock_universe_daily` AS u
      ON u.sec_code = s.sec_code AND u.trade_date = s.trade_date
     AND u.trade_date BETWEEN @sd AND @ed
    WHERE s.trade_date BETWEEN @sd AND @ed
      AND s.feature_version = (SELECT ANY_VALUE(tp.feature_version)
                               FROM `{project}.ashare_ads.ads_ml_training_panel_daily` AS tp
                               WHERE tp.run_id = @rid
                                 AND tp.trade_date BETWEEN @sd AND @ed
                               LIMIT 1)
    GROUP BY s.trade_date, s.split_tag
    ORDER BY s.trade_date
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("rid", "STRING", run_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
        bigquery.ScalarQueryParameter("h", "INT64", label_horizon),
    ])


def fetch_prediction_funnel(client: bigquery.Client, project: str,
                            prediction_run_id: str, candidate_run_id: str, strategy_id: str,
                            start_date: str, end_date: str) -> pd.DataFrame:
    sql = f"""
    SELECT
      pred.predict_date AS trade_date,
      COUNT(*) AS prediction_count,
      COUNTIF(cand.is_selected_candidate) AS selected_count,
      COUNTIF(cand.in_universe_default) AS in_universe_pred
    FROM `{project}.ashare_ads.ads_model_prediction_daily` AS pred
    LEFT JOIN `{project}.ashare_ads.ads_stock_candidate_daily` AS cand
      ON cand.sec_code = pred.sec_code
     AND cand.rebalance_date = pred.predict_date
     AND cand.strategy_id = @sid
     AND cand.run_id = @cand_rid
    WHERE pred.run_id = @pred_rid
      AND pred.predict_date BETWEEN @sd AND @ed
    GROUP BY pred.predict_date
    ORDER BY pred.predict_date
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("pred_rid", "STRING", prediction_run_id),
        bigquery.ScalarQueryParameter("cand_rid", "STRING", candidate_run_id),
        bigquery.ScalarQueryParameter("sid", "STRING", strategy_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])


def fetch_trade_funnel(client: bigquery.Client, project: str,
                       backtest_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    sql = f"""
    SELECT
      t.trade_date,
      COUNTIF(t.side = 'BUY' AND t.fill_status IN ('FILLED', 'FILLED_SCALED_CASH')) AS buy_filled,
      COUNTIF(t.side = 'SELL' AND t.fill_status = 'FILLED') AS sell_filled
    FROM `{project}.ashare_ads.ads_backtest_trade_daily` AS t
    WHERE t.backtest_id = @bid
      AND t.trade_date BETWEEN @sd AND @ed
    GROUP BY t.trade_date
    ORDER BY t.trade_date
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])


def fetch_sample_filter_risk(client: bigquery.Client, project: str,
                             run_id: str, start_date: str, end_date: str,
                             label_horizon: int) -> pd.DataFrame:
    """Check whether valid/test prediction pool uses live-available mask
    (PRD-20260602-05: compare panel rows against legacy trainable and live-available)."""
    sql = f"""
    SELECT
      tp.split_tag,
      COUNT(*) AS panel_rows,
      COUNTIF(
        COALESCE(s.in_universe_default, FALSE)
        AND COALESCE(s.has_full_history_60d, FALSE)
        AND COALESCE(s.has_valuation_data, FALSE)
        AND COALESCE(s.label_entry_tradable, FALSE)
        AND CASE @h
          WHEN 5 THEN COALESCE(s.label_valid_5d, FALSE) AND s.label_top30_5d IS NOT NULL AND s.fwd_xs_ret_5d IS NOT NULL
          WHEN 10 THEN COALESCE(s.label_valid_10d, FALSE) AND s.label_top30_10d IS NOT NULL AND s.fwd_xs_ret_10d IS NOT NULL
          WHEN 20 THEN COALESCE(s.label_valid_20d, FALSE) AND s.label_top30_20d IS NOT NULL AND s.fwd_xs_ret_20d IS NOT NULL
        END
      ) AS legacy_trainable_rows,
      COUNTIF(COALESCE(s.in_universe_default, FALSE)
          AND COALESCE(s.has_full_history_60d, FALSE)
          AND COALESCE(s.has_valuation_data, FALSE)) AS live_available_rows,
      COUNTIF(CASE @h
        WHEN 5 THEN COALESCE(s.label_valid_5d, FALSE) AND s.fwd_xs_ret_5d IS NOT NULL
        WHEN 10 THEN COALESCE(s.label_valid_10d, FALSE) AND s.fwd_xs_ret_10d IS NOT NULL
        WHEN 20 THEN COALESCE(s.label_valid_20d, FALSE) AND s.fwd_xs_ret_20d IS NOT NULL
      END) AS label_available_eval_rows,
      -- rows in live-available but NOT in legacy trainable
      COUNTIF(COALESCE(s.in_universe_default, FALSE)
          AND COALESCE(s.has_full_history_60d, FALSE)
          AND COALESCE(s.has_valuation_data, FALSE)
          AND NOT (
            COALESCE(s.label_entry_tradable, FALSE)
            AND CASE @h
              WHEN 5 THEN COALESCE(s.label_valid_5d, FALSE) AND s.label_top30_5d IS NOT NULL AND s.fwd_xs_ret_5d IS NOT NULL
              WHEN 10 THEN COALESCE(s.label_valid_10d, FALSE) AND s.label_top30_10d IS NOT NULL AND s.fwd_xs_ret_10d IS NOT NULL
              WHEN 20 THEN COALESCE(s.label_valid_20d, FALSE) AND s.label_top30_20d IS NOT NULL AND s.fwd_xs_ret_20d IS NOT NULL
            END
          )) AS live_only_rows,
      -- legacy exclusion diagnostics
      COUNTIF(NOT COALESCE(s.label_entry_tradable, FALSE)) AS excluded_by_tradable,
      COUNTIF(NOT CASE @h
        WHEN 5 THEN COALESCE(s.label_valid_5d, FALSE)
        WHEN 10 THEN COALESCE(s.label_valid_10d, FALSE)
        WHEN 20 THEN COALESCE(s.label_valid_20d, FALSE)
      END) AS excluded_by_label_valid
    FROM `{project}.ashare_ads.ads_ml_training_panel_daily` AS tp
    JOIN `{project}.ashare_dws.dws_stock_sample_daily` AS s
      ON s.trade_date = tp.trade_date AND s.sec_code = tp.sec_code
     AND s.feature_version = tp.feature_version AND s.label_version = tp.label_version
    WHERE tp.run_id = @rid
      AND tp.trade_date BETWEEN @sd AND @ed
      AND tp.split_tag IN ('valid', 'test')
    GROUP BY tp.split_tag
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("rid", "STRING", run_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
        bigquery.ScalarQueryParameter("h", "INT64", label_horizon),
    ])


def compute_funnel_summary(sample_df: pd.DataFrame, pred_df: pd.DataFrame,
                           trade_df: pd.DataFrame) -> pd.DataFrame:
    if sample_df.empty:
        return pd.DataFrame()
    merged = sample_df.merge(pred_df, on="trade_date", how="left")
    merged = merged.merge(trade_df, on="trade_date", how="left")
    merged["predictable_rate"] = merged["prediction_count"] / merged["sample_trainable"]
    merged["selected_rate"] = merged["selected_count"] / merged["in_universe_default"]
    merged["total_exclusion"] = merged["pure_universe"] - merged["sample_trainable"]
    merged["explained_exclusion"] = (
        merged["is_st_count"]
        + merged["not_tradable_hard"]
        + (merged["pure_universe"] - merged["has_full_history"])
        + (merged["pure_universe"] - merged["has_valuation_data"])
        # label_valid_* exclusion only applies to train; this is a horizon-aware approximation.
    )
    merged["unexplained_exclusion_rate"] = (
        (merged["total_exclusion"] - merged["explained_exclusion"]).clip(lower=0)
        / merged["pure_universe"]
    )
    return merged


# ── FR-DIAG-6 特征暴露诊断 ────────────────────────────────────────────────────
def fetch_feature_exposure(client: bigquery.Client, project: str,
                           prediction_run_id: str, candidate_run_id: str,
                           strategy_id: str,
                           backtest_id: str,
                           start_date: str, end_date: str) -> pd.DataFrame:
    # Aggregate feature exposure in BigQuery. Pulling the full prediction pool
    # locally is large enough to make repeated OQ-010 diagnostics unstable.
    sql = f"""
    WITH base AS (
      SELECT
        pred.predict_date AS trade_date,
        pred.sec_code,
        pred.rank_pct,
        cand.is_selected_candidate,
        pos.weight AS position_weight,
        f.ret_1d, f.ret_5d, f.ret_20d, f.ret_60d,
        f.mom_20_5, f.mom_60_20,
        f.vol_20d, f.drawdown_20d,
        f.amount_ma20_cny, f.amount_zscore_20d,
        f.turnover_rate, f.volume_ratio,
        f.pe_ttm, f.pb, f.ep_ttm, f.bp,
        f.log_total_mv, f.log_circ_mv
      FROM `{project}.ashare_ads.ads_model_prediction_daily` AS pred
      LEFT JOIN `{project}.ashare_ads.ads_stock_candidate_daily` AS cand
        ON cand.sec_code = pred.sec_code
       AND cand.rebalance_date = pred.predict_date
       AND cand.strategy_id = @sid
       AND cand.run_id = @cand_rid
      LEFT JOIN `{project}.ashare_ads.ads_backtest_position_daily` AS pos
        ON pos.sec_code = pred.sec_code
       AND pos.trade_date = pred.predict_date
       AND pos.backtest_id = @bid
      LEFT JOIN `{project}.ashare_dws.dws_stock_feature_daily_v0` AS f
        ON f.sec_code = pred.sec_code
       AND f.trade_date = pred.predict_date
       AND f.trade_date BETWEEN @sd AND @ed
      WHERE pred.run_id = @pred_rid
        AND pred.predict_date BETWEEN @sd AND @ed
    ),
    grouped AS (
      SELECT 'all_predictions' AS group_name, * FROM base
      UNION ALL
      SELECT 'top_30pct' AS group_name, * FROM base WHERE rank_pct >= 0.7
      UNION ALL
      SELECT 'bottom_30pct' AS group_name, * FROM base WHERE rank_pct <= 0.3
      UNION ALL
      SELECT 'selected_candidate' AS group_name, * FROM base WHERE is_selected_candidate IS TRUE
      UNION ALL
      SELECT 'held_position' AS group_name, * FROM base WHERE position_weight > 0
    ),
    unpivoted AS (
      SELECT group_name, feature, value
      FROM grouped
      UNPIVOT (
        value FOR feature IN (
          ret_1d, ret_5d, ret_20d, ret_60d,
          mom_20_5, mom_60_20,
          vol_20d, drawdown_20d,
          amount_ma20_cny, amount_zscore_20d,
          turnover_rate, volume_ratio,
          pe_ttm, pb, ep_ttm, bp,
          log_total_mv, log_circ_mv
        )
      )
    )
    SELECT
      group_name AS `group`,
      feature,
      COUNT(value) AS n,
      ROUND(AVG(value), 6) AS mean,
      ROUND(STDDEV_SAMP(value), 6) AS std,
      ROUND(APPROX_QUANTILES(value, 100)[SAFE_OFFSET(50)], 6) AS median,
      ROUND(APPROX_QUANTILES(value, 100)[SAFE_OFFSET(10)], 6) AS p10,
      ROUND(APPROX_QUANTILES(value, 100)[SAFE_OFFSET(90)], 6) AS p90
    FROM unpivoted
    GROUP BY group_name, feature
    HAVING n > 0
    ORDER BY group_name, feature
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("pred_rid", "STRING", prediction_run_id),
        bigquery.ScalarQueryParameter("cand_rid", "STRING", candidate_run_id),
        bigquery.ScalarQueryParameter("sid", "STRING", strategy_id),
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])


def compute_feature_exposure_by_group(feat_df: pd.DataFrame) -> pd.DataFrame:
    if feat_df.empty:
        return pd.DataFrame()
    agg_cols = {"group", "feature", "n", "mean", "std", "median", "p10", "p90"}
    if agg_cols.issubset(set(feat_df.columns)):
        return feat_df
    groups = {
        "all_predictions": feat_df,
        "top_30pct": feat_df[feat_df["rank_pct"] >= 0.7],
        "bottom_30pct": feat_df[feat_df["rank_pct"] <= 0.3],
        "selected_candidate": feat_df[feat_df["is_selected_candidate"] == True],
        "held_position": feat_df[feat_df["position_weight"] > 0],
    }
    records = []
    for gname, gdf in groups.items():
        if gdf.empty:
            continue
        for col in FEATURE_COLS:
            if col not in gdf.columns:
                continue
            records.append({
                "group": gname,
                "feature": col,
                "n": int(len(gdf)),
                "mean": round(float(gdf[col].mean()), 6),
                "std": round(float(gdf[col].std()), 6) if len(gdf) > 1 else None,
                "median": round(float(gdf[col].median()), 6),
                "p10": round(float(gdf[col].quantile(0.10)), 6),
                "p90": round(float(gdf[col].quantile(0.90)), 6),
            })
    return pd.DataFrame.from_records(records)


# ── FR-DIAG-7 回测链路归因 ────────────────────────────────────────────────────
def fetch_backtest_attribution(client: bigquery.Client, project: str,
                               backtest_id: str, start_date: str, end_date: str) -> dict:
    # NAV / drawdown / concentration / cost / turnover
    sql_nav = f"""
    SELECT trade_date, nav, daily_return, turnover_cny, cost_cny,
           cash_cny, gross_exposure
    FROM `{project}.ashare_ads.ads_backtest_nav_daily`
    WHERE backtest_id = @bid AND trade_date BETWEEN @sd AND @ed
    ORDER BY trade_date
    """
    nav = bq_query(client, sql_nav, [
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])

    sql_pos = f"""
    SELECT trade_date, sec_code, weight, market_value_cny
    FROM `{project}.ashare_ads.ads_backtest_position_daily`
    WHERE backtest_id = @bid AND trade_date BETWEEN @sd AND @ed
    """
    pos = bq_query(client, sql_pos, [
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])

    sql_trade = f"""
    SELECT trade_date, sec_code, side, turnover_cny, fee_cny, tax_cny, slippage_cny,
           cash_effect_cny, fill_status
    FROM `{project}.ashare_ads.ads_backtest_trade_daily`
    WHERE backtest_id = @bid AND trade_date BETWEEN @sd AND @ed
    """
    trades = bq_query(client, sql_trade, [
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])
    return {"nav": nav, "positions": pos, "trades": trades}


def compute_drawdown_windows(nav_df: pd.DataFrame) -> pd.DataFrame:
    if nav_df.empty:
        return pd.DataFrame()
    nav_df = nav_df.sort_values("trade_date").reset_index(drop=True)
    nav_df["cummax"] = nav_df["nav"].cummax()
    nav_df["dd"] = nav_df["nav"] / nav_df["cummax"] - 1
    events = []
    in_dd = False
    peak_date = peak_val = trough_date = trough_val = None
    for _, row in nav_df.iterrows():
        dt, val, cm = row["trade_date"], row["nav"], row["cummax"]
        if val >= cm:
            if in_dd and trough_val is not None:
                dd_pct = trough_val / peak_val - 1
                if dd_pct < -0.01:
                    events.append({
                        "peak_date": str(peak_date),
                        "trough_date": str(trough_date),
                        "drawdown_pct": round(dd_pct, 6),
                        "peak_nav": round(peak_val, 6),
                        "trough_nav": round(trough_val, 6),
                    })
            in_dd = False
            peak_date, peak_val = dt, val
        else:
            if not in_dd:
                in_dd = True
                trough_date, trough_val = dt, val
            elif val < trough_val:
                trough_date, trough_val = dt, val
    if in_dd and trough_val is not None:
        dd_pct = trough_val / peak_val - 1
        if dd_pct < -0.01:
            events.append({
                "peak_date": str(peak_date),
                "trough_date": str(trough_date),
                "drawdown_pct": round(dd_pct, 6),
                "peak_nav": round(peak_val, 6),
                "trough_nav": round(trough_val, 6),
            })
    return pd.DataFrame.from_records(events)


def compute_portfolio_concentration(pos_df: pd.DataFrame) -> pd.DataFrame:
    if pos_df.empty:
        return pd.DataFrame()
    agg = pos_df.groupby("trade_date").agg(
        position_count=("sec_code", "count"),
        top_weight=("weight", "max"),
        hhi=("weight", lambda w: float((w ** 2).sum())),
        total_mv=("market_value_cny", "sum"),
    ).reset_index()
    return agg


def compute_cost_turnover(nav_df: pd.DataFrame, trades_df: pd.DataFrame) -> pd.DataFrame:
    if nav_df.empty:
        return pd.DataFrame()
    base = nav_df[["trade_date", "nav", "daily_return", "cost_cny", "turnover_cny"]].copy()
    cost_cols = ["turnover", "fee", "tax", "slippage", "economic_cost"]
    if trades_df.empty:
        for col in cost_cols:
            base[col] = 0.0
        return base

    trades = trades_df.copy()
    for col in ["turnover_cny", "fee_cny", "tax_cny", "slippage_cny"]:
        trades[col] = pd.to_numeric(trades[col], errors="coerce").fillna(0.0)
    trades["economic_cost"] = trades["fee_cny"].fillna(0) + trades["slippage_cny"].fillna(0)
    cost = trades.groupby("trade_date").agg(
        turnover=("turnover_cny", "sum"),
        fee=("fee_cny", "sum"),
        tax=("tax_cny", "sum"),
        slippage=("slippage_cny", "sum"),
        economic_cost=("economic_cost", "sum"),
    ).reset_index()
    merged = base.merge(cost, on="trade_date", how="left")
    numeric_fill_cols = [
        "nav", "daily_return", "cost_cny", "turnover_cny",
        "turnover", "fee", "tax", "slippage", "economic_cost",
    ]
    merged[numeric_fill_cols] = merged[numeric_fill_cols].fillna(0.0)
    return merged


# ── FR-DIAG-8 市场和风格阶段 ──────────────────────────────────────────────────
def fetch_market_regime(client: bigquery.Client, project: str,
                        start_date: str, end_date: str) -> pd.DataFrame:
    sql = f"""
    SELECT trade_date, close, pct_chg
    FROM `{project}.ashare_dwd.dwd_index_eod`
    WHERE sec_code = '000001.SH'
      AND trade_date BETWEEN @sd AND @ed
    ORDER BY trade_date
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])


def fetch_style_exposure(client: bigquery.Client, project: str,
                         prediction_run_id: str, backtest_id: str,
                         start_date: str, end_date: str) -> pd.DataFrame:
    sql = f"""
    SELECT
      pos.trade_date,
      pos.sec_code,
      pos.weight,
      f.log_total_mv,
      f.vol_20d,
      f.amount_ma20_cny,
      f.pe_ttm,
      f.pb,
      pred.score
    FROM `{project}.ashare_ads.ads_backtest_position_daily` AS pos
    LEFT JOIN `{project}.ashare_dws.dws_stock_feature_daily_v0` AS f
      ON f.sec_code = pos.sec_code AND f.trade_date = pos.trade_date
     AND f.trade_date BETWEEN @sd AND @ed
    LEFT JOIN `{project}.ashare_ads.ads_model_prediction_daily` AS pred
      ON pred.sec_code = pos.sec_code AND pred.predict_date = pos.trade_date
     AND pred.run_id = @rid
    WHERE pos.backtest_id = @bid AND pos.trade_date BETWEEN @sd AND @ed
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("rid", "STRING", prediction_run_id),
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])


# ── FR-DIAG-9 诊断结论分类 ────────────────────────────────────────────────────
def determine_primary_diagnosis(valid_ic: dict, test_ic: dict,
                                bucket_lift_df: pd.DataFrame,
                                label_horizon_df: pd.DataFrame,
                                funnel_df: pd.DataFrame,
                                cost_turnover_df: pd.DataFrame,
                                style_df: pd.DataFrame,
                                sample_risk_df: pd.DataFrame,
                                backtest_summary: dict,
                                label_horizon: int) -> dict:
    """Rule-based primary diagnosis with confidence level.
    Pipeline/sample risks are checked first so they cannot be masked by signal conclusions."""
    evidence = []

    def add_evidence(metric: str, value: Any, threshold: str, direction: str):
        evidence.append({"metric": metric, "value": value, "threshold": threshold, "direction": direction})

    valid_mean = valid_ic.get("mean") or 0
    test_mean = test_ic.get("mean") or 0
    valid_icir = valid_ic.get("icir") or 0
    test_icir = test_ic.get("icir") or 0

    # ── Mandatory pipeline checks first ──
    # Sample filter risk (PRD-20260602-05: live-available prediction pool check)
    if not sample_risk_df.empty:
        for _, row in sample_risk_df.iterrows():
            split = row.get("split_tag")
            panel_rows = int(row.get("panel_rows", 0) or 0)
            legacy_trainable = int(row.get("legacy_trainable_rows", 0) or 0)
            live_available = int(row.get("live_available_rows", 0) or 0)
            live_only = int(row.get("live_only_rows", 0) or 0)
            label_eval = int(row.get("label_available_eval_rows", 0) or 0)

            add_evidence(f"{split}_panel_rows", panel_rows, ">0", "info")
            add_evidence(f"{split}_legacy_trainable_rows", legacy_trainable, "<panel_rows", "info")
            add_evidence(f"{split}_live_available_rows", live_available, ">=legacy", "info")
            add_evidence(f"{split}_live_only_rows", live_only, ">0 proves live-available active", "info")
            add_evidence(f"{split}_label_eval_rows", label_eval, ">0", "info")

            # If live_only > 0, the live-available mask is active (good).
            # If live_only == 0 and panel_rows == legacy_trainable, still using old mask.
            if live_only == 0 and panel_rows == legacy_trainable and panel_rows > 0:
                add_evidence(f"{split}_trainable_ratio",
                             round(legacy_trainable / max(panel_rows, 1), 4), "<1.0", "filtered")
                return {"primary": "sample_filter_risk", "confidence": "high", "evidence": evidence}

    # Signal inverted
    if valid_mean < -0.03 and test_mean < -0.03:
        if not bucket_lift_df.empty:
            tmb = bucket_lift_df["top_minus_bottom"].dropna()
            if len(tmb) > 0 and tmb.iloc[0] < 0:
                add_evidence("valid_rank_ic_mean", valid_mean, "<-0.03", "negative")
                add_evidence("test_rank_ic_mean", test_mean, "<-0.03", "negative")
                add_evidence("bucket_top_minus_bottom", float(tmb.iloc[0]), "<0", "negative")
                return {"primary": "signal_inverted", "confidence": "high", "evidence": evidence}

    # Weak signal
    if abs(valid_mean) < 0.02 and abs(test_mean) < 0.02:
        add_evidence("valid_rank_ic_mean", valid_mean, "abs<0.02", "weak")
        add_evidence("test_rank_ic_mean", test_mean, "abs<0.02", "weak")
        return {"primary": "weak_signal", "confidence": "medium", "evidence": evidence}

    # Label horizon mismatch
    if not label_horizon_df.empty:
        target_name = f"{label_horizon}d"
        target_ic = label_horizon_df[label_horizon_df["horizon"] == target_name]["rank_ic"].mean()
        alt_ics = []
        for hname in ("1d", "5d", "10d", "20d"):
            if hname != target_name:
                alt_ics.append((label_horizon_df[label_horizon_df["horizon"] == hname]["rank_ic"].mean(), hname))
        if pd.isna(target_ic) or abs(target_ic or 0) < 0.02:
            best_alt = max(alt_ics, key=lambda x: abs(x[0] or 0))
            if abs(best_alt[0] or 0) > 0.05:
                add_evidence(f"rank_ic_{target_name}", target_ic, "abs<0.02", "weak")
                add_evidence(f"rank_ic_{best_alt[1]}", best_alt[0], "abs>0.05", "stronger")
                return {"primary": "label_horizon_mismatch", "confidence": "medium", "evidence": evidence}

    # Sample filter risk (funnel-based fallback)
    # PRD-20260602-05: only trigger if live-available mask is NOT active
    # (i.e., no live_only_rows detected in the earlier sample_risk_df check)
    if not funnel_df.empty:
        live_mask_active = False
        if not sample_risk_df.empty:
            for _, row in sample_risk_df.iterrows():
                if int(row.get("live_only_rows", 0) or 0) > 0:
                    live_mask_active = True
                    break
        if not live_mask_active:
            unexplained = funnel_df["unexplained_exclusion_rate"].mean()
            if unexplained > 0.10:
                add_evidence("unexplained_exclusion_rate", round(float(unexplained), 4), ">0.10", "high")
                return {"primary": "sample_filter_risk", "confidence": "high", "evidence": evidence}
        else:
            # Live-available mask is active; record funnel as evidence only, not as primary diagnosis
            unexplained = funnel_df["unexplained_exclusion_rate"].mean()
            add_evidence("funnel_unexplained_exclusion_rate", round(float(unexplained), 4), ">0.10", "info_only")

    # Cost turnover issue
    if not cost_turnover_df.empty:
        total_cost = cost_turnover_df["economic_cost"].sum()
        total_pnl = (cost_turnover_df["nav"].iloc[-1] - 1.0) * 100000 if not cost_turnover_df.empty else 0
        if total_pnl != 0 and abs(total_cost / total_pnl) >= 0.20:
            add_evidence("cost_to_pnl_ratio", round(abs(total_cost / total_pnl), 4), ">=0.20", "high")
            return {"primary": "cost_turnover_issue", "confidence": "medium", "evidence": evidence}

    # Portfolio concentration issue
    # (would need more detailed analysis; placeholder)

    # Style regime issue
    if not style_df.empty:
        avg_log_mv = style_df["log_total_mv"].mean()
        # Compare to prediction pool average? Simplified: just flag if data available
        pass

    # Default: inconclusive if signal exists but not strong enough
    if valid_mean > 0.02 and test_mean > 0.02:
        add_evidence("valid_rank_ic_mean", valid_mean, ">0.02", "positive")
        add_evidence("test_rank_ic_mean", test_mean, ">0.02", "positive")
        return {"primary": "usable_signal", "confidence": "low", "evidence": evidence}

    add_evidence("valid_rank_ic_mean", valid_mean, "inconclusive", "mixed")
    add_evidence("test_rank_ic_mean", test_mean, "inconclusive", "mixed")
    return {"primary": "inconclusive", "confidence": "low", "evidence": evidence}


# ── FR-DIAG-10 artifact & ADS writeback ───────────────────────────────────────
def write_csv(path: Path, df: pd.DataFrame):
    df.to_csv(path, index=False, encoding="utf-8-sig")


def write_json(path: Path, obj: dict):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def upload_dir_to_gcs(project: str, local_dir: Path, gcs_uri: str) -> bool:
    import mimetypes
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


def write_diagnosis_status_to_ads(client: bigquery.Client, project: str,
                                  backtest_id: str, local_path: str,
                                  diagnosis_status: str, upload_status: str,
                                  diagnosis_uri: str | None,
                                  diagnosis_summary: dict, artifact_manifest: dict):
    base = "PARSE_JSON(COALESCE(bs.metrics_json, '{}'), wide_number_mode => 'round')"
    params = [
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("local_path", "STRING", local_path),
        bigquery.ScalarQueryParameter("diagnosis_status", "STRING", diagnosis_status),
        bigquery.ScalarQueryParameter("upload_status", "STRING", upload_status),
        bigquery.ScalarQueryParameter("ts", "STRING", datetime.now(timezone.utc).isoformat()),
        bigquery.ScalarQueryParameter("ver", "STRING", DIAGNOSIS_VERSION),
        bigquery.ScalarQueryParameter("primary", "STRING", diagnosis_summary.get("primary_diagnosis", "")),
        bigquery.ScalarQueryParameter("confidence", "STRING", diagnosis_summary.get("confidence", "")),
        bigquery.ScalarQueryParameter("prediction_run_id", "STRING", diagnosis_summary.get("prediction_run_id", "")),
    ]

    json_expr = f"""JSON_SET({base},
      '$.model_diagnosis_status', @diagnosis_status,
      '$.model_diagnosis_upload_status', @upload_status,
      '$.model_diagnosis_version', @ver,
      '$.model_diagnosis_generated_utc', @ts,
      '$.local_model_diagnosis_path', @local_path,
      '$.model_diagnosis_prediction_run_id', @prediction_run_id,
      '$.model_diagnosis_primary_diagnosis', @primary,
      '$.model_diagnosis_confidence', @confidence"""

    if diagnosis_uri is not None:
        json_expr += ", '$.model_diagnosis_uri', @uri"
        params.append(bigquery.ScalarQueryParameter("uri", "STRING", diagnosis_uri))

    # artifact manifest
    manifest_json = json.dumps(artifact_manifest, ensure_ascii=False, default=str).replace("'", "\\'")
    json_expr += ", '$.model_diagnosis_artifact_manifest', PARSE_JSON(@manifest)"
    params.append(bigquery.ScalarQueryParameter("manifest", "STRING", manifest_json))

    json_expr += ")"

    sql = f"""
    UPDATE `{project}.ashare_ads.ads_backtest_performance_summary` AS bs
    SET bs.metrics_json = TO_JSON_STRING({json_expr})
    WHERE bs.backtest_id = @bid
    """
    sql = rewrite_sql_dataset_role(
        sql,
        dataset_role=OUTPUT_DATASET_ROLE,
        project=project,
    )
    client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
    print(
        "  Updated summary.metrics_json "
        f"(diagnosis_status={diagnosis_status}, upload_status={upload_status})"
    )


def render_diagnosis_markdown(identity: dict, valid_ic: dict, test_ic: dict,
                              bucket_lift_df: pd.DataFrame, label_horizon_df: pd.DataFrame,
                              funnel_summary: pd.DataFrame, feature_exposure_df: pd.DataFrame,
                              diagnosis_result: dict, args) -> str:
    lines = []
    lines.append("# 策略 1 模型质量诊断\n")
    lines.append(f"- **diagnosis_version**: `{DIAGNOSIS_VERSION}`")
    lines.append(f"- **run_id**: `{args.run_id}`")
    if args.prediction_run_id != args.run_id:
        lines.append(f"- **prediction_run_id**: `{args.prediction_run_id}`")
    lines.append(f"- **backtest_id**: `{args.backtest_id}`")
    lines.append(f"- **model_id**: `{identity.get('model_id')}`")
    lines.append(f"- **label_horizon**: `{args.p_label_horizon}d`")
    lines.append(f"- **score_orientation**: `{identity.get('score_orientation', 'identity')}`")
    lines.append(f"- **score_source**: `{identity.get('score_source', 'positive_class_probability')}`")
    if identity.get("orientation_decision_reason"):
        lines.append(f"- **orientation_reason**: {identity.get('orientation_decision_reason')}")
    if identity.get("raw_valid_rank_ic_mean") is not None:
        lines.append(f"- **raw_valid_rank_ic**: {identity.get('raw_valid_rank_ic_mean')}")
        lines.append(f"- **oriented_valid_rank_ic**: {identity.get('oriented_valid_rank_ic_mean')}")
    lines.append(f"- **生成时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")

    lines.append("## 诊断结论\n")
    lines.append(f"**主结论**: `{diagnosis_result['primary']}`")
    lines.append(f"**置信度**: `{diagnosis_result['confidence']}`")
    lines.append("")

    lines.append("## 信号方向与稳定性\n")
    lines.append("### Valid RankIC")
    for k, v in valid_ic.items():
        lines.append(f"- {k}: {v}")
    lines.append("### Test RankIC")
    for k, v in test_ic.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    def _df_to_md(df: pd.DataFrame) -> str:
        if df.empty:
            return ""
        cols = list(df.columns)
        header = "| " + " | ".join(cols) + " |"
        sep = "|" + "|".join([" --- " for _ in cols]) + "|"
        rows = []
        for _, row in df.iterrows():
            rows.append("| " + " | ".join(str(row[c]) if row[c] is not None else "" for c in cols) + " |")
        return "\n".join([header, sep] + rows)

    if not bucket_lift_df.empty:
        lines.append("## 分层收益 (5 bucket)\n")
        lines.append(_df_to_md(bucket_lift_df))
        lines.append("")

    if not label_horizon_df.empty:
        lines.append("## 标签 horizon 对照\n")
        lines.append(_df_to_md(label_horizon_df))
        lines.append("")

    if not funnel_summary.empty:
        lines.append("## 样本漏斗摘要\n")
        lines.append(f"- 平均不可解释排除率: {funnel_summary['unexplained_exclusion_rate'].mean():.2%}")
        lines.append("")

    lines.append("---\n")
    lines.append("*本诊断基于 BigQuery ADS/DWS/DWD 数据自动生成，所有结论可追溯至 CSV/JSON artifact。*")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    global OUTPUT_DATASET_ROLE
    args = parse_args()
    args.prediction_run_id = args.prediction_run_id or args.run_id
    OUTPUT_DATASET_ROLE = args.output_dataset_role
    bq = make_bq_client(args.project)

    print("读取模型身份...")
    identity = fetch_model_identity(bq, args.project, args.strategy_id, args.prediction_run_id)

    # Infer date ranges from model registry if available
    mp = identity.get("model_params_json", {})
    args.p_label_horizon = normalize_label_horizon(args.p_label_horizon or mp.get("label_horizon"))
    valid_start = mp.get("valid_start_date", "2024-01-01")
    valid_end = mp.get("valid_end_date", "2024-12-31")
    test_start = mp.get("test_start_date", "2025-01-01")
    test_end = mp.get("test_end_date", "2025-12-31")

    # FR-DIAG-2: predictions + labels
    print("拉取预测与标签...")
    pred_all = fetch_predictions_with_labels(
        bq, args.project, args.prediction_run_id, valid_start, test_end, args.p_label_horizon)
    pred_valid = pred_all[pred_all["split_tag"] == "valid"].copy()
    pred_test = pred_all[pred_all["split_tag"] == "test"].copy()
    print(
        "预测与标签行数: "
        f"all={len(pred_all)}, valid={len(pred_valid)}, test={len(pred_test)}, "
        f"memory_mb={pred_all.memory_usage(deep=True).sum() / 1024 / 1024:.1f}"
    )

    print("计算 RankIC...")
    ic_valid = compute_rank_ic(pred_valid)
    ic_test = compute_rank_ic(pred_test)
    ic_all = compute_rank_ic(pred_all)
    valid_ic_summary = compute_rank_ic_summary(ic_valid)
    test_ic_summary = compute_rank_ic_summary(ic_test)

    print("计算 bucket lift...")
    bucket_lift_valid = compute_bucket_lift(pred_valid)
    bucket_lift_test = compute_bucket_lift(pred_test)
    bucket_lift_all = pd.concat([
        bucket_lift_valid.assign(split="valid"),
        bucket_lift_test.assign(split="test"),
    ], ignore_index=True) if not (bucket_lift_valid.empty and bucket_lift_test.empty) else pd.DataFrame()

    topn_valid = compute_topn_ret(pred_valid, args.p_target_holdings)
    topn_test = compute_topn_ret(pred_test, args.p_target_holdings)

    print("计算校准...")
    cal_valid = compute_score_calibration(pred_valid)
    cal_test = compute_score_calibration(pred_test)
    cal_all = pd.concat([
        cal_valid.assign(split="valid"),
        cal_test.assign(split="test"),
    ], ignore_index=True) if not (cal_valid.empty and cal_test.empty) else pd.DataFrame()

    # FR-DIAG-4: label horizon
    print("标签 horizon 对照...")
    label_df = fetch_label_horizon(
        bq, args.project, args.prediction_run_id, valid_start, test_end, args.p_label_horizon)
    label_horizon = compute_label_horizon_comparison(label_df)

    # FR-DIAG-5: funnel
    print("样本漏斗...")
    sample_df = fetch_funnel_data(
        bq, args.project, args.prediction_run_id, args.strategy_id, valid_start, test_end, args.p_label_horizon)
    pred_funnel = fetch_prediction_funnel(
        bq, args.project, args.prediction_run_id, args.run_id, args.strategy_id, valid_start, test_end)
    trade_funnel = fetch_trade_funnel(bq, args.project, args.backtest_id, valid_start, test_end)
    funnel_summary = compute_funnel_summary(sample_df, pred_funnel, trade_funnel)

    print("检测 live-unavailable 过滤风险...")
    sample_risk_df = fetch_sample_filter_risk(
        bq, args.project, args.prediction_run_id, valid_start, test_end, args.p_label_horizon)

    # FR-DIAG-6: feature exposure
    print("特征暴露...")
    feat_df = fetch_feature_exposure(
        bq, args.project, args.prediction_run_id, args.run_id,
        args.strategy_id, args.backtest_id, valid_start, test_end)
    feature_exposure = compute_feature_exposure_by_group(feat_df)

    # FR-DIAG-7: backtest attribution
    print("回测归因...")
    bt = fetch_backtest_attribution(bq, args.project, args.backtest_id, test_start, test_end)
    dd_windows = compute_drawdown_windows(bt["nav"])
    concentration = compute_portfolio_concentration(bt["positions"])
    cost_turnover = compute_cost_turnover(bt["nav"], bt["trades"])

    # FR-DIAG-8: market regime
    print("市场风格...")
    market_regime = fetch_market_regime(bq, args.project, test_start, test_end)
    style_df = fetch_style_exposure(
        bq, args.project, args.prediction_run_id, args.backtest_id, test_start, test_end)

    # FR-DIAG-9: diagnosis conclusion
    print("诊断结论...")
    backtest_summary = {}  # Could fetch from ADS if needed
    diagnosis = determine_primary_diagnosis(
        valid_ic_summary, test_ic_summary,
        bucket_lift_all, label_horizon, funnel_summary,
        cost_turnover, style_df, sample_risk_df, backtest_summary,
        args.p_label_horizon,
    )
    diagnosis_summary = {
        "diagnosis_version": DIAGNOSIS_VERSION,
        "run_id": args.run_id,
        "prediction_run_id": args.prediction_run_id,
        "backtest_id": args.backtest_id,
        "label_horizon": args.p_label_horizon,
        "model_id": identity.get("model_id"),
        "score_orientation": identity.get("score_orientation", "identity"),
        "score_source": identity.get("score_source", "positive_class_probability"),
        "raw_valid_rank_ic_mean": identity.get("raw_valid_rank_ic_mean"),
        "oriented_valid_rank_ic_mean": identity.get("oriented_valid_rank_ic_mean"),
        "orientation_decision_reason": identity.get("orientation_decision_reason"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "primary_diagnosis": diagnosis["primary"],
        "confidence": diagnosis["confidence"],
        "evidence": diagnosis["evidence"],
        "valid_rank_ic": valid_ic_summary,
        "test_rank_ic": test_ic_summary,
        "topn_valid": topn_valid,
        "topn_test": topn_test,
    }

    # Setup directories
    diag_dir = (Path(args.local_mirror_root)
                / f"ml_pv_clf_v0/run_id={args.run_id}/backtest_id={args.backtest_id}/model_diagnosis")
    diag_dir.mkdir(parents=True, exist_ok=True)

    # Write artifacts
    print("写入 artifact...")
    write_csv(diag_dir / "daily_rank_ic.csv", ic_all)
    write_json(diag_dir / "rank_ic_summary.json", {
        "valid": valid_ic_summary,
        "test": test_ic_summary,
        "all": compute_rank_ic_summary(ic_all),
    })
    write_csv(diag_dir / "score_bucket_lift.csv", bucket_lift_all)
    write_csv(diag_dir / "score_calibration.csv", cal_all)
    write_csv(diag_dir / "label_horizon_comparison.csv", label_horizon)
    write_csv(diag_dir / "sample_universe_funnel.csv", funnel_summary)
    write_csv(diag_dir / "candidate_funnel.csv", pred_funnel)
    write_csv(diag_dir / "feature_exposure_by_group.csv", feature_exposure)
    write_csv(diag_dir / "drawdown_window_diagnostics.csv", dd_windows)
    write_csv(diag_dir / "portfolio_concentration.csv", concentration)
    write_csv(diag_dir / "cost_turnover_diagnostics.csv", cost_turnover)
    write_csv(diag_dir / "market_regime_diagnostics.csv", market_regime)
    write_csv(diag_dir / "style_exposure_diagnostics.csv", style_df)
    write_json(diag_dir / "diagnosis_summary.json", diagnosis_summary)

    md = render_diagnosis_markdown(
        identity, valid_ic_summary, test_ic_summary,
        bucket_lift_all, label_horizon, funnel_summary, feature_exposure,
        diagnosis, args)
    (diag_dir / "diagnosis.md").write_text(md, encoding="utf-8")

    # Artifact manifest
    artifact_manifest = {}
    for p in sorted(diag_dir.rglob("*")):
        if p.is_file():
            h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
            artifact_manifest[str(p.relative_to(diag_dir))] = h

    # GCS upload
    gcs_uri = (f"{args.artifact_base_uri}/ml_pv_clf_v0/"
               f"run_id={args.run_id}/backtest_id={args.backtest_id}/model_diagnosis")
    diagnosis_status = "completed"
    upload_status, diagnosis_uri = "skipped", None
    if not args.skip_gcs_upload:
        try:
            print(f"上传至 GCS: {gcs_uri}")
            upload_dir_to_gcs(args.project, diag_dir, gcs_uri)
            upload_status, diagnosis_uri = "uploaded", gcs_uri
        except Exception as e:
            print(f"  ⚠ GCS 上传失败: {e}", file=sys.stderr)
            upload_status = "skipped"

    # ADS writeback
    print("回写 ADS...")
    write_diagnosis_status_to_ads(
        bq, args.project, args.backtest_id,
        str(diag_dir), diagnosis_status, upload_status, diagnosis_uri,
        diagnosis_summary, artifact_manifest)

    print(f"完成。本地: {diag_dir}")


if __name__ == "__main__":
    main()
