# A 股日线量化数据仓库建模方案（DWS / ADS）

> 业务场景：**A 股 · 日线 · 中低频 · 小资金 · 机器学习量化**
> 当前建模范围：**2019-01-01 之后**的 DWS/ADS；2019 年以前数据仅作为财务/事件 PIT 前移、行情 lookback buffer、维度/日历历史支撑。
> 上游依赖：`data-aquarium.ashare_dim`、`data-aquarium.ashare_dwd`，设计口径以 `docs/数据仓库建模方案-DWD-DIM.md` 为准。
> 文档目标：设计可落地的 `ashare_dws`（特征/标签/样本层）与 `ashare_ads`（训练、预测、组合、回测、监控消费层）表体系。
> 文档维护：GPT-5（最近更新 2026-06-01）

---

## 0. TL;DR

1. **DWS 的核心产物**是按 `(sec_code, trade_date)` 对齐的样本、特征、标签：先分族物化，再合成训练宽表，避免一张超宽表承担所有职责。
2. **ADS 的核心产物**是面向策略执行和研究复现的消费表：训练面板、模型预测、候选池、目标组合、订单计划、回测持仓/NAV/绩效、信号监控。
3. **PIT 与交易假设延续 DWD/DIM 方案**：`t` 日盘后生成特征，`t+1` 开盘或 VWAP 建仓；财务/事件用 `visible_trade_date <= trade_date`；标签从 `t+1` 起算。
4. **当前 P0 依赖已设计的 4 张 DIM + 5 张 DWD**：可先做 universe、价格/估值/财务指标特征、指数/市场状态、1/5/10/20 日标签、训练面板和基线预测表。
5. **P1/P2 特征族增量接入**：资金、筹码、北向、两融、行业、事件、龙虎榜、大宗、质押、回购等单独进入分族 DWS，不阻塞 P0 宽表。
6. **所有 DWS/ADS 表都必须可追溯**：保留 `feature_version`、`label_version`、`universe_version`、`model_id`、`run_id`、`created_at` 等版本字段，避免回测不可复现。

---

## 1. 分层定位

```text
ashare_dim / ashare_dwd
  -> ashare_dws
       dws_stock_universe_daily
       dws_stock_feature_*_daily
       dws_stock_label_daily
       dws_stock_feature_daily_v0
       dws_stock_sample_daily
       dws_market_state_daily
       dws_feature_quality_daily
  -> ashare_ads
       ads_ml_training_panel_daily
       ads_model_prediction_daily
       ads_stock_candidate_daily
       ads_portfolio_target_daily
       ads_order_plan_daily
       ads_backtest_* / ads_signal_monitor_daily
```

| 层 | 职责 | 不做什么 |
|---|---|---|
| DWS | 以交易日横截面为中心，产出 PIT 正确的样本、特征、标签、市场状态和质量统计 | 不存模型对象，不存人工调仓结论 |
| ADS | 面向策略、训练、预测、组合和回测消费；每个结果都有版本、参数和运行批次 | 不重新清洗 ODS，不绕过 DWS/DWD 直接拼特征 |

## 2. 总体建模原则

### 2.1 主键与粒度

- 股票日频 DWS 主粒度：`(sec_code, trade_date)`。
- 市场/指数/行业状态粒度：`trade_date`、`(industry_code, trade_date)` 或 `(index_code, trade_date)`。
- ADS 预测/组合粒度按用途扩展：
  - 预测：`(model_id, predict_date, horizon, sec_code)`
  - 候选池：`(strategy_id, rebalance_date, sec_code)`
  - 组合：`(strategy_id, rebalance_date, sec_code)`
  - 回测持仓：`(backtest_id, trade_date, sec_code)`

### 2.2 时间与 PIT

- 特征日 `trade_date=t`：只能使用 `t` 日盘后已经可见的数据。
- 交易执行：默认 `t+1` 开盘/VWAP 建仓，卖出同理；A 股中低频策略不设计日内反转。
- 财务/事件 as-of：`visible_trade_date <= trade_date`，同一报告期取当时可见的最新版本。
- 标签：入场价从 `t+1` 起，持有到 `t+k`，用市场交易日序列定位，不用个股有行情序列。

### 2.3 物理设计

| 表类 | 分区 | 聚簇 | 说明 |
|---|---|---|---|
| 股票日频 DWS | `DATE_TRUNC(trade_date, MONTH)` | `sec_code` 或 `sec_code, feature_version` | 与 DWD 一致，支持按日期回测 |
| 标签/样本 | `DATE_TRUNC(trade_date, MONTH)` | `sec_code, label_version` | 标签也强制日期过滤 |
| ADS 预测/组合 | `DATE_TRUNC(predict_date/rebalance_date, MONTH)` | `model_id/strategy_id, sec_code` | 支持多模型并存 |
| 回测 NAV/绩效 | `DATE_TRUNC(trade_date, MONTH)` 或不分区 | `backtest_id` | 汇总表可不分区 |
| 元数据/运行清单 | 不分区 | `run_id/model_id/strategy_id` | 小表 |

