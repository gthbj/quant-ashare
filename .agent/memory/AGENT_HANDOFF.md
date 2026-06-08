> 当前交接补充（2026-06-08，GPT-5 Codex）
> - PR #114 review follow-up 已加硬 `v3` 切门 PRD：补了 `Sharpe` / `Calmar` / `Excess Calmar` 的除零规则、`max_drawdown` 负号约定、`策略最大回撤同期超额` 的窗口与价格字段定义。
> - 也补了五指数 `sec_code`、`000001.SH` 主 benchmark 的职责说明，以及“默认 `2024-01-02..2026-04-30` 只是首次 replay / cutover 默认窗口，不是未来月度滚动重训的永久硬编码窗口”。
> - 本次仍是 doc-only，不改 acceptance 实现；下一步继续是 `model_acceptance_contract_v3.yml -> replay -> QA -> live cutover`。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - 已新增 `docs/prd/PRD_20260608_02_策略1验收门v3切换实施.md`，把后续切门路线冻结为直接 `v1 -> v3`，明确忽略 `v2`。
> - 本次只写 PRD，不改 acceptance 实现、不改 manifest、不改 QA；当前 live search 仍使用 `model_acceptance_contract_v1.yml`。
> - `v3` 何时可用的标准已写清：先落 `model_acceptance_contract_v3.yml`，再做历史正式搜索 replay、补 `v3` QA，最后才切主写回门。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - Strategy1 Cloud Run `prepare_matrix` 已修复 JSON 布尔特征误按 `FLOAT64` 解包导致 `train split` 预期列全 `NULL` 的问题；已改为 `BOOL -> INT64`。
> - 已用 `configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml` 跑通 `12` 候选 LightGBM regression smoke，主 benchmark 为 `000001.SH`，`*_vs_primary_benchmark`、Top1 backtest、comparison artifacts 链路已验证。
> - 最终 smoke `search_id=cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_smoke_20260608_05`，Top1 为 `lgbm_r03_l63_lr002_n600_leaf300_ff09_bf09_l1_01_l2_1`，结果 `rejected`，原因为 `overall_excess_return_vs_primary_benchmark<=0.0;sharpe<0.7;max_drawdown<-0.25`。

## 当前交接摘要（2026-06-08）
- OQ-005 phase 1 foundation 仍保持已部署状态：`ashare-pipeline-control` Cloud Run service、`ashare_ods_ingestion_daily` 和 `ashare_warehouse_window_refresh` 两个 Workflows 已上线，既有 `qa_only` 与 `daily_current` smoke 继续作为当前 live 通过证据。
- `ashare_pipeline_alert_checker` 已按 owner 要求改为“最多每小时 1 次”：Composer 过渡态 DAG schedule 改为 `0 * * * *`，lookback 统一到 `70` 分钟，heartbeat 缺失告警窗口统一到 `120` 分钟；同时已补 `ashare-pipeline-control` `/v1/tasks/alert-check` 和 `orchestration/workflows/deploy_scheduler_jobs.sh`，为 cutover 后的 `Cloud Scheduler + Cloud Run` 小时级告警检查准备好入口。
- `airflow_monitoring` 已确认是 Composer 平台托管健康监控 DAG，不能在仓库代码里单独降频；只要 Composer 环境还在，它就会继续按平台频率运行。要真正把这部分 run 和固定底座费用降掉，必须完成 OQ-005 cutover 并删除 Composer 环境。
- `ashare_warehouse_full_rebuild` 已补出 Workflow 草案，但 review follow-up 已把它从标准 `deploy_workflows.sh` 中移出；现在只有显式 `DEPLOY_FULL_REBUILD=true` 才会部署。当前 `ashare-pipeline-control` 的 BigQuery task 仍同步等待 `job.result()`，full rebuild 长 SQL 有 Cloud Run / Workflows 单步超时风险，因此它仍是代码草案，未部署、未 smoke。
- `ashare-pipeline-control` 镜像现在会一起打包 `scripts/alerting`，避免 `service.py` 模块级导入 alert checker 时报 `ModuleNotFoundError` 导致整个控制面启动崩溃。后续启用 `Cloud Scheduler` alert checker 时，必须同时 pause / delete Composer DAG `ashare_pipeline_alert_checker`，避免双跑。

# Agent 交接（Agent Handoff）

本文件保存供后续 Agent 使用的最新交接记录。新交接用 `templates/HANDOFF_TEMPLATE.md` 追加到底部，并同步刷新下面的「当前交接摘要」。

> **语言约定（2026-06-01 起）**：新增交接条目一律用中文撰写；下方此前的英文历史条目保留原样作为记录，不回译。

## 当前交接摘要

- **2026-06-08 GPT-5 Codex：PR #112 review follow-up 已把不安全路径真正封住。** `Dockerfile.pipeline_control` 已补 `scripts/alerting` 到镜像，避免 `service.py` 模块级导入 `scripts.alerting.check_alerts` 时导致整个 `ashare-pipeline-control` 启动崩溃。`deploy_workflows.sh` 默认只部署 `ashare_ods_ingestion_daily` 和 `ashare_warehouse_window_refresh`；`ashare_warehouse_full_rebuild` 改为显式 `DEPLOY_FULL_REBUILD=true` 的 opt-in 路径，直到控制层 BigQuery 改成 async submit + poll 为止。README 也已补明：启用 `Cloud Scheduler` alert checker 时需同时 pause / delete Composer DAG `ashare_pipeline_alert_checker`，避免双跑。
- **2026-06-08 GPT-5 Codex：OQ-005 告警检查已统一限频到每小时。** `ashare_pipeline_alert_checker` 在 Composer 过渡态中的 schedule 已改为 `0 * * * *`，`check_alerts.py` lookback 调整为 `70` 分钟，heartbeat 缺失告警窗口调整为 `120` 分钟；cutover 后同一小时级口径将由 `Cloud Scheduler -> ashare-pipeline-control /v1/tasks/alert-check` 延续，部署脚本为 `orchestration/workflows/deploy_scheduler_jobs.sh`。
- **2026-06-08 GPT-5 Codex：`airflow_monitoring` 不能在仓库内单独降频。** 已确认它是 Composer 平台托管健康监控 DAG；只要 Composer 环境存在，它就会继续按平台频率运行。停止这类 run 和固定 `standard milli DCU-hours` 费用的路径是完成 OQ-005 cutover 并删除 Composer 环境，而不是继续在 repo 中找调频开关。
- **2026-06-08 GPT-5 Codex：`ashare_warehouse_full_rebuild` 目前仍是代码草案。** 已新增 `orchestration/workflows/ashare_warehouse_full_rebuild.yaml` 并接入 `deploy_workflows.sh`，但当前 `ashare-pipeline-control` 的 BigQuery 执行仍同步等待 `job.result()`；在改成 submit + poll 或进一步拆步前，full rebuild 长 SQL 存在 Cloud Run / Workflows 单步超时风险，因此现在未部署、未 smoke。
- **2026-06-08 GPT-5 Codex：OQ-005 Workflows phase 1 foundation 已部署并通过最小 live smoke。** 已新增 `tests/pipeline_control/test_state_lock.py` 覆盖 `acquire -> generation lookup -> heartbeat -> release`，并本地跑通 `unittest`。GCP 侧已启用 `workflows.googleapis.com`、创建并授权 runtime service account、部署 `ashare-pipeline-control` Cloud Run service，以及 `ashare_ods_ingestion_daily` / `ashare_warehouse_window_refresh` 两个 Workflows。真实 `qa_only` execution `aaad21db-7c1a-4cb2-92fb-55158edfa3a3` 与 `daily_current` 父/子 executions `2085f593-0fe9-483c-8888-6fa48fe7bb2f` / `d305d8a3-99a1-4007-9fb2-94e3698ff55c` 已 success。live 部署同时暴露并修正了 Workflows `http.* timeout <= 1800s`、布尔参数比较、窗口 SQL 必须透传 `warehouse_mode` 等运行期契约问题。当前仍未 cutover，下一步是迁 `ashare_warehouse_full_rebuild` / `ashare_pipeline_alert_checker`、补 `backfill` / 非交易日 skip smoke、接 Cloud Scheduler 并完成 shadow run / 删除 Composer。

- **2026-06-08 GPT-5 Codex：PR #108 comment follow-up 已把迁出 Composer PRD 加硬到实现级。** 已补 4 个 Workflows 易静默退化点：每个业务步骤都要显式写 `pipeline_task_status`，不能只写 start/finalize；`ashare_warehouse_window_refresh` 必须有显式分布式锁，不能假设存在 `max_active_runs=1`；生产 scheduled ingestion -> refresh 固定为同步 child workflow 调用，旧 `warehouse_refresh_missing` watchdog 只保留到迁移期；BigQuery / Cloud Run 调用按“提交 -> 轮询终态 -> 写状态”建模，并要求 Phase 1 先复核 Workflows 限额和 `full_rebuild` 是否要拆分。

- **2026-06-08 GPT-5 Codex：OQ-005 长期目标改为迁出 Composer。** 已新增 `docs/prd/PRD_20260608_01_OQ005调度完全迁出Composer.md`，明确当前 Composer 费用主体是常驻 `standard milli DCU-hours` 底座，而现有 DAG 主要只做编排。长期架构改为 `Cloud Scheduler + Cloud Workflows + Cloud Run Jobs + BigQuery SQL/Dataform`，单步 `ashare_pipeline_alert_checker` 迁到 `Cloud Scheduler + Cloud Run`；当前 Composer DAG 拆分、window refresh、alert checker 和 smoke 只视为 cutover 前过渡态，目标是在迁移验收后删除 Composer 环境。

- **2026-06-08 GPT-5 Codex：策略 1 runner / acceptance 默认 benchmark 切到上证指数并完成独立 replay。** 已把 BigQuery SQL runner `08/09`、Cloud Run Python ledger、OQ-010 调度器默认 `p_benchmark`、v2 acceptance contract、报告渲染和相关 QA/诊断默认 benchmark 从 `000852.SH` 切到 `000001.SH`，并把 v2 诊断 artifact 与 live 搜索 acceptance 路径的主 benchmark 字段名统一为 `*_vs_primary_benchmark`。随后用新 ids `s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01` / `bt_s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01` 重跑 fixed-prediction lot-aware reference，不覆盖旧 `000852.SH` 审计结果；`10` 采用 fixed-prediction split override 手工补跑，`10/12/20/22/23` QA 已通过。新的 acceptance artifact `acceptance_gate_v2_lotaware_ref_bm000001_20260608_01` 仍为 `rejected`，原因是 `full_period_excess_return_vs_primary_benchmark<=-0.03` 与 `full_period_information_ratio<0.0`。

- **2026-06-08 GPT-5 Codex：index benchmark QA 日期上限修复。** PR #106 合并后的 Composer smoke 验证新增 `market_state_dws` / `market_state_checks` 成功，但后置 `qa_after_window.index_benchmark_checks` 因默认扫到 `CURRENT_DATE` 而在 2026-06-08 当天 000001.SH 未到数时误失败。新分支 `codex/fix-index-benchmark-qa-date-bound` 已将 `sql/qa/03_index_benchmark_checks.sql` 默认 `dwd_end_date` 改为 DWD 中 `000001.SH` 完整 price + dailybasic 可用的最新 SSE 开市日，并真实跑通 `03` QA。

- **2026-06-08 GPT-5 Codex：PR #106 comment follow-up。** 已按 review 修复 market-state 日更全表重建问题：新增 `sql/incremental/03_refresh_market_state_window.sql`，Composer `windowed_transform` 改为窗口 MERGE；`sql/dws/08_dws_market_state_daily.sql` 只保留初始化 / full rebuild。`market_state_v0_20260606` 的 `sse_composite_*` 字段改为 `NULL`，`market_state_v1_20260607` 才填充上证指数指标，`11_market_state_checks` 已补断言。ODS index external table URI SQL 改为由 `scripts/ingestion/generate_index_external_table_uris.py` 从 current-scope manifest 生成，可用 `--check` 防漂移。

- **2026-06-07 GPT-5 Codex：上证指数 `000001.SH` ODS/DIM/DWD/DWS 补齐。** 已把 `index_daily_000001_SH` / `index_dailybasic_000001_SH` 加入 current-scope manifest、ODS external table 显式 `sourceUris`、`dim_index` seed 和 `dwd_index_eod`；BigQuery 手工补数和 2019-01-01 至 2026-06-05 指数窗口 backfill 均完成，`03` / `05` / `12` QA 通过。后续按 owner 要求创建 `ashare_backup`，把修改前 `dws_market_state_daily` 备份为 `ashare_backup.dws_market_state_daily_v0`，生产 DWS 已重建为 `market_state_v0_20260606` 兼容行 + `market_state_v1_20260607` 上证指数字段行；本次不写 ADS，不改变 risk-off 触发逻辑。

- **2026-06-07 GPT-5 Codex：合并后分支 / worktree 清理约束扩展。** Owner 要求把已有分支卫生规则扩展到对应独立 `git worktree`：PR 合并后，若 owner 未要求保留，应删除已合并且不再使用的 `codex/*` 本地分支、对应远端分支，并移除为该分支创建的独立 worktree；若 worktree 仍有未提交或未合并改动，先暂停并请 owner 决策，不得强删。

- **2026-06-07 GPT-5 Codex：Strategy1 风险特征 wave 4 Cloud Run 真实执行完成。** 在 `main=10cbd46c1524888d03c71c643ed7959eb1c998be` 基线上构建/部署 runner `riskfeatfix-10cbd46-20260607-04`（digest `sha256:e7d6c5e3c86293046166b8930f6016256fb6f43a46d02be54552b303fc9a6ada`），binary 与 regression 两条风险特征 manifest 均完成 20/20 candidate fanout、Top5 backtest/report、`19` QA、`21` QA；两条 Top5 均被 acceptance contract 拒绝，未产生 accepted baseline。Runtime 修复已并入 PR #103，并已同步到 `main`。

**OQ-010 风险特征入模 PR #102 review follow-up（2026-06-07）**：工作树 `/Users/luna/Desktop/git/quant-ashare-risk-feature-impl`，分支 `codex/implement-risk-feature-search`。已按 PR #102 comment 修复两项：风险专项 `max_drawdown >= -18%` 目标不再由 Python 常量 / SQL 默认值硬编码，而是写入 `configs/strategy1/model_acceptance_contract_v1.yml` 的 `thresholds.min_full_period_max_drawdown` 并由 `acceptance.py` 统一输出 `p_risk_feature_max_drawdown_target`；`21_qa_risk_feature_search_outputs.sql` 默认改为 `NULL` 并新增 `QA-RISK-0`，未注入 contract 参数的 standalone 真执行会 fail-loud。`final_holdout_status` 派生逻辑已移入共享 `acceptance.py`，orchestrator 删除重复函数。验证通过 Python `py_compile`、v1 contract 参数确认、原始/注入版 `21` QA BigQuery dry-run、risk feature orchestrator dry-run 和 `git diff --check`。尚未真实跑 Cloud Run 40 候选 / Top5 回测。

**OQ-010 风险特征入模第 4 波实现（2026-06-07）**：工作树 `/Users/luna/Desktop/git/quant-ashare-risk-feature-impl`，分支 `codex/implement-risk-feature-search`。已实现 `strategy1_pv_fin_risk_v0_20260606` 训练路径：新增 95 列 feature set 契约、Cloud Run 专用训练面板 SQL、binary/regression 各 20 候选 manifest、矩阵 `feature_delta_vs_base.json`、feature schema hash、风险/市场特征缺失率、LightGBM feature importance、风险专项 acceptance overlay 和 `sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`。验证已通过 Python 编译、manifest/orchestrator/prepare_matrix dry-run、训练面板 SQL 与 `21` QA BigQuery dry-run、feature_column_list 顺序一致性检查和 `git diff --check`。尚未执行真实 Cloud Run 40 候选训练 / Top5 回测，未建立 baseline；合并后下一步是构建/部署 runner 镜像，依次跑 binary 20 与 regression 20，并用 `19` + `21` QA 收口。

**OQ-010 整数手交易执行收口（2026-06-07）**：PR #100 已合并，PR #101 已修复 portfolio-only 报告/诊断的 `prediction_run_id` 透传并合并；临时分支/工作树已清理。镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:lotaware-c018ef5-20260607-01` 已构建并部署到 `strategy1-backtest-report-job`。Cloud Run execution `strategy1-backtest-report-job-h7vtl` 成功完成 fixed-prediction lot-aware reference：`run_id=s1_lotaware_ref_pvfq_n30_bw_h5_20260606_01`、`backtest_id=bt_s1_lotaware_ref_pvfq_n30_bw_h5_20260606_01`、`prediction_run_id=s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01`，覆盖 `2024-01-02` 至 `2026-04-30`，`ledger_version=ledger_exec_v1_lot100`。结果：total_return 35.17%、excess_return -7.20pct vs `000852.SH`、Sharpe 0.872、max_drawdown -13.59%；report、model diagnosis、tail-risk artifact 和 acceptance gate v2 artifact 均 uploaded。`10`/`12`/`20` 在 Cloud Run 内通过，手工复核 `22`/`23` 通过。acceptance gate v2 diagnosis `acceptance_gate_v2_lotaware_ref_20260607_01` 仍为 `rejected`，原因是全期跑输中证1000超过 3pct、IR 为负、2026 final_holdout 跑输中证1000 12.75pct。当前可进入下一模型族 / 风险特征训练路线。

**OQ-010 验收门 v2 实现（2026-06-06）**：PR #98 已合并；实现工作树 `/Users/luna/Desktop/git/quant-ashare-acceptance-gate-v2-impl`、分支 `codex/implement-acceptance-gate-v2` 的 v2 契约、只读诊断脚本和 `22` QA 已进入 `main`。已新增 `configs/strategy1/model_acceptance_contract_v2.yml`、只读脚本 `scripts/strategy1/diagnose_acceptance_gate_v2.py` 和 `sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`，并扩展 `scripts/strategy1_cloudrun/acceptance.py` 支持 contract hash / v2 SQL 参数。诊断脚本只读 ADS/DWD/DWS，不训练、不改 prediction、不写 ADS；默认 reference run/backtest 为 `s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01`，输出 `acceptance_gate_v2/` artifact、10/20/30/40 组合可行性、eligible benchmark、score orientation audit、低价股偏移、现金/实际持仓和风格暴露诊断。uploaded 模式成功，GCS URI：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/acceptance_gate_v2/diagnosis_id=acceptance_gate_v2_reference_20260606_01`，16 个对象；`22_qa_acceptance_gate_v2_outputs.sql` 注入真实 contract hash 后真实执行 9 个 ASSERT 全部通过，默认 standalone placeholder 已改为在 `QA-V2-1` fail-loud。当前 v2 结论：reference run 为 `rejected`，原因是跑输 `000852.SH`、full-period IR 为负、2026 final_holdout 严重跑输；拒绝范围仅限当前 top-30 long-only 实现，不否定信号家族。`10/5%` 是 `diagnostic_only`，`20/30/40` 因局部现金峰值为 `needs_more_evidence`，没有 implementation hard fail。后续已转为先实现整数手 lot-aware ledger。

**OQ-010 风险特征入模 Phase B0 实现（2026-06-06）**：PR #94 已合并；工作树 `/Users/luna/Desktop/git/quant-ashare-risk-feature-impl`，分支 `codex/implement-risk-feature-acceptance-diagnosis`。新增 `scripts/strategy1/diagnose_acceptance_window.py`，用于 PRD Phase B0 只读诊断：读取既有 ADS / artifact，重切 BQML historical reference 的 2025-only 指标，并汇总 sklearn native、LightGBM binary、LightGBM regression 三波已拒 Python Top5 候选；不训练模型、不重跑 BQML、不执行 `sql/ml/strategy1` SQL runner、不写 ADS。PR #96 review follow-up 已统一 maxDD 门口径：2025 excess 仍看 2025 段，风险 maxDD 门使用 full-period summary，报告同时展示 test maxDD 与 full maxDD。uploaded 模式已成功，artifact URI 为 `gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/acceptance_window_diagnosis/diagnosis_id=riskfeat_acceptance_window_20260606_01`。诊断结论 `primary_blocker=mixed_evidence`：BQML historical reference 2025-only excess -23.43%、test maxDD -10.06%、full-period maxDD -14.48%；15 个 Python 候选中 10 个 2025 excess 未过、5 个 full-period maxDD 未过，same-side fraction 66.67% 低于 80% 阈值。后续不应自动启动第 4 波风险特征训练，应先由 owner / 审查者复核诊断结论。

