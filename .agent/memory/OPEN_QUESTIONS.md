# 待决问题（Open Questions）

待决问题需由 owner / 维护者 / 指定决策流程解决。

| ID | 问题 | 状态 | Owner | 相关文件 |
|---|---|---|---|---|
| OQ-001 | 个股标准申万行业（L1/L2/L3）时点映射是否补采 Tushare `index_member_all`？ | **closed: 已补采**（ODS 已有 `index_member_all`；同时补入 `ci_index_member`，后续落 `dim_stock_sw_industry_hist` / `dim_stock_ci_industry_hist`） | owner | docs §5.4, DECISION-20260531-19 |
| OQ-002 | 财务回填前移到 `20170101`（保证 2019 初 PIT 完整）。 | **closed: 采纳**（财务/事件前移到 2017；行情仅读 lookback buffer，维度取快照/全量事件） | owner | docs §4.6, DECISION-20260531-11 |
| OQ-003 | 财务 `report_type` 口径：默认取合并报表 `'1'`；是否需要母公司/单季调整等口径维度？ | open | owner | docs §6.5, §10 |
| OQ-004 | 基准指数代码可用性：中证1000/中证2000/国证2000 等需以 `index_daily` 实际存在的 `ts_code` 为准，建仓前核对；前次复核到当前实际端点不含 `000300.SH`，且各指数起点不同。 | open | owner | docs §6.4, §10; docs/reviews/数据仓库建模方案-DWD-DIM-review-2019前数据范围修正.md |
| OQ-005 | 物化与调度选型：用 dbt（含 `persist_docs` 刷描述）还是纯 `bq` SQL 脚本 + 自建调度？ | open | owner | docs §3.4, §8 |
| OQ-006 | 金额单位逐接口换算系数表尚未逐一核对（仅核对了 daily 等核心表）；其余表落库前需逐接口确认。 | open | owner | docs §3.3-G, §10 |
| OQ-007 | ODS `stock_basic_delisted.delist_date` 外部表类型(INT64)与 Parquet 文件(BYTE_ARRAY)不一致、直读报错。是否由上游把该列统一为 STRING？在此之前 `dim_stock` 用「daily 最后交易日」兜底退市日。 | open | owner / 上游 ingestion | docs §5.2, review-response 调整-1 |
| OQ-008 | 全历史早期可交易字段缺口：`stk_limit` 2007 前、`suspend_d` 1999 前不可用。 | **closed: not applicable**（行情最终写 2019+；2018 lookback buffer 内核心可交易辅助表可用，不构成 P0 阻塞） | owner | docs §4.6, review 修正说明 |
| OQ-009 | ODS `index_dailybasic` 多列外部 schema 与 Parquet 物理类型不一致（如 `float_mv`、`float_share`），导致 2019+ 读取失败。 | **closed: upstream fixed + DWD restored**（已恢复 `dwd_index_eod` 估值/股本字段；STAR50/CSI1000 因 ODS 无 dailybasic 端点仍为空） | owner / 上游 ingestion | sql/dwd/04_dwd_index_eod.sql |
| OQ-010 | P0 策略默认参数待确认：回测成本参数、默认调仓频率、持股数/单票权重上限、北交所是否纳入首个基线、首个模型训练工具链。 | open | owner | docs/数据仓库建模方案-DWS-ADS.md §10; docs/A股中低频小资金机器学习策略方案.md §12 |
