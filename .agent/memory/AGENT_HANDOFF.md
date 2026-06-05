# Agent 交接（Agent Handoff）

本文件保存供后续 Agent 使用的最新交接记录。新交接用 `templates/HANDOFF_TEMPLATE.md` 追加到底部，并同步刷新下面的「当前交接摘要」。

> **语言约定（2026-06-01 起）**：新增交接条目一律用中文撰写；下方此前的英文历史条目保留原样作为记录，不回译。

## 当前交接摘要

**OQ-005 daily_current 20 日窗口与非交易日口径修复（2026-06-05）**：工作树 `/private/tmp/quant-ashare-oq005-daily-window-hardening`，分支 `codex/oq005-daily-window-hardening`。本分支从最新 `origin/main` 补入本地 `5b62895` 的 daily_current 20 个交易日窗口和 QA-WIN-16/17/18 估值覆盖检查，并进一步硬化非交易日口径：`daily_current` 的 `date_to` / `business_date` 会先归一到不晚于请求日期的最近 SSE 开市日，`backfill` 保持显式日期。已同步 `sql/README.md`、`orchestration/composer/README.md`、`ARCHITECTURE_MEMORY.md`、`KNOWN_CONSTRAINTS.md`、`OPEN_QUESTIONS.md`、`TODO.md` 和 `IMPLEMENTATION_STATUS.md`，将 OQ-005 状态从“尚未部署 / 待 smoke”修正为已完成 Composer DAG/SQL 部署验收、20 日估值缺口回填和 backfill / qa_only / daily_current smoke；OQ-005 仍 open，剩余 Dataform、告警、补跑和运维观测闭环。验证：窗口 SQL / QA 对 `daily_current business_date=2026-06-06` 和 `backfill 2026-06-03..2026-06-04` 的 BigQuery dry-run 均通过；只读窗口计算确认 `2026-06-06` 归一为 `2026-06-05`，窗口起点 `2026-05-11`，开市日数 20。尚未部署本分支到 Composer，合并后需同步 `sql/` 到 Composer bucket。

**策略 1 scikit-learn native 模型实验 PRD（2026-06-05）**：工作树 `/Users/luna/Desktop/git/quant-ashare-sklearn-native-prd`，分支 `codex/prd-sklearn-native-experiment`。新增 `docs/prd/PRD_20260605_03_策略1Sklearn模型实验.md`，定义 Cloud Run sklearn backend 在 BQML parity 未通过后的新 baseline 实验方案：固定当前最优交易口径 `pv_fin_quality + 30/5% + biweekly + 5d`，用 task fan-out 并发训练 36 个 sklearn 原生 LogisticRegression 候选，valid-only 选 Top 5 进入完整预测/组合/回测/报告/诊断，并通过 native acceptance gate 决定是否建立 `cloud_run_sklearn_native_baseline_v1`。BQML baseline 保留为历史 reference / fallback；现有 Cloud Run parity gate 不删除，只是不再作为 native baseline 的 hard gate。PR #69 review 后已加固：训练窗口钉死为 `2019-04-03` 至 `2023-12-31`；accepted 候选必须 `valid_signal_status=stable`，valid 弱但 test 过门只能 `needs_more_evidence`；跨模型族复用 2025 test 必须记录 `test_reuse_wave_no` / owner 批准，超过 3 个波次后必须新增最终 holdout 证据。本次只写 PRD 和记忆/TODO，未实现代码、未部署 Cloud Run Job、未执行 BigQuery。

**策略 1 Cloud Run task fan-out 正式全量验收（2026-06-05）**：工作树 `/Users/luna/Desktop/git/quant-ashare-ledger-p1`，`main` 分支。已先将 `strategy1-prepare-matrix-job` 从 `4 CPU / 16Gi` 提升到 `8 CPU / 32Gi`，再用正式全量 run `s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01` / `bt_s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01` 跑完整 Cloud Run task fan-out 链路。训练面板 3,055,781 行（train 1,999,065 / valid 476,346 / test 580,370）；`cloudrun_prepare_matrix` 4m10s 成功，5 个 candidate task 全部 succeeded，`cloudrun_select_register_predict`、`cloudrun_backtest_report` succeeded；`backtest_report` 内部完成 `05-09`、Python `ledger_exec_v1`、报告上传、`10`、diagnosis 和 `12`。`16_qa_cloudrun_runner_outputs.sql` 在 smoke/evidence 模式通过，`17_qa_cloudrun_orchestrator_status.sql` 通过；正式 `16` parity 在 `QA-CR-4` 失败，sklearn selected model `elastic_c_1_l1_0_5` valid RankIC `0.06665` 低于 BQML reference `0.09676`，`model_quality_status=model_quality_not_equivalent`。回测结果 total_return `46.29%`、excess_return `17.28%` vs `000852.SH`、Sharpe `1.111`、max_drawdown `-13.94%`，报告 URI `gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01/backtest_id=bt_s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01`。结论：Cloud Run 执行链路和 full-panel prepare OOM 已收口，但不能声明 sklearn 正式等价替代 BQML。

**策略 1 Cloud Run task fan-out 真实 smoke（2026-06-05）**：工作树 `/Users/luna/Desktop/git/quant-ashare-ledger-p1`，分支 `codex/fix-task-fanout-force-replace`。已构建并部署修复镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner@sha256:8cc8470014cb3b54272d4c7f47afb396d91cf7b97967f0c3ffab947f7432c38a` 到 `strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`。当前资源：prepare/select/backtest `4 CPU / 16Gi`，candidate task `1 CPU / 4Gi`；因 `asia-east2` 当前 20 vCPU / 40Gi 配额，candidate job 设置 `parallelism=10`。低成本 smoke `run_id=s1_cloudrun_taskfanout_smoke_20260605_03` / `backtest_id=bt_s1_cloudrun_taskfanout_smoke_20260605_03` 已跑通：`cloudrun_prepare_matrix`、5 个 candidate task、`cloudrun_select_register_predict`、`cloudrun_backtest_report` 全部 succeeded，`10`/`12`/`16`/`17` QA 全部通过。修复内容：orchestrator 不再把 `--force-replace` 传给 `prepare_matrix`；`10` QA 的 split 边界改为参数化；`12` QA-DIAG-6 改用训练面板 `tp.split_tag` 而非 DWS 固定 split。产物：matrix URI `gs://ashare-artifacts/models/strategy1/ml_pv_clf_v0/run_id=s1_cloudrun_taskfanout_smoke_20260605_03/matrix_id=s1_cloudrun_taskfanout_smoke_20260605_03__matrix_5294c2780a86`，model URI `gs://ashare-artifacts/models/strategy1/ml_pv_clf_v0/run_id=s1_cloudrun_taskfanout_smoke_20260605_03/model_id=s1_sklearn_s1_cloudrun_taskfanout_smoke_20260605_03__l2_c_10`，report URI `gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_cloudrun_taskfanout_smoke_20260605_03/backtest_id=bt_s1_cloudrun_taskfanout_smoke_20260605_03`。本次 smoke 证明 task fan-out 执行链路可用；正式替代 BQML 仍需 sklearn parity passed 或 owner 接受新 Cloud Run baseline。

**策略 1 Cloud Run 轻量 Task 并发实现分支（2026-06-05）**：工作树 `/Users/luna/Desktop/git/quant-ashare-cloudrun-task-fanout-impl`，分支 `codex/cloudrun-task-fanout`。已按 PRD-20260605-02 实现 P0 task fan-out 训练链路：`prepare_matrix.py` 一次性读取 `ads_ml_training_panel_daily` 并输出 GCS frozen matrix / work units / feature schema / preprocess stats / BigQuery job audit；`train_candidate_task.py` 通过 `CLOUD_RUN_TASK_INDEX + TASK_INDEX_OFFSET` 训练单个 candidate 并写 candidate artifact；`select_register_predict.py` 汇总 candidate artifact、校验 hash、选型、写 selected registry / prediction；`orchestrate_experiments.py` 新增 `--train-mode task_fanout` 和 `--candidate-parallelism`，可在 owner 不限流时单批 `--tasks=N` 全并发，显式限流时分批执行。PR #64 review follow-up 已修 QA-TASK-8：`select_register_predict` 通过 `JOBS_BY_PROJECT` 写入真实 `candidate_task_bq_*` 审计计数，`16_qa_cloudrun_runner_outputs.sql` 也直接查 `JOBS_BY_PROJECT` 兜底断言，不再依赖硬编码 0；后续 nit 已补齐 SQL 版 run_id label 归一化，使其与 Python `bq_label_value()` 完全一致。`17_qa_cloudrun_orchestrator_status.sql` 已补 task fan-out 状态 QA，运行手册和 README 已同步。验证：Python py_compile、入口 dry-run、orchestrator `--tasks` 计划 dry-run、`16`/`17` BigQuery dry-run、实际 Python INFORMATION_SCHEMA audit 查询、`git diff --check`、`gcloud run jobs execute --help` 参数核验均通过。该条为 PR #64 合并前 dry-run 阶段记录；真实 task fan-out smoke 见上一条。

**策略 1 Cloud Run 轻量 Task 并发 PRD（2026-06-05）**：新增 `docs/prd/PRD_20260605_02_策略1CloudRun轻量Task并发.md`，作为 Cloud Run 训练回测执行器的训练侧并发补充方案。PRD 固化 `prepare_matrix -> train_candidate_fanout --tasks=N --candidate-parallelism=M -> select_register_predict -> backtest_report` 链路：`prepare_matrix` 只做一次 BigQuery 训练面板读取并在 GCS 生成 frozen matrix / work units / feature schema / preprocess stats；`strategy1-train-candidate-fanout-job` 使用 Cloud Run Jobs task 原生机制，每个 task 通过 `CLOUD_RUN_TASK_INDEX` 训练一个 candidate / experiment work unit；`select_register_predict` 汇总全部候选、校验 hash、选型并统一写 registry / prediction。默认并发语义为 owner 不设限时单批全并发，35/100 个 work units 就启动 35/100 个并发 task；owner 可通过显式 `--candidate-parallelism` 让 orchestrator 分批限流。PR #63 review follow-up 已采纳：frozen features 明确为 `prepare_matrix` 输出的已预处理矩阵，candidate task 不重新预处理；QA-TASK-8 补 BigQuery job labels / audit 机制；candidate task 只读 train/valid，不读 predict features。候选 task 默认小规格 1 vCPU / 2-4Gi，避免用 4CPU/16Gi 高配 execution 跑单候选造成 CPU 浪费。本次只写 PRD，未实现代码、未部署 Cloud Run Job、未执行 BigQuery。

