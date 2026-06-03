# 项目背景（Project Context）

## 项目目标

`quant-ashare` 是一套基于 **BigQuery** 的 **A 股日线量化数据仓库**，服务于
**A 股 · 日线 · 中低频 · 小资金 · 机器学习量化** 场景。

最终消费物：以 `(sec_code, trade_date)` 为主键的**特征宽表 + 标签**，供 ML 模型训练/回测，要求 PIT 正确、无未来泄露、横截面规整、可复现。

## 数据底座

- 平台：BigQuery，项目 `data-aquarium`。
- ODS：数据集 `ashare_ods`，57 张 Tushare 来源的 **Hive 分区外部表**（分区键 `partition_date` + `endpoint`，强制分区裁剪）。
- 目标分层：`ashare_dim`（维度）+ `ashare_dwd`（明细）→ `ashare_dws`（特征/标签）→ `ashare_ads`（策略消费）。

## 分层架构

```text
ashare_ods (已有, 外部表)
  -> ashare_dim   维度：主数据 + 缓变维 + SCD2 时间线
  -> ashare_dwd   明细：清洗/去重/标准化/复权/PIT 对齐
  -> ashare_dws   特征宽表 + 标签（ML 直接消费）
  -> ashare_ads   训练面板 / 模型预测 / 候选池 / 组合 / 回测 / 监控
```

## 核心原则（量化语境五条铁律）

1. **PIT**：财务特征可见时间用按表定义的 `ann_date_eff`（如 income/bs/cf 用 `COALESCE(f_ann_date, ann_date)`，`fina_indicator` 用 `ann_date`），严禁用报告期/分区当可见时间。
2. **复权**：收益率与技术指标用后复权（`_hfq`）；前复权（`_qfq`）含未来信息，不入训练特征。
3. **幸存者偏差**：universe 必须含已退市股的历史区间。
4. **可交易性**：停牌、一字板、上市未满 N 日、ST 需打标做样本掩码。
5. **去重**：行情表按分区天然唯一；财务表按 `(sec_code, 报告期)` + 公告日 + `update_flag` 去重取最新修正。

## 当前阶段

