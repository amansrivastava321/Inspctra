"""
test_fix_reasoner.py - Tests for advisory-only fix reasoning.
"""

from qa_ai.ai_reasoning.fix_reasoner import FixReasoner


class TestFixReasoner:
    def test_fix_reasoning_is_advisory_only(self, artifact_store):
        artifact_store.save_artifact(
            "fix_plan",
            {"fixes": [{"fix_id": "FX1", "risk_level": "high", "recommended_tests": ["TEST-SEC"]}]},
            agent="test",
        )
        artifact_store.save_artifact(
            "change_impact_analysis",
            {"affected_tests": ["TEST-SEC", "TEST-SMOKE"]},
            agent="test",
        )
        result = FixReasoner(artifact_store).run()
        assert result["advisory_only"] is True
        assert result["strategies"]
        assert all(item.get("advisory_only") is True for item in result["strategies"])
        assert artifact_store.artifact_exists("ai_fix_reasoning")
