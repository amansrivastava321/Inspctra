"""
scenario_intelligence_engine.py - Convert AI test intents into execution-ready scenario plans.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class ScenarioIntelligenceEngine:
    """Maps test intents to candidate scenarios and deterministic execution subsystems."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        intents_payload = self._load("test_intents")
        intents = intents_payload.get("test_intents", []) if isinstance(intents_payload.get("test_intents"), list) else []
        plans: List[Dict[str, Any]] = []
        for index, intent in enumerate(intents, start=1):
            if not isinstance(intent, dict):
                continue
            domain = str(intent.get("domain", "runtime"))
            plans.append(
                {
                    "scenario_id": f"AI-SCENARIO-{index:03d}",
                    "intent_id": str(intent.get("intent_id", f"INTENT-{index:03d}")),
                    "domain": domain,
                    "execution_system": self._execution_system(domain),
                    "candidate_templates": self._templates(domain),
                    "deterministic_validation_required": True,
                    "expected_evidence": intent.get("expected_evidence", []),
                    "source_references": ["test_intents.json", "scenario_engine.py"],
                    "confidence": float(intent.get("confidence", 0.55)),
                }
            )

        result = {
            "scenarios": plans,
            "summary": {
                "scenario_count": len(plans),
                "uses_existing_engines": True,
                "engines": [
                    "ScenarioEngine",
                    "DistributedRuntimeRunner",
                    "MobileRuntimeRunner",
                    "LiveScenarioRunner",
                ],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("intelligent_scenario_plan", result, agent="ScenarioIntelligenceEngine")
        return result

    def _execution_system(self, domain: str) -> str:
        if domain == "mobile":
            return "MobileRuntimeRunner"
        if domain == "distributed":
            return "DistributedRuntimeRunner"
        if domain in {"runtime", "performance"}:
            return "LiveScenarioRunner"
        return "ScenarioEngine"

    def _templates(self, domain: str) -> List[str]:
        mapping = {
            "security": ["login_flow", "role_transition"],
            "sync": ["offline_sync_flow"],
            "distributed": ["retry_after_failure", "duplicate_submission"],
            "runtime": ["login_flow", "retry_after_failure"],
            "mobile": ["offline_sync_flow", "role_transition"],
            "api": ["retry_after_failure"],
            "database": ["duplicate_submission"],
            "performance": ["retry_after_failure"],
            "release_readiness": ["login_flow"],
        }
        return mapping.get(domain, ["login_flow"])

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
