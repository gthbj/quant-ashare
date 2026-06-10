#!/usr/bin/env python3
"""Strategy 1 factor attribution artifacts.

Reads the selected BQML model, frozen training panel, prediction pool and
backtest positions from BigQuery. Generates factor attribution summaries without
retraining, without ablation runs and without changing trading outputs.

Usage:
    python scripts/strategy1/attribute_factor_contribution.py \
        --project data-aquarium \
        --run-id s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01 \
        --backtest-id bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01 \
        --artifact-base-uri gs://ashare-artifacts/reports/strategy1 \
        --local-mirror-root reports/strategy1

Requirements: google-cloud-bigquery, google-cloud-bigquery-storage,
google-cloud-storage, pandas, db-dtypes
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import numpy as np
    import pandas as pd
    from google.cloud import bigquery, storage
    try:
        from google.cloud import bigquery_storage
    except ImportError:
        bigquery_storage = None
except ImportError as e:
    print(f"Missing dependency: {e}.", file=sys.stderr)
    print(
        "Install: pip install google-cloud-bigquery google-cloud-bigquery-storage "
        "google-cloud-storage pandas db-dtypes",
        file=sys.stderr,
    )
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.strategy1_cloudrun.dataset_roles import (
    OUTPUT_DATASET_ROLE_CHOICES,
    rewrite_sql_dataset_role,
)


ATTRIBUTION_VERSION = "strategy1_factor_attribution_v1"
OUTPUT_DATASET_ROLE = "ads"
REQUIRED_ARTIFACTS = [
    "factor_attribution.md",
    "factor_attribution_summary.json",
    "factor_model_weights.csv",
    "factor_rank_ic_daily.csv",
    "factor_rank_ic_summary.csv",
    "factor_bucket_lift_summary.csv",
    "factor_score_contribution_summary.csv",
    "portfolio_factor_exposure_daily.csv",
    "portfolio_factor_attribution_proxy.csv",
    "factor_group_summary.csv",
    "factor_correlation_summary.csv",
    "artifact_manifest.json",
]

SCORE_GROUPS = [
    "all_predictions",
    "top_30pct",
    "bottom_30pct",
    "selected_candidate",
    "held_position",
]

FEATURE_GROUPS = {
    "list_age_td": "seasoning",
    "ret_1d": "reversal_momentum",
    "ret_3d": "reversal_momentum",
    "ret_5d": "reversal_momentum",
    "ret_10d": "reversal_momentum",
    "ret_20d": "reversal_momentum",
    "ret_60d": "reversal_momentum",
    "mom_20_5": "reversal_momentum",
    "mom_60_20": "reversal_momentum",
    "vol_5d": "risk_volatility",
    "vol_20d": "risk_volatility",
    "vol_60d": "risk_volatility",
    "drawdown_20d": "risk_volatility",
    "hl_range_20d": "risk_volatility",
    "amount_ma20_cny": "liquidity_turnover",
    "amount_zscore_20d": "liquidity_turnover",
    "turnover_rate": "liquidity_turnover",
    "turnover_rate_free_float": "liquidity_turnover",
    "turnover_rate_ma20": "liquidity_turnover",
    "volume_ratio": "liquidity_turnover",
    "pe_ttm": "valuation",
    "pb": "valuation",
    "ps_ttm": "valuation",
    "dividend_yield_ttm": "valuation",
    "ep_ttm": "valuation",
    "bp": "valuation",
    "sp_ttm": "valuation",
    "log_total_mv": "size",
    "log_circ_mv": "size",
    "has_fin_indicator": "fin_availability",
    "has_fin_income": "fin_availability",
    "has_fin_balancesheet": "fin_availability",
    "has_fin_cashflow": "fin_availability",
    "report_age_days": "fin_freshness",
    "fin_report_lag_days": "fin_freshness",
    "roe": "fin_quality",
    "roe_deducted": "fin_quality",
    "roa": "fin_quality",
    "roic": "fin_quality",
    "grossprofit_margin": "fin_quality",
    "netprofit_margin": "fin_quality",
    "debt_to_assets": "fin_leverage_liquidity",
    "current_ratio": "fin_leverage_liquidity",
    "quick_ratio": "fin_leverage_liquidity",
    "assets_to_equity": "fin_leverage_liquidity",
    "cash_ratio": "fin_leverage_liquidity",
    "ocf_to_or": "fin_cashflow",
    "ocf_to_profit": "fin_cashflow",
    "netprofit_yoy": "fin_growth",
    "operating_revenue_yoy": "fin_growth",
    "total_revenue_yoy": "fin_growth",
    "basic_eps_yoy": "fin_growth",
    "q_roe": "fin_quarter_quality",
    "q_netprofit_margin": "fin_quarter_quality",
    "q_grossprofit_margin": "fin_quarter_quality",
}


def parse_args():
    p = argparse.ArgumentParser(description="策略 1 因子贡献度分析")
    p.add_argument("--project", required=True, help="GCP project id")
    p.add_argument("--run-id", required=True)
    p.add_argument(
        "--prediction-run-id",
        default=None,
        help="Prediction/model source run_id; defaults to --run-id",
    )
    p.add_argument("--backtest-id", required=True)
    p.add_argument("--strategy-id", default="ml_pv_clf_v0")
    p.add_argument("--artifact-base-uri", required=True, help="gs://bucket/path")
    p.add_argument("--local-mirror-root", default="reports/strategy1")
    p.add_argument("--output-dataset-role", choices=OUTPUT_DATASET_ROLE_CHOICES, default="ads")
    p.add_argument("--skip-gcs-upload", action="store_true")
    p.add_argument("--p-label-horizon", type=int, default=None)
    p.add_argument("--start-date", default=None, help="Analysis start date; defaults to summary.start_date")
    p.add_argument("--end-date", default=None, help="Analysis end date; defaults to summary.end_date")
    p.add_argument("--min-daily-factor-samples", type=int, default=100)
    p.add_argument("--correlation-sample-rate", type=float, default=0.05)
    p.add_argument("--max-correlation-rows", type=int, default=100000)
    return p.parse_args()


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


def normalize_label_horizon(value: Any) -> int:
    horizon = int(value or 5)
    if horizon not in (5, 10, 20):
        raise SystemExit("--p-label-horizon must be one of 5, 10, 20")
    return horizon


def parse_json(value: Any) -> dict:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value or "{}")
    except Exception:
        return {}


def feature_value_expr(json_col: str = "tp.feature_values_json", feature_col: str = "feature") -> str:
    raw = f"PARSE_JSON({json_col}, wide_number_mode => 'round')[{feature_col}]"
    return f"""
      CASE
        WHEN LAX_BOOL({raw}) IS TRUE THEN 1.0
        WHEN LAX_BOOL({raw}) IS FALSE THEN 0.0
        ELSE LAX_FLOAT64({raw})
      END
    """


def feature_array_params(features: list[str]) -> list:
    return [bigquery.ArrayQueryParameter("features", "STRING", features)]


def weights_array_params(features: list[str], raw_weights: list[float], oriented_weights: list[float]) -> list:
    return [
        bigquery.ArrayQueryParameter("features", "STRING", features),
        bigquery.ArrayQueryParameter("raw_weights", "FLOAT64", raw_weights),
        bigquery.ArrayQueryParameter("oriented_weights", "FLOAT64", oriented_weights),
    ]


def fetch_summary(client: bigquery.Client, project: str, backtest_id: str) -> dict:
    sql = f"""
    SELECT *
    FROM `{project}.ashare_ads.ads_backtest_performance_summary`
    WHERE backtest_id = @bid
    LIMIT 1
    """
    df = bq_query(client, sql, [bigquery.ScalarQueryParameter("bid", "STRING", backtest_id)])
    if df.empty:
        raise SystemExit(f"No summary for backtest_id={backtest_id}")
    return df.iloc[0].to_dict()


def fetch_model_identity(client: bigquery.Client, project: str,
                         strategy_id: str, prediction_run_id: str) -> dict:
    sql = f"""
    SELECT reg.*
    FROM `{project}.ashare_ads.ads_model_registry` AS reg
    WHERE reg.strategy_id = @sid
      AND reg.status = 'selected'
      AND JSON_VALUE(reg.model_params_json, '$.run_id') = @rid
    ORDER BY reg.created_at DESC
    LIMIT 1
    """
    df = bq_query(client, sql, [
        bigquery.ScalarQueryParameter("sid", "STRING", strategy_id),
        bigquery.ScalarQueryParameter("rid", "STRING", prediction_run_id),
    ])
    if df.empty:
        raise SystemExit(f"No selected model for prediction_run_id={prediction_run_id}")
    row = df.iloc[0].to_dict()
    metrics = parse_json(row.get("metrics_json"))
    params = parse_json(row.get("model_params_json"))
    model_uri = row.get("model_uri") or ""
    model_path = model_uri.replace("bq://", "") if model_uri.startswith("bq://") else model_uri
    return {
        **row,
        "metrics": metrics,
        "params": params,
        "model_path": model_path,
        "score_orientation": metrics.get("score_orientation", "identity"),
        "feature_set_id": params.get("feature_set_id") or row.get("feature_version"),
    }


def fetch_feature_list(client: bigquery.Client, project: str,
                       prediction_run_id: str, start_date: str, end_date: str) -> list[str]:
    sql = f"""
    SELECT feature_column_list
    FROM `{project}.ashare_ads.ads_ml_training_panel_daily` AS tp
    WHERE tp.run_id = @rid
      AND tp.trade_date BETWEEN @sd AND @ed
      AND ARRAY_LENGTH(tp.feature_column_list) > 0
    LIMIT 1
    """
    df = bq_query(client, sql, [
        bigquery.ScalarQueryParameter("rid", "STRING", prediction_run_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
    ])
    if df.empty:
        raise SystemExit(f"No feature_column_list for prediction_run_id={prediction_run_id}")
    return [str(x) for x in list(df.iloc[0]["feature_column_list"])]


def fetch_model_weights(client: bigquery.Client, model_path: str) -> pd.DataFrame:
    if not model_path or "." not in model_path:
        raise SystemExit(f"Invalid BigQuery model path: {model_path}")
    sql = f"""
    SELECT
      processed_input AS feature,
      SAFE_CAST(weight AS FLOAT64) AS raw_coefficient,
      category_weights
    FROM ML.WEIGHTS(MODEL `{model_path}`)
    ORDER BY processed_input
    """
    return bq_query(client, sql)


def fetch_training_stats(client: bigquery.Client, project: str,
                         prediction_run_id: str, features: list[str],
                         train_start: str, train_end: str) -> pd.DataFrame:
    value_expr = feature_value_expr()
    sql = f"""
    WITH unpivoted AS (
      SELECT
        feature,
        {value_expr} AS value
      FROM `{project}.ashare_ads.ads_ml_training_panel_daily` AS tp
      CROSS JOIN UNNEST(@features) AS feature
      WHERE tp.run_id = @rid
        AND tp.split_tag = 'train'
        AND tp.trade_date BETWEEN @sd AND @ed
    )
    SELECT
      feature,
      COUNT(value) AS n_train,
      AVG(value) AS feature_mean_train,
      STDDEV_SAMP(value) AS feature_std_train,
      APPROX_QUANTILES(value, 100)[SAFE_OFFSET(50)] AS feature_median_train
    FROM unpivoted
    GROUP BY feature
    ORDER BY feature
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("rid", "STRING", prediction_run_id),
        bigquery.ScalarQueryParameter("sd", "DATE", train_start),
        bigquery.ScalarQueryParameter("ed", "DATE", train_end),
        *feature_array_params(features),
    ])


