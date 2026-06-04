"""BigQuery audit/status writes for ODS ingestion jobs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

INGESTION_RUN_TABLE = "`data-aquarium.ashare_meta.ingestion_run`"
PARTITION_STATUS_TABLE = "`data-aquarium.ashare_meta.ingestion_partition_status`"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IngestionStatusWriter:
    """Persist live ingestion outcomes to ashare_meta.

    The writer is intentionally used only for live GCS writes. Dry-run and
    API-read-only smoke runs should not mutate production audit tables.
    """

    def __init__(self, project: str, location: str):
        self.project = project
        self.location = location
        self._client = None

    def write_results(
        self,
        results: list[dict[str, Any]],
        *,
        started_at: datetime,
        finished_at: datetime,
    ) -> None:
        for result in results:
            self._write_result(result, started_at=started_at, finished_at=finished_at)

    def write_failure(
        self,
        plan: list[dict[str, Any]],
        *,
        started_at: datetime,
        finished_at: datetime,
        error: BaseException,
    ) -> None:
        error_summary = _redact_error(error)
        for item in plan:
            result = {
                "ingestion_run_id": item["ingestion_run_id"],
                "source_system": item.get("source_system", "tushare"),
                "endpoint": item["endpoint"],
                "api": item.get("api", item["endpoint"]),
                "variant": item.get("variant", item["endpoint"]),
                "partition_endpoint": item.get("partition_endpoint", item["endpoint"]),
                "partition_date": item["partition_date"],
                "logical_date": item["partition_date"],
                "request_params_hash": item.get("request_params_hash"),
                "schema_version": item.get("schema_version"),
                "row_count": 0,
                "status": "failed",
                "gcs_uri": None,
                "error_summary": error_summary,
            }
            self._write_result(result, started_at=started_at, finished_at=finished_at)

    def _write_result(
        self,
        result: dict[str, Any],
        *,
        started_at: datetime,
        finished_at: datetime,
    ) -> None:
        params = self._params_for_result(result, started_at=started_at, finished_at=finished_at)
        self._bq().query(
            _INSERT_RUN_SQL,
            job_config=self._job_config(params),
        ).result()
        self._bq().query(
            _MERGE_PARTITION_STATUS_SQL,
            job_config=self._job_config(params),
        ).result()

    def _params_for_result(
        self,
        result: dict[str, Any],
        *,
        started_at: datetime,
        finished_at: datetime,
    ) -> list[Any]:
        from google.cloud import bigquery

        endpoint_key = result.get("partition_endpoint") or result["endpoint"]
        status = _canonical_status(result["status"])
        created_at = utc_now()
        return [
            bigquery.ScalarQueryParameter("ingestion_run_id", "STRING", result["ingestion_run_id"]),
            bigquery.ScalarQueryParameter("endpoint", "STRING", endpoint_key),
            bigquery.ScalarQueryParameter("source_system", "STRING", result.get("source_system", "tushare")),
            bigquery.ScalarQueryParameter("business_date_start", "STRING", result.get("logical_date")),
            bigquery.ScalarQueryParameter("business_date_end", "STRING", result.get("logical_date")),
            bigquery.ScalarQueryParameter("partition_date", "STRING", result["partition_date"]),
            bigquery.ScalarQueryParameter("request_params_hash", "STRING", result.get("request_params_hash")),
            bigquery.ScalarQueryParameter("row_count", "INT64", int(result.get("row_count") or 0)),
            bigquery.ScalarQueryParameter("schema_version", "STRING", result.get("schema_version")),
            bigquery.ScalarQueryParameter("gcs_uri", "STRING", result.get("gcs_uri")),
            bigquery.ScalarQueryParameter("status", "STRING", status),
            bigquery.ScalarQueryParameter("error_summary", "STRING", result.get("error_summary")),
            bigquery.ScalarQueryParameter("started_at", "TIMESTAMP", started_at),
            bigquery.ScalarQueryParameter("finished_at", "TIMESTAMP", finished_at),
            bigquery.ScalarQueryParameter("created_at", "TIMESTAMP", created_at),
            bigquery.ScalarQueryParameter("updated_at", "TIMESTAMP", finished_at),
        ]

    @staticmethod
    def _job_config(params: list[Any]) -> Any:
        from google.cloud import bigquery

        return bigquery.QueryJobConfig(query_parameters=params)

    def _bq(self) -> Any:
        from google.cloud import bigquery

        if self._client is None:
            self._client = bigquery.Client(project=self.project, location=self.location)
        return self._client


_INSERT_RUN_SQL = f"""
INSERT INTO {INGESTION_RUN_TABLE} (
  ingestion_run_id, endpoint, source_system, business_date_start, business_date_end,
  partition_date, request_params_hash, row_count, schema_version, gcs_uri, status,
  error_summary, started_at, finished_at, created_at
)
VALUES (
  @ingestion_run_id, @endpoint, @source_system, @business_date_start, @business_date_end,
  @partition_date, @request_params_hash, @row_count, @schema_version, @gcs_uri, @status,
  @error_summary, @started_at, @finished_at, @created_at
)
"""


_MERGE_PARTITION_STATUS_SQL = f"""
MERGE {PARTITION_STATUS_TABLE} AS T
USING (
  SELECT @endpoint AS endpoint, @partition_date AS partition_date
) AS S
ON T.endpoint = S.endpoint AND T.partition_date = S.partition_date
WHEN MATCHED THEN UPDATE SET
  status = @status,
  row_count = @row_count,
  ingestion_run_id = @ingestion_run_id,
  gcs_uri = @gcs_uri,
  schema_version = @schema_version,
  updated_at = @updated_at
WHEN NOT MATCHED THEN INSERT (
  endpoint, partition_date, status, row_count, ingestion_run_id,
  gcs_uri, schema_version, updated_at
)
VALUES (
  @endpoint, @partition_date, @status, @row_count, @ingestion_run_id,
  @gcs_uri, @schema_version, @updated_at
)
"""


def _canonical_status(status: str) -> str:
    if status == "success":
        return "success"
    if status == "empty_return":
        return "empty_return"
    if status == "failed":
        return "failed"
    return "skipped"


def _redact_error(error: BaseException) -> str:
    message = str(error)
    try:
        payload = json.loads(message)
        message = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except Exception:
        pass
    return message[:1000]
