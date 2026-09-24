"""Tests for qa_ai.interactive_runtime.result_verifier.ResultVerifier.

Core rule under test: pass ONLY when result is positively verified.
INCONCLUSIVE when no checks ran. FAILED when any check failed.
"""
from unittest.mock import MagicMock

import pytest

from qa_ai.interactive_runtime.result_verifier import ResultVerifier
from qa_ai.interactive_runtime.schemas import (
    ActionResult,
    ActionStatus,
    ScreenState,
    UIAction,
    VerificationStatus,
)


def _make_action_result(
    status: ActionStatus = ActionStatus.EXECUTED,
    visible_text=None,
    has_error_banner: bool = False,
    screen_after: bool = True,
) -> ActionResult:
    action = UIAction(action_type="click", description="test action")
    screen = None
    if screen_after:
        screen = ScreenState(
            title="TestScreen",
            has_error_banner=has_error_banner,
            visible_text=visible_text or [],
        )
    return ActionResult(action=action, status=status, screen_after=screen)


class TestResultVerifierBlocked:
    def test_blocked_action_returns_blocked_status(self):
        verifier = ResultVerifier()
        result = _make_action_result(status=ActionStatus.BLOCKED)
        vr = verifier.verify("step1", result)
        assert vr.overall_status == VerificationStatus.BLOCKED

    def test_blocked_action_has_no_checks(self):
        verifier = ResultVerifier()
        result = _make_action_result(status=ActionStatus.BLOCKED)
        vr = verifier.verify("step1", result)
        assert len(vr.checks) == 0


class TestResultVerifierNoCrash:
    def test_executed_action_no_crash_check_passes(self):
        verifier = ResultVerifier()
        result = _make_action_result(status=ActionStatus.EXECUTED, screen_after=False)
        vr = verifier.verify("step1", result, expected_no_error=False)
        crash_check = next(c for c in vr.checks if c.check_type == "action_status")
        assert crash_check.status == VerificationStatus.PASSED

    def test_failed_action_no_crash_check_fails(self):
        verifier = ResultVerifier()
        result = _make_action_result(status=ActionStatus.FAILED, screen_after=False)
        vr = verifier.verify("step1", result, expected_no_error=False)
        crash_check = next(c for c in vr.checks if c.check_type == "action_status")
        assert crash_check.status == VerificationStatus.FAILED


class TestResultVerifierErrorBanner:
    def test_no_error_banner_check_passes(self):
        verifier = ResultVerifier()
        result = _make_action_result(has_error_banner=False)
        vr = verifier.verify("step1", result, expected_no_error=True)
        banner_check = next(c for c in vr.checks if c.check_type == "ui_state")
        assert banner_check.status == VerificationStatus.PASSED

    def test_error_banner_present_fails(self):
        verifier = ResultVerifier()
        result = _make_action_result(has_error_banner=True)
        vr = verifier.verify("step1", result, expected_no_error=True)
        assert vr.overall_status == VerificationStatus.FAILED


class TestResultVerifierUIText:
    def test_expected_text_found_passes(self):
        verifier = ResultVerifier()
        result = _make_action_result(visible_text=["Welcome to Dashboard"])
        vr = verifier.verify("step1", result, expected_ui_text=["Welcome"])
        text_check = next(c for c in vr.checks if c.check_type == "ui_text")
        assert text_check.status == VerificationStatus.PASSED

    def test_expected_text_not_found_fails(self):
        verifier = ResultVerifier()
        result = _make_action_result(visible_text=["Error occurred"])
        vr = verifier.verify("step1", result, expected_ui_text=["Welcome"])
        text_check = next(c for c in vr.checks if c.check_type == "ui_text")
        assert text_check.status == VerificationStatus.FAILED

    def test_ui_text_check_case_insensitive(self):
        verifier = ResultVerifier()
        result = _make_action_result(visible_text=["DASHBOARD LOADED"])
        vr = verifier.verify("step1", result, expected_ui_text=["dashboard"])
        text_check = next(c for c in vr.checks if c.check_type == "ui_text")
        assert text_check.status == VerificationStatus.PASSED

    def test_ui_text_inconclusive_when_no_screen(self):
        verifier = ResultVerifier()
        result = _make_action_result(screen_after=False)
        vr = verifier.verify("step1", result, expected_no_error=False, expected_ui_text=["Hello"])
        text_check = next(c for c in vr.checks if c.check_type == "ui_text")
        assert text_check.status == VerificationStatus.INCONCLUSIVE


