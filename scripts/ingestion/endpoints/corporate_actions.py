"""公司行为手工补采 endpoint group。"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from scripts.ingestion.common.endpoint_runner import ingest_plan

logger = logging.getLogger(__name__)

ENDPOINTS = ["dividend"]


def ingest(
    client,
    manifest: dict[str, Any],
    business_date: date,
    ingestion_run_id: str,
    **kwargs,
) -> list[dict[str, Any]]:
    """采集公司行为 endpoint group。"""
    return ingest_plan(
        client=client,
        plan=kwargs["plan"],
        business_date=business_date,
        skip_gcs_write=kwargs.get("skip_gcs_write", False),
    )
