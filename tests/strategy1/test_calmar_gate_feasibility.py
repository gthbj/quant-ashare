from __future__ import annotations

import math

import pandas as pd

from scripts.strategy1 import analyze_calmar_gate_feasibility as analysis
from scripts.strategy1 import replay_acceptance_gate_v3 as replay_v3


def test_nav_stats_reuses_v3_replay_metric_semantics() -> None:
    nav = pd.DataFrame(
        {
            "trade_date": pd.date_range("2024-01-02", periods=5, freq="B").date,
            "nav_value": [1.0, 1.1, 1.045, 1.1495, 1.207],
            "daily_return": [math.nan, 0.10, -0.05, 0.10, 0.05002174858634187],
        }
    )

    row = analysis.nav_stats(nav)
    total_return, periods = replay_v3.total_return_from_nav(nav)
    expected_growth = replay_v3.compound_annualized_return(total_return, periods)
    expected_vol = replay_v3.annualized_volatility_from_daily_returns(nav["daily_return"])
    expected_drawdown, peak_date, trough_date = replay_v3.max_drawdown_window(nav)

    assert row["return_period_count"] == periods
    assert row["compound_annualized_return"] == expected_growth
    assert row["annualized_volatility"] == expected_vol
    assert row["sharpe_ratio"] == replay_v3.signed_zero_safe_ratio(expected_growth, expected_vol)
    assert row["max_drawdown"] == expected_drawdown
    assert row["max_drawdown_peak_date"] == peak_date.isoformat()
    assert row["max_drawdown_trough_date"] == trough_date.isoformat()
    assert row["calmar_ratio"] == replay_v3.signed_zero_safe_ratio(expected_growth, abs(expected_drawdown))


def test_select_canonical_rows_splits_portfolio_variants_without_counting_them_as_topk() -> None:
    raw = pd.DataFrame(
        [
            {
                "search_id": "search_one",
                "model_id": "s1_model__candidate_a__candidate_a",
                "backtest_id": "bt_s1_search_one__candidate_a",
                "shortlist_rank_valid_only": 1,
            },
            {
                "search_id": "search_one",
                "model_id": "s1_model__candidate_a__candidate_a",
                "backtest_id": "bt_s1_candidate_a_portfolio_n10_w15_20260609_01",
                "shortlist_rank_valid_only": 1,
            },
            {
                "search_id": "search_one",
                "model_id": "s1_model__candidate_b__candidate_b",
                "backtest_id": "bt_s1_search_one__candidate_b",
                "shortlist_rank_valid_only": 2,
            },
        ]
    )

    canonical, variants = analysis.select_canonical_rows(raw, ["search_one"], 2)

    assert canonical["backtest_id"].tolist() == [
        "bt_s1_search_one__candidate_a",
        "bt_s1_search_one__candidate_b",
    ]
    assert variants["backtest_id"].tolist() == ["bt_s1_candidate_a_portfolio_n10_w15_20260609_01"]
    assert variants.iloc[0]["expected_canonical_backtest_id"] == "bt_s1_search_one__candidate_a"


def test_option_statuses_keep_absolute_calmar_and_relative_gate_separate() -> None:
    metrics = {
        "sharpe_ratio": 0.71,
        "calmar_ratio": 0.60,
        "compound_annualized_return": 0.12,
        "max_drawdown": -0.20,
    }
    relative = pd.DataFrame(
        [
            {"benchmark_sec_code": "000852.SH", "relative_gate_pass": False},
            {"benchmark_sec_code": "000001.SH", "relative_gate_pass": True},
        ]
    )

    rows = analysis.option_statuses(metrics, relative, option_a_threshold=0.5)

    assert rows["A_lower_absolute_calmar_0_50"]["status"] == "accepted"
    assert rows["B_absolute_excess_calmar_vs_000852"]["status"] == "rejected"
    assert rows["C_dual_track_remove_absolute_calmar"]["status"] == "accepted"
    assert rows["D_current_v3_no_change"]["status"] == "rejected"
    assert rows["D_current_v3_no_change"]["absolute_gate_status"] == "failed"
