# A 股日线量化数据仓库建模方案（ODS → DWD / DIM）

> 业务场景：**A 股 · 日线 · 中低频 · 小资金 · 机器学习量化**
> 数据底座：BigQuery 项目 `data-aquarium`，ODS 层数据集 `ashare_ods`（当前来源 Tushare，未来多源；全部为 Hive 分区外部表）
> 文档目标：基于现有 ODS 表，设计可落地的 **DWD（明细层）** 与 **DIM（维度层）**，并给出横切的工程原则（命名规范、PIT 防未来函数、复权、去重、可交易性、增量调度等）。
> 文档维护：Claude Opus 4.8（最近更新 2026-05-31）

---

## 0. TL;DR（一页纸结论）

1. **ODS 现状**：`ashare_ods` 下共 56 张外部表，全部以 `partition_date`（`STRING`，`YYYYMMDD`）+ `endpoint` 作为 Hive 分区键。**任何查询都必须带 `partition_date`/`endpoint` 过滤**，否则 BigQuery 直接报错（强制分区裁剪）。
2. **三类分区语义**（建模的地基，必须先理解）：
   - **A. 行情增量表**：`partition_date == trade_date`，单日一个分区、无重复，历史可回溯到 **1990-12-19**。例：`daily`、`adj_factor`、`daily_basic`。
   - **B. 财务/公告表**：`partition_date == end_date`（报告期，**不是公告日**），同一 `(ts_code, end_date)` 因 `report_type`/修正存在多条。例：`income`、`balancesheet`、`cashflow`、`fina_indicator`。
   - **C. 维度快照表**：每个 `partition_date` 一份**全量快照**，取最新分区即得当前全量。例：`stock_basic`、`trade_cal`、`index_classify`。注意 `stock_basic` 用 `endpoint` 区分 `listed` / `delisted`，**必须 UNION 才完整（含退市股，避免幸存者偏差）**。
3. **建议分层**：`ashare_ods`（已有） → `ashare_dim`（维度） + `ashare_dwd`（明细） → `ashare_dws`（特征宽表/标签，下游 ML 直接消费）。本文聚焦 DIM 与 DWD，并给出 DWS 衔接。
4. **统一命名规范（详见 §3.3，全文遵循）**：证券主键统一为 **`sec_code`**（值标准格式 `600000.SH`，源字段 `ts_code`/`con_code`/`code` 等在出口归一）；交易日 **`trade_date`**、日历日 `cal_date`；财务可见时间 **`ann_date_eff`**；量纲**统一到元/股**；DWD 事实表统一带血缘字段 **`source_system` + `ingested_at`**。
5. **量化语境下的五条铁律**：
   - **PIT（Point-In-Time）**：财务特征的可见时间一律用 `ann_date_eff`（= `COALESCE(f_ann_date, ann_date)`），严禁用 `end_date`/`partition_date` 当可见时间。
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

> 下表是 56 张 ODS 表 → 目标 DWD/DIM 的完整映射。`类`列对应 §0 的三类分区语义（A 行情增量 / B 财务公告 / C 维度快照）。

### 2.1 行情与交易行为域（A 类为主）

| ODS 表 | 含义 | 类 | 目标表 | 优先级 |
|---|---|---|---|---|
| `ods_tushare_daily` | 未复权日线 OHLCV | A | `dwd_stock_eod_price` | P0 |
| `ods_tushare_adj_factor` | 复权因子 | A | `dwd_stock_eod_price`（合并） | P0 |
| `ods_tushare_daily_basic` | 估值/换手/市值 | A | `dwd_stock_eod_valuation` | P0 |
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
| `ods_tushare_index_daily` | 指数日线 | A | `dwd_index_eod` | P0 |
| `ods_tushare_index_dailybasic` | 指数估值/市值 | A | `dwd_index_eod`（合并） | P1 |
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
| `ods_tushare_index_weight` | 指数成分权重 | A* | `dim_index_weight`（缓变维） | P1 |
| `ods_tushare_margin_secs` | 两融标的 | C | `dim_margin_target`（缓变维） | P2 |
| `ods_tushare_new_share` | 新股发行 | C | `dim_ipo` | P1 |
| `ods_tushare_bse_mapping` | 北交所代码映射 | C | `dim_bse_code_map` | P2 |
| `ods_tushare_stock_hsgt` | 沪深股通成分 | C | `dim_hsgt_member` | P2 |
| `ods_tushare_stock_st` | ST 状态 | A*/B | `dwd_stock_st_event` | P1 |
| `ods_tushare_st` | ST 公告(另一来源) | B | `dwd_stock_st_event`（合并） | P1 |
| `ods_tushare_stk_managers` | 管理层 | C | `dim_stock_manager` | P3 |

