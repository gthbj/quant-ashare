#!/usr/bin/env python3
"""Strategy 1 backtest report renderer.

Reads metrics from BigQuery ADS tables, renders Markdown + HTML report
and PNG charts, uploads to GCS, writes a local mirror, and updates
ads_backtest_performance_summary.metrics_json with report_uri.

Usage:
    python scripts/strategy1/render_report.py \
        --project data-aquarium \
        --backtest-id bt_s1_bqml_20260601_01 \
        --run-id s1_bqml_20260601_01 \
        --artifact-base-uri gs://ashare-artifacts/reports/strategy1 \
        --local-mirror-root reports/strategy1

Requirements: google-cloud-bigquery, google-cloud-storage, matplotlib, pandas
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    from google.cloud import bigquery, storage
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import pandas as pd
except ImportError as e:
    print(f"Missing dependency: {e}.", file=sys.stderr)
    print("Install: pip install google-cloud-bigquery google-cloud-storage matplotlib pandas db-dtypes", file=sys.stderr)
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


def fetch_summary(client: bigquery.Client, project: str, backtest_id: str) -> dict:
    sql = f"""
    SELECT bs.* FROM `{project}.ashare_ads.ads_backtest_performance_summary` AS bs
    WHERE bs.backtest_id = @bid LIMIT 1
    """
    job_cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id)])
    rows = client.query(sql, job_config=job_cfg).to_dataframe()
    if rows.empty:
        raise SystemExit(f"No summary found for backtest_id={backtest_id}")
    return rows.iloc[0].to_dict()


def fetch_nav(client: bigquery.Client, project: str, backtest_id: str,
              start_date: str, end_date: str) -> pd.DataFrame:
    sql = f"""
    SELECT n.trade_date, n.nav, n.daily_return, n.benchmark_return, n.excess_return
    FROM `{project}.ashare_ads.ads_backtest_nav_daily` AS n
    WHERE n.backtest_id = @bid
      AND n.trade_date BETWEEN @sd AND @ed
    ORDER BY n.trade_date
    """
    job_cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("sd", "DATE", start_date),
        bigquery.ScalarQueryParameter("ed", "DATE", end_date)])
    df = client.query(sql, job_config=job_cfg).to_dataframe()
    if df.empty:
        raise SystemExit(f"No NAV data for backtest_id={backtest_id}")
    return df


def fetch_model_info(client: bigquery.Client, project: str,
                     strategy_id: str, run_id: str) -> dict:
    sql = f"""
    SELECT reg.model_id, reg.model_params_json, reg.metrics_json, reg.model_uri
    FROM `{project}.ashare_ads.ads_model_registry` AS reg
    WHERE reg.strategy_id = @sid AND reg.status = 'selected'
      AND JSON_VALUE(reg.model_params_json, '$.run_id') = @rid
    ORDER BY reg.created_at DESC LIMIT 1
    """
    job_cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("sid", "STRING", strategy_id),
        bigquery.ScalarQueryParameter("rid", "STRING", run_id)])
    rows = client.query(sql, job_config=job_cfg).to_dataframe()
    return rows.iloc[0].to_dict() if not rows.empty else {}


def plot_nav(nav_df: pd.DataFrame, out_path: Path):
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(nav_df["trade_date"], nav_df["nav"], label="Portfolio NAV", linewidth=1.2)
    bench = (1 + nav_df["benchmark_return"].fillna(0)).cumprod()
    ax.plot(nav_df["trade_date"], bench, label="Benchmark", linewidth=1.0, alpha=0.7)
    ax.set_title("NAV Curve"); ax.set_ylabel("NAV"); ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(out_path, dpi=150); plt.close(fig)


def plot_drawdown(nav_df: pd.DataFrame, out_path: Path):
    dd = nav_df["nav"] / nav_df["nav"].cummax() - 1
    fig, ax = plt.subplots(figsize=(12, 3))
    ax.fill_between(nav_df["trade_date"], dd, 0, alpha=0.5, color="red")
    ax.set_title("Drawdown"); ax.set_ylabel("Drawdown")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(out_path, dpi=150); plt.close(fig)


def fmt(v, decimals=4):
    if v is None or (isinstance(v, float) and v != v):
        return "N/A"
    return f"{v:.{decimals}f}"


def render_markdown(summary: dict, model_info: dict, args) -> str:
    m = json.loads(summary.get("metrics_json") or "{}")
    lines = [
        "# Strategy 1 Backtest Report", "",
        f"- **backtest_id**: `{args.backtest_id}`",
        f"- **run_id**: `{args.run_id}`",
        f"- **strategy_id**: `{args.strategy_id}`",
        f"- **model_id**: `{model_info.get('model_id', 'N/A')}`",
        f"- **generated**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", "",
        "## Performance Summary", "",
        "| Metric | Value |", "|---|---|",
        f"| Period | {summary.get('start_date', '')} to {summary.get('end_date', '')} |",
        f"| Total Return | {fmt(summary.get('total_return'))} |",
        f"| Annual Return | {fmt(summary.get('annual_return'))} |",
        f"| Annual Vol | {fmt(summary.get('annual_vol'))} |",
        f"| Sharpe | {fmt(summary.get('sharpe'))} |",
        f"| Max Drawdown | {fmt(summary.get('max_drawdown'))} |",
        f"| Excess Return | {fmt(summary.get('excess_return'))} |",
        f"| Information Ratio | {fmt(summary.get('information_ratio'))} |",
        f"| Buy Fail Rate | {fmt(m.get('buy_fail_rate'))} |",
        f"| Sell Delay Rate | {fmt(m.get('sell_delay_rate'))} |",
        f"| Sell Blocked Count | {m.get('sell_blocked_count', 'N/A')} |",
        f"| Cost (bps) | {fmt(summary.get('cost_bps'), 0)} |",
        f"| Benchmark | `{summary.get('benchmark_sec_code', '')}` |", "",
        "## Model Selection", "",
        "```json",
        json.dumps(json.loads(model_info.get("metrics_json") or "{}"), indent=2),
        "```", "",
        "## Charts", "",
        "![NAV](assets/nav.png)", "",
        "![Drawdown](assets/drawdown.png)", "",
        "---", "",
        "*OQ-010 parameters are example values, not business-final.*",
    ]
    return "\n".join(lines)


def render_html(summary: dict, model_info: dict, args) -> str:
    m = json.loads(summary.get("metrics_json") or "{}")

    def row(label, value):
        return f"<tr><th>{html.escape(label)}</th><td>{html.escape(str(value))}</td></tr>"

    perf_rows = "".join([
        row("Period", f"{summary.get('start_date', '')} to {summary.get('end_date', '')}"),
        row("Total Return", fmt(summary.get("total_return"))),
        row("Annual Return", fmt(summary.get("annual_return"))),
        row("Annual Vol", fmt(summary.get("annual_vol"))),
        row("Sharpe", fmt(summary.get("sharpe"))),
        row("Max Drawdown", fmt(summary.get("max_drawdown"))),
        row("Excess Return", fmt(summary.get("excess_return"))),
        row("Information Ratio", fmt(summary.get("information_ratio"))),
        row("Buy Fail Rate", fmt(m.get("buy_fail_rate"))),
        row("Sell Delay Rate", fmt(m.get("sell_delay_rate"))),
        row("Sell Blocked Count", m.get("sell_blocked_count", "N/A")),
        row("Cost (bps)", fmt(summary.get("cost_bps"), 0)),
        row("Benchmark", summary.get("benchmark_sec_code", "")),
    ])
    model_metrics = html.escape(json.dumps(json.loads(model_info.get("metrics_json") or "{}"), indent=2))
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Strategy 1 Backtest Report</title>
<style>body{{font-family:system-ui,Arial,sans-serif;max-width:960px;margin:auto;padding:24px;color:#222}}
h1,h2{{border-bottom:1px solid #eee;padding-bottom:4px}}
table{{border-collapse:collapse;margin:12px 0}}td,th{{border:1px solid #ccc;padding:6px 12px;text-align:left}}
th{{background:#f6f6f6}}img{{max-width:100%;margin:8px 0}}pre{{background:#f6f6f6;padding:12px;overflow:auto}}
.muted{{color:#888;font-size:0.9em}}</style></head>
<body>
<h1>Strategy 1 Backtest Report</h1>
<ul>
<li><b>backtest_id</b>: {html.escape(args.backtest_id)}</li>
<li><b>run_id</b>: {html.escape(args.run_id)}</li>
<li><b>strategy_id</b>: {html.escape(args.strategy_id)}</li>
<li><b>model_id</b>: {html.escape(str(model_info.get('model_id', 'N/A')))}</li>
<li><b>generated</b>: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</li>
</ul>
<h2>Performance Summary</h2>
<table>{perf_rows}</table>
<h2>Model Selection</h2>
<pre>{model_metrics}</pre>
<h2>Charts</h2>
<img src="assets/nav.png" alt="NAV">
<img src="assets/drawdown.png" alt="Drawdown">
<p class="muted">OQ-010 parameters are example values, not business-final.</p>
</body></html>"""


