> 文档维护：GPT-5 Codex（最近更新 2026-06-10）

# Strategy1 Research Table Contracts

`sql/research/**` defines the D0 contract for `data-aquarium.ashare_research`.
This layer is for unpromoted Strategy1 experiments, diagnostics, acceptance
replay, and promotion provenance.

Current status:

- D0 defines schema contracts; D1 has passed a real explicit research-mode
  smoke, and D2 switches ordinary Strategy1 execution to research-first.
- `configs/strategy1/active_step_catalog.yml` keeps the current dataset role as
  `research`; `ads` is now an explicit historical/promotion target.
- Runner/report/QA/acceptance default to research outputs. Use
  `--output-dataset-role ads` only for historical ADS audit runs.
- Phase D3 adds the explicit owner-approved promotion job:
  `python -m scripts.strategy1.promote_research_to_ads`.

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
- Run `03_qa_research_schema_readiness.sql` after every research contract
  migration and before rebuilding jobs that should write research by default.
- Never use `CREATE OR REPLACE` for populated research tables unless owner has
  approved a destructive reset.

Naming rules:

- All research tables use the `research_*` prefix.
- Research rows are run-scoped and unpromoted by default; ordinary research
  outputs default to `research_status='candidate'` and
  `promotion_status='not_promoted'`.
- `accepted` means acceptance gate passed inside research; it is not the same
  as `promoted`.
- `promoted` requires a successful row in `research_promotion_manifest`; the
  promotion job also marks promoted research rows with
  `promotion_status='promoted'`. Promotion does not rewrite
  `acceptance_status` or `research_status` to `accepted`, including
  owner-approved `--allow-unaccepted` runs.
- `ashare_ads` remains the target for owner-approved promoted outputs only.
