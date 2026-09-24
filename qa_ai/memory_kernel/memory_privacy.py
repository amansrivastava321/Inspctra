"""
memory_privacy.py - Redact sensitive data before memory storage.

No shell. No subprocess. No eval. No secrets stored.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Redaction patterns ─────────────────────────────────────────────────────────

_PATTERNS = [
    # API keys / tokens
    (re.compile(r'\b(sk|pk|rk|ak|xk)-[A-Za-z0-9\-_]{16,}', re.I), "[REDACTED_KEY]"),
    (re.compile(r'Bearer\s+[A-Za-z0-9\-_\.]+', re.I), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r'Authorization:\s*\S+\s+\S+', re.I), "Authorization: [REDACTED]"),
    # Passwords
    (re.compile(r'password\s*[=:]\s*\S+', re.I), "password=[REDACTED]"),
    (re.compile(r'passwd\s*[=:]\s*\S+', re.I), "passwd=[REDACTED]"),
    # DB URLs
    (re.compile(r'(postgres|postgresql|mysql|mongodb|redis|sqlite):\/\/[^\s\'"]+', re.I), "[REDACTED_DB_URL]"),
    # Cookies
    (re.compile(r'cookie\s*[=:]\s*\S+', re.I), "cookie=[REDACTED]"),
    (re.compile(r'session[_-]?token\s*[=:]\s*\S+', re.I), "session_token=[REDACTED]"),
    # AWS
    (re.compile(r'AKIA[0-9A-Z]{16}', re.I), "[REDACTED_AWS_KEY]"),
    (re.compile(r'aws_secret_access_key\s*[=:]\s*\S+', re.I), "aws_secret_access_key=[REDACTED]"),
    # Generic secret=value
    (re.compile(r'secret\s*[=:]\s*\S+', re.I), "secret=[REDACTED]"),
    (re.compile(r'api_key\s*[=:]\s*\S+', re.I), "api_key=[REDACTED]"),
    # GitHub tokens
    (re.compile(r'gh[pousr]_[A-Za-z0-9]{36}', re.I), "[REDACTED_GH_TOKEN]"),
    # JWT
    (re.compile(r'eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+'), "[REDACTED_JWT]"),
]

_SENSITIVE_KEYS = frozenset({
    "password", "passwd", "secret", "api_key", "apikey", "token",
    "access_token", "refresh_token", "private_key", "auth", "authorization",
    "credential", "credentials", "db_url", "database_url", "connection_string",
    "cookie", "session", "bearer",
})


def redact_text(text: str) -> str:
    """Apply all redaction patterns to text."""
    if not text:
        return text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_json(data: Any, _depth: int = 0) -> Any:
    """Recursively redact sensitive keys in JSON-like structures."""
    if _depth > 10:
        return data
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if isinstance(k, str) and k.lower() in _SENSITIVE_KEYS:
                result[k] = "[REDACTED]"
            else:
                result[k] = redact_json(v, _depth + 1)
        return result
    if isinstance(data, list):
        return [redact_json(item, _depth + 1) for item in data]
    if isinstance(data, str):
        return redact_text(data)
    return data


def redact_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Redact a metadata dict."""
    return redact_json(meta)


def detect_sensitive_payload(text: str) -> bool:
    """Return True if text likely contains credentials."""
    low = text.lower()
    return any(k in low for k in (
        "password", "api_key", "secret", "bearer ", "authorization:",
        "private_key", "access_token",
    ))


def safe_artifact_path(artifact_root: Path, user_path: str) -> Optional[Path]:
    """
    Resolve user_path relative to artifact_root and check for traversal.

    Returns None if path escapes the root.
    No shell. No os.system. No eval.
    """
    try:
        root = artifact_root.resolve()
        candidate = (root / user_path).resolve()
        # Must stay inside artifact_root
        if not str(candidate).startswith(str(root)):
            logger.warning("Path traversal blocked: %r outside %r", user_path, str(root))
            return None
        return candidate
    except Exception as exc:
        logger.warning("safe_artifact_path error: %s", exc)
        return None
