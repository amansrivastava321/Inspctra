from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.self_optimization.self_optimization_orchestrator import SelfOptimizationOrchestrator


def test_self_optimization_orchestrator_generates_all_artifacts(artifact_store):
    artifact_store.save_artifact("benchmark_scoring_report", {"overall_score": 0.8}, agent="test")
    artifact_store.save_artifact("ai_confidence_report", {"overall_confidence": 0.7, "stage_confidence": {}}, agent="test")

    summary = SelfOptimizationOrchestrator(artifact_store).run(workspace="default", cross_project=True)

    assert summary["advisory_only"] is True
    assert summary["artifact_backed_learning_only"] is True
    assert summary["automatic_source_modification"] is False
    assert summary["external_upload"] is False
    assert summary["cross_project"] is True

    expected = [
        "audit_memory_index",
        "strategy_adaptation_plan",
        "finding_deduplication_report",
        "confidence_calibration_report",
        "evidence_quality_optimization",
        "scenario_optimization_report",
        "risk_prediction_report",
        "remediation_learning_report",
        "cross_project_learning_report",
        "self_optimization_summary",
    ]
    validator = ArtifactValidator()
    for artifact in expected:
        payload = artifact_store.load_artifact(artifact)
        validated = validator.validate_for_consumption(artifact, payload)
        assert isinstance(validated.data, dict)


def test_self_optimization_orchestrator_handles_malformed_artifacts_safely(artifact_store):
    artifact_store.save_artifact("benchmark_scoring_report", "bad", agent="test")
    summary = SelfOptimizationOrchestrator(artifact_store).run()
    assert summary["advisory_only"] is True
