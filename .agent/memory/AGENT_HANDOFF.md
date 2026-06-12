> 当前交接摘要（2026-06-13，GPT-5.5，PRD_20260613_01 P1 市值规则修复双选项 paper）
> - `codex/p1-rules-paper-batch` 已扩展 `analyze_topdown_lot_phase0.py`：字段级 P1 null reason、T1a/T1b1/T1b2 三新臂、0.60 饱和回退与 0.50/0.70 阈值敏感性附表。
> - BigQuery 只读 + 本地 pandas 实跑完成，resolver 解析到 true5y CA-on：prediction `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01`，official backtest `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01`。
> - matched official cost / `walk_depth=50` 主判读下 T1a/T1b1/T1b2 均未满足预登记四门槛；若继续 Phase 2，建议用 T0 / no P1，PRD_10 的 P1 绑定条款需 owner 决策。
> - PR #210 Claude review low follow-up 已补报告口径说明：Phase 0 effective-window 与本轮 true5y CA-on prediction 流不同，T1-T0 gap `-13.70pp -> -15.95pp` 不可直接横比。
> - 本轮不写 BigQuery 数据集、不改 ledger/runner/catalog/默认 profile、不标 accepted/promotion；大明细 CSV 已上传 GCS，小 metrics CSV 随 PR 入库。
>
> Model: GPT-5.5

## 2026-06-13 GPT-5.5 - PRD_20260613_01 P1 市值规则修复双选项 paper

日期: 2026-06-13
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-p1-paper`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/p1-rules-paper-batch`
Run ID: prediction `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01`；official backtest `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01`
相关 issue/PR: PRD `docs/prd/PRD_20260613_01_策略1P1市值规则修复双选项Paper批量.md`；PR #210

### 已完成工作

- 扩展 `scripts/strategy1/analyze_topdown_lot_phase0.py`：P1 null reason 从统一 `tail_risk:required_field_null` 细化为字段级 reason，市值字段归市值组、形态字段归形态组；T0/T1 原过滤语义保持不变。
- 新增 T1a/T1b1/T1b2 三臂：T1a 仅形态组；T1b1 在当次调仓 walk_depth P1 标记率 `>0.60` 时退到 T1a；T1b2 在同阈值触发时退到 T0。回退只影响当次调仓新买入过滤。
- 增加 0.50 / 0.70 阈值敏感性附表，主判读仍固定 matched official cost + `walk_depth=50` + `p1_marked_rate > 0.60`。
- 生成报告 `docs/分析-策略1P1市值规则修复双选项-20260613.md` 与小 metrics CSV；大 daily / rebalance audit CSV 上传到 `gs://ashare-artifacts/reports/strategy1/p1_market_cap_rules/analysis_date=20260613/`。
- 新增单测覆盖 P1 分组、字段级 NULL 分组、T1a/T1 语义差异、饱和阈值严格边界、回退局部性。
- PR #210 Claude review low follow-up：报告 `方法与边界` 已补 Phase 0 对照说明，明确 Phase 0 用 effective-window prediction 流、本轮用 true5y CA-on resolver，T1-T0 gap 从 `-13.70pp` 到 `-15.95pp` 是 prediction 流切换导致，不是实现差异。

### 重要上下文

- 主结果 matched official cost / `walk_depth=50`：T0 CAGR=`11.81%`、MaxDD=`-58.67%`、Calmar=`0.201`；T1 CAGR=`-4.14%`、MaxDD=`-67.38%`、Calmar=`-0.061`；T1a CAGR=`6.26%`、MaxDD=`-59.80%`、Calmar=`0.105`；T1b1 CAGR=`4.24%`、MaxDD=`-60.11%`、Calmar=`0.070`；T1b2 CAGR=`4.11%`、MaxDD=`-63.99%`、Calmar=`0.064`。
- 预登记判读：T1a/T1b1/T1b2 均未同时满足 CAGR gap、饱和 episode 现金、MaxDD 与 crunch excess 四门槛；结论为 P1 市值规则修复不足，若继续 Phase 2 建议以 T0 / no P1 口径进入，PRD_10 的 P1 profile 绑定条款需 owner 决策。
- paper 为 raw 价格口径，不模拟 CA-on ledger 的分红送转与卖出失败降级；五臂内部对比可用，绝对值不与 CA-on official ledger 直接互比。
- 本轮未写任何 BigQuery 数据集，未启动 Cloud Run，未改 ledger / runner / catalog / 默认 profile，未做 accepted / promotion / 默认 profile 变更。

### 改动文件

- `scripts/strategy1/analyze_topdown_lot_phase0.py`
- `tests/strategy1/test_topdown_lot_phase0.py`
- `docs/分析-策略1P1市值规则修复双选项-20260613.md`
- `docs/analysis_strategy1_p1_market_cap_rules_20260613_metrics.csv`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_topdown_lot_phase0.py tests/strategy1/test_metric_definition_freeze.py`：14 passed。
- `python3 -m py_compile scripts/strategy1/analyze_topdown_lot_phase0.py tests/strategy1/test_topdown_lot_phase0.py`：passed。
- `PYTHONPATH=src python3 scripts/strategy1/analyze_topdown_lot_phase0.py`：completed，报告与 CSV 已生成。
- `gcloud storage cp ... gs://ashare-artifacts/reports/strategy1/p1_market_cap_rules/analysis_date=20260613/`：daily / rebalance audit 上传成功。
- 全量 pytest 与 `git diff --check`：提交前执行。

### 阻塞项

- 无。

### 下一步建议

- owner 决定 PRD_10 Phase 2 是否改为 T0 / no P1 口径，或是否先做 CA 调整后的 paper/真实 ledger 证据。
- 合并前如 `origin/main` 再变化，rebase 后重跑全量 pytest 与 `git diff --check`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

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