**策略 1 Cloud Run 真实 smoke（2026-06-05）**：Cloud Run runner 与 orchestrator 状态/锁增强已进入 `main` 后，完成真实 Cloud Run/BQ smoke。已部署镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner@sha256:6564434f9f216aec6c86cae3923bc44450c3ca26ead14a248b05ca77087d8ead` 到 `strategy1-train-predict-job` / `strategy1-backtest-report-job`，job 配置 16Gi/4CPU/`--max-retries=0`；runtime service account 已具备 `ashare_ads` 写权限。smoke `cloudrun_smoke_pvfq_n30_bw_h5` 跑通 `run_id=s1_cloudrun_sklearn_smoke_20260604_02` / `backtest_id=bt_s1_cloudrun_sklearn_smoke_20260604_02`，train/predict execution `strategy1-train-predict-job-s5725`、backtest/report execution `strategy1-backtest-report-job-6fzvr` 均成功，prediction 1,056,716 行，报告 uploaded 到 `gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_cloudrun_sklearn_smoke_20260604_02/backtest_id=bt_s1_cloudrun_sklearn_smoke_20260604_02`，`16_qa_cloudrun_runner_outputs.sql`（smoke 模式 `p_require_model_quality_parity_passed=FALSE`）和 `17_qa_cloudrun_orchestrator_status.sql` 通过。回测指标：total_return 46.29%、Sharpe 1.111、max_drawdown -13.94%、excess_return 17.28% vs `000852.SH`。注意：sklearn vs BQML parity 未通过，当前 `model_quality_status=model_quality_not_equivalent`，只能证明 Cloud Run 链路可运行，不能声明 sklearn 已等价替代 BQML baseline。

**OQ-005 生产采集状态（2026-06-05）**：当前每日生产采集只覆盖 SQL 实际消费的 14 张 ODS；`ashare-ingest-current-scope` 单 execution 入口已部署，Cloud Run Jobs 走 Direct VPC egress + Cloud NAT + 区域静态 IP 固定出口，Composer DAG 使用 default Celery queue。纯 scheduler smoke `manual_oq005_scheduler_smoke_default_queue_20260604_01` 成功；`2026-05-20` 至 `2026-06-03` SSE 开市日生产 GCS 回填全部成功并逐日通过 `sql/qa/09_ods_daily_partition_readiness.sql`；`manual_oq005_daily_prod_20260604_01` 已按生产路径写入 `2026-06-04` 并成功完成 readiness。OQ-005 仍未关闭，因为 Phase 2.0 仍需部署 smoke / `skip_ingestion`、`qa_only`、`full_rebuild_compat` 验收，后续还需 Dataform 生产链路、增量影响窗口、告警、补跑和运维观测闭环。

**PR #58 review follow-up**：live ingestion 已补 `ashare_meta.ingestion_run` 与 `ingestion_partition_status` 写入，dry-run/API 只读 smoke 不写 meta；`ingestion_partition_status.endpoint` 存 `partition_endpoint`，避免同 API 多 variant 串状态。raw GCS canonical 路径固定为 `api=<api>/endpoint=<partition_endpoint>/partition_date=...`，不使用 `api=tushare`；2026-06-04 已用 BigQuery `INFORMATION_SCHEMA.TABLE_OPTIONS` 复核当前 14 张 ODS 与 10 张 schema repair 表 source URI。GCS publish 覆盖正式 object 不做 write-once backup，这是采集重跑口径；历史可回滚回填留后续独立开关/流程。

`quant-ashare` 已完成 P0 DIM/DWD 物化、OQ-004 指数基准口径、策略 1 DWS/ADS、策略 1 BigQuery ML runner 端到端实跑、OQ-006 单位契约、OQ-003 财务三表 DWD/DWS、OQ-010 交易成本 profile、策略 1 中文报告与归因分析、策略 1 报告 GCS uploaded 模式、策略 1 模型质量诊断 PRD 及实现、策略 1 valid/test live-available 预测池口径修正 PRD 及实现，以及策略 1 分数方向校准 PRD 及实现。2026-06-02 已创建 `gs://ashare-artifacts`（`ASIA-EAST2`）、配置本机 ADC（quota project=`data-aquarium`）、去掉 `--skip-gcs-upload` 重跑 `render_report.py`，ADS 已回写 `report_upload_status=uploaded` 和真实 `report_uri`，`sql/ml/strategy1/10_qa_runner_outputs.sql` 全部通过。诊断 QA（`12`）已全部通过：PR #27/28 修复 `split_tag` 歧义（QA-DIAG-6 valid/test 日数校验通过），PR #29/30 实现 live-available 预测池口径（QA-POOL-1~6 全部通过），PR #32 实现 score orientation 校准（QA-ORIENT-DIAG-1 通过）。2026-06-03 已完成 livepool reverse-score shadow run（`s1_bqml_livepool_revscore_20260603_01`），验证反向后的 valid/test RankIC 转正且回测从亏损转为正收益（total_return=0.2787）；oriented run（`s1_bqml_livepool_oriented_20260603_01`）的 `12` QA 全部通过。已新增 `data_audit/` ODS/GCS 数据审查入口和 `data_audit/reports/` 报告目录，提示词限定本次只审查 2019-01-01 及之后的数据、只读不补数据，并要求审查 Agent 自行编写和维护审查脚本；提示词已补 Tushare 官方文档链接、API 返回行数打满单次上限时的截断风险检查，以及按 endpoint/主题拆脚本规则。OQ-005 GCP 数据流水线 PRD 已新增并按 owner 反馈收敛为陈述性目标实现方案：长期方案为 Cloud Run Jobs 采集 Tushare/Tinyshare→GCS Parquet，Dataform / BigQuery Studio pipeline 做 ODS→DIM/DWD/DWS/ADS，Cloud Composer 做全流程编排；首批每日生产采集只覆盖当前实际消费的 14 张 ODS，当前未消费 endpoint 进入后续接入池；PR #39 review 两条低优先级建议已补入财务 empty-return 口径和 Phase 1 Cloud Scheduler / Composer 触发入口；PR #42 分支已实现 Phase 0 采集 manifest、schema contract、meta 表 DDL 与采集脚本 stub，并整合 PR #44/#46 review 修复。已新增 OQ-012 ODS 外部表 Parquet schema 修复 PRD：10 张 2019+ schema mismatch 外部表按 GCS 原文件 schema-preserving rewrite 方案修复，API 重拉只作补救路径，当前 P0 源表 `ods_tushare_stk_limit` 优先；PR #43 已实现 schema contract、修复/验证脚本、QA SQL 和执行 README，并按 review 补齐 INT->FLOAT64 fail-closed、null count 阻断、BQ staging 行数/列可读验证与 staging 清理；P0 `stk_limit` 仍待在 BigQuery 实际执行修复并验证。核心规范保持：`sec_code` 主键、单位元/股、`ann_date_eff`/`visible_trade_date` PIT、后复权 `_hfq`、行业归属时点区间、血缘与版本字段、按月分区 + 聚簇；当前阶段先把 2019+ 数据做正确，2019 年以前正式样本/明细是下一步。

**已物化表**：`data-aquarium.ashare_meta` 下 `ods_field_unit_map`；`data-aquarium.ashare_dim` 下 `dim_trade_calendar`、`dim_stock`、`dim_stock_name_hist`、`dim_index`；`data-aquarium.ashare_dwd` 下 `dwd_stock_eod_price`、`dwd_stock_eod_valuation`、`dwd_fin_indicator`、`dwd_fin_indicator_latest`、`dwd_index_eod`，以及 OQ-003 财务三大报表 `dwd_fin_income`/`dwd_fin_balancesheet`/`dwd_fin_cashflow` 及各自 `_latest`（PR #13）；`data-aquarium.ashare_dws` 下策略 1 六表（universe、价格特征、估值特征、标签、特征宽表、样本表）和 `dws_stock_feature_fin_daily`（默认合并口径 PIT 财务特征，PR #13）；`data-aquarium.ashare_ads` 下 11 张训练/预测/组合/回测/监控契约表。PR #9 合并后的 `dim_stock` 依赖链已在 2026-06-02 重建：`dim_stock`、`dwd_stock_eod_price`、策略 1 DWS 六表和 ADS 契约表均已刷新，`sql/metadata/01_p0_table_column_descriptions.sql` 已执行，`sql/qa/01_p0_smoke_checks.sql` 与 `sql/qa/02_strategy1_dws_ads_checks.sql` 均通过；`sql/qa/03_oq004_index_checks.sql` 近期通过。二轮评审发现已修复：盘中临停不再误标全天停牌，财务 latest 改为 `update_flag DESC` 优先。P0 DIM/DWD 字段说明缺失数为 0。

**评审协议（2026-06-01 更新）**：评审已提交代码/SQL 或设计文档时，GitHub PR review 默认写 PR comment；一条写不下拆多条。只有 owner 明确要求或无 PR comment 承载面时，才另写 `docs/reviews/` 评审文档。评审只读——不擅改被评审对象、不把发现直接写进 `.agent/memory/**`/`TODO.md`，发现是否转 OQ/TODO/决策由 owner 定（AGENTS.md §六 / DECISION-20260601-03）。历史 `docs/reviews/P0-建表SQL-review.md` 等评审文档保留作审计记录。

**重要执行结果**：`dim_stock` 5,853 行，其中 326 个退市股使用 ODS `stock_basic_delist_date`；`dwd_stock_eod_price` 8,506,688 行；`dwd_stock_eod_valuation` 8,452,073 行；`dwd_fin_indicator` 332,960 行；`dwd_fin_indicator_latest` 198,030 行；`dim_index` 7 行；`dwd_index_eod` 11,922 行，其中 8,899 行有 `index_dailybasic` 估值/市值/股本字段，且沪深300已归一为 `sec_code='000300.SH'` / `source_sec_code='399300.SZ'`。`dim_index` 当前记录：SSE50、CSI300、STAR50、CSI1000、CSI500、深证成指、创业板指；`000852.SH` 可作收益 benchmark，但 `has_dailybasic=FALSE`。策略 1 DWS 行数：universe 8,506,688 行、价格特征 8,506,688 行、估值特征 8,452,073 行、标签 8,506,688 行、特征宽表 8,506,688 行、样本表 8,506,688 行（默认可训练 3,274,084 行）。上游已修复 `index_dailybasic` Parquet 类型问题，OQ-009 已关闭；STAR50/CSI1000 因 ODS 无 dailybasic endpoint 仍为空。2026-06-02 已应用 PR #9 的 ODS 正式退市日口径并完成依赖重建。

**DWS/ADS 设计与已落地范围**：P0 DWS 设计包含 `dws_stock_universe_daily`、价格/估值/财务特征、`dws_market_state_daily`、`dws_stock_label_daily`、`dws_stock_feature_daily_v0`、`dws_stock_sample_daily`；当前策略 1 已落地 universe、价格/估值特征、open-to-close 标签（rank/xs return 按默认 universe 截面计算）、特征宽表、样本表，以及 OQ-003 财务特征 `dws_stock_feature_fin_daily`；市场状态 `dws_market_state_daily` 待补。财务特征口径 PRD 已采纳、关闭并实现 OQ-003（PR #13）：P0 默认消费合并报表 `report_type='1'`，三大报表 DWD（`income/balancesheet/cashflow` + `_latest`）保留 `report_type`/`report_caliber`/`is_default_report_caliber`，`dws_stock_feature_fin_daily` 默认只过滤默认口径（口径契约 + `has_fin_*` 掩码），已物化并通过 `sql/qa/04_finance_caliber_checks.sql`，并按 OQ-006 单位契约补全 `ods_field_unit_map` 财务字段、跑通 `sql/qa/05_oq006_unit_checks.sql`。PR #4 comment 的 P1/P2 已跟进：`label_valid` 语义说明、去冗余 JOIN、最早可训练样本日 QA、DWD 字段名文档同步。P1 行业路径已可落地：`dim_stock_sw_industry_hist` 使用 `index_member_all`，`dim_stock_ci_industry_hist` 使用 `ci_index_member`，历史 join 用 `in_date/out_date`，`is_new` 仅标当前归属。P0 ADS 表契约已落地。策略 1 PRD 名称为 `ml_pv_clf_v0`；首个基线默认股票池仅沪深主板（`SSE_MAIN` / `SZSE_MAIN`），不含北交所、创业板、科创板；runner 设计 `docs/策略1-ml_pv_clf_v0-runner设计.md`、runner 实现 PRD `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md` 和 runner SQL 已完成，执行路径为 BigQuery ML + SQL：训练面板、BQML model object、预测、候选、组合、订单、回测、监控均写既有 ADS 表。**runner 已于 PR #12 端到端实跑并通过全部 QA**（08 已重写为账户级 ledger，详见本文件末尾 2026-06-02 交接条目与摘要顶部）。

