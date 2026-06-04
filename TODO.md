# TODO

本文件只保留"下一步可执行事项"。整体状态和历史完成记录见 `.agent/memory/IMPLEMENTATION_STATUS.md` / `.agent/memory/AGENT_HANDOFF.md`；待 owner 决策的问题以 `.agent/memory/OPEN_QUESTIONS.md` 为唯一来源。

维护规则见 `AGENTS.md` 的「TODO 维护协议」。

## P0 — 当前优先

- [ ] 补 P0 通用 DWS 扩展表：`dws_market_state_daily`、后续策略共用市场状态特征（`dws_stock_feature_fin_daily` 已落地）
- [~] 修复 ODS 外部表 Parquet schema mismatch：PR #43 已实现 schema contract YAML × 10 endpoint、修复/验证脚本、QA SQL 和执行 README，并按 review 补齐 QA 参数格式、INT->FLOAT64 fail-closed、null count 阻断、BQ staging 行数/列可读验证和 staging 清理；P0 `stk_limit` 待在 BigQuery 实际执行修复并验证，再分批修其余 9 张 P1/P2/P3 表；默认从 GCS 原 Parquet 按 schema contract 重写，不从 API 重拉覆盖历史 raw
- [ ] 策略 1 runner v0 模型质量与参数迭代（OQ-010）：基础 A/B/C 与 3*2*2*2 全因子 24 组合已跑完并全部通过 `12_qa_model_diagnosis_outputs`；当前最优组合为 `pv_fin_quality + 30/5% + biweekly + 5d`，并已完成正式基线重训 run `s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01` / backtest `bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01`（2024-01-02 至 2025-12-31，total_return 41.10%、excess_return 12.09% vs `000852.SH`、Sharpe 1.043、max_drawdown -14.48%，报告和诊断均已上传 GCS）。因子贡献度 P0 已实现并通过 `14_qa_factor_attribution_outputs.sql`；Ledger v1 P0 已进 main；P2 resume 已实现分支并通过短区间 smoke/`10` QA。下一步需 owner 确认是否采纳最优组合为默认参数，并补 P1 2026 YTD fixed-model 扩展验证与完整 resume consistency 验收
- [ ] Ledger v1 P1：不重新训练，复用正式 baseline 模型/参数/score orientation，从 `2024-01-02` fresh-start 重跑至 `2026-04-30`，产出 fixed-model extended baseline，并在报告中单独拆出 `2026-01-02` 至 `2026-04-30` 表现
- [~] Ledger v1 P2：`codex/ledger-state-resume` 已实现 ledger state resume，支持从 `parent_backtest_id + state_as_of_date` 恢复现金、持仓、active target 和 pending sell，并新增 resume QA 与一致性 QA；PR #54 review follow-up 已修复 biweekly resume QA 必填原实验 anchor、resume 首日 `daily_return` 父 NAV 锚点和 `15` 一致性 QA 的 daily_return 覆盖；已用 `bt_ledger_resume_smoke_20260604_01` 跑通短区间 `08`/`09`/本地报告/`10` QA。待 PR review/merge 后，结合 P1 extended baseline 做 `2024-2026.04` fresh 全段 vs `2024-2025 + resume 2026` 一致性验收
- [ ] 按 `docs/prd/PRD_20260604_02_策略1月度滚动重训.md` 实现月度滚动重训 prediction stream；该项必须在 Ledger v1 P0/P1/P2 完成后再做，避免模型生命周期变化和交易执行语义变化混在一起
- [~] 按 `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md` 实现策略 1 Cloud Run 训练回测执行器：首版 Cloud Run runner 与 orchestrator 状态/锁增强已由 PR #56/#57 合并；真实 Cloud Run smoke 已在 `data-aquarium` 跑通，`run_id=s1_cloudrun_sklearn_smoke_20260604_02` / `backtest_id=bt_s1_cloudrun_sklearn_smoke_20260604_02`，train/predict execution `strategy1-train-predict-job-s5725`、backtest/report execution `strategy1-backtest-report-job-6fzvr` 均成功，报告 uploaded 到 GCS，`16_qa_cloudrun_runner_outputs.sql`（smoke 模式 `p_require_model_quality_parity_passed=FALSE`）和 `17_qa_cloudrun_orchestrator_status.sql` 通过。当前 sklearn smoke 可运行但模型质量未等价 BQML baseline（`model_quality_status=model_quality_not_equivalent`，valid RankIC gap 超阈值）；2026-06-05 新增 `docs/prd/PRD_20260605_02_策略1CloudRun轻量Task并发.md`，定义 `prepare_matrix` 冻结矩阵 + Cloud Run Jobs task fan-out + reducer 架构，让 35/100 个候选或实验 work unit 默认全并发且避免每个 task 重扫 BigQuery。下一步需做 sklearn backend 参数/模型质量迭代、实现轻量 task fan-out，并补 Python ledger vs SQL ledger 的正式等价验收，正式替代 BQML 前仍需 parity passed 或 owner 接受新 baseline

