from __future__ import annotations

import datetime as dt
import dataclasses
import json
import math
from types import SimpleNamespace
import unittest

import pandas as pd
import pytest

import quant_ashare.strategy1.ledger as ledger_mod
from scripts.strategy1_cloudrun.ledger import (
    CORPORATE_ACTIONS_CASH_DIV_AND_SPLIT,
    CORPORATE_ACTIONS_NONE,
    DIVIDEND_TAX_FLAT_10PCT,
    LEDGER_VERSION_LOT100,
    RESUME_POLICY_CLOUDRUN_LOT100,
    LedgerParams,
    PlanRow,
    apply_corporate_actions,
    build_daily_plan,
    execute_plan,
    validate_ledger_params,
    ledger_params_hash,
    hash_holdings,
    parent_summary_corporate_action_params,
    run_ledger,
    update_holdings,
    update_pending_sell,
)


def params() -> LedgerParams:
    return LedgerParams(
        project="data-aquarium",
        run_id="unit_run",
        backtest_id="unit_backtest",
        ledger_version=LEDGER_VERSION_LOT100,
    )


def row(
    sec_code: str,
    *,
    open_price: float = 10.0,
    cur_shares: float = 0.0,
    desired_value: float = 0.0,
    cur_value: float = 0.0,
    sell_shares: float = 0.0,
    want_value: float = 0.0,
    rank_raw: float | None = 1,
    sell_skip_shares: float = 0.0,
    sell_skip_status: str | None = None,
) -> PlanRow:
    p = params()
    return PlanRow(
        sec_code=sec_code,
        cur_shares=cur_shares,
        exec_open=open_price,
        buy_fill_price=open_price * (1 + p.slippage_buy_bps / 10000.0),
        sell_fill_price=open_price * (1 - p.slippage_sell_bps / 10000.0),
        can_buy=True,
        can_sell=True,
        val_price=open_price,
        desired_value=desired_value,
        cur_value=cur_value,
        was_pending=False,
        sell_shares=sell_shares,
        want_value=want_value,
        sell_skip_shares=sell_skip_shares,
        buy_skip_value=0.0,
        tail_risk_new_buy_blocked=False,
        market_risk_buy_blocked=False,
        pending_noop=False,
        target_rank_raw=rank_raw,
        sell_skip_status=sell_skip_status,
    )


class FakePriceBook:
    def __init__(self, prices: dict[str, dict[str, object]]):
        self.prices = prices

    def row(self, sec_code, trade_date):
        data = self.prices.get(sec_code)
        if data is None:
            return None
        return type("PriceRow", (), data)()

    def valuation_price(self, sec_code, trade_date):
        return float(self.prices[sec_code].get("close", self.prices[sec_code]["open"]))


