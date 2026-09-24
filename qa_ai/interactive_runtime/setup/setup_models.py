"""
setup_models.py - Pydantic models for the Runtime Environment Doctor + Auto-Setup.

No app-specific logic. All fields are generic across platforms and app_types.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── enums ─────────────────────────────────────────────────────────────────────

class ActionType(str, Enum):
    CREATE_VENV = "create_venv"
    INSTALL_PYTHON_PACKAGE = "install_python_package"
    RUN_PLAYWRIGHT_INSTALL = "run_playwright_install"
    INSTALL_APPIUM_CLIENT = "install_appium_client"
    INSTALL_NPM_PACKAGE = "install_npm_package"        # npm install -g appium (approval required)
    INSTALL_APPIUM_DRIVER = "install_appium_driver"    # appium driver install uiautomator2/xcuitest
    PULL_OLLAMA_MODEL = "pull_ollama_model"            # ollama pull <model>
    CHECK_APPIUM_SERVER = "check_appium_server"
    OPEN_SYSTEM_SETTINGS = "open_system_settings"
    SHOW_MANUAL_STEPS = "show_manual_steps"
    VERIFY_PERMISSION = "verify_permission"
    WAIT_FOR_USER = "wait_for_user"
    NO_OP = "no_op"


class ActionRisk(str, Enum):
    SAFE = "safe"               # pip install in venv
    LOW = "low"                 # open settings app (read-only side effect)
    MEDIUM = "medium"           # create venv, non-venv installs
    HIGH = "high"               # global install, system-level changes
    REQUIRES_USER = "requires_user"  # OS permission — user must act manually


class ActionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    SKIPPED = "skipped"
    COMPLETED = "completed"
    FAILED = "failed"


# ── action ────────────────────────────────────────────────────────────────────

class SetupAction(BaseModel):
    """One atomic setup step."""

    action_id: str
    action_type: ActionType
    title: str
    description: str

    # subprocess call in list form — NEVER shell=True
    command: Optional[List[str]] = None
    working_dir: str = "."

    requires_permission: bool = True
    risk_level: ActionRisk = ActionRisk.SAFE

    # Only True for SAFE package installs that --yes can auto-approve
    can_auto_run: bool = False

    reason: str = ""
    rollback_info: str = ""
    verification_check: str = ""   # description of what to re-check after
    manual_steps: List[str] = Field(default_factory=list)

    status: ActionStatus = ActionStatus.PENDING
    output: Optional[str] = None
    error: Optional[str] = None


class SetupActionResult(BaseModel):
    action_id: str
    action_type: ActionType
    status: ActionStatus
    output: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0


# ── plan ──────────────────────────────────────────────────────────────────────

class SetupPlan(BaseModel):
    """Complete setup plan produced by SetupPlanner."""

    plan_id: str
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    platform: str = ""
    python_executable: str = ""
    venv_active: bool = False

    target_configs_checked: List[str] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)
    missing_capabilities: List[str] = Field(default_factory=list)

    actions: List[SetupAction] = Field(default_factory=list)

    # Split for reporting
    safe_auto_actions: List[str] = Field(default_factory=list)     # action_ids
    user_required_actions: List[str] = Field(default_factory=list)  # action_ids
    blocked_actions: List[str] = Field(default_factory=list)        # action_ids

    estimated_readiness_after_setup: int = 0  # 0-100


# ── doctor report ─────────────────────────────────────────────────────────────

class DriverReadiness(BaseModel):
    app_type: str
    driver_type: str
    status: str   # ready | not_available | missing_deps | permission_denied
    missing_deps: List[str] = Field(default_factory=list)
    setup_instructions: List[str] = Field(default_factory=list)


class PackageCheck(BaseModel):
    name: str
    installed: bool
    version: Optional[str] = None
    notes: str = ""


class EnvironmentDoctorReport(BaseModel):
    """Full environment readiness report."""

    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    platform: str = ""
    python_executable: str = ""
    python_version: str = ""
    venv_active: bool = False
    venv_path: Optional[str] = None

    # packages
    playwright_installed: bool = False
    playwright_browsers_installed: bool = False
    appium_client_installed: bool = False
    pywinauto_installed: bool = False
    atspi_installed: bool = False

    # OS permissions / tools
    macos_accessibility_granted: bool = False
    screencapture_available: bool = False
    xdotool_available: bool = False
    scrot_available: bool = False

    # Appium ecosystem (beyond Python client)
    npm_available: bool = False                  # npm command exists on PATH
    appium_command_available: bool = False       # appium command exists on PATH
    appium_uiautomator2_installed: bool = False  # appium driver list shows uiautomator2
    appium_xcuitest_installed: bool = False      # appium driver list shows xcuitest

    # Ollama / vision model
    ollama_configured_model: str = ""            # model name expected by config
    ollama_vision_model_available: bool = False  # configured model found in ollama list

    # services
    appium_server_reachable: bool = False
    appium_server_url: str = "http://localhost:4723"
    ollama_reachable: bool = False
    ollama_models: List[str] = Field(default_factory=list)

    # per-driver readiness
    driver_readiness: List[DriverReadiness] = Field(default_factory=list)

    # context flags exposed to the frontend
    needs_mobile: bool = False  # True when app_types includes mobile targets

    # summary
    missing_items: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    readiness_score: int = 0
    readiness_label: str = "blocked"  # blocked | partial | usable | ready


# ── execution log ─────────────────────────────────────────────────────────────

class SetupExecutionLog(BaseModel):
    """Records what was approved, run, and the outcome."""

    plan_id: str
    started_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: Optional[str] = None
    dry_run: bool = False
    results: List[SetupActionResult] = Field(default_factory=list)
    final_readiness_score: Optional[int] = None
    notes: str = ""
