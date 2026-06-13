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
- 被冻结的指标/格式化函数（`fmt_num/fmt_pct/markdown_table` 等）新增首个共享落点 `src/quant_ashare/strategy1/report_format.py`（零重依赖、可安全 import）：PR #222 的 cash-overlay 探针曾本地重定义致 `test_metric_definition_freeze` 红，已抽共享模块复用并更 allowlist 修复（分支 `fix/freeze-allowlist-cash-overlay-fmt`）。其余脚本本地副本可后续逐步收敛到该模块（`markdown_table` 带 `float_format` 兼容 `.4f`/`.6f`）。

### 开放主线

- `OPEN_QUESTIONS.md` 只剩 OQ-010：继续寻找可 accepted 的 Cloud Run Python baseline / 组合构造 / 风控路线。
- PRD_20260613_02 v3 Calmar 门合理性分析已产出只读证据；据此形成的契约 v4 提案（PRD_20260613_05，PR #214 定稿）本版已被 owner 否决（DECISION-20260613-01：长窗 MaxDD 必须硬门，不接受 sign-off 软门），v3 仍是唯一有效契约，修订重提由 owner 决定。PRD_20260613_04 已完成代码口径修订与 Phase 2 live：`ledger_exec_v2_lot100_topdown` 允许 `diagnostic_only`，QA-TOPDOWN-6/7/8 按 profile 条件化；`_v01` live 结果因 topdown retained 持仓未进入 `plan` 的 ledger bug 作废，修复后 `_v02` research-only T0 重跑和外接 QA 四件套已通过。预登记判读仍为 topdown 证伪（长窗 CAGR `11.96%`、Calmar `0.2104`、MaxDD `-56.85%`、平均现金 `2.51%`），不得 promotion / accepted / default。修复后现金拖累已缓解，但 ceil-lot 单票集中仍劣于 v1；PR #218 用只读 paper 探针测试**严格** `max_single_weight` 上限证明上限也救不回（最好 Calmar `0.2018` ≈ 无上限、仍是 v1 `0.41` 一半，MaxDD `-52%~-62%` 未改善），**owner 据此裁决 topdown 自上而下整手构造路线收口（DECISION-20260613-02）**——深回撤是满仓系统性回撤、v1 的 ~30% 现金是回撤保险，下一步转 market-state 条件化现金/仓位管理（待 owner 启动）。尾部风险后续路线、R14 长训练窗口覆盖审计和 OQ-005 短观察窗仍是待办方向，具体下一步以 `TODO.md` 为准。

## 最近补充（最近 7 条）

### 最新补充（2026-06-14）：PRD_20260613_06 大盘价值 long-only P0 live 完成——预登记证伪（STOP）

- P0 主 arm（`pv_fin_quality + label_horizon=20 + weight_version=logmv_xs_monotone_v0 + n20/w075 + biweekly + CA-on + diagnostic_only + market_state_v1`）已 live 跑完：6 年逐年 selection+final-refit→`synthetic_continuous` 合成（prediction `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_h20_wvlmv_largecap_value_v01`，2.64M 行）→ CA-on continuous backtest（`bt_..._h20_wvlmv_..._ca01`，NAV 1314 行 2021-01-04..2026-06-09，单一连续、无 resume）。一次性镜像 `strategy1-cloudrun-runner:largecap-value-prd06-1c6ce44`，4 个 Strategy1 job 跑时 pin、跑后已还原 `:latest`。
- 对照（contract，replay helper）：**长窗 Sharpe 0.6685→0.7499（+0.0814）/ CAGR 15.36%→15.15% / Calmar 0.4103→0.4048 / MaxDD −37.43% 持平**；近窗 Sharpe 1.4636→**1.1060**（变差）/ CAGR 38.28%→28.54%。回测可信：NAV 连续、单日收益 [−9.08%,+7.13%]、无极端跳变、长窗 MaxDD 与 v1 持平。
- **预登记判读 = STOP（机制未兑现）**：主判据长窗 contract Sharpe +0.0814 **< 预登记停做线 +0.10**；远未达 1.5、也不在 [0.9,1.2] 降级区间；近窗反而更差（2024-2026 偏小盘/反转，大盘价值倾斜让出超额）；长窗 MaxDD 持平印证 alpha/构造不动满仓系统性回撤。证伪与探针 caveat 吻合（long-only 连 1.2 大概率都需融券空头腿）。
- 预登记机制有效（可证伪、被证伪、无事后挑窗）；按预登记**不跑对照 arm**（n10/消融/w2），除非 owner 重新决策。下一步留 owner：是否解禁大盘融券空头腿（脱离 long-only，§1.3 降级路径）。research-only、不 promotion、不标 accepted；v1 黄金 hash / 默认语义 / 既有 set 未变。报告 `docs/分析-大盘价值倾斜LongOnly重训对照-20260614.md`。

