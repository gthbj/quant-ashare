"""Stable package entrypoint for Strategy1 backtest/report."""

from __future__ import annotations

from quant_ashare.strategy1.reporting import *  # noqa: F401,F403
from quant_ashare.strategy1.reporting import main


if __name__ == "__main__":
    raise SystemExit(main())
