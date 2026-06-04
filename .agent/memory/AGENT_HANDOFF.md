# Agent 交接（Agent Handoff）

本文件保存供后续 Agent 使用的最新交接记录。新交接用 `templates/HANDOFF_TEMPLATE.md` 追加到底部，并同步刷新下面的「当前交接摘要」。

> **语言约定（2026-06-01 起）**：新增交接条目一律用中文撰写；下方此前的英文历史条目保留原样作为记录，不回译。

## 当前交接摘要

`quant-ashare` 已完成 P0 DIM/DWD 物化、OQ-004 指数基准口径、策略 1 DWS/ADS、策略 1 BigQuery ML runner 端到端实跑、OQ-006 单位契约、OQ-003 财务三表 DWD/DWS、OQ-010 交易成本 profile、策略 1 中文报告与归因分析、策略 1 报告 GCS uploaded 模式、策略 1 模型质量诊断 PRD 及实现、策略 1 valid/test live-available 预测池口径修正 PRD 及实现，以及策略 1 分数方向校准 PRD 及实现。2026-06-02 已创建 `gs://ashare-artifacts`（`ASIA-EAST2`）、配置本机 ADC（quota project=`data-aquarium`）、去掉 `--skip-gcs-upload` 重跑 `render_report.py`，ADS 已回写 `report_upload_status=uploaded` 和真实 `report_uri`，`sql/ml/strategy1/10_qa_runner_outputs.sql` 全部通过。诊断 QA（`12`）已全部通过：PR #27/28 修复 `split_tag` 歧义（QA-DIAG-6 valid/test 日数校验通过），PR #29/30 实现 live-available 预测池口径（QA-POOL-1~6 全部通过），PR #32 实现 score orientation 校准（QA-ORIENT-DIAG-1 通过）。2026-06-03 已完成 livepool reverse-score shadow run（`s1_bqml_livepool_revscore_20260603_01`），验证反向后的 valid/test RankIC 转正且回测从亏损转为正收益（total_return=0.2787）；oriented run（`s1_bqml_livepool_oriented_20260603_01`）的 `12` QA 全部通过。已新增 `data_audit/` ODS/GCS 数据审查入口和 `data_audit/reports/` 报告目录，提示词限定本次只审查 2019-01-01 及之后的数据、只读不补数据，并要求审查 Agent 自行编写和维护审查脚本；提示词已补 Tushare 官方文档链接、API 返回行数打满单次上限时的截断风险检查，以及按 endpoint/主题拆脚本规则。OQ-005 GCP 数据流水线 PRD 已新增并按 owner 反馈收敛为陈述性目标实现方案：长期方案为 Cloud Run Jobs 采集 Tushare/Tinyshare→GCS Parquet，Dataform / BigQuery Studio pipeline 做 ODS→DIM/DWD/DWS/ADS，Cloud Composer 做全流程编排；首批每日生产采集只覆盖当前实际消费的 14 张 ODS，当前未消费 endpoint 进入后续接入池；PR #39 review 两条低优先级建议已补入财务 empty-return 口径和 Phase 1 Cloud Scheduler / Composer 触发入口；PR #42 分支已实现 Phase 0 采集 manifest、schema contract、meta 表 DDL 与采集脚本 stub，并整合 PR #44/#46 review 修复。已新增 OQ-012 ODS 外部表 Parquet schema 修复 PRD：10 张 2019+ schema mismatch 外部表按 GCS 原文件 schema-preserving rewrite 方案修复，API 重拉只作补救路径，当前 P0 源表 `ods_tushare_stk_limit` 优先；PR #40 review 建议已补入 backup write-once / `ok` 文件幂等跳过、临时 external table 显式 contract schema、INT→FLOAT64 `<2^53` 精度复核。核心规范保持：`sec_code` 主键、单位元/股、`ann_date_eff`/`visible_trade_date` PIT、后复权 `_hfq`、行业归属时点区间、血缘与版本字段、按月分区 + 聚簇；当前阶段先把 2019+ 数据做正确，2019 年以前正式样本/明细是下一步。

