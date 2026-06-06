# Dataform definitions

> 文档维护：GPT-5 Codex（最近更新 2026-06-06）

本目录是 Ashare pipeline 的 Dataform 首版定义。目标是让 ODS -> DIM/DWD/DWS 的核心生产转换拥有可编译的 Dataform action graph，并按 tag 分组运行。

当前口径：

- `sql/` 仍是 canonical SQL 来源。
- `dataform/definitions/**/*.sqlx` 由 `scripts/dataform/generate_sqlx_from_sql.py` 根据 `dataform/action_manifest.json` 生成。
- 迁移期字段说明仍由 `sql/metadata/01_core_table_column_descriptions.sql` 和 `sql/metadata/02_finance_table_column_descriptions.sql` 覆盖。
- 现有复杂 QA 先作为 Dataform `operations` 执行 BigQuery `ASSERT` 脚本；后续再拆成 Dataform-native assertions。
- ADS 契约初始化和策略 runner 不在本 Dataform 首版范围内，仍由 Composer / Cloud Run / BigQuery SQL 受控入口执行。

## Tags

| tag | 范围 |
|---|---|
| `setup` | meta 表、单位契约映射 |
| `dim_core` | `ashare_dim` 核心维表 |
| `dwd_market` | 股票/指数日频 DWD |
| `dwd_finance` | 财务指标与三大报表 DWD |
| `strategy1_dws` | 策略 1 DWS |
| `metadata` | 表/字段说明覆盖脚本 |
| `qa_core` | 核心数仓 smoke QA |
| `qa_contract` | 指数基准、财务口径、单位契约 QA |
| `assertion_strategy1` | 策略 1 DWS/ADS QA |

## Regenerate

```bash
python3 scripts/dataform/generate_sqlx_from_sql.py
python3 scripts/dataform/generate_sqlx_from_sql.py --check
npx --yes @dataform/cli compile dataform > /tmp/quant_ashare_dataform_compile.json
```

Any PR that changes canonical `sql/` files covered by `dataform/action_manifest.json` must rerun the generator and include the generated `dataform/definitions/**/*.sqlx` diff. Use `--check` to fail fast when generated SQLX files are stale or missing.

## Production Notes

Composer remains the production orchestrator. It should record `transform_backend='dataform'`, selected tags, and Dataform workflow invocation id in `ashare_meta.pipeline_task_status` before Dataform is promoted from shadow/diff mode to production writes.
