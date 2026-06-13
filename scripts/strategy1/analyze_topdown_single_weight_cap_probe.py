#!/usr/bin/env python3
"""Read-only paper probe: does a single-name weight cap rescue top-down T0 vs v1?

Reuses the validated Phase 0 paper harness (`analyze_topdown_lot_phase0`) and only
toggles the opt-in `single_weight_cap` config. For each cap level it runs the T0 arm
(no P1) at walk_depth=50 with the primary matched-cost profile, then reports
CAGR / Calmar / MaxDD / Sharpe / avg cash / avg holdings / single-name weight stats.

Validation anchor: `--cap none` must reproduce the committed paper T0 numbers
(CAGR 11.81% / Calmar 0.2013 / MaxDD -58.67% / max weight 47.19% / holdings 14.54);
if it does, the capped rows from the same harness are trustworthy.

Strictly read-only: BigQuery SELECT only, no writes, no GCS upload, no Cloud Run.
Background: PR #217 (retained-holding ledger bug fix) confirmed live topdown `_v02`
≈ paper T0 (11.96% vs 11.81%), so this local probe is a faithful, free proxy for the
live ledger and is used to decide whether a live capped re-run is worth the cycle.

> 文档维护：Claude Opus 4.8（2026-06-13）
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
from pathlib import Path

from scripts.strategy1.analyze_topdown_lot_phase0 import (
    MAIN_PANEL_ID,
    PriceBook,
    add_tail_risk_reasons,
    config_from_args,
    fetch_benchmark,
    fetch_calendar,
    fetch_candidates,
    fetch_prices,
    make_client,
    parse_args as parse_phase0_args,
    simulate_arm,
    summarize_arm,
    validate_candidates,
)

DEFAULT_CAPS = "none,0.20,0.15,0.10"
DEFAULT_OUT_CSV = "docs/analysis_topdown_single_weight_cap_probe_20260613.csv"
ARM = "T0"


def parse_cap(token: str) -> float | None:
    token = token.strip().lower()
    if token in {"none", "off", ""}:
        return None
    value = float(token)
    if not 0.0 < value <= 1.0:
        raise ValueError(f"cap must be in (0, 1], got {value}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--caps", default=DEFAULT_CAPS, help="Comma list; 'none' = disabled.")
    parser.add_argument("--walk-depth", type=int, default=50)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    caps = [parse_cap(tok) for tok in args.caps.split(",") if tok.strip()]
    cfg = config_from_args(parse_phase0_args([]))
    wd = args.walk_depth if args.walk_depth in cfg.walk_depths else max(cfg.walk_depths)

    client = make_client(cfg.project, cfg.location)
    print(f"prediction_run_id={cfg.prediction_run_id}\nbacktest_id(v1)={cfg.backtest_id}", flush=True)
    max_depth = max(max(cfg.walk_depths), wd)
    candidates = add_tail_risk_reasons(fetch_candidates(client, cfg, max_depth))
    validate_candidates(candidates, cfg, max_depth)
    calendar = fetch_calendar(client, cfg)
    benchmark = fetch_benchmark(client, cfg)
    prices = fetch_prices(client, cfg, sorted(candidates["sec_code"].dropna().astype(str).unique()))
    price_book = PriceBook(prices)
    prof = next((p for p in cfg.cost_profiles if getattr(p, "is_primary", False)), cfg.cost_profiles[-1])
    print(f"arm={ARM} walk_depth={wd} cost_profile={prof.cost_profile_id}\n", flush=True)

    fields = [
        "single_weight_cap", "compound_annual_return", "calmar_ratio", "max_drawdown",
        "absolute_sharpe_or_contract_sharpe", "avg_cash_weight", "avg_realized_holdings_count",
        "max_realized_weight", "p95_max_realized_weight", "annual_turnover",
    ]
    header = f"{'cap':>6} {'CAGR':>8} {'Calmar':>8} {'MaxDD':>9} {'Sharpe':>7} {'avgCash':>8} {'avgHold':>8} {'maxW':>7} {'p95W':>7} {'turn':>7}"
    print(header)
    rows: list[dict] = []
    for cap in caps:
        cfg_cap = dataclasses.replace(cfg, single_weight_cap=cap)
        daily, audit = simulate_arm(
            cfg=cfg_cap, arm=ARM, walk_depth=wd, cost_profile=prof,
            saturation_threshold=cfg_cap.saturation_threshold, analysis_panel=MAIN_PANEL_ID,
            candidates=candidates, calendar=calendar, benchmark=benchmark, price_book=price_book,
        )
        m = summarize_arm(daily, audit, cfg_cap, ARM, wd, prof, cfg_cap.saturation_threshold, MAIN_PANEL_ID)
        row = {"single_weight_cap": "none" if cap is None else cap}
        row.update({k: m[k] for k in fields[1:]})
        rows.append(row)
        print(
            f"{str(cap):>6} {m['compound_annual_return']:>8.4f} {m['calmar_ratio']:>8.4f} "
            f"{m['max_drawdown']:>9.4f} {m['absolute_sharpe_or_contract_sharpe']:>7.4f} "
            f"{m['avg_cash_weight']:>8.4f} {m['avg_realized_holdings_count']:>8.2f} "
            f"{m['max_realized_weight']:>7.4f} {m['p95_max_realized_weight']:>7.4f} "
            f"{m['annual_turnover']:>7.2f}",
            flush=True,
        )

    out_path = Path(args.out_csv)
    with out_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nwrote {out_path}")
    print("v1 baseline reference: CAGR 0.1535 / Calmar 0.4101 / MaxDD -0.3743 / Sharpe ~0.668 / avgCash ~0.30 / avgHold ~16")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
