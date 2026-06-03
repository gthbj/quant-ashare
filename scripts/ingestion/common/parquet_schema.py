"""Parquet schema 校验与 cast。Phase 0 stub，Phase 1 实现。"""

from __future__ import annotations

import pyarrow as pa

# Tushare STRING 字段 -> Parquet UTF-8
# Tushare FLOAT 字段 -> Parquet float64
# Tushare INTEGER 字段 -> Parquet int64

TUSHARE_TYPE_MAP = {
    "STRING": pa.string(),
    "FLOAT": pa.float64(),
    "INTEGER": pa.int64(),
}


def build_parquet_schema(contract_fields: list[dict]) -> pa.Schema:
    """从 schema contract 的 fields 列表构建 PyArrow Schema。"""
    fields = []
    for f in contract_fields:
        pa_type = TUSHARE_TYPE_MAP.get(f["type"])
        if pa_type is None:
            raise ValueError(f"Unknown type: {f['type']} for field {f['name']}")
        fields.append(pa.field(f["name"], pa_type, nullable=f.get("nullable", True)))
    return pa.schema(fields)


def cast_rows(rows: list[dict], schema: pa.Schema) -> pa.Table:
    """将原始行数据按 schema cast 为 PyArrow Table。"""
    arrays = []
    for field in schema:
        values = [row.get(field.name) for row in rows]
        arrays.append(pa.array(values, type=field.type))
    return pa.table(arrays, schema=schema)
