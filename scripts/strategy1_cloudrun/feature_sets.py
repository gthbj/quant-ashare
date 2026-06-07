"""Feature-set contracts for Strategy 1 Cloud Run matrix builders."""

from __future__ import annotations

from typing import Any


PV_FEATURE_SET_ID = "strategy1_pv_v0_20260601"
PV_FIN_QUALITY_FEATURE_SET_ID = "strategy1_pv_fin_quality_v0_20260603"
PV_FIN_RISK_FEATURE_SET_ID = "strategy1_pv_fin_risk_v0_20260606"

BASE_FEATURE_SET_ID_BY_FEATURE_SET = {
    PV_FIN_RISK_FEATURE_SET_ID: PV_FIN_QUALITY_FEATURE_SET_ID,
}

PV_FEATURE_COLUMNS = [
    "list_age_td",
    "ret_1d",
    "ret_3d",
    "ret_5d",
    "ret_10d",
    "ret_20d",
    "ret_60d",
    "mom_20_5",
    "mom_60_20",
    "vol_5d",
    "vol_20d",
    "vol_60d",
    "drawdown_20d",
    "hl_range_20d",
    "amount_ma20_cny",
    "amount_zscore_20d",
    "turnover_rate",
    "turnover_rate_free_float",
    "turnover_rate_ma20",
    "volume_ratio",
    "pe_ttm",
    "pb",
    "ps_ttm",
    "dividend_yield_ttm",
    "ep_ttm",
    "bp",
    "sp_ttm",
    "log_total_mv",
    "log_circ_mv",
]

FIN_QUALITY_FEATURE_COLUMNS = [
    "has_fin_indicator",
    "has_fin_income",
    "has_fin_balancesheet",
    "has_fin_cashflow",
    "report_age_days",
    "fin_report_lag_days",
    "roe",
    "roe_deducted",
    "roa",
    "roic",
    "grossprofit_margin",
    "netprofit_margin",
    "debt_to_assets",
    "current_ratio",
    "quick_ratio",
    "assets_to_equity",
    "ocf_to_or",
    "ocf_to_profit",
    "cash_ratio",
    "netprofit_yoy",
    "operating_revenue_yoy",
    "total_revenue_yoy",
    "basic_eps_yoy",
    "q_roe",
    "q_netprofit_margin",
    "q_grossprofit_margin",
]

RISK_STOCK_ADDED_FEATURE_COLUMNS = [
    "limit_down_days_20d",
    "one_word_limit_days_20d",
    "total_mv_cny",
    "circ_mv_cny",
]

RISK_FLAG_FEATURE_COLUMNS = [
    "risk_ret20_lt_30pct",
    "risk_drawdown20_lt_30pct",
    "risk_limit_down_20d_ge2",
    "risk_one_word_limit_20d_ge1",
    "risk_microcap_total_mv",
    "risk_microcap_circ_mv",
]

MARKET_STATE_FEATURE_COLUMNS = [
    "csi300_ret_5d",
    "csi300_ret_20d",
    "csi300_drawdown_20d",
    "csi1000_ret_5d",
    "csi1000_ret_20d",
    "csi1000_drawdown_20d",
    "csi1000_close_to_ma20",
    "csi1000_close_to_ma60",
    "csi1000_ma20_to_ma60",
    "csi300_vol_20d",
    "csi1000_vol_20d",
    "avg_vol_20d",
    "adv_ratio_1d",
    "above_ma20_ratio",
    "new_low_20d_ratio",
    "ret_20d_p25",
    "ret_20d_median",
    "drawdown_20d_median",
    "limit_down_count",
    "one_word_limit_down_count",
    "limit_down_mv_ratio",
    "is_smallcap_trend_down",
    "is_breadth_weak",
    "is_limit_down_diffusion",
    "risk_off_trigger_count",
    "is_risk_off",
]

RISK_INTERACTION_FEATURE_COLUMNS = [
    "stock_drawdown_x_market_riskoff",
    "stock_vol_x_market_vol",
    "microcap_x_breadth_weak",
    "limitdown_history_x_limitdown_diffusion",
]

RISK_FEATURE_COLUMNS = (
    RISK_STOCK_ADDED_FEATURE_COLUMNS
    + RISK_FLAG_FEATURE_COLUMNS
    + MARKET_STATE_FEATURE_COLUMNS
    + RISK_INTERACTION_FEATURE_COLUMNS
)

