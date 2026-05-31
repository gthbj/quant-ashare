# Agent 工作记忆（Agent Memory）

本目录是 `quant-ashare` 仓库的**长期 Agent 工作记忆层**。

它为后续的 Agent 与维护者保存：项目背景、架构与建模决策、实现状态、已知约束、待决问题、术语、以及跨会话的交接信息。

## 核心约定

- **任何 Agent 在开始工作前，必须先读取本目录下相关记忆文件**（入口见 `MEMORY_INDEX.md`）。
- **任何 Agent 在结束工作前，必须按 `UPDATE_PROTOCOL.md` 更新相关记忆文件**。
- 完整读写规则见仓库根目录 `AGENTS.md` 的「Agent 记忆协议」。

## 安全红线

不得在记忆文件中存储：密钥、token、`auth.json`/凭据文件、API key、OAuth token、私有凭证、个人隐私数据、或未脱敏的原始日志。
（特别针对本项目：**BigQuery service account key、Tushare token 绝不可写入**。）

## 性质

记忆文件是 **Git 可审计产物**。更新应当：简洁、可追溯、可 review。
