> 文档维护：GPT-5 Codex（最近更新 2026-06-06）

# Strategy 1 BigQuery ML Runner

基于 `ml_pv_clf_v0` 的 BigQuery ML + SQL 训练/预测/回测闭环。

## 前置条件

- `ashare_dws` 6 张 DWS 表已物化（`sql/dws/01-06`）
- `ashare_ads` 11 张 ADS 契约表已创建（`sql/ads/01`）
- `sql/qa/02_strategy1_dws_ads_checks.sql` 通过
- `ashare_dim.dim_index` 与 `ashare_dwd.dwd_index_eod` 已按 OQ-004 口径重建，`sql/qa/03_oq004_index_checks.sql` 通过
- `pip install google-cloud-bigquery google-cloud-storage matplotlib pandas requests db-dtypes`

## 执行顺序

所有 BigQuery job 显式指定 `--location=asia-east2`。脚本可按顺序执行，无需手动替换。

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/01_build_training_panel.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/02_train_bqml_logistic_candidates.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/03_select_model_and_register.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/04_predict_daily.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/05_build_candidates.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/06_build_portfolio_targets.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/07_build_order_plan.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/08_run_backtest.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/09_build_metrics_and_report_inputs.sql

# render_report 必须在 10 之前：它把报告状态回写 summary.metrics_json（local_report_path +
# report_upload_status、report_version、diagnosis_triggered、ai_analysis_status、artifact_manifest），
# 10 做模式感知断言。
# 默认（无 --skip-gcs-upload）会上传 GCS 并写 report_uri，需要 ashare-artifacts bucket + ADC；
# 本地验证用 --skip-gcs-upload（不写 report_uri，report_upload_status=skipped）。
python scripts/strategy1/render_report.py \
    --project data-aquarium \
    --backtest-id bt_s1_bqml_livepool_20260602_01 \
    --run-id s1_bqml_livepool_20260602_01 \
    --artifact-base-uri gs://ashare-artifacts/reports/strategy1 \
    --local-mirror-root reports/strategy1 \
    --skip-gcs-upload   # 去掉则上传 GCS 并写真实 report_uri（需 bucket + ADC）

bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/10_qa_runner_outputs.sql

# 11-12: 模型质量诊断（在 01-10 和 render_report 完成后执行）
# diagnose_model_quality.py 读取 ADS/DWS/DWD，生成 model_diagnosis/ artifact，
# 上传 GCS（默认），并回写 metrics_json.model_diagnosis_*。
# 本地验证用 --skip-gcs-upload。
python scripts/strategy1/diagnose_model_quality.py \
    --project data-aquarium \
    --run-id s1_bqml_livepool_20260602_01 \
    --backtest-id bt_s1_bqml_livepool_20260602_01 \
    --artifact-base-uri gs://ashare-artifacts/reports/strategy1 \
    --local-mirror-root reports/strategy1 \
    --skip-gcs-upload

bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql

# 13-14: 因子贡献度分析（在 01-12 和模型诊断成功后执行）
# attribute_factor_contribution.py 只读 selected model / prediction / backtest / feature panel，
# 不重新训练、不做消融实验；生成 factor_attribution/ artifact，并回写 summary.metrics_json。
python scripts/strategy1/attribute_factor_contribution.py \
    --project data-aquarium \
    --run-id s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01 \
    --backtest-id bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01 \
    --artifact-base-uri gs://ashare-artifacts/reports/strategy1 \
    --local-mirror-root reports/strategy1 \
    --skip-gcs-upload

bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/14_qa_factor_attribution_outputs.sql

# 15: Ledger resume consistency QA（仅 P2 验收时执行）
# 用于比较 full fresh-start backtest 与 resume segment backtest 在 2026 段的 NAV/持仓/成交一致性。
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/15_qa_ledger_resume_consistency.sql

# 16: Cloud Run sklearn runner QA（仅 Cloud Run 路径验收时执行）
# 先按实际 run/backtest 修改脚本顶部参数，或由后续调度器注入参数。
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql

# 17: Cloud Run orchestrator 状态/锁 QA（仅通过 orchestrator 启动时执行）
# 先按实际 experiment/run/backtest 修改脚本顶部参数。
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/17_qa_cloudrun_orchestrator_status.sql

# 18: sklearn native search QA（仅 PRD-20260605-03 的 36 候选 / Top5 路径执行）
# 由 orchestrate_sklearn_native_search.py 在 Top5 完整回测后注入参数执行。
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql

# 19: Cloud Run Python baseline search QA（仅 PRD-20260605-04 的 LightGBM / Top5 路径执行）
# 由 orchestrate_cloudrun_python_baseline_search.py 在 Top5 完整回测后注入参数执行。
bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql

