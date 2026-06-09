# 实现状态（Implementation Status）

这是实现状态的唯一事实来源。面向「已完成/进行中/受阻的整体状态」；「下一步要做什么」见根目录 `TODO.md`。

Last updated: 2026-06-09

## 当前状态

### 最新补充（2026-06-09）：Strategy1 R14 长训练窗口回测 PRD 已新增

- 新增 `docs/prd/PRD_20260609_01_策略1R14长训练回测.md`，定义固定当前 R14 LightGBM regression 方法，不重新搜索参数，使用名义训练窗口 `2015-04-01 ~ 2019-12-31`，先跑 `2020-01-02 ~ 2022-12-30` 的 `10` 只 / `20` 只双组合 diagnostic backtest；`2023-01 ~ 2026-06-09` 追加回测视 P0 结果和 owner 决策而定，若追加也跑两个组合。
- PRD 明确 `5d` 标签必须做 embargo：训练样本只保留未来 5 日标签完整落在 `2019-12-31` 及以前的信号日，避免 2019 年末样本使用 2020 回测期收益形成标签。
- PRD 将 P0 组合设为 `target_holdings=10` / `max_single_weight=15%` 与 `target_holdings=20` / `max_single_weight=7.5%` 两个变体，并明确当前 Cloud Run Python ledger P0 仍是 fresh-start；后续如单独跑 `2023-2026-06-09` 只能作为追加诊断，正式连续结果默认必须从 2020 重新 fresh-run，除非 Cloud Run Python ledger resume 已实现并通过 resume consistency QA。
- 该 PRD 只写方案，未执行 BigQuery / Cloud Run；下一步是只读覆盖审计 2015-2018 DWD/DWS、risk feature、market-state 和 label embargo 样本数。

### 最新补充（2026-06-09）：OQ-005 旧 Composer 补跑 helper 已清理

- `scripts/pipeline/run_warehouse_refresh.py` 是 Composer 时代通过 `gcloud composer environments run` 触发 `ashare_warehouse_window_refresh` 的补跑 / resume helper；当前生产入口已切到 `Cloud Scheduler + Cloud Workflows` 且 `ashare-composer` 已删除，因此该脚本已从仓库移除。
- 后续窗口补跑 / QA-only / full rebuild 恢复路径以 `docs/Pipeline-补跑与故障恢复-Runbook.md` 和 `orchestration/workflows/**` 为准；不得把旧 Composer helper 重新作为 active 运维入口。

### 最新补充（2026-06-09）：Strategy1 live acceptance gate 已在分支切到 v3

- Cloud Run Python search 的默认 acceptance contract 已从 `model_acceptance_contract_v1.yml` 切到 `model_acceptance_contract_v3.yml`；v1 保留为历史搜索审计契约。
- live orchestrator 在回写 ADS 前会按实际 backtest span / manifest final_holdout window 和 v3 contract 的五指数集合重算候选级 Sharpe / Calmar / 复合年化、策略最大回撤同期超额和 Excess Calmar，并把 v3 状态写入 registry / backtest summary / comparison artifact；contract 的 replay 默认窗口不再无条件套用于 live。
- `19` QA 已改成 v3-aware：v3 accepted 不再套用旧的 000852 / final_holdout hard gate，而是检查 v3 信号质量、Sharpe、Calmar 和五指数相对门摘要；`21` risk-feature QA 已把旧的风险回撤 overlay 约束限定在 legacy contract。
- 已用 PR #125 分支镜像 `strategy1-cloudrun-runner:pr125-smoke-3210a7f` 和临时 `*-pr125-smoke` Cloud Run jobs 跑通 2 候选 live v3 smoke：prepare matrix、2 个 candidate fanout、select/register/predict、backtest/report、19 QA 和 comparison artifact 上传均 succeeded。smoke 结果为 Top-K 1 rejected，registry 写出 `model_acceptance_contract_v3`、`strategy1_acceptance_gate_v3`、`000001.SH`、5 个 comparison benchmark 和 v3 Sharpe / Calmar；`v3_relative_gate_by_benchmark.csv` 已生成。smoke 过程中发现逐指数 artifact 的 `search_id` 未透传，已在分支修复。

### 最新补充（2026-06-08）：OQ-005 调度迁移已完成 production cutover

- 生产调度唯一入口已经切到 `Cloud Scheduler + Cloud Workflows`：`ashare-ods-ingestion-daily`（`0 20 * * *`）负责 ODS daily + child warehouse refresh，`ashare-pipeline-alert-checker`（`0 * * * *`）负责小时级告警检查。
- `ashare_pipeline_alert_checker`、`ashare_ods_ingestion_daily`、`ashare_warehouse_window_refresh` 与 `ashare_warehouse_full_rebuild` 的 Workflows 路径都已完成部署；`qa_only`、`daily_current`、`backfill`、非交易日 skip、alert checker 和 full rebuild dry-run 都已有真实 smoke 证据。
- `ashare-composer` 环境已于 2026-06-08 删除完成；`orchestration/composer/**` 现在只保留为 retired / audit-only 历史快照，不再是现行生产路径。
- `docs/Pipeline-补跑与故障恢复-Runbook.md` 已改写为 Workflows 版恢复手册，告警链路不会再把 on-call 指向已删除的 `ashare-composer` 操作命令；`scripts/alerting/README.md` 与 `setup_alerts.py` 的描述也已同步到 Scheduler + Workflows 路径。
- 2026-06-09 首次 20:00 scheduled ODS run 暴露 runtime SA 权限缺口：Cloud Run Job 需要 `run.jobs.runWithOverrides`，operation polling 需要 `run.operations.get`；live IAM 已补 `roles/run.jobsExecutorWithOverrides`（job-level）和 `roles/run.viewer`（project-level），bootstrap 脚本也已同步修正。

