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
- 2026-06-12 scheduled current_scope 已使用修复后 ingestion 镜像 `sha256:5c78e8624584e9ee47471be087ba7e4090d00477a37ec276920f8696810c3f3b` 写入 `ashare_meta.ingestion_run` / `ingestion_partition_status` 27 行，采集审计链路恢复已验证；本轮新增 `v_ingestion_meta_missing` 与对应 alert policy 防复发。PRD_20260613_03 已合并，`dividend` 纳入日常 current_scope 的 `corporate_actions` 组，按最近 5 个 SSE 开市日逐日重查，并在 `daily_current` 链尾以 non-blocking weak 方式接入 dwd/12 + qa/14；合并后已重建 ingestion 镜像到 `sha256:49bc7e1b59c88a78869238d3d3a8433b99fafb82a577f750eabcb797809ae493`、完成 `dividend_backfill` 2026-06-12 smoke，并把 `ashare_warehouse_window_refresh` 部署到 revision `000013-140`。下一步是 2026-06-15 20:00 CST scheduled run 后核验新 digest、dividend meta、事件 task 和可见上界；OQ-005 仍剩 post-cutover 短观察窗与 2026-06-12 下游 window QA 独立失败跟进。

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
- PRD_20260613_02 v3 Calmar 门合理性分析已产出只读证据；据此形成的契约 v4 提案（PRD_20260613_05，PR #214 定稿）本版已被 owner 否决（DECISION-20260613-01：长窗 MaxDD 必须硬门，不接受 sign-off 软门），v3 仍是唯一有效契约，修订重提由 owner 决定。PRD_20260613_04 已按 owner 裁决把 topdown Phase 2 代码口径修到 T0 / no-P1：`ledger_exec_v2_lot100_topdown` 允许 `diagnostic_only`，QA-TOPDOWN-6/7/8 按 profile 条件化，PRD_10 文首已加 supersede 指针。Phase 2 live 重跑、外接 QA 四件套、三方对比报告和预登记判读需等代码 PR 合并后执行；尾部风险后续路线、R14 长训练窗口覆盖审计和 OQ-005 短观察窗仍是待办方向，具体下一步以 `TODO.md` 为准。

## 最近补充（最近 7 条）

### 最新补充（2026-06-13）：PRD_20260613_04 topdown Phase 2 T0 代码 PR 已实现

- 分支 `codex/topdown-phase2-t0` 已按 PRD §1.3 完成代码层修订：`ledger_exec_v2_lot100_topdown` 的 profile 校验允许 `diagnostic_only` 或显式 individual guard profile，仍拒绝 `market_risk_off_v0` 这类非构造 profile；`ledger_exec_v1_lot100` 默认行为和黄金 hash 不变。
- `qa_topdown_construction_outputs.sql` 的 QA-TOPDOWN-1 会对齐 summary 实际 `tail_risk_profile_id`，QA-TOPDOWN-6 改为允许 `diagnostic_only` / individual profiles，QA-TOPDOWN-7/8 仅在 individual guard profile 下执行；catalog 将派生变量 `p_has_individual_risk_guard` 登记为 internal param，research 渲染仍要求外部显式参数表覆盖 `p_tail_risk_profile_id`。
- 新增/更新单测覆盖 topdown + `diagnostic_only` 不再 raise、tail_risk 标记在 diagnostic-only 下自然放行买入、`cash_redistribution` 仍为 `topdown_whole_order_skip_v2`，以及 market-only profile 仍 fail-fast；`PRD_20260611_10` 文首已加入 `PRD_20260613_04` supersede 指针。
- 本轮只交付代码 PR，未构建 Strategy1 runner 镜像、未执行 Cloud Run live、未写 BigQuery/GCS、未做 Phase 2 QA 四件套 / 三方对比报告，不 promotion、不 accepted。live 重跑需等 owner review 通过并合并后 resume 执行。

### 最新补充（2026-06-13）：PRD_20260613_03 合并后 ingestion 镜像和 window_refresh 已部署

