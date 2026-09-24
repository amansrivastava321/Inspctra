from qa_ai.cicd_runtime.incremental_audit_engine import IncrementalAuditEngine


def test_incremental_audit_engine_uses_graph_relationships(artifact_store):
    artifact_store.save_artifact("execution_trace", {"events": [{"id": "1"}]}, agent="test")
    artifact_store.save_artifact("replay_analysis", {"comparison": {"total_regressions": 1}}, agent="test")

    result = IncrementalAuditEngine(artifact_store).run(
        changed_files=["qa_ai/cicd_runtime/release_gate_engine.py", "qa_ai/orchestration/workflow_engine.py"]
    )

    assert result["scope_mode"] == "incremental_graph_runtime"
    assert isinstance(result["graph_related_files"], list)
    assert result["runtime_trace_context"] is True
    assert result["replay_history_context"] is True
    assert "replay_analysis" in result["recommended_phases"]
