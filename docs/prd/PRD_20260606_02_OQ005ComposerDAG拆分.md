# PRD: OQ-005 Composer DAG 拆分方案

> 文档维护：GPT-5 Codex（最近更新 2026-06-06）
> 状态：Draft，待实现。
> 范围声明：本文只定义 Composer DAG 拆分与迁移方案，不实现代码、不部署 Composer、不运行 BigQuery / Dataform / Cloud Run。

## 1. 背景

OQ-005 生产调度已经完成 current-scope ODS 采集、ODS readiness、DWD/DWS 20 交易日窗口刷新、非交易日 skip gate、告警/观测和 checker heartbeat。当前主入口 `ashare_daily_pipeline_v0` 同时承载每日采集、ODS readiness、窗口刷新、全量兼容路径、`qa_only`、ADS 契约初始化、非交易日 gate、状态回写和告警衔接。

随着后续 Dataform definitions、补跑 / resume 自动化、策略 runner / report 可选分支继续接入，单 DAG 会继续膨胀。调度职责需要按生产采集、数仓刷新、全量维护和研究实验拆分，使每条 DAG 的触发方式、参数、状态、失败恢复和告警语义都保持清晰。

## 2. 目标

1. 将 `ashare_daily_pipeline_v0` 的职责拆成多个单一边界 DAG。
2. 保持现有生产能力：每日只采当前实际消费的 14 个 ODS endpoint，开市日写 GCS Parquet，非交易日自动 skip，ODS readiness 继续作为下游门禁。
3. 将每日生产采集与 DIM/DWD/DWS 窗口刷新解耦，允许 ingestion 成功后触发 warehouse refresh，也允许手工触发 backfill。
4. 将全量重建从日更 DAG 中移出，变成显式手工维护 DAG。
5. 将研究实验 DAG 与生产数仓 DAG 分离，避免实验 runner / report 逻辑污染每日生产调度。
6. 保留 `oq005_alert_checker` 独立运行，不并入生产 DAG。
7. 继续使用 `ashare_meta.pipeline_run` / `ashare_meta.pipeline_task_status` 作为统一观测事实表，必要时补充跨 DAG 链路字段。

## 3. 非目标

1. 不改变 ODS、DIM、DWD、DWS、ADS 表结构和业务口径。
2. 不改变策略模型训练方法、回测口径、report artifact 结构。
3. 不在本 PRD 中迁移到 Dataform；本文只定义 Dataform 可接入的 DAG 边界。
4. 不新增 ODS endpoint；每日生产采集仍仅覆盖当前实际消费范围。
5. 不要求本地多进程裸跑 SQL；所有生产任务仍通过 Composer / Cloud Run / BigQuery / Dataform 等受控入口执行。

## 4. 目标 DAG

| DAG | 调度方式 | 职责 | 明确不负责 |
|---|---|---|---|
| `ashare_ods_ingestion_daily` | 每日 20:00 Asia/Shanghai scheduled；支持手工 smoke | 生产采集 + ODS readiness；交易日 gate；Cloud Run ingestion；readiness strong/weak gate；写 ingestion / pipeline 状态 | 不执行 DIM/DWD/DWS/ADS 写入；不执行全量重建；不跑研究实验 |
| `ashare_warehouse_window_refresh` | 由 ingestion DAG 成功触发；支持手工 backfill / qa smoke | `daily_current` / `backfill` 的 DIM/DWD/DWS 窗口刷新；metadata 恢复；窗口 QA；P0 只读 QA 门禁 | 不采集 ODS；不执行全量 CTAS；不执行策略 runner / report |
| `ashare_warehouse_full_rebuild` | 手工触发，默认无 schedule | 维护型全量重建；显式确认后重建 DIM/DWD/DWS；跑 P0 / 策略 / OQ QA | 不被每日调度自动触发；不执行 ODS 采集；不跑研究实验 |
| `ashare_research_model_experiment` | 手工触发 | 单次策略研究实验；读取已冻结或可复用数据；写 ADS 实验产物、报告、诊断和 QA 状态 | 不写生产 DIM/DWD/DWS；不负责每日 ODS readiness |
| `ashare_research_model_fanout` | 手工触发 | 批量候选搜索 / fan-out；控制候选并发；写 ADS 搜索产物、报告、诊断和 QA 状态 | 不写生产 DIM/DWD/DWS；不触发生产日更 |
| `oq005_alert_checker` | 每 10 分钟 scheduled | 查询观测视图，写 Cloud Logging 业务告警和 heartbeat | 不编排生产任务 |

