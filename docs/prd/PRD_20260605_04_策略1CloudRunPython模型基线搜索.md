> 文档维护：GPT-5 Codex（最近更新 2026-06-05）

# PRD: 策略 1 Cloud Run Python 模型基线搜索

> 状态：实现中；本 PR 落地 Cloud Run Python LightGBM baseline search 代码、配置和 QA，完整真实 search 待合并部署后执行。
> 范围声明：本文定义策略 1 在放弃 BQML / SQL runner 作为未来执行路径后的 Cloud Run Python 模型基线搜索方案；实现阶段允许新增 Python runner、manifest、共享验收契约和 QA，但完整候选训练 / Top5 回测 / ADS 与 GCS 产物生成必须在单独执行窗口中完成。
> 关联：`docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`、`docs/prd/PRD_20260605_02_策略1CloudRun轻量Task并发.md`、`docs/prd/PRD_20260605_03_策略1Sklearn模型实验.md`、`docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`、`docs/prd/PRD_20260604_02_策略1月度滚动重训.md`、`.agent/memory/OPEN_QUESTIONS.md` OQ-010。

---

## 1. 背景

策略 1 已完成以下事实闭环：

1. 历史 BQML 最优组合为 `pv_fin_quality + 30/5% + biweekly + 5d`。
2. Ledger v1 P0/P1/P2 已完成，P1 fixed-model extended fresh run 覆盖 `2024-01-02` 至 `2026-04-30`，P2 resume 与 full fresh 在 2026 段一致。
3. Cloud Run 训练 / 回测执行器、轻量 task fan-out、GCS artifact、报告、诊断和 QA 链路已能运行。
4. sklearn native 首轮 36 个 LogisticRegression 候选已完成；Top5 均因 `test_year_excess_return<=0.0` 被 native acceptance 拒绝，未建立 `cloud_run_sklearn_native_baseline_v1`。
5. owner 已决定后续不再使用 BQML 或 `sql/ml/strategy1` SQL runner 作为策略训练、预测、回测、报告、诊断、月度滚动重训或多实验搜索的默认 / fallback / 新增开发路线；历史 BQML 只保留为 reference / audit。

因此，下一步不是继续调同一批 sklearn LogisticRegression 参数，也不是继续追 BQML parity，而是建立一条新的 Cloud Run Python 模型基线搜索流程。

本文定义该流程。

## 2. 数据截止口径

本轮 Cloud Run Python 模型基线搜索固定使用数据到：

```text
data_end_date = 2026-04-30
```

原因：

1. `2026-04-30` 已被 Ledger v1 P1/P2 验收覆盖，是当前已收口的连续扩展回测截止日。
2. owner 已明确本轮先使用到 `2026-04-30`，避免在基线搜索 PRD review 中继续移动数据边界。
3. 2026 年 5 月行情 / 特征虽然已进入 ODS/DWD/DWS，但完整 5 月 5d 标签在复核时仍有最后交易日依赖后续行情，且 2026 年 5 月尚未进入 Ledger P1/P2 固定验收窗口。
4. 为避免把最新观察期反复纳入调参，本轮不使用 2026 年 5 月数据。

后续若要把 2026 年 5 月或更晚数据纳入 final holdout，必须另开 PRD 或在本 PRD 后续版本中显式调整 `data_end_date` 和 holdout 复用规则。

## 3. 目标

### 3.1 P0 目标

1. 固定策略交易参数、股票池、成本、Ledger v1 交易语义和数据切分，只比较 Cloud Run Python 模型 backend / 模型族 / 参数。
2. 在 Cloud Run task fan-out 上运行新的 Python 模型候选搜索。
3. 优先尝试适合表格非线性特征的 LightGBM 模型族。
4. 使用 train/valid 范围内的 purged walk-forward CV 和 2024 valid confirmation 筛选 shortlist，避免用 test / final holdout 直接选参数。
5. 对 Top 5 候选跑完整预测、组合、回测、报告、诊断和 QA。
6. 输出是否建立 `cloud_run_python_baseline_v1` 的明确结论。
7. 所有产物必须可追溯到 `search_id`、`candidate_id`、`run_id`、`backtest_id`、matrix hash、container image、model artifact 和 report / diagnosis URI。

### 3.2 P1 目标