# 20: 尾部风险诊断 QA（仅 PRD-20260606-01 的 P0 最大回撤诊断路径执行）
# analyze_tail_risk.py 严格只读 ADS/DWD/DIM，生成 tail_risk/ artifact；
# 20 QA 复算最大回撤、跌停/不可卖暴露，并用脚本产出的 pre/post hash 校验 ADS 未被改动。
python scripts/strategy1/analyze_tail_risk.py \
    --project data-aquarium \
    --run-id s1_cloudrun_python_lgbm_reg_example \
    --prediction-run-id s1_cloudrun_python_lgbm_reg_example \
    --backtest-id bt_s1_cloudrun_python_lgbm_reg_example \
    --search-id cloudrun_python_lgbm_reg_search_example \
    --feature-version strategy1_pv_v0_20260601 \
    --artifact-base-uri gs://ashare-artifacts/reports/strategy1 \
    --local-mirror-root reports/strategy1 \
    --skip-gcs-upload

bq query --use_legacy_sql=false --location=asia-east2 < sql/ml/strategy1/20_qa_tail_risk_outputs.sql
```

## Cloud Run sklearn runner（PRD-20260604-04）

Cloud Run 路径保留 BigQuery DWS/ADS、GCS artifact、报告、诊断和 QA 契约，只替代：

| 旧路径 | Cloud Run 路径 |
|---|---|
| `02_train_bqml_logistic_candidates.sql` | `python -m scripts.strategy1_cloudrun.train_predict` 训练 scikit-learn logistic candidates |
| `03_select_model_and_register.sql` | `train_predict` 内完成 valid 选型、score orientation 和 registry 写入 |
| `04_predict_daily.sql` | `train_predict` 内写 `ads_model_prediction_daily` |
| `08_run_backtest.sql` | `python -m scripts.strategy1_cloudrun.backtest_report` 默认调用 Python `ledger_exec_v1` fresh-start；`--use-bq-ledger` 可走原 SQL fallback 做等价对照 |

默认配置见 `configs/strategy1/cloudrun_runner_default.yml`，运行手册见 `docs/策略1CloudRun训练回测运行手册.md`。

并发规则：`orchestrate_experiments.py` 未传 `--max-parallel-experiments` 或传 `0` 时，resolved 并发数等于本次 manifest 可执行实验数；只有 owner 显式传 `N > 0` 时才限流。

模型质量对等门禁：`train_predict` 会记录 sklearn vs BQML parity 证据。`model_quality_parity_status='passed'` 时标记 `model_quality_status='model_quality_equivalent'`；未通过时仍写 selected registry / prediction / artifact，但必须标记 `model_quality_status='model_quality_not_equivalent'`，不能声明 sklearn backend 已等价替代 BQML baseline。`16_qa_cloudrun_runner_outputs.sql` 默认仍硬断言 parity passed；只做 smoke / 证据留存时，可显式设 `p_require_model_quality_parity_passed=FALSE`。`--use-bq-ledger` fallback 仅改变回测执行器，summary 会标记为 `execution_backend='cloud_run_sklearn_bq_sql_ledger_v1'`、`ledger_executor='bigquery_sql'`，默认 Python ledger 路径标记为 `cloud_run_sklearn_ledger_v1` / `cloud_run_python`。

Cloud Run orchestrator 状态与锁：启动前先执行 `sql/meta/02_strategy1_experiment_run_status.sql`。orchestrator 对每个实验链写 `cloudrun_train_predict` / `cloudrun_backtest_report` 两个状态 step，并用 `gs://ashare-artifacts/locks/strategy1/cloudrun/` 下的 generation-guarded GCS lock 做互斥；启动 Cloud Run execution 后立即记录 execution id 到 lock/status table，再轮询 execution terminal 状态。stale lock 回收前会检查原 execution 是否已结束，当前执行失锁时会 cancel execution。支持 `--resume` 跳过已成功 step，支持 `--resume-from-step cloudrun_backtest_report` 从指定 step 继续。通过 orchestrator 启动的 smoke 需额外跑 `17_qa_cloudrun_orchestrator_status.sql`。

Cloud Run task fan-out 训练路径（PRD-20260605-02）：`--train-mode task_fanout` 会把原 `cloudrun_train_predict` 拆成 `cloudrun_prepare_matrix` / `cloudrun_train_candidate_fanout` / `cloudrun_select_register_predict` 三段。`prepare_matrix` 只读一次 `ads_ml_training_panel_daily` 并写 GCS frozen matrix；candidate task 只读 frozen matrix，按 `CLOUD_RUN_TASK_INDEX + TASK_INDEX_OFFSET` 训练一个候选；reducer 默认要求全部 candidate artifact 成功后再选型、写 registry 和 prediction，并通过 `JOBS_BY_PROJECT` 写入 `candidate_task_bq_*` 审计计数。`--candidate-parallelism 0` 表示候选 work unit 默认全并发；`N > 0` 表示按 N 个 task 分批。验收时把 `16_qa_cloudrun_runner_outputs.sql` 的 `p_require_task_fanout` 设为 `TRUE`，由 `16` 同时检查 registry 审计字段和直接 `JOBS_BY_PROJECT` 兜底断言；并把 `17_qa_cloudrun_orchestrator_status.sql` 的 `p_require_train_step=FALSE`、`p_require_task_fanout=TRUE`。

