> 文档维护：GPT-5 Codex（最近更新 2026-06-09）

# PRD: 策略 1 旧 BQML / SQL Runner 退役

> 状态：草案，待 owner review。
> 范围声明：本文只定义 Strategy1 旧 BigQuery ML / SQL runner 的退役与删除计划，不在本 PR 删除代码、不运行 BigQuery / Cloud Run、不覆盖任何历史实验产物。
> 关联：`docs/策略1-ml_pv_clf_v0-runner设计.md`、`docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`、`docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`、`docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`、`configs/strategy1/model_acceptance_contract_v3.yml`、`.agent/memory/OPEN_QUESTIONS.md` OQ-010。

---

## 1. 背景

Strategy1 早期实现路径是 BigQuery ML + SQL runner：

```text
sql/ml/strategy1/01-10
```

该路径负责：训练面板、BQML logistic candidate、`ML.PREDICT`、候选池、组合目标、订单计划、SQL ledger、报告输入和 `10` QA。

后续 owner 已明确：

```text
不再使用 BQML 或 sql/ml/strategy1 SQL runner 作为策略执行层默认 / fallback / 新增开发路线。
```

当前实际策略搜索和验收主线已切到 Cloud Run Python runner + v3 acceptance gate。旧 BQML / SQL runner 仍留在仓库中，主要价值只剩 historical reference / audit。继续保留完整可执行主链会带来三个问题：

1. 新 agent 容易误以为 BQML / SQL runner 仍是可选 fallback。
2. 旧 `01-10` 与当前 Cloud Run Python / v3 gate 的执行语义继续分叉，增加维护成本。
3. 后续 Strategy1 cleanup 时很难区分“仍在用的 Cloud Run QA”和“已退役的 BQML 主链”。

本文定义退役边界。

## 2. 目标

1. 明确旧 BQML / SQL runner 主链不再作为 active execution path。
2. 删除或归档仍可误触发旧 BQML / SQL runner 的代码入口。
3. 保留当前 Cloud Run Python / v3 acceptance 所需的 QA、replay、contract 和历史审计字段。
4. 保留历史实验结果的可解释性：旧 BQML run / backtest id、历史报告、GCS artifact 和 ADS 已写结果不因代码删除而失去说明。
5. 删除后，仓库内不应再存在“可直接按旧 SQL runner 顺序跑出新 production baseline”的路径。

## 3. 非目标

1. 不删除 BigQuery 中已存在的历史 ADS 结果、BQML model object 或 GCS artifact。
2. 不重算历史 BQML baseline。
3. 不改变当前 Cloud Run Python runner、v3 gate、v3 replay 或 live search 逻辑。
4. 不删除 `sql/ml/strategy1` 整个目录；该目录下仍有当前 Cloud Run / v3 QA SQL。
5. 不把历史 BQML 文档伪装成当前方案；旧文档应标记为 historical / retired，而不是静默删除所有上下文。

## 4. 退役原则

### 4.1 当前 active path

当前 Strategy1 active path 固定为：

```text
Cloud Run Python training / prediction / backtest
  -> ADS registry / summary / artifacts
  -> v3 acceptance gate
  -> 19/21/24 等 QA / replay
```

BQML / SQL runner 不再是：

1. 默认执行路径。
2. fallback 路径。
3. 新模型搜索入口。
4. production accepted baseline 写回入口。

### 4.2 历史审计必须保留

以下内容不得因 runner 代码删除而丢失语义：

| 类型 | 处理 |
|---|---|
| 历史 BQML run / backtest id | 保留在文档、记忆和 ADS 历史数据中 |
| 历史 GCS report / diagnosis artifact | 不删除 |
| `bqml_reference_*` 字段 | 先保留；只有确认当前代码和报告不再读取后才能重命名或删除 |
| BQML 设计 PRD | 改为 historical / retired 说明，不作为 active runbook |

## 5. 删除范围

### 5.1 P0 删除候选：旧 SQL runner 主链

以下脚本属于旧 BQML / SQL runner 主链，P0 删除候选：

