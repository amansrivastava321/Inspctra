"""
test_permission_manager.py - Tests for the PermissionManager.
Validates permission request creation, approval, denial, persistence.
"""

import pytest
from pathlib import Path

from qa_ai.runtime.permission_manager import (
    PermissionManager,
    PermissionRequest,
    PermissionRisk,
    PermissionStatus,
)


class TestPermissionRequest:
    def test_defaults(self):
        req = PermissionRequest(request_id="perm-0001", action="install_pip", description="Install pip")
        assert req.status == PermissionStatus.PENDING
        assert req.risk == PermissionRisk.MEDIUM
        assert req.resolved_at is None

    def test_to_dict(self):
        req = PermissionRequest(
            request_id="perm-0001",
            action="install_playwright",
            description="Install Playwright browsers",
            risk=PermissionRisk.HIGH,
            capability_name="playwright",
            command="playwright install chromium",
        )
        d = req.to_dict()
        assert d["request_id"] == "perm-0001"
        assert d["risk"] == "high"
        assert d["status"] == "pending"
        assert d["command"] == "playwright install chromium"


class TestPermissionManager:
    def test_create_request(self, tmp_dir):
        mgr = PermissionManager(artifact_dir=tmp_dir / "artifacts")
        req = mgr.create_request(
            action="install_playwright",
            description="Install Playwright browsers",
            risk=PermissionRisk.HIGH,
            capability_name="playwright",
        )
        assert req.request_id == "perm-0001"
        assert req.status == PermissionStatus.PENDING
        assert len(mgr.get_pending()) == 1

    def test_approve(self, tmp_dir):
        mgr = PermissionManager(artifact_dir=tmp_dir / "artifacts")
        req = mgr.create_request(action="install_pip", description="Install pip")
        assert mgr.approve(req.request_id) is True
        assert req.status == PermissionStatus.APPROVED
        assert req.resolved_at is not None
        assert len(mgr.get_pending()) == 0
        assert len(mgr.get_approved()) == 1

    def test_deny(self, tmp_dir):
        mgr = PermissionManager(artifact_dir=tmp_dir / "artifacts")
        req = mgr.create_request(action="install_docker", description="Install Docker")
        assert mgr.deny(req.request_id, reason="Not needed") is True
        assert req.status == PermissionStatus.DENIED
        assert req.reason == "Not needed"
        assert len(mgr.get_denied()) == 1

    def test_approve_nonexistent(self, tmp_dir):
        mgr = PermissionManager(artifact_dir=tmp_dir / "artifacts")
        assert mgr.approve("perm-9999") is False

    def test_deny_already_approved(self, tmp_dir):
        mgr = PermissionManager(artifact_dir=tmp_dir / "artifacts")
        req = mgr.create_request(action="test", description="test")
        mgr.approve(req.request_id)
        assert mgr.deny(req.request_id) is False  # Already resolved

    def test_get_request(self, tmp_dir):
        mgr = PermissionManager(artifact_dir=tmp_dir / "artifacts")
        req = mgr.create_request(action="test", description="test")
        assert mgr.get_request(req.request_id) is req
        assert mgr.get_request("perm-9999") is None

    def test_is_approved(self, tmp_dir):
        mgr = PermissionManager(artifact_dir=tmp_dir / "artifacts")
        req = mgr.create_request(action="install_playwright", description="Install PW", capability_name="playwright")
        assert mgr.is_approved("install_playwright") is False
        mgr.approve(req.request_id)
        assert mgr.is_approved("install_playwright") is True
        assert mgr.is_approved("install_playwright", capability_name="playwright") is True
        assert mgr.is_approved("install_playwright", capability_name="chromium") is False

    def test_action_summary(self, tmp_dir):
        mgr = PermissionManager(artifact_dir=tmp_dir / "artifacts")
        mgr.create_request(action="a", description="a", risk=PermissionRisk.LOW)
        mgr.create_request(action="b", description="b", risk=PermissionRisk.HIGH)
        req3 = mgr.create_request(action="c", description="c", risk=PermissionRisk.CRITICAL)
        mgr.approve(req3.request_id)

        summary = mgr.action_summary()
        assert summary["total"] == 3
        assert summary["pending"] == 2
        assert summary["approved"] == 1
        assert summary["by_risk"]["low"] == 1
        assert summary["by_risk"]["high"] == 1
        assert summary["by_risk"]["critical"] == 1

    def test_save_and_load(self, tmp_dir):
        artifact_dir = tmp_dir / "artifacts"
        mgr = PermissionManager(artifact_dir=artifact_dir)
        mgr.create_request(action="install_x", description="Install X", risk=PermissionRisk.HIGH)
        req2 = mgr.create_request(action="install_y", description="Install Y")
        mgr.approve(req2.request_id)
        mgr.save()

        mgr2 = PermissionManager(artifact_dir=artifact_dir)
        assert mgr2.load() is True
        assert len(mgr2.get_pending()) == 1
        assert len(mgr2.get_approved()) == 1
        assert mgr2.get_pending()[0].action == "install_x"
        assert mgr2.get_approved()[0].action == "install_y"

    def test_load_nonexistent(self, tmp_dir):
        mgr = PermissionManager(artifact_dir=tmp_dir / "artifacts")
        assert mgr.load() is False

    def test_clear(self, tmp_dir):
        mgr = PermissionManager(artifact_dir=tmp_dir / "artifacts")
        mgr.create_request(action="test", description="test")
        assert len(mgr.get_pending()) == 1
        mgr.clear()
        assert len(mgr.get_pending()) == 0

    def test_no_install_without_approval(self, tmp_dir):
        """Critical safety test: nothing should be approved by default."""
        mgr = PermissionManager(artifact_dir=tmp_dir / "artifacts")
        req = mgr.create_request(
            action="install_dangerous",
            description="Some dangerous install",
            risk=PermissionRisk.CRITICAL,
        )
        # Without explicit approval, is_approved must be False
        assert mgr.is_approved("install_dangerous") is False
        assert req.status == PermissionStatus.PENDING
