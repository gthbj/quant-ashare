> 当前交接摘要（2026-06-13，GPT-5.5，PRD_20260613_02）
> - `codex/calmar-gate-analysis` 已完成 v3 Calmar 门合理性只读分析：新增 `scripts/strategy1/analyze_calmar_gate_feasibility.py`、报告 `docs/分析-策略1v3Calmar门合理性-20260613.md` 与 6 份小 CSV。
> - 分析覆盖契约语义、八指数双窗口、3 年滚动 Calmar、true5y CA-on baseline NAV exposure overlay 上界、A/B/C/D 反事实矩阵、portfolio 变体附表和全 gate 失败原因矩阵。
> - 主要结论：长窗口八指数 Calmar 上限仅 `0.1089`，当前 CA-on baseline 长窗口 Calmar `0.4103`；无摩擦 exposure 上界可到 `0.6455`，因此不能宣称绝对物理不可达，但 v3 Calmar `>1.0` 对当前路线仍显著偏高且窗口敏感。
> - 本轮只读，未改 contract / acceptance / registry，未写 BigQuery/GCS；全量 `pytest tests` 与 `git diff --check` 已通过，PR #211 已创建。
>
> Model: GPT-5.5

## 2026-06-13 GPT-5.5 - PRD_20260613_02 v3 Calmar gate feasibility analysis

日期: 2026-06-13
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-calmar-gate`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/calmar-gate-analysis`
Run ID: N/A
相关 issue/PR: PRD `docs/prd/PRD_20260613_02_策略1v3Calmar门合理性分析.md`；PR #211

### 已完成工作

- 新增只读分析脚本 `scripts/strategy1/analyze_calmar_gate_feasibility.py`，复用 v3 replay metric helper 与 `simulate_exposure_overlay_upper_bound.py` 路径，不新增 metric freeze 清单内本地定义。
- 梳理 v3 gate 契约组合语义，引用 `acceptance.py`、`model_acceptance_contract_v3.yml`、`PRD_20260608_02` 与 `DECISION-20260608-11/-12` 的设计意图。
- 对八个 benchmark candidate 指数计算 `2021-01-04..2026-06-09` 与 `2024-01-02..2026-04-30` 双窗口 CAGR / Sharpe / MaxDD / Calmar，并生成 3 年滚动 Calmar。
- 拼接当前 true5y CA-on parent/child NAV，复算 baseline 指标，并在该 NAV 上跑 48 个零摩擦 exposure overlay 上界变体。
- 按 PRD 数据契约读取 ADS 三表、从 NAV 复算指标、只把 canonical `bt_s1_<search_id>__<candidate_id>` 纳入候选，portfolio 变体单独附表；产出 A/B/C/D 反事实回放、全 gate 失败原因矩阵和满仓持指数误放行底线检查。
- 生成报告 `docs/分析-策略1v3Calmar门合理性-20260613.md` 与 6 份小 CSV 入库产物。

### 重要上下文

- 本轮严格只读：未改 contract / acceptance / registry，未写 BigQuery/GCS，反事实结果只落报告和 CSV。
- 当前 true5y CA-on stitched baseline 长窗口 CAGR=`15.36%`、Sharpe=`0.6685`、MaxDD=`-37.43%`、Calmar=`0.4103`；短窗口 Calmar=`1.1041`。
- 八指数长窗口 Calmar 区间为 `-0.1024..0.1089`，短窗口为 `0.6557..1.3868`；3 年滚动最高 Calmar=`0.5535`。
- exposure overlay 零摩擦最优变体 `two_state_biweekly_elow0_cost0bps` Calmar=`0.6455`、Sharpe=`0.7478`，说明 `Calmar > 1.0` 仍远，但“不存在任何择时上界可达 0.5”的强物理不可达结论不成立。
- 历史短窗口 canonical 回放中现行 v3 有 `1 accepted / 24 rejected`；该 accepted 是历史短窗口候选，不改变当前 true5y CA-on baseline 未 accepted / 不 promotion 的事实。
- 四选项都存在短窗口纯指数误放行风险，必须保留 pure-index guard / alpha evidence guard；owner 需要先裁决 acceptance 窗口口径，再决定 A/B/C/D 或分级展示。

### 改动文件