> 标 `*` 者粒度介于两类之间：`namechange`/`stock_st` 是**事件流**，落 DWD 后可派生 SCD2 维度；`index_weight` 是按 `trade_date` 的成分快照（缓慢变化维）。

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

> **`sec_code` 值标准化**：当前 Tushare 源即 `.SH/.SZ/.BJ` 后缀，直接采用为 canonical 格式。未来接入其它源（如米筐 `.XSHG/.XSHE`、Wind）时，**在该源的接入层转换成标准后缀**，保证字段名与值都统一。北交所历史代码用 `dim_bse_code_map`（`o_code`→`n_code`）归一。

**(B) 日期 / 时间（日期统一 `DATE`）**

| 标准名 | 含义 | 收敛自 |
|---|---|---|
| `trade_date` | 交易日（事实表时间轴） | `trade_date` |
| `cal_date` | 日历日（仅 `dim_trade_calendar`，含非交易日） | `cal_date` |
| `pre_trade_date` | 上一交易日 | `pretrade_date` |
| `ann_date_eff` | **数据可见日（PIT 连接键）** | `COALESCE(f_ann_date, ann_date)` |
| `announce_date` | 公告日（原始） | `ann_date` |
| `report_period` | 报告期 | `end_date`（财报） |
| `ex_date`/`record_date`/`pay_date` | 除权/登记/派息日 | 同名 |
| `ipo_date` | 上市日（新股表） | `ipo_date` |

**(C) 行情 OHLCV**

| 标准名 | 含义 | 源 | 标准单位 |
|---|---|---|---|
| `open`/`high`/`low`/`close`/`pre_close` | 开/高/低/收/昨收 | 同名 | 元（未复权原始价） |
| `pct_change` | 涨跌幅 | `pct_chg` | %（校验用） |
| `volume` | 成交量 | `vol` | **股** |
| `amount` | 成交额 | `amount` | **元** |

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
| `moneyflow.*_vol` | 手 | 股 | `× 100` |
| `moneyflow.*_amount` / `net_mf_amount` | 万元 | 元 | `× 10000` |
| 财务三表金额字段 | 元（多数） | 元 | `× 1`（逐接口核对） |

> ⚠️ **同名字段不同表单位可能不同**（如 `daily.amount` 是千元、`moneyflow.amount` 是万元）。换算必须按"表 + 字段"查表，不能一刀切。

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
- 证券主键统一 `sec_code`（见 §3.3-A）。源字段 `ts_code`/`con_code`/`code`/`index_code` 在 ODS→DWD/DIM 出口统一 `… AS sec_code`；保留 `sec_symbol` 仅供展示，不作 join 键；并用 `sec_type` 区分品种，使股票/指数/基金/可转债共用一套主键与连接逻辑。
- 所有 `*_date` 落库转 `DATE`。`stock_basic.delist_date` 在 ODS 中是 `INT64`，需 `SAFE.PARSE_DATE('%Y%m%d', CAST(delist_date AS STRING))`。
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
- **行情/估值**（`daily`/`daily_basic`）：当日盘后即可得，`trade_date` 当日可见，PIT 安全。
- **财务**（`income`/`balancesheet`/`cashflow`/`fina_indicator`）：
  - `partition_date == end_date`（报告期），**绝不能当可见时间**。
  - 可见时间 = `ann_date_eff = COALESCE(f_ann_date, ann_date)`（实际公告日优先）。
  - 在任意 `trade_date`，只能使用 `ann_date_eff <= trade_date` 的最新一期 → **as-of join**（见 §7.3）。
- **事件**（分红/预告/快报/增减持/质押/龙虎榜）：可见时间用各自的公告/实施日（`announce_date`/`imp_date`/`ex_date`/`trade_date`），同样 as-of。
- **标签**用未来数据是允许的（那是 `y`），但必须与特征**时间错位**：`t` 日特征 → 标签从 `t+1` 起算（§7.4），杜绝用 `t` 日收盘信息进入入场价。

