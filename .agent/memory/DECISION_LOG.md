# 决策日志（Decision Log）

记录持久的项目决策。主文件保留全量索引与最近 10 条决策全文；更早全文按月归档到 `archive/DECISION_LOG_YYYY-MM.md`。

## 决策格式

```md
## DECISION-YYYYMMDD-NN: <标题>

Date:
Status: active | superseded
Owner:
Context:
Decision:
Rationale:
Impact:
Related files:
```

## 决策索引

| ID | 日期 | 标题 | 状态 | 归档全文 |
|---|---|---|---|---|
| DECISION-20260531-01 | 2026-05-31 | 三层数仓分层 | active | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-02 | 2026-05-31 | 证券主键统一为 sec_code（数据源中性） | active | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-03 | 2026-05-31 | 量纲统一元/股 | active | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-04 | 2026-05-31 | 财务可见时间字段用 ann_date_eff | active | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-05 | 2026-05-31 | 按月分区 + sec_code 聚簇 | active | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-06 | 2026-05-31 | 行情表强制分区过滤 + 初始回填范围 | active | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-07 | 2026-05-31 | 表/字段注释规范 + 描述继承 ODS | active | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-08 | 2026-05-31 | Agent 产出标明模型名 | active | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-09 | 2026-05-31 | 按 Review 整改建模方案（9 采纳 / 2 调整） | active | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-10 | 2026-05-31 | DWD/DIM 初始写入 ODS 可用全历史 | superseded by DECISION-20260531-11 | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-11 | 2026-05-31 | 当前阶段先做好 2019+ 数据，2019 前仅作必要支撑 | active | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-12 | 2026-05-31 | P0 建表 SQL 先以根目录 sql/ bootstrap 脚本落地 | active | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-13 | 2026-05-31 | 评审须产出 docs/reviews/ 评审文档；评审本身只读 | superseded by DECISION-20260601-03 | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-14 | 2026-05-31 | 采纳 P0 SQL 首轮评审并修复物化前风险 | active | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-15 | 2026-05-31 | P0 先将 dwd_index_eod 物化为价格-only | superseded by DECISION-20260531-16 | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-16 | 2026-05-31 | 恢复 dwd_index_eod 指数估值/股本字段 | active | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-17 | 2026-05-31 | 拆分全天停牌与盘中临停语义，并修正财务 latest 排序 | active | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-18 | 2026-05-31 | DWS/ADS 采用分族特征层 + 策略消费层 | active | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-19 | 2026-05-31 | 行业时点映射改用已补采的 index_member_all / ci_index_member | active | archive/DECISION_LOG_2026-05.md |
| DECISION-20260531-20 | 2026-05-31 | P0 表字段说明由集中 metadata 脚本补齐 | active | archive/DECISION_LOG_2026-05.md |
| DECISION-20260601-01 | 2026-06-01 | 指数 DWD 使用 canonical sec_code 并保留 source_sec_code | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260601-02 | 2026-06-01 | 策略 1 runner 采用 BigQuery ML + SQL 执行路径 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260601-03 | 2026-06-01 | GitHub PR review 默认写 PR comment | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260601-04 | 2026-06-01 | dim_stock 退市日优先使用 ODS delist_date | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260601-05 | 2026-06-01 | 财务 report_type 默认合并报表，DWD 保留口径维度 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260601-06 | 2026-06-01 | 策略 1 首个基线仅纳入沪深主板 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260601-07 | 2026-06-01 | 策略 1 回测 v0 采用「有守卫的简化版」，QA 失败即触发升级到账户级 ledger | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260601-08 | 2026-06-01 | 指数可用性由 dim_index 承载，runner 必须校验 benchmark 窗口 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260602-01 | 2026-06-02 | 策略 1 回测 08 升级为账户级有状态 ledger（落地 DECISION-20260601-07） | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260602-02 | 2026-06-02 | OQ-006 单位契约作为 DWD 准入门禁 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260602-03 | 2026-06-02 | 财务三大报表 DWD/DWS 落地的实现口径 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260602-04 | 2026-06-02 | 策略 1 默认交易成本 profile | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260602-05 | 2026-06-02 | 策略 1 报告中文归因旧口径（已废弃） | superseded by DECISION-20260602-06 | archive/DECISION_LOG_2026-06.md |
| DECISION-20260602-06 | 2026-06-02 | 策略 1 报告基准分层与证据包治理口径 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260603-01 | 2026-06-03 | OQ-010 第一轮 A/B/C 参数实验采用分阶段非笛卡尔积口径 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260603-02 | 2026-06-03 | GCP 生产数据流水线采用 Cloud Run Jobs + Dataform + Cloud Composer | superseded by DECISION-20260608-20 | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-20 | 2026-06-08 | OQ-005 长期编排正式从 Cloud Composer 转为 `Cloud Scheduler + Cloud Workflows` | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260603-03 | 2026-06-03 | ODS Parquet schema 修复默认采用 GCS 原文件重写 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260603-04 | 2026-06-03 | OQ-010 实验并发调度与隔离采用 GCS 原子锁 + BigQuery 状态表 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260603-05 | 2026-06-03 | OQ-010 调度器参数注入和状态表历史必须硬门禁 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260604-01 | 2026-06-04 | OQ-010 先 Ledger P0/P1/P2 再月度滚动重训 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260604-02 | 2026-06-04 | OQ-010 因子贡献度分析不做消融实验 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260604-03 | 2026-06-04 | 策略 1 训练回测迁移为 Cloud Run Jobs | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260604-04 | 2026-06-04 | OQ-005 每日生产采集采用 current-scope 单 Job + 固定出口 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260605-01 | 2026-06-05 | OQ-005 Phase 2.0 用 warehouse_mode 显式区分每日与兼容全量转换 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260605-02 | 2026-06-05 | OQ-005 窗口刷新估值特征按实际观测推导读取边界 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260605-03 | 2026-06-05 | 策略执行层后续停止使用 BQML 与 SQL runner | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260606-01 | 2026-06-06 | OQ-005 先拆分 Composer DAG 边界再继续扩展生产调度 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260606-02 | 2026-06-06 | 策略 1 组合验收门先固定 10/20/30/40 持股数候选 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260606-03 | 2026-06-06 | 策略 1 验收门 v2 使用版本化共享契约 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260606-04 | 2026-06-06 | 策略 1 production acceptance 必须先切到整数手 ledger | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260607-01 | 2026-06-07 | dws_market_state_daily 采用备份表 + 双版本行承接上证指数补充 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-01 | 2026-06-08 | index benchmark QA 默认终点对齐 DWD 已可用日期 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-02 | 2026-06-08 | 策略 1 runner 与默认验收 benchmark 切换为上证指数 | unknown（归档原文无 Date / Status 字段） | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-24 | 2026-06-08 | OQ-005 长期编排层迁出 Cloud Composer | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-03 | 2026-06-08 | OQ-005 Workflows 实现必须显式补回 Airflow 免费语义 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-04 | 2026-06-08 | 策略 1 runner 与默认验收 benchmark 切换为上证指数 | unknown（归档原文无 Date / Status 字段） | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-05 | 2026-06-08 | benchmark 切换后的历史 replay 保留旧审计产物并使用新 run 身份 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-06 | 2026-06-08 | OQ-005 phase 1 采用薄 pipeline-control 服务承接 Workflows 公共能力 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-07 | 2026-06-08 | OQ-005 Workflows cutover 前必须先过最小锁测试与真实 qa_only/daily_current smoke | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-08 | 2026-06-08 | Composer 迁移期告警检查统一限频到每小时，airflow_monitoring 不单独调优 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-09 | 2026-06-08 | full_rebuild 保持默认不部署，Scheduler alert-check cutover 必须停 Composer checker | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-25 | 2026-06-08 | Strategy1 Cloud Run JSON 布尔特征解包必须使用 `BOOL -> INT64` | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-10 | 2026-06-08 | Strategy1 Cloud Run 布尔解包白名单仅限真实 JSON 布尔字段 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-11 | 2026-06-08 | 策略 1 验收门切换路线直接从 v1 到 v3，不经过 v2 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-12 | 2026-06-08 | 策略 1 v3 gate 的公式、符号与窗口约定必须在 PRD/contract 中显式冻结 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-13 | 2026-06-08 | OQ-005 alert checker cutover 改为 `Cloud Scheduler -> Workflows`，并废止旧的直连 Cloud Run scheduler 路径 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-14 | 2026-06-08 | Strategy1 v3 切门先以独立 contract 固化规则，不提前改 replay 或 live gate | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-15 | 2026-06-08 | Strategy1 v3 replay 必须作为独立只读 artifact 路径存在，不能覆盖历史 v1 结论 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-16 | 2026-06-08 | `ashare_pipeline_alert_checker` workflow 不写 `pipeline_run` / `pipeline_task_status` | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-17 | 2026-06-08 | `ashare_warehouse_full_rebuild` 改为 async BigQuery submit+poll，并继续保持 manual opt-in 部署 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-18 | 2026-06-08 | Strategy1 v3 replay / QA 对历史 search 缺失信号字段采用 source-derivable fallback，不回填 registry | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-19 | 2026-06-08 | OQ-005 跳过 shadow run，直接切到 Scheduler + Workflows 生产入口 | unknown（归档原文无 Date / Status 字段） | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-21 | 2026-06-08 | 首轮 sklearn native search 的 v3 replay 允许用 valid 证据代理缺失的 CV confirmation | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-22 | 2026-06-08 | Strategy1 v3 的 final_holdout 仅作诊断，不再作为 hard veto | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-26 | 2026-06-08 | Strategy1 v3 的 replay QA 必须由 contract-driven helper 执行 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-23 | 2026-06-08 | Strategy1 v3 replay QA 的业务口径必须完整从 contract 派生 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260608-30 | 2026-06-08 | `orchestration/composer/` 只保留为历史审计快照 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260609-01 | 2026-06-09 | Strategy1 Cloud Run live acceptance gate 切到 v3 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260609-02 | 2026-06-09 | 显式 backfill 可写入 2019 年以前历史训练窗口 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260610-01 | 2026-06-10 | dim_stock 历史生命周期用 ODS daily 首交易日兜底 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260610-02 | 2026-06-10 | core smoke 不再把 2019 作为 DWD 全表存在下限 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260610-03 | 2026-06-10 | Strategy1 旧 BQML-only 与 SQL ledger fallback 执行入口退役删除 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260610-04 | 2026-06-10 | Strategy1 回测新增复合年化字段且保留 legacy 年化语义 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260610-05 | 2026-06-10 | 项目结构重构采用 research/ADS 分层与稳定命名空间 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260610-06 | 2026-06-10 | Strategy1 年度滚动选参采用上一整年 valid 与 selected final refit | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260610-07 | 2026-06-10 | PR #136 一次性合并项目结构重构 Phase A/A2/B/C | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260610-08 | 2026-06-10 | Strategy1 research lifecycle 默认值与 D1 收尾验收门槛 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260610-09 | 2026-06-10 | Research 表契约变更必须同步 additive migration 和 readiness QA | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260610-10 | 2026-06-10 | Strategy1 普通实验默认写 research，ADS 只能显式 audit 或 promotion | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260610-11 | 2026-06-10 | Strategy1 promotion 必须显式 owner-approved，Phase E 领域逻辑迁入 package | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260610-12 | 2026-06-10 | Strategy1 普通 runner ADS 写权限暂按现状保留，依赖流程约束 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260610-13 | 2026-06-10 | 缺失本机/运行依赖可由 Agent 直接安装 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260611-01 | 2026-06-11 | 年度 final refit 使用 dedicated panel 与 effective coverage floor | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260611-02 | 2026-06-11 | 接受 annual effective-window 结果作为研究复盘口径 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260611-03 | 2026-06-11 | 关闭 OQ-012 ODS Parquet schema mismatch | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260612-01 | 2026-06-12 | BigQuery 数据集清理与退役口径 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260612-02 | 2026-06-12 | 采纳 true-five-year continuous 为研究 baseline，关闭 OQ-011 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260612-03 | 2026-06-12 | 研究 baseline 数字切换为 CA-on 口径，"未复权简化"约定 superseded，后续实验一律 CA-on | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260613-01 | 2026-06-13 | 否决验收契约 v4 提案本版：后续契约修订必须含长窗 MaxDD 硬门，v3 维持唯一有效契约 | active | archive/DECISION_LOG_2026-06.md |
| DECISION-20260613-02 | 2026-06-13 | topdown 自上而下整手构造路线收口（retained bug 修复后证伪 + 严格单票上限无效） | active | archive/DECISION_LOG_2026-06.md |

