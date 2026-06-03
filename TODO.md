# TODO

本文件只保留"下一步可执行事项"。整体状态和历史完成记录见 `.agent/memory/IMPLEMENTATION_STATUS.md` / `.agent/memory/AGENT_HANDOFF.md`；待 owner 决策的问题以 `.agent/memory/OPEN_QUESTIONS.md` 为唯一来源。

维护规则见 `AGENTS.md` 的「TODO 维护协议」。

## P0 — 当前优先

- [ ] 补 P0 通用 DWS 扩展表：`dws_market_state_daily`、后续策略共用市场状态特征（`dws_stock_feature_fin_daily` 已落地）
- [ ] 修复 ODS 外部表 Parquet schema mismatch：按 `docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md` 先修当前 P0 源表 `ods_tushare_stk_limit`，再分批修其余 9 张 P1/P2/P3 表；默认从 GCS 原 Parquet 按 schema contract 重写，不从 API 重拉覆盖历史 raw
- [ ] 策略 1 runner v0 模型质量与参数迭代（OQ-010）：PR #37 已合并，实验参数化、manifest、对比报告脚本、horizon-aware 诊断/QA 和 portfolio-only `prediction_run_id` 复用预测源路径已进入 `main`；A0（`oq010_a0_n5_w20`）已跑通 01-12，诊断稳定性修复 PR 待合并后继续 A1-A3。阶段 A/B/C 基础路径为 `4 + 3 + 3 = 10`，包含阶段 D 为 12 个实验，不做 `4 * 3 * 3` 全量笛卡尔积；必要时补最多 `2 * 2` A/B、A/C、B/C pairwise 复核或最多 `2 * 2 * 2` 最终保底复核
- [ ] OQ-010 并发调度 Phase 2-4：实现 05-12 参数化调度 + portfolio-only 并发（Phase 2）、08 ledger 并发与 resume（Phase 3）、retrain 实验训练/预测锁与混合队列（Phase 4）；当前 Phase 1（状态表、调度器 dry-run、GCS 原子锁、并发 QA）已实现

## P1 — 数据 / 特征扩展

- [ ] 三大报表单季派生（`income`/`cashflow` 累计转单季 `q_*`）作为 P1 财务表内容（OQ-003 PRD §4 推荐延后）
- [ ] `dim_stock_sw_industry_hist`（source `index_member_all`，按 `in_date/out_date` 建申万行业时点归属，并 QA 区间重叠 / 缺口）
- [ ] `dim_stock_ci_industry_hist`（source `ci_index_member`，中信行业时点归属，对照体系）
- [ ] `dwd_sw_industry_eod` + 行业中性化
- [ ] P1+ 资金面 / 事件 / 行业族 DWD：moneyflow、margin、hk_hold / ccass、龙虎榜、股东增减持、质押回购、业绩预告 / 快报、分红、分析师报告等；新增 DWD 前先按 OQ-006 补单位映射
- [ ] `dim_index_weight`、`dim_sw_industry`、`dim_ipo`
- [ ] 补 lookback-capable 价格构建输入或调整 DWD/DWS 构建方式，使 2019-01 起 60 日窗口可直接读取 2018 buffer；当前策略 1 DWS 用 `has_full_history_60d=FALSE` 标记并默认剔除不完整窗口样本（OQ-011）

## 工程 / 调度

- [ ] OQ-005 GCP 数据流水线落地：`docs/prd/PRD_20260603_03_GCP数据流水线方案.md` 已定义 Cloud Run Jobs 采集、Dataform / BigQuery Studio pipeline 做 ODS→ADS、Cloud Composer 编排，且已按 owner 要求收敛为只描述最终实现方式的陈述性方案；PR #39 review 两条低优先级建议已补入财务 empty-return 口径和 Phase 1 触发入口；下一步实现首批 14 张当前消费 ODS 的采集 manifest、Cloud Run Jobs、Dataform P0 转换和 Composer DAG
- [ ] 将 `lookback_start_date` 从固定默认值升级为按最大滚动窗口计算 / 调度配置
- [ ] 写"从 ODS 继承字段描述"脚本（`bq show` -> 映射 -> `bq update`）
- [ ] 增量调度（dbt 或 Airflow + SQL）与数据质量断言

## 近期完成