- PR #212 已合并到 `main`（merge commit `3f017d5`）；已从最新 main 按 `orchestration/cloud_run_jobs/cloudbuild.ingestion.yaml` 重建 `ingestion:latest`，Cloud Build `9a6a778f-8942-49ac-93ec-9cb15b6596af` 成功，新 digest `sha256:49bc7e1b59c88a78869238d3d3a8433b99fafb82a577f750eabcb797809ae493`。
- 手工 smoke execution `ashare-ingest-current-scope-zzbfj` 使用该 digest 对 `dividend_backfill` / `2026-06-12` 采集，写入 dividend meta run `ing_dividend_backfill_20260612_20260612T173304Z`；`ingestion_run` / `ingestion_partition_status` 均为 `row_count=94`、`status=success`，ODS 读取 `partition_date=20260612` 与 `ex_date` 匹配 94 行。
- `ashare_warehouse_window_refresh` 已按部署脚本的 render/deploy 参数单独部署到 revision `000013-140`；因 `deploy_workflows.sh` 会同时部署三条 workflow，本轮为遵守红线只部署 window_refresh，`ashare_ods_ingestion_daily` / `ashare_pipeline_alert_checker` revision 仍为 `000010-141` / `000004-f7b`。
- 本轮未改 full_rebuild opt-in、Cloud Run job spec、IAM 或 scheduler；TODO 已保留 2026-06-15 scheduled run 核验清单和连续两个交易日全绿收口项。

### 最新补充（2026-06-13）：PRD_20260613_03 dividend 日常采集与事件链路接入已实现

- 分支 `codex/dividend-daily-scope` 已按 PRD §2 实现 dividend 日常化：`configs/ingestion/ods_current_scope_v0.yml` 新增 `dividend` endpoint，归入 `corporate_actions`，`current_scope` alias 追加该组，`dividend_backfill` 仍保留为历史缺口手工组。
- `run_ingestion_job.py` 新增 `lookback_open_days=5` 的日历解析，生产从 `ashare_dim.dim_trade_calendar` 取最近 5 个 SSE 开市日并展开为逐日 `ex_date` plan；`endpoint_runner` 改为按 plan item 的 `partition_date/logical_date` 发请求，确保每日期独立分区、独立结果/meta 行、幂等覆盖。
- `sql/qa/09_ods_daily_partition_readiness.sql` 将 dividend 注册为 weak endpoint，淡季 `empty_return` 不写 warning、不阻断 strong endpoint readiness。
- `orchestration/workflows/ashare_warehouse_window_refresh.yaml` 在 `daily_current` 主链尾部新增 dwd/12 与 qa/14 两步，并用局部 try/except 捕获事件链失败：失败写对应 task `failed`、不 rethrow、pipeline finalize success；`backfill` / `qa_only` 不跑事件链，告警沿用既有 `task_failure`。
- 文档和约束已同步：`KNOWN_CONSTRAINTS.md`、`sql/README.md`、ingestion/workflows README、runbook 和 TODO。代码合并后后续动作是重建 ingestion 镜像、记录 digest、用 `dividend_backfill` 最近开市日 smoke，并在 2026-06-15 scheduled run 后核验新镜像、dividend meta、事件 task 与可见上界；连续两个交易日全绿作为 TODO 后续收口。

### 最新补充（2026-06-13）：PRD_20260613_02 v3 Calmar 门合理性分析已实现

