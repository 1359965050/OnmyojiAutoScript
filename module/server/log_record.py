# This Python file uses the following encoding: utf-8
"""Structured log record used between script subprocess and main process."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class LogRecord:
    """标准化日志记录，便于前后端解析、过滤、持久化。"""

    timestamp: str
    level: str
    script: str
    module: str
    message: str
    formatted: str
    context: Optional[Dict[str, Any]] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "LogRecord":
        data = json.loads(raw)
        return cls(**data)

    @classmethod
    def from_logging_record(
        cls,
        record: logging.LogRecord,
        script: str,
        formatted: str,
    ) -> "LogRecord":
        return cls(
            timestamp=datetime.fromtimestamp(record.created).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            level=record.levelname,
            script=script,
            module=f"{record.filename}:{record.lineno}",
            message=record.getMessage(),
            formatted=formatted,
            context=None,
        )
