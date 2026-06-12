> 文档维护：Claude Fable 5（最近更新 2026-06-12）

# PRD：BigQuery 数据集清理与退役（轻量）

> 状态：草案，待 Codex review 收敛后定稿。
> 范围声明：按 owner 2026-06-12 决策清理 `data-aquarium` 项目中的遗留/冗余 BigQuery 对象：遗留数据集 `ashare` 整库硬删除、windowed equivalence QA 工具退役（脚本 + scratch 数据集）、`ads_ml_training_panel_daily` BQML 旧 run 面板行裁剪。不改任何策略语义、不动 research/promotion 链路、不触碰回测事实表。
> 关联：2026-06-12 全数据集盘点（11 个数据集逐表 + 契约比对 + 作业审计 + 对抗复核，结论见 `.agent/memory/IMPLEMENTATION_STATUS.md` 2026-06-12 小节）；`DECISION-20260612-01`；KNOWN_CONSTRAINTS「窗口等价 QA」与「true-five-year overlap parity」条款（本 PRD 将改写）。

---

## 1. 背景

2026-06-12 盘点结论：`ashare_dim` / `ashare_dwd` / `ashare_dws` / `ashare_ads` / `ashare_research` 与 `sql/` 契约**双向零差异**，核心分层不乱；杂物集中在周边——

| 对象 | 现状（盘点事实） |
|---|---|
| 数据集 `ashare`（无后缀） | 旧代仓库孤儿：118 个对象（69 native 表 + 48 外部表 + 1 个 BQML model `bqml_ml_stock_picker_baseline`），250.4 GiB，`last_modified` 全部停在 2026-05-23~25；全仓代码/SQL/配置/文档零引用（仅 Artifact Registry 同名 Docker 仓库路径，与 BigQuery 数据集无关）；`INFORMATION_SCHEMA.JOBS_BY_PROJECT` 近 14 天仅 owner 盘点自身的 3 条 SELECT |
| `ashare_qa_windowed_equivalence` | windowed equivalence QA 的 scratch 数据集；18 张 shadow 残留表已于 2026-06-12 先行删除（owner 批准的第 1 类清理），现为空数据集 |
| `scripts/qa/` 两个 QA 脚本 | `run_windowed_refresh_equivalence.py` / `run_index_market_windowed_equivalence.py`，scratch 数据集名为脚本内默认值；PRD_06 宽窗口 parity 验收（2026-06-11）已完成，工具使命结束 |
| `ads_ml_training_panel_daily` | 692.9 GB / 221,450,285 行 / 73 个 run；其中 `run_id LIKE 's1_bqml%'` 的 BQML 旧 run 共 12 个、36,853,582 行（约 115 GB），全部早于 owner 2026-06-05「BQML 仅作 reference/audit」决策 |
| `ashare_meta._repair_val_*` | 5 张 2026-06-04 schema repair 泄漏外部表，已于 2026-06-12 先行删除（第 1 类清理） |

另：盘点顺带发现 `ashare_meta.ingestion_run` / `ingestion_partition_status` 自建表以来 0 行、与 live 采集成功记录矛盾（疑似采集镜像 stale，采集级告警静默）。该问题**不在本 PRD 范围**，已作为独立排查任务挂出。

## 2. owner 已定决策（2026-06-12，记入 DECISION-20260612-01）

1. 遗留数据集 `ashare` **硬删除**（不导出、不归档；接受其中 BQML model `bqml_ml_stock_picker_baseline` 无恢复路径——time travel 不覆盖 model）。
2. `ashare_qa_windowed_equivalence` **硬删除，数据集也删**；两个 windowed equivalence QA 脚本删除，所有引用与标注一并处理。
3. `ashare_meta.tushare_api_catalog` / `tushare_api_params` **保留不删**。
4. 其余按 2026-06-12 评估建议执行：`ads_ml_training_panel_daily` 裁剪 BQML 旧 run 面板行；50 个 BQML model、`ads_model_prediction_daily`、全部回测事实表、`ashare_backup`、ODS 43 张 scope 外外部表均**不动**。

## 3. 目标（三个独立 Phase）

### Phase A：遗留数据集 `ashare` 硬删除

1. **删除前预检（唯一硬门）**：查 Data Access 审计日志（BigQueryAuditMetadata），lookback ≥ 30 天，过滤数据集 `ashare` 的读取事件，例如：
   `gcloud logging read 'protoPayload.serviceName="bigquery.googleapis.com" AND protoPayload.resourceName:"datasets/ashare/"' --freshness=30d --project=data-aquarium`
   （`JOBS_BY_PROJECT` 看不到其他 billing project 发起的跨项目查询，审计日志补此盲区。）判定规则：除 owner 账号与本次盘点作业外出现**任何其他 principal / 项目**的读取 → 暂停，报 owner 后再决定。