**已物化表**：`data-aquarium.ashare_meta` 下 `ods_field_unit_map`；`data-aquarium.ashare_dim` 下 `dim_trade_calendar`、`dim_stock`、`dim_stock_name_hist`、`dim_index`；`data-aquarium.ashare_dwd` 下 `dwd_stock_eod_price`、`dwd_stock_eod_valuation`、`dwd_fin_indicator`、`dwd_fin_indicator_latest`、`dwd_index_eod`，以及 OQ-003 财务三大报表 `dwd_fin_income`/`dwd_fin_balancesheet`/`dwd_fin_cashflow` 及各自 `_latest`（PR #13）；`data-aquarium.ashare_dws` 下策略 1 六表（universe、价格特征、估值特征、标签、特征宽表、样本表）和 `dws_stock_feature_fin_daily`（默认合并口径 PIT 财务特征，PR #13）；`data-aquarium.ashare_ads` 下 11 张训练/预测/组合/回测/监控契约表。PR #9 合并后的 `dim_stock` 依赖链已在 2026-06-02 重建：`dim_stock`、`dwd_stock_eod_price`、策略 1 DWS 六表和 ADS 契约表均已刷新，`sql/metadata/01_p0_table_column_descriptions.sql` 已执行，`sql/qa/01_p0_smoke_checks.sql` 与 `sql/qa/02_strategy1_dws_ads_checks.sql` 均通过；`sql/qa/03_oq004_index_checks.sql` 近期通过。二轮评审发现已修复：盘中临停不再误标全天停牌，财务 latest 改为 `update_flag DESC` 优先。P0 DIM/DWD 字段说明缺失数为 0。

**评审协议（2026-06-01 更新）**：评审已提交代码/SQL 或设计文档时，GitHub PR review 默认写 PR comment；一条写不下拆多条。只有 owner 明确要求或无 PR comment 承载面时，才另写 `docs/reviews/` 评审文档。评审只读——不擅改被评审对象、不把发现直接写进 `.agent/memory/**`/`TODO.md`，发现是否转 OQ/TODO/决策由 owner 定（AGENTS.md §六 / DECISION-20260601-03）。历史 `docs/reviews/P0-建表SQL-review.md` 等评审文档保留作审计记录。

**重要执行结果**：`dim_stock` 5,853 行，其中 326 个退市股使用 ODS `stock_basic_delist_date`；`dwd_stock_eod_price` 8,506,688 行；`dwd_stock_eod_valuation` 8,452,073 行；`dwd_fin_indicator` 332,960 行；`dwd_fin_indicator_latest` 198,030 行；`dim_index` 7 行；`dwd_index_eod` 11,922 行，其中 8,899 行有 `index_dailybasic` 估值/市值/股本字段，且沪深300已归一为 `sec_code='000300.SH'` / `source_sec_code='399300.SZ'`。`dim_index` 当前记录：SSE50、CSI300、STAR50、CSI1000、CSI500、深证成指、创业板指；`000852.SH` 可作收益 benchmark，但 `has_dailybasic=FALSE`。策略 1 DWS 行数：universe 8,506,688 行、价格特征 8,506,688 行、估值特征 8,452,073 行、标签 8,506,688 行、特征宽表 8,506,688 行、样本表 8,506,688 行（默认可训练 3,274,084 行）。上游已修复 `index_dailybasic` Parquet 类型问题，OQ-009 已关闭；STAR50/CSI1000 因 ODS 无 dailybasic endpoint 仍为空。2026-06-02 已应用 PR #9 的 ODS 正式退市日口径并完成依赖重建。

