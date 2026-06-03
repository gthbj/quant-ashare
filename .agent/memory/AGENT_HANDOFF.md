# Agent 交接（Agent Handoff）

本文件保存供后续 Agent 使用的最新交接记录。新交接用 `templates/HANDOFF_TEMPLATE.md` 追加到底部，并同步刷新下面的「当前交接摘要」。

> **语言约定（2026-06-01 起）**：新增交接条目一律用中文撰写；下方此前的英文历史条目保留原样作为记录，不回译。

## 当前交接摘要

`quant-ashare` 已完成 P0 DIM/DWD 物化、OQ-004 指数基准口径、策略 1 DWS/ADS、策略 1 BigQuery ML runner 端到端实跑、OQ-006 单位契约、OQ-003 财务三表 DWD/DWS、OQ-010 交易成本 profile、策略 1 中文报告与归因分析、策略 1 报告 GCS uploaded 模式、策略 1 模型质量诊断 PRD 及实现、策略 1 valid/test live-available 预测池口径修正 PRD 及实现，以及策略 1 分数方向校准 PRD 及实现。2026-06-02 已创建 `gs://ashare-artifacts`（`ASIA-EAST2`）、配置本机 ADC（quota project=`data-aquarium`）、去掉 `--skip-gcs-upload` 重跑 `render_report.py`，ADS 已回写 `report_upload_status=uploaded` 和真实 `report_uri`，`sql/ml/strategy1/10_qa_runner_outputs.sql` 全部通过。诊断 QA（`12`）已全部通过：PR #27/28 修复 `split_tag` 歧义（QA-DIAG-6 valid/test 日数校验通过），PR #29/30 实现 live-available 预测池口径（QA-POOL-1~6 全部通过），PR #32 实现 score orientation 校准（QA-ORIENT-DIAG-1 通过）。2026-06-03 已完成 livepool reverse-score shadow run（`s1_bqml_livepool_revscore_20260603_01`），验证反向后的 valid/test RankIC 转正且回测从亏损转为正收益（total_return=0.2787）；oriented run（`s1_bqml_livepool_oriented_20260603_01`）的 `12` QA 全部通过。已新增 `data_audit/` ODS/GCS 数据审查入口和 `data_audit/reports/` 报告目录，提示词限定本次只审查 2019-01-01 及之后的数据、只读不补数据，并要求审查 Agent 自行编写和维护审查脚本；提示词已补 Tushare 官方文档链接、API 返回行数打满单次上限时的截断风险检查，以及按 endpoint/主题拆脚本规则。OQ-005 GCP 数据流水线 PRD 已新增并按 owner 反馈收敛为陈述性目标实现方案：长期方案为 Cloud Run Jobs 采集 Tushare/Tinyshare→GCS Parquet，Dataform / BigQuery Studio pipeline 做 ODS→DIM/DWD/DWS/ADS，Cloud Composer 做全流程编排；首批每日生产采集只覆盖当前实际消费的 14 张 ODS，当前未消费 endpoint 进入后续接入池；PR #39 review 两条低优先级建议已补入财务 empty-return 口径和 Phase 1 Cloud Scheduler / Composer 触发入口；PR #42 分支已实现 Phase 0 采集 manifest、schema contract、meta 表 DDL 与采集脚本 stub，并整合 PR #44/#46 review 修复。已新增 OQ-012 ODS 外部表 Parquet schema 修复 PRD：10 张 2019+ schema mismatch 外部表按 GCS 原文件 schema-preserving rewrite 方案修复，API 重拉只作补救路径，当前 P0 源表 `ods_tushare_stk_limit` 优先；PR #40 review 建议已补入 backup write-once / `ok` 文件幂等跳过、临时 external table 显式 contract schema、INT→FLOAT64 `<2^53` 精度复核。核心规范保持：`sec_code` 主键、单位元/股、`ann_date_eff`/`visible_trade_date` PIT、后复权 `_hfq`、行业归属时点区间、血缘与版本字段、按月分区 + 聚簇；当前阶段先把 2019+ 数据做正确，2019 年以前正式样本/明细是下一步。

**已物化表**：`data-aquarium.ashare_meta` 下 `ods_field_unit_map`；`data-aquarium.ashare_dim` 下 `dim_trade_calendar`、`dim_stock`、`dim_stock_name_hist`、`dim_index`；`data-aquarium.ashare_dwd` 下 `dwd_stock_eod_price`、`dwd_stock_eod_valuation`、`dwd_fin_indicator`、`dwd_fin_indicator_latest`、`dwd_index_eod`，以及 OQ-003 财务三大报表 `dwd_fin_income`/`dwd_fin_balancesheet`/`dwd_fin_cashflow` 及各自 `_latest`（PR #13）；`data-aquarium.ashare_dws` 下策略 1 六表（universe、价格特征、估值特征、标签、特征宽表、样本表）和 `dws_stock_feature_fin_daily`（默认合并口径 PIT 财务特征，PR #13）；`data-aquarium.ashare_ads` 下 11 张训练/预测/组合/回测/监控契约表。PR #9 合并后的 `dim_stock` 依赖链已在 2026-06-02 重建：`dim_stock`、`dwd_stock_eod_price`、策略 1 DWS 六表和 ADS 契约表均已刷新，`sql/metadata/01_p0_table_column_descriptions.sql` 已执行，`sql/qa/01_p0_smoke_checks.sql` 与 `sql/qa/02_strategy1_dws_ads_checks.sql` 均通过；`sql/qa/03_oq004_index_checks.sql` 近期通过。二轮评审发现已修复：盘中临停不再误标全天停牌，财务 latest 改为 `update_flag DESC` 优先。P0 DIM/DWD 字段说明缺失数为 0。

**评审协议（2026-06-01 更新）**：评审已提交代码/SQL 或设计文档时，GitHub PR review 默认写 PR comment；一条写不下拆多条。只有 owner 明确要求或无 PR comment 承载面时，才另写 `docs/reviews/` 评审文档。评审只读——不擅改被评审对象、不把发现直接写进 `.agent/memory/**`/`TODO.md`，发现是否转 OQ/TODO/决策由 owner 定（AGENTS.md §六 / DECISION-20260601-03）。历史 `docs/reviews/P0-建表SQL-review.md` 等评审文档保留作审计记录。

**重要执行结果**：`dim_stock` 5,853 行，其中 326 个退市股使用 ODS `stock_basic_delist_date`；`dwd_stock_eod_price` 8,506,688 行；`dwd_stock_eod_valuation` 8,452,073 行；`dwd_fin_indicator` 332,960 行；`dwd_fin_indicator_latest` 198,030 行；`dim_index` 7 行；`dwd_index_eod` 11,922 行，其中 8,899 行有 `index_dailybasic` 估值/市值/股本字段，且沪深300已归一为 `sec_code='000300.SH'` / `source_sec_code='399300.SZ'`。`dim_index` 当前记录：SSE50、CSI300、STAR50、CSI1000、CSI500、深证成指、创业板指；`000852.SH` 可作收益 benchmark，但 `has_dailybasic=FALSE`。策略 1 DWS 行数：universe 8,506,688 行、价格特征 8,506,688 行、估值特征 8,452,073 行、标签 8,506,688 行、特征宽表 8,506,688 行、样本表 8,506,688 行（默认可训练 3,274,084 行）。上游已修复 `index_dailybasic` Parquet 类型问题，OQ-009 已关闭；STAR50/CSI1000 因 ODS 无 dailybasic endpoint 仍为空。2026-06-02 已应用 PR #9 的 ODS 正式退市日口径并完成依赖重建。