| 文件 | 旧职责 | 处理 |
|---|---|---|
| `sql/ml/strategy1/01_build_training_panel.sql` | 旧 BQML 训练面板 | 删除候选 |
| `sql/ml/strategy1/02_train_bqml_logistic_candidates.sql` | `CREATE MODEL` BQML logistic 候选 | 删除候选 |
| `sql/ml/strategy1/03_select_model_and_register.sql` | BQML valid 选择与 registry 写回 | 删除候选 |
| `sql/ml/strategy1/04_predict_daily.sql` | `ML.PREDICT` 预测写回 | 删除候选 |
| `sql/ml/strategy1/05_build_candidates.sql` | 旧候选池构建 | 删除候选 |
| `sql/ml/strategy1/06_build_portfolio_targets.sql` | 旧组合目标构建 | 删除候选 |
| `sql/ml/strategy1/07_build_order_plan.sql` | 旧订单计划 | 删除候选 |
| `sql/ml/strategy1/08_run_backtest.sql` | 旧 BigQuery SQL ledger | 删除候选 |
| `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql` | 旧报告输入 / summary | 删除候选 |
| `sql/ml/strategy1/10_qa_runner_outputs.sql` | 旧 runner QA | 删除候选 |

删除前必须确认 Cloud Run Python 路径没有直接 shell / SQL 调用这些文件。

### 5.2 P0 删除候选：旧实验调度入口

| 文件 | 旧职责 | 处理 |
|---|---|---|
| `scripts/strategy1/run_oq010_experiments.py` | 调度旧 `01-10` SQL runner / BQML experiment | 删除候选；若仍有 historical report 依赖，先拆出只读查询 helper |

### 5.3 P1 评估后处理

以下文件不在 P0 直接删除，先查依赖：

| 文件 | 原因 | P1 处理 |
|---|---|---|
| `sql/ml/strategy1/11_model_quality_diagnostics.sql` | 旧模型诊断可能仍被历史报告引用 | 依赖清空后删除或改 historical |
| `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql` | 旧诊断 QA | 依赖清空后删除或改 historical |
| `sql/ml/strategy1/14_qa_factor_attribution_outputs.sql` | 因子归因 QA，可能仍用于历史 BQML artifact | 先保留 |
| `sql/ml/strategy1/15_qa_ledger_resume_consistency.sql` | 旧 SQL ledger resume QA；当前后续可能需要 Cloud Run resume 对照 | 先保留，等 Cloud Run resume QA 明确后再处理 |
| `scripts/strategy1/attribute_factor_contribution.py` | 读取 selected BQML model 系数 | 若只服务历史 BQML，改 historical 或删除 |
| `scripts/strategy1/diagnose_acceptance_window.py` | 仍读取 BQML historical reference 做只读诊断 | 先保留，但文档明确“不重跑 BQML” |

## 6. 必须保留范围

以下文件 / 目录不得在本次退役中删除：

| 范围 | 保留原因 |
|---|---|
| `sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql` | Cloud Run runner QA |
| `sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql` | Cloud Run orchestrator QA |
| `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql` | sklearn native search 历史 / QA |
| `sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql` | 当前 Cloud Run Python live search QA |
| `sql/ml/strategy1/20_qa_tail_risk_outputs.sql` | 尾部风险 QA |
| `sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql` | risk-feature search QA |
| `sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql` | v2 historical diagnosis QA |
| `sql/ml/strategy1/23_qa_lot_aware_ledger_outputs.sql` | lot-aware ledger QA |
| `sql/ml/strategy1/24_qa_acceptance_gate_v3_replay_outputs.sql` | v3 replay QA |
| `configs/strategy1/model_acceptance_contract_v3.yml` | 当前 acceptance contract |
| `scripts/strategy1/replay_acceptance_gate_v3.py` | 当前 v3 replay helper |
| `scripts/strategy1/run_acceptance_gate_v3_replay_qa.py` | 当前 v3 QA helper |
| `scripts/strategy1_cloudrun/**` | 当前 Cloud Run Python execution path |

