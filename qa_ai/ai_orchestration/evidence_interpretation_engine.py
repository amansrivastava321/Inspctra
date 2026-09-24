"""
evidence_interpretation_engine.py - Evidence-backed interpretation without proof inflation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class EvidenceInterpretationEngine:
    """Summarizes what evidence proves, partially proves, does not prove, or blocks."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        findings_payload = self._load("verified_findings")
        if not findings_payload:
            findings_payload = self._load("correlated_findings")
        findings = findings_payload.get("findings", []) if isinstance(findings_payload.get("findings"), list) else []

        evidence_pool = self._evidence_pool()
        interpretations: List[Dict[str, Any]] = []
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            refs = self._finding_refs(finding)
            status = self._status(refs, evidence_pool["total_evidence_count"])
            interpretations.append(
                {
                    "finding_id": str(finding.get("id", "")),
                    "title": str(finding.get("title", "")),
                    "status": status,
                    "evidence_references": refs,
                    "evidence_strength": self._strength(status, refs),
                    "notes": self._notes(status),
                    "source_artifacts": ["execution_trace.json", "network_trace.json", "evidence_graph.json"],
                }
            )

        summary = {
            "proved": sum(1 for row in interpretations if row.get("status") == "proved"),
            "partially_proved": sum(1 for row in interpretations if row.get("status") == "partially_proved"),
            "not_proved": sum(1 for row in interpretations if row.get("status") == "not_proved"),
            "blocked": sum(1 for row in interpretations if row.get("status") == "blocked"),
            "total_evidence_count": evidence_pool["total_evidence_count"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        result = {
            "interpretations": interpretations,
            "evidence_pool": evidence_pool,
            "summary": summary,
            "safety": {
                "no_claim_without_evidence": True,
                "proof_requires_reference": True,
            },
        }
        self.store.save_artifact("evidence_interpretation", result, agent="EvidenceInterpretationEngine")
        return result

    def _evidence_pool(self) -> Dict[str, Any]:
        execution_trace = self._load("execution_trace")
        network_trace = self._load("network_trace")
        evidence_graph = self._load("evidence_graph")
        events = execution_trace.get("events", []) if isinstance(execution_trace.get("events"), list) else []
        requests = network_trace.get("requests", []) if isinstance(network_trace.get("requests"), list) else []
        graph_nodes = evidence_graph.get("graph", {}).get("nodes", []) if isinstance(evidence_graph.get("graph"), dict) else []
        total = len(events) + len(requests) + (len(graph_nodes) if isinstance(graph_nodes, list) else 0)
        return {
            "trace_events": len(events),
            "network_events": len(requests),
            "graph_nodes": len(graph_nodes) if isinstance(graph_nodes, list) else 0,
            "total_evidence_count": total,
        }

    def _finding_refs(self, finding: Dict[str, Any]) -> List[str]:
        refs: List[str] = []
        raw = finding.get("evidence_refs", finding.get("evidence", []))
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    value = str(item.get("filename", item.get("evidence_type", ""))).strip()
                    if value:
                        refs.append(value)
                else:
                    value = str(item).strip()
                    if value:
                        refs.append(value)
        return refs

    def _status(self, refs: List[str], evidence_count: int) -> str:
        if evidence_count <= 0:
            return "blocked"
        if refs:
            return "proved"
        if evidence_count > 0:
            return "partially_proved"
        return "not_proved"

    def _strength(self, status: str, refs: List[str]) -> str:
        if status == "proved" and refs:
            return "strong"
        if status == "partially_proved":
            return "moderate"
        if status == "blocked":
            return "none"
        return "weak"

    def _notes(self, status: str) -> str:
        if status == "proved":
            return "Deterministic evidence references support this interpretation."
        if status == "partially_proved":
            return "Evidence exists globally, but finding-level linkage is incomplete."
        if status == "blocked":
            return "No evidence artifacts available; proof claim blocked."
        return "Evidence does not currently prove this finding."

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
