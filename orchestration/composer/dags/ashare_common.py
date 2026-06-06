"""Shared helpers for quant-ashare Cloud Composer DAGs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from airflow.exceptions import AirflowFailException
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.google.cloud.operators.cloud_run import CloudRunExecuteJobOperator
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule


DEFAULT_PROJECT_ID = "data-aquarium"
DEFAULT_REGION = "asia-east2"
DEFAULT_BQ_LOCATION = "asia-east2"
PROJECT_ID = DEFAULT_PROJECT_ID
REGION = DEFAULT_REGION
BQ_LOCATION = DEFAULT_BQ_LOCATION

BUSINESS_DATE = "{{ dag_run.conf.get('business_date', data_interval_end.in_timezone('Asia/Shanghai').strftime('%Y-%m-%d')) }}"
DATE_FROM = "{{ dag_run.conf.get('date_from', '') }}"
DATE_TO = "{{ dag_run.conf.get('date_to', dag_run.conf.get('business_date', data_interval_end.in_timezone('Asia/Shanghai').strftime('%Y-%m-%d'))) }}"
TRANSFORM_BACKEND = "{{ dag_run.conf.get('transform_backend', var.value.get('ashare_transform_backend', 'bq_sql')) }}"
PIPELINE_DRY_RUN = "{{ dag_run.conf.get('pipeline_dry_run', dag_run.conf.get('dry_run', var.value.get('ashare_pipeline_dry_run', 'true'))) }}"
REQUIRE_BUSINESS_PARTITION = "{{ dag_run.conf.get('require_business_partition', var.value.get('ashare_require_business_partition', '')) }}"
LEGACY_FULL_REFRESH = "{{ var.value.get('ashare_enable_full_refresh', 'false') }}"
INGESTION_RUN_ID_PREFIX = "{{ dag_run.run_id }}"
UPSTREAM_PIPELINE_RUN_ID = "{{ dag_run.conf.get('upstream_pipeline_run_id', dag_run.conf.get('source_pipeline_run_id', '')) }}"
TRIGGERED_BY_DAG_ID = "{{ dag_run.conf.get('triggered_by_dag_id', dag_run.conf.get('source_dag_id', '')) }}"

DAG_DEFAULTS = {
    "ashare_ods_ingestion_daily": {
        "run_label": "daily_ingestion",
        "warehouse_mode": "not_applicable",
    },
    "ashare_warehouse_window_refresh": {
        "run_label": "warehouse_window_refresh",
        "warehouse_mode": "daily_current",
    },
    "ashare_warehouse_full_rebuild": {
        "run_label": "manual_full_rebuild",
        "warehouse_mode": "full_rebuild",
    },
    "ashare_daily_pipeline_v0": {
        "run_label": "production_daily",
        "warehouse_mode": "daily_current",
    },
}


def run_label_template(default: str) -> str:
    return "{{ dag_run.conf.get('run_label', '" + default + "') }}"


def warehouse_mode_template(default: str) -> str:
    return "{{ dag_run.conf.get('warehouse_mode', '" + default + "') }}"


def _read_sql(relative_path: str) -> str:
    dag_file = Path(__file__).resolve()
    candidate_roots = [Path("/home/airflow/gcs/data")]
    for parent_index in (3, 1, 0):
        if len(dag_file.parents) > parent_index:
            candidate_roots.append(dag_file.parents[parent_index])
    candidate_roots.append(Path.cwd())

    for root in candidate_roots:
        sql_path = root / relative_path
        if sql_path.exists():
            return sql_path.read_text()
    return f"ASSERT FALSE AS 'Missing bundled SQL file: {relative_path}';"


def _string_query_parameter(name: str, value: str) -> dict:
    return {
        "name": name,
        "parameterType": {"type": "STRING"},
        "parameterValue": {"value": value},
    }


def _bq_sql_task(
    task_id: str,
    relative_path: str,
    query_parameters: Sequence[dict] | None = None,
    trigger_rule: str = TriggerRule.ALL_SUCCESS,
) -> BigQueryInsertJobOperator:
    query_config = {
        "query": _read_sql(relative_path),
        "useLegacySql": False,
    }
    if query_parameters:
        query_config["queryParameters"] = list(query_parameters)

    return BigQueryInsertJobOperator(
        task_id=task_id,
        project_id=PROJECT_ID,
        location=BQ_LOCATION,
        configuration={"query": query_config},
        trigger_rule=trigger_rule,
    )


def _cloud_run_ingestion_task(
    task_id: str,
    job_name: str,
    endpoint_group: str,
    dry_run: bool,
) -> CloudRunExecuteJobOperator:
    args = [
        "--endpoint-group",
        endpoint_group,
        "--business-date",
        BUSINESS_DATE,
        "--ingestion-run-id",
        f"{INGESTION_RUN_ID_PREFIX}_{endpoint_group}_{'dry_run' if dry_run else 'write'}",
    ]
    if dry_run:
        args.append("--dry-run")
    else:
        args.append("--allow-gcs-write")

    return CloudRunExecuteJobOperator(
        task_id=task_id,
        project_id=PROJECT_ID,
        region=REGION,
        job_name=job_name,
        overrides={"container_overrides": [{"args": args}]},
    )


def _safe_text(value: Any, max_length: int = 1000) -> str:
    if value is None:
        return ""
    return str(value).replace("\x00", "")[:max_length]


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _runtime_conf(context: dict) -> dict:
    dag_run = context.get("dag_run")
    return getattr(dag_run, "conf", None) or {}


def _dag_id(context: dict) -> str:
    dag = context.get("dag")
    return getattr(dag, "dag_id", "")


def _dag_default(context: dict, field: str, fallback: str) -> str:
    return DAG_DEFAULTS.get(_dag_id(context), {}).get(field, fallback)


def _runtime_value(context: dict, conf_key: str, variable_name: str, default: str) -> str:
    conf = _runtime_conf(context)
    if conf_key in conf and conf[conf_key] is not None:
        return str(conf[conf_key])
    return Variable.get(variable_name, default_var=default)


def _project_id() -> str:
    return Variable.get("ashare_project_id", default_var=DEFAULT_PROJECT_ID)


def _region() -> str:
    return Variable.get("ashare_region", default_var=DEFAULT_REGION)


def _bq_location() -> str:
    return Variable.get("ashare_bq_location", default_var=DEFAULT_BQ_LOCATION)


def _business_date_value(context: dict) -> str:
    conf = _runtime_conf(context)
    if conf.get("business_date"):
        return str(conf["business_date"])
    data_interval_end = context.get("data_interval_end")
    if data_interval_end is not None:
        return data_interval_end.in_timezone("Asia/Shanghai").strftime("%Y-%m-%d")
    return str(context.get("ds") or "")


def _date_to_value(context: dict) -> str:
    conf = _runtime_conf(context)
    if conf.get("date_to"):
        return str(conf["date_to"])
    return _business_date_value(context)


def _run_label(context: dict) -> str:
    conf = _runtime_conf(context)
    if conf.get("run_label") is not None:
        return str(conf["run_label"])
    return _dag_default(context, "run_label", "production_daily")


def _selected_warehouse_mode(context: dict, default: str | None = None) -> str:
    if default is None:
        default = _dag_default(context, "warehouse_mode", "daily_current")
    conf = _runtime_conf(context)
    if conf.get("warehouse_mode") is not None:
        return str(conf["warehouse_mode"]).strip().lower()
    return default.strip().lower()


def _effective_warehouse_mode(context: dict, default: str | None = None) -> str:
    mode = _selected_warehouse_mode(context, default=default)
    legacy_full_refresh = _truthy(Variable.get("ashare_enable_full_refresh", default_var="false"))
    if mode == "daily_current" and legacy_full_refresh:
        return "full_rebuild_compat"
    return mode


def _transform_backend(context: dict) -> str:
    return _runtime_value(context, "transform_backend", "ashare_transform_backend", "bq_sql").strip().lower()


def _skip_transform(context: dict) -> bool:
    conf = _runtime_conf(context)
    if "skip_transform" in conf:
        return _truthy(conf["skip_transform"])
    return _truthy(Variable.get("ashare_skip_transform", default_var="false"))


def _pipeline_dry_run(context: dict) -> bool:
    conf = _runtime_conf(context)
    for key in ("pipeline_dry_run", "dry_run"):
        if key in conf:
            return _truthy(conf[key])
    return _truthy(Variable.get("ashare_pipeline_dry_run", default_var="true"))


def _dag_run_type(context: dict) -> str:
    dag_run = context.get("dag_run")
    run_type = getattr(dag_run, "run_type", "")
    return str(getattr(run_type, "value", run_type)).strip().lower()


def _sse_is_open_date(business_date: str) -> bool:
    from google.cloud import bigquery

    query = """