**DWS/ADS 设计与已落地范围**：P0 DWS 设计包含 `dws_stock_universe_daily`、价格/估值/财务特征、`dws_market_state_daily`、`dws_stock_label_daily`、`dws_stock_feature_daily_v0`、`dws_stock_sample_daily`；当前策略 1 已落地 universe、价格/估值特征、open-to-close 标签（rank/xs return 按默认 universe 截面计算）、特征宽表、样本表，以及 OQ-003 财务特征 `dws_stock_feature_fin_daily`；市场状态 `dws_market_state_daily` 待补。财务特征口径 PRD 已采纳、关闭并实现 OQ-003（PR #13）：P0 默认消费合并报表 `report_type='1'`，三大报表 DWD（`income/balancesheet/cashflow` + `_latest`）保留 `report_type`/`report_caliber`/`is_default_report_caliber`，`dws_stock_feature_fin_daily` 默认只过滤默认口径（口径契约 + `has_fin_*` 掩码），已物化并通过 `sql/qa/04_finance_caliber_checks.sql`，并按 OQ-006 单位契约补全 `ods_field_unit_map` 财务字段、跑通 `sql/qa/05_oq006_unit_checks.sql`。PR #4 comment 的 P1/P2 已跟进：`label_valid` 语义说明、去冗余 JOIN、最早可训练样本日 QA、DWD 字段名文档同步。P1 行业路径已可落地：`dim_stock_sw_industry_hist` 使用 `index_member_all`，`dim_stock_ci_industry_hist` 使用 `ci_index_member`，历史 join 用 `in_date/out_date`，`is_new` 仅标当前归属。P0 ADS 表契约已落地。策略 1 PRD 名称为 `ml_pv_clf_v0`；首个基线默认股票池仅沪深主板（`SSE_MAIN` / `SZSE_MAIN`），不含北交所、创业板、科创板；runner 设计 `docs/策略1-ml_pv_clf_v0-runner设计.md`、runner 实现 PRD `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md` 和 runner SQL 已完成，执行路径为 BigQuery ML + SQL：训练面板、BQML model object、预测、候选、组合、订单、回测、监控均写既有 ADS 表。**runner 已于 PR #12 端到端实跑并通过全部 QA**（08 已重写为账户级 ledger，详见本文件末尾 2026-06-02 交接条目与摘要顶部）。

**下一步（P0/P1）**：score orientation 校准已实现并验证（PR #32），live-available 预测池口径已实现并验证（PR #29/30），诊断 QA 全部通过。`docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md` 已由 PR #35 合并进入 `main`；OQ-010 首轮实验 runner 参数化、manifest、对比报告脚本、portfolio-only `prediction_run_id` 复用预测源路径和 horizon-aware 诊断/QA 已由 PR #37 合并进入 `main` 并通过 dry-run。2026-06-03 已配置本机 BigQuery Storage API 客户端并修复诊断脚本大 DataFrame 拉取不稳定问题；A0（`oq010_a0_n5_w20`）已端到端跑通 01-12，`10`/`12` QA 通过，诊断 artifact 已上传 GCS。OQ-010 同阶段实验并发调度已用于 Stage C 三个 retrain 实验并发实跑；当前 Stage C 已跑到 09，但 10 QA 暴露 runner 顺序和预测幂等边界问题。下一步是合并 `codex/fix-oq010-stage-c-runner-qa` 后用 `--force-replace` 重跑 Stage C，并完成 report、10 QA、diagnosis 和 12 QA；阶段 A/B/C 基础路径按 `4 + 3 + 3 = 10` 分阶段跑，包含阶段 D 为 12 个实验，不做 `4 * 3 * 3` 笛卡尔积，必要时补最多 `2 * 2` A/B、A/C、B/C pairwise 复核或最多 `2 * 2 * 2` 最终保底复核。阶段 A 的 `30/5%` 表示目标持股 30 只、单票权重上限 5%，目标单票等权约 3.33%，实际入选不足时剩余现金保留；A1-A3/B0-B2 为组合层实验，复用预测源并只重跑 05-12。也可补 P0 通用 `dws_market_state_daily`。P1 再做三大报表单季 `q_*` 派生、行业/资金/事件特征扩展。关键参数：`@dwd_start_date = DATE '2019-01-01'`、`@fin_start_period = '20170101'`、`@lookback_start_date = DATE '2018-01-01'` 默认；后续应把 lookback 改为按最大滚动窗口计算，并决定是否补 lookback-capable 价格构建输入（OQ-011）。

**待 owner 确认 / 执行**：OQ-005 GCP 数据流水线后续 Cloud Run Jobs / Dataform / Composer 链路待实施；P0 策略调仓频率、持股数/单票权重上限、特征/标签/选股口径实验（OQ-010，成本子项、报告实现、诊断、预测池口径、分数方向校准和并发调度 Phase 1 均已完成）；是否补 lookback-capable 价格构建输入以填满 2019-01 起 60 日窗口（OQ-011）；按 OQ-012 PRD 实现 ODS Parquet schema 修复。OQ-001/OQ-003/OQ-004/OQ-006/OQ-007 已关闭。

**TODO / OQ 维护约定**：`TODO.md` 只保留下一步可执行事项和少量近期完成项；待 owner 决策的问题以 `.agent/memory/OPEN_QUESTIONS.md` 为唯一来源，TODO 仅引用 OQ 编号和对应行动。

**PR #45 最新修复（2026-06-03）**：OQ-010 并发调度 Phase 1 review follow-up 已修复：`run_oq010_experiments.py` 的 stale lock reclaim、heartbeat 和 release 均使用 GCS object generation 条件操作，避免并发调度器误删新锁；SQL `DECLARE p_* DEFAULT` 参数注入改为强校验，dry-run 会预检可执行实验，禁止静默沿用 SQL 默认 `run_id` / `backtest_id`；锁获取后的释放统一进 `finally`，heartbeat 线程停止后才写 `succeeded` / `failed`；状态表 DDL 改为 `CREATE TABLE IF NOT EXISTS` 保留 audit/resume 历史；状态表 DDL 与并发 QA 文件编号改为 `02` / `07` 避免冲突。验证已通过 Python `py_compile`、`git diff --check`、stage_a dry-run、单实验 dry-run、全 manifest dry-run 和直接参数注入断言；未执行 BigQuery。

**Stage C runner/QA 修复分支（2026-06-04）**：Stage C 三个 retrain 实验已跑到 09，但 10 QA 暴露 runner 顺序和预测表幂等问题。分支 `codex/fix-oq010-stage-c-runner-qa` 已修复：补 `google.cloud.bigquery` import、调度顺序改为 `09 -> render_report -> 10 QA`、`04_predict_daily` 按 `run_id` 清理/阻断既有预测，`10_qa_runner_outputs` 新增预测表 `(predict_date, sec_code)` 唯一性断言。已通过 Python `py_compile`、`git diff --check`、Stage C manifest dry-run 和 `04`/`10` BigQuery dry-run。合并后需用 `--force-replace` 重跑 Stage C。

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
Run ID: stage_c resolved manifest `oq010_stage_c_resolved_20260603_01`
相关 issue/PR: OQ-010 / Stage C runner QA fix

### 已完成工作

