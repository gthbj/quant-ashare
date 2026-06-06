# PRD: ODS 外部表 Parquet Schema 修复

> 文档维护：GPT-5（最近更新 2026-06-03）
> 状态：草案，待 review / 合并。
> 范围声明：本文定义 `ashare_ods` 外部表 Parquet 物理类型不一致问题的修复方案、执行边界、验证门禁和防复发要求；本文不直接修复 GCS 文件、不重建 ODS 外部表、不补采数据。
> 关联：`data_audit/ODS_GCS_DATA_AUDIT_PROMPT.md`、`.agent/memory/KNOWN_CONSTRAINTS.md`、`docs/数据仓库建模方案-DWD-DIM.md`。

---

## 1. 背景

`data-aquarium.ashare_ods` 当前为 Tushare 来源的 Hive 分区外部表，底层数据存放在 GCS Parquet。数据审查发现 10 张 ODS 外部表存在 Parquet 物理类型与 BigQuery 外部表 schema 不一致的问题。

2026-06-03 已用 BigQuery 只读查询复核：对这些表执行 `partition_date >= '20190101'` 范围内的业务列读取时，BigQuery 会因 Parquet schema mismatch 报错。该问题发生在 GCS Parquet 文件层，`SAFE_CAST` 无法兜底。

典型模式：

- BigQuery 外部表期望 `FLOAT64`，部分 Parquet 分区写成 `INT32` 或 `INT64`。
- BigQuery 外部表期望 `INT64`，部分 Parquet 分区写成 `DOUBLE`.
- 某些分区因字段全为整数或空值，由 pandas / pyarrow 自动推断出更窄或不同的物理类型。

当前策略 1 不直接读取 ODS，而是读取已物化 DWD/DWS/ADS。10 张问题表中，当前 P0/策略链路只消费 `ods_tushare_stk_limit`；现有 `dwd_stock_eod_price` 只读取其中 `up_limit` / `down_limit`，这两列当前可读。`stk_limit.pre_close` 仍存在 mismatch，后续读全表或扩展字段会失败。

## 2. 目标

1. 修复 10 张 ODS 外部表 2019-01-01 及之后分区的 Parquet schema mismatch。
2. 修复方式以 GCS 原 Parquet 文件 schema-preserving rewrite 为主。
3. 修复过程只改变 Parquet 物理 schema，不改变业务值口径、不补缺数、不创建伪空 Parquet。
4. 修复前建立 endpoint schema contract，修复后所有目标业务列能被 BigQuery 外部表读取。
5. 对当前策略相关的 `ods_tushare_stk_limit` 优先修复和验证。
6. 在 ingestion / Parquet 生成侧加入显式 cast，防止新增分区再次写出不一致 schema。

## 3. 实施边界

- 本 PRD 处理 Parquet 物理类型修复，不处理 API 值级差异。
- API 回查命中 6000 行上限的问题按数据审查流程继续拆分复核，不作为本 PRD 的修复输入。
- 字段值差异按 endpoint 逐项判断接口快照、版本、请求参数和当前 API 返回变化，不在本 PRD 中合并修正。
- 默认不从 Tushare/Tinyshare API 重新拉取并覆盖历史 raw。
- GCS 原文件不可读、原文件缺失、行数缺失或 owner 明确要求按当前 API 快照重建时，API 重拉作为补救路径。
- 修复脚本、schema contract、QA SQL 和运行报告在后续实现 PR 中交付。

## 4. 受影响范围

### 4.1 10 张外部表

