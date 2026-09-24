"""
findings_quality.py - Scores the quality of findings produced by a validation run.

Metrics per finding:
- has_evidence         : at least one evidence reference attached
- has_reproduction     : steps_to_reproduce is non-empty
- has_expected_behavior: expected_behavior is non-empty
- has_actual_behavior  : actual_behavior is non-empty
- has_category         : category is set (not None/empty)
- has_severity         : severity is set
- title_is_specific    : title is not a generic template string
- completeness_score   : 0.0–1.0 average of the above booleans

Aggregate metrics:
- total_findings
- findings_with_evidence_pct
- findings_with_reproduction_pct
- findings_with_full_detail_pct   (all 4 behavior fields populated)
- mean_completeness_score
- remediation_usefulness_score    : pct of findings actionable (has evidence + reproduction)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


_GENERIC_TITLE_FRAGMENTS = frozenset({
    "test failed",
    "finding",
    "issue found",
    "error detected",
    "problem",
    "failure",
})


@dataclass
class FindingQualityScore:
    finding_id: str
    title: str
    severity: str
    category: str
    has_evidence: bool
    has_reproduction: bool
    has_expected_behavior: bool
    has_actual_behavior: bool
    has_category: bool
    has_severity: bool
    title_is_specific: bool
    completeness_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "title": self.title,
            "severity": self.severity,
            "category": self.category,
            "has_evidence": self.has_evidence,
            "has_reproduction": self.has_reproduction,
            "has_expected_behavior": self.has_expected_behavior,
            "has_actual_behavior": self.has_actual_behavior,
            "has_category": self.has_category,
            "has_severity": self.has_severity,
            "title_is_specific": self.title_is_specific,
            "completeness_score": round(self.completeness_score, 3),
        }


@dataclass
class FindingsQualityReport:
    total_findings: int
    findings_with_evidence_pct: float
    findings_with_reproduction_pct: float
    findings_with_full_detail_pct: float
    mean_completeness_score: float
    remediation_usefulness_score: float
    per_finding: List[FindingQualityScore] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_findings": self.total_findings,
            "findings_with_evidence_pct": round(self.findings_with_evidence_pct, 3),
            "findings_with_reproduction_pct": round(self.findings_with_reproduction_pct, 3),
            "findings_with_full_detail_pct": round(self.findings_with_full_detail_pct, 3),
            "mean_completeness_score": round(self.mean_completeness_score, 3),
            "remediation_usefulness_score": round(self.remediation_usefulness_score, 3),
            "per_finding": [s.to_dict() for s in self.per_finding],
        }


class FindingsQualityAnalyzer:
    """Score the quality of a list of raw finding dicts."""

    def analyze(self, findings: List[Dict[str, Any]]) -> FindingsQualityReport:
        if not findings:
            return FindingsQualityReport(
                total_findings=0,
                findings_with_evidence_pct=0.0,
                findings_with_reproduction_pct=0.0,
                findings_with_full_detail_pct=0.0,
                mean_completeness_score=0.0,
                remediation_usefulness_score=0.0,
            )

        scores: List[FindingQualityScore] = [self._score(f) for f in findings]
        n = len(scores)

        evidence_pct = sum(1 for s in scores if s.has_evidence) / n
        repro_pct = sum(1 for s in scores if s.has_reproduction) / n
        full_detail_pct = sum(
            1 for s in scores
            if s.has_evidence and s.has_reproduction
            and s.has_expected_behavior and s.has_actual_behavior
        ) / n
        mean_score = sum(s.completeness_score for s in scores) / n
        remediation_pct = sum(
            1 for s in scores if s.has_evidence and s.has_reproduction
        ) / n

        return FindingsQualityReport(
            total_findings=n,
            findings_with_evidence_pct=evidence_pct,
            findings_with_reproduction_pct=repro_pct,
            findings_with_full_detail_pct=full_detail_pct,
            mean_completeness_score=mean_score,
            remediation_usefulness_score=remediation_pct,
            per_finding=scores,
        )

    def _score(self, f: Dict[str, Any]) -> FindingQualityScore:
        title = str(f.get("title", ""))
        severity = str(f.get("severity", "") or "")
        category = str(f.get("category", "") or "")
        evidence = f.get("evidence", []) or []
        steps = f.get("steps_to_reproduce", []) or []
        expected = str(f.get("expected_behavior", "") or "").strip()
        actual = str(f.get("actual_behavior", "") or "").strip()

        has_evidence = bool(evidence)
        has_reproduction = bool(steps)
        has_expected = bool(expected)
        has_actual = bool(actual)
        has_category = bool(category)
        has_severity = bool(severity)
        title_specific = self._title_is_specific(title)

        flags = [
            has_evidence, has_reproduction, has_expected, has_actual,
            has_category, has_severity, title_specific,
        ]
        score = sum(flags) / len(flags)

        return FindingQualityScore(
            finding_id=str(f.get("id", "")),
            title=title,
            severity=severity,
            category=category,
            has_evidence=has_evidence,
            has_reproduction=has_reproduction,
            has_expected_behavior=has_expected,
            has_actual_behavior=has_actual,
            has_category=has_category,
            has_severity=has_severity,
            title_is_specific=title_specific,
            completeness_score=score,
        )

    @staticmethod
    def _title_is_specific(title: str) -> bool:
        lower = title.lower().strip()
        if not lower or len(lower) < 10:
            return False
        return not any(frag == lower or lower.startswith(frag + ":") for frag in _GENERIC_TITLE_FRAGMENTS)
