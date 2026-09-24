"""
test_distributed_runtime_runner.py - Tests for end-to-end distributed runtime orchestration.
"""

from pathlib import Path

from qa_ai.distributed_runtime.distributed_runtime_runner import DistributedRuntimeRunner


class TestDistributedRuntimeRunner:
    def test_distributed_runtime_dry_run_generates_all_artifacts(self, artifact_store):
        app_path = Path("sample_apps/sync_conflict_demo").resolve()
        runner = DistributedRuntimeRunner(artifact_store)

        report = runner.run(
            app_path=str(app_path),
            actors=["cashier", "manager", "background_sync"],
            dry_run=True,
            mode="parallel",
        )

        assert report["dry_run"] is True
        assert report["summary"]["distributed_mode"] == "parallel"
        assert report["summary"]["actor_count"] == 3
        assert "phases" in report

        expected_artifacts = [
            "actor_registry",
            "multi_session_report",
            "concurrency_analysis",
            "network_condition_report",
            "offline_recovery_report",
            "sync_conflict_report",
            "chaos_execution_report",
            "execution_trace",
            "network_trace",
            "distributed_evidence_graph",
            "distributed_runtime_report",
        ]
        for artifact in expected_artifacts:
            assert artifact_store.artifact_exists(artifact), artifact
