> 文档维护：Claude Fable 5（最近更新 2026-06-11）

# PRD：策略 1 年度滚动 Final Refit

> 状态：草案，待 owner review。
> 范围声明：本文只定义年度滚动 valid 选参后的 final refit 执行方案；不改候选池、不改 valid 选参规则、不改 acceptance gate、不实现 continuous ledger（见 `PRD_20260611_03`）、不做 promotion。
> 关联：`docs/prd/PRD_20260610_03_策略1年度滚动选参.md`、`docs/prd/PRD_20260610_04_策略1年度滚动执行工程化.md`、`docs/prd/PRD_20260611_01_策略1年度滚动并发调度.md`。

---

## 1. 背景

2026-06-10 至 2026-06-11 的 `2021-2026` 年度滚动链路已全部跑完（每年 panel → matrix → 11 候选 fanout → select/register/predict → 年度 diagnostic backtest），但存在一个方法论偏离：

**PRD_20260610_03 要求 valid 选参后用最近 5 年重新训练最终模型（final refit），当前实现没有执行这一步。** `select_register_predict` 只是把 selection 阶段训练出的 selected candidate 模型直接注册并用于预测。

以 2026 为例：

| 项 | 当前实际 | PRD 要求 |
|---|---|---|
| selected model 训练窗口 | `2020-01-02 ~ 2024-12-24`（selection train） | `2021-01-04 ~ 2025-12-24`（final refit） |

后果：每年的预测模型少用了最近一整年（valid 年）的数据，且训练窗口比 PRD 口径整体偏旧一年。当前 6 年的预测与年度 diagnostic 结果只能作为链路通畅证据，不能进入正式 continuous ledger 评价。

实现层面有一个有利事实：annual orchestrator 的 resolved plan **已经计算并携带每年的 refit 窗口**（`year_plan` 输出中的 `final_refit` 块，`status='planned_after_candidate_selection'`），缺的只是消费这些窗口的执行步骤、registry 契约和 QA 硬门。

## 2. 目标

1. 每年 valid 选参后，对 selected candidate 的参数在 final refit 窗口上重新训练最终模型。
2. 用 refit 模型重写该年 prediction（覆盖该年 test/predict 窗口）。
3. Registry 写入 refit 模型并保留完整溯源（selected candidate、refit 窗口、source run）。
4. QA 硬门：断言 selected/refit 模型训练窗口等于 PRD 口径的 refit 窗口——本次偏离正是缺少这道断言才静默通过。
5. `2021-2026` 六年从 select 之后重跑（refit + predict + 可选年度 diagnostic），**不重跑 panel / matrix / 11 候选 fanout**。

## 3. 非目标

- 不改变 11 个 LightGBM regression 候选池和 valid 选参 / 排序规则。
- 不改 `biweekly`、20 只持仓、7.5% 单票上限等组合口径。
- 不重建 panel / matrix，不重跑候选 fanout。
- 不实现 synthetic continuous prediction 与 continuous ledger（PRD_20260611_03）。
- 不做 promotion，不写 ADS。
- 不修 research summary 落库字段（PRD_20260611_04）。

## 4. Refit 窗口口径

公式（与 PRD_20260610_04 §5 一致）：

```text
refit_train_start = actual_first_trading_day(backtest_year - 5)
refit_train_end   = label_safe_year_end(backtest_year - 1, label_horizon=5)
```

名义窗口表（实际值以 orchestrator resolved plan 的 `final_refit` 块为唯一权威来源，避免手算漂移）：

| 回测年 | refit 名义窗口 |
|---|---|
| 2021 | 2016-01-04 ~ 2020-12-24 |
| 2022 | 2017-01-03 ~ 2021-12-24 |
| 2023 | 2018-01-02 ~ 2022-12-23 |
| 2024 | 2019-01-02 ~ 2023-12-22 |
| 2025 | 2020-01-02 ~ 2024-12-24 |
| 2026 | 2021-01-04 ~ 2025-12-24 |

label embargo 规则不变：`label_horizon=5` 的训练样本必须保证未来 5 日标签完整落在 refit 窗口内（`label_safe_year_end` 末端收缩）。

## 5. 核心设计

### 5.1 复用冻结 matrix，不重建数据

这是"从 select 之后重跑"成立的关键论证：

- 每年 panel / matrix 的日期覆盖 = selection train + valid + test 的连续区间。
- refit 窗口 = selection train 的尾部 + valid 年，**真子集于 matrix 覆盖区间**。
- 因此 refit = 同一冻结 matrix 上按日期窗口换 train mask（横跨原 train 与 valid split 的行），无需新 panel、无需新 matrix。

实现 PR 必须包含前置断言：matrix 的日期覆盖区间 ⊇ refit 窗口；不满足时 fail-fast，禁止静默缩窗。

