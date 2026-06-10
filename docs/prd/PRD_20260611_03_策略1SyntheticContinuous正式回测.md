> 文档维护：Claude Fable 5（最近更新 2026-06-11）

# PRD：策略 1 Synthetic Continuous Prediction 与正式 Continuous Ledger

> 状态：草案，待 owner review。
> 范围声明：本文只定义年度预测合并与正式连续回测的生成方案；不改模型、不改选参、不做 promotion。正式执行依赖 `PRD_20260611_02` final refit 完成，但**代码实现与彩排不依赖**（见 §6）。
> 关联：`docs/prd/PRD_20260610_03_策略1年度滚动选参.md`、`docs/prd/PRD_20260610_04_策略1年度滚动执行工程化.md` §9、`docs/prd/PRD_20260611_02_策略1年度滚动FinalRefit.md`。

---

## 1. 背景

`2021-2026` 年度链路已跑通，但两个事实决定了现有结果不能直接作为正式结论：

1. **年度 backtest 都是 fresh-run**，资金状态每年重置，拼接 NAV 被既有约束明确禁止；正式结果必须来自单一 continuous ledger（路径 A）或通过 resume-continuous QA 的 segment ledger（路径 B）。
2. **prediction 表每个 run 同时包含 valid 段与 test 段的行**（本次实跑确认）。直接按 run 全量拼接会把 valid 段预测混入连续流，且相邻年度的 valid/test 段日期重叠，必须严格按年度 test 窗口切片。

本 PRD 把 PRD_20260610_04 §9 的路径 A 落为可实现规约，并把切片陷阱显式化。

## 2. 目标

1. 定义逐年 prediction 切片规则与合并产物（synthetic continuous prediction run）。
2. merge 输入参数化为显式 manifest，彩排与正式执行共用同一套代码。
3. 合并完整性 QA：无跨年重叠、无年界缺口、行数对账、溯源完整。
4. 单条 official continuous ledger 执行口径与验收标准。
5. 彩排机制：用 pre-refit 预测演练全链路，并为 refit 前后对比留下基线。

## 3. 非目标

- 不实现 final refit（PRD_20260611_02）。
- 不改 ledger 语义（沿用 `ledger_exec_v1_lot100`）。
- 不做 promotion、不写 ADS。
- P0 不实现路径 B（resume-continuous segment），保留为备选；若路径 A 的 synthetic 合并被 owner 否决再启用。

## 4. Merge 设计

### 4.1 输入 manifest（参数化，禁止硬编码）

merge 的唯一输入是显式 manifest，逐年声明：

```json
{
  "synthetic_run_id": "s1_annual_roll_synth_continuous_2021_2026_n20_w075_vYYYYMMDD_NN",
  "years": [
    {"backtest_year": 2021, "source_run_id": "<refit 或彩排 run>", "predict_start": "2021-01-04", "predict_end": "2021-12-31"},
    {"backtest_year": 2026, "source_run_id": "...", "predict_start": "2026-01-05", "predict_end": "2026-06-09"}
  ]
}
```

- `source_run_id` 由调用方显式给出：彩排传 pre-refit run，正式传 refit run。**代码不感知 refit 与否**，解耦由 manifest 承担。
- manifest 本体作为 artifact 落 GCS，并在 synthetic run 的溯源字段记录其 URI 与 hash。

### 4.2 切片规则

对每年只取：

```text
predict_date BETWEEN predict_start AND predict_end
```

- 显式排除 valid 段行（valid 行的 `predict_date` 落在窗口外，天然被边界排除——QA 仍需独立验证，不依赖这一推断）。
- 窗口值来自 resolved plan 的年度实际边界，不手填日历值。

### 4.3 Synthetic run 写入

- 切片行写入 research prediction 表，`run_id = synthetic_run_id`，原行字段保留（`model_id` 保留各年 refit 模型 id，体现逐年换模型的事实）。
- 不修改、不删除任何 source run 的行。

## 5. 合并完整性 QA

新增 QA（SQL step，登记 catalog），至少断言：

| 断言 | 口径 |
|---|---|
| 无跨年重叠 | synthetic run 内 `(predict_date, sec_code)` 唯一 |
| 无年界缺口 | 每年切片的首末 `predict_date` 等于 manifest 窗口边界对应的实际交易日；相邻年份之间无开市日空洞（对照 `dim_trade_calendar`） |
| 行数对账 | synthetic 总行数 == Σ 各年源 run 在切片窗口内的行数 |
| 溯源 | synthetic run 的 manifest URI / hash 可回查，且每年 `model_id` 与 manifest 的 source run selected 模型一致 |
| valid 排除 | synthetic run 内不存在任何源 run valid 段日期的行 |

## 6. 彩排与正式执行

| | 彩排（rehearsal） | 正式（official） |
|---|---|---|
| manifest source | 当前 pre-refit 六年 run | PRD_20260611_02 完成后的 refit run |
| run/backtest id | 必须含 `rehearsal` 标记 | 正式命名（PRD_20260610_04 §6.3） |
| 结果定位 | diagnostic_only，报告显式标注 | official continuous result |
| 依赖 | 无（现在即可做） | refit 六年重跑完成 |

彩排的两个目的：在真实"脏"数据（含 valid 段、跨年重叠风险）上验证切片与 QA；为 refit 前后提供同一管线的对照基线，量化 final refit 的影响。

## 7. Official Continuous Ledger

- 单条 backtest：`2021-01-04` fresh-start 跑到 `2026-06-09`，`initial_state_mode='fresh'`。
- `rebalance_anchor_start='2021-01-04'`，`biweekly`，`ledger_exec_v1_lot100`，成本 profile 沿用现行口径。
- prediction 源 = synthetic continuous run。
- backtest id 按 PRD_20260610_04 §6.3：`bt_s1_annual_roll_continuous_2021_2026_n20_w075_vYYYYMMDD_NN`（彩排版加 `rehearsal`）。
- 跑完执行 runner QA + lot-aware ledger QA + 本 PRD 合并 QA；报告必须把年度 diagnostic、彩排 continuous、official continuous 三类结果分开呈现。

## 8. 验收标准

| 验收项 | 要求 |
|---|---|
| manifest 驱动 | merge 代码无任何硬编码 run_id；彩排与正式走同一入口 |
| 切片正确 | §5 全部 QA 断言通过（彩排与正式各跑一次） |
| 正式前置 | official 执行的 manifest source 全部为 refit run（QA 校验 `refit=true` 溯源） |
| 单一 ledger | official 结果只有一个 continuous backtest id，无年度拼接 |
| research-first | 全部写 `ashare_research`；promotion 另行 owner 审批 |

## 9. 风险与控制

| 风险 | 控制 |
|---|---|
| valid 段混入连续流 | 窗口切片 + QA 独立断言 valid 排除 |
| 跨年重叠 / 缺口 | 唯一性与交易日历缺口 QA |
| 彩排结果被误读为正式 | id 强制含 `rehearsal`，summary 标 diagnostic_only |
| 正式执行误用 pre-refit run | QA 校验 manifest source 的 refit 溯源 |
| synthetic run 与源 run 混淆 | 独立 run_id 命名前缀 `synth_continuous`，源 run 只读 |

## 10. 实施顺序

1. merge + QA 实现与单元测试（可立即开始，不等 refit）。
2. 彩排：pre-refit manifest → synthetic run → 合并 QA → rehearsal continuous ledger。
3. 等 PRD_20260611_02 六年 refit 完成。
4. 正式 manifest → official synthetic run → 合并 QA → official continuous ledger → 全套 QA 与报告。