SELECT
  COUNT(1) AS calendar_rows,
  COUNTIF(is_open IS NULL) AS null_is_open_rows,
  COALESCE(LOGICAL_OR(is_open = 1), FALSE) AS is_open
FROM `data-aquarium.ashare_dim.dim_trade_calendar`
WHERE exchange = 'SSE'
  AND cal_date = SAFE_CAST(@business_date AS DATE)
"""
    client = bigquery.Client(project=_project_id(), location=_bq_location())
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("business_date", "STRING", business_date),
        ]
    )
    row = next(iter(client.query(query, job_config=job_config).result()), None)
    if row is None or row.calendar_rows == 0:
        raise RuntimeError(f"SSE trade calendar has no row for business_date={business_date}")
    if row.null_is_open_rows:
        raise RuntimeError(f"SSE trade calendar has NULL is_open for business_date={business_date}")
    return bool(row.is_open)


def _non_trading_day_gate_enabled(context: dict) -> bool:
    if _dag_run_type(context) == "scheduled":
        return True
    return _truthy(_runtime_conf(context).get("force_non_trading_day_gate", False))


def _non_trading_day_gate_branch(
    next_task_id: str,
    skip_task_id: str = "skip_non_trading_day",
    require_daily_current: bool = True,
    **context,
) -> str:
    if not _non_trading_day_gate_enabled(context):
        return next_task_id
    if require_daily_current and _effective_warehouse_mode(context) != "daily_current":
        return next_task_id
    if _sse_is_open_date(_business_date_value(context)):
        return next_task_id
    return skip_task_id


def _skip_ingestion_branch(
    readiness_task_id: str = "ods_daily_partition_readiness",
    dry_run_task_id: str = "ingestion.ingest_current_scope_dry_run",
    write_task_id: str = "ingestion.ingest_current_scope_write",
    **context,
) -> str | list[str]:
    if _truthy(_runtime_conf(context).get("skip_ingestion", False)):
        return readiness_task_id
    ingestion_task_id = dry_run_task_id if _pipeline_dry_run(context) else write_task_id
    return [ingestion_task_id, readiness_task_id]


def _window_transform_enabled(**context) -> bool:
    if _skip_transform(context) or _pipeline_dry_run(context):
        return False
    mode = _effective_warehouse_mode(context, default="daily_current")
    backend = _transform_backend(context)
    return backend == "bq_sql" and mode in {"daily_current", "backfill"}


def _full_rebuild_write_enabled(**context) -> bool:
    if _skip_transform(context) or _pipeline_dry_run(context):
        return False
    mode = _effective_warehouse_mode(context, default="full_rebuild")
    backend = _transform_backend(context)
    return backend == "bq_sql" and mode in {"full_rebuild", "full_rebuild_compat"}


def _qa_only_enabled(**context) -> bool:
    return not _skip_transform(context) and _effective_warehouse_mode(context) == "qa_only"


def _task_type(task_id: str) -> str:
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
    if task_id == "ads_contract_init":
        return "ads_contract"
    return "orchestration"


def _xcom_text(context: dict, key: str | None = None, max_length: int = 500) -> str:
    task_instance = context.get("task_instance")
    if task_instance is None:
        return ""
    try:
        value = task_instance.xcom_pull(task_ids=task_instance.task_id, key=key)
    except Exception:
        return ""
    return _safe_text(value, max_length=max_length)


def _cloud_run_execution_id(context: dict) -> str:
    execution_text = _xcom_text(context, key=None, max_length=500)
    if "/executions/" in execution_text:
        return execution_text.rsplit("/executions/", 1)[-1].split("/", 1)[0]
    return execution_text.rsplit("/", 1)[-1]


def _bigquery_job_url(job_id: str) -> str:
    if not job_id:
        return ""
    return f"https://console.cloud.google.com/bigquery?project={_project_id()}&j=bq:{_bq_location()}:{job_id}&page=queryresults"


def _cloud_run_execution_url(execution_id: str) -> str:
    if not execution_id:
        return ""
    return f"https://console.cloud.google.com/run/jobs/executions/details/{_region()}/{execution_id}?project={_project_id()}"


def _pipeline_run_parameters(
    status: str,
    *,
    default_run_label: str,
    default_warehouse_mode: str,
) -> list[dict]:
    return [
        _string_query_parameter("pipeline_run_id", "{{ dag_run.run_id }}"),
        _string_query_parameter("dag_id", "{{ dag.dag_id }}"),
        _string_query_parameter("business_date", BUSINESS_DATE),
        _string_query_parameter("date_from", DATE_FROM),
        _string_query_parameter("date_to", DATE_TO),
        _string_query_parameter("run_label", run_label_template(default_run_label)),
        _string_query_parameter("warehouse_mode", warehouse_mode_template(default_warehouse_mode)),
        _string_query_parameter("legacy_full_refresh", LEGACY_FULL_REFRESH),
        _string_query_parameter("transform_backend", TRANSFORM_BACKEND),
        _string_query_parameter("upstream_pipeline_run_id", UPSTREAM_PIPELINE_RUN_ID),
        _string_query_parameter("triggered_by_dag_id", TRIGGERED_BY_DAG_ID),
        _string_query_parameter("status", status),
    ]


def _window_refresh_parameters(default_warehouse_mode: str = "daily_current") -> list[dict]:
    return [
        _string_query_parameter("business_date", BUSINESS_DATE),
        _string_query_parameter("date_from", DATE_FROM),
        _string_query_parameter("date_to", DATE_TO),
        _string_query_parameter("warehouse_mode", warehouse_mode_template(default_warehouse_mode)),
    ]


def _pipeline_run_status_task(
    task_id: str,
    status: str,
    *,
    default_run_label: str,
    default_warehouse_mode: str,
    trigger_rule: str = TriggerRule.ALL_SUCCESS,
) -> BigQueryInsertJobOperator:
    query = """
