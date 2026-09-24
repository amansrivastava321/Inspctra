"""
finding_deduplication_engine.py - Cluster duplicate findings across current/history/benchmarks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from qa_ai.runtime.artifact_store import ArtifactStore


class FindingDeduplicationEngine:
    """Detect duplicate and near-duplicate findings to reduce noise."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self) -> Dict[str, Any]:
        current = self._current_findings()
        historical = self._historical_findings()
        benchmark = self._benchmark_findings()

        merged = [
            *[("current", row) for row in current],
            *[("historical", row) for row in historical],
            *[("benchmark", row) for row in benchmark],
        ]

        clusters: Dict[str, Dict[str, Any]] = {}
        for source, finding in merged:
            key = self._key(finding)
            bucket = clusters.setdefault(
                key,
                {
                    "cluster_id": f"CL-{len(clusters) + 1:04d}",
                    "signature": key,
                    "sources": set(),
                    "findings": [],
                },
            )
            bucket["sources"].add(source)
            bucket["findings"].append(finding)

        rows = []
        duplicate_clusters = 0
        for row in clusters.values():
            count = len(row["findings"])
            if count > 1:
                duplicate_clusters += 1
            rows.append(
                {
                    "cluster_id": row["cluster_id"],
                    "signature": row["signature"],
                    "sources": sorted(list(row["sources"])),
                    "finding_count": count,
                    "representative": row["findings"][0] if row["findings"] else {},
                }
            )

        report = {
            "advisory_only": True,
            "clusters": sorted(rows, key=lambda item: int(item.get("finding_count", 0)), reverse=True),
            "summary": {
                "current_findings": len(current),
                "historical_findings": len(historical),
                "benchmark_findings": len(benchmark),
                "cluster_count": len(rows),
                "duplicate_clusters": duplicate_clusters,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "source_artifacts": [
                "correlated_findings.json",
                "audit_memory_index.json",
                "benchmark_summary.json",
            ],
        }
        self.store.save_artifact("finding_deduplication_report", report, agent="SelfOptimization.FindingDeduplicationEngine")
        return report

    def _current_findings(self) -> List[Dict[str, Any]]:
        rows = self._load("correlated_findings").get("findings", [])
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def _historical_findings(self) -> List[Dict[str, Any]]:
        memory = self._load("audit_memory_index")
        runs = memory.get("runs", []) if isinstance(memory.get("runs"), list) else []
        out: List[Dict[str, Any]] = []
        for run in runs[-5:]:
            if not isinstance(run, dict):
                continue
            source = run.get("source", {}) if isinstance(run.get("source"), dict) else {}
            # memory is summary-level; encode recurring risk signal as pseudo-finding with deterministic source
            out.append(
                {
                    "id": str(run.get("memory_id", "")),
                    "title": "historical_findings_signal",
                    "category": "historical",
                    "target": "memory",
                    "description": f"findings={source.get('findings',0)} fp={source.get('false_positives',0)}",
                }
            )
        return out

    def _benchmark_findings(self) -> List[Dict[str, Any]]:
        summary = self._load("benchmark_summary")
        apps = summary.get("apps", []) if isinstance(summary.get("apps"), list) else []
        out: List[Dict[str, Any]] = []
        for app in apps:
            if not isinstance(app, dict):
                continue
            findings = app.get("findings", []) if isinstance(app.get("findings"), list) else []
            for finding in findings:
                if isinstance(finding, dict):
                    out.append(finding)
        return out

    def _key(self, finding: Dict[str, Any]) -> str:
        title = str(finding.get("title", "")).strip().lower()
        category = str(finding.get("category", "")).strip().lower()
        target = str(finding.get("target", finding.get("file_path", ""))).strip().lower()
        if not title and not target:
            title = str(finding.get("id", "unknown")).lower()
        return "|".join([title, category, target])

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
