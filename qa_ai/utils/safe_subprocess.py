"""
safe_subprocess.py - Security-hardened subprocess execution.

Rules enforced:
1. Command must be a list (no shell=True, no string commands)
2. Executable must not be in the blocked set
3. Environment variables matching secret patterns are stripped
4. cwd must exist when specified
5. Audit log at INFO for every invocation
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Optional, Sequence

logger = logging.getLogger(__name__)

# Executables that should never be run by the QA platform
_BLOCKED_EXECUTABLES: frozenset[str] = frozenset({
    "rm",
    "rmdir",
    "dd",
    "mkfs",
    "fdisk",
    "shred",
    "wipefs",
    "parted",
    "format",
    "deltree",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "init",
    "kill",
    "killall",
    "pkill",
})

# Environment variable name patterns to strip before passing to subprocess
_STRIP_ENV_KEYS: frozenset[str] = frozenset({
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "GITHUB_TOKEN",
    "GITHUB_PAT",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "DATABASE_URL",
    "DATABASE_PASSWORD",
    "DB_PASSWORD",
    "SECRET_KEY",
    "DJANGO_SECRET_KEY",
    "FLASK_SECRET_KEY",
    "JWT_SECRET",
    "STRIPE_SECRET_KEY",
    "STRIPE_API_KEY",
    "TWILIO_AUTH_TOKEN",
    "SENDGRID_API_KEY",
    "SLACK_BOT_TOKEN",
    "SLACK_SIGNING_SECRET",
})

# Additional pattern suffixes that are always stripped
_STRIP_ENV_SUFFIXES: tuple[str, ...] = (
    "_SECRET",
    "_SECRET_KEY",
    "_API_KEY",
    "_AUTH_TOKEN",
    "_ACCESS_TOKEN",
    "_PRIVATE_KEY",
    "_PASSWORD",
    "_PASSWD",
)


class CommandBlockedError(ValueError):
    """Raised when the requested executable is on the blocked list."""


class SubprocessTimeoutError(TimeoutError):
    """Raised when a subprocess exceeds its timeout."""


class InvalidCwdError(ValueError):
    """Raised when the specified cwd does not exist."""


def _sanitize_env(env: dict[str, str]) -> dict[str, str]:
    """Return a copy of env with secret keys removed."""
    sanitized: dict[str, str] = {}
    for key, value in env.items():
        upper = key.upper()
        if upper in _STRIP_ENV_KEYS:
            continue
        if any(upper.endswith(suffix) for suffix in _STRIP_ENV_SUFFIXES):
            continue
        sanitized[key] = value
    return sanitized


def run_safe(
    cmd: Sequence[str],
    *,
    cwd: Optional[str] = None,
    timeout: Optional[float] = None,
    capture_output: bool = False,
    text: bool = False,
    check: bool = False,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """
    Run a subprocess command with security hardening.

    Args:
        cmd: Command as a list of strings (no shell strings accepted)
        cwd: Working directory (must exist if specified)
        timeout: Seconds before TimeoutExpired
        capture_output: Capture stdout/stderr
        text: Decode output as text
        check: Raise on non-zero exit code
        **kwargs: Passed through to subprocess.run

    Raises:
        TypeError: If cmd is not a list/sequence of strings
        CommandBlockedError: If the executable is on the blocked list
        InvalidCwdError: If cwd does not exist
        SubprocessTimeoutError: If the process times out
    """
    if isinstance(cmd, str):
        raise TypeError(
            "run_safe() requires a list command, not a string. "
            "Use shlex.split() to convert: run_safe(shlex.split(cmd_str))"
        )

    executable = os.path.basename(str(cmd[0]))
    if executable in _BLOCKED_EXECUTABLES:
        raise CommandBlockedError(
            f"Execution of '{executable}' is blocked by the QA platform security policy. "
            f"Blocked executables: {sorted(_BLOCKED_EXECUTABLES)}"
        )

    if cwd is not None and not Path(cwd).exists():
        raise InvalidCwdError(
            f"Specified cwd does not exist: {cwd!r}"
        )

    # Sanitize environment
    base_env = kwargs.pop("env", None) or dict(os.environ)
    safe_env = _sanitize_env(base_env)

    logger.info("run_safe: %s (cwd=%s, timeout=%s)", " ".join(str(c) for c in cmd), cwd, timeout)

    try:
        return subprocess.run(
            list(cmd),
            cwd=cwd,
            timeout=timeout,
            capture_output=capture_output,
            text=text,
            check=check,
            env=safe_env,
            **kwargs,
        )
    except subprocess.TimeoutExpired as exc:
        raise SubprocessTimeoutError(
            f"Command timed out after {timeout}s: {' '.join(str(c) for c in cmd)}"
        ) from exc
