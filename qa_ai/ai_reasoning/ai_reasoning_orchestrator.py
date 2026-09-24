"""
ai_reasoning_orchestrator.py - Orchestrate AI reasoning modules with safe fallback.
"""

from __future__ import annotations

from typing import Any, Dict
import logging
import requests

logger = logging.getLogger(__name__)

from qa_ai.ai.model_router import ModelRouter
from qa_ai.config.settings import get_settings as _get_settings
from qa_ai.ai_reasoning.adaptive_audit_planner import AdaptiveAuditPlanner
from qa_ai.ai_reasoning.evidence_synthesizer import EvidenceSynthesizer
from qa_ai.ai_reasoning.fix_reasoner import FixReasoner
from qa_ai.ai_reasoning.learning_optimizer import LearningOptimizer
from qa_ai.ai_reasoning.reasoning_context_builder import ReasoningContextBuilder
from qa_ai.ai_reasoning.risk_reasoner import RiskReasoner
from qa_ai.ai_reasoning.scenario_generator import ScenarioGenerator
from qa_ai.ai_reasoning.semantic_rca_engine import SemanticRCAEngine
from qa_ai.runtime.artifact_store import ArtifactStore


class AIReasoningOrchestrator:
    """Run advisory AI reasoning while preserving deterministic-first behavior."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        enabled: bool = True,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        model_available = self._detect_model_availability()
        use_model = bool(enabled and model_available and not dry_run)

        if not enabled:
            summary = {
                "enabled": False,
                "dry_run": dry_run,
                "model_available": model_available,
                "mode": "disabled",
                "artifacts": {},
                "notes": ["AI reasoning disabled by configuration."],
            }
            self.store.save_artifact("ai_reasoning_summary", summary, agent="AIReasoningOrchestrator")
            return summary

        context = ReasoningContextBuilder(self.store).run()
        semantic_rca = SemanticRCAEngine(self.store).run(use_model=use_model)
        adaptive_plan = AdaptiveAuditPlanner(self.store).run()
        evidence_synthesis = EvidenceSynthesizer(self.store).run()
        semantic_risk = RiskReasoner(self.store).run()
        scenarios = ScenarioGenerator(self.store).run()
        fix_reasoning = FixReasoner(self.store).run()
        learning_optimization = LearningOptimizer(self.store).run()

        summary = {
            "enabled": True,
            "dry_run": dry_run,
            "model_available": model_available,
            "mode": "model_augmented" if use_model else "deterministic_fallback",
            "artifacts": {
                "reasoning_context": "reasoning_context.json",
                "semantic_root_cause_analysis": "semantic_root_cause_analysis.json",
                "adaptive_audit_plan": "adaptive_audit_plan.json",
                "evidence_synthesis": "evidence_synthesis.json",
                "semantic_risk_report": "semantic_risk_report.json",
                "ai_generated_scenarios": "ai_generated_scenarios.json",
                "ai_fix_reasoning": "ai_fix_reasoning.json",
                "learning_optimization_report": "learning_optimization_report.json",
            },
            "summary": {
                "context_items": context.get("summary", {}).get("pruned_item_count", 0),
                "hypotheses": semantic_rca.get("summary", {}).get("hypothesis_count", 0),
                "adaptive_actions": adaptive_plan.get("summary", {}).get("action_count", 0),
                "evidence_conclusions": evidence_synthesis.get("summary", {}).get("conclusion_count", 0),
                "risk_chains": len(semantic_risk.get("risk_chains", [])) if isinstance(semantic_risk.get("risk_chains"), list) else 0,
                "generated_scenarios": scenarios.get("summary", {}).get("scenario_count", 0),
                "fix_advisories": fix_reasoning.get("summary", {}).get("strategy_count", 0),
                "learning_recommendations": learning_optimization.get("summary", {}).get("recommendation_count", 0),
            },
            "safety": {
                "deterministic_first": True,
                "advisory_only_fixes": True,
                "no_evidence_invention_rule": True,
            },
        }
        self.store.save_artifact("ai_reasoning_summary", summary, agent="AIReasoningOrchestrator")
        return summary

    def _detect_model_availability(self) -> bool:
        try:
            doctor = ModelRouter(artifact_store=self.store).doctor()
            if doctor.get("openrouter_configured") and doctor.get("allow_cloud_models"):
                return True
        except Exception as e:
            logger.debug("ModelRouter doctor check failed: %s", e)

        url = _get_settings().ollama_base_url + "/api/tags"
        timeout = _get_settings().llm_health_check_timeout
        for attempt in range(2):
            try:
                response = requests.get(url, timeout=timeout)
                return response.status_code == 200
            except Exception as e:
                logger.debug("Ollama availability check failed (attempt %d): %s", attempt + 1, e)
        return False