- 修复 `scripts/strategy1/run_oq010_experiments.py` 缺少 `google.cloud.bigquery` import，避免写状态表时 `name 'bigquery' is not defined`。
- 修复 OQ-010 调度顺序：`render_report.py` 现在排在 `10_qa_runner_outputs.sql` 之前，符合 README 和 QA 对 report 状态回写的要求。
- 修复 `sql/ml/strategy1/04_predict_daily.sql` 幂等边界：`p_force_replace` 和非 force 存在性检查均按 `run_id` 处理预测，避免同一 run 重训后旧 `model_id` 预测残留。
- 在 `sql/ml/strategy1/10_qa_runner_outputs.sql` 新增预测表 `(predict_date, sec_code)` 唯一性断言。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要。

### 重要上下文

- Stage C 的 C0/C1/C2 已跑到 09；当前失败不是策略结果结论，而是 runner/QA 执行链问题。
- C0 的 `rank_raw=1` 重复由同一 `run_id` 下旧模型预测残留触发；修复后需重新生成预测和下游结果。
- C1/C2 的 report QA 失败由 runner 把 `10_qa_runner_outputs` 放在 `render_report.py` 前触发。

### 改动文件

- `scripts/strategy1/run_oq010_experiments.py`
- `sql/ml/strategy1/04_predict_daily.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`

### 测试 / 验证

- `/Users/luna/miniconda3/bin/python -m py_compile scripts/strategy1/run_oq010_experiments.py`
- `git diff --check`
- Stage C resolved manifest dry-run with `--force-replace --max-parallel 3 --max-parallel-backtest 3`
- BigQuery dry-run: `sql/ml/strategy1/04_predict_daily.sql`
- BigQuery dry-run: `sql/ml/strategy1/10_qa_runner_outputs.sql`

### 阻塞项

- 无代码阻塞；PR 合并后仍需重跑 Stage C 才能判断实验结果。

### 下一步建议

- 合并本修复 PR 后，使用 resolved Stage C manifest 和 `--force-replace` 重跑 C0/C1/C2，完成 report、10 QA、diagnosis 和 12 QA。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #42 / PR #44 / PR #46 / OQ-005

### 已完成工作

- 为合并 PR #42，将最新 `origin/main` 合入 `feat/gcp-pipeline-phase0`，解决 `.agent/memory/**` 与 `TODO.md` 冲突。
- 保留 `main` 已新增的 OQ-010 并发调度 Phase 1 状态和文件，同时补回 OQ-005 Phase 0 实现分支状态。
- 记录 PR #44 已合入 #42；PR #46 因冲突已手动整合其有效修复并关闭。
- 同步 `TODO.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要。

### 重要上下文

- OQ-005 仍为 open。当前只完成 Phase 0 采集侧基础代码与 review 修复，Cloud Run Jobs、Dataform P0 转换和 Composer DAG 仍待后续实现。
- `endpoint` 是 Tushare API endpoint，`partition_endpoint` 是 GCS Hive 分区 `endpoint=` 值；`stock_basic` 变体必须用后者分开写入，避免下游 `dim_stock` 消费不到 listed/delisted 分区。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

### 测试 / 验证

- `git diff --check`
- `git diff --cached --check`
- conflict marker scan
- PR #42 mergeability check

### 阻塞项

- 无。

### 下一步建议

- 合并 PR #42 后继续实现 Cloud Run Jobs 镜像/任务、Dataform P0 转换、Composer DAG 与端到端 dry-run。

---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #45 / issuecomment-4612729919 / OQ-010

### 已完成工作

- 跟进 PR #45 最新 review comment `issuecomment-4612729919`，直接修复并发调度 Phase 1 实现。
- 将 SQL `DECLARE p_* DEFAULT` 参数注入改为强校验：扫描所有可注入参数，缺少 manifest/default 值、格式不匹配、类型不匹配或必需隔离参数缺失时直接失败。
- dry-run 新增可执行实验 SQL 参数注入预检；blocked placeholder 实验仅打印计划，不用 placeholder 做类型预检。
- 锁释放改为获取 GCS lock 后统一 `finally` 释放；`running` 状态写失败、step 执行失败或异常均不会泄漏 GCS lock。
- heartbeat 线程改为非 daemon，step 结束后先停止并 join，再写 `succeeded` / `failed`，避免 heartbeat 后写 `running` 覆盖 terminal status。
- 状态表 DDL 从 `CREATE OR REPLACE TABLE` 改为 `CREATE TABLE IF NOT EXISTS`，保留 audit/resume 历史。
- 文件编号避冲突：状态表 DDL 使用 `sql/meta/02_strategy1_experiment_run_status.sql`；并发 QA 使用 `sql/qa/07_strategy1_experiment_concurrency_checks.sql`，并同步文档/记忆/TODO 引用。

### 重要上下文

- 本次没有执行 BigQuery 实验、没有触碰正在运行的 A3 实验、没有删除或覆盖 `reports/strategy1` 已有产物。
- 状态表仍只用于审计和 resume 输入；GCS object generation 条件操作仍是锁安全边界。
- 后续若再调整 SQL runner，必须保持 dry-run 参数注入预检，否则会重新暴露静默沿用默认 `run_id` / `backtest_id` 的风险。

### 改动文件

- `scripts/strategy1/run_oq010_experiments.py`
- `sql/meta/02_strategy1_experiment_run_status.sql`
- `sql/qa/07_strategy1_experiment_concurrency_checks.sql`
- `docs/策略1实验并发调度器运行手册.md`
- `docs/prd/PRD_20260603_05_策略1实验并发调度与隔离.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/run_oq010_experiments.py`
- `python3 scripts/strategy1/run_oq010_experiments.py --dry-run --stage-id stage_a`
- `python3 scripts/strategy1/run_oq010_experiments.py --dry-run --experiment-id oq010_a1_n10_w10`
- `python3 scripts/strategy1/run_oq010_experiments.py --dry-run`
- 直接参数注入断言：确认 `05_build_candidates.sql` 的 `p_run_id` 被替换为实验 run_id，未保留 SQL 默认值。
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 等 PR #45 合并后再按 owner 决定是否在真实 OQ-010 实验中启用并发；首次实跑仍建议 `max_parallel_backtest=1`。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`（追加 `DECISION-20260603-05`，并同步本 PR 内改名后的文件路径引用）
- `.agent/memory/OPEN_QUESTIONS.md`（仅同步本 PR 内改名后的文件路径引用）
- `TODO.md`

---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #41 / issuecomment-4612007495 / OQ-010

### 已完成工作

