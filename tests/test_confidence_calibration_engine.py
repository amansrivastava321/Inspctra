from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.self_optimization.confidence_calibration_engine import ConfidenceCalibrationEngine


def test_confidence_calibration_engine_detects_overconfidence(artifact_store):
    artifact_store.save_artifact(
        "ai_confidence_report",
        {"overall_confidence": 0.9, "stage_confidence": {"security": 0.95, "api": 0.2}},
        agent="test",
    )
    artifact_store.save_artifact("benchmark_scoring_report", {"overall_score": 0.5}, agent="test")
    artifact_store.save_artifact("release_gate_decision", {"decision": "warning"}, agent="test")

    report = ConfidenceCalibrationEngine(artifact_store).run()

    assert report["advisory_only"] is True
    assert "security" in report["overconfident_modules"]
    assert report["calibration_suggestion"] == "decrease"

    validated = ArtifactValidator().validate_for_consumption(
        "confidence_calibration_report",
        artifact_store.load_artifact("confidence_calibration_report"),
    )
    assert isinstance(validated.data, dict)


def test_confidence_calibration_engine_handles_malformed_artifacts_safely(artifact_store):
    artifact_store.save_artifact("ai_confidence_report", "bad", agent="test")
    report = ConfidenceCalibrationEngine(artifact_store).run()
    assert report["advisory_only"] is True