DECLARE selected_warehouse_mode STRING DEFAULT LOWER(@warehouse_mode);
DECLARE effective_warehouse_mode STRING DEFAULT IF(
  LOWER(@legacy_full_refresh) IN ('1', 'true', 'yes', 'y', 'on')
  AND selected_warehouse_mode = 'daily_current',
  'full_rebuild_compat',
  selected_warehouse_mode
);

MERGE `data-aquarium.ashare_meta.pipeline_run` AS T
USING (
  SELECT
    @pipeline_run_id AS pipeline_run_id,
    @dag_id AS dag_id,
    @business_date AS business_date,
    NULLIF(@date_from, '') AS date_from,
    NULLIF(@date_to, '') AS date_to,
    @run_label AS run_label,
    effective_warehouse_mode AS warehouse_mode,
    LOWER(@transform_backend) AS transform_backend,
    NULLIF(@upstream_pipeline_run_id, '') AS upstream_pipeline_run_id,
    NULLIF(@triggered_by_dag_id, '') AS triggered_by_dag_id,
    @status AS status
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
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP()
);
"""
    return BigQueryInsertJobOperator(
        task_id=task_id,
        project_id=PROJECT_ID,
        location=BQ_LOCATION,
        configuration={
            "query": {
                "query": query,
                "useLegacySql": False,
                "queryParameters": _pipeline_run_parameters(
                    status,
                    default_run_label=default_run_label,
                    default_warehouse_mode=default_warehouse_mode,
                ),
            }
        },
        trigger_rule=trigger_rule,
    )


def _write_pipeline_task_status(context: dict, status: str) -> None:
    try:
        from google.cloud import bigquery

        task_instance = context["task_instance"]
        dag_run = context["dag_run"]
        task_id = task_instance.task_id
        bq_job_id = _xcom_text(context, key="job_id", max_length=256)
        cloud_run_execution = _cloud_run_execution_id(context) if task_id.startswith("ingestion.") else ""
        exception = context.get("exception")
        error_summary = _safe_text(f"{type(exception).__name__}: {exception}", 1000) if exception else ""
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
    @cloud_run_execution_id AS cloud_run_execution_id,
    @airflow_log_url AS airflow_log_url,
    @bigquery_job_url AS bigquery_job_url,
    @cloud_run_execution_url AS cloud_run_execution_url,
    @status AS status,
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
  cloud_run_execution_id = S.cloud_run_execution_id,
  airflow_log_url = S.airflow_log_url,
  bigquery_job_url = S.bigquery_job_url,
  cloud_run_execution_url = S.cloud_run_execution_url,
  status = S.status,
  error_summary = S.error_summary,
  started_at = COALESCE(S.started_at, T.started_at),
  finished_at = S.finished_at,
  created_at = T.created_at,
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
  cloud_run_execution_id,
  airflow_log_url,
  bigquery_job_url,
  cloud_run_execution_url,
  status,
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
  S.cloud_run_execution_id,
  S.airflow_log_url,
  S.bigquery_job_url,
  S.cloud_run_execution_url,
  S.status,
  S.error_summary,
  S.started_at,
  S.finished_at,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP()
);
"""
        client = bigquery.Client(project=_project_id(), location=_bq_location())
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("pipeline_run_id", "STRING", dag_run.run_id),
                bigquery.ScalarQueryParameter("task_id", "STRING", task_id),
                bigquery.ScalarQueryParameter("task_type", "STRING", _task_type(task_id)),
                bigquery.ScalarQueryParameter("business_date", "STRING", _business_date_value(context)),
                bigquery.ScalarQueryParameter("date_from", "STRING", _runtime_conf(context).get("date_from", "")),
                bigquery.ScalarQueryParameter("date_to", "STRING", _date_to_value(context)),
                bigquery.ScalarQueryParameter("run_label", "STRING", _run_label(context)),
                bigquery.ScalarQueryParameter("warehouse_mode", "STRING", _effective_warehouse_mode(context)),
                bigquery.ScalarQueryParameter("transform_backend", "STRING", _transform_backend(context)),
                bigquery.ScalarQueryParameter("endpoint", "STRING", "current_scope" if task_id.startswith("ingestion.") else ""),
                bigquery.ScalarQueryParameter("bigquery_job_id", "STRING", bq_job_id),
                bigquery.ScalarQueryParameter("cloud_run_execution_id", "STRING", cloud_run_execution),
                bigquery.ScalarQueryParameter("airflow_log_url", "STRING", _safe_text(getattr(task_instance, "log_url", ""), 1000)),
                bigquery.ScalarQueryParameter("bigquery_job_url", "STRING", _bigquery_job_url(bq_job_id)),
                bigquery.ScalarQueryParameter("cloud_run_execution_url", "STRING", _cloud_run_execution_url(cloud_run_execution)),
                bigquery.ScalarQueryParameter("status", "STRING", status),
                bigquery.ScalarQueryParameter("error_summary", "STRING", error_summary),
                bigquery.ScalarQueryParameter(
                    "started_at",
                    "STRING",
                    task_instance.start_date.isoformat() if task_instance.start_date else "",
                ),
                bigquery.ScalarQueryParameter(
                    "finished_at",
                    "STRING",
                    task_instance.end_date.isoformat() if task_instance.end_date else "",
                ),
            ]
        )
        client.query(query, job_config=job_config).result()
    except Exception as exc:
        print(f"pipeline_task_status write skipped: {type(exc).__name__}: {_safe_text(exc, 300)}")


