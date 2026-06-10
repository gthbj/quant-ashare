"""Scoped linter for retired Strategy 1 references."""

from __future__ import annotations

import argparse
import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from quant_ashare.strategy1.catalog import REPO_ROOT, load_step_catalog


@dataclass(frozen=True)
class RetiredReferenceViolation:
    path: str
    ref: str
    line_no: int
    line: str


def lint_retired_references(catalog: dict[str, Any] | None = None) -> list[RetiredReferenceViolation]:
    catalog = catalog or load_step_catalog()
    lint_cfg = catalog.get("retired_reference_lint") or {}
    active_scopes = lint_cfg.get("active_scopes") or []
    historical_scopes = lint_cfg.get("historical_allowed_scopes") or []
    required_markers = [str(marker).lower() for marker in lint_cfg.get("required_marker_for_historical_refs") or []]
    banned_refs = lint_cfg.get("banned_active_refs") or []
    violations: list[RetiredReferenceViolation] = []
    for path in iter_scope_files(active_scopes, historical_scopes):
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        is_historical = matches_any(rel, historical_scopes)
        has_marker = any(marker in text.lower() for marker in required_markers)
        for ref in banned_refs:
            for line_no, line in matching_lines(text, ref):
                if is_historical and has_marker:
                    continue
                violations.append(RetiredReferenceViolation(rel, ref, line_no, line.strip()))
    violations.extend(lint_catalog_callers(catalog, banned_refs))
    return violations


def iter_scope_files(active_scopes: Iterable[str], historical_scopes: Iterable[str]) -> Iterable[Path]:
    seen: set[Path] = set()
    for pattern in [*active_scopes, *historical_scopes]:
        for path in REPO_ROOT.glob(file_glob_pattern(pattern)):
            if path.is_dir():
                continue
            if path in seen or ".git" in path.parts:
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel == "configs/strategy1/active_step_catalog.yml":
                continue
            seen.add(path)
            yield path


def file_glob_pattern(pattern: str) -> str:
    if pattern == "**":
        return "**/*"
    if pattern.endswith("/**"):
        return f"{pattern}/*"
    return pattern


def matching_lines(text: str, ref: str) -> Iterable[tuple[int, str]]:
    for line_no, line in enumerate(text.splitlines(), start=1):
        if ref in line:
            yield line_no, line


def lint_catalog_callers(catalog: dict[str, Any], banned_refs: Iterable[str]) -> list[RetiredReferenceViolation]:
    catalog_text = (REPO_ROOT / "configs/strategy1/active_step_catalog.yml").read_text(encoding="utf-8")
    violations: list[RetiredReferenceViolation] = []
    for step_name, cfg in (catalog.get("steps") or {}).items():
        if cfg.get("status") == "retired":
            continue
        for caller in cfg.get("caller") or []:
            for ref in banned_refs:
                if ref not in str(caller):
                    continue
                line_no = next(
                    (line_no for line_no, line in matching_lines(catalog_text, str(caller))),
                    0,
                )
                violations.append(
                    RetiredReferenceViolation(
                        "configs/strategy1/active_step_catalog.yml",
                        ref,
                        line_no,
                        f"{step_name}.caller: {caller}",
                    )
                )
    return violations


def matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint active scopes for retired Strategy1 references")
    parser.add_argument("--catalog", default=None)
    args = parser.parse_args()
    catalog = load_step_catalog(args.catalog)
    violations = lint_retired_references(catalog)
    if violations:
        for violation in violations:
            print(f"{violation.path}:{violation.line_no}: retired ref {violation.ref}: {violation.line}")
        return 1
    print("No retired Strategy1 active-scope references found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
