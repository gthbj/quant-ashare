> 文档维护：GPT-5 Codex（最近更新 2026-06-11）

# 策略 1 Cloud Run 训练回测运行手册

本文对应 `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md` 的第一版实现。

## 1. 当前边界

当前 Cloud Run runner 已提供：

1. `quant_ashare.strategy1.train_predict`：读取既有训练面板，用 scikit-learn logistic regression 训练候选，做 valid 选型、score orientation、sklearn vs BQML parity，按当前 dataset role 写 registry 与 prediction。
2. `quant_ashare.strategy1.backtest_report`：复用 cataloged SQL 生成候选 / 组合 / 订单，默认使用 Cloud Run Python `ledger_exec_v1_lot100` fresh-start 回测，随后跑报告、诊断和 QA。
3. `quant_ashare.strategy1.pipeline_control`：按 manifest 启动 Cloud Run Jobs，并写当前 dataset role 对应的 experiment status 表、使用 GCS generation-guarded lock。未设置 `--max-parallel-experiments` 或传 `0` 时，resolved 并发数等于本次可执行实验数。
4. `quant_ashare.strategy1.prepare_matrix`、`train_candidate_task`、`select_register_predict`：task fan-out 训练路径。`prepare_matrix` 一次性读取 BigQuery 训练面板并生成 GCS frozen matrix；每个 Cloud Run task 只训练一个 candidate；reducer 统一选型、登记模型并写预测。
5. `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`：按 sklearn native PRD 执行 36 候选 search，valid-only 选 Top5，再为 Top5 生成独立 prediction / backtest / report / diagnosis；同一 orchestrator 也承载 Cloud Run Python baseline search 的通用 TopK 流程。
6. `scripts/strategy1_cloudrun/orchestrate_cloudrun_python_baseline_search.py`：Cloud Run Python baseline search 入口，当前用于 PRD04 LightGBM wave 2 / wave 3，以及 PRD-20260606-03 风险特征 wave 4。
7. `sql/strategy1/qa/qa_cloudrun_runner_outputs.sql`：校验 Cloud Run backend、sklearn artifact、prediction orientation、model-quality parity、resolved 并发契约，以及 task fan-out matrix/work-unit 审计字段。
8. `sql/strategy1/qa/qa_cloudrun_orchestrator_status.sql`：校验 Cloud Run orchestrator 状态表、锁元数据、execution id 和 task fan-out 状态行。
9. `sql/strategy1/qa/qa_sklearn_native_search_outputs.sql`：校验 sklearn native TopK 产物、valid-only 排名、uploaded 报告/诊断、native acceptance gate 和 test 复用记录。
10. `sql/strategy1/qa/qa_cloudrun_python_baseline_search_outputs.sql`：校验 Cloud Run Python LightGBM baseline search 的 TopK、CV 证据、共享验收契约、test reuse 和 final_holdout watch。
11. `sql/strategy1/qa/qa_risk_feature_search_outputs.sql`：校验风险特征搜索的 feature schema/delta hash、市场状态覆盖、feature importance、wave 4 test reuse 和 `max_drawdown >= -18%` 风险目标。
12. `scripts/strategy1/analyze_tail_risk.py` 与 `sql/strategy1/qa/qa_tail_risk_outputs.sql`：在 TopK 回测完成后只读 ADS/DWD/DIM，输出最大回撤窗口、持仓贡献、跌停/不可卖暴露和选股画像，并校验 ADS pre/post hash 未变化。
13. `sql/dws/08_dws_market_state_daily.sql` 与 `sql/qa/11_market_state_checks.sql`：生成并校验 P2 市场状态 risk-off 证据表；`backtest_report.py` 在 `tail_risk_profile_id=market_risk_off_v0` 或 `individual_and_market_risk_guard_v0` 时由 Python ledger 读取该表并跳过 risk-off 次日买单。
14. `scripts/strategy1/diagnose_acceptance_gate_v2.py` 与 `sql/strategy1/acceptance/qa_acceptance_gate_v2_outputs.sql`：按 `model_acceptance_contract_v2` 只读生成验收门 v2、10/20/30/40 组合可行性、eligible benchmark 和 score orientation audit artifact；不训练、不改 prediction、不写 ADS。
15. `sql/strategy1/qa/qa_lot_aware_ledger_outputs.sql`：校验 Cloud Run Python lot-aware ledger 的整数手成交、odd-lot 清仓、below-lot 跳单、现金和 summary lot 参数。
16. `sql/strategy1/qa/qa_cloudrun_ledger_resume_outputs.sql` 与 `sql/strategy1/qa/qa_ledger_resume_consistency.sql`：校验 Cloud Run Python `ledger_exec_v1_lot100` resume child 与 full fresh continuous parent 的同窗口切片逐日一致，并检查 parent state、resume metadata、ledger version、resume policy、原始 rebalance anchor 和 next-open 边界。
17. `sql/strategy1/qa/qa_topdown_construction_outputs.sql`：校验 `ledger_exec_v2_lot100_topdown` 的自上而下整手构造参数、零现金缩股、P1 标记生效、full-rank 输入完整性和超深度持仓卖出失败追溯。

当前限制：

