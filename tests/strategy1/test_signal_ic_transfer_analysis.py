from __future__ import annotations

import math
from datetime import date

import pandas as pd

from scripts.strategy1 import analyze_signal_ic_decomposition as analysis


def test_newey_west_t_stat_has_lower_effective_n_for_positive_autocorrelation() -> None:
    values = [0.01, 0.02, 0.018, 0.019, 0.021, 0.02, 0.019, 0.018]

    result = analysis.newey_west_mean_t(values, lag=3)

    assert result["t_stat"] > 0
    assert 1 <= result["effective_n"] <= len(values)


def test_residualize_by_date_removes_size_linear_effect() -> None:
    df = pd.DataFrame(
        {
            "predict_date": [date(2024, 1, 2)] * 5,
            "score": [1, 2, 3, 4, 5],
            "fwd_xs_ret_5d": [2, 4, 6, 8, 10],
            "log_circ_mv": [1, 2, 3, 4, 5],
        }
    )

    out = analysis.residualize_by_date(df, "fwd_xs_ret_5d", ["log_circ_mv"])

    assert abs(float(out["score_residual"].mean())) < 1e-12
    assert out["score_residual"].abs().max() < 1e-10
    assert out["label_residual"].abs().max() < 1e-10


def test_build_biweekly_rebalance_dates_uses_alternating_weekly_last_open() -> None:
    dates = pd.to_datetime(
        [
            "2021-01-04",
            "2021-01-05",
            "2021-01-08",
            "2021-01-11",
            "2021-01-15",
            "2021-01-18",
            "2021-01-22",
            "2021-01-25",
            "2021-01-29",
        ]
    ).date
    calendar = pd.DataFrame({"trade_date": dates, "trade_date_seq": range(1, len(dates) + 1)})

    result = analysis.build_biweekly_rebalance_dates(calendar, "2021-01-04", "2021-01-29")

    assert result == [date(2021, 1, 8), date(2021, 1, 22)]


def test_weight_book_generates_expected_levels_and_l3_equal_top20() -> None:
    base = pd.DataFrame(
        {
            "predict_date": [date(2021, 1, 8)] * 100,
            "sec_code": [f"{i:06d}.SZ" for i in range(100)],
            "score": list(range(100)),
        }
    )

    book = analysis.build_weight_book(base, [date(2021, 1, 8)])

    assert set(book["level"]) == {"L0", "L0.5", "L1", "L2", "L3"}
    l05 = book[book["level"] == "L0.5"]
    assert len(l05) == 10
    assert math.isclose(float(l05["weight"].sum()), 1.0)
    l3 = book[book["level"] == "L3"]
    assert len(l3) == 20
    assert math.isclose(float(l3["weight"].sum()), 1.0)
    assert l3["weight"].nunique() == 1


def test_l0_weights_are_dollar_neutral() -> None:
    group = pd.DataFrame(
        {
            "sec_code": [f"{i:06d}.SZ" for i in range(20)],
            "score": list(range(20)),
        }
    ).sort_values("score", ascending=False)

    weights = analysis.l0_weights(group, n_decile=2)

    assert math.isclose(float(weights["weight"].sum()), 0.0, abs_tol=1e-12)
    assert math.isclose(float(weights.loc[weights["weight"] > 0, "weight"].sum()), 1.0)
    assert math.isclose(float(weights.loc[weights["weight"] < 0, "weight"].sum()), -1.0)


def test_simulate_weight_book_applies_open_to_close_on_exec_and_close_to_close_after() -> None:
    signal = date(2021, 1, 4)
    exec_day = date(2021, 1, 5)
    hold_day = date(2021, 1, 6)
    weights = pd.DataFrame(
        {
            "signal_date": [signal],
            "sec_code": ["000001.SZ"],
            "weight": [1.0],
            "level": ["L3"],
        }
    )
    price_returns = {
        ("000001.SZ", exec_day): (0.10, 0.50),
        ("000001.SZ", hold_day): (0.20, 0.03),
    }

    out = analysis.simulate_weight_book(
        weights,
        [signal],
        [signal, exec_day, hold_day],
        {signal: exec_day, exec_day: hold_day},
        price_returns,
        cost_bps=0.0,
    )

    assert out.loc[out["trade_date"] == exec_day, "daily_return"].iloc[0] == 0.10
    assert abs(out.loc[out["trade_date"] == hold_day, "daily_return"].iloc[0] - 0.03) < 1e-12


def test_weight_correlation_uses_explicit_domain_with_missing_as_zero() -> None:
    ideal = {"a": 0.7, "b": 0.3}
    actual = {"a": 0.5, "c": 0.5}

    corr = analysis.weight_correlation_on_domain(ideal, actual, ["a", "b", "c", "d"])

    assert corr < 1.0
    assert corr > -1.0


def test_weight_correlation_rejects_near_constant_vector() -> None:
    ideal = {"a": 0.7, "b": 0.3}
    constant = {"a": 0.05, "b": 0.05}

    corr = analysis.weight_correlation_on_domain(ideal, constant, ["a", "b"])

    assert pd.isna(corr)


