# PRD：Strategy1 包结构 Phase E 收尾（src ↔ scripts 依赖方向翻正）

> 状态：草案，待 Codex review 收敛后定稿。
> 范围声明：纯代码搬移与 shim 回填，**不改任何运行语义**；不动 Cloud Run job spec / args / 镜像 / IAM；不动两个大 orchestrator（`orchestrate_sklearn_native_search.py` / `orchestrate_annual_rolling_selection.py`，KNOWN_CONSTRAINTS 兼容层条款继续适用）。
> 关联：PRD_20260610_02（项目结构重构方案，本 PRD 是其 Phase C/E 既定目标的收尾实施）；DECISION-20260610-11（新增领域逻辑落 src、scripts 只作兼容入口）；2026-06-12 重构评估（owner 已采纳，四个评估维度独立命中本问题）。

---

## 1. 背景与问题

PRD_20260610_02 的目标态是「`src/quant_ashare/**` 是可独立安装、可测试的库代码，`scripts/**` 只保留 CLI / 兼容入口」。2026-06-10 的迁移把业务逻辑层（ledger / acceptance / sql_runner / dataset_roles / 五个 entrypoint）搬进了 src 并以 thin shim 回填 scripts——该模式已实跑验证 4+ 次。但基础设施层没迁，形成**依赖方向倒置**（`main@d45560d` 实测）：

- `src/quant_ashare/strategy1/` 的 **12/23 个模块、共 50 行** `from scripts.strategy1_cloudrun import ...`（`annual_pipeline_scheduler.py:23-52`、`pipeline_control.py:16-45`、`train_predict.py:36`、`prepare_matrix.py:17-28`、`reporting.py:12-13`、`acceptance.py:10-11`、`ledger.py:21` 等）。
- 被依赖的真实实现滞留 scripts：`bq_io.py`(227 行)、`config.py`(465+ 行)、`state.py`(528 行)、`feature_sets.py`(324 行)、`preprocess.py`(198 行)、`task_fanout.py`(164 行)、`training_panel.py`。
- `scripts/strategy1_cloudrun/config.py:27` 反向 `from quant_ashare.strategy1.catalog import step_name_for_path`，构成跨层环；极端案例：`src/.../tail_risk_overlay_ab.py:28` 经 scripts shim 绕一圈 import 回自己包内的 `dataset_roles`。
- `pyproject.toml` 只打包 `src/`（`where=["src"]`），wheel 单独安装后 12 个 src 模块 import 即失败；当前只靠 `Dockerfile.strategy1-cloudrun` 整仓 COPY + `pip install -e .` 跑通。
- 项目规定新逻辑必须落 src，每加一个模块反向 import 就继续涨（06-10 至 06-12 已 +10 行）。

「scripts 兼容层按单独迁移节奏保留」的既有决策覆盖的是 **scripts→src 方向的转发 wrapper**；src→scripts 的反向依赖从未被认可为设计，是排期内未完成项。

## 2. 目标

1. `src/quant_ashare/strategy1` 零 `from scripts...` import，包自洽（wheel 可独立安装使用）。
2. `scripts/strategy1_cloudrun/` 全部退化为 thin re-export shim（既有模式），公开符号集合不变。
3. 顺带消除 state 相关的逐字重复 helper 与无单测的 GCS lease 类（仅限字面级去重 + 补测，**不**合并语义）。

## 3. 方案：三批迁移，每批独立 PR

通用模式（已验证）：模块文件移入 `src/quant_ashare/strategy1/`（文件名不变），scripts 侧同名文件改为 shim（参照现有 `scripts/strategy1_cloudrun/ledger.py`：docstring 注明迁移 + `from quant_ashare.strategy1.<mod> import *` + 显式 re-export 非 `__all__` 私有符号——以**符号集合等价断言测试**兜底，见 §5）。src 包内所有 `from scripts.strategy1_cloudrun import X` 改为包内相对 / 绝对 import。

### Batch 1：`bq_io.py` + `config.py`

- 迁移后 `config.py:27` 的反向 import 自然消解（包内 import catalog）。
- `config.py` 是参数 / 环境解析核心，被 src 与 scripts 双侧最多模块消费，shim 必须完整 re-export（含模块级常量）。