class LotAwareLedgerTest(unittest.TestCase):
    def test_buy_floors_to_100_share_lot_and_keeps_cash_fragment(self):
        p = params()
        trade_date = dt.date(2026, 1, 5)
        plan = [row("000001.SZ", open_price=23.0, want_value=10_000.0)]

        cash, trades = execute_plan(trade_date, 10_000.0, plan, p, is_rebalance=True)

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["fill_status"], "FILLED")
        self.assertEqual(trades[0]["filled_shares"], 400.0)
        expected_turnover = 400.0 * 23.0 * 1.0005
        expected_fee = expected_turnover * 0.0001
        self.assertTrue(math.isclose(trades[0]["turnover_cny"], expected_turnover, abs_tol=1e-9))
        self.assertTrue(math.isclose(trades[0]["fee_cny"], expected_fee, abs_tol=1e-9))
        self.assertTrue(math.isclose(cash, 10_000.0 - expected_turnover - expected_fee, abs_tol=1e-9))
        self.assertEqual(update_holdings(plan), {"000001.SZ": 400.0})

    def test_original_below_lot_buy_is_skipped_without_cash_effect(self):
        p = params()
        plan = [row("000001.SZ", open_price=10.0, want_value=999.0)]

        cash, trades = execute_plan(dt.date(2026, 1, 5), 10_000.0, plan, p, is_rebalance=True)

        self.assertEqual(cash, 10_000.0)
        self.assertEqual(trades[0]["fill_status"], "BUY_SKIPPED_BELOW_LOT")
        self.assertEqual(trades[0]["filled_shares"], 0.0)
        self.assertEqual(trades[0]["cash_effect_cny"], 0.0)
        self.assertEqual(update_holdings(plan), {})

    def test_cash_scale_can_make_buy_below_lot_after_scale(self):
        p = params()
        plan = [
            row("000001.SZ", open_price=50.0, want_value=9_000.0, rank_raw=1),
            row("000002.SZ", open_price=50.0, want_value=9_000.0, rank_raw=2),
        ]

        cash, trades = execute_plan(dt.date(2026, 1, 5), 4_000.0, plan, p, is_rebalance=True)

        self.assertEqual(cash, 4_000.0)
        self.assertEqual([t["fill_status"] for t in trades], [
            "BUY_SKIPPED_BELOW_LOT_AFTER_SCALE",
            "BUY_SKIPPED_BELOW_LOT_AFTER_SCALE",
        ])
        self.assertEqual(update_holdings(plan), {})

    def test_cash_defensive_fallback_drops_lower_priority_buy(self):
        p = params()
        plan = [
            row("000001.SZ", open_price=50.0, want_value=9_000.0, rank_raw=1),
            row("000002.SZ", open_price=50.0, want_value=9_000.0, rank_raw=2),
        ]

        cash, trades = execute_plan(dt.date(2026, 1, 5), 10_000.0, plan, p, is_rebalance=True)

        statuses = {t["sec_code"]: t["fill_status"] for t in trades}
        self.assertEqual(statuses["000001.SZ"], "FILLED_SCALED_CASH")
        self.assertEqual(statuses["000002.SZ"], "BUY_SKIPPED_CASH_INSUFFICIENT_AFTER_ROUNDING")
        self.assertGreaterEqual(cash, 0.0)
        self.assertEqual(update_holdings(plan), {"000001.SZ": 100.0})

    def test_full_exit_allows_odd_lot_sell(self):
        p = params()
        price_book = FakePriceBook({
            "000001.SZ": {"open": 10.0, "close": 10.0, "can_buy_open": True, "can_sell_open": True},
        })
        plan = build_daily_plan(
            dt.date(2026, 1, 5),
            True,
            {"000001.SZ": 75.0},
            {},
            set(),
            set(),
            False,
            750.0,
            price_book,
            p,
        )

        cash, trades = execute_plan(dt.date(2026, 1, 5), 0.0, plan, p, is_rebalance=True)

        self.assertEqual(trades[0]["side"], "SELL")
        self.assertEqual(trades[0]["fill_status"], "FILLED")
        self.assertEqual(trades[0]["filled_shares"], 75.0)
        self.assertGreater(cash, 0.0)
        self.assertEqual(update_holdings(plan), {})

    def test_partial_sell_below_lot_keeps_residual_and_no_pending_retry(self):
        p = params()
        price_book = FakePriceBook({
            "000001.SZ": {"open": 10.0, "close": 10.0, "can_buy_open": True, "can_sell_open": True},
        })
        plan = build_daily_plan(
            dt.date(2026, 1, 5),
            True,
            {"000001.SZ": 150.0},
            {"000001.SZ": {"target_weight": 2 / 3, "rank_raw": 1}},
            set(),
            set(),
            False,
            1_500.0,
            price_book,
            p,
        )

        cash, trades = execute_plan(dt.date(2026, 1, 5), 0.0, plan, p, is_rebalance=True)

        self.assertEqual(cash, 0.0)
        self.assertEqual(trades[0]["fill_status"], "SELL_SKIPPED_BELOW_LOT_PARTIAL")
        self.assertEqual(update_holdings(plan), {"000001.SZ": 150.0})
        self.assertEqual(update_pending_sell(plan, True), set())

    def test_untradable_full_exit_enters_pending_then_retries_next_open_day(self):
        p = params()
        day1_prices = FakePriceBook({
            "000001.SZ": {"open": 10.0, "close": 10.0, "can_buy_open": True, "can_sell_open": False},
        })
        day1_plan = build_daily_plan(
            dt.date(2026, 1, 5),
            True,
            {"000001.SZ": 100.0},
            {},
            set(),
            set(),
            False,
            1_000.0,
            day1_prices,
            p,
        )
        _, day1_trades = execute_plan(dt.date(2026, 1, 5), 0.0, day1_plan, p, is_rebalance=True)
        pending = update_pending_sell(day1_plan, True)

        self.assertEqual(day1_trades[0]["fill_status"], "SELL_SKIPPED_UNTRADABLE")
        self.assertEqual(pending, {"000001.SZ"})

        day2_prices = FakePriceBook({
            "000001.SZ": {"open": 10.0, "close": 10.0, "can_buy_open": True, "can_sell_open": True},
        })
        day2_plan = build_daily_plan(
            dt.date(2026, 1, 6),
            False,
            {"000001.SZ": 100.0},
            {},
            pending,
            set(),
            False,
            1_000.0,
            day2_prices,
            p,
        )
        _, day2_trades = execute_plan(dt.date(2026, 1, 6), 0.0, day2_plan, p, is_rebalance=False)

        self.assertEqual(day2_trades[0]["fill_status"], "FILLED")
        self.assertEqual(day2_trades[0]["filled_shares"], 100.0)
        self.assertEqual(update_pending_sell(day2_plan, False), set())


