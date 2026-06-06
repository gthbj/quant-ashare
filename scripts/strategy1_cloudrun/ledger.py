"""Python implementation of Strategy 1 `ledger_exec_v1`.

The implementation follows `sql/ml/strategy1/08_run_backtest.sql` for the
fresh-start path. Resume support is intentionally fail-fast until the Cloud Run
runner passes the fresh-start equivalence gate against the BigQuery ledger.
"""

from __future__ import annotations

import dataclasses
import math
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd
from google.cloud import bigquery

from scripts.strategy1_cloudrun.bq_io import ADS, execute_query, load_dataframe, query_dataframe


@dataclasses.dataclass(frozen=True)
class LedgerParams:
    project: str
    run_id: str
    backtest_id: str
    strategy_id: str = "ml_pv_clf_v0"
    predict_start: str = "2024-01-02"
    predict_end: str = "2025-12-31"
    initial_capital: float = 100000.0
    benchmark: str = "000852.SH"
    commission_bps: float = 1.0
    min_commission_cny: float = 0.0
    stamp_tax_buy_bps: float = 0.0
    stamp_tax_sell_bps: float = 5.0
    slippage_buy_bps: float = 5.0
    slippage_sell_bps: float = 5.0
    force_replace: bool = False
    initial_state_mode: str = "fresh"
    parent_backtest_id: str | None = None
    state_as_of_date: str | None = None
    tail_risk_profile_id: str = "diagnostic_only"


