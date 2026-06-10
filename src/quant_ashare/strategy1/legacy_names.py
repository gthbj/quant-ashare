"""Legacy-name exception registry for Strategy1 structure cleanup."""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any

from quant_ashare.strategy1.catalog import load_step_catalog


def allowed_legacy_names(catalog: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    catalog = catalog or load_step_catalog()
    return dict(catalog.get("allowed_legacy_names") or {})


def legacy_name_config(name: str, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = allowed_legacy_names(catalog)
    if name not in registry:
        raise KeyError(f"legacy name is not registered: {name}")
    return dict(registry[name])


def is_legacy_name_allowed(name: str, path: str, catalog: dict[str, Any] | None = None) -> bool:
    cfg = legacy_name_config(name, catalog)
    return any(fnmatch(path, pattern) for pattern in cfg.get("allowed_in") or [])
