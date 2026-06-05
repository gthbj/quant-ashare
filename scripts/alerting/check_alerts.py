#!/usr/bin/env python3
"""OQ-005 Pipeline 告警查询脚本。

定期查询 v_alert_summary 视图，检测到异常时发送通知。

使用方式：
    # 查询最近 1 小时异常
    python scripts/alerting/check_alerts.py --lookback-hours 1

    # 查询并发送通知（需配置通知渠道）
    python scripts/alerting/check_alerts.py --notify

前置条件：
    1. 已执行 sql/observability/01_pipeline_status_views.sql 创建视图
    2. 已配置 ADC：gcloud auth application-default login
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


PROJECT_ID = "data-aquarium"
DATASET = "ashare_meta"
REGION = "asia-east2"


def check_alerts(
    project_id: str,
    lookback_hours: int = 1,
) -> list[dict[str, Any]]:
    """查询最近 N 小时的异常。"""
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
WHERE finished_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {lookback_hours} HOUR)
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
        print(f"查询失败：{e}")
        return []

    return results


def format_alert_message(alerts: list[dict[str, Any]]) -> str:
    """格式化告警消息。"""
    if not alerts:
        return ""

    lines = [
        f"🚨 OQ-005 Pipeline 告警 ({len(alerts)} 条异常)",
        f"时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    for i, alert in enumerate(alerts, 1):
        lines.append(f"{i}. [{alert['alert_type']}] {alert['resource_id']}")
        lines.append(f"   业务日期：{alert['business_date']}")
        lines.append(f"   模式：{alert['warehouse_mode']}")
        lines.append(f"   状态：{alert['status']}")
        if alert.get("error_summary"):
            # 截断错误摘要
            error = alert["error_summary"][:200]
            if len(alert["error_summary"]) > 200:
                error += "..."
            lines.append(f"   错误：{error}")
        lines.append(f"   时间：{alert['started_at']} → {alert['finished_at']}")
        lines.append("")

    lines.append("详情请查看：")
    lines.append(f"  https://console.cloud.google.com/bigquery?project={PROJECT_ID}")
    lines.append(f"  查询：SELECT * FROM `{PROJECT_ID}.{DATASET}.v_alert_summary`")

    return "\n".join(lines)


def send_notification(message: str, channel: str = "stdout") -> None:
    """发送通知。"""
    if channel == "stdout":
        print(message)
    elif channel == "slack":
        # TODO: 集成 Slack webhook
        print("Slack 通知尚未实现，请手动配置。")
        print(message)
    elif channel == "email":
        # TODO: 集成 Cloud Functions + SendGrid
        print("Email 通知尚未实现，请手动配置。")
        print(message)
    else:
        print(f"未知通知渠道：{channel}")
        print(message)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OQ-005 Pipeline 告警查询"
    )
    parser.add_argument(
        "--project",
        default=PROJECT_ID,
        help=f"GCP 项目 ID（默认：{PROJECT_ID}）",
    )
    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=1,
        help="查询最近 N 小时的异常（默认：1）",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="发送通知（默认只打印）",
    )
    parser.add_argument(
        "--channel",
        default="stdout",
        choices=["stdout", "slack", "email"],
        help="通知渠道（默认：stdout）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 格式",
    )
    args = parser.parse_args()

    # 查询异常
    alerts = check_alerts(args.project, args.lookback_hours)

    if args.json:
        print(json.dumps(alerts, indent=2, ensure_ascii=False))
        return

    if not alerts:
        print(f"✅ 最近 {args.lookback_hours} 小时无异常。")
        return

    # 格式化消息
    message = format_alert_message(alerts)

    # 发送通知
    if args.notify:
        send_notification(message, args.channel)
    else:
        print(message)
        print()
        print("提示：使用 --notify 参数发送通知。")


if __name__ == "__main__":
    main()
