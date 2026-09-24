"""
artifact_store.py - Central system memory for the Autonomous QA Platform.
All agents read/write structured artifacts here.
Features: save, load, list, version, provenance tracking, agent coordination.

BOUNDARY RULES:
  ✅ Used by: CLI/agent pipeline (qa_ai.runtime.*, qa_ai.agents.*, qa_ai.webapp.*)
  ❌ Must NOT be imported by: qa_ai.product_backend.*
     (product_backend uses ProductStorage/SQLite; use ArtifactIndex for filesystem reads)

KNOWN LIMITATIONS / BACKLOG:

  TODO(distributed-artifact-backend): ArtifactStore writes to the local filesystem.
    In distributed_runtime (actor_engine.py), each worker node has its own local fs.
    Artifacts written on worker A are invisible to workers B/C unless a shared
    volume or object-store backend is wired up. Future work: add a pluggable
    storage backend (e.g., S3, GCS, shared NFS) to ArtifactStore so distributed
    runs share a single artifact namespace. Until then, distributed runs may see
    stale/missing artifacts across nodes.

  TODO(benchmark-persistence): benchmark_intelligence stores cross-run history via
    BenchmarkHistoryTracker, which currently writes JSON files through ArtifactStore.
    This is per-run storage, not persistent across separate audit invocations.
    Future work: expose benchmark history through ProductStorage (SQLite) so the
    web UI can query trends without re-running agents. Alternatively, give
    BenchmarkHistoryTracker its own dedicated SQLite store.
"""

from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional, Dict, List
import json
import shutil
import logging

from qa_ai.artifacts.artifact_validator import ArtifactValidator

logger = logging.getLogger(__name__)


