> 文档维护：Claude Fable 5（最近更新 2026-06-11）

# PRD：策略 1 尾部风险 Overlay 三组 A/B（continuous ledger）

> 状态：草案，待 owner review。
> 范围声明：只做组合执行层 overlay 的 portfolio-only A/B；不重训、不改 ledger 语义、不改默认 profile、不 promotion。
> 关联：`DECISION-20260611-02`（effective-window 研究口径）、`PRD_20260611_03`（synthetic continuous 执行模式）、KNOWN_CONSTRAINTS 中 P1/P2 尾部风险约束。

---

## 1. 背景

最新 effective-window official continuous（DECISION-20260611-02 接受的研究口径）：
CAGR `12.04%`、MaxDD `-45.48%`、IR `0.542`、v3 contract Sharpe `0.529 < 0.70`、Calmar `0.265 < 1.0`。

回撤分解（owner 已核，基于旧 official run，窗口 `2021-10-21 → 2024-02-07`）：策略 `-45.93%`，
同期中证1000 `-36.06%`，最差指数（深证成指）`-39.71%`——**beta 解释约 -36pp，另有约 -10pp
超额损失**，trough 落在 2024-02 小微盘踩踏，疑似集中于该末段。

两层风控已实现但从未在 full-period continuous 上启用：

- **P1** `individual_risk_guard_v0`：候选层按六条固定规则打 `tail_risk:*` 标记（`ret_20d<-30%`、
  `drawdown_20d<-30%`、`limit_down_days_20d>=2`、`one_word_limit_days_20d>=1`、总市值<30亿、
  流通市值<20亿，必需字段 NULL 也记风险）；ledger 层对无持仓的风险目标写 `BUY_SKIPPED_TAIL_RISK`，
  不买不候补，已持仓不强制卖。
- **P2** `market_risk_off_v0`：`dws_market_state_daily` 三组触发器（中证1000 走弱 / 宽度走弱 /
  跌停扩散），≥2 组命中或跌停扩散单独命中 → `is_risk_off`，次日跳过全部买单（PIT：t 收盘信号
  只影响 t+1）。

既有约束："P1 full-period A/B 完成前不得把 `individual_risk_guard_v0` 设为默认 profile"——本 PRD
正是该前置 A/B。

## 2. 目标

1. 在同一条 effective-window synthetic prediction 流上，跑三组 portfolio-only continuous 对照：
   P1、P2、P1+P2（`individual_and_market_risk_guard_v0`）。
2. 产出与 baseline 的逐项对比：MaxDD / Calmar / CAGR / Sharpe / IR / 回撤窗口变化。
3. 量化"只禁买"的隐性减仓效应：risk-off 期间现金占比时间序列、`BUY_SKIPPED_TAIL_RISK`
   逐年计数、2024-01~02 末段的超额损失变化。
4. 为两个后续决策提供数据：① 是否将某 profile 设为默认（owner 决策 + 改约束）；
   ② beta 部分是否必须立"市场状态条件化暴露管理" PRD。

## 3. 非目标

- 不重训模型、不重建 panel / matrix / refit、不重做 synthetic merge。
- 不修改 ledger 语义（不实现 risk-off 卖出 / 降仓——那属于后续暴露管理 PRD）。
- 不修改默认 `tail_risk_profile_id=diagnostic_only`；不改 KNOWN_CONSTRAINTS 的 P1 默认约束
  （A/B 结果出来后由 owner 决策另行变更）。
- 不 promotion、不写 ADS；结果与 baseline 同为研究口径，不得标 accepted。

## 4. 实验设计

### 4.1 共同基座

- prediction 源：**复用** 最新 official effective-window synthetic continuous run（以
  PR #174 / `IMPLEMENTATION_STATUS.md` 记录为准，实现时从记忆/manifest 解析，**不得在代码中
  硬编码 run id**）。三个 arm 不做新 merge，直接 `prediction_run_id = synthetic run`。
- 执行模式：与 official continuous 完全一致——`backtest_report --skip-diagnosis
  --skip-tail-risk --skip-qa`（synthetic run 无 panel / 无真实模型 artifact；注意
  `--skip-tail-risk` 跳过的是尾部风险**诊断**步骤，不影响 profile 驱动的 guard 行为），
  `2021-01-04` fresh-start 至 `2026-06-09`、`rebalance_anchor_start=2021-01-04`、biweekly、
  `ledger_exec_v1_lot100`、20 只 / 7.5%、成本 profile 不变。
- 每个 arm 独立新 run_id / backtest_id（建议后缀 `_p1`、`_p2`、`_p1p2` + 新版本号），
  全部写 `ashare_research`；`--force-replace` 只用于同 arm 显式重跑。

### 4.2 三个 arm