| ODS 表 | endpoint | 当前消费状态 | 修复优先级 | 已复现 mismatch 字段 |
|---|---|---|---|---|
| `ods_tushare_stk_limit` | `stk_limit` | P0 `dwd_stock_eod_price` 消费 `up_limit/down_limit` | P0 | `pre_close` |
| `ods_tushare_limit_list_d` | `limit_list_d` | P1 涨跌停 / 连板事件扩展 | P1 | `amount`, `limit_amount`, `fd_amount`, `open_times`, `limit_times` |
| `ods_tushare_moneyflow` | `moneyflow` | P1 资金流扩展 | P1 | `buy_md_vol`, `sell_md_vol` |
| `ods_tushare_margin_detail` | `margin_detail` | P1 两融个股明细扩展 | P1 | `rqye`, `rzrqye` |
| `ods_tushare_dividend` | `dividend` | P1 分红送转事件扩展 | P1 | `stk_bo_rate`, `stk_co_rate` |
| `ods_tushare_margin` | `margin` | P2 两融市场汇总扩展 | P2 | `rqyl` |
| `ods_tushare_daily_info` | `daily_info` | P2 市场概况扩展 | P2 | `com_count`, `trans_count` |
| `ods_tushare_sz_daily_info` | `sz_daily_info` | P2 市场概况扩展 | P2 | `total_share`, `total_mv`, `float_share`, `float_mv` |
| `ods_tushare_fina_audit` | `fina_audit` | P2 财务审计扩展 | P2 | `audit_fees` |
| `ods_tushare_stk_rewards` | `stk_rewards` | P3 管理层薪酬持股扩展 | P3 | `hold_vol` |

### 4.2 当前策略影响

当前策略 1 的已物化链路：

```text
ods_tushare_stk_limit
  -> dwd_stock_eod_price
  -> dws_stock_feature_price_daily / universe / label / sample
  -> ads strategy1 runner
```

现有 DWD SQL 只读取：

```sql
SAFE_CAST(up_limit AS FLOAT64) AS up_limit,
SAFE_CAST(down_limit AS FLOAT64) AS down_limit
```

因此当前策略运行未被 `pre_close` mismatch 直接阻断。但 `ods_tushare_stk_limit` 作为 P0 源表，应在本次修复中优先处理，使表级全字段读取和未来字段扩展稳定。

## 5. 修复原则

1. **先定 schema contract，再改文件**
   每个 endpoint 的字段类型先固化为机器可读 contract，再按 contract 重写 Parquet。

2. **优先修 GCS 原 Parquet，不默认重拉 API**
   当前问题是 Parquet 物理类型不一致。直接用当前 API 重拉会引入接口快照、版本变化、请求参数和 6000 行上限风险。

3. **只修 schema，不改口径**
   修复后同一分区行数保持不变；字段值仅做类型等价转换，例如整数物理类型写成 `FLOAT64` 逻辑类型。

4. **staging 先行，验证后发布**
   所有修复文件先写 staging prefix；schema、行数、null count 和 BigQuery 外部读取验证通过后，才覆盖正式 prefix。

5. **先备份再覆盖**
   正式路径覆盖前复制原文件到 backup prefix，并记录 backup URI、修复 run id 和文件 hash。

6. **ingestion 侧防复发**
   修复历史文件后，采集 / Parquet 写入侧必须按同一 schema contract 显式 cast。

## 6. 目标产物

后续实现 PR 交付以下产物：

| 产物 | 路径建议 | 内容 |
|---|---|---|
| Schema contract | `configs/ods_schema_contracts/*.yml` | 10 个 endpoint 的字段、目标 BigQuery 类型、目标 pyarrow 类型、nullable、单位备注 |
| 修复脚本 | `scripts/ods_repair/repair_parquet_schema.py` | 从 GCS 原 Parquet 读取、按 contract cast、写 staging、生成 repair manifest |
| 验证脚本 | `scripts/ods_repair/validate_repair.py` | 行数、schema、null count、hash、BigQuery 临时外部表读取验证 |
| QA SQL | `sql/qa/06_ods_parquet_schema_checks.sql` | 对 10 张 ODS 表 2019+ 业务列执行可读性检查 |
| 修复报告 | `data_audit/reports/ods_parquet_schema_repair_<run_id>.md` | 修复时间、范围、脚本版本、执行者模型、表/分区/文件清单、验证结果、遗留项 |

## 7. Schema Contract 设计

### 7.1 字段

