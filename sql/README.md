> 文档维护：GPT-5 Codex（最近更新 2026-06-10）

# A 股 DIM/DWD/DWS/ADS 建表 SQL

本目录存放基于 BigQuery `data-aquarium.ashare_ods` 构建 `ashare_dim`、`ashare_dwd`、`ashare_dws`、`ashare_ads` 的建表 SQL。当前建模目标是 **2019-01-01 之后的 A 股日线中低频量化数据**；2019 年以前数据只作为 PIT、滚动窗口或维表历史的支撑输入。

## 执行顺序

所有 BigQuery job 显式指定 `--location=asia-east2`，与 ODS/目标数据集保持一致。

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/00_create_datasets.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/meta/01_create_meta_tables.sql
# 单位换算映射（OQ-006）：覆盖 P0 + 财务三表标准字段，qa/05 据此门禁。
bq query --use_legacy_sql=false --location=asia-east2 < sql/meta/04_ods_field_unit_map.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dim/01_dim_trade_calendar.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dim/02_dim_stock.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dim/03_dim_stock_name_hist.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dim/04_dim_index.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dwd/01_dwd_stock_eod_price.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dwd/02_dwd_stock_eod_valuation.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dwd/03_dwd_fin_indicator.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dwd/04_dwd_index_eod.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dwd/05_dwd_fin_indicator_latest.sql
# 财务三大报表 DWD（PIT 版本事实表 + 默认合并口径 latest，OQ-003）。表/字段完整说明在 sql/metadata/02（CTAS 重建后必跑）。
bq query --use_legacy_sql=false --location=asia-east2 < sql/dwd/06_dwd_fin_income.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dwd/07_dwd_fin_income_latest.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dwd/08_dwd_fin_balancesheet.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dwd/09_dwd_fin_balancesheet_latest.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dwd/10_dwd_fin_cashflow.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dwd/11_dwd_fin_cashflow_latest.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/metadata/01_core_table_column_descriptions.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/01_dws_stock_universe_daily.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/02_dws_stock_feature_price_daily.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/03_dws_stock_feature_valuation_daily.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/04_dws_stock_label_daily.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/05_dws_stock_feature_daily_v0.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/06_dws_stock_sample_daily.sql
# 默认合并口径 PIT 财务特征（OQ-003），依赖 universe + 财务三表 + dwd_fin_indicator。
bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/07_dws_stock_feature_fin_daily.sql
# 财务三表 DWD + 财务特征 DWS 表/字段说明补齐（OQ-003，PRD §10；CTAS 重建后必跑，qa/04 含缺失断言）。
bq query --use_legacy_sql=false --location=asia-east2 < sql/metadata/02_finance_table_column_descriptions.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ads/01_ads_strategy1_tables.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/02_strategy1_dws_ads_checks.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/04_finance_caliber_checks.sql

# 策略 1 共享 SQL（当前 Cloud Run Python path 复用，详见 sql/strategy1/README.md）
bq query --use_legacy_sql=false --location=asia-east2 < sql/strategy1/panel/build_training_panel_base.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/strategy1/execution/build_candidates.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/strategy1/execution/build_portfolio_targets.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/strategy1/execution/build_order_plan.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/strategy1/reporting/build_metrics_and_report_inputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_runner_outputs.sql
python scripts/strategy1/render_report.py --project data-aquarium --backtest-id bt_s1_bqml_20260601_01 --run-id s1_bqml_20260601_01 --artifact-base-uri gs://ashare-artifacts/reports/strategy1

