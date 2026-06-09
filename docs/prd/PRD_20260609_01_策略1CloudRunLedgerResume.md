> 文档维护：GPT-5 Codex（最近更新 2026-06-09）

# PRD: 策略 1 Cloud Run Ledger Resume

> 状态：草案，待 review / 合并。
> 范围声明：本文只定义 Strategy1 Cloud Run Python `ledger_exec_v1_lot100` 的分段 resume 方案；不实现代码、不创建或修改 BigQuery 表、不运行 Cloud Run / BigQuery、不生成或覆盖任何回测产物。
> 关联：`docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`、`docs/prd/PRD_20260606_05_策略1整数手交易执行.md`、`docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`。

---

## 1. 背景

当前 Strategy1 Cloud Run Python runner 已可用 `strategy1-backtest-report-job` 跑 lot-aware 回测，但 `scripts/strategy1_cloudrun/ledger.py` 的执行状态仍是 fresh-start only：

```text
initial_state_mode = fresh
initial cash = initial_capital
initial holdings = empty
pending_sell = empty
previous_nav_value = None
```

这意味着如果先跑 `2020-2022`，再单独跑 `2023-2026`，第二段会重新从初始现金和空仓开始，不等价于一条连续的 `2020-2026` 回测。

历史 BigQuery SQL runner 曾实现过 P2 resume consistency QA，但 owner 已决定后续策略执行层不再扩展 BQML / `sql/ml/strategy1` SQL runner。后续 resume 必须落到 Cloud Run Python `ledger_exec_v1_lot100`，BigQuery SQL 只保留为 ADS 契约 QA / 只读校验工具。

本文定义 Cloud Run Python ledger resume 的产品和工程契约，用于支持：

```text
先跑 2020-2022
再从 2022-12-30 账户状态 resume 跑 2023-2026
并使 2023-2026 段与 fresh-start 全段 2020-2026 的对应区间一致
```

## 2. 目标

1. 支持 Cloud Run Python ledger 从父回测的真实账户状态继续运行后续区间。
2. 让长窗口回测可以先做短窗口 smoke，再在需要时无损接续，而不是只能 full fresh 重跑。
3. 固化 resume 所需的现金、持仓、pending sell、active target、NAV anchor 和调仓锚点边界。
4. 明确 fail-fast 条件，禁止 resume 缺状态时静默 fallback 到 fresh-start。
5. 为未来 `2020-2022 -> 2023-2026`、月度滚动重训和长窗口研究实验提供同一 resume 契约。
6. 保持 Cloud Run Python runner 是唯一新增实现路径，不恢复或扩展历史 BQML / SQL runner。

## 3. 非目标

1. 不改变模型训练、特征、标签、score orientation、prediction stream 或 v3 acceptance gate。
2. 不改变 lot-aware ledger 的交易规则：100 股整数手买入、odd-lot 清仓、卖出先于买入、pending sell、现金约束、收盘 mark-to-market。
3. 不把 `2020-2022` 与 `2023-2026` 两个 fresh-start 回测简单拼接成连续结果。
4. 不要求 P0 支持从历史 FLOAT-shares 或 BQML SQL runner 回测直接 resume。
5. 不实现分钟线、T+1 卖出锁仓、成交深度、候补买入或余现金二次分配。
6. 不在本文修改 ADS schema；schema 变更和代码实现放到后续实现 PR。

## 4. 术语

| 术语 | 定义 |
|---|---|
| parent backtest | 已完成的前一段回测，例如 `2020-2022` |
| child backtest | 从 parent 状态继续运行的后一段回测，例如 `2023-2026` |
| state_as_of_date | 从 parent 读取账户状态的日期，必须是 parent 已有 NAV 日期 |
| resume start date | child 的首个执行日期，必须是 `state_as_of_date` 后下一个 SSE 开市日 |
| resume snapshot | 从 parent 回测恢复 child 所需的最小状态集合 |
| NAV anchor | child 首日 `daily_return` 的上一日 NAV，来自 parent `state_as_of_date` |
| rebalance anchor | 计算 weekly / biweekly / monthly 调仓日时使用的全局锚点，不能随 child `predict_start` 重置 |