1. 训练面板 SQL 由 runner config 的 `training_panel_step` 指定；基础面板为 `build_training_panel_base`，风险特征面板为 `build_training_panel_risk_feature`。
2. candidate / portfolio / order 仍使用 `sql/strategy1/execution/**` BigQuery SQL。
3. Python ledger 默认仍为 fresh-start；resume 路径已实现并通过 PRD_20260611_08 research-only 验收，但每次作为正式分段结果使用前仍必须显式 owner 批准并跑 resume QA。`ledger_exec_v1_lot100` / `ledger_exec_v2_lot100_topdown` 都是 Python-only 执行语义，不再要求与 SQL FLOAT-shares runner 等价。
4. Cloud Run Jobs、Artifact Registry、IAM 和服务账号需按本文部署，不在代码中保存任何凭据。

## 2. 本地 dry-run

```bash
python -m quant_ashare.strategy1.pipeline_control \
  --project data-aquarium \
  --region asia-east2 \
  --manifest configs/strategy1/oq010_experiments_v0.json \
  --config configs/strategy1/cloudrun_runner_default.yml \
  --experiment-id oq010_a0_n5_w20 \
  --max-parallel-experiments 0 \
  --dry-run
```

期望：

1. 输出 `selected_experiment_count=1`。
2. 输出 `resolved_max_parallel_experiments=1`。
3. 输出将执行的 `gcloud run jobs execute strategy1-train-predict-job` 和 `strategy1-backtest-report-job` 命令。

task fan-out 训练路径 dry-run：

```bash
python -m quant_ashare.strategy1.pipeline_control \
  --project data-aquarium \
  --region asia-east2 \
  --manifest configs/strategy1/oq010_experiments_v0.json \
  --config configs/strategy1/cloudrun_runner_default.yml \
  --experiment-id oq010_a0_n5_w20 \
  --train-mode task_fanout \
  --candidate-parallelism 0 \
  --dry-run
```

期望：

1. 输出 `cloudrun_prepare_matrix`、`cloudrun_train_candidate_fanout`、`cloudrun_select_register_predict`、`cloudrun_backtest_report` 四类 step。
2. `--candidate-parallelism 0` 表示候选 work unit 默认全并发；若 owner 显式传 `N > 0`，orchestrator 按 N 个 task 一批分批执行。
3. candidate task 命令只读取 `matrix_uri`，不直接查询 BigQuery 训练面板。

年度滚动选参 resolved plan dry-run：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_annual_rolling_selection \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/annual_rolling_lgbm_regression_v0.yml \
  --manifest configs/strategy1/annual_rolling_lgbm_regression_v0.yml \
  --start-year 2021 \
  --end-year 2026 \
  --run-version vYYYYMMDD_NN \
  --include-yearly-backtest-commands \
  --dry-run
```

期望：

1. 每个年度 plan 的第一步必须是 `build_training_panel`，`sql_step=build_training_panel_risk_feature`。
2. `build_training_panel` 命令使用 `python -m quant_ashare.strategy1.sql_runner` 执行 catalog SQL step，并显式带 `--output-dataset-role=research`。
3. 后续顺序必须是 `cloudrun_prepare_matrix`、`cloudrun_train_candidate_fanout`、`cloudrun_select_register_predict`、`build_refit_training_panel`、`cloudrun_refit_register_predict`，若传 `--include-yearly-backtest-commands` 再追加 `cloudrun_backtest_report`。
4. `build_refit_training_panel` 必须使用独立 `__refit01` run_id 写 dedicated refit panel；`cloudrun_refit_register_predict` 使用 `quant_ashare.strategy1.refit_register_predict`，通过 `source_run_id` 读取 selection run 的 selected registry lineage，通过 `source_panel_run_id=__refit01` 读取 dedicated refit panel，并写入同一个独立 `__refit01` run。
5. 年度 fresh-run backtest 只作 diagnostic，且应引用 refit run；正式 `2021-2026` 结果仍必须来自单一 continuous ledger 或经过 resume-continuous QA 的 segment ledger。

PRD_20260611_06 true-five-year refit 代码准备入口（仅在历史 DWD/DWS 回填与 QA 通过后使用）：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_annual_rolling_selection \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/annual_rolling_lgbm_regression_v0.yml \
  --manifest configs/strategy1/annual_rolling_lgbm_regression_v0.yml \
  --start-year 2021 \
  --end-year 2024 \
  --run-version vYYYYMMDD_NN \
  --emit-refit-only \
  --true-five-year-refit \
  --final-refit-run-suffix __true5y01 \
  --dry-run
```

执行纪律：

1. `--true-five-year-refit` 会禁用当前 `2019-04-03` effective coverage floor，refit train start 回到每年名义五年窗口的实际首个开市日；必须配套非默认 `--final-refit-run-suffix`，避免覆盖现有 `__refit01` effective-window 结果。
2. `--emit-refit-only` 只输出 `build_refit_training_panel` 与 `cloudrun_refit_register_predict`。它假设 selection run / selected candidate 已存在，不重建 selection panel / matrix / 11 候选 fanout。
3. 运行前必须先完成 `2019-01-02..2019-04-02` 旗标修复、2010+ 历史 backfill、`sql/qa/13_true5y_historical_coverage_checks.sql` 和 overlap parity QA。stock parity 用 `scripts/qa/run_windowed_refresh_equivalence.py`，index/market parity 用 `scripts/qa/run_index_market_windowed_equivalence.py`，两者都应落 `summary-output-jsonl`；若 mismatch 非零，停止重跑 refit。

年度滚动 synthetic continuous merge 与 official continuous ledger：

```bash
python -m quant_ashare.strategy1.synthetic_continuous \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/annual_rolling_lgbm_regression_v0.yml \
  --manifest-json /tmp/strategy1_annual_refit_manifest_vYYYYMMDD_NN.json \
  --require-source-refit
```

manifest 示例：

