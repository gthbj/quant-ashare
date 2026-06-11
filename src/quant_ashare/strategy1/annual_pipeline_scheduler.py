"""Scheduler for Strategy 1 annual rolling pipeline execution.

The default mode is still dry-run only. Live execution requires both
``--execute-live`` and ``--candidate-only-smoke`` so the Phase 2 smoke path
cannot accidentally launch the full annual rolling pipeline.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import subprocess
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from google.cloud import storage

from scripts.strategy1_cloudrun import __version__
from scripts.strategy1_cloudrun.bq_io import join_gs_uri, json_dumps_strict, parse_gs_uri
from scripts.strategy1_cloudrun.config import (
    add_common_args,
    apply_cli_overrides,
    experiment_to_b64,
    load_runner_config,
)
from scripts.strategy1_cloudrun.dataset_roles import output_dataset_role_cli_args
from scripts.strategy1_cloudrun.orchestrate_annual_rolling_selection import (
    DEFAULT_AS_OF_DATE,
    DEFAULT_CANDIDATE_SET_ID,
    DEFAULT_CONFIG_PATH,
    actual_first_trading_day,
    b26_reference_plan,
    build_year_experiment,
    command_plan,
    continuous_backtest_id_for,
    final_refit_experiment,
    parse_iso_date,
    validate_config,
)
from scripts.strategy1_cloudrun.task_fanout import (
    candidate_grid_hash,
    candidate_output_uri,
    default_matrix_id,
    matrix_artifact_uri,
)
from quant_ashare.strategy1.pipeline_control import gcloud_execute_command
from scripts.strategy1_cloudrun.state import (
    cloud_run_execution_state,
    extract_cloud_run_execution_id,
)


STAGE_PANEL = "panel"
STAGE_MATRIX = "matrix"
STAGE_CANDIDATE = "candidate"
STAGE_SELECT = "select"
STAGE_REFIT_PANEL = "refit_panel"
STAGE_REFIT = "refit"
STAGE_DIAGNOSTIC_BACKTEST = "diagnostic_backtest"
STAGE_CONTINUOUS_LEDGER = "continuous_ledger"

STATUS_PLANNED = "planned"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_DEFERRED = "deferred"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "failed"

SIMULATION_MODEL_SYNCHRONOUS_WAVES = "synchronous_waves"

DEFAULT_SELECT_CPU = 4
DEFAULT_SELECT_MEMORY_GIB = 16
DEFAULT_REFIT_CPU = 8
DEFAULT_REFIT_MEMORY_GIB = 32
DEFAULT_BACKTEST_CPU = 4
DEFAULT_BACKTEST_MEMORY_GIB = 16
DEFAULT_PREPARE_CPU = 8
DEFAULT_PREPARE_MEMORY_GIB = 32
DEFAULT_CANDIDATE_CPU = 2
DEFAULT_CANDIDATE_MEMORY_GIB = 8


@dataclasses.dataclass(frozen=True)
class ResourceTokens:
    cpu: int = 0
    memory_gib: int = 0
    candidate_slots: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "cpu": self.cpu,
            "memory_gib": self.memory_gib,
            "candidate_slots": self.candidate_slots,
        }

    def add(self, other: "ResourceTokens") -> "ResourceTokens":
        return ResourceTokens(
            cpu=self.cpu + other.cpu,
            memory_gib=self.memory_gib + other.memory_gib,
            candidate_slots=self.candidate_slots + other.candidate_slots,
        )


@dataclasses.dataclass(frozen=True)
class SchedulerLimits:
    candidate_task_slots: int = 20
    cloudrun_cpu_tokens: int = 40
    cloudrun_memory_gib_tokens: int = 160
    active_fanout_executions: int = 4
    active_panel_jobs: int = 1
    active_prepare_jobs: int = 1
    active_select_jobs: int = 1
    active_backtest_jobs: int = 1

    def stage_limit(self, stage: str) -> int:
        if stage in (STAGE_PANEL, STAGE_REFIT_PANEL):
            return self.active_panel_jobs
        if stage == STAGE_MATRIX:
            return self.active_prepare_jobs
        if stage == STAGE_SELECT:
            return self.active_select_jobs
        if stage == STAGE_REFIT:
            return self.active_select_jobs
        if stage == STAGE_DIAGNOSTIC_BACKTEST:
            return self.active_backtest_jobs
        if stage == STAGE_CONTINUOUS_LEDGER:
            return 1
        if stage == STAGE_CANDIDATE:
            return self.candidate_task_slots
        raise ValueError(f"unknown stage: {stage}")

    def to_dict(self) -> dict[str, int]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class PipelineTask:
    task_id: str
    stage: str
    year: int | None
    dependencies: tuple[str, ...]
    tokens: ResourceTokens
    command: tuple[str, ...] = ()
    job_name: str | None = None
    unit_index: int | None = None
    candidate_id: str | None = None
    artifact_uri: str | None = None
    matrix_id: str | None = None
    matrix_uri: str | None = None
    diagnostic_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "stage": self.stage,
            "year": self.year,
            "unit_index": self.unit_index,
            "candidate_id": self.candidate_id,
            "dependencies": list(self.dependencies),
            "resource_tokens": self.tokens.to_dict(),
            "job_name": self.job_name,
            "command": list(self.command),
            "artifact_uri": self.artifact_uri,
            "matrix_id": self.matrix_id,
            "matrix_uri": self.matrix_uri,
            "diagnostic_only": self.diagnostic_only,
        }


@dataclasses.dataclass(frozen=True)
class SchedulerContext:
    lock_owned: bool = True
    scheduler_lock_generation: int | None = 1

    @property
    def can_submit(self) -> bool:
        return self.lock_owned and self.scheduler_lock_generation is not None


class StateGenerationMismatch(RuntimeError):
    """Raised when a generation-conditioned state update loses ownership."""


class LiveSchedulerOwnershipLost(RuntimeError):
    """Raised when the live scheduler loses GCS lease ownership."""


@dataclasses.dataclass
class InMemoryGenerationStateStore:
    """Small local model of GCS generation-conditioned state writes.

    Production state writes must use GCS object generation preconditions. This
    in-memory store is used by the dry-run scheduler and tests to keep that
    contract explicit without touching GCS.
    """

    generation: int | None = None
    payload: dict[str, Any] = dataclasses.field(default_factory=dict)

    def read(self) -> tuple[dict[str, Any] | None, int | None]:
        if self.generation is None:
            return None, None
        return json.loads(json_dumps_strict(self.payload, ensure_ascii=False)), self.generation

    def create_if_absent(self, payload: dict[str, Any]) -> int:
        if self.generation is not None:
            return self.generation
        return self.create(payload)

    def create(self, payload: dict[str, Any]) -> int:
        if self.generation is not None:
            raise StateGenerationMismatch(
                f"state object already exists at generation {self.generation}; expected create-only generation 0"
            )
        self.payload = json.loads(json_dumps_strict(payload, ensure_ascii=False))
        self.generation = 1
        return self.generation

    def update(self, payload: dict[str, Any], *, expected_generation: int) -> int:
        if self.generation != expected_generation:
            raise StateGenerationMismatch(
                f"state generation mismatch: expected {expected_generation}, current {self.generation}"
            )
        self.payload = json.loads(json_dumps_strict(payload, ensure_ascii=False))
        self.generation = (self.generation or 0) + 1
        return self.generation


class GcsGenerationStateStore:
    """GCS JSON state object with generation-conditioned writes."""

    def __init__(
        self,
        *,
        project: str,
        bucket: str,
        prefix: str,
        state_key: str,
        client: storage.Client | None = None,
    ):
        self.project = project
        self.bucket_name = bucket
        self.blob_name = f"{prefix.rstrip('/')}/{state_key}.json"
        self._client = client

    def read(self) -> tuple[dict[str, Any] | None, int | None]:
        blob = self._blob()
        try:
            blob.reload()
            generation = int(blob.generation)
            payload = json.loads(blob.download_as_bytes(if_generation_match=generation))
            return payload, generation
        except Exception as exc:
            if _is_not_found_error(exc):
                return None, None
            raise

    def create_if_absent(self, payload: dict[str, Any]) -> int:
        blob = self._blob()
        try:
            blob.upload_from_string(
                json_dumps_strict(payload, ensure_ascii=False, sort_keys=True),
                content_type="application/json",
                if_generation_match=0,
            )
            blob.reload()
            return int(blob.generation)
        except Exception as exc:
            if _is_precondition_error(exc):
                _, generation = self.read()
                if generation is None:
                    raise StateGenerationMismatch("state create raced but object is still missing") from exc
                return generation
            raise

    def update(self, payload: dict[str, Any], *, expected_generation: int) -> int:
        blob = self._blob()
        try:
            blob.upload_from_string(
                json_dumps_strict(payload, ensure_ascii=False, sort_keys=True),
                content_type="application/json",
                if_generation_match=expected_generation,
            )
            blob.reload()
            return int(blob.generation)
        except Exception as exc:
            if _is_precondition_error(exc) or _is_not_found_error(exc):
                raise StateGenerationMismatch(
                    f"state generation mismatch: expected {expected_generation}"
                ) from exc
            raise

    def _blob(self) -> storage.Blob:
        if self._client is None:
            self._client = storage.Client(project=self.project)
        return self._client.bucket(self.bucket_name).blob(self.blob_name)


class GcsSchedulerLease:
    """Lightweight annual-scheduler lease using GCS generation preconditions."""

    def __init__(
        self,
        *,
        project: str,
        bucket: str,
        prefix: str,
        lock_key: str,
        owner: str,
        ttl_minutes: int,
        client: storage.Client | None = None,
    ):
        self.project = project
        self.bucket_name = bucket
        self.blob_name = f"{prefix.rstrip('/')}/{lock_key}.lock"
        self.lock_key = lock_key
        self.owner = owner
        self.ttl_minutes = ttl_minutes
        self._client = client
        self._generation: int | None = None

    @property
    def generation(self) -> int | None:
        return self._generation

    def acquire(self) -> bool:
        now = utc_now()
        payload = {
            "lock_key": self.lock_key,
            "lock_owner": self.owner,
            "acquired_at": now.isoformat(),
            "lease_expires_at": (now + timedelta(minutes=self.ttl_minutes)).isoformat(),
        }
        blob = self._blob()
        try:
            blob.upload_from_string(
                json_dumps_strict(payload, ensure_ascii=False, sort_keys=True),
                content_type="application/json",
                if_generation_match=0,
            )
            blob.reload()
            self._generation = int(blob.generation)
            return True
        except Exception as exc:
            if _is_precondition_error(exc):
                return False
            raise

    def heartbeat(self) -> bool:
        if self._generation is None:
            return False
        blob = self._blob()
        try:
            existing = json.loads(blob.download_as_bytes(if_generation_match=self._generation))
            if existing.get("lock_owner") != self.owner:
                return False
            now = utc_now()
            existing["last_heartbeat_at"] = now.isoformat()
            existing["lease_expires_at"] = (now + timedelta(minutes=self.ttl_minutes)).isoformat()
            blob.upload_from_string(
                json_dumps_strict(existing, ensure_ascii=False, sort_keys=True),
                content_type="application/json",
                if_generation_match=self._generation,
            )
            blob.reload()
            self._generation = int(blob.generation)
            return True
        except Exception as exc:
            if _is_precondition_error(exc) or _is_not_found_error(exc):
                return False
            raise

    def release(self) -> None:
        if self._generation is None:
            return
        try:
            self._blob().delete(if_generation_match=self._generation)
        except Exception:
            pass
        finally:
            self._generation = None

    def _blob(self) -> storage.Blob:
        if self._client is None:
            self._client = storage.Client(project=self.project)
        return self._client.bucket(self.bucket_name).blob(self.blob_name)


@dataclasses.dataclass(frozen=True)
class LiveExecutionUnit:
    unit_key: str
    stage: str
    year: int
    task_ids: tuple[str, ...]
    command: tuple[str, ...]
    job_name: str
    tokens: ResourceTokens
    matrix_uri: str | None
    artifact_uris: tuple[str, ...]

    def to_state_seed(self) -> dict[str, Any]:
        return {
            "unit_key": self.unit_key,
            "stage": self.stage,
            "year": self.year,
            "task_ids": list(self.task_ids),
            "job_name": self.job_name,
            "resource_tokens": self.tokens.to_dict(),
            "matrix_uri": self.matrix_uri,
            "artifact_uris": list(self.artifact_uris),
            "status": STATUS_PLANNED,
        }


@dataclasses.dataclass(frozen=True)
class CloudRunSubmitResult:
    returncode: int
    execution_id: str | None
    stdout_tail: str = ""
    stderr_tail: str = ""


class GcloudExecutionClient:
    def submit(self, command: tuple[str, ...] | list[str]) -> CloudRunSubmitResult:
        proc = subprocess.run(list(command), text=True, capture_output=True)
        return CloudRunSubmitResult(
            returncode=proc.returncode,
            execution_id=extract_cloud_run_execution_id(proc.stdout, proc.stderr),
            stdout_tail=proc.stdout[-4000:],
            stderr_tail=proc.stderr[-4000:],
        )

    def describe(self, *, project: str, region: str, execution_id: str) -> dict[str, Any] | None:
        proc = subprocess.run(
            [
                "gcloud", "run", "jobs", "executions", "describe", execution_id,
                f"--project={project}",
                f"--region={region}",
                "--format=json",
            ],
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            return None
        try:
            return json.loads(proc.stdout)
        except Exception:
            return None


class GcsArtifactStore:
    """GCS artifact checker used by live scheduling.

    Candidate tasks are considered complete only when both the success marker
    and metrics file exist under the candidate output URI.
    """

    def __init__(self, *, project: str, client: storage.Client | None = None):
        self.project = project
        self._client = client

    def artifact_complete(self, unit: LiveExecutionUnit) -> bool:
        if not unit.artifact_uris:
            return False
        for uri in unit.artifact_uris:
            if not self._candidate_artifact_complete(uri):
                return False
        return True

    def matrix_ready(self, unit: LiveExecutionUnit) -> bool:
        if not unit.matrix_uri:
            return False
        required = ("matrix_manifest.json", "work_units.json")
        bucket_name, prefix = parse_gs_uri(unit.matrix_uri)
        if self._client is None:
            self._client = storage.Client(project=self.project)
        bucket = self._client.bucket(bucket_name)
        return all(bucket.blob(join_object_name(prefix, name)).exists() for name in required)

    def _candidate_artifact_complete(self, uri: str) -> bool:
        required = ("task_status.json", "candidate_metrics.json")
        bucket_name, prefix = parse_gs_uri(uri)
        if self._client is None:
            self._client = storage.Client(project=self.project)
        bucket = self._client.bucket(bucket_name)
        return all(bucket.blob(join_object_name(prefix, name)).exists() for name in required)


def main() -> int:
    args = parse_args()
    config = apply_cli_overrides(load_runner_config(args.config), args)
    validate_config(config, args)
    if args.heartbeat_interval_seconds is None:
        args.heartbeat_interval_seconds = config.heartbeat_interval_seconds
    if args.lock_ttl_minutes is None:
        args.lock_ttl_minutes = config.lock_ttl_minutes
    plan = build_scheduler_plan(config=config, args=args)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_dumps_strict(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.execute_live:
        result = execute_candidate_only_live_smoke(
            plan=plan,
            config=config,
            args=args,
        )
        print(json_dumps_strict(result, ensure_ascii=False, indent=2))
        return 0
    print(json_dumps_strict(plan, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0
    raise SystemExit(
        "non-dry-run annual pipeline scheduler is not implemented; "
        "run with --dry-run to inspect the DAG and resource plan"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategy 1 annual rolling pipeline scheduler")
    add_common_args(parser)
    parser.set_defaults(config=DEFAULT_CONFIG_PATH, manifest=DEFAULT_CONFIG_PATH)
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--as-of-date", default=DEFAULT_AS_OF_DATE)
    parser.add_argument("--run-version", default=None)
    parser.add_argument("--scheduler-run-id", default=None)
    parser.add_argument("--scheduler-instance-id", default=None)
    parser.add_argument("--target-holdings", type=int, default=20)
    parser.add_argument("--max-single-weight", type=float, default=0.075)
    parser.add_argument("--rebalance-frequency", default="biweekly")
    parser.add_argument("--feature-set-id", default="strategy1_pv_fin_risk_v0_20260606")
    parser.add_argument("--feature-version", default="strategy1_pv_v0_20260601")
    parser.add_argument("--fin-feature-version", default="fin_default_v0_20260602")
    parser.add_argument("--market-state-version", default="market_state_v0_20260606")
    parser.add_argument("--tail-risk-profile-id", default="diagnostic_only")
    parser.add_argument("--candidate-set-id", default=DEFAULT_CANDIDATE_SET_ID)
    parser.add_argument("--candidate-parallelism", type=int, default=0)
    parser.add_argument("--force-replace", action="store_true")
    parser.add_argument("--skip-gcs-upload", action="store_true")
    parser.add_argument("--skip-diagnosis", action="store_true")
    parser.add_argument("--skip-qa", action="store_true")
    parser.add_argument("--skip-b26-diagnostic-reference", action="store_true")
    parser.add_argument("--skip-yearly-diagnostic-backtest", action="store_true")
    parser.add_argument("--global-candidate-task-limit", type=int, default=20)
    parser.add_argument("--global-cpu-limit", type=int, default=40)
    parser.add_argument("--global-memory-gib-limit", type=int, default=160)
    parser.add_argument("--max-active-fanout-executions", type=int, default=4)
    parser.add_argument("--max-active-panel-jobs", type=int, default=1)
    parser.add_argument("--max-active-prepare-jobs", type=int, default=1)
    parser.add_argument("--max-active-select-jobs", type=int, default=1)
    parser.add_argument("--max-active-backtest-jobs", type=int, default=1)
    parser.add_argument("--min-candidate-batch-size", type=int, default=2)
    parser.add_argument("--no-tail-fill-single-task", dest="tail_fill_single_task", action="store_false", default=True)
    parser.add_argument("--stage-policy", default="pipeline_v1")
    parser.add_argument("--lock-bucket", default=None)
    parser.add_argument("--lock-prefix", default=None)
    parser.add_argument("--lock-ttl-minutes", type=int, default=None)
    parser.add_argument("--heartbeat-interval-seconds", type=int, default=None)
    parser.add_argument("--execute-live", action="store_true", help="Submit live Cloud Run executions; requires --candidate-only-smoke")
    parser.add_argument("--candidate-only-smoke", action="store_true", help="Limit live mode to the PRD_07 candidate-only smoke subset")
    parser.add_argument("--smoke-year", dest="smoke_years", type=int, action="append", default=None)
    parser.add_argument("--smoke-candidates-per-year", type=int, default=3)
    parser.add_argument("--candidate-smoke-batch-size", type=int, default=1)
    parser.add_argument("--live-poll-seconds", type=float, default=15.0)
    parser.add_argument("--max-live-poll-attempts", type=int, default=120)
    parser.add_argument("--output", default=None, help="Optional local path for scheduler dry-run JSON")
    args = parser.parse_args()
    if args.execute_live:
        if args.dry_run:
            parser.error("--execute-live cannot be combined with --dry-run")
        if not args.candidate_only_smoke:
            parser.error("--execute-live requires --candidate-only-smoke")
        if args.smoke_candidates_per_year < 1:
            parser.error("--smoke-candidates-per-year must be >= 1")
        if args.candidate_smoke_batch_size < 1:
            parser.error("--candidate-smoke-batch-size must be >= 1")
    return args


def build_scheduler_plan(*, config, args: argparse.Namespace) -> dict[str, Any]:
    as_of = parse_iso_date(args.as_of_date)
    version = args.run_version or f"v{datetime.now(timezone.utc).strftime('%Y%m%d')}_01"
    years = list(range(args.start_year, args.end_year + 1))
    if not years:
        raise ValueError("--start-year/--end-year produced an empty range")
    experiments = [
        build_year_experiment(
            backtest_year=year,
            args=args,
            version=version,
            as_of=as_of,
            continuous_anchor_start=actual_first_trading_day(args.start_year),
        )
        for year in years
    ]
    continuous_backtest_id = continuous_backtest_id_for(
        start_year=args.start_year,
        end_year=args.end_year,
        target_holdings=args.target_holdings,
        max_single_weight=args.max_single_weight,
        version=version,
    )
    stage_tokens = default_stage_tokens(config)
    limits = SchedulerLimits(
        candidate_task_slots=args.global_candidate_task_limit,
        cloudrun_cpu_tokens=args.global_cpu_limit,
        cloudrun_memory_gib_tokens=args.global_memory_gib_limit,
        active_fanout_executions=args.max_active_fanout_executions,
        active_panel_jobs=args.max_active_panel_jobs,
        active_prepare_jobs=args.max_active_prepare_jobs,
        active_select_jobs=args.max_active_select_jobs,
        active_backtest_jobs=args.max_active_backtest_jobs,
    )
    tasks = build_pipeline_tasks(
        config=config,
        args=args,
        experiments=experiments,
        continuous_backtest_id=continuous_backtest_id,
        stage_tokens=stage_tokens,
    )
    simulation = simulate_dry_run_schedule(
        tasks,
        limits=limits,
        min_candidate_batch_size=args.min_candidate_batch_size,
        tail_fill_single_task=args.tail_fill_single_task,
        config=config,
        args=args,
    )
    scheduler_run_id = args.scheduler_run_id or scheduler_run_id_for(
        candidate_set_id=args.candidate_set_id,
        start_year=args.start_year,
        end_year=args.end_year,
        run_version=version,
    )
    plan_hash = stable_plan_hash(tasks)
    lock_bucket = args.lock_bucket or config.lock_bucket
    lock_prefix = args.lock_prefix or config.lock_prefix
    return {
        "entrypoint": "annual_pipeline_scheduler",
        "runner_version": __version__,
        "status": "dry_run" if args.dry_run else "planned_not_executed",
        "stage_policy": args.stage_policy,
        "project": config.project,
        "region": config.region,
        "output_dataset_role": config.output_dataset_role,
        "config": args.config,
        "manifest": args.manifest,
        "candidate_set_id": args.candidate_set_id,
        "candidate_count": len(config.candidate_grid),
        "candidate_grid_hash": candidate_grid_hash(config),
        "start_year": args.start_year,
        "end_year": args.end_year,
        "as_of_date": args.as_of_date,
        "run_version": version,
        "scheduler_run_id": scheduler_run_id,
        "scheduler_instance_id": args.scheduler_instance_id,
        "plan_hash": plan_hash,
        "scheduler_lock": {
            "lock_key": scheduler_lock_key(args.candidate_set_id, args.start_year, args.end_year, version),
            "bucket": lock_bucket,
            "prefix": lock_prefix,
            "ttl_minutes": args.lock_ttl_minutes,
            "heartbeat_interval_seconds": args.heartbeat_interval_seconds,
            "generation_guarded": True,
            "create_precondition": "if_generation_match=0",
            "heartbeat_precondition": "if_generation_match=<current_generation>",
        },
        "state_model": {
            "authoritative_store": "gcs_generation_conditioned_json",
            "bucket": lock_bucket,
            "prefix": f"{lock_prefix.rstrip('/')}/annual_pipeline_state" if lock_prefix else None,
            "state_key": scheduler_run_id,
            "create_precondition": "if_generation_match=0",
            "update_precondition": "if_generation_match=<current_generation>",
            "generation_mismatch_action": "re_read_reconcile_running_executions_and_artifacts",
            "blind_overwrite_allowed": False,
        },
        "resource_limits": limits.to_dict(),
        "stage_tokens": stage_tokens_for_output(stage_tokens),
        "fanout_execution_accounting": {
            "dry_run_model": "candidate_year_proxy",
            "live_model": "cloud_run_execution",
            "phase2_required_model": "cloud_run_execution",
            "note": (
                "Phase 1 dry-run counts active candidate fanout by year. "
                "Phase 2 live scheduling must count actual Cloud Run executions, "
                "because retries and tail batches can split one year into multiple executions."
            ),
        },
        "continuous_ledger": {
            "backtest_id": continuous_backtest_id,
            "prediction_run_ids": [final_refit_experiment(exp).prediction_run_id for exp in experiments],
            "prediction_merge_required": True,
            "fresh_segment_stitching_allowed": False,
            "resume_segment_allowed_if_qa_passed": True,
        },
        "b26_diagnostic_reference": None if args.skip_b26_diagnostic_reference else b26_reference_plan(args),
        "task_count": len(tasks),
        "tasks": [task.to_dict() for task in tasks],
        "simulation": simulation,
    }


def default_stage_tokens(config) -> dict[str, ResourceTokens]:
    return {
        STAGE_PANEL: ResourceTokens(),
        STAGE_REFIT_PANEL: ResourceTokens(),
        STAGE_MATRIX: ResourceTokens(cpu=DEFAULT_PREPARE_CPU, memory_gib=DEFAULT_PREPARE_MEMORY_GIB),
        STAGE_CANDIDATE: ResourceTokens(
            cpu=int(config.candidate_task_cpu or DEFAULT_CANDIDATE_CPU),
            memory_gib=parse_gib(config.candidate_task_memory or f"{DEFAULT_CANDIDATE_MEMORY_GIB}Gi"),
            candidate_slots=1,
        ),
        STAGE_SELECT: ResourceTokens(cpu=DEFAULT_SELECT_CPU, memory_gib=DEFAULT_SELECT_MEMORY_GIB),
        STAGE_REFIT: ResourceTokens(cpu=DEFAULT_REFIT_CPU, memory_gib=DEFAULT_REFIT_MEMORY_GIB),
        STAGE_DIAGNOSTIC_BACKTEST: ResourceTokens(cpu=DEFAULT_BACKTEST_CPU, memory_gib=DEFAULT_BACKTEST_MEMORY_GIB),
        STAGE_CONTINUOUS_LEDGER: ResourceTokens(cpu=DEFAULT_BACKTEST_CPU, memory_gib=DEFAULT_BACKTEST_MEMORY_GIB),
    }


def stage_tokens_for_output(stage_tokens: dict[str, ResourceTokens]) -> dict[str, dict[str, int]]:
    output = {stage: tokens.to_dict() for stage, tokens in stage_tokens.items()}
    output["prepare_matrix"] = stage_tokens[STAGE_MATRIX].to_dict()
    return output


def parse_gib(value: str | int) -> int:
    if isinstance(value, int):
        return value
    normalized = value.strip().lower()
    if normalized.endswith("gi"):
        normalized = normalized[:-2]
    elif normalized.endswith("gib"):
        normalized = normalized[:-3]
    return int(normalized)


def build_pipeline_tasks(
    *,
    config,
    args: argparse.Namespace,
    experiments: Iterable[Any],
    continuous_backtest_id: str,
    stage_tokens: dict[str, ResourceTokens],
) -> list[PipelineTask]:
    tasks: list[PipelineTask] = []
    refit_task_ids: list[str] = []
    include_backtest = not args.skip_yearly_diagnostic_backtest
    for exp in experiments:
        year = int(exp.raw["backtest_year"])
        year_commands = command_plan(config=config, exp=exp, args=args, include_backtest=include_backtest)
        by_step = {item["step_id"]: item for item in year_commands}
        matrix_id = default_matrix_id(config, exp)
        matrix_uri = matrix_artifact_uri(config, exp, matrix_id)
        panel_id = task_id(STAGE_PANEL, year)
        matrix_id_task = task_id(STAGE_MATRIX, year)
        tasks.append(PipelineTask(
            task_id=panel_id,
            stage=STAGE_PANEL,
            year=year,
            dependencies=(),
            tokens=stage_tokens[STAGE_PANEL],
            command=tuple(by_step["build_training_panel"]["command"]),
            job_name=by_step["build_training_panel"].get("job_name"),
            artifact_uri=None,
        ))
        tasks.append(PipelineTask(
            task_id=matrix_id_task,
            stage=STAGE_MATRIX,
            year=year,
            dependencies=(panel_id,),
            tokens=stage_tokens[STAGE_MATRIX],
            command=tuple(by_step["cloudrun_prepare_matrix"]["command"]),
            job_name=by_step["cloudrun_prepare_matrix"].get("job_name"),
            matrix_id=matrix_id,
            matrix_uri=matrix_uri,
            artifact_uri=matrix_uri,
        ))
        candidate_ids = []
        for unit_index, candidate in enumerate(config.candidate_grid):
            candidate_id = str(candidate["candidate_id"])
            candidate_ids.append(task_id(STAGE_CANDIDATE, year, unit_index))
            tasks.append(PipelineTask(
                task_id=task_id(STAGE_CANDIDATE, year, unit_index),
                stage=STAGE_CANDIDATE,
                year=year,
                unit_index=unit_index,
                candidate_id=candidate_id,
                dependencies=(matrix_id_task,),
                tokens=stage_tokens[STAGE_CANDIDATE],
                job_name=config.train_candidate_fanout_job,
                matrix_id=matrix_id,
                matrix_uri=matrix_uri,
                artifact_uri=candidate_output_uri(matrix_uri, unit_index),
            ))
        select_id = task_id(STAGE_SELECT, year)
        tasks.append(PipelineTask(
            task_id=select_id,
            stage=STAGE_SELECT,
            year=year,
            dependencies=tuple(candidate_ids),
            tokens=stage_tokens[STAGE_SELECT],
            command=tuple(by_step["cloudrun_select_register_predict"]["command"]),
            job_name=by_step["cloudrun_select_register_predict"].get("job_name"),
            matrix_id=matrix_id,
            matrix_uri=matrix_uri,
        ))
        refit_panel_id = task_id(STAGE_REFIT_PANEL, year)
        refit_panel_step = by_step["build_refit_training_panel"]
        tasks.append(PipelineTask(
            task_id=refit_panel_id,
            stage=STAGE_REFIT_PANEL,
            year=year,
            dependencies=(select_id,),
            tokens=stage_tokens[STAGE_REFIT_PANEL],
            command=tuple(refit_panel_step["command"]),
            job_name=refit_panel_step.get("job_name"),
            artifact_uri=None,
        ))
        refit_id = task_id(STAGE_REFIT, year)
        refit_step = by_step["cloudrun_refit_register_predict"]
        tasks.append(PipelineTask(
            task_id=refit_id,
            stage=STAGE_REFIT,
            year=year,
            dependencies=(refit_panel_id,),
            tokens=stage_tokens[STAGE_REFIT],
            command=tuple(refit_step["command"]),
            job_name=refit_step.get("job_name"),
            matrix_id=matrix_id,
            matrix_uri=matrix_uri,
        ))
        refit_task_ids.append(refit_id)
        if include_backtest:
            backtest_step = by_step["cloudrun_backtest_report"]
            tasks.append(PipelineTask(
                task_id=task_id(STAGE_DIAGNOSTIC_BACKTEST, year),
                stage=STAGE_DIAGNOSTIC_BACKTEST,
                year=year,
                dependencies=(refit_id,),
                tokens=stage_tokens[STAGE_DIAGNOSTIC_BACKTEST],
                command=tuple(backtest_step["command"]),
                job_name=backtest_step.get("job_name"),
                diagnostic_only=True,
            ))
    tasks.append(PipelineTask(
        task_id=STAGE_CONTINUOUS_LEDGER,
        stage=STAGE_CONTINUOUS_LEDGER,
        year=None,
        dependencies=tuple(refit_task_ids),
        tokens=stage_tokens[STAGE_CONTINUOUS_LEDGER],
        artifact_uri=continuous_backtest_id,
    ))
    return tasks


def task_id(stage: str, year: int, unit_index: int | None = None) -> str:
    if unit_index is None:
        return f"{stage}:y{year}"
    return f"{stage}:y{year}:u{unit_index:03d}"


def ready_tasks(
    tasks: Iterable[PipelineTask],
    statuses: dict[str, str],
    *,
    context: SchedulerContext,
) -> list[PipelineTask]:
    if not context.can_submit:
        return []
    ready = []
    for task in tasks:
        if statuses.get(task.task_id, STATUS_PLANNED) != STATUS_PLANNED:
            continue
        if all(statuses.get(dep) == STATUS_SUCCEEDED for dep in task.dependencies):
            ready.append(task)
    return sorted(ready, key=task_priority)


def task_priority(task: PipelineTask) -> tuple[int, int, int]:
    stage_priority = {
        STAGE_CANDIDATE: 10,
        STAGE_SELECT: 20,
        STAGE_REFIT_PANEL: 30,
        STAGE_REFIT: 40,
        STAGE_PANEL: 50,
        STAGE_MATRIX: 60,
        STAGE_DIAGNOSTIC_BACKTEST: 70,
        STAGE_CONTINUOUS_LEDGER: 80,
    }
    return (
        stage_priority[task.stage],
        task.year if task.year is not None else 9999,
        task.unit_index if task.unit_index is not None else -1,
    )


def resource_usage(tasks: Iterable[PipelineTask]) -> ResourceTokens:
    usage = ResourceTokens()
    for task in tasks:
        usage = usage.add(task.tokens)
    return usage


def can_admit(
    task: PipelineTask,
    *,
    active_tasks: Iterable[PipelineTask],
    selected_tasks: Iterable[PipelineTask],
    limits: SchedulerLimits,
) -> bool:
    current = list(active_tasks) + list(selected_tasks)
    usage = resource_usage(current).add(task.tokens)
    if usage.cpu > limits.cloudrun_cpu_tokens:
        return False
    if usage.memory_gib > limits.cloudrun_memory_gib_tokens:
        return False
    if usage.candidate_slots > limits.candidate_task_slots:
        return False
    stage_counts = Counter(item.stage for item in current)
    if stage_counts[task.stage] + 1 > limits.stage_limit(task.stage):
        return False
    return True


def select_admissible_tasks(
    ready: Iterable[PipelineTask],
    *,
    active_tasks: Iterable[PipelineTask],
    limits: SchedulerLimits,
) -> list[PipelineTask]:
    selected: list[PipelineTask] = []
    active_candidate_years = {task.year for task in active_tasks if task.stage == STAGE_CANDIDATE}
    selected_candidate_years: set[int | None] = set()
    for task in ready:
        new_candidate_year = False
        if task.stage == STAGE_CANDIDATE:
            active_fanout_count = len(active_candidate_years | selected_candidate_years)
            if task.year not in active_candidate_years and task.year not in selected_candidate_years:
                if active_fanout_count >= limits.active_fanout_executions:
                    continue
                new_candidate_year = True
        if can_admit(task, active_tasks=active_tasks, selected_tasks=selected, limits=limits):
            selected.append(task)
            if new_candidate_year:
                selected_candidate_years.add(task.year)
    return selected


def simulate_dry_run_schedule(
    tasks: list[PipelineTask],
    *,
    limits: SchedulerLimits,
    min_candidate_batch_size: int,
    tail_fill_single_task: bool,
    config,
    args: argparse.Namespace,
) -> dict[str, Any]:
    statuses = {task.task_id: STATUS_PLANNED for task in tasks}
    waves = []
    peak = ResourceTokens()
    task_map = {task.task_id: task for task in tasks}
    break_reason = None
    context = SchedulerContext(lock_owned=True, scheduler_lock_generation=1)
    for wave_no in range(1, len(tasks) + 1):
        ready = ready_tasks(tasks, statuses, context=context)
        admitted = select_admissible_tasks(ready, active_tasks=[], limits=limits)
        if not admitted:
            remaining = [task_id for task_id, status in statuses.items() if status == STATUS_PLANNED]
            deferred = [task_id for task_id, status in statuses.items() if status == STATUS_DEFERRED]
            if remaining and deferred:
                break_reason = "blocked_by_deferred_candidate_batches"
                break
            if remaining:
                raise RuntimeError(f"scheduler deadlock in dry-run; remaining planned tasks: {remaining[:10]}")
            break
        groups = submission_groups_for_wave(
            admitted,
            config=config,
            args=args,
            min_candidate_batch_size=min_candidate_batch_size,
            tail_fill_single_task=tail_fill_single_task,
        )
        submitted_task_ids, deferred_task_ids = submitted_and_deferred_task_ids(groups)
        submitted_tasks = [task_map[task_id] for task_id in submitted_task_ids]
        usage = resource_usage(submitted_tasks)
        peak = ResourceTokens(
            cpu=max(peak.cpu, usage.cpu),
            memory_gib=max(peak.memory_gib, usage.memory_gib),
            candidate_slots=max(peak.candidate_slots, usage.candidate_slots),
        )
        waves.append({
            "wave": wave_no,
            "submitted_task_ids": submitted_task_ids,
            "deferred_task_ids": deferred_task_ids,
            "resource_usage": usage.to_dict(),
            "submission_groups": groups,
        })
        for task_id in submitted_task_ids:
            statuses[task_id] = STATUS_SUCCEEDED
        for task_id in deferred_task_ids:
            statuses[task_id] = STATUS_DEFERRED
        if not submitted_task_ids and deferred_task_ids:
            break_reason = "blocked_by_deferred_candidate_batches"
            break
    assert all(task_id in task_map for task_id in statuses)
    deferred_task_ids = [task_id for task_id, status in statuses.items() if status == STATUS_DEFERRED]
    return {
        "simulation_model": SIMULATION_MODEL_SYNCHRONOUS_WAVES,
        "simulation_model_note": (
            "Dry-run waves mark submitted tasks succeeded before the next scheduling pass. "
            "This validates DAG/resource admission, but it does not model long-running overlap "
            "such as a slow candidate remaining active while the next year starts."
        ),
        "peak_resource_usage_semantics": "synchronous_wave_reference_not_live_capacity_ceiling",
        "wave_count": len(waves),
        "peak_resource_usage": peak.to_dict(),
        "all_tasks_scheduled": all(status == STATUS_SUCCEEDED for status in statuses.values()),
        "deferred_task_count": len(deferred_task_ids),
        "deferred_task_ids": deferred_task_ids,
        "terminal_status_counts": dict(sorted(Counter(statuses.values()).items())),
        "break_reason": break_reason,
        "waves": waves,
    }


def submission_groups_for_wave(
    tasks: Iterable[PipelineTask],
    *,
    config,
    args: argparse.Namespace,
    min_candidate_batch_size: int,
    tail_fill_single_task: bool,
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    candidates_by_year: dict[int, list[PipelineTask]] = defaultdict(list)
    for task in tasks:
        if task.stage == STAGE_CANDIDATE and task.year is not None:
            candidates_by_year[task.year].append(task)
        else:
            groups.append({
                "group_type": "single_task",
                "task_ids": [task.task_id],
                "stage": task.stage,
                "year": task.year,
                "command": list(task.command),
            })
    for year in sorted(candidates_by_year):
        ordered = sorted(candidates_by_year[year], key=lambda item: int(item.unit_index or 0))
        for run in contiguous_candidate_runs(ordered):
            batch_size = len(run)
            below_min = batch_size < min_candidate_batch_size
            if below_min and not tail_fill_single_task:
                groups.append({
                    "group_type": "candidate_batch_deferred",
                    "task_ids": [task.task_id for task in run],
                    "stage": STAGE_CANDIDATE,
                    "year": year,
                    "reason": "below_min_candidate_batch_size",
                })
                continue
            first = run[0]
            groups.append({
                "group_type": "candidate_fanout_batch",
                "task_ids": [task.task_id for task in run],
                "stage": STAGE_CANDIDATE,
                "year": year,
                "task_index_offset": first.unit_index,
                "tasks": batch_size,
                "below_min_candidate_batch_size": below_min,
                "matrix_id": first.matrix_id,
                "matrix_uri": first.matrix_uri,
                "command": candidate_batch_command(config, args, first.matrix_id, first.matrix_uri, first.unit_index or 0, batch_size),
            })
    return groups


def execute_candidate_only_live_smoke(
    *,
    plan: dict[str, Any],
    config,
    args: argparse.Namespace,
    state_store: Any | None = None,
    lease: Any | None = None,
    cloud_run: Any | None = None,
    artifact_store: Any | None = None,
) -> dict[str, Any]:
    if not getattr(args, "execute_live", False) or not getattr(args, "candidate_only_smoke", False):
        raise ValueError("live scheduler requires --execute-live --candidate-only-smoke")
    if int(plan["start_year"]) == 2021 and int(plan["end_year"]) == 2026:
        # The smoke subset is still small, but keep the result explicit so a
        # full-range invocation cannot be mistaken for a full live pipeline.
        live_scope = "candidate_only_smoke_subset_of_full_plan"
    else:
        live_scope = "candidate_only_smoke_subset"
    lock_bucket = plan["scheduler_lock"]["bucket"]
    lock_prefix = plan["scheduler_lock"]["prefix"]
    if not lock_bucket or not lock_prefix:
        raise ValueError("live scheduler requires lock bucket and prefix")
    owner = args.scheduler_instance_id or f"annual-pipeline-scheduler-{int(time.time())}"
    if state_store is None:
        state_store = GcsGenerationStateStore(
            project=config.project,
            bucket=lock_bucket,
            prefix=f"{lock_prefix.rstrip('/')}/annual_pipeline_state",
            state_key=plan["scheduler_run_id"],
        )
    if lease is None:
        lease = GcsSchedulerLease(
            project=config.project,
            bucket=lock_bucket,
            prefix=lock_prefix,
            lock_key=plan["scheduler_lock"]["lock_key"],
            owner=owner,
            ttl_minutes=int(args.lock_ttl_minutes or 30),
        )
    if cloud_run is None:
        cloud_run = GcloudExecutionClient()
    if artifact_store is None:
        artifact_store = GcsArtifactStore(project=config.project)
    if not lease.acquire():
        raise LiveSchedulerOwnershipLost("annual scheduler lease is held by another owner")
    units = candidate_smoke_execution_units(plan=plan, config=config, args=args)
    summary = {
        "entrypoint": "annual_pipeline_scheduler",
        "status": "live_candidate_only_smoke_completed",
        "live_scope": live_scope,
        "scheduler_run_id": plan["scheduler_run_id"],
        "scheduler_instance_id": owner,
        "plan_hash": plan["plan_hash"],
        "fanout_execution_accounting": "cloud_run_execution",
        "unit_count": len(units),
        "submitted_execution_count": 0,
        "skipped_artifact_count": 0,
        "recovered_execution_count": 0,
        "failed_execution_count": 0,
        "units": [],
    }
    try:
        ensure_live_state(state_store, plan=plan, units=units)
        for unit in units:
            if not lease.heartbeat():
                raise LiveSchedulerOwnershipLost(f"lost scheduler lease before submitting {unit.unit_key}")
            outcome = process_live_unit(
                unit,
                plan=plan,
                config=config,
                args=args,
                state_store=state_store,
                lease=lease,
                cloud_run=cloud_run,
                artifact_store=artifact_store,
            )
            summary["units"].append(outcome)
            if outcome["action"] == "submitted":
                summary["submitted_execution_count"] += 1
            if outcome["action"] == "artifact_skip":
                summary["skipped_artifact_count"] += 1
            if outcome["action"] == "recovered":
                summary["recovered_execution_count"] += 1
            if outcome["status"] == STATUS_FAILED:
                summary["failed_execution_count"] += 1
        if summary["failed_execution_count"]:
            summary["status"] = "live_candidate_only_smoke_failed"
        return summary
    finally:
        lease.release()


def candidate_smoke_execution_units(*, plan: dict[str, Any], config, args: argparse.Namespace) -> list[LiveExecutionUnit]:
    available_years = sorted({int(task["year"]) for task in plan["tasks"] if task["stage"] == STAGE_CANDIDATE})
    selected_years = args.smoke_years or available_years[:2]
    task_by_id = {task["task_id"]: task for task in plan["tasks"]}
    units: list[LiveExecutionUnit] = []
    batch_size = int(args.candidate_smoke_batch_size)
    for year in selected_years:
        candidates = [
            task for task in plan["tasks"]
            if task["stage"] == STAGE_CANDIDATE and int(task["year"]) == int(year)
        ]
        candidates = sorted(candidates, key=lambda item: int(item["unit_index"]))[: int(args.smoke_candidates_per_year)]
        for batch_index in range(0, len(candidates), batch_size):
            batch = candidates[batch_index: batch_index + batch_size]
            if not batch:
                continue
            first = task_by_id[batch[0]["task_id"]]
            offset = int(first["unit_index"])
            tasks = len(batch)
            matrix_id = first["matrix_id"]
            matrix_uri = first["matrix_uri"]
            unit_key = f"candidate_smoke:y{year}:u{offset:03d}:n{tasks:03d}"
            tokens = ResourceTokens(
                cpu=sum(int(item["resource_tokens"]["cpu"]) for item in batch),
                memory_gib=sum(int(item["resource_tokens"]["memory_gib"]) for item in batch),
                candidate_slots=sum(int(item["resource_tokens"]["candidate_slots"]) for item in batch),
            )
            units.append(LiveExecutionUnit(
                unit_key=unit_key,
                stage=STAGE_CANDIDATE,
                year=int(year),
                task_ids=tuple(str(item["task_id"]) for item in batch),
                command=tuple(candidate_batch_command(config, args, matrix_id, matrix_uri, offset, tasks)),
                job_name=str(first["job_name"]),
                tokens=tokens,
                matrix_uri=str(matrix_uri),
                artifact_uris=tuple(str(item["artifact_uri"]) for item in batch if item.get("artifact_uri")),
            ))
    return units


def ensure_live_state(state_store: Any, *, plan: dict[str, Any], units: list[LiveExecutionUnit]) -> None:
    payload, generation = state_store.read()
    now = utc_now().isoformat()
    seed_units = {unit.unit_key: unit.to_state_seed() for unit in units}
    if payload is None:
        payload = {
            "schema_version": 1,
            "scheduler_run_id": plan["scheduler_run_id"],
            "plan_hash": plan["plan_hash"],
            "created_at": now,
            "updated_at": now,
            "units": seed_units,
        }
        state_store.create_if_absent(payload)
        payload, generation = state_store.read()
        if payload is None or generation is None:
            raise StateGenerationMismatch("state create finished but object could not be read")
    if payload.get("plan_hash") != plan["plan_hash"]:
        raise ValueError(
            f"state plan hash mismatch for {plan['scheduler_run_id']}: "
            f"{payload.get('plan_hash')} != {plan['plan_hash']}"
        )
    changed = False
    payload.setdefault("units", {})
    for key, seed in seed_units.items():
        if key not in payload["units"]:
            payload["units"][key] = seed
            changed = True
    if changed:
        payload["updated_at"] = now
        state_store.update(payload, expected_generation=generation)


def process_live_unit(
    unit: LiveExecutionUnit,
    *,
    plan: dict[str, Any],
    config,
    args: argparse.Namespace,
    state_store: Any,
    lease: Any,
    cloud_run: Any,
    artifact_store: Any,
) -> dict[str, Any]:
    state_payload, _ = state_store.read()
    record = (state_payload or {}).get("units", {}).get(unit.unit_key, {})
    if record.get("status") in {STATUS_SUCCEEDED, STATUS_SKIPPED}:
        return {"unit_key": unit.unit_key, "action": "already_terminal", "status": record["status"]}
    execution_id = record.get("execution_id")
    action = "recovered" if record.get("status") == STATUS_RUNNING and execution_id else "submitted"
    if not execution_id:
        if not artifact_store.matrix_ready(unit):
            update_live_unit_state(
                state_store,
                unit.unit_key,
                {
                    "status": STATUS_FAILED,
                    "error_message": "candidate live smoke requires existing matrix_manifest.json and work_units.json",
                    "artifact_status": "matrix_missing",
                    "finished_at": utc_now().isoformat(),
                },
            )
            return {
                "unit_key": unit.unit_key,
                "action": "matrix_missing",
                "status": STATUS_FAILED,
                "artifact_status": "matrix_missing",
            }
        if artifact_store.artifact_complete(unit):
            update_live_unit_state(
                state_store,
                unit.unit_key,
                {
                    "status": STATUS_SKIPPED,
                    "artifact_status": "present_before_submit",
                    "finished_at": utc_now().isoformat(),
                },
            )
            return {"unit_key": unit.unit_key, "action": "artifact_skip", "status": STATUS_SKIPPED}
        if not can_admit_live_execution(unit, state_payload or {}, plan):
            return {"unit_key": unit.unit_key, "action": "blocked_by_live_admission", "status": STATUS_PLANNED}
        submit_result = cloud_run.submit(unit.command)
        execution_id = submit_result.execution_id
        if not execution_id:
            update_live_unit_state(
                state_store,
                unit.unit_key,
                {
                    "status": STATUS_FAILED,
                    "error_message": "gcloud execute did not return a Cloud Run execution id",
                    "submit_returncode": submit_result.returncode,
                    "submit_stdout_tail": submit_result.stdout_tail,
                    "submit_stderr_tail": submit_result.stderr_tail,
                    "finished_at": utc_now().isoformat(),
                },
            )
            return {"unit_key": unit.unit_key, "action": action, "status": STATUS_FAILED}
        update_live_unit_state(
            state_store,
            unit.unit_key,
            {
                "status": STATUS_RUNNING,
                "execution_id": execution_id,
                "submit_returncode": submit_result.returncode,
                "submit_stdout_tail": submit_result.stdout_tail,
                "submit_stderr_tail": submit_result.stderr_tail,
                "submitted_at": utc_now().isoformat(),
            },
        )
    final = wait_for_live_execution_confirmation(
        unit,
        execution_id=str(execution_id),
        config=config,
        args=args,
        lease=lease,
        cloud_run=cloud_run,
        artifact_store=artifact_store,
    )
    update_live_unit_state(state_store, unit.unit_key, final)
    return {
        "unit_key": unit.unit_key,
        "action": action,
        "status": final["status"],
        "execution_id": execution_id,
        "artifact_status": final.get("artifact_status"),
    }


def wait_for_live_execution_confirmation(
    unit: LiveExecutionUnit,
    *,
    execution_id: str,
    config,
    args: argparse.Namespace,
    lease: Any,
    cloud_run: Any,
    artifact_store: Any,
) -> dict[str, Any]:
    attempts = int(args.max_live_poll_attempts)
    poll_seconds = float(args.live_poll_seconds)
    last_state = "unknown"
    for attempt in range(1, attempts + 1):
        if not lease.heartbeat():
            raise LiveSchedulerOwnershipLost(f"lost scheduler lease while waiting for {execution_id}")
        payload = cloud_run.describe(project=config.project, region=config.region, execution_id=execution_id)
        last_state = cloud_run_execution_state(payload)
        artifact_ok = artifact_store.artifact_complete(unit)
        if last_state == STATUS_SUCCEEDED and artifact_ok:
            return {
                "status": STATUS_SUCCEEDED,
                "cloud_run_execution_state": last_state,
                "artifact_status": "present_after_describe_success",
                "finished_at": utc_now().isoformat(),
                "describe_attempts": attempt,
            }
        if last_state in {STATUS_FAILED, "cancelled"}:
            return {
                "status": STATUS_FAILED,
                "cloud_run_execution_state": last_state,
                "artifact_status": "present" if artifact_ok else "missing",
                "finished_at": utc_now().isoformat(),
                "describe_attempts": attempt,
            }
        if poll_seconds > 0:
            time.sleep(poll_seconds)
    artifact_ok = artifact_store.artifact_complete(unit)
    return {
        "status": STATUS_SUCCEEDED if last_state == STATUS_SUCCEEDED and artifact_ok else STATUS_FAILED,
        "cloud_run_execution_state": last_state,
        "artifact_status": "present" if artifact_ok else "missing",
        "finished_at": utc_now().isoformat(),
        "describe_attempts": attempts,
        "error_message": None if last_state == STATUS_SUCCEEDED and artifact_ok else "describe/artifact confirmation did not succeed",
    }


def update_live_unit_state(state_store: Any, unit_key: str, patch: dict[str, Any]) -> None:
    for _ in range(3):
        payload, generation = state_store.read()
        if payload is None or generation is None:
            raise StateGenerationMismatch("state disappeared during live update")
        next_payload = json.loads(json_dumps_strict(payload, ensure_ascii=False))
        units = next_payload.setdefault("units", {})
        record = dict(units.get(unit_key) or {"unit_key": unit_key})
        record.update(patch)
        units[unit_key] = record
        next_payload["updated_at"] = utc_now().isoformat()
        try:
            state_store.update(next_payload, expected_generation=generation)
            return
        except StateGenerationMismatch:
            continue
    raise StateGenerationMismatch(f"state update for {unit_key} lost generation race")


def can_admit_live_execution(unit: LiveExecutionUnit, state_payload: dict[str, Any], plan: dict[str, Any]) -> bool:
    running = [
        record for record in (state_payload.get("units") or {}).values()
        if record.get("status") == STATUS_RUNNING
    ]
    active_tokens = ResourceTokens()
    for record in running:
        raw = record.get("resource_tokens") or {}
        active_tokens = active_tokens.add(ResourceTokens(
            cpu=int(raw.get("cpu") or 0),
            memory_gib=int(raw.get("memory_gib") or 0),
            candidate_slots=int(raw.get("candidate_slots") or 0),
        ))
    usage = active_tokens.add(unit.tokens)
    limits = plan["resource_limits"]
    if usage.cpu > int(limits["cloudrun_cpu_tokens"]):
        return False
    if usage.memory_gib > int(limits["cloudrun_memory_gib_tokens"]):
        return False
    if usage.candidate_slots > int(limits["candidate_task_slots"]):
        return False
    running_candidate_executions = sum(1 for record in running if record.get("stage") == STAGE_CANDIDATE)
    if unit.stage == STAGE_CANDIDATE and running_candidate_executions + 1 > int(limits["active_fanout_executions"]):
        return False
    return True


def submitted_and_deferred_task_ids(groups: Iterable[dict[str, Any]]) -> tuple[list[str], list[str]]:
    submitted: list[str] = []
    deferred: list[str] = []
    for group in groups:
        task_ids = list(group.get("task_ids") or [])
        if group.get("group_type") == "candidate_batch_deferred":
            deferred.extend(task_ids)
        else:
            submitted.extend(task_ids)
    return submitted, deferred


def contiguous_candidate_runs(tasks: list[PipelineTask]) -> list[list[PipelineTask]]:
    if not tasks:
        return []
    runs = [[tasks[0]]]
    for task in tasks[1:]:
        prev = runs[-1][-1]
        if task.unit_index == (prev.unit_index or 0) + 1:
            runs[-1].append(task)
        else:
            runs.append([task])
    return runs


def candidate_batch_command(config, args: argparse.Namespace, matrix_id: str | None, matrix_uri: str | None, offset: int, tasks: int) -> list[str]:
    if matrix_id is None or matrix_uri is None:
        raise ValueError("candidate batch requires matrix_id and matrix_uri")
    return gcloud_execute_command(
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
            f"--task-index-offset={offset}",
        ],
        tasks=tasks,
        env_vars={
            "MATRIX_ID": matrix_id,
            "MATRIX_URI": matrix_uri,
            "WORK_UNITS_URI": join_gs_uri(matrix_uri, "work_units.json"),
            "TASK_INDEX_OFFSET": str(offset),
        },
    )


def scheduler_run_id_for(*, candidate_set_id: str, start_year: int, end_year: int, run_version: str) -> str:
    return f"annual_pipeline_{candidate_set_id}_{start_year}_{end_year}_{run_version}"


def scheduler_lock_key(candidate_set_id: str, start_year: int, end_year: int, run_version: str) -> str:
    return f"annual_pipeline:{candidate_set_id}:{start_year}:{end_year}:{run_version}"


def stable_plan_hash(tasks: Iterable[PipelineTask]) -> str:
    payload = [
        {
            "task_id": task.task_id,
            "stage": task.stage,
            "year": task.year,
            "unit_index": task.unit_index,
            "candidate_id": task.candidate_id,
            "dependencies": task.dependencies,
            "tokens": task.tokens.to_dict(),
        }
        for task in tasks
    ]
    return hashlib.sha256(json_dumps_strict(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def join_object_name(prefix: str, name: str) -> str:
    return "/".join([prefix.rstrip("/"), name.strip("/")]) if prefix else name.strip("/")


def _is_precondition_error(exc: Exception) -> bool:
    text = str(exc)
    return any(token in text for token in ("conditionNotMet", "PreconditionFailed", "GenerationDoesNotMatch", "412"))


def _is_not_found_error(exc: Exception) -> bool:
    text = str(exc)
    return any(token in text for token in ("NotFound", "404", "No such object"))


if __name__ == "__main__":
    raise SystemExit(main())
