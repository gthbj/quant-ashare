# A 股日线量化数据仓库建模方案（ODS → DWD / DIM）

> 业务场景：**A 股 · 日线 · 中低频 · 小资金 · 机器学习量化**
> 当前建模范围：**2019-01-01 之后**的 A 股日线 DWD/DWS 建模；2019 年以前数据仅作为财务/事件 PIT 前移、行情 lookback buffer、维度/日历历史支撑，正式扩展 2019 年以前样本属后续阶段。
> 数据底座：BigQuery 项目 `data-aquarium`，ODS 层数据集 `ashare_ods`（当前来源 Tushare，未来多源；全部为 Hive 分区外部表）
> 文档目标：基于现有 ODS 表，设计可落地的 **DWD（明细层）** 与 **DIM（维度层）**，并给出横切的工程原则（命名规范、PIT 防未来函数、复权、去重、可交易性、增量调度等）。
> 文档维护：Claude Opus 4.8（最近更新 2026-05-31）；§4.6 回填范围与 ODS 清单更新：GPT-5（2026-05-31）；P0 实表字段名与 OQ-007 同步：GPT-5（2026-06-01）

---

## 0. TL;DR（一页纸结论）

1. **当前建模范围**：本文当前阶段落地 **2019-01-01 之后**的 DWD/DWS；2019 年以前只在三类必要场景读取或保留：财务/事件前移到 2017 做 PIT，行情读取 lookback buffer 做 warm-up，维度/日历取最新快照或全量历史事件。不要把这理解为全历史行情建模。
2. **ODS 现状**：`ashare_ods` 下共 57 张外部表，全部以 `partition_date`（`STRING`，`YYYYMMDD`）+ `endpoint` 作为 Hive 分区键。**任何查询都必须带 `partition_date`/`endpoint` 过滤**，否则 BigQuery 直接报错（强制分区裁剪）。
3. **三类分区语义**（建模的地基，必须先理解）：
   - **A. 行情增量表**：`partition_date == trade_date`，单日一个分区、无重复，历史可回溯到 **1990-12-19**。例：`daily`、`adj_factor`、`daily_basic`。
   - **B. 财务/公告表**：`partition_date == end_date`（报告期，**不是公告日**），同一 `(ts_code, end_date)` 因 `report_type`/修正存在多条。例：`income`、`balancesheet`、`cashflow`、`fina_indicator`。
   - **C. 维度快照表**：每个 `partition_date` 一份**全量快照**，取最新分区即得当前全量。例：`stock_basic`、`trade_cal`、`index_classify`。注意 `stock_basic` 用 `endpoint` 区分 `listed` / `delisted`，**必须 UNION 才完整（含退市股，避免幸存者偏差）**。
4. **建议分层**：`ashare_ods`（已有） → `ashare_dim`（维度） + `ashare_dwd`（明细） → `ashare_dws`（特征宽表/标签，下游 ML 直接消费）。本文聚焦 DIM 与 DWD，并给出 DWS 衔接。
5. **统一命名规范（详见 §3.3，全文遵循）**：证券主键统一为 **`sec_code`**（值标准格式 `600000.SH`，源字段 `ts_code`/`con_code`/`code` 等在出口归一）；交易日 **`trade_date`**、日历日 `cal_date`；财务可见时间 **`ann_date_eff`**；量纲**统一到元/股**；DWD 事实表统一带血缘字段 **`source_system` + `ingested_at`**。
6. **量化语境下的五条铁律**：
   - **PIT（Point-In-Time）**：财务特征的可见时间一律用 `ann_date_eff`（**按表定义**，见 §4.3 表级可见日规则；如 income/bs/cf 用 `COALESCE(f_ann_date, ann_date)`，而 `fina_indicator` **无 `f_ann_date`**、仅能用 `ann_date`），严禁用 `end_date`/`partition_date` 当可见时间。
   - **复权**：收益率与技术指标统一基于 `adj_factor` 计算的**后复权**口径（`_hfq`）；前复权（`_qfq`）含未来除权信息，仅用于展示、不用于训练特征。
   - **幸存者偏差**：universe 必须包含已退市股票的历史区间。
   - **可交易性**：停牌、一字涨跌停、上市未满 N 日、ST 等需打标，作为样本过滤/掩码。
   - **去重**：行情表按分区天然唯一；财务/公告表必须按业务键 + 公告日 + `update_flag` 去重取最新修正版。

---

## 1. 业务场景与建模诉求

| 维度 | 取值 | 对建模的影响 |
|---|---|---|
| 标的 | 全 A 股（沪/深/北，含科创、创业、退市） | universe 治理是核心；需处理多板块涨跌幅、北交所代码映射、退市偏差 |
| 频率 | 日线（EOD） | 粒度统一为 `(sec_code, trade_date)`；不涉及分钟/tick |
| 周期 | 中低频（持仓数日~数周） | 标签为未来 1/5/10/20 日复权收益；换手不敏感 |
| 资金 | 小资金 | 容量不敏感，可全市场选股、可碰小盘低流动性；但**冲击成本/可买入性**仍要建模（一字板、停牌） |
| 方法 | 机器学习 | 需要**规整、稠密、无未来泄露**的特征宽表 + 干净标签；强调 PIT、横截面对齐、可复现 |

ML 量化的最终消费物是一张以 `(sec_code, trade_date)` 为主键的**特征宽表**（features）+ **标签**（labels）。DWD/DIM 的全部设计都服务于"能高效、正确地拼出这张宽表"。

---

## 2. ODS 全量盘点与去向映射

> 下表是 57 张 ODS 表 → 目标 DWD/DIM 的完整映射。`类`列对应 §0 的三类分区语义（A 行情增量 / B 财务公告 / C 维度快照）。

### 2.1 行情与交易行为域（A 类为主）

| ODS 表 | 含义 | 类 | 目标表 | 优先级 |
|---|---|---|---|---|
| `ods_tushare_daily` | 未复权日线 OHLCV | A | `dwd_stock_eod_price` | P0 |
| `ods_tushare_adj_factor` | 复权因子 | A | `dwd_stock_eod_price`（合并） | P0 |
| `ods_tushare_daily_basic` | 估值/换手/市值 | A | `dwd_stock_eod_valuation` | P0 |
| `ods_tushare_bak_basic` | 股票历史列表/备用基础列表 | A | `dwd_stock_bak_basic_daily`（历史基础属性/估值兜底） | P2 |
| `ods_tushare_stk_limit` | 每日涨跌停价 | A | `dwd_stock_eod_price`（合并） | P0 |
| `ods_tushare_suspend_d` | 停复牌 | A | `dwd_stock_eod_price`（打标） | P0 |
| `ods_tushare_limit_list_d` | 涨跌停/连板统计 | A | `dwd_stock_limit_event` | P1 |
| `ods_tushare_moneyflow` | 个股资金流(大中小单) | A | `dwd_stock_moneyflow` | P1 |
| `ods_tushare_moneyflow_hsgt` | 沪深港通资金流(市场) | A | `dwd_market_north_flow` | P1 |
| `ods_tushare_hk_hold` | 北向个股持股 | A | `dwd_stock_north_hold` | P1 |
| `ods_tushare_ccass_hold` | 中央结算持股 | A | `dwd_stock_ccass_hold` | P2 |
| `ods_tushare_cyq_perf` | 筹码分布/胜率 | A | `dwd_stock_chip` | P1 |
| `ods_tushare_margin` | 两融汇总(市场/交易所) | A | `dwd_market_margin` | P2 |
| `ods_tushare_margin_detail` | 两融明细(个股) | A | `dwd_stock_margin` | P1 |
| `ods_tushare_top_list` | 龙虎榜每日明细 | A | `dwd_stock_dragon_tiger` | P2 |
| `ods_tushare_top_inst` | 龙虎榜机构成交 | A | `dwd_stock_dragon_tiger_inst` | P2 |
| `ods_tushare_block_trade` | 大宗交易 | A | `dwd_stock_block_trade` | P2 |
| `ods_tushare_index_daily` | 指数日线 | A | `dim_index`（端点可用性）+ `dwd_index_eod` | P0 |
| `ods_tushare_index_dailybasic` | 指数估值/市值 | A | `dim_index`（端点可用性）+ `dwd_index_eod`（合并） | P1 |
| `ods_tushare_sw_daily` | 申万行业日线 | A | `dwd_sw_industry_eod` | P1 |
| `ods_tushare_ci_daily` | 中信行业日线 | A | `dwd_ci_industry_eod` | P2 |
| `ods_tushare_daily_info` | 上交所市场概况 | A | `dwd_market_overview` | P2 |
| `ods_tushare_sz_daily_info` | 深交所市场概况 | A | `dwd_market_overview`（UNION） | P2 |

### 2.2 财务/公告/事件域（B 类，强 PIT）

| ODS 表 | 含义 | 类 | 目标表 | 优先级 |
|---|---|---|---|---|
| `ods_tushare_income` | 利润表 | B | `dwd_fin_income` | P0 |
| `ods_tushare_balancesheet` | 资产负债表 | B | `dwd_fin_balancesheet` | P0 |
| `ods_tushare_cashflow` | 现金流量表 | B | `dwd_fin_cashflow` | P0 |
| `ods_tushare_fina_indicator` | 财务指标(已算好比率) | B | `dwd_fin_indicator` | P0 |
| `ods_tushare_fina_mainbz` | 主营构成 | B | `dwd_fin_mainbz` | P2 |
| `ods_tushare_forecast` | 业绩预告 | B | `dwd_event_forecast` | P1 |
| `ods_tushare_express` | 业绩快报 | B | `dwd_event_express` | P1 |
| `ods_tushare_dividend` | 分红送转 | B | `dwd_event_dividend` | P1 |
| `ods_tushare_disclosure_date` | 预约披露日 | B | `dwd_disclosure_plan` | P2 |
| `ods_tushare_fina_audit` | 审计意见 | B | `dwd_fin_audit` | P2 |
| `ods_tushare_stk_holdernumber` | 股东户数 | B | `dwd_event_holder_number` | P1 |
| `ods_tushare_stk_holdertrade` | 股东增减持 | B | `dwd_event_holder_trade` | P1 |
| `ods_tushare_top10_holders` | 前十大股东 | B | `dwd_holder_top10` | P2 |
| `ods_tushare_top10_floatholders` | 前十大流通股东 | B | `dwd_holder_top10_float` | P2 |
| `ods_tushare_pledge_detail` | 股权质押明细 | B | `dwd_event_pledge_detail` | P2 |
| `ods_tushare_pledge_stat` | 股权质押统计 | B | `dwd_event_pledge_stat` | P2 |
| `ods_tushare_repurchase` | 股票回购 | B | `dwd_event_repurchase` | P2 |
| `ods_tushare_report_rc` | 卖方盈利预测/评级 | B | `dwd_analyst_report` | P1 |
| `ods_tushare_stk_rewards` | 管理层薪酬持股 | B | `dwd_manager_reward` | P3 |

