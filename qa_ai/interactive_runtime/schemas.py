"""
schemas.py - Pydantic models for the Interactive Runtime Testing Layer.

These models represent configuration, live session state, UI elements,
actions, verification results, evidence, coverage, and final reports.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── enums ─────────────────────────────────────────────────────────────────────

class AppType(str, Enum):
    FLUTTER_MACOS = "flutter_macos"
    FLUTTER_WEB = "flutter_web"
    FLUTTER_ANDROID = "flutter_android"
    FLUTTER_IOS = "flutter_ios"
    WEB = "web"
    BACKEND_FASTAPI = "backend_fastapi"
    BACKEND_NODE = "backend_node"
    BACKEND_DJANGO = "backend_django"
    DOCKER_COMPOSE = "docker_compose"
    CUSTOM = "custom"
    NATIVE_MACOS = "native_macos"
    NATIVE_WINDOWS = "native_windows"
    NATIVE_LINUX = "native_linux"
    ANDROID = "android"
    IOS = "ios"
    ELECTRON = "electron"
    FLUTTER_WINDOWS = "flutter_windows"
    FLUTTER_LINUX = "flutter_linux"


class ActionStatus(str, Enum):
    PLANNED = "planned"
    APPROVED = "approved"
    EXECUTED = "executed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class VerificationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class RiskLevel(str, Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DESTRUCTIVE = "destructive"
    EXTERNAL_COST = "external_cost"
    PRODUCTION_RISK = "production_risk"


class FunctionStatus(str, Enum):
    DISCOVERED = "discovered"
    ATTEMPTED = "attempted"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    INCONCLUSIVE = "inconclusive"


class PermissionDecision(str, Enum):
    APPROVED_ONCE = "approved_once"
    APPROVED_ALL = "approved_all"
    DENIED = "denied"
    SKIPPED = "skipped"


class CapabilityStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PARTIAL = "partial"


class AutomationBackend(str, Enum):
    PLAYWRIGHT = "playwright"
    MACOS_ACCESSIBILITY = "macos_accessibility"
    WINDOWS_UIA = "windows_uia"
    LINUX_ATSPI = "linux_atspi"
    ANDROID_APPIUM = "android_appium"
    IOS_APPIUM = "ios_appium"
    VISION_FALLBACK = "vision_fallback"
    NULL = "null"


class DriverStatus(str, Enum):
    READY = "ready"
    NOT_AVAILABLE = "not_available"
    PERMISSION_DENIED = "permission_denied"
    INITIALIZING = "initializing"


class ActionConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ── configuration ─────────────────────────────────────────────────────────────

class DatabaseConfig(BaseModel):
    type: str = "sqlite"                     # sqlite | postgres | supabase
    enabled: bool = False
    read_only: bool = True
    path: Optional[str] = None               # SQLite path
    url_env: Optional[str] = None            # env var holding DB URL
    key_env: Optional[str] = None            # env var holding service key


class LogConfig(BaseModel):
    capture_stdout: bool = True
    capture_stderr: bool = True
    expected_tags: List[str] = Field(default_factory=list)
    redact_patterns: List[str] = Field(default_factory=list)


class PermissionsConfig(BaseModel):
    launch_app: str = "ask"                  # ask | auto | deny
    interact_with_ui: str = "ask"
    take_screenshots: str = "ask"
    call_external_apis: str = "ask"
    call_ai_providers: str = "ask"
    modify_database: str = "ask"
    destructive_actions: str = "always_ask"


class UIAutomationConfig(BaseModel):
    preferred_backend: Optional[AutomationBackend] = None
    vision_fallback_enabled: bool = False
    accessibility_timeout_seconds: int = 10


class MacOSConfig(BaseModel):
    bundle_id: Optional[str] = None
    use_applescript: bool = True
    screenshot_tool: str = "screencapture"
    accessibility_permission_prompt: bool = True


class WindowsConfig(BaseModel):
    use_uia: bool = True


class LinuxConfig(BaseModel):
    use_atspi: bool = True
    display: str = ":0"


class MobileConfig(BaseModel):
    appium_enabled: bool = False
    appium_server_url: str = "http://localhost:4723"
    device_name: Optional[str] = None
    platform_version: Optional[str] = None
    app_path: Optional[str] = None
    udid: Optional[str] = None


class VisionFallbackConfig(BaseModel):
    enabled: bool = False
    provider: str = "local_ollama"
    model: str = "qwen2.5vl:7b"
    api_key_env: str = ""
    require_approval: bool = True
    max_coordinate_clicks: int = 20


class InteractiveRuntimeConfig(BaseModel):
    """Top-level config loaded from interactive_runtime.yaml."""
    app_name: str = ""
    app_type: AppType = AppType.WEB
    working_dir: str = "."
    launch_command: str = ""
    readiness_url: Optional[str] = None      # poll this URL until HTTP 200
    readiness_timeout_seconds: int = 60
    permission_required: bool = True
    screenshot_enabled: bool = True
    log_capture_enabled: bool = True
    database_verification_enabled: bool = False
    backend_verification_enabled: bool = False
    dangerous_actions_require_approval: bool = True
    max_actions: int = 100
    max_duration_seconds: int = 1800
    output_dir: str = "artifacts"

    logs: LogConfig = Field(default_factory=LogConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)

    backend_base_url: Optional[str] = None
    test_objectives: List[str] = Field(default_factory=list)

    ui_automation: UIAutomationConfig = Field(default_factory=UIAutomationConfig)
    macos: MacOSConfig = Field(default_factory=MacOSConfig)
    windows: WindowsConfig = Field(default_factory=WindowsConfig)
    linux: LinuxConfig = Field(default_factory=LinuxConfig)
    mobile: MobileConfig = Field(default_factory=MobileConfig)
    vision_fallback: VisionFallbackConfig = Field(default_factory=VisionFallbackConfig)
    ai_runtime: Optional["AIRuntimeConfig"] = None

    # Live Runtime Connector Layer — optional; existing configs work unchanged
    runtime_connectors: Optional[Any] = None  # RuntimeConnectorsConfig (lazy to avoid circular)


# ── driver result models ──────────────────────────────────────────────────────

class WindowInfo(BaseModel):
    title: str = ""
    process_name: str = ""
    pid: Optional[int] = None
    bundle_id: Optional[str] = None
    bounds: Optional[Dict[str, float]] = None


class DriverCapabilities(BaseModel):
    backend: AutomationBackend = AutomationBackend.NULL
    status: DriverStatus = DriverStatus.NOT_AVAILABLE
    can_observe_screen: bool = False
    can_click: bool = False
    can_type: bool = False
    can_screenshot: bool = False
    can_get_accessibility_tree: bool = False
    can_find_windows: bool = False
    can_coordinate_click: bool = False
    notes: List[str] = Field(default_factory=list)
    missing_dependencies: List[str] = Field(default_factory=list)
    setup_instructions: List[str] = Field(default_factory=list)


# ── screen / UI ───────────────────────────────────────────────────────────────

class UIElement(BaseModel):
    element_id: str = ""
    label: str = ""
    element_type: str = ""               # button | input | select | tab | menu | dialog | text | link
    visible: bool = True
    enabled: bool = True
    placeholder: Optional[str] = None
    value: Optional[str] = None
    selector: Optional[str] = None       # CSS selector or accessibility path
    bounding_box: Optional[Dict[str, float]] = None
    risk_level: RiskLevel = RiskLevel.SAFE


class ScreenState(BaseModel):
    screen_id: str = ""
    title: str = ""
    url: Optional[str] = None
    captured_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    elements: List[UIElement] = Field(default_factory=list)
    visible_text: List[str] = Field(default_factory=list)
    has_loading_indicator: bool = False
    has_error_banner: bool = False
    has_modal: bool = False
    screenshot_path: Optional[str] = None
    raw_html_excerpt: Optional[str] = None
    testability_issues: Optional[List[str]] = None

    @property
    def buttons(self) -> List[UIElement]:
        return [e for e in self.elements if e.element_type == "button"]

    @property
    def inputs(self) -> List[UIElement]:
        return [e for e in self.elements if e.element_type == "input"]


# ── actions ───────────────────────────────────────────────────────────────────

class UIAction(BaseModel):
    action_id: str = ""
    action_type: str = ""                # click | type | select | navigate | wait | submit | scroll
    target_element: Optional[UIElement] = None
    input_value: Optional[str] = None
    url: Optional[str] = None
    wait_ms: int = 0
    risk_level: RiskLevel = RiskLevel.SAFE
    requires_approval: bool = False
    description: str = ""
    step_id: Optional[str] = None


class ActionResult(BaseModel):
    action: UIAction = Field(default_factory=UIAction)
    status: ActionStatus = ActionStatus.PLANNED
    screen_before: Optional[ScreenState] = None
    screen_after: Optional[ScreenState] = None
    screenshot_before: Optional[str] = None
    screenshot_after: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: float = 0.0
    executed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── verification ──────────────────────────────────────────────────────────────

class VerificationCheck(BaseModel):
    check_type: str = ""                 # ui_text | ui_element | log_tag | api_response | db_row | file_exists
    description: str = ""
    expected: str = ""
    actual: Optional[str] = None
    status: VerificationStatus = VerificationStatus.INCONCLUSIVE
    evidence_path: Optional[str] = None


class VerificationResult(BaseModel):
    step_id: str = ""
    checks: List[VerificationCheck] = Field(default_factory=list)
    overall_status: VerificationStatus = VerificationStatus.INCONCLUSIVE
    verified_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""

    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.checks if c.status == VerificationStatus.PASSED)

    @property
    def failed_count(self) -> int:
        return sum(1 for c in self.checks if c.status == VerificationStatus.FAILED)


# ── evidence ──────────────────────────────────────────────────────────────────

class RuntimeEvidence(BaseModel):
    step_id: str = ""
    action_description: str = ""
    screen_before: Optional[str] = None         # screenshot path
    screen_after: Optional[str] = None          # screenshot path
    expected_result: str = ""
    actual_result: str = ""
    verification_method: str = ""
    screenshots: List[str] = Field(default_factory=list)
    log_excerpts: List[str] = Field(default_factory=list)
    backend_evidence: Optional[Dict[str, Any]] = None
    database_evidence: Optional[Dict[str, Any]] = None
    status: VerificationStatus = VerificationStatus.INCONCLUSIVE
    severity: str = "info"
    reproduction_steps: List[str] = Field(default_factory=list)
    captured_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── function coverage ─────────────────────────────────────────────────────────

class FunctionCoverageItem(BaseModel):
    item_id: str = ""
    screen: str = ""
    element_label: str = ""
    element_type: str = ""
    action_attempted: str = ""
    expected_result: str = ""
    actual_result: Optional[str] = None
    status: FunctionStatus = FunctionStatus.DISCOVERED
    evidence_links: List[str] = Field(default_factory=list)
    severity: Optional[str] = None
    notes: str = ""
    discovered_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tested_at: Optional[str] = None


# ── capability inventory ──────────────────────────────────────────────────────

class CapabilityGap(BaseModel):
    capability: str = ""
    status: CapabilityStatus = CapabilityStatus.UNAVAILABLE
    reason: str = ""
    workaround: str = ""
    todo: str = ""


# ── final report ──────────────────────────────────────────────────────────────

class InteractiveRuntimeReport(BaseModel):
    report_id: str = ""
    app_name: str = ""
    app_type: str = ""
    launch_command: str = ""
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    permission_summary: Dict[str, Any] = Field(default_factory=dict)
    capability_gaps: List[CapabilityGap] = Field(default_factory=list)

    tested_screens: List[str] = Field(default_factory=list)
    total_functions_discovered: int = 0
    total_functions_tested: int = 0
    total_passed: int = 0
    total_failed: int = 0
    total_blocked: int = 0
    total_skipped: int = 0
    total_inconclusive: int = 0

    passed_flows: List[str] = Field(default_factory=list)
    failed_flows: List[str] = Field(default_factory=list)
    blocked_flows: List[str] = Field(default_factory=list)
    inconclusive_flows: List[str] = Field(default_factory=list)

    screenshot_paths: List[str] = Field(default_factory=list)
    relevant_log_lines: List[str] = Field(default_factory=list)

    final_verdict: str = ""
    verdict_reason: str = ""
    recommendations: List[str] = Field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def coverage_pct(self) -> float:
        if self.total_functions_discovered == 0:
            return 0.0
        return self.total_functions_tested / self.total_functions_discovered * 100


# ── AI runtime enums ──────────────────────────────────────────────────────────

class AIVerdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNCLEAR = "unclear"


class IntentCategory(str, Enum):
    NAVIGATION = "navigation"
    FORM_SUBMIT = "form_submit"
    SAVE = "save"
    DELETE = "delete"
    GENERATE_AI_CONTENT = "generate_ai_content"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    SEARCH = "search"
    FILTER = "filter"
    PAYMENT = "payment"
    PRINT = "print"
    SYNC = "sync"
    LOGIN = "login"
    LOGOUT = "logout"
    SETTINGS = "settings"
    UNKNOWN = "unknown"


# ── AI runtime config ─────────────────────────────────────────────────────────

class AIGuidanceConfig(BaseModel):
    enabled: bool = False
    provider: str = "local_ollama"
    model: str = "qwen2.5vl:7b"
    allow_cloud: bool = False
    require_approval_for_ai_calls: bool = True


class VisionAnalysisConfig(BaseModel):
    enabled: bool = False
    provider: str = "local_ollama"
    model: str = "qwen2.5vl:7b"
    fallback_to_accessibility_tree: bool = True
    max_coordinate_click_confidence: float = 0.6


class LiveGuidedConfig(BaseModel):
    enabled: bool = False
    print_steps: bool = True
    write_markdown_trace: bool = True
    write_json_trace: bool = True
    pause_on_fail: bool = False
    pause_on_unclear: bool = False


class EvidenceGroundingConfig(BaseModel):
    pass_requires_evidence: bool = True
    ai_only_max_confidence: float = 0.5
    unclear_on_missing_evidence: bool = True
    require_screenshot_for_ui_actions: bool = True


class CuriosityConfig(BaseModel):
    enabled: bool = True
    max_actions: int = 25
    avoid_destructive_actions: bool = True
    prioritize_untested_elements: bool = True


class TestObjectiveConfig(BaseModel):
    name: str = ""
    description: str = ""
    priority: str = "normal"


class GenericExpectedSignals(BaseModel):
    logs: List[str] = Field(default_factory=list)
    ui_text_any: List[str] = Field(default_factory=list)


# ── AI runtime data models ────────────────────────────────────────────────────

class VisionAnalysis(BaseModel):
    """Output of VisionScreenAnalyzer."""
    screen_id: str = ""
    possible_screen_purpose: str = ""
    inferred_clickable_regions: List[Dict[str, Any]] = Field(default_factory=list)
    inferred_buttons: List[str] = Field(default_factory=list)
    inferred_inputs: List[str] = Field(default_factory=list)
    inferred_menus: List[str] = Field(default_factory=list)
    uncertainty_score: float = 1.0      # 0.0 = certain, 1.0 = fully uncertain
    provider_used: str = "accessibility_tree"
    capability_gap: Optional["CapabilityGap"] = None
    raw_analysis: Optional[str] = None


class IntentInference(BaseModel):
    """Output of IntentInferenceEngine."""
    element_label: str = ""
    element_type: str = ""
    intent_category: IntentCategory = IntentCategory.UNKNOWN
    action_type: str = ""
    expected_outcome: str = ""
    risk_level: RiskLevel = RiskLevel.SAFE
    confidence: float = 0.5
    reasoning: str = ""


class AIActionProposal(BaseModel):
    """Output of AIActionDecider."""
    proposed_action: Optional[UIAction] = None
    reason: str = ""
    expected_outcome: str = ""
    risk_level: RiskLevel = RiskLevel.SAFE
    required_permissions: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    ask_user: bool = False
    blocked: bool = False
    block_reason: str = ""


class OracleSuggestion(BaseModel):
    """Output of AIOracle. Suggestion only — not a final verdict."""
    step_id: str = ""
    suggested_verdict: AIVerdict = AIVerdict.UNCLEAR
    reasoning: str = ""
    confidence: float = 0.0
    evidence_gaps: List[str] = Field(default_factory=list)
    recommended_next_check: str = ""
    is_suggestion_only: bool = True     # always True — oracle cannot finalize


class EvidenceSource(BaseModel):
    source_type: str = ""               # ui_state | log | db | backend | screenshot | file
    description: str = ""
    strength: str = "weak"             # strong | moderate | weak
    detail: Optional[str] = None


class GroundedVerdict(BaseModel):
    """Final verdict from EvidenceGrounder. This is authoritative."""
    step_id: str = ""
    final_status: AIVerdict = AIVerdict.UNCLEAR
    confidence: float = 0.0
    evidence_sources_used: List[EvidenceSource] = Field(default_factory=list)
    evidence_sources_missing: List[str] = Field(default_factory=list)
    reasoning: str = ""
    next_best_check: str = ""
    oracle_suggestion: Optional[OracleSuggestion] = None
    deterministic_override: bool = False    # True if deterministic failure overrode AI


class CuriosityTarget(BaseModel):
    """Output of CuriosityEngine."""
    target_element: Optional[UIElement] = None
    target_label: str = ""
    exploration_reason: str = ""
    priority_score: float = 0.5
    stop_condition_met: bool = False
    stop_reason: str = ""


class SafetyDecision(BaseModel):
    """Output of SafetyFilter."""
    allowed: bool = True
    requires_approval: bool = False
    blocked: bool = False
    block_reason: str = ""
    risk_category: str = ""
    risk_level: RiskLevel = RiskLevel.SAFE


class GuidedStep(BaseModel):
    """One step in a live guided trace."""
    step_number: int = 0
    step_id: str = ""
    screen_title: str = ""
    screen_url: Optional[str] = None
    what_inspectra_sees: str = ""
    plan: str = ""
    why: str = ""
    permission_needed: str = ""
    action_taken: str = ""
    evidence_checked: List[str] = Field(default_factory=list)
    evidence_found: List[str] = Field(default_factory=list)
    screenshot_before: Optional[str] = None
    screenshot_after: Optional[str] = None
    log_matches: List[str] = Field(default_factory=list)
    db_check_result: Optional[str] = None
    backend_check_result: Optional[str] = None
    oracle_suggestion: Optional[OracleSuggestion] = None
    grounded_verdict: Optional[GroundedVerdict] = None
    final_verdict: AIVerdict = AIVerdict.UNCLEAR
    confidence_pct: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Extended config (update InteractiveRuntimeConfig) ─────────────────────────

class AIRuntimeConfig(BaseModel):
    """Full AI runtime config block, nested in InteractiveRuntimeConfig."""
    ai_guidance: AIGuidanceConfig = Field(default_factory=AIGuidanceConfig)
    vision_analysis: VisionAnalysisConfig = Field(default_factory=VisionAnalysisConfig)
    live_guided: LiveGuidedConfig = Field(default_factory=LiveGuidedConfig)
    evidence_grounding: EvidenceGroundingConfig = Field(default_factory=EvidenceGroundingConfig)
    curiosity: CuriosityConfig = Field(default_factory=CuriosityConfig)
    test_objective_config: Optional[TestObjectiveConfig] = None
    generic_expected_signals: GenericExpectedSignals = Field(default_factory=GenericExpectedSignals)
