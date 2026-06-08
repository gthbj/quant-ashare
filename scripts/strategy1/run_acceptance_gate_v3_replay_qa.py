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

from scripts.strategy1_cloudrun.acceptance import contract_hash, contract_version, load_acceptance_contract
from scripts.strategy1_cloudrun.bq_io import execute_query, make_client


DEFAULT_CONTRACT_PATH = "configs/strategy1/model_acceptance_contract_v3.yml"
DEFAULT_SQL_TEMPLATE_PATH = "sql/ml/strategy1/24_qa_acceptance_gate_v3_replay_outputs.sql"


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
    sql = render_sql(Path(args.sql_template).read_text(encoding="utf-8"), contract)
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
    rendered = template.replace("standalone_contract_hash_required", contract_hash(contract), 1)
    rendered = rendered.replace(
        "standalone_final_holdout_enforcement_required",
        final_holdout_enforcement(contract),
        1,
    )
    rendered = rendered.replace(
        "standalone_legacy_valid_as_cv_search_ids_json_required",
        json.dumps(legacy_valid_as_cv_search_ids(contract), ensure_ascii=False),
        1,
    )
    return rendered


def final_holdout_enforcement(contract: dict[str, object]) -> str:
    gate = (contract.get("final_holdout_gate") or {}) if isinstance(contract, dict) else {}
    enforcement = gate.get("enforcement") if isinstance(gate, dict) else None
    return str(enforcement or "blocking")


def legacy_valid_as_cv_search_ids(contract: dict[str, object]) -> list[str]:
    compatibility = (contract.get("replay_compatibility") or {}) if isinstance(contract, dict) else {}
    values = compatibility.get("legacy_valid_as_cv_search_ids") if isinstance(compatibility, dict) else None
    return [str(value) for value in (values or [])]


if __name__ == "__main__":
    raise SystemExit(main())