### 4.4 去重（Deduplication）
- **A 类行情表**：单分区内 `(sec_code, trade_date)` 已唯一（实测 `daily` 每日 5500+ 行、`COUNT(*) == COUNT(DISTINCT ts_code)`）。跨分区无重复，**无需去重**；若发生回填重跑，按 `_ingested_at` 取最新兜底。
- **B 类财务表**：同一 `(sec_code, report_period)` 有多条（不同 `report_type`/修正/`update_flag`）。标准去重：
  ```sql
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY ts_code, end_date
    ORDER BY update_flag DESC, COALESCE(f_ann_date, ann_date) DESC, _ingested_at DESC
  ) = 1
  ```
  并按需先过滤 `report_type`（合并报表通常取 `'1'`）。**保留每期最新修正版**，同时建议另存"修正历史"以支持严格 PIT 回测（即回测某日只看当日已公告的版本）。

### 4.5 Universe 与可交易性
- **幸存者偏差**：`dim_stock` 必须 UNION `stock_basic` 的 `listed` + `delisted` 两个 endpoint，保留退市股的 `list_date`/`delist_date`，回测区间内"在市"才纳入截面。
- **可交易标记**（落在 `dwd_stock_eod_price`，作为样本掩码）：
  - `is_suspended`：当日停牌（`suspend_d` 命中 或 `volume IS NULL/0`）。
  - `is_limit_up` / `is_limit_down`：收盘封板（`close >= up_limit` / `close <= down_limit`）。
  - `is_one_word_board`：一字板（`high==low` 且触及涨跌停）→ 当日**买不进/卖不出**。
  - `is_newly_listed`：`trade_date - list_date < N`（默认 N=60 个自然日，可参数化为交易日），次新股波动剧烈，常单独处理。
  - `is_st`：来自 `dwd_stock_st_event` / `namechange`（名称含 `ST`/`*ST`）→ 涨跌幅 ±5%，风险偏好低时剔除。
- **涨跌停幅度**：直接用 `stk_limit.up_limit`/`down_limit`（Tushare 已按板块算好 ±10%/±5%/±20%/±30%），避免自己按板块硬编码。

### 4.6 分区裁剪与增量（成本/性能）
- ODS 是外部表且**强制分区裁剪**：所有读 ODS 的 SQL 必须含 `WHERE partition_date <谓词>`（常量比较，`partition_date` 为 `YYYYMMDD` 字符串）。
- DWD/DIM 构建走**增量**：行情类按 `partition_date BETWEEN @start AND @end` 处理新增交易日；财务/事件类按 `partition_date`（report period）或 `ann_date` 增量 + MERGE 去重。
- DWD 原生表自身按 `DATE` 分区，下游 `dws` 拼接时同样分区裁剪，控制扫描量。
- **初始回填范围（重要，分层处理）**：首期仅回填 **2019-01-01 起** 的数据以控成本，但**不能一刀切**：
  - **行情/估值/资金类**（`partition_date == trade_date`）：`WHERE partition_date >= '20190101'`。
  - **财务/事件类**（`partition_date == 报告期/公告期`）：**起点前移到 `'20170101'`**——2019 初做 PIT 需取到"当时最新的年报/季报"（2018 报告期、甚至 2017 年报）；若也按 2019 截断，2019 年初截面会缺最近一期财务。
  - **维度/日历**：`dim_stock` 取最新快照（含全部历史股票，按 `list_date/delist_date` 在 universe 逻辑过滤，**不按数据时间截断**）；`dim_trade_calendar` **保留全量**（至少下探到 2018），以提供 `t-1/t-k` 交易日边界。
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
    ROW_NUMBER() OVER (
      PARTITION BY exchange, IF(is_open=1, 0, 1)
      ORDER BY cal_date
    ) AS trade_date_seq
  FROM ashare_ods.ods_tushare_trade_cal, latest
  WHERE partition_date = latest.pd;
  -- 注：CTAS 带显式列定义时，列名/顺序/类型须与 SELECT 输出一致（此处恰好匹配）
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
    SAFE.PARSE_DATE('%Y%m%d', CAST(delist_date AS STRING)) AS delist_date,
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

