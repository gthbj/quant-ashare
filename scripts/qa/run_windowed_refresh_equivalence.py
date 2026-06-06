#!/usr/bin/env python3
"""Validate windowed stock refresh against canonical full SQL.

This is a periodic QA for the warehouse window refresh. It renders the existing canonical
full-refresh SQL into scratch "_full" tables, copies those tables to "_window",
runs the windowed refresh SQL against "_window", then compares the affected
window row-by-row and column-by-column.

The script does not mutate production DWD/DWS tables.
"""

from __future__ import annotations

import argparse
import datetime as dt
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
VALUATION_OBSERVATION_WINDOW = 60


@dataclass(frozen=True)
class TableSpec:
    source_dataset: str
    table_name: str
    key_columns: tuple[str, ...]
    compare_window: str

    @property
    def source_ref(self) -> str:
        return f"`data-aquarium.{self.source_dataset}.{self.table_name}`"

    def full_ref(self, project: str, scratch_dataset: str) -> str:
        return f"`{project}.{scratch_dataset}.{self.table_name}_full`"

    def window_ref(self, project: str, scratch_dataset: str) -> str:
        return f"`{project}.{scratch_dataset}.{self.table_name}_window`"


TABLES = (
    TableSpec("ashare_dwd", "dwd_stock_eod_price", ("trade_date", "sec_code"), "dwd"),
    TableSpec("ashare_dwd", "dwd_stock_eod_valuation", ("trade_date", "sec_code"), "dwd"),
    TableSpec("ashare_dws", "dws_stock_universe_daily", ("trade_date", "sec_code"), "dwd"),
    TableSpec("ashare_dws", "dws_stock_feature_price_daily", ("trade_date", "sec_code", "feature_version"), "dwd"),
    TableSpec("ashare_dws", "dws_stock_feature_valuation_daily", ("trade_date", "sec_code", "feature_version"), "dwd"),
    TableSpec("ashare_dws", "dws_stock_feature_fin_daily", ("trade_date", "sec_code", "feature_version"), "dwd"),
    TableSpec("ashare_dws", "dws_stock_label_daily", ("trade_date", "sec_code", "label_version"), "label"),
    TableSpec("ashare_dws", "dws_stock_feature_daily_v0", ("trade_date", "sec_code", "feature_version"), "label"),
    TableSpec(
        "ashare_dws",
        "dws_stock_sample_daily",
        ("trade_date", "sec_code", "feature_version", "label_version"),
        "label",
    ),
)

FULL_SQL_FILES = (
    Path("sql/dwd/01_dwd_stock_eod_price.sql"),
    Path("sql/dwd/02_dwd_stock_eod_valuation.sql"),
    Path("sql/dws/01_dws_stock_universe_daily.sql"),
    Path("sql/dws/02_dws_stock_feature_price_daily.sql"),
    Path("sql/dws/03_dws_stock_feature_valuation_daily.sql"),
    Path("sql/dws/07_dws_stock_feature_fin_daily.sql"),
    Path("sql/dws/04_dws_stock_label_daily.sql"),
    Path("sql/dws/05_dws_stock_feature_daily_v0.sql"),
    Path("sql/dws/06_dws_stock_sample_daily.sql"),
)

WINDOW_SQL_FILE = Path("sql/incremental/01_refresh_stock_dwd_dws_window.sql")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build full/window shadow tables and compare windowed refresh values.",
    )
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--location", default=LOCATION)
    parser.add_argument("--scratch-dataset", default=SCRATCH_DATASET)
    parser.add_argument("--build-start-date", default="2024-01-01")
    parser.add_argument("--lookback-start-date", default="2023-01-01")
    parser.add_argument("--date-from", default="2025-06-02")
    parser.add_argument("--date-to", default="2025-06-13")
    parser.add_argument("--business-date", default="")
    parser.add_argument("--warehouse-mode", default="backfill")
    parser.add_argument("--float-tolerance", type=float, default=1e-8)
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without running BigQuery jobs")
    parser.add_argument("--cleanup", action="store_true", help="Delete scratch dataset after a successful run")
    return parser.parse_args()


def parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def quote_identifier(name: str) -> str:
    return f"`{name}`"


