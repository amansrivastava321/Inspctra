from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.remediation.remediation_orchestrator import RemediationOrchestrator


def test_remediation_orchestrator_generates_artifacts_and_keeps_safety_defaults(artifact_store):
    artifact_store.save_artifact(
        "fix_plan",
        {
            "fixes": [
                {
                    "fix_id": "FIX-001",
                    "title": "Harden auth check",
                    "description": "Add missing auth validation.",
                    "risk_level": "high",
                    "confidence": 0.82,
                    "affected_files": ["qa_ai/audit/api_audit.py"],
                    "affected_functions": ["_check_auth"],
                    "finding_ids": ["F-001"],
                    "recommended_tests": ["TEST-SEC-001"],
                    "safe_steps": ["Minimal patch", "Targeted retest"],
                }
            ]
        },
        agent="test",
    )
    artifact_store.save_artifact(
        "correlated_findings",
        {"findings": [{"id": "F-001", "title": "Missing auth check", "severity": "high", "file_path": "qa_ai/audit/api_audit.py"}]},
        agent="test",
    )
    artifact_store.save_artifact(
        "root_cause_analysis",
        {"root_causes": [{"cause_id": "RC-001", "description": "Auth branch bypass", "finding_ids": ["F-001"]}]},
        agent="test",
    )
    artifact_store.save_artifact(
        "ai_fix_reasoning",
        {"strategies": [{"fix_id": "FIX-001", "recommended_strategy": "stage_changes_incrementally"}]},
        agent="test",
    )
    artifact_store.save_artifact(
        "change_impact_analysis",
        {"affected_tests": ["TEST-SEC-001"], "affected_files": ["qa_ai/audit/api_audit.py"], "affected_workflows": ["auth"], "affected_apis": ["/users"]},
        agent="test",
    )
    artifact_store.save_artifact(
        "test_plan",
        {"test_suites": {"smoke": [{"id": "SMOKE-1", "type": "smoke"}], "security": [{"id": "TEST-SEC-001", "type": "security"}]}},
        agent="test",
    )

    summary = RemediationOrchestrator(artifact_store).run(
        dry_run=True,
        proposal_only=False,
        approve_fix_ids=["FIX-001"],
        sandbox=True,
    )

    assert summary["advisory_only_default"] is True
    assert summary["permission_gated"] is True
    assert summary["safety"]["apply_by_default"] is False
    assert summary["counts"]["proposals"] >= 1

    expected = [
        "patch_proposals",
        "change_simulation_report",
        "rollback_plan",
        "remediation_retest_scope",
        "remediation_risk_report",
        "remediation_validation_report",
        "remediation_approval_log",
        "remediation_summary",
    ]
    validator = ArtifactValidator()
    for name in expected:
        payload = artifact_store.load_artifact(name)
        assert isinstance(payload, dict)
        validated = validator.validate_for_consumption(name, payload)
        assert isinstance(validated.data, dict)
