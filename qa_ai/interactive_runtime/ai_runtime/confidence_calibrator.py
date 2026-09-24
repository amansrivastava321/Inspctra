"""
confidence_calibrator.py - Calibrate confidence based on evidence strength.

Rules:
  UI + log + DB match  → 95+
  UI + log only        → 80-90
  UI only              → 60-75
  AI judgment only     → max 0.50 → status UNCLEAR
  Coordinate click     → reduce confidence
  Accessibility selector click → high confidence
  Destructive action skipped  → blocked
"""
from __future__ import annotations

from typing import List

from qa_ai.interactive_runtime.schemas import (
    AIVerdict,
    EvidenceSource,
    GroundedVerdict,
)


# Evidence type weight map: source_type → base score contribution
_SOURCE_WEIGHTS = {
    "ui_state": 0.30,
    "log": 0.25,
    "db": 0.25,
    "backend": 0.20,
    "screenshot": 0.15,
    "file": 0.10,
}

_AI_ONLY_MAX = 0.50


class ConfidenceCalibrator:
    """
    Compute confidence score from evidence sources and action method.

    Output is 0.0-1.0. Multiply by 100 for percentage display.
    """

    def calibrate(
        self,
        evidence_sources: List[EvidenceSource],
        used_coordinate_click: bool = False,
        used_accessibility_selector: bool = True,
        ai_judgment_only: bool = False,
        deterministic_failure: bool = False,
    ) -> float:
        """
        Compute calibrated confidence.

        Returns float 0.0-1.0.
        """
        if deterministic_failure:
            return 0.05  # near-zero: explicit failure found

        if ai_judgment_only or not evidence_sources:
            return _AI_ONLY_MAX

        score = self._compute_evidence_score(evidence_sources)

        # Coordinate click reduces confidence
        if used_coordinate_click:
            score *= 0.80

        # Accessibility selector boosts slightly
        if used_accessibility_selector:
            score = min(1.0, score * 1.05)

        # Cap based on evidence count — single source is never 100% certain
        max_cap = self._max_cap(evidence_sources)
        return min(score, max_cap)

    def _compute_evidence_score(self, sources: List[EvidenceSource]) -> float:
        strong = [s for s in sources if s.strength == "strong"]
        moderate = [s for s in sources if s.strength == "moderate"]
        weak = [s for s in sources if s.strength == "weak"]

        if strong:
            base = 0.70 + (len(strong) * 0.08)
            base += len(moderate) * 0.04
        elif moderate:
            base = 0.55 + (len(moderate) * 0.08)
            base += len(weak) * 0.02
        else:
            base = 0.35 + (len(weak) * 0.05)

        return min(1.0, base)

    def _max_cap(self, sources: List[EvidenceSource]) -> float:
        types = {s.source_type for s in sources}
        strong_count = sum(1 for s in sources if s.strength == "strong")

        if strong_count >= 3:
            return 0.98
        if strong_count >= 2:
            return 0.93
        if strong_count >= 1 and len(types) >= 2:
            return 0.88
        if strong_count >= 1:
            return 0.78
        return 0.70

    def verdict_from_confidence(
        self,
        confidence: float,
        ai_judgment_only: bool,
        deterministic_failure: bool,
        has_any_strong_evidence: bool,
    ) -> AIVerdict:
        """
        Map confidence + evidence flags to AIVerdict.

        This is advisory for EvidenceGrounder — the grounder has final say.
        """
        if deterministic_failure:
            return AIVerdict.FAIL
        if ai_judgment_only or not has_any_strong_evidence:
            return AIVerdict.UNCLEAR
        if confidence >= 0.70 and has_any_strong_evidence:
            return AIVerdict.PASS
        if confidence < 0.40:
            return AIVerdict.FAIL
        return AIVerdict.UNCLEAR
