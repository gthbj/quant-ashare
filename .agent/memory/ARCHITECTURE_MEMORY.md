# 架构记忆（Architecture Memory）

## 数据流

```text
Tushare 等数据源
  -> data-aquarium.ashare_ods   ODS 外部表（Hive 分区，原样）
  -> ashare_dim / ashare_dwd    维度 + 明细（清洗/去重/复权/PIT/单位归一）
  -> ashare_dws                 (sec_code, trade_date) 特征宽表 + 标签
  -> ashare_ads (可选)          选股池 / 组合 / 回测输入
```

## ODS 三类分区语义（建模地基，务必牢记）

| 类 | 语义 | 例 | 处理方式 |
|---|---|---|---|
| A 行情增量 | `partition_date == trade_date`，单日单分区、无重复，历史自 1990-12-19 | daily, adj_factor, daily_basic, moneyflow, stk_limit, suspend_d | 按 partition_date 增量裁剪 |
| B 财务/公告 | `partition_date == 报告期(end_date)`，**非公告日**；同期多 report_type/修正 | income, balancesheet, cashflow, fina_indicator | 用 ann_date_eff 做 PIT；按 (sec_code,报告期) 去重 |
| C 维度快照 | 每个 partition_date 一份全量，取最新分区 | stock_basic, trade_cal, index_classify | 取 MAX(partition_date)；stock_basic 需 UNION listed+delisted |

## 目标表（P0 优先级）

| 层 | 表 | 源 | 粒度 |
|---|---|---|---|
| dim | dim_trade_calendar | trade_cal | (exchange, cal_date) |
| dim | dim_stock | stock_basic(listed+delisted) | sec_code |
| dim | dim_stock_name_hist | namechange | (sec_code, start_date) SCD2 |
| dwd | dwd_stock_eod_price | daily+adj_factor+stk_limit+suspend_d | (sec_code, trade_date) |
| dwd | dwd_stock_eod_valuation | daily_basic | (sec_code, trade_date) |
| dwd | dwd_fin_indicator | fina_indicator | (sec_code, report_period) PIT |
| dwd | dwd_fin_indicator_latest | dwd_fin_indicator | (sec_code, report_period) 最新版本便捷表 |
| dwd | dwd_index_eod | index_daily + index_dailybasic | (sec_code, trade_date) |

完整 54 张 ODS→DWD/DIM 映射见 `docs/数据仓库建模方案-DWD-DIM.md` §2。

## SQL 代码布局

- 根目录 `sql/` 存放 P0 BigQuery Standard SQL：`00_create_datasets.sql`、`dim/*.sql`、`dwd/*.sql`。
- 现有脚本覆盖 3 张 DIM + 5 张 DWD，使用 `CREATE OR REPLACE TABLE` + CTAS + 后置 `ALTER COLUMN SET OPTIONS`；`sql/qa/01_p0_smoke_checks.sql` 存放物化后基础断言。
- 当前脚本是 bootstrap SQL，不关闭 OQ-005；后续仍可迁移为 dbt 或纳入 Airflow 调度。
- 2026-05-31 P0 已物化到 BigQuery；`dwd_index_eod` 已恢复读取 `index_dailybasic`。该接口市值/股本单位为元/股，不做 `*10000` 换算。

## 物理规范（BigQuery）

| 表类 | 分区键 | 聚簇键 | require_partition_filter |
|---|---|---|---|
| 行情 DWD | `DATE_TRUNC(trade_date, MONTH)` | `sec_code` | TRUE |
| 财务 DWD | `DATE_TRUNC(ann_date_eff, MONTH)` | `sec_code` | 不开（as-of 模式） |
| 普通 DIM | 不分区 | `sec_code` | — |
| 时序 DIM（index_weight） | `DATE_TRUNC(trade_date, MONTH)` | `index_code, sec_code` | 视情况 |

- **按月分区**而非按天：BigQuery 单表上限 4000 分区，按天全史 ~8700 交易日会超限；本表数据量小，按天碎片化。
- DWD/DIM 物化为**原生表**，不再是外部表；下游一律查 DWD 不直接打 ODS。
- 2019 年前数据范围三分：财务/事件按分区前移到 `20170101`；行情 DWD/DWS 最终写 `trade_date >= 2019-01-01`、构建时读取 lookback buffer；维度/日历取最新快照或全量历史事件。

## 命名规范要点（详见 docs §3.3 + DECISION_LOG）

- 证券主键 `sec_code`（`600000.SH`），辅助 `sec_symbol`、品种 `sec_type`。
- 日期：`trade_date`/`cal_date`/`pre_trade_date`/`ann_date_eff`/`report_period`/`ex_date`。
- 量纲统一元/股；复权后缀 `_hfq`/`_qfq`，收益 `ret_1d`/`fwd_ret_Nd`。
- 血缘 `source_system` + `ingested_at`。
- **ODS 源字段保留原名（如 ts_code），仅在 DWD/DIM 出口 rename + 单位换算。**

## 表/字段注释

所有 dim/dwd/dws 表带表级 + 字段级中文 description；财务大表字段描述**继承 ODS 同名字段**（脚本化），改名/派生/换算字段手写。详见 docs §3.4。
