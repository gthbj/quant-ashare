"""GCS staging / publish 写入。Phase 0 stub，Phase 1 实现。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)


def write_parquet_to_gcs(
    rows: list[dict[str, Any]],
    schema: pa.Schema,
    bucket: str,
    prefix: str,
    partition_date: str,
    ingestion_run_id: str,
    staging_prefix: str = "_staging/",
) -> str:
    """将行数据写为 Parquet 到 GCS staging 路径，校验后 publish 到正式路径。

    流程：
    1. 写 staging prefix
    2. schema 校验
    3. publish 到正式 prefix

    Returns: 正式 GCS URI
    """
    # Phase 1 实现
    raise NotImplementedError("Phase 1 实现")


def read_schema_contract(contract_path: Path) -> dict[str, Any]:
    """读取 schema contract JSON。"""
    import json
    with open(contract_path) as f:
        return json.load(f)