## 近期完整条目（最近 10 条，时间倒序）

## DECISION-20260613-02: topdown 自上而下整手构造路线收口（retained bug 修复后证伪 + 严格单票上限无效）

日期: 2026-06-13
状态: active
负责人: owner
Agent ID: Claude
模型: Claude Opus 4.8

### 背景

PRD_20260613_04 Phase 2 以 T0 / no-P1 口径执行 topdown 自上而下整手构造（`ledger_exec_v2_lot100_topdown`）。PR #217 在 live 执行中发现并修复一个灾难级 ledger 记账 bug：`build_daily_plan_topdown` 把 retained 持仓（rank ≤ walk_depth）`continue` 不放入 plan，而主循环 `update_holdings(plan)` 只从 plan 重建持仓，于是每个调仓日 retained 持仓被静默销毁（无 SELL、无现金回款）；`_v01` 的 `-99.95%` 系该 bug 所致、已作废。v1 非 topdown 分支把全部持仓纳入 universe，结构性免疫。修复后 `_v02`（research-only，外接 QA 四件套全过）给出干净结果：长窗 CAGR `11.96%` / contract Sharpe `0.3821` / Calmar `0.2104` / MaxDD `-56.85%` / 平均现金 `2.51%`，全维度劣于 v1 official baseline（`15.36%` / `0.6685` / `0.4103` / `-37.43%` / ~29% 现金）。PR #218 用只读 paper 探针（已验证 ≈ live，cap=None 复现 `_v02`）测试**严格** `max_single_weight` 单票上限：cap∈{0.20,0.15,0.10} 把最大单票压到 13-21%，但最好 Calmar 仅 `0.2018`（≈无上限 `0.2013`、仍是 v1 一半），MaxDD `-52%~-62%` 未改善，释放现金被再分配、平均现金仍 ~2.6%。

