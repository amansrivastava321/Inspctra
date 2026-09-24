"""
false_positive_tracker.py - False-positive and noise tracking for benchmarks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class FalsePositiveTracker:
    """Track false positives, unverifiable findings, and noisy detections."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        metrics = self._load("benchmark_metrics")
        benchmark_summary = self._load("benchmark_summary")

        per_app = metrics.get("per_app", []) if isinstance(metrics.get("per_app"), list) else []
        rows: List[Dict[str, Any]] = []
        total_fp = 0
        total_noisy = 0
        total_unverifiable = 0

        apps = benchmark_summary.get("apps", []) if isinstance(benchmark_summary.get("apps"), list) else []
        app_lookup = {str(item.get("app_name", "")): item for item in apps if isinstance(item, dict)}

        for app in per_app:
            if not isinstance(app, dict):
                continue
            name = str(app.get("app_name", "unknown"))
            fp = self._safe_int(app.get("false_positives"))
            duplicates = self._safe_int(app.get("duplicate_findings"))
            app_summary = app_lookup.get(name, {})
            runtime_summary = app_summary.get("runtime_validation_summary", {}) if isinstance(app_summary.get("runtime_validation_summary"), dict) else {}
            unverifiable = self._safe_int(runtime_summary.get("unverifiable", 0))

            total_fp += fp
            total_noisy += duplicates
            total_unverifiable += unverifiable
            rows.append(
                {
                    "app_name": name,
                    "false_positives": fp,
                    "unverifiable_findings": unverifiable,
                    "noisy_findings": duplicates,
                }
            )

        report = {
            "per_app": rows,
            "summary": {
                "false_positives": total_fp,
                "unverifiable_findings": total_unverifiable,
                "noisy_findings": total_noisy,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("false_positive_report", report, agent="BenchmarkIntelligence.FalsePositiveTracker")
        return report

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