## 5. Resume 模式

新增 Cloud Run Python ledger 参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `initial_state_mode` | `fresh` | `fresh` / `resume_from_backtest` |
| `parent_backtest_id` | `NULL` | resume 时必填，父回测 ID |
| `state_as_of_date` | `NULL` | resume 时必填，父回测状态日期 |
| `resume_policy_id` | `cloudrun_lot100_resume_v1` | P0 固定值；仅作为 artifact / summary 的兼容标签，不做运行时分支 |
| `rebalance_anchor_start` | fresh: `predict_start`; resume: 必填 | fresh 可默认等于 `predict_start`；resume 必须由调用方显式传入 parent / full experiment 的原始锚点 |
| `resume_strictness` | `fail_fast` | P0 只支持 fail-fast，不支持宽松 fallback |

语义：

```text
fresh:
  cash = initial_capital
  holdings = {}
  pending_sell = set()
  previous_nav_value = None

resume_from_backtest:
  cash = parent cash at state_as_of_date
  holdings = parent positions at state_as_of_date
  pending_sell = parent pending_sell at state_as_of_date
  previous_nav_value = parent net_value_cny at state_as_of_date
  first child date = next SSE open date after state_as_of_date
```

### 5.1 `resume_policy_id` 语义

P0 中 `resume_policy_id` 固定为 `cloudrun_lot100_resume_v1`。它不是独立的交易规则开关，也不允许在 P0 代码里产生多套运行时分支。

用途仅限：

1. 写入 summary / report / ledger state artifact，作为 resume 状态兼容标签。
2. 与 `ledger_version`、`ledger_params_hash` 一起用于 parent / child 兼容性校验。
3. 后续如果引入新的 resume 行为，再新增新的 policy id，并在对应 PRD 中定义差异。

P0 实现方不应猜测 `cloudrun_lot100_resume_v1` 以外的语义。

## 6. Resume snapshot

### 6.1 最小状态

P0 resume snapshot 至少包含：

| 字段 | 来源 | 用途 |
|---|---|---|
| `cash_cny` | parent `ads_backtest_nav_daily.cash_cny` | child 初始现金 |
| `net_value_cny` | parent `ads_backtest_nav_daily.net_value_cny` | child 首日收益 LAG anchor |
| `nav` | parent `ads_backtest_nav_daily.nav` | 报告 / 拼接校验 |
| `holdings` | parent `ads_backtest_position_daily` | child 初始实际持仓 |
| `pending_sell_sec_codes` | parent ledger state 或可验证推导 | child 非调仓日继续尝试卖出 |
| `active_signal_date` | parent ledger state 或可验证推导 | 恢复当前有效目标组合 |
| `active_target_weights` | parent target rows | 判断 pending sell 与 netting |
| `ledger_version` | parent summary / metrics | 兼容性校验 |
| `ledger_params_hash` | parent metrics | 成本、lot、rounding、资金规模兼容性校验 |
| `rebalance_anchor_start` | parent run context | 保持 biweekly / monthly 调仓日一致 |

### 6.2 状态持久化建议

P0 实现优先新增一个轻量 ledger state artifact，而不是只从 trade rows 反推：

```text
gs://ashare-artifacts/reports/strategy1/<strategy_id>/run_id=<run_id>/backtest_id=<backtest_id>/ledger_state_daily.parquet
```

建议同时写入 ADS 表或 report artifact 索引，后续实现 PR 再决定是否新增正式表：

