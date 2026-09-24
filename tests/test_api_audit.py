"""
test_api_audit.py - Tests for the API audit agent.
Validates audit check generation, blocked checks, unsafe endpoint detection,
and artifact persistence.
"""

import pytest

from qa_ai.audit.api_audit import APIAuditAgent
from qa_ai.schemas.audit_result_schema import AuditCheckStatus, AuditSeverity


class TestAPIAuditAgent:
    def test_generates_blocked_checks_when_base_url_missing(self, artifact_store, sample_app_map):
        agent = APIAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map, base_url=None)

        # Should have blocked checks for token validation (requires base_url)
        blocked = [c for c in result.checks if c.status == AuditCheckStatus.BLOCKED]
        assert len(blocked) > 0
        for check in blocked:
            assert check.blocked_reason is not None
            assert "base_url" in check.blocked_reason.lower() or "url" in check.blocked_reason.lower()

    def test_identifies_unauthenticated_endpoints(self, artifact_store, sample_app_map):
        agent = APIAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        # sample_app_map has GET /users with auth_required=False
        auth_checks = [c for c in result.checks if c.category == "authentication"]
        assert len(auth_checks) > 0

    def test_identifies_unsafe_methods(self, artifact_store, sample_app_map):
        agent = APIAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        # sample_app_map has POST /users
        unsafe_checks = [c for c in result.checks if c.category == "method_safety"]
        assert len(unsafe_checks) > 0
        assert any("POST" in c.target for c in unsafe_checks)

    def test_identifies_idempotency_risks(self, artifact_store, sample_app_map):
        agent = APIAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        idemp_checks = [c for c in result.checks if c.category == "idempotency"]
        assert len(idemp_checks) > 0

    def test_audit_result_counts(self, artifact_store, sample_app_map):
        agent = APIAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        assert result.total_checks == len(result.checks)
        assert result.total_checks == (
            result.passed + result.failed + result.warnings + result.blocked + result.skipped
        )

    def test_audit_result_has_metadata(self, artifact_store, sample_app_map):
        agent = APIAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        assert result.metadata.audit_type == "api_audit"
        assert result.metadata.app_name == "test-app"
        assert result.metadata.generated_by == "APIAuditAgent"
        assert result.metadata.duration_seconds >= 0

    def test_audit_result_has_summary(self, artifact_store, sample_app_map):
        agent = APIAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        assert "endpoints_audited" in result.summary
        assert result.summary["endpoints_audited"] == 2
        assert "by_category" in result.summary

    def test_artifacts_written(self, artifact_store, sample_app_map):
        agent = APIAuditAgent(artifact_store)
        agent.run(app_map=sample_app_map)

        assert artifact_store.artifact_exists("api_audit_results")
        assert artifact_store.artifact_exists("api_audit_plan")

    def test_pass_rate_property(self, artifact_store, sample_app_map):
        agent = APIAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        assert 0.0 <= result.pass_rate <= 1.0

    def test_high_risk_endpoint_gets_failed_check(self, artifact_store):
        app_map = {
            "metadata": {"app_name": "test"},
            "api_endpoints": [
                {
                    "method": "DELETE",
                    "path": "/admin/users/{id}",
                    "auth_required": False,
                    "risk": {"risk_level": "critical", "mutates_data": True, "admin_operation": True},
                },
            ],
            "security_surfaces": {"public_endpoints": []},
        }
        agent = APIAuditAgent(artifact_store)
        result = agent.run(app_map=app_map)

        failed = [c for c in result.checks if c.status == AuditCheckStatus.FAILED]
        assert len(failed) > 0
        assert any("auth" in c.category for c in failed)

    def test_empty_app_map(self, artifact_store):
        agent = APIAuditAgent(artifact_store)
        result = agent.run(app_map={})

        assert result.total_checks == 0
        assert result.metadata.audit_type == "api_audit"

    def test_critical_and_high_findings_properties(self, artifact_store):
        app_map = {
            "metadata": {"app_name": "test"},
            "api_endpoints": [
                {
                    "method": "DELETE",
                    "path": "/admin/users",
                    "auth_required": False,
                    "risk": {"risk_level": "critical", "mutates_data": True, "admin_operation": True},
                },
            ],
            "security_surfaces": {"public_endpoints": []},
        }
        agent = APIAuditAgent(artifact_store)
        result = agent.run(app_map=app_map)

        # Should have some findings
        assert isinstance(result.critical_findings, list)
        assert isinstance(result.high_findings, list)

    def test_endpoint_with_unknown_auth(self, artifact_store):
        app_map = {
            "metadata": {"app_name": "test"},
            "api_endpoints": [
                {"method": "GET", "path": "/health", "auth_required": None},
            ],
            "security_surfaces": {"public_endpoints": []},
        }
        agent = APIAuditAgent(artifact_store)
        result = agent.run(app_map=app_map)

        unknown_checks = [c for c in result.checks if "unknown" in c.check_id.lower() or "unknown" in c.title.lower()]
        assert len(unknown_checks) > 0
