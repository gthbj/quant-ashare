"""Daily ODS ingestion DAG for quant-ashare.

This DAG owns only production ODS collection and ODS readiness. Warehouse
refresh is triggered as a separate DAG after a successful real ingestion run.
"""

from __future__ import annotations

import pendulum
from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule

from ashare_common import (
    BUSINESS_DATE,
    DATE_TO,
    PIPELINE_DRY_RUN,
    REQUIRE_BUSINESS_PARTITION,
    _bq_sql_task,
    _cloud_run_ingestion_task,
    _non_trading_day_gate_branch,
    _pipeline_dry_run,
    _runtime_conf,
    _skip_ingestion_branch,
    _string_query_parameter,
    _task_failure_callback,
    _task_success_callback,
    _truthy,
    _write_pipeline_run_failed,
    build_pipeline_finalize_status,
    build_pipeline_start_status,
    build_setup_group,
    build_skip_downstream_refresh_task,
    build_skip_non_trading_day_task,
)


def _downstream_refresh_branch(**context) -> str:
    conf = _runtime_conf(context)
    if _truthy(conf.get("skip_downstream_refresh", False)):
        return "skip_downstream_refresh"
    if _pipeline_dry_run(context):
        return "skip_downstream_refresh"
    if _truthy(conf.get("skip_ingestion", False)) and not _truthy(conf.get("trigger_downstream_refresh", False)):
        return "skip_downstream_refresh"
    return "trigger_warehouse_window_refresh"


with DAG(
    dag_id="ashare_ods_ingestion_daily",
    description="Daily current-scope ODS ingestion and readiness gate.",
    start_date=pendulum.datetime(2026, 6, 6, tz="Asia/Shanghai"),
    schedule="0 20 * * *",
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=True,
    default_args={
        "on_success_callback": _task_success_callback,
        "on_failure_callback": _task_failure_callback,
    },
    on_failure_callback=_write_pipeline_run_failed,
    tags=["quant-ashare", "pipeline", "ods", "ingestion"],
) as dag:
    start = EmptyOperator(task_id="start")
    finish = EmptyOperator(
        task_id="finish",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    setup = build_setup_group()
    pipeline_start_status = build_pipeline_start_status(
        default_run_label="daily_ingestion",
        default_warehouse_mode="not_applicable",
    )
    non_trading_day_gate = BranchPythonOperator(
        task_id="non_trading_day_gate",
        python_callable=_non_trading_day_gate_branch,
        op_kwargs={
            "next_task_id": "branch_ingestion",
            "skip_task_id": "skip_non_trading_day",
            "require_daily_current": False,
        },
    )
    skip_non_trading_day = build_skip_non_trading_day_task()
    branch_ingestion = BranchPythonOperator(
        task_id="branch_ingestion",
        python_callable=_skip_ingestion_branch,
        op_kwargs={
            "readiness_task_id": "ods_daily_partition_readiness",
            "dry_run_task_id": "ingestion.ingest_current_scope_dry_run",
            "write_task_id": "ingestion.ingest_current_scope_write",
        },
    )

    with TaskGroup(group_id="ingestion") as ingestion:
        _cloud_run_ingestion_task(
            task_id="ingest_current_scope_dry_run",
            job_name="ashare-ingest-current-scope",
            endpoint_group="current_scope",
            dry_run=True,
        )
        _cloud_run_ingestion_task(
            task_id="ingest_current_scope_write",
            job_name="ashare-ingest-current-scope",
            endpoint_group="current_scope",
            dry_run=False,
        )

    ods_daily_partition_readiness = _bq_sql_task(
        "ods_daily_partition_readiness",
        "sql/qa/09_ods_daily_partition_readiness.sql",
        query_parameters=[
            _string_query_parameter("pipeline_run_id", "{{ dag_run.run_id }}"),
            _string_query_parameter("business_date", BUSINESS_DATE),
            _string_query_parameter("pipeline_dry_run", PIPELINE_DRY_RUN),
            _string_query_parameter(
                "require_business_partition",
                REQUIRE_BUSINESS_PARTITION,
            ),
        ],
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )
    branch_downstream_refresh = BranchPythonOperator(
        task_id="branch_downstream_refresh",
        python_callable=_downstream_refresh_branch,
    )
    skip_downstream_refresh = build_skip_downstream_refresh_task()
    trigger_warehouse_window_refresh = TriggerDagRunOperator(
        task_id="trigger_warehouse_window_refresh",
        trigger_dag_id="ashare_warehouse_window_refresh",
        conf={
            "business_date": BUSINESS_DATE,
            "date_to": DATE_TO,
            "warehouse_mode": "daily_current",
            "pipeline_dry_run": "false",
            "source_pipeline_run_id": "{{ dag_run.run_id }}",
            "source_dag_id": "{{ dag.dag_id }}",
            "run_label": "triggered_daily_current",
        },
        wait_for_completion=False,
    )
    pipeline_finalize_status = build_pipeline_finalize_status(
        default_run_label="daily_ingestion",
        default_warehouse_mode="not_applicable",
    )

    start >> setup >> pipeline_start_status >> non_trading_day_gate
    non_trading_day_gate >> skip_non_trading_day
    non_trading_day_gate >> branch_ingestion
    branch_ingestion >> ingestion >> ods_daily_partition_readiness
    branch_ingestion >> ods_daily_partition_readiness
    ods_daily_partition_readiness >> branch_downstream_refresh
    branch_downstream_refresh >> trigger_warehouse_window_refresh
    branch_downstream_refresh >> skip_downstream_refresh
    [
        skip_non_trading_day,
        trigger_warehouse_window_refresh,
        skip_downstream_refresh,
    ] >> pipeline_finalize_status >> finish
