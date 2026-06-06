"""Ashare Pipeline Alert Checker DAG.

Periodically checks for pipeline failures and writes alerts to Cloud Logging.
This enables the Cloud Monitoring alert pipeline:
  v_alert_summary -> check_alerts.py -> Cloud Logging -> log-based metric -> alert policy

Schedule: every 10 minutes
Lookback: 20 minutes, intentionally overlapping to tolerate scheduler jitter
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.trigger_rule import TriggerRule


def _run_alert_check(**context) -> None:
    """Run check_alerts.py and write alerts to Cloud Logging."""
    # Try to find the script in multiple locations
    script_paths = [
        Path("/home/airflow/gcs/data/scripts/alerting/check_alerts.py"),
        Path(__file__).resolve().parents[3] / "scripts" / "alerting" / "check_alerts.py",
        Path.cwd() / "scripts" / "alerting" / "check_alerts.py",
    ]

    script_path = None
    for p in script_paths:
        if p.exists():
            script_path = p
            break

    if script_path is None:
        raise FileNotFoundError(
            f"check_alerts.py not found in any of: {[str(p) for p in script_paths]}"
        )

    # Run the script
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project", "data-aquarium",
            "--lookback-minutes", "20",
            "--write-log",
            "--write-heartbeat",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 1:
        # Query failure - this is a real error
        raise RuntimeError(f"Alert check failed: {result.stderr}")
    elif result.returncode == 2:
        # Alerts found - log them but don't fail the DAG
        print(f"Alerts found: {result.stdout}")
    elif result.returncode == 0:
        # No alerts
        print("No alerts found")
    else:
        raise RuntimeError(
            "Alert checker exited with unexpected return code "
            f"{result.returncode}.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


with DAG(
    dag_id="ashare_pipeline_alert_checker",
    description="Ashare pipeline periodic alert checker. Queries v_alert_summary and writes to Cloud Logging.",
    start_date=pendulum.datetime(2026, 6, 5, tz="Asia/Shanghai"),
    schedule="*/10 * * * *",
    catchup=False,
    max_active_runs=1,
    tags=["quant-ashare", "pipeline", "alerting"],
) as dag:
    check_alerts = PythonOperator(
        task_id="check_alerts",
        python_callable=_run_alert_check,
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )

    check_alerts
