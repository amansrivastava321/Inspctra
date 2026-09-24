"""
validation_result.py - Result models for Phase 2 validation.

Covers per-target results, repeatability metrics, and flake findings.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TargetValidationStatus(str, Enum):
    NOT_RUN = "not_run"
    DRY_RUN_ONLY = "dry_run_only"
    BLOCKED_PLATFORM = "blocked_platform"
    BLOCKED_PERMISSION = "blocked_permission"
    BLOCKED_CAPABILITY = "blocked_capability"
    LIVE_PASSED = "live_passed"
    LIVE_FAILED = "live_failed"
    LIVE_UNCLEAR = "live_unclear"
    LIVE_BLOCKED = "live_blocked"
    ERROR = "error"


class ValidationResult(BaseModel):
    """Outcome for a single ValidationTarget run."""

    target_id: str
    app_name: str
    app_type: str
    status: TargetValidationStatus = TargetValidationStatus.NOT_RUN
    platform: str = ""
    driver_backend: str = ""
    driver_status: str = ""

    # dry-run findings
    dry_run_caps: Optional[Dict[str, Any]] = None
    capability_gaps: List[str] = Field(default_factory=list)
    setup_instructions: List[str] = Field(default_factory=list)
    missing_deps: List[str] = Field(default_factory=list)

    # live run findings
    live_verdict: Optional[str] = None  # passed | failed | unclear | blocked
    live_pass_count: int = 0
    live_fail_count: int = 0
    live_unclear_count: int = 0
    live_blocked_count: int = 0
    coverage_pct: float = 0.0

    # artifacts produced
    artifacts: List[str] = Field(default_factory=list)

    error: Optional[str] = None
    duration_seconds: float = 0.0
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    notes: str = ""


# ── Repeatability ─────────────────────────────────────────────────────────────

class RunMetrics(BaseModel):
    """Metrics from one run inside a repeatability trial."""
    run_index: int
    status: TargetValidationStatus
    live_verdict: Optional[str] = None
    coverage_pct: float = 0.0
    duration_seconds: float = 0.0
    capability_gaps: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class RepeatabilityResult(BaseModel):
    """Aggregated repeatability metrics across N runs of one target."""

    target_id: str
    app_name: str
    total_runs: int
    successful_runs: int   # status not ERROR and not BLOCKED_*
    stable_runs: int       # same verdict across all non-error runs
    repeatability_score: float  # stable_runs / total_runs
    verdict_distribution: Dict[str, int] = Field(default_factory=dict)
    avg_coverage_pct: float = 0.0
    avg_duration_seconds: float = 0.0
    duration_variance: float = 0.0
    runs: List[RunMetrics] = Field(default_factory=list)
    notes: str = ""


# ── Flake ──────────────────────────────────────────────────────────────────────

class FlakeSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKER = "blocker"


class FlakeFinding(BaseModel):
    """One detected flaky behavior signal."""

    target_id: str
    signal: str        # human description of what's flaky
    severity: FlakeSeverity = FlakeSeverity.LOW
    evidence: List[str] = Field(default_factory=list)  # e.g. ["run 1: PASS", "run 2: FAIL"]
    recommendation: str = ""


class FlakeReport(BaseModel):
    """Full flake analysis output for one or more targets."""

    analyzed_targets: List[str] = Field(default_factory=list)
    total_findings: int = 0
    blocker_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    findings: List[FlakeFinding] = Field(default_factory=list)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