if __name__ == "__main__":
    unittest.main()



def test_resume_requires_explicit_parent_state_and_anchor() -> None:
    params = LedgerParams(
        project="data-aquarium",
        run_id="child",
        backtest_id="child_bt",
        strategy_id="strategy",
        predict_start="2024-01-08",
        predict_end="2024-01-31",
        initial_state_mode="resume_from_backtest",
        parent_backtest_id="parent_bt",
        state_as_of_date="2024-01-05",
    )

    with pytest.raises(ValueError, match="explicit rebalance_anchor_start"):
        validate_ledger_params(params)


def test_resume_policy_id_is_fixed() -> None:
    params = LedgerParams(
        project="data-aquarium",
        run_id="child",
        backtest_id="child_bt",
        strategy_id="strategy",
        predict_start="2024-01-08",
        predict_end="2024-01-31",
        initial_state_mode="resume_from_backtest",
        parent_backtest_id="parent_bt",
        state_as_of_date="2024-01-05",
        rebalance_anchor_start="2024-01-02",
        resume_policy_id=RESUME_POLICY_CLOUDRUN_LOT100,
    )

    validate_ledger_params(params)


def test_ledger_params_hash_ignores_backtest_identity_but_keeps_anchor() -> None:
    parent = LedgerParams(
        project="data-aquarium",
        run_id="parent",
        backtest_id="parent_bt",
        strategy_id="strategy",
        predict_start="2024-01-02",
        predict_end="2024-12-31",
        rebalance_anchor_start="2024-01-02",
    )
    child = LedgerParams(
        project="data-aquarium",
        run_id="child",
        backtest_id="child_bt",
        strategy_id="strategy",
        predict_start="2024-07-01",
        predict_end="2024-12-31",
        initial_state_mode="resume_from_backtest",
        parent_backtest_id="parent_bt",
        state_as_of_date="2024-06-28",
        rebalance_anchor_start="2024-01-02",
    )
    shifted_anchor = LedgerParams(
        project="data-aquarium",
        run_id="child",
        backtest_id="child_bt",
        strategy_id="strategy",
        predict_start="2024-07-01",
        predict_end="2024-12-31",
        initial_state_mode="resume_from_backtest",
        parent_backtest_id="parent_bt",
        state_as_of_date="2024-06-28",
        rebalance_anchor_start="2024-07-01",
    )

    assert ledger_params_hash(parent) == ledger_params_hash(child)
    assert ledger_params_hash(parent) != ledger_params_hash(shifted_anchor)


def test_default_ledger_params_hash_keeps_pre_corporate_action_golden_value() -> None:
    assert ledger_params_hash(params()) == "2108e411d056418b09c84f99b75021a5329fea58eb474d5906e0e4287f69cc0d"
    ca_on = dataclasses.replace(params(), corporate_actions=CORPORATE_ACTIONS_CASH_DIV_AND_SPLIT)

    assert ledger_params_hash(params()) != ledger_params_hash(ca_on)


def test_hash_holdings_is_order_invariant() -> None:
    assert hash_holdings({"000001.SZ": 200, "000002.SZ": 100}) == hash_holdings(
        {"000002.SZ": 100, "000001.SZ": 200}
    )


def test_corporate_action_split_floor_and_flat_tax_use_record_date_shares() -> None:
    p = dataclasses.replace(params(), corporate_actions=CORPORATE_ACTIONS_CASH_DIV_AND_SPLIT)
    event = SimpleNamespace(
        sec_code="000001.SZ",
        ex_date=dt.date(2024, 1, 3),
        record_date=dt.date(2024, 1, 2),
        cash_div_per_share_pretax=1.0,
        split_ratio=0.5,
        source_event_count=2,
    )

    cash, holdings, rows = apply_corporate_actions(
        dt.date(2024, 1, 3),
        1_000.0,
        {"000001.SZ": 200.0},
        {dt.date(2024, 1, 2): {"000001.SZ": 100.0}},
        [event],
        p,
    )

    assert holdings == {"000001.SZ": 250.0}
    assert math.isclose(cash, 1_090.0, abs_tol=1e-9)
    assert [row["fill_status"] for row in rows] == [
        "CORPORATE_ACTION_SPLIT",
        "CORPORATE_ACTION_CASH_DIVIDEND",
    ]
    assert rows[0]["planned_shares"] == 150.0
    assert rows[0]["filled_shares"] == 50.0
    assert rows[1]["planned_shares"] == 100.0
    assert rows[1]["turnover_cny"] == 100.0
    assert rows[1]["tax_cny"] == 10.0
    assert rows[1]["cash_effect_cny"] == 90.0