1. 如果 LightGBM 未通过接受门，扩展到 XGBoost / HistGradientBoostingClassifier / CatBoost 等模型族。
2. 如果模型信号仍弱，再引入 `dws_market_state_daily` 等市场状态特征后的第二轮特征搜索。
3. 通过 accepted baseline 后，改造月度滚动重训 PRD，使其消费 Cloud Run Python model registry / prediction stream。

## 4. 非目标

1. 不新增或扩展 BQML 训练、预测、回测或报告路径。
2. 不把 `sql/ml/strategy1` SQL runner 作为 fallback。
3. 不改变 DWD/DWS 数仓事实口径。
4. 不改变首轮固定交易参数：`pv_fin_quality + 30/5% + biweekly + 5d`。
5. 不改变首个基线股票池：仅沪深主板，不含北交所、创业板、科创板。
6. 不改变成本口径：佣金万一免五、卖出印花税 5 bps、买 / 卖滑点各 5 bps。
7. 不改变 Ledger v1 交易执行语义。
8. 不把 2026 final holdout 用于参数排名。
9. 不在模型基线未建立前继续大规模调持股数、调仓频率、权重上限或标签 horizon。
10. 不引入本地训练、GPU、Ray、Dask、Spark 或深度学习。

## 5. 固定实验口径

### 5.1 数据切分

本轮固定切分：

| split | 日期范围 | 用途 |
|---|---|---|
| train | `2019-04-03` 至 `2023-12-31` | 训练模型、fit 预处理统计量 |
| valid | `2024-01-02` 至 `2024-12-31` | 候选排序、阈值选择、score orientation、TopK 筛选 |
| test | `2025-01-02` 至 `2025-12-31` | 样本外接受门，不参与参数选择 |
| final_holdout | `2026-01-05` 至 `2026-04-30` | 最新市场环境风险复核，不参与参数选择 |
| overall_report | `2024-01-02` 至 `2026-04-30` | 报告展示、长期收益和风险汇总 |

`2019-04-03` 是现有策略训练面板剔除 2019 年初 60 日窗口不完整样本后的可训练起点。实现不得简写为 `2019-01-01`。

### 5.2 固定交易参数

| 参数 | 值 |
|---|---|
| `strategy_id` | `ml_pv_clf_v0` |
| `feature_set_id` | `strategy1_pv_fin_quality_v0_20260603` |
| `label_horizon` | 5d |
| 持股数 | 30 |
| 单票权重上限 | 5% |
| 调仓频率 | `biweekly` |
| 初始资金 | 沿用现有 runner / Cloud Run 默认 |
| 成本 profile | 佣金万一免五、卖出印花税 5 bps、买 / 卖滑点各 5 bps |
| 评估主基准 | 中证1000 `000852.SH` |
| 展示对比基准 | 沪深300 `000300.SH`、上证50、必要时中证1000 |
| 回测语义 | Ledger v1 |

### 5.3 固定股票池

沿用当前策略 1 基线股票池：

1. 仅沪深主板。
2. 不含北交所。
3. 不含创业板。
4. 不含科创板。
5. 保留退市股历史区间，避免幸存者偏差。
6. 停牌、一字板、ST、上市未满 N 日等仍按现有 universe / mask 口径处理。

## 6. 搜索波次

### 6.1 历史波次

已完成波次：

| 波次 | 模型族 | search_id | 结论 |
|---|---|---|---|
| wave 1 | sklearn LogisticRegression | `sklearn_native_pvfq_n30_bw_h5_20260605_01` | Top5 全部 rejected，不建立 baseline |

本文从 `model_search_wave_no=2` 开始。

### 6.2 Wave 2: LightGBM

P0 默认模型族为：

```text
model_family = lightgbm_gbdt
library = lightgbm
objective = binary
label = label_top30_5d
score = calibrated / oriented positive-class probability
```

推荐理由：

1. 当前特征是结构化表格数据，LightGBM 对非线性、特征交互、缺失值和尺度差异更友好。
2. 相比深度学习，LightGBM 在当前数据规模、日线频率和 CPU Cloud Run 环境下更实用。
3. 相比继续调 LogisticRegression，LightGBM 更可能解决线性模型无法表达的信号形态。

Wave 2 P0 固定运行 40 个候选，不再使用 `40-80` 的范围表达，也不做完整笛卡尔积。40 是本轮 owner 确认的执行规模：足够覆盖人工分层参数空间，同时与计划提升后的 Cloud Run `50 vCPU / 200Gi` 区域配额和 `candidate_parallelism=40` 对齐。