### 决策

owner 裁决（2026-06-13）：**topdown 自上而下整手构造路线收口，不再在该构造内迭代。**

1. topdown 经济价值在修复后的干净 `_v02` 中已被证伪（劣于 v1），严格单票上限也救不回——证伪不再是 bug artifact。
2. 现金拖累问题真实，但解法不是 topdown（满仓）：v1 的 ~30% 现金是回撤保险而非纯拖累，topdown 满仓丢了缓冲，故 Calmar 只有 v1 一半；topdown 深回撤是满仓小盘篮的系统性回撤，单票上限无能为力。下一步方向（待 owner 另批启动）= market-state 条件化现金/仓位管理，而非满仓 topdown。
3. topdown ledger 的 retained 持仓修复与新增 QA-TOPDOWN-11/12 持仓守恒断言作为长期防护保留；paper harness 的 `single_weight_cap` 作为 opt-in 研究开关保留（默认关闭，14 个既有 paper 单测仍过）。
4. 不 promotion、不标 accepted、不改默认构造 / 默认 profile / v1 语义。

### 理由

修复消除背离源后 paper（`11.81%`）与 live `_v02`（`11.96%`）吻合，topdown 劣于 v1 是真实经济结论；严格上限探针排除了"集中度可救"的反事实。

### 影响

1. PRD_20260611_10 topdown 构造与 PRD_20260613_04 Phase 2 收口；topdown v2 T0 不作为 accepted / promotion / 默认构造候选。
2. OQ-010 下 topdown 构造子路线关闭；alpha/组合改进转向 market-state 条件化现金管理、模型层 riskfeat 或独立 overlay。
3. 契约窗口语义修订（含 MaxDD 硬门，DECISION-20260613-01）仍是另一条待 owner 启动的线。

### 相关文件

`docs/分析-topdownPhase2三方对比-20260613.md`, `docs/分析-topdown单票上限探针-20260613.md`, `scripts/strategy1/analyze_topdown_lot_phase0.py`, `scripts/strategy1/analyze_topdown_single_weight_cap_probe.py`, `src/quant_ashare/strategy1/ledger.py`, PR #217, PR #218, `docs/prd/PRD_20260613_04_topdownPhase2T0口径修订与重跑.md`

## DECISION-20260613-01: 否决验收契约 v4 提案本版：后续契约修订必须含长窗 MaxDD 硬门，v3 维持唯一有效契约