def upload_dir_to_gcs(local_dir: Path, gcs_uri: str, skip: bool):
    if skip:
        print(f"  Skipping GCS upload. Local: {local_dir}")
        return gcs_uri
    bucket_name = gcs_uri.replace("gs://", "").split("/")[0]
    prefix = "/".join(gcs_uri.replace("gs://", "").split("/")[1:])
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    for path in local_dir.rglob("*"):
        if path.is_file():
            blob = bucket.blob(f"{prefix}/{path.relative_to(local_dir)}")
            blob.upload_from_filename(str(path))
            print(f"  Uploaded {blob.name}")
    return gcs_uri


def write_report_uri_to_ads(client: bigquery.Client, project: str,
                             backtest_id: str, gcs_uri: str, local_path: str):
    # metrics_json is a STRING column; JSON_SET needs JSON, so PARSE_JSON in and
    # TO_JSON_STRING out to keep the column a STRING while preserving existing keys.
    sql = f"""
    UPDATE `{project}.ashare_ads.ads_backtest_performance_summary` AS bs
    SET bs.metrics_json = TO_JSON_STRING(JSON_SET(
      PARSE_JSON(COALESCE(bs.metrics_json, '{{}}')),
      '$.report_uri', @gcs_uri,
      '$.local_report_path', @local_path,
      '$.report_generated_utc', @ts
    ))
    WHERE bs.backtest_id = @bid
    """
    job_cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("bid", "STRING", backtest_id),
        bigquery.ScalarQueryParameter("gcs_uri", "STRING", gcs_uri),
        bigquery.ScalarQueryParameter("local_path", "STRING", local_path),
        bigquery.ScalarQueryParameter("ts", "STRING", datetime.utcnow().isoformat())])
    client.query(sql, job_config=job_cfg).result()
    print(f"  Updated ads_backtest_performance_summary.metrics_json with report_uri")


