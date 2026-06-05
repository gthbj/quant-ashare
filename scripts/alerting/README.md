# OQ-005 Pipeline 告警与观测

> 文档维护：opencode（最近更新 2026-06-05）

## 概述

本目录包含 OQ-005 日常调度链路的告警规则、观测视图和补跑 runbook。

## 告警链路

```
check_alerts.py (Cloud Scheduler, */5 * * * *)
    |
    v
v_alert_summary (BigQuery view)
    |
    v
Cloud Logging (JSON payload, severity=ERROR)
    |
    v
Cloud Monitoring (log-based metric)
    |
    v
Alert Policy --> Notification Channel (Email/Slack/PagerDuty)
```

关键点：
- `check_alerts.py` 查询 BigQuery 视图，将异常写入 Cloud Logging
- Cloud Monitoring 日志指标匹配这些 JSON 条目
- 告警策略在指标 > 0 时触发通知
- `empty_return` 不触发 ingestion 告警，需按 endpoint/date 判断

## 目录结构

```
scripts/alerting/
├── setup_alerts.py      # 告警规则配置脚本（Cloud Monitoring）
├── check_alerts.py      # 告警查询脚本（定期检查 + 写入 Cloud Logging）
└── README.md            # 本文件

sql/observability/
└── 01_pipeline_status_views.sql  # 观测视图定义

docs/
└── OQ005-Pipeline-补跑与故障恢复-Runbook.md  # 补跑与故障恢复手册
```

## 快速开始

### 1. 创建观测视图

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/observability/01_pipeline_status_views.sql
```

### 2. 配置告警规则

```bash
# 安装依赖
pip install google-cloud-monitoring google-cloud-bigquery google-cloud-logging

# dry-run 查看配置
python scripts/alerting/setup_alerts.py --dry-run

# 实际配置
python scripts/alerting/setup_alerts.py --notification-channels "projects/xxx/notificationChannels/yyy"
```

### 3. 部署定期检查

```bash
# 方式 1：Cloud Scheduler + Cloud Run
gcloud scheduler jobs create http oq005-alert-check \
  --schedule='*/5 * * * *' \
  --uri='https://<cloud-run-url>/check-alerts' \
  --http-method=POST

# 方式 2：本机 cron
*/5 * * * * python /path/to/check_alerts.py --write-log --lookback-minutes 10
```

### 4. 查询异常

```bash
# 查询最近 10 分钟异常
python scripts/alerting/check_alerts.py

# 查询最近 10 分钟异常
python scripts/alerting/check_alerts.py --lookback-minutes 10

# 写入 Cloud Logging（供告警链路使用）
python scripts/alerting/check_alerts.py --write-log

# JSON 格式输出
python scripts/alerting/check_alerts.py --json
```

## 告警规则

| 告警名称 | 触发条件 | 严重程度 |
|---|---|---|
| Pipeline Run Failed | `pipeline_run.status = 'failed'` | ERROR |
| Task Failed (QA/Readiness/Transform) | `pipeline_task_status.status = 'failed'` | ERROR |
| Cloud Run Ingestion Failed | `ingestion_run.status = 'failed'`（不含 empty_return） | WARNING |

## 观测视图

| 视图名称 | 用途 |
|---|---|
| `v_pipeline_recent_runs` | 最近 DAG run 状态概览 |
| `v_pipeline_failed_tasks` | 失败 task 明细（含 BQ job id、Airflow log URL） |
| `v_pipeline_qa_failures` | QA 失败明细（QA-WIN-* 断言） |
| `v_ingestion_failures` | Cloud Run ingestion 失败明细（仅 failed） |
| `v_ingestion_empty_returns` | empty_return 明细（需按 endpoint/date 判断） |
| `v_pipeline_daily_health` | 每日 pipeline 健康仪表盘（按 pipeline_run_id join） |
| `v_alert_summary` | 最近 24 小时异常摘要（供告警查询） |
| `v_alert_probe` | 24 小时异常计数（手工健康检查；定时告警用 `check_alerts.py`） |

## 前置条件

1. 已执行 `sql/observability/01_pipeline_status_views.sql` 创建视图
2. 已配置 ADC：`gcloud auth application-default login`
3. 已启用 Cloud Monitoring API + Cloud Logging API
4. 已配置通知渠道（Email/Slack/PagerDuty）
5. `check_alerts.py` 已部署为定期任务（Cloud Scheduler 或 cron）
