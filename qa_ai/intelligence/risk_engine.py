"""
risk_engine.py - Assigns weighted severity scores and calculates
overall application risk. Prioritizes findings and classifies them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging
import time

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)

# Severity weights for risk scoring
SEVERITY_WEIGHTS = {
    "critical": 10.0,
    "high": 7.0,
    "medium": 4.0,
    "low": 1.0,
    "info": 0.1,
}

# Category risk multipliers
CATEGORY_MULTIPLIERS = {
    "security": 1.5,
    "authentication": 1.5,
    "secrets": 2.0,
    "endpoint_auth": 1.8,
    "data_exposure": 1.4,
    "transport_security": 1.3,
    "token_security": 1.3,
    "idempotency": 1.1,
    "error_handling": 1.0,
    "file_size": 0.8,
    "function_size": 0.8,
    "class_size": 0.8,
    "technical_debt": 0.6,
    "duplication": 0.5,
    "version_pinning": 0.7,
    "ecosystem": 0.4,
    "environment_config": 0.8,
    "ci_cd": 0.9,
    "signing": 0.7,
    "monitoring": 0.8,
    "backup_recovery": 0.7,
    "debug_config": 1.2,
    "debug_flags": 1.0,
    "exposed_routes": 1.3,
    "data_storage": 1.0,
    "observability": 0.7,
}


class RiskEngine:
    """
    Calculates weighted risk scores for findings and the overall application.

    Risk score = sum(severity_weight * category_multiplier) for each finding.
    Overall risk is normalized to 0-100 scale.
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        correlated_findings: Optional[Dict[str, Any]] = None,
        app_map: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run the risk engine."""
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if correlated_findings is None:
            correlated_findings = self.store.load_artifact("correlated_findings") or {}

        findings = correlated_findings.get("findings", [])

        # Score each finding
        scored_findings: List[Dict[str, Any]] = []
        total_score = 0.0

        for f in findings:
            severity = f.get("severity", "medium")
            category = f.get("tags", [""])[0] if f.get("tags") else f.get("category", "")

            sev_weight = SEVERITY_WEIGHTS.get(severity, 4.0)
            cat_mult = CATEGORY_MULTIPLIERS.get(category, 1.0)
            score = sev_weight * cat_mult

            scored = {
                **f,
                "risk_score": round(score, 2),
                "risk_classification": self._classify_risk(score),
                "priority_rank": 0,  # Will be set after sorting
            }
            scored_findings.append(scored)
            total_score += score

        # Sort by risk score descending
        scored_findings.sort(key=lambda x: x["risk_score"], reverse=True)
        for i, f in enumerate(scored_findings):
            f["priority_rank"] = i + 1

        # Calculate overall risk
        max_possible = len(findings) * 10.0 * 2.0  # critical * highest multiplier
        overall_score = min(100.0, (total_score / max_possible * 100)) if max_possible > 0 else 0.0

        # Risk classification
        if overall_score >= 75:
            risk_level = "critical"
        elif overall_score >= 50:
            risk_level = "high"
        elif overall_score >= 25:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Category breakdown
        category_scores: Dict[str, float] = {}
        for f in scored_findings:
            cat = f.get("category", "unknown")
            category_scores[cat] = category_scores.get(cat, 0.0) + f["risk_score"]

        duration = time.time() - start_time

        result = {
            "metadata": {
                "risk_type": "risk_assessment",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": duration,
                "generated_by": "RiskEngine",
            },
            "overall_risk_score": round(overall_score, 2),
            "risk_level": risk_level,
            "total_findings": len(findings),
            "total_risk_score": round(total_score, 2),
            "findings": scored_findings,
            "category_breakdown": {k: round(v, 2) for k, v in sorted(category_scores.items(), key=lambda x: -x[1])},
            "top_risks": scored_findings[:10],
            "risk_distribution": {
                "critical": sum(1 for f in scored_findings if f["risk_classification"] == "critical"),
                "high": sum(1 for f in scored_findings if f["risk_classification"] == "high"),
                "medium": sum(1 for f in scored_findings if f["risk_classification"] == "medium"),
                "low": sum(1 for f in scored_findings if f["risk_classification"] == "low"),
            },
        }

        self.store.save_artifact("overall_risk_report", result, agent="RiskEngine")
        logger.info(f"Risk assessment complete: {risk_level} risk ({overall_score:.1f}/100)")
        return result

    def _classify_risk(self, score: float) -> str:
        if score >= 14.0:
            return "critical"
        elif score >= 8.0:
            return "high"
        elif score >= 3.0:
            return "medium"
        else:
            return "low"
