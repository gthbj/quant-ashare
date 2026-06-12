> 当前交接摘要（2026-06-13，GPT-5.5，dividend post-merge live deploy）
> - PR #212 已合并；已从 `main@3f017d5` 用 `cloudbuild.ingestion.yaml` 重建 `ingestion:latest`，Cloud Build `9a6a778f-8942-49ac-93ec-9cb15b6596af`，新 digest `sha256:49bc7e1b59c88a78869238d3d3a8433b99fafb82a577f750eabcb797809ae493`。
> - 手工 smoke `ashare-ingest-current-scope-zzbfj` 已用该 digest 对 `dividend_backfill` / `2026-06-12` 写入 dividend meta run `ing_dividend_backfill_20260612_20260612T173304Z`，`row_count=94`。
> - 只部署 `ashare_warehouse_window_refresh` 到 revision `000013-140`；`ashare_ods_ingestion_daily` / `ashare_pipeline_alert_checker` revision 未变，full_rebuild opt-in、Cloud Run job spec、IAM、scheduler 未动。
> - TODO 已记录 2026-06-15 scheduled run 核验清单与连续两个交易日全绿收口项；这两项仍待后续真实 scheduled run。
>
> Model: GPT-5.5

## 2026-06-13 GPT-5.5 - dividend post-merge live deployment

日期: 2026-06-13
Agent ID: Codex
Agent 实例 ID: local checkout `/Users/fisher/Desktop/git/quant-ashare`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/dividend-live-deploy-note`
Run ID: Cloud Build `9a6a778f-8942-49ac-93ec-9cb15b6596af`；Cloud Run execution `ashare-ingest-current-scope-zzbfj`；Workflow revision `ashare_warehouse_window_refresh@000013-140`
相关 issue/PR: PRD `docs/prd/PRD_20260613_03_dividend日常采集与事件链路编排接入.md`；PR #212

### 已完成工作

- PR #212 合并后，从最新 `main@3f017d5` 按 `orchestration/cloud_run_jobs/cloudbuild.ingestion.yaml` 重建并推送 `asia-east2-docker.pkg.dev/data-aquarium/ashare/ingestion:latest`；Artifact Registry digest 为 `sha256:49bc7e1b59c88a78869238d3d3a8433b99fafb82a577f750eabcb797809ae493`。
- 执行 `ashare-ingest-current-scope` 手工 smoke，参数限定为 `--manifest configs/ingestion/ods_dividend_backfill_v0.yml --endpoint-group dividend_backfill --business-date 2026-06-12 --allow-gcs-write`；execution `ashare-ingest-current-scope-zzbfj` 成功完成，解析到同一 digest。
- 复核 `ashare_meta.ingestion_run` / `ingestion_partition_status`：dividend `partition_date=20260612`、run `ing_dividend_backfill_20260612_20260612T173304Z`、`status=success`、`row_count=94`；ODS 读取同分区 94 行且 `ex_date` 匹配。
- 按 `deploy_workflows.sh` 的 control URL render 与 deploy 参数，单独部署 `ashare_warehouse_window_refresh` 到 revision `000013-140`。因脚本会同时部署三条 workflow，本轮为遵守红线未部署 `ashare_ods_ingestion_daily` / `ashare_pipeline_alert_checker`，其 revision 保持 `000010-141` / `000004-f7b`。
- 更新 `orchestration/cloud_run_jobs/README.md`、`IMPLEMENTATION_STATUS.md`、`AGENT_HANDOFF.md` 与 `TODO.md`，记录 digest、smoke、workflow revision、06-15 scheduled run 核验清单和连续两个交易日全绿收口项。

### 重要上下文

- 本轮只动 ingestion 镜像与 `ashare_warehouse_window_refresh` workflow 部署；未改 full_rebuild opt-in、Cloud Run job spec、IAM 或 scheduler。
- 2026-06-15 20:00 CST scheduled run 尚未发生，不能标记 live scheduled 验收完成；后续需核验 execution digest、dividend meta、`v_ingestion_meta_missing`、事件两步 task status 和 `dwd_stock_dividend_event` 可见上界。

### 改动文件

- `orchestration/cloud_run_jobs/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

### 测试 / 验证

- `gcloud builds submit . --project=data-aquarium --config=orchestration/cloud_run_jobs/cloudbuild.ingestion.yaml`：Cloud Build `9a6a778f-8942-49ac-93ec-9cb15b6596af` success。
- Artifact Registry describe：`ingestion:latest` digest `sha256:49bc7e1b59c88a78869238d3d3a8433b99fafb82a577f750eabcb797809ae493`。
- Cloud Run smoke execution `ashare-ingest-current-scope-zzbfj`：success，digest 与新镜像一致。
- BigQuery meta / ODS 复核：dividend `20260612` meta `row_count=94`，ODS 同分区 `ex_date` 行数 94。
- Workflows describe：`ashare_warehouse_window_refresh` revision `000013-140`；`ashare_ods_ingestion_daily` / `ashare_pipeline_alert_checker` revision 仍为 `000010-141` / `000004-f7b`。

### 阻塞项

- 无部署阻塞；2026-06-15 scheduled run 和连续两个交易日收口只能在未来交易日后验证。

### 下一步建议

- 2026-06-15 20:00 CST scheduled run 后按 TODO 清单核验新 digest、dividend meta、`v_ingestion_meta_missing`、事件两步 task status 和可见上界。
- 连续两个交易日 scheduled run 全绿后关闭 PRD_20260613_03 后续收口项。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

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
