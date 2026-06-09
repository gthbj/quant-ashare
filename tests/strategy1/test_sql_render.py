from __future__ import annotations

import pytest

from quant_ashare.strategy1.sql_render import render_sql_step
from scripts.strategy1_cloudrun.backtest_report import build_sql_params
from scripts.strategy1_cloudrun.config import Experiment, load_runner_config
from scripts.strategy1_cloudrun.ledger import LEDGER_VERSION_LOT100


def test_render_step_requires_declared_runtime_params() -> None:
    with pytest.raises(ValueError, match="missing required SQL params"):
        render_sql_step("build_candidates", {"p_run_id": "unit_run"})


def test_backtest_report_params_render_active_steps_without_example_defaults() -> None:
    exp = Experiment(
        experiment_id="unit_exp",
        run_id="unit_run",
        prediction_run_id="unit_pred",
        backtest_id="unit_bt",
        predict_start="2024-01-02",
        predict_end="2024-01-31",
    )
    args = type("Args", (), {"lot_size": 100, "min_buy_lot": 1})()
    params = build_sql_params(exp, force_replace=True, use_float_ledger=False, args=args)

    sql = render_sql_step("build_candidates", params)

    assert "unit_run" in sql
    assert "s1_bqml_livepool_oriented_20260603_01" not in sql


def test_config_maps_legacy_training_panel_sql_to_step(tmp_path) -> None:
    cfg = tmp_path / "runner.yml"
    cfg.write_text(
        "training_panel_sql: sql/cloudrun/strategy1/01_build_training_panel.sql\n",
        encoding="utf-8",
    )

    loaded = load_runner_config(cfg)

    assert loaded.training_panel_step == "build_training_panel_risk_feature"


def test_lot_aware_qa_params_include_min_buy_shares() -> None:
    exp = Experiment(
        experiment_id="unit_exp",
        run_id="unit_run",
        prediction_run_id="unit_pred",
        backtest_id="unit_bt",
    )
    args = type("Args", (), {"lot_size": 100, "min_buy_lot": 1})()
    params = build_sql_params(exp, force_replace=False, use_float_ledger=False, args=args)

    rendered = render_sql_step("qa_lot_aware_ledger_outputs", params)

    assert "DECLARE p_min_buy_shares INT64 DEFAULT 100;" in rendered
    assert LEDGER_VERSION_LOT100 in rendered

