> 文档维护：GPT-5 Codex（最近更新 2026-06-10）

# PRD: 策略 1 旧 BQML / SQL Runner 退役

> 状态：已采纳并在本 PR 实现 P0 退役范围。
> 范围声明：本文定义并实现 Strategy1 旧 BigQuery ML / SQL runner 的 P0 退役；本 PR 删除旧代码入口，但不运行 BigQuery / Cloud Run、不覆盖任何历史实验产物。
> 关联：`docs/策略1-ml_pv_clf_v0-runner设计.md`、`docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`、`docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`、`docs/prd/PRD_20260605_04_策略1CloudRunPython模型基线搜索.md`、`configs/strategy1/model_acceptance_contract_v3.yml`、`.agent/memory/OPEN_QUESTIONS.md` OQ-010。

---

## 1. 背景

Strategy1 早期实现路径是 BigQuery ML + SQL runner。历史上 `sql/ml/strategy1/01-10` 串成完整链路：训练面板、BQML logistic candidate、`ML.PREDICT`、候选池、组合目标、订单计划、SQL ledger、报告输入和 `10` QA。

当前状态已经不是“整条 `01-10` 都退役”。Cloud Run Python 路线只替换了 BQML 训练 / 选型 / 预测这段：

```text
02_train_bqml_logistic_candidates.sql
03_select_model_and_register.sql
04_predict_daily.sql
```

但当前 Cloud Run Python 默认生产路径仍直接复用共享 SQL：

```text
01_build_training_panel.sql
05_build_candidates.sql
06_build_portfolio_targets.sql
07_build_order_plan.sql
09_build_metrics_and_report_inputs.sql
10_qa_runner_outputs.sql
12_qa_model_diagnosis_outputs.sql
```

退役前，`08_run_backtest.sql` 已不是默认 Python ledger 路径，但仍可通过 `--use-bq-ledger` 作为 SQL ledger 对照 / fallback-style diagnostic 可选入口存在。owner 现决定也退役该可选入口。

因此，本 PRD 的退役对象收敛为两类：

1. BQML-only 的 `02-04`。
2. 非默认的 SQL ledger fallback `08` 及其 `--use-bq-ledger` 入口。

不得整体删除 `01-10`。

后续 owner 已明确：

```text
不再使用旧 BQML 训练 / 选型 / 预测路径作为策略执行层默认、fallback 或新增开发路线；当前仍复用的共享 SQL 另行保留。
```

当前实际策略搜索和验收主线已切到 Cloud Run Python training / prediction / ledger + 共享 BigQuery SQL candidate / portfolio / order / report / QA + v3 acceptance gate。BQML-only 训练 / 选型 / 预测脚本仍留在仓库中，主要价值只剩 historical reference / audit。继续保留可执行 BQML-only 主链会带来三个问题：

1. 新 agent 容易误以为 BQML 训练 / 预测仍是可选 fallback。
2. 旧 BQML `02-04` 与当前 Cloud Run Python 模型路径继续分叉，增加维护成本。
3. 后续 Strategy1 cleanup 时很难区分“当前共享 SQL”与“已退役的 BQML-only / SQL-ledger fallback 脚本”。

本文定义退役边界。

## 2. 目标

1. 明确旧 BQML-only 训练 / 选型 / 预测脚本不再作为 active execution path。
2. 明确 `08_run_backtest.sql` 的 BigQuery SQL ledger fallback 也不再保留为 active diagnostic / equivalence path。
3. 删除或归档仍可误触发 BQML `CREATE MODEL` / `ML.PREDICT` 或 `--use-bq-ledger` 的代码入口。
4. 保留当前 Cloud Run Python 所需的共享 SQL、v3 acceptance QA、replay、contract 和历史审计字段。
5. 保留历史实验结果的可解释性：旧 BQML run / backtest id、历史报告、GCS artifact 和 ADS 已写结果不因代码删除而失去说明。
6. 删除后，仓库内不应再存在“可直接重跑 BQML 训练 / 预测并写出新 production baseline”的路径，也不应再存在 `--use-bq-ledger` 可选回测入口。

## 3. 非目标

