"""The environment phase must be able to plan every platform and environment."""

from __future__ import annotations

import pytest

from qa_ai.orchestration.environment_orchestrator import EnvironmentOrchestrator
from qa_ai.runtime.execution_context import Environment, Platform


@pytest.mark.parametrize("environment", list(Environment), ids=lambda e: e.name)
@pytest.mark.parametrize("platform", list(Platform), ids=lambda p: p.name)
def test_required_capabilities_are_defined_for_every_platform(platform: Platform, environment: Environment) -> None:
    required = EnvironmentOrchestrator()._get_required_capabilities(platform, environment)

    assert isinstance(required, list)


@pytest.mark.parametrize("platform", [Platform.ANDROID, Platform.IOS], ids=lambda p: p.name)
def test_flutter_targets_require_the_flutter_sdk(platform: Platform) -> None:
    assert "flutter" in EnvironmentOrchestrator()._get_required_capabilities(platform, Environment.LOCAL)