- 跟进 PR #41 review comment `issuecomment-4612007495`。
- 将策略 1 实验并发调度与隔离 PRD 从 `_04_` 改名为 `_05_`，避免与已合并 PR #40 的 `PRD_20260603_04_ODS外部表ParquetSchema修复.md` 撞号。
- rebase 到当前 `origin/main`，保留 #40 的 ODS schema 修复记忆/TODO，并重新接入 OQ-010 并发 PRD 状态。
- 在 PRD 第 6 章补充真实原子锁获取机制：P0 推荐 GCS object `ifGenerationMatch=0` create-if-not-exists，BigQuery 状态表只做审计和 resume 输入。
- 在 PRD 中补充 `lock_owner`、`lock_acquired_at`、`lock_expires_at`、`last_heartbeat_at`、lease TTL、heartbeat、stale lock reclaim 和多调度器约束。
- 在调度器设计中补充 `--scheduler-instance-id`、`--lock-ttl-minutes` 和后续 Cloud Composer / Airflow 映射。
- 同步 `TODO.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`KNOWN_CONSTRAINTS.md`、`OPEN_QUESTIONS.md`、`MEMORY_INDEX.md` 和当前交接摘要。

### 重要上下文

- 本次仍只修订 PRD 和记忆/TODO，未修改 SQL runner、未执行 BigQuery、未触碰正在运行的 A3 实验，也未改 `reports/strategy1`。
- 当前 runner 仍遵守“不并发”约束；PRD 合并不等于允许并发，必须等状态表、GCS 原子锁、调度器和并发 QA 实现并验收后再启用。

### 改动文件

- `docs/prd/PRD_20260603_05_策略1实验并发调度与隔离.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/PROJECT_CONTEXT.md`

### 测试 / 验证

- `git diff --check`
- `git diff --cached --check`
- conflict marker scan
- PRD 编号复核

### 阻塞项

- 无。

### 下一步建议

- 合并 PR #41。
- 后续实现 `ashare_meta.strategy1_experiment_run_status`、GCS lock、`scripts/strategy1/run_oq010_experiments.py`、runner 参数接口和 `sql/qa/07_strategy1_experiment_concurrency_checks.sql`。

---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #40 / issuecomment-4611909699 / OQ-012

### 已完成工作

- 跟进 PR #40 review comment `issuecomment-4611909699` 的 1 个 P2 和 2 个 P3 建议。
- 在 `docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md` 补充 backup write-once 规则：每个 `(endpoint, partition_date, source_uri)` 已存在 backup 时不得覆盖，重复执行只记录 `backup_status='existing'`。
- 在 Phase 0 / 发布规则中补充 `ok` 文件跳过重写、跳过发布，保证修复脚本幂等。
- 在临时 BigQuery external table QA 中补充 schema 必须显式取自 schema contract，禁止 autodetect。
- 在类型策略 / 风险控制中补充 INT→FLOAT64 仅对 `<2^53` 整数无损，超阈值字段进入 `manual_review`。
- 同步 `DECISION_LOG.md`、`KNOWN_CONSTRAINTS.md`、`IMPLEMENTATION_STATUS.md`、`TODO.md` 和当前交接摘要。

### 重要上下文

- PR #40 review 结论为可以合并，无阻断项。
- 本次仍只修订 PRD 和记忆/TODO，未修改 GCS、BigQuery ODS 外部表或生产数据。

### 改动文件

- `docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`

### 测试 / 验证

- `git diff --check`
- `git diff --cached --check`
- conflict marker / credential keyword scan

### 阻塞项

- 无。

### 下一步建议

- 合并 PR #40。
- 合并后实现 schema contract、repair manifest 和 `ods_tushare_stk_limit` staging 修复验证。

### 已更新记忆文件

- `TODO.md`
- `AGENT_HANDOFF.md`
- `DECISION_LOG.md`
- `IMPLEMENTATION_STATUS.md`
- `KNOWN_CONSTRAINTS.md`

---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-012 / ODS 外部表 Parquet schema 修复 PRD

### 已完成工作

- 新建 worktree `/Users/luna/Desktop/git/quant-ashare-ods-parquet-schema-repair-prd` 和分支 `codex/prd-ods-parquet-schema-repair`。
- 新增 `docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md`，定义 10 张 ODS 外部表 Parquet 物理类型 mismatch 的修复方案。
- PRD 明确默认修复路径为 schema contract → GCS 原 Parquet 读取 → 显式 cast → staging → 临时 external table 验证 → backup → 发布正式 prefix → 正式 ODS QA。
- PRD 明确 API 重拉只作为原文件损坏、缺失、行数无法复原或 owner 明确要求的补救路径，不作为默认修复方式。
- PRD 明确优先修当前 P0 源表 `ods_tushare_stk_limit`，再分批修 `limit_list_d`、`moneyflow`、`margin_detail`、`dividend`、`margin`、`daily_info`、`sz_daily_info`、`fina_audit`、`stk_rewards`。
- 新增 `DECISION-20260603-03` 和 OQ-012，更新 `KNOWN_CONSTRAINTS.md`、`ARCHITECTURE_MEMORY.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`MEMORY_INDEX.md` 和 `TODO.md`。

### 重要上下文

- 本次只写 PRD 和记忆/TODO，未修改 GCS、BigQuery ODS 外部表或生产数据。
- 10 张表中当前策略相关的只有 `ods_tushare_stk_limit`；现有 DWD 只读取 `up_limit/down_limit`，但 `pre_close` mismatch 仍需修复，避免未来全字段读取或扩展失败。
- API 6000 行上限和值级差异问题继续按数据审查流程复核，不纳入本 PRD 的默认修复输入。

### 改动文件

- `docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review 并合并本 PRD。
- 合并后先实现 schema contract、repair manifest 和 `ods_tushare_stk_limit` 的 staging 修复验证。

### 已更新记忆文件

- `TODO.md`
- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `ARCHITECTURE_MEMORY.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `DECISION_LOG.md`
- `KNOWN_CONSTRAINTS.md`
- `AGENT_HANDOFF.md`

---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #39 / issuecomment-4611682018 / OQ-005

### 已完成工作

- 跟进 PR #39 review comment `issuecomment-4611682018` 的 2 个低优先级建议。
- 在 `docs/prd/PRD_20260603_03_GCP数据流水线方案.md` §6.4 明确财务报告期 endpoint 每日执行近期公告 / 修正滚动检查，有新增或修正行时写回对应报告期分区；空返回记录 `expected_empty` / `empty_return` event，正式 GCS prefix 保持无新增对象。
- 在 PRD Phase 1 交付与验收中补充 Cloud Scheduler 与 Composer 两种触发入口，明确 Cloud Run Jobs 可由 Cloud Scheduler 或 Composer 触发并写入统一 run id / execution id。
- 同步 `TODO.md`、`OPEN_QUESTIONS.md`、`PROJECT_CONTEXT.md`、`ARCHITECTURE_MEMORY.md`、`IMPLEMENTATION_STATUS.md`、`MEMORY_INDEX.md` 和当前交接摘要。

### 重要上下文

- PR #39 review 结论为可以合并、0 个阻塞发现。
- 本次只修订 PRD 与记忆/TODO，未实现 Cloud Run、Dataform 或 Composer。
- 架构决策和首批 14 张 ODS 采集范围未改变。

### 改动文件

- `docs/prd/PRD_20260603_03_GCP数据流水线方案.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review 并合并 PR #39。
- 合并后按 Phase 0 实现 `configs/ingestion/ods_current_scope_v0.yml` 与首批 14 张 ODS schema contract。

### 已更新记忆文件

- `TODO.md`
- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `ARCHITECTURE_MEMORY.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`

---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #45 / OQ-010 实验并发调度 Phase 1

### 已完成工作

- 跟进 PR #45 最新 review comment，修复 OQ-010 并发调度器的 GCS lock 安全问题。
- `scripts/strategy1/run_oq010_experiments.py` 的 GCS lock acquire 记录 `acquired_at`、`lease_expires_at` 和 object generation。
- stale lock reclaim 改为读取并删除同一 generation：只删除刚检查过且已过期的 lock object，避免多个调度器竞争时误删对方刚创建的新锁。
- heartbeat 和 release 也改为 generation 条件操作，旧进程不会刷新或删除新 generation 的 lock object。
- 状态表 upsert 支持写入真实 `lock_acquired_at`、`lock_expires_at` 和 `last_heartbeat_at`；running 状态写入失败仍会释放 GCS lock 并取消 step。
- heartbeat loop 同步刷新 BigQuery 状态表中的 `last_heartbeat_at` 和 `lock_expires_at`，让审计字段与 GCS lease 对齐。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`KNOWN_CONSTRAINTS.md` 和当前交接摘要。

### 重要上下文

- 本次未执行 BigQuery，不触碰正在运行的 A3 实验，不删除或覆盖 `reports/strategy1` 下已有产物。
- 该修复只收口 PR #45 Phase 1 锁安全与审计字段；Phase 2-4 仍待后续实现和端到端验收。

### 改动文件

- `scripts/strategy1/run_oq010_experiments.py`
- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/run_oq010_experiments.py`
- `git diff --check origin/main..HEAD`
- `git diff --check`
- `python3 scripts/strategy1/run_oq010_experiments.py --dry-run --stage-id stage_a`
- `python3 scripts/strategy1/run_oq010_experiments.py --dry-run --experiment-id oq010_a1_n10_w10`
- fake GCS blob 测试：stale reclaim 使用被检查到的 generation 条件删除，非过期锁不删除。