每个 endpoint contract 至少包含：

| 字段 | 含义 |
|---|---|
| `source_system` | `tushare` / `tinyshare` |
| `endpoint` | API endpoint |
| `ods_table` | BigQuery ODS 外部表 |
| `gcs_prefix` | GCS raw prefix |
| `partition_field` | `partition_date` |
| `field_name` | 字段名 |
| `bigquery_type` | `STRING` / `INT64` / `FLOAT64` / `BOOL` |
| `pyarrow_type` | `string` / `int64` / `float64` / `bool` |
| `nullable` | 是否允许 NULL |
| `semantic_type` | `amount` / `volume` / `share` / `price` / `ratio` / `count` / `text` / `date` |
| `unit_note` | 源字段单位说明，未知则标 `pending` |
| `repair_policy` | `cast_preserve_value` / `stringify` / `manual_review` |

### 7.2 类型策略

| BigQuery 目标类型 | Parquet / pyarrow 写入类型 | 说明 |
|---|---|---|
| `STRING` | `pa.string()` | 日期字段仍按 ODS 原口径保留 `YYYYMMDD` 字符串 |
| `INT64` | `pa.int64()` | 仅用于语义确定为整数且无小数风险的字段 |
| `FLOAT64` | `pa.float64()` | 金额、比例、市值、股本、价格、可能出现小数的数量字段 |
| `BOOL` | `pa.bool_()` | 仅用于明确布尔字段 |

若字段当前 BQ schema 为 `INT64` 但实测 Parquet 出现 `DOUBLE`，应复核字段语义。若字段属于数量但存在小数或空分区导致自动推断漂移，应将 contract 升级为 `FLOAT64` 并同步更新 BigQuery 外部表 schema；该类变更需要单独列为 breaking schema decision。

整数物理类型加宽到 `FLOAT64` 时，contract review 必须确认字段量级低于 `2^53`，保证整数值可被 IEEE-754 double 精确表示。对 `sz_daily_info.total_share/total_mv` 等大量级字段，应在 repair manifest 中记录修复前最大值、修复后最大值和是否低于 `2^53`；超过该阈值的字段不得自动转 `FLOAT64`，必须进入 `manual_review`。

## 8. 修复流程

### 8.1 Phase 0: 盘点与冻结

1. 列出 10 张表 `partition_date >= '20190101'` 的所有 GCS Parquet 文件。
2. 按文件读取 pyarrow schema，生成 `schema_inventory`。
3. 与 BigQuery `INFORMATION_SCHEMA.COLUMNS` 和 schema contract 对比。
4. 标记每个文件的修复状态：
   - `ok`
   - `schema_mismatch`
   - `read_failed`
   - `missing_file`
   - `manual_review`
5. `ok` 表示文件 schema 已匹配 contract，修复脚本必须跳过重写、跳过发布、只记录 inventory；该规则用于保证重复执行幂等。

### 8.2 Phase 1: P0 源表修复

先修 `ods_tushare_stk_limit`：

1. 读取所有 2019+ 分区原 Parquet。
2. 按 contract 将 `pre_close`, `up_limit`, `down_limit` 等业务字段写成稳定 `FLOAT64`。
3. 写 staging prefix。
4. 验证 staging 行数、schema、null count。
5. 建临时 BigQuery external table 指向 staging，临时表 schema 必须从 schema contract 显式生成，禁止使用 autodetect。
6. 执行目标列读取：

```sql
SELECT
  COUNT(pre_close) AS pre_close_cnt,
  COUNT(up_limit) AS up_limit_cnt,
  COUNT(down_limit) AS down_limit_cnt
FROM `<temp_dataset>.ods_tushare_stk_limit_repair_staging`
WHERE partition_date >= '20190101';
```

7. 备份正式文件，发布 staging 文件到正式 prefix。
8. 对正式 ODS 执行同样 QA。

### 8.3 Phase 2: P1/P2/P3 表批量修复

按优先级分批：

