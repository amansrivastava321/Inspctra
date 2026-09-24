"""
explorer_agent.py - Discovery Agent wrapper.
Provides a class-based interface to the discovery pipeline for use by the WorkflowEngine.
Delegates to generate_app_map() for the actual work.
"""

from pathlib import Path
from typing import Optional, Dict, Any

from qa_ai.agents.generate_app_map import generate_app_map
from qa_ai.runtime.artifact_store import ArtifactStore


class DiscoveryAgent:
    """
    Discovery Agent — scans a codebase and produces an app_map.

    This wraps the functional generate_app_map() to provide a
    class-based interface expected by the WorkflowEngine.
    """

    def __init__(
        self,
        app_path: Path,
        artifact_store: Optional[ArtifactStore] = None,
    ):
        self.app_path = Path(app_path)
        self.store = artifact_store

    def discover(self) -> Dict[str, Any]:
        """Run discovery and return the app_map dict."""
        return generate_app_map(
            app_path=self.app_path,
            artifact_store=self.store,
        )
