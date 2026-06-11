"""Dry-run scheduler for Strategy 1 annual rolling pipeline execution."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from scripts.strategy1_cloudrun import __version__
from scripts.strategy1_cloudrun.bq_io import join_gs_uri, json_dumps_strict
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


@dataclasses.dataclass
class InMemoryGenerationStateStore:
    """Small local model of GCS generation-conditioned state writes.

    Production state writes must use GCS object generation preconditions. This
    in-memory store is used by the dry-run scheduler and tests to keep that
    contract explicit without touching GCS.
    """

    generation: int | None = None
    payload: dict[str, Any] = dataclasses.field(default_factory=dict)

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
    parser.add_argument("--output", default=None, help="Optional local path for scheduler dry-run JSON")
    return parser.parse_args()


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
            "create_precondition": "if_generation_match=0",
            "update_precondition": "if_generation_match=<current_generation>",
            "generation_mismatch_action": "re_read_reconcile_running_executions_and_artifacts",
            "blind_overwrite_allowed": False,
        },
        "resource_limits": limits.to_dict(),
        "stage_tokens": stage_tokens_for_output(stage_tokens),
        "fanout_execution_accounting": {
            "dry_run_model": "candidate_year_proxy",
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


if __name__ == "__main__":
    raise SystemExit(main())