1. 不删除 BigQuery 中已存在的历史 ADS 结果、BQML model object 或 GCS artifact。
2. 不重算历史 BQML baseline。
3. 不改变当前 Cloud Run Python 默认 runner、共享 SQL candidate / portfolio / order / report / QA、v3 gate、v3 replay 或 live search 逻辑。
4. 不删除 `sql/ml/strategy1` 整个目录；该目录下仍有当前 Cloud Run 共享 SQL 和 v3 QA SQL。
5. 不把历史 BQML 文档伪装成当前方案；旧文档应标记为 historical / retired，而不是静默删除所有上下文。

## 4. 退役原则

### 4.1 当前 active path

当前 Strategy1 active path 是混合路径，不是纯 Python：

```text
Cloud Run Python training / prediction / ledger
  -> shared BigQuery SQL training panel / candidate / portfolio / order / report / QA
  -> ADS registry / summary / artifacts
  -> v3 acceptance gate
  -> 19/21/24 等 QA / replay
```

其中当前默认路径仍在使用的共享 SQL 包括 `01`、`05-07`、`09-10` 和 `12`。退役前，`08` 仅在显式传 `--use-bq-ledger` 时使用；本 PRD 要求退役该可选分支。BQML-only 的 `02-04` 和 SQL ledger fallback 的 `08` 不再是：

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

### 5.1 P0 删除候选：BQML-only 脚本

以下脚本只服务旧 BQML 训练 / 选型 / 预测，当前 Cloud Run Python 生产路径不直接调用，P0 已删除：

| 文件 | 旧职责 | 处理 |
|---|---|---|
| `sql/ml/strategy1/02_train_bqml_logistic_candidates.sql` | `CREATE MODEL` BQML logistic 候选 | 删除 |
| `sql/ml/strategy1/03_select_model_and_register.sql` | BQML valid 选择与 registry 写回 | 删除 |
| `sql/ml/strategy1/04_predict_daily.sql` | `ML.PREDICT` 预测写回 | 删除 |

删除同步确认：

1. Cloud Run Python path 不调用 `02-04`。
2. 当前 QA / replay helper 不调用 `02-04`。
3. README / PRD / runbook 不再把 `02-04` 描述为 active path。

### 5.2 P0 删除候选：SQL ledger fallback

退役前，以下脚本不在默认 Python ledger 路径上，但仍可由 `--use-bq-ledger` 触发。owner 现决定退役该可选 SQL ledger fallback，因此 P0 已删除：

| 文件 | 旧职责 | 处理 |
|---|---|---|
| `sql/ml/strategy1/08_run_backtest.sql` | BigQuery SQL ledger fallback / historical equivalence diagnostic | 删除，并同步移除 `--use-bq-ledger` 入口 |

删除 `08` 同步完成：

1. 删除 `scripts/strategy1_cloudrun/backtest_report.py` 的 `--use-bq-ledger` 参数、`resolve_backend_tags(... use_bq_ledger ...)` 分支和对 `08_run_backtest.sql` 的调用。
2. 删除 `scripts/strategy1_cloudrun/orchestrate_experiments.py` 与 `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py` 中透传 `--use-bq-ledger` 的逻辑。
3. 更新 `sql/ml/strategy1/README.md` 中 `--use-bq-ledger`、SQL ledger fallback 和 `08_run_backtest.sql` 的 active / diagnostic 说明。
4. 确认当前 live search、v3 acceptance、v3 replay、lot-aware QA 和 R14 长训练实验均不依赖 `--use-bq-ledger`。
5. 历史 BQML / SQL ledger run 只保留为已写 ADS / GCS artifact，不再保留可重跑入口。

### 5.3 不可删除：当前 Cloud Run Python 仍使用的共享 SQL

以下文件虽然历史上属于 `01-10` SQL runner，但当前 Cloud Run Python 默认生产路径仍直接调用，不能作为删除候选：

| 文件 | 当前调用方 | 当前职责 |
|---|---|---|
| `sql/ml/strategy1/01_build_training_panel.sql` | `scripts/strategy1_cloudrun/config.py` / `train_predict.py` | Cloud Run Python 训练面板 SQL |
| `sql/ml/strategy1/05_build_candidates.sql` | `scripts/strategy1_cloudrun/backtest_report.py` | 候选池构建 |
| `sql/ml/strategy1/06_build_portfolio_targets.sql` | `scripts/strategy1_cloudrun/backtest_report.py` | 组合目标构建 |
| `sql/ml/strategy1/07_build_order_plan.sql` | `scripts/strategy1_cloudrun/backtest_report.py` | 订单计划构建 |
| `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql` | `scripts/strategy1_cloudrun/backtest_report.py` | summary / report input |
| `sql/ml/strategy1/10_qa_runner_outputs.sql` | `scripts/strategy1_cloudrun/backtest_report.py` | runner QA |
| `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql` | `scripts/strategy1_cloudrun/backtest_report.py` | diagnosis QA |

