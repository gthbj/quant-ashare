# Cloud Composer 历史审计目录

> 文档维护：GPT-5 Codex（最近更新 2026-06-08）
>
> 状态：retired / audit-only

`ashare-composer` 已于 `2026-06-08` 删除。OQ-005 cutover 后，生产调度与编排入口已经固定为 `Cloud Scheduler + Cloud Workflows`，当前代码入口见 `orchestration/workflows/`。

本目录保留的目的只有三个：

1. 审计 2026-06-08 前最后一版 Composer 实现。
2. 对照 Workflows 迁移后的语义是否完整保留。
3. 在 owner 明确批准的极端回滚场景下，作为历史参考快照。

## 当前边界

以下事情不要再在本目录做：

- 不要把 `orchestration/composer/**` 当成当前生产部署面。
- 不要继续往 Composer DAG 里加新功能、修新入口或改新调度。
- 不要再执行基于 `ashare-composer` 环境的同步、pause、trigger 或运维命令。

以下事情仍然允许：

- 查历史 DAG 语义。
- 对照迁移前后的 task/status/gate/trigger 设计。
- 在审计文档、事故复盘、迁移回顾里引用这里的历史实现。

## 当前生产入口

调度/编排的现行权威路径是：

- `orchestration/workflows/README.md`
- `docs/prd/PRD_20260608_01_OQ005调度完全迁出Composer.md`

如果后续还要改生产调度，应只改 `orchestration/workflows/**`、相关 Cloud Run control-plane 代码和对应 runbook，不再改本目录。

## 保留的历史快照

| 文件 | 保留原因 | 当前状态 |
|---|---|---|
| `dags/ashare_common.py` | 最后一版 Composer shared helper 快照 | 历史保留，不再部署 |
| `dags/ashare_daily_pipeline_v0.py` | 迁移前单 DAG 生产流水线快照 | 历史保留，不再部署 |
| `dags/ashare_ods_ingestion_daily.py` | DAG 拆分阶段的 Composer ODS 入口快照 | 历史保留，不再部署 |
| `dags/ashare_warehouse_window_refresh.py` | DAG 拆分阶段的 Composer warehouse window refresh 快照 | 历史保留，不再部署 |
| `dags/ashare_warehouse_full_rebuild.py` | DAG 拆分阶段的 Composer full rebuild 快照 | 历史保留，不再部署 |
| `dags/ashare_pipeline_alert_checker.py` | DAG 拆分阶段的 Composer alert checker 快照 | 历史保留，不再部署 |

## 历史语义摘要

在最后一版 Composer 实现里，职责边界是：

| DAG | 历史职责 |
|---|---|
| `ashare_ods_ingestion_daily` | 当前 14 个 ODS endpoint 采集、非交易日 gate、ODS readiness，真实写入成功后触发窗口刷新 |
| `ashare_warehouse_window_refresh` | `daily_current` / `backfill` 的 DIM/DWD/DWS 窗口刷新、metadata 恢复、窗口 QA 和只读 QA |
| `ashare_warehouse_full_rebuild` | 显式确认后的 DIM/DWD/DWS 全量维护重建 |
| `ashare_pipeline_alert_checker` | 查询观测视图，写 Cloud Logging 告警和 heartbeat |
| `ashare_daily_pipeline_v0` | 更早期的单 DAG 生产入口；已被拆分 DAG 方案取代 |

`ashare_meta.pipeline_run` / `ashare_meta.pipeline_task_status`、非交易日 skip、ODS parent -> warehouse child、window QA、alert checker heartbeat 等语义，已经在 Workflows 路径重新落地；本目录只保留它们的 Composer 时代实现快照。

## 为什么不再保留历史操作命令

此前 README 里包含过 Composer bucket 同步、Airflow Variables、手工 trigger 示例等命令。现在这些内容被主动删掉，原因是：

1. `ashare-composer` 环境已经不存在，命令默认不可执行。
2. 保留这类命令会误导后续维护者把本目录当成当前生产 runbook。
3. 真要做受控回滚，应把“重建 Composer”视为新的架构决策，并重新评估 IAM、bucket、DAG 同步和告警链路，而不是复制旧命令直接执行。

如需恢复更细的历史命令，请从 git 历史读取本文件在 `2026-06-08` 之前的版本，不要把这些命令重新写回当前 README。