```text
ashare_ads.ads_backtest_ledger_state_daily
```

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `backtest_id` | STRING | 回测 ID |
| `trade_date` | DATE | 状态日期 |
| `cash_cny` | FLOAT64 | 当日收盘后现金 |
| `net_value_cny` | FLOAT64 | 当日收盘后账户净值 |
| `pending_sell_sec_codes_json` | STRING | pending sell 股票列表 JSON |
| `active_signal_date` | DATE | 当前有效信号日 |
| `active_target_weights_json` | STRING | 当前目标组合权重 JSON |
| `holdings_hash` | STRING | 当日持仓快照 hash |
| `ledger_version` | STRING | 如 `ledger_exec_v1_lot100` |
| `ledger_params_hash` | STRING | 成本、lot、rounding、资金规模等参数 hash |
| `created_at` | TIMESTAMP | 写入时间 |

如果 P0 不新增 ADS 表，也必须把上述状态写入 GCS artifact，并在 summary/report 中记录 artifact URI。

### 6.3 不支持的 parent

P0 不支持以下 parent 直接 resume：

1. FLOAT-shares ledger parent。
2. BigQuery SQL runner parent。
3. 缺少 ledger state artifact 且无法可靠恢复 pending sell / active target 的 parent。
4. `ledger_version`、成本 profile、lot 参数、初始资金、股票池或 rebalance 规则与 child 不兼容的 parent。

这些情况必须 fail-fast，并给出明确错误原因。

## 7. 日期与调仓锚点

### 7.1 Resume start date

P0 强制：

```text
child.predict_start = next_sse_open_date(parent.state_as_of_date)
```

例如：

```text
parent: 2020-01-02 ~ 2022-12-30
state_as_of_date: 2022-12-30
child.predict_start: 2023-01-03
```

如果 `child.predict_start` 不是 `state_as_of_date` 后下一个 SSE 开市日，直接失败。

### 7.2 调仓锚点

`05_build_candidates.sql` 当前会基于 `predict_start` 重新计算 weekly / biweekly 周序号。对 resume 来说这是危险的：

```text
full 2020-2026: biweekly week_idx 从 2020 起算
child 2023-2026: 如果从 2023 重新起算，双周奇偶可能漂移
```

因此 P0 必须引入 `rebalance_anchor_start`：

1. fresh run 默认 `rebalance_anchor_start = predict_start`。
2. resume child 必须使用 parent/full experiment 的原始 `rebalance_anchor_start`。
3. `05_build_candidates` 的 weekly / biweekly / monthly 日期生成必须按 anchor 计算，而不是按 child start 重新编号。
4. QA 必须比较 full fresh 与 segmented resume 的 rebalance dates 完全一致。

## 8. Fail-fast 校验

进入 child ledger 前必须校验：

1. `initial_state_mode='resume_from_backtest'` 时，`parent_backtest_id` 和 `state_as_of_date` 必填。
2. parent NAV 在 `state_as_of_date` 必须唯一存在。
3. parent positions 在 `state_as_of_date` 必须可读，且持仓 `(trade_date, sec_code)` 唯一。
4. parent `cash_cny + SUM(position_market_value_cny)` 与 parent `net_value_cny` 的差异必须在容忍阈值内。
5. parent ledger version 必须等于 child ledger version，P0 固定 `ledger_exec_v1_lot100`。
6. parent 与 child 的成本 profile、lot 参数、初始资金、strategy_id、target_holdings、max_single_weight、rebalance_frequency、label_horizon 和股票池口径必须兼容。
7. child `predict_start` 必须等于 state date 后下一 SSE 开市日。
8. resume 时 `rebalance_anchor_start` 必须由调用方显式传入，并且必须等于 parent / full experiment 的原始锚点；不允许静默使用默认 `predict_start`。如果 `rebalance_anchor_start = child.predict_start` 且 `child.predict_start` 不等于 parent 原始锚点，必须 fail-fast。
9. resume 模式必须确认候选生成路径已经支持并实际使用 `rebalance_anchor_start`；如果 `05_build_candidates` / wrapper 仍只能按 child `predict_start` 重新编号 week index，必须拒绝 resume。
10. child `backtest_id` 必须不同于 parent `backtest_id`。
11. `force_replace` 只能清理 child 输出范围，禁止删除 parent 产物。
12. 缺少 pending sell / active target 状态时，P0 不允许静默按空状态继续。