sklearn native search（PRD-20260605-03）：当 Cloud Run sklearn parity 未通过时，不再把 `QA-CR-4` 作为 native baseline hard gate，而是用独立入口执行 36 个 sklearn 原生 LogisticRegression 候选，并按 valid-only Top5 完整回测：

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

该入口会复用 Cloud Run task fan-out：一次 `prepare_matrix` 后并发训练 manifest 中的 36 个候选，下载轻量 candidate artifact 做 valid-only 排名，再把 Top5 转成独立 `candidate_run_id` / `candidate_backtest_id` 跑 `select_register_predict` 和 `backtest_report`。Top5 候选会在 ADS training panel 中复制一份同 run_id 的训练面板别名，保证报告诊断和 `10/12` QA 仍按独立 run_id 校验。单个 Top5 候选失败时，其余候选继续执行，但最终 `18` QA 仍要求完整 Top5 产物。搜索报告写到 `reports/strategy1_cloudrun/sklearn_native_search/search_id=<search_id>/`，uploaded 模式同步到 `gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/search_id=<search_id>/`。最终验收使用 `18_qa_sklearn_native_search_outputs.sql`，accepted 候选还必须满足 valid/test `top_minus_bottom_fwd_ret_mean` 不能同时为负；valid/test 的 `top_minus_bottom` 均按 5 分桶计算。

Cloud Run Python baseline search（PRD-20260605-04）：sklearn native 首轮 Top5 rejected 后，下一轮用 LightGBM 在 Cloud Run task fan-out 上寻找新的 Python baseline。P0 manifest 固定为 `configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml`：40 个 `lightgbm_gbdt` 候选、默认 40 task 并发、数据截止 `2026-04-30`、固定 `pv_fin_quality + 30/5% + biweekly + 5d`，并使用 `configs/strategy1/model_acceptance_contract_v1.yml` 作为共享验收契约。

```bash
python -m scripts.strategy1_cloudrun.orchestrate_cloudrun_python_baseline_search \
  --project data-aquarium \
  --region asia-east2 \
  --config configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml \
  --manifest configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml \
  --build-training-panel \
  --force-replace
```

该入口会先按 PRD04 窗口构建训练面板，再由 `prepare_matrix` 生成 frozen matrix，并发训练候选、按 2021/2022/2023 purged walk-forward CV + 2024 valid confirmation 选 Top5。Top5 完整 prediction / portfolio / ledger / report / diagnosis 后，由 `19_qa_cloudrun_python_baseline_search_outputs.sql` 校验 Cloud Run Python backend、LightGBM 模型族、CV 证据、uploaded 报告/诊断、共享验收契约、2025 test reuse 和 2026 final_holdout watch。若 Top5 存在 `needs_more_evidence` 且无 accepted 候选，当前 wave 的 QA 先完成；随后才可按 manifest 触发 `configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml` 的 `lightgbm_regression` 下一波，且下一波失败只记录在 orchestrator 输出中，不覆盖当前 wave 结论。

尾部风险诊断（PRD-20260606-01）：`scripts/strategy1/analyze_tail_risk.py` 是 P0 只读诊断入口，不改变 candidate、target、order、trade、position、NAV 或 summary。Cloud Run `backtest_report.py` 默认在报告、模型诊断和 `12` QA 后执行该脚本，并把 experiment 的 `feature_version` 传给诊断脚本，避免多版本 `dws_stock_feature_daily_v0` join 扩行时行数扇出；若只需要复跑原报告链路，可显式传 `--skip-tail-risk`。诊断 artifact 写入单候选报告目录下的 `tail_risk/`，包含最大回撤事件、持仓贡献、行业/板块贡献、跌停和不可卖暴露、选股画像、风险股票名单、ADS 只读 guard 和中文 `tail_risk.md`。TopK 搜索比较报告会额外写 `tail_risk/search_tail_risk_summary.csv`，并在 comparison markdown 的 Top5 表中展示最大回撤窗口和跌停仓位峰值。P0 验收用 `sql/ml/strategy1/20_qa_tail_risk_outputs.sql`；该 QA 只复算 ADS/DWD 派生不变量，artifact 文件存在性和 ADS pre/post hash 由脚本本身强制校验。ADS pre/post hash 变化必须 hard fail；其他尾部风险诊断异常在 `backtest_report.py` 中 fail-soft，写入 `tail_risk/tail_risk_failure.json` 并跳过 `20`，不使已成功的报告和模型诊断链路失败。

## 参数说明

每个脚本顶部有 `DECLARE p_*` 参数块（`p_` 前缀避免与表列同名）。

