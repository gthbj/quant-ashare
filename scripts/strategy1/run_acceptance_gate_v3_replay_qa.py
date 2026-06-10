#!/usr/bin/env python3
"""Run Strategy 1 acceptance-gate v3 replay QA with contract-rendered parameters."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists() and str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from quant_ashare.strategy1.catalog import resolve_step_path
from scripts.strategy1_cloudrun.acceptance import contract_hash, contract_version, load_acceptance_contract
from scripts.strategy1_cloudrun.bq_io import execute_query, make_client


DEFAULT_CONTRACT_PATH = "configs/strategy1/model_acceptance_contract_v3.yml"
DEFAULT_SQL_TEMPLATE_PATH = "sql/strategy1/acceptance/qa_acceptance_gate_v3_replay_outputs.sql"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="策略 1 验收门 v3 replay BigQuery QA")
    parser.add_argument("--project", default="data-aquarium")
    parser.add_argument("--region", default="asia-east2")
    parser.add_argument("--contract", default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--sql-template", default=DEFAULT_SQL_TEMPLATE_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = load_acceptance_contract(args.contract)
    if contract_version(contract) != "model_acceptance_contract_v3":
        raise SystemExit("--contract must point to model_acceptance_contract_v3")
    sql = render_sql(resolve_step_path(args.sql_template).read_text(encoding="utf-8"), contract)
    client = make_client(args.project, args.region)
    execute_query(
        client,
        sql,
        labels={"component": "strategy1", "step": "qa_accept_v3_replay"},
    )
    print(json.dumps(
        {
            "status": "succeeded",
            "acceptance_contract_version": contract_version(contract),
            "acceptance_contract_sha256": contract_hash(contract),
            "final_holdout_enforcement": final_holdout_enforcement(contract),
            "legacy_valid_as_cv_search_ids": legacy_valid_as_cv_search_ids(contract),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


def render_sql(template: str, contract: dict[str, object]) -> str:
    replacements = {
        "standalone_acceptance_gate_version_required": acceptance_gate_version(contract),
        "standalone_contract_version_required": contract_version(contract),
        "standalone_contract_hash_required": contract_hash(contract),
        "standalone_search_ids_json_required": json.dumps(replay_search_ids(contract), ensure_ascii=False),
        "standalone_top_k_per_search_required": str(replay_top_k_per_search(contract)),
        "standalone_primary_benchmark_sec_code_required": primary_benchmark_sec_code(contract),
        "standalone_comparison_benchmark_sec_codes_json_required": json.dumps(
            comparison_benchmark_sec_codes(contract),
            ensure_ascii=False,
        ),
        "standalone_final_holdout_enforcement_required": final_holdout_enforcement(contract),
        "standalone_legacy_valid_as_cv_search_ids_json_required": json.dumps(
            legacy_valid_as_cv_search_ids(contract),
            ensure_ascii=False,
        ),
        "standalone_full_start_date_required": window_start_date(contract, "default_replay_and_initial_cutover_full_period"),
        "standalone_full_end_date_required": window_end_date(contract, "default_replay_and_initial_cutover_full_period"),
        "standalone_valid_start_date_required": window_start_date(contract, "valid"),
        "standalone_valid_end_date_required": window_end_date(contract, "valid"),
        "standalone_test_start_date_required": window_start_date(contract, "test"),
        "standalone_test_end_date_required": window_end_date(contract, "test"),
        "standalone_final_holdout_start_date_required": window_start_date(contract, "final_holdout"),
        "standalone_final_holdout_end_date_required": window_end_date(contract, "final_holdout"),
        "standalone_min_valid_rank_ic_required": str(signal_threshold_value(contract, "valid_rank_ic")),
        "standalone_min_valid_top_minus_bottom_required": str(
            signal_threshold_value(contract, "valid_top_minus_bottom_fwd_ret")
        ),
        "standalone_min_test_rank_ic_required": str(signal_threshold_value(contract, "test_rank_ic")),
        "standalone_min_test_top_minus_bottom_required": str(
            signal_threshold_value(contract, "test_top_minus_bottom_fwd_ret")
        ),
        "standalone_min_sharpe_required": str(absolute_threshold_value(contract, "sharpe_ratio")),
        "standalone_min_calmar_ratio_required": str(absolute_threshold_value(contract, "calmar_ratio")),
        "standalone_min_final_holdout_trading_days_required": str(final_holdout_min_trading_days(contract)),
        "standalone_allowed_score_orientations_json_required": json.dumps(
            allowed_score_orientations(contract),
            ensure_ascii=False,
        ),
    }
    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value, 1)
    return rendered


def acceptance_gate_version(contract: dict[str, object]) -> str:
    gate = (contract.get("gate") or {}) if isinstance(contract, dict) else {}
    value = gate.get("acceptance_gate_version") if isinstance(gate, dict) else None
    return str(value or "strategy1_acceptance_gate_v3")


def final_holdout_enforcement(contract: dict[str, object]) -> str:
    gate = (contract.get("final_holdout_gate") or {}) if isinstance(contract, dict) else {}
    enforcement = gate.get("enforcement") if isinstance(gate, dict) else None
    return str(enforcement or "blocking")


def replay_search_ids(contract: dict[str, object]) -> list[str]:
    scope = (contract.get("replay_scope") or {}) if isinstance(contract, dict) else {}
    values = scope.get("search_ids") if isinstance(scope, dict) else None
    return [str(value) for value in (values or [])]


def replay_top_k_per_search(contract: dict[str, object]) -> int:
    scope = (contract.get("replay_scope") or {}) if isinstance(contract, dict) else {}
    value = scope.get("top_k_per_search") if isinstance(scope, dict) else None
    return int(value or 5)


def primary_benchmark_sec_code(contract: dict[str, object]) -> str:
    benchmarks = (contract.get("benchmarks") or {}) if isinstance(contract, dict) else {}
    value = benchmarks.get("primary_benchmark_sec_code") if isinstance(benchmarks, dict) else None
    return str(value or "000001.SH")


def comparison_benchmark_sec_codes(contract: dict[str, object]) -> list[str]:
    benchmarks = (contract.get("benchmarks") or {}) if isinstance(contract, dict) else {}
    values = benchmarks.get("comparison_benchmarks") if isinstance(benchmarks, dict) else None
    codes: list[str] = []
    for value in values or []:
        if isinstance(value, dict) and value.get("sec_code") is not None:
            codes.append(str(value["sec_code"]))
    return codes


def window_start_date(contract: dict[str, object], window_key: str) -> str:
    windows = (contract.get("windows") or {}) if isinstance(contract, dict) else {}
    window = windows.get(window_key) if isinstance(windows, dict) else None
    value = window.get("start_date") if isinstance(window, dict) else None
    if value is None:
        raise KeyError(f"missing windows.{window_key}.start_date in v3 contract")
    return str(value)


def window_end_date(contract: dict[str, object], window_key: str) -> str:
    windows = (contract.get("windows") or {}) if isinstance(contract, dict) else {}
    window = windows.get(window_key) if isinstance(windows, dict) else None
    value = window.get("end_date") if isinstance(window, dict) else None
    if value is None:
        raise KeyError(f"missing windows.{window_key}.end_date in v3 contract")
    return str(value)


def signal_threshold_value(contract: dict[str, object], metric_key: str) -> float:
    gate = (contract.get("signal_quality_gate") or {}) if isinstance(contract, dict) else {}
    thresholds = gate.get("thresholds") if isinstance(gate, dict) else None
    metric = thresholds.get(metric_key) if isinstance(thresholds, dict) else None
    value = metric.get("value") if isinstance(metric, dict) else None
    if value is None:
        raise KeyError(f"missing signal_quality_gate.thresholds.{metric_key}.value in v3 contract")
    return float(value)


def absolute_threshold_value(contract: dict[str, object], metric_key: str) -> float:
    gate = (contract.get("absolute_performance_gate") or {}) if isinstance(contract, dict) else {}
    metric = gate.get(metric_key) if isinstance(gate, dict) else None
    value = metric.get("value") if isinstance(metric, dict) else None
    if value is None:
        raise KeyError(f"missing absolute_performance_gate.{metric_key}.value in v3 contract")
    return float(value)


def final_holdout_min_trading_days(contract: dict[str, object]) -> int:
    gate = (contract.get("final_holdout_gate") or {}) if isinstance(contract, dict) else {}
    metric = gate.get("trading_day_count") if isinstance(gate, dict) else None
    value = metric.get("value") if isinstance(metric, dict) else None
    if value is None:
        raise KeyError("missing final_holdout_gate.trading_day_count.value in v3 contract")
    return int(value)


def legacy_valid_as_cv_search_ids(contract: dict[str, object]) -> list[str]:
    compatibility = (contract.get("replay_compatibility") or {}) if isinstance(contract, dict) else {}
    values = compatibility.get("legacy_valid_as_cv_search_ids") if isinstance(compatibility, dict) else None
    return [str(value) for value in (values or [])]


def allowed_score_orientations(contract: dict[str, object]) -> list[str]:
    required = (contract.get("required") or {}) if isinstance(contract, dict) else {}
    values = required.get("allowed_score_orientation") if isinstance(required, dict) else None
    return [str(value) for value in (values or [])]


if __name__ == "__main__":
    raise SystemExit(main())
