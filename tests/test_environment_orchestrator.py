"""
test_environment_orchestrator.py - Tests for improved EnvironmentOrchestrator.
Validates test classification, readiness generation, and permission integration.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from qa_ai.orchestration.environment_orchestrator import (
    EnvironmentOrchestrator,
    ProvisionAction,
    ProvisionStatus,
    ProvisionStep,
    EnvironmentPlan,
    OrchestrationResult,
)
from qa_ai.runtime.capability_registry import (
    CapabilityRegistry,
    Capability,
    CapabilityStatus,
    ProvisionStrategy,
    EnvironmentCapabilities,
    DeviceInfo,
)
from qa_ai.runtime.execution_context import Platform, Environment


class TestTestClassification:
    def _make_orchestrator(self, capabilities):
        """Create an orchestrator with pre-set capabilities."""
        registry = MagicMock(spec=CapabilityRegistry)
        orch = EnvironmentOrchestrator(registry=registry)
        orch.capabilities = capabilities
        return orch

    def test_classify_full_ready(self):
        """Test that tests pass when all capabilities are available."""
        caps = EnvironmentCapabilities(
            capabilities={
                "python": Capability(name="python", category="runtime", status=CapabilityStatus.AVAILABLE),
                "playwright": Capability(name="playwright", category="tool", status=CapabilityStatus.AVAILABLE),
            }
        )
        orch = self._make_orchestrator(caps)

        test_plan = {
            "test_suites": {
                "functional": [
                    {"id": "T1", "title": "Test 1", "type": "functional", "tags": []},
                ],
            },
        }

        classified = orch.classify_tests(test_plan, Platform.WEB)
        assert "T1" in [t.get("id") for t in classified["full_ready"]]
        assert len(classified["blocked"]) == 0

    def test_classify_blocked(self):
        """Test that tests are blocked when xcode is not provisionable."""
        caps = EnvironmentCapabilities(
            capabilities={
                "xcode": Capability(
                    name="xcode",
                    category="tool",
                    status=CapabilityStatus.NOT_FOUND,
                    provision_strategy=ProvisionStrategy.NOT_PROVISIONABLE,
                ),
            }
        )
        orch = self._make_orchestrator(caps)

        test_plan = {
            "test_suites": {
                "functional": [
                    {"id": "T1", "title": "Test iOS", "type": "functional", "tags": []},
                ],
            },
        }

        classified = orch.classify_tests(test_plan, Platform.IOS)
        assert "T1" in [t.get("id") for t in classified["blocked"]]

    def test_classify_permission_required(self):
        """Test that tests need permission when capability is GUIDED provisionable."""
        caps = EnvironmentCapabilities(
            capabilities={
                "adb": Capability(
                    name="adb",
                    category="tool",
                    status=CapabilityStatus.NOT_FOUND,
                    provision_strategy=ProvisionStrategy.GUIDED,
                ),
            }
        )
        orch = self._make_orchestrator(caps)

        test_plan = {
            "test_suites": {
                "functional": [
                    {"id": "T1", "title": "Test Android", "type": "functional", "tags": []},
                ],
            },
        }

        classified = orch.classify_tests(test_plan, Platform.ANDROID)
        assert "T1" in [t.get("id") for t in classified["permission_required"]]

    def test_classify_partial_ready(self):
        """Test partial_ready when capability is AUTO provisionable."""
        caps = EnvironmentCapabilities(
            capabilities={
                "playwright": Capability(
                    name="playwright",
                    category="tool",
                    status=CapabilityStatus.NOT_FOUND,
                    provision_strategy=ProvisionStrategy.AUTO,
                ),
            }
        )
        orch = self._make_orchestrator(caps)

        test_plan = {
            "test_suites": {
                "functional": [
                    {"id": "T1", "title": "Web test", "type": "functional", "tags": []},
                ],
            },
        }

        classified = orch.classify_tests(test_plan, Platform.WEB)
        assert "T1" in [t.get("id") for t in classified["partial_ready"]]

    def test_classify_backend_always_ready(self):
        """Backend tests don't need special capabilities."""
        caps = EnvironmentCapabilities()
        orch = self._make_orchestrator(caps)

        test_plan = {
            "test_suites": {
                "functional": [
                    {"id": "T1", "title": "API test", "type": "functional", "tags": []},
                ],
            },
        }

        classified = orch.classify_tests(test_plan, Platform.BACKEND)
        assert "T1" in [t.get("id") for t in classified["full_ready"]]

    def test_classify_mixed(self):
        """Test a mix of test types across readiness categories."""
        caps = EnvironmentCapabilities(
            capabilities={
                "python": Capability(name="python", category="runtime", status=CapabilityStatus.AVAILABLE),
                "playwright": Capability(name="playwright", category="tool", status=CapabilityStatus.AVAILABLE),
            }
        )
        orch = self._make_orchestrator(caps)

        test_plan = {
            "test_suites": {
                "functional": [
                    {"id": "T1", "title": "Web test", "type": "functional", "tags": []},
                ],
                "performance": [
                    {"id": "T2", "title": "Perf test", "type": "performance", "tags": []},
                ],
            },
        }

        classified = orch.classify_tests(test_plan, Platform.WEB)
        all_ids = []
        for group in classified.values():
            all_ids.extend(t.get("id") for t in group)
        assert "T1" in all_ids
        assert "T2" in all_ids


