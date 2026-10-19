"""
dotenv_loader.py - Optional ``.env`` support for local use.

Reads ``<project root>/.env`` (the file is gitignored; ``.env.example`` is the template) and
copies a fixed set of variables into ``os.environ``.

Deliberately narrow:
- Only the Inspectra project root is searched, never the current directory, so auditing
  another app that has its own ``.env`` cannot change this tool's configuration.
- Only ``QA_AI_*``, ``INSPECTRA_*`` and the provider key names are accepted.
- Variables already set in the real environment always win.
- Values are never logged.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DISABLE_VARIABLE = "INSPECTRA_DISABLE_DOTENV"

_ALLOWED_PREFIXES = ("QA_AI_", "INSPECTRA_")
_ALLOWED_NAMES = frozenset({
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY",
})


def _is_allowed(name: str) -> bool:
    return name in _ALLOWED_NAMES or name.startswith(_ALLOWED_PREFIXES)


def load_project_dotenv(root: Optional[Path] = None) -> Dict[str, bool]:
    """Load ``<root>/.env``. Returns ``{name: applied}`` for each allowed, non-empty entry.

    Never raises: a missing file, a missing ``python-dotenv`` or a malformed file simply
    loads nothing.
    """
    if os.environ.get(DISABLE_VARIABLE, "").strip().lower() in {"1", "true", "yes"}:
        return {}
    env_file = (root or PROJECT_ROOT) / ".env"
    if not env_file.is_file():
        return {}
    try:
        from dotenv import dotenv_values
    except ImportError:
        logger.warning("%s exists but python-dotenv is not installed; ignoring it", env_file)
        return {}
    try:
        entries = dotenv_values(env_file)
    except (OSError, UnicodeDecodeError, ValueError):
        logger.warning("Could not read %s; ignoring it", env_file)
        return {}

    applied: Dict[str, bool] = {}
    for name, value in entries.items():
        if not value or not _is_allowed(name):
            continue
        if name in os.environ:
            applied[name] = False
            continue
        os.environ[name] = value
        applied[name] = True
    if applied:
        logger.info("Loaded %d setting(s) from %s: %s", sum(applied.values()), env_file, ", ".join(sorted(applied)))
    return applied
