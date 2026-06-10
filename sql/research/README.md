> 文档维护：GPT-5 Codex（最近更新 2026-06-10）

# Strategy1 Research Table Contracts

`sql/research/**` defines the D0 contract for `data-aquarium.ashare_research`.
This layer is for unpromoted Strategy1 experiments, diagnostics, acceptance
replay, and promotion provenance.

Current status:

- D0 defines schema contracts; D1 has passed a real explicit research-mode
  smoke.
- `configs/strategy1/active_step_catalog.yml` still keeps the current default
  dataset role as `ads`.
- Explicit research routing is supported by runner/report/QA/acceptance, but
  Phase D2 has not switched ordinary experiments to research-first yet.
- Phase D2 may switch normal experiments to research-first only after all
  readers support research tables and the D1 smoke has passed.
- Phase D3 will add the explicit owner-approved promotion job.

Run manually when creating or refreshing the research contract:

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/00_create_datasets.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/research/01_research_strategy1_tables.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/research/02_research_strategy1_additive_migrations.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/research/03_qa_research_schema_readiness.sql
```

Migration rules:

- `01_research_strategy1_tables.sql` is the canonical contract for new
  environments.
- Because it uses `CREATE TABLE IF NOT EXISTS`, it will not propagate new
  columns to existing research tables. Every additive contract change must also
  be represented in `02_research_strategy1_additive_migrations.sql` with an
  idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.
- Run `03_qa_research_schema_readiness.sql` before Phase D2 research-first
  execution and after every research contract migration.
- Never use `CREATE OR REPLACE` for populated research tables unless owner has
  approved a destructive reset.

Naming rules:

- All research tables use the `research_*` prefix.
- Research rows are run-scoped and unpromoted by default; ordinary research
  outputs default to `research_status='candidate'` and
  `promotion_status='not_promoted'`.
- `accepted` means acceptance gate passed inside research; it is not the same
  as `promoted`.
- `ashare_ads` remains the target for owner-approved promoted outputs only.