建议 `ashare_dws` 和 `ashare_ads` 新建为 BigQuery 原生数据集。当前 BigQuery 中 `ashare_dws`/`ashare_ads` 尚未创建；P0 SQL 落地时先补 dataset bootstrap。

### 2.4 版本字段

| 字段 | 表 | 作用 |
|---|---|---|
| `universe_version` | universe/sample/ADS | 样本过滤规则版本 |
| `feature_version` | feature/sample/training | 特征清单、窗口、预处理版本 |
| `label_version` | label/sample/training | 标签计算口径版本 |
| `strategy_id` | ADS | 策略定义，如 `ml_ranker_v0` |
| `model_id` | ADS | 模型实例，如 `lgbm_ranker_20260531_v1` |
| `run_id` | ADS | 一次训练、预测、回测或调仓运行 |
| `created_at` | 全部 ADS、可选 DWS | 生成时间 |

版本字段不替代 git commit；生产中 `run_id` 应记录 SQL/git commit、参数 JSON、训练窗口、数据截止日。

---

## 3. DWS 表清单

## 3.1 P0 表

| 表 | 粒度 | 上游 | 作用 |
|---|---|---|---|
| `dws_stock_universe_daily` | `(sec_code, trade_date)` | `dwd_stock_eod_price`, `dwd_stock_eod_valuation`, `dim_stock`, `dim_stock_name_hist` | 每日样本骨架和过滤掩码 |
| `dws_stock_feature_price_daily` | `(sec_code, trade_date, feature_version)` | `dwd_stock_eod_price` | 收益、动量、波动、趋势、形态、可交易行为特征 |
| `dws_stock_feature_valuation_daily` | `(sec_code, trade_date, feature_version)` | `dwd_stock_eod_valuation` | 估值、市值、换手、流动性特征 |
| `dws_stock_feature_fin_daily` | `(sec_code, trade_date, feature_version)` | `dwd_fin_indicator` + `dwd_fin_income/balancesheet/cashflow`（默认合并口径） | PIT 财务指标、质量、成长、杠杆、现金流、三大报表绝对值、财报时效特征 |
| `dws_market_state_daily` | `(trade_date, market_state_version)` | `dwd_index_eod`, `dwd_stock_eod_price`, `dws_stock_feature_daily_v0` | 市场状态、指数趋势、全市场宽度、P2 market risk-off 触发证据 |
| `dws_stock_label_daily` | `(sec_code, trade_date, label_version)` | `dwd_stock_eod_price`, `dwd_index_eod`, `dim_trade_calendar` | 未来收益、超额收益、可成交标签 |
| `dws_stock_feature_daily_v0` | `(sec_code, trade_date, feature_version)` | 上述特征族 | P0 训练用特征宽表 |
| `dws_stock_sample_daily` | `(sec_code, trade_date, feature_version, label_version)` | universe + feature + label | 训练/回测样本清单 |

## 3.2 P1/P2 扩展表

| 表 | 粒度 | 依赖 DWD | 作用 |
|---|---|---|---|
| `dws_stock_feature_fundflow_daily` | `(sec_code, trade_date, feature_version)` | `dwd_stock_moneyflow`, `dwd_stock_north_hold`, `dwd_stock_margin` | 主力资金、北向、两融变化 |
| `dws_stock_feature_chip_daily` | `(sec_code, trade_date, feature_version)` | `dwd_stock_chip` | 筹码成本、获利盘、筹码集中 |
| `dws_stock_feature_event_daily` | `(sec_code, trade_date, feature_version)` | forecast/express/dividend/holder/report_rc 等 | 事件窗口、距事件天数、公告强度 |
| `dws_stock_feature_industry_daily` | `(sec_code, trade_date, feature_version)` | `dim_stock_sw_industry_hist`, `dim_stock_ci_industry_hist`, `dwd_sw_industry_eod`, `dwd_ci_industry_eod` | 行业归属、行业收益、行业中性暴露 |
| `dws_industry_feature_daily` | `(industry_system, industry_code, trade_date)` | `dwd_sw_industry_eod`, `dwd_ci_industry_eod` | 行业动量、拥挤度、估值 |
| `dws_feature_quality_daily` | `(feature_name, trade_date, feature_version)` | DWS 特征族 | 缺失率、分布、异常、IC 监控输入 |

---

## 4. DWS 逐表设计

### 4.1 `dws_stock_universe_daily`

**目标**：提供全市场每日股票样本骨架和可交易/训练/回测掩码，所有特征和标签都以此为左表。

**粒度**：`(sec_code, trade_date)`。

**关键字段**：

