"""
patch_proposal_engine.py - Advisory-first remediation proposal generation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.remediation.patch_generator import PatchGenerator


class PatchProposalEngine:
    """Generate structured, evidence-linked remediation proposals without modifying files."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        base = PatchGenerator(self.store).run(proposal_only=True)
        fixes = self._load("fix_plan").get("fixes", [])
        fixes = fixes if isinstance(fixes, list) else []
        fix_by_id = {
            str(item.get("fix_id", "")).strip(): item
            for item in fixes
            if isinstance(item, dict) and str(item.get("fix_id", "")).strip()
        }

        evidence = self._load("evidence_interpretation")
        semantic_rca = self._load("semantic_root_cause_analysis")
        fallback_rca = self._load("root_cause_analysis")

        proposals: List[Dict[str, Any]] = []
        for row in base.get("proposals", []):
            if not isinstance(row, dict):
                continue
            fix_id = str(row.get("fix_id", "")).strip()
            fix = fix_by_id.get(fix_id, {})
            evidence_links = self._normalize_evidence(row.get("evidence_links", []))
            source_artifacts = self._source_artifacts(evidence_links)
            confidence = self._bounded_float(row.get("confidence"), 0.0, 1.0, default=0.55)

            retest_requirements = self._string_list(fix.get("recommended_tests"))
            affected_files = self._string_list(row.get("target_files"))
            affected_workflows = self._string_list(fix.get("affected_workflows"))
            if not affected_workflows:
                affected_workflows = self._infer_workflows_from_rca(fix_id, semantic_rca, fallback_rca)

            proposal = {
                "proposal_id": str(row.get("proposal_id", f"PATCH-{len(proposals) + 1:03d}")),
                "fix_id": fix_id,
                "rationale": self._build_rationale(row, fix, evidence),
                "confidence": confidence,
                "source_artifacts": source_artifacts,
                "source_evidence": evidence_links,
                "affected_files": affected_files,
                "target_files": affected_files,
                "affected_workflows": affected_workflows,
                "rollback_considerations": self._rollback_considerations(row, fix),
                "regression_sensitivity": self._regression_sensitivity(row, fix),
                "retest_requirements": retest_requirements,
                "pseudo_patch": str(row.get("patch_preview", "")),
                "change_recommendations": self._string_list(row.get("suggested_changes")),
                "safe_edit_description": "advisory proposal only; explicit approval required before any execution",
                "config_changes": self._config_changes(row, fix),
                "dependency_changes": self._dependency_changes(row, fix),
                "advisory_only": True,
                "approval_required": True,
                "apply_by_default": False,
                "direct_file_modification": False,
            }
            proposals.append(proposal)

        result = {
            "mode": "advisory_first",
            "proposals": proposals,
            "summary": {
                "proposal_count": len(proposals),
                "advisory_only": True,
                "approval_required": True,
                "direct_file_modification": False,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("patch_proposals", result, agent="PatchProposalEngine")
        return result

    def _infer_workflows_from_rca(self, fix_id: str, semantic_rca: Dict[str, Any], fallback_rca: Dict[str, Any]) -> List[str]:
        out: Set[str] = set()
        for payload in (semantic_rca, fallback_rca):
            causes = payload.get("root_causes", []) if isinstance(payload, dict) else []
            if not isinstance(causes, list):
                continue
            for cause in causes:
                if not isinstance(cause, dict):
                    continue
                linked = self._string_list(cause.get("fix_ids"))
                if fix_id and fix_id in linked:
                    out.update(self._string_list(cause.get("affected_workflows")))
        return sorted(out)

    def _rollback_considerations(self, proposal: Dict[str, Any], fix: Dict[str, Any]) -> List[str]:
        files = self._string_list(proposal.get("target_files"))
        considerations = [
            "snapshot affected files before any apply step",
            "use approval-gated rollback plan before rollout",
        ]
        if len(files) > 3:
            considerations.append("split into staged rollouts due to file-count impact")
        risk = str(fix.get("risk_level", proposal.get("risk_level", "medium"))).lower()
        if risk in {"high", "critical"}:
            considerations.append("require mandatory human checkpoint before and after apply")
        return considerations

    def _regression_sensitivity(self, proposal: Dict[str, Any], fix: Dict[str, Any]) -> str:
        risk = str(fix.get("risk_level", proposal.get("risk_level", "medium"))).lower()
        files = len(self._string_list(proposal.get("target_files")))
        if risk in {"critical", "high"} or files >= 5:
            return "high"
        if risk == "medium" or files >= 2:
            return "medium"
        return "low"

    def _build_rationale(self, proposal: Dict[str, Any], fix: Dict[str, Any], evidence: Dict[str, Any]) -> str:
        title = str(proposal.get("title", fix.get("title", "Remediation proposal"))).strip()
        desc = str(proposal.get("description", fix.get("description", ""))).strip()
        evidence_basis = "evidence-backed"
        if isinstance(evidence, dict):
            overall = evidence.get("overall_confidence")
            if isinstance(overall, (int, float)):
                evidence_basis = f"evidence-backed (interpretation_confidence={round(float(overall), 2)})"
        return f"{title}: {desc or 'deterministic issue resolution plan'}; {evidence_basis}."

    def _source_artifacts(self, evidence_links: List[Dict[str, str]]) -> List[str]:
        artifacts = [row.get("artifact", "") for row in evidence_links if isinstance(row, dict)]
        normalized = {
            f"{artifact}.json" if artifact and not artifact.endswith(".json") else artifact
            for artifact in artifacts
            if artifact
        }
        normalized.update(
            {
                "fix_plan.json",
                "ai_fix_reasoning.json",
                "semantic_root_cause_analysis.json",
                "evidence_interpretation.json",
            }
        )
        return sorted(normalized)

    def _normalize_evidence(self, value: Any) -> List[Dict[str, str]]:
        links: List[Dict[str, str]] = []
        if not isinstance(value, list):
            return links
        for row in value:
            if not isinstance(row, dict):
                continue
            artifact = str(row.get("artifact", "")).strip()
            reference = str(row.get("reference", "")).strip()
            if artifact and reference:
                links.append({"artifact": artifact, "reference": reference})
        return links

    def _config_changes(self, proposal: Dict[str, Any], fix: Dict[str, Any]) -> List[str]:
        combined = " ".join(
            self._string_list(proposal.get("suggested_changes"))
            + [str(fix.get("description", ""))]
        ).lower()
        out: List[str] = []
        if "config" in combined or "flag" in combined:
            out.append("review runtime config toggles under approval workflow")
        return out

    def _dependency_changes(self, proposal: Dict[str, Any], fix: Dict[str, Any]) -> List[str]:
        combined = " ".join(
            self._string_list(proposal.get("suggested_changes"))
            + [str(fix.get("description", ""))]
        ).lower()
        out: List[str] = []
        if "dependency" in combined or "package" in combined or "version" in combined:
            out.append("evaluate dependency delta in sandbox before approval")
        return out

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _string_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _bounded_float(self, value: Any, minimum: float, maximum: float, default: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = default
        parsed = max(minimum, min(maximum, parsed))
        return round(parsed, 4)