def test_parent_summary_corporate_action_params_default_old_rows_and_fail_fast() -> None:
    old_summary = pd.DataFrame([{"metrics_json": json.dumps({"ledger_version": LEDGER_VERSION_LOT100})}])
    ca_summary = pd.DataFrame([
        {
            "metrics_json": json.dumps({
                "corporate_actions": CORPORATE_ACTIONS_CASH_DIV_AND_SPLIT,
                "dividend_tax_mode": DIVIDEND_TAX_FLAT_10PCT,
            })
        }
    ])

    assert parent_summary_corporate_action_params(old_summary) == (
        CORPORATE_ACTIONS_NONE,
        DIVIDEND_TAX_FLAT_10PCT,
    )
    assert parent_summary_corporate_action_params(ca_summary) == (
        CORPORATE_ACTIONS_CASH_DIV_AND_SPLIT,
        DIVIDEND_TAX_FLAT_10PCT,
    )
    with pytest.raises(RuntimeError, match="exactly once"):
        parent_summary_corporate_action_params(pd.DataFrame([
            {"metrics_json": "{}"},
            {"metrics_json": "{}"},
        ]))


def test_explicit_none_v1_params_preserve_default_run_ledger_outputs(monkeypatch) -> None:
    """Proves default CA params are neutral; golden hash covers pre-CA payload parity."""

    class FixedDatetime(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 1, 1, 0, 0, tzinfo=tz)

    calendar = pd.DataFrame([
        {"trade_date": dt.date(2024, 1, 2), "trade_date_seq": 1},
        {"trade_date": dt.date(2024, 1, 3), "trade_date_seq": 2},
    ])
    targets = pd.DataFrame([
        {
            "rebalance_date": dt.date(2024, 1, 2),
            "sec_code": "000001.SZ",
            "target_weight": 0.50,
            "rank_raw": 1,
        }
    ])
    prices = pd.DataFrame([
        {
            "sec_code": "000001.SZ",
            "trade_date": dt.date(2024, 1, 2),
            "open": 10.0,
            "close": 10.0,
            "can_buy_open": True,
            "can_sell_open": True,
        },
        {
            "sec_code": "000001.SZ",
            "trade_date": dt.date(2024, 1, 3),
            "open": 10.0,
            "close": 10.0,
            "can_buy_open": True,
            "can_sell_open": True,
        },
    ])

    monkeypatch.setattr(ledger_mod, "datetime", FixedDatetime)
    monkeypatch.setattr(ledger_mod, "benchmark_assert", lambda client, params: None)
    monkeypatch.setattr(ledger_mod, "load_calendar", lambda client, start, end: calendar.copy())
    monkeypatch.setattr(ledger_mod, "load_targets", lambda client, params: targets.copy())
    monkeypatch.setattr(ledger_mod, "load_prices", lambda client, params, sec_codes, start, end: prices.copy())
    monkeypatch.setattr(ledger_mod, "load_benchmark", lambda client, params, start, end: {dt.date(2024, 1, 3): 0.0})
    monkeypatch.setattr(ledger_mod, "load_tail_risk_buy_guards", lambda client, params: {})
    monkeypatch.setattr(ledger_mod, "load_market_risk_off_signal_dates", lambda client, params: set())
    monkeypatch.setattr(ledger_mod, "load_corporate_action_events", lambda client, params, sec_codes, start, end: pd.DataFrame())

    def capture_outputs(ledger_params: LedgerParams) -> dict[str, str]:
        captured: dict[str, pd.DataFrame] = {}

        def fake_load_dataframe(client, frame, table_id):
            captured[table_id.rsplit(".", 1)[-1]] = frame.copy()

        monkeypatch.setattr(ledger_mod, "load_dataframe", fake_load_dataframe)
        run_ledger(object(), ledger_params)
        return {
            table_name: frame.sort_index(axis=1).to_json(
                orient="records",
                date_format="iso",
                default_handler=str,
            )
            for table_name, frame in sorted(captured.items())
        }

    default_params = LedgerParams(
        project="data-aquarium",
        run_id="unit_run",
        backtest_id="unit_backtest",
        predict_start="2024-01-02",
        predict_end="2024-01-03",
    )
    explicit_none_params = dataclasses.replace(
        default_params,
        corporate_actions=CORPORATE_ACTIONS_NONE,
        dividend_tax_mode=DIVIDEND_TAX_FLAT_10PCT,
    )

    assert capture_outputs(default_params) == capture_outputs(explicit_none_params)


