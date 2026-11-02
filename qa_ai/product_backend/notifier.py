"""
notifier.py - tell someone when a scheduled run fails.

A pack may carry a `notify_webhook_url`. When a run the scheduler started ends failed, one JSON POST goes
to that URL (works with Slack/Discord/Teams incoming webhooks via a small relay, n8n, Zapier, ...).

Safety: http(s) only, short timeout, redirects are not followed, the body holds only the pack/run ids, names,
status and redacted failure messages (never headers, request bodies or evidence), and a failure to deliver is
logged without the URL (it can contain a token) and never affects the run.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from qa_ai.ai.prompt_safety import redact_secrets

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT_SECONDS = 5
MAX_URL_LENGTH = 500
MAX_FAILURES_REPORTED = 5
_MAX_MESSAGE_CHARS = 300
_FAILED_STATUSES = frozenset({"failed", "error"})


def is_valid_webhook_url(url: Optional[str]) -> bool:
    """True for an absolute http(s) URL with a host, of sane length."""
    if not url or len(url) > MAX_URL_LENGTH:
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def mask_webhook_url(url: Optional[str]) -> Optional[str]:
    """Show only the origin of a webhook URL: its path/query usually hold the secret token."""
    if not url:
        return None
    try:
        parts = urlsplit(url)
    except ValueError:
        return "***"
    if not parts.scheme or not parts.hostname:
        return "***"
    return f"{parts.scheme}://{parts.netloc.rsplit('@', 1)[-1]}/***"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401 - urllib hook
        return None


def build_failure_payload(pack: Dict[str, Any], run: Dict[str, Any]) -> Dict[str, Any]:
    """The JSON body sent for a failed scheduled run."""
    failures: List[Dict[str, Any]] = []
    for result in sorted(run.get("step_results") or [], key=lambda r: r.get("step") or 0):
        if result.get("status") not in _FAILED_STATUSES:
            continue
        message = result.get("error") or result.get("message") or result.get("description") or ""
        failures.append({
            "step": result.get("step"),
            "description": redact_secrets(str(result.get("description") or ""))[:_MAX_MESSAGE_CHARS],
            "message": redact_secrets(str(message))[:_MAX_MESSAGE_CHARS],
        })
        if len(failures) >= MAX_FAILURES_REPORTED:
            break
    error = run.get("error")
    return {
        "event": "scheduled_run_failed",
        "pack": {"id": pack.get("id"), "name": pack.get("name")},
        "run": {
            "id": run.get("id"),
            "status": run.get("status"),
            "error": redact_secrets(str(error))[:_MAX_MESSAGE_CHARS] if error else None,
            "completed_at": run.get("completed_at"),
        },
        "failed_steps": failures,
    }


def notify_scheduled_failure(pack: Dict[str, Any], run: Dict[str, Any]) -> bool:
    """POST the failure to the pack's webhook. Returns True when it was delivered (any 2xx)."""
    url = (pack.get("notify_webhook_url") or "").strip()
    if not url or run.get("status") not in _FAILED_STATUSES:
        return False
    if not is_valid_webhook_url(url):
        logger.warning("Notifier: pack %s has an invalid webhook URL; not sending", pack.get("id"))
        return False
    body = json.dumps(build_failure_payload(pack, run)).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "Inspectra-Notifier"},
    )
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=WEBHOOK_TIMEOUT_SECONDS) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as exc:
        logger.warning("Notifier: webhook for pack %s answered HTTP %s", pack.get("id"), exc.code)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        # Deliberately not logging the URL or the exception text: either can include the secret token.
        logger.warning("Notifier: webhook for pack %s could not be reached (%s)", pack.get("id"), type(exc).__name__)
    return False
