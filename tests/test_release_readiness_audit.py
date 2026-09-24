"""
test_release_readiness_audit.py - Tests for the Release Readiness audit agent.
Validates environment config, CI, signing, monitoring, backup,
and debug-in-production detection.
"""

import pytest

from qa_ai.audit.release_readiness_audit import ReleaseReadinessAuditAgent
from qa_ai.schemas.audit_result_schema import AuditCheckStatus, AuditSeverity


class TestReleaseReadinessAuditAgent:
    def test_detects_env_files(self, artifact_store):
        file_list = [".env.example", ".env.production", "src/main.py"]
        agent = ReleaseReadinessAuditAgent(artifact_store)
        result = agent.run(file_list=file_list)

        env_checks = [c for c in result.checks if c.category == "environment_config"]
        assert len(env_checks) > 0
        assert any(c.status == AuditCheckStatus.PASSED for c in env_checks)

    def test_warns_missing_env_files(self, artifact_store):
        file_list = ["src/main.py", "README.md"]
        agent = ReleaseReadinessAuditAgent(artifact_store)
        result = agent.run(file_list=file_list)

        env_checks = [c for c in result.checks if c.category == "environment_config"]
        assert len(env_checks) > 0
        assert env_checks[0].status == AuditCheckStatus.WARNING

    def test_detects_ci_config(self, artifact_store):
        file_list = [".github/workflows/deploy.yml", "src/app.py"]
        agent = ReleaseReadinessAuditAgent(artifact_store)
        result = agent.run(file_list=file_list)

        ci_checks = [c for c in result.checks if c.category == "ci_cd"]
        assert len(ci_checks) > 0
        assert ci_checks[0].status == AuditCheckStatus.PASSED

    def test_warns_missing_ci_config(self, artifact_store):
        file_list = ["src/app.py", "README.md"]
        agent = ReleaseReadinessAuditAgent(artifact_store)
        result = agent.run(file_list=file_list)

        ci_checks = [c for c in result.checks if c.category == "ci_cd"]
        assert len(ci_checks) > 0
        assert ci_checks[0].status == AuditCheckStatus.WARNING

    def test_detects_signing_config(self, artifact_store):
        file_list = ["keystore.jks", "build.gradle"]
        agent = ReleaseReadinessAuditAgent(artifact_store)
        result = agent.run(file_list=file_list)

        sign_checks = [c for c in result.checks if c.category == "signing"]
        assert len(sign_checks) > 0
        assert sign_checks[0].status == AuditCheckStatus.PASSED

    def test_detects_monitoring(self, artifact_store):
        file_contents = {
            "app.py": "import sentry_sdk\nsentry_sdk.init(dsn='https://...')",
        }
        file_list = ["app.py"]
        agent = ReleaseReadinessAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents, file_list=file_list)

        mon_checks = [c for c in result.checks if c.category == "monitoring"]
        assert len(mon_checks) > 0
        assert mon_checks[0].status == AuditCheckStatus.PASSED

    def test_warns_missing_monitoring(self, artifact_store):
        file_contents = {"app.py": "print('hello')"}
        file_list = ["app.py"]
        agent = ReleaseReadinessAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents, file_list=file_list)

        mon_checks = [c for c in result.checks if c.category == "monitoring"]
        assert len(mon_checks) > 0
        assert mon_checks[0].status == AuditCheckStatus.WARNING

    def test_detects_backup_recovery(self, artifact_store):
        file_contents = {
            "db.py": "def backup_database():\n    pass",
        }
        agent = ReleaseReadinessAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        bak_checks = [c for c in result.checks if c.category == "backup_recovery"]
        assert len(bak_checks) > 0
        assert bak_checks[0].status == AuditCheckStatus.PASSED

    def test_warns_missing_backup(self, artifact_store):
        file_contents = {"app.py": "print('hello')"}
        agent = ReleaseReadinessAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        bak_checks = [c for c in result.checks if c.category == "backup_recovery"]
        assert len(bak_checks) > 0
        assert bak_checks[0].status == AuditCheckStatus.WARNING

    def test_detects_debug_in_production_config(self, artifact_store):
        file_contents = {
            "settings.production.py": "DEBUG = True",
        }
        agent = ReleaseReadinessAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        debug_checks = [c for c in result.checks if c.category == "debug_config"]
        assert len(debug_checks) > 0
        assert debug_checks[0].severity == AuditSeverity.CRITICAL

    def test_no_env_example_warns(self, artifact_store):
        file_list = [".env.local", "src/app.py"]
        agent = ReleaseReadinessAuditAgent(artifact_store)
        result = agent.run(file_list=file_list)

        env_checks = [c for c in result.checks if c.category == "environment_config"]
        assert any("no .env.example" in c.title.lower() for c in env_checks)

    def test_result_has_metadata(self, artifact_store, sample_app_map):
        agent = ReleaseReadinessAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        assert result.metadata.audit_type == "release_readiness_audit"
        assert result.metadata.generated_by == "ReleaseReadinessAuditAgent"

    def test_artifacts_written(self, artifact_store, sample_app_map):
        agent = ReleaseReadinessAuditAgent(artifact_store)
        agent.run(app_map=sample_app_map)

        assert artifact_store.artifact_exists("release_readiness_results")

    def test_pass_rate_bounds(self, artifact_store, sample_app_map):
        agent = ReleaseReadinessAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        assert 0.0 <= result.pass_rate <= 1.0

    def test_summary_ready_for_release(self, artifact_store):
        file_contents = {
            "app.py": "import sentry_sdk",
            "db.py": "def backup(): pass",
        }
        file_list = [".env.example", ".github/workflows/ci.yml", "keystore.jks"]
        agent = ReleaseReadinessAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents, file_list=file_list)

        assert "ready_for_release" in result.summary
