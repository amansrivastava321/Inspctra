"""
remediation_validation_engine.py - Deterministic validation for remediation runtime proposals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from qa_ai.runtime.artifact_store import ArtifactStore


class RemediationValidationEngine:
    """Validate proposals against evidence, runtime context, and safety constraints."""

    UNSAFE_TOKENS = ("rm -rf", "drop table", "truncate", "shutdown", "delete from")

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        proposals: Dict[str, Any] | None = None,
        simulation: Dict[str, Any] | None = None,
        retest_scope: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        proposal_payload = proposals if isinstance(proposals, dict) else self._load("patch_proposals")
        simulation_payload = simulation if isinstance(simulation, dict) else self._load("remediation_change_simulation")
        retest_payload = retest_scope if isinstance(retest_scope, dict) else self._load("remediation_retest_scope")

        findings = self._load("correlated_findings") or self._load("findings")
        semantic_rca = self._load("semantic_root_cause_analysis") or self._load("root_cause_analysis")
        regression_guard = self._load("regression_guard_report")
        ai_fix_reasoning = self._load("ai_fix_reasoning")

        known_fix_ids = self._known_fix_ids()
        known_finding_ids = self._known_finding_ids(findings)
        known_cause_ids = self._known_cause_ids(semantic_rca)
        impacted_by_proposal = self._impacted_by_proposal(simulation_payload)

        valid: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []

        for proposal in proposal_payload.get("proposals", []):
            if not isinstance(proposal, dict):
                continue
            proposal_id = str(proposal.get("proposal_id", "")).strip()
            fix_id = str(proposal.get("fix_id", "")).strip()
            reasons = self._reasons(
                proposal=proposal,
                fix_id=fix_id,
                known_fix_ids=known_fix_ids,
                known_finding_ids=known_finding_ids,
                known_cause_ids=known_cause_ids,
                impacted_files=impacted_by_proposal.get(proposal_id, []),
                retest_payload=retest_payload,
                regression_guard=regression_guard,
                ai_fix_reasoning=ai_fix_reasoning,
            )
            if reasons:
                rejected.append(
                    {
                        "proposal_id": proposal_id,
                        "fix_id": fix_id,
                        "rejected": True,
                        "reasons": reasons,
                    }
                )
            else:
                valid.append(proposal)

        result = {
            "valid_proposals": valid,
            "rejected_proposals": rejected,
            "summary": {
                "validated_count": len(valid),
                "rejected_count": len(rejected),
                "unsafe_rejected_count": sum(1 for row in rejected if any("unsafe" in reason for reason in row.get("reasons", []))),
                "hallucinated_rejected_count": sum(1 for row in rejected if any("hallucinated" in reason for reason in row.get("reasons", []))),
                "deterministic_evidence_source_of_truth": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("remediation_validation_report", result, agent="RemediationValidationEngine")
        return result

    def _reasons(
        self,
        proposal: Dict[str, Any],
        fix_id: str,
        known_fix_ids: Set[str],
        known_finding_ids: Set[str],
        known_cause_ids: Set[str],
        impacted_files: List[str],
        retest_payload: Dict[str, Any],
        regression_guard: Dict[str, Any],
        ai_fix_reasoning: Dict[str, Any],
    ) -> List[str]:
        reasons: List[str] = []
        advisory = bool(proposal.get("advisory_only", False))
        approval_required = bool(proposal.get("approval_required", False))
        apply_by_default = bool(proposal.get("apply_by_default", True))

        if not advisory:
            reasons.append("unsupported_fix_non_advisory")
        if not approval_required:
            reasons.append("unsupported_fix_missing_approval_gate")
        if apply_by_default:
            reasons.append("unsafe_apply_by_default")

        affected_files = self._string_list(proposal.get("affected_files") or proposal.get("target_files"))
        if not affected_files:
            reasons.append("low_evidence_missing_affected_files")

        evidence_links = proposal.get("source_evidence", [])
        if not isinstance(evidence_links, list) or not evidence_links:
            reasons.append("low_evidence_missing_source_evidence")
        elif not self._evidence_supported(evidence_links, known_finding_ids, known_cause_ids):
            reasons.append("hallucinated_evidence_reference")

        source_artifacts = self._string_list(proposal.get("source_artifacts"))
        if not source_artifacts:
            reasons.append("low_evidence_missing_source_artifacts")

        if fix_id and fix_id not in known_fix_ids:
            reasons.append("hallucinated_fix_reference")

        pseudo_patch = str(proposal.get("pseudo_patch", proposal.get("patch_preview", ""))).lower()
        if any(token in pseudo_patch for token in self.UNSAFE_TOKENS):
            reasons.append("unsafe_patch_content_detected")

        if impacted_files and len(impacted_files) > 25:
            reasons.append("unsafe_blast_radius_exceeds_limit")

        retest_requirements = self._string_list(proposal.get("retest_requirements"))
        if not retest_requirements and isinstance(retest_payload, dict) and not self._string_list(retest_payload.get("tests")):
            reasons.append("low_evidence_missing_retest_scope")

        if regression_guard.get("regression_detected") is True and not retest_requirements:
            reasons.append("unsafe_missing_retest_under_regression")

        if not self._ai_confidence_sufficient(ai_fix_reasoning, fix_id):
            reasons.append("low_ai_confidence_for_fix")

        return reasons

    def _ai_confidence_sufficient(self, ai_fix_reasoning: Dict[str, Any], fix_id: str) -> bool:
        if not fix_id:
            return False
        strategies = ai_fix_reasoning.get("strategies", []) if isinstance(ai_fix_reasoning.get("strategies"), list) else []
        for strategy in strategies:
            if not isinstance(strategy, dict):
                continue
            if str(strategy.get("fix_id", "")).strip() != fix_id:
                continue
            confidence = strategy.get("confidence", 0.5)
            try:
                return float(confidence) >= 0.25
            except (TypeError, ValueError):
                return False
        # Deterministic artifacts may not include every fix; treat as weak but acceptable.
        return True

    def _evidence_supported(self, links: List[Dict[str, Any]], finding_ids: Set[str], cause_ids: Set[str]) -> bool:
        for row in links:
            if not isinstance(row, dict):
                continue
            artifact = str(row.get("artifact", "")).strip()
            reference = str(row.get("reference", "")).strip()
            if artifact in {"correlated_findings", "findings"} and reference in finding_ids:
                return True
            if artifact in {"semantic_root_cause_analysis", "root_cause_analysis"} and reference in cause_ids:
                return True
            if artifact in {"fix_plan", "ai_fix_reasoning", "evidence_interpretation"}:
                return True
        return False

    def _impacted_by_proposal(self, simulation_payload: Dict[str, Any]) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        rows = simulation_payload.get("impacts", []) if isinstance(simulation_payload.get("impacts"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            proposal_id = str(row.get("proposal_id", "")).strip()
            if proposal_id:
                out[proposal_id] = self._string_list(row.get("impacted_files"))
        return out

    def _known_fix_ids(self) -> Set[str]:
        fix_plan = self._load("fix_plan")
        fixes = fix_plan.get("fixes", []) if isinstance(fix_plan.get("fixes"), list) else []
        out: Set[str] = set()
        for row in fixes:
            if not isinstance(row, dict):
                continue
            fix_id = str(row.get("fix_id", "")).strip()
            if fix_id:
                out.add(fix_id)
        return out

    def _known_finding_ids(self, findings: Dict[str, Any]) -> Set[str]:
        out: Set[str] = set()
        rows = findings.get("findings", []) if isinstance(findings.get("findings"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            finding_id = str(row.get("id", "")).strip()
            if finding_id:
                out.add(finding_id)
        return out

    def _known_cause_ids(self, semantic_rca: Dict[str, Any]) -> Set[str]:
        out: Set[str] = set()
        rows = semantic_rca.get("root_causes", []) if isinstance(semantic_rca.get("root_causes"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            cause_id = str(row.get("cause_id", "")).strip()
            if cause_id:
                out.add(cause_id)
        return out

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _string_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]