候选 manifest 应人工分层覆盖以下维度：

| 维度 | 推荐取值 |
|---|---|
| `num_leaves` | 15, 31, 63 |
| `learning_rate` | 0.02, 0.05, 0.10 |
| `n_estimators` | 100, 300, 600 |
| `min_data_in_leaf` | 100, 300, 800 |
| `feature_fraction` | 0.7, 0.9, 1.0 |
| `bagging_fraction` | 0.7, 0.9, 1.0 |
| `lambda_l1` | 0, 0.1, 1.0 |
| `lambda_l2` | 0, 0.1, 1.0 |
| `is_unbalance` / `scale_pos_weight` | 默认不用；只在候选 manifest 中少量对照 |

每个候选必须固定 `random_state`，并记录 `num_threads`、`deterministic` 或等价可复现参数。若 LightGBM 版本不支持完全 deterministic，必须在候选 artifact 中记录库版本和随机种子。

P0 固定并发口径：

| 参数 | P0 固定值 |
|---|---|
| `candidate_count` | 40 |
| `candidate_parallelism` | 40 |
| `candidate_task_cpu` | 1 vCPU |
| `candidate_task_memory` | 4Gi |
| 计划区域配额 | 50 vCPU / 200Gi |

每个 candidate 对应一个轻量 Cloud Run Job task；默认 `--tasks=40 --parallelism=40`，owner 显式限流时才降低 `candidate_parallelism`。40 个 task 理论峰值为 40 vCPU / 160Gi，50 vCPU / 200Gi 配额提供 10 vCPU / 40Gi 余量。若 LightGBM CV smoke 证明单 task 4Gi 不够，应提高单 task 内存并同步降低并发或重新申请更高配额，不能在未更新资源口径的情况下静默超配。

P0 必须启用 §8.2 的 purged walk-forward CV 排名确认，不能只用单一年份 2024 valid 从 40 个候选中选 Top 5。若实现阶段暂不支持 CV，本轮 search 不得登记 `accepted` baseline。若后续要扩到 60 / 80 / 100 个候选，必须另行更新 PRD、candidate manifest、Cloud Run 配额和 test reuse 记录；本文 P0 不允许 `candidate_count > 40`。

### 6.3 Wave 3: 备选模型族

若 Wave 2 没有 accepted 候选，P1 进入 Wave 3。Wave 3 优先先做同一 LightGBM 管线内的目标函数对照，再考虑换模型库：

| 优先级 | 模型族 | 说明 |
|---|---|---|
| P1-A | `lightgbm_regression` | 预测未来横截面收益或收益排名，仍输出逐行标量分，兼容现有 orientation / TopN / RankIC 契约，是 binary LightGBM 后最便宜的目标对齐对照 |
| P1-B | `xgboost_hist` | 更强的树模型对照，需引入 `xgboost` 依赖 |
| P1-C | `sklearn_hist_gradient_boosting` | 依赖更轻，但能力通常弱于 LightGBM / XGBoost |
| P2 | `catboost` | 可作为后续外部库对照，P0 不引入 |

Wave 3 复用同一 2025 test 和 2026 final holdout 时，必须遵守 §10 的 test / holdout 复用约束。

### 6.4 Wave 4: 特征增强

如果 Wave 2/3 均未建立 accepted baseline，下一步不是继续盲目扩大模型网格，而是补策略特征：

1. 先实现 `dws_market_state_daily`。
2. 增加市场趋势、波动率、宽度、流动性、基准强弱等市场状态特征。
3. 重新冻结 `feature_set_id`，再跑新一轮模型搜索。

Wave 4 需要单独 PRD 或本 PRD 修订版，不在 P0 直接实现。

### 6.5 Objective 路线

P0 仍使用：

```text
objective = binary
label = label_top30_5d
```

原因是当前 Cloud Run Python runner、候选池、报告和 acceptance gate 已以“正类概率排序分”为契约，直接切换到 ranking objective 会牵涉按交易日分组的训练矩阵、score 可比性、模型解释和 QA 字段改造。

但 PRD 必须承认：`label_top30_5d` 是二分类标签，而 RankIC / top-minus-bottom 是排序质量指标，两者并不完全一致。因此：

