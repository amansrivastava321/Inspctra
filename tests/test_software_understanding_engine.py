from qa_ai.platform_performance.incremental_graph_manager import IncrementalGraphManager
from qa_ai.ai_orchestration.software_understanding_engine import SoftwareUnderstandingEngine


def test_software_understanding_engine_infers_type_and_workflows(artifact_store):
    artifact_store.save_artifact(
        "app_map",
        {
            "stack": {"framework": "fastapi", "app_type": "backend", "language": "python"},
            "screens": [{"path": "/dashboard", "auth_required": True}],
            "api_endpoints": [{"path": "/users", "auth_required": True, "risk": {"risk_level": "high"}}],
            "critical_flows": [{"name": "auth_flow", "priority": "critical", "type": "auth"}],
            "security_surfaces": {"auth_endpoints": ["/users"], "admin_endpoints": ["/admin"]},
        },
        agent="test",
    )

    result = SoftwareUnderstandingEngine(artifact_store).run(app_path=".")
    assert result["software_type"] in {"api_backend_service", "api_service", "full_stack_application"}
    assert "auth_flow" in result["critical_workflows"]
    assert "authenticated_api" in result["sensitive_areas"]
    assert result["summary"]["confidence"] > 0
    assert IncrementalGraphManager().plan()["graph_stats"]["nodes"] > 0

