"""
evidence_storage_optimizer.py - Plan evidence storage compaction safely.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class EvidenceStorageOptimizer:
    """Analyzes evidence volume and proposes non-destructive compaction steps."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        evidence_dir = self.store.evidence_dir
        rows: List[Dict[str, Any]] = []
        total_size = 0
        total_files = 0
        for folder in sorted([path for path in evidence_dir.iterdir() if path.is_dir()] if evidence_dir.exists() else []):
            files = [path for path in folder.rglob("*") if path.is_file()]
            size = sum(int(file.stat().st_size) for file in files)
            total_size += size
            total_files += len(files)
            rows.append(
                {
                    "evidence_type": folder.name,
                    "file_count": len(files),
                    "size_bytes": int(size),
                    "recommended_action": "compress_archive_candidate" if size > 50_000_000 else "keep",
                    "delete_now": False,
                }
            )

        report = {
            "directories": rows,
            "summary": {
                "evidence_directory": str(evidence_dir),
                "total_files": int(total_files),
                "total_size_bytes": int(total_size),
                "compaction_candidates": sum(1 for item in rows if item["recommended_action"] != "keep"),
                "delete_operations_planned": 0,
                "advisory_only": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("evidence_storage_report", report, agent="EvidenceStorageOptimizer")
        return report
