from qa_ai.ai_orchestration.test_intent_generator import TestIntentGenerator


def test_test_intent_generator_includes_required_fields(artifact_store):
    artifact_store.save_artifact(
        "ai_audit_strategy",
        {
            "priorities": [
                {"domain": "security", "confidence": 0.82},
                {"domain": "api", "confidence": 0.71},
            ]
        },
        agent="test",
    )
    artifact_store.save_artifact("software_understanding", {"software_type": "api_backend_service"}, agent="test")

    result = TestIntentGenerator(artifact_store).run()
    assert result["summary"]["intent_count"] >= 1
    intent = result["test_intents"][0]
    assert intent["why_this_matters"]
    assert intent["risk_being_tested"]
    assert isinstance(intent["expected_evidence"], list) and intent["expected_evidence"]
    assert intent["required_environment"]
    assert "confidence" in intent

