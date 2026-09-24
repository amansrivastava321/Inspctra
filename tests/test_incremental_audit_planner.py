from qa_ai.cicd.incremental_audit_planner import IncrementalAuditPlanner


def test_incremental_audit_planner_selects_changed_modules(artifact_store):
    result = IncrementalAuditPlanner(artifact_store).run(
        changed_files=[
            "qa_ai/cicd/release_gate_engine.py",
            "qa_ai/audit/security_audit.py",
            "tests/test_release_gate_engine.py",
        ]
    )

    assert "cicd" in result["changed_modules"]
    assert "audit" in result["changed_modules"]
    assert "tests" in result["changed_modules"]
    assert "release_readiness_audit" in result["recommended_phases"]

