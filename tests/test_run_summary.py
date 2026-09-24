"""
test_run_summary.py - Tests for CLI run summary artifact generation.
"""

from qa_ai.cli.run_summary import RunSummary


class TestRunSummary:
    def test_build_contains_expected_fields(self, artifact_store):
        artifact_store.save_artifact("software_health_score", {"overall_score": 80}, agent="test")
        artifact_store.save_report("executive_report.html", "<html></html>")

        builder = RunSummary(artifact_store)
        summary = builder.build(
            run_id="run_abc123",
            target_path="/tmp/app",
            profile="web",
            phases_executed=["discovery", "reporting"],
            status="completed",
            warnings=["warn"],
            errors=[],
            dry_run=False,
        )

        assert summary["run_id"] == "run_abc123"
        assert summary["profile"] == "web"
        assert summary["status"] == "completed"
        assert "software_health_score.json" in summary["artifacts_generated"]
        assert "executive_report.html" in summary["report_paths"]
        assert "generated_at" in summary

    def test_save_persists_run_summary_artifact(self, artifact_store):
        builder = RunSummary(artifact_store)
        summary = builder.build(
            run_id="run_xyz789",
            target_path="/tmp/app",
            profile="api",
            phases_executed=[],
            status="dry_run",
            dry_run=True,
        )
        builder.save(summary)

        stored = artifact_store.load_artifact("run_summary")
        assert stored is not None
        assert stored["run_id"] == "run_xyz789"
        assert stored["status"] == "dry_run"