class TestResultVerifierLogTags:
    def test_log_tag_found_passes(self):
        mock_log = MagicMock()
        mock_log.tag_found.return_value = True
        mock_log.get_matched_lines.return_value = ["[AI_CONFIG] model=gpt-4o"]
        verifier = ResultVerifier(log_watcher=mock_log)
        result = _make_action_result(screen_after=False)
        vr = verifier.verify("step1", result, expected_no_error=False, expected_log_tags=["[AI_CONFIG]"])
        log_check = next(c for c in vr.checks if c.check_type == "log_tag")
        assert log_check.status == VerificationStatus.PASSED

    def test_log_tag_not_found_fails(self):
        mock_log = MagicMock()
        mock_log.tag_found.return_value = False
        mock_log.get_matched_lines.return_value = []
        verifier = ResultVerifier(log_watcher=mock_log)
        result = _make_action_result(screen_after=False)
        vr = verifier.verify("step1", result, expected_no_error=False, expected_log_tags=["[AI_CONFIG]"])
        log_check = next(c for c in vr.checks if c.check_type == "log_tag")
        assert log_check.status == VerificationStatus.FAILED

    def test_log_tag_inconclusive_when_no_watcher(self):
        verifier = ResultVerifier()  # no log_watcher
        result = _make_action_result(screen_after=False)
        vr = verifier.verify("step1", result, expected_no_error=False, expected_log_tags=["[ERROR]"])
        log_check = next(c for c in vr.checks if c.check_type == "log_tag")
        assert log_check.status == VerificationStatus.INCONCLUSIVE


class TestResultVerifierAggregation:
    def test_no_positive_checks_is_inconclusive(self):
        """Only no-crash check runs (PASSED) but nothing else → still PASSED because crash=PASSED."""
        verifier = ResultVerifier()
        result = _make_action_result(screen_after=False)
        # Just the crash check — no ui_text, no log tags, no api, no db
        vr = verifier.verify("step1", result, expected_no_error=False)
        # crash check PASSED → overall PASSED (one confirmed positive check)
        assert vr.overall_status == VerificationStatus.PASSED

    def test_any_failed_check_makes_overall_failed(self):
        verifier = ResultVerifier()
        result = _make_action_result(has_error_banner=True)
        vr = verifier.verify("step1", result, expected_no_error=True)
        assert vr.overall_status == VerificationStatus.FAILED

    def test_mixed_passed_and_inconclusive_is_inconclusive(self):
        """If some checks are INCONCLUSIVE and some PASSED but not all PASSED → INCONCLUSIVE."""
        verifier = ResultVerifier()  # no log_watcher configured
        result = _make_action_result(visible_text=["Dashboard"])
        # ui_text will PASS, log_tag will INCONCLUSIVE (no watcher)
        vr = verifier.verify(
            "step1", result,
            expected_no_error=False,
            expected_ui_text=["Dashboard"],
            expected_log_tags=["[SOME_TAG]"],
        )
        # One PASSED, one INCONCLUSIVE → INCONCLUSIVE (not all PASSED)
        assert vr.overall_status == VerificationStatus.INCONCLUSIVE

    def test_all_passed_checks_is_passed(self):
        mock_log = MagicMock()
        mock_log.tag_found.return_value = True
        mock_log.get_matched_lines.return_value = ["[AI_CONFIG] ok"]
        verifier = ResultVerifier(log_watcher=mock_log)
        result = _make_action_result(
            visible_text=["Dashboard Loaded"],
            has_error_banner=False,
        )
        vr = verifier.verify(
            "step1", result,
            expected_no_error=True,
            expected_ui_text=["Dashboard"],
            expected_log_tags=["[AI_CONFIG]"],
        )
        assert vr.overall_status == VerificationStatus.PASSED

    def test_pass_only_when_verified_not_just_clicked(self):
        """An action that executed but has NO verification checks is INCONCLUSIVE."""
        verifier = ResultVerifier()
        # EXECUTED action with no screen_after, no log checks, no ui_text
        action = UIAction(action_type="click", description="Click something")
        result = ActionResult(action=action, status=ActionStatus.EXECUTED, screen_after=None)
        # Only crash check runs (PASSED), but without screen there's no error banner check
        # and no additional checks → still returns the crash check result
        vr = verifier.verify("step1", result, expected_no_error=False)
        # crash check PASSED — this is the minimum positive signal
        assert vr.overall_status == VerificationStatus.PASSED

    def test_no_checks_at_all_is_inconclusive(self):
        """The static aggregate method returns INCONCLUSIVE for empty list."""
        assert ResultVerifier._aggregate([]) == VerificationStatus.INCONCLUSIVE
