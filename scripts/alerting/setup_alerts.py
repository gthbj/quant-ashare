#!/usr/bin/env python3
"""OQ-005 Pipeline 告警规则配置脚本。

告警链路：
  1. check_alerts.py 由 Cloud Scheduler 定时调用
  2. 查询 v_alert_summary 视图
  3. 将异常写入 Cloud Logging（stdout JSON，被 ops-agent 采集）
  4. Cloud Monitoring 日志指标匹配这些条目
  5. 告警策略在指标 > 0 时触发通知

使用方式：
    # dry-run 查看配置
    python scripts/alerting/setup_alerts.py --dry-run

    # 创建日志指标 + 告警策略
    python scripts/alerting/setup_alerts.py

    # 指定通知渠道
    python scripts/alerting/setup_alerts.py --notification-channels "projects/xxx/notificationChannels/yyy"

前置条件：
    1. 已执行 sql/observability/01_pipeline_status_views.sql 创建视图
    2. 已启用 Cloud Monitoring API
    3. check_alerts.py 已部署为 Cloud Scheduler job（每 5-10 分钟执行）
    4. 已配置通知渠道（Email/Slack/PagerDuty）
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

try:
    from google.cloud import monitoring_v3
    from google.protobuf import duration_pb2
except ImportError:
    print("请安装依赖：pip install google-cloud-monitoring")
    sys.exit(1)


PROJECT_ID = "data-aquarium"
DATASET = "ashare_meta"

# 日志指标定义
# 这些指标匹配 check_alerts.py 写入 Cloud Logging 的 JSON 条目。
# check_alerts.py 写入格式：{"severity": "ERROR", "alert_type": "...", ...}
LOG_METRICS = [
    {
        "name": "oq005_pipeline_failure",
        "description": "Pipeline DAG run failed",
        "filter": (
            'resource.type="global" AND '
            'jsonPayload.alert_type="pipeline_failure"'
        ),
    },
    {
        "name": "oq005_task_failure",
        "description": "Pipeline task failed (QA, readiness, windowed transform, etc.)",
        "filter": (
            'resource.type="global" AND '
            'jsonPayload.alert_type="task_failure"'
        ),
    },
    {
        "name": "oq005_ingestion_failed",
        "description": "Cloud Run ingestion execution failed",
        "filter": (
            'resource.type="global" AND '
            'jsonPayload.alert_type="ingestion_failed"'
        ),
    },
]

# 告警策略定义
ALERT_POLICIES = [
    {
        "display_name": "OQ-005: Pipeline Run Failed",
        "description": (
            "Composer DAG run 失败。\n\n"
            "覆盖：ods_daily_partition_readiness、窗口刷新、QA-WIN 等所有 task。\n\n"
            "Runbook：docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md"
        ),
        "condition_display_name": "pipeline_failure",
        "metric_type": f"logging.googleapis.com/user/{PROJECT_ID}_oq005_pipeline_failure",
        "threshold_value": 0,
        "duration_seconds": 0,
        "severity": "ERROR",
    },
    {
        "display_name": "OQ-005: Task Failed (QA / Readiness / Transform)",
        "description": (
            "Pipeline task 失败。\n\n"
            "常见类型：QA-WIN-* 断言、ods_daily_partition_readiness、"
            "windowed_transform.stock_dwd_dws_window。\n\n"
            "Runbook：docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md"
        ),
        "condition_display_name": "task_failure",
        "metric_type": f"logging.googleapis.com/user/{PROJECT_ID}_oq005_task_failure",
        "threshold_value": 0,
        "duration_seconds": 0,
        "severity": "ERROR",
    },
    {
        "display_name": "OQ-005: Cloud Run Ingestion Failed",
        "description": (
            "Cloud Run ingestion execution 失败。\n\n"
            "注意：empty_return 不触发此告警，需按 endpoint/date 判断是否正常。\n\n"
            "Runbook：docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md"
        ),
        "condition_display_name": "ingestion_failed",
        "metric_type": f"logging.googleapis.com/user/{PROJECT_ID}_oq005_ingestion_failed",
        "threshold_value": 0,
        "duration_seconds": 0,
        "severity": "WARNING",
    },
]


def create_log_metric(
    client: monitoring_v3.MetricServiceClient,
    project_id: str,
    metric_def: dict[str, Any],
) -> None:
    """创建自定义日志指标。"""
    project_name = f"projects/{project_id}"

    descriptor = monitoring_v3.MetricDescriptor()
    descriptor.type = f"logging.googleapis.com/user/{metric_def['name']}"
    descriptor.metric_kind = monitoring_v3.MetricDescriptor.MetricKind.GAUGE
    descriptor.value_type = monitoring_v3.MetricDescriptor.ValueType.INT64
    descriptor.description = metric_def["description"]
    descriptor.display_name = metric_def["name"]

    try:
        client.create_metric_descriptor(
            name=project_name,
            metric_descriptor=descriptor,
        )
        print(f"  + 创建日志指标：{metric_def['name']}")
    except Exception as e:
        if "ALREADY_EXISTS" in str(e):
            print(f"  = 日志指标已存在：{metric_def['name']}")
        else:
            print(f"  x 创建日志指标失败：{metric_def['name']}：{e}")
            raise


def create_alert_policy(
    client: monitoring_v3.AlertPolicyServiceClient,
    project_id: str,
    policy_def: dict[str, Any],
    notification_channels: list[str] | None = None,
) -> None:
    """创建告警策略。"""
    project_name = f"projects/{project_id}"

    policy = monitoring_v3.AlertPolicy()
    policy.display_name = policy_def["display_name"]
    policy.documentation.content = policy_def["description"]
    policy.documentation.mime_type = "text/markdown"

    condition = monitoring_v3.AlertPolicy.Condition()
    condition.display_name = policy_def["condition_display_name"]

    threshold = monitoring_v3.AlertPolicy.Condition.MetricThreshold()
    threshold.filter = f'resource.type="global" AND metric.type="{policy_def["metric_type"]}"'
    threshold.comparison = monitoring_v3.AlertPolicy.Condition.ComparisonType.COMPARISON_GT
    threshold.threshold_value = policy_def["threshold_value"]

    if policy_def["duration_seconds"] > 0:
        threshold.duration = duration_pb2.Duration(seconds=policy_def["duration_seconds"])

    aggregation = monitoring_v3.Aggregation()
    aggregation.alignment_period.seconds = 300
    aggregation.per_series_aligner = monitoring_v3.Aggregation.Aligner.ALIGN_COUNT
    aggregation.cross_series_reducer = monitoring_v3.Aggregation.Reducer.REDUCE_SUM
    threshold.aggregations.append(aggregation)

    condition.metric_threshold = threshold
    policy.conditions.append(condition)

    if notification_channels:
        for channel in notification_channels:
            policy.notification_channels.append(channel)

    policy.severity = getattr(
        monitoring_v3.AlertPolicy.Severity,
        policy_def.get("severity", "ERROR"),
    )

    alert_strategy = monitoring_v3.AlertPolicy.AlertStrategy()
    alert_strategy.auto_close.seconds = 86400
    policy.alert_strategy = alert_strategy

    try:
        created = client.create_alert_policy(name=project_name, alert_policy=policy)
        print(f"  + 创建告警策略：{policy_def['display_name']}")
        print(f"    ID：{created.name}")
    except Exception as e:
        if "ALREADY_EXISTS" in str(e):
            print(f"  = 告警策略已存在：{policy_def['display_name']}")
        else:
            print(f"  x 创建告警策略失败：{policy_def['display_name']}：{e}")
            raise


def list_notification_channels(
    client: monitoring_v3.NotificationChannelServiceClient,
    project_id: str,
) -> list[dict[str, str]]:
    """列出已配置的通知渠道。"""
    project_name = f"projects/{project_id}"
    channels = []
    try:
        for channel in client.list_notification_channels(name=project_name):
            channels.append({
                "name": channel.name,
                "display_name": channel.display_name,
                "type": channel.type_,
            })
    except Exception as e:
        print(f"  ! 无法列出通知渠道：{e}")
    return channels


def main() -> None:
    parser = argparse.ArgumentParser(description="OQ-005 Pipeline 告警规则配置")
    parser.add_argument("--project", default=PROJECT_ID, help=f"GCP 项目 ID（默认：{PROJECT_ID}）")
    parser.add_argument("--dry-run", action="store_true", help="只打印配置，不实际创建")
    parser.add_argument("--notification-channels", nargs="*", help="通知渠道 resource name 列表")
    args = parser.parse_args()

    print(f"OQ-005 Pipeline 告警规则配置")
    print(f"项目：{args.project}")
    print(f"模式：{'dry-run' if args.dry_run else 'apply'}")
    print()

    if args.dry_run:
        print("=== 日志指标 ===")
        for m in LOG_METRICS:
            print(f"  - {m['name']}: {m['description']}")
            print(f"    filter: {m['filter']}")
        print()
        print("=== 告警策略 ===")
        for p in ALERT_POLICIES:
            print(f"  - {p['display_name']} [{p.get('severity', 'ERROR')}]")
            print(f"    {p['description'].splitlines()[0]}")
        print()
        print("=== 前置条件 ===")
        print("  1. check_alerts.py 已部署为 Cloud Scheduler job（每 5-10 分钟）")
        print("  2. check_alerts.py 将异常写入 Cloud Logging（JSON 格式）")
        print("  3. 日志指标匹配这些 JSON 条目")
        print("  4. 告警策略在指标 > 0 时触发通知")
        return

    metric_client = monitoring_v3.MetricServiceClient()
    alert_client = monitoring_v3.AlertPolicyServiceClient()
    channel_client = monitoring_v3.NotificationChannelServiceClient()

    print("=== 通知渠道 ===")
    channels = list_notification_channels(channel_client, args.project)
    if channels:
        for ch in channels:
            print(f"  - {ch['display_name']} ({ch['type']}): {ch['name']}")
    else:
        print("  ! 未配置通知渠道。请在 Cloud Console 中配置后重新运行。")
    print()

    print("=== 创建日志指标 ===")
    for m in LOG_METRICS:
        create_log_metric(metric_client, args.project, m)
    print()

    print("=== 创建告警策略 ===")
    notification_channels = args.notification_channels or []
    for p in ALERT_POLICIES:
        create_alert_policy(alert_client, args.project, p, notification_channels)
    print()

    print("=== 完成 ===")
    print()
    print("下一步：")
    print("  1. 部署 check_alerts.py 为 Cloud Scheduler job：")
    print(f"     gcloud scheduler jobs create http oq005-alert-check \\")
    print(f"       --schedule='*/5 * * * *' \\")
    print(f"       --uri='https://<cloud-run-url>/check-alerts' \\")
    print(f"       --http-method=POST")
    print("  2. 或在本机 cron 中运行：")
    print("     */5 * * * * python /path/to/check_alerts.py --write-log")
    print()
    print("验证：")
    print(f"  https://console.cloud.google.com/monitoring/alerting?project={args.project}")


if __name__ == "__main__":
    main()
