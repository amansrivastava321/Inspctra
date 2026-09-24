"""
self_optimization_orchestrator.py - Orchestrates self-optimization intelligence pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.self_optimization.audit_memory_store import AuditMemoryStore
from qa_ai.self_optimization.strategy_adaptation_engine import StrategyAdaptationEngine
from qa_ai.self_optimization.finding_deduplication_engine import FindingDeduplicationEngine
from qa_ai.self_optimization.confidence_calibration_engine import ConfidenceCalibrationEngine
from qa_ai.self_optimization.evidence_quality_optimizer import EvidenceQualityOptimizer
from qa_ai.self_optimization.scenario_optimization_engine import ScenarioOptimizationEngine
from qa_ai.self_optimization.risk_prediction_engine import RiskPredictionEngine
from qa_ai.self_optimization.remediation_learning_engine import RemediationLearningEngine
from qa_ai.self_optimization.cross_project_learning_engine import CrossProjectLearningEngine


class SelfOptimizationOrchestrator:
    """Run full self-optimization sequence with advisory-only outputs."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, workspace: str = "default", cross_project: bool = False) -> Dict[str, Any]:
        memory = AuditMemoryStore(self.store).run(workspace=workspace)
        strategy = StrategyAdaptationEngine(self.store).run()
        dedup = FindingDeduplicationEngine(self.store).run()
        calibration = ConfidenceCalibrationEngine(self.store).run()
        evidence = EvidenceQualityOptimizer(self.store).run()
        scenario = ScenarioOptimizationEngine(self.store).run()
        remediation = RemediationLearningEngine(self.store).run()
        risk = RiskPredictionEngine(self.store).run()
        cross = CrossProjectLearningEngine(self.store).run(workspace=workspace, enabled=cross_project)

        summary = {
            "workspace": workspace,
            "cross_project": bool(cross_project),
            "advisory_only": True,
            "artifact_backed_learning_only": True,
            "automatic_source_modification": False,
            "external_upload": False,
            "artifacts": {
                "audit_memory_index": "audit_memory_index.json",
                "strategy_adaptation_plan": "strategy_adaptation_plan.json",
                "finding_deduplication_report": "finding_deduplication_report.json",
                "confidence_calibration_report": "confidence_calibration_report.json",
                "evidence_quality_optimization": "evidence_quality_optimization.json",
                "scenario_optimization_report": "scenario_optimization_report.json",
                "risk_prediction_report": "risk_prediction_report.json",
                "remediation_learning_report": "remediation_learning_report.json",
                "cross_project_learning_report": "cross_project_learning_report.json",
                "self_optimization_summary": "self_optimization_summary.json",
            },
            "counts": {
                "memory_runs": len(memory.get("runs", [])) if isinstance(memory.get("runs"), list) else 0,
                "strategy_recommendations": len(strategy.get("recommendations", [])) if isinstance(strategy.get("recommendations"), list) else 0,
                "dedup_clusters": len(dedup.get("clusters", [])) if isinstance(dedup.get("clusters"), list) else 0,
                "evidence_recommendations": len(evidence.get("recommendations", [])) if isinstance(evidence.get("recommendations"), list) else 0,
                "risk_predictions": len(risk.get("predictions", [])) if isinstance(risk.get("predictions"), list) else 0,
            },
            "integrations": {
                "ai_orchestration": self._exists("ai_audit_strategy") or self._exists("ai_confidence_report"),
                "benchmark_intelligence": self._exists("benchmark_scoring_report") or self._exists("benchmark_runtime_summary"),
                "enterprise_governance": self._exists("enterprise_runtime_summary") or self._exists("governance_summary"),
                "remediation_runtime": self._exists("remediation_runtime_summary"),
                "cicd_runtime": self._exists("cicd_runtime_summary"),
                "artifact_store": True,
                "artifact_validator": True,
            },
            "summary": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("self_optimization_summary", summary, agent="SelfOptimization.SelfOptimizationOrchestrator")
        return summary

    def _exists(self, artifact_name: str) -> bool:
        return self.store.artifact_exists(artifact_name)