def test_corporate_actions_are_applied_before_same_day_rebalance(monkeypatch) -> None:
    class FixedDatetime(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 1, 1, 0, 0, tzinfo=tz)

    calendar = pd.DataFrame([
        {"trade_date": dt.date(2024, 1, 1), "trade_date_seq": 1},
        {"trade_date": dt.date(2024, 1, 2), "trade_date_seq": 2},
        {"trade_date": dt.date(2024, 1, 3), "trade_date_seq": 3},
    ])
    targets = pd.DataFrame([
        {
            "rebalance_date": dt.date(2024, 1, 1),
            "sec_code": "000001.SZ",
            "target_weight": 0.10,
            "rank_raw": 1,
        },
        {
            "rebalance_date": dt.date(2024, 1, 2),
            "sec_code": "000002.SZ",
            "target_weight": 0.10,
            "rank_raw": 1,
        },
    ])
    prices = pd.DataFrame([
        {
            "sec_code": "000001.SZ",
            "trade_date": dt.date(2024, 1, 2),
            "open": 10.0,
            "close": 10.0,
            "can_buy_open": True,
            "can_sell_open": True,
        },
        {
            "sec_code": "000001.SZ",
            "trade_date": dt.date(2024, 1, 3),
            "open": 9.1,
            "close": 9.1,
            "can_buy_open": True,
            "can_sell_open": True,
        },
        {
            "sec_code": "000002.SZ",
            "trade_date": dt.date(2024, 1, 3),
            "open": 20.0,
            "close": 20.0,
            "can_buy_open": True,
            "can_sell_open": True,
        },
    ])
    corporate_events = pd.DataFrame([
        {
            "sec_code": "000001.SZ",
            "ex_date": dt.date(2024, 1, 3),
            "record_date": dt.date(2024, 1, 2),
            "cash_div_per_share_pretax": 1.0,
            "bonus_ratio": 0.0,
            "conversion_ratio": 0.1,
            "split_ratio": 0.1,
            "source_event_count": 1,
            "hfq_mismatch_count": 0,
            "unclassified_mismatch_count": 0,
        }
    ])
    captured: dict[str, pd.DataFrame] = {}

    monkeypatch.setattr(ledger_mod, "datetime", FixedDatetime)
    monkeypatch.setattr(ledger_mod, "benchmark_assert", lambda client, params: None)
    monkeypatch.setattr(ledger_mod, "load_calendar", lambda client, start, end: calendar.copy())
    monkeypatch.setattr(ledger_mod, "load_targets", lambda client, params: targets.copy())
    monkeypatch.setattr(ledger_mod, "load_prices", lambda client, params, sec_codes, start, end: prices.copy())
    monkeypatch.setattr(ledger_mod, "load_benchmark", lambda client, params, start, end: {dt.date(2024, 1, 3): 0.0})
    monkeypatch.setattr(ledger_mod, "load_tail_risk_buy_guards", lambda client, params: {})
    monkeypatch.setattr(ledger_mod, "load_market_risk_off_signal_dates", lambda client, params: set())
    monkeypatch.setattr(
        ledger_mod,
        "load_corporate_action_events",
        lambda client, params, sec_codes, start, end: corporate_events.copy(),
    )
    monkeypatch.setattr(
        ledger_mod,
        "load_dataframe",
        lambda client, frame, table_id: captured.setdefault(table_id.rsplit(".", 1)[-1], frame.copy()),
    )

    run_ledger(
        object(),
        LedgerParams(
            project="data-aquarium",
            run_id="unit_run",
            backtest_id="unit_backtest",
            predict_start="2024-01-02",
            predict_end="2024-01-03",
            corporate_actions=CORPORATE_ACTIONS_CASH_DIV_AND_SPLIT,
        ),
    )

    trade_key = next(key for key in captured if key.endswith("backtest_trade_daily"))
    trades = captured[trade_key]
    day2_trades = trades[trades["trade_date"] == dt.date(2024, 1, 3)].reset_index(drop=True)

    assert day2_trades.loc[0, "fill_status"] == "CORPORATE_ACTION_SPLIT"
    assert day2_trades.loc[1, "fill_status"] == "CORPORATE_ACTION_CASH_DIVIDEND"
    assert day2_trades.loc[2, "side"] == "SELL"
    assert day2_trades.loc[2, "fill_status"] == "FILLED"
    assert day2_trades.loc[2, "filled_shares"] == 1100.0