**下一步（P0/P1）**：score orientation 校准已实现并验证（PR #32），live-available 预测池口径已实现并验证（PR #29/30），诊断 QA 全部通过。`docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md` 已由 PR #35 合并进入 `main`；OQ-010 首轮实验 runner 参数化、manifest、对比报告脚本、portfolio-only `prediction_run_id` 复用预测源路径和 horizon-aware 诊断/QA 已由 PR #37 合并进入 `main`。2026-06-04 PR #47 合并后 Stage C 已重跑通过；随后补齐 3*2*2*2 全因子网格缺失的 19 个组合，最终 24 个组合均通过 `12_qa_model_diagnosis_outputs`；同 stage dependency batching 与诊断状态语义修复已由 PR #48 合入 `main`。当前最优组合 `pv_fin_quality + 30/5% + biweekly + 5d` 已完成正式基线重训 run `s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01` / backtest `bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01`（2024-01-02 至 2025-12-31，benchmark=`000852.SH`，total_return=41.10%、excess_return=12.09%、Sharpe=1.043、max_drawdown=-14.48%，报告和诊断均 uploaded 到 GCS）。2026-06-04 已新增并改造 `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`、`docs/prd/PRD_20260604_02_策略1月度滚动重训.md` 和 `docs/prd/PRD_20260604_03_策略1因子贡献度分析.md`；因子贡献度分析 P0 已实现：新增独立脚本、`14_qa_factor_attribution_outputs.sql`、主报告摘要接入和 README 说明，正式 baseline local-only 生成 `factor_attribution/` artifact，覆盖 55 个非截距特征、13 个因子组，`14` QA 全部通过。Ledger v1 P0 已进入 `main`（commit `602baea`）；Ledger v1 P2 state resume 已在 `codex/ledger-state-resume` 实现，且 PR #54 review follow-up 已修复 biweekly resume QA anchor 强制、resume 首日 `daily_return` 父 NAV 锚点和 `15` 一致性 QA 的 daily_return 覆盖；`bt_ledger_resume_smoke_20260604_01` 已重新跑通短区间 `08`/`09`/本地报告/`10` resume QA。2026-06-04 已新增 `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`，定义 Cloud Run Jobs + scikit-learn logistic 训练 / 预测 + Python `ledger_exec_v1` 回测；PR #55 review follow-up 已补 sklearn vs BQML 模型质量对等门槛、P0 默认 `class_weight=None`、sklearn 正则网格不得直接翻译 BQML L1/L2；默认并发数为 manifest 可执行实验数量，owner 可显式限流，既有 BQML runner 保留为 reference / fallback。Cloud Run runner 首版已在 `codex/implement-strategy1-cloudrun-runner` 实现并通过本地 dry-run / py_compile / BigQuery dry-run；真实 Cloud Run/BQ smoke、sklearn vs BQML parity 和 Python ledger vs SQL ledger 等价验收仍待做。后续建议 review/merge Cloud Run runner PR，再 review/merge P2 resume PR；随后跑 Ledger v1 P1 fixed-model 扩展回测至 `2026-04-30` 并做 full fresh vs resume segment 一致性验收；月度滚动重训应复用 Cloud Run train/predict 底座。P1 再做三大报表单季 `q_*` 派生、行业/资金/事件特征扩展。关键参数：`@dwd_start_date = DATE '2019-01-01'`、`@fin_start_period = '20170101'`、`@lookback_start_date = DATE '2018-01-01'` 默认；后续应把 lookback 改为按最大滚动窗口计算，并决定是否补 lookback-capable 价格构建输入（OQ-011）。

**待 owner 确认 / 执行**：OQ-005 生产 GCS 采集已启用并完成 `2026-05-20` 至 `2026-06-04` 当前范围数据写入/日分区 readiness 验证；后续仍需完成完整 ODS→ADS 转换、Dataform/BigQuery SQL 生产链路、告警、补跑和运维观测验收。OQ-010 正式基线默认参数是否采纳；Ledger v1 P2 resume PR 是否合并，以及后续 P1 2026 fixed-model 扩展回测 / resume consistency 验收 / 月度滚动重训；是否补 lookback-capable 价格构建输入以填满 2019-01 起 60 日窗口（OQ-011）；OQ-012 修复脚本与 QA 待合并后实际执行 P0 `stk_limit` 修复并验证。OQ-001/OQ-003/OQ-004/OQ-006/OQ-007 已关闭。

**TODO / OQ 维护约定**：`TODO.md` 只保留下一步可执行事项和少量近期完成项；待 owner 决策的问题以 `.agent/memory/OPEN_QUESTIONS.md` 为唯一来源，TODO 仅引用 OQ 编号和对应行动。

**PR #45 最新修复（2026-06-03）**：OQ-010 并发调度 Phase 1 review follow-up 已修复：`run_oq010_experiments.py` 的 stale lock reclaim、heartbeat 和 release 均使用 GCS object generation 条件操作，避免并发调度器误删新锁；SQL `DECLARE p_* DEFAULT` 参数注入改为强校验，dry-run 会预检可执行实验，禁止静默沿用 SQL 默认 `run_id` / `backtest_id`；锁获取后的释放统一进 `finally`，heartbeat 线程停止后才写 `succeeded` / `failed`；状态表 DDL 改为 `CREATE TABLE IF NOT EXISTS` 保留 audit/resume 历史；状态表 DDL 与并发 QA 文件编号改为 `02` / `07` 避免冲突。验证已通过 Python `py_compile`、`git diff --check`、stage_a dry-run、单实验 dry-run、全 manifest dry-run 和直接参数注入断言；未执行 BigQuery。

**OQ-010 实跑与调度修复（2026-06-04）**：Stage C runner/QA 修复已由 PR #47 合并并完成重跑；3*2*2*2 全因子 24 组合已补齐。并发调度后续修复已由 PR #48 合并，解决同 stage dependency batching 和诊断状态/上传状态语义拆分问题。

**Cloud Run 最新状态（2026-06-05）**：策略 1 Cloud Run runner 首版已由 PR #56 合并到 `main`，orchestrator 状态/锁增强已由 PR #57 合并到 `main`。真实 Cloud Run Job smoke 已完成并通过链路级 QA；本轮修复将 `gcloud run jobs execute --args` 补上 Python module、降低 Cloud Build 本地 tag 依赖、优化特征矩阵内存、给中文报告容器补 CJK 字体、放宽 Python/BigQuery float round-trip 的 score orientation QA 容差，并把 parity 未通过从 fail-fast 改为记录 `model_quality_not_equivalent`。后续重点不是“能否运行”，而是 sklearn backend 是否能达到 BQML baseline 模型质量等价，以及 Python ledger vs SQL ledger 的正式等价验收。

**分支卫生**：PR 合并后，若 owner 未要求保留工作分支，应删除已合并且不再使用的 `codex/*` 本地分支和对应远端分支。`codex/implement-strategy1-prd` 和 `codex/implement-oq004-index` 已在本地和远端删除。

> 历史交接已归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-05.md` 和 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。常规启动只需阅读本文件的当前摘要和最近交接；归档仅用于审计追溯。

---

---

## 交接条目

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-010 / Strategy 1 sklearn native model experiment PRD

### 已完成工作

- 在独立工作树 `/Users/luna/Desktop/git/quant-ashare-sklearn-native-prd` 和分支 `codex/prd-sklearn-native-experiment` 新增 `docs/prd/PRD_20260605_03_策略1Sklearn模型实验.md`。
- PRD 固定当前交易口径 `pv_fin_quality + 30/5% + biweekly + 5d`，避免把模型实验和交易参数变化混在一起。
- PRD 定义第一轮 36 个 LogisticRegression sklearn 原生候选：无正则、L2、ElasticNet，覆盖 `C`、`class_weight`、`l1_ratio` 和 solver 语义。
- PRD 定义搜索流程：一次 `prepare_matrix`，candidate task fan-out 并发训练全部候选，valid-only 选 Top 5，再对 Top 5 跑完整预测、组合、回测、报告、诊断和 QA。
- PRD 定义 sklearn native acceptance gate：valid/test RankIC、2025 test-year 收益和相对中证1000超额、Sharpe、max drawdown、成本、`10/12/16/17/18` QA 和 Python ledger vs SQL ledger 等价边界。
- 同步 `TODO.md`、`PROJECT_CONTEXT.md`、`OPEN_QUESTIONS.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要。

### 重要上下文

- 本 PRD 是 Cloud Run sklearn backend 在 BQML parity 未通过后的后续方案；它不删除既有 BQML parity gate，只新增 native baseline path。
- BQML baseline 继续作为 reference / fallback；native baseline 是否接受由后续 36 候选 + Top 5 回测结果决定。
- 本次没有实现代码，没有部署 Cloud Run Job，没有执行 BigQuery，没有生成或覆盖 ADS / GCS 产物。

### 改动文件

- `docs/prd/PRD_20260605_03_策略1Sklearn模型实验.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review / 合并本 PRD。
- 合并后实现 `configs/strategy1/sklearn_native_pvfq_n30_bw_h5_v0.yml`、candidate search orchestrator、Top 5 backtest flow 和 `18_qa_sklearn_native_search_outputs.sql`。
- 再跑第一轮 36 个 LogisticRegression 候选并产出 comparison report。

### 已更新记忆文件

- `TODO.md`
- `PROJECT_CONTEXT.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01
相关 issue/PR: Strategy 1 Cloud Run task fan-out formal validation

### 已完成工作

- 将 `strategy1-prepare-matrix-job` 资源从 `4 CPU / 16Gi` 提升到 `8 CPU / 32Gi`，用于解决全量 2019-2025 训练面板 prepare 阶段 16Gi OOM 风险。
- 为正式验收创建独立 run/backtest：`s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01` / `bt_s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01`，不覆盖既有 BQML baseline。
- 重建该 run 的训练面板，行数 3,055,781（train 1,999,065 / valid 476,346 / test 580,370），注意样本 `p_feature_version` 仍使用 DWS 现有 `strategy1_pv_v0_20260601`，`p_feature_set_id` 使用 `strategy1_pv_fin_quality_v0_20260603`。
- 执行完整 Cloud Run task fan-out 链路：`cloudrun_prepare_matrix`、5 个 candidate task、`cloudrun_select_register_predict`、`cloudrun_backtest_report` 全部 succeeded。
- `cloudrun_backtest_report` 内部跑通 `05_build_candidates`、`06_build_portfolio_targets`、`07_build_order_plan`、Python `ledger_exec_v1`、`09_build_metrics_and_report_inputs`、报告上传、`10_qa_runner_outputs.sql`、诊断脚本和 `12_qa_model_diagnosis_outputs.sql`。

### 重要上下文

- `prepare_matrix` execution：`strategy1-prepare-matrix-job-q4zd5`，Cloud Run 侧耗时约 4m10s。
- candidate fan-out execution：`strategy1-train-candidate-fanout-job-fpk9d`，5 个 task 全部 succeeded。
- select/register/predict execution：`strategy1-select-register-predict-job-d5kj2`。
- backtest/report execution：`strategy1-backtest-report-job-4shcl`。
- selected sklearn candidate 为 `elastic_c_1_l1_0_5`，`score_orientation=reverse_probability`。
- 报告 URI：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01/backtest_id=bt_s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01`。
- 模型诊断 URI：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01/backtest_id=bt_s1_cloudrun_taskfanout_pvfq_n30_bw_h5_20260605_01/model_diagnosis`。

### 测试 / 验证

- orchestrator 全链路返回 `status=succeeded`、`failure_count=0`。
- `10_qa_runner_outputs.sql` 和 `12_qa_model_diagnosis_outputs.sql` 在 `cloudrun_backtest_report` 内部通过。
- `16_qa_cloudrun_runner_outputs.sql` 在 `p_require_model_quality_parity_passed=FALSE` 的 smoke/evidence 模式通过。
- `17_qa_cloudrun_orchestrator_status.sql` 在 `p_require_task_fanout=TRUE` 下通过。
- 正式 `16_qa_cloudrun_runner_outputs.sql` 在默认 `p_require_model_quality_parity_passed=TRUE` 下未通过，失败点为 `QA-CR-4`。

### 结果摘要

- 回测 total_return `46.29%`、annual_return `21.72%`、Sharpe `1.111`、max_drawdown `-13.94%`。
- benchmark 为 `000852.SH`，excess_return `17.28%`，information_ratio `0.237`。
- prediction 行数 1,056,716，日期范围 `2024-01-02` 至 `2025-12-31`，score NULL 行数 0。
- diagnosis 结论 `usable_signal`，confidence `low`；valid RankIC mean `0.06665`，test RankIC mean `0.03359`。
- sklearn vs BQML parity 未通过：sklearn valid RankIC `0.06665`，BQML reference `0.09676`，delta `-0.03011`；`model_quality_status=model_quality_not_equivalent`。

### 阻塞项

- 无执行链路阻塞；正式替代 BQML 的模型质量门槛未过。

### 下一步建议

- 不要把本 run 直接标记为 BQML 替代 baseline；它目前只能证明 Cloud Run task fan-out 执行链路可用。
- 下一步应先做 sklearn parity 提升（候选网格、预处理、模型族或参数）或由 owner 明确接受新的 Cloud Run baseline。
- 另需补 Python ledger vs SQL ledger 完整等价验收，再考虑让 Cloud Run runner 成为默认执行路径。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: s1_cloudrun_taskfanout_smoke_20260605_03
相关 issue/PR: Strategy 1 Cloud Run task fan-out smoke / fix branch `codex/fix-task-fanout-force-replace`

### 已完成工作