def _write_pipeline_run_failed(context: dict) -> None:
    try:
        from google.cloud import bigquery

        dag_run = context["dag_run"]
        exception = context.get("exception")
        error_summary = _safe_text(f"{type(exception).__name__}: {exception}", 1000) if exception else ""
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
    @error_summary AS error_summary
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
  status = 'failed',
  finished_at = CURRENT_TIMESTAMP(),
  error_summary = S.error_summary,
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
  'failed',
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP(),
  S.error_summary,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP()
);
"""
        client = bigquery.Client(project=_project_id(), location=_bq_location())
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("pipeline_run_id", "STRING", dag_run.run_id),
                bigquery.ScalarQueryParameter("dag_id", "STRING", context["dag"].dag_id),
                bigquery.ScalarQueryParameter("business_date", "STRING", _business_date_value(context)),
                bigquery.ScalarQueryParameter("date_from", "STRING", _runtime_conf(context).get("date_from", "")),
                bigquery.ScalarQueryParameter("date_to", "STRING", _date_to_value(context)),
                bigquery.ScalarQueryParameter("run_label", "STRING", _run_label(context)),
                bigquery.ScalarQueryParameter("warehouse_mode", "STRING", _effective_warehouse_mode(context)),
                bigquery.ScalarQueryParameter("transform_backend", "STRING", _transform_backend(context)),
                bigquery.ScalarQueryParameter(
                    "upstream_pipeline_run_id",
                    "STRING",
                    _runtime_conf(context).get("upstream_pipeline_run_id", _runtime_conf(context).get("source_pipeline_run_id", "")),
                ),
                bigquery.ScalarQueryParameter(
                    "triggered_by_dag_id",
                    "STRING",
                    _runtime_conf(context).get("triggered_by_dag_id", _runtime_conf(context).get("source_dag_id", "")),
                ),
                bigquery.ScalarQueryParameter("error_summary", "STRING", error_summary),
            ]
        )
        client.query(query, job_config=job_config).result()
    except Exception as exc:
        print(f"pipeline_run failed-status write skipped: {type(exc).__name__}: {_safe_text(exc, 300)}")


def _task_success_callback(context: dict) -> None:
    _write_pipeline_task_status(context, "success")


def _task_failure_callback(context: dict) -> None:
    _write_pipeline_task_status(context, "failed")


def _task_skipped_status_callback(context: dict) -> None:
    _write_pipeline_task_status(context, "skipped")


def _write_skip_non_trading_day_status(**context) -> None:
    _write_pipeline_task_status(context, "skipped")


def _write_skip_downstream_refresh_status(**context) -> None:
    _write_pipeline_task_status(context, "skipped")


def _require_full_rebuild_confirmed(**context) -> None:
    conf = _runtime_conf(context)
    if not _truthy(conf.get("confirm_full_rebuild", False)):
        raise AirflowFailException("confirm_full_rebuild=true is required for ashare_warehouse_full_rebuild")
    mode = _effective_warehouse_mode(context, default="full_rebuild")
    if mode not in {"full_rebuild", "full_rebuild_compat"}:
        raise AirflowFailException(f"warehouse_mode must be full_rebuild or full_rebuild_compat, got {mode}")
    if not conf.get("date_from") or not conf.get("date_to"):
        raise AirflowFailException("date_from and date_to are required for ashare_warehouse_full_rebuild")


def build_setup_group(group_id: str = "setup") -> TaskGroup:
    with TaskGroup(group_id=group_id) as setup:
        ensure_datasets = _bq_sql_task("ensure_datasets", "sql/00_create_datasets.sql")
        ensure_meta_tables = _bq_sql_task("ensure_meta_tables", "sql/meta/01_create_meta_tables.sql")
        ensure_unit_contract_map = _bq_sql_task(
            "ensure_unit_contract_map",
            "sql/meta/04_ods_field_unit_map.sql",
        )

        ensure_datasets >> ensure_meta_tables >> ensure_unit_contract_map

    return setup


def build_qa_chain(group_id: str) -> TaskGroup:
    with TaskGroup(group_id=group_id) as qa_group:
        core_smoke_checks = _bq_sql_task("core_smoke_checks", "sql/qa/01_core_smoke_checks.sql")
        strategy1_dws_ads_checks = _bq_sql_task(
            "strategy1_dws_ads_checks",
            "sql/qa/02_strategy1_dws_ads_checks.sql",
        )
        index_benchmark_checks = _bq_sql_task("index_benchmark_checks", "sql/qa/03_index_benchmark_checks.sql")
        finance_caliber_checks = _bq_sql_task(
            "finance_caliber_checks",
            "sql/qa/04_finance_caliber_checks.sql",
        )
        unit_contract_checks = _bq_sql_task("unit_contract_checks", "sql/qa/05_unit_contract_checks.sql")

        core_smoke_checks >> strategy1_dws_ads_checks
        strategy1_dws_ads_checks >> index_benchmark_checks
        index_benchmark_checks >> finance_caliber_checks
        finance_caliber_checks >> unit_contract_checks

    return qa_group


def build_full_dim_group(group_id: str = "dim") -> TaskGroup:
    with TaskGroup(group_id=group_id) as dim:
        dim_trade_calendar = _bq_sql_task("dim_trade_calendar", "sql/dim/01_dim_trade_calendar.sql")
        dim_stock = _bq_sql_task("dim_stock", "sql/dim/02_dim_stock.sql")
        dim_stock_name_hist = _bq_sql_task("dim_stock_name_hist", "sql/dim/03_dim_stock_name_hist.sql")
        dim_index = _bq_sql_task("dim_index", "sql/dim/04_dim_index.sql")

        dim_trade_calendar >> dim_stock
        dim_stock >> dim_stock_name_hist
        dim_stock >> dim_index

    return dim


def build_full_dwd_group(group_id: str = "dwd") -> TaskGroup:
    with TaskGroup(group_id=group_id) as dwd:
        dwd_stock_eod_price = _bq_sql_task("dwd_stock_eod_price", "sql/dwd/01_dwd_stock_eod_price.sql")
        dwd_stock_eod_valuation = _bq_sql_task(
            "dwd_stock_eod_valuation",
            "sql/dwd/02_dwd_stock_eod_valuation.sql",
        )
        dwd_index_eod = _bq_sql_task("dwd_index_eod", "sql/dwd/04_dwd_index_eod.sql")
        dwd_fin_indicator = _bq_sql_task("dwd_fin_indicator", "sql/dwd/03_dwd_fin_indicator.sql")
        dwd_fin_indicator_latest = _bq_sql_task(
            "dwd_fin_indicator_latest",
            "sql/dwd/05_dwd_fin_indicator_latest.sql",
        )
        dwd_fin_income = _bq_sql_task("dwd_fin_income", "sql/dwd/06_dwd_fin_income.sql")
        dwd_fin_income_latest = _bq_sql_task(
            "dwd_fin_income_latest",
            "sql/dwd/07_dwd_fin_income_latest.sql",
        )
        dwd_fin_balancesheet = _bq_sql_task(
            "dwd_fin_balancesheet",
            "sql/dwd/08_dwd_fin_balancesheet.sql",
        )
        dwd_fin_balancesheet_latest = _bq_sql_task(
            "dwd_fin_balancesheet_latest",
            "sql/dwd/09_dwd_fin_balancesheet_latest.sql",
        )
        dwd_fin_cashflow = _bq_sql_task("dwd_fin_cashflow", "sql/dwd/10_dwd_fin_cashflow.sql")
        dwd_fin_cashflow_latest = _bq_sql_task(
            "dwd_fin_cashflow_latest",
            "sql/dwd/11_dwd_fin_cashflow_latest.sql",
        )

        dwd_stock_eod_price >> dwd_stock_eod_valuation
        dwd_fin_indicator >> dwd_fin_indicator_latest
        dwd_fin_income >> dwd_fin_income_latest
        dwd_fin_balancesheet >> dwd_fin_balancesheet_latest
        dwd_fin_cashflow >> dwd_fin_cashflow_latest

    return dwd


def build_full_dws_group(group_id: str = "dws") -> TaskGroup:
    with TaskGroup(group_id=group_id) as dws:
        dws_stock_universe_daily = _bq_sql_task(
            "dws_stock_universe_daily",
            "sql/dws/01_dws_stock_universe_daily.sql",
        )
        dws_stock_feature_price_daily = _bq_sql_task(
            "dws_stock_feature_price_daily",
            "sql/dws/02_dws_stock_feature_price_daily.sql",
        )
        dws_stock_feature_valuation_daily = _bq_sql_task(
            "dws_stock_feature_valuation_daily",
            "sql/dws/03_dws_stock_feature_valuation_daily.sql",
        )
        dws_stock_label_daily = _bq_sql_task("dws_stock_label_daily", "sql/dws/04_dws_stock_label_daily.sql")
        dws_stock_feature_daily_v0 = _bq_sql_task(
            "dws_stock_feature_daily_v0",
            "sql/dws/05_dws_stock_feature_daily_v0.sql",
        )
        dws_stock_sample_daily = _bq_sql_task("dws_stock_sample_daily", "sql/dws/06_dws_stock_sample_daily.sql")
        dws_stock_feature_fin_daily = _bq_sql_task(
            "dws_stock_feature_fin_daily",
            "sql/dws/07_dws_stock_feature_fin_daily.sql",
        )

        dws_stock_universe_daily >> [
            dws_stock_feature_price_daily,
            dws_stock_feature_valuation_daily,
            dws_stock_label_daily,
            dws_stock_feature_fin_daily,
        ]
        [
            dws_stock_feature_price_daily,
            dws_stock_feature_valuation_daily,
        ] >> dws_stock_feature_daily_v0
        [
            dws_stock_feature_daily_v0,
            dws_stock_label_daily,
        ] >> dws_stock_sample_daily

    return dws


def build_metadata_group(group_id: str = "metadata", include_finance: bool = True) -> TaskGroup:
    with TaskGroup(group_id=group_id) as metadata:
        core_column_descriptions = _bq_sql_task(
            "core_column_descriptions",
            "sql/metadata/01_core_table_column_descriptions.sql",
        )
        if include_finance:
            finance_column_descriptions = _bq_sql_task(
                "finance_column_descriptions",
                "sql/metadata/02_finance_table_column_descriptions.sql",
            )
            core_column_descriptions >> finance_column_descriptions

    return metadata


def build_windowed_dim_group(group_id: str = "windowed_dim") -> TaskGroup:
    with TaskGroup(group_id=group_id) as windowed_dim:
        windowed_dim_trade_calendar = _bq_sql_task("dim_trade_calendar", "sql/dim/01_dim_trade_calendar.sql")
        windowed_dim_stock = _bq_sql_task("dim_stock", "sql/dim/02_dim_stock.sql")
        windowed_dim_stock_name_hist = _bq_sql_task("dim_stock_name_hist", "sql/dim/03_dim_stock_name_hist.sql")
        windowed_dim_index = _bq_sql_task("dim_index", "sql/dim/04_dim_index.sql")

        windowed_dim_trade_calendar >> windowed_dim_stock
        windowed_dim_stock >> windowed_dim_stock_name_hist
        windowed_dim_stock >> windowed_dim_index

    return windowed_dim


def build_windowed_metadata_group(group_id: str = "windowed_metadata") -> TaskGroup:
    with TaskGroup(group_id=group_id) as windowed_metadata:
        _bq_sql_task(
            "core_column_descriptions",
            "sql/metadata/01_core_table_column_descriptions.sql",
        )

    return windowed_metadata


def build_windowed_transform_group(group_id: str = "windowed_transform") -> TaskGroup:
    with TaskGroup(group_id=group_id) as windowed_transform:
        stock_dwd_dws_window = _bq_sql_task(
            "stock_dwd_dws_window",
            "sql/incremental/01_refresh_stock_dwd_dws_window.sql",
            query_parameters=_window_refresh_parameters(),
        )
        windowed_stock_refresh_checks = _bq_sql_task(
            "windowed_stock_refresh_checks",
            "sql/qa/10_windowed_stock_refresh_checks.sql",
            query_parameters=_window_refresh_parameters(),
        )

        stock_dwd_dws_window >> windowed_stock_refresh_checks

    return windowed_transform


def build_pipeline_start_status(
    default_run_label: str,
    default_warehouse_mode: str,
) -> BigQueryInsertJobOperator:
    return _pipeline_run_status_task(
        "pipeline_start_status",
        "running",
        default_run_label=default_run_label,
        default_warehouse_mode=default_warehouse_mode,
    )


def build_pipeline_finalize_status(
    default_run_label: str,
    default_warehouse_mode: str,
) -> BigQueryInsertJobOperator:
    return _pipeline_run_status_task(
        "pipeline_finalize_status",
        "success",
        default_run_label=default_run_label,
        default_warehouse_mode=default_warehouse_mode,
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )


def build_skip_non_trading_day_task() -> PythonOperator:
    return PythonOperator(
        task_id="skip_non_trading_day",
        python_callable=_write_skip_non_trading_day_status,
        on_success_callback=_task_skipped_status_callback,
    )


def build_skip_downstream_refresh_task() -> PythonOperator:
    return PythonOperator(
        task_id="skip_downstream_refresh",
        python_callable=_write_skip_downstream_refresh_status,
        on_success_callback=_task_skipped_status_callback,
    )


def build_full_rebuild_confirm_task() -> PythonOperator:
    return PythonOperator(
        task_id="confirm_full_rebuild",
        python_callable=_require_full_rebuild_confirmed,
    )
