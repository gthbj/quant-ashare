#!/usr/bin/env python3
"""Validate windowed index/market-state refresh against canonical full SQL.

The script renders canonical full-refresh SQL into scratch "_full" tables, copies
those rows to "_window" tables, runs the index and market-state window refreshes
against the scratch targets, then compares affected rows. It does not mutate
production DWD/DWS tables.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from google.cloud import bigquery


PROJECT = "data-aquarium"
LOCATION = "asia-east2"
SCRATCH_DATASET = "ashare_qa_windowed_equivalence"
FLOAT_TYPES = {"FLOAT", "FLOAT64", "NUMERIC", "BIGNUMERIC"}
IGNORED_COMPARE_COLUMNS = {"created_at"}


@dataclass(frozen=True)
class TableSpec:
    source_dataset: str
    table_name: str
    key_columns: tuple[str, ...]

    @property
    def source_ref(self) -> str:
        return f"`data-aquarium.{self.source_dataset}.{self.table_name}`"

    def full_ref(self, project: str, scratch_dataset: str) -> str:
        return f"`{project}.{scratch_dataset}.{self.table_name}_full`"

    def window_ref(self, project: str, scratch_dataset: str) -> str:
        return f"`{project}.{scratch_dataset}.{self.table_name}_window`"


TABLES = (
    TableSpec("ashare_dwd", "dwd_index_eod", ("trade_date", "sec_code")),
    TableSpec("ashare_dws", "dws_market_state_daily", ("trade_date", "market_state_version")),
)

FULL_SQL_FILES = (
    Path("sql/dwd/04_dwd_index_eod.sql"),
    Path("sql/dws/08_dws_market_state_daily.sql"),
)

WINDOW_SQL_FILES = (
    Path("sql/incremental/02_refresh_index_dwd_window.sql"),
    Path("sql/incremental/03_refresh_market_state_window.sql"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build full/window shadow tables and compare index/market refresh values.",
    )
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--location", default=LOCATION)
    parser.add_argument("--scratch-dataset", default=SCRATCH_DATASET)
    parser.add_argument("--build-start-date", default="2024-01-01")
    parser.add_argument("--date-from", default="2025-06-02")
    parser.add_argument("--date-to", default="2025-06-13")
    parser.add_argument("--business-date", default="")
    parser.add_argument("--warehouse-mode", default="backfill")
    parser.add_argument("--float-tolerance", type=float, default=1e-8)
    parser.add_argument("--summary-output-jsonl", default="", help="Optional JSONL file for per-table mismatch summaries")
    parser.add_argument("--diff-sample-output-jsonl", default="", help="Optional JSONL file for mismatch samples")
    parser.add_argument("--max-diff-samples", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without running BigQuery jobs")
    parser.add_argument("--cleanup", action="store_true", help="Delete scratch dataset after a successful run")
    return parser.parse_args()


def parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def quote_identifier(name: str) -> str:
    return f"`{name}`"


def literal(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def table_id(project: str, dataset: str, table: str) -> str:
    return f"{project}.{dataset}.{table}"


def replacement_map(project: str, scratch_dataset: str, suffix: str) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for spec in TABLES:
        target = spec.full_ref(project, scratch_dataset) if suffix == "full" else spec.window_ref(project, scratch_dataset)
        mapped[spec.source_ref] = target
    return mapped


def apply_replacements(sql: str, replacements: dict[str, str]) -> str:
    for source, target in replacements.items():
        sql = sql.replace(source, target)
    return sql


def override_date_declarations(sql: str, *, build_start_date: str, end_date: str) -> str:
    replacements = {
        r"DECLARE dwd_start_date DATE DEFAULT DATE '2019-01-01';": f"DECLARE dwd_start_date DATE DEFAULT DATE '{build_start_date}';",
        r"DECLARE dwd_end_date DATE DEFAULT CURRENT_DATE\('Asia/Shanghai'\);": f"DECLARE dwd_end_date DATE DEFAULT DATE '{end_date}';",
        r"DECLARE dws_start_date DATE DEFAULT DATE '2019-01-01';": f"DECLARE dws_start_date DATE DEFAULT DATE '{build_start_date}';",
        r"DECLARE dws_end_date DATE DEFAULT CURRENT_DATE\('Asia/Shanghai'\);": f"DECLARE dws_end_date DATE DEFAULT DATE '{end_date}';",
    }
    for pattern, replacement in replacements.items():
        sql = re.sub(pattern, replacement, sql)
    return sql


def render_full_sql(path: Path, args: argparse.Namespace, full_end_date: str) -> str:
    sql = path.read_text(encoding="utf-8")
    sql = override_date_declarations(
        sql,
        build_start_date=args.build_start_date,
        end_date=full_end_date,
    )
    return apply_replacements(sql, replacement_map(args.project, args.scratch_dataset, "full"))


def render_window_sql(path: Path, args: argparse.Namespace) -> tuple[str, list[bigquery.ScalarQueryParameter]]:
    sql = path.read_text(encoding="utf-8")
    sql = apply_replacements(sql, replacement_map(args.project, args.scratch_dataset, "window"))
    query_parameters = [
        bigquery.ScalarQueryParameter("business_date", "STRING", args.business_date or args.date_to),
        bigquery.ScalarQueryParameter("date_from", "STRING", args.date_from),
        bigquery.ScalarQueryParameter("date_to", "STRING", args.date_to),
        bigquery.ScalarQueryParameter("warehouse_mode", "STRING", args.warehouse_mode),
    ]
    return sql, query_parameters


def create_copy_sql(spec: TableSpec, args: argparse.Namespace, full_end_date: str) -> str:
    return f"""
