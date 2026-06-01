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
当前阶段：**P0 DIM/DWD 已物化并通过 smoke QA；`dwd_index_eod` 已重建为 canonical `sec_code` + `source_sec_code`；策略 1 价格量价 DWS 六表与 ADS 表契约已物化并通过 `sql/qa/02_strategy1_dws_ads_checks.sql`；策略 1 BigQuery ML runner 设计已完成**。正确口径：财务/事件按分区前移到 2017，行情最终写 2019+ 但构建时读 2018 lookback buffer，维度/日历取最新快照或全量历史事件；下一步是落地策略 1 BigQuery ML + SQL 训练/预测/组合/回测 runner，或补通用财务/市场状态 DWS。