### 2.3 维度/主数据域（C 类，快照取最新）

| ODS 表 | 含义 | 类 | 目标表 | 优先级 |
|---|---|---|---|---|
| `ods_tushare_stock_basic` | 股票列表(listed/delisted) | C | `dim_stock` | P0 |
| `ods_tushare_stock_company` | 公司基本信息 | C | `dim_stock`（扩展属性） | P2 |
| `ods_tushare_namechange` | 曾用名/ST 时间线 | C* | `dim_stock_name_hist`（SCD2） | P0 |
| `ods_tushare_trade_cal` | 交易日历 | C | `dim_trade_calendar` | P0 |
| `ods_tushare_index_classify` | 申万行业树 | C | `dim_sw_industry` | P1 |
| `ods_tushare_index_member_all` | 申万行业个股时点归属 | C* | `dim_stock_sw_industry_hist` | P1 |
| `ods_tushare_ci_index_member` | 中信行业个股时点归属 | C* | `dim_stock_ci_industry_hist` | P2 |
| `ods_tushare_index_weight` | 指数成分权重 | A* | `dim_index_weight`（缓变维） | P1 |
| `ods_tushare_margin_secs` | 两融标的 | C | `dim_margin_target`（缓变维） | P2 |
| `ods_tushare_new_share` | 新股发行 | C | `dim_ipo` | P1 |
| `ods_tushare_bse_mapping` | 北交所代码映射 | C | `dim_bse_code_map` | P2 |
| `ods_tushare_stock_hsgt` | 沪深股通成分 | C | `dim_hsgt_member` | P2 |
| `ods_tushare_stock_st` | ST 状态 | A*/B | `dwd_stock_st_event` | P1 |
| `ods_tushare_st` | ST 公告(另一来源) | B | `dwd_stock_st_event`（合并） | P1 |
| `ods_tushare_stk_managers` | 管理层 | C | `dim_stock_manager` | P3 |

> 标 `*` 者粒度介于两类之间：`namechange`/`stock_st` 是**事件流**，落 DWD 后可派生 SCD2 维度；`index_member_all`/`ci_index_member` 是最新分区里的全量历史行业归属区间（用 `in_date/out_date` 还原时点）；`index_weight` 是按 `trade_date` 的成分快照（缓慢变化维）。

### 2.4 ODS 表级元数据矩阵（分区语义 ≠ 业务日期，逐表登记）

「A=trade_date / B=报告期 / C=快照」是粗分类；**事件表的分区键、业务日期、可见日各不相同**，增量回填与 PIT 必须按表登记，不能套统一模板。下表为实测核对的特例，新增表须补登：

| 表 | 分区键语义 | 业务日期 | 可见日 `ann_date_eff` | 增量键 |
|---|---|---|---|---|
| daily / adj_factor / daily_basic / bak_basic / stk_limit / suspend_d / moneyflow … | `partition_date==trade_date` | trade_date | trade_date | partition_date |
| income / balancesheet / cashflow | `partition_date==报告期` | end_date | `COALESCE(f_ann_date, ann_date)` | partition_date |
| **fina_indicator** | `partition_date==报告期` | end_date | `ann_date`（**无 f_ann_date**） | partition_date |
| forecast / express / fina_audit / top10_holders / top10_floatholders / pledge_stat / disclosure_date | 大体按 end_date | end_date | ann_date | partition_date |
| dividend | `partition_date==ex_date` | ex_date | ann_date（除权口径用 ex_date） | partition_date |
| report_rc | `partition_date==report_date` | report_date | report_date | partition_date |
| stock_st | `partition_date==trade_date` | trade_date | trade_date | partition_date |
| index_member_all / ci_index_member | 最新分区全量历史区间快照 | `in_date/out_date` | 行业归属有效区间 | 取最新 partition_date |
| index_weight | 自然月末分区，`trade_date`=月末最后交易日（二者不总相等） | trade_date | trade_date | partition_date |
| stk_holdertrade / stk_holdernumber / pledge_detail | 与 `ann_date` 不稳定相等，需单独定规则 | ann_date | ann_date | partition_date + 校验 |

> **事件表 DWD 不继承 B 类统一模板**：每张表单独定义可见时间与回填窗口。完整 57 表矩阵在建表前逐表补全。

---

## 3. 分层架构与命名规范

```
ashare_ods   （已有）  各源原样外部表，只做分区裁剪，不做清洗
   │
   ├─ ashare_dim    维度层：主数据 + 缓变维 + 时间线维度（SCD2）
   │
   ├─ ashare_dwd    明细层：清洗/去重/标准化/复权/PIT 对齐后的事实明细
   │
   └─ ashare_dws    汇总/特征层：(sec_code, trade_date) 特征宽表 + 标签（ML 直接消费）
        └─ ashare_ads  （可选）策略层：选股池、组合权重、回测输入
```

### 3.1 表命名约定
- 维度：`dim_<实体>`，如 `dim_stock`、`dim_trade_calendar`。
- 明细：`dwd_<域>_<实体>[_<频率>]`，如 `dwd_stock_eod_price`、`dwd_fin_income`、`dwd_event_dividend`。
- 特征：`dws_<主题>_<粒度>`，如 `dws_stock_feature_daily`、`dws_stock_label_daily`。

### 3.2 物化策略（统一）
- DWD/DIM 一律物化为 **BigQuery 原生表**（非外部表），按 `trade_date`/`ann_date_eff` 做 **DATE 分区**，按 `sec_code` 做 **Cluster**。
- **行情类按月分区**：`PARTITION BY DATE_TRUNC(trade_date, MONTH)` + `CLUSTER BY sec_code`。**不按天**——BigQuery 单表上限 **4000 分区**，按天分区全史 ~8700 交易日会超限，且本表每日仅 ~1–2MB、按天过碎；按月仅 ~420 分区，一劳永逸（下游仍按 `trade_date` 范围裁剪，无需写 `DATE_TRUNC`）。财务类 `PARTITION BY DATE_TRUNC(ann_date_eff, MONTH)` + `CLUSTER BY sec_code`。详见 §8.1。

### 3.3 统一字段字典（数据字典 · 全文权威口径）

> **总原则**：① 字段统一 snake_case；② 所有日期落库为 `DATE`、时间为 `TIMESTAMP`；③ **量纲统一到「元 / 股」**；④ **ODS 源字段保留各源原名，仅在 ODS→DWD/DIM 出口做一次 rename/单位换算**，下游一律用标准名；⑤ DWD 事实表统一追加血缘字段。

**(A) 标识与维度属性**

| 标准名 | 类型 | 含义 | 收敛自（源字段） | 格式/取值 |
|---|---|---|---|---|
| `sec_code` | STRING | **证券代码（统一主键）** | `ts_code` / `con_code` / `code` / `index_code` | `600000.SH`（标准后缀 `.SH/.SZ/.BJ`） |
| `sec_symbol` | STRING | 纯数字代码（展示，不作 join 键） | `symbol` | `600000` |
| `sec_name` | STRING | 证券简称 | `name` | — |
| `sec_type` | STRING | 品种 | （派生） | `stock`/`index`/`fund`/`cb`/`industry` |
| `exchange` | STRING | 交易所 | `exchange` | `SSE`/`SZSE`/`BSE` |
| `board_type` | STRING | 板块 | （派生自代码前缀） | `MAIN`/`STAR`/`CHINEXT`/`BSE` |
| `list_date`/`delist_date` | DATE | 上市/退市日 | 同名 | — |

> **`sec_code` 值标准化**：当前 Tushare 股票源即 `.SH/.SZ/.BJ` 后缀，通常直接采用为 canonical 格式。若同一证券/指数存在多个源代码或交易所代码（如 ODS 沪深300 `399300.SZ` 归一为 canonical `000300.SH`），DWD/DIM 出口仍以 canonical `sec_code` 为主键，并保留 `source_sec_code` 追溯来源代码。未来接入其它源（如米筐 `.XSHG/.XSHE`、Wind）时，**在该源的接入层转换成标准后缀**，保证字段名与值都统一。北交所历史代码用 `dim_bse_code_map`（`o_code`→`n_code`）归一。

**(B) 日期 / 时间（日期统一 `DATE`）**

| 标准名 | 含义 | 收敛自 |
|---|---|---|
| `trade_date` | 交易日（事实表时间轴） | `trade_date` |
| `cal_date` | 日历日（仅 `dim_trade_calendar`，含非交易日） | `cal_date` |
| `pre_trade_date` | 上一交易日 | `pretrade_date` |
| `ann_date_eff` | **数据可见日（PIT 连接键）** | **按表定义**（见 §4.3）：income/bs/cf=`COALESCE(f_ann_date, ann_date)`；`fina_indicator` 仅 `ann_date`（无 f_ann_date）；事件表用各自公告/实施日 |
| `announce_date` | 公告日（原始） | `ann_date` |
| `report_period` | 报告期 | `end_date`（财报） |
| `ex_date`/`record_date`/`pay_date` | 除权/登记/派息日 | 同名 |
| `ipo_date` | 上市日（新股表） | `ipo_date` |

**(C) 行情 OHLCV**

| 标准名 | 含义 | 源 | 标准单位 |
|---|---|---|---|
| `open`/`high`/`low`/`close`/`pre_close` | 开/高/低/收/昨收 | 同名 | 元（未复权原始价） |
| `pct_chg` | 涨跌幅 | `pct_chg` | %（校验用） |
| `volume_share` | 成交量 | `vol` | **股** |
| `amount_cny` | 成交额 | `amount` | **元** |

**(D) 复权与收益（派生，前后缀风格定为后缀）**

| 标准名 | 含义 |
|---|---|
| `adj_factor` | 累计后复权因子 |
| `open_hfq`/`high_hfq`/`low_hfq`/`close_hfq` | 后复权价（指标/收益计算用） |
| `close_qfq`/… | 前复权价（仅展示，**不入训练特征**） |
| `ret_1d` | 复权日收益率 |
| `fwd_ret_5d`（1/5/10/20…） | 未来 k 日复权收益（标签） |

**(E) 估值 / 市值 / 份额**

| 标准名 | 含义 | 标准单位 |
|---|---|---|
| `turnover_rate`/`turnover_rate_f`/`volume_ratio` | 换手率/自由流通换手/量比 | %/倍 |
| `pe`/`pe_ttm`/`pb`/`ps`/`ps_ttm`/`dv_ratio`/`dv_ttm` | 估值 | 倍/% |
| `total_share`/`float_share`/`free_share` | 总/流通/自由流通股本 | **股** |
| `total_mv`/`circ_mv` | 总/流通市值 | **元** |