日期: 2026-06-13
状态: active
负责人: owner
Agent ID: Claude
模型: Claude Fable 5

### 背景

PRD_20260613_05 基于 PR #211 的窗口敏感性证据提案 contract v4：验收窗钉死为"最近两完整自然年 + YTD"、Calmar/Sharpe 阈值不变、pure-index guard 固化、research/production 分级；其中长窗风险控制设计为软门——披露义务 + 长窗 MaxDD 深于 -45% 时 production-accept 须 owner 显式 sign-off。提案经 Codex review 收敛定稿（PR #214 合并），按 DECISION-20260608-12 冻结纪律交 owner 最终批准。

### 决策

owner 否决该版提案（2026-06-13，原话要点："先不采纳门构造的改造，至少不采纳这一版，因为最大回撤肯定要一个硬门"）：

1. v4 本版不实施；`model_acceptance_contract_v3.yml` 仍是唯一有效契约，v3 公式冻结纪律（DECISION-20260608-12）继续适用。
2. 否决理由具有规格效力：任何后续验收契约修订提案，长窗 MaxDD 必须设计为**硬门**（超阈值自动拒绝），不接受 owner sign-off 类软门替代。
3. PRD_20260613_05 标注否决状态后留档不删除——窗口语义缺陷（v3 未钉死评估窗，PR #211 证实）的证据与分析仍有效，是后续修订版的事实基础。
4. 是否/何时重提含 MaxDD 硬门的修订版（阈值与适用窗口是关键开放参数），由 owner 决定。

### 理由

owner 判断回撤控制是不可协商的验收底线：软门保留了"深回撤候选经人工放行通过"的制度化路径，与回撤底线的定位矛盾。

### 影响

1. 当前 baseline 判定不变：v3 口径下未过门（contract Sharpe `0.6685` / Calmar `0.4103`），五轮 replay 1 accepted / 24 rejected 历史结论不追溯改写。
2. PRD_20260613_04 Phase 2 报告不附加 v4 shadow 判定表（原文该项以"v4 若获批"为前提，前提失效）；Phase 2 预登记判读是构造对比，不受本决策影响，继续执行。
3. v4 实施物清单（contract v4 yml、acceptance 路由与 pure-index guard 实现、切换决策记录、判定报告）全部不启动。

### 相关文件

`docs/prd/PRD_20260613_05_验收契约v4窗口语义与Calmar门提案.md`, `configs/strategy1/model_acceptance_contract_v3.yml`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `TODO.md`

## DECISION-20260612-03: 研究 baseline 数字切换为 CA-on 口径，"未复权简化"约定 superseded，后续实验一律 CA-on

日期: 2026-06-12
状态: active
负责人: owner
Agent ID: Claude
模型: Claude Fable 5

### 背景

PRD_20260612_02（Ledger 分红送转记账修复）三阶段全部完成并通过逐阶段 review：Phase A DWD 事件表（双向 hfq 交叉校验，OQ-015 预演拦截 74 条经裁决机制化处理）、Phase B ledger `corporate_actions` 参数实现（11 接缝传播、默认逐字节回归）、Phase C true5y CA-on 重跑（execution `strategy1-backtest-report-job-dnt4b`，三套 QA 通过，ADS 反向 0 行）。六项偏差分解桥精确闭合（`unexplained_residual < 1e-9pp`），证明 Phase A 数据、Phase B 记账与 PR #194 独立测量三者一致。

### 决策

1. 策略 1 研究 baseline 数字切换为 **CA-on 口径**：backtest `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01`，锚点 compound CAGR=`15.35%`、v3 contract Sharpe=`0.6682`、contract Calmar=`0.4101`、平均现金分红税后入账（flat 10%）。true5y CA-off 与 effective-window 口径降级为历史参照。
2. DECISION_LOG 中 v1 ledger 验收决策所含"未复权口径、持有期除权简化"约定自本决策起 **superseded**（其余 v1 简化如不可交易腿 carry 语义不受影响）。
3. **后续所有策略实验一律 CA-on**：显式传 `corporate_actions=cash_div_and_split_v1` / `dividend_tax_mode=flat_10pct`；代码默认值保持 `none_v1` 不变（历史可复现性），纪律靠 run 参数与 QA 断言执行。
4. v3 gates 现状如实记录：contract Sharpe `0.6682 < 0.70`（距门 0.032）、Calmar `0.4101 < 1.0`——**baseline ≠ accepted、不得 promotion**；测量仪已修正，剩余缺口为真实 alpha/结构缺口（OQ-010 范畴）。

### 理由

预登记判据（PR #194 触发）与逐阶段验收全部满足；偏差桥闭合证明新口径可信。继续以漏记分红的数字为锚会让后续所有实验背上已知且已修复的测量偏差。

### 影响

PRD_20260611_10 Phase 2 及后续实验的对照基线与运行参数随之切换；对比旧 baseline 的历史结论标注口径；超额/IR 叙事需注意基准 000852 为价格指数（不含分红），跨口径对比时考虑全收益指数。

### 备选方案

- 维持 CA-off baseline：不采用——保留已修复的已知偏差无收益。
- 把代码默认值改为 CA-on：不采用——破坏历史 run 可复现性与默认逐字节回归承诺，纪律由参数+QA 承担即可。

### 相关文件

`docs/prd/PRD_20260612_02_策略1Ledger分红送转记账修复.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/MEMORY_INDEX.md`, `TODO.md`
## DECISION-20260612-02: 采纳 true-five-year continuous 为研究 baseline，关闭 OQ-011

日期: 2026-06-12
状态: active
负责人: owner
Agent ID: Claude
模型: Claude Fable 5