## 5. 生产链路

### 5.1 每日开市日链路

```text
ashare_ods_ingestion_daily
  -> non_trading_day_gate
  -> Cloud Run: ashare-ingest-current-scope
  -> sql/qa/09_ods_daily_partition_readiness.sql
  -> ODS ready dataset / trigger: ashare_warehouse_window_refresh

ashare_warehouse_window_refresh
  -> windowed_dim
  -> sql/incremental/01_refresh_stock_dwd_dws_window.sql
  -> sql/qa/10_windowed_stock_refresh_checks.sql
  -> P0 / strategy1 / OQ004 / finance / OQ006 QA
  -> pipeline_finalize_status
```

`ashare_ods_ingestion_daily` 在开市日成功后触发 `ashare_warehouse_window_refresh`，并传入 `business_date`、`date_to`、`source_pipeline_run_id`、`warehouse_mode='daily_current'`、`transform_backend`、`pipeline_dry_run=false` 等参数。窗口刷新 DAG 使用自己的 `pipeline_run_id`，并记录上游 ingestion run 以便排查全链路。

P0 优先使用 Airflow Datasets / data-aware scheduling 表达 “ODS ready -> warehouse refresh” 的数据驱动触发关系；如果 Composer 版本或运行约束暂时阻塞，可使用 `TriggerDagRunOperator` 作为过渡，但不能是无观测的 fire-and-forget：必须写入 `upstream_pipeline_run_id`，并由 watchdog 检查 ingestion success 后 warehouse refresh 是否按时启动 / 成功。

### 5.2 非交易日链路

scheduled `ashare_ods_ingestion_daily` 在非交易日执行 `non_trading_day_gate`，写入 `skip_non_trading_day` 状态行，然后结束。该 DAG 不触发 Cloud Run，不触发 ODS readiness，不触发 warehouse refresh。日历缺行或 `is_open` 为空时 fail-closed。

### 5.3 手工 backfill 链路

手工触发 `ashare_warehouse_window_refresh`，传入 `warehouse_mode='backfill'`、`date_from`、`date_to`。backfill 不自动触发 ODS ingestion；执行前由 owner 或运行手册确认对应 ODS 分区已经可读，并由 readiness / QA 兜底阻断缺失。

### 5.4 全量重建链路

手工触发 `ashare_warehouse_full_rebuild`，必须传入 `confirm_full_rebuild=true` 和明确日期范围。该 DAG 负责维护型全量 CTAS / Dataform 全量 invocation，不允许 scheduled 自动运行。全量重建完成后跑 P0 / 策略 / OQ QA，并写入独立 `pipeline_run`。

既有 `warehouse_mode=full_rebuild` / `full_rebuild_compat` 语义迁移到该 DAG。迁移期若仍存在 legacy `ashare_enable_full_refresh=true` 入口，只能映射为手工维护语义 `full_rebuild_compat`，并记录到状态表；旧 DAG 暂停后，该 legacy 开关随旧 DAG 一并退役。

### 5.5 研究实验链路

研究 DAG 只读生产 DWS / ADS 契约输入，写入按 `run_id` / `backtest_id` / `search_id` 隔离的 ADS 和 GCS artifact。研究 DAG 不作为每日生产 DAG 的下游，也不阻塞 ODS→DWS 生产日更。

## 6. 参数契约

### 6.1 `ashare_ods_ingestion_daily`

