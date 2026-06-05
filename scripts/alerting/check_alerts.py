#!/usr/bin/env python3
"""OQ-005 Pipeline 告警查询脚本。

查询 v_alert_summary 视图，检测到异常时：
  - 默认：打印到 stdout
  - --write-log：写入 Cloud Logging（供 Cloud Monitoring 日志指标采集）
  - --notify：发送通知（stdout / Slack / Email）

使用方式：
    # 查询最近 1 小时异常
    python scripts/alerting/check_alerts.py

    # 写入 Cloud Logging（供告警链路使用）
    python scripts/alerting/check_alerts.py --write-log

    # 指定查询窗口
    python scripts/alerting/check_alerts.py --lookback-minutes 10

前置条件：
    1. 已执行 sql/observability/01_pipeline_status_views.sql 创建视图
    2. 已配置 ADC：gcloud auth application-default login
    3. 如使用 --write-log，需启用 Cloud Logging API
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

try:
    from google.cloud import bigquery
except ImportError:
    print("请安装依赖：pip install google-cloud-bigquery")
    sys.exit(1)

try:
    from google.cloud import logging as cloud_logging
    HAS_CLOUD_LOGGING = True
except ImportError:
    HAS_CLOUD_LOGGING = False


PROJECT_ID = "data-aquarium"
DATASET = "ashare_meta"
REGION = "asia-east2"
LOG_NAME = "oq005-pipeline-alerts"


def check_alerts(
    project_id: str,
    lookback_minutes: int = 60,
) -> list[dict[str, Any]]:
    """查询最近 N 分钟的异常。"""
    client = bigquery.Client(project=project_id, location=REGION)

    query = f"""
SELECT
  alert_type,
  resource_id,
  business_date,
  warehouse_mode,
  status,
  error_summary,
  started_at,
  finished_at
FROM `{project_id}.{DATASET}.v_alert_summary`
WHERE finished_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {lookback_minutes} MINUTE)
ORDER BY finished_at DESC
"""

    results = []
    try:
        rows = client.query(query).result()
        for row in rows:
            results.append({
                "alert_type": row.alert_type,
                "resource_id": row.resource_id,
                "business_date": row.business_date,
                "warehouse_mode": row.warehouse_mode,
                "status": row.status,
                "error_summary": row.error_summary,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            })
    except Exception as e:
        print(f"查询失败：{e}", file=sys.stderr)
        return []

    return results


def write_to_cloud_logging(
    project_id: str,
    alerts: list[dict[str, Any]],
) -> int:
    """将异常写入 Cloud Logging，供日志指标采集。"""
    if not HAS_CLOUD_LOGGING:
        print("请安装依赖：pip install google-cloud-logging", file=sys.stderr)
        return 0

    client = cloud_logging.Client(project=project_id)
    logger = client.logger(LOG_NAME)

    written = 0
    for alert in alerts:
        # 每条异常作为一个独立的日志条目
        payload = {
            "alert_type": alert["alert_type"],
            "resource_id": alert["resource_id"],
            "business_date": alert["business_date"],
            "warehouse_mode": alert["warehouse_mode"],
            "status": alert["status"],
            "error_summary": (alert.get("error_summary") or "")[:500],
            "started_at": alert["started_at"],
            "finished_at": alert["finished_at"],
        }
        logger.log_struct(payload, severity="ERROR")
        written += 1

    return written


def format_alert_message(alerts: list[dict[str, Any]]) -> str:
    """格式化告警消息。"""
    if not alerts:
        return ""

    lines = [
        f"OQ-005 Pipeline Alert ({len(alerts)} issues)",
        f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    for i, alert in enumerate(alerts, 1):
        lines.append(f"{i}. [{alert['alert_type']}] {alert['resource_id']}")
        lines.append(f"   business_date: {alert['business_date']}")
        lines.append(f"   warehouse_mode: {alert['warehouse_mode']}")
        lines.append(f"   status: {alert['status']}")
        if alert.get("error_summary"):
            error = alert["error_summary"][:200]
            if len(alert["error_summary"]) > 200:
                error += "..."
            lines.append(f"   error: {error}")
        lines.append(f"   time: {alert['started_at']} -> {alert['finished_at']}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="OQ-005 Pipeline Alert Checker")
    parser.add_argument("--project", default=PROJECT_ID, help=f"GCP project (default: {PROJECT_ID})")
    parser.add_argument("--lookback-minutes", type=int, default=60, help="Lookback window in minutes (default: 60)")
    parser.add_argument("--write-log", action="store_true", help="Write alerts to Cloud Logging")
    parser.add_argument("--notify", action="store_true", help="Send notification")
    parser.add_argument("--channel", default="stdout", choices=["stdout", "slack", "email"], help="Notification channel")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    alerts = check_alerts(args.project, args.lookback_minutes)

    if args.json:
        print(json.dumps(alerts, indent=2, ensure_ascii=False))
        return

    if not alerts:
        # 探针模式：无异常时输出 0
        if not args.notify:
            print("0")
        return

    # 写入 Cloud Logging
    if args.write_log:
        written = write_to_cloud_logging(args.project, alerts)
        print(f"Wrote {written} alerts to Cloud Logging", file=sys.stderr)

    # 输出/通知
    message = format_alert_message(alerts)
    if args.notify:
        if args.channel == "stdout":
            print(message)
        else:
            print(f"Channel {args.channel} not implemented, falling back to stdout:")
            print(message)
    else:
        print(message)


if __name__ == "__main__":
    main()
