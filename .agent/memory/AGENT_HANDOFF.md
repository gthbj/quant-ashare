> 当前交接摘要（2026-06-13，GPT-5.5，topdown Phase 2 T0 code PR）
> - 分支 `codex/topdown-phase2-t0` 已按 `PRD_20260613_04` 完成代码层修订：topdown ledger v2 允许 `diagnostic_only`，仍只允许 individual guard profiles 执行 P1 专属行为。
> - `qa_topdown_construction_outputs.sql` 已将 QA-TOPDOWN-6/7/8 按 profile 条件化，catalog 登记内部派生参数，PRD_10 文首已加 supersede 指针。
> - 本轮只交付代码 PR；未构建 Strategy1 runner 新镜像、未执行 Phase 2 live、未跑外接 QA 四件套、未写 BigQuery/GCS，不 promotion、不 accepted。
> - 下一步：owner review 通过并合并后，resume 本会话执行新镜像 boot smoke、Phase 2 research-only 重跑、外接 QA 四件套、三方对比报告和预登记判读。
>
> Model: GPT-5.5

## 2026-06-13 GPT-5.5 - topdown Phase 2 T0 code PR

日期: 2026-06-13
Agent ID: Codex
Agent 实例 ID: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-topdown-p2`
模型: GPT-5.5
运行环境: macOS / zsh / branch `codex/topdown-phase2-t0`
Run ID: N/A
相关 issue/PR: PRD `docs/prd/PRD_20260613_04_topdownPhase2T0口径修订与重跑.md`

### 已完成工作

- `src/quant_ashare/strategy1/ledger.py` 放宽 topdown v2 profile 校验：允许 `diagnostic_only` 或显式 individual guard profile，仍拒绝 `market_risk_off_v0` 这类非 topdown 构造 profile；v1 默认行为与黄金 hash 不变。
- `sql/strategy1/qa/qa_topdown_construction_outputs.sql` 将 QA-TOPDOWN-6/7/8 改为 profile 条件化，并在 QA-TOPDOWN-1 对齐 summary 实际 `tail_risk_profile_id`：`diagnostic_only` 跳过 P1 专属断言，individual guard profile 仍要求 tail-risk marker 与零 filled BUY。
- `configs/strategy1/active_step_catalog.yml` 将 `p_has_individual_risk_guard` 登记为 `qa_topdown_construction_outputs` 的 internal param，保持 SQL render 不留 unmanaged default。
- 单测补齐 topdown + `diagnostic_only`：不再 raise、tail-risk 标记自然放行买入、`cash_redistribution` 仍为 `topdown_whole_order_skip_v2`；market-only profile 仍 fail-fast。
- `docs/prd/PRD_20260611_10_策略1自上而下整手组合构造.md` 文首加入 `PRD_20260613_04` supersede 指针。

### 重要上下文

- 本轮只做代码 PR；按 owner 指令，live 重跑需等代码 PR review 通过并合并后再执行。
- 未构建 Strategy1 runner 新镜像、未执行 Cloud Run、未写 BigQuery/GCS、未跑外接 QA 四件套、未产出三方对比报告；不 promotion、不 accepted。
- Phase 2 live 执行时仍必须显式 CA-on 参数、`tail_risk_profile_id=diagnostic_only`、`--use-topdown-ledger`、`--skip-diagnosis --skip-tail-risk --skip-qa`，并用外接 QA 参数表显式覆盖 topdown ledger / resume policy。

### 改动文件

- `src/quant_ashare/strategy1/ledger.py`
- `sql/strategy1/qa/qa_topdown_construction_outputs.sql`
- `configs/strategy1/active_step_catalog.yml`
- `tests/strategy1_cloudrun/test_lot_aware_ledger.py`
- `tests/strategy1/test_sql_render.py`
- `docs/prd/PRD_20260611_10_策略1自上而下整手组合构造.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1_cloudrun/test_lot_aware_ledger.py tests/strategy1/test_sql_render.py`：40 passed。
- `PYTHONPATH=src python3 -m pytest -q tests`：295 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：passed。
- `git diff --check`：passed。
- `bq query --project_id=data-aquarium --location=asia-east2 --use_legacy_sql=false --dry_run < sql/strategy1/qa/qa_topdown_construction_outputs.sql`：validated。

### 阻塞项

- 无代码阻塞；Phase 2 live 重跑等待 owner review 通过并合并代码 PR。

### 下一步建议

- PR 合并后构建包含本修订的 immutable Strategy1 runner 镜像，完成 backtest_report boot smoke。
- 按 `PRD_20260613_04` §2 执行 research-only topdown Phase 2 fresh continuous、外接 QA 四件套、ADS/promotion 反查、三方对比报告与预登记判读。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/archive/IMPLEMENTATION_STATUS_2026-06.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

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