### 阻塞项

- 无。

### 下一步建议

- Review PR #45 最新提交后合并。
- 合并后先继续 dry-run / 单实验执行验证，再按 Phase 2-4 推进 portfolio-only 并发、08 ledger 并发和 retrain 混合队列。

### 已更新记忆文件

- `TODO.md`
- `IMPLEMENTATION_STATUS.md`
- `KNOWN_CONSTRAINTS.md`
- `AGENT_HANDOFF.md`

---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-005 / GCP 数据流水线 PRD

### 已完成工作

- 新建 worktree `/Users/luna/Desktop/git/quant-ashare-gcp-data-pipeline-prd` 和分支 `codex/prd-gcp-data-pipeline`。
- 新增 `docs/prd/PRD_20260603_03_GCP数据流水线方案.md`，定义长期生产架构：Cloud Run Jobs 负责 Tushare/Tinyshare→GCS Parquet，Dataform / BigQuery Studio pipeline 负责 ODS→DIM/DWD/DWS/ADS，Cloud Composer 负责调度、重试、补跑和告警。
- 从当前 SQL 引用提取首批每日生产采集范围：`daily`、`adj_factor`、`stk_limit`、`suspend_d`、`daily_basic`、`index_daily`、`index_dailybasic`、`stock_basic`、`trade_cal`、`namechange`、`fina_indicator`、`income`、`balancesheet`、`cashflow`；明确未消费 ODS 暂不安排定时任务。
- 追加 `DECISION-20260603-02`，同步 `OPEN_QUESTIONS.md`、`ARCHITECTURE_MEMORY.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`MEMORY_INDEX.md`、`TODO.md` 和当前交接摘要。

### 重要上下文

- 本次是 PRD / 记忆 / 决策更新，未实现 Cloud Run、Dataform、Composer 或采集代码。
- OQ-005 仍标记为 open，状态为 PRD 草案已新增，待 review/合并与实施后关闭。
- PRD 明确首批生产采集不做 57 张 ODS 全量调度；新增 endpoint 必须先更新采集 manifest、schema contract、单位契约和 QA。

### 改动文件

- `docs/prd/PRD_20260603_03_GCP数据流水线方案.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- review/合并本 PRD。
- 合并后按 Phase 0 新增 `configs/ingestion/ods_current_scope_v0.yml` 与首批 14 张 ODS schema contract。
- 后续实现 Cloud Run Jobs、Dataform P0 转换和 Cloud Composer DAG。

### 已更新记忆文件

- `TODO.md`
- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `ARCHITECTURE_MEMORY.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `DECISION_LOG.md`
- `AGENT_HANDOFF.md`

---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: ODS/GCS 数据审查提示词直接入 main

### 已完成工作

- 新增根目录 `data_audit/`，作为 ODS/GCS 数据审查入口。
- 新增 `data_audit/ODS_GCS_DATA_AUDIT_PROMPT.md`，提示词要求审查 Agent 通过 BigQuery ODS 外部表和 Tushare/Tinyshare API 做只读审查，审查范围限定 2019-01-01 及之后。
- 明确审查脚本由执行 Agent 自行编写；若请求参数、并发、限速、schema 检测、报告生成等审查代码有问题，执行 Agent 应自行修正审查代码后继续。
- 明确审查脚本必须按 endpoint 或主题拆分，不能把所有接口请求堆进一个大脚本。
- 补充 Tushare 官方数据索引和常见 endpoint 文档链接；要求报告记录每个实际审查 endpoint 使用的官方文档 URL。
- 补充 API 返回行数命中官方单次上限或脚本 page size / limit 时的风险处理：标记 `row_limit_hit=true`、拆细条件复查，复查前不得把响应当完整样本做结论。
- 新增 `data_audit/reports/README.md`，要求审查报告记录审查时间、数据范围、审查 LLM、run id、Git 状态、BQ 范围、token 数量、限速、请求统计、官方文档链接、row limit 命中复查、Findings 和只读声明。
- 同步 `TODO.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要。

### 重要上下文

- 本次只新增审查提示词和报告目录约定，未执行实际审查，未调用 Tushare/Tinyshare，未修改 GCS 或 BigQuery 生产数据。
- 提示词允许修正审查脚本本身，但禁止补采数据、写伪空 Parquet、改写 raw、重建或覆盖生产表。

### 改动文件

- `data_audit/README.md`
- `data_audit/ODS_GCS_DATA_AUDIT_PROMPT.md`
- `data_audit/reports/README.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- 使用 `data_audit/ODS_GCS_DATA_AUDIT_PROMPT.md` 启动审查 Agent。
- 审查完成后将报告写入 `data_audit/reports/`。

### 已更新记忆文件

- `TODO.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`

---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: gthbj/quant-ashare#35 / issuecomment-4609670537

### 已完成工作

- 评估 PR #35 comment 中两条 P2，均认可并修订 PRD。
- 将 `baseline_experiment_id` 改为 canonical `oq010_base_oriented_weekly_h5_n5_w20_pv`，阶段 A/B/C 使用独立 `experiment_id` 并通过 `parent_experiment_id` 追溯来源。
- 明确阶段 C 固定使用阶段 B 晋级调仓频率，以隔离 label horizon 变量；`horizon_natural_frequency` 仅写入 manifest / 报告作解释。
- 同步 `TODO.md`、`OPEN_QUESTIONS.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`MEMORY_INDEX.md` 和当前交接摘要。

### 重要上下文

- 本次仍是 PRD / 记忆修订，未修改 runner SQL 或 Python。
- 后续实现应按修订后的 manifest 字段补 `baseline_experiment_id` / `parent_experiment_id`，并在 QA 中校验阶段 C 频率不被 horizon 硬绑覆盖。

### 改动文件

- `docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`

### 测试 / 验证

- `git diff --check`
- 复核旧 baseline id、旧“建议调仓频率”表头和 conflict marker 均无正文残留。
- 文档 / 记忆更新，未执行 SQL。

### 阻塞项

- 无。

### 下一步建议

- owner 确认修订后的首轮实验矩阵。
- 根据确认结果实现实验参数化、manifest、对比报告和 QA。

### 已更新记忆文件

