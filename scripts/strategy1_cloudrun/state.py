"""State-table and GCS lock helpers for the Strategy 1 Cloud Run orchestrator."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import bigquery, storage

from scripts.strategy1_cloudrun import __version__
from scripts.strategy1_cloudrun.config import Experiment, RunnerConfig


STATUS_TABLE = "`data-aquarium.ashare_meta.strategy1_experiment_run_status`"
DEFAULT_LOCK_BUCKET = "ashare-artifacts"
DEFAULT_LOCK_PREFIX = "locks/strategy1/cloudrun"
DEFAULT_LOCK_TTL_MINUTES = 30
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 60

LOGGER = logging.getLogger("strategy1_cloudrun.state")


@dataclass(frozen=True)
class StepStateSpec:
    step_id: str
    display_name: str
    lock_key: str
    job_name: str
    command: list[str]


@dataclass(frozen=True)
class LockConfig:
    project: str
    region: str
    bucket: str = DEFAULT_LOCK_BUCKET
    prefix: str = DEFAULT_LOCK_PREFIX
    ttl_minutes: int = DEFAULT_LOCK_TTL_MINUTES
    dry_run: bool = False


def scheduler_instance_id() -> str:
    hostname = os.uname().nodename
    return f"cloudrun-orchestrator-{hostname}-{os.getpid()}-{int(time.time())}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def experiment_params_json(exp: Experiment, *, execution_backend: str, manifest_hash: str) -> str:
    payload = exp.to_params()
    payload["execution_backend"] = execution_backend
    payload["manifest_hash"] = manifest_hash
    payload["runner_version"] = __version__
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def build_lock_key(exp: Experiment, step_id: str) -> str:
    if step_id == "cloudrun_train_predict":
        return f"cloudrun:train:{exp.prediction_run_id}"
    if step_id == "cloudrun_backtest_report":
        return f"cloudrun:backtest:{exp.backtest_id or exp.run_id}"
    return f"cloudrun:{step_id}:{exp.run_id}"


class GcsLeaseLock:
    """GCS create-if-not-exists lock with generation-guarded heartbeat/release."""

    def __init__(self, config: LockConfig, lock_key: str, exp: Experiment, step_id: str, owner: str):
        self.config = config
        self.lock_key = lock_key
        self.exp = exp
        self.step_id = step_id
        self.owner = owner
        self.blob_name = f"{config.prefix.rstrip('/')}/{lock_key}.lock"
        self.acquired_at: datetime | None = None
        self.lease_expires_at: datetime | None = None
        self._client: storage.Client | None = None
        self._blob: storage.Blob | None = None
        self._generation: int | None = None

    def acquire(self) -> bool:
        if self.config.dry_run:
            self.acquired_at = utc_now()
            self.lease_expires_at = self.acquired_at + timedelta(minutes=self.config.ttl_minutes)
            return True
        bucket = self._bucket()
        for attempt in range(2):
            blob = bucket.blob(self.blob_name)
            now = utc_now()
            expires_at = now + timedelta(minutes=self.config.ttl_minutes)
            payload = {
                "lock_key": self.lock_key,
                "experiment_id": self.exp.experiment_id,
                "run_id": self.exp.run_id,
                "prediction_run_id": self.exp.prediction_run_id,
                "backtest_id": self.exp.backtest_id,
                "stage_id": self.exp.stage_id,
                "step_id": self.step_id,
                "lock_owner": self.owner,
                "acquired_at": now.isoformat(),
                "lease_expires_at": expires_at.isoformat(),
            }
            try:
                blob.upload_from_string(
                    json.dumps(payload, ensure_ascii=False),
                    content_type="application/json",
                    if_generation_match=0,
                )
                blob.reload()
                self._blob = blob
                self._generation = int(blob.generation)
                self.acquired_at = now
                self.lease_expires_at = expires_at
                return True
            except Exception as exc:
                if not _is_precondition_error(exc):
                    LOGGER.warning("lock acquire failed: %s: %s", self.blob_name, exc)
                    return False
                if attempt == 0 and self._reclaim_if_stale(bucket, blob):
                    continue
                return False
        return False

    def heartbeat(self) -> datetime | None:
        if self.config.dry_run:
            self.lease_expires_at = utc_now() + timedelta(minutes=self.config.ttl_minutes)
            return self.lease_expires_at
        if self._blob is None or self._generation is None:
            return None
        try:
            blob = self._blob.bucket.blob(self._blob.name)
            existing = blob.download_as_bytes(if_generation_match=self._generation)
            payload = json.loads(existing)
            lease_expires_at = utc_now() + timedelta(minutes=self.config.ttl_minutes)
            payload["last_heartbeat_at"] = utc_now().isoformat()
            payload["lease_expires_at"] = lease_expires_at.isoformat()
            blob.upload_from_string(
                json.dumps(payload, ensure_ascii=False),
                content_type="application/json",
                if_generation_match=self._generation,
            )
            blob.reload()
            self._blob = blob
            self._generation = int(blob.generation)
            self.lease_expires_at = lease_expires_at
            return lease_expires_at
        except Exception as exc:
            if _is_precondition_error(exc) or _is_not_found_error(exc):
                LOGGER.warning("lock heartbeat lost ownership: %s: %s", self.blob_name, exc)
                return None
            LOGGER.warning("lock heartbeat failed: %s: %s", self.blob_name, exc)
            return self.lease_expires_at

    def record_execution(self, *, execution_id: str, job_name: str) -> bool:
        if self.config.dry_run:
            return True
        if self._blob is None or self._generation is None:
            return False
        try:
            blob = self._blob.bucket.blob(self._blob.name)
            existing = blob.download_as_bytes(if_generation_match=self._generation)
            payload = json.loads(existing)
            payload["cloud_run_job_name"] = job_name
            payload["cloud_run_execution_id"] = execution_id
            payload["job_id"] = execution_id
            payload["execution_recorded_at"] = utc_now().isoformat()
            blob.upload_from_string(
                json.dumps(payload, ensure_ascii=False),
                content_type="application/json",
                if_generation_match=self._generation,
            )
            blob.reload()
            self._blob = blob
            self._generation = int(blob.generation)
            return True
        except Exception as exc:
            LOGGER.warning("lock execution record failed: %s: %s", self.blob_name, exc)
            return False

    def release(self) -> None:
        if self.config.dry_run or self._blob is None:
            return
        try:
            if self._generation is None:
                self._blob.delete()
            else:
                self._blob.delete(if_generation_match=self._generation)
        except Exception as exc:
            LOGGER.warning("lock release failed: %s: %s", self.blob_name, exc)

    def _reclaim_if_stale(self, bucket: storage.Bucket, blob: storage.Blob) -> bool:
        try:
            blob.reload()
            generation = int(blob.generation)
            payload = json.loads(blob.download_as_bytes(if_generation_match=generation))
            expires_raw = payload.get("lease_expires_at")
            if not expires_raw:
                return False
            expires_at = datetime.fromisoformat(expires_raw)
            if utc_now() <= expires_at:
                return False
            execution_id = payload.get("cloud_run_execution_id") or payload.get("job_id")
            if execution_id and not is_cloud_run_execution_terminal(self.config.project, self.config.region, execution_id):
                LOGGER.warning("stale lock not reclaimed because execution is not terminal: %s", execution_id)
                return False
            blob.delete(if_generation_match=generation)
            return True
        except Exception as exc:
            LOGGER.warning("stale lock reclaim failed: %s: %s", self.blob_name, exc)
            return False

    def _bucket(self) -> storage.Bucket:
        if self._client is None:
            self._client = storage.Client(project=self.config.project)
        return self._client.bucket(self.config.bucket)


class OrchestratorStatusTable:
    """BigQuery status table writer used for Cloud Run orchestration audit/resume."""

    def __init__(self, project: str, location: str, *, dry_run: bool = False):
        self.project = project
        self.location = location
        self.dry_run = dry_run
        self._client: bigquery.Client | None = None

    def get_status(self, exp: Experiment, step_id: str) -> str | None:
        if self.dry_run:
            return None
        sql = f"""
        SELECT status
        FROM {STATUS_TABLE}
        WHERE experiment_id = @experiment_id
          AND run_id = @run_id
          AND step_id = @step_id
        ORDER BY updated_at DESC
        LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("experiment_id", "STRING", exp.experiment_id),
                bigquery.ScalarQueryParameter("run_id", "STRING", exp.run_id),
                bigquery.ScalarQueryParameter("step_id", "STRING", step_id),
            ]
        )
        rows = list(self._bq().query(sql, job_config=job_config).result())
        return rows[0]["status"] if rows else None

    def upsert(
        self,
        exp: Experiment,
        step: StepStateSpec,
        *,
        status: str,
        scheduler_id: str,
        manifest_path: str,
        manifest_hash: str,
        params_json: str,
        force_replace: bool,
        lock: GcsLeaseLock | None = None,
        job_id: str | None = None,
        error_message: str | None = None,
        log_dir: str | None = None,
    ) -> None:
        if self.dry_run:
            return
        now = utc_now()
        started_at = now if status == "running" else None
        finished_at = now if status in {"succeeded", "failed", "cancelled"} else None
        lock_acquired_at = lock.acquired_at if lock and status == "running" else None
        lock_expires_at = lock.lease_expires_at if lock and status == "running" else None
        last_heartbeat_at = now if lock and status == "running" else None
        sql = f"""
        MERGE {STATUS_TABLE} AS T
        USING (
          SELECT @experiment_id AS experiment_id, @run_id AS run_id, @step_id AS step_id
        ) AS S
        ON T.experiment_id = S.experiment_id AND T.run_id = S.run_id AND T.step_id = S.step_id
        WHEN MATCHED THEN UPDATE SET
          prediction_run_id = @prediction_run_id,
          backtest_id = @backtest_id,
          stage_id = @stage_id,
          experiment_group = @experiment_group,
          experiment_type = @experiment_type,
          step_display_name = @step_display_name,
          status = @status,
          status_reason = @status_reason,
          started_at = IF(@status = 'running', @started_at, T.started_at),
          finished_at = @finished_at,
          updated_at = @updated_at,
          job_id = IFNULL(@job_id, T.job_id),
          attempt = CASE
            WHEN @status = 'running' AND T.status != 'running' THEN IFNULL(T.attempt, 0) + 1
            ELSE T.attempt
          END,
          force_replace = @force_replace,
          lock_key = IFNULL(@lock_key, T.lock_key),
          lock_owner = IFNULL(@lock_owner, T.lock_owner),
          lock_acquired_at = IF(@status = 'running', @lock_acquired_at, T.lock_acquired_at),
          lock_expires_at = IF(@status = 'running', @lock_expires_at, T.lock_expires_at),
          last_heartbeat_at = IF(@status = 'running', @last_heartbeat_at, T.last_heartbeat_at),
          manifest_path = @manifest_path,
          manifest_hash = @manifest_hash,
          params_json = @params_json,
          runner_version = @runner_version,
          scheduler_instance_id = @scheduler_instance_id,
          log_dir = IFNULL(@log_dir, T.log_dir),
          error_message = @error_message
        WHEN NOT MATCHED THEN INSERT (
          experiment_id, run_id, prediction_run_id, backtest_id, stage_id,
          experiment_group, experiment_type, step_id, step_display_name,
          status, status_reason, started_at, finished_at, created_at, updated_at,
          job_id, attempt, force_replace, lock_key, lock_owner,
          lock_acquired_at, lock_expires_at, last_heartbeat_at,
          artifact_uri, report_uri, diagnosis_uri, diagnosis_status, qa_status,
          manifest_path, manifest_hash, params_json, runner_version,
          scheduler_instance_id, log_dir, error_message
        ) VALUES (
          @experiment_id, @run_id, @prediction_run_id, @backtest_id, @stage_id,
          @experiment_group, @experiment_type, @step_id, @step_display_name,
          @status, @status_reason, @started_at, @finished_at, @created_at, @updated_at,
          @job_id, @attempt, @force_replace, @lock_key, @lock_owner,
          @lock_acquired_at, @lock_expires_at, @last_heartbeat_at,
          @artifact_uri, @report_uri, @diagnosis_uri, @diagnosis_status, @qa_status,
          @manifest_path, @manifest_hash, @params_json, @runner_version,
          @scheduler_instance_id, @log_dir, @error_message
        )
        """
        params = [
            bigquery.ScalarQueryParameter("experiment_id", "STRING", exp.experiment_id),
            bigquery.ScalarQueryParameter("run_id", "STRING", exp.run_id),
            bigquery.ScalarQueryParameter("prediction_run_id", "STRING", exp.prediction_run_id),
            bigquery.ScalarQueryParameter("backtest_id", "STRING", exp.backtest_id),
            bigquery.ScalarQueryParameter("stage_id", "STRING", exp.stage_id),
            bigquery.ScalarQueryParameter("experiment_group", "STRING", exp.experiment_group),
            bigquery.ScalarQueryParameter("experiment_type", "STRING", exp.experiment_type),
            bigquery.ScalarQueryParameter("step_id", "STRING", step.step_id),
            bigquery.ScalarQueryParameter("step_display_name", "STRING", step.display_name),
            bigquery.ScalarQueryParameter("status", "STRING", status),
            bigquery.ScalarQueryParameter("status_reason", "STRING", error_message or ""),
            bigquery.ScalarQueryParameter("started_at", "TIMESTAMP", started_at),
            bigquery.ScalarQueryParameter("finished_at", "TIMESTAMP", finished_at),
            bigquery.ScalarQueryParameter("created_at", "TIMESTAMP", now),
            bigquery.ScalarQueryParameter("updated_at", "TIMESTAMP", now),
            bigquery.ScalarQueryParameter("job_id", "STRING", job_id),
            bigquery.ScalarQueryParameter("attempt", "INT64", 1),
            bigquery.ScalarQueryParameter("force_replace", "BOOL", force_replace),
            bigquery.ScalarQueryParameter("lock_key", "STRING", step.lock_key),
            bigquery.ScalarQueryParameter("lock_owner", "STRING", scheduler_id),
            bigquery.ScalarQueryParameter("lock_acquired_at", "TIMESTAMP", lock_acquired_at),
            bigquery.ScalarQueryParameter("lock_expires_at", "TIMESTAMP", lock_expires_at),
            bigquery.ScalarQueryParameter("last_heartbeat_at", "TIMESTAMP", last_heartbeat_at),
            bigquery.ScalarQueryParameter("artifact_uri", "STRING", ""),
            bigquery.ScalarQueryParameter("report_uri", "STRING", ""),
            bigquery.ScalarQueryParameter("diagnosis_uri", "STRING", ""),
            bigquery.ScalarQueryParameter("diagnosis_status", "STRING", ""),
            bigquery.ScalarQueryParameter("qa_status", "STRING", ""),
            bigquery.ScalarQueryParameter("manifest_path", "STRING", manifest_path),
            bigquery.ScalarQueryParameter("manifest_hash", "STRING", manifest_hash),
            bigquery.ScalarQueryParameter("params_json", "STRING", params_json),
            bigquery.ScalarQueryParameter("runner_version", "STRING", __version__),
            bigquery.ScalarQueryParameter("scheduler_instance_id", "STRING", scheduler_id),
            bigquery.ScalarQueryParameter("log_dir", "STRING", log_dir),
            bigquery.ScalarQueryParameter("error_message", "STRING", error_message or ""),
        ]
        self._bq().query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()

    def _bq(self) -> bigquery.Client:
        if self._client is None:
            self._client = bigquery.Client(project=self.project, location=self.location)
        return self._client


