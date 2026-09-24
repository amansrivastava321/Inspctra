"""
test_semantic_rca_engine.py - Tests for semantic RCA fallback and confidence fields.
"""

from qa_ai.ai_reasoning.semantic_rca_engine import SemanticRCAEngine


class TestSemanticRCAEngine:
    def test_semantic_rca_fallback_without_model(self, artifact_store):
        artifact_store.save_artifact(
            "root_cause_analysis",
            {
                "root_causes": [
                    {
                        "cause_id": "RC-1",
                        "description": "Endpoint auth guard missing",
                        "confidence": 0.77,
                        "finding_ids": ["F1"],
                        "affected_files": ["app/api.py"],
                    }
                ]
            },
            agent="test",
        )
        artifact_store.save_artifact(
            "correlated_findings",
            {"findings": [{"id": "F1", "title": "Missing auth"}]},
            agent="test",
        )
        artifact_store.save_artifact("evidence_graph", {"summary": {"evidence_nodes": 2}}, agent="test")

        result = SemanticRCAEngine(artifact_store).run(use_model=False)
        assert result["mode"] == "deterministic_fallback"
        assert result["summary"]["hypothesis_count"] >= 1
        hypothesis = result["hypotheses"][0]
        assert "confidence" in hypothesis
        assert hypothesis["deterministic_references"]
        assert artifact_store.artifact_exists("semantic_root_cause_analysis")