2. 删除：`bq rm -r -f -d data-aquarium:ashare`，记录精确 UTC 时间戳。
3. 回滚窗口：该数据集 `maxTimeTravelHours=168`，删除后 7 天内可 `UNDROP SCHEMA`（同名数据集不得重建，否则 undrop 失败）；过窗后仅剩 7 天 fail-safe（需 Google 支持工单），再之后永久不可恢复。BQML model 不受 time travel 保护，删除即不可恢复（owner 已接受）。
4. 边界说明：48 张外部表删除只移除 BigQuery 元数据，**其背后 GCS 文件不属于本 PRD**（旧仓 GCS 存量盘点列入 §9 后续建议）；Artifact Registry 中同名 Docker 仓库 `ashare`（`asia-east2-docker.pkg.dev/data-aquarium/ashare/*`）是生产采集镜像仓库，**严禁误删**。

### Phase B：windowed equivalence QA 退役（代码 + 数据集）

代码改动（实现 PR 范围）：

1. 删除 `scripts/qa/run_windowed_refresh_equivalence.py` 与 `scripts/qa/run_index_market_windowed_equivalence.py`（`scripts/qa/` 仅此两文件，目录一并移除）。在本 PRD 定稿 commit 中记录两脚本最后所在 commit（即实现 PR 的 parent），作为未来 git history 恢复入口。
2. `tests/strategy1/test_true5y_prd06_contracts.py`：移除对两脚本的契约用例（约 :101 / :122 / :134 三处），保留 `13_true5y` SQL 契约用例。
3. `sql/README.md`：移除 windowed equivalence 运行示例段（约 :105-115）。
4. `docs/策略1CloudRun训练回测运行手册.md` :118：true-five-year refit 前置从「两个 equivalence QA 脚本 + 13」改写为「`sql/qa/13_true5y_historical_coverage_checks.sql` + 逐年 refit panel coverage QA」，并注明 parity 工具已退役、历史验收记录见 IMPLEMENTATION_STATUS（2026-06-11 小节）。
5. `configs/strategy1/active_step_catalog.yml`：`retired_reference_lint.banned_active_refs` 增加 `scripts/qa/run_windowed_refresh_equivalence` 与 `scripts/qa/run_index_market_windowed_equivalence` 两个路径引用，防止 active scope 回流。
6. **KNOWN_CONSTRAINTS 两处条款改写**（这是本 Phase 的实质决策影响，review 重点）：
   - 工程约束 OQ-005 条目中「窗口 SQL 与 canonical full SQL 双实现并存期间，发布前或定期必须运行 `scripts/qa/run_windowed_refresh_equivalence.py` …等价 QA 必须校验 `build_start_date` 足够早…」→ 改写为：parity 工具已于 2026-06-12 按 DECISION-20260612-01 退役；窗口刷新正确性此后依赖 `sql/qa/10_windowed_stock_refresh_checks.sql` 窗口 QA 与发布前 review；如未来再次大规模重写历史窗口需要 full/window parity，从 git history 恢复脚本并另行评估。
   - true-five-year 条目中「后续任何 true-five-year refit / continuous 重跑仍必须先通过 stock/index/market overlap parity、`13_true5y`…」→ overlap parity 改为「2026-06-11 已一次性验收完成（stock 9 表 `1e-8` 零 mismatch；index/market `1e-4` 零 mismatch），工具已退役」，后续重跑硬门收敛为 `13_true5y` + 逐年 refit panel coverage QA。
7. `.agent/memory/ARCHITECTURE_MEMORY.md` 中 OQ-005 Phase 2.2 对该脚本的描述补退役注记（历史叙述保留）。

BigQuery 操作（实现 PR 合并后执行）：

8. 删除数据集：`bq rm -r -f -d data-aquarium:ashare_qa_windowed_equivalence`，记录时间戳（7 天 UNDROP 窗口同上；当前已为空数据集，风险极低）。

### Phase C：`ads_ml_training_panel_daily` BQML 旧 run 面板行裁剪

1. **裁剪口径**（与「BQML 仅作 reference/audit」决策一致）：只删**可由 DWS + 已归档 SQL 确定性重建**的训练面板行；模型评分、组合与成交等**不可重建的实验事实全部保留**——即 `ads_model_registry`（151 行，其中 52 行 s1_bqml 引用）、`ads_model_prediction_daily`（含 9 个 s1_bqml run）、candidate / target / order / trade / position / NAV / summary、50 个 BQML model 均不动。
2. 删除前留证：`SELECT run_id, COUNT(*) ... WHERE trade_date >= '2000-01-01' GROUP BY run_id` 全量快照存档（贴实现 PR comment）。
3. 执行（注意表为 `trade_date` 月分区 + `require_partition_filter` + cluster `(run_id, sec_code)`，DELETE 必须带全范围分区过滤）：
   ```sql
   DELETE FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
   WHERE trade_date >= DATE '2000-01-01'
     AND run_id LIKE 's1_bqml%';
   ```
4. 预期账目：删除 12 个 run / 36,853,582 行（约 115 GB）；剩余 61 个 run / 184,596,703 行。
5. 回滚窗口：DML 后 7 天内可 `FOR SYSTEM_TIME AS OF` 恢复；过窗永久。

