# 已关闭问题归档（Closed Questions Archive）

> 维护：GPT-5（最近更新 2026-06-01）

本文件保存已关闭的 owner / 维护者问题。常规启动不需要读取；仅在追溯历史决策时参考。

| ID | 问题 | 关闭状态 | Owner | 相关文件 |
|---|---|---|---|---|
| OQ-001 | 个股标准申万行业（L1/L2/L3）时点映射是否补采 Tushare `index_member_all`？ | closed: 已补采（ODS 已有 `index_member_all`；同时补入 `ci_index_member`，后续落 `dim_stock_sw_industry_hist` / `dim_stock_ci_industry_hist`） | owner | docs §5.4, DECISION-20260531-19 |
| OQ-002 | 财务回填前移到 `20170101`（保证 2019 初 PIT 完整）。 | closed: 采纳（财务/事件前移到 2017；行情仅读 lookback buffer，维度取快照/全量事件） | owner | docs §4.6, DECISION-20260531-11 |
| OQ-003 | 财务 `report_type` 口径：默认取合并报表 `'1'`；是否需要母公司/单季调整等口径维度？ | closed: 采纳（P0 默认合并报表 `report_type='1'`；带 `report_type` 的 DWD 保留 `report_type`/`report_caliber`/`is_default_report_caliber`；P0 DWS 默认过滤默认口径，多口径特征后续另建/扩展） | owner | `docs/prd/PRD_20260601_03_财务报表口径维度.md`, DECISION-20260601-05 |
| OQ-004 | 基准指数代码可用性：指数端点必须以 ODS `index_daily` 实际存在的 `ts_code` 为准，并维护 `source_sec_code -> sec_code` canonical 映射。 | closed: 已实现（新增并物化 `dim_index`；`dwd_index_eod` 从 `dim_index` 读取映射；新增 `sql/qa/03_oq004_index_checks.sql` 并通过；runner 08 增加 benchmark 可用性与窗口覆盖前置校验） | owner | `docs/prd/PRD_20260601_04_OQ004基准指数口径.md`, `sql/dim/04_dim_index.sql`, `sql/dwd/04_dwd_index_eod.sql`, `sql/qa/03_oq004_index_checks.sql`, DECISION-20260601-08 |
| OQ-007 | ODS `stock_basic_delisted.delist_date` 外部表类型与 Parquet 文件类型不一致、直读报错。 | closed: upstream fixed + DIM SQL updated（ODS 字段已统一为 `STRING` 并可解析；`dim_stock` 改为优先使用 ODS 退市日，仅缺值时用 daily 最后交易日兜底） | owner / 上游 ingestion | docs §5.2, sql/dim/02_dim_stock.sql, DECISION-20260601-04 |
| OQ-008 | 全历史早期可交易字段缺口：`stk_limit` 2007 前、`suspend_d` 1999 前不可用。 | closed: not applicable（行情最终写 2019+；2018 lookback buffer 内核心可交易辅助表可用，不构成 P0 阻塞） | owner | docs §4.6, review 修正说明 |
| OQ-009 | ODS `index_dailybasic` 多列外部 schema 与 Parquet 物理类型不一致（如 `float_mv`、`float_share`），导致 2019+ 读取失败。 | closed: upstream fixed + DWD restored（已恢复 `dwd_index_eod` 估值/股本字段；STAR50/CSI1000 因 ODS 无 dailybasic 端点仍为空） | owner / 上游 ingestion | sql/dwd/04_dwd_index_eod.sql |
