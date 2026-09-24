# tests/test_safe_subprocess.py
import os
import pytest
from unittest.mock import patch, MagicMock
from qa_ai.utils.safe_subprocess import (
    run_safe,
    CommandBlockedError,
    SubprocessTimeoutError,
    InvalidCwdError,
    _BLOCKED_EXECUTABLES,
    _STRIP_ENV_KEYS,
)


class TestAllowlist:
    def test_blocked_executable_raises(self):
        # Pick something from the blocked list
        blocked = next(iter(_BLOCKED_EXECUTABLES))
        with pytest.raises(CommandBlockedError, match=blocked):
            run_safe([blocked, "--version"])

    def test_allowed_executable_runs(self):
        # 'echo' should be allowed and work on macOS/Linux
        result = run_safe(["echo", "hello"], capture_output=True, text=True)
        assert "hello" in result.stdout

    def test_command_must_be_list(self):
        with pytest.raises(TypeError, match="list"):
            run_safe("echo hello")  # string not allowed


class TestEnvSanitization:
    def test_strips_secret_env_vars(self, monkeypatch):
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret123")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-abc")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            run_safe(["echo", "test"])
            _, kwargs = mock_run.call_args
            env = kwargs.get("env", {})
            assert "AWS_SECRET_ACCESS_KEY" not in env
            assert "OPENAI_API_KEY" not in env

    def test_normal_env_vars_pass_through(self, monkeypatch):
        monkeypatch.setenv("MY_NORMAL_VAR", "value123")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            run_safe(["echo", "test"])
            _, kwargs = mock_run.call_args
            env = kwargs.get("env", {})
            assert env.get("MY_NORMAL_VAR") == "value123"


class TestCwdValidation:
    def test_nonexistent_cwd_raises(self, tmp_path):
        nonexistent = str(tmp_path / "does_not_exist")
        with pytest.raises(InvalidCwdError, match="does not exist"):
            run_safe(["echo", "hi"], cwd=nonexistent)

    def test_valid_cwd_accepted(self, tmp_path):
        result = run_safe(["echo", "hi"], cwd=str(tmp_path), capture_output=True, text=True)
        assert result.returncode == 0


class TestTimeout:
    def test_timeout_raises_subprocess_timeout_error(self):
        import subprocess
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["sleep", "10"], timeout=0.1)
            with pytest.raises(SubprocessTimeoutError):
                run_safe(["sleep", "10"], timeout=0.1)


class TestAuditLogging:
    def test_audit_log_emitted(self, caplog):
        import logging
        with caplog.at_level(logging.INFO, logger="qa_ai.utils.safe_subprocess"):
            run_safe(["echo", "audit_test"], capture_output=True, text=True)
        assert any("echo" in r.message for r in caplog.records)
