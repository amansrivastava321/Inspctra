from qa_ai.ai_orchestration.audit_strategy_engine import AuditStrategyEngine


def test_audit_strategy_prioritizes_by_software_type(artifact_store):
    artifact_store.save_artifact(
        "software_understanding",
        {
            "software_type": "mobile_application",
            "business_risk_areas": ["offline_sync", "authenticated_api"],
            "graphify_context": {"graph_nodes": 4000},
        },
        agent="test",
    )
    artifact_store.save_artifact("benchmark_summary", {"totals": {"findings_total": 12}}, agent="test")
    artifact_store.save_artifact("doctor_report", {"status": "ok"}, agent="test")

    result = AuditStrategyEngine(artifact_store).run()
    domains = [row["domain"] for row in result["priorities"]]
    assert domains[0] in {"mobile", "security", "sync"}
    assert "mobile" in domains
    assert result["fallback_mode"] == "deterministic_fallback"

