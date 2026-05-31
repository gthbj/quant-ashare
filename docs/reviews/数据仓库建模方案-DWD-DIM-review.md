# 《数据仓库建模方案-DWD-DIM》Review

Review 日期：2026-05-31  
Review 范围：`docs/数据仓库建模方案-DWD-DIM.md`，并核对 BigQuery `data-aquarium.ashare_ods` 当前 ODS 元数据与若干关键分区样本。  
结论：方案方向正确，尤其是 PIT、复权、幸存者偏差、按月分区、2019+ 回填但财务前移这些原则是对的。但当前文档里有几处会导致 SQL 不能运行、PIT 回测不严格，或停牌/退市样本处理失真。建议先修正 P0/P1 后再进入 DDL/调度实现。

## 核对到的 ODS 事实

- 当前 `ashare_ods` 是 54 张表，不是文档 TL;DR 写的 56 张；文档正文实际列出的唯一 ODS 表名也是 54 张。
- 54 张表均为 BigQuery 外部表，Hive 分区列为 `endpoint STRING, partition_date STRING`，并开启 `require_hive_partition_filter=true`。
- 行情核心表最新分区：`daily`/`adj_factor`/`daily_basic` 为 `20260529`；`stock_basic` 最新分区为 `20260528`；`trade_cal` 最新分区为 `20260531`。
- `20260529` 样本：`daily` 5506 只、`daily_basic` 5506 只、`adj_factor` 5525 只、`stk_limit` 7628 只；`stock_basic_listed` 最新快照 5524 只、`stock_basic_delisted` 326 只。
- `ods_tushare_fina_indicator` 当前 schema 没有 `f_ann_date`，只有 `ann_date` 与 `end_date`。
- `stock_basic_delisted` 分区读取 `delist_date` 时报 Parquet 类型不一致：外部表 schema 是 `INT64`，但 delisted parquet 文件里该列是 `BYTE_ARRAY`。这会影响 `dim_stock` 对退市日期的构建。

## P0 Findings

### P0-1 `dwd_fin_indicator` 示例 SQL 直接不可运行

原文位置：第 17、19、165、266、546-565 行。  
问题：文档把财务可见日统一写成 `COALESCE(f_ann_date, ann_date)`，并在 `dwd_fin_indicator` 示例中直接引用 `f_ann_date`。但实际 `ods_tushare_fina_indicator` 没有该字段，查询会报：

```text
Unrecognized name: f_ann_date; Did you mean ann_date?
```

影响：P0 路线图里把 `dwd_fin_indicator` 作为首批 ML 因子表；该 SQL 会在第一步失败。

建议：
- 按表定义 `ann_date_eff`，不要用一个公式覆盖所有财务表。
- `income`/`balancesheet`/`cashflow`：`COALESCE(f_ann_date, ann_date)`。
- `fina_indicator`：当前只能用 `ann_date`，除非后续 ODS 补采或补齐 `f_ann_date`。
- 在字段字典里加一张“表级可见日规则表”，明确每张表的可见日字段和缺失处理。

### P0-2 财务去重为“当前最新修正版”不满足严格 PIT

原文位置：第 271-280、544-568、673 行。  
问题：文档建议 `PARTITION BY ts_code, end_date ORDER BY update_flag DESC, ann_date_eff DESC, _ingested_at DESC` 后只保留 1 行。这会把同一期财报的多个公告版本压成“当前最新版本”。实际样本里存在同一报告期在多年后修正的记录，例如 `income` 的 `20231231` 报告期里，有个股同一期出现 2024、2025、2026 的不同公告/修正日期。

影响：
- 回测 2019 或 2024 某日时，如果只保留 2026 修正版，as-of join 会找不到当时已公布的旧版本，导致历史特征缺失或口径偏移。
- 如果后续为了补缺失又按 `report_period` 回填，容易引入未来修正数据。

建议：
- DWD 财务层保留版本事实表，主键至少包含 `(sec_code, report_period, ann_date_eff, update_flag, ingested_at/run_id)`。
- 可以另建当前快照表，例如 `dwd_fin_indicator_latest`，但不要让它成为回测特征唯一来源。
- DWS as-of join 时按 `ann_date_eff <= feature_cutoff_date` 过滤后，再取 `report_period DESC, ann_date_eff DESC, ingested_at DESC`。
- 若首期想简化，也应在文档中明确“当前最新口径不支持严格历史 PIT”，避免误用于回测。

### P0-3 以 `daily` 为价格主表基表会漏掉停牌日

原文位置：第 284-290、438-490、598-605、626-640 行。  
问题：`dwd_stock_eod_price` 示例从 `daily` 起表，再 left join `suspend_d`。但 Tushare `daily` 在停牌日通常没有该股票行。实测 `20260529`：最新上市股票 5524 只，`daily` 只有 5506 只；`suspend_d` 有 23 只，其中 19 只上市股票当天缺失于 `daily`，且都在 `suspend_d` 中。

