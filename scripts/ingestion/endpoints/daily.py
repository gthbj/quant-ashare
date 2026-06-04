"""日频行情采集：daily, adj_factor, stk_limit, suspend_d, daily_basic。"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from scripts.ingestion.common.endpoint_runner import ingest_plan

logger = logging.getLogger(__name__)

ENDPOINTS = ["daily", "adj_factor", "stk_limit", "suspend_d", "daily_basic"]


def ingest(client, manifest: dict[str, Any], business_date: date,
           ingestion_run_id: str, **kwargs) -> list[dict[str, Any]]:
    """采集日频行情 endpoint group。

    Returns: 每个 endpoint 的采集结果列表
        [{"endpoint": ..., "partition_date": ..., "row_count": ..., "status": ..., ...}]
    """
    return ingest_plan(
        client=client,
        plan=kwargs["plan"],
        business_date=business_date,
        skip_gcs_write=kwargs.get("skip_gcs_write", False),
    )
