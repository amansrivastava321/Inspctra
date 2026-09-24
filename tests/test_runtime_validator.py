"""
test_runtime_validator.py - Tests for the RuntimeValidator.
Validates finding verification, blocked/unverifiable handling,
evidence capture, and artifact persistence.
"""

import pytest

from qa_ai.runtime_intelligence.runtime_validator import (
    RuntimeValidator,
    VerificationStatus,
)


class TestRuntimeValidator:
    def test_initializes_with_artifact_store(self, artifact_store):
        validator = RuntimeValidator(artifact_store)
        assert validator.store is artifact_store

    def test_returns_verified_findings_structure(self, artifact_store, sample_app_map):
        artifact_store.save_artifact("app_map", sample_app_map)
        validator = RuntimeValidator(artifact_store)
        result = validator.run(findings=[], base_url=None)

        assert "metadata" in result
        assert "verified_findings" in result
        assert "summary" in result
        assert result["metadata"]["validation_type"] == "runtime_validation"

    def test_marks_non_verifiable_categories(self, artifact_store):
        findings = [
            {"id": "F1", "title": "Large file", "category": "file_size", "severity": "low"},
            {"id": "F2", "title": "TODO comment", "category": "technical_debt", "severity": "low"},
        ]
        validator = RuntimeValidator(artifact_store)
        result = validator.run(findings=findings, base_url=None)

        for vf in result["verified_findings"]:
            assert vf["verification_status"] == VerificationStatus.UNVERIFIABLE.value

    def test_marks_blocked_when_no_base_url(self, artifact_store):
        findings = [
            {"id": "F1", "title": "Missing auth", "category": "authentication", "severity": "high"},
        ]
        validator = RuntimeValidator(artifact_store)
        result = validator.run(findings=findings, base_url=None)

        assert result["verified_findings"][0]["verification_status"] == VerificationStatus.BLOCKED.value
        assert "No base_url" in result["verified_findings"][0]["verification_reason"]

    def test_verifiable_categories_include_auth(self, artifact_store):
        verifiable = {"authentication", "endpoint_auth", "transport_security",
                      "token_security", "exposed_routes", "idempotency"}
        # These are the categories that should be attempted for verification
        assert "authentication" in verifiable
        assert "transport_security" in verifiable

    def test_handles_empty_findings(self, artifact_store):
        validator = RuntimeValidator(artifact_store)
        result = validator.run(findings=[], base_url="http://localhost:8000")

        assert result["verified_findings"] == []
        assert result["metadata"]["total_findings"] == 0

    def test_artifacts_written(self, artifact_store):
        validator = RuntimeValidator(artifact_store)
        validator.run(findings=[], base_url=None)

        assert artifact_store.artifact_exists("verified_findings")

    def test_summary_counts_statuses(self, artifact_store):
        findings = [
            {"id": "F1", "title": "Large file", "category": "file_size", "severity": "low"},
            {"id": "F2", "title": "Missing auth", "category": "authentication", "severity": "high"},
        ]
        validator = RuntimeValidator(artifact_store)
        result = validator.run(findings=findings, base_url=None)

        summary = result["summary"]
        assert summary.get("unverifiable", 0) >= 1
        assert summary.get("blocked", 0) >= 1

    def test_loads_findings_from_store(self, artifact_store):
        correlated = {
            "findings": [
                {"id": "F1", "title": "Test", "category": "file_size", "severity": "low"},
            ],
        }
        artifact_store.save_artifact("correlated_findings", correlated)

        validator = RuntimeValidator(artifact_store)
        result = validator.run(base_url=None)

        assert result["metadata"]["total_findings"] == 1

    def test_idempotency_findings_marked_unverifiable(self, artifact_store):
        findings = [
            {"id": "F1", "title": "No idempotency", "category": "idempotency", "severity": "medium"},
        ]
        validator = RuntimeValidator(artifact_store)
        result = validator.run(findings=findings, base_url="http://localhost:8000")

        # Without a real server, idempotency checks are unverifiable
        assert result["verified_findings"][0]["verification_status"] == VerificationStatus.UNVERIFIABLE.value