| 字段 | 类型 | 口径 |
|---|---|---|
| `trade_date` | DATE | 交易日 |
| `sec_code` | STRING | 股票代码 |
| `exchange`, `board`, `market` | STRING | 来自 `dim_stock` |
| `list_date`, `delist_date`, `listed_days` | DATE/INT64 | 生命周期 |
| `is_listed_on_date` | BOOL | `list_date <= trade_date < delist_date` |
| `is_suspended` | BOOL | 来自价格 DWD |
| `is_one_word_limit_up/down` | BOOL | 一字涨跌停 |
| `can_buy_next_open` | BOOL | `t+1` 开盘可买，来自 `t+1` 价格 DWD 的 `can_buy_open` |
| `can_sell_next_open` | BOOL | `t+1` 开盘可卖 |
| `is_st` | BOOL | `dim_stock_name_hist` as-of |
| `is_newly_listed` | BOOL | 默认上市未满 60 自然日 |
| `amount_cny_20d_avg` | FLOAT64 | 20 日成交额均值 |
| `sample_basic` | BOOL | 训练基础样本：在市、非停牌、非 ST、非次新、有估值/价格 |
| `sample_liquid` | BOOL | 加流动性过滤后的样本 |
| `universe_version` | STRING | 规则版本 |

**默认规则**：

- `sample_basic = is_listed_on_date AND NOT is_suspended AND NOT is_st AND NOT is_newly_listed`
- `sample_liquid = sample_basic AND amount_cny_20d_avg >= @min_amount_cny`
- 小资金策略可把 `@min_amount_cny` 设得较低，但仍应剔除极端无成交和长期停牌股票。
- 策略 1 首个基线默认 `board_allowlist = ['SSE_MAIN','SZSE_MAIN']`，仅沪深主板，不含北交所、创业板、科创板；其他策略或对照实验可用不同板块参数。

**注意**：训练特征在 `t` 日可计算，是否能买入要看 `t+1`，因此 `can_buy_next_open` 需要通过交易日序列右移取得，不能用 `t` 日 `can_buy_open` 代替。

### 4.2 `dws_stock_feature_price_daily`

**目标**：日线价格行为特征。全部基于后复权价 `_hfq`、成交量和涨跌停/停牌状态计算。

**窗口建议**：

- 短期：1/3/5 日
- 中期：10/20 日
- 中低频：60/120/250 日

**字段族**：

| 字段族 | 示例字段 | 说明 |
|---|---|---|
| 收益/反转 | `ret_1d`, `ret_3d`, `ret_5d`, `ret_20d`, `ret_60d` | 简单累计收益 |
| 动量剔除近端 | `mom_20_5`, `mom_60_20`, `mom_120_20` | 避免短期反转污染中期动量 |
| 波动 | `vol_5d`, `vol_20d`, `downside_vol_20d` | 日收益标准差 |
| 振幅/跳空 | `amplitude_1d`, `gap_open_1d`, `intraday_ret_1d` | 价格形态 |
| 趋势 | `close_to_ma20`, `ma20_to_ma60`, `close_rank_60d` | 均线和区间位置 |
| 回撤 | `drawdown_20d`, `drawdown_60d` | 相对滚动高点回撤 |
| 可交易行为 | `suspend_days_20d`, `limit_up_days_20d`, `one_word_limit_days_20d` | 可成交性和拥挤度 |

**窗口边界**：

- P0 写入 2019+，但 2019 年初的滚动特征必须读取 2018 lookback buffer。
- `ret_1d` 跨停牌用最近有价交易日，滚动窗口的分母也应按市场交易日序列，不用自然日。

### 4.3 `dws_stock_feature_valuation_daily`

**目标**：估值、市值、换手和流动性。

**字段族**：

| 字段族 | 示例字段 |
|---|---|
| 估值原值 | `pe_ttm`, `pb`, `ps_ttm`, `dividend_yield_ttm` |
| 估值变换 | `log_pe_ttm`, `log_pb`, `ep_ttm = 1 / pe_ttm` |
| 市值 | `log_total_mv`, `log_circ_mv`, `float_share` |
| 换手 | `turnover_rate`, `turnover_rate_5d_avg`, `turnover_rate_20d_avg` |
| 流动性 | `amount_cny_5d_avg`, `amount_cny_20d_avg`, `amihud_20d` |
| 量价配合 | `volume_ratio`, `amount_zscore_20d`, `turnover_zscore_60d` |

**处理规则**：

- `pe_ttm <= 0` 不直接做 log；保留原值，并派生 `is_pe_ttm_positive`。
- 极端值在 DWS 原表保留，训练面板中再做横截面 winsorize/z-score。
- 市值中性化建议放在 ADS 训练前处理或单独产出残差特征，避免把单一中性口径固化进 DWS 原子特征。

### 4.4 `dws_stock_feature_fin_daily`

> **已落地**（`sql/dws/07_dws_stock_feature_fin_daily.sql`，OQ-003 / PRD_20260601_03）。`feature_version='fin_default_v0_20260602'`。

**目标**：把 `dwd_fin_indicator` 与三大报表（`income`/`balancesheet`/`cashflow`）的 PIT 版本事实表 as-of 到每个 universe `trade_date`，作为后续策略共用的财务特征底座。

**口径（默认合并报表）**：

- 三大报表只消费默认合并口径（`is_default_report_caliber=TRUE`，`report_type='1'`）；该过滤放在预过滤 CTE 内，再 `LEFT JOIN` universe，**绝不**写进 `WHERE`，避免把 `LEFT JOIN` 退化成 inner join、丢掉暂无财报的股票日期（行数与 universe 完全一致）。
- `fina_indicator` 无 `report_type`，按 `source_default` 口径消费。
- `report_caliber`/`is_default_report_caliber` 描述本表**消费口径契约**（恒 `consolidated`/`TRUE`）；某只股票某日是否真有某来源财报由 `has_fin_*` 掩码与各来源 `*_report_period` 标识。

