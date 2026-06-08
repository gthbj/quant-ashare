"""Shared Strategy 1 model acceptance contract logic."""

from __future__ import annotations

import math
import hashlib
from pathlib import Path
from typing import Any

from scripts.strategy1_cloudrun.bq_io import json_dumps_strict
from scripts.strategy1_cloudrun.config import read_mapping


DEFAULT_CONTRACT_PATH = "configs/strategy1/model_acceptance_contract_v1.yml"


def load_acceptance_contract(path: str | Path | None = None) -> dict[str, Any]:
    contract = read_mapping(path or DEFAULT_CONTRACT_PATH)
    if not contract.get("contract_version"):
        raise ValueError("acceptance contract must define contract_version")
    contract = dict(contract)
    contract.setdefault("contract_name", str(contract["contract_version"]))
    contract["_contract_sha256"] = contract_payload_hash(contract)
    contract["contract_sha256"] = contract.get("contract_sha256") or contract["_contract_sha256"]
    return contract


def contract_payload_hash(contract: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in contract.items()
        if key not in {"contract_sha256", "_contract_sha256", "_contract_path"}
    }
    encoded = json_dumps_strict(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def contract_version(contract: dict[str, Any]) -> str:
    return str(contract["contract_version"])


def contract_hash(contract: dict[str, Any]) -> str:
    return str(contract.get("_contract_sha256") or contract.get("contract_sha256") or contract_payload_hash(contract))


def _threshold_float(thresholds: dict[str, Any], key: str, default: float) -> float:
    value = safe_float(thresholds.get(key))
    return value if math.isfinite(value) else default


def _primary_benchmark_metric(
    row: dict[str, Any],
    primary_key: str,
    legacy_key: str,
    fallback_key: str | None = None,
) -> Any:
    keys = [primary_key, legacy_key]
    if fallback_key is not None:
        keys.append(fallback_key)
    return _first(row, *keys)


def full_period_max_drawdown_threshold(contract: dict[str, Any]) -> float:
    thresholds = contract.get("thresholds") or {}
    fallback = _threshold_float(thresholds, "min_max_drawdown", -0.25)
    return _threshold_float(thresholds, "min_full_period_max_drawdown", fallback)


def risk_feature_max_drawdown_target(contract: dict[str, Any]) -> float:
    thresholds = contract.get("thresholds") or {}
    fallback = full_period_max_drawdown_threshold(contract)
    return _threshold_float(thresholds, "risk_feature_max_drawdown_target", fallback)


def contract_sql_params(contract: dict[str, Any]) -> dict[str, Any]:
    """Return SQL DECLARE parameters derived from the shared YAML contract."""

    thresholds = contract.get("thresholds") or {}
    required = contract.get("required") or {}
    test_reuse = contract.get("test_reuse") or {}
    implementation = contract.get("implementation_gate") or {}
    return {
        "p_acceptance_contract_version": contract_version(contract),
        "p_acceptance_contract_sha256": contract_hash(contract),
        "p_min_valid_rank_ic": thresholds.get("min_valid_rank_ic", 0.0),
        "p_min_valid_rank_ic_t_stat": thresholds.get("min_valid_rank_ic_t_stat", 1.0),
        "p_min_valid_top_minus_bottom_fwd_ret": thresholds.get("min_valid_top_minus_bottom_fwd_ret", 0.0),
        "p_min_test_rank_ic": thresholds.get("min_test_rank_ic", 0.0),
        "p_min_test_rank_ic_t_stat": thresholds.get("min_test_rank_ic_t_stat", 1.0),
        "p_min_test_top_minus_bottom_fwd_ret": thresholds.get("min_test_top_minus_bottom_fwd_ret", 0.0),
        "p_min_test_year_excess_return_vs_000852": thresholds.get("min_test_year_excess_return_vs_000852", 0.0),
        "p_min_overall_excess_return_vs_000852": thresholds.get("min_overall_excess_return_vs_000852", 0.0),
        "p_min_total_return": thresholds.get("min_total_return", 0.0),
        "p_min_sharpe": thresholds.get("min_sharpe", 0.70),
        "p_min_max_drawdown": thresholds.get("min_max_drawdown", -0.25),
        "p_min_full_period_excess_return_vs_000852": thresholds.get(
            "min_full_period_excess_return_vs_000852",
            thresholds.get("min_overall_excess_return_vs_000852", 0.0),
        ),
        "p_hard_reject_full_period_excess_return_vs_000852": thresholds.get(
            "hard_reject_full_period_excess_return_vs_000852", -0.03
        ),
        "p_min_full_period_information_ratio": thresholds.get("min_full_period_information_ratio", 0.25),
        "p_hard_reject_full_period_information_ratio": thresholds.get("hard_reject_full_period_information_ratio", 0.0),
        "p_min_full_period_excess_return_vs_eligible_executable": thresholds.get(
            "min_full_period_excess_return_vs_eligible_executable", 0.0
        ),
        "p_hard_reject_full_period_excess_return_vs_eligible_executable": thresholds.get(
            "hard_reject_full_period_excess_return_vs_eligible_executable", -0.03
        ),
        "p_min_full_period_information_ratio_vs_eligible_executable": thresholds.get(
            "min_full_period_information_ratio_vs_eligible_executable", 0.0
        ),
        "p_min_full_period_max_drawdown": full_period_max_drawdown_threshold(contract),
        "p_risk_feature_max_drawdown_target": risk_feature_max_drawdown_target(contract),
        "p_hard_reject_full_period_max_drawdown": thresholds.get("hard_reject_full_period_max_drawdown", -0.25),
        "p_min_full_period_relative_max_drawdown_vs_000852": thresholds.get(
            "min_full_period_relative_max_drawdown_vs_000852", -0.18
        ),
        "p_hard_reject_full_period_relative_max_drawdown_vs_000852": thresholds.get(
            "hard_reject_full_period_relative_max_drawdown_vs_000852", -0.25
        ),
        "p_min_final_holdout_excess_return_vs_000852": thresholds.get("min_final_holdout_excess_return_vs_000852", -0.05),
        "p_hard_reject_final_holdout_excess_return_vs_000852": thresholds.get(
            "hard_reject_final_holdout_excess_return_vs_000852", -0.10
        ),
        "p_min_final_holdout_total_return": thresholds.get("min_final_holdout_total_return", -0.08),
        "p_weak_valid_rank_ic_threshold": thresholds.get("weak_valid_rank_ic_threshold", 0.01),
        "p_min_final_holdout_trading_days": thresholds.get("min_final_holdout_trading_days", 40),
        "p_actual_holdings_ratio_min": implementation.get("actual_holdings_ratio_min", 0.80),
        "p_actual_holdings_ratio_hard_fail": implementation.get("actual_holdings_ratio_hard_fail", 0.60),
        "p_avg_cash_weight_max": implementation.get("avg_cash_weight_max", 0.10),
        "p_avg_cash_weight_hard_fail": implementation.get("avg_cash_weight_hard_fail", 0.20),
        "p_max_cash_weight_max": implementation.get("max_cash_weight_max", 0.20),
        "p_skipped_buy_rate_max": implementation.get("skipped_buy_rate_max", 0.20),
        "p_skipped_buy_rate_hard_fail": implementation.get("skipped_buy_rate_hard_fail", 0.35),
        "p_max_single_weight_realized_max": implementation.get("max_single_weight_realized_max", 0.055),
        "p_low_price_median_ratio_needs_evidence": implementation.get("low_price_median_ratio_needs_evidence", 0.70),
        "p_low_price_median_ratio_hard_fail": implementation.get("low_price_median_ratio_hard_fail", 0.50),
        "p_low_price_active_weight_needs_evidence": implementation.get("low_price_active_weight_needs_evidence", 0.20),
        "p_low_price_contribution_share_hard_fail": implementation.get("low_price_contribution_share_hard_fail", 0.50),
        "p_required_valid_signal_status": required.get("valid_signal_status", "stable"),
        "p_required_cv_confirmation_status": required.get("cv_confirmation_status", "passed"),
        "p_required_ledger_version": required.get("required_ledger_version", "ledger_exec_v1_lot100"),
        "p_final_holdout_required_after_wave": test_reuse.get("final_holdout_required_after_wave", 3),
        "p_final_holdout_passed_status": test_reuse.get("final_holdout_passed_status", "passed"),
    }


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

    unmatched_reasons = _unmatched_input_state_reasons(row, contract)
    if unmatched_reasons:
        derived["unmatched_acceptance_state_reasons"] = unmatched_reasons
        return "rejected", "unmatched_acceptance_state", derived

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
        ("test_year_excess_return_vs_primary_benchmark", _primary_benchmark_metric(row, "test_year_excess_return_vs_primary_benchmark", "test_year_excess_return_vs_000852", "test_year_excess_return"), thresholds.get("min_test_year_excess_return_vs_000852", 0.0), "gt"),
        ("overall_excess_return_vs_primary_benchmark", _primary_benchmark_metric(row, "overall_excess_return_vs_primary_benchmark", "overall_excess_return_vs_000852", "excess_return"), thresholds.get("min_overall_excess_return_vs_000852", 0.0), "gt"),
        ("total_return", row.get("total_return"), thresholds.get("min_total_return", 0.0), "gt"),
        ("sharpe", row.get("sharpe"), thresholds.get("min_sharpe", 0.70), "ge"),
        ("max_drawdown", row.get("max_drawdown"), thresholds.get("min_max_drawdown", -0.25), "ge"),
        ("final_holdout_excess_return_vs_primary_benchmark", _primary_benchmark_metric(row, "final_holdout_excess_return_vs_primary_benchmark", "final_holdout_excess_return_vs_000852"), thresholds.get("min_final_holdout_excess_return_vs_000852", -0.05), "gt"),
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

    final_excess = safe_float(
        _primary_benchmark_metric(
            row,
            "final_holdout_excess_return_vs_primary_benchmark",
            "final_holdout_excess_return_vs_000852",
        )
    )
    final_total = safe_float(row.get("final_holdout_total_return"))
    if (math.isfinite(final_excess) and final_excess < 0) or (math.isfinite(final_total) and final_total < 0):
        derived["holdout_watch_flag"] = True

    wave_no = safe_int(row.get("test_reuse_wave_no"))
    required_after = safe_int(test_reuse.get("final_holdout_required_after_wave", 3))
    passed_status = str(test_reuse.get("final_holdout_passed_status", "passed"))
    if wave_no > required_after and row.get("final_holdout_status") != passed_status:
        return "needs_more_evidence", "test_reuse_wave_no_gt_final_holdout_threshold_without_passed_holdout", derived
    return "accepted", "all_acceptance_contract_gates_passed", derived


def derive_final_holdout_status(row: dict[str, Any], contract: dict[str, Any]) -> str | None:
    current = row.get("final_holdout_status")
    if current:
        return str(current)
    thresholds = contract.get("thresholds") or {}
    min_days = safe_float(thresholds.get("min_final_holdout_trading_days", 40))
    min_excess = safe_float(thresholds.get("min_final_holdout_excess_return_vs_000852", -0.05))
    min_total = safe_float(thresholds.get("min_final_holdout_total_return", -0.08))
    days = safe_float(row.get("final_holdout_trading_days"))
    excess = safe_float(
        _primary_benchmark_metric(
            row,
            "final_holdout_excess_return_vs_primary_benchmark",
            "final_holdout_excess_return_vs_000852",
        )
    )
    total = safe_float(row.get("final_holdout_total_return"))
    if not all(math.isfinite(value) for value in (days, excess, total)):
        return None
    if days >= min_days and excess > min_excess and total > min_total:
        return "passed"
    return "failed"


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
        ("test_year_excess_return_vs_primary_benchmark", _primary_benchmark_metric(row, "test_year_excess_return_vs_primary_benchmark", "test_year_excess_return_vs_000852", "test_year_excess_return"), thresholds.get("min_test_year_excess_return_vs_000852", 0.0), "le"),
        ("overall_excess_return_vs_primary_benchmark", _primary_benchmark_metric(row, "overall_excess_return_vs_primary_benchmark", "overall_excess_return_vs_000852", "excess_return"), thresholds.get("min_overall_excess_return_vs_000852", 0.0), "le"),
        ("total_return", row.get("total_return"), thresholds.get("min_total_return", 0.0), "le"),
        ("sharpe", row.get("sharpe"), thresholds.get("min_sharpe", 0.70), "lt"),
        ("max_drawdown", row.get("max_drawdown"), thresholds.get("min_max_drawdown", -0.25), "lt"),
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
    final_numeric_checks = [
        ("final_holdout_excess_return_vs_primary_benchmark", _primary_benchmark_metric(row, "final_holdout_excess_return_vs_primary_benchmark", "final_holdout_excess_return_vs_000852"), thresholds.get("min_final_holdout_excess_return_vs_000852", -0.05), "le"),
        ("final_holdout_total_return", row.get("final_holdout_total_return"), thresholds.get("min_final_holdout_total_return", -0.08), "le"),
    ]
    for name, actual, threshold, op in final_numeric_checks:
        actual_value = safe_float(actual)
        threshold_value = safe_float(threshold)
        if not math.isfinite(actual_value):
            continue
        if op == "le" and actual_value <= threshold_value:
            reasons.append(f"{name}<={threshold_value}")
    required = contract.get("required") or {}
    allowed_score_orientation = set(required.get("allowed_score_orientation") or ["identity", "reverse_probability"])
    if row.get("score_orientation") not in allowed_score_orientation:
        reasons.append(f"score_orientation={row.get('score_orientation')}")
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
    if _primary_benchmark_metric(row, "final_holdout_excess_return_vs_primary_benchmark", "final_holdout_excess_return_vs_000852") is None or row.get("final_holdout_total_return") is None:
        reasons.append("final_holdout_metrics=missing")
    wave_no = safe_int(row.get("test_reuse_wave_no"))
    required_after = safe_int(test_reuse.get("final_holdout_required_after_wave", 3))
    passed_status = str(test_reuse.get("final_holdout_passed_status", "passed"))
    if wave_no > required_after and row.get("final_holdout_status") != passed_status:
        reasons.append("test_reuse_wave_no_gt_final_holdout_threshold_without_passed_holdout")
    if not row.get("acceptance_contract_version"):
        reasons.append("acceptance_contract_version=missing")
    return reasons


def _unmatched_input_state_reasons(row: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    required = contract.get("required") or {}
    allowed_score_orientation = set(required.get("allowed_score_orientation") or ["identity", "reverse_probability"])
    reasons = []
    if row.get("score_orientation") is not None and row.get("score_orientation") not in allowed_score_orientation:
        reasons.append(f"score_orientation={row.get('score_orientation')}")
    valid_signal_status = row.get("valid_signal_status")
    if valid_signal_status is not None and valid_signal_status not in {"stable", "weak", "failed"}:
        reasons.append(f"valid_signal_status={valid_signal_status}")
    cv_status = row.get("cv_confirmation_status")
    if cv_status is not None and cv_status not in {"passed", "failed", "missing"}:
        reasons.append(f"cv_confirmation_status={cv_status}")
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
