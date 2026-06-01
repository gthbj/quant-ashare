#!/usr/bin/env python3
"""Strategy 1 backtest report renderer.

Reads metrics from BigQuery ADS tables (or exported metrics.json),
renders Markdown/HTML report and PNG charts, uploads to GCS,
and writes a local mirror under reports/.

Usage:
    python scripts/strategy1/render_report.py \
        --project data-aquarium \
        --backtest-id bt_s1_bqml_20260601_01 \
        --run-id s1_bqml_20260601_01 \
        --artifact-base-uri gs://ashare-artifacts/reports/strategy1 \
        --local-mirror-root reports/strategy1

Requirements: google-cloud-bigquery, google-cloud-storage, matplotlib, jinja2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from google.cloud import bigquery, storage
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
except ImportError as e:
    print(f"Missing dependency: {e}. Install: pip install google-cloud-bigquery google-cloud-storage matplotlib", file=sys.stderr)
    sys.exit(1)


def parse_args():
    p = argparse.ArgumentParser(description="Render strategy 1 backtest report")
    p.add_argument("--project", required=True)
    p.add_argument("--backtest-id", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--strategy-id", default="ml_pv_clf_v0")
    p.add_argument("--artifact-base-uri", required=True, help="gs://bucket/path")
    p.add_argument("--local-mirror-root", default="reports/strategy1")
    p.add_argument("--skip-gcs-upload", action="store_true")
    return p.parse_args()


def fetch_nav(client, project: str, backtest_id: str):
    sql = f"""
    SELECT trade_date, nav, daily_return, benchmark_return, excess_return
    FROM `{project}.ashare_ads.ads_backtest_nav_daily`
    WHERE backtest_id = @backtest_id
    ORDER BY trade_date
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("backtest_id", "STRING", backtest_id)]
    )
    return client.query(sql, job_config=job_config).to_dataframe()


def fetch_summary(client, project: str, backtest_id: str):
    sql = f"""
    SELECT *
    FROM `{project}.ashare_ads.ads_backtest_performance_summary`
    WHERE backtest_id = @backtest_id
    LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("backtest_id", "STRING", backtest_id)]
    )
    rows = client.query(sql, job_config=job_config).to_dataframe()
    return rows.iloc[0].to_dict() if len(rows) > 0 else {}


def fetch_model_info(client, project: str, strategy_id: str):
    sql = f"""
    SELECT model_id, model_params_json, metrics_json, model_uri
    FROM `{project}.ashare_ads.ads_model_registry`
    WHERE strategy_id = @strategy_id AND status = 'selected'
    ORDER BY created_at DESC LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("strategy_id", "STRING", strategy_id)]
    )
    rows = client.query(sql, job_config=job_config).to_dataframe()
    return rows.iloc[0].to_dict() if len(rows) > 0 else {}


def plot_nav(nav_df, out_path: Path):
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(nav_df["trade_date"], nav_df["nav"], label="Portfolio NAV", linewidth=1.2)
    bench_nav = (1 + nav_df["benchmark_return"].fillna(0)).cumprod()
    ax.plot(nav_df["trade_date"], bench_nav, label="Benchmark", linewidth=1.0, alpha=0.7)
    ax.set_title("NAV Curve")
    ax.set_ylabel("NAV")
    ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_drawdown(nav_df, out_path: Path):
    nav_series = nav_df["nav"]
    running_max = nav_series.cummax()
    drawdown = nav_series / running_max - 1
    fig, ax = plt.subplots(figsize=(12, 3))
    ax.fill_between(nav_df["trade_date"], drawdown, 0, alpha=0.5, color="red")
    ax.set_title("Drawdown")
    ax.set_ylabel("Drawdown")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def render_markdown(summary: dict, model_info: dict, args) -> str:
    lines = [
        f"# Strategy 1 Backtest Report",
        f"",
        f"- **backtest_id**: `{args.backtest_id}`",
        f"- **run_id**: `{args.run_id}`",
        f"- **strategy_id**: `{args.strategy_id}`",
        f"- **model_id**: `{model_info.get('model_id', 'N/A')}`",
        f"- **generated**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"",
        f"## Performance Summary",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Period | {summary.get('start_date', '')} to {summary.get('end_date', '')} |",
        f"| Total Return | {summary.get('total_return', 0):.4f} |",
        f"| Annual Return | {summary.get('annual_return', 0):.4f} |",
        f"| Annual Vol | {summary.get('annual_vol', 0):.4f} |",
        f"| Sharpe | {summary.get('sharpe', 0):.4f} |",
        f"| Max Drawdown | {summary.get('max_drawdown', 0):.4f} |",
        f"| Excess Return | {summary.get('excess_return', 0):.4f} |",
        f"| Information Ratio | {summary.get('information_ratio', 0):.4f} |",
        f"| Cost (bps) | {summary.get('cost_bps', 0):.0f} |",
        f"| Benchmark | `{summary.get('benchmark_sec_code', '')}` |",
        f"",
        f"## Model Selection",
        f"",
        f"```json",
        f"{json.dumps(json.loads(model_info.get('metrics_json', '{}') or '{}'), indent=2)}",
        f"```",
        f"",
        f"## Charts",
        f"",
        f"![NAV](assets/nav.png)",
        f"",
        f"![Drawdown](assets/drawdown.png)",
        f"",
        f"---",
        f"",
        f"*OQ-010 parameters are example values, not business-final.*",
    ]
    return "\n".join(lines)


def upload_directory_to_gcs(local_dir: Path, gcs_uri: str, skip: bool):
    if skip:
        print(f"Skipping GCS upload (--skip-gcs-upload). Local: {local_dir}")
        return
    bucket_name = gcs_uri.replace("gs://", "").split("/")[0]
    prefix = "/".join(gcs_uri.replace("gs://", "").split("/")[1:])
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    for path in local_dir.rglob("*"):
        if path.is_file():
            blob_name = f"{prefix}/{path.relative_to(local_dir)}"
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(str(path))
            print(f"  Uploaded {blob_name}")


def main():
    args = parse_args()
    bq_client = bigquery.Client(project=args.project)

    report_dir = Path(args.local_mirror_root) / f"ml_pv_clf_v0/run_id={args.run_id}/backtest_id={args.backtest_id}"
    assets_dir = report_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    print("Fetching data from BigQuery...")
    nav_df = fetch_nav(bq_client, args.project, args.backtest_id)
    summary = fetch_summary(bq_client, args.project, args.backtest_id)
    model_info = fetch_model_info(bq_client, args.project, args.strategy_id)

    print("Rendering charts...")
    plot_nav(nav_df, assets_dir / "nav.png")
    plot_drawdown(nav_df, assets_dir / "drawdown.png")

    print("Rendering report...")
    md_content = render_markdown(summary, model_info, args)
    (report_dir / "report.md").write_text(md_content)

    metrics = {
        "backtest_id": args.backtest_id,
        "run_id": args.run_id,
        "strategy_id": args.strategy_id,
        "model_id": model_info.get("model_id"),
        "summary": summary,
        "model_selection": json.loads(model_info.get("metrics_json", "{}") or "{}"),
        "generated_utc": datetime.utcnow().isoformat(),
    }
    (report_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))

    gcs_uri = f"{args.artifact_base_uri}/ml_pv_clf_v0/run_id={args.run_id}/backtest_id={args.backtest_id}"
    print(f"Uploading to GCS: {gcs_uri}")
    upload_directory_to_gcs(report_dir, gcs_uri, args.skip_gcs_upload)

    print(f"Done. Local mirror: {report_dir}")
    print(f"GCS URI: {gcs_uri}")


if __name__ == "__main__":
    main()
