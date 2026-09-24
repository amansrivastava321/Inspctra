"""
connector_models.py - Pydantic models for the Live Runtime Connector Layer.

No app-specific logic. All models are generic across connector types and platforms.

Security:
- No secrets in model fields; credential fields hold env-var names only.
- launch_command is stored as a list (parsed from string on load); never passed to shell.
- database_url_env / api_key_env hold env-var names, not values.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── enums ─────────────────────────────────────────────────────────────────────

class ConnectorType(str, Enum):
    WEB_BROWSER = "web_browser"
    DESKTOP_APP = "desktop_app"
    MOBILE_APP = "mobile_app"
    BACKEND_SERVICE = "backend_service"
    DATABASE = "database"
    DOCKER_SERVICE = "docker_service"
    AI_MODEL = "ai_model"
    THIRD_PARTY_APP = "third_party_app"
    FILE_SYSTEM = "file_system"
    API_SERVICE = "api_service"
    EMULATOR = "emulator"
    SIMULATOR = "simulator"
    SERVICE_PROCESS = "service_process"


class RuntimeConnectorStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"
    FAILED = "failed"
    SKIPPED = "skipped"
    CAPABILITY_GAP = "capability_gap"


class ReadinessCheckType(str, Enum):
    HTTP_URL = "http_url"
    TCP_PORT = "tcp_port"
    PROCESS_ALIVE = "process_alive"
    FILE_EXISTS = "file_exists"
    COMMAND_EXIT_ZERO = "command_exit_zero"
    DATABASE_QUERY = "database_query"
    APPIUM_SERVER = "appium_server"
    OLLAMA_MODEL = "ollama_model"
    BROWSER_PAGE = "browser_page"
    DEVICE_VISIBLE = "device_visible"
    WINDOW_FOUND = "window_found"


class ConnectorMode(str, Enum):
    LAUNCH = "launch"        # connector starts the process
    ATTACH = "attach"        # connector attaches to already-running process
    CHECK_ONLY = "check_only"  # connector only verifies availability


# ── sub-models ────────────────────────────────────────────────────────────────

class ReadinessCheck(BaseModel):
    """One readiness verification step."""
    check_type: ReadinessCheckType
    target: str = ""              # URL, port, file path, command, etc.
    expected: str = ""            # expected value/pattern
    timeout_seconds: int = 30
    result: Optional[bool] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    checked_at: Optional[str] = None


class ConnectorCapabilityGap(BaseModel):
    """Describes a missing capability that prevents a connector from working."""
    gap_id: str
    description: str
    setup_instructions: List[str] = Field(default_factory=list)
    required_tool: Optional[str] = None
    docs_url: Optional[str] = None


# ── main config ───────────────────────────────────────────────────────────────

class RuntimeConnectorConfig(BaseModel):
    """
    Configuration for one runtime connector.

    Security:
    - launch_command stored as raw string; parsed to list before subprocess call.
    - database_url_env / api_key_env store ENV VAR NAMES only, never values.
    - requires_permission=True gates every action behind user approval.
    """

    connector_id: str
    connector_type: ConnectorType
    name: str = ""
    enabled: bool = True
    mode: ConnectorMode = ConnectorMode.LAUNCH
    required: bool = True   # if True, failure blocks the test target

    # process / service launch
    launch_command: str = ""
    working_dir: str = "."
    env_passthrough: List[str] = Field(default_factory=list)  # env var names to forward

    # readiness
    readiness_url: Optional[str] = None
    readiness_port: Optional[int] = None
    healthcheck_command: str = ""
    readiness_timeout_seconds: int = 60

    # process identity
    process_name: Optional[str] = None

    # app-specific (used by desktop/mobile connectors)
    app_type: Optional[str] = None   # web | android | ios | native_macos | native_windows | native_linux | electron
    package_name: Optional[str] = None   # Android package name
    bundle_id: Optional[str] = None      # iOS/macOS bundle ID
    app_path: Optional[str] = None       # path to .app / .apk / .ipa
    app_window_title: Optional[str] = None  # for window-based attach

    # Docker
    docker_compose_file: Optional[str] = None
    docker_service: Optional[str] = None

    # Database (env var names — never actual credentials)
    database_type: Optional[str] = None    # sqlite | postgres | supabase | mysql
    database_url_env: Optional[str] = None
    database_path: Optional[str] = None    # SQLite path

    # API / backend
    api_base_url: Optional[str] = None

    # AI model
    model_provider: Optional[str] = None   # ollama | local
    model_name: Optional[str] = None

    # safety gates
    requires_permission: bool = True
    allow_external_calls: bool = False
    allow_destructive_actions: bool = False

    timeout_seconds: int = 120
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("readiness_url", mode="before")
    @classmethod
    def _validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # basic guard: must be http/https only; enforced further in connectors
        v = str(v).strip()
        if v and not v.startswith(("http://", "https://")):
            raise ValueError(f"readiness_url must start with http:// or https://, got: {v!r}")
        return v


class RuntimeConnectorsConfig(BaseModel):
    """Top-level runtime_connectors section in interactive_runtime.yaml."""
    enabled: bool = True
    stop_on_failure: bool = True   # if required connector fails, block the target
    stop_after_test: bool = True   # stop launched connectors after test completes
    connectors: List[RuntimeConnectorConfig] = Field(default_factory=list)


# ── result models ─────────────────────────────────────────────────────────────

class RuntimeConnectorResult(BaseModel):
    """Result from one connector's connect_or_launch call."""
    connector_id: str
    connector_type: ConnectorType
    name: str = ""
    status: RuntimeConnectorStatus = RuntimeConnectorStatus.PENDING
    readiness: Optional[bool] = None
    endpoint: Optional[str] = None      # URL or address usable by tests
    process_id: Optional[int] = None
    driver_backend: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    logs: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    setup_instructions: List[str] = Field(default_factory=list)
    capability_gaps: List[ConnectorCapabilityGap] = Field(default_factory=list)
    readiness_checks: List[ReadinessCheck] = Field(default_factory=list)
    connected_at: Optional[str] = None
    stopped_at: Optional[str] = None
    duration_seconds: float = 0.0


class RuntimeContext(BaseModel):
    """
    Combined runtime context handed to InteractionExecutor after all connectors ready.
    Each field holds the endpoint/address/session info the test loop needs.
    """
    session_id: str = ""
    connectors_ready: bool = False

    # Per-type context fields (all optional; populated when connector is ready)
    browser_endpoint: Optional[str] = None       # URL opened in browser
    backend_base_url: Optional[str] = None       # backend API base URL
    appium_server_url: Optional[str] = None      # Appium server URL
    appium_capabilities: Dict[str, Any] = Field(default_factory=dict)
    database_available: bool = False
    database_type: Optional[str] = None
    ai_model_available: bool = False
    ai_model_name: Optional[str] = None
    docker_services_running: List[str] = Field(default_factory=list)

    # raw connector results indexed by connector_id
    connector_results: Dict[str, RuntimeConnectorResult] = Field(default_factory=dict)

    # evidence from all connectors
    connector_evidence: Dict[str, Any] = Field(default_factory=dict)

    # overall gaps
    capability_gaps: List[ConnectorCapabilityGap] = Field(default_factory=list)
    blocked_connector_ids: List[str] = Field(default_factory=list)

    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
