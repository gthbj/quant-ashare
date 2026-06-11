"""Python implementation of Strategy 1 Cloud Run ledger.

The default implementation is the lot-aware `ledger_exec_v1_lot100` path.  The
legacy float-share `ledger_exec_v1` path is kept only for explicit audit runs.
Resume support is limited to deterministic lot-aware parent-state restore.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd
from google.cloud import bigquery

from scripts.strategy1_cloudrun.bq_io import execute_query, load_dataframe, query_dataframe
from quant_ashare.strategy1.dataset_roles import DEFAULT_OUTPUT_DATASET_ROLE, TableResolver

ALLOWED_TAIL_RISK_PROFILES = frozenset({
    "diagnostic_only",
    "individual_risk_guard_v0",
    "market_risk_off_v0",
    "individual_and_market_risk_guard_v0",
})
INDIVIDUAL_RISK_PROFILES = frozenset({"individual_risk_guard_v0", "individual_and_market_risk_guard_v0"})
MARKET_RISK_PROFILES = frozenset({"market_risk_off_v0", "individual_and_market_risk_guard_v0"})
DEFAULT_MARKET_STATE_VERSION = "market_state_v0_20260606"
LEDGER_VERSION_FLOAT = "ledger_exec_v1"
LEDGER_VERSION_LOT100 = "ledger_exec_v1_lot100"
LEDGER_VERSION_TOPDOWN_LOT100 = "ledger_exec_v2_lot100_topdown"
RESUME_POLICY_CLOUDRUN_LOT100 = "cloudrun_lot100_resume_v1"
RESUME_POLICY_CLOUDRUN_TOPDOWN_LOT100 = "cloudrun_lot100_topdown_resume_v1"
CASH_REDISTRIBUTION_NONE_V1 = "none_v1"
CASH_REDISTRIBUTION_TOPDOWN_WHOLE_ORDER_SKIP_V2 = "topdown_whole_order_skip_v2"
FILLED_STATUSES = frozenset({"FILLED", "FILLED_SCALED_CASH"})
LOT_AWARE_ZERO_FILL_STATUSES = frozenset({
    "BUY_SKIPPED_UNTRADABLE",
    "BUY_SKIPPED_TAIL_RISK",
    "BUY_SKIPPED_MARKET_RISK_OFF",
    "BUY_SKIPPED_BELOW_LOT",
    "BUY_SKIPPED_BELOW_LOT_AFTER_SCALE",
    "BUY_SKIPPED_CASH_INSUFFICIENT_AFTER_ROUNDING",
    "SELL_SKIPPED_UNTRADABLE",
    "SELL_SKIPPED_BELOW_LOT_PARTIAL",
    "PENDING_SELL_CARRY",
    "CANCELLED_BY_NETTING",
    "NOOP_ALREADY_TARGET",
})


@dataclasses.dataclass(frozen=True)
class LedgerParams:
    project: str
    run_id: str
    backtest_id: str
    output_dataset_role: str = DEFAULT_OUTPUT_DATASET_ROLE
    strategy_id: str = "ml_pv_clf_v0"
    predict_start: str = "2024-01-02"
    predict_end: str = "2025-12-31"
    initial_capital: float = 100000.0
    benchmark: str = "000001.SH"
    commission_bps: float = 1.0
    min_commission_cny: float = 0.0
    stamp_tax_buy_bps: float = 0.0
    stamp_tax_sell_bps: float = 5.0
    slippage_buy_bps: float = 5.0
    slippage_sell_bps: float = 5.0
    ledger_version: str = LEDGER_VERSION_LOT100
    lot_size: int = 100
    min_buy_lot: int = 1
    sell_odd_lot_policy: str = "allow_full_exit_odd_lot"
    partial_sell_rounding: str = "floor_to_lot_keep_residual"
    buy_rounding: str = "floor_to_lot"
    cash_redistribution: str = CASH_REDISTRIBUTION_NONE_V1
    min_notional_cny: float = 0.0
    force_replace: bool = False
    rebalance_frequency: str = "weekly"
    target_holdings: int = 5
    max_single_weight: float = 0.20
    label_horizon: int = 5
    horizon_natural_frequency: str = "weekly"
    initial_state_mode: str = "fresh"
    parent_backtest_id: str | None = None
    state_as_of_date: str | None = None
    resume_policy_id: str = RESUME_POLICY_CLOUDRUN_LOT100
    rebalance_anchor_start: str | None = None
    tail_risk_profile_id: str = "diagnostic_only"
    market_state_version: str = DEFAULT_MARKET_STATE_VERSION
    position_floor_count: int = 20
    min_position_weight: float | None = None
    walk_depth: int = 50



@dataclasses.dataclass(frozen=True)
class ResumeSnapshot:
    cash_cny: float
    previous_nav_value: float
    holdings: dict[str, float]
    pending_sell: set[str]
    target_weights: dict[str, dict[str, Any]]
    active_signal_date: Any | None
    ledger_params_hash: str
    rebalance_anchor_start: Any


def run_ledger(client: bigquery.Client, params: LedgerParams) -> dict[str, int]:
    validate_ledger_params(params)
    if params.tail_risk_profile_id not in ALLOWED_TAIL_RISK_PROFILES:
        raise ValueError(f"unsupported tail_risk_profile_id: {params.tail_risk_profile_id}")
    if params.force_replace:
        clear_ledger_outputs(client, params)

    calendar_end = (pd.Timestamp(params.predict_end) + pd.Timedelta(days=90)).date().isoformat()
    calendar_start = min_iso_date(params.predict_start, params.state_as_of_date, params.rebalance_anchor_start)
    price_start = min_iso_date(
        (pd.Timestamp(params.predict_start) - pd.Timedelta(days=10)).date().isoformat(),
        params.state_as_of_date,
        params.rebalance_anchor_start,
    )
    benchmark_assert(client, params)

    cal = load_calendar(client, calendar_start, calendar_end)
    exec_days = cal[(cal["trade_date"] >= pd.to_datetime(params.predict_start).date()) & (cal["trade_date"] <= pd.to_datetime(params.predict_end).date())].copy()
    exec_days = exec_days.sort_values("trade_date").reset_index(drop=True)
    resume_snapshot = load_resume_snapshot(client, params, cal) if params.initial_state_mode == "resume_from_backtest" else None
    targets = load_targets(client, params)
    if targets.empty and resume_snapshot is None:
        raise RuntimeError(f"no portfolio targets for run_id={params.run_id}")
    periods = build_periods(targets, cal, params) if not targets.empty else pd.DataFrame(columns=["signal_date", "exec_date"])
    if periods.empty and resume_snapshot is None:
        raise RuntimeError(f"no executable rebalance periods for run_id={params.run_id}")

    if targets.empty or periods.empty:
        presence = pd.DataFrame(columns=["sec_code"])
    else:
        presence = targets.merge(periods, left_on="rebalance_date", right_on="signal_date", how="inner")
    sec_codes = set(str(v) for v in presence["sec_code"].dropna().unique().tolist())
    if resume_snapshot is not None:
        sec_codes.update(resume_snapshot.holdings)
        sec_codes.update(resume_snapshot.pending_sell)
        sec_codes.update(resume_snapshot.target_weights)
    prices = load_prices(client, params, sorted(sec_codes), price_start, calendar_end)
    px = PriceBook(prices)
    benchmark = load_benchmark(client, params, params.predict_start, calendar_end)

    if resume_snapshot is not None:
        cash = float(resume_snapshot.cash_cny)
        holdings = dict(resume_snapshot.holdings)
        target_weights = dict(resume_snapshot.target_weights)
        pending_sell = set(resume_snapshot.pending_sell)
        previous_nav_value: float | None = float(resume_snapshot.previous_nav_value)
        active_signal_date = resume_snapshot.active_signal_date
    else:
        cash = float(params.initial_capital)
        holdings: dict[str, float] = {}
        target_weights: dict[str, dict[str, Any]] = {}
        pending_sell: set[str] = set()
        previous_nav_value = None
        active_signal_date = None

    trade_rows: list[dict[str, Any]] = []
    position_rows: list[dict[str, Any]] = []
    nav_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    params_hash = ledger_params_hash(params)
    anchor_start = effective_rebalance_anchor_start(params)

    periods_by_exec = {row.exec_date: row for row in periods.itertuples(index=False)}
    targets_by_signal = build_target_specs_by_signal(targets) if not targets.empty else {}
    tail_risk_buy_guards = load_tail_risk_buy_guards(client, params)
    market_risk_off_signal_dates = load_market_risk_off_signal_dates(client, params)

    for exec_date in exec_days["trade_date"]:
        period = periods_by_exec.get(exec_date)
        is_rebalance = period is not None
        if is_rebalance:
            active_signal_date = period.signal_date
            target_weights = targets_by_signal.get(period.signal_date, {})

        nav_before = cash + sum(shares * px.valuation_price(sec, exec_date) for sec, shares in holdings.items())
        plan = build_daily_plan(
            exec_date,
            is_rebalance,
            cash,
            holdings,
            target_weights,
            pending_sell,
            tail_risk_buy_guards.get(period.signal_date, set()) if is_rebalance else set(),
            period.signal_date in market_risk_off_signal_dates if is_rebalance else False,
            nav_before,
            px,
            params,
        )
        cash, daily_trade_rows = execute_plan(exec_date, cash, plan, params, is_rebalance=is_rebalance)
        trade_rows.extend(daily_trade_rows)
        holdings = update_holdings(plan)
        pending_sell = update_pending_sell(plan, is_rebalance)

        position_value = 0.0
        for sec, shares in sorted(holdings.items()):
            close = px.close_price(sec, exec_date)
            if close is None or not np.isfinite(close):
                continue
            mv = shares * close
            position_value += mv
            position_rows.append({
                "backtest_id": params.backtest_id,
                "trade_date": exec_date,
                "sec_code": sec,
                "shares": shares,
                "close": close,
                "market_value_cny": mv,
                "weight": None,
                "unrealized_pnl_cny": None,
                "run_id": params.run_id,
                "created_at": datetime.now(timezone.utc),
            })
        nav_value = cash + position_value
        daily_return = None if previous_nav_value is None else nav_value / previous_nav_value - 1.0
        previous_nav_value = nav_value
        bench_ret = benchmark.get(exec_date, 0.0)
        day_turnover = sum(row["turnover_cny"] for row in daily_trade_rows if row["fill_status"] in FILLED_STATUSES)
        day_cost = sum(row["fee_cny"] for row in daily_trade_rows if row["fill_status"] in FILLED_STATUSES)
        nav_row = {
            "backtest_id": params.backtest_id,
            "trade_date": exec_date,
            "nav": nav_value / params.initial_capital,
            "cash_cny": cash,
            "net_value_cny": nav_value,
            "gross_exposure": safe_divide(position_value, nav_value),
            "turnover_cny": day_turnover,
            "cost_cny": day_cost,
            "daily_return": daily_return,
            "benchmark_sec_code": params.benchmark,
            "benchmark_return": bench_ret,
            "excess_return": (daily_return or 0.0) - (bench_ret or 0.0),
            "run_id": params.run_id,
            "created_at": datetime.now(timezone.utc),
        }
        nav_rows.append(nav_row)
        state_rows.append({
            "backtest_id": params.backtest_id,
            "trade_date": exec_date,
            "cash_cny": cash,
            "net_value_cny": nav_value,
            "nav": nav_row["nav"],
            "pending_sell_sec_codes_json": json.dumps(sorted(pending_sell), separators=(",", ":")),
            "active_signal_date": active_signal_date,
            "active_target_weights_json": json.dumps(
                normalize_target_weights(target_weights),
                sort_keys=True,
                separators=(",", ":"),
            ),
            "holdings_hash": hash_holdings(holdings),
            "ledger_version": params.ledger_version,
            "ledger_params_hash": params_hash,
            "resume_policy_id": params.resume_policy_id,
            "rebalance_anchor_start": anchor_start,
            "run_id": params.run_id,
            "created_at": datetime.now(timezone.utc),
        })

    nav_by_date = {row["trade_date"]: row["net_value_cny"] for row in nav_rows}
    for row in position_rows:
        row["weight"] = safe_divide(row["market_value_cny"], nav_by_date[row["trade_date"]])

    tables = TableResolver(dataset_role=params.output_dataset_role, project=params.project)
    load_dataframe(client, pd.DataFrame(trade_rows), tables.fqn("backtest_trade_daily"))
    load_dataframe(client, pd.DataFrame(position_rows), tables.fqn("backtest_position_daily"))
    load_dataframe(client, pd.DataFrame(nav_rows), tables.fqn("backtest_nav_daily"))
    load_dataframe(client, pd.DataFrame(state_rows), tables.fqn("backtest_ledger_state_daily"))
    return {"trades": len(trade_rows), "positions": len(position_rows), "nav": len(nav_rows), "state": len(state_rows)}


@dataclasses.dataclass
class PlanRow:
    sec_code: str
    cur_shares: float
    exec_open: float | None
    buy_fill_price: float | None
    sell_fill_price: float | None
    can_buy: bool
    can_sell: bool
    val_price: float
    desired_value: float
    cur_value: float
    was_pending: bool
    sell_shares: float
    want_value: float
    sell_skip_shares: float
    buy_skip_value: float
    tail_risk_new_buy_blocked: bool
    market_risk_buy_blocked: bool
    pending_noop: bool
    target_rank_raw: float | None = None
    filter_reason: str | None = None
    buy_skip_status: str | None = None
    sell_skip_status: str | None = None
    filled_sell_shares: float = 0.0
    filled_buy_shares: float = 0.0
    scale: float = 1.0


class PriceBook:
    def __init__(self, prices: pd.DataFrame):
        prices = prices.sort_values(["sec_code", "trade_date"]).copy()
        prices["close_ffill"] = prices.groupby("sec_code")["close"].ffill()
        prices["prev_close_ffill"] = prices.groupby("sec_code")["close_ffill"].shift(1)
        self.by_key = {(row.sec_code, row.trade_date): row for row in prices.itertuples(index=False)}

    def row(self, sec_code: str, trade_date: Any):
        return self.by_key.get((sec_code, trade_date))

    def valuation_price(self, sec_code: str, trade_date: Any) -> float:
        row = self.row(sec_code, trade_date)
        if row is None:
            return 0.0
        return first_finite(row.prev_close_ffill, row.open, row.close_ffill, default=0.0)

    def close_price(self, sec_code: str, trade_date: Any) -> float | None:
        row = self.row(sec_code, trade_date)
        if row is None:
            return None
        return first_finite(row.close_ffill, row.open, default=None)


def build_daily_plan(
    exec_date: Any,
    is_rebalance: bool,
    cash: float,
    holdings: dict[str, float],
    target_weights: dict[str, dict[str, Any]],
    pending_sell: set[str],
    tail_risk_blocked_new_buys: set[str],
    market_risk_off_signal: bool,
    nav_before: float,
    px: PriceBook,
    params: LedgerParams,
) -> list[PlanRow]:
    if is_topdown_lot100(params):
        return build_daily_plan_topdown(
            exec_date,
            is_rebalance,
            cash,
            holdings,
            target_weights,
            pending_sell,
            market_risk_off_signal,
            nav_before,
            px,
            params,
        )
    universe = set(holdings)
    if is_rebalance:
        universe |= set(target_weights)
    universe |= set(pending_sell)
    plan = []
    for sec in sorted(universe):
        row = px.row(sec, exec_date)
        cur_shares = float(holdings.get(sec, 0.0))
        exec_open = first_finite(getattr(row, "open", None), default=None) if row is not None else None
        can_buy = bool(getattr(row, "can_buy_open", False)) if row is not None else False
        can_sell = bool(getattr(row, "can_sell_open", False)) if row is not None else False
        val_price = px.valuation_price(sec, exec_date)
        target_spec = target_weights.get(sec, {})
        w = float(target_spec.get("target_weight", 0.0) or 0.0)
        rank_raw = target_spec.get("rank_raw")
        cur_value = cur_shares * val_price
        desired_value = w * nav_before
        can_buy_now = can_buy and exec_open is not None and np.isfinite(exec_open)
        can_sell_now = can_sell and exec_open is not None and np.isfinite(exec_open)
        tail_risk_new_buy_blocked = (
            has_individual_risk_guard(params.tail_risk_profile_id)
            and is_rebalance
            and sec in tail_risk_blocked_new_buys
            and cur_shares <= 0.000001
        )
        market_risk_buy_blocked = (
            has_market_risk_guard(params.tail_risk_profile_id)
            and is_rebalance
            and market_risk_off_signal
        )
        sell_shares = 0.0
        sell_skip_status = None
        sell_gap_value = cur_value - desired_value
        has_sell_intent = cur_shares > 0 and (is_rebalance or sec in pending_sell) and sell_gap_value > 0.01
        if has_sell_intent and can_sell_now:
            raw_sell_shares = cur_shares if desired_value <= 0.01 else min(cur_shares, sell_gap_value / exec_open)
            if is_lot_aware(params) and desired_value > 0.01:
                sell_shares = round_down_to_lot(raw_sell_shares, params.lot_size)
                if sell_shares < params.lot_size and raw_sell_shares > 0.000001:
                    sell_shares = 0.0
                    sell_skip_status = "SELL_SKIPPED_BELOW_LOT_PARTIAL"
            else:
                sell_shares = raw_sell_shares
        want_value = 0.0
        if (
            is_rebalance
            and can_buy_now
            and desired_value - cur_value > 0.01
            and not tail_risk_new_buy_blocked
            and not market_risk_buy_blocked
        ):
            want_value = desired_value - cur_value
        sell_skip_shares = 0.0
        if sell_skip_status == "SELL_SKIPPED_BELOW_LOT_PARTIAL":
            sell_skip_shares = min(cur_shares, safe_divide(sell_gap_value, exec_open))
        elif has_sell_intent and not can_sell_now:
            denom = exec_open if exec_open is not None and np.isfinite(exec_open) else val_price
            sell_skip_shares = cur_shares if desired_value <= 0.01 else min(cur_shares, safe_divide(sell_gap_value, denom))
            sell_skip_status = "SELL_SKIPPED_UNTRADABLE" if is_rebalance else "PENDING_SELL_CARRY"
        buy_skip_value = 0.0
        if is_rebalance and desired_value - cur_value > 0.01 and (
            not can_buy_now
            or tail_risk_new_buy_blocked
            or market_risk_buy_blocked
        ):
            buy_skip_value = desired_value - cur_value
        pending_noop = sec in pending_sell and cur_shares > 0 and not (cur_value - desired_value > 0.01)
        plan.append(PlanRow(
            sec_code=sec,
            cur_shares=cur_shares,
            exec_open=exec_open,
            buy_fill_price=exec_open * (1 + params.slippage_buy_bps / 10000.0) if exec_open else None,
            sell_fill_price=exec_open * (1 - params.slippage_sell_bps / 10000.0) if exec_open else None,
            can_buy=can_buy,
            can_sell=can_sell,
            val_price=val_price,
            desired_value=desired_value,
            cur_value=cur_value,
            was_pending=sec in pending_sell,
            sell_shares=sell_shares,
            want_value=want_value,
            sell_skip_shares=sell_skip_shares,
            buy_skip_value=buy_skip_value,
            tail_risk_new_buy_blocked=tail_risk_new_buy_blocked,
            market_risk_buy_blocked=market_risk_buy_blocked,
            pending_noop=pending_noop,
            target_rank_raw=float(rank_raw) if rank_raw is not None and pd.notna(rank_raw) else None,
            sell_skip_status=sell_skip_status,
        ))
    return plan


def build_daily_plan_topdown(
    exec_date: Any,
    is_rebalance: bool,
    cash: float,
    holdings: dict[str, float],
    candidate_specs: dict[str, dict[str, Any]],
    pending_sell: set[str],
    market_risk_off_signal: bool,
    nav_before: float,
    px: PriceBook,
    params: LedgerParams,
) -> list[PlanRow]:
    if not is_rebalance:
        return build_pending_sell_retry_plan(exec_date, holdings, pending_sell, px, params)

    min_weight = effective_min_position_weight(params)
    retained: set[str] = set()
    sell_rows: list[PlanRow] = []
    buy_rows: list[PlanRow] = []
    audit_rows: list[PlanRow] = []
    available_cash = float(cash)

    ranked_candidates = sorted(
        (
            (sec, spec)
            for sec, spec in candidate_specs.items()
            if candidate_rank(spec) is not None and candidate_rank(spec) <= params.walk_depth
        ),
        key=lambda item: (candidate_rank(item[1]) or 1_000_000, item[0]),
    )
    candidate_secs = {sec for sec, _ in ranked_candidates}

    for sec, cur_shares in sorted(holdings.items()):
        spec = candidate_specs.get(sec, {})
        rank = candidate_rank(spec)
        keep = rank is not None and rank <= params.walk_depth
        if keep:
            retained.add(sec)
            continue
        item = base_plan_row(sec, exec_date, float(cur_shares), 0.0, px, params, spec)
        if item.cur_shares <= 0.000001:
            continue
        expected_sell_price = item.sell_fill_price
        if expected_sell_price is None and item.val_price > 0:
            expected_sell_price = item.val_price * (1 - params.slippage_sell_bps / 10000.0)
        if item.can_sell and expected_sell_price is not None and expected_sell_price > 0:
            turnover = item.cur_shares * expected_sell_price
            fee = max(turnover * params.commission_bps / 10000.0, params.min_commission_cny)
            tax = turnover * params.stamp_tax_sell_bps / 10000.0
            available_cash += turnover - fee - tax
        if item.can_sell and item.sell_fill_price is not None:
            item.sell_shares = item.cur_shares
        else:
            item.sell_skip_shares = item.cur_shares
            item.sell_skip_status = "SELL_SKIPPED_UNTRADABLE"
        sell_rows.append(item)

    if market_risk_off_signal and has_market_risk_guard(params.tail_risk_profile_id):
        for sec, spec in ranked_candidates:
            if sec in retained or sec in holdings:
                continue
            item = base_plan_row(sec, exec_date, 0.0, 0.0, px, params, spec)
            item.buy_skip_value = min_weight * nav_before
            item.market_risk_buy_blocked = True
            item.buy_skip_status = "BUY_SKIPPED_MARKET_RISK_OFF"
            audit_rows.append(item)
        return sell_rows + audit_rows

    for sec, spec in ranked_candidates:
        if sec in retained or sec in holdings:
            continue
        item = base_plan_row(sec, exec_date, 0.0, 0.0, px, params, spec)
        if is_tail_risk_candidate(spec) and has_individual_risk_guard(params.tail_risk_profile_id):
            item.buy_skip_value = min_weight * nav_before
            item.tail_risk_new_buy_blocked = True
            item.buy_skip_status = "BUY_SKIPPED_TAIL_RISK"
            audit_rows.append(item)
            continue
        if not item.can_buy or item.exec_open is None or not np.isfinite(item.exec_open):
            item.buy_skip_value = min_weight * nav_before
            item.buy_skip_status = "BUY_SKIPPED_UNTRADABLE"
            audit_rows.append(item)
            continue

        desired_shares = topdown_min_buy_shares(nav_before, item.exec_open, min_weight, params)
        if desired_shares < min_buy_shares(params):
            item.buy_skip_value = min_weight * nav_before
            item.buy_skip_status = "BUY_SKIPPED_BELOW_LOT"
            audit_rows.append(item)
            continue
        probe = build_buy_execution(item, desired_shares, params, "FILLED")
        if available_cash + 1e-6 >= probe.cash_required:
            item.want_value = desired_shares * item.exec_open
            available_cash -= probe.cash_required
            buy_rows.append(item)
        else:
            item.buy_skip_value = desired_shares * item.exec_open
            item.buy_skip_status = "BUY_SKIPPED_CASH_INSUFFICIENT_AFTER_ROUNDING"
            audit_rows.append(item)
        if available_cash < min_weight * nav_before:
            break

    # Include pending sells that are no longer in holdings defensively as no-ops are omitted.
    missing_pending = sorted(sec for sec in pending_sell - set(holdings) - candidate_secs)
    for sec in missing_pending:
        item = base_plan_row(sec, exec_date, 0.0, 0.0, px, params, {})
        item.pending_noop = True
        audit_rows.append(item)

    return sell_rows + buy_rows + audit_rows


def build_pending_sell_retry_plan(
    exec_date: Any,
    holdings: dict[str, float],
    pending_sell: set[str],
    px: PriceBook,
    params: LedgerParams,
) -> list[PlanRow]:
    plan: list[PlanRow] = []
    for sec in sorted(set(holdings) | set(pending_sell)):
        item = base_plan_row(sec, exec_date, float(holdings.get(sec, 0.0)), 0.0, px, params, {})
        item.was_pending = sec in pending_sell
        if item.cur_shares <= 0.000001:
            continue
        if sec in pending_sell:
            if item.can_sell and item.sell_fill_price is not None:
                item.sell_shares = item.cur_shares
            else:
                item.sell_skip_shares = item.cur_shares
                item.sell_skip_status = "PENDING_SELL_CARRY"
        plan.append(item)
    return plan


def base_plan_row(
    sec: str,
    exec_date: Any,
    cur_shares: float,
    desired_value: float,
    px: PriceBook,
    params: LedgerParams,
    spec: dict[str, Any],
) -> PlanRow:
    row = px.row(sec, exec_date)
    exec_open = first_finite(getattr(row, "open", None), default=None) if row is not None else None
    can_buy = bool(getattr(row, "can_buy_open", False)) if row is not None else False
    can_sell = bool(getattr(row, "can_sell_open", False)) if row is not None else False
    val_price = px.valuation_price(sec, exec_date)
    cur_value = cur_shares * val_price
    rank_raw = spec.get("rank_raw")
    return PlanRow(
        sec_code=sec,
        cur_shares=cur_shares,
        exec_open=exec_open,
        buy_fill_price=exec_open * (1 + params.slippage_buy_bps / 10000.0) if exec_open else None,
        sell_fill_price=exec_open * (1 - params.slippage_sell_bps / 10000.0) if exec_open else None,
        can_buy=can_buy,
        can_sell=can_sell,
        val_price=val_price,
        desired_value=desired_value,
        cur_value=cur_value,
        was_pending=False,
        sell_shares=0.0,
        want_value=0.0,
        sell_skip_shares=0.0,
        buy_skip_value=0.0,
        tail_risk_new_buy_blocked=False,
        market_risk_buy_blocked=False,
        pending_noop=False,
        target_rank_raw=float(rank_raw) if rank_raw is not None and pd.notna(rank_raw) else None,
        filter_reason=spec.get("filter_reason"),
    )


def effective_min_position_weight(params: LedgerParams) -> float:
    if params.min_position_weight is not None:
        return float(params.min_position_weight)
    return 1.0 / float(params.position_floor_count)


def topdown_min_buy_shares(nav_value: float, open_price: float, min_weight: float, params: LedgerParams) -> float:
    lot_notional = params.lot_size * open_price
    lots = math.ceil((min_weight * nav_value) / lot_notional)
    return float(max(params.min_buy_lot, lots) * params.lot_size)


def candidate_rank(spec: dict[str, Any]) -> float | None:
    rank = spec.get("rank_raw")
    if rank is None or pd.isna(rank):
        return None
    value = float(rank)
    return value if math.isfinite(value) else None


def is_tail_risk_candidate(spec: dict[str, Any]) -> bool:
    return str(spec.get("filter_reason") or "").startswith("tail_risk:")


def execute_plan(
    exec_date: Any,
    cash: float,
    plan: list[PlanRow],
    params: LedgerParams,
    *,
    is_rebalance: bool,
) -> tuple[float, list[dict[str, Any]]]:
    if is_lot_aware(params):
        return execute_plan_lot_aware(exec_date, cash, plan, params)
    return execute_plan_float(exec_date, cash, plan, params, is_rebalance=is_rebalance)


def execute_plan_float(
    exec_date: Any,
    cash: float,
    plan: list[PlanRow],
    params: LedgerParams,
    *,
    is_rebalance: bool,
) -> tuple[float, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    for item in plan:
        if item.sell_shares > 0.000001:
            turnover = item.sell_shares * item.sell_fill_price
            fee = max(turnover * params.commission_bps / 10000.0, params.min_commission_cny)
            tax = turnover * params.stamp_tax_sell_bps / 10000.0
            cash_effect = turnover - fee - tax
            cash += cash_effect
            item.filled_sell_shares = item.sell_shares
            rows.append(trade_row(params, exec_date, item, "SELL", item.sell_shares, item.sell_shares, item.sell_fill_price, turnover, fee, tax, slippage_sell(turnover, params), cash_effect, "FILLED"))
    required_cash = 0.0
    for item in plan:
        if item.want_value > 0.000001:
            gross = item.want_value * (1 + params.slippage_buy_bps / 10000.0)
            required_cash += gross + max(gross * params.commission_bps / 10000.0, params.min_commission_cny) + gross * params.stamp_tax_buy_bps / 10000.0
    scale = min(1.0, safe_divide(cash, required_cash)) if required_cash > 0 else 1.0
    for item in plan:
        item.scale = scale
        if item.want_value > 0.000001 and scale > 0.000001:
            gross = item.want_value * scale * (1 + params.slippage_buy_bps / 10000.0)
            fee = max(gross * params.commission_bps / 10000.0, params.min_commission_cny)
            tax = gross * params.stamp_tax_buy_bps / 10000.0
            cash_effect = -(gross + fee + tax)
            cash += cash_effect
            planned_shares = safe_divide(item.want_value, item.exec_open)
            filled_shares = safe_divide(item.want_value * scale, item.exec_open)
            item.filled_buy_shares = filled_shares
            rows.append(trade_row(params, exec_date, item, "BUY", planned_shares, filled_shares, item.buy_fill_price, gross, fee, tax, slippage_buy(gross, params), cash_effect, "FILLED_SCALED_CASH" if scale < 0.999999 else "FILLED"))
        elif item.want_value > 0.000001 and scale <= 0.000001:
            rows.append(trade_row(params, exec_date, item, "BUY", safe_divide(item.want_value, item.exec_open), 0.0, None, 0.0, 0.0, 0.0, 0.0, 0.0, "SKIPPED_CASH_INSUFFICIENT"))
        if item.sell_skip_shares > 0.000001:
            status = item.sell_skip_status or ("SELL_SKIPPED_UNTRADABLE" if is_rebalance else "PENDING_SELL_CARRY")
            rows.append(trade_row(params, exec_date, item, "SELL", item.sell_skip_shares, 0.0, None, 0.0, 0.0, 0.0, 0.0, 0.0, status))
        if item.buy_skip_value > 0.000001:
            if item.buy_skip_status:
                status = item.buy_skip_status
            elif item.market_risk_buy_blocked:
                status = "BUY_SKIPPED_MARKET_RISK_OFF"
            elif item.tail_risk_new_buy_blocked:
                status = "BUY_SKIPPED_TAIL_RISK"
            else:
                status = "BUY_SKIPPED_UNTRADABLE"
            rows.append(trade_row(params, exec_date, item, "BUY", safe_divide(item.buy_skip_value, item.val_price), 0.0, None, 0.0, 0.0, 0.0, 0.0, 0.0, status))
        if item.pending_noop:
            rows.append(trade_row(params, exec_date, item, "SELL", 0.0, 0.0, None, 0.0, 0.0, 0.0, 0.0, 0.0, "CANCELLED_BY_NETTING"))
    return cash, rows


@dataclasses.dataclass
class BuyExecution:
    item: PlanRow
    planned_shares: float
    filled_shares: float
    turnover: float
    fee: float
    tax: float
    slippage: float
    cash_required: float
    fill_status: str


def execute_plan_lot_aware(
    exec_date: Any,
    cash: float,
    plan: list[PlanRow],
    params: LedgerParams,
) -> tuple[float, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    for item in plan:
        if item.sell_shares > 0.000001:
            turnover = item.sell_shares * item.sell_fill_price
            fee = max(turnover * params.commission_bps / 10000.0, params.min_commission_cny)
            tax = turnover * params.stamp_tax_sell_bps / 10000.0
            cash_effect = turnover - fee - tax
            cash += cash_effect
            item.filled_sell_shares = item.sell_shares
            rows.append(trade_row(
                params, exec_date, item, "SELL", item.sell_shares, item.sell_shares,
                item.sell_fill_price, turnover, fee, tax, slippage_sell(turnover, params),
                cash_effect, "FILLED",
            ))

    buy_items = [item for item in plan if item.want_value > 0.000001]
    provisional: list[BuyExecution] = []
    for item in buy_items:
        planned_shares = round_down_to_lot(safe_divide(item.want_value, item.exec_open), params.lot_size)
        if planned_shares < min_buy_shares(params):
            rows.append(trade_row(
                params, exec_date, item, "BUY", safe_divide(item.want_value, item.exec_open),
                0.0, None, 0.0, 0.0, 0.0, 0.0, 0.0, "BUY_SKIPPED_BELOW_LOT",
            ))
            continue
        provisional.append(build_buy_execution(item, planned_shares, params, "FILLED"))

    required_cash = sum(order.cash_required for order in provisional)
    scale = min(1.0, safe_divide(cash, required_cash)) if required_cash > 0 else 1.0
    executable: list[BuyExecution] = []
    if is_topdown_lot100(params):
        executable = provisional
    elif scale >= 0.999999:
        executable = provisional
    else:
        for order in provisional:
            item = order.item
            item.scale = scale
            scaled_shares = round_down_to_lot(safe_divide(item.want_value * scale, item.exec_open), params.lot_size)
            if scaled_shares < min_buy_shares(params):
                rows.append(trade_row(
                    params, exec_date, item, "BUY", order.planned_shares, 0.0, None,
                    0.0, 0.0, 0.0, 0.0, 0.0, "BUY_SKIPPED_BELOW_LOT_AFTER_SCALE",
                ))
                continue
            executable.append(build_buy_execution(item, scaled_shares, params, "FILLED_SCALED_CASH"))

    executable = drop_buys_until_cash_nonnegative(executable, cash, params, exec_date, rows)
    for order in executable:
        item = order.item
        cash -= order.cash_required
        item.filled_buy_shares = order.filled_shares
        rows.append(trade_row(
            params, exec_date, item, "BUY", order.planned_shares, order.filled_shares,
            item.buy_fill_price, order.turnover, order.fee, order.tax, order.slippage,
            -order.cash_required, order.fill_status,
        ))

    for item in plan:
        if item.sell_skip_shares > 0.000001:
            rows.append(trade_row(
                params, exec_date, item, "SELL", item.sell_skip_shares, 0.0, None,
                0.0, 0.0, 0.0, 0.0, 0.0, item.sell_skip_status or "SELL_SKIPPED_UNTRADABLE",
            ))
        if item.buy_skip_value > 0.000001:
            if item.buy_skip_status:
                status = item.buy_skip_status
            elif item.market_risk_buy_blocked:
                status = "BUY_SKIPPED_MARKET_RISK_OFF"
            elif item.tail_risk_new_buy_blocked:
                status = "BUY_SKIPPED_TAIL_RISK"
            else:
                status = "BUY_SKIPPED_UNTRADABLE"
            rows.append(trade_row(params, exec_date, item, "BUY", safe_divide(item.buy_skip_value, item.val_price), 0.0, None, 0.0, 0.0, 0.0, 0.0, 0.0, status))
        if item.pending_noop:
            rows.append(trade_row(params, exec_date, item, "SELL", 0.0, 0.0, None, 0.0, 0.0, 0.0, 0.0, 0.0, "CANCELLED_BY_NETTING"))

    if cash < -1.0:
        raise RuntimeError(f"lot-aware ledger produced negative cash {cash:.4f} on {exec_date}")
    return cash, rows


def update_holdings(plan: list[PlanRow]) -> dict[str, float]:
    holdings = {}
    for item in plan:
        shares = item.cur_shares - item.filled_sell_shares + item.filled_buy_shares
        if shares > 0.000001:
            holdings[item.sec_code] = shares
    return holdings


def update_pending_sell(plan: list[PlanRow], is_rebalance: bool) -> set[str]:
    pending = set()
    for item in plan:
        if item.sell_skip_status == "SELL_SKIPPED_BELOW_LOT_PARTIAL":
            continue
        remaining_shares = item.cur_shares - item.filled_sell_shares
        remaining_value = remaining_shares * item.val_price
        if remaining_shares > 0.000001 and remaining_value - item.desired_value > 0.01 and (
            item.sell_skip_shares > 0.000001 or item.was_pending or is_rebalance
        ):
            pending.add(item.sec_code)
    return pending


def trade_row(
    params: LedgerParams,
    trade_date: Any,
    item: PlanRow,
    side: str,
    planned_shares: float,
    filled_shares: float,
    fill_price: float | None,
    turnover: float,
    fee: float,
    tax: float,
    slippage: float,
    cash_effect: float,
    fill_status: str,
) -> dict[str, Any]:
    return {
        "backtest_id": params.backtest_id,
        "trade_date": trade_date,
        "sec_code": item.sec_code,
        "side": side,
        "planned_shares": planned_shares,
        "filled_shares": filled_shares,
        "fill_price": fill_price,
        "turnover_cny": turnover,
        "fee_cny": fee + tax,
        "tax_cny": tax,
        "slippage_cny": slippage,
        "cash_effect_cny": cash_effect,
        "fill_status": fill_status,
        "run_id": params.run_id,
        "created_at": datetime.now(timezone.utc),
    }


def clear_ledger_outputs(client: bigquery.Client, params: LedgerParams) -> None:
    tables = TableResolver(dataset_role=params.output_dataset_role, project=params.project)
    calendar_end = (pd.Timestamp(params.predict_end) + pd.Timedelta(days=90)).date().isoformat()
    qparams = [
        bigquery.ScalarQueryParameter("backtest_id", "STRING", params.backtest_id),
        bigquery.ScalarQueryParameter("start_date", "DATE", params.predict_start),
        bigquery.ScalarQueryParameter("end_date", "DATE", calendar_end),
    ]
    for role in (
        "backtest_trade_daily",
        "backtest_position_daily",
        "backtest_nav_daily",
        "backtest_ledger_state_daily",
    ):
        execute_query(
            client,
            f"DELETE FROM `{tables.fqn(role)}` WHERE backtest_id=@backtest_id AND trade_date BETWEEN @start_date AND @end_date",
            qparams,
        )
    execute_query(
        client,
        f"DELETE FROM `{tables.fqn('backtest_summary')}` WHERE backtest_id=@backtest_id",
        [bigquery.ScalarQueryParameter("backtest_id", "STRING", params.backtest_id)],
    )


def benchmark_assert(client: bigquery.Client, params: LedgerParams) -> None:
    sql = """
    SELECT COUNT(*) AS n
    FROM `data-aquarium.ashare_dim.dim_index`
    WHERE sec_code = @benchmark AND has_daily AND is_benchmark_candidate
    """
    frame = query_dataframe(client, sql, [bigquery.ScalarQueryParameter("benchmark", "STRING", params.benchmark)])
    if int(frame.iloc[0]["n"]) != 1:
        raise RuntimeError(f"benchmark {params.benchmark} is not an available benchmark candidate")


def load_calendar(client: bigquery.Client, start: str, end: str) -> pd.DataFrame:
    sql = """
    SELECT cal_date AS trade_date, trade_date_seq
    FROM `data-aquarium.ashare_dim.dim_trade_calendar`
    WHERE exchange='SSE' AND is_open=1 AND cal_date BETWEEN @start AND @end
    ORDER BY cal_date
    """
    return normalize_dates(query_dataframe(client, sql, [
        bigquery.ScalarQueryParameter("start", "DATE", start),
        bigquery.ScalarQueryParameter("end", "DATE", end),
    ]), ["trade_date"])



def min_iso_date(*values: str | None) -> str:
    present = [v for v in values if v]
    if not present:
        raise ValueError("At least one date is required")
    return min(present)


def effective_rebalance_anchor_start(params: LedgerParams) -> str:
    return params.rebalance_anchor_start or params.predict_start


def normalize_target_weights(target_weights: dict[str, dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    normalized: dict[str, dict[str, float | int]] = {}
    for sec_code, spec in sorted(target_weights.items()):
        item: dict[str, float | int] = {"target_weight": float(spec.get("target_weight", 0.0) or 0.0)}
        if spec.get("rank_raw") is not None and pd.notna(spec.get("rank_raw")):
            item["rank_raw"] = int(spec["rank_raw"])
        normalized[str(sec_code)] = item
    return normalized


def ledger_params_hash(params: LedgerParams) -> str:
    payload = {
        "benchmark": params.benchmark,
        "buy_rounding": params.buy_rounding,
        "cash_redistribution": params.cash_redistribution,
        "commission_bps": params.commission_bps,
        "horizon_natural_frequency": params.horizon_natural_frequency,
        "initial_capital": params.initial_capital,
        "label_horizon": params.label_horizon,
        "ledger_version": params.ledger_version,
        "lot_size": params.lot_size,
        "market_state_version": params.market_state_version,
        "max_single_weight": params.max_single_weight,
        "min_buy_lot": params.min_buy_lot,
        "min_commission_cny": params.min_commission_cny,
        "min_notional_cny": params.min_notional_cny,
        "partial_sell_rounding": params.partial_sell_rounding,
        "rebalance_anchor_start": effective_rebalance_anchor_start(params),
        "rebalance_frequency": params.rebalance_frequency,
        "resume_policy_id": params.resume_policy_id,
        "sell_odd_lot_policy": params.sell_odd_lot_policy,
        "slippage_buy_bps": params.slippage_buy_bps,
        "slippage_sell_bps": params.slippage_sell_bps,
        "stamp_tax_buy_bps": params.stamp_tax_buy_bps,
        "stamp_tax_sell_bps": params.stamp_tax_sell_bps,
        "strategy_id": params.strategy_id,
        "tail_risk_profile_id": params.tail_risk_profile_id,
        "target_holdings": params.target_holdings,
    }
    if is_topdown_lot100(params):
        payload["min_position_weight"] = effective_min_position_weight(params)
        payload["position_floor_count"] = params.position_floor_count
        payload["walk_depth"] = params.walk_depth
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def hash_holdings(holdings: dict[str, float]) -> str:
    payload = {
        sec_code: round(float(shares), 6)
        for sec_code, shares in sorted(holdings.items())
        if abs(float(shares)) > 0.000001
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_resume_snapshot(
    client: bigquery.Client,
    params: LedgerParams,
    calendar: pd.DataFrame,
) -> ResumeSnapshot:
    tables = TableResolver(dataset_role=params.output_dataset_role, project=params.project)
    next_open = next_open_after(calendar, params.state_as_of_date)
    if next_open is None or str(next_open) != params.predict_start:
        raise RuntimeError(
            "resume_from_backtest requires predict_start to be the next open trading day after state_as_of_date"
        )

    qparams = [
        bigquery.ScalarQueryParameter("parent_backtest_id", "STRING", params.parent_backtest_id),
        bigquery.ScalarQueryParameter("state_as_of_date", "DATE", params.state_as_of_date),
    ]
    nav = query_dataframe(
        client,
        f"""
        SELECT trade_date, nav, net_value_cny
        FROM `{tables.fqn('backtest_nav_daily')}`
        WHERE backtest_id = @parent_backtest_id
          AND trade_date = @state_as_of_date
        """,
        qparams,
    )
    if nav.empty:
        raise RuntimeError("Parent NAV snapshot not found for resume")

    state = query_dataframe(
        client,
        f"""
        SELECT
          trade_date,
          cash_cny,
          net_value_cny,
          nav,
          pending_sell_sec_codes_json,
          active_signal_date,
          active_target_weights_json,
          holdings_hash,
          ledger_version,
          ledger_params_hash,
          resume_policy_id,
          rebalance_anchor_start
        FROM `{tables.fqn('backtest_ledger_state_daily')}`
        WHERE backtest_id = @parent_backtest_id
          AND trade_date = @state_as_of_date
        """,
        qparams,
    )
    if state.empty:
        raise RuntimeError("Parent ledger state snapshot not found for resume")

    positions = query_dataframe(
        client,
        f"""
        SELECT sec_code, shares, market_value_cny
        FROM `{tables.fqn('backtest_position_daily')}`
        WHERE backtest_id = @parent_backtest_id
          AND trade_date = @state_as_of_date
        """,
        qparams,
    )

    state_row = state.iloc[0]
    expected_hash = ledger_params_hash(params)
    if str(state_row["ledger_version"]) != params.ledger_version:
        raise RuntimeError("Parent ledger_version does not match resume child")
    if str(state_row["resume_policy_id"]) != params.resume_policy_id:
        raise RuntimeError("Parent resume_policy_id does not match resume child")
    if str(state_row["rebalance_anchor_start"]) != effective_rebalance_anchor_start(params):
        raise RuntimeError("Parent rebalance_anchor_start does not match resume child")
    if str(state_row["ledger_params_hash"]) != expected_hash:
        raise RuntimeError("Parent ledger_params_hash does not match resume child")

    holdings = {
        str(row.sec_code): float(row.shares)
        for row in positions.itertuples(index=False)
        if abs(float(row.shares)) > 0.000001
    }
    if hash_holdings(holdings) != str(state_row["holdings_hash"]):
        raise RuntimeError("Parent holdings_hash does not match position snapshot")

    market_value = float(positions["market_value_cny"].sum()) if not positions.empty else 0.0
    cash_cny = float(state_row["cash_cny"])
    net_value_cny = float(state_row["net_value_cny"])
    if abs(cash_cny + market_value - net_value_cny) > 1.0:
        raise RuntimeError("Parent cash plus positions does not reconcile to net value")

    pending_sell = set(json.loads(state_row["pending_sell_sec_codes_json"] or "[]"))
    target_weights = json.loads(state_row["active_target_weights_json"] or "{}")
    nav_value = float(nav.iloc[0]["net_value_cny"])
    if abs(nav_value - net_value_cny) > 1.0:
        raise RuntimeError("Parent ledger state net value does not match NAV snapshot")

    active_signal_date = state_row["active_signal_date"]
    if pd.isna(active_signal_date):
        active_signal_date = None

    return ResumeSnapshot(
        cash_cny=cash_cny,
        previous_nav_value=net_value_cny,
        holdings=holdings,
        pending_sell=pending_sell,
        target_weights=target_weights,
        active_signal_date=active_signal_date,
        ledger_params_hash=str(state_row["ledger_params_hash"]),
        rebalance_anchor_start=state_row["rebalance_anchor_start"],
    )


def next_open_after(calendar: pd.DataFrame, state_as_of_date: str | None) -> object | None:
    if not state_as_of_date:
        return None
    later = calendar[calendar["trade_date"].astype(str) > state_as_of_date]
    if later.empty:
        return None
    return later.iloc[0]["trade_date"]


def load_targets(client: bigquery.Client, params: LedgerParams) -> pd.DataFrame:
    tables = TableResolver(dataset_role=params.output_dataset_role, project=params.project)
    if is_topdown_lot100(params):
        sql = f"""
        SELECT
          cand.rebalance_date,
          cand.sec_code,
          CAST(NULL AS FLOAT64) AS target_weight,
          cand.rank_raw,
          cand.filter_reason
        FROM `{tables.fqn('stock_candidate_daily')}` AS cand
        WHERE cand.strategy_id=@strategy_id AND cand.run_id=@run_id
          AND cand.rebalance_date BETWEEN @start AND @end
          AND cand.rank_raw IS NOT NULL
          AND cand.rank_raw <= @walk_depth
        ORDER BY cand.rebalance_date, cand.rank_raw, cand.sec_code
        """
        return normalize_dates(query_dataframe(client, sql, [
            bigquery.ScalarQueryParameter("strategy_id", "STRING", params.strategy_id),
            bigquery.ScalarQueryParameter("run_id", "STRING", params.run_id),
            bigquery.ScalarQueryParameter("start", "DATE", params.predict_start),
            bigquery.ScalarQueryParameter("end", "DATE", params.predict_end),
            bigquery.ScalarQueryParameter("walk_depth", "INT64", params.walk_depth),
        ]), ["rebalance_date"])
    sql = f"""
    SELECT
      pt.rebalance_date,
      pt.sec_code,
      pt.target_weight,
      cand.rank_raw,
      cand.filter_reason
    FROM `{tables.fqn('portfolio_target_daily')}` AS pt
    LEFT JOIN `{tables.fqn('stock_candidate_daily')}` AS cand
      ON cand.strategy_id = pt.strategy_id
     AND cand.run_id = pt.run_id
     AND cand.rebalance_date = pt.rebalance_date
     AND cand.sec_code = pt.sec_code
     AND cand.rebalance_date BETWEEN @start AND @end
    WHERE pt.strategy_id=@strategy_id AND pt.run_id=@run_id
      AND pt.rebalance_date BETWEEN @start AND @end
    ORDER BY pt.rebalance_date, COALESCE(cand.rank_raw, 999999), pt.sec_code
    """
    return normalize_dates(query_dataframe(client, sql, [
        bigquery.ScalarQueryParameter("strategy_id", "STRING", params.strategy_id),
        bigquery.ScalarQueryParameter("run_id", "STRING", params.run_id),
        bigquery.ScalarQueryParameter("start", "DATE", params.predict_start),
        bigquery.ScalarQueryParameter("end", "DATE", params.predict_end),
    ]), ["rebalance_date"])


def build_target_specs_by_signal(targets: pd.DataFrame) -> dict[Any, dict[str, dict[str, Any]]]:
    by_signal: dict[Any, dict[str, dict[str, Any]]] = {}
    for signal_date, group in targets.groupby("rebalance_date"):
        specs: dict[str, dict[str, Any]] = {}
        for row in group.itertuples(index=False):
            specs[row.sec_code] = {
                "target_weight": float(row.target_weight or 0.0),
                "rank_raw": getattr(row, "rank_raw", None),
                "filter_reason": getattr(row, "filter_reason", None),
            }
        by_signal[signal_date] = specs
    return by_signal


def load_tail_risk_buy_guards(client: bigquery.Client, params: LedgerParams) -> dict[Any, set[str]]:
    if not has_individual_risk_guard(params.tail_risk_profile_id):
        return {}
    tables = TableResolver(dataset_role=params.output_dataset_role, project=params.project)
    sql = f"""
    SELECT rebalance_date, sec_code
    FROM `{tables.fqn('stock_candidate_daily')}`
    WHERE strategy_id=@strategy_id AND run_id=@run_id
      AND rebalance_date BETWEEN @start AND @end
      AND is_selected_candidate
      AND STARTS_WITH(COALESCE(filter_reason, ''), 'tail_risk:')
    ORDER BY rebalance_date, sec_code
    """
    frame = normalize_dates(query_dataframe(client, sql, [
        bigquery.ScalarQueryParameter("strategy_id", "STRING", params.strategy_id),
        bigquery.ScalarQueryParameter("run_id", "STRING", params.run_id),
        bigquery.ScalarQueryParameter("start", "DATE", params.predict_start),
        bigquery.ScalarQueryParameter("end", "DATE", params.predict_end),
    ]), ["rebalance_date"])
    guards: dict[Any, set[str]] = {}
    for row in frame.itertuples(index=False):
        guards.setdefault(row.rebalance_date, set()).add(row.sec_code)
    return guards


def load_market_risk_off_signal_dates(client: bigquery.Client, params: LedgerParams) -> set[Any]:
    if not has_market_risk_guard(params.tail_risk_profile_id):
        return set()
    sql = """
    SELECT trade_date
    FROM `data-aquarium.ashare_dws.dws_market_state_daily`
    WHERE trade_date BETWEEN @start AND @end
      AND market_state_version = @market_state_version
      AND is_risk_off
      AND risk_off_action = 'skip_new_buys'
    ORDER BY trade_date
    """
    frame = normalize_dates(query_dataframe(client, sql, [
        bigquery.ScalarQueryParameter("start", "DATE", params.predict_start),
        bigquery.ScalarQueryParameter("end", "DATE", params.predict_end),
        bigquery.ScalarQueryParameter("market_state_version", "STRING", params.market_state_version),
    ]), ["trade_date"])
    return set(frame["trade_date"].tolist())


def build_periods(targets: pd.DataFrame, cal: pd.DataFrame, params: LedgerParams) -> pd.DataFrame:
    seq_by_date = cal.set_index("trade_date")["trade_date_seq"].to_dict()
    date_by_seq = cal.set_index("trade_date_seq")["trade_date"].to_dict()
    rows = []
    for signal_date in sorted(targets["rebalance_date"].drop_duplicates()):
        seq = seq_by_date.get(signal_date)
        exec_date = date_by_seq.get(seq + 1) if seq is not None else None
        if exec_date and pd.to_datetime(params.predict_start).date() <= exec_date <= pd.to_datetime(params.predict_end).date():
            rows.append({"signal_date": signal_date, "exec_date": exec_date})
    return pd.DataFrame(rows)


def load_prices(client: bigquery.Client, params: LedgerParams, sec_codes: list[str], start: str, end: str) -> pd.DataFrame:
    if not sec_codes:
        return pd.DataFrame()
    sql = """
    SELECT sec_code, trade_date, open, close,
           COALESCE(can_buy_open, FALSE) AS can_buy_open,
           COALESCE(can_sell_open, FALSE) AS can_sell_open
    FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price`
    WHERE trade_date BETWEEN @start AND @end
      AND sec_code IN UNNEST(@sec_codes)
    ORDER BY sec_code, trade_date
    """
    return normalize_dates(query_dataframe(client, sql, [
        bigquery.ScalarQueryParameter("start", "DATE", start),
        bigquery.ScalarQueryParameter("end", "DATE", end),
        bigquery.ArrayQueryParameter("sec_codes", "STRING", sec_codes),
    ]), ["trade_date"])


def load_benchmark(client: bigquery.Client, params: LedgerParams, start: str, end: str) -> dict[Any, float]:
    sql = """
    SELECT trade_date, pct_chg / 100.0 AS benchmark_return
    FROM `data-aquarium.ashare_dwd.dwd_index_eod`
    WHERE sec_code=@benchmark AND trade_date BETWEEN @start AND @end
    """
    frame = normalize_dates(query_dataframe(client, sql, [
        bigquery.ScalarQueryParameter("benchmark", "STRING", params.benchmark),
        bigquery.ScalarQueryParameter("start", "DATE", start),
        bigquery.ScalarQueryParameter("end", "DATE", end),
    ]), ["trade_date"])
    return dict(zip(frame["trade_date"], frame["benchmark_return"]))


def normalize_dates(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col in frame.columns:
            frame[col] = pd.to_datetime(frame[col]).dt.date
    return frame


def first_finite(*values: Any, default: Any = None) -> Any:
    for value in values:
        if value is None:
            continue
        try:
            if np.isfinite(value):
                return float(value)
        except TypeError:
            continue
    return default


def safe_divide(numerator: Any, denominator: Any) -> float:
    try:
        if denominator is None or not np.isfinite(denominator) or abs(denominator) <= 1e-12:
            return 0.0
        return float(numerator) / float(denominator)
    except TypeError:
        return 0.0


def validate_ledger_params(params: LedgerParams) -> None:
    if params.ledger_version not in {LEDGER_VERSION_FLOAT, LEDGER_VERSION_LOT100, LEDGER_VERSION_TOPDOWN_LOT100}:
        raise ValueError(f"unsupported ledger_version: {params.ledger_version}")
    if params.initial_state_mode not in {"fresh", "resume_from_backtest"}:
        raise ValueError(f"Unsupported initial_state_mode={params.initial_state_mode}")
    expected_resume_policy = expected_resume_policy_id(params)
    if params.resume_policy_id != expected_resume_policy:
        raise ValueError(
            f"Unsupported resume_policy_id={params.resume_policy_id}; expected {expected_resume_policy}"
        )
    if params.rebalance_anchor_start and params.rebalance_anchor_start > params.predict_start:
        raise ValueError("rebalance_anchor_start must be <= predict_start")
    if params.initial_state_mode == "fresh":
        if params.parent_backtest_id or params.state_as_of_date:
            raise ValueError("fresh ledger run must not set parent_backtest_id or state_as_of_date")
    else:
        if not is_lot_aware(params):
            raise ValueError("resume_from_backtest requires a lot-aware ledger")
        if not params.parent_backtest_id:
            raise ValueError("resume_from_backtest requires parent_backtest_id")
        if not params.state_as_of_date:
            raise ValueError("resume_from_backtest requires state_as_of_date")
        if not params.rebalance_anchor_start:
            raise ValueError("resume_from_backtest requires explicit rebalance_anchor_start")
        if params.parent_backtest_id == params.backtest_id:
            raise ValueError("parent_backtest_id must differ from backtest_id")
        if params.state_as_of_date >= params.predict_start:
            raise ValueError("state_as_of_date must be before predict_start")
    if is_lot_aware(params):
        if params.lot_size <= 0:
            raise ValueError("lot_size must be positive")
        if params.min_buy_lot <= 0:
            raise ValueError("min_buy_lot must be positive")
        if params.buy_rounding != "floor_to_lot":
            raise ValueError(f"unsupported buy_rounding: {params.buy_rounding}")
        if params.sell_odd_lot_policy != "allow_full_exit_odd_lot":
            raise ValueError(f"unsupported sell_odd_lot_policy: {params.sell_odd_lot_policy}")
        if params.partial_sell_rounding != "floor_to_lot_keep_residual":
            raise ValueError(f"unsupported partial_sell_rounding: {params.partial_sell_rounding}")
        expected_cash_redistribution = expected_cash_redistribution_id(params)
        if params.cash_redistribution != expected_cash_redistribution:
            raise ValueError(
                "unsupported cash_redistribution: "
                f"{params.cash_redistribution}; expected {expected_cash_redistribution}"
            )
    if is_topdown_lot100(params):
        if params.position_floor_count <= 0:
            raise ValueError("position_floor_count must be positive")
        if effective_min_position_weight(params) <= 0:
            raise ValueError("min_position_weight must be positive")
        if params.walk_depth <= 0:
            raise ValueError("walk_depth must be positive")
        if not has_individual_risk_guard(params.tail_risk_profile_id):
            raise ValueError("topdown ledger requires individual tail-risk guard profile")


def is_lot_aware(params: LedgerParams) -> bool:
    return params.ledger_version in {LEDGER_VERSION_LOT100, LEDGER_VERSION_TOPDOWN_LOT100}


def is_topdown_lot100(params: LedgerParams) -> bool:
    return params.ledger_version == LEDGER_VERSION_TOPDOWN_LOT100


def expected_resume_policy_id(params: LedgerParams) -> str:
    return RESUME_POLICY_CLOUDRUN_TOPDOWN_LOT100 if is_topdown_lot100(params) else RESUME_POLICY_CLOUDRUN_LOT100


def expected_cash_redistribution_id(params: LedgerParams) -> str:
    return cash_redistribution_id_for_ledger_version(params.ledger_version)


def cash_redistribution_id_for_ledger_version(ledger_version: str) -> str:
    if ledger_version == LEDGER_VERSION_TOPDOWN_LOT100:
        return CASH_REDISTRIBUTION_TOPDOWN_WHOLE_ORDER_SKIP_V2
    return CASH_REDISTRIBUTION_NONE_V1


def min_buy_shares(params: LedgerParams) -> int:
    return int(params.lot_size * params.min_buy_lot)


def round_down_to_lot(shares: Any, lot_size: int) -> float:
    try:
        value = float(shares)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(value) or value <= 0:
        return 0.0
    return float(math.floor(value / lot_size) * lot_size)


def buy_cost_components(shares: float, fill_price: float | None, params: LedgerParams) -> tuple[float, float, float, float]:
    if fill_price is None or not np.isfinite(fill_price) or shares <= 0:
        return 0.0, 0.0, 0.0, 0.0
    turnover = shares * fill_price
    fee = max(turnover * params.commission_bps / 10000.0, params.min_commission_cny)
    tax = turnover * params.stamp_tax_buy_bps / 10000.0
    slippage = slippage_buy(turnover, params)
    return turnover, fee, tax, slippage


def build_buy_execution(item: PlanRow, shares: float, params: LedgerParams, fill_status: str) -> BuyExecution:
    turnover, fee, tax, slippage = buy_cost_components(shares, item.buy_fill_price, params)
    return BuyExecution(
        item=item,
        planned_shares=round_down_to_lot(safe_divide(item.want_value, item.exec_open), params.lot_size),
        filled_shares=shares,
        turnover=turnover,
        fee=fee,
        tax=tax,
        slippage=slippage,
        cash_required=turnover + fee + tax,
        fill_status=fill_status,
    )


def drop_buys_until_cash_nonnegative(
    executable: list[BuyExecution],
    cash: float,
    params: LedgerParams,
    exec_date: Any,
    rows: list[dict[str, Any]],
) -> list[BuyExecution]:
    remaining = list(executable)
    while sum(order.cash_required for order in remaining) - cash > 1e-6 and remaining:
        drop_idx = max(range(len(remaining)), key=lambda idx: buy_drop_priority(remaining[idx]))
        dropped = remaining.pop(drop_idx)
        rows.append(trade_row(
            params,
            exec_date,
            dropped.item,
            "BUY",
            dropped.planned_shares,
            0.0,
            None,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            "BUY_SKIPPED_CASH_INSUFFICIENT_AFTER_ROUNDING",
        ))
    return remaining


def buy_drop_priority(order: BuyExecution) -> tuple[float, str]:
    rank_raw = order.item.target_rank_raw
    rank_key = float(rank_raw) if rank_raw is not None and math.isfinite(float(rank_raw)) else 1_000_000.0
    return rank_key, order.item.sec_code


def has_individual_risk_guard(profile_id: str) -> bool:
    return profile_id in INDIVIDUAL_RISK_PROFILES


def has_market_risk_guard(profile_id: str) -> bool:
    return profile_id in MARKET_RISK_PROFILES


def slippage_sell(turnover: float, params: LedgerParams) -> float:
    denom = 10000.0 - params.slippage_sell_bps
    return turnover * params.slippage_sell_bps / denom if denom else 0.0


def slippage_buy(turnover: float, params: LedgerParams) -> float:
    denom = 10000.0 + params.slippage_buy_bps
    return turnover * params.slippage_buy_bps / denom if denom else 0.0
