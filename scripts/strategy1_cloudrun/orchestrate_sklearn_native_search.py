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
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
from google.cloud import bigquery

from scripts.strategy1_cloudrun import __version__
from scripts.strategy1_cloudrun.acceptance import (
    contract_version,
    decide_acceptance as decide_contract_acceptance,
    load_acceptance_contract,
    safe_float,
)
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
    expected_model_family = candidate_model_family(config)
    expected_model_search_wave_no = int(raw_manifest.get("model_search_wave_no") or test_reuse_wave_no)

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
        "expected_model_family": expected_model_family,
        "expected_model_search_wave_no": expected_model_search_wave_no,
        "build_training_panel": args.build_training_panel,
        "max_parallel_topk_backtests_arg": args.max_parallel_topk_backtests,
        "next_wave_manifest": raw_manifest.get("next_wave_manifest"),
        "auto_next_wave_on_needs_more_evidence": bool(
            args.auto_next_wave_on_needs_more_evidence
            or raw_manifest.get("auto_next_wave_on_needs_more_evidence")
        ),
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

    client = make_client(config.project, config.region)
    if args.build_training_panel:
        run_sql_script(
            client,
            "sql/ml/strategy1/01_build_training_panel.sql",
            build_training_panel_params(search_exp, force_replace=args.force_replace),
        )

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
        download_models=False,
    )
    manifest = read_json(matrix_local / "matrix_manifest.json")
    work_units = read_json(matrix_local / "work_units.json")
    candidates = load_candidates(
        matrix_local,
        manifest,
        work_units,
        require_all_candidates=not args.allow_partial_candidates,
        load_models=False,
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

    successful_topk_results = [item for item in topk_results if item.get("status") == "succeeded"]
    comparison_rows = fetch_topk_ads_outputs(client, successful_topk_results) if successful_topk_results else []
    contract = load_acceptance_contract(config.acceptance_contract_path)
    apply_native_acceptance_to_ads(client, comparison_rows, raw_manifest, contract)
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
    next_wave = maybe_run_next_wave(
        args=args,
        raw_manifest=raw_manifest,
        comparison_rows=comparison_rows,
    )
    if not args.skip_qa:
        qa_script = (
            "sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql"
            if search_id.startswith("sklearn_native_")
            else "sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql"
        )
        run_sql_script(
            client,
            qa_script,
            {
                "p_search_id": search_id,
                "p_source_run_id": search_exp.run_id,
                "p_expected_candidate_count": len(config.candidate_grid),
                "p_expected_candidate_parallelism": resolve_parallel_count(
                    len(config.candidate_grid),
                    args.candidate_parallelism,
                ),
                "p_expected_model_family": expected_model_family,
                "p_expected_model_search_wave_no": expected_model_search_wave_no,
                "p_top_k": top_k,
                "p_test_reuse_wave_no": test_reuse_wave_no,
                "p_acceptance_contract_version": contract_version(contract),
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
        "next_wave": next_wave,
        "topk_results": topk_results,
    }, ensure_ascii=False, indent=2, default=str))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategy 1 sklearn native search orchestrator")
    add_common_args(parser)
    parser.add_argument("--experiment-id", default=None)
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
    parser.add_argument("--build-training-panel", action="store_true")
    parser.add_argument("--auto-next-wave-on-needs-more-evidence", action="store_true")
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


def candidate_model_family(config) -> str:
    families = {
        str(candidate.get("model_family") or "logistic_regression")
        for candidate in config.candidate_grid
    }
    if len(families) != 1:
        raise ValueError(f"candidate_grid must use one model_family per search, got {sorted(families)}")
    return next(iter(families))


