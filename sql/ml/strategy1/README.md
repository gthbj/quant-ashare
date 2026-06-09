> 文档维护：GPT-5 Codex（最近更新 2026-06-10）

# Historical Strategy1 SQL Namespace

`sql/ml/strategy1/**` no longer contains active Strategy1 shared SQL.

Active candidate、portfolio、order、report、QA 和 acceptance SQL 已迁移到
`sql/strategy1/**`，并由 `configs/strategy1/active_step_catalog.yml` 统一维护
stable step name、旧路径、目标路径、调用方和参数契约。

旧 BQML-only `02_train_bqml_logistic_candidates.sql`、
`03_select_model_and_register.sql`、`04_predict_daily.sql` 和 SQL ledger fallback
`08_run_backtest.sql` 已退役并删除；历史 BQML / SQL runner 结果只作为
ADS / GCS / PRD / memory 中的 historical audit reference。

如需运行当前 Strategy1 shared SQL，请使用：

```bash
python -m scripts.strategy1_cloudrun.backtest_report --help
python -m scripts.strategy1_cloudrun.orchestrate_sklearn_native_search --help
python scripts/strategy1/run_acceptance_gate_v3_replay_qa.py --help
```

或直接查看 `sql/strategy1/README.md` 中的新路径说明。