### 5.3 `dim_stock_name_hist` —— 名称/ST 状态时间线（P0，SCD2）
- **源**：`ods_tushare_namechange`（事件流：`start_date`/`end_date`/`change_reason`）。
- **粒度**：`(sec_code, start_date)`，每段名称一行（SCD2 区间）。
- **用途**：按 `trade_date` 还原**当时的股票名**与 **ST 状态**（名称含 `ST`/`*ST`/`退`）。ST 判定优先用此表，`stock_st`/`st` 作交叉校验。
- **关键字段**：`sec_code, sec_name, start_date(DATE), end_date(DATE, 开区间用 9999-12-31 填充), is_st(派生), is_star_st(派生)`。
- **PIT 用法**：`JOIN ON trade_date BETWEEN start_date AND end_date`。

### 5.4 `dim_sw_industry` + 个股行业归属（P1）
- **源**：`ods_tushare_index_classify`（申万行业树：`index_code, industry_name, parent_code, level, src`）。
- **粒度**：行业节点（`sec_code` 承载行业代码，`sec_type='industry'`），含 L1/L2/L3 层级（`parent_code` 自关联成树）。
- **个股→行业映射的现状与缺口**：
  - 简易口径：直接用 `dim_stock.industry`（Tushare 自带行业字段，较粗，**非时点**）。
  - 标准申万口径：需要"个股-申万行业成分"明细。当前 ODS 的 `index_weight` 是**指数成分权重**，若含申万行业指数成分可反推；否则这是一个**数据缺口**，建议后续补采 Tushare `index_member`/`index_member_all`。文档先用 `dim_stock.industry` 兜底，并在 `dws` 层预留 `sw_l1/sw_l2/sw_l3` 字段。
- **用途**：行业中性化、行业动量、行业暴露约束。

### 5.5 `dim_index_weight` —— 指数成分权重（P1，缓变维）
- **源**：`ods_tushare_index_weight`（`index_code, con_code, trade_date, weight`，A* 类按调仓日快照）。
- **粒度**：`(index_code, sec_code, trade_date)`（`index_code` 为指数、`sec_code` 来自 `con_code`）。
- **用途**：判断个股是否属于沪深300/中证500/中证1000/中证2000 等基准；做指数增强、成分内选股、基准对齐。按 as-of（`trade_date <= 当前`取最近一次成分）使用。

### 5.6 其它维度（P2/P3）
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
| `sec_code, trade_date` | daily | 主键 |
| `open, high, low, close, pre_close` | daily | 元，未复权原始价 |
| `volume` | `daily.vol * 100` | **股** |
| `amount` | `daily.amount * 1000` | **元**（daily 原千元） |
| `pct_change` | daily.pct_chg | %（校验用） |
| `adj_factor` | adj_factor | 累计后复权因子 |
| `open_hfq/high_hfq/low_hfq/close_hfq` | `raw * adj_factor` | 后复权价（指标计算用） |
| `ret_1d` | `close*adjf / LAG(close*adjf) - 1` | 复权日收益率（按 sec_code 排序） |
| `up_limit, down_limit` | stk_limit | 元，当日涨跌停价 |
| `is_limit_up, is_limit_down` | `close>=up_limit` / `close<=down_limit` | 收盘封板 |
| `is_one_word_board` | `high==low AND 触及涨跌停` | 一字板（不可成交） |
| `is_suspended` | suspend_d 命中 或 volume 缺失 | 停牌掩码 |
| `is_tradable` | 非停牌 且 非一字板 且 已上市未退市 | **样本可交易掩码** |
| `is_newly_listed` | `trade_date - list_date < N` | 次新标记 |
| `source_system, ingested_at` | 血缘 | — |