```json
{
  "synthetic_run_id": "s1_annual_roll_synth_continuous_2021_2026_n20_w075_vYYYYMMDD_NN",
  "years": [
    {
      "backtest_year": 2021,
      "source_run_id": "s1_annual_roll_y2021_train2015_2019_valid2020_n20_w075_vYYYYMMDD_NN__refit01",
      "predict_start": "2021-01-04",
      "predict_end": "2021-12-31"
    }
  ]
}
```

期望：

1. merge 只写 `ashare_research`：生成 1 行 synthetic selected registry，`model_id` 统一为 `synth_<synthetic_run_id>`，prediction 行统一改写到该 synthetic model/run。
2. manifest 必须显式列出每年 `(source_run_id, predict_start, predict_end)`；official 模式必须传 `--require-source-refit`，确保 source registry 带 `refit=true`。
3. merge 不删除或修改任何年度 source run；若 synthetic run 已存在，必须显式 `--force-replace` 才会删除同 synthetic run 的 registry/prediction 后重写。
4. continuous ledger 通过现有 `quant_ashare.strategy1.backtest_report` 执行，`prediction_run_id` 指向 synthetic run，且必须显式传 `--skip-diagnosis --skip-tail-risk --skip-qa`；随后单独执行 `qa_continuous_backtest_outputs` 和 `qa_lot_aware_ledger_outputs`。
5. `qa_continuous_backtest_outputs` 必须验证 synthetic manifest hash、year→source model 溯源、source/target prediction 行数、valid 段排除、交易日历覆盖，以及 continuous summary / NAV / ledger state 不变式。不得把年度 fresh NAV 拼接成正式结论。

Cloud Run ledger resume 验收 / 手工恢复：

```bash
python -m quant_ashare.strategy1.backtest_report \
  --experiment-id <resume_experiment_id> \
  --experiment-json <base64-resolved-experiment-json> \
  --output-dataset-role research \
  --force-replace \
  --skip-gcs-upload \
  --skip-report \
  --skip-diagnosis \
  --skip-tail-risk \
  --skip-qa
```

resume experiment JSON 必须显式包含：

1. `initial_state_mode=resume_from_backtest`。
2. `parent_backtest_id=<full fresh continuous parent backtest id>`。
3. `state_as_of_date=<parent state date>`。
4. `predict_start=<state_as_of_date 后下一 SSE 开市日>`。
5. `rebalance_anchor_start=<parent 原始调仓锚点>`；biweekly 禁止按 segment start 重算奇偶。
6. `prediction_run_id`、`target_holdings`、`max_single_weight`、`rebalance_frequency`、成本和 feature/label 口径必须与 parent 兼容。

验收必须使用 full fresh continuous parent 的同窗口切片作为等价参照，不得用 cut date 后重新 fresh-start 的短段作为 full 输入；短段 fresh-start 会重置现金、持仓和 NAV，必然不等价。两套 QA 均通过后，resume segment 才可作为可用工具：

```bash
python -m quant_ashare.strategy1.sql_runner \
  --step qa_cloudrun_ledger_resume_outputs \
  --params-json-b64 <params> \
  --output-dataset-role research

python -m quant_ashare.strategy1.sql_runner \
  --step qa_ledger_resume_consistency \
  --params-json-b64 <params> \
  --output-dataset-role research
```

2026-06-11 PRD_08 验收证据：parent backtest `bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`，cut `2024-12-31`，next open `2025-01-02`，anchor `2021-01-04`；resume child execution `strategy1-backtest-report-job-82454` 成功，`qa_cloudrun_ledger_resume_outputs` job `eb99f350-feb4-4fdc-977d-d2e6b7c74201` 与 `qa_ledger_resume_consistency` job `8b2b1e17-42ad-44d2-8318-9f283c26eee2` 均通过；验收产物只写 `ashare_research`，同 run/backtest 在 ADS 为 0 行。

自上而下整手组合构造（PRD_20260611_10）手工 backtest：

```bash
python -m quant_ashare.strategy1.backtest_report \
  --experiment-id <experiment_id> \
  --experiment-json <base64-resolved-experiment-json> \
  --output-dataset-role research \
  --use-topdown-ledger \
  --position-floor-count 20 \
  --walk-depth 50 \
  --force-replace
```

执行纪律：

1. `--use-topdown-ledger` 会把 Python ledger 切到 `ledger_exec_v2_lot100_topdown`，并在 summary `metrics_json` 记录 `portfolio_construction_method=topdown_lot100_v2`、`position_floor_count`、`min_position_weight`、`walk_depth` 和 `cash_redistribution=topdown_whole_order_skip_v2`。
2. v2 ledger 直接读取 `stock_candidate_daily.rank_raw <= walk_depth` 的 full ranked candidates；`portfolio_target_daily` / `order_plan_daily` 仍由既有 SQL 生成兼容产物，不能作为 v2 构造输入解释。
3. 若要验证 P1 绑定，experiment 的 `tail_risk_profile_id` 必须显式为 `individual_risk_guard_v0` 或 `individual_and_market_risk_guard_v0`；不得修改全局默认 profile。
4. `backtest_report` 在未传 `--skip-qa` 时会继续跑 `qa_lot_aware_ledger_outputs`，并额外跑 `qa_topdown_construction_outputs`。后者要求零 `FILLED_SCALED_CASH` / `BUY_SKIPPED_BELOW_LOT_AFTER_SCALE`、P1 标记非空且不产生新增 BUY、full-rank 输入覆盖到 `walk_depth`，以及超深度持仓只能由 `SELL_SKIPPED_*` / `PENDING_SELL_CARRY` 解释。
5. v2 结果仍是 research evidence；是否取代 official 口径、是否进入 accepted baseline 或 promotion，都必须由 owner 单独决策。

