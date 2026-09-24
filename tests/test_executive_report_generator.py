"""
test_executive_report_generator.py - Tests for executive report generation.
"""

from qa_ai.reporting.executive_report_generator import ExecutiveReportGenerator


class TestExecutiveReportGenerator:
    def test_generates_executive_report_from_validated_artifacts(self, artifact_store):
        artifact_store.save_artifact(
            "software_health_score",
            {"overall_score": 82, "health_level": "good", "dimensions": {}},
            agent="test",
        )
        artifact_store.save_artifact(
            "runtime_risk_report",
            {"risk_level": "high", "findings": [{"title": "Auth risk", "severity": "high"}], "risk_distribution": {}},
            agent="test",
        )
        artifact_store.save_artifact(
            "regression_guard_report",
            {"regression_detected": True, "summary": {"worsened_findings": 1}},
            agent="test",
        )

        result = ExecutiveReportGenerator(artifact_store).run()

        assert result["summary"]["overall_health_score"] == 82
        assert artifact_store.load_report("executive_report.html") is not None

    def test_handles_malformed_inputs_safely(self, artifact_store):
        artifact_store.save_artifact("runtime_risk_report", ["bad"], agent="test")

        result = ExecutiveReportGenerator(artifact_store).run()

        assert "top_risks_count" in result["summary"]
        assert artifact_store.load_report("executive_report.html") is not None
