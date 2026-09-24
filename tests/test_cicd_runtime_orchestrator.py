from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.cicd_runtime.cicd_runtime_orchestrator import CICDRuntimeOrchestrator


def test_cicd_runtime_orchestrator_generates_all_runtime_artifacts(artifact_store, tmp_dir):
    (tmp_dir / ".github" / "workflows").mkdir(parents=True)
    artifact_store.save_artifact(
        "correlated_findings",
        {"findings": [{"id": "F-1", "severity": "critical", "category": "security"}]},
        agent="test",
    )
    artifact_store.save_artifact("evidence_graph", {"summary": {"total_evidence": 4}}, agent="test")
    artifact_store.save_artifact("replay_analysis", {"comparison": {"total_regressions": 1}}, agent="test")
    artifact_store.save_artifact(
        "remediation_validation_report",
        {"valid_proposals": [], "rejected_proposals": []},
        agent="test",
    )

    summary = CICDRuntimeOrchestrator(artifact_store).run(
        repo_path=str(tmp_dir),
        provider="github",
        changed_files=["qa_ai/cicd_runtime/release_gate_engine.py"],
        dry_run=True,
    )

    assert summary["advisory_only"] is True
    assert summary["permission_aware"] is True
    assert summary["rollback_aware"] is True
    assert summary["release_decision"] in {"pass", "warning", "blocked"}

    expected = [
        "cicd_provider_report",
        "github_actions_plan",
        "incremental_audit_plan",
        "baseline_comparison_report",
        "release_gate_decision",
        "pipeline_policy_report",
        "pr_audit_report",
        "cicd_audit_log",
        "cicd_runtime_summary",
    ]
    validator = ArtifactValidator()
    for name in expected:
        payload = artifact_store.load_artifact(name)
        assert isinstance(payload, dict)
        validated = validator.validate_for_consumption(name, payload)
        assert isinstance(validated.data, dict)


def test_cicd_runtime_orchestrator_handles_malformed_inputs_safely(artifact_store, tmp_dir):
    (tmp_dir / ".github" / "workflows").mkdir(parents=True)
    artifact_store.save_artifact("correlated_findings", {"findings": "bad-shape"}, agent="test")
    artifact_store.save_artifact("evidence_graph", "bad-shape", agent="test")
    artifact_store.save_artifact("replay_analysis", {"comparison": "bad-shape"}, agent="test")
    artifact_store.save_artifact("remediation_validation_report", {"rejected_proposals": "bad-shape"}, agent="test")

    summary = CICDRuntimeOrchestrator(artifact_store).run(repo_path=str(tmp_dir), provider="github", dry_run=True)

    assert summary["advisory_only"] is True
    assert summary["release_decision"] in {"pass", "warning", "blocked"}
