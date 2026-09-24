from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.cicd.cicd_reporter import CICDReporter


def test_cicd_reporter_aggregates_artifacts_and_validates_contract(artifact_store):
    artifact_store.save_artifact("cicd_provider_report", {"provider": "github", "known_provider": True}, agent="test")
    artifact_store.save_artifact(
        "ci_workflow_plan",
        {"provider": "github", "file_plan": {"path": ".github/workflows/qa_ai_audit.yml", "action": "plan_only"}},
        agent="test",
    )
    artifact_store.save_artifact(
        "incremental_audit_plan",
        {"changed_files": ["qa_ai/cicd/release_gate_engine.py"], "changed_modules": ["cicd"], "recommended_phases": ["release_gate"]},
        agent="test",
    )
    artifact_store.save_artifact("baseline_comparison", {"summary": {"baseline_present": True}}, agent="test")
    artifact_store.save_artifact("release_gate_decision", {"decision": "warning"}, agent="test")
    artifact_store.save_artifact(
        "cicd_audit_report",
        {"critical_security_findings": 0, "coverage_percent": 72.0, "evidence_count": 3},
        agent="test",
    )

    result = CICDReporter(artifact_store).run()

    assert result["provider"] == "github"
    assert result["release_gate_decision"] == "warning"
    assert result["summary"]["permission_gated"] is True
    validator = ArtifactValidator()
    for artifact_name in [
        "cicd_provider_report",
        "ci_workflow_plan",
        "incremental_audit_plan",
        "baseline_comparison",
        "release_gate_decision",
        "cicd_audit_report",
    ]:
        payload = artifact_store.load_artifact(artifact_name)
        validated = validator.validate_for_consumption(artifact_name, payload)
        assert validated.valid is True
