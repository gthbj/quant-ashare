> 文档维护：GPT-5 Codex（最近更新 2026-06-10）

# 策略1 Research Promotion 运行手册

`ashare_research` 是默认实验产物位置；`ashare_ads` 只接收 owner 明确批准后的正式产物。Promotion 必须通过独立入口执行，不由普通 runner、report、QA 或 acceptance replay 隐式写 ADS。

## 前置条件

- Source research run 已完成 report / diagnosis / QA / acceptance。
- Source model 或 acceptance result 的 `acceptance_status='accepted'`，且 `accepted=TRUE` 可在 `research_acceptance_result` 中查到；只有 owner 明确要求时才可传 `--allow-unaccepted`。
- Promotion 操作者已给出 `promotion_id`、`approval_ref`、`approved_by`、`acceptance_contract_version` 和 `acceptance_contract_sha256`。
- 运行身份需要读取/更新 `data-aquarium.ashare_research`，写入 `data-aquarium.ashare_ads`，并可写 `research_promotion_manifest`。普通 experiment runner 不应具备常规 ADS 写入权限。

## Dry Run

```bash
python -m scripts.strategy1.promote_research_to_ads \
  --promotion-id promo_<model_or_run>_<yyyymmdd> \
  --source-run-id <research_run_id> \
  --source-backtest-id <research_backtest_id> \
  --source-model-id <research_model_id> \
  --window-start <YYYY-MM-DD> \
  --window-end <YYYY-MM-DD> \
  --approval-ref <PR-or-issue-or-owner-record> \
  --approved-by <owner> \
  --acceptance-contract-version <contract_version> \
  --acceptance-contract-sha256 <contract_sha256> \
  --dry-run --print-sql
```

检查输出中的 `target_ads_tables`、日期窗口、approval 字段和 generated SQL。默认 promotion 目标覆盖 registry、prediction、candidate、portfolio target、order plan、backtest trade/position/nav/ledger state/summary 和 signal monitor；训练面板很大，默认不复制，只有 owner 明确要求时传 `--include-training-panel` 或单独 `--target-role training_panel`。

## Execute

确认 dry-run 后去掉 `--dry-run`：

```bash
python -m scripts.strategy1.promote_research_to_ads \
  --promotion-id promo_<model_or_run>_<yyyymmdd> \
  --source-run-id <research_run_id> \
  --source-backtest-id <research_backtest_id> \
  --source-model-id <research_model_id> \
  --window-start <YYYY-MM-DD> \
  --window-end <YYYY-MM-DD> \
  --approval-ref <PR-or-issue-or-owner-record> \
  --approved-by <owner> \
  --acceptance-contract-version <contract_version> \
  --acceptance-contract-sha256 <contract_sha256>
```

默认 `--force-replace` 为关闭状态；如果 ADS 目标已有相同 run/model/backtest/date 窗口的行，脚本会 fail-fast。只有 owner 明确批准覆盖已有正式产物时才传 `--force-replace`。

## 验证

- `research_promotion_manifest` 有且只有一个 `promotion_id` 对应行，`promotion_status='succeeded'`，`target_ads_tables` 与 dry-run 一致。
- 对应 research registry / summary / acceptance rows 已标记 promoted，并记录 `promotion_id` 或 `promotion_manifest_id`。
- ADS 目标表中只出现本次 source run/model/backtest/date window 的正式行；训练面板未被默认复制。
- 普通 research runner 后续仍默认写 `ashare_research`，不因本次 promotion 改回 ADS。
