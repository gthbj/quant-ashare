"""Compatibility wrapper for Strategy1 Cloud Run state helpers."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists() and str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from quant_ashare.strategy1.state import *  # noqa: E402,F401,F403
from quant_ashare.strategy1.state import (  # noqa: E402,F401
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DEFAULT_LOCK_BUCKET,
    DEFAULT_LOCK_PREFIX,
    DEFAULT_LOCK_TTL_MINUTES,
    STATUS_TABLE,
    GcsLeaseLock,
    LockConfig,
    OrchestratorStatusTable,
    StepStateSpec,
    build_lock_key,
    cancel_cloud_run_execution,
    cloud_run_execution_state,
    describe_cloud_run_execution,
    experiment_params_json,
    extract_cloud_run_execution_id,
    scheduler_instance_id,
    status_table_ref,
)