**as-of 规则**（四个来源各自 as-of，同 universe 日内取当时已可见的最新版本）：

```sql
LEFT JOIN (
  SELECT * FROM dwd_fin_income WHERE is_default_report_caliber = TRUE
) fi
  ON fi.sec_code = u.sec_code
 AND fi.visible_trade_date <= u.trade_date
 AND fi.visible_trade_date >= DATE_SUB(u.trade_date, INTERVAL 900 DAY)  -- 扇出约束，超窗视为缺失
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY u.sec_code, u.trade_date
  ORDER BY fi.report_period DESC, fi.ann_date_eff DESC, fi.update_flag DESC, fi.ingested_at DESC, fi.source_partition_date DESC
) = 1
```

**关键字段**：

| 字段族 | 示例字段 | 说明 |
|---|---|---|
| 报告期元数据（主，以利润表为准） | `report_period`, `ann_date_eff`, `visible_trade_date`, `report_caliber`, `is_default_report_caliber`, `report_age_days`, `fin_report_lag_days` | 财务新鲜度 + 口径契约 |
| 盈利质量（fina_indicator） | `roe`, `roe_deducted`, `roa`, `roic`, `grossprofit_margin`, `netprofit_margin` | 质量因子 |
| 成长（fina_indicator） | `netprofit_yoy`, `operating_revenue_yoy`, `total_revenue_yoy`, `basic_eps_yoy` | 成长因子 |
| 杠杆/偿债（fina_indicator） | `debt_to_assets`, `current_ratio`, `quick_ratio`, `assets_to_equity` | 风险和财务结构 |
| 现金流比率（fina_indicator） | `ocf_to_or`, `ocf_to_profit`, `cash_ratio` | 现金流质量 |
| 单季指标（fina_indicator） | `q_roe`, `q_netprofit_margin`, `q_grossprofit_margin` | 盈利边际变化 |
| 利润表绝对值（元，YTD） | `total_revenue`, `revenue`, `operate_profit`, `total_profit`, `n_income`, `n_income_attr_p`, `ebit`, `ebitda` | 规模/盈利 |
| 资产负债表绝对值（元，时点） | `total_assets`, `total_liab`, `total_hldr_eqy_exc_min_int`, `money_cap`, `inventories`, `accounts_receiv`, `goodwill` | 资产结构 |
| 现金流量表绝对值（元，YTD） | `n_cashflow_act`, `n_cashflow_inv_act`, `n_cash_flows_fnc_act`, `free_cashflow` | 现金流规模 |
| 缺失/可用性 | `has_fin_indicator`, `has_fin_income`, `has_fin_balancesheet`, `has_fin_cashflow`, 各来源 `*_report_period`/`*_visible_trade_date` | 模型显式识别缺失、各来源报告期可不同 |

**报告期泄露防线**（QA：`sql/qa/04_finance_caliber_checks.sql`）：

- 不能按 `report_period <= trade_date` 直接拼；一律用 `visible_trade_date <= trade_date`（主报告期与 ind/bs/cf 各来源可见日均断言不晚于 `trade_date`）。
- 不能用任何 `dwd_fin_*_latest` 便捷表作为回测特征。
- 对财报公布前的交易日，仍应使用上一期已可见财报。
- **单季派生**（利润表/现金流 `q_*`）作为 P1 内容，P0 先用 fina_indicator 现成的 `q_*` 指标，绝对值保留累计/YTD 口径。

### 4.5 `dws_market_state_daily`

**目标**：给模型和策略提供市场环境特征，支持仓位控制、分层训练、风险诊断和策略 1 P2 market risk-off。

**粒度**：`(trade_date, market_state_version)`。`trade_date=t` 的状态在 t 日收盘后形成，只允许影响 t+1 开盘及之后的执行决策。

**字段族**：

| 字段族 | 示例字段 |
|---|---|
| 指数收益 | `csi300_ret_5d`, `csi300_ret_20d`, `csi1000_ret_5d`, `csi1000_ret_20d` |
| 指数趋势/波动 | `csi1000_drawdown_20d`, `csi1000_vol_20d`, `csi1000_close_to_ma20`, `csi1000_close_to_ma60`, `csi1000_ma20_to_ma60` |
| 市场宽度 | `adv_ratio_1d`, `above_ma20_ratio`, `new_low_20d_ratio`, `limit_down_count`, `one_word_limit_down_count`, `limit_down_mv_ratio` |
| 横截面画像 | `avg_ret_20d`, `ret_20d_p25`, `ret_20d_median`, `drawdown_20d_median`, `avg_vol_20d` |
| P2 触发证据 | `is_smallcap_trend_down`, `is_breadth_weak`, `is_limit_down_diffusion`, `risk_off_trigger_count`, `risk_off_reasons` |
| 状态标签 | `market_regime`, `is_risk_off`, `risk_off_action` |