- `scripts/strategy1/analyze_calmar_gate_feasibility.py`
- `tests/strategy1/test_calmar_gate_feasibility.py`
- `docs/分析-策略1v3Calmar门合理性-20260613.md`
- `docs/analysis_strategy1_v3_calmar_gate_20260613_index_metrics.csv`
- `docs/analysis_strategy1_v3_calmar_gate_20260613_rolling_3y.csv`
- `docs/analysis_strategy1_v3_calmar_gate_20260613_exposure_overlay.csv`
- `docs/analysis_strategy1_v3_calmar_gate_20260613_reachability_ladder.csv`
- `docs/analysis_strategy1_v3_calmar_gate_20260613_counterfactual_matrix.csv`
- `docs/analysis_strategy1_v3_calmar_gate_20260613_portfolio_variants.csv`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 scripts/strategy1/analyze_calmar_gate_feasibility.py`：成功生成报告与 CSV。
- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_calmar_gate_feasibility.py`：3 passed。
- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_metric_definition_freeze.py`：1 passed。
- `PYTHONPATH=src python3 -m pytest -q tests`：281 passed。
- `git diff --check`：passed。

### 阻塞项

- 无。

### 下一步建议

- owner 先决定 v3 acceptance 采用长 continuous 窗口、短 replay 窗口还是分层判读，再裁决 A/B/C/D 或改为正式/研究分级展示。
- 合并前 rebase 到最新 `origin/main`；若上游改动影响 Strategy1 metric/replay/acceptance 相关文件，需要重跑全量验证。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

## 2026-06-13 GPT-5.5 - ingestion meta incident follow-up

日期: 2026-06-13
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-meta-incident`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/ingestion-meta-incident`
Run ID: N/A
相关 issue/PR: PR #196 事故修复复核；本分支待创建 PR

### 已完成工作

- 只读复核 `ashare-ingest-current-scope` job spec、execution image digest 历史、Cloud Build / Artifact Registry、git ingestion 代码演进、BigQuery `ingestion_run` / `ingestion_partition_status` 行分布和 alert checker 覆盖面。
- 新增事故报告 `docs/分析-ingestion-meta-0行事故排查-20260613.md`，记录根因链、时间线、当前镜像状态、历史缺口处置建议和 2026-06-13 / 2026-06-15 验证计划。
- 在 `sql/observability/01_pipeline_status_views.sql` 新增 `v_ingestion_meta_missing`，并把 `alert_type='ingestion_meta_missing'` 接入 `v_alert_summary`。
- 在 `scripts/alerting/setup_alerts.py` 新增 `ashare_pipeline_ingestion_meta_missing` log metric 和 `Ashare Pipeline: Ingestion Meta Missing` policy；同步更新 alert README 与 active runbook。
- 新增 `tests/alerting/test_ingestion_meta_missing_alert.py`，固定 SQL、setup 和 README 的告警接线。

### 重要上下文

- 当前 job spec image 仍是 `ingestion:latest`，不是 digest pin；execution 创建时解析 tag。本轮确认 2026-06-12 scheduled current_scope execution `ashare-ingest-current-scope-9wnh8` 使用修复镜像 `sha256:5c78e8624584e9ee47471be087ba7e4090d00477a37ec276920f8696810c3f3b` 并落 27 条 meta。
- Artifact Registry 当前 `latest` 指向 dividend 补采镜像 `sha256:35acbc363408d05dd758d70ba5f293e8b0d333a000c6dfe8e8143ddadd0b8bba`；该镜像后续 dividend executions 已实证写 meta。本轮无需、也未执行生产 job 更新。
- 2026-06-13 是周六，SSE `is_open=0`；20:00 CST scheduled workflow 应走非交易日 gate，不会触发 live ingestion，不应期待 20260613 meta 行。下一次 live meta 验证应看 2026-06-15 20:00 CST 后的 current_scope 行。
- 历史 2026-06-09/10/11 meta 缺口建议不回填，保留报告/PR/Cloud Run/pipeline status 作为审计记录，避免混淆真实运行时审计与事后重建记录。

### 改动文件

- `docs/分析-ingestion-meta-0行事故排查-20260613.md`
- `sql/observability/01_pipeline_status_views.sql`
- `scripts/alerting/setup_alerts.py`
- `scripts/alerting/README.md`
- `docs/Pipeline-补跑与故障恢复-Runbook.md`
- `tests/alerting/test_ingestion_meta_missing_alert.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

