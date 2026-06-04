"""OQ-005 daily data pipeline.

Cloud Composer orchestrates Cloud Run ingestion jobs and daily ODS readiness
checks for the current ODS scope. Full warehouse refresh is behind an explicit
Airflow variable so the daily schedule does not scan 2019+ history by default.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pendulum
from airflow import DAG
from airflow.models import Variable
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import ShortCircuitOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.google.cloud.operators.cloud_run import CloudRunExecuteJobOperator
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule


PROJECT_ID = Variable.get("ashare_project_id", default_var="data-aquarium")
REGION = Variable.get("ashare_region", default_var="asia-east2")
BQ_LOCATION = Variable.get("ashare_bq_location", default_var="asia-east2")
PIPELINE_DRY_RUN = Variable.get("ashare_pipeline_dry_run", default_var="true").lower() == "true"
BUSINESS_DATE = "{{ dag_run.conf.get('business_date', ds) }}"
INGESTION_RUN_ID_PREFIX = "{{ dag_run.run_id }}"


def _read_sql(relative_path: str) -> str:
    dag_file = Path(__file__).resolve()
    candidate_roots = []
    candidate_roots.append(Path("/home/airflow/gcs/data"))
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
    )


def _cloud_run_ingestion_task(task_id: str, job_name: str, endpoint_group: str) -> CloudRunExecuteJobOperator:
    args = [
        "--endpoint-group",
        endpoint_group,
        "--business-date",
        BUSINESS_DATE,
        "--ingestion-run-id",
        f"{INGESTION_RUN_ID_PREFIX}_{endpoint_group}",
    ]
    if PIPELINE_DRY_RUN:
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


def _full_refresh_enabled() -> bool:
    return Variable.get("ashare_enable_full_refresh", default_var="false").lower() == "true"


with DAG(
    dag_id="ashare_daily_pipeline_v0",
    description="OQ-005 daily Tushare-compatible ingestion and BigQuery warehouse pipeline.",
    start_date=pendulum.datetime(2026, 6, 4, tz="Asia/Shanghai"),
    # Current-scope explicit daily updates finish by 17:00; 20:00 leaves a 3h buffer.
    schedule="0 20 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["quant-ashare", "oq005", "ods", "bigquery"],
) as dag:
    start = EmptyOperator(task_id="start")
    finish = EmptyOperator(
        task_id="finish",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    with TaskGroup(group_id="setup") as setup:
        ensure_datasets = _bq_sql_task("ensure_datasets", "sql/00_create_datasets.sql")
        ensure_meta_tables = _bq_sql_task("ensure_meta_tables", "sql/meta/01_create_meta_tables.sql")
        ensure_unit_contract_map = _bq_sql_task(
            "ensure_unit_contract_map",
            "sql/meta/01_ods_field_unit_map.sql",
        )

        ensure_datasets >> ensure_meta_tables >> ensure_unit_contract_map

    with TaskGroup(group_id="ingestion") as ingestion:
        _cloud_run_ingestion_task(
            task_id="ingest_current_scope",
            job_name="ashare-ingest-current-scope",
            endpoint_group="current_scope",
        )

    ods_daily_partition_readiness = _bq_sql_task(
        "ods_daily_partition_readiness",
        "sql/qa/09_ods_daily_partition_readiness.sql",
        query_parameters=[
            _string_query_parameter("business_date", BUSINESS_DATE),
            _string_query_parameter(
                "require_business_partition",
                "false" if PIPELINE_DRY_RUN else "true",
            ),
        ],
    )
    full_refresh_gate = ShortCircuitOperator(
        task_id="full_refresh_gate",
        python_callable=_full_refresh_enabled,
        ignore_downstream_trigger_rules=False,
    )
    ods_parquet_schema_p0 = _bq_sql_task(
        "ods_parquet_schema_p0",
        "sql/qa/06_ods_parquet_schema_checks.sql",
        query_parameters=[_string_query_parameter("priority_filter", "P0")],
    )

    with TaskGroup(group_id="dim") as dim:
        dim_trade_calendar = _bq_sql_task("dim_trade_calendar", "sql/dim/01_dim_trade_calendar.sql")
        dim_stock = _bq_sql_task("dim_stock", "sql/dim/02_dim_stock.sql")
        dim_stock_name_hist = _bq_sql_task("dim_stock_name_hist", "sql/dim/03_dim_stock_name_hist.sql")
        dim_index = _bq_sql_task("dim_index", "sql/dim/04_dim_index.sql")

        dim_trade_calendar >> dim_stock
        dim_stock >> dim_stock_name_hist
        dim_stock >> dim_index

    with TaskGroup(group_id="dwd") as dwd:
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

    with TaskGroup(group_id="dws") as dws:
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

    with TaskGroup(group_id="metadata") as metadata:
        p0_column_descriptions = _bq_sql_task(
            "p0_column_descriptions",
            "sql/metadata/01_p0_table_column_descriptions.sql",
        )
        finance_column_descriptions = _bq_sql_task(
            "finance_column_descriptions",
            "sql/metadata/02_finance_table_column_descriptions.sql",
        )

    with TaskGroup(group_id="qa") as qa:
        p0_smoke_checks = _bq_sql_task("p0_smoke_checks", "sql/qa/01_p0_smoke_checks.sql")
        strategy1_dws_ads_checks = _bq_sql_task(
            "strategy1_dws_ads_checks",
            "sql/qa/02_strategy1_dws_ads_checks.sql",
        )
        oq004_index_checks = _bq_sql_task("oq004_index_checks", "sql/qa/03_oq004_index_checks.sql")
        finance_caliber_checks = _bq_sql_task(
            "finance_caliber_checks",
            "sql/qa/04_finance_caliber_checks.sql",
        )
        oq006_unit_checks = _bq_sql_task("oq006_unit_checks", "sql/qa/05_oq006_unit_checks.sql")

        p0_smoke_checks >> strategy1_dws_ads_checks
        strategy1_dws_ads_checks >> oq004_index_checks
        oq004_index_checks >> finance_caliber_checks
        finance_caliber_checks >> oq006_unit_checks

    start >> setup >> ingestion
    ingestion >> ods_daily_partition_readiness >> finish
    ods_daily_partition_readiness >> full_refresh_gate >> ods_parquet_schema_p0
    ods_parquet_schema_p0 >> dim >> dwd >> dws >> metadata >> qa >> finish