**DWS/ADS 设计与已落地范围**：P0 DWS 设计包含 `dws_stock_universe_daily`、价格/估值/财务特征、`dws_market_state_daily`、`dws_stock_label_daily`、`dws_stock_feature_daily_v0`、`dws_stock_sample_daily`；当前策略 1 已落地 universe、价格/估值特征、open-to-close 标签（rank/xs return 按默认 universe 截面计算）、特征宽表、样本表，以及 OQ-003 财务特征 `dws_stock_feature_fin_daily`；市场状态 `dws_market_state_daily` 待补。财务特征口径 PRD 已采纳、关闭并实现 OQ-003（PR #13）：P0 默认消费合并报表 `report_type='1'`，三大报表 DWD（`income/balancesheet/cashflow` + `_latest`）保留 `report_type`/`report_caliber`/`is_default_report_caliber`，`dws_stock_feature_fin_daily` 默认只过滤默认口径（口径契约 + `has_fin_*` 掩码），已物化并通过 `sql/qa/04_finance_caliber_checks.sql`，并按 OQ-006 单位契约补全 `ods_field_unit_map` 财务字段、跑通 `sql/qa/05_oq006_unit_checks.sql`。PR #4 comment 的 P1/P2 已跟进：`label_valid` 语义说明、去冗余 JOIN、最早可训练样本日 QA、DWD 字段名文档同步。P1 行业路径已可落地：`dim_stock_sw_industry_hist` 使用 `index_member_all`，`dim_stock_ci_industry_hist` 使用 `ci_index_member`，历史 join 用 `in_date/out_date`，`is_new` 仅标当前归属。P0 ADS 表契约已落地。策略 1 PRD 名称为 `ml_pv_clf_v0`；首个基线默认股票池仅沪深主板（`SSE_MAIN` / `SZSE_MAIN`），不含北交所、创业板、科创板；runner 设计 `docs/策略1-ml_pv_clf_v0-runner设计.md`、runner 实现 PRD `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md` 和 runner SQL 已完成，执行路径为 BigQuery ML + SQL：训练面板、BQML model object、预测、候选、组合、订单、回测、监控均写既有 ADS 表。**runner 已于 PR #12 端到端实跑并通过全部 QA**（08 已重写为账户级 ledger，详见本文件末尾 2026-06-02 交接条目与摘要顶部）。

**下一步（P0/P1）**：score orientation 校准已实现并验证（PR #32），live-available 预测池口径已实现并验证（PR #29/30），诊断 QA 全部通过。`docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md` 已由 PR #35 合并进入 `main`；OQ-010 首轮实验 runner 参数化、manifest、对比报告脚本、portfolio-only `prediction_run_id` 复用预测源路径和 horizon-aware 诊断/QA 已由 PR #37 合并进入 `main`。2026-06-04 PR #47 合并后 Stage C 已重跑通过；随后补齐 3*2*2*2 全因子网格缺失的 19 个组合，最终 24 个组合均通过 `12_qa_model_diagnosis_outputs`；同 stage dependency batching 与诊断状态语义修复已由 PR #48 合入 `main`。当前最优组合 `pv_fin_quality + 30/5% + biweekly + 5d` 已完成正式基线重训 run `s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01` / backtest `bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01`（2024-01-02 至 2025-12-31，benchmark=`000852.SH`，total_return=41.10%、excess_return=12.09%、Sharpe=1.043、max_drawdown=-14.48%，报告和诊断均 uploaded 到 GCS）。2026-06-04 已新增 `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md` 和 `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`，并进一步改造为 Ledger PRD 承接 P0 交易语义、P1 fixed-model 连续扩展回测（`2024-01-02` 至 `2026-04-30`）、P2 ledger state resume；月度重训 PRD 只定义模型生命周期和 prediction stream。2026-06-04 又新增 `docs/prd/PRD_20260604_03_策略1因子贡献度分析.md`：不做消融实验，只读当前 baseline，输出模型系数、单因子 RankIC/bucket lift、score contribution、组合因子暴露和归因 proxy。实现顺序建议为因子贡献度分析 → Ledger v1 P0/P1/P2 → 月度滚动重训；这只是顺序，不代表优先级高低。P1 再做三大报表单季 `q_*` 派生、行业/资金/事件特征扩展。关键参数：`@dwd_start_date = DATE '2019-01-01'`、`@fin_start_period = '20170101'`、`@lookback_start_date = DATE '2018-01-01'` 默认；后续应把 lookback 改为按最大滚动窗口计算，并决定是否补 lookback-capable 价格构建输入（OQ-011）。

