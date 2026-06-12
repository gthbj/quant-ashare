# PRD：dividend 日常采集与事件链路编排接入

> 状态：草案，待 Codex review 收敛后定稿。
> 范围声明：生产采集与编排变更——dividend endpoint 纳入每日 scheduled 采集、`dwd_stock_dividend_event` + `sql/qa/14` 接入每日 warehouse 刷新。涉及 manifest / Workflows YAML / readiness QA / 镜像重建与一次 live 验证。**不改 ledger / 策略语义、不改默认 `corporate_actions=none_v1`、不动其他 endpoint 行为、不动 Cloud Run job spec 资源与 IAM**。
> 关联：owner 2026-06-13 决策（dividend 进日常 scope + 编排接入）；PR #205（手工补采先例：manifest/endpoint group/契约已就绪）；PR #208（meta 0 行事故根因：`:latest` 执行时解析 + 代码-镜像空窗，镜像纪律据此设计）；DECISION-20260612-03（CA-on 纪律使事件新鲜度成为运营依赖）；KNOWN_CONSTRAINTS dividend 过渡政策条款（本 PRD 落地后改写）。

---

## 1. 背景

DECISION-20260612-03 要求后续所有实验 CA-on，`qa_corporate_action_ledger_outputs` 的 staleness 断言（QA-CA-LEDGER-0）已守门"`predict_end` ≤ 事件可见上界"。当前 dividend 数据靠手工补采（PR #205 的 `dividend_backfill` endpoint group + runbook），意味着每次实验窗口推进都需要人工补采——运营成本随实验频率线性增长。本 PRD 把链路日常化：每日 scheduled 采集 dividend 分区 → 每日刷新事件 DWD 与 QA → staleness 断言长期自动满足。

已就绪的基础（PR #205）：`configs/ingestion/ods_dividend_backfill_v0.yml`、`scripts/ingestion/endpoints/corporate_actions.py`（endpoint group `dividend_backfill`）、`configs/ingestion/schema_contracts/dividend.json`、`request_date_param=ex_date` 机制、canonical GCS 路径 `api=dividend/endpoint=dividend/partition_date=<ex_date>/`。

## 2. 设计

### 2.1 采集侧：dividend 进入每日 scheduled scope

1. 在 `configs/ingestion/ods_current_scope_v0.yml` 新增 dividend endpoint 条目（口径照搬 `ods_dividend_backfill_v0.yml`：`partition_date_semantics=business_date`、`business_date_field/request_date_param=ex_date`），归入 endpoint group **`corporate_actions`**（复用既有 module `scripts.ingestion.endpoints.corporate_actions`）。
2. `run_ingestion_job.py`：`ENDPOINT_GROUPS` 新增 `corporate_actions` 正式组（dividend），`current_scope` alias 显式列表追加 `corporate_actions`（PR #205 把 alias 改为显式列表正是为此刻服务——本次是**有意**纳入，与当时排除 `dividend_backfill` 不矛盾；`dividend_backfill` 手工组保留用于历史补采）。
3. **语义辨析（review 重点）**：dividend 的 `partition_date == ex_date`，每日 scheduled run 以 `business_date=当日` 请求 `ex_date=当日`——采集的是"当日除权除息的事件"。已实施分红预案的 `ex_date` 公布通常早于除权日，但我们按 ex_date 分区只在除权日当天采到该事件，**事件可见上界 = 最近已采集的 ex_date 日**，与 staleness 断言的全表 MAX 口径一致；回看窗口缺口（如停采几天）用 `dividend_backfill` 手工组补。无需为 dividend 引入 ann_date 维度采集（Phase A 契约只消费 `div_proc='实施'` + ex_date，PIT 语义由 DWD 层保证）。
4. **readiness QA（`sql/qa/09`）**：dividend 注册为 **weak** endpoint（绝不进 blocking strong 清单）。特殊性：淡季交易日零事件是常态，API 空返回（`empty_return`）**不写 warning**——实现上把 dividend 加入"允许空返回不告警"的豁免清单（若 qa/09 无此机制则新增，措辞与既有 weak endpoint 警告语义区分）；非交易日不采（scheduled gate 已覆盖）。
5. meta：沿用 `IngestionStatusWriter`（PR #208 后已正常），`ingestion_partition_status.endpoint` 存 `dividend`。

