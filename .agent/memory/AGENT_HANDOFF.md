# Agent 交接（Agent Handoff）

本文件保存供后续 Agent 使用的最新交接记录。新交接用 `templates/HANDOFF_TEMPLATE.md` 追加到底部，并同步刷新下面的「当前交接摘要」。

> **语言约定（2026-06-01 起）**：新增交接条目一律用中文撰写；下方此前的英文历史条目保留原样作为记录，不回译。

## 当前交接摘要

**项目记忆瘦身归档（2026-06-05）**：`AGENT_HANDOFF.md` 已按 owner 要求整理，当前文件只保留启动摘要、归档清理交接和最近 3 条交接；较早的 30 条交接已追加到 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。常规启动优先读本文件；需要审计历史时再读 archive。

**OQ-005 告警/观测生产闭环部署与 PR #75 follow-up（2026-06-05）**：工作树 `/private/tmp/oq005-alerts-ops`，分支 `codex/oq005-alerts-ops`。已完成：8 个 BigQuery 观测视图创建、3 个 Cloud Logging log-based metrics 创建、3 个 Cloud Monitoring alert policies 启用（Ingestion severity 已从 CRITICAL 修正为 WARNING）、Email 通知渠道配置并关联到 3 个策略、定时 checker DAG `oq005_alert_checker` 部署（每 10 分钟）、三类告警 smoke 验证（pipeline_failure / task_failure / ingestion_failed 均在 timeSeries 中 value=1）。PR #75 review follow-up 已修复 README 生产入口、OQ-005 状态矛盾、DAG 意外返回码静默成功、checker liveness 缺失和 10 分钟 lookback 无重叠问题：DAG 只接受 rc `0/1/2`，其他 rc fail-closed；生产 lookback 改 20 分钟；`check_alerts.py` 新增 `--write-heartbeat`；`setup_alerts.py` 新增 `oq005_alert_checker_heartbeat` metric 与 30 分钟 absence policy，并修复 Monitoring API duration / condition enum / condition field 写法。验证通过 py_compile、`setup_alerts.py --dry-run`、只读 `check_alerts.py --json`、Monitoring condition 构造、观测 SQL dry-run、`git diff --check`。该 follow-up 尚未同步 Composer bucket 或应用新增 liveness policy；合并后需部署并验收 checker heartbeat absence 告警。下一步：合并 PR 后继续 Dataform definitions、补跑和完整 ODS→ADS 运维观测闭环。

**OQ-005 告警/观测 PR #72 review follow-up（2026-06-05）**：工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-alerts-runbook`，分支 `codex/oq005-alerts-runbook`。PR #72 新增 BigQuery 观测视图、Cloud Logging / Cloud Monitoring 告警配置脚本、告警查询脚本和补跑 runbook。本轮按 comment 修复：`setup_alerts.py` 的 `LogMetric` 使用正确 `filter` 字段；`check_alerts.py` 查询失败和缺 `google-cloud-logging` 写日志路径均 fail-closed，默认 lookback 改 10 分钟并用稳定 `insert_id` 降低重复日志；runbook §9 的 `task_failure` / `ingestion_failed` 与 SQL 实现一致；`v_alert_probe` 注释改为固定 24 小时手工健康检查口径。验证通过 Python `py_compile`、观测 SQL BigQuery dry-run、`git diff --check`；本机缺 `google-cloud-logging`，未做真实 log metric API apply。合并后仍需部署视图、配置 Cloud Scheduler/Cloud Run checker、log-based metrics、alert policies，并做生产 smoke。

**OQ-010 当前路线（2026-06-05）**：owner 已决定后续不再使用 BQML 或 `sql/ml/strategy1` SQL runner 作为策略训练、预测、回测、报告、诊断、月度滚动重训或多实验搜索的默认 / fallback / 新增开发路线；该决策已写入 `DECISION-20260605-03`。历史 BQML 最优组合 `pv_fin_quality + 30/5% + biweekly + 5d` 仅作 reference / audit。PR #76 follow-up 已在 `docs/prd/PRD_20260604_02_策略1月度滚动重训.md` 文首补 superseded banner；正文仍待后续改造成 Cloud Run Python / backend-neutral prediction stream。下一步应寻找可接受的 Cloud Run Python 模型 / backend baseline。

**OQ-010 已收口事实（2026-06-05）**：Ledger v1 P1 extended fresh run `s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` 覆盖 `2024-01-02` 至 `2026-04-30`，total_return 35.16%、excess_return -7.22% vs `000852.SH`；P2 resume run `s1_bqml_baseline_pvfq_n30_bw_h5_resume_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_resume_20260604_01` 通过 `sql/ml/strategy1/15_qa_ledger_resume_consistency.sql`。sklearn native search 首轮 `sklearn_native_pvfq_n30_bw_h5_20260605_01` 已完成，Top5 均因 `test_year_excess_return<=0.0` 被拒绝，本轮不建立 `cloud_run_sklearn_native_baseline_v1`。

