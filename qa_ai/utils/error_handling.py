"""
error_handling.py - Centralized helpers for observable safe fallbacks.

Use log_and_fallback() to replace silent `except Exception: pass` blocks
while preserving the safe-fallback behavior and making failures visible.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")


def log_and_fallback(
    fn: Callable[[], T],
    default: T,
    logger_name: str,
    context: str = "",
    level: int = logging.WARNING,
) -> T:
    """
    Call fn(). If it raises, log the exception and return default.

    Args:
        fn: Zero-argument callable to attempt
        default: Value to return if fn raises
        logger_name: Logger name (typically __name__ of the caller)
        context: Optional label for the log message (e.g. "parse_pubspec")
        level: Log level for the exception message (default: WARNING)
    """
    try:
        return fn()
    except Exception as exc:
        log = logging.getLogger(logger_name)
        label = f"[{context}] " if context else ""
        log.log(level, "%s%s: %s", label, type(exc).__name__, exc)
        return default


def safe_fallback(
    default: Any,
    logger_name: str,
    context: str = "",
    level: int = logging.WARNING,
) -> Callable:
    """
    Decorator factory. Wraps a function so any exception returns `default`.

    Usage:
        @safe_fallback(default=[], logger_name=__name__)
        def risky_function(x):
            ...
    """
    import functools

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return log_and_fallback(
                lambda: fn(*args, **kwargs),
                default=default,
                logger_name=logger_name,
                context=context or fn.__name__,
                level=level,
            )
        return wrapper
    return decorator
