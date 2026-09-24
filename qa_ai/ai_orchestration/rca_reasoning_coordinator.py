"""
rca_reasoning_coordinator.py - Merge deterministic RCA and semantic RCA safely.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class RCAReasoningCoordinator:
    """Coordinates deterministic and semantic RCA while preserving evidence requirements."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        deterministic = self._load("root_cause_analysis")
        semantic = self._load("semantic_root_cause_analysis")
        det_causes = deterministic.get("root_causes", []) if isinstance(deterministic.get("root_causes"), list) else []
        sem_hypotheses = semantic.get("hypotheses", []) if isinstance(semantic.get("hypotheses"), list) else []

        hypotheses: List[Dict[str, Any]] = []
        for index, cause in enumerate(det_causes, start=1):
            if not isinstance(cause, dict):
                continue
            cause_id = str(cause.get("cause_id", f"RC-{index:03d}"))
            linked_sem = self._matching_semantic(cause, sem_hypotheses)
            hypotheses.append(
                {
                    "hypothesis_id": f"HYP-{index:03d}",
                    "deterministic_cause_id": cause_id,
                    "description": str(cause.get("description", "Deterministic RCA hypothesis.")),
                    "root_type": str(cause.get("root_type", "unknown")),
                    "evidence_references": [f"root_cause_analysis:{cause_id}"] + linked_sem.get("evidence_references", []),
                    "confidence": round(self._confidence(cause, linked_sem), 2),
                    "source_artifacts": ["root_cause_analysis.json", "semantic_root_cause_analysis.json"],
                }
            )

        result = {
            "mode": "deterministic_coordinated_with_semantic",
            "hypotheses": hypotheses,
            "summary": {
                "deterministic_root_cause_count": len(det_causes),
                "semantic_hypothesis_count": len(sem_hypotheses),
                "coordinated_hypothesis_count": len(hypotheses),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "safety": {
                "requires_deterministic_reference": True,
                "no_unreferenced_hypothesis": True,
            },
        }
        self.store.save_artifact("ai_rca_coordination", result, agent="RCAReasoningCoordinator")
        return result

    def _matching_semantic(self, cause: Dict[str, Any], hypotheses: List[Dict[str, Any]]) -> Dict[str, Any]:
        cause_findings = set(self._string_list(cause.get("finding_ids")))
        for hypothesis in hypotheses:
            if not isinstance(hypothesis, dict):
                continue
            refs = set(self._string_list(hypothesis.get("finding_ids")))
            if cause_findings and refs and cause_findings.intersection(refs):
                return hypothesis
        return {}

    def _confidence(self, cause: Dict[str, Any], semantic: Dict[str, Any]) -> float:
        det = float(cause.get("confidence", 0.55) or 0.55)
        sem = float(semantic.get("confidence", det) or det) if isinstance(semantic, dict) else det
        return max(0.0, min(0.98, (det * 0.75) + (sem * 0.25)))

    def _string_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
