from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.self_optimization.remediation_learning_engine import RemediationLearningEngine


def test_remediation_learning_engine_detects_regression_patterns(artifact_store):
    artifact_store.save_artifact("remediation_validation_report", {"valid_proposals": [{"id": "P1"}], "rejected_proposals": [{"id": "P2"}]}, agent="test")
    artifact_store.save_artifact("remediation_rollback_plan", {"plans": [{"proposal_id": "P1"}]}, agent="test")
    artifact_store.save_artifact(
        "patch_proposals",
        {"proposals": [{"affected_files": ["qa_ai/a.py", "qa_ai/b.py"]}, {"affected_files": ["qa_ai/a.py"]}]},
        agent="test",
    )
    artifact_store.save_artifact("regression_guard_report", {"regression_detected": True}, agent="test")

    report = RemediationLearningEngine(artifact_store).run()
    assert report["advisory_only"] is True
    assert report["fix_types_reducing_risk"] == 1
    assert report["regression_causing_fixes"] == 1
    assert len(report["remediation_sensitive_modules"]) >= 1

    validated = ArtifactValidator().validate_for_consumption(
        "remediation_learning_report",
        artifact_store.load_artifact("remediation_learning_report"),
    )
    assert isinstance(validated.data, dict)
