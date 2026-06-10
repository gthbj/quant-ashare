> 文档维护：Claude Fable 5（最近更新 2026-06-11）

# PRD：Research Backtest Summary `created_date` / `run_id` 落库修复

> 状态：草案，待 owner review。简短 PRD，对应一个 bug-fix PR。
> 范围声明：只修 summary 落库字段、回填与 QA 防复发；不改指标计算、不改 ledger、不动 ADS 历史行为。

---

## 1. 问题

`2021-2026` 年度链路写入的 6 条 `research_backtest_performance_summary` 行中，`created_date` 与 `run_id` 为 `NULL`：

- `created_date` 是该表的月分区列——按分区字段过滤的常规查询查不到这些行；
- `run_id` 为空断掉 run 级溯源，影响后续 promotion / readiness / 报告对账。

## 2. 根因（已实证）

- `sql/strategy1/reporting/build_metrics_and_report_inputs.sql`（`09`）的 summary INSERT 列清单为 `(backtest_id, strategy_id, model_id, start_date, end_date, ...)`，**不含 `run_id` 与 `created_date`**。
- 这是历史遗留：ADS 的 `ads_backtest_performance_summary` 表**本身没有这两列**（已核对 `sql/ads/01` DDL），列清单当年按 ADS schema 写成立。
- D0 的 research 表按 run-scoped lifecycle 设计新增了 `run_id` / `created_date` 列；D1a 的 research 渲染只重写表名、不重写列清单 → 未列出且无 DEFAULT 的列按 BigQuery DML 语义写 `NULL`（带 DEFAULT 的 `promotion_status` 等不受影响，与现象一致）。

## 3. 修复方案

1. **对齐 schema（推荐）**：用 additive migration（`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`，沿用 `sql/ads/03` 模式）给 `ads_backtest_performance_summary` 补 `run_id STRING`、`created_date DATE` 两列；ADS 历史行保持 `NULL`，作为 legacy 事实不回填。
2. `09` SQL 的 INSERT 列清单与 SELECT 增加 `run_id`（取 `p_run_id`）与 `created_date`（取 `CURRENT_DATE()`），ADS / research 两种渲染共用同一列清单。
3. **回填现有 6 行 research summary**（需 owner 批准的 research 数据更正）：按 `backtest_id` UPDATE 补 `run_id` 与 `created_date`；`created_date` 取各行 `created_at` 的日期部分，保持与写入时刻一致。该表 `require_partition_filter=FALSE`，UPDATE 按 `backtest_id` 过滤合规。
4. **QA 防复发**：
   - `qa_runner_outputs` 增加断言：summary 行 `run_id` / `created_date` NOT NULL；
   - **扩展 `qa_cloudrun_schema_readiness`（按 PR #162 review finding 3）**：在 `ads_backtest_performance_summary` 的 `required_columns` 中加入 `run_id STRING` / `created_date DATE`——修复后 ADS 渲染的 `09` 也依赖这两列，漏跑 additive migration 的环境必须被 preflight 拦截而不是 `09` 运行期报错；失败信息指向本 PRD 的 migration 文件；
   - research readiness QA（research 侧列存在性已覆盖）不需改；
   - 同步检查 catalog `backtest_summary` 的分区元数据语义（research 侧 `created_date` 分区、ADS 侧无分区），如有表述歧义在 catalog 注释说明。

备选方案（不推荐）：`09` 按 dataset role 条件化列清单——引入双份 SQL 维护成本，且 schema 对齐本来就是 research/ADS 镜像设计的既定方向。

## 4. 验收标准

| 验收项 | 要求 |
|---|---|
| 写入修复 | 修复后新写入的 summary 行 `run_id` / `created_date` 非空（ADS 与 research 两种渲染） |
| 回填 | 现有 6 行 research summary 两字段补齐，且其余字段逐字节不变 |
| 分区可查 | 按 `created_date` 分区过滤可查到全部 6 行 |
| QA | `qa_runner_outputs` 的 NOT NULL 断言上线并在回填后通过 |
| readiness 防漏 | `qa_cloudrun_schema_readiness` 覆盖 ADS summary 新增两列，live 复跑通过 |
| ADS 兼容 | ADS 渲染的 `09` 在补列后正常执行；ADS 历史行不回填、不重建 |

## 5. 执行顺序

1. additive migration（ADS 补列）→ `09` SQL 修复 → 单元/渲染测试。
2. owner 批准后回填 6 行并复核。
3. QA 断言上线。
4. 本修复应先于 PRD_20260611_02/03 的任何重跑执行，避免重跑继续产出缺字段的 summary 行。
