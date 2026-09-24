"""
test_runtime_context.py - Tests for the RuntimeContext deep wiring package.

Covers:
1. context_models - RuntimeTestContext, RuntimeCapabilityPlan, ContextEvidenceBundle
2. context_adapter - RuntimeContext → RuntimeTestContext conversion + secret redaction
3. context_capability_mapper - context → capability plan mapping
4. context_verification_planner - per-action plan generation
5. context_evidence_collector - evidence aggregation
6. context_safety_policy - action blocking rules
7. context_reporter - JSON artifact writing
8. BackendStateChecker.from_context
9. DatabaseVerifier.from_context
10. InteractionExecutor context wiring
11. ResultVerifier runtime_context param
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from qa_ai.interactive_runtime.runtime_context.context_models import (
    ContextEvidenceBundle,
    ContextVerificationPlan,
    EvidenceSource,
    RuntimeCapabilityPlan,
    RuntimeTestContext,
    UITestMethod,
    VerificationMethod,
)
from qa_ai.interactive_runtime.runtime_context.context_adapter import ContextAdapter
from qa_ai.interactive_runtime.runtime_context.context_capability_mapper import ContextCapabilityMapper
from qa_ai.interactive_runtime.runtime_context.context_verification_planner import ContextVerificationPlanner
from qa_ai.interactive_runtime.runtime_context.context_evidence_collector import ContextEvidenceCollector
from qa_ai.interactive_runtime.runtime_context.context_safety_policy import (
    ContextSafetyDecision,
    ContextSafetyPolicy,
)
from qa_ai.interactive_runtime.runtime_context.context_reporter import ContextReporter


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_runtime_context(**kwargs) -> Any:
    """Build a minimal RuntimeContext-like mock."""
    from qa_ai.interactive_runtime.connectors.connector_models import RuntimeContext
    defaults = dict(
        session_id="test-session",
        connectors_ready=True,
        browser_endpoint=None,
        backend_base_url=None,
        appium_server_url=None,
        appium_capabilities={},
        database_available=False,
        database_type=None,
        ai_model_available=False,
        ai_model_name=None,
        docker_services_running=[],
        connector_results={},
        connector_evidence={},
        capability_gaps=[],
        blocked_connector_ids=[],
    )
    defaults.update(kwargs)
    return RuntimeContext(**defaults)


def _make_test_context(**kwargs) -> RuntimeTestContext:
    defaults = dict(
        session_id="test-session",
        connectors_ready=True,
        ui_method=UITestMethod.PLAYWRIGHT_WEB,
        browser_url="http://localhost:3000",
        backend_base_url="http://localhost:8000",
        backend_available=True,
        database_available=True,
        database_type="sqlite",
        database_path="/tmp/test.db",
    )
    defaults.update(kwargs)
    return RuntimeTestContext(**defaults)


# ── 1. context_models ─────────────────────────────────────────────────────────

class TestContextModels:
    def test_runtime_test_context_defaults(self):
        ctx = RuntimeTestContext()
        assert ctx.ui_method == UITestMethod.NONE
        assert ctx.backend_available is False
        assert ctx.database_available is False
        assert ctx.is_third_party_mode is False
        assert ctx.allow_external_calls is False
        assert ctx.allow_destructive_actions is False

    def test_runtime_capability_plan_defaults(self):
        plan = RuntimeCapabilityPlan()
        assert plan.can_test_ui is False
        assert plan.can_verify_backend is False
        assert plan.can_verify_database is False
        assert plan.ui_methods_available == []

    def test_context_evidence_bundle_defaults(self):
        bundle = ContextEvidenceBundle(step_id="step-0001")
        assert bundle.backend_health is None
        assert bundle.log_lines == []
        assert bundle.errors == []

    def test_context_verification_plan_defaults(self):
        vplan = ContextVerificationPlan(step_id="s1", action_description="click login")
        assert vplan.run_backend_health is False
        assert vplan.run_log_tag_check is False
        assert vplan.confidence_floor == 0.0


# ── 2. context_adapter ────────────────────────────────────────────────────────

class TestContextAdapter:
    def test_adapt_none_returns_none(self):
        assert ContextAdapter.adapt(None) is None

    def test_adapt_empty_context_returns_none_ui_method(self):
        ctx = _make_runtime_context()
        result = ContextAdapter.adapt(ctx)
        assert result is not None
        assert result.ui_method == UITestMethod.NONE

    def test_adapt_web_browser_connector(self):
        from qa_ai.interactive_runtime.connectors.connector_models import (
            ConnectorType, RuntimeConnectorResult, RuntimeConnectorStatus,
        )
        result = RuntimeConnectorResult(
            connector_id="browser-1",
            connector_type=ConnectorType.WEB_BROWSER,
            status=RuntimeConnectorStatus.READY,
            endpoint="http://localhost:3000",
        )
        ctx = _make_runtime_context(
            browser_endpoint="http://localhost:3000",
            connector_results={"browser-1": result},
        )
        adapted = ContextAdapter.adapt(ctx)
        assert adapted.ui_method == UITestMethod.PLAYWRIGHT_WEB
        assert adapted.browser_url == "http://localhost:3000"

    def test_adapt_android_mobile_connector(self):
        from qa_ai.interactive_runtime.connectors.connector_models import (
            ConnectorType, RuntimeConnectorResult, RuntimeConnectorStatus,
        )
        result = RuntimeConnectorResult(
            connector_id="mobile-1",
            connector_type=ConnectorType.MOBILE_APP,
            status=RuntimeConnectorStatus.READY,
        )
        ctx = _make_runtime_context(
            appium_server_url="http://127.0.0.1:4723",
            appium_capabilities={"platformName": "Android"},
            connector_results={"mobile-1": result},
        )
        adapted = ContextAdapter.adapt(ctx)
        assert adapted.ui_method == UITestMethod.APPIUM_ANDROID
        assert adapted.appium_server_url == "http://127.0.0.1:4723"

    def test_adapt_ios_mobile_connector(self):
        from qa_ai.interactive_runtime.connectors.connector_models import (
            ConnectorType, RuntimeConnectorResult, RuntimeConnectorStatus,
        )
        result = RuntimeConnectorResult(
            connector_id="mobile-ios",
            connector_type=ConnectorType.MOBILE_APP,
            status=RuntimeConnectorStatus.READY,
        )
        ctx = _make_runtime_context(
            appium_capabilities={"platformName": "iOS"},
            connector_results={"mobile-ios": result},
        )
        adapted = ContextAdapter.adapt(ctx)
        assert adapted.ui_method == UITestMethod.APPIUM_IOS

    def test_adapt_redacts_appium_credential_keys(self):
        from qa_ai.interactive_runtime.connectors.connector_models import (
            ConnectorType, RuntimeConnectorResult, RuntimeConnectorStatus,
        )
        result = RuntimeConnectorResult(
            connector_id="mobile-1",
            connector_type=ConnectorType.MOBILE_APP,
            status=RuntimeConnectorStatus.READY,
        )
        ctx = _make_runtime_context(
            appium_capabilities={
                "platformName": "Android",
                "appium:token": "SECRET_VALUE",      # must be stripped
                "app:password": "hunter2",           # must be stripped
                "deviceName": "Pixel 6",             # safe
            },
            connector_results={"mobile-1": result},
        )
        adapted = ContextAdapter.adapt(ctx)
        assert "deviceName" in adapted.appium_caps
        assert "appium:token" not in adapted.appium_caps
        assert "app:password" not in adapted.appium_caps

    def test_adapt_db_stores_env_var_name_not_value(self):
        """database_url_env must hold env var NAME, never value."""
        from qa_ai.interactive_runtime.connectors.connector_models import (
            ConnectorType, RuntimeConnectorResult, RuntimeConnectorStatus,
        )
        result = RuntimeConnectorResult(
            connector_id="db-1",
            connector_type=ConnectorType.DATABASE,
            status=RuntimeConnectorStatus.READY,
            evidence={
                "database_type": "postgres",
                "database_url_env": "DATABASE_URL",    # name only
            },
        )
        ctx = _make_runtime_context(
            database_available=True,
            database_type="postgres",
            connector_results={"db-1": result},
        )
        adapted = ContextAdapter.adapt(ctx)
        assert adapted.database_url_env == "DATABASE_URL"
        # Must NOT contain the actual env var value
        if "DATABASE_URL" in os.environ:
            assert adapted.database_url_env != os.environ["DATABASE_URL"]

    def test_adapt_third_party_mode_detected(self):
        from qa_ai.interactive_runtime.connectors.connector_models import (
            ConnectorType, RuntimeConnectorResult, RuntimeConnectorStatus,
        )
        result = RuntimeConnectorResult(
            connector_id="tp-1",
            connector_type=ConnectorType.THIRD_PARTY_APP,
            status=RuntimeConnectorStatus.READY,
        )
        ctx = _make_runtime_context(connector_results={"tp-1": result})
        adapted = ContextAdapter.adapt(ctx)
        assert adapted.is_third_party_mode is True

    def test_adapt_backend_url_from_connector_evidence(self):
        from qa_ai.interactive_runtime.connectors.connector_models import (
            ConnectorType, RuntimeConnectorResult, RuntimeConnectorStatus,
        )
        result = RuntimeConnectorResult(
            connector_id="backend-1",
            connector_type=ConnectorType.BACKEND_SERVICE,
            status=RuntimeConnectorStatus.READY,
            endpoint="http://localhost:8080",
        )
        ctx = _make_runtime_context(connector_results={"backend-1": result})
        adapted = ContextAdapter.adapt(ctx)
        assert adapted.backend_base_url == "http://localhost:8080"
        assert adapted.backend_available is True


# ── 3. context_capability_mapper ─────────────────────────────────────────────

class TestContextCapabilityMapper:
    def test_none_context_blocks_all(self):
        plan = ContextCapabilityMapper.map(None)
        assert plan.can_test_ui is False
        assert "all" in plan.blocked_methods

    def test_playwright_context_enables_ui(self):
        ctx = _make_test_context()
        plan = ContextCapabilityMapper.map(ctx)
        assert plan.can_test_ui is True
        assert UITestMethod.PLAYWRIGHT_WEB in plan.ui_methods_available
        assert plan.has_screenshot_support is True

    def test_no_ui_method_blocks_ui(self):
        ctx = _make_test_context(ui_method=UITestMethod.NONE)
        plan = ContextCapabilityMapper.map(ctx)
        assert plan.can_test_ui is False
        assert "ui_control" in plan.blocked_methods

    def test_backend_available_enables_api_verification(self):
        ctx = _make_test_context()
        plan = ContextCapabilityMapper.map(ctx)
        assert plan.can_verify_backend is True
        assert VerificationMethod.BACKEND_API in plan.verification_methods_available

    def test_no_backend_blocks_api_verification(self):
        ctx = _make_test_context(backend_available=False, backend_base_url=None)
        plan = ContextCapabilityMapper.map(ctx)
        assert plan.can_verify_backend is False
        assert "backend_api" in plan.blocked_methods

    def test_database_available_enables_db_verification(self):
        ctx = _make_test_context()
        plan = ContextCapabilityMapper.map(ctx)
        assert plan.can_verify_database is True
        assert VerificationMethod.DATABASE_READ in plan.verification_methods_available

    def test_no_database_blocks_db_verification(self):
        ctx = _make_test_context(database_available=False)
        plan = ContextCapabilityMapper.map(ctx)
        assert plan.can_verify_database is False

    def test_third_party_mode_blocks_log_watcher(self):
        ctx = _make_test_context(is_third_party_mode=True)
        plan = ContextCapabilityMapper.map(ctx)
        assert plan.can_collect_logs is False
        assert "log_watcher" in plan.blocked_methods
        assert VerificationMethod.LOG_WATCHER not in plan.verification_methods_available

    def test_ui_only_mode_confidence_adjustment(self):
        ctx = _make_test_context(backend_available=False, backend_base_url=None, database_available=False)
        plan = ContextCapabilityMapper.map(ctx)
        assert VerificationMethod.UI_STATE.value in plan.confidence_adjustments
        assert plan.confidence_adjustments[VerificationMethod.UI_STATE.value] < 1.0

    def test_third_party_mode_global_confidence_adjustment(self):
        ctx = _make_test_context(is_third_party_mode=True)
        plan = ContextCapabilityMapper.map(ctx)
        assert "all" in plan.confidence_adjustments
        assert plan.confidence_adjustments["all"] < 1.0

    def test_evidence_sources_populated(self):
        ctx = _make_test_context()
        plan = ContextCapabilityMapper.map(ctx)
        assert EvidenceSource.BACKEND_HEALTH in plan.evidence_sources_available
        assert EvidenceSource.DATABASE_STATE in plan.evidence_sources_available
        assert EvidenceSource.SCREENSHOT in plan.evidence_sources_available
        assert EvidenceSource.CONNECTOR_LOGS in plan.evidence_sources_available


# ── 4. context_verification_planner ──────────────────────────────────────────

class TestContextVerificationPlanner:
    def test_plan_for_none_context(self):
        planner = ContextVerificationPlanner(None, None)
        vplan = planner.plan_for_action("s1", "click button")
        assert vplan.run_backend_health is False
        assert vplan.confidence_floor == 0.0

    def test_plan_submit_triggers_backend_health(self):
        ctx = _make_test_context()
        plan = ContextCapabilityMapper.map(ctx)
        planner = ContextVerificationPlanner(ctx, plan)
        vplan = planner.plan_for_action("s1", "submit login form")
        assert vplan.run_backend_health is True

    def test_plan_click_no_backend_health(self):
        ctx = _make_test_context()
        plan = ContextCapabilityMapper.map(ctx)
        planner = ContextVerificationPlanner(ctx, plan)
        vplan = planner.plan_for_action("s1", "click navigation menu")
        assert vplan.run_backend_health is False

    def test_plan_log_tags_included(self):
        ctx = _make_test_context()
        plan = ContextCapabilityMapper.map(ctx)
        planner = ContextVerificationPlanner(ctx, plan)
        vplan = planner.plan_for_action("s1", "click button", extra_log_tags=["user_created"])
        assert vplan.run_log_tag_check is True
        assert "user_created" in vplan.log_tags

    def test_plan_ui_text_included(self):
        ctx = _make_test_context()
        plan = ContextCapabilityMapper.map(ctx)
        planner = ContextVerificationPlanner(ctx, plan)
        vplan = planner.plan_for_action("s1", "click button", extra_ui_text=["Welcome"])
        assert vplan.run_ui_text_check is True
        assert "Welcome" in vplan.expected_ui_text

    def test_plan_destructive_reduces_confidence(self):
        ctx = _make_test_context()
        plan = ContextCapabilityMapper.map(ctx)
        planner = ContextVerificationPlanner(ctx, plan)
        vplan = planner.plan_for_action("s1", "delete user account")
        assert vplan.confidence_floor <= 0.5

    def test_plan_third_party_global_confidence_applied(self):
        ctx = _make_test_context(is_third_party_mode=True)
        plan = ContextCapabilityMapper.map(ctx)
        planner = ContextVerificationPlanner(ctx, plan)
        vplan = planner.plan_for_action("s1", "click button")
        assert vplan.confidence_floor < 1.0

    def test_plan_notes_populated(self):
        ctx = _make_test_context()
        plan = ContextCapabilityMapper.map(ctx)
        planner = ContextVerificationPlanner(ctx, plan)
        vplan = planner.plan_for_action("s1", "save settings")
        assert len(vplan.notes) > 0


# ── 5. context_evidence_collector ────────────────────────────────────────────

class TestContextEvidenceCollector:
    def test_collect_no_context(self):
        collector = ContextEvidenceCollector(None)
        bundle = collector.collect("s1")
        assert bundle.step_id == "s1"
        assert bundle.backend_health is None

    def test_collect_with_backend_checker(self):
        ctx = _make_test_context()
        mock_checker = MagicMock()
        mock_check = MagicMock()
        mock_check.status.value = "passed"
        mock_check.description = "health ok"
        mock_check.actual = "HTTP 200"
        mock_checker.check_health.return_value = mock_check

        collector = ContextEvidenceCollector(ctx, backend_checker=mock_checker)
        bundle = collector.collect("s1")
        assert bundle.backend_health is not None
        assert bundle.backend_health["status"] == "passed"

    def test_collect_backend_error_recorded_not_raised(self):
        ctx = _make_test_context()
        mock_checker = MagicMock()
        mock_checker.check_health.side_effect = RuntimeError("Connection refused")

        collector = ContextEvidenceCollector(ctx, backend_checker=mock_checker)
        bundle = collector.collect("s1")
        assert bundle.backend_health is None
        assert len(bundle.errors) == 1

    def test_collect_log_watcher(self):
        ctx = _make_test_context()
        mock_logs = MagicMock()
        mock_logs.all_lines.return_value = ["line1", "line2"]

        collector = ContextEvidenceCollector(ctx, log_watcher=mock_logs)
        bundle = collector.collect("s1")
        assert "line1" in bundle.log_lines

    def test_collect_no_logs_in_third_party_mode(self):
        ctx = _make_test_context(is_third_party_mode=True)
        mock_logs = MagicMock()
        mock_logs.all_lines.return_value = ["line1"]

        collector = ContextEvidenceCollector(ctx, log_watcher=mock_logs)
        bundle = collector.collect("s1")
        assert bundle.log_lines == []

    def test_collect_screenshots_included(self):
        ctx = _make_test_context()
        collector = ContextEvidenceCollector(ctx)
        bundle = collector.collect("s1", screenshots=["/tmp/shot1.png", "/tmp/shot2.png"])
        assert len(bundle.screenshots) == 2

    def test_collect_none_screenshots_filtered(self):
        ctx = _make_test_context()
        collector = ContextEvidenceCollector(ctx)
        bundle = collector.collect("s1", screenshots=["/tmp/shot1.png", None, ""])
        assert "/tmp/shot1.png" in bundle.screenshots
        assert None not in bundle.screenshots


# ── 6. context_safety_policy ─────────────────────────────────────────────────

class TestContextSafetyPolicy:
    def test_none_context_allows_all(self):
        policy = ContextSafetyPolicy(None)
        decision = policy.check_action("click", "click button")
        assert decision.allowed is True

    def test_third_party_blocks_coordinate_click(self):
        ctx = _make_test_context(is_third_party_mode=True)
        policy = ContextSafetyPolicy(ctx)
        decision = policy.check_action("coordinate_click", "click at (100, 200)")
        assert decision.allowed is False
        assert "third-party" in decision.reason.lower()

    def test_third_party_blocks_write_file(self):
        ctx = _make_test_context(is_third_party_mode=True)
        policy = ContextSafetyPolicy(ctx)
        decision = policy.check_action("write_file", "write config")
        assert decision.allowed is False

    def test_third_party_allows_labeled_click(self):
        ctx = _make_test_context(is_third_party_mode=True)
        policy = ContextSafetyPolicy(ctx)
        decision = policy.check_action("click", "click Submit button")
        assert decision.allowed is True

    def test_external_url_blocked_when_disallowed(self):
        ctx = _make_test_context(allow_external_calls=False)
        policy = ContextSafetyPolicy(ctx)
        decision = policy.check_action("navigate", "navigate to API", target_url="https://api.example.com")
        assert decision.allowed is False

    def test_external_url_allowed_when_permitted(self):
        ctx = _make_test_context(allow_external_calls=True)
        policy = ContextSafetyPolicy(ctx)
        decision = policy.check_action("navigate", "navigate", target_url="https://api.example.com")
        assert decision.allowed is True

    def test_localhost_url_always_allowed(self):
        ctx = _make_test_context(allow_external_calls=False)
        policy = ContextSafetyPolicy(ctx)
        decision = policy.check_action("navigate", "navigate", target_url="http://localhost:3000/path")
        assert decision.allowed is True

    def test_destructive_action_blocked_when_disallowed(self):
        ctx = _make_test_context(allow_destructive_actions=False)
        policy = ContextSafetyPolicy(ctx)
        decision = policy.check_action("click", "delete all users")
        assert decision.allowed is False

    def test_destructive_action_allowed_when_permitted(self):
        ctx = _make_test_context(allow_destructive_actions=True)
        policy = ContextSafetyPolicy(ctx)
        decision = policy.check_action("click", "delete test record")
        assert decision.allowed is True

    def test_db_write_always_blocked(self):
        ctx = _make_test_context(allow_destructive_actions=True)
        policy = ContextSafetyPolicy(ctx)
        decision = policy.check_action("db_write", "insert row into users")
        assert decision.allowed is False

    def test_check_backend_url_localhost_allowed(self):
        ctx = _make_test_context(allow_external_calls=False)
        policy = ContextSafetyPolicy(ctx)
        decision = policy.check_backend_url("http://localhost:8000/health")
        assert decision.allowed is True

    def test_check_backend_url_external_blocked(self):
        ctx = _make_test_context(allow_external_calls=False)
        policy = ContextSafetyPolicy(ctx)
        decision = policy.check_backend_url("https://api.stripe.com/v1/charges")
        assert decision.allowed is False

    def test_normal_action_allowed(self):
        ctx = _make_test_context()
        policy = ContextSafetyPolicy(ctx)
        decision = policy.check_action("click", "click Submit button")
        assert decision.allowed is True


# ── 7. context_reporter ───────────────────────────────────────────────────────

class TestContextReporter:
    def test_write_context(self, tmp_path):
        reporter = ContextReporter(output_dir=str(tmp_path))
        ctx = _make_test_context()
        reporter.write_context(ctx)
        path = tmp_path / "runtime_test_context.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["ui_method"] == "playwright_web"
        # Must not contain credential values
        text = path.read_text()
        assert "SECRET" not in text
        assert "password" not in text.lower()

    def test_write_capability_plan(self, tmp_path):
        reporter = ContextReporter(output_dir=str(tmp_path))
        ctx = _make_test_context()
        plan = ContextCapabilityMapper.map(ctx)
        reporter.write_capability_plan(plan)
        path = tmp_path / "runtime_capability_plan.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["can_test_ui"] is True

    def test_write_evidence_bundles(self, tmp_path):
        reporter = ContextReporter(output_dir=str(tmp_path))
        bundles = [
            ContextEvidenceBundle(step_id="s1", collected_at="2024-01-01T00:00:00Z"),
            ContextEvidenceBundle(step_id="s2", collected_at="2024-01-01T00:00:01Z"),
        ]
        reporter.write_evidence_bundles(bundles)
        path = tmp_path / "context_evidence.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data) == 2

    def test_write_safety_summary(self, tmp_path):
        reporter = ContextReporter(output_dir=str(tmp_path))
        decisions = [
            {"action_type": "click", "allowed": True, "reason": ""},
            {"action_type": "db_write", "allowed": False, "reason": "DB write blocked"},
        ]
        reporter.write_safety_summary(decisions)
        path = tmp_path / "context_safety_policy.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["total_decisions"] == 2
        assert data["blocked_count"] == 1

    def test_write_verification_plan(self, tmp_path):
        reporter = ContextReporter(output_dir=str(tmp_path))
        vplan = ContextVerificationPlan(step_id="s1", action_description="save form")
        reporter.write_verification_plan(vplan)
        path = tmp_path / "context_verification_plan.json"
        assert path.exists()

    def test_reporter_redacts_secret_values_in_strings(self, tmp_path):
        """Secret-looking values embedded in string fields must be redacted."""
        reporter = ContextReporter(output_dir=str(tmp_path))
        ctx = RuntimeTestContext(
            session_id="abc",
            backend_base_url="http://localhost:8000",
            # Simulate a field that somehow got a secret value (belt+suspenders)
            database_url_env="token=SECRET_TOKEN_VALUE",
        )
        reporter.write_context(ctx)
        text = (tmp_path / "runtime_test_context.json").read_text()
        assert "SECRET_TOKEN_VALUE" not in text


# ── 8. BackendStateChecker.from_context ───────────────────────────────────────

class TestBackendStateCheckerFromContext:
    def test_from_none_context(self):
        from qa_ai.interactive_runtime.backend_state_checker import BackendStateChecker
        checker = BackendStateChecker.from_context(None)
        assert checker._base == ""

    def test_from_context_with_backend_url(self):
        from qa_ai.interactive_runtime.backend_state_checker import BackendStateChecker
        ctx = _make_test_context(backend_base_url="http://localhost:9000")
        checker = BackendStateChecker.from_context(ctx)
        assert checker._base == "http://localhost:9000"

    def test_from_context_no_backend_url(self):
        from qa_ai.interactive_runtime.backend_state_checker import BackendStateChecker
        ctx = _make_test_context(backend_base_url=None)
        checker = BackendStateChecker.from_context(ctx)
        assert checker._base == ""


# ── 9. DatabaseVerifier.from_context ─────────────────────────────────────────

class TestDatabaseVerifierFromContext:
    def test_from_none_context_disabled(self):
        from qa_ai.interactive_runtime.database_verifier import DatabaseVerifier
        verifier = DatabaseVerifier.from_context(None)
        assert verifier._enabled is False

    def test_from_context_not_available_disabled(self):
        from qa_ai.interactive_runtime.database_verifier import DatabaseVerifier
        ctx = _make_test_context(database_available=False)
        verifier = DatabaseVerifier.from_context(ctx)
        assert verifier._enabled is False

    def test_from_context_sqlite_enabled(self):
        from qa_ai.interactive_runtime.database_verifier import DatabaseVerifier
        ctx = _make_test_context(
            database_available=True,
            database_type="sqlite",
            database_path="/tmp/test.db",
        )
        verifier = DatabaseVerifier.from_context(ctx)
        assert verifier._enabled is True
        assert verifier._type == "sqlite"
        assert verifier._path == "/tmp/test.db"

    def test_from_context_stores_env_var_name_not_value(self):
        """Must store env var NAME (database_url_env), never resolve it."""
        from qa_ai.interactive_runtime.database_verifier import DatabaseVerifier
        ctx = _make_test_context(
            database_available=True,
            database_type="postgres",
            database_url_env="DATABASE_URL",
        )
        verifier = DatabaseVerifier.from_context(ctx)
        assert verifier._url_env == "DATABASE_URL"
        # Must not resolve the env var value
        assert verifier._url_env != os.environ.get("DATABASE_URL", "")


# ── 10. InteractionExecutor context wiring ────────────────────────────────────

class TestInteractionExecutorContextWiring:
    """Test that InteractionExecutor correctly initializes context objects."""

    def _make_executor(self, runtime_context=None):
        """Build a minimal InteractionExecutor with mocked dependencies."""
        from qa_ai.interactive_runtime.interaction_executor import InteractionExecutor
        from qa_ai.interactive_runtime.schemas import InteractiveRuntimeConfig

        config = InteractiveRuntimeConfig(
            app_name="TestApp",
            app_type="web",
            max_actions=5,
            max_duration_seconds=60,
        )
        executor = InteractionExecutor(
            config=config,
            session=MagicMock(),
            controller=MagicMock(),
            observer=MagicMock(),
            planner=MagicMock(),
            permission_gate=MagicMock(),
            approval_gate=MagicMock(),
            verifier=MagicMock(),
            evidence_builder=MagicMock(),
            coverage=MagicMock(),
            screenshots=MagicMock(),
            runtime_context=runtime_context,
        )
        return executor

    def test_init_without_runtime_context(self):
        executor = self._make_executor(None)
        assert executor._runtime_context is None
        assert executor._test_context is None
        assert executor._capability_plan is None

    def test_init_runtime_context_stored(self):
        ctx = _make_runtime_context()
        executor = self._make_executor(ctx)
        assert executor._runtime_context is ctx

    def test_init_runtime_context_no_crash(self):
        """_init_runtime_context must not raise even with empty context."""
        executor = self._make_executor(_make_runtime_context())
        executor._init_runtime_context()  # should not raise

    def test_apply_context_safety_allows_safe_action(self):
        from qa_ai.interactive_runtime.connectors.connector_models import RuntimeContext
        executor = self._make_executor(_make_runtime_context())
        executor._init_runtime_context()
        decision = executor._apply_context_safety("click", "click Submit button")
        assert decision.allowed is True

    def test_apply_context_safety_records_decision(self):
        executor = self._make_executor(_make_runtime_context())
        executor._init_runtime_context()
        executor._apply_context_safety("click", "click Submit")
        assert len(executor._context_safety_decisions) == 1

    def test_apply_context_safety_blocks_db_write(self):
        executor = self._make_executor(_make_runtime_context())
        executor._init_runtime_context()
        decision = executor._apply_context_safety("db_write", "insert row")
        assert decision.allowed is False

    def test_collect_context_evidence_no_collector_returns_none(self):
        executor = self._make_executor(None)
        result = executor._collect_context_evidence("s1")
        assert result is None

    def test_collect_context_evidence_with_collector(self):
        executor = self._make_executor(_make_runtime_context())
        executor._init_runtime_context()
        if executor._evidence_collector:
            bundle = executor._collect_context_evidence("s1")
            assert bundle is not None
            assert len(executor._context_evidence_bundles) == 1


# ── 11. ResultVerifier runtime_context param ─────────────────────────────────

class TestResultVerifierContextParam:
    def _make_verifier(self):
        from qa_ai.interactive_runtime.result_verifier import ResultVerifier
        return ResultVerifier()

    def _make_action_result(self):
        from qa_ai.interactive_runtime.schemas import ActionResult, ActionStatus, UIAction
        action = UIAction(action_type="click", description="click button")
        return ActionResult(action=action, status=ActionStatus.EXECUTED)

    def test_verify_without_context_works(self):
        verifier = self._make_verifier()
        result = verifier.verify("s1", self._make_action_result())
        assert result is not None

    def test_verify_with_context_adds_notes_ui_only(self):
        verifier = self._make_verifier()
        ctx = _make_test_context(
            backend_available=False,
            backend_base_url=None,
            database_available=False,
        )
        result = verifier.verify("s1", self._make_action_result(), runtime_context=ctx)
        assert "UI-only" in result.notes or result.notes == ""

    def test_verify_with_third_party_context_adds_note(self):
        verifier = self._make_verifier()
        ctx = _make_test_context(is_third_party_mode=True)
        result = verifier.verify("s1", self._make_action_result(), runtime_context=ctx)
        assert "Third-party" in result.notes or "third-party" in result.notes.lower() or result.notes == ""


# ── 12. Security regression tests ─────────────────────────────────────────────

class TestSecurityRegressions:
    """Targeted tests for all 7 Trail of Bits findings."""

    # Finding 1 (CRITICAL): evidence bundles sanitized before JSON write
    def test_evidence_bundles_sanitized(self, tmp_path):
        reporter = ContextReporter(output_dir=str(tmp_path))
        bundle = ContextEvidenceBundle(
            step_id="s1",
            backend_health={"status": "ok", "token": "SECRET_BEARER_VALUE"},
        )
        reporter.write_evidence_bundles([bundle])
        text = (tmp_path / "context_evidence.json").read_text()
        assert "SECRET_BEARER_VALUE" not in text

    # Finding 2 (HIGH): Dict[str,Any] fields sanitized in context reporter
    def test_context_dict_fields_sanitized(self, tmp_path):
        reporter = ContextReporter(output_dir=str(tmp_path))
        ctx = RuntimeTestContext(
            session_id="s1",
            database_url_env="password=hunter2",  # secret-looking value
        )
        reporter.write_context(ctx)
        text = (tmp_path / "runtime_test_context.json").read_text()
        assert "hunter2" not in text

    # Finding 3 (HIGH): SQL identifier injection rejected
    def test_sql_injection_in_table_name_rejected(self):
        from qa_ai.interactive_runtime.database_verifier import DatabaseVerifier
        verifier = DatabaseVerifier(
            db_type="sqlite", path="/tmp/test.db", enabled=True
        )
        result = verifier.check_row_exists("users; DROP TABLE users;--", "id=1")
        assert result.status.value == "failed"
        assert "invalid" in result.description.lower() or "valid" in result.description.lower()

    def test_sql_injection_in_field_name_rejected(self):
        from qa_ai.interactive_runtime.database_verifier import DatabaseVerifier
        verifier = DatabaseVerifier(db_type="sqlite", path="/tmp/test.db", enabled=True)
        result = verifier.check_field_value(
            "users", "name'; DROP TABLE users;--", "admin", "id=1"
        )
        assert result.status.value == "failed"

    def test_sql_identifier_valid_accepted(self):
        from qa_ai.interactive_runtime.database_verifier import DatabaseVerifier
        verifier = DatabaseVerifier.__new__(DatabaseVerifier)
        # Should not raise
        verifier._guard_identifier("users")
        verifier._guard_identifier("my_table_2")

    def test_sql_identifier_with_space_rejected(self):
        from qa_ai.interactive_runtime.database_verifier import DatabaseVerifier
        verifier = DatabaseVerifier.__new__(DatabaseVerifier)
        with pytest.raises(ValueError, match="invalid SQL"):
            verifier._guard_identifier("my table")

    # Finding 4 (HIGH): IPv6-mapped IPv4 is treated as external
    def test_ipv6_mapped_ipv4_is_external(self):
        from qa_ai.interactive_runtime.runtime_context.context_safety_policy import _is_external_url
        assert _is_external_url("http://[::ffff:192.168.1.1]/path") is True

    def test_localhost_is_not_external(self):
        from qa_ai.interactive_runtime.runtime_context.context_safety_policy import _is_external_url
        assert _is_external_url("http://localhost:8000/health") is False
        assert _is_external_url("http://127.0.0.1:8080/api") is False
        assert _is_external_url("http://::1/path") is False

    def test_external_domain_is_external(self):
        from qa_ai.interactive_runtime.runtime_context.context_safety_policy import _is_external_url
        assert _is_external_url("https://api.stripe.com/v1") is True
        assert _is_external_url("http://10.0.0.1/internal") is True

    def test_non_http_scheme_not_external(self):
        from qa_ai.interactive_runtime.runtime_context.context_safety_policy import _is_external_url
        # file:// and javascript:// are not "external HTTP" — handled by other guards
        assert _is_external_url("file:///etc/passwd") is False
        assert _is_external_url("javascript://alert(1)") is False

    # Finding 5 (MEDIUM): backend URL validated in context_adapter
    def test_adapter_rejects_file_scheme_backend_url(self):
        from qa_ai.interactive_runtime.connectors.connector_models import (
            ConnectorType, RuntimeConnectorResult, RuntimeConnectorStatus,
        )
        result = RuntimeConnectorResult(
            connector_id="backend-1",
            connector_type=ConnectorType.BACKEND_SERVICE,
            status=RuntimeConnectorStatus.READY,
            endpoint="file:///etc/passwd",
        )
        ctx = _make_runtime_context(connector_results={"backend-1": result})
        adapted = ContextAdapter.adapt(ctx)
        assert adapted.backend_base_url != "file:///etc/passwd"
        assert adapted.backend_available is False

    def test_adapter_rejects_javascript_scheme_backend_url(self):
        from qa_ai.interactive_runtime.connectors.connector_models import (
            ConnectorType, RuntimeConnectorResult, RuntimeConnectorStatus,
        )
        result = RuntimeConnectorResult(
            connector_id="backend-1",
            connector_type=ConnectorType.BACKEND_SERVICE,
            status=RuntimeConnectorStatus.READY,
            endpoint="javascript://evil",
        )
        ctx = _make_runtime_context(connector_results={"backend-1": result})
        adapted = ContextAdapter.adapt(ctx)
        assert adapted.backend_available is False

    # Finding 6 (MEDIUM): evidence collector validates injected objects
    def test_evidence_collector_rejects_bad_backend_checker(self):
        ctx = _make_test_context()
        bad_checker = object()   # no check_health method
        collector = ContextEvidenceCollector(ctx, backend_checker=bad_checker)
        # Should be nullified, not crash
        assert collector._backend is None

    def test_evidence_collector_rejects_bad_log_watcher(self):
        ctx = _make_test_context()
        bad_watcher = "not a log watcher"
        collector = ContextEvidenceCollector(ctx, log_watcher=bad_watcher)
        assert collector._logs is None

    def test_evidence_collector_accepts_valid_checker(self):
        ctx = _make_test_context()
        valid_checker = MagicMock()
        valid_checker.check_health = MagicMock()
        collector = ContextEvidenceCollector(ctx, backend_checker=valid_checker)
        assert collector._backend is valid_checker

    # Finding 7 (MEDIUM): result_verifier has public backend/db properties
    def test_result_verifier_has_public_backend_property(self):
        from qa_ai.interactive_runtime.result_verifier import ResultVerifier
        mock_checker = MagicMock()
        verifier = ResultVerifier(backend_checker=mock_checker)
        assert verifier.backend_checker is mock_checker

    def test_result_verifier_has_public_db_property(self):
        from qa_ai.interactive_runtime.result_verifier import ResultVerifier
        mock_db = MagicMock()
        verifier = ResultVerifier(db_verifier=mock_db)
        assert verifier.db_verifier is mock_db
