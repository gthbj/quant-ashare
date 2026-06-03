"""日频行情采集：daily, adj_factor, stk_limit, suspend_d, daily_basic。Phase 0 stub，Phase 1 实现。"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

ENDPOINTS = ["daily", "adj_factor", "stk_limit", "suspend_d", "daily_basic"]


def ingest(client, manifest: dict[str, Any], business_date: date,
           ingestion_run_id: str, **kwargs) -> list[dict[str, Any]]:
    """采集日频行情 endpoint group。

    Returns: 每个 endpoint 的采集结果列表
        [{"endpoint": ..., "partition_date": ..., "row_count": ..., "status": ..., ...}]
    """
    # Phase 1 实现
    raise NotImplementedError("Phase 1 实现")
