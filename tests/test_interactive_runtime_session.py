"""Tests for qa_ai.interactive_runtime.runtime_session.RuntimeSession."""
import json
import time
from pathlib import Path

import pytest

from qa_ai.interactive_runtime.runtime_session import RuntimeSession
from qa_ai.interactive_runtime.schemas import (
    ActionResult,
    ActionStatus,
    CapabilityGap,
    CapabilityStatus,
    FunctionCoverageItem,
    FunctionStatus,
    RuntimeEvidence,
    UIAction,
    VerificationResult,
    VerificationStatus,
)


def _make_session(**kwargs) -> RuntimeSession:
    defaults = dict(
        app_name="TestApp",
        app_type="flutter_web",
        target_path="/tmp/testapp",
        launch_command="flutter run",
    )
    defaults.update(kwargs)
    return RuntimeSession(**defaults)


def _make_action_result(status: ActionStatus = ActionStatus.EXECUTED, shot_before=None, shot_after=None) -> ActionResult:
    action = UIAction(action_type="click", description="Click button")
    return ActionResult(
        action=action,
        status=status,
        screenshot_before=shot_before,
        screenshot_after=shot_after,
    )


class TestRuntimeSessionLifecycle:
    def test_start_records_timestamp(self):
        session = _make_session()
        assert session.started_at is None
        session.start()
        assert session.started_at is not None

    def test_end_records_timestamp(self):
        session = _make_session()
        session.start()
        session.end(verdict="passed", reason="all good")
        assert session.ended_at is not None
        assert session.final_verdict == "passed"
        assert session.verdict_reason == "all good"

    def test_duration_seconds_positive_after_start(self):
        session = _make_session()
        session.start()
        time.sleep(0.05)
        assert session.duration_seconds > 0

    def test_session_id_generated_automatically(self):
        s1 = _make_session()
        s2 = _make_session()
        assert s1.session_id != s2.session_id

    def test_custom_session_id_preserved(self):
        session = _make_session(session_id="my-fixed-id")
        assert session.session_id == "my-fixed-id"


class TestRuntimeSessionRecordActions:
    def test_record_action_appended(self):
        session = _make_session()
        session.start()
        result = _make_action_result()
        session.record_action(result)
        assert session.total_actions == 1

    def test_record_multiple_actions(self):
        session = _make_session()
        session.start()
        for _ in range(5):
            session.record_action(_make_action_result())
        assert session.total_actions == 5

    def test_screenshots_tracked_from_action(self):
        session = _make_session()
        session.start()
        result = _make_action_result(
            shot_before="before.png",
            shot_after="after.png",
        )
        session.record_action(result)
        assert "before.png" in session.screenshots_captured
        assert "after.png" in session.screenshots_captured

    def test_action_without_screenshots_no_error(self):
        session = _make_session()
        session.start()
        session.record_action(_make_action_result())
        assert len(session.screenshots_captured) == 0


class TestRuntimeSessionRecordVerification:
    def test_record_verification_appended(self):
        session = _make_session()
        session.start()
        vr = VerificationResult(step_id="step1", overall_status=VerificationStatus.PASSED)
        session.record_verification("step1", vr)
        assert len(session.verification_results) == 1

    def test_record_evidence_appended(self):
        session = _make_session()
        session.start()
        ev = RuntimeEvidence(step_id="step1", action_description="click login")
        session.record_evidence(ev)
        assert len(session.evidence) == 1


class TestRuntimeSessionCoverage:
    def _make_item(self, label: str, status: FunctionStatus) -> FunctionCoverageItem:
        item = FunctionCoverageItem(
            item_id=label,
            screen="Login",
            element_label=label,
            element_type="button",
            status=status,
        )
        return item

    def test_passed_function_recorded(self):
        session = _make_session()
        session.record_coverage(self._make_item("Login", FunctionStatus.PASSED))
        assert "Login" in session.passed_functions

    def test_failed_function_recorded(self):
        session = _make_session()
        session.record_coverage(self._make_item("Submit", FunctionStatus.FAILED))
        assert "Submit" in session.failed_functions

    def test_blocked_function_recorded(self):
        session = _make_session()
        session.record_coverage(self._make_item("Delete", FunctionStatus.BLOCKED))
        assert "Delete" in session.blocked_functions

    def test_skipped_function_recorded(self):
        session = _make_session()
        session.record_coverage(self._make_item("Export", FunctionStatus.SKIPPED))
        assert "Export" in session.skipped_functions

    def test_inconclusive_function_recorded(self):
        session = _make_session()
        session.record_coverage(self._make_item("AI Generate", FunctionStatus.INCONCLUSIVE))
        assert "AI Generate" in session.inconclusive_functions


class TestRuntimeSessionLogs:
    def test_add_logs_appended(self):
        session = _make_session()
        session.add_logs(["line 1", "line 2"])
        assert "line 1" in session.logs_captured
        assert "line 2" in session.logs_captured

    def test_add_capability_gap(self):
        session = _make_session()
        gap = CapabilityGap(
            capability="screen_observation_flutter_macos",
            status=CapabilityStatus.UNAVAILABLE,
            reason="Native macOS UI automation not implemented",
            todo="Add Accessibility API bridge",
        )
        session.add_capability_gap(gap)
        assert len(session.capability_gaps) == 1


class TestRuntimeSessionVerdict:
    def test_compute_verdict_failed_when_failed_functions_exist(self):
        session = _make_session()
        session.failed_functions.append("Login")
        session.end()
        assert session.final_verdict == "failed"

    def test_compute_verdict_blocked_when_only_blocked(self):
        session = _make_session()
        session.blocked_functions.append("Delete")
        session.end()
        assert session.final_verdict == "blocked"

    def test_compute_verdict_passed_when_passed_no_failed(self):
        session = _make_session()
        session.passed_functions.append("Login")
        session.end()
        assert session.final_verdict == "passed"

    def test_compute_verdict_inconclusive_fallthrough(self):
        session = _make_session()
        session.inconclusive_functions.append("Generate")
        session.end()
        assert session.final_verdict == "inconclusive"

    def test_explicit_verdict_overrides_compute(self):
        session = _make_session()
        session.failed_functions.append("Login")
        session.end(verdict="blocked", reason="permission denied")
        assert session.final_verdict == "blocked"


class TestRuntimeSessionPersistence:
    def test_save_writes_json_file(self, tmp_path):
        session = _make_session()
        session.start()
        session.end(verdict="passed")
        path = session.save(output_dir=str(tmp_path))
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["app_name"] == "TestApp"
        assert data["final_verdict"] == "passed"

    def test_saved_json_includes_functions(self, tmp_path):
        session = _make_session()
        session.start()
        session.passed_functions.append("Login")
        session.failed_functions.append("Register")
        session.end()
        path = session.save(output_dir=str(tmp_path))
        data = json.loads(path.read_text())
        assert "Login" in data["passed_functions"]
        assert "Register" in data["failed_functions"]

    def test_saved_json_includes_capability_gaps(self, tmp_path):
        session = _make_session()
        session.start()
        session.add_capability_gap(CapabilityGap(
            capability="native_ui",
            reason="not implemented",
            todo="add later",
        ))
        session.end()
        path = session.save(output_dir=str(tmp_path))
        data = json.loads(path.read_text())
        assert len(data["capability_gaps"]) == 1
        assert data["capability_gaps"][0]["capability"] == "native_ui"
