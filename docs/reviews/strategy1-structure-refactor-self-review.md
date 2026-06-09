> 文档维护：GPT-5 Codex（最近更新 2026-06-10）

# Strategy1 Structure Refactor Self Review

Review object: branch `codex/strategy1-structure-refactor`, implementing `docs/prd/PRD_20260610_02_项目结构重构方案.md` Phase A/B/C.

## 30-Item Review Checklist

1. PASS - Worktree is isolated from the primary checkout.
2. PASS - PRD scope stays within Phase A/B/C; no `ashare_research` dataset creation.
3. PASS - Existing Cloud Run module entrypoints remain under `scripts.strategy1_cloudrun`.
4. PASS - Active step catalog exists at `configs/strategy1/active_step_catalog.yml`.
5. PASS - Catalog covers both former `sql/ml/strategy1/**` and former `sql/cloudrun/strategy1/**` paths.
6. PASS - Catalog classifies `16-25` individually instead of treating the range as uniformly active.
7. PASS - Catalog records current ADS role and future research role without switching runtime writes.
8. PASS - Table role resolver maps research requests back to ADS in the current phase.
9. PASS - Active SQL files moved to `sql/strategy1/**`.
10. PASS - Old SQL namespaces contain historical/audit README notes only.
11. PASS - `backtest_report.py` uses catalog step names instead of active raw SQL paths.
12. PASS - Search orchestrator uses `training_panel_step` and catalog QA steps.
13. PASS - Risk-feature manifests no longer point at `sql/cloudrun/strategy1/01_build_training_panel.sql`.
14. PASS - v3 replay QA helper defaults to the new acceptance SQL path.
15. PASS - SQL render enforces required params for step calls.
16. PASS - SQL render supports `ARRAY<STRING>` and `ARRAY<INT64>` declarations.
17. PASS - Backtest SQL params include cost, benchmark, initial capital, lot size, and tail-risk thresholds.
18. PASS - Retired linter is scoped and allowlisted, not a whole-repo grep.
19. PASS - Retired linter passes active scopes.
20. PASS - Active docs/runbooks point to `sql/strategy1/**`.
21. PASS - `Dockerfile.strategy1-cloudrun` installs the package with `pip install --no-deps -e .`.
22. PASS - Tests cover catalog validation, path mapping, resolver behavior, strict rendering, and retired lint.
23. PASS - Existing ledger tests pass after restoring overwritten resume validation.
24. PASS - `compileall` succeeds for `src`, `scripts/strategy1`, and `scripts/strategy1_cloudrun`.
25. PASS - `backtest_report` dry-run succeeds for `oq010_a0_n5_w20`.
26. PASS - Search orchestrator `--help` imports successfully in the test venv.
27. PASS - v3 replay QA helper `--help` imports successfully.
28. PASS - Active step render smoke covers all active catalog steps.
29. PASS - `git diff --check` succeeds.
30. FOLLOW-UP - Dataform `--check` still reports stale generated SQLX files, but this branch has no `dataform/` diff versus `origin/main`; treat as pre-existing until a Dataform cleanup PR.
