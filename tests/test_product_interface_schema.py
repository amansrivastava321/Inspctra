"""
test_product_interface_schema.py - Tests for product interface Pydantic models.
"""
import pytest
from datetime import datetime

from qa_ai.schemas.product_interface_schema import (
    CLIRunSummaryArtifact,
    WebAppSessionArtifact,
    ProductInterfaceSummaryArtifact,
)


class TestCLIRunSummaryArtifact:
    def test_default_artifact_type(self):
        a = CLIRunSummaryArtifact()
        assert a.artifact_type == "cli_run_summary"

    def test_default_status_is_ok(self):
        a = CLIRunSummaryArtifact()
        assert a.status == "ok"

    def test_default_exit_code_zero(self):
        a = CLIRunSummaryArtifact()
        assert a.exit_code == 0

    def test_started_at_is_iso_string(self):
        a = CLIRunSummaryArtifact()
        datetime.fromisoformat(a.started_at)  # must not raise

    def test_phases_executed_default_empty(self):
        a = CLIRunSummaryArtifact()
        assert a.phases_executed == []

    def test_can_set_all_fields(self):
        a = CLIRunSummaryArtifact(
            command="audit",
            subcommand="run",
            target_path="/app",
            profile="api",
            status="failed",
            exit_code=1,
            phases_executed=["discovery"],
            errors=["something broke"],
        )
        assert a.command == "audit"
        assert a.status == "failed"
        assert a.exit_code == 1
        assert "discovery" in a.phases_executed

    def test_serialises_to_dict(self):
        a = CLIRunSummaryArtifact(command="audit")
        d = a.model_dump()
        assert d["artifact_type"] == "cli_run_summary"
        assert "started_at" in d


class TestWebAppSessionArtifact:
    def test_default_artifact_type(self):
        a = WebAppSessionArtifact()
        assert a.artifact_type == "webapp_session"

    def test_default_port(self):
        a = WebAppSessionArtifact()
        assert a.port == 8765

    def test_default_host(self):
        a = WebAppSessionArtifact()
        assert a.host == "127.0.0.1"

    def test_read_only_true_by_default(self):
        a = WebAppSessionArtifact()
        assert a.read_only is True

    def test_routes_default_empty(self):
        a = WebAppSessionArtifact()
        assert a.routes_registered == []

    def test_custom_routes(self):
        a = WebAppSessionArtifact(routes_registered=["/", "/api/findings"])
        assert "/api/findings" in a.routes_registered


class TestProductInterfaceSummaryArtifact:
    def test_default_artifact_type(self):
        a = ProductInterfaceSummaryArtifact()
        assert a.artifact_type == "product_interface_summary"

    def test_counters_default_zero(self):
        a = ProductInterfaceSummaryArtifact()
        assert a.total_cli_runs == 0
        assert a.total_dashboard_sessions == 0

    def test_lists_default_empty(self):
        a = ProductInterfaceSummaryArtifact()
        assert a.commands_used == []
        assert a.profiles_used == []

    def test_generated_at_is_iso_string(self):
        a = ProductInterfaceSummaryArtifact()
        datetime.fromisoformat(a.generated_at)

    def test_optional_fields_none_by_default(self):
        a = ProductInterfaceSummaryArtifact()
        assert a.last_audit_target is None
        assert a.last_audit_status is None

    def test_serialises_to_dict(self):
        a = ProductInterfaceSummaryArtifact(
            total_cli_runs=5,
            commands_used=["audit", "doctor"],
            last_audit_status="completed",
        )
        d = a.model_dump()
        assert d["total_cli_runs"] == 5
        assert "audit" in d["commands_used"]