| 参数 | 说明 |
|---|---|
| `p_run_id` | 本次运行唯一 ID；嵌入模型对象名以保证 run 隔离 |
| `p_prediction_run_id` | 模型/预测来源 run_id；默认等于 `p_run_id`。OQ-010 portfolio-only 实验（A1-A3、B0-B2）使用独立 `p_run_id` 输出候选/组合/回测，但把该参数设为基线或上一阶段晋级预测源 |
| `p_backtest_id` | 回测 ID |
| `p_experiment_id` | OQ-010 实验 ID；来自 `configs/strategy1/oq010_experiments_v0.json` |
| `p_experiment_group` | OQ-010 阶段/实验组，如 `portfolio_concentration`、`rebalance_frequency` |
| `p_baseline_experiment_id` | OQ-010 全局 baseline：`oq010_base_oriented_weekly_h5_n5_w20_pv` |
| `p_parent_experiment_id` / `p_parent_run_id` | 当前实验依赖的上一阶段晋级实验，用于追溯 |
| `p_train_start` | 训练起点（默认 2019-04-03，避开 60 日窗口不完整期） |
| `p_label_horizon` | 训练标签周期，支持 5 / 10 / 20；`01/03/11/12` 会按该值选择目标标签和收益列 |
| `p_rebalance_frequency` | 调仓频率，支持 `weekly` / `biweekly` / `monthly` |
| `p_rebalance_anchor_start` | `10` QA 使用；biweekly resume 校验调仓日时必须设为原实验起点，默认等于 `p_predict_start` |
| `p_target_holdings` | 持股数（OQ-010 待确认，示例值 5） |
| `p_max_single_weight` | 单票权重上限（OQ-010 待确认，示例值 0.20） |
| `p_feature_set_id` | 特征集合 ID；基础为 `strategy1_pv_v0_20260601`，财务扩展为 `strategy1_pv_fin_quality_v0_20260603` |
| `p_fin_feature_version` | 财务 DWS 来源版本，默认 `fin_default_v0_20260602`；仅 `p_feature_set_id` 为财务扩展时使用 |
| `p_cost_profile_id` | OQ-010 默认成本 profile：`cn_a_share_wanyi_no_min_slip5_v20260602`（佣金万一免五 + 卖出印花税 5 bps + 买卖滑点各 5 bps） |
| `p_commission_bps` | 佣金，默认 1.0（万一） |
| `p_min_commission_cny` | 最低佣金，默认 0.0（免五） |
| `p_stamp_tax_buy_bps` | 买入印花税，默认 0.0 |
| `p_stamp_tax_sell_bps` | 卖出印花税，默认 5.0 |
| `p_slippage_buy_bps` | 买入滑点，默认 5.0（成交价向上偏移） |
| `p_slippage_sell_bps` | 卖出滑点，默认 5.0（成交价向下偏移） |
| `p_cost_bps` | 兼容字段，旧一揽子成本 30 bps；已由分项成本取代，不再作为默认撮合成本来源 |
| `p_benchmark` | **评估主基准** canonical 代码，默认 `000852.SH`（中证 1000）；执行前必须存在于 `dim_index` 且完整覆盖回测 NAV 窗口 |
| `p_force_replace` | 是否覆盖同 run_id 结果（默认 FALSE） |
| `p_initial_state_mode` | `08/09/10` 使用；`fresh` 从现金+空仓开始，`resume_from_backtest` 从父回测恢复状态 |
| `p_parent_backtest_id` | resume 父回测 ID；仅 `p_initial_state_mode='resume_from_backtest'` 时必填 |
| `p_state_as_of_date` | resume 状态读取日；`p_predict_start` 必须等于该日后的下一开市日 |
| `p_resume_policy_id` | resume 状态兼容策略版本，当前为 `ledger_exec_v1_resume_v20260604` |

### render_report.py 参数

| 参数 | 说明 |
|---|---|
| `--project` | GCP project id |
| `--backtest-id` | 回测 ID |
| `--run-id` | 运行 ID |
| `--strategy-id` | 策略 ID（默认 `ml_pv_clf_v0`） |
| `--artifact-base-uri` | GCS 基础路径（`gs://bucket/path`） |
| `--local-mirror-root` | 本地镜像根目录（默认 `reports/strategy1`） |
| `--skip-gcs-upload` | 跳过 GCS 上传，仅写本地（不写 `report_uri`） |
| `--ai-analysis-mode` | AI 诊断模式：`auto`（默认）/ `off` / `evidence_only` / `llm` |
| `--ai-timeout-seconds` | LLM 调用超时秒数（默认 60） |
| `--ai-max-retries` | LLM 重试次数（默认 2） |
| `--ai-provider` | LLM 提供商（默认 `openai`） |

## 基准体系（PRD-20260602-03）

| 角色 | canonical `sec_code` | 名称 | 用途 |
|---|---|---|---|
| **评估主基准** | `000852.SH` | 中证 1000 | 计算超额收益、信息比率、alpha/beta 归因。ADS 主字段写入此基准。 |
| **展示对比基准** | `000300.SH` | 沪深 300 | owner 默认阅读口径，报告中展示对比。不写入 ADS 主 benchmark 字段。 |
| **辅助风格基准** | `000905.SH` | 中证 500 | 可选中盘风格对照，报告中展示。 |

