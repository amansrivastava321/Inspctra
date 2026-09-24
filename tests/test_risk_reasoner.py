"""
test_risk_reasoner.py - Tests for semantic risk explanations and risk chain generation.
"""

from qa_ai.ai_reasoning.risk_reasoner import RiskReasoner


class TestRiskReasoner:
    def test_risk_chain_generation_from_deterministic_artifacts(self, artifact_store):
        artifact_store.save_artifact(
            "runtime_risk_report",
            {
                "risk_level": "high",
                "overall_adjusted_risk_score": 62.0,
                "findings": [
                    {"id": "R1", "title": "Auth gap on sync endpoint", "severity": "high", "category": "security", "target": "/sync"},
                    {"id": "R2", "title": "Sync conflict corruption", "severity": "high", "category": "sync", "target": "/sync"},
                ],
            },
            agent="test",
        )
        artifact_store.save_artifact(
            "semantic_root_cause_analysis",
            {"hypotheses": [{"hypothesis": "auth and sync failures co-occur"}]},
            agent="test",
        )

        report = RiskReasoner(artifact_store).run()
        assert report["risk_level"] == "high"
        assert report["risk_chains"]
        assert "confidence" in report["risk_chains"][0]
        assert artifact_store.artifact_exists("semantic_risk_report")