| 参数 | 默认值 | 说明 |
|---|---|---|
| `business_date` | scheduled run 使用 `data_interval_end` 的 Asia/Shanghai 日期；手工 conf 可覆盖 | 采集业务日 |
| `pipeline_dry_run` | Airflow Variable fallback；conf 可覆盖 | dry-run 时不写 GCS / meta |
| `skip_ingestion` | `false` | 只读 readiness smoke 使用 |
| `force_non_trading_day_gate` | `false` | smoke hook，用于手工验证非交易日 gate |
| `run_label` | `daily_ingestion` | 写入 `pipeline_run.run_label` |

### 6.2 `ashare_warehouse_window_refresh`

| 参数 | 默认值 | 说明 |
|---|---|---|
| `warehouse_mode` | `daily_current` | 沿用现有状态字段语义，只允许 `daily_current` 或 `backfill` |
| `business_date` | conf 传入；缺省用触发日期 | daily_current 业务日 |
| `date_from` / `date_to` | daily_current 自动计算；backfill 必填 | 写入窗口 |
| `lookback_trading_days` | `20` | daily_current 默认回填当前日往前 20 个交易日 |
| `source_pipeline_run_id` | ingestion 触发时传入 | 上游采集 run 追踪 |
| `transform_backend` | `bq_sql` | 后续可切换 `dataform` |
| `pipeline_dry_run` | `false` | dry-run 不写目标表 |

### 6.3 `ashare_warehouse_full_rebuild`

| 参数 | 默认值 | 说明 |
|---|---|---|
| `confirm_full_rebuild` | 必须显式为 `true` | 全量重建保护门 |
| `date_from` / `date_to` | 必填 | 重建范围或审计范围 |
| `transform_backend` | `bq_sql` | 后续可切换 `dataform` |
| `run_label` | `manual_full_rebuild` | 写入状态表 |

### 6.4 研究 DAG

| DAG | 关键参数 |
|---|---|
| `ashare_research_model_experiment` | `experiment_id`、`run_id`、`prediction_run_id`、`backtest_id`、`manifest_path`、`force_replace`、`resume` |
| `ashare_research_model_fanout` | `search_id`、`manifest_path`、`candidate_count`、`candidate_parallelism`、`max_parallel_backtest`、`force_replace`、`resume` |

## 7. 状态与观测

P0 继续复用现有 `ashare_meta.pipeline_run` 和 `ashare_meta.pipeline_task_status`，并补齐跨 DAG 血缘：

1. 每个 DAG run 生成独立 `pipeline_run_id`。
2. `dag_id` 固定为目标 DAG 名，观测视图按 `dag_id` 区分任务类型。
3. `warehouse_mode` 在 ingestion DAG 中固定为空或 `not_applicable`，不再承担 downstream mode 分支。
4. `warehouse_mode` 在 warehouse DAG 中记录 `daily_current`、`backfill`、`full_rebuild`。
5. `transform_backend` 在 warehouse DAG 中记录 `bq_sql` 或 `dataform`。
6. `upstream_pipeline_run_id` 必须记录由哪个 ingestion run 触发 warehouse refresh。
7. `pipeline_task_status` 继续记录 Cloud Run execution ID、BigQuery job ID、Airflow log URL、error message 和 terminal status。

P0 新增字段：

| 字段 | 表 | 用途 |
|---|---|---|
| `upstream_pipeline_run_id` | `pipeline_run` | 记录由哪个 ingestion run 触发 warehouse refresh |
| `triggered_by_dag_id` | `pipeline_run` | 跨 DAG 血缘 |

P1 建议补充可选字段：

| 字段 | 表 | 用途 |
|---|---|---|
| `data_interval_start` / `data_interval_end` | `pipeline_run` | scheduled run 审计 |
| `task_attempt` | `pipeline_task_status` | 更清晰地区分 Airflow retry |