### 背景

DECISION-20260611-02 接受 effective-window annual final refit / continuous 作为研究复盘口径时已写明：该口径是当时 DWS 覆盖不足下的妥协，"若未来需要 true five-year evidence，另开专项修复 DWS/lookback 并重跑"。该专项即 PRD_20260611_06，现已完成并通过全部门禁：2010-2014 backfill、2015Q1 与 `2019-01-02..2019-04-02` repair、57 个早期 `daily_basic` 市值字段全空开市日补采、宽窗口 overlap parity（stock/DWD/DWS 9 表 `1e-8` 零 mismatch；index/market `1e-4` 元级容忍后零 mismatch）、`13_true5y` 覆盖 QA、2021-2024 true-five-year refit（`__true5y01` 非默认 suffix）四年 QA、true-five-year synthetic continuous 的 continuous / lot-aware QA 与 ADS 反向验证。

新结果（`s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01` / `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01`）：compound CAGR=`0.13852596798718442`、MaxDD=`-0.37189972934558946`、v3 contract Sharpe=`0.6075887294330015`、contract Calmar=`0.3724820349585642`，较 effective-window（`0.12036528993503204` / `-0.4548151193656952` / `0.5285475500566089` / `0.26464663290635254`）全面改善，但仍未通过 v3 hard gates。

### 决策

1. 自本决策起，**策略 1 的研究 baseline 切换为 true-five-year continuous**（上列 run/backtest id）；effective-window continuous 降级为历史参照口径。
2. 所有新实验（portfolio-only A/B、paper 原型、Phase 0/2 类重跑、复权漏损量化等）的 prediction 流与对照 backtest 一律解析为 true-five-year ids（从记忆解析，禁止硬编码）；报告须注明所用基线版本。
3. **baseline ≠ accepted**：true-five-year 仍未过 v3 双门，不得标 accepted、不得 promotion；KNOWN_CONSTRAINTS 既有 acceptance 约束原样保留。
4. 既有结论的迁移纪律：#179 / #181 / #186 / #190 等的**机制级结论**（信号真实性、long-only 悬崖、lot 现金拖累、P1 饱和、two_state 优于 hysteresis）视为结构性、可迁移；**数字级结论**保留为"旧 baseline 口径"证据，不批量重跑，引用时注明口径。
5. 关闭 OQ-011，移入 closed archive。

### 理由

采纳依据是**方法论性**的而非结果驱动：effective-window 是被数据覆盖约束被迫的口径，PRD_06 已用通过门禁的工程修复拆除了该约束，"为约束而设的口径"失去存在理由。结果改善方向（更完整训练面板 → 更好模型）与 DECISION-20260611-01（dedicated refit panel 使 CAGR 8.11%→12.04%）的既有证据自洽，比较本身是冻结候选、同流程、仅训练窗变长的干净 walk-forward。先于后续工作切换可避免每件在排队的事各自重锚一次。

### 影响

1. `OPEN_QUESTIONS.md` 仅剩 OQ-010。
2. 在排队工作的基线指向变更：PRD_20260611_10 §6 基线兼容条款生效（Phase 0 后续重跑切 true5y 流）；复权漏损量化需覆盖 true5y backtest；OQ-010 路线讨论以 true5y 指标为现状锚点。
3. 记忆中 effective-window 的锚定数字保留但身份变更为历史参照。

### 备选方案

- 维持 effective-window 为 baseline：不采用——其存在前提（覆盖约束）已被拆除，继续使用等于自愿保留已知的训练窗截断偏差。
- 双 baseline 并行：不采用——每个实验双跑成本翻倍，且"比较靶子唯一"是项目既有纪律。

### 相关文件

`.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/archive/CLOSED_QUESTIONS.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/MEMORY_INDEX.md`, `TODO.md`, `docs/prd/PRD_20260611_06_策略1历史数据回填与TrueFiveYearRefit.md`, `docs/prd/PRD_20260611_10_策略1自上而下整手组合构造.md`
## DECISION-20260612-01: BigQuery 数据集清理与退役口径

日期: 2026-06-12
状态: active
负责人: owner
Agent ID: Claude Code（quant-ashare 会话）
模型: Claude Fable 5

### 背景

2026-06-12 全数据集盘点确认：核心分层数据集与 `sql/` 契约双向零差异；遗留数据集 `ashare`（约 250.4 GiB、118 对象）为 2026-05-23~25 旧代仓库孤儿，仓库零引用、近 14 天无外部消费；`ashare_qa_windowed_equivalence` 为 windowed equivalence QA scratch（PRD_06 宽窗口 parity 验收已于 2026-06-11 完成）；`ads_ml_training_panel_daily` 含 12 个 `s1_bqml%` 旧 run 约 115 GB 可重建面板行；`ashare_meta` 有 5 张 `_repair_val_*` 泄漏外部表。

### 决策

