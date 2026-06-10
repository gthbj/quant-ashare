from __future__ import annotations

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
        "backtest_report",
    ],
)
def test_old_and_package_entrypoint_help_match(entrypoint: str) -> None:
    old = _run_module(f"scripts.strategy1_cloudrun.{entrypoint}", ["--help"])
    new = _run_module(f"quant_ashare.strategy1.{entrypoint}", ["--help"])

    assert old.returncode == 0, old.stderr
    assert new.returncode == 0, new.stderr
    assert old.stdout == new.stdout


@pytest.mark.parametrize(
    "entrypoint",
    [
        "train_predict",
        "prepare_matrix",
        "train_candidate_task",
        "select_register_predict",
        "backtest_report",
    ],
)
def test_old_and_package_entrypoint_dry_run_plans_match(entrypoint: str, tmp_path: Path) -> None:
    args = _entrypoint_args(tmp_path)[entrypoint]

    old = _run_module(f"scripts.strategy1_cloudrun.{entrypoint}", args)
    new = _run_module(f"quant_ashare.strategy1.{entrypoint}", args)

    assert old.returncode == 0, old.stderr
    assert new.returncode == 0, new.stderr
    assert json.loads(old.stdout) == json.loads(new.stdout)
