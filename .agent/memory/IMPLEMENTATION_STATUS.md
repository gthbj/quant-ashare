# 实现状态（Implementation Status）

这是实现状态的唯一事实来源。面向「已完成/进行中/受阻的整体状态」；「下一步要做什么」见根目录 `TODO.md`。

Last updated: 2026-06-02

## 当前状态

项目处于**P0 DIM/DWD 已物化并通过 smoke QA，OQ-004 基准指数代码可用性已实现并关闭，策略 1 价格量价 DWS/ADS SQL 已物化并通过 QA，策略 1 BigQuery ML runner 设计、实现 PRD 与 `sql/ml/strategy1/01-10` 脚本已合并入 `main`，OQ-003 财务报表口径已采纳并关闭，OQ-006 接口单位换算口径 PRD 草案已完成**阶段。已产出 DWD/DIM 建模方案、DWS/ADS 表设计方案、策略方案、策略 1 PRD、runner 设计与 runner 实现 PRD、OQ-003 财务 `report_type` 口径 PRD、OQ-004 基准指数代码可用性 PRD、OQ-006 单位契约 PRD。owner 澄清：财务/事件按分区前移到 2017，行情最终写 2019+ 但构建时读 2018 lookback buffer，维度/日历取最新快照或全量历史事件；OQ-003 已采纳 P0 默认合并报表 `report_type='1'`、DWD 保留口径字段、DWS 默认过滤默认口径。根目录 `sql/` 已覆盖 P0 DIM/DWD、策略 1 DWS、策略 1 ADS 表契约、策略 1 BigQuery ML runner、metadata 和 QA；BigQuery 目标已建 4 张 DIM + 5 张 DWD + 6 张策略 1 DWS + 11 张 ADS 契约表。OQ-004 已新增并物化 `dim_index`，`dwd_index_eod` 已改为从 `dim_index` 读取映射并重建，`sql/qa/03_oq004_index_checks.sql` 通过，runner 08 benchmark 前置校验 dry-run 通过；PR #11 review feedback 已跟进并已合并到 `main`，合并后本地/远端 `codex/implement-oq004-index` 分支已删除。OQ-007 的 ODS `stock_basic_delisted.delist_date` 已复核为 `STRING` 且可解析，仓库 SQL 已改为优先使用 ODS 退市日，PR #9 已合并；2026-06-02 已重建 `dim_stock`、`dwd_stock_eod_price`、策略 1 DWS 六表与 ADS 契约表，并重新执行 metadata、P0 QA 和策略 1 QA。暂无调度代码。策略 1 runner 已于 PR #12 在 BigQuery 端到端实跑并通过全部 QA：run_id `s1_bqml_20260601_01` / backtest `bt_s1_bqml_20260601_01`，产出训练面板 3,051,752 行、5 个 BQML LOGISTIC_REG 候选+选型、预测/候选/组合/订单/回测/监控 ADS 结果和本地报告，`10_qa_runner_outputs.sql` 16 个断言全过。实跑暴露并修复多处运行期问题（03/07/08/09 相关子查询去相关 + 分区过滤、10 `cal_date`、render ADC 回退 + PARSE_JSON wide number），并按 DECISION-20260601-07 将 08 由 v0 set-based 重写为账户级有状态 ledger（v0 守卫 cash/gross 在真实数据上失败）。v0 模型为反向预测基线（valid rank_ic≈-0.10、AUC≈0.50），回测 NAV 收于≈0.02——属模型质量（OQ-010）问题，非管线缺陷。

## 已完成（Completed）

