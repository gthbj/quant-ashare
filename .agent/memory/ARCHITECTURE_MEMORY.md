# 架构记忆（Architecture Memory）

## 数据流

```text
Tushare 等数据源
  -> data-aquarium.ashare_ods   ODS 外部表（Hive 分区，原样）
  -> ashare_dim / ashare_dwd    维度 + 明细（清洗/去重/复权/PIT/单位归一）
  -> ashare_dws                 (sec_code, trade_date) 特征宽表 + 标签
  -> ashare_ads (可选)          选股池 / 组合 / 回测输入
```

## GCP 生产流水线目标架构（OQ-005）

长期生产链路采用 GCP 原生组合：Cloud Run Jobs 负责 Tushare 兼容 API 到 GCS Parquet 的每日采集；Dataform / BigQuery Studio pipeline 负责 ODS→DIM/DWD/DWS/ADS 的 BigQuery SQL 转换、依赖、assertions 和文档；Cloud Composer 负责全流程编排、失败重试、补跑和告警。方案文档为 `docs/prd/PRD_20260603_03_GCP数据流水线方案.md`，正文已按 owner 反馈收敛为陈述性目标实现方案，并已补入财务 empty-return 口径和 Phase 1 Cloud Scheduler / Composer 触发入口。

2026-06-05 已合并剩余 ODS→ADS 生产调度链路 PRD：`docs/prd/PRD_20260605_01_OQ005剩余调度链路.md`。该文档是 Phase 1.7 生产采集之后的实现依据，定义 ODS gate、BigQuery SQL 兼容路径、Dataform definitions、ADS 契约隔离、刷新窗口、metadata、QA、pipeline 状态、告警、补跑、策略 runner/report 可选分支和 OQ-005 关闭标准。Phase 2.0 BigQuery SQL 兼容路径已由 PR #61 进入 `main` 并部署到 Composer；`skip_ingestion` / `qa_only` / `daily_current` 生产 smoke 已完成。

2026-06-06 新增 Composer DAG 拆分目标 PRD：`docs/prd/PRD_20260606_02_OQ005ComposerDAG拆分.md`。后续 OQ-005 调度边界应拆为 `ashare_ods_ingestion_daily`（生产采集 + ODS readiness）、`ashare_warehouse_window_refresh`（daily_current / backfill 的 DIM/DWD/DWS 窗口刷新）、`ashare_warehouse_full_rebuild`（手工全量维护）、`ashare_research_model_experiment`（手工单次研究实验）、`ashare_research_model_fanout`（手工批量候选搜索），`ashare_pipeline_alert_checker` 继续独立。新增生产能力应优先落到对应 DAG，不继续扩大 `ashare_daily_pipeline_v0`；跨 DAG 触发必须在 P0 记录 `upstream_pipeline_run_id` 并配置 refresh-missing watchdog。

2026-06-06 OQ-005 Composer DAG 拆分实现已由 PR #86 合入并完成生产部署 / 切换。`orchestration/composer/dags/ashare_common.py` 是共享 helper；production scheduled 入口为 `ashare_ods_ingestion_daily`，每日 20:00 CST 采集当前 14 个 ODS endpoint、执行非交易日 gate 和 ODS readiness，并在成功后触发 `ashare_warehouse_window_refresh`；`ashare_warehouse_window_refresh` 负责 `daily_current` / `backfill` 的 DIM/DWD/DWS 窗口刷新和 `qa_only` 只读 QA，`max_active_runs=1` 串行；`ashare_warehouse_full_rebuild` 是无 schedule 的手工全量维护 DAG。旧 `ashare_daily_pipeline_v0` 已暂停，仅保留为迁移期回滚参考。P0 跨 DAG 触发使用 `TriggerDagRunOperator`，并通过 `pipeline_run.upstream_pipeline_run_id` / `triggered_by_dag_id`、`v_pipeline_refresh_missing` 和 `warehouse_refresh_missing` 告警补可观测链路；refresh-missing 只在完全没有 linked warehouse run 时触发，已触发但失败的下游 run 交给 failure 告警。2026-06-06 已完成 Composer import 检查、非交易日 skip、`qa_only`、2026-06-05 1 日 backfill 和 refresh-missing synthetic transaction smoke；仍需等待新 DAG 至少两个开市日 scheduled run 和一个真实非交易日 scheduled skip 自然通过。

