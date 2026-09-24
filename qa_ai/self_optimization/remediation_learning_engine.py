"""
remediation_learning_engine.py - Learn from remediation outcomes and rollback utility.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class RemediationLearningEngine:
    """Derive remediation learning signals from runtime remediation artifacts."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        validation = self._load("remediation_validation_report")
        rollback = self._load("remediation_rollback_plan")
        patches = self._load("patch_proposals")
        regression = self._load("regression_guard_report")

        valid = validation.get("valid_proposals", []) if isinstance(validation.get("valid_proposals"), list) else []
        rejected = validation.get("rejected_proposals", []) if isinstance(validation.get("rejected_proposals"), list) else []
        plans = rollback.get("plans", []) if isinstance(rollback.get("plans"), list) else []
        proposals = patches.get("proposals", []) if isinstance(patches.get("proposals"), list) else []

        sensitive_modules: Dict[str, int] = {}
        for proposal in proposals:
            if not isinstance(proposal, dict):
                continue
            files = proposal.get("affected_files", []) if isinstance(proposal.get("affected_files"), list) else []
            for file_path in files:
                key = str(file_path)
                if key:
                    sensitive_modules[key] = sensitive_modules.get(key, 0) + 1

        regression_causing = 0
        if bool(regression.get("regression_detected", False)):
            regression_causing = len(rejected)

        report = {
            "advisory_only": True,
            "fix_types_reducing_risk": len(valid),
            "regression_causing_fixes": regression_causing,
            "remediation_sensitive_modules": [
                {"module": module, "touch_count": count}
                for module, count in sorted(sensitive_modules.items(), key=lambda item: item[1], reverse=True)
            ],
            "rollback_plan_utility": {
                "rollback_plan_count": len(plans),
                "rollback_plan_present": len(plans) > 0,
            },
            "summary": {
                "valid_count": len(valid),
                "rejected_count": len(rejected),
                "regression_causing_fixes": regression_causing,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "source_artifacts": [
                "remediation_validation_report.json",
                "remediation_rollback_plan.json",
                "patch_proposals.json",
                "regression_guard_report.json",
            ],
        }
        self.store.save_artifact("remediation_learning_report", report, agent="SelfOptimization.RemediationLearningEngine")
        return report

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
