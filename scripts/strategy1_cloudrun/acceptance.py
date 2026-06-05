"""Shared Strategy 1 model acceptance contract logic."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from scripts.strategy1_cloudrun.config import read_mapping


DEFAULT_CONTRACT_PATH = "configs/strategy1/model_acceptance_contract_v1.yml"


def load_acceptance_contract(path: str | Path | None = None) -> dict[str, Any]:
    contract = read_mapping(path or DEFAULT_CONTRACT_PATH)
    if not contract.get("contract_version"):
        raise ValueError("acceptance contract must define contract_version")
    return contract


def contract_version(contract: dict[str, Any]) -> str:
    return str(contract["contract_version"])


def decide_acceptance(row: dict[str, Any], contract: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """Return status, machine-readable reason and derived fields.

    Priority is intentionally fail-fast and mirrors PRD_20260605_04 §9:
    failed artifacts/QA, hard reject, needs-more-evidence, accepted, unmatched.
    """

    thresholds = contract.get("thresholds") or {}
    required = contract.get("required") or {}
    test_reuse = contract.get("test_reuse") or {}
    derived: dict[str, Any] = {
        "acceptance_contract_version": contract_version(contract),
        "holdout_watch_flag": False,
    }

    failed_reasons = _failed_reasons(row)
    if failed_reasons:
        return "failed", ";".join(failed_reasons), derived

    hard_reject = _hard_reject_reasons(row, contract)
    if hard_reject:
        return "rejected", ";".join(hard_reject), derived

    evidence = _needs_more_evidence_reasons(row, contract)
    if evidence:
        return "needs_more_evidence", ";".join(evidence), derived

    checks = [
        ("cv_confirmation_status", row.get("cv_confirmation_status"), required.get("cv_confirmation_status", "passed"), "eq"),
        ("valid_rank_ic_mean", _first(row, "valid_rank_ic_mean", "oriented_valid_rank_ic_mean"), thresholds.get("min_valid_rank_ic", 0.0), "gt"),
        ("valid_top_minus_bottom_fwd_ret_mean", row.get("valid_top_minus_bottom_fwd_ret_mean"), thresholds.get("min_valid_top_minus_bottom_fwd_ret", 0.0), "gt"),
        ("valid_signal_status", row.get("valid_signal_status"), required.get("valid_signal_status", "stable"), "eq"),
        ("test_rank_ic_mean", row.get("test_rank_ic_mean"), thresholds.get("min_test_rank_ic", 0.0), "gt"),
        ("test_top_minus_bottom_fwd_ret_mean", row.get("test_top_minus_bottom_fwd_ret_mean"), thresholds.get("min_test_top_minus_bottom_fwd_ret", 0.0), "gt"),
        ("test_year_excess_return_vs_000852", _first(row, "test_year_excess_return_vs_000852", "test_year_excess_return"), thresholds.get("min_test_year_excess_return_vs_000852", 0.0), "gt"),
        ("overall_excess_return_vs_000852", _first(row, "overall_excess_return_vs_000852", "excess_return"), thresholds.get("min_overall_excess_return_vs_000852", 0.0), "gt"),
        ("total_return", row.get("total_return"), thresholds.get("min_total_return", 0.0), "gt"),
        ("sharpe", row.get("sharpe"), thresholds.get("min_sharpe", 0.70), "ge"),
        ("max_drawdown", row.get("max_drawdown"), thresholds.get("min_max_drawdown", -0.25), "ge"),
        ("final_holdout_excess_return_vs_000852", row.get("final_holdout_excess_return_vs_000852"), thresholds.get("min_final_holdout_excess_return_vs_000852", -0.05), "gt"),
        ("final_holdout_total_return", row.get("final_holdout_total_return"), thresholds.get("min_final_holdout_total_return", -0.08), "gt"),
    ]
    unmatched = []
    for name, actual, threshold, op in checks:
        if op == "eq":
            if actual != threshold:
                unmatched.append(f"{name}!={threshold}")
            continue
        actual_value = safe_float(actual)
        threshold_value = safe_float(threshold)
        if not math.isfinite(actual_value):
            unmatched.append(f"{name}=missing")
        elif op == "gt" and not actual_value > threshold_value:
            unmatched.append(f"{name}<={threshold_value}")
        elif op == "ge" and not actual_value >= threshold_value:
            unmatched.append(f"{name}<{threshold_value}")
    if unmatched:
        return "rejected", ";".join(unmatched), derived

    final_excess = safe_float(row.get("final_holdout_excess_return_vs_000852"))
    final_total = safe_float(row.get("final_holdout_total_return"))
    if (math.isfinite(final_excess) and final_excess < 0) or (math.isfinite(final_total) and final_total < 0):
        derived["holdout_watch_flag"] = True

    wave_no = safe_int(row.get("test_reuse_wave_no"))
    required_after = safe_int(test_reuse.get("final_holdout_required_after_wave", 3))
    passed_status = str(test_reuse.get("final_holdout_passed_status", "passed"))
    if wave_no > required_after and row.get("final_holdout_status") != passed_status:
        return "needs_more_evidence", "test_reuse_wave_no_gt_final_holdout_threshold_without_passed_holdout", derived
    return "accepted", "all_acceptance_contract_gates_passed", derived


def _failed_reasons(row: dict[str, Any]) -> list[str]:
    reasons = []
    if row.get("execution_status") == "failed":
        reasons.append("execution_status=failed")
    if row.get("qa_status") == "failed":
        reasons.append("qa_status=failed")
    if row.get("report_uri") is None:
        reasons.append("report_uri=missing")
    if row.get("model_diagnosis_uri") is None:
        reasons.append("model_diagnosis_uri=missing")
    return reasons


def _hard_reject_reasons(row: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    thresholds = contract.get("thresholds") or {}
    reasons = []
    numeric_checks = [
        ("valid_rank_ic_mean", _first(row, "valid_rank_ic_mean", "oriented_valid_rank_ic_mean"), thresholds.get("min_valid_rank_ic", 0.0), "le"),
        ("valid_top_minus_bottom_fwd_ret_mean", row.get("valid_top_minus_bottom_fwd_ret_mean"), thresholds.get("min_valid_top_minus_bottom_fwd_ret", 0.0), "le"),
        ("test_rank_ic_mean", row.get("test_rank_ic_mean"), thresholds.get("min_test_rank_ic", 0.0), "le"),
        ("test_top_minus_bottom_fwd_ret_mean", row.get("test_top_minus_bottom_fwd_ret_mean"), thresholds.get("min_test_top_minus_bottom_fwd_ret", 0.0), "le"),
        ("test_year_excess_return_vs_000852", _first(row, "test_year_excess_return_vs_000852", "test_year_excess_return"), thresholds.get("min_test_year_excess_return_vs_000852", 0.0), "le"),
        ("overall_excess_return_vs_000852", _first(row, "overall_excess_return_vs_000852", "excess_return"), thresholds.get("min_overall_excess_return_vs_000852", 0.0), "le"),
        ("total_return", row.get("total_return"), thresholds.get("min_total_return", 0.0), "le"),
        ("sharpe", row.get("sharpe"), thresholds.get("min_sharpe", 0.70), "lt"),
        ("max_drawdown", row.get("max_drawdown"), thresholds.get("min_max_drawdown", -0.25), "lt"),
        ("final_holdout_excess_return_vs_000852", row.get("final_holdout_excess_return_vs_000852"), thresholds.get("min_final_holdout_excess_return_vs_000852", -0.05), "le"),
        ("final_holdout_total_return", row.get("final_holdout_total_return"), thresholds.get("min_final_holdout_total_return", -0.08), "le"),
    ]
    for name, actual, threshold, op in numeric_checks:
        actual_value = safe_float(actual)
        threshold_value = safe_float(threshold)
        if not math.isfinite(actual_value):
            reasons.append(f"{name}=missing")
        elif op == "le" and actual_value <= threshold_value:
            reasons.append(f"{name}<={threshold_value}")
        elif op == "lt" and actual_value < threshold_value:
            reasons.append(f"{name}<{threshold_value}")
    required = contract.get("required") or {}
    if row.get("valid_signal_status") != required.get("valid_signal_status", "stable"):
        reasons.append(f"valid_signal_status={row.get('valid_signal_status')}")
    diagnosis = contract.get("diagnosis") or {}
    if row.get("model_diagnosis_primary_diagnosis") in set(diagnosis.get("hard_reject_primary_diagnosis") or []):
        reasons.append(f"primary_diagnosis={row.get('model_diagnosis_primary_diagnosis')}")
    by_conf = diagnosis.get("hard_reject_confidence_by_diagnosis") or {}
    primary = row.get("model_diagnosis_primary_diagnosis")
    if primary in by_conf and row.get("model_diagnosis_confidence") in set(by_conf[primary]):
        reasons.append(f"primary_diagnosis={primary}:{row.get('model_diagnosis_confidence')}")
    return reasons


def _needs_more_evidence_reasons(row: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    thresholds = contract.get("thresholds") or {}
    required = contract.get("required") or {}
    test_reuse = contract.get("test_reuse") or {}
    reasons = []
    if row.get("cv_confirmation_status") != required.get("cv_confirmation_status", "passed"):
        reasons.append(f"cv_confirmation_status={row.get('cv_confirmation_status')}")
    min_days = safe_int(thresholds.get("min_final_holdout_trading_days", 40))
    actual_days = safe_int(row.get("final_holdout_trading_days"))
    if actual_days < min_days:
        reasons.append(f"final_holdout_trading_days<{min_days}")
    wave_no = safe_int(row.get("test_reuse_wave_no"))
    required_after = safe_int(test_reuse.get("final_holdout_required_after_wave", 3))
    passed_status = str(test_reuse.get("final_holdout_passed_status", "passed"))
    if wave_no > required_after and row.get("final_holdout_status") != passed_status:
        reasons.append("test_reuse_wave_no_gt_final_holdout_threshold_without_passed_holdout")
    if not row.get("acceptance_contract_version"):
        reasons.append("acceptance_contract_version=missing")
    return reasons


def safe_float(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return math.nan
    return out if math.isfinite(out) else math.nan


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None:
            return value
    return None