### 5.2 Refit 执行步骤

新增执行步骤（建议名 `refit_register_predict`，package entrypoint 优先）：

输入：
- 该年 select 阶段输出的 `selected_candidate_id` 与模型参数。
- 该年冻结 matrix（`matrix_uri`）。
- resolved plan 的 `final_refit` 窗口。

动作：
1. 在 refit 窗口（date mask，跨原 train/valid split）上训练 selected candidate 参数的单个模型。
2. 用 refit 模型对该年 test/predict 窗口生成 prediction。
3. 写 registry 与 prediction（见 5.3）。

### 5.3 Registry 与 run 契约

建议方案：**每年 refit 产生独立的新 run_id**，例如：

```text
s1_annual_roll_y{year}_..._{version}__refit01
```

- refit run 的 registry 只有 1 行，`status='selected'`；保持"每 run 一个 selected"的查询语义（比 selection run 的 11 行更干净，规避既有的 registry 误读问题）。
- 溯源字段（registry 列或 `metrics_json`）：`selected_candidate_id`、`source_run_id`（selection run）、`refit_train_start/end`、`refit=true`。
- prediction 行写在 refit run_id 下；原 selection run 的 11 行 registry 与 prediction 全部保留为 audit，不删除不修改。
- 年度 diagnostic backtest 与后续 continuous manifest 一律引用 refit run_id。

备选方案（不推荐）：在原 run 内追加 refit 行——会破坏"每 run 一个 selected"语义，且需要改既有 QA；仅当 owner 明确要求时采用。

### 5.4 Scheduler DAG 变更

`PRD_20260611_01` 的 DAG 在 select 与 diagnostic backtest 之间插入 refit stage：

```text
select:yYYYY -> refit:yYYYY -> diagnostic_backtest:yYYYY
```

- `refit:yYYYY` 资源 token 与单 candidate task 同级（建议 `2 CPU / 8Gi`，单任务）。
- continuous ledger 依赖从 `select:*` 改为 `refit:*` 全集。
- dry-run 模拟与 catalog caller 同步更新。

### 5.5 QA 硬门

新增或扩展 QA（SQL 或 pytest 层），至少断言：

1. refit model 的 `train_start_date/train_end_date` == resolved plan 的 `final_refit` 窗口（逐年）。
2. refit run prediction 完整覆盖该年 test/predict 窗口（行数 > 0 且日期边界吻合）。
3. refit registry 行含 `selected_candidate_id` 与 `source_run_id` 溯源且非空。
4. refit 使用的 matrix 日期覆盖 ⊇ refit 窗口。

## 6. 重跑范围

- 六年 `refit_register_predict`（6 个单模型训练 + 预测）。
- 可选：六年年度 diagnostic backtest 用 refit prediction 重跑（仍是 diagnostic，不是正式结果）。
- 不重跑：panel、matrix、11 候选 fanout、select（选参结论不变——valid 选参只依赖已有 fanout 结果）。

## 7. 验收标准

| 验收项 | 要求 |
|---|---|
| refit 窗口 | 六年 refit model 训练窗口逐年等于 resolved plan `final_refit` 窗口，QA 断言通过 |
| 数据复用 | 全程未新建 panel / matrix，refit 从冻结 matrix 读取 |
| 溯源 | 每个 refit run 可回溯到 selected candidate 与 selection run |
| 审计保留 | 原 selection run 的 registry / prediction 行未被修改或删除 |
| prediction | 六年 refit prediction 覆盖各自 test 窗口，QA 通过 |
| 默认 research | 全部写入 `ashare_research`，不触碰 ADS |

## 8. 风险与控制

| 风险 | 控制 |
|---|---|
| refit 窗口配置漂移（重蹈本次覆辙） | QA 硬门逐年断言窗口；窗口唯一来源是 resolved plan |
| matrix 覆盖不足 refit 窗口 | 前置断言 fail-fast，禁止静默缩窗 |
| refit 行污染 selection run 查询语义 | refit 独立 run_id，原 run 保持 audit 不变 |
| refit 与 selection 模型混用 | diagnostic / continuous 流程只接受带 `refit=true` 溯源的 run |
| 重跑覆盖已 succeeded artifact | 沿用既有纪律：`--force-replace` 仅显式使用 |

## 9. 实施顺序

1. 实现 `refit_register_predict` 步骤 + 单元测试（窗口断言、mask 构造、registry 契约）。
2. scheduler DAG / catalog / runbook 同步。
3. 先以 2026 单年做 live smoke（refit + predict + QA）。
4. 六年重跑 + 逐年 QA。
5. 之后进入 `PRD_20260611_03` 的正式 continuous 流程。