### 最新补充（2026-06-13）：PRD_20260613_06 大盘价值倾斜 long-only P0 代码实现完成（live 待跑）

- 分支 `experiment/largecap-value-longonly-prd06`（PR #224，模式 B：Claude 实现、Codex 审），PRD 经 Codex 6 轮 review 定稿后实现 P0：① `label_horizon`(=20) 一等参数贯通 orchestrate/annual_pipeline_scheduler CLI、Experiment(to_params/from_b64)、CV embargo(task_fanout 注入)、label-safe 窗口截断、synthetic_continuous；② `weight_version` 全链路（CLI→Experiment→training_panel→panel SQL CASE→run_id→write_registry→synthetic_continuous 派生），panel `build_training_panel_risk_feature.sql` sample_weight 由 `p_weight_version` 驱动（constant_1p0_v0 恒 1.0=v1；logmv_xs_monotone_v0/_w2_v0 按每日截面 log_total_mv min-max 倾斜 [1.0,3.0]/[1.0,2.0]）；③ 选模型 6 处 evaluate_scores topn 对齐 holdings（非默认 arm），model_quality_parity 对 n30/h5 bqml reference 口径错配降级 `skipped_caliber_mismatch`（QA 枚举允许集已加）；④ label-safe 年末截断 retire `subtract_weekdays`、改 `LABEL_SAFE_YEAR_END_BY_HORIZON` 冻结派生表（dim_trade_calendar SSE 开市日 + trade_date_seq，2015-2025×h{5,10,20}）+ fail-fast + 对账测试；⑤ synthetic_continuous 去硬编码（horizon=5/feature_set=pv_fin_risk/feature_version=pv_v0）→ 从 source registry 派生唯一 lineage + 不一致 fail-fast，新增 `--emit-backtest-experiment-json` 把 CA-on(cash_div_and_split_v1/flat_10pct)+ diagnostic_only 烤进 base64 Experiment payload（因 backtest_report `--experiment-json` 路径忽略 CLI override）。
- v1 复现红线保住：默认 arm（h5 + constant_1p0_v0）run_id/选参/valid/refit 窗口、sample_weight 恒 1.0、选模型 topn=30、synth registry（v1 lineage）字节级不变；未碰 ledger/portfolio/order SQL，ledger 黄金 hash 不变；不扩域；未改既有 3 个 feature set 列定义；未写任何 ADS/生产数据。
- 验证：全仓库 `PYTHONPATH=src python3 -m pytest -q tests` **309 passed / 1 skipped**（BQ 对账 RUN_BQ_RECON=1 才跑）；`generate_sqlx_from_sql.py --check`、`git diff --check` PASS；已 merge origin/main（含 PR #223 metric-freeze 修复）。Codex(GPT-5.5+xhigh) review（off origin refs）发现并修复 2 处：parity 枚举兼容（QA-CR-4 / QA-SKN-8 加 skipped_caliber_mismatch）、`annual_pipeline_scheduler.py` 补 `--label-horizon`/`--weight-version`；复核可合并。#8 synthetic_continuous 由隔离 worktree 子代理实现、主会话审 diff 后 cherry-pick。
- **live 待跑**：owner 选「Codex review 过即自动跑主 arm」。下一步：PRD §10 BQ 核验 → 从分支重建 Strategy1 runner 镜像 → 主 arm `pv_fin_quality+h20+logmv+n20`（≈74 execution）→ 外接 QA → 与 v1 逐窗对照报告（长窗 contract Sharpe 主判据 0.6685→1.5，停做线 <+0.10）。research-only、不 promotion、不标 accepted。

### 最新补充（2026-06-13）：PRD_20260613_04 topdown Phase 2 T0 live 修复后重跑完成