年度滚动 pipeline scheduler dry-run：

```bash
python -m quant_ashare.strategy1.annual_pipeline_scheduler \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/annual_rolling_lgbm_regression_v0.yml \
  --manifest configs/strategy1/annual_rolling_lgbm_regression_v0.yml \
  --start-year 2021 \
  --end-year 2026 \
  --run-version vYYYYMMDD_NN \
  --global-candidate-task-limit 20 \
  --global-cpu-limit 40 \
  --global-memory-gib-limit 160 \
  --dry-run
```

期望：

1. 输出 2021-2026 全部 `panel` / `matrix` / `candidate` / `select` / `refit` / `diagnostic_backtest` / `continuous_ledger` DAG task。
2. `select:yYYYY` 依赖本年 11 个 `candidate:yYYYY:uNNN` 全部成功；`refit:yYYYY` 依赖本年 `select:yYYYY`；`continuous_ledger` 依赖六个 `refit:*`，不是 selection run；下一年 `panel` / `matrix` 不依赖上一年 `select`。
3. `scheduler_lock` 明确使用 GCS generation-guarded lease lock；`state_model` 明确 GCS state JSON 必须 generation-conditioned update，不允许 blind overwrite。
4. `stage_tokens` 显示 candidate `2 CPU / 8Gi`、prepare/refit `8 CPU / 32Gi`、select/backtest `4 CPU / 16Gi`（refit 复用 train job 但需要更大内存），且 `simulation.peak_resource_usage` 不超过全局 `20 / 40 CPU / 160Gi`。
5. `simulation.simulation_model=synchronous_waves` 表示 dry-run 每个 wave 原子完成后再排下一轮；该峰值是 DAG/resource admission 参考值，不是 live overlap 容量上限。Phase 2 真实执行必须按 Cloud Run execution 粒度统计 fanout，因为 retry / 尾部 batch 可能让同一年拆成多个 execution。

年度滚动 Phase 2 candidate-only live smoke：

前置：对应 `run-version` / 年度的 `prepare_matrix` 产物必须已存在，至少包含
`matrix_manifest.json` 与 `work_units.json`。本 smoke 只验证 candidate fanout live
调度，不会自动构建 panel 或 matrix；若 matrix 缺失，scheduler 会在本地失败并且不提交
Cloud Run execution。

```bash
python -m quant_ashare.strategy1.annual_pipeline_scheduler \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/annual_rolling_lgbm_regression_v0.yml \
  --manifest configs/strategy1/annual_rolling_lgbm_regression_v0.yml \
  --start-year 2021 \
  --end-year 2022 \
  --run-version vYYYYMMDD_NN \
  --global-candidate-task-limit 20 \
  --global-cpu-limit 40 \
  --global-memory-gib-limit 160 \
  --execute-live \
  --candidate-only-smoke \
  --smoke-year 2021 \
  --smoke-year 2022 \
  --smoke-candidates-per-year 3 \
  --candidate-smoke-batch-size 1
```

期望：

1. live 模式必须同时传 `--execute-live --candidate-only-smoke`；默认 dry-run / 非 live 仍不提交 Cloud Run。
2. 只提交 candidate fanout smoke executions，不执行 panel / matrix 构建、`select_register_predict`、final refit、synthetic merge 或 continuous ledger，不代表完整年度滚动已验收。
3. scheduler 使用 GCS generation-guarded lease 与 state JSON；state 恢复时按 Cloud Run execution id、describe 状态和 candidate artifact 双确认，已完成 artifact 会 skip，不重复提交。
4. `gcloud run jobs execute` 非零退出但能解析到 execution id 时，不直接判失败；必须以 execution describe 成功且 `task_status.json` / `candidate_metrics.json` 存在作为成功条件。
5. 本 smoke 不改 Cloud Run job spec、IAM 或镜像；如需完整 2021-2026 live pipeline，必须另按 Phase 3 获得 owner 批准。

sklearn native search dry-run：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_sklearn_native_search \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/sklearn_native_pvfq_n30_bw_h5_v0.yml \
  --manifest configs/strategy1/sklearn_native_pvfq_n30_bw_h5_v0.yml \
  --search-id sklearn_native_pvfq_n30_bw_h5_20260605_01 \
  --candidate-parallelism 0 \
  --top-k-backtest 5 \
  --dry-run
```

期望：

1. 输出 `candidate_count=36`。
2. `cloudrun_train_candidate_fanout` 命令包含 `--tasks=36`。
3. TopK 模板使用 `s1_<search_id>__<candidate_id>` / `bt_s1_<search_id>__<candidate_id>`，不出现重复前缀。
4. 子 Job 命令必须带 `--config configs/strategy1/sklearn_native_pvfq_n30_bw_h5_v0.yml`，避免 Cloud Run 内退回默认 5 候选。

Cloud Run Python LightGBM baseline search dry-run：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml \
  --manifest configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml \
  --build-training-panel \
  --dry-run
```

期望：

1. 输出 `candidate_count=40`。
2. `cloudrun_train_candidate_fanout` 命令包含 `--tasks=40`。
3. `expected_model_family=lightgbm_gbdt`、`expected_model_search_wave_no=2`。
4. `next_wave_manifest=configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml`，且 `auto_next_wave_on_needs_more_evidence=true`。若 Top5 全部没有 accepted 且存在 `needs_more_evidence`，orchestrator 会进入下一波 `lightgbm_regression`。

