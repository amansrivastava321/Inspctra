"""
profile_manager.py - Audit profile selection and phase mapping.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from qa_ai.cli.config_loader import ConfigLoader
from qa_ai.orchestration.workflow_engine import WorkflowPhase
from qa_ai.runtime.execution_context import Platform


class ProfileManager:
    """Load and validate named CLI audit profiles."""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.loader = ConfigLoader(config_dir / "default_profiles.yaml")
        self._index = self.loader.load()

    def list_profiles(self) -> List[str]:
        profiles = self._index.get("profiles", {})
        if not isinstance(profiles, dict):
            return []
        return sorted(str(name) for name in profiles.keys())

    def get_profile(self, name: str) -> Dict[str, Any]:
        profiles = self._index.get("profiles", {})
        if not isinstance(profiles, dict):
            return {}
        config_file = profiles.get(name)
        if not isinstance(config_file, str):
            return {}
        loaded = self.loader.load(self.config_dir / config_file)
        return loaded if isinstance(loaded, dict) else {}

    def validate_profile(self, name: str) -> bool:
        return bool(self.get_profile(name))

    def get_workflow_phases(self, name: str) -> List[WorkflowPhase]:
        profile = self.get_profile(name)
        raw_phases = profile.get("phases", [])
        if not isinstance(raw_phases, list):
            return []
        phases: List[WorkflowPhase] = []
        for phase_name in raw_phases:
            if not isinstance(phase_name, str):
                continue
            try:
                phases.append(WorkflowPhase(phase_name))
            except ValueError:
                continue
        return phases

    def get_platform(self, name: str) -> Platform:
        profile = self.get_profile(name)
        raw_platform = profile.get("platform", "unknown")
        if not isinstance(raw_platform, str):
            return Platform.UNKNOWN
        try:
            return Platform(raw_platform)
        except ValueError:
            return Platform.UNKNOWN
