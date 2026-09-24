"""
false_positive_detector.py - Heuristic detection of likely false-positive findings.

A finding is flagged as a false-positive candidate when it matches one or more
of these heuristics:

1. HIGH/CRITICAL severity but zero evidence attached
2. No steps_to_reproduce AND no api_endpoint AND no test_case_id
3. Title matches known boilerplate patterns (e.g. "Test failed: test_xxx")
4. actual_behavior is identical to or a substring of expected_behavior
5. Finding was produced with no supporting tags (empty tag list on HIGH/CRITICAL)

Each candidate gets a `reason` list so reviewers know which rule fired.
The detector never removes findings — it only flags candidates for human review.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


_BOILERPLATE_PREFIXES = (
    "test failed:",
    "test error:",
    "assertion error",
    "generic check",
    "placeholder",
)


@dataclass
class FalsePositiveCandidate:
    finding_id: str
    title: str
    severity: str
    reasons: List[str] = field(default_factory=list)
    confidence: float = 0.0  # 0.0–1.0; higher = more likely FP

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "title": self.title,
            "severity": self.severity,
            "reasons": self.reasons,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class FalsePositiveReport:
    total_findings: int
    candidate_count: int
    candidate_rate: float
    candidates: List[FalsePositiveCandidate] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_findings": self.total_findings,
            "candidate_count": self.candidate_count,
            "candidate_rate": round(self.candidate_rate, 3),
            "candidates": [c.to_dict() for c in self.candidates],
        }


class FalsePositiveDetector:
    """Apply heuristic rules to flag likely false-positive findings."""

    # Severity levels considered "high stakes" (FP here is worse)
    _HIGH_STAKES = {"high", "critical"}

    def detect(self, findings: List[Dict[str, Any]]) -> FalsePositiveReport:
        candidates: List[FalsePositiveCandidate] = []

        for f in findings:
            reasons: List[str] = []
            severity = str(f.get("severity", "") or "").lower()
            title = str(f.get("title", "") or "").lower()
            evidence = f.get("evidence", []) or []
            steps = f.get("steps_to_reproduce", []) or []
            api_endpoint = f.get("api_endpoint") or ""
            test_case_id = f.get("test_case_id") or ""
            tags = f.get("tags", []) or []
            expected = str(f.get("expected_behavior", "") or "").strip()
            actual = str(f.get("actual_behavior", "") or "").strip()

            # Rule 1: High/critical with no evidence
            if severity in self._HIGH_STAKES and not evidence:
                reasons.append("high_severity_no_evidence")

            # Rule 2: No locating information
            if not steps and not api_endpoint and not test_case_id:
                reasons.append("no_locating_information")

            # Rule 3: Boilerplate title
            if any(title.startswith(p) for p in _BOILERPLATE_PREFIXES):
                reasons.append("boilerplate_title")

            # Rule 4: Actual == expected (test probably didn't run meaningfully)
            if actual and expected and actual == expected:
                reasons.append("actual_equals_expected")

            # Rule 5: High/critical with empty tags
            if severity in self._HIGH_STAKES and not tags:
                reasons.append("high_severity_no_tags")

            if reasons:
                # Confidence: fraction of 5 rules that fired, scaled by severity weight
                base = len(reasons) / 5.0
                weight = 1.2 if severity in self._HIGH_STAKES else 1.0
                confidence = min(base * weight, 1.0)
                candidates.append(FalsePositiveCandidate(
                    finding_id=str(f.get("id", "")),
                    title=str(f.get("title", "")),
                    severity=severity,
                    reasons=reasons,
                    confidence=confidence,
                ))

        n = len(findings)
        return FalsePositiveReport(
            total_findings=n,
            candidate_count=len(candidates),
            candidate_rate=len(candidates) / n if n else 0.0,
            candidates=candidates,
        )
