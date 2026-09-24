"""
fix_reasoner.py - Advisory fix strategy reasoning with risk and retest scope.
"""

from __future__ import annotations

from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class FixReasoner:
    """Suggest advisory fix strategy refinements without applying changes."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        backlog = self._load("improvement_backlog").get("items", [])
        backlog = backlog if isinstance(backlog, list) else []
        fix_plan = self._load("fix_plan").get("fixes", [])
        fix_plan = fix_plan if isinstance(fix_plan, list) else []
        impact = self._load("change_impact_analysis")
        tests = impact.get("affected_tests", []) if isinstance(impact.get("affected_tests"), list) else []

        strategies: List[Dict[str, Any]] = []
        for fix in fix_plan[:12]:
            if not isinstance(fix, dict):
                continue
            risk_level = str(fix.get("risk_level", "medium"))
            strategies.append(
                {
                    "fix_id": fix.get("fix_id", ""),
                    "advisory_only": True,
                    "recommended_strategy": "stage_changes_incrementally" if risk_level in {"high", "critical"} else "batch_low_risk_changes",
                    "risk_level": risk_level,
                    "confidence": 0.67,
                    "rationale": f"Derived from deterministic fix risk level={risk_level}.",
                    "proposed_retest_scope": list(fix.get("recommended_tests", []))[:12] or tests[:12],
                    "deterministic_references": ["fix_plan.json", "change_impact_analysis.json"],
                    "evidence_references": ["fix_plan.json"],
                }
            )

        if not strategies and backlog:
            strategies.append(
                {
                    "fix_id": str(backlog[0].get("fix_id", "")) if isinstance(backlog[0], dict) else "",
                    "advisory_only": True,
                    "recommended_strategy": "validate_backlog_top_item_first",
                    "risk_level": str(backlog[0].get("risk_level", "medium")) if isinstance(backlog[0], dict) else "medium",
                    "confidence": 0.52,
                    "rationale": "Fallback strategy due to missing deterministic fix plan items.",
                    "proposed_retest_scope": tests[:10],
                    "deterministic_references": ["improvement_backlog.json", "change_impact_analysis.json"],
                    "evidence_references": ["improvement_backlog.json"],
                }
            )

        report = {
            "advisory_only": True,
            "strategies": strategies,
            "summary": {
                "strategy_count": len(strategies),
                "high_risk_suggestions": sum(1 for item in strategies if item.get("risk_level") in {"high", "critical"}),
            },
            "safety_note": "No code changes are applied by AI fix reasoning; output is advisory only.",
        }
        self.store.save_artifact("ai_fix_reasoning", report, agent="FixReasoner")
        return report

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
