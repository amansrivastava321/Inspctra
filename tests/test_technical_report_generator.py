"""
test_technical_report_generator.py - Tests for technical report generation.
"""

from qa_ai.reporting.technical_report_generator import TechnicalReportGenerator


class TestTechnicalReportGenerator:
    def test_generates_technical_report(self, artifact_store):
        artifact_store.save_artifact(
            "correlated_findings",
            {"findings": [{"id": "F1", "title": "Missing auth", "severity": "high", "file_path": "app.py"}]},
            agent="test",
        )
        artifact_store.save_artifact("root_cause_analysis", {"root_causes": [{"cause_id": "RC1"}]}, agent="test")
        artifact_store.save_artifact("evidence_graph", {"graph": {"nodes": [], "edges": []}, "summary": {}}, agent="test")
        artifact_store.save_artifact("replay_analysis", {"comparison": {}, "regression_detected": False}, agent="test")
        artifact_store.save_artifact("regression_guard_report", {"regression_detected": False, "summary": {}}, agent="test")
        artifact_store.save_artifact(
            "change_impact_analysis",
            {"affected_files": ["app.py"], "affected_workflows": ["auth"], "risk_summary": {}},
            agent="test",
        )

        result = TechnicalReportGenerator(artifact_store).run()

        assert result["summary"]["findings_count"] == 1
        assert artifact_store.load_report("technical_report.html") is not None

    def test_malformed_artifacts_do_not_crash_report(self, artifact_store):
        artifact_store.save_artifact("correlated_findings", {"findings": "bad"}, agent="test")
        result = TechnicalReportGenerator(artifact_store).run()
        assert "html_report" in result