1. Wave 2 P0 先用 binary LightGBM 建立可运行基线。
2. 若 binary LightGBM rejected，Wave 3 首选 `lightgbm_regression`。它仍是逐行标量分，不需要 `trade_date` group 管线，能复用现有 orientation / 选股 / RankIC / 报告契约。
3. `lightgbm_lambdarank` 或 XGBoost ranking 属于更重的后续路线；引入 ranking objective 前，必须先定义按 `trade_date` 分组的训练数据契约、eval group 契约、score orientation 契约和对应 QA。

## 7. 预处理与矩阵

### 7.1 Tree 模型预处理

Wave 2 默认：

```text
preprocess_version = tree_winsor_missing_passthrough_v1
```

规则：

1. 只使用 train split 计算 winsor 分位点。
2. 数值特征按 train split 的 `p0.1` / `p99.9` 或 manifest 显式分位点 winsor。
3. 不做 zscore；树模型不需要统一尺度。
4. 缺失值保留为 `NaN`，由 LightGBM 处理。
5. valid/test/final_holdout/predict 只应用 train split 的 winsor 边界。
6. 所有预处理统计量写入 `preprocess_stats.json`。

### 7.2 Frozen matrix

继续复用 Cloud Run 轻量 task fan-out 架构：

```text
01_build_training_panel.sql
  -> prepare_matrix
  -> train_candidate_fanout
  -> rank_candidates
  -> top5_predict_backtest_report
  -> compare_candidates
  -> select_cloudrun_python_baseline
```

`prepare_matrix` 必须一次性生成覆盖 train / valid / test / final_holdout / predict 的 frozen matrix。candidate task 不允许各自重复扫描 BigQuery 全量训练面板。

矩阵 manifest 必须记录：

| 字段 | 说明 |
|---|---|
| `data_end_date` | 必须为 `2026-04-30` |
| `train_start_date` | `2019-04-03` |
| `train_end_date` | `2023-12-31` |
| `valid_start_date` / `valid_end_date` | 2024 全年交易日 |
| `test_start_date` / `test_end_date` | 2025 全年交易日 |
| `final_holdout_start_date` / `final_holdout_end_date` | `2026-01-05` 至 `2026-04-30` |
| `feature_set_id` | 本轮固定 feature set |
| `label_horizon` | 5d |
| `feature_schema_hash` | 特征列顺序和类型 hash |
| `matrix_hash` | 数据内容 / schema / split 的可追溯 hash |

## 8. 候选筛选流程

### 8.1 Candidate fan-out

每个 candidate task 只负责：

1. 读取自己的 candidate 参数。
2. 读取 frozen train / valid matrix。
3. 训练模型。
4. 输出 valid 预测分、candidate metrics、model artifact 和 task status。

candidate task 不写 ADS selected registry，不写正式 prediction，不跑回测。

P0 candidate fan-out 固定以 40 个 task 单批启动：

```text
candidate_count = 40
candidate_parallelism = 40
candidate_task_cpu = 1
candidate_task_memory = 4Gi
```

40 并发只覆盖 candidate 训练、CV 预测和 valid metrics 计算。`prepare_matrix` 必须在 fan-out 前单独完成；Top 5 的正式预测、组合、回测、报告和诊断必须在 reducer 选型后执行，不与 40 个 candidate task 混在同一批并发里。

### 8.2 候选排序: CV + valid confirmation

候选排序不得使用 2025 test 或 2026 final_holdout。默认排序证据来自 train/valid 范围内：

1. `2021` / `2022` / `2023` 三个独立 purged walk-forward CV folds。
2. 2024 valid confirmation。

推荐 CV folds：

| fold | 训练窗口 | 评价窗口 |
|---|---|---|
| `cv_2021` | `2019-04-03` 至 `2020-12-31` | `2021-01-01` 至 `2021-12-31` |
| `cv_2022` | `2019-04-03` 至 `2021-12-31` | `2022-01-01` 至 `2022-12-31` |
| `cv_2023` | `2019-04-03` 至 `2022-12-31` | `2023-01-01` 至 `2023-12-31` |

每个 fold 的评价窗口前必须按 `label_horizon` 设置 embargo。本轮 `label_horizon=5d`，默认 embargo 为 5 个 SSE 交易日；实现可按实际标签窗口扩大，但不得小于 5 个交易日。

