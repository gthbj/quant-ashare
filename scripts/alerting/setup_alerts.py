#!/usr/bin/env python3
"""OQ-005 Pipeline 告警规则配置脚本。

基于 ashare_meta.v_alert_summary 视图创建 Cloud Monitoring 告警策略。

使用方式：
    python scripts/alerting/setup_alerts.py --project data-aquarium

前置条件：
    1. 已执行 sql/observability/01_pipeline_status_views.sql 创建视图
    2. 已启用 Cloud Monitoring API
    3. 已配置通知渠道（Email/Slack/PagerDuty）

注意：本脚本只创建告警规则，不配置通知渠道。通知渠道需在 Cloud Console 中手动配置。
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

try:
    from google.cloud import monitoring_v3
    from google.protobuf import duration_pb2, struct_pb2
except ImportError:
    print("请安装依赖：pip install google-cloud-monitoring")
    sys.exit(1)


PROJECT_ID = "data-aquarium"
REGION = "asia-east2"
DATASET = "ashare_meta"

# 告警规则定义
ALERT_POLICIES = [
    {
        "display_name": "OQ-005: Pipeline Run Failed",
        "description": "Composer DAG run 失败通知。覆盖 ods_daily_partition_readiness、窗口刷新、QA-WIN 等所有 task。",
        "condition_display_name": "pipeline_failure",
        "filter": (
            f'resource.type="bigquery_dataset" AND '
            f'metric.type="logging.googleapis.com/user/{PROJECT_ID}_pipeline_failure" AND '
            f'resource.label.dataset_id="{DATASET}"'
        ),
        "threshold_value": 0,
        "duration_seconds": 0,
        "auto_close_seconds": 86400,
        "severity": "ERROR",
    },
    {
        "display_name": "OQ-005: QA-WIN Assertion Failed",
        "description": "QA-WIN-* 断言失败通知。覆盖主键唯一、生命周期、估值覆盖等所有窗口 QA。",
        "condition_display_name": "qa_failure",
        "filter": (
            f'resource.type="bigquery_dataset" AND '
            f'metric.type="logging.googleapis.com/user/{PROJECT_ID}_qa_failure" AND '
            f'resource.label.dataset_id="{DATASET}"'
        ),
        "threshold_value": 0,
        "duration_seconds": 0,
        "auto_close_seconds": 86400,
        "severity": "ERROR",
    },
    {
        "display_name": "OQ-005: Cloud Run Ingestion Failed",
        "description": "Cloud Run ingestion execution 失败或 empty_return 通知。",
        "condition_display_name": "ingestion_failure",
        "filter": (
            f'resource.type="bigquery_dataset" AND '
            f'metric.type="logging.googleapis.com/user/{PROJECT_ID}_ingestion_failure" AND '
            f'resource.label.dataset_id="{DATASET}"'
        ),
        "threshold_value": 0,
        "duration_seconds": 0,
        "auto_close_seconds": 86400,
        "severity": "WARNING",
    },
    {
        "display_name": "OQ-005: ODS Daily Partition Readiness Failed",
        "description": "每日 ODS 分区就绪检查失败。通常意味着 ODS 数据未采集或采集失败。",
        "condition_display_name": "ods_readiness_failure",
        "filter": (
            f'resource.type="bigquery_dataset" AND '
            f'metric.type="logging.googleapis.com/user/{PROJECT_ID}_ods_readiness_failure" AND '
            f'resource.label.dataset_id="{DATASET}"'
        ),
        "threshold_value": 0,
        "duration_seconds": 0,
        "auto_close_seconds": 86400,
        "severity": "ERROR",
    },
]

# 自定义日志指标定义（基于 v_alert_summary 视图查询结果写入日志）
LOG_METRICS = [
    {
        "name": f"{PROJECT_ID}_pipeline_failure",
        "description": "Pipeline run failed in last 24 hours",
        "filter": (
            'resource.type="bigquery_resource" AND '
            'textPayload=~"pipeline_failure"'
        ),
    },
    {
        "name": f"{PROJECT_ID}_qa_failure",
        "description": "QA assertion failed in last 24 hours",
        "filter": (
            'resource.type="bigquery_resource" AND '
            'textPayload=~"task_failure.*qa"'
        ),
    },
    {
        "name": f"{PROJECT_ID}_ingestion_failure",
        "description": "Cloud Run ingestion failed in last 24 hours",
        "filter": (
            'resource.type="cloud_run_revision" AND '
            'textPayload=~"ingestion_failure"'
        ),
    },
    {
        "name": f"{PROJECT_ID}_ods_readiness_failure",
        "description": "ODS daily partition readiness failed",
        "filter": (
            'resource.type="bigquery_resource" AND '
            'textPayload=~"task_failure.*readiness"'
        ),
    },
]


def create_log_metric(
    client: monitoring_v3.MetricServiceClient,
    project_id: str,
    metric_def: dict[str, Any],
) -> None:
    """创建自定义日志指标。"""
    project_name = f"projects/{project_id}"

    metric_descriptor = monitoring_v3.MetricDescriptor()
    metric_descriptor.type = f"logging.googleapis.com/user/{metric_def['name']}"
    metric_descriptor.metric_kind = monitoring_v3.MetricDescriptor.MetricKind.GAUGE
    metric_descriptor.value_type = monitoring_v3.MetricDescriptor.ValueType.INT64
    metric_descriptor.description = metric_def["description"]
    metric_descriptor.display_name = metric_def["name"]

    label_descriptor = monitoring_v3.LabelDescriptor()
    label_descriptor.key = "dataset_id"
    label_descriptor.value_type = monitoring_v3.LabelDescriptor.ValueType.STRING
    label_descriptor.description = "BigQuery dataset ID"
    metric_descriptor.labels.append(label_descriptor)

    try:
        client.create_metric_descriptor(
            name=project_name,
            metric_descriptor=metric_descriptor,
        )
        print(f"  ✓ 创建日志指标：{metric_def['name']}")
    except Exception as e:
        if "ALREADY_EXISTS" in str(e):
            print(f"  - 日志指标已存在：{metric_def['name']}")
        else:
            print(f"  ✗ 创建日志指标失败：{metric_def['name']}：{e}")


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

    # 条件
    condition = monitoring_v3.AlertPolicy.Condition()
    condition.display_name = policy_def["condition_display_name"]

    condition_filter = policy_def["filter"]

    threshold = monitoring_v3.AlertPolicy.Condition.MetricThreshold()
    threshold.filter = condition_filter
    threshold.comparison = (
        monitoring_v3.AlertPolicy.Condition.ComparisonType.COMPARISON_GT
    )
    threshold.threshold_value = policy_def["threshold_value"]

    if policy_def["duration_seconds"] > 0:
        threshold.duration = duration_pb2.Duration(
            seconds=policy_def["duration_seconds"]
        )

    aggregations = monitoring_v3.Aggregation()
    aggregations.alignment_period.seconds = 300
    aggregations.per_series_aligner = (
        monitoring_v3.Aggregation.Aligner.ALIGN_COUNT
    )
    aggregations.cross_series_reducer = (
        monitoring_v3.Aggregation.Reducer.REDUCE_SUM
    )
    threshold.aggregations.append(aggregations)

    condition.metric_threshold = threshold
    policy.conditions.append(condition)

    # 通知渠道
    if notification_channels:
        for channel in notification_channels:
            policy.notification_channels.append(channel)

    # 策略选项
    policy.severity = getattr(
        monitoring_v3.AlertPolicy.Severity,
        policy_def.get("severity", "ERROR"),
    )

    alert_strategy = monitoring_v3.AlertPolicy.AlertStrategy()
    alert_strategy.auto_close.seconds = policy_def.get(
        "auto_close_seconds", 86400
    )
    policy.alert_strategy = alert_strategy

    try:
        created = client.create_alert_policy(
            name=project_name,
            alert_policy=policy,
        )
        print(f"  ✓ 创建告警策略：{policy_def['display_name']}")
        print(f"    ID：{created.name}")
    except Exception as e:
        if "ALREADY_EXISTS" in str(e):
            print(f"  - 告警策略已存在：{policy_def['display_name']}")
        else:
            print(f"  ✗ 创建告警策略失败：{policy_def['display_name']}：{e}")


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
        print(f"  ⚠ 无法列出通知渠道：{e}")

    return channels


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OQ-005 Pipeline 告警规则配置"
    )
    parser.add_argument(
        "--project",
        default=PROJECT_ID,
        help=f"GCP 项目 ID（默认：{PROJECT_ID}）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印配置，不实际创建",
    )
    parser.add_argument(
        "--notification-channels",
        nargs="*",
        help="通知渠道名称列表（可选）",
    )
    args = parser.parse_args()

    print(f"OQ-005 Pipeline 告警规则配置")
    print(f"项目：{args.project}")
    print(f"模式：{'dry-run' if args.dry_run else 'apply'}")
    print()

    if args.dry_run:
        print("=== 告警规则 ===")
        for policy in ALERT_POLICIES:
            print(f"- {policy['display_name']}")
            print(f"  描述：{policy['description']}")
            print(f"  严重程度：{policy.get('severity', 'ERROR')}")
            print()
        print("=== 日志指标 ===")
        for metric in LOG_METRICS:
            print(f"- {metric['name']}")
            print(f"  描述：{metric['description']}")
            print()
        return

    # 创建客户端
    metric_client = monitoring_v3.MetricServiceClient()
    alert_client = monitoring_v3.AlertPolicyServiceClient()
    channel_client = monitoring_v3.NotificationChannelServiceClient()

    # 列出通知渠道
    print("=== 通知渠道 ===")
    channels = list_notification_channels(channel_client, args.project)
    if channels:
        for ch in channels:
            print(f"  - {ch['display_name']} ({ch['type']}): {ch['name']}")
    else:
        print("  ⚠ 未配置通知渠道。请在 Cloud Console 中配置后重新运行。")
    print()

    # 创建日志指标
    print("=== 创建日志指标 ===")
    for metric in LOG_METRICS:
        create_log_metric(metric_client, args.project, metric)
    print()

    # 创建告警策略
    print("=== 创建告警策略 ===")
    notification_channels = args.notification_channels or []
    for policy in ALERT_POLICIES:
        create_alert_policy(
            alert_client,
            args.project,
            policy,
            notification_channels,
        )
    print()

    print("=== 完成 ===")
    print("请在 Cloud Console > Monitoring > Alerting 中验证告警规则。")
    print("如需配置通知渠道，请访问：")
    print(f"  https://console.cloud.google.com/monitoring/alerting/notification?project={args.project}")


if __name__ == "__main__":
    main()
