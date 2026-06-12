"""Compatibility wrapper for Strategy1 feature-set contracts."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists() and str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from quant_ashare.strategy1.feature_sets import *  # noqa: E402,F401,F403
from quant_ashare.strategy1.feature_sets import (  # noqa: E402,F401
    BASE_FEATURE_SET_ID_BY_FEATURE_SET,
    BOOLEAN_FEATURE_COLUMNS,
    FEATURE_COLUMNS_BY_SET,
    FEATURE_GROUPS,
    FIN_QUALITY_FEATURE_COLUMNS,
    MARKET_STATE_FEATURE_COLUMNS,
    PV_FEATURE_COLUMNS,
    PV_FEATURE_SET_ID,
    PV_FIN_QUALITY_COLUMNS,
    PV_FIN_QUALITY_FEATURE_SET_ID,
    PV_FIN_RISK_COLUMNS,
    PV_FIN_RISK_FEATURE_SET_ID,
    RISK_FEATURE_COLUMNS,
    RISK_FLAG_FEATURE_COLUMNS,
    RISK_INTERACTION_FEATURE_COLUMNS,
    RISK_REGROUPED_COLUMNS,
    RISK_STOCK_ADDED_FEATURE_COLUMNS,
    SOURCE_TABLE_BY_GROUP,
    base_feature_set_id,
    boolean_feature_names,
    expected_feature_columns,
    feature_delta_vs_base,
    feature_metadata,
    market_state_feature_names,
    pit_rule_for_group,
    risk_feature_names,
    risk_required_feature_names,
)