首批每日生产采集只覆盖当前 SQL 实际消费的 14 张 ODS：`daily`、`adj_factor`、`stk_limit`、`suspend_d`、`daily_basic`、`index_daily`、`index_dailybasic`、`stock_basic`、`trade_cal`、`namechange`、`fina_indicator`、`income`、`balancesheet`、`cashflow`。P1+ 当前未消费 endpoint 进入后续接入池；新增 endpoint 必须先更新采集 manifest、schema contract、单位契约和 QA。

2026-06-07 已补齐上证指数 `000001.SH` 的生产 BigQuery 读链路：`index_daily_000001_SH` / `index_dailybasic_000001_SH` 已加入 current-scope manifest、ODS external table 显式 `sourceUris`、`dim_index` seed 和 `dwd_index_eod`。由于 ODS index external tables 使用显式 URI 列表，不是 `endpoint=*` 自动发现，新增 index endpoint 时必须同步 `sql/ods/01_index_external_table_uris.sql` 并在 Composer setup 中运行；否则 GCS 已有文件也不会被 BigQuery ODS 读取。`ashare_warehouse_window_refresh` 的窗口转换链路已补 `sql/incremental/02_refresh_index_dwd_window.sql`，后续 daily_current/backfill 会先刷新指数 DWD，再刷新股票 DWD/DWS。为保持既有训练复现，本次不改 `dws_market_state_daily` / `market_state_v0_20260606`；新增训练市场状态应使用新版本。

2026-06-04 OQ-005 Phase 1/1.5/1.7 已实现 endpoint-group worker、`ashare-ingest-current-scope` 生产入口、Direct VPC egress + Cloud NAT 固定出口、ODS 可读性 QA 和 Composer smoke：`scripts/ingestion/run_ingestion_job.py` 是 Cloud Run Job 入口，`scripts/ingestion/common/endpoint_runner.py` 统一执行 API 拉取、血缘列、schema cast、分区写入和财务报告期 merge；`orchestration/cloud_run_jobs/` 保存采集镜像、Cloud Build、Job 配置和部署脚本，`orchestration/composer/dags/ashare_daily_pipeline_v0.py` 保存每日流水线 DAG。镜像已推送到 `asia-east2-docker.pkg.dev/data-aquarium/ashare/ingestion@sha256:351dfd996b6ec066135d68c40f84eb1c2a52e43ea8e28208ba1711be90a7652d`，5 个 Cloud Run Jobs 已部署且模板默认 `--dry-run`。Cloud Composer 3 环境 `ashare-composer` 已创建，DAG 文件同步到 Composer bucket 的 `dags/`，SQL 文件同步到 Composer bucket 的 `data/sql/`；不要把 SQL 树放在 `dags/sql/`，避免 DAG 解析/worker 同步异常。Airflow 变量 `ashare_pipeline_dry_run=false` 时，Composer 触发 `ashare-ingest-current-scope` 并显式传入 `--allow-gcs-write` 做生产写入；`ashare_enable_full_refresh=false` 时不进入完整 ODS→ADS 分支。Tushare token 只允许通过 Secret Manager 注入为 `TUSHARE_TOKEN`，官方或兼容 API 地址通过 `TUSHARE_HTTP_URL` 运行时配置。

OQ-005 raw GCS canonical 路径为 `a-share/tushare/raw_data/api=<api>/endpoint=<partition_endpoint>/partition_date=<YYYYMMDD>/data.parquet`，其中 `api=` 是实际 Tushare API 名（财务使用 `*_vip`），`endpoint=` 是 ODS partition endpoint / variant，不使用 `api=tushare`。live ingestion 写入成功/失败/空返回时同步写 `ashare_meta.ingestion_run` 和 `ashare_meta.ingestion_partition_status`；dry-run / API 只读 smoke 不写生产 meta 表。采集 publish 以 staging 校验后覆盖正式 object 为准，不做 write-once backup；需要可回滚的历史回填应另开 backup 开关或独立流程。