**OQ-005 / OQ-012 当前状态（2026-06-05）**：OQ-005 已完成 current-scope 生产采集、Composer DAG/SQL 部署验收、20 日窗口 DWD/DWS smoke 和 readiness 门禁复核；仍 open，剩余 Dataform 生产链路、告警、补跑和完整运维观测闭环。OQ-012 当前 BigQuery 读层 `sql/qa/06_ods_parquet_schema_checks.sql` 对 P0 与 all 范围均通过，待 owner 决定关闭/归档或保留 schema contract / ingestion 显式 cast 防复发任务。

**常规约定**：评审默认写 GitHub PR comment；TODO 只保留下一步可执行事项，待 owner 决策问题以 `OPEN_QUESTIONS.md` 为唯一来源。PR 合并后，若 owner 未要求保留工作分支，应删除已合并且不再使用的 `codex/*` 本地分支和对应远端分支。

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
相关 issue/PR: memory archive cleanup

### 已完成工作

- 按 owner 要求整理项目记忆，将 `AGENT_HANDOFF.md` 中较早的 30 条交接追加归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。
- 当前 `AGENT_HANDOFF.md` 保留当前摘要、归档清理交接和最近 3 条交接，降低常规启动读取成本。
- 保留 `DECISION-20260605-03` 与当前 OQ-010 路线：后续不再使用 BQML / `sql/ml/strategy1` SQL runner，历史 BQML 仅作 reference / audit。
- 按 PR #76 review comment，在 `docs/prd/PRD_20260604_02_策略1月度滚动重训.md` 文首补 superseded banner，提示不得按旧 BQML / SQL runner 口径直接实现。

### 重要上下文

- 本次整理记忆文件，并给月度滚动重训 PRD 增加状态 banner；不改代码、SQL 或 BigQuery/GCS 产物。
- 归档是搬运历史交接，不删除审计信息。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`

### 测试 / 验证

- `git diff --check` 通过。

### 阻塞项

- 无。

### 下一步建议

- 后续常规启动只读 `AGENT_HANDOFF.md` 的当前摘要和最近交接；需要审计历史时再读 archive。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-010 / DECISION-20260605-03 / memory-only update

### 已完成工作

- 按 owner 明确指令，将“后续不再使用 BQML 以及 `sql/ml/strategy1` SQL runner”写入项目长期记忆。
- 新增 `DECISION-20260605-03: 策略执行层后续停止使用 BQML 与 SQL runner`。
- 同步约束、项目上下文、实现状态、开放问题和 TODO，使后续 OQ-010 不再把 BQML baseline / SQL runner 作为默认或 fallback 路线。

### 重要上下文

- 历史 BQML baseline、SQL runner、报告和 QA 结果仍保留为 reference / audit，不删除、不改写历史事实。
- BigQuery SQL 仍继续用于 ODS→DIM/DWD/DWS/ADS 数仓转换、metadata、单位契约、QA、状态表和只读分析；本决策只废弃策略执行层 SQL runner。
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md` 仍是旧口径，真正实现前必须先改为 Cloud Run Python / backend-neutral 口径。

### 改动文件

- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 待执行 `git diff --check`。
- 未执行 SQL / Python / Cloud Run，本次仅更新项目记忆。

### 阻塞项

- 无。

### 下一步建议

- 先寻找可接受的 Cloud Run Python 模型 / backend baseline。
- 在实现月度滚动重训前，先改造 `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`，移除 BQML / SQL runner 执行口径。

### 已更新记忆文件

- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01 / s1_bqml_baseline_pvfq_n30_bw_h5_resume_20260604_01
相关 issue/PR: OQ-010 / Ledger v1 P1/P2 2026 extended and resume closeout

### 已完成工作

- 取消误启动的重复 2026 扩展 BigQuery job `bqjob_r2337986e7fdea586_0000019e9752fad3_1`。
- 删除无效 run_id `s1_bqml_baseline_pvfq_n30_bw_h5_ext20260430_v20260605_01` / backtest_id `bt_s1_bqml_baseline_pvfq_n30_bw_h5_ext20260430_v20260605_01` 在 ADS 训练面板、registry、prediction、candidate、portfolio、order 和 backtest 相关表中的残留。
- 复核无效 run 在 10 张相关 ADS 表中均为 0 行。
- 复核已有 P1 extended fresh run：`s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01`，窗口 `2024-01-02` 至 `2026-04-30`。
- 复核已有 P2 resume run：`s1_bqml_baseline_pvfq_n30_bw_h5_resume_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_resume_20260604_01`，从父回测 `2025-12-31` 状态恢复。
- 执行 `sql/ml/strategy1/15_qa_ledger_resume_consistency.sql`，6 个断言全部通过。

