from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from quant_ashare.strategy1 import reporting, train_predict


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = "configs/strategy1/oq010_experiments_v0.json"
DEFAULT_EXPERIMENT_ID = "oq010_a0_n5_w20"


def _args(**overrides) -> argparse.Namespace:
    values = {
        "experiment_id": DEFAULT_EXPERIMENT_ID,
        "manifest": DEFAULT_MANIFEST,
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


def test_current_orchestrators_do_not_pass_manifest_resolved_to_backtest_report() -> None:
    searched_roots = [
        REPO_ROOT / "src" / "quant_ashare" / "strategy1",
        REPO_ROOT / "scripts" / "strategy1_cloudrun",
    ]
    allowed = {
        Path("src/quant_ashare/strategy1/train_predict.py"),
        Path("src/quant_ashare/strategy1/reporting.py"),
        Path("src/quant_ashare/strategy1/experiment_resolution.py"),
    }
    offenders = []
    for root in searched_roots:
        for path in sorted(root.rglob("*.py")):
            relative = path.relative_to(REPO_ROOT)
            if relative in allowed:
                continue
            if "--manifest-resolved" in path.read_text(encoding="utf-8"):
                offenders.append(str(relative))

    assert offenders == []
