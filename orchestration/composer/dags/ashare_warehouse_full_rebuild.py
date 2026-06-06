"""Manual full warehouse rebuild DAG for quant-ashare."""

from __future__ import annotations

import pendulum
from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator
from airflow.utils.trigger_rule import TriggerRule

from ashare_common import (
    _bq_sql_task,
    _full_rebuild_write_enabled,
    _task_failure_callback,
    _task_success_callback,
    _write_pipeline_run_failed,
    build_full_dim_group,
    build_full_dwd_group,
    build_full_dws_group,
    build_full_rebuild_confirm_task,
    build_metadata_group,
    build_pipeline_finalize_status,
    build_pipeline_start_status,
    build_qa_chain,
    build_setup_group,
)


def _full_rebuild_branch(**context) -> str:
    if _full_rebuild_write_enabled(**context):
        return "run_full_rebuild"
    return "skip_full_rebuild_write"


with DAG(
    dag_id="ashare_warehouse_full_rebuild",
    description="Manual DIM/DWD/DWS full rebuild with explicit confirmation guard.",
    start_date=pendulum.datetime(2026, 6, 6, tz="Asia/Shanghai"),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={
        "on_success_callback": _task_success_callback,
        "on_failure_callback": _task_failure_callback,
    },
    on_failure_callback=_write_pipeline_run_failed,
    tags=["quant-ashare", "pipeline", "warehouse", "full-rebuild"],
) as dag:
    start = EmptyOperator(task_id="start")
    finish = EmptyOperator(
        task_id="finish",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    setup = build_setup_group()
    pipeline_start_status = build_pipeline_start_status(
        default_run_label="manual_full_rebuild",
        default_warehouse_mode="full_rebuild",
    )
    confirm_full_rebuild = build_full_rebuild_confirm_task()
    branch_full_rebuild = BranchPythonOperator(
        task_id="branch_full_rebuild",
        python_callable=_full_rebuild_branch,
    )
    run_full_rebuild = EmptyOperator(task_id="run_full_rebuild")
    skip_full_rebuild_write = EmptyOperator(task_id="skip_full_rebuild_write")
    ods_parquet_schema_p0 = _bq_sql_task(
        "ods_parquet_schema_p0",
        "sql/qa/06_ods_parquet_schema_checks.sql",
        query_parameters=[
            {
                "name": "priority_filter",
                "parameterType": {"type": "STRING"},
                "parameterValue": {"value": "P0"},
            }
        ],
    )
    dim = build_full_dim_group()
    dwd = build_full_dwd_group()
    dws = build_full_dws_group()
    metadata = build_metadata_group()
    qa = build_qa_chain("qa")
    pipeline_finalize_status = build_pipeline_finalize_status(
        default_run_label="manual_full_rebuild",
        default_warehouse_mode="full_rebuild",
    )

    start >> setup >> pipeline_start_status >> confirm_full_rebuild >> branch_full_rebuild
    branch_full_rebuild >> run_full_rebuild
    branch_full_rebuild >> skip_full_rebuild_write
    run_full_rebuild >> ods_parquet_schema_p0 >> dim >> dwd >> dws >> metadata >> qa
    [
        qa,
        skip_full_rebuild_write,
    ] >> pipeline_finalize_status >> finish