- 构建并部署 task fan-out 修复镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner@sha256:8cc8470014cb3b54272d4c7f47afb396d91cf7b97967f0c3ffab947f7432c38a`。
- 更新 Cloud Run Jobs：`strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`。
- 执行低成本 task fan-out smoke：2023 train、2024H1 valid、2024H2 test/predict，5 个默认候选全部用 candidate task 并发训练。
- 修复 smoke 暴露的问题：`prepare_matrix` 不支持 `--force-replace`；`10` QA split 边界写死；`12` QA-DIAG-6 使用 DWS 固定 split 导致短窗口 test 误判为 0 天。

### 重要上下文

- 当前 job CPU：prepare/select/backtest 为 `4 CPU / 16Gi`；candidate task 为 `1 CPU / 4Gi`。
- 当前区域配额限制为 `asia-east2` 约 `20 vCPU / 40Gi`，所以 candidate job 设置 `parallelism=10`；本次默认 5 候选 smoke 实际并发为 5。
- 全量 2019-2025 训练面板的 `prepare_matrix` 曾在 `16Gi` 下 OOM；本次 smoke 改用短窗口验证链路。后续正式全量 matrix 可能需要提高 prepare job 内存或做分片/流式构建。

### 改动文件

- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/backtest_report.py`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/orchestrate_experiments.py scripts/strategy1_cloudrun/backtest_report.py`
- `git diff --check`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`
- Cloud Run smoke 状态表 4 步 succeeded：`cloudrun_prepare_matrix`、`cloudrun_train_candidate_fanout`、`cloudrun_select_register_predict`、`cloudrun_backtest_report`
- `10_qa_runner_outputs.sql`、`12_qa_model_diagnosis_outputs.sql`、`16_qa_cloudrun_runner_outputs.sql`、`17_qa_cloudrun_orchestrator_status.sql` 全部通过

### 阻塞项

- 无执行链路阻塞；正式替代 BQML 仍需 sklearn parity passed 或 owner 明确采纳新 Cloud Run baseline。

### 下一步建议

- 提 PR review 并合并本次 smoke 修复。
- 后续若要 35/100 候选并发，需要先决定是提升 Cloud Run 区域配额，还是降低 candidate task 内存并验证 OOM 风险。
- 针对全量窗口 `prepare_matrix` 的 16Gi OOM，单独做 prepare 阶段内存优化或提高 job 规格。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: Strategy 1 Cloud Run lightweight task fan-out implementation

### 已完成工作

- 在工作树 `/Users/luna/Desktop/git/quant-ashare-cloudrun-task-fanout-impl`、分支 `codex/cloudrun-task-fanout` 实现 task fan-out P0。
- 新增 `prepare_matrix.py`，集中读取 `ads_ml_training_panel_daily`，按 train split fit 预处理器，输出已预处理 train/valid/predict parquet、feature schema、preprocess stats、work units、matrix manifest 和 BigQuery job audit。
- 新增 `train_candidate_task.py`，按 `CLOUD_RUN_TASK_INDEX + TASK_INDEX_OFFSET` 训练单个 candidate，输出 candidate model、metrics、training log 和 task status。
- 新增 `select_register_predict.py`，汇总 candidate artifact，校验 matrix/hash，一致通过后选型、写 selected model artifact、registry 和 prediction。
- `orchestrate_experiments.py` 新增 `--train-mode task_fanout` / `--candidate-parallelism`；owner 不限流时单批 `--tasks=N` 全并发，显式限流时按批次执行。
- `16_qa_cloudrun_runner_outputs.sql` 与 `17_qa_cloudrun_orchestrator_status.sql` 增加 task fan-out 模式断言；运行手册和 runner README 已同步。

### 重要上下文

- 该条为 PR #64 合并前 dry-run 阶段交接；真实 task fan-out smoke 已在后续 2026-06-05 交接完成。
- 当前默认 candidate grid 仍是 5 个；未擅自扩到 35 个。扩网格和真实成本实验需要 owner 再确认。
- `prepare_matrix` 依赖既有 `ads_ml_training_panel_daily`，不会自动执行 `01_build_training_panel.sql`；真实执行前必须先确认对应 `run_id` 的训练面板已存在。
- 本机默认 Python 3.9 起初缺 `joblib/scikit-learn`；已按 `scripts/strategy1/requirements.txt` 用 `pip install --user` 补齐本地 dry-run 依赖。

### 改动文件

- `configs/strategy1/cloudrun_runner_default.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1_cloudrun/bq_io.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/prepare_matrix.py`
- `scripts/strategy1_cloudrun/select_register_predict.py`
- `scripts/strategy1_cloudrun/task_fanout.py`
- `scripts/strategy1_cloudrun/train_candidate_task.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/*.py`
- `python3 -m scripts.strategy1_cloudrun.prepare_matrix --project data-aquarium --region asia-east2 --experiment-id oq010_a0_n5_w20 --candidate-parallelism 0 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.train_candidate_task --project data-aquarium --region asia-east2 --matrix-uri gs://dummy/matrix --matrix-local-dir <tmp> --task-index 0 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.select_register_predict --project data-aquarium --region asia-east2 --experiment-id oq010_a0_n5_w20 --matrix-uri gs://dummy/matrix --matrix-local-dir <tmp> --dry-run`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --project data-aquarium --region asia-east2 --manifest configs/strategy1/oq010_experiments_v0.json --config configs/strategy1/cloudrun_runner_default.yml --experiment-id oq010_a0_n5_w20 --train-mode task_fanout --candidate-parallelism 0 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --project data-aquarium --region asia-east2 --manifest configs/strategy1/oq010_experiments_v0.json --config configs/strategy1/cloudrun_runner_default.yml --experiment-id oq010_a0_n5_w20 --train-mode task_fanout --candidate-parallelism 2 --dry-run`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`
- `gcloud run jobs execute --help | rg -n -- '--tasks|--update-env-vars|--args'`
- `git diff --check`

### 阻塞项

- 无代码阻塞；该历史交接的部署与 5 候选 smoke 已在后续 2026-06-05 完成。

### 下一步建议

- 提 PR review。
- PR 合并后部署 `strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`。
- 先用 5 个默认候选跑低成本 task fan-out smoke，通过 `16`/`17` task fan-out QA 后，再讨论是否扩到 35 候选并做 sklearn parity 实验。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-010 / Strategy 1 Cloud Run lightweight task fan-out PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260605_02_策略1CloudRun轻量Task并发.md`。
- PRD 定义 `prepare_matrix -> train_candidate_fanout --tasks=N --candidate-parallelism=M -> select_register_predict -> backtest_report` 链路。
- 固化 GCS frozen matrix 契约、work units manifest、`CLOUD_RUN_TASK_INDEX` 分片映射、小规格 candidate task、owner 显式限流、reducer 选型、QA、状态表与幂等规则。
- 跟进 PR #63 review comment：明确 frozen features 为 `prepare_matrix` 输出的已预处理矩阵，candidate task 不重新预处理；补 BigQuery job labels / audit 机制来验证训练面板只在 `prepare_matrix` 读取；补 candidate task 不读 `predict_features` / `predict_index`。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和本交接文件。

### 重要上下文

- 工作树：`/Users/luna/Desktop/git/quant-ashare-cloudrun-task-fanout-prd`。
- 分支：`codex/prd-cloudrun-task-fanout`。
- 本次只写文档；未实现代码、未部署 Cloud Run Job、未执行 BigQuery、未生成或覆盖 GCS / ADS 产物。
- 该 PRD 是 `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md` 的训练侧并发补充，不替代 Cloud Run runner / orchestrator 已有 PRD。

### 改动文件

- `docs/prd/PRD_20260605_02_策略1CloudRun轻量Task并发.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- review / merge 本 PRD。
- 合并后按阶段实现：Phase 1 先做 dry-run / manifest 展开，Phase 2 做 `prepare_matrix` frozen matrix，Phase 3 做 Cloud Run task fan-out，Phase 4 做 reducer / prediction / QA，最后做 35/100 work units smoke。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #61 / OQ-005 Phase 2.0 BigQuery SQL 兼容调度路径

### 已完成工作

- 跟进 PR #61 review comment。
- `orchestration/composer/dags/ashare_daily_pipeline_v0.py` 移除模块顶层 `Variable.get()`：project/region/location 改为 operator 模板参数，callback URL / BigQuery client 改为运行期 helper 读取。
- `pipeline_dry_run` / `dry_run` 支持单次 DAG run 覆盖 Airflow Variable；DAG 通过 branch 在运行期选择 `ingest_current_scope_dry_run` 或 `ingest_current_scope_write`，避免全局翻转变量才能做真实采集。
- `sql/qa/09_ods_daily_partition_readiness.sql` 新增 `pipeline_dry_run` 参数；`require_business_partition` 为空时由 dry-run 运行期口径推导，dry-run 默认不要求精确业务日分区，真实写入默认要求精确业务日/交易日分区。
- 删除冗余 `ods_daily_partition_readiness >> finish` 依赖。
- 抽出 `_build_qa_chain(group_id)`，复用 `qa` 与 `qa_only` 的 5 个 QA task 定义。
- 同步 `orchestration/composer/README.md` / `orchestration/README.md` 的手工运行参数说明。

### 重要上下文

- 本次只改仓库文件；未部署 Composer、未触发 DAG、未执行生产 BigQuery 转换、未写 GCS。
- PR #61 仍是 OQ-005 Phase 2.0 代码入口；OQ-005 仍保持 open，后续还需要 Composer 部署 smoke、生产验收、Dataform 生产链路、增量影响窗口、告警和补跑闭环。

### 改动文件

- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `sql/qa/09_ods_daily_partition_readiness.sql`
- `orchestration/composer/README.md`
- `orchestration/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=pipeline_dry_run:STRING:true --parameter=require_business_partition:STRING: < sql/qa/09_ods_daily_partition_readiness.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=pipeline_dry_run:STRING:false --parameter=require_business_partition:STRING: < sql/qa/09_ods_daily_partition_readiness.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/meta/01_create_meta_tables.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/meta/04_ods_field_unit_map.sql`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 推送 PR #61 follow-up commit 并在 PR comment 回复验证结果。
- 部署到 Composer 后先做 `skip_ingestion=true` smoke，再做 `warehouse_mode=qa_only` 只读 QA 和 `warehouse_mode=full_rebuild_compat` 维护链路 smoke。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-005 / Phase 2.0 BigQuery SQL 兼容调度路径

### 已完成工作

- 在新工作树 `/private/tmp/quant-ashare-oq005-scheduler-phase2`、分支 `codex/oq005-scheduler-phase2` 开始实现已合并的 `docs/prd/PRD_20260605_01_OQ005剩余调度链路.md`。
- `orchestration/composer/dags/ashare_daily_pipeline_v0.py` 新增 `pipeline_run` / `pipeline_task_status` 状态回写、task success/failure callback、DAG failed callback、`warehouse_mode` 分支、legacy `ashare_enable_full_refresh=true` 到 `full_rebuild_compat` 的记录映射、`skip_ingestion` 分支、`qa_only` 只读 QA 分支和 ADS 契约手工初始化分支。
- `sql/meta/01_create_meta_tables.sql` 扩展 `pipeline_run` / `pipeline_task_status` 字段，新增 `date_from`、`date_to`、`run_label`、`warehouse_mode`、`transform_backend`、`updated_at` 和 Airflow / BigQuery / Cloud Run URL 字段。
- 将 OQ-006 单位映射脚本从 `sql/meta/01_ods_field_unit_map.sql` 重命名为 `sql/meta/04_ods_field_unit_map.sql`，并同步 DAG、SQL README 和 PRD 引用。
- 同步 `orchestration/composer/README.md`、`orchestration/README.md`、`sql/README.md` 和 OQ-005 PRD 中的 Phase 2.0 口径。
- 新增 `DECISION-20260605-01`，记录 `warehouse_mode` 显式区分每日、只读 QA、兼容全量转换和 ADS 契约初始化。

### 重要上下文

- 本次只改仓库文件；未部署 Composer、未触发 DAG、未执行生产 BigQuery 转换、未写 GCS。
- Phase 2.0 现有 CTAS 转换只允许 `warehouse_mode=full_rebuild` 或 `warehouse_mode=full_rebuild_compat` 手工进入；默认 `daily_current` 只做采集、ODS readiness 和状态回写。
- `warehouse_mode=qa_only` 只跑 ODS readiness 后的 `01-05` QA，不改生产表。
- `enable_ads_contract_init=true` 才会执行 `sql/ads/01_ads_strategy1_tables.sql`。

### 改动文件

- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `sql/meta/01_create_meta_tables.sql`
- `sql/meta/04_ods_field_unit_map.sql`
- `orchestration/composer/README.md`
- `orchestration/README.md`
- `sql/README.md`
- `docs/prd/PRD_20260605_01_OQ005剩余调度链路.md`
- `docs/prd/PRD_20260602_01_OQ006接口单位换算口径.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/meta/01_create_meta_tables.sql`
- `git diff --check`

### 阻塞项

- 未阻塞；下一步需要提 PR / review 后部署到 Composer 做 smoke。

### 下一步建议

