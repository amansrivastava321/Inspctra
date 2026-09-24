"""
result_verifier.py - Verify whether expected results actually occurred.

Core rule: "passed" only when a result is positively verified.
If action happened but result cannot be verified → INCONCLUSIVE (not passed).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from qa_ai.interactive_runtime.schemas import (
    ActionResult,
    ActionStatus,
    ScreenState,
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
)
from qa_ai.interactive_runtime.log_watcher import LogWatcher
from qa_ai.interactive_runtime.backend_state_checker import BackendStateChecker
from qa_ai.interactive_runtime.database_verifier import DatabaseVerifier

logger = logging.getLogger(__name__)


class ResultVerifier:
    """
    Verify that the expected result occurred after a UI action.

    Pass only when result is positively confirmed via:
    - UI state (text, element presence)
    - Log tags
    - API response
    - Database state
    - File/artifact existence

    If NONE of these checks are run → status = INCONCLUSIVE.
    """

    def __init__(
        self,
        log_watcher: Optional[LogWatcher] = None,
        backend_checker: Optional[BackendStateChecker] = None,
        db_verifier: Optional[DatabaseVerifier] = None,
    ):
        self._logs = log_watcher
        self._backend = backend_checker
        self._db = db_verifier

    # Public accessors for context wiring (avoids getattr on private attrs)
    @property
    def backend_checker(self) -> Optional[BackendStateChecker]:
        return self._backend

    @property
    def db_verifier(self) -> Optional[DatabaseVerifier]:
        return self._db

    def verify(
        self,
        step_id: str,
        action_result: ActionResult,
        expected_ui_text: Optional[List[str]] = None,
        expected_log_tags: Optional[List[str]] = None,
        expected_api_checks: Optional[List[Dict[str, Any]]] = None,
        expected_db_checks: Optional[List[Dict[str, Any]]] = None,
        expected_no_error: bool = True,
        runtime_context: Optional[Any] = None,
    ) -> VerificationResult:
        """
        Run all configured verification checks for a step.

        Returns VerificationResult with overall_status set conservatively:
        - At least one PASSED and zero FAILED → PASSED
        - Any FAILED → FAILED
        - All SKIPPED or no checks → INCONCLUSIVE
        - Action was BLOCKED → BLOCKED
        """
        if action_result.status == ActionStatus.BLOCKED:
            return VerificationResult(
                step_id=step_id,
                overall_status=VerificationStatus.BLOCKED,
                notes="Action was blocked — no verification performed.",
            )

        checks: List[VerificationCheck] = []

        # 1. No-crash check (always)
        checks.append(self._check_no_crash(action_result))

        # 2. No error banner (if requested)
        if expected_no_error and action_result.screen_after:
            checks.append(self._check_no_error_banner(action_result.screen_after))

        # 3. Expected UI text
        for text in (expected_ui_text or []):
            checks.append(self._check_ui_text(text, action_result.screen_after))

        # 4. Log tags
        for tag in (expected_log_tags or []):
            checks.append(self._check_log_tag(tag))

        # 5. Backend API checks
        for spec in (expected_api_checks or []):
            checks.extend(self._run_api_check(spec))

        # 6. Database checks
        for spec in (expected_db_checks or []):
            checks.extend(self._run_db_check(spec))

        overall = self._aggregate(checks)
        notes = None
        # Attach context capability note when only UI checks were run
        if runtime_context is not None:
            can_backend = getattr(runtime_context, "backend_available", False)
            can_db = getattr(runtime_context, "database_available", False)
            is_third_party = getattr(runtime_context, "is_third_party_mode", False)
            if not can_backend and not can_db:
                notes = "UI-only verification (no backend/DB available in context)."
            if is_third_party:
                notes = (notes or "") + " Third-party mode: log/API evidence not available."
        return VerificationResult(
            step_id=step_id,
            checks=checks,
            overall_status=overall,
            notes=notes or "",
        )

    # ── individual checks ─────────────────────────────────────────────────────

    def _check_no_crash(self, result: ActionResult) -> VerificationCheck:
        ok = result.status not in (ActionStatus.FAILED, ActionStatus.BLOCKED)
        return VerificationCheck(
            check_type="action_status",
            description="Action did not crash",
            expected="status != failed",
            actual=result.status.value,
            status=VerificationStatus.PASSED if ok else VerificationStatus.FAILED,
        )

    def _check_no_error_banner(self, screen: ScreenState) -> VerificationCheck:
        return VerificationCheck(
            check_type="ui_state",
            description="No error banner on screen",
            expected="has_error_banner = False",
            actual=f"has_error_banner = {screen.has_error_banner}",
            status=VerificationStatus.PASSED if not screen.has_error_banner else VerificationStatus.FAILED,
        )

    def _check_ui_text(self, expected: str, screen: Optional[ScreenState]) -> VerificationCheck:
        if screen is None:
            return VerificationCheck(
                check_type="ui_text",
                description=f"UI contains '{expected}'",
                expected=expected,
                actual="Screen state unavailable",
                status=VerificationStatus.INCONCLUSIVE,
            )
        found = any(expected.lower() in line.lower() for line in screen.visible_text)
        return VerificationCheck(
            check_type="ui_text",
            description=f"UI contains '{expected}'",
            expected=expected,
            actual="found" if found else "not found",
            status=VerificationStatus.PASSED if found else VerificationStatus.FAILED,
        )

    def _check_log_tag(self, tag: str) -> VerificationCheck:
        if self._logs is None:
            return VerificationCheck(
                check_type="log_tag",
                description=f"Log contains '{tag}'",
                expected=tag,
                actual="LogWatcher not configured",
                status=VerificationStatus.INCONCLUSIVE,
            )
        found = self._logs.tag_found(tag)
        lines = self._logs.get_matched_lines(tag)
        return VerificationCheck(
            check_type="log_tag",
            description=f"Log contains tag '{tag}'",
            expected=tag,
            actual=lines[0][:200] if lines else "not found",
            status=VerificationStatus.PASSED if found else VerificationStatus.FAILED,
        )

    def _run_api_check(self, spec: Dict[str, Any]) -> List[VerificationCheck]:
        if self._backend is None:
            return [VerificationCheck(
                check_type="api_response",
                description=str(spec),
                expected="—",
                actual="BackendStateChecker not configured",
                status=VerificationStatus.INCONCLUSIVE,
            )]
        check_type = spec.get("type", "health")
        if check_type == "health":
            return [self._backend.check_health(spec.get("path", "/health"))]
        elif check_type == "entity_exists":
            return [self._backend.check_entity_exists(
                spec["path"], spec["entity_id"], spec.get("description", "")
            )]
        elif check_type == "endpoint":
            return [self._backend.check_endpoint_response(
                spec["path"],
                spec.get("field"),
                spec.get("value"),
            )]
        return []

    def _run_db_check(self, spec: Dict[str, Any]) -> List[VerificationCheck]:
        if self._db is None:
            return [VerificationCheck(
                check_type="db_row",
                description=str(spec),
                expected="—",
                actual="DatabaseVerifier not configured",
                status=VerificationStatus.INCONCLUSIVE,
            )]
        check_type = spec.get("type", "row_exists")
        if check_type == "row_exists":
            return [self._db.check_row_exists(spec["table"], spec["where"])]
        elif check_type == "row_count":
            return [self._db.check_row_count(spec["table"], spec.get("min", 1), spec.get("where"))]
        elif check_type == "field_value":
            return [self._db.check_field_value(spec["table"], spec["field"], spec["value"], spec["where"])]
        return []

    # ── aggregation ───────────────────────────────────────────────────────────

    @staticmethod
    def _aggregate(checks: List[VerificationCheck]) -> VerificationStatus:
        real_checks = [c for c in checks if c.status != VerificationStatus.SKIPPED]
        if not real_checks:
            return VerificationStatus.INCONCLUSIVE

        if any(c.status == VerificationStatus.FAILED for c in real_checks):
            return VerificationStatus.FAILED

        if any(c.status == VerificationStatus.PASSED for c in real_checks):
            if all(c.status in (VerificationStatus.PASSED, VerificationStatus.SKIPPED)
                   for c in real_checks):
                return VerificationStatus.PASSED

        return VerificationStatus.INCONCLUSIVE
