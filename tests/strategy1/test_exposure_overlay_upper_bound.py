from __future__ import annotations

from datetime import date
import math

import pandas as pd

from scripts.strategy1 import simulate_exposure_overlay_upper_bound as sim


def _frame() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=6, freq="B").date
    return pd.DataFrame(
        {
            "trade_date": dates,
            "nav": [1.0, 1.01, 1.02, 1.03, 1.04, 1.05],
            "daily_return": [float("nan"), 0.01, 0.02, -0.03, 0.04, -0.01],
            "is_risk_off": [False, True, True, False, False, False],
            "market_regime": ["risk_on", "risk_off", "risk_off", "neutral", "risk_on", "risk_on"],
            "risk_off_trigger_count": [0, 2, 2, 0, 0, 0],
            "is_limit_down_diffusion": [False, False, False, False, False, False],
            "benchmark_return": [0.0, 0.005, 0.005, -0.01, 0.01, -0.005],
        }
    )


def test_two_state_daily_uses_previous_open_day_signal() -> None:
    frame = sim.prepare_simulation_frame(
        nav=_frame()[["trade_date", "nav", "daily_return"]],
        calendar=pd.DataFrame({"trade_date": _frame()["trade_date"], "trade_date_seq": range(1, 7)}),
        market_state=_frame()[["trade_date", "is_risk_off", "market_regime", "risk_off_trigger_count", "is_limit_down_diffusion"]],
        benchmark=_frame()[["trade_date", "benchmark_return"]],
    )

    exposure = sim.compute_exposure_path(
        frame,
        sim.Variant("unit", "two_state", "daily", 0.3, 0.0),
        rebalance_dates=set(frame["trade_date"]),
    )

    assert exposure.tolist() == [1.0, 1.0, 0.3, 0.3, 1.0, 1.0]


def test_hysteresis_recovers_only_after_previous_day_risk_on() -> None:
    frame = sim.prepare_simulation_frame(
        nav=_frame()[["trade_date", "nav", "daily_return"]],
        calendar=pd.DataFrame({"trade_date": _frame()["trade_date"], "trade_date_seq": range(1, 7)}),
        market_state=_frame()[["trade_date", "is_risk_off", "market_regime", "risk_off_trigger_count", "is_limit_down_diffusion"]],
        benchmark=_frame()[["trade_date", "benchmark_return"]],
    )

    exposure = sim.compute_exposure_path(
        frame,
        sim.Variant("unit", "hysteresis", "daily", 0.5, 0.0),
        rebalance_dates=set(frame["trade_date"]),
    )

    assert exposure.tolist() == [1.0, 1.0, 0.5, 0.5, 0.5, 1.0]


def test_biweekly_timing_changes_only_on_rebalance_dates() -> None:
    frame = sim.prepare_simulation_frame(
        nav=_frame()[["trade_date", "nav", "daily_return"]],
        calendar=pd.DataFrame({"trade_date": _frame()["trade_date"], "trade_date_seq": range(1, 7)}),
        market_state=_frame()[["trade_date", "is_risk_off", "market_regime", "risk_off_trigger_count", "is_limit_down_diffusion"]],
        benchmark=_frame()[["trade_date", "benchmark_return"]],
    )
    rebalance_dates = {frame["trade_date"].iloc[3]}

    exposure = sim.compute_exposure_path(
        frame,
        sim.Variant("unit", "two_state", "biweekly", 0.3, 0.0),
        rebalance_dates=rebalance_dates,
    )

    assert exposure.tolist() == [1.0, 1.0, 1.0, 0.3, 0.3, 0.3]


def test_cost_is_applied_on_exposure_changes() -> None:
    exposure = pd.Series([1.0, 1.0, 0.3, 0.3, 1.0])

    cost = sim.compute_cost_rate(exposure, transaction_cost_bps=20.0)

    assert cost.tolist() == [0.0, 0.0, 0.0014, 0.0, 0.0014]


