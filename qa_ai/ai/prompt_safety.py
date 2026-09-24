"""
prompt_safety.py - Redact secrets from prompts before any model call.

Before any model call:
- Strip API keys / tokens / bearer headers.
- Strip database URLs with credentials.
- Strip Authorization headers.
- Truncate long logs.
- Flag cloud-block conditions in private mode.
- Never persist raw prompts by default.

Output: SafePromptResult with safe_prompt + audit fields.
No shell. No subprocess. No eval.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

# ── Redaction patterns ─────────────────────────────────────────────────────────

_PATTERNS = [
    # API key patterns
    (re.compile(r"sk-[A-Za-z0-9\-_]{20,}", re.I), "[REDACTED_API_KEY]"),
    (re.compile(r"sk-or-[A-Za-z0-9\-_]{20,}", re.I), "[REDACTED_OPENROUTER_KEY]"),
    # Bearer tokens
    (re.compile(r"Bearer\s+[A-Za-z0-9\-\._~+/]{20,}", re.I), "Bearer [REDACTED]"),
    # Authorization header values
    (re.compile(r"(Authorization|x-api-key|api-key|api_key):\s*[^\s\n]{10,}", re.I),
     r"\1: [REDACTED]"),
    # JWT tokens
    (re.compile(r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"),
     "[REDACTED_JWT]"),
    # Database URLs with credentials (postgres://user:pass@host, mysql://...)
    (re.compile(
        r"(postgres|postgresql|mysql|mariadb|mongodb|redis)://[^:@\s]+:[^@\s]+@[^\s]+",
        re.I),
     r"\1://[REDACTED_CREDENTIALS]@[REDACTED_HOST]"),
    # Generic high-entropy 40+ char tokens (base64-ish)
    (re.compile(r"(?<![A-Za-z0-9/+])([A-Za-z0-9+/]{40,}={0,2})(?![A-Za-z0-9/+])"),
     "[REDACTED_TOKEN]"),
    # Private key headers
    (re.compile(r"-----BEGIN\s+[A-Z ]+PRIVATE KEY-----.*?-----END\s+[A-Z ]+PRIVATE KEY-----",
                re.DOTALL | re.I),
     "[REDACTED_PRIVATE_KEY]"),
    # Hardcoded passwords in common patterns
    (re.compile(r'(password|passwd|pwd)\s*[=:]\s*["\']?[^\s"\']{4,}', re.I),
     r"\1=[REDACTED]"),
]

# Patterns considered "cloud-sensitive" content
_PRIVATE_CONTENT_SIGNALS = [
    re.compile(r"class\s+\w+", re.I),         # source code class definitions
    re.compile(r"def\s+\w+\s*\("),            # function definitions
    re.compile(r"import\s+[a-zA-Z_]"),        # import statements
    re.compile(r"Traceback\s+\(most recent"),  # stack traces
    re.compile(r"Error:\s+at\s+"),            # JS stack traces
    re.compile(r"SQLException"),              # DB errors with potential schema info
    re.compile(r"/var/www|/etc/passwd"),      # file paths
]

# Truncation limits
_LOG_MAX_CHARS = 3000
_PROMPT_MAX_CHARS = 16_000


@dataclass
class SafePromptResult:
    safe_prompt: str
    redactions_applied: List[str]
    blocked_reason: Optional[str]
    risk_level: str   # "low" | "medium" | "high" | "blocked"
    private_content_detected: bool
    original_length: int
    safe_length: int


def make_safe(
    prompt: str,
    *,
    private_mode: bool = False,
    cloud_target: bool = False,
    allow_private_to_cloud: bool = False,
    truncate_logs: bool = True,
) -> SafePromptResult:
    """
    Apply redaction and safety checks to a prompt.

    Args:
        prompt: Raw prompt text.
        private_mode: True when private_code_mode is enabled.
        cloud_target: True when the selected provider is a cloud model.
        allow_private_to_cloud: Explicit user approval to send private content to cloud.
        truncate_logs: Truncate log snippets to prevent token explosion.

    Returns:
        SafePromptResult. If blocked_reason is set, do not call the model.
    """
    original_length = len(prompt)
    safe = prompt
    redactions: List[str] = []

    # Apply all redaction patterns
    for pattern, replacement in _PATTERNS:
        new_safe, n = pattern.subn(replacement, safe)
        if n > 0:
            redactions.append(replacement.strip("[]"))
            safe = new_safe

    # Truncate if needed
    if truncate_logs and len(safe) > _PROMPT_MAX_CHARS:
        safe = safe[:_PROMPT_MAX_CHARS] + "\n[TRUNCATED]"
        redactions.append("TRUNCATED_PROMPT")

    # Detect private content
    private_detected = _has_private_content(safe)
    risk_level = _assess_risk(safe, private_detected, cloud_target)

    # Block cloud call if private content and no approval
    blocked_reason: Optional[str] = None
    if cloud_target and private_detected and not allow_private_to_cloud:
        blocked_reason = (
            "Cloud call blocked: prompt contains private code/logs. "
            "Set allow_private_to_cloud=True with user approval to proceed."
        )
        risk_level = "blocked"

    if cloud_target and private_mode and not allow_private_to_cloud:
        blocked_reason = (
            "Cloud call blocked: private_mode is enabled. "
            "Disable private_mode or get explicit approval to use cloud models."
        )
        risk_level = "blocked"

    return SafePromptResult(
        safe_prompt=safe,
        redactions_applied=redactions,
        blocked_reason=blocked_reason,
        risk_level=risk_level,
        private_content_detected=private_detected,
        original_length=original_length,
        safe_length=len(safe),
    )


def redact_for_logging(text: str, max_length: int = 200) -> str:
    """
    Fast single-pass redaction for log lines.

    Never logs full prompts. Returns first max_length chars of redacted text.
    """
    safe = text
    for pattern, replacement in _PATTERNS:
        safe = pattern.sub(replacement, safe)
    if len(safe) > max_length:
        safe = safe[:max_length] + "…"
    return safe


def _has_private_content(text: str) -> bool:
    return any(pat.search(text) for pat in _PRIVATE_CONTENT_SIGNALS)


def _assess_risk(text: str, private_detected: bool, cloud_target: bool) -> str:
    if private_detected and cloud_target:
        return "high"
    if private_detected:
        return "medium"
    if cloud_target:
        return "medium"
    return "low"