## 4. 非目标（明确不动）

- `ashare_research` 全部 15 张表；`ashare_ods` 57 张外部表（含 43 张当前 scope 外——P1 行业/资金/事件特征扩展的潜在输入，BQ 侧 0 字节）；`ashare_backup`（长期审计快照，0.6 MB）；`gcp_billing`。
- `tushare_api_catalog` / `tushare_api_params`（owner 决策保留）。
- 不做数据集 labels / default expiration 治理、不动 dataform `ashare_dataform` 配置、不做 GCS raw 存量盘点（见 §9）。
- 不改任何策略代码、运行路径、默认 profile；不涉及 promotion / acceptance。

## 5. 执行顺序与角色

1. 本 PRD 经 Codex review 收敛 → 定稿。
2. 实现 PR（Phase B 代码 / 文档 / 约束 / 记忆改写）→ Claude review → 合并。
3. 合并后按 §3 顺序手工执行 BigQuery 操作：Phase A 预检 + 删库、Phase B-8 删数据集、Phase C 留证 + DML；三者相互独立，可同日完成。每步删除记录 UTC 时间戳与前后对账证据，贴实现 PR comment 并写入 handoff。
4. 验收通过后更新记忆收尾（§8）。

## 6. 验收标准

| 项 | 要求 |
|---|---|
| Phase A | 审计日志预检结果留档（无未知消费方，或已报 owner 裁决）；`bq show data-aquarium:ashare` 返回 Not found；删除时间戳留档 |
| Phase B 代码 | 两脚本及 `scripts/qa/` 目录删除；retired linter 含两路径且 `lint_retired_references()==[]`；全量 pytest 通过；全仓 grep 两脚本路径在 active scope 零引用（历史文档/archive 除外）；KNOWN_CONSTRAINTS / runbook / README / catalog 同步完成 |
| Phase B 数据集 | `bq show data-aquarium:ashare_qa_windowed_equivalence` 返回 Not found |
| Phase C | `run_id LIKE 's1_bqml%'` 计数 = 0；其余 61 个 run 行数与删除前快照逐一相等；`ads_model_registry` 仍 151 行、52 行 s1_bqml 引用完整；`bq ls -m` 仍 50 个 model；`ads_model_prediction_daily` 行数不变 |
| 记忆同步 | IMPLEMENTATION_STATUS / AGENT_HANDOFF / TODO 更新；KNOWN_CONSTRAINTS 改写随实现 PR 提交 |

## 7. 风险与控制

| 风险 | 控制 |
|---|---|
| `ashare` 存在盘点未见的跨项目消费方 | Phase A 审计日志预检为硬门（补 `JOBS_BY_PROJECT` 跨 billing project 盲区）；发现任何未知 principal 即暂停报 owner |
| 删错对象（同名 Docker 仓库 / `ashare_*` 前缀误匹配） | 操作只用全限定 `data-aquarium:ashare` 数据集 ID；PRD 显式标注 Artifact Registry 同名仓库禁删 |
| equivalence QA 退役后窗口刷新失去 parity 兜底 | KNOWN_CONSTRAINTS 显式改写（不是静默失效）：日常正确性由窗口 QA `10` 承担；大规模历史重写场景要求从 git history 恢复脚本另行评估；恢复入口 commit 记录在案 |
| Phase C 误删非 BQML run 行 | 删除条件仅 `run_id LIKE 's1_bqml%'`；删除前后 run 级行数快照逐一对账为硬验收 |
| 误把 prediction / 回测事实当"可重建"删掉 | §3-C-1 裁剪口径白名单式列出唯一删除对象：`ads_ml_training_panel_daily` 一张表 |
| 7 天反悔窗口被错过 | 每步删除记录时间戳；验收对账在删除当日完成，发现异常立即 UNDROP / time travel 恢复 |

## 8. 记忆与文档同步

- 实现 PR：随代码同步改 `KNOWN_CONSTRAINTS.md`（§3-B-6 两处）、`ARCHITECTURE_MEMORY.md` 注记、`TODO.md` 勾选、`AGENT_HANDOFF.md` 交接。
- BigQuery 操作完成后：`IMPLEMENTATION_STATUS.md` 记录三个 Phase 的执行时间戳、对账结果与回滚窗口截止日。

## 9. 后续建议（不在本 PRD 范围，owner 另行决策）

1. 数据集治理：11 个数据集统一补 labels；scratch / backup 类数据集设 default table expiration。
2. dataform 盲区：`workflow_settings.yaml` 的 `defaultDataset=ashare_dataform` 在 live 不存在，切换 dataform backend 前需先决策该数据集的创建与纳管。
3. ODS 契约盲区：当前 scope 14 张外部表中 12 张的 `CREATE EXTERNAL TABLE` DDL 不在版本库，建议补齐入库。
4. 旧仓 GCS 存量：`ashare` 外部表背后的 GCS Parquet 与 ODS raw bucket 的 lifecycle 策略未盘点，真正的存储成本在 GCS 而非 BQ 外部表。