**当前实现**：

- SQL：`sql/dws/08_dws_market_state_daily.sql`。
- QA：`sql/qa/11_market_state_checks.sql`。
- 默认版本：`market_state_v0_20260606`。
- P2 v0 执行动作固定为 `risk_off_action='skip_new_buys'`：risk-off 次一开市日允许卖出和 pending sell 继续处理，但 BUY 侧新增/加仓订单必须写 `BUY_SKIPPED_MARKET_RISK_OFF`，不成交、不候补。

**基准代码**：

- DWS/ADS 只使用 `dwd_index_eod.sec_code` 作为基准指数 join key；该字段已在 DWD 层归一为 canonical 指数代码。
- `dwd_index_eod.source_sec_code` 仅用于追溯 ODS/Tushare 实际端点代码，不进入 DWS/ADS 业务 join。例：ODS 沪深300 来源代码为 `399300.SZ`，DWD `sec_code` 输出为 canonical `000300.SH`，`source_sec_code='399300.SZ'`。
- 双代码或多代码指数的 `source_sec_code -> sec_code` 映射由 `dim_index` 统一维护；`dwd_index_eod` 从 `dim_index` 读取可用端点与 canonical 映射。
- 任何 runner / ADS 回测在写基准收益前，必须先校验 `benchmark_sec_code` 是 `dim_index.has_daily=TRUE AND is_benchmark_candidate=TRUE`，并校验完整 NAV 窗口内每个开市日 `dwd_index_eod` 有且只有一条非空价格记录。依赖 PE/PB/市值等指数估值特征时，还必须要求 `has_dailybasic=TRUE`。

### 4.6 `dws_stock_label_daily`

**目标**：统一生成所有监督学习标签和可成交标记。

**粒度**：`(sec_code, trade_date, label_version)`。

**基础标签**：

| 字段 | 口径 |
|---|---|
| `fwd_ret_1d` | `t+1` 开盘买入，`t+1` 收盘卖出 |
| `fwd_ret_3d` | `t+1` 开盘买入，`t+3` 收盘卖出 |
| `fwd_ret_5d` | `t+1` 开盘买入，`t+5` 收盘卖出 |
| `fwd_ret_10d` | `t+1` 开盘买入，`t+10` 收盘卖出 |
| `fwd_ret_20d` | `t+1` 开盘买入，`t+20` 收盘卖出 |
| `fwd_excess_ret_5d` | 个股 `fwd_ret_5d` - 基准同窗口收益 |
| `fwd_ret_5d_rank_pct` | 当日横截面分位标签 |
| `top_quantile_5d` | 是否进入当日未来收益 top q |
| `entry_reachable_k` | `t+1` 是否可买 |
| `exit_reachable_k` | 退出日是否可卖 |
| `label_valid_k` | 入场可成交且标签入场/退出价格非空；退出日可卖性由 `exit_reachable_k` 单独标记，回测撮合层处理顺延或持仓延续 |

**标签 SQL 要点**：

- 使用 `dim_trade_calendar.trade_date_seq` 定位 `t+1/t+k`。
- 入场价使用 `open_hfq` 或未来扩展的 `vwap_hfq`，不能用 `t` 日收盘。
- 若 `t+1` 一字涨停或停牌，则 `entry_reachable=false`；训练可剔除，也可保留并作为无法成交样本分析。
- 如果退出日一字跌停/停牌，应设 `exit_reachable=false`，回测层选择顺延卖出或按无法卖出持仓延续。
- 当前策略 1 SQL 中 `label_valid_k` 用于训练样本有效性，只要求 `label_entry_tradable` 和 `fwd_ret_kd IS NOT NULL`；不把退出日不可卖并入 `label_valid_k`，避免把标签口径与回测顺延撮合混在一起。

### 4.7 `dws_stock_feature_daily_v0`

**目标**：P0 训练用宽表，合并价格、估值、财务、市场状态中最稳定的一组字段。

**建议字段规模**：

- P0 控制在 80-150 个特征。
- P1 扩展到 250-500 个特征。
- 不建议一开始把所有财务字段无筛选塞入训练表。

**字段分组**：

| 分组 | P0 字段示例 |
|---|---|
| 标识 | `sec_code`, `trade_date`, `feature_version` |
| 技术 | `ret_1d/5d/20d/60d`, `mom_20_5`, `vol_20d`, `drawdown_60d`, `close_rank_60d` |
| 流动性 | `amount_cny_20d_avg`, `turnover_rate_20d_avg`, `amihud_20d` |
| 估值/规模 | `log_circ_mv`, `pb`, `pe_ttm`, `ep_ttm`, `dividend_yield_ttm` |
| 财务 | `roe`, `grossprofit_margin`, `netprofit_yoy`, `debt_to_assets`, `ocf_to_or`, `report_age_days` |
| 可交易 | `suspend_days_20d`, `limit_up_days_20d`, `is_st`, `is_newly_listed` |
| 市场 | `market_regime`, `csi500_ret_20d`, `adv_ratio_1d` |

**不在 DWS 宽表中做的事**：