- **构建要点（核心 SQL 骨架）**：
  ```sql
  CREATE OR REPLACE TABLE ashare_dwd.dwd_stock_eod_price
  PARTITION BY DATE_TRUNC(trade_date, MONTH) CLUSTER BY sec_code   -- 按月分区，避开 4000 分区上限
  OPTIONS(description="个股复权日线主表：整合未复权 OHLCV、后复权价(_hfq)、复权收益率、涨跌停/停牌/可交易性标记；粒度 (sec_code, trade_date)，金额单位元、量单位股",
          require_partition_filter = TRUE) AS   -- 强制下游必须带 trade_date 过滤
  WITH d AS (                              -- 读 ODS：保留 ts_code 原名
    SELECT ts_code, PARSE_DATE('%Y%m%d', trade_date) trade_date,
           open, high, low, close, pre_close, pct_chg,
           vol*100      AS volume,         -- 手→股
           amount*1000  AS amount,         -- 千元→元
           SAFE_CAST(_ingested_at AS TIMESTAMP) AS ingested_at,
           COALESCE(_source,'tushare')          AS source_system
    FROM ashare_ods.ods_tushare_daily
    WHERE partition_date BETWEEN @start AND @end          -- 增量裁剪；初始回填 @start='20190101'
  ),
  adj AS (
    SELECT ts_code, PARSE_DATE('%Y%m%d', trade_date) trade_date, adj_factor
    FROM ashare_ods.ods_tushare_adj_factor
    WHERE partition_date BETWEEN @start AND @end
  ),
  lim AS (
    SELECT ts_code, PARSE_DATE('%Y%m%d', trade_date) trade_date, up_limit, down_limit
    FROM ashare_ods.ods_tushare_stk_limit
    WHERE partition_date BETWEEN @start AND @end
  ),
  susp AS (
    SELECT DISTINCT ts_code, PARSE_DATE('%Y%m%d', trade_date) trade_date
    FROM ashare_ods.ods_tushare_suspend_d
    WHERE partition_date BETWEEN @start AND @end
  )
  SELECT
    d.ts_code AS sec_code, d.trade_date,            -- 出口归一为 sec_code
    d.open, d.high, d.low, d.close, d.pre_close, d.pct_chg AS pct_change,
    d.volume, d.amount,
    adj.adj_factor,
    d.open*adj.adj_factor  AS open_hfq,
    d.high*adj.adj_factor  AS high_hfq,
    d.low*adj.adj_factor   AS low_hfq,
    d.close*adj.adj_factor AS close_hfq,
    SAFE_DIVIDE(d.close*adj.adj_factor,
                LAG(d.close*adj.adj_factor) OVER (PARTITION BY d.ts_code ORDER BY d.trade_date)) - 1 AS ret_1d,
    lim.up_limit, lim.down_limit,
    d.close >= lim.up_limit              AS is_limit_up,
    d.close <= lim.down_limit            AS is_limit_down,
    (d.high = d.low) AND (d.close >= lim.up_limit OR d.close <= lim.down_limit) AS is_one_word_board,
    susp.ts_code IS NOT NULL OR d.volume IS NULL OR d.volume = 0 AS is_suspended,
    s.list_date, s.delist_date, s.board_type,
    DATE_DIFF(d.trade_date, s.list_date, DAY) < 60 AS is_newly_listed,
    NOT (susp.ts_code IS NOT NULL OR COALESCE(d.volume,0)=0)
      AND NOT ((d.high=d.low) AND (d.close>=lim.up_limit OR d.close<=lim.down_limit))
      AND d.trade_date >= s.list_date
      AND (s.delist_date IS NULL OR d.trade_date < s.delist_date) AS is_tradable,
    d.source_system, d.ingested_at
  FROM d
  LEFT JOIN adj  USING (ts_code, trade_date)   -- CTE 内仍是 ts_code，join 成立
  LEFT JOIN lim  USING (ts_code, trade_date)
  LEFT JOIN susp USING (ts_code, trade_date)
  LEFT JOIN ashare_dim.dim_stock s ON s.sec_code = d.ts_code;
  ```
  > 增量运行时用 `MERGE` 按 `(sec_code, trade_date)` upsert；`ret_1d` 的 `LAG` 在增量批次边界需回看前一交易日（用 `dim_trade_calendar.pre_trade_date` 取边界前一日重算首行）。