`cv_2021` 的训练窗口较短，参与三折排序稳定性计算，但不得单独一票否决候选；候选是否进入 Top 5 仍以三折聚合指标、2024 valid confirmation 和 §9 机器门槛共同决定。

2024 仍是固定 valid split，但不再重复命名为 `cv_2024`。它用于最新年度 confirmation、score orientation 和 Top 5 最低门槛，不计入独立 CV fold 数。

主排序规则：

1. `cv_rank_ic_mean` 降序。
2. `cv_top_minus_bottom_fwd_ret_mean` 降序。
3. `valid_rank_ic_mean` 降序。
4. `valid_top_minus_bottom_fwd_ret_mean` 降序。
5. `valid_icir` 降序。
6. `valid_auc` 降序。
7. 在前六项接近时，优先更低 turnover proxy 和更简单模型。

进入 Top 5 的最低门槛：

1. `cv_confirmation_status='passed'`。
2. `valid_rank_ic_mean > 0`。
3. `valid_top_minus_bottom_fwd_ret_mean > 0`。
4. `valid_signal_status='stable'`。
5. candidate 训练状态为 `succeeded`。
6. 模型收敛 / early stopping 状态不得为失败。

若没有任何候选满足门槛，本轮 search 直接输出 `failed_no_positive_valid_signal`，不跑完整回测。

### 8.3 Top 5 完整回测

只有 Top 5 候选进入完整链路：

1. 写 `ads_model_registry` 候选记录。
2. 对 valid/test/final_holdout/predict 窗口写预测分。
3. 生成候选池、目标组合、订单计划。
4. 运行 Ledger v1 回测。
5. 生成中文报告、交易明细、持仓、NAV、benchmark 对比、亏损归因和诊断。
6. 运行策略 runner QA、模型诊断 QA 和本 PRD 新增 QA。

## 9. 接受标准

### 9.1 共享验收契约

为避免本 PRD 与 `PRD_20260605_03_策略1Sklearn模型实验.md` 的验收门槛继续漂移，P0 实现必须把模型接受门槛落成共享配置：

```text
configs/strategy1/model_acceptance_contract_v1.yml
```

本文 §9 的阈值是该契约的默认值；后续模型搜索、月度滚动重训和 baseline registry 均应引用同一契约版本，而不是在各 PRD / SQL / Python 中各写一份。

该契约必须取代 `PRD_20260605_03_策略1Sklearn模型实验.md` / PR #71 实现中的内联阈值。P0 实现时必须同步迁移：

1. `scripts/strategy1_cloudrun/*` 中 sklearn native search 的 `decide_acceptance` 或等价接受判断函数。
2. `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`。
3. 本 PRD 新增的 `19_qa_cloudrun_python_baseline_search_outputs.sql`。

Python 与 SQL 可通过“YAML -> JSON artifact / BigQuery 参数表 / generated SQL include”等方式读取同一契约版本；允许实现层选择机制，但不允许继续维护多份手写阈值字面量。

### 9.2 状态枚举

每个 Top 5 候选最终状态：

| 状态 | 含义 |
|---|---|
| `accepted` | 可登记为 `cloud_run_python_baseline_v1` |
| `needs_more_evidence` | 未命中 hard reject，但 CV / holdout 样本量 / test 复用等必要证据不足，需要 owner 决策或后续数据 |
| `rejected` | 明确不接受 |
| `failed` | 执行失败，不参与模型结论 |

### 9.3 状态机优先级

状态决策必须互斥、完整、机器可校验，按以下优先级执行：

1. 执行失败、artifact 缺失或 QA 运行失败：`failed`。
2. 命中任一 hard reject 条件：`rejected`。
3. 未命中 hard reject，但缺少必要证据：`needs_more_evidence`。
4. 满足全部 accepted 条件：`accepted`。
5. 任何未被上述规则覆盖的边界值或未知组合：`rejected`，并写 `acceptance_reason='unmatched_acceptance_state'`。

所有边界必须显式处理。`RankIC == 0`、`top_minus_bottom == 0`、`test_year_excess_return == 0` 均不得落入未定义状态。

### 9.4 Accepted 机器门槛

候选登记为 `accepted` 必须同时满足：