def prepare_model_weights(weights_df: pd.DataFrame, training_stats: pd.DataFrame,
                          features: list[str], score_orientation: str) -> pd.DataFrame:
    rows = []
    for _, row in weights_df.iterrows():
        feature = str(row["feature"])
        raw_coef = float(row["raw_coefficient"] or 0.0)
        factor_group = "intercept" if feature == "__INTERCEPT__" else FEATURE_GROUPS.get(feature, "unknown")
        rows.append({
            "feature": feature,
            "factor_group": factor_group,
            "is_intercept": feature == "__INTERCEPT__",
            "raw_coefficient": raw_coef,
        })
    out = pd.DataFrame.from_records(rows)
    if out.empty:
        raise SystemExit("ML.WEIGHTS returned no rows")

    out = out.merge(training_stats, on="feature", how="left")
    out["feature_in_training_panel"] = out["feature"].isin(features) | out["is_intercept"]
    out["feature_std_train"] = pd.to_numeric(out["feature_std_train"], errors="coerce").fillna(0.0)
    out["standardized_coefficient"] = out["raw_coefficient"] * out["feature_std_train"]
    orient = -1.0 if score_orientation == "reverse_probability" else 1.0
    out["score_orientation"] = score_orientation
    out["oriented_coefficient"] = out["raw_coefficient"] * orient
    out["oriented_standardized_coefficient"] = out["standardized_coefficient"] * orient
    out["abs_oriented_standardized_coefficient"] = out["oriented_standardized_coefficient"].abs()
    ordered_cols = [
        "feature", "factor_group", "is_intercept", "feature_in_training_panel",
        "score_orientation", "raw_coefficient", "feature_mean_train",
        "feature_std_train", "feature_median_train", "n_train",
        "standardized_coefficient", "oriented_coefficient",
        "oriented_standardized_coefficient", "abs_oriented_standardized_coefficient",
    ]
    return out[ordered_cols].sort_values(
        ["is_intercept", "abs_oriented_standardized_coefficient", "feature"],
        ascending=[True, False, True],
    )


