from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from quant_ashare.strategy1.catalog import load_step_catalog, repo_path
from quant_ashare.strategy1.sql_render import render_sql_step
from quant_ashare.strategy1.synthetic_continuous import (
    canonical_manifest_sha256,
    default_synthetic_model_id,
    load_synthetic_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


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


def _pythonpath_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(REPO_ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}{os.pathsep}{existing}"
    return env


def test_synthetic_manifest_is_normalized_and_hashed(tmp_path: Path) -> None:
    loaded = load_synthetic_manifest(_manifest(tmp_path / "manifest.json"))

    assert loaded["synthetic_run_id"] == "s1_annual_roll_synth_continuous_unit"
    assert [item.backtest_year for item in loaded["years"]] == [2021, 2022]
    assert canonical_manifest_sha256(loaded) == canonical_manifest_sha256(loaded)
    assert default_synthetic_model_id(loaded["synthetic_run_id"]).startswith("synth_s1_annual_roll")


def test_synthetic_manifest_rejects_overlapping_windows(tmp_path: Path) -> None:
    path = _manifest(tmp_path / "manifest.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["years"][1]["predict_start"] = "2021-12-31"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="non-overlapping"):
        load_synthetic_manifest(path)


def test_synthetic_entrypoint_rejects_ads_output_role_even_in_dry_run(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "manifest.json")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "quant_ashare.strategy1.synthetic_continuous",
            "--dry-run",
            "--manifest-json",
            str(manifest),
            "--output-dataset-role",
            "ads",
        ],
        cwd=REPO_ROOT,
        env=_pythonpath_env(),
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
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
    assert "research_model_prediction_daily" not in sql
