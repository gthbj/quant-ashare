# 已知约束（Known Constraints）

## 数据约束（Tushare / ODS 事实）

- ODS 全部为 Hive 分区外部表，**查询必须带 `partition_date`/`endpoint` 过滤**（强制分区裁剪），否则报错。`partition_date` 是 `YYYYMMDD` 字符串。
- OQ-005 采集 manifest 中 `endpoint` 表示 Tushare API endpoint，`partition_endpoint` 表示写入 GCS Hive 分区 `endpoint=` 的值；两者不得混用。普通接口二者相同，`stock_basic` 必须按 request variant 写入 `stock_basic_listed` / `stock_basic_delisted` 两个 `partition_endpoint`，以匹配 `dim_stock` 的 `endpoint IN (...)` 消费口径。
- 2026-06-03 复核确认 10 张 ODS 外部表存在 Parquet schema mismatch：`ods_tushare_daily_info`、`ods_tushare_dividend`、`ods_tushare_fina_audit`、`ods_tushare_limit_list_d`、`ods_tushare_margin`、`ods_tushare_margin_detail`、`ods_tushare_moneyflow`、`ods_tushare_stk_limit`、`ods_tushare_stk_rewards`、`ods_tushare_sz_daily_info`。修复按 `docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md` 执行：先从 GCS 原 Parquet 按 schema contract 做 schema-preserving rewrite，API 重拉只作为原文件损坏、缺失或 owner 明确要求的补救路径；修复过程只改 Parquet 物理 schema，不补数据、不改业务值口径、不写伪空 Parquet；backup 必须 write-once，已匹配 contract 的文件跳过重写 / 发布。
- **财务表 `partition_date == 报告期(end_date)`，不是公告日**：禁止用 partition_date 当数据可见时间，必须用 `ann_date_eff = COALESCE(f_ann_date, ann_date)` 做 PIT。
- 财务表同一 `(sec_code, 报告期)` 有多条（不同 `report_type`/修正/`update_flag`）：P0 默认消费合并报表 `report_type='1'`；带 `report_type` 的 DWD 版本事实表保留源 `report_type` 并派生 `report_caliber`/`is_default_report_caliber`，P0 DWS 默认过滤默认口径，多口径特征后续另建/扩展。
- **三大报表 `income/balancesheet/cashflow` 已落地**（`sql/dwd/06/08/10` + `_latest` 07/09/11，OQ-003/DECISION-20260601-05）：实测当前 ODS 三表**仅含 `report_type='1'`**（合并报表，分 `comp_type` 1/2/3/4/7）；版本事实键 `(sec_code, report_period, report_type, ann_date_eff, update_flag)`，可见日 `COALESCE(f_ann_date, ann_date)`；默认 `_latest` 与 `dws_stock_feature_fin_daily` 只消费默认合并口径。`report_type>'1'` 的 caliber 映射为前向兼容、当前不触发。金额单位为元（Tushare 原始口径，未换算），income/cashflow 为累计/YTD、balancesheet 为时点值。
- `dws_stock_feature_fin_daily`（`feature_version='fin_default_v0_20260602'`）把 `dwd_fin_indicator` + 三大报表 as-of 到 universe 每个交易日：`report_caliber`/`is_default_report_caliber` 是**消费口径契约**（恒 consolidated/TRUE），实际可用性看 `has_fin_*` 与 `*_report_period`；as-of 有界 `visible_trade_date ∈ [trade_date-900d, trade_date]`，超窗视为缺失（DECISION-20260602-03）。行数 = universe，主键唯一，零 PIT 泄露。
- `dwd_fin_*_latest` / `dwd_fin_indicator_latest` 是便捷最新表，不用于 PIT 回测 join；其版本排序按 `update_flag DESC, ann_date_eff DESC, ingested_at DESC, source_partition_date DESC`，优先保留修正版。
- `stock_basic` 用 `endpoint` 分 `listed`/`delisted`：**必须 UNION 两者**，否则丢失退市股 → 幸存者偏差。
- 行情历史自 **1990-12-19**；行情表单分区内 `(ts_code, trade_date)` 已唯一、无需去重。
- 2019 年前数据范围分三类，不能混作“全历史写入”：财务/事件按分区前移到 `20170101`；行情 DWD/DWS 最终写 `trade_date >= 2019-01-01`，构建时按最大滚动窗口读取 2018 lookback buffer；维度/日历取最新快照或全量历史事件。
- 行情 lookback buffer 不落最终 DWD/DWS；`ret_1d` 至少读到 2018 年最后一个交易日，120/250 日滚动特征按窗口多读。
- 当前已物化的策略 1 价格 DWS 只读取最终 DWD/DIM，不直接打 ODS；最终 DWD 价格表不落 2018 buffer 行，因此 2019 年初 60 日窗口以 `has_full_history_60d=FALSE` 显式标记，默认样本掩码剔除这些不完整窗口。若需要 2019-01 起完整 60 日特征，需补专用 lookback-capable 构建输入或调整 DWD/DWS 构建方式。
- **`fina_indicator` 无 `f_ann_date`**（实测）：其可见日只能用 `ann_date`；可见日规则**按表定义**，不可用统一 `COALESCE(f_ann_date,ann_date)` 公式覆盖所有财务表（见 docs §4.3）。
- `stock_basic_delisted.delist_date` 已由上游统一为 `STRING` 并可直读解析；`dim_stock` 应优先使用 ODS 退市日，只有缺值时才用 `daily` 最后交易日加一天兜底（OQ-007 已关闭）。
- **停牌日 `daily` 无该股行**：价格 DWD 必须以「交易日历开市日 × 在市股票」为骨架（保留停牌日空行），不能从 `daily` 起表，否则停牌日整行消失、`t+k` 标签错位。
- **`suspend_d.suspend_type` 区分停牌/复牌**：`S`=停牌，`R`=复牌。价格 DWD 只可用 `S` 标记停牌事件；`R` 复牌日若 daily 有成交，不能判 `is_suspended=TRUE`。
- `S` 事件也可能是盘中临停。若当日 `daily` 有 close 且 volume > 0，不能把该行标为全天停牌；DWD 用 `has_intraday_halt` 标记盘中临停，用 `has_open_halt` 标记开盘时段或未知时段临停并影响开盘建仓掩码。
- Tushare 各接口金额/量单位不一（手/千元/万股/万元）：落库须按「表+字段」归一到元/股。
- OQ-006 已实现：`ashare_meta.ods_field_unit_map` 是单位换算唯一事实来源；`dwd_index_eod.volume/amount` 已按 `vol*100` / `amount*1000` 换算并迁移为 `volume_share/amount_cny`；新增或修改 DWD 标准字段的 PR 必须更新 `ods_field_unit_map` 并运行 `sql/qa/05_oq006_unit_checks.sql`；OQ-006 最小实现已先于 P1 资金流、财务扩展等高单位风险 DWD 正式落地。
- 部分数值字段在 ODS 是 STRING（如 `moneyflow_hsgt`、`ccass_hold`）：落库须 `SAFE_CAST`。
- 北向数据（hk_hold / moneyflow_hsgt）2024 年后部分口径变化/停更，需做可用性标记。
- `index_member_all` / `ci_index_member` 已在 ODS 中可用，是最新分区中的全量历史行业归属区间快照；历史 join 必须用 `in_date/out_date`，不能用 `is_new` 回填历史。默认区间口径为 `[in_date, out_date)`，落地前需 QA `out_date` 当天有效性、区间重叠/缺口和 2019+ 覆盖率。
- `dim_index` 是指数 canonical 映射、ODS 实际代码、端点可用性和 benchmark 候选状态的事实来源。`dwd_index_eod.sec_code` 应输出 canonical 指数代码；若 ODS 实际代码不同，用 `source_sec_code` 保留来源代码（如 ODS `399300.SZ` → canonical `000300.SH`），DWS/ADS 基准 join 只使用 canonical `sec_code`。
- runner 使用 `benchmark_sec_code` 前必须校验该代码在 `dim_index` 中 `has_daily=TRUE AND is_benchmark_candidate=TRUE`，并校验完整 NAV 窗口内 `dwd_index_eod` 对每个开市日有且只有一条非空价格记录。依赖指数 PE/PB/市值字段的市场状态特征必须要求 `dim_index.has_dailybasic=TRUE`。

