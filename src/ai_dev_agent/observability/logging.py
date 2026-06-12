"""Structured logging with a bound trace id and secret masking."""

from __future__ import annotations

import logging
import re
import sys
import uuid

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars
from structlog.typing import EventDict, WrappedLogger

_SECRET_RE = re.compile(
    r"gh[ps]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}"
)
_REDACTED = "***REDACTED***"


def redact(text: str) -> str:
    return _SECRET_RE.sub(_REDACTED, text)


def mask_secrets(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    for key, value in event_dict.items():
        if isinstance(value, str):
            event_dict[key] = redact(value)
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    numeric_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            mask_secrets,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def new_trace_id() -> str:
    return uuid.uuid4().hex


def bind_trace_id(trace_id: str) -> None:
    bind_contextvars(trace_id=trace_id)


def reset_trace() -> None:
    clear_contextvars()


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
