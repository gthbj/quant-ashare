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
import itertools
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from google.cloud import bigquery

from scripts.strategy1_cloudrun import __version__
from scripts.strategy1_cloudrun.acceptance import (
    contract_sql_params,
    contract_version,
    decide_acceptance as decide_contract_acceptance,
    derive_final_holdout_status,
    load_acceptance_contract,
    risk_feature_max_drawdown_target,
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
    effective_candidate_parallelism,
    experiment_to_b64,
    filter_experiments,
    load_manifest,
    load_runner_config,
    manifest_hash,
    read_mapping,
    resolve_parallel_count,
)
from scripts.strategy1_cloudrun.feature_sets import PV_FIN_RISK_FEATURE_SET_ID
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
from scripts.strategy1.replay_acceptance_gate_v3 import (
    apply_contract_defaults as apply_v3_contract_defaults,
    comparison_benchmarks as v3_comparison_benchmarks,
    ensure_benchmark_coverage as ensure_v3_benchmark_coverage,
    evaluate_candidate as evaluate_v3_candidate,
    fetch_benchmark_rows as fetch_v3_benchmark_rows,
    fetch_nav_rows as fetch_v3_nav_rows,
    split_nav_by_backtest as split_v3_nav_by_backtest,
    split_prices_by_benchmark as split_v3_prices_by_benchmark,
)


def main() -> int:
    args = parse_args()
    config = apply_cli_overrides(load_runner_config(args.config), args)
    requested_candidate_parallelism = effective_candidate_parallelism(config, args.candidate_parallelism)
    candidate_parallelism_source = "cli" if args.candidate_parallelism not in (None, 0) else "config"
    args.candidate_parallelism_from_cli = args.candidate_parallelism not in (None, 0)
    args.candidate_parallelism = requested_candidate_parallelism
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
        "candidate_parallelism_arg": requested_candidate_parallelism,
        "candidate_parallelism_source": candidate_parallelism_source,
        "candidate_task_cpu": config.candidate_task_cpu,
        "candidate_task_memory": config.candidate_task_memory,
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
            config.training_panel_sql,
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
    comparison_rows = fetch_topk_ads_outputs(client, successful_topk_results, search_exp) if successful_topk_results else []
    comparison_rows = enrich_tail_risk_rows(client, comparison_rows)
    contract = load_acceptance_contract(config.acceptance_contract_path)
    v3_benchmark_rows: list[dict[str, Any]] = []
    if contract_version(contract) == "model_acceptance_contract_v3":
        comparison_rows, v3_benchmark_rows = enrich_v3_acceptance_rows(
            client,
            config,
            search_exp,
            comparison_rows,
            contract,
        )
    apply_native_acceptance_to_ads(client, comparison_rows, raw_manifest, contract)
    comparison_rows = fetch_topk_ads_outputs(client, successful_topk_results, search_exp) if successful_topk_results else []
    comparison_rows = enrich_tail_risk_rows(client, comparison_rows)
    if contract_version(contract) == "model_acceptance_contract_v3":
        comparison_rows, v3_benchmark_rows = enrich_v3_acceptance_rows(
            client,
            config,
            search_exp,
            comparison_rows,
            contract,
        )
    overlap_rows, common_crash_rows = build_search_tail_risk_artifacts(client, search_id, comparison_rows)
    write_final_comparison(
        comparison_dir,
        search_id=search_id,
        search_exp=search_exp,
        matrix_uri=matrix_uri,
        matrix_local=matrix_local,
        ranking=ranking,
        top_rows=top_rows,
        comparison_rows=comparison_rows,
        v3_benchmark_rows=v3_benchmark_rows,
        overlap_rows=overlap_rows,
        common_crash_rows=common_crash_rows,
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
        qa_script = (
            "sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql"
            if search_id.startswith("sklearn_native_")
            else "sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql"
        )
        qa_params = {
            "p_search_id": search_id,
            "p_source_run_id": search_exp.run_id,
            "p_expected_candidate_count": len(config.candidate_grid),
            "p_expected_candidate_parallelism": resolve_parallel_count(
                len(config.candidate_grid),
                args.candidate_parallelism,
            ),
            "p_expected_candidate_task_cpu": config.candidate_task_cpu,
            "p_expected_candidate_task_memory": config.candidate_task_memory,
            "p_expected_model_family": expected_model_family,
            "p_expected_model_search_wave_no": expected_model_search_wave_no,
            "p_top_k": top_k,
            "p_test_reuse_wave_no": test_reuse_wave_no,
            "p_acceptance_contract_version": contract_version(contract),
            "p_valid_start_date": search_exp.valid_start,
            "p_valid_end_date": search_exp.valid_end,
            "p_test_start_date": search_exp.test_start,
            "p_test_end_date": search_exp.test_end,
            "p_final_holdout_start_date": search_exp.final_holdout_start,
            "p_final_holdout_end_date": search_exp.final_holdout_end,
            "p_data_end_date": search_exp.final_holdout_end or search_exp.predict_end,
        }
        qa_params.update(contract_sql_params(contract))
        run_sql_script(client, qa_script, qa_params)
        if search_exp.feature_set_id == PV_FIN_RISK_FEATURE_SET_ID:
            risk_qa_params = contract_sql_params(contract)
            risk_qa_params = {
                **risk_qa_params,
                "p_search_id": search_id,
                "p_source_run_id": search_exp.run_id,
                "p_expected_feature_set_id": search_exp.feature_set_id,
                "p_expected_model_search_wave_no": expected_model_search_wave_no,
                "p_top_k": top_k,
                "p_test_reuse_wave_no": test_reuse_wave_no,
                "p_test_reuse_approval_ref": test_reuse_approval_ref,
                "p_market_state_version": search_exp.market_state_version,
                "p_train_start_date": search_exp.train_start,
                "p_data_end_date": search_exp.final_holdout_end or search_exp.predict_end,
                "p_final_holdout_start_date": search_exp.final_holdout_start,
                "p_final_holdout_end_date": search_exp.final_holdout_end,
            }
            run_sql_script(client, "sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql", risk_qa_params)
    next_wave = maybe_run_next_wave(
        args=args,
        raw_manifest=raw_manifest,
        comparison_rows=comparison_rows,
    )
    print(json.dumps({
        "status": "succeeded",
        "search_id": search_id,
        "matrix_uri": matrix_uri,
        "candidate_count": len(config.candidate_grid),
        "candidate_parallelism_arg": args.candidate_parallelism,
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
    completed = subprocess.run(cmd, check=False)
    return {
        "triggered": True,
        "reason": "needs_more_evidence",
        "command": cmd,
        "returncode": completed.returncode,
        "status": "succeeded" if completed.returncode == 0 else "failed",
    }


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
        "p_market_state_version": exp.market_state_version,
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
        f"--search-id={search_id}",
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
    matrix_local: Path | None,
    ranking: list[dict[str, Any]],
    top_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    v3_benchmark_rows: list[dict[str, Any]],
    overlap_rows: list[dict[str, Any]],
    common_crash_rows: list[dict[str, Any]],
    topk_execution_results: list[dict[str, Any]],
    test_reuse_wave_no: int,
    test_reuse_approval_ref: str | None,
    final_holdout_status: str | None,
) -> None:
    pd.DataFrame(ranking).to_csv(out_dir / "candidate_ranking.csv", index=False)
    pd.DataFrame(comparison_rows).to_csv(out_dir / "top5_backtest_summary.csv", index=False)
    if v3_benchmark_rows:
        pd.DataFrame(v3_benchmark_rows).to_csv(out_dir / "v3_relative_gate_by_benchmark.csv", index=False)
    write_feature_search_artifacts(out_dir, matrix_local, comparison_rows)
    tail_cols = [
        "candidate_id", "run_id", "backtest_id", "tail_risk_profile_id",
        "tail_risk_peak_date", "tail_risk_trough_date", "tail_risk_drawdown_pct",
        "tail_risk_benchmark_return", "tail_risk_excess_return",
        "tail_risk_limit_down_weight_peak", "tail_risk_uri",
    ]
    tail_dir = out_dir / "tail_risk"
    tail_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{key: row.get(key) for key in tail_cols} for row in comparison_rows]).to_csv(
        tail_dir / "search_tail_risk_summary.csv",
        index=False,
    )
    pd.DataFrame(overlap_rows or [], columns=[
        "search_id", "signal_date", "left_run_id", "right_run_id",
        "left_candidate_id", "right_candidate_id", "left_selected_count",
        "right_selected_count", "overlap_count",
    ]).to_csv(tail_dir / "candidate_overlap_by_signal_date.csv", index=False)
    pd.DataFrame(common_crash_rows or [], columns=[
        "search_id", "signal_date", "sec_code", "sec_name", "selected_run_count",
        "run_ids", "candidate_ids", "window_cumulative_contribution",
    ]).to_csv(tail_dir / "common_crash_names.csv", index=False)
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
        "feature_delta_vs_base_uri": "feature_delta_vs_base.json" if (out_dir / "feature_delta_vs_base.json").exists() else None,
        "ranking_uses_test_metrics": False,
        "top_k_candidate_ids": [row["candidate_id"] for row in top_rows],
        "test_reuse_wave_no": test_reuse_wave_no,
        "test_reuse_approval_ref": test_reuse_approval_ref,
        "final_holdout_status": final_holdout_status,
        "acceptance_contract_version": selected.get("acceptance_contract_version") if selected else None,
        "acceptance_contract_sha256": selected.get("acceptance_contract_sha256") if selected else None,
        "acceptance_gate_version": selected.get("acceptance_gate_version") if selected else None,
        "ranking": ranking,
        "topk_execution_results": topk_execution_results,
        "top5_backtest_summary": comparison_rows,
        "v3_relative_gate_by_benchmark": v3_benchmark_rows,
        "selected_sklearn_native_baseline": selected,
    }
    write_json(out_dir / "sklearn_native_candidate_comparison.json", payload)
    write_text(out_dir / "sklearn_native_candidate_comparison.md", render_comparison_md(payload, comparison_rows))


