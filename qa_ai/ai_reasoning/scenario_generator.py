"""
scenario_generator.py - Generate candidate scenarios from deterministic gaps.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class ScenarioGenerator:
    """Generate advisory scenarios with explicit safety classifications."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        findings = self._load("correlated_findings").get("findings", [])
        findings = findings if isinstance(findings, list) else []
        distributed = self._load("concurrency_analysis").get("anomalies", [])
        distributed = distributed if isinstance(distributed, list) else []
        mobile_monitor = self._load("mobile_runtime_monitor_report")
        graphify = self._graphify_snapshot()

        scenarios: List[Dict[str, Any]] = []
        scenarios.append(
            self._scenario(
                scenario_id="scenario-auth-boundary-multi-actor",
                objective="Validate permission boundaries across actor roles under concurrent operations.",
                actors=["cashier", "manager", "anonymous_user"],
                preconditions=["distributed runtime dry-run prepared"],
                steps=["start isolated actor sessions", "submit conflicting role actions", "verify permission denials and audit logs"],
                expected_outcomes=["unauthorized actions blocked", "no privilege escalation"],
                required_environment=["distributed-runtime", "api-auth-enabled"],
                safety_classification="safe_simulation",
                deterministic_references=["correlated_findings.json", "actor_registry.json"],
            )
        )

        if distributed:
            scenarios.append(
                self._scenario(
                    scenario_id="scenario-sync-race-recovery",
                    objective="Reproduce and verify conflict resolution for race and stale-write anomalies.",
                    actors=["customer", "background_sync"],
                    preconditions=["offline queue and sync endpoints available"],
                    steps=["queue offline edits", "reconnect with overlapping remote writes", "verify deduplication and conflict handling"],
                    expected_outcomes=["no duplicate entities", "convergent final state"],
                    required_environment=["distributed-runtime", "offline-simulation"],
                    safety_classification="safe_simulation",
                    deterministic_references=["concurrency_analysis.json", "sync_conflict_report.json"],
                )
            )

        reconnect_instability = int(mobile_monitor.get("reconnect_instability", 0) or 0)
        if reconnect_instability > 0:
            scenarios.append(
                self._scenario(
                    scenario_id="scenario-mobile-offline-reconnect",
                    objective="Validate mobile reconnect stability and data sync resilience.",
                    actors=["customer", "background_sync"],
                    preconditions=["mobile runtime plans generated", "network simulation enabled"],
                    steps=["switch to offline mode", "perform local mutations", "reconnect under intermittent connectivity"],
                    expected_outcomes=["queued actions replay once", "no stale local state divergence"],
                    required_environment=["mobile-runtime", "network-simulation"],
                    safety_classification="safe_simulation",
                    deterministic_references=["mobile_runtime_monitor_report.json", "mobile_network_report.json"],
                )
            )

        if graphify.get("graph_edges", 0) > 10000:
            scenarios.append(
                self._scenario(
                    scenario_id="scenario-hotspot-trace-validation",
                    objective="Increase evidence around hotspot modules highlighted by graph context.",
                    actors=["admin", "manager"],
                    preconditions=["graphify context loaded", "trace capture enabled"],
                    steps=["target hotspot workflow path", "capture trace and network evidence", "compare replay outcomes"],
                    expected_outcomes=["improved evidence density on hotspot path"],
                    required_environment=["trace-capture", "replay-analysis"],
                    safety_classification="safe_observational",
                    deterministic_references=["graphify-out/GRAPH_REPORT.md", "execution_trace.json"],
                )
            )

        # Use finding categories to propose one additional scenario.
        categories = sorted({str(item.get("category", "")).strip().lower() for item in findings if isinstance(item, dict) and item.get("category")})
        if categories:
            scenarios.append(
                self._scenario(
                    scenario_id="scenario-category-cluster-regression",
                    objective=f"Stress test dominant finding categories: {', '.join(categories[:4])}.",
                    actors=["manager", "customer"],
                    preconditions=["baseline findings available"],
                    steps=["execute representative critical flows", "inject category-specific negative inputs", "replay for regression confirmation"],
                    expected_outcomes=["category regression paths remain controlled"],
                    required_environment=["scenario-engine", "replay-engine"],
                    safety_classification="safe_simulation",
                    deterministic_references=["correlated_findings.json"],
                )
            )

        result = {
            "scenarios": scenarios,
            "summary": {
                "scenario_count": len(scenarios),
                "safety_classes": sorted({item.get("safety_classification", "") for item in scenarios}),
            },
        }
        self.store.save_artifact("ai_generated_scenarios", result, agent="ScenarioGenerator")
        return result

    def _scenario(
        self,
        scenario_id: str,
        objective: str,
        actors: List[str],
        preconditions: List[str],
        steps: List[str],
        expected_outcomes: List[str],
        required_environment: List[str],
        safety_classification: str,
        deterministic_references: List[str],
    ) -> Dict[str, Any]:
        return {
            "scenario_id": scenario_id,
            "objective": objective,
            "actors": actors,
            "preconditions": preconditions,
            "steps": steps,
            "expected_outcomes": expected_outcomes,
            "required_environment": required_environment,
            "safety_classification": safety_classification,
            "confidence": 0.63,
            "rationale": "Generated from deterministic artifact gaps and graph/runtime anomaly signals.",
            "evidence_references": deterministic_references,
            "deterministic_references": deterministic_references,
        }

    def _graphify_snapshot(self) -> Dict[str, Any]:
        graph_path = Path("graphify-out/graph.json")
        if not graph_path.exists():
            return {"graph_nodes": 0, "graph_edges": 0}
        try:
            import json

            payload = json.loads(graph_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.debug("_graph_stats: failed to parse graph.json: %s", e)
            return {"graph_nodes": 0, "graph_edges": 0}
        nodes = payload.get("nodes", [])
        edges = payload.get("edges") or payload.get("links") or []
        return {
            "graph_nodes": len(nodes) if isinstance(nodes, list) else 0,
            "graph_edges": len(edges) if isinstance(edges, list) else 0,
        }

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