| 领域 | 字段 | 门槛 |
|---|---|---|
| CV | `cv_confirmation_status` | `passed` |
| valid | `valid_rank_ic_mean` | `> 0` |
| valid | `valid_top_minus_bottom_fwd_ret_mean` | `> 0` |
| valid | `valid_signal_status` | `stable` |
| test | `test_rank_ic_mean` | `> 0` |
| test | `test_top_minus_bottom_fwd_ret_mean` | `> 0` |
| test | `test_year_excess_return_vs_000852` | `> 0` |
| overall | `overall_excess_return_vs_000852` | `> 0` |
| overall | `total_return` | `> 0` |
| risk | `sharpe` | `>= 0.70` |
| risk | `max_drawdown` | `>= -25%` |
| final_holdout | `final_holdout_excess_return_vs_000852` | `> -5pct` |
| final_holdout | `final_holdout_total_return` | `> -8%` |
| diagnosis | `primary_diagnosis` / `model_quality_status` | 不得为失败状态 |
| QA | runner / diagnosis / search QA | 全部通过 |

`final_holdout_excess_return_vs_000852` 不再要求 `>=0`。2026 final_holdout 只有约一个季度，重平衡次数少，不能作为“必须跑赢”的硬接受门；它只作为明显坏结果 veto 和风险观察。若 final holdout 为负但未触发 hard reject，候选仍可 `accepted`，但必须写：

```text
holdout_watch_flag = TRUE
```

并在 comparison report / baseline registry 中展示原因。

### 9.5 Needs-more-evidence

任一条件触发即 `needs_more_evidence`，不得登记为正式 baseline：

1. `cv_confirmation_status!='passed'`。
2. final_holdout 可交易调仓次数或有效交易日数低于契约最低样本要求，导致 2026 风险复核不可解释。
3. `test_reuse_wave_no > 3` 且没有新增最终 holdout 证据。
4. acceptance contract 版本缺失或阈值无法复现，但候选本身没有命中 hard reject。

### 9.6 Hard reject

任一条件触发即 `rejected`：

| 领域 | 条件 |
|---|---|
| valid | `valid_rank_ic_mean <= 0` |
| valid | `valid_top_minus_bottom_fwd_ret_mean <= 0` |
| valid | `valid_signal_status != 'stable'` |
| test | `test_rank_ic_mean <= 0` |
| test | `test_top_minus_bottom_fwd_ret_mean <= 0` |
| test | `test_year_excess_return_vs_000852 <= 0` |
| overall | `overall_excess_return_vs_000852 <= 0` |
| overall | `total_return <= 0` |
| risk | `sharpe < 0.70` |
| risk | `max_drawdown < -25%` |
| final_holdout | `final_holdout_excess_return_vs_000852 <= -5pct` |
| final_holdout | `final_holdout_total_return <= -8%` |
| diagnosis | `signal_inverted`、`unusable_signal`、`sample_filter_risk high` 或等价失败状态 |
| QA | runner / diagnosis / search QA 任一失败 |

## 10. Test / holdout 复用约束

2025 test 已在 sklearn LogisticRegression wave 1 中使用过。本 PRD 的 LightGBM 是新的模型族波次，因此：

```text
test_reuse_wave_no = 2
```

实现要求：

1. 每个 search 必须记录 `test_reuse_wave_no`。
2. 每个 search 必须记录 `test_reuse_approval_ref`，可指向本 PRD / PR。
3. 2025 test 不参与 candidate 排名，只参与 Top 5 接受门。
4. 2026 final_holdout 不参与 candidate 排名，只参与明显坏结果 veto、风险 watch 和报告复核；不要求正超额作为硬接受门。
5. 如果后续进入 `test_reuse_wave_no > 3`，必须新增最终 holdout 证据，不能继续只依赖 2025 test + 2026-04-30 holdout。
6. 若 owner 明确把 2026 年 5 月及之后数据加入 holdout，应新增 `final_holdout_status` 或等价机器可校验字段，供 QA 判断是否允许 accepted。

## 11. 产物契约

### 11.1 GCS 路径

推荐路径：

```text
gs://ashare-artifacts/models/strategy1/ml_pv_clf_v0/
  search_id=<search_id>/
    matrix/
    candidates/<candidate_id>/
    topk/
    comparison/

gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/
  search_id=<search_id>/
    candidate_id=<candidate_id>/
      run_id=<run_id>/
      backtest_id=<backtest_id>/
```

### 11.2 BigQuery / ADS

