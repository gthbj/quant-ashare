"""Table role resolver for the current Strategy 1 ADS-compatible phase."""

from __future__ import annotations

from typing import Any

from quant_ashare.strategy1.catalog import load_step_catalog


def resolve_table_role(
    role: str,
    *,
    dataset_role: str = "ads",
    project: str | None = None,
    catalog: dict[str, Any] | None = None,
    allow_future_research: bool = False,
) -> str:
    catalog = catalog or load_step_catalog()
    table_roles = catalog.get("table_roles") or {}
    if role not in table_roles:
        raise KeyError(f"unknown table role: {role}")
    effective_dataset_role = dataset_role if allow_future_research else "ads"
    dataset_roles = catalog.get("dataset_roles") or {}
    dataset_cfg = dataset_roles[effective_dataset_role]
    table_cfg = table_roles[role]
    table_name_key = "research_table" if effective_dataset_role == "research" else "ads_table"
    table_name = table_cfg.get(table_name_key) or table_cfg["ads_table"]
    project_id = project or dataset_cfg.get("project") or catalog.get("project")
    return f"{project_id}.{dataset_cfg['dataset']}.{table_name}"


def table_role_config(role: str, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    catalog = catalog or load_step_catalog()
    table_roles = catalog.get("table_roles") or {}
    if role not in table_roles:
        raise KeyError(f"unknown table role: {role}")
    return table_roles[role]

