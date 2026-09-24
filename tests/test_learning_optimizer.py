"""
test_learning_optimizer.py - Tests for benchmark-driven learning optimization.
"""

from qa_ai.ai_reasoning.learning_optimizer import LearningOptimizer


class TestLearningOptimizer:
    def test_learning_optimization_recommendations(self, artifact_store):
        artifact_store.save_artifact(
            "benchmark_metrics",
            {
                "metrics": {
                    "false_positive_rate": 0.4,
                    "duplicate_finding_rate": 0.3,
                    "issue_coverage": 0.4,
                    "runtime_verification_rate": 0.5,
                    "evidence_completeness": 0.4,
                }
            },
            agent="test",
        )
        artifact_store.save_artifact("learning_registry", {"recurring_root_causes": [{"cause": "auth"}]}, agent="test")
        result = LearningOptimizer(artifact_store).run()
        assert result["summary"]["recommendation_count"] >= 4
        assert all("confidence" in item for item in result["recommendations"])
        assert artifact_store.artifact_exists("learning_optimization_report")
