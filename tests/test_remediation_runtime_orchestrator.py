from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.remediation_runtime.remediation_runtime_orchestrator import RemediationRuntimeOrchestrator


def _seed_runtime_inputs(artifact_store):
    artifact_store.save_artifact(
        "fix_plan",
        {
            "fixes": [
                {
                    "fix_id": "FIX-001",
                    "title": "Patch auth check",
                    "description": "Fix missing auth validation",
                    "risk_level": "high",
                    "affected_files": ["qa_ai/audit/api_audit.py"],
                    "affected_workflows": ["auth_flow"],
                    "recommended_tests": ["TEST-SEC-001"],
                    "finding_ids": ["F-001"],
                }
            ]
        },
        agent="test",
    )
    artifact_store.save_artifact(
        "correlated_findings",
        {"findings": [{"id": "F-001", "title": "Missing auth", "severity": "high", "file_path": "qa_ai/audit/api_audit.py"}]},
        agent="test",
    )
    artifact_store.save_artifact(
        "root_cause_analysis",
        {"root_causes": [{"cause_id": "RC-001", "description": "Auth branch bypass", "finding_ids": ["F-001"], "affected_workflows": ["auth_flow"]}]},
        agent="test",
    )
    artifact_store.save_artifact(
        "ai_fix_reasoning",
        {"strategies": [{"fix_id": "FIX-001", "recommended_strategy": "incremental", "confidence": 0.9}]},
        agent="test",
    )
    artifact_store.save_artifact(
        "test_plan",
        {"test_suites": {"security": [{"id": "TEST-SEC-001", "type": "security"}], "smoke": [{"id": "SMOKE-1", "type": "smoke"}]}},
        agent="test",
    )


def test_remediation_runtime_orchestrator_generates_all_artifacts_with_safety_defaults(artifact_store):
    _seed_runtime_inputs(artifact_store)

    summary = RemediationRuntimeOrchestrator(artifact_store).run(
        dry_run=True,
        proposal_only=False,
        simulate=False,
        sandbox=True,
        approve_fix_ids=[],
    )

    assert summary["safety"]["advisory_first"] is True
    assert summary["safety"]["permission_gated"] is True
    assert summary["safety"]["direct_file_modification_by_default"] is False
    assert summary["counts"]["proposals"] >= 1

    approval = artifact_store.load_artifact("remediation_approval_workflow")
    assert isinstance(approval, dict)
    assert approval["summary"]["pending_approval"] >= 1

    sandbox = artifact_store.load_artifact("remediation_sandbox_report")
    assert isinstance(sandbox, dict)
    assert sandbox["summary"]["source_files_modified"] is False

    expected = [
        "patch_proposals",
        "remediation_change_simulation",
        "remediation_rollback_plan",
        "remediation_sandbox_report",
        "remediation_approval_workflow",
        "remediation_retest_scope",
        "remediation_validation_report",
        "remediation_audit_log",
        "remediation_runtime_summary",
    ]
    validator = ArtifactValidator()
    for name in expected:
        payload = artifact_store.load_artifact(name)
        assert isinstance(payload, dict)
        validated = validator.validate_for_consumption(name, payload)
        assert isinstance(validated.data, dict)


def test_remediation_runtime_orchestrator_handles_malformed_artifacts_safely(artifact_store):
    artifact_store.save_artifact("fix_plan", {"fixes": ["bad"]}, agent="test")
    artifact_store.save_artifact("patch_proposals", "not-a-dict", agent="test")

    summary = RemediationRuntimeOrchestrator(artifact_store).run(dry_run=True, proposal_only=True)

    assert summary["mode"] == "proposal_only"
    assert summary["safety"]["advisory_first"] is True
