"""
benchmark_history_tracker.py - Historical benchmark run index management.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class BenchmarkHistoryTracker:
    """Maintain benchmark history index for comparative intelligence."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        existing = self._load("benchmark_history_index")
        runs = existing.get("runs", []) if isinstance(existing.get("runs"), list) else []

        snapshot = self._snapshot()
        if all(str(row.get("run_id", "")) != str(snapshot.get("run_id", "")) for row in runs if isinstance(row, dict)):
            runs.append(snapshot)

        normalized = sorted([row for row in runs if isinstance(row, dict)], key=lambda item: str(item.get("captured_at", "")))

        report = {
            "runs": normalized,
            "summary": {
                "run_count": len(normalized),
                "latest_run_id": str(normalized[-1].get("run_id", "")) if normalized else "",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("benchmark_history_index", report, agent="BenchmarkIntelligence.HistoryTracker")
        return report

    def _snapshot(self) -> Dict[str, Any]:
        scoring = self._load("benchmark_scoring_report")
        maturity = self._load("benchmark_maturity_score")
        summary = self._load("benchmark_summary")
        scores = scoring.get("scores", {}) if isinstance(scoring.get("scores"), dict) else {}
        overall = float(scoring.get("overall_score", 0.0) or 0.0)
        maturity_level = str(maturity.get("maturity_level", "developing"))
        totals = summary.get("totals", {}) if isinstance(summary.get("totals"), dict) else {}

        digest_input = f"{overall:.4f}|{maturity_level}|{totals.get('findings_total',0)}|{totals.get('apps_total',0)}"
        digest = sha1(digest_input.encode("utf-8")).hexdigest()[:16]
        return {
            "run_id": f"BM-{digest}",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "scores": scores,
            "overall_score": round(overall, 4),
            "maturity_level": maturity_level,
            "totals": totals,
        }

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
