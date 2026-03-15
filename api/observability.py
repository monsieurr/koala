"""Lightweight observability helpers (structured logs + request tracing)."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
import sys
import time
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from fastapi import FastAPI
from starlette.requests import Request


REQUEST_ID_HEADER = "X-Request-Id"
_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id_ctx.get()


@dataclass(frozen=True)
class LogConfig:
    level: str
    format: str

    @classmethod
    def from_env(cls) -> "LogConfig":
        return cls(
            level=os.getenv("LOG_LEVEL", "INFO").upper(),
            format=os.getenv("LOG_FORMAT", "json").lower(),
        )


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    _reserved: set[str] = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "request_id",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        payload.update(self._extract_extras(record))
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True, default=_json_default)

    def _extract_extras(self, record: logging.LogRecord) -> dict[str, Any]:
        extras: dict[str, Any] = {}
        for key, value in record.__dict__.items():
            if key in self._reserved or key.startswith("_"):
                continue
            extras[key] = value
        return extras


def _json_default(value: Any) -> str:
    return str(value)


def configure_logging() -> None:
    config = LogConfig.from_env()
    handler = logging.StreamHandler(sys.stdout)
    if config.format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
    handler.addFilter(RequestIdFilter())

    logging.basicConfig(level=config.level, handlers=[handler], force=True)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.handlers = []
        logger.propagate = True


def configure_observability(app: FastAPI) -> None:
    configure_logging()
    app.middleware("http")(request_logging_middleware)


async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
    token = _request_id_ctx.set(request_id)
    start = time.perf_counter()
    status_code = 500
    response = None
    logger = logging.getLogger("koala.request")
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    except Exception:
        logger.exception(
            "request_failed",
            extra={
                "event": "request.error",
                "method": request.method,
                "path": request.url.path,
            },
        )
        raise
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request_complete",
            extra={
                "event": "request.complete",
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 2),
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            },
        )
        if response is not None:
            response.headers[REQUEST_ID_HEADER] = request_id
        _request_id_ctx.reset(token)
