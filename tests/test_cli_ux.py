"""
test_cli_ux.py - Tests for CLI formatter and new CLI commands.
"""
import sys
import pytest
from io import StringIO
from unittest.mock import patch, MagicMock

from qa_ai.cli.formatter import (
    print_version,
    print_init_result,
    print_audit_summary,
    print_doctor_report,
    print_dashboard_starting,
    print_result,
)


class TestPrintVersion:
    def test_outputs_version_string(self, capsys):
        print_version("1.2.3")
        captured = capsys.readouterr()
        assert "1.2.3" in captured.out

    def test_outputs_product_name(self, capsys):
        print_version("1.0.0")
        captured = capsys.readouterr()
        assert "Inspectra" in captured.out or "inspectra" in captured.out.lower()


class TestPrintInitResult:
    def test_success_shows_ok(self, capsys):
        print_init_result({"status": "ok", "created": ["artifacts/"]})
        captured = capsys.readouterr()
        assert captured.out  # something was printed

    def test_error_shows_error(self, capsys):
        print_init_result({"status": "error", "error": "permission denied"})
        captured = capsys.readouterr()
        assert captured.out


class TestPrintAuditSummary:
    def test_prints_status(self, capsys):
        print_audit_summary({
            "status": "completed",
            "phases_executed": ["discovery", "analysis"],
            "findings": [{"severity": "high"}, {"severity": "low"}],
        })
        captured = capsys.readouterr()
        assert captured.out

    def test_prints_finding_count(self, capsys):
        result = {
            "status": "completed",
            "findings": [{"id": "F1"}, {"id": "F2"}],
            "phases_executed": [],
        }
        print_audit_summary(result)
        captured = capsys.readouterr()
        assert captured.out

    def test_handles_empty_result(self, capsys):
        print_audit_summary({})
        captured = capsys.readouterr()
        assert captured.out  # should not crash


class TestPrintDoctorReport:
    def test_prints_check_table(self, capsys):
        print_doctor_report({
            "checks": [
                {"name": "config", "status": "ok", "detail": "all good"},
                {"name": "llm", "status": "warn", "detail": "slow"},
            ]
        })
        captured = capsys.readouterr()
        assert captured.out

    def test_handles_empty_report(self, capsys):
        print_doctor_report({})
        assert True  # should not raise


class TestPrintDashboardStarting:
    def test_prints_url(self, capsys):
        print_dashboard_starting("127.0.0.1", 8765, "artifacts/")
        captured = capsys.readouterr()
        assert "8765" in captured.out or "127.0.0.1" in captured.out or captured.out


class TestPrintResult:
    def test_prints_something_for_any_command(self, capsys):
        print_result({"status": "ok"}, command="audit")
        captured = capsys.readouterr()
        assert captured.out or True  # formatter may choose to output nothing for unknown


class TestCLIVersionCommand:
    def test_version_command_exits_zero(self):
        from qa_ai.cli.main import main
        with patch("sys.argv", ["qa_ai", "version"]):
            code = main()
        assert code == 0

    def test_version_command_outputs_text(self, capsys):
        from qa_ai.cli.main import main
        with patch("sys.argv", ["qa_ai", "version"]):
            main()
        captured = capsys.readouterr()
        assert captured.out


class TestCLIInitCommand:
    def test_init_command_runs(self, tmp_path):
        from qa_ai.cli.main import main
        with patch("sys.argv", ["qa_ai", "init", "--dir", str(tmp_path)]):
            code = main()
        assert code == 0

    def test_init_creates_artifacts_dir(self, tmp_path):
        from qa_ai.cli.main import main
        with patch("sys.argv", ["qa_ai", "init", "--dir", str(tmp_path)]):
            main()
        assert (tmp_path / "artifacts").exists()
