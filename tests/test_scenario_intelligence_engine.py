from qa_ai.ai_orchestration.scenario_intelligence_engine import ScenarioIntelligenceEngine


def test_scenario_intelligence_engine_generates_candidate_plan(artifact_store):
    artifact_store.save_artifact(
        "test_intents",
        {
            "test_intents": [
                {
                    "intent_id": "INTENT-001",
                    "domain": "distributed",
                    "expected_evidence": ["distributed_runtime_report"],
                    "confidence": 0.66,
                }
            ]
        },
        agent="test",
    )

    result = ScenarioIntelligenceEngine(artifact_store).run()
    assert result["summary"]["scenario_count"] == 1
    scenario = result["scenarios"][0]
    assert scenario["execution_system"] in {"DistributedRuntimeRunner", "ScenarioEngine", "MobileRuntimeRunner", "LiveScenarioRunner"}
    assert scenario["deterministic_validation_required"] is True

