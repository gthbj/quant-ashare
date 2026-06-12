# 实现状态（Implementation Status）

这是实现状态的唯一事实来源。面向「已完成/进行中/受阻的整体状态」；「下一步要做什么」见根目录 `TODO.md`。

Last updated: 2026-06-13

## 当前状态快照

### 数仓分层与数据覆盖

- P0 数仓底座已完成：ODS→DIM/DWD→DWS→ADS 分层稳定，核心 DIM/DWD/DWS/ADS、单位契约、benchmark 口径和财务三大报表链路已物化并通过 QA。
- ODS schema mismatch（OQ-012）已关闭；新增 / 修复 ODS Parquet 必须按 schema contract 显式 cast 并运行对应 QA。
- true-five-year 数据覆盖修复已完成：2010-2014、2015Q1、`2019-01-02..2019-04-02` 覆盖补齐，`13_true5y` 与逐年 refit panel coverage QA 是后续 true-five-year 重跑硬门。

### 采集与调度

- 生产调度唯一入口已迁到 `Cloud Scheduler + Cloud Workflows`；`ashare-composer` 已删除，Composer 目录仅保留为 retired / audit-only 历史快照。
- 2026-06-12 scheduled current_scope 已使用修复后 ingestion 镜像 `sha256:5c78e8624584e9ee47471be087ba7e4090d00477a37ec276920f8696810c3f3b` 写入 `ashare_meta.ingestion_run` / `ingestion_partition_status` 27 行，采集审计链路恢复已验证；本轮新增 `v_ingestion_meta_missing` 与对应 alert policy 防复发。2026-06-13 是周六，20:00 scheduled run 应验证非交易日 gate；下一次 live meta 验证窗口是 2026-06-15 20:00 CST。OQ-005 仍剩 post-cutover 短观察窗与 2026-06-12 下游 window QA 独立失败跟进。

### Strategy1 执行层与 baseline

- Strategy1 普通实验默认写 `ashare_research.research_*`，ADS 正式发布只能走 owner-approved promotion；旧 BQML / SQL ledger runner 仅作 historical reference / audit。
- 当前研究 baseline 数字为 true-five-year CA-on：prediction `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01`，backtest `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01`，CAGR `15.36%` (`0.153578`)、v3 contract Sharpe `0.6685`、Calmar `0.4103`、MaxDD 不变；2026-06-12 dividend 补采后 resume 修正，child `bt_s1_dividend_backfill_resume_20260528_20260609_v20260612_01`，详见 `docs/分析-dividend-ODS补采与CA-Resume补跑-20260612.md`。
- baseline 仍不等于 accepted：Sharpe 距 0.70 门约 `0.0315`，Calmar `< 1.0`；不得 promotion。后续实验一律显式 `corporate_actions=cash_div_and_split_v1` / `dividend_tax_mode=flat_10pct`。

### QA 与契约

- Cloud Run Python / native Strategy1 路线、lot-aware ledger、resume、synthetic continuous、research routing、promotion review-only、CA ledger QA 均已形成契约化测试或 SQL QA；PRD_20260612_04 已补 CA staleness、catalog、metric freeze、window SQL 同构、resolver 和纯函数测试护栏。
- `tests/strategy1/test_topdown_lot_phase0.py` 依赖项目记忆解析当前 baseline id；任何记忆重排必须保留 CA-on baseline 段落或让 `DECISION_LOG` 近期全文可解析。

### 工程治理与记忆体系

- PRD_20260612_03 已把主记忆文件压缩为快照 / 索引 / 近期条目结构；历史编年史和决策全文原文归档到 `.agent/memory/archive/`。
- PRD_20260612_05 Strategy1 包结构 Phase E 收尾已完成 Batch 1/2/3：`bq_io.py` / `config.py` / `state.py` / `task_fanout.py` / `feature_sets.py` / `preprocess.py` / `training_panel.py` / runner `__version__` 已迁入 `src/quant_ashare/strategy1/`，annual rolling 计划层已抽到 `annual_rolling_plan.py`；src 对 `scripts.strategy1_cloudrun.*` 的反向 import 已清零，脚本侧保留两个 orchestrator CLI 主体与 thin shim 兼容群。
- `KNOWN_CONSTRAINTS.md` 只做保守拆行和结构化映射，操作性语义不删除；全量 before/after 映射见 `docs/prd/PRD_20260612_03_KNOWN_CONSTRAINTS映射表.md`。

