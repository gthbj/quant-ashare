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

- P0 数仓底座、财务三大报表、benchmark 口径、单位契约、ODS schema 防复发、OQ-005 调度迁移与 true-five-year 数据覆盖修复均已完成或关闭。
- Strategy1 已完成 research-first / promotion 架构、package entrypoint、年度 final refit + synthetic continuous、lot-aware / resume / CA-on ledger 契约链路。
- 当前研究 baseline 为 true-five-year CA-on：prediction `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01`，backtest `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01`。
- baseline 指标锚点：CAGR `15.36%` (`0.153578`)、v3 contract Sharpe `0.6685`、Calmar `0.4103`、MaxDD 不变；2026-06-12 dividend 补采后 resume 修正，child `bt_s1_dividend_backfill_resume_20260528_20260609_v20260612_01`，详见 `docs/分析-dividend-ODS补采与CA-Resume补跑-20260612.md`；仍未过 v3 hard gates，baseline ≠ accepted，不得 promotion。
- 当前开放主线只剩 OQ-010：继续寻找可 accepted 的 Cloud Run Python baseline / 组合构造 / 风控路线。
- 下一步执行项以 `TODO.md` 为准；完整现状快照见 `IMPLEMENTATION_STATUS.md`。

## 不可妥协的约定

- 证券主键统一 `sec_code`（数据源中性，值标准格式 `600000.SH`）。
- 金额单位统一「元」、数量单位统一「股」。
- DWD 事实表统一带血缘字段 `source_system` + `ingested_at`。
- DWS/ADS 必须带版本与运行追踪字段（如 `feature_version`、`label_version`、`universe_version`、`model_id`、`strategy_id`、`run_id`）。
- 2019 年前数据不能混作“全历史写入”：财务/事件前移到 2017；行情写 2019+ 但读 lookback buffer；维度/日历取快照或全量历史事件。
- 记忆文件、文档、代码中均不得出现 BigQuery key / Tushare token 等凭据。
