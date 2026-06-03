# Agent 交接（Agent Handoff）

本文件保存供后续 Agent 使用的最新交接记录。新交接用 `templates/HANDOFF_TEMPLATE.md` 追加到底部，并同步刷新下面的「当前交接摘要」。

> **语言约定（2026-06-01 起）**：新增交接条目一律用中文撰写；下方此前的英文历史条目保留原样作为记录，不回译。

## 当前交接摘要

`quant-ashare` 已完成 P0 DIM/DWD 物化、OQ-004 指数基准口径、策略 1 DWS/ADS、策略 1 BigQuery ML runner 端到端实跑、OQ-006 单位契约、OQ-003 财务三表 DWD/DWS、OQ-010 交易成本 profile、策略 1 中文报告与归因分析、策略 1 报告 GCS uploaded 模式、策略 1 模型质量诊断 PRD 及实现、策略 1 valid/test live-available 预测池口径修正 PRD 及实现，以及策略 1 分数方向校准 PRD 及实现。2026-06-02 已创建 `gs://ashare-artifacts`（`ASIA-EAST2`）、配置本机 ADC（quota project=`data-aquarium`）、去掉 `--skip-gcs-upload` 重跑 `render_report.py`，ADS 已回写 `report_upload_status=uploaded` 和真实 `report_uri`，`sql/ml/strategy1/10_qa_runner_outputs.sql` 全部通过。诊断 QA（`12`）已全部通过：PR #27/28 修复 `split_tag` 歧义（QA-DIAG-6 valid/test 日数校验通过），PR #29/30 实现 live-available 预测池口径（QA-POOL-1~6 全部通过），PR #32 实现 score orientation 校准（QA-ORIENT-DIAG-1 通过）。2026-06-03 已完成 livepool reverse-score shadow run（`s1_bqml_livepool_revscore_20260603_01`），验证反向后的 valid/test RankIC 转正且回测从亏损转为正收益（total_return=0.2787）；oriented run（`s1_bqml_livepool_oriented_20260603_01`）的 `12` QA 全部通过。核心规范保持：`sec_code` 主键、单位元/股、`ann_date_eff`/`visible_trade_date` PIT、后复权 `_hfq`、行业归属时点区间、血缘与版本字段、按月分区 + 聚簇；当前阶段先把 2019+ 数据做正确，2019 年以前正式样本/明细是下一步。

**已物化表**：`data-aquarium.ashare_meta` 下 `ods_field_unit_map`；`data-aquarium.ashare_dim` 下 `dim_trade_calendar`、`dim_stock`、`dim_stock_name_hist`、`dim_index`；`data-aquarium.ashare_dwd` 下 `dwd_stock_eod_price`、`dwd_stock_eod_valuation`、`dwd_fin_indicator`、`dwd_fin_indicator_latest`、`dwd_index_eod`，以及 OQ-003 财务三大报表 `dwd_fin_income`/`dwd_fin_balancesheet`/`dwd_fin_cashflow` 及各自 `_latest`（PR #13）；`data-aquarium.ashare_dws` 下策略 1 六表（universe、价格特征、估值特征、标签、特征宽表、样本表）和 `dws_stock_feature_fin_daily`（默认合并口径 PIT 财务特征，PR #13）；`data-aquarium.ashare_ads` 下 11 张训练/预测/组合/回测/监控契约表。PR #9 合并后的 `dim_stock` 依赖链已在 2026-06-02 重建：`dim_stock`、`dwd_stock_eod_price`、策略 1 DWS 六表和 ADS 契约表均已刷新，`sql/metadata/01_p0_table_column_descriptions.sql` 已执行，`sql/qa/01_p0_smoke_checks.sql` 与 `sql/qa/02_strategy1_dws_ads_checks.sql` 均通过；`sql/qa/03_oq004_index_checks.sql` 近期通过。二轮评审发现已修复：盘中临停不再误标全天停牌，财务 latest 改为 `update_flag DESC` 优先。P0 DIM/DWD 字段说明缺失数为 0。

