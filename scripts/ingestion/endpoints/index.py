"""指数行情采集：index_daily, index_dailybasic。Phase 0 stub，Phase 1 实现。"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

ENDPOINTS = ["index_daily", "index_dailybasic"]


def ingest(client, manifest: dict[str, Any], business_date: date,
           ingestion_run_id: str, **kwargs) -> list[dict[str, Any]]:
    """采集指数行情 endpoint group。"""
    raise NotImplementedError("Phase 1 实现")
