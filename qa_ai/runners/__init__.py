"""
qa_ai/runners/__init__.py - Runners package initialization.
"""

from qa_ai.runners.base_runner import BaseRunner
from qa_ai.runners.api_runner import APIRunner

__all__ = [
    "BaseRunner",
    "APIRunner",
]

try:
    from qa_ai.runners.playwright_runner import PlaywrightRunner
    __all__.append("PlaywrightRunner")
except ImportError:
    pass
