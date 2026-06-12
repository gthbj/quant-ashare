from __future__ import annotations

import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / "orchestration/workflows/ashare_warehouse_window_refresh.yaml"


def _orchestrate_steps() -> list[dict]:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text())
    main_steps = workflow["main"]["steps"]
    orchestrate = next(step["orchestrate"] for step in main_steps if "orchestrate" in step)
    return orchestrate["try"]["steps"]


def _step_names(steps: list[dict]) -> list[str]:
    return [next(iter(step)) for step in steps]


def test_daily_current_runs_dividend_event_chain_after_market_state_checks() -> None:
    steps = _orchestrate_steps()
    names = _step_names(steps)

    assert names.index("heartbeat_after_market_state_checks") < names.index("branch_corporate_action_event_chain")
    assert names.index("branch_corporate_action_event_chain") < names.index("set_qa_after_window_prefix")

    branch = steps[names.index("branch_corporate_action_event_chain")]["branch_corporate_action_event_chain"]
    assert branch["switch"] == [{"condition": '${warehouse_mode == "daily_current"}', "next": "run_corporate_action_event_chain"}]
    assert branch["next"] == "set_qa_after_window_prefix"


def test_dividend_event_chain_is_local_non_blocking_without_rethrow() -> None:
    steps = _orchestrate_steps()
    names = _step_names(steps)
    event_chain = steps[names.index("run_corporate_action_event_chain")]["run_corporate_action_event_chain"]
    chain_text = json.dumps(event_chain, ensure_ascii=False)

    assert "sql/dwd/12_dwd_stock_dividend_event.sql" in chain_text
    assert "sql/qa/14_corporate_action_event_checks.sql" in chain_text
    assert "windowed_weak_transform.dwd_stock_dividend_event" in chain_text
    assert "windowed_weak_qa.corporate_action_event_checks" in chain_text
    assert "write_corporate_action_failed_task_status" in chain_text
    assert '"status": "failed"' in chain_text
    assert "raise" not in event_chain["except"]
    assert event_chain["next"] == "set_qa_after_window_prefix"


def test_injected_dividend_event_failure_continues_to_finalize_success_contract() -> None:
    steps = _orchestrate_steps()
    names = _step_names(steps)
    event_chain = steps[names.index("run_corporate_action_event_chain")]["run_corporate_action_event_chain"]
    exception_steps = event_chain["except"]["steps"]
    exception_text = json.dumps(exception_steps, ensure_ascii=False)

    assert "write_corporate_action_failed_task_status" in exception_text
    assert '"status": "failed"' in exception_text
    assert event_chain["next"] == "set_qa_after_window_prefix"

    release_success = steps[names.index("release_window_lock_success_call")]["release_window_lock_success_call"]
    assert release_success["next"] == "finalize_pipeline_success"

    finalize_success = steps[names.index("write_pipeline_run_success")]["write_pipeline_run_success"]
    assert finalize_success["args"]["status"] == "success"


def test_dividend_event_chain_not_in_qa_only_or_backfill_paths() -> None:
    text = WORKFLOW_PATH.read_text()

    assert text.count("sql/dwd/12_dwd_stock_dividend_event.sql") == 1
    assert text.count("sql/qa/14_corporate_action_event_checks.sql") == 1
    assert '${warehouse_mode == "daily_current"}' in text
    assert "warehouse_mode == \"backfill\"" not in text
    assert text.index("set_qa_only_prefix") < text.index("run_corporate_action_event_chain")