def main():
    args = parse_args()
    bq = bigquery.Client(project=args.project)

    print("Fetching summary...")
    summary = fetch_summary(bq, args.project, args.backtest_id)
    sd, ed = str(summary.get("start_date", "2024-01-01")), str(summary.get("end_date", "2025-12-31"))

    print("Fetching NAV...")
    nav_df = fetch_nav(bq, args.project, args.backtest_id, sd, ed)

    print("Fetching model info...")
    model_info = fetch_model_info(bq, args.project, args.strategy_id, args.run_id)

    report_dir = Path(args.local_mirror_root) / f"ml_pv_clf_v0/run_id={args.run_id}/backtest_id={args.backtest_id}"
    assets_dir = report_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    print("Rendering charts...")
    plot_nav(nav_df, assets_dir / "nav.png")
    plot_drawdown(nav_df, assets_dir / "drawdown.png")

    print("Rendering report...")
    md = render_markdown(summary, model_info, args)
    (report_dir / "report.md").write_text(md)
    (report_dir / "report.html").write_text(render_html(summary, model_info, args))
    metrics = {
        "backtest_id": args.backtest_id, "run_id": args.run_id,
        "strategy_id": args.strategy_id, "model_id": model_info.get("model_id"),
        "summary": {k: str(v) if not isinstance(v, (int, float, bool, type(None))) else v
                     for k, v in summary.items()},
        "generated_utc": datetime.utcnow().isoformat(),
    }
    (report_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))

    gcs_uri = f"{args.artifact_base_uri}/ml_pv_clf_v0/run_id={args.run_id}/backtest_id={args.backtest_id}"
    print(f"Uploading to GCS: {gcs_uri}")
    upload_dir_to_gcs(report_dir, gcs_uri, args.skip_gcs_upload)

    print("Writing report_uri back to ADS...")
    write_report_uri_to_ads(bq, args.project, args.backtest_id, gcs_uri, str(report_dir))

    print(f"Done. Local: {report_dir}")


if __name__ == "__main__":
    main()
