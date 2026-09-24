"""
workspace_manager.py - Local workspace isolation registry management.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from qa_ai.runtime.artifact_store import ArtifactStore


class WorkspaceManager:
    """Manage isolated local workspaces without external tenancy."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(self, workspace_name: str = "default", root_path: str | None = None) -> Dict[str, Any]:
        root = Path(root_path).expanduser().resolve() if root_path else self.store.base_dir.parent.resolve()
        workspace_root = root / "workspaces"
        workspace_root.mkdir(parents=True, exist_ok=True)

        workspace_dir = (workspace_root / workspace_name).resolve()
        workspace_dir.mkdir(parents=True, exist_ok=True)

        workspace_id = self._workspace_id(workspace_name)
        existing = self._load("workspace_registry")
        rows = existing.get("workspaces", []) if isinstance(existing.get("workspaces"), list) else []

        updated: List[Dict[str, Any]] = []
        found = False
        for row in rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("workspace_id", "")) == workspace_id:
                found = True
                updated.append(self._row(workspace_id, workspace_name, workspace_dir))
            else:
                updated.append(row)
        if not found:
            updated.append(self._row(workspace_id, workspace_name, workspace_dir))

        report = {
            "isolation_mode": "local_filesystem_only",
            "cloud_tenancy_enabled": False,
            "workspaces": sorted(updated, key=lambda item: str(item.get("workspace_id", ""))),
            "summary": {
                "workspace_count": len(updated),
                "active_workspace_id": workspace_id,
                "root_path": str(workspace_root),
                "advisory_only": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("workspace_registry", report, agent="Enterprise.WorkspaceManager")
        return report

    def _workspace_id(self, workspace_name: str) -> str:
        token = "".join(ch.lower() if ch.isalnum() else "_" for ch in workspace_name).strip("_") or "default"
        return f"WS-{token.upper()}"

    def _row(self, workspace_id: str, workspace_name: str, workspace_dir: Path) -> Dict[str, Any]:
        return {
            "workspace_id": workspace_id,
            "workspace_name": workspace_name,
            "workspace_path": str(workspace_dir),
            "artifact_path": str(self.store.base_dir.resolve()),
            "isolated": True,
            "local_only": True,
            "external_uploads_enabled": False,
        }

    def _load(self, artifact_name: str) -> Dict[str, Any]:
        payload = self.store.load_artifact(artifact_name)
        return payload if isinstance(payload, dict) else {}
