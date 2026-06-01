# 项目背景（Project Context）

## 项目目标

`quant-ashare` 是一套基于 **BigQuery** 的 **A 股日线量化数据仓库**，服务于
**A 股 · 日线 · 中低频 · 小资金 · 机器学习量化** 场景。

最终消费物：以 `(sec_code, trade_date)` 为主键的**特征宽表 + 标签**，供 ML 模型训练/回测，要求 PIT 正确、无未来泄露、横截面规整、可复现。

## 数据底座

- 平台：BigQuery，项目 `data-aquarium`。
- ODS：数据集 `ashare_ods`，57 张 Tushare 来源的 **Hive 分区外部表**（分区键 `partition_date` + `endpoint`，强制分区裁剪）。
- 目标分层：`ashare_dim`（维度）+ `ashare_dwd`（明细）→ `ashare_dws`（特征/标签）→ `ashare_ads`（策略消费）。

## 分层架构

```text
ashare_ods (已有, 外部表)
  -> ashare_dim   维度：主数据 + 缓变维 + SCD2 时间线
  -> ashare_dwd   明细：清洗/去重/标准化/复权/PIT 对齐
  -> ashare_dws   特征宽表 + 标签（ML 直接消费）
  -> ashare_ads   训练面板 / 模型预测 / 候选池 / 组合 / 回测 / 监控
```

## 核心原则（量化语境五条铁律）

1. **PIT**：财务特征可见时间用按表定义的 `ann_date_eff`（如 income/bs/cf 用 `COALESCE(f_ann_date, ann_date)`，`fina_indicator` 用 `ann_date`），严禁用报告期/分区当可见时间。
2. **复权**：收益率与技术指标用后复权（`_hfq`）；前复权（`_qfq`）含未来信息，不入训练特征。
3. **幸存者偏差**：universe 必须含已退市股的历史区间。
4. **可交易性**：停牌、一字板、上市未满 N 日、ST 需打标做样本掩码。
5. **去重**：行情表按分区天然唯一；财务表按 `(sec_code, 报告期)` + 公告日 + `update_flag` 去重取最新修正。

## 当前阶段

- DWD/DIM 建模方案文档已完成：`docs/数据仓库建模方案-DWD-DIM.md`。
- DWS/ADS 表设计文档已完成：`docs/数据仓库建模方案-DWS-ADS.md`。
- 策略设计文档已完成：`docs/A股中低频小资金机器学习策略方案.md`。
- 2026-05-31 owner 澄清 2019 年前数据范围：财务/事件按分区前移到 2017；行情最终写 2019+、构建时按最大滚动窗口读 2018 lookback buffer；维度/日历取最新快照或全量历史事件。主方案 §4.6 已按该口径修订。
- 命名规范、单位、分区/聚簇、表/字段注释规范均已敲定；2019 前数据范围见 `DECISION_LOG.md` 最新决策。
- 仓库已 `git init`（默认分支 `main`）。
- P0 建表 SQL 已落地到 `sql/`，并已按 `docs/reviews/P0-建表SQL-review.md` 修复首轮评审发现：显式 BigQuery location、复牌行过滤、`dim_stock` 稳健性、财务版本键去重兜底、`dwd_fin_indicator_latest` 与 QA 脚本。
- P0 DIM/DWD 已物化到 BigQuery 并通过 `sql/qa/01_p0_smoke_checks.sql`。已建 3 张 DIM + 5 张 DWD；`dwd_index_eod` 已恢复 `index_dailybasic` 估值/股本字段，STAR50/CSI1000 因 ODS 暂无对应 dailybasic endpoint 仍为空。
- P0 二轮评审发现已修复：`dwd_stock_eod_price` 拆分全天停牌与盘中临停语义；`dwd_fin_indicator_latest` 改为 `update_flag DESC` 优先取最新修正版；相关表已重建并通过 QA。
- 2026-05-31 ODS 已补采 `index_member_all` 与 `ci_index_member`，可落地申万/中信个股行业时点映射维表；OQ-001 已关闭。
- **下一步**：补 `income` / `balancesheet` / `cashflow` 财务三表；或落地 P0 DWS/ADS SQL（universe、价格/估值/财务特征、市场状态、标签、训练面板、预测/候选/组合/回测表）和 `ml_ranker_v0` 基线回测。

## 不可妥协的约定

- 证券主键统一 `sec_code`（数据源中性，值标准格式 `600000.SH`）。
- 金额单位统一「元」、数量单位统一「股」。
- DWD 事实表统一带血缘字段 `source_system` + `ingested_at`。
- DWS/ADS 必须带版本与运行追踪字段（如 `feature_version`、`label_version`、`universe_version`、`model_id`、`strategy_id`、`run_id`）。
- 2019 年前数据不能混作“全历史写入”：财务/事件前移到 2017；行情写 2019+ 但读 lookback buffer；维度/日历取快照或全量历史事件。
- 记忆文件、文档、代码中均不得出现 BigQuery key / Tushare token 等凭据。
