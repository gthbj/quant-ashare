# ODS Parquet Schema Repair Scripts

修复 `ashare_ods` 外部表底层 GCS Parquet 文件的物理类型 mismatch。

关联 PRD: `docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md`

## 文件结构

```
configs/ods_schema_contracts/
  stk_limit.yml        # P0 - 涨跌停价格（dwd_stock_eod_price 消费）
  limit_list_d.yml     # P1 - 每日涨跌停统计
  moneyflow.yml        # P1 - 个股资金流向
  margin_detail.yml    # P1 - 融资融券明细
  dividend.yml         # P1 - 分红送股
  margin.yml           # P2 - 融资融券汇总
  daily_info.yml       # P2 - 每日市场概况
  sz_daily_info.yml    # P2 - 深圳市场概况
  fina_audit.yml       # P2 - 财务审计意见
  stk_rewards.yml      # P3 - 管理层薪酬持股

scripts/ods_repair/
  repair_parquet_schema.py   # 主修复脚本
  validate_repair.py         # 修复后验证脚本
  README.md                  # 本文件

sql/qa/
  06_ods_parquet_schema_checks.sql  # BigQuery QA 断言
```

## 执行顺序

### 1. Dry-run 盘点（P0 stk_limit）

```bash
python scripts/ods_repair/repair_parquet_schema.py \
  --endpoint stk_limit \
  --run-id repair_dryrun_001 \
  --partition-start 20190101 \
  --dry-run
```

输出 `data_audit/reports/repair_manifest_repair_dryrun_001.csv`，列出所有 mismatch 文件。

### 2. 执行 P0 修复

```bash
python scripts/ods_repair/repair_parquet_schema.py \
  --endpoint stk_limit \
  --run-id repair_20260603_01 \
  --partition-start 20190101
```

### 3. 验证修复结果

```bash
python scripts/ods_repair/validate_repair.py \
  --manifest data_audit/reports/repair_manifest_repair_20260603_01.csv
```

### 4. BigQuery QA（P0 only）

```bash
bq query --location=asia-east2 --use_legacy_sql=false \
  --parameter='priority_filter::P0' \
  < sql/qa/06_ods_parquet_schema_checks.sql
```

### 5. 分批修复 P1/P2/P3

```bash
# P1
for ep in limit_list_d moneyflow margin_detail dividend; do
  python scripts/ods_repair/repair_parquet_schema.py \
    --endpoint "$ep" --run-id repair_20260603_01 --partition-start 20190101
done

# P2
for ep in margin daily_info sz_daily_info fina_audit; do
  python scripts/ods_repair/repair_parquet_schema.py \
    --endpoint "$ep" --run-id repair_20260603_01 --partition-start 20190101
done

# P3
python scripts/ods_repair/repair_parquet_schema.py \
  --endpoint stk_rewards --run-id repair_20260603_01 --partition-start 20190101
```

### 6. BigQuery QA（full，全部 10 张修复后）

```bash
bq query --location=asia-east2 --use_legacy_sql=false \
  --parameter='priority_filter::all' \
  < sql/qa/06_ods_parquet_schema_checks.sql
```

## 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--endpoint` | 必填 | endpoint 名称，对应 contract YAML 文件名 |
| `--run-id` | 必填 | 修复运行 ID，用于 staging/backup/manifest 路径 |
| `--partition-start` | `20190101` | 起始分区日期 |
| `--partition-end` | 无 | 结束分区日期（含） |
| `--contracts-dir` | `configs/ods_schema_contracts` | contract 目录 |
| `--manifest-path` | 自动生成 | manifest CSV 路径 |
| `--dry-run` | false | 只检测不写入 |
| `--gcs-project` | `data-aquarium` | GCP 项目 |

## 幂等机制

- 每个 `(endpoint, partition_date, source_uri)` 在 manifest 中记录状态
- 状态为 `ok` 的文件自动跳过，不会重复修复
- backup/staging 路径包含 source_uri 的稳定 hash（`src_<sha256[:12]>`），保证同一分区下多个文件不互相覆盖
- backup 使用 GCS `if_generation_match=0` 原子写入：目标对象已存在时 copy 失败（HTTP 412），不会覆盖原始备份；并发场景下先到者创建、后到者看到已存在并跳过
- 源文件 schema 已匹配 contract 时跳过重写和发布
- 临时 BQ 验证表名包含 `run_id` + `src_hash`，delete-then-create 保证并发安全
- 验证查询对所有字段名加反引号（`` ` ``），避免 BigQuery 保留字冲突（如 `limit`）

## INT->FLOAT64 精度安全

整型字段加宽到 FLOAT64 时，脚本检查非空最大值是否 < 2^53。
超过阈值的字段标记为 `manual_review`，不自动写入。

## 回滚方式

每个修复的原始文件备份在（路径包含 source_uri hash 保证唯一性）：

```
gs://data-aquarium/a-share/tushare/repair_backup/run_id=<run_id>/api=tushare/endpoint=<endpoint>/partition_date=<YYYYMMDD>/src_<sha256[:12]>/data.parquet
```

回滚步骤：

1. 从 manifest CSV 中找到对应行的 `backup_uri` 列（推荐，最可靠）
2. 或手动构造路径：`run_id` + `endpoint` + `partition_date` + `src_<hash>`
3. 从 backup 路径复制回 `source_uri`（正式路径）
4. 或用 `gsutil cp` 恢复

示例：
```bash
# 从 manifest 读取 backup URI 并恢复
python -c "
import csv
with open('data_audit/reports/repair_manifest_repair_20260603_01.csv') as f:
    for row in csv.DictReader(f):
        if row['endpoint']=='stk_limit' and row['partition_date']=='20190102':
            print(row['backup_uri'])
"
# 然后 gsutil cp <backup_uri> <source_uri>
```

## Manifest 状态枚举

| 状态 | 含义 |
|---|---|
| `ok` | 修复成功或 schema 已匹配 |
| `dry_run_mismatch` | dry-run 模式下检测到 mismatch |
| `manual_review` | INT->FLOAT64 精度风险，需人工复核 |
| `read_failed` | 原始文件无法读取 |
| `staging_write_failed` | staging 写入失败 |
| `bq_validation_failed` | BigQuery 临时外部表验证失败（publish 前阻断） |
| `backup_failed` | 备份失败 |
| `publish_failed` | 发布到正式路径失败 |
| `error` | 其他错误（如行数变化） |
| `skipped_schema_match` | 原始 schema 已匹配，跳过 |