def maybe_run_next_wave(
    *,
    args: argparse.Namespace,
    raw_manifest: dict[str, Any],
    comparison_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    accepted = [row for row in comparison_rows if row.get("native_acceptance_status") == "accepted"]
    needs = [row for row in comparison_rows if row.get("native_acceptance_status") == "needs_more_evidence"]
    if accepted or not needs:
        return {"triggered": False, "reason": "accepted_exists_or_no_needs_more_evidence"}
    next_manifest = raw_manifest.get("next_wave_manifest")
    if not next_manifest:
        return {"triggered": False, "reason": "next_wave_manifest_missing"}
    cmd = [
        sys.executable,
        "-m",
        "scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search",
        f"--project={args.project}" if args.project else None,
        f"--region={args.region}" if args.region else None,
        f"--config={next_manifest}",
        f"--manifest={next_manifest}",
        f"--candidate-parallelism={args.candidate_parallelism}",
        f"--top-k-backtest={args.top_k_backtest}" if args.top_k_backtest else None,
    ]
    if args.force_replace:
        cmd.append("--force-replace")
    if args.build_training_panel:
        cmd.append("--build-training-panel")
    if args.skip_diagnosis:
        cmd.append("--skip-diagnosis")
    if args.skip_qa:
        cmd.append("--skip-qa")
    cmd = [part for part in cmd if part is not None]
    auto = bool(args.auto_next_wave_on_needs_more_evidence or raw_manifest.get("auto_next_wave_on_needs_more_evidence"))
    if not auto:
        return {"triggered": False, "reason": "auto_next_wave_disabled", "command": cmd}
    subprocess.run(cmd, check=True)
    return {"triggered": True, "reason": "needs_more_evidence", "command": cmd}


def build_training_panel_params(exp: Experiment, *, force_replace: bool) -> dict[str, Any]:
    return {
        "p_run_id": exp.run_id,
        "p_strategy_id": "ml_pv_clf_v0",
        "p_experiment_id": exp.experiment_id,
        "p_experiment_group": exp.experiment_group,
        "p_baseline_experiment_id": exp.baseline_experiment_id,
        "p_parent_experiment_id": exp.parent_experiment_id,
        "p_parent_run_id": exp.parent_run_id,
        "p_preprocess_version": "raw_v0",
        "p_feature_version": exp.feature_version,
        "p_feature_set_id": exp.feature_set_id,
        "p_fin_feature_version": exp.fin_feature_version,
        "p_label_horizon": exp.label_horizon,
        "p_rebalance_frequency": exp.rebalance_frequency,
        "p_target_holdings": exp.target_holdings,
        "p_max_single_weight": exp.max_single_weight,
        "p_horizon_natural_frequency": exp.horizon_natural_frequency,
        "p_train_start": exp.train_start,
        "p_train_end": exp.train_end,
        "p_valid_start": exp.valid_start,
        "p_valid_end": exp.valid_end,
        "p_test_start": exp.test_start,
        "p_test_end": exp.test_end,
        "p_final_holdout_start": exp.final_holdout_start,
        "p_final_holdout_end": exp.final_holdout_end,
        "p_force_replace": force_replace,
    }


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
    download_models: bool = True,
) -> Path:
    local_dir = Path(matrix_local) if matrix_local else Path(tempfile.mkdtemp(prefix="strategy1-native-search-"))
    for rel in ("matrix_manifest.json", "work_units.json"):
        download_gcs_file(project, join_gs_uri(matrix_uri, rel), local_dir / rel)
    for unit_index in range(candidate_count):
        names = ["candidate_metrics.json", "task_status.json"]
        if download_models:
            names.append("model.joblib")
        for name in names:
            rel = f"candidates/unit_index={unit_index}/{name}"
            download_gcs_file(project, join_gs_uri(matrix_uri, rel), local_dir / rel)
    return local_dir