- `TODO.md`
- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`

---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: OQ-005 / PR #39 / `codex/prd-gcp-data-pipeline`

### 已完成工作

- 按 owner 反馈修订 `docs/prd/PRD_20260603_03_GCP数据流水线方案.md`，将正文从“选型说明 / 为什么不”收敛为陈述性目标实现方案。
- 移除“为什么不用纯 BigQuery Scheduled Queries”“为什么不把每日采集写在 BigQuery Studio notebook 里”等反向论证段落。
- 将“非目标”改为“实施边界”，将“推荐架构”改为“目标架构”，并用职责边界表描述 Cloud Run Jobs、Dataform / BigQuery Studio pipeline、Cloud Composer、SQL QA 和 notebook / 手工 SQL 的生产职责。
- 将每日生产请求口径明确为单授权上下文 / 授权代理 + endpoint group 有限并发 + job 级基础节流；数据审查并发模式和生产采集模式分开管理。
- 同步 `TODO.md`、`OPEN_QUESTIONS.md`、`ARCHITECTURE_MEMORY.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`MEMORY_INDEX.md` 和当前交接摘要。

### 重要上下文

- 架构决策未改变：仍是 Cloud Run Jobs 采集、Dataform / BigQuery Studio pipeline 转换、Cloud Composer 编排。
- 首批每日生产采集范围未改变：14 个当前实际消费 ODS endpoint。
- OQ-005 仍为 open，待 PRD review/合并与后续实现后关闭。

### 改动文件

