# OQ-005 Pipeline 补跑与故障恢复 Runbook

> 文档维护：opencode（最近更新 2026-06-05）

本 runbook 覆盖 OQ-005 日常调度链路的常见故障与恢复步骤。

---

## 1. 故障分类与快速定位

| 故障类型 | 典型错误 | 关键日志/表 |
|---|---|---|
| ODS 某天没采集 | `QA-ODS-DAILY-2: zero rows` | `ashare_meta.ingestion_run` |
| 某 endpoint 采集失败 | `ingestion_run.status = 'failed'` | `ashare_meta.ingestion_partition_status` |
| 窗口 SQL 执行失败 | BigQuery job error | `pipeline_task_status.bigquery_job_url` |
| QA 断言失败 | `QA-WIN-*` / `QA-ODS-*` | `pipeline_task_status.error_summary` |
| DAG run 卡住 | task 状态停在 `queued`/`running` | Airflow UI / `pipeline_task_status` |
| 需要 backfill 某日期窗口 | 数据修复/补采后 | 手动触发 DAG |

---

## 2. ODS 某天没采集

**症状：** `ods_daily_partition_readiness` 失败，错误 `QA-ODS-DAILY-2: required daily/recent ODS partition has zero rows`

**原因：** Cloud Run ingestion 未执行或执行失败，导致 ODS GCS 分区缺失。

**恢复步骤：**

1. **确认缺失分区：**
   ```sql
   SELECT endpoint, partition_date, status
   FROM `data-aquarium.ashare_meta.ingestion_partition_status`
   WHERE partition_date = FORMAT_DATE('%Y%m%d', DATE '2026-06-05')
     AND status != 'success'
   ORDER BY endpoint;
   ```

2. **触发采集补跑：**
   ```bash
   gcloud run jobs execute ashare-ingest-current-scope \
     --project=data-aquarium \
     --region=asia-east2 \
     --args="--endpoint-group,current_scope,--business-date,2026-06-05,--allow-gcs-write"
   ```

3. **验证采集完成：**
   ```sql
   SELECT endpoint, partition_date, status, row_count
   FROM `data-aquarium.ashare_meta.ingestion_partition_status`
   WHERE partition_date = '20260605'
   ORDER BY endpoint;
   ```

4. **重新触发 DAG：**
   ```bash
   gcloud composer environments run ashare-composer \
     --project=data-aquarium --location=asia-east2 \
     dags -- trigger ashare_daily_pipeline_v0 \
     --conf '{"skip_ingestion": true, "warehouse_mode": "daily_current", "business_date": "2026-06-05"}' \
     --run-id "manual_oq005_recovery_20260605"
   ```

---

## 3. 某 endpoint 采集失败

**症状：** `ingestion_run.status = 'failed'`，部分 endpoint 无数据。

**恢复步骤：**

1. **查看失败详情：**
   ```sql
   SELECT ingestion_run_id, endpoint, status, error_summary, started_at, finished_at
   FROM `data-aquarium.ashare_meta.ingestion_run`
   WHERE status = 'failed'
     AND started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
   ORDER BY started_at DESC;
   ```

2. **单 endpoint 补跑（如需要）：**
   ```bash
   gcloud run jobs execute ashare-ingest-current-scope \
     --project=data-aquarium \
     --region=asia-east2 \
     --args="--endpoint-group,current_scope,--endpoint,daily,--business-date,2026-06-05,--allow-gcs-write"
   ```
   注意：`--endpoint` 参数可重复使用，如 `--endpoint,daily,--endpoint,adj_factor`。

3. **验证分区状态：**
   ```sql
   SELECT endpoint, partition_date, status, row_count
   FROM `data-aquarium.ashare_meta.ingestion_partition_status`
   WHERE partition_date = '20260605'
   ORDER BY endpoint;
   ```

---

## 4. 窗口 SQL 执行失败

**症状：** `windowed_transform.stock_dwd_dws_window` 失败，BigQuery job error。

**恢复步骤：**

1. **获取 BigQuery job URL：**
   ```sql
   SELECT task_id, bigquery_job_id, bigquery_job_url, error_summary
   FROM `data-aquarium.ashare_meta.pipeline_task_status`
   WHERE pipeline_run_id = 'manual_oq005_xxx'
     AND task_id = 'windowed_transform.stock_dwd_dws_window';
   ```

2. **在 BigQuery Console 查看 job 详情和错误信息。**

3. **常见原因与修复：**
   - **表不存在：** 确认 DWD/DWS 表已由全量路径初始化
   - **权限不足：** 检查 Composer service account 权限
   - **资源超限：** 减小窗口范围或分批执行

4. **修复后重新触发 DAG。**

---

## 5. QA 断言失败

**症状：** `windowed_stock_refresh_checks` 失败，错误包含 `QA-WIN-*`。

**恢复步骤：**

1. **查看具体断言：**
   ```sql
   SELECT task_id, error_summary, bigquery_job_url
   FROM `data-aquarium.ashare_meta.pipeline_task_status`
   WHERE pipeline_run_id = 'manual_oq005_xxx'
     AND task_id LIKE '%qa%'
     AND status = 'failed';
   ```