# Cloud Run Python lot-aware ledger 路径额外执行
bq query --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_lot_aware_ledger_outputs.sql
```

## 范围参数

- 行情 DWD：写入 `dwd_start_date = 2019-01-01` 之后的数据；价格表默认读取 `lookback_start_date = 2018-01-01` 作为滚动窗口和 `ret_1d` warm-up。
- 策略 1 DWS：写入 `dws_start_date = 2019-01-01` 之后的数据；当前只读取已物化 DWD/DIM，不直接读取 ODS。由于最终 DWD 价格表不落 2018 buffer 行，价格特征表用 `has_full_history_60d` 显式标记 2019 年初 60 日窗口不完整样本，样本默认训练掩码会剔除这些行。
- 当前物化结果下，`sample_trainable_default = TRUE` 的最早 `trade_date` 为 `2019-04-03`，2019Q1 无默认可训练样本；该范围由 `sql/qa/02_strategy1_dws_ads_checks.sql` 断言。
- 财务 DWD：`fina_indicator` 从 `fin_start_period = 20170101` 起读取并写入，用于 2019+ PIT 和同比/基期特征。
- 财务三大报表 DWD（OQ-003）：`income` / `balancesheet` / `cashflow` 同样从 `fin_start_period = 20170101` 起读取，可见日 `ann_date_eff = COALESCE(f_ann_date, ann_date)`；保留源 `report_type` 并派生 `report_caliber` / `is_default_report_caliber`，默认消费口径为合并报表 `report_type='1'`（实测当前 ODS 仅此一种口径）。默认 `_latest` 与 `dws_stock_feature_fin_daily` 只消费默认合并口径。
- `dws_stock_feature_fin_daily`：把 `dwd_fin_indicator` 与三大报表 PIT as-of 到每个 universe 交易日，主键 `(sec_code, trade_date, feature_version='fin_default_v0_20260602')`。as-of 限制 `visible_trade_date` 在 `[trade_date - asof_lookback_days, trade_date]`（默认 `asof_lookback_days = 900` 日 ≈ 2.5 年）以约束扇出；超窗未更新财报视为缺失（`has_fin_*=FALSE`）。`report_caliber`/`is_default_report_caliber` 为消费口径契约（恒 consolidated/TRUE），实际可用性见 `has_fin_*` 与各来源 `*_report_period`。
- 维度/日历：使用最新快照或全量历史事件，不按 2019 分区截断。

## 窗口刷新

`sql/incremental/01_refresh_stock_dwd_dws_window.sql` 用于生产每日或区间补跑。目标表必须已由全量 CTAS 路径初始化；脚本只刷新股票日频 DWD 与策略 1 DWS，不写 ADS run/backtest 产物。

- DWD 写入窗口：`backfill` 保持显式 `date_from` / `date_to`；`daily_current` 未传 `date_from` 时，先把 `date_to` 或 `business_date` 归一到不晚于请求日期的最近 SSE 开市日，再刷新最近 20 个交易日。
- 价格特征读取窗口：按 SSE 交易日历向前读取 60 个交易日。
- 估值特征读取窗口：按每只股票写入窗口首日前的实际 60 条估值观测推导，覆盖 `daily_basic` 缺口。
- 标签、特征宽表、样本表写入窗口：按 SSE 交易日历向前回补 20 个交易日，覆盖 forward label 受新增价格影响的历史样本。
- 窗口 DML 使用 BigQuery transaction 包裹，日常小窗口失败时整体回滚；大区间 backfill 按年/季/月拆分执行。

```bash
bq query \
  --use_legacy_sql=false \
  --location=asia-east2 \
  --parameter=business_date:STRING:2026-06-04 \
  --parameter=date_from:STRING:2026-06-03 \
  --parameter=date_to:STRING:2026-06-04 \
  --parameter=warehouse_mode:STRING:backfill \
  < sql/incremental/01_refresh_stock_dwd_dws_window.sql

bq query \
  --use_legacy_sql=false \
  --location=asia-east2 \
  --parameter=business_date:STRING:2026-06-04 \
  --parameter=date_from:STRING:2026-06-03 \
  --parameter=date_to:STRING:2026-06-04 \
  --parameter=warehouse_mode:STRING:backfill \
  < sql/qa/10_windowed_stock_refresh_checks.sql
```

窗口刷新和全量 CTAS 逻辑并存期间，定期或发布前运行等价 QA，防止两条路径静默漂移。该 QA 会先用生产 DWD 估值表校验 `build_start_date` 足够早，避免 full shadow 与 window shadow 被同样截断后假通过；随后把 canonical full SQL 渲染到 scratch `_full` 表，再把 `_full` 复制为 `_window` 表，重写窗口 SQL 刷 `_window`，最后逐列比较受影响窗口内 `_window` 与 `_full` 的数值。

```bash
python3 scripts/qa/run_windowed_refresh_equivalence.py --dry-run

python3 scripts/qa/run_windowed_refresh_equivalence.py \
  --project data-aquarium \
  --location asia-east2 \
  --scratch-dataset ashare_qa_windowed_equivalence \
  --build-start-date 2024-01-01 \
  --lookback-start-date 2023-01-01 \
  --date-from 2025-06-02 \
  --date-to 2025-06-13