- `docs/prd/PRD_20260603_03_GCP数据流水线方案.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `rg -n "为什么|非目标|不建议|不采用|不要|避免|原因：|暂不|不把|\\b建议\\b|可选|可以|如果|适合" docs/prd/PRD_20260603_03_GCP数据流水线方案.md`
- `git diff --check`

### 阻塞项

- 无。

### 下一步建议

- Review 并合并 PR #39。
- 合并后按 Phase 0 实现 `configs/ingestion/ods_current_scope_v0.yml` 与首批 14 张 ODS schema contract。

### 已更新记忆文件

- `TODO.md`
- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `ARCHITECTURE_MEMORY.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`

---

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: `s1_bqml_oq010_oq010_a0_n5_w20_20260603_01`
相关 issue/PR: `codex/fix-diagnosis-bqstorage-fetch`

### 已完成工作

- 配置本机 BigQuery Storage API 客户端：`data-aquarium` 已启用 `bigquerystorage.googleapis.com`；本机 conda Python 与默认 `python3` 均已安装 `google-cloud-bigquery-storage==2.38.0`。
- 修复 `scripts/strategy1/diagnose_model_quality.py` 的本地大 DataFrame 拉取不稳定问题：
  - `bq_query()` 显式使用 `BigQueryReadClient`，优先 ADC，ADC 不可用时复用 `gcloud auth print-access-token` fallback；缺依赖或无可用凭据时保留 REST fallback。
  - valid/test 预测标签改为一次拉取 2024-2025 后按 `split_tag` 分片，减少重复查询和本地对象复制。
  - feature exposure 改为 BigQuery 侧聚合，只回传聚合统计行，不再把预测池全部特征拉回本地。
- 更新 `scripts/strategy1/requirements.txt`，新增 `google-cloud-bigquery-storage>=2.0`。
- 完成 A0（`oq010_a0_n5_w20`）后续诊断与 QA：`diagnose_model_quality.py` uploaded 模式成功，`sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql` 全部 ASSERT 通过。

### 重要上下文

- A0 已端到端跑通 01-12：`run_id=s1_bqml_oq010_oq010_a0_n5_w20_20260603_01`，`backtest_id=bt_s1_bqml_oq010_oq010_a0_n5_w20_20260603_01`。
- A0 summary：`total_return=0.27868`，`sharpe=0.7258`，`max_drawdown=-0.2217`，相对中证1000 `excess_return=-0.01145`。
- A0 诊断：`primary_diagnosis=usable_signal`，`confidence=low`，valid RankIC mean `0.098666`，test RankIC mean `0.055965`；诊断 artifact 上传至 `gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_bqml_oq010_oq010_a0_n5_w20_20260603_01/backtest_id=bt_s1_bqml_oq010_oq010_a0_n5_w20_20260603_01/model_diagnosis`。
- 继续 A1-A3 前应先合并本修复 PR，避免诊断阶段重复出现本地拉取不稳定。

### 改动文件

- `scripts/strategy1/diagnose_model_quality.py`
- `scripts/strategy1/requirements.txt`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `/Users/luna/miniconda3/bin/python -m py_compile scripts/strategy1/diagnose_model_quality.py scripts/strategy1/render_report.py scripts/strategy1/compare_oq010_experiments.py`
- 仓库 `bq_query()` helper 验证：`rest_endpoint_warning=False`，`BigQueryReadClient` fallback 路径可导入和编译
- 受控预测标签拉取：1,055,737 行，DataFrame 约 195.8 MB，BigQuery Storage 生效
- `fetch_feature_exposure()` 聚合验证：返回 90 行
- A0 `diagnose_model_quality.py`：`diagnose_rc=0`
- A0 `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`：全部 ASSERT successful

### 阻塞项

- 无代码阻塞；需 review/合并诊断稳定性修复 PR 后继续 A1-A3。

### 下一步建议

- 合并诊断稳定性修复 PR。
- 回到 `main` 后继续阶段 A：A1/A2/A3 只跑 05-12，并使用 `prediction_run_id=s1_bqml_livepool_oriented_20260603_01`。
- 阶段 A 全部完成后再运行 `compare_oq010_experiments.py`，只记录事实，不直接下默认参数结论。

### 已更新记忆文件

- `TODO.md`
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
相关 issue/PR: PR #37 / merge commit `57cff1852a9386bbc06a43d35d5e18ea7cc4ec58`

### 已完成工作

- 合并 PR #37 到 `main`：OQ-010 首轮实验 runner 参数化、manifest、对比报告脚本、portfolio-only `prediction_run_id` 复用预测源路径、horizon-aware 诊断/QA 已进入主线。
- rebase PR #37 到最新 `origin/main` 并解决 `TODO.md` 状态记录冲突；保留 ODS/GCS 数据审查完成项和 OQ-010 runner 完成项。
- GitHub merge 后已同步本地 `main`，并通过 `git fetch --prune origin` 清理 `origin/codex/implement-oq010-experiment-runner` stale 引用；远端 PR 分支已删除，本地无该分支。
- 同步 `TODO.md`、`MEMORY_INDEX.md`、`PROJECT_CONTEXT.md`、`OPEN_QUESTIONS.md`、`IMPLEMENTATION_STATUS.md` 和当前交接摘要：明确 PR #37 已合并，但 OQ-010 端到端实验尚未跑。

### 重要上下文

- OQ-010 实验执行仍未开始；下一步应先跑 A0 基线复现，再跑 A1-A3 portfolio-only 阶段 A 实验。
- A0 可重训，用于对账 5d 基线；A1-A3/B0-B2 只跑 05-12，并用 `p_prediction_run_id` / `--prediction-run-id` 复用预测源。

### 改动文件

- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- PR #37 合并前已通过：JSON 校验、Python `py_compile`、`git diff --check`、BigQuery dry-run。
- 本次状态同步为文档 / 记忆更新，未执行 SQL。

### 阻塞项

- 无代码阻塞；等待执行 OQ-010 第一轮实验。

### 下一步建议

- 执行 OQ-010 阶段 A：先 A0 基线复现，再 A1-A3 portfolio-only。
- 每个实验跑 `10`、`render_report.py`、`diagnose_model_quality.py`、`12`，再用 `compare_oq010_experiments.py` 汇总事实 artifact。

---

## 交接条目

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #37 / issuecomment-4610284627

### 已完成工作

- 处理 PR #37 review feedback：认可组合层实验不应全量重训，并实现 portfolio-only `prediction_run_id` 复用模型/预测路径。
- 更新 `configs/strategy1/oq010_experiments_v0.json`：A0 保留 `requires_retrain=true` 作为 5d 基线复现检查；A1-A3 与 B0-B2 改为 `requires_retrain=false`，并显式记录 `prediction_run_id`。
- 修改 `05/09/10/11/12` 与 `diagnose_model_quality.py`：输出仍写实验 `run_id/backtest_id`，模型注册、预测表、训练面板和分数方向 QA 改查 `prediction_run_id`。
- 修改 `06_build_portfolio_targets.sql`：目标权重按 `min(1 / p_target_holdings, p_max_single_weight)` 计算；实际入选不足时保留现金，不按实际入选数重新满仓。
- 更新 `compare_oq010_experiments.py` 和 README：对比脚本可从 summary 或 manifest 的 `prediction_run_id` 读取 registry 指标；执行说明区分 `requires_retrain=true` 的 01-12 和 `requires_retrain=false` 的 05-12 路径。

### 重要上下文

- 本轮仍未端到端实跑 OQ-010 实验；只做 SQL/Python/manifest/文档修订和 dry-run 级验证。
- Claude review 的 P2 已采纳；P3 目标权重口径选择直接对齐 PRD 留现金要求；P3 基线复现建议通过 A0 保留重训检查承载。

### 改动文件

- `configs/strategy1/oq010_experiments_v0.json`
- `scripts/strategy1/compare_oq010_experiments.py`
- `scripts/strategy1/diagnose_model_quality.py`
- `sql/ml/strategy1/05_build_candidates.sql`
- `sql/ml/strategy1/06_build_portfolio_targets.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/11_model_quality_diagnostics.sql`
- `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m json.tool configs/strategy1/oq010_experiments_v0.json`
- `python3 -m py_compile scripts/strategy1/compare_oq010_experiments.py scripts/strategy1/diagnose_model_quality.py scripts/strategy1/render_report.py`
- `git diff --check`
- BigQuery dry-run：`sql/ml/strategy1/05_build_candidates.sql`、`06_build_portfolio_targets.sql`、`09_build_metrics_and_report_inputs.sql`、`10_qa_runner_outputs.sql`、`11_model_quality_diagnostics.sql`、`12_qa_model_diagnosis_outputs.sql`

### 阻塞项

- 无代码阻塞；尚需提交并推送 PR #37。

### 下一步建议

- 完成验证并推送 PR #37 修订。
- PR 合并后先跑 A0 基线复现，再执行 A1-A3 portfolio-only 实验。

---

---

## 交接条目

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: gthbj/quant-ashare#35

### 已完成工作

- 合并 PR #35 到 `main`：OQ-010 策略 1 首轮质量迭代实验 PRD 已进入主线。
- 同步本地 `main` 到 `origin/main` 合并提交 `8de0498`。
- 确认远端 `codex/prd-oq010-quality-iteration` 分支已删除，并通过 `git fetch --prune origin` 清理本地 remote-tracking 引用。
- 更新 PRD 状态、`TODO.md`、`MEMORY_INDEX.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md` 和当前交接摘要，收敛到“按已合并 PRD 实现实验参数化 / manifest / 对比报告 / 第一轮实验”。

### 重要上下文

- PR #35 是文档 / 记忆 PR，未修改 runner SQL 或 Python。
- OQ-010 仍保持 open：首轮实验 PRD 已合并，但默认调仓频率、持股数、单票权重上限和特征 / 标签口径需等实验结果再确认。

### 改动文件

- `docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`

### 测试 / 验证

- `git diff --check`
- 已复核 PRD / TODO / memory 正文无 PR #35 合并前 review 状态残留。

### 阻塞项

- 无。

### 下一步建议

- 开始实现 OQ-010 第一轮实验参数化、manifest、对比报告和 QA。

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
相关 issue/PR: OQ-010 / 策略 1 首轮实验非笛卡尔积口径

### 已完成工作

- 按 owner 确认修订 `docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`。
- 明确阶段 A/B/C 不做 `4 * 3 * 3` 全量笛卡尔积；基础执行为阶段 A 固定 weekly + 5d 跑 4 个持股 / 权重实验，再用阶段 A 晋级组合跑阶段 B 的 3 个调仓频率实验，再用阶段 A/B 晋级参数跑阶段 C 的 3 个 label horizon 实验，即 `4 + 3 + 3 = 10`。
- 明确阶段 D 只使用阶段 C 或最终保底复核晋级参数跑 2 个特征集合；完整第一轮基础实验数为 12。
- 增加可选小型交互复核规则：阶段 A/B、A/C 或 B/C 暴露明显交互风险时，补最多 `2 * 2 = 4` 个 pairwise 实验；最终 `2 * 2 * 2` 只在至少两类 pairwise 复核显示明显联动、晋级结果不稳或 owner 明确要求时作为保底复核。
- 补充 `30/5%` 解释：表示目标持股 30 只、单票权重上限 5%，目标单票等权约 3.33%，不是每只买 5%。
- 采纳 PR #36 comment：补充 A/C（持股数 * label horizon）pairwise 复核，防止 5d+weekly 下选出的持股数在 10d/20d 胜出时不再稳。
- 追加 `DECISION-20260603-01`，同步 `TODO.md`、`OPEN_QUESTIONS.md`、`PROJECT_CONTEXT.md`、`IMPLEMENTATION_STATUS.md`、`MEMORY_INDEX.md` 和当前交接摘要。

### 重要上下文

- 本次仍是 PRD / 记忆修订，未修改 runner SQL 或 Python。
- 后续实现 manifest / 对比报告 / QA 应以 `4 + 3 + 3` 为 A/B/C 基础路径、包含阶段 D 为 12 个基础实验；只有满足触发条件时才补 A/B、A/C、B/C pairwise 或最终 `2 * 2 * 2` 复核，不应默认生成 36 个 A/B/C 全量组合。

### 改动文件

- `docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`

### 测试 / 验证

- `git diff --check`
- 已复核 PRD / TODO / memory 中阶段 A/B/C 非笛卡尔积、基础 `4 + 3 + 3`、阶段 D 12 个基础实验、可选 A/B、A/C、B/C `2 * 2` pairwise 和最终 `2 * 2 * 2` 保底复核口径一致。
- 文档 / 记忆更新，未执行 SQL。

### 阻塞项

- 无。

### 下一步建议

- 实现 OQ-010 第一轮实验参数化、manifest、对比报告和 QA。

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
Agent ID: DeepSeek V4
Agent 实例 ID: opencode desktop session
模型: DeepSeek V4
运行环境: opencode desktop
Run ID: —
相关 issue/PR: OQ-010 / PRD_20260603_05 策略1实验并发调度与隔离

### 已完成工作

- 新建 worktree `/Users/luna/Desktop/git/quant-ashare-oq010-parallel-runner` 和分支 `codex/implement-oq010-parallel-runner`（基于 `main`）。
- 新增 `sql/meta/02_strategy1_experiment_run_status.sql`：`ashare_meta.strategy1_experiment_run_status` 状态表 DDL，覆盖实验身份、step 状态、锁信息、产物和调度追踪字段。
- 新增 `scripts/strategy1/run_oq010_experiments.py`：OQ-010 并发调度器，支持全部 PRD 定义 CLI 参数。实现 GCS `ifGenerationMatch=0` 原子锁、lease/heartbeat/stale reclaim、manifest 解析与依赖拓扑排序、BigQuery 状态表 upsert（`MERGE`）、step 执行（bq / python subprocess）、实验参数注入 SQL `DECLARE`、ThreadPoolExecutor 并发控制、backtest semaphore。dry-run 展开完整计划（step 列表、锁 key、ADS 表、并发分组、依赖阻断）。
- 新增 `sql/qa/07_strategy1_experiment_concurrency_checks.sql`：12 个 QA-CONC 断言。
- 新增 `docs/策略1实验并发调度器运行手册.md`。
- 追加 `DECISION-20260603-04`（GCS 原子锁 + BigQuery 状态表架构决策）。
- 更新 `TODO.md`、`IMPLEMENTATION_STATUS.md`、`KNOWN_CONSTRAINTS.md`、`OPEN_QUESTIONS.md`、`AGENT_HANDOFF.md` 和当前交接摘要。

### 重要上下文

- 本次只实现 Phase 1（状态表 DDL、调度器 dry-run、GCS 锁原语、并发 QA SQL），未修改现有 SQL runner 脚本，未在 BigQuery 执行真正并发实验，未触碰正在运行的 A3 实验，未删除或覆盖 `reports/strategy1` 下已有产物。
- 调度器使用 `subprocess` 调用 `bq query` 执行 SQL 和 `python` 执行报告/诊断脚本。SQL 参数注入使用 `_inject_parameter()` 替换 `DECLARE ... DEFAULT` 值。
- GCS 锁 bucket 为 `ashare-artifacts`，锁前缀 `locks/strategy1/oq010/`。锁默认 TTL 30 分钟，heartbeat 每 60 秒刷新。
- Phase 2-4（portfolio-only 并发执行、08 ledger 并发、retrain 训练锁与混合队列）仍待实现和验收。当前约束下禁止本机裸多进程直接并发跑 SQL。

### 改动文件

- `sql/meta/02_strategy1_experiment_run_status.sql`（新）
- `scripts/strategy1/run_oq010_experiments.py`（新）
- `sql/qa/07_strategy1_experiment_concurrency_checks.sql`（新）
- `docs/策略1实验并发调度器运行手册.md`（新）
- `TODO.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m py_compile scripts/strategy1/run_oq010_experiments.py`
- `python3 scripts/strategy1/run_oq010_experiments.py --dry-run`（通过：展开 stage_a 多实验计划）
- `python3 scripts/strategy1/run_oq010_experiments.py --experiment-id oq010_a1_n10_w10 --dry-run`（通过：单实验 dry-run）
- `git diff --check`（无 whitespace error）
- 未执行 BigQuery，未触碰 A3 / reports 产物

### 阻塞项

- 无。

### 下一步建议

- Review 并合并本 PR。
- 合并后先用调度器 dry-run 验证同 stage 计划展开，再选择适当实验用调度器执行。
- 后续实现 Phase 2-4 以支持真正的并发执行。

---

## 交接条目

日期: 2026-06-03
Agent ID: Codex
Agent 实例 ID: Codex desktop session
模型: GPT-5
运行环境: Codex desktop
Run ID: —
相关 issue/PR: PR #37 / `codex/implement-oq010-experiment-runner`

### 已完成工作

- 新增 OQ-010 实验 manifest：`configs/strategy1/oq010_experiments_v0.json`，覆盖阶段 A/B/C/D 基础路径、blocked 依赖和非笛卡尔积执行策略。
- 新增实验对比报告脚本：`scripts/strategy1/compare_oq010_experiments.py`，从 manifest + ADS summary/registry 生成 Markdown/JSON/CSV 对比 artifact。
- 参数化策略 1 runner：`sql/ml/strategy1/01-06/09-12` 支持 `experiment_id`、`experiment_group`、`baseline_experiment_id`、`parent_experiment_id`、`parent_run_id`、`p_rebalance_frequency`、`p_target_holdings`、`p_max_single_weight`、`p_label_horizon`、`p_feature_set_id`，并在 05/09/10/11/12 与诊断脚本支持 portfolio-only `p_prediction_run_id` 复用预测源。
- 扩展 `dws_stock_sample_daily` 输出 10d/20d 标签和收益字段，供 `p_label_horizon` 选择目标列。
- 将 `diagnose_model_quality.py`、`11_model_quality_diagnostics.sql`、`12_qa_model_diagnosis_outputs.sql` 改为 horizon-aware，避免 10d/20d 实验仍按 5d 诊断或 QA。
- 更新 `sql/ml/strategy1/README.md` 的 OQ-010 执行说明和参数表。

### 重要上下文

- 本轮只做实现和 dry-run 验证，尚未在 BigQuery 端到端执行任何 OQ-010 实验。
- 财务特征实验中 `feature_version` 仍保留基础量价样本版本 `strategy1_pv_v0_20260601`，财务扩展通过 `feature_set_id='strategy1_pv_fin_quality_v0_20260603'` 控制；财务 DWS 来源版本为 `fin_default_v0_20260602`。
- `30/5%` 由 `06_build_portfolio_targets.sql` 计算为 `min(1 / target_holdings, max_single_weight)`，30 只时目标单票约 3.33%，实际入选不足持股数时保留现金，不按实际入选数重新满仓、不突破单票上限。

### 改动文件

- `configs/strategy1/oq010_experiments_v0.json`
- `scripts/strategy1/compare_oq010_experiments.py`
- `scripts/strategy1/diagnose_model_quality.py`
- `sql/dws/06_dws_stock_sample_daily.sql`
- `sql/ml/strategy1/01_build_training_panel.sql`
- `sql/ml/strategy1/02_train_bqml_logistic_candidates.sql`
- `sql/ml/strategy1/03_select_model_and_register.sql`
- `sql/ml/strategy1/04_predict_daily.sql`
- `sql/ml/strategy1/05_build_candidates.sql`
- `sql/ml/strategy1/06_build_portfolio_targets.sql`
- `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`
- `sql/ml/strategy1/10_qa_runner_outputs.sql`
- `sql/ml/strategy1/11_model_quality_diagnostics.sql`
- `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql`
- `sql/ml/strategy1/README.md`
- `TODO.md`
- `.agent/memory/MEMORY_INDEX.md`
- `.agent/memory/PROJECT_CONTEXT.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m json.tool configs/strategy1/oq010_experiments_v0.json`
- `python3 -m py_compile scripts/strategy1/compare_oq010_experiments.py scripts/strategy1/diagnose_model_quality.py scripts/strategy1/render_report.py`
- `git diff --check`
- BigQuery dry-run：`sql/dws/06_dws_stock_sample_daily.sql`、`sql/ml/strategy1/01_build_training_panel.sql`、`02_train_bqml_logistic_candidates.sql`、`03_select_model_and_register.sql`、`04_predict_daily.sql`、`05_build_candidates.sql`、`06_build_portfolio_targets.sql`、`09_build_metrics_and_report_inputs.sql`、`10_qa_runner_outputs.sql`、`11_model_quality_diagnostics.sql`、`12_qa_model_diagnosis_outputs.sql`

### 阻塞项

- 无代码阻塞；尚需 PR review/合并后才能开始端到端实验执行。

### 下一步建议

- Review 并合并 PR #37。
- 合并后先重建 `sql/dws/06_dws_stock_sample_daily.sql`，再按 manifest 阶段 A 开始跑第一批实验。
- 每批实验跑完 `10`、`render_report.py`、`diagnose_model_quality.py`、`12`，再用 `compare_oq010_experiments.py` 生成对比 artifact。

### 已更新记忆文件

- `TODO.md`
- `MEMORY_INDEX.md`
- `PROJECT_CONTEXT.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENT_HANDOFF.md`
