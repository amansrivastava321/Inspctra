"""
improvement_strategy_engine.py - Convert validated findings into improvement strategy.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class ImprovementStrategyEngine:
    """Prioritizes improvement opportunities using evidence-backed findings only."""

    SEVERITY_SCORE = {"critical": 100, "high": 78, "medium": 52, "low": 28, "info": 14}

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        findings = self._validated_findings()
        improvements: List[Dict[str, Any]] = []
        for index, finding in enumerate(findings, start=1):
            severity = str(finding.get("severity", "medium")).lower()
            risk_score = self.SEVERITY_SCORE.get(severity, 52)
            evidence_strength = self._evidence_strength(finding)
            complexity = self._fix_complexity(finding)
            business_impact = self._business_impact(finding, severity)
            regression_risk = "high" if severity in {"critical", "high"} else "medium"
            priority = int(risk_score + business_impact - complexity + evidence_strength)

            improvements.append(
                {
                    "improvement_id": f"AI-IMP-{index:03d}",
                    "title": f"Improve: {finding.get('title', 'finding')}",
                    "source_finding_id": str(finding.get("id", "")),
                    "risk_score": risk_score,
                    "business_impact_score": business_impact,
                    "evidence_strength_score": evidence_strength,
                    "fix_complexity_score": complexity,
                    "regression_risk": regression_risk,
                    "priority_score": priority,
                    "source_artifacts": ["correlated_findings.json", "verified_findings.json", "evidence_interpretation.json"],
                }
            )
        improvements.sort(key=lambda row: row["priority_score"], reverse=True)

        result = {
            "improvements": improvements,
            "summary": {
                "improvement_count": len(improvements),
                "highest_priority": improvements[0]["improvement_id"] if improvements else None,
                "uses_validated_findings_only": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("ai_improvement_strategy", result, agent="ImprovementStrategyEngine")
        return result

    def _validated_findings(self) -> List[Dict[str, Any]]:
        verified = self._load("verified_findings")
        verified_findings = verified.get("findings", []) if isinstance(verified.get("findings"), list) else []
        if verified_findings:
            return [row for row in verified_findings if isinstance(row, dict)]
        correlated = self._load("correlated_findings")
        correlated_findings = correlated.get("findings", []) if isinstance(correlated.get("findings"), list) else []
        return [row for row in correlated_findings if isinstance(row, dict)]

    def _evidence_strength(self, finding: Dict[str, Any]) -> int:
        refs = finding.get("evidence_refs", finding.get("evidence", []))
        if isinstance(refs, list) and refs:
            return 15
        return 2

    def _fix_complexity(self, finding: Dict[str, Any]) -> int:
        file_path = str(finding.get("file_path", "")).strip()
        if not file_path:
            return 20
        if file_path.endswith(".py") or file_path.endswith(".ts") or file_path.endswith(".dart"):
            return 12
        return 18

    def _business_impact(self, finding: Dict[str, Any], severity: str) -> int:
        category = str(finding.get("category", "")).lower()
        base = 20 if severity in {"critical", "high"} else 10
        if "security" in category or "auth" in category:
            base += 15
        if "data" in category or "sync" in category:
            base += 12
        return base

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