def run_ledger(client: bigquery.Client, params: LedgerParams) -> dict[str, int]:
    if params.initial_state_mode != "fresh":
        raise NotImplementedError("Cloud Run Python ledger P0 supports fresh-start only; resume is fail-fast")
    if params.force_replace:
        clear_ledger_outputs(client, params)

    calendar_end = (pd.Timestamp(params.predict_end) + pd.Timedelta(days=90)).date().isoformat()
    price_start = (pd.Timestamp(params.predict_start) - pd.Timedelta(days=10)).date().isoformat()
    benchmark_assert(client, params)

    cal = load_calendar(client, params.predict_start, calendar_end)
    exec_days = cal[(cal["trade_date"] >= pd.to_datetime(params.predict_start).date()) & (cal["trade_date"] <= pd.to_datetime(params.predict_end).date())].copy()
    exec_days = exec_days.sort_values("trade_date").reset_index(drop=True)
    targets = load_targets(client, params)
    if targets.empty:
        raise RuntimeError(f"no portfolio targets for run_id={params.run_id}")
    periods = build_periods(targets, cal, params)
    presence = targets.merge(periods, left_on="rebalance_date", right_on="signal_date", how="inner")
    prices = load_prices(client, params, presence["sec_code"].dropna().unique().tolist(), price_start, calendar_end)
    px = PriceBook(prices)
    benchmark = load_benchmark(client, params, params.predict_start, calendar_end)

    cash = float(params.initial_capital)
    holdings: dict[str, float] = {}
    target_weights: dict[str, float] = {}
    pending_sell: set[str] = set()
    trade_rows: list[dict[str, Any]] = []
    position_rows: list[dict[str, Any]] = []
    nav_rows: list[dict[str, Any]] = []
    previous_nav_value: float | None = None

    periods_by_exec = {row.exec_date: row for row in periods.itertuples(index=False)}
    targets_by_signal = {
        signal_date: group.set_index("sec_code")["target_weight"].astype(float).to_dict()
        for signal_date, group in targets.groupby("rebalance_date")
    }
    tail_risk_buy_guards = load_tail_risk_buy_guards(client, params)

    for exec_date in exec_days["trade_date"]:
        period = periods_by_exec.get(exec_date)
        is_rebalance = period is not None
        if is_rebalance:
            target_weights = targets_by_signal.get(period.signal_date, {})

        nav_before = cash + sum(shares * px.valuation_price(sec, exec_date) for sec, shares in holdings.items())
        plan = build_daily_plan(
            exec_date,
            is_rebalance,
            holdings,
            target_weights,
            pending_sell,
            tail_risk_buy_guards.get(period.signal_date, set()) if is_rebalance else set(),
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
        day_turnover = sum(row["turnover_cny"] for row in daily_trade_rows if row["fill_status"] in ("FILLED", "FILLED_SCALED_CASH"))
        day_cost = sum(row["fee_cny"] for row in daily_trade_rows if row["fill_status"] in ("FILLED", "FILLED_SCALED_CASH"))
        nav_rows.append({
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
        })

    nav_by_date = {row["trade_date"]: row["net_value_cny"] for row in nav_rows}
    for row in position_rows:
        row["weight"] = safe_divide(row["market_value_cny"], nav_by_date[row["trade_date"]])

    load_dataframe(client, pd.DataFrame(trade_rows), f"{ADS}.ads_backtest_trade_daily")
    load_dataframe(client, pd.DataFrame(position_rows), f"{ADS}.ads_backtest_position_daily")
    load_dataframe(client, pd.DataFrame(nav_rows), f"{ADS}.ads_backtest_nav_daily")
    return {"trades": len(trade_rows), "positions": len(position_rows), "nav": len(nav_rows)}


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
    pending_noop: bool
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
    holdings: dict[str, float],
    target_weights: dict[str, float],
    pending_sell: set[str],
    tail_risk_blocked_new_buys: set[str],
    nav_before: float,
    px: PriceBook,
    params: LedgerParams,
) -> list[PlanRow]:
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
        w = float(target_weights.get(sec, 0.0))
        cur_value = cur_shares * val_price
        desired_value = w * nav_before
        can_buy_now = can_buy and exec_open is not None and np.isfinite(exec_open)
        can_sell_now = can_sell and exec_open is not None and np.isfinite(exec_open)
        tail_risk_new_buy_blocked = (
            params.tail_risk_profile_id == "individual_risk_guard_v0"
            and is_rebalance
            and sec in tail_risk_blocked_new_buys
            and cur_shares <= 0.000001
        )
        sell_shares = 0.0
        if cur_shares > 0 and (is_rebalance or sec in pending_sell) and cur_value - desired_value > 0.01 and can_sell_now:
            sell_shares = cur_shares if desired_value <= 0.01 else min(cur_shares, (cur_value - desired_value) / exec_open)
        want_value = 0.0
        if is_rebalance and can_buy_now and desired_value - cur_value > 0.01 and not tail_risk_new_buy_blocked:
            want_value = desired_value - cur_value
        sell_skip_shares = 0.0
        if cur_shares > 0 and (is_rebalance or sec in pending_sell) and cur_value - desired_value > 0.01 and not can_sell_now:
            denom = exec_open if exec_open is not None and np.isfinite(exec_open) else val_price
            sell_skip_shares = cur_shares if desired_value <= 0.01 else min(cur_shares, safe_divide(cur_value - desired_value, denom))
        buy_skip_value = 0.0
        if is_rebalance and desired_value - cur_value > 0.01 and (not can_buy_now or tail_risk_new_buy_blocked):
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
            pending_noop=pending_noop,
        ))
    return plan