def test_transfer_coefficients_report_full_universe_and_membership_coverage() -> None:
    base = pd.DataFrame(
        {
            "predict_date": [date(2021, 1, 8)] * 5,
            "sec_code": ["a", "b", "c", "d", "e"],
        }
    )
    weight_book = pd.DataFrame(
        {
            "signal_date": [date(2021, 1, 8), date(2021, 1, 8)],
            "sec_code": ["a", "b"],
            "weight": [0.7, 0.3],
            "level": ["L2", "L2"],
        }
    )
    targets = pd.DataFrame(
        {
            "rebalance_date": [date(2021, 1, 8), date(2021, 1, 8)],
            "sec_code": ["a", "b"],
            "target_weight": [0.5, 0.5],
        }
    )
    positions = pd.DataFrame(
        {
            "trade_date": [date(2021, 1, 11)],
            "sec_code": ["a"],
            "weight": [0.4],
        }
    )
    calendar = pd.DataFrame(
        {
            "trade_date": [date(2021, 1, 8), date(2021, 1, 11)],
            "trade_date_seq": [1, 2],
        }
    )

    out = analysis.compute_transfer_coefficients(
        base=base,
        weight_book=weight_book,
        official_targets=targets,
        official_positions=positions,
        calendar=calendar,
    )
    row = out.iloc[0]

    assert row["tc_domain"] == "full_prediction_universe"
    assert row["universe_size"] == 5
    assert row["target_ideal_overlap_rate"] == 1.0
    assert row["realized_target_overlap_rate"] == 0.5
    assert row["official_cash_weight"] == 0.6


def test_report_contains_preregistered_rules_and_no_score_reversal_instruction() -> None:
    cfg = analysis.AnalysisConfig(
        project="data-aquarium",
        location="asia-east2",
        strategy_id="ml_pv_clf_v0",
        prediction_run_id="pred",
        backtest_id="bt",
        start_date="2021-01-04",
        end_date="2026-06-09",
        label_version="open_to_close_h1_5_10_20_v20260601",
        feature_version="strategy1_pv_v0_20260601",
        market_state_version="market_state_v1_20260607",
        benchmark_sec_code="000852.SH",
        ic_csv=analysis.Path("ic.csv"),
        daily_ic_csv=analysis.Path("daily.csv"),
        transfer_csv=analysis.Path("transfer.csv"),
        tc_csv=analysis.Path("tc.csv"),
        report_md=analysis.Path("report.md"),
        skip_report=False,
    )
    ic = pd.DataFrame(
        [
            {
                "section": "A5_horizon",
                "bucket": "5d",
                "horizon": 5,
                "mean_rank_ic": 0.01,
                "nw_t_stat": 2.0,
                "n_days": 10,
                "sample_start": "2021-01-04",
                "sample_end": "2021-01-18",
            }
        ]
    )
    transfer = pd.DataFrame(
        [
            {
                "level": "L0",
                "cost_bps": 0.0,
                "compound_annual_return": 0.1,
                "absolute_sharpe_or_contract_sharpe": 0.9,
                "information_ratio_vs_000852": 0.8,
                "max_drawdown": -0.2,
                "calmar_ratio": 0.5,
                "crunch_excess_return_vs_000852": 0.1,
                "avg_gross_exposure": 2.0,
                "rebalance_count": 3,
            },
            {
                "level": "L0.5",
                "cost_bps": 0.0,
                "compound_annual_return": 0.09,
                "absolute_sharpe_or_contract_sharpe": 0.6,
                "information_ratio_vs_000852": 0.7,
                "max_drawdown": -0.22,
                "calmar_ratio": 0.4,
                "crunch_excess_return_vs_000852": 0.05,
                "avg_gross_exposure": 1.0,
                "rebalance_count": 3,
            },
            {
                "level": "L3",
                "cost_bps": 0.0,
                "compound_annual_return": 0.08,
                "absolute_sharpe_or_contract_sharpe": 0.5,
                "information_ratio_vs_000852": 0.4,
                "max_drawdown": -0.3,
                "calmar_ratio": 0.27,
                "crunch_excess_return_vs_000852": -0.2,
                "avg_gross_exposure": 1.0,
                "rebalance_count": 3,
                "official_l3_daily_return_corr": 0.9,
                "official_l3_cagr_diff": 0.01,
                "official_l3_maxdd_diff": -0.02,
            },
        ]
    )
    tc = pd.DataFrame(
        [
            {
                "tc_target": 0.5,
                "tc_realized": 0.4,
                "target_ideal_overlap_rate": 1.0,
                "realized_target_overlap_rate": 0.5,
                "realized_nonzero": 10,
                "official_cash_weight": 0.2,
            }
        ]
    )

    report = analysis.build_report(cfg, ic, transfer, tc)

    assert "预登记解读规则" in report
    assert "本报告不按 `score_orientation` 再反转" in report
    assert "L0 no-cost 最优 absolute Sharpe" in report
    assert "名字重合率" in report
    assert "几乎不保留 score-weighted 强度" not in report
