"""
improvement_reporter.py - Generates prioritized improvement backlog and summary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import time

from qa_ai.runtime.artifact_store import ArtifactStore


class ImprovementReporter:
    """Prioritizes improvements by risk, confidence, impact, and effort."""

    RISK = {"high": 3, "medium": 2, "low": 1}
    IMPACT = {"broad": 3, "moderate": 2, "narrow": 1, "none": 0}

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        health_score: Optional[Dict[str, Any]] = None,
        fix_plan: Optional[Dict[str, Any]] = None,
        impact_analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        start = time.time()
        started_at = datetime.now(timezone.utc).isoformat()
        health_score = health_score or self.store.load_artifact("software_health_score") or {}
        fix_plan = fix_plan or self.store.load_artifact("fix_plan") or {"fixes": []}
        impact_analysis = impact_analysis or self.store.load_artifact("change_impact_analysis") or {}

        backlog = []
        blast_radius = impact_analysis.get("risk_summary", {}).get("blast_radius", "none")
        for fix in fix_plan.get("fixes", []):
            effort = self._effort(fix)
            priority_score = self._priority(fix, blast_radius, effort)
            backlog.append({
                "item_id": f"IMP-{len(backlog) + 1:03d}",
                "fix_id": fix.get("fix_id"),
                "title": fix.get("title", "Untitled improvement"),
                "risk_level": fix.get("risk_level", "medium"),
                "confidence": fix.get("confidence", 0.5),
                "impact": blast_radius,
                "effort": effort,
                "priority_score": priority_score,
                "affected_files": fix.get("affected_files", []),
                "recommended_tests": fix.get("recommended_tests", []),
            })
        backlog.sort(key=lambda item: item["priority_score"], reverse=True)

        summary_text = self._summary_text(health_score, backlog)
        result = {
            "metadata": {
                "report_type": "improvement_backlog",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": time.time() - start,
                "generated_by": "ImprovementReporter",
            },
            "items": backlog,
            "summary_text": summary_text,
            "summary": {
                "total_items": len(backlog),
                "top_priority": backlog[0]["item_id"] if backlog else None,
                "health_score": health_score.get("overall_score"),
                "health_level": health_score.get("health_level"),
            },
        }
        self.store.save_artifact("improvement_backlog", result, agent="ImprovementReporter")
        self.store.save_report("improvement_summary.md", summary_text)
        return result

    def _priority(self, fix: Dict[str, Any], impact: str, effort: str) -> float:
        effort_penalty = {"low": 0.5, "medium": 1.0, "high": 1.5}.get(effort, 1.0)
        risk = self.RISK.get(fix.get("risk_level", "medium"), 2)
        confidence = float(fix.get("confidence", 0.5))
        impact_score = self.IMPACT.get(impact, 1)
        return round((risk * 3.0 + confidence * 2.0 + impact_score) / effort_penalty, 2)

    def _effort(self, fix: Dict[str, Any]) -> str:
        files = len(fix.get("affected_files", []))
        tests = len(fix.get("recommended_tests", []))
        if files <= 1 and tests <= 2:
            return "low"
        if files <= 3:
            return "medium"
        return "high"

    def _summary_text(self, health_score: Dict[str, Any], backlog: list[Dict[str, Any]]) -> str:
        lines = [
            "# Improvement Summary",
            "",
            f"Software health score: {health_score.get('overall_score', 'unknown')} ({health_score.get('health_level', 'unknown')}).",
            f"Improvement backlog items: {len(backlog)}.",
        ]
        if backlog:
            top = backlog[0]
            lines.extend([
                "",
                f"Top priority: {top['title']} ({top['risk_level']} risk, {top['impact']} impact, {top['effort']} effort).",
            ])
        return "\n".join(lines)