2026-06-05 OQ-005 Phase 2.0 DAG 目标主链为 setup → `pipeline_start_status` → 可选 `ashare-ingest-current-scope` Cloud Run Job → `sql/qa/09_ods_daily_partition_readiness.sql` → 按 `warehouse_mode` 进入只读 QA、BigQuery SQL 兼容全量转换或 ADS 契约手工初始化 → `pipeline_finalize_status` → finish。`09` 只检查业务日分区或近期小窗口；现有 CTAS 转换只能通过 `warehouse_mode=full_rebuild` 或 `warehouse_mode=full_rebuild_compat` 显式手工进入，legacy `ashare_enable_full_refresh=true` 记录为 `full_rebuild_compat`。`warehouse_mode=qa_only` 只跑只读 QA，`skip_ingestion=true` 用于跳过 Cloud Run 的 smoke / 下游验收，`enable_ads_contract_init=true` 才执行 ADS 契约初始化。PR #61 follow-up 后，DAG 不再在模块顶层读取 Airflow Variable，单次 DAG run 可用 `pipeline_dry_run` / `dry_run` 覆盖 Cloud Run dry/write 分支。default Celery queue 的纯 scheduler smoke `manual_oq005_scheduler_smoke_default_queue_20260604_01` 已成功，`2026-05-20` 至 `2026-06-05` SSE 开市日生产 GCS 写入 / 补写均成功并通过 `09` readiness；`manual_pr80_daily_current_20260605_20260606_01` 已按生产路径写入 `2026-06-05` 并完成 readiness、窗口刷新和窗口 QA；Phase 2.0 BigQuery SQL 兼容路径已进入 `main`。

2026-06-06 OQ-005 Phase 2.2 股票窗口刷新已进入 `main` 并完成生产 smoke。`warehouse_mode=daily_current` / `backfill` 且 `pipeline_dry_run=false` 时，Composer DAG 在 ODS readiness 后刷新 DIM 小表、恢复 P0 metadata，执行 `sql/incremental/01_refresh_stock_dwd_dws_window.sql` 窗口化刷新股票价格/估值 DWD 与策略 1 DWS，并执行 `sql/qa/10_windowed_stock_refresh_checks.sql`。窗口脚本不写 ADS runner/backtest/report 产物；`daily_current` 默认刷新最近 20 个交易日，非交易日 `date_to` / `business_date` 在本 hardening 分支中归一为不晚于请求日期的最近 SSE 开市日，`backfill` 保持显式日期；估值覆盖 QA 在 `daily_current` 默认检查该 20 日窗口，在 `backfill` 检查实际写入窗口；QA-WIN-18 只在 price-driven feature universe 内按 `total_mv_cny/circ_mv_cny` 口径检查 `dws_stock_feature_daily_v0.has_valuation_data`，不要求所有 DWD valuation 行进入最终特征宽表。标签、特征宽表和样本表按 SSE 交易日历向前回补 20 个交易日；价格特征向前读取 60 个交易日；估值特征按每只股票写入窗口首日前的实际 60 条估值观测推导读取边界，以覆盖 `daily_basic` 缺口。窗口 DML 使用 transaction 包裹并有目标表存在性守卫。`scripts/qa/run_windowed_refresh_equivalence.py` 是 full-vs-window 等价 QA runner：先用生产 DWD 估值表校验 `build_start_date` 足够早，再用 canonical full SQL 生成 scratch `_full` 表，复制为 `_window`，重写窗口 SQL 刷 `_window`，再逐列比较受影响窗口。PR #80 合并后已同步 DAG 与仓库 `sql/` 到 Composer bucket；`manual_pr80_daily_current_20260605_20260606_01` 成功完成 2026-06-05 current_scope 采集、ODS readiness、窗口 DIM/DWD/DWS 刷新和窗口 QA，`manual_pr80_qa_only_20260605_20260606_01` 成功完成 readiness + P0 / strategy1 / OQ004 / finance / OQ006 五个只读 QA。最近 20 个交易日 `2026-05-11..2026-06-05` ODS `daily_basic`、DWD valuation、DWS valuation 行数均为 110,035，错配天数 0。PR #83 已新增并部署 scheduled `daily_current` 非交易日 gate：在 ingestion 前查询 `ashare_dim.dim_trade_calendar`，非交易日通过实体 Python task 写 `skip_non_trading_day` 状态并跳过 ingestion、readiness 和 transform；普通手工触发不走 gate，部署 smoke 可显式 `force_non_trading_day_gate=true`；日历缺行 / `is_open` NULL 均 fail-closed；`manual_smoke_skip_non_trading_day_pr83_20260606_02` 已验证 gate、状态落库和 Cloud Run 未触发。

## ODS Raw Parquet Schema 修复约束

2026-06-03 已确认 10 张 ODS 外部表存在 2019+ Parquet 物理类型 mismatch，方案文档为 `docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md`。修复优先级：先修当前 P0 源表 `ods_tushare_stk_limit`，再分批修 P1/P2/P3 扩展表 `limit_list_d`、`moneyflow`、`margin_detail`、`dividend`、`margin`、`daily_info`、`sz_daily_info`、`fina_audit`、`stk_rewards`。2026-06-05 只读复核中，`sql/qa/06_ods_parquet_schema_checks.sql` 对 P0 与 all 范围均通过；当前 BigQuery 读层未再暴露 schema mismatch，后续是否关闭 OQ-012 或保留防复发任务待 owner 决定。

