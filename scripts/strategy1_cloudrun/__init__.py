"""Strategy 1 Cloud Run runner package.

P0 keeps BigQuery DWS/ADS as the structured contract and moves model
training/prediction plus orchestration into Python entrypoints suitable for
Cloud Run Jobs.
"""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists() and str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from quant_ashare.strategy1.runner_version import __version__

__all__ = ["__version__"]
