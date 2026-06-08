"""HTTP runtime for Workflows-based ashare pipeline control."""

from __future__ import annotations

import os
from typing import Any

from flask import Flask, jsonify, request

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
    context = dict(_require(payload, "context"))
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


@app.post("/v1/locks/acquire")
def lock_acquire():
    payload = _body()
    result = STATE.acquire_lock(
        lock_key=str(_require(payload, "lock_key")),
        owner=str(_require(payload, "owner")),
        ttl_minutes=int(payload.get("ttl_minutes", 30)),
        metadata=dict(payload.get("metadata", {})),
    )
    return jsonify({"ok": result.get("acquired", False), **result}), (200 if result.get("acquired", False) else 409)


@app.post("/v1/locks/heartbeat")
def lock_heartbeat():
    payload = _body()
    result = STATE.heartbeat_lock(
        lock_key=str(_require(payload, "lock_key")),
        generation=int(_require(payload, "generation")),
        ttl_minutes=int(payload.get("ttl_minutes", 30)),
    )
    return jsonify({"ok": True, **result})


@app.post("/v1/locks/release")
def lock_release():
    payload = _body()
    result = STATE.release_lock(
        lock_key=str(_require(payload, "lock_key")),
        generation=int(_require(payload, "generation")),
    )
    return jsonify({"ok": True, **result})