- ODS 探查：`ashare_ods` 当前 57 张外部表的字段与分区语义已摸清（三类分区：A 行情增量 / B 财务报告期 / C 维度快照；`index_member_all`/`ci_index_member` 为最新分区全量历史区间快照）。
- DWD/DIM 建模方案文档 `docs/数据仓库建模方案-DWD-DIM.md` 定稿：分层、57 表映射、五条铁律、DIM/DWD 逐表设计、DWS 衔接、工程建议、路线图、风险项。
- 命名规范敲定：`sec_code` 主键、`trade_date/cal_date`、`ann_date_eff`、单位元/股、复权 `_hfq/_qfq`、血缘 `source_system/ingested_at`。
- 物理设计敲定：按月分区 + `sec_code` 聚簇、行情表 `require_partition_filter=TRUE`。
- 2019 前数据范围敲定：财务/事件 `partition_date >= '20170101'`；行情 DWD/DWS 写 `trade_date >= 2019-01-01`、构建时按最大窗口读取 2018 lookback buffer；维度/日历取最新快照或全量历史事件。
- 表/字段注释规范敲定：内联 DDL / 后置 ALTER / 继承 ODS 描述三法。
- 仓库初始化：`git init` + `.gitignore` + 首个 commit（`main`）。
- 建立 `.agent/` Agent 工作记忆体系 + 根 `AGENTS.md` 读写协议；推送 GitHub（gthbj/quant-ashare）；加模型署名协议。
- 按实测 review 整改建模方案（9 采纳 / 2 调整）：财务版本事实表、价格表「交易日历×在市」骨架（含停牌日）、表级可见日规则（`fina_indicator` 用 `ann_date`）、ODS 元数据矩阵、lookback buffer、方向性可交易、`visible_trade_date`、表数订正 54；写 `docs/reviews/…-review-response.md`。
- 修正早先“全历史写入”误读：`docs/reviews/数据仓库建模方案-DWD-DIM-review-2019前数据范围修正.md` 已改为 2019 前数据范围修正说明；主方案 §4.6 已新增范围表。
- 主方案文首和 TL;DR 已显式说明：当前建模范围是 2019-01-01 之后的 A 股日线 DWD/DWS；2019 年以前数据仅作为 PIT / lookback / 维度历史支撑。
- P0 建表 SQL 已落地到 `sql/`：`00_create_datasets.sql`、4 张 DIM、5 张 DWD、3 个 QA 脚本。脚本采用 `CREATE OR REPLACE TABLE`、月分区、`sec_code` 聚簇、范围参数 `dwd_start_date/fin_start_period/lookback_start_date`。
- SQL 校验完成（物化前历史阶段）：dataset/DIM 脚本 dry-run 通过；`dwd_stock_eod_valuation`、`dwd_index_eod` dry-run 通过；`dwd_stock_eod_price`、`dwd_fin_indicator` 曾因目标 DIM 未物化，使用临时空维表替换后 dry-run 通过。后续 P0 已实际物化并通过 QA。
- 采纳并修复 P0 SQL 评审发现：README 命令加 `--location=asia-east2`；`suspend_d` 只以 `suspend_type='S'` 标记停牌，复牌 `R` 不再误判停牌；`dim_stock` 加 `sec_code` 去重与派生退市 30 日宽限；`dwd_fin_indicator` 加版本键去重兜底；新增 `dwd_fin_indicator_latest` 与 `sql/qa/01_p0_smoke_checks.sql`。修复后相关脚本 dry-run 通过。
- P0 物化完成并通过 smoke QA：`dim_trade_calendar` 13,162 行；`dim_stock` 5,853 行；`dim_stock_name_hist` 3,776 行；`dim_index` 7 行；`dwd_stock_eod_price` 8,506,688 行（2019-01-02 至 2026-06-02 当前范围）；`dwd_stock_eod_valuation` 8,452,073 行；`dwd_index_eod` 11,922 行；`dwd_fin_indicator` 332,960 行；`dwd_fin_indicator_latest` 198,030 行。2026-06-01 OQ-004 实现后新增 `dim_index` 并重建 `dwd_index_eod`，OQ-004 专项 QA 通过；2026-06-02 PR #9 依赖链重建后，P0 smoke QA 通过。
- 上游修复 `ods_tushare_index_dailybasic` Parquet 类型后，`dwd_index_eod` 已恢复估值/股本字段并重建：2019+ 共 11,922 行，其中 8,899 行有 `pe/pe_ttm/pb/total_mv_cny/float_mv_cny/total_share/float_share` 等 dailybasic 字段；STAR50(`000688.SH`) 和 CSI1000(`000852.SH`) 因 ODS 无 dailybasic endpoint 仍为空。
- `dwd_index_eod` 脚本已按 owner 确认调整为 canonical `sec_code` + `source_sec_code` 血缘口径，并已重建 BigQuery 实表；重新执行 `sql/metadata/01_p0_table_column_descriptions.sql` 和 `sql/qa/01_p0_smoke_checks.sql` 通过。验证：沪深300 `sec_code='000300.SH'`、`source_sec_code='399300.SZ'`，STAR50/CSI1000 估值字段仍因 ODS 无 dailybasic endpoint 为空。
- 修复 P0 二轮评审发现：`dwd_stock_eod_price` 将 `is_suspended` 限定为全天停牌/无成交，新增 `has_intraday_halt` 与 `has_open_halt`，开盘临停影响 `can_buy_open/can_sell_open/is_tradable`；`dwd_fin_indicator_latest` 改为 `update_flag DESC, ann_date_eff DESC, ingested_at DESC, source_partition_date DESC` 排序。相关表已重建，QA 通过；验证指标：有成交但 `is_suspended=TRUE` 为 0，latest 排序差异为 0。
- P0 表/字段说明补齐：新增并执行 `sql/metadata/01_p0_table_column_descriptions.sql`，9 张 P0 DIM/DWD 表的 table description 和所有 schema field description 均已补齐；2026-06-02 复核 missing description = 0。
- OQ-007 已复核并关闭：`stock_basic_delisted.delist_date` 在 ODS 中已统一为 `STRING`，最新 delisted 分区 326 行全部可解析；`dim_stock` SQL 改为优先使用 ODS 退市日，daily 最后交易日加一天仅作缺值兜底，并补 P0 QA 断言（含退市股生命周期合法性）。2026-06-02 已按依赖重建 BigQuery 实表。
- PR #9 合并后的 OQ-007 依赖链已在 BigQuery 重建并通过 QA：`dim_stock` 5,853 行，其中 326 个退市股使用 `stock_basic_delist_date`；`dwd_stock_eod_price` 8,506,688 行；策略 1 DWS 六表已重建，`dws_stock_sample_daily` 8,506,688 行，`sample_trainable_default` 3,274,084 行；ADS 11 张契约表已重建（执行前均为空表）。已执行 `sql/metadata/01_p0_table_column_descriptions.sql`，P0 DIM/DWD 字段说明缺失数为 0；`sql/qa/01_p0_smoke_checks.sql` 与 `sql/qa/02_strategy1_dws_ads_checks.sql` 全部通过。
- DWS/ADS 表设计文档已完成：`docs/数据仓库建模方案-DWS-ADS.md`。定义 P0 DWS（universe、价格/估值/财务特征、市场状态、标签、样本）与 ADS（训练面板、模型预测、候选池、组合、订单计划、回测/监控）表体系。
- 策略方案文档已完成：`docs/A股中低频小资金机器学习策略方案.md`。定义首个 `ml_ranker_v0` 机器学习横截面排序策略，以及小盘质量反转、趋势延续、财务事件、资金筹码、行业轮动等后续策略族。
- 策略 1 PRD 已完成并通过 review 修订：`docs/prd/PRD_20260601_01_策略1价格量价基础分类模型.md`。首版落地名称为 `ml_pv_clf_v0`，范围限定价格量价 + 估值特征、open-to-close 标签和通用 DWS/ADS 表契约。
- 策略 1 DWS SQL 已落地并物化：`sql/dws/01_dws_stock_universe_daily.sql`、`02_dws_stock_feature_price_daily.sql`、`03_dws_stock_feature_valuation_daily.sql`、`04_dws_stock_label_daily.sql`、`05_dws_stock_feature_daily_v0.sql`、`06_dws_stock_sample_daily.sql`。2026-06-02 PR #9 依赖链重建后行数：universe 8,506,688 行、价格特征 8,506,688 行、估值特征 8,452,073 行、标签 8,506,688 行、特征宽表 8,506,688 行、样本表 8,506,688 行（默认可训练 3,274,084 行）。
- 策略 1/P0 ADS 表契约已落地并物化：`sql/ads/01_ads_strategy1_tables.sql` 创建训练面板、模型注册、预测、候选池、组合目标、订单计划、回测成交/持仓/NAV/绩效汇总、信号监控 11 张表。
- 策略 1 DWS/ADS QA 已落地并通过：`sql/qa/02_strategy1_dws_ads_checks.sql` 校验 DWS/ADS 表存在、DWS 主键唯一、universe 含退市股存活区间、不暴露 qfq 字段、2019 初 60 日历史不完整显式标记、默认可训练样本具备 universe-ranked `rank_pct_5d`、`fwd_ret_5d = close_hfq[t+5] / open_hfq[t+1] - 1`。
- PR #4 comment 跟进修复完成：`dws_stock_label_daily` 去掉 `ce/c1` 冗余日历 JOIN；补充 `label_valid_*d` 与 `exit_reachable_*d` 字段说明，明确 `label_valid` 检查入场可交易与标签价格可用，退出可卖性交给 `exit_reachable` 和回测撮合；`sql/qa/02_strategy1_dws_ads_checks.sql` 增加默认可训练样本最早日期断言（当前 `2019-04-03`，2019Q1 无默认可训练样本）；DWD-DIM/DWS-ADS 文档同步相关口径与 `volume_share`/`amount_cny` 实表字段名。已重建 label/sample 并重跑策略 1 QA 通过。
- PR #4 已合并到 `main`；已删除合并后不再使用的 `codex/implement-strategy1-prd` 本地分支和远端分支，并在 `KNOWN_CONSTRAINTS.md` 增加 PR 合并后清理无用 `codex/*` 分支的工程规则。
- 策略 1 BigQuery ML runner 设计已完成：`docs/策略1-ml_pv_clf_v0-runner设计.md`。设计限定 BigQuery SQL + BigQuery ML 执行路径，覆盖训练面板、`CREATE MODEL`、BQML `L1_REG/L2_REG` 手动候选网格、valid RankIC 选型、`ML.PREDICT`、候选池、组合、订单、回测、监控、GCS 报告产物、本地报告镜像、幂等、QA 和验收；`board` 保留为监控字段、不进 v0 主模型训练列。
- 策略 1 BigQuery ML runner 与回测闭环实现 PRD 已完成：`docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`。PRD 定义 `sql/ml/strategy1/01-10` 脚本交付物、输入输出、运行参数、功能需求、QA、报告产物和验收标准；报告渲染脚本 `scripts/strategy1/render_report.py` 是必需交付物。（PRD 原 v0 卖出顺延 `next_sellable_trade_date` 口径已在 PR #12 实跑后废弃、升级为 v1 账户级 ledger，PRD/设计已同步。）
- 策略 1 BigQuery ML runner 脚本已合并入 `main`（PR #7）：`sql/ml/strategy1/01_build_training_panel.sql` 至 `10_qa_runner_outputs.sql`、`sql/ml/strategy1/README.md`、`scripts/strategy1/render_report.py` 与 `scripts/strategy1/requirements.txt`。
- 策略 1 runner 已在 BigQuery 端到端实跑并通过全部 QA（PR #12）：run_id `s1_bqml_20260601_01` / backtest `bt_s1_bqml_20260601_01`。01 训练面板 3,051,752 行；02 训练 5 个 BQML LOGISTIC_REG 候选；03 选 `l1_0_l2_1e_3`（valid rank_ic≈-0.10、AUC≈0.50，反向预测基线）；04 预测 1,052,687 行；05 候选 224,648 行；06 组合 520 行；07 订单 565 行；08 ledger 回测（NAV 485 天；不可交易腿记 `*_SKIPPED_UNTRADABLE` 意图行并 carry）；09 summary+monitor（buy/sell skip 指标从成交表 1:1 汇总）；render 本地报告（local-only `--skip-gcs-upload`：写 `local_report_path` + `report_upload_status=skipped`，`report_uri=NULL`）；`10_qa_runner_outputs.sql` 16 个断言全过（含模式感知报告断言）。实跑修复：03/07/08/09 BigQuery 相关子查询去相关 + 强制分区过滤、10 `cal_date`、render ADC 回退 + PARSE_JSON wide number；08 因 v0 set-based 守卫失败（现金 -34 万、gross 2803 倍）按 DECISION-20260601-07 重写为账户级有状态 ledger。PR #12 review 跟进：08 写 skip 意图行 + 09 改 ledger 口径成交诊断、render 仅在真实上传时写 `report_uri`、`ads_backtest_trade_daily.fill_status` 描述补 skip 枚举、文档/记忆收敛到 v1 ledger。NAV 收于≈0.02 属 v0 模型质量（OQ-010），非管线缺陷。
- OQ-006 接口单位换算口径 PRD 草案已完成：`docs/prd/PRD_20260602_01_OQ006接口单位换算口径.md`。PRD 建议把 OQ-006 从人工记忆升级为单位契约 + 覆盖检查 + DWD 准入门禁，后续实现交付物包括 `ashare_meta.ods_field_unit_map`、P0 + PR #13 财务三表首批字段映射 seed、`sql/qa/05_oq006_unit_checks.sql`、DWD-DIM/README/KNOWN_CONSTRAINTS 同步；已按 review feedback 明确 PR #13 财务三表不能只放 P1、QA 编号避开 `04_finance_caliber_checks`、契约表增加命名例外字段、P0 覆盖补价格/比率字段；OQ-006 仍 open，待 owner review 与实现。
- OQ-003 财务 `report_type` / 报表口径维度已采纳并关闭：`docs/prd/PRD_20260601_03_财务报表口径维度.md`。P0 默认消费合并报表 `report_type='1'`，DWD 对三大财务表保留 `report_type`/`report_caliber`/`is_default_report_caliber`，DWS 财务特征默认只过滤默认口径并补 NULL-safe QA；后续实现 PR 需同步主建模方案文档和 SQL。
- OQ-004 基准指数代码可用性已实现并关闭：`docs/prd/PRD_20260601_04_OQ004基准指数口径.md` 已更新为已实现；新增 `sql/dim/04_dim_index.sql`，更新 `sql/dwd/04_dwd_index_eod.sql` 从 `dim_index` 读取映射，新增 `sql/qa/03_oq004_index_checks.sql`，并在 `sql/ml/strategy1/08_run_backtest.sql` 增加 benchmark 可用性与窗口覆盖前置校验。BigQuery 已物化 `dim_index`、重建 `dwd_index_eod`、执行 metadata，OQ-004 QA 通过。
- PR #11 review feedback 已跟进：`sql/dim/04_dim_index.sql` 注明中证2000/国证2000等未见 ODS `index_daily` 端点时不 seed；`dim_index` 字段描述改由 `sql/metadata/01_p0_table_column_descriptions.sql` 统一维护；`sql/qa/03_oq004_index_checks.sql` 注明示例 benchmark/window 与 SSE 日历假设；`sql/ml/strategy1/08_run_backtest.sql` 注明 runner benchmark 窗口校验使用 SSE 作为全市场开市日历。复核结果：`dim_index` 与 `dwd_index_eod` 字段描述缺失数均为 0，OQ-004 QA 通过。
- PR #11 已合并到 `main`，本地 `main` 已 fast-forward 到远端合并结果；远端和本地 `codex/implement-oq004-index` 分支均已删除。
- 策略 1 首个基线股票池板块纳入口径已确认：仅沪深主板（`SSE_MAIN` / `SZSE_MAIN`），不含北交所、创业板、科创板。现有 `sql/dws/01_dws_stock_universe_daily.sql` 默认 `board_allowlist` 已符合该口径；已同步文档和 OQ-010，OQ-010 仅剩成本、调仓、持股数/权重上限待确认。
- 评审协议已按 owner 最新要求更新：GitHub PR review 默认写 PR comment，一条写不下拆多条；只有 owner 明确要求或无 PR comment 承载面时才写 `docs/reviews/` 评审文档。`DECISION-20260531-13` 已被 `DECISION-20260601-03` supersede。
- ODS 已补采 `index_member_all` 和 `ci_index_member`；主方案、DWS/ADS 文档和策略文档已更新为可落地申万/中信行业时点映射，OQ-001 已关闭。
- 工作记忆瘦身完成：旧交接归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-05.md`；已关闭问题迁移到 `.agent/memory/archive/CLOSED_QUESTIONS.md`；`OPEN_QUESTIONS.md` 仅保留 open 项；`UPDATE_PROTOCOL.md` 增加只读任务免追加交接和归档规则。
- `TODO.md` 已整理为下一步可执行清单：移除大段历史完成项和重复 OQ 汇总，仅保留当前优先、P1 扩展、工程/调度待办与少量近期完成项；开放问题继续以 `OPEN_QUESTIONS.md` 为唯一来源。

## 进行中 / 部分（In Progress）

- 无。

## 未开始 / 未来（Not Started / Future）

- `lookback_start_date` 从固定默认值升级为按最大滚动窗口计算/调度配置。
- 「从 ODS 继承字段描述」的脚本（bq show → 映射 → bq update）。
- 增量调度（dbt 或 Airflow + SQL）、数据质量断言。
- OQ-006 实现：新增 `ashare_meta.ods_field_unit_map`，补 P0 + PR #13 财务三表首批单位映射 seed，新增 `sql/qa/05_oq006_unit_checks.sql`，并将单位准入硬规则写入 DWD-DIM / README / `KNOWN_CONSTRAINTS.md`。
- P0 通用 DWS 扩展表：`dws_stock_feature_fin_daily`、`dws_market_state_daily`（策略 1 价格量价首版未阻塞；财务特征按 OQ-003 PRD 默认合并报表口径消费）。
- 策略 1 runner v0 模型质量提升（独立于管线）：当前 `ml_pv_clf_v0` valid rank_ic≈-0.10（反向预测）、回测 NAV≈0.02，需要特征/标签/选股口径迭代（OQ-010），管线本身已端到端跑通。
- lookback-capable 价格构建输入：当前策略 1 DWS 只读取最终 DWD/DIM，不直接读 ODS；由于最终 DWD 价格表不落 2018 buffer 行，2019 年初 60 日价格窗口用 `has_full_history_60d=FALSE` 显式标记并由默认样本掩码剔除。若要求 2019-01 起 60 日窗口完整，需要补专用 lookback 构建输入或调整 DWD/DWS 构建方式。
- P1+ 资金面/事件/行业族 DWD。
- `dim_stock_sw_industry_hist` / `dim_stock_ci_industry_hist` 建表 SQL 与 QA（`out_date` 边界、区间重叠/缺口、2019+ 覆盖率）。

## Coverage Snapshot

| 能力 | 状态 | 备注 |
|---|---|---|
| ODS 理解 | 高 | 57 表字段+分区语义已探明 |
| DWD/DIM 设计 | 高 | 主文档已完成；§4.6 已修订 2019 前数据范围 |
| 命名/单位/分区/注释规范 | 高 | 已敲定并写入文档 |
| P0 建表 SQL | 已完成 | `sql/` 已新增 4 张 DIM + 5 张 DWD + QA；OQ-004 新增 `dim_index` 和专项 QA |
| P0 表物化/QA | 已完成 | 4 张 DIM + 5 张 DWD 已物化；PR #9 后 `dim_stock` 依赖链已重建，P0 smoke QA 通过；OQ-004 专项 QA 通过 |
| DWS/ADS 设计 | 已完成 | 两篇设计文档已完成；策略 1 DWS 六表、ADS 表契约与 runner 脚本已落地 |
| ETL/调度 | 未开始 | — |
| DWS 特征/标签 SQL | 部分完成 | 策略 1 universe、价格/估值特征、标签、宽表、样本已物化并 QA；财务特征和市场状态待补，财务口径已采纳 |
| 策略/ADS 闭环 | 已跑通 | `ml_pv_clf_v0` runner 01-10 已在 BigQuery 端到端实跑（PR #12），08 为账户级 ledger，`10` 16 断言全过；模型质量待迭代（OQ-010） |
| 行业映射 | 可落地设计完成 | ODS 已有 index_member_all / ci_index_member；待 SQL 和 QA |
