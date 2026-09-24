"""
test_risk_visualizer.py - Tests for risk visualization metadata generation.
"""

from qa_ai.reporting.risk_visualizer import RiskVisualizer


class TestRiskVisualizer:
    def test_generates_risk_visualization_metadata(self, artifact_store):
        artifact_store.save_artifact(
            "runtime_risk_report",
            {
                "risk_distribution": {"critical": 1, "high": 2, "medium": 0, "low": 0},
                "findings": [
                    {"category": "security", "runtime_adjusted_score": 20, "file_path": "qa_ai/audit/api_audit.py"},
                    {"category": "security", "runtime_adjusted_score": 10, "file_path": "qa_ai/audit/api_audit.py"},
                ],
            },
            agent="test",
        )
        artifact_store.save_artifact(
            "quality_trend",
            {"history": [{"recorded_at": "2026-01-01T00:00:00+00:00", "overall_score": 70, "health_level": "fair"}]},
            agent="test",
        )

        result = RiskVisualizer(artifact_store).run()

        assert result["severity_distribution"]["critical"] == 1
        assert len(result["risk_heatmap"]) >= 1
        assert artifact_store.artifact_exists("risk_visualization")