Wave 3 regression dry-run：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml \
  --manifest configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml \
  --build-training-panel \
  --dry-run
```

期望输出 `candidate_count=12`、`--tasks=12`、`expected_model_family=lightgbm_regression`、`expected_model_search_wave_no=3`。

风险特征 wave 4 binary dry-run：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_v0.yml \
  --manifest configs/strategy1/cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_v0.yml \
  --build-training-panel \
  --dry-run
```

风险特征 wave 4 regression dry-run：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/cloudrun_python_riskfeat_lgbm_regression_pvfq_n30_bw_h5_v0.yml \
  --manifest configs/strategy1/cloudrun_python_riskfeat_lgbm_regression_pvfq_n30_bw_h5_v0.yml \
  --build-training-panel \
  --dry-run
```

期望：

1. 两个 manifest 分别输出 `candidate_count=20`、`--tasks=20`。
2. `build_training_panel` 使用 catalog step `build_training_panel_risk_feature`。
3. `expected_model_search_wave_no=4`、`test_reuse_wave_no=4`。
4. Top5 完整回测后先跑 `19_qa_cloudrun_python_baseline_search_outputs.sql`，再跑 `21_qa_risk_feature_search_outputs.sql`。

多实验 dry-run：

```bash
python -m quant_ashare.strategy1.pipeline_control \
  --project data-aquarium \
  --region asia-east2 \
  --stage-id stage_a \
  --dry-run
```

未显式限流时，`resolved_max_parallel_experiments` 必须等于本次可执行实验数量。

## 3. 本地单入口 dry-run

```bash
python -m quant_ashare.strategy1.train_predict \
  --project data-aquarium \
  --region asia-east2 \
  --experiment-id oq010_a0_n5_w20 \
  --dry-run

python -m quant_ashare.strategy1.backtest_report \
  --project data-aquarium \
  --region asia-east2 \
  --experiment-id oq010_a0_n5_w20 \
  --dry-run

python -m quant_ashare.strategy1.prepare_matrix \
  --project data-aquarium \
  --region asia-east2 \
  --experiment-id oq010_a0_n5_w20 \
  --candidate-parallelism 0 \
  --dry-run
```

dry-run 只解析 manifest、参数、artifact 路径和执行计划，不写 ADS。

## 4. 构建镜像

```bash
gcloud builds submit \
  --project data-aquarium \
  --region asia-east2 \
  --config cloudbuild.strategy1-cloudrun.yaml
```

如需把当前 Git commit 写入镜像 tag，可显式传入：

```bash
gcloud builds submit \
  --project data-aquarium \
  --region asia-east2 \
  --config cloudbuild.strategy1-cloudrun.yaml \
  --substitutions=_TAG="$(git rev-parse --short HEAD)"
```

默认镜像：

```text
asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:latest
```

如 Artifact Registry repository 不存在，先创建：

```bash
gcloud artifacts repositories create quant-ashare \
  --project data-aquarium \
  --location asia-east2 \
  --repository-format docker
```

Cloud Run runtime service account 必须具备以下权限：

| 范围 | 权限 | 用途 |
|---|---|---|
| project 或源数据集 | `roles/bigquery.dataViewer` | 读取 DWD / DWS / ADS 输入表 |
| project | `roles/bigquery.jobUser` | 提交 BigQuery query / load job |
| `ashare_ads` dataset | `WRITER` / `roles/bigquery.dataEditor` | 删除并写入 prediction、candidate、portfolio、order、NAV、summary 等 ADS 输出 |
| `gs://ashare-artifacts` | `roles/storage.objectAdmin` | 上传模型、报告、诊断 artifact，并读写 orchestrator lock |
| Cloud Logging | `roles/logging.logWriter` | 写 Cloud Run job 日志 |

当前默认 Compute Engine service account 形如：

```text
<project-number>-compute@developer.gserviceaccount.com
```

## 5. 部署 Cloud Run Jobs

训练 / 预测 job：

```bash
gcloud run jobs deploy strategy1-train-predict-job \
  --project data-aquarium \
  --region asia-east2 \
  --image asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:latest \
  --command python \
  --args="-m,quant_ashare.strategy1.train_predict" \
  --memory 16Gi \
  --cpu 4 \
  --task-timeout 3600 \
  --max-retries 0
```

回测 / 报告 job：

```bash
gcloud run jobs deploy strategy1-backtest-report-job \
  --project data-aquarium \
  --region asia-east2 \
  --image asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:latest \
  --command python \
  --args="-m,quant_ashare.strategy1.backtest_report" \
  --memory 16Gi \
  --cpu 4 \
  --task-timeout 7200 \
  --max-retries 0
```

task fan-out 训练路径额外需要三个 job。`prepare_matrix` 和 reducer 读取 / 写入数据较多，沿用较高资源；candidate task 只训练单个模型，默认用轻量规格，并通过 Cloud Run Jobs task 数量实现并发。

```bash
gcloud run jobs deploy strategy1-prepare-matrix-job \
  --project data-aquarium \
  --region asia-east2 \
  --image asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:latest \
  --command python \
  --args="-m,quant_ashare.strategy1.prepare_matrix" \
  --memory 32Gi \
  --cpu 8 \
  --task-timeout 3600 \
  --max-retries 0

gcloud run jobs deploy strategy1-train-candidate-fanout-job \
  --project data-aquarium \
  --region asia-east2 \
  --image asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:latest \
  --command python \
  --args="-m,quant_ashare.strategy1.train_candidate_task" \
  --memory 8Gi \
  --cpu 2 \
  --parallelism 20 \
  --task-timeout 3600 \
  --max-retries 0
```

