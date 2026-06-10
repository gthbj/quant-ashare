from __future__ import annotations

import pytest

from quant_ashare.strategy1.catalog import declared_params, load_step_catalog, repo_path
from quant_ashare.strategy1.sql_render import (
    render_sql_step,
    render_sql_text,
    table_role_replacements,
)
from scripts.strategy1_cloudrun.backtest_report import build_sql_params
from scripts.strategy1_cloudrun.config import Experiment, load_runner_config
from scripts.strategy1_cloudrun.ledger import LEDGER_VERSION_LOT100


def _sql_value_for_type(sql_type: str) -> object:
    values = {
        "ARRAY<INT64>": [1],
        "ARRAY<STRING>": ["unit"],
        "BOOL": True,
        "DATE": "2024-01-02",
        "FLOAT64": 1.0,
        "INT64": 1,
        "STRING": "unit",
        "TIMESTAMP": "2024-01-02T00:00:00Z",
    }
    return values[sql_type]


def _params_for_step_sql(step_cfg: dict[str, object]) -> dict[str, object]:
    sql_path = repo_path(step_cfg.get("sql_path") or step_cfg["target_path"])
    declarations = declared_params(sql_path.read_text(encoding="utf-8"))
    return {
        name: _sql_value_for_type(str(spec["type"]))
        for name, spec in declarations.items()
    }


def _backtest_params() -> dict[str, object]:
    exp = Experiment(
        experiment_id="unit_exp",
        run_id="unit_run",
        prediction_run_id="unit_pred",
        backtest_id="unit_bt",
        predict_start="2024-01-02",
        predict_end="2024-01-31",
    )
    args = type("Args", (), {"lot_size": 100, "min_buy_lot": 1})()
    return build_sql_params(exp, force_replace=True, use_float_ledger=False, args=args)


def test_render_step_requires_declared_runtime_params() -> None:
    with pytest.raises(ValueError, match="missing required SQL params"):
        render_sql_step("build_candidates", {"p_run_id": "unit_run"})


def test_backtest_report_params_render_active_steps_without_example_defaults() -> None:
    params = _backtest_params()

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


def test_default_table_role_rendering_keeps_ads_targets() -> None:
    sql = render_sql_step("build_candidates", _backtest_params())

    assert "`data-aquarium.ashare_ads.ads_model_registry`" in sql
    assert "`data-aquarium.ashare_ads.ads_model_prediction_daily`" in sql
    assert "`data-aquarium.ashare_ads.ads_stock_candidate_daily`" in sql
    assert "data-aquarium.ashare_research" not in sql


def test_research_table_role_rendering_requires_explicit_allow() -> None:
    with pytest.raises(ValueError, match="dataset_role=research is not enabled"):
        render_sql_step("build_candidates", _backtest_params(), dataset_role="research")


def test_research_table_role_rendering_rewrites_step_roles_only() -> None:
    sql = render_sql_step(
        "build_candidates",
        _backtest_params(),
        dataset_role="research",
        allow_future_research=True,
    )

    assert "`data-aquarium.ashare_research.research_model_registry`" in sql
    assert "`data-aquarium.ashare_research.research_model_prediction_daily`" in sql
    assert "`data-aquarium.ashare_research.research_stock_candidate_daily`" in sql
    assert "data-aquarium.ashare_ads.ads_model_registry" not in sql
    assert "data-aquarium.ashare_ads.ads_model_prediction_daily" not in sql
    assert "data-aquarium.ashare_ads.ads_stock_candidate_daily" not in sql
    assert "data-aquarium.ashare_research.research_acceptance_result" not in sql
    assert "`data-aquarium.ashare_dws.dws_stock_universe_daily`" in sql


def test_all_active_steps_render_research_without_ads_residue() -> None:
    catalog = load_step_catalog()

    for step_name, cfg in catalog["steps"].items():
        if cfg.get("status") == "retired":
            continue
        rendered = render_sql_step(
            step_name,
            _params_for_step_sql(cfg),
            catalog=catalog,
            dataset_role="research",
            allow_future_research=True,
        )

        assert "data-aquarium.ashare_ads." not in rendered, step_name


def test_table_role_rendering_handles_meta_dataset_override() -> None:
    replacements = table_role_replacements(
        dataset_role="research",
        allow_future_research=True,
        role_names=["experiment_run_status"],
    )
    sql = render_sql_text(
        "SELECT * FROM `data-aquarium.ashare_meta.strategy1_experiment_run_status`",
        {},
        table_replacements=replacements,
    )

    assert sql == "SELECT * FROM `data-aquarium.ashare_research.research_experiment_run_status`"


def test_table_role_rendering_rewrites_string_literals_for_contract_qa() -> None:
    replacements = table_role_replacements(
        dataset_role="research",
        allow_future_research=True,
        role_names=["training_panel"],
    )
    sql = render_sql_text(
        "SELECT 'data-aquarium.ashare_ads.ads_ml_training_panel_daily'",
        {},
        table_replacements=replacements,
    )

    assert sql == "SELECT 'data-aquarium.ashare_research.research_ml_training_panel_daily'"


def test_global_research_table_role_rendering_rejects_ambiguous_ads_sources() -> None:
    with pytest.raises(ValueError, match="ambiguous table role replacement"):
        table_role_replacements(dataset_role="research", allow_future_research=True)


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


def test_model_diagnosis_pool_qa_uses_explicit_valid_test_windows() -> None:
    sql = repo_path("sql/strategy1/qa/qa_model_diagnosis_outputs.sql").read_text(encoding="utf-8")
    pool5 = sql.split("-- QA-POOL-5:", 1)[1].split("-- QA-POOL-6:", 1)[0]

    assert "tp.trade_date BETWEEN p_valid_start AND p_valid_end" in pool5
    assert "tp.trade_date BETWEEN p_test_start AND p_test_end" in pool5
    assert "s.trade_date BETWEEN p_valid_start AND p_valid_end" in pool5
    assert "s.trade_date BETWEEN p_test_start AND p_test_end" in pool5
    assert "s.trade_date BETWEEN p_valid_start AND p_test_end" not in pool5
