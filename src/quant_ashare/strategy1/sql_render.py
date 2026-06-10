"""Strict SQL parameter rendering for Strategy 1 shared SQL."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

from quant_ashare.strategy1.catalog import (
    declared_params,
    load_step_catalog,
    repo_path,
    resolve_step_path,
    step_config,
)


DECLARE_DEFAULT_RE = re.compile(
    r"(?im)^(\s*DECLARE\s+(?P<name>p_[A-Za-z0-9_]+)\s+"
    r"(?P<type>ARRAY<STRING>|ARRAY<INT64>|STRING|INT64|FLOAT64|BOOL|DATE|TIMESTAMP)"
    r"\s+DEFAULT\s+)(?P<value>[^;]*)(;)"
)


def render_sql_file(
    script_path: str | Path,
    params: dict[str, Any],
    *,
    step: str | None = None,
    catalog: dict[str, Any] | None = None,
    strict: bool = False,
) -> str:
    catalog = catalog or load_step_catalog()
    resolved_path = resolve_step_path(script_path, catalog)
    sql = resolved_path.read_text(encoding="utf-8")
    cfg = step_config(step, catalog) if step else _config_for_path(script_path, catalog)
    if cfg and strict:
        validate_render_params(sql, params, cfg)
    return render_sql_text(sql, params)


def render_sql_step(step: str, params: dict[str, Any], *, catalog: dict[str, Any] | None = None) -> str:
    catalog = catalog or load_step_catalog()
    cfg = step_config(step, catalog)
    sql_path = repo_path(cfg.get("sql_path") or cfg["target_path"])
    sql = sql_path.read_text(encoding="utf-8")
    validate_render_params(sql, params, cfg)
    return render_sql_text(sql, params)


def render_sql_text(sql: str, params: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        if name not in params:
            return match.group(0)
        rendered = render_value(params[name], match.group("type"))
        return f"{match.group(1)}{rendered}{match.group(5)}"

    return DECLARE_DEFAULT_RE.sub(replace, sql)


def validate_render_params(sql: str, params: dict[str, Any], step_cfg: dict[str, Any]) -> None:
    declared = set(declared_params(sql))
    required = set(step_cfg.get("required_params") or [])
    optional = step_cfg.get("optional_params") or {}
    internal = set(step_cfg.get("internal_params") or [])
    missing_required = sorted(name for name in required if name not in params)
    if missing_required:
        raise ValueError(f"{step_cfg.get('stable_name', 'step')} missing required SQL params: {missing_required}")
    unmanaged_missing = []
    for name in sorted(declared - set(params)):
        if name in required:
            unmanaged_missing.append(name)
            continue
        if name in internal:
            continue
        spec = optional.get(name)
        if spec and spec.get("allow_default") is True:
            continue
        unmanaged_missing.append(name)
    if unmanaged_missing:
        raise ValueError(
            f"{step_cfg.get('stable_name', 'step')} would keep unmanaged SQL defaults: {unmanaged_missing}"
        )


def render_value(value: Any, sql_type: str) -> str:
    if value is None:
        return "NULL"
    if sql_type == "STRING":
        escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"
    if sql_type == "DATE":
        if isinstance(value, (dt.datetime, dt.date)):
            value = value.isoformat()[:10]
        return f"DATE '{value}'"
    if sql_type == "TIMESTAMP":
        if isinstance(value, dt.datetime):
            value = value.isoformat()
        return f"TIMESTAMP '{value}'"
    if sql_type == "BOOL":
        return "TRUE" if bool(value) else "FALSE"
    if sql_type in {"INT64", "FLOAT64"}:
        return str(value)
    if sql_type == "ARRAY<STRING>":
        values = ", ".join(render_value(item, "STRING") for item in value)
        return f"[{values}]"
    if sql_type == "ARRAY<INT64>":
        values = ", ".join(render_value(item, "INT64") for item in value)
        return f"[{values}]"
    raise ValueError(f"unsupported SQL type: {sql_type}")


def _config_for_path(path: str | Path, catalog: dict[str, Any]) -> dict[str, Any] | None:
    resolved = resolve_step_path(path, catalog)
    rel = resolved.relative_to(repo_path(".")).as_posix() if resolved.is_absolute() else resolved.as_posix()
    for cfg in (catalog.get("steps") or {}).values():
        if rel in {cfg.get("sql_path"), cfg.get("target_path")}:
            return cfg
    return None
