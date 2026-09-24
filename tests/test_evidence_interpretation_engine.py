from qa_ai.ai_orchestration.evidence_interpretation_engine import EvidenceInterpretationEngine


def test_evidence_interpretation_does_not_prove_without_finding_refs(artifact_store):
    artifact_store.save_artifact(
        "correlated_findings",
        {"findings": [{"id": "F-1", "title": "Missing auth", "severity": "high"}]},
        agent="test",
    )
    artifact_store.save_artifact("execution_trace", {"events": [{"action": "navigate"}]}, agent="test")
    artifact_store.save_artifact("network_trace", {"requests": [{"url": "/users"}]}, agent="test")
    artifact_store.save_artifact("evidence_graph", {"graph": {"nodes": [{"node_id": "n1"}]}}, agent="test")

    result = EvidenceInterpretationEngine(artifact_store).run()
    assert result["summary"]["proved"] == 0
    assert result["interpretations"][0]["status"] == "partially_proved"
    assert result["safety"]["no_claim_without_evidence"] is True

