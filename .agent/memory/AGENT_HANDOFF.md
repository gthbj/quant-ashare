# Agent 交接（Agent Handoff）

本文件保存供后续 Agent 使用的最新交接记录。新交接用 `templates/HANDOFF_TEMPLATE.md` 追加到底部，并同步刷新下面的「当前交接摘要」。

> **语言约定（2026-06-01 起）**：新增交接条目一律用中文撰写；下方此前的英文历史条目保留原样作为记录，不回译。

## 当前交接摘要

**OQ-010 尾部风险 P0 诊断实现（2026-06-06）**：PR #84（`docs/prd/PRD_20260606_01_策略1尾部风险控制.md`）已合并，PRD 分支已清理。当前实现工作树 `/Users/luna/Desktop/git/quant-ashare-tail-risk-impl`，分支 `codex/implement-tail-risk-diagnostics-p0`，PR #87。已新增只读 `scripts/strategy1/analyze_tail_risk.py`、Cloud Run `backtest_report.py` 自动执行入口、TopK comparison 尾部风险摘要和 `sql/ml/strategy1/20_qa_tail_risk_outputs.sql`；产物写入 `tail_risk/` local/GCS artifact，覆盖最大回撤窗口、持仓贡献、跌停 / 不可卖暴露、选股画像、风险股票名单和 ADS pre/post hash guard，不改变候选、订单、成交、持仓、NAV 或 summary。已用 Wave 3 regression Top1 完成本地 artifact smoke 和真实 `20` QA。P1 个股硬风险过滤 profile A/B 与 P2 市场状态 risk-off 仍待后续独立实现。

**OQ-005 Composer DAG 拆分 PRD（2026-06-06）**：工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-dag-split-prd`，分支 `codex/oq005-dag-split-prd`。新增 `docs/prd/PRD_20260606_02_OQ005ComposerDAG拆分.md`，定义将当前 `ashare_daily_pipeline_v0` 拆成 `ashare_ods_ingestion_daily`、`ashare_warehouse_window_refresh`、`ashare_warehouse_full_rebuild`、`ashare_research_model_experiment`、`ashare_research_model_fanout`，`oq005_alert_checker` 继续独立。本次只写 PRD 和记忆/TODO，不改 DAG、不部署 Composer、不运行 BigQuery / Dataform / Cloud Run。后续建议先实现 production DAG 拆分 Phase B/C/D：抽共享 helper，新增 ingestion daily DAG 与 warehouse window refresh DAG，完成开市日、非交易日和 backfill smoke 后再继续 Dataform definitions / resume 自动化。

**OQ-010 PRD04 Wave 3 执行收口（2026-06-06）**：工作树 `/Users/luna/Desktop/git/quant-ashare-prd04-wave3`，分支 `codex/fix-prd04-prepare-matrix-parallelism`，PR #82。PR #79 合并后已部署 Cloud Run runner；本分支修复 `prepare_matrix()` requested parallelism 作用域 bug，并补 BigQuery JSON sanitizer，避免 regression `roc_auc/log_loss` 的 NaN 写入非法 `metrics_json`；PR #82 review follow-up 已补 `NaT` / `pd.NA` / `NaN` / `inf` 转 `null`、`np.ndarray` / pandas 标量递归转换和 `default=str` 兜底，并把状态表 `params_json`、GCS lock payload、work-unit manifest/hash 等 runner JSON 路径统一到 strict helper。最终镜像 `prd04-7d8daec-20260606-01` 已构建并部署到五个策略 Cloud Run Jobs。Wave 3 `cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01` 已完成：12 个 regression 候选、Top5 回测/报告/诊断和 `19` QA 全部通过，Top5 全部 rejected，当前仍不建立 `cloud_run_python_baseline_v1`。后续建议进入 PRD04 下一模型族 / 特征增强路线，或先分析回撤过大原因。

**OQ-005 非交易日 skip gate 已部署验收（2026-06-06）**：PR #83 已合并到 `main`（`3723f52`），`ashare_daily_pipeline_v0.py` 已同步到 Composer bucket `gs://asia-east2-ashare-composer-b2629133-bucket/dags/`，本地与 bucket SHA256 均为 `e4b07ba402716b914bfbd6fe27fa38f97fab8e1c12f6a0bcce9e5fd8c58696af`。`manual_smoke_skip_non_trading_day_pr83_20260606_02` 使用 `business_date=2026-06-06`、`warehouse_mode=daily_current`、`force_non_trading_day_gate=true`、`pipeline_dry_run=true` 成功：`non_trading_day_gate=success`、`skip_non_trading_day=success`，`pipeline_task_status` 写入 `skip_non_trading_day status='skipped'`，ingestion/readiness/transform 全部 skipped，Cloud Run 最新 execution 仍为 01:53 的旧 PR #80 run，未被 smoke 触发。DAG 当前 active/unpaused、无 import errors。首次 smoke `manual_smoke_skip_non_trading_day_pr83_20260606_01` 在 Composer 新旧 serialized DAG 切换窗口内走到旧路径，已中止、确认未触发 Cloud Run，并在 `pipeline_run` 标为 `partial` 防止假告警；`v_alert_summary` 对两次 smoke 为空。

**OQ-005 PR #83 记忆一致性 follow-up（2026-06-06）**：PR #83 review comment `4637354942` 指出 `IMPLEMENTATION_STATUS.md` 已完成区仍残留旧的部署等待状态。已将相关 durable bullet 改为“后续已由 PR #80/PR #83 部署与 smoke 覆盖”，并把几条历史补充明确标为部署前状态，避免同一记忆文件内当前状态自相矛盾。

**OQ-010 PRD04 Cloud Run Python baseline search 实现（2026-06-06）**：工作树 `/Users/luna/Desktop/git/quant-ashare-prd04-cloudrun-python-baseline`，分支 `codex/implement-prd04-cloudrun-python-baseline`。PR #79 review follow-up 与 residual follow-up 已完成：共享验收契约阈值注入 `18/19` QA、final_holdout 缺证据改为 `needs_more_evidence`、QA NULL 空过和数据上界断言补齐、split 边界对齐 `2024-01-02` / `2025-01-02`、auto-next-wave 改为当前 wave QA 后非阻断触发，并补资源元数据和 LightGBM convergence 元数据。运行手册已同步 40 候选 / 20 并发 / 2 vCPU 8Gi，`config.py` / `ledger.py` / `01` / `10` 的 fallback 默认日期已对齐 Jan 2 交易日起点，`18/19` 已用 `qa_required()` 让单行 NULL 也 fail，并声明 SQL `DECLARE` 默认只是 standalone fallback、生产必须由 orchestrator 从共享契约注入。真实 LightGBM binary wave 2 search `cloudrun_python_lgbm_pvfq_n30_bw_h5_20260605_01` 已按 `candidate_count=40`、`candidate_parallelism=20`、单 task `2 vCPU / 8Gi` 完成，Top5 均 rejected，不建立 `cloud_run_python_baseline_v1`；`18/19` 真实 QA 均通过。合并部署 PR #79 follow-up 后下一步：执行 `lightgbm_regression` wave 3。

**项目记忆瘦身归档（2026-06-05）**：`AGENT_HANDOFF.md` 已按 owner 要求整理，当前文件只保留启动摘要、归档清理交接和最近 3 条交接；较早的 30 条交接已追加到 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。常规启动优先读本文件；需要审计历史时再读 archive。

