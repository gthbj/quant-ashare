# topdown Phase 2 T0 三方对比

> 文档维护：GPT-5.5（最近更新 2026-06-13）

## 结论

**撤回上一版 `_v01` 报告的结论。** `_v01` run/backtest `s1_topdown_t0_continuous_true5y_2021_2026_v20260613_01` / `bt_s1_topdown_t0_continuous_true5y_2021_2026_v20260613_01` 被 topdown retained 持仓未进入 `plan` 的 ledger bug 污染：每个调仓日仍在 `walk_depth` 内的持仓被 `update_holdings(plan)` 静默丢弃，无 SELL、无现金回款。该 run 的 `-99.95%` MaxDD 与“topdown 证伪 / 路线收口”判读作废，不作为经济结果使用。

本版基于修复后 `_v02` 重跑重新判读。按 PRD_20260613_04 §3 预登记规则，`_v02` 仍落在 **topdown 证伪** 分支：长窗 CAGR `11.96%` 低于 v1 official baseline `15.36%`，Calmar `0.2104` 低于 v1 `0.4103`。现金门槛通过（平均现金 `2.51% < 10%`），但收益和风险没有同时达到构造切换要求。

本报告不做 accepted / promotion / 默认构造变更；结果仅写 `ashare_research`，ADS 与 promotion manifest 反查均为 0。

## 根因复核与修复

只读复核确认新 PR 评论的根因成立：

- 代码层：`build_daily_plan_topdown` 原先对 retained 持仓 `retained.add(sec); continue`，不 append `PlanRow`；主循环随后 `holdings = update_holdings(plan)` 只从 plan 重建持仓，因此 retained 持仓被静默销毁。v1 非 topdown 分支用 `universe = set(holdings) | targets | pending_sell`，结构上免疫。
- 数据层：`002245.SZ` 在 2021-07-12 BUY 100 股，2021-07-23 持仓市值 `2405` 元，active signal `2021-07-23` rank `23 <= 50`；2021-07-26 该票无 SELL/CA 行却从持仓消失，NAV 从 `3317` 降到 `851`，单日 `-74.35%`。
- 新增 QA 对 `_v01` 按预期失败：`qa_topdown_construction_outputs` 的 `QA-TOPDOWN-11` 在 job `bqjob_ra6e754e0d10734_0000019ebef0b5ce_1` 拦住“股数减少且无 SELL/CA 行”。

修复方式：只在 `build_daily_plan_topdown` 内把 retained 持仓输出为 hold/no-op `PlanRow`，保留 `cur_shares`，`sell_shares=0`，`want_value=0`，无 skip 状态；不改 `update_holdings`。同时保留上一轮 `planned_buy_shares` 修复，避免 topdown ceil-lot 股数被执行层浮点回算改变。

## 执行证据

| 项 | 值 |
| --- | --- |
| branch | `codex/topdown-phase2-live` |
| image tag | `topdown-p2-retained-fix-7a70d98-20260613-04` |
| image digest | `sha256:0e3f3c7751ab4be4cbcefc94529c5ef51f663a89ef7609e4d5d4c662779cb016` |
| Cloud Build | `a0aa7fb7-a26c-4480-bdb9-1163ed410b5d` |
| latest tag | 未更新，仍为 `sha256:fdb61f8141e240c377b3faaa21b5e6efef9c783ebb9e04923ff3b675b8d54bc2` |
| Cloud Run job pin | `strategy1-backtest-report-job` generation `55` |
| boot smoke | `strategy1-backtest-report-job-4hh4d` succeeded |
| formal execution | `strategy1-backtest-report-job-2lpzn` succeeded，jobGeneration `55`，completion `2026-06-13T03:13:58.067608Z` |
| run / backtest | `s1_topdown_t0_continuous_true5y_2021_2026_v20260613_02` / `bt_s1_topdown_t0_continuous_true5y_2021_2026_v20260613_02` |
| prediction stream | `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01` |
| ledger / resume | `ledger_exec_v2_lot100_topdown` / `cloudrun_lot100_topdown_resume_v1` |
| CA / tax | `cash_div_and_split_v1` / `flat_10pct` |
| tail risk | `diagnostic_only` |
| status | `acceptance_status=NULL`，`promotion_status=not_promoted` |

Research 输出行数：candidate `279625`、target `2780`、order `4830`、trade `3429`、position `19084`、NAV `1314`、ledger_state `1314`。

## QA 与 Research-only

| 检查 | 结果 | job id / 证据 |
| --- | --- | --- |
| `qa_continuous_backtest_outputs` | passed | `bqjob_r13624ec7b8c6f625_0000019ebefb96b8_1`，显式 `p_expected_ledger_version=ledger_exec_v2_lot100_topdown` / `p_resume_policy_id=cloudrun_lot100_topdown_resume_v1` |
| `qa_lot_aware_ledger_outputs` | passed | `bqjob_r34586777e4e7223b_0000019ebefbcda9_1` |
| `qa_topdown_construction_outputs` | passed | `bqjob_r4eaa32102a6d2982_0000019ebefbedf2_1`，含新增 `QA-TOPDOWN-11/12` |
| `qa_corporate_action_ledger_outputs` | passed | `bqjob_r15a60913a1b1c58c_0000019ebefc0d61_1` |
| 持仓守恒只读复核 | passed | “股数减少且无 SELL/CA 行”查询返回 0 行 |
| 单日收益 sanity | passed | `daily_return < -50%` 查询返回 0 行 |
| ADS 反查 | passed | 9 张 ADS run/backtest scoped 表均 `0` 行，job `bqjob_r7238d2f3c49e6c60_0000019ebefca18a_1` |
| promotion manifest | passed | `ashare_research.research_promotion_manifest` 反查 `0` 行 |

