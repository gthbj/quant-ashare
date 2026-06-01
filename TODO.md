# TODO

项目级待办，面向「下一步做什么」。整体状态见 `.agent/memory/IMPLEMENTATION_STATUS.md`。
维护规则见 `AGENTS.md` 的「TODO 维护协议」。

## P0 — 跑通最小可用闭环

- [x] 编写并物化 `dim_trade_calendar`（`sql/dim/01_dim_trade_calendar.sql`，dry-run / 物化 / QA 通过）
- [x] 编写并物化 `dim_stock`（`sql/dim/02_dim_stock.sql`，UNION listed+delisted；当前 SQL 优先使用 ODS `delist_date`，缺值时日线兜底；历史版本已 dry-run / 物化 / QA 通过）
- [x] 编写并物化 `dim_stock_name_hist`（`sql/dim/03_dim_stock_name_hist.sql`，SCD2，dry-run / 物化 / QA 通过）
- [x] 修订主方案 §4.6：当前先做 2019+，2019 前仅作财务/事件前移、行情 lookback buffer、维度/日历历史支撑
- [x] 在 P0 SQL 中显式参数化范围（`dwd_start_date=2019-01-01`、`fin_start_period=20170101`、`lookback_start_date=2018-01-01` 默认）
- [x] 编写 `dwd_stock_eod_price` 建表 SQL（复权+可交易掩码，月分区+sec_code 聚簇+require_partition_filter，写 2019+，构建读 lookback buffer；临时维表替换 dry-run 通过）
- [x] 编写 `dwd_stock_eod_valuation` 建表 SQL（估值/市值/换手，单位归一，写 2019+，dry-run 通过）
- [x] 编写 `dwd_fin_indicator` 建表 SQL（PIT 版本事实 + `ann_date_eff`，`partition_date >= 20170101`；临时维表替换 dry-run 通过）
- [x] 编写并回填 `dwd_index_eod` 建表 SQL（基准指数价格 + `index_dailybasic` 估值/股本，dry-run/QA 通过）
- [x] 重建 `dwd_index_eod` 以应用 canonical `sec_code` + `source_sec_code` 指数代码归一调整，并重新执行 metadata / QA（2026-06-01 已物化，P0 smoke QA 通过）
- [x] 修复 P0 SQL 评审发现 R1-R5（显式 `--location=asia-east2`、复牌行不判停牌、`dim_stock` 去重与派生退市宽限、`fina_indicator` 去重兜底、补 `dwd_fin_indicator_latest` 和 QA 脚本；dry-run 通过）
- [x] 执行 `sql/` P0 建表脚本并运行 `sql/qa/01_p0_smoke_checks.sql`（已物化 3 张 DIM + 5 张 DWD，QA 通过）
- [x] 修复 P0 SQL 二轮评审发现（盘中临停不再误标全天停牌；`dwd_fin_indicator_latest` 改为 `update_flag DESC` 优先；重建相关 DWD 并跑通 QA）
- [x] 补齐 P0 DIM/DWD 表说明和字段说明（`sql/metadata/01_p0_table_column_descriptions.sql` 已执行，8 张表 missing description=0）
- [x] 复核并关闭 OQ-007：ODS `stock_basic_delisted.delist_date` 已统一为 `STRING` 且可解析；`dim_stock` SQL 改为优先使用 ODS 退市日，并补 P0 QA 断言
- [ ] 合并 OQ-007 后重建 `dim_stock`，并按依赖重建 `dwd_stock_eod_price` 与策略 1 DWS/ADS 派生产物，执行 metadata / P0 QA / 策略 1 QA
- [ ] 将 `lookback_start_date` 从固定默认值升级为按最大滚动窗口计算/调度配置
- [ ] 写「从 ODS 继承字段描述」脚本（`bq show` → 映射 → `bq update`）
- [x] 设计 DWS/ADS 表体系（`docs/数据仓库建模方案-DWS-ADS.md`，覆盖 P0 DWS 特征/标签与 ADS 训练/预测/组合/回测/监控）
- [x] 设计中低频小资金 ML 策略方案（`docs/A股中低频小资金机器学习策略方案.md`，首个策略 `ml_ranker_v0`）
- [x] 编写并物化策略 1 DWS 建表 SQL：`dws_stock_universe_daily`、`dws_stock_feature_price_daily`、`dws_stock_feature_valuation_daily`、`dws_stock_label_daily`、`dws_stock_feature_daily_v0`、`dws_stock_sample_daily`（`sql/dws/*.sql`，dry-run / 物化 / `sql/qa/02_strategy1_dws_ads_checks.sql` 通过；PR #4 comment 已补 `label_valid` 语义说明、去冗余 JOIN、量化最早可训练日期、同步 DWD-DIM 字段名）
- [ ] 补 P0 通用 DWS 扩展表：`dws_stock_feature_fin_daily`、`dws_market_state_daily`、后续策略共用的财务/市场状态特征
- [x] 编写并物化策略 1/P0 ADS 表契约：`ads_ml_training_panel_daily`、`ads_model_registry`、`ads_model_prediction_daily`、`ads_stock_candidate_daily`、`ads_portfolio_target_daily`、`ads_order_plan_daily`、`ads_backtest_*`、`ads_signal_monitor_daily`（`sql/ads/01_ads_strategy1_tables.sql`，dry-run / 物化 / QA 通过）
- [x] 编写策略 1 BigQuery ML runner 设计：`docs/策略1-ml_pv_clf_v0-runner设计.md`（BigQuery SQL + BigQuery ML，覆盖训练、预测、候选、组合、订单、回测、监控、幂等和 QA）
- [x] 编写策略 1 BigQuery ML runner 与回测闭环实现 PRD：`docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`
- [x] 编写并采纳 OQ-003 财务 `report_type` 口径 PRD：`docs/prd/PRD_20260601_03_财务报表口径维度.md`（P0 默认合并报表，DWD 保留口径字段，DWS 默认过滤；PR #8 review comment 与 NULL-safe QA 已跟进）
- [x] 编写 OQ-004 基准指数代码可用性 PRD：`docs/prd/PRD_20260601_04_OQ004基准指数口径.md`（指数 endpoint/canonical 映射、`dim_index`、benchmark 窗口契约）
- [ ] 按 `PRD_20260601_04_OQ004基准指数口径.md` 补 `dim_index`、OQ-004 QA、映射驱动的 `dwd_index_eod` 和 runner benchmark 窗口校验
- [ ] 按 `PRD_20260601_02_策略1BQML回测闭环.md` 补策略 1 BigQuery ML + SQL runner：生成 `ads_ml_training_panel_daily`，训练 BQML `LOGISTIC_REG` / `LINEAR_REG`，写预测/候选/组合/回测 ADS 表，输出 RankIC/分位收益/净值/换手/不可成交比例
- [ ] 补 lookback-capable 价格构建输入或调整 DWD/DWS 构建方式，使 2019-01 起 60 日价格窗口可直接读取 2018 buffer；当前策略 1 DWS 已用 `has_full_history_60d` 显式标记并默认剔除不完整窗口样本

