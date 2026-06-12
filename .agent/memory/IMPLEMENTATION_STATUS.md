# 实现状态（Implementation Status）

这是实现状态的唯一事实来源。面向「已完成/进行中/受阻的整体状态」；「下一步要做什么」见根目录 `TODO.md`。

Last updated: 2026-06-12

## 当前状态快照

### 数仓分层与数据覆盖

- P0 数仓底座已完成：ODS→DIM/DWD→DWS→ADS 分层稳定，核心 DIM/DWD/DWS/ADS、单位契约、benchmark 口径和财务三大报表链路已物化并通过 QA。
- ODS schema mismatch（OQ-012）已关闭；新增 / 修复 ODS Parquet 必须按 schema contract 显式 cast 并运行对应 QA。
- true-five-year 数据覆盖修复已完成：2010-2014、2015Q1、`2019-01-02..2019-04-02` 覆盖补齐，`13_true5y` 与逐年 refit panel coverage QA 是后续 true-five-year 重跑硬门。

### 采集与调度

- 生产调度唯一入口已迁到 `Cloud Scheduler + Cloud Workflows`；`ashare-composer` 已删除，Composer 目录仅保留为 retired / audit-only 历史快照。
- OQ-005 当前只剩 post-cutover 观察记录与 2026-06-12 scheduled ingestion 审计链路验证；窗口刷新正确性依赖 `sql/qa/10_windowed_stock_refresh_checks.sql` 与 review。

### Strategy1 执行层与 baseline

- Strategy1 普通实验默认写 `ashare_research.research_*`，ADS 正式发布只能走 owner-approved promotion；旧 BQML / SQL ledger runner 仅作 historical reference / audit。
- 当前研究 baseline 数字为 true-five-year CA-on：prediction `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01`，backtest `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01`，CAGR `15.35%`、v3 contract Sharpe `0.6682`、Calmar `0.4101`。
- baseline 仍不等于 accepted：Sharpe 距 0.70 门约 `0.032`，Calmar `< 1.0`；不得 promotion。后续实验一律显式 `corporate_actions=cash_div_and_split_v1` / `dividend_tax_mode=flat_10pct`。

### QA 与契约

- Cloud Run Python / native Strategy1 路线、lot-aware ledger、resume、synthetic continuous、research routing、promotion review-only、CA ledger QA 均已形成契约化测试或 SQL QA；PRD_20260612_04 已补 CA staleness、catalog、metric freeze、window SQL 同构、resolver 和纯函数测试护栏。
- `tests/strategy1/test_topdown_lot_phase0.py` 依赖项目记忆解析当前 baseline id；任何记忆重排必须保留 CA-on baseline 段落或让 `DECISION_LOG` 近期全文可解析。

### 工程治理与记忆体系

- PRD_20260612_03 已把主记忆文件压缩为快照 / 索引 / 近期条目结构；历史编年史和决策全文原文归档到 `.agent/memory/archive/`。
- PRD_20260612_05 Strategy1 包结构 Phase E 收尾已完成 Batch 1/2：`bq_io.py` / `config.py` / `state.py` / `task_fanout.py` / runner `__version__` 已迁入 `src/quant_ashare/strategy1/`，scripts 侧保留兼容 shim，src 对这些模块及 `dataset_roles` / `acceptance` / `__version__` 的反向 import 已清零；Batch 3 仍待单独 PR，剩余 src→scripts import 仅限 `feature_sets` / `preprocess` / `orchestrate_annual_rolling_selection`。
- `KNOWN_CONSTRAINTS.md` 只做保守拆行和结构化映射，操作性语义不删除；全量 before/after 映射见 `docs/prd/PRD_20260612_03_KNOWN_CONSTRAINTS映射表.md`。

### 开放主线

- `OPEN_QUESTIONS.md` 只剩 OQ-010：继续寻找可 accepted 的 Cloud Run Python baseline / 组合构造 / 风控路线。
- PRD_20260611_10 topdown Phase 0 / Phase 2、尾部风险后续路线、R14 长训练窗口覆盖审计和 OQ-005 短观察窗仍是待办方向，具体下一步以 `TODO.md` 为准。

## 最近补充（最近 7 条）

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

### 最新补充（2026-06-12）：baseline 数字切换为 CA-on 口径（DECISION-20260612-03），PRD_20260612_02 全三阶段收口

- Phase C CA-on 重跑完成：backtest `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01`（execution `strategy1-backtest-report-job-dnt4b`），continuous/lot-aware/CA 三套 QA 通过，ADS 反向 0 行。新锚点：CAGR=`15.35%`、contract Sharpe=`0.6682`、Calmar=`0.4101`。
- 六项偏差分解桥精确闭合（hfq 估计 − CA-on = 3.5066pp = 税 0.7283 + 现金滞留 2.7920 + 取整 0 + 聚合 0 + 因子残差 -0.0138，unexplained < 1e-9pp）。
- v3 gates：Sharpe 距 0.70 门 0.032、Calmar 0.4101 < 1.0——baseline ≠ accepted、不得 promotion；测量仪已修正，剩余缺口为真实 alpha/结构缺口（OQ-010）。
- 纪律：后续实验一律显式 CA-on（代码默认 none_v1 不变）；PRD_20260611_10 Phase 2 等后续工作的对照与参数随之切换。

### 最新补充（2026-06-12）：Ledger 分红送转 Phase C research-only 重跑完成