PV_FIN_QUALITY_COLUMNS = PV_FEATURE_COLUMNS + FIN_QUALITY_FEATURE_COLUMNS
PV_FIN_RISK_COLUMNS = PV_FEATURE_COLUMNS + FIN_QUALITY_FEATURE_COLUMNS + RISK_FEATURE_COLUMNS

FEATURE_COLUMNS_BY_SET = {
    PV_FEATURE_SET_ID: PV_FEATURE_COLUMNS,
    PV_FIN_QUALITY_FEATURE_SET_ID: PV_FIN_QUALITY_COLUMNS,
    PV_FIN_RISK_FEATURE_SET_ID: PV_FIN_RISK_COLUMNS,
}

RISK_REGROUPED_COLUMNS = {
    "ret_5d",
    "ret_20d",
    "ret_60d",
    "drawdown_20d",
    "vol_20d",
    "vol_60d",
    "hl_range_20d",
    "amount_ma20_cny",
    "turnover_rate_ma20",
    "volume_ratio",
    "log_total_mv",
    "log_circ_mv",
}

FEATURE_GROUPS: dict[str, str] = {
    "list_age_td": "universe_lifecycle",
    "ret_1d": "price_return",
    "ret_3d": "price_return",
    "ret_5d": "risk_recent_return",
    "ret_10d": "price_return",
    "ret_20d": "risk_recent_return",
    "ret_60d": "risk_recent_return",
    "mom_20_5": "price_momentum",
    "mom_60_20": "price_momentum",
    "vol_5d": "price_volatility",
    "vol_20d": "risk_volatility",
    "vol_60d": "risk_volatility",
    "drawdown_20d": "risk_drawdown",
    "hl_range_20d": "risk_volatility",
    "amount_ma20_cny": "risk_liquidity",
    "amount_zscore_20d": "price_liquidity",
    "turnover_rate": "valuation_liquidity",
    "turnover_rate_free_float": "valuation_liquidity",
    "turnover_rate_ma20": "risk_liquidity",
    "volume_ratio": "risk_liquidity",
    "pe_ttm": "valuation",
    "pb": "valuation",
    "ps_ttm": "valuation",
    "dividend_yield_ttm": "valuation",
    "ep_ttm": "valuation",
    "bp": "valuation",
    "sp_ttm": "valuation",
    "log_total_mv": "risk_size",
    "log_circ_mv": "risk_size",
    "limit_down_days_20d": "risk_limit_down",
    "one_word_limit_days_20d": "risk_limit_down",
    "total_mv_cny": "risk_size",
    "circ_mv_cny": "risk_size",
}

for _name in FIN_QUALITY_FEATURE_COLUMNS:
    FEATURE_GROUPS[_name] = "financial_quality"
for _name in RISK_FLAG_FEATURE_COLUMNS:
    FEATURE_GROUPS[_name] = "risk_flags"
for _name in MARKET_STATE_FEATURE_COLUMNS:
    if _name.startswith(("csi300_", "csi1000_")) and "vol" not in _name:
        FEATURE_GROUPS[_name] = "market_index_trend"
    elif _name.endswith("_vol_20d") or _name == "avg_vol_20d":
        FEATURE_GROUPS[_name] = "market_volatility"
    elif _name in {"limit_down_count", "one_word_limit_down_count", "limit_down_mv_ratio"}:
        FEATURE_GROUPS[_name] = "market_limit_down"
    elif _name.startswith("is_") or _name == "risk_off_trigger_count":
        FEATURE_GROUPS[_name] = "market_regime_flags"
    else:
        FEATURE_GROUPS[_name] = "market_breadth"
for _name in RISK_INTERACTION_FEATURE_COLUMNS:
    FEATURE_GROUPS[_name] = "risk_interactions"