## P1 — 特征扩展

- [ ] `dwd_fin_income/balancesheet/cashflow`（按 OQ-003 PRD 保留 `report_type`/`report_caliber`；单季派生）
- [x] 修复/绕过 `index_dailybasic` Parquet 类型不一致后，回填 `dwd_index_eod` 指数估值/股本字段（ODS 已修复，DWD 已重建；STAR50/CSI1000 无 dailybasic 端点仍为空）
- [ ] `dim_stock_sw_industry_hist`（源 `index_member_all`，按 `in_date/out_date` 建申万行业时点归属，并 QA 区间重叠/缺口）
- [ ] `dim_stock_ci_industry_hist`（源 `ci_index_member`，中信行业时点归属，对照体系）
- [ ] `dwd_sw_industry_eod` + 行业中性化
- [ ] 资金面：`dwd_stock_moneyflow` / `north_hold` / `chip` / `margin` / `limit_event`
- [ ] 事件：`dwd_event_forecast/express/dividend/holder_*`、`dwd_analyst_report`
- [ ] `dim_index_weight`、`dim_sw_industry`、`dim_ipo`

## P2 / P3

- [ ] 龙虎榜/大宗、质押/回购/审计、ccass、市场总览
- [ ] 增量调度（dbt 或 Airflow）+ 数据质量断言
- [ ] 治理类维度（managers/rewards）、北交所代码映射长历史拼接

## 项目维护

- [x] 整理 `.agent/memory/` 工作记忆：归档旧 handoff、迁移 closed questions、压缩 superseded 决策、修正陈旧状态描述、更新协议防止继续膨胀

## 待 owner 决策（见 OPEN_QUESTIONS）

- [x] OQ-001 行业映射：`index_member_all` 已补采（同时补入 `ci_index_member`），后续转为建表 SQL + QA
- [x] OQ-003 财务 `report_type` 口径：已采纳 `docs/prd/PRD_20260601_03_财务报表口径维度.md` 推荐方案（P0 默认合并报表、DWD 保留多口径字段、DWS 默认过滤）
- [ ] OQ-004 基准指数代码可用性：PRD 已写，待 owner review `dim_index` 和 runner benchmark 校验方案
- [x] OQ-007 退市日类型：ODS `stock_basic_delisted.delist_date` 已修复为 `STRING`，`dim_stock` SQL 已改为优先使用 ODS 退市日
- [ ] OQ-005 物化选型：dbt（persist_docs）还是纯 bq SQL
- [ ] OQ-010 P0 策略默认参数：成本、调仓频率、持股数/权重上限（训练工具链已定为 BigQuery ML + SQL runner；首个基线股票池已定为仅沪深主板，不含北交所/创业板/科创板）