修复路径固定为：schema contract → GCS 原 Parquet 读取 → 显式 cast → staging → 临时 external table 验证 → backup → 发布正式 prefix → 正式 ODS QA。默认不从 API 重拉覆盖历史 raw；API 重拉仅作为原文件损坏、缺失、行数无法复原或 owner 明确要求的补救路径。

## ODS 三类分区语义（建模地基，务必牢记）

| 类 | 语义 | 例 | 处理方式 |
|---|---|---|---|
| A 行情增量 | `partition_date == trade_date`，单日单分区、无重复，历史自 1990-12-19 | daily, adj_factor, daily_basic, bak_basic, moneyflow, stk_limit, suspend_d | 按 partition_date 增量裁剪 |
| B 财务/公告 | `partition_date == 报告期(end_date)`，**非公告日**；同期多 report_type/修正 | income, balancesheet, cashflow, fina_indicator | 用 ann_date_eff 做 PIT；P0 默认合并报表 report_type='1'，DWD 保留口径字段 |
| C 维度快照 | 每个 partition_date 一份全量，取最新分区 | stock_basic, trade_cal, index_classify | 取 MAX(partition_date)；stock_basic 需 UNION listed+delisted |
| C* 历史区间快照 | 最新 partition_date 保存全量历史区间 | index_member_all, ci_index_member | 取最新分区，用 in_date/out_date 建 SCD2 时点维表 |

## 目标表（P0 优先级）

| 层 | 表 | 源 | 粒度 |
|---|---|---|---|
| dim | dim_trade_calendar | trade_cal | (exchange, cal_date) |
| dim | dim_stock | stock_basic(listed+delisted) | sec_code |
| dim | dim_stock_name_hist | namechange | (sec_code, start_date) SCD2 |
| dim | dim_index | index_daily + index_dailybasic endpoint stats | (sec_code, source_sec_code) |
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
- `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`
- `docs/策略1-ml_pv_clf_v0-runner设计.md`

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

2026-06-01 策略 1（`ml_pv_clf_v0`）已先落地价格量价首版 DWS/ADS：

- DWS 已物化 6 张表：`dws_stock_universe_daily`、`dws_stock_feature_price_daily`、`dws_stock_feature_valuation_daily`、`dws_stock_label_daily`、`dws_stock_feature_daily_v0`、`dws_stock_sample_daily`。
- ADS 已物化 11 张契约表：训练面板、模型注册、预测、候选池、组合目标、订单计划、回测成交/持仓/NAV/绩效汇总、信号监控。
- 标签口径固定为 `close_hfq[t+H] / open_hfq[t+1] - 1`，H=1/5/10/20；`rank_pct_Hd` / `fwd_xs_ret_Hd` 按默认 universe 截面计算；`label_entry_tradable` 只用于训练有效性、回测撮合和归因，不作为 t 日选股过滤。
- 首个基线默认股票池仅纳入沪深主板（`SSE_MAIN` / `SZSE_MAIN`），不含北交所、创业板、科创板；后续如需纳入其他板块，用 `board_allowlist` 另开对照实验或单独模型。
- 当前策略 1 DWS 不直接读取 ODS；由于最终 DWD 价格表不落 2018 buffer 行，2019 年初 60 日窗口用 `has_full_history_60d=FALSE` 显式标记，默认样本掩码剔除不完整窗口。
- 策略 1 runner 执行路径已收敛为 BigQuery SQL + BigQuery ML：用 `ads_ml_training_panel_daily` 冻结样本，BQML `LOGISTIC_REG` 训练 `label_top30_5d`，正则化用 BQML 原生 `L1_REG/L2_REG` 手动候选网格并按 valid RankIC/分层收益选择，`ML.PREDICT` 写 `ads_model_prediction_daily`，后续候选池、组合、订单、回测和监控全部写既有 ADS 表。`board` 仅作分组/暴露监控，不进入 v0 主模型训练列。设计文档为 `docs/策略1-ml_pv_clf_v0-runner设计.md`；runner SQL 计划放 `sql/ml/strategy1/`。
- 策略 1 后续目标执行路径为 Cloud Run Jobs / Python runner：`docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md` 定义用 scikit-learn / 后续 Python 模型库替代 BQML 训练 / 预测，用 Cloud Run Python `ledger_exec_v1` 替代 BigQuery scripting `08` 回测；BigQuery DWS/ADS、GCS artifact、报告诊断和 QA 仍是事实契约。Cloud Run 多实验 orchestrator 默认并发数等于 manifest 可执行实验数量，owner 可显式设置 `--max-parallel-experiments`；2026-06-05 owner 已决定后续不再使用 BigQuery ML + `sql/ml/strategy1` SQL runner 作为策略执行层默认 / fallback / 新增开发路线，既有 runner 仅作 historical reference / audit。
- runner 实现 PRD 为 `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`，交付 `sql/ml/strategy1/01-10` 脚本、README、QA、报告产物（GCS 或 local-only 镜像）和报告渲染脚本 `scripts/strategy1/render_report.py`。**回测口径自 PR #12 为 v1 账户级有状态 ledger**（scripting `WHILE` 循环逐调仓 period：按当前 NAV 定档、卖先于买、买受现金约束、netting；不可交易腿本期跳过 + carry）。原 PRD 的 v0 set-based + 预计算 `next_sellable_trade_date` / 60 日顺延口径在真机违反守卫后已废弃升级（DECISION-20260601-07 触发、DECISION-20260602-01 落地）。报告 `report_uri` 仅在真实上传 GCS 时写，local-only（`--skip-gcs-upload`）写 `local_report_path` + `report_upload_status=skipped`。
- 回测报告 artifact 采用 GCS-first + 本地镜像：结构化结果以 ADS 表为事实来源；Markdown/HTML/图表/JSON 持久写 `gs://<ashare-artifact-bucket>/reports/strategy1/ml_pv_clf_v0/run_id=<run_id>/backtest_id=<backtest_id>/`，并镜像到本地 `reports/strategy1/ml_pv_clf_v0/run_id=<run_id>/backtest_id=<backtest_id>/` 方便读取；本地 `reports/` 默认不提交 git。

