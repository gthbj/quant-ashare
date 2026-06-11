from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]


def _pythonpath_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(REPO_ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}{os.pathsep}{existing}"
    return env


def test_true_five_year_refit_dry_run_uses_nominal_window_and_refit_only_steps() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.strategy1_cloudrun.orchestrate_annual_rolling_selection",
            "--dry-run",
            "--start-year",
            "2021",
            "--end-year",
            "2021",
            "--run-version",
            "vunit",
            "--emit-refit-only",
            "--true-five-year-refit",
            "--final-refit-run-suffix",
            "__true5y01",
        ],
        cwd=REPO_ROOT,
        env=_pythonpath_env(),
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr
    plan = json.loads(proc.stdout)
    assert plan["execution_scope"] == "refit_only"
    assert plan["true_five_year_refit"] is True
    assert plan["final_refit_min_training_day"] is None
    year = plan["years"][0]
    assert year["final_refit"]["window_mode"] == "true_five_year_nominal"
    assert year["final_refit"]["effective_final_refit_min_train_start"] is None
    assert year["final_refit"]["train_start"] == "2016-01-04"
    assert year["window_contract"]["nominal_final_refit_train_start"] == "2016-01-01"
    assert year["refit_experiment"]["run_id"].endswith("__true5y01")
    assert [step["step_id"] for step in year["commands"]] == [
        "build_refit_training_panel",
        "cloudrun_refit_register_predict",
    ]
    joined = "\n".join(" ".join(step["command"]) for step in year["commands"])
    assert "--refit-train-start=2016-01-04" in joined
    assert "--source-run-id=s1_annual_roll_y2021_train2015_2019_valid2020_n20_w075_vunit" in joined
    assert "--source-panel-run-id=s1_annual_roll_y2021_train2015_2019_valid2020_n20_w075_vunit__true5y01" in joined


def test_true_five_year_refit_requires_explicit_nondefault_suffix() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.strategy1_cloudrun.orchestrate_annual_rolling_selection",
            "--dry-run",
            "--start-year",
            "2021",
            "--end-year",
            "2021",
            "--run-version",
            "vunit",
            "--true-five-year-refit",
        ],
        cwd=REPO_ROOT,
        env=_pythonpath_env(),
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )

    assert proc.returncode != 0
    assert "requires an explicit non-default --final-refit-run-suffix" in proc.stderr


def test_windowed_stock_equivalence_dry_run_exposes_summary_and_sample_outputs(tmp_path: Path) -> None:
    summary = tmp_path / "stock_summary.jsonl"
    samples = tmp_path / "stock_samples.jsonl"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/qa/run_windowed_refresh_equivalence.py",
            "--dry-run",
            "--summary-output-jsonl",
            str(summary),
            "--diff-sample-output-jsonl",
            str(samples),
            "--max-diff-samples",
            "2",
        ],
        cwd=REPO_ROOT,
        env=_pythonpath_env(),
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr
    assert f"Write per-table mismatch summaries to {summary}" in proc.stdout
    assert f"Write up to 2 mismatch samples per failing table to {samples}" in proc.stdout

    script = (REPO_ROOT / "scripts/qa/run_windowed_refresh_equivalence.py").read_text(encoding="utf-8")
    assert "f AS full_row" in script
    assert "w AS window_row" in script
    assert "diff_sample_json" in script


def test_index_market_equivalence_dry_run_exposes_summary_and_sample_outputs(tmp_path: Path) -> None:
    summary = tmp_path / "index_market_summary.jsonl"
    samples = tmp_path / "index_market_samples.jsonl"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/qa/run_index_market_windowed_equivalence.py",
            "--dry-run",
            "--summary-output-jsonl",
            str(summary),
            "--diff-sample-output-jsonl",
            str(samples),
        ],
        cwd=REPO_ROOT,
        env=_pythonpath_env(),
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr
    assert "sql/incremental/02_refresh_index_dwd_window.sql" in proc.stdout
    assert "sql/incremental/03_refresh_market_state_window.sql" in proc.stdout
    assert f"Write per-table mismatch summaries to {summary}" in proc.stdout
    assert f"Write up to 5 mismatch samples per failing table to {samples}" in proc.stdout


def test_true5y_historical_coverage_sql_pins_repair_window_and_internal_gaps() -> None:
    sql = (REPO_ROOT / "sql/qa/13_true5y_historical_coverage_checks.sql").read_text(encoding="utf-8")

    assert "DATE '2019-01-02'" in sql
    assert "DATE '2019-04-02'" in sql
    assert "not only natural Q1" in sql
    assert "has_full_history_60d" in sql
    assert "COUNTIF(feature_row_count = 0) = 0" in sql
    assert "COUNTIF(trainable_sample_count = 0) = 0" in sql
    assert "valuation_non_null_ratio < p_min_valuation_non_null_ratio" in sql
