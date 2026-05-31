# CLAUDE.md

> 本文件由 Claude Code 在**每次会话自动加载**，作用是把 Agent 工作记忆协议带入每个会话，**确保「主动读取、主动更新」落地**。其他 Agent 框架请读同目录 `AGENTS.md`（内容一致）。

## 🔴 会话开始：先读记忆（Before Work）

在修改任何文件前，**必须先读**：

1. `.agent/memory/MEMORY_INDEX.md`（记忆入口）
2. `.agent/memory/PROJECT_CONTEXT.md`
3. `.agent/memory/IMPLEMENTATION_STATUS.md`
4. `.agent/memory/KNOWN_CONSTRAINTS.md`
5. `.agent/memory/OPEN_QUESTIONS.md`
6. 与当前任务相关的其他记忆文件（见索引）

任务若与已知约束冲突 → 先暂停、与 owner 澄清。

## 🔴 会话结束：更新记忆（After Work）

按 `.agent/memory/UPDATE_PROTOCOL.md` 更新：`IMPLEMENTATION_STATUS.md`、`AGENT_HANDOFF.md`（追加交接条目 + 刷新摘要）、`DECISION_LOG.md`（持久决策）、`OPEN_QUESTIONS.md`、`KNOWN_CONSTRAINTS.md`、根 `TODO.md`。

## 🔴 安全红线

绝不写入 BigQuery key / Tushare token / 任何凭据 / 隐私 / 未脱敏日志。

## 项目一句话

基于 BigQuery `data-aquarium` 的 A 股日线量化数据仓库（ODS→DIM/DWD→DWS）。当前：DWD/DIM 设计已定稿（`docs/数据仓库建模方案-DWD-DIM.md`），下一步落地 P0 建表 SQL。

## 🔴 署名：标明你的模型名

- commit message 末尾加 `Co-Authored-By: <你的模型名> <noreply@…>`，精确到版本（如 `Claude Opus 4.8`）。
- 自己写/大改的文档，文首或文末标注 `> 文档维护：<模型名>（日期）`。
- 详见 AGENTS.md「五、模型署名协议」。

## 完整协议

@AGENTS.md
