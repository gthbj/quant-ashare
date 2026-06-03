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
    """将原始行数据按 schema cast 为 PyArrow Table。

    对 FLOAT/INTEGER 字段做 None-safe 数值强转：
    Tushare 偶尔给 FLOAT 返回字符串、给 INT 返回浮点。
    """
    arrays = []
    for field in schema:
        values = [row.get(field.name) for row in rows]
        if pa.types.is_floating(field.type):
            values = [_safe_float(v) for v in values]
        elif pa.types.is_integer(field.type):
            values = [_safe_int(v) for v in values]
        arrays.append(pa.array(values, type=field.type))
    return pa.table(arrays, schema=schema)


def _safe_float(v):
    """None-safe float 转换，无法转换返回 None。"""
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _safe_int(v):
    """None-safe int 转换，无法转换返回 None。"""
    if v is None:
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None
