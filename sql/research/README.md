> 文档维护：GPT-5 Codex（最近更新 2026-06-10）

# Strategy1 Research Table Contracts

`sql/research/**` defines the D0 contract for `data-aquarium.ashare_research`.
This layer is for unpromoted Strategy1 experiments, diagnostics, acceptance
replay, and promotion provenance.

Current status:

- D0 only defines schema contracts. It does not deploy BigQuery objects by
  default and does not change runner behavior.
- `configs/strategy1/active_step_catalog.yml` still keeps the current default
  dataset role as `ads`.
- `resolve_table_role(..., dataset_role="research")` must continue to fail
  unless the caller explicitly passes `allow_future_research=True`.
- Phase D1 will add explicit research routing for runner/report/QA/acceptance.
- Phase D2 may switch normal experiments to research-first only after all
  readers support research tables.
- Phase D3 will add the explicit owner-approved promotion job.

Run manually only when owner approves creating the research contract:

```bash
bq query --use_legacy_sql=false --location=asia-east2 < sql/00_create_datasets.sql
bq query --use_legacy_sql=false --location=asia-east2 < sql/research/01_research_strategy1_tables.sql
```

Naming rules:

- All research tables use the `research_*` prefix.
- Research rows are run-scoped and unpromoted by default.
- `accepted` means acceptance gate passed inside research; it is not the same
  as `promoted`.
- `ashare_ads` remains the target for owner-approved promoted outputs only.
