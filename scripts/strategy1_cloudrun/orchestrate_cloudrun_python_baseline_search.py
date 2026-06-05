#!/usr/bin/env python3
"""Entrypoint alias for Strategy 1 Cloud Run Python baseline search."""

from __future__ import annotations

from scripts.strategy1_cloudrun.orchestrate_sklearn_native_search import main


if __name__ == "__main__":
    raise SystemExit(main())
