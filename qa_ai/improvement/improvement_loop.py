"""
improvement_loop.py - Orchestrates continuous software improvement modules.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from qa_ai.artifacts.artifact_validator import ArtifactValidator
from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.improvement.software_health_model import SoftwareHealthModel
from qa_ai.improvement.fix_planner import FixPlanner
from qa_ai.improvement.change_impact_analyzer import ChangeImpactAnalyzer
from qa_ai.improvement.improvement_reporter import ImprovementReporter
from qa_ai.improvement.remediation_engine import RemediationEngine
from qa_ai.improvement.retest_orchestrator import RetestOrchestrator
from qa_ai.improvement.regression_guard import RegressionGuard
from qa_ai.improvement.quality_score_tracker import QualityScoreTracker
from qa_ai.improvement.learning_registry import LearningRegistry


class ImprovementLoop:
    """Runs health, planning, impact, remediation, retest, regression, trend, and learning."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store
        self.validator = ArtifactValidator()

    def run(
        self,
        findings: Optional[Dict[str, Any]] = None,
        root_causes: Optional[Dict[str, Any]] = None,
        risk_report: Optional[Dict[str, Any]] = None,
        evidence: Optional[Dict[str, Any]] = None,
        test_plan: Optional[Dict[str, Any]] = None,
        app_map: Optional[Dict[str, Any]] = None,
        before_audit: Optional[Dict[str, Any]] = None,
        after_audit: Optional[Dict[str, Any]] = None,
        remediation_approved: bool = False,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        safe_findings = self._validate_inbound("correlated_findings", findings)
        safe_root_causes = self._validate_inbound("root_cause_analysis", root_causes)
        safe_risk_report = self._validate_inbound("overall_risk_report", risk_report)
        safe_test_plan = self._validate_inbound("test_plan", test_plan)
        safe_app_map = self._validate_inbound("app_map", app_map)
        safe_before = before_audit if isinstance(before_audit, dict) else None
        safe_after = after_audit if isinstance(after_audit, dict) else None

        if safe_findings is not None:
            self.store.save_artifact("correlated_findings", findings, agent="ImprovementLoop")
        if safe_root_causes is not None:
            self.store.save_artifact("root_cause_analysis", root_causes, agent="ImprovementLoop")
        if safe_risk_report is not None:
            self.store.save_artifact("overall_risk_report", risk_report, agent="ImprovementLoop")
        if safe_test_plan is not None:
            self.store.save_artifact("test_plan", test_plan, agent="ImprovementLoop")
        if safe_app_map is not None:
            self.store.save_artifact("app_map", app_map, agent="ImprovementLoop")

        health = SoftwareHealthModel(self.store).run(risk_report=safe_risk_report, evidence=evidence)
        fix_plan = FixPlanner(self.store).run(
            findings=safe_findings,
            root_causes=safe_root_causes,
            risk_report=safe_risk_report,
            test_plan=safe_test_plan,
        )
        impact = ChangeImpactAnalyzer(self.store).run(fix_plan=fix_plan, app_map=safe_app_map)
        backlog = ImprovementReporter(self.store).run(
            health_score=health,
            fix_plan=fix_plan,
            impact_analysis=impact,
        )
        remediation = RemediationEngine(self.store).run(
            fix_plan=fix_plan,
            approved=remediation_approved,
            dry_run=dry_run,
        )
        retest = RetestOrchestrator(self.store).run(fix_plan=fix_plan, test_plan=safe_test_plan)
        regression = RegressionGuard(self.store).run(before=safe_before, after=safe_after)
        trend = QualityScoreTracker(self.store).run(current_score=health)
        learning = LearningRegistry(self.store).run(
            audit_result={
                "root_causes": (safe_root_causes or {}).get("root_causes", []),
                "fixes": fix_plan.get("fixes", []),
            }
        )

        return {
            "health_score": health,
            "improvement_backlog": backlog,
            "fix_plan": fix_plan,
            "change_impact_analysis": impact,
            "remediation_plan": remediation,
            "retest_results": retest,
            "regression_guard": regression,
            "quality_trend": trend,
            "learning_registry": learning,
        }

    def _validate_inbound(self, artifact_name: str, payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None
        validated = self.validator.validate_for_consumption(artifact_name, payload)
        return validated.data if isinstance(validated.data, dict) else None
