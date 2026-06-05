# OQ-005 Pipeline 告警与观测

> 文档维护：opencode（最近更新 2026-06-05）

## 概述

本目录包含 OQ-005 日常调度链路的告警规则、观测视图和补跑 runbook。

## 目录结构

```
scripts/alerting/
├── setup_alerts.py      # 告警规则配置脚本（Cloud Monitoring）
├── check_alerts.py      # 告警查询脚本（定期检查）
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
pip install google-cloud-monitoring google-cloud-bigquery

# dry-run 查看配置
python scripts/alerting/setup_alerts.py --dry-run

# 实际配置（需先配置通知渠道）
python scripts/alerting/setup_alerts.py --notification-channels "projects/xxx/notificationChannels/yyy"
```

### 3. 查询异常

```bash
# 查询最近 1 小时异常
python scripts/alerting/check_alerts.py

# 查询最近 24 小时异常
python scripts/alerting/check_alerts.py --lookback-hours 24

# JSON 格式输出
python scripts/alerting/check_alerts.py --json
```

## 告警规则

| 告警名称 | 触发条件 | 严重程度 |
|---|---|---|
| Pipeline Run Failed | `pipeline_run.status = 'failed'` | ERROR |
| QA-WIN Assertion Failed | QA 断言失败 | ERROR |
| Cloud Run Ingestion Failed | 采集失败或 empty_return | WARNING |
| ODS Daily Partition Readiness Failed | ODS 分区就绪检查失败 | ERROR |

## 观测视图

| 视图名称 | 用途 |
|---|---|
| `v_pipeline_recent_runs` | 最近 DAG run 状态概览 |
| `v_pipeline_failed_tasks` | 失败 task 明细（含 BQ job id、Airflow log URL） |
| `v_pipeline_qa_failures` | QA 失败明细（QA-WIN-* 断言） |
| `v_ingestion_failures` | Cloud Run ingestion 失败明细 |
| `v_pipeline_daily_health` | 每日 pipeline 健康仪表盘 |
| `v_alert_summary` | 最近 24 小时异常摘要（供告警查询） |

## 补跑与故障恢复

详见 `docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md`，覆盖：

- ODS 某天没采集
- 某 endpoint 采集失败
- 窗口 SQL 执行失败
- QA 断言失败
- DAG run 卡住
- 需要 backfill 某日期窗口

## 前置条件

1. 已执行 `sql/observability/01_pipeline_status_views.sql` 创建视图
2. 已配置 ADC：`gcloud auth application-default login`
3. 已启用 Cloud Monitoring API（如使用 `setup_alerts.py`）
4. 已配置通知渠道（Email/Slack/PagerDuty）

## 注意事项

- 告警规则基于 `v_alert_summary` 视图，该视图查询最近 24 小时的异常
- `check_alerts.py` 默认查询最近 1 小时，可通过 `--lookback-hours` 调整
- 通知渠道需在 Cloud Console 中手动配置，脚本只创建告警规则
- 建议将 `check_alerts.py` 配置为 Cloud Scheduler 定时任务，每 5-10 分钟执行一次