**OQ-005 PR #80 部署与 2026-06-05 smoke（2026-06-06）**：当前 `main` 已包含 PR #80，并已完成生产部署：`ashare_daily_pipeline_v0.py` 同步到 Composer `dags/`，仓库 `sql/` 同步到 `gs://asia-east2-ashare-composer-b2629133-bucket/data/sql/`，本地 / bucket DAG 与 `09_ods_daily_partition_readiness.sql` SHA256 一致。`manual_pr80_daily_current_20260605_20260606_01` 使用 `business_date=2026-06-05` 成功完成 current_scope 采集、ODS readiness、窗口 DIM/DWD/DWS 刷新和窗口 QA；采集后 2026-06-05 strong endpoint 行数为 daily 5514、daily_basic 5514、adj_factor 5526、stk_limit 7634、index_daily 7。`manual_pr80_qa_only_20260605_20260606_01` 使用 `skip_ingestion=true` 成功完成 readiness + P0 / strategy1 / OQ004 / finance / OQ006 五个只读 QA。最近 20 个交易日 `2026-05-11..2026-06-05` ODS daily_basic → DWD valuation → DWS valuation 行数均为 110,035，错配天数 0。下一步仍是 Dataform 生产链路、补跑/resume 自动化和完整 ODS→ADS 运维观测闭环；非交易日自动 skip gate 已由 PR #83 合并部署，并通过 `manual_smoke_skip_non_trading_day_pr83_20260606_02` 验收。

**OQ-010 Cloud Run Python baseline 搜索 PRD（2026-06-05）**：工作树 `/Users/luna/Desktop/git/quant-ashare-cloudrun-python-baseline-search`，分支 `codex/prd-cloudrun-python-baseline-search`。新增 `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`：本轮数据截止 `2026-04-30`；train/valid/test/final_holdout 为 `2019-04-03..2023-12-31` / 2024 / 2025 / `2026-01-05..2026-04-30`；固定 `pv_fin_quality + 30/5% + biweekly + 5d`、沪深主板股票池、成本 profile 和 Ledger v1；P0 推荐 LightGBM wave 2。PR #78 review follow-up 后，候选排序改为 2021/2022/2023 三折 purged walk-forward CV + 2024 valid confirmation，2025 test 做硬接受门，2026 final_holdout 只做明显坏结果 veto / holdout watch；实现 smoke 后当前资源口径已从最初 40 并发 / 1 vCPU 4Gi 调整为 40 候选 / 20 并发 / 2 vCPU 8Gi；若 binary LightGBM rejected，后续优先试 `lightgbm_regression`。

**OQ-005 告警/观测生产闭环部署与 PR #75 follow-up（2026-06-05）**：PR #75 已合并并完成生产部署；后续代码收敛工作树 `/private/tmp/oq005-alerting-deploy-followup`，分支 `codex/oq005-alerting-deploy-followup`。已完成：8 个 BigQuery 观测视图创建、3 个 Cloud Logging log-based metrics 创建、3 个 Cloud Monitoring alert policies 启用（Ingestion severity 已从 CRITICAL 修正为 WARNING）、Email 通知渠道配置并关联到告警策略、定时 checker DAG `oq005_alert_checker` 部署（每 10 分钟）、三类告警 smoke 验证（pipeline_failure / task_failure / ingestion_failed 均在 timeSeries 中 value=1）。PR #75 follow-up 已部署并验收：Composer bucket 已同步 DAG 与 `check_alerts.py`；新增 `oq005_alert_checker_heartbeat` log-based metric 和 `OQ-005: Alert Checker Heartbeat Missing` 30 分钟 absence policy，策略已启用并绑定 1 个 Email 通知渠道；`check_alerts.py` 显式使用 `resource.type=global` 写业务告警与 heartbeat，避免 Composer 默认 `k8s_container` resource 与现有告警策略不匹配。PR #77 review follow-up 已修复告警策略幂等键：`setup_alerts.py` 使用稳定 `user_labels.oq005_policy` 并兼容旧 display name 迁移，避免旧名环境重复创建新旧两份策略。manual smoke `manual_oq005_alert_checker_heartbeat_global_20260605_01` 成功，随后的 scheduled run 也成功；Cloud Logging 中 heartbeat 为 `resource.type=global`、`lookback_minutes=20`、`alerts_count=0`，Cloud Monitoring global timeSeries 已有点。下一步：继续 Dataform definitions、补跑和完整 ODS→ADS 运维观测闭环。

**OQ-005 告警/观测 PR #72 review follow-up（2026-06-05）**：工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-alerts-runbook`，分支 `codex/oq005-alerts-runbook`。PR #72 新增 BigQuery 观测视图、Cloud Logging / Cloud Monitoring 告警配置脚本、告警查询脚本和补跑 runbook。本轮按 comment 修复：`setup_alerts.py` 的 `LogMetric` 使用正确 `filter` 字段；`check_alerts.py` 查询失败和缺 `google-cloud-logging` 写日志路径均 fail-closed，默认 lookback 改 10 分钟并用稳定 `insert_id` 降低重复日志；runbook §9 的 `task_failure` / `ingestion_failed` 与 SQL 实现一致；`v_alert_probe` 注释改为固定 24 小时手工健康检查口径。验证通过 Python `py_compile`、观测 SQL BigQuery dry-run、`git diff --check`；本机缺 `google-cloud-logging`，未做真实 log metric API apply。合并后仍需部署视图、配置 Cloud Scheduler/Cloud Run checker、log-based metrics、alert policies，并做生产 smoke。

**OQ-010 当前路线（2026-06-05）**：owner 已决定后续不再使用 BQML 或 `sql/ml/strategy1` SQL runner 作为策略训练、预测、回测、报告、诊断、月度滚动重训或多实验搜索的默认 / fallback / 新增开发路线；该决策已写入 `DECISION-20260605-03`。历史 BQML 最优组合 `pv_fin_quality + 30/5% + biweekly + 5d` 仅作 reference / audit。PR #76 follow-up 已在 `docs/prd/PRD_20260604_02_策略1月度滚动重训.md` 文首补 superseded banner；正文仍待后续改造成 Cloud Run Python / backend-neutral prediction stream。下一步应寻找可接受的 Cloud Run Python 模型 / backend baseline。

**OQ-010 已收口事实（2026-06-05）**：Ledger v1 P1 extended fresh run `s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` 覆盖 `2024-01-02` 至 `2026-04-30`，total_return 35.16%、excess_return -7.22% vs `000852.SH`；P2 resume run `s1_bqml_baseline_pvfq_n30_bw_h5_resume_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_resume_20260604_01` 通过 `sql/ml/strategy1/15_qa_ledger_resume_consistency.sql`。sklearn native search 首轮 `sklearn_native_pvfq_n30_bw_h5_20260605_01` 已完成，Top5 均因 `test_year_excess_return<=0.0` 被拒绝，本轮不建立 `cloud_run_sklearn_native_baseline_v1`。

**OQ-005 / OQ-012 当前状态（2026-06-06）**：OQ-005 已完成 current-scope 生产采集至 `2026-06-05`、Composer DAG/SQL 部署验收、20 日窗口 DWD/DWS smoke、readiness 门禁复核、告警/观测与 alert checker heartbeat；scheduled 非交易日 skip gate 已由 PR #83 合并部署并完成 force hook smoke。OQ-005 仍 open，剩余 Dataform 生产链路、补跑/resume 自动化和完整 ODS→ADS 运维观测闭环。OQ-012 当前 BigQuery 读层 `sql/qa/06_ods_parquet_schema_checks.sql` 对 P0 与 all 范围均通过，待 owner 决定关闭/归档或保留 schema contract / ingestion 显式 cast 防复发任务。