class ArtifactStore:
    """
    Central artifact repository for all agents in the QA platform.
    
    Every agent writes its output here. Every downstream agent reads from here.
    This is the system's shared memory. Nothing is stored in agent-local state.
    
    Structure:
        artifacts/
        ├── app_map.json              # Latest version (always overwritten)
        ├── test_plan.json            # Latest version
        ├── findings.json             # Latest version
        ├── execution_results.json    # Latest version
        ├── report.json               # Latest version
        ├── evidence/                 # Screenshots, logs, traces
        ├── reports/                  # Generated PDF/HTML reports
        └── versions/                 # Historical versions
            ├── app_map/
            │   ├── v1.0.0.json
            │   ├── v1.0.0_meta.json
            │   └── v1.1.0.json
            ├── test_plan/
            └── ...
    """
    
    def __init__(self, base_dir: Path = Path("artifacts")):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.validator = ArtifactValidator()
        
        # Subdirectories
        self.versions_dir = self.base_dir / "versions"
        self.versions_dir.mkdir(exist_ok=True)
        
        self.evidence_dir = self.base_dir / "evidence"
        self.evidence_dir.mkdir(exist_ok=True)
        
        self.reports_dir = self.base_dir / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        # In-memory index for fast lookups
        self._index: Dict[str, List[str]] = {}
        self._build_index()
    
    # ─── Core Operations ──────────────────────────────
    
    def save_artifact(
        self,
        artifact_name: str,
        data: Any,
        version: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        agent: Optional[str] = None,
    ) -> Path:
        """
        Save an artifact to the store.
        
        Args:
            artifact_name: Name of the artifact (e.g., 'app_map', 'test_plan')
            data: The data to store (dict, list, or serializable object)
            version: Optional version string. If None, saves as 'latest' only.
            metadata: Optional dict with extra provenance information
            agent: Name of the agent that produced this artifact
            
        Returns:
            Path to the saved artifact file
        """
        # Ensure .json extension
        if not artifact_name.endswith(".json"):
            artifact_name = f"{artifact_name}.json"

        validation = self.validator.validate_for_persistence(
            artifact_name=artifact_name,
            data=data,
            generated_by=agent,
        )
        if validation.warnings:
            for warning in validation.warnings:
                logger.warning(warning)
        if validation.errors:
            logger.debug("Artifact validation errors for %s: %s", artifact_name, validation.errors)
        data = validation.data
        
        # Build metadata
        full_metadata = {
            "produced_at": datetime.now(timezone.utc).isoformat(),
            "produced_by": agent or "unknown",
            "artifact_name": artifact_name,
            "contract_valid": validation.valid,
        }
        if metadata:
            full_metadata.update(metadata)
        
        # If data is a dict, inject metadata at top level
        if isinstance(data, dict):
            data = {**data, "_metadata": full_metadata}
        
        # Save latest version (always overwrite)
        latest_path = self.base_dir / artifact_name
        self._write_json(latest_path, data)
        
        # Save versioned copy if version specified
        if version:
            version_dir = self.versions_dir / artifact_name.replace(".json", "")
            version_dir.mkdir(exist_ok=True)
            
            version_path = version_dir / f"{version}.json"
            self._write_json(version_path, data)
            
            # Save metadata separately for version history
            meta_path = version_dir / f"{version}_meta.json"
            self._write_json(meta_path, full_metadata)
            
            # Update index
            base_name = artifact_name.replace(".json", "")
            if base_name not in self._index:
                self._index[base_name] = []
            if version not in self._index[base_name]:
                self._index[base_name].append(version)
                self._index[base_name].sort()
        
        logger.debug(f"Artifact saved: {artifact_name} (version: {version or 'latest'})")
        return latest_path
    
    def load_artifact(
        self,
        artifact_name: str,
        version: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Load an artifact from the store.
        
        Args:
            artifact_name: Name of the artifact (with or without .json)
            version: Specific version to load. If None, loads 'latest'.
            
        Returns:
            The artifact data, or None if not found
        """
        if not artifact_name.endswith(".json"):
            artifact_name = f"{artifact_name}.json"
        
        if version:
            file_path = (
                self.versions_dir /
                artifact_name.replace(".json", "") /
                f"{version}.json"
            )
        else:
            file_path = self.base_dir / artifact_name
        
        if not file_path.exists():
            logger.warning(f"Artifact not found: {artifact_name} (version: {version or 'latest'})")
            return None

        data = self._read_json(file_path)
        validation = self.validator.validate_for_consumption(
            artifact_name=artifact_name,
            data=data,
        )
        if validation.warnings:
            for warning in validation.warnings:
                logger.warning(warning)
        if validation.errors:
            logger.debug("Artifact consumption validation errors for %s: %s", artifact_name, validation.errors)
        return validation.data
    
    def artifact_exists(self, artifact_name: str, version: Optional[str] = None) -> bool:
        """Check if an artifact exists in the store."""
        if not artifact_name.endswith(".json"):
            artifact_name = f"{artifact_name}.json"
        
        if version:
            file_path = (
                self.versions_dir /
                artifact_name.replace(".json", "") /
                f"{version}.json"
            )
        else:
            file_path = self.base_dir / artifact_name
        
        return file_path.exists()
    
    def list_artifacts(self) -> List[str]:
        """List all artifacts currently in the store (latest versions only)."""
        artifacts = []
        for path in self.base_dir.glob("*.json"):
            if path.name not in ["_metadata.json"]:
                artifacts.append(path.name)
        return sorted(artifacts)
    
    def list_versions(self, artifact_name: str) -> List[str]:
        """List all versions of a specific artifact."""
        base_name = artifact_name.replace(".json", "")
        
        # Check in-memory index first
        if base_name in self._index:
            return self._index[base_name]
        
        # Fall back to filesystem scan
        version_dir = self.versions_dir / base_name
        if not version_dir.exists():
            return []
        
        versions = sorted([
            p.stem for p in version_dir.glob("*.json")
            if not p.stem.endswith("_meta")
        ])
        
        # Update index
        self._index[base_name] = versions
        return versions
    
    def get_artifact_metadata(
        self,
        artifact_name: str,
        version: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific artifact version.
        
        Args:
            artifact_name: Name of the artifact
            version: Version to get metadata for. If None, returns metadata from latest.
            
        Returns:
            Metadata dict, or None if not found
        """
        if not artifact_name.endswith(".json"):
            artifact_name = f"{artifact_name}.json"
        
        # Try versioned metadata first
        if version:
            meta_path = (
                self.versions_dir /
                artifact_name.replace(".json", "") /
                f"{version}_meta.json"
            )
            if meta_path.exists():
                return self._read_json(meta_path)
        
        # Try embedded metadata in the artifact
        data = self.load_artifact(artifact_name, version)
        if isinstance(data, dict) and "_metadata" in data:
            return data["_metadata"]
        
        return None
    
    # ─── Evidence Management ──────────────────────────
    
    def save_evidence(self, evidence_type: str, filename: str, data: bytes) -> Path:
        """
        Save binary evidence (screenshots, logs, traces).
        
        Args:
            evidence_type: Category (e.g., 'screenshots', 'logs', 'network')
            filename: Name of the evidence file
            data: Binary content
            
        Returns:
            Path to the saved evidence file
        """
        evidence_path = self.evidence_dir / evidence_type
        evidence_path.mkdir(exist_ok=True)
        
        file_path = evidence_path / filename
        file_path.write_bytes(data)
        
        logger.debug(f"Evidence saved: {evidence_type}/{filename}")
        return file_path
    
    def save_evidence_json(
        self,
        evidence_type: str,
        filename: str,
        data: Dict[str, Any],
    ) -> Path:
        """Save JSON evidence (API responses, test results)."""
        if not filename.endswith(".json"):
            filename = f"{filename}.json"
        
        evidence_path = self.evidence_dir / evidence_type
        evidence_path.mkdir(exist_ok=True)
        
        file_path = evidence_path / filename
        self._write_json(file_path, data)
        
        return file_path
    
    def load_evidence(self, evidence_type: str, filename: str) -> Optional[bytes]:
        """Load binary evidence."""
        file_path = self.evidence_dir / evidence_type / filename
        if not file_path.exists():
            return None
        return file_path.read_bytes()
    
    def list_evidence(self, evidence_type: Optional[str] = None) -> List[Path]:
        """List all evidence files, optionally filtered by type."""
        if evidence_type:
            search_path = self.evidence_dir / evidence_type
        else:
            search_path = self.evidence_dir
        
        if not search_path.exists():
            return []
        
        return sorted(search_path.rglob("*"))
    
    # ─── Report Management ────────────────────────────
    
    def save_report(self, filename: str, content: str) -> Path:
        """
        Save a generated report.
        
        Args:
            filename: Report filename (e.g., 'qa_audit_report.md')
            content: Report content
            
        Returns:
            Path to the saved report
        """
        file_path = self.reports_dir / filename
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"Report saved: {filename}")
        return file_path
    
    def load_report(self, filename: str) -> Optional[str]:
        """Load a generated report."""
        file_path = self.reports_dir / filename
        if not file_path.exists():
            return None
        return file_path.read_text(encoding="utf-8")
    
    def list_reports(self) -> List[str]:
        """List all generated reports."""
        return sorted([p.name for p in self.reports_dir.glob("*")])
    
    # ─── Convenience Methods for Agents ───────────────
    
    def get_latest_app_map(self) -> Optional[Dict[str, Any]]:
        """Convenience: load the latest app_map."""
        return self.load_artifact("app_map")
    
    def get_latest_test_plan(self) -> Optional[Dict[str, Any]]:
        """Convenience: load the latest test_plan."""
        return self.load_artifact("test_plan")
    
    def get_latest_findings(self) -> Optional[Dict[str, Any]]:
        """Convenience: load the latest findings."""
        return self.load_artifact("findings")
    
    def save_findings(self, findings: Dict[str, Any], agent: str = "unknown") -> Path:
        """Convenience: save findings with agent tracking."""
        return self.save_artifact(
            artifact_name="findings",
            data=findings,
            agent=agent,
        )
    
    def append_findings(self, new_findings: List[Dict[str, Any]], agent: str = "unknown") -> Path:
        """
        Append new findings to the existing findings artifact.
        Used when multiple agents contribute findings incrementally.
        """
        existing = self.load_artifact("findings") or {"findings": []}
        
        if isinstance(existing, dict) and "findings" in existing:
            existing["findings"].extend(new_findings)
        else:
            existing = {
                "findings": new_findings,
                "_metadata": {
                    "produced_at": datetime.now(timezone.utc).isoformat(),
                    "produced_by": agent,
                }
            }
        
        return self.save_artifact(
            artifact_name="findings",
            data=existing,
            agent=agent,
        )
    
    # ─── Store Management ─────────────────────────────
    
    def clear(self, keep_reports: bool = True):
        """
        Clear all artifacts from the store.
        
        Args:
            keep_reports: If True, preserves generated reports
        """
        for path in self.base_dir.glob("*.json"):
            path.unlink()
        
        # Clear versions
        if self.versions_dir.exists():
            shutil.rmtree(self.versions_dir)
            self.versions_dir.mkdir()
        
        # Clear evidence
        if self.evidence_dir.exists():
            shutil.rmtree(self.evidence_dir)
            self.evidence_dir.mkdir()
        
        if not keep_reports and self.reports_dir.exists():
            shutil.rmtree(self.reports_dir)
            self.reports_dir.mkdir()
        
        self._index = {}
        logger.info("Artifact store cleared")
    
    def get_store_size(self) -> Dict[str, int]:
        """Get total size of stored artifacts in bytes."""
        total = 0
        for path in self.base_dir.rglob("*"):
            if path.is_file():
                total += path.stat().st_size
        return {
            "total_bytes": total,
            "total_mb": round(total / (1024 * 1024), 2),
            "file_count": sum(1 for p in self.base_dir.rglob("*") if p.is_file()),
        }
    
    # ─── Internal Helpers ─────────────────────────────
    
    def _write_json(self, path: Path, data: Any):
        """Write data as JSON with consistent formatting."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    
    def _read_json(self, path: Path) -> Any:
        """Read JSON data from file."""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _build_index(self):
        """Build in-memory index of all versioned artifacts."""
        if not self.versions_dir.exists():
            return
        
        for artifact_dir in self.versions_dir.iterdir():
            if artifact_dir.is_dir():
                base_name = artifact_dir.name
                versions = sorted([
                    p.stem for p in artifact_dir.glob("*.json")
                    if not p.stem.endswith("_meta")
                ])
                if versions:
                    self._index[base_name] = versions


# ─── Global Instance ───────────────────────────────────

_default_store: Optional[ArtifactStore] = None


def get_artifact_store(base_dir: Path = Path("artifacts")) -> ArtifactStore:
    """Get or create the global artifact store instance."""
    global _default_store
    if _default_store is None:
        _default_store = ArtifactStore(base_dir)
    return _default_store


def reset_artifact_store():
    """Reset the global artifact store instance."""
    global _default_store
    _default_store = None
