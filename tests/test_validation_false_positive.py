"""
tests/test_validation_false_positive.py - Tests for FalsePositiveDetector.
"""
import pytest
from qa_ai.validation.false_positive_detector import FalsePositiveDetector, FalsePositiveReport


def _finding(**kwargs):
    base = {
        "id": "F-0001",
        "title": "SQL injection vulnerability in login endpoint",
        "severity": "high",
        "evidence": [{"type": "request"}],
        "steps_to_reproduce": ["POST /login with payload"],
        "api_endpoint": "/api/login",
        "test_case_id": "TC-001",
        "tags": ["security"],
        "expected_behavior": "Reject malformed input",
        "actual_behavior": "Input passed to query unescaped",
    }
    base.update(kwargs)
    return base


class TestFalsePositiveDetector:
    def setup_method(self):
        self.detector = FalsePositiveDetector()

    def test_empty_list_returns_empty_report(self):
        report = self.detector.detect([])
        assert report.total_findings == 0
        assert report.candidate_count == 0
        assert report.candidate_rate == 0.0

    def test_clean_finding_not_flagged(self):
        report = self.detector.detect([_finding()])
        assert report.candidate_count == 0

    def test_high_severity_without_evidence_flagged(self):
        f = _finding(severity="high", evidence=[])
        report = self.detector.detect([f])
        assert report.candidate_count == 1
        candidate = report.candidates[0]
        assert "high_severity_no_evidence" in candidate.reasons

    def test_critical_without_evidence_flagged(self):
        report = self.detector.detect([_finding(severity="critical", evidence=[])])
        assert report.candidate_count == 1

    def test_low_severity_without_evidence_not_flagged_for_rule1(self):
        # Low severity without evidence should not trigger rule 1
        f = _finding(severity="low", evidence=[],
                     steps_to_reproduce=["step"], api_endpoint="/x",
                     test_case_id="tc1", tags=["t"])
        report = self.detector.detect([f])
        if report.candidate_count > 0:
            reasons = report.candidates[0].reasons
            assert "high_severity_no_evidence" not in reasons

    def test_no_locating_info_flagged(self):
        f = _finding(steps_to_reproduce=[], api_endpoint="", test_case_id="")
        report = self.detector.detect([f])
        assert report.candidate_count == 1
        assert "no_locating_information" in report.candidates[0].reasons

    def test_boilerplate_title_flagged(self):
        f = _finding(title="test failed: test_login_invalid_password")
        report = self.detector.detect([f])
        assert report.candidate_count >= 1
        assert "boilerplate_title" in report.candidates[0].reasons

    def test_actual_equals_expected_flagged(self):
        same = "Returns 200 OK"
        f = _finding(actual_behavior=same, expected_behavior=same)
        report = self.detector.detect([f])
        assert report.candidate_count == 1
        assert "actual_equals_expected" in report.candidates[0].reasons

    def test_candidate_rate_correct(self):
        findings = [
            _finding(id="F-0001"),                          # clean
            _finding(id="F-0002", evidence=[]),             # flagged
            _finding(id="F-0003", evidence=[]),             # flagged
        ]
        report = self.detector.detect(findings)
        assert report.total_findings == 3
        assert report.candidate_count == 2
        assert abs(report.candidate_rate - 2 / 3) < 0.01

    def test_confidence_increases_with_more_rules(self):
        # Multiple rules firing → higher confidence
        f_one_rule = _finding(evidence=[])          # 1 rule (no evidence, high sev)
        f_two_rules = _finding(                     # 2+ rules
            evidence=[],
            steps_to_reproduce=[], api_endpoint="", test_case_id="",
        )
        r1 = self.detector.detect([f_one_rule])
        r2 = self.detector.detect([f_two_rules])
        assert r2.candidates[0].confidence >= r1.candidates[0].confidence