CREATE OR REPLACE TABLE {spec.window_ref(args.project, args.scratch_dataset)} AS
SELECT *
FROM {spec.full_ref(args.project, args.scratch_dataset)}
WHERE trade_date BETWEEN DATE {literal(args.build_start_date)} AND DATE {literal(full_end_date)};
""".strip()


def compare_diff_predicate(
    spec: TableSpec,
    args: argparse.Namespace,
    schema: Iterable[bigquery.SchemaField],
) -> str:
    compared_columns = [
        field
        for field in schema
        if field.name not in spec.key_columns and field.name not in IGNORED_COMPARE_COLUMNS
    ]
    diff_terms = []
    for field in compared_columns:
        col = quote_identifier(field.name)
        if field.field_type.upper() in FLOAT_TYPES:
            diff_terms.append(
                f"((f.{col} IS NULL) != (w.{col} IS NULL) "
                f"OR (f.{col} IS NOT NULL AND w.{col} IS NOT NULL "
                f"AND ABS(SAFE_CAST(f.{col} AS FLOAT64) - SAFE_CAST(w.{col} AS FLOAT64)) > {args.float_tolerance}))"
            )
        else:
            diff_terms.append(f"(f.{col} IS DISTINCT FROM w.{col})")
    return "\n    OR ".join(diff_terms) if diff_terms else "FALSE"


def build_compare_sql(spec: TableSpec, args: argparse.Namespace, schema: Iterable[bigquery.SchemaField]) -> str:
    diff_predicate = compare_diff_predicate(spec, args, schema)
    using_keys = ", ".join(quote_identifier(col) for col in spec.key_columns)
    return f"""
