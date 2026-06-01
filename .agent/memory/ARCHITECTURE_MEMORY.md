# 架构记忆（Architecture Memory）

## 数据流

```text
Tushare 等数据源
  -> data-aquarium.ashare_ods   ODS 外部表（Hive 分区，原样）
  -> ashare_dim / ashare_dwd    维度 + 明细（清洗/去重/复权/PIT/单位归一）
  -> ashare_dws                 (sec_code, trade_date) 特征宽表 + 标签
  -> ashare_ads (可选)          选股池 / 组合 / 回测输入
```

## ODS 三类分区语义（建模地基，务必牢记）

| 类 | 语义 | 例 | 处理方式 |
|---|---|---|---|
| A 行情增量 | `partition_date == trade_date`，单日单分区、无重复，历史自 1990-12-19 | daily, adj_factor, daily_basic, bak_basic, moneyflow, stk_limit, suspend_d | 按 partition_date 增量裁剪 |
| B 财务/公告 | `partition_date == 报告期(end_date)`，**非公告日**；同期多 report_type/修正 | income, balancesheet, cashflow, fina_indicator | 用 ann_date_eff 做 PIT；按 (sec_code,报告期) 去重 |
| C 维度快照 | 每个 partition_date 一份全量，取最新分区 | stock_basic, trade_cal, index_classify | 取 MAX(partition_date)；stock_basic 需 UNION listed+delisted |
| C* 历史区间快照 | 最新 partition_date 保存全量历史区间 | index_member_all, ci_index_member | 取最新分区，用 in_date/out_date 建 SCD2 时点维表 |

## 目标表（P0 优先级）

| 层 | 表 | 源 | 粒度 |
|---|---|---|---|
| dim | dim_trade_calendar | trade_cal | (exchange, cal_date) |
| dim | dim_stock | stock_basic(listed+delisted) | sec_code |
| dim | dim_stock_name_hist | namechange | (sec_code, start_date) SCD2 |
| dim | dim_stock_sw_industry_hist | index_member_all | (sec_code, valid_from, sw_l3_code) SCD2 |
| dim | dim_stock_ci_industry_hist | ci_index_member | (sec_code, valid_from, ci_l3_code) SCD2 |
| dwd | dwd_stock_eod_price | daily+adj_factor+stk_limit+suspend_d | (sec_code, trade_date) |
| dwd | dwd_stock_eod_valuation | daily_basic | (sec_code, trade_date) |
| dwd | dwd_stock_bak_basic_daily | bak_basic | (sec_code, trade_date) |
| dwd | dwd_fin_indicator | fina_indicator | (sec_code, report_period) PIT |
| dwd | dwd_fin_indicator_latest | dwd_fin_indicator | (sec_code, report_period) 最新版本便捷表 |
| dwd | dwd_index_eod | index_daily + index_dailybasic | (sec_code, trade_date) |

完整 57 张 ODS→DWD/DIM 映射见 `docs/数据仓库建模方案-DWD-DIM.md` §2。

## DWS / ADS 设计

设计文档：

- `docs/数据仓库建模方案-DWS-ADS.md`
- `docs/A股中低频小资金机器学习策略方案.md`

P0 DWS 目标表：

| 层 | 表 | 粒度 | 作用 |
|---|---|---|---|
| dws | dws_stock_universe_daily | (sec_code, trade_date) | 样本骨架、生命周期、可交易/训练掩码 |
| dws | dws_stock_feature_price_daily | (sec_code, trade_date, feature_version) | 收益、动量、波动、趋势、涨跌停/停牌窗口特征 |
| dws | dws_stock_feature_valuation_daily | (sec_code, trade_date, feature_version) | 估值、市值、换手、流动性 |
| dws | dws_stock_feature_fin_daily | (sec_code, trade_date, feature_version) | PIT 财务指标 as-of |
| dws | dws_market_state_daily | trade_date | 指数趋势、市场宽度、风险状态 |
| dws | dws_stock_label_daily | (sec_code, trade_date, label_version) | fwd_ret_1d/5d/10d/20d、超额收益、可成交标签 |
| dws | dws_stock_feature_daily_v0 | (sec_code, trade_date, feature_version) | P0 训练特征宽表 |
| dws | dws_stock_sample_daily | (sec_code, trade_date, feature_version, label_version) | 训练/回测样本清单 |

P0 ADS 目标表：

| 层 | 表 | 粒度 | 作用 |
|---|---|---|---|
| ads | ads_ml_training_panel_daily | (run_id, sec_code, trade_date) | 冻结后的训练面板 |
| ads | ads_model_registry | model_id | 模型元数据 |
| ads | ads_model_prediction_daily | (model_id, predict_date, horizon, sec_code) | 每日预测分与横截面排序 |
| ads | ads_stock_candidate_daily | (strategy_id, rebalance_date, sec_code) | 策略候选池 |
| ads | ads_portfolio_target_daily | (strategy_id, rebalance_date, sec_code) | 目标组合权重 |
| ads | ads_order_plan_daily | (strategy_id, rebalance_date, sec_code, side) | 交易计划/回测订单输入 |
| ads | ads_backtest_* | backtest_id + 日期/股票 | 成交、持仓、NAV、绩效 |
| ads | ads_signal_monitor_daily | (strategy_id/model_id, trade_date) | 信号、样本、漂移、不可成交监控 |

