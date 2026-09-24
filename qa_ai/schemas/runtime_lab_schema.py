"""
runtime_lab_schema.py - Strict contracts for runtime lab artifacts.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from pydantic import Field

from qa_ai.schemas.reporting_schema import ArtifactContract


class BootstrapPlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "bootstrap_plan"

    app_path: str = ""
    app_type: str = "unknown"
    dry_run: bool = True
    allow_auto_install: bool = False
    environment_ready: bool = False
    checks: List[Dict[str, Any]] = Field(default_factory=list)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    missing_dependencies: List[str] = Field(default_factory=list)


class DockerRuntimePlanArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "docker_runtime_plan"

    docker_available: bool = False
    app_path: str = ""
    app_type: str = "unknown"
    start_requested: bool = False
    can_start: bool = False
    plan_steps: List[Dict[str, Any]] = Field(default_factory=list)


class RuntimeMonitorReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "runtime_monitor_report"

    process_id: str = ""
    app_name: str = ""
    status: str = "unknown"
    crashed: bool = False
    timed_out: bool = False
    running: bool = False
    sample_count: int = 0
    error_lines: int = 0
    total_log_lines: int = 0
    error_rate: float = 0.0
    samples: List[Dict[str, Any]] = Field(default_factory=list)
    logs: Dict[str, Any] = Field(default_factory=dict)


class LiveBenchmarkSummaryArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "live_benchmark_summary"

    benchmark_root: str = ""
    dry_run: bool = False
    apps: List[Dict[str, Any]] = Field(default_factory=list)
    totals: Dict[str, Any] = Field(default_factory=dict)


class LiveBenchmarkMetricsArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "live_benchmark_metrics"

    metrics: Dict[str, Any] = Field(default_factory=dict)
    per_app: List[Dict[str, Any]] = Field(default_factory=list)


class CleanupReportArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "cleanup_report"

    terminated_processes: int = 0
    closed_browser_sessions: int = 0
    removed_temp_paths: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    success: bool = True


class RuntimeLabDoctorArtifact(ArtifactContract):
    ARTIFACT_TYPE: ClassVar[str] = "runtime_lab_doctor_report"

    status: str = "unknown"
    checks: Dict[str, Any] = Field(default_factory=dict)
