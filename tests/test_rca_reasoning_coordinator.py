from qa_ai.ai_orchestration.rca_reasoning_coordinator import RCAReasoningCoordinator


def test_rca_reasoning_coordinator_requires_deterministic_refs(artifact_store):
    artifact_store.save_artifact(
        "root_cause_analysis",
        {
            "root_causes": [
                {
                    "cause_id": "RC-001",
                    "description": "Auth branch bypass",
                    "root_type": "file_hotspot",
                    "finding_ids": ["F-1"],
                    "confidence": 0.8,
                }
            ]
        },
        agent="test",
    )
    artifact_store.save_artifact(
        "semantic_root_cause_analysis",
        {"hypotheses": [{"finding_ids": ["F-1"], "confidence": 0.7, "evidence_references": ["trace:1"]}]},
        agent="test",
    )

    result = RCAReasoningCoordinator(artifact_store).run()
    assert result["summary"]["coordinated_hypothesis_count"] == 1
    hypothesis = result["hypotheses"][0]
    assert any("root_cause_analysis:RC-001" == ref for ref in hypothesis["evidence_references"])
    assert result["safety"]["requires_deterministic_reference"] is True

