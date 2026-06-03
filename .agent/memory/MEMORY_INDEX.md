# 记忆索引（Memory Index）

本文件是所有项目记忆文件的入口。**任何 Agent 修改文件前必须先读本文件。**

| 文件 | 用途 | 何时读取 | 何时更新 |
|---|---|---|---|
| PROJECT_CONTEXT.md | 项目背景与目标 | 每个任务开始时 | 项目目标或范围变化时 |
| ARCHITECTURE_MEMORY.md | 数仓分层、表清单、物理规范 | 涉及建模/架构时 | 架构或表设计变化时 |
| IMPLEMENTATION_STATUS.md | 已完成/进行中/未开始 | 每个任务开始时 | 每个开发任务结束时 |
| DECISION_LOG.md | 重要且持久的决策记录 | 涉及关键取舍时 | 新增不可逆/重要决策时 |
| KNOWN_CONSTRAINTS.md | 已知约束（数据/平台/PIT 等） | 每个任务开始时 | 约束变化时 |
| OPEN_QUESTIONS.md | 未决问题 | 每个任务开始时 | 新增或关闭问题时 |
| GLOSSARY.md | 项目术语 | 术语需澄清时 | 出现新术语时 |
| DOC_CONVENTIONS.md | 文档 / PRD 存放与命名规范 | 写文档 / PRD 时 | 文档规范变化时 |
| AGENT_HANDOFF.md | 跨会话交接摘要 | 每个任务开始时 | 每个任务结束时 |
| UPDATE_PROTOCOL.md | 记忆更新规则 | 每个任务结束前 | 协议本身变化时 |
| templates/ | 交接/决策/更新模板 | 需要追加条目时 | 模板格式调整时 |
| archive/ | 已归档交接和已关闭问题 | 仅追溯历史时 | 归档旧 handoff / closed questions 时 |

新增任何记忆文件，必须在本索引登记。

## 当前项目一句话状态

`quant-ashare` 是基于 BigQuery `data-aquarium` 的 **A 股日线量化数据仓库**（ODS→DIM/DWD→DWS→ADS）。
当前阶段：**P0 DIM/DWD 已物化并通过 smoke QA；OQ-004 已实现并关闭且 PR #11 已合并到 `main`，`dim_index` 已物化，`dwd_index_eod` 已从 `dim_index` 读取 canonical `sec_code` + `source_sec_code` 映射，`sql/qa/03_oq004_index_checks.sql` 通过；策略 1 价格量价 DWS 六表与 ADS 表契约已物化并通过 `sql/qa/02_strategy1_dws_ads_checks.sql`；策略 1 BigQuery ML runner `sql/ml/strategy1/01-10` 已于 PR #12 在 BigQuery 端到端实跑并通过全部 QA（`10` 16 断言全过），08 已重写为账户级有状态 ledger；OQ-006 单位契约已实现并关闭（PR #16 已合并，含 `ods_field_unit_map`、`05_oq006_unit_checks.sql`、`dwd_index_eod` 换算修复 + 命名迁移）；OQ-003 财务报表口径已实现（PR #13）：三大报表 DWD（`income/balancesheet/cashflow` + `_latest`，`sql/dwd/06-11`）保留 `report_type`/`report_caliber` 口径字段，`dws_stock_feature_fin_daily`（`sql/dws/07`，默认合并口径 PIT 财务特征）已物化并通过 `sql/qa/04_finance_caliber_checks.sql`，并按 OQ-006 单位契约在 `ods_field_unit_map` 补全财务三表字段映射、跑通 `sql/qa/05_oq006_unit_checks.sql`；OQ-010 交易成本 profile 已在 runner SQL 中实现，默认成本 profile 为佣金万一免五、卖出印花税 5 bps、买/卖滑点各 5 bps；策略 1 中文报告与归因分析已实现并合并（PR #20），报告中文化、评估主基准保持中证1000 `000852.SH`、展示对比基准包含沪深300 `000300.SH`、交易/持仓/NAV 附件、亏损证据包和 AI 诊断已进入 runner；策略 1 报告 GCS uploaded 模式已跑通，`gs://ashare-artifacts` 已创建、本机 ADC 已配置、ADS 已回写真实 `report_uri`，`10_qa_runner_outputs.sql` 全部通过；策略 1 模型质量诊断、valid/test live-available 预测池口径和 score orientation 校准均已实现并通过 `12` QA；OQ-010 首轮质量迭代实验 PRD 已合并（PR #35，`PRD_20260603_02_策略1首轮质量迭代实验.md`），且 PRD 已补充阶段 A/B/C 基础路径 `4 + 3 + 3 = 10`、包含阶段 D 为 12 个实验，不做 `4 * 3 * 3` 笛卡尔积，必要时补 A/B、A/C、B/C pairwise 或最终 `2 * 2 * 2` 保底复核；OQ-010 首轮实验 runner 参数化、manifest、对比报告脚本和 horizon-aware 诊断/QA 已在 `codex/implement-oq010-experiment-runner` PR 分支实现并通过 dry-run，尚未合并或端到端实跑实验**。正确口径：财务/事件按分区前移到 2017，行情最终写 2019+ 但构建时读 2018 lookback buffer，维度/日历取最新快照或全量历史事件；下一步 review/合并 OQ-010 实现 PR 后执行第一轮实验，或补 `dws_market_state_daily`。
