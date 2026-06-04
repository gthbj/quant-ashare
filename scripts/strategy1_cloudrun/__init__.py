"""Strategy 1 Cloud Run runner package.

P0 keeps BigQuery DWS/ADS as the structured contract and moves model
training/prediction plus orchestration into Python entrypoints suitable for
Cloud Run Jobs.
"""

__all__ = ["__version__"]

__version__ = "strategy1_cloudrun_runner_v0_20260604"