1. P1：`limit_list_d`, `moneyflow`, `margin_detail`, `dividend`
2. P2：`margin`, `daily_info`, `sz_daily_info`, `fina_audit`
3. P3：`stk_rewards`

每批均按 Phase 1 同一流程执行。每批发布后必须生成修复报告并更新 repair manifest。

### 8.4 Phase 3: Ingestion 防复发

修复 ingestion / Parquet 生成侧：

1. 写 Parquet 前按 schema contract 显式 cast。
2. 空 DataFrame 走 empty-return event，不写伪空 Parquet。
3. 对全 NULL 或全整数的浮点字段，仍按 `pa.float64()` 写入。
4. 写入 staging 后先读回 pyarrow schema 校验。
5. schema mismatch 阻断 publish。

## 9. 备份与发布

### 9.1 路径约定

正式 raw 路径保持现有 Hive 分区结构：

```text
gs://data-aquarium/a-share/tushare/raw_data/api=<api>/endpoint=<endpoint>/partition_date=<YYYYMMDD>/data.parquet
```

staging 路径：

```text
gs://data-aquarium/a-share/tushare/repair_staging/run_id=<run_id>/api=<api>/endpoint=<endpoint>/partition_date=<YYYYMMDD>/data.parquet
```

backup 路径：

```text
gs://data-aquarium/a-share/tushare/repair_backup/run_id=<run_id>/api=<api>/endpoint=<endpoint>/partition_date=<YYYYMMDD>/data.parquet
```

### 9.2 发布规则

1. staging 校验通过后才能发布。
2. 发布前必须完成 backup copy。
3. backup 对每个 `(endpoint, partition_date, source_uri)` 执行 write-once 语义：目标 backup object 已存在时不得覆盖，只记录 `backup_status='existing'` 并复用该 URI。重复修复或二次发布时，不能把已修复版本覆盖到原始备份路径。
4. 若正式源文件当前 schema 已匹配 contract，发布流程必须跳过该文件，不创建新 backup、不覆盖正式 prefix。
5. repair manifest 必须记录：
   - `run_id`
   - `endpoint`
   - `partition_date`
   - `source_uri`
   - `staging_uri`
   - `backup_uri`
   - `backup_status`
   - `published_uri`
   - `source_row_count`
   - `staging_row_count`
   - `source_schema`
   - `target_schema`
   - `null_count_before`
   - `null_count_after`
   - `status`
   - `error_summary`
6. 发布后正式 ODS 外部表 QA 失败时，按 backup 回滚。

## 10. QA 门禁

### 10.1 文件级 QA

每个文件修复后检查：

- pyarrow schema 与 contract 一致；
- 行数不变；
- 字段集合不变；
- 修复目标列 null count 与修复前一致，或差异可解释并记录；
- 非目标字段 hash 或抽样值一致；
- 文件可被 pyarrow 重新读取。

### 10.2 BigQuery 临时外部表 QA

staging 发布前，对 staging 建临时 external table。临时表 schema 必须直接取自 schema contract，不能使用 BigQuery autodetect；验证目标是确认 staging 文件能满足既定 contract，而不是让 BigQuery 重新推断类型。临时表创建后执行：

- `SELECT COUNT(*)`；
- 所有业务列 `COUNT(column)`；
- 目标 mismatch 列 `MIN/MAX/COUNT`；
- `partition_date >= '20190101'` 范围读取；
- 按 endpoint 的关键日期字段非空检查。

### 10.3 正式 ODS QA

发布后，对正式 10 张 ODS 表执行：

```sql
SELECT COUNT(<business_column>)
FROM `data-aquarium.ashare_ods.<ods_table>`
WHERE partition_date >= '20190101';
```

所有业务列都必须可读。`ods_tushare_stk_limit` 还必须通过当前 P0 依赖链最小验证：

```sql
SELECT
  COUNT(pre_close) AS pre_close_cnt,
  COUNT(up_limit) AS up_limit_cnt,
  COUNT(down_limit) AS down_limit_cnt
FROM `data-aquarium.ashare_ods.ods_tushare_stk_limit`
WHERE endpoint = 'stk_limit'
  AND partition_date >= '20190101';
```

