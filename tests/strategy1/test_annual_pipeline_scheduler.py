from __future__ import annotations

import argparse
import json

import pytest

from scripts.strategy1_cloudrun.config import RunnerConfig
from quant_ashare.strategy1.annual_pipeline_scheduler import (
    CloudRunSubmitResult,
    InMemoryGenerationStateStore,
    LiveExecutionUnit,
    LiveSchedulerOwnershipLost,
    PipelineTask,
    ResourceTokens,
    SchedulerContext,
    SchedulerLimits,
    StateGenerationMismatch,
    build_scheduler_plan,
    can_admit_live_execution,
    candidate_smoke_execution_units,
    execute_candidate_only_live_smoke,
    ready_tasks,
    select_admissible_tasks,
    simulate_dry_run_schedule,
)


def _args(**overrides) -> argparse.Namespace:
    values = {
        "config": "configs/strategy1/annual_rolling_lgbm_regression_v0.yml",
        "manifest": "configs/strategy1/annual_rolling_lgbm_regression_v0.yml",
        "project": None,
        "region": None,
        "strategy_id": None,
        "artifact_base_uri": None,
        "model_artifact_base_uri": None,
        "local_mirror_root": None,
        "output_dataset_role": None,
        "dry_run": True,
        "start_year": 2021,
        "end_year": 2022,
        "as_of_date": "2026-06-09",
        "run_version": "v20260611_test",
        "scheduler_run_id": None,
        "scheduler_instance_id": None,
        "target_holdings": 20,
        "max_single_weight": 0.075,
        "rebalance_frequency": "biweekly",
        "feature_set_id": "strategy1_pv_fin_risk_v0_20260606",
        "feature_version": "strategy1_pv_v0_20260601",
        "fin_feature_version": "fin_default_v0_20260602",
        "market_state_version": "market_state_v0_20260606",
        "tail_risk_profile_id": "diagnostic_only",
        "candidate_set_id": "strategy1_annual_rolling_lgbm_regression_11_v0",
        "candidate_parallelism": 0,
        "force_replace": False,
        "skip_gcs_upload": False,
        "skip_diagnosis": False,
        "skip_qa": False,
        "skip_b26_diagnostic_reference": False,
        "skip_yearly_diagnostic_backtest": False,
        "global_candidate_task_limit": 20,
        "global_cpu_limit": 40,
        "global_memory_gib_limit": 160,
        "max_active_fanout_executions": 4,
        "max_active_panel_jobs": 1,
        "max_active_prepare_jobs": 1,
        "max_active_select_jobs": 1,
        "max_active_backtest_jobs": 1,
        "min_candidate_batch_size": 2,
        "tail_fill_single_task": True,
        "stage_policy": "pipeline_v1",
        "lock_bucket": None,
        "lock_prefix": None,
        "lock_ttl_minutes": 30,
        "heartbeat_interval_seconds": 60,
        "execute_live": False,
        "candidate_only_smoke": False,
        "smoke_years": None,
        "smoke_candidates_per_year": 3,
        "candidate_smoke_batch_size": 1,
        "live_poll_seconds": 0,
        "max_live_poll_attempts": 1,
        "output": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_scheduler_plan_select_depends_on_all_candidates_and_cross_year_is_independent() -> None:
    config = RunnerConfig(
        output_dataset_role="research",
        training_panel_step="build_training_panel_risk_feature",
        candidate_task_cpu=2,
        candidate_task_memory="8Gi",
        candidate_grid=tuple(
            {"candidate_id": f"candidate_{idx}", "model_family": "lightgbm_regression"}
            for idx in range(11)
        ),
    )

    plan = build_scheduler_plan(config=config, args=_args())
    tasks = {task["task_id"]: task for task in plan["tasks"]}

    assert plan["entrypoint"] == "annual_pipeline_scheduler"
    assert plan["stage_tokens"]["prepare_matrix"] == {"cpu": 8, "memory_gib": 32, "candidate_slots": 0}
    assert plan["stage_tokens"]["select"] == {"cpu": 4, "memory_gib": 16, "candidate_slots": 0}
    assert plan["stage_tokens"]["refit_panel"] == {"cpu": 0, "memory_gib": 0, "candidate_slots": 0}
    assert plan["stage_tokens"]["refit"] == {"cpu": 8, "memory_gib": 32, "candidate_slots": 0}
    assert plan["stage_tokens"]["diagnostic_backtest"] == {"cpu": 4, "memory_gib": 16, "candidate_slots": 0}

    select_2021 = tasks["select:y2021"]
    assert set(select_2021["dependencies"]) == {f"candidate:y2021:u{idx:03d}" for idx in range(11)}
    assert tasks["refit_panel:y2021"]["dependencies"] == ["select:y2021"]
    assert tasks["refit:y2021"]["dependencies"] == ["refit_panel:y2021"]
    assert "quant_ashare.strategy1.sql_runner" in " ".join(tasks["refit_panel:y2021"]["command"])
    assert "--source-panel-run-id=s1_annual_roll_y2021_train2015_2019_valid2020_n20_w075_v20260611_test__refit01" in (
        " ".join(tasks["refit:y2021"]["command"])
    )
    assert "quant_ashare.strategy1.refit_register_predict" in " ".join(tasks["refit:y2021"]["command"])
    assert tasks["diagnostic_backtest:y2021"]["dependencies"] == ["refit:y2021"]
    assert "select:y2021" not in tasks["panel:y2022"]["dependencies"]
    assert tasks["matrix:y2022"]["dependencies"] == ["panel:y2022"]
    assert tasks["continuous_ledger"]["dependencies"] == ["refit:y2021", "refit:y2022"]
    assert plan["continuous_ledger"]["prediction_run_ids"] == [
        "s1_annual_roll_y2021_train2015_2019_valid2020_n20_w075_v20260611_test__refit01",
        "s1_annual_roll_y2022_train2016_2020_valid2021_n20_w075_v20260611_test__refit01",
    ]


def test_scheduler_requires_lock_ownership_before_ready_tasks() -> None:
    task = PipelineTask(
        task_id="panel:y2021",
        stage="panel",
        year=2021,
        dependencies=(),
        tokens=ResourceTokens(),
    )

    assert ready_tasks([task], {}, context=SchedulerContext(lock_owned=True, scheduler_lock_generation=12))
    assert ready_tasks([task], {}, context=SchedulerContext(lock_owned=False, scheduler_lock_generation=12)) == []
    assert ready_tasks([task], {}, context=SchedulerContext(lock_owned=True, scheduler_lock_generation=None)) == []


def test_candidate_saturation_blocks_prepare_on_shared_cpu_memory_pool() -> None:
    active = [
        PipelineTask(
            task_id=f"candidate:active:u{idx:03d}",
            stage="candidate",
            year=2021,
            unit_index=idx,
            dependencies=(),
            tokens=ResourceTokens(cpu=2, memory_gib=8, candidate_slots=1),
        )
        for idx in range(20)
    ]
    prepare = PipelineTask(
        task_id="matrix:y2022",
        stage="matrix",
        year=2022,
        dependencies=(),
        tokens=ResourceTokens(cpu=8, memory_gib=32),
    )

    admitted = select_admissible_tasks(
        [prepare],
        active_tasks=active,
        limits=SchedulerLimits(
            candidate_task_slots=20,
            cloudrun_cpu_tokens=40,
            cloudrun_memory_gib_tokens=160,
        ),
    )

    assert admitted == []


def test_generation_conditioned_state_rejects_stale_update() -> None:
    store = InMemoryGenerationStateStore()
    generation = store.create({"status": "planned"})

    next_generation = store.update({"status": "running"}, expected_generation=generation)

    assert next_generation == generation + 1
    with pytest.raises(StateGenerationMismatch, match="generation mismatch"):
        store.update({"status": "stale"}, expected_generation=generation)


def test_annual_pipeline_scheduler_cli_dry_run_outputs_json(run_module) -> None:
    proc = run_module(
        "quant_ashare.strategy1.annual_pipeline_scheduler",
        [
            "--start-year",
            "2021",
            "--end-year",
            "2021",
            "--run-version",
            "v20260611_test",
            "--dry-run",
        ],
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["entrypoint"] == "annual_pipeline_scheduler"
    assert payload["scheduler_lock"]["generation_guarded"] is True
    assert payload["state_model"]["blind_overwrite_allowed"] is False
    assert payload["simulation"]["simulation_model"] == "synchronous_waves"
    assert payload["simulation"]["peak_resource_usage_semantics"] == (
        "synchronous_wave_reference_not_live_capacity_ceiling"
    )
    assert payload["fanout_execution_accounting"]["dry_run_model"] == "candidate_year_proxy"
    assert payload["simulation"]["peak_resource_usage"]["candidate_slots"] <= 20


def test_no_tail_fill_single_task_defers_without_succeeding_candidate() -> None:
    candidate = PipelineTask(
        task_id="candidate:y2021:u000",
        stage="candidate",
        year=2021,
        unit_index=0,
        candidate_id="candidate_0",
        dependencies=(),
        tokens=ResourceTokens(cpu=2, memory_gib=8, candidate_slots=1),
        matrix_id="unit_matrix",
        matrix_uri="gs://unit/matrix",
    )

    simulation = simulate_dry_run_schedule(
        [candidate],
        limits=SchedulerLimits(),
        min_candidate_batch_size=2,
        tail_fill_single_task=False,
        config=None,
        args=_args(tail_fill_single_task=False),
    )

    assert simulation["all_tasks_scheduled"] is False
    assert simulation["deferred_task_ids"] == ["candidate:y2021:u000"]
    assert simulation["terminal_status_counts"] == {"deferred": 1}
    assert simulation["waves"][0]["submitted_task_ids"] == []
    assert simulation["waves"][0]["deferred_task_ids"] == ["candidate:y2021:u000"]
    assert simulation["waves"][0]["resource_usage"] == {"cpu": 0, "memory_gib": 0, "candidate_slots": 0}


class _FakeLease:
    def __init__(self, *, heartbeat_results: list[bool] | None = None):
        self.heartbeat_results = list(heartbeat_results or [])
        self.acquire_calls = 0
        self.heartbeat_calls = 0
        self.release_calls = 0

    def acquire(self) -> bool:
        self.acquire_calls += 1
        return True

    def heartbeat(self) -> bool:
        self.heartbeat_calls += 1
        if self.heartbeat_results:
            return self.heartbeat_results.pop(0)
        return True

    def release(self) -> None:
        self.release_calls += 1


class _FakeCloudRun:
    def __init__(self, *, submit_returncode: int = 0, describe_states: dict[str, list[str]] | None = None):
        self.submit_returncode = submit_returncode
        self.describe_states = {key: list(value) for key, value in (describe_states or {}).items()}
        self.submitted_commands: list[tuple[str, ...]] = []
        self.next_execution_no = 1

    def submit(self, command):
        self.submitted_commands.append(tuple(command))
        execution_id = f"strategy1-train-candidate-fanout-job-{self.next_execution_no}"
        self.next_execution_no += 1
        return CloudRunSubmitResult(
            returncode=self.submit_returncode,
            execution_id=execution_id,
            stdout_tail=f"Execution [{execution_id}]",
        )

    def describe(self, *, project: str, region: str, execution_id: str):
        states = self.describe_states.setdefault(execution_id, ["succeeded"])
        state = states.pop(0) if states else "succeeded"
        if state == "unknown":
            return None
        return {"status": {"conditions": [{"type": "Completed", "status": "True" if state == "succeeded" else "False"}]}}


class _FakeArtifacts:
    def __init__(self, complete_keys: set[str] | None = None, *, matrix_ready: bool = True):
        self.complete_keys = set(complete_keys or set())
        self._matrix_ready = matrix_ready

    def matrix_ready(self, unit: LiveExecutionUnit) -> bool:
        return self._matrix_ready

    def artifact_complete(self, unit: LiveExecutionUnit) -> bool:
        return unit.unit_key in self.complete_keys or all(uri in self.complete_keys for uri in unit.artifact_uris)


class _EventuallyCompleteArtifacts:
    def __init__(self):
        self.calls = 0

    def matrix_ready(self, unit: LiveExecutionUnit) -> bool:
        return True

    def artifact_complete(self, unit: LiveExecutionUnit) -> bool:
        self.calls += 1
        return self.calls > 1


def _config(candidate_count: int = 4) -> RunnerConfig:
    return RunnerConfig(
        project="data-aquarium",
        region="asia-east2",
        output_dataset_role="research",
        artifact_base_uri="gs://ashare-artifacts/reports/strategy1",
        model_artifact_base_uri="gs://ashare-artifacts/models/strategy1",
        lock_bucket="ashare-artifacts",
        lock_prefix="locks/strategy1/cloudrun",
        train_candidate_fanout_job="strategy1-train-candidate-fanout-job",
        training_panel_step="build_training_panel_risk_feature",
        candidate_task_cpu=2,
        candidate_task_memory="8Gi",
        candidate_grid=tuple(
            {"candidate_id": f"candidate_{idx}", "model_family": "lightgbm_regression"}
            for idx in range(candidate_count)
        ),
    )


def _live_plan_and_units(**arg_overrides):
    config = _config()
    values = {
        "dry_run": False,
        "execute_live": True,
        "candidate_only_smoke": True,
        "start_year": 2021,
        "end_year": 2022,
        "smoke_years": [2021],
        "smoke_candidates_per_year": 2,
    }
    values.update(arg_overrides)
    args = _args(**values)
    plan = build_scheduler_plan(config=config, args=args)
    units = candidate_smoke_execution_units(plan=plan, config=config, args=args)
    return config, args, plan, units


def test_gcs_state_generation_conflict_reread_preserves_winner() -> None:
    store = InMemoryGenerationStateStore()
    generation = store.create({"status": "planned"})
    store.update({"status": "running"}, expected_generation=generation)

    with pytest.raises(StateGenerationMismatch):
        store.update({"status": "stale"}, expected_generation=generation)

    payload, current_generation = store.read()
    assert current_generation == generation + 1
    assert payload == {"status": "running"}


def test_live_scheduler_lost_ownership_stops_before_submit() -> None:
    config, args, plan, _ = _live_plan_and_units()
    store = InMemoryGenerationStateStore()
    lease = _FakeLease(heartbeat_results=[False])
    cloud_run = _FakeCloudRun()

    with pytest.raises(LiveSchedulerOwnershipLost, match="lost scheduler lease"):
        execute_candidate_only_live_smoke(
            plan=plan,
            config=config,
            args=args,
            state_store=store,
            lease=lease,
            cloud_run=cloud_run,
            artifact_store=_FakeArtifacts(),
        )

    assert cloud_run.submitted_commands == []
    assert lease.release_calls == 1


def test_live_state_recovery_does_not_resubmit_completed_execution() -> None:
    config, args, plan, units = _live_plan_and_units(smoke_candidates_per_year=1)
    unit = units[0]
    store = InMemoryGenerationStateStore()
    store.create({
        "schema_version": 1,
        "scheduler_run_id": plan["scheduler_run_id"],
        "plan_hash": plan["plan_hash"],
        "units": {
            unit.unit_key: {
                **unit.to_state_seed(),
                "status": "running",
                "execution_id": "strategy1-train-candidate-fanout-job-existing",
            }
        },
    })
    cloud_run = _FakeCloudRun(
        describe_states={"strategy1-train-candidate-fanout-job-existing": ["succeeded"]}
    )

    result = execute_candidate_only_live_smoke(
        plan=plan,
        config=config,
        args=args,
        state_store=store,
        lease=_FakeLease(),
        cloud_run=cloud_run,
        artifact_store=_FakeArtifacts({unit.unit_key}),
    )

    assert cloud_run.submitted_commands == []
    assert result["recovered_execution_count"] == 1
    payload, _ = store.read()
    assert payload["units"][unit.unit_key]["status"] == "succeeded"


def test_live_scheduler_artifact_skip_avoids_submission() -> None:
    config, args, plan, units = _live_plan_and_units(smoke_candidates_per_year=1)
    unit = units[0]
    cloud_run = _FakeCloudRun()

    result = execute_candidate_only_live_smoke(
        plan=plan,
        config=config,
        args=args,
        state_store=InMemoryGenerationStateStore(),
        lease=_FakeLease(),
        cloud_run=cloud_run,
        artifact_store=_FakeArtifacts({unit.unit_key}),
    )

    assert cloud_run.submitted_commands == []
    assert result["skipped_artifact_count"] == 1
    assert result["units"][0]["status"] == "skipped"


def test_live_scheduler_missing_matrix_fails_before_submission() -> None:
    config, args, plan, units = _live_plan_and_units(smoke_candidates_per_year=1)
    unit = units[0]
    cloud_run = _FakeCloudRun()
    store = InMemoryGenerationStateStore()

    result = execute_candidate_only_live_smoke(
        plan=plan,
        config=config,
        args=args,
        state_store=store,
        lease=_FakeLease(),
        cloud_run=cloud_run,
        artifact_store=_FakeArtifacts(matrix_ready=False),
    )

    assert cloud_run.submitted_commands == []
    assert result["failed_execution_count"] == 1
    assert result["units"][0]["action"] == "matrix_missing"
    payload, _ = store.read()
    assert payload["units"][unit.unit_key]["artifact_status"] == "matrix_missing"


def test_live_admission_counts_cloud_run_executions_not_candidate_year_proxy() -> None:
    _, _, plan, units = _live_plan_and_units(smoke_candidates_per_year=2)
    plan["resource_limits"]["active_fanout_executions"] = 1
    state_payload = {
        "units": {
            units[0].unit_key: {
                **units[0].to_state_seed(),
                "status": "running",
                "execution_id": "execution-a",
            }
        }
    }

    assert can_admit_live_execution(units[1], state_payload, plan) is False


def test_describe_success_and_artifact_confirm_success_after_execute_wait_failure() -> None:
    config, args, plan, units = _live_plan_and_units(smoke_candidates_per_year=1)
    unit = units[0]
    cloud_run = _FakeCloudRun(submit_returncode=1)

    result = execute_candidate_only_live_smoke(
        plan=plan,
        config=config,
        args=args,
        state_store=InMemoryGenerationStateStore(),
        lease=_FakeLease(),
        cloud_run=cloud_run,
        artifact_store=_EventuallyCompleteArtifacts(),
    )

    assert result["submitted_execution_count"] == 1
    assert result["failed_execution_count"] == 0
    assert result["units"][0]["status"] == "succeeded"
