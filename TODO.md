# TODO

项目级待办，面向「下一步做什么」。整体状态见 `.agent/memory/IMPLEMENTATION_STATUS.md`。
维护规则见 `AGENTS.md` 的「TODO 维护协议」。

## P0 — 跑通最小可用闭环

- [x] 编写 `dim_trade_calendar` 建表 SQL（`sql/dim/01_dim_trade_calendar.sql`，dry-run 通过；尚未物化）
- [x] 编写 `dim_stock` 建表 SQL（`sql/dim/02_dim_stock.sql`，UNION listed+delisted + 日线兜底，dry-run 通过；尚未物化）
- [x] 编写 `dim_stock_name_hist` 建表 SQL（`sql/dim/03_dim_stock_name_hist.sql`，SCD2，dry-run 通过；尚未物化）
- [x] 修订主方案 §4.6：当前先做 2019+，2019 前仅作财务/事件前移、行情 lookback buffer、维度/日历历史支撑
- [x] 在 P0 SQL 中显式参数化范围（`dwd_start_date=2019-01-01`、`fin_start_period=20170101`、`lookback_start_date=2018-01-01` 默认）
- [x] 编写 `dwd_stock_eod_price` 建表 SQL（复权+可交易掩码，月分区+sec_code 聚簇+require_partition_filter，写 2019+，构建读 lookback buffer；临时维表替换 dry-run 通过）
- [x] 编写 `dwd_stock_eod_valuation` 建表 SQL（估值/市值/换手，单位归一，写 2019+，dry-run 通过）
- [x] 编写 `dwd_fin_indicator` 建表 SQL（PIT 版本事实 + `ann_date_eff`，`partition_date >= 20170101`；临时维表替换 dry-run 通过）
- [x] 编写并回填 `dwd_index_eod` 建表 SQL（基准指数价格 + `index_dailybasic` 估值/股本，dry-run/QA 通过）
- [x] 修复 P0 SQL 评审发现 R1-R5（显式 `--location=asia-east2`、复牌行不判停牌、`dim_stock` 去重与派生退市宽限、`fina_indicator` 去重兜底、补 `dwd_fin_indicator_latest` 和 QA 脚本；dry-run 通过）
- [x] 执行 `sql/` P0 建表脚本并运行 `sql/qa/01_p0_smoke_checks.sql`（已物化 3 张 DIM + 5 张 DWD，QA 通过）
- [x] 修复 P0 SQL 二轮评审发现（盘中临停不再误标全天停牌；`dwd_fin_indicator_latest` 改为 `update_flag DESC` 优先；重建相关 DWD 并跑通 QA）
- [x] 补齐 P0 DIM/DWD 表说明和字段说明（`sql/metadata/01_p0_table_column_descriptions.sql` 已执行，8 张表 missing description=0）
- [ ] 将 `lookback_start_date` 从固定默认值升级为按最大滚动窗口计算/调度配置
- [ ] 写「从 ODS 继承字段描述」脚本（`bq show` → 映射 → `bq update`）
- [x] 设计 DWS/ADS 表体系（`docs/数据仓库建模方案-DWS-ADS.md`，覆盖 P0 DWS 特征/标签与 ADS 训练/预测/组合/回测/监控）
- [x] 设计中低频小资金 ML 策略方案（`docs/A股中低频小资金机器学习策略方案.md`，首个策略 `ml_ranker_v0`）
- [ ] 编写 P0 DWS 建表 SQL：`dws_stock_universe_daily`、`dws_stock_feature_price_daily`、`dws_stock_feature_valuation_daily`、`dws_stock_feature_fin_daily`、`dws_market_state_daily`、`dws_stock_label_daily`、`dws_stock_feature_daily_v0`、`dws_stock_sample_daily`
- [ ] 编写 P0 ADS 建表 SQL：`ads_ml_training_panel_daily`、`ads_model_registry`、`ads_model_prediction_daily`、`ads_stock_candidate_daily`、`ads_portfolio_target_daily`、`ads_order_plan_daily`、`ads_backtest_*`、`ads_signal_monitor_daily`
- [ ] 跑通 `ml_ranker_v0` 基线：生成训练面板、训练模型、写预测/候选/组合/回测 ADS 表、输出 RankIC/分位收益/净值/换手/不可成交比例

## P1 — 特征扩展

- [ ] `dwd_fin_income/balancesheet/cashflow`（单季派生）
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

## 待 owner 决策（见 OPEN_QUESTIONS）

- [x] OQ-001 行业映射：`index_member_all` 已补采（同时补入 `ci_index_member`），后续转为建表 SQL + QA
- [ ] OQ-005 物化选型：dbt（persist_docs）还是纯 bq SQL
- [ ] OQ-010 P0 策略默认参数：成本、调仓频率、持股数/权重上限、北交所开关、训练工具链
