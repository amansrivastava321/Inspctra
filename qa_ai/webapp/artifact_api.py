"""
artifact_api.py - Read-only adapter between ArtifactStore and FastAPI routes.

All data access goes through ArtifactStore so the web layer never touches
the filesystem directly. This keeps ArtifactStore as the single source of truth.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class ArtifactAPI:
    """
    Thin read-only adapter over ArtifactStore for HTTP routes.

    Safety guarantee: only reads. No write, delete, or mutation methods.
    """

    def __init__(self, artifacts_dir: str):
        self.artifacts_dir = Path(artifacts_dir)
        self._store = ArtifactStore(base_dir=self.artifacts_dir)

    # ── listing ───────────────────────────────────────────────────────────────

    def list_artifacts(self) -> List[Dict[str, Any]]:
        """Return all artifact names with basic metadata."""
        names = self._store.list_artifacts()
        result = []
        for name in names:
            meta = self._store.get_artifact_metadata(name.replace(".json", "")) or {}
            result.append({
                "name": name,
                "agent": meta.get("agent", ""),
                "saved_at": meta.get("saved_at", ""),
                "size_bytes": self._size(name),
            })
        return result

    def list_reports(self) -> List[str]:
        return self._store.list_reports()

    def list_evidence(self) -> List[str]:
        return [str(p.name) for p in self._store.list_evidence()]

    # ── single artifact ───────────────────────────────────────────────────────

    def get_artifact(self, name: str) -> Optional[Any]:
        """Load a single artifact by name (with or without .json)."""
        return self._store.load_artifact(name)

    def get_summary(self) -> Optional[Dict[str, Any]]:
        return self._store.load_artifact("audit_summary") or {}

    def get_findings(self) -> List[Dict[str, Any]]:
        data = self._store.get_latest_findings()
        if not data:
            return []
        findings = data.get("findings", [])
        return findings if isinstance(findings, list) else []

    def get_risk(self) -> Optional[Dict[str, Any]]:
        return self._store.load_artifact("risk_report") or self._store.load_artifact("risk_score") or {}

    def get_remediation(self) -> Optional[Dict[str, Any]]:
        return (
            self._store.load_artifact("remediation_runtime_summary")
            or self._store.load_artifact("remediation_summary")
            or {}
        )

    def get_benchmarks(self) -> Optional[Dict[str, Any]]:
        return (
            self._store.load_artifact("benchmark_intelligence_summary")
            or self._store.load_artifact("benchmark_summary")
            or {}
        )

    def get_cicd(self) -> Optional[Dict[str, Any]]:
        return (
            self._store.load_artifact("cicd_runtime_release_gate")
            or self._store.load_artifact("cicd_release_gate")
            or self._store.load_artifact("cicd_report")
            or {}
        )

    def get_self_optimization(self) -> Optional[Dict[str, Any]]:
        return self._store.load_artifact("self_optimization_plan") or {}

    def get_store_stats(self) -> Dict[str, Any]:
        sizes = self._store.get_store_size()
        return {
            "artifact_count": len(self._store.list_artifacts()),
            "report_count": len(self._store.list_reports()),
            "evidence_count": len(self._store.list_evidence()),
            "total_bytes": sizes.get("total", 0),
            "artifacts_dir": str(self.artifacts_dir),
        }

    # ── helpers ───────────────────────────────────────────────────────────────

    def _size(self, name: str) -> int:
        p = self.artifacts_dir / name
        try:
            return p.stat().st_size if p.exists() else 0
        except Exception:
            return 0