### 开放主线

- `OPEN_QUESTIONS.md` 只剩 OQ-010：继续寻找可 accepted 的 Cloud Run Python baseline / 组合构造 / 风控路线。
- PRD_20260611_10 topdown Phase 0 / Phase 2、尾部风险后续路线、R14 长训练窗口覆盖审计和 OQ-005 短观察窗仍是待办方向，具体下一步以 `TODO.md` 为准。

## 最近补充（最近 7 条）

### 最新补充（2026-06-13）：ingestion meta 0 行事故复核与防复发告警已实现

- 分支 `codex/ingestion-meta-incident` 已完成 ashare_meta ingestion meta 0 行事故独立复核并产出报告 `docs/分析-ingestion-meta-0行事故排查-20260613.md`。根因仍成立：旧 ingestion 镜像 `sha256:351dfd996b6ec066135d68c40f84eb1c2a52e43ea8e28208ba1711be90a7652d` 构建早于 `60fb242` 接入 `IngestionStatusWriter`，2026-06-09/10/11 live ingestion task success 但 meta rows=0。
- 当前 `ashare-ingest-current-scope` job spec 仍是 `ingestion:latest`、generation=1；不需要更新 job spec。本轮只读确认 2026-06-12 20:00 CST scheduled execution `ashare-ingest-current-scope-9wnh8` 使用 `sha256:5c78e8624584e9ee47471be087ba7e4090d00477a37ec276920f8696810c3f3b` 并写入 27 条 current_scope meta。随后 dividend 补采镜像 `sha256:35acbc363408d05dd758d70ba5f293e8b0d333a000c6dfe8e8143ddadd0b8bba` 成为 `latest`，后续 dividend executions 也已写 meta。
- 新增 `ashare_meta.v_ingestion_meta_missing`，并把 `alert_type='ingestion_meta_missing'` 接入 `v_alert_summary`、`scripts/alerting/setup_alerts.py` log metric / Cloud Monitoring policy、alert README 与 runbook；历史回放显示 2026-06-09/10/11 会告警，2026-06-12 修复后 `meta_rows=27` 不会误报。
- 2026-06-13 是周六，SSE `is_open=0`；20:00 CST scheduled workflow 应验证 `non_trading_day_gate` / `skip_non_trading_day`，不会触发 live ingestion，也不应期待 20260613 meta 行。下一次 live meta 验证应看 2026-06-15 20:00 CST 后是否使用当前 `latest` digest 并写 20260615 current_scope meta。
- 验证通过：`bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/observability/01_pipeline_status_views.sql`；`python3 -m pytest -q tests/alerting/test_ingestion_meta_missing_alert.py`；`python3 scripts/alerting/setup_alerts.py --dry-run`；`python3 scripts/dataform/generate_sqlx_from_sql.py --check`；`git diff --check`。本轮未改生产 job spec/IAM/Workflows/Scheduler，未补写历史 meta。

### 最新补充（2026-06-12）：PRD_20260612_05 Batch 3 包结构收尾已实现

