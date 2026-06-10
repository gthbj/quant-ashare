#!/usr/bin/env python3
"""Build OQ-010 experiment comparison artifacts from dataset-role outputs.

The script reads a manifest and selected BigQuery output tables, then writes:
- experiment_comparison.md
- experiment_comparison.json
- experiment_metrics.csv
- experiment_manifest_resolved.json

It does not decide final strategy defaults; it only ranks and summarizes facts
for owner review.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from google.cloud import bigquery
except ImportError as exc:
    print(f"Missing dependency: {exc}", file=sys.stderr)
    print("Install: pip install google-cloud-bigquery pandas db-dtypes", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.strategy1_cloudrun.dataset_roles import (
    DEFAULT_OUTPUT_DATASET_ROLE,
    OUTPUT_DATASET_ROLE_CHOICES,
    rewrite_sql_dataset_role,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="生成 OQ-010 实验对比报告")
    p.add_argument("--project", default="data-aquarium")
    p.add_argument("--manifest", default="configs/strategy1/oq010_experiments_v0.json")
    p.add_argument("--comparison-id", required=True)
    p.add_argument("--output-root", default="reports/strategy1/oq010_experiment_comparison")
    p.add_argument("--output-dataset-role", choices=OUTPUT_DATASET_ROLE_CHOICES, default=DEFAULT_OUTPUT_DATASET_ROLE)
    p.add_argument("--include-planned", action="store_true",
                   help="Include manifest rows without selected output rows in CSV/JSON")
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


def query_rows(
    client: bigquery.Client,
    sql: str,
    params: list,
    *,
    output_dataset_role: str,
) -> list[dict[str, Any]]:
    sql = rewrite_sql_dataset_role(
        sql,
        dataset_role=output_dataset_role,
        project=client.project,
    )
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    return [dict(row) for row in client.query(sql, job_config=job_config)]


def parse_json_obj(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open() as f:
        manifest = json.load(f)
    seen: set[str] = set()
    for exp in manifest.get("experiments", []):
        eid = exp.get("experiment_id")
        if not eid:
            raise SystemExit("Every experiment must have experiment_id")
        if eid in seen:
            raise SystemExit(f"Duplicate experiment_id: {eid}")
        seen.add(eid)
    return manifest


def fetch_output_rows(
    client: bigquery.Client,
    experiments: list[dict[str, Any]],
    *,
    output_dataset_role: str,
) -> dict[str, dict[str, Any]]:
    backtest_ids = [e["backtest_id"] for e in experiments if isinstance(e.get("backtest_id"), str)]
    run_ids = sorted({
        rid
        for e in experiments
        for rid in (e.get("run_id"), e.get("prediction_run_id"))
        if isinstance(rid, str)
    })
    if not backtest_ids and not run_ids:
        return {}

    summaries = query_rows(
        client,
        """
        SELECT
          bs.backtest_id, bs.strategy_id, bs.model_id, bs.start_date, bs.end_date,
          bs.total_return, bs.annual_return, bs.annual_vol, bs.sharpe,
          bs.max_drawdown, bs.turnover_annual, bs.benchmark_sec_code,
          bs.excess_return, bs.information_ratio, bs.cost_bps,
          bs.metrics_json
        FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
        WHERE bs.backtest_id IN UNNEST(@backtest_ids)
        """,
        [bigquery.ArrayQueryParameter("backtest_ids", "STRING", backtest_ids)],
        output_dataset_role=output_dataset_role,
    )
    summary_by_backtest = {r["backtest_id"]: r for r in summaries}
    run_ids = sorted(set(run_ids) | {
        str(prediction_run_id)
        for r in summaries
        for prediction_run_id in [parse_json_obj(r.get("metrics_json")).get("prediction_run_id")]
        if prediction_run_id
    })

    registries = query_rows(
        client,
        """
        SELECT
          JSON_VALUE(reg.model_params_json, '$.run_id') AS run_id,
          reg.model_id, reg.status, reg.horizon,
          reg.feature_version, reg.label_version, reg.metrics_json,
          reg.model_params_json
        FROM `data-aquarium.ashare_ads.ads_model_registry` AS reg
        WHERE JSON_VALUE(reg.model_params_json, '$.run_id') IN UNNEST(@run_ids)
          AND reg.status = 'selected'
        """,
        [bigquery.ArrayQueryParameter("run_ids", "STRING", run_ids)],
        output_dataset_role=output_dataset_role,
    )
    registry_by_run = {r["run_id"]: r for r in registries}

    out: dict[str, dict[str, Any]] = {}
    for exp in experiments:
        eid = exp["experiment_id"]
        summary = summary_by_backtest.get(exp.get("backtest_id"))
        summary_metrics = parse_json_obj((summary or {}).get("metrics_json"))
        registry_run_id = summary_metrics.get("prediction_run_id") or exp.get("prediction_run_id") or exp.get("run_id")
        registry = registry_by_run.get(registry_run_id)
        if summary or registry:
            out[eid] = {"summary": summary or {}, "registry": registry or {}}
    return out


def row_for_experiment(exp: dict[str, Any], ads: dict[str, Any] | None) -> dict[str, Any]:
    summary = (ads or {}).get("summary", {})
    registry = (ads or {}).get("registry", {})
    sm = parse_json_obj(summary.get("metrics_json"))
    rm = parse_json_obj(registry.get("metrics_json"))
    row = {
        "experiment_id": exp.get("experiment_id"),
        "experiment_group": exp.get("experiment_group"),
        "status": "completed" if summary else exp.get("status", "planned"),
        "run_id": exp.get("run_id"),
        "prediction_run_id": sm.get("prediction_run_id") or exp.get("prediction_run_id") or exp.get("run_id"),
        "backtest_id": exp.get("backtest_id"),
        "parent_experiment_id": exp.get("parent_experiment_id"),
        "rebalance_frequency": exp.get("rebalance_frequency"),
        "target_holdings": exp.get("target_holdings"),
        "max_single_weight": exp.get("max_single_weight"),
        "label_horizon": exp.get("label_horizon"),
        "feature_set_id": exp.get("feature_set_id"),
        "requires_retrain": exp.get("requires_retrain"),
        "total_return": summary.get("total_return"),
        "excess_return": summary.get("excess_return"),
        "sharpe": summary.get("sharpe"),
        "max_drawdown": summary.get("max_drawdown"),
        "turnover_annual": summary.get("turnover_annual"),
        "information_ratio": summary.get("information_ratio"),
        "economic_cost_cny": sm.get("total_economic_cost_cny"),
        "rank_ic_mean": rm.get("rank_ic_mean"),
        "rank_icir": rm.get("rank_icir"),
        "topn_fwd_ret_mean": rm.get("topn_fwd_ret_mean"),
        "roc_auc": rm.get("roc_auc"),
        "score_orientation": rm.get("score_orientation"),
        "model_id": summary.get("model_id") or registry.get("model_id"),
    }
    return row


def sort_key(row: dict[str, Any]) -> tuple:
    completed = 1 if row.get("status") == "completed" else 0
    total_return = row.get("total_return")
    sharpe = row.get("sharpe")
    rank_ic = row.get("rank_ic_mean")
    return (
        completed,
        float("-inf") if total_return is None else float(total_return),
        float("-inf") if sharpe is None else float(sharpe),
        float("-inf") if rank_ic is None else float(rank_ic),
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    cols = [
        "experiment_id", "experiment_group", "status", "run_id", "backtest_id",
        "prediction_run_id", "parent_experiment_id", "rebalance_frequency", "target_holdings",
        "max_single_weight", "label_horizon", "feature_set_id", "requires_retrain",
        "total_return", "excess_return", "sharpe", "max_drawdown",
        "turnover_annual", "information_ratio", "economic_cost_cny",
        "rank_ic_mean", "rank_icir", "topn_fwd_ret_mean", "roc_auc",
        "score_orientation", "model_id",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c) for c in cols})


def fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def write_md(path: Path, rows: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    completed = [r for r in rows if r.get("status") == "completed"]
    ranked = sorted(completed, key=sort_key, reverse=True)
    lines = [
        "# OQ-010 策略 1 首轮实验对比",
        "",
        f"- manifest_version: `{manifest.get('manifest_version')}`",
        f"- baseline_experiment_id: `{manifest.get('baseline_experiment_id')}`",
        f"- generated_at: `{datetime.now(timezone.utc).isoformat()}`",
        f"- completed_experiments: {len(completed)} / {len(rows)}",
        "",
    ]
    if ranked:
        best = ranked[0]
        lines.extend([
            "## 当前最高排序候选",
            "",
            f"- experiment_id: `{best['experiment_id']}`",
            f"- group: `{best['experiment_group']}`",
            f"- total_return: {fmt(best.get('total_return'))}",
            f"- sharpe: {fmt(best.get('sharpe'))}",
            f"- max_drawdown: {fmt(best.get('max_drawdown'))}",
            f"- rank_ic_mean: {fmt(best.get('rank_ic_mean'))}",
            "",
        ])
    else:
        lines.extend(["## 当前最高排序候选", "", "暂无已完成实验。", ""])

    lines.extend([
        "## 实验指标",
        "",
        "| experiment_id | group | status | total_return | sharpe | max_drawdown | rank_ic_mean | topn_fwd_ret_mean |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ])
    for row in sorted(rows, key=lambda r: (str(r.get("experiment_group")), str(r.get("experiment_id")))):
        lines.append(
            f"| `{row.get('experiment_id')}` | {row.get('experiment_group')} | {row.get('status')} | "
            f"{fmt(row.get('total_return'))} | {fmt(row.get('sharpe'))} | "
            f"{fmt(row.get('max_drawdown'))} | {fmt(row.get('rank_ic_mean'))} | "
            f"{fmt(row.get('topn_fwd_ret_mean'))} |"
        )
    lines.extend([
        "",
        "## 说明",
        "",
        "- valid 指标用于实验晋级，test 只做样本外验收；本文不替 owner 写最终默认参数。",
        "- 未完成或 blocked 的实验保留在 manifest 中，用于追踪分阶段执行依赖。",
    ])
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    args = parse_args()
    manifest = load_manifest(Path(args.manifest))
    experiments = manifest.get("experiments", [])
    client = make_bq_client(args.project)
    output_by_experiment = fetch_output_rows(
        client,
        experiments,
        output_dataset_role=args.output_dataset_role,
    )
    rows = [
        row_for_experiment(exp, output_by_experiment.get(exp["experiment_id"]))
        for exp in experiments
        if args.include_planned or exp["experiment_id"] in output_by_experiment
    ]

    out_dir = Path(args.output_root) / args.comparison_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "experiment_manifest_resolved.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    (out_dir / "experiment_comparison.json").write_text(
        json.dumps({"comparison_id": args.comparison_id, "rows": rows},
                   ensure_ascii=False, indent=2, default=str) + "\n"
    )
    write_csv(out_dir / "experiment_metrics.csv", rows)
    write_md(out_dir / "experiment_comparison.md", rows, manifest)
    print(f"Wrote OQ-010 comparison artifacts to {out_dir}")


if __name__ == "__main__":
    main()