**评审协议（2026-06-01 更新）**：评审已提交代码/SQL 或设计文档时，GitHub PR review 默认写 PR comment；一条写不下拆多条。只有 owner 明确要求或无 PR comment 承载面时，才另写 `docs/reviews/` 评审文档。评审只读——不擅改被评审对象、不把发现直接写进 `.agent/memory/**`/`TODO.md`，发现是否转 OQ/TODO/决策由 owner 定（AGENTS.md §六 / DECISION-20260601-03）。历史 `docs/reviews/P0-建表SQL-review.md` 等评审文档保留作审计记录。

**重要执行结果**：`dim_stock` 5,853 行，其中 326 个退市股使用 ODS `stock_basic_delist_date`；`dwd_stock_eod_price` 8,506,688 行；`dwd_stock_eod_valuation` 8,452,073 行；`dwd_fin_indicator` 332,960 行；`dwd_fin_indicator_latest` 198,030 行；`dim_index` 7 行；`dwd_index_eod` 11,922 行，其中 8,899 行有 `index_dailybasic` 估值/市值/股本字段，且沪深300已归一为 `sec_code='000300.SH'` / `source_sec_code='399300.SZ'`。`dim_index` 当前记录：SSE50、CSI300、STAR50、CSI1000、CSI500、深证成指、创业板指；`000852.SH` 可作收益 benchmark，但 `has_dailybasic=FALSE`。策略 1 DWS 行数：universe 8,506,688 行、价格特征 8,506,688 行、估值特征 8,452,073 行、标签 8,506,688 行、特征宽表 8,506,688 行、样本表 8,506,688 行（默认可训练 3,274,084 行）。上游已修复 `index_dailybasic` Parquet 类型问题，OQ-009 已关闭；STAR50/CSI1000 因 ODS 无 dailybasic endpoint 仍为空。2026-06-02 已应用 PR #9 的 ODS 正式退市日口径并完成依赖重建。

**DWS/ADS 设计与已落地范围**：P0 DWS 设计包含 `dws_stock_universe_daily`、价格/估值/财务特征、`dws_market_state_daily`、`dws_stock_label_daily`、`dws_stock_feature_daily_v0`、`dws_stock_sample_daily`；当前策略 1 已落地 universe、价格/估值特征、open-to-close 标签（rank/xs return 按默认 universe 截面计算）、特征宽表、样本表，以及 OQ-003 财务特征 `dws_stock_feature_fin_daily`；市场状态 `dws_market_state_daily` 待补。财务特征口径 PRD 已采纳、关闭并实现 OQ-003（PR #13）：P0 默认消费合并报表 `report_type='1'`，三大报表 DWD（`income/balancesheet/cashflow` + `_latest`）保留 `report_type`/`report_caliber`/`is_default_report_caliber`，`dws_stock_feature_fin_daily` 默认只过滤默认口径（口径契约 + `has_fin_*` 掩码），已物化并通过 `sql/qa/04_finance_caliber_checks.sql`，并按 OQ-006 单位契约补全 `ods_field_unit_map` 财务字段、跑通 `sql/qa/05_oq006_unit_checks.sql`。PR #4 comment 的 P1/P2 已跟进：`label_valid` 语义说明、去冗余 JOIN、最早可训练样本日 QA、DWD 字段名文档同步。P1 行业路径已可落地：`dim_stock_sw_industry_hist` 使用 `index_member_all`，`dim_stock_ci_industry_hist` 使用 `ci_index_member`，历史 join 用 `in_date/out_date`，`is_new` 仅标当前归属。P0 ADS 表契约已落地。策略 1 PRD 名称为 `ml_pv_clf_v0`；首个基线默认股票池仅沪深主板（`SSE_MAIN` / `SZSE_MAIN`），不含北交所、创业板、科创板；runner 设计 `docs/策略1-ml_pv_clf_v0-runner设计.md`、runner 实现 PRD `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md` 和 runner SQL 已完成，执行路径为 BigQuery ML + SQL：训练面板、BQML model object、预测、候选、组合、订单、回测、监控均写既有 ADS 表。**runner 已于 PR #12 端到端实跑并通过全部 QA**（08 已重写为账户级 ledger，详见本文件末尾 2026-06-02 交接条目与摘要顶部）。

