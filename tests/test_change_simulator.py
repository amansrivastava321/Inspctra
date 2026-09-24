from qa_ai.remediation.change_simulator import ChangeSimulator


def test_change_simulator_uses_graphify_context(artifact_store, graphify_workspace):
    artifact_store.save_artifact(
        "patch_proposals",
        {
            "proposals": [
                {
                    "proposal_id": "PATCH-001",
                    "fix_id": "FIX-001",
                    "target_files": ["qa_ai/improvement/fix_planner.py"],
                }
            ]
        },
        agent="test",
    )

    result = ChangeSimulator(artifact_store).run()
    assert result["summary"]["graphify_used"] is True
    assert result["summary"]["graph_nodes_scanned"] == 2
    assert result["summary"]["graph_edges_scanned"] == 1
    assert len(result["impacts"]) == 1
    assert "qa_ai/improvement/fix_consumer.py" in result["impacts"][0]["impacted_files"]