影响：
- `is_suspended` 只能标记“daily 中仍有行”的情况，真正缺行情的停牌日会从 DWD 消失。
- `dws` 用 `dwd_stock_eod_price` 做样本骨架时，停牌日不是 `is_tradable=false`，而是整行不存在。
- 标签 SQL 用 `ROW_NUMBER() OVER (PARTITION BY sec_code ORDER BY trade_date)` 会跳过停牌市场日，`t+1` 变成“下一次有行情的交易日”，高估可成交性。

建议：
- 价格 DWD 至少对 `daily` 与 `suspend_d` 做 full outer/union skeleton，保留停牌日行。
- 更稳妥的骨架是 `dim_trade_calendar` 的开市日 × 当日在市股票，再 left join `daily`/`adj_factor`/`stk_limit`/`suspend_d`。
- 对停牌日保留 `close/open` 缺失、`is_suspended=true`、`is_tradable=false`，并在标签层用市场交易日序列和 `can_buy/can_sell` 掩码，不用“个股有行情行序列”替代市场时间。

### P0-4 `dim_stock` 读取退市日期会被 ODS 类型不一致卡住

原文位置：第 246、339-374 行。  
问题：`stock_basic.delist_date` 在 INFORMATION_SCHEMA 中是 `INT64`，文档也按 `CAST(delist_date AS STRING)` 解析。但读取 `endpoint='stock_basic_delisted'` 的 `delist_date` 时，BigQuery 报 Parquet 列类型不匹配：外部表期望 `INT64`，文件实际是 `BYTE_ARRAY`。

影响：
- 文档中的 `dim_stock` 构建 SQL 在读取退市 endpoint 并使用 `delist_date` 聚合/全量构建时会失败。
- 即使临时不读 `delist_date`，回测 universe 也无法正确判断退市边界，幸存者偏差治理落不了地。

建议：
- 优先修 ODS：把 `stock_basic` 外部表的 `delist_date` 统一为 `STRING`，或拆成 listed/delisted 两张 schema 一致的外部表后再 union。
- 在 DWD/DIM 建模前加一条数据质量门禁：`stock_basic_listed + stock_basic_delisted` 必须能读取 `list_date/delist_date` 并解析为 DATE。
- 当前最新 `stock_basic` 还缺少 2019+ `daily` 中出现过的 3 个代码（样本：`000043.SZ`, `300114.SZ`, `920218.BJ`），建议 `dim_stock` 增加从价格表/代码映射补主数据的兜底校验。

## P1 Findings

### P1-1 “三类分区语义”对事件表过粗

原文位置：第 11-15、72-95、292-299 行。  
问题：文档把财务/公告类大体归为 `partition_date == end_date`，但实际事件表分区语义不一：

| 表 | 实测分区语义 |
|---|---|
| `forecast`, `express`, `fina_audit`, `top10_holders`, `top10_floatholders`, `pledge_stat`, `disclosure_date` | 基本按 `end_date` |
| `dividend` | `partition_date == ex_date` |
| `report_rc` | `partition_date == report_date` |
| `stock_st` | `partition_date == trade_date` |
| `index_weight` | 多数为自然月末分区，`trade_date` 是月末最后交易日，二者不总相等 |
| `stk_holdertrade`, `stk_holdernumber`, `pledge_detail` | 与 `ann_date` 不稳定相等，需要单独定规则 |

影响：增量回填如果只按“A=trade_date / B=end_date / C=snapshot”处理，会漏采、误判可见时间，或把分区日期误当事件日期。

建议：
- 在方案中加“ODS 表级元数据矩阵”：`partition_key_semantic`、`business_date`、`visible_date`、`event_date`、`recommended_increment_key`。
- 事件表 DWD 不要继承 B 类统一模板；每张表单独定义可见时间和分区回填窗口。

### P1-2 2019+ 首期写入仍需要更明确的读取回看窗口

原文位置：第 296-299、492、626-640 行。  
问题：文档已把财务回填前移到 2017，这是对的；但行情/技术特征同样有边界问题。若 DWD 只读写 `partition_date >= '20190101'`，`2019-01-02` 的 `ret_1d`、以及 5/20/60/120 日滚动特征都会缺少 2018 年尾部历史。

影响：2019 年初样本特征不稳定；如果后续直接丢弃 warm-up 期，会减少样本且容易和标签窗口混在一起。

建议：
- 明确“写入范围”和“读取范围”分离：DWD/DWS 对外只写 `trade_date >= 2019-01-01`，但计算时按指标最大 lookback 读取 2018 或更早 buffer。
- `ret_1d` 至少读取 2018 年最后一个交易日；滚动特征按最大窗口读取足够交易日。

### P1-3 可交易性需要拆成方向与时点，不宜只有 `is_tradable`

原文位置：第 282-290、475-484、626-640 行。  
问题：小资金低频选股最常用的是“t 日收盘后算因子，t+1 开盘或 VWAP 建仓”。文档的 `is_tradable` 把停牌、一字板、在市状态混成一个布尔值，但没有区分买入/卖出方向，也没有区分开盘、盘中、收盘。

