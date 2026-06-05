#!/usr/bin/env python3
"""Orchestrate Strategy 1 sklearn native candidate search.

This entrypoint implements the P0 flow from
`PRD_20260605_03_策略1Sklearn模型实验.md`:

1. one frozen matrix prepare;
2. Cloud Run task fan-out training for all LogisticRegression candidates;
3. valid-only ranking and Top-K shortlist;
4. independent selected/prediction/backtest/report/diagnosis runs for Top-K.

It reuses the existing Cloud Run Jobs and the same GCS lock / status table
mechanism as `orchestrate_experiments.py`.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import json
import math
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
from google.cloud import bigquery

from scripts.strategy1_cloudrun import __version__
from scripts.strategy1_cloudrun.bq_io import (
    download_gcs_file,
    join_gs_uri,
    make_client,
    upload_directory_to_gcs,
    write_json,
    write_text,
)
from scripts.strategy1_cloudrun.config import (
    Experiment,
    add_common_args,
    apply_cli_overrides,
    experiment_to_b64,
    filter_experiments,
    load_manifest,
    load_runner_config,
    manifest_hash,
    read_mapping,
    resolve_parallel_count,
)
from scripts.strategy1_cloudrun.orchestrate_experiments import (
    build_task_fanout_steps,
    gcloud_execute_command,
    run_locked_step,
)
from scripts.strategy1_cloudrun.select_register_predict import (
    load_candidates,
    rank_candidates,
)
from scripts.strategy1_cloudrun.sql_runner import run_sql_script
from scripts.strategy1_cloudrun.state import (
    LockConfig,
    OrchestratorStatusTable,
    StepStateSpec,
    build_lock_key,
    scheduler_instance_id,
)
from scripts.strategy1_cloudrun.task_fanout import default_matrix_id, matrix_artifact_uri, read_json


def main() -> int:
    args = parse_args()
    config = apply_cli_overrides(load_runner_config(args.config), args)
    raw_manifest = read_mapping(args.manifest)
    _, experiments = load_manifest(args.manifest)
    selected = filter_experiments(
        experiments,
        experiment_id=args.experiment_id,
        include_blocked=args.include_blocked,
    )
    if len(selected) != 1:
        raise ValueError(f"expected exactly one search experiment, got {len(selected)}")
    search_exp = selected[0]
    search_id = args.search_id or raw_manifest.get("search_id") or search_exp.experiment_id
    top_k = args.top_k_backtest or int(raw_manifest.get("top_k_backtest") or 5)
    test_reuse = raw_manifest.get("test_reuse") or {}
    test_reuse_wave_no = args.test_reuse_wave_no or int(test_reuse.get("wave_no") or 1)
    test_reuse_approval_ref = args.test_reuse_approval_ref
    if test_reuse_approval_ref is None:
        test_reuse_approval_ref = test_reuse.get("approval_ref")
    final_holdout_status = args.final_holdout_status
    if final_holdout_status is None:
        final_holdout_status = test_reuse.get("final_holdout_status")

    matrix_id = default_matrix_id(config, search_exp)
    matrix_uri = matrix_artifact_uri(config, search_exp, matrix_id)
    common_flags = common_job_flags(config, args, search_exp)
    train_steps = build_task_fanout_steps(config, search_exp, args, common_flags)[:-1]
    plan = {
        "entrypoint": "sklearn_native_search_orchestrator",
        "runner_version": __version__,
        "project": config.project,
        "region": config.region,
        "config": args.config,
        "manifest": args.manifest,
        "search_id": search_id,
        "search_experiment": search_exp.to_params(),
        "matrix_id": matrix_id,
        "matrix_uri": matrix_uri,
        "candidate_count": len(config.candidate_grid),
        "candidate_parallelism_arg": args.candidate_parallelism,
        "top_k_backtest": top_k,
        "test_reuse_wave_no": test_reuse_wave_no,
        "test_reuse_approval_ref": test_reuse_approval_ref,
        "final_holdout_status": final_holdout_status,
        "max_parallel_topk_backtests_arg": args.max_parallel_topk_backtests,
        "train_steps": [step_plan(step) for step in train_steps],
    }
    candidate_experiments = [
        topk_experiment(search_exp, search_id, f"<top{i}>")
        for i in range(1, top_k + 1)
    ]
    plan["topk_experiment_template"] = [exp.to_params() for exp in candidate_experiments]
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.skip_gcs_upload:
        raise ValueError("sklearn native search requires GCS matrix/candidate artifacts; do not use --skip-gcs-upload")

    scheduler_id = args.scheduler_instance_id or scheduler_instance_id()
    lock_config = LockConfig(
        project=config.project,
        region=config.region,
        bucket=args.lock_bucket or config.lock_bucket,
        prefix=args.lock_prefix or config.lock_prefix,
        ttl_minutes=args.lock_ttl_minutes or config.lock_ttl_minutes,
        dry_run=False,
    )
    manifest_hash_value = manifest_hash(args.manifest)
    status_table = OrchestratorStatusTable(config.project, config.region, dry_run=False)
    for step in train_steps:
        run_step(
            config=config,
            exp=search_exp,
            step=step,
            manifest_hash_value=manifest_hash_value,
            scheduler_id=scheduler_id,
            lock_config=lock_config,
            status_table=status_table,
            args=args,
        )

    matrix_local = ensure_candidate_artifacts_local(
        project=config.project,
        matrix_uri=matrix_uri,
        candidate_count=len(config.candidate_grid),
        matrix_local=args.matrix_local_dir,
    )
    manifest = read_json(matrix_local / "matrix_manifest.json")
    work_units = read_json(matrix_local / "work_units.json")
    candidates = load_candidates(
        matrix_local,
        manifest,
        work_units,
        require_all_candidates=not args.allow_partial_candidates,
    )
    ranking = rank_candidates(candidates, top_k=top_k)
    top_rows = [row for row in ranking if row.get("shortlist_rank_valid_only") is not None]
    top_rows = sorted(top_rows, key=lambda row: int(row["shortlist_rank_valid_only"]))[:top_k]
    if not top_rows:
        raise RuntimeError("no Top-K candidates were shortlisted")

    comparison_dir = comparison_local_dir(config, search_id)
    write_preliminary_comparison(
        comparison_dir,
        search_id=search_id,
        search_exp=search_exp,
        matrix_uri=matrix_uri,
        ranking=ranking,
        top_rows=top_rows,
        test_reuse_wave_no=test_reuse_wave_no,
        test_reuse_approval_ref=test_reuse_approval_ref,
        final_holdout_status=final_holdout_status,
    )
    if not args.skip_gcs_upload:
        upload_directory_to_gcs(config.project, comparison_dir, comparison_uri(config, search_id))

    max_topk_workers = resolve_parallel_count(
        len(top_rows),
        args.max_parallel_topk_backtests,
    )
    topk_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, max_topk_workers)) as executor:
        futures = {
            executor.submit(
                run_topk_candidate,
                config,
                args,
                lock_config,
                scheduler_id,
                manifest_hash_value,
                search_exp,
                search_id,
                matrix_uri,
                row,
                test_reuse_wave_no,
                test_reuse_approval_ref,
                final_holdout_status,
            ): row
            for row in top_rows
        }
        for future in concurrent.futures.as_completed(futures):
            row = futures[future]
            try:
                topk_results.append(future.result())
            except Exception as exc:
                exp = topk_experiment(search_exp, search_id, row["candidate_id"])
                topk_results.append({
                    "status": "failed",
                    "candidate_id": row["candidate_id"],
                    "shortlist_rank_valid_only": int(row["shortlist_rank_valid_only"]),
                    "experiment": exp.to_params(),
                    "error": str(exc)[-8000:],
                })

    client = make_client(config.project, config.region)
    successful_topk_results = [item for item in topk_results if item.get("status") == "succeeded"]
    comparison_rows = fetch_topk_ads_outputs(client, successful_topk_results) if successful_topk_results else []
    apply_native_acceptance_to_ads(client, comparison_rows, raw_manifest)
    comparison_rows = fetch_topk_ads_outputs(client, successful_topk_results) if successful_topk_results else []
    write_final_comparison(
        comparison_dir,
        search_id=search_id,
        search_exp=search_exp,
        matrix_uri=matrix_uri,
        ranking=ranking,
        top_rows=top_rows,
        comparison_rows=comparison_rows,
        topk_execution_results=topk_results,
        test_reuse_wave_no=test_reuse_wave_no,
        test_reuse_approval_ref=test_reuse_approval_ref,
        final_holdout_status=final_holdout_status,
    )
    uploaded = [] if args.skip_gcs_upload else upload_directory_to_gcs(
        config.project,
        comparison_dir,
        comparison_uri(config, search_id),
    )
    if not args.skip_qa:
        run_sql_script(
            client,
            "sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql",
            {
                "p_search_id": search_id,
                "p_source_run_id": search_exp.run_id,
                "p_expected_candidate_count": len(config.candidate_grid),
                "p_top_k": top_k,
                "p_test_reuse_wave_no": test_reuse_wave_no,
            },
        )
    print(json.dumps({
        "status": "succeeded",
        "search_id": search_id,
        "matrix_uri": matrix_uri,
        "candidate_count": len(config.candidate_grid),
        "top_k_backtest": len(top_rows),
        "comparison_uri": None if args.skip_gcs_upload else comparison_uri(config, search_id),
        "uploaded_artifacts": uploaded,
        "topk_results": topk_results,
    }, ensure_ascii=False, indent=2, default=str))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategy 1 sklearn native search orchestrator")
    add_common_args(parser)
    parser.add_argument("--experiment-id", default="sklearn_native_pvfq_n30_bw_h5_search_v0")
    parser.add_argument("--include-blocked", action="store_true")
    parser.add_argument("--search-id", default=None)
    parser.add_argument("--candidate-parallelism", type=int, default=0)
    parser.add_argument("--top-k-backtest", type=int, default=None)
    parser.add_argument("--max-parallel-topk-backtests", type=int, default=0)
    parser.add_argument("--matrix-local-dir", default=None)
    parser.add_argument("--force-replace", action="store_true")
    parser.add_argument("--skip-gcs-upload", action="store_true")
    parser.add_argument("--skip-diagnosis", action="store_true")
    parser.add_argument("--skip-qa", action="store_true")
    parser.add_argument("--use-bq-ledger", action="store_true")
    parser.add_argument("--allow-partial-candidates", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Skip Cloud Run steps already marked succeeded")
    parser.add_argument("--test-reuse-wave-no", type=int, default=None)
    parser.add_argument("--test-reuse-approval-ref", default=None)
    parser.add_argument("--final-holdout-status", default=None)
    parser.add_argument("--scheduler-instance-id", default=None)
    parser.add_argument("--lock-bucket", default=None)
    parser.add_argument("--lock-prefix", default=None)
    parser.add_argument("--lock-ttl-minutes", type=int, default=None)
    parser.add_argument("--heartbeat-interval-seconds", type=int, default=None)
    return parser.parse_args()


def common_job_flags(config, args, exp: Experiment) -> list[str]:
    flags = [
        f"--project={config.project}",
        f"--region={config.region}",
        f"--config={args.config}",
        f"--manifest={args.manifest}",
        f"--experiment-id={exp.experiment_id}",
        f"--experiment-json={experiment_to_b64(exp)}",
    ]
    if args.force_replace:
        flags.append("--force-replace")
    if args.skip_gcs_upload:
        flags.append("--skip-gcs-upload")
    return flags


def ensure_candidate_artifacts_local(
    *,
    project: str,
    matrix_uri: str,
    candidate_count: int,
    matrix_local: str | None,
) -> Path:
    local_dir = Path(matrix_local) if matrix_local else Path(tempfile.mkdtemp(prefix="strategy1-native-search-"))
    for rel in ("matrix_manifest.json", "work_units.json"):
        download_gcs_file(project, join_gs_uri(matrix_uri, rel), local_dir / rel)
    for unit_index in range(candidate_count):
        for name in ("candidate_metrics.json", "task_status.json", "model.joblib"):
            rel = f"candidates/unit_index={unit_index}/{name}"
            download_gcs_file(project, join_gs_uri(matrix_uri, rel), local_dir / rel)
    return local_dir


def topk_experiment(search_exp: Experiment, search_id: str, candidate_id: str) -> Experiment:
    candidate_safe = candidate_id.replace("-", "_")
    run_prefix = f"s1_{search_id}" if search_id.startswith("sklearn_native_") else f"s1_sklearn_native_{search_id}"
    return dataclasses.replace(
        search_exp,
        experiment_id=f"{search_exp.experiment_id}__{candidate_safe}",
        run_id=f"{run_prefix}__{candidate_safe}",
        prediction_run_id=f"{run_prefix}__{candidate_safe}",
        backtest_id=f"bt_{run_prefix}__{candidate_safe}",
        experiment_group="sklearn_native_top5_backtest",
        parent_experiment_id=search_exp.experiment_id,
        parent_run_id=search_exp.run_id,
    )


def run_topk_candidate(
    config,
    args,
    lock_config: LockConfig,
    scheduler_id: str,
    manifest_hash_value: str,
    search_exp: Experiment,
    search_id: str,
    matrix_uri: str,
    row: dict[str, Any],
    test_reuse_wave_no: int,
    test_reuse_approval_ref: str | None,
    final_holdout_status: str | None,
) -> dict[str, Any]:
    candidate_id = row["candidate_id"]
    exp = topk_experiment(search_exp, search_id, candidate_id)
    status_table = OrchestratorStatusTable(config.project, config.region, dry_run=False)
    select_flags = common_job_flags(config, args, exp)
    select_flags.extend([
        f"--matrix-uri={matrix_uri}",
        f"--candidate-id={candidate_id}",
        f"--search-id={search_id}",
        "--native-search",
        f"--shortlist-rank-valid-only={int(row['shortlist_rank_valid_only'])}",
        f"--test-reuse-wave-no={test_reuse_wave_no}",
    ])
    if test_reuse_approval_ref:
        select_flags.append(f"--test-reuse-approval-ref={test_reuse_approval_ref}")
    if final_holdout_status:
        select_flags.append(f"--final-holdout-status={final_holdout_status}")
    select_step = StepStateSpec(
        step_id="cloudrun_select_register_predict",
        display_name=f"Cloud Run select/register/predict TopK {candidate_id}",
        lock_key=build_lock_key(exp, "cloudrun_select_register_predict"),
        job_name=config.select_register_predict_job,
        command=gcloud_execute_command(
            config.project,
            config.region,
            config.select_register_predict_job,
            "scripts.strategy1_cloudrun.select_register_predict",
            select_flags,
        ),
    )
    backtest_flags = common_job_flags(config, args, exp)
    backtest_flags.extend([
        f"--run-id={exp.run_id}",
        f"--prediction-run-id={exp.prediction_run_id}",
        f"--backtest-id={exp.backtest_id}",
    ])
    if args.skip_diagnosis:
        backtest_flags.append("--skip-diagnosis")
    if args.skip_qa:
        backtest_flags.append("--skip-qa")
    if args.use_bq_ledger:
        backtest_flags.append("--use-bq-ledger")
    backtest_step = StepStateSpec(
        step_id="cloudrun_backtest_report",
        display_name=f"Cloud Run backtest/report TopK {candidate_id}",
        lock_key=build_lock_key(exp, "cloudrun_backtest_report"),
        job_name=config.backtest_report_job,
        command=gcloud_execute_command(
            config.project,
            config.region,
            config.backtest_report_job,
            "scripts.strategy1_cloudrun.backtest_report",
            backtest_flags,
        ),
    )
    outputs = []
    for step in (select_step, backtest_step):
        outputs.append(run_step(
            config=config,
            exp=exp,
            step=step,
            manifest_hash_value=manifest_hash_value,
            scheduler_id=scheduler_id,
            lock_config=lock_config,
            status_table=status_table,
            args=args,
        ))
    return {
        "status": "succeeded",
        "candidate_id": candidate_id,
        "shortlist_rank_valid_only": int(row["shortlist_rank_valid_only"]),
        "experiment": exp.to_params(),
        "steps": outputs,
    }


def run_step(
    *,
    config,
    exp: Experiment,
    step: StepStateSpec,
    manifest_hash_value: str,
    scheduler_id: str,
    lock_config: LockConfig,
    status_table: OrchestratorStatusTable,
    args,
) -> dict[str, Any]:
    if args.resume and status_table.get_status(exp, step.step_id) == "succeeded":
        return {"step_id": step.step_id, "status": "skipped_succeeded"}
    return run_locked_step(
        config=config,
        exp=exp,
        step=step,
        manifest_hash_value=manifest_hash_value,
        scheduler_id=scheduler_id,
        lock_config=lock_config,
        status_table=status_table,
        args=args,
    )


def comparison_local_dir(config, search_id: str) -> Path:
    return Path(config.local_mirror_root) / "sklearn_native_search" / f"search_id={search_id}"


def comparison_uri(config, search_id: str) -> str:
    return join_gs_uri(config.artifact_base_uri, "ml_pv_clf_v0", f"search_id={search_id}")


def write_preliminary_comparison(
    out_dir: Path,
    *,
    search_id: str,
    search_exp: Experiment,
    matrix_uri: str,
    ranking: list[dict[str, Any]],
    top_rows: list[dict[str, Any]],
    test_reuse_wave_no: int,
    test_reuse_approval_ref: str | None,
    final_holdout_status: str | None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(ranking).to_csv(out_dir / "candidate_ranking.csv", index=False)
    pd.DataFrame([row for row in ranking]).to_csv(out_dir / "candidate_metrics.csv", index=False)
    payload = {
        "search_id": search_id,
        "search_experiment": search_exp.to_params(),
        "matrix_uri": matrix_uri,
        "ranking_uses_test_metrics": False,
        "top_k_candidate_ids": [row["candidate_id"] for row in top_rows],
        "test_reuse_wave_no": test_reuse_wave_no,
        "test_reuse_approval_ref": test_reuse_approval_ref,
        "final_holdout_status": final_holdout_status,
        "ranking": ranking,
    }
    write_json(out_dir / "sklearn_native_candidate_comparison.json", payload)
    write_text(out_dir / "sklearn_native_candidate_comparison.md", render_comparison_md(payload, []))


def write_final_comparison(
    out_dir: Path,
    *,
    search_id: str,
    search_exp: Experiment,
    matrix_uri: str,
    ranking: list[dict[str, Any]],
    top_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    topk_execution_results: list[dict[str, Any]],
    test_reuse_wave_no: int,
    test_reuse_approval_ref: str | None,
    final_holdout_status: str | None,
) -> None:
    pd.DataFrame(ranking).to_csv(out_dir / "candidate_ranking.csv", index=False)
    pd.DataFrame(comparison_rows).to_csv(out_dir / "top5_backtest_summary.csv", index=False)
    diag_cols = [
        "candidate_id", "run_id", "backtest_id", "model_diagnosis_primary_diagnosis",
        "model_diagnosis_confidence", "model_diagnosis_uri",
    ]
    pd.DataFrame([{key: row.get(key) for key in diag_cols} for row in comparison_rows]).to_csv(
        out_dir / "top5_model_diagnosis_summary.csv",
        index=False,
    )
    accepted = [row for row in comparison_rows if row.get("native_acceptance_status") == "accepted"]
    selected = accepted[0] if accepted else (comparison_rows[0] if comparison_rows else None)
    write_json(out_dir / "selected_sklearn_native_baseline.json", selected or {
        "search_id": search_id,
        "native_acceptance_status": "rejected",
        "native_acceptance_reason": "no_top5_outputs",
    })
    payload = {
        "search_id": search_id,
        "search_experiment": search_exp.to_params(),
        "matrix_uri": matrix_uri,
        "ranking_uses_test_metrics": False,
        "top_k_candidate_ids": [row["candidate_id"] for row in top_rows],
        "test_reuse_wave_no": test_reuse_wave_no,
        "test_reuse_approval_ref": test_reuse_approval_ref,
        "final_holdout_status": final_holdout_status,
        "ranking": ranking,
        "topk_execution_results": topk_execution_results,
        "top5_backtest_summary": comparison_rows,
        "selected_sklearn_native_baseline": selected,
    }
    write_json(out_dir / "sklearn_native_candidate_comparison.json", payload)
    write_text(out_dir / "sklearn_native_candidate_comparison.md", render_comparison_md(payload, comparison_rows))


def render_comparison_md(payload: dict[str, Any], comparison_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# 策略 1 sklearn native 候选搜索对比",
        "",
        f"- search_id: `{payload['search_id']}`",
        f"- source_run_id: `{payload['search_experiment']['run_id']}`",
        f"- matrix_uri: `{payload['matrix_uri']}`",
        f"- ranking_uses_test_metrics: `{payload['ranking_uses_test_metrics']}`",
        f"- test_reuse_wave_no: `{payload.get('test_reuse_wave_no')}`",
        "",
        "## Valid-only Top 5",
        "",
        "| rank | candidate_id | valid RankIC | valid ICIR | topN ret | spread | signal |",
        "|---:|---|---:|---:|---:|---:|---|",
    ]
    for row in payload.get("ranking", []):
        if row.get("shortlist_rank_valid_only") is None:
            continue
        lines.append(
            f"| {row.get('shortlist_rank_valid_only')} | `{row.get('candidate_id')}` | "
            f"{fmt(row.get('valid_oriented_rank_ic_mean'))} | "
            f"{fmt(row.get('valid_oriented_rank_ic_icir'))} | "
            f"{fmt(row.get('valid_topn_fwd_ret_mean'))} | "
            f"{fmt(row.get('valid_top_minus_bottom_fwd_ret_mean'))} | "
            f"{row.get('valid_signal_status')} |"
        )
    if comparison_rows:
        lines.extend([
            "",
            "## Top 5 回测",
            "",
            "| rank | candidate_id | status | total_return | excess_return | sharpe | max_drawdown | test RankIC | test excess |",
            "|---:|---|---|---:|---:|---:|---:|---:|---:|",
        ])
        for row in comparison_rows:
            lines.append(
                f"| {row.get('shortlist_rank_valid_only')} | `{row.get('candidate_id')}` | "
                f"{row.get('native_acceptance_status')} | {fmt(row.get('total_return'))} | "
                f"{fmt(row.get('excess_return'))} | {fmt(row.get('sharpe'))} | "
                f"{fmt(row.get('max_drawdown'))} | {fmt(row.get('test_rank_ic_mean'))} | "
                f"{fmt(row.get('test_year_excess_return'))} |"
            )
    lines.extend([
        "",
        "## 说明",
        "",
        "- Top 5 排名只使用 valid 指标；test 指标只用于样本外验收和风险复核。",
        "- `accepted` 要求 valid_signal_status=stable，且满足 PRD §10.1 的收益、超额、回撤、Sharpe 和 QA 门槛。",
    ])
    return "\n".join(lines) + "\n"


def fetch_topk_ads_outputs(client: bigquery.Client, topk_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    run_ids = [item["experiment"]["run_id"] for item in topk_results]
    backtest_ids = [item["experiment"]["backtest_id"] for item in topk_results]
    rank_by_run = {
        item["experiment"]["run_id"]: item["shortlist_rank_valid_only"]
        for item in topk_results
    }
    candidate_by_run = {
        item["experiment"]["run_id"]: item["candidate_id"]
        for item in topk_results
    }
    sql = """
    WITH registry AS (
      SELECT
        JSON_VALUE(model_params_json, '$.run_id') AS run_id,
        model_id,
        model_uri,
        metrics_json,
        model_params_json
      FROM `data-aquarium.ashare_ads.ads_model_registry`
      WHERE status = 'selected'
        AND JSON_VALUE(model_params_json, '$.run_id') IN UNNEST(@run_ids)
    ),
    summary AS (
      SELECT
        backtest_id, model_id, start_date, end_date, total_return, annual_return,
        annual_vol, sharpe, max_drawdown, turnover_annual, benchmark_sec_code,
        excess_return, information_ratio, cost_bps, metrics_json
      FROM `data-aquarium.ashare_ads.ads_backtest_performance_summary`
      WHERE backtest_id IN UNNEST(@backtest_ids)
    ),
    test_rank_ic AS (
      SELECT
        day_ic.run_id,
        AVG(day_ic.rank_ic) AS test_rank_ic_mean,
        SAFE_DIVIDE(AVG(day_ic.rank_ic), NULLIF(STDDEV_SAMP(day_ic.rank_ic), 0)) AS test_rank_ic_icir
      FROM (
        SELECT
          pred.run_id,
          pred.predict_date,
          CORR(
            CAST(score_rank AS FLOAT64),
            CAST(ret_rank AS FLOAT64)
          ) AS rank_ic
        FROM (
          SELECT
            pred.run_id,
            pred.predict_date,
            pred.sec_code,
            RANK() OVER(PARTITION BY pred.run_id, pred.predict_date ORDER BY pred.score) AS score_rank,
            RANK() OVER(PARTITION BY pred.run_id, pred.predict_date ORDER BY tp.target_return) AS ret_rank
          FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
          JOIN `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
            ON tp.run_id = pred.run_id
           AND tp.trade_date = pred.predict_date
           AND tp.sec_code = pred.sec_code
          WHERE pred.run_id IN UNNEST(@run_ids)
            AND pred.predict_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'
            AND tp.split_tag = 'test'
            AND tp.target_return IS NOT NULL
        ) AS pred
        GROUP BY pred.run_id, pred.predict_date
      ) AS day_ic
      GROUP BY day_ic.run_id
    ),
    test_bucket_spread AS (
      SELECT
        run_id,
        AVG(top_minus_bottom) AS test_top_minus_bottom_fwd_ret_mean
      FROM (
        SELECT
          run_id,
          predict_date,
          AVG(IF(score_bucket = 5, target_return, NULL))
            - AVG(IF(score_bucket = 1, target_return, NULL)) AS top_minus_bottom
        FROM (
          SELECT
            pred.run_id,
            pred.predict_date,
            tp.target_return,
            NTILE(5) OVER(PARTITION BY pred.run_id, pred.predict_date ORDER BY pred.score) AS score_bucket
          FROM `data-aquarium.ashare_ads.ads_model_prediction_daily` AS pred
          JOIN `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
            ON tp.run_id = pred.run_id
           AND tp.trade_date = pred.predict_date
           AND tp.sec_code = pred.sec_code
          WHERE pred.run_id IN UNNEST(@run_ids)
            AND pred.predict_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'
            AND tp.split_tag = 'test'
            AND tp.target_return IS NOT NULL
        )
        GROUP BY run_id, predict_date
      )
      GROUP BY run_id
    ),
    test_perf AS (
      SELECT
        run_id,
        EXP(SUM(IF(1.0 + daily_return > 0, LN(1.0 + daily_return), NULL))) - 1.0 AS test_year_total_return,
        EXP(SUM(IF(1.0 + benchmark_return > 0, LN(1.0 + benchmark_return), NULL))) - 1.0 AS test_year_benchmark_return
      FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily`
      WHERE run_id IN UNNEST(@run_ids)
        AND trade_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'
      GROUP BY run_id
    )
    SELECT
      reg.run_id,
      JSON_VALUE(reg.metrics_json, '$.candidate_id') AS candidate_id,
      JSON_VALUE(reg.metrics_json, '$.search_id') AS search_id,
      reg.model_id,
      reg.model_uri,
      reg.metrics_json AS registry_metrics_json,
      reg.model_params_json,
      summary.backtest_id,
      summary.total_return,
      summary.excess_return,
      summary.sharpe,
      summary.max_drawdown,
      summary.turnover_annual,
      summary.benchmark_sec_code,
      summary.cost_bps,
      summary.metrics_json AS summary_metrics_json,
      test_rank_ic.test_rank_ic_mean,
      test_rank_ic.test_rank_ic_icir,
      test_bucket_spread.test_top_minus_bottom_fwd_ret_mean,
      test_perf.test_year_total_return,
      test_perf.test_year_total_return - test_perf.test_year_benchmark_return AS test_year_excess_return
    FROM registry AS reg
    LEFT JOIN summary
      ON summary.model_id = reg.model_id
    LEFT JOIN test_rank_ic
      ON test_rank_ic.run_id = reg.run_id
    LEFT JOIN test_bucket_spread
      ON test_bucket_spread.run_id = reg.run_id
    LEFT JOIN test_perf
      ON test_perf.run_id = reg.run_id
    ORDER BY reg.run_id
    """
    rows = [
        dict(row)
        for row in client.query(
            sql,
            job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ArrayQueryParameter("run_ids", "STRING", run_ids),
                bigquery.ArrayQueryParameter("backtest_ids", "STRING", backtest_ids),
            ]),
        ).result()
    ]
    out = []
    for row in rows:
        reg_metrics = parse_json(row.get("registry_metrics_json"))
        summary_metrics = parse_json(row.get("summary_metrics_json"))
        run_id = row["run_id"]
        out.append({
            "run_id": run_id,
            "backtest_id": row.get("backtest_id"),
            "candidate_id": row.get("candidate_id") or candidate_by_run.get(run_id),
            "shortlist_rank_valid_only": rank_by_run.get(run_id),
            "model_id": row.get("model_id"),
            "model_uri": row.get("model_uri"),
            "valid_signal_status": reg_metrics.get("valid_signal_status"),
            "native_acceptance_status": reg_metrics.get("native_acceptance_status"),
            "native_acceptance_reason": reg_metrics.get("native_acceptance_reason"),
            "oriented_valid_rank_ic_mean": reg_metrics.get("oriented_valid_rank_ic_mean"),
            "oriented_valid_rank_ic_icir": reg_metrics.get("oriented_valid_rank_ic_icir"),
            "valid_topn_fwd_ret_mean": reg_metrics.get("valid_topn_fwd_ret_mean"),
            "valid_top_minus_bottom_fwd_ret_mean": reg_metrics.get("valid_top_minus_bottom_fwd_ret_mean"),
            "test_rank_ic_mean": row.get("test_rank_ic_mean"),
            "test_rank_ic_icir": row.get("test_rank_ic_icir"),
            "test_top_minus_bottom_fwd_ret_mean": row.get("test_top_minus_bottom_fwd_ret_mean"),
            "test_year_total_return": row.get("test_year_total_return"),
            "test_year_excess_return": row.get("test_year_excess_return"),
            "total_return": row.get("total_return"),
            "excess_return": row.get("excess_return"),
            "sharpe": row.get("sharpe"),
            "max_drawdown": row.get("max_drawdown"),
            "turnover_annual": row.get("turnover_annual"),
            "benchmark_sec_code": row.get("benchmark_sec_code"),
            "cost_bps": row.get("cost_bps"),
            "report_uri": summary_metrics.get("report_uri"),
            "model_diagnosis_uri": summary_metrics.get("model_diagnosis_uri"),
            "model_diagnosis_primary_diagnosis": summary_metrics.get("model_diagnosis_primary_diagnosis"),
            "model_diagnosis_confidence": summary_metrics.get("model_diagnosis_confidence"),
            "test_reuse_wave_no": reg_metrics.get("test_reuse_wave_no"),
            "test_reuse_approval_ref": reg_metrics.get("test_reuse_approval_ref"),
            "final_holdout_status": reg_metrics.get("final_holdout_status"),
        })
    return sorted(out, key=lambda row: row.get("shortlist_rank_valid_only") or 999)


def apply_native_acceptance_to_ads(
    client: bigquery.Client,
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> None:
    acceptance = manifest.get("native_acceptance") or {}
    for row in rows:
        status, reason = decide_acceptance(row, acceptance)
        patch_native_acceptance(client, row, status, reason)
        row["native_acceptance_status"] = status
        row["native_acceptance_reason"] = reason


def decide_acceptance(row: dict[str, Any], acceptance: dict[str, Any]) -> tuple[str, str]:
    valid_status = row.get("valid_signal_status")
    if valid_status != "stable":
        return ("needs_more_evidence" if valid_status == "weak" else "rejected", f"valid_signal_status={valid_status}")
    checks = [
        ("test_rank_ic_mean", row.get("test_rank_ic_mean"), float(acceptance.get("min_test_rank_ic", 0.0)), "gt"),
        ("test_year_total_return", row.get("test_year_total_return"), 0.0, "gt"),
        ("test_year_excess_return", row.get("test_year_excess_return"), float(acceptance.get("min_test_excess_return", 0.0)), "gt"),
        ("sharpe", row.get("sharpe"), float(acceptance.get("min_full_period_sharpe", 0.70)), "ge"),
        ("max_drawdown", row.get("max_drawdown"), float(acceptance.get("max_full_period_drawdown", -0.25)), "ge"),
    ]
    failures = []
    for name, actual, threshold, op in checks:
        actual_value = safe_float(actual)
        if not math.isfinite(actual_value):
            failures.append(f"{name}=missing")
            continue
        if op == "ge" and actual_value < threshold:
            failures.append(f"{name}<{threshold}")
        if op == "gt" and actual_value <= threshold:
            failures.append(f"{name}<={threshold}")
    valid_spread = safe_float(row.get("valid_top_minus_bottom_fwd_ret_mean"))
    test_spread = safe_float(row.get("test_top_minus_bottom_fwd_ret_mean"))
    if not math.isfinite(valid_spread):
        failures.append("valid_top_minus_bottom_fwd_ret_mean=missing")
    if not math.isfinite(test_spread):
        failures.append("test_top_minus_bottom_fwd_ret_mean=missing")
    if math.isfinite(valid_spread) and math.isfinite(test_spread) and valid_spread < 0 and test_spread < 0:
        failures.append("valid_and_test_top_minus_bottom_both_negative")
    if failures:
        return "rejected", ";".join(failures)
    return "accepted", "all_native_acceptance_gates_passed"


def patch_native_acceptance(client: bigquery.Client, row: dict[str, Any], status: str, reason: str) -> None:
    params = [
        bigquery.ScalarQueryParameter("run_id", "STRING", row["run_id"]),
        bigquery.ScalarQueryParameter("backtest_id", "STRING", row.get("backtest_id")),
        bigquery.ScalarQueryParameter("status", "STRING", status),
        bigquery.ScalarQueryParameter("reason", "STRING", reason),
        bigquery.ScalarQueryParameter("candidate_id", "STRING", row.get("candidate_id")),
        bigquery.ScalarQueryParameter("shortlist_rank", "INT64", row.get("shortlist_rank_valid_only")),
        bigquery.ScalarQueryParameter("test_rank_ic_mean", "FLOAT64", safe_float_or_none(row.get("test_rank_ic_mean"))),
        bigquery.ScalarQueryParameter("test_top_minus_bottom", "FLOAT64", safe_float_or_none(row.get("test_top_minus_bottom_fwd_ret_mean"))),
        bigquery.ScalarQueryParameter("test_year_total_return", "FLOAT64", safe_float_or_none(row.get("test_year_total_return"))),
        bigquery.ScalarQueryParameter("test_year_excess_return", "FLOAT64", safe_float_or_none(row.get("test_year_excess_return"))),
    ]
    client.query(
        """
        UPDATE `data-aquarium.ashare_ads.ads_model_registry` AS reg
        SET reg.metrics_json = TO_JSON_STRING(JSON_SET(
          PARSE_JSON(COALESCE(reg.metrics_json, '{}'), wide_number_mode => 'round'),
          '$.native_acceptance_status', @status,
          '$.native_acceptance_reason', @reason,
          '$.test_rank_ic_mean', @test_rank_ic_mean,
          '$.test_top_minus_bottom_fwd_ret_mean', @test_top_minus_bottom,
          '$.test_year_total_return', @test_year_total_return,
          '$.test_year_excess_return', @test_year_excess_return
        ))
        WHERE JSON_VALUE(reg.model_params_json, '$.run_id') = @run_id
          AND reg.status = 'selected'
        """,
        job_config=bigquery.QueryJobConfig(query_parameters=params),
    ).result()
    client.query(
        """
        UPDATE `data-aquarium.ashare_ads.ads_backtest_performance_summary` AS bs
        SET bs.metrics_json = TO_JSON_STRING(JSON_SET(
          PARSE_JSON(COALESCE(bs.metrics_json, '{}'), wide_number_mode => 'round'),
          '$.candidate_id', @candidate_id,
          '$.sklearn_native_baseline_candidate', true,
          '$.shortlist_rank_valid_only', @shortlist_rank,
          '$.native_acceptance_status', @status,
          '$.native_acceptance_reason', @reason,
          '$.test_rank_ic_mean', @test_rank_ic_mean,
          '$.test_top_minus_bottom_fwd_ret_mean', @test_top_minus_bottom,
          '$.test_year_total_return', @test_year_total_return,
          '$.test_year_excess_return', @test_year_excess_return
        ))
        WHERE bs.backtest_id = @backtest_id
        """,
        job_config=bigquery.QueryJobConfig(query_parameters=params),
    ).result()


def parse_json(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}


def fmt(value: Any, digits: int = 4) -> str:
    value = safe_float_or_none(value)
    if value is None:
        return "NA"
    return f"{value:.{digits}f}"


def safe_float(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return math.nan
    return out


def safe_float_or_none(value: Any) -> float | None:
    out = safe_float(value)
    return out if math.isfinite(out) else None


def step_plan(step: StepStateSpec) -> dict[str, Any]:
    return {
        "step_id": step.step_id,
        "display_name": step.display_name,
        "job_name": step.job_name,
        "lock_key": step.lock_key,
        "command": step.command,
    }


if __name__ == "__main__":
    raise SystemExit(main())
