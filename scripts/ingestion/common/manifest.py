"""读取 ODS 采集 manifest。Phase 0 实现。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_manifest(path: str | Path = "configs/ingestion/ods_current_scope_v0.yml") -> dict[str, Any]:
    """读取 manifest YAML，返回完整配置。"""
    with open(path) as f:
        return yaml.safe_load(f)


def get_enabled_endpoints(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """返回 manifest 中 enabled=true 的 endpoint 列表。"""
    return [ep for ep in manifest.get("endpoints", []) if ep.get("enabled", True)]


def get_endpoint(manifest: dict[str, Any], endpoint_name: str) -> dict[str, Any] | None:
    """按 endpoint 名称查找配置。"""
    for ep in manifest.get("endpoints", []):
        if ep["endpoint"] == endpoint_name:
            return ep
    return None