**常规约定**：评审默认写 GitHub PR comment；TODO 只保留下一步可执行事项，待 owner 决策问题以 `OPEN_QUESTIONS.md` 为唯一来源。PR 合并后，若 owner 未要求保留工作分支，应删除已合并且不再使用的 `codex/*` 本地分支和对应远端分支。

> 历史交接已归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-05.md` 和 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。常规启动只需阅读本文件的当前摘要和最近交接；归档仅用于审计追溯。

---

---

## 交接条目

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: oq005_dag_split_prd_20260606
相关 issue/PR: OQ-005 / Composer DAG split PRD

### 已完成工作

- 新建工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-dag-split-prd` 和分支 `codex/oq005-dag-split-prd`。
- 新增 PRD `docs/prd/PRD_20260606_02_OQ005ComposerDAG拆分.md`，定义 OQ-005 多 DAG 目标边界、参数契约、状态观测、迁移顺序、QA 和验收条件。
- 同步 TODO、IMPLEMENTATION_STATUS、OPEN_QUESTIONS、ARCHITECTURE_MEMORY 和 DECISION_LOG；新增 `DECISION-20260606-01`。

### 重要上下文

- 本次只写文档，不改 `orchestration/composer/dags/ashare_daily_pipeline_v0.py`，不部署 Composer，不运行 BigQuery / Dataform / Cloud Run。
- PRD 规定后续先做 production DAG 拆分，再继续 Dataform definitions、补跑 / resume 自动化和完整 ODS→ADS 运维观测闭环；P0 必须包含 `upstream_pipeline_run_id` 跨 DAG 血缘和 refresh-missing watchdog。
- 目标生产拆分的 P0 是 `ashare_ods_ingestion_daily` 与 `ashare_warehouse_window_refresh`；全量重建和研究 DAG 放在后续阶段。

### 改动文件

- `docs/prd/PRD_20260606_02_OQ005ComposerDAG拆分.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check origin/main...HEAD` 通过。

### 阻塞项

- 无。

### 下一步建议

- 实现 Phase B/C/D：抽共享 Composer helper，新增 `ashare_ods_ingestion_daily` 与 `ashare_warehouse_window_refresh`，补 `upstream_pipeline_run_id` 和 refresh-missing watchdog，完成开市日、非交易日和 backfill smoke。
- 新 production DAG 连续通过至少两个开市日 scheduled run 和一个非交易日 skip smoke 后，暂停旧 `ashare_daily_pipeline_v0`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01
相关 issue/PR: PR #82 / OQ-010 / PRD04 Cloud Run Python baseline search / Wave 3 `lightgbm_regression`

### 已完成工作

- 合并后构建并部署 PR #79 镜像 `prd04-e54cd54-20260606103115` 到五个策略 Cloud Run Jobs。
- 启动 `lightgbm_regression` wave 3；首次执行因未带 `--build-training-panel`，`ads_ml_training_panel_daily` 对当前 run_id 为空而失败。
- 使用 `--build-training-panel --force-replace` 重跑，训练面板构建成功：3,246,953 行，日期范围 `2019-04-03` 至 `2026-04-30`。
- 定位并修复 `prepare_matrix.py` 在 Cloud Run 中引用函数外局部变量 `candidate_parallelism_arg` 的 NameError；requested parallelism 现显式传入函数并写入 work units / summary。
- 补 `json_dumps_strict()` / `json_compatible()`，确保写入 BigQuery JSON 字符串列前将 NaN / inf 转成 null；清理本轮 5 条 Top5 registry 中已写入的非法 `roc_auc/log_loss` NaN。
- 按 PR #82 review follow-up 补强 strict JSON helper：保留 `default=str` 兜底，将 `pd.NaT` / `pd.NA` / `NaN` / `inf` 转 `null`，支持 `np.ndarray` 和 pandas 标量，并把状态表 `params_json`、GCS lock payload、work-unit manifest/hash 等 runner JSON 路径统一到该 helper。
- 使用 `--resume` 复用已成功的训练和 Top5 回测步骤，完成 comparison artifacts 上传和 acceptance 回写。
- 构建最终镜像 `prd04-7d8daec-20260606-01` 并部署到五个策略 Cloud Run Jobs。
- PR #82 已 rebase 到最新 `main`。

### 重要上下文

- 当前修复不改变 PRD04 搜索口径、候选配置、验收阈值或 Cloud Run 资源口径。
- Wave 3 已完成；不需要重跑训练或回测。
- Wave 3 的更准确结论：regression 信号在 test 期有正向 RankIC 和正 test excess，但回撤风险不达标，且多数候选 final_holdout 明显跑输中证1000。

### 改动文件

- `scripts/strategy1_cloudrun/prepare_matrix.py`
- `scripts/strategy1_cloudrun/bq_io.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/state.py`
- `scripts/strategy1_cloudrun/task_fanout.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check` 通过。
- `py_compile` 覆盖 `bq_io.py`、`train_predict.py`、`prepare_matrix.py`、`orchestrate_cloudrun_python_baseline_search.py`、`orchestrate_sklearn_native_search.py`。
- `prepare_matrix.py --dry-run` 使用 regression manifest 和 `--candidate-parallelism 12` 通过，输出 `candidate_parallelism_requested=12` / `candidate_parallelism_resolved=12`。
- strict JSON sanitizer 小测试通过：NaN / inf / `pd.NaT` 输出为 JSON null，`np.ndarray` 转为 JSON array。
- Cloud Build 镜像 `prd04-318e79f-20260606-01` 和最终镜像 `prd04-7d8daec-20260606-01` 构建成功；最终镜像已部署到五个策略 Cloud Run Jobs。
- Wave 3 真实执行：`prepare_matrix` succeeded；`train_candidate_fanout` 12/12 succeeded；Top5 `select_register_predict` 与 `backtest_report` 全部 succeeded。
- `sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql` 全部断言通过。

### 阻塞项

- 无。

### 下一步建议

- 合并 PR #82 后删除不再使用的本地和远端分支。
- 若继续 PRD04，进入下一模型族或特征增强；重点分析 regression 候选 max drawdown 超过 -25% 的原因。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: 无
相关 issue/PR: OQ-010 / PRD04 Wave 3 regression tail risk follow-up

### 已完成工作

- 新建工作树 `/Users/luna/Desktop/git/quant-ashare-tail-risk-prd` 和分支 `codex/prd-strategy1-tail-risk-diagnostics`。
- 新增 `docs/prd/PRD_20260606_01_策略1尾部风险控制.md` 草案。
- 创建 PR #84，并按 review comment 完成 5 条 follow-up。
- PRD 基于 Wave 3 `lightgbm_regression` Top5 因 `max_drawdown < -25%` 全部 rejected 的复核结论，定义三阶段方案：
  - P0 固定最大回撤诊断 artifact / 报告 / QA，不改变交易结果。
  - P1 `individual_risk_guard_v0` 个股硬风险过滤 profile A/B。
  - P2 依赖 `dws_market_state_daily` 或等价 artifact 的 market risk-off 风控。
