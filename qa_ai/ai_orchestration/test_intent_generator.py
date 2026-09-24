"""
test_intent_generator.py - Generate high-level AI-led test intents.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class TestIntentGenerator:
    """Creates intention-level audit tests before concrete test execution."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        strategy = self._load("ai_audit_strategy")
        understanding = self._load("software_understanding")
        priorities = strategy.get("priorities", []) if isinstance(strategy.get("priorities"), list) else []
        software_type = str(understanding.get("software_type", "unknown_application"))

        intents: List[Dict[str, Any]] = []
        for index, row in enumerate(priorities[:8], start=1):
            if not isinstance(row, dict):
                continue
            domain = str(row.get("domain", "security"))
            confidence = float(row.get("confidence", 0.6) or 0.6)
            intent = {
                "intent_id": f"INTENT-{index:03d}",
                "domain": domain,
                "title": f"Validate {domain} resilience",
                "why_this_matters": self._why(domain, software_type),
                "risk_being_tested": self._risk(domain),
                "expected_evidence": self._expected_evidence(domain),
                "required_environment": self._environment(domain, software_type),
                "confidence": round(max(0.0, min(0.99, confidence)), 2),
                "source_references": ["ai_audit_strategy.json", "software_understanding.json"],
            }
            intents.append(intent)

        if not intents:
            intents.append(
                {
                    "intent_id": "INTENT-001",
                    "domain": "security",
                    "title": "Validate baseline security posture",
                    "why_this_matters": "No strategy artifacts available; run baseline safety checks.",
                    "risk_being_tested": "Unauthenticated access and weak validation paths.",
                    "expected_evidence": ["execution_trace", "network_trace", "security_audit_results"],
                    "required_environment": "local_or_ci",
                    "confidence": 0.5,
                    "source_references": ["software_understanding.json"],
                }
            )

        result = {
            "test_intents": intents,
            "summary": {
                "intent_count": len(intents),
                "avg_confidence": round(sum(float(i.get("confidence", 0.0)) for i in intents) / len(intents), 3),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("test_intents", result, agent="TestIntentGenerator")
        return result

    def _why(self, domain: str, software_type: str) -> str:
        if domain == "security":
            return "Security failures can invalidate all downstream quality signals."
        if domain == "api":
            return f"{software_type} depends on API behavior for core business flows."
        if domain == "mobile":
            return "Device state and network changes can trigger user-facing failures."
        if domain == "sync":
            return "Sync consistency issues can silently corrupt business data."
        return "This domain materially affects release confidence and user trust."

    def _risk(self, domain: str) -> str:
        mapping = {
            "security": "Privilege bypass, auth gaps, and sensitive data exposure.",
            "runtime": "Execution failures under realistic runtime conditions.",
            "sync": "Data divergence during offline/online transitions.",
            "mobile": "Platform-specific regressions across device/tooling states.",
            "distributed": "Multi-actor race and ordering anomalies.",
            "api": "Contract drift, auth bypass, and invalid payload handling.",
            "database": "Data integrity and schema/migration regressions.",
            "performance": "Latency, throughput, and timeout instability.",
            "release_readiness": "Missing safeguards before shipping changes.",
        }
        return mapping.get(domain, "General software correctness risk.")

    def _expected_evidence(self, domain: str) -> List[str]:
        base = ["execution_trace", "evidence_graph"]
        if domain in {"security", "api", "database"}:
            base.append("network_trace")
        if domain in {"mobile", "sync"}:
            base.append("mobile_logs_index")
        if domain == "distributed":
            base.append("distributed_runtime_report")
        if domain == "release_readiness":
            base.append("release_readiness_results")
        return base

    def _environment(self, domain: str, software_type: str) -> str:
        if domain == "mobile" or software_type == "mobile_application":
            return "mobile_runtime"
        if domain == "distributed":
            return "distributed_runtime"
        if domain == "performance":
            return "runtime_lab"
        return "deterministic_audit_runtime"

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
