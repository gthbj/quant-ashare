# topdown Phase 2 T0 三方对比

> 文档维护：GPT-5.5（最近更新 2026-06-13）

## 结论

- 按 PRD_20260613_04 §3 预登记规则，本次判读为 **topdown 证伪**：长窗 topdown CAGR -77.13%、Calmar -0.772，均显著低于 v1 official baseline 的 CAGR 15.36%、Calmar 0.4103。
- 现金门槛也未过：长窗平均现金 76.31%，显著高于预登记的 `<10%` 要求；MaxDD -99.95%，期末总收益 -99.95%。
- 本报告不做 accepted / promotion / 默认构造变更；结果仅写 `ashare_research`，ADS 与 promotion 反查为 0。后续现金拖累问题不建议继续在当前 topdown 构造路线内推进，应转入碎股/资金口径或其他独立路线。

## 执行证据

| 项 | 值 |
| --- | --- |
| source main | `origin/main@779089d`（PR #215 后又含 PR #216 文档/记忆变更；runner 代码无额外 main 变更） |
| live branch hotfix | `PlanRow.planned_buy_shares` 保留 topdown ceil-lot 股数，避免 `want_value / exec_open` 浮点回算把 500 股压成 400 股 |
| image tag | `topdown-p2-t0-live-779089d-20260613-03` |
| image digest | `sha256:1e91a5733df2cd7a38c2275cdb3a75f246fabe539c1e57db992c3a36bef5c9db` |
| Cloud Build | `bc6cca10-565c-4244-a227-e2cefd9ad9d3` |
| Cloud Run job pin | `strategy1-backtest-report-job` generation `54`, digest pin；`latest` 仍为 `sha256:fdb61f8141e240c377b3faaa21b5e6efef9c783ebb9e04923ff3b675b8d54bc2` |
| boot smoke | `strategy1-backtest-report-job-phtfj` succeeded |
| formal execution | `strategy1-backtest-report-job-j9m5t` succeeded，jobGeneration `54`，completion `2026-06-13T01:36:09.984850Z` |
| run / backtest | `s1_topdown_t0_continuous_true5y_2021_2026_v20260613_01` / `bt_s1_topdown_t0_continuous_true5y_2021_2026_v20260613_01` |
| prediction stream | `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01` |
| ledger / resume | `ledger_exec_v2_lot100_topdown` / `cloudrun_lot100_topdown_resume_v1` |
| CA / tax | `cash_div_and_split_v1` / `flat_10pct` |
| tail risk | `diagnostic_only` |
| status | `acceptance_status=NULL`，`promotion_status=not_promoted` |

## QA 与 Research-only

| 检查 | 结果 | job id / 证据 |
| --- | --- | --- |
| `qa_continuous_backtest_outputs` | passed | `11cb7abb-f015-467c-be68-5f1f1827a569`，显式 `p_expected_ledger_version=ledger_exec_v2_lot100_topdown` / `p_resume_policy_id=cloudrun_lot100_topdown_resume_v1` |
| `qa_lot_aware_ledger_outputs` | passed | `849654cd-9802-43ff-afcf-aab3c14c5cea` |
| `qa_topdown_construction_outputs` | passed | `2e99bef8-dfab-4828-aced-1a6de40522e4` |
| `qa_corporate_action_ledger_outputs` | passed | `413ff54a-be61-413a-9422-1ce5ad0bc611` |
| ADS 反查 | passed | 9 张 ADS run/backtest scoped 表均 `0` 行 |
| promotion manifest | passed | `ashare_research.research_promotion_manifest` 反查 `0` 行，job `f27c5e31-09af-46ac-9a66-5142509ede8b` |

Research 输出行数：candidate `279625`、target `2780`、order `4830`、trade `6548`、position `1128`、NAV `1314`、ledger_state `1314`。

## 双窗口指标

长窗使用 `2021-01-04..2026-06-09`。v1 official baseline 长窗 CAGR / Sharpe / Calmar 使用 dividend resume 修正后的展示锚点；MaxDD 不变。Phase 0 paper T0 使用 `docs/analysis_strategy1_p1_market_cap_rules_20260613_metrics.csv` 对应的日级 GCS artifact 复算。

