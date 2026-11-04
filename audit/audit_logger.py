from __future__ import annotations

from functools import wraps
from time import perf_counter
from typing import Any, Callable

from server.logging import get_logger

logger = get_logger("mcp.aegis.audit")

_SECRET_KEYS = {
    "token",
    "api_token",
    "password",
    "authorization",
    "secret",
    "api_key",
}


def _redact(value: Any) -> Any:
    """Drop credential fields before they are written to the audit log."""
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if str(key).lower() in _SECRET_KEYS:
                redacted[key] = "***"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value)
    return value


def audit_tool_call(tool_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that emits structured audit records for every tool invocation."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            started = perf_counter()
            logger.info(
                "tool_call_started",
                extra={
                    "extra_payload": {
                        "event": "tool_call_started",
                        "tool": tool_name,
                        "args": str(_redact(args)),
                        "kwargs": _redact(kwargs),
                    }
                },
            )
            try:
                result = func(*args, **kwargs)
                duration_ms = int((perf_counter() - started) * 1000)
                logger.info(
                    "tool_call_succeeded",
                    extra={
                        "extra_payload": {
                            "event": "tool_call_succeeded",
                            "tool": tool_name,
                            "duration_ms": duration_ms,
                        }
                    },
                )
                return result
            except Exception as exc:  # noqa: BLE001
                duration_ms = int((perf_counter() - started) * 1000)
                logger.error(
                    "tool_call_failed",
                    extra={
                        "extra_payload": {
                            "event": "tool_call_failed",
                            "tool": tool_name,
                            "duration_ms": duration_ms,
                            "error": str(exc),
                        }
                    },
                )
                raise

        return wrapper

    return decorator