### 测试 / 验证

- `bq query --project_id=data-aquarium --location=asia-east2 --use_legacy_sql=false --dry_run < sql/observability/01_pipeline_status_views.sql`：validated。
- `python3 -m pytest -q tests/alerting/test_ingestion_meta_missing_alert.py`：1 passed。
- `python3 scripts/alerting/setup_alerts.py --dry-run`：新 metric/policy 可见。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：passed。
- `git diff --check`：passed。

### 阻塞项

- 无。

### 下一步建议

- PR 合并并部署观测 SQL / alert policy 后，2026-06-15 20:00 CST 后复核 `v_ingestion_meta_missing` 为空、`ingestion_run` 有 20260615 current_scope 行。
- 2026-06-13 20:00 CST 只验证非交易日 gate；若触发 live ingestion，反而需要按非交易日 gate 异常处理。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

## 2026-06-12 GPT-5.5 - PRD_20260612_05 Batch 3 package cleanup

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-prd05-b3`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/prd05-batch3`
Run ID: N/A
相关 issue/PR: PRD `docs/prd/PRD_20260612_05_Strategy1包结构PhaseE收尾.md`；PR #206

### 已完成工作

- 将 `scripts/strategy1_cloudrun/feature_sets.py`、`preprocess.py`、`training_panel.py` 迁移到 `src/quant_ashare/strategy1/`，scripts 侧改为 thin re-export shim。
- 将 src 内对 `scripts.strategy1_cloudrun.feature_sets` / `preprocess` 的 import 改为包内直连；Batch 3 后 src→`scripts.strategy1_cloudrun.*` 反向 import 为 0。
- 新增 `src/quant_ashare/strategy1/annual_rolling_plan.py`，承载 annual rolling 计划层常量和 helper；scheduler 与脚本 orchestrator 均改从该模块 import。
- 更新 `tests/strategy1/test_package_boundaries.py` 的 Batch 3 兼容符号快照、硬断言 src 不导入 scripts，并新增非仓库 cwd / `PYTHONPATH=src` 的 package self-contained import 测试。
- 同步 `KNOWN_CONSTRAINTS.md` 兼容层条款、`docs/prd/PRD_20260610_02_项目结构重构方案.md` Phase E 状态注记、`IMPLEMENTATION_STATUS.md` 和 `TODO.md`。

### 重要上下文

- 本轮严格只做 PRD Batch 3；两个脚本 orchestrator 仍保留 CLI 主体和兼容导入面。
- `orchestrate_annual_rolling_selection.py` 的 CLI 参数面、dry-run JSON 输出路径和非 dry-run 拒绝行为保持不变；迁出的计划函数通过脚本顶层 import 继续兼容旧测试/调用方。
- 旧 `scripts.strategy1_cloudrun.feature_sets` / `preprocess` / `training_panel` 路径仍是合法兼容 shim，不应加入 retired-reference ban-list。
- 本轮未改训练、回测、ledger、Cloud Run job spec、args、镜像或 IAM；未写 BigQuery/GCS。

### 改动文件

- `src/quant_ashare/strategy1/feature_sets.py`
- `src/quant_ashare/strategy1/preprocess.py`
- `src/quant_ashare/strategy1/training_panel.py`
- `src/quant_ashare/strategy1/annual_rolling_plan.py`
- `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`
- `scripts/strategy1_cloudrun/feature_sets.py`
- `scripts/strategy1_cloudrun/preprocess.py`
- `scripts/strategy1_cloudrun/training_panel.py`
- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`
- 相关 `src/quant_ashare/strategy1/*.py` import
- `tests/strategy1/test_package_boundaries.py`
- `docs/prd/PRD_20260610_02_项目结构重构方案.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests`：276 passed。
- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_package_boundaries.py`：7 passed。
- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_cloudrun_package_entrypoints.py`：16 passed。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：passed。
- `python3 -m compileall -q src scripts tests`：passed。
- `git diff --check`：passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：passed。

### 阻塞项

- 无。

### 下一步建议

- 等待 Claude review；认可的 comment 在本分支修复，不认可的在 PR comment 说明理由。
- 若合并前 `origin/main` 有新提交，rebase 后重跑关键验证。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`