WITH full_rows AS (
  SELECT TRUE AS __in_full, *
  FROM {spec.full_ref(args.project, args.scratch_dataset)}
  WHERE trade_date BETWEEN DATE {literal(args.date_from)} AND DATE {literal(args.date_to)}
),
window_rows AS (
  SELECT TRUE AS __in_window, *
  FROM {spec.window_ref(args.project, args.scratch_dataset)}
  WHERE trade_date BETWEEN DATE {literal(args.date_from)} AND DATE {literal(args.date_to)}
),
mismatches AS (
  SELECT
    f AS full_row,
    w AS window_row
  FROM full_rows AS f
  FULL OUTER JOIN window_rows AS w
  USING ({using_keys})
  WHERE f.__in_full IS NULL
    OR w.__in_window IS NULL
    OR {diff_predicate}
)
SELECT
  {literal(spec.table_name)} AS table_name,
  DATE {literal(args.date_from)} AS compare_start_date,
  DATE {literal(args.date_to)} AS compare_end_date,
  COUNT(*) AS mismatch_count
FROM mismatches
""".strip()


def build_diff_sample_sql(spec: TableSpec, args: argparse.Namespace, schema: Iterable[bigquery.SchemaField]) -> str:
    diff_predicate = compare_diff_predicate(spec, args, schema)
    using_keys = ", ".join(quote_identifier(col) for col in spec.key_columns)
    return f"""
WITH full_rows AS (
  SELECT TRUE AS __in_full, *
  FROM {spec.full_ref(args.project, args.scratch_dataset)}
  WHERE trade_date BETWEEN DATE {literal(args.date_from)} AND DATE {literal(args.date_to)}
),
window_rows AS (
  SELECT TRUE AS __in_window, *
  FROM {spec.window_ref(args.project, args.scratch_dataset)}
  WHERE trade_date BETWEEN DATE {literal(args.date_from)} AND DATE {literal(args.date_to)}
),
mismatches AS (
  SELECT
    f AS full_row,
    w AS window_row
  FROM full_rows AS f
  FULL OUTER JOIN window_rows AS w
  USING ({using_keys})
  WHERE f.__in_full IS NULL
    OR w.__in_window IS NULL
    OR {diff_predicate}
)
SELECT
  {literal(spec.table_name)} AS table_name,
  DATE {literal(args.date_from)} AS compare_start_date,
  DATE {literal(args.date_to)} AS compare_end_date,
  TO_JSON_STRING(STRUCT(TO_JSON_STRING(full_row) AS full_row_json, TO_JSON_STRING(window_row) AS window_row_json)) AS diff_sample_json
