"""
context_evidence_collector.py - Collect evidence from all runtime sources.

Aggregates evidence from backend, DB, logs, screenshots per step.
All collections are read-only and non-blocking — errors are logged, not raised.

Security:
- Never logs secret values.
- DB collection: SELECT-only via DatabaseVerifier.
- Backend collection: GET-only via BackendStateChecker.
- Process PIDs only — no kill/signal/process memory reads.
- Log lines: redacted before storage (caller responsibility; we don't re-redact).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from qa_ai.interactive_runtime.runtime_context.context_models import (
    ContextEvidenceBundle,
    RuntimeTestContext,
)

logger = logging.getLogger(__name__)


class ContextEvidenceCollector:
    """
    Collect evidence from all available runtime sources for one step.

    Injected with optional BackendStateChecker, DatabaseVerifier, LogWatcher.
    Falls back gracefully if any are not configured.
    """

    def __init__(
        self,
        ctx: Optional[RuntimeTestContext],
        backend_checker: Optional[Any] = None,   # BackendStateChecker | None
        db_verifier: Optional[Any] = None,        # DatabaseVerifier | None
        log_watcher: Optional[Any] = None,        # LogWatcher | None
    ):
        self._ctx = ctx

        # Validate injected objects via duck-typing (defense in depth against
        # unexpected objects being injected via Optional[Any] params)
        if backend_checker is not None and not callable(getattr(backend_checker, "check_health", None)):
            logger.warning(
                "ContextEvidenceCollector: backend_checker has no check_health() — ignored"
            )
            backend_checker = None
        if db_verifier is not None and not callable(getattr(db_verifier, "check_row_exists", None)):
            logger.warning(
                "ContextEvidenceCollector: db_verifier has no check_row_exists() — ignored"
            )
            db_verifier = None
        if log_watcher is not None and not callable(getattr(log_watcher, "all_lines", None)):
            logger.warning(
                "ContextEvidenceCollector: log_watcher has no all_lines() — ignored"
            )
            log_watcher = None

        self._backend = backend_checker
        self._db = db_verifier
        self._logs = log_watcher

    def collect(
        self,
        step_id: str,
        screenshots: Optional[List[str]] = None,
    ) -> ContextEvidenceBundle:
        """
        Collect all available evidence for a step.
        Non-blocking — errors recorded in bundle.errors.
        """
        bundle = ContextEvidenceBundle(
            step_id=step_id,
            collected_at=datetime.now(timezone.utc).isoformat(),
        )

        if not self._ctx:
            return bundle

        # ── Backend health ──────────────────────────────────────────────────────
        if self._ctx.backend_available and self._backend:
            try:
                check = self._backend.check_health("/health")
                bundle.backend_health = {
                    "status": check.status.value,
                    "description": check.description,
                    "actual": check.actual,
                }
            except Exception as exc:
                bundle.errors.append(f"Backend health collection failed: {exc}")
                logger.debug("Backend health collection error: %s", exc)

        # ── Log lines (not available in third-party mode) ────────────────────────
        if not self._ctx.is_third_party_mode and self._logs:
            try:
                bundle.log_lines = self._logs.all_lines()[-30:]
            except Exception as exc:
                bundle.errors.append(f"Log collection failed: {exc}")
                logger.debug("Log collection error: %s", exc)

        # ── Screenshots ─────────────────────────────────────────────────────────
        if screenshots:
            bundle.screenshots = [s for s in screenshots if s]

        return bundle
