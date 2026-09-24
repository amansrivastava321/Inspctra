"""
audit_history_manager.py - Historical audit index and trend lookup.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class AuditHistoryManager:
    """Maintain historical audit index from local artifact state."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        existing = self._load("audit_history_index")
        history = existing.get("runs", []) if isinstance(existing.get("runs"), list) else []

        snapshot = self._snapshot()
        snap_id = str(snapshot.get("snapshot_id", ""))
        if snap_id and all(str(row.get("snapshot_id", "")) != snap_id for row in history if isinstance(row, dict)):
            history.append(snapshot)

        history_sorted = sorted(
            [row for row in history if isinstance(row, dict)],
            key=lambda item: str(item.get("captured_at", "")),
        )

        report = {
            "runs": history_sorted,
            "trend_lookup": self._trends(history_sorted),
            "summary": {
                "run_count": len(history_sorted),
                "latest_snapshot_id": str(history_sorted[-1].get("snapshot_id", "")) if history_sorted else "",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("audit_history_index", report, agent="Enterprise.AuditHistoryManager")
        return report

    def _snapshot(self) -> Dict[str, Any]:
        workflow = self._load("workflow_result")
        run_summary = self._load("run_summary")
        remediation = self._load("remediation_runtime_summary")
        cicd = self._load("cicd_runtime_summary")
        benchmark = self._load("benchmark_runtime_summary")

        source = {
            "workflow_status": workflow.get("status", "unknown"),
            "run_status": run_summary.get("status", "unknown"),
            "remediation_mode": remediation.get("mode", "none"),
            "release_decision": cicd.get("release_decision", "unknown"),
            "benchmark_overall": (benchmark.get("scores") or {}).get("overall", 0.0)
            if isinstance(benchmark.get("scores"), dict)
            else 0.0,
        }
        digest = sha1(str(sorted(source.items())).encode("utf-8")).hexdigest()[:16]
        return {
            "snapshot_id": f"AUD-{digest}",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
        }

    def _trends(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        statuses = [str((row.get("source") or {}).get("workflow_status", "unknown")) for row in history]
        completed = sum(1 for value in statuses if value == "completed")
        failed = sum(1 for value in statuses if value == "failed")
        degraded = sum(1 for value in statuses if value not in {"completed", "failed"})
        return {
            "completed_runs": completed,
            "failed_runs": failed,
            "other_runs": degraded,
        }

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
