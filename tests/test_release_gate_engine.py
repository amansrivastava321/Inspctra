from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.cicd.release_gate_engine import ReleaseGateEngine
from qa_ai.cicd_runtime.release_gate_engine import ReleaseGateEngine as RuntimeReleaseGateEngine


def test_release_gate_engine_blocks_on_critical_findings(artifact_store):
    artifact_store.save_artifact(
        "cicd_audit_report",
        {"critical_security_findings": 2, "coverage_percent": 80, "evidence_count": 10},
        agent="test",
    )
    artifact_store.save_artifact(
        "baseline_comparison",
        {"regressions": {"critical_findings_increased": False}},
        agent="test",
    )

    result = ReleaseGateEngine(artifact_store).run()
    assert result["decision"] == "blocked"

    validated = ArtifactValidator().validate_for_consumption("release_gate_decision", result)
    assert validated.valid is True


def test_release_gate_engine_handles_malformed_artifacts_safely(artifact_store):
    artifact_store.save_artifact("cicd_audit_report", {"critical_security_findings": "bad"}, agent="test")
    artifact_store.save_artifact("baseline_comparison", {"regressions": "bad-shape"}, agent="test")

    result = ReleaseGateEngine(artifact_store).run()
    assert result["decision"] in {"pass", "warning", "blocked"}


def test_cicd_runtime_release_gate_blocks_on_critical_regressions(artifact_store):
    artifact_store.save_artifact(
        "correlated_findings",
        {"findings": [{"id": "F-1", "severity": "critical"}]},
        agent="test",
    )
    artifact_store.save_artifact(
        "baseline_comparison_report",
        {"summary": {"regression_growth": 1}, "current": {"runtime_instability": 2}},
        agent="test",
    )
    artifact_store.save_artifact(
        "remediation_validation_report",
        {"valid_proposals": [], "rejected_proposals": [{"proposal_id": "P1"}]},
        agent="test",
    )
    artifact_store.save_artifact("evidence_graph", {"summary": {"total_evidence": 1}}, agent="test")
    artifact_store.save_artifact("replay_analysis", {"comparison": {"total_regressions": 1}}, agent="test")

    result = RuntimeReleaseGateEngine(artifact_store).run()

    assert result["decision"] == "blocked"
    assert "critical_findings_present" in result["blocked_reasons"]