**(F) 血缘 / 元数据（DWD 事实表统一追加；DIM 可只带 `source_system`）**

| 标准名 | 类型 | 含义 | 收敛自 |
|---|---|---|---|
| `source_system` | STRING | 数据来源系统 | `_source`（值如 `tushare`/`wind`/`rqdata`） |
| `ingested_at` | TIMESTAMP | 入库时间 | `_ingested_at`（ODS 为 STRING，需 parse） |

**(G) 单位归一对照表**（ODS→标准 元/股 的换算系数，**以各源接口文档为准，接入新源时按源调整**）

| 源表.字段 | 原单位 | 标准 | 换算 |
|---|---|---|---|
| `daily.vol` | 手 | 股 | `× 100` |
| `daily.amount` | 千元 | 元 | `× 1000` |
| `daily_basic.total_share/float_share/free_share` | 万股 | 股 | `× 10000` |
| `daily_basic.total_mv/circ_mv` | 万元 | 元 | `× 10000` |
| `bak_basic.float_share/total_share` | 亿股 | 股 | `× 100000000` |
| `bak_basic.total_assets/liquid_assets/fixed_assets` | 亿元 | 元 | `× 100000000` |
| `moneyflow.*_vol` | 手 | 股 | `× 100` |
| `moneyflow.*_amount` / `net_mf_amount` | 万元 | 元 | `× 10000` |
| 财务三表金额字段 | 元（多数） | 元 | `× 1`（逐接口核对） |

> ⚠️ **同名字段不同表单位可能不同**（如 `daily.amount` 是千元、`moneyflow.amount` 是万元）。换算必须按"表 + 字段"查表，不能一刀切。

**(H) DWD 落库单位准入规则（OQ-006）**

所有进入 DWD 的金额、数量、股本、市值、价格、比率字段必须遵守以下规则：

- **FR-UNIT-1：标准字段必须带单位后缀**。金额字段统一 `_cny`，数量/股本字段统一 `_share`，保留源单位字段时用 `_k_cny`、`_10k_cny`、`_lot`、`_10k_share` 等后缀。示例：`daily.amount` → `amount_k_cny`（raw，千元）；`daily.amount * 1000` → `amount_cny`（standard，元）。
- **FR-UNIT-2：换算只能发生在 ODS -> DWD**。DWS/ADS 不允许出现单位乘法常数（如 `* 1000`、`* 10000`）。如确需派生金额或股数，必须基于 DWD 标准字段计算。
- **FR-UNIT-3：高风险字段保留 raw 字段**。资金流、财务、北向、持股、质押、回购等高风险接口，首版 DWD 建议同时保留 raw 字段和标准字段。
- **FR-UNIT-4：字段 description 写清换算来源**。示例：`成交额，元，由 Tushare daily.amount 千元 * 1000 换算`。
- **FR-UNIT-5：新 DWD PR 必须附单位映射**。新增或修改 DWD 标准字段时，PR 必须同时新增或更新 `ashare_meta.ods_field_unit_map` 记录和 `sql/qa/05_oq006_unit_checks.sql` 覆盖范围，并把 `05_oq006_unit_checks.sql` 纳入该 PR 的必跑 QA。没有 `verified` 映射，不得合并。

单位换算的唯一事实来源是 `data-aquarium.ashare_meta.ods_field_unit_map`，粒度为 `source_system + endpoint + ods_table + source_field + dwd_table + dwd_field`。`verification_status='verified'` 需同时具备官方文档确认和数据自洽校验；`pending` 字段不得作为标准 DWD 输出。

### 3.4 表与字段注释（description）规范

与 ODS 一致，所有 `dim_*` / `dwd_*` / `dws_*` 表都必须带 **表级 description** 与 **字段级 description**（中文，业务口径，在 BigQuery 控制台与 `INFORMATION_SCHEMA` 可查）。风格沿用 ODS——业务含义 + 单位/口径 + 必要算法（例：ODS `amount`=「成交额（千元）」，DWD 归一后写「成交额（元）」；ODS `pct_chg` 注明算法，DWD 同样保留）。

**落地方式**（按工程化程度递增）：
1. **内联 DDL**（建表即注释，字段少的维度表首选，见 §5.1 模板）：
   `CREATE TABLE x (col TYPE OPTIONS(description="…"), …) OPTIONS(description="表说明") AS SELECT …`
2. **后置 ALTER**（CTAS 由计算列生成、列多的表用，如 §6.1）：
   `ALTER TABLE x SET OPTIONS(description="…");` / `ALTER TABLE x ALTER COLUMN col SET OPTIONS(description="…");`
3. **dbt `persist_docs` 或 `bq update --schema schema.json`**（推荐）：描述写在 `schema.yml`/schema JSON，随模型入 git，一键刷到 BQ，可版本化。

**描述继承（省力且与 ODS 对齐）**：DWD 中**保留原名**的字段（尤其财务三表数百个字段）直接**继承 ODS 同名字段的描述**；仅改名（`ts_code`→`sec_code`）、派生（`ret_1d`/`*_hfq`/`is_tradable`）、换算（`volume`/`amount`/`*_mv`/`*_share`）字段需手写或加注「单位已转元/股」。继承可脚本化：
```bash
# 导出 ODS 字段描述 → 套用到目标表同名字段 → 刷新目标表 schema
bq show --schema --format=prettyjson data-aquarium:ashare_ods.ods_tushare_income > ods.json
#（脚本：把 ods.json 的 name→description 映射到目标表 schema，改名/派生字段单独补，输出 dwd.json）
bq update --schema dwd.json data-aquarium:ashare_dwd.dwd_fin_income
```
这样既"像 ODS 一样有表/字段解释"，财务大表又无需手写。

---

## 4. 横切设计原则（量化语境的"地基"）

### 4.1 标识与日期标准化
- 证券主键统一 `sec_code`（见 §3.3-A）。源字段 `ts_code`/`con_code`/`code`/`index_code` 在 ODS→DWD/DIM 出口统一为 canonical `sec_code`；若源代码与 canonical 代码不同，保留 `source_sec_code` 做血缘追溯；保留 `sec_symbol` 仅供展示，不作 join 键；并用 `sec_type` 区分品种，使股票/指数/基金/可转债共用一套主键与连接逻辑。
- 所有 `*_date` 落库转 `DATE`。`stock_basic.delist_date` 当前在 ODS 中是 `STRING`，用 `SAFE.PARSE_DATE('%Y%m%d', NULLIF(delist_date, ''))` 解析。
- 交易日对齐一律以 `dim_trade_calendar`（`exchange='SSE'`）为准，禁止用自然日 `lag`。

### 4.2 复权（Adjustment）—— 收益率与价格特征的正确口径
Tushare `adj_factor` 为**累计后复权因子**。

- **后复权价**：`<col>_hfq = <raw> * adj_factor`（单调、无未来依赖，**推荐用于技术指标与收益率**）。
- **前复权价（截至基准日 T0）**：`<col>_qfq = <raw> * adj_factor / adj_factor_at_T0`。
  > ⚠️ 前复权用到了"基准日"的因子，**隐含未来除权信息**。若 T0 取样本最新日，则历史前复权价会随每次新除权而整体变化，构成**未来泄露**。因此：**训练特征不要用前复权价**；`_qfq` 仅用于人工看图/展示。
- **复权收益率（核心标签与动量特征基础）**：
  ```
  ret_1d = (close * adj_factor) / LAG(close * adj_factor) - 1
  ```
  等价于"用后复权价算简单收益"，在除权日自动正确。生产中用 `daily.pct_chg` 做交叉校验（除权日两者应一致；不一致则告警）。
- **技术指标**（MA/EMA/RSI/波动率等）一律在**后复权价**序列上计算，避免除权断点产生假信号。

### 4.3 PIT（Point-In-Time）—— 防未来函数的第一原则

**基准执行假设（全文据此）**：EOD 盘后用截至 `t` 日收盘已可见的信息生成因子，**`t+1` 开盘 / VWAP 建仓**。下面的可见性判断都以此为前提；若改为"`t` 日开盘前交易"，须把可见日整体右移一个交易日。

- **行情/估值**（`daily`/`daily_basic`）：当日盘后即可得，`trade_date` 当日可见，PIT 安全。
- **财务**：`partition_date == 报告期`，**绝不能当可见时间**；可见时间用 `ann_date_eff`，且**按表定义**（见下表）。在任意 `trade_date` 只能用 `ann_date_eff <= trade_date` 的版本 → as-of（§7.3）。
- **事件**：可见时间用各自的公告/实施日，按表定义（见下表）。

**表级可见日规则表**（实测核对，57 张表；新增表须在此登记）：

| 表 | `ann_date_eff` 取法 | 说明 |
|---|---|---|
| income / balancesheet / cashflow | `COALESCE(f_ann_date, ann_date)` | 有 `f_ann_date`，实际披露日优先 |
| **fina_indicator** | `ann_date` | **无 `f_ann_date`**（实测） |
| forecast / express / fina_audit / stk_holdernumber / stk_holdertrade | `ann_date` | 公告日 |
| dividend | `ann_date`（除权口径用 `ex_date`） | 分区实测 ≈ `ex_date` |
| report_rc | `report_date` | 卖方报告日 |
| top10_holders / top10_floatholders / pledge_stat | `ann_date` | 公告日 |
| stock_st / st | `trade_date` / `imp_date` | ST 生效日 |

> **盘后/非交易日公告须右移**：派生 `visible_trade_date` =「`ann_date_eff` 当日若是交易日且基准假设下可得，则取当日，否则映射到**下一个开市交易日**」。A 股多数公告盘后披露，基准假设下 `t` 日公告可用于 `t+1` 建仓；若公告日落在周末/停牌/盘后无法当日消化，`visible_trade_date` 必须落到下一个可建仓交易日。as-of join 一律用 `visible_trade_date <= feature_date`，避免把"名义可见但不可交易"的日期当信号日。

- **标签**用未来数据允许（那是 `y`），但必须与特征**时间错位**：`t` 日特征 → 标签从 `t+1` 起算（§7.4），杜绝用 `t` 日收盘信息进入入场价。