实现可以复用现有 ADS 表，但必须能表达：

| 字段 | 说明 |
|---|---|
| `model_backend` | `cloud_run_python` |
| `model_family` | `lightgbm_gbdt` / `xgboost_hist` / etc. |
| `model_library` | `lightgbm` / `xgboost` / `sklearn` |
| `model_library_version` | Python package version |
| `search_id` | 本轮搜索 ID |
| `candidate_id` | 候选 ID |
| `model_search_wave_no` | 本轮为 2 |
| `test_reuse_wave_no` | 本轮为 2 |
| `acceptance_contract_version` | 本轮为 `model_acceptance_contract_v1` |
| `cv_confirmation_status` | `passed` / `missing` / `failed` |
| `holdout_watch_flag` | final holdout 轻微跑输但未触发 hard reject 时为 TRUE |
| `data_end_date` | `2026-04-30` |
| `final_holdout_start_date` | `2026-01-05` |
| `final_holdout_end_date` | `2026-04-30` |
| `native_baseline_status` | `accepted` / `needs_more_evidence` / `rejected` / `failed` |
| `acceptance_reason` | 机器可读原因 |

若现有 ADS 表缺字段，P0 可先把扩展字段写入 JSON artifact 和 comparison table；进入正式 baseline 前必须补 ADS 可查询字段或维护独立 baseline registry 表。

## 12. QA

新增 QA 建议：

```text
sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql
```

最低断言：

1. `search_id` 存在且 Top 5 候选数量符合配置。
2. matrix `data_end_date = 2026-04-30`。
3. train / valid / test / final_holdout 日期边界完全符合 §5.1。
4. 不存在 `trade_date > 2026-04-30` 的候选预测、组合、回测或诊断行。
5. 所有 candidate artifact 有 `model_family`、`model_library`、`model_library_version`、`candidate_id`、`matrix_hash`。
6. Top 5 候选均有完整 report / diagnosis URI。
7. `accepted` 候选必须满足 §9.4 所有机器门槛。
8. `needs_more_evidence` 候选不得被登记为 `cloud_run_python_baseline_v1`。
9. `rejected` 候选必须有至少一条机器可读拒绝原因。
10. 若 `test_reuse_wave_no > 3`，必须存在 `final_holdout_status='passed'` 或等价证据字段。
11. BQML / SQL runner 不得写入本轮 search 的新 baseline 状态。
12. 所有 report / diagnosis / comparison artifact URI 必须在 GCS 存在。
13. `native_baseline_status` 不得出现 §9 未覆盖的状态组合；未知组合必须被拒绝并写 `unmatched_acceptance_state`。
14. 本轮 search 必须记录 `candidate_count=40`、`candidate_parallelism=40`、candidate task 资源为 1 vCPU / 4Gi；`accepted` 候选必须有 `cv_confirmation_status='passed'`。
15. `final_holdout_excess_return_vs_000852 < 0` 或 `final_holdout_total_return < 0` 但未触发 hard reject 时，必须写 `holdout_watch_flag=TRUE`。
16. `18_qa_sklearn_native_search_outputs.sql` 与 `19_qa_cloudrun_python_baseline_search_outputs.sql` 必须能追溯到同一 `acceptance_contract_version`，不得继续各自硬编码相同阈值。

## 13. 实施顺序

### Phase A: PRD 合并

1. 合并本文。
2. 确认 owner 接受 LightGBM 作为 P0 新依赖。
3. 确认本轮截止日期固定为 `2026-04-30`。

### Phase B: 代码实现

1. 新增共享验收配置 `configs/strategy1/model_acceptance_contract_v1.yml`。
2. 新增契约加载 / 物化机制，使 Python acceptance 和 SQL QA 使用同一契约版本。
3. 先迁移现有 sklearn native search 的 `decide_acceptance` 和 `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`，用共享契约取代 PR #71 的内联阈值。
4. 容器镜像加入 `lightgbm` 依赖。
5. 扩展 candidate manifest schema，支持 `model_family=lightgbm_gbdt` 与后续 `lightgbm_regression`。
6. 扩展 `train_candidate_fanout`，支持 LightGBM 训练、CV / valid 预测和 metrics。
7. 扩展 reducer / ranking / Top5 完整回测流程。
8. 增加 search comparison artifact 和 baseline acceptance 写入。
9. 增加 `19_qa_cloudrun_python_baseline_search_outputs.sql`。