**待 owner 确认 / 执行**：OQ-005 GCP 数据流水线后续 Cloud Run Jobs / Dataform / Composer 链路待实施；OQ-010 正式基线默认参数是否采纳，以及因子贡献度分析 → Ledger v1 P0/P1/P2 → 月度滚动重训的实现链路；是否补 lookback-capable 价格构建输入以填满 2019-01 起 60 日窗口（OQ-011）；按 OQ-012 PRD 实现 ODS Parquet schema 修复。OQ-001/OQ-003/OQ-004/OQ-006/OQ-007 已关闭。

**TODO / OQ 维护约定**：`TODO.md` 只保留下一步可执行事项和少量近期完成项；待 owner 决策的问题以 `.agent/memory/OPEN_QUESTIONS.md` 为唯一来源，TODO 仅引用 OQ 编号和对应行动。

**PR #45 最新修复（2026-06-03）**：OQ-010 并发调度 Phase 1 review follow-up 已修复：`run_oq010_experiments.py` 的 stale lock reclaim、heartbeat 和 release 均使用 GCS object generation 条件操作，避免并发调度器误删新锁；SQL `DECLARE p_* DEFAULT` 参数注入改为强校验，dry-run 会预检可执行实验，禁止静默沿用 SQL 默认 `run_id` / `backtest_id`；锁获取后的释放统一进 `finally`，heartbeat 线程停止后才写 `succeeded` / `failed`；状态表 DDL 改为 `CREATE TABLE IF NOT EXISTS` 保留 audit/resume 历史；状态表 DDL 与并发 QA 文件编号改为 `02` / `07` 避免冲突。验证已通过 Python `py_compile`、`git diff --check`、stage_a dry-run、单实验 dry-run、全 manifest dry-run 和直接参数注入断言；未执行 BigQuery。

**OQ-010 实跑与调度修复（2026-06-04）**：Stage C runner/QA 修复已由 PR #47 合并并完成重跑；3*2*2*2 全因子 24 组合已补齐。并发调度后续修复已由 PR #48 合并，解决同 stage dependency batching 和诊断状态/上传状态语义拆分问题。

**分支卫生**：PR 合并后，若 owner 未要求保留工作分支，应删除已合并且不再使用的 `codex/*` 本地分支和对应远端分支。`codex/implement-strategy1-prd` 和 `codex/implement-oq004-index` 已在本地和远端删除。

> 历史交接已归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-05.md` 和 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。常规启动只需阅读本文件的当前摘要和最近交接；归档仅用于审计追溯。

---

---

## 交接条目

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / factor attribution PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260604_03_策略1因子贡献度分析.md`。
- 明确本轮因子贡献度分析不做消融实验，不重训、不 drop factor，只读当前 baseline。
- 因子贡献度 PRD 定义模型系数/标准化系数、单因子 RankIC/bucket lift、score contribution、组合因子暴露、归因 proxy 和因子相关性/共线性摘要。
- 更新 Ledger PRD 和月度重训 PRD 的推荐实施顺序：因子贡献度分析 → Ledger v1 P0/P1/P2 → 月度滚动重训。
- 跟进 PR #51 comment，补充多重共线性解释边界：单因子系数排名不稳定、组级解读优先、单因子 RankIC 与多变量系数可能不一致、proxy 贡献不可跨相关因子加总。
- 新增 `DECISION-20260604-02` 并同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要。

