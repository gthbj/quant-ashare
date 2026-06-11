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

## 🔴 Claude ↔ Codex 协作流程（PRD 与代码）

**闭环**：Claude 写 PRD → 交 Codex review（Claude 对发现：认同的改，不认同的向 Codex 说明理由）→ Codex 不再提出新问题后，由 Codex 按该 PRD 写代码 → Claude review 代码（Codex 对发现：认可的改，不认可的向 Claude 给出理由）→ 循环往复，代码**完全通过 Claude 审核**才可合并。双方的 review 结论与不认可理由都写在对应 PR comment，保持可追溯。

**会话纪律**：同一个需求 / 同一个 PR 只用**一个 Codex 对话**；每一轮新反馈必须续接既有会话，不要新开（避免上下文分裂）。

**模型要求**：Codex 必须使用 **GPT-5.5 + reasoning effort `xhigh`**。CLI 显式传 `-m gpt-5.5 -c model_reasoning_effort="xhigh"`（resume 时同样传，防止沿用旧会话模型）；默认值固化在 `~/.codex/config.toml` 的 `model` / `model_reasoning_effort`。注意：ChatGPT 账号下模型 id 是 `gpt-5.5`，`gpt-5.5-codex` 不可用（已实测 400）。

**操作要点（Claude 会话内驱动 Codex 的标准做法，2026-06-11 在 PR #189 实跑验证）**：

1. 优先用 codex plugin 命令（如 `/codex:setup --enable-review-gate`）；plugin 命令在当前会话不可用时，直接用 `codex` CLI（已在 PATH）。
2. 定位该 PR 的既有 Codex 会话：记录在 `~/.codex/sessions/YYYY/MM/DD/rollout-*-<session-id>.jsonl`，按分支名 / worktree 路径 / PR 号 grep 定位。**首轮交接后把 session id 记入 PR body 或 `AGENT_HANDOFF.md`**，后续轮次免检索。
3. 续接会话：`codex exec resume <session-id> "<prompt>"`，后台运行（预期十几分钟以上），完成后拉取其 PR 回帖与新 commit 复核。
4. 交接 prompt 必须自包含：review comment 的 URL 及拉取命令（`gh api repos/<owner>/<repo>/issues/comments/<id> --jq .body`）、协作规则原文（认可→改；不认可→PR comment 说明理由）、修复后必须重跑的验证清单、记忆/TODO 同步要求、署名 commit + push + PR 回帖要求、该任务的红线约束（如"默认语义不可变 / 不跑 live 写入 / 不改默认 profile"）。
5. Codex 回帖后 Claude 逐条复核：已修的验证修复质量；不认可的评估其理由——理由成立则在 PR comment 显式撤回该发现，不成立则说明原因并要求继续修。全部收敛后 Claude 在 PR 上给出"可合并"判定。

## 🔴 署名：标明你的模型名

- commit message 末尾加 `Co-Authored-By: <你的模型名> <noreply@…>`，精确到版本（如 `Claude Opus 4.8`）。
- 自己写/大改的文档，文首或文末标注 `> 文档维护：<模型名>（日期）`。
- 详见 AGENTS.md「五、模型署名协议」。

## 完整协议

@AGENTS.md