def fetch_factor_rank_ic_daily(client: bigquery.Client, project: str,
                               prediction_run_id: str, features: list[str],
                               start_date: str, end_date: str,
                               label_horizon: int, min_daily_samples: int) -> pd.DataFrame:
    value_expr = feature_value_expr()
    sql = f"""
    WITH unpivoted AS (
      SELECT
        tp.split_tag,
        tp.trade_date,
        tp.sec_code,
        feature,
        {value_expr} AS feature_value,
        tp.target_return
      FROM `{project}.ashare_ads.ads_ml_training_panel_daily` AS tp
      CROSS JOIN UNNEST(@features) AS feature
      WHERE tp.run_id = @rid
        AND tp.trade_date BETWEEN @sd AND @ed
        AND tp.split_tag IN ('valid', 'test')
        AND tp.horizon = @h
        AND tp.target_return IS NOT NULL
    ),
    ranked AS (
      SELECT
        *,
        RANK() OVER (PARTITION BY split_tag, trade_date, feature ORDER BY feature_value) AS feature_rank,
        RANK() OVER (PARTITION BY split_tag, trade_date, feature ORDER BY target_return) AS target_rank
      FROM unpivoted
      WHERE feature_value IS NOT NULL
    )
    SELECT
      split_tag,
      trade_date,
      feature,
      COUNT(*) AS n,
      CORR(CAST(feature_rank AS FLOAT64), CAST(target_rank AS FLOAT64)) AS rank_ic
    FROM ranked
    GROUP BY split_tag, trade_date, feature
    HAVING n >= @min_n
    ORDER BY split_tag, trade_date, feature
    """
    return bq_query(client, sql, [
        bigquery.ScalarQueryParameter("rid", "STRING", prediction_run_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
        bigquery.ScalarQueryParameter("h", "INT64", label_horizon),
        bigquery.ScalarQueryParameter("min_n", "INT64", min_daily_samples),
        *feature_array_params(features),
    ])


def summarize_rank_ic(rank_ic_daily: pd.DataFrame) -> pd.DataFrame:
    if rank_ic_daily.empty:
        return pd.DataFrame(columns=[
            "split_tag", "feature", "factor_group", "n_days", "mean_rank_ic",
            "std_rank_ic", "icir", "positive_ratio", "median_n",
        ])
    df = rank_ic_daily.copy()
    df["rank_ic"] = pd.to_numeric(df["rank_ic"], errors="coerce")
    records = []
    for (split, feature), g in df.groupby(["split_tag", "feature"]):
        vals = g["rank_ic"].dropna()
        std = float(vals.std()) if len(vals) > 1 else np.nan
        records.append({
            "split_tag": split,
            "feature": feature,
            "factor_group": FEATURE_GROUPS.get(feature, "unknown"),
            "n_days": int(len(vals)),
            "mean_rank_ic": round(float(vals.mean()), 8) if len(vals) else None,
            "std_rank_ic": round(std, 8) if not np.isnan(std) else None,
            "icir": round(float(vals.mean() / std), 6) if len(vals) > 1 and std > 0 else None,
            "positive_ratio": round(float((vals > 0).sum() / len(vals)), 6) if len(vals) else None,
            "median_n": round(float(g["n"].median()), 2) if "n" in g else None,
        })
    return pd.DataFrame.from_records(records).sort_values(
        ["split_tag", "mean_rank_ic", "feature"],
        ascending=[True, False, True],
    )


def fetch_bucket_lift_summary(client: bigquery.Client, project: str,
                              prediction_run_id: str, features: list[str],
                              start_date: str, end_date: str,
                              label_horizon: int, min_daily_samples: int) -> pd.DataFrame:
    value_expr = feature_value_expr()
    sql = f"""
    WITH unpivoted AS (
      SELECT
        tp.split_tag,
        tp.trade_date,
        feature,
        {value_expr} AS feature_value,
        tp.target_return
      FROM `{project}.ashare_ads.ads_ml_training_panel_daily` AS tp
      CROSS JOIN UNNEST(@features) AS feature
      WHERE tp.run_id = @rid
        AND tp.trade_date BETWEEN @sd AND @ed
        AND tp.split_tag IN ('valid', 'test')
        AND tp.horizon = @h
        AND tp.target_return IS NOT NULL
    ),
    eligible AS (
      SELECT *,
             COUNT(*) OVER (PARTITION BY split_tag, trade_date, feature) AS n_daily
      FROM unpivoted
      WHERE feature_value IS NOT NULL
    ),
    bucketed AS (
      SELECT
        split_tag,
        trade_date,
        feature,
        NTILE(5) OVER (PARTITION BY split_tag, trade_date, feature ORDER BY feature_value) AS bucket,
        target_return
      FROM eligible
      WHERE n_daily >= @min_n
    ),
    daily_bucket AS (
      SELECT
        split_tag,
        trade_date,
        feature,
        bucket,
        COUNT(*) AS n,
        AVG(target_return) AS avg_target_return
      FROM bucketed
      GROUP BY split_tag, trade_date, feature, bucket
    ),
    daily_spread AS (
      SELECT
        split_tag,
        trade_date,
        feature,
        MAX(IF(bucket = 5, avg_target_return, NULL)) AS bucket_5_return,
        MAX(IF(bucket = 1, avg_target_return, NULL)) AS bucket_1_return,
        MAX(IF(bucket = 5, avg_target_return, NULL))
          - MAX(IF(bucket = 1, avg_target_return, NULL)) AS top_minus_bottom
      FROM daily_bucket
      GROUP BY split_tag, trade_date, feature
    )
    SELECT
      split_tag,
      feature,
      COUNT(*) AS n_days,
      AVG(bucket_5_return) AS bucket_5_avg_return,
      AVG(bucket_1_return) AS bucket_1_avg_return,
      AVG(top_minus_bottom) AS top_minus_bottom_mean,
      STDDEV_SAMP(top_minus_bottom) AS top_minus_bottom_std,
      APPROX_QUANTILES(top_minus_bottom, 100)[SAFE_OFFSET(50)] AS top_minus_bottom_median
    FROM daily_spread
    GROUP BY split_tag, feature
    ORDER BY split_tag, top_minus_bottom_mean DESC, feature
    """
    df = bq_query(client, sql, [
        bigquery.ScalarQueryParameter("rid", "STRING", prediction_run_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
        bigquery.ScalarQueryParameter("h", "INT64", label_horizon),
        bigquery.ScalarQueryParameter("min_n", "INT64", min_daily_samples),
        *feature_array_params(features),
    ])
    if not df.empty:
        df["factor_group"] = df["feature"].map(lambda f: FEATURE_GROUPS.get(str(f), "unknown"))
    return df


def fetch_score_contribution_summary(client: bigquery.Client, project: str,
                                     prediction_run_id: str, candidate_run_id: str,
                                     backtest_id: str, strategy_id: str,
                                     features: list[str], weights_df: pd.DataFrame,
                                     start_date: str, end_date: str) -> pd.DataFrame:
    weight_map = {
        str(r["feature"]): (
            float(r["raw_coefficient"] or 0.0),
            float(r["oriented_coefficient"] or 0.0),
        )
        for _, r in weights_df[~weights_df["is_intercept"]].iterrows()
    }
    ordered_features = [f for f in features if f in weight_map]
    raw_weights = [weight_map[f][0] for f in ordered_features]
    oriented_weights = [weight_map[f][1] for f in ordered_features]
    value_expr = feature_value_expr()
    sql = f"""
    WITH weight_table AS (
      SELECT
        feature,
        raw_weight,
        oriented_weight
      FROM UNNEST(@features) AS feature WITH OFFSET AS off
      JOIN UNNEST(@raw_weights) AS raw_weight WITH OFFSET AS raw_off
        ON off = raw_off
      JOIN UNNEST(@oriented_weights) AS oriented_weight WITH OFFSET AS oriented_off
        ON off = oriented_off
    ),
    base AS (
      SELECT
        pred.predict_date,
        pred.sec_code,
        pred.rank_pct,
        cand.is_selected_candidate,
        pos.weight AS position_weight,
        tp.feature_values_json
      FROM `{project}.ashare_ads.ads_model_prediction_daily` AS pred
      JOIN `{project}.ashare_ads.ads_ml_training_panel_daily` AS tp
        ON tp.trade_date = pred.predict_date
       AND tp.sec_code = pred.sec_code
       AND tp.run_id = @pred_rid
       AND tp.trade_date BETWEEN @sd AND @ed
      LEFT JOIN `{project}.ashare_ads.ads_stock_candidate_daily` AS cand
        ON cand.strategy_id = @sid
       AND cand.run_id = @cand_rid
       AND cand.rebalance_date = pred.predict_date
       AND cand.sec_code = pred.sec_code
       AND cand.rebalance_date BETWEEN @sd AND @ed
      LEFT JOIN `{project}.ashare_ads.ads_backtest_position_daily` AS pos
        ON pos.backtest_id = @bid
       AND pos.trade_date = pred.predict_date
       AND pos.sec_code = pred.sec_code
       AND pos.trade_date BETWEEN @sd AND @ed
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
    contrib AS (
      SELECT
        g.group_name,
        w.feature,
        {value_expr.replace("tp.feature_values_json", "g.feature_values_json")} AS feature_value,
        w.raw_weight,
        w.oriented_weight
      FROM grouped AS g
      CROSS JOIN weight_table AS w
    )
    SELECT
      group_name,
      feature,
      COUNT(feature_value) AS n,
      AVG(feature_value * raw_weight) AS raw_score_contribution_mean,
      AVG(feature_value * oriented_weight) AS oriented_score_contribution_mean,
      STDDEV_SAMP(feature_value * oriented_weight) AS oriented_score_contribution_std,
      APPROX_QUANTILES(feature_value * oriented_weight, 100)[SAFE_OFFSET(10)] AS oriented_score_contribution_p10,
      APPROX_QUANTILES(feature_value * oriented_weight, 100)[SAFE_OFFSET(50)] AS oriented_score_contribution_p50,
      APPROX_QUANTILES(feature_value * oriented_weight, 100)[SAFE_OFFSET(90)] AS oriented_score_contribution_p90
    FROM contrib
    WHERE feature_value IS NOT NULL
    GROUP BY group_name, feature
    ORDER BY group_name, oriented_score_contribution_mean DESC, feature
    """
    df = bq_query(client, sql, [
        bigquery.ScalarQueryParameter("pred_rid", "STRING", prediction_run_id),
        bigquery.ScalarQueryParameter("cand_rid", "STRING", candidate_run_id),
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sid", "STRING", strategy_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
        *weights_array_params(ordered_features, raw_weights, oriented_weights),
    ])
    if not df.empty:
        df["factor_group"] = df["feature"].map(lambda f: FEATURE_GROUPS.get(str(f), "unknown"))
    return df


def fetch_portfolio_factor_proxy(client: bigquery.Client, project: str,
                                 prediction_run_id: str, candidate_run_id: str,
                                 backtest_id: str, strategy_id: str,
                                 features: list[str], start_date: str, end_date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    value_expr = feature_value_expr()
    sql = f"""
    WITH base AS (
      SELECT
        pred.predict_date AS trade_date,
        pred.sec_code,
        feature,
        {value_expr} AS feature_value,
        tp.target_return,
        cand.is_selected_candidate,
        pos.weight AS position_weight
      FROM `{project}.ashare_ads.ads_model_prediction_daily` AS pred
      JOIN `{project}.ashare_ads.ads_ml_training_panel_daily` AS tp
        ON tp.trade_date = pred.predict_date
       AND tp.sec_code = pred.sec_code
       AND tp.run_id = @pred_rid
       AND tp.trade_date BETWEEN @sd AND @ed
      CROSS JOIN UNNEST(@features) AS feature
      LEFT JOIN `{project}.ashare_ads.ads_stock_candidate_daily` AS cand
        ON cand.strategy_id = @sid
       AND cand.run_id = @cand_rid
       AND cand.rebalance_date = pred.predict_date
       AND cand.sec_code = pred.sec_code
       AND cand.rebalance_date BETWEEN @sd AND @ed
      LEFT JOIN `{project}.ashare_ads.ads_backtest_position_daily` AS pos
        ON pos.backtest_id = @bid
       AND pos.trade_date = pred.predict_date
       AND pos.sec_code = pred.sec_code
       AND pos.trade_date BETWEEN @sd AND @ed
      WHERE pred.run_id = @pred_rid
        AND pred.predict_date BETWEEN @sd AND @ed
    ),
    stats AS (
      SELECT
        trade_date,
        feature,
        AVG(feature_value) AS mean_value,
        STDDEV_SAMP(feature_value) AS std_value
      FROM base
      WHERE feature_value IS NOT NULL
      GROUP BY trade_date, feature
    ),
    z AS (
      SELECT
        b.trade_date,
        b.sec_code,
        b.feature,
        SAFE_DIVIDE(b.feature_value - s.mean_value, NULLIF(s.std_value, 0)) AS factor_zscore,
        b.target_return,
        b.is_selected_candidate,
        b.position_weight
      FROM base AS b
      JOIN stats AS s USING (trade_date, feature)
      WHERE b.feature_value IS NOT NULL
    ),
    exposure AS (
      SELECT
        trade_date,
        feature,
        COUNTIF(position_weight > 0) AS held_position_count,
        COUNTIF(is_selected_candidate IS TRUE) AS selected_candidate_count,
        SUM(IF(position_weight > 0, position_weight * factor_zscore, 0.0)) AS portfolio_factor_exposure,
        AVG(IF(is_selected_candidate IS TRUE, factor_zscore, NULL)) AS selected_candidate_equal_weight_exposure
      FROM z
      GROUP BY trade_date, feature
    ),
    slope AS (
      SELECT
        trade_date,
        feature,
        COUNT(*) AS slope_sample_count,
        SAFE_DIVIDE(COVAR_SAMP(factor_zscore, target_return), NULLIF(VAR_SAMP(factor_zscore), 0)) AS factor_return_proxy
      FROM z
      WHERE target_return IS NOT NULL
      GROUP BY trade_date, feature
    )
    SELECT
      e.trade_date,
      e.feature,
      e.held_position_count,
      e.selected_candidate_count,
      e.portfolio_factor_exposure,
      e.selected_candidate_equal_weight_exposure,
      s.slope_sample_count,
      s.factor_return_proxy,
      e.portfolio_factor_exposure * s.factor_return_proxy AS portfolio_factor_proxy_contribution
    FROM exposure AS e
    LEFT JOIN slope AS s USING (trade_date, feature)
    ORDER BY e.trade_date, e.feature
    """
    df = bq_query(client, sql, [
        bigquery.ScalarQueryParameter("pred_rid", "STRING", prediction_run_id),
        bigquery.ScalarQueryParameter("cand_rid", "STRING", candidate_run_id),
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sid", "STRING", strategy_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
        *feature_array_params(features),
    ])
    if not df.empty:
        df["factor_group"] = df["feature"].map(lambda f: FEATURE_GROUPS.get(str(f), "unknown"))
    exposure_cols = [
        "trade_date", "feature", "factor_group", "held_position_count",
        "selected_candidate_count", "portfolio_factor_exposure",
        "selected_candidate_equal_weight_exposure",
    ]
    proxy_cols = [
        "trade_date", "feature", "factor_group", "slope_sample_count",
        "factor_return_proxy", "portfolio_factor_exposure",
        "portfolio_factor_proxy_contribution",
    ]
    exposure = df[exposure_cols].copy() if not df.empty else pd.DataFrame(columns=exposure_cols)
    proxy = df[proxy_cols].copy() if not df.empty else pd.DataFrame(columns=proxy_cols)
    return exposure, proxy


def fetch_correlation_sample(client: bigquery.Client, project: str,
                             prediction_run_id: str, features: list[str],
                             start_date: str, end_date: str,
                             sample_rate: float, max_rows: int) -> pd.DataFrame:
    sample_mod = max(1, min(10000, int(round(sample_rate * 10000))))
    sql = f"""
    SELECT
      tp.trade_date,
      tp.sec_code,
      tp.feature_values_json
    FROM `{project}.ashare_ads.ads_ml_training_panel_daily` AS tp
    WHERE tp.run_id = @rid
      AND tp.trade_date BETWEEN @sd AND @ed
      AND tp.split_tag IN ('valid', 'test')
      AND ABS(MOD(FARM_FINGERPRINT(CONCAT(tp.sec_code, CAST(tp.trade_date AS STRING))), 10000)) < @sample_mod
    LIMIT @max_rows
    """
    df = bq_query(client, sql, [
        bigquery.ScalarQueryParameter("rid", "STRING", prediction_run_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date),
        bigquery.ScalarQueryParameter("sample_mod", "INT64", sample_mod),
        bigquery.ScalarQueryParameter("max_rows", "INT64", max_rows),
    ])
    if df.empty:
        return pd.DataFrame(columns=features)

    rows = []
    for _, row in df.iterrows():
        values = parse_json(row.get("feature_values_json"))
        parsed = {}
        for feature in features:
            v = values.get(feature)
            if isinstance(v, bool):
                parsed[feature] = 1.0 if v else 0.0
            else:
                parsed[feature] = pd.to_numeric(v, errors="coerce")
        rows.append(parsed)
    return pd.DataFrame.from_records(rows, columns=features)


def compute_correlation_summary(sample_df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    records = []
    if sample_df.empty:
        for group in sorted(set(FEATURE_GROUPS.get(f, "unknown") for f in features)):
            records.append({
                "row_type": "group_summary",
                "factor_group": group,
                "feature_a": None,
                "feature_b": None,
                "factor_group_a": None,
                "factor_group_b": None,
                "correlation": None,
                "abs_correlation": None,
                "feature_count": sum(1 for f in features if FEATURE_GROUPS.get(f, "unknown") == group),
                "pair_count": 0,
                "high_corr_pair_count": 0,
                "max_abs_corr": None,
                "avg_abs_corr": None,
                "status": "insufficient_samples",
            })
        return pd.DataFrame.from_records(records)

    numeric = sample_df.apply(pd.to_numeric, errors="coerce")
    corr = numeric.corr(method="pearson", min_periods=100)
    abs_pairs_by_group: dict[str, list[float]] = {}
    high_pairs_by_group: dict[str, int] = {}

    for i, feature_a in enumerate(features):
        for feature_b in features[i + 1:]:
            val = corr.loc[feature_a, feature_b] if feature_a in corr.index and feature_b in corr.columns else np.nan
            if pd.isna(val):
                continue
            abs_val = abs(float(val))
            group_a = FEATURE_GROUPS.get(feature_a, "unknown")
            group_b = FEATURE_GROUPS.get(feature_b, "unknown")
            if group_a == group_b:
                abs_pairs_by_group.setdefault(group_a, []).append(abs_val)
                if abs_val >= 0.75:
                    high_pairs_by_group[group_a] = high_pairs_by_group.get(group_a, 0) + 1
            if abs_val >= 0.75:
                records.append({
                    "row_type": "pair",
                    "factor_group": None,
                    "feature_a": feature_a,
                    "feature_b": feature_b,
                    "factor_group_a": group_a,
                    "factor_group_b": group_b,
                    "correlation": round(float(val), 8),
                    "abs_correlation": round(abs_val, 8),
                    "feature_count": None,
                    "pair_count": None,
                    "high_corr_pair_count": None,
                    "max_abs_corr": None,
                    "avg_abs_corr": None,
                    "status": "high_corr_pair",
                })

    for group in sorted(set(FEATURE_GROUPS.get(f, "unknown") for f in features)):
        group_features = [f for f in features if FEATURE_GROUPS.get(f, "unknown") == group]
        vals = abs_pairs_by_group.get(group, [])
        pair_count = int(len(group_features) * (len(group_features) - 1) / 2)
        records.append({
            "row_type": "group_summary",
            "factor_group": group,
            "feature_a": None,
            "feature_b": None,
            "factor_group_a": None,
            "factor_group_b": None,
            "correlation": None,
            "abs_correlation": None,
            "feature_count": len(group_features),
            "pair_count": pair_count,
            "high_corr_pair_count": int(high_pairs_by_group.get(group, 0)),
            "max_abs_corr": round(float(max(vals)), 8) if vals else None,
            "avg_abs_corr": round(float(np.mean(vals)), 8) if vals else None,
            "status": "ok" if vals or pair_count == 0 else "insufficient_samples",
        })
    return pd.DataFrame.from_records(records)


def build_group_summary(weights_df: pd.DataFrame, rank_ic_summary: pd.DataFrame,
                        score_contrib: pd.DataFrame, exposure: pd.DataFrame,
                        proxy: pd.DataFrame, corr_summary: pd.DataFrame,
                        features: list[str]) -> pd.DataFrame:
    groups = sorted(set(FEATURE_GROUPS.get(f, "unknown") for f in features))
    records = []
    non_intercept_weights = weights_df[~weights_df["is_intercept"]].copy()
    for group in groups:
        group_features = [f for f in features if FEATURE_GROUPS.get(f, "unknown") == group]
        w = non_intercept_weights[non_intercept_weights["factor_group"] == group]
        ric_valid = rank_ic_summary[
            (rank_ic_summary.get("factor_group") == group)
            & (rank_ic_summary.get("split_tag") == "valid")
        ] if not rank_ic_summary.empty else pd.DataFrame()
        ric_test = rank_ic_summary[
            (rank_ic_summary.get("factor_group") == group)
            & (rank_ic_summary.get("split_tag") == "test")
        ] if not rank_ic_summary.empty else pd.DataFrame()
        held_sc = score_contrib[
            (score_contrib.get("factor_group") == group)
            & (score_contrib.get("group_name") == "held_position")
        ] if not score_contrib.empty else pd.DataFrame()
        exp = exposure[exposure.get("factor_group") == group] if not exposure.empty else pd.DataFrame()
        prox = proxy[proxy.get("factor_group") == group] if not proxy.empty else pd.DataFrame()
        corr_g = corr_summary[
            (corr_summary.get("row_type") == "group_summary")
            & (corr_summary.get("factor_group") == group)
        ] if not corr_summary.empty else pd.DataFrame()
        records.append({
            "factor_group": group,
            "feature_count": len(group_features),
            "model_abs_oriented_standardized_coefficient_sum": float(w["abs_oriented_standardized_coefficient"].sum()) if not w.empty else 0.0,
            "model_oriented_standardized_coefficient_sum": float(w["oriented_standardized_coefficient"].sum()) if not w.empty else 0.0,
            "valid_mean_rank_ic_avg": float(ric_valid["mean_rank_ic"].mean()) if not ric_valid.empty else None,
            "test_mean_rank_ic_avg": float(ric_test["mean_rank_ic"].mean()) if not ric_test.empty else None,
            "held_position_score_contribution_sum": float(held_sc["oriented_score_contribution_mean"].sum()) if not held_sc.empty else None,
            "avg_abs_portfolio_factor_exposure": float(exp["portfolio_factor_exposure"].abs().mean()) if not exp.empty else None,
            "avg_portfolio_factor_proxy_contribution": float(prox["portfolio_factor_proxy_contribution"].mean()) if not prox.empty else None,
            "high_corr_pair_count": int(corr_g["high_corr_pair_count"].iloc[0]) if not corr_g.empty and pd.notna(corr_g["high_corr_pair_count"].iloc[0]) else 0,
            "max_abs_corr": float(corr_g["max_abs_corr"].iloc[0]) if not corr_g.empty and pd.notna(corr_g["max_abs_corr"].iloc[0]) else None,
        })
    return pd.DataFrame.from_records(records).sort_values(
        "model_abs_oriented_standardized_coefficient_sum", ascending=False
    )


def top_records(df: pd.DataFrame, sort_col: str, n: int = 10,
                ascending: bool = False, columns: list[str] | None = None) -> list[dict]:
    if df.empty or sort_col not in df.columns:
        return []
    out = df.copy()
    out[sort_col] = pd.to_numeric(out[sort_col], errors="coerce")
    out = out.dropna(subset=[sort_col]).sort_values(sort_col, ascending=ascending).head(n)
    cols = columns or list(out.columns)
    records = []
    for _, row in out.iterrows():
        item = {}
        for col in cols:
            v = row.get(col)
            if pd.isna(v):
                item[col] = None
            elif isinstance(v, (np.integer,)):
                item[col] = int(v)
            elif isinstance(v, (np.floating,)):
                item[col] = float(v)
            else:
                item[col] = v
        records.append(item)
    return records


def build_summary(identity: dict, args, features: list[str], weights_df: pd.DataFrame,
                  rank_ic_summary: pd.DataFrame, score_contrib: pd.DataFrame,
                  exposure: pd.DataFrame, proxy: pd.DataFrame,
                  group_summary: pd.DataFrame, corr_summary: pd.DataFrame,
                  artifact_manifest: dict, upload_status: str,
                  factor_uri: str | None, local_path: str) -> dict:
    non_intercept = weights_df[~weights_df["is_intercept"]]
    held = score_contrib[score_contrib["group_name"] == "held_position"] if not score_contrib.empty else pd.DataFrame()
    test_ric = rank_ic_summary[rank_ic_summary["split_tag"] == "test"] if not rank_ic_summary.empty else pd.DataFrame()
    exp_summary = exposure.groupby(["feature", "factor_group"], as_index=False).agg(
        avg_abs_portfolio_factor_exposure=("portfolio_factor_exposure", lambda x: float(pd.to_numeric(x, errors="coerce").abs().mean())),
        avg_portfolio_factor_exposure=("portfolio_factor_exposure", "mean"),
    ) if not exposure.empty else pd.DataFrame()
    high_corr_groups = group_summary[group_summary["high_corr_pair_count"] > 0] if not group_summary.empty else pd.DataFrame()
    return {
        "factor_attribution_version": ATTRIBUTION_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "prediction_run_id": args.prediction_run_id,
        "backtest_id": args.backtest_id,
        "strategy_id": args.strategy_id,
        "model_id": identity.get("model_id"),
        "model_path": identity.get("model_path"),
        "feature_set_id": identity.get("feature_set_id"),
        "label_horizon": args.p_label_horizon,
        "score_orientation": identity.get("score_orientation"),
        "upload_status": upload_status,
        "factor_attribution_uri": factor_uri,
        "local_factor_attribution_path": local_path,
        "factor_model_feature_count": int(len(non_intercept)),
        "factor_training_feature_count": int(len(features)),
        "factor_model_feature_coverage_count": int(non_intercept["feature_in_training_panel"].sum()),
        "factor_unknown_group_count": int((non_intercept["factor_group"] == "unknown").sum()),
        "factor_group_count": int(group_summary["factor_group"].nunique()) if not group_summary.empty else 0,
        "rank_ic_summary_rows": int(len(rank_ic_summary)),
        "score_contribution_summary_rows": int(len(score_contrib)),
        "portfolio_exposure_rows": int(len(exposure)),
        "correlation_summary_rows": int(len(corr_summary)),
        "limitations": {
            "non_ablation": True,
            "non_causal": True,
            "proxy_only": True,
            "collinearity_sensitive": True,
        },
        "top_positive_score_factors": top_records(
            held, "oriented_score_contribution_mean", 10, False,
            ["feature", "factor_group", "oriented_score_contribution_mean", "n"],
        ),
        "top_negative_score_factors": top_records(
            held, "oriented_score_contribution_mean", 10, True,
            ["feature", "factor_group", "oriented_score_contribution_mean", "n"],
        ),
        "top_positive_rankic_factors": top_records(
            test_ric, "mean_rank_ic", 10, False,
            ["feature", "factor_group", "mean_rank_ic", "icir", "n_days"],
        ),
        "top_negative_rankic_factors": top_records(
            test_ric, "mean_rank_ic", 10, True,
            ["feature", "factor_group", "mean_rank_ic", "icir", "n_days"],
        ),
        "top_portfolio_exposure_factors": top_records(
            exp_summary, "avg_abs_portfolio_factor_exposure", 10, False,
            ["feature", "factor_group", "avg_abs_portfolio_factor_exposure", "avg_portfolio_factor_exposure"],
        ),
        "top_score_factor_groups": top_records(
            group_summary, "model_abs_oriented_standardized_coefficient_sum", 10, False,
            ["factor_group", "feature_count", "model_abs_oriented_standardized_coefficient_sum",
             "held_position_score_contribution_sum", "test_mean_rank_ic_avg"],
        ),
        "high_collinearity_factor_groups": top_records(
            high_corr_groups, "high_corr_pair_count", 10, False,
            ["factor_group", "feature_count", "high_corr_pair_count", "max_abs_corr"],
        ),
        "factor_attribution_artifact_manifest": artifact_manifest,
    }


def df_to_md(df: pd.DataFrame, cols: list[str], n: int = 10) -> str:
    if df.empty:
        return "无数据。"
    sub = df[cols].head(n).copy()
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---" for _ in cols]) + "|"]
    for _, row in sub.iterrows():
        vals = []
        for col in cols:
            v = row.get(col)
            if isinstance(v, float):
                vals.append(f"{v:.6f}")
            elif pd.isna(v):
                vals.append("")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def render_markdown(summary: dict, group_summary: pd.DataFrame,
                    weights_df: pd.DataFrame, rank_ic_summary: pd.DataFrame,
                    score_contrib: pd.DataFrame, exposure: pd.DataFrame,
                    corr_summary: pd.DataFrame) -> str:
    lines = []
    lines.append("# 策略 1 因子贡献度分析\n")
    lines.append(f"- **版本**: `{ATTRIBUTION_VERSION}`")
    lines.append(f"- **run_id**: `{summary['run_id']}`")
    if summary["prediction_run_id"] != summary["run_id"]:
        lines.append(f"- **prediction_run_id**: `{summary['prediction_run_id']}`")
    lines.append(f"- **backtest_id**: `{summary['backtest_id']}`")
    lines.append(f"- **model_id**: `{summary.get('model_id')}`")
    lines.append(f"- **feature_set_id**: `{summary.get('feature_set_id')}`")
    lines.append(f"- **score_orientation**: `{summary.get('score_orientation')}`")
    lines.append(f"- **生成时间**: {summary['generated_utc']}")
    lines.append("")

    lines.append("## 一句话摘要\n")
    top_groups = summary.get("top_score_factor_groups", [])
    group_names = "、".join(g["factor_group"] for g in top_groups[:3]) if top_groups else "无"
    lines.append(
        f"当前模型分数贡献主要集中在 `{group_names}`；以下结果是基于已训练模型、"
        "现有预测和现有持仓计算的贡献度 proxy，不是消融实验，也不是因果证明。"
    )
    lines.append("")

    lines.append("## 因子组贡献排序\n")
    lines.append(df_to_md(group_summary, [
        "factor_group", "feature_count",
        "model_abs_oriented_standardized_coefficient_sum",
        "held_position_score_contribution_sum",
        "test_mean_rank_ic_avg",
        "avg_abs_portfolio_factor_exposure",
        "high_corr_pair_count",
    ], 15))
    lines.append("")

    lines.append("## 模型分数贡献因子\n")
    held = score_contrib[score_contrib["group_name"] == "held_position"] if not score_contrib.empty else pd.DataFrame()
    lines.append("### 正向贡献 top 10\n")
    lines.append(df_to_md(
        held.sort_values("oriented_score_contribution_mean", ascending=False) if not held.empty else held,
        ["feature", "factor_group", "oriented_score_contribution_mean", "n"],
        10,
    ))
    lines.append("\n### 负向贡献 top 10\n")
    lines.append(df_to_md(
        held.sort_values("oriented_score_contribution_mean", ascending=True) if not held.empty else held,
        ["feature", "factor_group", "oriented_score_contribution_mean", "n"],
        10,
    ))
    lines.append("")

    lines.append("## 单因子 RankIC\n")
    test_ric = rank_ic_summary[rank_ic_summary["split_tag"] == "test"] if not rank_ic_summary.empty else pd.DataFrame()
    lines.append("### Test 正向 RankIC top 10\n")
    lines.append(df_to_md(
        test_ric.sort_values("mean_rank_ic", ascending=False) if not test_ric.empty else test_ric,
        ["feature", "factor_group", "mean_rank_ic", "icir", "n_days"],
        10,
    ))
    lines.append("\n### Test 负向 RankIC top 10\n")
    lines.append(df_to_md(
        test_ric.sort_values("mean_rank_ic", ascending=True) if not test_ric.empty else test_ric,
        ["feature", "factor_group", "mean_rank_ic", "icir", "n_days"],
        10,
    ))
    lines.append("")

    lines.append("## 当前持仓因子暴露\n")
    if not exposure.empty:
        exp = exposure.groupby(["feature", "factor_group"], as_index=False).agg(
            avg_abs_portfolio_factor_exposure=("portfolio_factor_exposure", lambda x: float(pd.to_numeric(x, errors="coerce").abs().mean())),
            avg_portfolio_factor_exposure=("portfolio_factor_exposure", "mean"),
        ).sort_values("avg_abs_portfolio_factor_exposure", ascending=False)
    else:
        exp = pd.DataFrame()
    lines.append(df_to_md(exp, [
        "feature", "factor_group", "avg_abs_portfolio_factor_exposure", "avg_portfolio_factor_exposure",
    ], 10))
    lines.append("")

    lines.append("## 共线性提示\n")
    high_pairs = corr_summary[corr_summary["row_type"] == "pair"] if not corr_summary.empty else pd.DataFrame()
    if high_pairs.empty:
        lines.append("未发现 `ABS(correlation) >= 0.75` 的高相关因子对，或样本不足。")
    else:
        lines.append(df_to_md(high_pairs.sort_values("abs_correlation", ascending=False), [
            "feature_a", "feature_b", "factor_group_a", "factor_group_b", "correlation", "abs_correlation",
        ], 20))
    lines.append("")

    lines.append("## 解释边界\n")
    lines.append("- 本报告不做消融实验，也不做 drop-one-factor / drop-one-group 重训。")
    lines.append("- 本报告不把任何因子结论解释为因果关系。")
    lines.append("- 组合因子归因是 proxy，使用持仓暴露乘以单因子日截面收益斜率估计收益关联。")
    lines.append("- 多重共线性会影响单因子系数排名，正式解读应优先看因子组。")
    lines.append("- proxy contribution 不要求加总等于组合每日收益，也不得作为总 P&L 分解。")
    lines.append("")

    lines.append("## 附件\n")
    for name in REQUIRED_ARTIFACTS:
        lines.append(f"- `{name}`")
    return "\n".join(lines)


def write_csv(path: Path, df: pd.DataFrame):
    df.to_csv(path, index=False, encoding="utf-8-sig")


def write_json(path: Path, obj: dict):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_artifact_manifest(local_dir: Path, row_counts: dict[str, int],
                            gcs_uri: str | None = None) -> dict:
    manifest = {}
    for path in sorted(local_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(local_dir).as_posix()
        item = {
            "sha256": file_sha256(path),
            "rows": row_counts.get(rel, 1),
            "local_path": str(path),
        }
        if gcs_uri is not None:
            item["uri"] = f"{gcs_uri}/{rel}"
        manifest[rel] = item
    return manifest


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


def write_attribution_status(client: bigquery.Client, project: str,
                             backtest_id: str, patch: dict):
    base = "PARSE_JSON(COALESCE(bs.metrics_json, '{}'), wide_number_mode => 'round')"
    if patch.get("factor_attribution_uri") is None:
        base = f"JSON_REMOVE({base}, '$.factor_attribution_uri')"

    json_expr = base
    params = [bigquery.ScalarQueryParameter("bid", "STRING", backtest_id)]
    fragments = []
    for idx, (key, value) in enumerate(patch.items()):
        if value is None:
            fragments.append(f" '$.{key}', NULL")
            continue
        pname = f"p{idx}"
        if isinstance(value, bool):
            fragments.append(f" '$.{key}', @{pname}")
            params.append(bigquery.ScalarQueryParameter(pname, "BOOL", value))
        elif isinstance(value, int):
            fragments.append(f" '$.{key}', @{pname}")
            params.append(bigquery.ScalarQueryParameter(pname, "INT64", value))
        elif isinstance(value, float):
            fragments.append(f" '$.{key}', @{pname}")
            params.append(bigquery.ScalarQueryParameter(pname, "FLOAT64", value))
        elif isinstance(value, (dict, list)):
            fragments.append(f" '$.{key}', PARSE_JSON(@{pname})")
            params.append(bigquery.ScalarQueryParameter(
                pname, "STRING", json.dumps(value, ensure_ascii=False, default=str)
            ))
        else:
            fragments.append(f" '$.{key}', @{pname}")
            params.append(bigquery.ScalarQueryParameter(pname, "STRING", str(value)))

    if fragments:
        json_expr = f"JSON_SET({json_expr},\n{','.join(fragments)}\n)"

    sql = f"""
    UPDATE `{project}.ashare_ads.ads_backtest_performance_summary` AS bs
    SET bs.metrics_json = TO_JSON_STRING({json_expr})
    WHERE bs.backtest_id = @bid
    """
    sql = rewrite_sql_dataset_role(
        sql,
        dataset_role=OUTPUT_DATASET_ROLE,
        project=client.project,
    )
    client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
    print("  Updated summary.metrics_json (factor_attribution_status=completed)")


def main():
    global OUTPUT_DATASET_ROLE
    args = parse_args()
    OUTPUT_DATASET_ROLE = args.output_dataset_role
    args.prediction_run_id = args.prediction_run_id or args.run_id
    bq = make_bq_client(args.project)

    print("读取回测 summary...")
    summary_row = fetch_summary(bq, args.project, args.backtest_id)
    summary_metrics = parse_json(summary_row.get("metrics_json"))
    analysis_start = args.start_date or str(summary_row.get("start_date", "2024-01-01"))
    analysis_end = args.end_date or str(summary_row.get("end_date", "2025-12-31"))

    print("读取 selected model...")
    identity = fetch_model_identity(bq, args.project, args.strategy_id, args.prediction_run_id)
    model_params = identity.get("params", {})
    args.p_label_horizon = normalize_label_horizon(
        args.p_label_horizon
        or summary_metrics.get("label_horizon")
        or model_params.get("label_horizon")
    )
    train_start = str(model_params.get("train_start_date") or identity.get("train_start_date") or "2019-04-03")
    train_end = str(model_params.get("train_end_date") or identity.get("train_end_date") or "2023-12-31")
    valid_start = str(model_params.get("valid_start_date") or identity.get("valid_start_date") or "2024-01-01")
    test_end = analysis_end

    print("读取训练特征清单...")
    features = fetch_feature_list(bq, args.project, args.prediction_run_id, train_start, test_end)
    unknown_features = sorted([f for f in features if f not in FEATURE_GROUPS])
    if unknown_features:
        print(f"  ⚠ 未映射因子组: {unknown_features}", file=sys.stderr)

    print("读取模型系数...")
    raw_weights = fetch_model_weights(bq, identity["model_path"])

    print("计算训练期特征统计...")
    training_stats = fetch_training_stats(
        bq, args.project, args.prediction_run_id, features, train_start, train_end)
    weights = prepare_model_weights(
        raw_weights, training_stats, features, identity.get("score_orientation", "identity"))

    print("计算单因子 RankIC...")
    rank_ic_daily = fetch_factor_rank_ic_daily(
        bq, args.project, args.prediction_run_id, features,
        valid_start, test_end, args.p_label_horizon,
        args.min_daily_factor_samples,
    )
    rank_ic_summary = summarize_rank_ic(rank_ic_daily)

    print("计算单因子 bucket lift...")
    bucket_lift = fetch_bucket_lift_summary(
        bq, args.project, args.prediction_run_id, features,
        valid_start, test_end, args.p_label_horizon,
        args.min_daily_factor_samples,
    )

    print("计算模型分数贡献...")
    score_contrib = fetch_score_contribution_summary(
        bq, args.project, args.prediction_run_id, args.run_id,
        args.backtest_id, args.strategy_id, features, weights,
        analysis_start, analysis_end,
    )

    print("计算组合因子暴露和归因 proxy...")
    exposure, proxy = fetch_portfolio_factor_proxy(
        bq, args.project, args.prediction_run_id, args.run_id,
        args.backtest_id, args.strategy_id, features,
        analysis_start, analysis_end,
    )

    print("计算因子相关性摘要...")
    corr_sample = fetch_correlation_sample(
        bq, args.project, args.prediction_run_id, features,
        valid_start, test_end, args.correlation_sample_rate,
        args.max_correlation_rows,
    )
    corr_summary = compute_correlation_summary(corr_sample, features)

    print("汇总因子组...")
    group_summary = build_group_summary(
        weights, rank_ic_summary, score_contrib, exposure, proxy, corr_summary, features)

    factor_dir = (
        Path(args.local_mirror_root)
        / f"ml_pv_clf_v0/run_id={args.run_id}/backtest_id={args.backtest_id}/factor_attribution"
    )
    factor_dir.mkdir(parents=True, exist_ok=True)
    row_counts: dict[str, int] = {}

    print("写入 artifact...")
    artifact_frames = {
        "factor_model_weights.csv": weights,
        "factor_rank_ic_daily.csv": rank_ic_daily,
        "factor_rank_ic_summary.csv": rank_ic_summary,
        "factor_bucket_lift_summary.csv": bucket_lift,
        "factor_score_contribution_summary.csv": score_contrib,
        "portfolio_factor_exposure_daily.csv": exposure,
        "portfolio_factor_attribution_proxy.csv": proxy,
        "factor_group_summary.csv": group_summary,
        "factor_correlation_summary.csv": corr_summary,
    }
    for name, df in artifact_frames.items():
        write_csv(factor_dir / name, df)
        row_counts[name] = int(len(df))

    gcs_uri = (
        f"{args.artifact_base_uri}/ml_pv_clf_v0/"
        f"run_id={args.run_id}/backtest_id={args.backtest_id}/factor_attribution"
    )

    def write_summary_artifacts(status: str, uri: str | None) -> dict:
        manifest = build_artifact_manifest(factor_dir, row_counts, uri)
        factor_summary_obj = build_summary(
            identity, args, features, weights, rank_ic_summary, score_contrib,
            exposure, proxy, group_summary, corr_summary, manifest,
            status, uri, str(factor_dir),
        )
        write_json(factor_dir / "factor_attribution_summary.json", factor_summary_obj)
        row_counts["factor_attribution_summary.json"] = 1
        (factor_dir / "factor_attribution.md").write_text(
            render_markdown(
                factor_summary_obj, group_summary, weights, rank_ic_summary,
                score_contrib, exposure, corr_summary,
            ),
            encoding="utf-8",
        )
        row_counts["factor_attribution.md"] = 1
        manifest = build_artifact_manifest(factor_dir, row_counts, uri)
        write_json(factor_dir / "artifact_manifest.json", manifest)
        row_counts["artifact_manifest.json"] = 1
        return build_artifact_manifest(factor_dir, row_counts, uri)

    upload_status = "skipped" if args.skip_gcs_upload else "uploaded"
    factor_uri = None if args.skip_gcs_upload else gcs_uri
    final_manifest = write_summary_artifacts(upload_status, factor_uri)

    if not args.skip_gcs_upload:
        try:
            print(f"上传至 GCS: {gcs_uri}")
            upload_dir_to_gcs(args.project, factor_dir, gcs_uri)
        except Exception as e:
            print(f"  ⚠ GCS 上传失败: {e}", file=sys.stderr)
            upload_status, factor_uri = "skipped", None
            final_manifest = write_summary_artifacts(upload_status, factor_uri)

    rank_ic_valid_rows = (
        int((rank_ic_summary["split_tag"] == "valid").sum())
        if not rank_ic_summary.empty else 0
    )
    rank_ic_test_rows = (
        int((rank_ic_summary["split_tag"] == "test").sum())
        if not rank_ic_summary.empty else 0
    )
    score_groups = sorted(score_contrib["group_name"].dropna().unique().tolist()) if not score_contrib.empty else []
    position_holding_days = int(
        exposure.loc[exposure["held_position_count"] > 0, "trade_date"].nunique()
    ) if not exposure.empty else 0
    exposure_days = int(exposure["trade_date"].nunique()) if not exposure.empty else 0
    corr_group_rows = int((corr_summary["row_type"] == "group_summary").sum()) if not corr_summary.empty else 0
    final_summary = build_summary(
        identity, args, features, weights, rank_ic_summary, score_contrib,
        exposure, proxy, group_summary, corr_summary, final_manifest,
        upload_status, factor_uri, str(factor_dir),
    )

    patch = {
        "factor_attribution_status": "completed",
        "factor_attribution_upload_status": upload_status,
        "factor_attribution_version": ATTRIBUTION_VERSION,
        "factor_attribution_generated_utc": datetime.now(timezone.utc).isoformat(),
        "factor_attribution_uri": factor_uri,
        "local_factor_attribution_path": str(factor_dir),
        "factor_attribution_prediction_run_id": args.prediction_run_id,
        "factor_attribution_feature_set_id": identity.get("feature_set_id"),
        "factor_attribution_model_id": identity.get("model_id"),
        "factor_model_feature_count": int((~weights["is_intercept"]).sum()),
        "factor_training_feature_count": int(len(features)),
        "factor_model_feature_coverage_count": int(
            weights.loc[~weights["is_intercept"], "feature_in_training_panel"].sum()
        ),
        "factor_unknown_group_count": int(
            (weights.loc[~weights["is_intercept"], "factor_group"] == "unknown").sum()
        ),
        "factor_group_count": int(group_summary["factor_group"].nunique()) if not group_summary.empty else 0,
        "factor_rank_ic_summary_rows": int(len(rank_ic_summary)),
        "factor_rank_ic_valid_rows": rank_ic_valid_rows,
        "factor_rank_ic_test_rows": rank_ic_test_rows,
        "factor_bucket_lift_summary_rows": int(len(bucket_lift)),
        "factor_score_contribution_summary_rows": int(len(score_contrib)),
        "factor_score_contribution_groups": score_groups,
        "factor_portfolio_exposure_days": exposure_days,
        "factor_position_holding_days": position_holding_days,
        "factor_correlation_summary_rows": int(len(corr_summary)),
        "factor_correlation_group_summary_rows": corr_group_rows,
        "factor_attribution_limitations_included": True,
        "top_positive_score_factors": final_summary["top_positive_score_factors"],
        "top_negative_score_factors": final_summary["top_negative_score_factors"],
        "top_positive_rankic_factors": final_summary["top_positive_rankic_factors"],
        "top_negative_rankic_factors": final_summary["top_negative_rankic_factors"],
        "top_portfolio_exposure_factors": final_summary["top_portfolio_exposure_factors"],
        "top_score_factor_groups": final_summary["top_score_factor_groups"],
        "high_collinearity_factor_groups": final_summary["high_collinearity_factor_groups"],
        "factor_attribution_artifact_manifest": final_manifest,
    }

    print("回写 summary...")
    write_attribution_status(bq, args.project, args.backtest_id, patch)
    print(f"完成。本地: {factor_dir}")


if __name__ == "__main__":
    main()