**OQ-010 风险特征入模 PRD（2026-06-06）**：工作树 `/Users/luna/Desktop/git/quant-ashare-risk-feature-prd`，分支 `codex/prd-strategy1-risk-feature-baseline`，PR #94。新增 `docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md`，承接 PRD04 LightGBM binary/regression 均 rejected、尾部风险 P1 轻度改善但仍跑输、P2 v0 `skip_new_buys` 降收益且未改善回撤的事实。PRD 将下一步收敛为风险特征入模：新增 `feature_set_id=strategy1_pv_fin_risk_v0_20260606`，把个股尾部风险字段、`dws_market_state_daily` 市场状态字段和风险 flag 纳入 Cloud Run frozen matrix；P0 固定 `diagnostic_only`、40 候选 / 20 并发 / 2 vCPU 8Gi、LightGBM binary + regression、共享 acceptance contract；P1 才评估 `risk_score_penalty_v0` 候选风险评分。PR #94 review follow-up 已补 `test_reuse_wave_no=4` / final_holdout passed 要求、训练前只读 `acceptance_window_diagnosis`、`feature_delta_vs_base.json`、market-state 贡献展示，以及风险专项 accepted 目标 `max_drawdown >= -18%`。本次只写 PRD 和记忆/TODO，未改代码、未运行 BigQuery / Cloud Run。

**OQ-010 尾部风险 P2 market risk-off 实跑结论（2026-06-06）**：PR #92 已合并；`dws_market_state_daily` 已物化并通过 `sql/qa/11_market_state_checks.sql`（562 行，risk-off 91 日）。已构建/部署 runner 镜像 `tailrisk-p2-6db6bd9-20260606-01`，并用 `configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml` 并发跑完 diagnostic-only、`market_risk_off_v0`、`individual_and_market_risk_guard_v0` 三条 portfolio-only A/B。结果：diagnostic-only total_return 38.25%、Sharpe 0.882、max_drawdown -14.46%；market-only total_return 28.20%、Sharpe 0.734、max_drawdown -15.72%，market skip 217 笔；combo total_return 30.04%、Sharpe 0.773、max_drawdown -14.71%，market skip 217 笔、tail-risk skip 3 笔。三条 report / model diagnosis / tail-risk diagnosis / `10` / `12` / `20` 均 succeeded 并上传 GCS。结论：P2 v0 `skip_new_buys` 降低仓位但未改善回撤且显著拖累收益，不采纳为默认策略；后续若继续市场风控，应另写 v1 风险动作/阈值。

**OQ-005 调度运行稳定命名生产 cutover + PR #93 部署（2026-06-06）**：PR #91 已完成生产 cutover：Composer bucket `data/sql/`、新 DAG / alert checker 和 `check_alerts.py` 已同步；旧 `oq005_alert_checker.py`、旧命名 QA/metadata SQL 和旧 `oq005_*` log metrics 已清理；`ashare_pipeline_alert_checker` active，`ashare_ods_ingestion_daily` unpaused，旧 `ashare_daily_pipeline_v0` paused。PR #93 已合并并部署：`ashare_common.py`、`ashare_ods_ingestion_daily.py` 和 `sql/observability/01_pipeline_status_views.sql` 已同步到 Composer bucket / BigQuery。ODS-only skip smoke `manual_pr93_ods_only_skip_20260605_20260606_01` 成功，Cloud Run ingestion tasks skipped，`trigger_warehouse_window_refresh` skipped，`skip_downstream_refresh` 在 `pipeline_task_status` 中为 `skipped`，无 linked warehouse run，`v_pipeline_refresh_missing` / `v_alert_summary` / `check_alerts.py --lookback-minutes 20 --json` 均为空。后续只剩新 DAG 至少两个开市日 scheduled run 和一个真实非交易日 scheduled skip 自然观察，以及 Dataform 生产接入 / shadow 验证。

**Dataform definitions 与调度运行命名清理（2026-06-06）**：工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-dataform-definitions`，分支 `codex/oq005-dataform-definitions`，PR #91。已新增 Dataform 首版 `workflow_settings.yaml`、`action_manifest.json`、生成器 `scripts/dataform/generate_sqlx_from_sql.py` 和 45 个 `definitions/**/*.sqlx`，以 canonical `sql/` 生成 31 个 Dataform operations；`npx --yes @dataform/cli compile dataform` 通过。按 owner 要求清理调度运行代码中的阶段性命名：告警 DAG 文件改为 `ashare_pipeline_alert_checker.py`，QA/metadata SQL 改为 `01_core_smoke_checks.sql`、`03_index_benchmark_checks.sql`、`05_unit_contract_checks.sql`、`01_core_table_column_descriptions.sql`，Composer task_id / Dataform action/tag 改为 `core_*`、`index_benchmark_checks`、`unit_contract_checks`、`qa_core`、`qa_contract` 等稳定命名。PR #91 review follow-up 已补运行命名 cutover runbook、Dataform `--check` 防漂移检查和“线上旧名 vs 目标新名”记忆说明；运行命名已在后续 cutover 中成为线上事实。Dataform definitions 尚未接入 Dataform 生产 / shadow。

**OQ-010 尾部风险 P1 comment follow-up（2026-06-06）**：工作树 `/Users/luna/Desktop/git/quant-ashare-tail-risk-p1`，分支 `codex/implement-tail-risk-p1`，PR #88 已 rebase 到最新 `origin/main` 并按 review comment 修正。最新语义：`05_build_candidates.sql` 只写 `tail_risk:*` 风险标记，不把风险标记股票从 TopN / target 剔除；必需风险字段 NULL 记为 `tail_risk_required_field_null`。Python Ledger v1 与 BigQuery SQL fallback 均新增 `BUY_SKIPPED_TAIL_RISK`：未持仓风险目标跳过新买入，已有持仓不因 P1 标记被强制卖出。`10` / `20` QA 已改为验证未持仓风险目标无真实买入成交且留下 skip 状态。验证：Python `py_compile`、`05/08/09/10/11/20` dry-run 均通过；短区间 smoke 因跳过报告触发 `10` report guard 失败，已确认是 smoke 参数问题并清理临时 ADS 残留为 0。另已在 `KNOWN_CONSTRAINTS.md` 写入 BigQuery 分区表查询/删除/更新必须显式带分区列过滤的项目硬约束。

**OQ-005 warehouse refresh 补跑/resume helper（2026-06-06）**：工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-backfill-resume`，分支 `codex/oq005-backfill-resume`，PR #90。新增通用脚本 `scripts/pipeline/run_warehouse_refresh.py`（文件名不绑定 OQ 编号），支持 `backfill` 分块计划、`qa-only` 计划、`status` 查询、显式 `--execute` 触发 Composer、`--wait --fail-fast` 等待 terminal 状态，以及 `--resume` 按 `ashare_meta.pipeline_run` 精确跳过同一 `warehouse_mode/date_from/date_to` 已 `success` 或 `running` 的窗口。PR #90 review follow-up 已补 `--max-execute-runs` 默认 20 个非 skipped run 的执行上限，超过需缩小日期范围或显式 `--yes`。Composer README 与 OQ-005 runbook 已补脚本入口和手工 `gcloud` fallback。本次只做本地 plan/静态验证，不触发 Composer、不运行 BigQuery DML、不部署生产。按 owner 要求，`KNOWN_CONSTRAINTS.md` 已写入“需要代码在工作树中改，改完推 PR。”

**OQ-005 alert setup review follow-up（2026-06-06）**：分支 `codex/oq005-alert-logmetric-alreadyexists`。针对 `fd8aefe` review 的 Low finding，`scripts/alerting/setup_alerts.py` 已将 log metric 已存在的幂等判断从异常 message substring 改为显式捕获 `google.api_core.exceptions.AlreadyExists`，其他异常仍 fail-fast。该分支只改告警配置脚本和记忆，不改 Composer DAG、BigQuery SQL 或生产调度状态；验证为 `python3 -m py_compile scripts/alerting/setup_alerts.py` 和 `git diff --check`。

## 交接条目

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: main-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: strategy1-benchmark-default-switch-20260608
相关 issue/PR: N/A

### 已完成工作

- 把策略 1 runner / acceptance 的默认 benchmark 从 `000852.SH` 切到 `000001.SH`。
- 更新 BigQuery SQL runner `08/09`、Cloud Run Python ledger、OQ-010 调度器默认 `p_benchmark`、v2 acceptance contract、报告渲染默认评估主基准、runner/benchmark QA 默认断言与诊断默认参数。
- 把 v2 acceptance 诊断 artifact 中主 benchmark 相关字段名从 `*_vs_000852` 改成 `*_vs_primary_benchmark`，避免在默认 benchmark 切换后继续输出误导字段名。

### 重要上下文

- 这次只改了默认值和直接耦合的 QA/报告/诊断口径，没有重跑任何 Cloud Run / BigQuery 历史 reference，也没有改历史 PRD 对 `000852.SH` 的叙述。
- 现有已落库的 historical summary / report / diagnosis / acceptance artifact 仍然是相对 `000852.SH` 的审计结果；如果要正式启用新默认值，下一步必须先做 reference / acceptance replay。

### 改动文件

- `configs/strategy1/model_acceptance_contract_v2.yml`
- `scripts/strategy1_cloudrun/ledger.py`
- `scripts/strategy1/run_oq010_experiments.py`
- `scripts/strategy1/render_report.py`
- `scripts/strategy1/analyze_tail_risk.py`
- `scripts/strategy1/diagnose_acceptance_window.py`
- `scripts/strategy1/diagnose_acceptance_gate_v2.py`
- `scripts/strategy1/diagnose_model_quality.py`
- `sql/ml/strategy1/08_run_backtest.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/11_model_quality_diagnostics.sql`
- `sql/qa/03_index_benchmark_checks.sql`
- `sql/ml/strategy1/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

### 测试 / 验证

- 未运行 Cloud Run / BigQuery runner。
- 未重跑 `03` / `10` / `19` / `22` QA。
- 本次为默认值与口径切换，后续需要 replay 验证历史 reference / acceptance artifact。

### 阻塞项

- 无硬阻塞。

### 下一步建议

- 先用 `000001.SH` 重跑 fixed reference / acceptance replay，确认 summary、report、diagnosis 与 gate artifact 全部换到新主 benchmark。
- 再决定是否把 v1/v2 contract / QA 内部仍沿用的 `*_vs_000852` 阈值键名做兼容重命名。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: workflows-smoke-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: oq005-workflows-smoke-20260608
相关 issue/PR: 待创建 PR

### 已完成工作

- 新增 `tests/pipeline_control/test_state_lock.py`，用 mock GCS 覆盖 `acquire -> lock_generation_for_owner -> heartbeat -> release` 的最小锁契约，并本地跑通 `unittest`。
- 已启用 `workflows.googleapis.com`，创建/授权 `ashare-workflows-runtime@data-aquarium.iam.gserviceaccount.com`，并部署 `ashare-pipeline-control` Cloud Run service 与 `ashare_ods_ingestion_daily` / `ashare_warehouse_window_refresh` 两个 Workflows。
- 为通过真实部署补了 3 处关键 Workflow 修正：BigQuery control call `timeout` 从 `3300` 收敛到 Workflows 上限 `1800`；所有布尔条件改为按布尔值判断，不再和 `"true"` 字符串比较；`index_dwd_window`、`stock_dwd_dws_window`、`market_state_dws` 与 `windowed_stock_refresh_checks` 统一透传 `warehouse_mode`。
- 真实 `qa_only` smoke 已成功：`ashare_warehouse_window_refresh` execution `aaad21db-7c1a-4cb2-92fb-55158edfa3a3`，`business_date=date_to=2026-06-05`、`warehouse_mode=qa_only`。
- 真实 `daily_current` smoke 已成功：父 workflow execution `2085f593-0fe9-483c-8888-6fa48fe7bb2f`，子 workflow execution `d305d8a3-99a1-4007-9fb2-94e3698ff55c`；child 内 `index_dwd_window`、`stock_dwd_dws_window`、`market_state_dws`、`core_smoke_checks`、`index_benchmark_checks`、`finance_caliber_checks`、`unit_contract_checks`、`pipeline_finalize_status`、`finish` 全部 success。

### 重要上下文

- 本轮验证的是 OQ-005 phase 1 foundation，不是生产 cutover。Composer 仍是生产调度入口；Workflows 现在只是并行存在且已证明主链路可跑通。
- 这次暴露的错误几乎都属于运行期接线/类型问题：`http timeout`、bool 判断、参数透传、锁兼容路径。`py_compile` 抓不到，后续做 `full_rebuild` / Scheduler / cutover 前仍应继续坚持“本地最小集成测试 + 真实 smoke”这套门。
- `ashare_warehouse_full_rebuild`、`ashare_pipeline_alert_checker`、Cloud Scheduler / IAM bootstrap 还没迁完；`backfill` 和非交易日 skip 的 Workflows smoke 也还没补。

### 改动文件

- `tests/pipeline_control/test_state_lock.py`
- `orchestration/workflows/ashare_ods_ingestion_daily.yaml`
- `orchestration/workflows/ashare_warehouse_window_refresh.yaml`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m unittest discover -s tests/pipeline_control -p 'test_state_lock.py'`
- `ashare_warehouse_window_refresh` `qa_only` execution `aaad21db-7c1a-4cb2-92fb-55158edfa3a3` succeeded
- `ashare_ods_ingestion_daily` `daily_current` execution `2085f593-0fe9-483c-8888-6fa48fe7bb2f` succeeded
- child `ashare_warehouse_window_refresh` execution `d305d8a3-99a1-4007-9fb2-94e3698ff55c` succeeded

### 阻塞项

- 无硬阻塞。

### 下一步建议

- 迁移 `ashare_warehouse_full_rebuild` 到 Workflows，并保持显式状态写回、同步终态轮询和锁语义。
- 迁移 `ashare_pipeline_alert_checker` 到 `Cloud Scheduler + Cloud Run`。
- 补 `backfill` 与非交易日 skip 的 Workflows smoke，再接入 Cloud Scheduler / IAM bootstrap，进入 shadow run 与最终 cutover。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: composer-exit-next-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: pr112-review-followup-20260608
相关 issue/PR: PR #112

### 已完成工作

- 修复 `ashare-pipeline-control` 镜像启动崩溃风险：`Dockerfile.pipeline_control` 现已打包 `scripts/alerting`，使 `service.py` 的 alert-check 模块级导入可在运行镜像中解析。
- 把 `ashare_warehouse_full_rebuild` 从标准 `deploy_workflows.sh` 路径移出，改成显式 `DEPLOY_FULL_REBUILD=true` 的 opt-in 部署。
- 更新 `orchestration/workflows/README.md`，明确 full rebuild 仍未 deployment-ready，且启用 `Cloud Scheduler` alert-check 时必须同步 pause / delete Composer DAG `ashare_pipeline_alert_checker`。

### 重要上下文

- 这轮是 review follow-up，没有新增部署或 smoke。
- full rebuild 现在虽然仍存在 workflow 文件，但默认部署脚本不会再把它注册到 GCP；这样“code-only”不再只是文档声明，而是代码层的真实约束。
- alert checker 双跑问题当前靠部署约束解决，不靠运行时去重。

### 改动文件

- `orchestration/workflows/Dockerfile.pipeline_control`
- `orchestration/workflows/deploy_workflows.sh`
- `orchestration/workflows/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未运行新的本地测试。
- 未部署新的 Cloud Run / Workflows / Cloud Scheduler。

### 阻塞项

- `ashare_warehouse_full_rebuild` 的核心阻塞不变：控制层 BigQuery 仍同步 `job.result()`，未解决前不应投入生产。

### 下一步建议

- 若继续收口 PR #112，优先看是否还需要把“pause Composer checker”写进实际 cutover runbook / deploy script 输出。
- 后续继续做 full rebuild 时，先实现 async submit + poll，或把 workflow 继续拆成可稳定落在 step 时限内的更小单元。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

**OQ-005 Composer DAG 拆分生产切换（2026-06-06）**：PR #86 已合并并完成 Composer 部署 / smoke。已应用 meta DDL 与观测视图，部署 `ashare_common.py`、`ashare_ods_ingestion_daily.py`、`ashare_warehouse_window_refresh.py`、`ashare_warehouse_full_rebuild.py` 和仓库 `sql/` 到 Composer bucket。旧 `ashare_daily_pipeline_v0` 已暂停，新 scheduled DAG `ashare_ods_ingestion_daily` 已 unpause；`ashare_warehouse_window_refresh` 与 `ashare_warehouse_full_rebuild` 无 schedule。`setup_alerts.py` 已补真实 GCP apply 兼容修复，`ashare_pipeline_warehouse_refresh_missing` metric 与 `Ashare Pipeline: Warehouse Refresh Missing` policy 已创建 / 对齐。Smoke：`manual_split_skip_gate_20260606_01` 非交易日 gate 成功且 Cloud Run 未触发；`manual_split_qa_only_20260605_01` 5 个 QA success；`manual_split_backfill_20260605_01` 1 日窗口刷新和全部 QA success；refresh-missing synthetic transaction smoke 通过；`check_alerts.py --lookback-minutes 20` 返回空。后续只剩新 DAG 至少两个开市日 scheduled run 和一个真实非交易日 scheduled skip 自然观察，以及 Dataform 生产接入 / shadow 验证、完整 ODS→ADS 运维观测闭环和后续自然 scheduled 观察。

**OQ-010 尾部风险 P0/P1/P2 当前版收口（2026-06-06）**：PR #84（`docs/prd/PRD_20260606_01_策略1尾部风险控制.md`）已合并，P0 固定最大回撤诊断已由 PR #87 实现并通过真实 `20` QA；P1 个股硬风险过滤 profile A/B 已完成，`individual_risk_guard_v0` 对回撤有轻度改善但仍跑输中证1000；P2 market risk-off 已由 PR #92 合并、物化 DWS 并完成 A/B。当前可复用的事实链路是 `tail_risk/` artifact、`20_qa_tail_risk_outputs.sql` 和 P1/P2 A/B 结果；当前不应把 P2 v0 `skip_new_buys` 设为默认策略。

**OQ-005 Composer DAG 拆分 PRD（2026-06-06）**：工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-dag-split-prd`，分支 `codex/oq005-dag-split-prd`。新增 `docs/prd/PRD_20260606_02_OQ005ComposerDAG拆分.md`，定义将当前 `ashare_daily_pipeline_v0` 拆成 `ashare_ods_ingestion_daily`、`ashare_warehouse_window_refresh`、`ashare_warehouse_full_rebuild`、`ashare_research_model_experiment`、`ashare_research_model_fanout`，`ashare_pipeline_alert_checker` 继续独立。本次只写 PRD 和记忆/TODO，不改 DAG、不部署 Composer、不运行 BigQuery / Dataform / Cloud Run。后续建议先实现 production DAG 拆分 Phase B/C/D：抽共享 helper，新增 ingestion daily DAG 与 warehouse window refresh DAG，完成开市日、非交易日和 backfill smoke 后再继续 Dataform 生产接入 / shadow 验证 / resume 自动化。

**OQ-010 PRD04 Wave 3 执行收口（2026-06-06）**：工作树 `/Users/luna/Desktop/git/quant-ashare-prd04-wave3`，分支 `codex/fix-prd04-prepare-matrix-parallelism`，PR #82。PR #79 合并后已部署 Cloud Run runner；本分支修复 `prepare_matrix()` requested parallelism 作用域 bug，并补 BigQuery JSON sanitizer，避免 regression `roc_auc/log_loss` 的 NaN 写入非法 `metrics_json`；PR #82 review follow-up 已补 `NaT` / `pd.NA` / `NaN` / `inf` 转 `null`、`np.ndarray` / pandas 标量递归转换和 `default=str` 兜底，并把状态表 `params_json`、GCS lock payload、work-unit manifest/hash 等 runner JSON 路径统一到 strict helper。最终镜像 `prd04-7d8daec-20260606-01` 已构建并部署到五个策略 Cloud Run Jobs。Wave 3 `cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01` 已完成：12 个 regression 候选、Top5 回测/报告/诊断和 `19` QA 全部通过，Top5 全部 rejected，当前仍不建立 `cloud_run_python_baseline_v1`。后续建议进入 PRD04 下一模型族 / 特征增强路线，或先分析回撤过大原因。

**OQ-005 非交易日 skip gate 已部署验收（2026-06-06）**：PR #83 已合并到 `main`（`3723f52`），`ashare_daily_pipeline_v0.py` 已同步到 Composer bucket `gs://asia-east2-ashare-composer-b2629133-bucket/dags/`，本地与 bucket SHA256 均为 `e4b07ba402716b914bfbd6fe27fa38f97fab8e1c12f6a0bcce9e5fd8c58696af`。`manual_smoke_skip_non_trading_day_pr83_20260606_02` 使用 `business_date=2026-06-06`、`warehouse_mode=daily_current`、`force_non_trading_day_gate=true`、`pipeline_dry_run=true` 成功：`non_trading_day_gate=success`、`skip_non_trading_day=success`，`pipeline_task_status` 写入 `skip_non_trading_day status='skipped'`，ingestion/readiness/transform 全部 skipped，Cloud Run 最新 execution 仍为 01:53 的旧 PR #80 run，未被 smoke 触发。DAG 当前 active/unpaused、无 import errors。首次 smoke `manual_smoke_skip_non_trading_day_pr83_20260606_01` 在 Composer 新旧 serialized DAG 切换窗口内走到旧路径，已中止、确认未触发 Cloud Run，并在 `pipeline_run` 标为 `partial` 防止假告警；`v_alert_summary` 对两次 smoke 为空。

