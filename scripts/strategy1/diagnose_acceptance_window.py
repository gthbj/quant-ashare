#!/usr/bin/env python3
"""Strategy 1 acceptance-window preflight diagnosis.

This is the Phase B0 read-only diagnostic from
`PRD_20260606_03_策略1风险特征入模与候选增强.md`. It reads existing ADS
backtest/model artifacts, re-cuts the historical BQML reference to the 2025 test
window, summarizes already rejected Python candidates, and writes local/GCS
artifacts. It must not train models, rerun the SQL runner, or write ADS tables.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from google.cloud import bigquery

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.strategy1_cloudrun.acceptance import load_acceptance_contract
from scripts.strategy1_cloudrun.bq_io import (
    get_git_commit,
    join_gs_uri,
    make_client,
    query_dataframe,
    upload_directory_to_gcs,
    write_json,
    write_text,
)


DEFAULT_DIAGNOSIS_ID = "riskfeat_acceptance_window_20260606_01"
DEFAULT_BQML_BACKTEST_ID = "bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01"
DEFAULT_SEARCH_IDS = [
    "sklearn_native_pvfq_n30_bw_h5_20260605_01",
    "cloudrun_python_lgbm_pvfq_n30_bw_h5_20260605_01",
    "cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01",
]
REQUIRED_ARTIFACTS = [
    "acceptance_window_diagnosis.json",
    "acceptance_window_diagnosis.md",
    "bqml_2025_reference_metrics.json",
    "python_candidate_acceptance_window.csv",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="策略 1 acceptance-window 只读前置诊断")
    parser.add_argument("--project", default="data-aquarium")
    parser.add_argument("--region", default="asia-east2")
    parser.add_argument("--strategy-id", default="ml_pv_clf_v0")
    parser.add_argument("--diagnosis-id", default=DEFAULT_DIAGNOSIS_ID)
    parser.add_argument("--bqml-reference-backtest-id", default=DEFAULT_BQML_BACKTEST_ID)
    parser.add_argument("--search-id", action="append", default=None,
                        help="已完成 Python search_id；可重复传入。默认分析 sklearn/lgbm binary/lgbm regression 三波")
    parser.add_argument("--test-start-date", default="2025-01-02")
    parser.add_argument("--test-end-date", default="2025-12-31")
    parser.add_argument("--benchmark-sec-code", default="000001.SH")
    parser.add_argument("--risk-max-drawdown-target", type=float, default=-0.18)
    parser.add_argument("--python-same-side-threshold", type=float, default=0.80)
    parser.add_argument("--artifact-base-uri", default="gs://ashare-artifacts/reports/strategy1")
    parser.add_argument("--local-mirror-root", default="reports/strategy1")
    parser.add_argument("--skip-gcs-upload", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 0 < args.python_same_side_threshold <= 1:
        raise SystemExit("--python-same-side-threshold must be in (0, 1]")
    search_ids = args.search_id or DEFAULT_SEARCH_IDS

    client = make_client(args.project, args.region)
    out_dir = artifact_local_dir(args)
    out_dir.mkdir(parents=True, exist_ok=True)

    bqml_metrics = fetch_bqml_reference_metrics(client, args)
    candidate_rows = fetch_python_candidate_metrics(client, args, search_ids)
    candidates_df = pd.DataFrame(candidate_rows)
    if candidates_df.empty:
        candidates_df = pd.DataFrame(columns=[
            "search_id", "candidate_id", "run_id", "backtest_id",
            "native_acceptance_status", "native_acceptance_reason",
            "test_year_excess_return", "test_year_max_drawdown",
            "full_period_max_drawdown",
        ])
    diagnosis = build_diagnosis(args, bqml_metrics, candidates_df, search_ids)

    write_json(out_dir / "bqml_2025_reference_metrics.json", bqml_metrics)
    candidates_df.to_csv(out_dir / "python_candidate_acceptance_window.csv", index=False)
    write_json(out_dir / "acceptance_window_diagnosis.json", diagnosis)
    write_text(out_dir / "acceptance_window_diagnosis.md", render_markdown(diagnosis, candidates_df))

    missing = [name for name in REQUIRED_ARTIFACTS if not (out_dir / name).is_file()]
    if missing:
        raise SystemExit(f"missing acceptance-window artifacts: {missing}")

    diagnosis["artifact_uri"] = None if args.skip_gcs_upload else artifact_gcs_uri(args)
    diagnosis["artifact_upload_status"] = "skipped" if args.skip_gcs_upload else "uploaded"
    diagnosis["uploaded_artifacts"] = []
    write_json(out_dir / "acceptance_window_diagnosis.json", diagnosis)
    write_text(out_dir / "acceptance_window_diagnosis.md", render_markdown(diagnosis, candidates_df))
    if not args.skip_gcs_upload:
        uploaded = upload_directory_to_gcs(args.project, out_dir, artifact_gcs_uri(args))
        diagnosis["uploaded_artifacts"] = uploaded
        write_json(out_dir / "acceptance_window_diagnosis.json", diagnosis)
        upload_directory_to_gcs(args.project, out_dir, artifact_gcs_uri(args))

    print(json.dumps({
        "status": "succeeded",
        "diagnosis_id": args.diagnosis_id,
        "primary_blocker": diagnosis["primary_blocker"],
        "artifact_uri": diagnosis["artifact_uri"],
        "local_dir": str(out_dir),
        "bqml_reference_passes_2025_excess": bqml_metrics["passes_test_year_excess_gate"],
        "bqml_reference_passes_risk_drawdown_target": bqml_metrics["passes_risk_max_drawdown_target"],
        "python_candidate_count": int(len(candidates_df)),
    }, ensure_ascii=False, indent=2))
    return 0


def artifact_local_dir(args: argparse.Namespace) -> Path:
    return (
        Path(args.local_mirror_root)
        / args.strategy_id
        / "acceptance_window_diagnosis"
        / f"diagnosis_id={args.diagnosis_id}"
    )


def artifact_gcs_uri(args: argparse.Namespace) -> str:
    return join_gs_uri(
        args.artifact_base_uri,
        args.strategy_id,
        "acceptance_window_diagnosis",
        f"diagnosis_id={args.diagnosis_id}",
    )


def fetch_bqml_reference_metrics(client: bigquery.Client, args: argparse.Namespace) -> dict[str, Any]:
    sql = f"""
    WITH nav AS (
      SELECT
        trade_date,
        nav AS nav_value,
        daily_return,
        benchmark_return,
        benchmark_sec_code
      FROM `{args.project}.ashare_ads.ads_backtest_nav_daily`
      WHERE backtest_id = @backtest_id
        AND trade_date BETWEEN @test_start AND @test_end
    ),
    summary AS (
      SELECT
        start_date AS full_period_start_date,
        end_date AS full_period_end_date,
        benchmark_sec_code AS full_period_benchmark_sec_code,
        max_drawdown AS full_period_max_drawdown
      FROM `{args.project}.ashare_ads.ads_backtest_performance_summary`
      WHERE backtest_id = @backtest_id
      LIMIT 1
    ),
    perf AS (
      SELECT
        COUNT(*) AS trading_days,
        ARRAY_AGG(benchmark_sec_code IGNORE NULLS ORDER BY trade_date DESC LIMIT 1)[SAFE_OFFSET(0)] AS benchmark_sec_code,
        EXP(SUM(IF(1.0 + daily_return > 0, LN(1.0 + daily_return), NULL))) - 1.0 AS total_return,
        EXP(SUM(IF(1.0 + benchmark_return > 0, LN(1.0 + benchmark_return), NULL))) - 1.0 AS benchmark_return
      FROM nav
    ),
    dd AS (
      SELECT MIN(drawdown) AS test_year_max_drawdown
      FROM (
        SELECT
          nav_value / NULLIF(MAX(nav_value) OVER (
            ORDER BY trade_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
          ), 0) - 1.0 AS drawdown
        FROM nav
      )
    )
    SELECT
      @backtest_id AS backtest_id,
      @test_start AS test_start_date,
      @test_end AS test_end_date,
      summary.full_period_start_date,
      summary.full_period_end_date,
      perf.trading_days,
      COALESCE(perf.benchmark_sec_code, summary.full_period_benchmark_sec_code) AS benchmark_sec_code,
      perf.total_return,
      perf.benchmark_return,
      perf.total_return - perf.benchmark_return AS excess_return,
      dd.test_year_max_drawdown,
      summary.full_period_max_drawdown,
      summary.full_period_max_drawdown AS max_drawdown
    FROM perf
    CROSS JOIN dd
    LEFT JOIN summary ON TRUE
    """
    frame = query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("backtest_id", "STRING", args.bqml_reference_backtest_id),
            bigquery.ScalarQueryParameter("test_start", "DATE", args.test_start_date),
            bigquery.ScalarQueryParameter("test_end", "DATE", args.test_end_date),
        ],
        labels={"component": "strategy1", "step": "accept_window_bqml"},
    )
    if frame.empty:
        raise RuntimeError(f"no NAV rows found for BQML reference {args.bqml_reference_backtest_id}")
    row = normalize_record(frame.iloc[0].to_dict())
    if int(row.get("trading_days") or 0) <= 0:
        raise RuntimeError(f"zero 2025 NAV rows for BQML reference {args.bqml_reference_backtest_id}")
    row["passes_test_year_excess_gate"] = safe_float(row.get("excess_return")) > 0.0
    row["passes_risk_max_drawdown_target"] = (
        safe_float(row.get("full_period_max_drawdown")) >= args.risk_max_drawdown_target
    )
    return row


def fetch_python_candidate_metrics(
    client: bigquery.Client,
    args: argparse.Namespace,
    search_ids: list[str],
) -> list[dict[str, Any]]:
    sql = f"""
    WITH registry AS (
      SELECT
        reg.model_id,
        JSON_VALUE(reg.metrics_json, '$.search_id') AS search_id,
        JSON_VALUE(reg.metrics_json, '$.candidate_id') AS candidate_id,
        SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.shortlist_rank_valid_only') AS INT64) AS shortlist_rank_valid_only,
        JSON_VALUE(reg.model_params_json, '$.run_id') AS run_id,
        JSON_VALUE(reg.metrics_json, '$.native_acceptance_status') AS native_acceptance_status,
        JSON_VALUE(reg.metrics_json, '$.native_acceptance_reason') AS native_acceptance_reason,
        JSON_VALUE(reg.metrics_json, '$.model_family') AS model_family,
        JSON_VALUE(reg.metrics_json, '$.model_library') AS model_library,
        SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.test_reuse_wave_no') AS INT64) AS test_reuse_wave_no,
        SAFE_CAST(JSON_VALUE(reg.metrics_json, '$.model_search_wave_no') AS INT64) AS model_search_wave_no,
        JSON_VALUE(reg.metrics_json, '$.final_holdout_status') AS final_holdout_status
      FROM `{args.project}.ashare_ads.ads_model_registry` AS reg
      WHERE reg.strategy_id = @strategy_id
        AND reg.status = 'selected'
        AND JSON_VALUE(reg.metrics_json, '$.search_id') IN UNNEST(@search_ids)
    ),
    summary AS (
      SELECT
        bs.model_id,
        bs.backtest_id,
        bs.start_date,
        bs.end_date,
        bs.total_return AS full_period_total_return,
        bs.excess_return AS full_period_excess_return,
        bs.sharpe AS full_period_sharpe,
        bs.max_drawdown AS full_period_max_drawdown,
        bs.benchmark_sec_code,
        bs.metrics_json AS summary_metrics_json
      FROM `{args.project}.ashare_ads.ads_backtest_performance_summary` AS bs
      JOIN registry AS reg
        ON reg.model_id = bs.model_id
    ),
    test_perf AS (
      SELECT
        nav.run_id,
        COUNT(*) AS test_year_trading_days,
        EXP(SUM(IF(1.0 + nav.daily_return > 0, LN(1.0 + nav.daily_return), NULL))) - 1.0 AS test_year_total_return,
        EXP(SUM(IF(1.0 + nav.benchmark_return > 0, LN(1.0 + nav.benchmark_return), NULL))) - 1.0 AS test_year_benchmark_return
      FROM `{args.project}.ashare_ads.ads_backtest_nav_daily` AS nav
      JOIN registry AS reg
        ON reg.run_id = nav.run_id
      WHERE nav.trade_date BETWEEN @test_start AND @test_end
      GROUP BY nav.run_id
    ),
    test_dd AS (
      SELECT
        run_id,
        MIN(nav_value / NULLIF(running_peak, 0) - 1.0) AS test_year_max_drawdown
      FROM (
        SELECT
          nav.run_id,
          nav.trade_date,
          nav.nav AS nav_value,
          MAX(nav.nav) OVER (
            PARTITION BY nav.run_id
            ORDER BY nav.trade_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
          ) AS running_peak
        FROM `{args.project}.ashare_ads.ads_backtest_nav_daily` AS nav
        JOIN registry AS reg
          ON reg.run_id = nav.run_id
        WHERE nav.trade_date BETWEEN @test_start AND @test_end
      )
      GROUP BY run_id
    )
    SELECT
      reg.search_id,
      reg.candidate_id,
      reg.shortlist_rank_valid_only,
      reg.run_id,
      summary.backtest_id,
      reg.model_id,
      reg.model_family,
      reg.model_library,
      reg.model_search_wave_no,
      reg.test_reuse_wave_no,
      reg.final_holdout_status,
      reg.native_acceptance_status,
      reg.native_acceptance_reason,
      summary.start_date,
      summary.end_date,
      summary.benchmark_sec_code,
      summary.full_period_total_return,
      summary.full_period_excess_return,
      summary.full_period_sharpe,
      summary.full_period_max_drawdown,
      test_perf.test_year_trading_days,
      test_perf.test_year_total_return,
      test_perf.test_year_benchmark_return,
      test_perf.test_year_total_return - test_perf.test_year_benchmark_return AS test_year_excess_return,
      test_dd.test_year_max_drawdown,
      JSON_VALUE(summary.summary_metrics_json, '$.report_uri') AS report_uri,
      JSON_VALUE(summary.summary_metrics_json, '$.model_diagnosis_uri') AS model_diagnosis_uri,
      JSON_VALUE(summary.summary_metrics_json, '$.model_diagnosis_primary_diagnosis') AS model_diagnosis_primary_diagnosis,
      JSON_VALUE(summary.summary_metrics_json, '$.model_diagnosis_confidence') AS model_diagnosis_confidence
    FROM registry AS reg
    LEFT JOIN summary USING (model_id)
    LEFT JOIN test_perf
      ON test_perf.run_id = reg.run_id
    LEFT JOIN test_dd
      ON test_dd.run_id = reg.run_id
    ORDER BY reg.search_id, reg.shortlist_rank_valid_only, reg.candidate_id
    """
    frame = query_dataframe(
        client,
        sql,
        [
            bigquery.ScalarQueryParameter("strategy_id", "STRING", args.strategy_id),
            bigquery.ArrayQueryParameter("search_ids", "STRING", search_ids),
            bigquery.ScalarQueryParameter("test_start", "DATE", args.test_start_date),
            bigquery.ScalarQueryParameter("test_end", "DATE", args.test_end_date),
        ],
        labels={"component": "strategy1", "step": "accept_window_py"},
    )
    records = [normalize_record(row) for row in frame.to_dict("records")]
    for record in records:
        record["passes_test_year_excess_gate"] = safe_float(record.get("test_year_excess_return")) > 0.0
        record["passes_risk_max_drawdown_target"] = (
            safe_float(record.get("full_period_max_drawdown")) >= args.risk_max_drawdown_target
        )
    return records


def build_diagnosis(
    args: argparse.Namespace,
    bqml_metrics: dict[str, Any],
    candidates: pd.DataFrame,
    search_ids: list[str],
) -> dict[str, Any]:
    contract = load_acceptance_contract()
    candidate_count = int(len(candidates))
    rejected = candidates[candidates.get("native_acceptance_status", pd.Series(dtype=str)).eq("rejected")]
    failed_test_excess = count_bool(candidates, "passes_test_year_excess_gate", expected=False)
    failed_risk_dd = count_bool(candidates, "passes_risk_max_drawdown_target", expected=False)
    bqml_fails_excess = not bool(bqml_metrics["passes_test_year_excess_gate"])
    bqml_fails_risk_dd = not bool(bqml_metrics["passes_risk_max_drawdown_target"])
    same_side_checks = []
    if bqml_fails_excess:
        same_side_checks.append({
            "gate": "test_year_excess_return_gt_0",
            "python_failed_count": failed_test_excess,
            "python_failed_fraction": fraction(failed_test_excess, candidate_count),
            "threshold": args.python_same_side_threshold,
            "same_side": fraction(failed_test_excess, candidate_count) >= args.python_same_side_threshold,
        })
    if bqml_fails_risk_dd:
        same_side_checks.append({
            "gate": "full_period_risk_max_drawdown_target",
            "python_failed_count": failed_risk_dd,
            "python_failed_fraction": fraction(failed_risk_dd, candidate_count),
            "threshold": args.python_same_side_threshold,
            "same_side": fraction(failed_risk_dd, candidate_count) >= args.python_same_side_threshold,
        })

    if (bqml_fails_excess or bqml_fails_risk_dd) and any(item["same_side"] for item in same_side_checks):
        primary_blocker = "acceptance_window_risk"
        recommendation = "pause_before_wave4_training_and_review_acceptance_window"
    elif not bqml_fails_excess and not bqml_fails_risk_dd and candidate_count > 0 and len(rejected) == candidate_count:
        primary_blocker = "model_feature_gap"
        recommendation = "continue_with_risk_feature_modeling"
    elif candidate_count == 0:
        primary_blocker = "missing_python_candidate_evidence"
        recommendation = "collect_existing_search_artifacts_before_training"
    else:
        primary_blocker = "mixed_evidence"
        recommendation = "review_diagnosis_before_wave4_training"

    return {
        "diagnosis_id": args.diagnosis_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "project": args.project,
        "region": args.region,
        "strategy_id": args.strategy_id,
        "test_start_date": args.test_start_date,
        "test_end_date": args.test_end_date,
        "benchmark_sec_code": args.benchmark_sec_code,
        "acceptance_contract_version": contract.get("contract_version"),
        "risk_feature_max_drawdown_target": args.risk_max_drawdown_target,
        "python_same_side_threshold": args.python_same_side_threshold,
        "primary_blocker": primary_blocker,
        "recommendation": recommendation,
        "bqml_reference": bqml_metrics,
        "python_search_ids": search_ids,
        "python_candidate_count": candidate_count,
        "python_rejected_count": int(len(rejected)),
        "python_failed_test_year_excess_count": failed_test_excess,
        "python_failed_risk_drawdown_target_count": failed_risk_dd,
        "same_side_checks": same_side_checks,
        "notes": [
            "This diagnostic is read-only and uses existing ADS/GCS artifacts.",
            "BQML historical reference is not retrained or rerun.",
            "retired BQML/SQL runner is not executed.",
        ],
    }


def render_markdown(diagnosis: dict[str, Any], candidates: pd.DataFrame) -> str:
    bqml = diagnosis["bqml_reference"]
    lines = [
        "# 策略 1 Acceptance Window 前置诊断",
        "",
        f"- diagnosis_id: `{diagnosis['diagnosis_id']}`",
        f"- primary_blocker: `{diagnosis['primary_blocker']}`",
        f"- recommendation: `{diagnosis['recommendation']}`",
        f"- test window: `{diagnosis['test_start_date']}` 至 `{diagnosis['test_end_date']}`",
        f"- risk max drawdown target: `{diagnosis['risk_feature_max_drawdown_target']:.2%}`",
        "",
        "## BQML Historical Reference 2025-only",
        "",
        "| backtest_id | trading_days | test_return | test_benchmark | test_excess | test_maxDD | full_maxDD | excess gate | full risk DD target |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
        (
            f"| `{bqml.get('backtest_id')}` | {bqml.get('trading_days')} | "
            f"{pct(bqml.get('total_return'))} | {pct(bqml.get('benchmark_return'))} | "
            f"{pct(bqml.get('excess_return'))} | {pct(bqml.get('test_year_max_drawdown'))} | "
            f"{pct(bqml.get('full_period_max_drawdown'))} | "
            f"{yes_no(bqml.get('passes_test_year_excess_gate'))} | "
            f"{yes_no(bqml.get('passes_risk_max_drawdown_target'))} |"
        ),
        "",
        "## Python 已拒候选",
        "",
        f"- candidate_count: {diagnosis['python_candidate_count']}",
        f"- rejected_count: {diagnosis['python_rejected_count']}",
        f"- failed_test_year_excess_count: {diagnosis['python_failed_test_year_excess_count']}",
        f"- failed_full_period_risk_drawdown_target_count: {diagnosis['python_failed_risk_drawdown_target_count']}",
        "",
    ]
    if not candidates.empty:
        lines.extend([
            "| search_id | rank | candidate_id | status | reason | test_excess | test_maxDD | full_maxDD |",
            "|---|---:|---|---|---|---:|---:|---:|",
        ])
        for _, row in candidates.iterrows():
            lines.append(
                f"| `{row.get('search_id')}` | {int_or_blank(row.get('shortlist_rank_valid_only'))} | "
                f"`{row.get('candidate_id') or ''}` | {row.get('native_acceptance_status') or ''} | "
                f"{row.get('native_acceptance_reason') or ''} | {pct(row.get('test_year_excess_return'))} | "
                f"{pct(row.get('test_year_max_drawdown'))} | {pct(row.get('full_period_max_drawdown'))} |"
            )
    else:
        lines.append("_未读取到 Python Top5 候选记录。_")
    lines.extend([
        "",
        "## Same-side Checks",
        "",
        "| gate | python_failed_count | python_failed_fraction | threshold | same_side |",
        "|---|---:|---:|---:|---|",
    ])
    for item in diagnosis["same_side_checks"]:
        lines.append(
            f"| `{item['gate']}` | {item['python_failed_count']} | "
            f"{item['python_failed_fraction']:.2%} | {item['threshold']:.2%} | {yes_no(item['same_side'])} |"
        )
    if not diagnosis["same_side_checks"]:
        lines.append("| NA | 0 | 0.00% | 0.00% | no |")
    lines.extend([
        "",
        "## 结论",
        "",
        conclusion_text(diagnosis),
        "",
        "## 约束",
        "",
        "- 本诊断只读 ADS / 已有 artifact，不训练模型。",
        "- 不重跑 BQML，不执行已退役 Strategy1 SQL runner。",
        "- BigQuery 读取 `ads_backtest_nav_daily` 时显式使用 `trade_date BETWEEN ...` 分区过滤。",
    ])
    return "\n".join(lines) + "\n"


def conclusion_text(diagnosis: dict[str, Any]) -> str:
    blocker = diagnosis["primary_blocker"]
    if blocker == "acceptance_window_risk":
        return (
            "既有 BQML historical reference 在 2025-only 或风险回撤目标上也未形成足够余量，"
            "且已拒 Python 候选集中落在同一错误侧。按 PRD，进入第 4 波训练前应先由 owner 复核接受门 / 年份区间。"
        )
    if blocker == "model_feature_gap":
        return (
            "既有 BQML historical reference 能通过 2025-only excess 和风险回撤目标，而 Python 候选未通过。"
            "当前瓶颈更像模型 / 特征差距，可以继续风险特征入模。"
        )
    if blocker == "missing_python_candidate_evidence":
        return "未读取到三波 Python Top5 候选记录；应先补齐已有 search artifacts，再决定是否进入第 4 波。"
    return "证据混合，不能自动判断瓶颈；建议人工复核后再决定是否启动风险特征搜索。"


def normalize_record(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if pd.isna(value):
            out[key] = None
        elif hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def safe_float(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return math.nan
    return out if math.isfinite(out) else math.nan


def count_bool(frame: pd.DataFrame, column: str, *, expected: bool) -> int:
    if frame.empty or column not in frame.columns:
        return 0
    return int((frame[column].fillna(not expected) == expected).sum())


def fraction(numerator: int, denominator: int) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def pct(value: Any) -> str:
    number = safe_float(value)
    return "NA" if not math.isfinite(number) else f"{number:.2%}"


def yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"


def int_or_blank(value: Any) -> str:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return ""


if __name__ == "__main__":
    raise SystemExit(main())