## P1 — 数据 / 特征扩展

- [ ] 三大报表单季派生（`income`/`cashflow` 累计转单季 `q_*`）作为 P1 财务表内容（OQ-003 PRD §4 推荐延后）
- [ ] `dim_stock_sw_industry_hist`（source `index_member_all`，按 `in_date/out_date` 建申万行业时点归属，并 QA 区间重叠 / 缺口）
- [ ] `dim_stock_ci_industry_hist`（source `ci_index_member`，中信行业时点归属，对照体系）
- [ ] `dwd_sw_industry_eod` + 行业中性化
- [ ] P1+ 资金面 / 事件 / 行业族 DWD：moneyflow、margin、hk_hold / ccass、龙虎榜、股东增减持、质押回购、业绩预告 / 快报、分红、分析师报告等；新增 DWD 前先按 OQ-006 补单位映射
- [ ] `dim_index_weight`、`dim_sw_industry`、`dim_ipo`
- [ ] 补 lookback-capable 价格构建输入或调整 DWD/DWS 构建方式，使 2019-01 起 60 日窗口可直接读取 2018 buffer；当前策略 1 DWS 用 `has_full_history_60d=FALSE` 标记并默认剔除不完整窗口样本（OQ-011）

## 工程 / 调度

- [~] OQ-005 GCP 数据流水线落地：`docs/prd/PRD_20260603_03_GCP数据流水线方案.md` 与 `docs/prd/PRD_20260605_01_OQ005剩余调度链路.md` 已定义 Cloud Run Jobs 采集、Dataform / BigQuery Studio pipeline 做 ODS→ADS、Cloud Composer 编排；Phase 0 已实现采集 manifest、14 张 schema contract、meta 表 DDL 与采集脚本 stub；Phase 1/1.5/1.6 已实现 endpoint worker、GCS staging/publish、小范围写入 smoke、ODS 可读性 QA、Composer 3 环境和每日轻量 readiness DAG；Phase 1.7 已新增 `ashare-ingest-current-scope` 单 execution 生产入口、Direct VPC egress + Cloud NAT 固定出口，修复 Composer scheduler queued 问题为 default Celery queue 路径，并完成 `2026-05-20` 至 `2026-06-03` SSE 开市日生产 GCS 回填和 `2026-06-04` Composer 生产 DAG 首跑。Phase 2.0 BigQuery SQL 兼容路径已在 PR #61 分支 `codex/oq005-scheduler-phase2` 实现并跟进 review comment：DAG 新增 `pipeline_run` / `pipeline_task_status` 状态回写、`warehouse_mode` 分支、`skip_ingestion` smoke、`qa_only` 只读 QA、ADS 契约手工初始化隔离和 meta 脚本编号整理；已移除 parse-time `Variable.get()`，支持单次 run 用 `pipeline_dry_run` / `dry_run` 覆盖采集 dry/write 分支，并整理 QA TaskGroup。下一步部署到 Composer 后做 `skip_ingestion=true` smoke、`warehouse_mode=qa_only` 验收和 `warehouse_mode=full_rebuild_compat` 维护链路 smoke；之后进入 Phase 2.1 Dataform definitions、Phase 2.2 增量影响窗口、策略 runner/report 可选分支和告警/补跑/状态闭环
- [ ] 将 `lookback_start_date` 从固定默认值升级为按最大滚动窗口计算 / 调度配置
- [ ] 写"从 ODS 继承字段描述"脚本（`bq show` -> 映射 -> `bq update`）
- [ ] 增量调度（dbt 或 Airflow + SQL）与数据质量断言