**OQ-005 PR #83 记忆一致性 follow-up（2026-06-06）**：PR #83 review comment `4637354942` 指出 `IMPLEMENTATION_STATUS.md` 已完成区仍残留旧的部署等待状态。已将相关 durable bullet 改为“后续已由 PR #80/PR #83 部署与 smoke 覆盖”，并把几条历史补充明确标为部署前状态，避免同一记忆文件内当前状态自相矛盾。

## 交接条目

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: main-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: pr109_comment_followup_primary_benchmark_fields_20260608
相关 issue/PR: PR #109

### 已完成工作

- 处理 PR #109 的 P2 comment：补齐 live 搜索 acceptance 路径的 benchmark 输出字段命名。
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py` 不再输出 `test_year_excess_return_vs_000852`、`overall_excess_return_vs_000852`、`final_holdout_excess_return_vs_000852`，统一改为 `*_vs_primary_benchmark`。
- `scripts/strategy1_cloudrun/acceptance.py` 读取时优先使用新字段名，并兼容回退旧字段名与通用字段，保持阈值键 `*_vs_000852` 暂不重命名的兼容策略。

### 重要上下文

- 本次只修正 live 搜索 acceptance 的输出字段名，不改阈值键名，不改 benchmark 数值逻辑。
- 目的不是改计算口径，而是避免 benchmark 已切到 `000001.SH` 后，registry / comparison artifact 继续写 `*_vs_000852` 的误导命名。
- v2 diagnosis 路径和 live 搜索 acceptance 路径现在都统一到 `*_vs_primary_benchmark` 输出命名。

### 改动文件

- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1_cloudrun/acceptance.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未运行新的 Cloud Run / BigQuery replay。
- 本次是 PR comment follow-up 的命名一致性修复，未改数值计算逻辑。

### 阻塞项

- 无。

### 下一步建议

- 把本次 follow-up 追加到 PR #109。
- 如果后续要彻底清理 benchmark 历史命名债，再单独重构 contract / QA 内部阈值键 `*_vs_000852`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 交接条目

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: main-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: strategy1-benchmark-replay-000001-20260608
相关 issue/PR: N/A

### 已完成工作

- 在默认 benchmark 已切到 `000001.SH` 的前提下，完成不覆盖旧审计结果的 fixed-prediction lot-aware replay：
  `run_id=s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01`
  `backtest_id=bt_s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01`
  `prediction_run_id=s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01`
- 已重新生成并上传新 replay 的 report、model diagnosis、tail-risk 和 acceptance gate v2 artifact。
- 已手工补跑 `10`、`12`、`20`、`22`、`23` QA，均通过。
- 新 acceptance artifact `acceptance_gate_v2_lotaware_ref_bm000001_20260608_01` 已上传，状态为 `rejected`。

### 重要上下文

- 旧 `000852.SH` 口径 historical summary / report / diagnosis / gate artifact 保留不动，继续作为审计对照。
- 这次 replay 复用的 source prediction stream 没有独立 `final_holdout` split_tag，所以 `10_qa_runner_outputs.sql` 必须按 fixed-prediction override 跑：
  `p_test_end=2026-04-30`
  `p_final_holdout_start=NULL`
  `p_final_holdout_end=NULL`
- acceptance gate v2 仍按 replay NAV 的时间窗计算 final holdout；override 只用于 runner QA 的 split_tag 一致性。
- 新 gate 的拒绝原因是：
  `full_period_excess_return_vs_primary_benchmark<=-0.03`
  `full_period_information_ratio<0.0`

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m scripts.strategy1_cloudrun.backtest_report --experiment-json ...`
- `python3 scripts/strategy1/diagnose_model_quality.py --project data-aquarium --run-id s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01 --prediction-run-id s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01 --backtest-id bt_s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01 --artifact-base-uri gs://ashare-artifacts/reports/strategy1 --local-mirror-root reports/strategy1`
- `python3 scripts/strategy1/analyze_tail_risk.py --project data-aquarium --run-id s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01 --prediction-run-id s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01 --backtest-id bt_s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01 --artifact-base-uri gs://ashare-artifacts/reports/strategy1 --local-mirror-root reports/strategy1`
- `python3 scripts/strategy1/diagnose_acceptance_gate_v2.py --project data-aquarium --diagnosis-id acceptance_gate_v2_lotaware_ref_bm000001_20260608_01 --reference-run-id s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01 --reference-backtest-id bt_s1_lotaware_ref_pvfq_n30_bw_h5_bm000001_20260608_01 --prediction-run-id s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01 --contract configs/strategy1/model_acceptance_contract_v2.yml --feature-version strategy1_pv_fin_quality_v0_20260603 --label-version open_to_close_h1_5_10_20_v20260601 --horizon 5 --full-start-date 2024-01-02 --full-end-date 2026-04-30 --valid-start-date 2024-01-02 --valid-end-date 2024-12-31 --test-start-date 2025-01-02 --test-end-date 2025-12-31 --final-holdout-start-date 2026-01-05 --final-holdout-end-date 2026-04-30 --artifact-base-uri gs://ashare-artifacts/reports/strategy1 --local-mirror-root reports/strategy1`
- 通过 `scripts.strategy1_cloudrun.sql_runner.run_sql_script` 手工执行：
  `sql/ml/strategy1/10_qa_runner_outputs.sql`
  `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`
  `sql/ml/strategy1/20_qa_tail_risk_outputs.sql`
  `sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`
  `sql/ml/strategy1/23_qa_lot_aware_ledger_outputs.sql`

### 阻塞项

- 无硬阻塞。

### 下一步建议

- 若 owner 要把 `000001.SH` 口径作为后续统一对外口径，可继续补 v1/v2 契约和 QA 内部历史 `*_vs_000852` 阈值键名的 benchmark-neutral 重命名。
- 若要继续 OQ-010 训练 / 搜索，后续相对 benchmark 的新结论应统一引用这次 `000001.SH` replay，而不是混用旧 `000852.SH` audit。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

**OQ-010 PRD04 Cloud Run Python baseline search 实现（2026-06-06）**：PR #79 review follow-up、PR #82 runtime 修复和真实 wave 2 / wave 3 执行均已完成。真实 LightGBM binary wave 2 `cloudrun_python_lgbm_pvfq_n30_bw_h5_20260605_01` 与 regression wave 3 `cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01` 均完成 Top5 回测/报告/诊断和 QA，Top5 全部 rejected，当前不建立 `cloud_run_python_baseline_v1`。运行资源口径为 40 候选 / 20 并发 / 2 vCPU 8Gi；后续建议进入下一模型族、特征增强或训练目标改造，而不是继续围绕已拒绝的两波 LightGBM 搜索。

**项目记忆瘦身归档（2026-06-05）**：`AGENT_HANDOFF.md` 已按 owner 要求整理，当前文件只保留启动摘要、归档清理交接和最近 3 条交接；较早的 30 条交接已追加到 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。常规启动优先读本文件；需要审计历史时再读 archive。

**OQ-005 PR #80 部署与 2026-06-05 smoke（2026-06-06）**：当前 `main` 已包含 PR #80，并已完成生产部署：`ashare_daily_pipeline_v0.py` 同步到 Composer `dags/`，仓库 `sql/` 同步到 `gs://asia-east2-ashare-composer-b2629133-bucket/data/sql/`，本地 / bucket DAG 与 `09_ods_daily_partition_readiness.sql` SHA256 一致。`manual_pr80_daily_current_20260605_20260606_01` 使用 `business_date=2026-06-05` 成功完成 current_scope 采集、ODS readiness、窗口 DIM/DWD/DWS 刷新和窗口 QA；采集后 2026-06-05 strong endpoint 行数为 daily 5514、daily_basic 5514、adj_factor 5526、stk_limit 7634、index_daily 7。`manual_pr80_qa_only_20260605_20260606_01` 使用 `skip_ingestion=true` 成功完成 readiness + P0 / strategy1 / OQ004 / finance / OQ006 五个只读 QA。最近 20 个交易日 `2026-05-11..2026-06-05` ODS daily_basic → DWD valuation → DWS valuation 行数均为 110,035，错配天数 0。下一步仍是 Dataform 生产链路、完整 ODS→ADS 运维观测闭环和新 DAG 自然 scheduled 观察；非交易日自动 skip gate 已由 PR #83 合并部署，并通过 `manual_smoke_skip_non_trading_day_pr83_20260606_02` 验收。

**OQ-010 Cloud Run Python baseline 搜索 PRD（2026-06-05）**：工作树 `/Users/luna/Desktop/git/quant-ashare-cloudrun-python-baseline-search`，分支 `codex/prd-cloudrun-python-baseline-search`。新增 `docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`：本轮数据截止 `2026-04-30`；train/valid/test/final_holdout 为 `2019-04-03..2023-12-31` / 2024 / 2025 / `2026-01-05..2026-04-30`；固定 `pv_fin_quality + 30/5% + biweekly + 5d`、沪深主板股票池、成本 profile 和 Ledger v1；P0 推荐 LightGBM wave 2。PR #78 review follow-up 后，候选排序改为 2021/2022/2023 三折 purged walk-forward CV + 2024 valid confirmation，2025 test 做硬接受门，2026 final_holdout 只做明显坏结果 veto / holdout watch；实现 smoke 后当前资源口径已从最初 40 并发 / 1 vCPU 4Gi 调整为 40 候选 / 20 并发 / 2 vCPU 8Gi；若 binary LightGBM rejected，后续优先试 `lightgbm_regression`。

**OQ-005 告警/观测生产闭环部署与 PR #75 follow-up（2026-06-05）**：PR #75 已合并并完成生产部署；后续代码收敛工作树 `/private/tmp/oq005-alerting-deploy-followup`，分支 `codex/oq005-alerting-deploy-followup`。已完成：8 个 BigQuery 观测视图创建、旧线上名 `oq005_pipeline_failure` / `oq005_task_failure` / `oq005_ingestion_failed` log-based metrics 创建、3 个 `OQ-005: ...` Cloud Monitoring alert policies 启用（Ingestion severity 已从 CRITICAL 修正为 WARNING）、Email 通知渠道配置并关联到告警策略、定时 checker DAG `oq005_alert_checker` 部署（每 10 分钟）、三类告警 smoke 验证（pipeline_failure / task_failure / ingestion_failed 均在 timeSeries 中 value=1）。PR #75 follow-up 已部署并验收：Composer bucket 已同步旧 checker DAG 与 `check_alerts.py`；新增旧线上名 `oq005_alert_checker_heartbeat` log-based metric 和 `OQ-005: Alert Checker Heartbeat Missing` 30 分钟 absence policy，策略已启用并绑定 1 个 Email 通知渠道；`check_alerts.py` 显式使用 `resource.type=global` 写业务告警与 heartbeat，避免 Composer 默认 `k8s_container` resource 与现有告警策略不匹配。PR #77 review follow-up 已修复告警策略幂等键：`setup_alerts.py` 使用稳定 `user_labels.oq005_policy` 并兼容旧 display name 迁移，避免旧名环境重复创建新旧两份策略。manual smoke `manual_oq005_alert_checker_heartbeat_global_20260605_01` 成功，随后的 scheduled run 也成功；Cloud Logging 中 heartbeat 为 `resource.type=global`、`lookback_minutes=20`、`alerts_count=0`，Cloud Monitoring global timeSeries 已有点。PR #91 的 `ashare_pipeline_*` 是后续 cutover 目标名。下一步：继续 Dataform definitions、补跑和完整 ODS→ADS 运维观测闭环。

**OQ-005 告警/观测 PR #72 review follow-up（2026-06-05）**：工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-alerts-runbook`，分支 `codex/oq005-alerts-runbook`。PR #72 新增 BigQuery 观测视图、Cloud Logging / Cloud Monitoring 告警配置脚本、告警查询脚本和补跑 runbook。本轮按 comment 修复：`setup_alerts.py` 的 `LogMetric` 使用正确 `filter` 字段；`check_alerts.py` 查询失败和缺 `google-cloud-logging` 写日志路径均 fail-closed，默认 lookback 改 10 分钟并用稳定 `insert_id` 降低重复日志；runbook §9 的 `task_failure` / `ingestion_failed` 与 SQL 实现一致；`v_alert_probe` 注释改为固定 24 小时手工健康检查口径。验证通过 Python `py_compile`、观测 SQL BigQuery dry-run、`git diff --check`；本机缺 `google-cloud-logging`，未做真实 log metric API apply。合并后仍需部署视图、配置 Cloud Scheduler/Cloud Run checker、log-based metrics、alert policies，并做生产 smoke。

**OQ-010 当前路线（2026-06-05）**：owner 已决定后续不再使用 BQML 或 `sql/ml/strategy1` SQL runner 作为策略训练、预测、回测、报告、诊断、月度滚动重训或多实验搜索的默认 / fallback / 新增开发路线；该决策已写入 `DECISION-20260605-03`。历史 BQML 最优组合 `pv_fin_quality + 30/5% + biweekly + 5d` 仅作 reference / audit。PR #76 follow-up 已在 `docs/prd/PRD_20260604_02_策略1月度滚动重训.md` 文首补 superseded banner；正文仍待后续改造成 Cloud Run Python / backend-neutral prediction stream。下一步应寻找可接受的 Cloud Run Python 模型 / backend baseline。

**OQ-010 已收口事实（2026-06-05）**：Ledger v1 P1 extended fresh run `s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` 覆盖 `2024-01-02` 至 `2026-04-30`，total_return 35.16%、excess_return -7.22% vs `000852.SH`；P2 resume run `s1_bqml_baseline_pvfq_n30_bw_h5_resume_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_resume_20260604_01` 通过 `sql/ml/strategy1/15_qa_ledger_resume_consistency.sql`。sklearn native search 首轮 `sklearn_native_pvfq_n30_bw_h5_20260605_01` 已完成，Top5 均因 `test_year_excess_return<=0.0` 被拒绝，本轮不建立 `cloud_run_sklearn_native_baseline_v1`。

**OQ-005 / OQ-012 当前状态（2026-06-06）**：OQ-005 已完成 current-scope 生产采集至 `2026-06-05`、Composer DAG/SQL 部署验收、20 日窗口 DWD/DWS smoke、readiness 门禁复核、告警/观测与 alert checker heartbeat；scheduled 非交易日 skip gate 已由 PR #83 合并部署并完成 force hook smoke。OQ-005 仍 open，剩余 Dataform 生产链路、完整 ODS→ADS 运维观测闭环和新 DAG 自然 scheduled 观察。OQ-012 当前 BigQuery 读层 `sql/qa/06_ods_parquet_schema_checks.sql` 对 P0 与 all 范围均通过，待 owner 决定关闭/归档或保留 schema contract / ingestion 显式 cast 防复发任务。

**常规约定**：评审默认写 GitHub PR comment；TODO 只保留下一步可执行事项，待 owner 决策问题以 `OPEN_QUESTIONS.md` 为唯一来源。PR 合并后，若 owner 未要求保留工作分支，应删除已合并且不再使用的 `codex/*` 本地分支、对应远端分支，并移除为该分支创建的独立 `git worktree`；若 worktree 仍有未提交或未合并改动，先暂停并请 owner 决策，不得强删。

> 历史交接已归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-05.md` 和 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。常规启动只需阅读本文件的当前摘要和最近交接；归档仅用于审计追溯。

---

---

## 交接条目

日期: 2026-06-07
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: index_000001_warehouse_backfill_20260607
相关 issue/PR: 待创建 PR

### 已完成工作

- 新增 `sql/ods/01_index_external_table_uris.sql`，用 `CREATE OR REPLACE EXTERNAL TABLE` 维护 `ods_tushare_index_daily` / `ods_tushare_index_dailybasic` 的显式 source URI 列表，并补入 `000001.SH` 两个 endpoint。
- `configs/ingestion/ods_current_scope_v0.yml` 已补 `index_daily_000001_SH` 和 `index_dailybasic_000001_SH` request variants。
- `sql/dim/04_dim_index.sql` 已加入上证指数 `SSE_COMPOSITE` seed。
- 新增 `sql/incremental/02_refresh_index_dwd_window.sql` 与 `sql/qa/12_windowed_index_refresh_checks.sql`，并接入 `orchestration/composer/dags/ashare_common.py` 的 setup / windowed transform 链路。
- 同步 `dataform/action_manifest.json` 和生成的 SQLX 文件。
- `sql/qa/03_index_benchmark_checks.sql`、`sql/qa/08_ods_external_readability_checks.sql`、`sql/qa/01_core_smoke_checks.sql` 已补 `000001.SH` 相关检查。

### 重要上下文

- ODS index external tables 当前使用显式 `sourceUris`，不是自动发现所有 `endpoint=*`。GCS 写入成功后，如果不更新 external table URI，BigQuery ODS 仍读不到新 endpoint。
- `000001.SH` 两个 endpoint 在 BigQuery ODS 中均已确认有 1,799 个 2019+ SSE 开市日分区 / 行。
- 为保持既有训练结果可复现，本次没有修改 `dws_market_state_daily` 或 `market_state_v0_20260606`，也没有写 ADS。后续如要把上证指数纳入训练市场状态，应新建 market-state 版本或新 feature set。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`
- `configs/ingestion/ods_current_scope_v0.yml`
- `dataform/action_manifest.json`
- `dataform/definitions/**`
- `docs/Pipeline-补跑与故障恢复-Runbook.md`
- `orchestration/composer/dags/ashare_common.py`
- `sql/dim/04_dim_index.sql`
- `sql/incremental/02_refresh_index_dwd_window.sql`
- `sql/ods/01_index_external_table_uris.sql`
- `sql/qa/01_core_smoke_checks.sql`
- `sql/qa/03_index_benchmark_checks.sql`
- `sql/qa/08_ods_external_readability_checks.sql`
- `sql/qa/12_windowed_index_refresh_checks.sql`

### 测试 / 验证

- `python3 scripts/dataform/generate_sqlx_from_sql.py`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/ods/01_index_external_table_uris.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dim/04_dim_index.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dwd/04_dwd_index_eod.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/03_index_benchmark_checks.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/05_unit_contract_checks.sql`
- `sql/incremental/02_refresh_index_dwd_window.sql` 使用 `warehouse_mode=backfill`、`date_from=2019-01-01`、`date_to=2026-06-05` 实跑，删除并重插 13,770 行，其中 `000001.SH` 1,799 行。
- `sql/qa/12_windowed_index_refresh_checks.sql` 同窗口通过。
- 复跑 `sql/qa/03_index_benchmark_checks.sql` 通过。

### 阻塞项

- 无。

### 下一步建议

- 提 PR 后合并并同步 `sql/` 与 Composer DAG 到 Composer bucket。
- 合并部署后触发一次 `ashare_warehouse_window_refresh` 小窗口 backfill 或等待下一次 scheduled ingestion 触发，确认 Airflow task 链路中的 `index_dwd_window` 与 `windowed_index_refresh_checks` 成功。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

---

日期: 2026-06-07
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_risk_feature_pr102_review_followup_20260607
相关 issue/PR: PR #102

### 已完成工作

- 按 PR #102 comment 修复风险特征实现的两个 review 点。
- 将风险专项最大回撤目标接入共享 acceptance contract：`model_acceptance_contract_v1.yml` 显式加入 `min_full_period_max_drawdown: -0.18`，`acceptance.py` 新增 `full_period_max_drawdown_threshold()` / `risk_feature_max_drawdown_target()`，`contract_sql_params()` 输出 `p_risk_feature_max_drawdown_target`。
- `21_qa_risk_feature_search_outputs.sql` 的 `p_risk_feature_max_drawdown_target` 默认改为 `NULL`，并新增 `QA-RISK-0`，防止 standalone 真执行时静默使用硬编码阈值。
- 将 `derive_final_holdout_status()` 从 orchestrator 移入共享 `acceptance.py`，orchestrator 删除本地重复函数并调用共享规则。

### 重要上下文

- 本次只修 PR #102 review follow-up，不执行真实 Cloud Run 训练，不更新 ADS，不建立 baseline。
- v1 contract hash 因新增阈值字段发生变化；这是预期结果，用于让风险专项阈值进入契约审计链。
- 合并后仍需构建/部署 runner 镜像，再执行 binary 20 与 regression 20 候选训练、Top5 回测和 `19` + `21` QA。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`
- `configs/strategy1/model_acceptance_contract_v1.yml`
- `scripts/strategy1_cloudrun/acceptance.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/acceptance.py scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- v1 contract hash / `p_min_full_period_max_drawdown` / `p_risk_feature_max_drawdown_target` 参数确认。
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`
- 使用 `contract_sql_params()` 渲染后的 `21_qa_risk_feature_search_outputs.sql` BigQuery dry-run。
- risk feature orchestrator `--build-training-panel --dry-run`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- PR #102 合并后构建/部署 runner 镜像。
- 执行 binary risk feature search，再执行 regression risk feature search。
- Top5 回测后以共享 `19` QA 和风险专项 `21` QA 收口，并按结果判断是否 accepted / needs_more_evidence / rejected。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

