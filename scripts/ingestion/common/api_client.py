"""Tushare/Tinyshare API 客户端。Phase 0 stub，Phase 1 实现。"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Tushare 官方单次返回上限
TUSHARE_ROW_LIMIT = 5000
# 请求间隔（秒）
DEFAULT_THROTTLE_SECONDS = 0.3
# 重试次数
DEFAULT_MAX_RETRIES = 3
# 超时（秒）
DEFAULT_TIMEOUT_SECONDS = 60


class TushareClient:
    """Tushare API 客户端，内置节流、重试和返回上限检查。"""

    def __init__(self, token: str | None = None,
                 base_url: str = "https://api.tushare.pro",
                 throttle: float = DEFAULT_THROTTLE_SECONDS,
                 max_retries: int = DEFAULT_MAX_RETRIES,
                 timeout: int = DEFAULT_TIMEOUT_SECONDS):
        self.token = token or os.environ.get("TUSHARE_TOKEN", "")
        self.base_url = base_url
        self.throttle = throttle
        self.max_retries = max_retries
        self.timeout = timeout
        self._last_request_time = 0.0

    def query(self, api_name: str, params: dict[str, Any] | None = None,
              fields: str | None = None) -> list[dict[str, Any]]:
        """调用 Tushare API，返回行列表。

        自动处理：
        - 节流（throttle）
        - 重试（timeout / 5xx）
        - 返回上限命中检测
        """
        self._throttle()
        payload: dict[str, Any] = {
            "api_name": api_name,
            "token": self.token,
            "params": params or {},
        }
        if fields:
            payload["fields"] = fields

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.post(
                    f"{self.base_url}",
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") != 0:
                    raise RuntimeError(f"Tushare API error: {data.get('msg', 'unknown')}")
                items = data.get("data", {}).get("items", [])
                columns = data.get("data", {}).get("fields", [])
                rows = [dict(zip(columns, row)) for row in items]
                # 返回上限命中检测
                if len(rows) >= TUSHARE_ROW_LIMIT:
                    logger.warning(
                        "API %s returned %d rows (hit limit %d). "
                        "May need to split request.", api_name, len(rows), TUSHARE_ROW_LIMIT)
                return rows
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_error = e
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.warning("Retry %d/%d for %s after %ds: %s",
                                   attempt + 1, self.max_retries, api_name, wait, e)
                    time.sleep(wait)
            except requests.exceptions.HTTPError as e:
                if resp.status_code >= 500 and attempt < self.max_retries:
                    last_error = e
                    time.sleep(2 ** attempt)
                    continue
                raise

        raise RuntimeError(f"Failed after {self.max_retries} retries: {last_error}")

    def _throttle(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.throttle:
            time.sleep(self.throttle - elapsed)
        self._last_request_time = time.time()

    @staticmethod
    def request_params_hash(params: dict[str, Any]) -> str:
        """计算请求参数 SHA256（用于去重）。"""
        raw = str(sorted(params.items()))
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