```

## 产出表

- `data-aquarium.ashare_dim.dim_trade_calendar`
- `data-aquarium.ashare_dim.dim_stock`
- `data-aquarium.ashare_dim.dim_stock_name_hist`
- `data-aquarium.ashare_dim.dim_index`
- `data-aquarium.ashare_dwd.dwd_stock_eod_price`
- `data-aquarium.ashare_dwd.dwd_stock_eod_valuation`
- `data-aquarium.ashare_dwd.dwd_fin_indicator`
- `data-aquarium.ashare_dwd.dwd_index_eod`
- `data-aquarium.ashare_dwd.dwd_fin_indicator_latest`
- `data-aquarium.ashare_dwd.dwd_fin_income` / `dwd_fin_income_latest`
- `data-aquarium.ashare_dwd.dwd_fin_balancesheet` / `dwd_fin_balancesheet_latest`
- `data-aquarium.ashare_dwd.dwd_fin_cashflow` / `dwd_fin_cashflow_latest`
- `data-aquarium.ashare_dws.dws_stock_universe_daily`
- `data-aquarium.ashare_dws.dws_stock_feature_price_daily`
- `data-aquarium.ashare_dws.dws_stock_feature_valuation_daily`
- `data-aquarium.ashare_dws.dws_stock_label_daily`
- `data-aquarium.ashare_dws.dws_stock_feature_daily_v0`
- `data-aquarium.ashare_dws.dws_stock_sample_daily`
- `data-aquarium.ashare_dws.dws_stock_feature_fin_daily`
- `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
- `data-aquarium.ashare_ads.ads_model_registry`
- `data-aquarium.ashare_ads.ads_model_prediction_daily`
- `data-aquarium.ashare_ads.ads_stock_candidate_daily`
- `data-aquarium.ashare_ads.ads_portfolio_target_daily`
- `data-aquarium.ashare_ads.ads_order_plan_daily`
- `data-aquarium.ashare_ads.ads_backtest_trade_daily`
- `data-aquarium.ashare_ads.ads_backtest_position_daily`
- `data-aquarium.ashare_ads.ads_backtest_nav_daily`
- `data-aquarium.ashare_ads.ads_backtest_performance_summary`
- `data-aquarium.ashare_ads.ads_signal_monitor_daily`

## QA

物化后运行基础断言：

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/01_core_smoke_checks.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/02_strategy1_dws_ads_checks.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/03_index_benchmark_checks.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/04_finance_caliber_checks.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/05_unit_contract_checks.sql
```

## Metadata

`sql/metadata/01_core_table_column_descriptions.sql` 统一维护 P0 DIM/DWD 表级和字段级中文说明。每次 `CREATE OR REPLACE TABLE` 重建 P0 表后，都应重新执行该 metadata 脚本，避免字段 description 被 CTAS 覆盖或遗漏。

`sql/metadata/02_finance_table_column_descriptions.sql` 同理维护财务三表 DWD（`dwd_fin_income/balancesheet/cashflow` + 各自 `_latest`）和 `dws_stock_feature_fin_daily` 的全部字段说明（OQ-003，PRD §10）。这些表 CTAS 重建后必须重跑该脚本；`sql/qa/04_finance_caliber_checks.sql` 内置字段 description 缺失断言，漏跑会被 QA 拦截。

## 注意事项

- ODS 外部表必须显式过滤 `endpoint` 和/或 `partition_date`，脚本已按该约束写入过滤条件。
- `stock_basic_delisted.delist_date` 当前在 ODS 侧为 `STRING` 且可解析；`dim_stock` 优先使用该字段作为正式退市边界，仅在缺值时回退到日线最后交易日加一天。
- `dwd_stock_eod_price` 使用交易日历乘股票生命周期生成骨架，再左连接行情，因此停牌日会保留一行。
- `suspend_d` 同时包含停牌 `S` 与复牌 `R` 事件；价格 DWD 只把 `S` 纳入停牌事件，避免复牌日被误判不可交易。
- `index_dailybasic` 的市值/股本单位已经是元/股，`dwd_index_eod` 不做 `*10000` 换算。
- `dim_index` 统一维护指数 canonical 代码、ODS 实际 `source_sec_code`、端点可用性和 benchmark 候选标记；`dwd_index_eod` 从该维表读取映射。
- `dwd_index_eod.sec_code` 输出 canonical 指数代码，`source_sec_code` 保留 ODS/Tushare 实际代码；例如沪深300 来源 `399300.SZ` 输出为 `sec_code='000300.SH'`。策略 runner 使用 benchmark 前会校验 `dim_index` 和完整回测窗口覆盖。
- 价格/估值/指数 DWD 使用月分区并开启 `require_partition_filter`；财务指标按公告月分区，但不强制分区过滤，方便 PIT as-of join。
- 策略 1 标签口径为 `close_hfq[t+H] / open_hfq[t+1] - 1`，H 为 1/5/10/20；`rank_pct_Hd` / `fwd_xs_ret_Hd` 按默认 universe 截面计算；`label_valid_Hd` 检查 t+1 入场可交易和标签价格可用，退出日可卖性单独由 `exit_reachable_Hd` 标记并交给回测撮合处理；`label_entry_tradable` 不能在 t 日选股时预先过滤。
- 策略 1 ADS SQL 只创建表契约；当前训练、预测和回测由 Cloud Run Python path 写入，候选池、组合、订单、报告输入和 QA 复用 `sql/strategy1/**` 的共享 SQL，并由 `configs/strategy1/active_step_catalog.yml` 维护路径和参数契约。