---

日期: 2026-06-07
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_risk_feature_search_implementation_20260607
相关 issue/PR: 待创建 PR

---

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: oq005_exit_composer_prd_20260608
相关 issue/PR: 待创建 PR

### 已完成工作

- 新增 `docs/prd/PRD_20260608_01_OQ005调度完全迁出Composer.md`，将 OQ-005 的长期编排方向从“长期保留 Composer”调整为“迁出 Composer 后删除环境”。
- PRD 明确推荐架构为 `Cloud Scheduler + Cloud Workflows + Cloud Run Jobs + BigQuery SQL/Dataform`，并将 `ashare_pipeline_alert_checker` 迁到 `Cloud Scheduler + Cloud Run`。
- 已同步更新 `PROJECT_CONTEXT.md`、`ARCHITECTURE_MEMORY.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`TODO.md`，把当前 Composer DAG 拆分、window refresh、alert checker 与 smoke 统一标注为 cutover 前过渡态。
- 已按 PR #108 comment follow-up 补强 PRD：把 per-task 状态写回、显式分布式锁、同步 child workflow / 退役 refresh-missing watchdog、BigQuery/Cloud Run 轮询模型和 Workflows 限额复核写成实现硬要求。

### 重要上下文

- 当前 Composer 费用问题的核心不是 DAG 次数，而是常驻 `Cloud Composer 3 standard milli DCU-hours` 底座费；迁移完成前，减少 DAG 次数本身不能显著降本。
- 本次只写 PRD 和记忆/TODO，不改现有 DAG、Cloud Run、BigQuery SQL 或告警实现。
- PRD 默认路径不要求 owner 额外拍板：多步编排使用 Workflows，单步 alert checker 直接走 Scheduler + Cloud Run。
- PR #108 review 已指出 4 个 Airflow -> Workflows 容易静默回退的点；这些已全部在 PRD 中转成硬要求，不再留到实现时自由发挥。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `TODO.md`
- `docs/prd/PRD_20260608_01_OQ005调度完全迁出Composer.md`

### 测试 / 验证

- 本次未运行 BigQuery / Cloud Run / Composer 验证。
- 仅完成文档与记忆同步。

### 阻塞项

- 无当前阻塞；下一阶段才需要实现 Workflows/Scheduler 基础设施和 cutover smoke。

### 下一步建议

- 新开实现分支，先落 Workflows/Scheduler 基础设施。
- 保持现有 SQL、metadata、QA 和 alert checker 语义不变，优先做无语义漂移迁移。
- 完成 `qa_only` / `daily_current` / `backfill` / 非交易日 skip 手工 smoke 后，再安排 scheduled cutover。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `TODO.md`

### 已完成工作

- 在工作树 `/Users/luna/Desktop/git/quant-ashare-risk-feature-impl`、分支 `codex/implement-risk-feature-search` 实现 PRD `docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md` 的风险特征第 4 波训练路径。
- 新增 `scripts/strategy1_cloudrun/feature_sets.py`，固化 `strategy1_pv_fin_risk_v0_20260606` 95 列特征契约，覆盖 `pv_fin_quality` 基础特征、个股风险、市场状态和风险交互项。
- `prepare_matrix.py` 增加 feature set 契约校验，输出 `feature_delta_vs_base.json`、feature schema hash、风险/市场特征列表和 split missing-rate。
- `train_candidate_task.py` 输出 LightGBM / sklearn-like feature importance，聚合到 feature group，并记录 `risk_feature_importance_gain_share`、`market_state_importance_gain_share`。
- `select_register_predict.py` 将 feature schema/delta hash、feature count、risk feature count 和 market-state feature count 写入 registry metrics。
- `orchestrate_sklearn_native_search.py` 支持 config 指定训练面板 SQL，风险特征 search 自动追加 `21` QA，并增加 final_holdout passed 派生与 `max_drawdown >= -18%` 风险专项 overlay。
- 新增 Cloud Run 专用训练面板 SQL `sql/cloudrun/strategy1/01_build_training_panel.sql`，按 PRD 写入个股风险、市场状态和交互特征。
- 新增 binary/regression 各 20 候选 manifest，以及 `sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`。

### 重要上下文

- 本次只完成实现和 dry-run 验证，未执行真实 Cloud Run 40 候选训练，未跑 Top5 回测，未建立 baseline。
- 两个 manifest 分别是 `configs/strategy1/cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_v0.yml` 和 `configs/strategy1/cloudrun_python_riskfeat_lgbm_regression_pvfq_n30_bw_h5_v0.yml`，均为 20 候选 / 20 并发 / 2 vCPU / 8Gi / wave 4 / `test_reuse_wave_no=4`。
- 合并后下一步应先构建/部署 runner 镜像，再依次跑 binary 20 与 regression 20；Top5 完整回测后必须跑共享 `19` QA 和风险特征 `21` QA。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`
- `configs/strategy1/cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_v0.yml`
- `configs/strategy1/cloudrun_python_riskfeat_lgbm_regression_pvfq_n30_bw_h5_v0.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/feature_sets.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1_cloudrun/prepare_matrix.py`
- `scripts/strategy1_cloudrun/select_register_predict.py`
- `scripts/strategy1_cloudrun/train_candidate_task.py`
- `sql/cloudrun/strategy1/01_build_training_panel.sql`
- `sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`
- `sql/ml/strategy1/README.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1_cloudrun/feature_sets.py scripts/strategy1_cloudrun/prepare_matrix.py scripts/strategy1_cloudrun/train_candidate_task.py scripts/strategy1_cloudrun/select_register_predict.py scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- manifest parse 校验：两个 riskfeat manifest 均为 20 候选、20 并发、2 vCPU / 8Gi、wave 4、风险特征集。
- `python3 -m scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search ... --build-training-panel --dry-run`，binary 和 regression 两个 manifest 均通过。
- `python3 -m scripts.strategy1_cloudrun.prepare_matrix ... --dry-run`，binary 和 regression 两个 manifest 均通过。
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/cloudrun/strategy1/01_build_training_panel.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`
- SQL/Python feature_column_list 95 列顺序一致性检查通过。
- `git diff --check`

### 阻塞项

- 无。真实训练需要合并后构建/部署 Cloud Run 镜像，并消耗 Cloud Run / BigQuery / GCS 资源。

### 下一步建议

- 创建并合并实现 PR。
- 合并后构建/部署 runner 镜像。
- 先跑 `cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_20260606_01`，再跑 `cloudrun_python_riskfeat_lgbm_reg_pvfq_n30_bw_h5_20260606_01`。
- 汇总 40 个候选和 Top5 回测结果，以 `19` + `21` QA 作为验收门。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

日期: 2026-06-07
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_lotaware_reference_execution_20260607
相关 issue/PR: PR #100, PR #101

### 已完成工作

- 合并 PR #101 `fix(strategy1): pass prediction source to portfolio reports`，清理远端/本地分支 `codex/fix-portfolio-only-report-source-run` 和工作树 `/Users/luna/Desktop/git/quant-ashare-lotaware-runner-fix`。
- 构建并部署 runner 镜像 `lotaware-c018ef5-20260607-01` 到 `strategy1-backtest-report-job`。
- 执行 fixed-prediction lot-aware reference：`s1_lotaware_ref_pvfq_n30_bw_h5_20260606_01` / `bt_s1_lotaware_ref_pvfq_n30_bw_h5_20260606_01`，复用 prediction run `s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01`，窗口 `2024-01-02..2026-04-30`，Cloud Run execution `strategy1-backtest-report-job-h7vtl` 成功。
- 生成并上传 report、model diagnosis、tail-risk artifact 和 acceptance gate v2 artifact `acceptance_gate_v2_lotaware_ref_20260607_01`。

### 结果

- lot-aware reference：total_return 35.17%、excess_return -7.20pct vs `000852.SH`、Sharpe 0.872、max_drawdown -13.59%、ledger_version `ledger_exec_v1_lot100`。
- 行数：prediction 1,247,888；candidate 132,909；target 1,800；order 962；trade 2,276；position 16,749；NAV 562。
- 成交状态：BUY filled 601 笔、BUY below-lot skipped 1,034 笔；SELL filled 467 笔、SELL below-lot partial skipped 160 笔、pending sell carry 8 笔。
- acceptance gate v2：`rejected`；拒绝原因是全期跑输中证1000超过 3pct、IR 为负、2026 final_holdout 跑输中证1000 12.75pct。

### 验证

- Cloud Run 内部：`10_qa_runner_outputs.sql`、`12_qa_model_diagnosis_outputs.sql`、`20_qa_tail_risk_outputs.sql` 通过。
- 手工复核：`22_qa_acceptance_gate_v2_outputs.sql` job `5a90c3d6-8d46-469a-b096-c92c5e7a7d55` 通过；`23_qa_lot_aware_ledger_outputs.sql` job `11ad8837-5e56-46c2-adbe-d275b919036f` 通过。

### 后续

- lot-aware 交易语义收口已完成；下一步可继续 `docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md` 的风险特征 / 下一模型族训练路线。

日期: 2026-06-07
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_lotaware_source_run_fix_20260607
相关 issue/PR: 待创建 PR

### 已完成工作

- 预检 fixed-prediction lot-aware reference 输入：源 prediction run `s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` 在 `2024-01-02` 至 `2026-04-30` 有 1,247,888 行预测；目标 `s1_lotaware_ref_pvfq_n30_bw_h5_20260606_01` / `bt_s1_lotaware_ref_pvfq_n30_bw_h5_20260606_01` 无 candidate / portfolio / order / trade / NAV 残留。
- 确认源模型 registry 为 `bqml_logistic_reg`、`feature_set_id=strategy1_pv_fin_quality_v0_20260603`、`target_holdings=30`、`rebalance_frequency=biweekly`。
- 修复 portfolio-only / lot-aware 报告和诊断的 source-run 口径：`render_report.py` 支持 `--prediction-run-id`，`backtest_report.py` 向 report / diagnosis 同时传新回测 run 与源预测 run。

### 验证

- `python3 -m py_compile scripts/strategy1/render_report.py scripts/strategy1_cloudrun/backtest_report.py`
- `python3 -m scripts.strategy1_cloudrun.backtest_report ... --experiment-json <lotaware_ref> --force-replace --dry-run`
- `git diff --check`

### 后续

- 创建并合并该修复 PR。
- 合并后构建/部署新 Cloud Run runner 镜像，执行 lot-aware reference，并运行 `23_qa_lot_aware_ledger_outputs.sql` 与 acceptance gate v2。

日期: 2026-06-07
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_lot_aware_ledger_merge_20260607
相关 issue/PR: PR #100

### 已完成工作

- 合并 PR #100 `feat(strategy1): implement lot-aware ledger` 到 `main`，merge commit 为 `4a1657d`。
- 本地 `main` 已 `git pull --ff-only origin main` 同步到 merge commit。
- 删除远端分支 `codex/implement-lot-aware-ledger`。
- 移除实现工作树 `/Users/luna/Desktop/git/quant-ashare-lot-aware-ledger-impl`。
- 删除本地分支 `codex/implement-lot-aware-ledger`。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要，明确 PR #100 已合并但 fixed-prediction lot-aware reference 尚未执行。

### 重要上下文

- `ledger_exec_v1_lot100` 代码、`sql/ml/strategy1/23_qa_lot_aware_ledger_outputs.sql`、golden-case 单测、report / summary / acceptance gate v2 对齐和运行手册已进入 `main`。
- PR #100 合并不等于策略 reference 已重跑；尚未部署 Cloud Run 镜像，也尚未执行 `2024-01-02` 至 `2026-04-30` 的 fixed-prediction lot-aware reference。
- 下一步策略训练 / 风险特征工作前，应先部署 runner 镜像，跑 lot-aware reference，执行 `23` QA 和 acceptance gate v2。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

### 测试 / 验证

- `gh pr view 100 --json state,mergedAt,mergeCommit,url,headRefName`
- `git pull --ff-only origin main`
- `git push origin --delete codex/implement-lot-aware-ledger`
- `git worktree remove /Users/luna/Desktop/git/quant-ashare-lot-aware-ledger-impl`
- `git branch -d codex/implement-lot-aware-ledger`

### 阻塞项

- 无。

### 下一步建议

- 构建并部署包含 PR #100 的 Cloud Run runner 镜像。
- 复用当前 prediction stream 跑 `2024-01-02` 至 `2026-04-30` fixed-prediction lot-aware reference。
- 执行 `23_qa_lot_aware_ledger_outputs.sql`、报告/诊断和 acceptance gate v2。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_lot_aware_ledger_implementation_20260606
相关 issue/PR: PR #99 / 待创建实现 PR

### 已完成工作

- 新建实现工作树 `/Users/luna/Desktop/git/quant-ashare-lot-aware-ledger-impl` 与分支 `codex/implement-lot-aware-ledger`。
- 将 Cloud Run Python 默认回测路径切到 `ledger_exec_v1_lot100` / `cloud_run_sklearn_ledger_v1_lot100`；保留显式 `--use-float-ledger` 与 `--use-bq-ledger` 作为 legacy / audit 路径。
- 在 `scripts/strategy1_cloudrun/ledger.py` 实现 lot-aware 执行：买入按 100 股整数手向下取整、below-lot 跳单、现金缩放后低于 1 手跳单、现金仍不足时按 rank 优先级回退低优先级买单、清仓 odd-lot 全额卖出、部分卖出向下取整到 100 股并保留残股、未成交 full-exit pending sell 继续重试。
- 在 `scripts/strategy1_cloudrun/backtest_report.py` 注入 `p_ledger_version` / `p_lot_size` / `p_min_buy_lot`，默认在 lot100 路径追加执行 `sql/ml/strategy1/23_qa_lot_aware_ledger_outputs.sql`。
- 扩展 `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`、`10_qa_runner_outputs.sql`、`16_qa_cloudrun_runner_outputs.sql`、`22_qa_acceptance_gate_v2_outputs.sql` 和 `configs/strategy1/model_acceptance_contract_v2.yml`，让 summary、runner QA 和 v2 acceptance gate 都能识别并要求 lot-aware ledger。
- 扩展 `scripts/strategy1/render_report.py`，在中文报告中展示 ledger version、整数手参数、跳单状态、odd-lot 清仓和现金权重。
- 新增 `sql/ml/strategy1/23_qa_lot_aware_ledger_outputs.sql`，验证 BUY filled shares 为 100 股整数倍、skipped 零成交、odd-lot 只出现在清仓 SELL、部分卖出 below-lot 后仍保留持仓、现金/暴露/持仓唯一性等。
- 新增 `tests/strategy1_cloudrun/test_lot_aware_ledger.py` golden-case 单元测试，覆盖买入取整、低于 1 手跳单、现金缩放后低于 1 手、现金回退、odd-lot 清仓、partial sell 残股保留和 pending sell 重试。
- 更新 `sql/README.md`、`sql/ml/strategy1/README.md` 和 `docs/策略1CloudRun训练回测运行手册.md`。

### 重要上下文

- 本 PR 只完成代码、QA 和文档实现；尚未部署 Cloud Run 镜像，尚未执行 `2024-01-02` 至 `2026-04-30` 的 fixed-prediction lot-aware reference。
- 后续 production acceptance 不得使用 FLOAT-shares backtest；需要先跑 lot-aware reference、执行 `23` QA，并重跑 acceptance gate v2。
- 余股的来源是历史买入 / 现金缩放 / corporate action 或历史 FLOAT position 等造成的非 100 股整数持仓；lot100 P0 允许清仓 odd-lot，但 partial sell 不卖碎股。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`
- `configs/strategy1/cloudrun_runner_default.yml`
- `configs/strategy1/model_acceptance_contract_v2.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1/diagnose_acceptance_gate_v2.py`
- `scripts/strategy1/render_report.py`
- `scripts/strategy1_cloudrun/__init__.py`
- `scripts/strategy1_cloudrun/acceptance.py`
- `scripts/strategy1_cloudrun/backtest_report.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/ledger.py`
- `sql/README.md`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`
- `sql/ml/strategy1/23_qa_lot_aware_ledger_outputs.sql`
- `sql/ml/strategy1/README.md`
- `tests/strategy1_cloudrun/test_lot_aware_ledger.py`

### 测试 / 验证

- `python3 -m unittest tests/strategy1_cloudrun/test_lot_aware_ledger.py`
- `python3 -m py_compile scripts/strategy1_cloudrun/ledger.py scripts/strategy1_cloudrun/backtest_report.py scripts/strategy1/render_report.py scripts/strategy1/diagnose_acceptance_gate_v2.py scripts/strategy1_cloudrun/acceptance.py scripts/strategy1_cloudrun/config.py scripts/strategy1_cloudrun/__init__.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/23_qa_lot_aware_ledger_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`
- `python3 -m scripts.strategy1_cloudrun.backtest_report --project data-aquarium --region asia-east2 --experiment-id oq010_a0_n5_w20 --dry-run`

### 阻塞项

- 无代码阻塞；真实 reference / Cloud Run 部署留待 PR 合并后执行。

### 下一步建议

- 创建并 review/merge 实现 PR。
- 合并后构建并部署 Cloud Run runner 镜像，复用当前 prediction stream 跑 `2024-01-02` 至 `2026-04-30` fixed-prediction lot-aware reference。
- reference 成功后执行 `23` QA、报告/诊断和 acceptance gate v2，确认能否进入下一轮风险特征训练或模型搜索。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_acceptance_gate_v2_implementation_20260606
相关 issue/PR: PR #97 / 待创建实现 PR

### 已完成工作

- 合并 PR #97，并清理已合并 PRD 分支 / worktree。
- 新建实现工作树 `/Users/luna/Desktop/git/quant-ashare-acceptance-gate-v2-impl` 与分支 `codex/implement-acceptance-gate-v2`。
- 新增 `configs/strategy1/model_acceptance_contract_v2.yml`，固化 v2 accepted / needs_more_evidence / hard reject 阈值、10/20/30/40 组合候选、eligible benchmark、score orientation audit 与 split 复用口径。
- 扩展 `scripts/strategy1_cloudrun/acceptance.py`，为共享契约增加 `contract_sha256` 与 v2 SQL 参数导出，同时保持 v1 历史搜索兼容。
- 新增只读诊断脚本 `scripts/strategy1/diagnose_acceptance_gate_v2.py`：读取当前 extended reference run、prediction、candidate、DWS 标签、DWD 价格和持仓，输出 v2 summary、10/20/30/40 组合可行性、eligible universe benchmark、score orientation audit、低价股偏移、实际持股、现金和风格暴露诊断；不训练、不改 prediction、不写 ADS。
- 新增 `sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`，校验 v2 contract、目标持股集合、reference rejected、候选 top40、score orientation 输入、valid/test 标签输入，以及 BQML/SQL runner 不得登记 v2 accepted baseline。

### 重要上下文

- 默认诊断 run：`acceptance_gate_v2_reference_20260606_01`。
- Reference run/backtest：`s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01`。
- 当前 v2 结论：`rejected`，原因是 `full_period_excess_return_vs_000852<=-0.03`、`full_period_information_ratio<0.0`、`final_holdout_excess_return_vs_000852<=-0.1`。该 rejection 只针对当前 top-30 long-only 组合实现，不否定信号家族。
- 组合可行性摘要：`10/5%` 为 `diagnostic_only`；`20/30/40` 因局部 `max_cash_weight` 或平均现金偏高进入 `needs_more_evidence`，未出现 implementation hard fail。
- uploaded artifact URI：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/acceptance_gate_v2/diagnosis_id=acceptance_gate_v2_reference_20260606_01`。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`
- `configs/strategy1/model_acceptance_contract_v2.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `scripts/strategy1/diagnose_acceptance_gate_v2.py`
- `scripts/strategy1_cloudrun/acceptance.py`
- `sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`
- `sql/ml/strategy1/README.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/diagnose_acceptance_gate_v2.py scripts/strategy1_cloudrun/acceptance.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`
- `python3 scripts/strategy1/diagnose_acceptance_gate_v2.py --project data-aquarium --skip-gcs-upload`
- `bq query --use_legacy_sql=false --location=asia-east2 < /tmp/22_qa_acceptance_gate_v2_outputs.injected.sql`（注入真实 contract hash 后 9 个 ASSERT 全部 successful）
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`（默认 standalone placeholder 预期在 `QA-V2-1` fail-loud）
- `python3 scripts/strategy1/diagnose_acceptance_gate_v2.py --project data-aquarium`（uploaded 成功，16 个 GCS artifact）
- `gcloud storage ls gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/acceptance_gate_v2/diagnosis_id=acceptance_gate_v2_reference_20260606_01/`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 创建并 review/merge 实现 PR。
- 合并后根据 v2 结论决定：继续 PRD03 风险特征训练，或先复核组合现金/执行语义（尤其 `20/30/40` 的局部现金峰值）。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_acceptance_gate_v2_qa_hash_hardening_20260606
相关 issue/PR: PR #98

