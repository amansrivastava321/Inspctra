from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.self_optimization.risk_prediction_engine import RiskPredictionEngine


def test_risk_prediction_engine_uses_hotspots_and_history(artifact_store):
    artifact_store.save_artifact(
        "audit_memory_index",
        {"runs": [{"source": {"findings": 20}}, {"source": {"findings": 10}}]},
        agent="test",
    )
    artifact_store.save_artifact("replay_analysis", {"comparison": {"total_regressions": 3}}, agent="test")
    artifact_store.save_artifact("remediation_learning_report", {"summary": {"regression_causing_fixes": 2}}, agent="test")
    artifact_store.save_artifact("benchmark_comparison_report", {"degraded_detection": True}, agent="test")

    report = RiskPredictionEngine(artifact_store).run()
    assert report["advisory_only"] is True
    assert report["signals"]["recurring_findings"] == 30
    assert report["signals"]["runtime_instability"] == 3
    assert isinstance(report["predictions"], list)

    validated = ArtifactValidator().validate_for_consumption(
        "risk_prediction_report",
        artifact_store.load_artifact("risk_prediction_report"),
    )
    assert isinstance(validated.data, dict)
