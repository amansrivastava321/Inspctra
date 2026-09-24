"""
test_adaptive_audit_planner.py - Tests for adaptive planning from low coverage/evidence gaps.
"""

from qa_ai.ai_reasoning.adaptive_audit_planner import AdaptiveAuditPlanner


class TestAdaptiveAuditPlanner:
    def test_generates_actions_from_coverage_and_evidence_gaps(self, artifact_store):
        artifact_store.save_artifact(
            "benchmark_metrics",
            {
                "metrics": {
                    "issue_coverage": 0.4,
                    "runtime_verification_rate": 0.5,
                    "evidence_completeness": 0.3,
                }
            },
            agent="test",
        )
        artifact_store.save_artifact("runtime_risk_report", {"risk_level": "high"}, agent="test")
        result = AdaptiveAuditPlanner(artifact_store).run()
        assert result["summary"]["action_count"] >= 3
        assert all("confidence" in item for item in result["actions"])
        assert artifact_store.artifact_exists("adaptive_audit_plan")
