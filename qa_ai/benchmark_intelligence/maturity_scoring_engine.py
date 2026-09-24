"""
maturity_scoring_engine.py - Capability maturity scoring for QA-AI benchmarks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class MaturityScoringEngine:
    """Compute category maturity scores from benchmark + runtime evidence."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        scoring = self._load("benchmark_scoring_report")
        dataset = self._load("benchmark_dataset_registry")

        score_block = scoring.get("scores", {}) if isinstance(scoring.get("scores"), dict) else {}
        datasets = dataset.get("datasets", []) if isinstance(dataset.get("datasets"), list) else []
        category_counts = self._category_counts(datasets)

        evidence = {
            "web_audit_capability": self._weighted(score_block.get("finding_accuracy", 0.0), category_counts.get("web", 0)),
            "api_audit_capability": self._weighted(score_block.get("finding_accuracy", 0.0), category_counts.get("api", 0)),
            "runtime_audit_capability": self._weighted(score_block.get("runtime_validation_quality", 0.0), category_counts.get("web", 0) + category_counts.get("api", 0)),
            "remediation_capability": self._weighted(score_block.get("remediation_quality", 0.0), int(self.store.artifact_exists("remediation_runtime_summary"))),
            "cicd_capability": self._weighted(score_block.get("release_gate_accuracy", 0.0), int(self.store.artifact_exists("cicd_runtime_summary"))),
            "distributed_runtime_capability": self._weighted(score_block.get("replay_stability", 0.0), int(self.store.artifact_exists("distributed_runtime_report"))),
        }

        overall = round(sum(evidence.values()) / float(len(evidence) or 1), 4)
        level = "developing"
        if overall >= 0.8:
            level = "advanced"
        elif overall >= 0.6:
            level = "maturing"

        report = {
            "scores": {k: round(v, 4) for k, v in evidence.items()} | {"overall": overall},
            "maturity_level": level,
            "summary": {
                "dataset_categories": category_counts,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("benchmark_maturity_score", report, agent="BenchmarkIntelligence.MaturityScoringEngine")
        return report

    def _weighted(self, base_score: Any, evidence_count: int) -> float:
        try:
            score = float(base_score or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        confidence = 1.0 if evidence_count > 0 else 0.5
        return max(0.0, min(1.0, score * confidence))

    def _category_counts(self, datasets: List[Dict[str, Any]]) -> Dict[str, int]:
        counts = {
            "web": 0,
            "api": 0,
            "mobile": 0,
            "distributed": 0,
            "offline-first": 0,
            "sync-heavy": 0,
        }
        for row in datasets:
            if not isinstance(row, dict):
                continue
            categories = row.get("categories", []) if isinstance(row.get("categories"), list) else []
            for category in categories:
                key = str(category)
                if key in counts:
                    counts[key] += 1
        return counts

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
