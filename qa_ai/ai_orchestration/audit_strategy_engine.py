"""
audit_strategy_engine.py - Build AI-led audit strategy using deterministic context.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class AuditStrategyEngine:
    """Prioritizes audit domains based on software understanding and risk context."""

    DOMAINS = [
        "security",
        "runtime",
        "sync",
        "mobile",
        "distributed",
        "api",
        "database",
        "performance",
        "release_readiness",
    ]

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        understanding = self._load("software_understanding")
        software_type = str(understanding.get("software_type", "unknown_application"))
        risk_areas = understanding.get("business_risk_areas", []) if isinstance(understanding.get("business_risk_areas"), list) else []
        graph_nodes = self._to_int(understanding.get("graphify_context", {}).get("graph_nodes", 0))

        benchmark_summary = self._load("benchmark_summary")
        benchmark_findings = self._to_int(benchmark_summary.get("totals", {}).get("findings_total", 0))
        environment_report = self._load("doctor_report")
        env_status = str(environment_report.get("status", "unknown"))

        priorities: List[Dict[str, Any]] = []
        for domain in self.DOMAINS:
            score = self._score(domain, software_type, risk_areas, benchmark_findings, graph_nodes)
            priorities.append(
                {
                    "domain": domain,
                    "priority_score": score,
                    "priority_level": self._level(score),
                    "reason": self._reason(domain, software_type, risk_areas),
                    "confidence": round(min(0.95, 0.55 + score / 250.0), 2),
                }
            )
        priorities.sort(key=lambda row: row["priority_score"], reverse=True)

        result = {
            "software_type": software_type,
            "priorities": priorities,
            "selected_primary_paths": [row["domain"] for row in priorities[:4]],
            "strategy_mode": "ai_led_deterministic_execution",
            "fallback_mode": "deterministic_fallback",
            "source_artifacts": [
                "software_understanding.json",
                "benchmark_summary.json",
                "doctor_report.json",
                "graphify-out/graph.json",
            ],
            "summary": {
                "top_priority": priorities[0]["domain"] if priorities else "security",
                "environment_status": env_status,
                "benchmark_findings": benchmark_findings,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("ai_audit_strategy", result, agent="AuditStrategyEngine")
        return result

    def _score(
        self,
        domain: str,
        software_type: str,
        risk_areas: List[str],
        benchmark_findings: int,
        graph_nodes: int,
    ) -> int:
        score = 45
        if domain == "security":
            score += 25
        if domain == "api" and software_type in {"api_backend_service", "api_service", "full_stack_application"}:
            score += 30
        if domain == "mobile" and software_type == "mobile_application":
            score += 40
        if domain == "sync" and any(token in risk_areas for token in ["offline_sync", "device_state", "sync"]):
            score += 30
        if domain == "distributed" and "distributed" in " ".join(risk_areas):
            score += 25
        if domain == "database" and any(token in risk_areas for token in ["data", "authorization", "input_validation"]):
            score += 18
        if domain == "runtime":
            score += 16
        if domain == "release_readiness":
            score += 12
        if domain == "performance":
            score += min(benchmark_findings, 30) // 2
        score += min(graph_nodes // 1200, 12)
        return max(0, min(100, score))

    def _level(self, score: int) -> str:
        if score >= 80:
            return "critical"
        if score >= 65:
            return "high"
        if score >= 50:
            return "medium"
        return "low"

    def _reason(self, domain: str, software_type: str, risk_areas: List[str]) -> str:
        if domain == "mobile" and software_type == "mobile_application":
            return "Software classified as mobile; mobile runtime risk is primary."
        if domain == "api" and software_type in {"api_backend_service", "api_service", "full_stack_application"}:
            return "API-heavy architecture detected from app map and routes."
        if domain == "sync" and any(token in risk_areas for token in ["offline_sync", "sync"]):
            return "Risk areas include sync/offline behavior requiring dedicated checks."
        if domain == "security":
            return "Security is universally high priority and evidence-critical."
        return f"Prioritized from software type '{software_type}' and risk context."

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _to_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