- 同步更新 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和本交接文件。
- Review follow-up 内容：P0 改为 ADS 严格只读并要求 pre/post hash；补 P1 风险字段可得性 / PIT 映射；持仓贡献权重口径钉死为 beginning-of-day；跌停主判据改为 DWD / `stk_limit` 派生源标记，收益阈值只作 fallback；补 top-K 回撤事件切分规则。

### 重要上下文

- P0 是诊断能力，不改变模型、候选池、交易、回测或 NAV；P0 禁止写入任何 ADS 核心表，诊断只落 GCS / 本地镜像 / comparison artifact。
- P1/P2 会改变选股或买入动作，必须作为独立实验验收，不能直接替换 PRD04 baseline search 默认口径。
- PRD 推荐 P1 首轮过滤阈值：`ret_20d < -30%`、`drawdown_20d < -30%`、`limit_down_days_20d >= 2`、`one_word_limit_days_20d >= 1`、`total_mv_cny < 30e8`、`circ_mv_cny < 20e8`；`vol_20d p95` 和 `turnover_rate_ma20 p98` 首轮只标记、不默认硬排除。
- P2 首轮推荐动作是 `skip_new_buys`，不是强制清仓或日内止损。

### 改动文件

- `docs/prd/PRD_20260606_01_策略1尾部风险控制.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check` 通过。

### 阻塞项

- 无。

### 下一步建议

- owner review PRD。
- 若认可，先实现 P0 固定最大回撤诊断和 `20_qa_tail_risk_outputs.sql`，用 Wave 3 Top5 回测做验收。
- P0 合并后再单独做 P1 风险过滤 profile A/B。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: cloudrun_python_lgbm_pvfq_n30_bw_h5_20260605_01
相关 issue/PR: PR #79 / OQ-010 / PRD04 Cloud Run Python baseline search review follow-up

### 已完成工作

- 复核 PR #79 comment，采纳 H1/H2/M1/M2/M3/L1/L2，并对 L3 补充运行元数据澄清；L4 不在本 PR 修改，原因是 CV eval-fold orientation 改成 held-in 定向会改变候选排序语义并要求重跑 wave 2。
- 将共享验收契约 `configs/strategy1/model_acceptance_contract_v1.yml` 的关键阈值注入 `18/19` QA，避免 Python acceptance 与 SQL QA 各自硬编码门槛。
- 修复 final_holdout 缺证据口径：缺失 final_holdout 不再 hard rejected，改为 `needs_more_evidence`；实际明显坏结果仍按契约 veto。
- 修复 `18/19` QA 的 NULL 空过问题、补 prediction / backtest 数据上界断言，并将 split 边界对齐 PRD 的 `2024-01-02` / `2025-01-02`。
- 调整 auto-next-wave：当前 wave QA 先执行，下一波失败不再让父 wave 失败。
- 接入 `allowed_score_orientation` 和 `weak_valid_rank_ic_threshold`，补 `unmatched_acceptance_state` 兜底和 QA。
- 根据真实 LightGBM smoke，将 P0 资源口径从 40 并发 / 1 vCPU 4Gi 调整为 40 候选 / 20 并发 / 2 vCPU 8Gi；Cloud Run Job spec `parallelism=20`，manifest 默认不再二次分批。
- 已把 wave 2 ADS metadata / run status 表中的资源、split、contract、convergence 元数据补齐，真实 `18_qa_sklearn_native_search_outputs.sql` 和 `19_qa_cloudrun_python_baseline_search_outputs.sql` 均通过。
- 继续完成 residual follow-up：运行手册部署命令和兜底示例已同步到 `parallelism=20` / `2 CPU / 8Gi`；`config.py`、Python ledger、`01_build_training_panel.sql` 和 `10_qa_runner_outputs.sql` 的 fallback 默认日期已对齐为 `2024-01-02` / `2025-01-02`；`18/19` QA 用 `qa_required()` 包住 remaining `LOGICAL_AND` 条件，单行 NULL 不再被聚合忽略。
- `18/19` QA 的 `DECLARE` 默认仍保留为 standalone fallback；生产和 orchestrator 路径的事实来源是 `configs/strategy1/model_acceptance_contract_v1.yml` 注入，已在 SQL 注释中写明。

### 重要上下文

- 真实 LightGBM binary wave 2 search `cloudrun_python_lgbm_pvfq_n30_bw_h5_20260605_01` 已完成，Top5 均 rejected，当前不建立 `cloud_run_python_baseline_v1`。
- Wave 2 的更准确结论是：valid / test RankIC 有正向证据，但 2025 test top-minus-bottom、2025 中证1000超额和 2026 final_holdout 风险门没有转化为可接受基线；不要再表述为“test 完全反转”。
- PR #79 合并后需要先构建 / 部署包含 review follow-up 的新镜像，再执行 `lightgbm_regression` wave 3。

### 改动文件

- `Dockerfile.strategy1-cloudrun`
- `configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml`
- `configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`
- `scripts/strategy1_cloudrun/acceptance.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/ledger.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1_cloudrun/prepare_matrix.py`
- `scripts/strategy1_cloudrun/select_register_predict.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `sql/ml/strategy1/01_build_training_panel.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`
- `sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- Python `py_compile` 通过。
- `git diff --check` 通过。
- `01_build_training_panel.sql` / `10_qa_runner_outputs.sql` BigQuery dry-run 通过。
- `18_qa_sklearn_native_search_outputs.sql` / `19_qa_cloudrun_python_baseline_search_outputs.sql` BigQuery dry-run 通过。
- Orchestrator dry-run 确认 manifest 默认 `candidate_parallelism=20` 时产生单个 `--tasks=40` train fan-out step，不再拆两批。
- Orchestrator dry-run 确认 wave 3 regression manifest 解析为 12 候选 / 12 并发 / 2 CPU / 8Gi，split 日期为 `2024-01-02` / `2025-01-02`。
- 真实 BigQuery `18` / `19` QA 均通过。

### 阻塞项

- 无。

### 下一步建议

- 合并 PR #79。
- 构建并部署新 Cloud Run runner 镜像。
- 执行 `lightgbm_regression` wave 3；若仍 rejected，再按 PRD04 进入下一模型族或特征增强讨论。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: manual_pr80_daily_current_20260605_20260606_01 / manual_pr80_qa_only_20260605_20260606_01
相关 issue/PR: PR #80 / OQ-005 production deploy and 2026-06-05 smoke

### 已完成工作

- 将 PR #80 后的 `orchestration/composer/dags/ashare_daily_pipeline_v0.py` 同步到 Composer `dags/`。
- 将仓库 `sql/` 同步到 Composer bucket `gs://asia-east2-ashare-composer-b2629133-bucket/data/sql/`。
- 触发 `business_date=2026-06-05`、`warehouse_mode=daily_current`、`pipeline_dry_run=false` 的生产 run，完成 current_scope 采集、ODS readiness、窗口 DIM/DWD/DWS 刷新和窗口 QA。
- 触发 `business_date=2026-06-05`、`warehouse_mode=qa_only`、`skip_ingestion=true` 的独立只读 QA smoke。
- 更新 `orchestration/composer/README.md`，把手动触发默认日期说明改为 `data_interval_end` 口径。
- 更新 TODO 和项目记忆，去掉 PR #80 “待部署 / 2026-06-05 未采集”的过期状态。

### 重要上下文