## 平台约束（BigQuery）

- **单表最多 4000 个分区**：行情表必须按月分区（`DATE_TRUNC(trade_date, MONTH)`），不能按天。
- **只有分区列能 `require_partition_filter` 强制过滤；聚簇列无法强制**。
- `CREATE TABLE AS SELECT` 不能在 SELECT 列上内联 description：维度表用内联列定义 DDL，事实表用 CTAS + 后置 `ALTER COLUMN SET OPTIONS`。
- P0 表重建后必须执行 `sql/metadata/01_p0_table_column_descriptions.sql`，集中恢复/补齐表级和字段级中文说明。财务三表 DWD（`dwd_fin_income/balancesheet/cashflow` + `_latest`）与 `dws_stock_feature_fin_daily` CTAS 重建后必须执行 `sql/metadata/02_finance_table_column_descriptions.sql`（CTAS 不保留列描述，PRD_20260601_03 §10）；`sql/qa/04_finance_caliber_checks.sql` 内置字段 description 缺失断言，漏跑会被 QA 拦截。
- 外部表的列描述/分区元数据通过 `bq show`/`INFORMATION_SCHEMA` 获取。
- `bq query` 执行本项目建表/QA 脚本时显式指定 `--location=asia-east2`，避免无源表脚本或跨数据集 CTAS 使用错误 job 区域。