- **字段注释（建表后补）**：原样字段继承 ODS（见 §3.4），派生/换算字段手写，例如：
  ```sql
  ALTER TABLE ashare_dwd.dwd_stock_eod_price ALTER COLUMN sec_code    SET OPTIONS(description="证券代码，标准格式 600000.SH（源 ts_code 归一）");
  ALTER TABLE ashare_dwd.dwd_stock_eod_price ALTER COLUMN volume      SET OPTIONS(description="成交量（股，源 daily.vol 手 ×100）");
  ALTER TABLE ashare_dwd.dwd_stock_eod_price ALTER COLUMN amount      SET OPTIONS(description="成交额（元，源 daily.amount 千元 ×1000）");
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
| `dwd_index_eod` | `index_daily`(+`index_dailybasic`) | 基准指数日线与估值：沪深300 `000300.SH`、中证500 `000905.SH`、中证1000 `000852.SH`、中证2000、国证2000 等（**以 ODS 实际可用 `sec_code` 为准**）。用于超额收益标签、市场状态、beta。 |
| `dwd_sw_industry_eod` | `sw_daily` | 申万行业日线 + 行业 PE/PB/市值；行业动量与中性化。 |
| `dwd_ci_industry_eod` | `ci_daily` | 中信行业日线（备选行业体系）。 |
| `dwd_market_overview` | `daily_info`+`sz_daily_info` | 沪/深市场总市值/成交/平均 PE（市场宽度/情绪）。 |

### 6.5 财务族（P0，强 PIT，B 类）
四张表统一处理范式：**去重取最新修正版 + 计算可见时间 `ann_date_eff`**。

| 表 | 源 | 说明 |
|---|---|---|
| `dwd_fin_income` | `income` | 利润表。建议保留累计值并派生**单季值**（`q_*`）。 |
| `dwd_fin_balancesheet` | `balancesheet` | 资产负债表（时点值）。 |
| `dwd_fin_cashflow` | `cashflow` | 现金流量表。 |
| `dwd_fin_indicator` | `fina_indicator` | **已算好的财务比率**（ROE/毛利率/周转/YoY/QoQ/单季 `q_*`…），ML 因子的"性价比之王"，优先接入。 |

- **统一构建范式**（以 `fina_indicator` 为例）：
  ```sql
  CREATE OR REPLACE TABLE ashare_dwd.dwd_fin_indicator
  PARTITION BY ann_month CLUSTER BY sec_code AS
  SELECT * EXCEPT(rn, ts_code, _ann_eff_str),
         ts_code                                          AS sec_code,
         PARSE_DATE('%Y%m%d', _ann_eff_str)               AS ann_date_eff,
         DATE_TRUNC(PARSE_DATE('%Y%m%d', _ann_eff_str), MONTH) AS ann_month,
         PARSE_DATE('%Y%m%d', end_date)                   AS report_period,
         COALESCE(_source,'tushare')                      AS source_system,
         SAFE_CAST(_ingested_at AS TIMESTAMP)             AS ingested_at
  FROM (
    SELECT *,
      COALESCE(f_ann_date, ann_date) AS _ann_eff_str,
      ROW_NUMBER() OVER (
        PARTITION BY ts_code, end_date
        ORDER BY update_flag DESC, COALESCE(f_ann_date, ann_date) DESC, _ingested_at DESC
      ) AS rn
    FROM ashare_ods.ods_tushare_fina_indicator
    WHERE partition_date >= @start_period          -- 初始 @start_period='20170101'（前移~2年，保证2019初PIT能取到最近年报/季报）
      AND ann_date IS NOT NULL                     -- 必须有公告日才可 PIT
  )
  WHERE rn = 1;
  ```
  > 三大报表 `income/balancesheet/cashflow` 额外按 `report_type` 过滤（通常 `'1'` 合并报表）。**关键产出 `ann_date_eff`** 是下游 as-of join 的连接键。

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
```sql
-- 给每个 (sec_code, trade_date) 拼接"当时已公告的最新一期"财务指标
SELECT base.sec_code, base.trade_date, fi.* EXCEPT(sec_code, ann_date_eff, report_period)
FROM base
LEFT JOIN ashare_dwd.dwd_fin_indicator fi
  ON fi.sec_code = base.sec_code
  AND fi.ann_date_eff <= base.trade_date          -- 只用已公告
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY base.sec_code, base.trade_date
  ORDER BY fi.report_period DESC, fi.ann_date_eff DESC   -- 取最新一期、同期取最新修正
) = 1
```
> 这是逻辑示意；生产中**物化为 `dws` 并增量**，或用"财务区间表 + 交易日区间 join"避免大笛卡尔。可对 `ann_date_eff` 建聚类、加窗口剪枝。

### 7.4 标签（未来收益，时间错位）
```sql
-- 以 t 日因子，标签用 t+1 开盘建仓、t+k 收盘平仓的复权收益，避免用 t 日收盘信息
WITH px AS (
  SELECT sec_code, trade_date, open_hfq, close_hfq,
         ROW_NUMBER() OVER (PARTITION BY sec_code ORDER BY trade_date) AS seq
  FROM ashare_dwd.dwd_stock_eod_price
)
SELECT a.sec_code, a.trade_date,
       SAFE_DIVIDE(c.close_hfq, b.open_hfq) - 1 AS fwd_ret_5d   -- t+1 开盘买, t+5 收盘卖
