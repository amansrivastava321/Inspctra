"""
test_dependency_audit.py - Tests for the Dependency audit agent.
Validates dependency parsing, unpinned version detection,
security-sensitive package identification, and ecosystem detection.
"""

import json
import pytest

from qa_ai.audit.dependency_audit import DependencyAuditAgent
from qa_ai.schemas.audit_result_schema import AuditCheckStatus


class TestDependencyAuditAgent:
    def test_detects_unpinned_python_deps(self, artifact_store):
        dependency_files = {
            "requirements.txt": "requests\nflask\nnumpy==1.24.0",
        }
        agent = DependencyAuditAgent(artifact_store)
        result = agent.run(dependency_files=dependency_files)

        pin_checks = [c for c in result.checks if c.category == "version_pinning"]
        assert len(pin_checks) > 0
        assert "2 unpinned" in pin_checks[0].description

    def test_detects_security_sensitive_python_packages(self, artifact_store):
        dependency_files = {
            "requirements.txt": "requests==2.31.0\ncryptography==41.0.0\npyjwt==2.8.0",
        }
        agent = DependencyAuditAgent(artifact_store)
        result = agent.run(dependency_files=dependency_files)

        sec_checks = [c for c in result.checks if c.category == "security_packages"]
        assert len(sec_checks) > 0

    def test_detects_unpinned_node_deps(self, artifact_store):
        pkg = {
            "name": "test-app",
            "dependencies": {"express": "*", "lodash": "latest"},
            "devDependencies": {"jest": "^29.0.0"},
        }
        dependency_files = {
            "package.json": json.dumps(pkg),
        }
        agent = DependencyAuditAgent(artifact_store)
        result = agent.run(dependency_files=dependency_files)

        pin_checks = [c for c in result.checks if c.category == "version_pinning"]
        assert len(pin_checks) > 0

    def test_detects_security_sensitive_node_packages(self, artifact_store):
        pkg = {
            "name": "test-app",
            "dependencies": {"jsonwebtoken": "^9.0.0", "express": "^4.18.0"},
        }
        dependency_files = {
            "package.json": json.dumps(pkg),
        }
        agent = DependencyAuditAgent(artifact_store)
        result = agent.run(dependency_files=dependency_files)

        sec_checks = [c for c in result.checks if c.category == "security_packages"]
        assert len(sec_checks) > 0

    def test_detects_pubspec(self, artifact_store):
        dependency_files = {
            "pubspec.yaml": "name: my_app\ndependencies:\n  flutter:\n    sdk: flutter",
        }
        agent = DependencyAuditAgent(artifact_store)
        result = agent.run(dependency_files=dependency_files)

        eco_checks = [c for c in result.checks if c.category == "ecosystem"]
        assert len(eco_checks) > 0

    def test_detects_multiple_ecosystems(self, artifact_store):
        dependency_files = {
            "requirements.txt": "flask==2.3.0",
            "package.json": json.dumps({"name": "app", "dependencies": {"react": "^18.0.0"}}),
        }
        agent = DependencyAuditAgent(artifact_store)
        result = agent.run(dependency_files=dependency_files)

        eco_checks = [c for c in result.checks if c.category == "ecosystem"]
        assert len(eco_checks) > 0
        assert "python" in eco_checks[0].description
        assert "node" in eco_checks[0].description

    def test_handles_invalid_json(self, artifact_store):
        dependency_files = {
            "package.json": "not valid json{{{",
        }
        agent = DependencyAuditAgent(artifact_store)
        result = agent.run(dependency_files=dependency_files)

        parse_checks = [c for c in result.checks if c.category == "parse_error"]
        assert len(parse_checks) > 0

    def test_pinned_deps_pass(self, artifact_store):
        dependency_files = {
            "requirements.txt": "flask==2.3.0\nrequests==2.31.0",
        }
        agent = DependencyAuditAgent(artifact_store)
        result = agent.run(dependency_files=dependency_files)

        pin_checks = [c for c in result.checks if c.category == "version_pinning"]
        assert len(pin_checks) == 0

    def test_result_has_metadata(self, artifact_store, sample_app_map):
        agent = DependencyAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        assert result.metadata.audit_type == "dependency_audit"
        assert result.metadata.generated_by == "DependencyAuditAgent"

    def test_artifacts_written(self, artifact_store, sample_app_map):
        agent = DependencyAuditAgent(artifact_store)
        agent.run(app_map=sample_app_map)

        assert artifact_store.artifact_exists("dependency_audit_results")

    def test_pass_rate_bounds(self, artifact_store, sample_app_map):
        agent = DependencyAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        assert 0.0 <= result.pass_rate <= 1.0

    def test_empty_input(self, artifact_store):
        agent = DependencyAuditAgent(artifact_store)
        result = agent.run(dependency_files={})

        assert result.total_checks == 0

    def test_summary_has_expected_keys(self, artifact_store, sample_app_map):
        agent = DependencyAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        assert "total_checks" in result.summary
        assert "files_audited" in result.summary
        assert "by_category" in result.summary
