from qa_ai.remediation_runtime.remediation_validation_engine import RemediationValidationEngine


def test_remediation_validation_engine_rejects_unsafe_and_hallucinated_fixes(artifact_store):
    artifact_store.save_artifact(
        "fix_plan",
        {"fixes": [{"fix_id": "FIX-001", "affected_files": ["app.py"]}]},
        agent="test",
    )
    artifact_store.save_artifact("correlated_findings", {"findings": [{"id": "F-001"}]}, agent="test")
    artifact_store.save_artifact("root_cause_analysis", {"root_causes": [{"cause_id": "RC-001"}]}, agent="test")
    artifact_store.save_artifact("ai_fix_reasoning", {"strategies": [{"fix_id": "FIX-001", "confidence": 0.8}]}, agent="test")
    artifact_store.save_artifact("remediation_retest_scope", {"tests": ["TEST-1"]}, agent="test")
    artifact_store.save_artifact("remediation_change_simulation", {"impacts": []}, agent="test")

    artifact_store.save_artifact(
        "patch_proposals",
        {
            "proposals": [
                {
                    "proposal_id": "PATCH-001",
                    "fix_id": "FIX-001",
                    "advisory_only": True,
                    "approval_required": True,
                    "apply_by_default": False,
                    "affected_files": ["app.py"],
                    "source_artifacts": ["fix_plan.json"],
                    "source_evidence": [{"artifact": "correlated_findings", "reference": "F-001"}],
                    "retest_requirements": ["TEST-1"],
                    "pseudo_patch": "safe patch preview",
                },
                {
                    "proposal_id": "PATCH-002",
                    "fix_id": "FIX-999",
                    "advisory_only": True,
                    "approval_required": True,
                    "apply_by_default": False,
                    "affected_files": ["app.py"],
                    "source_artifacts": ["fix_plan.json"],
                    "source_evidence": [{"artifact": "correlated_findings", "reference": "UNKNOWN"}],
                    "pseudo_patch": "rm -rf /",
                },
            ]
        },
        agent="test",
    )

    report = RemediationValidationEngine(artifact_store).run()

    assert artifact_store.artifact_exists("remediation_validation_report")
    assert len(report["valid_proposals"]) == 1
    assert len(report["rejected_proposals"]) == 1
    reasons = report["rejected_proposals"][0]["reasons"]
    assert any("hallucinated" in reason for reason in reasons)
    assert any("unsafe" in reason for reason in reasons)
