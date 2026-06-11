#!/usr/bin/env python3
"""Compatibility entrypoint for PRD_20260611_09 transfer ladder analysis."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.strategy1.analyze_signal_ic_decomposition import main


if __name__ == "__main__":
    raise SystemExit(main())