影响：
- 一字涨停主要影响买入，一字跌停主要影响卖出；同一个 `is_tradable=false` 会让训练、回测和实盘执行逻辑难以对齐。
- 标签中 `t+1 open` 建仓，需要的是 `can_buy_next_open`，不是 t 日的收盘封板状态。

建议：
- 在价格 DWD 增加方向性字段：`can_buy_open`, `can_sell_open`, `can_buy_close`, `can_sell_close` 或至少 `is_open_limit_up/down`, `is_one_word_limit_up/down`。
- DWS 标签表增加 `entry_reachable`, `exit_reachable`, `label_valid`。

### P1-4 财务/公告可见时间需要定义信号截点

原文位置：第 262-269、611-624 行。  
问题：`ann_date_eff <= trade_date` 是否可用，取决于策略信号是在当日开盘前、收盘后，还是盘中生成。A 股很多公告在盘后披露；如果特征时间是“t 日收盘后，为 t+1 开盘交易”，使用 t 日公告通常可以接受；如果是“t 日开盘前交易”，则应映射到下一个可交易日。

影响：同一个 `ann_date_eff <= trade_date` 在不同执行假设下可能成为未来函数。

建议：
- 文档中明确基准假设：EOD after close 生成 t 日特征，t+1 开盘建仓。
- 建议派生 `visible_trade_date`：按公告日期、交易日历、公告时点可得性，把非交易日/盘后公告映射到实际可用于建仓的交易日。

## P2 Findings

### P2-1 `dim_trade_calendar.trade_date_seq` 示例不符合描述

原文位置：第 309-335 行。  
问题：文档说 `trade_date_seq` “仅 `is_open=1` 递增”，但 SQL 用：

```sql
ROW_NUMBER() OVER (
  PARTITION BY exchange, IF(is_open=1, 0, 1)
  ORDER BY cal_date
)
```

这会让休市日也得到一套独立递增序号，而不是空值或上一个开市序号。

建议：
- 若只给开市日编号：`IF(is_open=1, COUNTIF(is_open=1) OVER (...), NULL)`。
- 若要每个自然日都带“截至当日最近交易日序号”，则用累计 `COUNTIF(is_open=1)`，并在字段说明里明确。

### P2-2 DWD 示例保留了过多 ODS 内部字段

原文位置：第 140-143、548-554 行。  
问题：字段字典说 ODS 原字段只在出口统一 rename/单位换算，下游用标准名；但 `dwd_fin_indicator` 示例 `SELECT * EXCEPT(rn, ts_code, _ann_eff_str)` 会把 `_source`, `_ingested_at`, `_run_id`, `_request_params_json`, `endpoint`, `partition_date` 等 ODS 内部字段原样带入，同时又新增 `source_system`, `ingested_at`。

影响：DWD schema 会不稳定，字段血缘重复，下游宽表容易误用 ODS 分区字段。

建议：
- DWD 显式列选择，不用财务大表的裸 `SELECT *`。
- 如确实需要保留 raw metadata，统一放到 `raw_metadata JSON` 或只保留标准血缘字段。

### P2-3 ODS 清单数量需要修正

原文位置：第 11、43 行。  
问题：文档写 `ashare_ods` 共 56 张外部表，但当前 BigQuery 是 54 张，文档中实际出现的唯一 ODS 表名也是 54 张。

建议：把数量改为 54，或补出缺失的 2 张表名及其目标层去向。

## 方案中值得保留的设计

- `sec_code` 统一主键、日期统一 DATE、金额/股本统一元/股，这些规范必要且适合多源扩展。
- 用后复权 `_hfq` 计算收益和技术指标、避免前复权进入训练特征，这个原则正确。
- DWD/DIM 物化为 BigQuery 原生表，ODS 只作为落地源；按月分区规避 4000 分区限制，方向合理。
- 首期只对外写 2019+，但财务读取前移，这个成本控制思路正确，只需补行情 lookback buffer。
- 明确 `stock_basic listed + delisted` 处理幸存者偏差，这个方向必须保留；但需要先解决 ODS `delist_date` 类型问题。

## 建议的落地顺序调整

1. 先修 ODS/中间读取问题：`stock_basic.delist_date` 类型一致性、`fina_indicator` 可见日规则、表级分区语义矩阵。
2. 先建 `dim_trade_calendar`，并确定 `trade_date_seq` 和 `visible_trade_date` 规则。
3. 建 `dim_stock`，同时加价格表覆盖校验：2019+ `daily` 出现过的代码必须能在维度中找到，找不到则进入异常表或补主数据。
4. 建 `dwd_stock_eod_price` 时使用“市场交易日 × 在市股票”或 `daily ∪ suspend_d` 骨架，不要只从 `daily` 起表。
5. 财务 DWD 先落版本事实表，再由 DWS 做严格 as-of；当前最新快照可以作为便捷表，但不要用于历史训练。
6. 最后再做 `dws_stock_feature_daily` / `dws_stock_label_daily`，并用 2019 年初、停牌样本、财务修正样本做回归校验。