## 9. Ledger 执行语义

resume child 第一天执行前：

1. `cash` 初始化为 parent cash。
2. `holdings` 初始化为 parent 实际持仓股数。
3. `pending_sell` 初始化为 parent pending sell。
4. `target_weights` 初始化为 parent active target；如果 child 首日不是调仓执行日，仍需用该 active target 继续处理 pending sell / netting。
5. `previous_nav_value` 初始化为 parent `state_as_of_date` 的 `net_value_cny`。

child 运行期间继续使用既有 lot-aware 规则：

1. 每个开市日都 mark-to-market。
2. 调仓日读新的 target；非调仓日沿用 active target。
3. pending sell 在后续每个开市日继续尝试卖出。
4. 旧仓重新入选时按实际持仓与新目标 netting。
5. 买入仍按 100 股整数手，清仓卖出允许 odd-lot。

## 10. 输出与报告

### 10.1 Child segment 输出

child backtest 继续写独立 ADS 产物：

```text
ads_backtest_trade_daily
ads_backtest_position_daily
ads_backtest_nav_daily
ads_backtest_performance_summary
report / diagnosis / QA artifact
```

child summary 默认表示 child segment 自身区间表现，例如 `2023-2026`。

### 10.2 Continuous stitched artifact

为了回答“2020-2026 连续表现”，P0 推荐额外生成只读 stitched artifact：

```text
parent + child continuous_nav.csv
parent + child continuous_summary.json
resume_consistency_report.md
```

规则：

1. stitched artifact 不覆盖 parent 或 child ADS summary。
2. continuous NAV 以 parent NAV 到 `state_as_of_date`，再接 child NAV。
3. child 首日 `daily_return` 已使用 parent NAV anchor，因此连续收益序列不应有断点。
4. v3 gate 若用于 official acceptance，应明确使用 full fresh backtest 还是 stitched continuous artifact；P0 只要求 resume consistency，不直接改变 acceptance 写回门。

## 11. QA 与验收

### 11.1 Golden case 单元测试

新增 Python golden-case 测试，至少覆盖：

1. 从 parent cash / positions 恢复 child 初始状态。
2. child 首日 `daily_return` 使用 parent NAV anchor。
3. parent pending sell 在 child 非调仓日继续尝试。
4. child 首日股票重新入选时正确 netting，而不是重复全额建仓。
5. biweekly `rebalance_anchor_start` 不随 child start 漂移。
6. 缺 parent NAV / 缺 state / ledger version 不兼容时 fail-fast。
7. `force_replace` 不删除 parent 输出。

### 11.2 真实回测一致性 QA

新增 Cloud Run Python resume QA，建议文件名：

```text
sql/ml/strategy1/25_qa_cloudrun_ledger_resume_outputs.sql
```

该 SQL 只做只读 ADS 契约 QA，不恢复 SQL runner。验收场景：

```text
full fresh: 2020-01-02 ~ 2026-04-30
parent:     2020-01-02 ~ 2022-12-30
child:      2023-01-03 ~ 2026-04-30, resume from parent 2022-12-30
```

必须检查：

1. full 与 child 在 `2023-01-03 ~ 2026-04-30` 的 NAV、cash、daily_return、position shares、trade rows 一致或在明确阈值内。
2. full 与 child 的 rebalance dates 一致。
3. full 与 child 的 pending sell 状态一致。
4. child 首日 daily return 与 full 同日 daily return 一致。
5. child 没有 fresh-start 迹象：首日现金不等于 `initial_capital`，首日持仓不为空，除非 parent 本身为空仓。
6. child summary/report 明确标记 `initial_state_mode=resume_from_backtest`、`parent_backtest_id` 和 `state_as_of_date`。