SOURCE_TABLE_BY_GROUP = {
    "universe_lifecycle": "ashare_dws.dws_stock_sample_daily",
    "price_return": "ashare_dws.dws_stock_sample_daily",
    "price_momentum": "ashare_dws.dws_stock_sample_daily",
    "price_volatility": "ashare_dws.dws_stock_sample_daily",
    "price_liquidity": "ashare_dws.dws_stock_sample_daily",
    "valuation": "ashare_dws.dws_stock_sample_daily",
    "valuation_liquidity": "ashare_dws.dws_stock_sample_daily",
    "financial_quality": "ashare_dws.dws_stock_feature_fin_daily",
    "risk_recent_return": "ashare_dws.dws_stock_sample_daily",
    "risk_drawdown": "ashare_dws.dws_stock_sample_daily",
    "risk_volatility": "ashare_dws.dws_stock_sample_daily",
    "risk_limit_down": "ashare_dws.dws_stock_sample_daily",
    "risk_liquidity": "ashare_dws.dws_stock_sample_daily",
    "risk_size": "ashare_dws.dws_stock_sample_daily",
    "risk_flags": "ads_ml_training_panel_daily derived",
    "market_index_trend": "ashare_dws.dws_market_state_daily",
    "market_volatility": "ashare_dws.dws_market_state_daily",
    "market_breadth": "ashare_dws.dws_market_state_daily",
    "market_limit_down": "ashare_dws.dws_market_state_daily",
    "market_regime_flags": "ashare_dws.dws_market_state_daily",
    "risk_interactions": "ads_ml_training_panel_daily derived",
}


def expected_feature_columns(feature_set_id: str) -> list[str] | None:
    columns = FEATURE_COLUMNS_BY_SET.get(feature_set_id)
    return list(columns) if columns is not None else None


def base_feature_set_id(feature_set_id: str) -> str | None:
    return BASE_FEATURE_SET_ID_BY_FEATURE_SET.get(feature_set_id)


def feature_metadata(feature_set_id: str, feature_columns: list[str]) -> list[dict[str, Any]]:
    metadata = []
    for name in feature_columns:
        group = FEATURE_GROUPS.get(name, "unknown")
        role = "base"
        if feature_set_id == PV_FIN_RISK_FEATURE_SET_ID:
            if name in RISK_FEATURE_COLUMNS:
                role = "added"
            elif name in RISK_REGROUPED_COLUMNS:
                role = "regrouped"
            elif name in FEATURE_COLUMNS_BY_SET[PV_FIN_QUALITY_FEATURE_SET_ID]:
                role = "reused"
        metadata.append({
            "feature_name": name,
            "feature_group": group,
            "source_table": SOURCE_TABLE_BY_GROUP.get(group, "unknown"),
            "pit_rule": pit_rule_for_group(group),
            "feature_role": role,
        })
    return metadata


def feature_delta_vs_base(feature_set_id: str, feature_columns: list[str]) -> dict[str, Any]:
    base_id = base_feature_set_id(feature_set_id)
    if not base_id:
        return {
            "feature_set_id": feature_set_id,
            "base_feature_set_id": None,
            "added_columns": [],
            "reused_columns": list(feature_columns),
            "regrouped_columns": [],
            "deleted_columns": [],
        }
    base_columns = set(FEATURE_COLUMNS_BY_SET[base_id])
    current = set(feature_columns)
    regrouped = sorted(current & base_columns & RISK_REGROUPED_COLUMNS)
    return {
        "feature_set_id": feature_set_id,
        "base_feature_set_id": base_id,
        "added_columns": sorted(current - base_columns),
        "reused_columns": sorted((current & base_columns) - set(regrouped)),
        "regrouped_columns": regrouped,
        "deleted_columns": sorted(base_columns - current),
    }


def risk_feature_names() -> list[str]:
    return list(RISK_FEATURE_COLUMNS)


def market_state_feature_names() -> list[str]:
    return list(MARKET_STATE_FEATURE_COLUMNS)


def risk_required_feature_names() -> list[str]:
    return list(RISK_STOCK_ADDED_FEATURE_COLUMNS + RISK_FLAG_FEATURE_COLUMNS + MARKET_STATE_FEATURE_COLUMNS)


def pit_rule_for_group(group: str) -> str:
    if group.startswith("market_"):
        return "same trade_date t market close state; usable for t signal and t+1 open execution"
    if group == "financial_quality":
        return "PIT as-of financial DWS visible on trade_date t"
    if group in {"risk_flags", "risk_interactions"}:
        return "derived from same trade_date t features and market state only"
    return "same trade_date t stock feature, computed from t and earlier observations"