## 建模约束（PIT / 量化正确性）

- 前复权价（`_qfq`）隐含未来除权信息，**不得作为训练特征**；技术指标/收益用后复权（`_hfq`）。
- 标签必须与特征时间错位：`t` 日特征 → 标签从 `t+1` 起算（入场价用 `t+1`）。
- universe 必须含退市股历史区间，并打标停牌/一字板/上市未满 N 日/ST 做样本掩码。
- 涨跌停价直接用 `stk_limit.up_limit/down_limit`（已按板块算好），不要自己按板块硬编码。

## 安全约束（红线）

- 仓库、记忆文件、文档、日志中**绝不可出现**：BigQuery service account key、Tushare token、任何 API key / 凭据 / 个人隐私。
- 凭据通过环境变量 / 受信环境注入；`.gitignore` 已忽略 `*.key`/`credentials*.json`/`.env` 等。

## 工程约束

- DWD/DIM 物化后，下游一律查 DWD/DIM，不直接打 ODS。
- 大范围回填建议分批（按年/季）跑并记录批次状态；P0 行情最终写 2019+，财务/事件从 2017 起。
- `dim_stock` 若遇到 latest `stock_basic` 缺失但 2019+ daily 有记录的代码，只能作为 `derived_from_daily` 兜底；派生退市边界用 ODS 最新交易日减宽限期判断，不能用系统当前日期直接判退市。
- PR 合并后，若 owner 未要求保留工作分支，应删除已合并且不再使用的 `codex/*` 本地分支和对应远端分支，保持分支列表干净。
- 提交（commit/push）仅在用户明确要求时进行。
- 策略 1 回测 `08_run_backtest.sql` 已按 `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md` 升级为 **ledger_exec_v1 日级账户 ledger**：`rebalance_date` 是信号日，下一开市日按开盘价加滑点执行；每日维护现金、实际持仓和 pending sell；卖出先于买入；买单按可用现金缩放；同股新目标与旧仓 netting；非目标旧仓留在 NAV 中每日 mark-to-market；卖不出进入 pending sell 并在后续每个开市日继续尝试；买不进不候补；订单状态显式写入 `FILLED`、`FILLED_SCALED_CASH`、`BUY_SKIPPED_UNTRADABLE`、`SELL_SKIPPED_UNTRADABLE`、`PENDING_SELL_CARRY`、`CANCELLED_BY_NETTING`、`SKIPPED_CASH_INSUFFICIENT`、`SKIPPED_MIN_NOTIONAL`、`NOOP_ALREADY_TARGET`。`10` 守卫断言 `cash_cny >= -1`、`gross_exposure <= 1.005`、持仓 `(trade_date, sec_code)` 唯一、NAV 覆盖全开市日、状态枚举、skipped/cancel/noop 零成交、同日同股填成交后只允许一个方向、pending sell 次日继续处理。P0 仍简化：FLOAT 股数、不做 100 股手数约束、不显式 T+1 卖出锁定、不做买入候补、不做 partial-fill 深度模型。
- **BQML runner 执行严禁并发，且清理模型对象前必须先确认无 RUNNING job**（2026-06-02 实跑事故教训）：
  - `02_train_bqml_logistic_candidates.sql` 用 `FOR ... EXECUTE IMMEDIATE 'CREATE OR REPLACE MODEL ...'` 顺序训练 5 个候选，单次执行约 5 分钟。**同一 run_id 的两个 02 执行重叠**会让后启动的那个撞上正在训练的同名模型，报 `Concurrent model update with retrain is not supported`（约 5 秒即失败）；先启动的那个其实仍在后台正常跑完。教训：一个 runner 步骤跑起来后，未确认结束前不要重复提交，CLI 返回报错≠后台 job 已停。
  - 事故经过：误判第一个 02「被拒绝/失败」而重跑，导致两执行重叠；随后又依据**过期的 `bq ls` 快照**把仍在运行的 job 正在训练的模型 `s1_bqml_20260601_01__l1_0_l2_0` `DROP` 掉，造成 job 完成后 `ads_model_registry` 有 5 条记录但只剩 4 个模型对象（registry 指向已删模型）。
  - 规则：① 动手 `DROP MODEL` / 删表前，先 `bq ls --jobs ... | grep RUNNING` 确认没有在跑的相关 job；② 用 `bq --location=asia-east2 wait <job_id> <秒>` 等 job 真正结束再做下一步；③ 修复 registry/模型不一致用 runner 自带幂等：以 `p_force_replace=TRUE` 重跑 02（会先 DELETE 同 run_id registry 再重建全部模型），不要手工拼 DDL 单独补建。
