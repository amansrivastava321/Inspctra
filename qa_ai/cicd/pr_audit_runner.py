"""
pr_audit_runner.py - Build CI-mode audit summary from incremental scope.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.cicd.incremental_audit_planner import IncrementalAuditPlanner


class PRAuditRunner:
    """Runs a lightweight PR-oriented audit plan and persists CI audit report."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, changed_files: List[str] | None = None) -> Dict[str, Any]:
        plan = IncrementalAuditPlanner(self.store).run(changed_files=changed_files or [])
        findings = self._load("correlated_findings")
        execution = self._load("execution_results")
        evidence = self._load("evidence_graph")

        result = {
            "mode": "ci_incremental",
            "changed_files": plan.get("changed_files", []),
            "changed_modules": plan.get("changed_modules", []),
            "recommended_phases": plan.get("recommended_phases", []),
            "critical_findings": self._count_by_severity(findings, "critical"),
            "high_findings": self._count_by_severity(findings, "high"),
            "critical_security_findings": self._count_security_critical(findings),
            "coverage_percent": self._coverage(execution),
            "evidence_count": self._evidence_count(evidence),
            "summary": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "incremental": True,
            },
        }
        self.store.save_artifact("cicd_audit_report", result, agent="PRAuditRunner")
        return result

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _count_by_severity(self, findings_payload: Dict[str, Any], severity: str) -> int:
        findings = findings_payload.get("findings", [])
        if not isinstance(findings, list):
            return 0
        target = severity.lower()
        return sum(
            1
            for finding in findings
            if isinstance(finding, dict) and str(finding.get("severity", "")).lower() == target
        )

    def _count_security_critical(self, findings_payload: Dict[str, Any]) -> int:
        findings = findings_payload.get("findings", [])
        if not isinstance(findings, list):
            return 0
        count = 0
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            severity = str(finding.get("severity", "")).lower()
            category = str(finding.get("category", "")).lower()
            if severity == "critical" and ("security" in category or not category):
                count += 1
        return count

    def _coverage(self, execution_payload: Dict[str, Any]) -> float:
        if not isinstance(execution_payload, dict):
            return 0.0
        raw = execution_payload.get("coverage_percent", execution_payload.get("coverage", 0.0))
        try:
            return float(raw or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _evidence_count(self, evidence_payload: Dict[str, Any]) -> int:
        if not isinstance(evidence_payload, dict):
            return 0
        raw_nodes = evidence_payload.get("graph", {}).get("nodes", [])
        if isinstance(raw_nodes, list) and len(raw_nodes) > 0:
            return len(raw_nodes)
        raw = evidence_payload.get("summary", {}).get("total_evidence", evidence_payload.get("evidence_count", 0))
        try:
            return int(raw or 0)
        except (TypeError, ValueError):
            return 0