- 分支 `codex/ledger-corporate-actions` 已按 `PRD_20260612_02` Phase C 完成 true-five-year CA-on continuous 重跑。新 Cloud Run runner 镜像使用 one-off tag `ledger-ca-phasec-43404e6-20260612-01`，不可变 digest `sha256:769c8e911cc7c660f53cad3cbe3ea5f1a9f6dd502f6e188e7ebfa3dc001ab957`；未更新 `latest` tag。`strategy1-backtest-report-job` 仅 pin 到该 digest（generation `51`），boot smoke execution `strategy1-backtest-report-job-97b5v` 成功。
- 正式 research-only execution `strategy1-backtest-report-job-dnt4b` 成功；run `s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01` / backtest `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01` 复用 synthetic prediction run `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01`，参数为 `corporate_actions=cash_div_and_split_v1`、`dividend_tax_mode=flat_10pct`，输出仅写 `ashare_research`。
- 产物行数：candidate `279625`、target `2780`、order `4830`、trade `4856`、position `21162`、NAV `1314`、ledger_state `1314`、summary `1`。summary CA 审计：audit rows `75`（现金分红 `73`、送转 `2`），税后现金入账 `6554.9556` 元，flat 10% 税 `728.3284` 元，送转增股 `90` 股。
- QA 全部通过：`qa_continuous_backtest_outputs` job `06273525-830b-4603-8503-2dc8f3091ca4`；`qa_lot_aware_ledger_outputs` job `1eec4250-5da4-44c1-bab7-ba3183dc14d5`；`qa_corporate_action_ledger_outputs` job `37674e4f-06ee-4998-9d1e-75ace14cb965`。三条 QA 的 research dry-run 也均通过。ADS run/backtest scoped 10 表反向验证为 `0` 行，`research_promotion_manifest` 为 `0` 行。
- 三方对照报告已新增 `docs/分析-Ledger CA 重跑对照-20260612.md`。CA-on 结果：total return `1.1044714853774122`、compound CAGR `0.15350594766603387`、MaxDD `-0.3742978588042647`、v3 contract Sharpe `0.6682084282261871`、Calmar `0.4101170873817589`、IR `0.6971241900405605`。相对 raw baseline 改善但仍未过 v3 hard gates（Sharpe `<0.70`、Calmar `<1.0`），不得标 accepted / promotion。
- Phase C 六项分解已闭合：hfq proxy 相对 CA-on terminal total return 高 `3.5066pp`；`tax_effect=+0.7283pp`，`cash_not_reinvested_effect=+2.7920pp`，`split_fractional_rounding_effect=0`，`same_ex_date_event_aggregation_effect=0`，`event_vs_adj_factor_residual=-0.0138pp`，`unexplained_residual=0`。Phase A mismatch 在 Phase C 窗口全部已分类：event_to_factor data_anomaly `1106`、special_dividend `1`、factor_to_event same_day_orphan_corporate_action `350`、unclassified `0`。
- 本阶段未改现役 baseline 数据、未 promotion、未改全局默认 profile、未跑 PRD_10 Phase 2。owner 仍需按报告中三组选项裁决是否切换 baseline 口径、如何 supersede 旧未复权约定，以及后续实验是否一律 CA-on。

### 最新补充（2026-06-12）：Ledger 分红送转 Phase B 已实现并完成本地验证

- 分支 `codex/ledger-corporate-actions` 在 Phase A 事件层之上完成 ledger 侧实现：`LedgerParams` / `Experiment` / CLI / Cloud Run dry-run plan / `build_sql_params` / `build_metrics_and_report_inputs` / catalog / QA / resume 两套 QA 均已接入 `corporate_actions` 与 `dividend_tax_mode`。默认仍为 `none_v1` / `flat_10pct`，`ledger_params_hash` 只在非默认值时写入新增参数，默认黄金 hash 保持 `2108e411d056418b09c84f99b75021a5329fea58eb474d5906e0e4287f69cc0d`。
- `run_ledger` 在每个 `ex_date` 开盘前先消费 `ashare_dwd.v_dwd_stock_dividend_event_ledger_consumable`，先按 record_date entitlement 做送转调股数 `floor` 并写 `CORPORATE_ACTION_SPLIT` 审计行，再按 record_date 股数和 flat 10% 税率写 `CORPORATE_ACTION_CASH_DIVIDEND` 现金入账；同日调仓仍是 CA 后交易。ledger 不直读 ODS，也不读 mismatch/anomaly 明细表。
- 新增 `qa_corporate_action_ledger_outputs`，并让 `qa_runner_outputs` / `qa_lot_aware_ledger_outputs` / `qa_ledger_resume_consistency` / `qa_cloudrun_ledger_resume_outputs` 用 COALESCE 兼容旧 summary key，同时校验父子 CA 参数一致。默认不变量用固定时间戳小 fixture 逐表 JSON 字节比较，并锁定 hash 黄金值。
- 验证：`python3 -m pytest tests` 176 passed；`PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint` 通过；`python3 -m compileall src scripts` 通过；Dataform generator `--check` 和 `npx --yes @dataform/cli compile dataform` 通过；`qa_corporate_action_ledger_outputs` research BigQuery dry-run 通过；`git diff --check` 通过。
- 本阶段未执行 Phase C、未跑 live backtest、未改既有 run、未 promotion、未改全局默认 profile、未触碰 `scripts/strategy1_cloudrun/bq_io.py`。下一步是提交/推送并等待 Claude review，review 通过后才可进入 Phase C research-only 重跑。