- 分支 `codex/prd05-batch3` / PR #206 已按 PRD §3 Batch 3 完成 Strategy1 包结构收尾：`feature_sets.py` / `preprocess.py` / `training_panel.py` 迁入 `src/quant_ashare/strategy1/`，scripts 同名路径改为 thin re-export shim；src 内对三模块的反向 import 已改为包内直连。
- `annual_pipeline_scheduler.py` 所依赖的年度滚动计划层符号已抽到 `src/quant_ashare/strategy1/annual_rolling_plan.py`；`scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py` 保留 CLI 主体、参数面和 dry-run 调度行为，并从新包模块 re-export 计划函数以维持旧导入路径兼容。
- `tests/strategy1/test_package_boundaries.py` 更新 Batch 3 shim 兼容符号快照，新增非仓库 cwd 且 `PYTHONPATH` 仅指向 `src` 的全包 import 自洽测试，并把 src→`scripts.strategy1_cloudrun.*` 反向 import 改为硬断言 `0`。
- 本轮不改训练、回测、ledger、orchestrator CLI 语义，不触碰 Cloud Run job spec/args/镜像/IAM，不写 BigQuery/GCS。最终验证通过：`PYTHONPATH=src python3 -m pytest -q tests`（276 passed）；`PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_package_boundaries.py`（7 passed）；`PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_cloudrun_package_entrypoints.py`（16 passed）；retired linter / compileall / Dataform check / `git diff --check` 均通过。

### 最新补充（2026-06-12）：dividend ODS 缺口补采与 CA-on baseline resume 补跑完成

- 分支 `codex/dividend-backfill-resume` 已按 owner 批准执行 dividend 缺口补采：新增独立 manifest / endpoint group `dividend_backfill`，`current_scope` alias 显式排除该 group，`dividend` business date 请求参数使用 `ex_date`；每日调度行为不变，默认 `corporate_actions=none_v1` 不变。
- Cloud Run job `ashare-ingest-current-scope` 补采 SSE 开市日 `2026-05-28..2026-06-12` 共 12 个分区，`ods_tushare_dividend` 新增窗口合计 `1215` 行，`ex_date` 与 partition_date 全匹配；2024/2025 同期行数分别为 `1182`/`1184`。本轮 ingestion meta 正常落 `12` 条 success。
- 已重跑 `sql/dwd/12_dwd_stock_dividend_event.sql` 与 `sql/qa/14_corporate_action_event_checks.sql`，QA-CA-EVENT-1..6 通过；baseline resume gap `2026-05-28..2026-06-09` 得到 canonical events=`902`、source rows=`905`，ledger-consumable view `unclassified_rows=0`。
- 已从 parent `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01` 的 `2026-05-27` state resume 到 child `bt_s1_dividend_backfill_resume_20260528_20260609_v20260612_01`，Cloud Run execution `strategy1-backtest-report-job-tjn4j` 成功，输出仅写 `ashare_research`。`qa_lot_aware_ledger_outputs` job `b697f4dc-1eaf-4eff-9df1-23e04fb809ac` 与 `qa_corporate_action_ledger_outputs` job `beefe3d8-0022-4aa9-a224-37eb82931760` 通过；ADS 反查和 promotion manifest 均为 0 行。
- parent/child 差异归因闭合：新增两条 `CORPORATE_ACTION_CASH_DIVIDEND`（`002756.SZ` 2026-05-29、`001314.SZ` 2026-06-02），税前 `76.0`、税 `7.6`、净现金 `68.4` 元；position/share 差异为 0。非 CA 只有两条未成交 `BUY_SKIPPED_BELOW_LOT` planned_shares 尾差，filled/cash/turnover/fee/tax/slippage 均为 0。
- 拼接 parent NAV `2021-01-04..2026-05-27` + child NAV `2026-05-28..2026-06-09` 后，v3 contract 口径 CAGR=`0.15357789449949522`、contract Sharpe=`0.668539787795112`、Calmar=`0.41030930550903105`、MaxDD=`-0.3742978588042647`。Claude review 已通过 PR #205 技术面，owner 预先决策影响很小则采纳；本轮采纳展示数字修正，但不改 `DECISION-20260612-03` 数字文本。

### 最新补充（2026-06-12）：PRD_20260612_05 Batch 2 包结构收尾已实现