### 4.4 去重与财务版本（Deduplication & Versioning）
- **A 类行情表**：单分区内 `(sec_code, trade_date)` 已唯一（实测 `daily` 每日 5500+ 行）。跨分区无重复，**无需去重**；回填重跑按 `_ingested_at` 取最新兜底。
- **B 类财务表 —— 必须区分两种产物**（同一 `(sec_code, report_period)` 因 `report_type`/多次修正存在多条，且修正可能**跨年发生**，例如某期年报在次年、第三年又被修正）：
  - **① 版本事实表（严格 PIT 的主表，推荐）**：保留**每个公告版本**，主键 `(sec_code, report_period, ann_date_eff, update_flag)`（+ `ingested_at` 兜底）。回测某日做 as-of 时先 `ann_date_eff <= feature_date` 过滤、再取最新版本，能真实还原"当时已公布的口径"。
  - **② 最新快照表（便捷表，如 `dwd_fin_indicator_latest`）**：每期只留最新修正版：
    ```sql
    QUALIFY ROW_NUMBER() OVER (
      PARTITION BY sec_code, report_period
      ORDER BY update_flag DESC, ann_date_eff DESC, ingested_at DESC) = 1
    ```
    > ⚠️ 最新快照会把**后期修正泄漏到历史**，**不支持严格历史 PIT、不可作为回测特征的唯一来源**；仅用于"看当前基本面"等非回测场景。
  - 按需先过滤 `report_type`（合并报表通常取 `'1'`）。`ann_date_eff` 按 §4.3 表级规则取（注意 `fina_indicator` 无 `f_ann_date`）。

### 4.5 Universe 与可交易性
- **幸存者偏差**：`dim_stock` 必须 UNION `stock_basic` 的 `listed` + `delisted`，保留退市股 `list_date`/`delist_date`，回测区间内"在市"才纳入截面。
- **样本骨架必须含停牌日**：价格 DWD 以「交易日历开市日 × 当日在市股票」为骨架（§6.1），停牌日**保留行**（价格 NULL、`is_suspended=true`、`is_tradable=false`）。**不能**以"个股有行情的日子"为骨架——Tushare `daily` 在停牌日无该股行，从 `daily` 起表会让停牌日整行消失，进而 `t+k` 标签错位、高估可成交性。
- **可交易标记**（落 `dwd_stock_eod_price`）：
  - `is_suspended`：停牌（骨架有行但 `daily` 无行，或 `suspend_d` 命中，或 `volume=0`）。
  - `is_limit_up` / `is_limit_down`：收盘封板（`close>=up_limit` / `close<=down_limit`）。
  - `is_one_word_limit_up` / `is_one_word_limit_down`：一字涨/跌停（`high==low` 且触及对应限价）——**区分方向**：一字涨停主要挡买入、一字跌停主要挡卖出。
  - `is_open_limit_up` / `is_open_limit_down`：**开盘**即触及涨/跌停（`open >= up_limit` / `open <= down_limit`），比"全天一字板"更贴近 t+1 开盘可成交性。
  - `can_buy_open` / `can_sell_open`：t+1 开盘可买/卖近似 = 非停牌 且 非 `is_open_limit_up`/`is_open_limit_down`。**仍是 EOD 近似**（开盘封板后盘中可能打开，精确需分钟数据）。
  - `is_newly_listed`（上市未满 N 日，默认 60 自然日）、`is_st`（±5%，来自 `dwd_stock_st_event`/`namechange`）。
  - `is_tradable`：综合样本掩码（非停牌 且 非一字板 且 在市）。
- **涨跌停幅度**：直接用 `stk_limit.up_limit`/`down_limit`（Tushare 已按板块算好 ±10%/±5%/±20%/±30%），不自己硬编码。

> 不单列收盘方向 `can_buy_close`/`can_sell_close`：EOD 下收盘封板已由 `is_limit_up/down` 表达，且本项目按 `t+1` 开盘建仓（理由见 `docs/reviews/…-review-response.md` 调整-2）。

### 4.6 分区裁剪与增量（成本/性能）
- ODS 是外部表且**强制分区裁剪**：所有读 ODS 的 SQL 必须含 `WHERE partition_date <谓词>`（常量比较，`partition_date` 为 `YYYYMMDD` 字符串）。
- DWD/DIM 构建走**增量**：行情类按 `partition_date BETWEEN @start AND @end` 处理新增交易日；财务/事件类按 `partition_date`（report period）或 `ann_date` 增量 + MERGE 去重。
- DWD 原生表自身按 `DATE` 分区，下游 `dws` 拼接时同样分区裁剪，控制扫描量。
- **当前阶段目标**：先把 **2019-01-01 起** 的 DWD/DWS 数据做正确；2019 年以前的正式样本/明细扩展是后续阶段。当前只在三类必要场景触碰 2019 前数据：财务/事件 PIT 前移、行情 lookback buffer、维度/日历历史快照。
- **为支持 2019+ 所需的 2019 年前数据范围（不要混成“全历史写入”）**：

  | 数据族 | ODS 读取 / 接口参数下界 | DWD 写入下界 | DWS 写入下界 | 原因 | 备注 |
  |---|---|---|---|---|---|
  | 财务 P0：`income` / `balancesheet` / `cashflow` / `fina_indicator` | `partition_date >= '20170101'`（或接口 `start_date/period` 从 2017 起） | `report_period >= 2017-01-01`，保留版本事实 | `trade_date >= 2019-01-01` | 2019 初 PIT 需要 2018 三季报/2017 年报；同比/基期也需去年同期 | `partition_date == end_date`，不能当可见日；可见日仍用 §4.3 表级规则 |
  | 事件 P1：`forecast` / `express` / `dividend` / `disclosure_date` / `stk_holdernumber` / `stk_holdertrade` / `report_rc` | 从 2017 起，按 §2.4 的表级分区语义取参数 | 事件业务日期/报告期 >= 2017-01-01 | `trade_date >= 2019-01-01` | 2019 样本可能需要 2017-2018 已公告事件状态或窗口特征 | `dividend`/`report_rc` 等不是统一 `end_date` 分区，按表配置 |
  | 事件/治理 P2：`fina_mainbz` / `fina_audit` / `top10_holders` / `top10_floatholders` / `pledge_detail` / `pledge_stat` / `repurchase` / `stk_rewards` | 从 2017 起，按表级元数据矩阵执行 | 业务日期/报告期 >= 2017-01-01 | `trade_date >= 2019-01-01` | 风控/治理类历史状态或窗口特征 | P2 落地时补齐表级规则 |
  | 行情核心：`daily` + `adj_factor` | `@lookback_start_date`，由最大滚动窗口决定；最小读到 2018 最后一个交易日，250 日窗口可保守读 2018 全年 | `trade_date >= 2019-01-01` | `trade_date >= 2019-01-01` | `ret_1d` 需要 t-1；MA/波动率等滚动特征需要 warm-up | 2019 前行只作为构建 buffer，不落最终 DWD/DWS |
  | 估值/资金/筹码：`daily_basic` / `moneyflow` / `cyq_perf` 等 | 若仅落 DWD 明细，读写 2019+；若构建滚动特征，则按最大窗口多读 buffer | `trade_date >= 2019-01-01` | `trade_date >= 2019-01-01` | 滚动换手、滚动资金流、筹码变化等需要 warm-up | buffer 下界与特征窗口一致 |
  | 维度/日历：`trade_cal` / `stock_basic` / `namechange` | `trade_cal`、`stock_basic` 取最新快照；`namechange` 保留全量历史事件 | 维度全量 / SCD2 全量 | 作为 join 维度使用 | 最新快照或事件历史天然含 2019 前信息 | 不属于“按分区往前拉旧行情”；正式扩展 2019 前样本时复用 |

- **写入范围 vs 读取范围分离（lookback buffer，重要）**：行情类最终 DWD/DWS 仍只写 `trade_date >= 2019-01-01`，但构建时按指标最大 lookback 多读早期 buffer。`ret_1d` 至少读到 2018 年最后一个交易日；MA/波动率等滚动特征按最大窗口（如 120/250 日）多读足够交易日。否则 2019 年初样本的滚动特征会因 warm-up 不足而失真。增量批次边界同理回看（§8.2）。
- **强制分区过滤（控成本）**：行情类 DWD 表建表设 `OPTIONS(require_partition_filter = TRUE)`，与 ODS 一致**强制下游必须带 `trade_date` 过滤**，否则报错，杜绝误扫全史；财务类（as-of 模式）不开。注意：**只有分区列能强制，聚簇列无法强制过滤**（BigQuery 无此选项）。

---

## 5. DIM 维度层设计

### 5.1 `dim_trade_calendar` —— 交易日历（P0，所有时间逻辑的基准）
- **源**：`ods_tushare_trade_cal`（C 类快照，取最新 `partition_date`）。
- **粒度**：`(exchange, cal_date)`。量化主用 `exchange='SSE'`。
- **关键字段**：`exchange, cal_date(DATE), is_open(1/0), pre_trade_date(DATE), trade_date_seq(交易日序号)`。
- **构建要点**：
  ```sql
  CREATE OR REPLACE TABLE ashare_dim.dim_trade_calendar (
    exchange       STRING OPTIONS(description="交易所：SSE 上交所 / SZSE 深交所 / BSE 北交所"),
    cal_date       DATE   OPTIONS(description="日历日（含非交易日）"),
    is_open        INT64  OPTIONS(description="是否交易日：1 交易 / 0 休市"),
    pre_trade_date DATE   OPTIONS(description="上一交易日"),
    trade_date_seq INT64  OPTIONS(description="交易日序号，仅 is_open=1 递增；用于按交易日定位 t±k")
  )
  OPTIONS(description="交易日历维度；来源 Tushare trade_cal 最新快照，量化所有时间逻辑的基准") AS
  WITH latest AS (
    SELECT MAX(partition_date) pd FROM ashare_ods.ods_tushare_trade_cal
    WHERE partition_date >= '19900101'
  )
  SELECT
    exchange,
    PARSE_DATE('%Y%m%d', cal_date)             AS cal_date,
    is_open,
    SAFE.PARSE_DATE('%Y%m%d', pretrade_date)   AS pre_trade_date,
    IF(is_open=1,
       COUNTIF(is_open=1) OVER (PARTITION BY exchange ORDER BY cal_date),
       NULL) AS trade_date_seq          -- 仅开市日递增编号；休市日为 NULL
  FROM ashare_ods.ods_tushare_trade_cal, latest
  WHERE partition_date = latest.pd;
  -- 注1：CTAS 带显式列定义时，列名/顺序/类型须与 SELECT 输出一致（此处恰好匹配）
  -- 注2：trade_date_seq 用累计 COUNTIF 实现"第几个交易日"，供 §7.4 标签按市场交易日序列定位 t±k
  ```
  > `trade_date_seq` 用于 §7.4 标签的"未来第 k 交易日"对齐，避免自然日偏移。