- 触发生产 run 前，BigQuery ODS strong endpoint 的 `20260605` 分区仍为 0 行；本次 `daily_current` 因此先执行了 current_scope 采集，再通过 readiness 和窗口刷新。
- PR #80 部署后本地 / Composer bucket 哈希一致：DAG SHA256 为 `e3d4e7a75dc64b28ce8d93081922b62f2a77f201bf99b79f684b661570476b31`，`sql/qa/09_ods_daily_partition_readiness.sql` SHA256 为 `52fe8070a9145756775614cc387724dc35d6a45c29d99b4194eed28f4c3ff0c4`。
- OQ-005 未关闭；非交易日自动 skip ingestion / transform gate、Dataform 生产链路、补跑/resume 自动化仍待完成。

### 改动文件

- `orchestration/composer/README.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 ... < sql/qa/09_ods_daily_partition_readiness.sql`
- `manual_pr80_daily_current_20260605_20260606_01`：Airflow terminal state `success`，2026-06-05 strong endpoint 行数为 daily 5514、daily_basic 5514、adj_factor 5526、stk_limit 7634、index_daily 7。
- `manual_pr80_qa_only_20260605_20260606_01`：Airflow terminal state `success`，readiness + P0 / strategy1 / OQ004 / finance / OQ006 五个只读 QA 均 success。
- `2026-06-05` DWD/DWS 主键唯一；`2026-05-11..2026-06-05` 最近 20 个交易日 ODS daily_basic → DWD valuation → DWS valuation 行数均为 110,035，错配天数 0。

### 阻塞项

- 无。

### 下一步建议

- 实现非交易日自动 skip gate：scheduled 非交易日自动跳过 ingestion / transform 并写 `skip_non_trading_day` 状态行。
- 推进 Dataform definitions / BigQuery Studio pipeline 生产链路。
- 做补跑/resume 自动化和完整 ODS→ADS 运维观测闭环。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: manual_verify_oq005_warning_before_assert_20260606_01 / manual_verify_oq005_dryrun_no_warning_20260606_01 / manual_verify_oq005_nontd_weak_suppressed_20260606_01
相关 issue/PR: PR #80 / OQ-005 readiness review follow-up

### 已完成工作

- 复核 PR #80 comment，认可 warning MERGE 没有实际运行验证、strong ASSERT 前未持久化 warning、dry-run 会写 warning、非交易日 weak 缺失会产生噪声等问题。
- 修改 `sql/qa/09_ods_daily_partition_readiness.sql`：先生成 readiness 结果并在非 dry-run 下前置 MERGE warning，再执行 strong endpoint 阻断 ASSERT。
- MERGE 过滤条件改为 API 行数上限风险或交易日 weak `MISSING_REQUIRED`；非交易日 weak 缺失不写 warning。
- 更新 `docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md`、`TODO.md`、`KNOWN_CONSTRAINTS.md`、`OPEN_QUESTIONS.md`、`IMPLEMENTATION_STATUS.md` 和本交接。

### 重要上下文

- 本 follow-up 只改 PR #80 分支内容；后续 PR #80 已合并，并已按上方 2026-06-06 部署交接同步 Composer bucket。
- 该条记录中的 `2026-06-05` ODS strong endpoint 缺失是合并前验证时点事实；后续 `manual_pr80_daily_current_20260605_20260606_01` 已完成 2026-06-05 采集并通过 readiness。

### 改动文件

- `sql/qa/09_ods_daily_partition_readiness.sql`
- `docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `bq query --dry_run` 验证 `sql/qa/09_ods_daily_partition_readiness.sql`。
- `manual_verify_oq005_warning_before_assert_20260606_01`：`2026-06-05` strong 缺失失败前写入 4 条 weak warning。
- `manual_verify_oq005_dryrun_no_warning_20260606_01`：dry-run 强制分区失败后 `pipeline_task_status` 0 行。
- `manual_verify_oq005_nontd_weak_suppressed_20260606_01`：`2026-06-06` 非交易日强门禁失败后 `pipeline_task_status` 0 行。

### 阻塞项

- 无。

### 下一步建议

- PR #80 合并后，同步最新 `sql/qa/09_ods_daily_partition_readiness.sql` 到 Composer bucket，并按生产路径重跑小 smoke。
- 继续实现非交易日自动 skip ingestion / transform gate 和 `skip_non_trading_day` 状态行。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`


日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #78 / OQ-010 / Cloud Run Python baseline search PRD re-review follow-up

### 已完成工作

- 按 PR #78 re-review comment 继续修订 `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`。
- 采纳建议 A：§9.1 和 Phase B 明确共享验收契约 `configs/strategy1/model_acceptance_contract_v1.yml` 必须取代 sklearn native search 的 `decide_acceptance` 和 `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql` 内联阈值；Python acceptance 与 SQL QA 必须通过同一契约版本追溯。
- 采纳建议 B：Wave 3 顺序改为 binary LightGBM rejected 后优先尝试 `lightgbm_regression`，再考虑 XGBoost / HistGradientBoosting / CatBoost 或特征增强。
- 澄清 CV 表述：独立 walk-forward folds 为 2021/2022/2023，2024 是 valid confirmation，不再重复命名为 `cv_2024`。
- 按 owner 最新确认采纳可选加固：新增 `cv_2021`（train `2019-04-03..2020-12-31`，eval 2021）作为第三个独立 CV fold；`cv_2021` 参与三折排序稳定性计算，但不单独一票否决候选。
- 按 owner 最新要求把 P0 候选规模固定为 `candidate_count=40` / `candidate_parallelism=40` / 单 task 1 vCPU / 4Gi，并写入 PRD、TODO 和记忆。
- 真实执行 `gcloud run jobs update strategy1-train-candidate-fanout-job --region=asia-east2 --parallelism=40`，随后 `gcloud run jobs describe` 复核 `parallelism: 40`。
- 同步 `docs/策略1CloudRun训练回测运行手册.md` 的 candidate fan-out job 部署命令，将共享 Job spec parallelism 从 100 收敛到当前 P0 的 40；同步 `docs/prd/PRD_20260605_02_策略1CloudRun轻量Task并发.md` 的当前最大并发说明。
- 不加换手 / 成本硬门；PRD 风险表要求 comparison report 展示 turnover / cost / economic cost watch，待真实候选暴露问题后再纳入共享契约硬阈值。
- 同步更新 `TODO.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和本交接。

### 重要上下文

- 本次只改 PRD/运行手册/记忆/TODO，并更新真实 Cloud Run Job parallelism；未实现 LightGBM 代码、未执行 BigQuery search。
- 后续实现顺序必须先落共享契约并迁移旧 sklearn acceptance / `18_qa`，再实现新的 LightGBM `19_qa` 和 baseline search。

### 改动文件

- `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`
- `docs/prd/PRD_20260605_02_策略1CloudRun轻量Task并发.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `gcloud run jobs describe strategy1-train-candidate-fanout-job --region=asia-east2` 复核 `parallelism: 40`。
- `git diff --check` 通过。

### 阻塞项

- 无。

### 下一步建议

- 合并 PRD 后，按 Phase B 顺序实现：共享契约 / sklearn acceptance 与 `18_qa` 迁移 / LightGBM candidate fan-out / 2021/2022/2023 三折 CV ranking / Top 5 完整回测 / `19` QA。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #78 / OQ-010 / Cloud Run Python baseline search PRD review follow-up

### 已完成工作

