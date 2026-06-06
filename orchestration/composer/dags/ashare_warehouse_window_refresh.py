"""Windowed warehouse refresh DAG for quant-ashare.

This DAG owns daily_current and backfill DIM/DWD/DWS refreshes. It can be
triggered by the ODS ingestion DAG or manually for a controlled backfill.
"""

from __future__ import annotations

import pendulum
from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator
from airflow.utils.trigger_rule import TriggerRule

from ashare_common import (
    BUSINESS_DATE,
    PIPELINE_DRY_RUN,
    REQUIRE_BUSINESS_PARTITION,
    _bq_sql_task,
    _qa_only_enabled,
    _string_query_parameter,
    _task_failure_callback,
    _task_success_callback,
    _window_transform_enabled,
    _write_pipeline_run_failed,
    build_pipeline_finalize_status,
    build_pipeline_start_status,
    build_qa_chain,
    build_setup_group,
    build_windowed_dim_group,
    build_windowed_metadata_group,
    build_windowed_transform_group,
)


def _window_refresh_branch(**context) -> str:
    if _qa_only_enabled(**context):
        return "run_qa_only"
    if _window_transform_enabled(**context):
        return "run_window_refresh"
    return "skip_window_refresh"


with DAG(
    dag_id="ashare_warehouse_window_refresh",
    description="Windowed DIM/DWD/DWS refresh for daily_current and backfill modes.",
    start_date=pendulum.datetime(2026, 6, 6, tz="Asia/Shanghai"),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={
        "on_success_callback": _task_success_callback,
        "on_failure_callback": _task_failure_callback,
    },
    on_failure_callback=_write_pipeline_run_failed,
    tags=["quant-ashare", "pipeline", "warehouse", "window"],
) as dag:
    start = EmptyOperator(task_id="start")
    finish = EmptyOperator(
        task_id="finish",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    setup = build_setup_group()
    pipeline_start_status = build_pipeline_start_status(
        default_run_label="warehouse_window_refresh",
        default_warehouse_mode="daily_current",
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
    )
    branch_window_refresh = BranchPythonOperator(
        task_id="branch_window_refresh",
        python_callable=_window_refresh_branch,
    )
    run_window_refresh = EmptyOperator(task_id="run_window_refresh")
    run_qa_only = EmptyOperator(task_id="run_qa_only")
    skip_window_refresh = EmptyOperator(task_id="skip_window_refresh")
    windowed_dim = build_windowed_dim_group()
    windowed_metadata = build_windowed_metadata_group()
    windowed_transform = build_windowed_transform_group()
    qa_after_window = build_qa_chain("qa_after_window")
    qa_only = build_qa_chain("qa_only")
    pipeline_finalize_status = build_pipeline_finalize_status(
        default_run_label="warehouse_window_refresh",
        default_warehouse_mode="daily_current",
    )

    start >> setup >> pipeline_start_status >> ods_daily_partition_readiness >> branch_window_refresh
    branch_window_refresh >> run_window_refresh
    branch_window_refresh >> run_qa_only
    branch_window_refresh >> skip_window_refresh
    run_window_refresh >> windowed_dim >> windowed_metadata >> windowed_transform >> qa_after_window
    run_qa_only >> qa_only
    [
        qa_after_window,
        qa_only,
        skip_window_refresh,
    ] >> pipeline_finalize_status >> finish
