"""
test_reasoning_context_builder.py - Tests for context bundle generation and pruning.
"""

from qa_ai.ai_reasoning.reasoning_context_builder import ReasoningContextBuilder


class TestReasoningContextBuilder:
    def test_context_generation_with_references_and_pruning(self, artifact_store):
        artifact_store.save_artifact(
            "correlated_findings",
            {"findings": [{"id": "F1", "title": "Missing auth", "severity": "high", "category": "security"}]},
            agent="test",
        )
        artifact_store.save_artifact(
            "root_cause_analysis",
            {"root_causes": [{"cause_id": "RC1", "description": "Auth guard missing", "confidence": 0.8}]},
            agent="test",
        )

        result = ReasoningContextBuilder(artifact_store).run(max_items=3, max_chars=2000)
        assert "context_items" in result
        assert "graphify_context" in result
        assert result["summary"]["pruned_item_count"] <= 3
        assert any(item.get("deterministic_reference") for item in result["context_items"])
        assert artifact_store.artifact_exists("reasoning_context")
