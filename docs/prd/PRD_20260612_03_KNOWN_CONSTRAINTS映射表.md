# PRD_20260612_03 KNOWN_CONSTRAINTS before/after 映射表

> 文档维护：GPT-5.5（最近更新 2026-06-12）

本表按改动前 `KNOWN_CONSTRAINTS.md` 的每个 bullet / 子 bullet 列出处置方式。`拆分重排` 仅改变 Markdown 行形态，原句顺序和操作性语义保留。

拆分行的子条款清单 = After 区间内各 bullet，按行号核对。

| Before 行 | 原条款摘要 | 处置方式 | After 落点 |
|---|---|---|---|
| 5 | `- ODS 全部为 Hive 分区外部表，**查询必须带 `partition_date`/`endpoint` 过滤**（强制分区裁剪），否则报错。`partition_date` 是 `YYYYMMDD` 字符串。` | 原文保留 | KNOWN_CONSTRAINTS.md:5 |
| 6 | `- OQ-005 采集 manifest 中 `endpoint` 表示 Tushare API endpoint，`partition_endpoint` 表示写入 GCS Hive 分区 `endpoint=` 的值；两者不得混用。普通接口二者相同，`stock_bas...` | 原文保留 | KNOWN_CONSTRAINTS.md:6 |
| 7 | `- OQ-005 raw GCS Hive 路径 canonical 口径固定为 `a-share/tushare/raw_data/api=<api>/endpoint=<partition_endpoint>/partition_date=<YYYYMMDD>/data...` | 原文保留 | KNOWN_CONSTRAINTS.md:7 |
| 8 | `- 2026-06-03 复核确认 10 张 ODS 外部表存在 Parquet schema mismatch：`ods_tushare_daily_info`、`ods_tushare_dividend`、`ods_tushare_fina_audit`、`ods_tu...` | 原文保留 | KNOWN_CONSTRAINTS.md:8 |
| 9 | `- **财务表 `partition_date == 报告期(end_date)`，不是公告日**：禁止用 partition_date 当数据可见时间，必须用 `ann_date_eff = COALESCE(f_ann_date, ann_date)` 做 PIT。` | 原文保留 | KNOWN_CONSTRAINTS.md:9 |
| 10 | `- 财务表同一 `(sec_code, 报告期)` 有多条（不同 `report_type`/修正/`update_flag`）：P0 默认消费合并报表 `report_type='1'`；带 `report_type` 的 DWD 版本事实表保留源 `report_typ...` | 原文保留 | KNOWN_CONSTRAINTS.md:10 |
| 11 | `- **三大报表 `income/balancesheet/cashflow` 已落地**（`sql/dwd/06/08/10` + `_latest` 07/09/11，OQ-003/DECISION-20260601-05）：实测当前 ODS 三表**仅含 `repor...` | 原文保留 | KNOWN_CONSTRAINTS.md:11 |
| 12 | `- `dws_stock_feature_fin_daily`（`feature_version='fin_default_v0_20260602'`）把 `dwd_fin_indicator` + 三大报表 as-of 到 universe 每个交易日：`report_c...` | 原文保留 | KNOWN_CONSTRAINTS.md:12 |
| 13 | `- `dwd_fin_*_latest` / `dwd_fin_indicator_latest` 是便捷最新表，不用于 PIT 回测 join；其版本排序按 `update_flag DESC, ann_date_eff DESC, ingested_at DESC, s...` | 原文保留 | KNOWN_CONSTRAINTS.md:13 |
| 14 | `- `stock_basic` 用 `endpoint` 分 `listed`/`delisted`：**必须 UNION 两者**，否则丢失退市股 → 幸存者偏差。` | 原文保留 | KNOWN_CONSTRAINTS.md:14 |
| 15 | `- 行情历史自 **1990-12-19**；行情表单分区内 `(ts_code, trade_date)` 已唯一、无需去重。` | 原文保留 | KNOWN_CONSTRAINTS.md:15 |
| 16 | `- 2019 年前数据范围分三类，不能混作“默认全历史写入”：财务/事件按分区前移到 `20170101`；日常 `daily_current` 与全量 CTAS 默认仍以行情 DWD/DWS `trade_date >= 2019-01-01` 为生产下限，构建时按最大滚...` | 原文保留 | KNOWN_CONSTRAINTS.md:16 |
| 17 | `- 行情 lookback buffer 不落最终 DWD/DWS；`ret_1d` 至少读到 2018 年最后一个交易日，120/250 日滚动特征按窗口多读。` | 原文保留 | KNOWN_CONSTRAINTS.md:17 |
| 18 | `- 当前已物化的策略 1 价格 DWS 只读取最终 DWD/DIM，不直接打 ODS；最终 DWD 价格表不落 2018 buffer 行，因此 2019 年初 60 日窗口以 `has_full_history_60d=FALSE` 显式标记，默认样本掩码剔除这些不完整窗...` | 原文保留 | KNOWN_CONSTRAINTS.md:18 |
| 19 | `- **`fina_indicator` 无 `f_ann_date`**（实测）：其可见日只能用 `ann_date`；可见日规则**按表定义**，不可用统一 `COALESCE(f_ann_date,ann_date)` 公式覆盖所有财务表（见 docs §4.3）。` | 原文保留 | KNOWN_CONSTRAINTS.md:19 |
| 20 | `- `stock_basic_delisted.delist_date` 已由上游统一为 `STRING` 并可直读解析；`dim_stock` 应优先使用 ODS 退市日，只有缺值时才用 `daily` 最后交易日加一天兜底（OQ-007 已关闭）。` | 原文保留 | KNOWN_CONSTRAINTS.md:20 |
| 21 | `- **停牌日 `daily` 无该股行**：价格 DWD 必须以「交易日历开市日 × 在市股票」为骨架（保留停牌日空行），不能从 `daily` 起表，否则停牌日整行消失、`t+k` 标签错位。` | 原文保留 | KNOWN_CONSTRAINTS.md:21 |
| 22 | `- **`suspend_d.suspend_type` 区分停牌/复牌**：`S`=停牌，`R`=复牌。价格 DWD 只可用 `S` 标记停牌事件；`R` 复牌日若 daily 有成交，不能判 `is_suspended=TRUE`。` | 原文保留 | KNOWN_CONSTRAINTS.md:22 |
| 23 | `- `S` 事件也可能是盘中临停。若当日 `daily` 有 close 且 volume > 0，不能把该行标为全天停牌；DWD 用 `has_intraday_halt` 标记盘中临停，用 `has_open_halt` 标记开盘时段或未知时段临停并影响开盘建仓掩码。` | 原文保留 | KNOWN_CONSTRAINTS.md:23 |
| 24 | `- Tushare 各接口金额/量单位不一（手/千元/万股/万元）：落库须按「表+字段」归一到元/股。` | 原文保留 | KNOWN_CONSTRAINTS.md:24 |
| 25 | `- OQ-006 已实现：`ashare_meta.ods_field_unit_map` 是单位换算唯一事实来源；`dwd_index_eod.volume/amount` 已按 `vol*100` / `amount*1000` 换算并迁移为 `volume_share...` | 原文保留 | KNOWN_CONSTRAINTS.md:25 |
| 26 | `- `dwd_stock_dividend_event` 是 ledger 可消费的分红送转事件入口；ledger 不得直读 `ods_tushare_dividend`。Phase A 仅覆盖现金分红、送股、转增；A 股无美股式 split/并股机制，配股/增发等未采集公...` | 原文保留 | KNOWN_CONSTRAINTS.md:26 |
| 27 | `- 部分数值字段在 ODS 是 STRING（如 `moneyflow_hsgt`、`ccass_hold`）：落库须 `SAFE_CAST`。` | 原文保留 | KNOWN_CONSTRAINTS.md:27 |
| 28 | `- 北向数据（hk_hold / moneyflow_hsgt）2024 年后部分口径变化/停更，需做可用性标记。` | 原文保留 | KNOWN_CONSTRAINTS.md:28 |
| 29 | `- `index_member_all` / `ci_index_member` 已在 ODS 中可用，是最新分区中的全量历史行业归属区间快照；历史 join 必须用 `in_date/out_date`，不能用 `is_new` 回填历史。默认区间口径为 `[in_dat...` | 原文保留 | KNOWN_CONSTRAINTS.md:29 |
| 30 | `- `dim_index` 是指数 canonical 映射、ODS 实际代码、端点可用性和 benchmark 候选状态的事实来源。`dwd_index_eod.sec_code` 应输出 canonical 指数代码；若 ODS 实际代码不同，用 `source_sec...` | 原文保留 | KNOWN_CONSTRAINTS.md:30 |
| 31 | `- runner 使用 `benchmark_sec_code` 前必须校验该代码在 `dim_index` 中 `has_daily=TRUE AND is_benchmark_candidate=TRUE`，并校验完整 NAV 窗口内 `dwd_index_eod` 对...` | 原文保留 | KNOWN_CONSTRAINTS.md:31 |
| 35 | `- **单表最多 4000 个分区**：行情表必须按月分区（`DATE_TRUNC(trade_date, MONTH)`），不能按天。` | 原文保留 | KNOWN_CONSTRAINTS.md:35 |
| 36 | `- **只有分区列能 `require_partition_filter` 强制过滤；聚簇列无法强制**。` | 原文保留 | KNOWN_CONSTRAINTS.md:36 |
| 37 | `- 对本项目所有启用 `require_partition_filter=TRUE` 的 BigQuery 分区表，任何 `SELECT` / `ASSERT` / `DELETE` / `UPDATE` / `MERGE` / 清理脚本都必须在对应表引用上显式写分区列过滤...` | 原文保留 | KNOWN_CONSTRAINTS.md:37 |
| 38 | `- `CREATE TABLE AS SELECT` 不能在 SELECT 列上内联 description：维度表用内联列定义 DDL，事实表用 CTAS + 后置 `ALTER COLUMN SET OPTIONS`。` | 原文保留 | KNOWN_CONSTRAINTS.md:38 |
| 39 | `- 核心表重建后必须执行 `sql/metadata/01_core_table_column_descriptions.sql`，集中恢复/补齐表级和字段级中文说明。财务三表 DWD（`dwd_fin_income/balancesheet/cashflow` + `_l...` | 原文保留 | KNOWN_CONSTRAINTS.md:39 |
| 40 | `- 外部表的列描述/分区元数据通过 `bq show`/`INFORMATION_SCHEMA` 获取。` | 原文保留 | KNOWN_CONSTRAINTS.md:40 |
| 41 | `- `bq query` 执行本项目建表/QA 脚本时显式指定 `--location=asia-east2`，避免无源表脚本或跨数据集 CTAS 使用错误 job 区域。` | 原文保留 | KNOWN_CONSTRAINTS.md:41 |
| 45 | `- 前复权价（`_qfq`）隐含未来除权信息，**不得作为训练特征**；技术指标/收益用后复权（`_hfq`）。` | 原文保留 | KNOWN_CONSTRAINTS.md:45 |
| 46 | `- 标签必须与特征时间错位：`t` 日特征 → 标签从 `t+1` 起算（入场价用 `t+1`）。` | 原文保留 | KNOWN_CONSTRAINTS.md:46 |
| 47 | `- universe 必须含退市股历史区间，并打标停牌/一字板/上市未满 N 日/ST 做样本掩码。` | 原文保留 | KNOWN_CONSTRAINTS.md:47 |
| 48 | `- 涨跌停价直接用 `stk_limit.up_limit/down_limit`（已按板块算好），不要自己按板块硬编码。` | 原文保留 | KNOWN_CONSTRAINTS.md:48 |
| 52 | `- 仓库、记忆文件、文档、日志中**绝不可出现**：BigQuery service account key、Tushare token、任何 API key / 凭据 / 个人隐私。` | 原文保留 | KNOWN_CONSTRAINTS.md:52 |
| 53 | `- 凭据通过环境变量 / 受信环境注入；`.gitignore` 已忽略 `*.key`/`credentials*.json`/`.env` 等。` | 原文保留 | KNOWN_CONSTRAINTS.md:53 |
| 54 | `- OQ-005 Cloud Run Jobs 部署只允许通过 Secret Manager 将 Tushare token 注入为运行时环境变量 `TUSHARE_TOKEN`；Tushare 官方或兼容 API 地址用 `TUSHARE_HTTP_URL` 运行时配置，...` | 原文保留 | KNOWN_CONSTRAINTS.md:54 |
| 58 | `- 需要代码在工作树中改，改完推 PR。` | 原文保留 | KNOWN_CONSTRAINTS.md:58 |
| 59 | `- owner 已明确授权：本项目执行过程中如缺失必要本机 / 运行依赖，Agent 可直接安装最小必要依赖并继续任务，无需再次询问。适用范围包括系统包、Python / Node 依赖、CLI 工具和运行时库（例如 LightGBM 所需 `libomp`）。该授权不覆盖...` | 原文保留 | KNOWN_CONSTRAINTS.md:59 |
| 60 | `- 调度运行代码、Composer DAG、告警配置、生产 QA 文件名 / task_id、Dataform action / tag 等运行时命名不得绑定 OQ、Phase、P0/P1 等阶段性编号；使用 `pipeline`、`ingestion`、`warehous...` | 原文保留 | KNOWN_CONSTRAINTS.md:60 |
| 61 | `- `dataform/definitions/**/*.sqlx` 是由 canonical `sql/` 和 `dataform/action_manifest.json` 生成的产物；任何修改 manifest 覆盖范围内 `sql/` 的 PR 都必须运行 `pyt...` | 原文保留 | KNOWN_CONSTRAINTS.md:61 |
| 62 | `- OQ-005 Workflows runtime 约束：Google Cloud Workflows `http.*` 单 step timeout 上限是 `1800s`，不能配置成 `3300` 或其他更大值；长耗时 BigQuery / Cloud Run 调用必...` | 原文保留 | KNOWN_CONSTRAINTS.md:62 |
| 63 | `- OQ-005 Workflows flag 约束：凡后续在 Workflow 内用 `== "true"` 判断的布尔开关（如 `pipeline_dry_run`、`scheduled_run`、`skip_ingestion`、`skip_downstream_re...` | 原文保留 | KNOWN_CONSTRAINTS.md:63 |
| 64 | `- DWD/DIM 物化后，下游一律查 DWD/DIM，不直接打 ODS。` | 原文保留 | KNOWN_CONSTRAINTS.md:64 |
| 65 | `- OQ-005 Cloud Run Job 模板仍默认 `--dry-run`，生产写入只能由 Composer 在 `ashare_pipeline_dry_run=false` 时显式传入 `--allow-gcs-write`，不得在脚本里硬编码 token 或绕过...` | 拆分重排：按句号拆为 18 个 bullet，原文句子顺序不变；未指针化、未删除操作性子句 | KNOWN_CONSTRAINTS.md:65-82 |
| 66 | `- `v_pipeline_refresh_missing` / `warehouse_refresh_missing` 只监控“应该触发下游刷新但完全没有 linked warehouse run”的异常。非交易日 scheduled skip（`pipeline_tas...` | 原文保留 | KNOWN_CONSTRAINTS.md:83 |
| 67 | `- OQ-005 live ingestion 成功/失败/空返回必须写入 `ashare_meta.ingestion_run` 和 `ashare_meta.ingestion_partition_status`；dry-run 与 `--skip-gcs-write`...` | 原文保留 | KNOWN_CONSTRAINTS.md:84 |
| 68 | `- 采集 Cloud Run 镜像（`asia-east2-docker.pkg.dev/data-aquarium/ashare/ingestion`）把 `scripts/ingestion/**` 与 `configs/ingestion/**`（含采集 manife...` | 原文保留 | KNOWN_CONSTRAINTS.md:85 |
| 69 | `- Composer DAG SQL 文件同步到 Composer bucket 的 `data/sql/`；不得把项目 SQL 树同步到 `dags/sql/`，避免 DAG 解析器把 SQL 文件树当作 DAG bundle 处理并造成 worker/DagBag 状态异常。` | 原文保留 | KNOWN_CONSTRAINTS.md:86 |
| 70 | `- 大范围回填建议分批（按年/季）跑并记录批次状态；P0 行情日常/全量默认仍写 2019+，但 owner 显式 `warehouse_mode=backfill` 可按历史训练窗口写入 2019 年以前 DWD/DWS 行，财务/事件从 2017 起。` | 原文保留 | KNOWN_CONSTRAINTS.md:87 |
| 71 | `- `dim_stock` 若遇到 latest `stock_basic` 缺失但 ODS daily 有历史记录的代码，应作为 `derived_from_daily` 兜底；若 `stock_basic.list_date` 晚于已存在的首个日线交易日，生命周期下限用...` | 原文保留 | KNOWN_CONSTRAINTS.md:88 |
| 72 | `- PR 合并后，若 owner 未要求保留工作分支，应删除已合并且不再使用的 `codex/*` 本地分支、对应远端分支，并移除为该分支创建的独立 `git worktree`，保持分支和工作树列表干净；若对应 worktree 仍有未提交或未合并改动，先暂停并请 own...` | 原文保留 | KNOWN_CONSTRAINTS.md:89 |
| 73 | `- 提交（commit/push）仅在用户明确要求时进行。` | 原文保留 | KNOWN_CONSTRAINTS.md:90 |
| 74 | `- 历史 SQL ledger `08_run_backtest.sql` 已退役并删除；当前 Strategy1 回测默认由 Cloud Run Python `ledger_exec_v1_lot100` 执行，继续遵守 `docs/prd/PRD_20260604_0...` | 原文保留 | KNOWN_CONSTRAINTS.md:91 |
| 75 | `- Ledger state resume 必须显式设置 `p_initial_state_mode='resume_from_backtest'`、`p_parent_backtest_id` 和 `p_state_as_of_date`；`p_predict_start...` | 原文保留 | KNOWN_CONSTRAINTS.md:92 |
| 76 | `- 2026-06-05 owner 决策：策略 1 后续执行层不再使用旧 BQML-only 训练 / 选型 / 预测路径、旧 SQL ledger fallback 或旧 SQL runner 调度器作为默认 / fallback / 新增开发路线。既有 BQML / ...` | 原文保留 | KNOWN_CONSTRAINTS.md:93 |
| 78 | `- 2026-06-05 owner 决策：策略 1 后续执行层不再使用旧 BQML-only 训练 / 选型 / 预测路径、旧 SQL ledger fallback 或旧 SQL runner 调度器作为默认 / fallback / 新增开发路线。既有 BQML / ...` | 原文保留 | KNOWN_CONSTRAINTS.md:95 |
| 79 | `- 2026-06-10 Strategy1 结构重构约束：当前 active/shared Strategy1 SQL 命名空间为 `sql/strategy1/**`，路径与参数契约由 `configs/strategy1/active_step_catalog.yml...` | 原文保留 | KNOWN_CONSTRAINTS.md:96 |
| 80 | `- 2026-06-10 Strategy1 Cloud Run entrypoint 迁移约束：五个正式 Cloud Run jobs 已迁移到 package entrypoint，job args 为 `quant_ashare.strategy1.train_pre...` | 原文保留 | KNOWN_CONSTRAINTS.md:97 |
| 81 | `- 2026-06-10 Strategy1 D2 research-first 约束：普通 Strategy1 runner、SQL runner、report、diagnosis、QA、acceptance/comparison 和 factor attribution...` | 原文保留 | KNOWN_CONSTRAINTS.md:98 |
| 82 | `- 2026-06-10 Strategy1 D3 promotion 约束：research 到 ADS 的正式发布只能通过显式 owner-approved promotion job `python -m scripts.strategy1.promote_resea...` | 拆分重排：按句号拆为 6 个 bullet，原文句子顺序不变；未指针化、未删除操作性子句 | KNOWN_CONSTRAINTS.md:99-104 |
| 83 | `- 2026-06-11 Strategy1 annual rolling official continuous 约束：2021-2026 正式结果不得拼接年度 fresh-run NAV，必须来自单一 continuous ledger（或另行验收的 resume-co...` | 原文保留 | KNOWN_CONSTRAINTS.md:105 |
| 84 | `- 2026-06-10 Strategy1 IAM 收敛决策：owner 已选择接受现状但保留流程约束。五个普通 Strategy1 Cloud Run jobs 暂继续使用 `241358486859-compute@developer.gserviceaccount....` | 原文保留 | KNOWN_CONSTRAINTS.md:106 |
| 86 | `- 2026-06-11 Strategy1 annual rolling source-panel / true-five-year 覆盖约束：PR #166 的 `2019-04-03` final-refit 起点 override 只能解释为“对齐当时 DWS / ...` | 拆分重排：按句号拆为 9 个 bullet，原文句子顺序不变；未指针化、未删除操作性子句 | KNOWN_CONSTRAINTS.md:108-116 |
| 87 | `- 2026-06-10 Strategy1 research schema migration 约束：`sql/research/01_research_strategy1_tables.sql` 是新环境 canonical contract，但由于使用 `CREATE...` | 原文保留 | KNOWN_CONSTRAINTS.md:117 |
| 88 | `- 策略 1 Cloud Run 训练回测执行器按 `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md` 实现：scikit-learn / 后续 Python 模型库替代策略模型训练 / 预测，不替代 BigQuery DWS/ADS...` | 原文保留 | KNOWN_CONSTRAINTS.md:118 |
| 89 | `- 2026-06-05 策略 1 Cloud Run 真实 smoke 约束：训练/预测 job 与回测/报告 job 至少按 16Gi/4CPU、`--max-retries=0` 部署；runtime service account 必须具备源数据读取、BigQuer...` | 原文保留 | KNOWN_CONSTRAINTS.md:119 |
| 90 | `- 2026-06-05 sklearn native search 约束：当前 `asia-east2` Cloud Run 配额已提升到约 40 vCPU / 160Gi，`strategy1-train-candidate-fanout-job` 可按 `1 CPU ...` | 原文保留 | KNOWN_CONSTRAINTS.md:120 |
| 91 | `- 2026-06-06 PRD04 LightGBM search 真实资源约束：LightGBM candidate smoke 后，40 候选不再按 `40 * 1 vCPU / 4Gi` 全并发执行，当前 P0 运行口径为 `candidate_count=40`、...` | 原文保留 | KNOWN_CONSTRAINTS.md:121 |
| 92 | `- 2026-06-06 策略 1 验收门 v2 约束：`configs/strategy1/model_acceptance_contract_v2.yml` 是 v2 阈值、边界和指标定义唯一事实来源；v2 诊断、后续 Python acceptance 和 `22_q...` | 原文保留 | KNOWN_CONSTRAINTS.md:122 |
| 93 | `- 2026-06-06 策略 1 production acceptance 的交易执行约束：后续 v2 accepted production baseline 必须使用 Cloud Run Python lot-aware ledger（当前实现目标版本 `ledge...` | 原文保留 | KNOWN_CONSTRAINTS.md:123 |
| 94 | `- 2026-06-07 fixed-prediction / portfolio-only runner QA 约束：`10_qa_runner_outputs.sql` 的 split 参数必须匹配 source `ads_ml_training_panel_daily...` | 原文保留 | KNOWN_CONSTRAINTS.md:124 |
| 95 | `- 2026-06-06 策略 1 尾部风险 P0 诊断约束：`scripts/strategy1/analyze_tail_risk.py` 只能只读 `ashare_ads` / `ashare_dwd` / `ashare_dim` 并写 local/GCS `tai...` | 原文保留 | KNOWN_CONSTRAINTS.md:125 |
| 96 | `- 2026-06-06 策略 1 尾部风险 P1 profile 约束：`tail_risk_profile_id` 默认必须是 `diagnostic_only`，不得改变选股；只有 manifest / experiment 显式设置 `individual_risk...` | 拆分重排：按句号拆为 7 个 bullet，原文句子顺序不变；未指针化、未删除操作性子句 | KNOWN_CONSTRAINTS.md:126-132 |
| 97 | `- sklearn native search 的 36 个 candidate task 可并发训练，但 TopK select/register/predict 会同时写 `ads_model_registry` / prediction 等 ADS 表；BigQuer...` | 原文保留 | KNOWN_CONSTRAINTS.md:133 |
| 98 | `- **历史 BQML runner 并发事故记录，仅作审计，不再作为修复 runbook**（2026-06-02 实跑事故教训）：` | 原文保留 | KNOWN_CONSTRAINTS.md:134 |
| 99 | `- 旧 `02_train_bqml_logistic_candidates.sql` 曾用 BigQuery ML `CREATE OR REPLACE MODEL` 顺序训练候选；同一 run_id 的两个 `02` 执行重叠会触发 `Concurrent model ...` | 原文保留 | KNOWN_CONSTRAINTS.md:135 |
| 100 | `- 事故经过：误判第一个 `02`「被拒绝/失败」而重跑，导致两执行重叠；随后又依据过期 `bq ls` 快照删除仍在运行 job 正在训练的模型，造成 registry 指向已删模型。` | 原文保留 | KNOWN_CONSTRAINTS.md:136 |
| 101 | `- 现行约束：BQML-only `02/03/04` 已删除，禁止再按“重跑 02”修复 registry / 模型不一致。历史 BQML 结果只作为 ADS / GCS / 文档审计引用；若未来确需恢复或重建 BQML 历史对象，必须另写 PRD 并经 owner 明确...` | 原文保留 | KNOWN_CONSTRAINTS.md:137 |
| 102 | `- **旧 OQ-010 SQL/BQML 并发调度器约束已退役，仅作历史审计**：`scripts/strategy1/run_oq010_experiments.py`、BQML-only `02/03/04` 与 SQL ledger fallback `08_run...` | 原文保留 | KNOWN_CONSTRAINTS.md:138 |
| 106 | `- `airflow_monitoring` 是 Cloud Composer 托管的环境健康 DAG，不由仓库 DAG 代码控制；在 Composer 仍存在时不能靠改 repo 把它降频到每小时以内。要消除这部分 run/底座费用，必须 cutover 后删除 Comp...` | 原文保留 | KNOWN_CONSTRAINTS.md:142 |
| 107 | `- 2026-06-08 起，生产业务调度唯一入口是 `Cloud Scheduler -> Cloud Workflows`：`ashare-ods-ingestion-daily`（`0 20 * * *`）负责日常 ODS + child warehouse refr...` | 原文保留 | KNOWN_CONSTRAINTS.md:143 |
| 108 | `- `ashare-composer` 环境已于 2026-06-08 删除完成；后续若需要重新引入 Composer，必须视为新的架构决策，而不是当前 OQ-005 路径上的默认运维动作。` | 原文保留 | KNOWN_CONSTRAINTS.md:144 |
| 109 | `- `orchestration/composer/**` 现仅保留为历史审计快照；当前生产部署、调度变更、runbook 更新和 smoke 路径都应落在 `orchestration/workflows/**`，不再向 Composer DAG / README 叠加新...` | 原文保留 | KNOWN_CONSTRAINTS.md:145 |
| 110 | `- `ashare_pipeline_alert_checker` 在迁移期与迁移后统一按“最多每小时 1 次”设计：schedule `0 * * * *`，lookback `70` 分钟，heartbeat 缺失告警窗口 `120` 分钟，避免 1 小时 cadenc...` | 原文保留 | KNOWN_CONSTRAINTS.md:146 |
| 111 | `- 2026-06-08 真实 cutover 后，生产定时入口已改为 Cloud Scheduler jobs `ashare-pipeline-alert-checker` 与 `ashare-ods-ingestion-daily`，两者统一由 `ashare-sch...` | 原文保留 | KNOWN_CONSTRAINTS.md:147 |
| 112 | `- OQ-005 scheduler least-privilege 约束：`ashare-workflows-runtime@data-aquarium.iam.gserviceaccount.com` 不应再持有项目级 `roles/run.developer`。它在 ...` | 原文保留 | KNOWN_CONSTRAINTS.md:148 |
| 113 | `- `ashare-pipeline-control` service 上的 `roles/run.invoker`` | 原文保留 | KNOWN_CONSTRAINTS.md:149 |
| 114 | `- `ashare-ingest-current-scope` Cloud Run Job 上的 `roles/run.jobsExecutorWithOverrides`，因为 workflow 会用 overrides 传入生产参数` | 原文保留 | KNOWN_CONSTRAINTS.md:150 |
| 115 | `- 项目级 `roles/run.viewer`，用于读取 Cloud Run operation / execution 状态；没有 `run.operations.get` 时，job 启动后会在 operation polling 阶段 403` | 原文保留 | KNOWN_CONSTRAINTS.md:151 |
| 117 | `- OQ-005 cutover 顺序约束：cutover helper 不得先 enable Scheduler jobs、后 pause Composer。安全顺序必须是：先创建/更新 Scheduler jobs 为 `PAUSED`，再 pause Composer...` | 原文保留 | KNOWN_CONSTRAINTS.md:153 |
| 118 | `- `ashare_warehouse_full_rebuild` 的 Workflows 路径现已改为 `ashare-pipeline-control` 服务端 async `submit + poll`，不能再退回同步 `job.result()`；否则会重新暴露 C...` | 原文保留 | KNOWN_CONSTRAINTS.md:154 |
| 119 | `- `ashare_warehouse_full_rebuild` 的 async poll 循环本身也必须续租共享写锁，不能只在每个 BigQuery step 结束后 heartbeat；否则单个 step 时长超过 lease 时，会被 stale-lock recl...` | 原文保留 | KNOWN_CONSTRAINTS.md:155 |
| 120 | `- `ashare-pipeline-control` 的 BigQuery poll 重试当前使用同步退避 `time.sleep`，一次 `/v1/tasks/bigquery/poll` 最坏会因 `get_job(...)` 内部重试额外阻塞约 `15s`（`1+2...` | 原文保留 | KNOWN_CONSTRAINTS.md:156 |
| 121 | `- 标准 `deploy_workflows.sh` 仍默认不部署 `ashare_warehouse_full_rebuild`；必须显式 `DEPLOY_FULL_REBUILD=true` 才会下发该 workflow。即使已部署，它也只允许手工触发，且必须显式传入 ...` | 原文保留 | KNOWN_CONSTRAINTS.md:157 |
| 122 | `- 启用 `Cloud Scheduler -> ashare-pipeline-control /v1/tasks/alert-check` 时，必须同步 pause / delete Composer DAG `ashare_pipeline_alert_checker...` | 原文保留 | KNOWN_CONSTRAINTS.md:158 |
