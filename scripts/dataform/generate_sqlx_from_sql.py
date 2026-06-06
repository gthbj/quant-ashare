#!/usr/bin/env python3
"""Generate Dataform SQLX actions from the canonical BigQuery SQL files."""

from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
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


def write_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def is_current(path: Path, content: str) -> bool:
    return path.exists() and path.read_text(encoding="utf-8") == content


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


def parse_args() -> Any:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write files; fail if generated SQLX files are missing or stale.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    stale_paths: list[Path] = []

    for source in manifest["sources"]:
        path = DATAFORM_DIR / "definitions" / "sources" / f"{source['name']}.sqlx"
        content = render_source(source)
        if args.check:
            if not is_current(path, content):
                stale_paths.append(path)
        else:
            write_if_changed(path, content)

    for action in manifest["actions"]:
        path = DATAFORM_DIR / action["path"]
        content = render_action(action)
        if args.check:
            if not is_current(path, content):
                stale_paths.append(path)
        else:
            write_if_changed(path, content)

    if stale_paths:
        print("Dataform generated SQLX files are stale or missing:", file=sys.stderr)
        for path in stale_paths:
            print(f"  {path.relative_to(REPO_ROOT)}", file=sys.stderr)
        print(
            "Run `python3 scripts/dataform/generate_sqlx_from_sql.py` and commit the generated files.",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
