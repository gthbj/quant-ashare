# TODO

项目级待办，面向「下一步做什么」。整体状态见 `.agent/memory/IMPLEMENTATION_STATUS.md`。
维护规则见 `AGENTS.md` 的「TODO 维护协议」。

## P0 — 跑通最小可用闭环

- [ ] 建 `dim_trade_calendar`（带描述、内联 DDL）
- [ ] 建 `dim_stock`（UNION listed+delisted，含退市股）
- [ ] 建 `dim_stock_name_hist`（SCD2，ST/曾用名时间线）
- [ ] 建 `dwd_stock_eod_price`（复权+可交易掩码，按月分区+sec_code 聚簇+require_partition_filter，回填 2019 起）
- [ ] 建 `dwd_stock_eod_valuation`（估值/市值/换手，单位归一）
- [ ] 建 `dwd_fin_indicator`（PIT 去重 + `ann_date_eff`，回填 2017 起）
- [ ] 建 `dwd_index_eod`（基准指数）
- [ ] 写「从 ODS 继承字段描述」脚本（`bq show` → 映射 → `bq update`）
- [ ] 衔接 `dws_stock_feature_daily` v0 + `dws_stock_label_daily`（`fwd_ret_1d/5d/10d/20d`）

## P1 — 特征扩展

- [ ] `dwd_fin_income/balancesheet/cashflow`（单季派生）
- [ ] `dwd_sw_industry_eod` + 行业中性化
- [ ] 资金面：`dwd_stock_moneyflow` / `north_hold` / `chip` / `margin` / `limit_event`
- [ ] 事件：`dwd_event_forecast/express/dividend/holder_*`、`dwd_analyst_report`
- [ ] `dim_index_weight`、`dim_sw_industry`、`dim_ipo`

## P2 / P3

- [ ] 龙虎榜/大宗、质押/回购/审计、ccass、市场总览
- [ ] 增量调度（dbt 或 Airflow）+ 数据质量断言
- [ ] 治理类维度（managers/rewards）、北交所代码映射长历史拼接

## 待 owner 决策（见 OPEN_QUESTIONS）

- [ ] OQ-001 行业映射缺口：是否补采 `index_member_all`
- [ ] OQ-002 财务回填前移到 2017 是否最终接受
- [ ] OQ-005 物化选型：dbt（persist_docs）还是纯 bq SQL