def extract_cloud_run_execution_id(stdout: str, stderr: str) -> str | None:
    for text in (stdout, stderr):
        if not text.strip():
            continue
        try:
            payload = json.loads(text)
            found = _find_execution_id(payload)
            if found:
                return found
        except Exception:
            pass
        match = re.search(r"/executions/([A-Za-z0-9_.-]+)", text)
        if match:
            return match.group(1)
        match = re.search(r"Execution\s+\[([^\]]+)\]", text)
        if match:
            return match.group(1)
    return None


def describe_cloud_run_execution(project: str, region: str, execution_id: str) -> dict[str, Any] | None:
    proc = subprocess.run(
        [
            "gcloud", "run", "jobs", "executions", "describe", execution_id,
            f"--project={project}",
            f"--region={region}",
            "--format=json",
        ],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        LOGGER.warning("Cloud Run execution describe failed: %s: %s", execution_id, proc.stderr[-1000:])
        return None
    try:
        return json.loads(proc.stdout)
    except Exception as exc:
        LOGGER.warning("Cloud Run execution describe JSON parse failed: %s: %s", execution_id, exc)
        return None


def cancel_cloud_run_execution(project: str, region: str, execution_id: str) -> None:
    proc = subprocess.run(
        [
            "gcloud", "run", "jobs", "executions", "cancel", execution_id,
            f"--project={project}",
            f"--region={region}",
            "--quiet",
        ],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        LOGGER.warning("Cloud Run execution cancel failed: %s: %s", execution_id, proc.stderr[-1000:])


def cloud_run_execution_state(payload: dict[str, Any] | None) -> str:
    if not payload:
        return "unknown"
    status = payload.get("status") or {}
    conditions = status.get("conditions") or []
    for condition in conditions:
        condition_type = str(condition.get("type") or "").lower()
        if condition_type not in {"completed", "complete", "succeeded"}:
            continue
        value = str(condition.get("state") or condition.get("status") or "").lower()
        reason = str(condition.get("reason") or "").lower()
        if value in {"true", "condition_succeeded", "succeeded"}:
            return "succeeded"
        if value in {"false", "condition_failed", "failed"}:
            if "cancel" in reason:
                return "cancelled"
            return "failed"
    if status.get("completionTime") or status.get("completion_time"):
        if _int_value(status.get("cancelledCount") or status.get("cancelled_count")) > 0:
            return "cancelled"
        if _int_value(status.get("failedCount") or status.get("failed_count")) > 0:
            return "failed"
        return "succeeded"
    return "running"


def is_cloud_run_execution_terminal(project: str, region: str, execution_id: str) -> bool:
    state = cloud_run_execution_state(describe_cloud_run_execution(project, region, execution_id))
    return state in {"succeeded", "failed", "cancelled"}


def _find_execution_id(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("name", "execution", "latestCreatedExecution"):
            raw = value.get(key)
            if isinstance(raw, str):
                if "/executions/" in raw:
                    return raw.rsplit("/executions/", 1)[-1]
                if key == "name":
                    return raw.rsplit("/", 1)[-1]
                if "execution" in key.lower():
                    return raw.rsplit("/", 1)[-1]
        for nested in value.values():
            found = _find_execution_id(nested)
            if found:
                return found
    if isinstance(value, list):
        for nested in value:
            found = _find_execution_id(nested)
            if found:
                return found
    return None


def _is_precondition_error(exc: Exception) -> bool:
    text = str(exc)
    return any(token in text for token in ("conditionNotMet", "PreconditionFailed", "GenerationDoesNotMatch", "412"))


def _is_not_found_error(exc: Exception) -> bool:
    text = str(exc)
    return any(token in text for token in ("NotFound", "404", "No such object"))


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0
