# TODO

本文件只保留"下一步可执行事项"。整体状态和历史完成记录见 `.agent/memory/IMPLEMENTATION_STATUS.md` / `.agent/memory/AGENT_HANDOFF.md`；待 owner 决策的问题以 `.agent/memory/OPEN_QUESTIONS.md` 为唯一来源。

维护规则见 `AGENTS.md` 的「TODO 维护协议」。

## P0 — 当前优先

- [ ] 补 P0 通用 DWS 扩展表：`dws_market_state_daily`、后续策略共用市场状态特征（`dws_stock_feature_fin_daily` 已落地）
- [ ] 策略 1 runner v0 模型质量与参数迭代（OQ-010）：按 PR #35 已合并的 `docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`，落地实验参数化、manifest、对比报告，并执行第一轮对照实验

## P1 — 数据 / 特征扩展

- [ ] 三大报表单季派生（`income`/`cashflow` 累计转单季 `q_*`）作为 P1 财务表内容（OQ-003 PRD §4 推荐延后）
- [ ] `dim_stock_sw_industry_hist`（source `index_member_all`，按 `in_date/out_date` 建申万行业时点归属，并 QA 区间重叠 / 缺口）
- [ ] `dim_stock_ci_industry_hist`（source `ci_index_member`，中信行业时点归属，对照体系）
- [ ] `dwd_sw_industry_eod` + 行业中性化
- [ ] P1+ 资金面 / 事件 / 行业族 DWD：moneyflow、margin、hk_hold / ccass、龙虎榜、股东增减持、质押回购、业绩预告 / 快报、分红、分析师报告等；新增 DWD 前先按 OQ-006 补单位映射
- [ ] `dim_index_weight`、`dim_sw_industry`、`dim_ipo`
- [ ] 补 lookback-capable 价格构建输入或调整 DWD/DWS 构建方式，使 2019-01 起 60 日窗口可直接读取 2018 buffer；当前策略 1 DWS 用 `has_full_history_60d=FALSE` 标记并默认剔除不完整窗口样本（OQ-011）

## 工程 / 调度

- [ ] OQ-005 物化选型：dbt（persist_docs）还是纯 `bq` SQL + 自建调度
- [ ] 将 `lookback_start_date` 从固定默认值升级为按最大滚动窗口计算 / 调度配置
- [ ] 写"从 ODS 继承字段描述"脚本（`bq show` -> 映射 -> `bq update`）
- [ ] 增量调度（dbt 或 Airflow + SQL）与数据质量断言

## 近期完成

- [x] 合并 OQ-010 策略 1 首轮质量迭代实验 PRD（PR #35）：`docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`，定义持股数/权重、调仓频率、标签 horizon、财务特征的第一轮分阶段实验矩阵；已按 review 修订 canonical baseline id、parent experiment 关系和阶段 B/C 调仓频率口径
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