- 提 PR 并 review Phase 2.0 DAG 变更。
- 部署后先用 `skip_ingestion=true` 做调度 smoke，确认不创建 Cloud Run execution 且 ODS readiness / 状态表回写正常。
- 再用 `warehouse_mode=qa_only` 验证只读 QA 不改生产表。
- 最后用 `warehouse_mode=full_rebuild_compat` 手工 smoke BigQuery SQL 兼容转换链路，确认 metadata / QA / `pipeline_run` terminal 状态完整。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-005 / 剩余 ODS→ADS 调度链路 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260605_01_OQ005剩余调度链路.md`。
- PRD 聚焦当前 `ashare-ingest-current-scope` 生产采集之后的剩余链路，覆盖 ODS gate、ODS→DIM/DWD/DWS/ADS 转换、ADS 契约隔离、metadata、QA、pipeline 状态、告警、补跑、Dataform / BigQuery SQL 双路径、策略 runner/report 可选分支和 OQ-005 关闭标准。
- PR #59 review follow-up：澄清 Phase 2.0/2.1 使用现有 CTAS 时是 `full_rebuild_compat` / maintenance 路径，真正默认每日不扫 2019+ 全史从 Phase 2.2 增量化开始；修正 ADS 脚本现状为已使用 `CREATE TABLE IF NOT EXISTS`；补充 `sql/meta/` 编号整理要求；明确字段说明迁移期生产来源为 `sql/metadata/01,02`。
- 同步 `TODO.md`、`PROJECT_CONTEXT.md`、`OPEN_QUESTIONS.md`、`IMPLEMENTATION_STATUS.md`、`ARCHITECTURE_MEMORY.md` 和当前交接摘要。

### 重要上下文

- 工作树：`/private/tmp/quant-ashare-oq005-ods-ads-scheduler-prd`。
- 分支：`codex/oq005-ods-ads-scheduler-prd`。
- 本次只写 PRD 和必要状态记录，未实现代码、未部署 Composer/Dataform/Cloud Run、未执行 BigQuery。
- OQ-005 继续保持 open，下一步按 PRD Phase 2.0/2.1/2.2/2.3 实现 BigQuery SQL 兼容路径闭环、Dataform definitions、增量影响窗口、策略 runner/report 分支和告警/补跑/状态闭环。

### 改动文件

- `docs/prd/PRD_20260605_01_OQ005剩余调度链路.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- review/merge 本 PRD。
- 合并后按 Phase 2.0 先补 `ashare_daily_pipeline_v0` 的 pipeline status、BigQuery SQL 兼容路径和 ADS 契约初始化隔离。
- Phase 2.1 再接 Dataform definitions 和 workflow invocation。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01 / bt_ledger_resume_smoke_20260604_01
相关 issue/PR: OQ-010 / Ledger v1 P2 state resume implementation

### 已完成工作

- 实现 Ledger v1 state resume。
- `08_run_backtest.sql` 新增 `p_initial_state_mode='resume_from_backtest'`、`p_parent_backtest_id`、`p_state_as_of_date` 和 `p_resume_policy_id`，从父回测恢复现金、实际持仓、active target 和 pending sell。
- resume 前置校验 fail-fast：父 summary 必须存在且 `ledger_version='ledger_exec_v1'`，父 NAV state 必须唯一且含 cash/net value/run_id，父持仓必须唯一且非负，父 NAV 必须能与现金+持仓市值对齐，`p_predict_start` 必须等于 state date 后下一 SSE 开市日。
- `09_build_metrics_and_report_inputs.sql` 在 summary `metrics_json` 写入 `initial_state_mode`、`parent_backtest_id`、`state_as_of_date`、`resume_policy_id` 和 `is_resumed_backtest`。
- `10_qa_runner_outputs.sql` 新增 `QA-RESUME-1..6`；biweekly resume 强制显式传 `p_rebalance_anchor_start` 原实验锚点，首个 resume 日 `daily_return` 必须非空。
- 新增 `sql/ml/strategy1/15_qa_ledger_resume_consistency.sql`，用于后续 full fresh vs resume segment 一致性验收，并比较 `daily_return`。
- `sql/ml/strategy1/README.md` 已同步 resume 参数、运行顺序和 consistency QA 说明。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`KNOWN_CONSTRAINTS.md` 和当前交接摘要。

### 重要上下文

- 当前实现分支：`codex/ledger-state-resume`，工作树 `/Users/luna/Desktop/git/quant-ashare-ledger-resume`。
- 基于 `origin/main` commit `602baea`，该 commit 已包含 Ledger v1 P0。
- smoke 父回测：`bt_ledger_v1_p0_smoke_20260604_01`，`state_as_of_date=2024-02-29`。
- smoke resume 回测：`bt_ledger_resume_smoke_20260604_01`，窗口 `2024-03-01` 至 `2024-03-15`。
- smoke 首日现金恢复为父状态现金 `135.9692847801162`，首日 `daily_return=-0.0031135`，NAV 11 行无 NULL daily_return，持仓 330 行，成交 36 行；本地报告使用 `--skip-gcs-upload`。
- 完整 consistency QA 需要先具备 full fresh extended backtest 与 resume segment backtest；本次只新增 QA 脚本并完成 dry-run。

### 改动文件

- `sql/ml/strategy1/08_run_backtest.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/15_qa_ledger_resume_consistency.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/08_run_backtest.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/15_qa_ledger_resume_consistency.sql`
- BigQuery smoke：PR #54 review follow-up 后，`08` resume、`09` resume、本地 `render_report.py --skip-gcs-upload`、`10_qa_runner_outputs.sql` 全部通过。
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 提 PR review 本次 Ledger v1 P2 resume 实现。
- 合并后补 Ledger v1 P1 fixed-model extended backtest 至 `2026-04-30`。
- 有 full fresh extended 与 resume segment 后，执行 `15_qa_ledger_resume_consistency.sql` 做一致性验收。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01
相关 issue/PR: OQ-010 / factor attribution implementation

### 已完成工作

- 实现策略 1 因子贡献度分析 P0。
- 新增 `scripts/strategy1/attribute_factor_contribution.py`，只读 selected BQML model、冻结训练面板、预测池、候选池、回测持仓和 summary，不重新训练、不做消融实验。
- 新增 `sql/ml/strategy1/14_qa_factor_attribution_outputs.sql`，断言状态、版本、manifest、模型特征覆盖、因子组映射、valid/test RankIC、score contribution 分组、持仓暴露覆盖、路径语义、相关性摘要、限制说明和禁止消融字段。
- `scripts/strategy1/render_report.py` 已接入可选“因子贡献度摘要”：第 13 步回写 completed 后，主报告展示 factor attribution 路径、top 因子组和 top score factors。
- `sql/ml/strategy1/README.md` 已补 13/14 执行命令、参数和 artifact 契约。
- `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要已同步。

### 重要上下文

- 正式 baseline local-only smoke 已成功生成 `reports/strategy1/ml_pv_clf_v0/run_id=s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01/backtest_id=bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01/factor_attribution/`。
- 本次覆盖 selected model 55 个非截距特征、13 个因子组；`factor_attribution_upload_status=skipped`，`local_factor_attribution_path` 已回写 ADS，`factor_attribution_uri` 为空。
- 计算过程中修复了 BigQuery 动态 JSON path 限制：脚本使用 `PARSE_JSON(feature_values_json, wide_number_mode => 'round')[feature]` 取动态特征值。
- 本 PR 只提交代码/SQL/文档/记忆；生成的 `reports/` 本地产物不纳入 git。

### 改动文件

- `scripts/strategy1/attribute_factor_contribution.py`
- `sql/ml/strategy1/14_qa_factor_attribution_outputs.sql`
- `scripts/strategy1/render_report.py`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/attribute_factor_contribution.py scripts/strategy1/render_report.py scripts/strategy1/diagnose_model_quality.py`
- `python3 scripts/strategy1/attribute_factor_contribution.py --help`
- `git diff --check`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/14_qa_factor_attribution_outputs.sql`
- `python3 scripts/strategy1/attribute_factor_contribution.py --project data-aquarium --run-id s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01 --backtest-id bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01 --artifact-base-uri gs://ashare-artifacts/reports/strategy1 --local-mirror-root reports/strategy1 --skip-gcs-upload`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/14_qa_factor_attribution_outputs.sql`，全部 ASSERT 通过。

### 阻塞项

- 无。

### 下一步建议

- 提 PR review 本次因子贡献度实现。
- 合并后按 Ledger v1 PRD 实现 P0 交易语义 A/B，再做 P1 fixed-model 连续扩展回测到 `2026-04-30` 和 P2 ledger state resume。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

---

## 交接条目

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-005 / daily_current 20 日窗口与非交易日口径 hardening

### 已完成工作

- 创建独立工作树 `/private/tmp/quant-ashare-oq005-daily-window-hardening` 和分支 `codex/oq005-daily-window-hardening`，不触碰主目录脏工作树。
- 从最新 `origin/main` 补入本地 `5b62895` 的 daily_current 20 个交易日窗口与 QA-WIN-16/17/18 估值覆盖检查。
- 将 `sql/incremental/01_refresh_stock_dwd_dws_window.sql` 和 `sql/qa/10_windowed_stock_refresh_checks.sql` 的 `daily_current` `date_to` / `business_date` 口径硬化为不晚于请求日期的最近 SSE 开市日；`backfill` 继续保持显式 `date_from` / `date_to`。
- 同步 `sql/README.md`、`orchestration/composer/README.md`、`ARCHITECTURE_MEMORY.md`、`KNOWN_CONSTRAINTS.md`、`OPEN_QUESTIONS.md`、`TODO.md` 和 `IMPLEMENTATION_STATUS.md`，修正 OQ-005 “尚未部署 Composer / 待 smoke”的过期状态。

### 重要上下文

- 2026-06-05 的独立验收已确认 Composer DAG / SQL 部署和 backfill / qa_only / daily_current smoke 成功；20 日估值窗口 `2026-05-08..2026-06-04` 中 ODS `daily_basic`、DWD valuation、DWS valuation 键数均为 110,012，缺失为 0。
- 本分支尚未部署到 Composer；合并后需要同步 `sql/` 到 Composer bucket，确保生产 DAG 读取新 SQL。
- OQ-005 仍保持 open，剩余 Dataform 生产链路、告警、补跑和完整 ODS→ADS 运维观测闭环。

### 改动文件

- `sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `sql/qa/10_windowed_stock_refresh_checks.sql`
- `sql/README.md`
- `orchestration/composer/README.md`
- `TODO.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `bq query --dry_run`：窗口 SQL，`warehouse_mode=daily_current`、`business_date=2026-06-06`。
- `bq query --dry_run`：窗口 QA，`warehouse_mode=daily_current`、`business_date=2026-06-06`。
- `bq query --dry_run`：窗口 SQL，`warehouse_mode=backfill`、`date_from=2026-06-03`、`date_to=2026-06-04`。
- `bq query --dry_run`：窗口 QA，`warehouse_mode=backfill`、`date_from=2026-06-03`、`date_to=2026-06-04`。
- 只读 BigQuery 计算确认 `business_date=2026-06-06` 时 `effective_date_to=2026-06-05`、`dwd_write_start_date=2026-05-11`、窗口内开市日数为 20。

### 阻塞项

- 无代码阻塞；生产部署需在合并后同步 SQL 到 Composer bucket。

### 下一步建议

- Review / merge 本分支。
- 合并后同步 `sql/` 到 Composer bucket，并用 `skip_ingestion=true` 的非交易日 `daily_current` smoke 验证线上 SQL 读取新口径。
- 继续推进 OQ-005 剩余 Dataform definitions、告警、补跑和状态观测闭环。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #69 / OQ-010 / Strategy 1 sklearn native model experiment PRD

### 已完成工作

- 按 PR #69 review comment 修订 `docs/prd/PRD_20260605_03_策略1Sklearn模型实验.md`。
- 将训练窗口从自然年简写改为 `2019-04-03` 至 `2023-12-31`，确保和 BQML baseline / livepool 训练起点一致。
- 新增 `valid_signal_status` 规则：accepted 候选必须为 `stable`；valid 弱但 test 过门只能标记 `needs_more_evidence`。
- 新增跨模型族 test 复用控制：记录 `test_reuse_wave_no` / `test_reuse_approval_ref`，第二波及以后需 owner 批准，超过 3 个波次后必须新增最终 holdout 证据。
- 同步输出报告、ADS/GCS JSON、QA、manifest、Phase 4 和风险表约束。
- 同步 `PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`TODO.md` 和当前交接摘要。

### 重要上下文

- 本次仍是纯文档/记忆修订，未实现代码、未部署 Cloud Run Job、未执行 BigQuery、未生成或覆盖 ADS / GCS 产物。
- `OPEN_QUESTIONS.md` 的 OQ-010 仍保持原 open 状态；关键修订已在 PROJECT_CONTEXT / STATUS / TODO / handoff 记录。

### 改动文件

- `docs/prd/PRD_20260605_03_策略1Sklearn模型实验.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review / 合并 PR #69。
- 合并后实现 sklearn native search manifest、candidate metrics、Top 5 full backtest flow 和 `18_qa_sklearn_native_search_outputs.sql`。

