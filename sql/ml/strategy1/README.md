> 文档维护：GPT-5（最近更新 2026-06-03）

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
```

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
- **回测交易与卖出口径（v1 ledger）**：08 只在每个调仓 period 的 `t+1 exec_date` 按当日开盘价交易；不可交易腿本期跳过、记为 `BUY_SKIPPED_UNTRADABLE` / `SELL_SKIPPED_UNTRADABLE` 意图行，持仓 carry 到下一个调仓执行日再尝试。
- **基准窗口校验**：08 执行前校验 `p_benchmark` 是 `dim_index` 中的可用收益基准，并且 `dwd_index_eod` 对 NAV 窗口每个开市日有且只有一条有效价格记录。
- **评估主基准**：`08` 和 `09` 的 `p_benchmark` 默认值为 `000852.SH`（中证 1000），ADS 主字段写入此基准。展示对比基准（沪深 300）和辅助基准（中证 500）由 `render_report.py` 从 `dwd_index_eod` 读取并固化到 `benchmark_nav.csv`。
- **报告渲染**：`render_report.py` 生成中文 Markdown + HTML + PNG + CSV 附件 + 证据包 + AI 诊断。默认上传 GCS 并写回 `metrics_json`；`--skip-gcs-upload` 仅写本地镜像。
- **AI 诊断**：`auto` 模式在无凭据或 LLM 失败时自动退化为 `evidence_only`，保证报告始终可生成。AI 只能引用证据包中的事实，不得编造外部原因。
- **OQ-010 参数**使用示例值，非业务定稿。

## 回测口径：v1 账户级有状态 ledger

`08_run_backtest.sql` 自 PR #12 为账户级有状态 ledger（BigQuery scripting `WHILE` 循环逐调仓 period）：
每个 `t+1 exec_date` 先按当前持仓估值得 NAV（停牌用 ffill 收盘）→ 目标仓位 = 目标权重 × 当前 NAV
（资金复利/回收）→ 卖出先于买入 → 买入受可用现金约束（超出按比例缩放）→ 对实际持仓 netting → 循环后按交易日展开每日持仓/NAV。
`10_qa_runner_outputs.sql` 的 `cash_cny >= -1`、`gross_exposure <= 1.005`、持仓 `(trade_date, sec_code)` 唯一、
NAV 覆盖全开市日由 ledger 构造保证。**v1 简化**：不可交易腿本期跳过 + carry（无 60 日 next-sellable 顺延）、未复权口径、持有期除权简化。
背景见 `.agent/memory/DECISION_LOG.md` DECISION-20260601-07（升级触发）与 DECISION-20260602-01（落地）。
