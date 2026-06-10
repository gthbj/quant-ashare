from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _entrypoint_args(tmp_path: Path) -> dict[str, list[str]]:
    matrix_dir = tmp_path / "matrix"
    matrix_dir.mkdir()
    (matrix_dir / "work_units.json").write_text(
        json.dumps({
            "units": [{
                "unit_index": 0,
                "unit_id": "candidate=unit",
                "unit_type": "candidate_train",
                "candidate_id": "unit",
                "model_params": {
                    "candidate_id": "unit",
                    "penalty": "l2",
                    "C": 1.0,
                    "l1_ratio": None,
                },
                "output_uri": "gs://unit/candidates/unit_index=0",
                "experiment_id": "oq010_a0_n5_w20",
                "run_id": "s1_bqml_oq010_oq010_a0_n5_w20_20260603_01",
            }],
        }),
        encoding="utf-8",
    )

    refit_exp = {
        "experiment_id": "annual_roll_unit__final_refit",
        "run_id": "unit_run__refit01",
        "prediction_run_id": "unit_run__refit01",
        "backtest_id": "unit_bt__refit01",
        "parent_experiment_id": "annual_roll_unit",
        "parent_run_id": "unit_run",
        "train_start": "2021-01-04",
        "train_end": "2025-12-24",
        "valid_start": "2021-01-04",
        "valid_end": "2025-12-24",
        "test_start": "2026-01-05",
        "test_end": "2026-06-09",
        "predict_start": "2026-01-05",
        "predict_end": "2026-06-09",
    }
    refit_exp_b64 = base64.urlsafe_b64encode(
        json.dumps(refit_exp, sort_keys=True).encode("utf-8")
    ).decode("ascii")
    synthetic_manifest = tmp_path / "synthetic_manifest.json"
    synthetic_manifest.write_text(
        json.dumps(
            {
                "synthetic_run_id": "s1_annual_roll_synth_continuous_unit",
                "years": [
                    {
                        "backtest_year": 2021,
                        "source_run_id": "unit_run__refit01",
                        "predict_start": "2021-01-04",
                        "predict_end": "2021-12-31",
                    },
                    {
                        "backtest_year": 2022,
                        "source_run_id": "unit_run_2022__refit01",
                        "predict_start": "2022-01-04",
                        "predict_end": "2022-12-30",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    return {
        "train_predict": [
            "--dry-run",
            "--experiment-id",
            "oq010_a0_n5_w20",
            "--skip-gcs-upload",
        ],
        "prepare_matrix": [
            "--dry-run",
            "--experiment-id",
            "oq010_a0_n5_w20",
            "--matrix-local-dir",
            str(matrix_dir),
            "--skip-gcs-upload",
        ],
        "train_candidate_task": [
            "--dry-run",
            "--matrix-uri",
            "gs://unit/matrix",
            "--matrix-local-dir",
            str(matrix_dir),
            "--task-index",
            "0",
            "--skip-gcs-upload",
        ],
        "select_register_predict": [
            "--dry-run",
            "--experiment-id",
            "oq010_a0_n5_w20",
            "--matrix-uri",
            "gs://unit/matrix",
            "--matrix-local-dir",
            str(matrix_dir),
            "--skip-gcs-upload",
        ],
        "refit_register_predict": [
            "--dry-run",
            "--experiment-json",
            refit_exp_b64,
            "--source-run-id",
            "unit_run",
            "--source-panel-run-id",
            "unit_run",
            "--refit-train-start",
            "2021-01-04",
            "--refit-train-end",
            "2025-12-24",
            "--skip-gcs-upload",
        ],
        "synthetic_continuous": [
            "--dry-run",
            "--manifest-json",
            str(synthetic_manifest),
            "--require-source-refit",
            "--skip-gcs-upload",
        ],
        "backtest_report": [
            "--dry-run",
            "--experiment-id",
            "oq010_a0_n5_w20",
            "--skip-gcs-upload",
            "--skip-report",
            "--skip-diagnosis",
            "--skip-tail-risk",
            "--skip-qa",
        ],
    }


def _pythonpath_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(REPO_ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}{os.pathsep}{existing}"
    return env


def _run_module(module: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=REPO_ROOT,
        env=_pythonpath_env(),
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


@pytest.mark.parametrize(
    "entrypoint",
    [
        "train_predict",
        "prepare_matrix",
        "train_candidate_task",
        "select_register_predict",
        "refit_register_predict",
        "synthetic_continuous",
        "backtest_report",
    ],
)
def test_package_entrypoint_help_smoke(entrypoint: str) -> None:
    new = _run_module(f"quant_ashare.strategy1.{entrypoint}", ["--help"])

    assert new.returncode == 0, new.stderr
    assert "usage:" in new.stdout


@pytest.mark.parametrize(
    "entrypoint",
    [
        "train_predict",
        "prepare_matrix",
        "train_candidate_task",
        "select_register_predict",
        "refit_register_predict",
        "synthetic_continuous",
        "backtest_report",
    ],
)
def test_package_entrypoint_dry_run_plan_is_json(entrypoint: str, tmp_path: Path) -> None:
    args = _entrypoint_args(tmp_path)[entrypoint]

    new = _run_module(f"quant_ashare.strategy1.{entrypoint}", args)

    assert new.returncode == 0, new.stderr
    assert isinstance(json.loads(new.stdout), dict)