策略 1 股票池偏中小盘，评估 alpha 时必须以中证 1000 为主基准，避免把小盘 beta 误读为选股 alpha。沪深 300 仅作为展示对比基准。

## 预测池口径（PRD-20260602-05）

| split | 入池规则 | 说明 |
|---|---|---|
| train | horizon-aware trainable mask | 含 label_entry_tradable / 当前 `p_label_horizon` 的 label_valid / target 非空，训练允许使用标签有效性 |
| valid | `predict_live_available_mask` | t 日已知 universe + feature + history + valuation，不含未来标签 |
| test | `predict_live_available_mask` | 同 valid |

`predict_live_available_mask` = `in_universe_default AND has_full_history_60d AND has_valuation_data`（NULL-safe，NULL 视为 FALSE）。

valid/test 预测、候选池、组合和回测从 live-available prediction pool 出发；事后评价（RankIC / bucket / AUC）在 label-available eval subset 上计算，不得反向影响预测池。

模型选型时，registry `metrics_json` 包含 `valid_eval_coverage` 和 `valid_eval_coverage_status`（ok >= 0.50 / warning >= 0.30 / critical < 0.30）。

## 报告产物（v2 中文报告）

报告输出到 `reports/strategy1/ml_pv_clf_v0/run_id=<run_id>/backtest_id=<backtest_id>/`：

| 文件 | 说明 |
|---|---|
| `report.md` | 中文 Markdown 报告（人读） |
| `report.html` | 中文 HTML 报告（人读） |
| `metrics.json` | 汇总指标 + artifact manifest + AI 状态 |
| `diagnosis_evidence.json` | AI 诊断证据包（schema: `strategy1_report_evidence_v1`） |
| `ai_analysis.json` | AI 诊断输出（模型、时间、evidence hash、状态） |
| `trades.csv` | 完整成交明细（含 score/rank/权重） |
| `positions.csv` | 每日持仓明细 |
| `nav.csv` | 每日净值、现金、暴露、成本 |
| `benchmark_nav.csv` | 策略与各基准净值对比（已固化，可复核） |
| `drawdown_events.csv` | 回撤事件列表 |
| `loss_attribution.csv` | 持仓亏损归因 |
| `assets/nav_vs_benchmark.png` | 策略净值 vs 基准对比图 |
| `assets/drawdown.png` | 回撤图 |
| `assets/excess_return.png` | 超额收益图 |
| `assets/turnover_cost.png` | 换手与成本图 |

### 报告正文结构

1. **首页摘要**：策略信息、基准、窗口、一句话结论
2. **绩效总览**：收益/风险指标、基准对比、成本分析、执行诊断
3. **图表**：净值对比、回撤、超额收益、换手成本
4. **买卖细节**：最近成交、最大成交、亏损贡献持仓、不可交易跳过样例
5. **风险与归因**：回撤事件、快速亏损窗口、持仓窗口贡献法归因
6. **AI 诊断**（触发时）：结论摘要、亏损窗口、主要亏损股票、可能原因、改进建议

### AI 诊断触发条件

满足以下任一条件时生成 AI 诊断章节：

- 策略累计收益 < 评估主基准累计收益
- 策略累计收益 < 展示对比基准累计收益
- 策略累计收益为负
- 最大回撤 <= -15%
- 5/10/20 日滚动收益 <= -8%
- 成本/亏损比 >= 20%

### AI 运行模式

| 模式 | 行为 |
|---|---|
| `off` | 不生成 AI 诊断，只生成证据包 |
| `evidence_only` | 不调用 LLM，用规则模板生成中文证据摘要 |
| `llm` | 必须调用 LLM；失败则报告生成失败 |
| `auto`（默认） | 触发条件满足且凭据可用时调用 LLM；无凭据或失败时退化为 `evidence_only` |

凭据通过环境变量提供：`OPENAI_API_KEY` 或 `LLM_API_KEY`，可选 `LLM_BASE_URL`、`LLM_MODEL`。

## 模型质量诊断产物（PRD-20260602-04）

诊断输出到 `reports/strategy1/ml_pv_clf_v0/run_id=<run_id>/backtest_id=<backtest_id>/model_diagnosis/`：

