"""维度快照采集：stock_basic, trade_cal, namechange。Phase 0 stub，Phase 1 实现。"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

ENDPOINTS = ["stock_basic", "trade_cal", "namechange"]


def ingest(client, manifest: dict[str, Any], business_date: date,
           ingestion_run_id: str, **kwargs) -> list[dict[str, Any]]:
    """采集维度快照 endpoint group。"""
    raise NotImplementedError("Phase 1 实现")