### 重要上下文

- 因子贡献度分析只是实施顺序上的前置解释基准，不代表优先级高于 Ledger 或月度重训。
- 当前 PRD 已把高相关因子问题写成解释约束；实现时必须输出 `factor_correlation_summary.csv` 并在中文摘要提示共线性限制。
- P0 推荐实现为独立 `scripts/strategy1/attribute_factor_contribution.py`，产出 `factor_attribution/` artifact，再用 `14_qa_factor_attribution_outputs.sql` 验收。
- 若未来要做消融实验，需要另写 PRD；本 PRD 明确禁止把消融路径混进 P0。

### 改动文件

- `docs/prd/PRD_20260604_03_策略1因子贡献度分析.md`
- `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review 并合并因子贡献度 PRD。
- 合并后实现 `attribute_factor_contribution.py` 和 `14_qa_factor_attribution_outputs.sql`，先对正式 baseline 生成 factor attribution artifact。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / Ledger v1 PRD / monthly retrain PRD

### 已完成工作

- 按 owner 采纳的方案改造两篇 PRD：不新增第三篇 PRD。
- `PRD_20260604_01_策略1LedgerV1交易执行语义.md` 已扩展为 Ledger P0/P1/P2：P0 交易执行语义、P1 `2024-01-02` 至 `2026-04-30` fixed-model 连续扩展回测、P2 ledger state resume。
- `PRD_20260604_02_策略1月度滚动重训.md` 已收敛为只定义模型生命周期、失败回退和 PIT-safe prediction stream，并明确依赖 Ledger P0/P1/P2。
- 新增 `DECISION-20260604-01`，固化实现顺序为 Ledger v1 P0 → Ledger v1 P1 → Ledger v1 P2 → 月度滚动重训。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要。

### 重要上下文

- 2026 扩展回测和 resume 均归入 Ledger/backtest 执行能力，不归入月度重训。
- P1 扩展回测必须 fixed-model fresh-start 从 `2024-01-02` 连续跑到 `2026-04-30`；不能用只跑 2026 片段再简单拼接替代。
- 月度重训正式效果归因必须等 Ledger P0/P1/P2 稳定后再做。

### 改动文件

- `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 提 PR review 两篇 PRD 改造。
- PRD 合并后先实现 Ledger v1 P0 交易执行语义并用正式 baseline 参数 A/B。
- P0 稳定后再做 P1 fixed-model 扩展回测和 P2 resume；最后实现月度滚动重训。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`
---

日期: 2026-06-04
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / Ledger v1 PRD / monthly retrain PRD / memory cleanup

### 已完成工作

- 清理工作记忆：`AGENT_HANDOFF.md` 缩到当前摘要 + 最近 3 条交接，19 条旧交接归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。
- 新增 `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`。
- 新增 `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`。
- 跟进 PR #49 review comment，补充 Ledger PRD 的 T+1 卖出锁定非目标、月度重训 PRD 的 oriented RankIC 通过标准和 test split 事后评价口径。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要。

### 重要上下文

- Ledger v1 PRD 固化 t-1 信号 / t 开盘执行、pending sell 每日继续卖、实际持仓 netting、现金缩放、订单状态和每日 mark-to-market NAV；明确不改变模型训练/预测来源。
- 月度滚动重训 PRD 定义 monthly cadence、rolling 5 年训练窗口、12 个月 valid 窗口、月内固定模型、失败回退和 PIT-safe prediction stream。
- 实现顺序必须先 Ledger v1 A/B，再月度重训，避免交易执行语义变化和模型生命周期变化混在一起。

### 改动文件

- `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 提 PR review 两篇 PRD。
- PRD 合并后先实现 Ledger v1 交易执行语义，并用正式 baseline 参数 A/B。
- Ledger v1 A/B 收敛后，再实现月度滚动重训 prediction stream。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`
