from qa_ai.cicd.pr_audit_runner import PRAuditRunner


def test_pr_audit_runner_generates_incremental_report(artifact_store):
    artifact_store.save_artifact(
        "correlated_findings",
        {
            "findings": [
                {"id": "F-1", "severity": "critical", "category": "security"},
                {"id": "F-2", "severity": "high", "category": "quality"},
            ]
        },
        agent="test",
    )
    artifact_store.save_artifact("execution_results", {"coverage_percent": 76.5}, agent="test")
    artifact_store.save_artifact("evidence_graph", {"summary": {"total_evidence": 5}}, agent="test")

    report = PRAuditRunner(artifact_store).run(changed_files=["qa_ai/cicd/release_gate_engine.py"])

    assert report["mode"] == "ci_incremental"
    assert "qa_ai/cicd/release_gate_engine.py" in report["changed_files"]
    assert report["critical_security_findings"] == 1
    assert report["evidence_count"] == 5

