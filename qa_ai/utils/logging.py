"""
logging.py - Structured logging setup for the QA platform.
Configures Python logging with rich formatting.
"""

import logging
import sys
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    use_rich: bool = False,
) -> None:
    """
    Configure logging for the QA platform.

    Args:
        level: Logging level (default: INFO)
        format_string: Custom format string
        use_rich: If True, use rich for console formatting
    """
    if format_string is None:
        format_string = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        datefmt = "%H:%M:%S"
    else:
        datefmt = None

    handler: logging.Handler

    if use_rich:
        try:
            from rich.logging import RichHandler

            handler = RichHandler(
                rich_tracebacks=True,
                show_time=True,
                show_path=False,
            )
            format_string = "%(message)s"
            datefmt = None
        except ImportError:
            handler = logging.StreamHandler(sys.stderr)
    else:
        handler = logging.StreamHandler(sys.stderr)

    logging.basicConfig(
        level=level,
        format=format_string,
        datefmt=datefmt,
        handlers=[handler],
        force=True,
    )

    # Quiet noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger for a module."""
    return logging.getLogger(name)
