-- 文档维护：GPT-5 Codex（最近更新 2026-06-10）
-- BigQuery Standard SQL
-- Strategy1 research additive migrations.
--
-- Research contract DDL uses CREATE TABLE IF NOT EXISTS, so new columns on an
-- already-created table must be propagated here with idempotent ALTER TABLE
-- statements. Do not rebuild populated research tables in this file.

ALTER TABLE `data-aquarium.ashare_research.research_experiment_run_status`
ADD COLUMN IF NOT EXISTS log_dir STRING
OPTIONS(description = '本地调度日志目录路径');