### 已完成工作

- 采纳 PR #98 review 的可选加固建议：`sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql` 的 `QA-V2-1` 明确拒绝 standalone placeholder hash。
- 保持 production / 真实验证路径不变：由契约注入真实 `acceptance_contract_sha256` 后执行 `22` QA。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`KNOWN_CONSTRAINTS.md` 和当前交接摘要。

### 重要上下文

- 默认直接执行 `22_qa_acceptance_gate_v2_outputs.sql` 现在会在 `QA-V2-1` fail-loud；这是预期行为，用于防止忘记注入真实契约 hash。
- 当前 v2 契约 hash 为 `e7f26a5f33713d9c740abaf9f4a60aa3d3adba119aad514519c30761d3cb8608`。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`
- `sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/diagnose_acceptance_gate_v2.py scripts/strategy1_cloudrun/acceptance.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < /tmp/22_qa_acceptance_gate_v2_outputs.injected.sql`（注入真实 contract hash 后 9 个 ASSERT 全部 successful）
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`（默认 standalone placeholder 预期在 `QA-V2-1` fail-loud）

### 阻塞项

- 无。

### 下一步建议

- PR #98 可继续按 review 结论合并；合并后删除不再使用的 `codex/implement-acceptance-gate-v2` 本地/远端分支。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_acceptance_gate_v2_review_followup_20260606
相关 issue/PR: PR #97 review

### 已完成工作

- 阅读 review 文本，认可全部实质问题，无反驳项。
- 修改 `docs/prd/PRD_20260606_04_策略1验收门v2与组合可行性诊断.md`：
  - `10/5%` 改为 `diagnostic_cash_control`，不参与 `accepted`，不适用满仓现金占比 hard gate。
  - accepted 条件新增跑赢 `eligible_executable_benchmark`，并把 eligible benchmark 拆成 signal-pool 与 executable 两版。
  - split 表新增 `reuse_status`，明确 2025 test / 2026 final_holdout 已被多轮查看，负向证据可 reject，正向证据不能单独 accepted。
  - 新增 `score_orientation_audit.json` 与 QA 断言，检查 actual long side、top-minus-bottom 定义和 RankIC 使用字段。
  - low-price tilt 从文字描述改为可计算字段和 needs_more_evidence / hard_failed 阈值。
  - 新增 gross exposure / deployed capital / exposure-adjusted return 视图。
  - 新增共享验收契约 v2 要求：`configs/strategy1/model_acceptance_contract_v2.yml` 是 v2 阈值和指标定义唯一事实来源，Python acceptance 与 `18/19/22` QA 必须读取同一契约。
  - 修正 `full_period_excess_return_vs_000852=-3%` 的边界归属：`-3%` 属 hard reject，needs-more-evidence 下边界改为开区间。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`DECISION_LOG.md` 和本交接文件。

### 重要上下文

- PRD 仍然只写方案，不改代码、不运行 BigQuery / Cloud Run。
- 10/20/30/40 仍是唯一持股数集合；50 仍被明确排除。
- 后续实现应先落 `model_acceptance_contract_v2.yml`，再做只读 `acceptance_gate_v2` 诊断和组合可行性模拟，之后再决定是否启动 PRD03 风险特征训练。

### 改动文件

- `docs/prd/PRD_20260606_04_策略1验收门v2与组合可行性诊断.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 复核后合并 PRD。
- 合并后先实现 `model_acceptance_contract_v2.yml`，再实现 `acceptance_gate_v2` 诊断和组合可行性模拟。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: strategy1_acceptance_gate_v2_prd_20260606
相关 issue/PR: OQ-010

### 已完成工作

- 新增 `docs/prd/PRD_20260606_04_策略1验收门v2与组合可行性诊断.md`。
- PRD 明确当前 extended reference run `s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` 在 v2 下为 `rejected`，但拒绝范围只针对当前 top-30 long-only 组合实现，不否定信号家族。
- 按 owner 最新口径固定组合候选为 `target_holdings=10/20/30/40`，明确不包含 `50`；首轮单票权重上限仍为 5%。
- PRD 新增 10 万 CNY、100 股整数手、实际持股数、现金占比、买入跳单率、低价股偏移和 eligible universe benchmark 诊断。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`DECISION_LOG.md` 和本交接文件。

### 重要上下文

- 本文是 PRD03 风险特征训练前置门：先实现只读 `acceptance_gate_v2` 诊断和组合可行性模拟，再决定是否启动第 4 波风险特征训练。
- `10/5%` 理论最多部署约 50% 资金，只作为低仓位 / 高现金 / 集中选股对照；`20/5%` 是 5% 上限下理论满仓边界；`30/5%` 是 current reference；`40/5%` 用于验证更分散组合。
- 本次只写 PRD 和记忆/TODO，不改代码、不运行 BigQuery / Cloud Run。

### 改动文件

- `docs/prd/PRD_20260606_04_策略1验收门v2与组合可行性诊断.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`
- `git diff --check --no-index /dev/null docs/prd/PRD_20260606_04_策略1验收门v2与组合可行性诊断.md`

### 阻塞项

- 无。

### 下一步建议

- review / 合并 PRD。
- 合并后实现只读 `acceptance_gate_v2` 诊断、10/20/30/40 组合可行性模拟和 eligible universe benchmark，再决定是否启动风险特征入模。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: pr96_acceptance_window_review_followup_20260606
相关 issue/PR: PR #96 comment `4638273442`

### 已完成工作

- 查看 PR #96 comment `4638273442`，认可 P3：BQML reference 的风险 maxDD 门原先使用 2025 段 maxDD，而 Python 候选风险门使用 full-period summary maxDD，口径不一致。
- 修改 `scripts/strategy1/diagnose_acceptance_window.py`：
  - BQML reference 仍用 2025 段计算 `total_return` / `benchmark_return` / `excess_return`。
  - BQML risk maxDD 门改为读取 `ads_backtest_performance_summary.max_drawdown` 的 full-period 口径。
  - 报告表同时展示 `test_maxDD` 与 `full_maxDD`，Python 候选 summary 文案改为 `failed_full_period_risk_drawdown_target_count`。
- 重新 uploaded 诊断 artifact 到同一路径：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/acceptance_window_diagnosis/diagnosis_id=riskfeat_acceptance_window_20260606_01`。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和本交接文件。

### 重要上下文

- 修正后结论不变：`primary_blocker=mixed_evidence`。
- BQML historical reference 2025-only：total_return 4.05%、benchmark_return 27.49%、excess_return -23.43%、test maxDD -10.06%、full-period maxDD -14.48%。
- Python 15 个已拒 Top5 候选仍为 10 个 2025 excess 未过、5 个 full-period maxDD 未过。
- comment 中关于 2025 小盘基准暴涨导致 `2025-excess` 门与 maxDD 门冲突的策略解读成立，但这是 owner 需要决策的接受门问题，当前 PR 只修诊断口径，不修改 acceptance contract。

### 改动文件

- `scripts/strategy1/diagnose_acceptance_window.py`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/diagnose_acceptance_window.py`
- `git diff --check`
- `python3 scripts/strategy1/diagnose_acceptance_window.py --project data-aquarium --region asia-east2`
- `gcloud storage ls gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/acceptance_window_diagnosis/diagnosis_id=riskfeat_acceptance_window_20260606_01/`

### 阻塞项

- 无代码阻塞；是否调整 2025 test excess / maxDD 接受门仍需 owner 决策。

### 下一步建议

- review / 合并 PR #96。
- 合并后先让 owner 决定是否调整接受门，再决定是否启动第 4 波风险特征训练。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: risk_feature_acceptance_window_impl_20260606
相关 issue/PR: PR #94 / OQ-010 风险特征入模

### 已完成工作

- 合并 PR #94，并清理不再使用的 PRD worktree、本地分支和远端分支。
- 创建实现工作树 `/Users/luna/Desktop/git/quant-ashare-risk-feature-impl` 和分支 `codex/implement-risk-feature-acceptance-diagnosis`。
- 新增 `scripts/strategy1/diagnose_acceptance_window.py`：
  - 只读 `ashare_ads` 既有 ADS / artifact，不写 ADS。
  - 重切 BQML historical reference `bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01` 的 2025-only 指标。
  - 汇总 `sklearn_native_pvfq_n30_bw_h5_20260605_01`、`cloudrun_python_lgbm_pvfq_n30_bw_h5_20260605_01`、`cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01` 的 Top5 已拒候选。
  - 输出 `acceptance_window_diagnosis.json` / `.md`、`bqml_2025_reference_metrics.json`、`python_candidate_acceptance_window.csv`。
- uploaded 模式已成功上传到 `gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/acceptance_window_diagnosis/diagnosis_id=riskfeat_acceptance_window_20260606_01`。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和本交接文件。

### 重要上下文

- 诊断结论为 `primary_blocker=mixed_evidence`，不是可自动继续训练的 `model_feature_gap`，也不是明确暂停的 `acceptance_window_risk`。
- BQML historical reference 2025-only：total_return 4.05%、benchmark_return 27.49%、excess_return -23.43%、test maxDD -10.06%；full-period maxDD -14.48%。
- 15 个已拒 Python Top5 候选：10 个 2025 excess 未过，5 个 full-period max_drawdown 未过；same-side fraction 66.67% 低于 80% 阈值。
- 脚本读取 `ads_backtest_nav_daily` 时显式使用 `trade_date BETWEEN ...` 分区过滤，符合项目硬约束。
- 后续进入第 4 波 `feature_set_id=strategy1_pv_fin_risk_v0_20260606` 训练前，应先由 owner / 审查者复核本诊断。

### 改动文件

- `scripts/strategy1/diagnose_acceptance_window.py`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/diagnose_acceptance_window.py`
- `git diff --check`
- `python3 scripts/strategy1/diagnose_acceptance_window.py --project data-aquarium --region asia-east2`
- `gcloud storage ls gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/acceptance_window_diagnosis/diagnosis_id=riskfeat_acceptance_window_20260606_01/`

### 阻塞项

- 无代码阻塞；下一步训练决策需要 owner / 审查者复核 mixed-evidence 诊断。

### 下一步建议

- 先 review / 合并本实现 PR。
- 若认可 mixed-evidence 下仍继续特征增强，再实现 PRD Phase B 的 `strategy1_pv_fin_risk_v0_20260606` frozen matrix、`feature_delta_vs_base.json`、候选训练和 `21_qa_risk_feature_search_outputs.sql`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: risk_feature_prd_review_followup_20260606
相关 issue/PR: PR #94 / OQ-010 风险特征入模

### 已完成工作

- 查看 PR #94 comment `4638193883`，认可其中 test 复用、个股风险特征增量、回撤目标和零成本前置诊断建议。
- 修改 `docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md`：
  - 明确本轮是 `model_search_wave_no=4` / `test_reuse_wave_no=4`，accepted 必须 `final_holdout_status='passed'`。
  - 增加 Cloud Run 训练前只读 `acceptance_window_diagnosis`，重切既有 BQML historical reference 的 2025-only 指标并汇总已拒 Python 候选。
  - 明确多数个股风险字段可能已在 base feature set 中，必须输出 `feature_delta_vs_base.json`。
  - 明确 market-state 在 hard-action A/B 中为净负，P0 只作特征，必须单独展示贡献。
  - 将共享 `max_drawdown >= -25%` 定义为拒绝地板，本文风险专项 accepted 目标为 `max_drawdown >= -18%`。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和本交接文件。

### 重要上下文

- 不再新增或扩展 BQML / `sql/ml/strategy1` 策略执行路线；PRD 中涉及 BQML 只读 historical reference 是读取已产出 ADS/GCS artifact，不重跑。
- 若 `acceptance_window_diagnosis` 输出 `primary_blocker='acceptance_window_risk'`，后续实现应先停下让 owner 复核接受门 / 年份区间，不应直接启动第 4 波 Cloud Run 训练。
- 如果继续实现 P0，`21_qa_risk_feature_search_outputs.sql` 需校验 `test_reuse_wave_no=4`、final_holdout passed、`risk_feature_max_drawdown_target=-0.18`、`feature_delta_vs_base.json` 和 `acceptance_window_diagnosis.json`。

### 改动文件

- `docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`
- `git diff --cached --check`

### 阻塞项

- 无。

### 下一步建议

- 等 PR #94 review 通过并合并后，先实现只读 `acceptance_window_diagnosis`，再决定是否启动风险特征 Cloud Run search。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: pr93_deploy_smoke_20260606
相关 issue/PR: PR #93 / OQ-005 scheduler runtime naming cutover

### 已完成工作

- 合并 PR #93 后，从 `main` 同步 `orchestration/composer/dags/ashare_common.py`、`orchestration/composer/dags/ashare_ods_ingestion_daily.py` 和 `sql/observability/01_pipeline_status_views.sql` 到 Composer bucket。
- 重新应用 `sql/observability/01_pipeline_status_views.sql` 到 BigQuery。
- 验证 Composer bucket 文件 SHA256 与本地一致，`dags list-import-errors` 返回 `No data found`。
- 触发 ODS-only skip smoke `manual_pr93_ods_only_skip_20260605_20260606_01`，使用 `business_date=2026-06-05`、`skip_ingestion=true`、`skip_downstream_refresh=true`、`pipeline_dry_run=false`、`require_business_partition=true`。
- smoke 结果：DAG success；Cloud Run ingestion dry/write task 均 skipped；`ods_daily_partition_readiness` success；`trigger_warehouse_window_refresh` skipped；`skip_downstream_refresh` Airflow task success 且 `pipeline_task_status.status='skipped'`；无 linked `ashare_warehouse_window_refresh` run；`v_pipeline_refresh_missing`、`v_alert_summary` 和 `check_alerts.py --lookback-minutes 20 --json` 均为空。

### 重要上下文

- 这次 smoke 只验证显式 ODS-only skip 路径，不替代后续两个开市日 scheduled run 观察，也不替代真实非交易日 scheduled skip 自然观察。
- Cloud Run 最新 `ashare-ingest-current-scope` execution 仍为 PR #80 的 `ashare-ingest-current-scope-rf729`（2026-06-06 01:53 UTC 创建），本次 smoke 未创建新 execution。
- PR #93 远端分支因 `gh pr merge --delete-branch` 的本地 worktree 限制未自动删除，后续已清理。

### 改动文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_common.py orchestration/composer/dags/ashare_ods_ingestion_daily.py`
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/observability/01_pipeline_status_views.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/observability/01_pipeline_status_views.sql`
- `gcloud composer environments run ashare-composer --location asia-east2 dags -- list-import-errors`
- `manual_pr93_ods_only_skip_20260605_20260606_01` Airflow task/state + BigQuery status table checks
- `python3 scripts/alerting/check_alerts.py --lookback-minutes 20 --json`

### 阻塞项

- 无当前部署阻塞。

### 下一步建议

- 等至少两个开市日 scheduled run 自然完成，确认采集成功后自动触发 `ashare_warehouse_window_refresh`。
- 等一个真实非交易日 scheduled skip 自然通过，确认 `skip_non_trading_day` 状态落库且 Cloud Run 未触发。
- 继续 Dataform 生产接入 / shadow 验证和完整 ODS→ADS 运维观测闭环。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: pipeline_runtime_naming_cutover_20260606
相关 issue/PR: PR #91 / PR #93 / OQ-005 scheduler runtime naming cutover

### 已完成工作

- 在 PR #91 合并后的最新 `main` 上创建工作树 `/Users/luna/Desktop/git/quant-ashare-pipeline-cutover-hotfix` 和分支 `codex/pipeline-cutover-refresh-missing-fix`。
- 执行生产 cutover：同步 Composer bucket `data/sql/`、新 DAG / alert checker 和 `check_alerts.py`，清理旧 `oq005_alert_checker.py`、旧命名 QA/metadata SQL 与旧 `oq005_*` metrics。
- 通过 `scripts/alerting/setup_alerts.py --notification-channels ...` 将 Cloud Monitoring policies 迁移为 `Ashare Pipeline: ...`，创建 / 对齐 `ashare_pipeline_*` log-based metrics，并保留 Email 通知渠道。
- 触发 alert checker cutover run 和 `qa_only` run，均成功。
- cutover smoke 暴露 `warehouse_refresh_missing` 对非交易日 skip 的误报，已修改 `sql/observability/01_pipeline_status_views.sql`：`v_pipeline_refresh_missing` 排除 `skip_non_trading_day` 与显式 `skip_downstream_refresh`，避免把预期不触发下游刷新报成异常。
- 将修复后的观测 SQL 应用到 BigQuery，并同步到 Composer bucket `data/sql/observability/01_pipeline_status_views.sql`。
- 按 PR #93 review comment 加固 `skip_downstream_refresh`：新增实体 Python task 显式写 `pipeline_task_status.status='skipped'`，不再依赖 `EmptyOperator` success callback 作为唯一豁免证据；观测视图兼容旧 `success` 与新 `skipped` 两种状态。
- 同步 TODO、IMPLEMENTATION_STATUS、OPEN_QUESTIONS、KNOWN_CONSTRAINTS 和本交接。

### 重要上下文

- `warehouse_refresh_missing` 现在只监控“应该触发下游刷新但完全没有 linked warehouse run”的异常。
- 非交易日 scheduled skip 和显式 ODS-only run 不应触发 warehouse refresh；这类 run 以 `pipeline_task_status` 中的 `skip_non_trading_day=skipped` 或 `skip_downstream_refresh=success/skipped` 作为豁免证据。
- 当前生产告警资源已改为稳定命名：`ashare_pipeline_failure`、`ashare_pipeline_task_failure`、`ashare_pipeline_ingestion_failed`、`ashare_pipeline_warehouse_refresh_missing`、`ashare_pipeline_alert_checker_heartbeat`。
- PR #93 review follow-up 的 DAG 加固已部署到 Composer，并通过 ODS-only skip smoke `manual_pr93_ods_only_skip_20260605_20260606_01` 验证不触发 Cloud Run 或 warehouse refresh。

### 改动文件

- `sql/observability/01_pipeline_status_views.sql`
- `orchestration/composer/dags/ashare_common.py`
- `orchestration/composer/dags/ashare_ods_ingestion_daily.py`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/observability/01_pipeline_status_views.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/observability/01_pipeline_status_views.sql`
- 查询 `data-aquarium.ashare_meta.v_pipeline_refresh_missing` 最新 10 行返回 `[]`。
- 查询 `data-aquarium.ashare_meta.v_alert_summary` 最近 20 分钟窗口返回 `[]`。
- `python3 scripts/alerting/check_alerts.py --lookback-minutes 20 --json` 返回 `[]`。
- `python3 -m py_compile orchestration/composer/dags/ashare_common.py orchestration/composer/dags/ashare_ods_ingestion_daily.py`

### 阻塞项

- 无当前切换阻塞。

### 下一步建议

- 观察新 `ashare_ods_ingestion_daily` 至少两个开市日 scheduled run，确认采集成功后自动触发 `ashare_warehouse_window_refresh`。
- 等待一个真实非交易日 scheduled skip 自然通过，确认 `skip_non_trading_day` 状态落库且 Cloud Run 未触发。
- 继续 Dataform 生产接入 / shadow 验证和完整 ODS→ADS 运维观测闭环。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: tailrisk_p2_market_riskoff_run_20260606
相关 issue/PR: PR #92 / OQ-010 尾部风险 P2

### 已完成工作

