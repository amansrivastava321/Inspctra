"""
ai_confidence_tracker.py - Aggregate confidence metrics across AI-orchestration stages.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from qa_ai.runtime.artifact_store import ArtifactStore


class AIConfidenceTracker:
    """Tracks stage-level and overall confidence for AI-first orchestration."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, stage_confidence: Dict[str, float] | None = None) -> Dict[str, Any]:
        stages = stage_confidence if isinstance(stage_confidence, dict) else {}
        normalized: Dict[str, float] = {}
        for stage, value in stages.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric = 0.0
            normalized[str(stage)] = max(0.0, min(1.0, numeric))

        overall = round(sum(normalized.values()) / len(normalized), 3) if normalized else 0.0
        result = {
            "stage_confidence": normalized,
            "overall_confidence": overall,
            "summary": {
                "stage_count": len(normalized),
                "confidence_present": bool(normalized),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("ai_confidence_report", result, agent="AIConfidenceTracker")
        return result
