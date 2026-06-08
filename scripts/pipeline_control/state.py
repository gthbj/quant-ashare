"""Shared runtime helpers for Workflows-based pipeline orchestration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from google.cloud import bigquery, storage
from google.cloud.exceptions import NotFound, PreconditionFailed


DEFAULT_PROJECT_ID = "data-aquarium"
DEFAULT_REGION = "asia-east2"
DEFAULT_BQ_LOCATION = "asia-east2"
DEFAULT_LOCK_BUCKET = "ashare-artifacts"
DEFAULT_LOCK_PREFIX = "locks/pipeline/orchestration"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def safe_text(value: Any, max_length: int = 1000) -> str:
    if value is None:
        return ""
    return str(value).replace("\x00", "")[:max_length]


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def workflow_console_url(project_id: str, region: str, workflow_id: str, workflow_execution_id: str) -> str:
    if not workflow_id or not workflow_execution_id:
        return ""
    return (
        "https://console.cloud.google.com/workflows/workflow/"
        f"{region}/{workflow_id}/executions/{workflow_execution_id}?project={project_id}"
    )


def bigquery_job_url(project_id: str, location: str, job_id: str) -> str:
    if not job_id:
        return ""
    return (
        "https://console.cloud.google.com/bigquery"
        f"?project={project_id}&j=bq:{location}:{job_id}&page=queryresults"
    )


def _cloud_run_execution_short_id(execution_name: str) -> str:
    if not execution_name:
        return ""
    if "/executions/" in execution_name:
        return execution_name.rsplit("/executions/", 1)[-1].split("/", 1)[0]
    if "/executions/" not in execution_name and "/" in execution_name:
        return execution_name.rsplit("/", 1)[-1]
    return execution_name


def cloud_run_execution_url(project_id: str, region: str, execution_name: str) -> str:
    execution_id = _cloud_run_execution_short_id(execution_name)
    if not execution_id:
        return ""
    return (
        "https://console.cloud.google.com/run/jobs/executions/details/"
        f"{region}/{execution_id}?project={project_id}"
    )


def _candidate_sql_roots() -> list[Path]:
    here = Path(__file__).resolve()
    roots = [Path("/app"), here.parents[2], Path.cwd()]
    seen: set[Path] = set()
    unique: list[Path] = []
    for root in roots:
        if root not in seen:
            unique.append(root)
            seen.add(root)
    return unique


def read_bundled_sql(relative_path: str) -> str:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"invalid sql_path: {relative_path}")
    for root in _candidate_sql_roots():
        candidate = root / path
        if candidate.exists():
            return candidate.read_text()
    raise FileNotFoundError(f"bundled SQL file not found: {relative_path}")


def _scalar_query_parameter(spec: dict[str, Any]) -> bigquery.ScalarQueryParameter:
    name = str(spec["name"])
    param_type = str(spec.get("type", "STRING")).upper()
    value = spec.get("value")
    if value == "" and param_type in {"STRING", "DATE", "TIMESTAMP"}:
        value = None
    if param_type == "BOOL":
        value = truthy(value)
    elif param_type == "INT64" and value is not None:
        value = int(value)
    elif param_type == "FLOAT64" and value is not None:
        value = float(value)
    return bigquery.ScalarQueryParameter(name, param_type, value)


def _task_type(task_id: str, explicit_type: str | None = None) -> str:
    if explicit_type:
        return explicit_type
    if task_id.startswith("ingestion."):
        return "ingestion"
    if task_id.startswith(("dim.", "dwd.", "dws.", "windowed_dim.", "windowed_transform.")):
        return "transform"
    if task_id.startswith(("metadata.", "windowed_metadata.")):
        return "metadata"
    if (
        task_id.startswith("qa.")
        or task_id.startswith("qa_only.")
        or task_id.endswith("_checks")
        or task_id.endswith("_readiness")
    ):
        return "qa"
    return "orchestration"


@dataclass(frozen=True)
class ControlConfig:
    project_id: str = DEFAULT_PROJECT_ID
    region: str = DEFAULT_REGION
    bq_location: str = DEFAULT_BQ_LOCATION
    lock_bucket: str = DEFAULT_LOCK_BUCKET
    lock_prefix: str = DEFAULT_LOCK_PREFIX


class PipelineStateStore:
    def __init__(self, config: ControlConfig):
        self.config = config
        self._bq_client: bigquery.Client | None = None
        self._storage_client: storage.Client | None = None

    def _bq(self) -> bigquery.Client:
        if self._bq_client is None:
            self._bq_client = bigquery.Client(
                project=self.config.project_id,
                location=self.config.bq_location,
            )
        return self._bq_client

    def _storage(self) -> storage.Client:
        if self._storage_client is None:
            self._storage_client = storage.Client(project=self.config.project_id)
        return self._storage_client

    def is_sse_open(self, business_date: str) -> dict[str, Any]:
        query = """
