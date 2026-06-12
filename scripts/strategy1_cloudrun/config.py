"""Compatibility wrapper for Strategy1 runner configuration helpers."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists() and str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from quant_ashare.strategy1.config import *  # noqa: E402,F401,F403
from quant_ashare.strategy1.config import (  # noqa: E402,F401
    Experiment,
    RunnerConfig,
    add_common_args,
    apply_cli_overrides,
    dump_resolved_manifest,
    effective_candidate_parallelism,
    experiment_from_b64,
    experiment_to_b64,
    filter_experiments,
    load_manifest,
    load_runner_config,
    manifest_hash,
    read_mapping,
    resolve_parallel_count,
)