| 文件 | 说明 |
|---|---|
| `diagnosis.md` | 中文诊断报告（人读） |
| `diagnosis_summary.json` | 结构化诊断结论、证据、下一步建议 |
| `daily_rank_ic.csv` | 日截面 RankIC（valid+test） |
| `rank_ic_summary.json` | valid/test/all RankIC 汇总统计 |
| `score_bucket_lift.csv` | 5/10 分组收益、命中率、单调性 |
| `score_calibration.csv` | score bucket 校准检查 |
| `label_horizon_comparison.csv` | 1d/5d/10d/20d horizon RankIC 对照 |
| `sample_universe_funnel.csv` | 样本股票池漏斗（trainable → universe → selected） |
| `candidate_funnel.csv` | 候选池漏斗（prediction → selected → filled） |
| `feature_exposure_by_group.csv` | 各群体特征暴露对比 |
| `drawdown_window_diagnostics.csv` | 回撤窗口诊断 |
| `portfolio_concentration.csv` | 持仓集中度（HHI、top weight、position count） |
| `cost_turnover_diagnostics.csv` | 成本与换手诊断 |
| `market_regime_diagnostics.csv` | 中证 1000 市场阶段 |
| `style_exposure_diagnostics.csv` | 持仓风格暴露 |

诊断参数：

| 参数 | 说明 |
|---|---|
| `--project` | GCP project id |
| `--run-id` | 运行 ID |
| `--backtest-id` | 回测 ID |
| `--strategy-id` | 策略 ID（默认 `ml_pv_clf_v0`） |
| `--artifact-base-uri` | GCS 基础路径 |
| `--local-mirror-root` | 本地镜像根目录 |
| `--skip-gcs-upload` | 跳过 GCS 上传 |
| `--p-target-holdings` | 当前目标持股数（默认 5） |
| `--p-label-horizon` | 当前目标标签周期；默认从 registry `model_params_json.label_horizon` 读取，缺失时为 5 |

## 因子贡献度产物（PRD-20260604-03）

因子贡献度输出到 `reports/strategy1/ml_pv_clf_v0/run_id=<run_id>/backtest_id=<backtest_id>/factor_attribution/`：

| 文件 | 说明 |
|---|---|
| `factor_attribution.md` | 中文因子贡献度摘要（人读） |
| `factor_attribution_summary.json` | 结构化摘要、top 因子 / 因子组、路径和 manifest |
| `factor_model_weights.csv` | selected BQML 模型系数、训练期统计、orientation 后系数 |
| `factor_rank_ic_daily.csv` | valid/test 单因子日频 RankIC |
| `factor_rank_ic_summary.csv` | valid/test 单因子 RankIC 汇总 |
| `factor_bucket_lift_summary.csv` | 单因子 5 bucket top-minus-bottom 汇总 |
| `factor_score_contribution_summary.csv` | all/top/bottom/candidate/holding 的模型分数贡献汇总 |
| `portfolio_factor_exposure_daily.csv` | 实际持仓和候选池因子暴露日频 |
| `portfolio_factor_attribution_proxy.csv` | 持仓暴露 × 单因子日截面收益斜率的归因 proxy |
| `factor_group_summary.csv` | 因子组层面的模型贡献、RankIC、暴露和共线性摘要 |
| `factor_correlation_summary.csv` | 高相关因子对和因子组共线性摘要 |
| `artifact_manifest.json` | 文件 hash / 行数 / 本地路径 / GCS URI |

该步骤不做消融实验、不重新训练、不改变交易输出。`render_report.py` 在检测到 `metrics_json.factor_attribution_status='completed'` 后，会在主报告中展示因子贡献度摘要和 artifact 路径。

### attribute_factor_contribution.py 参数

| 参数 | 说明 |
|---|---|
| `--project` | GCP project id |
| `--run-id` | 当前 run_id；组合实验可与 prediction source 不同 |
| `--prediction-run-id` | 模型/预测来源 run_id；默认等于 `--run-id` |
| `--backtest-id` | 回测 ID |
| `--strategy-id` | 策略 ID（默认 `ml_pv_clf_v0`） |
| `--artifact-base-uri` | GCS 基础路径 |
| `--local-mirror-root` | 本地镜像根目录 |
| `--skip-gcs-upload` | 跳过 GCS 上传，仅写本地（不写 `factor_attribution_uri`） |
| `--p-label-horizon` | 标签周期；默认从 summary / registry 推断 |
| `--start-date` / `--end-date` | 分析窗口；默认用 backtest summary 的起止日期 |
| `--min-daily-factor-samples` | 计算日频单因子 RankIC / bucket lift 的最小日截面样本数，默认 100 |
| `--correlation-sample-rate` | 因子相关性抽样比例，默认 0.05 |
| `--max-correlation-rows` | 相关性计算最多拉取行数，默认 100000 |

## OQ-010 首轮实验执行

实验矩阵由 `configs/strategy1/oq010_experiments_v0.json` 管理。基础路径不是 `4 * 3 * 3` 笛卡尔积，而是阶段 A/B/C/D 逐步晋级：

1. 阶段 A：固定周频、5d 标签、基础量价特征，跑 `5/20%`、`10/10%`、`20/5%`、`30/5%` 四组持股/权重。
2. 阶段 B：沿用阶段 A 晋级持股/权重，跑 weekly / biweekly / monthly。
3. 阶段 C：沿用阶段 B 晋级调仓频率，跑 5d / 10d / 20d 标签周期。
4. 阶段 D：沿用阶段 C 晋级标签周期，对比基础量价特征与财务质量特征。