| 对象 | CAGR | Compound Sharpe | Calmar | MaxDD | Total Ret | Avg Cash | Annual Turnover | Avg Holdings | Max Weight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| topdown v2 live ledger | -77.13% | -1.0831 | -0.7717 | -99.95% | -99.95% | 76.31% | 42.97 | 0.86 | 99.31% |
| v1 official baseline stitched | 15.36% | 0.6685 | 0.4103 | -37.43% | 110.52% | 29.92% | 35.05 | 16.11 | 7.82% |
| Phase 0 paper T0 | 11.81% | 0.3781 | 0.2013 | -58.67% | 78.88% | 2.58% | 39.70 | 14.54 | 47.19% |

静态近窗使用 `2024-01-02..2026-04-30`，这是 v3 replay 既定静态口径，不是 PRD_20260613_05 提案的动态 YTD 窗。注意 topdown 在近窗开始时 NAV 已约 `0.000458`（净值约 45.82 元），近窗内 0% CAGR / 0% MaxDD 只是“近乎归零后全现金不动”的局部窗口读数，不代表风险改善。

| 对象 | CAGR | Compound Sharpe | Calmar | MaxDD | Total Ret | Avg Cash | Annual Turnover | Avg Holdings | Max Weight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| topdown v2 live ledger | 0.00% | NA | NA | 0.00% | 0.00% | 100.00% | 0.00 | 0.00 | 0.00% |
| v1 official baseline stitched | 38.28% | 1.4642 | 1.1041 | -34.67% | 105.75% | 15.64% | 41.03 | 18.89 | 7.82% |
| Phase 0 paper T0 | 37.17% | 1.2301 | 0.9143 | -40.66% | 102.11% | 1.99% | 43.19 | 16.37 | 35.00% |

## 差异读数

| 窗口 | topdown vs v1 CAGR | topdown vs v1 Calmar | topdown vs Phase0 paper CAGR | topdown vs Phase0 paper Calmar |
| --- | --- | --- | --- | --- |
| 长窗 | -92.49% | -1.182 | -88.94% | -0.973 |
| 静态近窗 | -38.28% | NA | -37.17% | NA |

## Crunch 段

`crunch` 固定为 Phase 0 口径 `2024-01-01..2024-02-07`，benchmark 为 `000852.SH`。live/v1 用落库 NAV 复算策略收益，并用 `dwd_index_eod.pct_chg` 对齐 `000852.SH`。

| 对象 | Strategy | 000852 | Excess |
| --- | --- | --- | --- |
| topdown v2 live ledger | 0.00% | -18.50% | 18.50% |
| v1 official baseline stitched | -34.67% | -18.50% | -16.16% |
| Phase 0 paper T0 | -40.66% | -18.50% | -22.15% |

## 口径说明

- topdown live 是真实 Cloud Run ledger：会处理卖出失败、pending sell、公司行为和实际现金约束；Phase 0 paper 是 raw 价格本地模拟，不模拟卖出失败/pending sell/CA，因此只作为机制校准，不作为同口径验收候选。
- 本次 live 初跑暴露 `QA-TOPDOWN-4`：topdown 构造层已用 ceil-lot 接受 500 股，但执行层通过 `want_value / exec_open` 浮点回算时可能下取整成 400 股。当前 PR 增加 `planned_buy_shares`，topdown 路径直接使用已审定股数；v1 路径仍按原 `want_value / exec_open` 语义。最终 digest 与 QA 均基于该 hotfix。
- v1 baseline 长窗现金权重按落库 NAV 复算，约 `29%`；报告的 v1 长窗 CAGR/Sharpe/Calmar/MaxDD 采用 owner 指定的 dividend resume 修正展示锚点：`15.36% / 0.6685 / 0.4103 / -37.43%`。
- 本报告未改 prediction 流、未训练、未写 ADS、未写 promotion manifest、未标 accepted。

小 CSV：`docs/analysis_topdown_phase2_comparison_20260613.csv`。
