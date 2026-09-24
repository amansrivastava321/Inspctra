import qa_ai.ai_orchestration.ai_audit_orchestrator as ai_orch_module
from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.ai_orchestration.ai_audit_orchestrator import AIAuditOrchestrator


def test_ai_audit_orchestrator_runs_with_deterministic_fallback_and_validates_artifacts(artifact_store, monkeypatch):
    monkeypatch.setattr(ai_orch_module.AIAuditOrchestrator, "_model_available", lambda self: False)
    artifact_store.save_artifact(
        "app_map",
        {
            "stack": {"framework": "fastapi", "app_type": "backend", "language": "python"},
            "screens": [{"path": "/dashboard", "auth_required": True}],
            "api_endpoints": [{"path": "/users", "auth_required": True}],
            "critical_flows": [{"name": "auth_flow", "priority": "critical", "type": "auth"}],
            "security_surfaces": {"auth_endpoints": ["/users"]},
        },
        agent="test",
    )
    artifact_store.save_artifact("correlated_findings", {"findings": [{"id": "F-1", "title": "Missing auth", "severity": "high"}]}, agent="test")
    artifact_store.save_artifact("root_cause_analysis", {"root_causes": [{"cause_id": "RC-1", "description": "Auth branch", "root_type": "file_hotspot", "finding_ids": ["F-1"], "confidence": 0.72}]}, agent="test")
    artifact_store.save_artifact("semantic_root_cause_analysis", {"hypotheses": [{"finding_ids": ["F-1"], "confidence": 0.65}]}, agent="test")
    artifact_store.save_artifact("execution_trace", {"events": [{"action": "navigate"}]}, agent="test")
    artifact_store.save_artifact("network_trace", {"requests": [{"url": "/users"}]}, agent="test")
    artifact_store.save_artifact("evidence_graph", {"graph": {"nodes": [{"node_id": "n1"}]}}, agent="test")

    result = AIAuditOrchestrator(artifact_store).run(app_path=".", dry_run=True, enabled=True)
    assert result["mode"] == "deterministic_fallback"
    assert result["safety"]["no_hallucinated_findings"] is True
    assert result["decision_count"] >= 1
    assert result["overall_confidence"] >= 0.0

    validator = ArtifactValidator()
    for artifact_name in [
        "software_understanding",
        "ai_audit_strategy",
        "test_intents",
        "intelligent_scenario_plan",
        "evidence_interpretation",
        "ai_rca_coordination",
        "ai_improvement_strategy",
        "ai_decision_log",
        "ai_confidence_report",
        "ai_audit_brain_summary",
    ]:
        payload = artifact_store.load_artifact(artifact_name)
        validated = validator.validate_for_consumption(artifact_name, payload)
        assert validated.valid is True