- 合并后的 `main` 上物化 `sql/dws/08_dws_market_state_daily.sql`，并跑通 `sql/qa/11_market_state_checks.sql`。
- 构建 Cloud Run runner 镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:tailrisk-p2-6db6bd9-20260606-01`，Cloud Build `564b6223-908c-4123-a7b4-f59e7d5fe8dc` succeeded。
- 将 `strategy1-backtest-report-job` 更新到该镜像，使用 `configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml` 跑完 3 条 P2 portfolio-only A/B。
- 查询 ADS summary、trade、NAV 和 tail-risk summary，完成结果判断，并同步 TODO / memory。

### 重要上下文

- `dws_market_state_daily` 结果：`market_state_v0_20260606` 在 `2024-01-02` 至 `2026-04-30` 窗口共 562 行，risk-off 91 日。
- P2 diagnostic-only：run `s1_tailrisk_p2_diag_pvfq_n30_bw_h5_20260606_01` / backtest `bt_s1_tailrisk_p2_diag_pvfq_n30_bw_h5_20260606_01`，total_return 38.25%、excess_return -4.13% vs `000852.SH`、Sharpe 0.882、max_drawdown -14.46%。
- P2 market-only：run `s1_tailrisk_p2_mkt_pvfq_n30_bw_h5_20260606_01` / backtest `bt_s1_tailrisk_p2_mkt_pvfq_n30_bw_h5_20260606_01`，total_return 28.20%、excess_return -14.18% vs `000852.SH`、Sharpe 0.734、max_drawdown -15.72%，`BUY_SKIPPED_MARKET_RISK_OFF` 217 笔。
- P2 combo：run `s1_tailrisk_p2_combo_pvfq_n30_bw_h5_20260606_01` / backtest `bt_s1_tailrisk_p2_combo_pvfq_n30_bw_h5_20260606_01`，total_return 30.04%、excess_return -12.34% vs `000852.SH`、Sharpe 0.773、max_drawdown -14.71%，market skip 217 笔、tail-risk skip 3 笔。
- 最大回撤窗口均落在 2024-05 至 2024-09；market-only 最大回撤更深。P2 v0 `skip_new_buys` 降低平均仓位和交易成本，但错过买点/反弹，当前不应作为默认策略。
- Tail-risk artifact 成功上传，但路径带 `search_id=...`；summary 表的 `tail_risk_report_uri` 仍为空，这是可追溯性小缺口，不影响本轮结论。

### 改动文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/08_dws_market_state_daily.sql`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/11_market_state_checks.sql`
- `python -m scripts.strategy1_cloudrun.orchestrate_experiments --project data-aquarium --region asia-east2 --manifest configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml --config configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml --stage-id tailrisk_p2 --dry-run`
- Cloud Build succeeded：`564b6223-908c-4123-a7b4-f59e7d5fe8dc`
- Cloud Run executions succeeded：`strategy1-backtest-report-job-fg7kr`、`strategy1-backtest-report-job-p8phq`、`strategy1-backtest-report-job-jnzjc`
- Orchestrator final status：`succeeded`，failure_count 0。

### 阻塞项

- 无执行阻塞。策略结论是 P2 v0 不应默认启用。

### 下一步建议

- OQ-010 继续寻找可接受的 Cloud Run Python baseline：下一模型族、特征增强或训练目标改造优先于启用 P2 v0。
- 若继续做市场风控，单独写 P2 v1 方案，考虑更强但可验证的动作，例如风险仓位缩放、风险恢复条件、或按市场状态切换持股/行业暴露，而不是复用当前 `skip_new_buys`。
- 保留 P1 个股风险过滤作为可继续观察的候选 profile；它改善了回撤但收益仍跑输中证1000。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

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
- 生产迁移时先暂停旧 `ashare_daily_pipeline_v0`，再 unpause 新 production DAG；新 DAG 后续连续通过至少两个开市日 scheduled run 和一个非交易日 skip smoke。

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
Run ID: oq005_dag_split_impl_20260606
相关 issue/PR: OQ-005 / Composer DAG split implementation

### 已完成工作

- 在 PRD PR #85 合并后的最新 `main` 上创建工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-dag-split-impl` 和分支 `codex/implement-oq005-dag-split`。
- 新增共享 helper `orchestration/composer/dags/ashare_common.py`，封装 SQL 读取、BigQuery task、Cloud Run ingestion task、runtime conf、非交易日 gate、pipeline/task status 回写、窗口/全量 TaskGroup 和 QA chain。
- 新增 `ashare_ods_ingestion_daily`：每日 20:00 采当前 14 个 ODS endpoint，scheduled 非交易日 skip，ODS readiness 通过后用 `TriggerDagRunOperator` 触发 `ashare_warehouse_window_refresh`；手工 dry-run 或 `skip_ingestion=true` 默认不触发下游。
- 新增 `ashare_warehouse_window_refresh`：支持 `daily_current` / `backfill` 窗口刷新、metadata 恢复、`10_windowed_stock_refresh_checks.sql`、`01-05` QA 和 `qa_only` 只读 QA。
- 新增 `ashare_warehouse_full_rebuild`：手工维护 DAG，无 schedule；必须 `confirm_full_rebuild=true` 且 `date_from/date_to` 必填，`pipeline_dry_run=true` 不执行写入。
- 扩展 `pipeline_run` 元数据字段 `upstream_pipeline_run_id` / `triggered_by_dag_id`；新增 `v_pipeline_refresh_missing`，并将 `warehouse_refresh_missing` 接入 `v_alert_summary` 和 `setup_alerts.py`。
- 按 PR #86 review follow-up 补新 scheduled DAG `is_paused_upon_creation=True`、`ashare_warehouse_window_refresh max_active_runs=1`、refresh-missing watchdog 仅在没有任何 linked warehouse run 时触发。
- 将 Composer README 与 OQ-005 runbook 更新为拆分后的 DAG 入口和手工恢复命令。
- 同步 TODO 与实现状态 / 交接记忆。

### 重要上下文

- 本次只提交仓库文件，未部署 Composer，未运行 BigQuery / Dataform / Cloud Run，未触碰生产 GCS 或 ADS 产物。
- 旧 `ashare_daily_pipeline_v0` 没有在本 PR 中改动，保留为迁移期回滚入口；生产切换时必须先暂停旧 DAG，再 unpause 新 `ashare_ods_ingestion_daily`，迁移期任一时刻只保留一个 production scheduled DAG active。
- P0 使用 `TriggerDagRunOperator` 作为跨 DAG 触发入口，并通过 `upstream_pipeline_run_id` 与 refresh-missing watchdog 做可观测链路；后续如 Composer 版本和运行环境适配，可再升级为 Airflow Datasets。
- `ashare_warehouse_window_refresh` 的 `qa_only` 分支保留旧只读 QA 能力；`ashare_ods_ingestion_daily` 的 ODS-only 手工触发可用 `skip_downstream_refresh=true`。

### 改动文件

- `orchestration/composer/dags/ashare_common.py`
- `orchestration/composer/dags/ashare_ods_ingestion_daily.py`
- `orchestration/composer/dags/ashare_warehouse_window_refresh.py`
- `orchestration/composer/dags/ashare_warehouse_full_rebuild.py`
- `sql/meta/01_create_meta_tables.sql`
- `sql/observability/01_pipeline_status_views.sql`
- `scripts/alerting/setup_alerts.py`
- `orchestration/composer/README.md`
- `docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile orchestration/composer/dags/ashare_common.py orchestration/composer/dags/ashare_ods_ingestion_daily.py orchestration/composer/dags/ashare_warehouse_window_refresh.py orchestration/composer/dags/ashare_warehouse_full_rebuild.py scripts/alerting/setup_alerts.py scripts/alerting/check_alerts.py`
- `git diff --check`

### 阻塞项

- 无代码阻塞。生产启用前必须部署到 Composer 并完成 smoke。

### 下一步建议

- PR 合并后同步新 DAG、`sql/`、观测视图和 `setup_alerts.py` 到 Composer / GCP。
- Composer import 后确认 `ashare_ods_ingestion_daily` 仍为 paused；先暂停 `ashare_daily_pipeline_v0`，再 unpause 新 ingestion DAG。
- 依次验证：开市日 `ashare_ods_ingestion_daily` 真实采集后触发 `ashare_warehouse_window_refresh`；非交易日 `force_non_trading_day_gate=true` 不触发 Cloud Run；手工 `backfill` 小窗口通过；`qa_only` 通过；人工构造 ingestion success 但下游完全未创建 run 时触发 `v_pipeline_refresh_missing` / `warehouse_refresh_missing`。
- 新 DAG 连续通过至少两个开市日 scheduled run 和一个非交易日 skip smoke，旧 `ashare_daily_pipeline_v0` 保持 paused。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: tail_risk_p1_comment_followup_20260606
相关 issue/PR: PR #88 / OQ-010 尾部风险 P1

### 已完成工作

- 拉取并 rebase 到最新 `origin/main`，解决 `.agent/memory/AGENT_HANDOFF.md` 与 `.agent/memory/IMPLEMENTATION_STATUS.md` 的记忆冲突。
- 采纳 PR #88 comment 的两条发现：候选层 P1 风控不能强制卖出已有持仓；必需风险字段 NULL 不能 fail-open。
- 修改 `05_build_candidates.sql`：`individual_risk_guard_v0` 只写 `tail_risk:*` 风险标记，风险标记股票仍参与 TopN / target；必需风险字段 NULL 写 `tail_risk_required_field_null`。
- 修改 Python Ledger v1 与 BigQuery SQL fallback：对 selected tail-risk target，若执行前没有持仓则写 `BUY_SKIPPED_TAIL_RISK` 并跳过新买入；已有持仓不因 P1 标记被强制卖出。
- 更新 `09` 汇总、`10` runner QA、`11` 诊断 SQL、`20` tail-risk QA、报告统计、ADS fill_status 描述、README 和 PRD 正文。
- 按 owner 要求在 `KNOWN_CONSTRAINTS.md` 写入 BigQuery 分区表硬约束：所有启用 `require_partition_filter=TRUE` 的表查询 / DML / 清理 / 断言必须显式带分区列过滤；只按 `run_id` / `backtest_id` 等普通列过滤不满足 BigQuery 必要条件。

### 重要上下文

- 当前 P1 语义保持 PRD 原意：只拦截未持仓新买入，不把已持仓风险股从 target 层强制剔除。
- 短区间 smoke 使用 `--skip-report` 导致 `10_qa_runner_outputs.sql` 的 report guard 按预期失败；这不是 P1 风控逻辑失败。临时 run/backtest 的 ADS 残留已全部清理为 0。
- PR #88 仍需合并部署后跑 full-period `diagnostic_only` vs `individual_risk_guard_v0` A/B。

### 改动文件

- `docs/prd/PRD_20260606_01_策略1尾部风险控制.md`
- `scripts/strategy1/analyze_tail_risk.py`
- `scripts/strategy1/render_report.py`
- `scripts/strategy1_cloudrun/backtest_report.py`
- `scripts/strategy1_cloudrun/ledger.py`
- `sql/ads/01_ads_strategy1_tables.sql`
- `sql/ml/strategy1/05_build_candidates.sql`
- `sql/ml/strategy1/08_run_backtest.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/11_model_quality_diagnostics.sql`
- `sql/ml/strategy1/20_qa_tail_risk_outputs.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python -m py_compile scripts/strategy1_cloudrun/ledger.py scripts/strategy1_cloudrun/backtest_report.py scripts/strategy1/analyze_tail_risk.py scripts/strategy1/render_report.py`
- BigQuery dry-run：`sql/ml/strategy1/05_build_candidates.sql`
- BigQuery dry-run：`sql/ml/strategy1/08_run_backtest.sql`
- BigQuery dry-run：`sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- BigQuery dry-run：`sql/ml/strategy1/10_qa_runner_outputs.sql`
- BigQuery dry-run：`sql/ml/strategy1/11_model_quality_diagnostics.sql`
- BigQuery dry-run：`sql/ml/strategy1/20_qa_tail_risk_outputs.sql`
- 临时 smoke 残留清理查询确认 candidate / target / order / trade / position / nav / summary / monitor 均为 0。

### 阻塞项

- 无代码阻塞；full-period A/B 需等 PR #88 合并并部署新 runner 镜像。

### 下一步建议

- 提交并推送 PR #88 follow-up。
- 合并部署后执行 full-period `diagnostic_only` vs `individual_risk_guard_v0` A/B，重点比较收益、最大回撤、跌停/不可卖暴露、换手、`BUY_SKIPPED_TAIL_RISK` 次数和 acceptance 状态。

### 已更新记忆文件

- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: oq010_tailrisk_p2_market_riskoff_impl_20260606
相关 issue/PR: PR #92 / OQ-010 尾部风险 P2

### 已完成工作

- 在工作树 `/Users/luna/Desktop/git/quant-ashare-tailrisk-p2-market-riskoff`、分支 `codex/implement-tailrisk-p2-market-riskoff` 实现尾部风险 P2 market risk-off。
- 新增 `sql/dws/08_dws_market_state_daily.sql`，生成 `market_state_v0_20260606` 市场状态日表；新增 `sql/qa/11_market_state_checks.sql` 作为市场状态 DWS 门禁。
- Cloud Run Python ledger、SQL fallback `08_run_backtest.sql`、候选生成、汇总、`10` / `11` / `20` QA、中文报告和 tail-risk 诊断均支持 `market_risk_off_v0` / `individual_and_market_risk_guard_v0`。
- 新增 `configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml`，定义复用既有 prediction source、不重新训练的 P2 portfolio-only A/B。

### 重要上下文

- P2 风控动作固定为 `skip_new_buys`：risk-off 执行日只阻止新买 / 加仓，卖出和 pending sell 继续执行。
- risk-off 判定使用 t-1 signal date，执行日写 `BUY_SKIPPED_MARKET_RISK_OFF` 审计行。
- 本次没有实际物化 `dws_market_state_daily`，没有部署新 Cloud Run runner，也没有跑 P2 A/B；这些必须在 PR 合并后继续。

### 改动文件

- `sql/dws/08_dws_market_state_daily.sql`
- `sql/qa/11_market_state_checks.sql`
- `configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml`
- `scripts/strategy1_cloudrun/ledger.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/backtest_report.py`
- `scripts/strategy1/analyze_tail_risk.py`
- `scripts/strategy1/render_report.py`
- `sql/ml/strategy1/05_build_candidates.sql`
- `sql/ml/strategy1/08_run_backtest.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/11_model_quality_diagnostics.sql`
- `sql/ml/strategy1/20_qa_tail_risk_outputs.sql`
- `sql/ads/01_ads_strategy1_tables.sql`
- `sql/ml/strategy1/README.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `docs/数据仓库建模方案-DWS-ADS.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python -m py_compile scripts/strategy1_cloudrun/ledger.py scripts/strategy1_cloudrun/config.py scripts/strategy1_cloudrun/backtest_report.py scripts/strategy1/analyze_tail_risk.py scripts/strategy1/render_report.py`
- P2 manifest 解析：3 个实验均为 portfolio-only，`requires_retrain=false`
- BigQuery dry-run：`sql/dws/08_dws_market_state_daily.sql`、`sql/qa/11_market_state_checks.sql`、`sql/ml/strategy1/05_build_candidates.sql`、`08_run_backtest.sql`、`09_build_metrics_and_report_inputs.sql`、`10_qa_runner_outputs.sql`、`11_model_quality_diagnostics.sql`、`20_qa_tail_risk_outputs.sql`
- `python -m scripts.strategy1_cloudrun.backtest_report --project data-aquarium --region asia-east2 --config configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml --manifest configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml --experiment-id tailrisk_p2_market_riskoff_pvfq_n30_bw_h5_20260606 --dry-run`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- PR 合并后先执行 `sql/dws/08_dws_market_state_daily.sql` 和 `sql/qa/11_market_state_checks.sql`。
- 构建并部署包含 P2 改动的新 Cloud Run runner 镜像。
- 用 `configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml` 跑 diagnostic / market-only / combo 三条 P2 A/B，并比较收益、回撤、skip 笔数和风险暴露。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
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
- 按 PR #77 review comment 修复告警策略幂等：使用当时旧线上稳定键 `user_labels.oq005_policy` 做幂等，并兼容旧 display name 迁移，避免旧名环境重复创建新旧两份策略。
- 更新 alerting README、TODO 和 OQ-005 记忆状态。

### 重要上下文

- 生产 smoke `manual_oq005_alert_checker_heartbeat_global_20260605_01` 成功；随后 scheduled run 也成功。
- Cloud Logging 中 heartbeat 已确认为 `resource.type=global`、`lookback_minutes=20`、`alerts_count=0`。
- Cloud Monitoring `logging.googleapis.com/user/oq005_alert_checker_heartbeat` 的 global timeSeries 已有点；旧的 `k8s_container` heartbeat 只来自修复前第一次 smoke。PR #91 的 `ashare_pipeline_alert_checker_heartbeat` 是后续 cutover 目标名。
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

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: s1_cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01__lgbm_r03_l63_lr002_n600_leaf300_ff09_bf09_l1_01_l2_1
相关 issue/PR: PR #87 comment 4637582821 / OQ-010 / Tail-risk diagnostics P0

### 已完成工作

- 采纳 PR #87 review comment 三条反馈并直接修复。
- `scripts/strategy1/analyze_tail_risk.py` 新增 `--feature-version`，并在 `fetch_positions_enriched` / `fetch_selection_pool` 对 `dws_stock_feature_daily_v0` join 加 `feat.feature_version = @feature_version`，避免多版本特征表行数扇出；summary / search summary / markdown 同步记录 `feature_version`。
- 修复 `compute_drawdown_windows()` 峰值日期口径：回撤 episode 在 `nav >= peak_nav` 时关闭，但只有 `nav > peak_nav` 才更新 peak，保留首次高点日期。
- `scripts/strategy1_cloudrun/backtest_report.py` 调用尾部风险诊断时传入 experiment 的 `feature_version`；非 ADS guard 类尾部风险诊断失败改为 fail-soft，写 `tail_risk/tail_risk_failure.json` 并跳过 `20`，ADS read-only guard 失败仍 hard fail。
- 同步更新 `sql/ml/strategy1/README.md`、`docs/策略1CloudRun训练回测运行手册.md`、`TODO.md` 和相关记忆。

### 重要上下文

- 本次不改变 candidate、target、order、trade、position、NAV、summary 或 acceptance 结果。
- review follow-up 后，Wave 3 regression Top1 最大回撤窗口峰值日按首次高点口径为 `2024-01-02`，谷底日仍为 `2024-02-07`，回撤 `-34.80%`。
- `backtest_report.py` 的 fail-soft 只适用于尾部风险诊断普通异常；只读 guard 一旦发现 ADS summary / NAV hash 改变仍立即失败。

### 改动文件

- `scripts/strategy1/analyze_tail_risk.py`
- `scripts/strategy1_cloudrun/backtest_report.py`
- `sql/ml/strategy1/README.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python -m py_compile scripts/strategy1/analyze_tail_risk.py scripts/strategy1_cloudrun/backtest_report.py`
- `python scripts/strategy1/analyze_tail_risk.py --help`
- `bq query --use_legacy_sql=false --location=asia-east2 --dry_run < sql/ml/strategy1/20_qa_tail_risk_outputs.sql`
- `python -m scripts.strategy1_cloudrun.backtest_report --config configs/strategy1/cloudrun_runner_default.yml --manifest configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml --experiment-id cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_search_v0 --dry-run`
- `git diff --check`
- Wave 3 regression Top1 `analyze_tail_risk.py --feature-version strategy1_pv_v0_20260601 --skip-gcs-upload` 本地 artifact smoke 成功。
- 使用脚本 post-guard hash 执行真实 `sql/ml/strategy1/20_qa_tail_risk_outputs.sql`，job id `838dadcb-1d38-41ca-aea2-0cda757e738e`，无异常。

### 阻塞项

- 无。

### 下一步建议

- 合并 PR #87 后构建 / 部署新的 `strategy1-cloudrun-runner` 镜像。
- 对 Wave 3 Top5 统一生成 uploaded `tail_risk/` artifact 和 comparison summary。
- 基于尾部风险证据实现 P1 `individual_risk_guard_v0` profile A/B。

### 已更新记忆文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
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

- 继续 OQ-005 Dataform 生产接入 / shadow 验证、补跑/resume 自动化和完整 ODS→ADS 运维观测闭环。

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

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: oq005_dag_split_deploy_smoke_20260606
相关 issue/PR: OQ-005 / PR #86 / Composer DAG split production switch

### 已完成工作

- 将 OQ-005 DAG 拆分后的 meta DDL、观测视图、Composer DAG 和仓库 `sql/` 部署到 GCP / Composer bucket。
- 在真实 GCP apply 中修复 `scripts/alerting/setup_alerts.py` 两处兼容问题：log metric 已存在错误识别改为 case-insensitive `already exists`；Monitoring threshold 始终显式设置 `Duration(seconds=...)`，包括 0 秒。
- 创建 / 对齐 `ashare_pipeline_warehouse_refresh_missing` log-based metric 和 `Ashare Pipeline: Warehouse Refresh Missing` alert policy。
- 确认 Composer import errors 为 `[]`，暂停旧 scheduled DAG `ashare_daily_pipeline_v0`，unpause 新 scheduled DAG `ashare_ods_ingestion_daily`。
- 完成三类手工 smoke：非交易日 skip gate、`qa_only`、2026-06-05 1 日 backfill；完成 refresh-missing watchdog synthetic transaction smoke。
- 同步 TODO、IMPLEMENTATION_STATUS、ARCHITECTURE_MEMORY、KNOWN_CONSTRAINTS、OPEN_QUESTIONS 和本交接。

### 重要上下文

- 旧 `ashare_daily_pipeline_v0` 当前已暂停，只作为迁移期回滚参考；新增生产能力不要继续加到旧 DAG。
- 新 production scheduled 入口是 `ashare_ods_ingestion_daily`，每日 20:00 CST 采集当天数据，成功后触发 `ashare_warehouse_window_refresh`。
- `ashare_warehouse_window_refresh` 无 schedule，负责 `daily_current` / `backfill` / `qa_only`，并保持 `max_active_runs=1` 串行。
- 本次没有触发真实 opening-day ingestion→warehouse scheduled run；`manual_split_backfill_20260605_01` 是手工 backfill smoke。