### Phase C: 真实执行

1. 使用固定口径生成 search：

```text
search_id = cloudrun_python_lgbm_pvfq_n30_bw_h5_20260605_01
```

2. 复核 `strategy1-train-candidate-fanout-job` 共享 Job spec 为 `parallelism=40`，candidate task 资源为 1 vCPU / 4Gi；若不一致，先更新 Job 配置再执行 search。
3. 一次 prepare matrix。
4. 40 个 LightGBM candidate task fan-out，默认 `--tasks=40 --parallelism=40`。
5. 三折 CV + 2024 valid confirmation 选 Top 5。
6. Top 5 完整回测到 `2026-04-30`。
7. 跑 `10` / `12` / `19` QA。
8. 输出是否建立 `cloud_run_python_baseline_v1`。

### Phase D: 后续决策

1. 若 accepted：登记 `cloud_run_python_baseline_v1`，再改造月度滚动重训 PRD。
2. 若 needs_more_evidence：等待更多 holdout 或由 owner 决定是否 research-only。
3. 若 rejected：先进入 Wave 3 的 `lightgbm_regression` 目标函数对照；若仍 rejected，再进入 XGBoost / HistGradientBoosting 或先补 `dws_market_state_daily` 后再搜索。

## 14. 风险与控制

| 风险 | 控制 |
|---|---|
| 反复看 test / final holdout 导致过拟合 | 三折 CV + 2024 valid confirmation 排名；记录 `test_reuse_wave_no`；超过 3 波必须新增 holdout |
| 单一年份 valid 从 40 个候选中选参方差过高 | P0 必须启用 2021 / 2022 / 2023 purged walk-forward CV + 2024 valid confirmation；未启用则不得 accepted |
| 共享契约与旧实现硬编码并存导致继续漂移 | Phase B 必须先迁移 sklearn `decide_acceptance` 和 `18_qa`，再实现新 LightGBM acceptance |
| LightGBM 依赖增加镜像复杂度 | 只在 Cloud Run Python runner 镜像加入，不影响数仓 SQL |
| 候选太多导致成本上升 | 一次 prepare matrix；candidate task 轻量并发；只让 Top 5 跑完整回测 |
| final_holdout 过短导致误判 | final_holdout 只做明显坏结果 veto 和风险 watch；不要求正超额作为硬接受门 |
| 模型通过但解释性下降 | 通过因子贡献度 / permutation 或后续 SHAP PRD 补解释，不用线性系数解释树模型 |
| 二分类训练目标与排序评估指标不完全一致 | P0 先保留 binary 兼容当前链路；若 rejected，优先用 `lightgbm_regression` 做低成本目标对齐对照，再考虑 group-based ranking |
| 高换手候选只靠交易活跃勉强净正 | P0 暂不设换手硬门，先在 comparison report 中展示 turnover / cost / economic cost watch；若真实候选暴露该问题，再把阈值加入共享契约 |
| 月度重训 PRD 仍是旧口径 | accepted baseline 前不实现月度重训；accepted 后先改造 PRD |

## 15. 验收标准

本文合并后的验收标准：

1. PRD 明确后续不使用 BQML / SQL runner 作为新增模型搜索路径。
2. PRD 明确本轮数据截止到 `2026-04-30`。
3. PRD 明确 train / valid / test / final_holdout 分段。
4. PRD 明确 LightGBM 为 P0 默认新模型族。
5. PRD 明确候选排序使用三折 CV + 2024 valid confirmation，不使用 test / final_holdout 选参。
6. PRD 明确 2026 final_holdout 不参与参数排名，只作为明显坏结果 veto 和风险 watch。
7. PRD 明确 accepted / needs_more_evidence / rejected 互斥完整的机器化标准。
8. PRD 明确共享验收契约必须取代 sklearn `decide_acceptance` / `18_qa` 的内联阈值。
9. PRD 明确若 binary LightGBM rejected，下一步优先尝试 `lightgbm_regression`，再考虑 XGBoost / 特征增强。
10. PRD 明确 `strategy1-train-candidate-fanout-job` 需配置为 `parallelism=40` 后再执行本轮 search。
11. PRD 明确新增 QA 和产物契约。
12. TODO / 记忆同步到新的 OQ-010 下一步。
