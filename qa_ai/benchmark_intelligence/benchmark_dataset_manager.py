"""
benchmark_dataset_manager.py - Benchmark dataset catalog and categorization.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import json

from qa_ai.runtime.artifact_store import ArtifactStore


class BenchmarkDatasetManager:
    """Manage benchmark app metadata and category registry."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, sample_root: str = "sample_apps") -> Dict[str, Any]:
        root = Path(sample_root).expanduser().resolve()
        entries: List[Dict[str, Any]] = []

        if root.exists() and root.is_dir():
            for app_dir in sorted([item for item in root.iterdir() if item.is_dir()], key=lambda p: p.name):
                expected = self._expected_issue_count(app_dir)
                categories = self._categories(app_dir.name)
                entries.append(
                    {
                        "app_name": app_dir.name,
                        "app_path": str(app_dir),
                        "categories": categories,
                        "expected_issue_count": expected,
                        "sandbox_ready": True,
                    }
                )

        report = {
            "dataset_root": str(root),
            "datasets": entries,
            "summary": {
                "dataset_count": len(entries),
                "categories": self._category_counts(entries),
                "advisory_only": True,
                "external_uploads": False,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("benchmark_dataset_registry", report, agent="BenchmarkIntelligence.DatasetManager")
        return report

    def _categories(self, name: str) -> List[str]:
        lower = name.lower()
        out: List[str] = []
        if any(token in lower for token in ["react", "web", "dashboard", "ecommerce"]):
            out.append("web")
        if any(token in lower for token in ["api", "fastapi", "backend"]):
            out.append("api")
        if any(token in lower for token in ["flutter", "mobile", "android", "ios"]):
            out.append("mobile")
        if any(token in lower for token in ["distributed", "actor", "multi", "chaos"]):
            out.append("distributed")
        if any(token in lower for token in ["offline", "sync", "conflict"]):
            out.append("offline-first")
        if any(token in lower for token in ["sync", "conflict", "eventual"]):
            out.append("sync-heavy")
        return sorted(set(out or ["web"]))

    def _expected_issue_count(self, app_dir: Path) -> int:
        manifest = app_dir / "expected_issues.json"
        if not manifest.exists():
            return 0
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        issues = payload.get("issues", [])
        return len(issues) if isinstance(issues, list) else 0

    def _category_counts(self, entries: List[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {
            "web": 0,
            "api": 0,
            "mobile": 0,
            "distributed": 0,
            "offline-first": 0,
            "sync-heavy": 0,
        }
        for row in entries:
            categories = row.get("categories", []) if isinstance(row.get("categories"), list) else []
            for category in categories:
                key = str(category)
                if key in counts:
                    counts[key] += 1
        return counts
