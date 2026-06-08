"""HTTP runtime for Workflows-based ashare pipeline control."""

from __future__ import annotations

import os
from typing import Any

from flask import Flask, jsonify, request

from scripts.alerting.check_alerts import (
    PROJECT_ID as ALERT_PROJECT_ID,
    check_alerts as query_alerts,
    write_heartbeat_to_cloud_logging,
    write_to_cloud_logging,
)
from scripts.pipeline_control.state import (
    ControlConfig,
    DEFAULT_BQ_LOCATION,
    DEFAULT_LOCK_BUCKET,
    DEFAULT_LOCK_PREFIX,
    DEFAULT_PROJECT_ID,
    DEFAULT_REGION,
    PipelineStateStore,
    safe_text,
)


app = Flask(__name__)

CONFIG = ControlConfig(
    project_id=os.environ.get("GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT_ID),
    region=os.environ.get("REGION", DEFAULT_REGION),
    bq_location=os.environ.get("BQ_LOCATION", DEFAULT_BQ_LOCATION),
    lock_bucket=os.environ.get("LOCK_BUCKET", DEFAULT_LOCK_BUCKET),
    lock_prefix=os.environ.get("LOCK_PREFIX", DEFAULT_LOCK_PREFIX),
)
STATE = PipelineStateStore(CONFIG)


def _body() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    return payload


def _require(payload: dict[str, Any], key: str) -> Any:
    if key not in payload or payload[key] in (None, ""):
        raise ValueError(f"missing required field: {key}")
    return payload[key]


def _lock_key(payload: dict[str, Any]) -> str:
    raw = payload.get("lock_key", payload.get("lock_name"))
    if raw in (None, ""):
        raise ValueError("missing required field: lock_key")
    return str(raw)


def _lease_seconds(payload: dict[str, Any]) -> int:
    raw_lease_seconds = payload.get("lease_seconds")
    if raw_lease_seconds not in (None, ""):
        return max(1, int(raw_lease_seconds))
    raw_ttl_minutes = payload.get("ttl_minutes")
    if raw_ttl_minutes not in (None, ""):
        return max(1, int(raw_ttl_minutes)) * 60
    return 1800


def _lock_generation(payload: dict[str, Any], *, lock_key: str) -> int:
    raw_generation = payload.get("generation")
    if raw_generation not in (None, ""):
        return int(raw_generation)
    raw_owner = payload.get("owner")
    if raw_owner not in (None, ""):
        return STATE.lock_generation_for_owner(lock_key=lock_key, owner=str(raw_owner))
    raise ValueError("missing required field: generation")


def _truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", ""}:
            return False
    return bool(value)


@app.errorhandler(Exception)
def handle_error(exc: Exception):  # type: ignore[override]
    status_code = getattr(exc, "code", 500)
    return (
        jsonify(
            {
                "ok": False,
                "error_type": type(exc).__name__,
                "error_message": safe_text(exc, 2000),
            }
        ),
        status_code if isinstance(status_code, int) else 500,
    )


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True, "service": "ashare-pipeline-control"})


@app.post("/v1/gates/sse-is-open")
def sse_is_open():
    payload = _body()
    business_date = str(_require(payload, "business_date"))
    return jsonify({"ok": True, **STATE.is_sse_open(business_date)})


@app.post("/v1/pipeline-runs/status")
def pipeline_run_status():
    payload = _body()
    _require(payload, "pipeline_run_id")
    _require(payload, "dag_id")
    _require(payload, "status")
    STATE.upsert_pipeline_run(payload)
    return jsonify({"ok": True})


@app.post("/v1/tasks/status")
def task_status():
    payload = _body()
    _require(payload, "pipeline_run_id")
    _require(payload, "task_id")
    _require(payload, "status")
    STATE.upsert_task_status(payload)
    return jsonify({"ok": True})


@app.post("/v1/tasks/bigquery")
def task_bigquery():
    payload = _body()
    raw_context = payload.get("context")
    context = dict(raw_context) if isinstance(raw_context, dict) else dict(payload)
    task_id = str(_require(payload, "task_id"))
    sql_path = str(_require(payload, "sql_path"))
    result = STATE.run_sql_task(
        context=context,
        task_id=task_id,
        sql_path=sql_path,
        query_parameters=list(payload.get("query_parameters", [])),
        task_type=payload.get("task_type"),
        endpoint=str(payload.get("endpoint", "")),
    )
    return jsonify({"ok": True, "result": result})


@app.post("/v1/tasks/alert-check")
def task_alert_check():
    payload = _body()
    project_id = str(payload.get("project_id") or ALERT_PROJECT_ID)
    lookback_minutes = int(payload.get("lookback_minutes") or 70)
    write_log = _truthy(payload.get("write_log"), default=True)
    write_heartbeat = _truthy(payload.get("write_heartbeat"), default=True)
    alerts = query_alerts(project_id, lookback_minutes)
    written = 0
    if write_log and alerts:
        written = write_to_cloud_logging(project_id, alerts)
    if write_heartbeat:
        write_heartbeat_to_cloud_logging(
            project_id,
            alerts_count=len(alerts),
            lookback_minutes=lookback_minutes,
        )
    return jsonify(
        {
            "ok": True,
            "alerts_count": len(alerts),
            "log_entries_written": written,
            "lookback_minutes": lookback_minutes,
            "status": ("alerts_found" if alerts else "no_alerts"),
        }
    )


@app.post("/v1/locks/acquire")
def lock_acquire():
    payload = _body()
    result = STATE.acquire_lock(
        lock_key=_lock_key(payload),
        owner=str(_require(payload, "owner")),
        lease_seconds=_lease_seconds(payload),
        metadata=dict(payload.get("metadata", {})),
    )
    return jsonify({"ok": result.get("acquired", False), **result}), (200 if result.get("acquired", False) else 409)


@app.post("/v1/locks/heartbeat")
def lock_heartbeat():
    payload = _body()
    lock_key = _lock_key(payload)
    result = STATE.heartbeat_lock(
        lock_key=lock_key,
        generation=_lock_generation(payload, lock_key=lock_key),
        lease_seconds=_lease_seconds(payload),
    )
    return jsonify({"ok": True, **result})


@app.post("/v1/locks/release")
def lock_release():
    payload = _body()
    lock_key = _lock_key(payload)
    result = STATE.release_lock(
        lock_key=lock_key,
        generation=_lock_generation(payload, lock_key=lock_key),
    )
    return jsonify({"ok": True, **result})
