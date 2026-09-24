"""
test_evidence_synthesizer.py - Tests for evidence-safe synthesis behavior.
"""

from qa_ai.ai_reasoning.evidence_synthesizer import EvidenceSynthesizer


class TestEvidenceSynthesizer:
    def test_synthesis_uses_only_deterministic_references(self, artifact_store):
        artifact_store.save_artifact("evidence_graph", {"graph": {"nodes": [], "edges": []}}, agent="test")
        artifact_store.save_artifact("execution_trace", {"events": [{"action": "navigate"}]}, agent="test")
        artifact_store.save_artifact("network_trace", {"entries": [{"url": "/api"}]}, agent="test")

        result = EvidenceSynthesizer(artifact_store).run()
        assert result["summary"]["evidence_safety"] == "no_invented_evidence"
        for conclusion in result["conclusions"]:
            assert "confidence" in conclusion
            assert conclusion["deterministic_references"]
        assert artifact_store.artifact_exists("evidence_synthesis")