当前 OQ-010 Cloud Run Python baseline search 的 P0 口径固定为 40 个候选、20 并发、单 task `2 vCPU / 8Gi`。`strategy1-train-candidate-fanout-job` 的共享 Job spec 应保持 `parallelism=20`；40 个候选仍由一次 `--tasks=40` execution 启动，实际同时运行的 task 数由 Job spec 控制。若后续扩到 60 / 80 / 100 个候选，需要先更新对应 PRD、Cloud Run 区域配额和本部署命令。

若后续模型族发现单个 candidate task 的 `2 vCPU / 8Gi` 仍不足，先提高单 task 内存并按区域配额降低并发，而不是直接维持原并发：

```bash
gcloud run jobs update strategy1-train-candidate-fanout-job \
  --project data-aquarium \
  --region asia-east2 \
  --cpu 4 \
  --memory 16Gi \
  --parallelism 10
```

调整后，manifest 和执行参数中的 `candidate_parallelism` 必须同步改为新的并发值，并在 PR / 交接中记录 smoke 证据。

```bash
gcloud run jobs deploy strategy1-select-register-predict-job \
  --project data-aquarium \
  --region asia-east2 \
  --image asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:latest \
  --command python \
  --args="-m,quant_ashare.strategy1.select_register_predict" \
  --memory 16Gi \
  --cpu 4 \
  --task-timeout 3600 \
  --max-retries 0
```

## 6. 单实验 smoke

前置：先用现有 SQL 生成训练面板，例如修改 panel SQL 参数后执行：

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/strategy1/panel/build_training_panel_base.sql
```

然后执行：

```bash
python -m quant_ashare.strategy1.train_predict \
  --project data-aquarium \
  --region asia-east2 \
  --experiment-id oq010_a0_n5_w20 \
  --force-replace

python -m quant_ashare.strategy1.backtest_report \
  --project data-aquarium \
  --region asia-east2 \
  --experiment-id oq010_a0_n5_w20 \
  --force-replace
```

SQL ledger 对照入口已退役，`backtest_report` 不再支持旧 BQ ledger flag，也不再调用原 `08` SQL fallback。当前默认 Python ledger 路径为 `execution_backend='cloud_run_sklearn_ledger_v1_lot100'`、`ledger_executor='cloud_run_python'`；如需历史 FLOAT 股数审计，只能显式使用 Python `--use-float-ledger`。

`train_predict` 会把 sklearn selected model 与配置中的 BQML reference run 做模型质量对等检查；若 `model_quality_parity_status != 'passed'`，仍会写 selected registry、prediction、model artifact 和 parity 证据，但 `metrics_json.model_quality_status` 必须标记为 `model_quality_not_equivalent`，不得声明 sklearn backend 已等价替代 BQML baseline。
正式 baseline 验收继续要求 `sql/strategy1/qa/qa_cloudrun_runner_outputs.sql` 默认通过；只做 smoke / 证据留存时，可以显式把 `p_require_model_quality_parity_passed` 设为 `FALSE`，此时 QA 只要求 parity 证据完整。

## 7. Cloud Run orchestrator

首次使用前先确保状态表存在：

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/meta/02_strategy1_experiment_run_status.sql
```

默认全并发：

```bash
python -m quant_ashare.strategy1.pipeline_control \
  --project data-aquarium \
  --region asia-east2 \
  --manifest configs/strategy1/oq010_experiments_v0.json \
  --stage-id stage_a \
  --max-parallel-experiments 0
```

显式限流：

```bash
python -m quant_ashare.strategy1.pipeline_control \
  --project data-aquarium \
  --region asia-east2 \
  --stage-id stage_a \
  --max-parallel-experiments 4
```

规则：

1. `0` 或未传：resolved 并发数 = 本次可执行实验数。
2. `N > 0`：同一时刻最多 N 条实验链。
3. 默认训练路径每个子 job 使用状态表 step：`cloudrun_train_predict` / `cloudrun_backtest_report`。
4. task fan-out 训练路径使用状态表 step：`cloudrun_prepare_matrix` / `cloudrun_train_candidate_fanout`（或带 batch 后缀）/ `cloudrun_select_register_predict` / `cloudrun_backtest_report`。
5. `--train-mode task_fanout` 只替换训练 / 选型 / 预测部分，后续 `05-07`、ledger、报告和诊断仍由 `backtest_report` 负责。
6. `--candidate-parallelism 0` 表示一个训练实验内的全部 candidate work unit 同批并发；显式传 `N > 0` 时按 N 个 task 分批，前一批 terminal succeeded 后再启动下一批。
7. task fan-out P0 要求 reducer 默认所有 candidate artifact 都成功才进入选型；只有显式使用 reducer 的 `--allow-partial-candidates` 才允许缺候选继续。
8. 每个子 job 先获取 GCS lock：`gs://ashare-artifacts/locks/strategy1/cloudrun/<lock_key>.lock`，锁创建、heartbeat、release 均使用 object generation 条件操作。
9. 获取锁后启动 Cloud Run execution，立即把 execution id 写入 GCS lock 和状态表，然后由 orchestrator 轮询 execution terminal 状态。
10. stale lock 回收前会先检查原 Cloud Run execution；execution 仍在运行时不得抢占。当前执行失锁时会 cancel 对应 execution，避免两个 writer 写同一 run/backtest。
11. 默认遇到实验失败时停止提交新的排队实验；所有已完成 / 失败 / 跳过结果都会在最终 JSON 中列出。
12. 如需继续执行剩余排队实验，加 `--continue-on-error`；最终仍会按失败数量返回非零退出码。
13. 如需从状态表恢复，使用 `--resume` 跳过已 `succeeded` 的 step；或用 `--resume-from-step cloudrun_backtest_report` 从指定 step 重跑。
14. 如果 GCP quota 不足，失败实验必须以 Cloud Run execution 和日志追踪，不允许 runner 静默降到内部默认 2 或 1。