def literal(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def query_ref(project: str, dataset: str, table: str) -> str:
    return f"`{project}.{dataset}.{table}`"


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


def override_date_declarations(
    sql: str,
    *,
    build_start_date: str,
    lookback_start_date: str,
    end_date: str,
) -> str:
    replacements = {
        r"DECLARE dwd_start_date DATE DEFAULT DATE '2019-01-01';": f"DECLARE dwd_start_date DATE DEFAULT DATE '{build_start_date}';",
        r"DECLARE dwd_end_date DATE DEFAULT CURRENT_DATE\('Asia/Shanghai'\);": f"DECLARE dwd_end_date DATE DEFAULT DATE '{end_date}';",
        r"DECLARE lookback_start_date DATE DEFAULT DATE '2018-01-01';": f"DECLARE lookback_start_date DATE DEFAULT DATE '{lookback_start_date}';",
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
        lookback_start_date=args.lookback_start_date,
        end_date=full_end_date,
    )
    return apply_replacements(sql, replacement_map(args.project, args.scratch_dataset, "full"))


def render_window_sql(args: argparse.Namespace) -> tuple[str, list[bigquery.ScalarQueryParameter]]:
    sql = WINDOW_SQL_FILE.read_text(encoding="utf-8")
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


def compare_window_dates(spec: TableSpec, args: argparse.Namespace, label_start_date: str) -> tuple[str, str]:
    if spec.compare_window == "label":
        return label_start_date, args.date_to
    return args.date_from, args.date_to


def label_start_date_sql(args: argparse.Namespace) -> str:
    write_start = args.date_from or args.date_to
    return f"""
SELECT CAST(GREATEST(
  COALESCE(
    (
      SELECT MAX(cal_date)
      FROM `{args.project}.ashare_dim.dim_trade_calendar`
      WHERE exchange = 'SSE'
        AND is_open = 1
        AND trade_date_seq <= (
          SELECT MIN(trade_date_seq)
          FROM `{args.project}.ashare_dim.dim_trade_calendar`
          WHERE exchange = 'SSE'
            AND is_open = 1
            AND cal_date >= DATE {literal(write_start)}
        ) - 20
    ),
    DATE_SUB(DATE {literal(write_start)}, INTERVAL 35 DAY)
  ),
  DATE {literal(args.build_start_date)}
) AS STRING) AS label_start_date
""".strip()


def valuation_required_build_start_sql(args: argparse.Namespace) -> str:
    write_start = args.date_from or args.date_to
    return f"""
WITH first_write AS (
  SELECT
    sec_code,
    MIN(trade_date) AS first_write_trade_date
  FROM `{args.project}.ashare_dwd.dwd_stock_eod_valuation`
  WHERE trade_date BETWEEN DATE {literal(write_start)} AND DATE {literal(args.date_to)}
  GROUP BY sec_code
),
ranked AS (
  SELECT
    v.sec_code,
    v.trade_date,
    ROW_NUMBER() OVER (
      PARTITION BY v.sec_code
      ORDER BY v.trade_date DESC
    ) AS obs_rank_desc
  FROM `{args.project}.ashare_dwd.dwd_stock_eod_valuation` AS v
  JOIN first_write AS f
    ON v.sec_code = f.sec_code
   AND v.trade_date <= f.first_write_trade_date
  WHERE v.trade_date BETWEEN DATE '2019-01-01' AND DATE {literal(args.date_to)}
),
read_bounds AS (
  SELECT
    sec_code,
    MIN(trade_date) AS read_start_date,
    COUNT(*) AS read_obs_count
  FROM ranked
  WHERE obs_rank_desc <= {VALUATION_OBSERVATION_WINDOW}
  GROUP BY sec_code
)
SELECT
  CAST(MIN(read_start_date) AS STRING) AS required_build_start_date,
  COUNT(*) AS sec_code_count,
  COUNTIF(read_obs_count < {VALUATION_OBSERVATION_WINDOW}) AS sec_code_count_with_less_than_60_obs
FROM read_bounds
""".strip()


def build_compare_sql(spec: TableSpec, args: argparse.Namespace, schema: Iterable[bigquery.SchemaField], label_start_date: str) -> str:
    start_date, end_date = compare_window_dates(spec, args, label_start_date)
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
    diff_predicate = "\n    OR ".join(diff_terms) if diff_terms else "FALSE"
    using_keys = ", ".join(quote_identifier(col) for col in spec.key_columns)
    return f"""
WITH full_rows AS (
  SELECT TRUE AS __in_full, *
  FROM {spec.full_ref(args.project, args.scratch_dataset)}
  WHERE trade_date BETWEEN DATE {literal(start_date)} AND DATE {literal(end_date)}
),
window_rows AS (
  SELECT TRUE AS __in_window, *
  FROM {spec.window_ref(args.project, args.scratch_dataset)}
  WHERE trade_date BETWEEN DATE {literal(start_date)} AND DATE {literal(end_date)}
),
mismatches AS (
  SELECT 1
  FROM full_rows AS f
  FULL OUTER JOIN window_rows AS w
  USING ({using_keys})
  WHERE f.__in_full IS NULL
    OR w.__in_window IS NULL
    OR {diff_predicate}
)
SELECT
  {literal(spec.table_name)} AS table_name,
  DATE {literal(start_date)} AS compare_start_date,
  DATE {literal(end_date)} AS compare_end_date,
  COUNT(*) AS mismatch_count
FROM mismatches
""".strip()


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
    dataset.description = "Scratch dataset for windowed stock refresh equivalence QA."
    client.create_dataset(dataset, exists_ok=True)


def validate_build_start_guard(client: bigquery.Client, args: argparse.Namespace) -> None:
    rows = list(
        run_query(
            client,
            valuation_required_build_start_sql(args),
            description="validate valuation build-start lookback",
            location=args.location,
        )
    )
    row = rows[0]
    required_build_start = row["required_build_start_date"]
    if required_build_start is None:
        print("[guard] no valuation rows found for the write window; build-start lookback guard skipped")
        return

    if parse_date(args.build_start_date) > parse_date(required_build_start):
        raise ValueError(
            "build_start_date is too late for a discriminating equivalence QA run: "
            f"build_start_date={args.build_start_date}, "
            f"required_build_start_date<={required_build_start}. "
            "Move --build-start-date earlier so canonical full shadows contain the "
            "same 60-observation valuation history required by the windowed path."
        )

    print(
        "[guard] valuation build-start lookback ok: "
        f"required_build_start_date<={required_build_start}, "
        f"sec_code_count={row['sec_code_count']}, "
        f"less_than_60_obs={row['sec_code_count_with_less_than_60_obs']}"
    )


def main() -> int:
    args = parse_args()
    date_to = parse_date(args.date_to)
    full_end_date = (date_to + dt.timedelta(days=45)).isoformat()
    business_date = args.business_date or args.date_to

    print("Windowed refresh equivalence QA")
    print(f"  project={args.project}")
    print(f"  scratch_dataset={args.scratch_dataset}")
    print(f"  build_start_date={args.build_start_date}")
    print(f"  lookback_start_date={args.lookback_start_date}")
    print(f"  date_from={args.date_from}")
    print(f"  date_to={args.date_to}")
    print(f"  business_date={business_date}")
    print(f"  full_end_date={full_end_date}")
    print(f"  dry_run={args.dry_run}")

    if args.dry_run:
        print("Dry-run plan:")
        print("  1. Validate build_start_date has enough valuation lookback against production DWD.")
        print("  2. Create scratch dataset.")
        for path in FULL_SQL_FILES:
            print(f"  3. Render and run canonical full SQL: {path}")
        for spec in TABLES:
            print(f"  4. Copy {spec.table_name}_full -> {spec.table_name}_window")
        print(f"  5. Render and run {WINDOW_SQL_FILE} against *_window tables.")
        print("  6. Compare *_window vs *_full for DWD and label windows.")
        return 0

    client = bigquery.Client(project=args.project, location=args.location)
    validate_build_start_guard(client, args)
    ensure_dataset(client, args)

    for path in FULL_SQL_FILES:
        sql = render_full_sql(path, args, full_end_date)
        run_query(client, sql, description=f"canonical full shadow: {path}", location=args.location)

    for spec in TABLES:
        run_query(client, create_copy_sql(spec, args, full_end_date), description=f"copy window seed: {spec.table_name}", location=args.location)

    window_sql, window_params = render_window_sql(args)
    run_query(
        client,
        window_sql,
        description="windowed refresh shadow",
        location=args.location,
        query_parameters=window_params,
    )

    label_start_rows = list(run_query(client, label_start_date_sql(args), description="compute label window start", location=args.location))
    label_start_date = label_start_rows[0]["label_start_date"]

    failures = []
    for spec in TABLES:
        table = client.get_table(table_id(args.project, args.scratch_dataset, f"{spec.table_name}_full"))
        compare_sql = build_compare_sql(spec, args, table.schema, label_start_date)
        rows = list(run_query(client, compare_sql, description=f"compare {spec.table_name}", location=args.location))
        mismatch_count = rows[0]["mismatch_count"]
        print(
            f"[compare] {spec.table_name}: mismatch_count={mismatch_count} "
            f"window={rows[0]['compare_start_date']}..{rows[0]['compare_end_date']}"
        )
        if mismatch_count:
            failures.append((spec.table_name, mismatch_count))

    if args.cleanup:
        dataset_ref = bigquery.DatasetReference(args.project, args.scratch_dataset)
        client.delete_dataset(dataset_ref, delete_contents=True, not_found_ok=True)
        print(f"[cleanup] deleted {args.project}.{args.scratch_dataset}")

    if failures:
        print("Windowed refresh equivalence QA failed:")
        for table_name, mismatch_count in failures:
            print(f"  {table_name}: {mismatch_count} mismatches")
        return 1

    print("Windowed refresh equivalence QA passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