- 复核 PR #78 comment，认可验收状态机不完备、accepted/rejected 门槛不一致、阈值与 sklearn native PRD 漂移、2026 final_holdout 过短、单一年份 valid 选高容量候选方差过高、binary objective 与排序评估不完全一致、缺少共享验收契约等问题。
- 修订 `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`：候选排序改为 2021/2022/2023 三折 purged walk-forward CV + 2024 valid confirmation；后续 follow-up 已将 P0 固定为 `candidate_count=40` / `candidate_parallelism=40`，且必须有 CV 证据，否则不得 accepted。
- 重写 §9 接受标准：新增共享验收配置 `configs/strategy1/model_acceptance_contract_v1.yml`，状态机改为互斥完整且机器可校验；补 Sharpe `>=0.70`、max drawdown `>=-25%` 等风险门槛；`RankIC == 0`、`top_minus_bottom == 0`、`test_year_excess_return == 0` 等边界显式 rejected。
- 将 2026 final_holdout 定位改为明显坏结果 veto / holdout watch：不再要求 `final_holdout_excess_return_vs_000852 >= 0`，但 `<= -5pct` 或 `final_holdout_total_return <= -8%` 仍 hard reject。
- 补充 objective 路线：P0 保留 LightGBM binary 兼容当前链路，ranking / regression objective 留作后续波次。
- 同步更新 `TODO.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和本交接。

### 重要上下文

- 未采纳“本轮直接扩展到 2026 年 5 月”：owner 已明确本轮先用到 `2026-04-30`，且 5 月尚未进入 Ledger P1/P2 固定验收窗口。
- 未把 P0 直接切为 `lambdarank`：当前 runner、候选池、报告和 QA 仍以正类概率排序分为契约，ranking objective 需要另行定义按日 group、score 可比性和 QA。
- 本次只改 PRD 和记忆/TODO，未实现代码、未部署 Cloud Run Job、未执行 BigQuery。

### 改动文件

- `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check` 通过。

### 阻塞项

- 无。

### 下一步建议

- 合并 PRD 后，先实现 `configs/strategy1/model_acceptance_contract_v1.yml`，再实现 LightGBM wave 2 candidate fan-out / CV ranking / Top 5 完整回测 / `19` QA。

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
Run ID: N/A
相关 issue/PR: OQ-010 / Cloud Run Python baseline search PRD

### 已完成工作

- 在独立工作树 `/Users/luna/Desktop/git/quant-ashare-cloudrun-python-baseline-search`、分支 `codex/prd-cloudrun-python-baseline-search` 新增 `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`。
- PRD 固定本轮数据截止 `2026-04-30`，明确不用 2026 年 5 月数据参与本轮模型搜索。
- PRD 固定 train/valid/test/final_holdout 为 `2019-04-03..2023-12-31` / 2024 / 2025 / `2026-01-05..2026-04-30`。
- PRD 固定交易参数、股票池、成本和 Ledger v1，只比较 Cloud Run Python 模型 backend / 模型族 / 参数。
- PRD 将 P0 模型族定为 LightGBM wave 2；PR #78 review follow-up 后已改为 2021/2022/2023 三折 purged walk-forward CV + 2024 valid confirmation 选 Top 5，2025 test 做硬接受门，2026 final_holdout 只做明显坏结果 veto / holdout watch。
- 同步更新 `TODO.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和本交接。

### 重要上下文

- 本次只写 PRD 和记忆/TODO，未实现代码、未部署 Cloud Run Job、未执行 BigQuery。
- 历史 BQML / SQL runner 仍仅作 reference / audit，不得作为后续新增模型搜索路径。
- accepted baseline 建立前，不建议实现月度滚动重训正文改造之外的生产重训逻辑。

### 改动文件

- `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check` 通过。
- 未执行 SQL / Python / Cloud Run。

### 阻塞项

- 无。

### 下一步建议

- 合并 PRD 后，实现 LightGBM wave 2 Cloud Run Python baseline search。
- 若 Wave 2 rejected，再进入 XGBoost / HistGradientBoosting 或补 `dws_market_state_daily` 后重搜。
- accepted baseline 建立后，再改造月度滚动重训 PRD 正文。

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

---

日期: 2026-06-05
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: manual_oq005_alert_checker_heartbeat_global_20260605_01
相关 issue/PR: PR #77 / OQ-005 alert checker liveness deployment follow-up

### 已完成工作

- 在 PR #75 合并后完成 OQ-005 alert checker liveness 生产部署验收，并把仓库脚本与生产状态对齐。
- 修复 `check_alerts.py`，让业务告警与 heartbeat 显式写入 Cloud Logging global resource。
- 修复 `setup_alerts.py`：正确导入 Logging Metrics client / LogMetric，设置 alert policy combiner，threshold / absence filter 统一加 `resource.type="global"`。
- 按 PR #77 review comment 修复告警策略幂等：使用稳定 `user_labels.oq005_policy` 做幂等键，并兼容旧 display name 迁移，避免旧名环境重复创建新旧两份策略。
- 更新 alerting README、TODO 和 OQ-005 记忆状态。

### 重要上下文

- 生产 smoke `manual_oq005_alert_checker_heartbeat_global_20260605_01` 成功；随后 scheduled run 也成功。
- Cloud Logging 中 heartbeat 已确认为 `resource.type=global`、`lookback_minutes=20`、`alerts_count=0`。
- Cloud Monitoring `logging.googleapis.com/user/oq005_alert_checker_heartbeat` 的 global timeSeries 已有点；旧的 `k8s_container` heartbeat 只来自修复前第一次 smoke。
- OQ-005 告警主链路和 checker liveness 均已上线；OQ-005 仍 open，剩余 Dataform 生产链路、补跑与完整 ODS→ADS 运维观测闭环。

### 改动文件