def test_identity_variant_reproduces_nav_metrics_on_synthetic_frame() -> None:
    raw = _frame()
    frame = sim.prepare_simulation_frame(
        nav=raw[["trade_date", "nav", "daily_return"]],
        calendar=pd.DataFrame({"trade_date": raw["trade_date"], "trade_date_seq": range(1, 7)}),
        market_state=raw[["trade_date", "is_risk_off", "market_regime", "risk_off_trigger_count", "is_limit_down_diffusion"]],
        benchmark=raw[["trade_date", "benchmark_return"]],
    )

    row = sim.simulate_variant(
        frame,
        sim.Variant("baseline_identity", "identity", "daily", 1.0, 0.0),
        rebalance_dates=set(frame["trade_date"]),
    )

    expected_total = math.prod(1.0 + x for x in raw["daily_return"].dropna()) - 1.0
    assert abs(row["total_return"] - expected_total) < 1e-12
    assert row["return_period_count"] == 5
    assert row["exposure_switch_count"] == 0
    assert row["cumulative_cost_drag_pp"] == 0.0


def test_markdown_table_does_not_require_optional_tabulate() -> None:
    table = sim.markdown_table(pd.DataFrame([{"a": 1, "b": 0.123456789}]))

    assert "| a | b |" in table
    assert "0.123457" in table


def test_report_display_columns_keep_detailed_metric_fields() -> None:
    required = {
        "annual_vol",
        "benchmark_total_return",
        "excess_return_vs_000852",
        "max_drawdown_peak_date",
        "max_drawdown_trough_date",
        "crunch_strategy_return",
        "crunch_000852_return",
        "return_period_count",
        "nav_row_count",
    }

    assert required <= set(sim.REPORT_DISPLAY_COLUMNS)


def test_report_calls_out_design_findings_and_metric_caveats() -> None:
    result = pd.DataFrame(
        [
            {
                "variant_id": "baseline_identity",
                "is_identity": True,
                "state_machine": "identity",
                "timing": "daily",
                "e_low": 1.0,
                "transaction_cost_bps": 0.0,
                "total_return": 0.1,
                "compound_annual_return": sim.EXPECTED_BASELINE["compound_annual_return"],
                "annual_vol": 0.2,
                "contract_sharpe": sim.EXPECTED_BASELINE["contract_sharpe"],
                "max_drawdown": sim.EXPECTED_BASELINE["max_drawdown"],
                "calmar_ratio": sim.EXPECTED_BASELINE["calmar_ratio"],
                "benchmark_total_return": 0.02,
                "excess_return_vs_000852": 0.08,
                "information_ratio": 0.36172030078673045,
                "max_drawdown_peak_date": "2023-06-16",
                "max_drawdown_trough_date": "2024-02-07",
                "crunch_strategy_return": -0.37,
                "crunch_000852_return": -0.18,
                "crunch_excess_return_vs_000852": sim.EXPECTED_BASELINE["crunch_excess_return_vs_000852"],
                "average_exposure": 1.0,
                "exposure_lt_1_day_ratio": 0.0,
                "exposure_switch_count": 0,
                "cumulative_cost_drag_pp": 0.0,
                "return_period_count": 1313,
                "nav_row_count": 1314,
            },
            {
                "variant_id": "two_state_biweekly_elow0_cost0bps",
                "is_identity": False,
                "state_machine": "two_state",
                "timing": "biweekly",
                "e_low": 0.0,
                "transaction_cost_bps": 0.0,
                "total_return": 0.2,
                "compound_annual_return": 0.12130091898447448,
                "annual_vol": 0.2019664043864822,
                "contract_sharpe": 0.6005994875878142,
                "max_drawdown": -0.297527701723727,
                "calmar_ratio": 0.4076962188116182,
                "benchmark_total_return": 0.02,
                "excess_return_vs_000852": 0.18,
                "information_ratio": 0.31,
                "max_drawdown_peak_date": "2023-06-16",
                "max_drawdown_trough_date": "2024-09-18",
                "crunch_strategy_return": -0.12,
                "crunch_000852_return": -0.18,
                "crunch_excess_return_vs_000852": 0.06,
                "average_exposure": 0.89,
                "exposure_lt_1_day_ratio": 0.11,
                "exposure_switch_count": 24,
                "cumulative_cost_drag_pp": 0.0,
                "return_period_count": 1313,
                "nav_row_count": 1314,
            },
        ]
    )
    args = type(
        "Args",
        (),
        {
            "backtest_id": "bt",
            "start_date": "2021-01-04",
            "end_date": "2026-06-09",
            "market_state_version": "market_state_v1_20260607",
            "benchmark_sec_code": "000852.SH",
        },
    )()

    report = sim.build_report(result, args, output_csv=sim.Path("result.csv"))

    assert "in-sample selection bias" in report
    assert "hysteresis" in report
    assert "two_state" in report
    assert "0.5420" in report
