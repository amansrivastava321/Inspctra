from qa_ai.cicd.pipeline_policy_engine import PipelinePolicyEngine
from qa_ai.cicd_runtime.pipeline_policy_engine import PipelinePolicyEngine as RuntimePipelinePolicyEngine


def test_pipeline_policy_engine_blocks_critical_missing_evidence_and_warns_low_coverage():
    policy = PipelinePolicyEngine().evaluate(
        audit_report={
            "critical_security_findings": 1,
            "coverage_percent": 42.0,
            "evidence_count": 0,
        },
        baseline_comparison={"regressions": {"critical_findings_increased": True}},
    )

    blocked = set(policy["summary"]["blocked_rules"])
    warned = set(policy["summary"]["warning_rules"])
    assert "block_critical_security_findings" in blocked
    assert "block_regression_increase" in blocked
    assert "block_missing_evidence" in blocked
    assert "warn_low_coverage" in warned


def test_cicd_runtime_policy_engine_blocks_invalid_release_conditions(artifact_store):
    artifact_store.save_artifact(
        "release_gate_decision",
        {"signals": {"critical_findings": 2, "evidence_count": 0}},
        agent="test",
    )
    artifact_store.save_artifact(
        "baseline_comparison_report",
        {"summary": {"regression_growth": 2}},
        agent="test",
    )
    artifact_store.save_artifact(
        "remediation_validation_report",
        {"valid_proposals": [], "rejected_proposals": [{"proposal_id": "P1"}]},
        agent="test",
    )
    artifact_store.save_artifact(
        "replay_analysis",
        {"comparison": {"total_regressions": 3}},
        agent="test",
    )

    result = RuntimePipelinePolicyEngine(artifact_store).run()
    blocked = set(result["summary"]["blocked_rules"])
    warned = set(result["summary"]["warning_rules"])
    assert "block_critical_security_findings" in blocked
    assert "block_unresolved_regressions" in blocked
    assert "require_evidence_completeness" in blocked
    assert "require_remediation_validation" in blocked
    assert "require_replay_stability" in warned