1. 遗留数据集 `ashare` 硬删除：不导出、不归档；接受其中 BQML model `bqml_ml_stock_picker_baseline` 无恢复路径。删除前必须完成 Data Access 审计日志预检（lookback ≥30 天，补 `JOBS_BY_PROJECT` 跨 billing project 盲区），发现未知消费方即暂停报 owner。
2. `ashare_qa_windowed_equivalence` 硬删除（数据集一并删除）；`scripts/qa/run_windowed_refresh_equivalence.py` 与 `scripts/qa/run_index_market_windowed_equivalence.py` 退役删除，相关引用（tests/README/runbook/catalog ban-list）一并清理，KNOWN_CONSTRAINTS 对应两处硬门显式改写（窗口正确性此后由 `sql/qa/10` 窗口 QA 承担；true5y 重跑硬门收敛为 `13_true5y` + 逐年 refit panel coverage QA）。
3. `ashare_meta.tushare_api_catalog` / `tushare_api_params` 保留不删。
4. `ads_ml_training_panel_daily` 裁剪 `run_id LIKE 's1_bqml%'` 面板行（预期 12 run / 36,853,582 行）；`ads_model_registry`、`ads_model_prediction_daily`、全部回测事实表与 50 个 BQML model 保留，维持「BQML 仅作 reference/audit」的血缘完整性。
5. `ashare_backup` 长期保留；ODS 43 张当前 scope 外外部表保留（P1 扩展潜在输入、BQ 侧零成本）。
6. 第 1 类小清理（`ashare_meta` 5 张 `_repair_val_*` + `ashare_qa_windowed_equivalence` 18 张 shadow 表）即时执行，已于 2026-06-12 完成。

### 理由

盘点证实"乱"来自旧代遗留与 scratch 残留，而非当前分层设计；硬删除消除误用风险与心智负担（约 365 GB、月省约 8 美元为次要收益）。BQML 面板行可由 DWS + 已归档 SQL 确定性重建，删除不破坏 reference/audit 决策（DECISION 2026-06-05）所需的评分与交易事实。

### 影响

- KNOWN_CONSTRAINTS「双实现并存期间必须运行 windowed equivalence QA」与「true-five-year 重跑必须先过 overlap parity」两条随实现 PR 改写；未来大规模历史重写如需 parity，从 git history 恢复脚本另行评估。
- 回滚语义按对象区分（自助窗口均为 7 天，`maxTimeTravelHours=168`）：native 表（含已删 18 张 shadow 表、Phase C DML 删行）可在 time travel 内恢复（`FOR SYSTEM_TIME AS OF`，须 `--location=asia-east2` 并带分区过滤）；数据集级删除（`ashare`、`ashare_qa_windowed_equivalence`）可在窗口内 `UNDROP SCHEMA`，恢复命令必须显式指定原 location `asia-east2`；外部表（含已删 5 张 `_repair_val_*`、`ashare` 的 48 张）不受 time travel 覆盖，删除仅移除 BigQuery definition（GCS 数据无涉），恢复靠 DDL / git / 脚本重建；BQML model 不受 time travel 保护，删除即不可恢复。

### 备选方案

- `ashare` 转 GCS Coldline 归档后再删：不采用，owner 明确硬删除。
- 保留 equivalence QA 脚本仅删数据集：不采用，脚本默认依赖该 scratch 数据集且使命已完成，保留半套工具反增维护歧义。
- 面板按日期阈值（<2026-06-05）裁剪：不采用，按 `s1_bqml%` 家族裁剪语义更精确，避免误删同期 Cloud Run smoke run。

### 相关文件

`docs/prd/PRD_20260612_01_BigQuery数据集清理退役.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `TODO.md`, `scripts/qa/run_windowed_refresh_equivalence.py`, `scripts/qa/run_index_market_windowed_equivalence.py`, `configs/strategy1/active_step_catalog.yml`, `tests/strategy1/test_true5y_prd06_contracts.py`, `sql/README.md`, `docs/策略1CloudRun训练回测运行手册.md`
## DECISION-20260611-03: 关闭 OQ-012 ODS Parquet schema mismatch

日期: 2026-06-11
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5 Codex

### 背景

OQ-012 记录了 10 张 ODS 外部表历史上暴露的 Parquet schema mismatch：`ods_tushare_stk_limit` 属当前 P0 源表，其余 `daily_info/dividend/fina_audit/limit_list_d/margin/margin_detail/moneyflow/stk_rewards/sz_daily_info` 属 P1/P2/P3 扩展表。实现侧已经具备 schema contract、repair / validate 脚本和 `sql/qa/06_ods_parquet_schema_checks.sql`。2026-06-05 只读复核中，`06_ods_parquet_schema_checks.sql` 对 P0 与 all 范围均通过，`ods_tushare_stk_limit` 2019+ 可读行数为 10,662,140，当前 BigQuery 读层未再暴露 mismatch。

### 决策

1. 正式关闭 OQ-012，并从 `OPEN_QUESTIONS.md` 移入 closed archive。
2. 不再把 schema mismatch 作为当前阻塞问题或开放 owner 决策项。
3. 保留长期防复发约束：新增或修复 ODS Parquet 时，必须按 schema contract 显式 cast，并运行对应 QA。
4. 历史 raw 修复仍按 `PRD_20260603_04` 口径执行：默认从 GCS 原 Parquet 做 schema-preserving rewrite；API 重拉只作为原文件损坏、缺失、行数无法复原或 owner 明确要求的补救路径。

### 理由

当前生产读层已经无 mismatch 暴露，且防复发工具链和约束已落地。继续把 OQ-012 留在开放问题中只会制造优先级噪音；真正需要保留的是 schema contract / explicit cast / QA 的工程约束。

### 影响

1. `OPEN_QUESTIONS.md` 当前只保留仍需 owner 决策的问题。
2. `TODO.md` 中 OQ-012 收口项标记为已完成。
3. 后续新增 endpoint、修复历史 raw 或改 ingestion Parquet 写入逻辑时，仍必须遵守 `KNOWN_CONSTRAINTS.md` 中的 schema contract 和 QA 约束。

### 备选方案

- 继续保留 OQ-012 open，等待未来再确认：不采用，因为当前复核证据已足够关闭运行问题，防复发应作为长期约束而不是开放问题。
- 关闭 OQ-012 并删除防复发约束：不采用，因为 schema drift 是外部表高风险问题，必须保留 contract / cast / QA 门禁。

### 相关文件

`.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/archive/CLOSED_QUESTIONS.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/ARCHITECTURE_MEMORY.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `TODO.md`, `docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md`, `sql/qa/06_ods_parquet_schema_checks.sql`
## DECISION-20260611-02: 接受 annual effective-window 结果作为研究复盘口径

