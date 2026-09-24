from qa_ai.ai_orchestration.ai_confidence_tracker import AIConfidenceTracker


def test_ai_confidence_tracker_outputs_stage_and_overall_scores(artifact_store):
    report = AIConfidenceTracker(artifact_store).run(
        stage_confidence={
            "understanding": 0.7,
            "strategy": 0.8,
            "scenario_generation": 0.6,
            "evidence_interpretation": 0.75,
            "rca": 0.72,
            "improvement_planning": 0.68,
        }
    )
    assert report["summary"]["confidence_present"] is True
    assert report["overall_confidence"] > 0
    assert "understanding" in report["stage_confidence"]

