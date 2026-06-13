"""共享的报告 / 指标格式化工具（strategy1 只读分析脚本复用）。

把被冻结的格式化函数 `fmt_pct` / `fmt_num` / `markdown_table` 抽到单一共享实现，
供 `scripts/strategy1/` 下的只读分析脚本 import 复用，避免各脚本本地重复定义。

约束依据：`.agent/memory/DOC_CONVENTIONS.md`「分析脚本指标定义」与冻结清单测试
`tests/strategy1/test_metric_definition_freeze.py`——新脚本不得本地重定义这些
格式化函数，应复用本模块或先抽共享模块再同步更新 allowlist。

本模块刻意零重依赖（只用 stdlib + numpy/pandas），不引入 BigQuery 等重型 import，
保证可被任意脚本安全 import。
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def fmt_pct(value: Any) -> str:
    """百分比格式：非有限值返回 ``NA``，否则 ``{value*100:.2f}%``。"""
    return "NA" if value is None or not math.isfinite(float(value)) else f"{float(value) * 100:.2f}%"


def fmt_num(value: Any) -> str:
    """定点数格式：非有限值返回 ``NA``，否则保留 4 位小数。"""
    return "NA" if value is None or not math.isfinite(float(value)) else f"{float(value):.4f}"


def markdown_table(frame: pd.DataFrame, *, float_format: str = "{:.4f}") -> str:
    """把 DataFrame 渲染成 GitHub Markdown 表格。

    浮点单元用 ``float_format`` 格式化（默认 4 位小数）；非有限浮点渲染为空串、
    整数原样输出、其余转 str 并转义 ``|``。
    """
    columns = list(frame.columns)
    out = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in frame.iterrows():
        out.append("| " + " | ".join(_md_cell(row[c], float_format) for c in columns) + " |")
    return "\n".join(out)


def _md_cell(value: Any, float_format: str = "{:.4f}") -> str:
    if value is None:
        return ""
    if isinstance(value, (float, np.floating)):
        return "" if not math.isfinite(float(value)) else float_format.format(float(value))
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    return str(value).replace("|", "\\|")
