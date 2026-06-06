#!/usr/bin/env python3
"""Generate Dataform SQLX actions from the canonical BigQuery SQL files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATAFORM_DIR = REPO_ROOT / "dataform"
MANIFEST_PATH = DATAFORM_DIR / "action_manifest.json"
GENERATED_MARKER = "Generated from canonical sql/ by scripts/dataform/generate_sqlx_from_sql.py."


def js_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_config(action: dict[str, Any]) -> str:
    ordered_keys = [
        "type",
        "database",
        "schema",
        "name",
        "hasOutput",
        "tags",
        "dependencies",
    ]
    lines = ["config {"]
    rendered = []
    for key in ordered_keys:
        if key in action:
            rendered.append(f"  {key}: {js_value(action[key])}")
    lines.append(",\n".join(rendered))
    lines.append("}")
    return "\n".join(lines)


def write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def render_source(source: dict[str, Any]) -> str:
    return (
        f"-- {GENERATED_MARKER}\n"
        f"-- Source declaration for `{source['database']}.{source['schema']}.{source['name']}`.\n\n"
        f"{render_config({**source, 'type': 'declaration'})}\n"
    )


def render_action(action: dict[str, Any]) -> str:
    sql_path = REPO_ROOT / action["sql"]
    sql = sql_path.read_text(encoding="utf-8").rstrip()
    return (
        f"-- {GENERATED_MARKER}\n"
        f"-- Canonical source: {action['sql']}\n\n"
        f"{render_config(action)}\n\n"
        f"{sql}\n"
    )


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    for source in manifest["sources"]:
        path = DATAFORM_DIR / "definitions" / "sources" / f"{source['name']}.sqlx"
        write_if_changed(path, render_source(source))

    for action in manifest["actions"]:
        path = DATAFORM_DIR / action["path"]
        write_if_changed(path, render_action(action))


if __name__ == "__main__":
    main()
