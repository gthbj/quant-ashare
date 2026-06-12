# 记忆更新协议（Memory Update Protocol）

本仓库每个 Agent 都必须遵循此协议。

## 工作前（Before Work）

1. 读 `.agent/memory/MEMORY_INDEX.md`。
2. 读与任务相关的所有记忆文件。
3. 检查 `.agent/memory/OPEN_QUESTIONS.md`。
4. 检查 `.agent/memory/KNOWN_CONSTRAINTS.md`。
5. 若任务与已知约束冲突，先暂停、与 owner 澄清，不要直接动手。

## 工作中（During Work）

1. 记忆更新保持简洁。
2. 不写原始思维链、不写推测性内容。
3. 不存密钥、凭据、token、auth 文件、隐私数据、原始日志（尤其 BQ key / Tushare token）。
4. 持久决策记入 `DECISION_LOG.md`。
5. 临时交接信息记入 `AGENT_HANDOFF.md`。
6. 未决问题记入 `OPEN_QUESTIONS.md`。

## 工作后（After Work）

结束前，更新：

1. `IMPLEMENTATION_STATUS.md` — 更新已完成/进行中/受阻区域。
2. `AGENT_HANDOFF.md` — 用 `templates/HANDOFF_TEMPLATE.md` 追加一条交接，并刷新顶部「当前交接摘要」。
3. `DECISION_LOG.md` — 仅追加持久决策（用 `templates/DECISION_RECORD_TEMPLATE.md`）。
4. `OPEN_QUESTIONS.md` — 新增或关闭问题。
5. `KNOWN_CONSTRAINTS.md` — 仅当约束变化时更新。
6. 根目录 `TODO.md` — 勾选已完成项、补充新发现项，保持反映真实进度。

例外：纯只读盘点 / 问答 / 评审，且未改项目文件、未产生 owner 已采纳的状态变化或新决策时，不追加 handoff、不更新状态/TODO。评审按 AGENTS.md §六优先写 GitHub PR comment；一条写不下拆多条。只有 owner 明确要求或无 PR comment 承载面时，才产出 `docs/reviews/` 评审文档。

## 归档与瘦身

1. `AGENT_HANDOFF.md` 只保留当前交接摘要和最近 3 条交接；追加新条目时若主文件超过摘要 + 3 条，当场把最旧条目按月归档到 `archive/AGENT_HANDOFF_YYYY-MM.md`。
2. `OPEN_QUESTIONS.md` 只保留 open 问题；closed 问题移入 `archive/CLOSED_QUESTIONS.md`。
3. `IMPLEMENTATION_STATUS.md` 只保留当前状态快照 + 最近 7 条「最新补充」（按小节日期排序，日期相同保持原相对顺序）；追加新小节时，同步刷新快照区，并把超出窗口的小节原文搬入对应月份 `archive/IMPLEMENTATION_STATUS_YYYY-MM.md`。
4. `DECISION_LOG.md` 主文件 = 全量决策索引行 + 最近 10 条决策全文；追加新决策时同步写索引行，超过 10 条的旧全文搬入对应月份 `archive/DECISION_LOG_YYYY-MM.md`，主文件索引必须继续保留全部 DECISION id。
5. `KNOWN_CONSTRAINTS.md` 新增 / 修改约束时只写操作性语义 + 出处指针（PRD / DECISION 编号），不内嵌论证与实跑记录；单条约束以一个短段落为上限。
6. `DECISION_LOG.md` 只追加重要且持久的决策；普通执行记录写入 `IMPLEMENTATION_STATUS.md` / `AGENT_HANDOFF.md`。已被 superseded 的决策可压缩为摘要，但必须保留替代决策编号和相关文件。该压缩仅适用于尚未归档的主文件条目；已归档全文一律不改写。

## 更新风格

用事实性、简洁的语言。

不要写：「我觉得」「也许」「大概」、私有推理、原始日志、密钥值、未脱敏 token。

要写：改了什么 / 为什么重要 / 相关文件 / 需要的后续 / 需要 owner 决策的点。

## 强制交接

每个改动了项目文件并产生持久状态变化的 Agent，都必须用 `.agent/memory/templates/HANDOFF_TEMPLATE.md` 在 `AGENT_HANDOFF.md` 追加一条交接条目。
