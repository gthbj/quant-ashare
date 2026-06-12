from __future__ import annotations

from datetime import date

import pandas as pd

from scripts.strategy1 import analyze_topdown_lot_phase0 as phase0


def test_tail_risk_reason_matches_p1_rules_and_null_guard() -> None:
    clean = {
        "ret_20d": -0.01,
        "drawdown_20d": -0.02,
        "limit_down_days_20d": 0,
        "one_word_limit_days_20d": 0,
        "total_mv_cny": 50e8,
        "circ_mv_cny": 40e8,
    }
    risky = {**clean, "ret_20d": -0.31, "circ_mv_cny": 10e8}
    missing = {**clean, "total_mv_cny": None}

    assert phase0.tail_risk_reason(clean) is None
    assert phase0.tail_risk_reason(risky) == "tail_risk:ret_20d_lt_30pct|tail_risk:circ_mv_lt_20e8"
    assert phase0.tail_risk_reason(missing) == "tail_risk:required_field_null"


def test_min_buy_shares_ceil_to_lot_threshold() -> None:
    assert phase0.min_buy_shares(100_000.0, 10.0, 0.05) == 500.0
    assert phase0.min_buy_shares(100_000.0, 80.0, 0.05) == 100.0


def test_rebalance_t1_skips_p1_and_replaces_with_next_candidate() -> None:
    cfg = phase0.Phase0Config(
        project="data-aquarium",
        location="asia-east2",
        strategy_id="ml_pv_clf_v0",
        prediction_run_id="pred",
        backtest_id="bt",
        start_date="2026-01-05",
        end_date="2026-01-05",
        feature_version="fv",
        benchmark_sec_code="000852.SH",
        initial_capital=100_000.0,
        position_floor_count=20,
        walk_depths=(3,),
        cost_bps_values=(0.0,),
        report_md=phase0.Path("report.md"),
        metrics_csv=phase0.Path("metrics.csv"),
        daily_csv=phase0.Path("daily.csv"),
        audit_csv=phase0.Path("audit.csv"),
        prd09_transfer_csv=phase0.Path("l3.csv"),
        skip_report=True,
    )
    prices = pd.DataFrame(
        {
            "sec_code": ["000001.SZ", "000002.SZ", "000003.SZ"],
            "trade_date": [date(2026, 1, 5)] * 3,
            "open": [10.0, 10.0, 10.0],
            "close": [10.0, 10.0, 10.0],
            "can_buy_open": [True, True, True],
            "can_sell_open": [True, True, True],
        }
    )
    candidates = pd.DataFrame(
        {
            "rebalance_date": [date(2026, 1, 2)] * 3,
            "sec_code": ["000001.SZ", "000002.SZ", "000003.SZ"],
            "rank_raw": [1, 2, 3],
            "tail_risk_reason": [None, "tail_risk:ret_20d_lt_30pct", None],
        }
    )
    state = phase0.PortfolioState(cash=11_000.0, holdings={}, previous_nav_value=100_000.0)

    t0_state, _, _, t0_audit = phase0.rebalance_topdown(
        cfg=cfg,
        state=state,
        trade_date=date(2026, 1, 5),
        signal_date=date(2026, 1, 2),
        arm="T0",
        walk_depth=3,
        cost_bps=0.0,
        nav_before=100_000.0,
        candidates=candidates,
        price_book=phase0.PriceBook(prices),
    )
    t1_state, _, _, t1_audit = phase0.rebalance_topdown(
        cfg=cfg,
        state=state,
        trade_date=date(2026, 1, 5),
        signal_date=date(2026, 1, 2),
        arm="T1",
        walk_depth=3,
        cost_bps=0.0,
        nav_before=100_000.0,
        candidates=candidates,
        price_book=phase0.PriceBook(prices),
    )

    assert set(t0_state.holdings) == {"000001.SZ", "000002.SZ"}
    assert set(t1_state.holdings) == {"000001.SZ", "000003.SZ"}
    assert t0_audit["p1_skip_count"] == 0
    assert t1_audit["p1_skip_count"] == 1


def test_rebalance_sells_over_depth_holding_without_pending_simulation() -> None:
    cfg = phase0.Phase0Config(
        project="data-aquarium",
        location="asia-east2",
        strategy_id="ml_pv_clf_v0",
        prediction_run_id="pred",
        backtest_id="bt",
        start_date="2026-01-05",
        end_date="2026-01-05",
        feature_version="fv",
        benchmark_sec_code="000852.SH",
        initial_capital=100_000.0,
        position_floor_count=20,
        walk_depths=(1,),
        cost_bps_values=(0.0,),
        report_md=phase0.Path("report.md"),
        metrics_csv=phase0.Path("metrics.csv"),
        daily_csv=phase0.Path("daily.csv"),
        audit_csv=phase0.Path("audit.csv"),
        prd09_transfer_csv=phase0.Path("l3.csv"),
        skip_report=True,
    )
    prices = pd.DataFrame(
        {
            "sec_code": ["000099.SZ"],
            "trade_date": [date(2026, 1, 5)],
            "open": [20.0],
            "close": [20.0],
            "can_buy_open": [False],
            "can_sell_open": [False],
        }
    )
    state = phase0.PortfolioState(cash=0.0, holdings={"000099.SZ": 100.0}, previous_nav_value=2_000.0)

    new_state, turnover, _, audit = phase0.rebalance_topdown(
        cfg=cfg,
        state=state,
        trade_date=date(2026, 1, 5),
        signal_date=date(2026, 1, 2),
        arm="T1",
        walk_depth=1,
        cost_bps=0.0,
        nav_before=2_000.0,
        candidates=pd.DataFrame(columns=["sec_code", "rank_raw", "tail_risk_reason"]),
        price_book=phase0.PriceBook(prices),
    )

    assert new_state.holdings == {}
    assert new_state.cash == 2_000.0
    assert turnover == 2_000.0
    assert audit["sell_count"] == 1
