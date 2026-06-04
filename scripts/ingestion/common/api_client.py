"""Tushare/Tinyshare API 客户端。Phase 0 stub，Phase 1 实现。"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Tushare 官方单次返回上限（按 endpoint 可覆盖）
DEFAULT_ROW_LIMIT = 5000
# 请求间隔（秒）
DEFAULT_THROTTLE_SECONDS = 0.3
# 重试次数
DEFAULT_MAX_RETRIES = 3
# 超时（秒）
DEFAULT_TIMEOUT_SECONDS = 60
# 单次调用最大分页数，避免 limit/offset 被接口忽略时无限循环
DEFAULT_MAX_PAGES = 100


class TushareClient:
    """Tushare API 客户端，内置节流、重试和返回上限检查。"""

    def __init__(self, token: str | None = None,
                 base_url: str = "https://api.tushare.pro",
                 throttle: float = DEFAULT_THROTTLE_SECONDS,
                 max_retries: int = DEFAULT_MAX_RETRIES,
                 timeout: int = DEFAULT_TIMEOUT_SECONDS,
                 row_limit: int = DEFAULT_ROW_LIMIT,
                 max_pages: int = DEFAULT_MAX_PAGES):
        self.token = token or os.environ.get("TUSHARE_TOKEN", "")
        self.base_url = base_url
        self.throttle = throttle
        self.max_retries = max_retries
        self.timeout = timeout
        self.row_limit = row_limit
        self.max_pages = max_pages
        self._last_request_time = 0.0

    def query(self, api_name: str, params: dict[str, Any] | None = None,
              fields: str | None = None) -> list[dict[str, Any]]:
        """调用 Tushare API，返回行列表。

        自动处理：
        - 节流（throttle）
        - 重试（timeout / 5xx）
        - limit/offset 分页；分页不能收敛时 fail-closed
        """
        base_params = params or {}
        rows: list[dict[str, Any]] = []
        seen_page_signatures: set[str] = set()

        for page_no in range(self.max_pages):
            page_params = {
                **base_params,
                "limit": self.row_limit,
                "offset": page_no * self.row_limit,
            }
            page_rows = self._query_once(api_name=api_name, params=page_params, fields=fields)
            page_signature = self._page_signature(page_rows)
            if page_signature in seen_page_signatures and page_rows:
                raise RuntimeError(
                    f"API {api_name} returned a repeated page at offset {page_params['offset']}; "
                    "limit/offset pagination did not advance."
                )
            seen_page_signatures.add(page_signature)
            rows.extend(page_rows)
            if len(page_rows) < self.row_limit:
                return rows

        raise RuntimeError(
            f"API {api_name} reached max_pages={self.max_pages} with page size {self.row_limit}; "
            "must split request to avoid silent data loss."
        )

    def _query_once(
        self,
        api_name: str,
        params: dict[str, Any],
        fields: str | None = None,
    ) -> list[dict[str, Any]]:
        self._throttle()
        payload: dict[str, Any] = {
            "api_name": api_name,
            "token": self.token,
            "params": params,
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
                return [dict(zip(columns, row)) for row in items]
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

    @staticmethod
    def _page_signature(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "empty"
        raw = repr(rows[:3]) + repr(rows[-3:]) + str(len(rows))
        return hashlib.sha256(raw.encode()).hexdigest()
