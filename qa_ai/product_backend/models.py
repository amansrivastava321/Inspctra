"""
models.py - Pydantic domain models for the product backend.

No app-specific logic. All models are generic across all target types.

Security:
- base_url validated: http/https only, no file://, javascript://, etc.
- No credential fields. No raw DB URLs.
- All IDs are UUIDs generated server-side.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Literal
import urllib.parse

from pydantic import BaseModel, Field, field_validator


class Provenance(str, Enum):
    REAL_EXECUTION = "REAL_EXECUTION"
    DRY_RUN = "DRY_RUN"
    MIXED = "MIXED"
    SIMULATED = "SIMULATED"
    DEMO_EXAMPLE = "DEMO_EXAMPLE"
    UNAVAILABLE = "UNAVAILABLE"


# Read-only run comparison: observations, not historical configuration snapshots.
class RunComparisonScope(BaseModel):
    pack_id: str
    app_target_id: str


class RunComparisonObservation(BaseModel):
    run_id: str
    status: str
    execution_mode: str | None = None
    provenance: Provenance
    provenance_basis: Literal["stored", "inferred", "unavailable"]
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    retest_of: str | None = None


class RunComparisonChronology(BaseModel):
    state: Literal["forward", "reverse", "same_time", "unavailable"] = "unavailable"
    basis: Literal["completed_at", "started_at", "created_at", "unavailable"] = "unavailable"
    baseline_time: str | None = None
    comparison_time: str | None = None


class RunComparisonCitation(BaseModel):
    run_id: str
    step_id: str | None = None
    provenance: Provenance
    provenance_basis: Literal["stored", "inferred", "unavailable"]
    evidence_ids: list[str] = Field(default_factory=list)


class RunComparisonMetric(BaseModel):
    key: Literal["duration_ms", "response_time_ms", "status_code"]
    unit: Literal["ms", "http_status"]
    baseline_value: float | None = None
    comparison_value: float | None = None
    delta: float | None = None
    reason: str | None = None


class RunComparisonEvidenceSummary(BaseModel):
    complete: bool = True
    baseline_count: int | None = None
    comparison_count: int | None = None
    baseline_type_counts: dict[str, int] = Field(default_factory=dict)
    comparison_type_counts: dict[str, int] = Field(default_factory=dict)
    hash_comparison: Literal["same_hash", "different_hash", "unavailable"] = "unavailable"


class RunComparisonFailureSignature(BaseModel):
    algorithm: Literal["history_v1"] = "history_v1"
    state: Literal["same_signature", "different_signature", "unavailable"] = "unavailable"
    reason: str | None = None


class RunComparisonDisplay(BaseModel):
    error: str | None = None
    failure_reason: str | None = None
    notes: str | None = None
    expected: str | None = None
    actual: str | None = None


class RunStepComparison(BaseModel):
    step_id: str | None = None
    identity_state: Literal["matched", "baseline_only", "comparison_only", "identity_unavailable", "identity_conflict"]
    comparison_state: Literal["factual", "informational", "unavailable"] = "unavailable"
    reason_codes: list[str] = Field(default_factory=list)
    baseline_status: str | None = None
    comparison_status: str | None = None
    baseline_provenance: Provenance | None = None
    comparison_provenance: Provenance | None = None
    transition: Literal["passed_to_failed", "failed_to_passed", "passed_to_passed", "failed_to_failed", "passed_to_inconclusive", "failed_to_inconclusive", "inconclusive_to_passed", "inconclusive_to_failed", "inconclusive_to_inconclusive", "not_comparable"] = "not_comparable"
    baseline_citation: RunComparisonCitation | None = None
    comparison_citation: RunComparisonCitation | None = None
    baseline_display: RunComparisonDisplay | None = None
    comparison_display: RunComparisonDisplay | None = None
    metric_comparisons: list[RunComparisonMetric] = Field(default_factory=list)
    evidence_comparison: RunComparisonEvidenceSummary = Field(default_factory=RunComparisonEvidenceSummary)
    failure_signature_comparison: RunComparisonFailureSignature = Field(default_factory=RunComparisonFailureSignature)


class RunComparisonSummaryCounts(BaseModel):
    matched: int = 0
    passed_to_failed: int = 0
    failed_to_passed: int = 0
    passed_to_passed: int = 0
    failed_to_failed: int = 0
    inconclusive_transitions: int = 0
    baseline_only: int = 0
    comparison_only: int = 0
    identity_unavailable: int = 0
    identity_conflict: int = 0
    not_comparable: int = 0


class RunComparisonCoverage(BaseModel):
    complete: bool = True
    evidence_limit_per_run: int = 500
    step_limit_per_run: int = 500
    result_bytes_limit_per_run: int = 2_097_152
    omissions: list[str] = Field(default_factory=list)


class RunComparisonComparability(BaseModel):
    state: Literal["partial", "unavailable"]
    configuration_snapshot_available: Literal[False] = False
    reason_codes: list[str] = Field(default_factory=list)


class RunComparisonResponse(BaseModel):
    schema_version: Literal["1"] = "1"
    baseline_run_id: str
    comparison_run_id: str
    selection_mode: Literal["explicit"] = "explicit"
    scope: RunComparisonScope
    baseline: RunComparisonObservation
    comparison: RunComparisonObservation
    chronology: RunComparisonChronology
    provenance_compatibility: Literal["compatible", "partial", "informational", "unavailable"]
    comparability: RunComparisonComparability
    comparability_warnings: list[str]
    coverage: RunComparisonCoverage
    summary_counts: RunComparisonSummaryCounts
    step_comparisons: list[RunStepComparison]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _validate_local_http_url(url: Optional[str]) -> Optional[str]:
    """
    Accept only http/https URLs. Reject file://, javascript://, data://, etc.
    Returns None if url is None/empty.
    Raises ValueError on invalid scheme.
    """
    if not url:
        return url
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as exc:
        raise ValueError(f"Invalid URL: {exc}") from exc
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"base_url must use http or https scheme, got: {parsed.scheme!r}"
        )
    if not parsed.netloc:
        raise ValueError("base_url must include a host.")
    return url


MAX_RETEST_LINEAGE_DEPTH = 10
"""Original run = depth 0. A retest child's depth is parent depth + 1.
A new child may be created only if its resulting depth <= this value."""

SUPPORTED_WEB_ACTIONS = frozenset({
    "navigate", "screenshot", "click", "type", "select", "press",
    "wait_for_selector", "assert_visible", "assert_text_contains",
    "assert_url_contains", "assert_title_contains",
    "measure_page_load", "assert_page_load_under",
    "check_accessibility", "assert_accessibility",
    "accessibility_scan", "assert_no_critical_a11y_violations", "assert_no_a11y_violations",
    "assert_visual_match", "visual_capture", "visual_compare",
    "passive_security_check", "assert_no_critical_security_findings", "assert_security_headers_present", "assert_cookie_flags_secure",
})

SUPPORTED_API_ACTIONS = frozenset({
    "api_request", "assert_status", "assert_json_path",
    "assert_header_contains", "assert_body_contains", "assert_response_time_under",
    "assert_api_response_time_under",
    "passive_security_check", "assert_no_critical_security_findings", "assert_security_headers_present", "assert_cookie_flags_secure",
})

SUPPORTED_TEST_STEP_ACTIONS = SUPPORTED_WEB_ACTIONS | SUPPORTED_API_ACTIONS
SUPPORTED_HTTP_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})


# ── Project ───────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    tags: List[str] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class Project(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)
    provenance: Provenance = Field(default=Provenance.UNAVAILABLE)


# ── AppTarget ─────────────────────────────────────────────────────────────────

class AppTargetCreate(BaseModel):
    project_id: str
    name: str
    app_type: str  # web, android, ios, native_macos, etc.
    base_url: Optional[str] = None
    description: str = ""
    tags: List[str] = Field(default_factory=list)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_local_http_url(v)


class AppTargetUpdate(BaseModel):
    name: Optional[str] = None
    app_type: Optional[str] = None
    base_url: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_local_http_url(v)


class AppTarget(BaseModel):
    id: str = Field(default_factory=_new_id)
    project_id: str
    name: str
    app_type: str
    base_url: Optional[str] = None  # http/https only — validated on write
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)
    # Source / discovery fields (optional, set via discovery flow)
    source_type: Optional[str] = None        # local_folder, web_url, api_base_url, manual
    source_path: Optional[str] = None        # local folder path (display only, not scanned again)
    source_url: Optional[str] = None         # web / api URL
    launch_command: Optional[str] = None     # detected or user-entered launch command
    working_directory: Optional[str] = None  # resolved local working dir
    discovery_id: Optional[str] = None       # discovery result that created this app
    detected_stack: Optional[str] = None     # comma-separated stack labels
    provenance: Provenance = Field(default=Provenance.UNAVAILABLE)


# ── ValidationStep ────────────────────────────────────────────────────────────

class ValidationStep(BaseModel):
    step_id: str = Field(default_factory=_new_id)
    order: int = 0
    description: str
    action_type: str = "interact"   # interact | verify | wait | navigate | screenshot
    target: Optional[str] = None    # CSS selector, URL path, element label, etc.
    input_value: Optional[str] = None
    expected_result: Optional[str] = None
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    optional: bool = False
    method: Optional[str] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, Any]] = None
    query_params: Optional[Dict[str, Any]] = None
    body_json: Optional[Any] = None
    expected_status: Optional[int] = None
    expected_json_path: Optional[str] = None
    expected_value: Optional[Any] = None
    budget_ms: Optional[int] = None
    warn_ms: Optional[int] = None
    metric_name: Optional[str] = None


# ── ValidationPack ────────────────────────────────────────────────────────────

class ValidationPackCreate(BaseModel):
    project_id: str
    name: str
    description: str = ""
    steps: List[ValidationStep] = Field(default_factory=list)
    app_id: Optional[str] = None
    schedule: Optional[str] = None         # none | daily | nightly | weekdays | hourly
    schedule_enabled: bool = False


class ValidationPackUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    steps: Optional[List[ValidationStep]] = None
    app_id: Optional[str] = None
    schedule: Optional[str] = None
    schedule_enabled: Optional[bool] = None


class ValidationPack(BaseModel):
    id: str = Field(default_factory=_new_id)
    project_id: str
    name: str
    description: str = ""
    steps: List[ValidationStep] = Field(default_factory=list)
    app_id: Optional[str] = None
    schedule: Optional[str] = None
    schedule_enabled: bool = False
    next_run_at: Optional[str] = None
    last_scheduled_run_at: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)
    provenance: Provenance = Field(default=Provenance.UNAVAILABLE)


# ── LiveRunRecord ─────────────────────────────────────────────────────────────

class StartRunRequest(BaseModel):
    app_target_id: str
    execution_mode: Optional[str] = "automated"  # manual | automated


class ManualStepResultRequest(BaseModel):
    status: str
    actual_result: Optional[str] = ""
    notes: Optional[str] = ""
    failure_reason: Optional[str] = ""
    tester_name: Optional[str] = None
    evidence_ids: Optional[List[str]] = None
    completed_at: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        if v not in ("passed", "failed", "blocked", "skipped"):
            raise ValueError("status must be passed, failed, blocked, or skipped")
        return v

    @field_validator("notes")
    @classmethod
    def _validate_notes(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 2000:
            raise ValueError("notes cannot exceed 2000 characters")
        return v

    @field_validator("actual_result")
    @classmethod
    def _validate_actual_result(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 2000:
            raise ValueError("actual_result cannot exceed 2000 characters")
        return v


class LiveRunRecord(BaseModel):
    id: str = Field(default_factory=_new_id)
    pack_id: str
    app_target_id: str
    status: str = "pending"  # pending | running | completed | failed | cancelled
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    step_results: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)
    retest_of: Optional[str] = None  # parent run_id if this is a retest run
    execution_mode: str = "automated"  # manual | automated
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    # Denormalized display names — populated by the GET handler via joins
    app_name: Optional[str] = None
    pack_name: Optional[str] = None
    provenance: Provenance = Field(default=Provenance.UNAVAILABLE)
    # Durable retest-resolution record for retest children; None for ordinary
    # runs and for retest children created before this field existed.
    retest_selection: Optional[Dict[str, Any]] = None


class RetestFailedResponse(LiveRunRecord):
    """Response for POST /runs/{run_id}/retest-failed.

    Extends LiveRunRecord (id, retest_of, etc. stay for backward compatibility)
    with explicit stable-step-id resolution outcome so callers never have to
    guess whether the retest actually covered what they expected.
    """
    parent_run_id: str
    retest_run_id: str
    requested_step_ids: List[str] = Field(default_factory=list)
    resolved_step_ids: List[str] = Field(default_factory=list)
    unresolved_step_ids: List[str] = Field(default_factory=list)
    identity_conflicts: List[str] = Field(default_factory=list)
    definition_continuity: Literal["verified", "changed", "unavailable"] = "unavailable"
    definition_source: Literal["normalized", "legacy", "none"] = "none"
    execution_started: bool = False


class RunEventRecord(BaseModel):
    id: int
    run_id: str
    step_index: Optional[int] = None
    step_id: Optional[str] = None
    event_type: str
    message: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now_iso)


# ── PermissionRecord ──────────────────────────────────────────────────────────

class PermissionDecision(BaseModel):
    approved: bool
    reason: Optional[str] = None


class PermissionRecord(BaseModel):
    id: str = Field(default_factory=_new_id)
    run_id: str
    action: str
    description: str
    risk: str = "medium"   # low | medium | high | critical
    status: str = "pending"  # pending | approved | denied
    requested_at: str = Field(default_factory=_now_iso)
    resolved_at: Optional[str] = None
    reason: Optional[str] = None


# ── EvidenceFile ──────────────────────────────────────────────────────────────

class EvidenceFile(BaseModel):
    id: str = Field(default_factory=_new_id)
    evidence_id: Optional[str] = None
    run_id: str
    step_id: Optional[str] = None
    evidence_type: Optional[str] = None  # maps to `type` in DB
    name: str
    # Relative path within artifacts dir ONLY — never absolute.
    # Validated at write-time in storage; never returned as download URL.
    relative_path: str
    path: Optional[str] = None  # maps to `relative_path`
    mime_type: str = "application/octet-stream"
    size_bytes: int = 0
    created_at: str = Field(default_factory=_now_iso)
    sha256: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    provenance: Provenance = Field(default=Provenance.UNAVAILABLE)

    # Extra fields for frontend rendering compatibility
    title: Optional[str] = None
    description: Optional[str] = None
    content_preview: Optional[str] = None

    def __init__(self, **data: Any) -> None:
        if "type" in data and "evidence_type" not in data:
            data["evidence_type"] = data["type"]
        elif "evidence_type" in data and "type" not in data:
            data["type"] = data["evidence_type"]

        if "id" in data and "evidence_id" not in data:
            data["evidence_id"] = data["id"]
        elif "evidence_id" in data and "id" not in data:
            data["id"] = data["evidence_id"]

        if "relative_path" in data and "path" not in data:
            data["path"] = data["relative_path"]
        elif "path" in data and "relative_path" not in data:
            data["relative_path"] = data["path"]

        if "description" not in data and "name" in data:
            data["description"] = data["name"]
        if "title" not in data:
            data["title"] = (data.get("evidence_type") or "evidence").upper()

        super().__init__(**data)



# ── ReportRecord ──────────────────────────────────────────────────────────────

class ReportFinding(BaseModel):
    id: str
    title: str
    severity: str = "info"   # critical | high | medium | low | info
    status: Optional[str] = None
    description: Optional[str] = None
    step_name: Optional[str] = None


class ReportRecord(BaseModel):
    id: str = Field(default_factory=_new_id)
    run_id: str
    name: str
    format: str = "json"   # json | html
    relative_path: str = ""  # relative within artifacts dir; empty if no file
    created_at: str = Field(default_factory=_now_iso)
    provenance: Provenance = Field(default=Provenance.UNAVAILABLE)
    # Rich summary fields — populated by the generate endpoint
    app_name: Optional[str] = None
    pack_name: Optional[str] = None
    verdict: Optional[str] = None
    summary: Optional[str] = None
    pass_count: Optional[int] = None
    fail_count: Optional[int] = None
    unclear_count: Optional[int] = None
    evidence_count: Optional[int] = None
    api_step_count: Optional[int] = None
    api_pass_count: Optional[int] = None
    api_fail_count: Optional[int] = None
    api_avg_response_time_ms: Optional[float] = None
    perf_total_checks: Optional[int] = None
    perf_passed_budgets: Optional[int] = None
    perf_failed_budgets: Optional[int] = None
    perf_avg_page_load_ms: Optional[float] = None
    perf_avg_api_response_time_ms: Optional[float] = None
    perf_slowest_check_ms: Optional[float] = None
    a11y_total_checks: Optional[int] = None
    a11y_passed_checks: Optional[int] = None
    a11y_failed_checks: Optional[int] = None
    a11y_total_violations: Optional[int] = None
    visual_total_checks: Optional[int] = None
    visual_passed_checks: Optional[int] = None
    visual_failed_checks: Optional[int] = None
    visual_avg_diff_percent: Optional[float] = None
    visual_worst_diff_percent: Optional[float] = None
    security_total_checks: Optional[int] = None
    security_passed_checks: Optional[int] = None
    security_failed_checks: Optional[int] = None
    security_total_findings: Optional[int] = None
    security_critical_findings: Optional[int] = None
    security_warning_findings: Optional[int] = None
    findings: Optional[List[ReportFinding]] = None


class RunReportSummary(BaseModel):
    run_id: str
    pack_name: str
    app_name: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    steps_total: int
    steps_passed: int
    steps_failed: int
    steps_error: int
    failure_reasons: List[str] = Field(default_factory=list)
    provenance: Provenance = Field(default=Provenance.UNAVAILABLE)
    formats_available: List[str] = Field(default_factory=list)


# ── ConnectorStatus ───────────────────────────────────────────────────────────

class ConnectorStatus(BaseModel):
    connector_id: str
    connector_type: str
    ready: bool
    details: str = ""
    checked_at: str = Field(default_factory=_now_iso)
    provenance: Provenance = Field(default=Provenance.UNAVAILABLE)


class ConnectorHealthResponse(BaseModel):
    checked_at: str = Field(default_factory=_now_iso)
    connectors: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    ready: int = 0
    partial: int = 0
    provenance: Provenance = Field(default=Provenance.UNAVAILABLE)


class ModelRouteHealthMetric(BaseModel):
    task: str
    primary_model: str
    primary_available: bool
    fallback_models: List[str] = Field(default_factory=list)
    fallback_available: List[bool] = Field(default_factory=list)
    status: str
    provenance: Provenance = Field(default=Provenance.UNAVAILABLE)


class ModelHealthResponse(BaseModel):
    ollama_reachable: bool = False
    ollama_base_url: Optional[str] = None
    installed_models: List[str] = Field(default_factory=list)
    required_models: List[str] = Field(default_factory=list)
    missing_models: List[str] = Field(default_factory=list)
    present_models: List[str] = Field(default_factory=list)
    route_coverage: List[ModelRouteHealthMetric] = Field(default_factory=list)
    cloud_providers_disabled: Optional[bool] = None
    overall_readiness: str = "unavailable"
    recommendations: List[str] = Field(default_factory=list)
    generated_at: Optional[str] = None
    error: Optional[str] = None
    provenance: Provenance = Field(default=Provenance.UNAVAILABLE)


# ── ProductSettings ───────────────────────────────────────────────────────────

class SettingUpdate(BaseModel):
    value: str


class ProductSetting(BaseModel):
    key: str
    value: str
    updated_at: str = Field(default_factory=_now_iso)


# ── DashboardSummary ──────────────────────────────────────────────────────────

class DashboardDailyBucket(BaseModel):
    date: str
    passed: int = 0
    failed: int = 0
    total: int = 0
    pass_rate: Optional[float] = None
    provenance: Provenance = Field(default=Provenance.UNAVAILABLE)


class DashboardFailureReason(BaseModel):
    category: str
    count: int
    run_ids: List[str] = Field(default_factory=list)
    provenance: Provenance = Field(default=Provenance.UNAVAILABLE)


class DashboardCoverage(BaseModel):
    with_packs: int = 0
    total: int = 0
    percentage: Optional[float] = None
    last_pack_created_at: Optional[str] = None
    provenance: Provenance = Field(default=Provenance.UNAVAILABLE)


class DashboardFailedRun(BaseModel):
    id: str
    pack_id: str
    app_target_id: str
    app_name: Optional[str] = None
    pack_name: Optional[str] = None
    failure_reason: str
    failed_at: str
    provenance: Provenance = Field(default=Provenance.UNAVAILABLE)
    screenshot_evidence_id: Optional[str] = None
    screenshot_provenance: Provenance = Field(default=Provenance.UNAVAILABLE)


class DashboardSummary(BaseModel):
    # Legacy count names stay additive for existing clients.
    project_count: int = 0
    app_target_count: int = 0
    validation_pack_count: int = 0
    total_runs: int = 0
    runs_completed: int = 0
    runs_failed: int = 0
    runs_running: int = 0
    recent_runs: List[LiveRunRecord] = Field(default_factory=list)
    projects_count: int = 0
    apps_count: int = 0
    packs_count: int = 0
    total_runs_7d: int = 0
    passed_runs_7d: int = 0
    recent_failed_run: Optional[DashboardFailedRun] = None
    failure_reasons: List[DashboardFailureReason] = Field(default_factory=list)
    pass_rate_7d: List[DashboardDailyBucket] = Field(default_factory=list)
    coverage: DashboardCoverage = Field(default_factory=DashboardCoverage)
    last_run_at: Optional[str] = None
    last_run_provenance: Provenance = Field(default=Provenance.UNAVAILABLE)
    generated_at: str = Field(default_factory=_now_iso)
    provenance: Provenance = Field(default=Provenance.UNAVAILABLE)


class HealthResponse(BaseModel):
    status: str
    provenance: Provenance = Field(default=Provenance.UNAVAILABLE)


# ── TestPlan / TestCase ───────────────────────────────────────────────────────
#
# Generic models — no app-specific logic.
# Safety level and requires_permission must be explicit.
# No secrets or credentials stored here.

_VALID_TEST_TYPES = frozenset({
    "positive", "negative", "edge_case", "regression",
    "security", "accessibility", "performance", "data_integrity",
    "permission", "sync_offline", "api_contract", "visual", "ai_behavior",
})
_VALID_AUTOMATION_STATUS = frozenset({
    "ready", "needs_selector", "needs_credentials", "needs_permission",
    "blocked", "manual_only", "capability_gap",
})
_VALID_SAFETY_LEVELS = frozenset({"safe", "caution", "destructive", "external_cost", "real_user_impact"})
_VALID_PRIORITIES = frozenset({"P0", "P1", "P2"})
_VALID_RISK_LEVELS = frozenset({"critical", "high", "medium", "low"})


class TestCaseCreate(BaseModel):
    flow_name: str = ""
    title: str
    description: str = ""
    test_type: str = "positive"
    priority: str = "P1"
    risk_level: str = "medium"
    preconditions: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)
    expected_result: str = ""
    expected_evidence: List[str] = Field(default_factory=list)
    pass_criteria: str = ""
    fail_criteria: str = ""
    automation_status: str = "needs_selector"
    safety_level: str = "safe"
    requires_permission: bool = False
    tags: List[str] = Field(default_factory=list)
    enabled: bool = True
    confidence: Optional[float] = None
    rationale: Optional[str] = None
    generated_by: Optional[str] = None
    generation_source: Optional[str] = None
    generation_metadata: Optional[Dict[str, Any]] = None

    @field_validator("test_type")
    @classmethod
    def _check_test_type(cls, v: str) -> str:
        if v not in _VALID_TEST_TYPES:
            raise ValueError(f"test_type must be one of {sorted(_VALID_TEST_TYPES)}")
        return v

    @field_validator("automation_status")
    @classmethod
    def _check_automation_status(cls, v: str) -> str:
        if v not in _VALID_AUTOMATION_STATUS:
            raise ValueError(f"automation_status must be one of {sorted(_VALID_AUTOMATION_STATUS)}")
        return v

    @field_validator("safety_level")
    @classmethod
    def _check_safety_level(cls, v: str) -> str:
        if v not in _VALID_SAFETY_LEVELS:
            raise ValueError(f"safety_level must be one of {sorted(_VALID_SAFETY_LEVELS)}")
        return v

    @field_validator("priority")
    @classmethod
    def _check_priority(cls, v: str) -> str:
        if v not in _VALID_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(_VALID_PRIORITIES)}")
        return v

    @field_validator("risk_level")
    @classmethod
    def _check_risk_level(cls, v: str) -> str:
        if v not in _VALID_RISK_LEVELS:
            raise ValueError(f"risk_level must be one of {sorted(_VALID_RISK_LEVELS)}")
        return v


class TestCaseUpdate(BaseModel):
    flow_name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    test_type: Optional[str] = None
    priority: Optional[str] = None
    risk_level: Optional[str] = None
    preconditions: Optional[List[str]] = None
    steps: Optional[List[str]] = None
    expected_result: Optional[str] = None
    expected_evidence: Optional[List[str]] = None
    pass_criteria: Optional[str] = None
    fail_criteria: Optional[str] = None
    automation_status: Optional[str] = None
    safety_level: Optional[str] = None
    requires_permission: Optional[bool] = None
    tags: Optional[List[str]] = None
    enabled: Optional[bool] = None
    confidence: Optional[float] = None
    rationale: Optional[str] = None
    generated_by: Optional[str] = None
    generation_source: Optional[str] = None
    generation_metadata: Optional[Dict[str, Any]] = None


class TestCase(BaseModel):
    test_case_id: str = Field(default_factory=_new_id)
    plan_id: str
    pack_id: str
    app_id: Optional[str] = None
    flow_name: str = ""
    title: str
    description: str = ""
    test_type: str = "positive"
    priority: str = "P1"
    risk_level: str = "medium"
    preconditions: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)
    expected_result: str = ""
    expected_evidence: List[str] = Field(default_factory=list)
    pass_criteria: str = ""
    fail_criteria: str = ""
    automation_status: str = "needs_selector"
    safety_level: str = "safe"
    requires_permission: bool = False
    tags: List[str] = Field(default_factory=list)
    enabled: bool = True
    test_steps: List[TestCaseStep] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)
    confidence: Optional[float] = None
    rationale: Optional[str] = None
    generated_by: Optional[str] = None
    generation_source: Optional[str] = None
    generation_metadata: Optional[Dict[str, Any]] = None


class TestCaseStep(BaseModel):
    step_id: str = Field(default_factory=_new_id)
    case_id: str
    step_order: int = 0
    action_type: str
    target: Optional[str] = None
    value: Optional[str] = None
    expected: Optional[str] = None
    timeout_ms: int = Field(default=30000, ge=1, le=300000)
    optional: bool = False
    notes: Optional[str] = None
    method: Optional[str] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, Any]] = None
    query_params: Optional[Dict[str, Any]] = None
    body_json: Optional[Any] = None
    expected_status: Optional[int] = None
    expected_json_path: Optional[str] = None
    expected_value: Optional[Any] = None
    budget_ms: Optional[int] = None
    warn_ms: Optional[int] = None
    metric_name: Optional[str] = None
    confidence: Optional[float] = None
    rationale: Optional[str] = None
    generated_by: Optional[str] = None
    generation_source: Optional[str] = None
    generation_metadata: Optional[Dict[str, Any]] = None


class TestCaseStepCreate(BaseModel):
    action_type: str
    target: Optional[str] = None
    value: Optional[str] = None
    expected: Optional[str] = None
    timeout_ms: int = Field(default=30000, ge=1, le=300000)
    optional: bool = False
    notes: Optional[str] = None
    method: Optional[str] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, Any]] = None
    query_params: Optional[Dict[str, Any]] = None
    body_json: Optional[Any] = None
    expected_status: Optional[int] = None
    expected_json_path: Optional[str] = None
    expected_value: Optional[Any] = None
    budget_ms: Optional[int] = None
    warn_ms: Optional[int] = None
    metric_name: Optional[str] = None
    confidence: Optional[float] = None
    rationale: Optional[str] = None
    generated_by: Optional[str] = None
    generation_source: Optional[str] = None
    generation_metadata: Optional[Dict[str, Any]] = None

    @field_validator("target")
    @classmethod
    def _validate_target(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 500:
            raise ValueError("Selector/Target length cannot exceed 500 characters.")
        return v

    @field_validator("url")
    @classmethod
    def _validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 2000:
            raise ValueError("URL length cannot exceed 2000 characters.")
        return v

    @field_validator("value")
    @classmethod
    def _validate_value(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 1000:
            raise ValueError("Value length cannot exceed 1000 characters.")
        return v

    @field_validator("method")
    @classmethod
    def _validate_method(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        method = v.upper()
        if method not in SUPPORTED_HTTP_METHODS:
            raise ValueError(f"HTTP method must be one of {sorted(SUPPORTED_HTTP_METHODS)}")
        return method

    @field_validator("headers", "query_params")
    @classmethod
    def _validate_json_map(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v is not None and not isinstance(v, dict):
            raise ValueError("Field must be a JSON object.")
        return v

    @field_validator("action_type")
    @classmethod
    def _validate_action_type(cls, v: str) -> str:
        if v not in SUPPORTED_TEST_STEP_ACTIONS:
            raise ValueError(f"Action type {v!r} is not supported.")
        return v


class TestCaseStepUpdate(BaseModel):
    action_type: Optional[str] = None
    target: Optional[str] = None
    value: Optional[str] = None
    expected: Optional[str] = None
    timeout_ms: Optional[int] = None
    optional: Optional[bool] = None
    notes: Optional[str] = None
    method: Optional[str] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, Any]] = None
    query_params: Optional[Dict[str, Any]] = None
    body_json: Optional[Any] = None
    expected_status: Optional[int] = None
    expected_json_path: Optional[str] = None
    expected_value: Optional[Any] = None
    budget_ms: Optional[int] = None
    warn_ms: Optional[int] = None
    metric_name: Optional[str] = None
    confidence: Optional[float] = None
    rationale: Optional[str] = None
    generated_by: Optional[str] = None
    generation_source: Optional[str] = None
    generation_metadata: Optional[Dict[str, Any]] = None

    @field_validator("target")
    @classmethod
    def _validate_target(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 500:
            raise ValueError("Selector/Target length cannot exceed 500 characters.")
        return v

    @field_validator("url")
    @classmethod
    def _validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 2000:
            raise ValueError("URL length cannot exceed 2000 characters.")
        return v

    @field_validator("value")
    @classmethod
    def _validate_value(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 1000:
            raise ValueError("Value length cannot exceed 1000 characters.")
        return v

    @field_validator("method")
    @classmethod
    def _validate_method(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        method = v.upper()
        if method not in SUPPORTED_HTTP_METHODS:
            raise ValueError(f"HTTP method must be one of {sorted(SUPPORTED_HTTP_METHODS)}")
        return method

    @field_validator("headers", "query_params")
    @classmethod
    def _validate_json_map(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v is not None and not isinstance(v, dict):
            raise ValueError("Field must be a JSON object.")
        return v

    @field_validator("action_type")
    @classmethod
    def _validate_action_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in SUPPORTED_TEST_STEP_ACTIONS:
            raise ValueError(f"Action type {v!r} is not supported.")
        return v


class StepReorderRequest(BaseModel):
    step_ids: List[str]



class TestPlanGenerateRequest(BaseModel):
    force: bool = False           # overwrite existing plan if True
    app_id: Optional[str] = None  # explicit app_id — uses app_map if stored


class TestPlan(BaseModel):
    plan_id: str = Field(default_factory=_new_id)
    pack_id: str
    app_id: Optional[str] = None
    generated_from: str = "generic_app_type_template"
    coverage_summary: Dict[str, Any] = Field(default_factory=dict)
    risk_summary: Dict[str, Any] = Field(default_factory=dict)
    test_cases: List[TestCase] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


# ── Model provider / route models ─────────────────────────────────────────────

_ALLOWED_PROVIDER_TYPES = frozenset({
    "ollama", "openai_compatible", "openrouter", "openai",
    "anthropic", "gemini", "lm_studio", "llama_cpp", "vllm", "custom_http",
})

_SSRF_BLOCKED_SCHEMES = frozenset({"file", "javascript", "data", "ftp", "gopher"})


def _validate_provider_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return url
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as exc:
        raise ValueError(f"Invalid provider URL: {exc}") from exc
    if parsed.scheme in _SSRF_BLOCKED_SCHEMES:
        raise ValueError(f"Provider URL scheme not allowed: {parsed.scheme!r}")
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Provider URL must use http or https, got: {parsed.scheme!r}")
    return url


class ModelProviderCreate(BaseModel):
    provider_id: str
    provider_type: str
    name: str
    enabled: bool = False
    base_url: Optional[str] = None
    # api_key_env stores the ENV VAR NAME only — never the key value itself
    api_key_env: Optional[str] = None
    secret_ref: Optional[str] = None
    allow_cloud: bool = False
    local_only: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("provider_type")
    @classmethod
    def _validate_type(cls, v: str) -> str:
        if v not in _ALLOWED_PROVIDER_TYPES:
            raise ValueError(f"Unknown provider_type: {v!r}. Allowed: {sorted(_ALLOWED_PROVIDER_TYPES)}")
        return v

    @field_validator("base_url")
    @classmethod
    def _validate_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_provider_url(v)

    @field_validator("api_key_env")
    @classmethod
    def _no_key_value(cls, v: Optional[str]) -> Optional[str]:
        """Reject any value that looks like an actual API key (not an env var name)."""
        import re
        if not v:
            return v
        # Env var names: uppercase letters, digits, underscores
        if re.match(r"^[A-Z][A-Z0-9_]{0,127}$", v):
            return v
        raise ValueError(
            "api_key_env must be an environment variable NAME (e.g. 'OPENROUTER_API_KEY'), "
            "not the actual key value."
        )


class ModelProviderUpdate(BaseModel):
    provider_type: Optional[str] = None
    name: Optional[str] = None
    enabled: Optional[bool] = None
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None
    secret_ref: Optional[str] = None
    allow_cloud: Optional[bool] = None
    local_only: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("base_url")
    @classmethod
    def _validate_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_provider_url(v)


class ModelProviderRecord(BaseModel):
    provider_id: str
    provider_type: str
    name: str
    enabled: bool
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None   # env var NAME only — never the value
    secret_ref: Optional[str] = None
    allow_cloud: bool
    local_only: bool
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    # api_key_status: is the referenced env var set? (safe to surface)
    api_key_configured: bool = False


class ModelRouteUpdate(BaseModel):
    model: Optional[str] = None
    provider_id: Optional[str] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None
    fallback_models: Optional[List[str]] = None
    temperature: Optional[float] = None
    timeout_seconds: Optional[int] = None
    estimated_memory_gb: Optional[float] = None
    local_only: Optional[bool] = None
    requires_approval: Optional[bool] = None


class ModelRouteRecord(BaseModel):
    id: str
    task: str
    provider_id: str
    model: str
    priority: int = 1
    enabled: bool = True
    fallback_models: List[str] = Field(default_factory=list)
    temperature: float = 0.1
    timeout_seconds: int = 60
    estimated_memory_gb: float = 4.0
    local_only: bool = True
    requires_approval: bool = False
    created_at: str
    updated_at: str


class ModelUsageEvent(BaseModel):
    id: str = Field(default_factory=_new_id)
    task: str
    provider_id: str
    model: str
    latency_ms: float = 0.0
    status: str = "ok"
    fallback_used: bool = False
    tokens_in: int = 0
    tokens_out: int = 0
    created_at: str = Field(default_factory=_now_iso)


class ProviderTestRequest(BaseModel):
    """
    Request to test a provider connection.
    Cloud providers require approval_token.
    """
    approval_token: Optional[str] = None


class ProviderTestResult(BaseModel):
    provider_id: str
    success: bool
    latency_ms: float = 0.0
    error: Optional[str] = None
    model_used: Optional[str] = None
    cloud_call: bool = False
    approved: bool = False


class AIProposedTestStep(BaseModel):
    step_id: Optional[str] = None
    action_type: str
    target: Optional[str] = None
    value: Optional[str] = None
    expected: Optional[str] = None
    timeout_ms: int = 30000
    optional: bool = False
    notes: Optional[str] = None
    confidence: float = 1.0
    rationale: Optional[str] = None
    method: Optional[str] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, Any]] = None
    query_params: Optional[Dict[str, Any]] = None
    body_json: Optional[Any] = None
    expected_status: Optional[int] = None
    expected_json_path: Optional[str] = None
    expected_value: Optional[Any] = None
    budget_ms: Optional[int] = None
    warn_ms: Optional[int] = None
    metric_name: Optional[str] = None


class AIProposedTestCase(BaseModel):
    test_case_id: Optional[str] = None
    flow_name: str = ""
    title: str
    description: str = ""
    test_type: str = "positive"
    priority: str = "P1"
    risk_level: str = "medium"
    preconditions: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)
    expected_result: str = ""
    expected_evidence: List[str] = Field(default_factory=list)
    pass_criteria: str = ""
    fail_criteria: str = ""
    automation_status: str = "needs_selector"
    safety_level: str = "safe"
    requires_permission: bool = False
    tags: List[str] = Field(default_factory=list)
    enabled: bool = True
    confidence: float
    rationale: str
    test_steps: List[AIProposedTestStep] = Field(default_factory=list)


class AITestPlanPreview(BaseModel):
    pack_id: str
    app_id: Optional[str] = None
    generated_from: str = "ai_generation"
    generation_source: str = "ollama"
    coverage_summary: Dict[str, int] = Field(default_factory=dict)
    risk_summary: Dict[str, int] = Field(default_factory=dict)
    test_cases: List[AIProposedTestCase] = Field(default_factory=list)
    created_at: str
    updated_at: str
    safety_redaction_metadata: Dict[str, Any] = Field(default_factory=dict)


class AITestPlanAcceptRequest(BaseModel):
    test_cases: List[AIProposedTestCase]
    force: bool = False


# ── AI Evidence Evaluation ───────────────────────────────────────────────────

_VALID_VERDICT_ASSESSMENTS = frozenset({"supports_verdict", "contradicts_verdict", "inconclusive"})
_VALID_SUGGESTED_VERDICTS = frozenset({"pass", "fail", "blocked", "skipped"})


class AIEvaluationNote(BaseModel):
    evaluation_id: str = Field(default_factory=_new_id)
    run_id: str
    step_id: Optional[str] = None
    verdict_assessment: str
    suggested_verdict: Optional[str] = None
    confidence: float
    summary: str
    evidence_used: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    rationale: str
    generation_source: str
    generation_metadata_json: Optional[Dict[str, Any]] = None
    created_at: str = Field(default_factory=_now_iso)

    @field_validator("verdict_assessment")
    @classmethod
    def _validate_assessment(cls, v: str) -> str:
        if v not in _VALID_VERDICT_ASSESSMENTS:
            raise ValueError(f"verdict_assessment must be one of {sorted(_VALID_VERDICT_ASSESSMENTS)}")
        return v

    @field_validator("suggested_verdict")
    @classmethod
    def _validate_suggested_verdict(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _VALID_SUGGESTED_VERDICTS:
            raise ValueError(f"suggested_verdict must be one of {sorted(_VALID_SUGGESTED_VERDICTS)} or null")
        return v

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


class AIEvaluationRequest(BaseModel):
    step_id: Optional[str] = None


class AIEvaluationResponse(BaseModel):
    note: AIEvaluationNote


# ── AI Root Cause Suggestions ──────────────────────────────────────────

_ABSOLUTE_CAUSAL_WORDING = (
    "definitely caused by",
    "root cause is",
    "certainly caused",
    "guaranteed cause",
)


class AIRootCauseEvidenceRef(BaseModel):
    type: str
    id: str
    field: str
    provenance: Provenance = Provenance.UNAVAILABLE


class AIRootCauseSuggestion(BaseModel):
    suggestion_id: str = Field(default_factory=_new_id)
    analysis_id: str
    run_id: str
    step_id: Optional[str] = None
    rank: int = Field(ge=1)
    title: str
    possible_cause: str
    category: str
    confidence: float
    evidence_refs: List[AIRootCauseEvidenceRef] = Field(default_factory=list)
    supporting_signals: List[str] = Field(default_factory=list)
    contradicting_signals: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    recommended_verification: List[str] = Field(default_factory=list)
    suggested_owner_area: str = "unknown"
    source_provenance: Provenance = Provenance.UNAVAILABLE
    generation_source: str
    generation_metadata: Dict[str, Any] = Field(default_factory=dict)
    authoritative: bool = False
    created_at: str = Field(default_factory=_now_iso)

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @field_validator("authoritative")
    @classmethod
    def _reject_authoritative(cls, value: bool) -> bool:
        if value:
            raise ValueError("Root cause suggestions are advisory and cannot be authoritative")
        return False

    @field_validator("possible_cause")
    @classmethod
    def _validate_advisory_wording(cls, value: str) -> str:
        lowered = value.casefold()
        if any(phrase in lowered for phrase in _ABSOLUTE_CAUSAL_WORDING):
            raise ValueError("possible_cause must use advisory wording")
        if not any(term in lowered for term in ("possible", "may", "might", "could")):
            raise ValueError("possible_cause must explicitly remain advisory")
        return value


class AIRootCauseSuggestionBatch(BaseModel):
    analysis_id: str = Field(default_factory=_new_id)
    run_id: str
    status: str
    authoritative: bool = False
    source_provenance: Provenance = Provenance.UNAVAILABLE
    generation_source: str
    generation_metadata: Dict[str, Any] = Field(default_factory=dict)
    missing_evidence: List[str] = Field(default_factory=list)
    suggestions: List[AIRootCauseSuggestion] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now_iso)

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        if value not in {"suggested", "inconclusive"}:
            raise ValueError("status must be suggested or inconclusive")
        return value

    @field_validator("authoritative")
    @classmethod
    def _reject_authoritative(cls, value: bool) -> bool:
        if value:
            raise ValueError("Root cause suggestion batches cannot be authoritative")
        return False


class AIRootCauseRequest(BaseModel):
    step_id: Optional[str] = None


# ── Deterministic historical run memory ─────────────────────────────────────

class RunHistoryCitation(BaseModel):
    run_id: str
    step_id: Optional[str] = None
    completed_at: Optional[str] = None
    provenance: Provenance
    evidence_ids: List[str] = Field(default_factory=list)


class RunHistoryScope(BaseModel):
    pack_id: str
    app_target_id: str
    terminal_statuses: List[str] = Field(
        default_factory=lambda: ["completed", "failed", "cancelled"]
    )
    exact_match: bool = True
    configuration_snapshot_available: bool = False


class RunHistoryItem(BaseModel):
    run_id: str
    status: str
    outcome: Optional[str] = None
    execution_mode: str
    provenance: Provenance
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str
    included_in_failure_rate: bool = False
    exclusion_reason: Optional[str] = None
    citation: RunHistoryCitation


class RunHistoryFailureRate(BaseModel):
    failed: int = 0
    total: int = 0
    value: float = 0.0
    citations: List[RunHistoryCitation] = Field(default_factory=list)


class RunStepHistory(BaseModel):
    step_id: Optional[str] = None
    passed: int = 0
    failed: int = 0
    inconclusive: int = 0
    total: int = 0
    citations: List[RunHistoryCitation] = Field(default_factory=list)
    insufficient_identity: bool = False


class RepeatedFailureSignature(BaseModel):
    signature: str
    step_id: str
    category: str
    error_code: str = ""
    error: str = ""
    failure_reason: str = ""
    notes: str = ""
    occurrences: int
    citations: List[RunHistoryCitation] = Field(default_factory=list)


class RunHistoryResponse(BaseModel):
    run_id: str
    scope: RunHistoryScope
    considered_runs: int = 0
    excluded_runs: int = 0
    exclusions_by_reason: Dict[str, int] = Field(default_factory=dict)
    insufficient_history: bool = True
    comparability_warnings: List[str] = Field(default_factory=list)
    last_passed: Optional[RunHistoryItem] = None
    last_failed: Optional[RunHistoryItem] = None
    failure_rate: RunHistoryFailureRate = Field(default_factory=RunHistoryFailureRate)
    step_history: List[RunStepHistory] = Field(default_factory=list)
    repeated_failure_signatures: List[RepeatedFailureSignature] = Field(default_factory=list)
    recent_runs: List[RunHistoryItem] = Field(default_factory=list)
    manual_observations: List[RunHistoryItem] = Field(default_factory=list)
