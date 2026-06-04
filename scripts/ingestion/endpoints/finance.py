"""财务报告期采集：fina_indicator, income, balancesheet, cashflow。"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from scripts.ingestion.common.endpoint_runner import ingest_plan

logger = logging.getLogger(__name__)

ENDPOINTS = ["fina_indicator", "income", "balancesheet", "cashflow"]


def ingest(client, manifest: dict[str, Any], business_date: date,
           ingestion_run_id: str, **kwargs) -> list[dict[str, Any]]:
    """采集财务报告期 endpoint group。

    采用 recent rolling window 模式：
    - 每日执行近期公告/修正滚动检查
    - 有新增或修正行时写回对应报告期分区
    - 空返回记录 expected_empty / empty_return event
    """
    return ingest_plan(
        client=client,
        plan=kwargs["plan"],
        business_date=business_date,
        skip_gcs_write=kwargs.get("skip_gcs_write", False),
    )
