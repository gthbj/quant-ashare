# OQ-005 Pipeline 补跑与故障恢复 Runbook

> 文档维护：GPT-5 Codex（最近更新 2026-06-06）

本 runbook 覆盖 OQ-005 日常调度链路的常见故障与恢复步骤。

---

## 0. DAG 参数速查

| 参数 | 默认值 | 说明 |
|---|---|---|
| `business_date` | `data_interval_end`（Asia/Shanghai 当天） | 业务日期，手动触发时覆盖 |
| `date_from` | 空 | backfill 起始日期 |
| `date_to` | `data_interval_end`（Asia/Shanghai 当天） | backfill 结束日期 |
| `warehouse_mode` | `daily_current` | `daily_current` / `backfill` / `qa_only` / `full_rebuild` |
| `skip_ingestion` | `false` | 跳过 Cloud Run 采集 |
| `pipeline_dry_run` | `true` | 采集 dry-run 模式 |
| `skip_transform` | `false` | 跳过 DWD/DWS 转换 |
| `run_label` | `production_daily` | 运行标签 |
| `require_business_partition` | 空（dry-run=false 时默认 true） | 强制要求精确分区 |

**调度语义：**
- 20:00 CST scheduled run：`business_date` 默认为当天（Asia/Shanghai）
- 手动触发：`dag_run.conf` 中的参数最高优先级
- `backfill` 模式：必须显式指定 `date_from`/`date_to`
- 非交易日：当前 DAG 仍按给定 `business_date` 进入 readiness；不要依赖它自动补上一交易日，需要修复上一交易日时显式触发 `backfill`
- `pipeline_dry_run=true` 时，readiness 只做检查，不写 `pipeline_task_status` warning 行

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
| API 行数达到上限 | `api_row_limit_risk` | `pipeline_task_status` |

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

## 8. 非交易日处理

**场景：** 周末或节假日触发 daily_current 模式。

**当前行为：**
- scheduled `daily_current` 会先查 SSE 交易日历；若当天不是交易日，自动跳过 ingestion、ODS readiness 和 transform，并写入 `skip_non_trading_day` task 状态。
- 手工触发的 `daily_current` 不作为自动跳过入口；如果触发到非交易日，应先确认是否需要补上一交易日。只有部署 smoke 可以显式传 `force_non_trading_day_gate=true` 来强制测试 skip 分支。
- 需要修复上一交易日时，显式使用 `backfill` 并设置 `date_from`/`date_to`。
- 非交易日不会因为 weak endpoint 缺失写入 warning；strong endpoint 若归一到的最近交易日 ODS 缺失，仍会阻断。
- `qa_only` 模式继续执行只读检查。
- gate 依赖 `ashare_dim.dim_trade_calendar` 已覆盖目标日期；若未来日历未延展或 `is_open` 为空，DAG 会 fail-closed，需要先采集/刷新 `trade_cal` 与 `dim_trade_calendar` 后再恢复调度。

**生产验收：** DAG 合并部署后，用真正 scheduler 触发的周末/节假日 run 验证 `skip_non_trading_day` 状态写入；如果无法等待 scheduler，可手工触发并显式设置 `force_non_trading_day_gate=true`，但普通 `dags trigger` 不算 skip gate 验收。上一交易日修复仍走显式 `backfill`。

**手动触发非交易日：**
```bash
# 非交易日只跑 QA
gcloud composer environments run ashare-composer \
  --project=data-aquarium --location=asia-east2 \
  dags -- trigger ashare_daily_pipeline_v0 \
  --conf '{"warehouse_mode": "qa_only", "business_date": "2026-06-07"}' \
  --run-id "manual_qa_only_weekend"

# smoke-only：手工强制测试 scheduled 非交易日 skip 分支
gcloud composer environments run ashare-composer \
  --project=data-aquarium --location=asia-east2 \
  dags -- trigger ashare_daily_pipeline_v0 \
  --conf '{"warehouse_mode": "daily_current", "business_date": "2026-06-07", "force_non_trading_day_gate": true}' \
  --run-id "manual_smoke_skip_non_trading_day"

# 补跑上一交易日（必须显式 backfill）
gcloud composer environments run ashare-composer \
  --project=data-aquarium --location=asia-east2 \
  dags -- trigger ashare_daily_pipeline_v0 \
  --conf '{"warehouse_mode": "backfill", "date_from": "2026-06-05", "date_to": "2026-06-05", "skip_ingestion": true}' \
  --run-id "manual_backfill_friday"
```

---

## 9. Strong endpoint 缺失处理

**场景：** 交易日 20:00 后 strong endpoint（daily, daily_basic, adj_factor, stk_limit, index_daily）数据缺失。

**行为：** `ods_daily_partition_readiness` 失败，错误 `QA-ODS-DAILY-2`，pipeline 阻断。非阻断 warning 会先写入 `pipeline_task_status`，便于失败后仍能看到 weak endpoint 缺失或 API 行数上限风险。

**恢复步骤：**