跨 DAG 缺失检测是 P0：观测视图或 `oq005_alert_checker` 必须检查 “ingestion run succeeded，但指定时间内没有对应 `upstream_pipeline_run_id` 的 warehouse refresh running / succeeded” 的情况，并写入业务告警。默认检测窗口建议为 ingestion terminal success 后 60 分钟，可在部署 smoke 后按实际运行耗时调整。

`daily_current` 默认刷新最近 20 个交易日，因此单日 warehouse refresh 丢失且 ODS 已采集成功时，次日 refresh 会覆盖上一日窗口；这能降低数据长期缺口风险，但不能替代 refresh-missing watchdog。

## 8. 代码组织要求

1. Composer DAG 文件按职责拆分到 `orchestration/composer/dags/`：
   - `ashare_ods_ingestion_daily.py`
   - `ashare_warehouse_window_refresh.py`
   - `ashare_warehouse_full_rebuild.py`
   - `ashare_research_model_experiment.py`
   - `ashare_research_model_fanout.py`
   - `oq005_alert_checker.py` 保持独立
2. 抽取共享 helper 到 `orchestration/composer/dags/ashare_common.py` 或同级包，复用：
   - conf 参数读取和类型转换
   - `business_date` / `data_interval_end` 口径
   - pipeline status upsert
   - BigQuery SQL task 封装
   - Cloud Run execution 链接记录
   - Airflow log URL 生成
3. SQL 文件继续放在 Composer bucket `data/sql/`，不放进 `dags/sql/`。
4. 新 DAG import 必须轻量，不在模块顶层读取 Airflow Variable 或访问 GCP API。
5. 新 DAG 必须保留 `pipeline_dry_run`、manual smoke 和 fail-closed 行为。

## 9. 迁移顺序

### Phase A: PRD 与状态同步

新增本文档，同步 `TODO.md` 与 `.agent/memory/`。本阶段不改 DAG 代码。

### Phase B: 抽共享 helper

从 `ashare_daily_pipeline_v0.py` 抽出状态回写、日期计算、参数解析、Cloud Run / BigQuery 任务构造 helper。该阶段保持旧 DAG 行为不变，并用 `py_compile` / DAG import 检查确认无回归。Phase B 的零回归验证是 Phase C 的硬前置；helper 未稳定前不得并行铺新 DAG。

### Phase C: 新增 `ashare_ods_ingestion_daily`

复制并收敛当前 ingestion + readiness + non-trading gate 逻辑。完成 smoke：

1. scheduled-equivalent 开市日 smoke：触发 Cloud Run current-scope，readiness 通过。
2. `force_non_trading_day_gate=true` smoke：写 `skip_non_trading_day` 状态，Cloud Run 未触发。
3. `skip_ingestion=true` smoke：只跑 readiness。

### Phase D: 新增 `ashare_warehouse_window_refresh`

迁移 `daily_current` / `backfill` 窗口刷新、metadata、窗口 QA 和只读 QA。完成 smoke：

1. 手工 backfill `2026-06-03..2026-06-04` 通过。
2. ingestion DAG 成功后通过 dataset 或 trigger 自动触发 `warehouse_mode='daily_current'`。
3. 最近 20 个交易日 ODS daily_basic → DWD valuation → DWS valuation 行数一致。
4. refresh-missing watchdog 可识别人工构造的 “ingestion success 但下游未启动” 场景。

### Phase E: 新增 `ashare_warehouse_full_rebuild`

迁移全量维护路径，增加 `confirm_full_rebuild=true` 保护。完成 smoke：

1. 未传确认参数时 fail-closed。
2. dry-run 展开计划，不执行真实 DML。
3. owner 明确批准后再执行一次受控全量维护验证。

### Phase F: 退役旧 DAG

新 production DAG 连续通过至少两个开市日 scheduled run 和一个非交易日 skip smoke 后，暂停 `ashare_daily_pipeline_v0`。暂停后保留一个 release cycle 作为回滚参考，再删除或标记 deprecated。

### Phase G: 拆研究 DAG

将策略研究单实验和 fan-out 搜索从生产 DAG 之外独立成手工 DAG。研究 DAG 接入时必须复用已有 run status / lock / artifact 隔离要求，不得写生产 DIM/DWD/DWS。

