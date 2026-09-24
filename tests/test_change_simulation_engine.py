from qa_ai.remediation_runtime.change_simulation_engine import ChangeSimulationEngine


def test_change_simulation_engine_outputs_blast_radius_and_runtime_sensitivity(artifact_store):
    artifact_store.save_artifact(
        "patch_proposals",
        {
            "proposals": [
                {
                    "proposal_id": "PATCH-001",
                    "fix_id": "FIX-001",
                    "affected_files": ["qa_ai/improvement/fix_planner.py"],
                }
            ]
        },
        agent="test",
    )

    result = ChangeSimulationEngine(artifact_store).run()

    assert artifact_store.artifact_exists("remediation_change_simulation")
    assert result["summary"]["proposal_count"] == 1
    impact = result["impacts"][0]
    assert impact["blast_radius"] in {"none", "narrow", "moderate", "broad"}
    assert impact["runtime_sensitivity"] in {"low", "medium", "high", "critical"}
    assert "dependency_propagation" in impact