执行前先跑 `oq010_a0_n5_w20` 作为 5d 基线复现检查，并与 `s1_bqml_livepool_oriented_20260603_01` 对账训练面板行数、selected model 和核心回测指标，确认 train mask 与默认参数没有被本轮参数化改动意外改变。

每个实验执行时，需要把 SQL 顶部 `DECLARE p_*` 参数替换为 manifest 对应值，并保持 `run_id` / `backtest_id` 唯一：

- `requires_retrain=true`：执行 `01-12`，`p_prediction_run_id` 默认等于本实验 `p_run_id`。
- `requires_retrain=false`：跳过 `01-04`，从 `05` 开始执行到 `12`；`05/09/10/12` 和 `diagnose_model_quality.py --prediction-run-id` 必须使用 manifest 的 `prediction_run_id`，只重建候选、组合、订单、回测、报告和诊断。

`30/5%` 的目标权重由 `06` 计算为 `min(1/30, 0.05)=3.33%`，不会按 `30 * 5%` 建成 150% 仓位；若实际入选数量不足 `p_target_holdings`，剩余资金保留为现金，不按实际入选数重新满仓。

完成一批实验后生成对比 artifact：

```bash
python scripts/strategy1/compare_oq010_experiments.py \
    --project data-aquarium \
    --manifest configs/strategy1/oq010_experiments_v0.json \
    --comparison-id oq010_stage_a_20260603_01 \
    --output-root reports/strategy1/oq010_experiment_comparison \
    --include-planned
```

输出包括 `experiment_comparison.md`、`experiment_comparison.json`、`experiment_metrics.csv` 和 `experiment_manifest_resolved.json`。该脚本只汇总事实和排序，不替 owner 决定最终默认参数。

## Score orientation 校准（PRD-20260603-01）

`03` 在 valid 期对每个候选模型同时评估 raw score（label='1' 正类概率）和 reversed score（`1.0 - raw_score`）的 RankIC 与 bucket lift。按 PRD §6.2 的保守三条件规则决定方向：

```text
IF raw_valid_rank_ic_mean <= -0.03
   AND reverse_valid_rank_ic_mean >= 0.03
   AND reverse_valid_top_minus_bottom > raw_valid_top_minus_bottom
THEN score_orientation = 'reverse_probability'
ELSE score_orientation = 'identity'
```

弱信号（两者绝对值都 < 0.03）默认 `identity`，不自动反转。

选模型时使用 oriented score 口径的 `rank_ic_mean → topn_fwd_ret_mean → roc_auc`。selected model 的 registry `metrics_json` 持久记录：

- `score_source`: 始终为 `positive_class_probability`
- `score_orientation`: `identity` 或 `reverse_probability`
- `raw_valid_rank_ic_mean` / `oriented_valid_rank_ic_mean`
- `raw_valid_top_minus_bottom` / `reversed_valid_top_minus_bottom`
- `orientation_decision_reason`
- `orientation_decision_split`: 始终为 `valid`（test 不参与方向决策）

`04` 从 registry 读取 `score_orientation`。如果 registry 缺少 `score_orientation`，04 会 RAISE 失败（不会静默 fallback 到 identity）。ML.PREDICT 仍取 label='1' 概率作为 `raw_score`；写入 `ads_model_prediction_daily` 时：
- `score` = oriented score（identity 保留原始，reverse 用 `1.0 - raw_score`）
- `raw_score` = 原始 label='1' 概率（可追溯）
- `score_orientation` = 来自 registry
- `rank_raw` / `rank_pct` 按 oriented `score DESC` 计算

QA 断言（`10` QA-ORIENT-1..4）验证 registry 有 `score_orientation`、prediction 表的 `score_orientation` 与 registry 一致、`score` 与 `raw_score` 的关系和 orientation 一致。

## 关键设计

- **run 隔离**：模型对象名嵌入 `p_run_id`，registry 用 `JSON_VALUE(model_params_json, '$.run_id')` 过滤。
- **04 动态模型引用**：用 `EXECUTE IMMEDIATE FORMAT(...)` 自动引用 03 选出的 selected model URI，无需手动替换。
- **回测交易与卖出口径（ledger_exec_v1）**：`rebalance_date` 是信号日，08 推导下一开市日为 `execution_date` 并按开盘价交易；卖出先于买入，按实际持仓与目标持仓净差额 netting；买不进不候补，卖不出进入 `pending_sell` 并在后续每个开市日继续尝试卖出；现金不足的买单按比例缩放并记为 `FILLED_SCALED_CASH`。
- **基准窗口校验**：08 执行前校验 `p_benchmark` 是 `dim_index` 中的可用收益基准，并且 `dwd_index_eod` 对 NAV 窗口每个开市日有且只有一条有效价格记录。
- **评估主基准**：`08` 和 `09` 的 `p_benchmark` 默认值为 `000852.SH`（中证 1000），ADS 主字段写入此基准。展示对比基准（沪深 300）和辅助基准（中证 500）由 `render_report.py` 从 `dwd_index_eod` 读取并固化到 `benchmark_nav.csv`。
- **报告渲染**：`render_report.py` 生成中文 Markdown + HTML + PNG + CSV 附件 + 证据包 + AI 诊断。默认上传 GCS 并写回 `metrics_json`；`--skip-gcs-upload` 仅写本地镜像。
- **AI 诊断**：`auto` 模式在无凭据或 LLM 失败时自动退化为 `evidence_only`，保证报告始终可生成。AI 只能引用证据包中的事实，不得编造外部原因。
- **OQ-010 参数**使用示例值，非业务定稿。

