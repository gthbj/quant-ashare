from __future__ import annotations

from datetime import date
import math

import pandas as pd

from scripts.strategy1 import analyze_official_adj_leak as leak


def test_nav_from_returns_preserves_initial_nav_and_skips_first_nan() -> None:
    nav = leak.nav_from_returns(pd.Series([float("nan"), 0.10, -0.05]), initial_nav=1.0)

    assert nav.tolist() == [1.0, 1.1, 1.045]


def test_compute_performance_metrics_uses_n_minus_one_return_periods() -> None:
    daily = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]).date,
            "daily_return": [float("nan"), 0.10, -0.05],
            "corrected_daily_return": [float("nan"), 0.12, -0.02],
            "nav": [1.0, 1.1, 1.045],
            "corrected_nav": [1.0, 1.12, 1.0976],
            "benchmark_return_effective": [0.0, 0.01, -0.01],
        }
    )
    spec = leak.BacktestSpec("unit", "bt")

    row = leak.compute_performance_metrics(
        daily,
        return_col="daily_return",
        nav_col="nav",
        variant="before",
        spec=spec,
    )

    assert row["return_period_count"] == 2
    assert math.isclose(row["total_return"], 0.045)
    assert row["max_drawdown_peak_date"] == "2024-01-03"
    assert row["max_drawdown_trough_date"] == "2024-01-04"


def test_event_frame_classifies_large_factor_jump_as_bonus_split() -> None:
    contributions = pd.DataFrame(
        {
            "trade_date": [date(2024, 1, 2), date(2024, 1, 3)],
            "prev_trade_date": [date(2024, 1, 1), date(2024, 1, 2)],
            "sec_code": ["000001.SZ", "000002.SZ"],
            "factor_jump": [0.25, 0.01],
            "leak_contribution": [0.002, 0.001],
            "prev_weight": [0.04, 0.05],
            "raw_return": [-0.20, -0.01],
            "hfq_return": [0.05, 0.01],
            "raw_close": [8.0, 9.9],
            "close_hfq": [10.5, 10.1],
            "adj_factor": [1.31, 1.02],
        }
    )

    events = leak.build_event_frame(contributions, leak.BacktestSpec("unit", "bt"))

    assert events["event_type"].tolist() == [
        "bonus_split_type_abs_factor_jump_gt_20pct",
        "dividend_or_small_event_type",
    ]
    assert events["leak_contribution_pp"].tolist() == [0.2, 0.1]


def test_no_trade_residual_validation_passes_small_residual() -> None:
    daily = pd.DataFrame(
        {
            "trade_date": [date(2024, 1, 2), date(2024, 1, 3)],
            "daily_return": [float("nan"), 0.03],
            "raw_replication_return": [0.0, 0.0300000001],
            "residual_raw_replication": [float("nan"), -1e-10],
            "filled_trade_count": [0, 0],
        }
    )

    leak.validate_no_trade_residuals(daily, leak.BacktestSpec("unit", "bt"), tolerance=1e-6)


def test_no_trade_residual_validation_fails_large_residual() -> None:
    daily = pd.DataFrame(
        {
            "trade_date": [date(2024, 1, 2), date(2024, 1, 3)],
            "daily_return": [float("nan"), 0.03],
            "raw_replication_return": [0.0, 0.01],
            "residual_raw_replication": [float("nan"), 0.02],
            "filled_trade_count": [0, 0],
            "prev_weight_sum": [0.0, 0.5],
            "held_position_count": [0, 10],
        }
    )

    try:
        leak.validate_no_trade_residuals(daily, leak.BacktestSpec("unit", "bt"), tolerance=1e-6)
    except RuntimeError as exc:
        assert "raw-return residual check failed" in str(exc)
    else:
        raise AssertionError("expected residual validation failure")


def test_preregistered_verdict_uses_true5y_delta_thresholds() -> None:
    assert "建议立 PRD" in leak.preregistered_verdict(pd.Series({"cagr": 0.0101, "calmar": 0.0}))
    assert "建议立 PRD" in leak.preregistered_verdict(pd.Series({"cagr": 0.0, "calmar": 0.0501}))
    assert "维持约定" in leak.preregistered_verdict(pd.Series({"cagr": 0.004, "calmar": 0.02}))
