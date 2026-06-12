from __future__ import annotations

import math
from datetime import date

import pandas as pd

from scripts.strategy1 import analyze_topdown_lot_phase0 as phase0


def make_cfg(**overrides: object) -> phase0.Phase0Config:
    values = {
        "project": "data-aquarium",
        "location": "asia-east2",
        "strategy_id": "ml_pv_clf_v0",
        "prediction_run_id": "pred",
        "backtest_id": "bt",
        "start_date": "2026-01-05",
        "end_date": "2026-01-12",
        "feature_version": "fv",
        "benchmark_sec_code": "000852.SH",
        "initial_capital": 100_000.0,
        "position_floor_count": 20,
        "walk_depths": (3,),
        "cost_bps_values": (0.0,),
        "report_md": phase0.Path("report.md"),
        "metrics_csv": phase0.Path("metrics.csv"),
        "daily_csv": phase0.Path("daily.csv"),
        "audit_csv": phase0.Path("audit.csv"),
        "prd09_transfer_csv": phase0.Path("l3.csv"),
        "skip_report": True,
    }
    values.update(overrides)
    return phase0.Phase0Config(**values)


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
    assert phase0.tail_risk_reason(risky) == "tail_risk:ret_20d_lt_30pct;tail_risk:circ_mv_lt_20e8"
    assert phase0.tail_risk_reason(missing) == "tail_risk:required_field_null"


def test_min_buy_shares_ceil_to_lot_threshold() -> None:
    assert phase0.min_buy_shares(100_000.0, 10.0, 0.05) == 500.0
    assert phase0.min_buy_shares(100_000.0, 80.0, 0.05) == 100.0


def test_resolve_run_ids_prefers_true5y_current_research_baseline_fixture() -> None:
    memory_text = """
### 旧记录：effective-window continuous

- 运行口径：run `s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02`
  / backtest `bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`。

### 最新补充（2026-06-12）：研究 baseline 切换为 true-five-year continuous（DECISION-20260612-02）

- Owner 采纳 true-five-year continuous 为策略 1 研究 baseline：run
  `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01`、
  backtest `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01`；
  effective-window continuous 降级为历史参照。
"""

    prediction_run_id, backtest_id = phase0.resolve_run_ids_from_memory_text(None, None, memory_text)

    assert prediction_run_id == "s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01"
    assert backtest_id == "bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01"


def test_rebalance_t1_skips_p1_and_replaces_with_next_candidate() -> None:
    cfg = make_cfg(end_date="2026-01-05")
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
    cfg = make_cfg(end_date="2026-01-05", walk_depths=(1,))
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


def test_rebalance_uses_split_buy_sell_cost_bps() -> None:
    cfg = make_cfg(end_date="2026-01-05", walk_depths=(1,))
    prices = pd.DataFrame(
        {
            "sec_code": ["000001.SZ", "000002.SZ"],
            "trade_date": [date(2026, 1, 5)] * 2,
            "open": [10.0, 10.0],
            "close": [10.0, 10.0],
            "can_buy_open": [True, True],
            "can_sell_open": [True, True],
        }
    )
    state = phase0.PortfolioState(cash=5_000.0, holdings={"000001.SZ": 100.0}, previous_nav_value=10_000.0)

    new_state, turnover, cost, audit = phase0.rebalance_topdown(
        cfg=cfg,
        state=state,
        trade_date=date(2026, 1, 5),
        signal_date=date(2026, 1, 2),
        arm="T0",
        walk_depth=1,
        cost_bps=8.5,
        buy_cost_bps=6.0,
        sell_cost_bps=11.0,
        nav_before=10_000.0,
        candidates=pd.DataFrame(
            {"sec_code": ["000002.SZ"], "rank_raw": [1], "tail_risk_reason": [None]}
        ),
        price_book=phase0.PriceBook(prices),
    )

    assert new_state.holdings == {"000002.SZ": 100.0}
    assert math.isclose(turnover, 2_000.0)
    assert math.isclose(cost, 1.7)
    assert math.isclose(audit["cost_cny"], 1.7)
    assert math.isclose(new_state.cash, 4_998.3)


def test_simulate_arm_reports_max_weight_with_nav_denominator() -> None:
    cfg = make_cfg(walk_depths=(1,))
    calendar = pd.DataFrame(
        {
            "trade_date": [
                date(2026, 1, 5),
                date(2026, 1, 6),
                date(2026, 1, 7),
                date(2026, 1, 8),
                date(2026, 1, 9),
                date(2026, 1, 12),
            ],
            "trade_date_seq": [1, 2, 3, 4, 5, 6],
        }
    )
    candidates = pd.DataFrame(
        {
            "rebalance_date": [date(2026, 1, 9)],
            "sec_code": ["000001.SZ"],
            "rank_raw": [1],
            "tail_risk_reason": [None],
        }
    )
    benchmark = calendar[["trade_date"]].copy()
    benchmark["benchmark_return"] = 0.0
    prices = pd.DataFrame(
        {
            "sec_code": ["000001.SZ"],
            "trade_date": [date(2026, 1, 12)],
            "open": [10.0],
            "close": [10.0],
            "can_buy_open": [True],
            "can_sell_open": [True],
        }
    )

    daily, _ = phase0.simulate_arm(
        cfg=cfg,
        arm="T0",
        walk_depth=1,
        cost_profile=phase0.CostProfile("single_0bps", 0.0, 0.0, 0.0),
        candidates=candidates,
        calendar=calendar,
        benchmark=benchmark,
        price_book=phase0.PriceBook(prices),
    )

    rebalance_day = daily[daily["trade_date"] == date(2026, 1, 12)].iloc[0]
    assert math.isclose(rebalance_day["max_realized_weight"], 0.05)
    assert math.isclose(rebalance_day["max_position_weight_within_holdings"], 1.0)


def test_summarize_arm_uses_n_minus_one_return_period_and_avg_nav_turnover() -> None:
    cfg = make_cfg()
    daily = pd.DataFrame(
        {
            "trade_date": [date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)],
            "daily_return": [0.0, 0.10, 0.10],
            "benchmark_return": [0.0, 0.0, 0.0],
            "nav": [1.0, 1.1, 1.21],
            "net_value_cny": [100_000.0, 110_000.0, 121_000.0],
            "cash_weight": [0.0, 0.0, 0.0],
            "realized_holdings_count": [1, 1, 1],
            "max_realized_weight": [0.2, 0.2, 0.2],
            "max_position_weight_within_holdings": [0.2, 0.2, 0.2],
        }
    )
    audit = pd.DataFrame(
        {
            "turnover_cny": [22_000.0],
            "cost_cny": [0.0],
            "p1_skip_count": [0],
            "unbuyable_skip_count": [0],
            "cash_insufficient_skip_count": [0],
            "sell_price_missing_count": [0],
            "p1_marked_rate": [0.0],
        }
    )

    summary = phase0.summarize_arm(
        daily,
        audit,
        cfg,
        "T0",
        1,
        phase0.CostProfile("single_0bps", 0.0, 0.0, 0.0),
    )

    assert summary["return_period_count"] == 2
    expected_turnover = 22_000.0 / daily["net_value_cny"].mean() / (2 / 252.0)
    assert math.isclose(summary["annual_turnover"], expected_turnover)
