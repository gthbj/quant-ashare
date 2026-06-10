from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.strategy1_cloudrun.config import RunnerConfig
from quant_ashare.strategy1.annual_pipeline_scheduler import (
    InMemoryGenerationStateStore,
    PipelineTask,
    ResourceTokens,
    SchedulerContext,
    SchedulerLimits,
    StateGenerationMismatch,
    build_scheduler_plan,
    ready_tasks,
    select_admissible_tasks,
    simulate_dry_run_schedule,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


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
    assert plan["stage_tokens"]["diagnostic_backtest"] == {"cpu": 4, "memory_gib": 16, "candidate_slots": 0}

    select_2021 = tasks["select:y2021"]
    assert set(select_2021["dependencies"]) == {f"candidate:y2021:u{idx:03d}" for idx in range(11)}
    assert "select:y2021" not in tasks["panel:y2022"]["dependencies"]
    assert tasks["matrix:y2022"]["dependencies"] == ["panel:y2022"]
    assert tasks["continuous_ledger"]["dependencies"] == ["select:y2021", "select:y2022"]


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


def test_annual_pipeline_scheduler_cli_dry_run_outputs_json() -> None:
    env = os.environ.copy()
    src_path = str(REPO_ROOT / "src")
    env["PYTHONPATH"] = src_path if not env.get("PYTHONPATH") else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "quant_ashare.strategy1.annual_pipeline_scheduler",
            "--start-year",
            "2021",
            "--end-year",
            "2021",
            "--run-version",
            "v20260611_test",
            "--dry-run",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
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
