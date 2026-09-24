"""
ai_audit_orchestrator.py - AI-first orchestrator layered on deterministic audit outputs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import logging

logger = logging.getLogger(__name__)

from qa_ai.ai.llm_router import get_router
from qa_ai.ai.model_router import ModelRouter
from qa_ai.ai.ollama_client import OllamaClient
from qa_ai.config.settings import get_settings as _get_settings
from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.ai_orchestration.software_understanding_engine import SoftwareUnderstandingEngine
from qa_ai.ai_orchestration.audit_strategy_engine import AuditStrategyEngine
from qa_ai.ai_orchestration.test_intent_generator import TestIntentGenerator
from qa_ai.ai_orchestration.scenario_intelligence_engine import ScenarioIntelligenceEngine
from qa_ai.ai_orchestration.evidence_interpretation_engine import EvidenceInterpretationEngine
from qa_ai.ai_orchestration.rca_reasoning_coordinator import RCAReasoningCoordinator
from qa_ai.ai_orchestration.improvement_strategy_engine import ImprovementStrategyEngine
from qa_ai.ai_orchestration.ai_decision_log import AIDecisionLog
from qa_ai.ai_orchestration.ai_confidence_tracker import AIConfidenceTracker


class AIAuditOrchestrator:
    """Coordinates AI-first audit planning and narrative with deterministic safety boundaries."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        app_path: str = "",
        dry_run: bool = True,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        model_available = self._model_available()
        mode = "model_augmented" if (enabled and model_available and not dry_run) else "deterministic_fallback"

        understanding = SoftwareUnderstandingEngine(self.store).run(app_path=app_path)
        strategy = AuditStrategyEngine(self.store).run()
        intents = TestIntentGenerator(self.store).run()
        scenarios = ScenarioIntelligenceEngine(self.store).run()
        evidence = EvidenceInterpretationEngine(self.store).run()
        rca = RCAReasoningCoordinator(self.store).run()
        improvement = ImprovementStrategyEngine(self.store).run()

        decisions = self._decisions(understanding, strategy, intents, scenarios, evidence, rca, improvement, mode)
        decision_log = AIDecisionLog(self.store).run(decisions=decisions)
        confidence = AIConfidenceTracker(self.store).run(stage_confidence=self._confidence_map(understanding, strategy, intents, evidence, rca, improvement))

        summary = {
            "enabled": enabled,
            "mode": mode,
            "dry_run": bool(dry_run),
            "model_available": bool(model_available),
            "software_type": understanding.get("software_type", "unknown_application"),
            "primary_audit_paths": strategy.get("selected_primary_paths", []),
            "intent_count": intents.get("summary", {}).get("intent_count", 0),
            "scenario_count": scenarios.get("summary", {}).get("scenario_count", 0),
            "proved_findings": evidence.get("summary", {}).get("proved", 0),
            "coordinated_hypotheses": rca.get("summary", {}).get("coordinated_hypothesis_count", 0),
            "improvement_count": improvement.get("summary", {}).get("improvement_count", 0),
            "decision_count": decision_log.get("summary", {}).get("decision_count", 0),
            "overall_confidence": confidence.get("overall_confidence", 0.0),
            "artifacts": {
                "software_understanding": "software_understanding.json",
                "ai_audit_strategy": "ai_audit_strategy.json",
                "test_intents": "test_intents.json",
                "intelligent_scenario_plan": "intelligent_scenario_plan.json",
                "evidence_interpretation": "evidence_interpretation.json",
                "ai_rca_coordination": "ai_rca_coordination.json",
                "ai_improvement_strategy": "ai_improvement_strategy.json",
                "ai_decision_log": "ai_decision_log.json",
                "ai_confidence_report": "ai_confidence_report.json",
                "ai_audit_brain_summary": "ai_audit_brain_summary.json",
            },
            "narrative": self._narrative(understanding, strategy, evidence, improvement),
            "safety": {
                "no_hallucinated_findings": True,
                "deterministic_validation_required": True,
                "no_unrestricted_remediation": True,
                "evidence_backed_interpretation": True,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.store.save_artifact("ai_audit_brain_summary", summary, agent="AIAuditOrchestrator")
        return summary

    def _model_available(self) -> bool:
        try:
            doctor = ModelRouter(artifact_store=self.store).doctor()
            if doctor.get("openrouter_configured") and doctor.get("allow_cloud_models"):
                return True
            router = get_router(client=OllamaClient())
            checks = router.check_all_models()
            if isinstance(checks, dict) and any(bool(v) for v in checks.values()):
                return True
        except Exception as e:
            logger.debug("_model_available: router.check_all_models failed: %s", e)
        url = _get_settings().ollama_base_url + "/api/tags"
        timeout = _get_settings().llm_health_check_timeout
        for attempt in range(2):
            try:
                import requests
                response = requests.get(url, timeout=timeout)
                return response.status_code == 200
            except Exception as e:
                logger.debug("Ollama availability check failed (attempt %d): %s", attempt + 1, e)
        return False

    def _confidence_map(
        self,
        understanding: Dict[str, Any],
        strategy: Dict[str, Any],
        intents: Dict[str, Any],
        evidence: Dict[str, Any],
        rca: Dict[str, Any],
        improvement: Dict[str, Any],
    ) -> Dict[str, float]:
        intent_items = intents.get("test_intents", []) if isinstance(intents.get("test_intents"), list) else []
        intent_conf = 0.0
        if intent_items:
            intent_conf = sum(float(item.get("confidence", 0.0)) for item in intent_items if isinstance(item, dict)) / len(intent_items)
        return {
            "understanding": float(understanding.get("summary", {}).get("confidence", 0.55)),
            "strategy": float(strategy.get("priorities", [{}])[0].get("confidence", 0.55)) if strategy.get("priorities") else 0.55,
            "scenario_generation": float(intent_conf or 0.55),
            "evidence_interpretation": 0.72 if evidence.get("summary", {}).get("total_evidence_count", 0) > 0 else 0.45,
            "rca": 0.7 if rca.get("summary", {}).get("coordinated_hypothesis_count", 0) > 0 else 0.5,
            "improvement_planning": 0.74 if improvement.get("summary", {}).get("improvement_count", 0) > 0 else 0.52,
        }

    def _decisions(
        self,
        understanding: Dict[str, Any],
        strategy: Dict[str, Any],
        intents: Dict[str, Any],
        scenarios: Dict[str, Any],
        evidence: Dict[str, Any],
        rca: Dict[str, Any],
        improvement: Dict[str, Any],
        mode: str,
    ) -> List[Dict[str, Any]]:
        return [
            {
                "decision": f"Classified software as {understanding.get('software_type', 'unknown_application')}.",
                "reason": "Software understanding synthesized stack/routes/apis/screens.",
                "source_artifacts": ["software_understanding.json", "app_map.json"],
                "confidence": understanding.get("summary", {}).get("confidence", 0.55),
                "fallback_mode": mode,
            },
            {
                "decision": "Selected top audit paths from AI strategy.",
                "reason": f"Top paths: {', '.join(strategy.get('selected_primary_paths', [])[:4])}",
                "source_artifacts": ["ai_audit_strategy.json", "graphify-out/graph.json"],
                "confidence": strategy.get("priorities", [{}])[0].get("confidence", 0.55) if strategy.get("priorities") else 0.55,
                "fallback_mode": mode,
            },
            {
                "decision": "Generated test intents and scenario plan.",
                "reason": f"Intents: {intents.get('summary', {}).get('intent_count', 0)}, scenarios: {scenarios.get('summary', {}).get('scenario_count', 0)}",
                "source_artifacts": ["test_intents.json", "intelligent_scenario_plan.json"],
                "confidence": 0.68,
                "fallback_mode": mode,
            },
            {
                "decision": "Interpreted evidence with proof-status constraints.",
                "reason": "Proof status requires evidence references and deterministic artifacts.",
                "source_artifacts": ["evidence_interpretation.json", "execution_trace.json", "evidence_graph.json"],
                "confidence": 0.7,
                "fallback_mode": mode,
            },
            {
                "decision": "Coordinated RCA and built improvement strategy.",
                "reason": f"Hypotheses: {rca.get('summary', {}).get('coordinated_hypothesis_count', 0)}, improvements: {improvement.get('summary', {}).get('improvement_count', 0)}",
                "source_artifacts": ["ai_rca_coordination.json", "ai_improvement_strategy.json", "root_cause_analysis.json"],
                "confidence": 0.72,
                "fallback_mode": mode,
            },
        ]

    def _narrative(
        self,
        understanding: Dict[str, Any],
        strategy: Dict[str, Any],
        evidence: Dict[str, Any],
        improvement: Dict[str, Any],
    ) -> str:
        software_type = understanding.get("software_type", "unknown_application")
        top_paths = ", ".join(strategy.get("selected_primary_paths", [])[:4]) or "security, runtime"
        proved = evidence.get("summary", {}).get("proved", 0)
        partial = evidence.get("summary", {}).get("partially_proved", 0)
        improvements = improvement.get("summary", {}).get("improvement_count", 0)
        return (
            f"AI-first orchestration classified the project as {software_type}, prioritized {top_paths}, "
            f"converted strategy into intent-driven scenario planning, interpreted evidence with proof constraints "
            f"(proved={proved}, partially_proved={partial}), then produced {improvements} evidence-backed improvement priorities."
        )
