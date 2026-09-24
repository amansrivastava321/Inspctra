"""
semantic_rca_engine.py - Semantic RCA over deterministic artifacts with safe fallback.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import json

from qa_ai.ai.model_profiles import RoutingComponent
from qa_ai.ai.model_router import ModelRouter
from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class SemanticRCAEngine:
    """Build semantic root-cause hypotheses without replacing deterministic RCA."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, use_model: bool = False) -> Dict[str, Any]:
        deterministic_rca = self._load("root_cause_analysis")
        correlated_findings = self._load("correlated_findings")
        evidence_graph = self._load("evidence_graph")
        runtime_behavior = self._load("behavioral_analysis")

        hypotheses = self._fallback_hypotheses(
            deterministic_rca=deterministic_rca,
            correlated_findings=correlated_findings,
            evidence_graph=evidence_graph,
            runtime_behavior=runtime_behavior,
        )
        mode = "deterministic_fallback"
        model_notes = ""

        if use_model:
            model_notes = self._try_model_summary(hypotheses, deterministic_rca, correlated_findings)
            if model_notes:
                mode = "model_augmented"

        result = {
            "mode": mode,
            "hypotheses": hypotheses,
            "model_notes": model_notes,
            "summary": {
                "hypothesis_count": len(hypotheses),
                "has_model_notes": bool(model_notes),
                "deterministic_reference_count": sum(len(item.get("deterministic_references", [])) for item in hypotheses),
            },
        }
        self.store.save_artifact("semantic_root_cause_analysis", result, agent="SemanticRCAEngine")
        return result

    def _fallback_hypotheses(
        self,
        deterministic_rca: Dict[str, Any],
        correlated_findings: Dict[str, Any],
        evidence_graph: Dict[str, Any],
        runtime_behavior: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        root_causes = deterministic_rca.get("root_causes", [])
        root_causes = root_causes if isinstance(root_causes, list) else []
        findings = correlated_findings.get("findings", [])
        findings = findings if isinstance(findings, list) else []
        graph_summary = evidence_graph.get("summary", {}) if isinstance(evidence_graph.get("summary"), dict) else {}
        anomalies = runtime_behavior.get("anomalies", []) if isinstance(runtime_behavior.get("anomalies"), list) else []

        hypotheses: List[Dict[str, Any]] = []
        for cause in root_causes[:12]:
            if not isinstance(cause, dict):
                continue
            finding_ids = cause.get("finding_ids", [])
            finding_ids = finding_ids if isinstance(finding_ids, list) else []
            hypotheses.append(
                {
                    "hypothesis": cause.get("description", "Deterministic root cause cluster"),
                    "confidence": float(cause.get("confidence", 0.55) or 0.55),
                    "rationale": f"Derived from deterministic RCA cause {cause.get('cause_id', 'unknown')}.",
                    "supporting_evidence": [
                        {"type": "finding", "reference": fid} for fid in finding_ids[:10]
                    ]
                    + [{"type": "evidence_graph", "reference": f"nodes={graph_summary.get('evidence_nodes', 0)}"}],
                    "affected_modules": cause.get("affected_files", []),
                    "affected_workflows": cause.get("affected_workflows", []),
                    "deterministic_references": [
                        {"artifact": "root_cause_analysis", "path": "$.root_causes"},
                        {"artifact": "correlated_findings", "path": "$.findings"},
                        {"artifact": "evidence_graph", "path": "$.summary"},
                    ],
                }
            )

        if not hypotheses:
            top_findings = [item for item in findings[:5] if isinstance(item, dict)]
            hypotheses.append(
                {
                    "hypothesis": "Clustered findings indicate shared quality and validation gaps.",
                    "confidence": 0.45,
                    "rationale": "Fallback hypothesis built from correlated findings due to missing deterministic RCA root causes.",
                    "supporting_evidence": [
                        {"type": "finding", "reference": item.get("id", "")} for item in top_findings
                    ]
                    + [{"type": "runtime_anomaly_count", "reference": str(len(anomalies))}],
                    "affected_modules": [item.get("file_path", "") for item in top_findings if item.get("file_path")][:8],
                    "affected_workflows": [],
                    "deterministic_references": [
                        {"artifact": "correlated_findings", "path": "$.findings"},
                        {"artifact": "behavioral_analysis", "path": "$.anomalies"},
                    ],
                }
            )
        return hypotheses

    def _try_model_summary(
        self,
        hypotheses: List[Dict[str, Any]],
        deterministic_rca: Dict[str, Any],
        correlated_findings: Dict[str, Any],
    ) -> str:
        router = ModelRouter(artifact_store=self.store)
        prompt = json.dumps(
            {
                "task": "Summarize semantic root cause patterns in <=120 words.",
                "hypotheses": hypotheses[:5],
                "deterministic_root_causes": (deterministic_rca.get("root_causes", []) if isinstance(deterministic_rca, dict) else [])[:5],
                "deterministic_findings": (correlated_findings.get("findings", []) if isinstance(correlated_findings, dict) else [])[:5],
            },
            ensure_ascii=True,
        )
        try:
            result = router.route(
                component=RoutingComponent.HUGE_REPO_REASONING,
                prompt=prompt,
                context={"contains_private_code": True, "graphify_summary": "semantic_rca_summary_only"},
                deterministic_fallback=lambda: "",
            )
            return result.content[:1200] if result.success else ""
        except Exception as e:
            logger.debug("specialist routing call failed: %s", e)
            return ""

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