## 7. 文档处理

### 7.1 保留但标记 retired

以下文档保留，但应在文首补充 historical / retired 标记：

1. `docs/策略1-ml_pv_clf_v0-runner设计.md`
2. `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`
3. `sql/ml/strategy1/README.md` 中关于 `01-10` 的 active run instructions

推荐文案：

```text
本文记录历史 BQML / SQL runner 方案；该路径已退役，不再作为 Strategy1 默认、fallback 或新增开发路线。当前 active path 为 Cloud Run Python runner + v3 acceptance gate。
```

### 7.2 保留历史结果说明

历史 BQML baseline 结果继续保留为 reference：

| 项 | 值 |
|---|---|
| run_id | `s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01` |
| backtest_id | `bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01` |
| 用途 | historical reference / audit |

删除代码后，文档必须仍能解释这些历史 run 为什么存在。

## 8. 执行计划

### 8.1 P0-A: 依赖审计

先做只读依赖审计：

1. 搜索所有 `sql/ml/strategy1/01_` 至 `10_` 的引用。
2. 搜索 `ML.PREDICT`、`CREATE MODEL`、`run_oq010_experiments.py` 的引用。
3. 搜索 Cloud Run Python path 是否仍调用旧 SQL runner 文件。
4. 输出保留 / 删除清单。

### 8.2 P0-B: 删除旧主链

在确认无 active dependency 后删除：

1. `sql/ml/strategy1/01-10`。
2. `scripts/strategy1/run_oq010_experiments.py`，或先拆出仍需的只读 helper 后删除调度入口。
3. README 中旧 active runbook 命令。

### 8.3 P0-C: 文档与记忆收口

1. 给历史 BQML 设计文档加 retired banner。
2. 更新 `sql/ml/strategy1/README.md`，保留当前 Cloud Run / v3 QA 说明，删除旧 BQML active 顺序执行命令。
3. 更新 `.agent/memory/IMPLEMENTATION_STATUS.md`、`.agent/memory/KNOWN_CONSTRAINTS.md`、`.agent/memory/OPEN_QUESTIONS.md` 和 `TODO.md`。

### 8.4 P0-D: QA / 审计检查

删除代码 PR 至少应做本地静态检查：

1. `rg` 确认不存在对已删文件的引用。
2. `rg` 确认 `CREATE MODEL` / `ML.PREDICT` 不再作为 Strategy1 active path 出现。
3. `rg` 确认 `sql/ml/strategy1/16-24` 仍保留。
4. 不要求重跑 BigQuery / Cloud Run，除非代码删除影响当前 QA helper。

## 9. 验收标准

1. 仓库内没有可直接执行旧 BQML / SQL runner 主链的脚本组合。
2. 当前 Cloud Run Python / v3 acceptance / v3 replay 所需文件未删除。
3. 历史 BQML baseline 的 run id、backtest id 和历史语义仍可在文档中追溯。
4. 新 agent 读 `README`、PRD 和记忆后，不会把 BQML / SQL runner 当作默认或 fallback 路线。
5. 删除 PR 不改变 BigQuery 生产表、ADS 历史结果或 GCS artifact。

## 10. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 误删当前 Cloud Run QA | v3 / live search QA 失败 | P0 只删 `01-10`，明确保留 `16-24` |
| 历史结果不可解释 | 旧 run / report 失去上下文 | 文档保留 retired 说明和历史 run id |
| 隐性引用未清理 | 删除后脚本报 file not found | P0-A 先做全仓引用审计 |
| 过早删除 factor / diagnosis helper | 历史审计能力下降 | `11/12/14/15` 和相关 Python helper 先 P1 评估 |

## 11. Owner 决策点

1. 是否确认 `sql/ml/strategy1/01-10` 可以整体删除。
2. 是否确认 `scripts/strategy1/run_oq010_experiments.py` 可以删除，或需要先拆出只读历史查询 helper。
3. 是否保留 `11/12/14/15` 一段时间作为历史审计 SQL。
4. 是否需要把历史 BQML 文档移动到 archive，还是仅加 retired banner。

