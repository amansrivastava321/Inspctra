"""
qa_ai.self_optimization - Artifact-backed self-optimizing audit intelligence.
"""

from qa_ai.self_optimization.audit_memory_store import AuditMemoryStore
from qa_ai.self_optimization.strategy_adaptation_engine import StrategyAdaptationEngine
from qa_ai.self_optimization.finding_deduplication_engine import FindingDeduplicationEngine
from qa_ai.self_optimization.confidence_calibration_engine import ConfidenceCalibrationEngine
from qa_ai.self_optimization.evidence_quality_optimizer import EvidenceQualityOptimizer
from qa_ai.self_optimization.scenario_optimization_engine import ScenarioOptimizationEngine
from qa_ai.self_optimization.risk_prediction_engine import RiskPredictionEngine
from qa_ai.self_optimization.remediation_learning_engine import RemediationLearningEngine
from qa_ai.self_optimization.cross_project_learning_engine import CrossProjectLearningEngine
from qa_ai.self_optimization.self_optimization_orchestrator import SelfOptimizationOrchestrator

__all__ = [
    "AuditMemoryStore",
    "StrategyAdaptationEngine",
    "FindingDeduplicationEngine",
    "ConfidenceCalibrationEngine",
    "EvidenceQualityOptimizer",
    "ScenarioOptimizationEngine",
    "RiskPredictionEngine",
    "RemediationLearningEngine",
    "CrossProjectLearningEngine",
    "SelfOptimizationOrchestrator",
]