### 改动文件

- `scripts/alerting/setup_alerts.py`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- BigQuery meta DDL 与观测视图 apply 成功。
- Composer DAG import errors 为 `[]`。
- `manual_split_skip_gate_20260606_01` success，`skip_non_trading_day` 状态行落库，Cloud Run execution 未新增。
- `manual_split_qa_only_20260605_01` success，P0 / strategy1 / OQ004 / finance / OQ006 五个只读 QA 均通过。
- `manual_split_backfill_20260605_01` success，窗口刷新和窗口 / P0 QA 均通过；2026-06-05 DWD/DWS 估值链路复核通过。
- refresh-missing synthetic transaction smoke 命中后清理归零，`check_alerts.py --lookback-minutes 20 --json` 返回 `[]`。
- `python3 -m py_compile scripts/alerting/setup_alerts.py` 与 `git diff --check` 通过。

### 阻塞项

- 无阻塞；剩余是 scheduled 自然观察项。

### 下一步建议

- 等新 `ashare_ods_ingestion_daily` 至少两个开市日 scheduled run 自然完成，确认 ingestion success 后自动触发 `ashare_warehouse_window_refresh`。
- 等一个真实非交易日 scheduled run 自然通过，确认 `skip_non_trading_day` 状态行落库且 Cloud Run 不触发。
- 继续 OQ-005 剩余 Dataform 生产接入 / shadow 验证、补跑/resume 自动化和完整 ODS→ADS 运维观测闭环。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: oq005_alert_setup_alreadyexists_followup_20260606
相关 issue/PR: OQ-005 / fd8aefe review follow-up

### 已完成工作

- 评估 `fd8aefe` review：认同 code finding，`create_log_metric()` 不应继续依赖异常 message substring 判断 log metric already exists。
- 在分支 `codex/oq005-alert-logmetric-alreadyexists` 修改 `scripts/alerting/setup_alerts.py`，导入并显式捕获 `google.api_core.exceptions.AlreadyExists`。
- 保留其他异常 fail-fast 行为，不改变告警策略定义、Cloud Monitoring policy 语义或生产调度状态。
- 同步 `IMPLEMENTATION_STATUS.md` 和本交接。

### 重要上下文

- process note 也成立：这次 follow-up 通过分支 / PR 提交，不再直接推 `main`。
- 本分支是对告警配置脚本的稳健性修复；不需要重新部署 Composer DAG，也不触发 BigQuery / Cloud Run。

### 改动文件

- `scripts/alerting/setup_alerts.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/alerting/setup_alerts.py`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 合并 PR 后如需重新应用告警配置，可直接运行 `python scripts/alerting/setup_alerts.py --notification-channels ...`，预期已存在的 log metric 会被类型化 `AlreadyExists` 分支幂等跳过。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: oq005_backfill_resume_helper_20260606
相关 issue/PR: OQ-005 / warehouse refresh backfill-resume automation

### 已完成工作

- 在工作树 `/Users/luna/Desktop/git/quant-ashare-oq005-backfill-resume`、分支 `codex/oq005-backfill-resume` 新增通用补跑脚本 `scripts/pipeline/run_warehouse_refresh.py`。
- 脚本支持 `backfill` 分块计划、`qa-only` 计划、`status` 查询，默认只打印 `gcloud composer ... dags trigger` 计划；只有显式 `--execute` 才触发 Composer。
- `--resume` 查询 `ashare_meta.pipeline_run`，按同一 `warehouse_mode/date_from/date_to` 精确跳过已 `success` 或 `running` 的窗口；`--wait --fail-fast` 支持逐个等待 terminal 状态并在失败时停止。
- PR #90 review follow-up 已补 `--max-execute-runs` 默认 20 个非 skipped run 的执行上限；超过上限时拒绝触发，需缩小日期范围或显式 `--yes`。
- Composer README 与 OQ-005 runbook 已补脚本入口、手工 `gcloud` fallback 和状态查询示例。
- 按 owner 要求在 `KNOWN_CONSTRAINTS.md` 写入：需要代码在工作树中改，改完推 PR。

### 重要上下文

- 文件名使用 `run_warehouse_refresh.py`，不绑定 OQ 编号；OQ-005 只作为当前调度阶段和 runbook 背景保留。
- 本次不部署 Composer、不运行 BigQuery DML、不触发生产 DAG、不修改 Cloud Run / GCS / ADS 产物。
- 后续如需真实补跑，应先不带 `--execute` 生成计划，确认分块窗口和 run id 后再加 `--execute --wait --fail-fast`。

### 改动文件

- `scripts/pipeline/run_warehouse_refresh.py`
- `orchestration/composer/README.md`
- `docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/pipeline/run_warehouse_refresh.py`
- `python3 scripts/pipeline/run_warehouse_refresh.py backfill --date-from 2026-06-03 --date-to 2026-06-04 --chunk-days 1`
- `python3 scripts/pipeline/run_warehouse_refresh.py qa-only --business-date 2026-06-05`
- `python3 scripts/pipeline/run_warehouse_refresh.py backfill --date-from 2026-06-03 --date-to 2026-06-04 --chunk-days 1 --execute --max-execute-runs 1` 返回 2，未触发 Composer。
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- PR 合并后，若需要真实补跑，先用 plan-only 确认窗口，再用 `--execute --wait --fail-fast` 触发。
- 继续 OQ-005 剩余项：新 DAG 至少两个开市日 scheduled run 和一个真实非交易日 scheduled skip 自然观察，Dataform definitions，完整 ODS→ADS 运维观测闭环。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: dataform_definitions_runtime_naming_cleanup_20260606
相关 issue/PR: OQ-005 / Dataform definitions / scheduler runtime naming

### 已完成工作

- 新增 Dataform 首版定义目录：`dataform/workflow_settings.yaml`、`dataform/action_manifest.json`、`dataform/README.md`、`dataform/definitions/**/*.sqlx`。
- 新增生成器 `scripts/dataform/generate_sqlx_from_sql.py`，从 canonical `sql/` 文件生成 SQLX operations / source declarations。
- 按 owner 要求清理调度运行链路阶段性命名：Composer DAG tag、告警 DAG 文件名、告警 metric/policy key、QA task_id、Dataform action/tag、生产 QA / metadata SQL 文件名均改为长期稳定命名。
- 重命名生产 QA / metadata SQL：`01_core_smoke_checks.sql`、`03_index_benchmark_checks.sql`、`05_unit_contract_checks.sql`、`01_core_table_column_descriptions.sql`。
- 同步 runbook、Composer / alerting / Dataform README、SQL README、当前记忆和 TODO 的活动路径。

### 重要上下文

- 本次未部署 Composer / Dataform，未运行 BigQuery DML，未触发 Cloud Run。
- 历史 PRD / archive 中的问题编号可保留为审计记录；运行时命名不得再使用 OQ、Phase、P0/P1 等阶段性编号。
- Dataform 首版目前以 `operations` 包装现有 BigQuery SQL / ASSERT 脚本；生产接入前还需要 shadow / diff 验证和 Composer 调用方式设计。

### 改动文件

- `dataform/**`
- `scripts/dataform/generate_sqlx_from_sql.py`
- `orchestration/composer/dags/ashare_common.py`
- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `orchestration/composer/dags/ashare_ods_ingestion_daily.py`
- `orchestration/composer/dags/ashare_warehouse_window_refresh.py`
- `orchestration/composer/dags/ashare_warehouse_full_rebuild.py`
- `orchestration/composer/dags/ashare_pipeline_alert_checker.py`
- `scripts/alerting/check_alerts.py`
- `scripts/alerting/setup_alerts.py`
- `sql/qa/01_core_smoke_checks.sql`
- `sql/qa/03_index_benchmark_checks.sql`
- `sql/qa/05_unit_contract_checks.sql`
- `sql/metadata/01_core_table_column_descriptions.sql`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 scripts/dataform/generate_sqlx_from_sql.py`
- `npx --yes @dataform/cli compile dataform`：编译通过 31 个 operations。
- `python3 -m py_compile scripts/dataform/generate_sqlx_from_sql.py scripts/alerting/setup_alerts.py scripts/alerting/check_alerts.py scripts/ingestion/run_ingestion_job.py`
- `rg` 确认调度 / alerting / ingestion / QA / metadata / Dataform 范围内无 `oq*`、`OQ-*`、`phase`、旧 `p0_*` task/tag 命中。
- `git diff --check`

### 阻塞项

- 无代码阻塞；生产接入仍需单独实现和 smoke。

### 下一步建议

- 对 Dataform definitions 做 shadow / diff 方案，明确 Composer 如何传 tag / workflow invocation id 并写入 `pipeline_task_status`。
- 部署新命名后的 alert checker DAG 与告警配置前，先确认旧命名资源的迁移 / 清理顺序，避免新旧 policy 并存。
- 新 DAG 继续等待至少两个开市日 scheduled run 和一个真实非交易日 scheduled skip 自然观察。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: prd_strategy1_risk_feature_baseline_20260606
相关 issue/PR: OQ-010 / 策略 1 风险特征入模

### 已完成工作

- 新建工作树 `/Users/luna/Desktop/git/quant-ashare-risk-feature-prd`，分支 `codex/prd-strategy1-risk-feature-baseline`。
- 新增 `docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md`。
- PRD 明确下一轮 OQ-010 不默认启用 P2 v0 `skip_new_buys`，而是把个股尾部风险、市场状态和风险 flag 纳入 Cloud Run frozen matrix。
- 同步 TODO、IMPLEMENTATION_STATUS、PROJECT_CONTEXT、OPEN_QUESTIONS 和本 handoff。

### 重要上下文

- P2 `market_risk_off_v0` / combo A/B 已完成且不采纳为默认策略：market-only total_return 28.20%、max_drawdown -15.72%；combo total_return 30.04%、max_drawdown -14.71%，均弱于 diagnostic-only。
- 新 PRD 默认 `feature_set_id=strategy1_pv_fin_risk_v0_20260606`。
- P0 固定 `tail_risk_profile_id=diagnostic_only`，默认 40 候选 / 20 并发 / 2 vCPU 8Gi，复用 LightGBM binary + regression 和共享 acceptance contract。
- P1 才评估 `candidate_risk_adjustment_profile_id=risk_score_penalty_v0`，并要求与 P0 feature-only 做 A/B。

### 改动文件

- `docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。本文为 PRD，未实现代码、未运行 BigQuery / Cloud Run。

### 下一步建议

- PRD 合并后先实现 backend-neutral training panel / frozen matrix 的风险特征集合，再跑 P0 feature-only risk search。
- 不要直接把 P2 v0 `skip_new_buys` 设为默认策略。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: pr91_dataform_naming_review_followup_20260606
相关 issue/PR: PR #91 / OQ-005 Dataform definitions / scheduler runtime naming

### 已完成工作

- 按 PR #91 review comment 补 `docs/Pipeline-补跑与故障恢复-Runbook.md` 的调度运行命名 cutover checklist。
- `scripts/dataform/generate_sqlx_from_sql.py` 新增 `--check` 模式，用于检查 generated SQLX 是否和 canonical `sql/` / manifest 一致；`dataform/README.md` 补对应命令和 PR 规则。
- `KNOWN_CONSTRAINTS.md` 新增 Dataform 生成物约束：改 manifest 覆盖范围内 canonical SQL 时必须重跑生成器并通过 `--check`。
- 记忆中补充“线上旧名 vs 目标新名”说明：PR #91 尚未部署，2026-06-05 / PR #75 历史线上资源仍按旧 `oq005_*` / `oq005_alert_checker` 名称审计；`ashare_pipeline_*` 是 cutover 后目标稳定名。

### 重要上下文

- 本次仍未部署 Composer / Dataform，未运行 BigQuery DML，未触发 Cloud Run。
- 生产 cutover 必须在同一维护窗口同步 Composer bucket `data/sql/`、新 DAG / alert checker、`ashare_pipeline_*` alert resources，并清理旧 `oq005_*` metrics / policies / checker DAG 文件；新 heartbeat metric 有点前不要视为切换完成。
- Dataform definitions 仍是生成产物，canonical 来源是 `sql/` 和 `dataform/action_manifest.json`。

### 改动文件

- `docs/Pipeline-补跑与故障恢复-Runbook.md`
- `scripts/dataform/generate_sqlx_from_sql.py`
- `dataform/README.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`
- `npx --yes @dataform/cli compile dataform`
- `python3 -m py_compile scripts/dataform/generate_sqlx_from_sql.py`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- PR #91 合并后，按 runbook 在维护窗口执行命名 cutover，并验证 `ashare_pipeline_alert_checker` heartbeat、`qa_only` smoke 和旧 `oq005_*` 资源清理。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

---

日期: 2026-06-06
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop
Run ID: prd_strategy1_lot_aware_ledger_20260606
相关 issue/PR: OQ-010 / 策略 1 整数手交易执行

### 已完成工作

- 新建工作树 `/Users/luna/Desktop/git/quant-ashare-lot-aware-ledger-prd`，分支 `codex/prd-strategy1-lot-aware-ledger`。
- 新增 PRD `docs/prd/PRD_20260606_05_策略1整数手交易执行.md`。
- PRD 明确后续 production acceptance 必须使用 Cloud Run Python `ledger_exec_v1_lot100` 或后续明确升级版，不得用 FLOAT-shares backtest 判定 accepted。
- 按 PR #99 review comment 补充 lot100 Python-only 后不再被现有 Python / SQL parity 覆盖，要求新增 Python 单元 / golden-case 测试独立复算现金、费用、PnL 和 NAV。
- 修正 §5.6.5 的 `min commission` 表述：当前成本 profile 为佣金万一免五，不存在 5 元最低佣金触发条件；现金回退只保留为费用 / 滑点 / 执行价 / 舍入防御性兜底。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`KNOWN_CONSTRAINTS.md`、`OPEN_QUESTIONS.md`、`DECISION_LOG.md` 和本 handoff。

### 重要上下文

- PR #98 已合并，验收门 v2 产物已进入 `main`。
- 当前 extended reference backtest `bt_s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` 的 1291 笔 `FILLED` 成交全部为 FLOAT shares，约 98.2% 四舍五入后也不是 100 股整数倍。
- 新 PRD 固化默认交易规则：买入按 100 股整数手向下取整；清仓卖出允许 odd-lot 全额卖出；部分卖出向下取整到 100 股并保留残股；P0 不做余现金二次分配。
- `15_qa_ledger_resume_consistency.sql` 和 `scripts/qa/run_windowed_refresh_equivalence.py` 不覆盖 lot100；实现时不能只依赖结构性 QA，必须补手工期望值 golden cases。
- 进入下一轮风险特征训练前，必须先实现 lot-aware ledger、补 `23` 或等价 QA、复用当前 prediction stream 跑 `2024-01-02` 至 `2026-04-30` fixed-prediction lot-aware reference，并重跑 acceptance gate v2。

### 改动文件

- `docs/prd/PRD_20260606_05_策略1整数手交易执行.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。本文为 PRD，未实现代码、未运行 BigQuery / Cloud Run。

### 下一步建议

- 合并本文 PRD 后，在实现工作树中实现 Cloud Run Python lot-aware ledger。
- 实现时先补参数 / QA / 报告口径，再跑 fixed-prediction reference；不要直接继续 PRD03 风险特征训练。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

---

## 交接记录：Strategy1 风险特征 wave 4 Cloud Run 真实执行完成

- Date: 2026-06-07
- Agent ID: Codex
- Agent Instance ID: Codex desktop session
- Model: GPT-5 Codex
- Environment: Codex desktop, `/Users/fisher/Desktop/git/quant-ashare`
- Run ID: strategy1_risk_feature_wave4_cloudrun_execution_20260607
- Related issue/PR: owner 已要求创建 PR

### 本轮完成

- 已将误放项目根目录的个人会话包移出仓库，保留在 `~/Downloads` 归档位置；未使用 `.agent/archive/`，未改 `.gitignore`。
- 已确认本地 `main` 到达 `10cbd46c1524888d03c71c643ed7959eb1c998be` 后，在 `codex/fix-riskfeat-training-panel-fields` 上处理 runtime 问题。
- 已构建并部署 Strategy1 runner 镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:riskfeatfix-10cbd46-20260607-04`，digest `sha256:e7d6c5e3c86293046166b8930f6016256fb6f43a46d02be54552b303fc9a6ada`。
- Binary manifest `configs/strategy1/cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_v0.yml` 已完成真实 Cloud Run 执行：`search_id=cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_20260606_01`，`source_run_id=s1_cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_20260606_01`，20/20 fanout 成功，Top5 backtest/report 完成，`19` 和 `21` QA 通过；Top5 全部 rejected，未建立 accepted baseline。
- Regression manifest `configs/strategy1/cloudrun_python_riskfeat_lgbm_regression_pvfq_n30_bw_h5_v0.yml` 已完成真实 Cloud Run 执行：`search_id=cloudrun_python_riskfeat_lgbm_reg_pvfq_n30_bw_h5_20260606_01`，`source_run_id=s1_cloudrun_python_riskfeat_lgbm_reg_pvfq_n30_bw_h5_20260606_01`，20/20 fanout 成功，Top5 backtest/report 完成，`19` 和 `21` QA 通过；Top5 全部 rejected，主要包含 `max_drawdown<-0.25`，未建立 accepted baseline。

### 代码与 SQL 变更