def execute_plan(
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
            rows.append(trade_row(params, exec_date, item, "BUY", planned_shares, filled_shares, item.buy_fill_price, gross, fee, tax, slippage_buy(gross, params), cash_effect, "FILLED_SCALED_CASH" if scale < 0.999999 else "FILLED"))
        elif item.want_value > 0.000001 and scale <= 0.000001:
            rows.append(trade_row(params, exec_date, item, "BUY", safe_divide(item.want_value, item.exec_open), 0.0, None, 0.0, 0.0, 0.0, 0.0, 0.0, "SKIPPED_CASH_INSUFFICIENT"))
        if item.sell_skip_shares > 0.000001:
            status = "SELL_SKIPPED_UNTRADABLE" if is_rebalance else "PENDING_SELL_CARRY"
            rows.append(trade_row(params, exec_date, item, "SELL", item.sell_skip_shares, 0.0, None, 0.0, 0.0, 0.0, 0.0, 0.0, status))
        if item.buy_skip_value > 0.000001:
            status = "BUY_SKIPPED_TAIL_RISK" if item.tail_risk_new_buy_blocked else "BUY_SKIPPED_UNTRADABLE"
            rows.append(trade_row(params, exec_date, item, "BUY", safe_divide(item.buy_skip_value, item.val_price), 0.0, None, 0.0, 0.0, 0.0, 0.0, 0.0, status))
        if item.pending_noop:
            rows.append(trade_row(params, exec_date, item, "SELL", 0.0, 0.0, None, 0.0, 0.0, 0.0, 0.0, 0.0, "CANCELLED_BY_NETTING"))
    return cash, rows


def update_holdings(plan: list[PlanRow]) -> dict[str, float]:
    holdings = {}
    for item in plan:
        shares = item.cur_shares - item.sell_shares
        if item.want_value > 0.000001 and item.scale > 0.000001:
            shares += safe_divide(item.want_value * item.scale, item.exec_open)
        if shares > 0.000001:
            holdings[item.sec_code] = shares
    return holdings


def update_pending_sell(plan: list[PlanRow], is_rebalance: bool) -> set[str]:
    pending = set()
    for item in plan:
        remaining_shares = item.cur_shares - item.sell_shares
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
    calendar_end = (pd.Timestamp(params.predict_end) + pd.Timedelta(days=90)).date().isoformat()
    qparams = [
        bigquery.ScalarQueryParameter("backtest_id", "STRING", params.backtest_id),
        bigquery.ScalarQueryParameter("start_date", "DATE", params.predict_start),
        bigquery.ScalarQueryParameter("end_date", "DATE", calendar_end),
    ]
    for table in ("ads_backtest_trade_daily", "ads_backtest_position_daily", "ads_backtest_nav_daily"):
        execute_query(client, f"DELETE FROM `{ADS}.{table}` WHERE backtest_id=@backtest_id AND trade_date BETWEEN @start_date AND @end_date", qparams)
    execute_query(client, f"DELETE FROM `{ADS}.ads_backtest_performance_summary` WHERE backtest_id=@backtest_id", [bigquery.ScalarQueryParameter("backtest_id", "STRING", params.backtest_id)])


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


def load_targets(client: bigquery.Client, params: LedgerParams) -> pd.DataFrame:
    sql = f"""
    SELECT rebalance_date, sec_code, target_weight
    FROM `{ADS}.ads_portfolio_target_daily`
    WHERE strategy_id=@strategy_id AND run_id=@run_id
      AND rebalance_date BETWEEN @start AND @end
    ORDER BY rebalance_date, sec_code
    """
    return normalize_dates(query_dataframe(client, sql, [
        bigquery.ScalarQueryParameter("strategy_id", "STRING", params.strategy_id),
        bigquery.ScalarQueryParameter("run_id", "STRING", params.run_id),
        bigquery.ScalarQueryParameter("start", "DATE", params.predict_start),
        bigquery.ScalarQueryParameter("end", "DATE", params.predict_end),
    ]), ["rebalance_date"])


def load_tail_risk_buy_guards(client: bigquery.Client, params: LedgerParams) -> dict[Any, set[str]]:
    if params.tail_risk_profile_id != "individual_risk_guard_v0":
        return {}
    sql = f"""
    SELECT rebalance_date, sec_code
    FROM `{ADS}.ads_stock_candidate_daily`
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


def slippage_sell(turnover: float, params: LedgerParams) -> float:
    denom = 10000.0 - params.slippage_sell_bps
    return turnover * params.slippage_sell_bps / denom if denom else 0.0


def slippage_buy(turnover: float, params: LedgerParams) -> float:
    denom = 10000.0 + params.slippage_buy_bps
    return turnover * params.slippage_buy_bps / denom if denom else 0.0