### 10.4 下游 QA

`ods_tushare_stk_limit` 修复发布后，执行：

- `sql/dwd/01_dwd_stock_eod_price.sql` dry-run；
- `sql/qa/01_core_smoke_checks.sql`；
- `sql/qa/02_strategy1_dws_ads_checks.sql`；
- `sql/qa/05_unit_contract_checks.sql` 中与价格 / 单位相关的现有断言。

若只修 raw schema、不重建 DWD，可先执行 dry-run 与 ODS 读取 QA；重建 DWD 时再跑完整 P0 / 策略 1 QA。

## 11. API 重拉补救路径

API 重拉仅在以下场景启用：

1. 原 GCS Parquet 文件损坏，pyarrow 也无法读取。
2. 原文件缺失，且有明确分区应存在。
3. 行数与历史 manifest / BigQuery 元数据不一致，无法从原文件修复。
4. owner 明确要求以当前 API 快照重建某批历史 raw。

启用 API 重拉时必须遵守数据审查规则：

- 先查官方文档确认 endpoint 起始日期和请求参数；
- API 返回行数命中单次上限时继续拆细请求；
- 事件 / 财务 / 公告类接口保留多快照和多版本；
- 不写伪空 Parquet；
- 写入前仍按 schema contract 显式 cast；
- 重拉报告必须记录请求参数、row limit 命中状态、分区范围和与原文件差异。

## 12. 验收标准

本 PRD 对应实现完成后，验收标准如下：

1. 10 张目标 ODS 外部表 2019+ 所有业务列均可被 BigQuery 读取。
2. `ods_tushare_stk_limit` 的 `pre_close/up_limit/down_limit` 均可读，且 P0 最小 QA 通过。
3. 每个 endpoint 有 schema contract。
4. 每个修复 run 有 repair manifest、backup URI 和修复报告。
5. 修复前后行数一致；null count 差异为 0 或有明确记录。
6. 正式 GCS raw 路径发布前已完成 write-once backup；重复执行不会覆盖原始 backup。
7. ingestion / Parquet 写入侧已接入 schema contract 和显式 cast。
8. 新增或后续重跑的分区不会再次出现本次类型漂移。
9. 修复过程未向 repo、日志、memory 或报告写入 token / key / 凭据。

## 13. 风险与控制

| 风险 | 影响 | 控制 |
|---|---|---|
| contract 类型定错 | 后续 DWD 口径错误 | contract review + 官方文档 + 字段语义复核 |
| 覆盖正式文件后发现异常 | ODS 读取或下游失败 | write-once backup prefix + repair manifest + 回滚流程 |
| pyarrow cast 引入值变化 | 数据值被改写 | 行数 / null count / 抽样值 / 非目标字段 hash 验证 |
| 大整数加宽到 FLOAT64 后丢精度 | 股本 / 市值等字段值被改变 | contract review 检查 `<2^53`，超过阈值进入 manual_review |
| API 重拉引入口径变化 | 历史 raw 与原始采集不一致 | API 重拉仅作补救路径，并独立记录差异 |
| ingestion 未修复 | 新分区继续 mismatch | publish 前 schema check 阻断 |
| P1/P2 表延后修复 | 后续特征开发被卡住 | P0 先修，P1/P2/P3 分批修，所有接入 PR 前强制 QA |

## 14. 实施顺序

1. 合并本 PRD。
2. 新增 schema contract 和 repair 脚本。
3. dry-run 盘点 10 张表 2019+ 文件 schema。
4. 修复并发布 `ods_tushare_stk_limit`。
5. 跑 ODS QA + P0 最小 QA。
6. 分批修复 P1/P2/P3 其余 9 张表。
7. 修复 ingestion / Parquet 生成侧显式 cast。
8. 将 `06_ods_parquet_schema_checks.sql` 加入数据审查 / 生产采集门禁。
