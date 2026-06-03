"""结构化日志（自动脱敏）。Phase 0 实现基础脱敏 filter。"""

from __future__ import annotations

import logging
import re
import sys

# 自动脱敏模式：匹配常见 token / key 模式
_SENSITIVE_PATTERNS = [
    re.compile(r'(token|key|secret|password|authorization)[\s=:]+[\w\-\.]+', re.IGNORECASE),
    re.compile(r'Bearer\s+[\w\-\.]+', re.IGNORECASE),
]


class _ScrubbingFilter(logging.Filter):
    """自动过滤日志中的敏感信息。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pat in _SENSITIVE_PATTERNS:
                record.msg = pat.sub(lambda m: m.group().split('=')[0].split(':')[0] + '=***', record.msg)
        return True


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """配置结构化日志，自动安装脱敏 filter。"""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_ScrubbingFilter())
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[handler],
    )
    return logging.getLogger("ingestion")


def redact_token(value: str) -> str:
    """脱敏 token：只保留前 4 和后 4 字符。"""
    if not value or len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"