SELECT
  COUNT(1) AS calendar_rows,
  COUNTIF(is_open IS NULL) AS null_is_open_rows,
  COALESCE(LOGICAL_OR(is_open = 1), FALSE) AS is_open
FROM `data-aquarium.ashare_dim.dim_trade_calendar`
WHERE exchange = 'SSE'
  AND cal_date = SAFE_CAST(@business_date AS DATE)
"""
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("business_date", "STRING", business_date),
            ]
        )
        row = next(iter(self._bq().query(query, job_config=job_config).result()), None)
        if row is None or row.calendar_rows == 0:
            raise RuntimeError(f"SSE trade calendar has no row for business_date={business_date}")
        if row.null_is_open_rows:
            raise RuntimeError(f"SSE trade calendar has NULL is_open for business_date={business_date}")
        return {
            "business_date": business_date,
            "is_open": bool(row.is_open),
            "calendar_rows": int(row.calendar_rows),
        }

    def upsert_pipeline_run(self, payload: dict[str, Any]) -> None:
        query = """
MERGE `data-aquarium.ashare_meta.pipeline_run` AS T
USING (
  SELECT
    @pipeline_run_id AS pipeline_run_id,
    @dag_id AS dag_id,
    @business_date AS business_date,
    NULLIF(@date_from, '') AS date_from,
    NULLIF(@date_to, '') AS date_to,
    @run_label AS run_label,
    @warehouse_mode AS warehouse_mode,
    @transform_backend AS transform_backend,
    NULLIF(@upstream_pipeline_run_id, '') AS upstream_pipeline_run_id,
    NULLIF(@triggered_by_dag_id, '') AS triggered_by_dag_id,
    @status AS status,
    NULLIF(@error_summary, '') AS error_summary
) AS S
ON T.pipeline_run_id = S.pipeline_run_id
WHEN MATCHED THEN UPDATE SET
  dag_id = S.dag_id,
  business_date = S.business_date,
  date_from = S.date_from,
  date_to = S.date_to,
  run_label = S.run_label,
  warehouse_mode = S.warehouse_mode,
  transform_backend = S.transform_backend,
  upstream_pipeline_run_id = S.upstream_pipeline_run_id,
  triggered_by_dag_id = S.triggered_by_dag_id,
  status = S.status,
  error_summary = S.error_summary,
  finished_at = IF(S.status = 'running', T.finished_at, CURRENT_TIMESTAMP()),
  updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
  pipeline_run_id,
  dag_id,
  business_date,
  date_from,
  date_to,
  run_label,
  warehouse_mode,
  transform_backend,
  upstream_pipeline_run_id,
  triggered_by_dag_id,
  status,
  started_at,
  finished_at,
  error_summary,
  created_at,
  updated_at
) VALUES (
  S.pipeline_run_id,
  S.dag_id,
  S.business_date,
  S.date_from,
  S.date_to,
  S.run_label,
  S.warehouse_mode,
  S.transform_backend,
  S.upstream_pipeline_run_id,
  S.triggered_by_dag_id,
  S.status,
  CURRENT_TIMESTAMP(),
  IF(S.status = 'running', NULL, CURRENT_TIMESTAMP()),
  S.error_summary,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP()
);
"""
        parameters = [
            bigquery.ScalarQueryParameter("pipeline_run_id", "STRING", payload["pipeline_run_id"]),
            bigquery.ScalarQueryParameter("dag_id", "STRING", payload["dag_id"]),
            bigquery.ScalarQueryParameter("business_date", "STRING", payload.get("business_date", "")),
            bigquery.ScalarQueryParameter("date_from", "STRING", payload.get("date_from", "")),
            bigquery.ScalarQueryParameter("date_to", "STRING", payload.get("date_to", "")),
            bigquery.ScalarQueryParameter("run_label", "STRING", payload.get("run_label", "")),
            bigquery.ScalarQueryParameter("warehouse_mode", "STRING", payload.get("warehouse_mode", "")),
            bigquery.ScalarQueryParameter("transform_backend", "STRING", payload.get("transform_backend", "bq_sql")),
            bigquery.ScalarQueryParameter(
                "upstream_pipeline_run_id",
                "STRING",
                payload.get("upstream_pipeline_run_id", ""),
            ),
            bigquery.ScalarQueryParameter(
                "triggered_by_dag_id",
                "STRING",
                payload.get("triggered_by_dag_id", ""),
            ),
            bigquery.ScalarQueryParameter("status", "STRING", payload["status"]),
            bigquery.ScalarQueryParameter("error_summary", "STRING", safe_text(payload.get("error_summary", ""), 1000)),
        ]
        self._bq().query(query, job_config=bigquery.QueryJobConfig(query_parameters=parameters)).result()

    def upsert_task_status(self, payload: dict[str, Any]) -> None:
        status = str(payload["status"])
        started_at = payload.get("started_at")
        finished_at = payload.get("finished_at")
        if status == "running" and not started_at:
            started_at = utc_now().isoformat()
        if status in {"success", "failed", "skipped", "warning"} and not finished_at:
            finished_at = utc_now().isoformat()

        workflow_log_url = safe_text(
            payload.get("airflow_log_url")
            or payload.get("orchestration_log_url")
            or workflow_console_url(
                self.config.project_id,
                self.config.region,
                str(payload.get("workflow_id", "")),
                str(payload.get("workflow_execution_id", "")),
            ),
            1000,
        )
        job_id = safe_text(payload.get("bigquery_job_id", ""), 256)
        execution_name = safe_text(payload.get("cloud_run_execution_id", ""), 500)
        execution_id = _cloud_run_execution_short_id(execution_name)

        query = """