## 双窗口指标

长窗使用 `2021-01-04..2026-06-09`。v1 official baseline 长窗 CAGR / Sharpe / Calmar 使用 dividend resume 修正后的展示锚点；MaxDD 不变。Phase 0 paper T0 使用 `docs/analysis_strategy1_p1_market_cap_rules_20260613_metrics.csv` 对应的日级 GCS artifact 复算。

| 对象 | CAGR | Compound Sharpe | Calmar | MaxDD | Total Ret | Avg Cash | Annual Turnover | Avg Holdings | Max Weight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| topdown v2 live ledger fixed | 11.96% | 0.3821 | 0.2104 | -56.85% | 80.17% | 2.51% | 42.74 | 14.52 | 46.28% |
| v1 official baseline stitched | 15.36% | 0.6685 | 0.4103 | -37.43% | 110.52% | 29.92% | 35.05 | 16.11 | 7.82% |
| Phase 0 paper T0 | 11.81% | 0.3781 | 0.2013 | -58.67% | 78.88% | 2.58% | 39.70 | 14.54 | 47.19% |

静态近窗使用 `2024-01-02..2026-04-30`，这是 v3 replay 既定静态口径，不是 PRD_20260613_05 提案的动态 YTD 窗。

| 对象 | CAGR | Compound Sharpe | Calmar | MaxDD | Total Ret | Avg Cash | Annual Turnover | Avg Holdings | Max Weight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| topdown v2 live ledger fixed | 35.47% | 1.1776 | 0.8841 | -40.12% | 96.57% | 2.19% | 49.23 | 16.44 | 30.54% |
| v1 official baseline stitched | 38.28% | 1.4642 | 1.1041 | -34.67% | 105.75% | 15.64% | 41.03 | 18.89 | 7.82% |
| Phase 0 paper T0 | 37.17% | 1.2301 | 0.9143 | -40.66% | 102.11% | 1.99% | 43.19 | 16.37 | 35.00% |

## 差异读数

| 窗口 | topdown vs v1 CAGR | topdown vs v1 Calmar | topdown vs Phase0 paper CAGR | topdown vs Phase0 paper Calmar |
| --- | --- | --- | --- | --- |
| 长窗 | -3.40pp | -0.200 | +0.15pp | +0.009 |
| 静态近窗 | -2.81pp | -0.220 | -1.70pp | -0.030 |

## Crunch 段

`crunch` 固定为 Phase 0 口径 `2024-01-01..2024-02-07`，benchmark 为 `000852.SH`。

| 对象 | Strategy | 000852 | Excess |
| --- | --- | --- | --- |
| topdown v2 live ledger fixed | -40.12% | -18.50% | -21.61% |
| v1 official baseline stitched | -34.67% | -18.50% | -16.16% |
| Phase 0 paper T0 | -40.66% | -18.50% | -22.15% |

## Ceil-lot 集中度

retained bug 修复后，ceil-lot 单票超配仍是可观的 report-only 风险，不在本 PR 改 sizing 语义：

- 长窗 `max_realized_weight=46.28%`，`p95_max_realized_weight=31.20%`，`avg_max_realized_weight=13.71%`。
- 静态近窗 `max_realized_weight=30.54%`，`p95_max_realized_weight=25.67%`。
- 平均现金已降到 `2.51%`，说明 topdown 确实消灭了 v1 的主要现金拖累；但 10 万本金 + 100 股整手 + 无单票上限会把部分高价票放大成 lumpy 权重，并在 crunch 段放大回撤。

是否为 topdown 增加 `max_single_weight` cap 或改最小整手 sizing 语义，需要 owner 另行决策；本 PR 只修记账 bug、补 QA、防止无效 run 再次过关。

## 口径说明

- topdown live 是真实 Cloud Run ledger：处理卖出失败、pending sell、公司行为和实际现金约束；Phase 0 paper 是 raw 价格本地模拟，不模拟卖出失败/pending sell/CA，因此只作为机制校准。
- v1 baseline 长窗现金权重按落库 NAV 复算，约 `29%`；报告的 v1 长窗 CAGR/Sharpe/Calmar/MaxDD 采用 owner 指定的 dividend resume 修正展示锚点：`15.36% / 0.6685 / 0.4103 / -37.43%`。
- 本报告未改 prediction 流、未训练、未写 ADS、未写 promotion manifest、未标 accepted。

小 CSV：`docs/analysis_topdown_phase2_comparison_20260613.csv`。