## 回测口径：ledger_exec_v1 日级账户 ledger

`08_run_backtest.sql` 实现 `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md` 的 P0 交易执行语义：
`rebalance_date` 继续表示 `signal_date`，成交日为下一开市日 `execution_date`。脚本按开市日逐日循环：
执行日前最近可用收盘价估算 NAV → 若当天是 execution_date 则更新目标组合 → 按实际持仓和目标持仓净差额 netting → 卖出先于买入 → 买入受可用现金约束（超出按比例缩放）→ 卖不出进入 pending sell 并在后续每个开市日继续尝试 → 每日收盘 mark-to-market 写 NAV。
`10_qa_runner_outputs.sql` 的 `cash_cny >= -1`、`gross_exposure <= 1.005`、持仓 `(trade_date, sec_code)` 唯一、
NAV 覆盖全开市日由 ledger 构造保证；同时校验新状态枚举、pending sell 次日重试、同股同日不同时成交买卖、非成交状态不影响现金。

### Ledger state resume

`08_run_backtest.sql` 支持两种初始状态：

| `p_initial_state_mode` | 行为 |
|---|---|
| `fresh` | 从 `p_initial_capital` 和空仓开始 |
| `resume_from_backtest` | 从 `p_parent_backtest_id + p_state_as_of_date` 恢复现金、实际持仓、最新 active target 和 pending sell |

resume 模式 fail-fast：

- `p_parent_backtest_id`、`p_state_as_of_date` 必填。
- `p_resume_policy_id` 必须为 `ledger_exec_v1_resume_v20260604`。
- biweekly resume 跑 `10_qa_runner_outputs.sql` 时必须显式设置 `p_rebalance_anchor_start` 为原实验起点，避免按 resume 窗口起点重算双周奇偶。
- 父回测 summary 必须存在且 `metrics_json.ledger_version='ledger_exec_v1'`。
- 父回测在 `p_state_as_of_date` 必须有唯一 NAV 状态，且 cash + position market value 必须能对上 net value。
- `p_predict_start` 必须等于 `p_state_as_of_date` 后的下一开市日，禁止有缺口或重叠。
- 父回测持仓必须唯一、非负、可在 resume 首日估值；状态异常时不允许静默 fallback 到 fresh。

pending sell 恢复不新增 ADS 状态表，而是从父回测 `ads_backtest_trade_daily` 的最新 SELL 状态推导：最新状态为
`SELL_SKIPPED_UNTRADABLE` 或 `PENDING_SELL_CARRY` 且状态日仍有持仓时，恢复为 pending sell；后续仍按日级 ledger 继续卖出或被 netting 取消。

resume 首日 `daily_return` 使用父回测 `p_state_as_of_date` 的 NAV 作为 LAG 锚点，保证拼接后的日收益序列不断点。
P2 验收时执行 `15_qa_ledger_resume_consistency.sql`，比较 full fresh-start backtest 与 resume segment backtest 在比较窗口内的 NAV、现金、`daily_return`、持仓和成交事实是否一致。

`ads_backtest_trade_daily.fill_status` 当前可能值：

| 状态 | 含义 |
|---|---|
| `FILLED` | 全部成交 |
| `FILLED_SCALED_CASH` | 因现金不足按比例缩放后成交 |
| `BUY_SKIPPED_UNTRADABLE` | 买入不可交易，未成交且不候补 |
| `SELL_SKIPPED_UNTRADABLE` | rebalance execution_date 卖出不可交易，进入/维持 pending sell |
| `PENDING_SELL_CARRY` | 非 rebalance 日继续尝试 pending sell 但仍不可卖 |
| `CANCELLED_BY_NETTING` | pending sell 因目标提高/重新入选被 netting 取消 |
| `SKIPPED_CASH_INSUFFICIENT` | 现金缩放后仍无法成交 |
| `SKIPPED_MIN_NOTIONAL` | 低于最小成交金额，当前 P0 默认不触发 |
| `NOOP_ALREADY_TARGET` | pending 持仓已达到目标，无需继续卖 |

P0 仍保持未复权现金成交口径、FLOAT shares、未显式建模 A 股 T+1 锁仓和持有期除权影响。
背景见 `.agent/memory/DECISION_LOG.md` DECISION-20260601-07（升级触发）与 `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`。
