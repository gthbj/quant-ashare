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


def test_true5y_historical_coverage_sql_pins_repair_window_and_internal_gaps() -> None:
    sql = (REPO_ROOT / "sql/qa/13_true5y_historical_coverage_checks.sql").read_text(encoding="utf-8")

    assert "DATE '2019-01-02'" in sql
    assert "DATE '2019-04-02'" in sql
    assert "not only natural Q1" in sql
    assert "has_full_history_60d" in sql
    assert "history_obs_60d >= 61" in sql
    assert "COUNT(prior.sec_code)" not in sql
    assert "ods_daily_basic_market_value_open_day_coverage" in sql
    assert "`data-aquarium.ashare_ods.ods_tushare_daily_basic`" in sql
    assert "b.endpoint = 'daily_basic'" in sql
    assert "b.partition_date BETWEEN FORMAT_DATE('%Y%m%d', p_true5y_start)" in sql
    assert "COUNTIF(mv_non_null_row_count = 0) = 0" in sql
    assert "COUNTIF(feature_row_count = 0) = 0" in sql
    assert "COUNTIF(trainable_sample_count = 0) = 0" in sql
    assert "valuation_non_null_ratio < p_min_valuation_non_null_ratio" in sql


def test_windowed_stock_refresh_prev_close_is_not_capped_to_730_days() -> None:
    sql = (REPO_ROOT / "sql/incremental/01_refresh_stock_dwd_dws_window.sql").read_text(encoding="utf-8")

    assert "DATE_SUB(p_dwd_write_start_date, INTERVAL 730 DAY)" not in sql
    assert "trade_date BETWEEN p_write_floor_date AND DATE_SUB(p_dwd_write_start_date, INTERVAL 1 DAY)" in sql


def test_market_state_backfill_reads_full_history_for_sparse_20_row_windows() -> None:
    sql = (REPO_ROOT / "sql/incremental/03_refresh_market_state_window.sql").read_text(encoding="utf-8")

    assert "WHEN p_warehouse_mode = 'backfill' THEN p_write_floor_date" in sql
    assert "p_roll_window_lookback_td" in sql


def test_strategy1_dws_qa_uses_full_history_semantics_not_fixed_start_date() -> None:
    sql = (REPO_ROOT / "sql/qa/02_strategy1_dws_ads_checks.sql").read_text(encoding="utf-8")

    assert "MIN(trade_date) = DATE '2019-04-03'" not in sql
    assert "history_obs_60d < 61" in sql
    assert "COALESCE(has_full_history_60d, TRUE)" in sql
    assert "history_obs_60d >= 61" in sql
    assert "NOT COALESCE(has_full_history_60d, FALSE)" in sql