### 2.2 转换侧：事件 DWD + QA 接入每日 warehouse 刷新

1. `ashare_warehouse_window_refresh`（`daily_current` 模式）在既有股票 DWD/DWS 窗口刷新成功后追加两步：
   - `sql/dwd/12_dwd_stock_dividend_event.sql` 全量重建（CTAS，当前 4.8 万行量级，秒级成本，不做窗口化）；
   - `sql/qa/14_corporate_action_event_checks.sql`（重建 mismatch 表 + ledger 消费视图 + 断言）。
2. **失败语义（review 重点）**：这两步为 **non-blocking weak 步骤**——失败写 `pipeline_task_status.status='failed'`（由既有 pipeline failure 告警报出），但**不阻断**主链其余部分也不使整个 run 失败（价格 DWD 是关键路径，事件链路失败的影响由 staleness 断言在消费端兜底）。Workflows 实现用既有的非致命分支模式；若现有 workflow 无该模式则实现"捕获-记录-继续"。
3. 顺序约束：qa/14 的 hfq 交叉校验依赖当日 `adj_factor`（已在 strong endpoint 主链先行），故两步置于 transform 链尾。
4. `backfill` 模式不自动跑事件链路（历史补采仍走手工 runbook，避免大区间重复重建）；`qa_only` 模式不跑（qa/14 有写副作用——mismatch 表与视图重建，违反 qa_only 只读约定）。

### 2.3 镜像与部署纪律（PR #208 根因的制度化）

1. 本 PRD 的 manifest / ingestion 代码变更合并后，**必须立即重建 ingestion 镜像**（`:latest`，沿用既有 Cloud Build 流程）并记录 digest——`:latest` 在执行时解析，不重建则改动静默不生效（即 PR #208 事故的反向形态：代码已合、镜像未建）。
2. 验证序列（实现 PR 合并后执行，证据贴 PR）：
   - 重建镜像 → `dividend_backfill` 组对最近一个开市日做一次手工 smoke（已有 runbook 路径）确认新镜像行为；
   - 下一个交易日 20:00 scheduled run 后核验：execution digest = 新镜像、`ingestion_run` 含 dividend 行（或 `empty_return`）、`v_ingestion_meta_missing` 无告警、warehouse refresh 的事件两步 task status 成功、`dwd_stock_dividend_event` 可见上界推进。
3. Workflows YAML 变更按既有 `deploy_workflows.sh` 部署（不触碰 full_rebuild 的 opt-in 约定）。

### 2.4 记忆与文档同步

- KNOWN_CONSTRAINTS dividend 过渡政策条款改写为日常化后的口径（保留手工补采作为缺口恢复路径）；`sql/README.md` 执行顺序注记更新（手工刷新 → 每日自动）。
- 运行手册：staleness 断言失败的恢复路径简化为"检查当日 pipeline 事件两步状态 → 必要时手工补采"。

## 3. 预登记验收

1. 全量 pytest + 既有 ingestion manifest 测试扩展（current_scope 含 corporate_actions、dividend_backfill 仍被排除在外的断言改为新口径）；
2. dry-run plan 显示 dividend 进入 current_scope 执行计划；qa/09 dry-run 编译通过；
3. live 验证按 §2.3.2 序列（第一个交易日即 2026-06-15 周一，与 PR #208 的 meta 验证窗口合并执行）；
4. 连续两个交易日 scheduled run 事件链路全绿后，本 PRD 收口。

## 4. 红线

不动 strong endpoint 清单与既有 14 endpoint 行为；qa_only 不得获得写副作用；事件两步失败不得阻断价格主链；不改 ledger / 默认 profile / staleness 断言语义；镜像重建不更新其他 job 的 pin。

> 文档维护：Claude Fable 5（2026-06-13）