FROM px a
JOIN px b ON b.sec_code=a.sec_code AND b.seq=a.seq+1                -- t+1
JOIN px c ON c.sec_code=a.sec_code AND c.seq=a.seq+5               -- t+5
```
> 关键：**入场价用 `t+1` 而非 `t`**；多周期标签（`fwd_ret_1d/5d/10d/20d`）并存；可加"未来是否一字涨停无法买入"的可达性掩码，使标签贴近真实可成交收益。

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
   - 复权交叉校验：`ABS(ret_1d - pct_change/100) < 阈值`（非除权日应几乎相等）。
   - 财务：`(sec_code, report_period)` 去重后唯一；`ann_date_eff >= report_period`（公告晚于报告期）。
   - 维度：`dim_stock` 主键唯一；`delist_date IS NULL OR delist_date > list_date`。
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
- `dim_index_weight`、`dim_sw_industry`、`dim_ipo`

**P2/P3（精细化与风控因子）**
- 龙虎榜/大宗、质押/回购/审计、ccass、市场总览
- 治理类维度（managers/rewards）、北交所映射与长历史拼接

---

## 10. 关键风险与待确认项

1. **个股标准申万行业归属缺口**：ODS 暂无 `index_member` 明细，个股→申万 L1/L2/L3 时点映射不完整。短期用 `dim_stock.industry` 兜底，建议补采 Tushare `index_member_all`。
2. **金额单位口径**：已在 §3.3-G 统一为元/股；但 Tushare 各接口原始单位不一，落库换算系数需逐接口核对，接入新源时按源调整。
3. **财务 `report_type` 选择**：默认取合并报表 `'1'`；若策略需要母公司/单季调整口径，需在 `dwd_fin_*` 增加口径维度而非简单过滤。
4. **基准指数代码可用性**：§6.4 列出的中证1000/中证2000/国证2000 等代码需以 `index_daily` 实际存在的 `sec_code` 为准，建仓前用 `SELECT DISTINCT ts_code` 核对。
5. **`moneyflow_hsgt` 等 STRING 数值字段**：入库统一 `SAFE_CAST`，并对历史口径变化（北向数据 2024 后部分停更）做可用性标记。

---

## 附录 A. ODS 三类分区语义实测结论
- `daily`：`partition_date==trade_date`，每日 ~5506 只、单分区无重复，历史自 `1990-12-19`。
- `adj_factor`：同上，每日 ~5525 只。
- `stock_basic`：每日全量快照，`endpoint` 分 `listed`(~5520)/`delisted`(~325)，需 UNION。
- `trade_cal`：每日全量快照，`cal_date`/`pretrade_date` 为 `YYYYMMDD`，含未来交易日预排。
- `income`：`partition_date==end_date`（报告期），同期多 `report_type`，**必须用 `f_ann_date` 做 PIT**。

## 附录 B. 命名规范决策记录（ADR）
| 决策 | 结论 | 理由 |
|---|---|---|
| 证券主键字段名 | `sec_code` | 数据源中性（不绑定 Tushare 的 `ts_code`），语义准确，`_code` 贴合自然键 |
| 证券代码值格式 | `600000.SH`（`.SH/.SZ/.BJ`） | 沿用最通用后缀；其它源在接入层转换 |
| 可见时间字段名 | `ann_date_eff` | `eff`=effective，团队约定保留 |
| 量纲 | 统一元/股 | 同量纲、价×量=额自洽，建模最不易踩单位坑 |
| 血缘字段 | `source_system` + `ingested_at` | 面向多数据源治理，标识来源与入库时间 |
| 交易日/日历日 | `trade_date` / `cal_date` | 事实表轴与日历维度严格区分 |
