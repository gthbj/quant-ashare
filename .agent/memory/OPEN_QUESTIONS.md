# 待决问题（Open Questions）

> 本文件只保留待 owner / 维护者 / 指定决策流程解决的开放问题。已关闭问题归档到 `archive/CLOSED_QUESTIONS.md`。

待决问题需由 owner / 维护者 / 指定决策流程解决。

| ID | 问题 | 状态 | Owner | 相关文件 |
|---|---|---|---|---|
| OQ-005 | 物化与调度选型：用 dbt（含 `persist_docs` 刷描述）还是纯 `bq` SQL 脚本 + 自建调度？ | open | owner | docs §3.4, §8 |
| OQ-010 | P0 策略默认参数待确认：默认调仓频率、持股数/单票权重上限，以及后续特征/标签/选股口径。成本子项已由 `PRD_20260602_02_OQ010交易成本口径.md` 固化为佣金万一免五、卖出印花税 5 bps、买/卖滑点各 5 bps，并已在 runner SQL 中实现；策略报告已由 `PRD_20260602_03_策略1中文报告归因分析.md` 固化为评估主基准中证1000 `000852.SH`、展示对比基准沪深300 `000300.SH`，且报告中文化/交易明细/亏损归因/AI 诊断已在 PR #20 实现；`PRD_20260602_04_策略1模型质量诊断.md` 已定义先诊断 signal/label/sample/universe/portfolio/cost/style，再进入参数和模型实验，诊断 QA（`12`）已通过；`PRD_20260602_05_策略1预测池口径修正.md` 已定义并实现了 valid/test live-available 预测池口径（PR #29/30）；livepool reverse-score shadow run 已显示 raw 正类概率方向存在稳定反向风险，`PRD_20260603_01_策略1分数方向校准.md` 已实现 score orientation 校准（PR #32），oriented run 验证通过；`PRD_20260603_02_策略1首轮质量迭代实验.md` 已由 PR #35 合并，定义第一轮分阶段实验矩阵；owner 已确认阶段 A/B/C 不做 `4 * 3 * 3` 全量笛卡尔积，基础路径为 `4 + 3 + 3 = 10` 个实验，包含阶段 D 为 12 个实验，必要时再补最多 `2 * 2` A/B、A/C、B/C pairwise 小型交互复核或最多 `2 * 2 * 2` 最终保底复核；阶段 A 的 `30/5%` 表示目标持股 30 只、单票权重上限 5%，目标单票等权约 3.33%；首轮实验 runner 参数化、manifest、对比报告脚本和 horizon-aware 诊断/QA 已在 PR #37 实现并通过 dry-run，尚未合并或端到端实跑实验；首个模型训练工具链已定为 BigQuery ML + SQL runner；首个基线股票池已定为仅沪深主板，不含北交所、创业板、科创板。 | open: 成本子项、报告实现、诊断、预测池口径、分数方向校准均已完成；首轮质量迭代实验 PRD 已合并，runner 实现 PR #37 已完成 dry-run；下一步 review/合并 PR #37 后执行实验，实验结果再用于确认默认参数 | owner | docs/数据仓库建模方案-DWS-ADS.md §10; docs/A股中低频小资金机器学习策略方案.md §12; docs/策略1-ml_pv_clf_v0-runner设计.md; docs/prd/PRD_20260601_02_策略1BQML回测闭环.md; docs/prd/PRD_20260602_02_OQ010交易成本口径.md; docs/prd/PRD_20260602_03_策略1中文报告归因分析.md; docs/prd/PRD_20260602_04_策略1模型质量诊断.md; docs/prd/PRD_20260602_05_策略1预测池口径修正.md; docs/prd/PRD_20260603_01_策略1分数方向校准.md; docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md |
| OQ-011 | 策略 1 价格 DWS 是否需要补 lookback-capable 构建输入，使 2019-01 起 60 日窗口完整？当前已物化版本只读取最终 DWD/DIM，不直接打 ODS，2019 年初窗口以 `has_full_history_60d=FALSE` 显式标记并由默认样本掩码剔除。 | open | owner | docs/prd/PRD_20260601_01_策略1价格量价基础分类模型.md §3.3; docs/prd/PRD_20260601_02_策略1BQML回测闭环.md; sql/dws/02_dws_stock_feature_price_daily.sql; sql/qa/02_strategy1_dws_ads_checks.sql |
