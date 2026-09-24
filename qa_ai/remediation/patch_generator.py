"""
patch_generator.py - Builds advisory patch proposals from deterministic artifacts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from qa_ai.runtime.artifact_store import ArtifactStore


class PatchGenerator:
    """Generate non-applying patch proposals linked to evidence and fix context."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, proposal_only: bool = False) -> Dict[str, Any]:
        fix_plan = self._load("fix_plan")
        findings = self._load("correlated_findings")
        if not findings:
            findings = self._load("findings")
        rca = self._load("root_cause_analysis")
        ai_fix_reasoning = self._load("ai_fix_reasoning")

        finding_map = self._finding_map(findings)
        rca_map = self._rca_map(rca)
        ai_strategies = ai_fix_reasoning.get("strategies", []) if isinstance(ai_fix_reasoning.get("strategies"), list) else []
        ai_by_fix = {
            str(item.get("fix_id", "")).strip(): item
            for item in ai_strategies
            if isinstance(item, dict) and str(item.get("fix_id", "")).strip()
        }

        proposals: List[Dict[str, Any]] = []
        fixes = fix_plan.get("fixes", []) if isinstance(fix_plan.get("fixes"), list) else []
        for fix in fixes:
            if not isinstance(fix, dict):
                continue
            fix_id = str(fix.get("fix_id", "")).strip() or f"FIX-{len(proposals) + 1:03d}"
            related_findings = [
                finding_map[fid]
                for fid in (fix.get("finding_ids", []) if isinstance(fix.get("finding_ids"), list) else [])
                if isinstance(fid, str) and fid in finding_map
            ]
            related_causes = self._related_causes(fix, rca_map)
            related_strategy = ai_by_fix.get(fix_id, {})
            unsafe_reasons = self._unsafe_reasons(fix)

            proposal = {
                "proposal_id": f"PATCH-{len(proposals) + 1:03d}",
                "fix_id": fix_id,
                "title": str(fix.get("title", "Untitled fix proposal")),
                "description": str(fix.get("description", "")),
                "risk_level": str(fix.get("risk_level", "medium")),
                "confidence": float(fix.get("confidence", 0.55) or 0.55),
                "target_files": self._string_list(fix.get("affected_files")),
                "affected_functions": self._string_list(fix.get("affected_functions")),
                "suggested_changes": self._build_suggested_changes(fix, related_findings, related_causes, related_strategy),
                "patch_preview": self._build_patch_preview(fix),
                "evidence_links": self._evidence_links(related_findings, related_causes),
                "source_artifacts": [
                    "fix_plan.json",
                    "correlated_findings.json" if findings else "findings.json",
                    "root_cause_analysis.json",
                    "ai_fix_reasoning.json",
                ],
                "advisory_only": True,
                "approval_required": True,
                "apply_by_default": False,
                "unsafe_reasons": unsafe_reasons,
                "is_safe": len(unsafe_reasons) == 0,
            }
            proposals.append(proposal)

        # Fallback if no fix plan exists: create minimal advisory proposals from findings.
        if not proposals:
            raw_findings = findings.get("findings", []) if isinstance(findings.get("findings"), list) else []
            for finding in raw_findings[:10]:
                if not isinstance(finding, dict):
                    continue
                finding_id = str(finding.get("id", "")).strip() or f"F-{len(proposals) + 1:03d}"
                target_file = str(finding.get("file_path", "")).strip()
                target_files = [target_file] if target_file else []
                proposals.append(
                    {
                        "proposal_id": f"PATCH-{len(proposals) + 1:03d}",
                        "fix_id": f"FIX-AUTO-{len(proposals) + 1:03d}",
                        "title": f"Advisory patch for {finding.get('title', 'finding')}",
                        "description": str(finding.get("description", "")),
                        "risk_level": str(finding.get("severity", "medium")).lower(),
                        "confidence": float(finding.get("confidence", 0.45) or 0.45),
                        "target_files": target_files,
                        "affected_functions": [],
                        "suggested_changes": [
                            "Implement the minimum change that closes the finding without broad refactors.",
                            "Add focused regression tests for the affected surface.",
                        ],
                        "patch_preview": self._preview_for_target(target_files),
                        "evidence_links": [{"artifact": "correlated_findings", "reference": finding_id}],
                        "source_artifacts": ["correlated_findings.json"],
                        "advisory_only": True,
                        "approval_required": True,
                        "apply_by_default": False,
                        "unsafe_reasons": [],
                        "is_safe": True,
                    }
                )

        result = {
            "proposal_only": bool(proposal_only),
            "proposals": proposals,
            "summary": {
                "proposal_count": len(proposals),
                "safe_proposals": sum(1 for item in proposals if item.get("is_safe")),
                "unsafe_proposals": sum(1 for item in proposals if not item.get("is_safe")),
                "requires_approval_count": sum(1 for item in proposals if item.get("approval_required")),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("patch_proposals", result, agent="PatchGenerator")
        return result

    def _build_suggested_changes(
        self,
        fix: Dict[str, Any],
        related_findings: List[Dict[str, Any]],
        related_causes: List[Dict[str, Any]],
        related_strategy: Dict[str, Any],
    ) -> List[str]:
        changes: List[str] = []
        for step in self._string_list(fix.get("safe_steps")):
            changes.append(step)
        for finding in related_findings[:3]:
            title = str(finding.get("title", "")).strip()
            if title:
                changes.append(f"Address finding: {title}")
        for cause in related_causes[:2]:
            description = str(cause.get("description", "")).strip()
            if description:
                changes.append(f"Mitigate root cause: {description}")
        strategy = str(related_strategy.get("recommended_strategy", "")).strip()
        if strategy:
            changes.append(f"AI advisory strategy: {strategy}")
        if not changes:
            changes.append("Apply the smallest deterministic fix aligned with evidence.")
        # Keep deterministic ordering while deduplicating.
        deduped: List[str] = []
        seen: Set[str] = set()
        for item in changes:
            if item not in seen:
                deduped.append(item)
                seen.add(item)
        return deduped

    def _build_patch_preview(self, fix: Dict[str, Any]) -> str:
        targets = self._string_list(fix.get("affected_files"))
        return self._preview_for_target(targets)

    def _preview_for_target(self, target_files: List[str]) -> str:
        if not target_files:
            return (
                "--- a/<target-file>\n"
                "+++ b/<target-file>\n"
                "@@ advisory @@\n"
                "- old behavior\n"
                "+ safe deterministic fix (approval-gated, not applied by default)\n"
            )
        first = target_files[0]
        return (
            f"--- a/{first}\n"
            f"+++ b/{first}\n"
            "@@ advisory @@\n"
            "- previous implementation\n"
            "+ proposed safe fix (approval-gated, not applied by default)\n"
        )

    def _unsafe_reasons(self, fix: Dict[str, Any]) -> List[str]:
        reasons: List[str] = []
        files = self._string_list(fix.get("affected_files"))
        if any(path.startswith("/") for path in files):
            reasons.append("absolute_path_target_disallowed")
        if len(files) > 15:
            reasons.append("too_many_target_files")
        description = str(fix.get("description", "")).lower()
        if any(token in description for token in ["drop table", "truncate", "delete all", "rm -rf", "shutdown"]):
            reasons.append("destructive_instruction_detected")
        return reasons

    def _evidence_links(self, findings: List[Dict[str, Any]], causes: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        links: List[Dict[str, str]] = []
        for finding in findings[:10]:
            links.append({"artifact": "correlated_findings", "reference": str(finding.get("id", ""))})
        for cause in causes[:5]:
            links.append({"artifact": "root_cause_analysis", "reference": str(cause.get("cause_id", ""))})
        if not links:
            links.append({"artifact": "fix_plan", "reference": "$.fixes"})
        return links

    def _related_causes(self, fix: Dict[str, Any], cause_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        finding_ids = self._string_list(fix.get("finding_ids"))
        out: List[Dict[str, Any]] = []
        for fid in finding_ids:
            if fid in cause_map:
                out.append(cause_map[fid])
        return out

    def _finding_map(self, findings_payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        findings = findings_payload.get("findings", []) if isinstance(findings_payload.get("findings"), list) else []
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            fid = str(finding.get("id", "")).strip()
            if fid:
                out[fid] = finding
        return out

    def _rca_map(self, rca_payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        causes = rca_payload.get("root_causes", []) if isinstance(rca_payload.get("root_causes"), list) else []
        for cause in causes:
            if not isinstance(cause, dict):
                continue
            for fid in self._string_list(cause.get("finding_ids")):
                out[fid] = cause
        return out

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _string_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]
