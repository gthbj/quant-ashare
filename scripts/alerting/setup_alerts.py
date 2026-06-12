#!/usr/bin/env python3
"""Ashare Pipeline 告警规则配置脚本。

告警链路：
  1. Cloud Scheduler 触发 Workflows `ashare_pipeline_alert_checker`
  2. Workflow 调用 ashare-pipeline-control /v1/tasks/alert-check
  3. check_alerts.py 查询 v_alert_summary 视图
  4. 将异常与 checker heartbeat 写入 Cloud Logging（JSON payload）
  5. Cloud Logging 日志指标匹配这些条目
  6. Cloud Monitoring 告警策略订阅日志指标，按阈值或 heartbeat 缺失触发通知

使用方式：
    # dry-run 查看配置
    python scripts/alerting/setup_alerts.py --dry-run

    # 创建日志指标 + 告警策略
    python scripts/alerting/setup_alerts.py

    # 指定通知渠道
    python scripts/alerting/setup_alerts.py --notification-channels "projects/xxx/notificationChannels/yyy"

前置条件：
    1. 已执行 sql/observability/01_pipeline_status_views.sql 创建视图
    2. 已启用 Cloud Logging API + Cloud Monitoring API
    3. ashare-pipeline-alert-checker Scheduler job 已部署（最多每小时 1 次）
    4. 已配置通知渠道（Email/Slack/PagerDuty）
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

try:
    from google.api_core.exceptions import AlreadyExists
    from google.cloud.logging_v2.services.metrics_service_v2 import MetricsServiceV2Client
    from google.cloud.logging_v2.types import LogMetric
except ImportError:
    print("请安装依赖：pip install google-cloud-logging")
    sys.exit(1)

try:
    from google.cloud import monitoring_v3
    from google.protobuf import duration_pb2
    from google.protobuf import field_mask_pb2
except ImportError:
    print("请安装依赖：pip install google-cloud-monitoring")
    sys.exit(1)


PROJECT_ID = "data-aquarium"
POLICY_LABEL_KEY = "ashare_pipeline_policy"

# 日志指标定义
# 用 Cloud Logging Log Metric API 创建，name 即为 metric 的标识。
# 在 Cloud Monitoring 中，metric type 为 logging.googleapis.com/user/{name}
LOG_METRICS = [
    {
        "name": "ashare_pipeline_failure",
        "description": "Pipeline workflow run failed",
        "filter": 'jsonPayload.alert_type="pipeline_failure"',
    },
    {
        "name": "ashare_pipeline_task_failure",
        "description": "Pipeline task failed (QA, readiness, windowed transform, etc.)",
        "filter": 'jsonPayload.alert_type="task_failure"',
    },
    {
        "name": "ashare_pipeline_ingestion_failed",
        "description": "Cloud Run ingestion execution failed (not empty_return)",
        "filter": 'jsonPayload.alert_type="ingestion_failed"',
    },
    {
        "name": "ashare_pipeline_ingestion_meta_missing",
        "description": "Live ODS ingestion task succeeded but ingestion meta rows are missing",
        "filter": 'jsonPayload.alert_type="ingestion_meta_missing"',
    },
    {
        "name": "ashare_pipeline_warehouse_refresh_missing",
        "description": "ODS ingestion succeeded but linked warehouse window refresh is missing",
        "filter": 'jsonPayload.alert_type="warehouse_refresh_missing"',
    },
    {
        "name": "ashare_pipeline_alert_checker_heartbeat",
        "description": "Ashare pipeline alert checker heartbeat for liveness monitoring",
        "filter": (
            'jsonPayload.alert_type="alert_checker_heartbeat" '
            'AND jsonPayload.resource_id="ashare_pipeline_alert_checker" '
            'AND jsonPayload.status="succeeded"'
        ),
    },
]

# 告警策略定义
# metric_type = logging.googleapis.com/user/{name}，与日志指标对应
ALERT_POLICIES = [
    {
        "policy_key": "pipeline_failure",
        "display_name": "Ashare Pipeline: Pipeline Run Failed",
        "description": (
            "Pipeline workflow run 失败。\n\n"
            "覆盖：ODS readiness、窗口刷新、QA-WIN 等 task。\n\n"
            "Runbook：docs/Pipeline-补跑与故障恢复-Runbook.md"
        ),
        "condition_display_name": "pipeline_failure",
        "condition_type": "threshold",
        "log_metric_name": "ashare_pipeline_failure",
        "threshold_value": 0,
        "duration_seconds": 0,
        "severity": "ERROR",
    },
    {
        "policy_key": "task_failure",
        "display_name": "Ashare Pipeline: Task Failed",
        "legacy_display_names": [
            "Ashare Pipeline: Task Failed (QA / Readiness / Transform)",
        ],
        "description": (
            "Pipeline task 失败。\n\n"
            "常见类型：QA-WIN-* 断言、ods_daily_partition_readiness、"
            "windowed_transform.stock_dwd_dws_window。\n\n"
            "Runbook：docs/Pipeline-补跑与故障恢复-Runbook.md"
        ),
        "condition_display_name": "task_failure",
        "condition_type": "threshold",
        "log_metric_name": "ashare_pipeline_task_failure",
        "threshold_value": 0,
        "duration_seconds": 0,
        "severity": "ERROR",
    },
    {
        "policy_key": "ingestion_failed",
        "display_name": "Ashare Pipeline: Ingestion Failed",
        "legacy_display_names": [
            "Ashare Pipeline: Cloud Run Ingestion Failed",
        ],
        "description": (
            "Cloud Run ingestion execution 失败。\n\n"
            "注意：empty_return 不触发此告警，需按 endpoint/date 判断是否正常。\n\n"
            "Runbook：docs/Pipeline-补跑与故障恢复-Runbook.md"
        ),
        "condition_display_name": "ingestion_failed",
        "condition_type": "threshold",
        "log_metric_name": "ashare_pipeline_ingestion_failed",
        "threshold_value": 0,
        "duration_seconds": 0,
        "severity": "WARNING",
    },
    {
        "policy_key": "warehouse_refresh_missing",
        "display_name": "Ashare Pipeline: Warehouse Refresh Missing",
        "description": (
            "ODS ingestion 已成功，但 60 分钟内没有对应 "
            "`ashare_warehouse_window_refresh` run 记录。\n\n"
            "检查 `ashare_meta.v_pipeline_refresh_missing`，确认是否为 child workflow 触发失败、"
            "Scheduler / Workflows 调度异常或状态回写失败。\n\n"
            "Runbook：docs/Pipeline-补跑与故障恢复-Runbook.md"
        ),
        "condition_display_name": "warehouse_refresh_missing",
        "condition_type": "threshold",
        "log_metric_name": "ashare_pipeline_warehouse_refresh_missing",
        "threshold_value": 0,
        "duration_seconds": 0,
        "severity": "ERROR",
    },
    {
        "policy_key": "ingestion_meta_missing",
        "display_name": "Ashare Pipeline: Ingestion Meta Missing",
        "description": (
            "Live ODS ingestion task 已成功，但对应 business_date 没有 "
            "`ashare_meta.ingestion_run` 行。\n\n"
            "这通常表示采集镜像 stale、meta 写入路径损坏，或 ingestion task 成功状态"
            "与实际 live 写入链路脱节。先查 `ashare_meta.v_ingestion_meta_missing`，"
            "再核对 Cloud Run execution 使用的镜像 digest 与 ingestion logs。\n\n"
            "Runbook：docs/Pipeline-补跑与故障恢复-Runbook.md"
        ),
        "condition_display_name": "ingestion_meta_missing",
        "condition_type": "threshold",
        "log_metric_name": "ashare_pipeline_ingestion_meta_missing",
        "threshold_value": 0,
        "duration_seconds": 0,
        "severity": "ERROR",
    },
    {
        "policy_key": "alert_checker_heartbeat_missing",
        "display_name": "Ashare Pipeline: Alert Checker Heartbeat Missing",
        "description": (
            "告警 checker 自身心跳缺失。\n\n"
            "`ashare_pipeline_alert_checker` 每小时运行并写入 heartbeat；"
            "若 120 分钟内没有 heartbeat，说明 checker Scheduler / Workflow 可能失败、被 pause、"
            "control service 调用异常或日志写入异常。\n\n"
            "Runbook：docs/Pipeline-补跑与故障恢复-Runbook.md"
        ),
        "condition_display_name": "alert_checker_heartbeat_absent",
        "condition_type": "absence",
        "log_metric_name": "ashare_pipeline_alert_checker_heartbeat",
        "duration_seconds": 7200,
        "severity": "ERROR",
    },
]


def policy_match_names(policy_def: dict[str, Any]) -> set[str]:
    """Return current and legacy display names for migration-safe matching."""
    names = {policy_def["display_name"]}
    names.update(policy_def.get("legacy_display_names", []))
    return names


def policy_matches(existing: monitoring_v3.AlertPolicy, policy_def: dict[str, Any]) -> bool:
    """Match an existing policy by stable label, falling back to legacy names."""
    if existing.user_labels.get(POLICY_LABEL_KEY) == policy_def["policy_key"]:
        return True
    if policy_def["policy_key"] in set(existing.user_labels.values()):
        return True
    return existing.display_name in policy_match_names(policy_def)


def build_alert_policy(
    policy_def: dict[str, Any],
    notification_channels: list[str] | None = None,
) -> monitoring_v3.AlertPolicy:
    """Build the desired Cloud Monitoring alert policy proto."""
    # metric type = logging.googleapis.com/user/{log_metric_name}
    metric_type = f"logging.googleapis.com/user/{policy_def['log_metric_name']}"

    policy = monitoring_v3.AlertPolicy()
    policy.display_name = policy_def["display_name"]
    policy.documentation.content = policy_def["description"]
    policy.documentation.mime_type = "text/markdown"
    policy.combiner = monitoring_v3.AlertPolicy.ConditionCombinerType.OR
    policy.user_labels[POLICY_LABEL_KEY] = policy_def["policy_key"]

    condition = monitoring_v3.AlertPolicy.Condition()
    condition.display_name = policy_def["condition_display_name"]

    aggregation = monitoring_v3.Aggregation()
    aggregation.alignment_period = duration_pb2.Duration(seconds=300)
    aggregation.per_series_aligner = monitoring_v3.Aggregation.Aligner.ALIGN_COUNT
    aggregation.cross_series_reducer = monitoring_v3.Aggregation.Reducer.REDUCE_SUM

    condition_type = policy_def.get("condition_type", "threshold")
    if condition_type == "absence":
        absence = monitoring_v3.AlertPolicy.Condition.MetricAbsence()
        absence.filter = f'resource.type="global" AND metric.type="{metric_type}"'
        absence.duration = duration_pb2.Duration(seconds=policy_def["duration_seconds"])
        absence.aggregations.append(aggregation)
        condition.condition_absent = absence
    else:
        threshold = monitoring_v3.AlertPolicy.Condition.MetricThreshold()
        threshold.filter = f'resource.type="global" AND metric.type="{metric_type}"'
        threshold.comparison = monitoring_v3.ComparisonType.COMPARISON_GT
        threshold.threshold_value = policy_def["threshold_value"]
        threshold.duration = duration_pb2.Duration(seconds=policy_def["duration_seconds"])

        threshold.aggregations.append(aggregation)
        condition.condition_threshold = threshold

    policy.conditions.append(condition)

    if notification_channels:
        for channel in notification_channels:
            policy.notification_channels.append(channel)

    policy.severity = getattr(
        monitoring_v3.AlertPolicy.Severity,
        policy_def.get("severity", "ERROR"),
    )

    alert_strategy = monitoring_v3.AlertPolicy.AlertStrategy()
    alert_strategy.auto_close = duration_pb2.Duration(seconds=86400)
    policy.alert_strategy = alert_strategy

    return policy


def create_log_metric(
    project_id: str,
    metric_def: dict[str, Any],
) -> None:
    """用 Cloud Logging API 创建日志指标。"""
    client = MetricsServiceV2Client()
    parent = f"projects/{project_id}"

    metric = LogMetric(
        name=metric_def["name"],
        description=metric_def["description"],
        filter=metric_def["filter"],
    )

    try:
        client.create_log_metric(parent=parent, metric=metric)
        print(f"  + 创建日志指标：{metric_def['name']}")
    except AlreadyExists:
        print(f"  = 日志指标已存在：{metric_def['name']}")
    except Exception as e:
        print(f"  x 创建日志指标失败：{metric_def['name']}：{e}")
        raise


def create_alert_policy(
    project_id: str,
    policy_def: dict[str, Any],
    notification_channels: list[str] | None = None,
) -> None:
    """用 Cloud Monitoring API 创建告警策略。"""
    client = monitoring_v3.AlertPolicyServiceClient()
    project_name = f"projects/{project_id}"

    matches = [
        existing
        for existing in client.list_alert_policies(name=project_name)
        if policy_matches(existing, policy_def)
    ]
    if len(matches) > 1:
        names = ", ".join(f"{p.display_name} ({p.name})" for p in matches)
        raise RuntimeError(
            f"检测到重复 Ashare pipeline 告警策略：{policy_def['policy_key']} -> {names}。"
            "请先手工清理重复策略，再重新执行。"
        )

    policy = build_alert_policy(policy_def, notification_channels)

    try:
        if matches:
            existing = matches[0]
            policy.name = existing.name
            if not notification_channels:
                policy.notification_channels.extend(existing.notification_channels)
            update_mask = field_mask_pb2.FieldMask(paths=[
                "display_name",
                "documentation",
                "combiner",
                "conditions",
                "notification_channels",
                "severity",
                "alert_strategy",
                "user_labels",
            ])
            updated = client.update_alert_policy(update_mask=update_mask, alert_policy=policy)
            if existing.display_name != policy_def["display_name"]:
                print(
                    f"  ~ 迁移并更新告警策略：{existing.display_name} -> "
                    f"{policy_def['display_name']} ({updated.name})"
                )
            else:
                print(f"  = 告警策略已存在并已对齐：{policy_def['display_name']} ({updated.name})")
            return

        created = client.create_alert_policy(name=project_name, alert_policy=policy)
        print(f"  + 创建告警策略：{policy_def['display_name']}")
        print(f"    ID：{created.name}")
    except Exception as e:
        if "ALREADY_EXISTS" in str(e):
            print(f"  = 告警策略已存在：{policy_def['display_name']}")
        else:
            print(f"  x 创建告警策略失败：{policy_def['display_name']}：{e}")
            raise


def list_notification_channels(project_id: str) -> list[dict[str, str]]:
    """列出已配置的通知渠道。"""
    client = monitoring_v3.NotificationChannelServiceClient()
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
    parser = argparse.ArgumentParser(description="Ashare Pipeline 告警规则配置")
    parser.add_argument("--project", default=PROJECT_ID, help=f"GCP project (default: {PROJECT_ID})")
    parser.add_argument("--dry-run", action="store_true", help="只打印配置，不实际创建")
    parser.add_argument("--notification-channels", nargs="*", help="通知渠道 resource name 列表")
    args = parser.parse_args()

    print(f"Ashare Pipeline 告警规则配置")
    print(f"项目：{args.project}")
    print(f"模式：{'dry-run' if args.dry_run else 'apply'}")
    print()

    if args.dry_run:
        print("=== 日志指标 (Cloud Logging API) ===")
        for m in LOG_METRICS:
            print(f"  - {m['name']}: {m['description']}")
            print(f"    filter: {m['filter']}")
        print()
        print("=== 告警策略 (Cloud Monitoring API) ===")
        for p in ALERT_POLICIES:
            metric_type = f"logging.googleapis.com/user/{p['log_metric_name']}"
            print(f"  - {p['display_name']} [{p.get('severity', 'ERROR')}]")
            print(f"    metric: {metric_type}")
            print(f"    description: {p['description'].splitlines()[0]}")
        print()
        print("=== 告警链路 ===")
        print("  ashare_pipeline_alert_checker -> check_alerts.py --write-log --write-heartbeat")
        print("    -> Cloud Logging (jsonPayload)")
        print("    -> log metric (ashare_pipeline_* + checker heartbeat)")
        print("    -> Cloud Monitoring alert policy")
        print("    -> notification channel")
        return

    print("=== 通知渠道 ===")
    channels = list_notification_channels(args.project)
    if channels:
        for ch in channels:
            print(f"  - {ch['display_name']} ({ch['type']}): {ch['name']}")
    else:
        print("  ! 未配置通知渠道。请在 Cloud Console 中配置后重新运行。")
    print()

    print("=== 创建日志指标 (Cloud Logging API) ===")
    for m in LOG_METRICS:
        create_log_metric(args.project, m)
    print()

    print("=== 创建告警策略 (Cloud Monitoring API) ===")
    notification_channels = args.notification_channels or []
    for p in ALERT_POLICIES:
        create_alert_policy(args.project, p, notification_channels)
    print()

    print("=== 完成 ===")
    print()
    print("下一步：")
    print("  1. 部署 ashare_pipeline_alert_checker 当前定时入口（最多每小时 1 次）")
    print("  2. 验证：https://console.cloud.google.com/monitoring/alerting?project=" + args.project)
    print("  3. 日志指标：https://console.cloud.google.com/logs/metrics?project=" + args.project)


if __name__ == "__main__":
    main()
