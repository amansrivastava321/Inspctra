"""
artifact_cache.py - Advisory artifact cache analysis and planning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class ArtifactCacheAnalyzer:
    """Builds safe cache metadata and estimated hit opportunities."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        artifacts = self._artifact_files()
        entries: List[Dict[str, Any]] = []
        total_size = 0
        for path in artifacts:
            rel = str(path.relative_to(self.store.base_dir))
            stat = path.stat()
            total_size += int(stat.st_size)
            key = sha1(rel.encode("utf-8")).hexdigest()[:16]
            entries.append(
                {
                    "artifact": rel,
                    "cache_key": key,
                    "size_bytes": int(stat.st_size),
                    "mtime_epoch": float(stat.st_mtime),
                    "cacheable": True,
                }
            )

        report = {
            "entries": entries,
            "summary": {
                "artifact_count": len(entries),
                "total_size_bytes": int(total_size),
                "estimated_hit_ratio": round(min(0.95, 0.4 + (len(entries) / 200.0)), 3),
                "advisory_only": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("artifact_cache_report", report, agent="ArtifactCacheAnalyzer")
        return report

    def _artifact_files(self) -> List[Path]:
        return sorted(
            [
                path
                for path in self.store.base_dir.glob("*.json")
                if path.name not in {"_metadata.json"}
            ]
        )