- `sql/cloudrun/strategy1/01_build_training_panel.sql`：补齐 `limit_down_days_20d`、`one_word_limit_days_20d`、`total_mv_cny`、`circ_mv_cny` 的 DWS feature source，并加入 PIT-safe market-state forward-fill。
- `scripts/strategy1_cloudrun/prepare_matrix.py`：将 feature JSON 在 BigQuery 端展开为数值列，按 split 顺序写 transformed features，减少 Cloud Run memory 峰值。
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`：修复 tail-risk enrich alias 冲突，acceptance writeback 改为按 `model_id` 更新并补齐 contract version，同时禁用 BigQuery Storage API dataframe path。
- `sql/ml/strategy1/10_qa_runner_outputs.sql`：`QA-LEDGER-7` 增加 `SELL_SKIPPED_BELOW_LOT_PARTIAL`，覆盖不可交易卖出后次日低于 lot 的合法处理状态。

### 验证

- Binary 风险特征 manifest：真实 Cloud Run fanout 20/20 成功，Top5 backtest/report 完成，`19_qa_cloudrun_python_baseline_search_outputs.sql` 通过，`21_qa_risk_feature_search_outputs.sql` 在 `p_risk_feature_max_drawdown_target=-0.18` 下通过。
- Regression 风险特征 manifest：真实 Cloud Run fanout 20/20 成功，Top5 backtest/report 完成；修复 QA 后手动重跑失败 backtest execution `strategy1-backtest-report-job-jn49x` 成功；`19` QA 通过，`21` QA 在 `p_risk_feature_max_drawdown_target=-0.18` 下通过。

### 后续建议

- Owner 已要求提交当前 `codex/fix-riskfeat-training-panel-fields` 并推送创建 PR；PR #103 已合并到 `main`。
- 当前 wave 4 风险特征 binary/regression 均无 accepted baseline；后续建模应优先评估新模型族、目标函数、样本窗口或 acceptance gate，而不是继续假设本轮风险特征配置可直接晋级。

---

## 交接记录：PR #103 review comment follow-up

- Date: 2026-06-07
- Agent ID: Codex
- Agent Instance ID: Codex desktop session
- Model: GPT-5 Codex
- Environment: Codex desktop, `/Users/fisher/Desktop/git/quant-ashare`
- Run ID: pr103_review_comment_followup_20260607
- Related issue/PR: PR #103

### 本轮完成

- 处理 PR #103 review comment 中认同的 2 个 P2 与 1 个 P3。
- `prepare_matrix.py`：expected feature-set 路径重新读取并校验 `feature_column_list`，且 train split 中任一 expected feature 全空时 fail-fast，避免缺列被 JSON 抽取静默转成全 NaN。
- `sql/cloudrun/strategy1/01_build_training_panel.sql`：新增 `p_market_state_ffill_max_trade_days=5`，market-state forward-fill 只允许沿用最近 5 个源表交易日内的非空值；同时将 `ret_20d`、`drawdown_20d`、`vol_20d` 统一从 `dws_stock_feature_daily_v0` 读取。
- `sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`：`QA-RISK-4` 改查源表 `dws_market_state_daily.csi1000_ret_20d` 缺失率，避免 post-fill 训练面板掩盖源表稀疏。

### 验证

- 本次仅处理 PR comment follow-up，未重新执行 Cloud Run 训练、回测或 BigQuery QA。

### 后续建议

- 如 CI 或 reviewer 要求，可对训练面板 SQL 与 `21` QA 做 BigQuery dry-run，再决定是否需要重建 runner 和局部重跑 matrix。

---

## 交接记录：合并后分支与工作树清理约束扩展

日期: 2026-06-07
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5 Codex
运行环境: Codex desktop, `/Users/fisher/Desktop/git/quant-ashare`
Run ID: post_merge_branch_worktree_cleanup_constraint_20260607
相关 issue/PR: owner 直接要求推送到 main

### 已完成工作

- 扩展 `KNOWN_CONSTRAINTS.md` 中已有 PR 合并后分支卫生规则：除删除已合并且不再使用的 `codex/*` 本地分支和对应远端分支外，还必须移除为该分支创建的独立 `git worktree`。
- 明确若对应 worktree 仍有未提交或未合并改动，先暂停并请 owner 决策，不得强删。
- 同步刷新 `AGENT_HANDOFF.md` 当前交接摘要和常规约定。

### 重要上下文

- 本次是项目工作记忆 / 工程约束更新，不涉及代码、SQL、BigQuery、Cloud Run 或生产资源。

### 改动文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- 未运行测试；本次为文档 / 记忆更新。

### 阻塞项

- 无。

### 下一步建议

- 后续合并 PR 后按该约束同步清理本地分支、远端分支和对应独立 worktree。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

---

## 2026-06-07 上证指数 DWS market-state 补齐

Model: GPT-5 Codex
运行环境: Codex desktop
Run ID: index_000001_dws_market_state_v1_20260607
相关 issue/PR: PR #106 后续提交

### 已完成工作

- 创建 BigQuery 数据集 `data-aquarium.ashare_backup`，用于保存数仓生产契约变更前的备份表。
- 将修改前 `data-aquarium.ashare_dws.dws_market_state_daily` 复制为 `data-aquarium.ashare_backup.dws_market_state_daily_v0`，并写入表说明，明确其是 2026-06-07 添加上证指数 market-state 覆盖前的 v0 生产快照。
- 修改 `sql/dws/08_dws_market_state_daily.sql`：生产表现在同时输出 `market_state_v0_20260606` 兼容行和 `market_state_v1_20260607` 行；v1 增加 `000001.SH` / `SSE_COMPOSITE` 的 5/20 日收益、20 日回撤、20 日波动、20/60 日均线偏离字段。
- 修改 `sql/qa/11_market_state_checks.sql`：默认检查 `market_state_v1_20260607`，并检查默认窗口内 legacy v0 与 current v1 每个交易日各一行。
- 将 `sql/dws/08_dws_market_state_daily.sql` 与 `sql/qa/11_market_state_checks.sql` 接入 `dataform/action_manifest.json` 并重新生成 SQLX。
- 将 `ashare_warehouse_window_refresh` 的 `windowed_transform` 链路补为：指数 DWD 窗口刷新 -> 指数窗口 QA -> 股票 DWD/DWS 窗口刷新 -> 股票窗口 QA -> market-state DWS 重建 -> market-state QA。
- 更新 DWS/ADS 设计文档、架构记忆、实现状态和 TODO。

### 重要上下文

- 本次没有把上证指数纳入 `is_risk_off` / `risk_off_trigger_count` 的触发逻辑，只补 DWS 字段和 v1 版本行，避免静默改变 P2 v0 risk-off 历史结论。
- 既有 runner/config 仍可继续指定 `market_state_v0_20260606`；如后续训练要使用新增上证指数字段，应显式切到 `market_state_v1_20260607` 或另建 feature-set 变更。
- 生产 `dws_market_state_daily` 已用更新后的 SQL 重建成功；`sql/qa/11_market_state_checks.sql` 已更新但本轮未单独执行 QA。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`
- `dataform/action_manifest.json`
- `dataform/definitions/assertions/11_market_state_checks.sqlx`
- `dataform/definitions/dws/08_dws_market_state_daily.sqlx`
- `docs/数据仓库建模方案-DWS-ADS.md`
- `orchestration/composer/dags/ashare_common.py`
- `sql/dws/08_dws_market_state_daily.sql`
- `sql/qa/11_market_state_checks.sql`

### 测试 / 验证

- `python3 scripts/dataform/generate_sqlx_from_sql.py`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/08_dws_market_state_daily.sql`

### 阻塞项

- 无。

### 下一步建议

- 如 owner 需要，可单独执行 `bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/11_market_state_checks.sql` 做 market-state QA。
- 合并部署后同步 Composer bucket 的 `data/sql/` 与 `ashare_common.py`，再触发一次 `ashare_warehouse_window_refresh` 小窗口 smoke 或等待下一次 scheduled refresh。

---

## 2026-06-08 PR #106 review follow-up

Model: GPT-5 Codex
运行环境: Codex desktop
Run ID: pr106_review_followup_market_state_window_20260608
相关 issue/PR: PR #106

### 已完成工作

- 处理 PR #106 review 的 P2：新增 `sql/incremental/03_refresh_market_state_window.sql`，用 `business_date/date_from/date_to/warehouse_mode` 计算写入窗口，向前读取 80 个 SSE 交易日覆盖 20/60 日滚动指标，并用 `MERGE` 更新 `ashare_dws.dws_market_state_daily`，不再在 daily/backfill 路径全表 `CREATE OR REPLACE`。
- `orchestration/composer/dags/ashare_common.py` 的 `build_windowed_transform_group` 已把 `market_state_dws` 从 `sql/dws/08_dws_market_state_daily.sql` 改为 `sql/incremental/03_refresh_market_state_window.sql`，并传入 `_window_refresh_parameters()`；`sql/dws/08_dws_market_state_daily.sql` 只作为初始化 / full rebuild 路径。
- 处理 PR #106 review 的 P3 设计点：`market_state_v0_20260606` 行的 `sse_composite_*` 字段保持 `NULL`，`market_state_v1_20260607` 行才填充上证指数指标；`sql/qa/11_market_state_checks.sql` 新增断言 legacy v0 不得填充 SSE Composite 字段。
- 处理 PR #106 review 的 P3 ODS URI 漂移点：新增 `scripts/ingestion/generate_index_external_table_uris.py`，从 `configs/ingestion/ods_current_scope_v0.yml` 生成 `sql/ods/01_index_external_table_uris.sql`，并支持 `--check` 防止 index endpoint 配置与 external table URI SQL 漂移。
- 重新生成 Dataform SQLX，并更新 DWS/ADS 文档、架构记忆、实现状态和 TODO。

### 重要上下文

- 本次只改代码 / 文档 / 记忆；没有重新执行 BigQuery DWS 重建或 QA。
- 若要让生产 BigQuery 表体现 v0 上证字段为 NULL 的新语义，需要重新执行 `sql/dws/08_dws_market_state_daily.sql` 或按覆盖窗口执行 `sql/incremental/03_refresh_market_state_window.sql`，随后跑 `sql/qa/11_market_state_checks.sql`。
- `sql/ods/01_index_external_table_uris.sql` 以后不要手改 URI 列表；新增指数 endpoint 应先改 `configs/ingestion/ods_current_scope_v0.yml`，再运行 `scripts/ingestion/generate_index_external_table_uris.py`。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`
- `dataform/definitions/**`
- `docs/数据仓库建模方案-DWS-ADS.md`
- `orchestration/composer/dags/ashare_common.py`
- `scripts/ingestion/generate_index_external_table_uris.py`
- `sql/dws/08_dws_market_state_daily.sql`
- `sql/incremental/03_refresh_market_state_window.sql`
- `sql/ods/01_index_external_table_uris.sql`
- `sql/qa/11_market_state_checks.sql`

### 测试 / 验证

- `scripts/ingestion/generate_index_external_table_uris.py`
- `python3 scripts/dataform/generate_sqlx_from_sql.py`

### 阻塞项

- 无。

### 下一步建议

- 如 owner 要求生产即时落地，执行 market-state 全量或窗口刷新并跑 `11_market_state_checks.sql`。
- 更新 PR #106 正文 / 回复 review comment，说明三条 comment 已处理。

---

## 2026-06-08 index benchmark QA 日期上限修复

Model: GPT-5 Codex
运行环境: Codex desktop
Run ID: fix_index_benchmark_qa_date_bound_20260608
相关 issue/PR: 待创建 PR

### 已完成工作

- PR #106 合并后，生产 `dws_market_state_daily` 已重建并通过 `sql/qa/11_market_state_checks.sql`（`QA-MKT-0..9` 全部 successful）。
- Composer 已同步 PR #106 相关 SQL 与 `ashare_common.py`，并触发 smoke `manual_pr106_market_state_window_smoke_20260605_20260608_01`。
- smoke 中 `index_dwd_window`、`windowed_index_refresh_checks`、`stock_dwd_dws_window`、`windowed_stock_refresh_checks`、`market_state_dws`、`market_state_checks` 均 success。
- smoke 后置 `qa_after_window.index_benchmark_checks` 暴露默认 `dwd_end_date = CURRENT_DATE('Asia/Shanghai')` 问题：2026-06-08 当天 000001.SH ODS/DWD 未到数时，backfill smoke 被误判为“000001.SH 未覆盖每个 2019+ SSE 开市日”。
- 新分支 `codex/fix-index-benchmark-qa-date-bound` 已修复 `sql/qa/03_index_benchmark_checks.sql`：默认 `dwd_end_date` 改为 `dwd_index_eod` 中 `000001.SH` 已有完整 price + dailybasic 的最新 SSE 开市日，并新增 `dwd_end_date` 非空 / 不早于 `dwd_start_date` 断言。
- 同步生成 `dataform/definitions/assertions/03_index_benchmark_checks.sqlx`。

### 重要上下文

- 该修复不降低 000001.SH 覆盖质量门，只是把默认检查终点从“不确定的今天”改成“DWD 中已完整落库的最新可用日期”。
- 若后续需要强制检查某个最新业务日，应通过补齐 ODS/DWD 后再运行 QA，或显式改参数化版本；不要把调度默认恢复为 `CURRENT_DATE`。
- 当前仍有未跟踪临时文件 `scripts/ingestion/backfill_index_000001.py`，本修复未纳入该文件。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`
- `dataform/definitions/assertions/03_index_benchmark_checks.sqlx`
- `sql/qa/03_index_benchmark_checks.sql`

### 测试 / 验证

- `python3 scripts/dataform/generate_sqlx_from_sql.py`
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/03_index_benchmark_checks.sql`

### 阻塞项

- 无。

### 下一步建议

- 提 PR 并合并后，同步 `sql/qa/03_index_benchmark_checks.sql` 到 Composer bucket。
- 重新触发或等待当前 smoke retry，让 `qa_after_window.index_benchmark_checks` 使用新口径通过。

---
Date: 2026-06-08
Model: GPT-5 Codex
Branch: codex/implement-composer-exit
Summary:
- Added first implementation slice for OQ-005 Composer exit on a dedicated worktree branch.
- Added thin `ashare-pipeline-control` Cloud Run service for pipeline status writeback, bundled SQL execution, SSE trading-day gate, and GCS-backed orchestration locks.
- Added Workflows definitions for `ashare_ods_ingestion_daily` and `ashare_warehouse_window_refresh` with explicit per-task status writes and synchronous child workflow invocation.
- Added deployment scaffolding and directory README for the workflows migration path.
Files:
- scripts/pipeline_control/__init__.py
- scripts/pipeline_control/requirements.txt
- scripts/pipeline_control/state.py
- scripts/pipeline_control/service.py
- orchestration/workflows/Dockerfile.pipeline_control
- orchestration/workflows/cloudbuild.pipeline_control.yaml
- orchestration/workflows/deploy_pipeline_control_service.sh
- orchestration/workflows/deploy_workflows.sh
- orchestration/workflows/README.md
- orchestration/workflows/ashare_ods_ingestion_daily.yaml
- orchestration/workflows/ashare_warehouse_window_refresh.yaml
- sql/meta/01_create_meta_tables.sql
Open follow-ups:
- Migrate `ashare_warehouse_full_rebuild` to Workflows with the same hard constraints.
- Migrate `ashare_pipeline_alert_checker` off Composer.
- Add Cloud Scheduler jobs, runtime IAM bootstrap, and shadow-run / cutover scripts.
- Review Workflows YAML semantics against PRD hard constraints before deployment.
Validation:
- Not run in this turn by owner instruction.

---
Date: 2026-06-08
Model: GPT-5 Codex
Branch: codex/implement-composer-exit
Summary:
- Addressed PR #110 review P2 items and one additional runtime blocker in the control service.
- Added explicit Workflow `http.post` timeout for `/v1/tasks/bigquery` and increased warehouse lock lease headroom.
- Wired lock lease semantics end-to-end in seconds and made lock endpoints backward-compatible with current workflow payload shape while resolving generation by owner when omitted.
- Fixed `/v1/tasks/bigquery` to accept the current flattened workflow payload as context, not only nested `context` form.
Files:
- orchestration/workflows/ashare_ods_ingestion_daily.yaml
- orchestration/workflows/ashare_warehouse_window_refresh.yaml
- scripts/pipeline_control/service.py
- scripts/pipeline_control/state.py
Open follow-ups:
- Consider adding Workflow execution liveness checks before stale-lock reclaim if phase 1 runtime shows lock-expiry edge cases.
Validation:
- Not run in this turn by owner instruction.

---
Date: 2026-06-08
Model: GPT-5 Codex
Branch: codex/implement-composer-exit
Summary:
- Addressed PR #110 re-review runtime bug in the lock compatibility path.
- Fixed `lock_generation_for_owner` to construct the GCS blob and read lock content correctly before deriving generation by owner.
- This restores the intended heartbeat/release path for workflows that omit explicit `generation` and rely on backward-compatible `lock_name`/`owner` payloads.
Files:
- scripts/pipeline_control/state.py
Validation:
- Not run in this turn by owner instruction.

日期: 2026-06-08
Agent ID: Codex
Agent 实例 ID: composer-exit-next-worktree
模型: GPT-5 Codex
运行环境: Codex desktop / zsh / macOS
Run ID: oq005-composer-exit-next-20260608
相关 issue/PR: 待创建 PR

### 已完成工作

- 把 Composer 过渡态的 `ashare_pipeline_alert_checker` 调整为每小时 1 次：DAG schedule 改为 `0 * * * *`，`check_alerts.py` lookback 改为 `70` 分钟。
- 补了 cutover 后的小时级告警检查骨架：`ashare-pipeline-control` 新增 `/v1/tasks/alert-check`，并新增 `orchestration/workflows/deploy_scheduler_jobs.sh`，用 `Cloud Scheduler` 以 OIDC 调用 Cloud Run。
- 同步把 `scripts/alerting/setup_alerts.py` / `scripts/alerting/README.md` / `orchestration/composer/README.md` / `orchestration/workflows/README.md` 改到小时级口径。
- 补出 `orchestration/workflows/ashare_warehouse_full_rebuild.yaml` 工作流草案，并把部署脚本接上该 workflow。
- 确认 `airflow_monitoring` 是 Composer 平台托管健康监控 DAG，不是项目可控调度项；无法在仓库代码中降到每小时，只能在 cutover 后随 Composer 环境删除而消失。

### 重要上下文

- 这轮没有部署新的 Cloud Run service / Workflow / Scheduler job，也没有跑新的 smoke；当前变更仍停留在代码和记忆层。
- `ashare_warehouse_full_rebuild` 当前只是草案。`scripts/pipeline_control/state.py` 的 BigQuery 执行仍同步等待 `job.result()`，full rebuild 长 SQL 可能超过 Cloud Run request timeout 或 Workflows step timeout；在改成 submit + poll 或进一步拆步之前，不应部署到生产。
- owner 对告警链路的要求现在已经固化为“最多每小时 1 次”。后续如果还有频率相关需求，迁移后的 `Cloud Scheduler` 配置应继续沿用同一上限。

### 改动文件

- `orchestration/composer/dags/ashare_pipeline_alert_checker.py`
- `orchestration/composer/README.md`
- `orchestration/workflows/README.md`
- `orchestration/workflows/deploy_workflows.sh`
- `orchestration/workflows/deploy_scheduler_jobs.sh`
- `orchestration/workflows/ashare_warehouse_full_rebuild.yaml`
- `scripts/alerting/README.md`
- `scripts/alerting/setup_alerts.py`
- `scripts/pipeline_control/requirements.txt`
- `scripts/pipeline_control/service.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未运行新的本地测试。
- 未部署新的 Cloud Run / Workflows / Cloud Scheduler。
- `airflow_monitoring` 不可调频这一点基于官方 Composer 文档确认，不是本地代码推断。

### 阻塞项

- `ashare_warehouse_full_rebuild` 仍受控制层同步 `job.result()` 设计限制，未解决前不能安全部署。

### 下一步建议

- 先决定 `ashare_warehouse_full_rebuild` 是改控制层为 submit + poll，还是继续拆成更小、可轮询的 SQL 步骤。
- 把 `ashare_pipeline_alert_checker` 的 Cloud Scheduler job 和 `ashare-pipeline-control` alert-check endpoint 做一次真实部署 / smoke。
- 再继续补 `backfill` / 非交易日 skip smoke 和 cutover runbook，收口 Composer exit。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - PR #113 review 已确认上一版 bool 白名单过宽：`risk_*` 6 列与 `is_*` 4 列在 training panel JSON 中是数字 `1.0/0.0` 或 `1/0`，不能按 `BOOL` 解包。
> - 已将 Strategy1 Cloud Run `BOOLEAN_FEATURE_COLUMNS` 收窄为仅 4 个 `has_fin_*`；它们继续走 `BOOL -> INT64`，其余 `risk_*` / `is_*` 恢复走 `FLOAT64`。
> - 这次是针对 review 的最小纠偏，不改 runner 其他逻辑；现有 PR #113 需以这版为准，上一条 handoff 中“新增布尔特征时同步更新布尔清单”仍成立，但布尔清单只应收录真实 JSON 布尔字段。

## 2026-06-08 - GPT-5 Codex
- Date: 2026-06-08
- Model: GPT-5 Codex
- Branch: `codex/cloudrun-boolfix-benchmark-smoke`
- Summary: 修复 Strategy1 Cloud Run `prepare_matrix` 把 JSON 布尔特征按 `FLOAT64` 解包而导致矩阵构建失败的问题，并完成 `000001.SH` 主 benchmark 下的 `12` 候选 LightGBM regression smoke。
- Files: `scripts/strategy1_cloudrun/feature_sets.py`, `scripts/strategy1_cloudrun/prepare_matrix.py`
- Validation: Cloud Run smoke `search_id=cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_smoke_20260608_05` 成功；Top1 `lgbm_r03_l63_lr002_n600_leaf300_ff09_bf09_l1_01_l2_1` 的最终 artifact 已写出 `benchmark_sec_code=000001.SH` 和 `*_vs_primary_benchmark` 路径结果。
- Notes: 本地 `gcloud` 若需继续追 execution describe，需显式绑定 `CLOUDSDK_PYTHON` 到仓库运行时的 Python 3.10+；这是工作站环境事项，不属于仓库代码变更。
- Next Steps: 继续基于当前 `v1` 门做下一轮模型/特征搜索；`v2` 路径后续忽略。

## 2026-06-08 - GPT-5 Codex
- Date: 2026-06-08
- Model: GPT-5 Codex
- Branch: `codex/cloudrun-boolfix-benchmark-smoke`
- Summary: 处理 PR #113 review，纠正 Strategy1 Cloud Run JSON 布尔特征白名单过宽的问题，避免把 10 个数值型 `risk_*` / `is_*` 特征静默解码为 `NULL`。
- Files: `scripts/strategy1_cloudrun/feature_sets.py`
- Validation: 基于 `sql/cloudrun/strategy1/01_build_training_panel.sql` 的字段类型复核，确认仅 4 个 `has_fin_*` 是 JSON 布尔；`risk_*` 为 `1.0/0.0`，`is_*` 为 `1/0`，必须继续走数值解包路径。
- Notes: 这是对同一 PR 的后续修复，未重跑新的 Cloud Run smoke；现有 smoke 结果只说明链路跑通，不再作为这 10 个字段解码正确性的证据。
- Next Steps: push 到 PR #113，并按该 review 结论继续后续搜索。

## 2026-06-08 - GPT-5 Codex
- Date: 2026-06-08
- Model: GPT-5 Codex
- Branch: `main`
- Summary: 新增策略 1 验收门 `v3` 切换实施 PRD，明确当前仍是 `v1` 主写回门，后续直接 `v1 -> v3`，不经过 `v2`。
- Files: `docs/prd/PRD_20260608_02_策略1验收门v3切换实施.md`
- Validation: 文档级变更；未改代码、未跑 Cloud Run、未跑 BigQuery QA。
- Notes: `v3` 当前仍是 doc + replay gate，不是 production write-back gate。实现前置顺序已经固定为 contract -> replay -> QA -> live cutover。
- Next Steps: 新增 `configs/strategy1/model_acceptance_contract_v3.yml`，再实现 `v3` replay 和对应 QA。
