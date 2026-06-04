"""维度快照采集：stock_basic, trade_cal, namechange。"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from scripts.ingestion.common.endpoint_runner import ingest_plan

logger = logging.getLogger(__name__)

ENDPOINTS = ["stock_basic", "trade_cal", "namechange"]


def ingest(client, manifest: dict[str, Any], business_date: date,
           ingestion_run_id: str, **kwargs) -> list[dict[str, Any]]:
    """采集维度快照 endpoint group。"""
    return ingest_plan(
        client=client,
        plan=kwargs["plan"],
        business_date=business_date,
        skip_gcs_write=kwargs.get("skip_gcs_write", False),
    )
