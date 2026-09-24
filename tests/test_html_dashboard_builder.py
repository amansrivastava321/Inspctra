"""
test_html_dashboard_builder.py - Tests for standalone dashboard generation.
"""

from qa_ai.reporting.html_dashboard_builder import HTMLDashboardBuilder


class TestHTMLDashboardBuilder:
    def test_generates_dashboard_html(self, artifact_store):
        artifact_store.save_artifact(
            "software_health_score",
            {"overall_score": 90, "health_level": "excellent", "dimensions": {}},
            agent="test",
        )
        artifact_store.save_artifact(
            "overall_risk_report",
            {"risk_level": "medium", "findings": [], "risk_distribution": {}},
            agent="test",
        )
        artifact_store.save_artifact("execution_trace", {"events": [], "summary": {}}, agent="test")
        artifact_store.save_artifact("improvement_backlog", {"items": [], "summary": {"total_items": 0}}, agent="test")
        artifact_store.save_artifact("regression_guard_report", {"regression_detected": False, "summary": {}}, agent="test")

        result = HTMLDashboardBuilder(artifact_store).run()

        assert result["dashboard_file"] == "audit_dashboard.html"
        html = artifact_store.load_report("audit_dashboard.html")
        assert html is not None
        assert "navigation sidebar" not in html.lower()  # ensure real content rather than placeholder text
