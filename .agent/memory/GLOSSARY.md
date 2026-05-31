# 术语表（Glossary）

| 术语 | 含义 |
|---|---|
| ODS / DIM / DWD / DWS | 数仓分层：贴源外部表 / 维度 / 明细 / 特征汇总 |
| sec_code | 统一证券主键，数据源中性，值如 `600000.SH`（源 Tushare `ts_code` 归一） |
| sec_type | 证券品种：stock/index/fund/cb/industry |
| PIT (Point-In-Time) | 时点正确：只用某时点已可见的数据，杜绝未来函数 |
| ann_date_eff | 财务数据可见日 = `COALESCE(f_ann_date, ann_date)`，PIT 连接键 |
| report_period | 报告期（财报 `end_date`），≠ 可见时间 |
| 后复权 / _hfq | `raw × adj_factor`，单调无未来依赖，用于指标与收益 |
| 前复权 / _qfq | 截至基准日的复权价，含未来除权信息，仅展示、不入训练特征 |
| adj_factor | Tushare 累计后复权因子 |
| ret_1d / fwd_ret_Nd | 复权日收益率 / 未来 N 日复权收益（标签） |
| universe | 某交易日的可选股票集合（含退市股历史区间） |
| 幸存者偏差 | 只用当前存续股票回测导致的偏差；靠 UNION 退市股避免 |
| 可交易掩码 (is_tradable) | 非停牌 且 非一字板 且 在市，作为样本过滤 |
| 一字板 | 开=高=低=收 且触及涨跌停，当日买不进/卖不出 |
| 横截面 | 同一 trade_date 全市场股票构成的截面 |
| require_partition_filter | BigQuery 表选项，强制查询带分区过滤 |
| SCD2 | 缓慢变化维 Type-2，用起止区间记录维度历史（如曾用名/ST） |
| 北向 (hk_hold/hsgt) | 沪深港通资金/持股 |
| 两融 (margin) | 融资融券 |
| 龙虎榜 (top_list) | 交易所每日大额异动榜单 |
| 筹码 (cyq_perf) | 筹码分布与获利盘比例 |
| source_system / ingested_at | 血缘字段：数据来源系统 / 入库时间 |