### 5.2 `dim_stock` —— 证券主数据（P0，universe 之源）
- **源**：`ods_tushare_stock_basic`（**UNION `endpoint='stock_basic_listed'` 与 `'stock_basic_delisted'`**，取最新 `partition_date`）+ 可选 `stock_company` 扩展。
- **粒度**：`sec_code`（当前主数据，1 行/股）。
- **关键字段**：`sec_code, sec_symbol, sec_name, sec_type(='stock'), area, industry(tushare口径), market, exchange, board_type, curr_type, list_status(L/D/P), list_date, delist_date, is_hs, is_delisted, source_system`。
- **构建要点**：
  ```sql
  CREATE OR REPLACE TABLE ashare_dim.dim_stock
  OPTIONS(description="证券主数据维度：含在市与已退市股票（stock_basic 最新快照 listed+delisted UNION）；universe 与幸存者偏差处理之源") AS
  WITH latest AS (
    SELECT MAX(partition_date) pd FROM ashare_ods.ods_tushare_stock_basic
    WHERE partition_date >= '19900101'
  )
  SELECT
    ts_code                         AS sec_code,        -- 出口归一
    symbol                          AS sec_symbol,
    name                            AS sec_name,
    'stock'                         AS sec_type,
    area, industry, market, exchange, curr_type,
    list_status,
    PARSE_DATE('%Y%m%d', list_date) AS list_date,
    SAFE.PARSE_DATE('%Y%m%d', NULLIF(delist_date, '')) AS delist_date,

    is_hs,
    -- 板块（影响涨跌幅、上市规则）
    CASE
      WHEN STARTS_WITH(ts_code,'688') THEN 'STAR'        -- 科创板 ±20%
      WHEN STARTS_WITH(ts_code,'300') OR STARTS_WITH(ts_code,'301') THEN 'CHINEXT' -- 创业板 ±20%
      WHEN exchange='BSE' OR STARTS_WITH(ts_code,'8') OR STARTS_WITH(ts_code,'4') THEN 'BSE'  -- 北交所 ±30%
      ELSE 'MAIN'                                          -- 主板 ±10%
    END                             AS board_type,
    (list_status = 'D')             AS is_delisted,
    COALESCE(_source, 'tushare')    AS source_system
  FROM ashare_ods.ods_tushare_stock_basic, latest
  WHERE partition_date = latest.pd
    AND endpoint IN ('stock_basic_listed','stock_basic_delisted');
  ```
  > **退市股一定要进表**（实测 delisted endpoint 每日 ~325 行）。回测 universe = `dim_stock` 中 `list_date <= trade_date AND (delist_date IS NULL OR trade_date < delist_date)`。

- **退市日读取口径（OQ-007 已关闭）**：`stock_basic_delisted.delist_date` 当前已由上游统一为 `STRING`，最新 delisted 分区可直读并解析为 `DATE`。处理：
  - **主口径**：`dim_stock.delist_date` 对 `list_status='D'` 优先使用 ODS `stock_basic_delisted.delist_date`，作为生命周期半开区间 `[list_date, delist_date)` 的正式边界。
  - **兜底**：仅当 ODS `delist_date` 缺失时，才使用该股在 `daily` 中的最后交易日加一天（`MAX(trade_date) + 1`）近似。
  - **质量门禁**：P0 QA 断言 `stock_basic_delisted.delist_date` 可读、可解析，且 `dim_stock` 中有 ODS 退市日的代码必须与 ODS 退市日一致；2019+ `daily` 出现但 `stock_basic` 缺失的代码仍从价格表补主数据或入异常表。

### 5.3 `dim_stock_name_hist` —— 名称/ST 状态时间线（P0，SCD2）
- **源**：`ods_tushare_namechange`（事件流：`start_date`/`end_date`/`change_reason`）。
- **粒度**：`(sec_code, start_date)`，每段名称一行（SCD2 区间）。
- **用途**：按 `trade_date` 还原**当时的股票名**与 **ST 状态**（名称含 `ST`/`*ST`/`退`）。ST 判定优先用此表，`stock_st`/`st` 作交叉校验。
- **关键字段**：`sec_code, sec_name, start_date(DATE), end_date(DATE, 开区间用 9999-12-31 填充), is_st(派生), is_star_st(派生)`。
- **PIT 用法**：`JOIN ON trade_date BETWEEN start_date AND end_date`。

### 5.4 `dim_sw_industry` + `dim_stock_sw_industry_hist` —— 申万行业与个股时点归属（P1）
- **源**：`ods_tushare_index_classify`（申万行业树：`index_code, industry_name, parent_code, level, src`）。
- **行业树粒度**：行业节点（`industry_code`，含 L1/L2/L3 层级，`parent_code` 自关联成树）。
- **个股归属源**：`ods_tushare_index_member_all`（字段含 `l1_code/l1_name/l2_code/l2_name/l3_code/l3_name/ts_code/in_date/out_date/is_new`；当前 ODS 已补采）。
- **个股归属粒度**：`(sec_code, valid_from, sw_l3_code)`，一段行业归属区间一行。
- **建议目标字段**：
  - `sec_code`
  - `valid_from = PARSE_DATE('%Y%m%d', in_date)`
  - `valid_to = COALESCE(PARSE_DATE('%Y%m%d', out_date), DATE '9999-12-31')`
  - `sw_l1_code/sw_l1_name`
  - `sw_l2_code/sw_l2_name`
  - `sw_l3_code/sw_l3_name`
  - `is_current = (is_new='Y')`
  - `source_system/ingested_at/source_partition_date`
- **PIT 用法**：
  ```sql
  JOIN ashare_dim.dim_stock_sw_industry_hist h
    ON h.sec_code = base.sec_code
   AND h.valid_from <= base.trade_date
   AND base.trade_date < h.valid_to
  ```
  `is_new='Y'` 只能表示当前最新归属，不能用于历史回测 join。回测必须使用 `in_date/out_date` 区间，避免用当前行业回填历史。
- **区间边界**：默认采用半开区间 `[valid_from, valid_to)`；落地 QA 需抽样验证 `out_date` 当天是否应仍有效，如 Tushare/申万口径显示当天仍有效，再统一调整为闭区间。
- **用途**：行业中性化、行业动量、行业暴露约束、行业内选股。

### 5.5 `dim_stock_ci_industry_hist` —— 中信行业个股时点归属（P2）
- **源**：`ods_tushare_ci_index_member`（字段结构与 `index_member_all` 一致，行业代码后缀为 `.CI`）。
- **粒度**：`(sec_code, valid_from, ci_l3_code)`。
- **用途**：作为申万行业体系的备选/对照；用于中信行业轮动、行业暴露诊断、行业中性化稳健性检验。
- **PIT 用法**：同 `dim_stock_sw_industry_hist`，使用 `in_date/out_date` 区间，禁止用 `is_new` 回填历史。

### 5.6 `dim_index` —— 指数主维表（P0，canonical 映射与端点可用性）
- **源**：静态指数候选清单 + `ods_tushare_index_daily` / `ods_tushare_index_dailybasic` 当前 DWD 范围内实测端点聚合。
- **粒度**：`(sec_code, source_sec_code)`，其中 `sec_code` 是 DWD/DWS/ADS 业务侧 canonical 指数代码，`source_sec_code` 是 ODS/Tushare 实际 `ts_code`。
- **用途**：
  - 维护 `source_sec_code -> sec_code` 映射，例如沪深300 ODS 来源 `399300.SZ` 统一输出 canonical `000300.SH`。
  - 记录 `daily_endpoint` / `dailybasic_endpoint`、起止日期、`has_daily`、`has_dailybasic`。
  - 区分收益 benchmark 可用性与指数估值/市值特征可用性；收益基准只要求 `has_daily=TRUE`，依赖 PE/PB/市值字段的市场状态特征必须要求 `has_dailybasic=TRUE`。
  - runner 使用 `benchmark_sec_code` 前必须校验 `dim_index.is_benchmark_candidate=TRUE`，并校验 `dwd_index_eod` 在完整 NAV 窗口内逐开市日覆盖。
- **当前关键事实**：`000852.SH`（中证1000）有 `index_daily` 价格端点，可作为收益基准候选；当前无 `index_dailybasic` 端点，不能作为依赖估值字段的市场状态来源。当前 ODS 无 `index_daily_000300_SH`，沪深300由 `399300.SZ -> 000300.SH` 映射输出。

### 5.7 `dim_index_weight` —— 指数成分权重（P1，缓变维）
- **源**：`ods_tushare_index_weight`（`index_code, con_code, trade_date, weight`，A* 类按调仓日快照）。
- **粒度**：`(index_code, sec_code, trade_date)`（`index_code` 为指数、`sec_code` 来自 `con_code`）。
- **用途**：判断个股是否属于沪深300/中证500/中证1000/中证2000 等基准；做指数增强、成分内选股、基准对齐。按 as-of（`trade_date <= 当前`取最近一次成分）使用。

### 5.8 其它维度（P2/P3）
- `dim_margin_target`：源 `margin_secs`，两融标的（缓变维），派生 `is_margin_target` 特征。
- `dim_ipo`：源 `new_share`，含 `ipo_date/issue_date/price/pe`，支撑"次新股"主题与上市日对齐。
- `dim_bse_code_map`：源 `bse_mapping`，北交所老代码↔新代码，长历史拼接用。
- `dim_hsgt_member`：源 `stock_hsgt`，沪深股通成分历史（事件 `type`/`type_name`）。
- `dim_stock_manager`：源 `stk_managers`，治理类，低优先。

---

## 6. DWD 明细层设计

### 6.1 `dwd_stock_eod_price` —— 复权日线主表（P0，全仓库最核心）
把"价、量、复权、涨跌停、停牌、可交易性"整合到一张以 `(sec_code, trade_date)` 为粒度的明细表，是几乎所有特征的基础。

- **源**：`daily`（OHLCV）+ `adj_factor`（复权）+ `stk_limit`（涨跌停价）+ `suspend_d`（停牌）+ `dim_stock`（上市/退市/板块）。
- **粒度**：`(sec_code, trade_date)`，分区 `PARTITION BY DATE_TRUNC(trade_date, MONTH)`（按月，见 §8.1），聚类 `CLUSTER BY sec_code`。
- **核心字段**：

