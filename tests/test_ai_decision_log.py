from qa_ai.ai_orchestration.ai_decision_log import AIDecisionLog


def test_ai_decision_log_requires_source_references(artifact_store):
    log = AIDecisionLog(artifact_store).run(
        decisions=[
            {
                "decision": "Prioritize security path",
                "reason": "Critical auth workflow detected",
                "source_artifacts": ["software_understanding.json"],
                "confidence": 0.78,
                "fallback_mode": "deterministic_fallback",
            }
        ]
    )
    assert log["summary"]["decision_count"] == 1
    assert log["summary"]["all_have_sources"] is True
    assert log["decisions"][0]["source_artifacts"] == ["software_understanding.json"]

