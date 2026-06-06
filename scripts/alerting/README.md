# Ashare Pipeline 告警与观测

> 文档维护：GPT-5 Codex（最近更新 2026-06-05）

## 概述

本目录包含 Ashare pipeline 日常调度链路的告警规则、观测视图和补跑 runbook。

## 告警链路

```
ashare_pipeline_alert_checker (Cloud Composer DAG, */10 * * * *)
    |
    v
check_alerts.py --write-log --write-heartbeat --lookback-minutes 20
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
- 生产定时入口是 Composer DAG `ashare_pipeline_alert_checker`，每 10 分钟执行一次
- checker 查询窗口为 20 分钟，和 10 分钟调度形成重叠，避免调度延迟时漏报
- `check_alerts.py` 查询 BigQuery 视图，将异常写入 Cloud Logging
- `check_alerts.py` 每次成功查询后写入 checker heartbeat
- Cloud Monitoring 日志指标匹配这些 JSON 条目
- 告警策略在指标 > 0 时触发通知
- checker heartbeat 30 分钟缺失会触发 dead-man's-switch 告警
- `empty_return` 不触发 ingestion 告警，需按 endpoint/date 判断

## 目录结构

```
scripts/alerting/
├── setup_alerts.py      # 告警规则配置脚本（Cloud Monitoring）
├── check_alerts.py      # 告警查询脚本（定期检查 + 写入 Cloud Logging）
└── README.md            # 本文件

orchestration/composer/dags/
└── ashare_pipeline_alert_checker.py  # 生产定时 checker DAG

sql/observability/
└── 01_pipeline_status_views.sql  # 观测视图定义

docs/
└── Pipeline-补跑与故障恢复-Runbook.md  # 补跑与故障恢复手册
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
# 生产路径：同步 checker 脚本与 DAG 到 Composer bucket
gcloud storage cp scripts/alerting/check_alerts.py \
  gs://asia-east2-ashare-composer-b2629133-bucket/data/scripts/alerting/check_alerts.py

gcloud storage cp orchestration/composer/dags/ashare_pipeline_alert_checker.py \
  gs://asia-east2-ashare-composer-b2629133-bucket/dags/ashare_pipeline_alert_checker.py

# 验证 DAG 已被 Airflow 识别
gcloud composer environments run ashare-composer \
  --location=asia-east2 dags list -- --output json
```

Cloud Scheduler 或本机 cron 仅作为非生产替代入口，不能作为当前生产部署口径记录。

### 4. 查询异常

```bash
# 查询最近 10 分钟异常（脚本默认窗口）
python scripts/alerting/check_alerts.py

# 按生产窗口查询最近 20 分钟异常
python scripts/alerting/check_alerts.py --lookback-minutes 20

# 写入 Cloud Logging（供告警链路使用）
python scripts/alerting/check_alerts.py --write-log --write-heartbeat --lookback-minutes 20

# JSON 格式输出
python scripts/alerting/check_alerts.py --json
```

## 告警规则

| 告警名称 | 触发条件 | 严重程度 |
|---|---|---|
| Pipeline Run Failed | `pipeline_run.status = 'failed'` | ERROR |
| Task Failed | `pipeline_task_status.status = 'failed'` | ERROR |
| Ingestion Failed | `ingestion_run.status = 'failed'`（不含 empty_return） | WARNING |
| Alert Checker Heartbeat Missing | `ashare_pipeline_alert_checker_heartbeat` 30 分钟无数据 | ERROR |

`Alert Checker Heartbeat Missing` 是告警链路自身的 liveness 监控。`ashare_pipeline_alert_checker` 每 10 分钟调用 `check_alerts.py --write-heartbeat` 写入一次 heartbeat；若 DAG 被 pause、Composer 调度异常、脚本启动失败或日志写入失败，heartbeat 会停止，Cloud Monitoring 的 absence condition 会触发通知。

`setup_alerts.py` 使用 `user_labels.ashare_pipeline_policy` 作为告警策略幂等键；旧版 display name 会被迁移到当前命名，避免重复创建新旧两份策略。

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
5. Composer DAG `ashare_pipeline_alert_checker` 已部署并处于 unpaused 状态
6. 已配置 `ashare_pipeline_alert_checker_heartbeat` log-based metric 与 absence alert policy
