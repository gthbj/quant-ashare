from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from quant_ashare.strategy1.catalog import load_step_catalog, repo_path
from quant_ashare.strategy1.config import experiment_from_b64
from quant_ashare.strategy1.sql_render import render_sql_step
from quant_ashare.strategy1 import synthetic_continuous as synthetic_continuous_module
from quant_ashare.strategy1.synthetic_continuous import (
    YearSlice,
    build_synthetic_backtest_experiment,
    build_year_slices,
    canonical_manifest_sha256,
    default_synthetic_model_id,
    load_synthetic_manifest,
    unify_source_lineage,
    write_synthetic_registry,
)


def _manifest(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "synthetic_run_id": "s1_annual_roll_synth_continuous_unit",
                "years": [
                    {
                        "backtest_year": 2021,
                        "source_run_id": "source_2021__refit01",
                        "predict_start": "2021-01-04",
                        "predict_end": "2021-12-31",
                    },
                    {
                        "backtest_year": 2022,
                        "source_run_id": "source_2022__refit01",
                        "predict_start": "2022-01-04",
                        "predict_end": "2022-12-30",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_synthetic_manifest_is_normalized_and_hashed(tmp_path: Path) -> None:
    loaded = load_synthetic_manifest(_manifest(tmp_path / "manifest.json"))

    assert loaded["synthetic_run_id"] == "s1_annual_roll_synth_continuous_unit"
    assert [item.backtest_year for item in loaded["years"]] == [2021, 2022]
    assert canonical_manifest_sha256(loaded) == canonical_manifest_sha256(loaded)
    assert default_synthetic_model_id(loaded["synthetic_run_id"]).startswith("synth_s1_annual_roll")


def test_synthetic_manifest_accepts_explicit_valid_windows(tmp_path: Path) -> None:
    path = _manifest(tmp_path / "manifest.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["years"][0]["valid_start"] = "2020-01-02"
    raw["years"][0]["valid_end"] = "2020-12-24"
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = load_synthetic_manifest(path)

    assert loaded["years"][0].valid_start.isoformat() == "2020-01-02"
    assert loaded["years"][0].valid_end.isoformat() == "2020-12-24"
    assert canonical_manifest_sha256(loaded) == canonical_manifest_sha256(loaded)


def test_build_year_slices_uses_selection_valid_window_for_refit_source() -> None:
    years = [
        YearSlice(
            backtest_year=2026,
            source_run_id="source_2026__refit01",
            predict_start=date.fromisoformat("2026-01-05"),
            predict_end=date.fromisoformat("2026-06-09"),
        )
    ]
    source_rows = {
        "source_2026__refit01": {
            "source_model_id": "model_2026_refit",
            "source_refit": True,
            "selected_candidate_id": "candidate_a",
            "valid_start_date": "2025-01-02",
            "valid_end_date": "2025-12-24",
        }
    }

    slices = build_year_slices(years, source_rows)

    assert slices[0]["valid_start"] == "2025-01-02"
    assert slices[0]["valid_end"] == "2025-12-24"
    assert slices[0]["predict_start"] == "2026-01-05"


def test_load_source_registry_rows_resolves_refit_valid_window_from_selection_registry(monkeypatch) -> None:
    refit_run_id = "source_2026__refit01"
    selection_run_id = "source_2026"
    calls = []

    def fake_query_dataframe(_client, _sql, _params):
        calls.append(_sql)
        if len(calls) == 1:
            return pd.DataFrame([
                {
                    "source_run_id": refit_run_id,
                    "model_id": "model_2026_refit",
                    "model_family": "lightgbm_regression",
                    "horizon": 5,
                    "feature_version": "strategy1_pv_v0_20260601",
                    "label_version": "open_to_close_h1_5_10_20_v20260601",
                    "preprocess_version": "tree_winsor_missing_passthrough_v1",
                    "train_start_date": date.fromisoformat("2021-01-04"),
                    "train_end_date": date.fromisoformat("2025-12-24"),
                    "valid_start_date": date.fromisoformat("2021-01-04"),
                    "valid_end_date": date.fromisoformat("2025-12-24"),
                    "test_start_date": date.fromisoformat("2026-01-05"),
                    "test_end_date": date.fromisoformat("2026-06-09"),
                    "model_params_json": json.dumps({
                        "run_id": refit_run_id,
                        "source_run_id": selection_run_id,
                        "refit": True,
                        "candidate_id": "candidate_a",
                    }),
                    "metrics_json": json.dumps({"selected_candidate_id": "candidate_a"}),
                    "model_uri": "gs://unit/model",
                    "artifact_uri": "gs://unit/artifact",
                    "created_at": "2026-06-11T00:00:00Z",
                }
            ])
        return pd.DataFrame([
            {
                "source_selection_run_id": selection_run_id,
                "valid_start_date": date.fromisoformat("2025-01-02"),
                "valid_end_date": date.fromisoformat("2025-12-24"),
                "created_at": "2026-06-10T00:00:00Z",
            }
        ])

    monkeypatch.setattr(synthetic_continuous_module, "query_dataframe", fake_query_dataframe)

    rows = synthetic_continuous_module.load_source_registry_rows(
        client=object(),
        config=SimpleNamespace(strategy_id="ml_pv_clf_v0"),
        registry_table="unit.registry",
        years=[
            YearSlice(
                backtest_year=2026,
                source_run_id=refit_run_id,
                predict_start=date.fromisoformat("2026-01-05"),
                predict_end=date.fromisoformat("2026-06-09"),
            )
        ],
        require_source_refit=True,
    )

    assert rows[refit_run_id]["valid_start_date"] == "2025-01-02"
    assert rows[refit_run_id]["valid_end_date"] == "2025-12-24"
    assert rows[refit_run_id]["source_selection_run_id"] == selection_run_id
    assert len(calls) == 2


def test_load_source_registry_rows_rejects_refit_without_selection_lineage(monkeypatch) -> None:
    refit_run_id = "source_2026__refit01"

    def fake_query_dataframe(_client, _sql, _params):
        return pd.DataFrame([
            {
                "source_run_id": refit_run_id,
                "model_id": "model_2026_refit",
                "model_family": "lightgbm_regression",
                "horizon": 5,
                "feature_version": "strategy1_pv_v0_20260601",
                "label_version": "open_to_close_h1_5_10_20_v20260601",
                "preprocess_version": "tree_winsor_missing_passthrough_v1",
                "train_start_date": date.fromisoformat("2021-01-04"),
                "train_end_date": date.fromisoformat("2025-12-24"),
                "valid_start_date": date.fromisoformat("2021-01-04"),
                "valid_end_date": date.fromisoformat("2025-12-24"),
                "test_start_date": date.fromisoformat("2026-01-05"),
                "test_end_date": date.fromisoformat("2026-06-09"),
                "model_params_json": json.dumps({
                    "run_id": refit_run_id,
                    "refit": True,
                    "candidate_id": "candidate_a",
                }),
                "metrics_json": json.dumps({"selected_candidate_id": "candidate_a"}),
                "model_uri": "gs://unit/model",
                "artifact_uri": "gs://unit/artifact",
                "created_at": "2026-06-11T00:00:00Z",
            }
        ])

    monkeypatch.setattr(synthetic_continuous_module, "query_dataframe", fake_query_dataframe)

    with pytest.raises(RuntimeError, match="model_params_json.source_run_id"):
        synthetic_continuous_module.load_source_registry_rows(
            client=object(),
            config=SimpleNamespace(strategy_id="ml_pv_clf_v0"),
            registry_table="unit.registry",
            years=[
                YearSlice(
                    backtest_year=2026,
                    source_run_id=refit_run_id,
                    predict_start=date.fromisoformat("2026-01-05"),
                    predict_end=date.fromisoformat("2026-06-09"),
                )
            ],
            require_source_refit=True,
        )


def test_synthetic_manifest_rejects_overlapping_windows(tmp_path: Path) -> None:
    path = _manifest(tmp_path / "manifest.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["years"][1]["predict_start"] = "2021-12-31"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="non-overlapping"):
        load_synthetic_manifest(path)


def test_synthetic_entrypoint_rejects_ads_output_role_even_in_dry_run(tmp_path: Path, run_module) -> None:
    manifest = _manifest(tmp_path / "manifest.json")

    proc = run_module(
        "quant_ashare.strategy1.synthetic_continuous",
        [
            "--dry-run",
            "--manifest-json",
            str(manifest),
            "--output-dataset-role",
            "ads",
        ],
    )

    assert proc.returncode != 0
    assert "research-only" in proc.stderr


def test_continuous_qa_catalog_contract_and_research_rendering() -> None:
    catalog = load_step_catalog()
    step = catalog["steps"]["qa_continuous_backtest_outputs"]

    assert step["execution_mode"] == "manual_continuous_qa"
    assert "quant_ashare.strategy1.synthetic_continuous" in step["caller"]
    assert set(step["inputs"]) >= {
        "model_registry",
        "model_prediction_daily",
        "backtest_summary",
        "backtest_nav_daily",
        "backtest_ledger_state_daily",
    }
    rendered = render_sql_step(
        "qa_continuous_backtest_outputs",
        {
            "p_run_id": "unit_synth",
            "p_prediction_run_id": "unit_synth",
            "p_strategy_id": "ml_pv_clf_v0",
            "p_backtest_id": "unit_bt",
            "p_synthetic_model_id": "unit_model",
            "p_predict_start": "2021-01-04",
            "p_predict_end": "2026-06-09",
            "p_expected_year_count": 6,
            "p_manifest_sha256": "unit_sha",
            "p_require_source_refit": True,
            "p_expected_ledger_version": "ledger_exec_v1_lot100",
            "p_resume_policy_id": "cloudrun_lot100_resume_v1",
        },
        dataset_role="research",
        allow_future_research=True,
    )

    assert "data-aquarium.ashare_ads." not in rendered
    assert "data-aquarium.ashare_research.research_model_prediction_daily" in rendered
    assert "QA-CONT-4: synthetic prediction row count" in rendered


def test_continuous_qa_sql_documents_default_path_exclusions() -> None:
    sql = repo_path("sql/strategy1/qa/qa_continuous_backtest_outputs.sql").read_text(encoding="utf-8")

    assert "JSON_QUERY_ARRAY(reg.metrics_json, '$.year_slices')" in sql
    assert "p_require_source_refit" in sql
    assert "pred.predict_date BETWEEN p_predict_start AND p_predict_end" in sql
    assert "pred.predict_date BETWEEN m.predict_start AND m.predict_end" in sql
    assert "research_model_prediction_daily" not in sql


# --- Part A: source-derived lineage + fail-fast -----------------------------------------


def _years(n: int = 2) -> list[YearSlice]:
    base = []
    for offset in range(n):
        year = 2021 + offset
        base.append(
            YearSlice(
                backtest_year=year,
                source_run_id=f"source_{year}__refit01",
                predict_start=date.fromisoformat(f"{year}-01-04"),
                predict_end=date.fromisoformat(f"{year}-12-30"),
            )
        )
    return base


def _source_row(
    *,
    label_horizon: int = 5,
    feature_set_id: str | None = "strategy1_pv_fin_risk_v0_20260606",
    feature_version: str | None = "strategy1_pv_v0_20260601",
    weight_version: str = "constant_1p0_v0",
) -> dict:
    return {
        "source_model_id": "model_x",
        "source_refit": True,
        "selected_candidate_id": "candidate_a",
        "horizon": label_horizon,
        "label_horizon": label_horizon,
        "feature_set_id": feature_set_id,
        "feature_version": feature_version,
        "weight_version": weight_version,
        "valid_start_date": "2020-01-02",
        "valid_end_date": "2020-12-24",
    }


def test_unify_source_lineage_returns_unique_values_when_consistent() -> None:
    years = _years(2)
    source_rows = {item.source_run_id: _source_row() for item in years}

    lineage = unify_source_lineage(years, source_rows)

    assert lineage == {
        "label_horizon": 5,
        "feature_set_id": "strategy1_pv_fin_risk_v0_20260606",
        "feature_version": "strategy1_pv_v0_20260601",
        "weight_version": "constant_1p0_v0",
    }


def test_unify_source_lineage_fail_fast_on_inconsistent_horizon() -> None:
    years = _years(2)
    source_rows = {
        years[0].source_run_id: _source_row(label_horizon=5),
        years[1].source_run_id: _source_row(label_horizon=20),
    }

    with pytest.raises(RuntimeError, match="disagree on label_horizon") as exc:
        unify_source_lineage(years, source_rows)
    message = str(exc.value)
    assert "source_2021__refit01=5" in message
    assert "source_2022__refit01=20" in message


def test_unify_source_lineage_fail_fast_on_inconsistent_weight_version() -> None:
    years = _years(2)
    source_rows = {
        years[0].source_run_id: _source_row(weight_version="constant_1p0_v0"),
        years[1].source_run_id: _source_row(weight_version="logmv_xs_monotone_v0"),
    }

    with pytest.raises(RuntimeError, match="disagree on weight_version"):
        unify_source_lineage(years, source_rows)


def test_unify_source_lineage_fail_fast_when_feature_set_id_missing() -> None:
    years = _years(1)
    source_rows = {years[0].source_run_id: _source_row(feature_set_id=None)}

    with pytest.raises(RuntimeError, match="missing required lineage fields"):
        unify_source_lineage(years, source_rows)


def test_load_source_registry_rows_defaults_missing_weight_version(monkeypatch) -> None:
    refit_run_id = "source_2026__refit01"
    selection_run_id = "source_2026"

    def fake_query_dataframe(_client, _sql, _params):
        if "source_selection_run_id" in _sql:
            return pd.DataFrame([
                {
                    "source_selection_run_id": selection_run_id,
                    "valid_start_date": date.fromisoformat("2025-01-02"),
                    "valid_end_date": date.fromisoformat("2025-12-24"),
                    "created_at": "2026-06-10T00:00:00Z",
                }
            ])
        return pd.DataFrame([
            {
                "source_run_id": refit_run_id,
                "model_id": "model_2026_refit",
                "model_family": "lightgbm_regression",
                "horizon": 5,
                "feature_version": "strategy1_pv_v0_20260601",
                "label_version": "open_to_close_h1_5_10_20_v20260601",
                "preprocess_version": "tree_winsor_missing_passthrough_v1",
                "train_start_date": date.fromisoformat("2021-01-04"),
                "train_end_date": date.fromisoformat("2025-12-24"),
                "valid_start_date": date.fromisoformat("2021-01-04"),
                "valid_end_date": date.fromisoformat("2025-12-24"),
                "test_start_date": date.fromisoformat("2026-01-05"),
                "test_end_date": date.fromisoformat("2026-06-09"),
                "model_params_json": json.dumps({
                    "run_id": refit_run_id,
                    "source_run_id": selection_run_id,
                    "refit": True,
                    "candidate_id": "candidate_a",
                    "label_horizon": 5,
                    "feature_set_id": "strategy1_pv_fin_risk_v0_20260606",
                    # 旧 source 行无 weight_version 键
                }),
                "metrics_json": json.dumps({"selected_candidate_id": "candidate_a"}),
                "model_uri": "gs://unit/model",
                "artifact_uri": "gs://unit/artifact",
                "created_at": "2026-06-11T00:00:00Z",
                "params_feature_set_id": "strategy1_pv_fin_risk_v0_20260606",
                "params_label_horizon": "5",
                "params_weight_version": None,
            }
        ])

    monkeypatch.setattr(synthetic_continuous_module, "query_dataframe", fake_query_dataframe)

    rows = synthetic_continuous_module.load_source_registry_rows(
        client=object(),
        config=SimpleNamespace(strategy_id="ml_pv_clf_v0"),
        registry_table="unit.registry",
        years=[
            YearSlice(
                backtest_year=2026,
                source_run_id=refit_run_id,
                predict_start=date.fromisoformat("2026-01-05"),
                predict_end=date.fromisoformat("2026-06-09"),
            )
        ],
        require_source_refit=True,
    )

    row = rows[refit_run_id]
    assert row["weight_version"] == "constant_1p0_v0"
    assert row["label_horizon"] == 5
    assert row["feature_set_id"] == "strategy1_pv_fin_risk_v0_20260606"
    assert row["feature_version"] == "strategy1_pv_v0_20260601"


def _capture_synthetic_registry(monkeypatch, year_slices, source_lineage) -> dict:
    captured: dict = {}

    def fake_load_dataframe(_client, frame, _table):
        captured["frame"] = frame.copy()

    monkeypatch.setattr(synthetic_continuous_module, "load_dataframe", fake_load_dataframe)
    monkeypatch.setattr(synthetic_continuous_module, "get_git_commit", lambda: "deadbeef")

    write_synthetic_registry(
        client=object(),
        config=SimpleNamespace(strategy_id="ml_pv_clf_v0"),
        registry_table="unit.registry",
        synthetic_run_id="s1_synth_unit",
        synthetic_model_id="synth_s1_synth_unit",
        artifact_uri="gs://unit/artifact",
        manifest_uri="gs://unit/manifest.json",
        input_manifest_sha256="input_sha",
        resolved_manifest_sha256="resolved_sha",
        year_slices=year_slices,
        source_lineage=source_lineage,
        require_source_refit=True,
        predict_start=date.fromisoformat("2021-01-04"),
        predict_end=date.fromisoformat("2026-06-09"),
    )
    row = captured["frame"].iloc[0]
    return {
        "horizon": row["horizon"],
        "feature_version": row["feature_version"],
        "model_params_json": row["model_params_json"],
        "metrics_json": row["metrics_json"],
    }


def test_v1_lineage_synthetic_registry_is_byte_identical_to_legacy_hardcode(monkeypatch) -> None:
    years = _years(2)
    source_rows = {item.source_run_id: _source_row() for item in years}
    year_slices = build_year_slices(years, source_rows)

    v1_lineage = {
        "label_horizon": 5,
        "feature_set_id": "strategy1_pv_fin_risk_v0_20260606",
        "feature_version": "strategy1_pv_v0_20260601",
        "weight_version": "constant_1p0_v0",
    }
    out = _capture_synthetic_registry(monkeypatch, year_slices, v1_lineage)

    # 旧硬编码：frame horizon=5 / feature_version=strategy1_pv_v0_20260601；
    # params_json label_horizon=5 / feature_set_id=strategy1_pv_fin_risk_v0_20260606，无 weight_version 键。
    assert int(out["horizon"]) == 5
    assert out["feature_version"] == "strategy1_pv_v0_20260601"
    params = json.loads(out["model_params_json"])
    assert params["label_horizon"] == 5
    assert params["feature_set_id"] == "strategy1_pv_fin_risk_v0_20260606"
    assert params["tail_risk_profile_id"] == "diagnostic_only"
    assert "weight_version" not in params  # v1 等价 weight_version 不写入，保持字节级不变
    metrics = json.loads(out["metrics_json"])
    assert metrics["diagnostic_only"] is False


def test_largecap_lineage_synthetic_registry_carries_derived_values(monkeypatch) -> None:
    years = _years(2)
    largecap_lineage = {
        "label_horizon": 20,
        "feature_set_id": "strategy1_pv_fin_quality_v0_20260603",
        "feature_version": "strategy1_pv_v0_20260601",
        "weight_version": "logmv_xs_monotone_v0",
    }
    source_rows = {
        item.source_run_id: _source_row(
            label_horizon=20,
            feature_set_id="strategy1_pv_fin_quality_v0_20260603",
            weight_version="logmv_xs_monotone_v0",
        )
        for item in years
    }
    year_slices = build_year_slices(years, source_rows)
    out = _capture_synthetic_registry(monkeypatch, year_slices, largecap_lineage)

    assert int(out["horizon"]) == 20
    assert out["feature_version"] == "strategy1_pv_v0_20260601"
    params = json.loads(out["model_params_json"])
    assert params["label_horizon"] == 20
    assert params["feature_set_id"] == "strategy1_pv_fin_quality_v0_20260603"
    assert params["weight_version"] == "logmv_xs_monotone_v0"


# --- Part B: CA-on backtest Experiment payload ------------------------------------------


def test_build_synthetic_backtest_experiment_carries_ca_on() -> None:
    lineage = {
        "label_horizon": 20,
        "feature_set_id": "strategy1_pv_fin_quality_v0_20260603",
        "feature_version": "strategy1_pv_v0_20260601",
        "weight_version": "logmv_xs_monotone_v0",
    }
    exp = build_synthetic_backtest_experiment(
        synthetic_run_id="s1_synth_largecap",
        backtest_id="bt_s1_synth_largecap_ca01",
        predict_start="2021-01-04",
        predict_end="2026-06-09",
        source_lineage=lineage,
    )

    assert exp.run_id == "s1_synth_largecap"
    assert exp.prediction_run_id == "s1_synth_largecap"
    assert exp.backtest_id == "bt_s1_synth_largecap_ca01"
    assert exp.corporate_actions == "cash_div_and_split_v1"
    assert exp.dividend_tax_mode == "flat_10pct"
    assert exp.tail_risk_profile_id == "diagnostic_only"
    assert exp.label_horizon == 20
    assert exp.feature_set_id == "strategy1_pv_fin_quality_v0_20260603"
    assert exp.feature_version == "strategy1_pv_v0_20260601"
    assert exp.weight_version == "logmv_xs_monotone_v0"
    assert exp.horizon_natural_frequency == "monthly"
    assert exp.requires_retrain is False
    assert exp.initial_state_mode == "fresh"
    assert exp.predict_start == "2021-01-04"
    assert exp.predict_end == "2026-06-09"


def test_synthetic_backtest_payload_roundtrips_through_experiment_from_b64() -> None:
    lineage = {
        "label_horizon": 5,
        "feature_set_id": "strategy1_pv_fin_risk_v0_20260606",
        "feature_version": "strategy1_pv_v0_20260601",
        "weight_version": "constant_1p0_v0",
    }
    exp = build_synthetic_backtest_experiment(
        synthetic_run_id="s1_synth_v1",
        backtest_id="bt_s1_synth_v1_ca01",
        predict_start="2021-01-04",
        predict_end="2026-06-09",
        source_lineage=lineage,
    )
    decoded = experiment_from_b64(synthetic_continuous_module.experiment_to_b64(exp))

    # CLI override 在 --experiment-json 路径下不生效，故 CA-on 必须在 payload 内随往返保留。
    assert decoded.corporate_actions == "cash_div_and_split_v1"
    assert decoded.dividend_tax_mode == "flat_10pct"
    assert decoded.prediction_run_id == "s1_synth_v1"
    assert decoded.backtest_id == "bt_s1_synth_v1_ca01"
    assert decoded.is_executable