| Arm | `tail_risk_profile_id` | 生效机制 |
|---|---|---|
| A1 | `individual_risk_guard_v0` | `05` 候选层打标 + ledger `BUY_SKIPPED_TAIL_RISK` |
| A2 | `market_risk_off_v0` | ledger 读 `dws_market_state_daily`，risk-off 次日禁买 |
| A3 | `individual_and_market_risk_guard_v0` | 两者叠加 |

Baseline = 已有 official continuous（`diagnostic_only`），不重跑。

### 4.3 前置检查

1. `dws_market_state_daily` 在 `2021-01-04 ~ 2026-06-09` 全开市日覆盖且无 NULL `is_risk_off`。
   注意：`sql/qa/11_market_state_checks.sql` 默认窗口是 `2024-01-02 ~ 2026-04-30`，且其
   QA-MKT-3 只断言"表中的行都是开市日"，**没有**反向的"每个开市日都有一行"覆盖断言。
   因此必须：① 跑 `11` 时显式传 A/B 全窗口参数；② 另跑一条 full-window calendar coverage
   查询——交易日历（SSE `is_open=1`）left join market state，断言窗口内每个开市日恰有一行
   当前版本数据且 `is_risk_off` 非 NULL。（owner 2026-06-11 只读抽查：`open_days=1314`、
   `missing_days=0`、`null_is_risk_off=0`、`risk_off_signal_days=170`，当前数据本身满足。）
2. 候选层 tail-risk 必需字段在 synthetic 流对应调仓日上的可用性抽查（避免大面积
   `tail_risk_required_field_null` 使 A1 退化为"全禁买"）。
3. research readiness QA 照常。

## 5. QA 与验证

每个 arm：

1. `qa_continuous_backtest_outputs`（按 arm 的 backtest_id；merge 断言部分与 baseline 同一
   synthetic run，复跑应仍通过）+ `qa_lot_aware_ledger_outputs`。
2. **Guard 生效性断言**（新增轻量验证查询，可入 QA 或脚本）：
   - A1/A3：`BUY_SKIPPED_TAIL_RISK` 订单数 > 0，且 2024-01~02 段计数显著非零；
   - A2/A3：risk-off execution dates 上不存在任何 filled BUY（对照
     `dws_market_state_daily.is_risk_off`，PIT 对齐到次日执行口径）；
   - A2/A3：`BUY_SKIPPED_MARKET_RISK_OFF` 只允许出现在 risk-off execution dates 上；
   - 反向抽查（如做）只比较 **guard 之前**的 candidate / target 输入与 baseline 是否一致，
     **不得**比较 ledger 之后的 filled BUY 路径——A2 首个 risk-off 跳买日后现金、持仓、
     lot rounding 路径即与 baseline 永久分叉，非 risk-off 日的成交行为本就不应一致。
3. 产出对比表（每 arm vs baseline）：CAGR / MaxDD / Calmar / contract Sharpe / IR /
   回撤窗口（peak/trough 日期）/ 年化换手 / risk-off 期现金占比均值与峰值 /
   `BUY_SKIPPED` 逐年计数 / 2024-01-01~02-07 段策略 vs 中证1000 超额。

## 6. 验收标准

| 项 | 要求 |
|---|---|
| 复用 | 零训练、零 merge；三 arm 均复用同一 synthetic prediction run |
| 隔离 | 三 arm 独立 run/backtest id，baseline 未被触碰 |
| guard 生效 | §5.2 生效性断言全过（否则说明 profile 未真正接通，结果无效） |
| QA | 每 arm continuous QA + lot-aware QA 通过 |
| 对比表 | §5.3 全字段，三 arm + baseline 四行 |
| 口径纪律 | 所有结果标记研究口径；不改默认 profile、不 promotion |

## 7. 风险与控制

| 风险 | 控制 |
|---|---|
| 必需风险字段大面积 NULL 使 A1 退化为全禁买 | §4.3.2 前置抽查；A1 结果异常时先查 `filter_reason` 分布 |
| market state 表覆盖缺口导致 A2 假阴性 | §4.3.1：`11` QA 显式传全窗口参数 + full-window calendar coverage 查询（默认参数与断言方向均不够） |
| guard 实际未接通（profile 没传到 05/ledger） | §5.2 生效性断言作为硬门 |
| 误改默认 profile | 本 PRD 不动配置默认值；arm 级显式传参 |
| 结果被解读为 accepted | 与 DECISION-20260611-02 同口径：仅研究复盘事实 |

## 8. 实施顺序

1. 前置检查（§4.3）。
2. A1 → A2 → A3 逐个跑（或并行，资源按 backtest job 串行约束）。
3. 每 arm QA + 生效性断言。
4. 汇总对比表，更新记忆；输出两个决策建议（默认 profile / 暴露管理 PRD 立项）交 owner。
