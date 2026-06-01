# 待决问题（Open Questions）

> 本文件只保留待 owner / 维护者 / 指定决策流程解决的开放问题。已关闭问题归档到 `archive/CLOSED_QUESTIONS.md`。

待决问题需由 owner / 维护者 / 指定决策流程解决。

| ID | 问题 | 状态 | Owner | 相关文件 |
|---|---|---|---|---|
| OQ-003 | 财务 `report_type` 口径：默认取合并报表 `'1'`；是否需要母公司/单季调整等口径维度？PRD 已提出 P0 默认合并报表、DWD 保留口径字段、DWS 默认过滤的推荐方案，且已跟进 PR #8 review comment 与 NULL-safe QA 细节。 | open: PRD 待 owner review | owner | docs §6.5, §10; `docs/prd/PRD_20260601_03_财务报表口径维度.md` |
| OQ-004 | 基准指数代码可用性：中证1000/中证2000/国证2000 等需以 ODS `index_daily` 实际存在的 `ts_code` 端点为准，并维护 `source_sec_code -> sec_code` canonical 映射；前次复核到当前实际端点不含 `000300.SH`，但可由 `399300.SZ` 映射。其余基准仍需核对端点、起点和映射。 | open | owner | docs §6.4, §10; docs/reviews/数据仓库建模方案-DWD-DIM-review-2019前数据范围修正.md; docs/prd/PRD_20260601_02_策略1BQML回测闭环.md |
| OQ-005 | 物化与调度选型：用 dbt（含 `persist_docs` 刷描述）还是纯 `bq` SQL 脚本 + 自建调度？ | open | owner | docs §3.4, §8 |
| OQ-006 | 金额单位逐接口换算系数表尚未逐一核对（仅核对了 daily 等核心表）；其余表落库前需逐接口确认。 | open | owner | docs §3.3-G, §10 |
| OQ-010 | P0 策略默认参数待确认：回测成本参数、默认调仓频率、持股数/单票权重上限、北交所是否纳入首个基线。首个模型训练工具链已定为 BigQuery ML + SQL runner。 | open | owner | docs/数据仓库建模方案-DWS-ADS.md §10; docs/A股中低频小资金机器学习策略方案.md §12; docs/策略1-ml_pv_clf_v0-runner设计.md; docs/prd/PRD_20260601_02_策略1BQML回测闭环.md |
| OQ-011 | 策略 1 价格 DWS 是否需要补 lookback-capable 构建输入，使 2019-01 起 60 日窗口完整？当前已物化版本只读取最终 DWD/DIM，不直接打 ODS，2019 年初窗口以 `has_full_history_60d=FALSE` 显式标记并由默认样本掩码剔除。 | open | owner | docs/prd/PRD_20260601_01_策略1价格量价基础分类模型.md §3.3; docs/prd/PRD_20260601_02_策略1BQML回测闭环.md; sql/dws/02_dws_stock_feature_price_daily.sql; sql/qa/02_strategy1_dws_ads_checks.sql |
