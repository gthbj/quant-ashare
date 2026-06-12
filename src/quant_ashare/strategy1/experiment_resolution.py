"""Shared Strategy 1 experiment resolution helpers."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from .config import (
    Experiment,
    experiment_from_b64,
    filter_experiments,
    load_manifest,
)


def resolve_experiment_from_args(
    args: Any,
    *,
    step_name: str,
    require_retrain: bool,
    support_resolved_manifest: bool = False,
    resolved_manifest_error: str | None = None,
    fallback_not_found_in_manifest: bool = True,
    run_id_updates_prediction: bool = False,
    cli_override_attrs: tuple[str, ...] = (),
) -> Experiment:
    """Resolve one executable experiment from common Strategy 1 CLI args."""
    if getattr(args, "experiment_json", None):
        exp = experiment_from_b64(args.experiment_json)
        _validate_experiment(exp, step_name=step_name, require_retrain=require_retrain)
        return exp

    if getattr(args, "manifest_resolved", None) and not support_resolved_manifest:
        if resolved_manifest_error:
            raise ValueError(resolved_manifest_error)
        raise ValueError(f"{step_name} does not support --manifest-resolved")

    if getattr(args, "manifest_resolved", None):
        exp = _resolve_from_resolved_manifest(args)
        if exp is not None:
            return exp

    exp = _resolve_from_manifest(args, not_found_in_manifest=fallback_not_found_in_manifest)
    replacements: dict[str, object] = {}
    if run_id_updates_prediction:
        run_id = getattr(args, "run_id", None)
        if run_id and run_id != exp.run_id:
            replacements["run_id"] = run_id
            replacements["prediction_run_id"] = run_id
    for attr in cli_override_attrs:
        value = getattr(args, attr)
        if value:
            replacements[attr] = value
    if replacements:
        exp = dataclasses.replace(exp, **replacements)
    _validate_experiment(exp, step_name=step_name, require_retrain=require_retrain)
    return exp


def _resolve_from_resolved_manifest(args: Any) -> Experiment | None:
    resolved = json.loads(Path(args.manifest_resolved).read_text(encoding="utf-8"))
    matches = [item for item in resolved.get("experiments", []) if item.get("experiment_id") == args.experiment_id]
    if not matches:
        raise ValueError(f"experiment_id {args.experiment_id} not found in resolved manifest")
    raw = matches[0]
    _, base_experiments = load_manifest(args.manifest)
    by_id = {exp.experiment_id: exp for exp in base_experiments}
    if args.experiment_id in by_id:
        exp = by_id[args.experiment_id]
        return dataclasses.replace(exp, **{key: raw[key] for key in raw if hasattr(exp, key)})
    return None


def _resolve_from_manifest(args: Any, *, not_found_in_manifest: bool) -> Experiment:
    _, experiments = load_manifest(args.manifest)
    matches = filter_experiments(experiments, experiment_id=args.experiment_id, include_blocked=True)
    if matches:
        return matches[0]
    suffix = f" in {args.manifest}" if not_found_in_manifest else ""
    raise ValueError(f"experiment_id {args.experiment_id} not found{suffix}")


def _validate_experiment(exp: Experiment, *, step_name: str, require_retrain: bool) -> None:
    if require_retrain and not exp.requires_retrain:
        raise ValueError(f"{exp.experiment_id} is portfolio-only and does not require {step_name}")
    if not exp.is_executable:
        raise ValueError(f"{exp.experiment_id} contains unresolved placeholders or blocked status")