- 不做模型训练专属的 one-hot、缺失填补、winsorize、z-score 固化。
- 不做行业/市值中性化作为唯一版本；如需要，另产出 `*_neutralized` 字段并保留原值。

### 4.8 `dws_stock_sample_daily`

**目标**：把 universe、feature、label 对齐成训练/回测样本清单，但不做最终模型预处理。

**关键字段**：

| 字段 | 说明 |
|---|---|
| `sec_code`, `trade_date` | 样本主键 |
| `feature_version`, `label_version`, `universe_version` | 三类版本 |
| `sample_basic`, `sample_liquid`, `sample_trainable` | 分层掩码 |
| `label_valid_5d/10d/20d` | 标签可用性 |
| `has_feature_price/valuation/fin` | 特征族可用性 |
| `missing_feature_count` | 宽表缺失数 |
| `target_*` | 可选保留常用标签 |

`sample_trainable` 的默认口径：

```text
sample_liquid
AND has_feature_price
AND has_feature_valuation
AND label_valid_5d
AND NOT is_st
AND listed_days >= 60
```

---

## 5. P1/P2 DWS 扩展设计

### 5.1 `dws_stock_feature_fundflow_daily`

依赖 `dwd_stock_moneyflow`、`dwd_stock_north_hold`、`dwd_market_north_flow`、`dwd_stock_margin`。

| 字段族 | 示例字段 |
|---|---|
| 主力资金 | `net_mf_amount_1d`, `net_mf_amount_5d_sum`, `net_mf_amount_to_mv_5d` |
| 大单结构 | `buy_lg_amount_ratio`, `buy_elg_amount_ratio`, `sell_elg_amount_ratio` |
| 北向 | `north_hold_ratio`, `north_hold_ratio_chg_5d`, `north_net_buy_proxy_20d` |
| 两融 | `rzye_to_mv`, `rzye_chg_5d`, `rqye_chg_5d` |
| 市场北向 | `north_money_5d_sum`, `north_money_zscore_60d` |

注意：北向数据 2024 年后部分口径变化/停更，DWS 必须提供 `is_north_data_available`。

### 5.2 `dws_stock_feature_event_daily`

依赖 forecast/express/dividend/holder/report_rc/repurchase/pledge 等事件 DWD。

| 字段族 | 示例字段 |
|---|---|
| 业绩预告 | `forecast_type`, `forecast_pchg_mid`, `days_since_forecast` |
| 业绩快报 | `express_yoy_net_profit`, `days_since_express` |
| 分红 | `dividend_cash_yield`, `days_to_ex_date`, `days_since_ex_date` |
| 股东户数 | `holder_num_chg`, `holder_num_chg_pct`, `days_since_holder_number` |
| 增减持 | `holder_trade_net_amount_90d`, `has_holder_reduce_30d` |
| 分析师 | `rating_num_30d`, `rating_upgrade_30d`, `target_price_premium` |
| 质押/回购 | `pledge_ratio`, `repurchase_amount_180d` |

事件表必须保留两个时间：

- `event_date`：事件发生/生效日。
- `visible_trade_date`：策略可见并可用于建仓的交易日。

DWS 特征只用 `visible_trade_date <= trade_date` 的事件。

### 5.3 `dws_stock_feature_industry_daily`

行业归属使用 `dim_stock_sw_industry_hist` 的 `in_date/out_date` 区间做 PIT join；中信行业可用 `dim_stock_ci_industry_hist` 作为备选/对照体系。`dim_stock.industry` 仅保留为粗口径兜底字段 `industry_tushare_raw`，不作为标准行业中性化依据。

| 字段族 | 示例字段 |
|---|---|
| 行业归属 | `sw_l1/l2/l3_code`, `sw_l1/l2/l3_name`, `ci_l1/l2/l3_code`, `ci_l1/l2/l3_name` |
| 行业收益 | `industry_ret_5d`, `industry_ret_20d`, `industry_mom_60_20` |
| 行业相对 | `ret_20d_minus_industry`, `vol_20d_minus_industry` |
| 行业宽度 | `industry_adv_ratio_1d`, `industry_limit_up_count` |
| 中性化辅助 | `industry_rank_pct`, `industry_member_count` |

行业 join 统一使用半开区间：

```sql
h.valid_from <= base.trade_date
AND base.trade_date < h.valid_to
```

`is_new='Y'` 只用于标识当前行业归属，不能用于历史训练/回测。

---

## 6. ADS 表清单

## 6.1 训练与模型消费

| 表 | 粒度 | 作用 |
|---|---|---|
| `ads_ml_training_panel_daily` | `(run_id, sec_code, trade_date)` | 某次训练/回测使用的最终样本、特征、标签 |
| `ads_model_registry` | `(model_id)` | 模型元数据，不存模型二进制 |
| `ads_model_prediction_daily` | `(model_id, predict_date, horizon, sec_code)` | 每日模型预测分数和排序 |
| `ads_signal_explain_daily` | `(model_id, predict_date, sec_code, feature_name)` | 可选：特征贡献/分组解释 |

### `ads_ml_training_panel_daily`

**字段**：