若未来想删除这些共享 SQL，必须先另写 PRD / migration plan，把 Cloud Run Python 的候选、组合、订单、回测、report 和 QA 全部迁出 BigQuery SQL；这不是本 PRD 的范围。

### 5.4 P0 评估：旧实验调度入口

| 文件 | 旧职责 | 处理 |
|---|---|---|
| `scripts/strategy1/run_oq010_experiments.py` | 调度旧 BQML / SQL runner experiment，也包含 portfolio-only / historical runner 逻辑 | 删除。该入口直接调度已删除的 `02-04` / `08`，不是当前 Cloud Run Python path；继续保留会形成失效的重跑入口。 |

### 5.5 P1 评估后处理

以下文件不在 P0 直接删除，先查依赖：

| 文件 | 原因 | P1 处理 |
|---|---|---|
| `sql/ml/strategy1/11_model_quality_diagnostics.sql` | 旧模型诊断可能仍被历史报告引用 | 依赖清空后删除或改 historical |
| `sql/ml/strategy1/14_qa_factor_attribution_outputs.sql` | 因子归因 QA，可能仍用于历史 BQML artifact | 先保留 |
| `sql/ml/strategy1/15_qa_ledger_resume_consistency.sql` | 旧 SQL ledger resume QA；当前后续可能需要 Cloud Run resume 对照 | 先保留，等 Cloud Run resume QA 明确后再处理 |
| `scripts/strategy1/attribute_factor_contribution.py` | 读取 selected BQML model 系数 | 若只服务历史 BQML，改 historical 或删除 |
| `scripts/strategy1/diagnose_acceptance_window.py` | 仍读取 BQML historical reference 做只读诊断 | 先保留，但文档明确“不重跑 BQML” |

## 6. 必须保留范围

以下文件 / 目录不得在本次退役中删除：

| 范围 | 保留原因 |
|---|---|
| `sql/ml/strategy1/01_build_training_panel.sql` | 当前 Cloud Run Python training panel SQL |
| `sql/ml/strategy1/05_build_candidates.sql` | 当前 Cloud Run Python backtest/report 共享 SQL |
| `sql/ml/strategy1/06_build_portfolio_targets.sql` | 当前 Cloud Run Python backtest/report 共享 SQL |
| `sql/ml/strategy1/07_build_order_plan.sql` | 当前 Cloud Run Python backtest/report 共享 SQL |
| `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql` | 当前 Cloud Run Python summary / report input SQL |
| `sql/ml/strategy1/10_qa_runner_outputs.sql` | 当前 Cloud Run Python runner QA |
| `sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql` | 当前 Cloud Run Python diagnosis QA |
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
本文记录历史 BQML / SQL runner 方案；其中 BQML-only 训练 / 选型 / 预测路径和 BigQuery SQL ledger fallback 已退役，不再作为 Strategy1 默认、fallback 或新增开发路线。当前 active path 为 Cloud Run Python training / prediction / ledger + 共享 BigQuery SQL candidate / portfolio / order / report / QA + v3 acceptance gate。
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

### 8.1 P0-A: 依赖审计（已执行）

本 PR 实现前先做只读依赖审计：

1. 搜索 `02_train_bqml_logistic_candidates.sql`、`03_select_model_and_register.sql`、`04_predict_daily.sql` 的引用。
2. 搜索 `08_run_backtest.sql` 和 `--use-bq-ledger` 的引用。
3. 搜索 `ML.PREDICT`、`CREATE MODEL`、`run_oq010_experiments.py` 的引用。
4. 搜索 Cloud Run Python path 是否仍调用 `02-04`。
5. 确认 Cloud Run Python 仍调用的 `01`、`05-07`、`09-10`、`12` 被列入保留清单。
6. 输出保留 / 删除清单。

### 8.2 P0-B: 删除旧主链（已执行）

确认当前 Cloud Run Python path 不依赖旧主链后，本 PR 删除：