def write_feature_search_artifacts(
    out_dir: Path,
    matrix_local: Path | None,
    comparison_rows: list[dict[str, Any]],
) -> None:
    if matrix_local:
        feature_delta_path = matrix_local / "feature_delta_vs_base.json"
        if feature_delta_path.exists():
            write_json(out_dir / "feature_delta_vs_base.json", read_json(feature_delta_path))
    group_rows: list[dict[str, Any]] = []
    for row in comparison_rows:
        for item in row.get("feature_group_importance") or []:
            group_rows.append({
                "candidate_id": row.get("candidate_id"),
                "run_id": row.get("run_id"),
                "shortlist_rank_valid_only": row.get("shortlist_rank_valid_only"),
                "native_acceptance_status": row.get("native_acceptance_status"),
                "feature_group": item.get("feature_group"),
                "feature_count": item.get("feature_count"),
                "gain_importance": item.get("gain_importance"),
                "gain_share": item.get("gain_share"),
                "split_importance": item.get("split_importance"),
                "split_share": item.get("split_share"),
            })
    pd.DataFrame(group_rows or [], columns=[
        "candidate_id", "run_id", "shortlist_rank_valid_only", "native_acceptance_status",
        "feature_group", "feature_count", "gain_importance", "gain_share",
        "split_importance", "split_share",
    ]).to_csv(out_dir / "feature_group_importance_summary.csv", index=False)


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
            "| rank | candidate_id | status | total_return | excess_return | sharpe | v3 Calmar | v3 passed benchmarks | max_drawdown | risk gain | market gain | max DD window | limit-down weight peak | test RankIC | test excess | final holdout excess |",
            "|---:|---|---|---:|---:|---:|---:|---|---:|---:|---:|---|---:|---:|---:|---:|",
        ])
        for row in comparison_rows:
            dd_window = "NA"
            if row.get("tail_risk_peak_date") and row.get("tail_risk_trough_date"):
                dd_window = f"{row.get('tail_risk_peak_date')}→{row.get('tail_risk_trough_date')}"
            lines.append(
                f"| {row.get('shortlist_rank_valid_only')} | `{row.get('candidate_id')}` | "
                f"{row.get('native_acceptance_status')} | {fmt(row.get('total_return'))} | "
                f"{fmt(row.get('excess_return'))} | {fmt(row.get('sharpe'))} | "
                f"{fmt(row.get('v3_calmar_ratio'))} | "
                f"{row.get('v3_passed_benchmark_sec_codes') or 'NA'} | "
                f"{fmt(row.get('max_drawdown'))} | "
                f"{fmt(row.get('risk_feature_importance_gain_share'))} | "
                f"{fmt(row.get('market_state_importance_gain_share'))} | "
                f"{dd_window} | "
                f"{fmt(row.get('tail_risk_limit_down_weight_peak'))} | "
                f"{fmt(row.get('test_rank_ic_mean'))} | "
                f"{fmt(row.get('test_year_excess_return'))} | "
                f"{fmt(row.get('final_holdout_excess_return'))} |"
            )
    lines.extend([
        "",
        "## 说明",
        "",
        "- Top 5 排名只使用 2021/2022/2023 CV 与 2024 valid；test / final_holdout 只用于验收和风险复核。",
        f"- `accepted` 要求满足共享验收契约 `{payload.get('acceptance_contract_version') or 'model_acceptance_contract_v3'}`。",
    ])
    return "\n".join(lines) + "\n"