- 标识：`run_id, sec_code, trade_date, feature_version, label_version, universe_version`
- 分割：`split_name`（train/valid/test/live）
- 特征：训练时实际使用的 feature 列
- 标签：`target_ret`, `target_rank_pct`, `target_top_quantile`
- 权重：`sample_weight`
- 掩码：`sample_trainable`, `label_valid`

**原则**：

- 训练面板是“冻结后的研究输入”，同一个 `run_id` 不应被覆盖。
- 面板中的特征预处理可以按策略需要固化，例如横截面 winsorize/z-score；原始特征仍留在 DWS。

### `ads_model_prediction_daily`

**字段**：

| 字段 | 说明 |
|---|---|
| `model_id`, `run_id` | 模型与预测批次 |
| `predict_date` | 信号日，对应 DWS `trade_date=t` |
| `horizon` | `1d/5d/10d/20d` |
| `sec_code` | 股票代码 |
| `pred_score` | 原始预测分 |
| `pred_rank` | 当日横截面名次 |
| `pred_rank_pct` | 当日横截面分位 |
| `pred_bucket` | 分组，如 1-10 十分位 |
| `is_candidate` | 是否进入候选 |
| `feature_version`, `model_version` | 版本 |
| `data_cutoff_date` | 数据截止日 |
| `created_at` | 生成时间 |

## 6.2 策略候选与组合

| 表 | 粒度 | 作用 |
|---|---|---|
| `ads_stock_candidate_daily` | `(strategy_id, rebalance_date, sec_code)` | 策略候选池，含过滤原因和排序 |
| `ads_portfolio_target_daily` | `(strategy_id, rebalance_date, sec_code)` | 目标持仓权重 |
| `ads_order_plan_daily` | `(strategy_id, rebalance_date, sec_code, side)` | 模拟/实盘订单计划 |
| `ads_risk_exposure_daily` | `(strategy_id, rebalance_date, exposure_name)` | 行业、市值、风格、集中度暴露 |

### `ads_stock_candidate_daily`

**字段**：

| 字段 | 说明 |
|---|---|
| `strategy_id`, `rebalance_date`, `sec_code` | 主键 |
| `model_id`, `horizon` | 信号来源 |
| `pred_score`, `pred_rank_pct` | 排序依据 |
| `candidate_rank` | 策略内名次 |
| `passed_universe_filter` | 是否通过样本过滤 |
| `passed_risk_filter` | 是否通过风险过滤 |
| `reject_reason` | 未入选原因 |
| `expected_entry_date` | 默认下一交易日 |
| `can_buy_expected_open` | 预期入场日可买 |

### `ads_portfolio_target_daily`

**字段**：

| 字段 | 说明 |
|---|---|
| `target_weight` | 目标权重 |
| `raw_weight` | 风控前权重 |
| `weight_cap_applied` | 是否被单票上限裁剪 |
| `industry_weight` | 所属行业组合权重 |
| `cash_weight` | 现金权重，通常只在组合级汇总行记录 |
| `rebalance_reason` | 例：scheduled/stop_loss/risk_off |

**默认组合规则**：

- 小资金长-only，默认不加杠杆、不做融券。
- 持股数 20-80 可配置；P0 基线建议 30-50。
- 单票目标权重默认不超过 5%。
- 行业分散：优先用申万 L1/L2 时点映射做约束；中信行业作为稳健性对照。
- 现金权重由市场状态或候选不足决定。

### `ads_order_plan_daily`

**字段**：

| 字段 | 说明 |
|---|---|
| `side` | BUY/SELL |
| `target_weight`, `current_weight`, `delta_weight` | 权重变化 |
| `reference_price` | 计划使用的开盘/VWAP/收盘参考价 |
| `expected_trade_date` | 预计交易日，默认 `rebalance_date` 的下一交易日 |
| `order_notional_cny` | 计划成交金额 |
| `order_shares` | 计划股数，按 100 股手数约束处理 |
| `can_trade_open` | 是否能在开盘方向成交 |
| `block_reason` | 停牌、一字涨停、一字跌停、价格缺失等 |

ADS 订单计划只做“可交易计划”和回测输入，不在本文设计券商接口。

## 6.3 回测与绩效

| 表 | 粒度 | 作用 |
|---|---|---|
| `ads_backtest_run` | `(backtest_id)` | 回测配置和版本 |
| `ads_backtest_trade_daily` | `(backtest_id, trade_date, sec_code, side)` | 成交明细 |
| `ads_backtest_position_daily` | `(backtest_id, trade_date, sec_code)` | 每日持仓 |
| `ads_backtest_nav_daily` | `(backtest_id, trade_date)` | 净值、收益、回撤 |
| `ads_backtest_performance_summary` | `(backtest_id)` | 汇总绩效 |

### `ads_backtest_run`

字段：`backtest_id, strategy_id, model_id, start_date, end_date, initial_capital_cny, rebalance_freq, holding_period, cost_config_json, universe_version, feature_version, label_version, code_version, created_at`。

### `ads_backtest_nav_daily`

字段：`nav, daily_ret, benchmark_ret, excess_ret, drawdown, gross_exposure, net_exposure, turnover, cost_cny, position_count, cash_weight`。

