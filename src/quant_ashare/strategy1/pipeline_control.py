#!/usr/bin/env python3
"""Cloud Run Job orchestrator for Strategy 1 experiments."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from .runner_version import __version__
from .config import (
    add_common_args,
    apply_cli_overrides,
    dump_resolved_manifest,
    effective_candidate_parallelism,
    filter_experiments,
    experiment_to_b64,
    load_manifest,
    load_runner_config,
    manifest_hash,
    resolve_parallel_count,
)
from .bq_io import join_gs_uri
from quant_ashare.strategy1.dataset_roles import output_dataset_role_cli_args
from .state import (
    GcsLeaseLock,
    LockConfig,
    OrchestratorStatusTable,
    StepStateSpec,
    build_lock_key,
    cancel_cloud_run_execution,
    cloud_run_execution_state,
    describe_cloud_run_execution,
    experiment_params_json,
    extract_cloud_run_execution_id,
    scheduler_instance_id,
    status_table_ref,
)
from .task_fanout import default_matrix_id, matrix_artifact_uri


LOGGER = logging.getLogger("strategy1_cloudrun.orchestrator")


def main() -> int:
    args = parse_args()
    config = apply_cli_overrides(load_runner_config(args.config), args)
    if args.heartbeat_interval_seconds is None:
        args.heartbeat_interval_seconds = config.heartbeat_interval_seconds
    _, experiments = load_manifest(args.manifest)
    selected = filter_experiments(
        experiments,
        stage_id=args.stage_id,
        experiment_id=args.experiment_id,
        include_blocked=args.include_blocked,
    )
    resolved_parallel = resolve_parallel_count(len(selected), args.max_parallel_experiments)
    manifest_hash_value = manifest_hash(args.manifest)
    scheduler_id = args.scheduler_instance_id or scheduler_instance_id()
    tmpdir = Path(tempfile.mkdtemp(prefix="strategy1-cloudrun-"))
    resolved_manifest = tmpdir / "manifest_resolved.json"
    dump_resolved_manifest(
        resolved_manifest,
        manifest_path=args.manifest,
        manifest_hash_value=manifest_hash_value,
        config=config,
        experiments=selected,
        resolved_parallel=resolved_parallel,
    )
    plan = {
        "entrypoint": "experiment_orchestrator",
        "runner_version": __version__,
        "project": config.project,
        "region": config.region,
        "execution_backend": config.execution_backend,
        "output_dataset_role": config.output_dataset_role,
        "manifest": args.manifest,
        "manifest_hash": manifest_hash_value,
        "selected_experiment_count": len(selected),
        "max_parallel_experiments_arg": args.max_parallel_experiments,
        "resolved_max_parallel_experiments": resolved_parallel,
        "resolved_manifest": str(resolved_manifest),
        "continue_on_error": args.continue_on_error,
        "resume": args.resume,
        "resume_from_step": args.resume_from_step,
        "scheduler_instance_id": scheduler_id,
        "status_table": status_table_ref(config.project, config.output_dataset_role).strip("`"),
        "lock_bucket": args.lock_bucket or config.lock_bucket,
        "lock_prefix": args.lock_prefix or config.lock_prefix,
        "heartbeat_interval_seconds": args.heartbeat_interval_seconds,
        "experiments": [exp.to_params() for exp in selected],
        "commands": [[step.command for step in build_chain_steps(config, exp, args)] for exp in selected],
        "state_steps": [[_step_plan(step) for step in build_chain_steps(config, exp, args)] for exp in selected],
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    if not selected:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    max_workers = max(1, resolved_parallel)
    lock_config = LockConfig(
        project=config.project,
        region=config.region,
        bucket=args.lock_bucket or config.lock_bucket,
        prefix=args.lock_prefix or config.lock_prefix,
        ttl_minutes=args.lock_ttl_minutes or config.lock_ttl_minutes,
        dry_run=False,
    )
    results = []
    stop_submitting = False
    queued = list(selected)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures: dict[concurrent.futures.Future, object] = {}
        while queued and len(futures) < max_workers:
            exp = queued.pop(0)
            futures[
                executor.submit(
                    run_chain,
                    config,
                    exp,
                    build_chain_steps(config, exp, args),
                    manifest_hash_value,
                    scheduler_id,
                    lock_config,
                    args,
                )
            ] = exp
        while futures:
            done, _ = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                exp = futures.pop(future)
                try:
                    result = future.result()
                    result["experiment_id"] = exp.experiment_id
                    results.append(result)
                except Exception as exc:
                    results.append({
                        "status": "failed",
                        "experiment_id": exp.experiment_id,
                        "error": str(exc)[-8000:],
                    })
                    if not args.continue_on_error:
                        stop_submitting = True
            while queued and not stop_submitting and len(futures) < max_workers:
                exp = queued.pop(0)
                futures[
                    executor.submit(
                        run_chain,
                        config,
                        exp,
                        build_chain_steps(config, exp, args),
                        manifest_hash_value,
                        scheduler_id,
                        lock_config,
                        args,
                    )
                ] = exp
        for exp in queued:
            results.append({"status": "skipped_due_to_prior_failure", "experiment_id": exp.experiment_id})
    failure_count = sum(1 for item in results if item["status"] == "failed")
    skipped_count = sum(1 for item in results if item["status"] == "skipped_due_to_prior_failure")
    status = "succeeded" if failure_count == 0 and skipped_count == 0 else "failed"
    print(json.dumps({
        "status": status,
        "failure_count": failure_count,
        "skipped_count": skipped_count,
        "results": results,
    }, ensure_ascii=False, indent=2))
    return 1 if failure_count or skipped_count else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategy 1 Cloud Run experiment orchestrator")
    add_common_args(parser)
    parser.add_argument("--stage-id", default=None)
    parser.add_argument("--experiment-id", default=None)
    parser.add_argument("--include-blocked", action="store_true")
    parser.add_argument("--max-parallel-experiments", type=int, default=0)
    parser.add_argument("--force-replace", action="store_true")
    parser.add_argument("--skip-gcs-upload", action="store_true")
    parser.add_argument("--skip-diagnosis", action="store_true")
    parser.add_argument("--skip-qa", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true", help="Run remaining queued experiments after a failure")
    parser.add_argument("--resume", action="store_true", help="Skip Cloud Run steps already marked succeeded in status table")
    parser.add_argument("--resume-from-step", default=None)
    parser.add_argument("--train-mode", choices=["train_predict", "task_fanout"], default="train_predict")
    parser.add_argument("--candidate-parallelism", type=int, default=0)
    parser.add_argument("--scheduler-instance-id", default=None)
    parser.add_argument("--lock-bucket", default=None)
    parser.add_argument("--lock-prefix", default=None)
    parser.add_argument("--lock-ttl-minutes", type=int, default=None)
    parser.add_argument("--heartbeat-interval-seconds", type=int, default=None)
    return parser.parse_args()


def build_chain_steps(config, exp, args) -> list[StepStateSpec]:
    steps = []
    common_flags = [
        f"--project={config.project}",
        f"--region={config.region}",
        f"--config={args.config}",
        f"--manifest={args.manifest}",
        *output_dataset_role_cli_args(config.output_dataset_role, equals=True),
        f"--experiment-id={exp.experiment_id}",
        f"--experiment-json={experiment_to_b64(exp)}",
    ]
    if args.force_replace:
        common_flags.append("--force-replace")
    if args.skip_gcs_upload:
        common_flags.append("--skip-gcs-upload")
    if exp.requires_retrain:
        if args.train_mode == "task_fanout":
            steps.extend(build_task_fanout_steps(config, exp, args, common_flags))
        else:
            steps.append(StepStateSpec(
                step_id="cloudrun_train_predict",
                display_name="Cloud Run sklearn train/predict",
                lock_key=build_lock_key(exp, "cloudrun_train_predict"),
                job_name=config.train_predict_job,
                command=gcloud_execute_command(
                    config.project,
                    config.region,
                    config.train_predict_job,
                    "quant_ashare.strategy1.train_predict",
                    common_flags,
                ),
            ))
    backtest_flags = list(common_flags)
    backtest_flags.extend([f"--run-id={exp.run_id}", f"--prediction-run-id={exp.prediction_run_id}", f"--backtest-id={exp.backtest_id}"])
    if args.skip_diagnosis:
        backtest_flags.append("--skip-diagnosis")
    if args.skip_qa:
        backtest_flags.append("--skip-qa")
    steps.append(StepStateSpec(
        step_id="cloudrun_backtest_report",
        display_name="Cloud Run backtest/report",
        lock_key=build_lock_key(exp, "cloudrun_backtest_report"),
        job_name=config.backtest_report_job,
        command=gcloud_execute_command(
            config.project,
            config.region,
            config.backtest_report_job,
            "quant_ashare.strategy1.backtest_report",
            backtest_flags,
        ),
    ))
    return steps


def build_task_fanout_steps(config, exp, args, common_flags: list[str]) -> list[StepStateSpec]:
    matrix_id = default_matrix_id(config, exp)
    matrix_uri = matrix_artifact_uri(config, exp, matrix_id)
    work_units_uri = join_gs_uri(matrix_uri, "work_units.json")
    work_unit_count = len(config.candidate_grid)
    candidate_parallelism_arg = effective_candidate_parallelism(config, args.candidate_parallelism)
    candidate_parallelism = resolve_candidate_parallel_count(work_unit_count, candidate_parallelism_arg)
    cli_limits_parallelism = getattr(
        args,
        "candidate_parallelism_from_cli",
        args.candidate_parallelism not in (None, 0),
    )
    batch_size_limit = candidate_parallelism if cli_limits_parallelism else work_unit_count
    # prepare_matrix only materializes frozen matrix artifacts; ADS replacement is handled by reducer/backtest steps.
    prepare_common_flags = [flag for flag in common_flags if flag != "--force-replace"]
    prepare_flags = [
        *prepare_common_flags,
        f"--matrix-id={matrix_id}",
        f"--matrix-uri={matrix_uri}",
        f"--candidate-parallelism={candidate_parallelism_arg}",
    ]
    steps = [
        StepStateSpec(
            step_id="cloudrun_prepare_matrix",
            display_name="Cloud Run prepare frozen matrix",
            lock_key=build_lock_key(exp, "cloudrun_prepare_matrix"),
            job_name=config.prepare_matrix_job,
            command=gcloud_execute_command(
                config.project,
                config.region,
                config.prepare_matrix_job,
                "quant_ashare.strategy1.prepare_matrix",
                prepare_flags,
            ),
        )
    ]
    for batch_index, batch_start in enumerate(range(0, work_unit_count, max(1, batch_size_limit))):
        batch_size = min(batch_size_limit, work_unit_count - batch_start)
        step_id = "cloudrun_train_candidate_fanout" if work_unit_count == batch_size else f"cloudrun_train_candidate_fanout_batch_{batch_index:03d}"
        steps.append(StepStateSpec(
            step_id=step_id,
            display_name=f"Cloud Run candidate fan-out batch {batch_index}",
            lock_key=build_lock_key(exp, step_id),
            job_name=config.train_candidate_fanout_job,
            command=gcloud_execute_command(
                config.project,
                config.region,
                config.train_candidate_fanout_job,
                "quant_ashare.strategy1.train_candidate_task",
                [
                    f"--project={config.project}",
                    f"--region={config.region}",
                    f"--config={args.config}",
                    *output_dataset_role_cli_args(config.output_dataset_role, equals=True),
                    f"--matrix-uri={matrix_uri}",
                    f"--task-index-offset={batch_start}",
                ],
                tasks=batch_size,
                env_vars={
                    "MATRIX_ID": matrix_id,
                    "MATRIX_URI": matrix_uri,
                    "WORK_UNITS_URI": work_units_uri,
                    "TASK_INDEX_OFFSET": str(batch_start),
                },
            ),
        ))
    select_flags = [
        *common_flags,
        f"--matrix-uri={matrix_uri}",
    ]
    steps.append(StepStateSpec(
        step_id="cloudrun_select_register_predict",
        display_name="Cloud Run select/register/predict",
        lock_key=build_lock_key(exp, "cloudrun_select_register_predict"),
        job_name=config.select_register_predict_job,
        command=gcloud_execute_command(
            config.project,
            config.region,
            config.select_register_predict_job,
            "quant_ashare.strategy1.select_register_predict",
            select_flags,
        ),
    ))
    return steps


def resolve_candidate_parallel_count(work_unit_count: int, candidate_parallelism: int | None) -> int:
    if work_unit_count <= 0:
        raise ValueError("candidate grid is empty")
    if candidate_parallelism is None or candidate_parallelism == 0:
        return work_unit_count
    if candidate_parallelism < 0:
        raise ValueError("--candidate-parallelism must be >= 0")
    return min(candidate_parallelism, work_unit_count)


def gcloud_execute_command(
    project: str,
    region: str,
    job_name: str,
    module: str,
    job_args: list[str],
    *,
    tasks: int | None = None,
    env_vars: dict[str, str] | None = None,
) -> list[str]:
    execution_args = ["-m", module, *job_args]
    command = [
        "gcloud", "run", "jobs", "execute", job_name,
        f"--project={project}",
        f"--region={region}",
        "--format=json",
        "--args=" + ",".join(execution_args),
    ]
    if tasks is not None:
        command.append(f"--tasks={tasks}")
    if env_vars:
        encoded = ",".join(f"{key}={value}" for key, value in sorted(env_vars.items()))
        command.append("--update-env-vars=" + encoded)
    return command


def run_chain(
    config,
    exp,
    steps: list[StepStateSpec],
    manifest_hash_value: str,
    scheduler_id: str,
    lock_config: LockConfig,
    args,
) -> dict[str, object]:
    if args.resume_from_step and args.resume_from_step not in {step.step_id for step in steps}:
        raise ValueError(f"{exp.experiment_id} has no step {args.resume_from_step}")
    status_table = OrchestratorStatusTable(
        config.project,
        config.region,
        dry_run=False,
        output_dataset_role=config.output_dataset_role,
    )
    outputs = []
    skip_until_step = args.resume_from_step
    for step in steps:
        if skip_until_step and step.step_id != skip_until_step:
            outputs.append({"step_id": step.step_id, "status": "skipped_before_resume_from_step"})
            continue
        if skip_until_step and step.step_id == skip_until_step:
            skip_until_step = None
        if args.resume and status_table.get_status(exp, step.step_id) == "succeeded":
            outputs.append({"step_id": step.step_id, "status": "skipped_succeeded"})
            continue
        outputs.append(run_locked_step(
            config=config,
            exp=exp,
            step=step,
            manifest_hash_value=manifest_hash_value,
            scheduler_id=scheduler_id,
            lock_config=lock_config,
            status_table=status_table,
            args=args,
        ))
    return {"status": "succeeded", "steps": outputs}


def run_locked_step(
    *,
    config,
    exp,
    step: StepStateSpec,
    manifest_hash_value: str,
    scheduler_id: str,
    lock_config: LockConfig,
    status_table: OrchestratorStatusTable,
    args,
) -> dict[str, object]:
    lock = GcsLeaseLock(lock_config, step.lock_key, exp, step.step_id, scheduler_id)
    params_json = experiment_params_json(
        exp,
        execution_backend=config.execution_backend,
        manifest_hash=manifest_hash_value,
        output_dataset_role=config.output_dataset_role,
    )
    if not lock.acquire():
        status_table.upsert(
            exp, step, status="cancelled", scheduler_id=scheduler_id,
            manifest_path=args.manifest, manifest_hash=manifest_hash_value,
            params_json=params_json, force_replace=args.force_replace,
            error_message="lock busy or acquire failed",
        )
        raise RuntimeError(f"{exp.experiment_id}/{step.step_id}: lock busy or acquire failed")
    heartbeat_stop = threading.Event()
    heartbeat_abort = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(
            lock,
            status_table,
            exp,
            step,
            scheduler_id,
            manifest_hash_value,
            params_json,
            args,
            heartbeat_stop,
            heartbeat_abort,
        ),
        daemon=True,
    )
    terminal_status_written = False
    def stop_heartbeat() -> None:
        heartbeat_stop.set()
        if heartbeat_thread.is_alive():
            heartbeat_thread.join()

    try:
        status_table.upsert(
            exp, step, status="running", scheduler_id=scheduler_id,
            manifest_path=args.manifest, manifest_hash=manifest_hash_value,
            params_json=params_json, force_replace=args.force_replace,
            lock=lock,
        )
        heartbeat_thread.start()
        start_proc = subprocess.run(step.command, text=True, capture_output=True)
        execution_id = extract_cloud_run_execution_id(start_proc.stdout, start_proc.stderr)
        start_result = {
            "step_id": step.step_id,
            "lock_key": step.lock_key,
            "command": step.command,
            "start_returncode": start_proc.returncode,
            "cloud_run_execution_id": execution_id,
            "stdout_tail": start_proc.stdout[-4000:],
            "stderr_tail": start_proc.stderr[-4000:],
        }
        if start_proc.returncode != 0 or not execution_id:
            stop_heartbeat()
            status_table.upsert(
                exp, step, status="failed", scheduler_id=scheduler_id,
                manifest_path=args.manifest, manifest_hash=manifest_hash_value,
                params_json=params_json, force_replace=args.force_replace,
                lock=lock, job_id=execution_id, error_message=json.dumps(start_result, ensure_ascii=False)[-8000:],
            )
            terminal_status_written = True
            raise RuntimeError(json.dumps(start_result, ensure_ascii=False))
        if not lock.record_execution(execution_id=execution_id, job_name=step.job_name):
            cancel_cloud_run_execution(config.project, config.region, execution_id)
            stop_heartbeat()
            status_table.upsert(
                exp, step, status="failed", scheduler_id=scheduler_id,
                manifest_path=args.manifest, manifest_hash=manifest_hash_value,
                params_json=params_json, force_replace=args.force_replace,
                lock=lock, job_id=execution_id, error_message="failed to record execution id in GCS lock",
            )
            terminal_status_written = True
            raise RuntimeError(f"{exp.experiment_id}/{step.step_id}: failed to record execution id in GCS lock")
        status_table.upsert(
            exp, step, status="running", scheduler_id=scheduler_id,
            manifest_path=args.manifest, manifest_hash=manifest_hash_value,
            params_json=params_json, force_replace=args.force_replace,
            lock=lock, job_id=execution_id,
        )
        execution_payload = wait_for_cloud_run_execution(
            project=config.project,
            region=config.region,
            execution_id=execution_id,
            poll_seconds=max(5, min(30, int(args.heartbeat_interval_seconds or 60))),
            abort_event=heartbeat_abort,
        )
        execution_state = cloud_run_execution_state(execution_payload)
        result = {
            "step_id": step.step_id,
            "lock_key": step.lock_key,
            "command": step.command,
            "cloud_run_execution_id": execution_id,
            "cloud_run_execution_state": execution_state,
            "start_stdout_tail": start_proc.stdout[-4000:],
            "start_stderr_tail": start_proc.stderr[-4000:],
        }
        if execution_state != "succeeded":
            stop_heartbeat()
            status_table.upsert(
                exp, step, status="failed", scheduler_id=scheduler_id,
                manifest_path=args.manifest, manifest_hash=manifest_hash_value,
                params_json=params_json, force_replace=args.force_replace,
                lock=lock, job_id=execution_id, error_message=json.dumps(result, ensure_ascii=False)[-8000:],
            )
            terminal_status_written = True
            raise RuntimeError(json.dumps(result, ensure_ascii=False))
        stop_heartbeat()
        status_table.upsert(
            exp, step, status="succeeded", scheduler_id=scheduler_id,
            manifest_path=args.manifest, manifest_hash=manifest_hash_value,
            params_json=params_json, force_replace=args.force_replace,
            lock=lock, job_id=execution_id,
        )
        terminal_status_written = True
        result["status"] = "succeeded"
        return result
    except Exception as exc:
        if not terminal_status_written:
            stop_heartbeat()
            status_table.upsert(
                exp, step, status="failed", scheduler_id=scheduler_id,
                manifest_path=args.manifest, manifest_hash=manifest_hash_value,
                params_json=params_json, force_replace=args.force_replace,
                lock=lock, error_message=str(exc)[-8000:],
            )
        raise
    finally:
        stop_heartbeat()
        lock.release()


def _heartbeat_loop(
    lock: GcsLeaseLock,
    status_table: OrchestratorStatusTable,
    exp,
    step: StepStateSpec,
    scheduler_id: str,
    manifest_hash_value: str,
    params_json: str,
    args,
    stop_event: threading.Event,
    abort_event: threading.Event,
) -> None:
    interval = max(5, int(args.heartbeat_interval_seconds or 60))
    while not stop_event.wait(interval):
        try:
            lease_expires_at = lock.heartbeat()
        except Exception as exc:
            LOGGER.warning("heartbeat loop GCS update failed: %s/%s: %s", exp.experiment_id, step.step_id, exc)
            continue
        if lease_expires_at is None:
            abort_event.set()
            return
        try:
            status_table.upsert(
                exp, step, status="running", scheduler_id=scheduler_id,
                manifest_path=args.manifest, manifest_hash=manifest_hash_value,
                params_json=params_json, force_replace=args.force_replace,
                lock=lock,
            )
        except Exception as exc:
            LOGGER.warning("heartbeat loop status upsert failed: %s/%s: %s", exp.experiment_id, step.step_id, exc)


def wait_for_cloud_run_execution(
    *,
    project: str,
    region: str,
    execution_id: str,
    poll_seconds: int,
    abort_event: threading.Event,
) -> dict[str, object] | None:
    unknown_count = 0
    while True:
        if abort_event.is_set():
            cancel_cloud_run_execution(project, region, execution_id)
            raise RuntimeError(f"{execution_id}: lost GCS lock ownership; cancelled execution")
        payload = describe_cloud_run_execution(project, region, execution_id)
        state = cloud_run_execution_state(payload)
        if state == "unknown":
            unknown_count += 1
            if unknown_count >= 5:
                raise RuntimeError(f"{execution_id}: unable to describe Cloud Run execution state")
        else:
            unknown_count = 0
        if state in {"succeeded", "failed", "cancelled"}:
            return payload
        time.sleep(poll_seconds)


def _step_plan(step: StepStateSpec) -> dict[str, object]:
    return {
        "step_id": step.step_id,
        "display_name": step.display_name,
        "lock_key": step.lock_key,
        "job_name": step.job_name,
        "command": step.command,
    }


if __name__ == "__main__":
    raise SystemExit(main())
