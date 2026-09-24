"""
tests/test_validation_findings_quality.py - Tests for FindingsQualityAnalyzer.
"""
import pytest
from qa_ai.validation.findings_quality import FindingsQualityAnalyzer, FindingsQualityReport


def _finding(**kwargs):
    base = {
        "id": "F-0001",
        "title": "SQL injection in /api/users endpoint",
        "severity": "high",
        "category": "security",
        "evidence": [{"evidence_type": "screenshot", "filename": "shot.png"}],
        "steps_to_reproduce": ["Step 1", "Step 2"],
        "expected_behavior": "Should reject malicious input",
        "actual_behavior": "Passes input directly to query",
        "tags": ["security", "injection"],
    }
    base.update(kwargs)
    return base


class TestFindingsQualityAnalyzer:
    def setup_method(self):
        self.analyzer = FindingsQualityAnalyzer()

    def test_empty_findings_returns_zero_report(self):
        report = self.analyzer.analyze([])
        assert report.total_findings == 0
        assert report.mean_completeness_score == 0.0
        assert report.findings_with_evidence_pct == 0.0
        assert report.remediation_usefulness_score == 0.0

    def test_perfect_finding_scores_1(self):
        report = self.analyzer.analyze([_finding()])
        assert report.total_findings == 1
        assert report.per_finding[0].completeness_score == 1.0
        assert report.findings_with_evidence_pct == 1.0
        assert report.findings_with_reproduction_pct == 1.0

    def test_finding_without_evidence_lowers_score(self):
        report = self.analyzer.analyze([_finding(evidence=[])])
        score = report.per_finding[0]
        assert score.has_evidence is False
        assert score.completeness_score < 1.0

    def test_finding_without_reproduction_lowers_score(self):
        report = self.analyzer.analyze([_finding(steps_to_reproduce=[])])
        score = report.per_finding[0]
        assert score.has_reproduction is False

    def test_generic_title_flagged(self):
        report = self.analyzer.analyze([_finding(title="test failed: test_login")])
        score = report.per_finding[0]
        assert score.title_is_specific is False

    def test_specific_title_passes(self):
        report = self.analyzer.analyze([_finding(title="Missing auth on DELETE /users/:id")])
        assert report.per_finding[0].title_is_specific is True

    def test_multiple_findings_aggregate_correctly(self):
        findings = [
            _finding(id="F-0001"),
            _finding(id="F-0002", evidence=[]),
            _finding(id="F-0003", evidence=[], steps_to_reproduce=[]),
        ]
        report = self.analyzer.analyze(findings)
        assert report.total_findings == 3
        # Only 1 of 3 has evidence
        assert abs(report.findings_with_evidence_pct - 1 / 3) < 0.01
        # Only 2 of 3 have reproduction steps
        assert abs(report.findings_with_reproduction_pct - 2 / 3) < 0.01

    def test_remediation_usefulness_requires_both_evidence_and_steps(self):
        findings = [
            _finding(id="F-0001"),                          # both present
            _finding(id="F-0002", evidence=[]),             # missing evidence
            _finding(id="F-0003", steps_to_reproduce=[]),   # missing steps
        ]
        report = self.analyzer.analyze(findings)
        # Only 1 out of 3 is "actionable"
        assert abs(report.remediation_usefulness_score - 1 / 3) < 0.01
