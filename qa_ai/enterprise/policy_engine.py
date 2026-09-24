"""
policy_engine.py - Governance policy evaluation for workspaces/projects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class PolicyEngine:
    """Evaluate governance policies using local artifacts and advisory controls."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        rules = [
            self._remediation_approval_policy(),
            self._release_gate_policy(),
            self._audit_retention_policy(),
            self._benchmark_policy(),
        ]

        blocked = [row for row in rules if row.get("status") == "blocked"]
        warning = [row for row in rules if row.get("status") == "warning"]
        passing = [row for row in rules if row.get("status") == "pass"]

        report = {
            "policy_mode": "local_governance_only",
            "advisory_only": True,
            "external_enforcement": False,
            "rules": rules,
            "summary": {
                "rule_count": len(rules),
                "blocked_rules": [str(row.get("rule")) for row in blocked],
                "warning_rules": [str(row.get("rule")) for row in warning],
                "pass_count": len(passing),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("governance_policy_report", report, agent="Enterprise.PolicyEngine")
        return report

    def _remediation_approval_policy(self) -> Dict[str, Any]:
        approval = self._load("remediation_approval_workflow")
        entries = approval.get("entries", []) if isinstance(approval.get("entries"), list) else []
        pending = sum(1 for row in entries if isinstance(row, dict) and row.get("state") == "pending_approval")
        status = "warning" if pending > 0 else "pass"
        return {
            "rule": "remediation_approval_policy",
            "status": status,
            "details": {
                "pending_approval": pending,
                "approval_required": True,
                "auto_approve": False,
            },
        }

    def _release_gate_policy(self) -> Dict[str, Any]:
        gate = self._load("release_gate_decision")
        decision = str(gate.get("decision", "warning"))
        status = "blocked" if decision == "blocked" else ("warning" if decision == "warning" else "pass")
        return {
            "rule": "release_gate_policy",
            "status": status,
            "details": {
                "decision": decision,
                "requires_review": decision in {"blocked", "warning"},
            },
        }

    def _audit_retention_policy(self) -> Dict[str, Any]:
        lifecycle = self._load("artifact_lifecycle_plan")
        summary = lifecycle.get("summary", {}) if isinstance(lifecycle.get("summary"), dict) else {}
        delete_planned = int(summary.get("delete_operations_planned", 0) or 0)
        delete_default = bool(summary.get("delete_by_default", False))
        status = "blocked" if delete_default or delete_planned > 0 else "pass"
        return {
            "rule": "audit_retention_policy",
            "status": status,
            "details": {
                "delete_by_default": delete_default,
                "delete_operations_planned": delete_planned,
                "explicit_approval_required": True,
            },
        }

    def _benchmark_policy(self) -> Dict[str, Any]:
        maturity = self._load("benchmark_maturity_score")
        overall = float((maturity.get("scores") or {}).get("overall", 0.0) or 0.0)
        status = "warning" if overall < 0.5 else "pass"
        return {
            "rule": "benchmark_policy",
            "status": status,
            "details": {
                "overall_maturity": round(overall, 4),
                "sandbox_execution_required": True,
                "external_uploads_allowed": False,
            },
        }

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
