> 文档维护：GPT-5（最近更新 2026-05-31）

# A 股 DIM/DWD 建表 SQL

本目录存放基于 BigQuery `data-aquarium.ashare_ods` 构建 `ashare_dim`、`ashare_dwd` 的建表 SQL。当前建模目标是 **2019-01-01 之后的 A 股日线中低频量化数据**；2019 年以前数据只作为 PIT、滚动窗口或维表历史的支撑输入。

## 执行顺序

```bash
bq query --use_legacy_sql=false < sql/00_create_datasets.sql
bq query --use_legacy_sql=false < sql/dim/01_dim_trade_calendar.sql
bq query --use_legacy_sql=false < sql/dim/02_dim_stock.sql
bq query --use_legacy_sql=false < sql/dim/03_dim_stock_name_hist.sql
bq query --use_legacy_sql=false < sql/dwd/01_dwd_stock_eod_price.sql
bq query --use_legacy_sql=false < sql/dwd/02_dwd_stock_eod_valuation.sql
bq query --use_legacy_sql=false < sql/dwd/03_dwd_fin_indicator.sql
bq query --use_legacy_sql=false < sql/dwd/04_dwd_index_eod.sql
```

## 范围参数

- 行情 DWD：写入 `dwd_start_date = 2019-01-01` 之后的数据；价格表默认读取 `lookback_start_date = 2018-01-01` 作为滚动窗口和 `ret_1d` warm-up。
- 财务 DWD：`fina_indicator` 从 `fin_start_period = 20170101` 起读取并写入，用于 2019+ PIT 和同比/基期特征。
- 维度/日历：使用最新快照或全量历史事件，不按 2019 分区截断。

## 产出表

- `data-aquarium.ashare_dim.dim_trade_calendar`
- `data-aquarium.ashare_dim.dim_stock`
- `data-aquarium.ashare_dim.dim_stock_name_hist`
- `data-aquarium.ashare_dwd.dwd_stock_eod_price`
- `data-aquarium.ashare_dwd.dwd_stock_eod_valuation`
- `data-aquarium.ashare_dwd.dwd_fin_indicator`
- `data-aquarium.ashare_dwd.dwd_index_eod`

## 注意事项

- ODS 外部表必须显式过滤 `endpoint` 和/或 `partition_date`，脚本已按该约束写入过滤条件。
- `stock_basic_delisted.delist_date` 在 ODS 侧存在 Parquet 类型不一致问题，`dim_stock` 不读取该字段；退市边界用日线最后交易日推导。
- `dwd_stock_eod_price` 使用交易日历乘股票生命周期生成骨架，再左连接行情，因此停牌日会保留一行。
- 价格/估值/指数 DWD 使用月分区并开启 `require_partition_filter`；财务指标按公告月分区，但不强制分区过滤，方便 PIT as-of join。