class TestEnvironmentStatusGeneration:
    def test_generate_environment_status(self, tmp_dir):
        """Test that environment_status.json is generated."""
        registry = MagicMock(spec=CapabilityRegistry)
        registry.scan_all.return_value = EnvironmentCapabilities(
            capabilities={
                "python": Capability(name="python", category="runtime", status=CapabilityStatus.AVAILABLE, version="3.11.0"),
            }
        )
        orch = EnvironmentOrchestrator(registry=registry)

        artifact_dir = tmp_dir / "artifacts"
        status = orch.generate_environment_status(artifact_dir=artifact_dir)

        assert "capabilities" in status
        assert "android" in status
        assert "ios" in status
        assert "ci" in status
        assert "docker" in status

        path = artifact_dir / "environment_status.json"
        assert path.exists()

    def test_generate_execution_readiness(self, tmp_dir):
        """Test that execution_readiness.json is generated with test classification."""
        registry = MagicMock(spec=CapabilityRegistry)
        registry.scan_all.return_value = EnvironmentCapabilities(
            capabilities={
                "python": Capability(name="python", category="runtime", status=CapabilityStatus.AVAILABLE),
                "playwright": Capability(name="playwright", category="tool", status=CapabilityStatus.AVAILABLE),
            }
        )
        orch = EnvironmentOrchestrator(registry=registry)

        test_plan = {
            "test_suites": {
                "functional": [
                    {"id": "T1", "title": "Test 1", "type": "functional", "tags": []},
                ],
            },
        }

        artifact_dir = tmp_dir / "artifacts"
        readiness = orch.generate_execution_readiness(test_plan, Platform.WEB, artifact_dir=artifact_dir)

        assert readiness["platform"] == "web"
        assert readiness["total_tests"] == 1
        assert readiness["full_ready"] == 1

        path = artifact_dir / "execution_readiness.json"
        assert path.exists()

    def test_readiness_creates_permission_requests(self, tmp_dir):
        """Test that permission requests are created for GUIDED provisionable capabilities."""
        registry = MagicMock(spec=CapabilityRegistry)
        registry.scan_all.return_value = EnvironmentCapabilities(
            capabilities={
                "adb": Capability(
                    name="adb",
                    category="tool",
                    status=CapabilityStatus.NOT_FOUND,
                    provision_strategy=ProvisionStrategy.GUIDED,
                    provision_instructions="Install ADB",
                ),
            }
        )
        orch = EnvironmentOrchestrator(registry=registry)

        test_plan = {
            "test_suites": {
                "functional": [
                    {"id": "T1", "title": "Android test", "type": "functional", "tags": []},
                ],
            },
        }

        artifact_dir = tmp_dir / "artifacts"
        readiness = orch.generate_execution_readiness(test_plan, Platform.ANDROID, artifact_dir=artifact_dir)

        assert readiness["permission_required"] == 1
        assert readiness["permission_requests"]["total"] >= 1

        # Check permissions.json was saved
        assert (artifact_dir / "permissions.json").exists()


class TestEnvironmentPlan:
    def test_plan_to_dict(self):
        plan = EnvironmentPlan(
            target_platform=Platform.WEB,
            environment=Environment.LOCAL,
            is_ready=True,
            missing_capabilities=["playwright"],
            blocked_reasons=[],
        )
        d = plan.to_dict()
        assert d["target_platform"] == "web"
        assert d["is_ready"] is True

    def test_plan_properties(self):
        plan = EnvironmentPlan(
            target_platform=Platform.ANDROID,
            environment=Environment.LOCAL,
            blocked_reasons=["No macOS"],
            requires_user_action=["install adb"],
        )
        assert plan.is_blocked is True
        assert plan.needs_user is True


class TestOrchestrationResult:
    def test_result_to_dict(self):
        result = OrchestrationResult(
            success=True,
            platform=Platform.WEB,
            provisioned=["playwright"],
            total_steps=2,
            completed_steps=1,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["platform"] == "web"
