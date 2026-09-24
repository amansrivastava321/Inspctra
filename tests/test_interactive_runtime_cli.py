"""Tests for the `interactive-test` CLI command.

Verifies:
- --help works and mentions the command
- --dry-run validates the config without launching any process
- Invalid / missing config returns error code 1
- Config file is loaded and its fields are respected
- --no-permission is wired up (skips interactive prompts in CI mode)
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from qa_ai.cli.main import build_parser, main


# ── helpers ────────────────────────────────────────────────────────────────────

def _write_config(tmp_path: Path, **overrides) -> Path:
    """Write a minimal valid interactive_runtime.yaml config file."""
    cfg = {
        "app_name": "TestApp",
        "app_type": "web",
        "working_dir": str(tmp_path),
        "launch_command": "echo running",
        "max_actions": 5,
        "max_duration_seconds": 60,
        "test_objectives": ["Login", "Dashboard"],
        "permissions": {
            "launch_app": "auto",
            "interact_with_ui": "auto",
            "take_screenshots": "auto",
            "call_external_apis": "auto",
        },
    }
    cfg.update(overrides)
    config_path = tmp_path / "runtime.yaml"
    config_path.write_text(yaml.dump(cfg))
    return config_path


# ── --help ─────────────────────────────────────────────────────────────────────

class TestInteractiveTestHelp:
    def test_help_exits_zero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["interactive-test", "--help"])
        assert exc_info.value.code == 0

    def test_help_mentions_interactive_test(self, capsys):
        with pytest.raises(SystemExit):
            main(["interactive-test", "--help"])
        captured = capsys.readouterr()
        assert "interactive" in captured.out.lower() or "interactive" in captured.err.lower()

    def test_global_help_lists_interactive_test(self, capsys):
        with pytest.raises(SystemExit):
            main(["--help"])
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "interactive-test" in combined


# ── parser ────────────────────────────────────────────────────────────────────

class TestInteractiveTestParser:
    def test_parser_accepts_dry_run_flag(self):
        parser = build_parser()
        args = parser.parse_args(["interactive-test", "--dry-run"])
        assert args.dry_run is True

    def test_parser_accepts_config_flag(self):
        parser = build_parser()
        args = parser.parse_args(["interactive-test", "--config", "myconfig.yaml"])
        assert args.config == "myconfig.yaml"

    def test_parser_accepts_no_permission_flag(self):
        parser = build_parser()
        args = parser.parse_args(["interactive-test", "--no-permission"])
        assert args.no_permission is True

    def test_parser_accepts_output_dir(self):
        parser = build_parser()
        args = parser.parse_args(["interactive-test", "--output-dir", "/tmp/out"])
        assert args.output_dir == "/tmp/out"

    def test_parser_accepts_target_override(self):
        parser = build_parser()
        args = parser.parse_args(["interactive-test", "--target", "/path/to/app"])
        assert args.target == "/path/to/app"

    def test_dry_run_defaults_to_false(self):
        parser = build_parser()
        args = parser.parse_args(["interactive-test"])
        assert args.dry_run is False

    def test_no_permission_defaults_to_false(self):
        parser = build_parser()
        args = parser.parse_args(["interactive-test"])
        assert args.no_permission is False


# ── dry-run: does not launch any app ──────────────────────────────────────────

class TestInteractiveTestDryRun:
    def test_dry_run_with_valid_config_exits_zero(self, tmp_path, capsys):
        config_path = _write_config(tmp_path)
        with patch("subprocess.Popen") as mock_popen:
            code = main([
                "interactive-test",
                "--config", str(config_path),
                "--dry-run",
            ])
        assert code == 0
        mock_popen.assert_not_called()

    def test_dry_run_prints_app_name(self, tmp_path, capsys):
        config_path = _write_config(tmp_path)
        main(["interactive-test", "--config", str(config_path), "--dry-run"])
        captured = capsys.readouterr()
        assert "TestApp" in captured.out

    def test_dry_run_prints_launch_command(self, tmp_path, capsys):
        config_path = _write_config(tmp_path)
        main(["interactive-test", "--config", str(config_path), "--dry-run"])
        captured = capsys.readouterr()
        assert "echo running" in captured.out

    def test_dry_run_prints_test_objectives(self, tmp_path, capsys):
        config_path = _write_config(tmp_path)
        main(["interactive-test", "--config", str(config_path), "--dry-run"])
        captured = capsys.readouterr()
        assert "Login" in captured.out or "Dashboard" in captured.out

    def test_dry_run_prints_dry_run_complete(self, tmp_path, capsys):
        config_path = _write_config(tmp_path)
        main(["interactive-test", "--config", str(config_path), "--dry-run"])
        captured = capsys.readouterr()
        assert "DRY-RUN" in captured.out.upper()

    def test_dry_run_does_not_call_subprocess(self, tmp_path):
        config_path = _write_config(tmp_path)
        with patch("subprocess.Popen") as mock_popen:
            main(["interactive-test", "--config", str(config_path), "--dry-run"])
        mock_popen.assert_not_called()


# ── missing / invalid config ───────────────────────────────────────────────────

class TestInteractiveTestInvalidConfig:
    def test_nonexistent_config_file_returns_error(self, capsys):
        code = main(["interactive-test", "--config", "/no/such/file.yaml"])
        assert code == 1

    def test_nonexistent_config_prints_error_message(self, capsys):
        main(["interactive-test", "--config", "/no/such/file.yaml"])
        captured = capsys.readouterr()
        assert "error" in captured.out.lower() or "error" in captured.err.lower()

    def test_default_config_when_no_flag_given(self, capsys):
        # When no --config flag given, load_config(None) should still proceed
        # (it may use a default or return a minimal config — just shouldn't crash the parser)
        with patch("qa_ai.interactive_runtime.config_loader.load_config") as mock_load:
            from qa_ai.interactive_runtime.schemas import InteractiveRuntimeConfig
            mock_load.return_value = InteractiveRuntimeConfig(
                app_name="Default",
                launch_command="echo hi",
            )
            with patch("qa_ai.cli.main._dry_run_report", return_value=0) as mock_dry:
                code = main(["interactive-test", "--dry-run"])
        assert code == 0


# ── --target overrides working_dir ────────────────────────────────────────────

class TestInteractiveTestTargetOverride:
    def test_target_overrides_working_dir(self, tmp_path, capsys):
        config_path = _write_config(tmp_path)
        override = str(tmp_path / "override")
        override_path = Path(override)
        override_path.mkdir(exist_ok=True)

        with patch("qa_ai.cli.main._dry_run_report") as mock_dry:
            mock_dry.return_value = 0
            main([
                "interactive-test",
                "--config", str(config_path),
                "--target", override,
                "--dry-run",
            ])
            # Verify the config passed to _dry_run_report has overridden working_dir
            called_config = mock_dry.call_args[0][0]
            assert called_config.working_dir == override


# ── --no-permission wiring ────────────────────────────────────────────────────

class TestInteractiveTestNoPermission:
    def test_no_permission_flag_sets_interactive_false(self, tmp_path):
        config_path = _write_config(tmp_path)
        with patch("qa_ai.cli.main._live_interactive_test") as mock_live:
            mock_live.return_value = 0
            main(["interactive-test", "--config", str(config_path), "--no-permission"])
        # The live function should be called with interactive=False
        _, kwargs = mock_live.call_args
        assert kwargs.get("interactive", mock_live.call_args[0][2] if mock_live.call_args[0] else True) is False
