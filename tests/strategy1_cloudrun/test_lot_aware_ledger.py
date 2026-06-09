from __future__ import annotations

import datetime as dt
import math
import unittest

from scripts.strategy1_cloudrun.ledger import (
    LEDGER_VERSION_LOT100,
    LedgerParams,
    PlanRow,
    build_daily_plan,
    execute_plan,
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


def test_hash_holdings_is_order_invariant() -> None:
    assert hash_holdings({"000001.SZ": 200, "000002.SZ": 100}) == hash_holdings(
        {"000002.SZ": 100, "000001.SZ": 200}
    )