def fetch_topk_ads_outputs(
    client: bigquery.Client,
    topk_results: list[dict[str, Any]],
    search_exp: Experiment,
) -> list[dict[str, Any]]:
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
            AND pred.predict_date BETWEEN @test_start AND @test_end
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
            AND pred.predict_date BETWEEN @test_start AND @test_end
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
        AND trade_date BETWEEN @test_start AND @test_end
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
        AND @final_holdout_start IS NOT NULL
        AND @final_holdout_end IS NOT NULL
        AND trade_date BETWEEN @final_holdout_start AND @final_holdout_end
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
      summary.start_date,
      summary.end_date,
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
                bigquery.ScalarQueryParameter("test_start", "DATE", search_exp.test_start),
                bigquery.ScalarQueryParameter("test_end", "DATE", search_exp.test_end),
                bigquery.ScalarQueryParameter("final_holdout_start", "DATE", search_exp.final_holdout_start),
                bigquery.ScalarQueryParameter("final_holdout_end", "DATE", search_exp.final_holdout_end),
            ]),
        ).result()
    ]
    out = []
    for row in rows:
        reg_metrics = parse_json(row.get("registry_metrics_json"))
        summary_metrics = parse_json(row.get("summary_metrics_json"))
        run_id = row["run_id"]
        out.append({
            "search_id": row.get("search_id"),
            "run_id": run_id,
            "backtest_id": row.get("backtest_id"),
            "start_date": row.get("start_date"),
            "end_date": row.get("end_date"),
            "candidate_id": row.get("candidate_id") or candidate_by_run.get(run_id),
            "shortlist_rank_valid_only": rank_by_run.get(run_id),
            "model_id": row.get("model_id"),
            "model_uri": row.get("model_uri"),
            "valid_signal_status": reg_metrics.get("valid_signal_status"),
            "score_orientation": reg_metrics.get("score_orientation"),
            "cv_confirmation_status": reg_metrics.get("cv_confirmation_status"),
            "model_family": reg_metrics.get("model_family"),
            "model_backend": reg_metrics.get("model_backend"),
            "primary_diagnosis": reg_metrics.get("primary_diagnosis")
                or summary_metrics.get("model_diagnosis_primary_diagnosis"),
            "sample_filter_risk": reg_metrics.get("sample_filter_risk"),
            "cv_rank_ic_mean": reg_metrics.get("cv_rank_ic_mean"),
            "cv_top_minus_bottom_fwd_ret_mean": reg_metrics.get("cv_top_minus_bottom_fwd_ret_mean"),
            "acceptance_contract_version": reg_metrics.get("acceptance_contract_version"),
            "native_acceptance_status": reg_metrics.get("native_acceptance_status"),
            "native_acceptance_reason": reg_metrics.get("native_acceptance_reason"),
            "oriented_valid_rank_ic_mean": reg_metrics.get("oriented_valid_rank_ic_mean"),
            "oriented_valid_rank_ic_icir": reg_metrics.get("oriented_valid_rank_ic_icir"),
            "valid_topn_fwd_ret_mean": reg_metrics.get("valid_topn_fwd_ret_mean"),
            "valid_top_minus_bottom_fwd_ret_mean": reg_metrics.get("valid_top_minus_bottom_fwd_ret_mean"),
            "feature_set_id": reg_metrics.get("feature_set_id"),
            "feature_count": reg_metrics.get("feature_count"),
            "risk_feature_count": reg_metrics.get("risk_feature_count"),
            "market_state_feature_count": reg_metrics.get("market_state_feature_count"),
            "market_state_features_enabled": reg_metrics.get("market_state_features_enabled"),
            "feature_schema_sha256": reg_metrics.get("feature_schema_sha256"),
            "feature_delta_vs_base_sha256": reg_metrics.get("feature_delta_vs_base_sha256"),
            "feature_importance_available": reg_metrics.get("feature_importance_available"),
            "feature_group_importance": reg_metrics.get("feature_group_importance"),
            "risk_feature_importance_gain_share": reg_metrics.get("risk_feature_importance_gain_share"),
            "market_state_importance_gain_share": reg_metrics.get("market_state_importance_gain_share"),
            "test_rank_ic_mean": row.get("test_rank_ic_mean"),
            "test_rank_ic_icir": row.get("test_rank_ic_icir"),
            "test_top_minus_bottom_fwd_ret_mean": row.get("test_top_minus_bottom_fwd_ret_mean"),
            "test_year_total_return": row.get("test_year_total_return"),
            "test_year_excess_return": row.get("test_year_excess_return"),
            "test_year_excess_return_vs_primary_benchmark": row.get("test_year_excess_return"),
            "final_holdout_trading_days": row.get("final_holdout_trading_days"),
            "final_holdout_total_return": row.get("final_holdout_total_return"),
            "final_holdout_excess_return": row.get("final_holdout_excess_return"),
            "final_holdout_excess_return_vs_primary_benchmark": row.get("final_holdout_excess_return"),
            "total_return": row.get("total_return"),
            "excess_return": row.get("excess_return"),
            "overall_excess_return_vs_primary_benchmark": row.get("excess_return"),
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
            "tail_risk_profile_id": summary_metrics.get("tail_risk_profile_id")
                or reg_metrics.get("tail_risk_profile_id")
                or "diagnostic_only",
        })
    return sorted(out, key=lambda row: row.get("shortlist_rank_valid_only") or 999)


