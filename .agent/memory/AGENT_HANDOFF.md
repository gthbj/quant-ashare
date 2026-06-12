> 当前交接摘要（2026-06-13，GPT-5.5，dividend daily scope）
> - `codex/dividend-daily-scope` 已实现 PRD_20260613_03：`dividend` 进入 current_scope 的 `corporate_actions` 组，并按 `lookback_open_days=5` 从 `dim_trade_calendar` 展开最近 5 个 SSE 开市日逐日 `ex_date` 请求。
> - `qa/09` 已把 dividend 注册为 weak endpoint，`empty_return` 不写 warning；`ashare_warehouse_window_refresh` 的 `daily_current` 链尾已接入 dwd/12 + qa/14，局部 try/except 保证事件链失败只写 task failed、不 rethrow。
> - 本轮未改 ledger / 默认 profile / Cloud Run job spec / IAM / full_rebuild opt-in；未写 BigQuery/GCS 生产数据。
> - 合并后必须重建 ingestion 镜像并记录 digest，用 `dividend_backfill` 最近开市日 smoke，部署 Workflows；2026-06-15 scheduled run 后核验新 digest、dividend meta、事件 task 与可见上界，连续两交易日全绿后收口。
>
> Model: GPT-5.5

## 2026-06-13 GPT-5.5 - dividend daily scope and event workflow

日期: 2026-06-13
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-div-daily`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/dividend-daily-scope`
Run ID: N/A
相关 issue/PR: PRD `docs/prd/PRD_20260613_03_dividend日常采集与事件链路编排接入.md`；PR #212

### 已完成工作

- 将 `dividend` 加入 `configs/ingestion/ods_current_scope_v0.yml`，归入 `corporate_actions`，并把 `current_scope` alias 显式追加该组；`dividend_backfill` 保持手工历史缺口组。
- `run_ingestion_job.py` 新增 `lookback_open_days` 支持：生产从 `ashare_dim.dim_trade_calendar` 解析最近 5 个 SSE 开市日；`build_plan` 展开为逐日 `partition_date=ex_date` plan；`endpoint_runner` 按 plan item 的 logical date 发请求与产出结果。
- `sql/qa/09_ods_daily_partition_readiness.sql` 将 dividend 注册为 weak endpoint，空返回豁免 warning。
- `orchestration/workflows/ashare_warehouse_window_refresh.yaml` 在 `daily_current` 链尾新增 dwd/12 与 qa/14 两步；局部 try/except 捕获失败后写 task failed 并继续主链 finalize success，`backfill` / `qa_only` 不跑事件链。
- 同步更新 `KNOWN_CONSTRAINTS.md`、`IMPLEMENTATION_STATUS.md`、`TODO.md`、`sql/README.md`、ingestion/workflows README 与 runbook。

### 重要上下文

- 本轮不改 ledger 代码、不改默认 `corporate_actions=none_v1`、不写 ADS/research/promotion，不触碰 Cloud Run job spec/IAM/full_rebuild opt-in。
- PR 合并前只做代码和 dry-run 验证；PRD 要求的 ingestion 镜像重建、digest 记录、`dividend_backfill` smoke 与 2026-06-15 live scheduled run 核验必须在合并后执行。
- 事件链 failure 通过既有 `v_alert_summary.alert_type='task_failure'` 承载；pipeline_run 仍应为 success。消费端 staleness 断言保持不变。

### 改动文件

- `configs/ingestion/ods_current_scope_v0.yml`
- `scripts/ingestion/run_ingestion_job.py`
- `scripts/ingestion/common/endpoint_runner.py`
- `scripts/ingestion/endpoints/corporate_actions.py`
- `sql/qa/09_ods_daily_partition_readiness.sql`
- `orchestration/workflows/ashare_warehouse_window_refresh.yaml`
- `tests/ingestion/test_dividend_backfill_manifest.py`
- `tests/ingestion/test_ods_readiness_dividend.py`
- `tests/workflows/test_dividend_event_chain.py`
- `scripts/ingestion/README.md`
- `orchestration/cloud_run_jobs/README.md`
- `orchestration/workflows/README.md`
- `docs/Pipeline-补跑与故障恢复-Runbook.md`
- `sql/README.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/ingestion/test_dividend_backfill_manifest.py tests/ingestion/test_ods_readiness_dividend.py tests/workflows/test_dividend_event_chain.py`：10 passed。
- `PYTHONPATH=src python3 -m pytest -q tests`：294 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：passed。
- `python3 -m compileall -q scripts tests`：passed。
- `git diff --check`：passed。
- `bq query --project_id=data-aquarium --location=asia-east2 --use_legacy_sql=false --dry_run --parameter=pipeline_run_id:STRING:dry_dividend_readiness --parameter=business_date:STRING:2026-06-16 --parameter=pipeline_dry_run:STRING:true --parameter=require_business_partition:STRING:false < sql/qa/09_ods_daily_partition_readiness.sql`：validated。
- `bq query --project_id=data-aquarium --location=asia-east2 --use_legacy_sql=false --dry_run < sql/dwd/12_dwd_stock_dividend_event.sql`：validated。
- `bq query --project_id=data-aquarium --location=asia-east2 --use_legacy_sql=false --dry_run < sql/qa/14_corporate_action_event_checks.sql`：validated。
- `python3 scripts/ingestion/run_ingestion_job.py --endpoint-group corporate_actions --business-date 2026-06-16 --dry-run --output-json --project data-aquarium --bq-location asia-east2`：plan 展开为 `20260610/11/12/15/16` 五个 dividend 分区。
- `python3 scripts/ingestion/run_ingestion_job.py --endpoint-group current_scope --business-date 2026-06-16 --dry-run --output-json --project data-aquarium --bq-location asia-east2`：current_scope dry-run 含 32 个 plan item，corporate_actions dividend 分区为 `20260610/11/12/15/16`。

### 阻塞项

- 无代码阻塞；生产镜像重建、Workflows 部署和 2026-06-15 live 验证需等 PR 合并后执行。

### 下一步建议

- 合并后立即重建 `ingestion:latest` 并记录 digest，用 `dividend_backfill` 最近开市日 smoke，随后通过 `deploy_workflows.sh` 部署 Workflows。
- 2026-06-15 20:00 CST scheduled run 后核验 execution digest、dividend meta、`v_ingestion_meta_missing`、事件两步 task status 和 `dwd_stock_dividend_event` 可见上界；连续两个交易日全绿后收口本 PRD。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

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