2. **常见 QA 断言与修复：**

   | 断言 | 含义 | 修复 |
   |---|---|---|
   | `QA-WIN-1..9` | 主键重复 | 检查 DML 逻辑或源数据 |
   | `QA-WIN-10..12` | 生命周期/退市日 | 重建 `dim_stock` |
   | `QA-WIN-13` | ODS daily 表示性 | 确认 ODS 数据完整 |
   | `QA-WIN-16` | 估值 DWD 缺失 | 确认 `dwd_stock_eod_valuation` 已刷新 |
   | `QA-WIN-17` | 估值 DWS 缺失 | 确认窗口刷新 SQL 正常执行 |
   | `QA-WIN-18` | `has_valuation_data` 异常 | 检查 `dws_stock_feature_daily_v0` 逻辑 |

3. **修复后重新触发 DAG。**

---

## 6. DAG run 卡住

**症状：** task 状态停在 `queued` 或 `running` 超过预期时间。

**恢复步骤：**

1. **查看 task 状态：**
   ```bash
   gcloud composer environments run ashare-composer \
     --project=data-aquarium --location=asia-east2 \
     tasks -- states-for-dag-run ashare_daily_pipeline_v0 "manual_oq005_xxx" --output table
   ```

2. **检查是否为 zombie job：**
   ```bash
   gcloud logging read "resource.type=cloud_composer_environment \
     AND resource.labels.environment_name=ashare-composer \
     AND textPayload=~\"zombie\"" \
     --project=data-aquarium --limit=5
   ```

3. **清理并重新调度：**
   ```bash
   # 清理卡住的 task
   gcloud composer environments run ashare-composer \
     --project=data-aquarium --location=asia-east2 \
     tasks -- clear ashare_daily_pipeline_v0 \
     -t "windowed_dim" -s "2026-06-05" -e "2026-06-05" -y --yes

   # 重新触发 DAG
   gcloud composer environments run ashare-composer \
     --project=data-aquarium --location=asia-east2 \
     dags -- trigger ashare_daily_pipeline_v0 \
     --conf '{"skip_ingestion": true, "warehouse_mode": "daily_current", "business_date": "2026-06-05"}' \
     --run-id "manual_oq005_recovery_20260605_2"
   ```

---

## 7. 需要 backfill 某日期窗口

**场景：** 数据修复、ODS 补采后需要重新刷新 DWD/DWS。

**步骤：**

1. **触发 backfill DAG：**
   ```bash
   gcloud composer environments run ashare-composer \
     --project=data-aquarium --location=asia-east2 \
     dags -- trigger ashare_daily_pipeline_v0 \
     --conf '{"skip_ingestion": true, "pipeline_dry_run": false, "warehouse_mode": "backfill", "business_date": "2026-06-04", "date_from": "2026-05-08", "date_to": "2026-06-04", "run_label": "manual_backfill"}' \
     --run-id "manual_oq005_backfill_20260508_20260604"
   ```

2. **监控执行状态：**
   ```bash
   gcloud composer environments run ashare-composer \
     --project=data-aquarium --location=asia-east2 \
     dags -- list-runs -d ashare_daily_pipeline_v0 --output table
   ```

3. **验证数据：**
   ```sql
   SELECT trade_date, COUNT(*) AS row_count
   FROM `data-aquarium.ashare_dwd.dwd_stock_eod_valuation`
   WHERE trade_date BETWEEN '2026-05-08' AND '2026-06-04'
   GROUP BY trade_date
   ORDER BY trade_date;
   ```

---

## 8. 常用观测查询

### 最近 DAG run 状态
```sql
SELECT * FROM `data-aquarium.ashare_meta.v_pipeline_recent_runs`;
```

### 失败 task 明细
```sql
SELECT * FROM `data-aquarium.ashare_meta.v_pipeline_failed_tasks`;
```

### QA 失败明细
```sql
SELECT * FROM `data-aquarium.ashare_meta.v_pipeline_qa_failures`;
```

### Cloud Run ingestion 失败
```sql
SELECT * FROM `data-aquarium.ashare_meta.v_ingestion_failures`;
```

### 最近 24 小时异常摘要
```sql
SELECT * FROM `data-aquarium.ashare_meta.v_alert_summary`;
```

### 每日 pipeline 健康仪表盘
```sql
SELECT * FROM `data-aquarium.ashare_meta.v_pipeline_daily_health`;
```

---

## 9. 告警规则配置

告警规则基于 `v_alert_summary` 视图，配置在 Cloud Monitoring 中：

1. **pipeline_failure：** `pipeline_run.status = 'failed'`
2. **task_failure：** `pipeline_task_status.status = 'failed'` 且 task_id 包含 `qa`/`checks`/`readiness`/`windowed`
3. **ingestion_failure：** `ingestion_run.status IN ('failed', 'empty_return')`

通知渠道建议：Email + Slack/PagerDuty（按严重程度分级）。

详见 `scripts/alerting/` 下的告警配置脚本。