| 字段 | 来源/算法 | 标准单位/说明 |
|---|---|---|
| `sec_code, trade_date` | univ 骨架（交易日历开市日 × 在市股票） | 主键；**停牌日也有行** |
| `open, high, low, close, pre_close` | daily | 元，未复权；**停牌日为 NULL** |
| `volume_lot` | `daily.vol` | 手，保留源单位 |
| `amount_k_cny` | `daily.amount` | 千元，保留源单位 |
| `volume_share` | `daily.vol * 100` | **股** |
| `amount_cny` | `daily.amount * 1000` | **元**（daily 原千元） |
| `pct_chg` | daily.pct_chg | %（校验用） |
| `adj_factor` | adj_factor | 累计后复权因子 |
| `open_hfq/high_hfq/low_hfq/close_hfq` | `raw * adj_factor` | 后复权价（指标计算用） |
| `ret_1d` | 复权收益，跨停牌用最近有价日 | 见 SQL（`LAST_VALUE … IGNORE NULLS`） |
| `up_limit, down_limit` | stk_limit | 元，当日涨跌停价 |
| `is_limit_up, is_limit_down` | `close>=up_limit` / `close<=down_limit` | 收盘封板 |
| `is_one_word_limit_up`/`_down` | `high==low` 且触及涨/跌停 | 一字涨/跌停（**区分方向**） |
| `is_open_limit_up`/`_down` | `open>=up_limit` / `open<=down_limit` | 开盘即涨/跌停（基于开盘价） |
| `can_buy_open`/`can_sell_open` | 非停牌 且 非 `is_open_limit_up/down` | t+1 开盘可买/卖近似（EOD 近似） |
| `is_suspended` | daily 无行 或 suspend_d 命中 或 volume=0 | 停牌掩码（停牌日保留行、价格 NULL） |
| `is_tradable` | 非停牌 且 非一字板 且 在市 | **综合样本掩码** |
| `is_newly_listed` | `trade_date - list_date < N` | 次新标记 |
| `source_system, ingested_at` | 血缘 | — |

- **构建要点（核心 SQL 骨架）**：
  ```sql
  CREATE OR REPLACE TABLE ashare_dwd.dwd_stock_eod_price
  PARTITION BY DATE_TRUNC(trade_date, MONTH) CLUSTER BY sec_code
  OPTIONS(description="个股复权日线主表：交易日历×在市股票为骨架（含停牌日空行）；整合未复权 OHLCV、后复权价(_hfq)、复权收益、涨跌停/停牌/方向性可交易标记；粒度 (sec_code, trade_date)，金额元、量股",
          require_partition_filter = TRUE) AS
  WITH cal AS (                       -- 市场开市日（来自交易日历）
    SELECT cal_date AS trade_date FROM ashare_dim.dim_trade_calendar
    WHERE exchange='SSE' AND is_open=1 AND cal_date BETWEEN @start AND @end   -- @start/@end 为 DATE
  ),
  univ AS (                           -- 骨架：开市日 × 当日在市股票（含退市股在市区间）
    SELECT s.sec_code, c.trade_date, s.list_date, s.delist_date, s.board_type
    FROM cal c JOIN ashare_dim.dim_stock s
      ON c.trade_date >= s.list_date AND (s.delist_date IS NULL OR c.trade_date < s.delist_date)
  ),
  d AS (                              -- ODS daily：出口归一 sec_code + 单位换算
    SELECT ts_code AS sec_code, PARSE_DATE('%Y%m%d', trade_date) trade_date,
           open, high, low, close, pre_close, pct_chg,
           vol AS volume_lot, amount AS amount_k_cny,         -- 保留源单位：手、千元
           vol*100 AS volume_share, amount*1000 AS amount_cny, -- 手→股、千元→元
           SAFE_CAST(_ingested_at AS TIMESTAMP) AS ingested_at, COALESCE(_source,'tushare') AS source_system
    FROM ashare_ods.ods_tushare_daily
    WHERE partition_date BETWEEN FORMAT_DATE('%Y%m%d',@start) AND FORMAT_DATE('%Y%m%d',@end)
  ),
  adj  AS ( SELECT ts_code AS sec_code, PARSE_DATE('%Y%m%d',trade_date) trade_date, adj_factor
            FROM ashare_ods.ods_tushare_adj_factor WHERE partition_date BETWEEN FORMAT_DATE('%Y%m%d',@start) AND FORMAT_DATE('%Y%m%d',@end) ),
  lim  AS ( SELECT ts_code AS sec_code, PARSE_DATE('%Y%m%d',trade_date) trade_date, up_limit, down_limit
            FROM ashare_ods.ods_tushare_stk_limit WHERE partition_date BETWEEN FORMAT_DATE('%Y%m%d',@start) AND FORMAT_DATE('%Y%m%d',@end) ),
  susp AS ( SELECT DISTINCT ts_code AS sec_code, PARSE_DATE('%Y%m%d',trade_date) trade_date
            FROM ashare_ods.ods_tushare_suspend_d WHERE partition_date BETWEEN FORMAT_DATE('%Y%m%d',@start) AND FORMAT_DATE('%Y%m%d',@end) )
  SELECT
    u.sec_code, u.trade_date,                       -- 骨架主键：停牌日也有行（d.* 为 NULL）
    d.open, d.high, d.low, d.close, d.pre_close, d.pct_chg,
    d.volume_lot, d.amount_k_cny, d.volume_share, d.amount_cny, adj.adj_factor,
    d.open*adj.adj_factor AS open_hfq, d.high*adj.adj_factor AS high_hfq,
    d.low*adj.adj_factor  AS low_hfq,  d.close*adj.adj_factor AS close_hfq,
    -- 复权日收益：分母取最近一个「有价交易日」的后复权收盘，跨停牌空行
    SAFE_DIVIDE(d.close*adj.adj_factor,
      LAST_VALUE(d.close*adj.adj_factor IGNORE NULLS) OVER (
        PARTITION BY u.sec_code ORDER BY u.trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)) - 1 AS ret_1d,
    lim.up_limit, lim.down_limit,
    d.close >= lim.up_limit   AS is_limit_up,
    d.close <= lim.down_limit AS is_limit_down,
    (d.high = d.low AND d.close >= lim.up_limit)   AS is_one_word_limit_up,
    (d.high = d.low AND d.close <= lim.down_limit) AS is_one_word_limit_down,
    (d.sec_code IS NULL OR susp.sec_code IS NOT NULL OR COALESCE(d.volume_lot,0)=0) AS is_suspended,
    u.list_date, u.delist_date, u.board_type,
    DATE_DIFF(u.trade_date, u.list_date, DAY) < 60 AS is_newly_listed,
    -- 开盘是否封板（基于 open 价，比全天一字板更贴近 t+1 开盘可成交性）
    (d.open >= lim.up_limit)   AS is_open_limit_up,
    (d.open <= lim.down_limit) AS is_open_limit_down,
    -- t+1 开盘可买/卖近似 = 非停牌 且 开盘未封对应方向（仍为 EOD 近似，盘中开板需分钟数据）
    (d.sec_code IS NOT NULL AND COALESCE(d.volume_lot,0)>0 AND NOT (d.open>=lim.up_limit))   AS can_buy_open,
    (d.sec_code IS NOT NULL AND COALESCE(d.volume_lot,0)>0 AND NOT (d.open<=lim.down_limit)) AS can_sell_open,
    (d.sec_code IS NOT NULL AND COALESCE(d.volume_lot,0)>0
      AND NOT (d.high=d.low AND (d.close>=lim.up_limit OR d.close<=lim.down_limit))) AS is_tradable,
    COALESCE(d.source_system,'tushare') AS source_system, d.ingested_at
  FROM univ u
  LEFT JOIN d    USING (sec_code, trade_date)   -- 停牌日 d 无行 → 价格 NULL、is_suspended=true
  LEFT JOIN adj  USING (sec_code, trade_date)
  LEFT JOIN lim  USING (sec_code, trade_date)
  LEFT JOIN susp USING (sec_code, trade_date);
  ```
  > 增量运行时用 `MERGE` 按 `(sec_code, trade_date)` upsert；`ret_1d` 跨停牌取最近有价日（`LAST_VALUE … IGNORE NULLS`），增量批次边界须按最大 lookback 多读早期 buffer（§4.6）重算首段。`@start/@end` 为 DATE，ODS 谓词用 `FORMAT_DATE` 转 `YYYYMMDD`。

- **字段注释（建表后补）**：原样字段继承 ODS（见 §3.4），派生/换算字段手写，例如：
  ```sql
  ALTER TABLE ashare_dwd.dwd_stock_eod_price ALTER COLUMN sec_code    SET OPTIONS(description="证券代码，标准格式 600000.SH（源 ts_code 归一）");
  ALTER TABLE ashare_dwd.dwd_stock_eod_price ALTER COLUMN volume_share SET OPTIONS(description="成交量（股，源 daily.vol 手 ×100）");
  ALTER TABLE ashare_dwd.dwd_stock_eod_price ALTER COLUMN amount_cny   SET OPTIONS(description="成交额（元，源 daily.amount 千元 ×1000）");
  ALTER TABLE ashare_dwd.dwd_stock_eod_price ALTER COLUMN close_hfq   SET OPTIONS(description="后复权收盘价 = close × adj_factor");
  ALTER TABLE ashare_dwd.dwd_stock_eod_price ALTER COLUMN ret_1d      SET OPTIONS(description="复权日收益率 = close_hfq / 前一交易日 close_hfq − 1");
  ALTER TABLE ashare_dwd.dwd_stock_eod_price ALTER COLUMN is_tradable SET OPTIONS(description="可交易掩码：非停牌 且 非一字板 且 在市");
  ```

### 6.2 `dwd_stock_eod_valuation` —— 估值/换手/市值（P0）
- **源**：`ods_tushare_daily_basic`。
- **粒度**：`(sec_code, trade_date)`。
- **字段**：`turnover_rate, turnover_rate_f, volume_ratio, pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm, total_share, float_share, free_share, total_mv, circ_mv` + 血缘。
- **单位归一**：`total_share/float_share/free_share`（万股 → 股，`×10000`）、`total_mv/circ_mv`（万元 → 元，`×10000`）。
- **说明**：这些是**当日盘后可得，PIT 安全**。`circ_mv`/`total_mv` 是**市值因子/中性化**的关键；`free_share` 用于换手与流动性。可独立成表，按需 join，减少宽表写放大。

### 6.3 资金/交易行为族
| 表 | 源 | 粒度 | 核心特征 |
|---|---|---|---|
| `dwd_stock_moneyflow` | `moneyflow` | (sec_code, trade_date) | 大/中/小/特大单买卖量额、`net_mf_amount` 主力净流入（量→股、额→元） |
| `dwd_stock_north_hold` | `hk_hold` | (sec_code, trade_date) | 北向持股量/占比 `ratio`，及其变化（增减持动量） |
| `dwd_market_north_flow` | `moneyflow_hsgt` | (trade_date) | `north_money`/`south_money` 市场级情绪（ODS 为 STRING，需 `SAFE_CAST`） |
| `dwd_stock_margin` | `margin_detail` | (sec_code, trade_date) | 融资余额 `rzye`、融券、`rzrqye`；杠杆资金动向 |
| `dwd_market_margin` | `margin` | (exchange, trade_date) | 市场两融余额 |
| `dwd_stock_chip` | `cyq_perf` | (sec_code, trade_date) | 筹码成本分位 `cost_5/15/50/85/95pct`、`winner_rate` 获利盘比例（强势特征） |
| `dwd_stock_limit_event` | `limit_list_d` | (sec_code, trade_date) | 连板数 `limit_times`、封单 `fd_amount`、开板次数 `open_times` |
| `dwd_stock_dragon_tiger`(_inst) | `top_list`/`top_inst` | (sec_code, trade_date) | 龙虎榜净买额、机构席位行为（游资/机构因子） |
| `dwd_stock_block_trade` | `block_trade` | (sec_code, trade_date) | 大宗折溢价、成交额（机构调仓信号） |