def enrich_tail_risk_rows(client: bigquery.Client, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    backtest_ids = [row.get("backtest_id") for row in rows if row.get("backtest_id")]
    if not backtest_ids:
        return rows
    start_dates = [str(row.get("start_date")) for row in rows if row.get("start_date")]
    end_dates = [str(row.get("end_date")) for row in rows if row.get("end_date")]
    if not start_dates or not end_dates:
        return rows
    start_date = min(start_dates)
    end_date = max(end_dates)
    nav_sql = """
    SELECT
      bt_nav.backtest_id,
      bt_nav.trade_date,
      bt_nav.nav,
      bt_nav.daily_return,
      bt_nav.benchmark_return,
      bt_nav.excess_return
    FROM `data-aquarium.ashare_ads.ads_backtest_nav_daily` AS bt_nav
    WHERE bt_nav.backtest_id IN UNNEST(@backtest_ids)
      AND bt_nav.trade_date BETWEEN @start_date AND @end_date
    ORDER BY bt_nav.backtest_id, bt_nav.trade_date
    """
    pos_sql = """
    SELECT
      pos.backtest_id,
      pos.trade_date,
      pos.sec_code,
      pos.weight,
      px.ret_1d,
      px.is_limit_down
    FROM `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
    LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
      ON px.sec_code = pos.sec_code
     AND px.trade_date = pos.trade_date
     AND px.trade_date BETWEEN @start_date AND @end_date
    WHERE pos.backtest_id IN UNNEST(@backtest_ids)
      AND pos.trade_date BETWEEN @start_date AND @end_date
    """
    params = [
        bigquery.ArrayQueryParameter("backtest_ids", "STRING", backtest_ids),
        bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
        bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
    ]
    nav = client.query(
        nav_sql,
        job_config=bigquery.QueryJobConfig(query_parameters=params),
    ).to_dataframe(create_bqstorage_client=False)
    pos = client.query(
        pos_sql,
        job_config=bigquery.QueryJobConfig(query_parameters=params),
    ).to_dataframe(create_bqstorage_client=False)
    if nav.empty:
        return rows
    nav["trade_date"] = pd.to_datetime(nav["trade_date"]).dt.date
    if not pos.empty:
        pos["trade_date"] = pd.to_datetime(pos["trade_date"]).dt.date
    by_backtest = {}
    for backtest_id, group in nav.groupby("backtest_id"):
        event = compute_tail_risk_event(group)
        if event is None:
            continue
        limit_peak = None
        if not pos.empty:
            p = pos[pos["backtest_id"] == backtest_id].copy()
            if not p.empty:
                peak = pd.Timestamp(event["tail_risk_peak_date"]).date()
                trough = pd.Timestamp(event["tail_risk_trough_date"]).date()
                p = p[(p["trade_date"] >= peak) & (p["trade_date"] <= trough)]
                if not p.empty:
                    ret = pd.to_numeric(p["ret_1d"], errors="coerce")
                    is_limit = p["is_limit_down"].fillna(False).astype(bool)
                    fallback = p["is_limit_down"].isna() & (ret <= -0.095)
                    p["limit_weight"] = np.where(is_limit | fallback, pd.to_numeric(p["weight"], errors="coerce").fillna(0.0), 0.0)
                    limit_peak = safe_float_or_none(p.groupby("trade_date")["limit_weight"].sum().max())
        event["tail_risk_limit_down_weight_peak"] = limit_peak
        by_backtest[backtest_id] = event
    enriched = []
    for row in rows:
        item = dict(row)
        item["tail_risk_profile_id"] = item.get("tail_risk_profile_id") or "diagnostic_only"
        event = by_backtest.get(row.get("backtest_id"))
        if event:
            item.update(event)
        report_uri = item.get("report_uri")
        if report_uri and str(report_uri).startswith("gs://"):
            item["tail_risk_uri"] = f"{str(report_uri).rstrip('/')}/tail_risk"
        enriched.append(item)
    return enriched


def build_search_tail_risk_artifacts(
    client: bigquery.Client,
    search_id: str,
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    run_ids = [str(row.get("run_id")) for row in rows if row.get("run_id")]
    if len(run_ids) < 2:
        return [], []
    start_dates = [str(row.get("start_date")) for row in rows if row.get("start_date")]
    end_dates = [str(row.get("end_date")) for row in rows if row.get("end_date")]
    if not start_dates or not end_dates:
        return [], []
    candidate_by_run = {str(row.get("run_id")): row.get("candidate_id") for row in rows if row.get("run_id")}
    start_date = min(start_dates)
    end_date = max(end_dates)
    target_sql = """
    SELECT
      pt.run_id,
      pt.rebalance_date AS signal_date,
      pt.sec_code,
      st.sec_name
    FROM `data-aquarium.ashare_ads.ads_portfolio_target_daily` AS pt
    LEFT JOIN `data-aquarium.ashare_dim.dim_stock` AS st
      ON st.sec_code = pt.sec_code
    WHERE pt.run_id IN UNNEST(@run_ids)
      AND pt.rebalance_date BETWEEN @start_date AND @end_date
    """
    params = [
        bigquery.ArrayQueryParameter("run_ids", "STRING", run_ids),
        bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
        bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
    ]
    targets = client.query(
        target_sql,
        job_config=bigquery.QueryJobConfig(query_parameters=params),
    ).to_dataframe(create_bqstorage_client=False)
    if targets.empty:
        return [], []
    targets["signal_date"] = pd.to_datetime(targets["signal_date"]).dt.date
    overlap_rows: list[dict[str, Any]] = []
    common_rows: list[dict[str, Any]] = []
    for signal_date, group in targets.groupby("signal_date"):
        selected_by_run = {
            run_id: set(run_group["sec_code"].dropna().astype(str))
            for run_id, run_group in group.groupby("run_id")
        }
        for left_run, right_run in itertools.combinations(sorted(selected_by_run), 2):
            left_set = selected_by_run.get(left_run, set())
            right_set = selected_by_run.get(right_run, set())
            overlap_rows.append({
                "search_id": search_id,
                "signal_date": str(signal_date),
                "left_run_id": left_run,
                "right_run_id": right_run,
                "left_candidate_id": candidate_by_run.get(left_run),
                "right_candidate_id": candidate_by_run.get(right_run),
                "left_selected_count": len(left_set),
                "right_selected_count": len(right_set),
                "overlap_count": len(left_set & right_set),
            })
        common_threshold = 3
        common = (
            group.groupby(["signal_date", "sec_code", "sec_name"], dropna=False)
            .agg(run_ids=("run_id", lambda values: sorted(set(map(str, values)))))
            .reset_index()
        )
        common["selected_run_count"] = common["run_ids"].map(len)
        common = common[common["selected_run_count"] >= common_threshold]
        for _, item in common.iterrows():
            run_list = item["run_ids"]
            common_rows.append({
                "search_id": search_id,
                "signal_date": str(signal_date),
                "sec_code": item.get("sec_code"),
                "sec_name": item.get("sec_name"),
                "selected_run_count": int(item.get("selected_run_count") or 0),
                "run_ids": ";".join(run_list),
                "candidate_ids": ";".join(str(candidate_by_run.get(run_id) or "") for run_id in run_list),
                "window_cumulative_contribution": None,
            })
    common_rows = attach_common_crash_contribution(client, rows, common_rows)
    return overlap_rows, common_rows


def attach_common_crash_contribution(
    client: bigquery.Client,
    rows: list[dict[str, Any]],
    common_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not common_rows:
        return common_rows
    sec_codes = sorted({str(row["sec_code"]) for row in common_rows if row.get("sec_code")})
    window_by_backtest = {
        str(row.get("backtest_id")): {
            "run_id": row.get("run_id"),
            "peak": row.get("tail_risk_peak_date"),
            "trough": row.get("tail_risk_trough_date"),
        }
        for row in rows
        if row.get("backtest_id") and row.get("tail_risk_peak_date") and row.get("tail_risk_trough_date")
    }
    if not sec_codes or not window_by_backtest:
        return common_rows
    start_date = min(str(item["peak"]) for item in window_by_backtest.values())
    end_date = max(str(item["trough"]) for item in window_by_backtest.values())
    pos_sql = """
    SELECT
      pos.backtest_id,
      pos.trade_date,
      pos.sec_code,
      pos.weight,
      px.ret_1d
    FROM `data-aquarium.ashare_ads.ads_backtest_position_daily` AS pos
    LEFT JOIN `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS px
      ON px.sec_code = pos.sec_code
     AND px.trade_date = pos.trade_date
     AND px.trade_date BETWEEN @start_date AND @end_date
    WHERE pos.backtest_id IN UNNEST(@backtest_ids)
      AND pos.sec_code IN UNNEST(@sec_codes)
      AND pos.trade_date BETWEEN @start_date AND @end_date
    """
    params = [
        bigquery.ArrayQueryParameter("backtest_ids", "STRING", list(window_by_backtest)),
        bigquery.ArrayQueryParameter("sec_codes", "STRING", sec_codes),
        bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
        bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
    ]
    pos = client.query(
        pos_sql,
        job_config=bigquery.QueryJobConfig(query_parameters=params),
    ).to_dataframe(create_bqstorage_client=False)
    if pos.empty:
        return common_rows
    pos["trade_date"] = pd.to_datetime(pos["trade_date"]).dt.date
    pos["weight"] = pd.to_numeric(pos["weight"], errors="coerce").fillna(0.0)
    pos["ret_1d"] = pd.to_numeric(pos["ret_1d"], errors="coerce").fillna(0.0)
    contribution_by_run_sec: dict[tuple[str, str], float] = {}
    run_by_backtest = {backtest_id: item["run_id"] for backtest_id, item in window_by_backtest.items()}
    for backtest_id, window in window_by_backtest.items():
        peak = pd.Timestamp(window["peak"]).date()
        trough = pd.Timestamp(window["trough"]).date()
        chunk = pos[
            (pos["backtest_id"] == backtest_id)
            & (pos["trade_date"] >= peak)
            & (pos["trade_date"] <= trough)
        ].copy()
        if chunk.empty:
            continue
        chunk["approx_contribution"] = chunk["weight"] * chunk["ret_1d"]
        run_id = str(run_by_backtest.get(backtest_id))
        for sec_code, value in chunk.groupby("sec_code")["approx_contribution"].sum().items():
            contribution_by_run_sec[(run_id, str(sec_code))] = float(value)
    enriched = []
    for row in common_rows:
        item = dict(row)
        total = 0.0
        has_value = False
        for run_id in str(item.get("run_ids") or "").split(";"):
            value = contribution_by_run_sec.get((run_id, str(item.get("sec_code"))))
            if value is not None:
                total += value
                has_value = True
        item["window_cumulative_contribution"] = safe_float_or_none(total) if has_value else None
        enriched.append(item)
    return enriched


def compute_tail_risk_event(nav: pd.DataFrame) -> dict[str, Any] | None:
    nav = nav.sort_values("trade_date").reset_index(drop=True).copy()
    if nav.empty:
        return None
    nav["run_max"] = pd.to_numeric(nav["nav"], errors="coerce").cummax()
    nav["drawdown"] = pd.to_numeric(nav["nav"], errors="coerce") / nav["run_max"] - 1.0
    trough_idx = nav["drawdown"].idxmin()
    if pd.isna(trough_idx):
        return None
    trough = nav.loc[trough_idx]
    peak_nav = trough["run_max"]
    peak_rows = nav[(nav.index <= trough_idx) & (abs(nav["nav"] - peak_nav) <= 1e-10)]
    peak = peak_rows.iloc[0] if not peak_rows.empty else nav.iloc[0]
    loss_window = nav[(nav["trade_date"] > peak["trade_date"]) & (nav["trade_date"] <= trough["trade_date"])]
    if loss_window.empty:
        loss_window = nav[(nav["trade_date"] >= peak["trade_date"]) & (nav["trade_date"] <= trough["trade_date"])]
    benchmark_return = compound_return(loss_window["benchmark_return"])
    drawdown = safe_float_or_none(trough["drawdown"])
    return {
        "tail_risk_peak_date": str(peak["trade_date"]),
        "tail_risk_trough_date": str(trough["trade_date"]),
        "tail_risk_drawdown_pct": drawdown,
        "tail_risk_benchmark_return": benchmark_return,
        "tail_risk_excess_return": None if drawdown is None or benchmark_return is None else drawdown - benchmark_return,
    }


def compound_return(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    values = values[values > -1.0]
    if values.empty:
        return 0.0
    return safe_float_or_none(np.prod(1.0 + values) - 1.0)


def enrich_v3_acceptance_rows(
    client: bigquery.Client,
    config,
    search_exp: Experiment,
    rows: list[dict[str, Any]],
    contract: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not rows:
        return rows, []
    args = argparse.Namespace(project=config.project, strategy_id=config.strategy_id)
    apply_v3_contract_defaults(args, contract)
    apply_live_v3_windows(args, search_exp, rows)
    backtest_ids = [str(row.get("backtest_id")) for row in rows if row.get("backtest_id")]
    if not backtest_ids:
        return [with_missing_v3_metrics(row, "backtest_id=missing") for row in rows], []

    nav_frame = fetch_v3_nav_rows(client, args, backtest_ids)
    nav_map = split_v3_nav_by_backtest(nav_frame)
    benchmark_meta = v3_comparison_benchmarks(contract)
    benchmark_codes = [row["sec_code"] for row in benchmark_meta]
    benchmark_frame = fetch_v3_benchmark_rows(client, args, benchmark_codes)
    benchmark_price_map = split_v3_prices_by_benchmark(benchmark_frame)
    ensure_v3_benchmark_coverage(contract, nav_map, benchmark_price_map, benchmark_codes)

    enriched_rows: list[dict[str, Any]] = []
    benchmark_rows: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        backtest_id = item.get("backtest_id")
        nav_df = nav_map.get(str(backtest_id))
        if nav_df is None:
            enriched_rows.append(with_missing_v3_metrics(item, "nav_rows=missing"))
            continue
        candidate_summary, per_benchmark = evaluate_v3_candidate(
            build_v3_candidate_record(item),
            nav_df,
            benchmark_price_map,
            benchmark_meta,
            contract,
            args,
        )
        apply_v3_candidate_summary(item, candidate_summary, per_benchmark)
        enriched_rows.append(item)
        benchmark_rows.extend(sanitize_v3_benchmark_row(row) for row in per_benchmark)
    return enriched_rows, benchmark_rows


def apply_live_v3_windows(
    args: argparse.Namespace,
    search_exp: Experiment,
    rows: list[dict[str, Any]],
) -> None:
    backtest_start_dates = [value for value in (parse_optional_date(row.get("start_date")) for row in rows) if value]
    backtest_end_dates = [value for value in (parse_optional_date(row.get("end_date")) for row in rows) if value]
    if backtest_start_dates:
        args.full_start_date = min(backtest_start_dates)
    else:
        args.full_start_date = parse_optional_date(search_exp.predict_start) or args.full_start_date
    if backtest_end_dates:
        args.full_end_date = max(backtest_end_dates)
    else:
        args.full_end_date = parse_optional_date(search_exp.predict_end) or args.full_end_date

    args.final_holdout_start_date = (
        parse_optional_date(search_exp.final_holdout_start)
        or args.final_holdout_start_date
    )
    args.final_holdout_end_date = (
        parse_optional_date(search_exp.final_holdout_end)
        or args.final_holdout_end_date
    )
    if args.full_start_date is None or args.full_end_date is None:
        raise ValueError("v3 live acceptance requires backtest or manifest full-period dates")
    if args.full_start_date > args.full_end_date:
        raise ValueError(f"invalid v3 live full-period window: {args.full_start_date} > {args.full_end_date}")
    if args.final_holdout_start_date and args.final_holdout_end_date and args.final_holdout_start_date > args.final_holdout_end_date:
        raise ValueError(
            f"invalid v3 live final-holdout window: {args.final_holdout_start_date} > {args.final_holdout_end_date}"
        )


def build_v3_candidate_record(row: dict[str, Any]) -> dict[str, Any]:
    record = dict(row)
    for key in [
        "cv_confirmation_status",
        "valid_signal_status",
        "score_orientation",
        "cv_rank_ic_mean",
        "cv_top_minus_bottom_fwd_ret_mean",
        "cv_fold_count",
        "valid_top_minus_bottom_fwd_ret_mean",
        "test_rank_ic_mean",
        "test_top_minus_bottom_fwd_ret_mean",
        "source_run_id",
        "model_family",
        "model_backend",
        "search_id",
        "run_id",
        "model_id",
        "backtest_id",
        "shortlist_rank_valid_only",
    ]:
        record[key] = row.get(key)
    record["effective_valid_rank_ic_mean"] = _first_present(
        row.get("oriented_valid_rank_ic_mean"),
        row.get("valid_rank_ic_mean"),
    )
    record["primary_diagnosis"] = _first_present(
        row.get("primary_diagnosis"),
        row.get("model_diagnosis_primary_diagnosis"),
    )
    record["sample_filter_risk"] = row.get("sample_filter_risk")
    record.setdefault("metrics_json", None)
    return record


def parse_optional_date(value: Any) -> Any:
    if value in (None, ""):
        return None
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def apply_v3_candidate_summary(
    row: dict[str, Any],
    summary: dict[str, Any],
    benchmark_rows: list[dict[str, Any]],
) -> None:
    reasons = summary.get("v3_acceptance_reasons") or []
    passed_codes = summary.get("passed_benchmark_sec_codes") or []
    row.update({
        "acceptance_contract_version": summary.get("acceptance_contract_version"),
        "acceptance_contract_sha256": summary.get("acceptance_contract_sha256"),
        "acceptance_gate_version": "strategy1_acceptance_gate_v3",
        "v3_acceptance_status": summary.get("v3_acceptance_status"),
        "v3_acceptance_reasons": ";".join(str(item) for item in reasons),
        "v3_strategy_total_return": safe_float_or_none(summary.get("strategy_total_return")),
        "v3_strategy_compound_annualized_return": safe_float_or_none(summary.get("strategy_compound_annualized_return")),
        "v3_annualized_volatility": safe_float_or_none(summary.get("annualized_volatility")),
        "v3_sharpe_ratio": safe_float_or_none(summary.get("sharpe_ratio")),
        "v3_strategy_max_drawdown": safe_float_or_none(summary.get("max_drawdown")),
        "v3_max_drawdown_peak_date": summary.get("max_drawdown_peak_date"),
        "v3_max_drawdown_trough_date": summary.get("max_drawdown_trough_date"),
        "v3_calmar_ratio": safe_float_or_none(summary.get("calmar_ratio")),
        "v3_final_holdout_trading_day_count": summary.get("final_holdout_trading_day_count"),
        "v3_final_holdout_gate_status": summary.get("final_holdout_gate_status"),
        "v3_passed_benchmark_sec_codes": ";".join(str(item) for item in passed_codes),
        "v3_passed_benchmark_count": len(passed_codes),
        "v3_relative_gate_evaluated_benchmark_count": len(benchmark_rows),
    })


def with_missing_v3_metrics(row: dict[str, Any], reason: str) -> dict[str, Any]:
    item = dict(row)
    item.update({
        "v3_acceptance_status": "rejected",
        "v3_acceptance_reasons": reason,
        "v3_passed_benchmark_count": 0,
        "v3_relative_gate_evaluated_benchmark_count": 0,
    })
    return item


def sanitize_v3_benchmark_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: sanitize_json_scalar(value) for key, value in row.items()}


def sanitize_json_scalar(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return ";".join(str(item) for item in value)
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, np.floating):
        float_value = float(value)
        return float_value if math.isfinite(float_value) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        try:
            if pd.isna(value):
                continue
        except Exception:
            pass
        return value
    return None


def safe_int_or_none(value: Any) -> int | None:
    try:
        if value is None or pd.isna(value):
            return None
    except Exception:
        if value is None:
            return None
    try:
        return int(value)
    except Exception:
        return None


def apply_native_acceptance_to_ads(
    client: bigquery.Client,
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    contract: dict[str, Any],
) -> None:
    for row in rows:
        row["acceptance_contract_version"] = row.get("acceptance_contract_version") or contract_version(contract)
        row["final_holdout_status"] = derive_final_holdout_status(row, contract)
        status, reason, derived = decide_contract_acceptance(row, contract)
        derived["acceptance_contract_version"] = (
            derived.get("acceptance_contract_version")
            or row["acceptance_contract_version"]
        )
        legacy_risk_overlay_enabled = contract_version(contract) != "model_acceptance_contract_v3"
        risk_target = risk_feature_max_drawdown_target(contract)
        if legacy_risk_overlay_enabled and row.get("feature_set_id") == PV_FIN_RISK_FEATURE_SET_ID and status == "accepted":
            max_drawdown = safe_float_or_none(row.get("max_drawdown"))
            if max_drawdown is None or max_drawdown < risk_target:
                status = "needs_more_evidence"
                reason = append_reason(reason, "risk_max_drawdown_target_not_met")
        derived["risk_feature_acceptance_overlay"] = (
            "max_drawdown_target_checked"
            if legacy_risk_overlay_enabled and row.get("feature_set_id") == PV_FIN_RISK_FEATURE_SET_ID
            else None
        )
        derived["risk_feature_max_drawdown_target"] = (
            risk_target
            if legacy_risk_overlay_enabled and row.get("feature_set_id") == PV_FIN_RISK_FEATURE_SET_ID
            else None
        )
        patch_native_acceptance(client, row, status, reason, derived)
        row["native_acceptance_status"] = status
        row["native_acceptance_reason"] = reason
        row.update(derived)


def append_reason(reason: str, extra: str) -> str:
    parts = [item for item in str(reason or "").split(";") if item]
    if extra not in parts:
        parts.append(extra)
    return ";".join(parts)


def patch_native_acceptance(
    client: bigquery.Client,
    row: dict[str, Any],
    status: str,
    reason: str,
    derived: dict[str, Any],
) -> None:
    params = [
        bigquery.ScalarQueryParameter("run_id", "STRING", row["run_id"]),
        bigquery.ScalarQueryParameter("model_id", "STRING", row.get("model_id")),
        bigquery.ScalarQueryParameter("backtest_id", "STRING", row.get("backtest_id")),
        bigquery.ScalarQueryParameter("status", "STRING", status),
        bigquery.ScalarQueryParameter("reason", "STRING", reason),
        bigquery.ScalarQueryParameter("acceptance_contract_version", "STRING", derived.get("acceptance_contract_version")),
        bigquery.ScalarQueryParameter("acceptance_gate_version", "STRING", derived.get("acceptance_gate_version")),
        bigquery.ScalarQueryParameter("acceptance_contract_sha256", "STRING", derived.get("acceptance_contract_sha256")),
        bigquery.ScalarQueryParameter("primary_benchmark_sec_code", "STRING", derived.get("primary_benchmark_sec_code")),
        bigquery.ScalarQueryParameter("holdout_watch_flag", "BOOL", bool(derived.get("holdout_watch_flag"))),
        bigquery.ScalarQueryParameter("final_holdout_status", "STRING", row.get("final_holdout_status")),
        bigquery.ScalarQueryParameter("risk_feature_acceptance_overlay", "STRING", derived.get("risk_feature_acceptance_overlay")),
        bigquery.ScalarQueryParameter(
            "risk_feature_max_drawdown_target",
            "FLOAT64",
            safe_float_or_none(derived.get("risk_feature_max_drawdown_target")),
        ),
        bigquery.ScalarQueryParameter(
            "unmatched_acceptance_state_reasons",
            "STRING",
            ";".join(derived.get("unmatched_acceptance_state_reasons") or []),
        ),
        bigquery.ScalarQueryParameter("candidate_id", "STRING", row.get("candidate_id")),
        bigquery.ScalarQueryParameter("shortlist_rank", "INT64", row.get("shortlist_rank_valid_only")),
        bigquery.ScalarQueryParameter("test_rank_ic_mean", "FLOAT64", safe_float_or_none(row.get("test_rank_ic_mean"))),
        bigquery.ScalarQueryParameter("test_top_minus_bottom", "FLOAT64", safe_float_or_none(row.get("test_top_minus_bottom_fwd_ret_mean"))),
        bigquery.ScalarQueryParameter("test_year_total_return", "FLOAT64", safe_float_or_none(row.get("test_year_total_return"))),
        bigquery.ScalarQueryParameter("test_year_excess_return", "FLOAT64", safe_float_or_none(row.get("test_year_excess_return"))),
        bigquery.ScalarQueryParameter("final_holdout_trading_days", "INT64", row.get("final_holdout_trading_days")),
        bigquery.ScalarQueryParameter("final_holdout_total_return", "FLOAT64", safe_float_or_none(row.get("final_holdout_total_return"))),
        bigquery.ScalarQueryParameter("final_holdout_excess_return", "FLOAT64", safe_float_or_none(row.get("final_holdout_excess_return"))),
        bigquery.ScalarQueryParameter("v3_acceptance_status", "STRING", derived.get("v3_acceptance_status")),
        bigquery.ScalarQueryParameter("v3_acceptance_reasons", "STRING", derived.get("v3_acceptance_reasons")),
        bigquery.ScalarQueryParameter(
            "v3_strategy_compound_annualized_return",
            "FLOAT64",
            safe_float_or_none(derived.get("v3_strategy_compound_annualized_return")),
        ),
        bigquery.ScalarQueryParameter("v3_annualized_volatility", "FLOAT64", safe_float_or_none(derived.get("v3_annualized_volatility"))),
        bigquery.ScalarQueryParameter("v3_sharpe_ratio", "FLOAT64", safe_float_or_none(derived.get("v3_sharpe_ratio"))),
        bigquery.ScalarQueryParameter("v3_calmar_ratio", "FLOAT64", safe_float_or_none(derived.get("v3_calmar_ratio"))),
        bigquery.ScalarQueryParameter("v3_strategy_max_drawdown", "FLOAT64", safe_float_or_none(derived.get("v3_strategy_max_drawdown"))),
        bigquery.ScalarQueryParameter("v3_max_drawdown_peak_date", "STRING", derived.get("v3_max_drawdown_peak_date")),
        bigquery.ScalarQueryParameter("v3_max_drawdown_trough_date", "STRING", derived.get("v3_max_drawdown_trough_date")),
        bigquery.ScalarQueryParameter(
            "v3_final_holdout_trading_day_count",
            "INT64",
            safe_int_or_none(derived.get("v3_final_holdout_trading_day_count")),
        ),
        bigquery.ScalarQueryParameter("v3_final_holdout_gate_status", "STRING", derived.get("v3_final_holdout_gate_status")),
        bigquery.ScalarQueryParameter("v3_passed_benchmark_sec_codes", "STRING", derived.get("v3_passed_benchmark_sec_codes")),
        bigquery.ScalarQueryParameter("v3_passed_benchmark_count", "INT64", safe_int_or_none(derived.get("v3_passed_benchmark_count"))),
        bigquery.ScalarQueryParameter(
            "v3_relative_gate_evaluated_benchmark_count",
            "INT64",
            safe_int_or_none(derived.get("v3_relative_gate_evaluated_benchmark_count")),
        ),
    ]
    client.query(
        """
        UPDATE `data-aquarium.ashare_ads.ads_model_registry` AS reg
        SET reg.metrics_json = TO_JSON_STRING(JSON_SET(
          PARSE_JSON(COALESCE(reg.metrics_json, '{}'), wide_number_mode => 'round'),
          '$.native_acceptance_status', @status,
          '$.native_acceptance_reason', @reason,
          '$.acceptance_contract_version', @acceptance_contract_version,
          '$.acceptance_gate_version', @acceptance_gate_version,
          '$.acceptance_contract_sha256', @acceptance_contract_sha256,
          '$.primary_benchmark_sec_code', @primary_benchmark_sec_code,
          '$.holdout_watch_flag', @holdout_watch_flag,
          '$.final_holdout_status', @final_holdout_status,
          '$.risk_feature_acceptance_overlay', @risk_feature_acceptance_overlay,
          '$.risk_feature_max_drawdown_target', @risk_feature_max_drawdown_target,
          '$.unmatched_acceptance_state_reasons', @unmatched_acceptance_state_reasons,
          '$.test_rank_ic_mean', @test_rank_ic_mean,
          '$.test_top_minus_bottom_fwd_ret_mean', @test_top_minus_bottom,
          '$.test_year_total_return', @test_year_total_return,
          '$.test_year_excess_return', @test_year_excess_return,
          '$.final_holdout_trading_days', @final_holdout_trading_days,
          '$.final_holdout_total_return', @final_holdout_total_return,
          '$.final_holdout_excess_return', @final_holdout_excess_return,
          '$.v3_acceptance_status', @v3_acceptance_status,
          '$.v3_acceptance_reasons', @v3_acceptance_reasons,
          '$.v3_strategy_compound_annualized_return', @v3_strategy_compound_annualized_return,
          '$.v3_annualized_volatility', @v3_annualized_volatility,
          '$.v3_sharpe_ratio', @v3_sharpe_ratio,
          '$.v3_calmar_ratio', @v3_calmar_ratio,
          '$.v3_strategy_max_drawdown', @v3_strategy_max_drawdown,
          '$.v3_max_drawdown_peak_date', @v3_max_drawdown_peak_date,
          '$.v3_max_drawdown_trough_date', @v3_max_drawdown_trough_date,
          '$.v3_final_holdout_trading_day_count', @v3_final_holdout_trading_day_count,
          '$.v3_final_holdout_gate_status', @v3_final_holdout_gate_status,
          '$.v3_passed_benchmark_sec_codes', @v3_passed_benchmark_sec_codes,
          '$.v3_passed_benchmark_count', @v3_passed_benchmark_count,
          '$.v3_relative_gate_evaluated_benchmark_count', @v3_relative_gate_evaluated_benchmark_count
        ))
        WHERE reg.model_id = @model_id
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
          '$.acceptance_gate_version', @acceptance_gate_version,
          '$.acceptance_contract_sha256', @acceptance_contract_sha256,
          '$.primary_benchmark_sec_code', @primary_benchmark_sec_code,
          '$.holdout_watch_flag', @holdout_watch_flag,
          '$.final_holdout_status', @final_holdout_status,
          '$.risk_feature_acceptance_overlay', @risk_feature_acceptance_overlay,
          '$.risk_feature_max_drawdown_target', @risk_feature_max_drawdown_target,
          '$.unmatched_acceptance_state_reasons', @unmatched_acceptance_state_reasons,
          '$.test_rank_ic_mean', @test_rank_ic_mean,
          '$.test_top_minus_bottom_fwd_ret_mean', @test_top_minus_bottom,
          '$.test_year_total_return', @test_year_total_return,
          '$.test_year_excess_return', @test_year_excess_return,
          '$.final_holdout_trading_days', @final_holdout_trading_days,
          '$.final_holdout_total_return', @final_holdout_total_return,
          '$.final_holdout_excess_return', @final_holdout_excess_return,
          '$.v3_acceptance_status', @v3_acceptance_status,
          '$.v3_acceptance_reasons', @v3_acceptance_reasons,
          '$.v3_strategy_compound_annualized_return', @v3_strategy_compound_annualized_return,
          '$.v3_annualized_volatility', @v3_annualized_volatility,
          '$.v3_sharpe_ratio', @v3_sharpe_ratio,
          '$.v3_calmar_ratio', @v3_calmar_ratio,
          '$.v3_strategy_max_drawdown', @v3_strategy_max_drawdown,
          '$.v3_max_drawdown_peak_date', @v3_max_drawdown_peak_date,
          '$.v3_max_drawdown_trough_date', @v3_max_drawdown_trough_date,
          '$.v3_final_holdout_trading_day_count', @v3_final_holdout_trading_day_count,
          '$.v3_final_holdout_gate_status', @v3_final_holdout_gate_status,
          '$.v3_passed_benchmark_sec_codes', @v3_passed_benchmark_sec_codes,
          '$.v3_passed_benchmark_count', @v3_passed_benchmark_count,
          '$.v3_relative_gate_evaluated_benchmark_count', @v3_relative_gate_evaluated_benchmark_count
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
