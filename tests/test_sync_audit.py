"""
test_sync_audit.py - Tests for the sync audit agent.
Validates sync signal detection, check generation, cursor risk detection,
and artifact persistence.
"""

import pytest

from qa_ai.audit.sync_audit import SyncAuditAgent
from qa_ai.schemas.audit_result_schema import AuditCheckStatus, AuditSeverity


class TestSyncAuditAgent:
    def test_detects_sync_status_pattern(self, artifact_store):
        file_contents = {
            "models.dart": "enum SyncStatus { pending, synced, failed }",
        }
        agent = SyncAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        assert result.summary["is_sync_architecture"] is True
        assert "sync_states" in result.summary["detected_signals"]

    def test_detects_remote_id_pattern(self, artifact_store):
        file_contents = {
            "models.dart": "String? remoteId;",
        }
        agent = SyncAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        assert "remote_id" in result.summary["detected_signals"]

    def test_detects_deleted_at_pattern(self, artifact_store):
        file_contents = {
            "models.dart": "DateTime? deletedAt;",
        }
        agent = SyncAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        assert "tombstone" in result.summary["detected_signals"]

    def test_no_sync_architecture_skips(self, artifact_store):
        file_contents = {
            "main.py": "print('hello world')",
        }
        agent = SyncAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        assert result.total_checks == 1
        assert result.checks[0].status == AuditCheckStatus.SKIPPED
        assert "no sync" in result.checks[0].title.lower()

    def test_flags_global_cursor_risk(self, artifact_store):
        file_contents = {
            "sync.dart": """
enum SyncStatus { pending, synced, failed }
String? remoteId;
let cursor = '';
function pullUsers() {
  fetch('/api/users?since=' + cursor);
}
function pullOrders() {
  fetch('/api/orders?since=' + cursor);
}
""",
        }
        agent = SyncAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        cursor_checks = [c for c in result.checks if c.category == "sync_cursor"]
        assert len(cursor_checks) > 0
        assert cursor_checks[0].status == AuditCheckStatus.FAILED

    def test_flags_missing_inflight_guard(self, artifact_store):
        file_contents = {
            "sync.dart": """
enum SyncStatus { pending, synced, failed }
class SyncManager {
  SyncStatus status = SyncStatus.pending;
}
""",
        }
        agent = SyncAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        concurrency_checks = [c for c in result.checks if c.category == "concurrency"]
        assert len(concurrency_checks) > 0
        assert concurrency_checks[0].status == AuditCheckStatus.FAILED

    def test_flags_no_conflict_resolution(self, artifact_store):
        file_contents = {
            "sync.dart": """
enum SyncStatus { pending, synced, failed }
""",
        }
        agent = SyncAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        conflict_checks = [c for c in result.checks if c.category == "conflict_resolution"]
        assert len(conflict_checks) > 0
        assert conflict_checks[0].status == AuditCheckStatus.FAILED

    def test_flags_tombstone_not_propagated(self, artifact_store):
        file_contents = {
            "models.dart": """
DateTime? deletedAt;
enum SyncStatus { pending, synced, failed }
""",
        }
        agent = SyncAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        tomb_checks = [c for c in result.checks if c.category == "data_consistency"]
        assert len(tomb_checks) > 0

    def test_flags_missing_retry_logic(self, artifact_store):
        file_contents = {
            "sync.dart": """
enum SyncStatus { pending, synced, failed }
""",
        }
        agent = SyncAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        retry_checks = [c for c in result.checks if c.category == "sync_reliability"]
        assert len(retry_checks) > 0

    def test_flags_no_offline_recovery(self, artifact_store):
        file_contents = {
            "sync.dart": """
enum SyncStatus { pending, synced, failed }
void handleOffline() { /* go offline */ }
""",
        }
        agent = SyncAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        recovery_checks = [c for c in result.checks if c.category == "offline_recovery"]
        assert len(recovery_checks) > 0

    def test_artifacts_written(self, artifact_store):
        file_contents = {
            "sync.dart": "enum SyncStatus { pending, synced, failed }",
        }
        agent = SyncAuditAgent(artifact_store)
        agent.run(file_contents=file_contents)

        assert artifact_store.artifact_exists("sync_audit_results")

    def test_pass_rate_property(self, artifact_store):
        agent = SyncAuditAgent(artifact_store)
        result = agent.run(file_contents={"x.py": "print('hi')"})

        assert 0.0 <= result.pass_rate <= 1.0

    def test_full_sync_architecture_detected(self, artifact_store):
        file_contents = {
            "sync_manager.dart": """
class SyncManager {
  String? remoteId;
  String? localId;
  DateTime? deletedAt;
  
  Future<void> pull() async { /* ... */ }
  Future<void> push() async { /* ... */ }
  
  void resolveConflict() {
    // last-write-wins
  }
}
""",
        }
        agent = SyncAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        assert result.summary["is_sync_architecture"] is True
        signals = result.summary["detected_signals"]
        assert "remote_id" in signals
        assert "tombstone" in signals
        assert "sync_functions" in signals
        assert "conflict_resolution" in signals

    def test_has_high_sync_risks_property(self, artifact_store):
        file_contents = {
            "sync.dart": """
enum SyncStatus { pending, synced, failed }
""",
        }
        agent = SyncAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        assert isinstance(result.summary.get("has_high_sync_risks"), bool)

    def test_empty_file_contents(self, artifact_store):
        agent = SyncAuditAgent(artifact_store)
        result = agent.run(file_contents={})

        assert result.total_checks == 1
        assert result.checks[0].status == AuditCheckStatus.SKIPPED