- OQ-010 实验并发调度与隔离 Phase 1 已实现：状态表 DDL（`sql/meta/02_strategy1_experiment_run_status.sql`）、调度器（`scripts/strategy1/run_oq010_experiments.py`）、GCS 原子锁（`ifGenerationMatch=0`）、并发 QA（`sql/qa/07_strategy1_experiment_concurrency_checks.sql`）。调度器引入的新约束：GCS 锁对象在 `gs://ashare-artifacts/locks/strategy1/oq010/` 下，默认 TTL 30 分钟，heartbeat 每 60 秒刷新；stale reclaim、heartbeat 写入与 release 必须使用已检查/持有的 GCS object generation 做条件操作，禁止无条件删除同名 lock object；锁获取后必须用 `finally` 释放，heartbeat 线程必须停止后再写 terminal status，避免 `running` 覆盖 `succeeded` / `failed`；状态表只用于审计和 resume 输入，不承担锁管理职责，DDL 必须保留历史审计记录（`CREATE TABLE IF NOT EXISTS`），且 `lock_expires_at` / `last_heartbeat_at` 必须与 GCS lock lease 对齐；SQL runner 参数注入必须强校验所有 `DECLARE p_* DEFAULT`，dry-run 必须预检可执行实验，禁止静默沿用 SQL 默认 `run_id` / `backtest_id`。Phase 2-4（portfolio-only 并发执行、08 ledger 并发、retrain 训练锁）仍待实现和验收；在当前约束下，本机本地多进程裸跑 SQL 仍被禁止，必须通过调度器 / 锁 / 状态表执行。“不并发”约束执行；只有状态表、GCS 原子锁、lease/heartbeat、调度器、写隔离、单实验 QA 和并发串号 QA 实现并验收后，才允许同阶段 portfolio-only / retrain 实验按配置并发。
