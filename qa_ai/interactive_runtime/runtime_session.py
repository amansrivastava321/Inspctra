"""
runtime_session.py - Represent and persist a live app testing session.

RuntimeSession is the single object that tracks everything: actions taken,
logs captured, screenshots, coverage, and final verdict.
It writes structured artifacts to ArtifactStore.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from qa_ai.interactive_runtime.schemas import (
    ActionResult,
    CapabilityGap,
    FunctionCoverageItem,
    RuntimeEvidence,
    VerificationResult,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


class RuntimeSession:
    """
    Track a complete interactive runtime testing session.

    Lifecycle:
        session = RuntimeSession(...)
        session.start()
        # ... test loop ...
        session.record_action(action_result)
        session.record_verification(step_id, vr)
        session.record_evidence(evidence)
        # ...
        session.end(verdict="passed", reason="All flows verified")
        session.save(output_dir)
    """

    def __init__(
        self,
        app_name: str = "",
        app_type: str = "",
        target_path: str = "",
        launch_command: str = "",
        session_id: Optional[str] = None,
        config: Optional[Any] = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())[:12]
        self.app_name = app_name
        self.app_type = app_type
        self.target_path = target_path
        self.launch_command = launch_command

        self.started_at: Optional[str] = None
        self.ended_at: Optional[str] = None
        self.current_screen: str = ""

        self.action_results: List[ActionResult] = []
        self.verification_results: List[VerificationResult] = []
        self.evidence: List[RuntimeEvidence] = []
        self.logs_captured: List[str] = []
        self.screenshots_captured: List[str] = []
        self.backend_checks: List[Dict] = []
        self.database_checks: List[Dict] = []
        self.capability_gaps: List[CapabilityGap] = []

        self.passed_functions: List[str] = []
        self.failed_functions: List[str] = []
        self.skipped_functions: List[str] = []
        self.blocked_functions: List[str] = []
        self.inconclusive_functions: List[str] = []

        self.final_verdict: str = ""
        self.verdict_reason: str = ""

        self.automation_backend: str = "unknown"
        self.driver_capabilities: dict = {}
        self.accessibility_permission_status: bool = False
        self.platform_info: str = ""

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        self.started_at = datetime.now(timezone.utc).isoformat()
        logger.info("RuntimeSession started: %s (%s)", self.session_id, self.app_name)

    def end(self, verdict: str = "", reason: str = "") -> None:
        self.ended_at = datetime.now(timezone.utc).isoformat()
        self.final_verdict = verdict or self._compute_verdict()
        self.verdict_reason = reason
        logger.info(
            "RuntimeSession ended: %s verdict=%s duration=%.1fs",
            self.session_id, self.final_verdict, self.duration_seconds
        )

    # ── recording ─────────────────────────────────────────────────────────────

    def record_action(self, result: ActionResult) -> None:
        self.action_results.append(result)
        if result.screenshot_before:
            self.screenshots_captured.append(result.screenshot_before)
        if result.screenshot_after:
            self.screenshots_captured.append(result.screenshot_after)

    def record_verification(self, step_id: str, vr: VerificationResult) -> None:
        self.verification_results.append(vr)

    def record_evidence(self, ev: RuntimeEvidence) -> None:
        self.evidence.append(ev)

    def record_coverage(self, item: FunctionCoverageItem) -> None:
        label = item.element_label or item.item_id
        if item.status.value == "passed":
            self.passed_functions.append(label)
        elif item.status.value == "failed":
            self.failed_functions.append(label)
        elif item.status.value == "skipped":
            self.skipped_functions.append(label)
        elif item.status.value == "blocked":
            self.blocked_functions.append(label)
        elif item.status.value == "inconclusive":
            self.inconclusive_functions.append(label)

    def add_logs(self, lines: List[str]) -> None:
        self.logs_captured.extend(lines)

    def add_capability_gap(self, gap: CapabilityGap) -> None:
        self.capability_gaps.append(gap)

    def set_screen(self, screen_title: str) -> None:
        self.current_screen = screen_title

    # ── properties ────────────────────────────────────────────────────────────

    @property
    def duration_seconds(self) -> float:
        if not self.started_at:
            return 0.0
        end = self.ended_at or datetime.now(timezone.utc).isoformat()
        from datetime import datetime as _dt
        start = _dt.fromisoformat(self.started_at.replace("Z", "+00:00"))
        finish = _dt.fromisoformat(end.replace("Z", "+00:00"))
        return (finish - start).total_seconds()

    @property
    def total_actions(self) -> int:
        return len(self.action_results)

    # ── persistence ───────────────────────────────────────────────────────────

    def save(self, output_dir: str = "artifacts") -> Path:
        """Write interactive_runtime_session.json to output_dir."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "interactive_runtime_session.json"
        path.write_text(
            json.dumps(self.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("Session saved: %s", path)
        return path

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "app_name": self.app_name,
            "app_type": self.app_type,
            "target_path": self.target_path,
            "launch_command": self.launch_command,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": round(self.duration_seconds, 2),
            "current_screen": self.current_screen,
            "final_verdict": self.final_verdict,
            "verdict_reason": self.verdict_reason,
            "total_actions": self.total_actions,
            "screenshots_count": len(set(self.screenshots_captured)),
            "logs_captured_count": len(self.logs_captured),
            "passed_functions": self.passed_functions,
            "failed_functions": self.failed_functions,
            "skipped_functions": self.skipped_functions,
            "blocked_functions": self.blocked_functions,
            "inconclusive_functions": self.inconclusive_functions,
            "capability_gaps": [g.model_dump() for g in self.capability_gaps],
            "backend_checks": self.backend_checks,
            "database_checks": self.database_checks,
            "automation_backend": self.automation_backend,
            "driver_capabilities": self.driver_capabilities,
            "accessibility_permission_status": self.accessibility_permission_status,
            "platform_info": self.platform_info,
        }

    # ── verdict ───────────────────────────────────────────────────────────────

    def _compute_verdict(self) -> str:
        if self.failed_functions:
            return "failed"
        if self.blocked_functions and not self.passed_functions:
            return "blocked"
        if self.passed_functions and not self.failed_functions:
            return "passed"
        if self.inconclusive_functions:
            return "inconclusive"
        return "unknown"