## 近期完成

- [x] 新增策略 1 Cloud Run 轻量 Task 并发训练 PRD：`docs/prd/PRD_20260605_02_策略1CloudRun轻量Task并发.md`，定义 `prepare_matrix` 一次性导出 frozen matrix、`strategy1-train-candidate-fanout-job` 按 Cloud Run task 执行候选 / 实验 work units、`select_register_predict` 汇总选型写 ADS，以及 owner 不限流时单批全并发、显式限流时分批执行的并发语义；本次只写文档，未实现代码、未部署 Cloud Run Job、未执行 BigQuery
- [x] 策略 1 Cloud Run 真实 smoke 已完成：已创建/使用 Artifact Registry `quant-ashare` 和 Cloud Run Jobs `strategy1-train-predict-job` / `strategy1-backtest-report-job`，镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner@sha256:6564434f9f216aec6c86cae3923bc44450c3ca26ead14a248b05ca77087d8ead`，job 配置 16Gi/4CPU/`--max-retries=0`；runtime service account 已具备 `ashare_ads` 写权限；smoke 输出 `total_return=46.29%`、`Sharpe=1.111`、`max_drawdown=-13.94%`、`excess_return=17.28%` vs `000852.SH`，但 sklearn parity 未通过，只能作为 Cloud Run 可运行证据，不能声明替代 BQML
- [x] 新增 OQ-005 剩余 ODS→ADS 生产调度链路 PRD：`docs/prd/PRD_20260605_01_OQ005剩余调度链路.md`，聚焦当前生产采集入口之后的 ODS gate、ODS→DIM/DWD/DWS/ADS 转换、ADS 契约隔离、metadata、QA、pipeline 状态、告警、补跑、Dataform/BigQuery SQL 双路径和 OQ-005 关闭标准；PR #59 review follow-up 已澄清 Phase 2.0/2.1 CTAS 全量兼容路径与 Phase 2.2 增量 daily_current 的边界、ADS 脚本现状、meta 编号整理要求和字段说明生产来源；本次只写文档，未实现代码、未部署任务、未执行 BigQuery
- [x] PR #58 review follow-up 已处理：live ingestion 现在写入 `ashare_meta.ingestion_run` 与 `ingestion_partition_status`，dry-run/API 只读 smoke 不写 meta；已把 raw GCS canonical 路径固定为 `api=<api>/endpoint=<partition_endpoint>/partition_date=...` 并用 BigQuery `INFORMATION_SCHEMA.TABLE_OPTIONS` 复核当前 14 张 ODS 与 10 张 schema repair 表 source URI；GCS overwrite 无 write-once backup 明确为采集重跑口径，历史可回滚回填留后续独立开关/流程
- [x] OQ-005 Phase 1.7 生产采集首跑已完成：Cloud Run Jobs 已切到 Direct VPC egress + Cloud NAT + 静态出口 IP，生产入口改为 `ashare-ingest-current-scope` 单 execution 顺序执行当前 14 个 ODS endpoint，Composer DAG 使用 default Celery queue 解决 scheduler 派发卡在 queued 的问题；纯 scheduler smoke `manual_oq005_scheduler_smoke_default_queue_20260604_01` 成功；`2026-05-20` 至 `2026-06-03` SSE 开市日生产 GCS 回填全部成功并逐日通过 `sql/qa/09_ods_daily_partition_readiness.sql`；`manual_oq005_daily_prod_20260604_01` 已按生产路径写入 `2026-06-04` 并成功完成 readiness，Airflow 变量当前为 `ashare_pipeline_dry_run=false`、`ashare_enable_full_refresh=false`
- [x] 新增策略 1 Cloud Run 训练回测执行器 PRD：`docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`，定义 Cloud Run Jobs + sklearn logistic + Python ledger_exec_v1 + GCS model/report artifact + 默认全实验并发 / owner 显式限流的目标执行路径；已明确 scikit-learn 只替代 BQML 模型训练/预测，不替代 BigQuery DWS/ADS、GCS artifact、报告诊断和 QA
- [x] Ledger v1 P0 交易执行语义已进入 main（commit `602baea`）：`08_run_backtest.sql` 已升级为 `ledger_exec_v1` 日级账户 ledger，固化 t-1 信号 / t 开盘执行、pending sell 每日继续卖、实际持仓 netting、现金缩放、订单状态和每日 mark-to-market NAV；短区间 BigQuery smoke（`bt_ledger_v1_p0_smoke_20260604_01`）和 `10` QA 已通过
- [x] 实现策略 1 因子贡献度分析 P0：新增 `scripts/strategy1/attribute_factor_contribution.py`、`sql/ml/strategy1/14_qa_factor_attribution_outputs.sql`，主报告接入因子贡献度摘要，并更新 runner README；正式 baseline local-only 生成 `factor_attribution/` artifact，覆盖 selected model 55 个非截距特征、13 个因子组，`14_qa_factor_attribution_outputs.sql` 全部通过
- [x] 工作记忆轻清理：`AGENT_HANDOFF.md` 缩到当前摘要 + 最近 3 条交接，19 条旧交接已归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- [x] 新增策略 1 因子贡献度分析 PRD：`docs/prd/PRD_20260604_03_策略1因子贡献度分析.md`，定义不做消融实验的模型系数、单因子 RankIC/bucket lift、score contribution、组合因子暴露、归因 proxy 和因子相关性/共线性摘要；PR #51 review 后已补充单因子系数排名受共线性影响、组级解读优先、proxy 不可加总等限制说明；实施顺序建议放在 Ledger v1 P0 前，但不代表优先级高于 Ledger / 月度重训
- [x] 新增策略 1 Ledger v1 交易执行语义 PRD 与月度滚动重训 PRD：`docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`、`docs/prd/PRD_20260604_02_策略1月度滚动重训.md`；PR #49 review 的 T+1 卖出锁定、oriented RankIC、月度模式 test split 口径澄清已补入正文；2026-06-04 已进一步改造为 Ledger P0/P1/P2（交易语义、2024-2026.04 fixed-model 连续扩展回测、ledger state resume）再月度重训的实现顺序
- [x] OQ-005 Phase 0 实现分支已整合 review 修复：PR #44 已合入 #42 分支，#46 的 GCS 路径、API 行数上限、Parquet cast、日志脱敏修复已手动合入，并追加修复 `partition_endpoint` 路径契约与参数化日志脱敏泄露问题
- [x] OQ-010 并发调度后续修复已合并（PR #48）：修复同 stage dependency batching 与诊断状态/上传状态语义拆分，支持正式基线和后续实验调度复用
- [x] OQ-010 正式基线 run 已完成：`s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01` / `bt_s1_bqml_baseline_pvfq_n30_bw_h5_v20260604_01`，参数为 `pv_fin_quality + 30/5% + biweekly + 5d`，01-12 全部成功，`10`/`12` QA 通过，中文报告和模型诊断均 uploaded 到 GCS
- [x] 实现 OQ-010 策略 1 实验并发调度与隔离 Phase 1：新增 `sql/meta/02_strategy1_experiment_run_status.sql` 状态表 DDL（`CREATE TABLE IF NOT EXISTS` 保留 audit/resume 历史）、`scripts/strategy1/run_oq010_experiments.py` 调度器（支持 --dry-run 展开完整计划、SQL 参数注入强校验、GCS ifGenerationMatch=0 原子锁、generation-guarded stale reclaim/release、lease/heartbeat、锁 finally 释放、heartbeat 终态保护、resume、max-parallel、max-parallel-backtest、fail-fast 等全部 PRD 定义参数）、`sql/qa/07_strategy1_experiment_concurrency_checks.sql` 并发 QA（QA-CONC-1~12），以及 `docs/策略1实验并发调度器运行手册.md`；已通过 Python 静态检查、stage_a dry-run、单实验 dry-run、全 manifest dry-run、直接参数注入断言；已更新 TODO/memory；尚未执行 BigQuery、不碰正在运行的 A3 实验、不删 reports/strategy1 已有产物
- [x] 新增 OQ-010 策略 1 实验并发调度与隔离 PRD：`docs/prd/PRD_20260603_05_策略1实验并发调度与隔离.md`，定义同阶段 portfolio-only / retrain 实验安全并发的状态表、GCS 原子锁、lease/heartbeat、调度器、runner 改造要求、08 ledger 并发边界和 QA；本次只写 PRD，未改 runner、未跑 BigQuery
- [x] 新增 OQ-005 GCP 数据流水线 PRD：`docs/prd/PRD_20260603_03_GCP数据流水线方案.md`，固化 Cloud Run Jobs + Dataform / BigQuery Studio pipeline + Cloud Composer 架构，限定每日生产采集只覆盖当前实际消费的 14 张 ODS，并已收敛为陈述性目标实现方案；PR #39 review 两条低优先级建议已补入正文
- [x] 新增 ODS 外部表 Parquet schema 修复 PRD：`docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md`，定义 10 张 schema mismatch 外部表的 GCS 原文件 schema-preserving rewrite、staging/backup/发布、QA 门禁和 ingestion 显式 cast 防复发方案；PR #40 review 建议已补入 backup write-once、临时表显式 schema 和 INT→FLOAT64 精度复核
- [x] 新增 ODS/GCS 数据审查目录与提示词：`data_audit/ODS_GCS_DATA_AUDIT_PROMPT.md`、`data_audit/reports/`；审查范围限定 2019-01-01 及之后，提示词要求只审查不补数据、审查脚本由执行 Agent 自行编写并在请求/限速/并发等问题上自修正；已补官方文档链接、API 返回上限命中风险和按 endpoint/主题拆脚本规则
- [x] 实现 OQ-010 首轮实验 runner 参数化（PR #37 已合并）：新增 `configs/strategy1/oq010_experiments_v0.json`、`scripts/strategy1/compare_oq010_experiments.py`；`sql/ml/strategy1/01-06/09-12` 支持 `experiment_id`、调仓频率、持股数/权重、`p_label_horizon`、`feature_set_id`；诊断脚本和 QA 已改为 horizon-aware，并支持 portfolio-only 实验用 `p_prediction_run_id` 复用模型/预测。已通过 Python/JSON/`git diff --check` 与 BigQuery dry-run，尚未端到端实跑实验
- [x] 配置本机 BigQuery Storage API 客户端并修复 OQ-010 诊断稳定性：`data-aquarium` 已启用 `bigquerystorage.googleapis.com`，本机 conda 与默认 `python3` 均已安装 `google-cloud-bigquery-storage`；诊断脚本改为一次性拉取 valid/test 预测标签并将 feature exposure 改为 BigQuery 侧聚合，A0 诊断与 `12_qa_model_diagnosis_outputs.sql` 已通过
- [x] OQ-010 3*2*2*2 全因子 24 组合已补齐并跑完：补跑 19 个缺失组合，全部实验最终状态为 `12_qa_model_diagnosis_outputs=succeeded`；本轮超额收益口径 benchmark 均为 `000852.SH`
- [x] 合并 OQ-010 策略 1 首轮质量迭代实验 PRD（PR #35）：`docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`，定义持股数/权重、调仓频率、标签 horizon、财务特征的第一轮分阶段实验矩阵；已按 review 修订 canonical baseline id、parent experiment 关系和阶段 B/C 调仓频率口径
- [x] 修订 OQ-010 首轮实验执行口径：阶段 A/B/C 不做 `4 * 3 * 3` 笛卡尔积，基础执行为 `4 + 3 + 3 = 10` 个实验，包含阶段 D 为 12 个实验；如阶段间暴露明显交互风险，再补最多 `2 * 2` A/B、A/C、B/C pairwise 复核，必要时补最多 `2 * 2 * 2` 最终保底复核
- [x] 修复诊断 QA：`sql/ml/strategy1/12_qa_model_diagnosis_outputs.sql` 的 `split_tag` 歧义已修复（PR #27/28），已可正常完成 QA 验收
- [x] 实现策略 1 valid/test live-available 预测池口径修正（按 `docs/prd/PRD_20260602_05_策略1预测池口径修正.md`）：train 继续用 trainable labeled sample，valid/test 预测池改为 t 日 live-available feature universe，标签有效性仅用于事后评价（PR #29/30 已合并）
- [x] 实现策略 1 模型质量诊断后续修订（按 `docs/prd/PRD_20260602_04_策略1模型质量诊断.md` + PRD 05）：补 prediction/eval coverage 证据，修正后重跑 local smoke → uploaded → `12_qa_model_diagnosis_outputs.sql`
- [x] 实现策略 1 score orientation 校准（按 `docs/prd/PRD_20260603_01_策略1分数方向校准.md`）：保留 `raw_score`，将最终 `score` 定义为方向校准后的排序分，03 选型登记 `score_orientation`，04 预测阶段应用方向并扩展 QA/report/diagnosis（PR #32 已合并）
- [x] 新增策略 1 分数方向校准 PRD：`docs/prd/PRD_20260603_01_策略1分数方向校准.md`，基于 livepool reverse-score shadow run，将 `raw_score` / oriented `score` / `score_orientation` 固化为待实现契约
- [x] 新增策略 1 valid/test live-available 预测池口径修正 PRD：`docs/prd/PRD_20260602_05_策略1预测池口径修正.md`，明确 sample_filter_risk high 后先修预测池口径，不与信号反向或组合参数实验混做
- [x] 新增策略 1 模型质量诊断 PRD：`docs/prd/PRD_20260602_04_策略1模型质量诊断.md`，明确先诊断 signal/label/sample/universe/portfolio/cost/style，再进入 OQ-010 参数和模型实验
- [x] 策略 1 报告 GCS uploaded 模式已跑通：创建 `gs://ashare-artifacts`（`ASIA-EAST2`）、配置本机 ADC（quota project=`data-aquarium`），去掉 `--skip-gcs-upload` 重跑 `render_report.py`，ADS `report_upload_status=uploaded` 且 `report_uri=gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/run_id=s1_bqml_20260601_01/backtest_id=bt_s1_bqml_20260601_01`，`sql/ml/strategy1/10_qa_runner_outputs.sql` 全部通过
- [x] OQ-010 交易成本口径 PRD 已新增并在 runner SQL 中实现：佣金万一免五、卖出印花税 5 bps、买/卖滑点各 5 bps
- [x] 新增策略 1 报告 GCS 上传运行手册：`docs/策略1报告GCS上传运行手册.md`，明确 uploaded 模式的 bucket/ADC/IAM/执行/验收步骤
- [x] 策略 1 中文报告与归因分析 PRD + 实现已合并：报告中文化、中证1000评估主基准、沪深300展示对比基准、交易/持仓/NAV 附件、亏损证据包和 AI 诊断已进入 `main`（PR #20）
- [x] PR #13 / OQ-003 财务三表 DWD + DWS 已合并：`dwd_fin_income` / `dwd_fin_balancesheet` / `dwd_fin_cashflow`（+ `_latest`）、`dws_stock_feature_fin_daily`、`sql/qa/04_finance_caliber_checks.sql` 已进入 `main`；已随表补全 `ods_field_unit_map` 财务字段映射并跑通 `sql/qa/05_oq006_unit_checks.sql`
- [x] OQ-006 单位契约实现已合并（PR #16）：`ashare_meta.ods_field_unit_map`、`sql/qa/05_oq006_unit_checks.sql`、`dwd_index_eod` 换算修复与 `volume_share/amount_cny` 迁移已进入 `main`，OQ-006 已关闭
- [x] 合并 OQ-006 PRD（PR #14）：`docs/prd/PRD_20260602_01_OQ006接口单位换算口径.md`
- [x] 策略 1 BigQuery ML runner 已于 PR #12 在 BigQuery 端到端实跑并通过 `10_qa_runner_outputs.sql`（16 断言）
- [x] OQ-004 基准指数代码可用性已实现并关闭（`dim_index` + 映射驱动 `dwd_index_eod` + OQ-004 QA + runner benchmark 窗口校验）
- [x] OQ-007 退市日类型已复核并关闭，PR #9 后依赖链已重建并通过 P0 / 策略 1 QA
