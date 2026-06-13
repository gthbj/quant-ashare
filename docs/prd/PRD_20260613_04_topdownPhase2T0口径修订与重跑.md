# PRD：topdown Phase 2 — T0 口径修订与 research-only continuous 重跑

> 状态：草案，待 Codex review 收敛后定稿。
> 范围声明：①修订 PRD_20260611_10 的 P1 绑定条款（owner 2026-06-13 已裁决：Phase 2 以 T0 / 无 P1 口径进入）；②解除 topdown ledger 对 individual 风控 profile 的 fail-fast 绑定（小代码改动）；③执行 Phase 2 research-only continuous 重跑与三方对比。**不改 v1 ledger 语义与 hash、不改默认 `tail_risk_profile_id=diagnostic_only`、不改默认 `corporate_actions=none_v1`、不 promotion、不标 accepted、输出只写 `ashare_research`**。
> 关联：PRD_20260611_10（本 PRD 修订其 §2.4 并执行其 Phase 2）；PRD_20260613_01 / PR #210（P1 不可救的预登记证据，owner 据此裁决）；DECISION-20260612-03（CA-on 纪律）；PR #189（Phase 1 代码：`ledger_exec_v2_lot100_topdown` + `qa_topdown_construction_outputs`）。

---

## 1. 决策依据与修订内容

### 1.1 owner 裁决（2026-06-13）

PRD_20260613_01 五臂 paper 批量证明：P1 全形态（完整六条 / 仅形态组 / 两种饱和回退）均未过预登记四门槛——修复臂消除了现金踏空但仍丢 5.5-7.7pp CAGR（持仓构成通道）且丢掉 crunch 保护；P1 的价值与代价绑在同一组规则上不可分离。owner 据此裁决：**Phase 2 以 T0（无 P1）口径进入；个股尾部风控从构造层移除，移交模型层（riskfeat 路线，基建已存在）与独立 overlay 路线（market-state 条件化），不在构造层重试**。

### 1.2 PRD_10 条款修订（supersede 声明）

- **§2.4 P1 绑定条款 superseded**：原文"P1 过滤必须以替换语义实现……此绑定是本构造规格的组成部分"改为——topdown 构造**默认不启用个股过滤**（`diagnostic_only`）；若未来实验显式启用 P1 类 profile，则替换语义红线仍然适用（禁止复用跳过留现金语义，#179 A1 教训不变）。
- 其余规格不变：自上而下贪心、`position_floor_count=20`（`min_position_weight=5%`）、无单票上限、`walk_depth=50` 统一阈值、整单跳过 `topdown_whole_order_skip_v2`、`max_realized_weight` 必报、10 万真实部署口径。
- 本修订以本 PRD 为准，不回改 PRD_10 原文（历史 PRD 保持审计原貌，PRD_10 文首加一行修订指针注记）。

### 1.3 代码改动（唯一语义变更点）

- `src/quant_ashare/strategy1/ledger.py:1593-1594` 的 fail-fast（`topdown ledger requires individual tail-risk guard profile`）放宽为：topdown 允许 `diagnostic_only`；若显式传入 P1 类 profile 行为不变。同文件 1276 行附近的 topdown P1 路径核查：`diagnostic_only` 下 P1 过滤分支必须自然失活（`has_individual_risk_guard=False`），不引入新分支语义。
- `qa_topdown_construction_outputs.sql` 中"P1 标记存在性 / `BUY_SKIPPED_TAIL_RISK`"类断言改为 **profile 条件化**（`diagnostic_only` 时跳过 P1 专属断言，其余 topdown 构造不变量照常）；catalog `required_params` 若有增减同步。
- v1 不变量：`ledger_params_hash` 默认黄金值、v1 全部行为与测试**必须原值通过**；topdown+`diagnostic_only` 组合补单测（不再 raise、P1 过滤失活、`cash_redistribution` 标签仍为 `topdown_whole_order_skip_v2`）。

## 2. Phase 2 执行规格

1. **输入**：当前研究 baseline 的 synthetic prediction 流（resolver 从记忆解析，禁止硬编码；当前应为 `s1_annual_roll_synth_continuous_true5y_..._v20260611_01`）。零训练、不改 prediction。
2. **运行**：Cloud Run `backtest_report` 一次 fresh continuous，窗口 `2021-01-04..2026-06-09`，`ledger_exec_v2_lot100_topdown` + `--use-topdown-ledger`，`tail_risk_profile_id=diagnostic_only`，显式 `corporate_actions=cash_div_and_split_v1` / `dividend_tax_mode=flat_10pct`（CA-on 纪律；staleness 断言现可过——事件可见上界已推进至 2026-06-12+）；`initial_capital=100000`；成本 profile 与 official baseline 相同；synthetic 流约束沿用：`--skip-diagnosis --skip-tail-risk --skip-qa`，外接 QA。
3. **QA**：`qa_continuous_backtest_outputs` + `qa_lot_aware_ledger_outputs` + `qa_topdown_construction_outputs` + `qa_corporate_action_ledger_outputs`；ADS / promotion manifest 反查 0 行。
4. **三方对比报告**（`docs/分析-topdownPhase2三方对比-<date>.md`，小 CSV 入库）：
   - topdown v2 real ledger vs **v1 official baseline**（CAGR 15.36% / Sharpe 0.6685 / Calmar 0.4103 / MaxDD -37.43% / 现金权重 ~29% / 换手 / 集中度 / crunch 段超额）——同口径首次可直接互比；
   - topdown v2 real vs **Phase 0 paper T0 读数**——量化 paper 简化（卖出失败 / pending sell / raw vs CA）偏差，校准 paper 工具；
   - 双窗口披露：长窗（全窗）与 2024-01-02..2026-04-30 近窗各报一组指标（服务 PRD_20260613_05 的窗口语义决策，不预设哪个是判定窗）。

## 3. 预登记判读（先写后跑）

1. **构造切换建议成立**：topdown 在长窗同时满足 (a) CAGR ≥ baseline − 1pp；(b) Calmar ≥ baseline；(c) 平均现金权重 < 10%（现金拖累确实消灭且没有用更差的风险换）→ 报告建议 owner 把 topdown 设为后续实验构造口径（最终切换仍是 owner 决策 + 单独决策记录）。
2. **互有胜负**：列 tradeoff 表（收益/回撤/换手/集中度/crunch）交 owner，不下建议。
3. **topdown 证伪**：CAGR 与 Calmar 双双劣于 baseline → 报告结论"现金拖累的收益被构造的其他代价吃掉"，topdown 路线收口，现金拖累问题转入其他路线（如碎股/资金口径）。
4. 不做 accepted / promotion / 默认构造变更。

## 4. 红线与验收

- v1 黄金 hash 原值；默认 profile / 默认 CA 不变；research-only；resolver 不硬编码。
- 验收：全量 pytest（含新增 topdown+diagnostic_only 单测）；QA 四件套实跑通过；报告 + 预登记判读；按 UPDATE_PROTOCOL 滚动更新记忆/TODO。
- 实现与重跑同一 PR 链（代码改动小且重跑依赖它）；镜像：`strategy1-backtest-report-job` 需要含本修订代码的新镜像（按既有不可变 digest 纪律构建 + boot smoke，不更新 latest tag 的既有规则沿用 Phase C 先例）。

> 文档维护：Claude Fable 5（2026-06-13）
