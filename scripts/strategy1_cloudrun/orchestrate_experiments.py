#!/usr/bin/env python3
"""Cloud Run Job orchestrator for Strategy 1 experiments."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import tempfile
from pathlib import Path

from scripts.strategy1_cloudrun import __version__
from scripts.strategy1_cloudrun.config import (
    add_common_args,
    apply_cli_overrides,
    dump_resolved_manifest,
    filter_experiments,
    experiment_to_b64,
    load_manifest,
    load_runner_config,
    manifest_hash,
    resolve_parallel_count,
)


def main() -> int:
    args = parse_args()
    config = apply_cli_overrides(load_runner_config(args.config), args)
    _, experiments = load_manifest(args.manifest)
    selected = filter_experiments(
        experiments,
        stage_id=args.stage_id,
        experiment_id=args.experiment_id,
        include_blocked=args.include_blocked,
    )
    resolved_parallel = resolve_parallel_count(len(selected), args.max_parallel_experiments)
    manifest_hash_value = manifest_hash(args.manifest)
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
        "manifest": args.manifest,
        "manifest_hash": manifest_hash_value,
        "selected_experiment_count": len(selected),
        "max_parallel_experiments_arg": args.max_parallel_experiments,
        "resolved_max_parallel_experiments": resolved_parallel,
        "resolved_manifest": str(resolved_manifest),
        "continue_on_error": args.continue_on_error,
        "experiments": [exp.to_params() for exp in selected],
        "commands": [build_chain_commands(config, exp, resolved_manifest, args) for exp in selected],
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    if not selected:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    max_workers = max(1, resolved_parallel)
    results = []
    stop_submitting = False
    queued = list(selected)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures: dict[concurrent.futures.Future, object] = {}
        while queued and len(futures) < max_workers:
            exp = queued.pop(0)
            futures[executor.submit(run_chain, build_chain_commands(config, exp, resolved_manifest, args))] = exp
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
                futures[executor.submit(run_chain, build_chain_commands(config, exp, resolved_manifest, args))] = exp
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
    parser.add_argument("--use-bq-ledger", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true", help="Run remaining queued experiments after a failure")
    return parser.parse_args()


def build_chain_commands(config, exp, resolved_manifest: Path, args) -> list[list[str]]:
    commands = []
    common_flags = [
        f"--project={config.project}",
        f"--region={config.region}",
        f"--manifest={args.manifest}",
        f"--experiment-id={exp.experiment_id}",
        f"--experiment-json={experiment_to_b64(exp)}",
    ]
    if args.force_replace:
        common_flags.append("--force-replace")
    if args.skip_gcs_upload:
        common_flags.append("--skip-gcs-upload")
    if exp.requires_retrain:
        commands.append(gcloud_execute_command(config.project, config.region, config.train_predict_job, common_flags))
    backtest_flags = list(common_flags)
    backtest_flags.extend([f"--run-id={exp.run_id}", f"--prediction-run-id={exp.prediction_run_id}", f"--backtest-id={exp.backtest_id}"])
    if args.skip_diagnosis:
        backtest_flags.append("--skip-diagnosis")
    if args.skip_qa:
        backtest_flags.append("--skip-qa")
    if args.use_bq_ledger:
        backtest_flags.append("--use-bq-ledger")
    commands.append(gcloud_execute_command(config.project, config.region, config.backtest_report_job, backtest_flags))
    return commands


def gcloud_execute_command(project: str, region: str, job_name: str, job_args: list[str]) -> list[str]:
    return [
        "gcloud", "run", "jobs", "execute", job_name,
        f"--project={project}",
        f"--region={region}",
        "--wait",
        "--args=" + ",".join(job_args),
    ]


def run_chain(commands: list[list[str]]) -> dict[str, object]:
    outputs = []
    for command in commands:
        proc = subprocess.run(command, text=True, capture_output=True)
        outputs.append({
            "command": command,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
        })
        if proc.returncode != 0:
            raise RuntimeError(json.dumps(outputs, ensure_ascii=False))
    return {"status": "succeeded", "steps": outputs}


if __name__ == "__main__":
    raise SystemExit(main())