## 7.1 sklearn native search

执行入口：

```bash
python -m scripts.strategy1_cloudrun.orchestrate_sklearn_native_search \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/sklearn_native_pvfq_n30_bw_h5_v0.yml \
  --manifest configs/strategy1/sklearn_native_pvfq_n30_bw_h5_v0.yml \
  --search-id sklearn_native_pvfq_n30_bw_h5_20260605_01 \
  --candidate-parallelism 0 \
  --top-k-backtest 5 \
  --force-replace
```

执行语义：

1. `prepare_matrix` 只跑一次，source run 为 manifest 中的 search run。
2. `--candidate-parallelism 0` 表示 36 个 candidate task 同批并发；显式传 `N > 0` 才分批。
3. 候选训练完成后，orchestrator 只下载 `matrix_manifest.json`、`work_units.json` 和每个候选的 `candidate_metrics.json` / `task_status.json` / `model.joblib`，不下载完整 frozen matrix。
4. Top5 排名只使用 valid 指标；test 指标只在 Top5 完整回测后用于验收。
5. 每个 Top5 候选会生成独立 `candidate_run_id` / `candidate_backtest_id`，并复制一份同 run_id 的 `ads_ml_training_panel_daily` 别名，保证 `10` / `12` QA 和诊断可按独立 run_id join。
6. Top5 select/register/predict 与 backtest/report 仍使用 GCS lock 和状态表 step，避免同一 run/backtest 被两个 writer 同时写。
7. 单个 Top5 候选失败时，orchestrator 记录该候选失败并继续等待其他 Top5；最终 `18` QA 仍要求完整 Top5 产物，避免部分成功被误判为通过。
8. 搜索报告写入 `reports/strategy1_cloudrun/sklearn_native_search/search_id=<search_id>/`，uploaded 模式同步到 `gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/search_id=<search_id>/`。
9. 完成后运行 `18_qa_sklearn_native_search_outputs.sql`；该 QA 不要求 BQML parity passed，而是检查 native acceptance gate。

## 7.2 尾部风险诊断

Cloud Run `backtest_report.py` 默认在 `09`、报告、模型诊断、`10/12` QA 后执行尾部风险诊断：

```bash
python -m quant_ashare.strategy1.backtest_report \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml \
  --manifest configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml \
  --experiment-id cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_search_v0 \
  --search-id cloudrun_python_lgbm_reg_pvfq_n30_bw_h5_20260605_01 \
  --run-id <candidate_run_id> \
  --prediction-run-id <candidate_prediction_run_id> \
  --backtest-id <candidate_backtest_id>
```

执行语义：

1. `analyze_tail_risk.py` 只读 `ashare_ads` / `ashare_dwd` / `ashare_dim`，不写 ADS，不改变回测结果。
2. 单候选 artifact 写到 `reports/strategy1/ml_pv_clf_v0/run_id=<run_id>/backtest_id=<backtest_id>/tail_risk/`；uploaded 模式同步到对应 GCS 报告路径下的 `tail_risk/`。
3. 主要产物包括 `max_drawdown_windows.*`、`drawdown_position_contribution.csv`、`limit_down_exposure_daily.csv`、`selection_profile_by_signal_date.csv`、`risky_selected_names.csv`、`ads_readonly_guard.json` 和中文 `tail_risk.md`。
4. `ads_readonly_guard.json` 记录 summary / NAV hash 和 ADS 相关行数的 pre/post 对比；pre/post 不一致时脚本 fail-fast，不能降级跳过。
5. `20_qa_tail_risk_outputs.sql` 复算最大回撤、持仓覆盖、跌停/不可卖权重和 summary/NAV hash；由 `backtest_report.py` 自动注入脚本产出的 expected hash。
6. `backtest_report.py` 对非 guard 类尾部风险诊断失败采用 fail-soft：原报告、模型诊断和 `10` / `12` 已完成时不回滚，写入 `tail_risk/tail_risk_failure.json` 并跳过 `20`；后续可单独复跑尾部风险诊断。
7. 若只想跳过本诊断，可传 `--skip-tail-risk`；这只影响尾部风险 artifact，不影响原报告和模型诊断。

## 7.3 市场状态 risk-off

P2 market risk-off 先构建市场状态 DWS，再跑 portfolio-only A/B，不重新训练：

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/dws/08_dws_market_state_daily.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/11_market_state_checks.sql

python -m quant_ashare.strategy1.pipeline_control \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml \
  --manifest configs/strategy1/tailrisk_p2_market_riskoff_ab_20260606.yml \
  --force-replace