- 分支 `codex/prd05-batch2` / PR #204 已按 PRD §3 Batch 2 完成 Strategy1 包结构收尾：`scripts/strategy1_cloudrun/state.py` 与 `task_fanout.py` 迁入 `src/quant_ashare/strategy1/`，scripts 同名文件改为 thin re-export shim；src 内对两模块的反向 import 已改为包内直连。
- `annual_pipeline_scheduler.py` 去重使用迁入后的 `state.utc_now` / `_is_precondition_error` / `_is_not_found_error` / `describe_cloud_run_execution`；`GcloudExecutionClient.describe` 复用 state helper，恢复失败路径的 `LOGGER.warning`，这是本 Batch 唯一行为差异修复。
- `GcsLeaseLock` / `GcsSchedulerLease` / `PipelineStateStore` docstring 已标注各自锁语义出处；未合并三类 lock 的 reclaim / heartbeat 语义。
- `tests/strategy1/test_gcs_leases.py` 新增 fake GCS 直测，覆盖 `GcsLeaseLock` acquire 竞争、stale reclaim 的 execution-terminal 条件、heartbeat 失锁，以及 `GcsSchedulerLease` generation conflict、失 owner 停止、无 reclaim 行为。`tests/strategy1/test_package_boundaries.py` 更新 Batch 2 shim 符号快照与反向 import 计数断言；Batch 2 后 src→scripts import 仅剩 `feature_sets` / `preprocess` / `orchestrate_annual_rolling_selection`。
- 本轮不改训练、回测、ledger、orchestrator 调度语义，不触碰 Cloud Run job spec/args/镜像/IAM，不写 BigQuery/GCS。最终验证通过：`PYTHONPATH=src python3 -m pytest -q tests`（275 passed）；`PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_package_boundaries.py`（6 passed）；`PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_cloudrun_package_entrypoints.py`（16 passed）；retired linter / compileall / Dataform check / `git diff --check` 均通过。

### 最新补充（2026-06-12）：PRD_20260612_05 Batch 1 包结构收尾已实现

- 分支 `codex/prd05-batch1` 已按 PRD §3 Batch 1 完成 Strategy1 包结构收尾并创建 PR #203：`scripts/strategy1_cloudrun/bq_io.py` 与 `config.py` 迁入 `src/quant_ashare/strategy1/`，scripts 同名文件改为 thin re-export shim；`runner_version.py` 在 src 内定义原 runner version 值，`scripts.strategy1_cloudrun.__version__` 改为 re-export。
- src 内对 `scripts.strategy1_cloudrun.bq_io` / `config` / `dataset_roles` / `acceptance` / `__version__` 的 import 已改为包内直连；剩余 src→scripts import 仅限 Batch 2/3 范围 `state` / `task_fanout` / `feature_sets` / `preprocess` / `orchestrate_annual_rolling_selection`。
- `tests/strategy1/test_package_boundaries.py` 新增 Batch 1 兼容符号快照与反向 import 计数断言，覆盖 `bq_io` / `config` shim 的跨文件引用符号和模块级常量；旧模块路径未加入 retired-lint ban-list。
- 本轮不改训练、回测、ledger、orchestrator 调度语义，不触碰 Cloud Run job spec/args/镜像/IAM，不写 BigQuery/GCS。
- 最终验证通过：`python3 -m pytest -q tests`（268 passed）；`python3 -m pytest -q tests/strategy1/test_package_boundaries.py`（6 passed）；`python3 -m pytest -q tests/strategy1/test_cloudrun_package_entrypoints.py`（16 passed）；`PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`；`python3 -m compileall -q src scripts tests`；`git diff --check`；`python3 scripts/dataform/generate_sqlx_from_sql.py --check`。

### 最新补充（2026-06-12）：PR #202 Claude review F2-F11 已修复，F1 留 owner 数据决策