## SQL 代码布局

- 根目录 `sql/` 存放 P0 BigQuery Standard SQL：`00_create_datasets.sql`、`dim/*.sql`、`dwd/*.sql`、`dws/*.sql`、`ads/*.sql`。
- 现有脚本覆盖 4 张 DIM + 5 张 DWD + 6 张策略 1 DWS + 11 张 ADS 契约表，使用 `CREATE OR REPLACE TABLE` + CTAS/DDL + 字段描述；`sql/qa/01_core_smoke_checks.sql` 存放 DIM/DWD 基础断言，`sql/qa/02_strategy1_dws_ads_checks.sql` 存放策略 1 DWS/ADS 断言，`sql/qa/03_index_benchmark_checks.sql` 存放 OQ-004 指数映射与 benchmark 覆盖断言。
- `sql/incremental/01_refresh_stock_dwd_dws_window.sql` 是 OQ-005 Phase 2.2 股票 DWD/DWS 窗口刷新脚本；`sql/qa/10_windowed_stock_refresh_checks.sql` 是对应窗口 QA；`scripts/qa/run_windowed_refresh_equivalence.py` 是定期/发布前 full-vs-window 数值等价 QA。
- `sql/metadata/01_core_table_column_descriptions.sql` 统一维护 P0 DIM/DWD 表级和字段级中文说明；每次重建 P0 表后都应重新执行该 metadata 脚本。
- 当前脚本是 bootstrap SQL，不关闭 OQ-005；后续仍可迁移为 dbt 或纳入 Airflow 调度。
- 2026-05-31 P0 已物化到 BigQuery；`dwd_index_eod` 已恢复读取 `index_dailybasic`。该接口市值/股本单位为元/股，不做 `*10000` 换算。
- `dim_index` 统一维护指数 canonical 代码、ODS 实际 `source_sec_code`、端点可用性、起止日期和 benchmark 候选标记。`dwd_index_eod` 从 `dim_index` 读取可用端点与映射；双代码指数如沪深300由 `399300.SZ -> 000300.SH` 输出。策略 runner 使用 benchmark 前必须校验 `dim_index` 和完整 NAV 窗口覆盖。
- `dwd_stock_eod_price` 中 `is_suspended` 仅表示全天停牌/无成交；有成交的 `S` 事件另用 `has_intraday_halt`，开盘时段/未知时段临停用 `has_open_halt` 并影响开盘侧可交易掩码。
- `dim_stock.delist_date` 优先使用 ODS `stock_basic_delisted.delist_date`（当前为可解析 `STRING`）；只有 ODS 退市日缺失时才用 `daily` 最后交易日加一天兜底。
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