- [x] 实现 OQ-010 策略 1 实验并发调度与隔离 Phase 1：新增 `sql/meta/03_strategy1_experiment_run_status.sql` 状态表 DDL、`scripts/strategy1/run_oq010_experiments.py` 调度器（支持 --dry-run 展开完整计划、GCS ifGenerationMatch=0 原子锁、generation-guarded stale reclaim/release、lease/heartbeat、resume、max-parallel、max-parallel-backtest、fail-fast 等全部 PRD 定义参数）、`sql/qa/06_strategy1_experiment_concurrency_checks.sql` 并发 QA（QA-CONC-1~12），以及 `docs/策略1实验并发调度器运行手册.md`；已通过 Python 静态检查、dry-run 和 fake GCS generation guard 测试；已更新 TODO/memory；尚未执行 BigQuery、不碰正在运行的 A3 实验、不删 reports/strategy1 已有产物
- [x] 新增 OQ-010 策略 1 实验并发调度与隔离 PRD：`docs/prd/PRD_20260603_05_策略1实验并发调度与隔离.md`，定义同阶段 portfolio-only / retrain 实验安全并发的状态表、GCS 原子锁、lease/heartbeat、调度器、runner 改造要求、08 ledger 并发边界和 QA；本次只写 PRD，未改 runner、未跑 BigQuery
- [x] 新增 OQ-005 GCP 数据流水线 PRD：`docs/prd/PRD_20260603_03_GCP数据流水线方案.md`，固化 Cloud Run Jobs + Dataform / BigQuery Studio pipeline + Cloud Composer 架构，限定每日生产采集只覆盖当前实际消费的 14 张 ODS，并已收敛为陈述性目标实现方案；PR #39 review 两条低优先级建议已补入正文
- [x] 新增 ODS 外部表 Parquet schema 修复 PRD：`docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md`，定义 10 张 schema mismatch 外部表的 GCS 原文件 schema-preserving rewrite、staging/backup/发布、QA 门禁和 ingestion 显式 cast 防复发方案；PR #40 review 建议已补入 backup write-once、临时表显式 schema 和 INT→FLOAT64 精度复核
- [x] 新增 ODS/GCS 数据审查目录与提示词：`data_audit/ODS_GCS_DATA_AUDIT_PROMPT.md`、`data_audit/reports/`；审查范围限定 2019-01-01 及之后，提示词要求只审查不补数据、审查脚本由执行 Agent 自行编写并在请求/限速/并发等问题上自修正；已补官方文档链接、API 返回上限命中风险和按 endpoint/主题拆脚本规则
- [x] 实现 OQ-010 首轮实验 runner 参数化（PR #37 已合并）：新增 `configs/strategy1/oq010_experiments_v0.json`、`scripts/strategy1/compare_oq010_experiments.py`；`sql/ml/strategy1/01-06/09-12` 支持 `experiment_id`、调仓频率、持股数/权重、`p_label_horizon`、`feature_set_id`；诊断脚本和 QA 已改为 horizon-aware，并支持 portfolio-only 实验用 `p_prediction_run_id` 复用模型/预测。已通过 Python/JSON/`git diff --check` 与 BigQuery dry-run，尚未端到端实跑实验
- [x] 配置本机 BigQuery Storage API 客户端并修复 OQ-010 诊断稳定性：`data-aquarium` 已启用 `bigquerystorage.googleapis.com`，本机 conda 与默认 `python3` 均已安装 `google-cloud-bigquery-storage`；诊断脚本改为一次性拉取 valid/test 预测标签并将 feature exposure 改为 BigQuery 侧聚合，A0 诊断与 `12_qa_model_diagnosis_outputs.sql` 已通过
- [x] 合并 OQ-010 策略 1 首轮质量迭代实验 PRD（PR #35）：`docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`，定义持股数/权重、调仓频率、标签 horizon、财务特征的第一轮分阶段实验矩阵；已按 review 修订 canonical baseline id、parent experiment 关系和阶段 B/C 调仓频率口径
- [x] 修订 OQ-010 首轮实验执行口径：阶段 A/B/C 不做 `4 * 3 * 3` 笛卡尔积，基础执行为 `4 + 3 + 3 = 10` 个实验，包含阶段 D 为 12 个实验；如阶段间暴露明显交互风险，再补最多 `2 * 2` A/B、A/C、B/C pairwise 复核，必要时补最多 `2 * 2 * 2` 最终保底复核
- [x] 修复诊断 QA：`sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql` 的 `split_tag` 歧义已修复（PR #27/28），已可正常完成 QA 验收
- [x] 实现策略 1 valid/test live-available 预测池口径修正（按 `docs/prd/PRD_20260602_05_策略1预测池口径修正.md`）：train 继续用 trainable labeled sample，valid/test 预测池改为 t 日 live-available feature universe，标签有效性仅用于事后评价（PR #29/30 已合并）
- [x] 实现策略 1 模型质量诊断后续修订（按 `docs/prd/PRD_20260602_04_策略1模型质量诊断.md` + PRD 05）：补 prediction/eval coverage 证据，修正后重跑 local smoke → uploaded → `12_qa_model_diagnosis_outputs.sql`
- [x] 实现策略 1 score orientation 校准（按 `docs/prd/PRD_20260603_01_策略1分数方向校准.md`）：保留 `raw_score`，将最终 `score` 定义为方向校准后的排序分，03 选型登记 `score_orientation`，04 预测阶段应用方向并扩展 QA/report/diagnosis（PR #32 已合并）
- [x] 新增策略 1 分数方向校准 PRD：`docs/prd/PRD_20260603_01_策略1分数方向校准.md`，基于 livepool reverse-score shadow run，将 `raw_score` / oriented `score` / `score_orientation` 固化为待实现契约
- [x] 新增策略 1 valid/test live-available 预测池口径修正 PRD：`docs/prd/PRD_20260602_05_策略1预测池口径修正.md`，明确 sample_filter_risk high 后先修预测池口径，不与信号反向或组合参数实验混做
- [x] 新增策略 1 模型质量诊断 PRD：`docs/prd/PRD_20260602_04_策略1模型质量诊断.md`，明确先诊断 signal/label/sample/universe/portfolio/cost/style，再进入 OQ-010 参数和模型实验
- [x] 策略 1 报告 GCS uploaded 模式已跑通：创建 `gs://ashare-artifacts`（`ASIA-EAST2`）、配置本机 ADC（quota project=`data-aquarium`），去掉 `--skip-gcs-upload` 重跑 `render_report.py`，ADS `report_upload_status=uploaded` 且 `report_uri=gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_bqml_20260601_01/backtest_id=bt_s1_bqml_20260601_01`，`sql/ml/strategy1/10_qa_runner_outputs.sql` 全部通过
- [x] OQ-010 交易成本口径 PRD 已新增并在 runner SQL 中实现：佣金万一免五、卖出印花税 5 bps、买/卖滑点各 5 bps
- [x] 新增策略 1 报告 GCS 上传运行手册：`docs/策略1报告GCS上传运行手册.md`，明确 uploaded 模式的 bucket/ADC/IAM/执行/验收步骤
- [x] 策略 1 中文报告与归因分析 PRD + 实现已合并：报告中文化、中证1000评估主基准、沪深300展示对比基准、交易/持仓/NAV 附件、亏损证据包和 AI 诊断已进入 `main`（PR #20）
- [x] PR #13 / OQ-003 财务三表 DWD + DWS 已合并：`dwd_fin_income` / `dwd_fin_balancesheet` / `dwd_fin_cashflow`（+ `_latest`）、`dws_stock_feature_fin_daily`、`sql/qa/04_finance_caliber_checks.sql` 已进入 `main`；已随表补全 `ods_field_unit_map` 财务字段映射并跑通 `sql/qa/05_oq006_unit_checks.sql`
- [x] OQ-006 单位契约实现已合并（PR #16）：`ashare_meta.ods_field_unit_map`、`sql/qa/05_oq006_unit_checks.sql`、`dwd_index_eod` 换算修复与 `volume_share/amount_cny` 迁移已进入 `main`，OQ-006 已关闭
- [x] 合并 OQ-006 PRD（PR #14）：`docs/prd/PRD_20260602_01_OQ006接口单位换算口径.md`
- [x] 策略 1 BigQuery ML runner 已于 PR #12 在 BigQuery 端到端实跑并通过 `10_qa_runner_outputs.sql`（16 断言）
- [x] OQ-004 基准指数代码可用性已实现并关闭（`dim_index` + 映射驱动 `dwd_index_eod` + OQ-004 QA + runner benchmark 窗口校验）
- [x] OQ-007 退市日类型已复核并关闭，PR #9 后依赖链已重建并通过 P0 / 策略 1 QA