> 这些表都是 A 类（`partition_date == trade_date`），构建模式同 6.1：按 `partition_date` 增量 + 日期 PARSE + `ts_code AS sec_code` 出口归一 + 单位归一（查 §3.3-G）+ 血缘字段 + `dim_stock` 校验 universe。

### 6.4 指数与行业族
| 表 | 源 | 用途 |
|---|---|---|
| `dwd_index_eod` | `dim_index` + `index_daily`(+`index_dailybasic`) | 基准指数日线与估值：从 `dim_index` 读取 canonical/source 映射与可用端点；`sec_code` 输出 canonical 指数代码（如沪深300 `000300.SH`），`source_sec_code` 保留 ODS 实际代码（如 `399300.SZ`）。用于超额收益标签、市场状态、beta。 |
| `dwd_sw_industry_eod` | `sw_daily` | 申万行业日线 + 行业 PE/PB/市值；行业动量与中性化。 |
| `dwd_ci_industry_eod` | `ci_daily` | 中信行业日线（备选行业体系）。 |
| `dwd_market_overview` | `daily_info`+`sz_daily_info` | 沪/深市场总市值/成交/平均 PE（市场宽度/情绪）。 |

### 6.5 财务族（P0，强 PIT，B 类）
四张表统一处理范式：**落版本事实表（保留所有公告版本）+ 计算可见时间 `ann_date_eff` / `visible_trade_date`**；去重交给消费侧 as-of（§4.4 / §7.3）。

| 表 | 源 | 说明 |
|---|---|---|
| `dwd_fin_income` | `income` | 利润表。建议保留累计值并派生**单季值**（`q_*`）。 |
| `dwd_fin_balancesheet` | `balancesheet` | 资产负债表（时点值）。 |
| `dwd_fin_cashflow` | `cashflow` | 现金流量表。 |
| `dwd_fin_indicator` | `fina_indicator` | **已算好的财务比率**（ROE/毛利率/周转/YoY/QoQ/单季 `q_*`…），ML 因子的"性价比之王"，优先接入。 |

- **统一构建范式**（以 `fina_indicator` 为例）：
  ```sql
  -- 版本事实表：保留每个公告版本（严格 PIT 主表）。fina_indicator 无 f_ann_date，可见日用 ann_date。
  CREATE OR REPLACE TABLE ashare_dwd.dwd_fin_indicator
  PARTITION BY DATE_TRUNC(ann_date_eff, MONTH) CLUSTER BY sec_code AS
  WITH base AS (
    SELECT
      ts_code AS sec_code,
      PARSE_DATE('%Y%m%d', end_date) AS report_period,
      PARSE_DATE('%Y%m%d', ann_date) AS ann_date_eff,     -- 本表无 f_ann_date，用 ann_date
      update_flag,
      -- 显式选用建模所需指标列（示例，按需扩展）；不要裸 SELECT *，避免带入 _source/_run_id/partition_date 等 ODS 内部字段
      eps, roe, roe_dt, grossprofit_margin, netprofit_margin, debt_to_assets,
      netprofit_yoy, or_yoy, q_roe, ocf_to_or,
      COALESCE(_source,'tushare')          AS source_system,
      SAFE_CAST(_ingested_at AS TIMESTAMP) AS ingested_at
    FROM ashare_ods.ods_tushare_fina_indicator
    WHERE partition_date >= @start_period   -- 财务/事件前移参数：首期 '20170101'，见 §4.6
      AND ann_date IS NOT NULL              -- 无公告日不可做 PIT
  )
  SELECT
    b.*,
    -- 可见交易日：公告日为非交易日/盘后则右移到下一开市日（§4.3）
    COALESCE(
      (SELECT MIN(c.cal_date) FROM ashare_dim.dim_trade_calendar c
       WHERE c.exchange='SSE' AND c.is_open=1 AND c.cal_date >= b.ann_date_eff),
      b.ann_date_eff) AS visible_trade_date
  FROM base b;
  -- 不在此去重：保留所有 (sec_code, report_period, ann_date_eff, update_flag) 版本
  ```
  > **本表是版本事实表**（保留所有公告版本，§4.4①），消费侧 as-of 去重见 §7.3；另建 `dwd_fin_indicator_latest`（每期最新版）供非回测便捷查询。三大报表 `income/balancesheet/cashflow` 同范式，但可见日用 `COALESCE(f_ann_date, ann_date)`，并额外按 `report_type`（通常 `'1'` 合并报表）过滤。**关键产出 `ann_date_eff` / `visible_trade_date`** 是下游 as-of 的连接键。

- **派生单季值**：利润/现金流是累计数，单季 = 本期累计 − 上期累计（Q1 单季=Q1 累计）：
  ```sql
  q_value = cum_value - LAG(cum_value) OVER (PARTITION BY sec_code, fiscal_year ORDER BY report_period)
  ```

### 6.6 事件族（P1/P2，B 类，as-of 使用）
| 表 | 源 | 可见时间 | 典型特征 |
|---|---|---|---|
| `dwd_event_forecast` | `forecast` | `announce_date` | 业绩预告类型/幅度 `p_change_min/max`、预告净利（**早于正式财报，强信号**） |
| `dwd_event_express` | `express` | `announce_date` | 业绩快报 `revenue/n_income/diluted_roe`、`yoy_net_profit` |
| `dwd_event_dividend` | `dividend` | `announce_date`/`ex_date` | 分红送转；与 `adj_factor` 交叉校验复权正确性 |
| `dwd_event_holder_number` | `stk_holdernumber` | `announce_date` | 股东户数变化（户数下降常预示筹码集中） |
| `dwd_event_holder_trade` | `stk_holdertrade` | `announce_date` | 重要股东增减持方向 `in_de`、规模 |
| `dwd_event_pledge_stat` | `pledge_stat` | `report_period`/`ann` | 质押比例 `pledge_ratio`（风险因子） |
| `dwd_event_repurchase` | `repurchase` | `announce_date` | 回购进度/金额（正向信号） |
| `dwd_analyst_report` | `report_rc` | `report_date` | 卖方评级 `rating`、目标价、预测 EPS/净利（一致预期因子） |
| `dwd_fin_audit` | `fina_audit` | `announce_date` | 审计意见（非标意见=风险） |
| `dwd_stock_st_event` | `stock_st`+`st` | `trade_date`/`imp_date` | ST 戴帽/摘帽时间线 |
| `dwd_disclosure_plan` | `disclosure_date` | `pre_date`/`actual_date` | 预约/实际披露日，辅助 PIT 与"财报临近"主题 |

> 事件类多为稀疏信号，进 `dws` 时常做成"距上次事件天数""窗口内是否发生""窗口内累计幅度"等衍生，并以可见时间做 as-of，禁止穿越。

---

## 7. 衔接 DWS：特征宽表与标签（防未来函数的落点）

> 用户本次聚焦 DWD/DIM，但 DWD 的正确性最终由"能否拼出无泄露的宽表"检验，故给出衔接设计与关键 SQL。

### 7.1 骨架：universe × 交易日
```sql
-- 每个交易日的可交易截面（含退市股的在市区间）
SELECT p.trade_date, p.sec_code
FROM ashare_dwd.dwd_stock_eod_price p
WHERE p.trade_date BETWEEN @bt_start AND @bt_end
  AND p.is_tradable                       -- 可建仓样本
  -- 按策略再叠加：NOT is_st / NOT is_newly_listed / circ_mv 下限 等
```

### 7.2 行情/估值/资金特征拼接
以 `(sec_code, trade_date)` 左连 `dwd_stock_eod_valuation`、`dwd_stock_moneyflow`、`dwd_stock_chip`、`dwd_stock_north_hold` 等（全部 PIT 安全，直接等值 join）。

### 7.3 财务 as-of join（PIT 核心）
**回测特征的 as-of 必须打在财务①版本事实表 `dwd_fin_indicator`（§6.5，含历史公告版本）上**，用 `visible_trade_date`（§4.3，已把盘后/非交易日公告右移到可建仓日）做截点；**不要用最新快照表 `_latest`**（会泄漏后期修正）。
```sql
-- 给每个 (sec_code, trade_date) 拼接"当时已可见的最新一期"财务指标
SELECT base.sec_code, base.trade_date,
       fi.* EXCEPT(sec_code, visible_trade_date, ann_date_eff, report_period)
FROM base
LEFT JOIN ashare_dwd.dwd_fin_indicator fi                 -- 版本事实表
  ON fi.sec_code = base.sec_code
  AND fi.visible_trade_date <= base.trade_date            -- 只用当时已可见的版本
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY base.sec_code, base.trade_date
  ORDER BY fi.report_period DESC, fi.ann_date_eff DESC     -- 取最新一期、同期取当时最新版本
) = 1
```
> 逻辑示意；生产中**物化为 `dws` 并增量**，或用"财务区间表 + 交易日区间 join"避免大笛卡尔。对 `(sec_code, visible_trade_date)` 建聚类、加窗口剪枝。

### 7.4 标签（未来收益，时间错位）
**用市场交易日序列（`dim_trade_calendar.trade_date_seq`）定位 `t±k`，不要用个股行情序列**——个股 `ROW_NUMBER` 会跳过停牌日，使 `t+1` 变成"下一次有行情的交易日"、高估可成交性。
```sql
-- t 日因子，t+1 开盘建仓、t+k 收盘平仓的复权收益
WITH cal AS (                       -- 市场交易日 → 连续序号
  SELECT cal_date AS trade_date, trade_date_seq AS seq
  FROM ashare_dim.dim_trade_calendar
  WHERE exchange='SSE' AND is_open=1
),
px AS (                             -- 价格挂到市场交易日序号（停牌日价格为 NULL）
  SELECT p.sec_code, c.seq, p.open_hfq, p.close_hfq, p.can_buy_open, p.is_suspended
  FROM ashare_dwd.dwd_stock_eod_price p
  JOIN cal c USING (trade_date)
)
SELECT a.sec_code, a.seq AS t_seq,
       SAFE_DIVIDE(c.close_hfq, b.open_hfq) - 1            AS fwd_ret_5d,      -- t+1 开盘买, t+5 收盘卖
       b.can_buy_open                                      AS entry_reachable, -- t+1 能否开盘买入
       (c.close_hfq IS NOT NULL AND NOT c.is_suspended)    AS exit_reachable,
       (b.can_buy_open AND b.open_hfq IS NOT NULL AND c.close_hfq IS NOT NULL) AS label_valid
FROM px a
JOIN px b ON b.sec_code=a.sec_code AND b.seq=a.seq+1               -- t+1（市场交易日）
JOIN px c ON c.sec_code=a.sec_code AND c.seq=a.seq+5              -- t+5
```
> 关键：**入场价用 `t+1`**，`t±k` 走**市场交易日序列**；多周期标签（`fwd_ret_1d/5d/10d/20d`）并存；`label_valid` 用于训练样本有效性，检查入场可交易和标签价格可用；`exit_reachable` 单独标记退出侧可卖性，回测撮合层据此顺延或持仓延续。

