"""
test_report_exporter.py - Tests for report export formats.
"""

from qa_ai.reporting.report_exporter import ReportExporter


class TestReportExporter:
    def test_exports_html_markdown_and_json_bundle(self, artifact_store):
        artifact_store.save_artifact(
            "software_health_score",
            {"overall_score": 80, "health_level": "good", "dimensions": {}},
            agent="test",
        )
        artifact_store.save_artifact(
            "overall_risk_report",
            {"risk_level": "medium", "findings": [], "risk_distribution": {}},
            agent="test",
        )

        result = ReportExporter(artifact_store).run()

        assert result["html"] == "audit_summary.html"
        assert result["markdown"] == "audit_summary.md"
        assert result["json"] == "audit_summary.json"
        assert artifact_store.load_report("audit_summary.html") is not None
        assert artifact_store.load_report("audit_summary.md") is not None
        assert artifact_store.artifact_exists("audit_summary")