### `ads_backtest_performance_summary`

字段：`annual_ret, annual_vol, sharpe, max_drawdown, calmar, win_rate, avg_turnover, avg_position_count, excess_annual_ret, information_ratio, top_bucket_spread`。

成本参数不在文档中写死；由 `cost_config_json` 记录，待 owner 确认。

## 6.4 监控与质量

| 表 | 粒度 | 作用 |
|---|---|---|
| `ads_signal_monitor_daily` | `(strategy_id/model_id, trade_date)` | 信号分布、候选数、换手、异常 |
| `ads_feature_drift_daily` | `(feature_name, trade_date, feature_version)` | 特征漂移 |
| `ads_data_quality_alert_daily` | `(alert_date, check_name)` | 数据质量告警 |

关键监控：

- 当日样本数、可买样本数、候选数。
- 预测分分布、top 分位行业/市值集中度。
- 特征缺失率、极端值率、横截面标准差为 0 的字段。
- 标签回填后 IC/RankIC、top-bottom spread。
- 交易计划中因停牌/涨跌停无法成交的比例。

---

## 7. P0 构建顺序

1. 创建 `ashare_dws`、`ashare_ads` 数据集。
2. 物化 P0 DIM/DWD：`dim_trade_calendar`、`dim_stock`、`dim_stock_name_hist`、`dwd_stock_eod_price`、`dwd_stock_eod_valuation`、`dwd_fin_indicator`、`dwd_index_eod`。
3. 构建 `dws_stock_universe_daily`。
4. 构建 `dws_stock_feature_price_daily` 和 `dws_stock_feature_valuation_daily`。
5. 构建 `dws_stock_feature_fin_daily`。
6. 构建 `dws_market_state_daily`。
7. 构建 `dws_stock_label_daily`。
8. 合成 `dws_stock_feature_daily_v0` 与 `dws_stock_sample_daily`。
9. 生成 `ads_ml_training_panel_daily` 的基线 run。
10. 训练基线模型后写入 `ads_model_registry`、`ads_model_prediction_daily`、`ads_stock_candidate_daily`。
11. 做 `ads_backtest_*` 回测闭环。

---

## 8. 数据质量与验收

### 8.1 DWS 验收

- `(sec_code, trade_date, feature_version)` 唯一。
- `trade_date >= 2019-01-01`，但滚动特征 2019 年初不因 warm-up 缺失而系统性为空。
- `dws_stock_universe_daily` 的每日股票数与 `dwd_stock_eod_price` 骨架一致。
- 财务特征中 `visible_trade_date <= trade_date`。
- `sample_trainable` 每日样本数稳定，不因缺失 join 大面积掉样本。
- 标签 `label_valid_k` 在最后 k 个交易日自然为空或 false，不应生成伪标签。

### 8.2 ADS 验收

- 每个 `run_id` 可追溯到 `feature_version`、`label_version`、`universe_version`、训练窗口和代码版本。
- 预测表每日每模型唯一：`(model_id, predict_date, horizon, sec_code)` 无重复。
- 候选池排序稳定：同一输入重复运行输出一致。
- 组合目标权重合计不超过 1，单票权重不超过策略约束。
- 回测 NAV 可由成交和持仓重算；每日收益与持仓收益对齐。
- 监控表能标出样本数异常、特征缺失异常、信号分布漂移。

---

## 9. 路线图

**P0：ML 最小闭环**

- DWS：universe、价格特征、估值特征、财务指标特征、市场状态、标签、训练样本。
- ADS：训练面板、模型注册、预测、候选池、目标组合、回测 NAV/绩效。
- 策略：`ml_ranker_v0`，5/10 日收益排序，周度或日度调仓。

**P1：提高信号密度**

- DWD/DWS 接入资金流、北向、筹码、两融、业绩预告/快报、股东户数、分析师。
- ADS 增加信号解释、特征漂移、IC 监控。
- 策略增加事件增强、资金流增强、行业轮动约束。

**P2：风控与研究平台化**

- 接入龙虎榜、大宗、质押、回购、审计、市场总览。
- 建策略运行清单和自动报告。
- 支持多模型 ensemble、分市场/分风格模型、动态仓位。

---

## 10. 待确认项

1. **行业区间 QA**：申万/中信时点映射已可落地；需在建表 QA 中确认 `out_date` 边界、区间重叠/缺口和 2019+ 覆盖率。
2. **成本参数**：佣金、滑点、税费、冲击成本需 owner 给出策略默认值，ADS 用 `cost_config_json` 参数化。
3. **首个策略执行频率**：建议 P0 同时支持日度预测、周度调仓；最终以回测结果确定。
4. **训练工具链**：策略 1 首版 runner 已定为 BigQuery ML + SQL，设计见 `docs/策略1-ml_pv_clf_v0-runner设计.md`；DWS/ADS 表契约仍保持模型族中立，后续策略可另定工具链。
5. **ADS 是否保留全量特征列**：训练面板可保留宽表，也可只保留样本索引 + feature vector 外部文件；P0 建议先保留 BigQuery 宽表，便于审计。