- PR #202 review follow-up 已完成代码面 F2-F11：staleness watermark 不再被 `p_predict_end` 截断、catalog 声明 direct base table、`experiment_json` 对四入口保持最高优先级、SQL 同构 guard 收紧并覆盖 review seeded mutations、acceptance/selection/train_predict 纯函数测试补强、scanner/manifest path/docstring/边界 token_map 已修正。
- F1 不执行数据补采、不写 BigQuery/GCS。Claude 实跑发现现存 CA-on baseline 对 `QA-CA-LEDGER-0` 会失败，真实缺口为 dividend 数据 `2026-05-28..2026-06-09` 未采集，`ods_tushare_dividend` 当前 max partition/date 为 `2026-05-27`；断言语义正确且未放宽，PR body 已如实说明。
- F2 口径：当前 `source_partition_date_max` 来自 DWD dividend event 的事件/分区日期，不能作为精确 ingestion watermark；本轮改为 full-table 可见上界检查（上限 `CURRENT_DATE('Asia/Shanghai')`）。精确 ingestion watermark 需要新增 source ingestion 列或修复 ingestion meta；后者当前另有 0-row 事件，留 owner 决策。
- §2.6 取舍：v3 contract 主路径在缺 v3 metrics 时先返回 `v3_acceptance_metrics=missing`，legacy `decide_acceptance` 主路径对 v3 contract 不强造测试；已改为测试该路由并补齐 legacy helper gate 覆盖。`select_candidate([], [], None)` 的 `IndexError` 作为当前行为被 characterization test 固定，本 PR 不改生产语义。
- 验证通过：`python3 -m pytest -q tests`（266 passed）；`python3 scripts/dataform/generate_sqlx_from_sql.py --check`；`git diff --check`；`cd /tmp && python3 -m pytest /Users/fisher/Desktop/git/worktrees/quant-ashare-prd04/tests --collect-only -q`（266 collected）；`bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_corporate_action_ledger_outputs.sql`。本轮仍未改回测/训练/组合语义，未改默认 `corporate_actions='none_v1'`，未触碰 Cloud Run job spec/镜像/IAM，未写 BigQuery 生产数据。

### 最新补充（2026-06-12）：PRD_20260612_04 工程护栏与测试补强已实现

- 分支 `codex/prd04-guardrails` 按已定稿 PRD §2.1-§2.7 完成实现，分 7 个主题提交：dividend staleness 断言与恢复路径、active step catalog 必填键校验、指标定义 freeze pytest、11 对 window SQL 文本同构 guard、四入口 experiment resolver 合一、acceptance/selection/train_predict 纯函数表驱动测试、pytest scaffold 与仓库外 collect 支持。
- `qa_corporate_action_ledger_outputs` 新增 `QA-CA-LEDGER-0`：当 `corporate_actions != none_v1` 时，若 `predict_end` 晚于 `ashare_dwd.dwd_stock_dividend_event.source_partition_date_max` 可见上界则 fail-fast；README 与 `KNOWN_CONSTRAINTS.md` 记录过渡政策和完整恢复路径（dividend ODS backfill -> dwd/12 -> qa/14 -> ledger QA）。
- `resolve_experiment` 公共逻辑迁至 `src/quant_ashare/strategy1/experiment_resolution.py`；`train_predict` 的 `--manifest-resolved` 旧语义保留，`backtest_report/reporting` 对 `--manifest-resolved` 选择 fail-fast，并用测试确认当前 orchestrator/backtest command builder 不传该参数。
- 新增测试覆盖：catalog contract、metric definition allowlist、window SQL 同构负向 seeded mutation、v3 acceptance / legacy helper 阈值边界、candidate ranking / selection 边界、valid signal / orientation / complexity / CV missing path、CLI module runner fixture 和仓库外 pytest collect。
- 验证通过：`python3 -m pytest -q tests`（243 passed）；`python3 scripts/dataform/generate_sqlx_from_sql.py --check`；`git diff --check`；`cd /tmp && python3 -m pytest /Users/fisher/Desktop/git/worktrees/quant-ashare-prd04/tests --collect-only -q`（243 collected）；`bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_corporate_action_ledger_outputs.sql`。本轮未改回测/训练/组合语义，未改默认 `corporate_actions='none_v1'`，未触碰 Cloud Run job spec/镜像/IAM，未写 BigQuery 生产数据。