```

执行语义：

1. `dws_market_state_daily` 的 `trade_date` 是信号日；risk-off 在 `t` 日收盘后形成，只能影响 `t+1` 开盘执行。
2. `market_risk_off_v0` 只启用市场状态风控；`individual_and_market_risk_guard_v0` 同时启用 P1 个股风险和 P2 市场状态。
3. P2 v0 动作固定为 `skip_new_buys`：risk-off 次日允许卖出和 pending sell 继续处理，但所有 BUY 侧新增/加仓订单写 `BUY_SKIPPED_MARKET_RISK_OFF`，不成交、不候补。
4. `tail_risk/market_risk_off_dates.csv` 记录 risk-off 日期、触发原因和关键指标；`10` / `20` QA 会校验 risk-off 执行日没有真实 BUY 成交。

## 7.4 Tail-risk overlay continuous A/B

年度 final-refit + synthetic continuous 基线完成后，可用专用入口在同一条 synthetic prediction 流上跑 P1 / P2 / P1+P2 三组 portfolio-only continuous A/B：

```bash
python -m quant_ashare.strategy1.tail_risk_overlay_ab \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/cloudrun_runner_default.yml \
  --run-version vYYYYMMDD_NN \
  --dry-run
```

执行前先跑 research readiness QA 和 overlay preflight：

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/research/03_qa_research_schema_readiness.sql
```

```bash
python -m quant_ashare.strategy1.tail_risk_overlay_ab \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/cloudrun_runner_default.yml \
  --run-version vYYYYMMDD_NN \
  --preflight-only
```

真实执行三组 arm：

```bash
python -m quant_ashare.strategy1.tail_risk_overlay_ab \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/cloudrun_runner_default.yml \
  --run-version vYYYYMMDD_NN \
  --execute-cloud-run \
  --parallel-arms \
  --wait
```

执行语义：

1. 默认自动发现最新 refit-backed synthetic continuous selected registry row；也可显式传 `--prediction-run-id`、`--synthetic-model-id`、`--manifest-sha256` 和 `--baseline-backtest-id` 固定输入。
2. 三组 arm 分别使用 `individual_risk_guard_v0`、`market_risk_off_v0`、`individual_and_market_risk_guard_v0`，全部写 `ashare_research`，不 promotion、不改默认 `diagnostic_only`。
3. 每个 arm 通过正式 `strategy1-backtest-report-job` 运行 `quant_ashare.strategy1.backtest_report`，并显式传 `--skip-diagnosis --skip-tail-risk --skip-qa`；这里跳过的是诊断/默认 QA，不影响 profile-driven guard。
4. 三个 arm 写不同 run/backtest id，可用 `--parallel-arms` 并发提交；默认不传时按 A1 → A2 → A3 串行。
5. Runner 对每个 arm 跑 `qa_continuous_backtest_outputs` 与 `qa_lot_aware_ledger_outputs`，三臂完成后跑 `qa_tail_risk_overlay_ab_outputs` 汇总 guard 生效性和对比表。
6. `qa_tail_risk_overlay_ab_outputs` 的 preflight 会额外验证 full-window market-state coverage、top20 rebalance prediction 的 tail-risk 必需字段可用性，以及 `000852.SH` 在 2024-01-01 至 2024-02-07 crunch 段的逐开市日覆盖。
7. 最终对比表包含 CAGR / MaxDD / Calmar / contract Sharpe / IR / 回撤 peak-trough 日期 / 年化换手 / risk-off 期现金占比均值与峰值 / `BUY_SKIPPED` 逐年 JSON / crunch 段策略 vs `000852.SH` 超额。

## 8. QA

Cloud Run smoke 后执行：

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_runner_outputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_model_diagnosis_outputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_cloudrun_runner_outputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_lot_aware_ledger_outputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_cloudrun_orchestrator_status.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_sklearn_native_search_outputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_tail_risk_outputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_tail_risk_overlay_ab_outputs.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/qa/11_market_state_checks.sql
```

`16` 需要按实际 `p_run_id` / `p_prediction_run_id` / `p_backtest_id` 修改脚本顶部参数，或由后续调度器注入参数。
task fan-out 路径还需把 `16` 的 `p_require_task_fanout` 设为 `TRUE`。`16` 会同时断言 selected registry 已写入 matrix/work-unit 审计字段、所有 candidate task 成功、reducer 写入的 `candidate_task_bq_*` 审计计数为 0，并直接查询 `JOBS_BY_PROJECT` 兜底确认 candidate task 未读取 BigQuery 训练面板。
`17` 需要按实际 `p_experiment_id` / `p_run_id` / `p_backtest_id` 修改脚本顶部参数；task fan-out 路径需把 `p_require_train_step=FALSE`、`p_require_task_fanout=TRUE`。如果单独直接运行 train/backtest job、没有经过 orchestrator，则不运行 `17`。
`18` 只用于 sklearn native search。它需要按实际 `p_search_id` / `p_source_run_id` 修改脚本顶部参数，或由 `orchestrate_sklearn_native_search.py` 注入参数执行。
`20` 用于尾部风险诊断、P1 个股风险和 P2 market risk-off。它需要按实际 `p_run_id` / `p_prediction_run_id` / `p_backtest_id` / `p_predict_start` / `p_predict_end` 修改参数，或由 `backtest_report.py` 注入参数执行；`p_expected_summary_hash` / `p_expected_nav_hash` 应来自 `tail_risk/ads_readonly_guard.json`。
`11_market_state_checks.sql` 用于 `dws_market_state_daily` 表级 QA；P2 A/B 前必须先跑通。

## 9. 安全

1. 不提交 service account key、ADC 文件、OAuth token、OpenAI key 或 Tushare token。
2. Cloud Run 使用 service account 权限访问 BigQuery、GCS 和 Cloud Logging。
3. 本地 ADC 仅用于开发机 smoke，不写入仓库和日志。
