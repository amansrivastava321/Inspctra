"""
test_learning_registry.py - Tests for learning registry persistence.
"""

from qa_ai.improvement.learning_registry import LearningRegistry


class TestLearningRegistry:
    def test_stores_lessons_by_category_without_duplicates(self, artifact_store):
        registry = LearningRegistry(artifact_store)

        result = registry.run(
            lessons={
                "false_positives": [{"id": "FP-1", "pattern": "generated migration warning"}],
                "effective_tests": [{"id": "T-1", "test_id": "TEST-1"}],
                "recurring_root_causes": [{"id": "RC-1", "description": "missing auth guard"}],
                "high_value_fix_patterns": [{"id": "PAT-1", "description": "centralize auth middleware"}],
                "risky_modules": [{"id": "MOD-1", "module": "qa_ai/audit/api_audit.py"}],
            }
        )
        result = registry.run(
            lessons={
                "false_positives": [{"id": "FP-1", "pattern": "generated migration warning"}],
            }
        )

        assert len(result["false_positives"]) == 1
        assert result["summary"]["total_lessons"] == 5
        assert artifact_store.artifact_exists("learning_registry")
