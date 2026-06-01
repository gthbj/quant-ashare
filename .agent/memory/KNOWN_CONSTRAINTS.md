# 已知约束（Known Constraints）

## 数据约束（Tushare / ODS 事实）

- ODS 全部为 Hive 分区外部表，**查询必须带 `partition_date`/`endpoint` 过滤**（强制分区裁剪），否则报错。`partition_date` 是 `YYYYMMDD` 字符串。
- **财务表 `partition_date == 报告期(end_date)`，不是公告日**：禁止用 partition_date 当数据可见时间，必须用 `ann_date_eff = COALESCE(f_ann_date, ann_date)` 做 PIT。
- 财务表同一 `(sec_code, 报告期)` 有多条（不同 `report_type`/修正/`update_flag`）：必须去重取最新修正版（通常 `report_type='1'` 合并报表）。
- `dwd_fin_indicator_latest` 是便捷最新表，不用于 PIT 回测 join；其版本排序按 `update_flag DESC, ann_date_eff DESC, ingested_at DESC, source_partition_date DESC`，优先保留修正版。
- `stock_basic` 用 `endpoint` 分 `listed`/`delisted`：**必须 UNION 两者**，否则丢失退市股 → 幸存者偏差。
- 行情历史自 **1990-12-19**；行情表单分区内 `(ts_code, trade_date)` 已唯一、无需去重。
- 2019 年前数据范围分三类，不能混作“全历史写入”：财务/事件按分区前移到 `20170101`；行情 DWD/DWS 最终写 `trade_date >= 2019-01-01`，构建时按最大滚动窗口读取 2018 lookback buffer；维度/日历取最新快照或全量历史事件。
- 行情 lookback buffer 不落最终 DWD/DWS；`ret_1d` 至少读到 2018 年最后一个交易日，120/250 日滚动特征按窗口多读。
- 当前已物化的策略 1 价格 DWS 只读取最终 DWD/DIM，不直接打 ODS；最终 DWD 价格表不落 2018 buffer 行，因此 2019 年初 60 日窗口以 `has_full_history_60d=FALSE` 显式标记，默认样本掩码剔除这些不完整窗口。若需要 2019-01 起完整 60 日特征，需补专用 lookback-capable 构建输入或调整 DWD/DWS 构建方式。
- **`fina_indicator` 无 `f_ann_date`**（实测）：其可见日只能用 `ann_date`；可见日规则**按表定义**，不可用统一 `COALESCE(f_ann_date,ann_date)` 公式覆盖所有财务表（见 docs §4.3）。
- `stock_basic_delisted.delist_date` 已由上游统一为 `STRING` 并可直读解析；`dim_stock` 应优先使用 ODS 退市日，只有缺值时才用 `daily` 最后交易日加一天兜底（OQ-007 已关闭）。
- **停牌日 `daily` 无该股行**：价格 DWD 必须以「交易日历开市日 × 在市股票」为骨架（保留停牌日空行），不能从 `daily` 起表，否则停牌日整行消失、`t+k` 标签错位。
- **`suspend_d.suspend_type` 区分停牌/复牌**：`S`=停牌，`R`=复牌。价格 DWD 只可用 `S` 标记停牌事件；`R` 复牌日若 daily 有成交，不能判 `is_suspended=TRUE`。
- `S` 事件也可能是盘中临停。若当日 `daily` 有 close 且 volume > 0，不能把该行标为全天停牌；DWD 用 `has_intraday_halt` 标记盘中临停，用 `has_open_halt` 标记开盘时段或未知时段临停并影响开盘建仓掩码。
- Tushare 各接口金额/量单位不一（手/千元/万股/万元）：落库须按「表+字段」归一到元/股。
- 部分数值字段在 ODS 是 STRING（如 `moneyflow_hsgt`、`ccass_hold`）：落库须 `SAFE_CAST`。
- 北向数据（hk_hold / moneyflow_hsgt）2024 年后部分口径变化/停更，需做可用性标记。
- `index_member_all` / `ci_index_member` 已在 ODS 中可用，是最新分区中的全量历史行业归属区间快照；历史 join 必须用 `in_date/out_date`，不能用 `is_new` 回填历史。默认区间口径为 `[in_date, out_date)`，落地前需 QA `out_date` 当天有效性、区间重叠/缺口和 2019+ 覆盖率。
- `dwd_index_eod.sec_code` 应输出 canonical 指数代码；若 ODS 实际代码不同，用 `source_sec_code` 保留来源代码（如 ODS `399300.SZ` → canonical `000300.SH`），DWS/ADS 基准 join 只使用 canonical `sec_code`。

## 平台约束（BigQuery）

- **单表最多 4000 个分区**：行情表必须按月分区（`DATE_TRUNC(trade_date, MONTH)`），不能按天。
- **只有分区列能 `require_partition_filter` 强制过滤；聚簇列无法强制**。
- `CREATE TABLE AS SELECT` 不能在 SELECT 列上内联 description：维度表用内联列定义 DDL，事实表用 CTAS + 后置 `ALTER COLUMN SET OPTIONS`。
- P0 表重建后必须执行 `sql/metadata/01_p0_table_column_descriptions.sql`，集中恢复/补齐表级和字段级中文说明。
- 外部表的列描述/分区元数据通过 `bq show`/`INFORMATION_SCHEMA` 获取。
- `bq query` 执行本项目建表/QA 脚本时显式指定 `--location=asia-east2`，避免无源表脚本或跨数据集 CTAS 使用错误 job 区域。

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
- 大范围回填建议分批（按年/季）跑并记录批次状态；P0 行情最终写 2019+，财务/事件从 2017 起。
- `dim_stock` 若遇到 latest `stock_basic` 缺失但 2019+ daily 有记录的代码，只能作为 `derived_from_daily` 兜底；派生退市边界用 ODS 最新交易日减宽限期判断，不能用系统当前日期直接判退市。
- PR 合并后，若 owner 未要求保留工作分支，应删除已合并且不再使用的 `codex/*` 本地分支和对应远端分支，保持分支列表干净。
- 提交（commit/push）仅在用户明确要求时进行。
