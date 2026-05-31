# 已知约束（Known Constraints）

## 数据约束（Tushare / ODS 事实）

- ODS 全部为 Hive 分区外部表，**查询必须带 `partition_date`/`endpoint` 过滤**（强制分区裁剪），否则报错。`partition_date` 是 `YYYYMMDD` 字符串。
- **财务表 `partition_date == 报告期(end_date)`，不是公告日**：禁止用 partition_date 当数据可见时间，必须用 `ann_date_eff = COALESCE(f_ann_date, ann_date)` 做 PIT。
- 财务表同一 `(sec_code, 报告期)` 有多条（不同 `report_type`/修正/`update_flag`）：必须去重取最新修正版（通常 `report_type='1'` 合并报表）。
- `stock_basic` 用 `endpoint` 分 `listed`/`delisted`：**必须 UNION 两者**，否则丢失退市股 → 幸存者偏差。
- 行情历史自 **1990-12-19**；行情表单分区内 `(ts_code, trade_date)` 已唯一、无需去重。
- **`fina_indicator` 无 `f_ann_date`**（实测）：其可见日只能用 `ann_date`；可见日规则**按表定义**，不可用统一 `COALESCE(f_ann_date,ann_date)` 公式覆盖所有财务表（见 docs §4.3）。
- **`stock_basic_delisted.delist_date` 类型不一致**（外部表 `INT64` / Parquet `BYTE_ARRAY`）：直读报错、`SAFE` 无效；`dim_stock` 用「`daily` 最后交易日」兜底退市日（OQ-007）。
- **停牌日 `daily` 无该股行**：价格 DWD 必须以「交易日历开市日 × 在市股票」为骨架（保留停牌日空行），不能从 `daily` 起表，否则停牌日整行消失、`t+k` 标签错位。
- Tushare 各接口金额/量单位不一（手/千元/万股/万元）：落库须按「表+字段」归一到元/股。
- 部分数值字段在 ODS 是 STRING（如 `moneyflow_hsgt`、`ccass_hold`）：落库须 `SAFE_CAST`。
- 北向数据（hk_hold / moneyflow_hsgt）2024 年后部分口径变化/停更，需做可用性标记。

## 平台约束（BigQuery）

- **单表最多 4000 个分区**：行情表必须按月分区（`DATE_TRUNC(trade_date, MONTH)`），不能按天。
- **只有分区列能 `require_partition_filter` 强制过滤；聚簇列无法强制**。
- `CREATE TABLE AS SELECT` 不能在 SELECT 列上内联 description：维度表用内联列定义 DDL，事实表用 CTAS + 后置 `ALTER COLUMN SET OPTIONS`。
- 外部表的列描述/分区元数据通过 `bq show`/`INFORMATION_SCHEMA` 获取。

## 建模约束（PIT / 量化正确性）

- 前复权价（`_qfq`）隐含未来除权信息，**不得作为训练特征**；技术指标/收益用后复权（`_hfq`）。
- 标签必须与特征时间错位：`t` 日特征 → 标签从 `t+1` 起算（入场价用 `t+1`）。
- universe 必须含退市股历史区间，并打标停牌/一字板/上市未满 N 日/ST 做样本掩码。
- 涨跌停价直接用 `stk_limit.up_limit/down_limit`（已按板块算好），不要自己按板块硬编码。

## 安全约束（红线）

- 仓库、记忆文件、文档、日志中**绝不可出现**：BigQuery service account key、Tushare token、任何 API key / 凭据 / 个人隐私。
- 凭据通过环境变量 / 受信环境注入；`.gitignore` 已忽略 `*.key`/`credentials*.json`/`.env` 等。

## 工程约束

- DWD/DIM 物化后，下游一律查 DWD/DIM，不直接打 ODS。
- 长历史回填分批（按年/季）跑，避免单次扫描 35 年全量。
- 提交（commit/push）仅在用户明确要求时进行。
