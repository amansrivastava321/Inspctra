"""
run_summary.py - Build and persist run summary artifacts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from qa_ai.runtime.artifact_store import ArtifactStore


class RunSummary:
    """Generate a portable run summary for CLI-driven audits."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def build(
        self,
        run_id: str,
        target_path: str,
        profile: str,
        phases_executed: List[str],
        status: str,
        warnings: Optional[List[str]] = None,
        errors: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        return {
            "run_id": run_id,
            "target_path": target_path,
            "profile": profile,
            "phases_executed": phases_executed,
            "artifacts_generated": self.store.list_artifacts(),
            "report_paths": self.store.list_reports(),
            "status": status,
            "warnings": warnings or [],
            "errors": errors or [],
            "dry_run": dry_run,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def save(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        self.store.save_artifact("run_summary", summary, agent="RunSummary")
        return summary
