"""Tests for qa_ai.interactive_runtime.app_launcher.AppLauncher."""
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from qa_ai.interactive_runtime.app_launcher import AppLauncher, LaunchResult


class TestAppLauncherDryRun:
    def test_dry_run_does_not_start_process(self):
        launcher = AppLauncher()
        result = launcher.launch(
            app_name="TestApp",
            launch_command="flutter run -d chrome",
            working_dir=".",
            dry_run=True,
        )
        assert result.status == "dry_run"
        assert result.pid is None
        assert result.process is None

    def test_dry_run_returns_working_dir(self, tmp_path):
        launcher = AppLauncher()
        result = launcher.launch(
            app_name="TestApp",
            launch_command="echo hello",
            working_dir=str(tmp_path),
            dry_run=True,
        )
        assert result.status == "dry_run"
        assert str(tmp_path) in result.working_dir


class TestAppLauncherInvalidDirectory:
    def test_missing_working_dir_returns_failed(self):
        launcher = AppLauncher()
        result = launcher.launch(
            app_name="TestApp",
            launch_command="echo hi",
            working_dir="/this/does/not/exist/at/all",
        )
        assert result.status == "failed"
        assert result.failure_reason is not None
        assert "not found" in result.failure_reason.lower()

    def test_missing_dir_has_no_pid(self):
        launcher = AppLauncher()
        result = launcher.launch(
            app_name="TestApp",
            launch_command="echo hi",
            working_dir="/nonexistent/path",
        )
        assert result.pid is None


class TestAppLauncherSuccessfulLaunch:
    def test_successful_long_running_process_is_running(self, tmp_path):
        launcher = AppLauncher()
        with patch("time.sleep"):  # skip the 1.5s startup pause
            with patch.object(subprocess.Popen, "poll", return_value=None):
                with patch("subprocess.Popen") as mock_popen:
                    mock_proc = MagicMock()
                    mock_proc.pid = 12345
                    mock_proc.poll.return_value = None
                    mock_popen.return_value = mock_proc
                    result = launcher.launch(
                        app_name="TestApp",
                        launch_command="sleep 999",
                        working_dir=str(tmp_path),
                    )
        assert result.status == "running"
        assert result.pid == 12345

    def test_immediate_exit_returns_failed(self, tmp_path):
        launcher = AppLauncher()
        with patch("time.sleep"):
            with patch("subprocess.Popen") as mock_popen:
                mock_proc = MagicMock()
                mock_proc.pid = 9999
                mock_proc.poll.return_value = 1  # exited
                mock_proc.stderr.read.return_value = "some error"
                mock_popen.return_value = mock_proc
                result = launcher.launch(
                    app_name="TestApp",
                    launch_command="false",
                    working_dir=str(tmp_path),
                )
        assert result.status == "failed"
        assert result.failure_reason is not None


class TestAppLauncherReadiness:
    def test_readiness_confirmed_when_url_responds(self, tmp_path):
        launcher = AppLauncher()
        with patch("time.sleep"):
            with patch("subprocess.Popen") as mock_popen:
                mock_proc = MagicMock()
                mock_proc.pid = 1111
                mock_proc.poll.return_value = None
                mock_popen.return_value = mock_proc
                with patch.object(AppLauncher, "_wait_for_readiness", return_value=True):
                    result = launcher.launch(
                        app_name="TestApp",
                        launch_command="serve",
                        working_dir=str(tmp_path),
                        readiness_url="http://localhost:3000",
                        readiness_timeout=5,
                    )
        assert result.readiness_confirmed is True

    def test_readiness_timeout_returns_timed_out(self, tmp_path):
        launcher = AppLauncher()
        with patch("time.sleep"):
            with patch("subprocess.Popen") as mock_popen:
                mock_proc = MagicMock()
                mock_proc.pid = 2222
                mock_proc.poll.return_value = None
                mock_popen.return_value = mock_proc
                with patch.object(AppLauncher, "_wait_for_readiness", return_value=False):
                    result = launcher.launch(
                        app_name="TestApp",
                        launch_command="serve",
                        working_dir=str(tmp_path),
                        readiness_url="http://localhost:3000",
                        readiness_timeout=1,
                    )
        assert result.status == "timed_out"
        assert result.readiness_confirmed is False

    def test_no_readiness_url_auto_confirms(self, tmp_path):
        launcher = AppLauncher()
        with patch("time.sleep"):
            with patch("subprocess.Popen") as mock_popen:
                mock_proc = MagicMock()
                mock_proc.pid = 3333
                mock_proc.poll.return_value = None
                mock_popen.return_value = mock_proc
                result = launcher.launch(
                    app_name="TestApp",
                    launch_command="echo running",
                    working_dir=str(tmp_path),
                )
        assert result.readiness_confirmed is True


class TestAppLauncherCommandParse:
    def test_parse_command_splits_correctly(self):
        parts = AppLauncher._parse_command("flutter run -d chrome --web-port 3000")
        assert parts == ["flutter", "run", "-d", "chrome", "--web-port", "3000"]

    def test_parse_command_handles_quoted_args(self):
        parts = AppLauncher._parse_command('python -c "print(1)"')
        assert parts == ["python", "-c", "print(1)"]


class TestAppLauncherStop:
    def test_stop_terminates_process(self):
        launcher = AppLauncher()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 5555
        launcher._process = mock_proc
        launcher.stop()
        mock_proc.terminate.assert_called_once()

    def test_stop_no_op_when_no_process(self):
        launcher = AppLauncher()
        launcher.stop()  # should not raise

    def test_is_running_false_when_no_process(self):
        launcher = AppLauncher()
        assert launcher.is_running() is False


class TestLaunchResultDict:
    def test_to_dict_contains_key_fields(self):
        result = LaunchResult(
            app_name="MyApp",
            launch_command="echo hi",
            working_dir="/tmp",
            status="running",
            pid=1234,
        )
        d = result.to_dict()
        assert d["app_name"] == "MyApp"
        assert d["status"] == "running"
        assert d["pid"] == 1234
