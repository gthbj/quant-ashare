> 文档维护：Claude Fable 5（最近更新 2026-06-11）

# PRD：策略 1 Cloud Run Ledger Resume 验收闭环（短）

> 状态：草案，待 owner review。
> 范围声明：对已合入但从未验收的 Cloud Run Python ledger resume 做测试 + 真实数据验收 + runbook 固化；research-only，不写 ADS。
> 关联：PR #127（resume 实现已合入）、`TODO.md`「实现 Cloud Run Python ledger resume」、KNOWN_CONSTRAINTS「正式连续结果默认 fresh-run，除非 resume 已实现并通过 resume consistency QA」。

---

## 1. 背景

resume 代码已随 PR #127 合入 main：`ledger.py` 有 `parent_backtest_id` / `state_as_of_date` 参数与
fresh/resume fail-fast 校验，state 表 role 已支持 research
（`backtest_ledger_state_daily` → `research_backtest_ledger_state_daily`），QA SQL 已迁移到
`sql/strategy1/qa/`（`qa_cloudrun_ledger_resume_outputs.sql`、`qa_ledger_resume_consistency.sql`）。
但**从未跑过测试、Cloud Run 或 BigQuery 验收**；当前 official continuous 全部 fresh-start，分段续跑 /
长窗口恢复能力实际不可用。

## 2. 目标

1. **测试闭环**：跑全部 resume 相关 pytest；验收中暴露的实现缺陷，修复 + 回归属于本 PRD 范围。
2. **真实数据验收（research-only）**：
   - parent = 当前 official continuous backtest（从记忆/manifest 解析 id，不硬编码）；
   - 在 rebalance 边界附近选 cut date（建议 2024 年末），从 parent state resume 跑 cut →
     `2026-06-09` 的 segment（新 run/backtest id，写 `ashare_research`）；
   - **边界参数硬门**（与 KNOWN_CONSTRAINTS resume 条款一致，违反即验收无效）：
     `p_predict_start` 必须等于 `state_as_of_date` 后下一 SSE 开市日；biweekly 必须显式传
     `p_rebalance_anchor_start` = parent 的原调仓锚点（当前 official continuous 为
     `2021-01-04`，实现时从 parent 记录解析），禁止按 segment start 重算双周奇偶；
     fresh 对照切片使用同一锚点，保证 compare window 调仓日逐一对齐；
   - 与 fresh run 同窗口切片做一致性比对：NAV、现金、日收益、持仓、成交事实逐日一致；
   - 跑 `qa_cloudrun_ledger_resume_outputs` + `qa_ledger_resume_consistency` 两套 QA。
3. **Runbook 固化**：resume 参数语义（`initial_state_mode` / `parent_backtest_id` /
   `state_as_of_date` / `resume_policy_id`）、适用场景与禁区写入运行手册。

## 3. 非目标

- 不做 scheduler 集成（属 `PRD_20260611_07` 之后的事）。
- 不改变"正式连续结果默认 fresh-run"的默认值——resume 验收通过后成为**可用工具**，
  分段产出正式结果仍需逐次 owner 批准。
- 不写 ADS、不 promotion、不动现有 official 结果。

## 4. 验收标准

| 项 | 要求 |
|---|---|
| 测试 | resume 相关 pytest 全过（含验收中新增的回归用例） |
| 边界参数 | `p_predict_start` = `state_as_of_date` 次 SSE 开市日；biweekly 显式 `p_rebalance_anchor_start` = parent 原锚点（不得按 segment start 重算奇偶）；fresh 对照同锚点 |
| 一致性 | resume segment 与 fresh 同窗口切片：NAV/现金/日收益/持仓/成交逐日一致（两套 resume QA 通过） |
| 隔离 | 验收产物全部在 `ashare_research`，parent 未被触碰 |
| runbook | resume 参数语义与适用边界落档 |
| 记忆同步 | 完成后更新 KNOWN_CONSTRAINTS 对应条款（"resume 已实现并通过 consistency QA"的例外条件状态）与 TODO |

## 5. 风险与控制

| 风险 | 控制 |
|---|---|
| state 表从未在真实路径写过，schema/字段语义与实现漂移 | 验收第一步先跑最小 smoke 写 state 并人工核对字段 |
| cut date 选在 pending sell / 持仓跨界处导致状态不完整 | cut date 选 rebalance 边界 + QA 显式断言 pending sell 延续一致 |
| 一致性失败被当作"差不多就行" | 逐日一致是硬门；失败即修实现，不放宽断言 |
