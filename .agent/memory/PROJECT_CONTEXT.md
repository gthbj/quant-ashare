# 项目背景（Project Context）

## 项目目标

`quant-ashare` 是一套基于 **BigQuery** 的 **A 股日线量化数据仓库**，服务于
**A 股 · 日线 · 中低频 · 小资金 · 机器学习量化** 场景。

最终消费物：以 `(sec_code, trade_date)` 为主键的**特征宽表 + 标签**，供 ML 模型训练/回测，要求 PIT 正确、无未来泄露、横截面规整、可复现。

## 数据底座

- 平台：BigQuery，项目 `data-aquarium`。
- ODS：数据集 `ashare_ods`，56 张 Tushare 来源的 **Hive 分区外部表**（分区键 `partition_date` + `endpoint`，强制分区裁剪）。
- 目标分层：`ashare_dim`（维度）+ `ashare_dwd`（明细）→ `ashare_dws`（特征/标签）→ 可选 `ashare_ads`（策略）。

## 分层架构

```text
ashare_ods (已有, 外部表)
  -> ashare_dim   维度：主数据 + 缓变维 + SCD2 时间线
  -> ashare_dwd   明细：清洗/去重/标准化/复权/PIT 对齐
  -> ashare_dws   特征宽表 + 标签（ML 直接消费）
```

## 核心原则（量化语境五条铁律）

1. **PIT**：财务特征可见时间用 `ann_date_eff = COALESCE(f_ann_date, ann_date)`，严禁用报告期/分区当可见时间。
2. **复权**：收益率与技术指标用后复权（`_hfq`）；前复权（`_qfq`）含未来信息，不入训练特征。
3. **幸存者偏差**：universe 必须含已退市股的历史区间。
4. **可交易性**：停牌、一字板、上市未满 N 日、ST 需打标做样本掩码。
5. **去重**：行情表按分区天然唯一；财务表按 `(sec_code, 报告期)` + 公告日 + `update_flag` 去重取最新修正。

## 当前阶段

- DWD/DIM 建模方案文档已完成定稿：`docs/数据仓库建模方案-DWD-DIM.md`。
- 命名规范、单位、分区/聚簇、回填范围、表/字段注释规范均已敲定（见 `DECISION_LOG.md`）。
- 仓库已 `git init`（默认分支 `main`）。
- **下一步**：落地 P0 建表 SQL（dim_trade_calendar / dim_stock / dwd_stock_eod_price / dwd_fin_indicator / dwd_index_eod）。

## 不可妥协的约定

- 证券主键统一 `sec_code`（数据源中性，值标准格式 `600000.SH`）。
- 金额单位统一「元」、数量单位统一「股」。
- DWD 事实表统一带血缘字段 `source_system` + `ingested_at`。
- 记忆文件、文档、代码中均不得出现 BigQuery key / Tushare token 等凭据。