**下一步（P0/P1）**：score orientation 校准已实现并验证（PR #32），live-available 预测池口径已实现并验证（PR #29/30），诊断 QA 全部通过。`docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md` 已新增为 OQ-010 第一轮实验方案草案，待 owner review 后按矩阵实现实验参数化、manifest、对比报告，并执行持股数/权重、调仓频率、标签 horizon、财务特征实验。也可补 P0 通用 `dws_market_state_daily`。P1 再做三大报表单季 `q_*` 派生、行业/资金/事件特征扩展。关键参数：`@dwd_start_date = DATE '2019-01-01'`、`@fin_start_period = '20170101'`、`@lookback_start_date = DATE '2018-01-01'` 默认；后续应把 lookback 改为按最大滚动窗口计算，并决定是否补 lookback-capable 价格构建输入（OQ-011）。

**待 owner 确认**：dbt vs 纯 SQL（OQ-005）；P0 策略调仓频率、持股数/单票权重上限、特征/标签/选股口径实验（OQ-010，成本子项、报告实现、诊断、预测池口径和分数方向校准均已完成）；是否补 lookback-capable 价格构建输入以填满 2019-01 起 60 日窗口（OQ-011）。OQ-001/OQ-003/OQ-004/OQ-006/OQ-007 已关闭。

**TODO / OQ 维护约定**：`TODO.md` 只保留下一步可执行事项和少量近期完成项；待 owner 决策的问题以 `.agent/memory/OPEN_QUESTIONS.md` 为唯一来源，TODO 仅引用 OQ 编号和对应行动。

**分支卫生**：PR 合并后，若 owner 未要求保留工作分支，应删除已合并且不再使用的 `codex/*` 本地分支和对应远端分支。`codex/implement-strategy1-prd` 和 `codex/implement-oq004-index` 已在本地和远端删除。

> 历史交接已归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-05.md` 和 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。常规启动只需阅读本文件的当前摘要和最近交接；归档仅用于审计追溯。

---

## 交接条目

日期: 2026-06-03
Agent ID: Kimi
Agent 实例 ID: Kimi Code CLI
模型: Kimi-k2.6
运行环境: Kimi Code CLI
Run ID: s1_bqml_livepool_oriented_20260603_01 / s1_bqml_livepool_revscore_20260603_01
相关 issue/PR: gthbj/quant-ashare#27~#32 / 诊断 QA 修复 + livepool 口径 + score orientation

### 已完成工作

- 确认 `origin/main`（8564311）已包含并合并 PR #27/28（`split_tag` 歧义修复）、PR #29/30（live-available 预测池口径）、PR #32（score orientation 校准）。本地分支 `codex/fix-diagnosis-qa-livepool` 已与 `origin/main` 对齐。
- 验证 `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql` 全部断言通过（ oriented run_id `s1_bqml_livepool_oriented_20260603_01`）：QA-DIAG-1~5 诊断状态/版本/结论/置信度/产物清单通过；QA-DIAG-6 valid/test 各 >=100 预测交易日通过；QA-DIAG-7a~7c 预测/候选/回测存在性通过；QA-POOL-1~6 训练/预测池口径语义通过；QA-ORIENT-DIAG-1 `score_orientation` 登记通过。
- 2026-06-03 已完成 livepool reverse-score shadow run（`s1_bqml_livepool_revscore_20260603_01`）：复制 3,055,781 训练面板行，插入 1,056,716 条反向预测（score = 1.0 - source_score），完整执行 05→08→09→report→10→diagnosis→12，全部 QA 通过；shadow backtest total_return=0.2787（source run 为 -0.9712），验证方向反转可将策略从亏损转为正收益。
- 更新 `TODO.md`：将诊断 QA 修复、livepool 预测池口径、score orientation 校准标记为已完成。
- 更新 `IMPLEMENTATION_STATUS.md`：刷新「进行中」和「未开始」状态，明确 split_tag 修复、livepool 口径、score orientation 均已实现并验证。
- 更新 `OPEN_QUESTIONS.md`：刷新 OQ-010 状态，明确诊断、预测池口径和分数方向校准均已完成。
- 更新 `AGENT_HANDOFF.md` 当前交接摘要和待 owner 确认项。

### 重要上下文

- 当前 `main`（8564311）已是全量合并后的最新状态；`codex/fix-diagnosis-qa-livepool` 分支无代码改动，仅文档/记忆更新。
- `ads_model_prediction_daily` 当前仅有 oriented run（`s1_bqml_livepool_oriented_20260603_01`）的 1,056,716 行预测；source run 预测已被覆盖/清理。
- 诊断 QA 全部通过后，管线已具备：训练 → 选型（含方向校准）→ 预测（含 live-available 池）→ 候选 → 组合 → 回测 → 报告 → 诊断 → QA 验收的完整闭环。

### 改动文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`：全部 11 个 ASSERT successful + 1 条 manual_check 输出。
- shadow run 端到端验证：05→08→09→report→10→diagnosis→12 全部通过。

