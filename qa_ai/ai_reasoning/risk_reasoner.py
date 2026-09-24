"""
risk_reasoner.py - Semantic risk explanations and chain construction.
"""

from __future__ import annotations

from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class RiskReasoner:
    """Combine deterministic risk scores with explicit semantic rationale."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        runtime_risk = self._load("runtime_risk_report")
        if not runtime_risk:
            runtime_risk = self._load("overall_risk_report")
        findings = runtime_risk.get("findings", [])
        findings = findings if isinstance(findings, list) else []
        root_causes = self._load("semantic_root_cause_analysis").get("hypotheses", [])
        root_causes = root_causes if isinstance(root_causes, list) else []

        top_risks = [item for item in findings[:10] if isinstance(item, dict)]
        risk_explanations: List[Dict[str, Any]] = []
        for item in top_risks:
            risk_explanations.append(
                {
                    "risk_id": item.get("id", ""),
                    "title": item.get("title", ""),
                    "severity": item.get("severity", ""),
                    "confidence": 0.66,
                    "rationale": f"Risk carries {item.get('severity', 'unknown')} severity and targets {item.get('target', item.get('api_endpoint', 'unknown'))}.",
                    "evidence_references": ["runtime_risk_report.json"],
                    "deterministic_references": ["runtime_risk_report.json"],
                }
            )

        risk_chains = self._build_risk_chains(findings=findings, root_causes=root_causes)

        report = {
            "risk_level": runtime_risk.get("risk_level", "unknown"),
            "overall_risk_score": runtime_risk.get("overall_adjusted_risk_score", runtime_risk.get("overall_risk_score", 0.0)),
            "risk_explanations": risk_explanations,
            "risk_chains": risk_chains,
            "summary": {
                "top_risk_count": len(risk_explanations),
                "chain_count": len(risk_chains),
            },
        }
        self.store.save_artifact("semantic_risk_report", report, agent="RiskReasoner")
        return report

    def _build_risk_chains(self, findings: List[Dict[str, Any]], root_causes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        text_blob = " ".join(
            [
                str(item.get("title", "")) + " " + str(item.get("description", "")) + " " + str(item.get("category", ""))
                for item in findings
                if isinstance(item, dict)
            ]
        ).lower()
        root_blob = " ".join(str(item.get("hypothesis", "")) for item in root_causes if isinstance(item, dict)).lower()
        chains: List[Dict[str, Any]] = []
        if ("auth" in text_blob or "auth" in root_blob) and ("sync" in text_blob or "sync" in root_blob):
            chains.append(
                {
                    "chain_id": "chain_auth_sync_integrity",
                    "chain": ["auth gap", "sync corruption", "data integrity issue", "business impact"],
                    "confidence": 0.7,
                    "rationale": "Auth and sync signals co-occur in deterministic findings/hypotheses.",
                    "deterministic_references": ["runtime_risk_report.json", "semantic_root_cause_analysis.json"],
                }
            )
        if not chains:
            chains.append(
                {
                    "chain_id": "chain_generic_quality",
                    "chain": ["input validation gap", "runtime instability", "service reliability impact"],
                    "confidence": 0.51,
                    "rationale": "Fallback semantic chain based on available deterministic risk artifacts.",
                    "deterministic_references": ["runtime_risk_report.json"],
                }
            )
        return chains

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
