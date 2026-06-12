# 记忆索引（Memory Index）

本文件是所有项目记忆文件的入口。**任何 Agent 修改文件前必须先读本文件。**

| 文件 | 用途 | 何时读取 | 何时更新 |
|---|---|---|---|
| PROJECT_CONTEXT.md | 项目背景与目标 | 每个任务开始时 | 项目目标或范围变化时 |
| ARCHITECTURE_MEMORY.md | 数仓分层、表清单、物理规范 | 涉及建模/架构时 | 架构或表设计变化时 |
| IMPLEMENTATION_STATUS.md | 当前状态快照 + 最近补充 | 每个任务开始时 | 每个开发任务结束时；追加补充时同步滚动归档 |
| DECISION_LOG.md | 全量决策索引 + 最近 10 条决策全文 | 涉及关键取舍时 | 新增不可逆/重要决策时；同步索引与月度归档 |
| KNOWN_CONSTRAINTS.md | 已知约束（数据/平台/PIT 等） | 每个任务开始时 | 约束变化时 |
| OPEN_QUESTIONS.md | 未决问题 | 每个任务开始时 | 新增或关闭问题时 |
| GLOSSARY.md | 项目术语 | 术语需澄清时 | 出现新术语时 |
| DOC_CONVENTIONS.md | 文档 / PRD 存放与命名规范 | 写文档 / PRD 时 | 文档规范变化时 |
| AGENT_HANDOFF.md | 跨会话交接摘要 | 每个任务开始时 | 每个任务结束时 |
| UPDATE_PROTOCOL.md | 记忆更新规则 | 每个任务结束前 | 协议本身变化时 |
| templates/ | 交接/决策/更新模板 | 需要追加条目时 | 模板格式调整时 |
| archive/ | 已归档交接、状态编年史、决策全文和已关闭问题 | 仅追溯历史时 | 滚动归档旧 handoff / status / decisions / closed questions 时 |
| archive/IMPLEMENTATION_STATUS_YYYY-MM.md | 状态编年史归档 | 追溯历史执行状态时 | `IMPLEMENTATION_STATUS.md` 滚动移出旧补充时 |
| archive/DECISION_LOG_YYYY-MM.md | 决策全文月度归档 | 需要决策全文时 | `DECISION_LOG.md` 保留索引并移出旧全文时 |

新增任何记忆文件，必须在本索引登记。

## 当前项目一句话状态

`quant-ashare` 是基于 BigQuery `data-aquarium` 的 **A 股日线量化数据仓库**（ODS→DIM/DWD→DWS→ADS）。当前阶段：P0 数仓底座、OQ-005 调度迁移、OQ-012 schema 防复发、OQ-011 true-five-year 覆盖和 PRD_20260612_02 CA-on ledger 均已收口；Strategy1 研究 baseline 为 true-five-year CA-on（backtest `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01`，CAGR `15.36%` (`0.153578`) / v3 contract Sharpe `0.6685` / Calmar `0.4103` / MaxDD 不变；2026-06-12 dividend 补采后 resume 修正，child `bt_s1_dividend_backfill_resume_20260528_20260609_v20260612_01`，详见 `docs/分析-dividend-ODS补采与CA-Resume补跑-20260612.md`），baseline ≠ accepted、不得 promotion。当前开放主线只剩 OQ-010。
