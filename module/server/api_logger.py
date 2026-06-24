from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from module.logger import logger


API_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "log" / "api"
API_LOG_DIR.mkdir(parents=True, exist_ok=True)

MAX_API_LOG_FILES = 30
MAX_API_LOG_SIZE = 5 * 1024 * 1024


class ApiLogEntry:
    __slots__ = ("timestamp", "method", "path", "status_code", "duration", "client_ip", "user_agent", "request_body", "response_body")

    def __init__(
        self,
        timestamp: datetime,
        method: str,
        path: str,
        status_code: int,
        duration: float,
        client_ip: str,
        user_agent: str = "",
        request_body: Optional[str] = None,
        response_body: Optional[str] = None,
    ):
        self.timestamp = timestamp
        self.method = method
        self.path = path
        self.status_code = status_code
        self.duration = duration
        self.client_ip = client_ip
        self.user_agent = user_agent
        self.request_body = request_body
        self.response_body = response_body

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "duration": round(self.duration * 1000, 2),
            "client_ip": self.client_ip,
            "user_agent": self.user_agent,
            "request_body": self.request_body,
            "response_body": self.response_body,
        }

    def to_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class ApiLogger:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._current_file: Optional[Path] = None
        self._file_size = 0

    def _get_log_file_path(self) -> Path:
        today = datetime.now().date()
        return API_LOG_DIR / f"{today}_api.txt"

    def _rotate_log_file(self) -> None:
        current = self._get_log_file_path()
        if current.exists() and current.stat().st_size > MAX_API_LOG_SIZE:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = API_LOG_DIR / f"{current.stem}_{timestamp}{current.suffix}"
            current.rename(backup)

        self._current_file = current
        self._file_size = current.stat().st_size if current.exists() else 0

    def _cleanup_old_files(self) -> None:
        try:
            files = sorted(API_LOG_DIR.glob("*_api.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old_file in files[MAX_API_LOG_FILES:]:
                old_file.unlink()
        except Exception:
            pass

    async def log(self, entry: ApiLogEntry) -> None:
        async with self._lock:
            self._rotate_log_file()

            if self._current_file is None:
                self._current_file = self._get_log_file_path()

            line = entry.to_line() + "\n"
            try:
                with open(self._current_file, "a", encoding="utf-8") as f:
                    f.write(line)
                self._file_size += len(line)
            except Exception as e:
                logger.error(f"Failed to write API log: {e}")

            self._cleanup_old_files()

    def get_recent_logs(self, limit: int = 100) -> list[Dict[str, Any]]:
        log_file = self._get_log_file_path()
        if not log_file.exists():
            return []

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            entries = []
            for line in reversed(lines[-limit:]):
                try:
                    data = json.loads(line)
                    entries.append(data)
                except json.JSONDecodeError:
                    pass

            return entries[::-1]
        except Exception:
            return []

    def get_stats(self) -> Dict[str, Any]:
        log_file = self._get_log_file_path()
        if not log_file.exists():
            return {"total_requests": 0, "error_count": 0, "avg_duration_ms": 0}

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            total_requests = 0
            error_count = 0
            total_duration = 0.0

            for line in lines:
                try:
                    data = json.loads(line)
                    total_requests += 1
                    if data.get("status_code", 200) >= 400:
                        error_count += 1
                    total_duration += data.get("duration", 0)
                except json.JSONDecodeError:
                    pass

            avg_duration = total_duration / total_requests if total_requests > 0 else 0

            return {
                "total_requests": total_requests,
                "error_count": error_count,
                "avg_duration_ms": round(avg_duration, 2),
                "log_file_size": log_file.stat().st_size,
            }
        except Exception:
            return {"total_requests": 0, "error_count": 0, "avg_duration_ms": 0}


api_logger = ApiLogger()


class ApiLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        timestamp = datetime.now()

        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")

        request_body = None
        try:
            if request.method in ("POST", "PUT", "PATCH"):
                body = await request.body()
                try:
                    decoded = body.decode("utf-8")
                    if len(decoded) < 2000:
                        request_body = decoded
                    else:
                        request_body = f"[Too large: {len(decoded)} bytes]"
                except Exception:
                    request_body = "[Binary data]"
        except Exception:
            pass

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            status_code = 500
            duration = time.time() - start_time

            entry = ApiLogEntry(
                timestamp=timestamp,
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration=duration,
                client_ip=client_ip,
                user_agent=user_agent,
                request_body=request_body,
                response_body=str(exc),
            )
            await api_logger.log(entry)
            raise

        duration = time.time() - start_time

        entry = ApiLogEntry(
            timestamp=timestamp,
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration=duration,
            client_ip=client_ip,
            user_agent=user_agent,
            request_body=request_body,
        )
        await api_logger.log(entry)

        return response