FROM mismatches
LIMIT {max(0, int(args.max_diff_samples))}
""".strip()


def reset_jsonl(path_value: str) -> None:
    if not path_value:
        return
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def append_jsonl(path_value: str, payload: dict[str, object]) -> None:
    if not path_value:
        return
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def run_query(
    client: bigquery.Client,
    sql: str,
    *,
    description: str,
    location: str,
    query_parameters: list[bigquery.ScalarQueryParameter] | None = None,
) -> bigquery.table.RowIterator:
    print(f"[run] {description}")
    job_config = bigquery.QueryJobConfig(
        query_parameters=query_parameters or [],
        use_query_cache=False,
    )
    job = client.query(sql, job_config=job_config, location=location)
    return job.result()


def ensure_dataset(client: bigquery.Client, args: argparse.Namespace) -> None:
    dataset = bigquery.Dataset(f"{args.project}.{args.scratch_dataset}")
    dataset.location = args.location
    dataset.description = "Scratch dataset for index/market windowed refresh equivalence QA."
    client.create_dataset(dataset, exists_ok=True)


def main() -> int:
    args = parse_args()
    full_end_date = parse_date(args.date_to).isoformat()
    business_date = args.business_date or args.date_to

    print("Index/market windowed refresh equivalence QA")
    print(f"  project={args.project}")
    print(f"  scratch_dataset={args.scratch_dataset}")
    print(f"  build_start_date={args.build_start_date}")
    print(f"  date_from={args.date_from}")
    print(f"  date_to={args.date_to}")
    print(f"  business_date={business_date}")
    print(f"  full_end_date={full_end_date}")
    print(f"  summary_output_jsonl={args.summary_output_jsonl or '(disabled)'}")
    print(f"  diff_sample_output_jsonl={args.diff_sample_output_jsonl or '(disabled)'}")
    print(f"  dry_run={args.dry_run}")

    if args.dry_run:
        print("Dry-run plan:")
        print("  1. Create scratch dataset.")
        for path in FULL_SQL_FILES:
            print(f"  2. Render and run canonical full SQL: {path}")
        for spec in TABLES:
            print(f"  3. Copy {spec.table_name}_full -> {spec.table_name}_window")
        for path in WINDOW_SQL_FILES:
            print(f"  4. Render and run window SQL: {path}")
        print("  5. Compare *_window vs *_full for the requested window.")
        if args.summary_output_jsonl:
            print(f"  6. Write per-table mismatch summaries to {args.summary_output_jsonl}.")
        if args.diff_sample_output_jsonl:
            print(f"  7. Write up to {args.max_diff_samples} mismatch samples per failing table to {args.diff_sample_output_jsonl}.")
        return 0

    reset_jsonl(args.summary_output_jsonl)
    reset_jsonl(args.diff_sample_output_jsonl)
    client = bigquery.Client(project=args.project, location=args.location)
    ensure_dataset(client, args)

    for path in FULL_SQL_FILES:
        sql = render_full_sql(path, args, full_end_date)
        run_query(client, sql, description=f"canonical full shadow: {path}", location=args.location)

    for spec in TABLES:
        run_query(client, create_copy_sql(spec, args, full_end_date), description=f"copy window seed: {spec.table_name}", location=args.location)

    for path in WINDOW_SQL_FILES:
        window_sql, window_params = render_window_sql(path, args)
        run_query(
            client,
            window_sql,
            description=f"windowed refresh shadow: {path}",
            location=args.location,
            query_parameters=window_params,
        )

    failures = []
    for spec in TABLES:
        table = client.get_table(table_id(args.project, args.scratch_dataset, f"{spec.table_name}_full"))
        rows = list(run_query(client, build_compare_sql(spec, args, table.schema), description=f"compare {spec.table_name}", location=args.location))
        result = rows[0]
        mismatch_count = result["mismatch_count"]
        print(
            f"[compare] {spec.table_name}: mismatch_count={mismatch_count} "
            f"window={result['compare_start_date']}..{result['compare_end_date']}"
        )
        append_jsonl(
            args.summary_output_jsonl,
            {
                "table_name": spec.table_name,
                "compare_start_date": result["compare_start_date"],
                "compare_end_date": result["compare_end_date"],
                "mismatch_count": mismatch_count,
                "float_tolerance": args.float_tolerance,
                "scratch_dataset": args.scratch_dataset,
            },
        )
        if mismatch_count:
            failures.append((spec.table_name, mismatch_count))
            if args.diff_sample_output_jsonl and args.max_diff_samples > 0:
                sample_rows = list(
                    run_query(
                        client,
                        build_diff_sample_sql(spec, args, table.schema),
                        description=f"sample diffs {spec.table_name}",
                        location=args.location,
                    )
                )
                for sample in sample_rows:
                    append_jsonl(
                        args.diff_sample_output_jsonl,
                        {
                            "table_name": sample["table_name"],
                            "compare_start_date": sample["compare_start_date"],
                            "compare_end_date": sample["compare_end_date"],
                            "diff_sample_json": sample["diff_sample_json"],
                            "scratch_dataset": args.scratch_dataset,
                        },
                    )

    if args.cleanup:
        dataset_ref = bigquery.DatasetReference(args.project, args.scratch_dataset)
        client.delete_dataset(dataset_ref, delete_contents=True, not_found_ok=True)
        print(f"[cleanup] deleted {args.project}.{args.scratch_dataset}")

    if failures:
        print("Index/market windowed refresh equivalence QA failed:")
        for table_name, mismatch_count in failures:
            print(f"  {table_name}: {mismatch_count} mismatches")
        return 1

    print("Index/market windowed refresh equivalence QA passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