### 重要上下文

- Extended fresh run 指标：total_return 35.16%、excess_return -7.22% vs `000852.SH`、Sharpe 0.819、max_drawdown -14.46%。
- 2026 段（`2026-01-05` 至 `2026-04-30`）策略收益 -2.45%；同期中证1000 +10.36%、沪深300 +3.83%、上证50 -1.51%，策略分别跑输 12.81pct / 6.28pct / 0.95pct。
- Resume consistency QA 证明 resume segment 与 full fresh run 在 NAV、现金、日收益、持仓和成交事实上一致。
- 该 BQML baseline 已转为历史 reference / audit；Cloud Run sklearn parity/native acceptance 仍未通过，后续需寻找可接受的 Cloud Run Python baseline。

### 改动文件

- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- BigQuery cleanup DML 成功，删除无效 run 残留。
- BigQuery 计数复核：10 张相关 ADS 表中该无效 run/backtest 均为 0 行。
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/15_qa_ledger_resume_consistency.sql`
- BigQuery 查询复核 extended/resume summary、2026 分段和季度 benchmark 对比。
- `git diff --check`

### 阻塞项

- 无执行阻塞。

### 下一步建议

- 寻找可接受的 Cloud Run Python 模型 / backend baseline。
- 实现月度滚动重训前，先把 `docs/prd/PRD_20260604_02_策略1月度滚动重训.md` 改造为 Cloud Run Python / backend-neutral 口径。
- 继续 OQ-005 Dataform、告警、补跑和运维观测闭环。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: sklearn_native_pvfq_n30_bw_h5_20260605_01
相关 issue/PR: sklearn native search Top5 runtime fix

### 已完成工作

- 在 `main` 部署镜像后启动真实 sklearn native search；补建 `s1_sklearn_native_pvfq_n30_bw_h5_20260605_01` 训练面板 3,055,781 行。
- 确认 `prepare_matrix` 成功（`strategy1-prepare-matrix-job-d697c`，4m04s）和 36 个 candidate task 全部成功（`strategy1-train-candidate-fanout-job-tpl9v`，1m24s）。
- 定位 Top5 后处理两个工程问题：本地 ranking 阶段下载/反序列化 `model.joblib` 不必要；Top5 并发写 `ads_model_registry` 触发 BigQuery 429 table update 限流。
- 修复 ranking-only candidate 加载：orchestrator 本地阶段只下载 `candidate_metrics.json` / `task_status.json`，`load_candidates(load_models=False)` 不要求也不加载 `model.joblib`。
- 修复 BigQuery load 瞬时限流：`load_dataframe` 对 `google.api_core.exceptions.TooManyRequests` 做退避重试。
- 取消不完整 Top5 backtest execution：`strategy1-backtest-report-job-pbr24`、`strategy1-backtest-report-job-mcpmc`、`strategy1-backtest-report-job-44qml`。

### 重要上下文

- 36 candidate 并发训练本身没有失败；失败发生在 Top5 select/register/predict 同时写同一张 ADS 表。
- 本修复需要合并并重建/部署 Cloud Run 镜像后才会影响容器端 select/register/predict。
- 后续可复用已成功的 prepare/fanout artifact，用同一 `search_id` 加 `--resume --force-replace` 重跑 Top5。

### 改动文件

- `scripts/strategy1_cloudrun/bq_io.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1_cloudrun/select_register_predict.py`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/bq_io.py scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py scripts/strategy1_cloudrun/select_register_predict.py scripts/strategy1_cloudrun/train_predict.py`
- 小样例验证 `load_candidates(load_models=False)` 不需要 `model.joblib` 且不调用 `joblib.load`。
- 小样例验证 `load_dataframe` 对 `TooManyRequests` 重试并按 10s/20s 退避。
- `orchestrate_sklearn_native_search --dry-run` 展开 36 candidate / Top5 plan。
- `git diff --check`

### 阻塞项

- 无代码阻塞；需要合并后重建 Cloud Run 镜像并重跑 Top5 才能完成 native search 验收。

### 下一步建议

- 提 PR 并合并本修复。
- 重建并部署 `strategy1-cloudrun-runner` 镜像到 prepare/candidate/select/backtest jobs。
- 用 `search_id=sklearn_native_pvfq_n30_bw_h5_20260605_01` 执行 `orchestrate_sklearn_native_search --resume --force-replace`，重跑 Top5，随后跑 `18` QA 并判断是否接受 sklearn native baseline。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