- `_v01` live 结果已撤回：独立复核代码与 BigQuery 后确认根因为 `build_daily_plan_topdown` 对 rank ≤ `walk_depth` 的 retained 持仓只 `retained.add(sec)`、不输出 `PlanRow`，而主循环 `update_holdings(plan)` 只从 plan 重建持仓，导致调仓日 retained 持仓无 SELL / 无现金回款地消失；`002245.SZ` 2021-07-26 案例与全局“股数减少且无 SELL/CA 行”查询一致。旧 ceil-lot 诊断被 supersede。
- 本分支只在 `build_daily_plan_topdown` 内为 retained 持仓输出 hold/no-op `PlanRow`，保留 `cur_shares`、`sell_shares=0`、`want_value=0`、无 skip 状态；不改 v1 共用的 `update_holdings`。新增 topdown retained 持仓守恒单测，并在 `qa_topdown_construction_outputs.sql` 增加 `QA-TOPDOWN-11`（股数减少必须由 SELL/CA 解释）和 `QA-TOPDOWN-12`（单日收益 `< -50%` hard sanity）；该 QA 对旧 `_v01` 已按预期失败，job `bqjob_ra6e754e0d10734_0000019ebef0b5ce_1`。
- 已从分支 `codex/topdown-phase2-live` 构建含修复的 one-off Strategy1 runner 镜像 `topdown-p2-retained-fix-7a70d98-20260613-04`，digest `sha256:0e3f3c7751ab4be4cbcefc94529c5ef51f663a89ef7609e4d5d4c662779cb016`，Cloud Build `a0aa7fb7-a26c-4480-bdb9-1163ed410b5d`；未更新 `latest`（仍为 `sha256:fdb61f8141e240c377b3faaa21b5e6efef9c783ebb9e04923ff3b675b8d54bc2`），`strategy1-backtest-report-job` pin 到 generation 55，boot smoke `strategy1-backtest-report-job-4hh4d` 成功。
- 修复后正式 Phase 2 run/backtest `s1_topdown_t0_continuous_true5y_2021_2026_v20260613_02` / `bt_s1_topdown_t0_continuous_true5y_2021_2026_v20260613_02` 已用 digest `sha256:0e3f3c...` `--force-replace` 完成（execution `strategy1-backtest-report-job-2lpzn`）。参数：resolver 解析 prediction `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01`，fresh continuous `2021-01-04..2026-06-09`，CA-on `cash_div_and_split_v1` / `flat_10pct`，`tail_risk_profile_id=diagnostic_only`，`ledger_exec_v2_lot100_topdown`，`cloudrun_lot100_topdown_resume_v1`，`--skip-diagnosis --skip-tail-risk --skip-qa`，research-only。
- 外接 QA 四件套全过：continuous `bqjob_r13624ec7b8c6f625_0000019ebefb96b8_1`（显式 topdown ledger/resume 覆盖）、lot-aware `bqjob_r34586777e4e7223b_0000019ebefbcda9_1`、topdown `bqjob_r4eaa32102a6d2982_0000019ebefbedf2_1`、CA ledger `bqjob_r15a60913a1b1c58c_0000019ebefc0d61_1`。持仓守恒和单日收益 sanity 只读复核均 0 行；ADS 9 张表反查 job `bqjob_r7238d2f3c49e6c60_0000019ebefca18a_1` 为 0，`ashare_research.research_promotion_manifest` 反查 0。
- 三方对比报告 `docs/分析-topdownPhase2三方对比-20260613.md` 与小 CSV `docs/analysis_topdown_phase2_comparison_20260613.csv` 已重做。预登记判读为 **topdown 证伪**，但基于修复后真实 `_v02` 数字：长窗 CAGR `11.96%`、compound Sharpe `0.3821`、Calmar `0.2104`、MaxDD `-56.85%`、平均现金 `2.51%`，低于 v1 official baseline（CAGR `15.36%` / Sharpe `0.6685` / Calmar `0.4103` / MaxDD `-37.43%`）且与 Phase 0 paper T0 互近；本轮不 promotion、不 accepted、不改 v1/default。
- 最终本地验证：`PYTHONPATH=src python3 -m pytest -q tests` 297 passed；`python3 scripts/dataform/generate_sqlx_from_sql.py --check` passed；`git diff --check` passed。

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