### 已更新记忆文件

- `PROJECT_CONTEXT.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`
- `TODO.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-005 Phase 2.2 / PR #65 post-merge hotfix / branch `codex/fix-windowed-refresh-equivalence`

### 已完成工作

- 在独立工作树 `/private/tmp/quant-ashare-oq005-window-prod` 从最新 `origin/main` 创建热修复分支 `codex/fix-windowed-refresh-equivalence`。
- 运行真实 scratch full-vs-window 等价 QA，确认 PR #65 合并后生产部署前存在两个阻断：QA runner 复制 `_full` 表时缺少分区过滤；估值特征读取窗口不足导致 `turnover_rate_zscore_60d` 漂移。
- 修复 `scripts/qa/run_windowed_refresh_equivalence.py`：复制 canonical `_full` 到 `_window` seed 时按 `trade_date BETWEEN build_start_date AND full_end_date` 过滤，兼容 `require_partition_filter=true`。
- 修复 `sql/incremental/01_refresh_stock_dwd_dws_window.sql`：估值特征读取边界按每只股票写入窗口首日前的实际 60 条估值观测推导，价格特征仍读取 60 个 SSE 交易日，标签/宽表/样本写入仍向前回补 20 个交易日。
- 修复 `scripts/qa/run_windowed_refresh_equivalence.py`：真实运行前用生产 DWD 估值表校验 `build_start_date` 足够早，避免 full/window shadow 被同样截断后假通过。
- 跟进 PR #68 comment：不采用固定 180 个交易日作为最终方案，改为 per-stock 实际观测边界，并用 QA guard 覆盖早期窗口假通过风险。
- 同步 `sql/README.md`、`TODO.md`、OQ-005 架构记忆、约束、状态和开放问题。

### 重要上下文

- 本次真实 QA 只写 scratch dataset `ashare_qa_windowed_equivalence` 的 `_full` / `_window` shadow 表，不写生产 DWD/DWS/ADS。
- 首次真实 QA 的 drift 集中在 `dws_stock_feature_valuation_daily.turnover_rate_zscore_60d` 和继承该字段的 `dws_stock_feature_daily_v0`，原因是 `daily_basic` 对部分股票不是每日完整观测，60 条观测窗口可能跨越超过 60 个交易日。
- 修复后 full-vs-window 等价 QA 对 9 张目标表 mismatch 均为 0；guard 结果为 `required_build_start_date<=2025-01-23`、`sec_code_count=5407`、`less_than_60_obs=32`。
- 仍未部署 Composer，未执行生产 DML，未写生产 BigQuery/GCS/ADS 产物。

### 改动文件

- `scripts/qa/run_windowed_refresh_equivalence.py`
- `sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `sql/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/qa/run_windowed_refresh_equivalence.py`
- `python3 scripts/qa/run_windowed_refresh_equivalence.py --dry-run`
- `bq query --dry_run`：窗口 SQL `backfill` 参数。
- `bq query --dry_run`：窗口 SQL `daily_current` 参数。
- 真实 scratch 等价 QA：9 张目标表 full-vs-window mismatch 均为 0。

### 阻塞项

- 无代码阻塞；生产部署和生产 DML smoke 需等待本 hotfix 合并。

### 下一步建议

- 合并 hotfix PR。
- 合并后部署 Composer DAG 与 SQL 到 Composer bucket。
- 先跑 `skip_ingestion=true` + `warehouse_mode=backfill` 小窗口生产 DML smoke，再跑 `daily_current` scheduler smoke 和 `qa_only` 验收。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #65 / OQ-005 Phase 2.2 股票 DWD/DWS 窗口刷新

### 已完成工作

- 将分支 `codex/windowed-dwd-dws-refresh` rebase 到 `origin/main` 最新提交 `96861b5`。
- 跟进 PR #65 review comment：`sql/incremental/01_refresh_stock_dwd_dws_window.sql` 增加目标表存在性 ASSERT，并用 BigQuery transaction 包住 9 张 DWD/DWS 目标表的窗口 DELETE/INSERT。
- 新增 `scripts/qa/run_windowed_refresh_equivalence.py`，用于发布前/定期在 scratch 表中对比 canonical full SQL 与 window SQL 的窗口内逐列数值等价。
- 同步 `sql/README.md`、`TODO.md` 和 OQ-005 相关记忆，明确大区间 backfill 按年/季/月分块执行，窗口 SQL 与 canonical full SQL 双实现并存期间必须跑等价 QA。

### 重要上下文

- 本次只修改 PR #65 分支内容，未部署 Composer，未执行生产 DML，未写 BigQuery/GCS/ADS 产物。
- 等价 QA runner 默认 scratch dataset 为 `ashare_qa_windowed_equivalence`；真实执行会创建 `_full` / `_window` shadow 表，不应修改生产 DWD/DWS 表。
- `git stash pop` 后的冲突已解决；本次 rebase 前安全备份 stash 已删除，仓库里剩余的 `stash@{0}: autostash` 不是本次 PR #65 follow-up 备份。

### 改动文件

- `sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `scripts/qa/run_windowed_refresh_equivalence.py`
- `sql/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py scripts/qa/run_windowed_refresh_equivalence.py`
- `python3 scripts/qa/run_windowed_refresh_equivalence.py --dry-run`
- `bq query --dry_run`：窗口 SQL `backfill` / `daily_current` 参数各一次。
- `bq query --dry_run`：`sql/qa/10_windowed_stock_refresh_checks.sql` `backfill` / `daily_current` 参数各一次。
- `git diff --check --cached`

### 阻塞项

- 无。

### 下一步建议

- 提交并 force-with-lease 推送 rebase 后的 PR #65 分支。
- PR 合并后先做 `skip_ingestion=true` + `warehouse_mode=backfill` 小窗口 Composer smoke，再做 `daily_current` scheduler smoke 和 `qa_only` 验收。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-005 Phase 2.2 / 股票 DWD-DWS 窗口刷新

### 已完成工作

- 在工作树 `/private/tmp/quant-ashare-windowed-refresh`、分支 `codex/windowed-dwd-dws-refresh` 实现股票 DWD/DWS 窗口刷新。
- 新增 `sql/incremental/01_refresh_stock_dwd_dws_window.sql`，对 `dwd_stock_eod_price`、`dwd_stock_eod_valuation`、策略 1 universe/price/valuation/finance/label/feature/sample DWS 做参数化窗口 DELETE/INSERT。
- 新增 `sql/qa/10_windowed_stock_refresh_checks.sql`，覆盖窗口内主键唯一、生命周期、退市日、ODS daily 表示性、停牌语义和 trainable sample 基础断言。
- `orchestration/composer/dags/ashare_daily_pipeline_v0.py` 新增 `daily_current/backfill` 窗口分支：真实写入时刷新 DIM 小表、恢复 P0 metadata、执行窗口刷新和窗口 QA；`pipeline_dry_run=true` 不写表。
- 同步修复 Composer project/region/location 常量，避免 BigQuery operator `location` 使用未渲染 Jinja。
- `sql/meta/01_create_meta_tables.sql` 合并同表多列 `ADD COLUMN IF NOT EXISTS`，降低连续 table update 限流风险。
- 更新 `orchestration/README.md`、`orchestration/composer/README.md`、`sql/README.md`、`TODO.md` 和相关记忆。

### 重要上下文

- 本次未部署 Composer，未触发 DAG，未执行生产 BigQuery DML，未写 GCS/ADS/report 产物。
- 窗口脚本假设目标 DIM/DWD/DWS 表已由全量 CTAS 路径初始化；ADS runner/backtest/report 仍由策略 runner 独立写入。
- `full_rebuild` / `full_rebuild_compat` 保留原全量兼容链路；`qa_only` 保持只读；`enable_ads_contract_init=true` 仍是 ADS 契约初始化的唯一入口。
- 窗口标签回补是 20 个 SSE 交易日，价格特征读取回看是 60 个 SSE 交易日；后续 hotfix 已把估值特征读取边界改为按每只股票实际 60 条估值观测推导，以覆盖 `daily_basic` 缺口。

### 改动文件

- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `orchestration/composer/README.md`
- `orchestration/README.md`
- `sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `sql/qa/10_windowed_stock_refresh_checks.sql`
- `sql/meta/01_create_meta_tables.sql`
- `sql/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=date_from:STRING:2026-06-03 --parameter=date_to:STRING:2026-06-04 --parameter=warehouse_mode:STRING:backfill < sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=date_from:STRING: --parameter=date_to:STRING:2026-06-04 --parameter=warehouse_mode:STRING:daily_current < sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=date_from:STRING:2026-06-03 --parameter=date_to:STRING:2026-06-04 --parameter=warehouse_mode:STRING:backfill < sql/qa/10_windowed_stock_refresh_checks.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date:STRING:2026-06-04 --parameter=date_from:STRING: --parameter=date_to:STRING:2026-06-04 --parameter=warehouse_mode:STRING:daily_current < sql/qa/10_windowed_stock_refresh_checks.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/meta/01_create_meta_tables.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/metadata/01_p0_table_column_descriptions.sql`

### 阻塞项

- 无代码阻塞；生产前仍需部署 Composer 并做 `skip_ingestion=true` + `warehouse_mode=backfill` 窗口 smoke、`daily_current` scheduler smoke 和 `qa_only` 验收。

### 下一步建议

- 运行 `git diff --check` 后提交 PR。
- PR 合并后同步 DAG 与 `sql/` 到 Composer bucket。
- 先用 `skip_ingestion=true`、`pipeline_dry_run=false`、`warehouse_mode=backfill`、小日期窗口做生产 DML smoke，再恢复/观察 `daily_current` scheduler。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: s1_cloudrun_sklearn_smoke_20260604_02 / bt_s1_cloudrun_sklearn_smoke_20260604_02
相关 issue/PR: OQ-010 / Strategy 1 Cloud Run real smoke

### 已完成工作

- 在独立工作树 `/Users/luna/Desktop/git/quant-ashare-cloudrun-smoke`、分支 `codex/cloudrun-smoke` 上完成策略 1 Cloud Run 真实 smoke 收尾。
- 修复 `orchestrate_experiments.py` 的 `gcloud run jobs execute --args`，确保通过 orchestrator 启动 Cloud Run Job 时包含 `python -m scripts.strategy1_cloudrun.train_predict` / `backtest_report` module。
- 修复 `cloudbuild.strategy1-cloudrun.yaml` 本地 build 时 `$SHORT_SHA` 为空的问题，改为显式 `_TAG` substitution，并同步运行手册 build/deploy 命令。
- 优化 Cloud Run 训练内存：`feature_column_list` 兼容 BigQuery Storage / pandas array-like `.tolist()`；特征矩阵改为预分配 `float32`；展开特征后丢弃 raw JSON 列。
- 将 sklearn vs BQML parity 未通过从 fail-fast 改为记录证据：未通过时仍写 selected registry / prediction / artifact，但必须标记 `model_quality_status=model_quality_not_equivalent`，正式 baseline QA 默认仍要求 parity passed。
- 放宽 score orientation QA 容差到 `1e-6`，覆盖 Python / BigQuery float round-trip 的 `~3e-8` 误差。
- 给 Cloud Run 容器安装 `fonts-noto-cjk`，并在 `render_report.py` 扩展 Noto CJK 字体候选，消除中文报告图表 glyph missing 警告。
- 补充运行手册中的 Cloud Run runtime service account IAM、16Gi/4CPU/`--max-retries=0` 和 smoke / 正式 parity QA 区分。

### 重要上下文