MERGE `data-aquarium.ashare_meta.pipeline_task_status` AS T
USING (
  SELECT
    @pipeline_run_id AS pipeline_run_id,
    @task_id AS task_id,
    @task_type AS task_type,
    @business_date AS business_date,
    NULLIF(@date_from, '') AS date_from,
    NULLIF(@date_to, '') AS date_to,
    @run_label AS run_label,
    @warehouse_mode AS warehouse_mode,
    @transform_backend AS transform_backend,
    @endpoint AS endpoint,
    @bigquery_job_id AS bigquery_job_id,
    @dataform_invocation_id AS dataform_invocation_id,
    @cloud_run_execution_id AS cloud_run_execution_id,
    @airflow_log_url AS airflow_log_url,
    @bigquery_job_url AS bigquery_job_url,
    @cloud_run_execution_url AS cloud_run_execution_url,
    @status AS status,
    @row_count AS row_count,
    @error_summary AS error_summary,
    SAFE_CAST(NULLIF(@started_at, '') AS TIMESTAMP) AS started_at,
    SAFE_CAST(NULLIF(@finished_at, '') AS TIMESTAMP) AS finished_at
) AS S
ON T.pipeline_run_id = S.pipeline_run_id AND T.task_id = S.task_id
WHEN MATCHED THEN UPDATE SET
  task_type = S.task_type,
  business_date = S.business_date,
  date_from = S.date_from,
  date_to = S.date_to,
  run_label = S.run_label,
  warehouse_mode = S.warehouse_mode,
  transform_backend = S.transform_backend,
  endpoint = S.endpoint,
  bigquery_job_id = S.bigquery_job_id,
  dataform_invocation_id = S.dataform_invocation_id,
  cloud_run_execution_id = S.cloud_run_execution_id,
  airflow_log_url = S.airflow_log_url,
  bigquery_job_url = S.bigquery_job_url,
  cloud_run_execution_url = S.cloud_run_execution_url,
  status = S.status,
  row_count = S.row_count,
  error_summary = S.error_summary,
  started_at = COALESCE(S.started_at, T.started_at),
  finished_at = S.finished_at,
  updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
  pipeline_run_id,
  task_id,
  task_type,
  business_date,
  date_from,
  date_to,
  run_label,
  warehouse_mode,
  transform_backend,
  endpoint,
  bigquery_job_id,
  dataform_invocation_id,
  cloud_run_execution_id,
  airflow_log_url,
  bigquery_job_url,
  cloud_run_execution_url,
  status,
  row_count,
  error_summary,
  started_at,
  finished_at,
  created_at,
  updated_at
) VALUES (
  S.pipeline_run_id,
  S.task_id,
  S.task_type,
  S.business_date,
  S.date_from,
  S.date_to,
  S.run_label,
  S.warehouse_mode,
  S.transform_backend,
  S.endpoint,
  S.bigquery_job_id,
  S.dataform_invocation_id,
  S.cloud_run_execution_id,
  S.airflow_log_url,
  S.bigquery_job_url,
  S.cloud_run_execution_url,
  S.status,
  S.row_count,
  S.error_summary,
  S.started_at,
  S.finished_at,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP()
);
"""
        parameters = [
            bigquery.ScalarQueryParameter("pipeline_run_id", "STRING", payload["pipeline_run_id"]),
            bigquery.ScalarQueryParameter("task_id", "STRING", payload["task_id"]),
            bigquery.ScalarQueryParameter(
                "task_type",
                "STRING",
                _task_type(str(payload["task_id"]), payload.get("task_type")),
            ),
            bigquery.ScalarQueryParameter("business_date", "STRING", payload.get("business_date", "")),
            bigquery.ScalarQueryParameter("date_from", "STRING", payload.get("date_from", "")),
            bigquery.ScalarQueryParameter("date_to", "STRING", payload.get("date_to", "")),
            bigquery.ScalarQueryParameter("run_label", "STRING", payload.get("run_label", "")),
            bigquery.ScalarQueryParameter("warehouse_mode", "STRING", payload.get("warehouse_mode", "")),
            bigquery.ScalarQueryParameter("transform_backend", "STRING", payload.get("transform_backend", "bq_sql")),
            bigquery.ScalarQueryParameter("endpoint", "STRING", payload.get("endpoint", "")),
            bigquery.ScalarQueryParameter("bigquery_job_id", "STRING", job_id),
            bigquery.ScalarQueryParameter(
                "dataform_invocation_id",
                "STRING",
                safe_text(payload.get("dataform_invocation_id", ""), 256),
            ),
            bigquery.ScalarQueryParameter("cloud_run_execution_id", "STRING", execution_id),
            bigquery.ScalarQueryParameter("airflow_log_url", "STRING", workflow_log_url),
            bigquery.ScalarQueryParameter(
                "bigquery_job_url",
                "STRING",
                safe_text(payload.get("bigquery_job_url") or bigquery_job_url(self.config.project_id, self.config.bq_location, job_id), 1000),
            ),
            bigquery.ScalarQueryParameter(
                "cloud_run_execution_url",
                "STRING",
                safe_text(payload.get("cloud_run_execution_url") or cloud_run_execution_url(self.config.project_id, self.config.region, execution_name), 1000),
            ),
            bigquery.ScalarQueryParameter("status", "STRING", status),
            bigquery.ScalarQueryParameter("row_count", "INT64", payload.get("row_count")),
            bigquery.ScalarQueryParameter("error_summary", "STRING", safe_text(payload.get("error_summary", ""), 1000)),
            bigquery.ScalarQueryParameter("started_at", "STRING", safe_text(started_at, 64)),
            bigquery.ScalarQueryParameter("finished_at", "STRING", safe_text(finished_at, 64)),
        ]
        self._bq().query(query, job_config=bigquery.QueryJobConfig(query_parameters=parameters)).result()

    def run_sql_task(
        self,
        *,
        context: dict[str, Any],
        task_id: str,
        sql_path: str,
        query_parameters: list[dict[str, Any]] | None = None,
        task_type: str | None = None,
        endpoint: str = "",
    ) -> dict[str, Any]:
        started_at = utc_now().isoformat()
        self.upsert_task_status(
            {
                **context,
                "task_id": task_id,
                "task_type": task_type,
                "endpoint": endpoint,
                "status": "running",
                "started_at": started_at,
            }
        )
        try:
            query = read_bundled_sql(sql_path)
            job_config = bigquery.QueryJobConfig(
                query_parameters=[_scalar_query_parameter(spec) for spec in (query_parameters or [])]
            )
            job = self._bq().query(query, job_config=job_config)
            job.result()
            finished_at = utc_now().isoformat()
            self.upsert_task_status(
                {
                    **context,
                    "task_id": task_id,
                    "task_type": task_type,
                    "endpoint": endpoint,
                    "status": "success",
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "bigquery_job_id": job.job_id,
                }
            )
            return {
                "job_id": job.job_id,
                "job_url": bigquery_job_url(self.config.project_id, self.config.bq_location, job.job_id),
                "started_at": started_at,
                "finished_at": finished_at,
            }
        except Exception as exc:
            self.upsert_task_status(
                {
                    **context,
                    "task_id": task_id,
                    "task_type": task_type,
                    "endpoint": endpoint,
                    "status": "failed",
                    "started_at": started_at,
                    "finished_at": utc_now().isoformat(),
                    "error_summary": f"{type(exc).__name__}: {safe_text(exc, 900)}",
                }
            )
            raise

    def acquire_lock(
        self,
        *,
        lock_key: str,
        owner: str,
        ttl_minutes: int,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        bucket = self._storage().bucket(self.config.lock_bucket)
        blob = bucket.blob(f"{self.config.lock_prefix.rstrip('/')}/{lock_key}.lock")
        payload = {
            "lock_key": lock_key,
            "lock_owner": owner,
            "lease_expires_at": (utc_now() + timedelta(minutes=ttl_minutes)).isoformat(),
            "acquired_at": utc_now().isoformat(),
        }
        if metadata:
            payload.update(metadata)
        stale_reclaimed = False
        for attempt in range(2):
            try:
                blob.upload_from_string(
                    json.dumps(payload, ensure_ascii=False),
                    content_type="application/json",
                    if_generation_match=0,
                )
                blob.reload()
                generation = int(blob.generation)
                return {
                    "acquired": True,
                    "generation": generation,
                    "lease_expires_at": payload["lease_expires_at"],
                    "stale_reclaimed": stale_reclaimed,
                    "lock_path": blob.name,
                }
            except PreconditionFailed:
                if attempt == 0 and self._reclaim_stale_lock(blob):
                    stale_reclaimed = True
                    continue
                current = self._read_lock_blob(blob)
                return {
                    "acquired": False,
                    "generation": current.get("generation"),
                    "lease_expires_at": current.get("lease_expires_at"),
                    "lock_owner": current.get("lock_owner"),
                    "lock_path": blob.name,
                }
        return {
            "acquired": False,
            "lock_path": blob.name,
        }

    def heartbeat_lock(self, *, lock_key: str, generation: int, ttl_minutes: int) -> dict[str, Any]:
        bucket = self._storage().bucket(self.config.lock_bucket)
        blob = bucket.blob(f"{self.config.lock_prefix.rstrip('/')}/{lock_key}.lock")
        try:
            existing = json.loads(blob.download_as_bytes(if_generation_match=generation))
            lease_expires_at = utc_now() + timedelta(minutes=ttl_minutes)
            existing["last_heartbeat_at"] = utc_now().isoformat()
            existing["lease_expires_at"] = lease_expires_at.isoformat()
            blob.upload_from_string(
                json.dumps(existing, ensure_ascii=False),
                content_type="application/json",
                if_generation_match=generation,
            )
            blob.reload()
            return {
                "generation": int(blob.generation),
                "lease_expires_at": existing["lease_expires_at"],
                "lock_path": blob.name,
            }
        except (PreconditionFailed, NotFound) as exc:
            raise RuntimeError(f"lock heartbeat lost ownership for {lock_key}: {exc}") from exc

    def release_lock(self, *, lock_key: str, generation: int) -> dict[str, Any]:
        bucket = self._storage().bucket(self.config.lock_bucket)
        blob = bucket.blob(f"{self.config.lock_prefix.rstrip('/')}/{lock_key}.lock")
        try:
            blob.delete(if_generation_match=generation)
            return {"released": True, "lock_path": blob.name}
        except NotFound:
            return {"released": True, "lock_path": blob.name, "already_missing": True}
        except PreconditionFailed as exc:
            raise RuntimeError(f"lock release lost ownership for {lock_key}: {exc}") from exc

    def _read_lock_blob(self, blob: storage.Blob) -> dict[str, Any]:
        blob.reload()
        content = json.loads(blob.download_as_bytes())
        content["generation"] = int(blob.generation)
        return content

    def _reclaim_stale_lock(self, blob: storage.Blob) -> bool:
        try:
            current = self._read_lock_blob(blob)
            expires_raw = current.get("lease_expires_at")
            if not expires_raw:
                return False
            expires_at = datetime.fromisoformat(expires_raw)
            if utc_now() <= expires_at:
                return False
            blob.delete(if_generation_match=current["generation"])
            return True
        except Exception:
            return False

