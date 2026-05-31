# AGENTS.md

`quant-ashare` 是基于 BigQuery `data-aquarium` 的 **A 股日线量化数据仓库**（ODS→DIM/DWD→DWS），服务中低频小资金机器学习量化。本文件定义所有在本仓库工作的 Agent 必须遵守的协议。

---

## 一、Agent 记忆协议（最重要，主动读取 + 主动更新）

本仓库在 `.agent/memory/` 维护一套**长期工作记忆**。**任何 Agent 在任何会话中都必须遵守以下闭环。**

### 1. 开始工作前 —— 主动读取

修改任何文件前，**必须先读** `.agent/memory/MEMORY_INDEX.md`（记忆入口索引），并至少读：

- `.agent/memory/PROJECT_CONTEXT.md` —— 项目目标与现状
- `.agent/memory/IMPLEMENTATION_STATUS.md` —— 已完成/进行中/未开始
- `.agent/memory/KNOWN_CONSTRAINTS.md` —— 数据/平台/PIT/安全约束
- `.agent/memory/OPEN_QUESTIONS.md` —— 未决问题
- `MEMORY_INDEX.md` 中与当前任务相关的其他记忆文件

若任务与 `KNOWN_CONSTRAINTS.md` 冲突，**先暂停并与 owner 澄清**，不要直接动手。

### 2. 结束工作前 —— 主动更新

**必须按 `.agent/memory/UPDATE_PROTOCOL.md` 更新相关记忆文件**，至少：

- `IMPLEMENTATION_STATUS.md`：更新完成/进行中/受阻状态
- `AGENT_HANDOFF.md`：用 `templates/HANDOFF_TEMPLATE.md` 追加一条交接，并刷新顶部「当前交接摘要」
- `DECISION_LOG.md`：仅追加**持久**决策（用 `templates/DECISION_RECORD_TEMPLATE.md`）
- `OPEN_QUESTIONS.md`：新增或关闭问题
- `KNOWN_CONSTRAINTS.md`：仅当约束变化时
- 根目录 `TODO.md`：勾选已完成、补充新发现

### 3. 安全红线（绝对）

记忆文件、文档、代码、日志中**绝不可写入**：BigQuery service account key、Tushare token、任何 API key / OAuth token / 凭据文件 / 个人隐私 / 未脱敏原始日志。

### 4. 更新风格

事实、简洁、可追溯。写「改了什么 / 为什么 / 相关文件 / 后续 / 需 owner 决策」；不写「我觉得/也许」、原始思维链、密钥值。

---

## 二、文档规范

- 设计/方案文档统一放 `docs/`。当前核心文档：`docs/数据仓库建模方案-DWD-DIM.md`（DWD/DIM 建模方案，权威口径）。
- 未来建表 SQL 建议放 `sql/`（如 `sql/dim/`、`sql/dwd/`），dbt 模型放 `models/`。
- 文档与 `.agent/memory/` 须保持一致：方案变更时同步 `ARCHITECTURE_MEMORY.md` / `DECISION_LOG.md`。

---

## 三、TODO 维护协议

根目录 `TODO.md` 是项目级待办。所有 Agent 必须**主动维护**，使其反映真实进度。

- 完成某项 → 勾 `[x]` 并补一句（关联 commit/文件）。
- 新增/拆解工作项 → 在对应优先级补 `[ ]`。
- 范围/优先级变化 → 调整分组或措辞。
- `TODO.md` 面向「下一步做什么」；`IMPLEMENTATION_STATUS.md` 面向「整体状态」，两者结束任务前都要最新。
- 不在 `TODO.md` 存任何凭据。

---

## 四、Git 约定

- 默认分支 `main`。**仅在 owner 明确要求时**才 commit / push。
- 改动项目文件时，相关 `.agent/memory/**` 与 `TODO.md` 应在同一次提交一并更新（记忆与代码同步）。
- 提交信息简洁可追溯，且必须带模型署名 trailer（见「五、模型署名协议」）。

---

## 五、模型署名协议

每个 Agent 必须在其产出中标明**具体模型名**（精确到版本，如 `Claude Opus 4.8`；不要只写 "AI" 或泛称 "Claude"）：

- **Git 提交**：commit message 末尾加 trailer
  `Co-Authored-By: <模型名> <noreply 邮箱>`，例如
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。
- **自己撰写或大幅改写的文档**：在文首或文末标注，例如
  `> 文档维护：Claude Opus 4.8（最近更新 YYYY-MM-DD）`。
- **记忆交接 / 决策条目**：填写模板中的 `Model:` 字段。

目的：让每项产出可追溯到具体模型，便于审计不同模型的贡献与质量。

---

## 六、评审（Review）协议

对**已提交的代码 / SQL** 或**设计 / 方案文档**做评审时：

- **必须产出一份评审文档**，放 `docs/reviews/`，命名 `<对象>-review[-<专题>].md`；评审结论不止停留在对话里。
- 文档至少含：评审对象（commit / 文件）、按严重度分级的发现、每条的依据 / 影响 / 建议、与既有决策是否冲突、结论；并带模型署名（§五）。
- **评审本身是只读的**：评审过程**不得**擅自改动被评审对象，也**不得**把发现直接写进 `.agent/memory/**` 或 `TODO.md`。发现是否转为 `OPEN_QUESTIONS` / `TODO` / 决策，由 owner 拍板。
- 是否 commit 评审文档由 owner 决定；owner 要求提交时，与相关 `.agent/memory/**`、`TODO.md` 同一次提交（见「四、Git 约定」记忆与代码同步）。