### 11.3 验收门

P0 完成条件：

1. Unit golden cases 通过。
2. 真实 `2020-2022 -> 2023-2026` resume QA 通过。
3. full fresh 与 segmented resume 的 2023+ 段差异为 0，或全部差异可解释并写入报告。
4. `backtest_report`、orchestrator、report artifact 和 ADS summary 都记录 resume context。
5. 失败路径 fail-fast，不生成看似成功的 fresh-start child。

## 12. 实施阶段

### Phase A: PRD

交付：

1. 本 PRD。
2. `TODO.md` 新增 Cloud Run ledger resume 实现任务。
3. `.agent/memory/IMPLEMENTATION_STATUS.md` 与 `.agent/memory/AGENT_HANDOFF.md` 同步当前状态。

### Phase B: 参数、状态契约与调仓锚点

实现必须把 resume 参数、状态恢复和调仓锚点作为同一阶段交付，不能先开放 `resume_from_backtest` 再后补 anchor。

实现：

1. `LedgerParams` 新增 resume 参数。
2. `backtest_report.py` 和 orchestrator 支持传递 resume 参数。
3. ledger 输出 resume state artifact。
4. summary/report 写入 resume context。
5. `05_build_candidates` / Python wrapper 支持 `rebalance_anchor_start`。
6. resume child 必须继承 parent / full experiment 的原始 anchor。
7. fail-fast 校验完整落地，包括缺 anchor、anchor 未被候选生成路径消费、或 anchor 回落到 child start 时拒绝 resume。

### Phase C: Golden cases 与 QA

实现：

1. Python golden-case tests。
2. `25_qa_cloudrun_ledger_resume_outputs.sql` 或等价只读 QA。
3. 真实 smoke：短窗口 parent/child。

### Phase D: 真实窗口验证

执行：

1. 固定 r14 或指定 prediction stream 跑 full fresh `2020-2026`。
2. 跑 parent `2020-2022`。
3. 从 parent `2022-12-30` resume 跑 child `2023-2026`。
4. 产出 resume consistency report。

## 13. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| biweekly anchor 漂移 | child 选股日期与 full 不一致 | 强制 `rebalance_anchor_start`，QA 比较调仓日期 |
| pending sell 反推不可靠 | child 与 full 持仓路径偏离 | 新增 ledger state artifact，缺状态 fail-fast |
| 首日 daily_return 断点 | 连续收益和 Sharpe 错误 | 使用 parent NAV 作为 `previous_nav_value` |
| force_replace 清 parent | 历史产物丢失 | child 清理范围只允许 child backtest_id |
| parent/child 参数不兼容 | resume 结果无意义 | ledger params hash + 显式兼容校验 |
| 旧 SQL runner resume 被误用 | 执行路线回退 | PRD 明确 Cloud Run Python only，SQL 只做 QA |

## 14. 推荐首个真实实验

为回答 owner 当前问题，首个真实 resume 实验建议：

| 项 | 值 |
|---|---|
| 模型方法 | 沿用当前 r14 方法 / 参数 |
| 训练窗口 | 2015-2019，前提是先补齐 2015-2018 DWD/DWS/sample/label |
| parent backtest | 2020-01-02 ~ 2022-12-30 |
| child backtest | 2023-01-03 ~ 2026-04-30 |
| full reference | 2020-01-02 ~ 2026-04-30 |
| ledger | `ledger_exec_v1_lot100` |
| 验收 | full reference vs parent+child resume 在 2023+ 段一致 |

如果 2015-2018 DWD/DWS 尚未补齐，可以先用当前已有 prediction stream 做工程 smoke，确认 resume 机制正确后，再做 2015-2019 训练实验。