- 使用 Artifact Registry repo `quant-ashare` 和镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner@sha256:6564434f9f216aec6c86cae3923bc44450c3ca26ead14a248b05ca77087d8ead`。
- Cloud Run Jobs：`strategy1-train-predict-job`、`strategy1-backtest-report-job`，均配置 16Gi/4CPU/`--max-retries=0`。
- runtime service account：`241358486859-compute@developer.gserviceaccount.com`，已补 `ashare_ads` dataset WRITER 权限。
- smoke experiment：`cloudrun_smoke_pvfq_n30_bw_h5`，对应正式 BQML reference run `s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01`。
- train/predict execution：`strategy1-train-predict-job-s5725`，prediction 1,056,716 行，selected candidate `elastic_c_1_l1_0_5`，score orientation `reverse_probability`。
- backtest/report execution：`strategy1-backtest-report-job-6fzvr`，完成时间约 2m58s，无 ERROR / CJK glyph warning。
- report URI：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_cloudrun_sklearn_smoke_20260604_02/backtest_id=bt_s1_cloudrun_sklearn_smoke_20260604_02`。
- 回测指标：total_return 46.29%、annual_return 21.72%、Sharpe 1.111、max_drawdown -13.94%、excess_return 17.28% vs `000852.SH`。
- 模型质量 caveat：BQML valid RankIC 0.09676，sklearn valid RankIC 0.06665，rank delta -0.03011 超出 0.02 阈值；`model_quality_parity_status=failed`，`model_quality_status=model_quality_not_equivalent`。

### 改动文件

- `Dockerfile.strategy1-cloudrun`
- `cloudbuild.strategy1-cloudrun.yaml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1/render_report.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/preprocess.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/train_predict.py scripts/strategy1_cloudrun/backtest_report.py scripts/strategy1_cloudrun/orchestrate_experiments.py scripts/strategy1_cloudrun/preprocess.py scripts/strategy1/render_report.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`
- Cloud Build 成功：build id `52191460-108a-404b-8017-c65eaa8ef259`。
- Cloud Run orchestrator resume from `cloudrun_backtest_report` 成功，final execution `strategy1-backtest-report-job-6fzvr` succeeded。
- `16_qa_cloudrun_runner_outputs.sql` 以 smoke 参数 `p_require_model_quality_parity_passed=FALSE` 通过。
- `17_qa_cloudrun_orchestrator_status.sql` 通过。
- `gcloud logging read` 未发现 final execution ERROR 或 CJK glyph warning。
- `git diff --check`。

### 阻塞项

- 无运行链路阻塞。模型质量阻塞仍存在：当前 sklearn backend 未达到 BQML baseline parity，不能作为正式替代。

### 下一步建议

- 提 PR review 本次 Cloud Run smoke 修复。
- 合并后做 sklearn backend 参数 / 模型族迭代，使 parity gate 通过，或由 owner 明确接受新的 sklearn baseline。
- 补 Python ledger vs SQL ledger 的完整等价验收；当前真实 smoke 已证明 Cloud Run Python ledger 能跑通，但还不是正式等价证明。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: manual_oq005_scheduler_smoke_default_queue_20260604_01 / manual_oq005_daily_prod_20260604_01
相关 issue/PR: OQ-005 / GCP pipeline production ingestion phase 1.7

### 已完成工作

- 在工作树 `/private/tmp/quant-ashare-oq005-deploy-phase1`、分支 `codex/oq005-deploy-phase1` 继续推进 OQ-005 生产采集部署，并在 rebase 到最新 `origin/main` 后保留 main 的策略 1 Cloud Run runner 状态。
- 新增并部署 `ashare-ingest-current-scope` Cloud Run Job，单 execution 顺序执行当前实际消费的 14 个 ODS endpoint；4 个分组 Jobs 保留为诊断和单组补救入口。
- PR #58 review follow-up 已补 live BigQuery meta 状态写入：`ashare_meta.ingestion_run` 和 `ashare_meta.ingestion_partition_status`。
- 已把 raw GCS canonical 路径固定为 `api=<api>/endpoint=<partition_endpoint>/partition_date=...`，并用 BigQuery `INFORMATION_SCHEMA.TABLE_OPTIONS` 只读复核当前 14 张 ODS 与 10 张 schema repair 表 source URI。
- 已明确 ingestion publish 覆盖正式 `data.parquet` 不做 write-once backup；历史可回滚回填留后续独立开关/流程。
- Cloud Run Jobs 已配置 Direct VPC egress + Cloud NAT + 区域静态外部 IP 固定出口；Job 模板默认保留 `--dry-run`，Composer 生产路径显式传入 `--allow-gcs-write`。
- `ashare_daily_pipeline_v0` 已移除 `queue="kubernetes"`，使用 default Celery queue；纯 scheduler smoke `manual_oq005_scheduler_smoke_default_queue_20260604_01` 成功。
- 生产 GCS 回填已完成：`2026-05-20` 至 `2026-06-03` 区间内 SSE 开市日全部写入成功，并逐日通过 `sql/qa/09_ods_daily_partition_readiness.sql`。
- Composer 生产 DAG 首跑 `manual_oq005_daily_prod_20260604_01` 已写入 `2026-06-04` 数据并成功完成 readiness。
- Airflow 变量当前为 `ashare_pipeline_dry_run=false`、`ashare_enable_full_refresh=false`。

### 重要上下文

- 当前只启用 ODS 生产采集和每日分区 readiness；完整 ODS→DIM/DWD/DWS/ADS 转换仍在 `ashare_enable_full_refresh=true` 显式分支之后，尚未作为生产链路验收。
- Cloud Run Job 模板保留 `--dry-run` 是安全门禁；生产写入依赖 Composer 传参，不能在脚本中移除 token/dry-run guard。
- Token 只保存在 Secret Manager，不写仓库、文档、日志或记忆。
- `ods_tushare_stk_limit` 历史 Parquet schema mismatch 仍属于 OQ-012 维护/修复工作，不阻断每日生产采集。

### 改动文件

- `scripts/ingestion/run_ingestion_job.py`
- `scripts/ingestion/README.md`
- `scripts/ingestion/common/gcs_writer.py`
- `scripts/ingestion/common/status_writer.py`
- `configs/ingestion/schema_contracts/suspend_d.json`
- `orchestration/cloud_run_jobs/deploy_ingestion_jobs.sh`
- `orchestration/cloud_run_jobs/ingestion_jobs.yaml`
- `orchestration/cloud_run_jobs/README.md`
- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `orchestration/composer/README.md`
- `orchestration/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- Artifact Registry latest digest 确认为 `sha256:351dfd996b6ec066135d68c40f84eb1c2a52e43ea8e28208ba1711be90a7652d`。
- `gcloud composer environments run ... variables get -- ashare_pipeline_dry_run` 返回 `false`。
- `gcloud composer environments run ... variables get -- ashare_enable_full_refresh` 返回 `false`。
- `gcloud composer environments run ... dags state -- ashare_daily_pipeline_v0 2026-06-04T15:15:08+00:00` 返回 `success, {"business_date": "2026-06-04"}`。
- `2026-05-20` 至 `2026-06-03` SSE 开市日生产回填均有对应 Cloud Run execution 成功记录，并逐日通过 `sql/qa/09_ods_daily_partition_readiness.sql`。
- `git rebase origin/main` 成功。
- `git diff --check` 通过。

### 阻塞项

- 无当前采集阻塞。OQ-005 仍未关闭，因完整 ODS→ADS 生产转换、告警、补跑和运维观测尚未验收。

### 下一步建议

- 接入/验证 Dataform 或 BigQuery SQL 生产转换链路。
- 补 Cloud Composer 告警、补跑和运行状态观测。
- 明确 ODS→ADS full refresh 的生产启用窗口，再将 `ashare_enable_full_refresh=true` 作为单独维护/补跑任务验收。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / Cloud Run orchestrator status and lock implementation

### 已完成工作

- 通过 GitHub API 合并 PR #56，并删除远端 `codex/implement-strategy1-cloudrun-runner` 分支。
- 创建工作树 `/Users/luna/Desktop/git/quant-ashare-cloudrun-orchestrator-state-lock`，分支 `codex/cloudrun-orchestrator-state-lock`。
- 新增 `scripts/strategy1_cloudrun/state.py`，封装 `OrchestratorStatusTable`、GCS generation-guarded lease lock、heartbeat/release、experiment params JSON 和 Cloud Run execution id 提取。
- 改造 `scripts/strategy1_cloudrun/orchestrate_experiments.py`：每个实验链的 `cloudrun_train_predict` / `cloudrun_backtest_report` step 写入 `ashare_meta.strategy1_experiment_run_status`，执行前获取 GCS lock，执行中 heartbeat，支持 `--resume` 跳过已成功 step，支持 `--resume-from-step cloudrun_backtest_report` 从指定 step 继续。
- 新增 `sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`，校验 orchestrator 状态、锁元数据、审计字段和 execution id 记录。
- 跟进 PR #57 review comment：Cloud Run orchestrator 改为先启动 execution、记录 execution id 到 GCS lock/status table，再轮询 execution terminal 状态；stale lock 回收前会检查原 execution 是否 terminal；失锁时 cancel 当前 execution；heartbeat 的 GCS/BQ 瞬时错误不再杀线程；QA-CRO-4 改为断言 succeeded step 必须记录 execution id。
- 同步 Cloud Run 默认配置、运行手册、runner README、`TODO.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要。

### 重要上下文

- 当前分支只做 orchestrator 状态/锁/resume 增强；没有启动真实 Cloud Run Job，没有重建 ADS 表，没有上传真实 sklearn model artifact。
- 状态表复用既有 `sql/meta/02_strategy1_experiment_run_status.sql`；执行 Cloud Run orchestrator 前必须先确保该表存在。
- GCS lock 默认路径为 `gs://ashare-artifacts/locks/strategy1/cloudrun/<lock_key>.lock`，lock key 使用 prediction run 或 backtest id 分离 train/predict 与 backtest/report step。
- `attempt` 只在非 running 状态进入 running 时增加；heartbeat 只刷新 lease 和 running 状态，不反复增加 attempt。
- `gcloud run jobs execute` 不再加 `--wait`；orchestrator 启动 execution 后用 `gcloud run jobs executions describe` 轮询状态，因此 stale lock payload 中能保留可检查的 execution id。

### 改动文件

- `configs/strategy1/cloudrun_runner_default.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/state.py`
- `sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`

### 测试 / 验证

