"""
runtime_evidence_builder.py - Build structured evidence for each test step.

Reuses EvidenceCollector for storage. Produces RuntimeEvidence objects
that are linked to FunctionCoverageItems and the final report.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from qa_ai.evidence.evidence_collector import EvidenceCollector
from qa_ai.interactive_runtime.schemas import (
    ActionResult,
    RuntimeEvidence,
    VerificationResult,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


class RuntimeEvidenceBuilder:
    """
    Build a RuntimeEvidence record for each action+verification step.

    Stores raw evidence via EvidenceCollector and returns structured
    RuntimeEvidence objects for the final report.
    """

    def __init__(self, evidence_collector: Optional[EvidenceCollector] = None):
        self._collector = evidence_collector
        self._evidence: List[RuntimeEvidence] = []

    def build(
        self,
        step_id: str,
        action_description: str,
        action_result: ActionResult,
        verification_result: VerificationResult,
        expected_result: str = "",
        log_excerpts: Optional[List[str]] = None,
        backend_evidence: Optional[Dict[str, Any]] = None,
        database_evidence: Optional[Dict[str, Any]] = None,
        reproduction_steps: Optional[List[str]] = None,
    ) -> RuntimeEvidence:
        """Build and store evidence for one step."""
        actual_result = self._summarise_verification(verification_result)
        status = verification_result.overall_status
        severity = self._severity_for(status)

        evidence = RuntimeEvidence(
            step_id=step_id,
            action_description=action_description,
            screen_before=action_result.screenshot_before,
            screen_after=action_result.screenshot_after,
            expected_result=expected_result,
            actual_result=actual_result,
            verification_method=self._verification_methods(verification_result),
            screenshots=[p for p in [
                action_result.screenshot_before,
                action_result.screenshot_after,
            ] if p],
            log_excerpts=log_excerpts or [],
            backend_evidence=backend_evidence,
            database_evidence=database_evidence,
            status=status,
            severity=severity,
            reproduction_steps=reproduction_steps or [],
        )
        self._evidence.append(evidence)

        # Also persist via EvidenceCollector if available
        if self._collector:
            self._persist(evidence)

        return evidence

    def all_evidence(self) -> List[RuntimeEvidence]:
        return list(self._evidence)

    def failed_evidence(self) -> List[RuntimeEvidence]:
        return [e for e in self._evidence if e.status == VerificationStatus.FAILED]

    def as_dicts(self) -> List[Dict[str, Any]]:
        return [e.model_dump() for e in self._evidence]

    # ── helpers ───────────────────────────────────────────────────────────────

    def _persist(self, evidence: RuntimeEvidence) -> None:
        try:
            self._collector.capture_api_response(
                test_id=evidence.step_id,
                test_title=evidence.action_description,
                method="INTERACTIVE",
                url=evidence.step_id,
                response_status=200 if evidence.status == VerificationStatus.PASSED else 0,
                response_body=evidence.model_dump(),
                error=evidence.actual_result if evidence.status == VerificationStatus.FAILED else None,
            )
        except Exception as exc:
            logger.debug("Evidence persistence error: %s", exc)

    @staticmethod
    def _summarise_verification(vr: VerificationResult) -> str:
        if not vr.checks:
            return "No verification performed"
        passed = vr.passed_count
        failed = vr.failed_count
        total = len(vr.checks)
        return f"{passed}/{total} checks passed" + (
            f" — {failed} failed" if failed else ""
        )

    @staticmethod
    def _verification_methods(vr: VerificationResult) -> str:
        types = list({c.check_type for c in vr.checks})
        return ", ".join(types) if types else "none"

    @staticmethod
    def _severity_for(status: VerificationStatus) -> str:
        return {
            VerificationStatus.PASSED: "info",
            VerificationStatus.FAILED: "high",
            VerificationStatus.INCONCLUSIVE: "medium",
            VerificationStatus.BLOCKED: "low",
            VerificationStatus.SKIPPED: "info",
        }.get(status, "info")
