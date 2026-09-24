"""
test_ai_reasoning_orchestrator.py - Tests for AI reasoning orchestration and fallback safety.
"""

import qa_ai.ai_reasoning.ai_reasoning_orchestrator as orchestrator_module
from qa_ai.ai_reasoning.ai_reasoning_orchestrator import AIReasoningOrchestrator


class TestAIReasoningOrchestrator:
    def test_orchestrator_deterministic_fallback_without_model(self, artifact_store, monkeypatch):
        monkeypatch.setattr(orchestrator_module.AIReasoningOrchestrator, "_detect_model_availability", lambda self: False)
        artifact_store.save_artifact("correlated_findings", {"findings": [{"id": "F1", "title": "Missing auth"}]}, agent="test")
        artifact_store.save_artifact("root_cause_analysis", {"root_causes": []}, agent="test")
        artifact_store.save_artifact("benchmark_metrics", {"metrics": {"issue_coverage": 0.5}}, agent="test")

        result = AIReasoningOrchestrator(artifact_store).run(enabled=True, dry_run=True)
        assert result["enabled"] is True
        assert result["mode"] == "deterministic_fallback"
        assert result["model_available"] is False
        assert artifact_store.artifact_exists("ai_reasoning_summary")
        for artifact_name in [
            "reasoning_context",
            "semantic_root_cause_analysis",
            "adaptive_audit_plan",
            "evidence_synthesis",
            "semantic_risk_report",
            "ai_generated_scenarios",
            "ai_fix_reasoning",
            "learning_optimization_report",
            "ai_reasoning_summary",
        ]:
            assert artifact_store.artifact_exists(artifact_name), artifact_name

    def test_orchestrator_disabled_mode(self, artifact_store):
        result = AIReasoningOrchestrator(artifact_store).run(enabled=False, dry_run=True)
        assert result["enabled"] is False
        assert result["mode"] == "disabled"
        assert artifact_store.artifact_exists("ai_reasoning_summary")