- `python3 -m compileall scripts/strategy1_cloudrun`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --experiment-id oq010_a0_n5_w20 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --experiment-id oq010_a0_n5_w20 --resume-from-step cloudrun_backtest_report --dry-run`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --stage-id stage_a --resume --dry-run`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/meta/02_strategy1_experiment_run_status.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql`
- 小单元式校验：`extract_cloud_run_execution_id` 可从 `metadata.name` 和完整 `/executions/` resource name 提取 execution id；`cloud_run_execution_state` 可识别 succeeded / failed / completionTime。
- `git diff --check`

### 阻塞项

- 无代码阻塞。真实验收仍需部署/确认 Cloud Run Jobs 后跑单实验 smoke。

### 下一步建议

- 提 PR review 本次 Cloud Run orchestrator 状态/锁增强。
- 合并后执行单实验真实 Cloud Run smoke，跑 `16_qa_cloudrun_runner_outputs.sql` 与 `17_qa_cloudrun_orchestrator_status.sql`。
- 用真实 smoke 结果验证 sklearn vs BQML parity、Python ledger vs SQL ledger 等价性、GCS model/report artifact 和 ADS 回写。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / Cloud Run strategy1 runner implementation

### 已完成工作

- 启动并完成策略 1 Cloud Run 训练回测执行器首版实现，工作分支 `codex/implement-strategy1-cloudrun-runner`，worktree `/Users/luna/Desktop/git/quant-ashare-strategy1-cloudrun-runner`。
- 新增 `scripts/strategy1_cloudrun/` Python 包：配置/实验 manifest 解析、BigQuery/GCS IO、sklearn 训练预测、Python fresh-start ledger、SQL 参数化 runner、Cloud Run 多实验 orchestrator。
- 新增 `Dockerfile.strategy1-cloudrun`、`cloudbuild.strategy1-cloudrun.yaml`、`configs/strategy1/cloudrun_runner_default.yml` 和 `docs/策略1CloudRun训练回测运行手册.md`。
- 新增 `sql/meta/03_strategy1_cloudrun_status_extensions.sql` 和 `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`；`09_build_metrics_and_report_inputs.sql` 已把 `execution_backend` 写入 summary `metrics_json`。
- `sql/ml/strategy1/README.md` 和 `scripts/strategy1/requirements.txt` 已同步 Cloud Run / sklearn runner 运行说明和依赖。
- 跟进 PR #56 review comment：确认 QA-CR-5 提到的 `ledger_version` 缺失不成立（`09` 已写入该字段）；同时补 `p_ledger_version` / `p_ledger_executor` 参数化、`--use-bq-ledger` fallback backend 标记、parity failed fail-fast 与 QA hard gate、orchestrator 失败结果汇总和 `--continue-on-error`。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要。

### 重要上下文

- 当前首版边界：`01_build_training_panel.sql` 仍是前置 SQL；`05/06/07` 仍复用 BigQuery SQL；Python ledger P0 只支持 fresh-start，resume 先 fail-fast，等 Python ledger vs SQL ledger 等价验收后再补。
- Cloud Run orchestrator 遵守 PRD 并发契约：未设置或传 `0` 时，默认并发数等于 manifest 中可执行实验数量；owner 可用 `--max-parallel-experiments N` 显式限流。P0 采用唯一 `run_id` / `backtest_id` + Cloud Run execution 轻隔离，尚未写 `strategy1_experiment_run_status` / GCS lock，真实多实验 smoke 后再对齐状态框架。
- 为避免 Cloud Run job 读取本地临时 manifest，orchestrator 已把 resolved experiment payload 通过 URL-safe base64 `--experiment-json` 传入 job。
- 本地 Python 3.9 环境未安装 sklearn/joblib；代码已使用 lazy import，使 dry-run 不依赖本地 sklearn。真实训练应在 Cloud Run 镜像内用 Python 3.11 和 requirements 执行。
- 本次没有执行真实 Cloud Run job，没有重建 ADS 表，没有上传真实 sklearn model artifact。

### 改动文件

- `Dockerfile.strategy1-cloudrun`
- `cloudbuild.strategy1-cloudrun.yaml`
- `configs/strategy1/cloudrun_runner_default.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1/requirements.txt`
- `scripts/strategy1_cloudrun/*`
- `sql/meta/03_strategy1_cloudrun_status_extensions.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`

### 测试 / 验证

- `python3 -m compileall scripts/strategy1_cloudrun`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --experiment-id oq010_a0_n5_w20 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --stage-id stage_a --dry-run`
- `python3 -m scripts.strategy1_cloudrun.train_predict --experiment-id oq010_a0_n5_w20 --dry-run`
- `python3 -m scripts.strategy1_cloudrun.backtest_report --experiment-id oq010_a0_n5_w20 --dry-run`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/meta/03_strategy1_cloudrun_status_extensions.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `git diff --check`
- PR #56 review follow-up 后补跑：`python3 -m compileall scripts/strategy1_cloudrun`、`python3 -m scripts.strategy1_cloudrun.backtest_report --experiment-id oq010_a0_n5_w20 --dry-run`、`python3 -m scripts.strategy1_cloudrun.backtest_report --experiment-id oq010_a0_n5_w20 --use-bq-ledger --dry-run`、`python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --stage-id stage_a --dry-run`、`09` / `16` BigQuery dry-run、`git diff --check`。

### 阻塞项

- 无代码阻塞。真实验收仍需部署 Cloud Run Jobs 并跑单实验 smoke。

### 下一步建议

- 提 PR review 本次 Cloud Run runner 首版实现。
- PR review 通过后部署 Cloud Run image/jobs，跑单实验真实 smoke。
- 真实 smoke 后补 sklearn vs BQML parity、Python ledger vs SQL ledger 等价验收；等 fresh-start 等价通过后再实现 resume path。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / Cloud Run training and backtest PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`。
- PRD 决定只写一篇统一文档，不拆训练 PRD 和回测 PRD，避免训练、预测、回测、实验并发和 artifact 契约漂移。
- PRD 定义 Cloud Run Jobs + scikit-learn logistic 训练 / 预测 + Python `ledger_exec_v1` 回测的目标执行路径。
- PRD 明确 scikit-learn 只替代 BQML `LOGISTIC_REG` 的模型训练 / 预测，不替代 BigQuery DWS/ADS、GCS artifact、报告诊断和 QA；P0 仍需 BigQuery / GCS 客户端、`pyarrow`、`polars` 或 `pandas`、`joblib` 等依赖。
- PRD 固化 Cloud Run 多实验默认并发规则：`--max-parallel-experiments` 未设置或为 0 时，并发数等于 manifest 可执行实验数量；owner 显式传 N 时才限流。
- 跟进 PR #55 review comment `issuecomment-4622638415`：补 sklearn vs BQML 模型质量对等门槛；P0 默认 `class_weight=None`；明确 sklearn 正则网格是重新定义，不直接翻译 BQML `L1_REG` / `L2_REG`。
- 新增 `DECISION-20260604-03`，并同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`KNOWN_CONSTRAINTS.md`、`PROJECT_CONTEXT.md`、`ARCHITECTURE_MEMORY.md` 和当前交接摘要。

### 重要上下文

- 本次只写 PRD 和记忆/TODO，没有实现 Cloud Run 代码，没有创建 GCP 资源，没有执行 BigQuery，也没有生成或覆盖报告 artifact。
- 既有 BigQuery ML + SQL runner 保留为 reference / fallback，直到 Cloud Run sklearn + Python ledger 路径通过契约、QA 和回测语义一致性验收。
- Cloud Run runner 的默认全实验并发是 owner 明确要求；不要沿用本地 OQ-010 调度器 `max_parallel=2` / `max_parallel_backtest=1` 的保守默认值。

### 改动文件

- `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review 并合并 Cloud Run 训练回测 PRD。
- 实现前先确认 Cloud Run region、service account、artifact bucket 和容器构建方式；默认沿用 `asia-east2`、`data-aquarium`、`gs://ashare-artifacts`。
- PRD 合并后新增 `scripts/strategy1_cloudrun/`、Cloud Run Dockerfile / build config、`sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql` 和运行手册。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01 / bt_ledger_v1_p0_smoke_20260604_01
相关 issue/PR: OQ-010 / Ledger v1 P0 implementation

### 已完成工作

- 实现策略 1 `ledger_exec_v1` P0 交易执行语义。
- `08_run_backtest.sql` 改为日级账户 ledger：t-1 信号 / t 开盘执行、每日 pending sell retry、卖出先于买入、实际持仓 netting、现金缩放、非目标持仓继续 mark-to-market、订单状态显式记录。
- 同步 `09` 指标汇总、`10` runner QA、`11` 诊断 SQL、ADS 字段说明、报告脚本、诊断脚本和 README。
- 修复报告买入明细关联预测表时缺少 `predict_date` 分区过滤的问题。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`KNOWN_CONSTRAINTS.md` 和当前交接摘要。

### 重要上下文

- P0 仍保留 PRD 定义的简化：FLOAT 股数、不做 100 股手数约束、不显式 T+1 卖出锁定、不做买入候补、不做 partial-fill 深度模型。
- 短区间 smoke 使用正式 baseline prediction run：`s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01`，新建 smoke backtest：`bt_ledger_v1_p0_smoke_20260604_01`，窗口 `2024-01-02` 至 `2024-02-29`。
- smoke `render_report.py` 使用 `--skip-gcs-upload`，只验证本地报告和 ADS 回写，不上传 GCS。

### 改动文件

- `sql/ml/strategy1/08_run_backtest.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/11_model_quality_diagnostics.sql`
- `sql/ads/01_ads_strategy1_tables.sql`
- `scripts/strategy1/render_report.py`
- `scripts/strategy1/diagnose_model_quality.py`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `bq query --dry_run`：`08_run_backtest.sql`、`09_build_metrics_and_report_inputs.sql`、`10_qa_runner_outputs.sql`、`11_model_quality_diagnostics.sql`、`sql/ads/01_ads_strategy1_tables.sql`
- `python3 -m py_compile scripts/strategy1/render_report.py scripts/strategy1/diagnose_model_quality.py`
- 短区间 BigQuery smoke：`08`、`09`、`render_report.py --skip-gcs-upload`、`10_qa_runner_outputs.sql` 全部通过
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review/merge Ledger v1 P0 实现 PR。
- 合并后用正式 baseline 参数跑完整 `2024-01-02` 至 `2025-12-31` 同区间 A/B，对比旧 ledger 与 `ledger_exec_v1`。
- A/B 收敛后再做 P1 fixed-model 连续扩展回测至 `2026-04-30` 和 P2 state resume。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / factor attribution PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260604_03_策略1因子贡献度分析.md`。
- 明确本轮因子贡献度分析不做消融实验，不重训、不 drop factor，只读当前 baseline。
- 因子贡献度 PRD 定义模型系数/标准化系数、单因子 RankIC/bucket lift、score contribution、组合因子暴露、归因 proxy 和因子相关性/共线性摘要。
- 更新 Ledger PRD 和月度重训 PRD 的推荐实施顺序：因子贡献度分析 → Ledger v1 P0/P1/P2 → 月度滚动重训。
- 跟进 PR #51 comment，补充多重共线性解释边界：单因子系数排名不稳定、组级解读优先、单因子 RankIC 与多变量系数可能不一致、proxy 贡献不可跨相关因子加总。
- 新增 `DECISION-20260604-02` 并同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要。

### 重要上下文

- 因子贡献度分析只是实施顺序上的前置解释基准，不代表优先级高于 Ledger 或月度重训。
- 当前 PRD 已把高相关因子问题写成解释约束；实现时必须输出 `factor_correlation_summary.csv` 并在中文摘要提示共线性限制。
- P0 推荐实现为独立 `scripts/strategy1/attribute_factor_contribution.py`，产出 `factor_attribution/` artifact，再用 `14_qa_factor_attribution_outputs.sql` 验收。
- 若未来要做消融实验，需要另写 PRD；本 PRD 明确禁止把消融路径混进 P0。

### 改动文件

- `docs/prd/PRD_20260604_03_策略1因子贡献度分析.md`
- `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review 并合并因子贡献度 PRD。
- 合并后实现 `attribute_factor_contribution.py` 和 `14_qa_factor_attribution_outputs.sql`，先对正式 baseline 生成 factor attribution artifact。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / Ledger v1 PRD / monthly retrain PRD

### 已完成工作

- 按 owner 采纳的方案改造两篇 PRD：不新增第三篇 PRD。
- `PRD_20260604_01_策略1LedgerV1交易执行语义.md` 已扩展为 Ledger P0/P1/P2：P0 交易执行语义、P1 `2024-01-02` 至 `2026-04-30` fixed-model 连续扩展回测、P2 ledger state resume。
- `PRD_20260604_02_策略1月度滚动重训.md` 已收敛为只定义模型生命周期、失败回退和 PIT-safe prediction stream，并明确依赖 Ledger P0/P1/P2。
- 新增 `DECISION-20260604-01`，固化实现顺序为 Ledger v1 P0 → Ledger v1 P1 → Ledger v1 P2 → 月度滚动重训。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要。

### 重要上下文

- 2026 扩展回测和 resume 均归入 Ledger/backtest 执行能力，不归入月度重训。
- P1 扩展回测必须 fixed-model fresh-start 从 `2024-01-02` 连续跑到 `2026-04-30`；不能用只跑 2026 片段再简单拼接替代。
- 月度重训正式效果归因必须等 Ledger P0/P1/P2 稳定后再做。

### 改动文件

- `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 提 PR review 两篇 PRD 改造。
- PRD 合并后先实现 Ledger v1 P0 交易执行语义并用正式 baseline 参数 A/B。
- P0 稳定后再做 P1 fixed-model 扩展回测和 P2 resume；最后实现月度滚动重训。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`
---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / Ledger v1 PRD / monthly retrain PRD / memory cleanup

### 已完成工作

- 清理工作记忆：`AGENT_HANDOFF.md` 缩到当前摘要 + 最近 3 条交接，19 条旧交接归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。
- 新增 `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`。
- 新增 `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`。
- 跟进 PR #49 review comment，补充 Ledger PRD 的 T+1 卖出锁定非目标、月度重训 PRD 的 oriented RankIC 通过标准和 test split 事后评价口径。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要。

### 重要上下文

- Ledger v1 PRD 固化 t-1 信号 / t 开盘执行、pending sell 每日继续卖、实际持仓 netting、现金缩放、订单状态和每日 mark-to-market NAV；明确不改变模型训练/预测来源。
- 月度滚动重训 PRD 定义 monthly cadence、rolling 5 年训练窗口、12 个月 valid 窗口、月内固定模型、失败回退和 PIT-safe prediction stream。
- 实现顺序必须先 Ledger v1 A/B，再月度重训，避免交易执行语义变化和模型生命周期变化混在一起。

### 改动文件

- `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 提 PR review 两篇 PRD。
- PRD 合并后先实现 Ledger v1 交易执行语义，并用正式 baseline 参数 A/B。
- Ledger v1 A/B 收敛后，再实现月度滚动重训 prediction stream。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`
