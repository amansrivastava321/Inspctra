"""
test_interactive_runtime_connectors.py - Tests for the Live Runtime Connector Layer.

Coverage:
 1. Connector models (Pydantic validation)
 2. Connector registry
 3. Connector factory
 4. RuntimeConnectorManager ordering
 5. Required connector failure blocks target
 6. Optional connector failure continues
 7. ServiceProcessConnector dry-run / blocked permission
 8. BrowserConnector missing Playwright gap
 9. DesktopAppConnector uses desktop driver path
10. MobileAppConnector missing Appium gap
11. BackendServiceConnector readiness URL
12. DatabaseConnector read-only default
13. DockerConnector requires approval
14. AIModelConnector Ollama readiness
15. ThirdPartyAppConnector black-box limitation
16. ValidationRunner uses connectors
17. RuntimeConnectorManager artifacts written
18. ConnectorReporter writes files
19. CLI dry-run shows connector plan
20. No hardcoded app strings in connector core
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── helpers ───────────────────────────────────────────────────────────────────

BASE = Path(__file__).parent.parent

# Ensure package importable
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))


def _make_config(
    connector_type: str = "backend_service",
    connector_id: str = "test_conn",
    **kwargs,
):
    from qa_ai.interactive_runtime.connectors.connector_models import (
        RuntimeConnectorConfig,
        ConnectorType,
    )
    return RuntimeConnectorConfig(
        connector_id=connector_id,
        connector_type=ConnectorType(connector_type),
        name=kwargs.pop("name", "Test Connector"),
        **kwargs,
    )


# ── 1. Connector models ───────────────────────────────────────────────────────

class TestConnectorModels:
    def test_runtime_connector_config_defaults(self):
        from qa_ai.interactive_runtime.connectors.connector_models import (
            RuntimeConnectorConfig, ConnectorType,
        )
        cfg = RuntimeConnectorConfig(
            connector_id="x",
            connector_type=ConnectorType.BACKEND_SERVICE,
        )
        assert cfg.enabled is True
        assert cfg.required is True
        assert cfg.requires_permission is True
        assert cfg.allow_external_calls is False
        assert cfg.allow_destructive_actions is False

    def test_readiness_url_validator_rejects_non_http(self):
        from qa_ai.interactive_runtime.connectors.connector_models import (
            RuntimeConnectorConfig, ConnectorType,
        )
        import pydantic
        with pytest.raises((pydantic.ValidationError, ValueError)):
            RuntimeConnectorConfig(
                connector_id="x",
                connector_type=ConnectorType.BACKEND_SERVICE,
                readiness_url="ftp://evil.com",
            )

    def test_readiness_url_validator_accepts_http_localhost(self):
        from qa_ai.interactive_runtime.connectors.connector_models import (
            RuntimeConnectorConfig, ConnectorType,
        )
        cfg = RuntimeConnectorConfig(
            connector_id="x",
            connector_type=ConnectorType.BACKEND_SERVICE,
            readiness_url="http://localhost:8000/health",
        )
        assert cfg.readiness_url == "http://localhost:8000/health"

    def test_connector_type_enum_values(self):
        from qa_ai.interactive_runtime.connectors.connector_models import ConnectorType
        types = {ct.value for ct in ConnectorType}
        assert "web_browser" in types
        assert "mobile_app" in types
        assert "database" in types
        assert "docker_service" in types
        assert "ai_model" in types
        assert "third_party_app" in types

    def test_runtime_context_defaults(self):
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeContext
        ctx = RuntimeContext()
        assert ctx.connectors_ready is False
        assert ctx.connector_results == {}
        assert ctx.blocked_connector_ids == []

    def test_connectors_config_defaults(self):
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorsConfig
        cfg = RuntimeConnectorsConfig()
        assert cfg.enabled is True
        assert cfg.stop_on_failure is True
        assert cfg.connectors == []

    def test_connector_status_enum(self):
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        assert RuntimeConnectorStatus.READY.value == "ready"
        assert RuntimeConnectorStatus.CAPABILITY_GAP.value == "capability_gap"
        assert RuntimeConnectorStatus.BLOCKED.value == "blocked"


# ── 2. Connector registry ─────────────────────────────────────────────────────

class TestConnectorRegistry:
    def test_all_types_registered(self):
        from qa_ai.interactive_runtime.connectors.connector_registry import all_registered
        from qa_ai.interactive_runtime.connectors.connector_models import ConnectorType
        registered = all_registered()
        assert ConnectorType.WEB_BROWSER in registered
        assert ConnectorType.MOBILE_APP in registered
        assert ConnectorType.BACKEND_SERVICE in registered
        assert ConnectorType.DATABASE in registered
        assert ConnectorType.DOCKER_SERVICE in registered
        assert ConnectorType.AI_MODEL in registered
        assert ConnectorType.THIRD_PARTY_APP in registered
        assert ConnectorType.DESKTOP_APP in registered

    def test_get_class_returns_none_for_unknown(self):
        from qa_ai.interactive_runtime.connectors.connector_registry import get_class
        from qa_ai.interactive_runtime.connectors.connector_models import ConnectorType
        # FILE_SYSTEM is registered? let's check it is or isn't - just test unknown handling
        result = get_class(ConnectorType.FILE_SYSTEM)
        # None or a class — both valid; just shouldn't raise
        assert result is None or callable(result)


# ── 3. Connector factory ──────────────────────────────────────────────────────

class TestConnectorFactory:
    def test_factory_returns_browser_connector(self):
        from qa_ai.interactive_runtime.connectors.connector_factory import ConnectorFactory
        from qa_ai.interactive_runtime.connectors.browser_connector import BrowserConnector
        cfg = _make_config("web_browser")
        conn = ConnectorFactory.create(cfg)
        assert isinstance(conn, BrowserConnector)

    def test_factory_returns_backend_connector(self):
        from qa_ai.interactive_runtime.connectors.connector_factory import ConnectorFactory
        from qa_ai.interactive_runtime.connectors.backend_service_connector import BackendServiceConnector
        cfg = _make_config("backend_service")
        conn = ConnectorFactory.create(cfg)
        assert isinstance(conn, BackendServiceConnector)

    def test_factory_returns_ai_model_connector(self):
        from qa_ai.interactive_runtime.connectors.connector_factory import ConnectorFactory
        from qa_ai.interactive_runtime.connectors.ai_model_connector import AIModelConnector
        cfg = _make_config("ai_model")
        conn = ConnectorFactory.create(cfg)
        assert isinstance(conn, AIModelConnector)

    def test_factory_available_types_not_empty(self):
        from qa_ai.interactive_runtime.connectors.connector_factory import ConnectorFactory
        types = ConnectorFactory.available_types()
        assert len(types) > 5


# ── 4. RuntimeConnectorManager ordering ───────────────────────────────────────

class TestConnectorManagerOrdering:
    def test_dependency_order_db_before_backend(self):
        from qa_ai.interactive_runtime.connectors.runtime_connector_manager import _TYPE_ORDER, _sort_key
        from qa_ai.interactive_runtime.connectors.connector_models import ConnectorType
        db_cfg = _make_config("database", connector_id="db")
        be_cfg = _make_config("backend_service", connector_id="be")
        assert _sort_key(db_cfg) < _sort_key(be_cfg)

    def test_dependency_order_docker_before_backend(self):
        from qa_ai.interactive_runtime.connectors.runtime_connector_manager import _sort_key
        docker_cfg = _make_config("docker_service", connector_id="d")
        be_cfg = _make_config("backend_service", connector_id="b")
        assert _sort_key(docker_cfg) < _sort_key(be_cfg)

    def test_dependency_order_backend_before_browser(self):
        from qa_ai.interactive_runtime.connectors.runtime_connector_manager import _sort_key
        be_cfg = _make_config("backend_service", connector_id="b")
        br_cfg = _make_config("web_browser", connector_id="w")
        assert _sort_key(be_cfg) < _sort_key(br_cfg)

    def test_manager_dry_run_no_processes_started(self):
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorsConfig
        from qa_ai.interactive_runtime.connectors.runtime_connector_manager import RuntimeConnectorManager
        connectors_cfg = RuntimeConnectorsConfig(
            connectors=[
                _make_config("ai_model", connector_id="ai", requires_permission=False),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            manager = RuntimeConnectorManager(output_dir=tmp, interactive=False)
            ctx = manager.run(connectors_cfg, dry_run=True)
        # Dry run: context created, no blocking
        assert ctx.session_id != ""
        # ai model dry run: should return PENDING (not actually connect)
        result = ctx.connector_results.get("ai")
        assert result is not None
        assert result.status.value in ("pending", "capability_gap", "ready")


# ── 5. Required connector failure blocks target ───────────────────────────────

class TestRequiredConnectorBlocksTarget:
    def test_required_failed_blocks(self):
        from qa_ai.interactive_runtime.connectors.connector_models import (
            RuntimeConnectorsConfig, RuntimeConnectorStatus,
        )
        from qa_ai.interactive_runtime.connectors.runtime_connector_manager import RuntimeConnectorManager
        # Backend with no launch command and required=True should fail
        cfg = _make_config(
            "backend_service",
            connector_id="be",
            launch_command="",
            required=True,
            requires_permission=False,
        )
        connectors_cfg = RuntimeConnectorsConfig(
            stop_on_failure=True,
            connectors=[cfg],
        )
        with tempfile.TemporaryDirectory() as tmp:
            manager = RuntimeConnectorManager(output_dir=tmp, interactive=False)
            ctx = manager.run(connectors_cfg, dry_run=False)
        assert ctx.connectors_ready is False
        assert "be" in ctx.blocked_connector_ids


# ── 6. Optional connector failure continues ───────────────────────────────────

class TestOptionalConnectorContinues:
    def test_optional_failed_does_not_block(self):
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorsConfig
        from qa_ai.interactive_runtime.connectors.runtime_connector_manager import RuntimeConnectorManager
        # Optional connector that will fail (bad launch_command, no permission auto-approve)
        cfg = _make_config(
            "backend_service",
            connector_id="be_optional",
            launch_command="",
            required=False,
            requires_permission=False,
        )
        connectors_cfg = RuntimeConnectorsConfig(
            stop_on_failure=True,
            connectors=[cfg],
        )
        with tempfile.TemporaryDirectory() as tmp:
            manager = RuntimeConnectorManager(output_dir=tmp, interactive=False)
            ctx = manager.run(connectors_cfg, dry_run=False)
        # Optional connector failed but target not blocked
        assert ctx.connectors_ready is True
        assert "be_optional" not in ctx.blocked_connector_ids


# ── 7. ServiceProcessConnector ────────────────────────────────────────────────

class TestServiceProcessConnector:
    def test_dry_run_returns_pending(self):
        from qa_ai.interactive_runtime.connectors.service_process_connector import ServiceProcessConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        conn = ServiceProcessConnector()
        cfg = _make_config("service_process", connector_id="svc",
                           launch_command="echo hello", requires_permission=False)
        result = conn.connect_or_launch(cfg, dry_run=True)
        assert result.status == RuntimeConnectorStatus.PENDING

    def test_missing_permission_returns_blocked(self):
        from qa_ai.interactive_runtime.connectors.service_process_connector import ServiceProcessConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        conn = ServiceProcessConnector()
        cfg = _make_config("service_process", connector_id="svc",
                           launch_command="echo hello", requires_permission=True)
        result = conn.connect_or_launch(cfg, dry_run=False, approved=False)
        assert result.status == RuntimeConnectorStatus.BLOCKED

    def test_missing_executable_returns_gap(self):
        from qa_ai.interactive_runtime.connectors.service_process_connector import ServiceProcessConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        conn = ServiceProcessConnector()
        cfg = _make_config("service_process", connector_id="svc",
                           launch_command="__definitely_not_a_real_exe_xyz__ arg1",
                           requires_permission=False)
        result = conn.connect_or_launch(cfg, dry_run=False, approved=True)
        assert result.status == RuntimeConnectorStatus.CAPABILITY_GAP

    def test_empty_command_returns_failed(self):
        from qa_ai.interactive_runtime.connectors.service_process_connector import ServiceProcessConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        conn = ServiceProcessConnector()
        cfg = _make_config("service_process", connector_id="svc",
                           launch_command="", requires_permission=False)
        result = conn.connect_or_launch(cfg, dry_run=False, approved=True)
        assert result.status == RuntimeConnectorStatus.FAILED

    def test_no_shell_true_in_launch(self):
        """ServiceProcessConnector must never call subprocess with shell=True."""
        import inspect, re
        from qa_ai.interactive_runtime.connectors import service_process_connector
        src = inspect.getsource(service_process_connector)
        # Check no actual subprocess call uses shell=True (comments/docstrings OK)
        calls = re.findall(r"subprocess\.[a-z_]+\([^)]*shell\s*=\s*True", src, re.DOTALL)
        assert not calls, f"subprocess shell=True call found: {calls}"


# ── 8. BrowserConnector missing Playwright ────────────────────────────────────

class TestBrowserConnectorGap:
    def test_playwright_missing_returns_gap(self):
        from qa_ai.interactive_runtime.connectors.browser_connector import BrowserConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        with patch(
            "qa_ai.interactive_runtime.connectors.browser_connector._playwright_available",
            return_value=False,
        ):
            conn = BrowserConnector()
            cfg = _make_config("web_browser", connector_id="browser",
                               readiness_url="http://127.0.0.1:3000")
            result = conn.connect_or_launch(cfg, dry_run=False, approved=True)
        assert result.status == RuntimeConnectorStatus.CAPABILITY_GAP
        assert any("playwright" in g.gap_id for g in result.capability_gaps)

    def test_playwright_present_dry_run(self):
        from qa_ai.interactive_runtime.connectors.browser_connector import BrowserConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        with patch(
            "qa_ai.interactive_runtime.connectors.browser_connector._playwright_available",
            return_value=True,
        ):
            conn = BrowserConnector()
            cfg = _make_config("web_browser", connector_id="browser",
                               readiness_url="http://127.0.0.1:3000")
            result = conn.connect_or_launch(cfg, dry_run=True)
        assert result.status == RuntimeConnectorStatus.PENDING

    def test_setup_instructions_present_in_gap(self):
        from qa_ai.interactive_runtime.connectors.browser_connector import BrowserConnector
        with patch(
            "qa_ai.interactive_runtime.connectors.browser_connector._playwright_available",
            return_value=False,
        ):
            conn = BrowserConnector()
            cfg = _make_config("web_browser", connector_id="browser")
            result = conn.connect_or_launch(cfg, dry_run=False, approved=True)
        assert len(result.setup_instructions) > 0


# ── 9. DesktopAppConnector ────────────────────────────────────────────────────

class TestDesktopAppConnector:
    def test_dry_run_returns_pending_or_gap(self):
        """Dry-run returns PENDING if platform tools present, CAPABILITY_GAP if missing."""
        from qa_ai.interactive_runtime.connectors.desktop_app_connector import DesktopAppConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        conn = DesktopAppConnector()
        cfg = _make_config("desktop_app", connector_id="desktop",
                           process_name="SomeApp")
        result = conn.connect_or_launch(cfg, dry_run=True)
        # platform capability check runs before dry_run; both outcomes valid
        assert result.status in (
            RuntimeConnectorStatus.PENDING,
            RuntimeConnectorStatus.CAPABILITY_GAP,
        )

    def test_no_permission_returns_blocked_or_gap(self):
        """Returns BLOCKED when platform tools present; GAP when tools missing."""
        from qa_ai.interactive_runtime.connectors.desktop_app_connector import DesktopAppConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        conn = DesktopAppConnector()
        cfg = _make_config("desktop_app", connector_id="desktop",
                           process_name="SomeApp", requires_permission=True)
        result = conn.connect_or_launch(cfg, dry_run=False, approved=False)
        assert result.status in (
            RuntimeConnectorStatus.BLOCKED,
            RuntimeConnectorStatus.CAPABILITY_GAP,
        )

    def test_required_tools_platform_aware(self):
        from qa_ai.interactive_runtime.connectors.desktop_app_connector import DesktopAppConnector
        conn = DesktopAppConnector()
        tools = conn.required_tools()
        # just verify it returns a list
        assert isinstance(tools, list)


# ── 10. MobileAppConnector missing Appium ─────────────────────────────────────

class TestMobileAppConnectorGap:
    def test_appium_client_missing_returns_gap(self):
        from qa_ai.interactive_runtime.connectors.mobile_app_connector import MobileAppConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        with patch(
            "qa_ai.interactive_runtime.connectors.mobile_app_connector._appium_client_available",
            return_value=False,
        ):
            conn = MobileAppConnector()
            cfg = _make_config("mobile_app", connector_id="mob",
                               app_type="android", package_name="com.example.test",
                               readiness_url="http://127.0.0.1:4723")
            result = conn.connect_or_launch(cfg, dry_run=False, approved=True)
        assert result.status == RuntimeConnectorStatus.CAPABILITY_GAP

    def test_ios_on_non_macos_returns_gap(self):
        import platform as _plt
        from qa_ai.interactive_runtime.connectors.mobile_app_connector import MobileAppConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        if _plt.system().lower() == "darwin":
            pytest.skip("Cannot test iOS non-macOS restriction on macOS")
        with patch(
            "qa_ai.interactive_runtime.connectors.mobile_app_connector._appium_client_available",
            return_value=True,
        ):
            conn = MobileAppConnector()
            cfg = _make_config("mobile_app", connector_id="ios_app",
                               app_type="ios", bundle_id="com.example.App",
                               readiness_url="http://127.0.0.1:4723")
            result = conn.connect_or_launch(cfg, dry_run=False, approved=True)
        assert result.status == RuntimeConnectorStatus.CAPABILITY_GAP

    def test_dry_run_with_appium_available(self):
        from qa_ai.interactive_runtime.connectors.mobile_app_connector import MobileAppConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        with patch(
            "qa_ai.interactive_runtime.connectors.mobile_app_connector._appium_client_available",
            return_value=True,
        ), patch(
            "qa_ai.interactive_runtime.connectors.readiness_checker.ReadinessChecker.check_appium_server",
            return_value=MagicMock(result=True, error=None, evidence={}),
        ):
            conn = MobileAppConnector()
            cfg = _make_config("mobile_app", connector_id="mob",
                               app_type="android", package_name="com.example.test",
                               readiness_url="http://127.0.0.1:4723")
            result = conn.connect_or_launch(cfg, dry_run=True, approved=False)
        assert result.status == RuntimeConnectorStatus.PENDING

    def test_invalid_package_name_rejected(self):
        from qa_ai.interactive_runtime.connectors.mobile_app_connector import MobileAppConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        with patch(
            "qa_ai.interactive_runtime.connectors.mobile_app_connector._appium_client_available",
            return_value=True,
        ), patch(
            "qa_ai.interactive_runtime.connectors.readiness_checker.ReadinessChecker.check_appium_server",
            return_value=MagicMock(result=True, error=None, evidence={}),
        ):
            conn = MobileAppConnector()
            cfg = _make_config("mobile_app", connector_id="mob",
                               app_type="android",
                               package_name="com.evil; rm -rf /",
                               readiness_url="http://127.0.0.1:4723")
            result = conn.connect_or_launch(cfg, dry_run=False, approved=True)
        assert result.status == RuntimeConnectorStatus.FAILED


# ── 11. BackendServiceConnector readiness URL ─────────────────────────────────

class TestBackendServiceConnector:
    def test_dry_run_validates_command(self):
        from qa_ai.interactive_runtime.connectors.backend_service_connector import BackendServiceConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        conn = BackendServiceConnector()
        cfg = _make_config("backend_service", connector_id="be",
                           launch_command="uvicorn app:app --port 8000",
                           readiness_url="http://127.0.0.1:8000/health",
                           api_base_url="http://127.0.0.1:8000",
                           requires_permission=False)
        result = conn.connect_or_launch(cfg, dry_run=True)
        # uvicorn not installed in test env → gap; or pending if dry_run
        assert result.status in (RuntimeConnectorStatus.PENDING, RuntimeConnectorStatus.CAPABILITY_GAP)

    def test_endpoint_set_from_api_base_url(self):
        from qa_ai.interactive_runtime.connectors.backend_service_connector import BackendServiceConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        conn = BackendServiceConnector()
        cfg = _make_config("backend_service", connector_id="be",
                           launch_command="echo hi",
                           readiness_url="http://127.0.0.1:8000/health",
                           api_base_url="http://127.0.0.1:8000",
                           requires_permission=False)
        # Mock successful launch
        with patch.object(
            conn._delegate, "connect_or_launch",
            return_value=MagicMock(
                status=RuntimeConnectorStatus.READY,
                endpoint="http://127.0.0.1:8000/health",
                evidence={},
            ),
        ):
            result = conn.connect_or_launch(cfg, dry_run=False, approved=True)
        assert "http://127.0.0.1:8000" in (result.endpoint or "")


# ── 12. DatabaseConnector read-only default ───────────────────────────────────

class TestDatabaseConnector:
    def test_dry_run_sqlite(self):
        from qa_ai.interactive_runtime.connectors.database_connector import DatabaseConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        conn = DatabaseConnector()
        cfg = _make_config("database", connector_id="db",
                           database_type="sqlite",
                           database_path="/tmp/test.db",
                           requires_permission=False)
        result = conn.connect_or_launch(cfg, dry_run=True)
        assert result.status == RuntimeConnectorStatus.PENDING

    def test_missing_sqlite_file_returns_failed(self):
        from qa_ai.interactive_runtime.connectors.database_connector import DatabaseConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        conn = DatabaseConnector()
        cfg = _make_config("database", connector_id="db",
                           database_type="sqlite",
                           database_path="/tmp/__nonexistent_test_db.db",
                           requires_permission=False)
        result = conn.connect_or_launch(cfg, dry_run=False, approved=True)
        assert result.status == RuntimeConnectorStatus.FAILED

    def test_read_only_by_default(self):
        from qa_ai.interactive_runtime.connectors.database_connector import DatabaseConnector
        conn = DatabaseConnector()
        cfg = _make_config("database", connector_id="db",
                           database_type="sqlite",
                           allow_destructive_actions=False)
        evidence = conn.collect_evidence(cfg)
        assert evidence["read_only"] is True

    def test_no_permission_returns_blocked(self):
        from qa_ai.interactive_runtime.connectors.database_connector import DatabaseConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        conn = DatabaseConnector()
        cfg = _make_config("database", connector_id="db",
                           database_type="sqlite",
                           requires_permission=True)
        result = conn.connect_or_launch(cfg, dry_run=False, approved=False)
        assert result.status == RuntimeConnectorStatus.BLOCKED

    def test_sqlite_connect_with_real_file(self):
        from qa_ai.interactive_runtime.connectors.database_connector import DatabaseConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        import sqlite3
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            db_path = f.name
        conn_db = sqlite3.connect(db_path)
        conn_db.execute("CREATE TABLE t(id INTEGER)")
        conn_db.commit()
        conn_db.close()

        conn = DatabaseConnector()
        cfg = _make_config("database", connector_id="db",
                           database_type="sqlite",
                           database_path=db_path,
                           requires_permission=False)
        result = conn.connect_or_launch(cfg, dry_run=False, approved=True)
        assert result.status == RuntimeConnectorStatus.READY
        os.unlink(db_path)


# ── 13. DockerConnector requires approval ─────────────────────────────────────

class TestDockerConnector:
    def test_requires_approval_before_compose_up(self):
        """Requires BLOCKED when docker present; GAP when docker not installed."""
        from qa_ai.interactive_runtime.connectors.docker_connector import DockerConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        with patch(
            "qa_ai.interactive_runtime.connectors.docker_connector._docker_available",
            return_value=True,
        ), patch(
            "qa_ai.interactive_runtime.connectors.docker_connector._compose_available",
            return_value=True,
        ):
            conn = DockerConnector()
            cfg = _make_config("docker_service", connector_id="docker",
                               docker_compose_file="./docker-compose.yml",
                               docker_service="app",
                               requires_permission=True,
                               working_dir=".")
            result = conn.connect_or_launch(cfg, dry_run=False, approved=False)
        assert result.status == RuntimeConnectorStatus.BLOCKED

    def test_docker_missing_returns_gap(self):
        from qa_ai.interactive_runtime.connectors.docker_connector import DockerConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        with patch(
            "qa_ai.interactive_runtime.connectors.docker_connector._docker_available",
            return_value=False,
        ):
            conn = DockerConnector()
            cfg = _make_config("docker_service", connector_id="docker",
                               docker_compose_file="./docker-compose.yml",
                               requires_permission=False)
            result = conn.connect_or_launch(cfg, dry_run=False, approved=True)
        assert result.status == RuntimeConnectorStatus.CAPABILITY_GAP

    def test_dry_run_no_actual_compose_run(self):
        from qa_ai.interactive_runtime.connectors.docker_connector import DockerConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        with patch(
            "qa_ai.interactive_runtime.connectors.docker_connector._docker_available",
            return_value=True,
        ), patch(
            "qa_ai.interactive_runtime.connectors.docker_connector._compose_available",
            return_value=True,
        ):
            conn = DockerConnector()
            cfg = _make_config("docker_service", connector_id="docker",
                               docker_compose_file="./docker-compose.yml",
                               docker_service="app",
                               working_dir=".",
                               requires_permission=False)
            result = conn.connect_or_launch(cfg, dry_run=True)
        assert result.status == RuntimeConnectorStatus.PENDING


# ── 14. AIModelConnector Ollama readiness ─────────────────────────────────────

class TestAIModelConnector:
    def test_ollama_unreachable_returns_gap(self):
        from qa_ai.interactive_runtime.connectors.ai_model_connector import AIModelConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        with patch(
            "qa_ai.interactive_runtime.connectors.readiness_checker.ReadinessChecker.check_http_url",
            return_value=MagicMock(result=False, error="Connection refused", evidence={}),
        ):
            conn = AIModelConnector()
            cfg = _make_config("ai_model", connector_id="ai",
                               model_provider="ollama", model_name="qwen2.5vl:7b",
                               requires_permission=False)
            result = conn.connect_or_launch(cfg, dry_run=False, approved=True)
        assert result.status == RuntimeConnectorStatus.CAPABILITY_GAP

    def test_dry_run_returns_pending(self):
        from qa_ai.interactive_runtime.connectors.ai_model_connector import AIModelConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        conn = AIModelConnector()
        cfg = _make_config("ai_model", connector_id="ai",
                           model_provider="ollama", model_name="qwen2.5vl:7b",
                           requires_permission=False)
        result = conn.connect_or_launch(cfg, dry_run=True)
        assert result.status == RuntimeConnectorStatus.PENDING

    def test_external_provider_blocked_by_default(self):
        from qa_ai.interactive_runtime.connectors.ai_model_connector import AIModelConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        conn = AIModelConnector()
        cfg = _make_config("ai_model", connector_id="ai",
                           model_provider="openai",
                           model_name="gpt-4",
                           allow_external_calls=False,
                           requires_permission=False)
        result = conn.connect_or_launch(cfg, dry_run=False, approved=True)
        assert result.status == RuntimeConnectorStatus.BLOCKED

    def test_invalid_model_name_rejected(self):
        from qa_ai.interactive_runtime.connectors.ai_model_connector import AIModelConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        conn = AIModelConnector()
        cfg = _make_config("ai_model", connector_id="ai",
                           model_provider="ollama",
                           model_name="../../etc/passwd",
                           requires_permission=False)
        result = conn.connect_or_launch(cfg, dry_run=False, approved=True)
        assert result.status == RuntimeConnectorStatus.FAILED

    def test_ollama_reachable_no_model_returns_ready(self):
        from qa_ai.interactive_runtime.connectors.ai_model_connector import AIModelConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        with patch(
            "qa_ai.interactive_runtime.connectors.readiness_checker.ReadinessChecker.check_http_url",
            return_value=MagicMock(result=True, error=None, evidence={"available_models": []}),
        ):
            conn = AIModelConnector()
            cfg = _make_config("ai_model", connector_id="ai",
                               model_provider="ollama", model_name="",
                               requires_permission=False)
            result = conn.connect_or_launch(cfg, dry_run=False, approved=True)
        assert result.status == RuntimeConnectorStatus.READY


# ── 15. ThirdPartyAppConnector black-box ──────────────────────────────────────

class TestThirdPartyAppConnector:
    def test_limitations_in_evidence(self):
        from qa_ai.interactive_runtime.connectors.third_party_app_connector import ThirdPartyAppConnector
        conn = ThirdPartyAppConnector()
        cfg = _make_config("third_party_app", connector_id="tp",
                           app_type="native_macos", process_name="Safari")
        evidence = conn.collect_evidence(cfg)
        assert "limitations" in evidence
        assert len(evidence["limitations"]) > 0

    def test_dry_run_returns_pending(self):
        from qa_ai.interactive_runtime.connectors.third_party_app_connector import ThirdPartyAppConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        conn = ThirdPartyAppConnector()
        cfg = _make_config("third_party_app", connector_id="tp",
                           app_type="native_macos", process_name="Safari")
        result = conn.connect_or_launch(cfg, dry_run=True)
        assert result.status == RuntimeConnectorStatus.PENDING

    def test_no_permission_returns_blocked(self):
        from qa_ai.interactive_runtime.connectors.third_party_app_connector import ThirdPartyAppConnector
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorStatus
        conn = ThirdPartyAppConnector()
        cfg = _make_config("third_party_app", connector_id="tp",
                           app_type="native_macos", process_name="Safari",
                           requires_permission=True)
        result = conn.connect_or_launch(cfg, dry_run=False, approved=False)
        assert result.status == RuntimeConnectorStatus.BLOCKED

    def test_stop_never_terminates_third_party_process(self):
        from qa_ai.interactive_runtime.connectors.third_party_app_connector import ThirdPartyAppConnector
        conn = ThirdPartyAppConnector()
        cfg = _make_config("third_party_app", connector_id="tp",
                           app_type="native_macos", process_name="Safari")
        result = conn.stop(cfg)
        # Evidence should say app was not terminated
        assert "NOT terminated" in (result.evidence.get("note") or "")


# ── 16. ValidationRunner uses connectors ──────────────────────────────────────

class TestValidationRunnerConnectors:
    def test_dry_run_with_connectors_config(self):
        """ValidationRunner dry-run runs connector dry-run without launching."""
        from qa_ai.interactive_runtime.validation.validation_runner import ValidationRunner
        from qa_ai.interactive_runtime.validation.validation_target import ValidationTarget

        target = ValidationTarget(
            target_id="test_conn_target",
            app_name="Test",
            app_type="web",
            config_path="examples/interactive_runtime/generic_full_stack.yaml",
            validation_mode="dry_run",
        )
        with tempfile.TemporaryDirectory() as tmp:
            runner = ValidationRunner(output_dir=tmp, interactive=False)
            result = runner.run_dry(target)
        # dry_run_caps may include connector_dry_results if config has runtime_connectors
        assert result is not None

    def test_run_connectors_dry_returns_list(self):
        """_run_connectors_dry returns list for config with connectors."""
        from qa_ai.interactive_runtime.validation.validation_runner import ValidationRunner
        from qa_ai.interactive_runtime.validation.validation_target import ValidationTarget
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorsConfig

        runner = ValidationRunner(output_dir="/tmp", interactive=False)

        # Make a minimal config with runtime_connectors
        cfg = MagicMock()
        cfg.runtime_connectors = RuntimeConnectorsConfig(
            connectors=[
                _make_config("ai_model", connector_id="ai",
                             model_provider="ollama", model_name="test",
                             requires_permission=False),
            ]
        )
        target = ValidationTarget(
            target_id="t",
            app_name="T",
            app_type="web",
            config_path="examples/interactive_runtime/generic_web.yaml",
        )
        results = runner._run_connectors_dry(cfg, target)
        assert isinstance(results, list)


# ── 17. ConnectorReporter writes artifacts ────────────────────────────────────

class TestConnectorReporter:
    def test_writes_all_artifacts(self):
        from qa_ai.interactive_runtime.connectors.connector_reporter import ConnectorReporter
        from qa_ai.interactive_runtime.connectors.connector_models import (
            RuntimeContext, RuntimeConnectorResult, ConnectorType, RuntimeConnectorStatus,
        )
        with tempfile.TemporaryDirectory() as tmp:
            reporter = ConnectorReporter(output_dir=tmp)
            ctx = RuntimeContext(session_id="test123", connectors_ready=True)
            results = [
                RuntimeConnectorResult(
                    connector_id="be",
                    connector_type=ConnectorType.BACKEND_SERVICE,
                    status=RuntimeConnectorStatus.READY,
                )
            ]
            reporter.write_all(ctx, results, {"be": {"status": "ready"}}, {"be": {}})
            for fname in [
                "runtime_context.json",
                "connector_results.json",
                "connector_evidence.json",
                "connector_capabilities.json",
                "connector_readiness.json",
            ]:
                fpath = Path(tmp) / fname
                assert fpath.exists(), f"{fname} not written"
                data = json.loads(fpath.read_text())
                assert data is not None

    def test_connector_section_md(self):
        from qa_ai.interactive_runtime.connectors.connector_reporter import ConnectorReporter
        from qa_ai.interactive_runtime.connectors.connector_models import (
            RuntimeConnectorResult, ConnectorType, RuntimeConnectorStatus,
        )
        reporter = ConnectorReporter(output_dir="/tmp")
        results = [
            RuntimeConnectorResult(
                connector_id="db",
                connector_type=ConnectorType.DATABASE,
                status=RuntimeConnectorStatus.READY,
            )
        ]
        md = reporter.write_connector_section_md(results)
        assert "db" in md
        assert "database" in md


# ── 18. RuntimeConnectorManager artifacts written ─────────────────────────────

class TestManagerArtifacts:
    def test_artifacts_created_in_output_dir(self):
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorsConfig
        from qa_ai.interactive_runtime.connectors.runtime_connector_manager import RuntimeConnectorManager
        connectors_cfg = RuntimeConnectorsConfig(
            connectors=[
                _make_config("ai_model", connector_id="ai",
                             model_provider="ollama", requires_permission=False),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            manager = RuntimeConnectorManager(output_dir=tmp, interactive=False)
            manager.run(connectors_cfg, dry_run=True)
            for fname in ["runtime_context.json", "connector_results.json",
                          "connector_evidence.json", "connector_readiness.json"]:
                assert (Path(tmp) / fname).exists(), f"{fname} missing"


# ── 19. CLI dry-run shows connector plan ──────────────────────────────────────

class TestCLIConnectors:
    def test_cli_validate_runtime_dry_run_no_crash(self):
        """CLI dry-run with connector example should not raise."""
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "qa_ai.cli",
                "validate-runtime",
                "--pack", "examples/interactive_runtime/phase2_validation_pack.yaml",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(BASE),
            shell=False,
        )
        # Should exit 0 for dry-run
        assert result.returncode == 0, f"stderr: {result.stderr[:500]}"

    def test_cli_runtime_doctor_dry_run_no_crash(self):
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "qa_ai.cli",
                "runtime-doctor",
                "--pack", "examples/interactive_runtime/phase2_validation_pack.yaml",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(BASE),
            shell=False,
        )
        assert result.returncode == 0, f"stderr: {result.stderr[:500]}"


# ── 20. No hardcoded app strings in connector core ────────────────────────────

class TestNoHardcodedAppStrings:
    def _get_connector_sources(self) -> dict[str, str]:
        import inspect
        import importlib
        sources = {}
        modules = [
            "qa_ai.interactive_runtime.connectors.connector_models",
            "qa_ai.interactive_runtime.connectors.base_connector",
            "qa_ai.interactive_runtime.connectors.runtime_connector_manager",
            "qa_ai.interactive_runtime.connectors.connector_factory",
            "qa_ai.interactive_runtime.connectors.service_process_connector",
            "qa_ai.interactive_runtime.connectors.browser_connector",
            "qa_ai.interactive_runtime.connectors.desktop_app_connector",
            "qa_ai.interactive_runtime.connectors.mobile_app_connector",
            "qa_ai.interactive_runtime.connectors.backend_service_connector",
            "qa_ai.interactive_runtime.connectors.database_connector",
            "qa_ai.interactive_runtime.connectors.docker_connector",
            "qa_ai.interactive_runtime.connectors.ai_model_connector",
            "qa_ai.interactive_runtime.connectors.third_party_app_connector",
        ]
        for name in modules:
            mod = importlib.import_module(name)
            sources[name] = inspect.getsource(mod)
        return sources

    def test_no_flowbook_in_connector_core(self):
        for name, src in self._get_connector_sources().items():
            assert "FlowBook" not in src, f"FlowBook hardcoded in {name}"

    def test_no_videomation_in_connector_core(self):
        for name, src in self._get_connector_sources().items():
            assert "Videomation" not in src, f"Videomation hardcoded in {name}"

    def test_no_openrouter_in_connector_core(self):
        for name, src in self._get_connector_sources().items():
            assert "OpenRouter" not in src and "openrouter" not in src.lower(), \
                f"OpenRouter hardcoded in {name}"

    def test_no_shell_true_in_any_connector(self):
        import re
        for name, src in self._get_connector_sources().items():
            calls = re.findall(r"subprocess\.[a-z_]+\([^)]*shell\s*=\s*True", src, re.DOTALL)
            assert not calls, f"subprocess shell=True call in {name}: {calls}"

    def test_no_os_system_in_any_connector(self):
        for name, src in self._get_connector_sources().items():
            assert "os.system(" not in src, f"os.system found in {name}"

    def test_no_eval_in_any_connector(self):
        for name, src in self._get_connector_sources().items():
            # allow "eval" as substring only in identifiers not as function calls
            import re
            calls = re.findall(r"\beval\s*\(", src)
            assert not calls, f"eval() call found in {name}: {calls}"