### 阻塞项

- 无。

### 下一步建议

- 合并本 PR（文档/记忆状态同步）。
- 由 owner 决策 OQ-010 剩余参数（调仓频率、持股数/单票权重上限）和模型质量迭代方向（特征/标签/选股口径实验）。
- 如需新一轮正式 run，使用新的 `run_id/backtest_id` 执行完整 01→12 流程。

### 已更新记忆文件

- `TODO.md`
- `IMPLEMENTATION_STATUS.md`
- `OPEN_QUESTIONS.md`
- `AGENT_HANDOFF.md`

---

## 交接条目

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-010 / 策略 1 首轮质量迭代实验 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`。
- PRD 将 OQ-010 剩余项拆为四阶段实验：组合集中度（持股数 / 单票权重）、调仓频率、标签 horizon、财务特征。
- PRD 固定当前 oriented run 为比较基线，并要求后续实现产出实验 manifest、独立 run/backtest、中文对比报告、10/12 QA 和诊断 artifact。
- 更新 `TODO.md`，把 OQ-010 下一步从“owner 决策”收敛为“按 PRD review 结果实现实验参数化与第一轮实验”。
- 更新 `OPEN_QUESTIONS.md`，记录首轮质量迭代 PRD 已新增、仍待 owner review。
- 更新 `MEMORY_INDEX.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md` 与当前交接摘要，清理旧的“诊断 QA 未通过 / 预测池待实现”表述。

### 重要上下文

- 本次只写 PRD 和记忆/TODO，未修改 runner SQL 或 Python。
- PRD 推荐第一轮继续使用 BigQuery ML `LOGISTIC_REG`，不切换模型族；股票池仍为沪深主板。
- PRD 推荐财务特征第一轮只加入比率、可用性和新鲜度字段，不加入原始金额字段，避免缺失和规模暴露直接污染预测池。

### 改动文件

- `docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`
- 文档 / 记忆更新，未执行 SQL。

### 阻塞项

- 无。

### 下一步建议

- owner review 首轮实验矩阵。
- 根据 review 结果实现实验参数化、manifest 和对比报告。
- 按阶段执行 OQ-010 第一轮实验，并用 10/12 QA 与诊断 artifact 验收。

### 已更新记忆文件

- `TODO.md`
- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`

---

## 交接条目

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: 记忆瘦身 / handoff 归档

### 已完成工作

- 按 `.agent/memory/UPDATE_PROTOCOL.md` 的归档规则，创建 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`。
- 将 `.agent/memory/AGENT_HANDOFF.md` 中较早的 2026-06 历史交接块迁入 6 月归档。
- 主 handoff 文件仅保留当前交接摘要、最近几段交接和本次清理交接，降低常规启动读取成本。

### 重要上下文

- 本次为记忆维护，不涉及 SQL、BigQuery 数据、策略逻辑或 PRD 内容变更。
- 历史交接仍可通过 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md` 审计追溯。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`

### 测试 / 验证

- `git diff --check`
- `wc -l .agent/memory/AGENT_HANDOFF.md .agent/memory/archive/AGENT_HANDOFF_2026-06.md`

### 阻塞项

- 无。

### 下一步建议

- 继续保持 `AGENT_HANDOFF.md` 只存摘要和最近 2-3 条交接；更早条目按月归档。

### 已更新记忆文件

- `AGENT_HANDOFF.md`
