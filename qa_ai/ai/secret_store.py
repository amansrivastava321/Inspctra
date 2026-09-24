"""
secret_store.py - Safe API key handling for model providers.

Rules:
- Do NOT store raw API keys in SQLite.
- Read keys from os.environ only at call time.
- Never log key values — log env var names only.
- Support: env var reference, optional keyring (if installed).
- Missing key → CapabilityGap result, never raise.
- Keys are single-use per call; no caching of key values.

No shell. No subprocess. No eval.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ── Key-like pattern (for redaction / validation) ──────────────────────────────

_KEY_PATTERN = re.compile(
    r"(password|passwd|token|secret|api[_\-]key|bearer|auth|credential|private[_\-]key)",
    re.I,
)

# Provider env var convention (add more as needed)
_KNOWN_ENV_VARS: dict[str, str] = {
    "openrouter":           "OPENROUTER_API_KEY",
    "openai":               "OPENAI_API_KEY",
    "anthropic":            "ANTHROPIC_API_KEY",
    "gemini":               "GOOGLE_API_KEY",
    "custom_openai":        "CUSTOM_OPENAI_API_KEY",
}


@dataclass
class KeyResult:
    found: bool
    key: Optional[str]       # None when not found — caller must handle
    env_var: str             # env var name (safe to log)
    provider_id: str
    capability_gap: Optional[str]


def resolve_api_key(
    provider_id: str,
    api_key_env: Optional[str] = None,
) -> KeyResult:
    """
    Resolve an API key from environment only.

    Args:
        provider_id: Logical provider identifier (e.g. "openrouter").
        api_key_env: Explicit env var name.  Falls back to known convention.

    Returns:
        KeyResult. If key not found, found=False and capability_gap is set.
        Never raises.
    """
    env_var = api_key_env or _KNOWN_ENV_VARS.get(provider_id, "")
    if not env_var:
        return KeyResult(
            found=False,
            key=None,
            env_var="",
            provider_id=provider_id,
            capability_gap=(
                f"No api_key_env configured for provider '{provider_id}'. "
                f"Set api_key_env in provider config."
            ),
        )

    value = os.environ.get(env_var, "").strip()
    if not value:
        logger.debug(
            "SecretStore: env var %s not set — provider %s capability gap",
            env_var, provider_id,
        )
        return KeyResult(
            found=False,
            key=None,
            env_var=env_var,
            provider_id=provider_id,
            capability_gap=(
                f"API key env var '{env_var}' is not set. "
                f"Export it before using cloud provider '{provider_id}'."
            ),
        )

    # Warn on suspiciously short or placeholder values
    if len(value) < 8 or value.lower() in ("placeholder", "changeme", "your_key_here"):
        logger.warning(
            "SecretStore: env var %s looks like a placeholder — provider %s may fail",
            env_var, provider_id,
        )

    return KeyResult(
        found=True,
        key=value,
        env_var=env_var,
        provider_id=provider_id,
        capability_gap=None,
    )


def key_available(provider_id: str, api_key_env: Optional[str] = None) -> bool:
    """Quick boolean check — does an API key exist for this provider?"""
    return resolve_api_key(provider_id, api_key_env).found


def redact_key(value: str) -> str:
    """
    Redact a key value for display/logging.

    Shows first 4 + last 2 characters only.
    """
    if not value or len(value) < 8:
        return "[REDACTED]"
    return f"{value[:4]}…{value[-2:]} [REDACTED]"


def validate_env_var_name(name: str) -> bool:
    """
    Validate an env var name is safe (no injection risk).
    Only allow uppercase letters, digits, underscores.
    """
    return bool(re.match(r"^[A-Z][A-Z0-9_]{0,127}$", name))


def safe_env_var_name(name: str) -> Optional[str]:
    """Return validated env var name or None if invalid."""
    if validate_env_var_name(name):
        return name
    logger.warning("SecretStore: rejected invalid env_var name: %r", name)
    return None
