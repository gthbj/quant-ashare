"""Table role resolver for Strategy 1 dataset roles."""

from __future__ import annotations

from typing import Any

from quant_ashare.strategy1.catalog import load_step_catalog


def resolve_table_role(
    role: str,
    *,
    dataset_role: str | None = None,
    project: str | None = None,
    catalog: dict[str, Any] | None = None,
    allow_future_research: bool = False,
) -> str:
    catalog = catalog or load_step_catalog()
    table_roles = catalog.get("table_roles") or {}
    if role not in table_roles:
        raise KeyError(f"unknown table role: {role}")
    dataset_roles = catalog.get("dataset_roles") or {}
    dataset_role = dataset_role or catalog.get("current_dataset_role", "ads")
    if dataset_role not in dataset_roles:
        raise KeyError(f"unknown dataset role: {dataset_role}")
    dataset_cfg = dataset_roles[dataset_role]
    if dataset_role != "ads" and not (allow_future_research or dataset_cfg.get("enabled_by_default")):
        raise ValueError(
            f"dataset_role={dataset_role} is not enabled by default"
        )
    effective_dataset_role = dataset_role
    table_cfg = table_roles[role]
    table_name_key = "research_table" if effective_dataset_role == "research" else "ads_table"
    table_name = table_cfg.get(table_name_key) or table_cfg["ads_table"]
    project_override_key = f"{effective_dataset_role}_project"
    dataset_override_key = f"{effective_dataset_role}_dataset"
    project_id = (
        project
        or table_cfg.get(project_override_key)
        or dataset_cfg.get("project")
        or catalog.get("project")
    )
    dataset_id = table_cfg.get(dataset_override_key) or dataset_cfg["dataset"]
    return f"{project_id}.{dataset_id}.{table_name}"


def table_role_config(role: str, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    catalog = catalog or load_step_catalog()
    table_roles = catalog.get("table_roles") or {}
    if role not in table_roles:
        raise KeyError(f"unknown table role: {role}")
    return table_roles[role]
