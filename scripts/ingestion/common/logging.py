"""结构化日志（脱敏）。Phase 0 stub，Phase 1 实现。"""

from __future__ import annotations

import logging
import sys


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """配置结构化日志。Token 和敏感信息不出现在日志中。"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    return logging.getLogger("ingestion")


def redact_token(value: str) -> str:
    """脱敏 token：只保留前 4 和后 4 字符。"""
    if not value or len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"
