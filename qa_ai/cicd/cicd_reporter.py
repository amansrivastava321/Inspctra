"""
cicd_reporter.py - Aggregate CI/CD artifacts into a single report.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from qa_ai.runtime.artifact_store import ArtifactStore


class CICDReporter:
    """Builds a consolidated CI/CD audit report from generated artifacts."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        provider = self._load("cicd_provider_report")
        plan = self._load("ci_workflow_plan")
        incremental = self._load("incremental_audit_plan")
        baseline = self._load("baseline_comparison")
        gate = self._load("release_gate_decision")
        pr_report = self._load("cicd_audit_report")

        result = {
            "provider": provider.get("provider", "unknown_manual"),
            "release_gate_decision": gate.get("decision", "warning"),
            "incremental_scope": {
                "changed_files": incremental.get("changed_files", []),
                "changed_modules": incremental.get("changed_modules", []),
                "recommended_phases": incremental.get("recommended_phases", []),
            },
            "workflow_plan_status": plan.get("summary", {}),
            "baseline_summary": baseline.get("summary", {}),
            "audit_signal": {
                "critical_security_findings": pr_report.get("critical_security_findings", 0),
                "coverage_percent": pr_report.get("coverage_percent", 0.0),
                "evidence_count": pr_report.get("evidence_count", 0),
            },
            "artifacts": {
                "cicd_provider_report": "cicd_provider_report.json",
                "ci_workflow_plan": "ci_workflow_plan.json",
                "incremental_audit_plan": "incremental_audit_plan.json",
                "baseline_comparison": "baseline_comparison.json",
                "release_gate_decision": "release_gate_decision.json",
                "cicd_audit_report": "cicd_audit_report.json",
            },
            "summary": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "advisory_only_default": True,
                "permission_gated": True,
            },
        }
        self.store.save_artifact("cicd_audit_report", result, agent="CICDReporter")
        return result

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