DWS/ADS 统一版本字段：`universe_version`、`feature_version`、`label_version`、`strategy_id`、`model_id`、`run_id`。首个策略为 `ml_ranker_v0`：P0 特征横截面排序，预测未来 5/10 日收益或分位，长-only，`t` 日盘后信号、`t+1` 开盘/VWAP 建仓。

## SQL 代码布局

- 根目录 `sql/` 存放 P0 BigQuery Standard SQL：`00_create_datasets.sql`、`dim/*.sql`、`dwd/*.sql`。
- 现有脚本覆盖 3 张 DIM + 5 张 DWD，使用 `CREATE OR REPLACE TABLE` + CTAS + 后置 `ALTER COLUMN SET OPTIONS`；`sql/qa/01_p0_smoke_checks.sql` 存放物化后基础断言。
- `sql/metadata/01_p0_table_column_descriptions.sql` 统一维护 P0 DIM/DWD 表级和字段级中文说明；每次重建 P0 表后都应重新执行该 metadata 脚本。
- 当前脚本是 bootstrap SQL，不关闭 OQ-005；后续仍可迁移为 dbt 或纳入 Airflow 调度。
- 2026-05-31 P0 已物化到 BigQuery；`dwd_index_eod` 已恢复读取 `index_dailybasic`。该接口市值/股本单位为元/股，不做 `*10000` 换算。
- `dwd_index_eod` 的 `sec_code` 使用 canonical 指数代码，`source_sec_code` 保留 ODS/Tushare 实际代码；双代码指数映射先由建表脚本 CTE 维护，未来可沉淀为 `dim_index`。
- `dwd_stock_eod_price` 中 `is_suspended` 仅表示全天停牌/无成交；有成交的 `S` 事件另用 `has_intraday_halt`，开盘时段/未知时段临停用 `has_open_halt` 并影响开盘侧可交易掩码。
- `dwd_fin_indicator_latest` 是非 PIT 便捷表，按 `update_flag DESC, ann_date_eff DESC, ingested_at DESC, source_partition_date DESC` 取每个 `(sec_code, report_period)` 的最新修正版。

## 物理规范（BigQuery）

| 表类 | 分区键 | 聚簇键 | require_partition_filter |
|---|---|---|---|
| 行情 DWD | `DATE_TRUNC(trade_date, MONTH)` | `sec_code` | TRUE |
| 财务 DWD | `DATE_TRUNC(ann_date_eff, MONTH)` | `sec_code` | 不开（as-of 模式） |
| 普通 DIM | 不分区 | `sec_code` | — |
| 时序 DIM（index_weight） | `DATE_TRUNC(trade_date, MONTH)` | `index_code, sec_code` | 视情况 |
| 股票日频 DWS | `DATE_TRUNC(trade_date, MONTH)` | `sec_code` / `sec_code, feature_version` | 视情况 |
| ADS 预测/组合 | `DATE_TRUNC(predict_date/rebalance_date, MONTH)` | `model_id/strategy_id, sec_code` | 视情况 |

- **按月分区**而非按天：BigQuery 单表上限 4000 分区，按天全史 ~8700 交易日会超限；本表数据量小，按天碎片化。
- DWD/DIM 物化为**原生表**，不再是外部表；下游一律查 DWD 不直接打 ODS。
- 2019 年前数据范围三分：财务/事件按分区前移到 `20170101`；行情 DWD/DWS 最终写 `trade_date >= 2019-01-01`、构建时读取 lookback buffer；维度/日历取最新快照或全量历史事件。

## 命名规范要点（详见 docs §3.3 + DECISION_LOG）

- 证券主键 `sec_code`（`600000.SH`），辅助 `sec_symbol`、品种 `sec_type`。
- 日期：`trade_date`/`cal_date`/`pre_trade_date`/`ann_date_eff`/`report_period`/`ex_date`。
- 量纲统一元/股；复权后缀 `_hfq`/`_qfq`，收益 `ret_1d`/`fwd_ret_Nd`。
- 血缘 `source_system` + `ingested_at`。
- **ODS 源字段在 DWD/DIM 出口归一为 canonical 字段；若源代码与 canonical 代码不同，保留 `source_sec_code` 做血缘追溯。**

## 表/字段注释

所有 dim/dwd/dws 表带表级 + 字段级中文 description；财务大表字段描述**继承 ODS 同名字段**（脚本化），改名/派生/换算字段手写。详见 docs §3.4。