- DWD/DIM 建模方案文档已完成：`docs/数据仓库建模方案-DWD-DIM.md`。
- DWS/ADS 表设计文档已完成：`docs/数据仓库建模方案-DWS-ADS.md`。
- 策略设计文档已完成：`docs/A股中低频小资金机器学习策略方案.md`。
- 2026-05-31 owner 澄清 2019 年前数据范围：财务/事件按分区前移到 2017；行情最终写 2019+、构建时按最大滚动窗口读 2018 lookback buffer；维度/日历取最新快照或全量历史事件。主方案 §4.6 已按该口径修订。
- 命名规范、单位、分区/聚簇、表/字段注释规范均已敲定；2019 前数据范围见 `DECISION_LOG.md` 最新决策。
- 仓库已 `git init`（默认分支 `main`）。
- P0 建表 SQL 已落地到 `sql/`，并已按 `docs/reviews/P0-建表SQL-review.md` 修复首轮评审发现：显式 BigQuery location、复牌行过滤、`dim_stock` 稳健性、财务版本键去重兜底、`dwd_fin_indicator_latest` 与 QA 脚本。
- P0 DIM/DWD 已物化到 BigQuery 并通过 `sql/qa/01_p0_smoke_checks.sql` 的历史版本。已建 4 张 DIM + 5 张 DWD；OQ-004 已实现：`dim_index` 物化为指数 canonical 映射与端点可用性维表，`dwd_index_eod` 已从 `dim_index` 读取映射并重建，`sql/qa/03_oq004_index_checks.sql` 通过。沪深300来源 `399300.SZ` 输出 canonical `000300.SH`；STAR50/CSI1000 因 ODS 暂无对应 dailybasic endpoint 仍为空。
- P0 二轮评审发现已修复：`dwd_stock_eod_price` 拆分全天停牌与盘中临停语义；`dwd_fin_indicator_latest` 改为 `update_flag DESC` 优先取最新修正版；相关表已重建并通过 QA。
- 2026-05-31 ODS 已补采 `index_member_all` 与 `ci_index_member`，可落地申万/中信个股行业时点映射维表；OQ-001 已关闭。
- 策略 1 价格量价 DWS/ADS SQL 已落地并物化：`sql/dws/01-06_*.sql` 建成 universe、价格/估值特征、open-to-close 标签、特征宽表、样本表；`sql/ads/01_ads_strategy1_tables.sql` 建成训练、预测、候选、组合、订单、回测、监控表契约；`sql/qa/02_strategy1_dws_ads_checks.sql` 已通过。
- 策略 1 `ml_pv_clf_v0` runner 设计已完成：`docs/策略1-ml_pv_clf_v0-runner设计.md`，执行路径收敛为 BigQuery ML + SQL，训练/预测/组合/回测结果写入既有 ADS 契约表。
- 策略 1 runner 与回测闭环实现 PRD 已完成：`docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`。
- 策略 1 BigQuery ML + SQL runner 脚本已合并入 `main`：`sql/ml/strategy1/01-10`、`sql/ml/strategy1/README.md`、`scripts/strategy1/render_report.py`。**已于 PR #12 在 BigQuery 端到端实跑并通过全部 QA**（run_id `s1_bqml_20260601_01` / backtest `bt_s1_bqml_20260601_01`，`10_qa_runner_outputs.sql` 16 断言全过）。08 回测已重写为账户级有状态 ledger（DECISION-20260602-01）；不可交易腿记 `*_SKIPPED_UNTRADABLE` 意图行；报告为模式感知：local-only 写 `local_report_path` + `report_upload_status=skipped`、`report_uri=NULL`，uploaded 模式写真实 GCS `report_uri`。
- OQ-006 单位契约已实现并关闭（PR #16 已合并）：`ashare_meta.ods_field_unit_map` 已创建并填充 P0 + PR #13 首批映射；`dwd_index_eod.volume/amount` 已按 `vol*100` / `amount*1000` 修复换算并迁移为 `volume_share/amount_cny`；`sql/qa/05_oq006_unit_checks.sql` 已创建并纳入所有 DWD PR 必跑 QA；单位准入硬规则已写入 DWD-DIM §3.3-H 和 `KNOWN_CONSTRAINTS.md`。
- OQ-003 财务报表口径已实现并关闭（PR #13 已合并）：`dwd_fin_income` / `dwd_fin_balancesheet` / `dwd_fin_cashflow`（+ `_latest`）与 `dws_stock_feature_fin_daily` 已进入 `main` 并物化；`sql/qa/04_finance_caliber_checks.sql` 通过，且已按 OQ-006 补全财务字段单位映射并跑通 `sql/qa/05_oq006_unit_checks.sql`。
- OQ-010 交易成本子项已形成 PRD（`docs/prd/PRD_20260602_02_OQ010交易成本口径.md`）并已在 runner SQL 中实现：默认成本 profile 为佣金万一免五、卖出印花税 5 bps、买/卖滑点各 5 bps，已将 runner 从单一 `p_cost_bps=30` 升级为分项成本。
- 策略 1 中文报告与归因分析已实现并合并（PR #20）：`render_report.py` v2 生成中文 Markdown/HTML、交易/持仓/NAV/benchmark CSV 附件、图表、亏损证据包和 AI 诊断；评估主基准保持中证1000 `000852.SH`，展示对比基准包含沪深300 `000300.SH`；`09/10/README` 已同步报告字段与 QA。
- 策略 1 报告 GCS uploaded 模式已跑通：`docs/策略1报告GCS上传运行手册.md` 已新增；2026-06-02 已创建 `gs://ashare-artifacts`（`ASIA-EAST2`）、配置本机 ADC（quota project=`data-aquarium`），去掉 `--skip-gcs-upload` 重跑报告并验收真实 `report_uri=gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_bqml_20260601_01/backtest_id=bt_s1_bqml_20260601_01`，`sql/ml/strategy1/10_qa_runner_outputs.sql` 全部通过。
- 策略 1 模型质量诊断 PRD 已新增并实现：`docs/prd/PRD_20260602_04_策略1模型质量诊断.md`，范围限定为先诊断 signal / label / sample-universe / candidate / portfolio / cost / style，不直接改模型或调参。`sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql` 的 `split_tag` 歧义已修复，诊断 QA 已通过。
- 策略 1 valid/test live-available 预测池口径修正 PRD 已新增并实现：`docs/prd/PRD_20260602_05_策略1预测池口径修正.md`。valid/test 预测池已改为 t 日 live-available feature universe，标签有效性只用于事后评价。
- 策略 1 score orientation 校准 PRD 已新增并实现：`docs/prd/PRD_20260603_01_策略1分数方向校准.md`。当前 oriented run 已修正 raw 正类概率反向问题，`12` QA 全部通过。
- OQ-010 首轮质量迭代实验 PRD 已合并（PR #35）：`docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`，用于分阶段比较持股数/权重、调仓频率、标签 horizon 和财务特征；已明确 canonical baseline id、parent experiment 追溯关系，以及阶段 C 固定沿用阶段 B 晋级调仓频率以隔离 label horizon。owner 已确认阶段 A/B/C 不做 `4 * 3 * 3` 笛卡尔积，基础路径为 `4 + 3 + 3 = 10` 个实验，包含阶段 D 为 12 个实验；必要时补最多 `2 * 2` A/B、A/C、B/C pairwise 小型交互复核，最终 `2 * 2 * 2` 只作为条件触发的保底复核。阶段 A 的 `30/5%` 表示目标持股 30 只、单票权重上限 5%，目标单票等权为 3.33%，不是每只买 5%。
- OQ-010 首轮实验 runner 实现已由 PR #37 合并进入 `main`：新增实验 manifest 和对比报告脚本；`sql/ml/strategy1/01-06/09-12` 支持实验身份、调仓频率、目标持股/权重、`p_label_horizon`、`feature_set_id` 和 portfolio-only `p_prediction_run_id` 复用预测源路径；诊断脚本与 QA 已改为 horizon-aware；已通过 JSON/Python/`git diff --check` 和 BigQuery dry-run，尚未端到端实跑实验。
- OQ-010 策略 1 实验并发调度与隔离 PRD 已新增：`docs/prd/PRD_20260603_05_策略1实验并发调度与隔离.md`。该 PRD 定义同阶段 portfolio-only / retrain 实验安全并发所需的状态表、GCS 原子锁、lease/heartbeat、调度器、runner 参数化和写隔离、08 ledger 并发边界、单实验 QA 和并发串号 QA；实现前当前 runner 仍遵守不并发约束。
- OQ-005 GCP 数据流水线 PRD 已新增：`docs/prd/PRD_20260603_03_GCP数据流水线方案.md`。长期方案采用 Cloud Run Jobs 做 Tushare/Tinyshare→GCS Parquet 采集，Dataform / BigQuery Studio pipeline 做 ODS→DIM/DWD/DWS/ADS，Cloud Composer 做全流程编排、重试、补跑和告警；每日生产采集只覆盖当前实际消费的 14 张 ODS，当前未消费 endpoint 进入后续接入池；PRD 已按 owner 反馈收敛为陈述性目标实现方案，并已补入 PR #39 review 的财务 empty-return 口径和 Phase 1 触发入口。PR #42 分支已实现 Phase 0 采集 manifest、14 张 schema contract、meta 表 DDL 与采集脚本 stub，并整合 PR #44/#46 review 修复；后续仍需落地 Cloud Run Jobs、Dataform P0 转换和 Composer DAG。
- ODS 外部表 Parquet schema 修复 PRD 已新增：`docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md`。2026-06-03 只读复核确认 10 张 ODS 外部表存在 2019+ Parquet 物理类型 mismatch；修复方案为先按 schema contract 从 GCS 原 Parquet 做 schema-preserving rewrite，API 重拉只作为原文件损坏、缺失或 owner 明确要求的补救路径。当前策略相关表只有 `ods_tushare_stk_limit`，需优先修。
- **下一步**：执行 OQ-010 第一轮对照实验（可用 `run_oq010_experiments.py` 调度器加速同阶段实验）。也可补 `dws_market_state_daily`。P1 再做三大报表单季 `q_*` 派生和行业/资金/事件特征扩展。

## 不可妥协的约定

- 证券主键统一 `sec_code`（数据源中性，值标准格式 `600000.SH`）。
- 金额单位统一「元」、数量单位统一「股」。
- DWD 事实表统一带血缘字段 `source_system` + `ingested_at`。
- DWS/ADS 必须带版本与运行追踪字段（如 `feature_version`、`label_version`、`universe_version`、`model_id`、`strategy_id`、`run_id`）。
- 2019 年前数据不能混作“全历史写入”：财务/事件前移到 2017；行情写 2019+ 但读 lookback buffer；维度/日历取快照或全量历史事件。
- 记忆文件、文档、代码中均不得出现 BigQuery key / Tushare token 等凭据。
