#!/usr/bin/env python3
"""Compatibility wrapper for Strategy1 reporting/backtest entrypoint."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists() and str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from quant_ashare.strategy1 import backtest_report as _impl  # noqa: E402
from quant_ashare.strategy1.backtest_report import *  # noqa: E402,F401,F403
from quant_ashare.strategy1.backtest_report import main  # noqa: E402

if __name__ != "__main__":
    sys.modules[__name__] = _impl


if __name__ == "__main__":
    raise SystemExit(main())