### 最新补充（2026-06-08）：Strategy1 `v3` replay / `24` QA 已收口为 contract-driven 路径

- `configs/strategy1/model_acceptance_contract_v3.yml` 已作为 `v3` 口径唯一事实来源。
- `scripts/strategy1/replay_acceptance_gate_v3.py` 与 `scripts/strategy1/run_acceptance_gate_v3_replay_qa.py` 已按最新 contract 真执行通过；当前结果仍为 `25` 个候选里 `1 accepted / 24 rejected`。
- `24_qa_acceptance_gate_v3_replay_outputs.sql` 已不再依赖手工镜像默认值：replay scope、Top-K、benchmark 集合、窗口、阈值和允许的 `score_orientation` 都由 helper 从 contract 渲染。

### 最新补充（2026-06-08）：当前仍开放的主线只剩 OQ-010 与 OQ-012

- OQ-010：Cloud Run Python 路径已打通，但当前仍没有 accepted Python baseline；后续重点仍是寻找可接受模型 / 特征 / 风险控制组合。
- OQ-012：schema contract、修复/验证脚本和 `06_ods_parquet_schema_checks.sql` 都已具备，当前 BigQuery 读层无 mismatch 暴露；剩余是 owner 是否正式关闭该问题，或保留防复发工程项。

## 已完成（Completed）

- P0 数仓底座已完成：4 张 DIM、5 张 DWD、核心 QA 和单位契约均已落地并通过 BigQuery smoke。
- OQ-003 / OQ-004 / OQ-006 已实现并关闭：财务三大报表 DWD + `dws_stock_feature_fin_daily`、`dim_index` / `dwd_index_eod` benchmark 口径、`ods_field_unit_map` 与 `05_unit_contract_checks.sql` 均已进入 `main`。
- OQ-005 已完成从 Composer 迁出：thin control-plane、ODS daily / warehouse window refresh / alert checker / full rebuild 四条 Workflows 路径已落地，生产 scheduler 已切换，Composer 环境已删除。
- `orchestration/composer/**` 已完成历史目录收口：README 改为 retired / audit-only 说明，保留的 DAG/helper 只用于审计、迁移对照和受控回滚参考。
- OQ-005 active recovery runbook 已完成 Workflows 改写：当前恢复命令使用 `gcloud workflows execute`、`gcloud scheduler jobs run/describe`、Cloud Run Jobs 与 BigQuery 状态表，不再使用 Composer / Airflow。
- 策略 1 历史 BigQuery ML runner、中文报告、GCS uploaded 模式、模型质量诊断、live-available 预测池口径和 score orientation 校准都已完成；这些结果只保留为 historical reference / audit，不再作为未来默认执行路径。
- Strategy1 `v3` acceptance gate 的只读 replay、helper 驱动的 `24` QA 和 contract-driven 参数注入已实现并真执行通过。
- `000001.SH` 的 ODS / DIM / DWD / DWS 链路已补齐，`dws_market_state_daily` 已保留 `market_state_v0_20260606` 兼容行并新增 `market_state_v1_20260607` 上证指数字段。

## 进行中 / 部分（In Progress）

- OQ-010：Cloud Run Python / native 模型路线仍在探索，当前 binary / regression / risk-feature 多轮候选都未产生 accepted baseline；live acceptance gate 正在从 v1 切到 v3，PR #125 分支已完成 2 候选 smoke。
- OQ-012：schema repair 工具链和 QA 已 ready，当前问题更偏向收口决策，而不是缺实现。
- OQ-005：主迁移已完成，只剩 cutover 后短观察窗记录和少量非阻断运维收尾。

## 未开始 / 未来（Not Started / Future）

- 若后续真实运行暴露 stale-lock 边界，再为 `ashare-pipeline-control` 的 stale-lock reclaim 增加 Workflows execution liveness 检查。
- 若 owner 决定继续精修 OQ-012，可把 schema contract / cast 防复发要求进一步前推到 ingestion 发布链路。
- 若 owner 决定继续推进策略侧，优先做 OQ-010 可接受 Python baseline，而不是恢复 BQML / SQL runner 路线。
- `lookback-capable` 价格构建输入、P1+ 资金面/事件/行业族 DWD、`dim_stock_sw_industry_hist` / `dim_stock_ci_industry_hist` 仍是后续扩展项。

## Coverage Snapshot

| 能力 | 状态 | 备注 |
|---|---|---|
| ODS 理解 | 高 | 57 张外部表字段与分区语义已摸清 |
| DWD/DIM 设计 | 高 | 主文档与命名/单位/分区约束已稳定 |
| P0 表物化/QA | 已完成 | 4 张 DIM + 5 张 DWD + 核心 QA 已通过 |
| DWS/ADS 设计 | 已完成 | 两篇设计文档已完成；策略 1 主体契约已落地 |
| OQ-005 调度迁移 | 已完成 | 生产入口已切到 `Cloud Scheduler + Cloud Workflows`，Composer 已删除 |
| 财务三大报表 DWD | 已完成 | `dwd_fin_income/balancesheet/cashflow` + `_latest` 与 `04/05` QA 已通过 |
| 市场状态 DWS | 已完成首版 | `dws_market_state_daily` 已进入生产链路，保留 v0 + v1 口径 |
| Strategy1 历史 BQML runner | 已完成 | 只保留为历史 reference / audit |
| Strategy1 Cloud Run Python 路线 | 部分完成 | 执行链路已可运行；live acceptance gate 已在分支切到 v3 并通过 2 候选 smoke，但仍无 accepted baseline |
| ODS schema repair | 部分完成 | contract / tooling / QA 已具备，待 owner 决定最终收口 |
