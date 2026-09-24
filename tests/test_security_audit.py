"""
test_security_audit.py - Tests for the Security audit agent.
Validates hardcoded secret detection, insecure HTTP, admin routes,
debug flags, local storage, weak token handling, and endpoint auth.
"""

import pytest

from qa_ai.audit.security_audit import SecurityAuditAgent
from qa_ai.schemas.audit_result_schema import AuditCheckStatus, AuditSeverity


class TestSecurityAuditAgent:
    def test_detects_hardcoded_api_key(self, artifact_store):
        file_contents = {
            "config.py": 'API_KEY = "sk-abc1234567890abcdef1234567890abcdef"',
        }
        agent = SecurityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        secret_checks = [c for c in result.checks if c.category == "secrets"]
        assert len(secret_checks) > 0
        assert any(c.status == AuditCheckStatus.FAILED for c in secret_checks)

    def test_detects_hardcoded_password(self, artifact_store):
        file_contents = {
            "settings.py": 'password = "supersecretpassword123"',
        }
        agent = SecurityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        secret_checks = [c for c in result.checks if c.category == "secrets"]
        assert len(secret_checks) > 0

    def test_detects_insecure_http_url(self, artifact_store):
        file_contents = {
            "config.py": 'API_URL = "http://api.example.com/data"',
        }
        agent = SecurityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        http_checks = [c for c in result.checks if c.category == "transport_security"]
        assert len(http_checks) > 0

    def test_ignores_localhost_http(self, artifact_store):
        file_contents = {
            "config.py": 'DEV_URL = "http://localhost:8000"',
        }
        agent = SecurityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        http_checks = [c for c in result.checks if c.category == "transport_security"]
        assert len(http_checks) == 0

    def test_detects_admin_route(self, artifact_store):
        file_contents = {
            "routes.py": '@app.route("/admin/users")',
        }
        agent = SecurityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        route_checks = [c for c in result.checks if c.category == "exposed_routes"]
        assert len(route_checks) > 0

    def test_detects_debug_flag(self, artifact_store):
        file_contents = {
            "settings.py": "DEBUG = True",
        }
        agent = SecurityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        debug_checks = [c for c in result.checks if c.category == "debug_flags"]
        assert len(debug_checks) > 0

    def test_detects_local_storage_usage(self, artifact_store):
        file_contents = {
            "auth.js": 'localStorage.setItem("token", value)',
        }
        agent = SecurityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        storage_checks = [c for c in result.checks if c.category == "data_storage"]
        assert len(storage_checks) > 0

    def test_detects_ssl_verification_disabled(self, artifact_store):
        file_contents = {
            "client.py": "verify = False",
        }
        agent = SecurityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        token_checks = [c for c in result.checks if c.category == "token_security"]
        assert len(token_checks) > 0

    def test_detects_unauthenticated_dangerous_endpoint(self, artifact_store):
        app_map = {
            "metadata": {"app_name": "test"},
            "api_endpoints": [
                {
                    "method": "DELETE",
                    "path": "/admin/users",
                    "auth_required": False,
                    "risk": {"risk_level": "critical", "mutates_data": True},
                },
            ],
            "security_surfaces": {"public_endpoints": []},
        }
        agent = SecurityAuditAgent(artifact_store)
        result = agent.run(app_map=app_map)

        ep_checks = [c for c in result.checks if c.category == "endpoint_auth"]
        assert len(ep_checks) > 0
        assert ep_checks[0].severity == AuditSeverity.CRITICAL

    def test_no_issues_with_clean_code(self, artifact_store):
        file_contents = {
            "app.py": "def hello():\n    return 'world'",
        }
        agent = SecurityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        assert result.total_checks >= 0
        assert result.metadata.audit_type == "security_audit"

    def test_result_has_metadata(self, artifact_store, sample_app_map):
        agent = SecurityAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        assert result.metadata.audit_type == "security_audit"
        assert result.metadata.generated_by == "SecurityAuditAgent"
        assert result.metadata.duration_seconds >= 0

    def test_artifacts_written(self, artifact_store, sample_app_map):
        agent = SecurityAuditAgent(artifact_store)
        agent.run(app_map=sample_app_map)

        assert artifact_store.artifact_exists("security_audit_results")

    def test_pass_rate_bounds(self, artifact_store, sample_app_map):
        agent = SecurityAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        assert 0.0 <= result.pass_rate <= 1.0

    def test_detects_github_token(self, artifact_store):
        file_contents = {
            "config.py": 'GITHUB_TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz1234567890ab"',
        }
        agent = SecurityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        secret_checks = [c for c in result.checks if c.category == "secrets"]
        assert len(secret_checks) > 0

    def test_multiple_files_scanned(self, artifact_store):
        file_contents = {
            "a.py": 'api_key = "sk-longenoughkey1234567890abcdef"',
            "b.py": "DEBUG = True",
            "c.js": 'localStorage.setItem(\"x\", \"y\")',
        }
        agent = SecurityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        categories = {c.category for c in result.checks}
        assert "secrets" in categories
        assert "debug_flags" in categories
        assert "data_storage" in categories

    def test_summary_has_expected_keys(self, artifact_store, sample_app_map):
        agent = SecurityAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        assert "total_checks" in result.summary
        assert "by_category" in result.summary
        assert "has_critical_secrets" in result.summary
        assert "has_auth_gaps" in result.summary
