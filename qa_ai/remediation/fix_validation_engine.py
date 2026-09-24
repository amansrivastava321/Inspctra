"""
fix_validation_engine.py - Deterministic validation for remediation proposals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class FixValidationEngine:
    """Validate proposal safety and deterministic evidence linkage."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        proposals: Dict[str, Any] | None = None,
        risk_report: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        proposals_payload = proposals if isinstance(proposals, dict) else self._load("patch_proposals")
        risk_payload = risk_report if isinstance(risk_report, dict) else self._load("remediation_risk_report")
        risk_by_proposal = self._risk_by_proposal(risk_payload)

        valid_proposals: List[Dict[str, Any]] = []
        rejected_proposals: List[Dict[str, Any]] = []
        all_proposals = proposals_payload.get("proposals", []) if isinstance(proposals_payload.get("proposals"), list) else []
        for proposal in all_proposals:
            if not isinstance(proposal, dict):
                continue
            proposal_id = str(proposal.get("proposal_id", "")).strip()
            reasons = self._rejection_reasons(proposal, risk_by_proposal.get(proposal_id, {}))
            if reasons:
                rejected_proposals.append(
                    {
                        "proposal_id": proposal_id,
                        "fix_id": str(proposal.get("fix_id", "")),
                        "rejected": True,
                        "reasons": reasons,
                    }
                )
                continue
            valid_proposals.append(proposal)

        report = {
            "valid_proposals": valid_proposals,
            "rejected_proposals": rejected_proposals,
            "summary": {
                "validated_count": len(valid_proposals),
                "rejected_count": len(rejected_proposals),
                "unsafe_rejected_count": sum(
                    1
                    for row in rejected_proposals
                    if any("unsafe" in str(reason) or "destructive" in str(reason) for reason in row.get("reasons", []))
                ),
                "deterministic_validation": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("remediation_validation_report", report, agent="FixValidationEngine")
        return report

    def _rejection_reasons(self, proposal: Dict[str, Any], risk: Dict[str, Any]) -> List[str]:
        reasons: List[str] = []
        if not bool(proposal.get("advisory_only", False)):
            reasons.append("advisory_only_required")
        if not bool(proposal.get("approval_required", False)):
            reasons.append("approval_required_must_be_true")
        if bool(proposal.get("apply_by_default", True)):
            reasons.append("apply_by_default_disallowed")
        if not self._string_list(proposal.get("target_files")):
            reasons.append("missing_target_files")
        if not self._evidence_links_present(proposal):
            reasons.append("missing_evidence_links")
        if not bool(proposal.get("is_safe", True)):
            reasons.append("unsafe_proposal_flagged")
        if self._contains_destructive_preview(proposal):
            reasons.append("destructive_patch_preview_detected")
        risk_level = str(risk.get("risk_level", "")).lower()
        if risk_level == "critical" and not self._evidence_links_present(proposal):
            reasons.append("critical_risk_requires_strong_evidence")
        return reasons

    def _contains_destructive_preview(self, proposal: Dict[str, Any]) -> bool:
        preview = str(proposal.get("patch_preview", "")).lower()
        return any(token in preview for token in ["rm -rf", "drop table", "truncate", "shutdown", "delete from"])

    def _evidence_links_present(self, proposal: Dict[str, Any]) -> bool:
        links = proposal.get("evidence_links", [])
        return isinstance(links, list) and len(links) > 0

    def _risk_by_proposal(self, risk_payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        rows = risk_payload.get("proposal_risks", []) if isinstance(risk_payload.get("proposal_risks"), list) else []
        out: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            proposal_id = str(row.get("proposal_id", "")).strip()
            if proposal_id:
                out[proposal_id] = row
        return out

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _string_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]