1. `sql/ml/strategy1/02_train_bqml_logistic_candidates.sql`。
2. `sql/ml/strategy1/03_select_model_and_register.sql`。
3. `sql/ml/strategy1/04_predict_daily.sql`。
4. `sql/ml/strategy1/08_run_backtest.sql`。
5. `--use-bq-ledger` CLI 参数、orchestrator 透传和 README fallback 说明。
6. README 中旧 BQML active runbook 命令。
7. `scripts/strategy1/run_oq010_experiments.py`。该入口直接调度已删除的 `02-04` / `08`，不是当前 Cloud Run Python path；继续保留会形成失效重跑入口。

### 8.3 P0-C: 文档与记忆收口（已执行）

1. 给历史 BQML 设计文档加 retired banner。
2. 更新 `sql/ml/strategy1/README.md`，保留当前 Cloud Run / 共享 SQL / v3 QA 说明，删除旧 BQML `02-04` active 顺序执行命令和 `--use-bq-ledger` fallback 说明。
3. 更新 `.agent/memory/IMPLEMENTATION_STATUS.md`、`.agent/memory/KNOWN_CONSTRAINTS.md`、`.agent/memory/OPEN_QUESTIONS.md` 和 `TODO.md`。

### 8.4 P0-D: QA / 审计检查（静态审计）

删除代码 PR 至少应做本地静态检查；本 PR 不要求重跑 BigQuery / Cloud Run：

1. `rg` 确认不存在对已删 `02-04` 文件的 active 引用。
2. `rg` 确认不存在对 `08_run_backtest.sql` 和 `--use-bq-ledger` 的 active 引用。
3. `rg` 确认 `CREATE MODEL` / `ML.PREDICT` 不再作为 Strategy1 active path 出现。
4. `rg` 确认 `sql/ml/strategy1/01`、`05-07`、`09-10`、`12` 仍保留并仍可被 Cloud Run Python 调用。
5. `rg` 确认 `sql/ml/strategy1/16-24` 仍保留。
6. 不要求重跑 BigQuery / Cloud Run，除非代码删除影响当前 QA helper。

## 9. 验收标准

1. 仓库内没有可直接执行旧 BQML `CREATE MODEL` / `ML.PREDICT` 主链的脚本组合，也没有 `--use-bq-ledger` SQL ledger fallback 入口。
2. 当前 Cloud Run Python / 共享 SQL / v3 acceptance / v3 replay 所需文件未删除。
3. 历史 BQML baseline 的 run id、backtest id 和历史语义仍可在文档中追溯。
4. 新 agent 读 `README`、PRD 和记忆后，不会把 BQML / SQL runner 当作默认或 fallback 路线。
5. 删除 PR 不改变 BigQuery 生产表、ADS 历史结果或 GCS artifact。

## 10. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 误删当前共享 SQL | Cloud Run Python backtest/report 失败 | P0 只删 BQML-only `02-04`，明确保留 `01`、`05-07`、`09-10`、`12` 和 `16-24` |
| 只删 `08` 不删 `--use-bq-ledger` | CLI / orchestrator 仍可触发已删 SQL，运行期 FileNotFoundError | `08` 删除必须和 `--use-bq-ledger` 参数、orchestrator 透传、README fallback 说明同批处理 |
| 历史结果不可解释 | 旧 run / report 失去上下文 | 文档保留 retired 说明和历史 run id |
| 隐性引用未清理 | 删除后脚本报 file not found | P0-A 先做全仓引用审计 |
| 过早删除 factor / diagnosis helper | 历史审计能力下降 | `11/14/15` 和相关 Python helper 先 P1 评估；`12` 当前由 Cloud Run Python 直接调用，默认不可删除 |

## 11. Owner 决策结论

1. owner 已确认 BQML-only `sql/ml/strategy1/02-04` 删除。
2. owner 已确认 `sql/ml/strategy1/08_run_backtest.sql` 和 `--use-bq-ledger` fallback 入口同批删除。
3. 本 PR 删除 `scripts/strategy1/run_oq010_experiments.py`，不拆只读 helper；理由是该入口直接依赖已删除的 `02-04` / `08`。
4. `11/14/15` 暂保留为 P1 评估对象；`12` 当前由 Cloud Run Python 直接调用，默认保留。
5. 历史 BQML 文档暂不移动 archive，只加 retired / historical 说明并保留审计语义。
