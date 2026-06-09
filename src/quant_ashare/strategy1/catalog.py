"""Strategy 1 step catalog loading and path resolution."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - Cloud Run image installs PyYAML.
    yaml = None


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG_PATH = REPO_ROOT / "configs/strategy1/active_step_catalog.yml"
DECLARE_PARAM_RE = re.compile(
    r"(?im)^\s*DECLARE\s+(?P<name>p_[A-Za-z0-9_]+)\s+"
    r"(?P<type>ARRAY<STRING>|ARRAY<INT64>|STRING|INT64|FLOAT64|BOOL|DATE|TIMESTAMP)"
    r"(?:\s+DEFAULT\s+(?P<value>[^;]*))?;"
)


def repo_relative(path: str | Path) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            candidate = candidate.relative_to(REPO_ROOT)
        except ValueError:
            return candidate.as_posix()
    return candidate.as_posix()


def repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def load_step_catalog(path: str | Path | None = None) -> dict[str, Any]:
    catalog_path = repo_path(path) if path else DEFAULT_CATALOG_PATH
    if yaml is None:
        raise RuntimeError("PyYAML is required to read Strategy1 step catalog")
    data = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    data["_catalog_path"] = str(catalog_path)
    return data


def steps(catalog: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    catalog = catalog or load_step_catalog()
    return catalog.get("steps") or {}


def step_config(step_name: str, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    all_steps = steps(catalog)
    if step_name not in all_steps:
        raise KeyError(f"unknown Strategy1 step: {step_name}")
    return all_steps[step_name]


def step_name_for_path(path: str | Path, catalog: dict[str, Any] | None = None) -> str | None:
    rel = repo_relative(path)
    for name, cfg in steps(catalog).items():
        candidates = {
            cfg.get("sql_path"),
            cfg.get("target_path"),
            cfg.get("current_path"),
        }
        if rel in {candidate for candidate in candidates if candidate}:
            return name
    return None


def resolve_step_path(step_or_path: str | Path, catalog: dict[str, Any] | None = None) -> Path:
    catalog = catalog or load_step_catalog()
    key = str(step_or_path)
    if key in steps(catalog):
        cfg = step_config(key, catalog)
        return repo_path(cfg.get("sql_path") or cfg["target_path"])
    mapped_step = step_name_for_path(step_or_path, catalog)
    if mapped_step:
        cfg = step_config(mapped_step, catalog)
        return repo_path(cfg.get("sql_path") or cfg["target_path"])
    return repo_path(step_or_path)


def declared_params(sql_text: str) -> dict[str, dict[str, str | None]]:
    return {
        match.group("name"): {
            "type": match.group("type"),
            "default": match.group("value"),
        }
        for match in DECLARE_PARAM_RE.finditer(sql_text)
    }


def validate_catalog(catalog: dict[str, Any] | str | Path | None = None) -> list[str]:
    if catalog is None or isinstance(catalog, (str, Path)):
        catalog = load_step_catalog(catalog)
    errors: list[str] = []
    for name, cfg in steps(catalog).items():
        target = cfg.get("target_path") or cfg.get("sql_path")
        if not target:
            errors.append(f"{name}: missing target_path/sql_path")
            continue
        if cfg.get("status") != "retired" and not repo_path(target).exists():
            errors.append(f"{name}: target SQL path does not exist: {target}")
            continue
        sql_file = repo_path(cfg.get("sql_path") or target)
        if not sql_file.exists():
            continue
        declared = set(declared_params(sql_file.read_text(encoding="utf-8")))
        required = set(cfg.get("required_params") or [])
        optional = cfg.get("optional_params") or {}
        if not isinstance(optional, dict):
            errors.append(f"{name}: optional_params must be a mapping")
            optional = {}
        for param, spec in optional.items():
            if not isinstance(spec, dict):
                errors.append(f"{name}: optional param {param} must be an object")
            elif "allow_default" not in spec:
                errors.append(f"{name}: optional param {param} missing allow_default")
        internal = set(cfg.get("internal_params") or [])
        unmanaged = declared - required - set(optional) - internal
        if unmanaged:
            errors.append(f"{name}: declared params missing catalog contract: {sorted(unmanaged)}")
        missing_declared = (required | set(optional) | internal) - declared
        if missing_declared:
            errors.append(f"{name}: catalog params not declared by SQL: {sorted(missing_declared)}")
    return errors