日期: 2026-06-11
状态: active
负责人: owner-delegated execution
Agent ID: Codex
模型: GPT-5 Codex

### 背景

PR #173 已合并并完成 live 重跑：2021-2026 dedicated refit panel、final refit、synthetic continuous merge、single continuous ledger 和 continuous QA 全部通过。该链路消除了旧 selection panel 的内部交易日缺口，但 2021-2024 refit 训练起点被 effective floor 截到 `2019-04-03`，不是名义完整五年窗口。最新 official continuous 指标为 compound annual return `0.12036528993503204`、max drawdown `-0.4548151193656952`、information ratio `0.5420201365046585`。只读复核显示 synthetic registry 仍为 `status='selected'` 且无 acceptance 状态；按 v3 contract 公式，contract Sharpe `0.5285475500566089 < 0.70`，Calmar `0.26464663290635254 < 1.0`。

### 决策

1. 接受当前 effective-window annual final refit / continuous ledger 作为本轮正式研究复盘与后续策略迭代的事实口径。
2. 暂不投入修复 / 重建 pre-2019 DWS lookback 与历史 valuation 覆盖来追求 true pre-2019 名义五年窗口。
3. 本结果不得标记为 accepted production baseline，不得 promotion 到 ADS；acceptance / promotion 仍必须另行按 contract 与 owner-approved promotion 流程完成。
4. 后续若需要 true five-year annual evidence，可重新打开专项 PRD / OQ，先修复 DWS/lookback 覆盖，再重跑 dedicated panel / refit / continuous。

### 理由

当前工程目标是完成年度 final refit 与 single continuous ledger 的可执行、可审计闭环。Effective-window 结果已经通过现有 refit 和 continuous QA，足以支持策略复盘和下一轮实验设计；但它既不是名义完整五年窗口，也未通过 v3 absolute performance gates，因此不应升级为 production accepted baseline。

### 影响

1. OQ-014 可关闭为“接受 effective-window 研究口径；不追求当前轮 true pre-2019 五年窗口”。
2. OQ-010 仍开放，下一步应基于 effective-window official continuous 指标做策略改进，而不是 promotion。
3. 记忆和 TODO 必须继续保留 caveat：2021-2024 不是名义完整五年 refit。

### 备选方案

- 立即修复 / 重建 DWS lookback 与历史 valuation 覆盖后重跑 true five-year：不采用，范围更大且不改变当前结果未通过 v3 acceptance 的事实。
- 将 effective-window 结果标为 accepted baseline：不采用，已实证 v3 contract Sharpe 和 Calmar 不达标，且 synthetic registry 没有 acceptance 状态。
- 完全废弃本轮结果：不采用，因为 dedicated panel / refit / continuous QA 均通过，作为研究复盘事实有效。

### 相关文件

`.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/archive/CLOSED_QUESTIONS.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/AGENT_HANDOFF.md`, `TODO.md`
## DECISION-20260611-01: 年度 final refit 使用 dedicated panel 与 effective coverage floor

日期: 2026-06-11
状态: active
负责人: owner-delegated execution
Agent ID: Codex
模型: GPT-5 Codex

### 背景

PR #171 后 review follow-up 审计确认：annual final refit 旧实现以 selection run panel 作为 `source_panel_run_id`，但 selection panel 在 refit 训练窗口内存在内部交易日缺口。2021/2022/2023 均缺 `2019-01-02..2019-04-02`，且多个年份还因 selection split / label-embargo 缺少年末开市日。进一步 BigQuery 审计显示，当前 DWS / sample 在 `2019-04-03` 之前仍有历史 valuation 稀疏和 `has_full_history_60d=FALSE` 约束；若使用 `max(nominal_refit_train_start, DATE '2019-04-03')` 作为 effective 起点，则 2021-2026 六年 effective refit train window 当前均可做到每个 SSE 开市日有 labeled sample。

### 决策

1. annual final refit 不再读取 selection run panel；每年在 select 之后新增 `build_refit_training_panel`，用 refit run_id 构建 dedicated refit panel。
2. `refit_register_predict --source-run-id` 继续指向 selection run，用于读取 selected candidate lineage；`--source-panel-run-id` 改为 refit run_id，用于读取 dedicated refit panel。
3. annual resolved plan 的 actual / effective final-refit 起点取 `max(nominal_refit_train_start, DATE '2019-04-03')`，并保留名义窗口与 `effective_final_refit_min_train_start` 元数据。
4. 该决策不关闭 OQ-014：2021-2024 结果只能解释为当前 DWS 覆盖下的 effective-window refit，不得宣称已完成名义完整五年 refit。
5. 若 owner 后续要求 true pre-2019 五年窗口，必须先修复 / 重建 DWS lookback 与历史 valuation 覆盖，再重跑 dedicated refit panel、refit 和 continuous ledger。

### 理由

该方案直接消除旧 selection panel 的 split / label-embargo 缺口，并让 refit QA 能按 dedicated refit panel 检查逐开市日覆盖。以 `2019-04-03` 作为显式 coverage floor，可在当前生产 DWS 数据质量边界内恢复可执行、可审计的年度 refit 链路，同时避免把缺失的历史覆盖伪装成完整五年训练。

### 影响