def topk_experiment(search_exp: Experiment, search_id: str, candidate_id: str) -> Experiment:
    candidate_safe = candidate_id.replace("-", "_")
    if search_id.startswith(("sklearn_native_", "cloudrun_python_")):
        run_prefix = f"s1_{search_id}"
    else:
        run_prefix = f"s1_cloudrun_python_{search_id}"
    group = "sklearn_native_top5_backtest" if search_id.startswith("sklearn_native_") else "cloudrun_python_top5_backtest"
    return dataclasses.replace(
        search_exp,
        experiment_id=f"{search_exp.experiment_id}__{candidate_safe}",
        run_id=f"{run_prefix}__{candidate_safe}",
        prediction_run_id=f"{run_prefix}__{candidate_safe}",
        backtest_id=f"bt_{run_prefix}__{candidate_safe}",
        experiment_group=group,
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
    dirname = "sklearn_native_search" if search_id.startswith("sklearn_native_") else "cloudrun_python_baseline_search"
    return Path(config.local_mirror_root) / dirname / f"search_id={search_id}"


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
    if not search_id.startswith("sklearn_native_"):
        write_json(out_dir / "selected_cloudrun_python_baseline.json", selected or {
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
        "# 策略 1 Cloud Run Python 候选搜索对比",
        "",
        f"- search_id: `{payload['search_id']}`",
        f"- source_run_id: `{payload['search_experiment']['run_id']}`",
        f"- matrix_uri: `{payload['matrix_uri']}`",
        f"- ranking_uses_test_metrics: `{payload['ranking_uses_test_metrics']}`",
        f"- test_reuse_wave_no: `{payload.get('test_reuse_wave_no')}`",
        "",
        "## CV + Valid Top 5",
        "",
        "| rank | candidate_id | CV status | CV RankIC | CV spread | valid RankIC | valid spread | signal |",
        "|---:|---|---|---:|---:|---:|---:|---|",
    ]
    for row in payload.get("ranking", []):
        if row.get("shortlist_rank_valid_only") is None:
            continue
        lines.append(
            f"| {row.get('shortlist_rank_valid_only')} | `{row.get('candidate_id')}` | "
            f"{row.get('cv_confirmation_status') or 'NA'} | "
            f"{fmt(row.get('cv_rank_ic_mean'))} | "
            f"{fmt(row.get('cv_top_minus_bottom_fwd_ret_mean'))} | "
            f"{fmt(row.get('valid_oriented_rank_ic_mean'))} | "
            f"{fmt(row.get('valid_top_minus_bottom_fwd_ret_mean'))} | "
            f"{row.get('valid_signal_status')} |"
        )
    if comparison_rows:
        lines.extend([
            "",
            "## Top 5 回测",
            "",
            "| rank | candidate_id | status | total_return | excess_return | sharpe | max_drawdown | test RankIC | test excess | final holdout excess |",
            "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for row in comparison_rows:
            lines.append(
                f"| {row.get('shortlist_rank_valid_only')} | `{row.get('candidate_id')}` | "
                f"{row.get('native_acceptance_status')} | {fmt(row.get('total_return'))} | "
                f"{fmt(row.get('excess_return'))} | {fmt(row.get('sharpe'))} | "
                f"{fmt(row.get('max_drawdown'))} | {fmt(row.get('test_rank_ic_mean'))} | "
                f"{fmt(row.get('test_year_excess_return'))} | "
                f"{fmt(row.get('final_holdout_excess_return'))} |"
            )
    lines.extend([
        "",
        "## 说明",
        "",
        "- Top 5 排名只使用 2021/2022/2023 CV 与 2024 valid；test / final_holdout 只用于验收和风险复核。",
        "- `accepted` 要求满足共享验收契约 `model_acceptance_contract_v1`。",
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
    ),
    final_holdout_perf AS (
      SELECT
        run_id,
        COUNT(*) AS final_holdout_trading_days,
        EXP(SUM(IF(1.0 + daily_return > 0, LN(1.0 + daily_return), NULL))) - 1.0 AS final_holdout_total_return,
        EXP(SUM(IF(1.0 + benchmark_return > 0, LN(1.0 + benchmark_return), NULL))) - 1.0 AS final_holdout_benchmark_return
      FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily`
      WHERE run_id IN UNNEST(@run_ids)
        AND trade_date BETWEEN DATE '2026-01-05' AND DATE '2026-04-30'
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
      test_perf.test_year_total_return - test_perf.test_year_benchmark_return AS test_year_excess_return,
      final_holdout_perf.final_holdout_trading_days,
      final_holdout_perf.final_holdout_total_return,
      final_holdout_perf.final_holdout_total_return - final_holdout_perf.final_holdout_benchmark_return
        AS final_holdout_excess_return
    FROM registry AS reg
    LEFT JOIN summary
      ON summary.model_id = reg.model_id
    LEFT JOIN test_rank_ic
      ON test_rank_ic.run_id = reg.run_id
    LEFT JOIN test_bucket_spread
      ON test_bucket_spread.run_id = reg.run_id
    LEFT JOIN test_perf
      ON test_perf.run_id = reg.run_id
    LEFT JOIN final_holdout_perf
      ON final_holdout_perf.run_id = reg.run_id
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
            "cv_confirmation_status": reg_metrics.get("cv_confirmation_status"),
            "cv_rank_ic_mean": reg_metrics.get("cv_rank_ic_mean"),
            "cv_top_minus_bottom_fwd_ret_mean": reg_metrics.get("cv_top_minus_bottom_fwd_ret_mean"),
            "acceptance_contract_version": reg_metrics.get("acceptance_contract_version"),
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
            "test_year_excess_return_vs_000852": row.get("test_year_excess_return"),
            "final_holdout_trading_days": row.get("final_holdout_trading_days"),
            "final_holdout_total_return": row.get("final_holdout_total_return"),
            "final_holdout_excess_return": row.get("final_holdout_excess_return"),
            "final_holdout_excess_return_vs_000852": row.get("final_holdout_excess_return"),
            "total_return": row.get("total_return"),
            "excess_return": row.get("excess_return"),
            "overall_excess_return_vs_000852": row.get("excess_return"),
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
    contract: dict[str, Any],
) -> None:
    for row in rows:
        row.setdefault("acceptance_contract_version", contract_version(contract))
        status, reason, derived = decide_contract_acceptance(row, contract)
        patch_native_acceptance(client, row, status, reason, derived)
        row["native_acceptance_status"] = status
        row["native_acceptance_reason"] = reason
        row.update(derived)


def patch_native_acceptance(
    client: bigquery.Client,
    row: dict[str, Any],
    status: str,
    reason: str,
    derived: dict[str, Any],
) -> None:
    params = [
        bigquery.ScalarQueryParameter("run_id", "STRING", row["run_id"]),
        bigquery.ScalarQueryParameter("backtest_id", "STRING", row.get("backtest_id")),
        bigquery.ScalarQueryParameter("status", "STRING", status),
        bigquery.ScalarQueryParameter("reason", "STRING", reason),
        bigquery.ScalarQueryParameter("acceptance_contract_version", "STRING", derived.get("acceptance_contract_version")),
        bigquery.ScalarQueryParameter("holdout_watch_flag", "BOOL", bool(derived.get("holdout_watch_flag"))),
        bigquery.ScalarQueryParameter("candidate_id", "STRING", row.get("candidate_id")),
        bigquery.ScalarQueryParameter("shortlist_rank", "INT64", row.get("shortlist_rank_valid_only")),
        bigquery.ScalarQueryParameter("test_rank_ic_mean", "FLOAT64", safe_float_or_none(row.get("test_rank_ic_mean"))),
        bigquery.ScalarQueryParameter("test_top_minus_bottom", "FLOAT64", safe_float_or_none(row.get("test_top_minus_bottom_fwd_ret_mean"))),
        bigquery.ScalarQueryParameter("test_year_total_return", "FLOAT64", safe_float_or_none(row.get("test_year_total_return"))),
        bigquery.ScalarQueryParameter("test_year_excess_return", "FLOAT64", safe_float_or_none(row.get("test_year_excess_return"))),
        bigquery.ScalarQueryParameter("final_holdout_trading_days", "INT64", row.get("final_holdout_trading_days")),
        bigquery.ScalarQueryParameter("final_holdout_total_return", "FLOAT64", safe_float_or_none(row.get("final_holdout_total_return"))),
        bigquery.ScalarQueryParameter("final_holdout_excess_return", "FLOAT64", safe_float_or_none(row.get("final_holdout_excess_return"))),
    ]
    client.query(
        """
        UPDATE `data-aquarium.ashare_ads.ads_model_registry` AS reg
        SET reg.metrics_json = TO_JSON_STRING(JSON_SET(
          PARSE_JSON(COALESCE(reg.metrics_json, '{}'), wide_number_mode => 'round'),
          '$.native_acceptance_status', @status,
          '$.native_acceptance_reason', @reason,
          '$.acceptance_contract_version', @acceptance_contract_version,
          '$.holdout_watch_flag', @holdout_watch_flag,
          '$.test_rank_ic_mean', @test_rank_ic_mean,
          '$.test_top_minus_bottom_fwd_ret_mean', @test_top_minus_bottom,
          '$.test_year_total_return', @test_year_total_return,
          '$.test_year_excess_return', @test_year_excess_return,
          '$.final_holdout_trading_days', @final_holdout_trading_days,
          '$.final_holdout_total_return', @final_holdout_total_return,
          '$.final_holdout_excess_return', @final_holdout_excess_return
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
          '$.acceptance_contract_version', @acceptance_contract_version,
          '$.holdout_watch_flag', @holdout_watch_flag,
          '$.test_rank_ic_mean', @test_rank_ic_mean,
          '$.test_top_minus_bottom_fwd_ret_mean', @test_top_minus_bottom,
          '$.test_year_total_return', @test_year_total_return,
          '$.test_year_excess_return', @test_year_excess_return,
          '$.final_holdout_trading_days', @final_holdout_trading_days,
          '$.final_holdout_total_return', @final_holdout_total_return,
          '$.final_holdout_excess_return', @final_holdout_excess_return
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
