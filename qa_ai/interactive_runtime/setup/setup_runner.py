"""
setup_runner.py - Execute a SetupPlan with user approval gating.

Rules:
- Never execute without approval.
- --yes only auto-approves can_auto_run=True actions.
- OS permission actions always require manual user steps.
- Dry-run: generate plan only, no execution.
- After install actions, re-run doctor to verify.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from qa_ai.interactive_runtime.setup.dependency_installer import DependencyInstaller
from qa_ai.interactive_runtime.setup.permission_assistant import PermissionAssistant
from qa_ai.interactive_runtime.setup.setup_models import (
    ActionRisk,
    ActionStatus,
    ActionType,
    SetupAction,
    SetupActionResult,
    SetupExecutionLog,
    SetupPlan,
)

logger = logging.getLogger(__name__)


class SetupRunner:
    """
    Execute setup actions from a SetupPlan.

    auto_approve_safe: if True, auto-approve can_auto_run=True actions (--yes flag).
    interactive: if False, skip all prompts (CI mode — only auto-approve safe).
    dry_run: if True, never execute anything.
    """

    def __init__(
        self,
        auto_approve_safe: bool = False,
        interactive: bool = True,
        dry_run: bool = False,
    ) -> None:
        self._auto_approve_safe = auto_approve_safe
        self._interactive = interactive
        self._dry_run = dry_run
        self._installer = DependencyInstaller(dry_run=dry_run)
        self._permission = PermissionAssistant()

    def run(self, plan: SetupPlan) -> SetupExecutionLog:
        """Execute all approved actions in the plan. Return execution log."""
        log = SetupExecutionLog(plan_id=plan.plan_id, dry_run=self._dry_run)
        results: List[SetupActionResult] = []

        for action in plan.actions:
            result = self._process_action(action)
            results.append(result)

        log.results = results
        log.completed_at = datetime.now(timezone.utc).isoformat()
        return log

    def _process_action(self, action: SetupAction) -> SetupActionResult:
        """Gate approval, then execute if approved."""
        if self._dry_run:
            return SetupActionResult(
                action_id=action.action_id,
                action_type=action.action_type,
                status=ActionStatus.SKIPPED,
                output=f"[DRY-RUN] Would execute: {action.title}",
            )

        approved = self._request_approval(action)
        if not approved:
            return SetupActionResult(
                action_id=action.action_id,
                action_type=action.action_type,
                status=ActionStatus.DENIED,
                output="User denied or skipped.",
            )

        # Special handling for OS permissions
        if action.action_type == ActionType.OPEN_SYSTEM_SETTINGS:
            return self._handle_open_settings(action)

        if action.action_type in (ActionType.SHOW_MANUAL_STEPS, ActionType.WAIT_FOR_USER,
                                   ActionType.CHECK_APPIUM_SERVER):
            self._show_manual_steps(action)
            return SetupActionResult(
                action_id=action.action_id,
                action_type=action.action_type,
                status=ActionStatus.COMPLETED,
                output="Manual steps displayed to user.",
            )

        if action.action_type == ActionType.VERIFY_PERMISSION:
            granted = self._permission.check_macos_accessibility()
            return SetupActionResult(
                action_id=action.action_id,
                action_type=action.action_type,
                status=ActionStatus.COMPLETED if granted else ActionStatus.FAILED,
                output="Permission granted." if granted else "Permission not granted.",
            )

        # Delegate to installer
        return self._installer.execute(action)

    def _request_approval(self, action: SetupAction) -> bool:
        """Return True if action is approved to run."""
        # Safety: never auto-approve OS permissions, destructive, or high-risk actions
        if action.risk_level == ActionRisk.REQUIRES_USER:
            return True  # User must act manually anyway; approve the "show/open" step

        if action.risk_level == ActionRisk.HIGH:
            # High risk: must always ask, never auto-approve
            if not self._interactive:
                logger.info("Non-interactive: skipping HIGH risk action '%s'", action.title)
                return False
            return self._ask_user(action)

        if action.can_auto_run and self._auto_approve_safe:
            logger.info("Auto-approving safe action: %s", action.title)
            return True

        if not self._interactive:
            logger.info("Non-interactive: skipping action '%s'", action.title)
            return False

        return self._ask_user(action)

    def _ask_user(self, action: SetupAction) -> bool:
        print(f"\n[SETUP ACTION] {action.title}")
        print(f"  Description : {action.description}")
        if action.command:
            print(f"  Command     : {' '.join(action.command)}")
        print(f"  Risk        : {action.risk_level.value}")
        if action.reason:
            print(f"  Reason      : {action.reason}")
        try:
            answer = input("  Approve? [y/N] ").strip().lower()
            return answer in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    def _handle_open_settings(self, action: SetupAction) -> SetupActionResult:
        """Open system settings and guide user to grant permission."""
        self._show_manual_steps(action)

        # Try to open settings automatically
        opened = False
        if action.command:
            result = self._installer.execute(action)
            opened = result.status == ActionStatus.COMPLETED

        if opened:
            print("[INFO] System settings opened. Follow the manual steps above.")
        else:
            print("[INFO] Could not open settings automatically. Follow manual steps.")

        # Wait for user then re-check
        granted = self._permission.recheck_macos_accessibility(interactive=self._interactive)

        return SetupActionResult(
            action_id=action.action_id,
            action_type=action.action_type,
            status=ActionStatus.COMPLETED if granted else ActionStatus.FAILED,
            output=(
                "Accessibility permission granted." if granted
                else "Accessibility permission still not granted."
            ),
        )

    def _show_manual_steps(self, action: SetupAction) -> None:
        if action.manual_steps:
            print(f"\n[MANUAL STEPS] {action.title}")
            for step in action.manual_steps:
                print(f"  {step}")
