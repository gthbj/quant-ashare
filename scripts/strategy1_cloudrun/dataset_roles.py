"""Dataset-role helpers for Strategy 1 runner code."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists() and str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from quant_ashare.strategy1.catalog import load_step_catalog
from quant_ashare.strategy1.sql_render import render_table_roles
from quant_ashare.strategy1.table_roles import resolve_table_role


OUTPUT_DATASET_ROLE_CHOICES = ("ads", "research")
DEFAULT_OUTPUT_DATASET_ROLE = "research"
DEFAULT_SQL_REWRITE_EXCLUDED_ROLES = frozenset({"acceptance_result"})


def validate_output_dataset_role(dataset_role: str | None) -> str:
    role = dataset_role or DEFAULT_OUTPUT_DATASET_ROLE
    if role not in OUTPUT_DATASET_ROLE_CHOICES:
        raise ValueError(f"unknown output_dataset_role: {role}")
    return role


def allow_future_research(dataset_role: str | None) -> bool:
    return validate_output_dataset_role(dataset_role) == "research"


def output_dataset_role_cli_args(dataset_role: str | None, *, equals: bool = False) -> list[str]:
    role = validate_output_dataset_role(dataset_role)
    if equals:
        return [f"--output-dataset-role={role}"]
    return ["--output-dataset-role", role]


def table_id(
    role: str,
    *,
    dataset_role: str = DEFAULT_OUTPUT_DATASET_ROLE,
    project: str | None = None,
) -> str:
    dataset_role = validate_output_dataset_role(dataset_role)
    return resolve_table_role(
        role,
        dataset_role=dataset_role,
        project=project,
        allow_future_research=allow_future_research(dataset_role),
    )


class TableResolver:
    def __init__(self, *, dataset_role: str = DEFAULT_OUTPUT_DATASET_ROLE, project: str | None = None) -> None:
        self.dataset_role = validate_output_dataset_role(dataset_role)
        self.project = project

    def fqn(self, role: str) -> str:
        return table_id(role, dataset_role=self.dataset_role, project=self.project)


def rewrite_sql_dataset_role(
    sql: str,
    *,
    dataset_role: str = DEFAULT_OUTPUT_DATASET_ROLE,
    project: str | None = None,
    role_names: Iterable[str] | None = None,
) -> str:
    dataset_role = validate_output_dataset_role(dataset_role)
    if dataset_role == "ads":
        return sql

    catalog = load_step_catalog()
    selected_roles = (
        set(role_names)
        if role_names is not None
        else set(catalog["table_roles"]) - DEFAULT_SQL_REWRITE_EXCLUDED_ROLES
    )
    replacements: dict[str, str] = {}
    for role in selected_roles:
        if role not in catalog["table_roles"]:
            continue
        target = resolve_table_role(
            role,
            dataset_role=dataset_role,
            project=project,
            catalog=catalog,
            allow_future_research=True,
        )
        canonical_ads_source = resolve_table_role(role, dataset_role="ads", catalog=catalog)
        _add_replacement(replacements, canonical_ads_source, target)
        if project:
            project_ads_source = resolve_table_role(
                role,
                dataset_role="ads",
                project=project,
                catalog=catalog,
            )
            _add_replacement(replacements, project_ads_source, target)
    return render_table_roles(sql, replacements)


def _add_replacement(replacements: dict[str, str], source: str, target: str) -> None:
    previous = replacements.get(source)
    if previous is not None and previous != target:
        raise ValueError(f"ambiguous dataset-role SQL rewrite for {source}: {previous} vs {target}")
    replacements[source] = target