1. **确认缺失 endpoint：**
   ```sql
   SELECT endpoint, partition_date, status
   FROM `data-aquarium.ashare_meta.ingestion_partition_status`
   WHERE partition_date = FORMAT_DATE('%Y%m%d', CURRENT_DATE('Asia/Shanghai'))
     AND status != 'success'
   ORDER BY endpoint;
   ```

2. **检查 Tushare 官方更新时间：**
   - daily: 15:00-17:00
   - daily_basic: 15:00-17:00
   - adj_factor: 盘前 9:15-9:20
   - stk_limit: 交易日 9:00
   - index_daily: 15:00-17:00

3. **如果 Tushare 已更新但 ODS 缺失：**
   ```bash
   # 补采缺失 endpoint
   gcloud run jobs execute ashare-ingest-current-scope \
     --project=data-aquarium --region=asia-east2 \
     --args="--endpoint-group,current_scope,--endpoint,daily,--endpoint,daily_basic,--business-date,2026-06-05,--allow-gcs-write"
   ```

4. **重新触发 DAG：**
   ```bash
   gcloud composer environments run ashare-composer \
     --project=data-aquarium --location=asia-east2 \
     dags -- trigger ashare_daily_pipeline_v0 \
     --conf '{"skip_ingestion": true, "warehouse_mode": "daily_current", "business_date": "2026-06-05"}' \
     --run-id "manual_recovery_strong_20260605"
   ```

---

## 10. Weak endpoint 空返回处理

**场景：** weak endpoint（suspend_d, stock_basic, trade_cal 等）空返回或缺失。

**行为：** 记录到 `pipeline_task_status`（status=`weak_endpoint_missing`），不阻断 pipeline。

**判断标准：**
- `suspend_d`：空返回可能是正常（当日无停牌）
- `stock_basic`：检查是否为最新分区
- `trade_cal`：检查是否为最新日历
- `namechange`：检查是否为最新快照
- `index_dailybasic`：检查 Tushare 是否已更新
- 财报类：20:00 不要求完整，后续公告由下次日更捕获

**如果确认异常：**
```bash
# 补采 weak endpoint
gcloud run jobs execute ashare-ingest-current-scope \
  --project=data-aquarium --region=asia-east2 \
  --args="--endpoint-group,current_scope,--endpoint,suspend_d,--business-date,2026-06-05,--allow-gcs-write"
```

---

## 11. Cloud Run / Airflow queued 卡住排查

**症状：** task 状态停在 `queued` 超过 10 分钟。

**排查步骤：**

1. **检查 Airflow worker 状态：**
   ```bash
   gcloud composer environments describe ashare-composer \
     --project=data-aquarium --location=asia-east2 \
     --format="value(config.workersConfig)"
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
     --run-id "manual_recovery_queued_20260605"
   ```

---

## 12. 需要显式 backfill 的场景

**场景：**
- 数据修复后需要重新刷新 DWD/DWS
- ODS 补采后需要重建窗口
- QA 失败后需要重跑
- 需要回填历史日期

**backfill 模式特点：**
- 必须显式指定 `date_from`/`date_to`
- 不依赖 `ds` 或 `data_interval_end`
- 使用 `skip_ingestion: true` 跳过已采集数据
- 使用 `pipeline_dry_run: false` 确保写入

**示例：**
```bash
# 回填 20 个交易日窗口
gcloud composer environments run ashare-composer \
  --project=data-aquarium --location=asia-east2 \
  dags -- trigger ashare_daily_pipeline_v0 \
  --conf '{
    "skip_ingestion": true,
    "pipeline_dry_run": false,
    "warehouse_mode": "backfill",
    "date_from": "2026-05-08",
    "date_to": "2026-06-04",
    "run_label": "manual_backfill_20d"
  }' \
  --run-id "manual_backfill_20260508_20260604"

# 只补 ODS（不跑 warehouse）
gcloud composer environments run ashare-composer \
  --project=data-aquarium --location=asia-east2 \
  dags -- trigger ashare_daily_pipeline_v0 \
  --conf '{
    "pipeline_dry_run": false,
    "skip_transform": true,
    "business_date": "2026-06-05",
    "run_label": "ods_only_20260605"
  }' \
  --run-id "manual_ods_only_20260605"

# 只跑 QA（不写数据）
gcloud composer environments run ashare-composer \
  --project=data-aquarium --location=asia-east2 \
  dags -- trigger ashare_daily_pipeline_v0 \
  --conf '{
    "warehouse_mode": "qa_only",
    "business_date": "2026-06-05"
  }' \
  --run-id "manual_qa_only_20260605"
```

---

## 13. 常用观测查询

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
2. **task_failure：** `pipeline_task_status.status = 'failed'`（所有失败 task；QA/readiness/windowed 明细见 `v_pipeline_qa_failures`）
3. **ingestion_failed：** `ingestion_run.status = 'failed'`（不含 `empty_return`，空返回见 `v_ingestion_empty_returns` 并按 endpoint/date 判断）

通知渠道建议：Email + Slack/PagerDuty（按严重程度分级）。

详见 `scripts/alerting/` 下的告警配置脚本。