## 10. QA 与验收

P0 验收条件：

1. 新 DAG 均通过 Python import / `py_compile`。
2. Composer 无 DAG import error。
3. `ashare_ods_ingestion_daily` 开市日 scheduled-equivalent smoke 成功写入 ODS current-scope 分区，并通过 `09_ods_daily_partition_readiness.sql`。
4. `ashare_ods_ingestion_daily` 非交易日 smoke 写入 `skip_non_trading_day` 状态，且 Cloud Run execution 未新增。
5. `ashare_warehouse_window_refresh` 手工 backfill 小窗口通过 `10_windowed_stock_refresh_checks.sql`。
6. ingestion DAG 成功触发 warehouse refresh 后，两个 DAG 的 `pipeline_run` 均可在观测视图中追踪。
7. `daily_current` 仍默认覆盖当天往前 20 个交易日，估值链路 QA-WIN-16/17/18 通过。
8. `ashare_warehouse_full_rebuild` 未显式确认时 fail-closed。
9. ingestion success 后若 warehouse refresh 缺失，watchdog 能在约定窗口后产生日志 / 告警证据。
10. `oq005_alert_checker` 继续每 10 分钟运行，heartbeat 和 absence policy 不受 DAG 拆分影响。
11. `ashare_daily_pipeline_v0` 暂停后，不再出现同一业务日新旧 DAG 双写。

## 11. 风险与控制

| 风险 | 控制 |
|---|---|
| 新旧 DAG 并存导致同一业务日重复写入 | 迁移期只允许一个 production scheduled DAG active；旧 DAG 暂停前先完成新 DAG smoke |
| ingestion 成功但 warehouse refresh 未触发 | P0 用 Airflow Datasets 或受控 trigger 触发；`upstream_pipeline_run_id` 写入状态；watchdog 检测 refresh missing |
| 跨 DAG 状态链路不完整 | P0 增加结构化 `upstream_pipeline_run_id` / `triggered_by_dag_id` 字段；观测视图按链路聚合 |
| helper 抽取造成旧 DAG 回归 | Phase B 先只抽 helper，不改行为；保留旧 DAG smoke |
| Dataform 接入时参数语义漂移 | `transform_backend` 显式记录，`daily_current` / `backfill` 参数契约固定 |
| full rebuild 误触发 | 单独 DAG、无 schedule、必须 `confirm_full_rebuild=true` |
| 研究实验影响生产日更 | 研究 DAG 手工触发，禁止写生产 DIM/DWD/DWS |

## 12. 与既有文档关系

1. `docs/prd/PRD_20260603_03_GCP数据流水线方案.md` 仍是 GCP 总体目标架构。
2. `docs/prd/PRD_20260605_01_OQ005剩余调度链路.md` 仍是 ODS→ADS 生产链路能力清单；本文补充 Composer DAG 拆分后的执行边界。
3. `orchestration/composer/README.md` 在实现时需要更新为多 DAG 运行手册。
4. `docs/OQ005-Pipeline-补跑与故障恢复-Runbook.md` 在实现时需要按新 DAG 名称改写触发命令和排障入口。
5. `.agent/memory/ARCHITECTURE_MEMORY.md` 需要记录多 DAG 目标边界，避免后续继续把新能力塞回 `ashare_daily_pipeline_v0`。

## 13. 下一步

1. 合并本文 PRD 后，先实现 Phase B/C/D：抽共享 helper，新增 `ashare_ods_ingestion_daily` 和 `ashare_warehouse_window_refresh`。
2. 生产 DAG 拆分 smoke 通过后，再实现 `ashare_warehouse_full_rebuild`。
3. 研究 DAG 拆分放在生产 DAG 稳定之后；Cloud Run Python baseline 搜索仍按现有手工 / orchestrator 路线推进。
4. Dataform definitions 接入前，先完成 production DAG 边界拆分，减少后续迁移时的参数和状态耦合。