1. annual orchestrator resolved plan 增加 `build_refit_training_panel` step；pipeline scheduler 增加 `refit_panel:yYYYY` stage。
2. 2021-2024 refit 训练窗口被显式缩短到 `2019-04-03` 起；2025/2026 不受该 floor 影响。
3. 合并后必须重建 runner 镜像，并重跑 2021-2026 dedicated refit panel / refit / synthetic continuous，旧 official continuous 结果不能直接升级为 accepted baseline 或 promotion source。
4. PRD_02、KNOWN_CONSTRAINTS、OPEN_QUESTIONS、TODO 必须同步保留 effective-window caveat。

### 备选方案

- 继续用 selection panel：不采用，因为已实证存在内部缺口，且 refit QA 会失败。
- 立即修复 / 重建 DWS lookback 与历史 valuation 覆盖后再做 refit：暂不采用。原因是范围更大、成本更高，且当前任务目标是先恢复年度 refit 链路的可执行性与可审计性。
- 静默把 2021-2024 缩窗但不记录：不采用。原因是会污染 baseline 方法论解释。

### 相关文件

`scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`, `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`, `docs/prd/PRD_20260611_02_策略1年度滚动FinalRefit.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/AGENT_HANDOFF.md`, `TODO.md`
## DECISION-20260610-13: 缺失本机/运行依赖可由 Agent 直接安装

日期: 2026-06-10
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5 Codex

### 背景

Strategy1 长窗口训练 / 回测执行中曾因本机运行环境缺少 LightGBM 依赖库 `libomp.dylib` 阻塞。owner 已明确要求：后续执行项目任务时，若缺少必要本机或运行依赖，Agent 应直接安装最小必要依赖并继续，不再逐次询问。

### 决策

在本项目开发、数据、训练、回测、QA 或发布任务中，若缺失必要系统包、Python / Node 依赖、CLI 工具或运行时库，Agent 可直接安装最小必要依赖并继续任务，不需要额外征询 owner 确认。

### 理由

依赖安装属于执行环境准备。直接处理可减少长任务中断，并避免把可恢复的本机环境缺口升级为 owner 决策阻塞。

### 影响

1. 该授权不覆盖密钥、token、service account key、OAuth 凭据、个人隐私材料或未脱敏原始敏感日志。
2. 该授权不覆盖显著增加云成本、改变生产权限边界、生产 job spec / IAM 变更或破坏性数据操作；这些仍按既有安全约束和 owner 确认流程处理。
3. 安装事实可在交接或状态中记录安全摘要，但不得记录凭据值、原始 token、key 文件内容或个人隐私。

### 备选方案

每次缺依赖都暂停询问 owner；不采用，因为 owner 已明确要求后续直接安装必要依赖。

### 相关文件

`.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/AGENT_HANDOFF.md`
## DECISION-20260610-12: Strategy1 普通 runner ADS 写权限暂按现状保留，依赖流程约束

日期: 2026-06-10
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5 Codex

### 背景

PR #151 review follow-up 实证确认：五个普通 Strategy1 Cloud Run jobs 仍使用 `241358486859-compute@developer.gserviceaccount.com`，且 `ashare_ads` dataset 仍授予该 SA WRITER。代码和线上默认已经切到 research-first，正式 ADS 发布路径也已收敛为 owner-approved promotion job，但 IAM 层仍允许显式 ADS audit 模式直接写 ADS。直接 revoke 可能破坏 ADS audit / 历史报告重渲染等兼容路径，尤其是历史 summary `metrics_json` 回写。

### 决策

1. 接受现状但保留流程约束：五个普通 Strategy1 runner jobs 暂继续使用原 compute SA，且该 SA 暂保留 `ashare_ads` WRITER。
2. 不执行 live IAM revoke，不新增表级 ACL 或专用 audit SA。
3. 普通新实验仍必须默认写 `ashare_research`；ADS 正式发布仍只能通过 owner-approved promotion job。
4. 显式 `--output-dataset-role ads` / `dataset_role="ads"` 仅作为历史 ADS audit / 兼容路径，不得作为普通新实验写入路径。
5. 后续若要改为 IAM 硬隔离，必须先由 owner 重新决策，并设计 ADS audit / 历史报告重渲染的替代授权路径。

### 理由

该方案避免在未盘清 ADS audit 写入点前直接收权限造成历史报告重渲染或审计回写中断。当前默认 research-first、promotion job review-only / execute gate、promotion manifest 和 owner approval 已经形成流程边界；在无明确误用需求前，保持线上权限现状是最低风险的运维选择。

### 影响

1. OQ-013 关闭归档；不再作为阻塞项目结构重构的开放项。
2. `KNOWN_CONSTRAINTS.md` 继续要求普通实验默认 research-first，并禁止把显式 ADS role 当作普通新实验写入路径。
3. 未来 agent 不应“好心”直接 revoke 普通 runner 的 `ashare_ads` 写权限；如需硬隔离，必须重新提出方案并经 owner 批准。
4. 本决策不改变 promotion job 的治理边界；真实 ADS promotion 仍需 owner 指定 accepted research source 后先 review-only 再 `--execute`。

### 备选方案

- 收回普通 runner ADS WRITER，并为 ADS audit 做特批路径：暂不采用。原因是需要先拆出 audit / 历史报告重渲染入口，否则会破坏兼容路径。
- 表级或专用 SA 收窄 ADS 写权限：暂不采用。原因是实现与运维复杂度更高，且当前没有必须硬隔离的线上故障。

### 相关文件

`docs/prd/PRD_20260610_02_项目结构重构方案.md`, `docs/策略1ResearchPromotion运行手册.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/archive/CLOSED_QUESTIONS.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/AGENT_HANDOFF.md`, `TODO.md`
