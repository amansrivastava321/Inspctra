"""
change_risk_analyzer.py - Computes risk score for remediation proposals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class ChangeRiskAnalyzer:
    """Score remediation proposals by blast radius, severity, and safety flags."""

    SEVERITY_WEIGHT = {
        "critical": 40,
        "high": 28,
        "medium": 16,
        "low": 8,
        "info": 4,
    }

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        proposals: Dict[str, Any] | None = None,
        simulation_report: Dict[str, Any] | None = None,
        retest_scope: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        proposals_payload = proposals if isinstance(proposals, dict) else self._load("patch_proposals")
        simulation = simulation_report if isinstance(simulation_report, dict) else self._load("change_simulation_report")
        retest = retest_scope if isinstance(retest_scope, dict) else self._load("remediation_retest_scope")

        impacts = simulation.get("impacts", []) if isinstance(simulation.get("impacts"), list) else []
        impact_by_proposal = {
            str(item.get("proposal_id", "")).strip(): item
            for item in impacts
            if isinstance(item, dict) and str(item.get("proposal_id", "")).strip()
        }
        retest_count = len(retest.get("tests", [])) if isinstance(retest.get("tests"), list) else 0

        entries: List[Dict[str, Any]] = []
        proposals_list = proposals_payload.get("proposals", []) if isinstance(proposals_payload.get("proposals"), list) else []
        for proposal in proposals_list:
            if not isinstance(proposal, dict):
                continue
            proposal_id = str(proposal.get("proposal_id", "")).strip()
            impact = impact_by_proposal.get(proposal_id, {})
            target_files = self._string_list(proposal.get("target_files"))
            impacted_files = self._string_list(impact.get("impacted_files"))
            risk_level = str(proposal.get("risk_level", "medium")).lower()
            unsafe_penalty = 20 if not bool(proposal.get("is_safe", True)) else 0

            score = (
                self.SEVERITY_WEIGHT.get(risk_level, 16)
                + min(len(target_files), 15) * 2
                + min(len(impacted_files), 25)
                + (8 if retest_count == 0 else 0)
                + unsafe_penalty
            )
            bounded_score = float(max(0, min(score, 100)))

            entries.append(
                {
                    "proposal_id": proposal_id,
                    "fix_id": str(proposal.get("fix_id", "")),
                    "risk_score": bounded_score,
                    "risk_level": self._risk_level(bounded_score),
                    "factors": {
                        "declared_risk_level": risk_level,
                        "target_file_count": len(target_files),
                        "impacted_file_count": len(impacted_files),
                        "retest_scope_count": retest_count,
                        "unsafe_penalty": unsafe_penalty,
                    },
                    "approval_required": True,
                }
            )

        result = {
            "proposal_risks": entries,
            "summary": {
                "proposal_count": len(entries),
                "high_or_critical": sum(1 for row in entries if row.get("risk_level") in {"high", "critical"}),
                "average_risk_score": round(
                    sum(float(row.get("risk_score", 0.0)) for row in entries) / len(entries), 2
                )
                if entries
                else 0.0,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("remediation_risk_report", result, agent="ChangeRiskAnalyzer")
        return result

    def _risk_level(self, score: float) -> str:
        if score >= 75:
            return "critical"
        if score >= 55:
            return "high"
        if score >= 30:
            return "medium"
        return "low"

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _string_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]
