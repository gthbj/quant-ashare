# 实现状态（Implementation Status）

这是实现状态的唯一事实来源。面向「已完成/进行中/受阻的整体状态」；「下一步要做什么」见根目录 `TODO.md`。

Last updated: 2026-05-31

## 当前状态

项目处于**设计完成、P0 建表 SQL 已落地但尚未物化**阶段。已产出 DWD/DIM 建模方案文档，并已修订 §4.6 的 2019 前数据范围。owner 澄清：财务/事件按分区前移到 2017，行情最终写 2019+ 但构建时读 2018 lookback buffer，维度/日历取最新快照或全量历史事件。根目录 `sql/` 已新增 BigQuery Standard SQL 脚本，覆盖 P0 DIM/DWD；尚无任何已物化的 BigQuery DWD/DIM 表，无调度代码。

## 已完成（Completed）

- ODS 探查：`ashare_ods` 全部 54 张外部表的字段与分区语义已摸清（三类分区：A 行情增量 / B 财务报告期 / C 维度快照）。
- DWD/DIM 建模方案文档 `docs/数据仓库建模方案-DWD-DIM.md` 定稿：分层、54 表映射、五条铁律、DIM/DWD 逐表设计、DWS 衔接、工程建议、路线图、风险项。
- 命名规范敲定：`sec_code` 主键、`trade_date/cal_date`、`ann_date_eff`、单位元/股、复权 `_hfq/_qfq`、血缘 `source_system/ingested_at`。
- 物理设计敲定：按月分区 + `sec_code` 聚簇、行情表 `require_partition_filter=TRUE`。
- 2019 前数据范围敲定：财务/事件 `partition_date >= '20170101'`；行情 DWD/DWS 写 `trade_date >= 2019-01-01`、构建时按最大窗口读取 2018 lookback buffer；维度/日历取最新快照或全量历史事件。
- 表/字段注释规范敲定：内联 DDL / 后置 ALTER / 继承 ODS 描述三法。
- 仓库初始化：`git init` + `.gitignore` + 首个 commit（`main`）。
- 建立 `.agent/` Agent 工作记忆体系 + 根 `AGENTS.md` 读写协议；推送 GitHub（gthbj/quant-ashare）；加模型署名协议。
- 按实测 review 整改建模方案（9 采纳 / 2 调整）：财务版本事实表、价格表「交易日历×在市」骨架（含停牌日）、表级可见日规则（`fina_indicator` 用 `ann_date`）、ODS 元数据矩阵、lookback buffer、方向性可交易、`visible_trade_date`、表数订正 54；写 `docs/reviews/…-review-response.md`。
- 修正早先“全历史写入”误读：`docs/reviews/数据仓库建模方案-DWD-DIM-review-2019前数据范围修正.md` 已改为 2019 前数据范围修正说明；主方案 §4.6 已新增范围表。
- 主方案文首和 TL;DR 已显式说明：当前建模范围是 2019-01-01 之后的 A 股日线 DWD/DWS；2019 年以前数据仅作为 PIT / lookback / 维度历史支撑。
- P0 建表 SQL 已落地到 `sql/`：`00_create_datasets.sql`、3 张 DIM、4 张 DWD。脚本采用 `CREATE OR REPLACE TABLE`、月分区、`sec_code` 聚簇、范围参数 `dwd_start_date/fin_start_period/lookback_start_date`。
- SQL 校验完成：dataset/DIM 脚本 dry-run 通过；`dwd_stock_eod_valuation`、`dwd_index_eod` dry-run 通过；`dwd_stock_eod_price`、`dwd_fin_indicator` 因目标 DIM 尚未物化，使用临时空维表替换后 dry-run 通过。未实际写入 BigQuery。

## 进行中 / 部分（In Progress）

- P0 SQL 已可执行，下一步是按 `sql/README.md` 执行物化并做基础数据质量 QA。
- P0 建表 SQL 已评审，结论见 `docs/reviews/P0-建表SQL-review.md`：5 项发现，2 项物化前必修（README 加 `--location=asia-east2`；`suspend_d` 复牌行过滤），3 项随 QA 补（fin 版本键去重兜底、`dim_stock` 唯一性断言、补 `dwd_fin_indicator_latest`）。发现是否转 TODO/OQ 待 owner 决定。已确立评审协议（AGENTS.md §六 / DECISION-20260531-13）。

## 未开始 / 未来（Not Started / Future）

- P0 BigQuery 物化执行与 QA：行数、主键唯一性、分区范围、停牌骨架、PIT `visible_trade_date`。
- `lookback_start_date` 从固定默认值升级为按最大滚动窗口计算/调度配置。
- 「从 ODS 继承字段描述」的脚本（bq show → 映射 → bq update）。
- 增量调度（dbt 或 Airflow + SQL）、数据质量断言。
- DWS 特征宽表 + 标签（`fwd_ret_1d/5d/10d/20d`）+ 基线模型。
- P1+ 资金面/事件/行业族 DWD。
- 个股标准申万行业映射补采（ODS 暂缺 `index_member`，见 OPEN_QUESTIONS）。

## Coverage Snapshot

| 能力 | 状态 | 备注 |
|---|---|---|
| ODS 理解 | 高 | 54 表字段+分区语义已探明 |
| DWD/DIM 设计 | 高 | 主文档已完成；§4.6 已修订 2019 前数据范围 |
| 命名/单位/分区/注释规范 | 高 | 已敲定并写入文档 |
| P0 建表 SQL | 已完成 | `sql/` 已新增 3 张 DIM + 4 张 DWD；dry-run 校验通过 |
| P0 表物化/QA | 未开始 | 尚未执行建表脚本 |
| ETL/调度 | 未开始 | — |
| DWS 特征/标签 | 未开始 | — |
| 行业映射 | 受阻 | ODS 缺 index_member（OQ-001） |
