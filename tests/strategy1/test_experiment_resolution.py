from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pytest

from quant_ashare.strategy1 import reporting, train_predict
from scripts.strategy1_cloudrun.config import Experiment, experiment_to_b64


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "configs/strategy1/oq010_experiments_v0.json"
DEFAULT_EXPERIMENT_ID = "oq010_a0_n5_w20"


def _args(**overrides) -> argparse.Namespace:
    values = {
        "experiment_id": DEFAULT_EXPERIMENT_ID,
        "manifest": str(DEFAULT_MANIFEST),
        "manifest_resolved": None,
        "experiment_json": None,
        "run_id": None,
        "prediction_run_id": None,
        "backtest_id": None,
        "initial_state_mode": None,
        "parent_backtest_id": None,
        "state_as_of_date": None,
        "resume_policy_id": None,
        "rebalance_anchor_start": None,
        "corporate_actions": None,
        "dividend_tax_mode": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_train_predict_resolved_manifest_preserves_legacy_override_semantics(tmp_path: Path) -> None:
    resolved_path = tmp_path / "resolved.json"
    resolved_path.write_text(
        json.dumps(
            {
                "experiments": [
                    {
                        "experiment_id": DEFAULT_EXPERIMENT_ID,
                        "run_id": "resolved_run",
                        "prediction_run_id": "resolved_prediction",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    exp = train_predict.resolve_experiment(_args(manifest_resolved=str(resolved_path)))

    assert exp.experiment_id == DEFAULT_EXPERIMENT_ID
    assert exp.run_id == "resolved_run"
    assert exp.prediction_run_id == "resolved_prediction"


def test_reporting_manifest_resolved_fails_fast(tmp_path: Path) -> None:
    resolved_path = tmp_path / "resolved.json"
    resolved_path.write_text(json.dumps({"experiments": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="backtest_report does not support --manifest-resolved"):
        reporting.resolve_experiment(_args(manifest_resolved=str(resolved_path)))


def test_reporting_experiment_json_keeps_priority_over_manifest_resolved(tmp_path: Path) -> None:
    resolved_path = tmp_path / "resolved.json"
    resolved_path.write_text(json.dumps({"experiments": []}), encoding="utf-8")
    exp = Experiment(
        experiment_id="json_exp",
        run_id="json_run",
        prediction_run_id="json_prediction",
        backtest_id="json_backtest",
        requires_retrain=False,
        status="planned",
    )

    resolved = reporting.resolve_experiment(
        _args(
            experiment_id="json_exp",
            experiment_json=experiment_to_b64(exp),
            manifest_resolved=str(resolved_path),
        )
    )

    assert resolved.experiment_id == "json_exp"
    assert resolved.run_id == "json_run"
    assert resolved.prediction_run_id == "json_prediction"
    assert resolved.backtest_id == "json_backtest"


def test_reporting_manifest_cli_overrides_are_still_applied() -> None:
    exp = reporting.resolve_experiment(
        _args(
            run_id="override_run",
            prediction_run_id="override_prediction",
            backtest_id="override_backtest",
            corporate_actions="cash_dividend_and_split_v1",
            dividend_tax_mode="flat_10pct",
        )
    )

    assert exp.run_id == "override_run"
    assert exp.prediction_run_id == "override_prediction"
    assert exp.backtest_id == "override_backtest"
    assert exp.corporate_actions == "cash_dividend_and_split_v1"
    assert exp.dividend_tax_mode == "flat_10pct"


def test_current_backtest_report_command_builders_do_not_pass_manifest_resolved() -> None:
    builder_files = [
        REPO_ROOT / "src/quant_ashare/strategy1/pipeline_control.py",
        REPO_ROOT / "src/quant_ashare/strategy1/annual_pipeline_scheduler.py",
        REPO_ROOT / "src/quant_ashare/strategy1/tail_risk_overlay_ab.py",
        REPO_ROOT / "scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py",
        REPO_ROOT / "scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py",
    ]
    offenders = []
    for path in builder_files:
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"quant_ashare\.strategy1\.backtest_report", text):
            snippet = text[max(0, match.start() - 800):match.end() + 1200]
            if "--manifest-resolved" in snippet:
                offenders.append(str(path.relative_to(REPO_ROOT)))

    assert offenders == []
