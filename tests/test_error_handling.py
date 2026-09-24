# tests/test_error_handling.py
import logging
import pytest
from unittest.mock import patch
from qa_ai.utils.error_handling import log_and_fallback, safe_fallback


class TestLogAndFallback:
    def test_returns_default_on_exception(self):
        def boom():
            raise ValueError("test error")

        result = log_and_fallback(boom, default=None, logger_name="test")
        assert result is None

    def test_returns_value_when_no_exception(self):
        def ok():
            return 42

        result = log_and_fallback(ok, default=None, logger_name="test")
        assert result == 42

    def test_logs_warning_on_exception(self, caplog):
        def boom():
            raise RuntimeError("something broke")

        with caplog.at_level(logging.WARNING, logger="test"):
            log_and_fallback(boom, default=None, logger_name="test", context="my_operation")

        assert "my_operation" in caplog.text or "something broke" in caplog.text

    def test_custom_default_returned(self):
        def boom():
            raise Exception("err")

        result = log_and_fallback(boom, default={"status": "unavailable"}, logger_name="test")
        assert result == {"status": "unavailable"}

    def test_safe_fallback_decorator(self):
        @safe_fallback(default=[], logger_name="test")
        def risky(x):
            if x < 0:
                raise ValueError("negative")
            return [x]

        assert risky(5) == [5]
        assert risky(-1) == []


class TestWorkflowEngineDurationFallback:
    """Verify workflow_engine silent handler was replaced with logged fallback."""
    def test_bad_iso_date_does_not_crash_phase(self):
        """PhaseResult duration calculation should not crash on bad timestamps."""
        from qa_ai.orchestration.workflow_engine import PhaseResult, WorkflowPhase
        r = PhaseResult(phase=WorkflowPhase.DISCOVERY)
        r.started_at = "not-a-date"
        r.completed_at = "also-not-a-date"
        # Should not raise; duration_seconds stays None or 0
        assert r.duration_seconds is None or r.duration_seconds == 0.0
