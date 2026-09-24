"""
ai_decision_log.py - Track AI-led decisions with evidence and fallback transparency.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class AIDecisionLog:
    """Persists AI decisions with reasons, source artifacts, and confidence."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, decisions: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        entries: List[Dict[str, Any]] = []
        for index, decision in enumerate(decisions or [], start=1):
            if not isinstance(decision, dict):
                continue
            source_artifacts = decision.get("source_artifacts", [])
            if not isinstance(source_artifacts, list):
                source_artifacts = []
            entries.append(
                {
                    "decision_id": f"AI-DEC-{index:03d}",
                    "decision": str(decision.get("decision", "")),
                    "reason": str(decision.get("reason", "")),
                    "source_artifacts": [str(item) for item in source_artifacts if str(item).strip()],
                    "confidence": float(decision.get("confidence", 0.5) or 0.5),
                    "fallback_mode": str(decision.get("fallback_mode", "deterministic_fallback")),
                }
            )

        result = {
            "decisions": entries,
            "summary": {
                "decision_count": len(entries),
                "all_have_sources": all(bool(item.get("source_artifacts")) for item in entries) if entries else True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("ai_decision_log", result, agent="AIDecisionLog")
        return result