- 分支 `codex/calmar-gate-analysis` 已按 PRD_20260613_02 产出只读分析脚本 `scripts/strategy1/analyze_calmar_gate_feasibility.py`、报告 `docs/分析-策略1v3Calmar门合理性-20260613.md` 和 6 个小 CSV；脚本显式读取 ADS 三表历史 replay 源与 research true5y CA-on baseline NAV，不写 BigQuery/GCS，不改 contract / acceptance / registry。
- 脚本复用 `replay_acceptance_gate_v3.py` 的复合年化、Sharpe、MaxDD、Calmar 与 relative gate helper，并新增单测覆盖指标对账、canonical backtest 去重和 A/B/C/D option gate 分离；未新增 metric freeze 清单内本地指标定义。
- 关键读数：8 指数长窗 Calmar 区间 `-0.1024..0.1089`，replay 短窗 `0.6557..1.3868`；当前 true5y CA-on baseline 拼接口径长窗 Calmar `0.4103` / Sharpe `0.6685`，短窗 Calmar `1.1041` / Sharpe `1.4636`；当前 CA-on NAV 上重算的无摩擦 exposure 上界最优 `two_state_biweekly_elow0_cost0bps` Calmar `0.6455` / Sharpe `0.7478`；历史 canonical Top5 replay 仍为 `1 accepted / 24 rejected`。
- 预登记判读：因当前 CA-on exposure 上界 `0.6455 > 0.5`，长窗“物理不可达”强判据未完全成立；但长窗 beta/baseline 均远低于 1.0，短窗/滚动窗出现 1.0 量级读数，核心结论收敛为“v3 Calmar 门高度窗口敏感，owner 需先钉死 production acceptance 窗口，再决定 A/B/C/D 门方案或分级”。本轮不做门变更、不 promotion、不标 baseline accepted。
- 验证通过：`PYTHONPATH=src python3 -m pytest -q tests`（281 passed）；`git diff --check`；脚本实跑成功生成报告/CSV。

### 最新补充（2026-06-13）：PRD_20260613_01 P1 市值规则修复双选项 paper 批量已完成

- 分支 `codex/p1-rules-paper-batch` 按 PRD 扩展 `scripts/strategy1/analyze_topdown_lot_phase0.py`：P1 NULL reason 细化为字段级 `tail_risk:null_<field>`，市值字段归市值组、形态字段归形态组；T0/T1 既有过滤行为保持，新增 T1a（仅形态组）、T1b1（饱和回退到 T1a）、T1b2（饱和回退到 T0）三臂，并把 0.60 主阈值与 0.50/0.70 附表阈值固定在 paper 层。
- 新增/更新单测覆盖规则分组、T1a 放行/拦截、`p1_marked_rate > 0.60` 严格边界、回退只影响当次调仓；metric freeze 守门未新增冻结清单内本地指标定义。
- 只读 BigQuery + 本地 pandas 实跑完成，resolver 解析到 true5y CA-on baseline：prediction `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01`，backtest `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01`。主判读 matched official cost / walk_depth=50：T0 CAGR=`11.81%`、MaxDD=`-58.67%`、Calmar=`0.201`；T1 CAGR=`-4.14%`；T1a CAGR=`6.26%`；T1b1 CAGR=`4.24%`；T1b2 CAGR=`4.11%`。
- 预登记判读：T1a/T1b1/T1b2 均未同时满足 “CAGR gap > -2pp / 2022-05 episode 平均现金 <30% / MaxDD 不比 T0 差超 2pp / crunch 超额不比 T1 差超 3pp”；报告结论为若进入 Phase 2，建议用 T0（无 P1）口径，PRD_10 的 P1 绑定条款需 owner 决策修订。本轮不做 accepted / promotion / 默认 profile 变更，不写任何 BigQuery 数据集，不改 ledger/runner/catalog。
- 交付报告 `docs/分析-策略1P1市值规则修复双选项-20260613.md`；小 metrics CSV `docs/analysis_strategy1_p1_market_cap_rules_20260613_metrics.csv` 随 PR 入库；大 daily/audit CSV 已上传 `gs://ashare-artifacts/reports/strategy1/p1_market_cap_rules/analysis_date=20260613/`。
- PR #210 Claude review low follow-up 已补报告口径说明：Phase 0 报告使用 effective-window prediction 流，本轮按 resolver 切到 true5y CA-on 研究 baseline；T1-T0 CAGR gap `-13.70pp -> -15.95pp` 源于 prediction 流切换，不能直接横向比较为实现差异。

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
