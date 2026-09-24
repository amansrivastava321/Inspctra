"""
impact_analyzer.py - Maps findings to business areas and estimates impact scope.
Identifies affected areas: auth, billing, payments, sync, inventory,
orders, reporting, user data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging
import time

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)

# Business area mapping keywords
BUSINESS_AREA_KEYWORDS = {
    "auth": ["auth", "login", "session", "token", "password", "credential", "jwt", "oauth", "sso"],
    "billing": ["billing", "invoice", "subscription", "plan", "pricing", "charge"],
    "payments": ["payment", "checkout", "stripe", "paypal", "transaction", "refund", "charge"],
    "sync": ["sync", "offline", "replication", "conflict", "merge", "push", "pull"],
    "inventory": ["inventory", "stock", "product", "catalog", "sku", "warehouse"],
    "orders": ["order", "cart", "checkout", "purchase", "fulfillment", "shipping"],
    "reporting": ["report", "analytics", "dashboard", "metric", "chart", "export"],
    "user_data": ["user", "profile", "pii", "personal", "gdpr", "privacy", "data"],
}


class ImpactAnalyzer:
    """
    Maps findings to business areas and estimates impact scope.
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        correlated_findings: Optional[Dict[str, Any]] = None,
        risk_report: Optional[Dict[str, Any]] = None,
        app_map: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run impact analysis."""
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if correlated_findings is None:
            correlated_findings = self.store.load_artifact("correlated_findings") or {}
        if risk_report is None:
            risk_report = self.store.load_artifact("overall_risk_report") or {}

        findings = correlated_findings.get("findings", [])

        # Map findings to business areas
        area_impacts: Dict[str, Dict[str, Any]] = {}

        for area, keywords in BUSINESS_AREA_KEYWORDS.items():
            matched_findings: List[Dict[str, Any]] = []
            for f in findings:
                combined = f"{f.get('title', '')} {f.get('description', '')} {' '.join(f.get('tags', []))}".lower()
                if any(kw in combined for kw in keywords):
                    matched_findings.append(f)

            if matched_findings:
                max_severity = self._max_severity(matched_findings)
                area_impacts[area] = {
                    "finding_count": len(matched_findings),
                    "max_severity": max_severity,
                    "finding_ids": [f.get("id", "") for f in matched_findings[:10]],
                    "impact_scope": self._estimate_scope(len(matched_findings), max_severity),
                    "description": self._describe_impact(area, matched_findings),
                }

        # Overall impact summary
        affected_areas = list(area_impacts.keys())
        critical_areas = [a for a, d in area_impacts.items() if d["max_severity"] in ("critical", "high")]

        duration = time.time() - start_time

        result = {
            "metadata": {
                "analysis_type": "impact_analysis",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": duration,
                "generated_by": "ImpactAnalyzer",
                "total_findings_analyzed": len(findings),
            },
            "area_impacts": area_impacts,
            "summary": {
                "total_affected_areas": len(affected_areas),
                "affected_areas": affected_areas,
                "critical_areas": critical_areas,
                "overall_impact_scope": self._overall_scope(area_impacts),
            },
        }

        self.store.save_artifact("impact_analysis", result, agent="ImpactAnalyzer")
        logger.info(f"Impact analysis complete: {len(affected_areas)} business areas affected")
        return result

    def _max_severity(self, findings: List[Dict[str, Any]]) -> str:
        severity_order = ["critical", "high", "medium", "low", "info"]
        for sev in severity_order:
            if any(f.get("severity") == sev for f in findings):
                return sev
        return "info"

    def _estimate_scope(self, finding_count: int, max_severity: str) -> str:
        if max_severity == "critical" or finding_count >= 5:
            return "broad"
        elif max_severity == "high" or finding_count >= 3:
            return "moderate"
        else:
            return "narrow"

    def _overall_scope(self, area_impacts: Dict[str, Dict[str, Any]]) -> str:
        if not area_impacts:
            return "none"
        critical_count = sum(1 for d in area_impacts.values() if d["max_severity"] == "critical")
        if critical_count >= 2:
            return "systemic"
        elif critical_count >= 1 or len(area_impacts) >= 4:
            return "broad"
        elif len(area_impacts) >= 2:
            return "moderate"
        return "narrow"

    def _describe_impact(self, area: str, findings: List[Dict[str, Any]]) -> str:
        descriptions = {
            "auth": "Authentication and authorization issues may allow unauthorized access.",
            "billing": "Billing issues may cause revenue loss or incorrect charges.",
            "payments": "Payment issues may cause failed transactions or financial loss.",
            "sync": "Sync issues may cause data loss or inconsistency across devices.",
            "inventory": "Inventory issues may cause overselling or stock discrepancies.",
            "orders": "Order issues may cause lost orders or fulfillment failures.",
            "reporting": "Reporting issues may cause inaccurate business intelligence.",
            "user_data": "User data issues may cause privacy violations or compliance failures.",
        }
        return descriptions.get(area, f"{len(findings)} findings affecting {area}.")