- `scripts/alerting/check_alerts.py`
- `scripts/alerting/setup_alerts.py`
- `scripts/alerting/README.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- Composer manual smoke：`manual_oq005_alert_checker_heartbeat_global_20260605_01` 成功。
- Composer scheduled run 成功。
- Cloud Logging 查询确认 heartbeat 使用 global resource。
- Cloud Monitoring timeSeries 查询确认 `oq005_alert_checker_heartbeat` global metric 有数据点。
- Cloud Monitoring alert policies 查询确认 4 个 OQ-005 policy 均启用并绑定通知渠道。
- 本地 py_compile、`setup_alerts.py --dry-run`、只读 `check_alerts.py --lookback-minutes 20 --json`、观测 SQL dry-run、旧名 policy 匹配断言和 `git diff --check` 均通过。

### 阻塞项

- 无。

### 下一步建议

- 继续 OQ-005 Dataform definitions、补跑自动化、生产 DAG 参数化闭环和 ODS→ADS 运行状态观测。
- 修复 `ashare_daily_pipeline_v0` scheduled run 默认 business_date 口径：每日 20 点定时任务必须跑当天数据，而不是 Airflow `ds` 的上一天。

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
Run ID: N/A
相关 issue/PR: OQ-010 / PRD04 Cloud Run Python baseline search implementation

### 已完成工作

- 在工作树 `/Users/luna/Desktop/git/quant-ashare-prd04-cloudrun-python-baseline`、分支 `codex/implement-prd04-cloudrun-python-baseline` 实现 `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md` 的 P0 代码路径。
- 新增共享验收契约 `configs/strategy1/model_acceptance_contract_v1.yml`，并让 sklearn native `18_qa` 追溯同一契约版本。
- 新增 LightGBM binary wave 2 manifest（40 候选、默认 40 task）和 LightGBM regression wave 3 manifest（12 候选、默认 12 task）。
- 扩展 Cloud Run Python task fan-out：tree 预处理、LightGBM classifier/regressor、raw/oriented score、CV folds、Top5 ranking、final_holdout 指标、shared acceptance、`needs_more_evidence` 自动进入下一波。
- 新增 `scripts/strategy1_cloudrun/orchestrate_cloudrun_python_baseline_search.py` 入口和 `sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql`。
- 同步运行手册、SQL README、TODO、PROJECT_CONTEXT、IMPLEMENTATION_STATUS、OPEN_QUESTIONS 和本交接。

### 重要上下文

- 本次只完成代码实现和本地/dry-run 验证，未构建/部署新 Cloud Run 镜像，未执行真实 40 候选 search，未生成新的 ADS/GCS search 产物。
- 若真实 LightGBM CV smoke 证明单 task `1 vCPU / 4Gi` 不够，应提高 candidate task 内存并降低并发；运行手册已给出 `8Gi / parallelism=20` 示例。
- 若 wave 2 Top5 无 accepted 且存在 `needs_more_evidence`，orchestrator 会按 manifest 进入 `lightgbm_regression` wave 3。

### 改动文件

- `configs/strategy1/model_acceptance_contract_v1.yml`
- `configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml`
- `configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml`
- `scripts/strategy1_cloudrun/*.py`
- `sql/ml/strategy1/01_build_training_panel.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`
- `sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql`
- `scripts/strategy1/requirements.txt`
- `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python -m py_compile scripts/strategy1_cloudrun/*.py`
- `python -m scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search --config configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml --manifest configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml --build-training-panel --dry-run`
- `python -m scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search --config configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml --manifest configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml --build-training-panel --dry-run`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/01_build_training_panel.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql`
- `git diff --check`

### 阻塞项

- 无代码阻塞；真实 search 需合并后构建/部署新镜像再执行。

### 下一步建议

- 合并 PR 后构建并部署 `strategy1-cloudrun-runner` 镜像到 prepare / candidate / select / backtest jobs。
- 执行 PRD04 wave 2 真实 search；若 candidate task 内存不足，按运行手册升内存并降低并发。
- 根据 Top5 acceptance 结论决定是否建立 `cloud_run_python_baseline_v1` 或进入 `lightgbm_regression` wave 3。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: OQ-005 / scheduled non-trading day skip gate

### 已完成工作

- 在新工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-nontrading-skip`、分支 `codex/oq005-nontrading-skip` 实现 `ashare_daily_pipeline_v0` 非交易日 skip gate。
- DAG 在 `pipeline_start_status` 后新增 `non_trading_day_gate`，仅对 scheduled `daily_current` 生效。
- gate 查询 `ashare_dim.dim_trade_calendar` 的 SSE 当日开市状态；非开市日进入 `skip_non_trading_day`，跳过 ingestion、ODS readiness 和 transform，并写 `pipeline_task_status.status='skipped'`。
- 手工触发、`backfill`、`qa_only`、`full_rebuild` 和 legacy full refresh 继续走原链路；上一交易日修复仍必须显式 `backfill`。
- 同步更新 Composer README、OQ-005 runbook、TODO、IMPLEMENTATION_STATUS、ARCHITECTURE_MEMORY、KNOWN_CONSTRAINTS、OPEN_QUESTIONS 和本交接。

### 重要上下文

- 本次只改代码和文档，未部署到 Composer，未触发生产 DAG，未执行 BigQuery。
- 非交易日 gate 依赖 `ashare_dim.dim_trade_calendar` 已有 SSE 当日行；若日历缺行会 fail-closed，不会静默跳过。
- 合并部署后需要用周末/节假日 scheduled 口径 smoke，确认 `skip_non_trading_day` 状态写入且 Cloud Run ingestion 没有触发。

### 改动文件

- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `orchestration/composer/README.md`
- `docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date::2026-06-06 ...`
- `git diff --check`

### 阻塞项

- 无代码阻塞；生产生效需要合并后部署 Composer。

### 下一步建议

- 合并后同步 DAG 到 Composer bucket。
- 触发周末/节假日 scheduled 口径 smoke，验收 `skip_non_trading_day` 状态行、pipeline terminal success 和 Cloud Run ingestion 未触发。
- 继续 OQ-005 Dataform 生产链路和补跑/resume 自动化。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: manual_smoke_skip_non_trading_day_pr83_20260606_02
相关 issue/PR: PR #83 / issuecomment-4637354942 / OQ-005 memory consistency follow-up

### 已完成工作

- 复核 PR #83 review comment `4637354942`，采纳 low finding。
- 修正 `.agent/memory/IMPLEMENTATION_STATUS.md` 已完成区残留的部署等待状态。
- 将几条 OQ-005 历史补充改为明确的部署前记录，并指向后续 PR #70 / PR #80 / PR #83 部署和 smoke 状态，避免和顶部当前状态冲突。

### 重要上下文

- 本次只修项目记忆一致性，不改 DAG / SQL / Python 代码，不重新部署 Composer，不重跑 BigQuery。
- PR #83 DAG 实现和 `manual_smoke_skip_non_trading_day_pr83_20260606_02` 验收结论不变。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `rg` 检查当前 OQ-005 记忆中不再有部署等待语义的自相矛盾状态。
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 继续 OQ-005 Dataform definitions、补跑/resume 自动化和完整 ODS→ADS 运维观测闭环。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: N/A
相关 issue/PR: PR #83 / OQ-005 non-trading day skip gate review follow-up

### 已完成工作

- 复核 PR #83 comment `4637223843`，认可全部 4 条问题。
- 补 `force_non_trading_day_gate=true` smoke-only 显式钩子：普通手工 `daily_current` 仍不自动走 gate，部署验收必须是真正 scheduled run 或显式 smoke hook，普通 `dags trigger` 不算 skip gate smoke。
- 将 `skip_non_trading_day` 从 `EmptyOperator` callback 状态写入改为实体 `PythonOperator`，在 task body 写 `pipeline_task_status.status='skipped'`，并保留 skipped callback 作为最终状态覆盖。
- 日历 gate 查询增加 `COUNTIF(is_open IS NULL)` 与 `COALESCE(LOGICAL_OR(...), FALSE)`；日历缺行或 `is_open` 为空均 fail-closed。
- Runbook 补充 `dim_trade_calendar` 覆盖边界：若未来日历未延展或 `is_open` 为空，需要先采集/刷新 `trade_cal` 与 `dim_trade_calendar`。
- 同步更新 Composer README、OQ-005 runbook、TODO、IMPLEMENTATION_STATUS、ARCHITECTURE_MEMORY、KNOWN_CONSTRAINTS、OPEN_QUESTIONS 和本交接。

### 重要上下文

- 本次只改 PR #83 分支代码和文档，未部署到 Composer，未触发生产 DAG。
- `force_non_trading_day_gate=true` 仅为 smoke-only 测试钩子；上一交易日修复仍必须显式 `backfill`。

### 改动文件

- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `orchestration/composer/README.md`
- `docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 --parameter=business_date::2026-06-06 ...`
- `git diff --check`

### 阻塞项

- 无代码阻塞；生产生效需要合并后部署 Composer。

### 下一步建议

- 合并后同步 DAG 到 Composer bucket。
- 用真正 scheduled run 或 `force_non_trading_day_gate=true` smoke-only 手工 run 验证 `skip_non_trading_day` 状态行、pipeline terminal success 和 Cloud Run ingestion 未触发。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: manual_smoke_skip_non_trading_day_pr83_20260606_02
相关 issue/PR: PR #83 / OQ-005 scheduled non-trading day skip gate deployment

### 已完成工作

- 将 `main` 快进到 PR #83 merge commit `3723f52`。
- 将 `orchestration/composer/dags/ashare_daily_pipeline_v0.py` 同步到 Composer DAG bucket：`gs://asia-east2-ashare-composer-b2629133-bucket/dags/ashare_daily_pipeline_v0.py`。
- 复核本地与 bucket DAG SHA256 一致：`e4b07ba402716b914bfbd6fe27fa38f97fab8e1c12f6a0bcce9e5fd8c58696af`。
- 用 `business_date=2026-06-06`、`warehouse_mode=daily_current`、`force_non_trading_day_gate=true`、`pipeline_dry_run=true` 触发 smoke `manual_smoke_skip_non_trading_day_pr83_20260606_02`。
- 验证 smoke 成功：`non_trading_day_gate=success`、`skip_non_trading_day=success`、`pipeline_finalize_status=success`、`finish=success`。
- 验证 `pipeline_task_status` 已写入 `skip_non_trading_day status='skipped'`，`pipeline_run.status='success'`。
- 验证 ingestion/readiness/window/full/qa 分支均 skipped，Cloud Run `ashare-ingest-current-scope` 没有新 execution。
- 验证 DAG 当前 active/unpaused、无 import errors；`v_alert_summary` 对本次 smoke 为空。

### 重要上下文

- 首次 smoke `manual_smoke_skip_non_trading_day_pr83_20260606_01` 在 Composer 新旧 serialized DAG 切换窗口内被创建，`non_trading_day_gate` / `skip_non_trading_day` 一度显示 `removed` 且旧 `branch_ingestion` 进入 scheduled。
- 已立即暂停 DAG、确认 Cloud Run 未触发、通过 Airflow API 将该 DagRun 标为 failed，并将 `ashare_meta.pipeline_run` 对应行修正为 `partial`，error_summary 写明被第二次成功 smoke supersede，避免假告警。
- 生产 20:00 scheduled run 当前保持启用；下一次真实周末 scheduled run 仍可作为自然验收补充，但本次 force hook smoke 已验证 skip 分支落库与 Cloud Run 未触发。

### 改动文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `gcloud storage cp` 部署 DAG，并下载回 `/tmp/ashare_daily_pipeline_v0.py.bucket` 做 SHA256 对比。
- Airflow REST API 验证 DAG `is_active=true`、`is_paused=false`、`has_import_errors=false`。
- Airflow task 状态验证 `manual_smoke_skip_non_trading_day_pr83_20260606_02` 成功走 skip 分支。
- BigQuery 查询验证 `pipeline_run` / `pipeline_task_status` 状态。
- Cloud Run execution list 验证最近 execution 仍为 PR #80 的 `manual_pr80_daily_current_20260605_20260606_01_current_scope_write`，本次 smoke 未触发 Cloud Run。
- BigQuery `v_alert_summary` 查询返回空。

### 阻塞项

- 无部署阻塞。

### 下一步建议

- 继续 OQ-005 Dataform definitions。
- 继续补跑/resume 自动化。
- 继续完整 ODS→ADS 运维观测闭环收尾。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: s1_cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01__lgbm_r03_l63_lr002_n600_leaf300_ff09_bf09_l1_01_l2_1
相关 issue/PR: PR #87 / OQ-010 / PRD_20260606_01 / Tail-risk diagnostics P0

### 已完成工作

- 通过 GitHub API squash merge PR #84，合并 `docs/prd/PRD_20260606_01_策略1尾部风险控制.md`，并删除远端 / 本地 `codex/prd-strategy1-tail-risk-diagnostics` 与对应工作树。
- 新建工作树 `/Users/luna/Desktop/git/quant-ashare-tail-risk-impl`，分支 `codex/implement-tail-risk-diagnostics-p0`。
- 新增 `scripts/strategy1/analyze_tail_risk.py`：只读 ADS/DWD/DIM，输出 `tail_risk/` 最大回撤事件、持仓贡献、行业 / 板块贡献、跌停 / 不可卖暴露、选股画像、风险股票名单、search summary、ADS read-only guard 和中文 `tail_risk.md`。
- 修改 `scripts/strategy1_cloudrun/backtest_report.py`：默认在报告、模型诊断和 `12` QA 后执行尾部风险诊断；新增 `--skip-tail-risk` 和 `--search-id`；诊断后自动执行 `20_qa_tail_risk_outputs.sql`，并注入脚本产出的 summary/NAV expected hash。
- 修改 `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`：TopK 回测传递 `search_id`，comparison report 增加最大回撤窗口和跌停仓位峰值，并输出 `tail_risk/search_tail_risk_summary.csv`。
- 新增 `sql/ml/strategy1/20_qa_tail_risk_outputs.sql`：复算最大回撤、持仓覆盖、跌停 / 不可卖权重和 summary/NAV hash，作为 P0 诊断 QA。
- 更新 `sql/ml/strategy1/README.md`、`docs/策略1CloudRun训练回测运行手册.md`、`TODO.md` 和相关记忆。

### 重要上下文

- P0 尾部风险诊断不写 ADS 核心表，不改变任何策略交易结果；artifact 文件存在性由 Python 脚本和 `artifact_manifest.json` 强制，`20` QA 只校验 BigQuery 派生不变量和只读 hash。
- 本地 smoke 使用 Wave 3 regression Top1：最大回撤区间 `2024-01-05` 至 `2024-02-07`，策略回撤 `-34.80%`，同期 benchmark return `-15.47%`，跌停仓位峰值约 `86.46%`（2024-02-05）。
- `candidate_overlap_by_signal_date.csv` / `common_crash_names.csv` 在单候选脚本中保留为空表头；TopK 横向诊断由 orchestrator comparison 生成，包含两两选股重叠、共同选中股票和回撤窗口近似贡献。
- P1/P2 尚未开始：P1 是个股硬风险过滤 profile A/B，P2 依赖 `dws_market_state_daily` 或等价 market state artifact 做 risk-off。

### 改动文件

- `scripts/strategy1/analyze_tail_risk.py`
- `scripts/strategy1_cloudrun/backtest_report.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `sql/ml/strategy1/20_qa_tail_risk_outputs.sql`
- `sql/ml/strategy1/README.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python -m py_compile scripts/strategy1/analyze_tail_risk.py scripts/strategy1_cloudrun/backtest_report.py scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `python scripts/strategy1/analyze_tail_risk.py --help`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/20_qa_tail_risk_outputs.sql`
- `python -m scripts.strategy1_cloudrun.backtest_report ... --dry-run`
- `python -m scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search ... --dry-run`
- Wave 3 regression Top1 `analyze_tail_risk.py --skip-gcs-upload` 本地 artifact smoke 成功。
- 使用脚本 post-guard hash 执行真实 `sql/ml/strategy1/20_qa_tail_risk_outputs.sql`，全部 ASSERT 通过。

### 阻塞项

- 无代码阻塞；生产生效需要合并本实现 PR 并部署 Cloud Run runner 镜像。

### 下一步建议

- 合并本实现 PR 后构建 / 部署新的 `strategy1-cloudrun-runner` 镜像。
- 对 Wave 3 Top5 统一生成 uploaded `tail_risk/` artifact 和 comparison summary。
- 基于尾部风险证据实现 P1 `individual_risk_guard_v0` profile A/B。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
