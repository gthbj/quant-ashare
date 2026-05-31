# 实现状态（Implementation Status）

这是实现状态的唯一事实来源。面向「已完成/进行中/受阻的整体状态」；「下一步要做什么」见根目录 `TODO.md`。

Last updated: 2026-05-31

## 当前状态

项目处于**设计完成、建表未开始**阶段。已产出一份定稿的 DWD/DIM 建模方案文档，命名/单位/分区/回填/注释规范全部敲定。仓库已 `git init`（`main`，首个 commit）。尚无任何已物化的 BigQuery DWD/DIM 表，无 ETL 代码。

## 已完成（Completed）

- ODS 探查：`ashare_ods` 全部 56 张外部表的字段与分区语义已摸清（三类分区：A 行情增量 / B 财务报告期 / C 维度快照）。
- DWD/DIM 建模方案文档 `docs/数据仓库建模方案-DWD-DIM.md` 定稿：分层、56 表映射、五条铁律、DIM/DWD 逐表设计、DWS 衔接、工程建议、路线图、风险项。
- 命名规范敲定：`sec_code` 主键、`trade_date/cal_date`、`ann_date_eff`、单位元/股、复权 `_hfq/_qfq`、血缘 `source_system/ingested_at`。
- 物理设计敲定：按月分区 + `sec_code` 聚簇、行情表 `require_partition_filter=TRUE`。
- 回填范围敲定：行情 `>=20190101`，财务前移 `>=20170101`，维度/日历不截断。
- 表/字段注释规范敲定：内联 DDL / 后置 ALTER / 继承 ODS 描述三法。
- 仓库初始化：`git init` + `.gitignore` + 首个 commit（`main`）。
- 建立 `.agent/` Agent 工作记忆体系 + 根 `AGENTS.md` 读写协议。

## 进行中 / 部分（In Progress）

- 无。

## 未开始 / 未来（Not Started / Future）

- P0 建表 SQL：`dim_trade_calendar`、`dim_stock`、`dim_stock_name_hist`、`dwd_stock_eod_price`、`dwd_stock_eod_valuation`、`dwd_fin_indicator`、`dwd_index_eod`。
- 「从 ODS 继承字段描述」的脚本（bq show → 映射 → bq update）。
- 增量调度（dbt 或 Airflow + SQL）、数据质量断言。
- DWS 特征宽表 + 标签（`fwd_ret_1d/5d/10d/20d`）+ 基线模型。
- P1+ 资金面/事件/行业族 DWD。
- 个股标准申万行业映射补采（ODS 暂缺 `index_member`，见 OPEN_QUESTIONS）。

## Coverage Snapshot

| 能力 | 状态 | 备注 |
|---|---|---|
| ODS 理解 | 高 | 56 表字段+分区语义已探明 |
| DWD/DIM 设计 | 高 | 文档定稿 |
| 命名/单位/分区/注释规范 | 高 | 已敲定并写入文档 |
| P0 建表 SQL | 未开始 | 下一步 |
| ETL/调度 | 未开始 | — |
| DWS 特征/标签 | 未开始 | — |
| 行业映射 | 受阻 | ODS 缺 index_member（OQ-001） |
