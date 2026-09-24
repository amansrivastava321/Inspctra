"""
test_profile_manager.py - Tests for CLI audit profile management.
"""

from pathlib import Path

from qa_ai.cli.profile_manager import ProfileManager
from qa_ai.orchestration.workflow_engine import WorkflowPhase
from qa_ai.runtime.execution_context import Platform


class TestProfileManager:
    def test_lists_expected_profiles(self):
        config_dir = Path(__file__).resolve().parents[1] / "qa_ai" / "config"
        manager = ProfileManager(config_dir)

        profiles = manager.list_profiles()
        assert profiles == ["api", "flutter", "full_stack", "web"]

    def test_invalid_profile_is_handled_safely(self):
        config_dir = Path(__file__).resolve().parents[1] / "qa_ai" / "config"
        manager = ProfileManager(config_dir)

        assert manager.validate_profile("missing") is False
        assert manager.get_profile("missing") == {}
        assert manager.get_workflow_phases("missing") == []
        assert manager.get_platform("missing") == Platform.UNKNOWN

    def test_profile_phase_mapping_and_platform(self):
        config_dir = Path(__file__).resolve().parents[1] / "qa_ai" / "config"
        manager = ProfileManager(config_dir)

        phases = manager.get_workflow_phases("web")
        assert WorkflowPhase.DISCOVERY in phases
        assert WorkflowPhase.REPORTING in phases
        assert manager.get_platform("web") == Platform.WEB
