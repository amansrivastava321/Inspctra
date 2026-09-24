"""
context_models.py - Normalized context models for the interactive test loop.

RuntimeTestContext: clean view of runtime state for InteractionExecutor.
RuntimeCapabilityPlan: which test methods are available given the context.
ContextEvidenceBundle: aggregated evidence from all runtime sources.
ContextVerificationPlan: per-action checks to run.

No raw connector plumbing. No secrets. All credential fields hold env-var
names only (never values).
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UITestMethod(str, Enum):
    PLAYWRIGHT_WEB = "playwright_web"
    APPIUM_ANDROID = "appium_android"
    APPIUM_IOS = "appium_ios"
    DESKTOP_ACCESSIBILITY = "desktop_accessibility"
    SCREENSHOT_DIFF = "screenshot_diff"
    NONE = "none"


class VerificationMethod(str, Enum):
    BACKEND_API = "backend_api"
    DATABASE_READ = "database_read"
    LOG_WATCHER = "log_watcher"
    UI_STATE = "ui_state"
    SCREENSHOT = "screenshot"
    AI_ORACLE = "ai_oracle"


class EvidenceSource(str, Enum):
    BACKEND_HEALTH = "backend_health"
    DATABASE_STATE = "database_state"
    CONNECTOR_LOGS = "connector_logs"
    PROCESS_ALIVE = "process_alive"
    SCREENSHOT = "screenshot"
    LOG_LINES = "log_lines"


class RuntimeTestContext(BaseModel):
    """
    Normalized, secret-free view of RuntimeContext for use by:
    - InteractionExecutor
    - ResultVerifier
    - BackendStateChecker
    - DatabaseVerifier

    Security: no credentials here. Credential fields hold env-var NAMES only.
    """

    session_id: str = ""
    connectors_ready: bool = False

    # UI control
    ui_method: UITestMethod = UITestMethod.NONE
    browser_url: Optional[str] = None           # URL open in browser
    appium_server_url: Optional[str] = None     # Appium server (localhost only)
    appium_caps: Dict[str, Any] = Field(default_factory=dict)
    desktop_window_title: Optional[str] = None  # desktop window to control

    # Backend verification
    backend_base_url: Optional[str] = None      # API base for BackendStateChecker
    backend_available: bool = False

    # Database verification (env var NAMES only — never values)
    database_available: bool = False
    database_type: Optional[str] = None         # sqlite | postgres | supabase
    database_path: Optional[str] = None         # SQLite path only
    database_url_env: Optional[str] = None      # env var name, not value

    # AI model
    ai_model_available: bool = False
    ai_model_name: Optional[str] = None

    # Docker
    docker_services_running: List[str] = Field(default_factory=list)

    # Blocked / missing
    blocked_connector_ids: List[str] = Field(default_factory=list)
    missing_capabilities: List[str] = Field(default_factory=list)

    # Safety flags (propagated from connector configs)
    is_third_party_mode: bool = False
    allow_external_calls: bool = False
    allow_destructive_actions: bool = False

    created_at: str = ""


class RuntimeCapabilityPlan(BaseModel):
    """
    Maps RuntimeTestContext to available test methods.
    Consumed by InteractionExecutor to decide what verification to run.
    """

    ui_methods_available: List[UITestMethod] = Field(default_factory=list)
    verification_methods_available: List[VerificationMethod] = Field(default_factory=list)
    evidence_sources_available: List[EvidenceSource] = Field(default_factory=list)

    # Methods blocked and why
    blocked_methods: Dict[str, str] = Field(default_factory=dict)

    # Confidence adjustments per method (multiplier 0-1)
    confidence_adjustments: Dict[str, float] = Field(default_factory=dict)

    # Summary flags
    can_test_ui: bool = False
    can_verify_backend: bool = False
    can_verify_database: bool = False
    can_collect_logs: bool = False
    has_screenshot_support: bool = False


class ContextEvidenceBundle(BaseModel):
    """
    Aggregated evidence from all available runtime sources for one step.
    Produced by ContextEvidenceCollector.
    """

    step_id: str = ""
    backend_health: Optional[Dict[str, Any]] = None
    database_snapshot: Optional[Dict[str, Any]] = None
    connector_logs: List[str] = Field(default_factory=list)
    process_pids: Dict[str, int] = Field(default_factory=dict)
    screenshots: List[str] = Field(default_factory=list)
    log_lines: List[str] = Field(default_factory=list)
    collected_at: str = ""
    errors: List[str] = Field(default_factory=list)


class ContextVerificationPlan(BaseModel):
    """
    Per-action verification plan derived from RuntimeTestContext.
    Tells ResultVerifier what checks to run.
    """

    step_id: str = ""
    action_description: str = ""
    run_backend_health: bool = False
    backend_health_path: str = "/health"
    run_db_row_check: bool = False
    db_table: Optional[str] = None
    db_where: Optional[str] = None
    run_log_tag_check: bool = False
    log_tags: List[str] = Field(default_factory=list)
    run_ui_text_check: bool = False
    expected_ui_text: List[str] = Field(default_factory=list)
    confidence_floor: float = 0.0
    notes: List[str] = Field(default_factory=list)
