"""结构化日志（自动脱敏）。"""

from __future__ import annotations

import logging
import re
import sys

# 自动脱敏模式：匹配常见 token / key 模式。
_KEY_VALUE_SECRET_PATTERN = re.compile(
    r"\b([A-Za-z0-9_.-]*(?:token|key|secret|password)[A-Za-z0-9_.-]*|authorization)\b"
    r"\s*(?:[:=]\s*|\s+)(?:Bearer\s+)?[^\s,;]+",
    re.IGNORECASE,
)
_BEARER_PATTERN = re.compile(r"\bBearer\s+[^\s,;]+", re.IGNORECASE)


def _scrub_text(value: str) -> str:
    """脱敏已格式化的日志文本。"""
    value = _KEY_VALUE_SECRET_PATTERN.sub(lambda m: f"{m.group(1)}=***", value)
    return _BEARER_PATTERN.sub("Bearer ***", value)


class _ScrubbingFilter(logging.Filter):
    """自动过滤日志中的敏感信息。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _scrub_text(record.getMessage())
        record.args = ()
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
