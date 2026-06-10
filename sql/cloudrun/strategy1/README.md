> 文档维护：GPT-5 Codex（最近更新 2026-06-10）

# Historical Cloud Run Strategy1 SQL Namespace

`sql/cloudrun/strategy1/**` no longer contains active Strategy1 shared SQL.

Risk-feature training panel SQL 已迁移到
`sql/strategy1/panel/build_training_panel_risk_feature.sql`，active caller 通过
`configs/strategy1/active_step_catalog.yml` 的
`build_training_panel_risk_feature` step 解析。

本目录仅保留 historical/audit note，避免后续把 `cloudrun` 路径误判为第三个
active SQL namespace。
