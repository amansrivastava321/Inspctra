"""
learning_registry.py - Stores lessons from previous audits.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import time

from qa_ai.runtime.artifact_store import ArtifactStore


class LearningRegistry:
    """Persists reusable improvement lessons."""

    CATEGORIES = [
        "false_positives",
        "effective_tests",
        "recurring_root_causes",
        "high_value_fix_patterns",
        "risky_modules",
    ]

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        lessons: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        audit_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        start = time.time()
        started_at = datetime.now(timezone.utc).isoformat()
        existing = self.store.load_artifact("learning_registry") or {}
        lessons = lessons or self._lessons_from_audit(audit_result or {})

        registry = {category: list(existing.get(category, [])) for category in self.CATEGORIES}
        for category in self.CATEGORIES:
            registry[category] = self._merge_unique(registry[category], lessons.get(category, []))

        total_lessons = sum(len(registry[category]) for category in self.CATEGORIES)
        result = {
            "metadata": {
                "registry_type": "continuous_learning",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": time.time() - start,
                "generated_by": "LearningRegistry",
            },
            **registry,
            "summary": {
                "total_lessons": total_lessons,
                **{f"{category}_count": len(registry[category]) for category in self.CATEGORIES},
            },
        }
        self.store.save_artifact("learning_registry", result, agent="LearningRegistry")
        return result

    def _merge_unique(self, existing: List[Dict[str, Any]], incoming: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged = list(existing)
        seen = {self._key(item) for item in merged}
        for item in incoming:
            key = self._key(item)
            if key not in seen:
                merged.append(item)
                seen.add(key)
        return merged

    def _key(self, item: Dict[str, Any]) -> str:
        return str(item.get("id") or item.get("pattern") or item.get("description") or item)

    def _lessons_from_audit(self, audit_result: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        lessons = {category: [] for category in self.CATEGORIES}
        for root in audit_result.get("root_causes", []):
            lessons["recurring_root_causes"].append({
                "id": root.get("cause_id", root.get("description")),
                "description": root.get("description", ""),
                "root_type": root.get("root_type", ""),
            })
        for fix in audit_result.get("fixes", []):
            if fix.get("risk_level") in {"low", "medium"} and fix.get("confidence", 0) >= 0.7:
                lessons["high_value_fix_patterns"].append({
                    "id": fix.get("fix_id"),
                    "description": fix.get("title", ""),
                    "affected_files": fix.get("affected_files", []),
                })
            for file_path in fix.get("affected_files", []):
                lessons["risky_modules"].append({"id": file_path, "module": file_path})
        return lessons