### Batch 2：`state.py` + `task_fanout.py` + 字面级去重 + lease 补测

- 迁移两模块。
- 去重（仅逐字相同代码）：`annual_pipeline_scheduler.py` 内与 `state.py` 逐字重复的 `_is_precondition_error` / `_is_not_found_error`(L1523-1530) / `utc_now`(L1515)，及近逐字拷贝的 `GcloudExecutionClient.describe`(L438-455，对照 `state.py:424-444` `describe_cloud_run_execution`，拷贝版丢了失败 LOGGER.warning——统一后恢复 warning，这是唯一允许的行为差异修复，PR 单列说明)。
- **明确不做**：不合并 `GcsLeaseLock` / `GcsSchedulerLease` / `pipeline_control` 锁的 reclaim / heartbeat 语义——三者差异各有 PRD 背书（PRD_20260611_01 L159 execution-terminal reclaim；PRD_20260611_07 §4.1 scheduler 无 reclaim 是刻意最小设计；KNOWN_CONSTRAINTS warehouse 锁条款）。仅在各类 docstring 补一行语义出处注记。
- 补测：`GcsLeaseLock`（acquire 竞争 / stale 回收含 execution-terminal 条件 / heartbeat 失锁）与 `GcsSchedulerLease`（generation conflict / 失 owner 即停 / 无 reclaim 行为本身）的直接单测，仿 `tests/pipeline_control/test_state_lock.py` 的 fake GCS 模式。

### Batch 3：`feature_sets.py` + `preprocess.py` + `training_panel.py` + 收尾

- 迁移三模块。
- 收尾验收：新增**包自洽测试**——subprocess 在非仓库 cwd、`PYTHONPATH` 仅含 `src/` 下逐个 import `quant_ashare.strategy1` 全部模块成功（这是 Phase E 完成的可执行定义）。
- 同步：KNOWN_CONSTRAINTS 兼容层条款更新（剩余兼容面收窄为两个 orchestrator + shim 群）；PRD_20260610_02 补一行状态注记；`tests/strategy1/test_package_boundaries.py` 边界断言随迁移更新（src 不得 import scripts 改为**硬断言**）。

### Batch 4（P1，可选，默认不在本轮范围）

- `ledger.py` 内 `sell_cost_components` 抽取（三处逐字拷贝：L527 / L704 / L771）与 CA 函数群拆 `corporate_actions.py` 子模块。前置条件：owner 对 topdown Phase 1 路线做出决策后、且下一次本就要改 ledger 时顺带；golden hash 不变量必须原值通过。本 PRD 仅登记，不排期。

## 4. 风险控制

- 每批必跑：全量 `python3 -m pytest -q tests`、`tests/strategy1/test_package_boundaries.py`、五个 package entrypoint 干跑测试、retired-reference linter、`python3 -m compileall`、`git diff --check`、`python3 scripts/dataform/generate_sqlx_from_sql.py --check`（不应有 SQL 变化，跑以证明零漂移）。
- Cloud Run 不受影响：五个正式 job args 已是 package entrypoint（`quant_ashare.strategy1.*`），镜像按 immutable digest 固定；本迁移是纯代码结构变化，镜像内整仓 COPY 下新旧 import 路径都可用。下次常规镜像重建时按既有 runbook boot smoke，不要求本 PRD 专门重建。
- 旧模块路径（`scripts.strategy1_cloudrun.bq_io` 等）**不进** retired-lint ban-list（与 ledger shim 同等待遇：兼容引用合法）；ban-list 维持现状。
- 并行研究会话可能正在改这些模块：每批 PR 前 rebase origin/main，迁移 commit 与逻辑改动 commit 严格分离（迁移 commit 必须是纯 move + import 重写，`git log --follow` 可追溯）。

## 5. 验收（每批 PR）

1. shim 符号集合等价：测试断言 `dir(scripts.strategy1_cloudrun.<mod>)` 的公开符号 ⊇ 迁移前快照（快照写死在测试中）。
2. src 反向 import 计数单调递减，Batch 3 后为 0（grep 断言进 `test_package_boundaries.py`）。
3. 全量测试通过 + §4 清单全绿。
4. Batch 3 后包自洽测试通过。

> 文档维护：Claude Fable 5（2026-06-12）