### 7.5 上线前未来函数 Checklist
- [ ] 财务/事件特征是否都用 `ann_date_eff <= trade_date`？
- [ ] 是否误用前复权价（`_qfq`）做特征？（应用后复权 `_hfq`）
- [ ] 标签入场价是否 ≥ `t+1`？是否用了 `t` 日 `close` 之后才知道的量？
- [ ] 横截面标准化/分位是否只用**当日截面内**信息（不跨日泄露）？
- [ ] universe 是否含退市股历史、剔除上市未满 N 日、停牌/一字板掩码？
- [ ] 缺失值填充是否只用历史方向（ffill），不引入未来？

---

## 8. 工程实现建议

1. **物化与分区**
   - DWD 行情：`PARTITION BY DATE_TRUNC(trade_date, MONTH) CLUSTER BY sec_code`（按月，避免 4000 分区上限与小分区碎片；单日截面查询重则可用 `CLUSTER BY sec_code, trade_date`）。
   - DWD 财务：`PARTITION BY ann_month`（按可见月）或报告期，`CLUSTER BY sec_code`，匹配 as-of 查询模式。
   - DIM 小表无需分区，`CLUSTER BY sec_code` 即可。
2. **增量调度（建议 dbt 或 Airflow + SQL）**
   - 行情类：每日盘后跑 `partition_date = @today`，`MERGE` 进 DWD；`ret_1d`/滚动指标在批边界回看 1~N 个交易日重算首行。
   - 财务类：财报季高频跑，按报告期增量 + 全键 `MERGE` 去重（覆盖修正版）。
   - 维度快照类：每日全量重建 `dim_*`（数据量小，成本可忽略）；`namechange` 增量追加 SCD2 区间。
3. **成本控制**
   - ODS 是外部表，**务必窄分区裁剪**（`partition_date` 常量谓词）；避免 `SELECT *` 全列读外部 Parquet。
   - 长历史回填分批（按年/季）跑，避免单次扫描 35 年全量。
   - DWD 物化后，下游一律查 DWD，不再直接打 ODS。
4. **数据质量校验（建议每日跑断言）**
   - 行情：每日 `COUNT(DISTINCT sec_code)` 在合理区间（~5500）；`high>=low`、`high>=close>=low`、`volume>=0`；`adj_factor` 单调非降（除特殊处理）。
   - 复权交叉校验：`ABS(ret_1d - pct_chg/100) < 阈值`（非除权日应几乎相等）。
   - 财务：`(sec_code, report_period)` 去重后唯一；`ann_date_eff >= report_period`（公告晚于报告期）。
   - 维度：`dim_stock` 主键唯一；退市股必须有合法退市边界（`is_delisted` 时 `delist_date IS NOT NULL` 且 `delist_date > list_date`，并禁止 `delist_date_source='missing_delist_date'`）。
5. **多源治理与可复现**
   - 每行带 `source_system`/`ingested_at`，多源并存时按来源优先级 `MERGE`（如自采 > Tushare），并保留血缘以便排查。
   - DWD/DIM 的构建 SQL 全部入 git（本仓库），参数化 `@start/@end`；保留财务"修正历史"快照以支持严格 PIT 回测复算。

---

## 9. 落地路线图（按优先级）

**P0（一周内，跑通最小可用闭环）**
1. `dim_trade_calendar`、`dim_stock`（含退市）、`dim_stock_name_hist`
2. `dwd_stock_eod_price`（复权+可交易掩码）、`dwd_stock_eod_valuation`
3. `dwd_fin_indicator`（PIT 去重 + `ann_date_eff`）
4. `dwd_index_eod`（基准）
5. 衔接出 `dws_stock_feature_daily` v0 + `dws_stock_label_daily`（`fwd_ret_1d/5d/10d/20d`）→ 跑通一个基线模型

**P1（特征扩展）**
- `dwd_fin_income/balancesheet/cashflow`（单季派生）、`dwd_sw_industry_eod` + 行业中性化
- 资金面：`dwd_stock_moneyflow`、`dwd_stock_north_hold`、`dwd_stock_chip`、`dwd_stock_margin`、`dwd_stock_limit_event`
- 事件：`dwd_event_forecast/express/dividend/holder_*`、`dwd_analyst_report`
- `dim_index_weight`、`dim_sw_industry`、`dim_stock_sw_industry_hist`、`dim_ipo`

**P2/P3（精细化与风控因子）**
- 龙虎榜/大宗、质押/回购/审计、ccass、市场总览
- `dim_stock_ci_industry_hist`、治理类维度（managers/rewards）、北交所映射与长历史拼接

---

## 10. 关键风险与待确认项

1. **行业归属区间口径**：ODS 已有 `index_member_all` / `ci_index_member`，可用 `in_date/out_date` 建时点行业维表；落地前需 QA `out_date` 当天是否按半开区间 `[in_date,out_date)` 处理，以及历史区间是否存在重叠/缺口。
2. **金额单位口径**：已在 §3.3-G 统一为元/股；但 Tushare 各接口原始单位不一，落库换算系数需逐接口核对，接入新源时按源调整。
3. **财务 `report_type` 选择**：默认取合并报表 `'1'`；若策略需要母公司/单季调整口径，需在 `dwd_fin_*` 增加口径维度而非简单过滤。
4. **新增基准指数的端点准入**：`dim_index` 已承载当前可用指数端点、起止日期和 `source_sec_code -> sec_code` 映射。后续新增中证2000/国证2000等基准时，必须先在 ODS 看到实际 `index_daily` 端点并更新 `dim_index`，不得直接写入 DWS/ADS 默认配置或 runner 参数。
5. **`moneyflow_hsgt` 等 STRING 数值字段**：入库统一 `SAFE_CAST`，并对历史口径变化（北向数据 2024 后部分停更）做可用性标记。

---

## 附录 A. ODS 三类分区语义实测结论
- `daily`：`partition_date==trade_date`，每日 ~5506 只、单分区无重复，历史自 `1990-12-19`。
- `adj_factor`：同上，每日 ~5525 只。
- `bak_basic`：`partition_date==trade_date`，每日股票历史列表/备用基础快照；2026-05-29 分区 5527 行，33 个字段均有 BigQuery description。
- `stock_basic`：每日全量快照，`endpoint` 分 `listed`(~5520)/`delisted`(~325)，需 UNION。
- `trade_cal`：每日全量快照，`cal_date`/`pretrade_date` 为 `YYYYMMDD`，含未来交易日预排。
- `income`：`partition_date==end_date`（报告期），同期多 `report_type`，用 `ann_date_eff=COALESCE(f_ann_date, ann_date)` 做 PIT。
- `index_member_all` / `ci_index_member`：最新分区里的全量历史行业归属区间，字段含 `l1/l2/l3`、`ts_code`、`in_date/out_date/is_new`；历史回测用 `in_date/out_date`，不用 `is_new`。
- **可见日字段按表存在性而定**（实测，57 张表）：`income`/`balancesheet`/`cashflow` 有 `f_ann_date`；`fina_indicator` **无 `f_ann_date`**，只能用 `ann_date`。

## 附录 B. 命名规范决策记录（ADR）
| 决策 | 结论 | 理由 |
|---|---|---|
| 证券主键字段名 | `sec_code` | 数据源中性（不绑定 Tushare 的 `ts_code`），语义准确，`_code` 贴合自然键 |
| 证券代码值格式 | `600000.SH`（`.SH/.SZ/.BJ`） | 沿用最通用后缀；其它源在接入层转换 |
| 可见时间字段名 | `ann_date_eff` | `eff`=effective，团队约定保留 |
| 量纲 | 统一元/股 | 同量纲、价×量=额自洽，建模最不易踩单位坑 |
| 血缘字段 | `source_system` + `ingested_at` | 面向多数据源治理，标识来源与入库时间 |
| 交易日/日历日 | `trade_date` / `cal_date` | 事实表轴与日历维度严格区分 |

## 附录 C. Review 整改记录（2026-05-31）

针对 `docs/reviews/数据仓库建模方案-DWD-DIM-review.md`：**9 项认可并整改、2 项认可问题但调整执行**（调整理由见 `docs/reviews/数据仓库建模方案-DWD-DIM-review-response.md`）。

| 编号 | 问题 | 处理 | 落点 |
|---|---|---|---|
| P0-1 | `fina_indicator` 无 `f_ann_date` | 采纳：可见日**按表定义** + 表级规则表 | §0 / §3.3-B / §4.3 / §6.5 |
| P0-2 | 只留最新修正不满足严格 PIT | 采纳：**版本事实表** + 最新快照分离 | §4.4 / §6.5 / §7.3 |
| P0-3 | `daily` 起表漏停牌日 | 采纳：**交易日历×在市骨架** + 标签用市场交易日序列 | §4.5 / §6.1 / §7.4 |
| P0-4 | `delist_date` Parquet 类型不一致 | 2026-06-01 上游已修复为 `STRING`；`dim_stock` 改为优先直读 ODS 退市日，保留 daily 兜底和 QA 门禁 | §5.2 + response |
| P1-1 | 事件表分区语义被一概而论 | 采纳：**ODS 表级元数据矩阵** | §2.4 / §4.3 |
| P1-2 | 缺 lookback buffer | 采纳：**写入 vs 读取范围分离** | §4.6 |
| P1-3 | 可交易性需方向化 | 采纳开盘侧 + reachable；**调整：不加收盘四象限** | §4.5 / §6.1 / §7.4 + response |
| P1-4 | 可见时间未定信号截点 | 采纳：基准假设 + `visible_trade_date` | §4.3 / §6.5 / §7.3 |
| P2-1 | `trade_date_seq` SQL 不符描述 | 采纳：累计 `COUNTIF` | §5.1 |
| P2-2 | DWD 裸 `SELECT *` | 采纳：显式列选择 | §6.5 |
| P2-3 | 表数 56→54 | 采纳：全文订正 | 全文 |
